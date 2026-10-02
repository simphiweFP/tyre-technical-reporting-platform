import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from urllib.parse import quote

import httpx
from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.core.database import SessionLocal
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.reports.infrastructure import TechnicalReportRecord


@dataclass(frozen=True)
class BounceNotice:
    recipient_email: str
    diagnostic: str
    original_message_id: str
    claim_reference: str


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_CLAIM_RE = re.compile(
    r"Royal Tyres technical report\s+([A-Z0-9._/-]+)",
    re.IGNORECASE,
)


def _normalize_message_id(value: str | None) -> str:
    return (value or "").strip().strip("<>").lower()


def _header_value(raw_text: str, name: str) -> str:
    match = re.search(
        rf"(?im)^{re.escape(name)}:\s*(.+?)\s*$",
        raw_text,
    )
    return match.group(1).strip() if match else ""


def _extract_recipient(raw_text: str, parsed_message) -> str:
    for header_name in ("Final-Recipient", "Original-Recipient", "X-Failed-Recipients"):
        value = _header_value(raw_text, header_name)
        if value:
            addresses = _EMAIL_RE.findall(value)
            if addresses:
                return addresses[0].lower()

    for header_name in ("X-Failed-Recipients", "To"):
        value = str(parsed_message.get(header_name) or "")
        addresses = _EMAIL_RE.findall(value)
        if addresses:
            return addresses[0].lower()
    return ""


def _extract_original_message_id(raw_text: str, parsed_message) -> str:
    for name in ("Original-Message-ID", "Original-Message-Id", "X-Original-Message-ID"):
        value = _header_value(raw_text, name)
        if value:
            return value.strip()

    ndr_message_id = _normalize_message_id(parsed_message.get("Message-ID"))
    matches = re.findall(r"(?im)^Message-ID:\s*(<[^>]+>|[^\r\n]+)", raw_text)
    for value in reversed(matches):
        if _normalize_message_id(value) != ndr_message_id:
            return value.strip()
    return ""


def _extract_diagnostic(raw_text: str) -> str:
    value = _header_value(raw_text, "Diagnostic-Code")
    if value:
        value = re.sub(r"(?i)^smtp;\s*", "", value).strip()
        return value[:900]

    patterns = (
        r"(?im)^Status:\s*(5\.\d+\.\d+).*$",
        r"(?i)\b(550\s+5\.\d+\.\d+[^\r\n]*)",
        r"(?i)\b(550[^\r\n]*(?:mailbox|recipient|address)[^\r\n]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return match.group(1).strip()[:900]
    return "The recipient mail server reported a permanent delivery failure."


def parse_bounce_message(raw_message: bytes) -> BounceNotice | None:
    parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
    raw_text = raw_message.decode("utf-8", errors="replace")
    subject = str(parsed.get("Subject") or "")

    has_delivery_status = any(
        part.get_content_type() == "message/delivery-status"
        for part in parsed.walk()
    )
    subject_indicates_bounce = any(
        phrase in subject.lower()
        for phrase in (
            "undeliverable",
            "delivery status notification",
            "delivery has failed",
            "delivery failure",
            "returned mail",
        )
    )
    if not has_delivery_status and not subject_indicates_bounce:
        return None

    recipient = _extract_recipient(raw_text, parsed)
    diagnostic = _extract_diagnostic(raw_text)
    message_id = _extract_original_message_id(raw_text, parsed)
    claim_match = _CLAIM_RE.search(raw_text)
    claim_reference = claim_match.group(1) if claim_match else ""

    if not recipient and not message_id:
        return None

    return BounceNotice(
        recipient_email=recipient,
        diagnostic=diagnostic,
        original_message_id=message_id,
        claim_reference=claim_reference,
    )


async def _graph_access_token(settings: Settings, client: httpx.AsyncClient) -> str:
    tenant = settings.microsoft_tenant_id.strip()
    if not tenant or tenant.lower() == "common":
        raise RuntimeError(
            "MICROSOFT_TENANT_ID must be the Royal Tyres tenant ID for bounce monitoring"
        )
    response = await client.post(
        f"https://login.microsoftonline.com/{quote(tenant)}/oauth2/v2.0/token",
        data={
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def _find_delivery_for_bounce(notice: BounceNotice) -> DeliveryAttempt | None:
    with SessionLocal() as db:
        statement = select(DeliveryAttempt).where(
            DeliveryAttempt.deleted_at.is_(None),
            DeliveryAttempt.status == "Sent",
        )

        normalized_id = _normalize_message_id(notice.original_message_id)
        if normalized_id:
            candidates = db.scalars(
                statement.order_by(DeliveryAttempt.last_attempt_at.desc()).limit(250)
            ).all()
            for attempt in candidates:
                if _normalize_message_id(attempt.message_id) == normalized_id:
                    return attempt

        if notice.recipient_email:
            statement = statement.where(
                DeliveryAttempt.recipient_email == notice.recipient_email
            )
        if notice.claim_reference:
            statement = statement.where(
                DeliveryAttempt.claim_reference == notice.claim_reference
            )
        statement = statement.where(
            DeliveryAttempt.last_attempt_at >= datetime.now(UTC) - timedelta(days=7)
        )
        return db.scalar(statement.order_by(DeliveryAttempt.last_attempt_at.desc()).limit(1))


def _mark_delivery_failed(delivery_id, notice: BounceNotice) -> bool:
    with SessionLocal() as db:
        attempt = db.get(DeliveryAttempt, delivery_id)
        if not attempt or attempt.deleted_at is not None or attempt.status == "Failed":
            return False

        attempt.status = "Failed"
        attempt.error_message = (
            "Delivery failed after Microsoft 365 initially accepted the message. "
            + notice.diagnostic
        )[:1000]
        attempt.last_attempt_at = datetime.now(UTC)

        record = db.scalar(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.claim_reference == attempt.claim_reference
            )
        )
        if record:
            record.status = "Email Failed"
            db.add(record)

        db.add(
            AuditEvent(
                actor_id=attempt.requested_by,
                action="report.email_bounced",
                entity_type="technical_report",
                entity_id=attempt.claim_reference,
                details={
                    "delivery_id": str(attempt.id),
                    "recipient": attempt.recipient_email,
                    "message_id": attempt.message_id,
                    "diagnostic": notice.diagnostic[:500],
                },
            )
        )
        db.commit()
        return True


async def process_microsoft_bounces(settings: Settings) -> tuple[int, int]:
    if not settings.bounce_monitor_enabled:
        return 0, 0
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        return 0, 0

    mailbox = (settings.bounce_monitor_mailbox or settings.email_from).strip()
    if not mailbox:
        return 0, 0

    processed = 0
    errors = 0
    timeout = httpx.Timeout(settings.bounce_monitor_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        token = await _graph_access_token(settings, client)
        headers = {"Authorization": f"Bearer {token}"}
        since = datetime.now(UTC) - timedelta(hours=settings.bounce_monitor_lookback_hours)

        response = await client.get(
            (
                "https://graph.microsoft.com/v1.0/users/"
                f"{quote(mailbox)}/mailFolders/inbox/messages"
            ),
            headers=headers,
            params={
                "$filter": (
                    "isRead eq false and receivedDateTime ge "
                    + since.isoformat().replace("+00:00", "Z")
                ),
                "$select": "id,subject,receivedDateTime,isRead",
                "$orderby": "receivedDateTime desc",
                "$top": str(settings.bounce_monitor_batch_size),
            },
        )
        response.raise_for_status()

        for item in response.json().get("value", []):
            message_id = str(item.get("id") or "")
            subject = str(item.get("subject") or "").lower()
            if not message_id:
                continue
            if not any(
                phrase in subject
                for phrase in (
                    "undeliverable",
                    "delivery status notification",
                    "delivery has failed",
                    "delivery failure",
                    "returned mail",
                )
            ):
                continue

            try:
                mime_response = await client.get(
                    (
                        "https://graph.microsoft.com/v1.0/users/"
                        f"{quote(mailbox)}/messages/{quote(message_id)}/$value"
                    ),
                    headers=headers,
                )
                mime_response.raise_for_status()
                notice = parse_bounce_message(mime_response.content)
                if notice:
                    attempt = _find_delivery_for_bounce(notice)
                    if attempt and _mark_delivery_failed(attempt.id, notice):
                        processed += 1

                await client.patch(
                    (
                        "https://graph.microsoft.com/v1.0/users/"
                        f"{quote(mailbox)}/messages/{quote(message_id)}"
                    ),
                    headers={**headers, "Content-Type": "application/json"},
                    json={"isRead": True},
                )
            except Exception:
                errors += 1

    return processed, errors

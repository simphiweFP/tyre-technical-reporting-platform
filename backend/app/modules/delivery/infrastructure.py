import smtplib
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from email.message import EmailMessage as SmtpMessage
from email.utils import make_msgid
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.config import Settings
from backend.app.core.database import Base
from backend.app.modules.delivery.domain import EmailMessage


def _royal_tyres_signature_html(body: str) -> tuple[str, dict[str, Path]]:
    """Build the branded Royal Tyres HTML email signature."""
    assets_dir = Path(__file__).resolve().parents[3] / "assets" / "email"

    logo = assets_dir / "royal-tyres-logo.png"
    aeo = assets_dir / "aeo.png"
    rmi = assets_dir / "rmi.png"

    inline_images: dict[str, Path] = {}
    if logo.exists():
        inline_images["royal-tyres-logo"] = logo
    if aeo.exists():
        inline_images["aeo-logo"] = aeo
    if rmi.exists():
        inline_images["rmi-logo"] = rmi

    safe_body = escape(body).replace("\n", "<br>")

    logo_html = (
        '<img src="cid:royal-tyres-logo" alt="Royal Tyres" width="330" '
        'style="display:block;border:0;width:330px;max-width:100%;height:auto;">'
        if logo.exists()
        else (
            '<div style="font-family:Arial,Helvetica,sans-serif;text-align:center;'
            'width:330px;">'
            '<div style="margin:0 auto 8px;width:78px;height:78px;line-height:78px;'
            'border-radius:50%;background:#ed1c24;color:#fff;font-size:46px;">♕</div>'
            '<div style="font-size:34px;line-height:38px;font-weight:800;'
            'color:#30369a;letter-spacing:-1px;">ROYAL TYRES</div>'
            '<div style="font-size:17px;font-weight:800;color:#ed1c24;">EST. 1939</div>'
            '</div>'
        )
    )

    aeo_html = (
        '<img src="cid:aeo-logo" alt="AEO" width="64" '
        'style="display:block;border:0;width:64px;height:auto;">'
        if aeo.exists()
        else '<strong style="font-size:13px;color:#777;">AEO</strong>'
    )
    rmi_html = (
        '<img src="cid:rmi-logo" alt="RMI" width="78" '
        'style="display:block;border:0;width:78px;height:auto;">'
        if rmi.exists()
        else '<strong style="font-size:13px;color:#30369a;">RMI</strong>'
    )

    html = f"""<!doctype html>
<html>
<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#111111;">
  <div style="font-size:16px;line-height:1.45;">
    <div>{safe_body}</div>

    <div style="margin-top:28px;">Kind Regards,</div>

    <!-- Deliberately blank: no employee name or job title -->

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;border-collapse:collapse;">
      <tr>
        <td style="padding:0;">{logo_html}</td>
      </tr>
    </table>

    <div style="margin-top:10px;font-size:14px;line-height:1.35;">
      <div style="color:#ed1c24;font-weight:700;">
        Tel: +27 (031) 303 2935 | Ext: 2609
      </div>
      <div>
        <a href="https://www.google.com/maps/search/?api=1&amp;query=50+Aberdare+Drive+Phoenix+Industrial+Park+Phoenix"
           style="color:#0563c1;text-decoration:underline;">
          50 Aberdare Drive, Phoenix Industrial Park, Phoenix
        </a>
        <span> | </span>
        <a href="https://www.royaltyres.co.za"
           style="color:#0563c1;text-decoration:underline;font-weight:700;">
          www.royaltyres.co.za
        </a>
      </div>
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           style="margin-top:14px;border-collapse:collapse;">
      <tr>
        <td style="font-size:14px;font-weight:700;padding-right:10px;vertical-align:middle;">
          Follow us
        </td>
        <td style="padding-right:7px;vertical-align:middle;">
          <a href="https://www.facebook.com/RoyalTyresGroup"
             style="display:inline-block;width:27px;height:27px;line-height:27px;border:2px solid #ed1c24;border-radius:50%;text-align:center;text-decoration:none;color:#30369a;font-family:Arial,sans-serif;font-size:18px;font-weight:700;">f</a>
        </td>
        <td style="padding-right:7px;vertical-align:middle;">
          <a href="https://www.instagram.com/royaltyresza/"
             style="display:inline-block;width:27px;height:27px;line-height:27px;border:2px solid #ed1c24;border-radius:50%;text-align:center;text-decoration:none;color:#30369a;font-family:Arial,sans-serif;font-size:17px;font-weight:700;">◎</a>
        </td>
        <td style="vertical-align:middle;">
          <a href="https://www.youtube.com/@RoyalVulcanizing"
             style="display:inline-block;width:27px;height:27px;line-height:27px;border:2px solid #ed1c24;border-radius:50%;text-align:center;text-decoration:none;color:#30369a;font-family:Arial,sans-serif;font-size:14px;font-weight:700;">▶</a>
        </td>
      </tr>
    </table>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           style="margin-top:12px;border-collapse:collapse;">
      <tr>
        <td style="padding-right:55px;vertical-align:middle;">{aeo_html}</td>
        <td style="vertical-align:middle;">{rmi_html}</td>
      </tr>
    </table>

    <div style="margin-top:18px;max-width:620px;font-size:10px;line-height:1.35;color:#222222;">
      <strong>Disclaimer:</strong><br>
      <strong>
        This message contains confidential information and is intended only for the recipients
        that the sender has addressed this mail to. If you are not the intended recipient then
        you should not disseminate, distribute or copy this e-mail. Please notify
        <a href="mailto:info@royaltyres.co.za" style="color:#0563c1;">info@royaltyres.co.za</a>
        immediately by e-mail if you have received this e-mail by mistake and delete this e-mail
        from your system. E-mail transmission cannot be guaranteed to be secure or error-free as
        information could be intercepted, corrupted, lost, destroyed, arrive late or incomplete,
        or contain viruses. Royal Tyres therefore does not accept liability for any errors or
        omissions in the contents of this message, which arise as a result of e-mail transmission.
      </strong>
    </div>
  </div>
</body>
</html>"""
    return html, inline_images


def _attach_inline_image(html_part, cid: str, path: Path) -> None:
    subtype = path.suffix.lower().lstrip(".") or "png"
    if subtype == "jpg":
        subtype = "jpeg"
    html_part.add_related(
        path.read_bytes(),
        maintype="image",
        subtype=subtype,
        cid=f"<{cid}>",
        filename=path.name,
        disposition="inline",
    )


class Recipient(Base):
    __tablename__ = "report_recipients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company: Mapped[str] = mapped_column(String(150))
    contact_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    default_cc: Mapped[str] = mapped_column(Text, default="")
    branch_code: Mapped[str] = mapped_column(String(20), default="All Branches")
    category: Mapped[str] = mapped_column(String(100), default="All Categories")
    escalation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class DeliveryAttempt(Base):
    __tablename__ = "report_delivery_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    claim_reference: Mapped[str] = mapped_column(String(80), index=True)
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_recipients.id"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(255))
    cc: Mapped[list] = mapped_column(JSON, default=list)
    report_payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_pdf_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    follow_ups: Mapped[list] = mapped_column(JSON, default=list)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class SmtpEmailGateway:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: EmailMessage) -> str:
        email = SmtpMessage()
        email["Subject"] = message.subject
        email["From"] = f"{self.settings.email_from_name} <{self.settings.email_from}>"
        email["To"] = ", ".join(message.to)
        email["Message-ID"] = make_msgid()
        if message.in_reply_to:
            email["In-Reply-To"] = message.in_reply_to
        if message.references:
            email["References"] = message.references
        if message.cc:
            email["Cc"] = ", ".join(message.cc)
        email.set_content(
            f"{message.body}\n\n"
            "Kind Regards,\n\n"
            "Royal Tyres\n"
            "Tel: +27 (031) 303 2935 | Ext: 2609\n"
            "50 Aberdare Drive, Phoenix Industrial Park, Phoenix | www.royaltyres.co.za\n"
            "Facebook: https://www.facebook.com/RoyalTyresGroup\n"
            "Instagram: https://www.instagram.com/royaltyresza/\n"
            "YouTube: https://www.youtube.com/@RoyalVulcanizing\n\n"
            "Disclaimer:\n"
            "This message contains confidential information and is intended only for the "
            "recipients that the sender has addressed this mail to. If you are not the intended "
            "recipient then you should not disseminate, distribute or copy this e-mail. Please "
            "notify info@royaltyres.co.za immediately by e-mail if you have received this e-mail "
            "by mistake and delete this e-mail from your system."
        )

        html_body, inline_images = _royal_tyres_signature_html(message.body)
        email.add_alternative(html_body, subtype="html")
        html_part = email.get_payload()[-1]
        for cid, path in inline_images.items():
            _attach_inline_image(html_part, cid, path)

        if message.attachment is not None:
            email.add_attachment(
                message.attachment,
                maintype="application",
                subtype="pdf",
                filename=message.attachment_name,
            )
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=20
        ) as client:
            client.ehlo()
            if self.settings.smtp_use_tls:
                client.starttls()
                client.ehlo()
            if self.settings.smtp_username:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(email)
        return str(email["Message-ID"])

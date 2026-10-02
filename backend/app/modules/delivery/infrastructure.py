import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage as SmtpMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.config import Settings
from backend.app.core.database import Base
from backend.app.modules.delivery.domain import EmailMessage


def _royal_tyres_signature_html(body: str) -> tuple[str, dict[str, Path]]:
    """Build the Royal Tyres business-standard email signature."""
    assets_dir = Path(__file__).resolve().parents[3] / "assets" / "email"

    logo = assets_dir / "royal-tyres-logo.png"
    aeo = assets_dir / "aeo.png"
    rmi = assets_dir / "rmi.png"
    facebook = assets_dir / "facebook.png"
    instagram = assets_dir / "instagram.png"
    youtube = assets_dir / "youtube.png"

    inline_images: dict[str, Path] = {}
    for cid, path in (
        ("royal-tyres-logo", logo),
        ("aeo-logo", aeo),
        ("rmi-logo", rmi),
        ("facebook-logo", facebook),
        ("instagram-logo", instagram),
        ("youtube-logo", youtube),
    ):
        if path.exists():
            inline_images[cid] = path

    safe_body = escape(body).replace("\n", "<br>")

    logo_html = (
        '<img src="cid:royal-tyres-logo" alt="Royal Tyres" width="287" '
        'style="display:block;border:0;width:287px;max-width:100%;height:auto;">'
        if logo.exists()
        else ""
    )
    aeo_html = (
        '<img src="cid:aeo-logo" alt="AEO" width="50" height="50" '
        'style="display:block;border:0;width:50px;height:50px;">'
        if aeo.exists()
        else ""
    )
    rmi_html = (
        '<img src="cid:rmi-logo" alt="RMI" width="55" height="46" '
        'style="display:block;border:0;width:55px;height:46px;">'
        if rmi.exists()
        else ""
    )

    facebook_html = (
        '<a href="https://www.facebook.com/royaltyresza" style="text-decoration:none;">'
        '<img src="cid:facebook-logo" alt="Facebook" width="28" height="28" '
        'style="display:block;border:0;width:28px;height:28px;"></a>'
        if facebook.exists()
        else ""
    )
    instagram_html = (
        '<a href="https://www.instagram.com/royaltyres1159/" style="text-decoration:none;">'
        '<img src="cid:instagram-logo" alt="Instagram" width="28" height="28" '
        'style="display:block;border:0;width:28px;height:28px;"></a>'
        if instagram.exists()
        else ""
    )
    youtube_html = (
        '<a href="https://www.youtube.com/user/RoyalVulcanizing" '
        'style="text-decoration:none;">'
        '<img src="cid:youtube-logo" alt="YouTube" width="28" height="28" '
        'style="display:block;border:0;width:28px;height:28px;"></a>'
        if youtube.exists()
        else ""
    )

    html = f"""<!doctype html>
<html>
<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#111111;">
  <div style="font-size:14px;line-height:1.35;">
    <div>{safe_body}</div>

    <div style="margin-top:18px;">Kind Regards,</div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           style="margin-top:8px;border-collapse:collapse;">
      <tr>
        <td style="padding:0 0 8px 0;">
          {logo_html}
        </td>
      </tr>

      <tr>
        <td style="padding:0 0 4px 0;font-size:12px;line-height:16px;color:#111111;">
          <span style="color:#ed1c24;font-weight:700;">Fax:</span>
          <span> 031 312 0532 </span>
          <span style="color:#ed1c24;font-weight:700;">| Tel:</span>
          <span> 031 303 2933 </span>
          <span style="color:#ed1c24;font-weight:700;">|</span>
        </td>
      </tr>

      <tr>
        <td style="padding:0 0 8px 0;font-size:12px;line-height:16px;">
          <a href="https://www.google.com/maps/search/?api=1&amp;query=1159+Umgeni+Road+Durban+4001"
             style="color:#0563c1;text-decoration:underline;">
            1159 Umgeni Road, Durban, 4001
          </a>
          <span style="color:#ed1c24;font-weight:700;"> | </span>
          <a href="https://www.royaltyres.co.za"
             style="color:#0563c1;text-decoration:underline;font-weight:700;">
            www.royaltyres.co.za
          </a>
        </td>
      </tr>

      <tr>
        <td style="padding:0 0 3px 0;font-size:12px;font-weight:700;color:#111111;">
          Follow us
        </td>
      </tr>

      <tr>
        <td style="padding:0 0 7px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"
                 style="border-collapse:collapse;">
            <tr>
              <td style="padding-right:4px;">{facebook_html}</td>
              <td style="padding-right:4px;">{instagram_html}</td>
              <td>{youtube_html}</td>
            </tr>
          </table>
        </td>
      </tr>

      <tr>
        <td style="padding:0 0 10px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"
                 style="border-collapse:collapse;">
            <tr>
              <td style="padding-right:8px;vertical-align:middle;">{aeo_html}</td>
              <td style="vertical-align:middle;">{rmi_html}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <div style="margin-top:4px;max-width:1360px;font-size:10px;line-height:1.25;color:#111111;">
      <strong>Disclaimer:</strong><br>
      This message contains confidential information and is intended only for the recipients
      that the sender has addressed this mail to. If you are not the intended recipient then
      you should not disseminate, distribute or copy this e-mail. Please notify
      <a href="mailto:info@royaltyres.co.za"
         style="color:#0563c1;text-decoration:underline;">info@royaltyres.co.za</a>
      immediately by e-mail if you have received this e-mail by mistake and delete this e-mail
      from your system. E-mail transmission cannot be guaranteed to be secure or error-free as
      information could be intercepted, corrupted, lost, destroyed, arrive late or incomplete,
      or contain viruses. Royal Tyres therefore does not accept liability for any errors or
      omissions in the contents of this message, which arise as a result of e-mail transmission.
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


class DeliveryAttempt(Base):
    __tablename__ = "report_delivery_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    claim_reference: Mapped[str] = mapped_column(String(80), index=True)
    document_type: Mapped[str] = mapped_column(
        String(40), default="technical", server_default="technical"
    )
    recipient_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
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
            "Fax: 031 312 0532 | Tel: 031 303 2933 |\n"
            "1159 Umgeni Road, Durban, 4001 | www.royaltyres.co.za\n"
            "Facebook: https://www.facebook.com/royaltyresza\n"
            "Instagram: https://www.instagram.com/royaltyres1159/\n"
            "YouTube: https://www.youtube.com/user/RoyalVulcanizing\n\n"
            "Disclaimer:\n"
            "This message contains confidential information and is intended only for the "
            "recipients that the sender has addressed this mail to. If you are not the intended "
            "recipient then you should not disseminate, distribute or copy this e-mail. Please "
            "notify info@royaltyres.co.za immediately by e-mail if you have received this e-mail "
            "by mistake and delete this e-mail from your system. E-mail transmission cannot be "
            "guaranteed to be secure or error-free as information could be intercepted, "
            "corrupted, lost, destroyed, arrive late or incomplete, or contain viruses. Royal "
            "Tyres therefore does not accept liability for any errors or omissions in the "
            "contents of this message, which arise as a result of e-mail transmission."
        )

        html_body, inline_images = _royal_tyres_signature_html(message.body)
        email.add_alternative(html_body, subtype="html")
        html_part = email.get_payload()[-1]
        for cid, path in inline_images.items():
            _attach_inline_image(html_part, cid, path)

        if message.attachment is not None:
            maintype, subtype = message.attachment_content_type.split("/", 1)
            email.add_attachment(
                message.attachment,
                maintype=maintype,
                subtype=subtype,
                filename=message.attachment_name,
            )
        for attachment in message.attachments:
            maintype, subtype = attachment.content_type.split("/", 1)
            email.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
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

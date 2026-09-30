"""Production-provider smoke checks.

Run only against a non-production/smoke environment with explicit credentials.
Checks PostgreSQL connectivity, Gemini structured image analysis and Microsoft SMTP.
"""

import os
from io import BytesIO

from PIL import Image, ImageDraw
from sqlalchemy import text

from backend.app.core.config import get_settings
from backend.app.core.database import engine
from backend.app.modules.delivery.domain import EmailMessage
from backend.app.modules.delivery.infrastructure import SmtpEmailGateway
from backend.app.modules.media.application import AnalyseInspectionImage


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for provider smoke testing")
    return value


async def main() -> None:
    settings = get_settings()
    recipient = require("SMOKE_EMAIL_TO")

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("PostgreSQL: OK")

    image = Image.new("RGB", (900, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (40, 80),
        "BRIDGESTONE 205/55 R16 DOT AB12 CD34 3425",
        fill="black",
    )
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=90)
    result = await AnalyseInspectionImage().execute(buffer.getvalue(), "image/jpeg")
    if not isinstance(result, dict) or "comment" not in result:
        raise RuntimeError("Gemini did not return the expected structured schema")
    print("Gemini: OK")

    message_id = SmtpEmailGateway(settings).send(
        EmailMessage(
            subject="Royal Tyres provider smoke test",
            body=(
                "Automated smoke test for the Technical Reporting Platform. "
                "No action is required."
            ),
            to=(recipient,),
            cc=(),
        )
    )
    if not message_id:
        raise RuntimeError("SMTP did not return a Message-ID")
    print("Microsoft SMTP: OK")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

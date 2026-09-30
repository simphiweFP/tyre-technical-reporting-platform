import base64
import json
import httpx

from backend.app.core.config import get_settings

class GeminiTyreExtractor:
    PROMPT = """Analyse this tyre or vehicle inspection image and extract only values that are clearly visible.
Return an empty string for anything you cannot confidently read. Do not invent values.

Fields:
brand, size, pattern, dot, serialNumber, vehicleMakeModel, rtd, comment
"""

    RESPONSE_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "brand": {"type": "STRING"},
            "size": {"type": "STRING"},
            "pattern": {"type": "STRING"},
            "dot": {"type": "STRING"},
            "serialNumber": {"type": "STRING"},
            "vehicleMakeModel": {"type": "STRING"},
            "rtd": {"type": "STRING"},
            "comment": {"type": "STRING"},
        },
    }

    async def analyse(self, content: bytes, mime_type: str) -> dict[str, str]:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "data": base64.b64encode(content).decode("ascii"),
                                "mimeType": mime_type,
                            }
                        },
                        {"text": self.PROMPT},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.RESPONSE_SCHEMA,
            },
        }

        async with httpx.AsyncClient(timeout=settings.gemini_timeout_seconds) as client:
            response = await client.post(
                endpoint,
                params={"key": settings.gemini_api_key},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned an invalid structured response") from exc

        return {
            field: str(parsed.get(field) or "").strip()
            for field in (
                "brand",
                "size",
                "pattern",
                "dot",
                "serialNumber",
                "vehicleMakeModel",
                "rtd",
                "comment",
            )
        }

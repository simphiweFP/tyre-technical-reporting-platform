import json
from pathlib import Path

from backend.app.core.config import get_settings


def search_suppliers(search: str = "") -> list[dict]:
    configured = Path(get_settings().supplier_json_path)
    path = configured if configured.is_absolute() else Path.cwd() / configured
    if not path.exists():
        return []
    try:
        records = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    term = search.strip().casefold()
    result = {}
    for row in records:
        if not isinstance(row, dict) or row.get("CardType", "S") != "S":
            continue
        name = str(row.get("CardName") or "").strip()
        code = str(row.get("CardCode") or "").strip()
        if name and (not term or term in name.casefold() or term in code.casefold()):
            result[(name.casefold(), code)] = {
                "CardCode": code,
                "CardName": name,
                "CardType": "S",
                "VATNumber": row.get("VATNumber"),
            }
    return sorted(result.values(), key=lambda row: row["CardName"].casefold())[:100]

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import get_settings

_customer_sync_lock = asyncio.Lock()


def _customer_json_path() -> Path:
    settings = get_settings()
    path = Path(settings.customer_json_path)
    return path if path.is_absolute() else Path.cwd() / path


def _extract_card_names(payload: Any) -> list[str]:
    names: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            card_name = value.get("CardName") or value.get("cardName")
            if card_name is not None:
                text = str(card_name).strip()
                if text:
                    names.add(text)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(names, key=str.casefold)


def _extract_customer_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            raw_code = value.get("CardCode") or value.get("cardCode")
            raw_name = value.get("CardName") or value.get("cardName")
            if raw_code is not None and raw_name is not None:
                code = str(raw_code).strip()
                name = str(raw_name).strip()
                if code and name:
                    record: dict[str, Any] = {"CardCode": code, "CardName": name}
                    vat = (
                        value.get("VATNumber")
                        or value.get("vatNumber")
                        or value.get("FederalTaxID")
                        or value.get("federalTaxID")
                    )
                    if vat is not None:
                        record["VATNumber"] = vat
                    records.append(record)
                    return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return records


def load_json_customer_records() -> list[dict[str, Any]]:
    path = _customer_json_path()
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []

    return [item for item in payload if isinstance(item, dict)]


def load_json_customers() -> list[str]:
    return _extract_card_names(load_json_customer_records())


def search_json_customers(search: str) -> list[str]:
    term = search.strip().casefold()
    if not term:
        return load_json_customers()

    return [
        name
        for name in load_json_customers()
        if term in name.casefold()
    ]


async def fetch_sap_customers() -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.sap_customer_endpoint:
        return []

    headers: dict[str, str] = {}
    if settings.sap_api_key:
        headers[settings.sap_api_key_header] = settings.sap_api_key

    params: dict[str, str] = {}
    if settings.sap_customer_company_db:
        params["companyDb"] = settings.sap_customer_company_db

    async with httpx.AsyncClient(timeout=settings.sap_customer_timeout_seconds) as client:
        response = await client.get(
            settings.sap_customer_endpoint,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return _extract_customer_records(response.json())


def _write_customer_records(records: list[dict[str, Any]]) -> None:
    path = _customer_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


async def refresh_customer_cache() -> dict[str, Any]:
    async with _customer_sync_lock:
        sap_records = await fetch_sap_customers()
        existing = load_json_customer_records()

        existing_codes = {
            str(item.get("CardCode") or "").strip().casefold()
            for item in existing
            if str(item.get("CardCode") or "").strip()
        }
        existing_pairs = {
            (
                str(item.get("CardCode") or "").strip().casefold(),
                str(item.get("CardName") or "").strip().casefold(),
            )
            for item in existing
        }

        added = 0
        for customer in sap_records:
            code = str(customer.get("CardCode") or "").strip()
            name = str(customer.get("CardName") or "").strip()
            if not code or not name:
                continue

            key = (code.casefold(), name.casefold())
            if key in existing_pairs or code.casefold() in existing_codes:
                continue

            existing.append(customer)
            existing_codes.add(code.casefold())
            existing_pairs.add(key)
            added += 1

        if added:
            existing.sort(
                key=lambda item: str(item.get("CardName") or "").casefold()
            )
            _write_customer_records(existing)
        else:
            # Touch the cache after a successful SAP check so the daily scheduler
            # does not call SAP repeatedly when there are no new customers.
            path = _customer_json_path()
            if path.exists():
                path.touch()

        return {
            "success": True,
            "added": added,
            "total": len(existing),
            "checked": len(sap_records),
            "refreshedAt": datetime.now(UTC).isoformat(),
        }


def customer_cache_refresh_due() -> bool:
    path = _customer_json_path()
    if not path.exists():
        return True

    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return datetime.now(UTC) - modified >= timedelta(hours=24)


async def refresh_customer_cache_if_due() -> dict[str, Any] | None:
    if not customer_cache_refresh_due():
        return None
    return await refresh_customer_cache()


async def customer_suggestions(search: str) -> list[str]:
    # Normal report capture never calls SAP. It searches the local JSON cache only.
    return search_json_customers(search)

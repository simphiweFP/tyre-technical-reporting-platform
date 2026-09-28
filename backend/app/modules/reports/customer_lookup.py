import json
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import get_settings


def _extract_card_names(payload: Any) -> list[str]:
    names: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            card_name = value.get("CardName")
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


def load_json_customers() -> list[str]:
    settings = get_settings()
    path = Path(settings.customer_json_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            return _extract_card_names(json.load(file))
    except (OSError, json.JSONDecodeError):
        return []


def search_json_customers(search: str) -> list[str]:
    term = search.strip().casefold()
    if not term:
        return load_json_customers()

    return [
        name
        for name in load_json_customers()
        if term in name.casefold()
    ]


async def search_sap_customers(search: str) -> list[str]:
    settings = get_settings()
    if not settings.sap_customer_endpoint:
        return []

    headers: dict[str, str] = {}
    if settings.sap_api_key:
        headers[settings.sap_api_key_header] = settings.sap_api_key

    params = {settings.sap_customer_search_param: search.strip()}

    try:
        async with httpx.AsyncClient(timeout=settings.sap_customer_timeout_seconds) as client:
            response = await client.get(
                settings.sap_customer_endpoint,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            names = _extract_card_names(response.json())
    except (httpx.HTTPError, ValueError):
        return []

    term = search.strip().casefold()
    if not term:
        return names

    return [name for name in names if term in name.casefold()]


async def customer_suggestions(search: str) -> list[str]:
    local_matches = search_json_customers(search)
    if local_matches:
        return local_matches

    return await search_sap_customers(search)

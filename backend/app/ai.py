"""Optional AI category suggestions for merchant names.

Only merchant names are sent (for example "KPN FARM FRESH"): never amounts, dates,
account numbers, UPI IDs or anything else from a statement. It runs only when the
server has ANTHROPIC_API_KEY set and the user hasn't turned it off. Any failure
(no key, timeout, bad answer) simply leaves those rows uncategorised.
"""
import json
import logging
import re

import httpx

from .config import get_settings

log = logging.getLogger("koshio.ai")
API_URL = "https://api.anthropic.com/v1/messages"
MAX_NAMES = 150
PERSON, UNKNOWN = "Person", "Unknown"


def available() -> bool:
    return bool(get_settings().anthropic_api_key)


def _prompt(names: list[str], categories: list[str]) -> str:
    return (
        "You categorise payees from Indian bank, UPI and credit card statements.\n"
        f"Allowed categories: {json.dumps(categories)}.\n"
        f'Also allowed: "{PERSON}" when the name is clearly an individual person, and "{UNKNOWN}" '
        "when you can't tell what kind of business it is.\n"
        "Use Indian context: 'hotel' usually means a restaurant, 'filling station' a fuel pump, "
        "'medicals' a pharmacy, 'kirana' or 'farm fresh' a grocery.\n"
        "Reply with only a JSON object mapping each name exactly as given to one allowed value, "
        "with no other text.\n"
        f"Names: {json.dumps(names, ensure_ascii=False)}"
    )


def suggest_categories(names: list[str], categories: list[str]) -> dict[str, str]:
    """name -> one of `categories`, PERSON or UNKNOWN. Returns {} if the AI can't be used."""
    s = get_settings()
    names = [n for n in dict.fromkeys(names) if n][:MAX_NAMES]
    if not names or not s.anthropic_api_key:
        return {}
    try:
        resp = httpx.post(
            API_URL, timeout=25.0,
            headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": s.anthropic_model, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": _prompt(names, categories)}]},
        )
        resp.raise_for_status()
        text = "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        answer = json.loads(m.group(0)) if m else {}
    except Exception as e:  # never let the AI break an import
        log.warning("AI categorisation skipped: %s", type(e).__name__)
        return {}
    allowed = set(categories) | {PERSON, UNKNOWN}
    return {n: v for n, v in answer.items() if n in names and isinstance(v, str) and v in allowed}

"""
Wraps sources/omrin_api.py (the real Freed/Omrin backend) with a monthly
cache, so we don't hit the API more than once a month, and a fallback to
the old HTML scraper (sources/omrin.py) if the API is ever unreachable.

Two bugs fixed here from the first pass at this file:

1. `from omrin_api import ...` was a bare import. That only resolves when
   a script runs *from inside* sources/ (e.g. `cd sources && python
   test_omrin.py`) — which is how the standalone test worked. Run through
   main.py from the project root, as cron actually does, and the import
   fails, and the `except ImportError:` below silently swallowed it and
   substituted a stub that always returns []. That's *why the real API
   looked broken* even though test_omrin.py proved it works. Fixed to an
   absolute `from sources.omrin_api import ...`, and the fallback now logs
   a warning instead of failing silently.

2. A failed or empty fetch used to get cached and then treated as
   authoritative "nothing collected" data — so once the API failed once,
   every run for the rest of the month confidently reported "morgen wordt
   niets opgehaald" instead of retrying or falling back to the scraper.
   Only a genuinely non-empty result is cached now; a failure always
   retries next run and falls through to the HTML-scraper fallback
   immediately, rather than being masked for a month.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from sources.omrin_api import fetch_omrin_calendar
except ImportError:
    log.warning(
        "sources.omrin_api could not be imported (missing rsa/pycryptodome?) "
        "— Omrin API disabled for this run, falling back to the HTML scraper."
    )
    fetch_omrin_calendar = None

STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "omrin_cache.json"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def _cache_key(postcode: str, huisnummer: int, today: date) -> str:
    return f"{postcode}-{huisnummer}-{today.strftime('%Y-%m')}"


def _load_cache() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(cache))


def get_calendar(postcode: str, huisnummer: int, today: date) -> list:
    """Returns the cached calendar for this address if we have one, else
    fetches fresh from the API. Never caches an empty/failed result —
    that would silently masquerade as "confirmed nothing scheduled"."""
    key = _cache_key(postcode, huisnummer, today)
    cache = _load_cache()
    cached = cache.get(key)
    if cached:
        return cached

    if fetch_omrin_calendar is None:
        return []

    try:
        data = fetch_omrin_calendar(postcode, huisnummer)
    except Exception:
        log.exception("Omrin API call failed")
        return []

    if data:
        cache[key] = data
        _save_cache(cache)
    else:
        log.warning("Omrin API returned no calendar data for %s %s", postcode, huisnummer)

    return data


def find_tomorrow_items(calendar_data: list, today: date) -> list:
    tomorrow = today + timedelta(days=1)
    items = []
    for item in calendar_data:
        d = datetime.strptime(item["Datum"], DATETIME_FORMAT).date()
        if d == tomorrow:
            items.append(item)
    return items


def _wrap(body_html: str, tomorrow: date) -> str:
    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        ♻️ Afvalinzameling morgen ({tomorrow.isoformat()})
    </h2>
    {body_html}
    """


def render_html(items: list, tomorrow: date) -> str:
    rows = "\n".join(
        f"<li><b>{item.get('Omschrijving','')}</b> – {item.get('Info','')}</li>" for item in items
    )
    return _wrap(f'<ul style="font-family:Arial,sans-serif; font-size:14px;">{rows}</ul>', tomorrow)


def render_nothing_scheduled(tomorrow: date) -> str:
    return _wrap(
        '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">Morgen wordt niets opgehaald.</p>',
        tomorrow,
    )


def render_no_data(tomorrow: date) -> str:
    return _wrap(
        '<p style="font-family:Arial,sans-serif; font-size:14px; color:#999;">'
        'Kon ophaalschema niet ophalen — controleer sources/omrin_api.py en sources/omrin_section.py.'
        "</p>",
        tomorrow,
    )


def build_section(config: dict, today: date | None = None) -> str:
    today = today or date.today()
    postcode = config["waste"]["postcode"]
    huisnummer = config["waste"]["huisnummer"]
    tomorrow = today + timedelta(days=1)

    calendar = get_calendar(postcode, huisnummer, today)
    items = find_tomorrow_items(calendar, today)

    if items:
        return render_html(items, tomorrow)

    if calendar:
        # We got real, current calendar data and tomorrow genuinely isn't in
        # it — that's a confirmed "nothing collected", not a failure.
        return render_nothing_scheduled(tomorrow)

    # calendar is empty: either the API failed, or it's genuinely disabled.
    # Try the old HTML scraper as a last resort before giving up honestly.
    log.info("No API calendar data available — trying HTML scraper fallback")
    try:
        from sources import omrin as web_omrin

        waste_cfg = {
            "postcode": postcode,
            "huisnummer": huisnummer,
            "toevoeging": config["waste"].get("toevoeging", ""),
        }
        collections = web_omrin.get_tomorrow_collections(waste_cfg)
        return web_omrin.render_html(collections)
    except Exception:
        log.exception("HTML scraper fallback also failed")
        return render_no_data(tomorrow)

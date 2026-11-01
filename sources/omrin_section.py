"""
"Afvalinzameling morgen" section of the newsletter.

Data sources, in order:
1. Live: scraped from omrin.nl on every run (sources/omrin.py).
2. The last successful live fetch, kept in state/omrin_cache.json, in case
   omrin.nl is down or changes its page.
3. The hand-maintained sources/omrin_schedule.json, as a last resort.

The old Freed app API (api-omrin.freed.nl) stopped returning data in late
2026 and was removed.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from sources import omrin

log = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "omrin_cache.json"
SCHEDULE_FILE = Path(__file__).resolve().parent / "omrin_schedule.json"


def _manual_calendar() -> list:
    """Calendar built from the hand-maintained omrin_schedule.json, if present."""
    if not SCHEDULE_FILE.exists():
        return []
    schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    return [
        {"Datum": day, "Omschrijving": name, "Info": ""}
        for name, days in schedule.items()
        for day in days
    ]


def _cache_key(postcode: str, huisnummer: int, toevoeging: str) -> str:
    return f"{postcode}-{huisnummer}{toevoeging}"


def _load_cache() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(cache), encoding="utf-8")


def get_calendar(postcode: str, huisnummer: int, toevoeging: str, today: date) -> tuple[list, str]:
    """Returns (calendar, source) where source is "live", "cache" or "manual"."""
    key = _cache_key(postcode, huisnummer, toevoeging)
    cache = _load_cache()

    try:
        data = omrin.fetch_calendar(postcode, huisnummer, toevoeging)
        cache[key] = {"fetched": today.isoformat(), "calendar": data}
        _save_cache(cache)
        return data, "live"
    except Exception:
        log.exception("Live Omrin fetch failed")

    cached = cache.get(key)
    if isinstance(cached, dict) and cached.get("calendar"):
        log.warning("Using cached Omrin calendar from %s", cached.get("fetched"))
        return cached["calendar"], "cache"

    log.warning("Using hand-maintained omrin_schedule.json")
    return _manual_calendar(), "manual"


def find_tomorrow_items(calendar_data: list, today: date) -> list:
    tomorrow = (today + timedelta(days=1)).isoformat()
    return [item for item in calendar_data if item["Datum"][:10] == tomorrow]


def _wrap(body_html: str, tomorrow: date, note: str = "") -> str:
    footer = (
        f'<p style="font-family:Arial,sans-serif; font-size:11px; color:#999;">{note}</p>' if note else ""
    )
    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        ♻️ Afvalinzameling morgen ({tomorrow.isoformat()})
    </h2>
    {body_html}
    {footer}
    """


def render_html(items: list, tomorrow: date, note: str = "") -> str:
    rows = "\n".join(
        f"<li><b>{item.get('Omschrijving','')}</b>" + (f" – {item['Info']}" if item.get("Info") else "") + "</li>"
        for item in items
    )
    return _wrap(f'<ul style="font-family:Arial,sans-serif; font-size:14px;">{rows}</ul>', tomorrow, note)


def render_nothing_scheduled(tomorrow: date, note: str = "") -> str:
    return _wrap(
        '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">Morgen wordt niets opgehaald.</p>',
        tomorrow,
        note,
    )


def render_no_data(tomorrow: date) -> str:
    return _wrap(
        '<p style="font-family:Arial,sans-serif; font-size:14px; color:#999;">'
        "Kon ophaalschema niet ophalen — controleer sources/omrin.py."
        "</p>",
        tomorrow,
    )


_SOURCE_NOTES = {
    "live": "",
    "cache": "Let op: omrin.nl was niet bereikbaar, schema van een eerdere ophaalactie.",
    "manual": "Let op: omrin.nl was niet bereikbaar, handmatig schema gebruikt.",
}


def build_section(config: dict, today: date | None = None) -> str:
    today = today or date.today()
    waste = config["waste"]
    tomorrow = today + timedelta(days=1)

    calendar, source = get_calendar(waste["postcode"], waste["huisnummer"], waste.get("toevoeging", ""), today)
    if not calendar:
        return render_no_data(tomorrow)

    note = _SOURCE_NOTES[source]
    items = find_tomorrow_items(calendar, today)
    if items:
        return render_html(items, tomorrow, note)
    return render_nothing_scheduled(tomorrow, note)

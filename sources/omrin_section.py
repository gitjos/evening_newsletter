"""
"Afvalinzameling morgen" section of the newsletter.

Data sources:
1. Live: scraped from omrin.nl (sources/omrin.py), at most once per calendar
   month. The result is kept in state/omrin_cache.json and reused for the
   rest of the month.
2. If the live fetch fails, the last successful fetch from the cache is
   used, or else the hand-maintained sources/omrin_schedule.json. The email
   then shows a line that live retrieval failed, and the next run retries.

Year boundaries: Omrin shows one tab per year (a second year appears once
it is published). All tabs are parsed. If tomorrow falls in a year the
cached calendar doesn't cover (31 December), it fetches again early; if
Omrin hasn't published that year yet, the email says so instead of
claiming nothing is collected.
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
    """Returns (calendar, note). note is "" when the data is fresh, else a
    line for the email explaining that live retrieval failed."""
    key = _cache_key(postcode, huisnummer, toevoeging)
    cache = _load_cache()
    cached = cache.get(key) if isinstance(cache.get(key), dict) else None
    tomorrow = today + timedelta(days=1)

    if cached and cached.get("calendar"):
        fetched_this_month = cached.get("fetched", "")[:7] == today.isoformat()[:7]
        covers_tomorrow = tomorrow.year in omrin.years_in(cached["calendar"])
        if fetched_this_month and covers_tomorrow:
            return cached["calendar"], ""

    try:
        data = omrin.fetch_calendar(postcode, huisnummer, toevoeging)
        cache[key] = {"fetched": today.isoformat(), "calendar": data}
        _save_cache(cache)
        log.info("Fetched Omrin calendar live (%d entries, years %s)", len(data), sorted(omrin.years_in(data)))
        return data, ""
    except Exception:
        log.exception("Live Omrin fetch failed")

    if cached and cached.get("calendar"):
        fetched = cached.get("fetched", "?")
        return cached["calendar"], (
            f"Live ophalen van de Omrin-kalender is mislukt; schema van {fetched} gebruikt."
        )

    return _manual_calendar(), (
        "Live ophalen van de Omrin-kalender is mislukt; handmatig schema (omrin_schedule.json) gebruikt."
    )


def find_tomorrow_items(calendar_data: list, today: date) -> list:
    tomorrow = (today + timedelta(days=1)).isoformat()
    return [item for item in calendar_data if item["Datum"][:10] == tomorrow]


def _wrap(body_html: str, tomorrow: date, note: str = "") -> str:
    footer = (
        f'<p style="font-family:Arial,sans-serif; font-size:12px; color:#b00020;">⚠️ {note}</p>' if note else ""
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


def render_no_data(tomorrow: date, message: str, note: str = "") -> str:
    return _wrap(
        f'<p style="font-family:Arial,sans-serif; font-size:14px; color:#999;">{message}</p>',
        tomorrow,
        note,
    )


def build_section(config: dict, today: date | None = None) -> str:
    today = today or date.today()
    waste = config["waste"]
    tomorrow = today + timedelta(days=1)

    calendar, note = get_calendar(waste["postcode"], waste["huisnummer"], waste.get("toevoeging", ""), today)
    if not calendar:
        return render_no_data(tomorrow, "Kon ophaalschema niet ophalen — controleer sources/omrin.py.", note)

    if tomorrow.year not in omrin.years_in(calendar):
        # Don't claim "nothing collected" for a year we have no calendar for.
        return render_no_data(tomorrow, f"Omrin heeft de afvalkalender voor {tomorrow.year} nog niet gepubliceerd.", note)

    items = find_tomorrow_items(calendar, today)
    if items:
        return render_html(items, tomorrow, note)
    return render_nothing_scheduled(tomorrow, note)

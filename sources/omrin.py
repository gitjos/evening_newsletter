"""
"Is there an Omrin collection tomorrow?" for the configured postcode/huisnummer.

Heads-up: this is the most fragile module in the project, and I want to be
upfront about why rather than pretend it's solid.

Omrin's public afvalkalender (https://www.omrin.nl/zelf-regelen/afvalkalender)
is a JS-driven form: you type a postcode/huisnummer and it renders the
calendar client-side, calling some backend endpoint via XHR. Because that
call happens in the browser, I can't see it from here without actually
running a browser against the live site (which I can't do in this
environment) or capturing it from your own browser's Network tab.

What every other open-source Omrin integration (Home Assistant's
"Afvalbeheer" component, the old Domoticz GarbageCalendar `m_omrin` module,
etc.) ends up doing is screen-scraping that same public page after
submitting postcode+huisnummer as query parameters. That's what this module
attempts below — but since I can't execute it against the live site from
here, treat this as a solid starting point to debug against your own
address, not as "done".

HOW TO FIX THIS IF IT RETURNS NOTHING:
1. Open https://www.omrin.nl/zelf-regelen/afvalkalender in a browser with
   devtools open, tab "Network", filter to Fetch/XHR.
2. Fill in your postcode/huisnummer and submit.
3. You'll see the real request (probably a POST or GET to some
   `/api/...` or `/umbraco/...` path) — copy its URL and payload shape.
4. Replace the `_fetch_calendar_html()` / `OMRIN_URL` below with that call,
   and adjust `_parse_rows()` to the real response shape (it might be JSON
   instead of HTML, which would actually make this whole module simpler).

Until then, this module fails soft: if it can't find anything sensible,
`get_tomorrow_collections()` returns None and the newsletter just prints
"kon niet ophalen" for this section instead of crashing the whole run.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

OMRIN_URL = "https://www.omrin.nl/zelf-regelen/afvalkalender"
HEADERS = {"User-Agent": "Mozilla/5.0 (evening-newsletter bot; personal use)"}

# Dutch month name lookup, since Omrin calendars are typically rendered in Dutch.
_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _fetch_calendar_html(postcode: str, huisnummer: int, toevoeging: str = "") -> str:
    params = {"postcode": postcode, "huisnummer": huisnummer}
    if toevoeging:
        params["toevoeging"] = toevoeging
    resp = requests.get(OMRIN_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _parse_date(text: str, year: int) -> datetime | None:
    """Parse something like '15 aug' or '15-08-2026' into a date."""
    text = text.strip().lower()

    m = re.match(r"(\d{1,2})\s+([a-z]{3,4})", text)
    if m:
        day, month_str = int(m.group(1)), m.group(2)[:3]
        month = _MONTHS.get(month_str)
        if month:
            return datetime(year, month, day)

    m = re.match(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", text)
    if m:
        day, month, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y if y > 100 else 2000 + y
        return datetime(y, month, day)

    return None


def _parse_rows(html: str) -> list[tuple[datetime, str]]:
    """Best-effort parse of a rendered calendar table into (date, waste_type) pairs."""
    soup = BeautifulSoup(html, "html.parser")
    today_year = datetime.now().year
    rows: list[tuple[datetime, str]] = []

    for row in soup.select("table tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        date = _parse_date(cells[0], today_year)
        if date:
            rows.append((date, cells[1]))

    return rows


def get_tomorrow_collections(waste_cfg: dict) -> list[str] | None:
    """Returns a list of waste-type names for tomorrow, or None if we couldn't tell."""
    try:
        html = _fetch_calendar_html(
            waste_cfg["postcode"], waste_cfg["huisnummer"], waste_cfg.get("toevoeging", "")
        )
        rows = _parse_rows(html)
    except Exception:
        log.exception("Omrin lookup failed")
        return None

    if not rows:
        return None

    tomorrow = (datetime.now() + timedelta(days=1)).date()
    return [waste_type for date, waste_type in rows if date.date() == tomorrow]


def render_html(collections: list[str] | None) -> str:
    if collections is None:
        body = '<p style="font-family:Arial,sans-serif; font-size:14px; color:#999;">Kon ophaalschema niet ophalen — zie sources/omrin.py.</p>'
    elif not collections:
        body = '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">Morgen wordt niets opgehaald.</p>'
    else:
        items = "".join(f"<li>{c}</li>" for c in collections)
        body = f'<ul style="font-family:Arial,sans-serif; font-size:14px; padding-left:20px;">{items}</ul>'

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        🗑️ Omrin – morgen
    </h2>
    {body}
    """


def build_section(config: dict) -> str:
    collections = get_tomorrow_collections(config["waste"])
    return render_html(collections)

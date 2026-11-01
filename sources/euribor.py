"""
Once-a-month 1-month Euribor mortgage note, ported from your Node-RED flow
(the fixing-date calculation, the holiday/workday logic, the FD.nl regex
scrape, and the "only send once per calendar month" gate) — minus the
sending, which main.py/emailer.py handle as part of the regular newsletter.

State (has this month's note already gone out?) is kept in a small JSON
file next to this script instead of Node-RED's msg.global, so it survives
across cron runs.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "euribor_state.json"

# Fixed Dutch public holidays as (day, month) — matches the Node-RED list exactly
# (New Year's Day, King's Day, Christmas Day, Boxing Day).
FIXED_HOLIDAYS = {(1, 1), (27, 4), (25, 12), (26, 12)}


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm — same one used in the Node-RED function."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    # The original JS returns `D + 1`, i.e. one day past the computed Easter
    # Sunday date — kept as-is here for parity with the Node-RED behaviour.
    return date(year, month, day) + timedelta(days=1)


def _is_easter_related(d: date) -> bool:
    easter = _easter_sunday(d.year)
    easter_monday = easter  # see note above: `easter` here is already +1 day
    hemelvaart = easter + timedelta(days=38)
    pinksteren_maandag = easter + timedelta(days=49)
    return d in (easter_monday, hemelvaart, pinksteren_maandag)


def _is_holiday(d: date) -> bool:
    return (d.day, d.month) in FIXED_HOLIDAYS or _is_easter_related(d)


def _is_workday(d: date) -> bool:
    return d.weekday() < 5 and not _is_holiday(d)


def euribor_fixing_date(reference: date) -> date:
    """The 15th of the month, rolled forward to the next workday."""
    d = date(reference.year, reference.month, 15)
    while not _is_workday(d):
        d += timedelta(days=1)
    return d


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_sent_month": None}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def is_due(today: date | None = None) -> bool:
    """
    True exactly once per month: on/after the fixing date, if we haven't
    already sent this month's note. Mirrors the Node-RED isSentThisMonth /
    isTimeToSent comparison.
    """
    today = today or date.today()
    state = _load_state()

    already_sent_this_month = state.get("last_sent_month") == today.strftime("%Y-%m")
    if already_sent_this_month:
        return False

    fixing_date = euribor_fixing_date(today)
    return today >= fixing_date


def mark_sent(today: date | None = None) -> None:
    today = today or date.today()
    _save_state({"last_sent_month": today.strftime("%Y-%m")})


@dataclass
class EuriborNote:
    fixing_date: date
    euribor_rate: float
    mortgage_rate: float


def fetch_euribor_rate(url: str, fixing_date: date) -> float:
    """Scrape the FD.nl historic-rates table for the fixing date's value."""
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    resp.raise_for_status()
    page = resp.text

    date_str = fixing_date.strftime("%d-%m-%Y")
    pattern = re.compile(
        # FD.nl trims trailing zeros (e.g. "2,46" instead of "2,460"), so accept any number of decimals.
        re.escape(date_str) + r'</td><td class="number">[^<]*</td><td class="price">(-?[0-9]+(?:,[0-9]+)?)'
    )
    match = pattern.search(page)
    if not match:
        raise RuntimeError(f"Could not find Euribor rate for {date_str} on {url}")

    return float(match.group(1).replace(",", "."))


def build_note(config: dict, today: date | None = None) -> EuriborNote:
    today = today or date.today()
    fixing_date = euribor_fixing_date(today)
    rate = fetch_euribor_rate(config["euribor"]["url"], fixing_date)
    margin = config["euribor"].get("margin_percent", 1.0)
    return EuriborNote(fixing_date=fixing_date, euribor_rate=rate, mortgage_rate=rate + margin)


def render_html(note: EuriborNote) -> str:
    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        🏦 Euribor hypotheekrente ({note.fixing_date.strftime('%d-%m-%Y')})
    </h2>
    <p style="font-family:Arial,sans-serif; font-size:14px;">
        1-maands Euribor: <b>{note.euribor_rate:.3f}%</b> &nbsp;→&nbsp;
        hypotheekrente (+{note.mortgage_rate - note.euribor_rate:.2f}%): <b>{note.mortgage_rate:.3f}%</b>
    </p>
    """


def build_section(config: dict) -> str | None:
    """Returns HTML only if the monthly note is due today; None otherwise."""
    if not is_due():
        return None
    note = build_note(config)
    mark_sent()
    return render_html(note)

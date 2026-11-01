"""
Live Omrin afvalkalender, scraped from https://www.omrin.nl/zelf-regelen/afvalkalender.

How the site works (checked in a real browser, Nov 2026):
- The page has an Umbraco form (ZipCode, HouseNr, HouseNrAddition plus the
  hidden anti-forgery fields __RequestVerificationToken and ufprt).
- Posting it returns the calendar as server-rendered HTML (no JSON API).
  Each waste type is a `.toggle__item` with a 12-column
  `table.table--calendar-desktop` (one column per month, day numbers in
  the cells). A `*` after a day means "gewijzigde inzameldag".
- There is one tab per year, each with a heading like "Afvalkalender 2026".
  Once Omrin publishes next year, a second tab appears; every tab is
  parsed, with the year read from its heading and the month of each column
  read from the table header.

Note: HTTPS only works on this machine because main.py calls
truststore.inject_into_ssl() — Norton re-signs TLS traffic with its own
root certificate, which Python's bundled certifi does not trust.
"""
from __future__ import annotations

import re
from datetime import date

import requests
from bs4 import BeautifulSoup

OMRIN_URL = "https://www.omrin.nl/zelf-regelen/afvalkalender"
HEADERS = {"User-Agent": "Mozilla/5.0 (evening-newsletter; personal use)"}
CHANGED_NOTE = "let op: gewijzigde inzameldag"


def _fetch_calendar_html(postcode: str, huisnummer: int, toevoeging: str = "") -> str:
    session = requests.Session()
    session.headers.update(HEADERS)

    resp = session.get(OMRIN_URL, timeout=30)
    resp.raise_for_status()
    form = BeautifulSoup(resp.text, "html.parser").find("form", action="/zelf-regelen/afvalkalender")
    if form is None:
        raise ValueError("Omrin address form not found on page")

    data = {i["name"]: i.get("value", "") for i in form.find_all("input") if i.get("name")}
    data.update(ZipCode=postcode.replace(" ", "").upper(), HouseNr=str(huisnummer), HouseNrAddition=toevoeging)

    resp = session.post(OMRIN_URL, data=data, timeout=30)
    resp.raise_for_status()
    return resp.text


_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _tab_year(tab) -> int | None:
    """Year of a calendar tab, from its heading ("Afvalkalender 2027")."""
    heading = tab.select_one(".tab__header") or tab
    m = re.search(r"\b(20\d\d)\b", heading.get_text(" ", strip=True))
    return int(m.group(1)) if m else None


def _column_months(table) -> list[int | None]:
    """Month number per column, read from the header ("Januari", "Februari", ...)."""
    return [_MONTHS.get(th.get_text(strip=True).lower()[:3]) for th in table.select("thead th")]


def parse_calendar(html: str) -> list[dict]:
    """Returns [{"Datum": "YYYY-MM-DD", "Omschrijving": ..., "Info": ...}, ...]
    for every year shown on the page (one tab per year)."""
    soup = BeautifulSoup(html, "html.parser")

    items = []
    for tab in soup.select(".tabs .tab"):
        year = _tab_year(tab)
        if year is None:
            continue
        for entry in tab.select(".toggle__item"):
            title = entry.select_one(".toggle__title")
            name = title.find(string=True, recursive=False).strip() if title else ""
            table = entry.select_one("table.table--calendar-desktop")
            if not name or table is None:
                continue
            months = _column_months(table)
            for row in table.select("tbody tr"):
                for month, cell in zip(months, row.find_all("td")):
                    text = cell.get_text(strip=True)
                    m = re.match(r"(\d{1,2})", text)
                    if not month or not m:
                        continue
                    try:
                        day = date(year, month, int(m.group(1)))
                    except ValueError:
                        continue
                    items.append({
                        "Datum": day.isoformat(),
                        "Omschrijving": name,
                        "Info": CHANGED_NOTE if "*" in text else "",
                    })
    return sorted(items, key=lambda i: (i["Datum"], i["Omschrijving"]))


def years_in(calendar: list[dict]) -> set[int]:
    return {int(item["Datum"][:4]) for item in calendar}


def fetch_calendar(postcode: str, huisnummer: int, toevoeging: str = "") -> list[dict]:
    calendar = parse_calendar(_fetch_calendar_html(postcode, huisnummer, toevoeging))
    if not calendar:
        raise ValueError(f"Omrin page returned no calendar for {postcode} {huisnummer}{toevoeging}")
    return calendar

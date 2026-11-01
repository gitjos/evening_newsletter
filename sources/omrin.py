"""
Live Omrin afvalkalender, scraped from https://www.omrin.nl/zelf-regelen/afvalkalender.

How the site works (checked in a real browser, Nov 2026):
- The page has an Umbraco form (ZipCode, HouseNr, HouseNrAddition plus the
  hidden anti-forgery fields __RequestVerificationToken and ufprt).
- Posting it returns the calendar as server-rendered HTML (no JSON API).
  Each waste type is a `.toggle__item` with a 12-column
  `table.table--calendar-desktop` (one column per month, day numbers in
  the cells). A `*` after a day means "gewijzigde inzameldag".
- The year comes from the tab label ("2026"); late in the year a second
  tab for the next year may appear, which is parsed too.

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


def parse_calendar(html: str) -> list[dict]:
    """Returns [{"Datum": "YYYY-MM-DD", "Omschrijving": ..., "Info": ...}, ...]."""
    soup = BeautifulSoup(html, "html.parser")
    labels = [label.get_text(strip=True) for label in soup.select(".tabs > label")]
    tabs = soup.select(".tabs > .tab")

    items = []
    for label, tab in zip(labels, tabs):
        if not label.isdigit():
            continue
        year = int(label)
        for entry in tab.select(".toggle__item"):
            title = entry.select_one(".toggle__title")
            name = title.find(string=True, recursive=False).strip() if title else ""
            table = entry.select_one("table.table--calendar-desktop")
            if not name or table is None:
                continue
            for row in table.select("tbody tr"):
                for month, cell in enumerate(row.find_all("td"), start=1):
                    text = cell.get_text(strip=True)
                    m = re.match(r"(\d{1,2})", text)
                    if not m:
                        continue
                    day = date(year, month, int(m.group(1)))
                    items.append({
                        "Datum": day.isoformat(),
                        "Omschrijving": name,
                        "Info": CHANGED_NOTE if "*" in text else "",
                    })
    return sorted(items, key=lambda i: (i["Datum"], i["Omschrijving"]))


def fetch_calendar(postcode: str, huisnummer: int, toevoeging: str = "") -> list[dict]:
    calendar = parse_calendar(_fetch_calendar_html(postcode, huisnummer, toevoeging))
    if not calendar:
        raise ValueError(f"Omrin page returned no calendar for {postcode} {huisnummer}{toevoeging}")
    return calendar

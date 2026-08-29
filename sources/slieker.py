"""
Today's Slieker Film programme (time + title, title linking to the
booking/movie page).

sliekerfilm.nl itself renders its programme through a JS booking widget,
which is unpleasant to scrape headlessly and breaks on every redesign.
MovieMeter maintains a plain-HTML cinema agenda page per cinema (including
Slieker), grouped by day, that links straight through to Slieker's own
ticket pages — so we scrape that instead and still land the user on
sliekerfilm.nl to book/read about the film.

NOTE: this is still screen-scraping a public page that isn't an API and can
change its markup. If this module starts coming back empty, open
`schedule_url` from config.json in a browser, view source, and check that
the anchor id pattern `day_DD` (DD = day-of-month) and the surrounding
`<a href="/film/...">` / `<a href="/boek-je-ticket/?event=...">` structure
below still match.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SliekerProgramBot/1.0)"}
TIME_RE = re.compile(r"\b([01]\d|2[0-3]):[0-5]\d\b")


@dataclass
class Showing:
    time: str
    title: str
    link: str


def _fetch_html(schedule_url: str) -> str:
    resp = requests.get(schedule_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def find_day_section(soup: BeautifulSoup, day: date):
    """Finds the element with id 'day-DD-MM-YYYY' that belongs to the given day."""
    day_id = f"day-{day.day:02d}-{day.month:02d}-{day.year}"
    element = soup.find(id=day_id)
    return element, day_id


def collect_day_elements(start_element):
    """Collect elements following the day anchor until the next day- anchor."""
    elements = []
    for el in start_element.find_all_next():
        el_id = el.get("id", "") or ""
        if el_id.startswith("day-") and el is not start_element:
            break
        elements.append(el)
    return elements


def find_entry_container(link_tag, max_depth: int = 6):
    current = link_tag
    for _ in range(max_depth):
        if current.parent is None:
            break
        current = current.parent
        movie_links = current.find_all("a", href=re.compile(r"/film/"))
        text = current.get_text(" ", strip=True)
        if len(movie_links) == 1 and TIME_RE.search(text):
            return current
    return None


def get_todays_programme(schedule_url: str) -> list[Showing]:
    html = _fetch_html(schedule_url)
    soup = BeautifulSoup(html, "html.parser")
    today = datetime.now().date()
    day_section, day_id = find_day_section(soup, today)

    if day_section is None:
        return []

    elements = collect_day_elements(day_section)

    movie_links = []
    for el in elements:
        if el.name == "a" and el.get("href") and re.search(r"/film/", el["href"]):
            movie_links.append(el)

    results: list[Showing] = []
    seen = set()

    for link in movie_links:
        container = find_entry_container(link)
        if container is None:
            continue

        href = link["href"]
        title_tag = container.find(["h2", "h3", "h4"])
        title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
        title = title.replace("Lees meer over", "").strip()
        if not title:
            continue

        text = container.get_text(" ", strip=True)
        time_match = TIME_RE.search(text)
        time_str = time_match.group(0) if time_match else None
        if time_str is None:
            continue

        key = (title, time_str, href)
        if key in seen:
            continue
        seen.add(key)

        results.append(Showing(time=time_str, title=title, link=href))

    results.sort(key=lambda s: s.time)
    return results


def render_html(showings: list[Showing], schedule_url: str | None = None) -> str:
    if not showings:
        if schedule_url:
            body = (
                '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">'
                'Geen voorstellingen vandaag — bekijk het volledige '
                f'<a href="{schedule_url}" style="color:#1a5fb4; text-decoration:none;">programma</a>.'
                '</p>'
            )
        else:
            body = '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">Geen voorstellingen vandaag.</p>'
    else:
        rows = "\n".join(
            ('<li style="margin-bottom:6px;">'
             f'<b>{s.time}</b> — <a href="{s.link}" style="color:#1a5fb4; text-decoration:none;">{s.title}</a>'
             '</li>')
            for s in showings
        )
        body = ('<ul style="font-family:Arial,sans-serif; font-size:14px; padding-left:20px; margin-top:8px;">'
                f"{rows}</ul>")

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        🎬 Slieker Film – vandaag
    </h2>
    {body}
    """


def build_section(config: dict) -> str:
    schedule_url = config["slieker"]["schedule_url"]
    showings = get_todays_programme(schedule_url)
    return render_html(showings, schedule_url)

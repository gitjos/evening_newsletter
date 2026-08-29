"""
`Vandaag in de geschiedenis` — fetches historical events for today's
date using the Wikipedia REST `onthisday` feed and renders a short list.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging

import requests

log = logging.getLogger(__name__)


@dataclass
class Event:
    year: int
    text: str
    title: str | None
    link: str | None


def fetch_events_for_date(month: int, day: int, lang: str = "nl") -> list[Event]:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        j = resp.json()
    except Exception:
        log.exception("Failed to fetch Wikipedia onthisday feed")
        return []

    events = []
    for ev in j.get("events", []):
        year = ev.get("year")
        text = ev.get("text") or ""
        pages = ev.get("pages", [])
        title = None
        link = None
        if pages:
            p = pages[0]
            title = p.get("title")
            link = p.get("content_urls", {}).get("desktop", {}).get("page")
        events.append(Event(year=year, text=text, title=title, link=link))
    return events


def render_html(events: list[Event], count: int = 5) -> str:
    items = []
    for ev in events[:count]:
        title_html = f' — <a href="{ev.link}" style="color:#1a5fb4; text-decoration:none;">{ev.title}</a>' if ev.link and ev.title else ""
        items.append(f'<li style="margin-bottom:6px;"><b>{ev.year}</b>{title_html} — {ev.text}</li>')

    if not items:
        body = '<p style="font-family:Arial,sans-serif; font-size:14px; color:#666;">Geen historische gebeurtenissen gevonden voor vandaag.</p>'
    else:
        body = "\n".join(items)
        body = f'<ul style="font-family:Arial,sans-serif; font-size:14px; padding-left:20px; margin-top:8px;">{body}</ul>'

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        📜 Vandaag in de geschiedenis
    </h2>
    {body}
    """


def build_section(config: dict) -> str:
    cfg = config.get("history", {})
    lang = cfg.get("lang", "nl")
    count = cfg.get("count", 5)
    today = date.today()
    events = fetch_events_for_date(today.month, today.day, lang=lang)
    # If language returned nothing, try English as a fallback
    if not events and lang != "en":
        events = fetch_events_for_date(today.month, today.day, lang="en")
    return render_html(events, count=count)

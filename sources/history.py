"""
`Vandaag in de geschiedenis` — fetches historical events for today's
date from Wikimedia's "on this day" feed and renders a short list.

Three things fixed here after a real 403 in production:

1. No User-Agent header was set, so requests went out with the default
   `python-requests/x.x` UA. Wikimedia's API explicitly rejects generic
   UAs — see https://meta.wikimedia.org/wiki/User-Agent_policy. Every
   request now identifies itself.
2. The URL built month/day without zero-padding (e.g. "9/1" instead of
   "09/01"). Wikimedia's feed service docs say day/month must be 2
   digits, so a request for the 1st-9th of any month could 404/403 on
   that alone.
3. The old `{lang}.wikipedia.org/api/rest_v1/feed/onthisday/...` path is
   the legacy RESTBase route, which Wikimedia has been migrating away
   from during 2026. The current documented route is
   `api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/events/{mm}/{dd}`.
   We try that first now and fall back to the legacy path, so this keeps
   working either way while the migration plays out.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging

import requests

log = logging.getLogger(__name__)

# Wikimedia blocks requests with generic/default User-Agents outright.
# https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {"User-Agent": "AvondbriefNewsletter/1.0 (personal, non-commercial home-lab project)"}

CURRENT_URL = "https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/events/{month:02d}/{day:02d}"
LEGACY_URL = "https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{month:02d}/{day:02d}"


@dataclass
class Event:
    year: int
    text: str
    title: str | None
    link: str | None


def _fetch(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("Wikimedia onthisday request failed for %s: %s", url, exc)
        return None


def fetch_events_for_date(month: int, day: int, lang: str = "nl") -> list[Event]:
    j = _fetch(CURRENT_URL.format(lang=lang, month=month, day=day))
    if j is None:
        # Fall back to the legacy RESTBase path in case the current one
        # isn't available for this language yet or has its own hiccup.
        j = _fetch(LEGACY_URL.format(lang=lang, month=month, day=day))
    if j is None:
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

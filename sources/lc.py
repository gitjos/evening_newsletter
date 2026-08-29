"""
Top headlines from LC (Leeuwarder Courant) via configurable RSS feed.

Works like `sources/nos.py` — the RSS URL is taken from the config so
you can adjust it if LC changes where their feed lives.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser

log = logging.getLogger(__name__)


@dataclass
class Headline:
    title: str
    link: str


def get_top_headlines(rss_url: str, count: int = 5) -> list[Headline]:
    feed = feedparser.parse(rss_url)

    if feed.bozo and not feed.entries:
        raise RuntimeError(f"Could not parse LC RSS feed: {feed.bozo_exception}")

    headlines = [Headline(title=entry.title.strip(), link=entry.link.strip()) for entry in feed.entries[:count]]

    if not headlines:
        raise RuntimeError("LC RSS feed returned zero entries")

    return headlines


def render_html(headlines: list[Headline]) -> str:
    items = "\n".join(
        f'<li style="margin-bottom:6px;">'
        f'<a href="{h.link}" style="color:#1a5fb4; text-decoration:none;">{h.title}</a>'
        f"</li>"
        for h in headlines
    )
    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        📰 LC – top {len(headlines)}
    </h2>
    <ul style="font-family:Arial,sans-serif; font-size:14px; padding-left:20px; margin-top:8px;">
        {items}
    </ul>
    """


def build_section(config: dict) -> str:
    cfg = config.get("lc", {})
    rss_url = cfg.get("rss_url")
    if not rss_url:
        raise RuntimeError("LC RSS URL not configured (config.json 'lc.rss_url')")
    headlines = get_top_headlines(rss_url, cfg.get("headline_count", 5))
    return render_html(headlines)

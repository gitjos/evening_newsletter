"""
Top NOS headlines, via the public NOS RSS feed.

This is the most stable source in the whole newsletter: it's a plain RSS
feed, no scraping, no auth. feedparser handles the XML quirks for us.
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
    """Return up to `count` headlines from the NOS RSS feed."""
    feed = feedparser.parse(rss_url)

    if feed.bozo and not feed.entries:
        # bozo=True just means "the XML parser had to guess something";
        # only treat it as fatal if we got no entries at all out of it.
        raise RuntimeError(f"Could not parse NOS RSS feed: {feed.bozo_exception}")

    headlines = [
        Headline(title=entry.title.strip(), link=entry.link.strip())
        for entry in feed.entries[:count]
    ]

    if not headlines:
        raise RuntimeError("NOS RSS feed returned zero entries")

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
        📰 NOS – top {len(headlines)}
    </h2>
    <ul style="font-family:Arial,sans-serif; font-size:14px; padding-left:20px; margin-top:8px;">
        {items}
    </ul>
    """


def build_section(config: dict) -> str:
    """Entry point called by main.py. Returns ready-to-insert HTML."""
    cfg = config["nos"]
    headlines = get_top_headlines(cfg["rss_url"], cfg.get("headline_count", 5))
    return render_html(headlines)

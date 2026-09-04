"""
Debug helper for sources/slieker.py — fetches the live page, saves it, and
reports what it found. Run with `python tools/slieker_debug.py` from
anywhere; it locates the project root itself.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources.slieker import _fetch_html, find_day_section, get_programme_for_day

URL = "https://sliekerfilm.nl/programma/"


def main():
    html = _fetch_html(URL)
    print("HTML length:", len(html))

    out_path = Path(__file__).resolve().parent / "slieker_page.html"
    out_path.write_text(html, encoding="utf-8")
    print("Wrote", out_path)

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tomorrow = date.today() + timedelta(days=1)
    section, day_id = find_day_section(soup, tomorrow)
    print(f"Looking for anchor id={day_id!r} -> found: {section is not None}")

    if section is None:
        import re

        anchors = sorted(set(re.findall(r'id="(day-\d{2}-\d{2}-\d{4})"', html)))
        print("Day anchors actually present on the page:", anchors)

    print("\n--- Parsed showings (tomorrow) ---")
    showings = get_programme_for_day(URL, tomorrow)
    print("Count:", len(showings))
    for s in showings:
        print(s.time, s.title, s.link)


if __name__ == "__main__":
    main()

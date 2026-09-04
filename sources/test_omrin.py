"""
Standalone smoke test: run with `python sources/test_omrin.py` from the
project root, or `python test_omrin.py` from inside sources/ — both work,
since we add the project root to sys.path ourselves rather than relying on
however the script happens to be launched (that's what caused
omrin_section.py's import bug in the first place).
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources.omrin_api import fetch_omrin_calendar
from sources.omrin_section import build_section

POSTCODE = "8916ED"
HUISNUMMER = 111

# Minimal config, same shape main.py builds from config.json.
CONFIG = {"waste": {"postcode": POSTCODE, "huisnummer": HUISNUMMER, "toevoeging": ""}}


def main():
    data = fetch_omrin_calendar(POSTCODE, HUISNUMMER)

    print("=== Raw Omrin data ===")
    print(len(data), "entries")

    print("\n=== Sorted table ===")
    rows = []
    for item in data:
        d = date.fromisoformat(item["Datum"][:10])
        rows.append((d, item.get("Omschrijving", ""), item.get("Info", "")))

    for d, summary, info in sorted(rows):
        print(f"{d}  {summary:20}  {info}")

    testdate = date(2026, 9, 1)
    print("\n=== build_section() for", testdate, "===")
    print(build_section(CONFIG, testdate))


if __name__ == "__main__":
    main()

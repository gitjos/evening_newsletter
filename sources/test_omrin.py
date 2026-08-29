# test_omrin.py
from datetime import date, datetime
import json
from omrin_api import fetch_omrin_calendar
from omrin_section import build_section

POSTCODE = "8916ED"
HUISNUMMER = 111

def main():
    data = fetch_omrin_calendar(POSTCODE, HUISNUMMER)

    print("=== Raw Omrin data ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\n=== Sorted table ===")
    rows = []
    for item in data:
        d = datetime.strptime(item["Datum"], "%Y-%m-%dT%H:%M:%S%z").date()
        rows.append((d, item.get("Omschrijving", ""), item.get("Info", "")))

    for d, summary, info in sorted(rows):
        print(f"{d}  {summary:20}  {info}")
    #testdate = datetime.date(2026, 9, 1)   
    testdate = datetime(2026, 9, 1).date()
    print(build_section(POSTCODE, HUISNUMMER, testdate))

if __name__ == "__main__":
    main()

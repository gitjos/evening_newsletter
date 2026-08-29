from datetime import date
import json
import logging

from euribor import build_section, build_note, render_html, euribor_fixing_date

# Minimal config — same shape your main project uses
CONFIG = {
    "euribor": {
        "url": "https://beurs.fd.nl/noteringen/190118378/euribor-1-maand/historie",   # or your real FD.nl URL
        "margin_percent": 1.0,
    }
}

logging.basicConfig(level=logging.INFO)

def main():
    print("=== Euribor standalone test ===")

    # Show fixing date
    fixing = euribor_fixing_date(date.today())
    print(f"Fixing date: {fixing}")

    # Try building the note (even if not due)
    try:
        note = build_note(CONFIG)
        html = render_html(note)
        print("\n--- Rendered HTML ---\n")
        print(html)
    except Exception as e:
        print("\nERROR while building note:")
        print(e)

    # Test the “is_due → build_section” path
    print("\n--- build_section() result ---")
    section = build_section(CONFIG)
    if section is None:
        print("Not due today (as expected on most days).")
    else:
        print("Section HTML:")
        print(section)

if __name__ == "__main__":
    main()

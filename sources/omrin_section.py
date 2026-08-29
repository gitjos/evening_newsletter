# omrin_section.py
import json
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from omrin_api import fetch_omrin_calendar
except ImportError:
    def fetch_omrin_calendar(postcode, huisnummer):
        return []

  
STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "omrin_cache.json"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def _load_cache():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_cache(cache):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(cache))


def _get_cached_month(key):
    cache = _load_cache()
    return cache.get(key)


def _store_cached_month(key, data):
    cache = _load_cache()
    cache[key] = data
    _save_cache(cache)


def get_calendar(postcode, huisnummer, today: date):
    key = today.strftime("%Y-%m")
    cached = _get_cached_month(key)
    if cached:
        return cached

    data = fetch_omrin_calendar(postcode, huisnummer)
    _store_cached_month(key, data)
    return data


def find_tomorrow_items(calendar_data, today: date):
    tomorrow = today + timedelta(days=1)
    items = []
    for item in calendar_data:
        d = datetime.strptime(item["Datum"], DATETIME_FORMAT).date()
        if d == tomorrow:
            items.append(item)
    return items



def render_html(items, tomorrow: date):
    rows = []
    for item in items:
        rows.append(
            f"<li><b>{item.get('Omschrijving','')}</b> – {item.get('Info','')}</li>"
        )

    items_html = "\n".join(rows)

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        ♻️ Afvalinzameling morgen ({tomorrow.isoformat()})
    </h2>
    <ul style="font-family:Arial,sans-serif; font-size:14px;">
        {items_html}
    </ul>
    """


def render_no_data(tomorrow: date):
    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        ♻️ Afvalinzameling morgen ({tomorrow.isoformat()})
    </h2>
    <p style="font-family:Arial,sans-serif; font-size:14px; color:#333;">
        Geen ophaaldata beschikbaar voor dit adres. Controleer uw postcode/huisnummer in de configuratie of bezoek de <a href="https://www.omrin.nl" style="color:#1a5fb4;">Omrin-website</a> voor de meest recente informatie.
    </p>
    """


def build_section(arg1, huisnummer=None, today: date | None = None):
    """Builds the Omrin section.

    Accepts either:
    - `config` dict (preferred): call as `build_section(config)` where
      `config["waste"]["postcode"]` and `config["waste"]["huisnummer"]`
      are used, or
    - legacy signature: `build_section(postcode, huisnummer, today)`.
    """
    # Support both the old (postcode, huisnummer, today) and new (config)
    # call patterns so callers in main.py and test_omrin.py both work.
    if isinstance(arg1, dict):
        cfg = arg1
        postcode = cfg["waste"]["postcode"]
        huisnummer = cfg["waste"].get("huisnummer")
        today = today or date.today()
    else:
        postcode = arg1
        today = today or date.today()

    calendar = get_calendar(postcode, huisnummer, today)
    items = find_tomorrow_items(calendar, today)
    tomorrow = today + timedelta(days=1)
    if not items:
        return render_no_data(tomorrow)
    return render_html(items, tomorrow)

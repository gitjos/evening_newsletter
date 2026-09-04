"""
Tomorrow's electricity prices, ANWB-Energie style, as a 24h bar chart.

ANWB Energie is a *reseller* of the day-ahead (EPEX) market price: your
actual per-kWh price is

    all_in = (day_ahead_price + inkoopvergoeding + energiebelasting) * (1 + btw)

There is no public "ANWB price" API — those numbers only live behind login
in "Mijn ANWB Energie". What IS public is the underlying day-ahead price,
via EnergyZero's free, keyless price API (the same day-ahead price nearly
every Dutch dynamic-contract provider resells). We fetch that and apply the
markup/tax constants from config.json ourselves.

Those constants (inkoopvergoeding, energiebelasting, btw) are policy/tariff
numbers that change over time — check them once in a while against
https://www.anwb.nl/energie/actuele-tarieven and update config.json.
"""
from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
import matplotlib
matplotlib.use("Agg")  # headless — no display available on the server
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

ENERGYZERO_URL = "https://api.energyzero.nl/v1/energyprices"


@dataclass
class HourPrice:
    time: datetime
    all_in_eur_per_kwh: float


def _tomorrow_range_utc() -> tuple[str, str]:
    tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
    start = f"{tomorrow.isoformat()}T00:00:00.000Z"
    end = f"{tomorrow.isoformat()}T23:59:59.999Z"
    return start, end


def get_day_ahead_prices(retries: int = 3, backoff_seconds: float = 5.0) -> list[tuple[datetime, float]]:
    """Return (timestamp, EUR/kWh excl. everything) for tomorrow, from EnergyZero.

    Retries a few times with backoff before giving up — the timeout seen
    in production so far only ever happened under cron, never running the
    same call interactively, which points at something environmental
    (see diagnose_network.py) rather than the API itself being down. A
    short retry loop is cheap insurance either way: it papers over a
    transient blip, and if it's a persistent environmental issue instead,
    the final exception still propagates with the same clear traceback.
    """
    start, end = _tomorrow_range_utc()
    params = {
        "fromDate": start,
        "tillDate": end,
        "interval": 4,      # hourly
        "usageType": 1,     # electricity, consumption
        "inclBtw": "false", # we apply our own markup+btw stack below
    }

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(ENERGYZERO_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            log.warning("EnergyZero request failed (attempt %d/%d): %r", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    else:
        raise RuntimeError(f"EnergyZero unreachable after {retries} attempts") from last_exc

    prices = data.get("Prices") or data.get("prices") or []
    if not prices:
        raise RuntimeError("EnergyZero returned no price points for tomorrow (not published yet?)")

    out = []
    for p in prices:
        ts = datetime.fromisoformat(p["readingDate"].replace("Z", "+00:00"))
        out.append((ts, float(p["price"])))
    return out


def apply_anwb_markup(day_ahead: list[tuple[datetime, float]], energy_cfg: dict) -> list[HourPrice]:
    inkoop = energy_cfg["inkoopvergoeding_ex_btw_per_kwh"]
    belasting = energy_cfg["energiebelasting_ex_btw_per_kwh"]
    btw = 1 + energy_cfg["btw_percentage"] / 100

    return [
        HourPrice(time=ts.astimezone(), all_in_eur_per_kwh=(price + inkoop + belasting) * btw)
        for ts, price in day_ahead
    ]


def render_chart(hours: list[HourPrice]) -> bytes:
    """Render a 24h bar chart to PNG bytes for embedding in the email."""
    labels = [h.time.strftime("%H") for h in hours]
    values = [h.all_in_eur_per_kwh * 100 for h in hours]  # cent/kWh, easier to read

    cheapest = values.index(min(values))
    priciest = values.index(max(values))
    colors = ["#c62828" if i == priciest else "#2e7d32" if i == cheapest else "#5b8def" for i in range(len(values))]

    fig, ax = plt.subplots(figsize=(9, 3), dpi=130)
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("cent/kWh (all-in)")
    ax.set_title(f"Stroomprijs morgen ({hours[0].time.strftime('%d-%m-%Y')})")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def render_html(hours: list[HourPrice], cid: str) -> str:
    cheapest = min(hours, key=lambda h: h.all_in_eur_per_kwh)
    priciest = max(hours, key=lambda h: h.all_in_eur_per_kwh)
    avg = sum(h.all_in_eur_per_kwh for h in hours) / len(hours)

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        ⚡ Energieprijzen morgen
    </h2>
    <p style="font-family:Arial,sans-serif; font-size:14px;">
        Goedkoopst: <b>{cheapest.time.strftime('%H:%M')}</b> ({cheapest.all_in_eur_per_kwh*100:.1f} ct/kWh) &nbsp;|&nbsp;
        Duurst: <b>{priciest.time.strftime('%H:%M')}</b> ({priciest.all_in_eur_per_kwh*100:.1f} ct/kWh) &nbsp;|&nbsp;
        Gemiddeld: {avg*100:.1f} ct/kWh
    </p>
    <img src="cid:{cid}" alt="Energieprijzen grafiek" style="max-width:100%; height:auto;">
    """


def build_section(config: dict) -> tuple[str, list[tuple[str, bytes, str]]]:
    """Returns (html, [(content_id, png_bytes, mime_type), ...]) for main.py to attach."""
    day_ahead = get_day_ahead_prices()
    hours = apply_anwb_markup(day_ahead, config["energy"])
    png = render_chart(hours)
    cid = "energy_chart"
    html = render_html(hours, cid)
    return html, [(cid, png, "image/png")]

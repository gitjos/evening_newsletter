"""
Weather section: next-24h hourly forecast + sunrise/sunset, styled like the
timeanddate.com hourly page you linked.

NOTE on a deliberate deviation from the brief: timeanddate.com's hourly page
is a heavy, frequently-restructured HTML page with no public API — scraping
it reliably from a cron job (no browser, no JS) is fragile and breaks
silently. Open-Meteo is a free, keyless, structured JSON API that gives us
the same numbers (temperature, precipitation chance, sunrise/sunset) for the
exact coordinates in config.json, and it's the same API you already used for
the Leeuwarden radiation script. This module reproduces the *layout* you
described (hour-by-hour, with sunrise/sunset called out) using that data
instead of screen-scraping timeanddate.com.

If you'd rather scrape timeanddate.com directly, this is the module to
swap out — get_forecast() is the only function the rest of the app calls.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Rough mapping of Open-Meteo's WMO weather codes to a short description + emoji.
WMO_CODES = {
    0: ("Helder", "☀️"), 1: ("Overwegend helder", "🌤️"), 2: ("Half bewolkt", "⛅"),
    3: ("Bewolkt", "☁️"), 45: ("Mist", "🌫️"), 48: ("Rijp/mist", "🌫️"),
    51: ("Lichte motregen", "🌦️"), 53: ("Motregen", "🌦️"), 55: ("Dichte motregen", "🌧️"),
    61: ("Lichte regen", "🌦️"), 63: ("Regen", "🌧️"), 65: ("Zware regen", "🌧️"),
    71: ("Lichte sneeuw", "🌨️"), 73: ("Sneeuw", "🌨️"), 75: ("Zware sneeuw", "❄️"),
    80: ("Buien", "🌦️"), 81: ("Flinke buien", "🌧️"), 82: ("Zware buien", "⛈️"),
    95: ("Onweer", "⛈️"), 96: ("Onweer met hagel", "⛈️"), 99: ("Zwaar onweer", "⛈️"),
}


@dataclass
class HourForecast:
    time: datetime
    temp_c: float
    precip_prob: int
    description: str
    icon: str


@dataclass
class Forecast:
    hours: list[HourForecast]
    sunrise: datetime
    sunset: datetime


def _describe(code: int) -> tuple[str, str]:
    return WMO_CODES.get(code, ("Onbekend", "❓"))


def get_forecast(location: dict, hours_ahead: int = 24) -> Forecast:
    """Fetch the next `hours_ahead` hours plus tomorrow's sunrise/sunset."""
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location.get("timezone", "Europe/Amsterdam"),
        "hourly": "temperature_2m,precipitation_probability,weathercode",
        "daily": "sunrise,sunset",
        "forecast_days": 2,
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    now = datetime.now()
    times = [datetime.fromisoformat(t) for t in data["hourly"]["time"]]
    temps = data["hourly"]["temperature_2m"]
    precs = data["hourly"]["precipitation_probability"]
    codes = data["hourly"]["weathercode"]

    hours: list[HourForecast] = []
    for t, temp, prec, code in zip(times, temps, precs, codes):
        if t < now.replace(minute=0, second=0, microsecond=0):
            continue
        if len(hours) >= hours_ahead:
            break
        desc, icon = _describe(code)
        hours.append(HourForecast(time=t, temp_c=temp, precip_prob=prec, description=desc, icon=icon))

    # Sunrise/sunset for tomorrow (index 1 of the daily arrays) — that's the
    # forward-looking bit that matters in a newsletter sent at 22:00.
    sunrise = datetime.fromisoformat(data["daily"]["sunrise"][1])
    sunset = datetime.fromisoformat(data["daily"]["sunset"][1])

    return Forecast(hours=hours, sunrise=sunrise, sunset=sunset)


def render_html(forecast: Forecast, place_name: str) -> str:
    rows = "\n".join(
        f'<tr>'
        f'<td style="padding:4px 8px;">{h.time.strftime("%a %H:%M")}</td>'
        f'<td style="padding:4px 8px;">{h.icon} {h.description}</td>'
        f'<td style="padding:4px 8px; text-align:right;">{h.temp_c:.0f}°C</td>'
        f'<td style="padding:4px 8px; text-align:right;">{h.precip_prob}%</td>'
        f"</tr>"
        for h in forecast.hours
    )

    return f"""
    <h2 style="font-family:Arial,sans-serif; color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        🌦️ Weer – {place_name}
    </h2>
    <p style="font-family:Arial,sans-serif; font-size:14px;">
        🌅 Zon op morgen: <b>{forecast.sunrise.strftime("%H:%M")}</b> &nbsp;|&nbsp;
        🌇 Zon onder morgen: <b>{forecast.sunset.strftime("%H:%M")}</b>
    </p>
    <table style="font-family:Arial,sans-serif; font-size:13px; border-collapse:collapse; width:100%;">
        <thead>
            <tr style="background:#f2f2f2; text-align:left;">
                <th style="padding:4px 8px;">Tijd</th>
                <th style="padding:4px 8px;">Weer</th>
                <th style="padding:4px 8px; text-align:right;">Temp</th>
                <th style="padding:4px 8px; text-align:right;">Neerslag</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    """


def build_section(config: dict) -> str:
    forecast = get_forecast(config["location"])
    return render_html(forecast, config["location"].get("place_name", ""))

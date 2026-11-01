"""
Weather section: a summary of tomorrow's weather.

Data comes from Open-Meteo (free, no API key) for the coordinates in
config.json. The section shows:
- one line with the overall weather for tomorrow
- min/max temperature, rain (mm and chance), wind (Beaufort + direction)
- a short morning / afternoon / evening breakdown
- sunrise and sunset for five days, tomorrow in the middle

build_section() is the only function the rest of the app calls.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo's WMO weather codes -> short Dutch description + emoji.
WMO_CODES = {
    0: ("Helder", "☀️"), 1: ("Overwegend helder", "🌤️"), 2: ("Half bewolkt", "⛅"),
    3: ("Bewolkt", "☁️"), 45: ("Mist", "🌫️"), 48: ("Rijp/mist", "🌫️"),
    51: ("Lichte motregen", "🌦️"), 53: ("Motregen", "🌦️"), 55: ("Dichte motregen", "🌧️"),
    56: ("IJzel", "🌧️"), 57: ("Zware ijzel", "🌧️"),
    61: ("Lichte regen", "🌦️"), 63: ("Regen", "🌧️"), 65: ("Zware regen", "🌧️"),
    66: ("IJzel", "🌧️"), 67: ("Zware ijzel", "🌧️"),
    71: ("Lichte sneeuw", "🌨️"), 73: ("Sneeuw", "🌨️"), 75: ("Zware sneeuw", "❄️"), 77: ("Korrelsneeuw", "🌨️"),
    80: ("Buien", "🌦️"), 81: ("Flinke buien", "🌧️"), 82: ("Zware buien", "⛈️"),
    85: ("Sneeuwbuien", "🌨️"), 86: ("Zware sneeuwbuien", "❄️"),
    95: ("Onweer", "⛈️"), 96: ("Onweer met hagel", "⛈️"), 99: ("Zwaar onweer", "⛈️"),
}

WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
WEEKDAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MONTHS_SHORT = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
WIND_DIRECTIONS = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]
# Upper limits (km/h) for Beaufort 0..11; above that is 12.
BEAUFORT_LIMITS = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]

# Parts of the day: (label, first hour, last hour inclusive)
DAY_PARTS = [("Ochtend", 6, 11), ("Middag", 12, 17), ("Avond", 18, 23)]


@dataclass
class DayPart:
    label: str
    temp_c: float
    precip_prob: int
    description: str
    icon: str


@dataclass
class DaySummary:
    day: date
    description: str
    icon: str
    temp_min: float
    temp_max: float
    precip_mm: float
    precip_prob: int
    wind_bft: int
    wind_dir: str
    gusts_kmh: float
    parts: list[DayPart]
    sun: list[tuple[date, datetime, datetime]]  # (day, sunrise, sunset), tomorrow in the middle


def _describe(code: int) -> tuple[str, str]:
    return WMO_CODES.get(code, ("Onbekend", "❓"))


def _beaufort(kmh: float) -> int:
    return next((bft for bft, limit in enumerate(BEAUFORT_LIMITS) if kmh < limit), 12)


def _wind_direction(degrees: float) -> str:
    return WIND_DIRECTIONS[round(degrees / 45) % 8]


def get_tomorrow(location: dict) -> DaySummary:
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location.get("timezone", "Europe/Amsterdam"),
        "hourly": "temperature_2m,precipitation_probability,weathercode",
        "daily": ",".join([
            "weathercode", "temperature_2m_max", "temperature_2m_min",
            "precipitation_sum", "precipitation_probability_max",
            "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant",
            "sunrise", "sunset",
        ]),
        # yesterday .. tomorrow+2, so tomorrow is in the middle of the sun table
        "past_days": 1,
        "forecast_days": 4,
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    daily = data["daily"]
    i = 2  # index 0 is yesterday, 1 today, 2 tomorrow
    tomorrow = date.fromisoformat(daily["time"][i])
    description, icon = _describe(daily["weathercode"][i])

    hourly = data["hourly"]
    hours = [
        (datetime.fromisoformat(t), temp, prob, code)
        for t, temp, prob, code in zip(
            hourly["time"], hourly["temperature_2m"], hourly["precipitation_probability"], hourly["weathercode"]
        )
        if datetime.fromisoformat(t).date() == tomorrow
    ]

    parts = []
    for label, first, last in DAY_PARTS:
        part_hours = [h for h in hours if first <= h[0].hour <= last]
        if not part_hours:
            continue
        # Most common weather code in this part of the day; ties go to the worse (higher) code.
        counts = Counter(h[3] for h in part_hours)
        code = max(counts, key=lambda c: (counts[c], c))
        part_desc, part_icon = _describe(code)
        parts.append(DayPart(
            label=label,
            temp_c=sum(h[1] for h in part_hours) / len(part_hours),
            precip_prob=max(h[2] or 0 for h in part_hours),
            description=part_desc,
            icon=part_icon,
        ))

    return DaySummary(
        day=tomorrow,
        description=description,
        icon=icon,
        temp_min=daily["temperature_2m_min"][i],
        temp_max=daily["temperature_2m_max"][i],
        precip_mm=daily["precipitation_sum"][i] or 0.0,
        precip_prob=daily["precipitation_probability_max"][i] or 0,
        wind_bft=_beaufort(daily["wind_speed_10m_max"][i]),
        wind_dir=_wind_direction(daily["wind_direction_10m_dominant"][i]),
        gusts_kmh=daily["wind_gusts_10m_max"][i],
        parts=parts,
        sun=[
            (date.fromisoformat(d), datetime.fromisoformat(rise), datetime.fromisoformat(set_))
            for d, rise, set_ in zip(daily["time"], daily["sunrise"], daily["sunset"])
        ],
    )


def _rain_text(s: DaySummary) -> str:
    if s.precip_prob < 20 and s.precip_mm < 0.2:
        return "droog"
    mm = f"{s.precip_mm:.1f}".replace(".", ",")
    return f"{s.precip_prob}% kans, {mm} mm"


FONT = "font-family:Arial,sans-serif;"
CARD = "background:#f5f7fa; border-radius:8px;"
MUTED = "color:#667085;"
HIGHLIGHT = "background:#fff1c9;"


def render_html(s: DaySummary, place_name: str) -> str:
    weekday = WEEKDAYS[s.day.weekday()]
    gusts = f" &nbsp;<span style=\"{MUTED}\">(stoten {s.gusts_kmh:.0f} km/u)</span>" if s.gusts_kmh >= 60 else ""

    # Two columns only (icon + text), with rain/wind on their own row, so it still fits a phone screen.
    summary = f"""
    <table role="presentation" width="100%" style="{FONT} {CARD} border-collapse:separate; margin:8px 0;">
        <tr>
            <td style="padding:14px 8px 6px 14px; width:52px; font-size:40px; line-height:1; vertical-align:middle;">{s.icon}</td>
            <td style="padding:14px 14px 6px 6px; vertical-align:middle;">
                <div style="font-size:14px; {MUTED}">{weekday.capitalize()} {s.day.day} {MONTHS_SHORT[s.day.month - 1]}</div>
                <div style="font-size:20px; font-weight:bold; color:#222;">{s.description}</div>
                <div style="font-size:18px; color:#222;">{s.temp_min:.0f}° / <b>{s.temp_max:.0f}°C</b></div>
            </td>
        </tr>
        <tr>
            <td colspan="2" style="padding:6px 14px 14px 14px; font-size:16px; color:#222; line-height:1.6;">
                ☔ {_rain_text(s)} &nbsp;&nbsp; 💨 {s.wind_dir} {s.wind_bft} Bft{gusts}
            </td>
        </tr>
    </table>
    """

    n = max(len(s.parts), 1)
    width = f"{100 // n}%"

    def part_cell(idx: int, p: DayPart) -> str:
        # Gaps between cards via cell padding (email clients handle margins/border-spacing inconsistently).
        pad_left = "0" if idx == 0 else "4px"
        pad_right = "0" if idx == n - 1 else "4px"
        return (
            f'<td width="{width}" style="padding:0 {pad_right} 0 {pad_left};">'
            f'<div style="{CARD} padding:12px 4px; text-align:center;">'
            f'<div style="font-size:14px; {MUTED}">{p.label}</div>'
            f'<div style="font-size:30px; line-height:1.3;">{p.icon}</div>'
            f'<div style="font-size:20px; font-weight:bold; color:#222;">{p.temp_c:.0f}°C</div>'
            f'<div style="font-size:15px; {MUTED}">💧 {p.precip_prob}%</div>'
            f"</div></td>"
        )

    parts = "".join(part_cell(idx, p) for idx, p in enumerate(s.parts))
    day_parts = f"""
    <table role="presentation" width="100%" style="{FONT} border-collapse:collapse; margin:8px 0;">
        <tr>{parts}</tr>
    </table>
    """

    return f"""
    <h2 style="{FONT} color:#222; border-bottom:2px solid #eee; padding-bottom:4px;">
        🌦️ Weer morgen – {place_name}
    </h2>
    {summary}
    {day_parts}
    {_sun_table(s)}
    """


def _sun_table(s: DaySummary) -> str:
    def cell(day: date, text: str, header: bool = False) -> str:
        tag = "th" if header else "td"
        style = "padding:8px 2px; text-align:center;"
        if day == s.day:
            style += f" {HIGHLIGHT} font-weight:bold; color:#222;"
        elif header:
            style += f" {MUTED} font-weight:normal;"
        return f'<{tag} style="{style}">{text}</{tag}>'

    # Date over two lines ("ma" / "2 nov") so six columns fit on a phone.
    head = "".join(
        cell(d, f"{WEEKDAYS_SHORT[d.weekday()]}<br>{d.day} {MONTHS_SHORT[d.month - 1]}", header=True)
        for d, _, _ in s.sun
    )
    rises = "".join(cell(d, rise.strftime("%H:%M")) for d, rise, _ in s.sun)
    sets = "".join(cell(d, set_.strftime("%H:%M")) for d, _, set_ in s.sun)
    label = f'style="padding:8px 4px 8px 10px; text-align:left; white-space:nowrap; {MUTED}"'
    row = "border-top:1px solid #e4e7ec;"
    return f"""
    <table role="presentation" width="100%" style="{FONT} {CARD} font-size:15px; border-collapse:collapse; margin:8px 0;">
        <tr style="font-size:13px;"><th></th>{head}</tr>
        <tr style="{row}"><td {label}>🌅 op</td>{rises}</tr>
        <tr style="{row}"><td {label}>🌇 onder</td>{sets}</tr>
    </table>
    """


def build_section(config: dict) -> str:
    summary = get_tomorrow(config["location"])
    return render_html(summary, config["location"].get("place_name", ""))

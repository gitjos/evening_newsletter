"""
Concatenates the per-topic HTML fragments (each topic lives in its own file
under sources/, as requested) into one email-safe HTML document.
"""
from __future__ import annotations

from datetime import date

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    @media only screen and (max-width: 480px) {{
      .page {{ padding: 12px 10px !important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background:#fafafa;">
  <div class="page" style="max-width:640px; margin:0 auto; padding:20px; background:#ffffff;">
    <h1 style="font-family:Arial,sans-serif; font-size:20px; color:#111;">
        🌙 Avondbrief — {today}
    </h1>
    {sections}
    <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
    <p style="font-family:Arial,sans-serif; font-size:11px; color:#aaa;">
        Automatisch gegenereerd, {timestamp}.
    </p>
  </div>
</body>
</html>
"""

SECTION_ERROR_TEMPLATE = """\
<h2 style="font-family:Arial,sans-serif; color:#a00; border-bottom:2px solid #eee; padding-bottom:4px;">
    ⚠️ {name}
</h2>
<p style="font-family:Arial,sans-serif; font-size:13px; color:#a00;">
    Kon deze sectie niet ophalen ({error}).
</p>
"""


def error_section(name: str, error: Exception) -> str:
    return SECTION_ERROR_TEMPLATE.format(name=name, error=str(error)[:200])


# Spelled out here rather than via locale, which isn't reliably installed on the server.
DUTCH_WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
DUTCH_MONTHS = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def dutch_date(d: date) -> str:
    """e.g. "zondag 1 november 2026"."""
    return f"{DUTCH_WEEKDAYS[d.weekday()]} {d.day} {DUTCH_MONTHS[d.month - 1]} {d.year}"


def render_page(section_htmls: list[str]) -> str:
    from datetime import datetime

    return PAGE_TEMPLATE.format(
        today=dutch_date(date.today()),
        sections="\n".join(section_htmls),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

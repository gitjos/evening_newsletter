"""
Concatenates the per-topic HTML fragments (each topic lives in its own file
under sources/, as requested) into one email-safe HTML document.
"""
from __future__ import annotations

from datetime import date

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background:#fafafa;">
  <div style="max-width:640px; margin:0 auto; padding:20px; background:#ffffff;">
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


def render_page(section_htmls: list[str]) -> str:
    from datetime import datetime

    return PAGE_TEMPLATE.format(
        today=date.today().strftime("%A %d %B %Y"),
        sections="\n".join(section_htmls),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

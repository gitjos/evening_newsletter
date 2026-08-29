#!/usr/bin/env python3
"""
Evening newsletter — builds every section, assembles one HTML email, and
sends it. Meant to run once a day around 22:00 via cron.

Each topic lives in its own file under sources/ and is built independently;
if one source fails (a site changed, is down, whatever), that section shows
an inline error instead of taking down the whole run — you still get an
email with everything else that worked.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import emailer
import render
from sources import energy, euribor, nos, omrin_section, slieker, weather

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("evening_newsletter")


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def build_sections(config: dict) -> tuple[list[str], list[tuple[str, bytes, str]]]:
    """Runs every source module, collecting HTML fragments and inline images."""
    section_htmls: list[str] = []
    inline_images: list[tuple[str, bytes, str]] = []

    # Order matches the brief: Omrin, energy, weather, Slieker, NOS, (Euribor if due).
    simple_sources = [
        ("Omrin", omrin_section),
        ("Weer", weather),
        ("Slieker Film", slieker),
        ("NOS", nos),
    ]

    # Energy is built separately since it also returns an image to embed.
    try:
        html, images = energy.build_section(config)
        section_htmls.append(html)
        inline_images.extend(images)
    except Exception as exc:
        log.exception("Energy section failed")
        section_htmls.append(render.error_section("Energieprijzen", exc))

    for name, module in simple_sources:
        try:
            result = module.build_section(config)
            if result:
                section_htmls.append(result)
            else:
                log.info("%s section returned no content, skipping", name)
        except Exception as exc:
            log.exception("%s section failed", name)
            section_htmls.append(render.error_section(name, exc))

    # Euribor only shows up on its once-a-month day; build_section returns
    # None the rest of the time, so it's simply omitted otherwise.
    try:
        euribor_html = euribor.build_section(config)
        if euribor_html:
            section_htmls.append(euribor_html)
    except Exception as exc:
        log.exception("Euribor section failed")
        section_htmls.append(render.error_section("Euribor", exc))

    return section_htmls, inline_images


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and send the evening newsletter")
    parser.add_argument("--dry-run", action="store_true", help="Build the HTML but don't send, write it to preview.html instead")
    args = parser.parse_args()

    config = load_config()
    section_htmls, inline_images = build_sections(config)
    html = render.render_page(section_htmls)

    if args.dry_run:
        preview_path = BASE_DIR / "preview.html"
        preview_path.write_text(html, encoding="utf-8")
        log.info("Dry run — wrote %s (inline images not embedded in preview)", preview_path)
        return

    subject = f"{config['email'].get('subject_prefix', 'Avondbrief')} — {__import__('datetime').date.today().isoformat()}"
    emailer.send_newsletter(config["email"], subject, html, inline_images)


if __name__ == "__main__":
    main()

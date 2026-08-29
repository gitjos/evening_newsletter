# Avondbrief — evening newsletter

Builds an HTML email every evening with: Omrin waste collection for
tomorrow, tomorrow's electricity prices as a chart, weather, today's Slieker
Film programme, top 5 NOS headlines, and (once a month) a Euribor
mortgage-rate note. Sends it over Gmail SMTP.

## Layout

```
config.json          all settings + secrets (postcode, Gmail app password, tariffs)
main.py              orchestrator — run this from cron
render.py            combines the per-topic HTML into one page
emailer.py           SMTP sending (Gmail app password, same style as google_mail_archiver)
sources/
  omrin.py           waste collection — see file header, this one needs verification
  energy.py          day-ahead price (EnergyZero) + ANWB markup/tax -> chart
  weather.py         Open-Meteo hourly forecast + tomorrow's sunrise/sunset
  slieker.py         today's programme, scraped via MovieMeter's cinema agenda
  nos.py             NOS RSS top headlines
  euribor.py         ported from your Node-RED flow — date logic + FD.nl scrape
state/
  euribor_state.json created automatically, tracks "already sent this month"
```

## Setup

```bash
cd evening_newsletter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Edit `config.json`:
- `email.sender` / `email.password` — Gmail address + an **app password**
  (https://myaccount.google.com/apppasswords), not your normal password.
- `waste.postcode` / `waste.huisnummer` — already defaulted to 8916ED / 111.
- `energy.*` — the ANWB markup/tax constants. Worth double-checking against
  https://www.anwb.nl/energie/actuele-tarieven now and then; these are
  policy numbers, not something an API gives you.

Test without sending anything:

```bash
python3 main.py --dry-run
# writes preview.html — open it in a browser (inline chart won't show,
# since that only gets attached on a real send)
```

Send for real:

```bash
python3 main.py
```

## Cron

Same pattern as the mail archiver — flock-guarded, logged:

```cron
0 22 * * * /usr/bin/flock -n /tmp/avondbrief.lock /path/to/venv/bin/python3 /path/to/evening_newsletter/main.py >> /var/log/avondbrief.log 2>&1
```

## Honesty about the fragile bits

Every scraped source is wrapped so one failure doesn't kill the whole run —
that section just prints an inline error and the rest of the email still
goes out. But two sources are genuinely more likely to need your attention
after a site redesign:

- **`sources/omrin.py`** — Omrin's calendar is a JS widget with no public
  API I could find or verify from here. The module submits
  postcode/huisnummer as query params to the public calendar page and
  parses the resulting table, mirroring what other open-source Omrin
  integrations do — but I couldn't run it against the live site to confirm
  the exact request/response shape. The file header has step-by-step
  instructions for capturing the real request from your browser's devtools
  if it comes back empty.
- **`sources/slieker.py`** — scrapes MovieMeter's cinema-agenda page (day
  anchors + adjacent film/ticket links) rather than sliekerfilm.nl directly,
  since Slieker's own site is a booking widget. Same caveat: verified the
  page's general shape by fetching it once, not by running the parser
  against live output.

Both fail soft (empty result / clear inline error), not silently wrong.

`sources/weather.py` deliberately uses the Open-Meteo API instead of
scraping the timeanddate.com page you linked — same numbers, same
hour-by-hour + sunrise/sunset layout, but a stable JSON API instead of HTML
scraping. If you'd rather match timeanddate.com's page exactly, that's the
one file to rewrite; `get_forecast()` is the only function main.py depends
on.

`sources/energy.py` uses EnergyZero's public day-ahead price API (the same
underlying EPEX price ANWB itself resells) plus the markup/tax constants
from config.json, since ANWB doesn't publish a public prices API — those
numbers only exist behind login in "Mijn ANWB Energie".

`sources/nos.py` and `sources/euribor.py`'s date/holiday logic are the
solid ones — plain RSS and pure date math respectively, no scraping
involved (Euribor's rate lookup on FD.nl is a regex scrape same as before,
kept close to 1:1 with your Node-RED version).

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sources.slieker import _fetch_html, _extract_today_block, get_todays_programme
from datetime import datetime

url = 'https://sliekerfilm.nl/programma/'
html = _fetch_html(url)
print('HTML length:', len(html))
open(str(Path(__file__).resolve().parent / 'slieker_page.html'), 'w', encoding='utf-8').write(html)
print('Wrote tools/slieker_page.html')
block = _extract_today_block(html, datetime.now().day)
print('Block is None?', block is None)
if block:
    print('\n--- Block excerpt (first 1200 chars) ---')
    print(block[:1200])
    print('\n--- End excerpt ---')
else:
    # Try to find any day anchors to understand the page structure
    import re
    anchors = [m.start() for m in re.finditer(r'id="day_\d{2}"', html)]
    print('Found day_ anchors count:', len(anchors))
    if anchors:
        i = anchors[0]
        print('\n--- First anchor context ---')
        print(html[max(0, i-200):i+200])
        print('\n--- End context ---')
    # Search for ticket links or film paths regardless of day_ anchors
    tickets = list(re.finditer(r'https://sliekerfilm\.nl/boek-je-ticket/\?event=\d+', html))
    films = list(re.finditer(r'/film/\d+', html))
    print('Found ticket links:', len(tickets))
    print('Found /film/ links:', len(films))
    if tickets:
        t = tickets[0].start()
        print('\n--- Ticket link context ---')
        print(html[max(0, t-200):t+200])
        print('\n--- End ticket context ---')
    if films:
        f = films[0].start()
        print('\n--- Film link context ---')
        print(html[max(0, f-200):f+200])
        print('\n--- End film context ---')
        # Search for other keywords that might indicate where the programme is stored
        for kw in ('programma', 'slieker', 'boek', 'ticket', 'event', 'show'):
            idx = html.lower().find(kw)
            print(f"Found '{kw}' at", idx)
            if idx != -1:
                print(html[max(0, idx-120):idx+120])

print('\n--- Parsed showings ---')
showings = get_todays_programme(url)
print('Count:', len(showings))
for s in showings:
    print(s.time, s.title, s.link)

# Try JSON / feeds that may contain the programme server-side
for feed in ('https://sliekerfilm.nl/wp/upcoming_events', 'https://sliekerfilm.nl/wp/upcoming_productions'):
    try:
        print('\nFetching', feed)
        data = _fetch_html(feed)
        print('Length', len(data))
        print('Excerpt:', data[:1000])
    except Exception as e:
        print('Failed to fetch', feed, e)

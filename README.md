# Breadfirst

A simple [Headfirst](https://www.headfirstbristol.co.uk/) copy, for Berlin.

## Aim

Create a website that mimics Headfirst, for finding music in Berlin.

Current restrictions for simplicity:

- Only live music listings (no clubnights, art etc.)
- Only get listings for the next month ahead
- No 'Editors Pick's
- No searching
- The 'Calendar' view is the only view
- No ticketing or links to tickets
- Restricted to the following venues for now:
  1. https://www.lido-berlin.de/
  2. https://www.prachtwerkberlin.com/
  3. https://www.berghain.berlin/de/program/kantine-am-berghain/
  4. https://kottimonarch.de/programm.php
  5. https://privatclub-berlin.de/
  6. https://www.gretchen-club.de/
  7. https://donau115.de/
  8. https://www.sowiesoberlin.com/
  9. https://neue-zukunft.org/konzerte.html
  10. https://larkberlin.com/events/
  11. https://hole-berlin.de/
  12. https://www.inselberlin.de/

I assume there's no way to pull from these websites except manually, so I will need a script that I can run weekly (daily ?) that adds new listings in the next month and puts a cancelled strike-through for cancelled listings.

## How it works

- `breadfirst/venues/*.py`: one scraper per venue. Each one fetches the venue's listing and keeps only the live concerts. Where the page is drawn by JavaScript, the scraper reads the feed behind it instead:
  - Prachtwerk: the JSON feed behind its Facebook-events widget.
  - Neue Zukunft: the JSON behind its Elfsight calendar widget.
  - Donau115: the Firebase database its page loads.
  - Lark: the WordPress REST API.
  - Insel: the Gatsby page data.

  Lido also fetches the page of its next gig, which is shown only in the header teaser.
- `breadfirst/store.py`: merges each run into `data/events.json`, which is committed to the repo. It works like this:
  - New gigs within the next 31 days are added, and existing ones are updated (e.g. when a gig sells out).
  - Gigs the venue marks as abgesagt or cancelled get a strike-through.
  - A future gig that disappears from its venue's site is also struck through, marked "No longer listed".
  - If a venue's scrape fails or finds nothing, its previous listings are kept as they were.
  - Past gigs are removed.
- `breadfirst/build.py`: renders `site/index.html`, the calendar view.
- `.github/workflows/update.yml`: runs the scrape daily at 04:17 UTC (or on demand), commits any changes to the data and deploys `site/` to GitHub Pages.

## Running locally

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

.venv/bin/pytest                                   # parser + merge tests (uses tests/fixtures)
.venv/bin/python -m breadfirst scrape --dry-run    # scrape all venues, print what would change
.venv/bin/python -m breadfirst all                 # scrape, update data/events.json, build site/
open site/index.html
```

`--venue lido` (repeatable) limits a run to particular venues.

When a venue changes its site, its parser test will start failing. To fix it, save the new page over `tests/fixtures/<venue>.html` (or `.json`) and update the parser. Some fixtures are trimmed:

- Prachtwerk: keep only the `events` key in the saved feed, because the rest contains access tokens.
- Donau115: keep only `bandName`, `date`, `live` and the time-bearing lines of `description`, with emails redacted. The feed also holds artists' contact details, which must never be committed.
- Neue Zukunft and Insel: drop image fields, and keep only recent events, to keep the files small.

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, hhmm, split_status_suffix, status_note

VENUE = "Gretchen"
SOURCE_URL = "https://www.gretchen-club.de/"


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events = []
    for gig in soup.select("div.gig"):
        when = gig.select_one(".gig_top span.date")
        when_text = when.get_text(" ", strip=True)
        day = datetime.strptime(when.select_one("strong").get_text(strip=True), "%d.%m.%Y").date()
        doors = hhmm(m.group(1)) if (m := re.search(r"Doors:\s*([\d.:]+)", when_text)) else None
        show = hhmm(m.group(1)) if (m := re.search(r"Show:\s*([\d.:]+)", when_text)) else None

        # No event type, so: concerts have a show time; otherwise a "*live*" act
        # before 22:00 counts. Doors-only late nights are club nights.
        has_live_act = "*live*" in gig.select_one(".gig_main").get_text().lower()
        if not show and not (has_live_act and doors and doors < "22:00"):
            continue

        link = gig.select_one("span.title h2 a")
        title, suffix = split_status_suffix(clean(link.get_text(" ")))
        status = detect_status(suffix) or Status.SCHEDULED
        overlay = gig.select_one("span.rotated")
        if overlay:
            status = detect_status(overlay.get_text()) or status

        href = link["href"]
        events.append(
            Event(
                id=f"gretchen:{href.rsplit('=', 1)[-1]}",
                venue=VENUE,
                title=title,
                date=day,
                doors=doors,
                start=show,
                url=urljoin(SOURCE_URL, href),
                status=status,
                status_note=status_note(suffix),
            )
        )
    return events

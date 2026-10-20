from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, split_status_suffix, status_note

VENUE = "Kantine am Berghain"
SOURCE_URL = "https://www.berghain.berlin/de/program/kantine-am-berghain/"


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events = []
    for card in soup.select('main a[href^="/de/event/"]'):
        venue = card.select_one("h3")
        if venue and "kantine" not in venue.get_text().lower():
            continue

        artists, any_live = [], False
        for a in card.select("h4 span.font-bold"):
            name = a.select_one("span.xs\\:whitespace-no-wrap")
            if name:
                artists.append(clean(name.get_text()))
            tag = a.select_one("span.uppercase")
            any_live |= bool(tag and tag.get_text(strip=True).lower() == "live")
        # A line-up with no "Live" act is a DJ night. Events with no line-up at all
        # (e.g. ones moved elsewhere) are kept.
        if artists and not any_live:
            continue

        meta = card.select_one("p").get_text(" ", strip=True)
        day = datetime.strptime(card.select_one("p span.font-bold").get_text(strip=True), "%d.%m.%Y").date()
        doors = re.search(r"tür (\d\d:\d\d)", meta)
        start = re.search(r"beginn (\d\d:\d\d)", meta)

        title, suffix = split_status_suffix(clean(card.select_one("h2").get_text()))
        status = detect_status(suffix) or Status.SCHEDULED
        others = [a for a in artists if a.lower() != title.lower()]

        href = card["href"]
        events.append(
            Event(
                id=f"kantine:{href.strip('/').rsplit('/', 1)[-1]}",
                venue=VENUE,
                title=title,
                subtitle=", ".join(others) or None,
                date=day,
                doors=doors and doors.group(1),
                start=start and start.group(1),
                url=urljoin(SOURCE_URL, href),
                status=status,
                status_note=status_note(suffix),
            )
        )
    return events

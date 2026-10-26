from __future__ import annotations

import json
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, hhmm, slugify, today_berlin

VENUE = "Sowieso"
SOURCE_URL = "https://www.sowiesoberlin.com/"

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
# Each gig starts a line with "Oct 23&nbsp;" (no year); the rest is hand-typed rich text.
_DATE = re.compile(
    r"(?:^|<br>)\s*(Jan|Feb|Mar|Apr|May|June?|July?|Aug|Sept?|Oct|Nov|Dec)\s+(\d{1,2})\b(?:&nbsp;|\s)",
    re.IGNORECASE | re.MULTILINE,
)
_HOUSE_TIMES = re.compile(r"Doors\s+(\d{1,2}[.:]\d{2})\s*\|\s*Concerts\s+(\d{1,2}[.:]\d{2})", re.IGNORECASE)
_OWN_TIMES = re.compile(r"\[\s*Doors\s+(\d{1,2}[.:]\d{2})\s*,\s*Start\s+(\d{1,2}[.:]\d{2})\s*\]", re.IGNORECASE)
# Now and then a reading or screening night; keep it if there's a line-up with instruments.
_NOT_MUSIC = re.compile(r"poetry|lesung|reading|screening|\bfilm", re.IGNORECASE)
_LINE_UP = re.compile(r"\([a-z][^)]*\)|\bsolo\b")


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str, today: date | None = None) -> list[Event]:
    today = today or today_berlin()
    script = BeautifulSoup(raw, "lxml").select_one('script[type="text/json"][data-set="ProjectDetail"]')
    content = json.loads(script.string)["content"]

    house = _HOUSE_TIMES.search(BeautifulSoup(content, "lxml").get_text(" "))
    doors, start = (hhmm(house.group(1)), hhmm(house.group(2))) if house else (None, None)

    events = []
    marks = list(_DATE.finditer(content))
    for m, nxt in zip(marks, marks[1:] + [None]):
        chunk = content[m.end() : nxt.start() if nxt else len(content)]
        # Double bills are split with " | "; each act's name is in bold.
        bills = [BeautifulSoup(part, "lxml") for part in re.split(r"\s\|\s", chunk)]
        names = [[n for b in bill.select("b") if (n := clean(b.get_text(" ")))] for bill in bills]
        if not any(names):
            continue
        title = " | ".join(" & ".join(n) for n in names if n)
        text = " | ".join(clean(bill.get_text(" ")) or "" for bill in bills)
        text = re.sub(r"\s+([,.)])", r"\1", text)
        if _NOT_MUSIC.search(text) and not _LINE_UP.search(text):
            continue

        own = _OWN_TIMES.search(text)
        text = clean(_OWN_TIMES.sub("", text)) or ""
        day = _date(m.group(1), int(m.group(2)), today)
        events.append(
            Event(
                id=f"sowieso:{day}-{slugify(title)}",
                venue=VENUE,
                title=title,
                subtitle=_line_up(text, names[0]),
                date=day,
                doors=hhmm(own.group(1)) if own else doors,
                start=hhmm(own.group(2)) if own else start,
                url=SOURCE_URL,
                status=detect_status(text) or Status.SCHEDULED,
            )
        )
    return events


def _date(month: str, day: int, today: date) -> date:
    """No year is given: the listing runs from a few days ago to a month or two ahead."""
    d = date(today.year, _MONTHS.index(month[:3].lower()) + 1, day)
    if d < today - timedelta(days=60):
        return d.replace(year=d.year + 1)
    if d > today + timedelta(days=300):
        return d.replace(year=d.year - 1)
    return d


def _line_up(text: str, lead: list[str]) -> str | None:
    """Drop the leading act names, which are already the title."""
    stripped = True
    while stripped:
        stripped = False
        text = text.lstrip(" ,&")
        for name in lead:
            if text.startswith(name):
                text, stripped = text[len(name) :], True
    return clean(text.lstrip(" ,&")) or None

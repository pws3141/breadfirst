from __future__ import annotations

import json
import re
from datetime import date

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, hhmm, split_status_prefix, status_note

VENUE = "Donau115"
SOURCE_URL = "https://donau115.de/"
# The page draws its listing from a Firebase database; look its URL up rather than pin it.
_FEED = re.compile(r"https://[\w.-]+\.firebasedatabase\.app/[\w/]*events\.json")

# The bar opens at 19:30 ("19:30–??:??" in the page header) unless an event says otherwise.
DEFAULT_DOORS = "19:30"
_DOORS = re.compile(r"\bdoors\s*:?\s*(\d{1,2}[.:]\d{2})", re.IGNORECASE)
# "(MUSIC STARTS 20:00)", "Show: 20:30", "opening set: 20", "Start time: 20:15".
_START = re.compile(
    r"\b(?:music starts|show|start(?: time)?|opening set)\s*:?\s*(\d{1,2}(?:[.:]\d{2})?)\b(?!\s*(?:€|eur))",
    re.IGNORECASE,
)


def fetch() -> str:
    m = _FEED.search(web.get(SOURCE_URL))
    if not m:
        raise ValueError("Donau115: events feed URL not found on the homepage")
    return web.get(m.group(0))


def parse(raw: str) -> list[Event]:
    events = []
    # Only read the fields we show: entries also carry artists' contact details.
    for key, ev in json.loads(raw).items():
        if ev.get("live") is not True:
            continue  # unpublished draft
        name, prefix = split_status_prefix(clean(ev["bandName"]) or "")
        text = f"{name}\n{ev.get('description') or ''}"
        doors = hhmm(m.group(1)) if (m := _DOORS.search(text)) else DEFAULT_DOORS
        start = _evening(hhmm(m.group(1))) if (m := _START.search(text)) else None
        events.append(
            Event(
                id=f"donau115:{key}",
                venue=VENUE,
                title=re.sub(r"\s*\([^)]*\d{1,2}[.:]\d{2}[^)]*\)", "", name),
                date=date.fromisoformat(ev["date"]),
                doors=doors,
                start=start,
                url=SOURCE_URL,
                status=detect_status(prefix) or Status.SCHEDULED,
                status_note=status_note(prefix),
            )
        )
    return events


def _evening(t: str | None) -> str | None:
    """'08:15' -> '20:15': nothing here starts in the morning."""
    if t and t < "12:00":
        return f"{int(t[:2]) + 12:02d}{t[2:]}"
    return t

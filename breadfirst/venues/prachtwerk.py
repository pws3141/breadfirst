from __future__ import annotations

import json
import re
import time
from datetime import datetime

from .. import web
from ..models import Event, Status
from ..text import BERLIN, clean, detect_status, hhmm, split_status_suffix, status_note

VENUE = "Prachtwerk"
# The site's listing is a SociableKit widget mirroring Prachtwerk's Facebook events;
# this is the JSON feed behind it. The feed's "settings" key holds tokens, so only
# "events" is ever read.
SOURCE_URL = "https://data.accentapi.com/feed/35219.json"

_SEPARATORS = re.compile(r"\s+(?:\||•|/{2,}|-|–)\s+")
_FILLER = re.compile(
    r"^(?:berlin|prachtwerk(?: berlin)?|berlin,? prachtwerk|\d{1,2}\.\d{1,2}\.\d{2,4}|berlin \d{1,2}\.\d{1,2}\.\d{2,4})$",
    re.IGNORECASE,
)
# "19:00", "19.00", "7:00 PM", "19h", "19 Uhr" - but not a bare number like a date.
_TIME = r"(\d{1,2}[.:]\d{2}(?:\s*[ap]m)?|\d{1,2}\s*(?:h|uhr|[ap]m)\b)"
_TRAILING = re.compile(
    r"\s+(?:live (?:in|at) (?:berlin|prachtwerk)!?|@ prachtwerk|i berlin)$", re.IGNORECASE
)


def fetch() -> str:
    return web.get(SOURCE_URL, params={"nocache": int(time.time())})


def _split_name(name: str) -> tuple[str, str | None]:
    """'Patrick Wolf | The Beast | Prachtwerk - Berlin' -> ('Patrick Wolf', 'The Beast')."""
    parts = [_TRAILING.sub("", p).strip() for p in _SEPARATORS.split(name)]
    parts = [p for p in parts if p and not _FILLER.match(p)]
    if not parts:
        return name, None
    return parts[0], " · ".join(parts[1:]) or None


def parse(raw: str) -> list[Event]:
    events = []
    for item in json.loads(raw)["events"]:
        start_local = datetime.fromisoformat(item["event_start_utc"].replace("Z", "+00:00")).astimezone(BERLIN)
        desc = clean(re.sub(r"<[^>]+>", " ", item.get("description") or "")) or ""
        doors = hhmm(m.group(1)) if (m := re.search(rf"(?:Einlass|Doors)\s*:?\s*{_TIME}", desc, re.I)) else None
        start = hhmm(m.group(1)) if (m := re.search(rf"(?:Beginn|Start|Show)\s*:?\s*{_TIME}", desc, re.I)) else None
        if not doors and not start:
            start = start_local.strftime("%H:%M")

        name, suffix = split_status_suffix(clean(item["name"]))
        title, subtitle = _split_name(name)
        # Facebook marks cancelled events; promoters sometimes write it into the name instead.
        status = detect_status(item.get("event_status"), suffix) or Status.SCHEDULED

        events.append(
            Event(
                id=f"prachtwerk:{item['event_id']}",
                venue=VENUE,
                title=title,
                subtitle=subtitle,
                date=start_local.date(),
                doors=doors,
                start=start,
                url=item.get("html_link") or "https://www.prachtwerkberlin.com/live-music-events",
                status=status,
                status_note=status_note(suffix),
            )
        )
    return events

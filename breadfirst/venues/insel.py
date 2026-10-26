from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import (
    BERLIN,
    clean,
    detect_status,
    hhmm,
    slugify,
    split_status_prefix,
    split_status_suffix,
    status_note,
)

VENUE = "Insel"
SOURCE_URL = "https://www.inselberlin.de/"
# A Gatsby site: the programme is a static-query JSON file named by a hash of the query.
# The homepage's page-data lists those hashes, so find the one holding the events.
PAGE_DATA = urljoin(SOURCE_URL, "page-data/index/page-data.json")

# Kids' shows, slams, readings, theatre and private bookings share the programme.
_NOT_A_GIG = re.compile(
    r"Slam|Lesung|Comedy|Theater|Hörspiel|Geschlossene|Firmen-Event|Matin[eé]e|\bDJs?\b|Kinder",
    re.IGNORECASE,
)
_DOORS = re.compile(r"\b(?:Einlass|Doors)\s*:?\s*(\d{1,2}(?:[.:]\d{2})?)", re.IGNORECASE)
_START = re.compile(r"\bBeginn\s*:?\s*(\d{1,2}(?:[.:]\d{2})?)", re.IGNORECASE)
_SUPPORT = re.compile(r"^\s*Support:\s*(.+?)\s*$", re.MULTILINE)
_SOCIAL = re.compile(r"instagram|facebook|youtube|youtu\.be|spotify|bandcamp|tiktok", re.IGNORECASE)


def fetch() -> str:
    for h in json.loads(web.get(PAGE_DATA))["staticQueryHashes"]:
        raw = web.get(urljoin(SOURCE_URL, f"page-data/sq/d/{h}.json"))
        if '"allDatoCmsEvent"' in raw:
            return raw
    raise ValueError("Insel: no static query with events found")


def parse(raw: str) -> list[Event]:
    events = []
    for edge in json.loads(raw)["data"]["allDatoCmsEvent"]["edges"]:
        ev = edge["node"]
        name = clean(ev["name"]) or ""
        kind = (ev.get("eventType") or {}).get("eventType") or ""
        if ev.get("kids") or _NOT_A_GIG.search(name) or _NOT_A_GIG.search(kind):
            continue

        name, prefix = split_status_prefix(name)
        name, suffix = split_status_suffix(name)
        status = detect_status(prefix, suffix) or Status.SCHEDULED
        note = status_note(prefix) or status_note(suffix)
        if status is Status.POSTPONED and note and re.search(r"\bin\b", note, re.IGNORECASE):
            status = Status.MOVED  # "VERSCHOBEN IN DIE 8MM BAR"

        # "The Risen Dread & Syridas | When Death Comes From Above Tour | Berlin",
        # "June Cocó • Berlin (Kulturhaus Insel) • EP Release Show".
        head, *parts = re.split(r"\s+[|•]\s+", name)
        head = re.sub(r"\s+-\s+berlin$", "", head, flags=re.IGNORECASE)
        parts = [p for p in parts if not re.match(r"berlin\b", p, re.IGNORECASE)]
        title, *extra = re.split(r"\s+\+\s+", head)
        extra = [f"+ {' + '.join(extra)}"] if extra else []

        desc = BeautifulSoup(ev.get("description") or "", "lxml")
        text = desc.get_text("\n")
        if (m := _SUPPORT.search(text)) and not re.fullmatch(r"tb[ac]\.?", m.group(1), re.IGNORECASE):
            extra.append(f"Support: {clean(m.group(1))}")

        when = datetime.fromisoformat(ev["time"]).astimezone(BERLIN)
        doors = hhmm(m.group(1)) if (m := _DOORS.search(text)) else when.strftime("%H:%M")
        start = hhmm(m.group(1)) if (m := _START.search(text)) else None
        events.append(
            Event(
                id=f"insel:{when.date()}-{slugify(title)}",
                venue=VENUE,
                title=title,
                subtitle=" · ".join(parts + extra) or None,
                date=when.date(),
                doors=doors,
                start=start,
                url=_tickets(desc, text) or SOURCE_URL,
                status=status,
                status_note=note,
            )
        )
    return events


def _tickets(desc: BeautifulSoup, text: str) -> str | None:
    """No event pages, so link to the first ticket shop the description points at."""
    for a in desc.select("a[href^=http]"):
        if not _SOCIAL.search(a["href"]):
            return re.sub(r"[?&]fbclid=[^&]*", "", a["href"])
    m = re.search(r"Tickets?\s*:?\s*(https?://\S+)", text, re.IGNORECASE)
    return m.group(1) if m else None

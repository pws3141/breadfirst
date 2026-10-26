from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, hhmm

VENUE = "Hole44"
# The homepage is the whole programme, and it's all concerts.
SOURCE_URL = "https://hole-berlin.de/"

_NEW_DATE = re.compile(r"auf den (\d{1,2})\.(\d{1,2})\.(\d{2,4})")
_INTO_HOLE = re.compile(r"\bin(?:s| das) Hole", re.IGNORECASE)


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events, seen = [], set()
    for item in soup.select("li.event-item"):
        link = item.select_one("a.artist")
        href = link["href"]
        m = re.search(r"/event/(\d{4}-\d{2}-\d{2})-", href)
        if not m or href in seen:
            continue
        seen.add(href)
        day = date.fromisoformat(m.group(1))

        support = link.select_one("span.event-support")
        subtitle = None
        if support:
            subtitle = clean(re.sub(r"^\+\s*(?:support:\s*)?", "", support.get_text(" ", strip=True), flags=re.I))
            support.extract()

        status, note = _status(item, day)
        start = item.select_one(".event_start")
        events.append(
            Event(
                id=f"hole:{href.rstrip('/').rsplit('/', 1)[-1]}",
                venue=VENUE,
                title=clean(link.get_text(" ")),
                subtitle=subtitle,
                date=day,
                start=hhmm(start.get_text()) if start else None,
                url=href,
                status=status,
                status_note=note,
            )
        )
    return events


def _status(item, day: date) -> tuple[Status, str | None]:
    warning = item.select_one("span.warning")
    if warning and detect_status(warning.get_text()) is Status.CANCELLED:
        return Status.CANCELLED, None
    changes = item.select_one("span.changes")
    text = clean(changes.get_text(" ")) if changes else None
    if not text:
        return detect_status(warning and warning.get_text()) or Status.SCHEDULED, None
    # "Achtung! Die Show wird auf den 23.01.2027 verschoben." - also said with "verlegt".
    # The new date gets its own listing, which also carries the notice.
    if m := _NEW_DATE.search(text):
        if _date(*m.groups()) != day:
            return Status.POSTPONED, f"Verschoben {m.group(0)}"
        return Status.SCHEDULED, None
    # "vom Huxleys ins Hole44 verlegt" is good news for us; "ins Metropol verlegt" isn't.
    if _INTO_HOLE.search(text):
        return Status.SCHEDULED, None
    status = detect_status(text) or Status.SCHEDULED
    return status, _sentence(text) if status is not Status.SCHEDULED else None


def _date(d: str, m: str, y: str) -> date:
    year = int(y) + 2000 if len(y) == 2 else int(y)
    return date(year, int(m), int(d))


def _sentence(text: str) -> str:
    """'Achtung! Das Konzert wird ins Metropol verlegt. Bereits ...' -> 'Das Konzert wird ins Metropol verlegt'."""
    text = re.sub(r"^(?:(?:achtung|hinweis|verlegt)\W*)+", "", text, flags=re.IGNORECASE)
    return re.split(r"[.!,]\s", text)[0].rstrip(".!")

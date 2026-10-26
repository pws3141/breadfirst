from __future__ import annotations

import json
import re
from datetime import date, timedelta

from .. import web
from ..models import Event, Status
from ..store import HORIZON_DAYS
from ..text import clean, detect_status, hhmm, split_status_prefix, split_status_suffix, status_note, today_berlin

VENUE = "Neue Zukunft"
PAGE_URL = "https://neue-zukunft.org/konzerte.html"
# konzerte.html is an Elfsight event-calendar widget; this is the JSON it boots from.
WIDGET = "e767cbbe-0026-4173-a511-5aaa105ed563"
SOURCE_URL = "https://core.service.elfsight.com/p/boot/"

_START = re.compile(r"\b(?:Beginn|Show ?start|Show|Start)\s*:?\s*(\d{1,2}[.:]\d{2})", re.IGNORECASE)


def fetch() -> str:
    return web.get(SOURCE_URL, params={"w": WIDGET})


def parse(raw: str, today: date | None = None) -> list[Event]:
    today = today or today_berlin()
    settings = json.loads(raw)["data"]["widgets"][WIDGET]["data"]["settings"]
    events = []
    for ev in settings["events"]:
        description = clean(re.sub(r"<[^>]+>", " ", ev.get("description") or ""))
        if not ev.get("eventType") and not description:
            continue  # editor placeholder

        name, prefix = split_status_prefix(clean(ev["name"]) or "")
        name, suffix = split_status_suffix(name)
        title, *support = re.split(r"\s+\+\s+", name)
        actions = ev.get("actions") or []
        status = detect_status(prefix, suffix) or Status.SCHEDULED
        if status is Status.SCHEDULED and any(detect_status(a.get("text")) is Status.SOLD_OUT for a in actions):
            status = Status.SOLD_OUT
        url = next((a["link"]["value"] for a in actions if (a.get("link") or {}).get("value")), PAGE_URL)

        # start.time is doors; times in the morning are editor defaults nobody changed.
        doors = hhmm(ev["start"].get("time"))
        if doors and doors < "15:00":
            doors = None
        start = hhmm(m.group(1)) if (m := _START.search(description or "")) else None

        recurring = ev.get("repeatPeriod", "noRepeat") != "noRepeat"
        for day in _dates(ev, today):
            events.append(
                Event(
                    id=f"neuezukunft:{ev['id']}:{day}" if recurring else f"neuezukunft:{ev['id']}",
                    venue=VENUE,
                    title=title,
                    subtitle=" ".join(f"+ {s}" for s in support) or None,
                    date=day,
                    doors=doors,
                    start=start,
                    url=url,
                    status=status,
                    status_note=status_note(prefix) or status_note(suffix),
                )
            )
    return events


def _dates(ev: dict, today: date) -> list[date]:
    seed = date.fromisoformat(ev["start"]["date"])
    if ev.get("repeatPeriod", "noRepeat") == "noRepeat":
        return [seed]
    # The jazz bar's sessions are set up as "every 1st and 3rd Wednesday" by giving one
    # seed per week of the month, so repeat each seed monthly on its nth weekday.
    nth = (seed.day - 1) // 7
    end = today + timedelta(days=HORIZON_DAYS)
    if ev.get("repeatEnds") == "onDate" and ev.get("repeatEndsDate"):
        end = min(end, date.fromisoformat(ev["repeatEndsDate"][:10]))
    skip = set(ev.get("exceptions") or [])
    days = []
    year, month = seed.year, seed.month
    while date(year, month, 1) <= end:
        first = date(year, month, 1)
        day = first + timedelta(days=(seed.weekday() - first.weekday()) % 7 + 7 * nth)
        if day.month == month and seed <= day <= end and day >= today and day.isoformat() not in skip:
            days.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return days

from __future__ import annotations

import json
from datetime import datetime

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, split_status_suffix, status_note

VENUE = "Privatclub"
SOURCE_URL = "https://privatclub-berlin.de/"


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")

    # Each event has a MusicEvent JSON-LD block (parties too); match them up by URL.
    ld = {}
    for script in soup.select('script[type="application/ld+json"]'):
        for item in json.loads(script.string, strict=False):
            if item.get("@type") == "MusicEvent":
                ld[item["url"]] = item

    events = []
    for wrapper in soup.select('div.event_wrapper[id^="id_"]'):
        kind = wrapper.select_one(".event_typ")
        if not kind or kind.get_text(strip=True).lower() != "konzert":
            continue
        url = wrapper.select_one("a.event_header")["href"]
        data = ld.get(url)
        if not data:
            continue
        start = datetime.fromisoformat(data["startDate"])

        title, suffix = split_status_suffix(clean(wrapper.select_one(".zeile_titel .titel").get_text()))
        sub_el = wrapper.select_one(".zeile_untertitel .untertitel")

        status = Status.SCHEDULED
        label = wrapper.select_one("div.label")
        label_text = label.get_text(" ", strip=True).lower() if label else ""
        if data.get("eventStatus", "").endswith("EventCancelled") or "abgesagt" in label_text:
            status = Status.CANCELLED
        elif "ausverkauft" in label_text:
            status = Status.SOLD_OUT
        elif "verlegt" in label_text or "verschoben" in label_text:
            status = Status.POSTPONED

        events.append(
            Event(
                id=f"privatclub:{wrapper['id'].removeprefix('id_')}",
                venue=VENUE,
                title=title,
                subtitle=clean(sub_el.get_text(" ")) if sub_el else None,
                date=start.date(),
                doors=data.get("doorTime"),
                start=start.strftime("%H:%M"),
                url=url,
                status=status,
                status_note=status_note(suffix),
            )
        )
    return events

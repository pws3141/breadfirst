from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status

VENUE = "Lido"
SOURCE_URL = "https://www.lido-berlin.de/"

_STATUS_LABELS = {
    "ausverkauft": Status.SOLD_OUT,
    "verlegt": Status.MOVED,
    "verschoben": Status.POSTPONED,
    "abgesagt": Status.CANCELLED,
}


def fetch() -> str:
    # Labels ("Konzert", "Ausverkauft") follow Accept-Language, which web.get pins to German.
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events = []
    # Today's event is only in the teaser block; it was already picked up on earlier runs.
    for card in soup.select("div.event-list > article.event-ticket"):
        kind = card.select_one(".event-ticket__type__label")
        if not kind or kind.get_text(strip=True).lower() != "konzert":
            continue
        link = card.select_one("h1.event-ticket__content__title a")
        # The date in the URL is unreliable; data-realdate is the doors time with offset.
        when = datetime.strptime(card["data-realdate"], "%Y-%m-%d %H:%M:%S %z")

        times = {}
        for t in card.select(".event-ticket__meta--desktop .event-ticket__meta__times__time"):
            label = t.select_one(".event-ticket__meta__times__time__label").get_text(strip=True)
            times[label.lower()] = t.select_one(".event-ticket__meta__times__time__value").get_text(strip=True)

        sub_el = card.select_one(".event-ticket__content__subtitle")
        subtitle_lines = [clean(s) for s in sub_el.stripped_strings] if sub_el else []
        subtitle_lines = [s for s in subtitle_lines if s]

        status = Status.SCHEDULED
        note = None
        label = card.select_one(".event-ticket__content__status__label")
        if label:
            status = _STATUS_LABELS.get(label.get_text(strip=True).lower(), Status.SCHEDULED)
        if status in (Status.MOVED, Status.POSTPONED, Status.CANCELLED):
            # The subtitle usually says where to / why, e.g. "HOCHVERLEGT IN DAS COLUMBIA THEATER".
            note = next((s for s in subtitle_lines if detect_status(s) == status), None)
            note = note and re.split(r"[.!]\s", note)[0].rstrip(".!")
        # Keep the subtitle to the tour name / support; drop shouty notices about status.
        subtitle = " · ".join(s for s in subtitle_lines if not detect_status(s)) or None

        href = link["href"]
        events.append(
            Event(
                id=f"lido:{href.rstrip('/').rsplit('/', 1)[-1]}",
                venue=VENUE,
                title=clean(link.get_text()),
                subtitle=subtitle,
                date=when.date(),
                doors=times.get("einlass") or when.strftime("%H:%M"),
                start=times.get("start"),
                url=urljoin(SOURCE_URL, href),
                status=status,
                status_note=note,
            )
        )
    return events

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
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

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["januar", "februar", "märz", "april", "mai", "juni", "juli",
         "august", "september", "oktober", "november", "dezember"],
        start=1,
    )
}


def fetch() -> str:
    # Labels ("Konzert", "Ausverkauft") follow Accept-Language, which web.get pins to German.
    soup = BeautifulSoup(web.get(SOURCE_URL), "lxml")
    # The next event (today's, or days away if there's a gap) is taken out of the list and
    # shown only in the teaser, without its type or start time. Its own page has the full
    # ticket, so graft that into the teaser for parse() to pick up.
    link = soup.select_one(".teaser__next-events__wrapper__event a[href]")
    if link:
        try:
            page = BeautifulSoup(web.get(urljoin(SOURCE_URL, link["href"])), "lxml")
        except httpx.HTTPError:
            page = None
        ticket = page and page.select_one("article.event > header.event-ticket")
        if ticket:
            link.find_parent(class_="teaser__next-events__wrapper__event").append(ticket)
    return str(soup)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events = []
    seen = set()
    for card in soup.select(
        "div.event-list > article.event-ticket, .teaser__next-events__wrapper__event > header.event-ticket"
    ):
        kind = card.select_one(".event-ticket__type__label")
        if not kind or kind.get_text(strip=True).lower() != "konzert":
            continue
        link = card.select_one("h1.event-ticket__content__title a")
        if link["href"] in seen:
            continue
        seen.add(link["href"])
        day, realdoors = _when(card)

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
                date=day,
                doors=times.get("einlass") or realdoors,
                start=times.get("start"),
                url=urljoin(SOURCE_URL, href),
                status=status,
                status_note=note,
            )
        )
    return events



def _when(card) -> tuple[date, str | None]:
    """(date, doors time if known)."""
    # The date in the URL is unreliable. List cards have data-realdate (doors time with
    # offset); the ticket from an event's own page only has the visible day/month/year.
    if card.has_attr("data-realdate"):
        when = datetime.strptime(card["data-realdate"], "%Y-%m-%d %H:%M:%S %z")
        return when.date(), when.strftime("%H:%M")
    meta = card.select_one(".event-ticket__meta--desktop .event-ticket__meta__date")
    part = lambda name: meta.select_one(f".event-ticket__meta__date__{name}").get_text(strip=True)
    return date(int(part("year")), _MONTHS[part("month").lower()], int(part("day"))), None

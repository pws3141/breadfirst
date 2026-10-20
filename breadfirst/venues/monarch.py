from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from .. import web
from ..models import Event, Status
from ..text import clean, detect_status, slugify, split_status_suffix, status_note

VENUE = "Monarch"
SOURCE_URL = "https://kottimonarch.de/programm.php"

_WHEN = re.compile(r"(\d{2})/(\d{2})/(\d{4})-(\d{2}:\d{2})?")
_KONZERT_TAG = re.compile(r"\s*\(KONZERT\)\s*", re.IGNORECASE)


def fetch() -> str:
    return web.get(SOURCE_URL)


def parse(raw: str) -> list[Event]:
    soup = BeautifulSoup(raw, "lxml")
    events = []
    for block in soup.select('div[style*="border-bottom:1px solid #cccccc"]'):
        when = _WHEN.search(block.find("b").get_text())
        if not when:
            continue
        dd, mm, yyyy, time = when.groups()
        day = date(int(yyyy), int(mm), int(dd))

        rows = block.select("table")[0].select("tr")
        title = clean(rows[0].get_text()) or ""
        series = clean(rows[1].get_text()) if len(rows) > 1 else None
        desc_el = block.select_one("td.tom")
        desc = clean(desc_el.get_text(" ")) if desc_el else None

        # Concerts are tagged "(KONZERT)"; a few untagged ones say so in the text.
        is_concert = bool(_KONZERT_TAG.search(title)) or bool(
            desc and re.search(r"\bkonzert\b", desc, re.IGNORECASE)
        )
        if not is_concert:
            continue

        title = _KONZERT_TAG.sub(" ", title).strip() or series or ""
        title, suffix = split_status_suffix(title)
        status = detect_status(suffix) or Status.SCHEDULED
        support = re.match(r"support:\s*(.+)", desc or "", re.IGNORECASE)

        events.append(
            Event(
                # No per-event pages or ids, so date + title is the best key there is.
                id=f"monarch:{day.isoformat()}-{slugify(title)}",
                venue=VENUE,
                title=title,
                subtitle=f"Support: {support.group(1)}" if support else None,
                date=day,
                start=time,
                url=SOURCE_URL,
                status=status,
                status_note=status_note(suffix),
            )
        )
    return events

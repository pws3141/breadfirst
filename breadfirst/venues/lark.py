from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta

from .. import web
from ..models import Event, Status
from ..store import HORIZON_DAYS
from ..text import clean, detect_status, split_status_prefix, split_status_suffix, status_note, today_berlin

VENUE = "Lark"
# WordPress REST API for the "event" post type; the post date is the event's doors time.
SOURCE_URL = "https://larkberlin.com/wp-json/wp/v2/event"

# "Flower Face SOLD OUT", "X (ausverkauft)", "X CANCELLED (follow ticket link for refunds)".
_STATUS_END = re.compile(
    r"\s*\(?\b(sold[ -]out|ausverkauft|abgesagt|cancell?ed|postponed|verschoben)\b\)?(?:\s*\([^)]*\))?\s*$",
    re.IGNORECASE,
)
# No event type to go on, so club nights are told apart by time and name.
_PARTY = re.compile(r"\bCLUBS\b|After Dark|\bParty\b|Disko|\bDJs?\b", re.IGNORECASE)
_SUPPORT = re.compile(r"\s+\+\s*|\s*\+\s+")


def fetch() -> str:
    today = today_berlin()
    end = today + timedelta(days=HORIZON_DAYS)
    return web.get(
        SOURCE_URL,
        params={
            "per_page": 100,
            "after": f"{today}T00:00:00",
            "before": f"{end}T23:59:59",
            "orderby": "date",
            "order": "asc",
            "_fields": "id,date,link,title,acf",
        },
    )


def parse(raw: str) -> list[Event]:
    events = []
    for post in json.loads(raw):
        acf = post.get("acf") or {}
        when = datetime.fromisoformat(acf.get("event_date") or post["date"])
        name = clean(html.unescape(post["title"]["rendered"])) or ""
        if when.hour >= 22 or _PARTY.search(name):
            continue

        name, prefix = split_status_prefix(name)
        name, suffix = split_status_suffix(name)
        flag = None
        if m := _STATUS_END.search(name):
            name, flag = name[: m.start()].strip(), m.group(1)
        status = detect_status(prefix, suffix, flag) or Status.SCHEDULED
        if status is Status.SCHEDULED and acf.get("event_status") == "Postponed":
            status = Status.POSTPONED

        title, subtitle = _split_name(name)
        events.append(
            Event(
                id=f"lark:{post['id']}",
                venue=VENUE,
                title=title,
                subtitle=subtitle,
                date=when.date(),
                doors=when.strftime("%H:%M"),
                url=post["link"],
                status=status,
                status_note=status_note(prefix) or status_note(suffix),
            )
        )
    return events


def _split_name(name: str) -> tuple[str, str | None]:
    """'Greg Mendez – BEAUTY LAND TOUR +  Lily Seabird (support)'
    -> ('Greg Mendez', 'BEAUTY LAND TOUR · + Lily Seabird')."""
    head, *others = _SUPPORT.split(name)
    title, _, tour = head.partition(" – ")
    parts = [tour.strip()] if tour.strip() else []
    others = [re.sub(r"^support:\s*|\s*\(support\)$", "", o, flags=re.IGNORECASE).strip() for o in others]
    if others:
        parts.append("+ " + " + ".join(o for o in others if o))
    return title.strip(), " · ".join(parts) or None

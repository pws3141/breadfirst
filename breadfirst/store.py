from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from .models import Event, Status

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "events.json"
HORIZON_DAYS = 31
VANISHED_NOTE = "No longer listed"


def load(path: Path = DATA_FILE) -> list[Event]:
    if not path.exists():
        return []
    return [Event.from_dict(d) for d in json.loads(path.read_text())["events"]]


def save(events: list[Event], updated_at: str, path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": updated_at, "events": [e.to_dict() for e in events]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def merge(
    existing: list[Event],
    scraped: dict[str, list[Event]],
    today: date,
) -> list[Event]:
    """Fold one run's scrape into the stored events.

    `scraped` maps venue name -> events, for venues whose scrape succeeded only.
    Venues missing from it keep their stored events untouched.
    """
    horizon = today + timedelta(days=HORIZON_DAYS)
    by_id = {e.id: e for e in existing}

    for venue, events in scraped.items():
        seen = {e.id for e in events}
        for new in events:
            if not today <= new.date <= horizon:
                # e.g. rescheduled to beyond the horizon: not vanished, just not shown yet.
                by_id.pop(new.id, None)
                continue
            old = by_id.get(new.id)
            by_id[new.id] = replace(
                new,
                first_seen=old.first_seen if old else today,
                last_seen=today,
            )
        # Venues often drop today's gig from their listing during the day, so only
        # treat future events as vanished.
        for e in list(by_id.values()):
            if e.venue == venue and e.id not in seen and e.date > today:
                if e.status is not Status.CANCELLED:
                    by_id[e.id] = replace(e, status=Status.CANCELLED, status_note=VANISHED_NOTE)

    kept = [e for e in by_id.values() if e.date >= today]
    return sorted(kept, key=lambda e: (e.date, e.time or "99:99", e.venue, e.title))

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum


class Status(str, Enum):
    SCHEDULED = "scheduled"
    SOLD_OUT = "sold_out"
    POSTPONED = "postponed"
    MOVED = "moved"
    CANCELLED = "cancelled"


@dataclass
class Event:
    id: str
    venue: str
    title: str
    date: date
    url: str
    subtitle: str | None = None
    doors: str | None = None  # "HH:MM", Berlin local
    start: str | None = None  # "HH:MM", Berlin local
    status: Status = Status.SCHEDULED
    status_note: str | None = None
    first_seen: date | None = None
    last_seen: date | None = None

    @property
    def time(self) -> str | None:
        return self.start or self.doors

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["status"] = self.status.value
        d["first_seen"] = self.first_seen.isoformat() if self.first_seen else None
        d["last_seen"] = self.last_seen.isoformat() if self.last_seen else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Event:
        d = dict(d)
        d["date"] = date.fromisoformat(d["date"])
        d["status"] = Status(d["status"])
        for k in ("first_seen", "last_seen"):
            d[k] = date.fromisoformat(d[k]) if d.get(k) else None
        return cls(**d)

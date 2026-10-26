from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .models import Status

BERLIN = ZoneInfo("Europe/Berlin")

# Most serious first: a "verlegt" event that's also marked "abgesagt" is cancelled.
_STATUS_WORDS = [
    (Status.CANCELLED, r"abgesagt|cancell?ed"),
    (Status.POSTPONED, r"verschoben|postponed"),
    (Status.MOVED, r"verlegt|moved to"),
    (Status.SOLD_OUT, r"ausverkauft|sold[ -]out"),
]
_ANY_STATUS = "|".join(p for _, p in _STATUS_WORDS)

# Status appended to a title, e.g. "MOLIY - *Abgesagt*", "BERWYN // CANCELLED",
# "Zoh Amba - Verlegt ins Bi Nuu", "Marnele - ABGESAGT / CANCELED".
_TITLE_SUFFIX = re.compile(
    rf"\s*(?:-|–|//)\s*\*?\s*((?:{_ANY_STATUS}).*?)[\s*!]*$", re.IGNORECASE
)


# Status put before a title, e.g. "!!AUSVERKAUFT!! Tim Vantol", "SOLD OUT: X", "ABGESAGT X",
# "CANCELLED: X", "VERSCHOBEN IN DIE 8MM BAR: X". Without punctuation it must be shouted,
# so a band called "Cancelled Plans" keeps its name.
_TITLE_PREFIX = re.compile(
    rf"^[!*\s]*((?:{_ANY_STATUS})(?:\s+in\s+[^:!]+(?=\s*:))?)(?:\s*([!:*]+)\s*|\s+)", re.IGNORECASE
)


def detect_status(*texts: str | None) -> Status | None:
    joined = " ".join(t for t in texts if t)
    for status, pattern in _STATUS_WORDS:
        if re.search(pattern, joined, re.IGNORECASE):
            return status
    return None


def split_status_suffix(title: str) -> tuple[str, str | None]:
    """Return (title without status suffix, the suffix)."""
    m = _TITLE_SUFFIX.search(title)
    if not m:
        return title, None
    return title[: m.start()].strip(), m.group(1).strip()


def split_status_prefix(title: str) -> tuple[str, str | None]:
    """Return (title without status prefix, the prefix)."""
    m = _TITLE_PREFIX.search(title)
    if not m or not title[m.end():].strip() or not (m.group(2) or m.group(1).isupper()):
        return title, None
    return title[m.end():].strip(), m.group(1).strip()


def status_note(suffix: str | None) -> str | None:
    """Keep a suffix as a note only when it says more than the status word, e.g. where to."""
    if not suffix:
        return None
    rest = re.sub(rf"^(?:{_ANY_STATUS})\b", "", suffix, flags=re.IGNORECASE).strip(" /!*")
    if not rest or re.fullmatch(_ANY_STATUS, rest, re.IGNORECASE):
        return None
    return suffix


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return text or None


def hhmm(text: str | None) -> str | None:
    """'19.30' / '19:30' / '7:00 pm' / '19h' -> '19:30' etc."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})(?:[.:](\d{2}))?\s*([ap]m)?", text, re.IGNORECASE)
    if not m:
        return None
    h, mins, ampm = int(m.group(1)), m.group(2) or "00", (m.group(3) or "").lower()
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mins}"


def today_berlin() -> date:
    return datetime.now(BERLIN).date()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

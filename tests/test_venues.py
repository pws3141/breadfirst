from datetime import date
from pathlib import Path

import pytest

from breadfirst.models import Status
from breadfirst.text import hhmm, split_status_suffix, status_note
from breadfirst.venues import gretchen, kantine, lido, monarch, prachtwerk, privatclub

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str, module) -> dict:
    ext = "json" if module is prachtwerk else "html"
    events = module.parse((FIXTURES / f"{name}.{ext}").read_text(encoding="utf-8"))
    assert events, f"{name}: parsed no events"
    return {e.title: e for e in events}


def test_lido():
    events = load("lido", lido)
    nand = events["NAND"]
    assert (nand.date, nand.doors, nand.start, nand.status) == (date(2026, 10, 22), "19:00", "20:00", Status.SOLD_OUT)
    assert events["TYLA YAWEH"].status is Status.CANCELLED
    sons = events["SONS OF LEGION"]
    assert sons.status is Status.MOVED
    assert sons.status_note == "HOCHVERLEGT IN DAS COLUMBIA THEATER"
    # URL says 2026-11-11 but the real date is the 6th.
    assert events["WESTSIDE COWBOY"].date == date(2026, 11, 6)
    # Status notices are kept out of the subtitle.
    assert "AUSVERKAUFT" not in (events["KAYLA SHYX"].subtitle or "")


def test_lido_skips_parties():
    events = lido.parse((FIXTURES / "lido.html").read_text())
    assert len(events) < 100  # the page lists 100 events, 16 or so are parties


def test_kantine():
    events = load("kantine", kantine)
    assert events["MOLIY"].status is Status.CANCELLED
    assert events["MOLIY"].date == date(2026, 10, 21)
    assert events["Yosho"].status is Status.POSTPONED
    zoh = events["Zoh Amba"]
    assert (zoh.status, zoh.status_note) == (Status.MOVED, "Verlegt ins Bi Nuu")
    assert events["GIRLS IN HAWAII"].subtitle == "Blumi"
    # A line-up with no "Live" act is a DJ night.
    assert "Psych Dreamers" not in events


def test_monarch():
    events = load("monarch", monarch)
    cactus = events["CACTUS FOR BREAKFAST"]
    assert (cactus.date, cactus.start, cactus.subtitle) == (date(2026, 10, 23), "19:00", "Support: wearemarvin")
    assert "INDIE GROUND" not in events
    assert "POETRY SLAM KREUZBERG" not in events


def test_privatclub():
    events = load("privatclub", privatclub)
    assert events["Marnele"].status is Status.CANCELLED
    robine = events["Robine"]
    assert (robine.date, robine.doors, robine.start, robine.status) == (date(2026, 10, 21), "19:00", "20:00", Status.SOLD_OUT)
    assert "Dedicated" not in events  # party
    assert "Songslam Kreuzberg" not in events


def test_gretchen():
    events = load("gretchen", gretchen)
    berwyn = events["Greyzone presents: BERWYN"]
    assert (berwyn.date, berwyn.status) == (date(2026, 10, 26), Status.CANCELLED)
    skeler = events["Trinity presents: SKELER - Nightfall World Tour"]
    assert (skeler.doors, skeler.start) == ("19:00", "20:00")
    assert not any("WHAT SO NOT" in t for t in events)  # doors-only club night
    assert not any("PURO BARRIO" in t for t in events)


def test_prachtwerk():
    events = load("prachtwerk", prachtwerk)
    neomi = events["NÉOMÍ"]
    assert (neomi.date, neomi.doors, neomi.start) == (date(2026, 10, 24), "18:30", "19:30")
    wolf = events["Patrick Wolf"]
    assert wolf.subtitle == "The Beast"
    assert (wolf.doors, wolf.start) == ("19:00", "20:00")
    saults = events["Saults Plays Prince + TILAR"]
    assert (saults.doors, saults.start) == ("19:00", "20:00")  # "Doors: 7:00 PM | Show: 8:00 PM"
    assert events["TRIXIE WHITLEY"].doors == "19:00"  # "Einlass 19h"
    assert "SAULTS" in events and "OSTR" in events and "AINDA" in events


@pytest.mark.parametrize(
    "title, clean, suffix, note",
    [
        ("MOLIY - *Abgesagt*", "MOLIY", "Abgesagt", None),
        ("Gast - Abgesagt!", "Gast", "Abgesagt", None),
        ("Zoh Amba - Verlegt ins Bi Nuu", "Zoh Amba", "Verlegt ins Bi Nuu", "Verlegt ins Bi Nuu"),
        ("Greyzone presents: BERWYN // CANCELLED", "Greyzone presents: BERWYN", "CANCELLED", None),
        ("Marnele - ABGESAGT / CANCELED", "Marnele", "ABGESAGT / CANCELED", None),
        ("Trinity presents: SKELER - Nightfall World Tour", "Trinity presents: SKELER - Nightfall World Tour", None, None),
    ],
)
def test_split_status_suffix(title, clean, suffix, note):
    assert split_status_suffix(title) == (clean, suffix)
    assert status_note(suffix) == note


@pytest.mark.parametrize(
    "text, expected",
    [("19.30", "19:30"), ("19:00", "19:00"), ("7:00 PM", "19:00"), ("19h", "19:00"), ("12:00 am", "00:00"), ("", None)],
)
def test_hhmm(text, expected):
    assert hhmm(text) == expected

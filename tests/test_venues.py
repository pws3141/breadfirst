from datetime import date
from pathlib import Path

import pytest

from breadfirst.models import Status
from breadfirst.text import hhmm, split_status_prefix, split_status_suffix, status_note
from breadfirst.venues import (
    donau115,
    gretchen,
    hole,
    insel,
    kantine,
    lark,
    lido,
    monarch,
    neuezukunft,
    prachtwerk,
    privatclub,
    sowieso,
)

FIXTURES = Path(__file__).parent / "fixtures"
# The day the fixtures were saved, for parsers that need to know when "now" is.
SAVED = date(2026, 10, 26)


def load(name: str, module, **kwargs) -> dict:
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        path = FIXTURES / f"{name}.html"
    events = module.parse(path.read_text(encoding="utf-8"), **kwargs)
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


def test_lido_teaser():
    # With no gigs Sun/Mon, Tuesday's was only in the teaser; fetch() grafts in its ticket.
    events = load("lido_teaser", lido)
    dan = events["DAN WHITLAM"]
    assert (dan.date, dan.doors, dan.start, dan.status) == (date(2026, 10, 27), "19:00", "20:00", Status.SCHEDULED)
    assert dan.subtitle == "+ Support: EMILIA RENN"


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


def test_hole():
    events = {e.id: e for e in hole.parse((FIXTURES / "hole.html").read_text(encoding="utf-8"))}
    wolves = events["hole:2026-10-27-wolves-in-the-throne-room"]
    assert (wolves.title, wolves.doors, wolves.start) == ("Wolves in the Throne Room", None, "19:30")
    assert wolves.subtitle == "Worm and Final Dose"
    assert events["hole:2026-10-30-deloraine"].status is Status.CANCELLED
    underscores = events["hole:2026-11-03-underscores"]
    assert (underscores.status, underscores.status_note) == (Status.MOVED, "Das Konzert wird ins Metropol verlegt")
    # The old date carries the notice; the new date is listed too, and is going ahead.
    jero = events["hole:2026-10-31-jero19"]
    assert (jero.status, jero.status_note) == (Status.POSTPONED, "Verschoben auf den 23.01.2027")
    assert events["hole:2027-01-23-jero19"].status is Status.SCHEDULED
    # Moved into the Hole from elsewhere, or "verlegt" to the date it's already listed on.
    assert events["hole:2026-10-29-kate-ryan"].status is Status.SCHEDULED
    assert events["hole:2026-11-04-kyle-alessandro"].status is Status.SCHEDULED
    assert events["hole:2027-05-30-omar76"].status is Status.SCHEDULED


def test_lark():
    events = load("lark", lark)
    greg = events["Greg Mendez"]
    assert (greg.date, greg.doors, greg.subtitle) == (date(2026, 10, 27), "19:00", "BEAUTY LAND TOUR · + Lily Seabird")
    assert events["Flower Face"].status is Status.SOLD_OUT
    assert events["aupinard"].subtitle == "“spleen. social club” Tour"
    assert events["Nokia Angel"].subtitle == "NECROMANCE TOUR"  # a concert, despite the ra.co tickets
    assert not any("Disko Souk" in t or "After Dark" in t or "CLUBS" in t for t in events)
    assert not any("Release Film Party" in t for t in events)


def test_neuezukunft():
    events = load("neuezukunft", neuezukunft, today=SAVED)
    melt = events["Melt Banana"]
    assert (melt.date, melt.doors, melt.start, melt.subtitle) == (date(2026, 11, 4), "19:00", None, "+ MPC Lafote")
    assert melt.url.startswith("https://www.tixforgigs.com/")
    assert events["Victoryland"].start == "20:00"  # "Show start: 20:00" in the description
    assert events["Ragana"].status is Status.SOLD_OUT


def test_neuezukunft_recurring():
    raw = (FIXTURES / "neuezukunft.json").read_text(encoding="utf-8")
    dates = lambda title: sorted(e.date for e in neuezukunft.parse(raw, today=SAVED) if e.title == title)
    # One seed per week of the month: 1st and 3rd Wednesdays, and 2nd and 4th.
    assert dates("Jazz After Dark") == [date(2026, 11, 4), date(2026, 11, 18)]
    assert dates("Future Bash Reloaded") == [date(2026, 10, 28), date(2026, 11, 11), date(2026, 11, 25)]


def test_donau115():
    events = load("donau115", donau115)
    dida = events["Dida Pelled"]
    assert (dida.date, dida.doors, dida.start, dida.url) == (date(2026, 10, 21), "19:30", None, "https://donau115.de/")
    assert events["Two-Song Tuesday"].start == "20:00"  # "(MUSIC STARTS 20:00)" taken out of the title
    assert events["Thursday Jazz Jam"].start == "20:00"  # "doors: 19:30 / opening set: 20"
    assert events["Domingo Fantástico IX"].start == "20:30"
    assert events["Ignore The Machine (hanno leichtmann / nils ostendorf)"].status is Status.CANCELLED
    assert "Phemo Quartet" not in events  # unpublished draft


def test_insel():
    events = load("insel", insel)
    aussichten = events["Die Weiteren Aussichten"]
    assert (aussichten.date, aussichten.doors, aussichten.start) == (date(2026, 11, 6), "19:00", "20:00")
    assert aussichten.subtitle == "Support: Alles Karo"
    assert aussichten.url.startswith("https://www.eventim.de/")
    assert events["Tim Vantol"].status is Status.SOLD_OUT  # "!!AUSVERKAUFT!! Tim Vantol"
    assert events["The Risen Dread & Syridas"].subtitle == "When Death Comes From Above Tour"
    assert events["June Cocó"].subtitle == "EP Release Show"
    assert events["Dion Lunadon (NZ)"].status is Status.MOVED  # "VERSCHOBEN IN DIE 8MM BAR: ..."
    assert "fbclid" not in events["Marlin Beach"].url
    assert not any("Slam" in t or "Comedy" in t or "Geschlossene" in t for t in events)


def test_sowieso():
    events = load("sowieso", sowieso, today=SAVED)
    space = events["Space"]
    assert (space.date, space.doors, space.start) == (date(2026, 10, 24), "20:00", "20:30")
    assert space.subtitle == "Lisa Ullén (piano), Elsa Bergman (double bass) & Anna Lund (drums)"
    assert events["Aki Takase & Alexander von Schlippenbach"].subtitle == "piano solos and duos"
    assert "Fanny Méteier | Foster & Griener" in events


@pytest.mark.parametrize(
    "month, day, today, expected",
    [
        ("Oct", 22, date(2026, 10, 26), date(2026, 10, 22)),  # a few days ago
        ("Jan", 8, date(2026, 12, 20), date(2027, 1, 8)),
        ("Dec", 30, date(2027, 1, 3), date(2026, 12, 30)),
    ],
)
def test_sowieso_year(month, day, today, expected):
    assert sowieso._date(month, day, today) == expected


@pytest.mark.parametrize(
    "title, clean, prefix",
    [
        ("!!AUSVERKAUFT!! Tim Vantol", "Tim Vantol", "AUSVERKAUFT"),
        ("SOLD OUT: Flower Face", "Flower Face", "SOLD OUT"),
        ("ABGESAGT Foo", "Foo", "ABGESAGT"),
        ("CANCELLED: Ignore The Machine", "Ignore The Machine", "CANCELLED"),
        ("VERSCHOBEN IN DIE 8MM BAR: Dion Lunadon", "Dion Lunadon", "VERSCHOBEN IN DIE 8MM BAR"),
        ("Cancelled Plans", "Cancelled Plans", None),  # a band name, not a notice
        ("SOLD OUT", "SOLD OUT", None),
    ],
)
def test_split_status_prefix(title, clean, prefix):
    assert split_status_prefix(title) == (clean, prefix)


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

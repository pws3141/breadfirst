from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import store
from .models import Status
from .text import BERLIN

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent / "site"

VENUE_SITES = {
    "Lido": "https://www.lido-berlin.de/",
    "Prachtwerk": "https://www.prachtwerkberlin.com/",
    "Kantine am Berghain": "https://www.berghain.berlin/de/program/kantine-am-berghain/",
    "Monarch": "https://kottimonarch.de/",
    "Privatclub": "https://privatclub-berlin.de/",
    "Gretchen": "https://www.gretchen-club.de/",
}

STATUS_LABELS = {
    Status.SOLD_OUT: "Sold out",
    Status.POSTPONED: "Postponed",
    Status.MOVED: "Moved",
    Status.CANCELLED: "Cancelled",
}


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build(today: date, data_file: Path = store.DATA_FILE, out_dir: Path = SITE_DIR) -> Path:
    events = [e for e in store.load(data_file) if e.date >= today]
    updated_at = None
    if data_file.exists():
        updated_at = json.loads(data_file.read_text()).get("updated_at")

    by_day = {d: list(evs) for d, evs in groupby(events, key=lambda e: e.date)}
    days = [today + timedelta(days=i) for i in range(store.HORIZON_DAYS + 1)]

    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["ordinal"] = _ordinal
    html = env.get_template("index.html.j2").render(
        today=today,
        days=days,
        by_day=by_day,
        status_labels=STATUS_LABELS,
        venue_sites=VENUE_SITES,
        updated_at=datetime.fromisoformat(updated_at).astimezone(BERLIN) if updated_at else None,
        css=(HERE / "static" / "style.css").read_text(),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(html)
    return out

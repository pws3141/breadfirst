from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime

from . import build, store
from .models import Status
from .text import BERLIN, today_berlin
from .venues import VENUES


def scrape(venues: list[str], dry_run: bool) -> int:
    today = today_berlin()
    scraped, failed = {}, []
    for key in venues:
        mod = VENUES[key]
        try:
            events = mod.parse(mod.fetch())
        except Exception:
            traceback.print_exc()
            failed.append(mod.VENUE)
            continue
        if not events:
            print(f"warning: {mod.VENUE}: parsed 0 events; keeping previous listings", file=sys.stderr)
            failed.append(mod.VENUE)
            continue
        scraped[mod.VENUE] = events
        print(f"{mod.VENUE}: {len(events)} live events found")

    before = {e.id: e for e in store.load()}
    merged = store.merge(list(before.values()), scraped, today)
    added = [e for e in merged if e.id not in before]
    newly_cancelled = [
        e for e in merged
        if e.status is Status.CANCELLED and e.id in before and before[e.id].status is not Status.CANCELLED
    ]
    print(f"{len(merged)} events in window; {len(added)} new, {len(newly_cancelled)} newly cancelled")
    for e in added:
        print(f"  + {e.date} {e.venue}: {e.title}")
    for e in newly_cancelled:
        print(f"  x {e.date} {e.venue}: {e.title} ({e.status_note or 'cancelled'})")

    if failed:
        msg = "Failed venues (listings kept from last run): " + ", ".join(failed)
        print(msg, file=sys.stderr)
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(summary, "a") as f:
                f.write(f"⚠️ {msg}\n")

    if not dry_run:
        store.save(merged, updated_at=datetime.now(BERLIN).isoformat(timespec="seconds"))
    return 1 if len(failed) == len(venues) else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="breadfirst")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("scrape", "all"):
        p = sub.add_parser(name)
        p.add_argument("--venue", action="append", choices=sorted(VENUES), help="only scrape these venues")
        p.add_argument("--dry-run", action="store_true", help="don't write data/events.json")
    sub.add_parser("build")
    args = parser.parse_args()

    code = 0
    if args.cmd in ("scrape", "all"):
        code = scrape(args.venue or list(VENUES), args.dry_run)
    if args.cmd in ("build", "all"):
        print(f"wrote {build.build(today_berlin())}")
    return code


if __name__ == "__main__":
    sys.exit(main())

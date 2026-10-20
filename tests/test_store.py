from datetime import date, timedelta

from breadfirst import store
from breadfirst.models import Event, Status

TODAY = date(2026, 10, 20)


def ev(id, day_offset=1, venue="Lido", status=Status.SCHEDULED, **kw):
    return Event(
        id=id, venue=venue, title=id.upper(), date=TODAY + timedelta(days=day_offset),
        url=f"https://example.com/{id}", status=status, **kw,
    )


def by_id(events):
    return {e.id: e for e in events}


def test_new_events_are_added_with_first_seen():
    merged = by_id(store.merge([], {"Lido": [ev("a")]}, TODAY))
    assert merged["a"].first_seen == TODAY
    assert merged["a"].last_seen == TODAY


def test_existing_events_are_updated_and_keep_first_seen():
    old = ev("a", first_seen=TODAY - timedelta(days=3), last_seen=TODAY - timedelta(days=1))
    merged = by_id(store.merge([old], {"Lido": [ev("a", status=Status.SOLD_OUT, start="20:00")]}, TODAY))
    assert merged["a"].first_seen == TODAY - timedelta(days=3)
    assert merged["a"].last_seen == TODAY
    assert merged["a"].status is Status.SOLD_OUT
    assert merged["a"].start == "20:00"


def test_explicit_cancellation_is_kept():
    merged = by_id(store.merge([ev("a")], {"Lido": [ev("a", status=Status.CANCELLED)]}, TODAY))
    assert merged["a"].status is Status.CANCELLED


def test_vanished_future_event_is_marked_cancelled():
    merged = by_id(store.merge([ev("a"), ev("b")], {"Lido": [ev("b")]}, TODAY))
    assert merged["a"].status is Status.CANCELLED
    assert merged["a"].status_note == store.VANISHED_NOTE
    assert merged["b"].status is Status.SCHEDULED


def test_vanished_event_today_is_not_cancelled():
    # Venues drop tonight's gig from their listing during the day.
    merged = by_id(store.merge([ev("a", day_offset=0)], {"Lido": [ev("b")]}, TODAY))
    assert merged["a"].status is Status.SCHEDULED


def test_reappearing_event_is_restored():
    gone = ev("a", status=Status.CANCELLED, status_note=store.VANISHED_NOTE)
    merged = by_id(store.merge([gone], {"Lido": [ev("a")]}, TODAY))
    assert merged["a"].status is Status.SCHEDULED
    assert merged["a"].status_note is None


def test_failed_venue_is_left_untouched():
    # Gretchen isn't in the scrape results (it failed), so its event must survive as-is.
    merged = by_id(store.merge([ev("g", venue="Gretchen")], {"Lido": [ev("a")]}, TODAY))
    assert merged["g"].status is Status.SCHEDULED


def test_past_events_are_pruned():
    merged = by_id(store.merge([ev("old", day_offset=-1)], {"Lido": [ev("a")]}, TODAY))
    assert "old" not in merged


def test_events_beyond_horizon_are_not_added():
    merged = by_id(store.merge([], {"Lido": [ev("far", day_offset=store.HORIZON_DAYS + 1)]}, TODAY))
    assert "far" not in merged


def test_event_rescheduled_beyond_horizon_is_dropped_not_cancelled():
    merged = by_id(store.merge([ev("a")], {"Lido": [ev("a", day_offset=90)]}, TODAY))
    assert "a" not in merged


def test_round_trip(tmp_path):
    path = tmp_path / "events.json"
    events = [ev("a", status=Status.MOVED, status_note="Verlegt", first_seen=TODAY)]
    store.save(events, "2026-10-20T06:00:00+02:00", path)
    assert store.load(path) == events

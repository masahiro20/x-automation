import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common import JST  # noqa: E402
from post import due_slot  # noqa: E402


def at(h, m):
    return datetime(2026, 9, 29, h, m, tzinfo=JST)


def posted(h, m):
    return {"posted_at": at(h, m).isoformat()}


def test_before_first_slot_is_not_due():
    assert due_slot(at(7, 0), []) is None


def test_inside_window_is_due():
    assert due_slot(at(7, 45), []) == at(7, 30)


def test_late_run_inside_window_is_still_due():
    assert due_slot(at(9, 50), []) == at(7, 30)


def test_late_run_before_next_slot_still_catches_up():
    assert due_slot(at(11, 50), []) == at(7, 30)


def test_last_slot_lasts_until_midnight_only():
    assert due_slot(at(23, 55), []) == at(21, 0)
    assert due_slot(datetime(2026, 9, 30, 0, 10, tzinfo=JST), []) is None


def test_already_posted_in_slot_is_not_due():
    assert due_slot(at(8, 0), [posted(7, 40)]) is None


def test_post_from_previous_slot_does_not_block():
    assert due_slot(at(12, 30), [posted(7, 40)]) == at(12, 15)

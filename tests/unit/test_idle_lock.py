"""Tests for the pure idle-lock logic (app.ui.idle_lock.IdleTracker)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.ui.idle_lock import IdleTracker


def test_disabled_when_threshold_is_zero() -> None:
    tracker = IdleTracker(threshold_minutes=0)
    later = tracker.last_activity + timedelta(hours=10)
    assert tracker.should_lock(now=later) is False


def test_locks_after_threshold_elapses() -> None:
    start = datetime.now(UTC)
    tracker = IdleTracker(threshold_minutes=10, last_activity=start)
    assert tracker.should_lock(now=start + timedelta(minutes=9)) is False
    assert tracker.should_lock(now=start + timedelta(minutes=10)) is True


def test_activity_resets_the_clock() -> None:
    start = datetime.now(UTC)
    tracker = IdleTracker(threshold_minutes=10, last_activity=start)
    tracker.record_activity(now=start + timedelta(minutes=9))
    assert tracker.should_lock(now=start + timedelta(minutes=15)) is False
    assert tracker.should_lock(now=start + timedelta(minutes=20)) is True


def test_already_locked_does_not_re_trigger() -> None:
    start = datetime.now(UTC)
    tracker = IdleTracker(threshold_minutes=10, last_activity=start)
    tracker.lock()
    assert tracker.should_lock(now=start + timedelta(hours=1)) is False


def test_activity_ignored_while_locked() -> None:
    start = datetime.now(UTC)
    tracker = IdleTracker(threshold_minutes=10, last_activity=start)
    tracker.lock()
    tracker.record_activity(now=start + timedelta(minutes=5))
    assert tracker.last_activity == start


def test_unlock_resets_and_clears_lock() -> None:
    start = datetime.now(UTC)
    tracker = IdleTracker(threshold_minutes=10, last_activity=start)
    tracker.lock()
    unlock_time = start + timedelta(hours=1)
    tracker.unlock(now=unlock_time)
    assert tracker.locked is False
    assert tracker.should_lock(now=unlock_time + timedelta(minutes=5)) is False

"""pytest-qt integration test: IdleWatcher actually fires a real Qt timer."""

from __future__ import annotations

from datetime import UTC

from app.ui.idle_lock import IdleWatcher


def test_watcher_emits_locked_after_short_threshold(qtbot):
    # threshold_minutes must be an int in the tracker; drive the underlying
    # tracker's threshold in seconds-equivalent by using a 1-poll-cycle setup:
    # poll every 0 seconds isn't allowed, so instead we shrink the *threshold*
    # by directly setting last_activity far enough in the past that the very
    # first poll tick (poll_seconds later) already crosses it.
    from datetime import datetime, timedelta

    watcher = IdleWatcher(threshold_minutes=1, poll_seconds=1)
    watcher.tracker.last_activity = datetime.now(UTC) - timedelta(minutes=5)
    watcher.start()

    with qtbot.waitSignal(watcher.locked, timeout=3000):
        pass

    assert watcher.tracker.locked is True
    watcher.stop()


def test_watcher_does_nothing_when_disabled(qtbot):
    watcher = IdleWatcher(threshold_minutes=0, poll_seconds=1)
    watcher.start()
    assert not watcher._timer.isActive()
    watcher.stop()

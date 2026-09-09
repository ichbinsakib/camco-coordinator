"""Idle-timeout session lock (spec section 27's "session_idle_minutes" setting).

Split into a pure, easily-testable :class:`IdleTracker` (just "how long since
the last activity, should we lock yet") and a thin Qt wrapper
(:class:`IdleWatcher`) that feeds it real activity events and a real timer -
the same separation used everywhere else in the app between business logic
and the UI layer that drives it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

_ACTIVITY_EVENT_TYPES = frozenset(
    {
        QEvent.Type.MouseMove,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.KeyPress,
        QEvent.Type.Wheel,
        QEvent.Type.TouchBegin,
    }
)


@dataclass(slots=True)
class IdleTracker:
    """Pure idle-time bookkeeping: no Qt, no wall-clock sleeping, easy to unit test."""

    threshold_minutes: int
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    locked: bool = False

    def record_activity(self, *, now: datetime | None = None) -> None:
        """Reset the idle clock. A no-op while already locked - unlocking is explicit."""
        if self.locked:
            return
        self.last_activity = now or datetime.now(UTC)

    def seconds_idle(self, *, now: datetime | None = None) -> float:
        """Seconds since the last recorded activity."""
        current = now or datetime.now(UTC)
        return (current - self.last_activity).total_seconds()

    def should_lock(self, *, now: datetime | None = None) -> bool:
        """True if idle time has exceeded the threshold and we're not already locked."""
        if self.threshold_minutes <= 0 or self.locked:
            return False
        return self.seconds_idle(now=now) >= self.threshold_minutes * 60

    def lock(self) -> None:
        self.locked = True

    def unlock(self, *, now: datetime | None = None) -> None:
        self.locked = False
        self.record_activity(now=now)


class IdleWatcher(QObject):
    """Installs a global event filter and polls an :class:`IdleTracker` on a timer.

    Emits :attr:`locked` once when the idle threshold is crossed. The caller
    (MainWindow) is responsible for showing a lock screen and calling
    :meth:`unlock` once the user re-authenticates.
    """

    locked = Signal()

    def __init__(self, threshold_minutes: int, *, poll_seconds: int = 15, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tracker = IdleTracker(threshold_minutes=threshold_minutes)
        self._timer = QTimer(self)
        self._timer.setInterval(poll_seconds * 1000)
        self._timer.timeout.connect(self._check)

    def start(self) -> None:
        if self.tracker.threshold_minutes > 0:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def unlock(self) -> None:
        self.tracker.unlock()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in _ACTIVITY_EVENT_TYPES:
            self.tracker.record_activity()
        return super().eventFilter(watched, event)

    def _check(self) -> None:
        if self.tracker.should_lock():
            self.tracker.lock()
            self.locked.emit()

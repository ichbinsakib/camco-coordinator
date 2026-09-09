"""Business-day aware date arithmetic.

Manufacturing due dates should not silently assume every day is a work day
(spec rule 53). All lateness/remaining-day calculations that need to respect
the shop calendar should go through here rather than doing raw ``date``
subtraction.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.config.settings import CalendarSettings


def is_business_day(day: date, calendar: CalendarSettings) -> bool:
    """True if ``day`` is a configured work day and not a holiday/shutdown day."""
    if day.weekday() not in calendar.work_days:
        return False
    return day not in calendar.holiday_dates()


def business_days_between(start: date, end: date, calendar: CalendarSettings) -> int:
    """Count business days strictly between two dates (sign matches ``end - start``).

    Falls back to plain calendar-day counting when ``use_business_days`` is
    off, so switching the setting doesn't require touching call sites.
    """
    if not calendar.use_business_days:
        return (end - start).days

    step = 1 if end >= start else -1
    count = 0
    current = start
    while current != end:
        current += timedelta(days=step)
        if is_business_day(current, calendar):
            count += step
    return count


def add_business_days(start: date, days: int, calendar: CalendarSettings) -> date:
    """Return the date ``days`` business days after ``start``."""
    if not calendar.use_business_days:
        return start + timedelta(days=days)

    step = 1 if days >= 0 else -1
    remaining = abs(days)
    current = start
    while remaining > 0:
        current += timedelta(days=step)
        if is_business_day(current, calendar):
            remaining -= 1
    return current

"""Business-day calendar math tests."""

from __future__ import annotations

from datetime import date

from app.config.settings import CalendarSettings
from app.utils.calendar_utils import add_business_days, business_days_between, is_business_day


def test_weekend_is_not_a_business_day() -> None:
    calendar = CalendarSettings()
    saturday = date(2026, 9, 12)
    assert saturday.weekday() == 5
    assert is_business_day(saturday, calendar) is False


def test_configured_holiday_is_not_a_business_day() -> None:
    calendar = CalendarSettings(holidays=["2026-12-25"])
    assert is_business_day(date(2026, 12, 25), calendar) is False


def test_shutdown_range_excludes_all_days_in_range() -> None:
    calendar = CalendarSettings(shutdown_ranges=[["2026-12-24", "2026-12-26"]])
    assert is_business_day(date(2026, 12, 25), calendar) is False


def test_add_business_days_skips_weekend() -> None:
    calendar = CalendarSettings()
    friday = date(2026, 9, 11)
    assert friday.weekday() == 4
    result = add_business_days(friday, 1, calendar)
    assert result == date(2026, 9, 14)  # Monday


def test_business_days_between_matches_add(monkeypatch=None) -> None:
    calendar = CalendarSettings()
    start = date(2026, 9, 8)
    end = add_business_days(start, 5, calendar)
    assert business_days_between(start, end, calendar) == 5


def test_calendar_math_falls_back_to_plain_days_when_disabled() -> None:
    calendar = CalendarSettings(use_business_days=False)
    start = date(2026, 9, 11)
    result = add_business_days(start, 3, calendar)
    assert result == date(2026, 9, 14)

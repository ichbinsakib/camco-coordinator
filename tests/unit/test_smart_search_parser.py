"""Tests for the deterministic keyword parser used by Smart Search.

These test the routing/keyword logic directly against
:func:`app.ai.smart_search.run_smart_search`'s helper pieces where possible
without a database; full end-to-end query execution is covered in
tests/integration/test_ai_smart_search.py.
"""

from __future__ import annotations

from datetime import date

from app.ai.smart_search import _mentions_any, _this_month_range, _this_week_range


def test_mentions_any_case_and_substring() -> None:
    assert _mentions_any("purchase orders are overdue", "overdue")
    assert not _mentions_any("purchase orders are on time", "overdue")


def test_this_month_range_spans_full_month() -> None:
    start, end = _this_month_range(date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)  # 2026 is not a leap year


def test_this_week_range_is_monday_to_sunday() -> None:
    # 2026-09-10 is a Thursday.
    start, end = _this_week_range(date(2026, 9, 10))
    assert start.weekday() == 0
    assert end.weekday() == 6
    assert start <= date(2026, 9, 10) <= end

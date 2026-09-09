"""Edge-case tests for CustomerOrderLine due-date and quantity math."""

from __future__ import annotations

from datetime import date, timedelta

from app.config.constants import OrderStatus
from app.models.orders import CustomerOrderLine


def _line(**kwargs) -> CustomerOrderLine:
    defaults = dict(
        customer_order_id=1, line_number=1, part_id=1,
        quantity_ordered=10, quantity_completed=0, status=OrderStatus.IN_PROGRESS.value,
    )
    defaults.update(kwargs)
    return CustomerOrderLine(**defaults)


def test_due_today_is_not_late() -> None:
    line = _line(due_date=date.today())
    assert line.days_late(date.today()) == 0


def test_due_tomorrow_is_not_late() -> None:
    line = _line(due_date=date.today() + timedelta(days=1))
    assert line.days_late(date.today()) == 0


def test_due_yesterday_is_one_day_late() -> None:
    line = _line(due_date=date.today() - timedelta(days=1))
    assert line.days_late(date.today()) == 1


def test_completed_early_is_not_late_even_if_overdue_by_date() -> None:
    line = _line(due_date=date.today() - timedelta(days=5), status=OrderStatus.COMPLETE.value)
    assert line.days_late(date.today()) == 0


def test_missing_due_date_is_never_late() -> None:
    line = _line(due_date=None)
    assert line.days_late(date.today()) == 0
    assert line.days_until_due(date.today()) is None


def test_quantity_zero_ordered_is_not_complete() -> None:
    line = _line(quantity_ordered=0, quantity_completed=0)
    assert line.is_complete is False
    assert line.quantity_remaining == 0


def test_over_completion_clamps_remaining_to_zero() -> None:
    line = _line(quantity_ordered=10, quantity_completed=15)
    assert line.quantity_remaining == 0
    assert line.is_complete is True


def test_partial_completion_remaining() -> None:
    line = _line(quantity_ordered=100, quantity_completed=40)
    assert line.quantity_remaining == 60
    assert line.is_complete is False

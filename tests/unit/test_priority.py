"""Tests for the automatic priority engine (app.business.priority)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.business.priority import (
    PriorityFactors,
    compute_line_priority,
    priority_band,
    score_priority,
)
from app.config.constants import OrderStatus, Priority
from app.config.settings import PrioritySettings
from app.models.orders import CustomerOrderLine


@pytest.fixture
def priority_settings() -> PrioritySettings:
    return PrioritySettings()


def test_score_increases_with_days_late(priority_settings: PrioritySettings) -> None:
    low = score_priority(PriorityFactors(days_late=1), priority_settings)
    high = score_priority(PriorityFactors(days_late=20), priority_settings)
    assert high > low


def test_days_late_is_capped(priority_settings: PrioritySettings) -> None:
    at_cap = score_priority(
        PriorityFactors(days_late=priority_settings.max_days_late_considered), priority_settings
    )
    beyond_cap = score_priority(
        PriorityFactors(days_late=priority_settings.max_days_late_considered + 500), priority_settings
    )
    assert at_cap == beyond_cap


def test_blocked_and_material_shortage_add_score(priority_settings: PrioritySettings) -> None:
    baseline = score_priority(PriorityFactors(), priority_settings)
    blocked = score_priority(PriorityFactors(is_blocked=True), priority_settings)
    material = score_priority(PriorityFactors(is_waiting_material=True), priority_settings)
    assert blocked > baseline
    assert material > baseline


def test_priority_band_thresholds(priority_settings: PrioritySettings) -> None:
    assert priority_band(priority_settings.critical_score, priority_settings) == Priority.CRITICAL
    assert priority_band(priority_settings.high_score, priority_settings) == Priority.HIGH
    assert priority_band(priority_settings.medium_score, priority_settings) == Priority.MEDIUM
    assert priority_band(0, priority_settings) == Priority.LOW


def _make_line(**kwargs) -> CustomerOrderLine:
    defaults = dict(
        customer_order_id=1,
        line_number=1,
        part_id=1,
        quantity_ordered=10,
        quantity_completed=0,
        status=OrderStatus.IN_PROGRESS.value,
    )
    defaults.update(kwargs)
    return CustomerOrderLine(**defaults)


def test_manual_priority_overrides_computed_score(priority_settings: PrioritySettings) -> None:
    line = _make_line(manual_priority=Priority.LOW.value, due_date=date.today() - timedelta(days=60))
    result = compute_line_priority(line, priority_settings, as_of=date.today(), customer_importance=1)
    assert result == Priority.LOW


def test_invalid_manual_priority_falls_back_to_computed(priority_settings: PrioritySettings) -> None:
    line = _make_line(manual_priority="NOT_A_REAL_PRIORITY", due_date=date.today())
    result = compute_line_priority(line, priority_settings, as_of=date.today(), customer_importance=3)
    assert isinstance(result, Priority)


def test_closed_line_never_scores_as_late(priority_settings: PrioritySettings) -> None:
    line = _make_line(status=OrderStatus.COMPLETE.value, due_date=date.today() - timedelta(days=30))
    assert line.days_late(date.today()) == 0

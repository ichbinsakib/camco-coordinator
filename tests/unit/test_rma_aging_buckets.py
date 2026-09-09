"""Tests for RMA aging-bucket labeling (spec section 17: aging in months)."""

from __future__ import annotations

from app.repositories.rma import aging_bucket_label

_BUCKETS = [1, 3, 6, 12]


def test_zero_to_one_month() -> None:
    assert aging_bucket_label(0.5, _BUCKETS) == "0-1 Months"


def test_one_to_three_months() -> None:
    assert aging_bucket_label(2, _BUCKETS) == "1-3 Months"


def test_boundary_falls_into_next_bucket() -> None:
    assert aging_bucket_label(3, _BUCKETS) == "3-6 Months"


def test_twelve_plus_months() -> None:
    assert aging_bucket_label(18, _BUCKETS) == "12+ Months"


def test_exactly_at_final_edge() -> None:
    assert aging_bucket_label(12, _BUCKETS) == "12+ Months"

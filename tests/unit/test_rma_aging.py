"""RMA aging must be reported in months, per rule 17."""

from __future__ import annotations

from datetime import date, timedelta

from app.models.rma import Rma


def _rma(**kwargs) -> Rma:
    rma = Rma(rma_number="RMA-1", customer_id=1, quantity=1, **kwargs)
    return rma


def test_age_in_months_for_open_rma() -> None:
    received = date.today() - timedelta(days=95)
    rma = _rma(date_received=received)
    assert rma.age_days(date.today()) == 95
    assert rma.age_months(date.today()) == round(95 / 30.0, 1)


def test_age_freezes_after_closure() -> None:
    received = date.today() - timedelta(days=200)
    closed = date.today() - timedelta(days=100)
    rma = _rma(date_received=received, actual_completion_date=closed)
    assert rma.age_days(date.today()) == 100


def test_age_never_negative() -> None:
    rma = _rma(date_received=date.today(), actual_completion_date=date.today())
    assert rma.age_days(date.today()) == 0

"""Integration tests for dashboard KPI aggregation queries."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import OrderStatus
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.repositories.dashboard import get_dashboard_counts


def _seed_line(session: Session, *, due_offset: int, status: str) -> None:
    customer = session.query(Customer).filter_by(code="ACME").one_or_none()
    if customer is None:
        customer = Customer(code="ACME", name="Acme Corp", importance=1)
        session.add(customer)
        session.flush()
    part = Part(part_number=f"PN-{due_offset}-{status}", revision="-")
    session.add(part)
    session.flush()
    order = CustomerOrder(co_number=f"CO-{due_offset}-{status}", customer_id=customer.id)
    session.add(order)
    session.flush()
    line = CustomerOrderLine(
        customer_order_id=order.id,
        line_number=1,
        part_id=part.id,
        quantity_ordered=10,
        quantity_completed=0,
        due_date=date.today() + timedelta(days=due_offset),
        status=status,
    )
    session.add(line)
    session.commit()


def test_past_due_counted_correctly(db_session: Session) -> None:
    _seed_line(db_session, due_offset=-5, status=OrderStatus.IN_PROGRESS.value)
    counts = get_dashboard_counts(db_session)
    assert counts.past_due == 1
    assert counts.open_customer_orders == 1


def test_closed_orders_excluded_from_open_count(db_session: Session) -> None:
    _seed_line(db_session, due_offset=-5, status=OrderStatus.COMPLETE.value)
    counts = get_dashboard_counts(db_session)
    assert counts.open_customer_orders == 0
    assert counts.past_due == 0


def test_due_today_and_due_this_week(db_session: Session) -> None:
    _seed_line(db_session, due_offset=0, status=OrderStatus.IN_PROGRESS.value)
    _seed_line(db_session, due_offset=3, status=OrderStatus.IN_PROGRESS.value)
    counts = get_dashboard_counts(db_session)
    assert counts.due_today == 1
    assert counts.due_this_week == 2


def test_awaiting_material_count(db_session: Session) -> None:
    _seed_line(db_session, due_offset=10, status=OrderStatus.WAITING_MATERIAL.value)
    counts = get_dashboard_counts(db_session)
    assert counts.awaiting_material == 1

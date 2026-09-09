"""Integration tests for ShipmentRepository and on-time-shipment analytics."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.shipping import Shipment, ShipmentLine
from app.repositories.shipping import ShipmentRepository, resolve_range

_counter = 0


def _seed_line(session: Session, due_date: date | None) -> CustomerOrderLine:
    global _counter
    _counter += 1
    customer = Customer(code=f"CUST{_counter}", name=f"Customer {_counter}")
    part = Part(part_number=f"P{_counter}", revision="A")
    session.add_all([customer, part])
    session.flush()
    order = CustomerOrder(co_number=f"CO-{_counter}", customer_id=customer.id)
    session.add(order)
    session.flush()
    line = CustomerOrderLine(
        customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10, due_date=due_date
    )
    session.add(line)
    session.flush()
    return line


def test_on_time_percentage_counts_on_time_and_late(db_session: Session) -> None:
    on_time_line = _seed_line(db_session, due_date=date.today())
    late_line = _seed_line(db_session, due_date=date.today() - timedelta(days=10))

    on_time_shipment = Shipment(shipment_number="S1", ship_date=date.today())
    late_shipment = Shipment(shipment_number="S2", ship_date=date.today())
    db_session.add_all([on_time_shipment, late_shipment])
    db_session.flush()
    db_session.add_all(
        [
            ShipmentLine(shipment_id=on_time_shipment.id, customer_order_line_id=on_time_line.id, quantity_shipped=10),
            ShipmentLine(shipment_id=late_shipment.id, customer_order_line_id=late_line.id, quantity_shipped=10),
        ]
    )
    db_session.commit()

    repo = ShipmentRepository(db_session)
    result = repo.on_time_percentage(date.today() - timedelta(days=30), date.today())
    assert result.on_time_lines == 1
    assert result.late_lines == 1
    assert result.on_time_percent == 50.0


def test_missing_due_date_counts_as_unknown_not_on_time(db_session: Session) -> None:
    line = _seed_line(db_session, due_date=None)
    shipment = Shipment(shipment_number="S3", ship_date=date.today())
    db_session.add(shipment)
    db_session.flush()
    db_session.add(ShipmentLine(shipment_id=shipment.id, customer_order_line_id=line.id, quantity_shipped=10))
    db_session.commit()

    repo = ShipmentRepository(db_session)
    result = repo.on_time_percentage(date.today() - timedelta(days=5), date.today())
    assert result.unknown_lines == 1
    assert result.on_time_lines == 0
    assert result.late_lines == 0


def test_no_shipments_in_range_returns_none_percent(db_session: Session) -> None:
    repo = ShipmentRepository(db_session)
    result = repo.on_time_percentage(date.today() - timedelta(days=5), date.today())
    assert result.on_time_percent is None
    assert result.total_shipped_lines == 0


def test_resolve_range_current_month() -> None:
    as_of = date(2026, 9, 15)
    start, end = resolve_range("Current Month", 0, as_of=as_of)
    assert start == date(2026, 9, 1)
    assert end == as_of


def test_resolve_range_previous_month() -> None:
    as_of = date(2026, 9, 15)
    start, end = resolve_range("Previous Month", -1, as_of=as_of)
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_resolve_range_last_n_months() -> None:
    as_of = date(2026, 9, 15)
    start, end = resolve_range("Last 3 Months", 3, as_of=as_of)
    assert start == date(2026, 6, 15)
    assert end == as_of

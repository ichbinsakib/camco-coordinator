"""Integration tests for app.ai.bottleneck_model."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.bottleneck_model import recurring_bottlenecks
from app.config.constants import ProductionStatus
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder


def _seed_production_order(session: Session, index: int) -> ProductionOrder:
    customer = Customer(code=f"C{index}", name=f"Customer {index}")
    part = Part(part_number=f"P{index}", revision="A")
    session.add_all([customer, part])
    session.flush()
    order = CustomerOrder(co_number=f"CO-{index}", customer_id=customer.id)
    session.add(order)
    session.flush()
    line = CustomerOrderLine(customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10)
    session.add(line)
    session.flush()
    production = ProductionOrder(
        production_number=f"PROD-{index}", customer_order_line_id=line.id, part_id=part.id, planned_quantity=10
    )
    session.add(production)
    session.flush()
    return production


def test_averages_duration_across_completed_operations(db_session: Session) -> None:
    for i, duration in enumerate([5, 7, 9], start=1):
        production = _seed_production_order(db_session, i)
        db_session.add(
            ProductionOperation(
                production_order_id=production.id, sequence=10, operation_name="Mill",
                status=ProductionStatus.COMPLETE.value,
                start_date=date.today() - timedelta(days=duration), actual_completion_date=date.today(),
            )
        )
    db_session.commit()

    results = recurring_bottlenecks(db_session)
    mill = next(r for r in results if r.operation_name == "Mill")
    assert mill.completed_count == 3
    assert mill.average_duration_days == 7.0
    assert mill.max_duration_days == 9


def test_operations_below_min_samples_are_excluded(db_session: Session) -> None:
    production = _seed_production_order(db_session, 1)
    db_session.add(
        ProductionOperation(
            production_order_id=production.id, sequence=10, operation_name="OnceOnly",
            status=ProductionStatus.COMPLETE.value,
            start_date=date.today() - timedelta(days=3), actual_completion_date=date.today(),
        )
    )
    db_session.commit()

    results = recurring_bottlenecks(db_session, min_samples=2)
    assert not any(r.operation_name == "OnceOnly" for r in results)


def test_currently_stuck_operations_are_counted_separately(db_session: Session) -> None:
    for i, duration in enumerate([4, 6], start=1):
        production = _seed_production_order(db_session, i)
        db_session.add(
            ProductionOperation(
                production_order_id=production.id, sequence=10, operation_name="Deburr",
                status=ProductionStatus.COMPLETE.value,
                start_date=date.today() - timedelta(days=duration), actual_completion_date=date.today(),
            )
        )
    stuck_production = _seed_production_order(db_session, 99)
    db_session.add(
        ProductionOperation(
            production_order_id=stuck_production.id, sequence=10, operation_name="Deburr",
            status=ProductionStatus.RUNNING.value, status_since=date.today() - timedelta(days=8),
        )
    )
    db_session.commit()

    results = recurring_bottlenecks(db_session)
    deburr = next(r for r in results if r.operation_name == "Deburr")
    assert deburr.completed_count == 2
    assert deburr.currently_stuck_count == 1


def test_results_sorted_by_average_duration_descending(db_session: Session) -> None:
    for i, (name, duration) in enumerate([("Fast", 2), ("Fast", 3), ("Slow", 20), ("Slow", 22)], start=1):
        production = _seed_production_order(db_session, i)
        db_session.add(
            ProductionOperation(
                production_order_id=production.id, sequence=10, operation_name=name,
                status=ProductionStatus.COMPLETE.value,
                start_date=date.today() - timedelta(days=duration), actual_completion_date=date.today(),
            )
        )
    db_session.commit()

    results = recurring_bottlenecks(db_session)
    assert results[0].operation_name == "Slow"

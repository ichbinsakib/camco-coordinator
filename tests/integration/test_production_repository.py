"""Integration tests for ProductionOrderRepository."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import ProductionStatus
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder
from app.repositories.production import ProductionOrderFilters, ProductionOrderRepository


def _seed_production_order(session: Session) -> ProductionOrder:
    customer = Customer(code="ACME", name="Acme Corp")
    part = Part(part_number="P100", revision="A")
    session.add_all([customer, part])
    session.flush()
    order = CustomerOrder(co_number="CO-9001", customer_id=customer.id)
    session.add(order)
    session.flush()
    line = CustomerOrderLine(
        customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=50
    )
    session.add(line)
    session.flush()
    production = ProductionOrder(
        production_number="PROD-1", customer_order_line_id=line.id, part_id=part.id, planned_quantity=50
    )
    session.add(production)
    session.flush()
    return production


def test_current_operation_is_first_incomplete_step(db_session: Session) -> None:
    production = _seed_production_order(db_session)
    db_session.add_all(
        [
            ProductionOperation(
                production_order_id=production.id, sequence=10, operation_name="Mill",
                status=ProductionStatus.COMPLETE.value,
            ),
            ProductionOperation(
                production_order_id=production.id, sequence=20, operation_name="Deburr",
                status=ProductionStatus.RUNNING.value, status_since=date.today() - timedelta(days=4),
            ),
        ]
    )
    db_session.commit()

    repo = ProductionOrderRepository(db_session)
    rows, total = repo.search(ProductionOrderFilters(open_only=False))
    assert total == 1
    assert rows[0].current_operation.operation_name == "Deburr"
    assert rows[0].days_in_status == 4


def test_all_complete_operations_means_no_current_operation(db_session: Session) -> None:
    production = _seed_production_order(db_session)
    db_session.add(
        ProductionOperation(
            production_order_id=production.id, sequence=10, operation_name="Mill",
            status=ProductionStatus.COMPLETE.value,
        )
    )
    db_session.commit()

    repo = ProductionOrderRepository(db_session)
    rows, _total = repo.search(ProductionOrderFilters(open_only=False))
    assert rows[0].current_operation is None
    assert rows[0].days_in_status == 0


def test_stagnant_operations_respects_threshold(db_session: Session) -> None:
    production = _seed_production_order(db_session)
    db_session.add_all(
        [
            ProductionOperation(
                production_order_id=production.id, sequence=10, operation_name="Stuck",
                status=ProductionStatus.WAITING_TOOLING.value, status_since=date.today() - timedelta(days=15),
            ),
        ]
    )
    db_session.commit()

    repo = ProductionOrderRepository(db_session)
    assert len(repo.stagnant_operations(10)) == 1
    assert len(repo.stagnant_operations(20)) == 0

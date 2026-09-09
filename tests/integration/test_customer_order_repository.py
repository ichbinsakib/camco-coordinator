"""Integration tests for CustomerOrderRepository line search and get-or-create."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import OrderStatus
from app.config.settings import PrioritySettings
from app.models.core import Customer, Part
from app.models.orders import CustomerOrderLine
from app.repositories.customer_orders import (
    CustomerOrderRepository,
    OrderLineFilters,
    get_or_create_order,
)


def _seed(session: Session) -> tuple[Customer, Part]:
    customer = Customer(code="ACME", name="Acme Corp", importance=1)
    part = Part(part_number="24514", revision="A")
    session.add_all([customer, part])
    session.flush()
    return customer, part


def test_get_or_create_order_is_idempotent(db_session: Session) -> None:
    customer, _ = _seed(db_session)
    first = get_or_create_order(db_session, "CO-1001", customer.id)
    second = get_or_create_order(db_session, "CO-1001", customer.id)
    assert first.id == second.id


def test_search_lines_filters_by_status(db_session: Session) -> None:
    customer, part = _seed(db_session)
    order = get_or_create_order(db_session, "CO-2001", customer.id)
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id,
            line_number=1,
            part_id=part.id,
            quantity_ordered=10,
            due_date=date.today() - timedelta(days=2),
            status=OrderStatus.WAITING_MATERIAL.value,
        )
    )
    db_session.commit()

    repo = CustomerOrderRepository(db_session)
    rows, total = repo.search_lines(
        OrderLineFilters(status=OrderStatus.WAITING_MATERIAL.value, open_only=False),
        PrioritySettings(),
    )
    assert total == 1
    assert rows[0].co_number == "CO-2001"
    assert rows[0].days_late == 2


def test_search_lines_open_only_excludes_complete(db_session: Session) -> None:
    customer, part = _seed(db_session)
    order = get_or_create_order(db_session, "CO-3001", customer.id)
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id,
            line_number=1,
            part_id=part.id,
            quantity_ordered=10,
            quantity_completed=10,
            status=OrderStatus.COMPLETE.value,
        )
    )
    db_session.commit()

    repo = CustomerOrderRepository(db_session)
    _rows, total = repo.search_lines(OrderLineFilters(open_only=True), PrioritySettings())
    assert total == 0


def test_search_lines_text_matches_co_number_and_part(db_session: Session) -> None:
    customer, part = _seed(db_session)
    order = get_or_create_order(db_session, "CO-4001", customer.id)
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id,
            line_number=1,
            part_id=part.id,
            quantity_ordered=5,
            status=OrderStatus.IN_PROGRESS.value,
        )
    )
    db_session.commit()

    repo = CustomerOrderRepository(db_session)
    _rows, total = repo.search_lines(
        OrderLineFilters(text="24514", open_only=False), PrioritySettings()
    )
    assert total == 1

"""Integration tests for app.ai.smart_search (end-to-end query execution)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.smart_search import run_smart_search
from app.config.constants import FollowUpStatus, OrderStatus, PurchaseOrderStatus
from app.config.settings import AppSettings
from app.models.core import Customer, Part, Vendor
from app.models.followup import FollowUp
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine


def _seed_customer_and_part(session: Session) -> tuple[Customer, Part]:
    customer = Customer(code="ACME", name="Acme Corp", importance=1)
    part = Part(part_number="P1", revision="A")
    session.add_all([customer, part])
    session.flush()
    return customer, part


def test_waiting_for_material_routes_to_customer_order_lines(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session)
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10,
            status=OrderStatus.WAITING_MATERIAL.value,
        )
    )
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=2, part_id=part.id, quantity_ordered=5,
            status=OrderStatus.IN_PROGRESS.value,
        )
    )
    db_session.commit()

    result = run_smart_search(db_session, "Which parts are waiting for material?", AppSettings())
    assert result.target == "customer_order_lines"
    assert len(result.rows) == 1
    assert result.rows[0].line.status == OrderStatus.WAITING_MATERIAL.value


def test_overdue_purchase_orders_routes_to_purchase_order_lines(db_session: Session) -> None:
    vendor = Vendor(code="V1", name="Vendor One")
    db_session.add(vendor)
    db_session.flush()
    po = PurchaseOrder(po_number="PO-1", vendor_id=vendor.id)
    db_session.add(po)
    db_session.flush()
    db_session.add_all(
        [
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=1, description="Late", quantity_ordered=10,
                required_date=date.today() - timedelta(days=10), status=PurchaseOrderStatus.OPEN.value,
            ),
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=2, description="On Time", quantity_ordered=10,
                required_date=date.today() + timedelta(days=10), status=PurchaseOrderStatus.OPEN.value,
            ),
        ]
    )
    db_session.commit()

    result = run_smart_search(db_session, "Which POs are overdue?", AppSettings())
    assert result.target == "purchase_order_lines"
    assert len(result.rows) == 1
    assert result.rows[0].line.description == "Late"


def test_open_follow_ups_query(db_session: Session) -> None:
    db_session.add_all(
        [
            FollowUp(subject="Call vendor", status=FollowUpStatus.OPEN.value),
            FollowUp(subject="Done already", status=FollowUpStatus.COMPLETED.value),
        ]
    )
    db_session.commit()

    result = run_smart_search(db_session, "show me open follow ups", AppSettings())
    assert result.target == "follow_ups"
    assert len(result.rows) == 1


def test_likely_to_be_late_uses_risk_model(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session)
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    # Currently blocked + already past due -> high rule-based risk score.
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10,
            due_date=date.today() - timedelta(days=15), status=OrderStatus.WAITING_MATERIAL.value,
        )
    )
    db_session.commit()

    result = run_smart_search(db_session, "customer orders likely to be late", AppSettings())
    assert result.target == "customer_order_lines"
    assert "risk" in result.interpretation.lower()


def test_interpretation_is_always_present(db_session: Session) -> None:
    result = run_smart_search(db_session, "anything open", AppSettings())
    assert result.interpretation
    assert result.target == "customer_order_lines"

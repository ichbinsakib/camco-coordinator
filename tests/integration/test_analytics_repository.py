"""Integration tests for app.repositories.analytics."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import OrderStatus, ProductionStatus, PurchaseOrderStatus
from app.config.settings import RmaSettings
from app.models.core import Customer, Part, Vendor
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.models.rma import Rma
from app.repositories.analytics import (
    bottleneck_operations,
    orders_by_status,
    past_due_trend,
    production_workload_by_department,
    rma_aging_distribution,
    vendor_performance,
)


def _seed_customer_and_part(session: Session, suffix: str) -> tuple[Customer, Part]:
    customer = Customer(code=f"C{suffix}", name=f"Customer {suffix}")
    part = Part(part_number=f"P{suffix}", revision="A")
    session.add_all([customer, part])
    session.flush()
    return customer, part


def test_orders_by_status_groups_correctly(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session, "1")
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add_all(
        [
            CustomerOrderLine(customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=1, status=OrderStatus.IN_PROGRESS.value),
            CustomerOrderLine(customer_order_id=order.id, line_number=2, part_id=part.id, quantity_ordered=1, status=OrderStatus.IN_PROGRESS.value),
            CustomerOrderLine(customer_order_id=order.id, line_number=3, part_id=part.id, quantity_ordered=1, status=OrderStatus.ON_HOLD.value),
        ]
    )
    db_session.commit()

    counts = {row.label: row.count for row in orders_by_status(db_session)}
    assert counts[OrderStatus.IN_PROGRESS.value] == 2
    assert counts[OrderStatus.ON_HOLD.value] == 1


def test_past_due_trend_buckets_by_week(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session, "2")
    order = CustomerOrder(co_number="CO-2", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=1,
            due_date=date.today() - timedelta(days=10), status=OrderStatus.IN_PROGRESS.value,
        )
    )
    db_session.commit()

    result = {row.label: row.count for row in past_due_trend(db_session)}
    assert result["1-2wk"] == 1


def test_production_workload_by_department(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session, "3")
    order = CustomerOrder(co_number="CO-3", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    line = CustomerOrderLine(customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=1)
    db_session.add(line)
    db_session.flush()
    prod = ProductionOrder(production_number="PROD-1", customer_order_line_id=line.id, part_id=part.id, planned_quantity=1)
    db_session.add(prod)
    db_session.flush()
    db_session.add(
        ProductionOperation(
            production_order_id=prod.id, sequence=10, operation_name="Mill", department="PRODUCTION",
            status=ProductionStatus.RUNNING.value,
        )
    )
    db_session.commit()

    result = {row.label: row.count for row in production_workload_by_department(db_session)}
    assert result["PRODUCTION"] == 1


def test_vendor_performance_computes_on_time_percent(db_session: Session) -> None:
    vendor = Vendor(code="V1", name="Vendor One")
    db_session.add(vendor)
    db_session.flush()
    po = PurchaseOrder(po_number="PO-1", vendor_id=vendor.id)
    db_session.add(po)
    db_session.flush()
    db_session.add_all(
        [
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=1, quantity_ordered=1, quantity_received=1,
                required_date=date.today() - timedelta(days=10), actual_receipt_date=date.today() - timedelta(days=11),
                status=PurchaseOrderStatus.RECEIVED.value,
            ),
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=2, quantity_ordered=1, quantity_received=1,
                required_date=date.today() - timedelta(days=10), actual_receipt_date=date.today() - timedelta(days=5),
                status=PurchaseOrderStatus.RECEIVED.value,
            ),
        ]
    )
    db_session.commit()

    results = vendor_performance(db_session)
    assert len(results) == 1
    assert results[0].total_lines == 2
    assert results[0].late_lines == 1
    assert results[0].on_time_percent == 50.0


def test_rma_aging_distribution_uses_configured_buckets(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session, "4")
    db_session.add(
        Rma(rma_number="RMA-1", customer_id=customer.id, part_id=part.id, quantity=1, date_received=date.today() - timedelta(days=40))
    )
    db_session.commit()

    result = {row.label: row.count for row in rma_aging_distribution(db_session, RmaSettings())}
    assert result["1-3 Months"] == 1


def test_bottleneck_operations_counts_current_operation_names(db_session: Session) -> None:
    customer, part = _seed_customer_and_part(db_session, "5")
    order = CustomerOrder(co_number="CO-5", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    line = CustomerOrderLine(customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=1)
    db_session.add(line)
    db_session.flush()
    prod = ProductionOrder(production_number="PROD-5", customer_order_line_id=line.id, part_id=part.id, planned_quantity=1)
    db_session.add(prod)
    db_session.flush()
    db_session.add(
        ProductionOperation(production_order_id=prod.id, sequence=10, operation_name="Deburr", status=ProductionStatus.RUNNING.value)
    )
    db_session.commit()

    result = {row.label: row.count for row in bottleneck_operations(db_session)}
    assert result.get("Deburr") == 1

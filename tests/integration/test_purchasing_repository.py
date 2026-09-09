"""Integration tests for PurchaseOrderRepository."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import PurchaseOrderStatus
from app.models.core import Vendor
from app.models.purchasing import PurchaseOrderLine
from app.repositories.purchasing import (
    PurchaseLineFilters,
    PurchaseOrderRepository,
    get_or_create_po,
)


def _seed_vendor(session: Session) -> Vendor:
    vendor = Vendor(code="VEN1", name="Vendor One")
    session.add(vendor)
    session.flush()
    return vendor


def test_get_or_create_po_is_idempotent(db_session: Session) -> None:
    vendor = _seed_vendor(db_session)
    first = get_or_create_po(db_session, "PO-1001", vendor.id)
    second = get_or_create_po(db_session, "PO-1001", vendor.id)
    assert first.id == second.id


def test_late_only_filters_correctly(db_session: Session) -> None:
    vendor = _seed_vendor(db_session)
    po = get_or_create_po(db_session, "PO-2001", vendor.id)
    db_session.add_all(
        [
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=1, description="Steel",
                quantity_ordered=10, required_date=date.today() - timedelta(days=5),
                status=PurchaseOrderStatus.OPEN.value,
            ),
            PurchaseOrderLine(
                purchase_order_id=po.id, line_number=2, description="Aluminum",
                quantity_ordered=10, required_date=date.today() + timedelta(days=5),
                status=PurchaseOrderStatus.OPEN.value,
            ),
        ]
    )
    db_session.commit()

    repo = PurchaseOrderRepository(db_session)
    rows, total = repo.search_lines(PurchaseLineFilters(late_only=True, open_only=False))
    assert total == 2  # total count is unfiltered by late_only (applied post-query)
    assert len(rows) == 1
    assert rows[0].line.description == "Steel"
    assert rows[0].days_late == 5


def test_received_line_is_never_late(db_session: Session) -> None:
    vendor = _seed_vendor(db_session)
    po = get_or_create_po(db_session, "PO-3001", vendor.id)
    db_session.add(
        PurchaseOrderLine(
            purchase_order_id=po.id, line_number=1, description="Steel",
            quantity_ordered=10, quantity_received=10,
            required_date=date.today() - timedelta(days=20),
            status=PurchaseOrderStatus.RECEIVED.value,
        )
    )
    db_session.commit()

    repo = PurchaseOrderRepository(db_session)
    rows, _total = repo.search_lines(PurchaseLineFilters(open_only=False))
    assert rows[0].days_late == 0
    assert rows[0].quantity_remaining == 0

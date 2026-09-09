"""Read-only queries backing the coordinator dashboard KPI cards.

Kept separate from the CRUD repositories because these are aggregate/derived
queries specific to one screen rather than persistence for one entity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.constants import (
    CLOSED_ORDER_STATUSES,
    CLOSED_PO_STATUSES,
    CLOSED_RMA_STATUSES,
    FollowUpStatus,
    OrderStatus,
)
from app.models.followup import FollowUp
from app.models.orders import CustomerOrderLine
from app.models.purchasing import PurchaseOrderLine
from app.models.rma import Rma


@dataclass(slots=True)
class DashboardCounts:
    """Snapshot of KPI counts shown on the dashboard cards."""

    open_customer_orders: int = 0
    past_due: int = 0
    due_today: int = 0
    due_this_week: int = 0
    late_purchase_orders: int = 0
    awaiting_material: int = 0
    open_rmas: int = 0
    open_follow_ups: int = 0


def get_dashboard_counts(session: Session, as_of: date | None = None) -> DashboardCounts:
    """Compute all dashboard KPI counts in a handful of aggregate queries."""
    today = as_of or date.today()
    week_end = today + timedelta(days=7)
    closed_values = [s.value for s in CLOSED_ORDER_STATUSES]

    open_lines_stmt = select(func.count()).select_from(CustomerOrderLine).where(
        CustomerOrderLine.status.notin_(closed_values)
    )
    past_due_stmt = open_lines_stmt.where(CustomerOrderLine.due_date < today)
    due_today_stmt = open_lines_stmt.where(CustomerOrderLine.due_date == today)
    due_week_stmt = open_lines_stmt.where(
        CustomerOrderLine.due_date >= today, CustomerOrderLine.due_date <= week_end
    )
    awaiting_material_stmt = open_lines_stmt.where(
        CustomerOrderLine.status == OrderStatus.WAITING_MATERIAL.value
    )

    closed_po_values = [s.value for s in CLOSED_PO_STATUSES]
    late_po_stmt = (
        select(func.count())
        .select_from(PurchaseOrderLine)
        .where(
            PurchaseOrderLine.status.notin_(closed_po_values),
            func.coalesce(PurchaseOrderLine.promised_date, PurchaseOrderLine.required_date) < today,
        )
    )

    closed_rma_values = [s.value for s in CLOSED_RMA_STATUSES]
    open_rma_stmt = select(func.count()).select_from(Rma).where(Rma.status.notin_(closed_rma_values))

    closed_followup_values = [FollowUpStatus.COMPLETED.value, FollowUpStatus.CANCELLED.value]
    open_followup_stmt = (
        select(func.count()).select_from(FollowUp).where(FollowUp.status.notin_(closed_followup_values))
    )

    return DashboardCounts(
        open_customer_orders=int(session.scalar(open_lines_stmt) or 0),
        past_due=int(session.scalar(past_due_stmt) or 0),
        due_today=int(session.scalar(due_today_stmt) or 0),
        due_this_week=int(session.scalar(due_week_stmt) or 0),
        late_purchase_orders=int(session.scalar(late_po_stmt) or 0),
        awaiting_material=int(session.scalar(awaiting_material_stmt) or 0),
        open_rmas=int(session.scalar(open_rma_stmt) or 0),
        open_follow_ups=int(session.scalar(open_followup_stmt) or 0),
    )

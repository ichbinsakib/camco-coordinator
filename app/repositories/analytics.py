"""Aggregate queries backing the Analytics page's charts.

Every function here answers one specific operational question (spec rule 46:
"every visualization must answer an operational question") and returns plain
data structures - no Qt, no chart objects - so the same queries can back a
future report export without depending on the chart widgets.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config.constants import (
    CLOSED_ORDER_STATUSES,
    CLOSED_PO_STATUSES,
    CLOSED_PRODUCTION_STATUSES,
    CLOSED_RMA_STATUSES,
)
from app.config.settings import RmaSettings
from app.models.orders import CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.models.rma import Rma
from app.repositories.rma import aging_bucket_label


@dataclass(slots=True)
class LabeledCount:
    """A generic (label, count) pair used by every bar/pie chart."""

    label: str
    count: int


def orders_by_status(session: Session) -> list[LabeledCount]:
    """Count of open customer order lines per status."""
    rows = session.execute(
        select(CustomerOrderLine.status, func.count())
        .group_by(CustomerOrderLine.status)
        .order_by(func.count().desc())
    ).all()
    return [LabeledCount(status, count) for status, count in rows]


def past_due_trend(session: Session, *, weeks: int = 8, as_of: date | None = None) -> list[LabeledCount]:
    """How many order lines were/are past due, sampled at each week boundary.

    A "trend" over already-completed history isn't reconstructable from
    current state alone (we don't retroactively know what was late three
    weeks ago), so this reports the *current* past-due count bucketed by how
    many weeks overdue each line is - which is what a coordinator actually
    needs: is the backlog concentrated in recently-missed dates or old ones.
    """
    as_of = as_of or date.today()
    closed_values = [s.value for s in CLOSED_ORDER_STATUSES]
    lines = session.scalars(
        select(CustomerOrderLine).where(
            CustomerOrderLine.status.notin_(closed_values), CustomerOrderLine.due_date < as_of
        )
    )
    buckets: Counter[str] = Counter()
    for line in lines:
        days_late = (as_of - line.due_date).days
        week_bucket = min(days_late // 7, weeks - 1)
        label = f"{week_bucket}-{week_bucket + 1}wk" if week_bucket < weeks - 1 else f"{weeks - 1}wk+"
        buckets[label] += 1
    ordered_labels = [f"{i}-{i + 1}wk" for i in range(weeks - 1)] + [f"{weeks - 1}wk+"]
    return [LabeledCount(label, buckets.get(label, 0)) for label in ordered_labels]


def production_workload_by_department(session: Session) -> list[LabeledCount]:
    """Open (not-complete) routing operations grouped by department."""
    closed_values = [s.value for s in CLOSED_PRODUCTION_STATUSES]
    rows = session.execute(
        select(
            func.coalesce(ProductionOperation.department, "(unassigned)"), func.count()
        )
        .where(ProductionOperation.status.notin_(closed_values))
        .group_by(ProductionOperation.department)
        .order_by(func.count().desc())
    ).all()
    return [LabeledCount(dept, count) for dept, count in rows]


@dataclass(slots=True)
class VendorPerformanceRow:
    """One vendor's on-time performance, computed from PO line history."""

    vendor_name: str
    total_lines: int
    late_lines: int
    on_time_percent: float | None


def vendor_performance(session: Session) -> list[VendorPerformanceRow]:
    """On-time percentage per vendor, based on received purchase order lines."""
    closed_values = [s.value for s in CLOSED_PO_STATUSES]
    results: dict[str, list[PurchaseOrderLine]] = {}
    lines = session.scalars(
        select(PurchaseOrderLine).join(PurchaseOrderLine.purchase_order).join(PurchaseOrder.vendor)
    )
    for line in lines:
        if line.status not in closed_values:
            continue
        vendor_name = line.purchase_order.vendor.name
        results.setdefault(vendor_name, []).append(line)

    output: list[VendorPerformanceRow] = []
    for vendor_name, vendor_lines in results.items():
        total = len(vendor_lines)
        late = sum(1 for line in vendor_lines if _was_received_late(line))
        on_time_percent = round(100.0 * (total - late) / total, 1) if total else None
        output.append(VendorPerformanceRow(vendor_name, total, late, on_time_percent))
    output.sort(key=lambda r: (r.on_time_percent is None, r.on_time_percent or 0))
    return output


def _was_received_late(line: PurchaseOrderLine) -> bool:
    reference = line.promised_date or line.required_date
    if reference is None or line.actual_receipt_date is None:
        return False
    return line.actual_receipt_date > reference


def rma_aging_distribution(session: Session, rma_settings: RmaSettings, *, as_of: date | None = None) -> list[LabeledCount]:
    """Count of open RMAs per aging bucket."""
    as_of = as_of or date.today()
    closed_values = [s.value for s in CLOSED_RMA_STATUSES]
    rmas = session.scalars(select(Rma).where(Rma.status.notin_(closed_values)))
    buckets: Counter[str] = Counter()
    for rma in rmas:
        buckets[aging_bucket_label(rma.age_months(as_of), rma_settings.aging_buckets_months)] += 1
    return [LabeledCount(label, count) for label, count in buckets.items()]


def monthly_order_trend(session: Session, *, months: int = 6, as_of: date | None = None) -> list[LabeledCount]:
    """Customer order lines created per month, most recent ``months`` months."""
    as_of = as_of or date.today()
    start = as_of.replace(day=1) - timedelta(days=32 * (months - 1))
    start = start.replace(day=1)
    lines = session.scalars(select(CustomerOrderLine).where(CustomerOrderLine.created_at >= start))
    buckets: Counter[str] = Counter()
    for line in lines:
        buckets[line.created_at.strftime("%Y-%m")] += 1
    labels = []
    cursor = start
    for _ in range(months):
        labels.append(cursor.strftime("%Y-%m"))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return [LabeledCount(label, buckets.get(label, 0)) for label in labels]


def bottleneck_operations(session: Session, *, top_n: int = 5) -> list[LabeledCount]:
    """The routing operation *names* most often the current bottleneck.

    Counts operation names appearing as the first not-yet-complete step
    across all open production orders - a name showing up often is where
    work keeps piling up.
    """
    orders = session.scalars(
        select(ProductionOrder).options(joinedload(ProductionOrder.operations))
    ).unique()
    buckets: Counter[str] = Counter()
    for order in orders:
        current = order.current_operation
        if current:
            buckets[current.operation_name] += 1
    return [LabeledCount(name, count) for name, count in buckets.most_common(top_n)]

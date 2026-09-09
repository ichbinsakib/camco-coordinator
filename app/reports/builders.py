"""Report builders: one function per report type, each returning a :class:`Report`.

Every builder reuses the same repositories and business rules the live UI
pages use (priority engine, dashboard counts, aging buckets, on-time %) - a
report can never show a different answer than the screen it's summarizing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constants import OrderStatus, Priority
from app.config.settings import AppSettings
from app.models.followup import FollowUp
from app.reports.model import Report, ReportSection
from app.repositories.analytics import rma_aging_distribution, vendor_performance
from app.repositories.customer_orders import CustomerOrderRepository, OrderLineFilters
from app.repositories.dashboard import get_dashboard_counts
from app.repositories.purchasing import PurchaseLineFilters, PurchaseOrderRepository
from app.repositories.rma import RmaFilters, RmaRepository
from app.repositories.shipping import STANDARD_RANGES, ShipmentRepository, resolve_range

_DATE_FMT = "%m/%d/%Y"


def _fmt_date(value: date | None) -> str:
    return value.strftime(_DATE_FMT) if value else ""


def _fmt_num(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:g}"


def build_daily_coordinator_report(
    session: Session, settings: AppSettings, *, generated_by: str, as_of: date | None = None
) -> Report:
    """The "what needs my attention today" report (spec section 23)."""
    as_of = as_of or date.today()
    order_repo = CustomerOrderRepository(session)
    po_repo = PurchaseOrderRepository(session)

    past_due_rows, _ = order_repo.search_lines(
        OrderLineFilters(open_only=True), settings.priority, as_of=as_of, limit=500
    )
    past_due_rows = [r for r in past_due_rows if r.days_late > 0]
    critical_rows = [r for r in past_due_rows if r.priority == Priority.CRITICAL]

    due_today_rows, _ = order_repo.search_lines(
        OrderLineFilters(open_only=True, due_before=as_of, due_after=as_of), settings.priority, as_of=as_of, limit=500
    )
    due_week_rows, _ = order_repo.search_lines(
        OrderLineFilters(open_only=True, due_after=as_of, due_before=as_of + timedelta(days=7)),
        settings.priority,
        as_of=as_of,
        limit=500,
    )
    material_rows, _ = order_repo.search_lines(
        OrderLineFilters(status=OrderStatus.WAITING_MATERIAL.value, open_only=True), settings.priority, as_of=as_of, limit=500
    )
    late_po_rows, _ = po_repo.search_lines(PurchaseLineFilters(late_only=True, open_only=True), as_of=as_of, limit=500)

    follow_ups = list(
        session.scalars(
            select(FollowUp).where(FollowUp.status.in_(["OPEN", "WAITING"]))
        )
    )
    overdue_follow_ups = [f for f in follow_ups if f.is_overdue(as_of)]

    sections = [
        ReportSection(
            "Critical Priority Issues",
            ["CO", "Customer", "Part", "Due Date", "Days Late", "Status"],
            [
                [r.co_number, r.customer_name, r.part_display, _fmt_date(r.line.due_date), str(r.days_late), r.line.status]
                for r in critical_rows
            ],
        ),
        ReportSection(
            "Past Due Orders",
            ["CO", "Customer", "Part", "Due Date", "Days Late", "Priority"],
            [
                [r.co_number, r.customer_name, r.part_display, _fmt_date(r.line.due_date), str(r.days_late), r.priority.value]
                for r in past_due_rows
            ],
        ),
        ReportSection(
            "Due Today",
            ["CO", "Customer", "Part", "Status"],
            [[r.co_number, r.customer_name, r.part_display, r.line.status] for r in due_today_rows],
        ),
        ReportSection(
            "Due This Week",
            ["CO", "Customer", "Part", "Due Date", "Status"],
            [[r.co_number, r.customer_name, r.part_display, _fmt_date(r.line.due_date), r.line.status] for r in due_week_rows],
        ),
        ReportSection(
            "Material Shortages",
            ["CO", "Customer", "Part", "Due Date"],
            [[r.co_number, r.customer_name, r.part_display, _fmt_date(r.line.due_date)] for r in material_rows],
        ),
        ReportSection(
            "Late Purchase Orders",
            ["PO", "Vendor", "Part", "Days Late", "Buyer"],
            [
                [r.po_number, r.vendor_name, r.part_display, str(r.days_late), r.line.purchase_order.buyer or ""]
                for r in late_po_rows
            ],
        ),
        ReportSection(
            "Overdue Follow-Ups",
            ["Subject", "Due Date", "Department"],
            [[f.subject, _fmt_date(f.due_date), f.department or ""] for f in overdue_follow_ups],
        ),
    ]
    return Report(
        title="Daily Coordinator Report",
        subtitle=f"As of {as_of.strftime(_DATE_FMT)}",
        generated_at=datetime.now(UTC),
        generated_by=generated_by,
        sections=sections,
    )


def build_customer_order_report(session: Session, settings: AppSettings, *, generated_by: str) -> Report:
    """Every open customer order line, spec section 13's fields, in one export."""
    repo = CustomerOrderRepository(session)
    rows, _total = repo.search_lines(OrderLineFilters(open_only=True), settings.priority, limit=5000)
    section = ReportSection(
        "Open Customer Order Lines",
        ["CO", "Customer", "Part", "Qty Ordered", "Qty Completed", "Qty Remaining", "Due Date", "Days Late", "Status", "Priority"],
        [
            [
                r.co_number, r.customer_name, r.part_display,
                _fmt_num(r.line.quantity_ordered), _fmt_num(r.line.quantity_completed), _fmt_num(r.quantity_remaining),
                _fmt_date(r.line.due_date), str(r.days_late) if r.days_late else "", r.line.status, r.priority.value,
            ]
            for r in rows
        ],
    )
    return Report(
        title="Customer Order Report", generated_at=datetime.now(UTC), generated_by=generated_by, sections=[section]
    )


def build_vendor_performance_report(session: Session, settings: AppSettings, *, generated_by: str) -> Report:
    """On-time receipt percentage per vendor (spec section 15/23)."""
    performance = vendor_performance(session)
    section = ReportSection(
        "Vendor On-Time Performance",
        ["Vendor", "Total Received Lines", "Late Lines", "On-Time %"],
        [
            [row.vendor_name, str(row.total_lines), str(row.late_lines), f"{row.on_time_percent}%" if row.on_time_percent is not None else "N/A"]
            for row in performance
        ],
    )
    return Report(
        title="Vendor Performance Report", generated_at=datetime.now(UTC), generated_by=generated_by, sections=[section]
    )


def build_on_time_shipment_report(
    session: Session, settings: AppSettings, *, generated_by: str, range_label: str = "Last 12 Months"
) -> Report:
    """On-time-shipment % for the selected historical range (spec section 16)."""
    months = dict(STANDARD_RANGES).get(range_label, 12)
    start, end = resolve_range(range_label, months)
    result = ShipmentRepository(session).on_time_percentage(
        start, end, grace_days=settings.shipping.on_time_grace_days, range_label=range_label
    )
    section = ReportSection(
        f"On-Time Shipment Summary ({range_label})",
        ["Metric", "Value"],
        [
            ["Date Range", f"{_fmt_date(start)} - {_fmt_date(end)}"],
            ["Total Shipped Lines", str(result.total_shipped_lines)],
            ["On-Time Lines", str(result.on_time_lines)],
            ["Late Lines", str(result.late_lines)],
            ["Unknown (no due date)", str(result.unknown_lines)],
            ["On-Time %", f"{result.on_time_percent}%" if result.on_time_percent is not None else "N/A"],
        ],
    )
    return Report(
        title="On-Time Shipment Report", generated_at=datetime.now(UTC), generated_by=generated_by, sections=[section]
    )


def build_rma_aging_report(session: Session, settings: AppSettings, *, generated_by: str) -> Report:
    """RMA count per aging bucket, plus the full open-RMA detail list (spec section 17)."""
    distribution = rma_aging_distribution(session, settings.rma)
    rma_repo = RmaRepository(session)
    detail_rows, _total = rma_repo.search(RmaFilters(open_only=True), settings.rma, limit=2000)

    summary_section = ReportSection(
        "RMA Count by Age", ["Age Bucket", "Open RMAs"], [[d.label, str(d.count)] for d in distribution]
    )
    detail_section = ReportSection(
        "Open RMA Detail",
        ["RMA #", "Customer", "Part", "Date Received", "Age", "Status"],
        [
            [r.rma.rma_number, r.customer_name, r.rma.part.part_number if r.rma.part else "", _fmt_date(r.rma.date_received), r.aging_bucket, r.rma.status]
            for r in detail_rows
        ],
    )
    return Report(
        title="RMA Aging Report",
        generated_at=datetime.now(UTC),
        generated_by=generated_by,
        sections=[summary_section, detail_section],
    )


def build_management_summary_report(session: Session, settings: AppSettings, *, generated_by: str, as_of: date | None = None) -> Report:
    """One-page rollup of the dashboard KPIs plus the current top-priority actions."""
    as_of = as_of or date.today()
    counts = get_dashboard_counts(session, as_of)

    kpi_section = ReportSection(
        "Key Metrics",
        ["Metric", "Count"],
        [
            ["Open Customer Order Lines", str(counts.open_customer_orders)],
            ["Past Due", str(counts.past_due)],
            ["Due Today", str(counts.due_today)],
            ["Due This Week", str(counts.due_this_week)],
            ["Late Purchase Orders", str(counts.late_purchase_orders)],
            ["Awaiting Material", str(counts.awaiting_material)],
            ["Open RMAs", str(counts.open_rmas)],
            ["Open Follow-Ups", str(counts.open_follow_ups)],
        ],
    )

    order_repo = CustomerOrderRepository(session)
    rows, _total = order_repo.search_lines(OrderLineFilters(open_only=True), settings.priority, as_of=as_of, limit=500)
    top_actions = sorted(rows, key=lambda r: (r.priority != Priority.CRITICAL, r.priority != Priority.HIGH, -r.days_late))[:15]
    actions_section = ReportSection(
        "Top Priority Actions",
        ["CO", "Customer", "Part", "Due Date", "Days Late", "Priority", "Status"],
        [
            [r.co_number, r.customer_name, r.part_display, _fmt_date(r.line.due_date), str(r.days_late), r.priority.value, r.line.status]
            for r in top_actions
        ],
    )
    return Report(
        title="Management Summary",
        subtitle=f"As of {as_of.strftime(_DATE_FMT)}",
        generated_at=datetime.now(UTC),
        generated_by=generated_by,
        sections=[kpi_section, actions_section],
    )

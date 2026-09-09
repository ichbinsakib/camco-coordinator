"""Repository for shipments and the on-time-shipment analytics (spec section 16)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.core import Customer
from app.models.orders import CustomerOrderLine
from app.models.shipping import Shipment, ShipmentLine
from app.repositories.base import Repository


@dataclass(slots=True)
class ShipmentFilters:
    """Search/filter criteria for the shipment list."""

    text: str = ""
    status: str | None = None


@dataclass(slots=True)
class OnTimeResult:
    """On-time-shipment percentage over a date range."""

    range_label: str
    start: date
    end: date
    total_shipped_lines: int
    on_time_lines: int
    late_lines: int
    unknown_lines: int

    @property
    def on_time_percent(self) -> float | None:
        """On-time percentage of lines with a known due date; ``None`` if no data."""
        known = self.on_time_lines + self.late_lines
        if known == 0:
            return None
        return round(100.0 * self.on_time_lines / known, 1)


#: Standard historical ranges offered on the shipping analytics panel.
STANDARD_RANGES: list[tuple[str, int]] = [
    ("Current Month", 0),
    ("Previous Month", -1),
    ("Last 3 Months", 3),
    ("Last 6 Months", 6),
    ("Last 12 Months", 12),
    ("Last 24 Months", 24),
    ("Last 36 Months", 36),
    ("Last 48 Months", 48),
    ("Last 60 Months", 60),
]


def resolve_range(label: str, months: int, *, as_of: date | None = None) -> tuple[date, date]:
    """Resolve a named range (see :data:`STANDARD_RANGES`) into concrete start/end dates."""
    as_of = as_of or date.today()
    if label == "Current Month":
        start = as_of.replace(day=1)
        return start, as_of
    if label == "Previous Month":
        this_month_start = as_of.replace(day=1)
        prev_month_end = this_month_start - relativedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        return prev_month_start, prev_month_end
    start = as_of - relativedelta(months=months)
    return start, as_of


class ShipmentRepository(Repository[Shipment]):
    """CRUD for shipments, plus on-time analytics over configurable date ranges."""

    model = Shipment

    def search(
        self, filters: ShipmentFilters, *, limit: int = 200, offset: int = 0
    ) -> tuple[list[Shipment], int]:
        """Search shipment headers by number/carrier/tracking/customer."""
        stmt = select(Shipment).outerjoin(Shipment.customer).options(joinedload(Shipment.customer))
        count_stmt = select(func.count()).select_from(Shipment).outerjoin(Shipment.customer)

        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            condition = or_(
                Shipment.shipment_number.ilike(pattern),
                Shipment.carrier.ilike(pattern),
                Shipment.tracking_number.ilike(pattern),
                Customer.name.ilike(pattern),
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if filters.status:
            stmt = stmt.where(Shipment.status == filters.status)
            count_stmt = count_stmt.where(Shipment.status == filters.status)

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(
            self.session.scalars(
                stmt.order_by(Shipment.ship_date.desc().nulls_last()).offset(offset).limit(limit)
            )
        )
        return rows, total

    def on_time_percentage(
        self, start: date, end: date, *, grace_days: int = 0, range_label: str = ""
    ) -> OnTimeResult:
        """Compute the on-time-shipment percentage for shipment lines in a date range."""
        stmt = (
            select(ShipmentLine)
            .join(ShipmentLine.shipment)
            .join(ShipmentLine.customer_order_line)
            .where(Shipment.ship_date >= start, Shipment.ship_date <= end)
            .options(
                joinedload(ShipmentLine.shipment), joinedload(ShipmentLine.customer_order_line)
            )
        )
        lines = list(self.session.scalars(stmt))

        on_time = late = unknown = 0
        for line in lines:
            result = line.was_on_time(grace_days)
            if result is None:
                unknown += 1
            elif result:
                on_time += 1
            else:
                late += 1

        return OnTimeResult(
            range_label=range_label,
            start=start,
            end=end,
            total_shipped_lines=len(lines),
            on_time_lines=on_time,
            late_lines=late,
            unknown_lines=unknown,
        )


def get_customer_order_lines_awaiting_shipment(session: Session) -> list[CustomerOrderLine]:
    """Lines in READY TO SHIP status - the pool a new shipment is built from."""
    from app.config.constants import OrderStatus

    stmt = select(CustomerOrderLine).where(
        CustomerOrderLine.status == OrderStatus.READY_TO_SHIP.value
    )
    return list(session.scalars(stmt))

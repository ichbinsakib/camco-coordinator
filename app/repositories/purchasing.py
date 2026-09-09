"""Repository for purchase orders and lines - the material/vendor worklist.

Like the customer order list, the screen coordinators want is line-level
(spec section 15): PO number, vendor, part, quantities, dates, days late,
buyer - one row per :class:`PurchaseOrderLine`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config.constants import CLOSED_PO_STATUSES
from app.models.core import Part, Vendor
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.repositories.base import Repository


@dataclass(slots=True)
class PurchaseLineFilters:
    """Search/filter criteria for the purchasing list."""

    text: str = ""
    status: str | None = None
    vendor_id: int | None = None
    late_only: bool = False
    open_only: bool = True


@dataclass(slots=True)
class PurchaseLineRow:
    """A flattened, display-ready purchase order line."""

    line: PurchaseOrderLine
    po_number: str
    vendor_name: str
    part_display: str
    quantity_remaining: float
    days_late: int


class PurchaseOrderRepository(Repository[PurchaseOrder]):
    """CRUD for PO headers plus the line-level search used by the purchasing page."""

    model = PurchaseOrder

    def get_by_number(self, po_number: str) -> PurchaseOrder | None:
        """Fetch a PO header by its unique number, or ``None``."""
        return self.session.scalar(
            select(PurchaseOrder).where(PurchaseOrder.po_number == po_number)
        )

    def search_lines(
        self,
        filters: PurchaseLineFilters,
        *,
        as_of: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[PurchaseLineRow], int]:
        """Search purchase order lines, returning display-ready rows and total count."""
        as_of = as_of or date.today()
        stmt = (
            select(PurchaseOrderLine)
            .join(PurchaseOrderLine.purchase_order)
            .join(PurchaseOrder.vendor)
            .outerjoin(PurchaseOrderLine.part)
            .options(
                joinedload(PurchaseOrderLine.purchase_order).joinedload(PurchaseOrder.vendor),
                joinedload(PurchaseOrderLine.part),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(PurchaseOrderLine)
            .join(PurchaseOrderLine.purchase_order)
            .join(PurchaseOrder.vendor)
            .outerjoin(PurchaseOrderLine.part)
        )

        conditions = self._build_conditions(filters)
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.session.scalar(count_stmt) or 0)
        lines = list(
            self.session.scalars(
                stmt.order_by(
                    func.coalesce(PurchaseOrderLine.promised_date, PurchaseOrderLine.required_date).asc().nulls_last()
                )
                .offset(offset)
                .limit(limit)
            )
        )

        rows = [self._to_row(line, as_of) for line in lines]
        if filters.late_only:
            rows = [r for r in rows if r.days_late > 0]
        return rows, total

    def _build_conditions(self, filters: PurchaseLineFilters) -> list:
        conditions = []
        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            conditions.append(
                or_(
                    PurchaseOrder.po_number.ilike(pattern),
                    Vendor.name.ilike(pattern),
                    Part.part_number.ilike(pattern),
                    PurchaseOrderLine.description.ilike(pattern),
                )
            )
        if filters.status:
            conditions.append(PurchaseOrderLine.status == filters.status)
        if filters.vendor_id is not None:
            conditions.append(PurchaseOrder.vendor_id == filters.vendor_id)
        if filters.open_only:
            closed_values = [s.value for s in CLOSED_PO_STATUSES]
            conditions.append(PurchaseOrderLine.status.notin_(closed_values))
        return conditions

    def _to_row(self, line: PurchaseOrderLine, as_of: date) -> PurchaseLineRow:
        part_display = line.part.display_name if line.part else (line.description or "")
        return PurchaseLineRow(
            line=line,
            po_number=line.purchase_order.po_number,
            vendor_name=line.purchase_order.vendor.name,
            part_display=part_display,
            quantity_remaining=line.quantity_remaining,
            days_late=line.days_late(as_of),
        )


def get_or_create_po(session: Session, po_number: str, vendor_id: int) -> PurchaseOrder:
    """Idempotently fetch or create a PO header by number."""
    order = session.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == po_number))
    if order is None:
        order = PurchaseOrder(po_number=po_number, vendor_id=vendor_id)
        session.add(order)
        session.flush()
    return order

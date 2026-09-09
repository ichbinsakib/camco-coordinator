"""Repository for production orders and their routing operations.

Spec section 14: a coordinator wants to see, per production order, the part,
the *current* operation (the first not-yet-complete step in routing order),
and how long it's been sitting there - that last figure is what feeds the
"stagnant operation" alert in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.config.constants import CLOSED_PRODUCTION_STATUSES
from app.models.core import Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder
from app.repositories.base import Repository


@dataclass(slots=True)
class ProductionOrderFilters:
    """Search/filter criteria for the production order list."""

    text: str = ""
    department: str | None = None
    open_only: bool = True


@dataclass(slots=True)
class ProductionOrderRow:
    """A production order plus its display-ready current-operation summary."""

    order: ProductionOrder
    co_number: str
    part_display: str
    current_operation: ProductionOperation | None
    days_in_status: int


class ProductionOrderRepository(Repository[ProductionOrder]):
    """CRUD for production orders plus the current-operation search used by the list page."""

    model = ProductionOrder

    def search(
        self,
        filters: ProductionOrderFilters,
        *,
        as_of: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[ProductionOrderRow], int]:
        """Search production orders, returning rows with the current operation resolved."""
        as_of = as_of or date.today()
        stmt = (
            select(ProductionOrder)
            .join(ProductionOrder.customer_order_line)
            .join(CustomerOrderLine.customer_order)
            .join(ProductionOrder.part)
            .options(
                joinedload(ProductionOrder.customer_order_line).joinedload(
                    CustomerOrderLine.customer_order
                ),
                joinedload(ProductionOrder.part),
                joinedload(ProductionOrder.operations),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(ProductionOrder)
            .join(ProductionOrder.customer_order_line)
            .join(CustomerOrderLine.customer_order)
            .join(ProductionOrder.part)
        )

        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            condition = or_(
                ProductionOrder.production_number.ilike(pattern),
                Part.part_number.ilike(pattern),
                CustomerOrder.co_number.ilike(pattern),
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.session.scalar(count_stmt) or 0)
        orders = list(
            self.session.execute(stmt.offset(offset).limit(limit)).unique().scalars()
        )

        rows = [self._to_row(order, as_of) for order in orders]
        if filters.department:
            rows = [
                r
                for r in rows
                if r.current_operation and r.current_operation.department == filters.department
            ]
        if filters.open_only:
            rows = [r for r in rows if r.current_operation is not None]
        return rows, total

    def _to_row(self, order: ProductionOrder, as_of: date) -> ProductionOrderRow:
        current = order.current_operation
        return ProductionOrderRow(
            order=order,
            co_number=order.customer_order_line.customer_order.co_number,
            part_display=order.part.display_name,
            current_operation=current,
            days_in_status=current.days_in_status(as_of) if current else 0,
        )

    def stagnant_operations(self, threshold_days: int, *, as_of: date | None = None) -> list[ProductionOperation]:
        """Operations that have sat in their current status past the configured threshold."""
        as_of = as_of or date.today()
        closed_values = [s.value for s in CLOSED_PRODUCTION_STATUSES]
        stmt = (
            select(ProductionOperation)
            .where(ProductionOperation.status.notin_(closed_values))
            .where(ProductionOperation.status_since.isnot(None))
        )
        candidates = list(self.session.scalars(stmt))
        return [op for op in candidates if op.days_in_status(as_of) >= threshold_days]

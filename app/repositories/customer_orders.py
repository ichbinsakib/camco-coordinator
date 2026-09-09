"""Repository for customer orders and their lines.

The list screen coordinators actually want is line-level (spec section 13:
search/filter by CO, part, customer, status, due date, priority, and see
qty/dates/status per line) - so the primary read query here joins order,
customer and part and returns one row per :class:`CustomerOrderLine`, not
per header.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.business.priority import compute_line_priority
from app.config.constants import CLOSED_ORDER_STATUSES, Priority
from app.config.settings import PrioritySettings
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.repositories.base import Repository


@dataclass(slots=True)
class OrderLineFilters:
    """Search/filter criteria for the customer order line list."""

    text: str = ""
    status: str | None = None
    priority: str | None = None
    customer_id: int | None = None
    due_before: date | None = None
    due_after: date | None = None
    open_only: bool = True


@dataclass(slots=True)
class OrderLineRow:
    """A flattened, display-ready row: the ORM line plus derived fields."""

    line: CustomerOrderLine
    co_number: str
    customer_name: str
    part_display: str
    quantity_remaining: float
    days_late: int
    days_until_due: int | None
    priority: Priority


class CustomerOrderRepository(Repository[CustomerOrder]):
    """CRUD for CO headers, plus the line-level search used by the CO list page."""

    model = CustomerOrder

    def get_by_number(self, co_number: str) -> CustomerOrder | None:
        """Fetch a CO header by its unique number, or ``None``."""
        return self.session.scalar(
            select(CustomerOrder).where(CustomerOrder.co_number == co_number)
        )

    def search_lines(
        self,
        filters: OrderLineFilters,
        priority_settings: PrioritySettings,
        *,
        as_of: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[OrderLineRow], int]:
        """Search order lines, returning display-ready rows and the total count."""
        as_of = as_of or date.today()
        stmt = (
            select(CustomerOrderLine)
            .join(CustomerOrderLine.customer_order)
            .join(CustomerOrderLine.part)
            .join(CustomerOrder.customer)
            .options(
                joinedload(CustomerOrderLine.customer_order).joinedload(CustomerOrder.customer),
                joinedload(CustomerOrderLine.part),
            )
        )
        count_stmt = (
            select(func.count())
            .select_from(CustomerOrderLine)
            .join(CustomerOrderLine.customer_order)
            .join(CustomerOrderLine.part)
            .join(CustomerOrder.customer)
        )

        conditions = self._build_conditions(filters)
        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.session.scalar(count_stmt) or 0)
        lines = list(
            self.session.scalars(
                stmt.order_by(CustomerOrderLine.due_date.asc().nulls_last())
                .offset(offset)
                .limit(limit)
            )
        )

        rows = [self._to_row(line, priority_settings, as_of) for line in lines]
        if filters.priority:
            rows = [r for r in rows if r.priority.value == filters.priority]
        return rows, total

    def _build_conditions(self, filters: OrderLineFilters) -> list:
        conditions = []
        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            conditions.append(
                or_(
                    CustomerOrder.co_number.ilike(pattern),
                    CustomerOrder.customer_po_number.ilike(pattern),
                    Part.part_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        if filters.status:
            conditions.append(CustomerOrderLine.status == filters.status)
        if filters.customer_id is not None:
            conditions.append(CustomerOrder.customer_id == filters.customer_id)
        if filters.due_before is not None:
            conditions.append(CustomerOrderLine.due_date <= filters.due_before)
        if filters.due_after is not None:
            conditions.append(CustomerOrderLine.due_date >= filters.due_after)
        if filters.open_only:
            closed_values = [s.value for s in CLOSED_ORDER_STATUSES]
            conditions.append(CustomerOrderLine.status.notin_(closed_values))
        return conditions

    def _to_row(
        self, line: CustomerOrderLine, priority_settings: PrioritySettings, as_of: date
    ) -> OrderLineRow:
        customer = line.customer_order.customer
        priority = compute_line_priority(
            line, priority_settings, as_of=as_of, customer_importance=customer.importance
        )
        return OrderLineRow(
            line=line,
            co_number=line.customer_order.co_number,
            customer_name=customer.name,
            part_display=line.part.display_name,
            quantity_remaining=line.quantity_remaining,
            days_late=line.days_late(as_of),
            days_until_due=line.days_until_due(as_of),
            priority=priority,
        )


def get_or_create_order(session: Session, co_number: str, customer_id: int) -> CustomerOrder:
    """Idempotently fetch or create a CO header by number, used by import/creation flows."""
    order = session.scalar(select(CustomerOrder).where(CustomerOrder.co_number == co_number))
    if order is None:
        order = CustomerOrder(co_number=co_number, customer_id=customer_id)
        session.add(order)
        session.flush()
    return order

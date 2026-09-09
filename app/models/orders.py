"""Customer order, sales order and their line items."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import CODE_LENGTH, OrderStatus, Priority
from app.database.base import AuditedBase


class CustomerOrder(AuditedBase):
    """A customer purchase-order header (what CAMCO calls a "CO")."""

    __tablename__ = "customer_orders"
    __table_args__ = (UniqueConstraint("co_number", name="uq_customer_orders_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    co_number: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    customer_po_number: Mapped[str | None] = mapped_column(String(CODE_LENGTH), nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer = relationship("Customer", back_populates="customer_orders")
    lines: Mapped[list[CustomerOrderLine]] = relationship(
        back_populates="customer_order", cascade="all, delete-orphan"
    )


class SalesOrder(AuditedBase):
    """A sales-order header, used when CAMCO's own SO number differs from the CO."""

    __tablename__ = "sales_orders"
    __table_args__ = (UniqueConstraint("so_number", name="uq_sales_orders_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    so_number: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    customer_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customer_orders.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_order: Mapped[CustomerOrder | None] = relationship()


class CustomerOrderLine(AuditedBase):
    """One part/quantity/due-date commitment within a customer order.

    This is the row most of the coordination workflow revolves around: it is
    what production, purchasing and shipping all ultimately serve.
    """

    __tablename__ = "customer_order_lines"
    __table_args__ = (
        UniqueConstraint("customer_order_id", "line_number", name="uq_co_line_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_orders.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    part_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False
    )
    sales_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_orders.id", ondelete="SET NULL"), nullable=True
    )
    quantity_ordered: Mapped[float] = mapped_column(nullable=False, default=0)
    quantity_completed: Mapped[float] = mapped_column(nullable=False, default=0)
    quantity_scrapped: Mapped[float] = mapped_column(nullable=False, default=0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    original_due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="First due date recorded; preserved even after reschedules"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OrderStatus.NOT_STARTED.value, index=True
    )
    manual_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_order: Mapped[CustomerOrder] = relationship(back_populates="lines")
    part = relationship("Part")
    sales_order: Mapped[SalesOrder | None] = relationship()

    @property
    def quantity_remaining(self) -> float:
        """Ordered quantity minus what has actually been completed and accepted.

        Clamped at zero: an over-completion (rework replacing scrap, a data
        correction) must never show a negative remaining quantity.
        """
        remaining = self.quantity_ordered - self.quantity_completed
        return max(remaining, 0.0)

    @property
    def is_complete(self) -> bool:
        """True once the full ordered quantity has been completed."""
        return self.quantity_remaining <= 0 and self.quantity_ordered > 0

    def days_late(self, as_of: date) -> int:
        """Positive integer days past due; zero if not late or not yet due.

        A completed/shipped/cancelled line is never "late" - closed work does
        not keep aging just because nobody updated the due date.
        """
        if self.status in {OrderStatus.COMPLETE.value, OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value}:
            return 0
        if self.due_date is None or as_of <= self.due_date:
            return 0
        return (as_of - self.due_date).days

    def days_until_due(self, as_of: date) -> int | None:
        """Days remaining until due (negative if past due); ``None`` if no due date."""
        if self.due_date is None:
            return None
        return (self.due_date - as_of).days

    def effective_priority(self) -> str | None:
        """A coordinator-pinned priority overrides the computed one; else ``None``."""
        if self.manual_priority and self.manual_priority in {p.value for p in Priority}:
            return self.manual_priority
        return None

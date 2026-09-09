"""Production orders and their routing operations."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import NAME_LENGTH, ProductionStatus
from app.database.base import AuditedBase


class ProductionOrder(AuditedBase):
    """The shop-floor work order that fulfils one customer order line."""

    __tablename__ = "production_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    customer_order_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_order_lines.id", ondelete="CASCADE"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(Integer, ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False)
    planned_quantity: Mapped[float] = mapped_column(nullable=False, default=0)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_order_line = relationship("CustomerOrderLine")
    part = relationship("Part")
    operations: Mapped[list[ProductionOperation]] = relationship(
        back_populates="production_order",
        cascade="all, delete-orphan",
        order_by="ProductionOperation.sequence",
    )

    @property
    def current_operation(self) -> ProductionOperation | None:
        """First not-yet-complete operation in routing order, or ``None`` if done."""
        for op in self.operations:
            if op.status != ProductionStatus.COMPLETE.value:
                return op
        return None


class ProductionOperation(AuditedBase):
    """A single routing step (OP10, OP20, ...) within a production order."""

    __tablename__ = "production_operations"
    __table_args__ = (
        UniqueConstraint("production_order_id", "sequence", name="uq_production_op_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, doc="10, 20, 30 ... routing order")
    operation_name: Mapped[str] = mapped_column(String(NAME_LENGTH), nullable=False)
    work_center: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planned_quantity: Mapped[float] = mapped_column(nullable=False, default=0)
    completed_quantity: Mapped[float] = mapped_column(nullable=False, default=0)
    scrap_quantity: Mapped[float] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ProductionStatus.NOT_STARTED.value, index=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status_since: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="Date the current status was set; drives stagnation alerts"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    production_order: Mapped[ProductionOrder] = relationship(back_populates="operations")

    @property
    def remaining_quantity(self) -> float:
        """Planned quantity still to complete at this operation."""
        return max(self.planned_quantity - self.completed_quantity, 0.0)

    def days_in_status(self, as_of: date) -> int:
        """Days the operation has sat in its current status; 0 if unknown/today."""
        if self.status_since is None or as_of <= self.status_since:
            return 0
        return (as_of - self.status_since).days

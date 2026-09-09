"""Purchase orders and lines: the material/vendor side of coordination."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import CODE_LENGTH, NAME_LENGTH, PurchaseOrderStatus
from app.database.base import AuditedBase


class PurchaseOrder(AuditedBase):
    """A purchase-order header issued to a vendor."""

    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("po_number", name="uq_purchase_orders_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False
    )
    buyer: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    po_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    vendor = relationship("Vendor")
    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(AuditedBase):
    """One material/part commitment on a purchase order."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_number", name="uq_po_line_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    part_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("parts.id", ondelete="SET NULL"), nullable=True
    )
    customer_order_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customer_order_lines.id", ondelete="SET NULL"), nullable=True,
        doc="Optional link to the demand this material supports",
    )
    description: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    quantity_ordered: Mapped[float] = mapped_column(nullable=False, default=0)
    quantity_received: Mapped[float] = mapped_column(nullable=False, default=0)
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PurchaseOrderStatus.OPEN.value, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    part = relationship("Part")
    customer_order_line = relationship("CustomerOrderLine")

    @property
    def quantity_remaining(self) -> float:
        """Quantity still outstanding on this line."""
        return max(self.quantity_ordered - self.quantity_received, 0.0)

    def days_late(self, as_of: date) -> int:
        """Days past the promised (or required, if unpromised) date.

        Received/closed/cancelled lines are never late - the receipt already
        happened or the line no longer matters.
        """
        closed = {
            PurchaseOrderStatus.RECEIVED.value,
            PurchaseOrderStatus.CLOSED.value,
            PurchaseOrderStatus.CANCELLED.value,
        }
        if self.status in closed:
            return 0
        reference = self.promised_date or self.required_date
        if reference is None or as_of <= reference:
            return 0
        return (as_of - reference).days

"""Shipments: the fulfilment side of a customer order line."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import NAME_LENGTH, ShipmentStatus
from app.database.base import AuditedBase


class Shipment(AuditedBase):
    """A single outbound shipment, which may carry several order lines."""

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    carrier: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    ship_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ShipmentStatus.PLANNED.value, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer = relationship("Customer")
    lines: Mapped[list[ShipmentLine]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )


class ShipmentLine(AuditedBase):
    """Quantity of one customer order line included in a shipment."""

    __tablename__ = "shipment_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False
    )
    customer_order_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_order_lines.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_shipped: Mapped[float] = mapped_column(nullable=False, default=0)

    shipment: Mapped[Shipment] = relationship(back_populates="lines")
    customer_order_line = relationship("CustomerOrderLine")

    def was_on_time(self, grace_days: int = 0) -> bool | None:
        """Whether this line shipped on/before its order line's due date.

        Returns ``None`` when either date is missing - "unknown" must never be
        silently counted as either on-time or late in an on-time-% KPI.
        """
        due = self.customer_order_line.due_date if self.customer_order_line else None
        ship_date = self.shipment.ship_date if self.shipment else None
        if due is None or ship_date is None:
            return None
        return ship_date <= due + timedelta(days=grace_days)

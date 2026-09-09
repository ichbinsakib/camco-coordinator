"""Return Material Authorizations - customer-reported quality issues."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import CODE_LENGTH, NAME_LENGTH, RmaStatus
from app.database.base import AuditedBase


class Rma(AuditedBase):
    """A single RMA case tracked from receipt through corrective action."""

    __tablename__ = "rmas"
    __table_args__ = (UniqueConstraint("rma_number", name="uq_rmas_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rma_number: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    part_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("parts.id", ondelete="SET NULL"), nullable=True
    )
    customer_order_line_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customer_order_lines.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[float] = mapped_column(nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    date_received: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RmaStatus.OPEN.value, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer = relationship("Customer")
    part = relationship("Part")
    customer_order_line = relationship("CustomerOrderLine")

    def age_days(self, as_of: date) -> int:
        """Days the RMA has been open (or was open for, if closed)."""
        start = self.date_received or self.created_at.date()
        end = self.actual_completion_date or as_of
        return max((end - start).days, 0)

    def age_months(self, as_of: date) -> float:
        """Age in months (30-day months) - RMA aging is reported in months, not days."""
        return round(self.age_days(as_of) / 30.0, 1)

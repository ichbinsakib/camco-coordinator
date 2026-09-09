"""Coordinator follow-ups: the "who do I need to chase" system."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import NAME_LENGTH, FollowUpStatus, Priority
from app.database.base import AuditedBase


class FollowUp(AuditedBase):
    """A coordination task tied to a person, department, or outside party."""

    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(NAME_LENGTH), nullable=False)
    part_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("parts.id", ondelete="SET NULL"), nullable=True
    )
    customer_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customer_orders.id", ondelete="SET NULL"), nullable=True
    )
    sales_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sales_orders.id", ondelete="SET NULL"), nullable=True
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(32), nullable=True)
    responsible_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default=Priority.MEDIUM.value)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FollowUpStatus.OPEN.value, index=True
    )
    communication_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_contacted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_followup_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    part = relationship("Part")
    customer_order = relationship("CustomerOrder")
    sales_order = relationship("SalesOrder")
    purchase_order = relationship("PurchaseOrder")
    vendor = relationship("Vendor")
    customer = relationship("Customer")
    responsible_user = relationship("User", foreign_keys=[responsible_user_id])

    def is_overdue(self, as_of: date) -> bool:
        """True if the follow-up is still open past its due date."""
        if self.status in {FollowUpStatus.COMPLETED.value, FollowUpStatus.CANCELLED.value}:
            return False
        return self.due_date is not None and as_of > self.due_date

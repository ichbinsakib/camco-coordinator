"""Core reference entities: users, customers, vendors and parts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import CODE_LENGTH, NAME_LENGTH, UserRole
from app.database.base import AuditedBase, Base, TimestampMixin


class User(Base, TimestampMixin):
    """A local application user / role holder.

    Password hashing is handled entirely in :mod:`app.security.auth`; this
    model only stores the resulting hash, never a plaintext password.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(NAME_LENGTH), nullable=False)
    email: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.COORDINATOR.value)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Customer(AuditedBase):
    """A customer that places orders against CAMCO."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("code", name="uq_customers_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH), nullable=False)
    importance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, doc="1 = strategic account ... 5 = low priority"
    )
    contact_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_orders: Mapped[list[CustomerOrder]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )


class Vendor(AuditedBase):
    """A supplier CAMCO purchases material, tooling or outside services from."""

    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("code", name="uq_vendors_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(NAME_LENGTH), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    average_lead_time_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    on_time_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, doc="Rolling on-time-delivery percentage, refreshed by analytics"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Part(AuditedBase):
    """A centralised part-number record, referenced by orders and transactions.

    ``part_number`` + ``revision`` is the natural key; a part is not unique on
    part number alone because revisions change form/fit/function.
    """

    __tablename__ = "parts"
    __table_args__ = (
        UniqueConstraint("part_number", "revision", name="uq_parts_number_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_number: Mapped[str] = mapped_column(String(CODE_LENGTH), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String(16), nullable=False, default="-")
    description: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    customer_part_number: Mapped[str | None] = mapped_column(String(CODE_LENGTH), nullable=True)
    drawing_number: Mapped[str | None] = mapped_column(String(CODE_LENGTH), nullable=True)
    material: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    finish: Mapped[str | None] = mapped_column(String(NAME_LENGTH), nullable=True)
    standard_lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer | None] = relationship()

    @property
    def display_name(self) -> str:
        """Part number with revision, formatted the way coordinators read it."""
        return f"{self.part_number} Rev {self.revision}" if self.revision != "-" else self.part_number

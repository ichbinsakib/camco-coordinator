"""Declarative base and reusable mixins for every ORM model.

Centralising the audit columns here means rule 57 (auditability) and rule 56
(database integrity) are enforced structurally instead of being something each
model author has to remember.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base shared by every model in the application."""


class TimestampMixin:
    """``created_at`` / ``updated_at`` columns, always UTC, always server-set."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditUserMixin:
    """``created_by`` / ``updated_by`` user references for traceable records.

    Nullable because the very first admin user and any data-migration path
    cannot always name a responsible user; application code should populate
    these whenever a real user session is available.
    """

    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AuditedBase(Base, TimestampMixin, AuditUserMixin):
    """Convenience base for tables that need full audit tracking."""

    __abstract__ = True


class CodeMixin:
    """A short, indexed business identifier such as a part number or PO number."""

    code: Mapped[str] = mapped_column(String(64), nullable=False)

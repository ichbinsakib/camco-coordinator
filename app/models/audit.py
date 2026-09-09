"""Cross-cutting records: notes, the immutable activity log, and alerts.

These tables are polymorphic by convention (``entity_type`` + ``entity_id``)
rather than by SQLAlchemy inheritance, because they must attach to entities as
different as a Part and a Vendor without those domain models knowing anything
about notes/activity/alerts. This keeps the domain layer decoupled (rule 43).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import AlertSeverity, AlertStatus
from app.database.base import Base, TimestampMixin


class Note(Base, TimestampMixin):
    """A free-text note attached to any entity, always attributed and dated."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    author_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    author = relationship("User")


class ActivityLogEntry(Base):
    """An append-only record of a meaningful change to an entity.

    There is deliberately no ``updated_at`` and no update/delete path exposed
    anywhere in the repository layer for this table (rule 21: history must not
    be easily deleted).
    """

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    field_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user = relationship("User")


class Alert(Base, TimestampMixin):
    """A generated attention item; distinct from a follow-up (system-raised, not manual)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_code: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, doc="Which alert rule produced this, e.g. PO_LATE"
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default=AlertSeverity.INFO.value)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AlertStatus.NEW.value, index=True
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    acknowledged_by = relationship("User")

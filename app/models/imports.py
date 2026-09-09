"""Import batch tracking: every Excel/CSV import is recorded, never silent."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import ImportStatus
from app.database.base import Base


class ImportBatch(Base):
    """One user-confirmed import run against a specific source file/sheet."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file: Mapped[str] = mapped_column(String(1024), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_entity: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Which table this batch loaded, e.g. customer_order_lines"
    )
    mapping_json: Mapped[str] = mapped_column(Text, nullable=False, doc="Column mapping used, as JSON")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ImportStatus.PREVIEW.value
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    imported_by = relationship("User")
    errors: Mapped[list[ImportRowError]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class ImportRowError(Base):
    """A single row-level validation problem surfaced to the user before commit."""

    __tablename__ = "import_row_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    batch: Mapped[ImportBatch] = relationship(back_populates="errors")

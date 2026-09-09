"""Repository for the centralized part-number record."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.models.core import Part
from app.repositories.base import Repository


class PartRepository(Repository[Part]):
    """CRUD plus search/pagination for :class:`Part`."""

    model = Part

    def search(
        self,
        text: str = "",
        *,
        customer_id: int | None = None,
        active_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[Part], int]:
        """Search by part number/description/drawing/customer part number."""
        stmt = select(Part).options(joinedload(Part.customer))
        count_stmt = select(func.count()).select_from(Part)

        if text.strip():
            pattern = f"%{text.strip()}%"
            condition = or_(
                Part.part_number.ilike(pattern),
                Part.description.ilike(pattern),
                Part.drawing_number.ilike(pattern),
                Part.customer_part_number.ilike(pattern),
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if customer_id is not None:
            stmt = stmt.where(Part.customer_id == customer_id)
            count_stmt = count_stmt.where(Part.customer_id == customer_id)
        if active_only:
            stmt = stmt.where(Part.is_active.is_(True))
            count_stmt = count_stmt.where(Part.is_active.is_(True))

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(
            self.session.scalars(
                stmt.order_by(Part.part_number, Part.revision).offset(offset).limit(limit)
            )
        )
        return rows, total

    def get_by_number_revision(self, part_number: str, revision: str) -> Part | None:
        """Fetch a part by its natural key, or ``None``."""
        return self.session.scalar(
            select(Part).where(Part.part_number == part_number, Part.revision == revision)
        )

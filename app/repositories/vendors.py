"""Repository for the vendor master."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.core import Vendor
from app.repositories.base import Repository


class VendorRepository(Repository[Vendor]):
    """CRUD plus search/pagination for :class:`Vendor`."""

    model = Vendor

    def search(
        self, text: str = "", *, active_only: bool = False, limit: int = 200, offset: int = 0
    ) -> tuple[list[Vendor], int]:
        """Search by code/name (case-insensitive substring); returns (rows, total_count)."""
        stmt = select(Vendor)
        count_stmt = select(func.count()).select_from(Vendor)

        if text.strip():
            pattern = f"%{text.strip()}%"
            condition = or_(Vendor.code.ilike(pattern), Vendor.name.ilike(pattern))
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if active_only:
            stmt = stmt.where(Vendor.is_active.is_(True))
            count_stmt = count_stmt.where(Vendor.is_active.is_(True))

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(self.session.scalars(stmt.order_by(Vendor.name).offset(offset).limit(limit)))
        return rows, total

    def get_by_code(self, code: str) -> Vendor | None:
        """Fetch a vendor by its unique code, or ``None``."""
        return self.session.scalar(select(Vendor).where(Vendor.code == code))

"""Repository for the customer master."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.core import Customer
from app.repositories.base import Repository


class CustomerRepository(Repository[Customer]):
    """CRUD plus search/pagination for :class:`Customer`."""

    model = Customer

    def search(
        self, text: str = "", *, active_only: bool = False, limit: int = 200, offset: int = 0
    ) -> tuple[list[Customer], int]:
        """Search by code/name (case-insensitive substring); returns (rows, total_count)."""
        stmt = select(Customer)
        count_stmt = select(func.count()).select_from(Customer)

        if text.strip():
            pattern = f"%{text.strip()}%"
            condition = or_(Customer.code.ilike(pattern), Customer.name.ilike(pattern))
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if active_only:
            stmt = stmt.where(Customer.is_active.is_(True))
            count_stmt = count_stmt.where(Customer.is_active.is_(True))

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(
            self.session.scalars(stmt.order_by(Customer.name).offset(offset).limit(limit))
        )
        return rows, total

    def get_by_code(self, code: str) -> Customer | None:
        """Fetch a customer by its unique code, or ``None``."""
        return self.session.scalar(select(Customer).where(Customer.code == code))

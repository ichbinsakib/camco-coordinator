"""Repository for coordinator follow-ups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.config.constants import CLOSED_FOLLOWUP_STATUSES
from app.models.followup import FollowUp
from app.repositories.base import Repository


@dataclass(slots=True)
class FollowUpFilters:
    """Search/filter criteria for the follow-up list."""

    text: str = ""
    status: str | None = None
    department: str | None = None
    overdue_only: bool = False
    open_only: bool = True


class FollowUpRepository(Repository[FollowUp]):
    """CRUD plus search/pagination for :class:`FollowUp`."""

    model = FollowUp

    def search(
        self,
        filters: FollowUpFilters,
        *,
        as_of: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[FollowUp], int]:
        """Search follow-ups; overdue-only is applied after loading since it's derived."""
        as_of = as_of or date.today()
        stmt = select(FollowUp).options(
            joinedload(FollowUp.customer),
            joinedload(FollowUp.vendor),
            joinedload(FollowUp.part),
            joinedload(FollowUp.customer_order),
            joinedload(FollowUp.responsible_user),
        )
        count_stmt = select(func.count()).select_from(FollowUp)

        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            condition = or_(FollowUp.subject.ilike(pattern), FollowUp.notes.ilike(pattern))
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if filters.status:
            stmt = stmt.where(FollowUp.status == filters.status)
            count_stmt = count_stmt.where(FollowUp.status == filters.status)
        if filters.department:
            stmt = stmt.where(FollowUp.department == filters.department)
            count_stmt = count_stmt.where(FollowUp.department == filters.department)
        if filters.open_only:
            closed_values = [s.value for s in CLOSED_FOLLOWUP_STATUSES]
            stmt = stmt.where(FollowUp.status.notin_(closed_values))
            count_stmt = count_stmt.where(FollowUp.status.notin_(closed_values))

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(
            self.session.scalars(
                stmt.order_by(FollowUp.due_date.asc().nulls_last()).offset(offset).limit(limit)
            )
        )
        if filters.overdue_only:
            rows = [f for f in rows if f.is_overdue(as_of)]
        return rows, total

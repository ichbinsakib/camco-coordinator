"""Repository for RMA (Return Material Authorization) cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.config.constants import CLOSED_RMA_STATUSES
from app.config.settings import RmaSettings
from app.models.core import Customer
from app.models.rma import Rma
from app.repositories.base import Repository


@dataclass(slots=True)
class RmaFilters:
    """Search/filter criteria for the RMA list."""

    text: str = ""
    status: str | None = None
    open_only: bool = True


@dataclass(slots=True)
class RmaRow:
    """An RMA plus its display-ready aging bucket."""

    rma: Rma
    customer_name: str
    age_months: float
    aging_bucket: str


def aging_bucket_label(age_months: float, buckets: list[float]) -> str:
    """Map an age in months onto a configured bucket label (e.g. "1-3 Months")."""
    edges = sorted(buckets)
    lower = 0.0
    for edge in edges:
        if age_months < edge:
            return f"{_fmt(lower)}-{_fmt(edge)} Months"
        lower = edge
    return f"{_fmt(lower)}+ Months"


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


class RmaRepository(Repository[Rma]):
    """CRUD plus search/pagination for :class:`Rma`, with aging-bucket display rows."""

    model = Rma

    def search(
        self,
        filters: RmaFilters,
        rma_settings: RmaSettings,
        *,
        as_of: date | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[RmaRow], int]:
        """Search RMAs, returning display-ready rows and the total count."""
        as_of = as_of or date.today()
        stmt = select(Rma).join(Rma.customer).options(joinedload(Rma.customer), joinedload(Rma.part))
        count_stmt = select(func.count()).select_from(Rma).join(Rma.customer)

        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            condition = or_(Rma.rma_number.ilike(pattern), Customer.name.ilike(pattern), Rma.reason.ilike(pattern))
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if filters.status:
            stmt = stmt.where(Rma.status == filters.status)
            count_stmt = count_stmt.where(Rma.status == filters.status)
        if filters.open_only:
            closed_values = [s.value for s in CLOSED_RMA_STATUSES]
            stmt = stmt.where(Rma.status.notin_(closed_values))
            count_stmt = count_stmt.where(Rma.status.notin_(closed_values))

        total = int(self.session.scalar(count_stmt) or 0)
        rmas = list(
            self.session.scalars(
                stmt.order_by(Rma.date_received.asc().nulls_last()).offset(offset).limit(limit)
            )
        )
        rows = [self._to_row(rma, rma_settings, as_of) for rma in rmas]
        return rows, total

    def _to_row(self, rma: Rma, rma_settings: RmaSettings, as_of: date) -> RmaRow:
        age = rma.age_months(as_of)
        return RmaRow(
            rma=rma,
            customer_name=rma.customer.name,
            age_months=age,
            aging_bucket=aging_bucket_label(age, rma_settings.aging_buckets_months),
        )

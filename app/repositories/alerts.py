"""Repository for querying and actioning generated alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.constants import AlertStatus
from app.models.audit import Alert
from app.repositories.base import Repository


@dataclass(slots=True)
class AlertFilters:
    """Search/filter criteria for the alert list."""

    text: str = ""
    severity: str | None = None
    include_snoozed: bool = True


class AlertRepository(Repository[Alert]):
    """CRUD plus the acknowledge/snooze/resolve actions used by the Alerts page."""

    model = Alert

    def search_active(
        self, filters: AlertFilters, *, as_of: date | None = None, limit: int = 200, offset: int = 0
    ) -> tuple[list[Alert], int]:
        """Alerts visible on the worklist: NEW/ACKNOWLEDGED, plus SNOOZED ones past their snooze."""
        as_of = as_of or date.today()
        now = datetime.now(UTC)
        active_statuses = [AlertStatus.NEW.value, AlertStatus.ACKNOWLEDGED.value]

        stmt = select(Alert)
        count_stmt = select(func.count()).select_from(Alert)

        if filters.include_snoozed:
            condition = Alert.status.in_(active_statuses) | (
                (Alert.status == AlertStatus.SNOOZED.value)
                & (Alert.snoozed_until.is_(None) | (Alert.snoozed_until <= now))
            )
        else:
            condition = Alert.status.in_(active_statuses)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

        if filters.text.strip():
            pattern = f"%{filters.text.strip()}%"
            stmt = stmt.where(Alert.message.ilike(pattern))
            count_stmt = count_stmt.where(Alert.message.ilike(pattern))
        if filters.severity:
            stmt = stmt.where(Alert.severity == filters.severity)
            count_stmt = count_stmt.where(Alert.severity == filters.severity)

        total = int(self.session.scalar(count_stmt) or 0)
        rows = list(
            self.session.scalars(
                stmt.order_by(Alert.severity.asc(), Alert.created_at.desc()).offset(offset).limit(limit)
            )
        )
        return rows, total

    def acknowledge(self, alert_id: int, user_id: int | None) -> None:
        """Mark an alert as seen without dismissing it."""
        alert = self.session.get(Alert, alert_id)
        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED.value
            alert.acknowledged_by_id = user_id

    def snooze(self, alert_id: int, days: int) -> None:
        """Hide an alert from the active worklist until ``days`` from now."""
        alert = self.session.get(Alert, alert_id)
        if alert:
            alert.status = AlertStatus.SNOOZED.value
            alert.snoozed_until = datetime.now(UTC) + timedelta(days=days)

    def resolve(self, alert_id: int) -> None:
        """Manually mark an alert resolved (distinct from the engine auto-resolving it)."""
        alert = self.session.get(Alert, alert_id)
        if alert:
            alert.status = AlertStatus.RESOLVED.value
            alert.resolved_at = datetime.now(UTC)


def count_active(session: Session) -> int:
    """Cheap count of currently-active alerts, for the dashboard KPI card."""
    now = datetime.now(UTC)
    active_statuses = [AlertStatus.NEW.value, AlertStatus.ACKNOWLEDGED.value]
    condition = Alert.status.in_(active_statuses) | (
        (Alert.status == AlertStatus.SNOOZED.value)
        & (Alert.snoozed_until.is_(None) | (Alert.snoozed_until <= now))
    )
    return int(session.scalar(select(func.count()).select_from(Alert).where(condition)) or 0)

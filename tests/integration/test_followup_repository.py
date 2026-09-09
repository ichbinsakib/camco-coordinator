"""Integration tests for FollowUpRepository."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config.constants import FollowUpStatus
from app.models.followup import FollowUp
from app.repositories.followups import FollowUpFilters, FollowUpRepository


def test_overdue_only_excludes_future_and_completed(db_session: Session) -> None:
    db_session.add_all(
        [
            FollowUp(subject="Overdue", due_date=date.today() - timedelta(days=2), status=FollowUpStatus.OPEN.value),
            FollowUp(subject="Future", due_date=date.today() + timedelta(days=2), status=FollowUpStatus.OPEN.value),
            FollowUp(
                subject="Completed but past due",
                due_date=date.today() - timedelta(days=5),
                status=FollowUpStatus.COMPLETED.value,
            ),
        ]
    )
    db_session.commit()

    repo = FollowUpRepository(db_session)
    rows, _total = repo.search(FollowUpFilters(overdue_only=True, open_only=False))
    assert len(rows) == 1
    assert rows[0].subject == "Overdue"


def test_open_only_excludes_completed_and_cancelled(db_session: Session) -> None:
    db_session.add_all(
        [
            FollowUp(subject="Open", status=FollowUpStatus.OPEN.value),
            FollowUp(subject="Waiting", status=FollowUpStatus.WAITING.value),
            FollowUp(subject="Done", status=FollowUpStatus.COMPLETED.value),
            FollowUp(subject="Cancelled", status=FollowUpStatus.CANCELLED.value),
        ]
    )
    db_session.commit()

    repo = FollowUpRepository(db_session)
    rows, total = repo.search(FollowUpFilters(open_only=True))
    assert total == 2
    assert {r.subject for r in rows} == {"Open", "Waiting"}


def test_due_today_is_not_overdue(db_session: Session) -> None:
    db_session.add(FollowUp(subject="Due Today", due_date=date.today(), status=FollowUpStatus.OPEN.value))
    db_session.commit()

    repo = FollowUpRepository(db_session)
    rows, _total = repo.search(FollowUpFilters(overdue_only=True, open_only=False))
    assert len(rows) == 0

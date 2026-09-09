"""Reconciles alert rule candidates against the ``alerts`` table.

Design: every refresh recomputes the full set of candidates that *should*
currently be active, then for each rule_code:

- a candidate with no matching non-resolved alert row -> insert a new NEW alert
- a candidate matching an existing NEW/ACKNOWLEDGED row -> update its message/
  severity in place (never spawn duplicates for the same condition)
- a candidate matching a SNOOZED row -> leave it alone until the snooze
  expires; the condition is still true, but the coordinator asked not to be
  bothered about it yet
- an existing NEW/ACKNOWLEDGED/SNOOZED row with *no* matching candidate
  anymore -> the underlying problem is gone; mark it RESOLVED automatically

RESOLVED/OBSOLETE rows are left untouched (history, not re-litigated).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.alerts.rules import (
    AlertCandidate,
    late_purchase_order_lines,
    material_shortage_order_lines,
    overdue_follow_ups,
    past_due_order_lines,
    stagnant_production_operations,
    upcoming_due_order_lines,
)
from app.config.constants import AlertStatus
from app.config.settings import AppSettings
from app.models.audit import Alert
from app.models.followup import FollowUp
from app.models.orders import CustomerOrderLine
from app.models.production import ProductionOperation, ProductionOrder
from app.models.purchasing import PurchaseOrderLine

log = logging.getLogger(__name__)

#: Alert statuses still considered "in play" - a rule no longer matching one
#: of these should resolve it; a rule matching one should update it in place.
_ACTIVE_STATUSES = [AlertStatus.NEW.value, AlertStatus.ACKNOWLEDGED.value, AlertStatus.SNOOZED.value]


@dataclass(slots=True)
class AlertRefreshResult:
    """Summary of what one refresh pass did."""

    created: int = 0
    updated: int = 0
    resolved: int = 0
    candidates_evaluated: int = 0


def _collect_candidates(session: Session, settings: AppSettings, as_of: date) -> list[AlertCandidate]:
    open_lines = list(
        session.scalars(
            select(CustomerOrderLine).options(
                joinedload(CustomerOrderLine.customer_order), joinedload(CustomerOrderLine.part)
            )
        )
    )
    po_lines = list(
        session.scalars(
            select(PurchaseOrderLine).options(joinedload(PurchaseOrderLine.purchase_order))
        )
    )
    operations = list(
        session.scalars(
            select(ProductionOperation).options(
                joinedload(ProductionOperation.production_order).joinedload(ProductionOrder.part)
            )
        )
    )
    follow_ups = list(session.scalars(select(FollowUp)))

    candidates: list[AlertCandidate] = []
    candidates.extend(past_due_order_lines(open_lines, settings.alerts, as_of=as_of))
    candidates.extend(upcoming_due_order_lines(open_lines, settings.alerts, as_of=as_of))
    candidates.extend(material_shortage_order_lines(open_lines))
    candidates.extend(late_purchase_order_lines(po_lines, settings.alerts, as_of=as_of))
    candidates.extend(stagnant_production_operations(operations, settings.alerts, as_of=as_of))
    candidates.extend(overdue_follow_ups(follow_ups, settings.alerts, as_of=as_of))
    return candidates


def refresh_alerts(session: Session, settings: AppSettings, *, as_of: date | None = None) -> AlertRefreshResult:
    """Recompute all alert candidates and reconcile them against the ``alerts`` table."""
    as_of = as_of or date.today()
    result = AlertRefreshResult()

    if not settings.alerts.enabled:
        return result

    candidates = _collect_candidates(session, settings, as_of)
    result.candidates_evaluated = len(candidates)
    candidate_keys = {(c.rule_code, c.entity_type, c.entity_id) for c in candidates}

    existing = list(session.scalars(select(Alert).where(Alert.status.in_(_ACTIVE_STATUSES))))
    existing_by_key = {(a.rule_code, a.entity_type, a.entity_id): a for a in existing}

    for candidate in candidates:
        key = (candidate.rule_code, candidate.entity_type, candidate.entity_id)
        existing_alert = existing_by_key.get(key)
        if existing_alert is None:
            session.add(
                Alert(
                    rule_code=candidate.rule_code,
                    entity_type=candidate.entity_type,
                    entity_id=candidate.entity_id,
                    severity=candidate.severity.value,
                    message=candidate.message,
                    status=AlertStatus.NEW.value,
                )
            )
            result.created += 1
        elif existing_alert.status != AlertStatus.SNOOZED.value and (
            existing_alert.message != candidate.message or existing_alert.severity != candidate.severity.value
        ):
            existing_alert.message = candidate.message
            existing_alert.severity = candidate.severity.value
            result.updated += 1

    for key, alert in existing_by_key.items():
        if key not in candidate_keys:
            alert.status = AlertStatus.RESOLVED.value
            alert.resolved_at = datetime.now(UTC)
            result.resolved += 1

    session.commit()
    log.info(
        "Alert refresh: %d candidates, %d created, %d updated, %d auto-resolved",
        result.candidates_evaluated, result.created, result.updated, result.resolved,
    )
    return result

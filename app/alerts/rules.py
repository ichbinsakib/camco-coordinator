"""Alert rule definitions.

Each rule is a pure function: given already-loaded rows and
:class:`app.config.settings.AppSettings`, it yields the alerts that *should*
currently exist. Reconciling that against what's actually stored in the
``alerts`` table (creating new ones, resolving cleared ones, leaving snoozed
ones alone) is :mod:`app.alerts.engine`'s job, not this module's - keeping the
two separate means a rule can be unit-tested with plain Python objects and no
database at all.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date

from app.config.constants import (
    CLOSED_ORDER_STATUSES,
    AlertSeverity,
    EntityType,
    OrderStatus,
)
from app.config.settings import AlertSettings
from app.models.followup import FollowUp
from app.models.orders import CustomerOrderLine
from app.models.production import ProductionOperation
from app.models.purchasing import PurchaseOrderLine


@dataclass(slots=True, frozen=True)
class AlertCandidate:
    """One alert that should currently exist, as computed by a rule."""

    rule_code: str
    entity_type: str
    entity_id: int
    severity: AlertSeverity
    message: str


def past_due_order_lines(
    lines: Iterable[CustomerOrderLine], settings: AlertSettings, *, as_of: date
) -> Iterator[AlertCandidate]:
    """Open order lines already past their due date."""
    for line in lines:
        days_late = line.days_late(as_of)
        if days_late <= 0:
            continue
        severity = AlertSeverity.CRITICAL if days_late >= settings.critical_late_days else AlertSeverity.HIGH
        co_number = line.customer_order.co_number
        part_number = line.part.part_number
        yield AlertCandidate(
            rule_code="ORDER_PAST_DUE",
            entity_type=EntityType.CUSTOMER_ORDER_LINE.value,
            entity_id=line.id,
            severity=severity,
            message=f"CO {co_number} / {part_number} is {days_late} day(s) past due.",
        )


def upcoming_due_order_lines(
    lines: Iterable[CustomerOrderLine], settings: AlertSettings, *, as_of: date
) -> Iterator[AlertCandidate]:
    """Open order lines due within the configured "due soon" window."""
    for line in lines:
        days_until = line.days_until_due(as_of)
        if days_until is None or not (0 <= days_until <= settings.due_soon_days):
            continue
        co_number = line.customer_order.co_number
        part_number = line.part.part_number
        when = "today" if days_until == 0 else f"in {days_until} day(s)"
        yield AlertCandidate(
            rule_code="ORDER_DUE_SOON",
            entity_type=EntityType.CUSTOMER_ORDER_LINE.value,
            entity_id=line.id,
            severity=AlertSeverity.MEDIUM,
            message=f"CO {co_number} / {part_number} is due {when}.",
        )


def material_shortage_order_lines(lines: Iterable[CustomerOrderLine]) -> Iterator[AlertCandidate]:
    """Order lines blocked on material."""
    for line in lines:
        if line.status != OrderStatus.WAITING_MATERIAL.value:
            continue
        co_number = line.customer_order.co_number
        part_number = line.part.part_number
        yield AlertCandidate(
            rule_code="MATERIAL_SHORTAGE",
            entity_type=EntityType.CUSTOMER_ORDER_LINE.value,
            entity_id=line.id,
            severity=AlertSeverity.HIGH,
            message=f"Material for {part_number} (CO {co_number}) has not been received.",
        )


def late_purchase_order_lines(
    lines: Iterable[PurchaseOrderLine], settings: AlertSettings, *, as_of: date
) -> Iterator[AlertCandidate]:
    """Purchase order lines past their promised/required date."""
    for line in lines:
        days_late = line.days_late(as_of)
        if days_late < settings.po_late_days or days_late <= 0:
            continue
        severity = AlertSeverity.CRITICAL if days_late >= settings.critical_late_days else AlertSeverity.HIGH
        po_number = line.purchase_order.po_number
        yield AlertCandidate(
            rule_code="PO_LATE",
            entity_type=EntityType.PURCHASE_ORDER_LINE.value,
            entity_id=line.id,
            severity=severity,
            message=f"PO {po_number} is {days_late} day(s) late.",
        )


def stagnant_production_operations(
    operations: Iterable[ProductionOperation], settings: AlertSettings, *, as_of: date
) -> Iterator[AlertCandidate]:
    """Routing operations that have sat in their current status too long."""
    for operation in operations:
        days = operation.days_in_status(as_of)
        if days < settings.stagnant_operation_days:
            continue
        part_number = operation.production_order.part.part_number
        yield AlertCandidate(
            rule_code="PRODUCTION_STAGNANT",
            entity_type=EntityType.PRODUCTION_OPERATION.value,
            entity_id=operation.id,
            severity=AlertSeverity.HIGH,
            message=(
                f"Part {part_number} has been in {operation.operation_name} "
                f"(OP{operation.sequence}) for {days} day(s)."
            ),
        )


def overdue_follow_ups(
    follow_ups: Iterable[FollowUp], settings: AlertSettings, *, as_of: date
) -> Iterator[AlertCandidate]:
    """Open follow-ups past their due date by the configured grace period."""
    for follow_up in follow_ups:
        if follow_up.due_date is None or not follow_up.is_overdue(as_of):
            continue
        days_over = (as_of - follow_up.due_date).days
        if days_over < settings.followup_overdue_days:
            continue
        yield AlertCandidate(
            rule_code="FOLLOWUP_OVERDUE",
            entity_type=EntityType.FOLLOW_UP.value,
            entity_id=follow_up.id,
            severity=AlertSeverity.MEDIUM,
            message=f'Follow-up "{follow_up.subject}" is overdue.',
        )


#: Statuses excluded when a caller loads candidate order lines for these rules.
OPEN_ORDER_STATUS_VALUES = [s.value for s in CLOSED_ORDER_STATUSES]

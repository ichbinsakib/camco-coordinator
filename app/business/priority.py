"""Automatic priority scoring for customer order lines.

Produces a numeric score and a :class:`Priority` band from a weighted sum of
operational risk factors. All weights and thresholds come from
:class:`app.config.settings.PrioritySettings` - nothing here is a magic number
(rule 36), and a coordinator can retune the algorithm from Settings without a
code change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.config.constants import BLOCKED_ORDER_STATUSES, OrderStatus, Priority
from app.config.settings import PrioritySettings
from app.models.orders import CustomerOrderLine


@dataclass(slots=True)
class PriorityFactors:
    """The inputs that go into a priority score, kept explicit for testability."""

    days_late: int = 0
    days_until_due: int | None = None
    customer_importance: int = 3  # 1 (strategic) .. 5 (low)
    is_blocked: bool = False
    is_waiting_material: bool = False
    has_open_rma: bool = False
    quantity_remaining: float = 0.0
    is_ready_to_ship: bool = False


def score_priority(factors: PriorityFactors, settings: PrioritySettings) -> float:
    """Compute a non-negative priority score from weighted risk factors."""
    score = 0.0

    late_days = min(factors.days_late, settings.max_days_late_considered)
    score += late_days * settings.weight_days_late

    if factors.days_until_due is not None and 0 <= factors.days_until_due <= settings.due_soon_days:
        closeness = settings.due_soon_days - factors.days_until_due + 1
        score += closeness * settings.weight_days_until_due

    # customer_importance: 1 = strategic -> contributes the most.
    importance_factor = max(0, 6 - factors.customer_importance)
    score += importance_factor * settings.weight_customer_importance

    if factors.is_blocked:
        score += settings.weight_blocked
    if factors.is_waiting_material:
        score += settings.weight_material_shortage
    if factors.has_open_rma:
        score += settings.weight_open_rma
    if factors.is_ready_to_ship:
        score += settings.weight_ready_to_ship

    if settings.quantity_reference > 0:
        qty_factor = min(factors.quantity_remaining / settings.quantity_reference, 1.0)
        score += qty_factor * settings.weight_quantity

    return round(score, 2)


def priority_band(score: float, settings: PrioritySettings) -> Priority:
    """Map a numeric score to a :class:`Priority` band using configured cutoffs."""
    if score >= settings.critical_score:
        return Priority.CRITICAL
    if score >= settings.high_score:
        return Priority.HIGH
    if score >= settings.medium_score:
        return Priority.MEDIUM
    return Priority.LOW


def factors_for_order_line(
    line: CustomerOrderLine, *, as_of: date, customer_importance: int, has_open_rma: bool = False
) -> PriorityFactors:
    """Derive :class:`PriorityFactors` from a loaded customer order line."""
    return PriorityFactors(
        days_late=line.days_late(as_of),
        days_until_due=line.days_until_due(as_of),
        customer_importance=customer_importance,
        is_blocked=line.status in {s.value for s in BLOCKED_ORDER_STATUSES},
        is_waiting_material=line.status == OrderStatus.WAITING_MATERIAL.value,
        has_open_rma=has_open_rma,
        quantity_remaining=line.quantity_remaining,
        is_ready_to_ship=line.status == OrderStatus.READY_TO_SHIP.value,
    )


def compute_line_priority(
    line: CustomerOrderLine,
    settings: PrioritySettings,
    *,
    as_of: date,
    customer_importance: int = 3,
    has_open_rma: bool = False,
) -> Priority:
    """Full pipeline: a manual pin wins, otherwise compute and band the score.

    This is the one function the dashboard, reports and alert engine should
    all call, so the "manual override beats computed priority" rule can never
    be re-implemented (and get out of sync) in a second place.
    """
    manual = line.effective_priority()
    if manual is not None:
        return Priority(manual)
    factors = factors_for_order_line(
        line, as_of=as_of, customer_importance=customer_importance, has_open_rma=has_open_rma
    )
    score = score_priority(factors, settings)
    return priority_band(score, settings)

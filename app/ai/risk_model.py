"""Predictive delivery risk: "how likely is this open order line to ship late?"

Two components, blended, and always kept visibly separate from ground truth:

1. A **learned base rate** - a small logistic regression
   (:mod:`app.ai.logistic_model`) trained on this database's own historical
   shipped order lines (label: did it ship after its due date). Features are
   ones knowable from a line's static attributes (customer importance,
   quantity, whether the due date was ever pushed out) - deliberately *not*
   current live status, because a shipped historical line's status is always
   a closed one and would teach the model nothing.
2. A **real-time rule-based adjustment** - the same kind of deterministic
   signal the alert/priority engines already use (currently blocked on
   material, a stagnant production operation, a late linked PO) - applied on
   top of the learned base rate for an *open* line, since that's exactly the
   information the historical training set structurally cannot capture.

If there isn't enough shipped history to train on, the learned component is
skipped entirely and the result says so - the rule-based adjustment alone
still produces a usable, honestly-labeled estimate (spec rule 28: never let
a prediction masquerade as more certain than it is).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.logistic_model import LogisticModel, train_logistic_model
from app.config.constants import BLOCKED_ORDER_STATUSES, CLOSED_ORDER_STATUSES, OrderStatus
from app.config.paths import app_home
from app.config.settings import AppSettings
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.production import ProductionOrder
from app.models.purchasing import PurchaseOrderLine
from app.models.shipping import ShipmentLine

log = logging.getLogger(__name__)

FEATURE_NAMES = ["customer_importance", "quantity_log", "was_rescheduled"]

#: Below this many labeled historical examples, the learned component is
#: skipped rather than trained on a sample too small to mean anything.
MIN_TRAINING_SAMPLES = 20

#: Points added to the base probability's logit-equivalent score (0-100
#: scale, additive - simple and explainable, not another learned weight).
_ADJUSTMENT_BLOCKED = 20
_ADJUSTMENT_MATERIAL_WAIT = 15
_ADJUSTMENT_STAGNANT_OP = 20
_ADJUSTMENT_LATE_LINKED_PO = 25
_ADJUSTMENT_PAST_DUE_ALREADY = 30


def _model_path() -> Path:
    return app_home() / "ai" / "delivery_risk_model.json"


def save_model(model: LogisticModel) -> None:
    """Persist a trained model to the application-data directory."""
    path = _model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")


def load_model() -> LogisticModel | None:
    """Load a previously trained model, or ``None`` if none exists yet."""
    path = _model_path()
    if not path.exists():
        return None
    try:
        return LogisticModel.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError):
        log.exception("Could not load saved delivery-risk model; will retrain from scratch")
        return None


def _quantity_log(quantity: float) -> float:
    return math.log(max(quantity, 0.0) + 1.0)


def _static_features(customer_importance: int, quantity_ordered: float, was_rescheduled: bool) -> dict[str, float]:
    return {
        "customer_importance": float(customer_importance),
        "quantity_log": _quantity_log(quantity_ordered),
        "was_rescheduled": 1.0 if was_rescheduled else 0.0,
    }


def build_training_examples(session: Session) -> list[tuple[dict[str, float], int]]:
    """Historical (features, label) pairs from shipped order lines.

    Label is 1 if the line's shipment(s) completed after its due date - the
    same "on time" definition the Shipping page's analytics already use
    (:func:`app.repositories.shipping.ShipmentRepository.on_time_percentage`),
    so the model's notion of "late" matches what a coordinator sees on that
    screen.
    """
    stmt = (
        select(CustomerOrderLine)
        .join(CustomerOrderLine.customer_order)
        .join(CustomerOrder.customer)
        .options(joinedload(CustomerOrderLine.customer_order).joinedload(CustomerOrder.customer))
    )
    lines = session.scalars(stmt).unique().all()

    examples: list[tuple[dict[str, float], int]] = []
    for line in lines:
        if line.due_date is None:
            continue
        ship_dates = [
            sl.shipment.ship_date
            for sl in session.scalars(
                select(ShipmentLine)
                .join(ShipmentLine.shipment)
                .where(ShipmentLine.customer_order_line_id == line.id)
            )
            if sl.shipment and sl.shipment.ship_date
        ]
        if not ship_dates:
            continue
        latest_ship_date = max(ship_dates)
        label = 1 if latest_ship_date > line.due_date else 0
        was_rescheduled = line.original_due_date is not None and line.original_due_date != line.due_date
        features = _static_features(line.customer_order.customer.importance, line.quantity_ordered, was_rescheduled)
        examples.append((features, label))
    return examples


def train_and_save(session: Session) -> LogisticModel | None:
    """Train on current historical data and persist the model. ``None`` if too little data."""
    examples = build_training_examples(session)
    if len(examples) < MIN_TRAINING_SAMPLES:
        log.info("Only %d historical shipped lines - skipping model training (need %d)", len(examples), MIN_TRAINING_SAMPLES)
        return None
    model = train_logistic_model(FEATURE_NAMES, examples)
    save_model(model)
    log.info("Trained delivery-risk model on %d historical examples", len(examples))
    return model


@dataclass(slots=True)
class RiskAdjustment:
    """One explainable reason the real-time score moved, and by how much."""

    reason: str
    points: int


@dataclass(slots=True)
class DeliveryRiskResult:
    """A single order line's predicted delivery risk - never confused with its actual status."""

    line_id: int
    base_probability: float | None  # None if the learned component was skipped
    score: float  # 0-100, blended base rate + real-time adjustments
    band: str  # LOW / MEDIUM / HIGH / CRITICAL
    adjustments: list[RiskAdjustment] = field(default_factory=list)
    used_learned_model: bool = False


def _band_for_score(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def predict_risk(
    line: CustomerOrderLine,
    model: LogisticModel | None,
    session: Session,
    *,
    as_of: date | None = None,
) -> DeliveryRiskResult:
    """Predict delivery risk for one open order line.

    Blends the learned base rate (if a model is available) with real-time
    deterministic adjustments; the adjustments alone are returned as a
    reasonable estimate when there's no trained model yet.
    """
    as_of = as_of or date.today()
    base_probability: float | None = None
    score = 0.0

    if model is not None:
        was_rescheduled = line.original_due_date is not None and line.original_due_date != line.due_date
        features = _static_features(line.customer_order.customer.importance, line.quantity_ordered, was_rescheduled)
        base_probability = model.predict_proba(features)
        score = base_probability * 100.0

    adjustments: list[RiskAdjustment] = []

    if line.status in {s.value for s in BLOCKED_ORDER_STATUSES}:
        adjustments.append(RiskAdjustment(f"Order is currently {line.status}", _ADJUSTMENT_BLOCKED))
    if line.status == OrderStatus.WAITING_MATERIAL.value:
        adjustments.append(RiskAdjustment("Waiting on material", _ADJUSTMENT_MATERIAL_WAIT))

    days_late = line.days_late(as_of)
    if days_late > 0:
        adjustments.append(RiskAdjustment(f"Already {days_late} day(s) past due", _ADJUSTMENT_PAST_DUE_ALREADY))

    production_order = session.scalar(
        select(ProductionOrder).where(ProductionOrder.customer_order_line_id == line.id)
    )
    if production_order is not None:
        current_op = production_order.current_operation
        if current_op is not None:
            days_in_status = current_op.days_in_status(as_of)
            if days_in_status >= 10:
                adjustments.append(
                    RiskAdjustment(f"Stuck in {current_op.operation_name} for {days_in_status} day(s)", _ADJUSTMENT_STAGNANT_OP)
                )

    late_po = session.scalar(
        select(PurchaseOrderLine).where(PurchaseOrderLine.customer_order_line_id == line.id)
    )
    if late_po is not None and late_po.days_late(as_of) > 0:
        adjustments.append(
            RiskAdjustment(f"Linked PO is {late_po.days_late(as_of)} day(s) late", _ADJUSTMENT_LATE_LINKED_PO)
        )

    score = min(score + sum(a.points for a in adjustments), 100.0)

    return DeliveryRiskResult(
        line_id=line.id,
        base_probability=base_probability,
        score=round(score, 1),
        band=_band_for_score(score),
        adjustments=adjustments,
        used_learned_model=model is not None,
    )


def predict_risk_for_open_lines(
    session: Session, settings: AppSettings, *, as_of: date | None = None
) -> list[DeliveryRiskResult]:
    """Predict delivery risk for every open (not closed) customer order line."""
    model = load_model()
    closed_values = [s.value for s in CLOSED_ORDER_STATUSES]
    stmt = (
        select(CustomerOrderLine)
        .join(CustomerOrderLine.customer_order)
        .join(CustomerOrder.customer)
        .where(CustomerOrderLine.status.notin_(closed_values))
        .options(joinedload(CustomerOrderLine.customer_order).joinedload(CustomerOrder.customer))
    )
    lines = session.scalars(stmt).unique().all()
    results = [predict_risk(line, model, session, as_of=as_of) for line in lines]
    results.sort(key=lambda r: r.score, reverse=True)
    return results

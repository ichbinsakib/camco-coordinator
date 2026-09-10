"""Smart Search: a deterministic natural-language query parser (spec section 28).

Keyword-rule based, not an LLM - the spec's own examples ("Which parts are
waiting for material?", "Which POs are overdue?") are exactly the kind of
fixed vocabulary a small rule set covers well, and a rule set has none of an
LLM's dependency weight, latency, or hallucination risk. Every match is
reported back as a plain-English "interpreted this as..." line so the
mapping is never a black box (spec rule 28's transparency requirement,
applied to search the same way it applies to risk scoring).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.risk_model import predict_risk_for_open_lines
from app.config.constants import OrderStatus
from app.config.settings import AppSettings, RmaSettings
from app.repositories.customer_orders import CustomerOrderRepository, OrderLineFilters
from app.repositories.followups import FollowUpFilters, FollowUpRepository
from app.repositories.purchasing import (
    PurchaseLineFilters,
    PurchaseOrderRepository,
)
from app.repositories.rma import RmaFilters, RmaRepository


@dataclass(slots=True)
class SmartSearchResult:
    """A parsed-and-executed smart-search query, with a human-readable explanation."""

    interpretation: str
    target: str  # "customer_order_lines" | "purchase_order_lines" | "rmas" | "follow_ups"
    rows: list = field(default_factory=list)


def _mentions_any(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)


def _this_month_range(as_of: date) -> tuple[date, date]:
    start = as_of.replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month - timedelta(days=1)
    return start, end


def _this_week_range(as_of: date) -> tuple[date, date]:
    start = as_of - timedelta(days=as_of.weekday())
    return start, start + timedelta(days=6)


def run_smart_search(session: Session, text: str, settings: AppSettings, *, as_of: date | None = None) -> SmartSearchResult:
    """Parse a natural-language query and execute it against the matching repository."""
    as_of = as_of or date.today()
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())

    likely_late = _mentions_any(normalized, "likely to be late", "at risk", "risk of being late", "predicted late")
    late = likely_late or _mentions_any(normalized, "late", "overdue", "past due", "behind")
    waiting_material = _mentions_any(normalized, "material", "waiting on material", "waiting for material")

    date_range: tuple[date, date] | None = None
    range_label = ""
    if "this month" in normalized:
        date_range = _this_month_range(as_of)
        range_label = " this month"
    elif "this week" in normalized:
        date_range = _this_week_range(as_of)
        range_label = " this week"
    elif "today" in normalized:
        date_range = (as_of, as_of)
        range_label = " today"

    if _mentions_any(normalized, "purchase order", " po ", " po", "po ") and not waiting_material:
        return _search_purchase_orders(session, late, date_range, range_label)
    if "rma" in normalized:
        return _search_rmas(session, late, range_label)
    if _mentions_any(normalized, "follow up", "followup", "follow-up"):
        return _search_follow_ups(session, late, range_label)

    # Default target: customer order lines - covers "parts waiting for
    # material", "customer orders likely to be late", and the bare fallback.
    return _search_customer_orders(session, settings, late, likely_late, waiting_material, date_range, range_label, as_of)


def _search_customer_orders(
    session: Session,
    settings: AppSettings,
    late: bool,
    likely_late: bool,
    waiting_material: bool,
    date_range: tuple[date, date] | None,
    range_label: str,
    as_of: date,
) -> SmartSearchResult:
    if likely_late:
        risk_results = predict_risk_for_open_lines(session, settings, as_of=as_of)
        high_risk_ids = {r.line_id for r in risk_results if r.band in ("HIGH", "CRITICAL")}
        repo = CustomerOrderRepository(session)
        filters = OrderLineFilters(open_only=True)
        if date_range:
            filters.due_after, filters.due_before = date_range
        rows, _total = repo.search_lines(filters, settings.priority, as_of=as_of, limit=500)
        rows = [r for r in rows if r.line.id in high_risk_ids]
        interpretation = f"Customer order lines predicted likely to ship late{range_label} (AI risk: HIGH or CRITICAL)."
        return SmartSearchResult(interpretation, "customer_order_lines", rows)

    status = OrderStatus.WAITING_MATERIAL.value if waiting_material else None
    filters = OrderLineFilters(open_only=True, status=status)
    if date_range:
        filters.due_after, filters.due_before = date_range

    repo = CustomerOrderRepository(session)
    rows, _total = repo.search_lines(filters, settings.priority, as_of=as_of, limit=500)
    if late:
        rows = [r for r in rows if r.days_late > 0]

    parts = []
    if waiting_material:
        parts.append("waiting on material")
    if late:
        parts.append("past due")
    if date_range and not late and not waiting_material:
        parts.append(f"due{range_label}")
    description = " and ".join(parts) if parts else "open"
    return SmartSearchResult(f"Customer order lines that are {description}.", "customer_order_lines", rows)


def _search_purchase_orders(
    session: Session, late: bool, date_range: tuple[date, date] | None, range_label: str
) -> SmartSearchResult:
    filters = PurchaseLineFilters(open_only=True, late_only=late)
    repo = PurchaseOrderRepository(session)
    rows, _total = repo.search_lines(filters, limit=500)
    if date_range:
        rows = [r for r in rows if r.line.required_date and date_range[0] <= r.line.required_date <= date_range[1]]
    description = "late" if late else "open"
    return SmartSearchResult(f"Purchase order lines that are {description}{range_label}.", "purchase_order_lines", rows)


def _search_rmas(session: Session, late: bool, range_label: str) -> SmartSearchResult:
    repo = RmaRepository(session)
    filters = RmaFilters(open_only=True)
    rows, _total = repo.search(filters, RmaSettings(), limit=500)
    return SmartSearchResult("Open RMAs.", "rmas", rows)


def _search_follow_ups(session: Session, late: bool, range_label: str) -> SmartSearchResult:
    repo = FollowUpRepository(session)
    filters = FollowUpFilters(open_only=True, overdue_only=late)
    rows, _total = repo.search(filters, limit=500)
    description = "overdue" if late else "open"
    return SmartSearchResult(f"Follow-ups that are {description}.", "follow_ups", rows)

"""Recurring bottleneck detection (spec section 28).

Deterministic historical-statistics analysis, not a learned model - the
question ("which operation recurringly causes delays") is answered
perfectly well by aggregating actual completed-operation durations, so
there's no reason to reach for ML here (rule 63). This complements
:func:`app.repositories.analytics.bottleneck_operations`, which only counts
*currently* stuck operations; this looks at completed history to say
whether an operation is recurringly slow, not just slow right now.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constants import CLOSED_PRODUCTION_STATUSES
from app.models.production import ProductionOperation


@dataclass(slots=True)
class RecurringBottleneck:
    """One operation name's historical duration profile across every order it appeared on."""

    operation_name: str
    completed_count: int
    average_duration_days: float
    max_duration_days: int
    currently_stuck_count: int


def recurring_bottlenecks(session: Session, *, as_of: date | None = None, min_samples: int = 2) -> list[RecurringBottleneck]:
    """Rank operation names by how consistently slow they've been historically.

    ``min_samples`` filters out operations that have only completed once or
    twice - not enough history to call "recurring" rather than a one-off.
    """
    as_of = as_of or date.today()

    all_ops = list(session.scalars(select(ProductionOperation)))
    durations: dict[str, list[int]] = defaultdict(list)
    for op in all_ops:
        if op.start_date and op.actual_completion_date and op.actual_completion_date >= op.start_date:
            durations[op.operation_name].append((op.actual_completion_date - op.start_date).days)

    closed_values = {s.value for s in CLOSED_PRODUCTION_STATUSES}
    stuck_counts: dict[str, int] = defaultdict(int)
    for op in all_ops:
        if op.status not in closed_values and op.days_in_status(as_of) >= 5:
            stuck_counts[op.operation_name] += 1

    results = [
        RecurringBottleneck(
            operation_name=name,
            completed_count=len(days),
            average_duration_days=round(sum(days) / len(days), 1),
            max_duration_days=max(days),
            currently_stuck_count=stuck_counts.get(name, 0),
        )
        for name, days in durations.items()
        if len(days) >= min_samples
    ]
    results.sort(key=lambda r: r.average_duration_days, reverse=True)
    return results

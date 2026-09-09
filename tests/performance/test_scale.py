"""Performance/scale tests against ~100k rows (spec rule 30: 100,000+ records).

Excluded from the default test run (`pytest -m "not slow"`, the project
default) because seeding 100k+ rows takes real time; run explicitly with:

    pytest -m slow tests/performance -v

These assert wall-clock ceilings generous enough to catch a real regression
(e.g. a missing index turning an O(n) scan into the query) without being
flaky on a slower CI runner - they are a smoke test for "did an index or a
pagination limit get lost", not a strict benchmark.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.config.constants import OrderStatus
from app.config.settings import PrioritySettings
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.repositories.customer_orders import CustomerOrderRepository, OrderLineFilters
from app.repositories.dashboard import get_dashboard_counts

pytestmark = pytest.mark.slow

_ROW_COUNT = 100_000
_MAX_QUERY_SECONDS = 3.0


def _seed_large_dataset(session: Session, row_count: int) -> None:
    """Bulk-insert customers, parts and order lines without the ORM's per-row overhead."""
    customer_count = 200
    part_count = 2000

    session.bulk_insert_mappings(
        Customer, [{"code": f"CUST{i:05d}", "name": f"Customer {i}", "importance": (i % 5) + 1} for i in range(customer_count)]
    )
    session.bulk_insert_mappings(
        Part, [{"part_number": f"PN{i:06d}", "revision": "A"} for i in range(part_count)]
    )
    session.commit()

    customer_ids = [row[0] for row in session.execute(Customer.__table__.select().with_only_columns(Customer.id))]
    part_ids = [row[0] for row in session.execute(Part.__table__.select().with_only_columns(Part.id))]

    order_count = row_count // 5
    session.bulk_insert_mappings(
        CustomerOrder,
        [
            {"co_number": f"CO-{i:06d}", "customer_id": customer_ids[i % customer_count]}
            for i in range(order_count)
        ],
    )
    session.commit()

    order_ids = [row[0] for row in session.execute(CustomerOrder.__table__.select().with_only_columns(CustomerOrder.id))]

    today = date.today()
    statuses = [s.value for s in OrderStatus]
    lines = []
    for i in range(row_count):
        due_offset = (i % 90) - 30  # spread across ~30 days past due to ~60 days out
        lines.append(
            {
                "customer_order_id": order_ids[i % order_count],
                "line_number": (i // order_count) + 1,
                "part_id": part_ids[i % part_count],
                "quantity_ordered": 10 + (i % 90),
                "quantity_completed": i % 10,
                "due_date": today + timedelta(days=due_offset),
                "status": statuses[i % len(statuses)],
            }
        )
        if len(lines) >= 5000:
            session.bulk_insert_mappings(CustomerOrderLine, lines)
            lines = []
    if lines:
        session.bulk_insert_mappings(CustomerOrderLine, lines)
    session.commit()


@pytest.fixture(scope="module")
def large_db_session(tmp_path_factory: pytest.TempPathFactory) -> Session:
    """A module-scoped 100k-row database - built once, reused by every test in this file."""
    from app.database.session import get_session_factory, init_database, reset_engine

    tmp_dir = tmp_path_factory.mktemp("perf")
    db_url = f"sqlite:///{(tmp_dir / 'perf.db').as_posix()}"
    init_database(db_url)
    session = get_session_factory()()
    _seed_large_dataset(session, _ROW_COUNT)
    yield session
    session.close()
    reset_engine()


def test_dashboard_counts_completes_quickly(large_db_session: Session) -> None:
    start = time.perf_counter()
    counts = get_dashboard_counts(large_db_session)
    elapsed = time.perf_counter() - start
    assert counts.open_customer_orders > 0
    assert elapsed < _MAX_QUERY_SECONDS, f"Dashboard counts took {elapsed:.2f}s against {_ROW_COUNT} rows"


def test_order_line_search_is_paginated_not_full_scan(large_db_session: Session) -> None:
    repo = CustomerOrderRepository(large_db_session)
    start = time.perf_counter()
    rows, total = repo.search_lines(OrderLineFilters(open_only=False), PrioritySettings(), limit=100, offset=0)
    elapsed = time.perf_counter() - start
    assert len(rows) == 100
    assert total >= _ROW_COUNT * 0.9  # allow for status distribution rounding
    assert elapsed < _MAX_QUERY_SECONDS, f"Paginated order line search took {elapsed:.2f}s"


def test_order_line_search_deep_page_still_fast(large_db_session: Session) -> None:
    """A page far into the result set should still be fast - no client-side skip-scan."""
    repo = CustomerOrderRepository(large_db_session)
    start = time.perf_counter()
    rows, _total = repo.search_lines(
        OrderLineFilters(open_only=False), PrioritySettings(), limit=100, offset=_ROW_COUNT - 200
    )
    elapsed = time.perf_counter() - start
    assert len(rows) > 0
    assert elapsed < _MAX_QUERY_SECONDS, f"Deep-page order line search took {elapsed:.2f}s"


def test_text_search_uses_indexed_columns(large_db_session: Session) -> None:
    repo = CustomerOrderRepository(large_db_session)
    start = time.perf_counter()
    _rows, total = repo.search_lines(
        OrderLineFilters(text="CO-000123", open_only=False), PrioritySettings(), limit=100
    )
    elapsed = time.perf_counter() - start
    assert total >= 1
    assert elapsed < _MAX_QUERY_SECONDS, f"Text search took {elapsed:.2f}s"

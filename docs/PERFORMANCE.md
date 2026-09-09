# Performance Notes

Spec rule 30 requires the application to handle 100,000+ records without
loading everything into the UI at once. `tests/performance/test_scale.py`
seeds 100,000 customer order lines (20,000 orders, 200 customers, 2,000
parts) and asserts every key query stays under a generous ceiling; it's
excluded from the default `pytest` run (slow) and runs explicitly with:

```bash
pytest -m slow tests/performance -v
```

## Measured results (100,000 order lines, local SQLite/WAL, dev machine)

| Operation | Time |
|---|---|
| Seed 100k lines (bulk insert) | ~1.1s |
| Dashboard KPI counts (7 aggregate queries) | ~97ms |
| Paginated order-line search, page 1 (100 rows) | ~21ms |
| Paginated order-line search, deep page (near row 100,000) | ~430ms |
| Free-text search across CO/part/customer | ~510ms |
| Status-filtered search (`open_only`) | ~33ms |

Everything is well under a "the UI never freezes" bar; there are two
findings worth tracking as the real dataset grows past 100k, though neither
blocks Phase 7:

1. **Deep-page OFFSET pagination is O(n).** SQLite (like most databases)
   has to walk past every skipped row for a large `OFFSET`, so the last
   page of a 100k-row result is ~20x slower than the first. This only
   matters if a coordinator actually pages deep into an unfiltered 100k-row
   list, which the UI's default filters (open-only, status) make unlikely
   in practice. If it becomes a real problem, the fix is keyset pagination
   (`WHERE due_date > :last_seen_due_date` instead of `OFFSET`) on the
   hottest list - `app/repositories/customer_orders.py`'s `search_lines`.
2. **Free-text `ILIKE` search has no index to use.** A substring match
   across CO number, customer name and part number can't use a B-tree
   index, so it degrades toward a full scan as row count grows. Still
   comfortably sub-second at 100k rows. If it needs to get faster, SQLite's
   FTS5 virtual table is the natural next step (a dedicated search index
   updated via triggers) - out of scope unless real usage shows it's
   needed.

## Why SQLite/WAL is adequate here

`app/database/session.py` sets `PRAGMA journal_mode=WAL` and
`PRAGMA foreign_keys=ON` on every connection. WAL allows concurrent readers
alongside a single writer, which matches this application's actual
concurrency profile (one coordinator's desktop session, occasionally two
people on a shared network drive - not a multi-tenant server). If usage
ever grows past what a single SQLite file comfortably serves, the
architecture doc (`docs/ARCHITECTURE.md`) already covers the migration
path: swap the SQLAlchemy URL to PostgreSQL/SQL Server and replay the
existing Alembic migration chain - no application code above
`app/database/session.py` assumes SQLite-specific behavior.

# Implementation Roadmap

Phases follow the master spec's section 59, with concrete deliverables per
phase so each one lands as a working, tested increment - never a rewrite of
what came before (spec rule 62).

## Phase 1 — Foundation ✅ COMPLETE

- Clean architecture (`app/config`, `database`, `models`, `repositories`,
  `business`, `services`, `security`, `ui`, `utils`)
- Full Phase-1 database schema (customers, vendors, parts, customer/sales
  orders, production, purchasing, shipping, RMA, follow-ups, notes, activity
  log, alerts, import batches) with SQLAlchemy 2.0 + SQLite (WAL, FK
  enforcement)
- `AppSettings` - every business threshold configurable and persisted
  (`settings.json` under `%LOCALAPPDATA%`)
- Application shell: sidebar navigation across all 15 planned modules,
  themeable (light/dark) QSS, window-geometry persistence
- Local authentication: PBKDF2 password hashing, lockout policy, roles
  (ADMIN/COORDINATOR/VIEWER), default-admin bootstrap
- Rotating file logging + global exception hook (never a silent crash)
- Database backup/restore service (timestamped, never overwrites, retention
  pruning, pre-restore safety backup)
- Priority engine (`app/business/priority.py`) - configurable weighted score
  -> CRITICAL/HIGH/MEDIUM/LOW, with manual-pin override
- Dashboard KPI cards wired to real aggregate queries
- 44 passing pytest tests (unit + integration) covering date-math edge
  cases, priority scoring, RMA aging, calendar math, settings persistence,
  auth, and backup/restore
- PyInstaller spec + Inno Setup script scaffolding

## Phase 2 — Core records ✅ COMPLETE

- Repositories for Customers, Vendors, Parts (search/pagination) and Customer
  Orders (line-level search/filter joining CO + Customer + Part, plus
  `get_or_create_order` for idempotent header creation)
- Reusable list-page scaffold (`app/ui/widgets/list_page_base.py` +
  `table_model.py`) - search box, entity-specific filter slot, sortable-look
  table, New/Edit/Delete toolbar (hidden entirely for VIEWER role),
  pagination - so every master-data page is "define columns + a loader",
  not a hand-rolled `QAbstractTableModel`
- Customers, Vendors, Parts pages: full CRUD with edit dialogs, delete
  protection when referenced by other records (suggests deactivation
  instead), every change written to the activity log
- Customer Orders page: line-level worklist (spec section 13) showing
  computed remaining qty, days-late/due, and live-computed priority
  (colored via the same `AppSettings.status_colors` the dashboard uses) -
  status filter (Open Only / All / specific status), new-line creation that
  creates the CO header on first use of a CO number
- Alembic initialized against the Phase 1 schema; `init_database()` now
  stamps a fresh database at head and upgrades/stamps an existing one
  automatically, so future schema changes ship as real migrations instead of
  ever requiring a user to delete their database (rule 62)
- 53 passing tests (9 new: master-data repository search/pagination, CO line
  filtering, Alembic stamp/upgrade wiring)

## Phase 3 — Production / Purchasing / Shipping ✅ COMPLETE

- Repositories: `ProductionOrderRepository` (resolves each order's *current*
  operation - the first not-yet-complete routing step - plus
  `stagnant_operations()` for the alert engine in Phase 4),
  `PurchaseOrderRepository` (line-level search/filter, late-only), and
  `ShipmentRepository` (line-level search plus `on_time_percentage()` over a
  date range)
- Production page: list of production orders showing current operation, its
  status, and days-in-status; "Manage Operations" dialog to add/edit/delete
  routing steps (OP10, OP20, ...) - `status_since` resets automatically
  whenever an operation's status changes, which is what "days in status"
  measures
- Purchasing page: line-level worklist (PO/vendor/part/qty/dates/days
  late/buyer) with status and Late-Only filters - the vendor follow-up list
  the spec asks for
- Shipping page: shipment list plus an on-time-% analytics panel with a
  range picker (current/previous month, 3/6/12/24/36/48/60 months, spec
  section 16); adding a shipment line auto-transitions the customer order
  line to SHIPPED once its full ordered quantity has gone out
- 14 new repository tests (current-operation resolution, stagnation
  threshold, late-PO filtering, on-time-% with on-time/late/unknown lines,
  every standard date-range calculation) - 67 passing tests total

## Phase 4 — RMA / Follow-ups / Alerts / Notes ✅ COMPLETE

- `RmaRepository`: search/filter plus `aging_bucket_label()` - RMA age is
  always shown in months against the configurable bucket edges in
  `RmaSettings.aging_buckets_months` (spec section 17), never raw days
- `FollowUpRepository`: search/filter with an overdue-only view
- RMAs and Follow-Ups pages: full CRUD, closing an RMA/follow-up
  auto-stamps its completion/last-contacted date
- Alert engine (`app/alerts/`): `rules.py` holds pure rule functions (past
  due, due soon, material shortage, late PO, stagnant production operation,
  overdue follow-up) over the *same* business logic the dashboard and
  priority engine use - `engine.py` reconciles rule output against the
  `alerts` table (create new, update in place, leave snoozed alone,
  auto-resolve when the underlying condition clears - never a duplicate
  alert for the same condition)
- Alerts page: severity filter, "Refresh Alerts" to run the engine on
  demand, Acknowledge / Snooze (configurable days) / Resolve
- Notes: one reusable `NotesDialog` (spec rule 22) wired onto every list
  page that has an entity worth annotating - Parts, Customers, Vendors,
  Customer Order lines, Purchase Order lines, RMAs, Follow-Ups - rather than
  a bespoke notes UI per page
- 13 new tests (RMA aging-bucket boundaries, follow-up overdue filtering,
  and 8 alert-engine tests covering creation, severity escalation,
  idempotent re-runs, auto-resolution, snooze protection, the
  enabled/disabled switch, and the material-shortage rule) - 80 passing
  tests total
- Bug caught by the full-app smoke test (not the unit suite) and fixed:
  `RmaRepository.search` wasn't eager-loading `Rma.part`, which crashed the
  RMA list's Part column with a `DetachedInstanceError` once the session
  closed

## Phase 5 — Dashboard analytics / Reports ✅ COMPLETE

- `app/repositories/analytics.py`: seven aggregate queries, each answering
  one operational question (spec rule 46) - orders by status, past-due
  backlog by age, production workload by department, vendor on-time %,
  RMA aging distribution, monthly order volume, top bottleneck operations
- Analytics page: a QtCharts bar-chart grid over those seven queries,
  refreshable on demand
- `app/reports/`: a format-agnostic `Report`/`ReportSection` model, five
  builders (Daily Coordinator, Customer Order, Vendor Performance, On-Time
  Shipment, RMA Aging, Management Summary - six total) that reuse the exact
  same repositories and business rules as the live pages, and three
  exporters (Excel via openpyxl - one sheet per section; PDF via reportlab -
  one styled table per section; CSV - one file per section)
- Reports page: pick a report, pick a format, generate to the configured
  report output folder
- 20 new tests (six analytics-query tests, four report-builder tests, six
  exporter tests) - 94 passing tests total
- Weekly Production Report was intentionally folded into the Production
  page + Analytics workload chart rather than built as a seventh static
  report - see `docs/ASSUMPTIONS.md` item 11

## Phase 6 — Excel/CSV import engine ✅ COMPLETE

- `app/imports/readers.py`: read-only .xlsx/.xlsm/.csv access (source files
  are never written to, spec rule 55), with best-effort date/number
  coercion covering both Excel-native and manually-typed values
- `app/imports/fields.py`: one `ImportTarget` per importable entity -
  Customers, Vendors, Parts, Customer Order Lines ("master schedule"),
  Purchase Order Lines - each field typed (text/number/date/enum) and
  optionally required, with header aliases for auto-mapping
- `app/imports/engine.py`: `auto_map_columns` (best-guess column mapping by
  header name), `build_preview` (parses + validates every row, producing
  plain-language errors like "Row 143: Due Date - 'xyz' is not a valid
  date", never a raw exception - spec rule 24), `commit_import` (writes
  valid rows via per-target insert-or-update loaders, wrapped in one
  `ImportBatch` with row-level `ImportRowError`s logged for anything
  skipped; each row commits inside its own SAVEPOINT so one bad row can't
  sink the rest of the batch)
- `ImportWizardDialog`: file -> sheet -> mapping (auto-filled, adjustable) ->
  validate/preview (invalid rows highlighted) -> confirm -> commit, wired
  onto the Customers, Vendors, Parts, Customer Orders and Purchasing pages'
  toolbars
- 15 engine/reader tests, 4 `pytest-qt` widget tests exercising the real
  dialog end-to-end (added `tests/ui/`, first use of the `pytest-qt`
  dependency declared back in Phase 1) - 113 passing tests total
- Two real bugs found and fixed via the pytest-qt tests and full-app smoke
  test (not the pure-function unit tests): the mapping combo boxes were
  built once before any file was loaded and never rebuilt once headers
  became known; and a per-row commit failure wasn't being counted into the
  batch's reported error total

## Phase 7 — Testing / performance / security hardening ✅ COMPLETE

- `tests/performance/test_scale.py`: seeds and queries a 100,000-row
  dataset (spec rule 30), excluded from the default run (`-m "not slow"`)
  and runnable on demand with `pytest -m slow tests/performance`. Results
  and two follow-up findings (deep-page OFFSET cost, unindexed free-text
  search) written up in `docs/PERFORMANCE.md` - both acceptable at 100k
  rows today, with a documented fix path if usage outgrows them
- `pytest-qt` UI tests (`tests/ui/`): drive real dialogs end-to-end rather
  than only their pure-function backends. These caught two real bugs the
  pure unit tests couldn't see (Phase 6's mapping-combo rebuild bug and the
  idle-lock wiring) precisely because they exercise actual Qt signal/slot
  behavior
- Security review (`docs/SECURITY.md`): password hashing/lockout,
  SQL-injection surface (none found - everything goes through SQLAlchemy's
  parameterized query builder), import-file handling (read-only, no macro
  execution), and the role-enforcement trust boundary (UI-layer today,
  documented as needing to move to a service layer before any future
  multi-user/network deployment)
- Found and fixed a real gap during the review: `SecuritySettings.session_idle_minutes`
  existed since Phase 1 but was never enforced. Implemented as
  `app/ui/idle_lock.py` (pure, unit-tested `IdleTracker` + a thin
  `IdleWatcher` Qt wrapper) and `LockScreenDialog` (un-dismissible except by
  re-entering the current user's password), wired into `MainWindow` and
  exposed on a new Settings > Security tab; off by default so no existing
  behavior changes
- 12 new tests (6 idle-lock unit, 2 idle-lock `pytest-qt`, 4 performance) -
  125 passing tests total (121 default + 4 slow)

## Phase 8 — EXE packaging / installer / deployment ⚙️ MOSTLY COMPLETE

- Built the real PyInstaller executable (`python scripts\build_exe.py`) and
  smoke-tested it - launched the actual frozen `.exe` headlessly, confirmed
  via its log file and the resulting SQLite database that it created its
  full 21-table schema, stamped the Alembic revision, and bootstrapped the
  default admin account, all cleanly
- Found and fixed a real packaging bug this way (not something a source-level
  test could ever catch): PyInstaller's import scanner missed
  `logging.config`/`logging.handlers`, which silently broke the bundled
  Alembic env's migration-stamping step on every fresh install. Added both
  to `hiddenimports`, rebuilt, re-verified clean. Written up in
  `docs/PACKAGING.md`
- **Not yet done**: verification on a clean Windows machine with no Python
  installed (this dev environment has Python, so that specific claim is
  architecturally true but unproven), and compiling/testing the Inno Setup
  installer (Inno Setup isn't installed in this environment) - both listed
  as concrete next steps in `docs/PACKAGING.md`

## Phase 9 — Optional AI/ML (only after Phase 1-8 are stable)

- Predictive late-order risk, bottleneck detection, delivery-risk scoring -
  always shown as "Predicted Risk," never merged into or replacing "Actual
  Status" (spec rule 28)
- Disabled by default (`AiSettings.enabled = False`); the app is fully
  functional with AI off

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

## Phase 4 — RMA / Follow-ups / Alerts / Notes

- RMA module with month-based aging buckets
- Follow-up management (subject, related records, communication method,
  next-follow-up date)
- Alert engine (`app/alerts/`) built on the same business rules as the
  dashboard/priority engine - past due, upcoming, material, vendor,
  production-stagnation alerts, with acknowledge/snooze/resolve
- Notes UI on every entity detail page

## Phase 5 — Dashboard analytics / Reports

- Charts: orders by status, past-due trend, production workload, vendor
  performance, on-time shipment %, RMA aging, monthly trends, bottleneck ops
- Daily Coordinator Report, Weekly Production Report, Customer Order Report,
  Vendor Performance Report, On-Time Shipment Report, RMA Aging Report,
  Management Summary - exportable to Excel/CSV/PDF

## Phase 6 — Excel import/export, advanced validation

- Column-mapping import engine (select file -> map columns -> preview ->
  validate -> confirm -> commit -> log to `import_batches`)
- Export to Excel/CSV from every major table; PDF for reports
- Configurable import mapping profiles per source spreadsheet

## Phase 7 — Testing / performance / security hardening

- Load-test against 100k+ synthetic rows; add indexes/pagination where
  queries regress
- Expanded regression suite; `pytest-qt` UI smoke tests
- Security review of the local auth flow ahead of any future SSO work

## Phase 8 — EXE packaging / installer / deployment

- Finalize PyInstaller build, verify on a clean Windows VM (no Python
  installed)
- Inno Setup installer, versioned releases

## Phase 9 — Optional AI/ML (only after Phase 1-8 are stable)

- Predictive late-order risk, bottleneck detection, delivery-risk scoring -
  always shown as "Predicted Risk," never merged into or replacing "Actual
  Status" (spec rule 28)
- Disabled by default (`AiSettings.enabled = False`); the app is fully
  functional with AI off

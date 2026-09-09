# Architecture

## Layering

```
app/ui/            PySide6 widgets, pages, dialogs. Talks to app_context,
                    repositories and services. Never contains business rules.
app/business/       Pure functions: priority scoring, status derivation,
                    calendar-aware date math consumers. No DB, no Qt.
app/services/       Orchestration that touches more than one repository or
                    an external resource (backup, future email/Teams, imports).
app/repositories/   Query/persistence per aggregate (or per screen, for
                    read-heavy aggregate views like the dashboard).
app/models/         SQLAlchemy ORM models - the schema, one file per domain
                    area (core, orders, production, purchasing, shipping,
                    rma, followup, audit, imports).
app/database/       Engine/session management, SQLite pragmas.
app/security/       Local authentication (password hashing, login, roles).
app/config/         Constants (enums shared everywhere) and persisted
                    AppSettings (every configurable business threshold).
app/utils/          Logging setup, business-day calendar math.
app/imports/        (Phase 6) Excel/CSV import engine.
app/exports/        (Phase 6) Excel/CSV/PDF export.
app/analytics/       (Phase 5) Chart-ready aggregate queries.
app/alerts/          (Phase 4) Alert-rule engine built on app/business rules.
app/reports/          (Phase 5) Report generation (PDF/Excel).
app/ai/               (Phase 9, optional, disabled by default) predictive risk.
```

Dependency direction is strictly downward: `ui -> services/repositories ->
business/models -> config`. Nothing in `business`, `models`, or `config`
imports Qt or SQLAlchemy sessions directly into its public API surface in a
way that would make it untestable without a running application.

## Why this shape

- **Business rules are centralized and pure** (`app/business/priority.py`,
  `app/utils/calendar_utils.py`). The dashboard, a future alert engine, and a
  future report all call the *same* `compute_line_priority` - there is
  exactly one place that decides what "late" or "critical" means, satisfying
  the spec's repeated instruction not to scatter status/priority logic
  through UI code (spec rules 9, 10, 36).
- **Settings, not constants, hold every business threshold**
  (`app/config/settings.py`). Due-soon windows, priority weights, RMA aging
  buckets, the work calendar - all live in a dataclass tree that round-trips
  to `settings.json`, so a coordinator can retune the system from the
  Settings page without a code change or a rebuild (spec rules 52-53).
- **A single ORM base with audit mixins** (`app/database/base.py`) means
  every domain table gets `created_at/updated_at/created_by/updated_by` for
  free - auditability (rule 57) is structural, not something each model
  author has to remember to add.
- **The activity log and notes are polymorphic by convention**
  (`entity_type` + `entity_id` in `app/models/audit.py`), not by ORM
  inheritance, so a Part, a Vendor, and an RMA can all carry notes/history
  without those domain models depending on each other.
- **Repositories are per-question, not just per-table.**
  `app/repositories/dashboard.py` runs aggregate SQL directly rather than
  loading every open order line into Python and counting in a loop - this is
  what makes the KPI cards viable against the 100k+ row target in spec rule
  30 (performance).
- **The UI layer is thin.** Pages hold widgets and call into
  repositories/services; `app/ui/app_context.py` hands every page the same
  `(settings, session_factory, current_user)` tuple rather than reaching for
  globals, so pages stay unit-testable in isolation from the main window.

## Database strategy

SQLite via SQLAlchemy 2.0 (`app/database/session.py`), with
`PRAGMA foreign_keys=ON` and WAL journaling set on every connection - SQLite
does not enforce foreign keys by default, so this pragma is not optional.
Schema creation for a fresh install is `Base.metadata.create_all`
(`init_database`); schema *changes* to an existing database are handled by
Alembic migrations under `alembic/` (added in Phase 2 once the schema is no
longer changing every commit) - `create_all` never runs against a database
with existing tables it doesn't already know about, so it cannot silently
skip a needed migration.

Moving to PostgreSQL/SQL Server later means: swap the SQLAlchemy URL, keep
every model as-is (they use portable types), and let Alembic's existing
migration chain replay against the new engine. No application code above
`app/database/session.py` references SQLite-specific behavior.

## Security model

Local username/password auth (`app/security/auth.py`), PBKDF2-HMAC-SHA256
hashing (versioned in the stored hash string), account lockout after
repeated failures, and a `role` column (`ADMIN` / `COORDINATOR` / `VIEWER`)
enforced through `AuthenticatedUser.can_edit` / `.is_admin`. Nothing in the
UI layer checks `role` strings directly - it goes through those two
properties, so an eventual Active Directory / Entra ID backend only has to
populate the same `role` field on login and every existing permission check
keeps working unchanged.

## Excel integration (Phase 6)

Not yet implemented. The intended shape: `app/imports/` will contain a
column-mapping engine (openpyxl to read, pandas for validation) that always
runs preview -> validate -> user-confirm -> commit, logging every run to the
`import_batches` / `import_row_errors` tables already defined in
`app/models/imports.py`. Source files are opened read-only; the app writes
new files for exports, never back into the source spreadsheet (spec rule
55).

## Packaging

PyInstaller one-folder build (`packaging/camco_coordinator.spec`,
`scripts/build_exe.py`) wrapped by an Inno Setup installer
(`packaging/inno_setup.iss`). Application data is never written beside the
`.exe` - see `app/config/paths.py`, which resolves everything writable under
`%LOCALAPPDATA%\CAMCO Coordinator\` (or `CAMCO_HOME` if set).

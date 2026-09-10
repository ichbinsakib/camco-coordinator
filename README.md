# CAMCO Coordinator

A Windows desktop application for manufacturing coordination and expediting
at CAMCO Manufacturing: one place to see what's late, what's due, what's
waiting on someone else, and what needs a phone call today.

Built with Python 3.12+, PySide6 (Qt), and SQLAlchemy over SQLite.

## Status

**All 9 phases complete.** The full coordination workflow is built, tested
and packaged: application shell, database schema, settings, local auth
(with idle-timeout lock), the dashboard/priority/alert engines, full CRUD
across Customer Orders, Parts, Production, Purchasing, Shipping, RMAs,
Follow-Ups, Customers and Vendors, Excel/CSV import, analytics charts, a
six-report export engine (Excel/PDF/CSV), a built-and-smoke-tested
Windows executable, and optional AI Insights (delivery-risk prediction,
recurring-bottleneck detection, natural-language search - off by default).
145 automated tests pass (`pytest`), plus a 100k-row performance suite
(`pytest -m slow tests/performance`).

Two Phase 8 items remain, both needing tools this dev environment doesn't
have: verifying the `.exe` on a clean Windows machine with no Python
installed, and compiling the Inno Setup installer. See
[docs/PACKAGING.md](docs/PACKAGING.md).

See [docs/ROADMAP.md](docs/ROADMAP.md) for what shipped in each phase, and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it's put together.

## Quick start (development)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m app.main
```

On first launch the app creates its database and a default `admin` account;
the temporary password is written to the log file
(`%LOCALAPPDATA%\CAMCO Coordinator\logs\camco_coordinator.log`) - change it
immediately after logging in.

## Running the tests

```bash
python -m pytest
```

## Building the Windows executable

```bash
pip install -r requirements-dev.txt
python scripts\build_exe.py
```

This produces `dist\CAMCO_Coordinator\CAMCO_Coordinator.exe`. To build a
distributable installer, install [Inno Setup](https://jrsoftware.org/isinfo.php)
and compile `packaging\inno_setup.iss` against that output.

## Where application data lives

The app never writes next to its own `.exe`. Everything writable - the
SQLite database, logs, backups, generated reports, and `settings.json` -
lives under `%LOCALAPPDATA%\CAMCO Coordinator\` by default. Every one of
those locations is configurable from the Settings page. Set the environment
variable `CAMCO_HOME` to redirect the entire application-data root (used
automatically by the test suite).

## Project layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown of
`app/`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Database schema](docs/DATABASE.md)
- [Roadmap / phased implementation plan](docs/ROADMAP.md)
- [Assumptions made where the spec was ambiguous](docs/ASSUMPTIONS.md)
- [Performance notes (100k-row benchmarks)](docs/PERFORMANCE.md)
- [Security review](docs/SECURITY.md)
- [Packaging (EXE build, installer)](docs/PACKAGING.md)
- [AI / Machine Learning (optional, off by default)](docs/AI.md)

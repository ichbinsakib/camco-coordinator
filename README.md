# CAMCO Coordinator

A Windows desktop application for manufacturing coordination and expediting
at CAMCO Manufacturing: one place to see what's late, what's due, what's
waiting on someone else, and what needs a phone call today.

Built with Python 3.12+, PySide6 (Qt), and SQLAlchemy over SQLite.

## Status

**Phase 1 complete.** The application shell, database schema, settings
system, logging, local authentication, backup/restore, and the dashboard KPI
engine are implemented and tested. See [docs/ROADMAP.md](docs/ROADMAP.md) for
what ships in each subsequent phase, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for how it's put together.

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

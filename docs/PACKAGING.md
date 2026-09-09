# Packaging (Phase 8)

## Building the executable

```bash
pip install -r requirements-dev.txt
python scripts\build_exe.py
```

Produces a one-folder build at `dist\CAMCO_Coordinator\CAMCO_Coordinator.exe`
(one-folder rather than `--onefile`: faster startup, and a stray DLL issue
in the field is far easier to diagnose than inside a single-file archive).
~197 MB, dominated by the Qt/PySide6 runtime.

**Verified**: built and smoke-tested on this machine (`app/main.py` launched
headlessly with a fresh `CAMCO_HOME`, confirmed via the log file and the
resulting SQLite file that the app started, created its 21-table schema,
stamped it at the current Alembic revision, and bootstrapped the default
admin account - all with zero errors). Not yet verified on a clean Windows
machine with no Python installed; that's the one remaining step before
calling Phase 8 fully closed (see below).

## A real bug this caught

The first build attempt produced a working exe that nonetheless logged an
error on every launch:

```
ModuleNotFoundError: No module named 'logging.config'
```

...coming from the bundled `alembic/env.py`, which imports
`logging.config.fileConfig`. PyInstaller's static import scanner didn't
pick up `logging.config` or `logging.handlers` as separate modules to
bundle (they're stdlib submodules pulled in dynamically enough that the
scanner missed them, even though `app/utils/logging_setup.py` uses
`RotatingFileHandler` from `logging.handlers` directly). The app didn't
crash - `app/database/migrations.py` catches and logs the failure - but it
silently meant every fresh install's database never got stamped with an
Alembic revision, which would have broken the upgrade path for whoever hit
it first.

Fixed by adding both to `hiddenimports` in
`packaging/camco_coordinator.spec`. Rebuilt and re-verified: the log is now
clean and `alembic_version` is correctly populated. This is exactly the
kind of bug that only a real frozen-build smoke test finds - the dev-mode
test suite has no reason to exercise PyInstaller's import graph at all.

## Building the installer

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) (not installed in
this environment - not verified end-to-end):

```bash
ISCC.exe packaging\inno_setup.iss
```

Wraps the `dist\CAMCO_Coordinator\` folder into
`dist\installer\CAMCO_Coordinator_Setup_<version>.exe`. The script requires
admin privileges only to write to Program Files; the application itself
never needs elevation, since all writable data lives under
`%LOCALAPPDATA%\CAMCO Coordinator\` (see `app/config/paths.py`).

## Remaining before Phase 8 is fully closed

1. **Clean-machine verification.** This environment already has Python
   installed, so "the app doesn't need Python installed" is architecturally
   true (PyInstaller bundles the interpreter and every dependency) but
   hasn't been proven on a machine that lacks Python. Recommended: run the
   built `dist\CAMCO_Coordinator\CAMCO_Coordinator.exe` on a clean Windows
   10/11 VM before shipping it to a coordinator's machine.
2. **Inno Setup not installed here** - the `.iss` script is written and
   follows Inno Setup's documented syntax, but has not been compiled or
   run. Install Inno Setup and run `ISCC.exe` against
   `packaging\inno_setup.iss` to produce and test the actual installer.
3. **Code signing** is not set up. An unsigned `.exe`/installer will
   trigger a Windows SmartScreen warning on first run; acceptable for
   internal tooling, but worth an Authenticode certificate if this is ever
   distributed more broadly.

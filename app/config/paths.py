"""Filesystem locations used by the application.

Writable application data never lives beside the executable (Program Files is
read-only for standard users).  Everything writable goes under a per-user
application-data root, which can be redirected with the ``CAMCO_HOME``
environment variable (used by tests and by portable installations).
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from app import APP_NAME

ENV_HOME = "CAMCO_HOME"


@lru_cache(maxsize=1)
def app_home() -> Path:
    """Return the writable application-data root, creating it if needed."""
    override = os.environ.get(ENV_HOME)
    if override:
        root = Path(override).expanduser()
    elif sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        root = Path(base) / APP_NAME
    else:  # pragma: no cover - development convenience on non-Windows hosts
        root = Path.home() / ".camco_coordinator"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sub(name: str) -> Path:
    path = app_home() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Directory holding the SQLite database."""
    return _sub("data")


def logs_dir() -> Path:
    """Directory holding rotating log files."""
    return _sub("logs")


def backups_dir() -> Path:
    """Default directory for database backups."""
    return _sub("backups")


def reports_dir() -> Path:
    """Default output directory for generated reports."""
    return _sub("reports")


def settings_file() -> Path:
    """Path of the JSON settings document."""
    return app_home() / "settings.json"


def default_database_file() -> Path:
    """Default SQLite database file location."""
    return data_dir() / "camco_coordinator.db"


def resource_dir() -> Path:
    """Directory containing bundled read-only resources (icons, QSS, seeds).

    Works both from source and from a PyInstaller one-file bundle.
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:  # pragma: no cover - only true inside a frozen build
        return Path(bundle) / "resources"
    return Path(__file__).resolve().parent.parent / "ui" / "resources"


def reset_path_cache() -> None:
    """Clear the cached home directory (used by tests that move ``CAMCO_HOME``)."""
    app_home.cache_clear()

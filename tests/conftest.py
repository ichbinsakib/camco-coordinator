"""Shared pytest fixtures.

Every test gets a throwaway in-memory-equivalent SQLite database via
``CAMCO_HOME`` pointed at a temp directory, so tests never touch the real
application data and never depend on each other.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

# pytest-qt widget tests need a display; there usually isn't one in CI or a
# background shell, so default to Qt's offscreen platform plugin. Set before
# any Qt import happens (pytest-qt's own plugin imports Qt at collection
# time), and only if the caller hasn't already chosen a platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers mapped classes
from app.config import paths as paths_module
from app.config.settings import AppSettings, SettingsManager, set_settings_manager
from app.database.session import get_session_factory, init_database, reset_engine


@pytest.fixture
def app_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the application-data root to a temp directory for this test."""
    monkeypatch.setenv(paths_module.ENV_HOME, str(tmp_path))
    paths_module.reset_path_cache()
    yield tmp_path
    paths_module.reset_path_cache()


@pytest.fixture
def settings_manager(app_home: Path) -> Iterator[SettingsManager]:
    """A fresh :class:`SettingsManager` backed by the temp app home."""
    manager = SettingsManager(app_home / "settings.json")
    set_settings_manager(manager)
    yield manager
    set_settings_manager(None)


@pytest.fixture
def db_session(app_home: Path, settings_manager: SettingsManager) -> Iterator[Session]:
    """A real SQLite-backed session against a fresh, empty schema."""
    db_url = f"sqlite:///{(app_home / 'test.db').as_posix()}"
    init_database(db_url)
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        reset_engine()


@pytest.fixture
def settings() -> AppSettings:
    """A default settings document, independent of any file."""
    return AppSettings()

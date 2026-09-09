"""Integration tests for database backup/restore."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import AppSettings
from app.services.backup_service import BackupService


def _settings_for(tmp_path: Path) -> AppSettings:
    settings = AppSettings()
    settings.paths.database_file = str(tmp_path / "camco.db")
    settings.paths.backup_dir = str(tmp_path / "backups")
    settings.backup.minimum_retained = 2
    return settings


def test_backup_creates_new_file_never_overwrites(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "camco.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    settings = _settings_for(tmp_path)
    service = BackupService(settings)

    first = service.create_backup()
    second = service.create_backup()

    assert first.path.exists()
    assert second.path.exists()
    assert first.path != second.path  # never the same file / never overwritten


def test_backup_missing_database_raises(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path)
    service = BackupService(settings)
    with pytest.raises(FileNotFoundError):
        service.create_backup()


def test_restore_backs_up_current_db_first(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "camco.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    settings = _settings_for(tmp_path)
    service = BackupService(settings)
    backup = service.create_backup()

    # Simulate a bad restore target.
    service.restore_backup(backup.path)

    backups_after = service.list_backups()
    # The pre-restore safety backup plus the original backup should both exist.
    assert len(backups_after) >= 2

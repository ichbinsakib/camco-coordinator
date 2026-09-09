"""SQLite database backup and restore.

Backups are timestamped copies, never in-place overwrites (rule 26: never
silently overwrite the only backup). Uses the SQLite online backup API via
``sqlite3.Connection.backup`` so a backup taken while the app is open is still
transactionally consistent, rather than a raw file copy that could catch a
half-written WAL frame.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import AppSettings

log = logging.getLogger(__name__)

_TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S_%f"


@dataclass(slots=True)
class BackupResult:
    """Outcome of a single backup operation."""

    path: Path
    size_bytes: int
    created_at: datetime


class BackupService:
    """Creates, lists, prunes and restores database backups."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def create_backup(self) -> BackupResult:
        """Create a new timestamped backup of the current database."""
        db_path = self._settings.paths.resolved_database_file()
        backup_dir = self._settings.paths.resolved_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        timestamp = datetime.now(UTC)
        dest = backup_dir / f"CAMCO_Coordinator_{timestamp.strftime(_TIMESTAMP_FORMAT)}.db"

        source_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(dest))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            source_conn.close()

        log.info("Database backup created: %s", dest)
        self._prune_old_backups(backup_dir)
        return BackupResult(path=dest, size_bytes=dest.stat().st_size, created_at=timestamp)

    def list_backups(self) -> list[Path]:
        """List backup files, newest first."""
        backup_dir = self._settings.paths.resolved_backup_dir()
        if not backup_dir.exists():
            return []
        files = sorted(backup_dir.glob("CAMCO_Coordinator_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def restore_backup(self, backup_path: Path) -> None:
        """Restore a backup over the live database.

        The *current* database is itself backed up first, so a bad restore
        choice is always recoverable - this operation is never destructive
        without a safety net.
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        db_path = self._settings.paths.resolved_database_file()
        if db_path.exists():
            self.create_backup()
        shutil.copy2(backup_path, db_path)
        log.warning("Database restored from backup: %s", backup_path)

    def _prune_old_backups(self, backup_dir: Path) -> None:
        """Delete backups past the retention window, always keeping a minimum count."""
        retention = self._settings.backup
        files = sorted(
            backup_dir.glob("CAMCO_Coordinator_*.db"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if len(files) <= retention.minimum_retained:
            return
        cutoff = datetime.now(UTC).timestamp() - retention.retention_days * 86400
        for path in files[retention.minimum_retained :]:
            if path.stat().st_mtime < cutoff:
                try:
                    path.unlink()
                    log.info("Pruned old backup: %s", path)
                except OSError:
                    log.exception("Could not prune backup %s", path)

"""Alembic integration: stamp a fresh database, upgrade an existing one.

Table *creation* for a brand-new database still goes through
``Base.metadata.create_all`` (see :func:`app.database.session.init_database`)
because that path has no dependency on the Alembic config being bundled or
discoverable - it must always work, including in a frozen build that, for
whatever reason, didn't ship ``alembic.ini``. This module's job is narrower:
make sure that once a database exists, its ``alembic_version`` row reflects
reality, so a later schema change can be applied with a real migration
instead of the spec's explicitly forbidden "just delete the database" (rule
62).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Engine, inspect

from alembic import command

log = logging.getLogger(__name__)


def _project_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:  # pragma: no cover - only true inside a frozen build
        return Path(bundle)
    return Path(__file__).resolve().parent.parent.parent


def _alembic_config(engine: Engine) -> Config | None:
    """Build an Alembic ``Config`` pointed at this project's migrations.

    The target database URL is taken from ``engine`` (not re-derived from
    settings) so this always operates on the exact database the caller is
    using - including a test's or a script's explicitly-chosen database file,
    not just the application's default configured one.

    Returns ``None`` (rather than raising) if the migration files aren't
    present - callers treat that as "skip, nothing to do" so a build that
    forgot to bundle them degrades gracefully instead of crashing on launch.
    """
    root = _project_root()
    ini_path = root / "alembic.ini"
    script_location = root / "alembic"
    if not ini_path.exists() or not script_location.exists():
        log.warning("Alembic config not found at %s - skipping migration step", ini_path)
        return None
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", str(engine.url))
    return config


def _has_user_tables(engine: Engine) -> bool:
    """True if the database has any table besides Alembic's own bookkeeping table."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    return bool(tables - {"alembic_version"})


def _has_alembic_version(engine: Engine) -> bool:
    return "alembic_version" in inspect(engine).get_table_names()


def sync_migration_state(engine: Engine) -> None:
    """Bring ``alembic_version`` in line with the database's actual state.

    - Empty database (no tables yet, `create_all` about to run / just ran
      with nothing pre-existing): nothing to stamp yet - the caller stamps
      after creating tables via :func:`stamp_head`.
    - Existing tables, no ``alembic_version`` row: this is a database created
      by an earlier build's ``create_all`` before Alembic was wired in.
      Stamp it at head without running migrations, since its schema already
      matches what the initial migration produces.
    - Existing ``alembic_version`` row: run any pending migrations.
    """
    config = _alembic_config(engine)
    if config is None:
        return
    try:
        if _has_user_tables(engine) and not _has_alembic_version(engine):
            log.info("Existing database has no Alembic version - stamping at head")
            command.stamp(config, "head")
        elif _has_alembic_version(engine):
            command.upgrade(config, "head")
    except Exception:
        log.exception("Alembic migration step failed; continuing with existing schema")


def stamp_head(engine: Engine) -> None:
    """Mark a freshly created database as being at the latest migration."""
    config = _alembic_config(engine)
    if config is None:
        return
    try:
        command.stamp(config, "head")
    except Exception:
        log.exception("Could not stamp new database with Alembic head revision")

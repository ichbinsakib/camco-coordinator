"""Engine and session factory.

A single module-level engine is created lazily from the current settings, so
tests can point ``CAMCO_HOME`` (or pass an explicit URL) at a throwaway
database without touching global state at import time.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

log = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _sqlite_url(db_path: Path) -> str:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


def build_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a new engine, applying the pragmas SQLite needs for integrity.

    ``foreign_keys=ON`` is not the SQLite default and must be set per
    connection - without it every ``ForeignKey`` in the models is decorative.
    """
    if database_url is None:
        database_url = _sqlite_url(get_settings().paths.resolved_database_file())

    engine = create_engine(database_url, echo=echo, future=True)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = build_engine()
        log.info("Database engine created: %s", _engine.url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session: commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose of and clear the cached engine/session factory (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_database(database_url: str | None = None, *, echo: bool = False) -> Engine:
    """Create all tables on a fresh engine and install it as the process engine.

    Safe to call against an existing database: ``create_all`` only creates
    tables that do not already exist. A brand-new database is then stamped at
    the latest Alembic revision; an existing one not yet tracked by Alembic is
    stamped in place (its schema already matches, since it came from this
    same ``create_all``); an existing tracked database is upgraded to head.
    From that point on, schema *changes* are applied as real Alembic
    migrations, not by re-running ``create_all``.
    """
    global _engine, _session_factory
    import app.models  # noqa: F401  (registers all mapped classes)
    from app.database.base import Base
    from app.database.migrations import stamp_head, sync_migration_state

    reset_engine()
    _engine = build_engine(database_url, echo=echo)

    is_fresh = not inspect(_engine).get_table_names()
    Base.metadata.create_all(_engine)
    if is_fresh:
        stamp_head(_engine)
    else:
        sync_migration_state(_engine)

    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine

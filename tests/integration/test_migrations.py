"""Integration tests for Alembic wiring around database creation."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text

from app.database.session import get_engine, init_database, reset_engine


def test_fresh_database_is_stamped_at_head(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    init_database(db_url)
    try:
        engine = get_engine()
        assert "alembic_version" in inspect(engine).get_table_names()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version is not None
    finally:
        reset_engine()


def test_reinitializing_an_existing_database_does_not_error(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'existing.db').as_posix()}"
    init_database(db_url)
    reset_engine()
    # Re-running init_database against the same file simulates a normal
    # second app launch - it must not try to re-create tables or crash.
    init_database(db_url)
    engine = get_engine()
    assert "users" in inspect(engine).get_table_names()
    reset_engine()


def test_running_alembic_does_not_disable_the_app_loggers(tmp_path: Path) -> None:
    """Regression test: alembic/env.py's fileConfig() call must not silence app logging.

    fileConfig() defaults to disable_existing_loggers=True, which sets
    ``.disabled = True`` on every logger that already exists at the time it
    runs - including every ``app.*`` logger the application set up before
    calling init_database(). That silently ate the first-run admin
    password's log line with no error anywhere, console or file.
    """
    app_logger = logging.getLogger("app.security.auth")
    app_logger.disabled = False  # start from a known-good state
    assert app_logger.disabled is False

    db_url = f"sqlite:///{(tmp_path / 'logging_check.db').as_posix()}"
    init_database(db_url)
    try:
        assert app_logger.disabled is False, (
            "Alembic's fileConfig() disabled an application logger - "
            "the first-run admin password (and everything else) would log nowhere."
        )
    finally:
        reset_engine()


def test_running_alembic_does_not_replace_the_root_handlers(tmp_path: Path) -> None:
    """Regression test: fileConfig() must not silently drop the app's log handlers either.

    disable_existing_loggers=False (see the test above) only stops loggers
    from being *disabled* - fileConfig() unconditionally replaces the root
    logger's *handler list* with whatever alembic.ini defines, regardless of
    that flag. That's the actual reason the first-run admin password never
    reached the persisted log file even after the disabled-loggers fix: the
    WARNING call still executed, but the RotatingFileHandler the app
    attached to the root logger was gone. This asserts a record actually
    reaches a handler the app installed before init_database() ran.
    """
    root_logger = logging.getLogger()
    records: list[logging.LogRecord] = []

    class _CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    probe_handler = _CapturingHandler()
    root_logger.addHandler(probe_handler)
    try:
        db_url = f"sqlite:///{(tmp_path / 'logging_handlers_check.db').as_posix()}"
        init_database(db_url)
        try:
            logging.getLogger("app.security.auth").warning("probe message after alembic ran")
            assert any(r.getMessage() == "probe message after alembic ran" for r in records), (
                "A log record emitted after init_database() never reached a handler "
                "the application installed beforehand - Alembic's fileConfig() replaced "
                "the root logger's handlers."
            )
        finally:
            reset_engine()
    finally:
        root_logger.handlers = [h for h in root_logger.handlers if h is not probe_handler]

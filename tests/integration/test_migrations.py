"""Integration tests for Alembic wiring around database creation."""

from __future__ import annotations

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

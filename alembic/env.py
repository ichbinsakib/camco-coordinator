"""Alembic environment: wires migrations to app.models and the live app database.

The database URL is not read from ``alembic.ini`` - it is resolved the same
way the running application resolves it (``AppSettings.paths``), so
migrations always target whatever database the app is actually configured
to use, including a ``CAMCO_HOME``-redirected one in tests/CI.
"""

import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Registers every mapped class on Base.metadata before Alembic inspects it.
import app.models  # noqa: F401
from alembic import context
from app.config.settings import get_settings
from app.database.base import Base

config = context.config

if config.config_file_name is not None:
    # fileConfig() reconfigures the *root* logger from alembic.ini
    # unconditionally - it replaces its handlers (dropping whatever the
    # embedding application already attached, e.g. our RotatingFileHandler)
    # and, with the default disable_existing_loggers=True, also disables
    # every already-registered logger not listed in alembic.ini's [loggers]
    # section. Both silently broke the app's own logging (the first-run
    # admin password's WARNING call executed and produced no error, but
    # landed nowhere - not the log file, not even the console once the
    # handler was gone). We already own logging setup end-to-end
    # (app/utils/logging_setup.py); this call only needs to exist for
    # alembic.ini's own formatting when Alembic is run standalone from a
    # terminal. So: snapshot the root logger's state, let fileConfig() do
    # its thing, then restore it - alembic.ini's config still applies for
    # standalone use (nothing to restore then), but it can never clobber an
    # application that configured logging before importing this module.
    _root_logger = logging.getLogger()
    _had_handlers = list(_root_logger.handlers)
    _had_level = _root_logger.level
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    if _had_handlers:
        _root_logger.handlers = _had_handlers
        _root_logger.setLevel(_had_level)

target_metadata = Base.metadata


_INI_PLACEHOLDER_URL = "driver://user:pass@localhost/dbname"


def _database_url() -> str:
    """Resolve the target database URL.

    Prefers a URL the caller already set on the Config object (e.g.
    :mod:`app.database.migrations`, which points this at the exact engine in
    use - a test's temp database, not necessarily the app's default one).
    Falls back to the application's configured default, which is what makes
    a plain `alembic upgrade head` from the command line work out of the box.
    """
    configured = config.get_main_option("sqlalchemy.url")
    if configured and configured != _INI_PLACEHOLDER_URL:
        return configured
    db_path = get_settings().paths.resolved_database_file()
    return f"sqlite:///{db_path.as_posix()}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite can't ALTER COLUMN directly; batch mode rebuilds the table.
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the application's live database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

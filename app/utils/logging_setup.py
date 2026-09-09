"""Application-wide logging configuration.

Called once at startup. Installs a rotating file handler under the
application-data logs directory plus a console handler, and hooks
``sys.excepthook`` so an unhandled exception is logged with a full traceback
instead of silently killing the Qt event loop (rule 25: never crash silently).
"""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

from app.config import paths
from app.config.settings import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> logging.Logger:
    """Configure root logging handlers and return the application logger."""
    settings = get_settings().logging
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.level.upper(), logging.INFO))

    # Avoid duplicate handlers if called more than once (tests, re-init).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        paths.logs_dir() / "camco_coordinator.log",
        maxBytes=settings.max_bytes,
        backupCount=settings.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if not settings.log_sql:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    install_global_exception_hook()
    return logging.getLogger("app")


def install_global_exception_hook() -> None:
    """Route uncaught exceptions to the log instead of a bare console traceback."""
    log = logging.getLogger("app.unhandled")

    def _hook(exc_type: type[BaseException], exc_value: BaseException, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical(
            "Unhandled exception: %s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )

    sys.excepthook = _hook

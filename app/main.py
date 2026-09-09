"""CAMCO Coordinator entry point.

Startup sequence: configure logging -> initialise database -> seed a default
admin (first run only) -> show login -> show main window. Any failure in this
sequence is logged and shown to the user via a message box rather than a bare
console traceback (rule 25).
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME, ORG_NAME
from app.config.settings import get_settings_manager
from app.database.session import get_session_factory, init_database
from app.security.auth import AuthService
from app.ui.app_context import AppContext
from app.ui.login_dialog import prompt_login
from app.ui.main_window import MainWindow
from app.ui.theme import stylesheet
from app.utils.logging_setup import configure_logging

log = logging.getLogger(__name__)


def main() -> int:
    """Launch the application. Returns the process exit code."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    settings_manager = get_settings_manager()
    settings = settings_manager.load()

    log_instance = configure_logging()
    log_instance.info("%s starting up", APP_NAME)

    try:
        init_database()
    except Exception as exc:
        log.exception("Database initialisation failed")
        QMessageBox.critical(None, APP_NAME, f"Could not open the database:\n{exc}")
        return 1

    session_factory = get_session_factory()
    app.setStyleSheet(stylesheet(settings.ui.theme, settings.ui.accent_color))

    with session_factory() as session:
        AuthService(session).ensure_default_admin()
        authenticated_user = prompt_login(session)

    if authenticated_user is None:
        log.info("Login cancelled; exiting")
        return 0

    context = AppContext(
        settings=settings, session_factory=session_factory, current_user=authenticated_user
    )
    window = MainWindow(context, settings_manager)
    window.show()

    log.info("%s ready", APP_NAME)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

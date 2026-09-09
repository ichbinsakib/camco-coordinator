"""Simple username/password login dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy.orm import Session

from app.security.auth import AuthenticatedUser, AuthError, AuthService


class LoginDialog(QDialog):
    """Blocking login prompt; ``authenticated_user`` is set on acceptance."""

    def __init__(self, session: Session, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self.authenticated_user: AuthenticatedUser | None = None

        self.setWindowTitle("CAMCO Coordinator - Sign In")
        self.setModal(True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        heading = QLabel("CAMCO Coordinator")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        form = QFormLayout()
        self._username = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._attempt_login)
        form.addRow("Username", self._username)
        form.addRow("Password", self._password)
        layout.addLayout(form)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #B91C1C;")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        login_btn = QPushButton("Sign In")
        login_btn.setObjectName("PrimaryButton")
        login_btn.clicked.connect(self._attempt_login)
        layout.addWidget(login_btn)

        self._username.setFocus()

    def _attempt_login(self) -> None:
        username = self._username.text().strip()
        password = self._password.text()
        if not username or not password:
            self._error_label.setText("Enter a username and password.")
            return
        try:
            self.authenticated_user = AuthService(self._session).login(username, password)
        except AuthError as exc:
            self._error_label.setText(str(exc))
            self._password.clear()
            return
        self.accept()


def prompt_login(session: Session, parent=None) -> AuthenticatedUser | None:
    """Show the login dialog; return the authenticated user, or ``None`` if cancelled."""
    dialog = LoginDialog(session, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.authenticated_user
    return None

"""Modal lock screen shown after idle timeout - unlocks by re-entering the current password.

Deliberately cannot be dismissed except by successful re-authentication as
the *same* user (Esc/close are disabled) - it is a session lock, not a
confirmation dialog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
from sqlalchemy.orm import Session

from app.security.auth import AuthError, AuthService


class LockScreenDialog(QDialog):
    """Blocks all interaction until the current user re-enters their password."""

    def __init__(self, session: Session, username: str, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._username = username
        self.setWindowTitle("Session Locked")
        self.setModal(True)
        self.setFixedWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        heading = QLabel(f"Session locked - {username}")
        heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        note = QLabel("Enter your password to continue.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        form = QFormLayout()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._attempt_unlock)
        form.addRow("Password", self._password)
        layout.addLayout(form)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #B91C1C;")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        unlock_btn = QPushButton("Unlock")
        unlock_btn.setObjectName("PrimaryButton")
        unlock_btn.clicked.connect(self._attempt_unlock)
        layout.addWidget(unlock_btn)

        self._password.setFocus()

    def _attempt_unlock(self) -> None:
        password = self._password.text()
        if not password:
            return
        try:
            AuthService(self._session).login(self._username, password)
        except AuthError as exc:
            self._error_label.setText(str(exc))
            self._password.clear()
            return
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            return  # a lock screen is not dismissible with Escape
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()  # only a successful unlock may close this dialog

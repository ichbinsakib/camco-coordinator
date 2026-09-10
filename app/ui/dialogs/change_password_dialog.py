"""Self-service password change for the currently logged-in user.

Claude/automation must never enter a password into this (or any) field on a
user's behalf - this dialog exists precisely so a coordinator can do it
themselves through the app's own UI, rather than a one-off script or a
developer touching the database directly.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton
from sqlalchemy.orm import Session

from app.models.core import User
from app.security.auth import AuthService, verify_password


class ChangePasswordDialog(QDialog):
    """Prompts for the current password, then a new one (entered twice), and saves it."""

    def __init__(self, session: Session, user_id: int, username: str, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._user_id = user_id
        self.setWindowTitle("Change Password")
        self.setFixedWidth(360)

        form = QFormLayout(self)
        form.addRow(QLabel(f"Signed in as {username}"))

        self._current_password = QLineEdit()
        self._current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password = QLineEdit()
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password.returnPressed.connect(self._attempt_change)

        form.addRow("Current Password", self._current_password)
        form.addRow("New Password", self._new_password)
        form.addRow("Confirm New Password", self._confirm_password)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #B91C1C;")
        self._error_label.setWordWrap(True)
        form.addRow(self._error_label)

        save_btn = QPushButton("Change Password")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._attempt_change)
        form.addRow(save_btn)

        self._current_password.setFocus()

    def _attempt_change(self) -> None:
        current = self._current_password.text()
        new = self._new_password.text()
        confirm = self._confirm_password.text()

        if not current or not new or not confirm:
            self._error_label.setText("Fill in all three fields.")
            return
        if new != confirm:
            self._error_label.setText("New password and confirmation don't match.")
            return

        user = self._session.get(User, self._user_id)
        if user is None or not verify_password(current, user.password_hash):
            self._error_label.setText("Current password is incorrect.")
            self._current_password.clear()
            return

        try:
            AuthService(self._session).change_password(self._user_id, new)
        except ValueError as exc:
            self._error_label.setText(str(exc))
            return

        QMessageBox.information(self, "Password Changed", "Your password has been updated.")
        self.accept()

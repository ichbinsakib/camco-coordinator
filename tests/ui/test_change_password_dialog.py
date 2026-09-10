"""pytest-qt tests for the self-service Change Password dialog."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.config.constants import UserRole
from app.security.auth import AuthService, verify_password
from app.ui.dialogs.change_password_dialog import ChangePasswordDialog


@pytest.fixture
def existing_user(db_session: Session):
    return AuthService(db_session).create_user("tester", "Tester", "correct-password-1", UserRole.COORDINATOR)


def test_wrong_current_password_is_rejected(qtbot, db_session: Session, existing_user) -> None:
    dialog = ChangePasswordDialog(db_session, existing_user.id, "tester")
    qtbot.addWidget(dialog)

    dialog._current_password.setText("totally-wrong")
    dialog._new_password.setText("brand-new-password-1")
    dialog._confirm_password.setText("brand-new-password-1")
    dialog._attempt_change()

    assert dialog.result() != ChangePasswordDialog.DialogCode.Accepted
    assert "incorrect" in dialog._error_label.text().lower()
    db_session.refresh(existing_user)
    assert verify_password("correct-password-1", existing_user.password_hash)


def test_mismatched_confirmation_is_rejected(qtbot, db_session: Session, existing_user) -> None:
    dialog = ChangePasswordDialog(db_session, existing_user.id, "tester")
    qtbot.addWidget(dialog)

    dialog._current_password.setText("correct-password-1")
    dialog._new_password.setText("brand-new-password-1")
    dialog._confirm_password.setText("does-not-match")
    dialog._attempt_change()

    assert dialog.result() != ChangePasswordDialog.DialogCode.Accepted
    assert "match" in dialog._error_label.text().lower()


def test_too_short_new_password_is_rejected(qtbot, db_session: Session, existing_user) -> None:
    dialog = ChangePasswordDialog(db_session, existing_user.id, "tester")
    qtbot.addWidget(dialog)

    dialog._current_password.setText("correct-password-1")
    dialog._new_password.setText("short")
    dialog._confirm_password.setText("short")
    dialog._attempt_change()

    assert dialog.result() != ChangePasswordDialog.DialogCode.Accepted
    db_session.refresh(existing_user)
    assert verify_password("correct-password-1", existing_user.password_hash)


def test_correct_current_password_updates_the_hash(
    qtbot, db_session: Session, existing_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dialog = ChangePasswordDialog(db_session, existing_user.id, "tester")
    qtbot.addWidget(dialog)

    dialog._current_password.setText("correct-password-1")
    dialog._new_password.setText("brand-new-password-1")
    dialog._confirm_password.setText("brand-new-password-1")
    dialog._attempt_change()

    assert dialog.result() == ChangePasswordDialog.DialogCode.Accepted
    db_session.refresh(existing_user)
    assert verify_password("brand-new-password-1", existing_user.password_hash)
    assert not verify_password("correct-password-1", existing_user.password_hash)

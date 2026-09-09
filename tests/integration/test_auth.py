"""Integration tests for local authentication against a real database."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.config.constants import UserRole
from app.config.settings import get_settings
from app.security.auth import AuthError, AuthService


def test_ensure_default_admin_creates_one_user(db_session: Session) -> None:
    service = AuthService(db_session)
    service.ensure_default_admin()
    from app.models.core import User

    assert db_session.query(User).count() == 1
    admin = db_session.query(User).one()
    assert admin.role == UserRole.ADMIN.value


def test_login_with_wrong_password_fails(db_session: Session) -> None:
    service = AuthService(db_session)
    service.create_user("jdoe", "Jane Doe", "correct-password-1", UserRole.COORDINATOR)
    with pytest.raises(AuthError):
        service.login("jdoe", "wrong-password")


def test_login_with_correct_password_succeeds(db_session: Session) -> None:
    service = AuthService(db_session)
    service.create_user("jdoe", "Jane Doe", "correct-password-1", UserRole.COORDINATOR)
    user = service.login("jdoe", "correct-password-1")
    assert user.username == "jdoe"
    assert user.role == UserRole.COORDINATOR.value


def test_account_locks_after_max_failed_attempts(db_session: Session) -> None:
    service = AuthService(db_session)
    service.create_user("locktest", "Lock Test", "correct-password-1", UserRole.VIEWER)
    max_attempts = get_settings().security.max_failed_attempts

    for _ in range(max_attempts):
        with pytest.raises(AuthError):
            service.login("locktest", "wrong")

    with pytest.raises(AuthError, match=r"[Ll]ocked"):
        service.login("locktest", "correct-password-1")


def test_weak_password_rejected(db_session: Session) -> None:
    service = AuthService(db_session)
    with pytest.raises(ValueError):
        service.create_user("weak", "Weak Pw", "123", UserRole.VIEWER)


def test_viewer_cannot_edit_but_coordinator_can(db_session: Session) -> None:
    service = AuthService(db_session)
    service.create_user("viewer1", "Viewer One", "correct-password-1", UserRole.VIEWER)
    service.create_user("coord1", "Coord One", "correct-password-1", UserRole.COORDINATOR)
    viewer = service.login("viewer1", "correct-password-1")
    coord = service.login("coord1", "correct-password-1")
    assert viewer.can_edit is False
    assert coord.can_edit is True

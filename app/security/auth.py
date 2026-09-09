"""Local authentication: password hashing, login and role checks.

Passwords are hashed with PBKDF2-HMAC-SHA256 via :mod:`hashlib`, which ships
with the Python standard library and needs no compiled dependency - a good
fit for a PyInstaller-bundled desktop app. The scheme is versioned in the
stored hash string so it can be upgraded later without breaking existing
users. This module is the *only* place a password is ever hashed or compared;
nothing else in the app touches plaintext passwords.

The design deliberately keeps :class:`AuthService` free of any Active
Directory / Entra ID assumptions today, but every check goes through
``role`` on :class:`app.models.core.User`, so a future SSO backend only needs
to populate that same field.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config.constants import UserRole
from app.config.settings import get_settings
from app.models.core import User

log = logging.getLogger(__name__)

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(plain_password: str) -> str:
    """Hash a password for storage. Format: ``pbkdf2_sha256$iterations$salt$hash``."""
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Check a password against a stored hash using a constant-time comparison."""
    try:
        algorithm, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        log.warning("Encountered a malformed password hash")
        return False
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


class AuthError(Exception):
    """Raised when a login attempt cannot succeed."""


@dataclass(slots=True)
class AuthenticatedUser:
    """A logged-in user, decoupled from the ORM session that fetched it."""

    id: int
    username: str
    display_name: str
    role: str

    def has_role(self, *roles: UserRole) -> bool:
        """True if this user holds one of the given roles."""
        return UserRole(self.role) in roles

    @property
    def can_edit(self) -> bool:
        """VIEWER is read-only; ADMIN and COORDINATOR can make operational changes."""
        return self.has_role(UserRole.ADMIN, UserRole.COORDINATOR)

    @property
    def is_admin(self) -> bool:
        return self.has_role(UserRole.ADMIN)


class AuthService:
    """Login, lockout and password-management operations against ``users``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def login(self, username: str, password: str) -> AuthenticatedUser:
        """Authenticate a user, enforcing the configured lockout policy.

        Raises :class:`AuthError` with a message safe to show the user
        (never leaking whether the username or the password was wrong).
        """
        settings = get_settings().security
        user = self._session.query(User).filter(User.username == username.strip()).one_or_none()
        generic_error = "Invalid username or password."
        if user is None or not user.is_active:
            raise AuthError(generic_error)

        # Naive UTC to match the naive datetimes SQLite round-trips for these columns.
        now = datetime.now(UTC).replace(tzinfo=None)
        if user.locked_until and user.locked_until > now:
            raise AuthError(
                f"Account locked until {user.locked_until.strftime('%H:%M')}. Contact an administrator."
            )

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_failed_attempts:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_attempts = 0
            self._session.commit()
            raise AuthError(generic_error)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        self._session.commit()
        return AuthenticatedUser(
            id=user.id, username=user.username, display_name=user.display_name, role=user.role
        )

    def create_user(
        self, username: str, display_name: str, password: str, role: UserRole
    ) -> User:
        """Create a new local user. Raises ``ValueError`` if the password is too weak."""
        min_len = get_settings().security.min_password_length
        if len(password) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters.")
        user = User(
            username=username.strip(),
            display_name=display_name.strip(),
            password_hash=hash_password(password),
            role=role.value,
        )
        self._session.add(user)
        self._session.commit()
        return user

    def change_password(self, user_id: int, new_password: str) -> None:
        """Set a new password for a user, applying the configured minimum length."""
        min_len = get_settings().security.min_password_length
        if len(new_password) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters.")
        user = self._session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.password_hash = hash_password(new_password)
        self._session.commit()

    def ensure_default_admin(self) -> None:
        """Seed a first ``admin`` account if the users table is empty.

        Only ever runs once (first launch); the generated password is logged
        to the local log file, not printed to any external channel.
        """
        if self._session.query(User).count() > 0:
            return
        temp_password = os.urandom(6).hex()
        self.create_user("admin", "Administrator", temp_password, UserRole.ADMIN)
        log.warning(
            "No users existed - created default account 'admin' with temporary password: %s "
            "(change this immediately after first login)",
            temp_password,
        )

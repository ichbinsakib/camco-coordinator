"""Shared runtime context handed to every page/widget.

Avoids a pile of singletons: pages take one ``AppContext`` and get the
settings, the DB session factory and the logged-in user from it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import AppSettings
from app.security.auth import AuthenticatedUser


@dataclass(slots=True)
class AppContext:
    """Everything a UI page needs beyond its own widgets."""

    settings: AppSettings
    session_factory: sessionmaker[Session]
    current_user: AuthenticatedUser

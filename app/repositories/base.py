"""Generic repository base class.

Concrete repositories add domain-specific queries; this base only provides the
CRUD operations every one of them needs, so that logic is written once (rule
36: DRY, no duplicated business logic).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Thin CRUD wrapper around a SQLAlchemy model bound to one session."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: int) -> ModelT | None:
        """Fetch by primary key, or ``None`` if it doesn't exist."""
        return self.session.get(self.model, entity_id)

    def list_all(self, limit: int | None = None, offset: int = 0) -> list[ModelT]:
        """Return all rows, optionally paginated (rule 30: don't load everything)."""
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def add(self, entity: ModelT) -> ModelT:
        """Insert a new row and flush so its primary key is available."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        """Remove a row. Callers are responsible for audit/activity logging."""
        self.session.delete(entity)
        self.session.flush()

    def count(self) -> int:
        """Total row count for this model."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return int(self.session.scalar(stmt) or 0)

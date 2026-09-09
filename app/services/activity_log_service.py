"""Records entries to the append-only activity log.

Every meaningful field change made through the UI should call
:func:`log_field_change` so the change is traceable later (spec rule 21/45).
This module is the only writer of :class:`ActivityLogEntry` - nothing else in
the app should construct one directly, so there is exactly one place that
could ever accidentally allow an update/delete on this table.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import ActivityLogEntry


def log_field_change(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value: object,
    new_value: object,
    user_id: int | None,
    description: str | None = None,
) -> None:
    """Append one field-change record, skipping unchanged values.

    ``description`` defaults to a human-readable "field: old -> new" line so
    the activity feed reads naturally without every call site formatting it.
    """
    old_text = "" if old_value is None else str(old_value)
    new_text = "" if new_value is None else str(new_value)
    if old_text == new_text:
        return
    entry = ActivityLogEntry(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        field_name=field_name,
        old_value=old_text or None,
        new_value=new_text or None,
        description=description or f"{field_name}: {old_text or '(blank)'} -> {new_text or '(blank)'}",
    )
    session.add(entry)


def log_event(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    description: str,
    user_id: int | None,
) -> None:
    """Append a free-form event record not tied to a single field (e.g. "created")."""
    session.add(
        ActivityLogEntry(
            entity_type=entity_type, entity_id=entity_id, user_id=user_id, description=description
        )
    )

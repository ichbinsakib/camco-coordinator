"""Parts master list page."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox
from sqlalchemy import select

from app.config.constants import EntityType
from app.models.core import Customer, Part
from app.repositories.parts import PartRepository
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.dialogs.part_dialog import PartDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)

_COLUMNS = [
    ColumnSpec("Part Number", lambda p: p.part_number),
    ColumnSpec("Rev", lambda p: p.revision),
    ColumnSpec("Description", lambda p: p.description),
    ColumnSpec("Customer", lambda p: p.customer.name if p.customer else ""),
    ColumnSpec("Customer PN", lambda p: p.customer_part_number),
    ColumnSpec("Material", lambda p: p.material),
    ColumnSpec("Active", lambda p: "Yes" if p.is_active else "No"),
]


class PartsPage(ListPageBase):
    """Search, create and edit the centralized part-number record."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Parts",
            "The centralized part record referenced by orders, production and purchasing.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )
        self.on_new = self._new_part
        self.on_edit = self._edit_part
        self.on_activated = self._edit_part
        self.on_delete = self._delete_part
        self.on_notes = self._view_notes
        self.refresh()

    def _view_notes(self, row: Part) -> None:
        NotesDialog(self._context, EntityType.PART.value, row.id, row.display_name, parent=self).exec()

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[Part], int]:
        with self._context.session_factory() as session:
            rows, total = PartRepository(session).search(text, limit=limit, offset=offset)
            for part in rows:
                _ = part.customer  # force-load before detaching
            session.expunge_all()
            return rows, total

    def _new_part(self) -> None:
        with self._context.session_factory() as session:
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            dialog = PartDialog(customers, parent=self)
            if dialog.exec() != PartDialog.DialogCode.Accepted:
                return
            part = Part()
            dialog.apply_to(part)
            session.add(part)
            try:
                session.flush()
            except Exception:
                session.rollback()
                QMessageBox.warning(
                    self, "Cannot Save", "A part with this Part Number + Revision already exists."
                )
                return
            log_event(
                session,
                entity_type="PART",
                entity_id=part.id,
                description=f"Part {part.display_name} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_part(self, row: Part) -> None:
        with self._context.session_factory() as session:
            part = session.get(Part, row.id)
            if part is None:
                QMessageBox.warning(self, "Not Found", "This part no longer exists.")
                self.refresh()
                return
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            before = {"description": part.description, "is_active": part.is_active}
            dialog = PartDialog(customers, part, parent=self)
            if dialog.exec() != PartDialog.DialogCode.Accepted:
                return
            dialog.apply_to(part)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="PART",
                    entity_id=part.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(part, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

    def _delete_part(self, row: Part) -> None:
        with self._context.session_factory() as session:
            part = session.get(Part, row.id)
            if part is None:
                self.refresh()
                return
            session.delete(part)
            try:
                session.commit()
            except Exception:
                session.rollback()
                QMessageBox.warning(
                    self, "Cannot Delete", "This part is referenced by existing orders. Mark it inactive instead."
                )
                return
        self.refresh()

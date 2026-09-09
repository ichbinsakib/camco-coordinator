"""Vendors master list page."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox

from app.config.constants import EntityType
from app.models.core import Vendor
from app.repositories.vendors import VendorRepository
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.dialogs.vendor_dialog import VendorDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _lead_time_label(vendor: Vendor) -> str:
    return f"{vendor.average_lead_time_days:.0f} days" if vendor.average_lead_time_days else ""


def _on_time_label(vendor: Vendor) -> str:
    return f"{vendor.on_time_score:.0f}%" if vendor.on_time_score is not None else "—"


_COLUMNS = [
    ColumnSpec("Code", lambda v: v.code),
    ColumnSpec("Name", lambda v: v.name),
    ColumnSpec("Contact", lambda v: v.contact_name),
    ColumnSpec("Avg Lead Time", _lead_time_label),
    ColumnSpec("On-Time %", _on_time_label),
    ColumnSpec("Active", lambda v: "Yes" if v.is_active else "No"),
]


class VendorsPage(ListPageBase):
    """Search, create, edit and deactivate vendors."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Vendors",
            "The vendor master used by purchase orders and vendor follow-ups.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )
        self.on_new = self._new_vendor
        self.on_edit = self._edit_vendor
        self.on_activated = self._edit_vendor
        self.on_delete = self._delete_vendor
        self.on_notes = self._view_notes
        self.refresh()

    def _view_notes(self, row: Vendor) -> None:
        NotesDialog(self._context, EntityType.VENDOR.value, row.id, row.name, parent=self).exec()

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[Vendor], int]:
        with self._context.session_factory() as session:
            rows, total = VendorRepository(session).search(text, limit=limit, offset=offset)
            session.expunge_all()
            return rows, total

    def _new_vendor(self) -> None:
        dialog = VendorDialog(parent=self)
        if dialog.exec() != VendorDialog.DialogCode.Accepted:
            return
        with self._context.session_factory() as session:
            vendor = Vendor()
            dialog.apply_to(vendor)
            session.add(vendor)
            session.flush()
            log_event(
                session,
                entity_type="VENDOR",
                entity_id=vendor.id,
                description=f"Vendor {vendor.code} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_vendor(self, row: Vendor) -> None:
        with self._context.session_factory() as session:
            vendor = session.get(Vendor, row.id)
            if vendor is None:
                QMessageBox.warning(self, "Not Found", "This vendor no longer exists.")
                self.refresh()
                return
            before = {"name": vendor.name, "is_active": vendor.is_active}
            dialog = VendorDialog(vendor, parent=self)
            if dialog.exec() != VendorDialog.DialogCode.Accepted:
                return
            dialog.apply_to(vendor)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="VENDOR",
                    entity_id=vendor.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(vendor, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

    def _delete_vendor(self, row: Vendor) -> None:
        with self._context.session_factory() as session:
            vendor = session.get(Vendor, row.id)
            if vendor is None:
                self.refresh()
                return
            session.delete(vendor)
            try:
                session.commit()
            except Exception:
                session.rollback()
                QMessageBox.warning(
                    self,
                    "Cannot Delete",
                    "This vendor has existing purchase orders. Mark it inactive instead.",
                )
                return
        self.refresh()

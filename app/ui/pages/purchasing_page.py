"""Purchase order line list page - material/vendor follow-up worklist."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QMessageBox
from sqlalchemy import select

from app.config.constants import EntityType, PurchaseOrderStatus
from app.models.core import Part, Vendor
from app.models.purchasing import PurchaseOrderLine
from app.repositories.purchasing import (
    PurchaseLineFilters,
    PurchaseLineRow,
    PurchaseOrderRepository,
    get_or_create_po,
)
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.import_wizard_dialog import ImportWizardDialog
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.dialogs.purchase_line_dialog import EditPurchaseLineDialog, NewPurchaseLineDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _days_late_label(row: PurchaseLineRow) -> str:
    return f"{row.days_late} days late" if row.days_late > 0 else ""


_COLUMNS = [
    ColumnSpec("PO Number", lambda r: r.po_number),
    ColumnSpec("Vendor", lambda r: r.vendor_name),
    ColumnSpec("Part / Description", lambda r: r.part_display),
    ColumnSpec("Qty Ordered", lambda r: r.line.quantity_ordered, align_right=True),
    ColumnSpec("Qty Received", lambda r: r.line.quantity_received, align_right=True),
    ColumnSpec("Qty Remaining", lambda r: r.quantity_remaining, align_right=True),
    ColumnSpec("Required Date", lambda r: r.line.required_date),
    ColumnSpec("Promised Date", lambda r: r.line.promised_date),
    ColumnSpec("Days Late", _days_late_label),
    ColumnSpec("Status", lambda r: r.line.status),
    ColumnSpec("Buyer", lambda r: r.line.purchase_order.buyer),
]


class PurchasingPage(ListPageBase):
    """Search/filter purchase order lines; the material/vendor follow-up worklist."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Purchasing",
            "Every open purchase order line, with computed remaining quantity and lateness.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
            show_import=True,
        )

        filter_bar = self.filter_bar_layout()
        filter_bar.addWidget(QLabel("Status:"))
        self._status_filter = QComboBox()
        self._status_filter.addItem("Open Only", "__open__")
        self._status_filter.addItem("All Statuses", None)
        for status in PurchaseOrderStatus:
            self._status_filter.addItem(status.value, status.value)
        self._status_filter.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self._status_filter)

        self._late_only = QCheckBox("Late Only")
        self._late_only.stateChanged.connect(self.refresh)
        filter_bar.addWidget(self._late_only)

        self.on_new = self._new_line
        self.on_edit = self._edit_line
        self.on_activated = self._edit_line
        self.on_notes = self._view_notes
        self.on_import = self._import_data
        self.refresh()

    def _view_notes(self, row: PurchaseLineRow) -> None:
        title = f"{row.po_number} / {row.part_display}"
        NotesDialog(self._context, EntityType.PURCHASE_ORDER_LINE.value, row.line.id, title, parent=self).exec()

    def _import_data(self) -> None:
        dialog = ImportWizardDialog(self._context, default_target_key="purchase_order_lines", parent=self)
        if dialog.exec() == ImportWizardDialog.DialogCode.Accepted:
            self.refresh()

    def _current_filters(self, text: str) -> PurchaseLineFilters:
        selection = self._status_filter.currentData()
        return PurchaseLineFilters(
            text=text,
            status=selection if selection not in (None, "__open__") else None,
            open_only=selection == "__open__",
            late_only=self._late_only.isChecked(),
        )

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[PurchaseLineRow], int]:
        with self._context.session_factory() as session:
            repo = PurchaseOrderRepository(session)
            rows, total = repo.search_lines(self._current_filters(text), limit=limit, offset=offset)
            session.expunge_all()
            return rows, total

    def _new_line(self) -> None:
        with self._context.session_factory() as session:
            vendors = list(session.scalars(select(Vendor).where(Vendor.is_active).order_by(Vendor.name)))
            parts = list(session.scalars(select(Part).where(Part.is_active).order_by(Part.part_number)))
            if not vendors:
                QMessageBox.information(self, "Missing Data", "Create at least one active Vendor first.")
                return
            dialog = NewPurchaseLineDialog(vendors, parts, parent=self)
            if dialog.exec() != NewPurchaseLineDialog.DialogCode.Accepted:
                return

            order = get_or_create_po(session, dialog.po_number.text().strip(), dialog.selected_vendor_id)
            if dialog.buyer.text().strip():
                order.buyer = dialog.buyer.text().strip()

            next_line_number = len(order.lines) + 1
            line = PurchaseOrderLine(
                purchase_order_id=order.id,
                line_number=next_line_number,
                part_id=dialog.selected_part_id,
                description=dialog.description.text().strip() or None,
                quantity_ordered=dialog.quantity_ordered.value(),
                required_date=dialog.selected_required_date,
                status=dialog.status.currentData(),
            )
            session.add(line)
            session.flush()
            log_event(
                session,
                entity_type="PURCHASE_ORDER_LINE",
                entity_id=line.id,
                description=f"Line {next_line_number} added to {order.po_number}",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_line(self, row: PurchaseLineRow) -> None:
        with self._context.session_factory() as session:
            line = session.get(PurchaseOrderLine, row.line.id)
            if line is None:
                QMessageBox.warning(self, "Not Found", "This purchase order line no longer exists.")
                self.refresh()
                return
            before = {
                "status": line.status,
                "quantity_received": line.quantity_received,
                "promised_date": line.promised_date,
            }
            dialog = EditPurchaseLineDialog(line, parent=self)
            if dialog.exec() != EditPurchaseLineDialog.DialogCode.Accepted:
                return
            dialog.apply_to(line)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="PURCHASE_ORDER_LINE",
                    entity_id=line.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(line, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

"""RMA list page - customer-reported quality issues, aged in months (spec section 17)."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox
from sqlalchemy import select

from app.config.constants import EntityType, RmaStatus
from app.config.settings import get_settings
from app.models.core import Customer, Part
from app.models.rma import Rma
from app.repositories.rma import RmaFilters, RmaRepository, RmaRow
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.dialogs.rma_dialog import RmaDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)

_COLUMNS = [
    ColumnSpec("RMA #", lambda r: r.rma.rma_number),
    ColumnSpec("Customer", lambda r: r.customer_name),
    ColumnSpec("Part", lambda r: r.rma.part.part_number if r.rma.part else ""),
    ColumnSpec("Quantity", lambda r: r.rma.quantity, align_right=True),
    ColumnSpec("Reason", lambda r: r.rma.reason),
    ColumnSpec("Date Received", lambda r: r.rma.date_received),
    ColumnSpec("Age", lambda r: r.aging_bucket),
    ColumnSpec("Status", lambda r: r.rma.status),
]


class RmasPage(ListPageBase):
    """Search/filter RMA cases; aging is shown in months, not days."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "RMAs",
            "Return Material Authorizations, aged in months from date received to closure.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )

        filter_bar = self.filter_bar_layout()
        filter_bar.addWidget(QLabel("Status:"))
        self._status_filter = QComboBox()
        self._status_filter.addItem("Open Only", "__open__")
        self._status_filter.addItem("All Statuses", None)
        for status in RmaStatus:
            self._status_filter.addItem(status.value, status.value)
        self._status_filter.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self._status_filter)

        self.on_new = self._new_rma
        self.on_edit = self._edit_rma
        self.on_activated = self._edit_rma
        self.on_notes = self._view_notes
        self.refresh()

    def _current_filters(self, text: str) -> RmaFilters:
        selection = self._status_filter.currentData()
        return RmaFilters(
            text=text,
            status=selection if selection not in (None, "__open__") else None,
            open_only=selection == "__open__",
        )

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[RmaRow], int]:
        with self._context.session_factory() as session:
            repo = RmaRepository(session)
            rows, total = repo.search(
                self._current_filters(text), get_settings().rma, limit=limit, offset=offset
            )
            session.expunge_all()
            return rows, total

    def _view_notes(self, row: RmaRow) -> None:
        NotesDialog(self._context, EntityType.RMA.value, row.rma.id, row.rma.rma_number, parent=self).exec()

    def _new_rma(self) -> None:
        with self._context.session_factory() as session:
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            parts = list(session.scalars(select(Part).order_by(Part.part_number)))
            if not customers:
                QMessageBox.information(self, "Missing Data", "Create at least one Customer first.")
                return
            dialog = RmaDialog(customers, parts, parent=self)
            if dialog.exec() != RmaDialog.DialogCode.Accepted:
                return
            rma = Rma(rma_number="", customer_id=customers[0].id, quantity=0)
            dialog.apply_to(rma)
            session.add(rma)
            try:
                session.flush()
            except Exception:
                session.rollback()
                QMessageBox.warning(self, "Cannot Save", "An RMA with this number already exists.")
                return
            log_event(
                session,
                entity_type="RMA",
                entity_id=rma.id,
                description=f"RMA {rma.rma_number} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_rma(self, row: RmaRow) -> None:
        with self._context.session_factory() as session:
            rma = session.get(Rma, row.rma.id)
            if rma is None:
                QMessageBox.warning(self, "Not Found", "This RMA no longer exists.")
                self.refresh()
                return
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            parts = list(session.scalars(select(Part).order_by(Part.part_number)))
            before = {"status": rma.status, "corrective_action": rma.corrective_action}
            dialog = RmaDialog(customers, parts, rma, parent=self)
            if dialog.exec() != RmaDialog.DialogCode.Accepted:
                return
            dialog.apply_to(rma)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="RMA",
                    entity_id=rma.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(rma, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

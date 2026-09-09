"""Shipping list page - shipment headers plus an on-time-% analytics panel."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox
from sqlalchemy import select

from app.models.core import Customer
from app.models.shipping import Shipment
from app.repositories.shipping import (
    STANDARD_RANGES,
    ShipmentFilters,
    ShipmentRepository,
    resolve_range,
)
from app.services.activity_log_service import log_event
from app.ui.app_context import AppContext
from app.ui.dialogs.manage_shipment_lines_dialog import ManageShipmentLinesDialog
from app.ui.dialogs.shipment_dialog import ShipmentDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)

_COLUMNS = [
    ColumnSpec("Shipment #", lambda s: s.shipment_number),
    ColumnSpec("Customer", lambda s: s.customer.name if s.customer else ""),
    ColumnSpec("Carrier", lambda s: s.carrier),
    ColumnSpec("Tracking #", lambda s: s.tracking_number),
    ColumnSpec("Ship Date", lambda s: s.ship_date),
    ColumnSpec("Status", lambda s: s.status),
]


class ShippingPage(ListPageBase):
    """Search shipments, manage their lines, and view on-time-shipment %."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Shipping",
            "Outbound shipments and the on-time delivery rate over a selectable date range.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
        )
        self.on_new = self._new_shipment
        self.on_edit = self._manage_lines
        self.on_activated = self._manage_lines

        analytics_row = QHBoxLayout()
        analytics_row.addWidget(QLabel("On-Time Shipment %:"))
        self._range_combo = QComboBox()
        for label, _months in STANDARD_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.setCurrentText("Last 12 Months")
        self._range_combo.currentIndexChanged.connect(self._refresh_on_time)
        analytics_row.addWidget(self._range_combo)
        self._on_time_label = QLabel("")
        self._on_time_label.setObjectName("PageSubtitle")
        analytics_row.addWidget(self._on_time_label)
        analytics_row.addStretch()
        self.layout().insertLayout(2, analytics_row)

        self.refresh()
        self._refresh_on_time()

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[Shipment], int]:
        with self._context.session_factory() as session:
            rows, total = ShipmentRepository(session).search(
                ShipmentFilters(text=text), limit=limit, offset=offset
            )
            for shipment in rows:
                _ = shipment.customer.name if shipment.customer else None
            session.expunge_all()
            return rows, total

    def _refresh_on_time(self) -> None:
        label = self._range_combo.currentText()
        months = dict(STANDARD_RANGES)[label]
        start, end = resolve_range(label, months)
        with self._context.session_factory() as session:
            result = ShipmentRepository(session).on_time_percentage(start, end, range_label=label)
        if result.on_time_percent is None:
            self._on_time_label.setText(f"No shipment data for {label.lower()}.")
        else:
            self._on_time_label.setText(
                f"{result.on_time_percent}% on-time "
                f"({result.on_time_lines} on-time / {result.late_lines} late / "
                f"{result.unknown_lines} unknown of {result.total_shipped_lines} lines)"
            )

    def _new_shipment(self) -> None:
        with self._context.session_factory() as session:
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            dialog = ShipmentDialog(customers, parent=self)
            if dialog.exec() != ShipmentDialog.DialogCode.Accepted:
                return
            shipment = Shipment()
            dialog.apply_to(shipment)
            session.add(shipment)
            try:
                session.flush()
            except Exception:
                session.rollback()
                QMessageBox.warning(self, "Cannot Save", "A shipment with this number already exists.")
                return
            log_event(
                session,
                entity_type="SHIPMENT",
                entity_id=shipment.id,
                description=f"Shipment {shipment.shipment_number} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
            shipment_id = shipment.id
        self.refresh()
        self._refresh_on_time()
        ManageShipmentLinesDialog(self._context, shipment_id, parent=self).exec()
        self.refresh()
        self._refresh_on_time()

    def _manage_lines(self, row: Shipment) -> None:
        ManageShipmentLinesDialog(self._context, row.id, parent=self).exec()
        self.refresh()
        self._refresh_on_time()

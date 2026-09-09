"""Create/edit dialog for a shipment header."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
)

from app.config.constants import ShipmentStatus
from app.models.core import Customer
from app.models.shipping import Shipment


def _to_qdate(value: date | None) -> QDate:
    return QDate(value.year, value.month, value.day) if value else QDate.currentDate()


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class ShipmentDialog(QDialog):
    """Modal form for creating or editing one shipment header."""

    def __init__(self, customers: list[Customer], shipment: Shipment | None = None, parent=None) -> None:
        super().__init__(parent)
        self._shipment = shipment
        self.setWindowTitle("Edit Shipment" if shipment else "New Shipment")
        self.setMinimumWidth(420)

        form = QFormLayout(self)

        self.shipment_number = QLineEdit(shipment.shipment_number if shipment else "")
        self.customer = QComboBox()
        self.customer.addItem("(none)", None)
        selected_index = 0
        for index, customer in enumerate(customers, start=1):
            self.customer.addItem(f"{customer.code} - {customer.name}", customer.id)
            if shipment and shipment.customer_id == customer.id:
                selected_index = index
        self.customer.setCurrentIndex(selected_index)

        self.carrier = QLineEdit(shipment.carrier or "" if shipment else "")
        self.tracking_number = QLineEdit(shipment.tracking_number or "" if shipment else "")

        self.ship_date = QDateEdit()
        self.ship_date.setCalendarPopup(True)
        self.ship_date.setDate(_to_qdate(shipment.ship_date if shipment else None))

        self.status = QComboBox()
        for status in ShipmentStatus:
            self.status.addItem(status.value, status.value)
        if shipment:
            self.status.setCurrentText(shipment.status)

        self.notes = QPlainTextEdit(shipment.notes or "" if shipment else "")
        self.notes.setFixedHeight(60)

        form.addRow("Shipment Number *", self.shipment_number)
        form.addRow("Customer", self.customer)
        form.addRow("Carrier", self.carrier)
        form.addRow("Tracking Number", self.tracking_number)
        form.addRow("Ship Date", self.ship_date)
        form.addRow("Status", self.status)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.shipment_number.text().strip():
            return
        self.accept()

    def apply_to(self, shipment: Shipment) -> None:
        """Write the form's values onto the (possibly new) shipment."""
        shipment.shipment_number = self.shipment_number.text().strip()
        shipment.customer_id = self.customer.currentData()
        shipment.carrier = self.carrier.text().strip() or None
        shipment.tracking_number = self.tracking_number.text().strip() or None
        shipment.ship_date = _from_qdate(self.ship_date.date())
        shipment.status = self.status.currentData()
        shipment.notes = self.notes.toPlainText().strip() or None

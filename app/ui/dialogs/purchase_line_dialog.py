"""Create/edit dialogs for a purchase order line."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
)

from app.config.constants import PurchaseOrderStatus
from app.models.core import Part, Vendor
from app.models.purchasing import PurchaseOrderLine


def _to_qdate(value: date | None) -> QDate:
    return QDate(value.year, value.month, value.day) if value else QDate.currentDate()


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class NewPurchaseLineDialog(QDialog):
    """Creates a new PO line, creating the PO header if the number is new."""

    def __init__(self, vendors: list[Vendor], parts: list[Part], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Purchase Order Line")
        self.setMinimumWidth(440)

        form = QFormLayout(self)

        self.po_number = QLineEdit()
        self.po_number.setPlaceholderText("Existing or new PO number")

        self.vendor = QComboBox()
        for vendor in vendors:
            self.vendor.addItem(f"{vendor.code} - {vendor.name}", vendor.id)

        self.part = QComboBox()
        self.part.addItem("(none / non-part material)", None)
        for part in parts:
            self.part.addItem(part.display_name, part.id)

        self.description = QLineEdit()
        self.buyer = QLineEdit()

        self.quantity_ordered = QDoubleSpinBox()
        self.quantity_ordered.setRange(0, 1_000_000)
        self.quantity_ordered.setValue(1)

        self.required_date = QDateEdit()
        self.required_date.setCalendarPopup(True)
        self.required_date.setDate(QDate.currentDate())

        self.status = QComboBox()
        for status in PurchaseOrderStatus:
            self.status.addItem(status.value, status.value)

        form.addRow("PO Number *", self.po_number)
        form.addRow("Vendor *", self.vendor)
        form.addRow("Part", self.part)
        form.addRow("Description", self.description)
        form.addRow("Buyer", self.buyer)
        form.addRow("Quantity Ordered *", self.quantity_ordered)
        form.addRow("Required Date", self.required_date)
        form.addRow("Status", self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.po_number.text().strip() or self.vendor.count() == 0:
            return
        self.accept()

    @property
    def selected_vendor_id(self) -> int | None:
        return self.vendor.currentData()

    @property
    def selected_part_id(self) -> int | None:
        return self.part.currentData()

    @property
    def selected_required_date(self) -> date:
        return _from_qdate(self.required_date.date())


class EditPurchaseLineDialog(QDialog):
    """Edits quantities, dates, status and buyer on an existing PO line."""

    def __init__(self, line: PurchaseOrderLine, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Purchase Line - {line.purchase_order.po_number}")
        self.setMinimumWidth(420)

        form = QFormLayout(self)
        form.addRow("Purchase Order", QLabel(line.purchase_order.po_number))
        form.addRow("Vendor", QLabel(line.purchase_order.vendor.name))

        self.buyer = QLineEdit(line.purchase_order.buyer or "")

        self.quantity_ordered = QDoubleSpinBox()
        self.quantity_ordered.setRange(0, 1_000_000)
        self.quantity_ordered.setValue(line.quantity_ordered)

        self.quantity_received = QDoubleSpinBox()
        self.quantity_received.setRange(0, 1_000_000)
        self.quantity_received.setValue(line.quantity_received)

        self.required_date = QDateEdit()
        self.required_date.setCalendarPopup(True)
        self.required_date.setDate(_to_qdate(line.required_date))

        self.promised_date = QDateEdit()
        self.promised_date.setCalendarPopup(True)
        self.promised_date.setDate(_to_qdate(line.promised_date))

        self.status = QComboBox()
        for status in PurchaseOrderStatus:
            self.status.addItem(status.value, status.value)
        self.status.setCurrentText(line.status)

        self.notes = QPlainTextEdit(line.notes or "")
        self.notes.setFixedHeight(70)

        form.addRow("Buyer", self.buyer)
        form.addRow("Quantity Ordered", self.quantity_ordered)
        form.addRow("Quantity Received", self.quantity_received)
        form.addRow("Required Date", self.required_date)
        form.addRow("Promised Date", self.promised_date)
        form.addRow("Status", self.status)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply_to(self, line: PurchaseOrderLine) -> None:
        """Write the form's values onto the line (and its header's buyer field)."""
        line.purchase_order.buyer = self.buyer.text().strip() or None
        line.quantity_ordered = self.quantity_ordered.value()
        old_received = line.quantity_received
        line.quantity_received = self.quantity_received.value()
        line.required_date = _from_qdate(self.required_date.date())
        line.promised_date = _from_qdate(self.promised_date.date())
        line.status = self.status.currentData()
        line.notes = self.notes.toPlainText().strip() or None
        if line.quantity_received > old_received and line.actual_receipt_date is None:
            line.actual_receipt_date = date.today()

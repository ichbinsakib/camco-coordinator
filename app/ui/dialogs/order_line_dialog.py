"""Create/edit dialogs for a customer order line."""

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

from app.config.constants import OrderStatus, Priority
from app.models.core import Customer, Part
from app.models.orders import CustomerOrderLine


def _to_qdate(value: date | None) -> QDate:
    return QDate(value.year, value.month, value.day) if value else QDate.currentDate()


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class NewOrderLineDialog(QDialog):
    """Creates a new CO line, creating the CO header if the number is new."""

    def __init__(self, customers: list[Customer], parts: list[Part], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Customer Order Line")
        self.setMinimumWidth(440)
        self._customers = customers
        self._parts = parts

        form = QFormLayout(self)

        self.co_number = QLineEdit()
        self.co_number.setPlaceholderText("Existing or new CO number")
        self.customer_po = QLineEdit()

        self.customer = QComboBox()
        for customer in customers:
            self.customer.addItem(f"{customer.code} - {customer.name}", customer.id)

        self.part = QComboBox()
        for part in parts:
            self.part.addItem(part.display_name, part.id)

        self.quantity_ordered = QDoubleSpinBox()
        self.quantity_ordered.setRange(0, 1_000_000)
        self.quantity_ordered.setValue(1)

        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(QDate.currentDate())

        self.status = QComboBox()
        for status in OrderStatus:
            self.status.addItem(status.value, status.value)

        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(60)

        form.addRow("CO Number *", self.co_number)
        form.addRow("Customer PO Number", self.customer_po)
        form.addRow("Customer *", self.customer)
        form.addRow("Part *", self.part)
        form.addRow("Quantity Ordered *", self.quantity_ordered)
        form.addRow("Due Date", self.due_date)
        form.addRow("Status", self.status)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.co_number.text().strip() or self.customer.count() == 0 or self.part.count() == 0:
            return
        self.accept()

    @property
    def selected_customer_id(self) -> int | None:
        return self.customer.currentData()

    @property
    def selected_part_id(self) -> int | None:
        return self.part.currentData()

    @property
    def selected_due_date(self) -> date:
        return _from_qdate(self.due_date.date())


class EditOrderLineDialog(QDialog):
    """Edits status, quantities, due date and priority on an existing CO line."""

    def __init__(self, line: CustomerOrderLine, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit Order Line - {line.customer_order.co_number} / {line.part.part_number}")
        self.setMinimumWidth(420)

        form = QFormLayout(self)
        form.addRow("Customer Order", QLabel(line.customer_order.co_number))
        form.addRow("Part", QLabel(line.part.display_name))

        self.quantity_ordered = QDoubleSpinBox()
        self.quantity_ordered.setRange(0, 1_000_000)
        self.quantity_ordered.setValue(line.quantity_ordered)

        self.quantity_completed = QDoubleSpinBox()
        self.quantity_completed.setRange(0, 1_000_000)
        self.quantity_completed.setValue(line.quantity_completed)

        self.quantity_scrapped = QDoubleSpinBox()
        self.quantity_scrapped.setRange(0, 1_000_000)
        self.quantity_scrapped.setValue(line.quantity_scrapped)

        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(_to_qdate(line.due_date))

        self.status = QComboBox()
        for status in OrderStatus:
            self.status.addItem(status.value, status.value)
        self.status.setCurrentText(line.status)

        self.manual_priority = QComboBox()
        self.manual_priority.addItem("(auto-computed)", None)
        for priority in Priority:
            self.manual_priority.addItem(priority.value, priority.value)
        if line.manual_priority:
            self.manual_priority.setCurrentText(line.manual_priority)

        self.notes = QPlainTextEdit(line.notes or "")
        self.notes.setFixedHeight(70)

        form.addRow("Quantity Ordered", self.quantity_ordered)
        form.addRow("Quantity Completed", self.quantity_completed)
        form.addRow("Quantity Scrapped", self.quantity_scrapped)
        form.addRow("Due Date", self.due_date)
        form.addRow("Status", self.status)
        form.addRow("Manual Priority Override", self.manual_priority)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply_to(self, line: CustomerOrderLine) -> None:
        """Write the form's values onto the line being edited."""
        line.quantity_ordered = self.quantity_ordered.value()
        line.quantity_completed = self.quantity_completed.value()
        line.quantity_scrapped = self.quantity_scrapped.value()
        line.due_date = _from_qdate(self.due_date.date())
        line.status = self.status.currentData()
        line.manual_priority = self.manual_priority.currentData()
        line.notes = self.notes.toPlainText().strip() or None

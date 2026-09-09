"""Create/edit dialog for an RMA case."""

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
    QLineEdit,
    QPlainTextEdit,
)

from app.config.constants import RmaStatus
from app.models.core import Customer, Part
from app.models.rma import Rma


def _to_qdate(value: date | None) -> QDate:
    return QDate(value.year, value.month, value.day) if value else QDate.currentDate()


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class RmaDialog(QDialog):
    """Modal form for creating or editing one RMA case."""

    def __init__(
        self, customers: list[Customer], parts: list[Part], rma: Rma | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._rma = rma
        self.setWindowTitle("Edit RMA" if rma else "New RMA")
        self.setMinimumWidth(440)

        form = QFormLayout(self)

        self.rma_number = QLineEdit(rma.rma_number if rma else "")

        self.customer = QComboBox()
        selected_customer_index = 0
        for index, customer in enumerate(customers):
            self.customer.addItem(f"{customer.code} - {customer.name}", customer.id)
            if rma and rma.customer_id == customer.id:
                selected_customer_index = index
        self.customer.setCurrentIndex(selected_customer_index)

        self.part = QComboBox()
        self.part.addItem("(none)", None)
        for index, part in enumerate(parts, start=1):
            self.part.addItem(part.display_name, part.id)
            if rma and rma.part_id == part.id:
                self.part.setCurrentIndex(index)

        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 1_000_000)
        self.quantity.setValue(rma.quantity if rma else 1)

        self.reason = QLineEdit(rma.reason or "" if rma else "")

        self.date_received = QDateEdit()
        self.date_received.setCalendarPopup(True)
        self.date_received.setDate(_to_qdate(rma.date_received if rma else date.today()))

        self.status = QComboBox()
        for status in RmaStatus:
            self.status.addItem(status.value, status.value)
        if rma:
            self.status.setCurrentText(rma.status)

        self.target_completion = QDateEdit()
        self.target_completion.setCalendarPopup(True)
        self.target_completion.setDate(_to_qdate(rma.target_completion_date if rma else None))

        self.corrective_action = QPlainTextEdit(rma.corrective_action or "" if rma else "")
        self.corrective_action.setFixedHeight(60)

        self.notes = QPlainTextEdit(rma.notes or "" if rma else "")
        self.notes.setFixedHeight(60)

        form.addRow("RMA Number *", self.rma_number)
        form.addRow("Customer *", self.customer)
        form.addRow("Part", self.part)
        form.addRow("Quantity", self.quantity)
        form.addRow("Reason", self.reason)
        form.addRow("Date Received", self.date_received)
        form.addRow("Status", self.status)
        form.addRow("Target Completion", self.target_completion)
        form.addRow("Corrective Action", self.corrective_action)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.rma_number.text().strip() or self.customer.count() == 0:
            return
        self.accept()

    def apply_to(self, rma: Rma) -> None:
        """Write the form's values onto the (possibly new) RMA."""
        was_open = rma.status not in {RmaStatus.CLOSED.value, RmaStatus.CANCELLED.value} if rma.id else True
        rma.rma_number = self.rma_number.text().strip()
        rma.customer_id = self.customer.currentData()
        rma.part_id = self.part.currentData()
        rma.quantity = self.quantity.value()
        rma.reason = self.reason.text().strip() or None
        rma.date_received = _from_qdate(self.date_received.date())
        rma.status = self.status.currentData()
        rma.target_completion_date = _from_qdate(self.target_completion.date())
        rma.corrective_action = self.corrective_action.toPlainText().strip() or None
        rma.notes = self.notes.toPlainText().strip() or None
        now_closed = rma.status in {RmaStatus.CLOSED.value, RmaStatus.CANCELLED.value}
        if was_open and now_closed and rma.actual_completion_date is None:
            rma.actual_completion_date = date.today()

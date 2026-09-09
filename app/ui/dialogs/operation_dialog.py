"""Add/edit dialog for a single production routing operation (OP10, OP20, ...)."""

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
    QSpinBox,
)

from app.config.constants import Department, ProductionStatus
from app.models.production import ProductionOperation


class OperationDialog(QDialog):
    """Modal form for creating or editing one routing operation."""

    def __init__(self, operation: ProductionOperation | None = None, *, next_sequence: int = 10, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Operation" if operation else "New Operation")
        self.setMinimumWidth(400)

        form = QFormLayout(self)

        self.sequence = QSpinBox()
        self.sequence.setRange(1, 9999)
        self.sequence.setValue(operation.sequence if operation else next_sequence)

        self.operation_name = QLineEdit(operation.operation_name if operation else "")
        self.work_center = QLineEdit(operation.work_center or "" if operation else "")

        self.department = QComboBox()
        self.department.addItem("(unspecified)", None)
        for dept in Department:
            self.department.addItem(dept.value, dept.value)
        if operation and operation.department:
            self.department.setCurrentText(operation.department)

        self.planned_quantity = QDoubleSpinBox()
        self.planned_quantity.setRange(0, 1_000_000)
        self.planned_quantity.setValue(operation.planned_quantity if operation else 0)

        self.completed_quantity = QDoubleSpinBox()
        self.completed_quantity.setRange(0, 1_000_000)
        self.completed_quantity.setValue(operation.completed_quantity if operation else 0)

        self.scrap_quantity = QDoubleSpinBox()
        self.scrap_quantity.setRange(0, 1_000_000)
        self.scrap_quantity.setValue(operation.scrap_quantity if operation else 0)

        self.status = QComboBox()
        for status in ProductionStatus:
            self.status.addItem(status.value, status.value)
        if operation:
            self.status.setCurrentText(operation.status)

        self.planned_completion = QDateEdit()
        self.planned_completion.setCalendarPopup(True)
        if operation and operation.planned_completion_date:
            d = operation.planned_completion_date
            self.planned_completion.setDate(QDate(d.year, d.month, d.day))
        else:
            self.planned_completion.setDate(QDate.currentDate())

        self.notes = QPlainTextEdit(operation.notes or "" if operation else "")
        self.notes.setFixedHeight(60)

        form.addRow("Sequence *", self.sequence)
        form.addRow("Operation Name *", self.operation_name)
        form.addRow("Work Center", self.work_center)
        form.addRow("Department", self.department)
        form.addRow("Planned Quantity", self.planned_quantity)
        form.addRow("Completed Quantity", self.completed_quantity)
        form.addRow("Scrap Quantity", self.scrap_quantity)
        form.addRow("Status", self.status)
        form.addRow("Planned Completion", self.planned_completion)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.operation_name.text().strip():
            return
        self.accept()

    def apply_to(self, operation: ProductionOperation, *, as_of: date) -> None:
        """Write the form's values onto the operation, resetting ``status_since`` on change."""
        status_changed = operation.status != self.status.currentData()
        operation.sequence = self.sequence.value()
        operation.operation_name = self.operation_name.text().strip()
        operation.work_center = self.work_center.text().strip() or None
        operation.department = self.department.currentData()
        operation.planned_quantity = self.planned_quantity.value()
        operation.completed_quantity = self.completed_quantity.value()
        operation.scrap_quantity = self.scrap_quantity.value()
        operation.status = self.status.currentData()
        d = self.planned_completion.date()
        operation.planned_completion_date = date(d.year(), d.month(), d.day())
        operation.notes = self.notes.toPlainText().strip() or None
        if status_changed or operation.status_since is None:
            operation.status_since = as_of

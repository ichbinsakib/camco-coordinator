"""Create dialog for a new production order against an open CO line."""

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
)

from app.models.orders import CustomerOrderLine


class NewProductionOrderDialog(QDialog):
    """Pick an open CO line and open a production order against it."""

    def __init__(self, eligible_lines: list[CustomerOrderLine], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Production Order")
        self.setMinimumWidth(440)
        self._lines = eligible_lines

        form = QFormLayout(self)

        self.co_line = QComboBox()
        for line in eligible_lines:
            label = f"{line.customer_order.co_number} / {line.part.part_number} (qty {line.quantity_remaining:.0f})"
            self.co_line.addItem(label, line.id)
        self.co_line.currentIndexChanged.connect(self._suggest_production_number)

        self.production_number = QLineEdit()

        self.planned_quantity = QDoubleSpinBox()
        self.planned_quantity.setRange(0, 1_000_000)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())

        self.planned_completion = QDateEdit()
        self.planned_completion.setCalendarPopup(True)
        self.planned_completion.setDate(QDate.currentDate())

        form.addRow("Customer Order Line *", self.co_line)
        form.addRow("Production Number *", self.production_number)
        form.addRow("Planned Quantity *", self.planned_quantity)
        form.addRow("Start Date", self.start_date)
        form.addRow("Planned Completion", self.planned_completion)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if eligible_lines:
            self._suggest_production_number(0)

    def _suggest_production_number(self, index: int) -> None:
        if not (0 <= index < len(self._lines)):
            return
        line = self._lines[index]
        self.production_number.setText(f"{line.customer_order.co_number}-{line.line_number}")
        self.planned_quantity.setValue(line.quantity_remaining)

    def _on_accept(self) -> None:
        if not self.production_number.text().strip() or self.co_line.count() == 0:
            return
        self.accept()

    @property
    def selected_line_id(self) -> int | None:
        return self.co_line.currentData()

    @property
    def selected_start_date(self) -> date:
        return date(self.start_date.date().year(), self.start_date.date().month(), self.start_date.date().day())

    @property
    def selected_planned_completion(self) -> date:
        d = self.planned_completion.date()
        return date(d.year(), d.month(), d.day())

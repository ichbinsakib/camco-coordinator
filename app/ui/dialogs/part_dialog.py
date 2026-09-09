"""Create/edit dialog for :class:`app.models.core.Part`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
)

from app.models.core import Customer, Part


class PartDialog(QDialog):
    """Modal form for creating or editing one part."""

    def __init__(self, customers: list[Customer], part: Part | None = None, parent=None) -> None:
        super().__init__(parent)
        self._part = part
        self.setWindowTitle("Edit Part" if part else "New Part")
        self.setMinimumWidth(440)

        form = QFormLayout(self)

        self.part_number = QLineEdit(part.part_number if part else "")
        self.revision = QLineEdit(part.revision if part else "-")
        self.description = QLineEdit(part.description or "" if part else "")

        self.customer = QComboBox()
        self.customer.addItem("(none)", None)
        selected_index = 0
        for index, customer in enumerate(customers, start=1):
            self.customer.addItem(f"{customer.code} - {customer.name}", customer.id)
            if part and part.customer_id == customer.id:
                selected_index = index
        self.customer.setCurrentIndex(selected_index)

        self.customer_part_number = QLineEdit(part.customer_part_number or "" if part else "")
        self.drawing_number = QLineEdit(part.drawing_number or "" if part else "")
        self.material = QLineEdit(part.material or "" if part else "")
        self.finish = QLineEdit(part.finish or "" if part else "")
        self.lead_time = QSpinBox()
        self.lead_time.setRange(0, 999)
        self.lead_time.setSuffix(" days")
        self.lead_time.setValue(part.standard_lead_time_days or 0 if part else 0)
        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(part.is_active if part else True)
        self.notes = QPlainTextEdit(part.notes or "" if part else "")
        self.notes.setFixedHeight(70)

        form.addRow("Part Number *", self.part_number)
        form.addRow("Revision", self.revision)
        form.addRow("Description", self.description)
        form.addRow("Customer", self.customer)
        form.addRow("Customer Part Number", self.customer_part_number)
        form.addRow("Drawing Number", self.drawing_number)
        form.addRow("Material", self.material)
        form.addRow("Finish", self.finish)
        form.addRow("Standard Lead Time", self.lead_time)
        form.addRow(self.is_active)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.part_number.text().strip():
            return
        self.accept()

    def apply_to(self, part: Part) -> None:
        """Write the form's values onto a (possibly new) :class:`Part`."""
        part.part_number = self.part_number.text().strip()
        part.revision = self.revision.text().strip() or "-"
        part.description = self.description.text().strip() or None
        part.customer_id = self.customer.currentData()
        part.customer_part_number = self.customer_part_number.text().strip() or None
        part.drawing_number = self.drawing_number.text().strip() or None
        part.material = self.material.text().strip() or None
        part.finish = self.finish.text().strip() or None
        part.standard_lead_time_days = self.lead_time.value() or None
        part.is_active = self.is_active.isChecked()
        part.notes = self.notes.toPlainText().strip() or None

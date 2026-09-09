"""Create/edit dialog for :class:`app.models.core.Customer`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
)

from app.models.core import Customer


class CustomerDialog(QDialog):
    """Modal form for creating or editing one customer."""

    def __init__(self, customer: Customer | None = None, parent=None) -> None:
        super().__init__(parent)
        self._customer = customer
        self.setWindowTitle("Edit Customer" if customer else "New Customer")
        self.setMinimumWidth(420)

        form = QFormLayout(self)

        self.code = QLineEdit(customer.code if customer else "")
        self.name = QLineEdit(customer.name if customer else "")
        self.importance = QSpinBox()
        self.importance.setRange(1, 5)
        self.importance.setValue(customer.importance if customer else 3)
        self.importance.setToolTip("1 = strategic account ... 5 = low priority")
        self.contact_name = QLineEdit(customer.contact_name or "" if customer else "")
        self.contact_email = QLineEdit(customer.contact_email or "" if customer else "")
        self.contact_phone = QLineEdit(customer.contact_phone or "" if customer else "")
        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(customer.is_active if customer else True)
        self.notes = QPlainTextEdit(customer.notes or "" if customer else "")
        self.notes.setFixedHeight(80)

        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Importance (1=strategic)", self.importance)
        form.addRow("Contact Name", self.contact_name)
        form.addRow("Contact Email", self.contact_email)
        form.addRow("Contact Phone", self.contact_phone)
        form.addRow(self.is_active)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.code.text().strip() or not self.name.text().strip():
            return
        self.accept()

    def apply_to(self, customer: Customer) -> None:
        """Write the form's values onto a (possibly new) :class:`Customer`."""
        customer.code = self.code.text().strip()
        customer.name = self.name.text().strip()
        customer.importance = self.importance.value()
        customer.contact_name = self.contact_name.text().strip() or None
        customer.contact_email = self.contact_email.text().strip() or None
        customer.contact_phone = self.contact_phone.text().strip() or None
        customer.is_active = self.is_active.isChecked()
        customer.notes = self.notes.toPlainText().strip() or None

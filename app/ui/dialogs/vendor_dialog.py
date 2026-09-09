"""Create/edit dialog for :class:`app.models.core.Vendor`."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
)

from app.models.core import Vendor


class VendorDialog(QDialog):
    """Modal form for creating or editing one vendor."""

    def __init__(self, vendor: Vendor | None = None, parent=None) -> None:
        super().__init__(parent)
        self._vendor = vendor
        self.setWindowTitle("Edit Vendor" if vendor else "New Vendor")
        self.setMinimumWidth(420)

        form = QFormLayout(self)

        self.code = QLineEdit(vendor.code if vendor else "")
        self.name = QLineEdit(vendor.name if vendor else "")
        self.contact_name = QLineEdit(vendor.contact_name or "" if vendor else "")
        self.contact_email = QLineEdit(vendor.contact_email or "" if vendor else "")
        self.contact_phone = QLineEdit(vendor.contact_phone or "" if vendor else "")
        self.lead_time = QDoubleSpinBox()
        self.lead_time.setRange(0, 999)
        self.lead_time.setSuffix(" days")
        self.lead_time.setValue(vendor.average_lead_time_days or 0 if vendor else 0)
        self.is_active = QCheckBox("Active")
        self.is_active.setChecked(vendor.is_active if vendor else True)
        self.notes = QPlainTextEdit(vendor.notes or "" if vendor else "")
        self.notes.setFixedHeight(80)

        form.addRow("Code *", self.code)
        form.addRow("Name *", self.name)
        form.addRow("Contact Name", self.contact_name)
        form.addRow("Contact Email", self.contact_email)
        form.addRow("Contact Phone", self.contact_phone)
        form.addRow("Average Lead Time", self.lead_time)
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

    def apply_to(self, vendor: Vendor) -> None:
        """Write the form's values onto a (possibly new) :class:`Vendor`."""
        vendor.code = self.code.text().strip()
        vendor.name = self.name.text().strip()
        vendor.contact_name = self.contact_name.text().strip() or None
        vendor.contact_email = self.contact_email.text().strip() or None
        vendor.contact_phone = self.contact_phone.text().strip() or None
        vendor.average_lead_time_days = self.lead_time.value() or None
        vendor.is_active = self.is_active.isChecked()
        vendor.notes = self.notes.toPlainText().strip() or None

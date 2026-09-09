"""Create/edit dialog for a coordinator follow-up."""

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

from app.config.constants import CommunicationMethod, Department, FollowUpStatus, Priority
from app.models.core import Customer, Vendor
from app.models.followup import FollowUp


def _to_qdate(value: date | None) -> QDate | None:
    return QDate(value.year, value.month, value.day) if value else None


def _from_qdate(value: QDate) -> date | None:
    return date(value.year(), value.month(), value.day()) if value.isValid() else None


class FollowUpDialog(QDialog):
    """Modal form for creating or editing one follow-up."""

    def __init__(
        self,
        customers: list[Customer],
        vendors: list[Vendor],
        follow_up: FollowUp | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._follow_up = follow_up
        self.setWindowTitle("Edit Follow-Up" if follow_up else "New Follow-Up")
        self.setMinimumWidth(440)

        form = QFormLayout(self)

        self.subject = QLineEdit(follow_up.subject if follow_up else "")

        self.customer = QComboBox()
        self.customer.addItem("(none)", None)
        for index, customer in enumerate(customers, start=1):
            self.customer.addItem(f"{customer.code} - {customer.name}", customer.id)
            if follow_up and follow_up.customer_id == customer.id:
                self.customer.setCurrentIndex(index)

        self.vendor = QComboBox()
        self.vendor.addItem("(none)", None)
        for index, vendor in enumerate(vendors, start=1):
            self.vendor.addItem(f"{vendor.code} - {vendor.name}", vendor.id)
            if follow_up and follow_up.vendor_id == vendor.id:
                self.vendor.setCurrentIndex(index)

        self.department = QComboBox()
        self.department.addItem("(unspecified)", None)
        for dept in Department:
            self.department.addItem(dept.value, dept.value)
        if follow_up and follow_up.department:
            self.department.setCurrentText(follow_up.department)

        self.priority = QComboBox()
        for priority in Priority:
            self.priority.addItem(priority.value, priority.value)
        self.priority.setCurrentText(follow_up.priority if follow_up else Priority.MEDIUM.value)

        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(_to_qdate(follow_up.due_date if follow_up else date.today()) or QDate.currentDate())

        self.status = QComboBox()
        for status in FollowUpStatus:
            self.status.addItem(status.value, status.value)
        if follow_up:
            self.status.setCurrentText(follow_up.status)

        self.communication_method = QComboBox()
        self.communication_method.addItem("(unspecified)", None)
        for method in CommunicationMethod:
            self.communication_method.addItem(method.value, method.value)
        if follow_up and follow_up.communication_method:
            self.communication_method.setCurrentText(follow_up.communication_method)

        self.next_followup_date = QDateEdit()
        self.next_followup_date.setCalendarPopup(True)
        self.next_followup_date.setSpecialValueText(" ")
        self.next_followup_date.setDate(
            _to_qdate(follow_up.next_followup_date if follow_up else None) or self.next_followup_date.minimumDate()
        )

        self.notes = QPlainTextEdit(follow_up.notes or "" if follow_up else "")
        self.notes.setFixedHeight(70)

        form.addRow("Subject *", self.subject)
        form.addRow("Customer", self.customer)
        form.addRow("Vendor", self.vendor)
        form.addRow("Department", self.department)
        form.addRow("Priority", self.priority)
        form.addRow("Due Date", self.due_date)
        form.addRow("Status", self.status)
        form.addRow("Communication Method", self.communication_method)
        form.addRow("Next Follow-Up Date", self.next_followup_date)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self.subject.text().strip():
            return
        self.accept()

    def apply_to(self, follow_up: FollowUp) -> None:
        """Write the form's values onto the (possibly new) follow-up."""
        was_open = follow_up.status not in {FollowUpStatus.COMPLETED.value, FollowUpStatus.CANCELLED.value} if follow_up.id else True
        follow_up.subject = self.subject.text().strip()
        follow_up.customer_id = self.customer.currentData()
        follow_up.vendor_id = self.vendor.currentData()
        follow_up.department = self.department.currentData()
        follow_up.priority = self.priority.currentData()
        follow_up.due_date = _from_qdate(self.due_date.date())
        follow_up.status = self.status.currentData()
        follow_up.communication_method = self.communication_method.currentData()
        follow_up.next_followup_date = (
            _from_qdate(self.next_followup_date.date())
            if self.next_followup_date.date() != self.next_followup_date.minimumDate()
            else None
        )
        follow_up.notes = self.notes.toPlainText().strip() or None
        now_closed = follow_up.status in {FollowUpStatus.COMPLETED.value, FollowUpStatus.CANCELLED.value}
        if was_open and now_closed:
            follow_up.last_contacted_date = date.today()

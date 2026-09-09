"""Customers master list page."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox

from app.config.constants import EntityType
from app.models.core import Customer
from app.repositories.customers import CustomerRepository
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.customer_dialog import CustomerDialog
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _importance_label(customer: Customer) -> str:
    return {1: "1 - Strategic", 2: "2", 3: "3", 4: "4", 5: "5 - Low"}.get(
        customer.importance, str(customer.importance)
    )


_COLUMNS = [
    ColumnSpec("Code", lambda c: c.code),
    ColumnSpec("Name", lambda c: c.name),
    ColumnSpec("Importance", _importance_label),
    ColumnSpec("Contact", lambda c: c.contact_name),
    ColumnSpec("Email", lambda c: c.contact_email),
    ColumnSpec("Phone", lambda c: c.contact_phone),
    ColumnSpec("Active", lambda c: "Yes" if c.is_active else "No"),
]


class CustomersPage(ListPageBase):
    """Search, create, edit and deactivate customers."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Customers",
            "The customer master used by customer orders, RMAs and follow-ups.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )
        self.on_new = self._new_customer
        self.on_edit = self._edit_customer
        self.on_activated = self._edit_customer
        self.on_delete = self._delete_customer
        self.on_notes = self._view_notes
        self.refresh()

    def _view_notes(self, row: Customer) -> None:
        NotesDialog(self._context, EntityType.CUSTOMER.value, row.id, row.name, parent=self).exec()

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[Customer], int]:
        with self._context.session_factory() as session:
            rows, total = CustomerRepository(session).search(text, limit=limit, offset=offset)
            session.expunge_all()
            return rows, total

    def _new_customer(self) -> None:
        dialog = CustomerDialog(parent=self)
        if dialog.exec() != CustomerDialog.DialogCode.Accepted:
            return
        with self._context.session_factory() as session:
            customer = Customer()
            dialog.apply_to(customer)
            session.add(customer)
            session.flush()
            log_event(
                session,
                entity_type="CUSTOMER",
                entity_id=customer.id,
                description=f"Customer {customer.code} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_customer(self, row: Customer) -> None:
        with self._context.session_factory() as session:
            customer = session.get(Customer, row.id)
            if customer is None:
                QMessageBox.warning(self, "Not Found", "This customer no longer exists.")
                self.refresh()
                return
            before = {"name": customer.name, "importance": customer.importance, "is_active": customer.is_active}
            dialog = CustomerDialog(customer, parent=self)
            if dialog.exec() != CustomerDialog.DialogCode.Accepted:
                return
            dialog.apply_to(customer)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="CUSTOMER",
                    entity_id=customer.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(customer, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

    def _delete_customer(self, row: Customer) -> None:
        with self._context.session_factory() as session:
            customer = session.get(Customer, row.id)
            if customer is None:
                self.refresh()
                return
            if customer.customer_orders:
                QMessageBox.warning(
                    self,
                    "Cannot Delete",
                    "This customer has existing orders. Mark it inactive instead of deleting it.",
                )
                return
            session.delete(customer)
            session.commit()
        self.refresh()

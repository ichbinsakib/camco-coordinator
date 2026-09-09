"""Customer Order line list page - the primary coordination worklist."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox
from sqlalchemy import select

from app.config.constants import EntityType, OrderStatus
from app.config.settings import get_settings
from app.models.core import Customer, Part
from app.models.orders import CustomerOrderLine
from app.repositories.customer_orders import (
    CustomerOrderRepository,
    OrderLineFilters,
    OrderLineRow,
    get_or_create_order,
)
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.dialogs.order_line_dialog import EditOrderLineDialog, NewOrderLineDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _priority_color(row: OrderLineRow) -> str | None:
    return get_settings().color_for(row.priority.value)


def _days_late_label(row: OrderLineRow) -> str:
    return f"{row.days_late} late" if row.days_late > 0 else ""


def _due_label(row: OrderLineRow) -> str:
    if row.days_until_due is None:
        return ""
    if row.days_until_due < 0:
        return f"{-row.days_until_due} days ago"
    if row.days_until_due == 0:
        return "Today"
    return f"in {row.days_until_due} days"


_COLUMNS = [
    ColumnSpec("CO Number", lambda r: r.co_number),
    ColumnSpec("Customer", lambda r: r.customer_name),
    ColumnSpec("Part", lambda r: r.part_display),
    ColumnSpec("Qty Ordered", lambda r: r.line.quantity_ordered, align_right=True),
    ColumnSpec("Qty Completed", lambda r: r.line.quantity_completed, align_right=True),
    ColumnSpec("Qty Remaining", lambda r: r.quantity_remaining, align_right=True),
    ColumnSpec("Due Date", lambda r: r.line.due_date),
    ColumnSpec("Due", _due_label),
    ColumnSpec("Status", lambda r: r.line.status, color=lambda r: get_settings().color_for(r.line.status)),
    ColumnSpec("Priority", lambda r: r.priority.value, color=_priority_color),
]


class CustomerOrdersPage(ListPageBase):
    """Search/filter customer order lines; the line-level worklist coordinators live in."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Customer Orders",
            "Every open order line, with computed remaining quantity, lateness and priority.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )

        filter_bar = self.filter_bar_layout()
        filter_bar.addWidget(QLabel("Status:"))
        self._status_filter = QComboBox()
        self._status_filter.addItem("Open Only", "__open__")
        self._status_filter.addItem("All Statuses", None)
        for status in OrderStatus:
            self._status_filter.addItem(status.value, status.value)
        self._status_filter.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self._status_filter)

        self.on_new = self._new_line
        self.on_edit = self._edit_line
        self.on_activated = self._edit_line
        self.on_notes = self._view_notes
        self.refresh()

    def _view_notes(self, row: OrderLineRow) -> None:
        title = f"{row.co_number} / {row.part_display}"
        NotesDialog(self._context, EntityType.CUSTOMER_ORDER_LINE.value, row.line.id, title, parent=self).exec()

    def _current_filters(self, text: str) -> OrderLineFilters:
        selection = self._status_filter.currentData()
        return OrderLineFilters(
            text=text,
            status=selection if selection not in (None, "__open__") else None,
            open_only=selection == "__open__",
        )

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[OrderLineRow], int]:
        with self._context.session_factory() as session:
            repo = CustomerOrderRepository(session)
            filters = self._current_filters(text)
            rows, total = repo.search_lines(
                filters, get_settings().priority, limit=limit, offset=offset
            )
            session.expunge_all()
            return rows, total

    def _new_line(self) -> None:
        with self._context.session_factory() as session:
            customers = list(session.scalars(select(Customer).where(Customer.is_active).order_by(Customer.name)))
            parts = list(session.scalars(select(Part).where(Part.is_active).order_by(Part.part_number)))
            if not customers or not parts:
                QMessageBox.information(
                    self, "Missing Data", "Create at least one active Customer and Part first."
                )
                return
            dialog = NewOrderLineDialog(customers, parts, parent=self)
            if dialog.exec() != NewOrderLineDialog.DialogCode.Accepted:
                return

            order = get_or_create_order(
                session, dialog.co_number.text().strip(), dialog.selected_customer_id
            )
            if dialog.customer_po.text().strip():
                order.customer_po_number = dialog.customer_po.text().strip()

            next_line_number = len(order.lines) + 1
            line = CustomerOrderLine(
                customer_order_id=order.id,
                line_number=next_line_number,
                part_id=dialog.selected_part_id,
                quantity_ordered=dialog.quantity_ordered.value(),
                due_date=dialog.selected_due_date,
                original_due_date=dialog.selected_due_date,
                status=dialog.status.currentData(),
                notes=dialog.notes.toPlainText().strip() or None,
            )
            session.add(line)
            session.flush()
            log_event(
                session,
                entity_type="CUSTOMER_ORDER_LINE",
                entity_id=line.id,
                description=f"Line {next_line_number} added to {order.co_number}",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_line(self, row: OrderLineRow) -> None:
        with self._context.session_factory() as session:
            line = session.get(CustomerOrderLine, row.line.id)
            if line is None:
                QMessageBox.warning(self, "Not Found", "This order line no longer exists.")
                self.refresh()
                return
            before = {
                "status": line.status,
                "quantity_completed": line.quantity_completed,
                "due_date": line.due_date,
            }
            dialog = EditOrderLineDialog(line, parent=self)
            if dialog.exec() != EditOrderLineDialog.DialogCode.Accepted:
                return
            dialog.apply_to(line)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="CUSTOMER_ORDER_LINE",
                    entity_id=line.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(line, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

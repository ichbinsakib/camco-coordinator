"""Production order list page - part, current operation, and how long it's been there."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox
from sqlalchemy import select

from app.config.constants import CLOSED_ORDER_STATUSES
from app.models.orders import CustomerOrderLine
from app.models.production import ProductionOrder
from app.repositories.production import (
    ProductionOrderFilters,
    ProductionOrderRepository,
    ProductionOrderRow,
)
from app.services.activity_log_service import log_event
from app.ui.app_context import AppContext
from app.ui.dialogs.manage_operations_dialog import ManageOperationsDialog
from app.ui.dialogs.production_order_dialog import NewProductionOrderDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _current_op_label(row: ProductionOrderRow) -> str:
    if row.current_operation is None:
        return "Complete"
    return f"OP{row.current_operation.sequence} - {row.current_operation.operation_name}"


def _days_label(row: ProductionOrderRow) -> str:
    return f"{row.days_in_status} days" if row.current_operation else ""


_COLUMNS = [
    ColumnSpec("Production #", lambda r: r.order.production_number),
    ColumnSpec("CO", lambda r: r.co_number),
    ColumnSpec("Part", lambda r: r.part_display),
    ColumnSpec("Planned Qty", lambda r: r.order.planned_quantity, align_right=True),
    ColumnSpec("Current Operation", _current_op_label),
    ColumnSpec("Op Status", lambda r: r.current_operation.status if r.current_operation else ""),
    ColumnSpec("Days in Status", _days_label),
    ColumnSpec("Planned Completion", lambda r: r.order.planned_completion_date),
]


class ProductionPage(ListPageBase):
    """Search production orders and manage each one's routing operations."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Production",
            "Production orders with their current routing operation and how long it's been there.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
        )
        self.on_new = self._new_order
        self.on_edit = self._manage_operations
        self.on_activated = self._manage_operations
        self.refresh()

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[ProductionOrderRow], int]:
        with self._context.session_factory() as session:
            repo = ProductionOrderRepository(session)
            rows, total = repo.search(
                ProductionOrderFilters(text=text, open_only=False), limit=limit, offset=offset
            )
            session.expunge_all()
            return rows, total

    def _new_order(self) -> None:
        with self._context.session_factory() as session:
            closed_values = [s.value for s in CLOSED_ORDER_STATUSES]
            existing_line_ids = {
                po.customer_order_line_id for po in session.scalars(select(ProductionOrder))
            }
            candidate_lines = list(
                session.scalars(
                    select(CustomerOrderLine).where(CustomerOrderLine.status.notin_(closed_values))
                )
            )
            eligible = [line for line in candidate_lines if line.id not in existing_line_ids]
            if not eligible:
                QMessageBox.information(
                    self,
                    "No Eligible Lines",
                    "Every open customer order line already has a production order.",
                )
                return
            for line in eligible:
                _ = line.customer_order.co_number
                _ = line.part.part_number

            dialog = NewProductionOrderDialog(eligible, parent=self)
            if dialog.exec() != NewProductionOrderDialog.DialogCode.Accepted:
                return

            order = ProductionOrder(
                production_number=dialog.production_number.text().strip(),
                customer_order_line_id=dialog.selected_line_id,
                part_id=next(
                    line.part_id for line in eligible if line.id == dialog.selected_line_id
                ),
                planned_quantity=dialog.planned_quantity.value(),
                start_date=dialog.selected_start_date,
                planned_completion_date=dialog.selected_planned_completion,
            )
            session.add(order)
            try:
                session.flush()
            except Exception:
                session.rollback()
                QMessageBox.warning(self, "Cannot Save", "A production order with this number already exists.")
                return
            log_event(
                session,
                entity_type="PRODUCTION_ORDER",
                entity_id=order.id,
                description=f"Production order {order.production_number} created",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _manage_operations(self, row: ProductionOrderRow) -> None:
        dialog = ManageOperationsDialog(self._context, row.order.id, parent=self)
        dialog.exec()
        self.refresh()

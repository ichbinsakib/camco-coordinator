"""Modal list of one production order's routing operations, with Add/Edit/Delete.

Unlike the other edit dialogs, this one commits each change immediately
(each operation is its own record) rather than staging everything behind one
Save button - the same pattern a coordinator expects from a small embedded
worklist.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from app.models.production import ProductionOperation, ProductionOrder
from app.services.activity_log_service import log_event
from app.ui.app_context import AppContext
from app.ui.dialogs.operation_dialog import OperationDialog
from app.ui.widgets.table_model import ColumnSpec, ListTableModel


def _days_label(op: ProductionOperation) -> str:
    days = op.days_in_status(date.today())
    return f"{days}d" if days else ""


_COLUMNS = [
    ColumnSpec("Seq", lambda op: op.sequence),
    ColumnSpec("Operation", lambda op: op.operation_name),
    ColumnSpec("Work Center", lambda op: op.work_center),
    ColumnSpec("Department", lambda op: op.department),
    ColumnSpec("Planned", lambda op: op.planned_quantity, align_right=True),
    ColumnSpec("Completed", lambda op: op.completed_quantity, align_right=True),
    ColumnSpec("Status", lambda op: op.status),
    ColumnSpec("Days in Status", _days_label),
]


class ManageOperationsDialog(QDialog):
    """Add, edit and remove routing operations for one production order."""

    def __init__(self, context: AppContext, production_order_id: int, parent=None) -> None:
        super().__init__(parent)
        self._context = context
        self._production_order_id = production_order_id
        self.setWindowTitle("Manage Routing Operations")
        self.setMinimumSize(680, 420)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Operation")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_operation)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_operation)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_operation)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._model = ListTableModel(_COLUMNS)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Reload operations for this production order from the database."""
        with self._context.session_factory() as session:
            order = session.get(ProductionOrder, self._production_order_id)
            operations = list(order.operations) if order else []
            session.expunge_all()
        self._model.set_rows(operations)

    def _selected(self) -> ProductionOperation | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_object(indexes[0].row())

    def _add_operation(self) -> None:
        existing = [self._model.row_object(i) for i in range(self._model.rowCount())]
        next_sequence = (max((op.sequence for op in existing), default=0) // 10 + 1) * 10
        dialog = OperationDialog(next_sequence=next_sequence, parent=self)
        if dialog.exec() != OperationDialog.DialogCode.Accepted:
            return
        with self._context.session_factory() as session:
            operation = ProductionOperation(production_order_id=self._production_order_id)
            dialog.apply_to(operation, as_of=date.today())
            session.add(operation)
            try:
                session.flush()
            except Exception:
                session.rollback()
                QMessageBox.warning(self, "Cannot Save", "An operation with this sequence already exists.")
                return
            log_event(
                session,
                entity_type="PRODUCTION_ORDER",
                entity_id=self._production_order_id,
                description=f"Operation {operation.sequence} ({operation.operation_name}) added",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_operation(self) -> None:
        row = self._selected()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select an operation to edit first.")
            return
        with self._context.session_factory() as session:
            operation = session.get(ProductionOperation, row.id)
            if operation is None:
                self.refresh()
                return
            dialog = OperationDialog(operation, parent=self)
            if dialog.exec() != OperationDialog.DialogCode.Accepted:
                return
            old_status = operation.status
            dialog.apply_to(operation, as_of=date.today())
            if old_status != operation.status:
                log_event(
                    session,
                    entity_type="PRODUCTION_ORDER",
                    entity_id=self._production_order_id,
                    description=f"Operation {operation.sequence} status: {old_status} -> {operation.status}",
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

    def _delete_operation(self) -> None:
        row = self._selected()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select an operation to delete first.")
            return
        confirm = QMessageBox.question(self, "Confirm Delete", "Delete this operation?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with self._context.session_factory() as session:
            operation = session.get(ProductionOperation, row.id)
            if operation:
                session.delete(operation)
                session.commit()
        self.refresh()

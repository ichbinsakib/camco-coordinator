"""Modal list of one shipment's lines, with Add/Delete.

Adding a line updates the underlying customer order line's status to SHIPPED
once its full ordered quantity has gone out - shipping is the one place that
transition happens automatically, since it's the fact the transition means.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)
from sqlalchemy import func, select

from app.config.constants import OrderStatus
from app.models.orders import CustomerOrderLine
from app.models.shipping import Shipment, ShipmentLine
from app.ui.app_context import AppContext
from app.ui.widgets.table_model import ColumnSpec, ListTableModel

_COLUMNS = [
    ColumnSpec("CO", lambda line: line.customer_order_line.customer_order.co_number),
    ColumnSpec("Part", lambda line: line.customer_order_line.part.part_number),
    ColumnSpec("Quantity Shipped", lambda line: line.quantity_shipped, align_right=True),
]


class _AddShipmentLineDialog(QDialog):
    def __init__(self, eligible_lines: list[CustomerOrderLine], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Shipment Line")
        self.setMinimumWidth(400)
        self._lines = eligible_lines

        form = QFormLayout(self)
        self.co_line = QComboBox()
        for line in eligible_lines:
            label = f"{line.customer_order.co_number} / {line.part.part_number} (qty {line.quantity_remaining:.0f})"
            self.co_line.addItem(label, line.id)
        self.co_line.currentIndexChanged.connect(self._suggest_quantity)

        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 1_000_000)

        form.addRow("Customer Order Line *", self.co_line)
        form.addRow("Quantity Shipped *", self.quantity)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if eligible_lines:
            self._suggest_quantity(0)

    def _suggest_quantity(self, index: int) -> None:
        if 0 <= index < len(self._lines):
            self.quantity.setValue(self._lines[index].quantity_remaining)

    @property
    def selected_line_id(self) -> int | None:
        return self.co_line.currentData()


class ManageShipmentLinesDialog(QDialog):
    """Add and remove lines on one shipment."""

    def __init__(self, context: AppContext, shipment_id: int, parent=None) -> None:
        super().__init__(parent)
        self._context = context
        self._shipment_id = shipment_id
        self.setWindowTitle("Manage Shipment Lines")
        self.setMinimumSize(560, 380)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Line")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_line)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_line)
        toolbar.addWidget(add_btn)
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
        """Reload lines for this shipment from the database."""
        with self._context.session_factory() as session:
            shipment = session.get(Shipment, self._shipment_id)
            lines = list(shipment.lines) if shipment else []
            for line in lines:
                _ = line.customer_order_line.customer_order.co_number
                _ = line.customer_order_line.part.part_number
            session.expunge_all()
        self._model.set_rows(lines)

    def _selected(self) -> ShipmentLine | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_object(indexes[0].row())

    def _add_line(self) -> None:
        with self._context.session_factory() as session:
            closed_or_shipped = {OrderStatus.CANCELLED.value, OrderStatus.SHIPPED.value, OrderStatus.COMPLETE.value}
            candidates = list(
                session.scalars(
                    select(CustomerOrderLine).where(CustomerOrderLine.status.notin_(closed_or_shipped))
                )
            )
            eligible = [line for line in candidates if line.quantity_remaining > 0]
            if not eligible:
                QMessageBox.information(self, "No Eligible Lines", "No open lines have remaining quantity to ship.")
                return
            for line in eligible:
                _ = line.customer_order.co_number
                _ = line.part.part_number

            dialog = _AddShipmentLineDialog(eligible, parent=self)
            if dialog.exec() != _AddShipmentLineDialog.DialogCode.Accepted:
                return

            co_line = session.get(CustomerOrderLine, dialog.selected_line_id)
            shipment_line = ShipmentLine(
                shipment_id=self._shipment_id,
                customer_order_line_id=dialog.selected_line_id,
                quantity_shipped=dialog.quantity.value(),
            )
            session.add(shipment_line)
            session.flush()

            total_shipped = (
                session.scalar(
                    select(func.coalesce(func.sum(ShipmentLine.quantity_shipped), 0)).where(
                        ShipmentLine.customer_order_line_id == dialog.selected_line_id
                    )
                )
                or 0
            )
            if co_line and total_shipped >= co_line.quantity_ordered:
                co_line.status = OrderStatus.SHIPPED.value
            session.commit()
        self.refresh()

    def _delete_line(self) -> None:
        row = self._selected()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select a line to delete first.")
            return
        with self._context.session_factory() as session:
            line = session.get(ShipmentLine, row.id)
            if line:
                session.delete(line)
                session.commit()
        self.refresh()

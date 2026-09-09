"""A generic, read-only table model driven by column specs.

Every list page (Customers, Vendors, Parts, Customer Order lines, ...) needs
the same thing: turn a list of Python objects into a Qt table using a handful
of "column -> value" extractors. Writing that once here means no list page
hand-rolls its own ``QAbstractTableModel`` subclass (rule 36: DRY).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


@dataclass(slots=True)
class ColumnSpec:
    """One column: a header, a value getter, and optional display/color hooks."""

    header: str
    getter: Callable[[Any], Any]
    color: Callable[[Any], str | None] | None = None
    align_right: bool = False


class ListTableModel(QAbstractTableModel):
    """Read-only model over a list of arbitrary row objects and :class:`ColumnSpec` columns."""

    def __init__(self, columns: list[ColumnSpec], rows: list[Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._rows: list[Any] = rows or []

    def set_rows(self, rows: list[Any]) -> None:
        """Replace all rows and refresh the view."""
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_object(self, row_index: int) -> Any:
        """Return the underlying Python object backing a given row."""
        return self._rows[row_index]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return self._columns[section].header

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column = self._columns[index.column()]
        row_obj = self._rows[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            value = column.getter(row_obj)
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and column.align_right:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and column.color:
            hex_color = column.color(row_obj)
            if hex_color:
                return QColor(hex_color)
        return None

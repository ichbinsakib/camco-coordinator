"""Shared scaffold for a searchable, paginated, sortable list page.

Every master-data page (Customers, Vendors, Parts, ...) and the Customer
Order line list is: a title, a toolbar (search box + New/Edit/Delete + any
entity-specific filters), a table, and pagination. Building that scaffold
once here keeps every concrete page down to "what are the columns and how do
I load a page of rows" (rule 36: DRY, and rule 30: don't load everything).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets.table_model import ColumnSpec, ListTableModel

#: (rows, total_count) for the current search text/filters/page.
LoaderFn = Callable[[str, int, int], tuple[list, int]]


class ListPageBase(QWidget):
    """Reusable search + table + pagination + CRUD-button scaffold.

    Subclasses/callers supply the columns, a ``loader`` callback, and
    optional callbacks for New/Edit/Delete/row-activated. Any entity-specific
    filter widgets can be inserted via :meth:`filter_bar_layout`.
    """

    def __init__(
        self,
        title: str,
        subtitle: str,
        columns: list[ColumnSpec],
        loader: LoaderFn,
        *,
        page_size: int = 100,
        can_edit: bool = True,
        show_notes: bool = False,
        show_import: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._loader = loader
        self._page_size = page_size
        self._page = 0
        self._total = 0
        self._can_edit = can_edit

        self.on_new: Callable[[], None] | None = None
        self.on_edit: Callable[[object], None] | None = None
        self.on_delete: Callable[[object], None] | None = None
        self.on_activated: Callable[[object], None] | None = None
        self.on_notes: Callable[[object], None] | None = None
        self.on_import: Callable[[], None] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        sub = QLabel(subtitle)
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.returnPressed.connect(self.refresh)
        toolbar.addWidget(self._search, stretch=1)

        self._extra_filter_layout = QHBoxLayout()
        toolbar.addLayout(self._extra_filter_layout)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.refresh)
        toolbar.addWidget(search_btn)

        if can_edit:
            new_btn = QPushButton("New")
            new_btn.setObjectName("PrimaryButton")
            new_btn.clicked.connect(self._handle_new)
            toolbar.addWidget(new_btn)

            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(self._handle_edit)
            toolbar.addWidget(edit_btn)

            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(self._handle_delete)
            toolbar.addWidget(delete_btn)

        if show_notes:
            notes_btn = QPushButton("Notes")
            notes_btn.clicked.connect(self._handle_notes)
            toolbar.addWidget(notes_btn)

        if show_import and can_edit:
            import_btn = QPushButton("Import…")
            import_btn.clicked.connect(self._handle_import)
            toolbar.addWidget(import_btn)

        root.addLayout(toolbar)

        self._model = ListTableModel(columns)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._handle_activated)
        root.addWidget(self._table, stretch=1)

        pagination = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Previous")
        self._prev_btn.clicked.connect(self._go_previous)
        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(self._go_next)
        self._page_label = QLabel("")
        pagination.addWidget(self._prev_btn)
        pagination.addWidget(self._page_label, alignment=Qt.AlignmentFlag.AlignCenter, stretch=1)
        pagination.addWidget(self._next_btn)
        root.addLayout(pagination)

    # -- public API for subclasses ---------------------------------------

    def filter_bar_layout(self) -> QHBoxLayout:
        """Layout entity-specific filter widgets should be added to."""
        return self._extra_filter_layout

    @property
    def search_text(self) -> str:
        return self._search.text()

    def selected_row(self) -> object | None:
        """Return the currently selected row's backing object, or ``None``."""
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_object(indexes[0].row())

    def refresh(self) -> None:
        """Reload the current page from the loader."""
        offset = self._page * self._page_size
        rows, total = self._loader(self._search.text(), self._page_size, offset)
        self._total = total
        self._model.set_rows(rows)
        self._update_pagination_label()

    # -- internal ---------------------------------------------------------

    def _update_pagination_label(self) -> None:
        if self._total == 0:
            self._page_label.setText("No results")
        else:
            start = self._page * self._page_size + 1
            end = min(start + self._page_size - 1, self._total)
            self._page_label.setText(f"{start}-{end} of {self._total}")
        self._prev_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled((self._page + 1) * self._page_size < self._total)

    def _go_previous(self) -> None:
        if self._page > 0:
            self._page -= 1
            self.refresh()

    def _go_next(self) -> None:
        if (self._page + 1) * self._page_size < self._total:
            self._page += 1
            self.refresh()

    def _handle_new(self) -> None:
        if self.on_new:
            self.on_new()

    def _handle_edit(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select a row to edit first.")
            return
        if self.on_edit:
            self.on_edit(row)

    def _handle_delete(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select a row to delete first.")
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete", "Delete the selected record? This cannot be undone."
        )
        if confirm == QMessageBox.StandardButton.Yes and self.on_delete:
            self.on_delete(row)

    def _handle_activated(self) -> None:
        row = self.selected_row()
        if row is not None and self.on_activated:
            self.on_activated(row)

    def _handle_notes(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select a row to view notes first.")
            return
        if self.on_notes:
            self.on_notes(row)

    def _handle_import(self) -> None:
        if self.on_import:
            self.on_import()

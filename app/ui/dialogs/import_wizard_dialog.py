"""Import wizard: file -> sheet -> column mapping -> preview -> confirm -> commit.

One dialog covers every target in :data:`app.imports.fields.IMPORT_TARGETS`
(spec section 44's full flow), reachable from Settings or from a specific
page pre-selecting its own target so a coordinator importing customer order
lines doesn't have to hunt through an entity picker first.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.imports.engine import auto_map_columns, build_preview, commit_import
from app.imports.fields import IMPORT_TARGETS, ImportTarget
from app.imports.readers import SUPPORTED_SUFFIXES, list_sheet_names, read_sheet
from app.ui.app_context import AppContext

log = logging.getLogger(__name__)

_INVALID_ROW_COLOR = QColor("#FDEAEA")


class ImportWizardDialog(QDialog):
    """Guides a coordinator through importing an Excel/CSV file into one target entity."""

    def __init__(self, context: AppContext, *, default_target_key: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._context = context
        self._file_path: Path | None = None
        self._sheet_data = None
        self._preview = None
        self._mapping_combos: dict[str, QComboBox] = {}

        self.setWindowTitle("Import Data")
        self.setMinimumSize(760, 560)
        root = QVBoxLayout(self)

        file_row = QHBoxLayout()
        self._file_label = QLabel("No file selected.")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self._file_label, stretch=1)
        file_row.addWidget(browse_btn)
        root.addLayout(file_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Import into:"))
        self._target_combo = QComboBox()
        for target in IMPORT_TARGETS.values():
            self._target_combo.addItem(target.label, target.key)
        if default_target_key:
            index = self._target_combo.findData(default_target_key)
            if index >= 0:
                self._target_combo.setCurrentIndex(index)
        self._target_combo.currentIndexChanged.connect(self._rebuild_mapping)
        target_row.addWidget(self._target_combo)

        target_row.addWidget(QLabel("Sheet:"))
        self._sheet_combo = QComboBox()
        self._sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        target_row.addWidget(self._sheet_combo)
        root.addLayout(target_row)

        self._mapping_group = QGroupBox("Column Mapping")
        self._mapping_layout = QVBoxLayout(self._mapping_group)
        root.addWidget(self._mapping_group)

        validate_btn = QPushButton("Validate / Preview")
        validate_btn.clicked.connect(self._validate)
        root.addWidget(validate_btn)

        self._preview_table = QTableWidget()
        root.addWidget(self._preview_table, stretch=1)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._commit_btn = buttons.addButton("Commit Import", QDialogButtonBox.ButtonRole.AcceptRole)
        self._commit_btn.setObjectName("PrimaryButton")
        self._commit_btn.setEnabled(False)
        self._commit_btn.clicked.connect(self._commit)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._rebuild_mapping()

    # -- selection ----------------------------------------------------------

    def _current_target(self) -> ImportTarget:
        return IMPORT_TARGETS[self._target_combo.currentData()]

    def _browse_file(self) -> None:
        suffix_filter = " ".join(f"*{s}" for s in sorted(SUPPORTED_SUFFIXES))
        file_name, _filter = QFileDialog.getOpenFileName(
            self, "Select File to Import", "", f"Supported Files ({suffix_filter})"
        )
        if not file_name:
            return
        self._file_path = Path(file_name)
        self._file_label.setText(str(self._file_path))
        try:
            sheets = list_sheet_names(self._file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Read File", str(exc))
            return
        self._sheet_combo.clear()
        self._sheet_combo.addItems(sheets)
        self._sheet_data = None
        self._commit_btn.setEnabled(False)

    def _on_sheet_changed(self) -> None:
        self._preview = None
        self._commit_btn.setEnabled(False)
        self._preview_table.clear()
        self._preview_table.setRowCount(0)
        self._status_label.setText("")

        if self._file_path is None or self._sheet_combo.currentText() == "":
            self._sheet_data = None
            self._rebuild_mapping()
            return
        try:
            self._sheet_data = read_sheet(self._file_path, self._sheet_combo.currentText())
        except Exception as exc:
            self._sheet_data = None
            QMessageBox.critical(self, "Could Not Read Sheet", str(exc))
        # Headers are only known now - rebuild the mapping combos so the
        # coordinator sees (and can adjust) the auto-mapping before validating.
        self._rebuild_mapping()

    def _rebuild_mapping(self) -> None:
        while self._mapping_layout.count():
            item = self._mapping_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._mapping_combos.clear()

        target = self._current_target()
        headers = self._sheet_data.headers if self._sheet_data else []

        for target_field in target.fields:
            row = QHBoxLayout()
            label_text = target_field.label + (" *" if target_field.required else "")
            row.addWidget(QLabel(label_text), stretch=1)
            combo = QComboBox()
            combo.addItem("(not mapped)", "")
            for header in headers:
                combo.addItem(header, header)
            if headers:
                mapping = auto_map_columns(headers, target)
                default = mapping.get(target_field.key, "")
                index = combo.findData(default)
                if index >= 0:
                    combo.setCurrentIndex(index)
            self._mapping_combos[target_field.key] = combo
            row.addWidget(combo, stretch=1)
            self._mapping_layout.addLayout(row)

    def _current_mapping(self) -> dict[str, str]:
        return {key: combo.currentData() for key, combo in self._mapping_combos.items()}

    # -- validate / preview ---------------------------------------------------

    def _validate(self) -> None:
        if self._sheet_data is None:
            QMessageBox.information(self, "No File", "Select a file and sheet first.")
            return
        target = self._current_target()
        mapping = self._current_mapping()
        self._preview = build_preview(self._sheet_data, target, mapping)
        self._render_preview(target)

    def _render_preview(self, target: ImportTarget) -> None:
        preview = self._preview
        headers = [f.label for f in target.fields] + ["Issues"]
        self._preview_table.setColumnCount(len(headers))
        self._preview_table.setHorizontalHeaderLabels(headers)
        self._preview_table.setRowCount(len(preview.rows))

        for row_index, row in enumerate(preview.rows):
            for col_index, target_field in enumerate(target.fields):
                value = row.values.get(target_field.key)
                item = QTableWidgetItem("" if value is None else str(value))
                if not row.is_valid:
                    item.setBackground(_INVALID_ROW_COLOR)
                self._preview_table.setItem(row_index, col_index, item)
            issues_text = "; ".join(f"Row {i.row_number}: {i.column} - {i.message}" for i in row.issues)
            issue_item = QTableWidgetItem(issues_text)
            if not row.is_valid:
                issue_item.setBackground(_INVALID_ROW_COLOR)
            self._preview_table.setItem(row_index, len(target.fields), issue_item)

        self._preview_table.resizeColumnsToContents()
        valid_count = len(preview.valid_rows)
        invalid_count = len(preview.invalid_rows)
        self._status_label.setText(
            f"{len(preview.rows)} row(s) parsed: {valid_count} ready to import, {invalid_count} with errors."
        )
        self._commit_btn.setEnabled(valid_count > 0)

    # -- commit ---------------------------------------------------------------

    def _commit(self) -> None:
        if self._preview is None or self._file_path is None:
            return
        target = self._current_target()
        mapping = self._current_mapping()

        confirm = QMessageBox.question(
            self,
            "Confirm Import",
            f"Import {len(self._preview.valid_rows)} row(s) into {target.label}? "
            f"{len(self._preview.invalid_rows)} row(s) with errors will be skipped and logged.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with self._context.session_factory() as session:
                result = commit_import(
                    session,
                    target,
                    mapping,
                    self._preview,
                    source_file=str(self._file_path),
                    sheet_name=self._sheet_combo.currentText(),
                    imported_by_id=self._context.current_user.id,
                )
        except Exception:
            log.exception("Import commit failed")
            QMessageBox.critical(self, "Import Failed", "Could not commit the import. See the logs for details.")
            return

        QMessageBox.information(
            self,
            "Import Complete",
            f"{result.inserted} new record(s), {result.updated} updated, {result.errors} skipped with errors.",
        )
        self.accept()

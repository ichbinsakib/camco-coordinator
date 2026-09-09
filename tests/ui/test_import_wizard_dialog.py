"""pytest-qt regression tests for the Import Wizard dialog.

These exercise real Qt signal/slot wiring (sheet selection actually
populating the column-mapping combos) rather than just the pure
:mod:`app.imports.engine` functions - the class of bug this dialog actually
had (mapping combos built once with no headers, then never rebuilt after a
sheet was read) only shows up when the widgets are driven end-to-end.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.config.constants import UserRole
from app.config.settings import get_settings
from app.database.session import get_session_factory
from app.models.core import Customer
from app.security.auth import AuthService
from app.ui.app_context import AppContext
from app.ui.dialogs.import_wizard_dialog import ImportWizardDialog


@pytest.fixture
def app_context(db_session: Session) -> AppContext:
    # A real User row (not just an AuthenticatedUser value object) - the
    # import batch's imported_by_id is a real foreign key, and it should be
    # exercised the same way a logged-in session would populate it.
    AuthService(db_session).create_user("admin", "Administrator", "correct-password-1", UserRole.ADMIN)
    db_session.add(Customer(code="ACME", name="Acme Corp", importance=1))
    db_session.commit()
    authenticated = AuthService(db_session).login("admin", "correct-password-1")
    return AppContext(settings=get_settings(), session_factory=get_session_factory(), current_user=authenticated)


@pytest.fixture
def sample_workbook(tmp_path: Path) -> Path:
    path = tmp_path / "schedule.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["CO Number", "Customer Code", "Part Number", "Quantity Ordered", "Due Date", "Status"])
    ws.append(["CO-5001", "ACME", "BRK-100", 50, "12/25/2026", "IN PROGRESS"])
    ws.append(["CO-5001", "ACME", "BRK-200", 30, "12/25/2026", "IN PROGRESS"])
    ws.append(["CO-5002", "ACME", "BRK-100", 10, "bad-date", "IN PROGRESS"])
    wb.save(path)
    return path


def _load_file_into_dialog(dialog: ImportWizardDialog, path: Path, qtbot) -> None:
    """Drive the same path _browse_file takes, without the native file picker."""
    from app.imports.readers import list_sheet_names

    dialog._file_path = path
    dialog._file_label.setText(str(path))
    with qtbot.waitSignal(dialog._sheet_combo.currentIndexChanged, timeout=1000):
        dialog._sheet_combo.addItems(list_sheet_names(path))


def test_selecting_a_sheet_populates_mapping_combos(qtbot, app_context: AppContext, sample_workbook: Path) -> None:
    dialog = ImportWizardDialog(app_context, default_target_key="customer_order_lines")
    qtbot.addWidget(dialog)
    _load_file_into_dialog(dialog, sample_workbook, qtbot)

    mapping = dialog._current_mapping()
    assert mapping["co_number"] == "CO Number"
    assert mapping["customer_code"] == "Customer Code"
    assert mapping["part_number"] == "Part Number"
    assert mapping["due_date"] == "Due Date"


def test_validate_after_sheet_selection_parses_valid_rows(qtbot, app_context: AppContext, sample_workbook: Path) -> None:
    dialog = ImportWizardDialog(app_context, default_target_key="customer_order_lines")
    qtbot.addWidget(dialog)
    _load_file_into_dialog(dialog, sample_workbook, qtbot)

    dialog._validate()

    assert dialog._preview is not None
    assert len(dialog._preview.valid_rows) == 2
    assert len(dialog._preview.invalid_rows) == 1
    assert dialog._commit_btn.isEnabled()


def test_commit_writes_rows_and_refreshes_afterward(
    qtbot, app_context: AppContext, sample_workbook: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dialog = ImportWizardDialog(app_context, default_target_key="customer_order_lines")
    qtbot.addWidget(dialog)
    _load_file_into_dialog(dialog, sample_workbook, qtbot)
    dialog._validate()
    dialog._commit()

    from sqlalchemy import select

    from app.models.orders import CustomerOrderLine

    with app_context.session_factory() as session:
        lines = list(session.scalars(select(CustomerOrderLine)))
        assert len(lines) == 2


def test_changing_target_without_a_file_does_not_crash(
    qtbot, app_context: AppContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards against the mapping rebuild assuming a file/sheet is always loaded."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dialog = ImportWizardDialog(app_context)
    qtbot.addWidget(dialog)
    dialog._target_combo.setCurrentIndex(dialog._target_combo.count() - 1)
    dialog._validate()  # should show "select a file" rather than raise
    assert dialog._preview is None

"""Integration tests for app.imports.engine: preview, validation and commit."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports.engine import auto_map_columns, build_preview, commit_import
from app.imports.fields import CUSTOMER_ORDER_LINES_TARGET, CUSTOMERS_TARGET, PARTS_TARGET
from app.imports.readers import SheetData
from app.models.core import Customer, Part
from app.models.imports import ImportBatch, ImportRowError
from app.models.orders import CustomerOrder, CustomerOrderLine


def test_auto_map_columns_matches_by_label_and_alias() -> None:
    headers = ["Customer Code", "Name", "Contact Name"]
    mapping = auto_map_columns(headers, CUSTOMERS_TARGET)
    assert mapping["code"] == "Customer Code"
    assert mapping["name"] == "Name"
    assert mapping["contact_name"] == "Contact Name"
    assert mapping["contact_email"] == ""  # unmapped, no matching header


def test_build_preview_flags_missing_required_field() -> None:
    sheet = SheetData(headers=["Customer Code", "Name"], rows=[{"Customer Code": "ACME", "Name": ""}])
    mapping = auto_map_columns(sheet.headers, CUSTOMERS_TARGET)
    preview = build_preview(sheet, CUSTOMERS_TARGET, mapping)
    assert len(preview.invalid_rows) == 1
    assert "required" in preview.invalid_rows[0].issues[0].message.lower()


def test_build_preview_flags_invalid_date_with_readable_message() -> None:
    sheet = SheetData(
        headers=["CO Number", "Customer Code", "Part Number", "Quantity Ordered", "Due Date"],
        rows=[{"CO Number": "CO-1", "Customer Code": "ACME", "Part Number": "P1", "Quantity Ordered": "10", "Due Date": "not-a-date"}],
    )
    mapping = auto_map_columns(sheet.headers, CUSTOMER_ORDER_LINES_TARGET)
    preview = build_preview(sheet, CUSTOMER_ORDER_LINES_TARGET, mapping)
    row = preview.rows[0]
    assert not row.is_valid
    messages = [issue.message for issue in row.issues]
    assert any("not a valid date" in m for m in messages)
    # Row number matches what a coordinator sees in Excel (header=1, first data row=2).
    assert row.row_number == 2


def test_build_preview_flags_duplicate_natural_key() -> None:
    sheet = SheetData(
        headers=["Part Number", "Revision"],
        rows=[{"Part Number": "P1", "Revision": "A"}, {"Part Number": "P1", "Revision": "A"}],
    )
    mapping = auto_map_columns(sheet.headers, PARTS_TARGET)
    preview = build_preview(sheet, PARTS_TARGET, mapping)
    assert preview.rows[0].is_valid
    assert not preview.rows[1].is_valid
    assert "duplicate" in preview.rows[1].issues[0].message.lower()


def test_commit_customers_inserts_new_and_updates_existing(db_session: Session) -> None:
    existing = Customer(code="ACME", name="Old Name")
    db_session.add(existing)
    db_session.commit()

    sheet = SheetData(
        headers=["Customer Code", "Name"],
        rows=[{"Customer Code": "ACME", "Name": "Acme Updated"}, {"Customer Code": "ZETA", "Name": "Zeta Corp"}],
    )
    mapping = auto_map_columns(sheet.headers, CUSTOMERS_TARGET)
    preview = build_preview(sheet, CUSTOMERS_TARGET, mapping)

    result = commit_import(
        db_session, CUSTOMERS_TARGET, mapping, preview,
        source_file="test.csv", sheet_name="test", imported_by_id=None,
    )
    assert result.inserted == 1
    assert result.updated == 1
    assert result.errors == 0

    updated = db_session.scalar(select(Customer).where(Customer.code == "ACME"))
    assert updated.name == "Acme Updated"
    new = db_session.scalar(select(Customer).where(Customer.code == "ZETA"))
    assert new is not None


def test_commit_logs_import_batch_and_row_errors(db_session: Session) -> None:
    sheet = SheetData(headers=["Customer Code", "Name"], rows=[{"Customer Code": "", "Name": "Missing Code"}])
    mapping = auto_map_columns(sheet.headers, CUSTOMERS_TARGET)
    preview = build_preview(sheet, CUSTOMERS_TARGET, mapping)

    result = commit_import(
        db_session, CUSTOMERS_TARGET, mapping, preview,
        source_file="test.csv", sheet_name="test", imported_by_id=None,
    )
    assert result.errors == 1
    assert result.inserted == 0

    batch = db_session.get(ImportBatch, result.batch_id)
    assert batch is not None
    assert batch.error_count == 1
    errors = list(db_session.scalars(select(ImportRowError).where(ImportRowError.batch_id == batch.id)))
    assert len(errors) == 1
    assert "required" in errors[0].message.lower()


def test_commit_customer_order_line_creates_co_header_and_part(db_session: Session) -> None:
    customer = Customer(code="ACME", name="Acme Corp")
    db_session.add(customer)
    db_session.commit()

    sheet = SheetData(
        headers=["CO Number", "Customer Code", "Part Number", "Quantity Ordered", "Due Date"],
        rows=[{"CO Number": "CO-9001", "Customer Code": "ACME", "Part Number": "NEWPART", "Quantity Ordered": "25", "Due Date": "12/31/2026"}],
    )
    mapping = auto_map_columns(sheet.headers, CUSTOMER_ORDER_LINES_TARGET)
    preview = build_preview(sheet, CUSTOMER_ORDER_LINES_TARGET, mapping)
    assert preview.rows[0].is_valid

    result = commit_import(
        db_session, CUSTOMER_ORDER_LINES_TARGET, mapping, preview,
        source_file="master_schedule.xlsx", sheet_name="Sheet1", imported_by_id=None,
    )
    assert result.inserted == 1

    order = db_session.scalar(select(CustomerOrder).where(CustomerOrder.co_number == "CO-9001"))
    assert order is not None
    part = db_session.scalar(select(Part).where(Part.part_number == "NEWPART"))
    assert part is not None
    line = db_session.scalar(select(CustomerOrderLine).where(CustomerOrderLine.customer_order_id == order.id))
    assert line.quantity_ordered == 25


def test_commit_customer_order_line_rejects_unknown_customer(db_session: Session) -> None:
    sheet = SheetData(
        headers=["CO Number", "Customer Code", "Part Number", "Quantity Ordered", "Due Date"],
        rows=[{"CO Number": "CO-1", "Customer Code": "NOPE", "Part Number": "P1", "Quantity Ordered": "5", "Due Date": "01/01/2027"}],
    )
    mapping = auto_map_columns(sheet.headers, CUSTOMER_ORDER_LINES_TARGET)
    preview = build_preview(sheet, CUSTOMER_ORDER_LINES_TARGET, mapping)
    assert preview.rows[0].is_valid  # passes field validation; the FK check happens at commit

    result = commit_import(
        db_session, CUSTOMER_ORDER_LINES_TARGET, mapping, preview,
        source_file="test.xlsx", sheet_name="Sheet1", imported_by_id=None,
    )
    assert result.errors == 1
    assert result.inserted == 0

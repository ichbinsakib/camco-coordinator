"""Column mapping, validation and commit for the import wizard.

Every commit is wrapped in one :class:`app.models.imports.ImportBatch` (spec
rule 44 step 10: "log import") with a row-level error recorded for anything
that couldn't be loaded (spec rule 24: never a bare Python exception message,
always something like "Row 143: Due Date is invalid").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.constants import ImportStatus
from app.imports.fields import FieldType, ImportField, ImportTarget
from app.imports.readers import SheetData, coerce_date, coerce_float
from app.models.core import Customer, Part, Vendor
from app.models.imports import ImportBatch, ImportRowError
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.services.activity_log_service import log_event

ColumnMapping = dict[str, str]  # target field key -> source header (or "" if unmapped)


def auto_map_columns(headers: list[str], target: ImportTarget) -> ColumnMapping:
    """Best-effort default mapping from source headers to target fields by name."""
    mapping: ColumnMapping = {}
    for f in target.fields:
        match = next((h for h in headers if f.matches_header(h)), "")
        mapping[f.key] = match
    return mapping


@dataclass(slots=True)
class RowIssue:
    """One validation problem on one row, in plain language (never a raw exception)."""

    row_number: int  # 1-based, matching what a coordinator sees in Excel (header = row 1)
    column: str
    message: str


@dataclass(slots=True)
class PreviewRow:
    """One parsed row, ready to commit if it has no issues."""

    row_number: int
    values: dict[str, Any]  # target field key -> parsed value
    issues: list[RowIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


@dataclass(slots=True)
class PreviewResult:
    """The full validated preview: every row, valid or not."""

    rows: list[PreviewRow]

    @property
    def valid_rows(self) -> list[PreviewRow]:
        return [r for r in self.rows if r.is_valid]

    @property
    def invalid_rows(self) -> list[PreviewRow]:
        return [r for r in self.rows if not r.is_valid]


def _parse_field(raw_value: Any, target_field: ImportField, row_number: int, issues: list[RowIssue]) -> Any:
    if raw_value is None or raw_value == "":
        if target_field.required:
            issues.append(RowIssue(row_number, target_field.label, "This field is required."))
        return None

    if target_field.field_type == FieldType.DATE:
        parsed = coerce_date(raw_value)
        if parsed is None:
            issues.append(RowIssue(row_number, target_field.label, f"'{raw_value}' is not a valid date."))
        return parsed

    if target_field.field_type == FieldType.NUMBER:
        parsed = coerce_float(raw_value)
        if parsed is None:
            issues.append(RowIssue(row_number, target_field.label, f"'{raw_value}' is not a valid number."))
        return parsed

    if target_field.field_type == FieldType.ENUM:
        text = str(raw_value).strip()
        canonical = next((v for v in target_field.allowed_values if v.lower() == text.lower()), None)
        if canonical is None:
            allowed = ", ".join(target_field.allowed_values)
            issues.append(RowIssue(row_number, target_field.label, f"'{raw_value}' is not one of: {allowed}."))
        return canonical

    return str(raw_value).strip()


def build_preview(sheet: SheetData, target: ImportTarget, mapping: ColumnMapping) -> PreviewResult:
    """Parse and validate every source row against the target's field definitions."""
    preview_rows: list[PreviewRow] = []
    seen_keys: set[tuple[Any, ...]] = set()

    for offset, raw_row in enumerate(sheet.rows):
        row_number = offset + 2  # header is row 1
        issues: list[RowIssue] = []
        values: dict[str, Any] = {}

        for target_field in target.fields:
            source_header = mapping.get(target_field.key, "")
            raw_value = raw_row.get(source_header) if source_header else None
            values[target_field.key] = _parse_field(raw_value, target_field, row_number, issues)

        key = tuple(values.get(k) for k in target.natural_key)
        if all(k is not None for k in key):
            if key in seen_keys:
                issues.append(RowIssue(row_number, " / ".join(target.natural_key), "Duplicate row within this import file."))
            seen_keys.add(key)

        preview_rows.append(PreviewRow(row_number=row_number, values=values, issues=issues))

    return PreviewResult(rows=preview_rows)


@dataclass(slots=True)
class CommitResult:
    """Outcome of committing a validated preview."""

    batch_id: int
    inserted: int
    updated: int
    errors: int


def commit_import(
    session: Session,
    target: ImportTarget,
    mapping: ColumnMapping,
    preview: PreviewResult,
    *,
    source_file: str,
    sheet_name: str,
    imported_by_id: int | None,
) -> CommitResult:
    """Commit every valid row via the target-specific loader, logging an ImportBatch."""
    loader = _LOADERS[target.key]
    inserted = updated = 0

    batch = ImportBatch(
        source_file=source_file,
        sheet_name=sheet_name,
        target_entity=target.key,
        mapping_json=json.dumps(mapping),
        status=ImportStatus.COMMITTED.value,
        row_count=len(preview.rows),
        imported_by_id=imported_by_id,
    )
    session.add(batch)
    session.flush()

    for row in preview.invalid_rows:
        for issue in row.issues:
            session.add(
                ImportRowError(batch_id=batch.id, row_number=row.row_number, column_name=issue.column, message=issue.message)
            )

    commit_errors = 0
    for row in preview.valid_rows:
        try:
            # A SAVEPOINT per row: a bad row (bad FK, constraint violation) is
            # rolled back on its own without invalidating the whole batch's
            # transaction, so one row's error can't sink every other row.
            with session.begin_nested():
                was_inserted = loader(session, row.values)
        except Exception as exc:
            commit_errors += 1
            session.add(
                ImportRowError(batch_id=batch.id, row_number=row.row_number, column_name=None, message=f"Could not save row: {exc}")
            )
            continue
        if was_inserted:
            inserted += 1
        else:
            updated += 1

    batch.inserted_count = inserted
    batch.updated_count = updated
    batch.error_count = len(preview.invalid_rows) + commit_errors
    log_event(
        session,
        entity_type="IMPORT_BATCH",
        entity_id=batch.id,
        description=f"Imported {target.label}: {inserted} new, {updated} updated, {batch.error_count} skipped",
        user_id=imported_by_id,
    )
    session.commit()
    return CommitResult(batch_id=batch.id, inserted=inserted, updated=updated, errors=batch.error_count)


# -- per-target loaders: each returns True if it inserted a new row, False if it updated one --


def _load_customer(session: Session, values: dict[str, Any]) -> bool:
    customer = session.scalar(select(Customer).where(Customer.code == values["code"]))
    is_new = customer is None
    if customer is None:
        customer = Customer(code=values["code"])
        session.add(customer)
    customer.name = values["name"]
    if values.get("importance") is not None:
        customer.importance = int(values["importance"])
    customer.contact_name = values.get("contact_name") or customer.contact_name
    customer.contact_email = values.get("contact_email") or customer.contact_email
    customer.contact_phone = values.get("contact_phone") or customer.contact_phone
    session.flush()
    return is_new


def _load_vendor(session: Session, values: dict[str, Any]) -> bool:
    vendor = session.scalar(select(Vendor).where(Vendor.code == values["code"]))
    is_new = vendor is None
    if vendor is None:
        vendor = Vendor(code=values["code"])
        session.add(vendor)
    vendor.name = values["name"]
    vendor.contact_name = values.get("contact_name") or vendor.contact_name
    vendor.contact_email = values.get("contact_email") or vendor.contact_email
    vendor.contact_phone = values.get("contact_phone") or vendor.contact_phone
    if values.get("average_lead_time_days") is not None:
        vendor.average_lead_time_days = values["average_lead_time_days"]
    session.flush()
    return is_new


def _load_part(session: Session, values: dict[str, Any]) -> bool:
    revision = values.get("revision") or "-"
    part = session.scalar(
        select(Part).where(Part.part_number == values["part_number"], Part.revision == revision)
    )
    is_new = part is None
    if part is None:
        part = Part(part_number=values["part_number"], revision=revision)
        session.add(part)
    part.description = values.get("description") or part.description
    part.customer_part_number = values.get("customer_part_number") or part.customer_part_number
    part.drawing_number = values.get("drawing_number") or part.drawing_number
    part.material = values.get("material") or part.material
    part.finish = values.get("finish") or part.finish
    if values.get("standard_lead_time_days") is not None:
        part.standard_lead_time_days = int(values["standard_lead_time_days"])

    customer_code = values.get("customer_code")
    if customer_code:
        customer = session.scalar(select(Customer).where(Customer.code == customer_code))
        if customer is None:
            raise ValueError(f"Customer code '{customer_code}' does not exist")
        part.customer_id = customer.id
    session.flush()
    return is_new


def _load_customer_order_line(session: Session, values: dict[str, Any]) -> bool:
    customer = session.scalar(select(Customer).where(Customer.code == values["customer_code"]))
    if customer is None:
        raise ValueError(f"Customer code '{values['customer_code']}' does not exist")

    revision = values.get("revision") or "-"
    part = session.scalar(select(Part).where(Part.part_number == values["part_number"], Part.revision == revision))
    if part is None:
        part = Part(part_number=values["part_number"], revision=revision, customer_id=customer.id)
        session.add(part)
        session.flush()

    order = session.scalar(select(CustomerOrder).where(CustomerOrder.co_number == values["co_number"]))
    if order is None:
        order = CustomerOrder(co_number=values["co_number"], customer_id=customer.id)
        session.add(order)
        session.flush()
    if values.get("customer_po_number"):
        order.customer_po_number = values["customer_po_number"]

    line = session.scalar(
        select(CustomerOrderLine).where(
            CustomerOrderLine.customer_order_id == order.id, CustomerOrderLine.part_id == part.id
        )
    )
    is_new = line is None
    if line is None:
        next_line_number = session.scalar(
            select(CustomerOrderLine.line_number)
            .where(CustomerOrderLine.customer_order_id == order.id)
            .order_by(CustomerOrderLine.line_number.desc())
        )
        line = CustomerOrderLine(
            customer_order_id=order.id, part_id=part.id, line_number=(next_line_number or 0) + 1
        )
        session.add(line)

    line.quantity_ordered = values["quantity_ordered"]
    if values.get("quantity_completed") is not None:
        line.quantity_completed = values["quantity_completed"]
    line.due_date = values["due_date"]
    if line.original_due_date is None:
        line.original_due_date = values["due_date"]
    if values.get("status"):
        line.status = values["status"]
    session.flush()
    return is_new


def _load_purchase_order_line(session: Session, values: dict[str, Any]) -> bool:
    vendor = session.scalar(select(Vendor).where(Vendor.code == values["vendor_code"]))
    if vendor is None:
        raise ValueError(f"Vendor code '{values['vendor_code']}' does not exist")

    order = session.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == values["po_number"]))
    if order is None:
        order = PurchaseOrder(po_number=values["po_number"], vendor_id=vendor.id)
        session.add(order)
        session.flush()
    if values.get("buyer"):
        order.buyer = values["buyer"]

    part = None
    if values.get("part_number"):
        part = session.scalar(select(Part).where(Part.part_number == values["part_number"]))

    query = select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
    if part is not None:
        query = query.where(PurchaseOrderLine.part_id == part.id)
    else:
        query = query.where(PurchaseOrderLine.description == values.get("description"))
    line = session.scalar(query)

    is_new = line is None
    if line is None:
        next_line_number = session.scalar(
            select(PurchaseOrderLine.line_number)
            .where(PurchaseOrderLine.purchase_order_id == order.id)
            .order_by(PurchaseOrderLine.line_number.desc())
        )
        line = PurchaseOrderLine(
            purchase_order_id=order.id, part_id=part.id if part else None, line_number=(next_line_number or 0) + 1
        )
        session.add(line)

    line.description = values.get("description") or line.description
    line.quantity_ordered = values["quantity_ordered"]
    line.required_date = values.get("required_date") or line.required_date
    line.promised_date = values.get("promised_date") or line.promised_date
    if values.get("status"):
        line.status = values["status"]
    session.flush()
    return is_new


_LOADERS = {
    "customers": _load_customer,
    "vendors": _load_vendor,
    "parts": _load_part,
    "customer_order_lines": _load_customer_order_line,
    "purchase_order_lines": _load_purchase_order_line,
}

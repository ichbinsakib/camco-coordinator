"""Field definitions for each importable target entity.

One :class:`ImportTarget` per entity the import wizard supports; each field
carries its own validation type so :mod:`app.imports.engine` never special-
cases a particular column by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.config.constants import OrderStatus, PurchaseOrderStatus


class FieldType(StrEnum):
    """How a column's raw cell values should be parsed/validated."""

    TEXT = "TEXT"
    NUMBER = "NUMBER"
    DATE = "DATE"
    ENUM = "ENUM"


@dataclass(slots=True, frozen=True)
class ImportField:
    """One target field: its key, display label, type, and whether it's required."""

    key: str
    label: str
    field_type: FieldType = FieldType.TEXT
    required: bool = False
    allowed_values: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def matches_header(self, header: str) -> bool:
        """True if a source column header looks like it maps to this field."""
        normalized = header.strip().lower().replace("_", " ").replace("-", " ")
        candidates = {self.label.lower(), self.key.replace("_", " ").lower(), *[a.lower() for a in self.aliases]}
        return normalized in candidates


@dataclass(slots=True, frozen=True)
class ImportTarget:
    """A destination entity the import wizard can load rows into."""

    key: str
    label: str
    fields: tuple[ImportField, ...]
    natural_key: tuple[str, ...]
    description: str = ""

    def field(self, key: str) -> ImportField | None:
        return next((f for f in self.fields if f.key == key), None)


CUSTOMERS_TARGET = ImportTarget(
    key="customers",
    label="Customers",
    description="Customer master records.",
    natural_key=("code",),
    fields=(
        ImportField("code", "Customer Code", required=True, aliases=("customer code", "cust code")),
        ImportField("name", "Customer Name", required=True, aliases=("name", "customer")),
        ImportField("importance", "Importance (1-5)", FieldType.NUMBER),
        ImportField("contact_name", "Contact Name"),
        ImportField("contact_email", "Contact Email"),
        ImportField("contact_phone", "Contact Phone"),
    ),
)

VENDORS_TARGET = ImportTarget(
    key="vendors",
    label="Vendors",
    description="Vendor master records.",
    natural_key=("code",),
    fields=(
        ImportField("code", "Vendor Code", required=True, aliases=("vendor code",)),
        ImportField("name", "Vendor Name", required=True, aliases=("name", "vendor")),
        ImportField("contact_name", "Contact Name"),
        ImportField("contact_email", "Contact Email"),
        ImportField("contact_phone", "Contact Phone"),
        ImportField("average_lead_time_days", "Average Lead Time (days)", FieldType.NUMBER),
    ),
)

PARTS_TARGET = ImportTarget(
    key="parts",
    label="Parts",
    description="Centralized part-number records.",
    natural_key=("part_number", "revision"),
    fields=(
        ImportField("part_number", "Part Number", required=True, aliases=("pn", "part no", "part #")),
        ImportField("revision", "Revision", aliases=("rev",)),
        ImportField("description", "Description"),
        ImportField("customer_code", "Customer Code", aliases=("customer",)),
        ImportField("customer_part_number", "Customer Part Number", aliases=("customer pn",)),
        ImportField("drawing_number", "Drawing Number", aliases=("drawing",)),
        ImportField("material", "Material"),
        ImportField("finish", "Finish"),
        ImportField("standard_lead_time_days", "Standard Lead Time (days)", FieldType.NUMBER),
    ),
)

CUSTOMER_ORDER_LINES_TARGET = ImportTarget(
    key="customer_order_lines",
    label="Customer Order Lines (Master Schedule)",
    description="CO lines - creates the CO header and Part if they don't already exist.",
    natural_key=("co_number", "part_number"),
    fields=(
        ImportField("co_number", "CO Number", required=True, aliases=("customer order", "co")),
        ImportField("customer_code", "Customer Code", required=True, aliases=("customer",)),
        ImportField("customer_po_number", "Customer PO Number", aliases=("customer po",)),
        ImportField("part_number", "Part Number", required=True, aliases=("pn", "part")),
        ImportField("revision", "Revision", aliases=("rev",)),
        ImportField("quantity_ordered", "Quantity Ordered", FieldType.NUMBER, required=True, aliases=("qty ordered", "quantity")),
        ImportField("quantity_completed", "Quantity Completed", FieldType.NUMBER, aliases=("qty completed",)),
        ImportField("due_date", "Due Date", FieldType.DATE, required=True, aliases=("due",)),
        ImportField(
            "status", "Status", FieldType.ENUM, allowed_values=tuple(s.value for s in OrderStatus),
        ),
    ),
)

PURCHASE_ORDER_LINES_TARGET = ImportTarget(
    key="purchase_order_lines",
    label="Purchase Order Lines",
    description="PO lines - creates the PO header if it doesn't already exist.",
    natural_key=("po_number", "part_number"),
    fields=(
        ImportField("po_number", "PO Number", required=True, aliases=("purchase order", "po")),
        ImportField("vendor_code", "Vendor Code", required=True, aliases=("vendor",)),
        ImportField("part_number", "Part Number", aliases=("pn", "part")),
        ImportField("description", "Description"),
        ImportField("quantity_ordered", "Quantity Ordered", FieldType.NUMBER, required=True, aliases=("qty ordered", "quantity")),
        ImportField("required_date", "Required Date", FieldType.DATE, aliases=("required",)),
        ImportField("promised_date", "Promised Date", FieldType.DATE, aliases=("promised",)),
        ImportField("buyer", "Buyer"),
        ImportField(
            "status", "Status", FieldType.ENUM, allowed_values=tuple(s.value for s in PurchaseOrderStatus),
        ),
    ),
)

IMPORT_TARGETS: dict[str, ImportTarget] = {
    t.key: t
    for t in (
        CUSTOMERS_TARGET,
        VENDORS_TARGET,
        PARTS_TARGET,
        CUSTOMER_ORDER_LINES_TARGET,
        PURCHASE_ORDER_LINES_TARGET,
    )
}

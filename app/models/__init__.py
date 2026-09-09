"""ORM models.

Importing this package registers every mapped class on :class:`app.database.base.Base`,
which is required before calling ``Base.metadata.create_all`` or running Alembic
autogenerate. Always import ``app.models`` (not an individual submodule) before
touching the schema.
"""

from app.database.base import Base
from app.models.audit import ActivityLogEntry, Alert, Note
from app.models.core import Customer, Part, User, Vendor
from app.models.followup import FollowUp
from app.models.imports import ImportBatch, ImportRowError
from app.models.orders import CustomerOrder, CustomerOrderLine, SalesOrder
from app.models.production import ProductionOperation, ProductionOrder
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine
from app.models.rma import Rma
from app.models.shipping import Shipment, ShipmentLine

__all__ = [
    "ActivityLogEntry",
    "Alert",
    "Base",
    "Customer",
    "CustomerOrder",
    "CustomerOrderLine",
    "FollowUp",
    "ImportBatch",
    "ImportRowError",
    "Note",
    "Part",
    "ProductionOperation",
    "ProductionOrder",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "Rma",
    "SalesOrder",
    "Shipment",
    "ShipmentLine",
    "User",
    "Vendor",
]

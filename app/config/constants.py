"""Canonical vocabularies shared by every layer of the application.

These enums are the *single* definition of the operational states used by the
database, the business rules and the UI.  Presentation details (colour, sort
order, thresholds) live in :mod:`app.config.settings`, never in UI code.
"""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    """Lifecycle of a customer order line / production demand.

    ``PAST_DUE`` is deliberately *not* a member: lateness is derived from the
    due date, it is not a state somebody types in.  Mixing the two is the
    classic way schedules start lying.
    """

    NOT_STARTED = "NOT STARTED"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN PROGRESS"
    WAITING_MATERIAL = "WAITING MATERIAL"
    WAITING_PURCHASE = "WAITING PURCHASE"
    WAITING_CUSTOMER = "WAITING CUSTOMER"
    WAITING_ENGINEERING = "WAITING ENGINEERING"
    WAITING_INSPECTION = "WAITING INSPECTION"
    READY_TO_SHIP = "READY TO SHIP"
    SHIPPED = "SHIPPED"
    COMPLETE = "COMPLETE"
    ON_HOLD = "ON HOLD"
    CANCELLED = "CANCELLED"


#: States that stop the clock - no lateness, no alerts, no follow-up nagging.
CLOSED_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {OrderStatus.COMPLETE, OrderStatus.CANCELLED, OrderStatus.SHIPPED}
)

#: States where the order is blocked by somebody other than the shop floor.
BLOCKED_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.WAITING_MATERIAL,
        OrderStatus.WAITING_PURCHASE,
        OrderStatus.WAITING_CUSTOMER,
        OrderStatus.WAITING_ENGINEERING,
        OrderStatus.WAITING_INSPECTION,
        OrderStatus.ON_HOLD,
    }
)


class Priority(StrEnum):
    """Computed or manually pinned attention level."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


PRIORITY_RANK: dict[Priority, int] = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class ProductionStatus(StrEnum):
    """State of a single routing operation."""

    NOT_STARTED = "NOT STARTED"
    SETUP = "SETUP"
    RUNNING = "RUNNING"
    WAITING_MATERIAL = "WAITING MATERIAL"
    WAITING_PROGRAMMING = "WAITING PROGRAMMING"
    WAITING_TOOLING = "WAITING TOOLING"
    WAITING_INSPECTION = "WAITING INSPECTION"
    AT_VENDOR = "AT VENDOR"
    ON_HOLD = "ON HOLD"
    COMPLETE = "COMPLETE"


CLOSED_PRODUCTION_STATUSES: frozenset[ProductionStatus] = frozenset({ProductionStatus.COMPLETE})


class PurchaseOrderStatus(StrEnum):
    """State of a purchase order line."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


CLOSED_PO_STATUSES: frozenset[PurchaseOrderStatus] = frozenset(
    {PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CLOSED, PurchaseOrderStatus.CANCELLED}
)


class ShipmentStatus(StrEnum):
    """State of an outbound shipment."""

    PLANNED = "PLANNED"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class RmaStatus(StrEnum):
    """State of a return / corrective-action case."""

    OPEN = "OPEN"
    RECEIVED = "RECEIVED"
    UNDER_INVESTIGATION = "UNDER INVESTIGATION"
    CORRECTIVE_ACTION = "CORRECTIVE ACTION"
    REWORK = "REWORK"
    REPLACEMENT_IN_PRODUCTION = "REPLACEMENT IN PRODUCTION"
    CREDIT_ISSUED = "CREDIT ISSUED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


CLOSED_RMA_STATUSES: frozenset[RmaStatus] = frozenset({RmaStatus.CLOSED, RmaStatus.CANCELLED})


class FollowUpStatus(StrEnum):
    """State of a coordinator follow-up item."""

    OPEN = "OPEN"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


CLOSED_FOLLOWUP_STATUSES: frozenset[FollowUpStatus] = frozenset(
    {FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED}
)


class CommunicationMethod(StrEnum):
    """How a follow-up contact was made."""

    EMAIL = "EMAIL"
    PHONE = "PHONE"
    TEAMS = "TEAMS"
    INTERNAL = "INTERNAL"
    OTHER = "OTHER"


class Department(StrEnum):
    """Internal owning department for work and follow-ups."""

    PLANNING = "PLANNING"
    PURCHASING = "PURCHASING"
    PRODUCTION = "PRODUCTION"
    ENGINEERING = "ENGINEERING"
    QUALITY = "QUALITY"
    SHIPPING = "SHIPPING"
    SALES = "SALES"
    MANAGEMENT = "MANAGEMENT"
    OTHER = "OTHER"


class AlertSeverity(StrEnum):
    """Severity band for generated alerts."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"


class AlertStatus(StrEnum):
    """Lifecycle of an alert instance."""

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SNOOZED = "SNOOZED"
    RESOLVED = "RESOLVED"
    OBSOLETE = "OBSOLETE"


class UserRole(StrEnum):
    """Authorisation role."""

    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    VIEWER = "VIEWER"


class EntityType(StrEnum):
    """Record kinds that can be referenced by notes, alerts and audit rows."""

    PART = "PART"
    CUSTOMER = "CUSTOMER"
    VENDOR = "VENDOR"
    CUSTOMER_ORDER = "CUSTOMER_ORDER"
    CUSTOMER_ORDER_LINE = "CUSTOMER_ORDER_LINE"
    SALES_ORDER = "SALES_ORDER"
    PRODUCTION_ORDER = "PRODUCTION_ORDER"
    PRODUCTION_OPERATION = "PRODUCTION_OPERATION"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    PURCHASE_ORDER_LINE = "PURCHASE_ORDER_LINE"
    SHIPMENT = "SHIPMENT"
    SHIPMENT_LINE = "SHIPMENT_LINE"
    RMA = "RMA"
    FOLLOW_UP = "FOLLOW_UP"
    USER = "USER"
    IMPORT_BATCH = "IMPORT_BATCH"


class ImportStatus(StrEnum):
    """Outcome of an Excel/CSV import batch."""

    PREVIEW = "PREVIEW"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ThemeMode(StrEnum):
    """Colour scheme selection."""

    LIGHT = "LIGHT"
    DARK = "DARK"
    SYSTEM = "SYSTEM"


#: Maximum length used for short business identifiers (PN, CO, PO, ...).
CODE_LENGTH = 64
#: Maximum length for free-text single-line fields.
NAME_LENGTH = 255

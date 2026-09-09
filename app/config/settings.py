"""Persisted application settings.

Every business threshold the coordinator might reasonably want to change lives
here, is serialised to ``settings.json`` in the application-data root, and is
read by the business layer at run time.  Nothing in this module imports Qt or
SQLAlchemy, so settings can be loaded by tests, scripts and the packaging code.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypeVar

from app.config import paths
from app.config.constants import (
    AlertSeverity,
    OrderStatus,
    Priority,
    PurchaseOrderStatus,
    RmaStatus,
    ThemeMode,
)

log = logging.getLogger(__name__)

SETTINGS_VERSION = 1

T = TypeVar("T")


@dataclass(slots=True)
class CompanySettings:
    """Identity shown on reports and exports."""

    name: str = "CAMCO Manufacturing"
    site: str = ""
    logo_path: str = ""
    report_footer: str = ""


@dataclass(slots=True)
class PathSettings:
    """Operational file locations.  Empty string means "use the default".

    ``database_file`` and ``backup_dir`` default to the application-data root;
    the ``*_folder`` entries point at the shared drive where the source
    spreadsheets live and are only ever read from.
    """

    database_file: str = ""
    backup_dir: str = ""
    report_output_dir: str = ""
    master_schedule_folder: str = ""
    customer_order_folder: str = ""
    purchasing_folder: str = ""
    production_folder: str = ""
    shipping_folder: str = ""

    def resolved_database_file(self) -> Path:
        """Configured database path, or the application-data default."""
        return Path(self.database_file) if self.database_file else paths.default_database_file()

    def resolved_backup_dir(self) -> Path:
        """Configured backup directory, or the application-data default."""
        return Path(self.backup_dir) if self.backup_dir else paths.backups_dir()

    def resolved_report_dir(self) -> Path:
        """Configured report output directory, or the application-data default."""
        return Path(self.report_output_dir) if self.report_output_dir else paths.reports_dir()


@dataclass(slots=True)
class LocaleSettings:
    """Date / time presentation and the timezone all calculations run in."""

    timezone: str = "America/New_York"
    date_format: str = "MM/dd/yyyy"
    datetime_format: str = "MM/dd/yyyy hh:mm AP"


@dataclass(slots=True)
class CalendarSettings:
    """Working calendar used by every "days late / days remaining" calculation.

    ``work_days`` uses Python's convention: Monday = 0 ... Sunday = 6.
    """

    work_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    holidays: list[str] = field(default_factory=list)
    shutdown_ranges: list[list[str]] = field(default_factory=list)
    use_business_days: bool = True

    def holiday_dates(self) -> set[date]:
        """Parse configured holidays and shutdown ranges into concrete dates."""
        result: set[date] = set()
        for raw in self.holidays:
            parsed = _parse_iso_date(raw)
            if parsed:
                result.add(parsed)
        for pair in self.shutdown_ranges:
            if len(pair) != 2:
                continue
            start, end = _parse_iso_date(pair[0]), _parse_iso_date(pair[1])
            if not start or not end or end < start:
                continue
            current = start
            while current <= end:
                result.add(current)
                current = date.fromordinal(current.toordinal() + 1)
        return result


@dataclass(slots=True)
class PrioritySettings:
    """Weights and thresholds for the automatic priority engine.

    The score is a weighted sum; the ``*_score`` thresholds convert it into a
    band.  Raising ``weight_days_late`` makes lateness dominate, and so on.
    """

    weight_days_late: float = 6.0
    weight_days_until_due: float = 4.0
    weight_customer_importance: float = 8.0
    weight_blocked: float = 10.0
    weight_material_shortage: float = 12.0
    weight_open_rma: float = 15.0
    weight_quantity: float = 2.0
    weight_ready_to_ship: float = 5.0
    critical_score: float = 70.0
    high_score: float = 45.0
    medium_score: float = 20.0
    due_soon_days: int = 5
    quantity_reference: int = 100
    max_days_late_considered: int = 30


@dataclass(slots=True)
class AlertSettings:
    """Thresholds that decide when the alert engine speaks up."""

    enabled: bool = True
    due_soon_days: int = 5
    critical_late_days: int = 5
    po_late_days: int = 1
    po_due_soon_days: int = 5
    stagnant_operation_days: int = 10
    followup_overdue_days: int = 0
    refresh_minutes: int = 15
    default_snooze_days: int = 1
    show_desktop_notifications: bool = True


@dataclass(slots=True)
class RmaSettings:
    """Aging buckets for RMA reporting, expressed in months."""

    aging_buckets_months: list[float] = field(default_factory=lambda: [1, 3, 6, 12])
    target_close_days: int = 30


@dataclass(slots=True)
class ShippingSettings:
    """On-time-shipment measurement rules."""

    on_time_grace_days: int = 0
    default_analysis_months: int = 12


@dataclass(slots=True)
class BackupSettings:
    """Automatic backup policy."""

    enabled: bool = True
    on_startup: bool = False
    on_shutdown: bool = True
    interval_hours: int = 12
    retention_days: int = 60
    minimum_retained: int = 5


@dataclass(slots=True)
class UiSettings:
    """Look, feel and table behaviour."""

    theme: str = ThemeMode.LIGHT.value
    accent_color: str = "#0F62FE"
    font_point_size: int = 10
    page_size: int = 200
    remember_window_geometry: bool = True
    window_geometry: str = ""
    window_state: str = ""
    last_page: str = "dashboard"
    dashboard_cards: list[str] = field(
        default_factory=lambda: [
            "open_customer_orders",
            "past_due",
            "due_today",
            "due_this_week",
            "late_purchase_orders",
            "awaiting_material",
            "open_rmas",
            "open_follow_ups",
        ]
    )


@dataclass(slots=True)
class LoggingSettings:
    """Log verbosity and retention."""

    level: str = "INFO"
    max_bytes: int = 2_000_000
    backup_count: int = 10
    log_sql: bool = False


@dataclass(slots=True)
class SecuritySettings:
    """Local authentication behaviour."""

    require_login: bool = True
    session_idle_minutes: int = 0
    min_password_length: int = 8
    max_failed_attempts: int = 5
    lockout_minutes: int = 10


@dataclass(slots=True)
class AiSettings:
    """AI/ML is opt-in and must never be required for the app to work."""

    enabled: bool = False
    provider: str = "none"
    endpoint: str = ""
    model: str = ""
    show_risk_predictions: bool = False


def _default_status_colors() -> dict[str, str]:
    """Colour per status/priority token, keyed by the enum *value*."""
    return {
        OrderStatus.NOT_STARTED.value: "#6B7280",
        OrderStatus.PLANNED.value: "#3B82F6",
        OrderStatus.IN_PROGRESS.value: "#0EA5E9",
        OrderStatus.WAITING_MATERIAL.value: "#D97706",
        OrderStatus.WAITING_PURCHASE.value: "#B45309",
        OrderStatus.WAITING_CUSTOMER.value: "#7C3AED",
        OrderStatus.WAITING_ENGINEERING.value: "#8B5CF6",
        OrderStatus.WAITING_INSPECTION.value: "#0891B2",
        OrderStatus.READY_TO_SHIP.value: "#059669",
        OrderStatus.SHIPPED.value: "#047857",
        OrderStatus.COMPLETE.value: "#15803D",
        OrderStatus.ON_HOLD.value: "#DC2626",
        OrderStatus.CANCELLED.value: "#4B5563",
        "PAST DUE": "#B91C1C",
        Priority.CRITICAL.value: "#B91C1C",
        Priority.HIGH.value: "#EA580C",
        Priority.MEDIUM.value: "#CA8A04",
        Priority.LOW.value: "#2563EB",
        AlertSeverity.CRITICAL.value: "#B91C1C",
        AlertSeverity.HIGH.value: "#EA580C",
        AlertSeverity.MEDIUM.value: "#CA8A04",
        AlertSeverity.INFO.value: "#2563EB",
        PurchaseOrderStatus.OPEN.value: "#3B82F6",
        PurchaseOrderStatus.ACKNOWLEDGED.value: "#0EA5E9",
        PurchaseOrderStatus.PARTIAL.value: "#D97706",
        PurchaseOrderStatus.RECEIVED.value: "#15803D",
        PurchaseOrderStatus.CLOSED.value: "#4B5563",
        PurchaseOrderStatus.CANCELLED.value: "#4B5563",
        RmaStatus.OPEN.value: "#DC2626",
        RmaStatus.UNDER_INVESTIGATION.value: "#D97706",
        RmaStatus.CORRECTIVE_ACTION.value: "#CA8A04",
        RmaStatus.CLOSED.value: "#15803D",
    }


@dataclass(slots=True)
class AppSettings:
    """Root settings document."""

    version: int = SETTINGS_VERSION
    company: CompanySettings = field(default_factory=CompanySettings)
    paths: PathSettings = field(default_factory=PathSettings)
    locale: LocaleSettings = field(default_factory=LocaleSettings)
    calendar: CalendarSettings = field(default_factory=CalendarSettings)
    priority: PrioritySettings = field(default_factory=PrioritySettings)
    alerts: AlertSettings = field(default_factory=AlertSettings)
    rma: RmaSettings = field(default_factory=RmaSettings)
    shipping: ShippingSettings = field(default_factory=ShippingSettings)
    backup: BackupSettings = field(default_factory=BackupSettings)
    ui: UiSettings = field(default_factory=UiSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    ai: AiSettings = field(default_factory=AiSettings)
    status_colors: dict[str, str] = field(default_factory=_default_status_colors)

    def color_for(self, token: str, fallback: str = "#6B7280") -> str:
        """Return the configured colour for a status/priority token."""
        return self.status_colors.get(str(token), fallback)


def _parse_iso_date(raw: str) -> date | None:
    """Parse an ISO date string, logging and skipping bad values."""
    try:
        return date.fromisoformat(str(raw).strip())
    except (ValueError, AttributeError):
        log.warning("Ignoring unparsable configured date %r", raw)
        return None


def _section_from_dict(cls: type[T], payload: Any) -> T:
    """Build a settings section from JSON, ignoring unknown keys.

    Forward/backward compatibility matters here: an older build must be able to
    open a settings file written by a newer one without losing the user's other
    preferences.
    """
    if not isinstance(payload, dict):
        return cls()  # type: ignore[call-arg]
    known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    kwargs = {key: value for key, value in payload.items() if key in known}
    try:
        return cls(**kwargs)  # type: ignore[call-arg]
    except TypeError:
        log.exception("Malformed settings section for %s; using defaults", cls.__name__)
        return cls()  # type: ignore[call-arg]


def settings_from_dict(payload: dict[str, Any]) -> AppSettings:
    """Deserialise a settings document, tolerating partial or stale files."""
    result = AppSettings()
    for f in fields(AppSettings):
        if f.name not in payload:
            continue
        value = payload[f.name]
        current = getattr(result, f.name)
        if is_dataclass(current) and not isinstance(current, type):
            setattr(result, f.name, _section_from_dict(type(current), value))
        elif f.name == "status_colors" and isinstance(value, dict):
            merged = _default_status_colors()
            merged.update({str(k): str(v) for k, v in value.items()})
            result.status_colors = merged
        elif f.name != "version":
            setattr(result, f.name, value)
    result.version = SETTINGS_VERSION
    return result


def settings_to_dict(settings: AppSettings) -> dict[str, Any]:
    """Serialise a settings document to plain JSON-compatible types."""
    return asdict(settings)


class SettingsManager:
    """Loads, caches and atomically saves :class:`AppSettings`."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or paths.settings_file()
        self._settings: AppSettings | None = None

    @property
    def path(self) -> Path:
        """Location of the JSON settings document."""
        return self._path

    @property
    def settings(self) -> AppSettings:
        """Return the cached settings, loading them on first access."""
        if self._settings is None:
            self._settings = self.load()
        return self._settings

    def load(self) -> AppSettings:
        """Read settings from disk; fall back to defaults on any problem."""
        if not self._path.exists():
            self._settings = AppSettings()
            self.save(self._settings)
            return self._settings
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            self._settings = settings_from_dict(payload)
        except (OSError, json.JSONDecodeError):
            log.exception("Could not read %s; falling back to defaults", self._path)
            self._settings = AppSettings()
        return self._settings

    def save(self, settings: AppSettings | None = None) -> None:
        """Write settings using temp-file + replace so a crash cannot truncate."""
        target = settings or self.settings
        self._settings = target
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(settings_to_dict(target), indent=2, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, self._path)
        except OSError:
            log.exception("Failed to save settings to %s", self._path)
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def reset(self) -> AppSettings:
        """Restore factory defaults and persist them."""
        self._settings = AppSettings()
        self.save(self._settings)
        return self._settings


_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Return the process-wide settings manager."""
    global _manager
    if _manager is None:
        _manager = SettingsManager()
    return _manager


def get_settings() -> AppSettings:
    """Convenience accessor for the current settings."""
    return get_settings_manager().settings


def set_settings_manager(manager: SettingsManager | None) -> None:
    """Replace the process-wide manager (used by tests)."""
    global _manager
    _manager = manager

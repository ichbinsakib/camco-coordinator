"""Alerts list page - system-generated attention items with acknowledge/snooze/resolve."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox, QPushButton, QSpinBox

from app.alerts.engine import refresh_alerts
from app.config.constants import AlertSeverity
from app.config.settings import get_settings
from app.models.audit import Alert
from app.repositories.alerts import AlertFilters, AlertRepository
from app.services.activity_log_service import log_event
from app.ui.app_context import AppContext
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)

_COLUMNS = [
    ColumnSpec("Severity", lambda a: a.severity, color=lambda a: get_settings().color_for(a.severity)),
    ColumnSpec("Rule", lambda a: a.rule_code),
    ColumnSpec("Message", lambda a: a.message),
    ColumnSpec("Status", lambda a: a.status),
    ColumnSpec("Raised", lambda a: a.created_at),
]


class AlertsPage(ListPageBase):
    """The system's ranked list of things that need attention."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Alerts",
            "Automatically generated attention items: past due orders, late POs, "
            "material shortages, stagnant operations, and overdue follow-ups.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
        )

        filter_bar = self.filter_bar_layout()
        filter_bar.addWidget(QLabel("Severity:"))
        self._severity_filter = QComboBox()
        self._severity_filter.addItem("All Severities", None)
        for severity in AlertSeverity:
            self._severity_filter.addItem(severity.value, severity.value)
        self._severity_filter.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self._severity_filter)

        refresh_btn = QPushButton("Refresh Alerts")
        refresh_btn.setObjectName("PrimaryButton")
        refresh_btn.clicked.connect(self._run_engine)
        filter_bar.addWidget(refresh_btn)

        if context.current_user.can_edit:
            ack_btn = QPushButton("Acknowledge")
            ack_btn.clicked.connect(self._acknowledge)
            filter_bar.addWidget(ack_btn)

            snooze_row = QLabel("Snooze")
            filter_bar.addWidget(snooze_row)
            self._snooze_days = QSpinBox()
            self._snooze_days.setRange(1, 90)
            self._snooze_days.setValue(get_settings().alerts.default_snooze_days)
            filter_bar.addWidget(self._snooze_days)
            snooze_btn = QPushButton("days")
            snooze_btn.clicked.connect(self._snooze)
            filter_bar.addWidget(snooze_btn)

            resolve_btn = QPushButton("Resolve")
            resolve_btn.clicked.connect(self._resolve)
            filter_bar.addWidget(resolve_btn)

        self.refresh()

    def _current_filters(self, text: str) -> AlertFilters:
        return AlertFilters(text=text, severity=self._severity_filter.currentData())

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[Alert], int]:
        with self._context.session_factory() as session:
            repo = AlertRepository(session)
            rows, total = repo.search_active(self._current_filters(text), limit=limit, offset=offset)
            session.expunge_all()
            return rows, total

    def _run_engine(self) -> None:
        with self._context.session_factory() as session:
            result = refresh_alerts(session, self._context.settings)
        QMessageBox.information(
            self,
            "Alerts Refreshed",
            f"{result.candidates_evaluated} conditions checked: "
            f"{result.created} new, {result.updated} updated, {result.resolved} auto-resolved.",
        )
        self.refresh()

    def _acknowledge(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select an alert first.")
            return
        with self._context.session_factory() as session:
            AlertRepository(session).acknowledge(row.id, self._context.current_user.id)
            session.commit()
        self.refresh()

    def _snooze(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select an alert first.")
            return
        with self._context.session_factory() as session:
            AlertRepository(session).snooze(row.id, self._snooze_days.value())
            session.commit()
        self.refresh()

    def _resolve(self) -> None:
        row = self.selected_row()
        if row is None:
            QMessageBox.information(self, "No Selection", "Select an alert first.")
            return
        with self._context.session_factory() as session:
            AlertRepository(session).resolve(row.id)
            log_event(
                session,
                entity_type="ALERT",
                entity_id=row.id,
                description=f"Alert manually resolved: {row.message}",
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

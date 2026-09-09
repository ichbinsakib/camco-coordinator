"""Settings: every configurable business rule and file location in one place.

Nothing here mutates ``AppSettings`` directly on every keystroke - changes are
staged in the widgets and written back (then persisted to disk) only when the
user clicks Save, so a half-edited form can't corrupt the live configuration.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config.constants import ThemeMode
from app.config.settings import SettingsManager
from app.services.backup_service import BackupService

log = logging.getLogger(__name__)


class _FolderRow(QWidget):
    """A path text field with a Browse button, used repeatedly on this page."""

    def __init__(self, initial: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(initial)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        layout.addWidget(self.edit)
        layout.addWidget(browse)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Folder", self.edit.text() or "")
        if directory:
            self.edit.setText(directory)

    def text(self) -> str:
        return self.edit.text().strip()


class SettingsPage(QWidget):
    """Tabbed settings editor backed by :class:`SettingsManager`."""

    def __init__(self, manager: SettingsManager, parent=None) -> None:
        super().__init__(parent)
        self._manager = manager

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._build_company_tab()
        self._build_folders_tab()
        self._build_calendar_tab()
        self._build_priority_alerts_tab()
        self._build_backup_tab()
        self._build_security_tab()
        self._build_appearance_tab()

        button_row = QHBoxLayout()
        button_row.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        root.addLayout(button_row)

    # -- tabs -----------------------------------------------------------

    def _build_company_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)
        self._company_name = QLineEdit(s.company.name)
        self._company_site = QLineEdit(s.company.site)
        self._report_footer = QLineEdit(s.company.report_footer)
        form.addRow("Company Name", self._company_name)
        form.addRow("Site", self._company_site)
        form.addRow("Report Footer", self._report_footer)
        self._tabs.addTab(page, "Company")

    def _build_folders_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)
        self._db_file = _FolderRow(str(s.paths.database_file))
        self._backup_dir = _FolderRow(str(s.paths.backup_dir))
        self._report_dir = _FolderRow(str(s.paths.report_output_dir))
        self._master_schedule = _FolderRow(str(s.paths.master_schedule_folder))
        self._customer_order = _FolderRow(str(s.paths.customer_order_folder))
        self._purchasing = _FolderRow(str(s.paths.purchasing_folder))
        self._production = _FolderRow(str(s.paths.production_folder))
        self._shipping = _FolderRow(str(s.paths.shipping_folder))
        form.addRow("Database File (blank = default)", self._db_file)
        form.addRow("Backup Folder (blank = default)", self._backup_dir)
        form.addRow("Report Output Folder (blank = default)", self._report_dir)
        form.addRow("Master Schedule Folder", self._master_schedule)
        form.addRow("Customer Orders Folder", self._customer_order)
        form.addRow("Purchasing Folder", self._purchasing)
        form.addRow("Production Folder", self._production)
        form.addRow("Shipping Folder", self._shipping)
        self._tabs.addTab(page, "Folders")

    def _build_calendar_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)
        self._use_business_days = QCheckBox("Use business-day calendar for due-date math")
        self._use_business_days.setChecked(s.calendar.use_business_days)
        self._work_days = QLineEdit(",".join(str(d) for d in s.calendar.work_days))
        self._work_days.setToolTip("Comma-separated weekdays, Monday=0 ... Sunday=6. Default: 0,1,2,3,4")
        form.addRow(self._use_business_days)
        form.addRow("Work Days", self._work_days)
        form.addRow(QLabel("Holidays and shutdown ranges are managed via the settings file for now."))
        self._tabs.addTab(page, "Calendar")

    def _build_priority_alerts_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)

        self._due_soon_days = QSpinBox()
        self._due_soon_days.setRange(0, 60)
        self._due_soon_days.setValue(s.alerts.due_soon_days)

        self._critical_late_days = QSpinBox()
        self._critical_late_days.setRange(0, 120)
        self._critical_late_days.setValue(s.alerts.critical_late_days)

        self._po_late_days = QSpinBox()
        self._po_late_days.setRange(0, 60)
        self._po_late_days.setValue(s.alerts.po_late_days)

        self._stagnant_days = QSpinBox()
        self._stagnant_days.setRange(1, 120)
        self._stagnant_days.setValue(s.alerts.stagnant_operation_days)

        self._critical_score = QDoubleSpinBox()
        self._critical_score.setRange(0, 1000)
        self._critical_score.setValue(s.priority.critical_score)

        self._high_score = QDoubleSpinBox()
        self._high_score.setRange(0, 1000)
        self._high_score.setValue(s.priority.high_score)

        self._medium_score = QDoubleSpinBox()
        self._medium_score.setRange(0, 1000)
        self._medium_score.setValue(s.priority.medium_score)

        form.addRow("Alerts: Due-Soon Window (days)", self._due_soon_days)
        form.addRow("Alerts: Critical-Late Threshold (days)", self._critical_late_days)
        form.addRow("Alerts: PO Late Threshold (days)", self._po_late_days)
        form.addRow("Alerts: Stagnant Operation Threshold (days)", self._stagnant_days)
        form.addRow("Priority: Critical Score Cutoff", self._critical_score)
        form.addRow("Priority: High Score Cutoff", self._high_score)
        form.addRow("Priority: Medium Score Cutoff", self._medium_score)
        self._tabs.addTab(page, "Priority && Alerts")

    def _build_backup_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self._backup_enabled = QCheckBox("Enable automatic backups")
        self._backup_enabled.setChecked(s.backup.enabled)
        self._backup_interval = QSpinBox()
        self._backup_interval.setRange(1, 168)
        self._backup_interval.setValue(s.backup.interval_hours)
        self._backup_retention = QSpinBox()
        self._backup_retention.setRange(1, 3650)
        self._backup_retention.setValue(s.backup.retention_days)

        form.addRow(self._backup_enabled)
        form.addRow("Backup Interval (hours)", self._backup_interval)
        form.addRow("Retention (days)", self._backup_retention)
        layout.addLayout(form)

        backup_now_btn = QPushButton("Back Up Now")
        backup_now_btn.clicked.connect(self._backup_now)
        layout.addWidget(backup_now_btn)
        layout.addStretch()
        self._tabs.addTab(page, "Backup")

    def _build_security_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)

        self._session_idle_minutes = QSpinBox()
        self._session_idle_minutes.setRange(0, 480)
        self._session_idle_minutes.setSpecialValueText("Disabled")
        self._session_idle_minutes.setSuffix(" minutes")
        self._session_idle_minutes.setValue(s.security.session_idle_minutes)

        self._min_password_length = QSpinBox()
        self._min_password_length.setRange(6, 64)
        self._min_password_length.setValue(s.security.min_password_length)

        self._max_failed_attempts = QSpinBox()
        self._max_failed_attempts.setRange(1, 20)
        self._max_failed_attempts.setValue(s.security.max_failed_attempts)

        self._lockout_minutes = QSpinBox()
        self._lockout_minutes.setRange(1, 1440)
        self._lockout_minutes.setValue(s.security.lockout_minutes)

        form.addRow("Lock Screen After Idle", self._session_idle_minutes)
        note = QLabel(
            "0 disables the idle lock. When enabled, the app requires your password again "
            "after this many minutes of no mouse/keyboard activity - the window stays open, "
            "nothing is lost, it just can't be used until you unlock it. "
            "Restart the application for a change here to take effect."
        )
        note.setObjectName("PageSubtitle")
        note.setWordWrap(True)
        form.addRow(note)
        form.addRow("Minimum Password Length", self._min_password_length)
        form.addRow("Max Failed Login Attempts", self._max_failed_attempts)
        form.addRow("Lockout Duration", self._lockout_minutes)
        self._tabs.addTab(page, "Security")

    def _build_appearance_tab(self) -> None:
        s = self._manager.settings
        page = QWidget()
        form = QFormLayout(page)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems([ThemeMode.LIGHT.value, ThemeMode.DARK.value])
        self._theme_combo.setCurrentText(s.ui.theme)
        form.addRow("Theme", self._theme_combo)
        note = QLabel("Restart the application for theme changes to fully apply.")
        note.setObjectName("PageSubtitle")
        form.addRow(note)
        self._tabs.addTab(page, "Appearance")

    # -- actions ----------------------------------------------------------

    def _backup_now(self) -> None:
        try:
            result = BackupService(self._manager.settings).create_backup()
        except Exception as exc:
            log.exception("Manual backup failed")
            QMessageBox.critical(self, "Backup Failed", str(exc))
            return
        QMessageBox.information(self, "Backup Complete", f"Backup saved to:\n{result.path}")

    def _save(self) -> None:
        s = self._manager.settings

        s.company = replace(
            s.company,
            name=self._company_name.text().strip() or s.company.name,
            site=self._company_site.text().strip(),
            report_footer=self._report_footer.text().strip(),
        )
        s.paths = replace(
            s.paths,
            database_file=self._db_file.text(),
            backup_dir=self._backup_dir.text(),
            report_output_dir=self._report_dir.text(),
            master_schedule_folder=self._master_schedule.text(),
            customer_order_folder=self._customer_order.text(),
            purchasing_folder=self._purchasing.text(),
            production_folder=self._production.text(),
            shipping_folder=self._shipping.text(),
        )
        try:
            work_days = [int(x) for x in self._work_days.text().split(",") if x.strip() != ""]
        except ValueError:
            QMessageBox.warning(self, "Invalid Work Days", "Work Days must be comma-separated numbers 0-6.")
            return
        s.calendar = replace(
            s.calendar, use_business_days=self._use_business_days.isChecked(), work_days=work_days
        )
        s.alerts = replace(
            s.alerts,
            due_soon_days=self._due_soon_days.value(),
            critical_late_days=self._critical_late_days.value(),
            po_late_days=self._po_late_days.value(),
            stagnant_operation_days=self._stagnant_days.value(),
        )
        s.priority = replace(
            s.priority,
            critical_score=self._critical_score.value(),
            high_score=self._high_score.value(),
            medium_score=self._medium_score.value(),
        )
        s.backup = replace(
            s.backup,
            enabled=self._backup_enabled.isChecked(),
            interval_hours=self._backup_interval.value(),
            retention_days=self._backup_retention.value(),
        )
        s.security = replace(
            s.security,
            session_idle_minutes=self._session_idle_minutes.value(),
            min_password_length=self._min_password_length.value(),
            max_failed_attempts=self._max_failed_attempts.value(),
            lockout_minutes=self._lockout_minutes.value(),
        )
        s.ui = replace(s.ui, theme=self._theme_combo.currentText())

        try:
            self._manager.save(s)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")

"""Reports page: pick a report, pick a format, generate it to the configured output folder."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.reports.builders import (
    build_customer_order_report,
    build_daily_coordinator_report,
    build_management_summary_report,
    build_on_time_shipment_report,
    build_rma_aging_report,
    build_vendor_performance_report,
)
from app.reports.csv_export import export_report_to_csv
from app.reports.excel_export import export_report_to_excel
from app.reports.model import Report
from app.reports.pdf_export import export_report_to_pdf
from app.repositories.shipping import STANDARD_RANGES
from app.ui.app_context import AppContext

log = logging.getLogger(__name__)

_REPORT_BUILDERS: dict[str, str] = {
    "Daily Coordinator Report": "daily",
    "Customer Order Report": "customer_order",
    "Vendor Performance Report": "vendor_performance",
    "On-Time Shipment Report": "on_time_shipment",
    "RMA Aging Report": "rma_aging",
    "Management Summary": "management_summary",
}


class ReportsPage(QWidget):
    """Pick a report type and format, generate it, and show where it was saved."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self._context = context

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(10)

        heading = QLabel("Reports")
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        sub = QLabel("Generate a report to Excel, PDF or CSV in the configured report output folder.")
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        form = QFormLayout()
        self._report_combo = QComboBox()
        self._report_combo.addItems(list(_REPORT_BUILDERS))
        self._report_combo.currentTextChanged.connect(self._on_report_changed)
        form.addRow("Report", self._report_combo)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["Excel (.xlsx)", "PDF (.pdf)", "CSV (.csv)"])
        form.addRow("Format", self._format_combo)

        self._range_combo = QComboBox()
        for label, _months in STANDARD_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.setCurrentText("Last 12 Months")
        self._range_row_label = QLabel("Date Range")
        form.addRow(self._range_row_label, self._range_combo)
        root.addLayout(form)

        generate_btn = QPushButton("Generate Report")
        generate_btn.setObjectName("PrimaryButton")
        generate_btn.clicked.connect(self._generate)
        root.addWidget(generate_btn)

        self._status_label = QLabel("")
        self._status_label.setObjectName("PageSubtitle")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)
        root.addStretch()

        self._on_report_changed(self._report_combo.currentText())

    def _on_report_changed(self, report_name: str) -> None:
        needs_range = _REPORT_BUILDERS.get(report_name) == "on_time_shipment"
        self._range_row_label.setVisible(needs_range)
        self._range_combo.setVisible(needs_range)

    def _build_report(self, session, report_key: str) -> Report:
        settings = self._context.settings
        generated_by = self._context.current_user.display_name
        if report_key == "daily":
            return build_daily_coordinator_report(session, settings, generated_by=generated_by)
        if report_key == "customer_order":
            return build_customer_order_report(session, settings, generated_by=generated_by)
        if report_key == "vendor_performance":
            return build_vendor_performance_report(session, settings, generated_by=generated_by)
        if report_key == "on_time_shipment":
            return build_on_time_shipment_report(
                session, settings, generated_by=generated_by, range_label=self._range_combo.currentText()
            )
        if report_key == "rma_aging":
            return build_rma_aging_report(session, settings, generated_by=generated_by)
        if report_key == "management_summary":
            return build_management_summary_report(session, settings, generated_by=generated_by)
        raise ValueError(f"Unknown report key: {report_key}")

    def _generate(self) -> None:
        report_name = self._report_combo.currentText()
        report_key = _REPORT_BUILDERS[report_name]

        try:
            with self._context.session_factory() as session:
                report = self._build_report(session, report_key)
        except Exception:
            log.exception("Failed to build report %s", report_name)
            QMessageBox.critical(self, "Report Failed", "Could not generate this report. See the logs for details.")
            return

        output_dir = self._context.settings.paths.resolved_report_dir()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base_name = report_name.replace(" ", "_")
        format_choice = self._format_combo.currentText()

        try:
            if format_choice.startswith("Excel"):
                path = export_report_to_excel(report, output_dir / f"{base_name}_{timestamp}.xlsx")
                written = [path]
            elif format_choice.startswith("PDF"):
                path = export_report_to_pdf(report, output_dir / f"{base_name}_{timestamp}.pdf")
                written = [path]
            else:
                written = export_report_to_csv(report, output_dir / f"{base_name}_{timestamp}.csv")
        except OSError:
            log.exception("Failed to write report file")
            QMessageBox.critical(self, "Save Failed", f"Could not write the report file to:\n{output_dir}")
            return

        self._status_label.setText("Saved:\n" + "\n".join(str(p) for p in written))
        QMessageBox.information(self, "Report Generated", f"{report_name} saved to:\n{written[0]}")

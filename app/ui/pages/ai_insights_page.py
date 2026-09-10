"""AI Insights page: Delivery Risk, Recurring Bottlenecks, and Smart Search.

Only reachable when ``AppSettings.ai.enabled`` is on (default off - see
``app/ui/main_window.py``). Every risk number here is rendered next to the
order's real status and explicitly labeled "Predicted Risk" - it is never
allowed to look like or substitute for the actual status column the rest of
the app shows (spec rule 28).
"""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ai.bottleneck_model import recurring_bottlenecks
from app.ai.risk_model import (
    MIN_TRAINING_SAMPLES,
    DeliveryRiskResult,
    predict_risk_for_open_lines,
    train_and_save,
)
from app.ai.smart_search import run_smart_search
from app.models.orders import CustomerOrderLine
from app.ui.app_context import AppContext
from app.ui.widgets.table_model import ColumnSpec, ListTableModel

log = logging.getLogger(__name__)


def _risk_color(result: DeliveryRiskResult) -> str:
    return {"CRITICAL": "#B91C1C", "HIGH": "#EA580C", "MEDIUM": "#CA8A04", "LOW": "#2563EB"}.get(result.band, "#6B7280")


class AiInsightsPage(QWidget):
    """Predicted delivery risk, recurring bottleneck stats, and smart search - all optional."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self._context = context

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(8)

        heading = QLabel("AI Insights")
        heading.setObjectName("PageTitle")
        root.addWidget(heading)
        sub = QLabel(
            "Predicted risk and pattern analysis - always separate from, and never a substitute for, "
            "the actual status shown on the Customer Orders, Production and Purchasing pages."
        )
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(sub)

        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)
        tabs.addTab(self._build_risk_tab(), "Delivery Risk")
        tabs.addTab(self._build_bottleneck_tab(), "Recurring Bottlenecks")
        tabs.addTab(self._build_search_tab(), "Smart Search")

    # -- Delivery Risk ----------------------------------------------------

    def _build_risk_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        self._risk_status_label = QLabel("")
        toolbar.addWidget(self._risk_status_label, stretch=1)
        retrain_btn = QPushButton("Retrain Model From History")
        retrain_btn.setObjectName("PrimaryButton")
        retrain_btn.clicked.connect(self._retrain_model)
        toolbar.addWidget(retrain_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_risk)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        columns = [
            ColumnSpec("CO", lambda r: r[0].customer_order.co_number),
            ColumnSpec("Customer", lambda r: r[0].customer_order.customer.name),
            ColumnSpec("Part", lambda r: r[0].part.part_number),
            ColumnSpec("Due Date", lambda r: r[0].due_date),
            ColumnSpec("Actual Status", lambda r: r[0].status),
            ColumnSpec("Predicted Risk", lambda r: r[1].band, color=lambda r: _risk_color(r[1])),
            ColumnSpec("Risk Score", lambda r: f"{r[1].score:.0f}/100", align_right=True),
            ColumnSpec("Why", lambda r: "; ".join(a.reason for a in r[1].adjustments) or "(base rate only)"),
        ]
        self._risk_model_table = ListTableModel(columns)
        self._risk_table = QTableView()
        self._risk_table.setModel(self._risk_model_table)
        self._risk_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._risk_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._risk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._risk_table.verticalHeader().setVisible(False)
        layout.addWidget(self._risk_table, stretch=1)

        self._refresh_risk()
        return page

    def _refresh_risk(self) -> None:
        try:
            with self._context.session_factory() as session:
                results = predict_risk_for_open_lines(session, self._context.settings)
                lines_by_id = {r.line_id: session.get(CustomerOrderLine, r.line_id) for r in results}
                for line in lines_by_id.values():
                    if line:
                        _ = line.customer_order.co_number
                        _ = line.customer_order.customer.name
                        _ = line.part.part_number
                paired = [(lines_by_id[r.line_id], r) for r in results if lines_by_id.get(r.line_id)]
                session.expunge_all()
        except Exception:
            log.exception("Failed to compute delivery risk")
            self._risk_status_label.setText("Could not compute delivery risk - see logs.")
            return

        self._risk_model_table.set_rows(paired)
        used_model = any(r.used_learned_model for _line, r in paired)
        if used_model:
            self._risk_status_label.setText(f"{len(paired)} open line(s) scored using the trained model + live status.")
        else:
            self._risk_status_label.setText(
                f"{len(paired)} open line(s) scored using live status only - "
                f"train the model once at least {MIN_TRAINING_SAMPLES} shipped orders exist."
            )

    def _retrain_model(self) -> None:
        try:
            with self._context.session_factory() as session:
                model = train_and_save(session)
        except Exception:
            log.exception("Delivery-risk model training failed")
            QMessageBox.critical(self, "Training Failed", "Could not train the model. See the logs for details.")
            return

        if model is None:
            QMessageBox.information(
                self,
                "Not Enough History",
                f"Fewer than {MIN_TRAINING_SAMPLES} shipped order lines exist yet - "
                "scoring will continue using live status only until there's more history to learn from.",
            )
        else:
            QMessageBox.information(
                self, "Model Trained", f"Trained on {model.trained_sample_count} historical shipped order line(s)."
            )
        self._refresh_risk()

    # -- Recurring Bottlenecks ---------------------------------------------

    def _build_bottleneck_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Operations ranked by historical average completion time."))
        toolbar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_bottlenecks)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        columns = [
            ColumnSpec("Operation", lambda b: b.operation_name),
            ColumnSpec("Times Completed", lambda b: b.completed_count, align_right=True),
            ColumnSpec("Avg Duration (days)", lambda b: b.average_duration_days, align_right=True),
            ColumnSpec("Max Duration (days)", lambda b: b.max_duration_days, align_right=True),
            ColumnSpec("Currently Stuck (5+ days)", lambda b: b.currently_stuck_count, align_right=True),
        ]
        self._bottleneck_table_model = ListTableModel(columns)
        table = QTableView()
        table.setModel(self._bottleneck_table_model)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        layout.addWidget(table, stretch=1)
        self._bottleneck_table = table

        self._refresh_bottlenecks()
        return page

    def _refresh_bottlenecks(self) -> None:
        try:
            with self._context.session_factory() as session:
                results = recurring_bottlenecks(session)
        except Exception:
            log.exception("Failed to compute recurring bottlenecks")
            return
        self._bottleneck_table_model.set_rows(results)

    # -- Smart Search -------------------------------------------------------

    def _build_search_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        hint = QLabel(
            'Try: "which purchase orders are overdue", "parts waiting for material", '
            '"customer orders likely to be late this month", "open follow-ups", "open rmas".'
        )
        hint.setObjectName("PageSubtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Ask a question…")
        self._search_box.returnPressed.connect(self._run_search)
        search_row.addWidget(self._search_box, stretch=1)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("PrimaryButton")
        search_btn.clicked.connect(self._run_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self._interpretation_label = QLabel("")
        self._interpretation_label.setObjectName("PageSubtitle")
        self._interpretation_label.setWordWrap(True)
        layout.addWidget(self._interpretation_label)

        self._search_results = QTextEdit()
        self._search_results.setReadOnly(True)
        layout.addWidget(self._search_results, stretch=1)

        return page

    def _run_search(self) -> None:
        text = self._search_box.text().strip()
        if not text:
            return
        try:
            with self._context.session_factory() as session:
                result = run_smart_search(session, text, self._context.settings, as_of=date.today())
                lines = [self._format_row(result.target, row) for row in result.rows[:200]]
        except Exception:
            log.exception("Smart search failed for query: %s", text)
            self._interpretation_label.setText("Could not run that search - see logs.")
            return

        self._interpretation_label.setText(f'Interpreted as: "{result.interpretation}" ({len(result.rows)} result(s))')
        self._search_results.setPlainText("\n".join(lines) if lines else "(no matches)")

    @staticmethod
    def _format_row(target: str, row) -> str:
        if target == "customer_order_lines":
            return f"CO {row.co_number} / {row.part_display} - {row.customer_name} - due {row.line.due_date} - {row.line.status}"
        if target == "purchase_order_lines":
            return f"PO {row.po_number} / {row.part_display} - {row.vendor_name} - {row.line.status}"
        if target == "rmas":
            return f"RMA {row.rma.rma_number} - {row.customer_name} - {row.aging_bucket} - {row.rma.status}"
        if target == "follow_ups":
            return f'"{row.subject}" - due {row.due_date} - {row.status}'
        return str(row)

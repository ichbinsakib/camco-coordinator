"""Analytics page: charts that each answer one operational question (spec rule 46)."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.repositories.analytics import (
    bottleneck_operations,
    monthly_order_trend,
    orders_by_status,
    past_due_trend,
    production_workload_by_department,
    rma_aging_distribution,
    vendor_performance,
)
from app.ui.app_context import AppContext
from app.ui.widgets.bar_chart import build_bar_chart

log = logging.getLogger(__name__)


class AnalyticsPage(QWidget):
    """A grid of charts, each backed by a single aggregate query."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self._context = context

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(8)

        header = QLabel("Analytics")
        header.setObjectName("PageTitle")
        root.addWidget(header)
        sub = QLabel("Operational trends across orders, production, purchasing, shipping and RMAs.")
        sub.setObjectName("PageSubtitle")
        root.addWidget(sub)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        root.addWidget(refresh_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._grid = QGridLayout(container)
        self._grid.setSpacing(16)
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        """Re-run every analytics query and rebuild the chart grid."""
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        try:
            with self._context.session_factory() as session:
                orders_data = orders_by_status(session)
                past_due_data = past_due_trend(session)
                production_data = production_workload_by_department(session)
                vendor_data = vendor_performance(session)
                rma_data = rma_aging_distribution(session, self._context.settings.rma)
                trend_data = monthly_order_trend(session)
                bottleneck_data = bottleneck_operations(session)
        except Exception:
            log.exception("Failed to load analytics data")
            self._grid.addWidget(QLabel("Could not load analytics data - see logs."), 0, 0)
            return

        charts = [
            ("Orders by Status", [d.label for d in orders_data], [d.count for d in orders_data], "#0F62FE"),
            ("Past Due Backlog by Age", [d.label for d in past_due_data], [d.count for d in past_due_data], "#B91C1C"),
            (
                "Production Workload by Department",
                [d.label for d in production_data],
                [d.count for d in production_data],
                "#0EA5E9",
            ),
            (
                "Vendor On-Time %",
                [v.vendor_name for v in vendor_data],
                [int(v.on_time_percent or 0) for v in vendor_data],
                "#059669",
            ),
            ("RMA Count by Age", [d.label for d in rma_data], [d.count for d in rma_data], "#DC2626"),
            ("Monthly Order Volume", [d.label for d in trend_data], [d.count for d in trend_data], "#7C3AED"),
            (
                "Top Bottleneck Operations",
                [d.label for d in bottleneck_data],
                [d.count for d in bottleneck_data],
                "#EA580C",
            ),
        ]

        for index, (title, labels, values, color) in enumerate(charts):
            chart_view = build_bar_chart(title, labels, values, bar_color=color)
            self._grid.addWidget(chart_view, index // 2, index % 2)

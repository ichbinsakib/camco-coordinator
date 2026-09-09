"""The coordinator dashboard: "what needs my attention today?" """

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.repositories.dashboard import get_dashboard_counts
from app.ui.app_context import AppContext
from app.ui.widgets.kpi_card import KpiCard

log = logging.getLogger(__name__)

_CARD_SPECS: list[tuple[str, str, str]] = [
    ("open_customer_orders", "Open CO Lines", "#0F62FE"),
    ("past_due", "Past Due", "#B91C1C"),
    ("due_today", "Due Today", "#EA580C"),
    ("due_this_week", "Due This Week", "#CA8A04"),
    ("late_purchase_orders", "Late Purchase Orders", "#B45309"),
    ("awaiting_material", "Awaiting Material", "#7C3AED"),
    ("open_rmas", "Open RMAs", "#DC2626"),
    ("open_follow_ups", "Open Follow-Ups", "#059669"),
]


class DashboardPage(QWidget):
    """Top-level KPI overview, refreshed from the database on demand."""

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self._context = context
        self._cards: dict[str, KpiCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(6)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        subtitle = QLabel(f"Welcome, {context.current_user.display_name} — here's what needs attention.")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(14)
        for index, (key, label, accent) in enumerate(_CARD_SPECS):
            card = KpiCard(label, accent)
            self._cards[key] = card
            grid.addWidget(card, index // 4, index % 4)
        root.addLayout(grid)

        self._status_label = QLabel("")
        self._status_label.setObjectName("PageSubtitle")
        root.addWidget(self._status_label)
        root.addStretch()

        self.refresh()

    def refresh(self) -> None:
        """Re-query the database and update every KPI card."""
        try:
            with self._context.session_factory() as session:
                counts = get_dashboard_counts(session)
        except Exception:
            log.exception("Failed to refresh dashboard counts")
            self._status_label.setText("Could not load dashboard data - see logs.")
            return

        for key, card in self._cards.items():
            card.set_value(getattr(counts, key))
        self._status_label.setText(f"Last updated {datetime.now().strftime('%I:%M:%S %p')}")

"""Main application window: sidebar navigation + stacked pages."""

from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME
from app.config.settings import SettingsManager
from app.ui.app_context import AppContext
from app.ui.dialogs.lock_screen_dialog import LockScreenDialog
from app.ui.idle_lock import IdleWatcher
from app.ui.pages.alerts_page import AlertsPage
from app.ui.pages.analytics_page import AnalyticsPage
from app.ui.pages.customer_orders_page import CustomerOrdersPage
from app.ui.pages.customers_page import CustomersPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.followups_page import FollowUpsPage
from app.ui.pages.parts_page import PartsPage
from app.ui.pages.placeholder_page import PlaceholderPage
from app.ui.pages.production_page import ProductionPage
from app.ui.pages.purchasing_page import PurchasingPage
from app.ui.pages.reports_page import ReportsPage
from app.ui.pages.rmas_page import RmasPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.shipping_page import ShippingPage
from app.ui.pages.vendors_page import VendorsPage

log = logging.getLogger(__name__)

#: (page key, sidebar label) in the order specified for the sidebar.
_NAV_ITEMS: list[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("customer_orders", "Customer Orders"),
    ("parts", "Parts"),
    ("production", "Production"),
    ("purchasing", "Purchasing"),
    ("shipping", "Shipping"),
    ("rmas", "RMAs"),
    ("followups", "Follow-Ups"),
    ("customers", "Customers"),
    ("vendors", "Vendors"),
    ("reports", "Reports"),
    ("analytics", "Analytics"),
    ("alerts", "Alerts"),
    ("search", "Search"),
    ("settings", "Settings"),
]


class MainWindow(QMainWindow):
    """Top-level window: title bar, sidebar, and the stack of pages."""

    def __init__(self, context: AppContext, settings_manager: SettingsManager) -> None:
        super().__init__()
        self._context = context
        self._settings_manager = settings_manager
        self.setWindowTitle(f"{APP_NAME} — {context.current_user.display_name}")
        self.resize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, stretch=1)
        self._page_index: dict[str, int] = {}
        self._build_pages()

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(
            f"Signed in as {context.current_user.display_name} ({context.current_user.role})"
        )

        self._restore_geometry()
        self._select_page(context.settings.ui.last_page or "dashboard")

        self._idle_watcher = IdleWatcher(context.settings.security.session_idle_minutes, parent=self)
        self._idle_watcher.locked.connect(self._show_lock_screen)
        self._idle_watcher.start()

    # -- construction -------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 12)
        layout.setSpacing(2)

        title = QLabel(APP_NAME)
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("Manufacturing Coordination")
        subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}

        for key, label in _NAV_ITEMS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, k=key: self._select_page(k))
            self._nav_group.addButton(button)
            self._nav_buttons[key] = button
            layout.addWidget(button)
            if key == "search":
                layout.addSpacing(8)

        layout.addStretch()
        return sidebar

    def _build_pages(self) -> None:
        self._add_page("dashboard", DashboardPage(self._context))
        self._add_page("customer_orders", CustomerOrdersPage(self._context))
        self._add_page("parts", PartsPage(self._context))
        self._add_page("production", ProductionPage(self._context))
        self._add_page("purchasing", PurchasingPage(self._context))
        self._add_page("shipping", ShippingPage(self._context))
        self._add_page("rmas", RmasPage(self._context))
        self._add_page("followups", FollowUpsPage(self._context))
        self._add_page("customers", CustomersPage(self._context))
        self._add_page("vendors", VendorsPage(self._context))
        self._add_page("reports", ReportsPage(self._context))
        self._add_page("analytics", AnalyticsPage(self._context))
        self._add_page("alerts", AlertsPage(self._context))
        self._add_page("search", self._placeholder("Search", "search"))
        self._add_page("settings", SettingsPage(self._settings_manager))

    def _placeholder(self, title: str, key: str) -> PlaceholderPage:
        note = (
            f"Global {title.lower()} across parts, orders, POs, RMAs and follow-ups is planned "
            "for a later phase of the CAMCO Coordinator roadmap (see docs/ROADMAP.md). "
            "Each module's own page already supports searching within it."
        )
        return PlaceholderPage(title, note)

    def _add_page(self, key: str, widget: QWidget) -> None:
        index = self._stack.addWidget(widget)
        self._page_index[key] = index

    # -- navigation -----------------------------------------------------

    def _select_page(self, key: str) -> None:
        index = self._page_index.get(key)
        if index is None:
            log.warning("Unknown page requested: %s", key)
            return
        self._stack.setCurrentIndex(index)
        button = self._nav_buttons.get(key)
        if button is not None:
            button.setChecked(True)
        self._context.settings.ui.last_page = key

    # -- idle lock ----------------------------------------------------------

    def _show_lock_screen(self) -> None:
        with self._context.session_factory() as session:
            dialog = LockScreenDialog(session, self._context.current_user.username, parent=self)
            dialog.exec()  # blocks - closeEvent/Escape are disabled, only a successful login accepts it
        self._idle_watcher.unlock()

    # -- window state -----------------------------------------------------

    def _restore_geometry(self) -> None:
        ui = self._context.settings.ui
        if ui.remember_window_geometry and ui.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(ui.window_geometry.encode("ascii")))

    def closeEvent(self, event) -> None:
        self._idle_watcher.stop()
        ui = self._context.settings.ui
        if ui.remember_window_geometry:
            ui.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        try:
            self._settings_manager.save(self._context.settings)
        except OSError:
            log.exception("Could not save settings on close")
        super().closeEvent(event)

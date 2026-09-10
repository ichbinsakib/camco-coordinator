"""pytest-qt regression test for the sidebar-label transparency bug.

Caught from a real screenshot: the global ``QWidget { background: ... }``
rule in app/ui/theme.py paints every widget's own background, including
labels sitting directly on the dark sidebar - without an explicit
``background: transparent`` for them, #SidebarTitle/#SidebarSubtitle each
rendered a light rectangle behind their (light-colored) text, making it
almost unreadable.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.config.constants import ThemeMode
from app.ui.theme import stylesheet


def _color_distance(a: QColor, b: QColor) -> float:
    return ((a.red() - b.red()) ** 2 + (a.green() - b.green()) ** 2 + (a.blue() - b.blue()) ** 2) ** 0.5


def _build_sidebar() -> tuple[QWidget, QLabel]:
    sidebar = QWidget()
    sidebar.setObjectName("Sidebar")
    layout = QVBoxLayout(sidebar)
    title = QLabel("CAMCO Coordinator")
    title.setObjectName("SidebarTitle")
    layout.addWidget(title)
    sidebar.resize(220, 80)
    return sidebar, title


def test_sidebar_title_background_matches_sidebar_not_the_page(qtbot) -> None:
    sidebar, title = _build_sidebar()
    qtbot.addWidget(sidebar)
    sidebar.setStyleSheet(stylesheet(ThemeMode.LIGHT.value))
    sidebar.show()
    qtbot.waitExposed(sidebar)

    pixmap = sidebar.grab()
    image = pixmap.toImage()

    # Sample a corner of the title label's rect - background, not glyph pixels.
    sample_point = title.mapTo(sidebar, title.rect().bottomRight()) - type(title.rect().bottomRight())(2, 2)
    sampled = QColor(image.pixel(sample_point))

    dark_sidebar_bg = QColor("#1C2733")  # _LIGHT["sidebar_bg"] in app/ui/theme.py
    light_page_bg = QColor("#F4F6F8")  # _LIGHT["bg"] in app/ui/theme.py

    assert _color_distance(sampled, dark_sidebar_bg) < _color_distance(sampled, light_page_bg), (
        f"SidebarTitle's background rendered as {sampled.name()}, closer to the light page "
        f"background {light_page_bg.name()} than the dark sidebar {dark_sidebar_bg.name()} - "
        "the label is painting its own light background instead of staying transparent."
    )

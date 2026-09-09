"""A single dashboard KPI tile."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class KpiCard(QFrame):
    """Clickable card showing a label and a count, coloured by severity."""

    clicked = Signal()

    def __init__(self, label: str, accent: str = "#0F62FE", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._value_label = QLabel("0")
        self._value_label.setObjectName("CardValue")
        self._value_label.setStyleSheet(f"color: {accent};")

        self._title_label = QLabel(label.upper())
        self._title_label.setObjectName("CardLabel")

        layout.addWidget(self._value_label)
        layout.addWidget(self._title_label)

    def set_value(self, value: int) -> None:
        """Update the displayed count."""
        self._value_label.setText(str(value))

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)

"""Placeholder for modules whose data grid/CRUD UI ships in a later phase.

The database schema and repositories for these modules already exist
(see ``app/models`` and ``app/repositories``) - only the table/detail UI is
pending, per the phased roadmap in ``docs/ROADMAP.md``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    """A named, titled stand-in page so every sidebar entry is navigable today."""

    def __init__(self, title: str, phase_note: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)

        note = QLabel(phase_note)
        note.setObjectName("PageSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

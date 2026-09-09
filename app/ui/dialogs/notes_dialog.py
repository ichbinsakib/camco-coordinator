"""Generic notes panel: view history and add a note for any entity.

One dialog, reused everywhere (spec rule 22: notes against Part, CO, SO, PO,
Customer, Vendor, RMA, Follow-Up) - entity-specific pages just pass their
``entity_type``/``entity_id`` rather than each rolling their own notes UI.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from app.models.audit import Note
from app.ui.app_context import AppContext


class NotesDialog(QDialog):
    """Chronological notes list for one entity, with an add-note box."""

    def __init__(self, context: AppContext, entity_type: str, entity_id: int, title: str, parent=None) -> None:
        super().__init__(parent)
        self._context = context
        self._entity_type = entity_type
        self._entity_id = entity_id
        self.setWindowTitle(f"Notes - {title}")
        self.setMinimumSize(480, 420)

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list, stretch=1)

        add_row = QHBoxLayout()
        self._new_note = QPlainTextEdit()
        self._new_note.setFixedHeight(60)
        self._new_note.setPlaceholderText("Add a note…")
        add_row.addWidget(self._new_note, stretch=1)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_note)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Reload notes for this entity, newest first."""
        self._list.clear()
        with self._context.session_factory() as session:
            notes = list(
                session.scalars(
                    select(Note)
                    .where(Note.entity_type == self._entity_type, Note.entity_id == self._entity_id)
                    .order_by(Note.created_at.desc())
                )
            )
            for note in notes:
                author = note.author.display_name if note.author else "Unknown"
                when = note.created_at.strftime("%m/%d/%Y %I:%M %p")
                item = QListWidgetItem(f"{when} - {author}\n{note.text}")
                self._list.addItem(item)
            if not notes:
                self._list.addItem(QListWidgetItem("No notes yet."))

    def _add_note(self) -> None:
        text = self._new_note.toPlainText().strip()
        if not text:
            return
        with self._context.session_factory() as session:
            session.add(
                Note(
                    entity_type=self._entity_type,
                    entity_id=self._entity_id,
                    author_id=self._context.current_user.id,
                    text=text,
                )
            )
            session.commit()
        self._new_note.clear()
        self.refresh()

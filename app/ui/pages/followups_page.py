"""Follow-Ups list page - the coordinator "who do I need to chase" worklist."""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QMessageBox
from sqlalchemy import select

from app.config.constants import EntityType, FollowUpStatus
from app.config.settings import get_settings
from app.models.core import Customer, Vendor
from app.models.followup import FollowUp
from app.repositories.followups import FollowUpFilters, FollowUpRepository
from app.services.activity_log_service import log_event, log_field_change
from app.ui.app_context import AppContext
from app.ui.dialogs.followup_dialog import FollowUpDialog
from app.ui.dialogs.notes_dialog import NotesDialog
from app.ui.widgets.list_page_base import ListPageBase
from app.ui.widgets.table_model import ColumnSpec

log = logging.getLogger(__name__)


def _overdue_label(follow_up: FollowUp) -> str:
    return "OVERDUE" if follow_up.is_overdue(date.today()) else ""


_COLUMNS = [
    ColumnSpec("Subject", lambda f: f.subject),
    ColumnSpec("Customer", lambda f: f.customer.name if f.customer else ""),
    ColumnSpec("Vendor", lambda f: f.vendor.name if f.vendor else ""),
    ColumnSpec("Department", lambda f: f.department),
    ColumnSpec("Priority", lambda f: f.priority, color=lambda f: get_settings().color_for(f.priority)),
    ColumnSpec("Due Date", lambda f: f.due_date),
    ColumnSpec("Overdue", _overdue_label, color=lambda f: "#B91C1C" if f.is_overdue(date.today()) else None),
    ColumnSpec("Status", lambda f: f.status),
]


class FollowUpsPage(ListPageBase):
    """Search/filter coordinator follow-ups."""

    def __init__(self, context: AppContext, parent=None) -> None:
        self._context = context
        super().__init__(
            "Follow-Ups",
            "Manual coordination tasks - who to contact, about what, and by when.",
            _COLUMNS,
            self._load,
            can_edit=context.current_user.can_edit,
            show_notes=True,
        )

        filter_bar = self.filter_bar_layout()
        filter_bar.addWidget(QLabel("Status:"))
        self._status_filter = QComboBox()
        self._status_filter.addItem("Open Only", "__open__")
        self._status_filter.addItem("All Statuses", None)
        for status in FollowUpStatus:
            self._status_filter.addItem(status.value, status.value)
        self._status_filter.currentIndexChanged.connect(self.refresh)
        filter_bar.addWidget(self._status_filter)

        self._overdue_only = QCheckBox("Overdue Only")
        self._overdue_only.stateChanged.connect(self.refresh)
        filter_bar.addWidget(self._overdue_only)

        self.on_new = self._new_followup
        self.on_edit = self._edit_followup
        self.on_activated = self._edit_followup
        self.on_notes = self._view_notes
        self.refresh()

    def _current_filters(self, text: str) -> FollowUpFilters:
        selection = self._status_filter.currentData()
        return FollowUpFilters(
            text=text,
            status=selection if selection not in (None, "__open__") else None,
            open_only=selection == "__open__",
            overdue_only=self._overdue_only.isChecked(),
        )

    def _load(self, text: str, limit: int, offset: int) -> tuple[list[FollowUp], int]:
        with self._context.session_factory() as session:
            repo = FollowUpRepository(session)
            rows, total = repo.search(self._current_filters(text), limit=limit, offset=offset)
            session.expunge_all()
            return rows, total

    def _view_notes(self, row: FollowUp) -> None:
        NotesDialog(self._context, EntityType.FOLLOW_UP.value, row.id, row.subject, parent=self).exec()

    def _new_followup(self) -> None:
        with self._context.session_factory() as session:
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            vendors = list(session.scalars(select(Vendor).order_by(Vendor.name)))
            dialog = FollowUpDialog(customers, vendors, parent=self)
            if dialog.exec() != FollowUpDialog.DialogCode.Accepted:
                return
            follow_up = FollowUp(subject="")
            dialog.apply_to(follow_up)
            session.add(follow_up)
            session.flush()
            log_event(
                session,
                entity_type="FOLLOW_UP",
                entity_id=follow_up.id,
                description=f'Follow-up "{follow_up.subject}" created',
                user_id=self._context.current_user.id,
            )
            session.commit()
        self.refresh()

    def _edit_followup(self, row: FollowUp) -> None:
        with self._context.session_factory() as session:
            follow_up = session.get(FollowUp, row.id)
            if follow_up is None:
                QMessageBox.warning(self, "Not Found", "This follow-up no longer exists.")
                self.refresh()
                return
            customers = list(session.scalars(select(Customer).order_by(Customer.name)))
            vendors = list(session.scalars(select(Vendor).order_by(Vendor.name)))
            before = {"status": follow_up.status, "due_date": follow_up.due_date}
            dialog = FollowUpDialog(customers, vendors, follow_up, parent=self)
            if dialog.exec() != FollowUpDialog.DialogCode.Accepted:
                return
            dialog.apply_to(follow_up)
            for field, old_value in before.items():
                log_field_change(
                    session,
                    entity_type="FOLLOW_UP",
                    entity_id=follow_up.id,
                    field_name=field,
                    old_value=old_value,
                    new_value=getattr(follow_up, field),
                    user_id=self._context.current_user.id,
                )
            session.commit()
        self.refresh()

"""Integration tests for the alert engine (app.alerts.engine.refresh_alerts)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.engine import refresh_alerts
from app.config.constants import AlertSeverity, AlertStatus, OrderStatus
from app.config.settings import AppSettings
from app.models.audit import Alert
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine


def _seed_late_line(session: Session, days_late: int = 10) -> CustomerOrderLine:
    customer = Customer(code="ACME", name="Acme Corp")
    part = Part(part_number="P1", revision="A")
    session.add_all([customer, part])
    session.flush()
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    session.add(order)
    session.flush()
    line = CustomerOrderLine(
        customer_order_id=order.id,
        line_number=1,
        part_id=part.id,
        quantity_ordered=10,
        due_date=date.today() - timedelta(days=days_late),
        status=OrderStatus.IN_PROGRESS.value,
    )
    session.add(line)
    session.commit()
    return line


def test_creates_alert_for_past_due_line(db_session: Session) -> None:
    _seed_late_line(db_session, days_late=10)
    settings = AppSettings()
    result = refresh_alerts(db_session, settings)
    assert result.created == 1

    alerts = list(db_session.scalars(select(Alert)))
    assert len(alerts) == 1
    assert alerts[0].rule_code == "ORDER_PAST_DUE"
    assert alerts[0].status == AlertStatus.NEW.value


def test_severity_escalates_past_critical_threshold(db_session: Session) -> None:
    settings = AppSettings()
    _seed_late_line(db_session, days_late=settings.alerts.critical_late_days + 5)
    refresh_alerts(db_session, settings)
    alert = db_session.scalars(select(Alert)).one()
    assert alert.severity == AlertSeverity.CRITICAL.value


def test_refresh_is_idempotent_no_duplicates(db_session: Session) -> None:
    _seed_late_line(db_session, days_late=10)
    settings = AppSettings()
    refresh_alerts(db_session, settings)
    result2 = refresh_alerts(db_session, settings)
    assert result2.created == 0
    assert len(list(db_session.scalars(select(Alert)))) == 1


def test_resolved_condition_auto_resolves_alert(db_session: Session) -> None:
    line = _seed_late_line(db_session, days_late=10)
    settings = AppSettings()
    refresh_alerts(db_session, settings)

    # Coordinator fixes the due date - the line is no longer late.
    line.due_date = date.today() + timedelta(days=10)
    db_session.commit()

    result = refresh_alerts(db_session, settings)
    assert result.resolved == 1
    alert = db_session.scalars(select(Alert)).one()
    assert alert.status == AlertStatus.RESOLVED.value
    assert alert.resolved_at is not None


def test_snoozed_alert_is_not_resurfaced_or_overwritten(db_session: Session) -> None:
    _seed_late_line(db_session, days_late=10)
    settings = AppSettings()
    refresh_alerts(db_session, settings)

    alert = db_session.scalars(select(Alert)).one()
    alert.status = AlertStatus.SNOOZED.value
    db_session.commit()

    result = refresh_alerts(db_session, settings)
    assert result.created == 0
    assert result.updated == 0
    refreshed = db_session.scalars(select(Alert)).one()
    assert refreshed.status == AlertStatus.SNOOZED.value


def test_disabled_alerts_produce_nothing(db_session: Session) -> None:
    _seed_late_line(db_session, days_late=10)
    settings = AppSettings()
    settings.alerts.enabled = False
    result = refresh_alerts(db_session, settings)
    assert result.candidates_evaluated == 0
    assert list(db_session.scalars(select(Alert))) == []


def test_material_shortage_alert_fires_for_waiting_material_status(db_session: Session) -> None:
    customer = Customer(code="ACME", name="Acme Corp")
    part = Part(part_number="P2", revision="A")
    db_session.add_all([customer, part])
    db_session.flush()
    order = CustomerOrder(co_number="CO-2", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=1, part_id=part.id,
            quantity_ordered=5, status=OrderStatus.WAITING_MATERIAL.value,
        )
    )
    db_session.commit()

    result = refresh_alerts(db_session, AppSettings())
    rule_codes = {a.rule_code for a in db_session.scalars(select(Alert))}
    assert "MATERIAL_SHORTAGE" in rule_codes
    assert result.created >= 1

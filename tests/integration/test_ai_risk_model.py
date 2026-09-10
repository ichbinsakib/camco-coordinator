"""Integration tests for app.ai.risk_model."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai.risk_model import (
    MIN_TRAINING_SAMPLES,
    build_training_examples,
    load_model,
    predict_risk,
    predict_risk_for_open_lines,
    train_and_save,
)
from app.config.constants import OrderStatus
from app.config.settings import AppSettings
from app.models.core import Customer, Part
from app.models.orders import CustomerOrder, CustomerOrderLine
from app.models.shipping import Shipment, ShipmentLine


def _seed_shipped_line(session: Session, index: int, *, days_late: int) -> None:
    """A closed, shipped order line - `days_late` > 0 means it shipped after its due date."""
    customer = Customer(code=f"C{index}", name=f"Customer {index}", importance=(index % 5) + 1)
    part = Part(part_number=f"P{index}", revision="A")
    session.add_all([customer, part])
    session.flush()
    order = CustomerOrder(co_number=f"CO-{index}", customer_id=customer.id)
    session.add(order)
    session.flush()
    due = date.today() - timedelta(days=60)
    line = CustomerOrderLine(
        customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10 + index,
        quantity_completed=10 + index, due_date=due, status=OrderStatus.SHIPPED.value,
    )
    session.add(line)
    session.flush()
    shipment = Shipment(shipment_number=f"SHP-{index}", ship_date=due + timedelta(days=days_late))
    session.add(shipment)
    session.flush()
    session.add(ShipmentLine(shipment_id=shipment.id, customer_order_line_id=line.id, quantity_shipped=10 + index))
    session.commit()


def test_build_training_examples_labels_late_and_on_time(db_session: Session) -> None:
    _seed_shipped_line(db_session, 1, days_late=5)  # late -> label 1
    _seed_shipped_line(db_session, 2, days_late=-3)  # early -> label 0

    examples = build_training_examples(db_session)
    labels = sorted(label for _features, label in examples)
    assert labels == [0, 1]


def test_lines_with_no_shipment_are_excluded_from_training(db_session: Session) -> None:
    customer = Customer(code="C1", name="Customer 1")
    part = Part(part_number="P1", revision="A")
    db_session.add_all([customer, part])
    db_session.flush()
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        CustomerOrderLine(
            customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=5,
            due_date=date.today(), status=OrderStatus.IN_PROGRESS.value,
        )
    )
    db_session.commit()

    assert build_training_examples(db_session) == []


def test_train_and_save_returns_none_below_minimum_samples(db_session: Session) -> None:
    for i in range(MIN_TRAINING_SAMPLES - 5):
        _seed_shipped_line(db_session, i, days_late=5 if i % 2 else -5)
    assert train_and_save(db_session) is None
    assert load_model() is None


def test_train_and_save_persists_a_loadable_model(db_session: Session) -> None:
    for i in range(MIN_TRAINING_SAMPLES + 5):
        _seed_shipped_line(db_session, i, days_late=5 if i % 2 else -5)

    model = train_and_save(db_session)
    assert model is not None
    assert model.trained_sample_count == MIN_TRAINING_SAMPLES + 5

    reloaded = load_model()
    assert reloaded is not None
    assert reloaded.feature_names == model.feature_names


def test_predict_risk_without_model_still_applies_rule_based_adjustments(db_session: Session) -> None:
    customer = Customer(code="C1", name="Customer 1", importance=1)
    part = Part(part_number="P1", revision="A")
    db_session.add_all([customer, part])
    db_session.flush()
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    line = CustomerOrderLine(
        customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10,
        due_date=date.today() - timedelta(days=5), status=OrderStatus.WAITING_MATERIAL.value,
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)

    result = predict_risk(line, None, db_session)
    assert result.used_learned_model is False
    assert result.base_probability is None
    assert result.score > 0
    assert any("material" in a.reason.lower() for a in result.adjustments)
    assert any("past due" in a.reason.lower() for a in result.adjustments)


def test_predict_risk_for_open_lines_excludes_closed_lines(db_session: Session) -> None:
    customer = Customer(code="C1", name="Customer 1")
    part = Part(part_number="P1", revision="A")
    db_session.add_all([customer, part])
    db_session.flush()
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add_all(
        [
            CustomerOrderLine(
                customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10,
                due_date=date.today(), status=OrderStatus.COMPLETE.value,
            ),
            CustomerOrderLine(
                customer_order_id=order.id, line_number=2, part_id=part.id, quantity_ordered=10,
                due_date=date.today(), status=OrderStatus.IN_PROGRESS.value,
            ),
        ]
    )
    db_session.commit()

    results = predict_risk_for_open_lines(db_session, AppSettings())
    assert len(results) == 1


def test_predict_risk_results_sorted_highest_first(db_session: Session) -> None:
    customer = Customer(code="C1", name="Customer 1")
    part = Part(part_number="P1", revision="A")
    db_session.add_all([customer, part])
    db_session.flush()
    order = CustomerOrder(co_number="CO-1", customer_id=customer.id)
    db_session.add(order)
    db_session.flush()
    db_session.add_all(
        [
            CustomerOrderLine(
                customer_order_id=order.id, line_number=1, part_id=part.id, quantity_ordered=10,
                due_date=date.today() + timedelta(days=30), status=OrderStatus.IN_PROGRESS.value,
            ),
            CustomerOrderLine(
                customer_order_id=order.id, line_number=2, part_id=part.id, quantity_ordered=10,
                due_date=date.today() - timedelta(days=20), status=OrderStatus.WAITING_MATERIAL.value,
            ),
        ]
    )
    db_session.commit()

    results = predict_risk_for_open_lines(db_session, AppSettings())
    assert results[0].score >= results[1].score

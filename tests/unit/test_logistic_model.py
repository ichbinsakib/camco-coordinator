"""Tests for the pure-Python logistic regression (app.ai.logistic_model)."""

from __future__ import annotations

from app.ai.logistic_model import LogisticModel, train_logistic_model

_FEATURES = ["x"]


def test_learns_a_clearly_separable_relationship() -> None:
    # label = 1 whenever x is large, 0 whenever x is small - trivially learnable.
    examples = [({"x": 0.0}, 0), ({"x": 1.0}, 0), ({"x": 2.0}, 0), ({"x": 8.0}, 1), ({"x": 9.0}, 1), ({"x": 10.0}, 1)]
    model = train_logistic_model(_FEATURES, examples, epochs=800)

    assert model.predict_proba({"x": 10.0}) > 0.7
    assert model.predict_proba({"x": 0.0}) < 0.3


def test_training_is_deterministic() -> None:
    examples = [({"x": 0.0}, 0), ({"x": 5.0}, 1), ({"x": 1.0}, 0), ({"x": 6.0}, 1)]
    model_a = train_logistic_model(_FEATURES, examples, epochs=200)
    model_b = train_logistic_model(_FEATURES, examples, epochs=200)
    assert model_a.weights == model_b.weights
    assert model_a.bias == model_b.bias


def test_missing_feature_defaults_to_zero_not_a_crash() -> None:
    model = train_logistic_model(_FEATURES, [({"x": 1.0}, 0), ({"x": 5.0}, 1)], epochs=50)
    # Predicting with an entirely different feature dict should not raise.
    result = model.predict_proba({"unrelated": 3.0})
    assert 0.0 <= result <= 1.0


def test_round_trip_through_dict() -> None:
    model = train_logistic_model(_FEATURES, [({"x": 1.0}, 0), ({"x": 5.0}, 1)], epochs=50)
    restored = LogisticModel.from_dict(model.to_dict())
    assert restored.predict_proba({"x": 5.0}) == model.predict_proba({"x": 5.0})
    assert restored.trained_sample_count == model.trained_sample_count


def test_constant_features_do_not_divide_by_zero() -> None:
    # Every example has the same x - std is 0, must not raise ZeroDivisionError.
    examples = [({"x": 3.0}, 0), ({"x": 3.0}, 1), ({"x": 3.0}, 0)]
    model = train_logistic_model(_FEATURES, examples, epochs=50)
    result = model.predict_proba({"x": 3.0})
    assert 0.0 <= result <= 1.0

"""A minimal, dependency-free logistic regression.

Deliberately pure Python (no numpy/scikit-learn): the feature count and
training-set sizes this app will ever train on on a coordinator's desktop
are small enough that a hand-rolled gradient-descent implementation is fast,
easy to unit-test deterministically, and doesn't add a multi-hundred-MB
dependency to the PyInstaller bundle for what is, underneath, ~40 lines of
math (rule 63: "do we really need this?" - here, no).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _sigmoid(z: float) -> float:
    # Clamp to avoid OverflowError on extreme inputs from unnormalized data.
    z = max(min(z, 35.0), -35.0)
    return 1.0 / (1.0 + math.exp(-z))


@dataclass(slots=True)
class LogisticModel:
    """A trained (or trainable) logistic regression over named features.

    Features are standardized (zero mean, unit variance) internally using
    statistics captured at training time, so prediction-time callers just
    pass raw feature values - they don't need to know the model normalizes.
    """

    feature_names: list[str]
    weights: list[float] = field(default_factory=list)
    bias: float = 0.0
    feature_means: list[float] = field(default_factory=list)
    feature_stds: list[float] = field(default_factory=list)
    trained_sample_count: int = 0

    def _standardize(self, features: list[float]) -> list[float]:
        return [
            (x - mean) / std if std > 1e-9 else 0.0
            for x, mean, std in zip(features, self.feature_means, self.feature_stds, strict=True)
        ]

    def predict_proba(self, features: dict[str, float]) -> float:
        """Predicted probability of the positive class (0.0-1.0)."""
        raw = [features.get(name, 0.0) for name in self.feature_names]
        standardized = self._standardize(raw)
        z = self.bias + sum(w * x for w, x in zip(self.weights, standardized, strict=True))
        return _sigmoid(z)

    def to_dict(self) -> dict:
        """Serialize to a plain-JSON-compatible dict."""
        return {
            "feature_names": self.feature_names,
            "weights": self.weights,
            "bias": self.bias,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
            "trained_sample_count": self.trained_sample_count,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> LogisticModel:
        return cls(
            feature_names=list(payload["feature_names"]),
            weights=list(payload["weights"]),
            bias=float(payload["bias"]),
            feature_means=list(payload["feature_means"]),
            feature_stds=list(payload["feature_stds"]),
            trained_sample_count=int(payload.get("trained_sample_count", 0)),
        )


def train_logistic_model(
    feature_names: list[str],
    examples: list[tuple[dict[str, float], int]],
    *,
    learning_rate: float = 0.5,
    epochs: int = 500,
    l2: float = 0.01,
) -> LogisticModel:
    """Train a logistic regression via batch gradient descent.

    ``examples`` is a list of ``(features, label)`` pairs, label in ``{0, 1}``.
    Deterministic given the same input - no random initialization, so this
    is exactly reproducible in tests.
    """
    n = len(examples)
    rows = [[feats.get(name, 0.0) for name in feature_names] for feats, _ in examples]
    labels = [label for _, label in examples]

    means = [sum(col) / n for col in zip(*rows, strict=True)] if n else [0.0] * len(feature_names)
    variances = (
        [sum((v - m) ** 2 for v in col) / n for col, m in zip(zip(*rows, strict=True), means, strict=True)]
        if n
        else [0.0] * len(feature_names)
    )
    stds = [math.sqrt(v) if v > 1e-9 else 1.0 for v in variances]

    standardized_rows = [[(x - m) / s for x, m, s in zip(row, means, stds, strict=True)] for row in rows]

    weights = [0.0] * len(feature_names)
    bias = 0.0

    for _ in range(epochs):
        grad_w = [0.0] * len(feature_names)
        grad_b = 0.0
        for row, label in zip(standardized_rows, labels, strict=True):
            z = bias + sum(w * x for w, x in zip(weights, row, strict=True))
            prediction = _sigmoid(z)
            error = prediction - label
            for i, x in enumerate(row):
                grad_w[i] += error * x
            grad_b += error

        weights = [
            w - learning_rate * (grad_w[i] / n + l2 * w) for i, w in enumerate(weights)
        ]
        bias -= learning_rate * (grad_b / n)

    return LogisticModel(
        feature_names=feature_names,
        weights=weights,
        bias=bias,
        feature_means=means,
        feature_stds=stds,
        trained_sample_count=n,
    )

"""Tests for app.utils.network_paths.is_network_path."""

from __future__ import annotations

from pathlib import Path

from app.utils.network_paths import is_network_path


def test_unc_path_is_detected() -> None:
    assert is_network_path(Path(r"\\SERVER\CAMCO\camco_coordinator.db")) is True


def test_unc_path_with_forward_slashes_is_detected() -> None:
    assert is_network_path(Path("//SERVER/CAMCO/camco_coordinator.db")) is True


def test_plain_local_path_is_not_network() -> None:
    assert is_network_path(Path("/tmp/camco_coordinator.db")) is False


def test_never_raises_on_a_relative_path() -> None:
    # Relative paths have no drive - must degrade to "not network", not crash.
    assert is_network_path(Path("data/camco_coordinator.db")) is False

"""Settings load/save round-trip and forward-compatibility behaviour."""

from __future__ import annotations

import json
from pathlib import Path

from app.config.settings import AppSettings, SettingsManager, settings_from_dict


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    manager = SettingsManager(tmp_path / "settings.json")
    settings = manager.load()
    settings.company.name = "Test Manufacturing"
    settings.alerts.due_soon_days = 9
    manager.save(settings)

    reloaded = SettingsManager(tmp_path / "settings.json").load()
    assert reloaded.company.name == "Test Manufacturing"
    assert reloaded.alerts.due_soon_days == 9


def test_missing_file_creates_defaults(tmp_path: Path) -> None:
    path = tmp_path / "does_not_exist.json"
    manager = SettingsManager(path)
    settings = manager.load()
    assert isinstance(settings, AppSettings)
    assert path.exists()


def test_unknown_keys_are_ignored_not_fatal() -> None:
    payload = json.loads(json.dumps({"company": {"name": "X", "totally_unknown_field": 123}}))
    settings = settings_from_dict(payload)
    assert settings.company.name == "X"


def test_partial_document_keeps_other_defaults() -> None:
    settings = settings_from_dict({"alerts": {"due_soon_days": 3}})
    assert settings.alerts.due_soon_days == 3
    assert settings.priority.critical_score == AppSettings().priority.critical_score


def test_corrupt_json_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not valid json", encoding="utf-8")
    manager = SettingsManager(path)
    settings = manager.load()
    assert isinstance(settings, AppSettings)

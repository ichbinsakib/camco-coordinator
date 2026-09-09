"""Tests for app.imports.readers: file parsing and coercion helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.imports.readers import coerce_date, coerce_float, read_sheet


def test_coerce_date_accepts_common_formats() -> None:
    assert coerce_date("09/15/2026") == date(2026, 9, 15)
    assert coerce_date("2026-09-15") == date(2026, 9, 15)
    assert coerce_date("09-15-2026") == date(2026, 9, 15)


def test_coerce_date_rejects_garbage() -> None:
    assert coerce_date("not a date") is None
    assert coerce_date(None) is None
    assert coerce_date("") is None


def test_coerce_date_passes_through_date_objects() -> None:
    d = date(2026, 1, 1)
    assert coerce_date(d) is d


def test_coerce_float_handles_thousands_separator() -> None:
    assert coerce_float("1,250.5") == 1250.5


def test_coerce_float_rejects_garbage() -> None:
    assert coerce_float("abc") is None
    assert coerce_float(None) is None


def test_read_csv_skips_blank_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("PN,Qty\nP1,10\n\nP2,20\n", encoding="utf-8")
    sheet = read_sheet(csv_path, "sample")
    assert sheet.headers == ["PN", "Qty"]
    assert len(sheet.rows) == 2
    assert sheet.rows[0] == {"PN": "P1", "Qty": "10"}


def test_read_csv_empty_file_returns_no_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")
    sheet = read_sheet(csv_path, "empty")
    assert sheet.headers == []
    assert sheet.rows == []

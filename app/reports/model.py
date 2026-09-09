"""Format-agnostic report data structures, shared by every exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ReportSection:
    """One table within a report: a heading, column headers, and rows."""

    title: str
    headers: list[str]
    rows: list[list[str]]
    note: str = ""


@dataclass(slots=True)
class Report:
    """A complete report: title, generation metadata, and one or more sections."""

    title: str
    generated_at: datetime
    generated_by: str
    sections: list[ReportSection] = field(default_factory=list)
    subtitle: str = ""

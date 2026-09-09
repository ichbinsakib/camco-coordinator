"""Export a :class:`Report` to CSV: one file per section.

CSV has no notion of multiple sheets, so a multi-section report becomes
several files named ``<base>_<section>.csv`` in the same folder - explicit
rather than silently dropping every section but the first.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from app.reports.model import Report


def _safe_filename_part(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "section"


def export_report_to_csv(report: Report, base_output_path: Path) -> list[Path]:
    """Write one CSV per section, alongside ``base_output_path``. Returns the paths written."""
    base_output_path.parent.mkdir(parents=True, exist_ok=True)
    stem = base_output_path.with_suffix("")
    written: list[Path] = []

    sections = report.sections or [None]
    for section in sections:
        if section is None or len(report.sections) == 1:
            path = stem.with_suffix(".csv")
        else:
            path = stem.parent / f"{stem.name}_{_safe_filename_part(section.title)}.csv"

        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([report.title])
            writer.writerow([report.subtitle or f"Generated {report.generated_at:%m/%d/%Y %I:%M %p} by {report.generated_by}"])
            if section is not None:
                writer.writerow([])
                writer.writerow(section.headers)
                writer.writerows(section.rows)
        written.append(path)

    return written

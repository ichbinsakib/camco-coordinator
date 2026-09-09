"""Export a :class:`Report` to a PDF, one table per section."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports.model import Report

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("ReportTitle", parent=_STYLES["Title"], fontSize=18)
_SUBTITLE_STYLE = ParagraphStyle("ReportSubtitle", parent=_STYLES["Normal"], textColor=colors.HexColor("#5B6675"))
_SECTION_STYLE = ParagraphStyle("SectionTitle", parent=_STYLES["Heading2"], spaceBefore=14)
_EMPTY_STYLE = ParagraphStyle("EmptyNote", parent=_STYLES["Italic"])


def export_report_to_pdf(report: Report, output_path: Path) -> Path:
    """Write ``report`` to a PDF file at ``output_path``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path), pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
    )

    story = [Paragraph(report.title, _TITLE_STYLE)]
    subtitle = report.subtitle or f"Generated {report.generated_at:%m/%d/%Y %I:%M %p} by {report.generated_by}"
    story.append(Paragraph(subtitle, _SUBTITLE_STYLE))
    story.append(Spacer(1, 0.15 * inch))

    for index, section in enumerate(report.sections):
        block = [Paragraph(section.title, _SECTION_STYLE)]
        if not section.rows:
            block.append(Paragraph("(no records)", _EMPTY_STYLE))
        else:
            table_data = [section.headers, *section.rows]
            table = Table(table_data, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1C2733")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDE3EA")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            block.append(table)
        story.append(KeepTogether(block))
        if index < len(report.sections) - 1:
            story.append(Spacer(1, 0.2 * inch))

    if not report.sections:
        story.append(Paragraph("(no data)", _EMPTY_STYLE))

    doc.build(story)
    return output_path

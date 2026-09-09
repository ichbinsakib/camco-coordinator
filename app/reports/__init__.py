"""Report generation: data builders plus Excel/PDF export.

Builders (in :mod:`app.reports.builders`) return a format-agnostic
:class:`Report` - the same data structure feeds both the Excel and PDF
exporters, so a new report type never has to be implemented twice.
"""

"""A small helper to build one bar-chart widget from (label, count) pairs.

Every analytics chart on the Analytics page is built with this one function
- one look-and-feel, one place to fix if QtCharts theming needs to change
(rule 36: DRY).
"""

from __future__ import annotations

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter


def build_bar_chart(title: str, labels: list[str], values: list[int], *, bar_color: str = "#0F62FE") -> QChartView:
    """Return a QChartView showing a single-series bar chart."""
    bar_set = QBarSet(title)
    bar_set.append(values or [0])
    bar_set.setColor(bar_color)

    series = QBarSeries()
    series.append(bar_set)

    chart = QChart()
    chart.addSeries(series)
    chart.setTitle(title)
    chart.legend().setVisible(False)
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
    chart.setBackgroundVisible(False)

    axis_x = QBarCategoryAxis()
    axis_x.append(labels or ["(no data)"])
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    max_value = max(values, default=0)
    axis_y.setRange(0, max(max_value, 1))
    axis_y.setLabelFormat("%d")
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(260)
    return view

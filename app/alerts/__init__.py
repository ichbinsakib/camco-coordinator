"""The automatic alert engine: turns business-rule violations into Alert rows.

Rules live in :mod:`app.alerts.rules` as pure functions over already-loaded
data (same spirit as `app.business`); :mod:`app.alerts.engine` is the only
place that reconciles those candidates against the `alerts` table.
"""

"""Business rules: priority scoring, status derivation, alert conditions.

Everything here is a pure function of data + :class:`app.config.settings.AppSettings`
- no database session, no Qt import - so the rules are trivially unit-testable
and cannot end up duplicated inside UI code (rule 10).
"""

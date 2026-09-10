"""Tests for app.database.session._sqlite_journal_mode.

Picking the wrong journal mode for a database on a network share is a real
data-integrity risk (SQLite's own docs warn WAL isn't safe there) - this is
the one function that decision hinges on, so it's tested directly.
"""

from __future__ import annotations

from app.database.session import _sqlite_journal_mode


def test_local_path_uses_wal() -> None:
    assert _sqlite_journal_mode("sqlite:///C:/Users/someone/camco_coordinator.db") == "WAL"


def test_in_memory_uses_wal() -> None:
    assert _sqlite_journal_mode("sqlite:///:memory:") == "WAL"


def test_unc_path_uses_delete_not_wal() -> None:
    # Matches what _sqlite_url() actually produces for a UNC Path via
    # as_posix(): "sqlite:///" (the URL prefix) + "//SERVER/..." (the UNC
    # path's own leading double-slash) = 5 slashes total after "sqlite:".
    assert _sqlite_journal_mode("sqlite://///SERVER/CAMCO/camco_coordinator.db") == "DELETE"

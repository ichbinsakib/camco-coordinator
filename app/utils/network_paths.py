"""Detects whether a filesystem path points at a network location.

Used by ``app/database/session.py`` to pick a SQLite journal mode that's
actually safe over a network share (spec section 55/rule 30's data-integrity
concerns, applied to the "shared database on a network drive" deployment
option): WAL mode relies on shared-memory primitives most network
filesystems (SMB in particular) don't implement safely, and SQLite's own
documentation warns against it for exactly this reason.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def is_network_path(path: Path) -> bool:
    """Best-effort check: is ``path`` a UNC path or a mapped network drive?

    UNC paths (``\\\\server\\share\\...``) are detected reliably from the
    path string alone. A mapped drive letter (``Z:\\...``) looks identical to
    a local drive from the path alone, so on Windows this also asks the OS
    via ``WNetGetConnectionW`` whether that drive letter is actually a
    network mapping. Never raises - any failure (non-Windows, no such API,
    an unmapped/local drive) is treated as "not a network path", the safer
    default for local development and for platforms this check doesn't
    apply to.
    """
    resolved = str(path)
    if resolved.startswith("\\\\") or resolved.startswith("//"):
        return True

    if sys.platform != "win32":
        return False

    drive = path.drive  # e.g. "Z:" for "Z:\\some\\path"
    if not drive:
        return False

    try:
        mpr = ctypes.windll.mpr  # type: ignore[attr-defined]
        buffer = ctypes.create_unicode_buffer(260)
        length = ctypes.c_ulong(260)
        # WNetGetConnectionW returns NO_ERROR (0) only for a genuinely mapped
        # network drive; any other result means "not a network mapping" as
        # far as this check is concerned.
        result = mpr.WNetGetConnectionW(drive + "\\", buffer, ctypes.byref(length))
        return result == 0
    except (AttributeError, OSError):
        log.debug("Could not query WNetGetConnectionW for drive %s; assuming local", drive)
        return False

"""Build the Windows executable with PyInstaller.

Usage:
    python scripts/build_exe.py

Produces ``dist/CAMCO_Coordinator/CAMCO_Coordinator.exe`` (one-folder build,
which starts faster than one-file and is easier to diagnose in the field).
Run this from an activated virtualenv that has ``requirements-dev.txt``
installed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    for stale in ("build", "dist"):
        stale_path = ROOT / stale
        if stale_path.exists():
            shutil.rmtree(stale_path)

    spec_file = ROOT / "packaging" / "camco_coordinator.spec"
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print("PyInstaller build failed.", file=sys.stderr)
        return result.returncode

    exe_path = ROOT / "dist" / "CAMCO_Coordinator" / "CAMCO_Coordinator.exe"
    if exe_path.exists():
        print(f"Build succeeded: {exe_path}")
    else:
        print("Build finished but the expected .exe was not found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

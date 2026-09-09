# PyInstaller spec for CAMCO Coordinator.
#
# One-folder build (not --onefile): faster startup, and a stray DLL/asset
# issue in the field is far easier to diagnose than inside a single-file
# archive. Inno Setup (see packaging/inno_setup.iss) wraps this folder into
# a normal Windows installer for distribution.

# pyright: reportUndefinedVariable=false
# ruff: noqa
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "app" / "ui" / "resources"), "resources"),
    ],
    hiddenimports=[
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CAMCO_Coordinator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="CAMCO_Coordinator",
)

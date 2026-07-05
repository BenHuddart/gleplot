# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the gleplot GUI editor.
#
# Layout: onedir (a directory bundle) on all platforms, wrapped in a macOS
# .app BUNDLE on Darwin. Windows CI feeds the resulting dist/gleplot directory
# to Inno Setup (packaging/windows/gleplot.iss); macOS CI wraps dist/gleplot.app
# into a .dmg (packaging/macos/dmg_settings.py).
#
# The icon path is supplied by CI via the PYI_ICON_PATH environment variable
# (.ico on Windows, .icns on macOS, generated from
# src/gleplot/gui/assets/gleplot.png). If unset or missing we fall back to no
# icon rather than failing the build.
#
# NOTE: gleplot's GUI shells out to an EXTERNAL `gle` binary at runtime. GLE is
# NOT bundled here; it is a runtime prerequisite the user installs separately.

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


# SPECPATH is the directory containing this spec file (packaging/), so the
# project root is its parent.
project_root = Path(SPECPATH).resolve().parent
src_root = project_root / "src"
entry_script = src_root / "gleplot" / "gui" / "app.py"

# Icon is generated per-platform by CI from src/gleplot/gui/assets/gleplot.png.
icon_path = os.environ.get("PYI_ICON_PATH")
if icon_path and not Path(icon_path).is_file():
    icon_path = None

# Bundle the package's own dist-info so importlib.metadata can read the version
# from inside the frozen app (gleplot reports its own version at runtime).
datas = copy_metadata("gleplot")

# Bundle the window-icon PNG so app.py can set the window icon at runtime via
# importlib.resources on the gleplot.gui package.
icon_png = src_root / "gleplot" / "gui" / "assets" / "gleplot.png"
if icon_png.is_file():
    datas += [(str(icon_png), "gleplot/gui/assets")]

# PySide6 has a bundled PyInstaller hook that collects the Qt runtime, so we do
# not manually collect its submodules. numpy is likewise picked up by static
# analysis of the imports in gleplot's core. Keep the spec minimal.
hiddenimports: list[str] = []

# Exclude heavy modules gleplot never imports. matplotlib appears only in
# comments/docstrings and marker-name strings (see gleplot.markers /
# gleplot.axes) — there is no `import matplotlib`, so excluding it is safe.
excludes = [
    "tkinter",
    "pytest",
    "matplotlib",
    "IPython",
    "notebook",
    "sphinx",
]

a = Analysis(
    [str(entry_script)],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="gleplot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="gleplot",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="gleplot.app",
        icon=icon_path if icon_path and icon_path.endswith(".icns") else None,
        bundle_identifier="io.github.benhuddart.gleplot",
    )

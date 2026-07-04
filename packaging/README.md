# Packaging gleplot

This directory holds the artifacts for building the **gleplot** GUI editor into
distributable desktop bundles:

| File | Purpose |
| --- | --- |
| `gleplot.spec` | PyInstaller spec — onedir bundle (all platforms) + macOS `.app` |
| `windows/gleplot.iss` | Inno Setup 6 script producing the Windows installer |
| `macos/dmg_settings.py` | `dmgbuild` settings for the macOS `.dmg` |
| `macos_icon.py` | Generates `.icns` / `.ico` from the source PNG logo (Pillow) |
| `../scripts/build_dmg_background.py` | Generates the DMG background PNG (Pillow) |

> **Runtime prerequisite (not bundled):** gleplot's GUI shells out to an
> external `gle` binary at runtime. GLE is **not** bundled in these packages —
> end users must install [GLE](https://glx.sourceforge.io/) separately and have
> `gle` on their `PATH`.

The source icon asset is `src/gleplot/gui/assets/gleplot.png` (a square PNG).
CI generates the platform icon formats from it; the spec reads the resulting
icon via the `PYI_ICON_PATH` environment variable and falls back to no icon if
unset/missing.

## Windows

```powershell
# 1. Install build dependencies (from the repo root)
pip install -e ".[gui]" pyinstaller Pillow

# 2. Generate the .ico from the source PNG
python packaging/macos_icon.py --ico build/icons/gleplot.ico

# 3. Build the onedir bundle -> dist/gleplot/
$env:PYI_ICON_PATH = "build/icons/gleplot.ico"
pyinstaller --clean --noconfirm packaging/gleplot.spec

# 4. (optional) Verify the frozen app constructs its main window headlessly
dist/gleplot/gleplot.exe --smoke-test   # exits 0 on success

# 5. Build the installer with Inno Setup 6 (iscc on PATH)
iscc /DAppVersion=1.2.0 `
     /DAppDir=dist\gleplot `
     /DIconFile=build\icons\gleplot.ico `
     /DOutputDir=dist `
     packaging/windows/gleplot.iss
```

This produces `dist\gleplot-1.2.0-windows-x64.exe`. Override the installer
base name with `/DOutputName=<name>`.

## macOS (arm64)

```bash
# 1. Install build dependencies
pip install -e ".[gui]" pyinstaller Pillow dmgbuild

# 2. Generate the .icns from the source PNG
python packaging/macos_icon.py --icns build/icons/gleplot.icns

# 3. Build the .app bundle -> dist/gleplot.app
export PYI_ICON_PATH="build/icons/gleplot.icns"
pyinstaller --clean --noconfirm packaging/gleplot.spec

# 4. (optional) Smoke-test the bundle headlessly
dist/gleplot.app/Contents/MacOS/gleplot --smoke-test   # exits 0 on success

# 5. Generate the DMG background image
python scripts/build_dmg_background.py --output build/dmg/background.png

# 6. Build the .dmg
export GLEPLOT_APP_BUNDLE="$PWD/dist/gleplot.app"
export GLEPLOT_DMG_BACKGROUND="$PWD/build/dmg/background.png"
dmgbuild -s packaging/macos/dmg_settings.py gleplot dist/gleplot-1.2.0-macos-arm64.dmg
```

## Environment variables

| Variable | Read by | Meaning |
| --- | --- | --- |
| `PYI_ICON_PATH` | `gleplot.spec` | Path to `.ico` (Windows) / `.icns` (macOS). Falls back to no icon if unset/missing. |
| `GLEPLOT_APP_BUNDLE` | `macos/dmg_settings.py` | Absolute path to `dist/gleplot.app`. |
| `GLEPLOT_DMG_BACKGROUND` | `macos/dmg_settings.py` | Absolute path to the DMG background PNG. |

Inno Setup build variables are passed via `/D` on the `iscc` command line:
`AppVersion`, `AppDir`, `IconFile`, `OutputDir`, and optional `OutputName`.

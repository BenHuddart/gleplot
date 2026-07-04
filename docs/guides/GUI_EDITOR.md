# GUI Editor Guide

gleplot includes a desktop editor -- built on PySide6 -- for building figures interactively: load data, map columns to series, style everything from dockable property panels, arrange subplots, and export, all with a live preview that recompiles as you edit.

## Overview

The editor window (`MainWindow`) has:

- A central **live preview** showing the figure rendered to PNG via GLE, debounced so rapid edits don't trigger a compile per keystroke.
- A **Data** dock for loading delimited data files and creating series from their columns.
- A **Properties** dock with **Layout**, **Figure**, **Axes**, and **Series** tabs.
- An **Output** dock listing structured compile errors (with line/column when GLE reports them), plus the raw compiler output.
- A permanent **status bar** label showing whether GLE was detected, and where.

It supports two modes:

- **Document mode** -- the normal editable workflow, backed by a `.glep` project (or a fresh, unsaved figure).
- **GLE-preview mode** -- a read-only view of a hand-written `.gle` script opened via File ▸ Open, described [below](#opening-hand-written-gle-files).

## Installation

```bash
pip install "gleplot[gui]"
```

This installs `PySide6>=6.5` in addition to gleplot's core dependencies. The base `gleplot` package (`import gleplot`) has no Qt dependency -- only the `gleplot.gui` subpackage does, so scripts that just generate GLE output are unaffected.

You'll also need GLE itself installed and discoverable for the live preview and for exporting anything other than a raw `.gle` script -- see [GLE discovery](#gle-discovery) below and the main [README installation instructions](../../README.md#installation).

## Launching

```bash
gleplot-gui
```

This is a console-script entry point (`gleplot.gui.app:main`) that creates a `QApplication`, shows the main window, and runs the Qt event loop. The window opens with an empty preview and the placeholder message "Nothing to render yet -- load data and add a series" until a figure has at least one series.

## Walkthrough

This walks through the same steps as `examples/gui/`, which ships a ready-to-open project (`damped_oscillation.glep`) and its source data (`damped_oscillation.csv`) if you'd rather skip straight to a finished example.

### 1. Load a data file

In the **Data** dock, click **Load data file...** and choose a `.csv`, `.dat`, or `.txt` file. The loader:

- sniffs the delimiter (comma, tab, semicolon, or whitespace);
- skips comment lines (`#` or `!`);
- detects a header row automatically (present if any field in the first row isn't a plain number);
- treats `*`, `?`, `-`, `.`, empty fields, and `nan`/`NaN` as missing values (`NaN` in the loaded arrays);
- shows up to 100 rows in the preview table.

Loaded files stay listed so you can switch between them or load several.

### 2. Pick columns and add a series

With a file selected, the "Add series" form fills its X/Y/Y-error column combos with the file's *numeric* columns. Choose:

- **X column** / **Y column** -- required.
- **Y error** -- optional, only used for the "Error bars" plot type.
- **Label** -- defaults to the Y column's name; edit it and the default stops auto-updating.
- **Plot type** -- Line, Scatter, Line+markers, or Error bars.
- **Mode** -- **Import data** copies the selected columns into the figure (they become `.dat` sidecars on export); **Reference file** instead points the GLE script at the original file by column index (via `Axes.line_from_file` / `Axes.errorbar_from_file`), so no data is duplicated. Note: reference mode's "Scatter" plot type currently falls back to a plain line -- markers on a referenced series aren't supported yet; use Import mode for a true scatter.

Click **Add series**. It's added to the figure's current axes and the live preview recompiles.

### 3. Style the series

Switch to the **Properties** dock's **Series** tab, which lists every series on the current axes. Select one to edit its color, marker, linestyle, and line width (control availability depends on the series kind -- e.g. bar charts only expose color, since GLE only supports one color per bar chart, and scatter series have no linestyle/linewidth).

The **Axes** tab covers axis labels, title, limits, scale (linear/log), and legend placement. The **Figure** tab covers figure-level settings (size, DPI).

### 4. Arrange subplots

The **Layout** tab shows the current subplot grid (rows x cols) and a list of grid slots. To add more panels: increase Rows/Cols and click **Apply grid**, then select an empty slot and click **Add axes here**. Selecting an existing (populated) slot retargets the Axes/Series tabs onto that subplot without marking the document dirty (it's a view change only).

The same tab has **Share X** / **Share Y** checkboxes (mirroring `figure.sharex`/`sharey`) and per-margin **Spacing** controls (`left`/`right`/`bottom`/`top`/`wspace`/`hspace`, matching `subplots_adjust`) -- each margin is an independent optional override; leaving its checkbox unchecked falls back to GLE's default.

Shrinking the grid or reshaping it (e.g. 2x3 to 3x2) refuses to relocate a populated axes off the new grid -- you'll see an inline error asking you to clear that axes' content first. Empty axes are dropped or reflowed silently.

### 5. Save the project

**File ▸ Save** (Ctrl+S) writes a `.glep` project file, prompting for a location the first time (or use **File ▸ Save As...**, Ctrl+Shift+S). Saved and recently-opened projects appear under **File ▸ Open Recent**.

### 6. Export

**File ▸ Export...** (Ctrl+E) opens the export dialog: choose a destination path, format (pdf/png/eps/svg/jpg/gle), DPI (raster formats only), and optionally "Export as folder bundle" to write a `<name>.gleplot/` folder containing the script, compiled output, and any data files together. Export always works from an immediate snapshot of the figure (`to_dict()` / `from_dict()`), never the live in-editing object, so it can't be affected by incidental edit order. On success the status bar shows "Exported \<path\>".

## The `.glep` project format

A `.glep` file is plain UTF-8 JSON (`indent=2`, stable key order) produced by `Figure.to_dict()` and written with `gleplot.project.save_project`; `gleplot.project.load_project` reverses it via `Figure.from_dict()`. The extension is a convention, not enforced.

The payload carries a `"version"` field (currently `1`) plus a `"gleplot_version"` field recording which gleplot release wrote it. Loading checks `version` against the build's supported version and raises a clear `ValueError` on a mismatch rather than guessing; unknown/extra keys within an otherwise-valid payload are tolerated so older projects stay loadable across minor releases. This is the same lossless snapshot format the editor's undo/redo history uses internally, so a project file always reflects exactly what File ▸ Save wrote.

## Opening hand-written `.gle` files

**File ▸ Open** accepts either a `.glep` project or a `.gle` script (the file-type filter offers both). Choosing a `.gle` file enters **GLE-preview mode**:

- The script is compiled once (synchronously, under a wait cursor) and shown read-only; the Data and Properties docks are disabled.
- The window title shows `<file.gle> (preview)` and the status bar explains you're in a read-only preview.
- **File ▸ Export** still works -- it recompiles the same script to whatever format/location you choose via a Save dialog -- but Save/Save As and Undo/Redo are disabled, since there's no editable `Figure` behind a hand-written script.
- **File ▸ New** (or opening a `.glep`/another file) leaves preview mode and returns to normal document editing.
- Compile failures still enter preview mode (so you can read the errors in the Output dock); the preview area shows a "could not compile" placeholder instead of an image.

## Undo/redo

Every in-place figure mutation (adding a series, editing a label, changing a limit, reshaping the grid, ...) is recorded as a full JSON snapshot (`Figure.to_dict()`), not as a list of reversible commands. Undo/redo simply moves a cursor through that snapshot history and rebuilds the figure via `Figure.from_dict()`.

Practical implications:

- The history is capped (50 snapshots by default); once exceeded, the oldest entries -- including the very first ("baseline") state -- are evicted, so very long sessions eventually lose the ability to undo all the way back to the start.
- **File ▸ New** and **File ▸ Open** each reset the history entirely -- undo cannot reach across a New/Open boundary.
- Undo/redo are disabled while in GLE-preview mode.
- Undoing back to exactly the last-saved position leaves the document marked clean (no `*` in the title); undoing to any other position re-dirties it, even if it happens to match the save some other way.

## GLE discovery

The editor locates the GLE executable the same way the core library does (`gleplot.compiler.find_gle`), in this order:

1. The **`GLE_PATH`** environment variable, if set and pointing at an existing path (a warning is emitted and discovery falls through if it's set but invalid).
2. `PATH` (via `shutil.which("gle")`, respecting `PATHEXT` on Windows).
3. A short list of well-known per-platform install locations.

The main window's status bar always shows the result as a permanent widget: `GLE: <path>` or `GLE: not found`. The same status also appears in **Help ▸ About**. Detection failures never crash the GUI -- an unexpected exception during discovery degrades to "not found" rather than propagating.

## Troubleshooting

### GLE not found

If the status bar reads "GLE: not found", the live preview and any export other than the raw `.gle` script will fail. Install GLE (see the [README](../../README.md#installation)) and either put it on `PATH` or set `GLE_PATH` to the executable, then restart the editor.

### Compile errors

When a render or export fails, structured errors appear in the **Output** dock as one line per error, in the form `line L, col C: message` (or just `line L: message` / `message` when GLE didn't report a column or line). Toggle **Show details** in the Output dock to see the compiler's raw stdout/stderr. The live preview keeps showing the last successful render underneath a failed compile, so a typo doesn't blank the canvas.

## Current limitations

- **Single figure per window.** There is one document per `MainWindow`; open a second window (a new `gleplot-gui` process) to work on two figures side by side.
- **Bar chart color.** Inherited from GLE itself: a `bar` series stores one color for the whole chart (`Axes.bar` only honors the first color if given a list), so per-bar colors aren't available in the Series panel either.
- **Live preview and most exports require GLE installed.** Only the `.gle`-script export format works without a working GLE installation.
- **Export runs synchronously** on the GUI thread (the live preview render does not -- it's async and debounced) -- large figures or a slow GLE install will briefly block the UI during File ▸ Export.
- **Reference-mode scatter series** fall back to a plain line (no per-point markers) since `line_from_file` doesn't support markers; use Import mode for true scatter plots.

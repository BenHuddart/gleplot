# GUI Editor Guide

gleplot includes a desktop editor -- built on PySide6 -- for building figures interactively: load data, map columns to series, style everything from dockable property panels, arrange subplots, and export, all with a live preview that recompiles as you edit.

## Overview

The editor window (`MainWindow`) has:

- A central **live preview** showing the figure rendered to PNG via GLE, debounced so rapid edits don't trigger a compile per keystroke.
- A **Data** dock for loading delimited data files and creating series from their columns.
- A **Properties** dock with **Layout**, **Figure**, **Axes**, and **Series** tabs.
- An **Output** dock listing structured compile errors (with line/column when GLE reports them) and any recovery warnings from opening a `.gle`, plus the raw compiler output.
- A permanent **status bar** label showing whether GLE was detected, and where.

It supports two modes:

- **Document mode** -- the normal editable workflow, backed by a native `.gle` file (or a fresh, unsaved figure).
- **GLE-preview mode** -- a read-only fallback for a `.gle` that uses GLE programming constructs (or one that can't be recognized as an editable figure), described [below](#opening-gle-files).

## Installation

There are two ways to get the editor: a **prebuilt desktop app** (no Python needed) or **`pip install`** into a Python environment. Either way, GLE itself is a separate prerequisite for live preview and compiled export -- see [Requirements / GLE prerequisite](#requirements--gle-prerequisite).

### Option A: prebuilt desktop app

Recommended for non-Python users. Download an installer for your platform from the project's [GitHub Releases](https://github.com/benhuddart/gleplot/releases):

- **Windows** -- the `.exe` installer.
- **macOS (Apple silicon / arm64)** -- the `.dmg`.

Then install GLE 4.3+ separately from the [GLE releases page](https://github.com/vlabella/GLE/releases/latest) so the editor can render previews and export compiled formats.

> **macOS Gatekeeper note.** The macOS app is currently **unsigned**, so the first launch is blocked by Gatekeeper. Either **right-click the app → Open** (then confirm) the first time, or clear the quarantine flag from a terminal:
>
> ```bash
> xattr -dr com.apple.quarantine /Applications/gleplot.app
> ```

### Option B: from pip

```bash
pip install "gleplot[gui]"
gleplot-gui
```

This installs `PySide6>=6.5` in addition to gleplot's core dependencies. The base `gleplot` package (`import gleplot`) has no Qt dependency -- only the `gleplot.gui` subpackage does, so scripts that just generate GLE output are unaffected.

You'll also need GLE itself installed and discoverable for the live preview and for exporting anything other than a raw `.gle` script -- see [Requirements / GLE prerequisite](#requirements--gle-prerequisite) below.

## Requirements / GLE prerequisite

The editor needs **GLE 4.3 or newer** for its two compiled features: the **live preview** (which compiles your figure to PNG) and **exporting** anything other than a raw `.gle` script (PDF/PNG/EPS/SVG/JPG). GLE is a separate program -- install it from the [GLE releases page](https://github.com/vlabella/GLE/releases/latest) and make it discoverable: point the editor at it via **Tools ▸ GLE Setup…**, put it on your `PATH`, or set the `GLE_PATH` environment variable to the executable (see [GLE discovery](#gle-discovery) for the exact search order).

The **status bar** shows the detected GLE path (`GLE: <path>`) or `GLE: not found` if the editor couldn't locate it; the same status also appears in **Help ▸ About**.

Without GLE installed, the editor still runs and **object-model editing still works** -- you can load data, add and style series, arrange subplots, and Save/Open native `.gle` files. Only the **live preview** and **compiled exports** are unavailable; the `.gle`-script export format still works, since it involves no compile step.

## Launching

```bash
gleplot-gui
```

This is a console-script entry point (`gleplot.gui.app:main`) that creates a `QApplication`, shows the main window, and runs the Qt event loop. The window opens with an empty preview and the placeholder message "Nothing to render yet -- load data and add a series" until a figure has at least one series.

## Walkthrough

This walks through the same steps as `examples/gui/`, which ships a ready-to-open figure (`damped_oscillation.gle` plus its `.dat` sidecars) and its source data (`damped_oscillation.csv`) if you'd rather skip straight to a finished example.

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

Switch to the **Properties** dock's **Series** tab, which lists every series on the current axes. Select one to edit its label, color, line style, marker, line width, and marker size (control availability depends on the series kind -- e.g. bar charts only expose color, since GLE only supports one color per bar chart, and scatter series have no line style/line width). The Remove / Up / Down buttons delete or reorder the selected series (reordering only moves it within its own kind -- lines, then scatters, then bars, ... -- the between-kind draw order is fixed).

The **Axes** tab covers axis labels (title, X/Y/Y2), limits (leave a limit blank for "auto"), scale (linear/log per axis, including a secondary Y2 axis), and legend (on/off plus one of five placements). The legend checkbox reflects the *effective* state: with it left on auto, a legend appears automatically once any series has a label. The **Figure** tab covers figure-level settings: width and height (inches) and DPI.

### 4. Arrange subplots

The **Layout** tab shows the current subplot grid (rows x cols) and a list of grid slots. To add more panels: increase Rows/Cols and click **Apply grid**, then select an empty slot and click **Add axes here**. Selecting an existing (populated) slot retargets the Axes/Series tabs onto that subplot without marking the document dirty (it's a view change only).

The same tab has **Share X** / **Share Y** checkboxes (mirroring `figure.sharex`/`sharey`) and per-margin **Spacing** controls (`left`/`right`/`bottom`/`top`/`wspace`/`hspace`, matching `subplots_adjust`) -- each margin is an independent optional override; leaving its checkbox unchecked falls back to GLE's default.

Shrinking the grid or reshaping it (e.g. 2x3 to 3x2) refuses to relocate a populated axes off the new grid -- you'll see an inline error asking you to clear that axes' content first. Empty axes are dropped or reflowed silently.

### 5. Save the figure

**File ▸ Save** (Ctrl+S) writes a native `.gle` file (the same format GLE renders), prompting for a location the first time (or use **File ▸ Save As...**, Ctrl+Shift+S). Imported-data series are written out as `.dat` sidecars alongside the `.gle`. Saved and recently-opened files appear under **File ▸ Open Recent**.

### 6. Export

**File ▸ Export...** (Ctrl+E) opens the export dialog: choose a destination path, format (pdf/png/eps/svg/jpg/gle), DPI (raster formats only), and optionally "Export as folder bundle" to write a `<name>.gleplot/` folder containing the script, compiled output, and any data files together. Export always works from an immediate snapshot of the figure (`to_dict()` / `from_dict()`), never the live in-editing object, so it can't be affected by incidental edit order. On success the status bar shows "Exported \<path\>".

## The native `.gle` format

`.gle` **is** the editor's native save format -- there is no separate project file. **File ▸ Save** writes a plain GLE script (via `Figure.savefig_gle`) that GLE renders directly, with any imported-data series written as `.dat` sidecars beside it. **File ▸ Open** parses a `.gle` file back into the editor with `gleplot.parser.recognizer.parse_gle_figure`, reconstructing the `Figure` object model so you can keep editing.

Opening is deliberately *tolerant*: a file gleplot wrote round-trips exactly, and a hand-edited or exotic `.gle` still opens -- anything the recognizer can't map onto the object model is preserved verbatim as **raw GLE** (shown, read-only, in the Properties dock's **Raw GLE** tab) and re-emitted unchanged on the next save, so no content is silently dropped.

Because GLE is a richer format than the object model, opening can apply a few user-visible normalizations. The lossy or behavior-changing ones append a note to the **Output** dock's warnings list on open; the two purely cosmetic ones are silent:

- **Constant/percentage error bars become data columns** *(warns)*. A `dN ... err 0.5` (constant) or `err 10%` (percentage) is expanded into a concrete per-point error column, which re-saves as a real `.dat` column.
- **Unsupported `title`/`key` options are kept raw** *(warns)*. A `title`/`key` line carrying modifiers the model can't represent is preserved verbatim (Raw GLE tab) rather than rewritten.
- **Programmatic files prompt for read-only** *(prompts on open)*. A file using GLE programming constructs (`sub`/`if`/`for`/...) offers a read-only preview instead of editing (see below).
- **Explicit-on legends collapse to auto** *(silent)*. An explicit `legend()`/`key pos` with labeled series comes back as an automatic legend — the rendering is identical, so no warning is raised.
- **Custom subplot spacing resets to defaults** *(silent)*. A multi-subplot figure that used a non-default `subplots_adjust` re-saves with default spacing (the baked-in cm geometry isn't uniquely invertible). Check multi-panel layouts after an open-and-save cycle.

Missing `.dat` sidecars don't fail the open: the referencing series is marked broken (a `data:` warning plus a ⚠ marker in the Series tab), and you can repoint it at a real file with **Locate file...**.

## Opening `.gle` files

**File ▸ Open** accepts a `.gle` file (the file-type filter is `GLE figure (*.gle)`). Most files open straight into the editor as described above, with any recovery warnings listed in the **Output** dock.

A file that uses GLE **programming constructs** (`sub`/`if`/`for`/`while`/...) is different: the recognizer has no control-flow awareness, so editing might restructure those constructs. Opening one prompts you to either **open a read-only preview** (the default) or **edit anyway**. The same read-only preview is also offered as a fallback if a `.gle` can't be opened as an editable figure at all. In **GLE-preview mode**:

- The script is compiled once (synchronously, under a wait cursor) and shown read-only; the Data and Properties docks are disabled.
- The window title shows `<file.gle> (preview)` and the status bar explains you're in a read-only preview.
- **File ▸ Export** still works -- it recompiles the same script to whatever format/location you choose via a Save dialog -- but Save/Save As and Undo/Redo are disabled, since there's no editable `Figure` behind the preview.
- **File ▸ New** (or opening another file) leaves preview mode and returns to normal document editing.
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

1. The path you pinned in **Tools ▸ GLE Setup…** (see below), if set and still pointing at an existing file. This explicit in-app choice deliberately outranks everything else; if the pinned path no longer exists, a warning is emitted and discovery falls through.
2. The **`GLE_PATH`** environment variable, if set and pointing at an existing path (a warning is emitted and discovery falls through if it's set but invalid).
3. `PATH` (via `shutil.which("gle")`, respecting `PATHEXT` on Windows).
4. A list of well-known per-platform install locations, including versioned install directories (e.g. `GLE-4.3.9`), MacPorts/Homebrew prefixes, and snap.

The main window's status bar always shows the result as a permanent widget: `GLE: <path>` or `GLE: not found`. The same status also appears in **Help ▸ About**. Detection failures never crash the GUI -- an unexpected exception during discovery degrades to "not found" rather than propagating.

### Tools ▸ GLE Setup…

Because the desktop app does **not** bundle GLE, the **Tools ▸ GLE Setup…** dialog lets you tell gleplot exactly which GLE executable to use -- useful when GLE is installed somewhere non-standard, or when you have several versions and want to pin one:

- **Auto-detect** searches your system (the order above, ignoring any current pin) and fills in the best guess.
- **Browse…** lets you pick the executable directly.
- The status line validates the selection by reading GLE's reported version, so you get immediate confirmation it works.
- Leaving the field **blank** means "auto-detect" (no pin).

Your choice is saved (per user, via `QSettings`) and reapplied on the next launch, and takes effect immediately -- the live preview re-renders and the status bar updates without a restart.

## Troubleshooting

### GLE not found

If the status bar reads "GLE: not found", the live preview and any export other than the raw `.gle` script will fail. Install [GLE 4.3+](https://github.com/vlabella/GLE/releases/latest), then either point the editor at it via **Tools ▸ GLE Setup…** (takes effect immediately, no restart), put it on `PATH`, or set `GLE_PATH` to the executable. Object-model editing and native `.gle` Save/Open keep working regardless -- see [Requirements / GLE prerequisite](#requirements--gle-prerequisite).

### Preview stays blank

If the preview shows "Nothing to render yet -- load data and add a series", the figure has no renderable content yet: an empty figure (no axes, or axes with no series) is deliberately *not* compiled, so add at least one series. If instead you see a "GLE not found" error in the Output dock, resolve the GLE install as above. A blank preview that never updates while GLE *is* detected usually means every render is failing -- check the Output dock for compile errors (the preview keeps the last good image, so persistent errors leave a stale or empty canvas).

### macOS app won't open ("unidentified developer")

The macOS build is unsigned; Gatekeeper blocks the first launch. Right-click the app → **Open** and confirm, or run `xattr -dr com.apple.quarantine /Applications/gleplot.app` -- see [Installation](#option-a-prebuilt-desktop-app).

### Compile errors

When a render or export fails, structured errors appear in the **Output** dock as one line per error, in the form `line L, col C: message` (or just `line L: message` / `message` when GLE didn't report a column or line). Toggle **Show details** in the Output dock to see the compiler's raw stdout/stderr. The live preview keeps showing the last successful render underneath a failed compile, so a typo doesn't blank the canvas.

## Current limitations

- **Single figure per window.** There is one document per `MainWindow`; open a second window (a new `gleplot-gui` process) to work on two figures side by side.
- **Bar chart color.** Inherited from GLE itself: a `bar` series stores one color for the whole chart (`Axes.bar` only honors the first color if given a list), so per-bar colors aren't available in the Series panel either.
- **Live preview and most exports require GLE installed.** Only the `.gle`-script export format works without a working GLE installation.
- **Export runs synchronously** on the GUI thread (the live preview render does not -- it's async and debounced) -- large figures or a slow GLE install will briefly block the UI during File ▸ Export.
- **Reference-mode scatter series** fall back to a plain line (no per-point markers) since `line_from_file` doesn't support markers; use Import mode for true scatter plots.

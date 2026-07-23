# GUI Editor Guide

gleplot includes a desktop editor -- built on PySide6 -- for building figures interactively: load data, map columns to series, style everything from dockable property panels, arrange subplots, and export, all with a live preview that recompiles as you edit.

## Overview

The editor window (`MainWindow`) has:

- A central **live preview** showing the figure rendered via GLE (vector SVG by default, PNG as a fallback -- see [Preview rendering](#preview-rendering)), debounced so rapid edits don't trigger a compile per keystroke, with draggable/editable text annotations directly on the canvas (see [Working with annotations](#working-with-annotations)).
- A **Data** dock for loading delimited data files and creating series from their columns.
- A **Properties** dock with **Layout**, **Figure**, **Axes**, **Series**, and **Texts** tabs.
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
- shows up to 100 rows in the preview table, with real column names as its header row whenever the source file has one (a positional `col1`/`col2`/... placeholder is used when it doesn't).

Loaded files stay listed so you can switch between them or load several.

### 2. Pick columns and add a series

With a file selected, the "Add series" form fills its X/Y/Y-error column combos with the file's *numeric* columns. Choose:

- **X column** / **Y column** -- required.
- **Y error** -- optional, only used for the "Error bars" plot type.
- **Label** -- defaults to the Y column's name; edit it and the default stops auto-updating.
- **Plot type** -- Line, Scatter, Line+markers, Error bars, or one of the two scattered-field types **Heatmap (scattered x,y,z)** and **Contour (scattered x,y,z)** (see [Heatmaps and contours](#heatmaps-and-contours) below).
- **Mode** -- **Import data** copies the selected columns into the figure (they become `.dat` sidecars on export); **Reference file** instead points the GLE script at the original file by column index (via `Axes.line_from_file` / `Axes.errorbar_from_file`), so no data is duplicated. Note: reference mode's "Scatter" plot type currently falls back to a plain line -- markers on a referenced series aren't supported yet; use Import mode for a true scatter.

Click **Add series**. It's added to the figure's current axes and the live preview recompiles.

### 3. Style the series

Switch to the **Properties** dock's **Series** tab, which lists every series on the current axes. Select one to edit its label, color, line style, marker, line width, and marker size (control availability depends on the series kind -- e.g. bar charts only expose color, since GLE only supports one color per bar chart, and scatter series have no line style/line width). The Remove / Up / Down buttons delete or reorder the selected series (reordering only moves it within its own kind -- lines, then scatters, then bars, ... -- the between-kind draw order is fixed).

The **Axes** tab covers axis labels (title, X/Y/Y2), limits (leave a limit blank for "auto"), scale (linear/log per axis, including a secondary Y2 axis), and legend (on/off plus one of five placements). The legend checkbox reflects the *effective* state: with it left on auto, a legend appears automatically once any series has a label. The **Figure** tab covers figure-level settings: width and height (inches) and DPI. The **Texts** tab lists and edits any free-form text annotations on the current axes -- see [Working with annotations](#working-with-annotations) for the full walkthrough, including adding and dragging annotations directly on the preview.

### Heatmaps and contours

The editor can draw scalar-field data as a colour map (heatmap) and/or contour lines. There are two ways in: creating one from scattered `(x, y, z)` samples in the **Data** dock, and styling it in the **Series** tab. (Gridded `imshow`/`contour` figures built in code, or opened from a `.gle`, are edited from the Series tab the same way.)

**Creating from scattered data.** Load a data file with at least three numeric columns, then pick **Heatmap (scattered x,y,z)** or **Contour (scattered x,y,z)** as the plot type. The form swaps its **Y error** row for a **Z column** picker; choose the X, Y, and Z columns and click **Add series**. gleplot writes the raw `x y z` triples to a sidecar and lets GLE grid them (via `fitz`) at compile time -- so these types are **Import mode only** (the Mode combo is disabled while one is selected; there is no reference-file equivalent, since `fitz` needs gleplot's own triples file). GLE allows **at most one heatmap per axes**: if the current axes already has one, adding another is refused with an explanatory dialog rather than replacing it -- remove the existing heatmap first (Series tab) if you want a different one. A contour on the same axes as a heatmap is fine (they are independent layers).

**Styling in the Series tab.** Heatmap and contour series appear in the Series list like any other. Selecting one shows its dedicated controls:

- **Heatmap** -- **Palette** (viridis, magma, inferno, plasma, cividis, coolwarm, rainbow/jet, or gray), **Colour min** / **Colour max** (leave blank for GLE's automatic data range), **Pixels** (the colormap's bitmap resolution), **Interpolation** (bicubic or nearest), **Invert colours**, and a **Show colorbar** toggle. Turning the colorbar on reveals its **Colorbar label** and **Colorbar format** fields (the format is a GLE `format$` string such as `fix 1`); the tick range is derived from the heatmap's colour range. A heatmap has no single line colour, so the shared **Color** control is disabled for it.
- **Contour** -- a **Levels** field, plus a **Label contours** toggle with a **Label format** field. Contours reuse the shared **Color** and **Line width** controls for their line styling. The Levels field accepts an explicit space- or comma-separated list (`0.1 0.2 0.3`), the shorthand `n=10` for ten evenly-spaced automatic levels, or blank for GLE's default set. Enabling **Label contours** draws the level value inline along each contour, formatted with the label format.

All of these edits go through the normal document flow, so the live preview recompiles and **Undo/redo** restores them like any other change.

### 4. Arrange subplots

The **Layout** tab shows the current subplot grid (rows x cols) and a list of grid slots. To add more panels: increase Rows/Cols and click **Apply grid**, then select an empty slot and click **Add axes here**. Selecting an existing (populated) slot retargets the Axes/Series tabs onto that subplot without marking the document dirty (it's a view change only).

The same tab has **Share X** / **Share Y** checkboxes (mirroring `figure.sharex`/`sharey`) and per-margin **Spacing** controls (`left`/`right`/`bottom`/`top`/`wspace`/`hspace`, matching `subplots_adjust`) -- each margin is an independent optional override; leaving its checkbox unchecked falls back to GLE's default.

Shrinking the grid or reshaping it (e.g. 2x3 to 3x2) refuses to relocate a populated axes off the new grid -- you'll see an inline error asking you to clear that axes' content first. Empty axes are dropped or reflowed silently.

### 5. Save the figure

**File ▸ Save** (Ctrl+S) writes a native `.gle` file (the same format GLE renders), prompting for a location the first time (or use **File ▸ Save As...**, Ctrl+Shift+S). Imported-data series are written out as `.dat` sidecars alongside the `.gle`. Saved and recently-opened files appear under **File ▸ Open Recent**.

Each generated `.dat` sidecar now begins with a named header row -- an `x` column plus one sanitized name per data column, derived from the series' label where one was given (lowercased, non-alphanumeric characters collapsed to underscores, de-duplicated with a `_2`/`_3` suffix if a name repeats, and never left looking like a plain number, since GLE would otherwise misread the header row as data). Opening the file in a text editor or spreadsheet shows real column names instead of anonymous numbers. Because GLE would otherwise invent its own legend text from a header row it can already read (its `auto_has_header` behavior), gleplot always writes an explicit `key` clause -- the series' real label, or an empty one -- alongside any headered sidecar, so adding a header never changes how the figure renders.

### 6. Export

**File ▸ Export...** (Ctrl+E) opens the export dialog: choose a destination path, format (pdf/png/eps/svg/jpg/gle), DPI (raster formats only), and optionally "Export as folder bundle" to write a `<name>.gleplot/` folder containing the script, compiled output, and any data files together. Export always works from an immediate snapshot of the figure (`to_dict()` / `from_dict()`), never the live in-editing object, so it can't be affected by incidental edit order. On success the status bar shows "Exported \<path\>".

## Working with annotations

Free-form text annotations (`Axes.text` entries) can be added, moved, edited, and removed directly on the live preview, in addition to the **Texts** tab in the Properties dock. Both stay in sync.

### Adding text

**Edit ▸ Add text annotation** (shortcut **T**) arms "click to place": the status bar shows "Click on the plot to place text — Esc to cancel", and the next left-click on the preview drops a new annotation at that point (in the data coordinates of whichever axes was clicked) and immediately opens it for inline editing. Press **Esc** before clicking to cancel without adding anything. The action is only enabled while the preview has a valid render to calibrate against -- see [Overlay availability](#overlay-availability) below.

The Texts tab has its own **Add** button as an alternative entry point: it inserts a new annotation at the centre of the current axes' limits (not at a clicked point) and selects it, ready to reposition via the X/Y fields or by dragging it on the canvas.

### Dragging

Hover over an existing annotation on the preview and the cursor becomes an open hand; drag it to reposition. Because the rendered image only shows the annotation at its *old* location until the next debounced re-render lands, the drag shows a semi-transparent "ghost" of the text following the cursor -- the real glyphs snap into place a moment later once GLE recompiles. Dropping an annotation outside its owning axes' frame is allowed (GLE renders text outside the graph box fine); the annotation keeps its original owning axes and its coordinates are still computed through that axes' data transform.

### Editing and deleting

- **Double-click** an annotation on the preview to edit its text inline. **Enter** commits the change; **Esc** cancels and leaves the model untouched. Committing an empty string deletes the annotation. (GLE's `write` command is single-line, so any newlines you type are flattened to spaces on commit.)
- Select an annotation (click it, or select its row in the Texts tab) and press **Delete** or **Backspace** to remove it.
- The Texts tab's **Remove** button deletes whichever row is selected there.

### Selection sync with the Texts tab

Clicking an annotation on the canvas selects the matching row in the Texts tab (retargeting the tab to that annotation's axes first, if needed), and selecting a row in the Texts tab highlights the corresponding handle on the canvas. Either direction is one-way-triggered per action -- there's no feedback loop -- so clicking around in either place always leaves both views agreeing on the current selection.

### The Texts tab

The Properties dock's **Texts** tab lists every annotation on the current axes and edits whichever one is selected:

- **Text** -- the annotation's content (multi-line input is accepted but flattened to a single line on commit, matching GLE's `write` command).
- **X** / **Y** -- the anchor position in data coordinates.
- **Color** -- opens a color picker; the chosen color is always written out explicitly (never left as "inherit default").
- **Font size** -- a "Custom size" checkbox plus a point-size spinner; unchecking it reverts the annotation to the default text size instead of a specific value.
- **Horiz. align** -- `left`, `center`, or `right`, matching the annotation's anchor point on the x-axis.
- **Vert. align** and **Box color** -- shown but **disabled**, with a tooltip reading "Stored but not rendered by GLE output." These two fields exist for API/data-model compatibility (and, for box color, round-trip through the same color storage as other color fields) but gleplot's GLE writer never emits anything that would make GLE draw a vertical alignment or a background box for annotation text -- so editing them would silently do nothing. They're left visible rather than hidden so the underlying data isn't a mystery, but disabled so you don't spend time tuning a setting with no visible effect.

### Overlay availability

The on-canvas overlay depends on a per-render calibration that maps the figure's data coordinates onto the rendered page (see [Preview rendering](#preview-rendering) below for how the preview itself works). That calibration is only available when the document has actually rendered successfully:

- It is unavailable before the first successful render (e.g. an empty figure, or the current edit doesn't yet compile) -- **Edit ▸ Add text annotation** is disabled, any active click-to-place is cancelled, and existing annotations aren't draggable until a render succeeds again.
- It is always unavailable in **GLE-preview mode** (see [Opening `.gle` files](#opening-gle-files)) -- that mode never renders through the document pipeline, so there is no calibration to compute from, and the Texts tab is disabled along with the rest of the Properties dock.
- It comes back automatically the moment a render succeeds again -- no user action needed.

## Preview rendering

The live preview renders either an SVG (vector) or a PNG (raster) image of the figure; either way, the same debounced recompile-on-edit behavior applies.

### SVG by default, PNG as a sticky fallback

The preview uses **SVG** by default in a session where GLE's Cairo-based SVG backend (`gle -d svg`) is confirmed to work. If SVG can't be used -- the optional SVG-rendering support isn't available, or a one-time startup check finds that this GLE install's SVG output doesn't load -- the preview starts in PNG instead.

If an SVG render fails partway through a session (for example, because the figure's own configured font isn't compatible with GLE's Cairo backend), the preview permanently falls back to PNG for the rest of that session: the status bar shows "Vector preview unavailable; showing PNG instead.", and **View ▸ Vector preview (SVG)** is unchecked and greyed out with a tooltip explaining why. This fallback is sticky -- it does not retry SVG later in the same session -- but a fresh launch of the editor tries SVG again.

### The toggle

**View ▸ Vector preview (SVG)** switches the live preview between SVG and PNG rendering. It's checked when SVG is active, and it's disabled entirely (with a tooltip) if SVG isn't available in this session at all. Toggling it doesn't change anything about the saved `.gle` file or any exported output -- it only affects what's drawn in the editor's own preview pane.

### Font substitution in the SVG preview (Cairo-safe fonts)

GLE's Cairo SVG backend refuses to draw PostScript fonts -- the default font gleplot's figures use when no font is explicitly set falls into that category, so an SVG preview render would otherwise fail immediately. To avoid that, the preview silently substitutes a Cairo/TeX-safe font (`texcmr`) for the SVG render **only** when the figure doesn't already set its own font explicitly; if you've set a font yourself, that choice is always respected and never overridden.

This substitution is applied only to the temporary copy of the script used to draw the live preview -- it never touches your saved `.gle` file, and it has no effect on PDF, PNG, EPS, or JPG **exports**, which compile the figure exactly as saved. In other words: if your SVG preview shows text in a different font than you expect, check your exported output before worrying -- the export is very likely using your actual configured font (or GLE's real default), and only the on-screen SVG preview needed the substitution to render at all.

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

On open, gleplot decides whether each `data` reference is one of its own imported sidecars (pulled in as editable series data) or an external file (referenced in place, read-only) **solely from the `! gleplot` metadata block** that gleplot writes into every file it saves. A hand-authored or third-party `.gle` has no such block, so *all* of its data references are treated as external references — gleplot never adopts and rewrites a file it can't prove it authored, even if the filename happens to look like one of its own `name_N.dat` sidecars.

### Named headers and column names in the Data dock

Sidecars gleplot writes carry the named header row described in [step 5](#5-save-the-figure) above, and both the loader and **File ▸ Open** read it back: the Data dock's preview table and any column-picking combo show the real names (`x`, `y_measured`, ...) instead of anonymous `col1`/`col2` placeholders, and re-saving a round-tripped figure reproduces the same names.

**Double-click a column header** in the Data dock's preview table to rename it. On a table gleplot owns, this opens a dialog prefilled with the current name; typing a new one and confirming sanitizes it the same way series labels are sanitized for a sidecar header (lowercased, non-alphanumeric characters collapsed to underscores, auto-suffixed with `_2`/`_3` if the name collides with another column in the same table) and applies it everywhere that table's name is shown.

Renaming is only offered for data gleplot itself owns:

- **Figure-owned sidecars** -- a series added in **Import data** mode, or a file loaded straight from disk that isn't (yet) the reference target of a **Reference file** series -- are gleplot's own copies, so their column names can be renamed from the Data dock.
- **Externally referenced files** -- anything a **Reference file** series points at (`Axes.line_from_file` / `Axes.errorbar_from_file`) -- are read-only for naming purposes: gleplot never rewrites a file it doesn't own the contents of. Their header cells show a tooltip explaining the names come from the referenced file, and double-clicking one shows an explanatory message instead of a rename dialog.

This mirrors the same Import-vs-Reference distinction from [step 2](#2-pick-columns-and-add-a-series) of the walkthrough -- if you can imagine gleplot rewriting the file on save, its headers are renameable; if the file lives outside the project and gleplot only reads it, they aren't.

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
- **Annotation vertical alignment and box color are not rendered.** Both fields exist on the Texts tab for data-model compatibility, but gleplot's GLE output never draws either one, so their controls are disabled -- see [The Texts tab](#the-texts-tab).
- **Dragging an annotation never changes its owning axes.** Dropping it visually inside a different subplot still keeps it attached to (and positioned relative to) the axes it was created on.
- **The on-canvas annotation overlay needs a successful render to work.** It's unavailable before the first render, during a compile failure, and always in GLE-preview mode -- see [Overlay availability](#overlay-availability).

# CLAUDE.md

Orientation for AI coding agents working in this repository. Keep it accurate — verify against code before trusting.

## What gleplot is

gleplot is a **matplotlib-compatible Python library** that generates **GLE (Graphics Layout Engine)** scripts for publication-quality vector graphics, plus a **PySide6 desktop editor** for building figures without writing code.

Two entry points:

- **Library API** — `import gleplot as glp`. Familiar matplotlib calls (`figure`, `subplots`, `plot`, `scatter`, `bar`, `fill_between`, `errorbar`, `savefig`, `view`) produce a `.gle` script and, when GLE is installed, compile it to PDF/PNG/EPS/SVG/JPG.
- **Desktop GUI** — `gleplot-gui` console script → `gleplot.gui.app:main`. A point-and-click editor with a live preview.

## Architecture map

### Core library (`src/gleplot/`)

- `__init__.py` — public API: `Figure`, `Axes`, config classes, module-level convenience functions (`figure`, `subplots`, `plot`, …), and `open_gle()` (parse a `.gle` file back into a `Figure`).
- `figure.py` — `Figure`: subplot layout, `savefig`, `view`, and a byte-stable `to_dict()`/`from_dict()` serialization (used by the GUI for undo/preview snapshots).
- `axes.py` — `Axes`: per-plot primitives (lines, scatter, bars, fills, errorbars, text, log scales, secondary y-axis, `*_from_file` series).
- `series.py` — the typed series classes (`LineSeries`, `ScatterSeries`, `BarSeries`, `FillSeries`, `ErrorbarSeries`, `FileSeries`, `TextAnnotation`, `HeatmapSeries`, `ContourSeries`, `RefLine`, `Span`) held in the eleven series lists on `Axes`, plus the `SERIES_CLASSES` registry that fixes their serialization/emission order. Each class declares its own fields, its array fields and its sidecar header-row defaults, and is a `dict` subclass so every `series["key"]` call site in the writer/recognizer/GUI keeps working and `to_dict()` stays byte-identical.
- `sources.py` — the `data_source` abstraction: `InlineData` (arrays baked onto the series — the default, and what a *missing* `data_source` key means), `ColumnRef`/`GridRef` (references into a table supplied by a `DataProvider`), the `DataProvider`/`ProviderTable` protocols with a concrete `TableData`/`DictDataProvider` pair, and `DanglingSourceRef` — the structured record produced when a reference cannot be resolved. Note the field is `data_source`: heatmaps/contours have had an unrelated `source` field (`'grid'`/`'points'`) since long before this.
- `writer.py` — turns the object model into GLE script text, and owns the write-time source resolution (`resolve_figure` → `SourceResolution`) that every series' data passes through. Series resolved from one provider table share a single `.dat` sidecar; a dangling reference skips its series and records a warning instead of raising. The provider is injected per write (`Figure.savefig(..., data_provider=...)`), never stored on the figure; results surface on `Figure.source_warnings`.
- `compiler.py` — `GLECompiler` + `find_gle()`: shells out to the external `gle` binary. Supported formats in `SUPPORTED_COMPILE_FORMATS`.
- `config.py` — `GLEStyleConfig`, `GLEGraphConfig`, `GLEMarkerConfig`, `GlobalConfig`.
- `colors.py`, `markers.py` — matplotlib→GLE color/marker mappings.
- `dataio.py` — pure-Python delimited data-file loading (`load_data_file`, `DataTable`); no Qt dependency, shared by parser and GUI.

### Parser subpackage (`src/gleplot/parser/`)

Parses **existing `.gle` source back into an object model**. No Qt imports; stdlib only.

- `lexer.py`, `syntax.py`, `expr.py` — tokenize/parse GLE into a structural tree (`parse_gle_source`, `emit`, `GleDocument`) with **round-trip fidelity** (`emit(parse_gle_source(text))` reproduces the input byte-for-byte when unchanged).
- `recognizer.py` — `parse_gle_figure()`: semantic mapper that reconstructs a gleplot `Figure` from GLE, returning recovery warnings for content it can't fully model.
- `tables.py`, `units.py`, `metadata.py` — GLE keyword tables, unit conversions (inches/pt→cm), embedded metadata.

### GUI subpackage (`src/gleplot/gui/`)

Core design principle — **the `FigureDocument` object model is the single source of truth**:

- `document.py` — `FigureDocument` wraps a `Figure` and broadcasts Qt signals (`figure_changed`, `figure_replaced`, `dirty_changed`). Owns no rendering or persistence logic. Panels mutate the figure then call `notify_changed()`.
- `.gle` is the **native on-disk format** (`file_ops.py`); unrecognized GLE content is preserved. Opening runs the parser's `recognizer`; warnings surface via `document.open_warnings`.
- `preview.py` — `PreviewController`: **debounced, asynchronous** GLE compile-to-PNG off the GUI thread (via `QProcess`), coalescing rapid edits. Renders from a `to_dict()` snapshot (never the live figure) to stay side-effect-free.
- `undo.py` — `UndoStack`: snapshot-based undo/redo driven by `Figure.to_dict()`, bounded by capacity.
- `main_window.py`, `app.py`, `export_dialog.py`, `error_panel.py`, `gle_viewer.py`, `file_ops.py`.
- `panels/` — property panels: `figure_panel`, `axes_panel`, `series_panel`, `layout_panel`, `raw_gle_panel`.
- `data/` — data-manager panel (`panel.py`); `loader.py` re-exports the loading layer now living in `dataio.py`.

## Page geometry: explicit placement, and the metadata v1 → v2 migration

Every graph block gleplot writes carries an **explicit frame rectangle** —
`amove x y` before the block, `size w h` + `scale 1 1` as its first statements.
That triple is the only GLE geometry that inverts to a rectangle (`scale 1 1`
makes the axis frame fill the graph box), so the recognizer reads it straight
back into `Axes.placement` and re-emits it verbatim.

- **One routine computes it**: `Figure._layout_rects`. A lone plot is the 1×1
  case of the subplot grid — there is no separate single-plot geometry path.
  `subplots_adjust`, `height_ratios`/`width_ratios` and the colorbar width
  reservation therefore apply to a single plot exactly as to a grid.
- **Margins are decoration margins.** GLE draws tick labels and axis titles
  *outside* the frame rect, so `_auto_margins_cm` leaves blank space around the
  grid for them. The 1×1 row is expressed in units of the text height `hei`
  (the overflow scales with the font); the grid rows keep their historical
  fixed-cm values. Margins are a heuristic in both cases — unusually wide tick
  labels still need `subplots_adjust(left=…)`.
- **`placement` wins when set.** The grid is only a helper that computes rects;
  the rects are the model (SPEC 3.3). A figure parsed back from GLE carries its
  recovered rects, which is why `subplots_adjust` layouts survive save → parse
  → save byte-identically even though the *fractions* are not recoverable.
- **Opt-out**: `GLEGraphConfig(scale_mode="fullsize")` still emits `fullsize`
  and no `amove`, and unmodelled geometry recovered from a hand-written file is
  re-emitted verbatim from `Axes.geometry_passthrough`.

**Migration policy (metadata block v1 → v2).** The `! gleplot-meta-begin vN`
marker records how a file's page geometry was written, not the `key = value`
line format (identical in every version). v1 files — where a single plot was a
bare `scale auto` and grid cells were only reproducible by re-deriving them —
**load fine**: their implicit geometry becomes auto placement (`placement =
None`), exactly as before. The **first save rewrites them as v2 with an explicit
rect**, a deliberate one-time byte diff, reported by a `metadata:` warning on
load. There is no downgrade path. `parse_metadata` accepts every version in
`SUPPORTED_VERSIONS`; only an *unknown* version warns as unrecognized.

The invariant this buys: `tests/parser/test_fixed_point.py` has an **empty
exemption set**. Writer → parse → writer is byte-identical for every builder in
the golden and project batteries, with no carve-outs. A builder that cannot
satisfy it is a bug, not a candidate for a new exemption.

## External dependency: GLE binary

The GUI and compiler **shell out to an external `gle` binary (GLE 4.3+)**, discovered via an explicit override (set in the GUI's **Tools ▸ GLE Setup…**, persisted in `QSettings` as `gle/path`, applied through `compiler.set_gle_path_override`) → `GLE_PATH` env var → `PATH` (`shutil.which`) → platform well-known locations, incl. globbed versioned install dirs (see `compiler.find_gle` / `compiler.autodetect_gle`). **GLE is NOT bundled.** The app degrades gracefully when GLE is absent: the status bar shows "not found", and features needing compilation are disabled while pure-`.gle` editing still works.

## How to

```bash
# Dev install (library + GUI + dev tooling)
pip install -e ".[dev,gui]"

# Run the full test suite
pytest tests/ -v

# Run one suite
pytest tests/unit/ -v
pytest tests/gui/ -v
pytest tests/parser/ -v
pytest tests/integration/ -v

# Launch the GUI
gleplot-gui
```

Test subdirs: `tests/unit/`, `tests/integration/`, `tests/parser/`, `tests/gui/`, `tests/agent/`. GUI tests need PySide6; compilation-dependent tests need a `gle` binary.

## Conventions

- **Formatting**: black (line-length 88); isort (black profile, line-length 88).
- **Python**: supports `>=3.7`; mypy target is `3.9`.
- **License**: GPL-2.0+ (compatible with GLE).
- **Commits**: conventional-commits. python-semantic-release drives versioning — `feat` → minor, `fix`/`perf` → patch. Version lives in `pyproject.toml` and `src/gleplot/__init__.py:__version__` (kept in sync by semantic-release).

## Where to look next

- `docs/` — user/dev guides in `docs/guides/` (including `GUI_EDITOR.md`), Sphinx source in `docs/source/`, and an index at `docs/DOCUMENTATION_INDEX.md`.
- `packaging/` — PyInstaller specs and helpers for building the standalone desktop binaries (Windows `.exe` installer, macOS `.dmg`). See the `packaging` optional-dependency group in `pyproject.toml`.

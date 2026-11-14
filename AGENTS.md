# AGENTS.md

Shared contract for AI coding agents in this repository. Keep it accurate — **verify against the code before trusting** this map.

## What gleplot is

gleplot is a **matplotlib-compatible Python library** that generates **GLE (Graphics Layout Engine)** scripts for publication-quality vector graphics, plus a **PySide6 desktop editor** for building figures without writing code.

Two entry points:

- **Library API** — `import gleplot as glp`. Familiar matplotlib calls (`figure`, `subplots`, `plot`, `scatter`, `bar`, `fill_between`, `errorbar`, `savefig`, `view`) produce a `.gle` script and, when GLE is installed, compile it to PDF/PNG/EPS/SVG/JPG.
- **Desktop GUI** — `gleplot-gui` → `gleplot.gui.app:main`. Point-and-click editor with live preview.

## Architecture map

### Core library (`src/gleplot/`)

- `__init__.py` — public API: `Figure`, `Axes`, config classes, module-level functions (`figure`, `subplots`, `plot`, …), `open_gle()`.
- `figure.py` — `Figure`: subplot layout, `savefig`, `view`, byte-stable `to_dict()`/`from_dict()` (GUI undo/preview).
- `axes.py` — `Axes`: plot primitives, log scales, secondary y-axis, `*_from_file` series.
- `series.py` — typed series classes on `Axes` plus `SERIES_CLASSES` (serialization/emission order). Each class is a `dict` subclass; `to_dict()` stays byte-identical.
- `sources.py` — `data_source`: `InlineData`, `ColumnRef`/`GridRef`, `DataProvider`, `DanglingSourceRef`. Field name is `data_source` (not heatmap/contour `source`).
- `writer.py` — object model → GLE text; write-time `resolve_figure` / `SourceResolution`. `data_provider` is per `savefig`, never stored on the figure; warnings on `Figure.source_warnings`.
- `compiler.py` — `GLECompiler`, `find_gle()`; external `gle` binary.
- `config.py` — `GLEStyleConfig`, `GLEGraphConfig`, `GLEMarkerConfig`, `GlobalConfig`.
- `colors.py`, `markers.py` — matplotlib→GLE mappings.
- `dataio.py` — delimited file loading; no Qt.
- `calibration.py` — calibration record v2; Qt-free post-generation instrumentation over `parser.syntax`.
- `guides.py` — guide subs and write-time routing (`Axes.guide_needs_engine_range`); no extra model field for engine-range guides.

### Parser (`src/gleplot/parser/`)

Stdlib only; no Qt.

- `lexer.py`, `syntax.py`, `expr.py` — parse/emit with round-trip fidelity when unchanged.
- `recognizer.py` — `parse_gle_figure()` → `Figure` + recovery warnings.
- `tables.py`, `units.py`, `metadata.py` — keywords, units, embedded metadata.

### GUI (`src/gleplot/gui/`)

**`FigureDocument` wraps `Figure` and is the single source of truth.** Panels mutate the figure and call `notify_changed()`. `.gle` is native on-disk format; preview uses `to_dict()` snapshots off the GUI thread.

- `document.py`, `file_ops.py`, `preview.py`, `undo.py`, `main_window.py`, `app.py`, `panels/`, `data/`.

## Invariants

Do not violate these without an explicit design change and tests.

- **Layout** — `Figure._layout_rects` is the only layout path; a lone plot is 1×1. Recovered `Axes.placement` (explicit `amove`/`size`/`scale 1 1`) wins over grid fractions. Opt-out: `GLEGraphConfig(scale_mode="fullsize")` or `Axes.geometry_passthrough` for unmodelled GLE.
- **Fixed point** — writer → `parse_gle_figure` → writer is **byte-identical** (GLE + `.dat` sidecars). `tests/parser/test_fixed_point.py` keeps an **empty** exemption set; a failing builder is a bug, not a new exemption.
- **Figure model** — preview/undo use `to_dict()` snapshots, not the live figure during compile.
- **Series** — stay `dict` subclasses; `SERIES_CLASSES` order is emission order.
- **Layers** — parser, `dataio`, calibration, and writer do **not** import Qt.
- **Preservation** — unrecognized GLE is preserved; recovery warnings are surfaced, not dropped silently.
- **Metadata** — v1 files load (implicit placement); first save rewrites to v2 with a `metadata:` warning. No downgrade. Unknown meta versions warn.
- **GLE optional** — saving `.gle` always works; **GLE is not bundled**. Discovery: GUI override → `GLE_PATH` → `PATH` → well-known paths (`compiler.find_gle`).

## Matplotlib compatibility

Match matplotlib **names**, **positional order**, and **defaults** on the API surface gleplot already documents: `plot`, `scatter`, `bar`, `errorbar`, `fill_between`, `text`, reference lines/spans, `legend`, axis labels/limits/scales, `grid`, `subplots`, `savefig`, colors, markers.

Where GLE cannot express a keyword: **accept it**, emit **`UserWarning`**, and document the gap in `docs/guides/MATPLOTLIB_MIGRATION.md`.

Do **not** add 3D, animation, or interactive widget APIs for signature parity.

Gleplot-specific API stays explicit: `data_prefix`, `data_source`, placement in cm, `open_gle`, `GLE*Config`. **`figsize` stays in inches.**

## Lean changes

- Extend existing series classes, writer branches, or `_layout_rects`. Write-time routing (guides, source resolution) is not a new persisted field unless the model truly needs it.
- New public names, series fields, or config knobs need a **caller in the same change**.
- Comments explain **invariants** or **GLE constraints**, not obvious code.
- **Python ≥3.7** syntax only; no new dependency for a small feature.
- Do **not** split `writer.py`, `axes.py`, or `recognizer.py` merely to shorten files.

## Plans and documentation

- **Design notes and implementation journals** → [GitHub issues](https://github.com/benhuddart/gleplot/issues), not the repo.
- **`docs/`** is user and contributor documentation only.
- **Do not add** files under `docs/agent/` or `tests/agent/`.

## Tests

Keep the suite layered (~100 modules). Prefer extending existing batteries over new files.

| Layer | Purpose | Needs |
|-------|---------|--------|
| `tests/unit` | Object model, emitted script text | — |
| `tests/parser` | Parse, recovery, fixed point | — |
| `tests/integration` | Truth after GLE compiles (ink, cairo, accept) | GLE binary, skipped when absent |
| `tests/gui` | Panels/document mutate figure | PySide6 |

- Add cases to the relevant module or battery (`test_fixed_point.py`, `tests/parser/_golden_battery.py`, `_*_battery.py` helpers). **New file = new behavior area.**
- No integration test that only duplicates a unit-level script assertion.
- Any emission change must keep the fixed point green.
- A test that shells out to GLE must **skip** when the binary is missing (`pytest.mark.skipif` around `GLECompiler()`, which raises `RuntimeError`). `@pytest.mark.gle` only labels those tests: CI runs the whole suite and does not filter on the marker, so the marker alone does not keep a machine without GLE green. Parser tests that compile use the same pair.
- **Coverage** is a branch finder, not a score to chase: no `fail-under` gate. After your change, run `pytest --cov=gleplot.<module> --cov-report=term-missing` on touched modules; add a test only for branches you changed without an assertion.

```bash
pip install -e ".[dev,gui]"

pytest tests/ -v
pytest tests/unit/ -v
pytest tests/parser/ -v
pytest tests/integration/ -v
pytest tests/gui/ -v   # PySide6

gleplot-gui
```

## Conventions

- **Format**: black + isort (line-length 88); flake8; mypy (target 3.9).
- **License**: GPL-2.0+.
- **Commits**: conventional commits; `python-semantic-release` — `feat` → minor, `fix`/`perf` → patch. Version: `pyproject.toml` and `src/gleplot/__init__.py:__version__`.

## Where to look next

- `docs/guides/` (including `GUI_EDITOR.md`, `MATPLOTLIB_MIGRATION.md`), `docs/DOCUMENTATION_INDEX.md`, `docs/source/` (Sphinx).
- `packaging/` — PyInstaller/desktop builds (`pyproject.toml` `[project.optional-dependencies] packaging`).
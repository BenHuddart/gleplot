# AGENTS.md

Shared contract for AI coding agents in this repository. Keep it accurate — **verify against the code before trusting** this map.

## What gleplot is

gleplot is a **matplotlib-compatible Python library** that generates **GLE (Graphics Layout Engine)** scripts for publication-quality vector graphics.

**Library API** — `import gleplot as glp`. Familiar matplotlib calls (`figure`, `subplots`, `plot`, `scatter`, `bar`, `fill_between`, `errorbar`, `savefig`, `view`) produce a `.gle` script and, when GLE is installed, compile it to PDF/PNG/EPS/SVG/JPG.

## Architecture map

### Core library (`src/gleplot/`)

- `__init__.py` — public API: `Figure`, `Axes`, config classes, module-level functions (`figure`, `subplots`, `plot`, …), `open_gle()`.
- `figure.py` — `Figure`: subplot layout, `savefig`, `view`, byte-stable `to_dict()`/`from_dict()` (serialization).
- `axes.py` — `Axes`: plot primitives, log scales, secondary y-axis, `*_from_file` series.
- `series.py` — typed series classes on `Axes` plus `SERIES_CLASSES` (serialization/emission order). Each class is a `dict` subclass; `to_dict()` stays byte-identical.
- `sources.py` — `data_source`: `InlineData`, `ColumnRef`/`GridRef`, `DataProvider`, `DanglingSourceRef`. Field name is `data_source` (not heatmap/contour `source`).
- `writer.py` — object model → GLE text; write-time `resolve_figure` / `SourceResolution`. `data_provider` is per `savefig`, never stored on the figure; warnings on `Figure.source_warnings`.
- `compiler.py` — `GLECompiler`, `find_gle()`; external `gle` binary.
- `config.py` — `GLEStyleConfig`, `GLEGraphConfig`, `GLEMarkerConfig`, `GlobalConfig`.
- `colors.py`, `markers.py` — matplotlib→GLE mappings.
- `dataio.py` — delimited file loading; no Qt.
- `guides.py` — guide subs and write-time routing (`Axes.guide_needs_engine_range`); no extra model field for engine-range guides.
- `brokenaxes.py` — `BrokenAxes`: a split x-axis built from adjacent graph blocks.
- `mathtext.py` — matplotlib `$...$` mathtext → GLE text markup.
- `palettes.py` — colormap stop tables and the self-contained palette subs emitted for heatmaps/contours.
- `cairo_support.py` — decides when a figure needs GLE's `-cairo` device and warns about fonts it rejects.

### Parser (`src/gleplot/parser/`)

Two layers:

- **Syntax layer** (stdlib only) — `lexer.py`, `syntax.py`, `expr.py` parse/emit with round-trip fidelity when unchanged; `units.py`, `metadata.py`, `report.py` (typed `ImportNote` recovery notes) sit beside them.
- **Model bridge** — `recognizer.py`: `parse_gle_figure()` → `Figure` + recovery warnings. It imports numpy and the object model (`Axes`, `Figure`, `series`, `dataio`, `GLEWriter`); nothing in the syntax layer may import it.
- `tables.py` — the lookup tables a parser must invert (line styles, key positions, text alignment, …). GLE's raw colour and marker name tables live in `colors.py` and `markers.py` and are re-exported here.

## Invariants

Do not violate these without an explicit design change and tests.

- **Layout** — `Figure._layout_rects` is the only layout path; a lone plot is 1×1. Recovered `Axes.placement` (explicit `amove`/`size`/`scale 1 1`) wins over grid fractions. Opt-out: `GLEGraphConfig(scale_mode="fullsize")` or `Axes.geometry_passthrough` for unmodelled GLE.
- **Fixed point** — writer → `parse_gle_figure` → writer is **byte-identical** (GLE + `.dat` sidecars). `tests/parser/test_fixed_point.py` keeps an **empty** exemption set; a failing builder is a bug, not a new exemption.
- **Figure model** — `to_dict()` snapshots are the canonical round-trip representation for undo-style callers and previews.
- **Series** — stay `dict` subclasses; `SERIES_CLASSES` order is emission order.
- **Layers** — the library has no GUI dependency: nothing under `src/gleplot` imports Qt or IPython at module level. The parser syntax layer is stdlib-only. Module-level imports are acyclic: `series`/`sources` and the leaf modules (`colors`, `markers`, `config`) sit below `writer`, then `axes`, then `figure`, then `parser.recognizer`. Do not hide a cycle inside a function: `tests/unit/test_layering.py` checks the graph and holds function-level imports to an explicit list.
- **Preservation** — unrecognized GLE is preserved; recovery warnings are surfaced, not dropped silently.
- **Metadata** — v1 files load (implicit placement); first save rewrites to v2 with a `metadata:` warning. No downgrade. Unknown meta versions warn.
- **GLE optional** — saving `.gle` always works; **GLE is not bundled**. Discovery: `GLE_PATH` → `PATH` → well-known paths (`compiler.find_gle`).

## Matplotlib compatibility

Match matplotlib **names**, **positional order**, and **defaults** on the API surface gleplot already documents: `plot`, `scatter`, `bar`, `errorbar`, `fill_between`, `text`, reference lines/spans, `legend`, axis labels/limits/scales, `grid`, `subplots`, `savefig`, colors, markers.

Where GLE cannot express a keyword: **accept it**, emit **`UserWarning`**, and document the gap in `docs/guides/MATPLOTLIB_MIGRATION.md`.

Do **not** add 3D, animation, or interactive widget APIs for signature parity.

Gleplot-specific API stays explicit: `data_prefix`, `data_source`, placement in cm, `open_gle`, `GLE*Config`. **`figsize` stays in inches.**

## Lean changes

- Extend existing series classes, writer branches, or `_layout_rects`. Write-time routing (guides, source resolution) is not a new persisted field unless the model truly needs it.
- New public names, series fields, or config knobs need a **caller in the same change**.
- Comments explain **invariants** or **GLE constraints**, not obvious code.
- **Python ≥3.9**; no new dependency for a small feature.
- Do **not** split `writer.py`, `axes.py`, or `recognizer.py` merely to shorten files.

### Adding a series field

A field on a series class is usually touched in five places; missing one breaks the fixed point or silently drops the field on reload:

1. the class annotation in `series.py` (absent means the historical behaviour — do not default to `None`),
2. the `Axes` method that sets it,
3. the `GLEWriter.add_*` method that emits it,
4. the call in `Figure._write_axes_content` that passes it through,
5. the `_Recognizer` branch that recovers it.

Then add a builder exercising it to `tests/parser/_golden_battery.py`, which `test_fixed_point.py` runs.

## Plans and documentation

- **Design notes and implementation journals** → [GitHub issues](https://github.com/benhuddart/gleplot/issues), not the repo.
- **`docs/`** is user and contributor documentation only.
- A new public name gets an entry in the Sphinx API pages (`docs/source/api*.rst`) in the same change, not only a guide mention.
- Docstrings are rendered by Sphinx (numpydoc sections via napoleon) and CI builds the site with `-W`: free text after a `Parameters` list goes under a `Notes` heading, not flush against the list.
- An example added under `examples/` is registered in `examples/run_and_compile.py` or `examples/run_all.py`; CI runs both and fails if any example raises or does not compile.
- **Do not add** files under `docs/agent/` or `tests/agent/`.

## Tests

Keep the suite layered (~100 modules). Prefer extending existing batteries over new files.

| Layer | Purpose | Needs |
|-------|---------|--------|
| `tests/unit` | Object model, emitted script text | — |
| `tests/parser` | Parse, recovery, fixed point | — |
| `tests/integration` | Truth after GLE compiles (ink, cairo, accept) | GLE binary, skipped when absent |

- Add cases to the relevant module or battery (`test_fixed_point.py`, `tests/parser/_golden_battery.py`, `_*_battery.py` helpers). **New file = new behavior area.**
- No integration test that only duplicates a unit-level script assertion.
- Any emission change must keep the fixed point green.
- A test that shells out to GLE carries **`@pytest.mark.gle`** (or a module-level `pytestmark`). `tests/conftest.py` skips marked tests when the binary is missing, so do not write a per-file availability check. This applies in every layer, parser and unit tests included. The `test-without-gle` CI job runs the suite with no GLE installed and fails on an unmarked test.
- **Coverage** is a branch finder, not a score to chase: no `fail-under` gate. After your change, run `pytest --cov=gleplot.<module> --cov-report=term-missing` on touched modules; add a test only for branches you changed without an assertion.

```bash
pip install -e ".[dev]"

pytest tests/ -v
pytest tests/unit/ -v
pytest tests/parser/ -v
pytest tests/integration/ -v
```

## Conventions

- **Format**: black + isort (line-length 88) and flake8 are enforced by the CI `lint` job over `src tests examples docs`. mypy runs there too but is advisory until its existing errors are cleared; do not add new ones. Use the black major pinned in `pyproject.toml`.
- **License**: GPL-2.0+.
- **Commits**: conventional commits; `python-semantic-release` — `feat` → minor, `fix`/`perf` → patch. Version: `pyproject.toml` and `src/gleplot/__init__.py:__version__`.

## Where to look next

- `docs/guides/README.md` indexes the topic guides (including `MATPLOTLIB_MIGRATION.md`, `TESTING.md`, `VERSIONING.md`); `docs/source/` is the Sphinx site.
# AGENTS.md

Shared contract for AI coding agents in this repository. It has two kinds of content, and they fail differently:

- **The map** (what gleplot is, the architecture map) describes the code. Where it disagrees with the code, the code is right: correct the map in the same change.
- **The rules** (everything else) describe the repository as it should be. Where existing code breaks a rule, the rule is right. That code is debt, not precedent: do not copy it and do not add to it. Bring it into line when your change already rewrites it; otherwise leave it for its own change. What is known to fall short is listed under [Known debt](#known-debt).

## What gleplot is

gleplot is a **matplotlib-compatible Python library** that generates **GLE (Graphics Layout Engine)** scripts for publication-quality vector graphics. `import gleplot as glp`; familiar matplotlib calls (`figure`, `subplots`, `plot`, `scatter`, `bar`, `errorbar`, `savefig`, `view`) produce a `.gle` script and, when GLE is installed, compile it to PDF/PNG/EPS/SVG/JPG. `open_gle()` reads a `.gle` file back into a `Figure`.

**Scope.** A library and nothing else. The desktop GUI and the calibration tooling were removed in 3.0; do not bring them back. No 3D, animation, or interactive widgets. numpy is the only runtime dependency, and GLE is never bundled.

## Priorities

When two rules pull in different directions, the earlier one wins:

1. **A user's figure keeps working.** The same script produces the same output, and a `.gle` file gleplot or a person wrote still loads and saves without loss.
2. **A matplotlib name behaves like matplotlib.**
3. **The smallest change that does the job.** Less code, fewer names, fewer files.

## Before you call a change done

Run what CI runs. All of it must pass; none of it may be skipped by editing the check.

```bash
pip install -e ".[dev]"
python -c "import gleplot; print(gleplot.__file__)"   # must be this checkout's src/

pytest tests/
black --check src tests examples docs
isort --check-only src tests examples docs
flake8 src tests examples docs
mypy src
```

If you touched a docstring, a page under `docs/`, or an example, also run the docs and examples steps in [CONTRIBUTING.md](CONTRIBUTING.md) (they need GLE). Then check the working tree: `git status` shows only files you meant to change, and no generated `.gle`, `.dat`, image, or scratch file is staged. Say plainly in your summary what you could not run.

## Architecture map

### Core library (`src/gleplot/`)

- `__init__.py` — public API: `Figure`, `Axes`, config classes, module-level functions (`figure`, `subplots`, `plot`, …), `open_gle()`. `__all__` is the list of public names.
- `figure.py` — `Figure`: subplot layout, `savefig`, `view`, byte-stable `to_dict()`/`from_dict()` (serialization).
- `axes.py` — `Axes`: plot primitives, log scales, secondary axes, `*_from_file` series.
- `series.py` — typed series classes on `Axes` plus `SERIES_CLASSES` (serialization/emission order). Each class is a `dict` subclass; `to_dict()` stays byte-identical.
- `sources.py` — `data_source`: `InlineData`, `ColumnRef`/`GridRef`, `DataProvider`, `DanglingSourceRef`. Field name is `data_source` (not heatmap/contour `source`).
- `writer.py` — object model → GLE text; write-time `resolve_figure` / `SourceResolution`. `data_provider` is per `savefig`, never stored on the figure; warnings on `Figure.source_warnings`.
- `compiler.py` — `GLECompiler`, `find_gle()`; external `gle` binary.
- `config.py` — `GLEStyleConfig`, `GLEGraphConfig`, `GLEMarkerConfig`, `GlobalConfig`.
- `colors.py`, `markers.py` — matplotlib→GLE mappings.
- `dataio.py` — delimited file loading.
- `guides.py` — guide subs and write-time routing (`Axes.guide_needs_engine_range`); no extra model field for engine-range guides.
- `brokenaxes.py` — `BrokenAxes`: a split x-axis built from adjacent graph blocks.
- `mathtext.py` — matplotlib `$...$` mathtext → GLE text markup.
- `palettes.py` — colormap stop tables and the self-contained palette subs emitted for heatmaps/contours.
- `cairo_support.py` — decides when a figure needs GLE's `-cairo` device and warns about fonts it rejects.
- `_warn.py` — `warn_external`: a warning attributed to the first frame outside gleplot. A leaf module.

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
- **Layers** — nothing under `src/gleplot` imports a GUI toolkit, and IPython is imported only inside `Figure.view`. The parser syntax layer is stdlib-only. Module-level imports are acyclic: `series`/`sources` and the leaf modules (`_warn`, `colors`, `markers`, `config`) sit below `writer`, then `axes`, then `figure`, then `parser.recognizer`. Do not hide a cycle inside a function: `tests/unit/test_layering.py` checks the graph, holds function-level imports to an explicit list, and holds third-party imports to the declared runtime dependencies.
- **Preservation** — unrecognized GLE is preserved; recovery warnings are surfaced, not dropped silently.
- **Metadata** — v1 files load (implicit placement); first save rewrites to v2 with a `metadata:` warning. No downgrade. Unknown meta versions warn.
- **GLE optional** — saving `.gle` always works without GLE. Discovery: `GLE_PATH` → `PATH` → well-known paths (`compiler.find_gle`).

A check that guards an invariant (the empty exemption set, the allowed deferred imports, a `-W` docs build, a lint rule) is part of the invariant. If your change trips one, fix the change. Widening the check, adding an exemption, an `xfail`, a `skip`, a `# noqa` or a `# type: ignore` is a design decision for the maintainer: stop and ask.

## Public API and what users see

### Matplotlib compatibility

Every public function or `Axes` method that shares a name with matplotlib matches matplotlib's **parameter names**, **positional order**, and **defaults**. Check the matplotlib signature before adding or changing one; do not work from memory.

Where GLE cannot express a keyword: **accept it**, emit a **`UserWarning`**, and document the gap in `docs/guides/MATPLOTLIB_MIGRATION.md`.

Gleplot-specific API stays explicit and is not disguised as matplotlib: `data_prefix`, `data_source`, placement in cm, `open_gle`, `GLE*Config`. **`figsize` stays in inches.**

### Errors and warnings

- Reject a bad argument **when the call is made**, not later at `savefig`. Raise `ValueError` (or `TypeError` for a wrong type) with a message that names the argument, shows the value received, and lists what is accepted.
- Anything gleplot accepts but cannot honour, or recovers imperfectly from a file, gets a `UserWarning` raised through `_warn.warn_external`, which attributes it to the caller's line however deep the call. Nothing is dropped silently. `tests/unit/test_source_rules.py` fails on a `warnings.warn` called anywhere else.
- A message is written for someone who knows matplotlib and has never read this source: say what to do next, in terms of the public API.
- No `print()` in library code; `tests/unit/test_source_rules.py` checks this. Results go through return values, exceptions, and warnings. Diagnostic output a user opts into goes through the `gleplot` logger.

### Compatibility

- Removing or renaming a public name, changing a default, or changing emitted GLE for an existing script is a **breaking change**. It needs the maintainer's agreement and a `feat!`/`fix!` commit.
- Emitted GLE is output users keep under version control. Do not reorder or reformat it as a side effect of another change.
- Private names (leading underscore) may change freely. Do not add a compatibility alias or shim for one.

## Lean changes

- Extend existing series classes, writer branches, or `_layout_rects`. Write-time routing (guides, source resolution) is not a new persisted field unless the model truly needs it.
- New public names, series fields, or config knobs need a **caller in the same change** and a reason a user would reach for them. A helper used once stays inline.
- Solve the case in front of you. No option, hook, or abstraction for a use nobody has asked for.
- A change that replaces code deletes what it replaced, including its tests, docs, and examples. No commented-out code, no "kept for reference" copies.
- Fix the cause in the layer that owns it. A recognizer workaround for a writer bug, or a special case that makes one test pass, is not a fix.
- Keep the diff to the task. A drive-by refactor or reformat goes in its own change.
- Comments explain **invariants** or **GLE constraints**, not obvious code, and not the history of the change.
- **Python ≥3.9**; no new dependency for a small feature.
- A function does one thing. Do not add another series kind or another option to a function that already branches over many; give the new case its own method and call it. The dispatchers this applies to most are `Figure._write_drawables`, `GLEWriter.add_axes` and `_Recognizer._parse_graph_block`.
- A module has the one job the map gives it. Line count alone is not a reason to split `writer.py`, `axes.py`, or `recognizer.py`; a split follows a real seam and is agreed with the maintainer first, because it moves every import and the layering test with it.

### Adding a series field

A field on a series class is usually touched in five places; missing one breaks the fixed point or silently drops the field on reload:

1. the class annotation in `series.py` (absent means the historical behaviour — do not default to `None`),
2. the `Axes` method that sets it,
3. the `GLEWriter.add_*` method that emits it,
4. the per-kind `Figure._write_<kind>` method (`_write_line`, `_write_bar`, …, or `_write_file_series`) that passes it through,
5. the `_Recognizer` branch that recovers it.

Then add a builder exercising it to `tests/parser/_golden_battery.py`, which `test_fixed_point.py` runs.

## Documentation

Docs describe what the code does now. A change in behaviour updates every place that describes it, in the same change: the docstring, the Sphinx API page, the topic guide, and any example that shows it.

- **`docs/`** is user and contributor documentation only. Design notes, plans, and implementation journals go in [GitHub issues](https://github.com/benhuddart/gleplot/issues). **Do not add** files under `docs/agent/` or `tests/agent/`, or status/summary markdown anywhere in the repo.
- Extend an existing guide before adding one. A new guide is a Markdown file in `docs/guides/`, published by a page in `docs/source/guides/` that includes it, and listed in the toctree for its section in `docs/source/index.rst`. A guide is shown both on GitHub and on the site, so it links to other guides by relative path and to anything else by full URL.
- A new public name gets an entry in the Sphinx API pages (`docs/source/api*.rst`) in the same change, not only a guide mention.
- Docstrings are rendered by Sphinx (numpydoc sections via napoleon) and CI builds the site with `-W`: free text after a `Parameters` list goes under a `Notes` heading, not flush against the list.
- Reference material is generated from docstrings. Do not hand-write an option table in a guide.
- Code shown in docs and docstrings must run against the current API. Do not describe behaviour you have not exercised.
- An example added under `examples/` is added to the registry in `examples/run_and_compile.py`; CI runs and compiles every registered example and fails on one that is not registered. The gallery is generated from the registry, and an example's docstring is its caption there.
- Examples write only to `examples/outputs/`, which is ignored. No generated figure or sidecar is committed.
- State facts once. Link to a guide instead of repeating it, and do not put counts or version numbers in prose that nothing will keep current.

## Tests

Keep the suite layered. Put a test in the lowest layer that can prove the point, and prefer extending an existing battery over a new file.

| Layer | Purpose | Needs |
|-------|---------|--------|
| `tests/unit` | Object model, emitted script text | — |
| `tests/parser` | Parse, recovery, fixed point | — |
| `tests/integration` | Truth after GLE compiles (ink, cairo, accept) | GLE binary, skipped when absent |

- A bug fix comes with a test that fails without the fix. A behaviour change updates the tests that pinned the old behaviour; say so in the commit rather than quietly editing expected values.
- Add cases to the relevant module or battery (`test_fixed_point.py`, `tests/parser/_golden_battery.py`, `_*_battery.py` helpers). **New file = new behavior area.**
- Assert on behaviour a user could observe (emitted script, recovered model, drawn ink), not on private helpers.
- No integration test that only duplicates a unit-level script assertion.
- Any emission change must keep the fixed point green.
- A test that shells out to GLE carries **`@pytest.mark.gle`** (or a module-level `pytestmark`). `tests/conftest.py` skips marked tests when the binary is missing, so do not write a per-file availability check. This applies in every layer. The `test-without-gle` CI job runs the suite with no GLE installed and fails on an unmarked test.
- Tests are plain pytest functions with fixtures, and write only under `tmp_path`: never into the source tree, `build/`, or the current directory.
- **Coverage** is a branch finder, not a score to chase: no `fail-under` gate. After your change, run `pytest --cov=gleplot.<module> --cov-report=term-missing` on touched modules; add a test only for branches you changed without an assertion.

More detail, including the output analyzers: `docs/guides/TESTING.md`.

## Conventions

- **Format and types**: black + isort (line-length 88), flake8 and mypy are enforced by the CI `lint` job. Use the black and mypy majors pinned in `pyproject.toml`. Fix a type error with an annotation or by narrowing; `warn_return_any` is off because series and data sources are `dict` subclasses whose accessors return `Any` by design.
- **License**: GPL-2.0+.
- **Commits**: conventional commits, and the type decides the release. `python-semantic-release` publishes a minor for `feat`, a patch for `fix`/`perf`, a major for `!` or a `BREAKING CHANGE:` footer, and nothing for `docs`, `test`, `refactor`, `style`, `ci`, `build`, `chore`. Pick the type by what a user of the installed package would notice, so a docs or test change is never a `fix`.
- **Releases are automatic.** Do not edit the version in `pyproject.toml` or `src/gleplot/__init__.py`, and do not edit `docs/CHANGELOG.md`; the release job writes all three from the commit history.

## Keeping this file useful

- Moving, renaming, adding, or removing a module updates the architecture map in the same change. Changing an invariant updates its bullet and the test that guards it together.
- This file holds rules and a map, not a tutorial or a history. If a rule can be enforced by a test or a lint check, add the check and shorten the rule to a pointer.
- Add a rule only for a mistake that has actually happened or would be expensive. Remove a rule when the thing it guarded is gone.

## Known debt

Places where the code does not yet meet the rules above. None of them is a pattern to follow. Each entry is deleted by the change that fixes it. The plan for each fix lives in the linked issue, and [#111](https://github.com/benhuddart/gleplot/issues/111) tracks the order.

- **Series logic is spread over five modules.** The "Adding a series field" checklist exists because one field is declared, set, emitted, passed through, and recovered in five separate places. The intended form is one description per series kind that those places read. Until then, follow the checklist. [#100](https://github.com/benhuddart/gleplot/issues/100)
- **Oversized dispatch functions**: `GLEWriter.add_axes`, `_Recognizer._parse_graph_block` and `_Recognizer.run` each run to hundreds of lines. [#109](https://github.com/benhuddart/gleplot/issues/109)

## Where to look next

- The Sphinx site under `docs/source/` is the one index; the topic guides in `docs/guides/` are pages of it.

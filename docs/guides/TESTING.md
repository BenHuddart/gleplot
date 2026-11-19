# Testing

## Running the suite

```bash
pip install -e ".[dev]"

pytest tests/                 # everything
pytest tests/unit/            # object model and emitted script text
pytest tests/parser/          # parsing, recovery, fixed point
pytest tests/integration/     # output after GLE has compiled it
```

The whole suite takes well under a minute. Useful variations:

```bash
pytest tests/unit/test_plotting.py::TestBasicPlotting   # one class
pytest tests/ -k errorbar                                # by keyword
pytest tests/ --durations=10                             # slowest tests
pytest --cov=gleplot.writer --cov-report=term-missing tests/
```

Coverage is a way to find untested branches in the module you changed, not a
target; there is no minimum.

## Layers

| Directory | What it asserts | Needs GLE |
|-----------|-----------------|-----------|
| `tests/unit` | The object model and the `.gle` text gleplot emits | No |
| `tests/parser` | Lexing, parsing, recovery warnings, and the writer/parser fixed point | No |
| `tests/integration` | What GLE actually renders: files exist, ink lands where expected | Yes |

Put a test in the lowest layer that can prove the point. An integration test
that only repeats a script-text assertion from `tests/unit` adds runtime and
no information.

## Tests that need GLE

GLE is optional, and the suite must pass without it. A test that shells out to
the `gle` binary carries the `gle` marker:

```python
import pytest

@pytest.mark.gle
def test_step_histogram_compiles(tmp_path):
    ...

# or for a whole module
pytestmark = pytest.mark.gle
```

`tests/conftest.py` skips marked tests when the binary is missing, so do not
write your own availability check. This applies in every directory: a unit or
parser test that compiles needs the marker too.

Two CI jobs keep this honest. `test` runs everything against a pinned GLE on
Ubuntu, macOS and Windows: it builds GLE on Ubuntu and macOS, and uses
upstream's prebuilt static build on Windows (on Ubuntu it also runs the
examples and a strict Sphinx build);
`test-without-gle` runs the suite on a machine with no GLE and fails if an
unmarked test tries to compile.

To install GLE locally, see the
[getting started guide](https://benhuddart.github.io/gleplot/getting_started.html).
`gle -info` confirms it is on `PATH`; set `GLE_PATH` to pick a specific binary.

## The fixed point

Saving a figure, parsing the `.gle` back with `parse_gle_figure`, and saving
again must produce byte-identical output, including the `.dat` sidecars.
`tests/parser/test_fixed_point.py` runs this over every figure builder in
`tests/parser/_golden_battery.py` and `tests/integration/test_project_io.py`.

Its exemption set is empty and a test asserts that it stays empty. If your
change makes a builder fail, the writer or the recognizer has a bug; fix that
rather than exempting the builder.

When you add something the writer emits (a series field, a new option), add a
builder that uses it to `_golden_battery.py`.

## Batteries

Several behaviour areas keep their cases in a shared helper so the unit and
integration layers exercise the same figures:

- `tests/parser/_golden_battery.py` — figures for the fixed point
- `tests/unit/_degenerate_battery.py` — degenerate autoscale ranges
- `tests/unit/_refline_battery.py` — reference lines and spans
- `tests/unit/_single_bar_battery.py` — single-bar width handling

Add a case to the relevant battery before creating a new test file. A new file
is for a new behaviour area.

## Checking compiled output

`tests/integration/graphics_analysis.py` has small analyzers for compiled
files:

```python
from tests.integration.graphics_analysis import (
    EPSAnalyzer, PDFAnalyzer, PNGAnalyzer, validate_graphics_file,
)

assert PDFAnalyzer(path).is_valid_pdf()
width, height = PNGAnalyzer(path).get_image_dimensions()
```

Tests that need to know *what GLE drew*, not just that a file exists, avoid
decoding images where they can:

- `tests/integration/test_ink_on_page.py` wraps the script in a `begin name`
  block and reads back its corner points, which gives the true bounding box
  of the ink, including anything that fell off the page.
- `tests/integration/test_line_style_rendering.py` reads the dash pattern GLE
  writes into its EPS output.
- `tests/integration/test_guide_marker_compiles.py` compares rasters with
  Pillow (in the `dev` extra) when two scripts must render identically.

## Writing a test

- Use pytest functions and the `tmp_path` fixture.
- Call `glp.close()` before and after tests that use the module-level
  `glp.plot(...)` API, so figures do not leak between tests.
- Run `black`, `isort` and `flake8` over `tests`; the CI `lint` job checks
  them.

## Known platform issue

GLE 4.3.9 on the macOS ARM CI runners crashes rendering `begin contour`
blocks. Those tests carry the non-strict `darwin_gle_contour_crash` xfail from
`tests/integration/conftest.py`.

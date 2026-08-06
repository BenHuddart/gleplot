"""Compiled proof that a figure's ink stays on its page.

Every other layout test asserts on the *numbers gleplot emits*. This one
asserts on what GLE actually draws: it wraps the whole script body in a
``begin name`` block and prints the block's corner points, which gives the
true bounding box of the rendered ink -- including ink that falls off the
page, which a raster or PDF-bbox measurement would silently clip away, i.e.
exactly the defect being guarded against.

The guarded defect: until the decoration margins were unified (see
``Figure._auto_margins_cm``), a multi-plot grid used fixed 1.0 cm / 1.5 cm
margins, less than the ~1.32 cm that a y-axis title plus tick labels like
"-0.5" occupy at the default 12 pt -- so a 2x2 grid with axis labels put its
leftmost decoration off the left edge of the page. Skipped when GLE is not
installed.
"""

from __future__ import annotations

import re
import subprocess

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler, find_gle


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")

_SIZE_RE = re.compile(r"^size ([\d.eE+-]+) ([\d.eE+-]+)\s*$", re.MULTILINE)
_INK_RE = re.compile(r"INKBOX ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+)")

#: How far ink may fall outside the page before the test fails (cm). Zero
#: would be the honest bar, but GLE's own line joins round outward by a hair;
#: this is well under a tick label's height.
_TOLERANCE_CM = 0.01


def _instrument(text: str) -> str:
    """Wrap the drawing body of a gleplot script in a printed named block."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("size "):
            break
    else:  # pragma: no cover - every gleplot script sets a page size
        raise AssertionError("no page size line in generated script")
    return "\n".join(
        lines[: i + 1]
        + ["begin name inkbox"]
        + lines[i + 1 :]
        + [
            "end name",
            'print "INKBOX" ptx(inkbox.bl) pty(inkbox.bl) '
            "ptx(inkbox.tr) pty(inkbox.tr)",
            "",
        ]
    )


def _overhang_cm(fig, tmp_path):
    """``(left, bottom, right, top)`` cm by which compiled ink escapes the page.

    Negative values are slack: the ink is that far inside the edge.
    """
    fig.savefig_gle(str(tmp_path / "figure.gle"))
    text = (tmp_path / "figure.gle").read_text(encoding="utf-8")
    page = _SIZE_RE.search(text)
    assert page is not None
    page_w, page_h = float(page.group(1)), float(page.group(2))

    (tmp_path / "probe.gle").write_text(_instrument(text), encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    found = _INK_RE.search(proc.stdout + proc.stderr)
    assert (
        found is not None
    ), f"GLE did not report an ink box:\n{proc.stdout}\n{proc.stderr}"
    x0, y0, x1, y1 = (float(v) for v in found.groups())
    return (-x0, -y0, x1 - page_w, y1 - page_h)


def _labelled_grid(rows, cols, **kwargs):
    """A grid whose y tick labels ("-1", "-0.5") are the wide, negative kind."""
    fig, axes = glp.subplots(rows, cols, figsize=(8, 6), data_prefix="ink", **kwargs)
    axes = axes if isinstance(axes, list) else [axes]
    for ax in axes:
        ax.plot(np.array([0.0, 1.0, 2.0]), np.array([-1.0, -0.5, -1.0]))
        ax.set_xlabel("time")
        ax.set_ylabel("voltage")
    return fig


def _assert_on_page(fig, tmp_path):
    over = _overhang_cm(fig, tmp_path)
    worst = max(over)
    assert worst <= _TOLERANCE_CM, (
        "compiled ink falls off the page by "
        f"(left, bottom, right, top) = {tuple(round(v, 3) for v in over)} cm"
    )


@pytest.fixture(autouse=True)
def _fresh_figure_registry():
    glp.close()
    yield
    glp.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"sharex": True},
        {"sharey": True},
        {"sharex": True, "sharey": True},
    ],
    ids=["plain", "sharex", "sharey", "shared"],
)
def test_a_labelled_2x2_grid_keeps_its_decoration_on_the_page(kwargs, tmp_path):
    """The reported defect, in every sharing mode a grid has."""
    _assert_on_page(_labelled_grid(2, 2, **kwargs), tmp_path)


@pytest.mark.parametrize("shape", [(1, 1), (1, 3), (3, 1), (2, 2), (3, 3)], ids=str)
def test_every_grid_shape_keeps_its_decoration_on_the_page(shape, tmp_path):
    """Including 1x1: one margin policy has to hold for all of them."""
    _assert_on_page(_labelled_grid(*shape), tmp_path)


@pytest.mark.parametrize("fontsize", [8, 12, 18])
def test_the_margins_track_the_font_size(fontsize, tmp_path):
    """Decoration overflow scales with ``hei``, so the margins must too.

    A fixed-centimetre margin that just fits at 12 pt clips at 18 pt; this is
    why the constants are expressed in ``hei`` units.
    """
    fig = _labelled_grid(2, 2, style=glp.GLEStyleConfig(fontsize=fontsize))
    _assert_on_page(fig, tmp_path)


def test_a_titled_grid_keeps_its_titles_on_the_page(tmp_path):
    fig = _labelled_grid(2, 2)
    for idx, ax in enumerate(fig.axes_list, start=1):
        ax.set_title(f"panel {idx}")
    _assert_on_page(fig, tmp_path)


def test_a_grid_with_a_secondary_y_axis_keeps_it_on_the_page(tmp_path):
    fig = _labelled_grid(1, 2)
    for ax in fig.axes_list:
        ax.plot(
            np.array([0.0, 1.0, 2.0]),
            np.array([100.0, 200.0, 150.0]),
            yaxis="y2",
        )
        ax.set_ylabel("current", axis="y2")
    _assert_on_page(fig, tmp_path)

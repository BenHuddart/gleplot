"""An inverted axis compiles, and really is drawn upside down.

``ax.set_ylim(3, 1)`` used to emit ``yaxis min 3 max 1``, which GLE refuses:
"Error: illegal range for yaxis: min = 3 max = 1". It now emits an ascending
range plus ``negate``, so these tests check both halves of that: that the
script builds, and that the axis it builds is actually reversed.

The second half is measured rather than asserted about the script text. GLE's
``yg()``/``xg()`` map a data value to a page coordinate through the same
transform the plotted data goes through (``graph_ygraph`` in ``graph2.cpp``),
so printing them is a direct read of which way up the axis ended. Skipped
when GLE is not installed.
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


pytestmark = [
    pytest.mark.skipif(not _gle_available(), reason="GLE binary not available"),
    pytest.mark.filterwarnings("ignore:.*log axis.*:UserWarning"),
]

_PROBE_RE = re.compile(r"PROBE ([\d.eE+-]+) ([\d.eE+-]+)")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _page_coords_of(fig, tmp_path, expr_lo, expr_hi):
    """Page cm of two data values, via GLE's own xg()/yg() mapping.

    Compiles the figure as written, so a script GLE rejects fails here.
    """
    gle_path = tmp_path / "figure.gle"
    fig.savefig_gle(str(gle_path))
    text = gle_path.read_text(encoding="utf-8")
    assert "end graph" in text
    probed = text.replace(
        "end graph",
        f'end graph\nprint "PROBE" {expr_lo} {expr_hi}',
        1,
    )
    (tmp_path / "probe.gle").write_text(probed, encoding="utf-8")

    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
    found = _PROBE_RE.search(out)
    assert found is not None, f"GLE did not compile the script:\n{out}"
    return float(found.group(1)), float(found.group(2))


def _plot(**limits):
    fig = glp.figure(data_prefix="invc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), marker="o")
    if "xlim" in limits:
        ax.set_xlim(*limits["xlim"])
    if "ylim" in limits:
        ax.set_ylim(*limits["ylim"])
    return fig


def test_a_descending_y_range_compiles_and_reverses_the_axis(tmp_path):
    low, high = _page_coords_of(_plot(ylim=(3, 1)), tmp_path, "yg(1)", "yg(3)")
    assert low > high, "y=1 should sit ABOVE y=3 on an inverted axis"


def test_a_descending_x_range_compiles_and_reverses_the_axis(tmp_path):
    left, right = _page_coords_of(_plot(xlim=(3, 1)), tmp_path, "xg(1)", "xg(3)")
    assert left > right, "x=1 should sit RIGHT of x=3 on an inverted axis"


def test_an_ascending_range_is_still_the_right_way_up(tmp_path):
    """Guards the inversion against applying itself to ordinary figures."""
    low, high = _page_coords_of(_plot(ylim=(1, 3)), tmp_path, "yg(1)", "yg(3)")
    assert low < high


def test_a_descending_secondary_y_axis_compiles(tmp_path):
    fig = glp.figure(data_prefix="invc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0]), yaxis="y2")
    ax.set_ylim(40, 5, axis="y2")
    ax.set_ylabel("secondary", axis="y2")
    out = fig.savefig(str(tmp_path / "y2.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_a_shared_inverted_grid_compiles(tmp_path):
    fig, axes = glp.subplots(2, 1, sharey=True, data_prefix="invc")
    for ax in axes:
        ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    axes[0].set_ylim(9, 1)
    out = fig.savefig(str(tmp_path / "shared.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_a_descending_log_range_compiles_upright(tmp_path):
    """GLE cannot invert a log axis, so gleplot draws it the usual way round."""
    fig = _plot(ylim=(100, 1))
    fig.axes_list[0].set_yscale("log")
    low, high = _page_coords_of(fig, tmp_path, "yg(1)", "yg(100)")
    assert low < high


def test_an_inverted_axis_with_guides_and_annotations_compiles(tmp_path):
    """axhline/axhspan resolve their fractions against the same limit pair."""
    fig = glp.figure(data_prefix="invc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_ylim(3, 1)
    ax.axhline(2.0, color="red")
    ax.axhspan(1.5, 2.5, color="lightblue", alpha=0.3)
    ax.text(2.0, 2.0, "middle")
    out = fig.savefig(str(tmp_path / "guides.pdf"))
    assert out.exists() and out.stat().st_size > 0

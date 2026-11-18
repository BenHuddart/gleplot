"""Per-point marker sizes are drawn at their sizes once GLE compiles them.

The script text is asserted in ``tests/unit/test_scatter_sizing.py``. This
checks the ink: GLE draws ``FCIRCLE`` as a PostScript ``arc``, so the radii in
the EPS are the marker sizes. Skipped when the binary is missing.
"""

from __future__ import annotations

import re

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle

_ARC_RE = re.compile(r"newpath [\d.eE+-]+ [\d.eE+-]+ ([\d.eE+-]+) 0 360 arc")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _radii(fig, tmp_path):
    out = tmp_path / "sizes.eps"
    fig.savefig(str(out))
    return [float(r) for r in _ARC_RE.findall(out.read_text(encoding="latin-1"))]


def test_each_point_is_drawn_at_its_own_size(tmp_path):
    reference = glp.figure(data_prefix="ref")
    reference.add_subplot(111).scatter([1], [1], s=400, color="blue")
    (r_400,) = _radii(reference, tmp_path)

    fig = glp.figure(data_prefix="sizes")
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3, 4], [1, 2, 3, 4], s=[100, 400, 900, 0], color="red")
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    # Area semantics: 1/4 and 9/4 of the area are 1/2 and 3/2 the radius,
    # the same s draws the same marker as a one-size scatter, and s=0 draws
    # nothing.
    assert _radii(fig, tmp_path) == pytest.approx(
        [r_400 / 2, r_400, 1.5 * r_400], rel=1e-3
    )


def test_points_gle_drops_leave_the_sizes_aligned(tmp_path):
    """A NaN point, and a negative one on a log axis, are not drawn; the
    others keep their own sizes (GLE refuses mismatched ``mdata`` counts)."""
    reference = glp.figure(data_prefix="ref")
    reference.add_subplot(111).scatter([1], [1], s=400, color="blue")
    (r_400,) = _radii(reference, tmp_path)

    fig = glp.figure(data_prefix="gaps")
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3, 4], [1, float("nan"), -3, 4], s=[100, 1, 1, 900])
    ax.set_yscale("log")
    ax.set_ylim(0.5, 5)
    assert _radii(fig, tmp_path) == pytest.approx([r_400 / 2, 1.5 * r_400], rel=1e-3)

"""Per-point colours are drawn in their colours once GLE compiles them.

The script text is asserted in ``tests/unit/test_scatter_colours.py``. This
checks the ink: GLE draws ``FCIRCLE`` as a PostScript ``arc``, and the colour
set just before each one is that point's colour. Skipped when the binary is
missing.
"""

from __future__ import annotations

import re

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle

_ARC_COLOUR_RE = re.compile(
    r"([\d.]+) ([\d.]+) ([\d.]+) setrgbcolor\n(?:(?!.*setrgbcolor).*\n)*?"
    r" newpath [\d.eE+-]+ [\d.eE+-]+ [\d.eE+-]+ 0 360 arc"
)

# matplotlib's viridis at 0, 0.5 and 1.
_FIRST = (0.267004, 0.004874, 0.329415)
_MIDDLE = (0.127568, 0.566949, 0.550556)
_LAST = (0.993248, 0.906157, 0.143936)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _point_colours(fig, tmp_path):
    out = tmp_path / "colours.eps"
    fig.savefig(str(out))
    text = out.read_text(encoding="latin-1")
    return [tuple(float(v) for v in m) for m in _ARC_COLOUR_RE.findall(text)]


def test_each_point_is_drawn_in_its_own_colour(tmp_path):
    fig = glp.figure(data_prefix="colours")
    ax = fig.add_subplot(111)
    # A NaN value is not drawn; values outside vmin..vmax take the end colour.
    ax.scatter(
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        c=[-50, 5, float("nan"), 10, 99],
        vmin=0,
        vmax=10,
    )
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 6)
    colours = _point_colours(fig, tmp_path)
    assert len(colours) == 4
    for got, want in zip(colours, [_FIRST, _MIDDLE, _LAST, _LAST]):
        # The palette sub interpolates matplotlib's table piecewise.
        assert got == pytest.approx(want, abs=0.01)

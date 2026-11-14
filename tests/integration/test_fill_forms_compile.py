"""Axis fills, clipped bands, and polygon fills compile on GLE.

The script text is asserted in ``tests/unit/test_plotting.py``. This checks
the part a string match cannot: that ``fill x1,dN``, ``fill dA,dB xmin``,
and ``fill dN`` (including an ``rgba255`` polygon) are scripts GLE accepts.
Skipped when the binary is missing.
"""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler


def _gle_available() -> bool:
    try:
        GLECompiler()
    except RuntimeError:
        return False
    return True


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_axis_clip_and_polygon_fills_compile(tmp_path):
    fig = glp.figure(data_prefix="fillc")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.fill_between(x, [1, 2, 2, 1], baseline="x1", color="gray")
    ax.fill_between(
        x,
        [1, 3, 2, 2],
        [0, 1, 1, 0],
        where=[False, True, True, False],
        color="blue",
        alpha=0.4,
    )
    ax.fill([0, 1, 0.5], [0, 0, 1], color="red", alpha=0.4)
    ax.set_ylim(0, 4)
    out = tmp_path / "fills.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

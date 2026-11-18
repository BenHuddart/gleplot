"""A polar axes compiles, with its title, angle labels and ring labels.

The script text is asserted in ``tests/unit/test_polar.py``. This checks that
GLE accepts the polar subs and ``let`` lines, and that the labels written
after ``end graph`` reach the page. Skipped when the binary is missing.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_polar_axes_with_curves_and_title_compiles(tmp_path):
    fig = glp.figure(figsize=(6, 3))
    ax = fig.add_subplot(projection="polar")
    theta = np.linspace(0, 2 * np.pi, 50)
    ax.plot(theta, 1 + 0.5 * np.cos(3 * theta), marker="o", label="lobes")
    ax.function("cos(2*x)", linestyle="--", label="rose")
    ax.set_title("Polar")
    ax.legend()
    out = tmp_path / "polar.eps"
    fig.savefig(str(out))
    eps = out.read_text(encoding="latin-1")
    # GLE writes text one glyph at a time: '(P) s'.
    glyphs = "".join(re.findall(r"^\((.)\) s$", eps, flags=re.MULTILINE))
    for word in ("Polar", "lobes", "rose", "04590135180225270315"):
        assert word in glyphs
    # The ring labels 0.5, 1.0, 1.5; the points are not single-glyph shows.
    assert "051015" in glyphs

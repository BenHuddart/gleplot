"""A box plot compiles, with its tick labels.

The script text is asserted in ``tests/unit/test_boxplot.py``. This checks
that GLE accepts the ``gleplot_box`` subs and their calls after ``end
graph``. Skipped when the binary is missing.
"""

from __future__ import annotations

import re

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_box_plot_with_fliers_means_and_tick_labels_compiles(tmp_path):
    fig, ax = glp.subplots()
    ax.boxplot(
        [[1, 2, 3, 4, 5, 6, 7, 8, 9, 100], [2, 3, 4]],
        tick_labels=["Frogs", "Hogs"],
        showmeans=True,
    )
    out = tmp_path / "box.eps"
    fig.savefig(str(out))
    eps = out.read_text(encoding="latin-1")
    # GLE writes text one glyph at a time: '(F) s'.
    glyphs = "".join(re.findall(r"^\((.)\) s$", eps, flags=re.MULTILINE))
    for word in ("Frogs", "Hogs"):
        assert word in glyphs

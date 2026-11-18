"""A pie chart compiles, with its title and every wedge's text.

The script text is asserted in ``tests/unit/test_pie.py``. This checks that
GLE accepts the ``gleplot_wedge`` calls after ``end graph`` and that the
hidden frame keeps the graph title. Skipped when the binary is missing.
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


def test_pie_with_labels_percentages_and_title_compiles(tmp_path):
    fig, ax = glp.subplots()
    ax.pie(
        [15, 30, 45, 10],
        labels=["Frogs", "Hogs", "Dogs", "Logs"],
        autopct="%1.1f%%",
        textprops={"fontsize": 14},
    )
    ax.set_title("Pets")
    out = tmp_path / "pie.eps"
    fig.savefig(str(out))
    eps = out.read_text(encoding="latin-1")
    # GLE writes text one glyph at a time: '(F) s'.
    glyphs = "".join(re.findall(r"^\((.)\) s$", eps, flags=re.MULTILINE))
    for word in ("Pets", "Frogs", "Hogs", "Dogs", "Logs"):
        assert word in glyphs

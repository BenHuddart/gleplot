"""Per-bar colour, edges, stacks, and horizontal bars compile on GLE.

The script text is asserted in the unit and parser suites. This checks
that the forms in issue 45 are scripts GLE accepts. Skipped when the
binary is missing.
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


def test_issue_45_bar_forms_compile(tmp_path):
    fig = glp.figure(data_prefix="barforms")
    ax = fig.add_subplot(111)
    x = [1, 2, 3]
    h1 = [2, 3, 4]
    h2 = [1, 2, 1]
    ax.bar(x, h1, width=0.4, label="a", edgecolor="k")
    ax.bar([v + 0.4 for v in x], h2, width=0.4, label="b")
    ax.bar(x, h2, bottom=h1, color="white")
    ax.barh([1, 2], [3, 4], color="teal")
    ax.legend()
    fig.savefig(str(tmp_path / "bars.png"))
    assert (tmp_path / "bars.png").exists()

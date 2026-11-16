"""Bar forms compile on GLE: colours, edges, stacks, and error bars.

The script text is asserted in the unit and parser suites. This checks
that the forms in issues 45 and 46 are scripts GLE accepts. Skipped
when the binary is missing.
"""

from __future__ import annotations

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


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


def test_issue_46_bar_errors_compile(tmp_path):
    """Symmetric, asymmetric, and horizontal-bar whiskers are scripts GLE accepts."""
    fig = glp.figure(data_prefix="barerr")
    ax = fig.add_subplot(111)
    ax.bar(
        [1, 2, 3],
        [2, 3, 4],
        yerr=([0.2, 0.1, 0.3], [0.4, 0.2, 0.1]),
        capsize=3,
        label="v",
    )
    ax.barh([1, 2], [3, 4], xerr=0.5, capsize=3, color="teal")
    ax.legend()
    fig.savefig(str(tmp_path / "barerr.png"))
    assert (tmp_path / "barerr.png").exists()

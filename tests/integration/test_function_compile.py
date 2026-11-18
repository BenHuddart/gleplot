"""Function curves compile on GLE.

The script text is asserted in ``tests/unit/test_plotting.py``. This checks
what a string match cannot: that the ``let`` gleplot writes, with and
without a range, beside ordinary data, is a script GLE accepts.
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


def test_function_curves_compile(tmp_path):
    fig = glp.figure(data_prefix="fnc")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.function("exp(-x^2/2)", xmin=-3, xmax=3, step=0.1, linestyle="--", label="g")
    ax.function("max(x,1)")
    ax.legend()
    out = tmp_path / "function.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

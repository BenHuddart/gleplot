"""Histograms compile on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_plotting.py``. This checks
the part a string match cannot: that ``let dK = hist`` followed by
``line hist`` or a full-width ``bar`` is a script GLE accepts.
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


def test_step_and_stepfilled_histograms_compile(tmp_path):
    fig = glp.figure(data_prefix="histc")
    ax = fig.add_subplot(111)
    samples = [0.0, 0.2, 0.4, 0.6, 0.9]
    ax.hist(samples, bins=4, range=(0, 1), histtype="step", color="blue")
    ax.hist(samples, bins=4, range=(0, 1), histtype="stepfilled", color="red")
    out = tmp_path / "hist.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

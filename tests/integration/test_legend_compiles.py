"""Bar, fill, and span legend swatches compile on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_legend.py``. This checks
the part a string match cannot: that ``dN key``, ``keyfill``, ``key
separator``, ``compact`` and ``background`` are a script GLE accepts.
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


def test_swatches_columns_and_background_compile(tmp_path):
    fig = glp.figure(data_prefix="legc")
    ax = fig.add_subplot(111)
    ax.bar([0, 1, 2], [1, 3, 2], color="C0", label="control")
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 2, 1], label="band", alpha=0.3)
    ax.plot([0, 1, 2], [0.5, 1.5, 0.5], label="fit")
    ax.axvspan(0.4, 1.2, color="orange", alpha=0.4, label="window")
    ax.legend(ncol=2, compact=True, facecolor="green")
    out = tmp_path / "legend.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

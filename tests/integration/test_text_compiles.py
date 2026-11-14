"""Aligned, rotated, and boxed text compiles on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_text.py``. This checks the
part a string match cannot: that ``begin rotate`` / ``begin box fill`` after
``end graph``, anchored with ``xg()``/``yg()``, is a script GLE accepts.
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


def test_aligned_rotated_boxed_text_compiles(tmp_path):
    fig = glp.figure(data_prefix="txtc")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.text(
        1,
        1,
        "peak",
        va="bottom",
        ha="center",
        rotation=45,
        bbox={"facecolor": "white"},
    )
    ax.text(0.2, 0.2, "note", va="top", ha="right", rotation=-20)
    out = tmp_path / "text.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

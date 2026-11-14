"""Step, stem and histogram line modes compile on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_plotting.py``. This checks
the part a string match cannot: that ``line steps``, ``line fsteps``,
``line hist``, ``line impulses`` and ``line bar`` are a script GLE accepts.
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


def test_every_line_mode_compiles(tmp_path):
    fig = glp.figure(data_prefix="lmode")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.step(x, [1, 2, 2, 1], where="pre")
    ax.step(x, [1, 3, 1, 2], where="post")
    ax.plot(x, [0, 1, 0, 1], drawstyle="steps-mid")
    ax.stem(x, [1, 0, 1, 0])
    ax.plot(x, [1, 2, 1, 2], line_mode="bar")
    out = tmp_path / "modes.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

"""Aligned, rotated, and boxed text compiles on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_text.py``. This checks the
part a string match cannot: that ``begin rotate`` / ``begin box fill`` after
``end graph``, anchored with ``xg()``/``yg()``, is a script GLE accepts.
Skipped when the binary is missing.
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


def test_annotation_arrows_compile(tmp_path):
    """``join`` from a named text box to a ``save``d point after ``end graph``."""
    fig, axes = glp.subplots(1, 2)
    for ax in axes:
        ax.plot([0, 1, 2], [0, 1, 0])
        ax.annotate(
            "peak", xy=(1, 1), xytext=(1.5, 0.5), arrowprops={"arrowstyle": "->"}
        )
        ax.annotate(
            "turn",
            xy=(0.5, 0.5),
            xytext=(0.2, 0.9),
            rotation=20,
            bbox={"facecolor": "white"},
            arrowprops={"arrowstyle": "<|-|>", "color": "red", "lw": 2},
        )
        ax.annotate(
            "line", xy=(2, 0), xytext=(1.6, 0.2), arrowprops={"arrowstyle": "-"}
        )
    out = tmp_path / "ann.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

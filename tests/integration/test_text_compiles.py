"""Aligned, rotated, and boxed text compiles on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_text.py``. This checks the
part a string match cannot: that ``begin rotate`` / ``begin box fill`` after
``end graph``, anchored with ``xg()``/``yg()``, is a script GLE accepts.
Skipped when the binary is missing.
"""

from __future__ import annotations

import re
import subprocess

import pytest

import gleplot as glp
from gleplot.compiler import find_gle

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


def test_axes_fraction_text_lands_on_the_frame_fraction(tmp_path):
    """``transform=ax.transAxes`` measures from the bottom-left of the frame.

    On a log x axis and an inverted y axis, GLE's own current point after
    the text's ``amove`` is a quarter across and three quarters up the box
    GLE drew. ``print`` reports both from the compiled script.
    """
    fig = glp.figure(data_prefix="txtf")
    ax = fig.add_subplot(111)
    ax.plot([1, 10, 100], [0, 1, 2])
    ax.set_xscale("log")
    ax.set_ylim(2, 0)
    ax.text(0.25, 0.75, "(a)", transform=ax.transAxes)
    fig.savefig_gle(str(tmp_path / "figure.gle"))
    lines = (tmp_path / "figure.gle").read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(lines) if "0.25*abs(" in line)
    lines[at + 1 : at + 1] = [
        'print "AT" xpos() ypos()',
        'print "BOX" xg(xgmin) xg(xgmax) yg(ygmin) yg(ygmax)',
    ]
    (tmp_path / "probe.gle").write_text("\n".join(lines), encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr

    def numbers(tag):
        found = re.search(tag + r"((?:\s+[-\d.eE+]+)+)", output)
        assert found is not None, output
        return [float(v) for v in found.group(1).split()]

    x, y = numbers("AT")
    x0, x1, y_at_ymin, y_at_ymax = numbers("BOX")
    assert y_at_ymin > y_at_ymax  # the inverted axis is exercised
    assert x == pytest.approx(x0 + 0.25 * (x1 - x0), abs=1e-3)
    assert y == pytest.approx(y_at_ymax + 0.75 * (y_at_ymin - y_at_ymax), abs=1e-3)

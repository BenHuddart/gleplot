"""Page drawings land where they were asked for once GLE draws them.

The script text is asserted in ``tests/unit/test_page_drawing.py``. This
measures the ink of each drawing alone on a page with no axes, which checks
that GLE reads the positions and sizes in cm and an ellipse's size as its
diameters. ``Figure.tex`` is left out: it also needs LaTeX.
"""

from __future__ import annotations

import subprocess

import pytest

import gleplot as glp
from gleplot.compiler import find_gle
from tests.integration.test_ink_on_page import _INK_RE, _instrument

pytestmark = pytest.mark.gle

#: Half the default line width plus GLE's rounding of line ends, in cm.
_TOLERANCE_CM = 0.03


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _ink_box(fig, tmp_path):
    fig.savefig_gle(str(tmp_path / "figure.gle"))
    text = (tmp_path / "figure.gle").read_text(encoding="utf-8")
    (tmp_path / "probe.gle").write_text(_instrument(text), encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    found = _INK_RE.search(proc.stdout + proc.stderr)
    assert found is not None, f"no ink box:\n{proc.stdout}\n{proc.stderr}"
    return tuple(float(v) for v in found.groups())


@pytest.mark.parametrize(
    "draw, box",
    [
        (lambda f: f.circle(2, 3, radius=0.5, fill="red"), (1.5, 2.5, 2.5, 3.5)),
        (
            lambda f: f.circle(2, 3, radius=0.5, fill="red", color="none"),
            (1.5, 2.5, 2.5, 3.5),
        ),
        (lambda f: f.ellipse(4, 3, 3, 1, fill="green"), (2.5, 2.5, 5.5, 3.5)),
        (lambda f: f.polygon([1, 4, 2], [1, 1, 3], fill="yellow"), (1, 1, 4, 3)),
    ],
    ids=["circle", "circle-no-outline", "ellipse", "polygon"],
)
def test_a_drawing_inks_its_own_extent(draw, box, tmp_path):
    fig = glp.figure(figsize=(4, 3))
    draw(fig)
    measured = _ink_box(fig, tmp_path)
    assert measured == pytest.approx(box, abs=_TOLERANCE_CM)


def test_the_line_drawings_and_a_table_compile(tmp_path):
    """Compiled only: GLE leaves an arc and a Bezier curve out of the ink box."""
    fig = glp.figure(figsize=(4, 3))
    fig.add_subplot(111).plot([0, 1], [0, 1])
    fig.arc(4, 3, 1, 0, 180)
    fig.bezier([1, 2, 3, 4], [1, 2, 2, 1])
    fig.curve([1, 2, 3], [1, 2, 1], (1, 0), (1, 0), color="blue", linewidth=2)
    fig.table(1, 6, "a   bb\n1   22")
    out = tmp_path / "figure.pdf"
    fig.savefig(str(out))
    assert out.stat().st_size > 0

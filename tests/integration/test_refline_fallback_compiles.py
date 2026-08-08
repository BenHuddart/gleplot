"""G14, engine side: the 0..1 guide fallback is GLE's own empty-graph range.

:data:`gleplot.axes.EMPTY_AXIS_FALLBACK_RANGE` is only defensible if it is the
range GLE actually renders when gleplot emits no ``xaxis min/max`` -- otherwise
a guide materialized over 0..1 would float somewhere inside (or outside) the
drawn frame. So the constant is pinned here by measurement, not by assertion
about the script text (cross-cutting rule 2): a bound-less gleplot figure is
compiled and GLE is asked for ``xgmin``/``xgmax``/``ygmin``/``ygmax``, and a
guide's endpoints are read back through GLE's own ``xg()``/``yg()`` mapping and
compared with the frame rectangle gleplot wrote.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess

import pytest

import gleplot as glp
from gleplot.axes import EMPTY_AXIS_FALLBACK_RANGE
from gleplot.compiler import GLECompiler, find_gle


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = [
    pytest.mark.gle,
    pytest.mark.skipif(not _gle_available(), reason="GLE binary not available"),
]

_NUM = r"[-+]?[\d.]+(?:[eE][-+]?\d+)?"


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _compile_and_probe(fig, tmp_path, expressions):
    """Compile ``fig`` as written and return the values GLE prints for
    ``expressions`` (a list of GLE expressions evaluated after ``end graph``).

    Compiling the script *as gleplot wrote it* means a script GLE rejects
    fails here rather than silently passing.
    """
    gle_path = tmp_path / "figure.gle"
    fig.savefig_gle(str(gle_path))
    text = gle_path.read_text(encoding="utf-8")
    assert "end graph" in text

    probe = ' " " '.join(expressions)
    (tmp_path / "probe.gle").write_text(
        text.replace("end graph", f'end graph\nprint "PROBE " {probe}', 1),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "probe.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * len(expressions)), out)
    assert found is not None, f"GLE did not compile the script:\n{out}"
    assert proc.returncode == 0, f"GLE exited {proc.returncode}:\n{out}"
    return text, [float(g) for g in found.groups()]


def _frame_rect(text):
    """The graph frame rectangle (x, y, w, h) in page cm, from the script."""
    amove = re.search(rf"^amove ({_NUM}) ({_NUM})$", text, re.M)
    size = re.search(rf"^ +size ({_NUM}) ({_NUM})$", text, re.M)
    assert amove and size, text
    x, y = (float(v) for v in amove.groups())
    w, h = (float(v) for v in size.groups())
    return x, y, w, h


# --------------------------------------------------------------------------- #
# The constant, measured against the engine
# --------------------------------------------------------------------------- #


def test_gle_renders_0_1_for_an_axis_gleplot_left_unbounded(tmp_path):
    """The numeric invariant G14's fallback is derived from: 0 1 0 1."""
    fig = glp.figure(data_prefix="fbc")
    fig.add_subplot(111)  # no series, no limits -> no xaxis/yaxis min/max
    text, (xgmin, xgmax, ygmin, ygmax) = _compile_and_probe(
        fig, tmp_path, ["xgmin", "xgmax", "ygmin", "ygmax"]
    )

    assert "xaxis min" not in text and "yaxis min" not in text
    assert (xgmin, xgmax) == pytest.approx((0.0, 1.0))
    assert (ygmin, ygmax) == pytest.approx((0.0, 1.0))
    assert EMPTY_AXIS_FALLBACK_RANGE == pytest.approx((xgmin, xgmax))
    assert EMPTY_AXIS_FALLBACK_RANGE == pytest.approx((ygmin, ygmax))


# --------------------------------------------------------------------------- #
# Guides materialized over the fallback really span the drawn frame
# --------------------------------------------------------------------------- #


def test_a_guide_spanning_the_fallback_range_reaches_both_frame_edges(tmp_path):
    """``axvline`` whose y range is unresolved: its endpoints ARE the frame.

    The x range is pinned explicitly so the only unresolved axis is the one
    the guide spans (see the xfail below for why a lone guide cannot pin its
    own axis).
    """
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.set_xlim(0.0, 1.0)
    ax.axvline(0.5)

    lo, hi = EMPTY_AXIS_FALLBACK_RANGE
    text, (y_lo, y_hi) = _compile_and_probe(fig, tmp_path, [f"yg({lo})", f"yg({hi})"])
    _fx, fy, _fw, fh = _frame_rect(text)

    assert y_lo == pytest.approx(fy, abs=1e-3)
    assert y_hi == pytest.approx(fy + fh, abs=1e-3)


def test_an_axvspan_on_a_completely_empty_axes_compiles_and_covers_the_frame(tmp_path):
    """The SPEC 14.3 placeholder band, created on a blank axes."""
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.axvspan(0.4, 0.6)

    _text, (ygmin, ygmax) = _compile_and_probe(fig, tmp_path, ["ygmin", "ygmax"])
    assert (ygmin, ygmax) == pytest.approx(EMPTY_AXIS_FALLBACK_RANGE)


def test_an_axhspan_on_a_completely_empty_axes_compiles_and_covers_the_frame(tmp_path):
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.axhspan(0.4, 0.6)

    _text, (xgmin, xgmax) = _compile_and_probe(fig, tmp_path, ["xgmin", "xgmax"])
    assert (xgmin, xgmax) == pytest.approx(EMPTY_AXIS_FALLBACK_RANGE)


def test_two_reflines_on_an_empty_axes_compile_and_span_the_full_frame(tmp_path):
    """Two guides bound their own axis, so nothing is left unresolved but y."""
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.axvline(0.25)
    ax.axvline(0.75)

    _text, (ygmin, ygmax) = _compile_and_probe(fig, tmp_path, ["ygmin", "ygmax"])
    assert (ygmin, ygmax) == pytest.approx(EMPTY_AXIS_FALLBACK_RANGE)


def test_the_rendered_page_is_not_blank(tmp_path):
    """End to end: blank figure + one guide produces real output."""
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.axvspan(0.4, 0.6)
    out = fig.savefig(str(tmp_path / "guide.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_a_lone_axvline_on_an_empty_axes_compiles(tmp_path):
    """The SPEC 14.3 headline case: blank project, one vertical guide.

    A strict xfail through G14, a pass since G15. A lone ``axvline`` is the
    only thing bounding x, so autoscale resolved x to a degenerate
    ``0.5..0.5`` and gleplot wrote ``xaxis min 0.5 max 0.5``, which GLE
    rejects ("illegal range for xaxis"). G15 leaves a collapsed range out of
    the script instead, so x becomes GLE's to scale -- it picks 0..1 here,
    from the two-point dataset G14 materializes -- while y keeps the fallback
    range the guide was drawn across.
    """
    fig = glp.figure(data_prefix="fbc")
    ax = fig.add_subplot(111)
    ax.axvline(0.5)

    text, (ygmin, ygmax) = _compile_and_probe(fig, tmp_path, ["ygmin", "ygmax"])
    assert "xaxis min" not in text and "xaxis max" not in text
    assert (ygmin, ygmax) == pytest.approx(EMPTY_AXIS_FALLBACK_RANGE)

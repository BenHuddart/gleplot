"""G17, engine side: a drawn guide spans the frame GLE actually chose.

The claim the draw form makes is numeric, so it is measured against the live
binary rather than asserted about script text (cross-cutting rule 2): compile
what gleplot wrote, ask GLE where the guide's endpoints landed, and compare
them with the frame rectangle gleplot wrote for the same block.

The headline measurement is the one that sent G17 to the supervisor. For
``plot([5], [7])`` + ``axvline(5, ymin=0, ymax=1)`` the pre-G17 emission -- a
literal two-point dataset over the 0..1 stand-in range -- covered **14.3 %** of
the frame it declared 100 % of, and it got there twice over: the fraction was
measured against 0..1 rather than the rendered frame, and the dataset's own
``0``/``1`` rows joined GLE's autoscale and pulled the frame from ``0..12``
down to ``0..7``. Both halves are reproduced here from the archived script and
compared against what gleplot emits today.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess

import numpy as np
import pytest

import gleplot as glp
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


def _probe_script(text, tmp_path, name, expressions, cairo=False):
    """Compile ``text`` with a ``print`` of ``expressions`` after ``end graph``.

    ``cairo`` mirrors the flag gleplot's own compile pipeline would pass for
    the same script (``Figure.requires_cairo``); GLE refuses a semi-transparent
    colour without it, which is exactly what a translucent band emits.
    """
    probe = ' " " '.join(expressions)
    path = tmp_path / f"{name}.gle"
    path.write_text(
        text.replace("end graph", f'end graph\nprint "PROBE " {probe}', 1),
        encoding="utf-8",
    )
    args = [str(find_gle()), "-d", "pdf"] + (["-cairo"] if cairo else []) + [path.name]
    proc = subprocess.run(
        args,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * len(expressions)), out)
    assert found is not None, f"GLE did not compile the script:\n{out}"
    assert proc.returncode == 0, f"GLE exited {proc.returncode}:\n{out}"
    return [float(g) for g in found.groups()]


def _compile_and_probe(fig, tmp_path, name, expressions):
    """Compile ``fig`` **as gleplot wrote it**, sidecars and all."""
    gle_path = tmp_path / f"{name}-src.gle"
    fig.savefig_gle(str(gle_path))
    text = gle_path.read_text(encoding="utf-8")
    return text, _probe_script(
        text, tmp_path, name, expressions, cairo=fig.requires_cairo()
    )


def _frame_rect(text):
    """The graph frame rectangle (x, y, w, h) in page cm, from the script."""
    amove = re.search(rf"^amove ({_NUM}) ({_NUM})$", text, re.M)
    size = re.search(rf"^ +size ({_NUM}) ({_NUM})$", text, re.M)
    assert amove and size, text
    x, y = (float(v) for v in amove.groups())
    w, h = (float(v) for v in size.groups())
    return x, y, w, h


def _deferred_axis_figure():
    """``plot([5], [7])`` + a full-height guide: y collapses, so y is GLE's."""
    fig = glp.figure(data_prefix="gd")
    ax = fig.add_subplot(111)
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.axvline(5.0, ymin=0.0, ymax=1.0)
    return fig


#: The pre-G17 emission of :func:`_deferred_axis_figure`, transcribed from the
#: G17 design note (``docs/agent/G17_GUIDE_EMISSION.md`` §1.1), which captured
#: it verbatim from the writer on commit ab65e90. Kept here so the "before"
#: number is a measurement of the real old script and not of a paraphrase.
_PRE_G17_SCRIPT = """\
! GLE graphics file
size 20.32 15.24
set hei 0.42328
amove 1.69312 1.26984
begin graph
    size 17.992 13.3352
    scale 1 1
    data gd_1.dat d1=c1,c2
    d1 line color BLACK lwidth 0.05292 key ""
    data gd_0.dat d2=c1,c2
    d2 line color BLUE lwidth 0.05292 key ""
end graph
"""


# --------------------------------------------------------------------------- #
# Residual (a), measured before and after
# --------------------------------------------------------------------------- #


def test_the_old_dataset_form_covered_14_percent_of_the_frame(tmp_path):
    """Archaeology: reproduce the defect G17 exists to remove.

    Both halves of it. The engine range is ``0..7`` rather than the ``0..12``
    GLE picks for the lone point alone, *because* the guide's own rows joined
    the autoscale; and the guide, declaring the full frame height, reaches
    only 14.3 % up it.
    """
    (tmp_path / "gd_0.dat").write_text("x y\n5 7\n", encoding="utf-8")
    (tmp_path / "gd_1.dat").write_text("x y\n5 0\n5 1\n", encoding="utf-8")
    ygmin, ygmax, guide_lo, guide_hi = _probe_script(
        _PRE_G17_SCRIPT, tmp_path, "before", ["ygmin", "ygmax", "yg(0)", "yg(1)"]
    )
    _fx, fy, _fw, fh = _frame_rect(_PRE_G17_SCRIPT)

    assert (ygmin, ygmax) == pytest.approx((0.0, 7.0))
    assert guide_lo == pytest.approx(fy, abs=1e-3)  # bottom edge: correct
    coverage = (guide_hi - guide_lo) / fh
    assert coverage == pytest.approx(0.143, abs=0.001)


def test_a_drawn_guide_covers_the_whole_frame_it_declared(tmp_path):
    """The same figure today: 100 %, on the range GLE chose for the point."""
    text, (ygmin, ygmax, guide_lo, guide_hi) = _compile_and_probe(
        _deferred_axis_figure(),
        tmp_path,
        "after",
        ["ygmin", "ygmax", "yg(ygmin)", "yg(ygmax)"],
    )
    _fx, fy, _fw, fh = _frame_rect(text)

    assert guide_lo == pytest.approx(fy, abs=1e-3)
    assert guide_hi == pytest.approx(fy + fh, abs=1e-3)
    assert (guide_hi - guide_lo) / fh == pytest.approx(1.0, abs=1e-4)
    # And the range it covered is the engine's own, not one the guide moved.
    assert (ygmin, ygmax) == pytest.approx((0.0, 12.0))


def test_the_guide_no_longer_moves_the_range_it_is_measured_against(tmp_path):
    """The circularity, isolated: same figure with and without the guide."""
    plain = glp.figure(data_prefix="gp")
    plain.add_subplot(111).plot(np.array([5.0]), np.array([7.0]))
    _t, without = _compile_and_probe(plain, tmp_path, "plain", ["ygmin", "ygmax"])

    glp.close()
    _t, with_guide = _compile_and_probe(
        _deferred_axis_figure(), tmp_path, "guided", ["ygmin", "ygmax"]
    )

    assert with_guide == pytest.approx(without)


# --------------------------------------------------------------------------- #
# Every guide kind compiles, on an empty axes and over a lone data point
# --------------------------------------------------------------------------- #


_GUIDE_BUILDERS = {
    "axvline": lambda ax: ax.axvline(5.0, ymin=0.25, ymax=0.75, color="red"),
    "axhline": lambda ax: ax.axhline(7.0, xmin=0.25, xmax=0.75, linestyle="--"),
    "axvspan": lambda ax: ax.axvspan(4.0, 6.0, color="orange", alpha=0.35),
    "axhspan": lambda ax: ax.axhspan(6.0, 8.0, label="band"),
}


@pytest.mark.parametrize("kind", sorted(_GUIDE_BUILDERS))
@pytest.mark.parametrize("with_point", [False, True], ids=["empty", "lone-point"])
def test_every_guide_kind_compiles_in_draw_form(kind, with_point, tmp_path):
    """The four kinds x the two situations that route them to the draw form.

    On an empty axes both ranges are GLE's; over a lone data point both
    collapse and are handed back (G15). Either way the guide must compile and
    land inside the frame gleplot drew.
    """
    fig = glp.figure(data_prefix="gk")
    ax = fig.add_subplot(111)
    if with_point:
        ax.plot(np.array([5.0]), np.array([7.0]))
    _GUIDE_BUILDERS[kind](ax)

    name = f"{kind}-{'point' if with_point else 'empty'}"
    text, (xgmin, xgmax, ygmin, ygmax) = _compile_and_probe(
        fig, tmp_path, name, ["xgmin", "xgmax", "ygmin", "ygmax"]
    )

    sub = "gleplot_" + kind[2:]  # axvline -> gleplot_vline
    assert f"sub {sub} " in text
    assert f"draw {sub} " in text
    # A real, non-degenerate frame in both directions -- the failure mode this
    # guards is GLE aborting on an illegal range before drawing anything.
    assert xgmax > xgmin and ygmax > ygmin


@pytest.mark.parametrize("kind", sorted(_GUIDE_BUILDERS))
def test_a_labelled_drawn_guide_renders_its_legend_entry(tmp_path, kind):
    """The data-free ``dN key`` bridge really does reach the key box.

    A ``draw`` owns no dataset and so cannot carry a key. Reflines borrow an
    empty one; bands have never had a legend entry in either form, so the
    label is carried through the script for recovery and draws nothing.
    """
    fig = glp.figure(data_prefix="gl")
    ax = fig.add_subplot(111)
    _GUIDE_BUILDERS[kind](ax)
    for guide in ax.reflines + ax.spans:
        guide["label"] = "threshold"

    gle_path = tmp_path / f"key-{kind}.gle"
    fig.savefig_gle(str(gle_path))
    out = fig.savefig(str(tmp_path / f"key-{kind}.pdf"))
    assert out.exists() and out.stat().st_size > 0

    text = gle_path.read_text(encoding="utf-8")
    assert '"threshold"' in text
    is_refline = bool(ax.reflines)
    assert (' key "threshold"' in text) is is_refline

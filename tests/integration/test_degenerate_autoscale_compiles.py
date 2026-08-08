"""G15, engine side: what gleplot stops writing, GLE writes better.

A range that collapses to a point is not written into the script at all, on
the claim that GLE will scale the axis itself. That claim is only worth making
if it is measured, so every number in this module comes from the live binary
(cross-cutting rule 2), through three independent channels that have to agree:

* ``print xgmin ...`` appended to **gleplot's own script**, compiled exactly
  as written -- a script GLE rejects fails here instead of passing quietly;
* the same probe on a **hand-written bare-GLE script** plotting the same
  points, which is what "GLE's own autoscale" means;
* the **calibration record** (SPEC 6.2) parsed off an instrumented copy, which
  is how GLEstudio learns the range and the only channel that has to keep
  working for a deferred axis to be editable on the canvas.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess

import numpy as np
import pytest

import gleplot as glp
from gleplot.calibration import (
    AxesSpec,
    instrument_script,
    parse_calibration_records,
)
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

#: GLE reports its ranges to six significant figures; the values here are all
#: small integers, so this is only float-formatting slack.
RANGE_TOLERANCE = 1e-6


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _run(tmp_path, name):
    proc = subprocess.run(
        [str(find_gle()), "-d", "pdf", "-verbosity", "0", name],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    return proc, re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)


def _probe(tmp_path, text, expressions, stem="probe"):
    """Compile ``text`` with a ``print`` of ``expressions`` after ``end graph``."""
    joined = ' " " '.join(expressions)
    (tmp_path / f"{stem}.gle").write_text(
        text.replace("end graph", f'end graph\nprint "PROBE " {joined}', 1),
        encoding="utf-8",
    )
    proc, out = _run(tmp_path, f"{stem}.gle")
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * len(expressions)), out)
    assert found is not None, f"GLE did not compile the script:\n{out}"
    assert proc.returncode == 0, f"GLE exited {proc.returncode}:\n{out}"
    return [float(g) for g in found.groups()]


def _gleplot_script(fig, tmp_path, stem="figure"):
    path = tmp_path / f"{stem}.gle"
    fig.savefig_gle(str(path))
    return path.read_text(encoding="utf-8")


def _bare_gle(tmp_path, rows, stem="bare", axis_lines=()):
    """A minimal hand-written GLE script plotting ``rows``: GLE's own answer."""
    (tmp_path / f"{stem}.dat").write_text(
        "".join(f"{x:g} {y:g}\n" for x, y in rows), encoding="utf-8"
    )
    settings = "".join(f"    {line}\n" for line in axis_lines)
    return (
        "size 20.32 15.24\n"
        "amove 1.69312 1.26984\n"
        "begin graph\n"
        "    size 17.992 13.3352\n"
        "    scale 1 1\n"
        f'    data "{stem}.dat" d1=c1,c2\n'
        f"{settings}"
        "    d1 marker circle\n"
        "end graph\n"
    )


def _single_point_figure(x, y):
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([float(x)]), np.array([float(y)]))
    return fig


# --------------------------------------------------------------------------- #
# The headline claim: a single point compiles, and GLE scales it
# --------------------------------------------------------------------------- #


def test_a_single_point_plot_compiles_and_gle_picks_the_range(tmp_path):
    """``plot([1], [2])``: rejected before G15, autoscaled to 0..2 / 1..3 now."""
    text = _gleplot_script(_single_point_figure(1, 2), tmp_path)
    assert "xaxis min" not in text and "yaxis min" not in text

    ranges = _probe(tmp_path, text, ["xgmin", "xgmax", "ygmin", "ygmax"])
    assert ranges == pytest.approx([0.0, 2.0, 1.0, 3.0], abs=RANGE_TOLERANCE)


@pytest.mark.parametrize(
    "point,expected",
    [
        ((1, 2), (0.0, 2.0, 1.0, 3.0)),
        ((5, 7), (0.0, 10.0, 0.0, 12.0)),
        ((-3, -3), (-6.0, 0.0, -6.0, 0.0)),
        ((0, 0), (-1.0, 1.0, -1.0, 1.0)),
    ],
    ids=["1_2", "5_7", "minus3", "origin"],
)
def test_the_deferred_range_is_exactly_what_bare_gle_would_have_chosen(
    tmp_path, point, expected
):
    """Deferring means deferring: no gleplot arithmetic is left in the answer.

    The reference is a hand-written script with the same point and no axis
    settings at all. gleplot's emission must land on the same numbers -- and
    on the ones recorded in the plan, so a change in GLE's own expansion
    shows up here as a failure rather than as a silently different figure.
    """
    x, y = point
    ours = _probe(
        tmp_path,
        _gleplot_script(_single_point_figure(x, y), tmp_path),
        ["xgmin", "xgmax", "ygmin", "ygmax"],
    )
    theirs = _probe(
        tmp_path,
        _bare_gle(tmp_path, [(x, y)]),
        ["xgmin", "xgmax", "ygmin", "ygmax"],
        stem="bare_probe",
    )

    assert ours == pytest.approx(theirs, abs=RANGE_TOLERANCE)
    assert ours == pytest.approx(list(expected), abs=RANGE_TOLERANCE)


def test_the_calibrated_range_is_the_range_gle_reports(tmp_path):
    """SPEC 6.2 reads the engine's choice back, exactly as for any autoscale.

    This is the assertion GLEstudio depends on: an axis gleplot declined to
    write is still fully calibrated, so the canvas overlay, hit-testing and
    "insert here" defaults all have real numbers to work from.
    """
    fig = _single_point_figure(1, 2)
    text = _gleplot_script(fig, tmp_path)
    axes_id = fig.axes_list[0].axes_id

    printed = _probe(tmp_path, text, ["xgmin", "xgmax", "ygmin", "ygmax"])

    (tmp_path / "inst.gle").write_text(
        instrument_script(text, [axes_id]).text, encoding="utf-8"
    )
    proc, out = _run(tmp_path, "inst.gle")
    assert proc.returncode == 0, out
    result = parse_calibration_records(out, [AxesSpec(axes_id)])
    assert result.warnings == []

    cal = result.calibrations[axes_id]
    assert cal.x_range == pytest.approx(tuple(printed[:2]), abs=RANGE_TOLERANCE)
    assert cal.y_range == pytest.approx(tuple(printed[2:]), abs=RANGE_TOLERANCE)
    assert cal.x_range == pytest.approx((0.0, 2.0), abs=RANGE_TOLERANCE)
    assert cal.y_range == pytest.approx((1.0, 3.0), abs=RANGE_TOLERANCE)


# --------------------------------------------------------------------------- #
# The other shapes that reach the branch
# --------------------------------------------------------------------------- #


def test_a_column_of_points_compiles_with_only_its_y_range_written(tmp_path):
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 1.0]), np.array([2.0, 3.0]))

    text = _gleplot_script(fig, tmp_path)
    assert "xaxis min" not in text
    assert "    yaxis min 2 max 3" in text

    ranges = _probe(tmp_path, text, ["xgmin", "xgmax", "ygmin", "ygmax"])
    assert ranges[2:] == pytest.approx([2.0, 3.0], abs=RANGE_TOLERANCE)
    assert ranges[0] < ranges[1]


def test_an_explicit_bound_kept_beside_a_deferred_one_still_bounds_the_frame(
    tmp_path,
):
    """``set_xlim(5, None)`` over a lone x=5: GLE draws 5..10, keeping the 5.

    Half a collapsed range is still a bound the caller chose, so only the
    derived half is dropped -- and the frame's left edge is the number they
    asked for, not one GLE invented.
    """
    fig = _single_point_figure(5, 7)
    fig.axes_list[0].set_xlim(5.0, None)

    text = _gleplot_script(fig, tmp_path)
    assert "    xaxis min 5\n" in text

    ours = _probe(tmp_path, text, ["xgmin", "xgmax"])
    theirs = _probe(
        tmp_path,
        _bare_gle(tmp_path, [(5, 7)], axis_lines=["xaxis min 5"]),
        ["xgmin", "xgmax"],
        stem="bare_probe",
    )
    assert ours == pytest.approx(theirs, abs=RANGE_TOLERANCE)
    assert ours == pytest.approx([5.0, 10.0], abs=RANGE_TOLERANCE)


def test_a_range_the_caller_asked_for_and_gle_cannot_draw_compiles_after_the_drop(
    tmp_path,
):
    """``set_xlim(5, 5)`` warned about and dropped -- the script still runs."""
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0]), np.array([2.0, 3.0]))
    ax.set_xlim(5.0, 5.0)

    with pytest.warns(UserWarning, match="empty range"):
        text = _gleplot_script(fig, tmp_path)

    ranges = _probe(tmp_path, text, ["xgmin", "xgmax"])
    assert ranges[0] < ranges[1]


def test_a_shared_grid_whose_union_collapses_compiles(tmp_path):
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="dgc")
    for ax in axes:
        ax.plot(np.array([1.0]), np.array([2.0]))

    text = _gleplot_script(fig, tmp_path)
    assert "xaxis min" not in text
    ranges = _probe(tmp_path, text, ["xgmin", "xgmax"])
    assert ranges[0] < ranges[1]


def test_the_rendered_page_is_not_blank(tmp_path):
    """End to end, through the real savefig path."""
    out = _single_point_figure(1, 2).savefig(str(tmp_path / "point.pdf"))
    assert out.exists() and out.stat().st_size > 0


# --------------------------------------------------------------------------- #
# The residual GLE cannot fix for us
# --------------------------------------------------------------------------- #


def test_a_single_bar_is_still_beyond_the_engine(tmp_path):
    """Bars are the one series GLE cannot autoscale from a single value.

    A bar chart's x range has always had to come from gleplot, because GLE
    derives the bar width from the spacing *between* the data points; with one
    bar that spacing is zero and the graph fails with "invalid range for
    dimension X" whether the (illegal) collapsed range is written or left out.
    So the deferral neither fixes nor worsens this case -- it changes which
    error GLE reports. Pinned so that a future fix (upstream or here) is
    noticed rather than assumed.
    """
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.bar([1], [5])

    text = _gleplot_script(fig, tmp_path)
    assert "xaxis min" not in text

    (tmp_path / "bar.gle").write_text(text, encoding="utf-8")
    proc, out = _run(tmp_path, "bar.gle")
    assert proc.returncode != 0
    assert "invalid range for dimension X" in out

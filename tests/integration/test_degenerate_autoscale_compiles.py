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

The last section is G16, the one figure G15 could not hand over: a bar chart
GLE cannot size from its own data. Same discipline -- the width gleplot writes
is the width the engine picks for the same heights when it has a spacing to
measure, read off the compiled page.

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
# The bar G15 could not draw (G16)
# --------------------------------------------------------------------------- #
#
# G15 left one residual: a bar chart with a single bar. GLE sizes a bar set
# from its data -- ``drawBar`` takes the width from
# ``GLEDataPairs::getMinXInterval()``, the smallest strictly positive gap
# between consecutive x values, and ``get_dataset_ranges`` widens the x data
# range by half that same interval either side -- so a dataset with no such
# gap has neither a width nor a range. G16 writes both down, from one nominal
# spacing. The tests below are the empirical case for that number: what the
# engine does with the dataset it cannot measure, and what width it picks for
# the same heights when it *can*.

#: One filled/stroked rectangle in GLE's EPS output. Bars are the only
#: axis-aligned rectangles in these figures apart from the frame, which is
#: drawn as a stroked path with a different shape.
_EPS_RECT = re.compile(
    rf"newpath ({_NUM}) ({_NUM}) moveto ({_NUM}) \2 l \3 ({_NUM}) l \1 \4 l closepath"
)


def _compile_eps(tmp_path, text, stem):
    """Compile ``text`` to EPS and return ``(proc, output, eps_text)``."""
    (tmp_path / f"{stem}.gle").write_text(text, encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "eps", "-verbosity", "0", f"{stem}.gle"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr)
    eps = tmp_path / f"{stem}.eps"
    return (
        proc,
        out,
        eps.read_text(encoding="utf-8", errors="replace") if eps.exists() else "",
    )


def _drawn_bar_widths(tmp_path, text, stem):
    """The width of every bar GLE actually drew, in DATA units.

    Measured off the PostScript rectangles and converted with the frame
    mapping GLE reports for the same run, so the answer is the engine's, not
    a re-derivation of its arithmetic.
    """
    probed = text.replace(
        "end graph",
        'end graph\nprint "PROBE " xgmin " " xgmax " " xg(xgmin) " " xg(xgmax)',
        1,
    )
    proc, out, eps = _compile_eps(tmp_path, probed, stem)
    assert proc.returncode == 0, f"GLE exited {proc.returncode}:\n{out}"
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * 4), out)
    assert found is not None, f"GLE did not report the frame:\n{out}"
    xgmin, xgmax, left_cm, right_cm = (float(g) for g in found.groups())
    assert "nan" not in eps, "GLE drew NaN coordinates"

    units_per_cm = (xgmax - xgmin) / (right_cm - left_cm)
    # Each bar is emitted twice (filled, then stroked) and GLE rounds its
    # PostScript to six significant figures, so equal bars differ in the last
    # digit or two; deduplicate at the precision the format actually carries.
    widths = {
        round((float(m.group(3)) - float(m.group(1))) * units_per_cm, 5)
        for m in _EPS_RECT.finditer(eps)
    }
    return sorted(w for w in widths if w > 0)


def _bare_bar_gle(tmp_path, rows, stem, bar_line="    bar d1 fill RED"):
    """A hand-written bar chart with no axis settings: GLE's own answer."""
    (tmp_path / f"{stem}.dat").write_text(
        "".join(f"{x:g} {y:g}\n" for x, y in rows), encoding="utf-8"
    )
    return (
        "size 20.32 15.24\n"
        "amove 1.69312 1.26984\n"
        "begin graph\n"
        "    size 17.992 13.3352\n"
        "    scale 1 1\n"
        f'    data "{stem}.dat" d1=c1,c2\n'
        f"{bar_line}\n"
        "end graph\n"
    )


def _single_bar_figure(x=1.0, height=5.0):
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.bar([x], [height])
    return fig


def test_gle_still_cannot_size_a_bar_set_it_cannot_measure(tmp_path):
    """Why anything is emitted at all: the three shapes, and their two failures.

    Left to itself GLE does not decline politely. Where the range collapsed
    with it, the graph aborts; where it did not, GLE compiles a page whose
    bars are ``-nan`` rectangles -- accepted by GLE, rejected downstream by
    Ghostscript. Both are pinned here so the emission below is answering a
    measured problem.
    """
    one = _bare_bar_gle(tmp_path, [(1, 5)], "bare_one")
    proc, out, _eps = _compile_eps(tmp_path, one, "bare_one")
    assert proc.returncode != 0
    assert "invalid range for dimension X" in out

    equal = _bare_bar_gle(tmp_path, [(1, 5), (1, 3)], "bare_equal")
    proc, out, _eps = _compile_eps(tmp_path, equal, "bare_equal")
    assert proc.returncode != 0
    assert "invalid range for dimension X" in out

    # Descending x, with the range spelled out as gleplot spells it: a range
    # GLE accepts, and a width it still cannot compute. Nothing stops the
    # compile -- the bars are simply drawn at NaN.
    desc = _bare_bar_gle(
        tmp_path,
        [(3, 5), (1, 3)],
        "bare_desc",
        bar_line="    xaxis min 1 max 3\n    bar d1 fill RED",
    )
    proc, out, eps = _compile_eps(tmp_path, desc, "bare_desc")
    assert proc.returncode == 0, out
    assert "nan" in eps


def test_the_emitted_width_is_the_one_gle_picks_at_unit_spacing(tmp_path):
    """The rationale, measured: two bars a unit apart get 0.5 from GLE itself.

    ``drawBar``'s ``min_int/(nbars*2)`` with ``min_int`` = 1 and ``nbars`` = 1.
    gleplot writes that number down for the dataset GLE cannot measure, so a
    lone bar is drawn exactly as wide as it would have been with a neighbour.
    """
    theirs = _drawn_bar_widths(
        tmp_path, _bare_bar_gle(tmp_path, [(1, 5), (2, 3)], "unit"), "unit"
    )
    assert theirs == pytest.approx([0.5], abs=RANGE_TOLERANCE)

    ours = _drawn_bar_widths(
        tmp_path, _gleplot_script(_single_bar_figure(), tmp_path), "figure"
    )
    assert ours == pytest.approx(theirs, abs=RANGE_TOLERANCE)
    assert "bar d1 fill RED width 0.5" in _gleplot_script(
        _single_bar_figure(), tmp_path
    )


def test_a_single_bar_compiles_and_lands_inside_its_frame(tmp_path):
    """The headline flip: the figure G15 pinned as impossible now draws.

    The frame is the bar's own x plus and minus half the nominal spacing, so
    the 0.5-wide bar sits centred in it with a quarter-spacing of clearance
    either side -- measured off the compiled page, not asserted from the
    script.
    """
    text = _gleplot_script(_single_bar_figure(x=1.0), tmp_path)
    assert "    xaxis min 0.5 max 1.5" in text

    probed = text.replace(
        "end graph",
        'end graph\nprint "PROBE " xgmin " " xgmax " " xg(xgmin) " " xg(xgmax)',
        1,
    )
    proc, out, eps = _compile_eps(tmp_path, probed, "single")
    assert proc.returncode == 0, out
    assert "nan" not in eps

    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * 4), out)
    xgmin, xgmax, left_cm, right_cm = (float(g) for g in found.groups())
    assert (xgmin, xgmax) == pytest.approx((0.5, 1.5), abs=RANGE_TOLERANCE)

    rects = [m for m in _EPS_RECT.finditer(eps)]
    assert rects, "no bar was drawn"
    lo_cm = min(float(m.group(1)) for m in rects)
    hi_cm = max(float(m.group(3)) for m in rects)
    assert left_cm < lo_cm < hi_cm < right_cm


def test_the_rendered_single_bar_page_is_not_blank(tmp_path):
    """End to end, through the real savefig path (Ghostscript included).

    Before G16 this exact call was the ``-nan`` failure: GLE compiled, and
    Ghostscript stopped with "Error: /undefined in -nan".
    """
    out = _single_bar_figure().savefig(str(tmp_path / "bar.pdf"))
    assert out.exists() and out.stat().st_size > 0
    assert out.read_bytes().startswith(b"%PDF")


def test_a_lone_bar_beside_other_data_stops_drawing_nan(tmp_path):
    """The half of the bug an axis range never hid: the polygons themselves."""
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.bar([1.0], [5.0])
    ax.plot(np.array([0.0, 10.0]), np.array([1.0, 9.0]))

    text = _gleplot_script(fig, tmp_path)
    assert "    xaxis min 0 max 10" in text

    proc, out, eps = _compile_eps(tmp_path, text, "mixed")
    assert proc.returncode == 0, out
    assert "nan" not in eps

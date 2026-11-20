"""G15, engine side: what gleplot stops writing, GLE writes better.

A range that collapses to a point is not written into the script at all, on
the claim that GLE will scale the axis itself. That claim is only worth making
if it is measured, so every number in this module comes from the live binary
(cross-cutting rule 2), through two independent channels that have to agree:

* ``print xgmin ...`` appended to **gleplot's own script**, compiled exactly
  as written -- a script GLE rejects fails here instead of passing quietly;
* the same probe on a **hand-written bare-GLE script** plotting the same
  points, which is what "GLE's own autoscale" means.

The last two sections are bars. G16 is the one figure G15 could not hand
over: a bar chart GLE cannot size from its own data. Same discipline -- the
width gleplot writes is the width the engine picks for the same heights when
it has a spacing to measure, read off the compiled page. G19 then lets the
model carry a width of its own, and measures the two facts that decides
rest on: GLE's bar-range widening ignores an explicit width entirely, and
the half-span gleplot supplies where the engine cannot measure keeps the bar
in the middle half of its frame at any width.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import find_gle

pytestmark = pytest.mark.gle

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


@pytest.mark.parametrize(
    "draw, axis, value",
    [
        (lambda ax: ax.rug([2], axis="y"), "y", 2.0),
        (lambda ax: ax.rug([5]), "x", 5.0),
    ],
    ids=["y-rug", "x-rug"],
)
def test_a_collapsed_axis_with_no_dataset_frames_its_value(tmp_path, draw, axis, value):
    """With no dataset GLE takes 0..1, which would clip the value (#219)."""
    fig = glp.figure(data_prefix="dg")
    draw(fig.add_subplot(111))
    text = _gleplot_script(fig, tmp_path)

    lo, hi = _probe(tmp_path, text, [f"{axis}gmin", f"{axis}gmax"])
    assert lo < value < hi


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
    assert (
        "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width 0.5"
        in _gleplot_script(_single_bar_figure(), tmp_path)
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


# --------------------------------------------------------------------------- #
# The width the script names (G19)
# --------------------------------------------------------------------------- #
#
# G16 derives a width for the bar sets GLE cannot measure. G19 lets the model
# carry one instead, which raises the question this section measures: what an
# explicit width does to the range. GLE's own answer is "nothing" -- the
# widening in ``get_dataset_ranges`` reads the DATA's minimum x interval, not
# ``br[b]->width`` -- so where gleplot has to supply the range itself, the
# half-span it picks is a gleplot decision, and the numbers below are what it
# was decided on.


def _bare_two_bar_ranges(tmp_path, stem, width_clause):
    """``(xgmin, xgmax)`` GLE autoscales to for two bars, with ``width_clause``."""
    text = _bare_bar_gle(
        tmp_path,
        [(1, 5), (2, 3)],
        stem,
        bar_line=f"    bar d1 fill RED{width_clause}",
    ).replace("end graph", 'end graph\nprint "PROBE " xgmin " " xgmax', 1)
    proc, out, _eps = _compile_eps(tmp_path, text, stem)
    assert proc.returncode == 0, out
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * 2), out)
    assert found is not None, f"GLE did not report the frame:\n{out}"
    return tuple(float(g) for g in found.groups())


def test_gles_bar_range_is_derived_from_the_data_not_from_the_width(tmp_path):
    """The measurement the half-span rule rests on.

    ``get_dataset_ranges`` widens a bar dataset's x range by
    ``getMinXInterval()/2`` either side. The bar's declared ``width`` is not
    part of that expression, and the engine agrees: the same two bars
    autoscale to the same frame with no width, with a fifth of the derived
    one, and with four times it. So gleplot must go on leaving the range of
    a measurable bar set alone, whatever width the model carries.
    """
    without = _bare_two_bar_ranges(tmp_path, "wr_none", "")
    assert without == pytest.approx((0.4, 2.6), abs=RANGE_TOLERANCE)
    assert _bare_two_bar_ranges(tmp_path, "wr_narrow", " width 0.2") == without
    assert _bare_two_bar_ranges(tmp_path, "wr_wide", " width 2") == without


@pytest.mark.parametrize("width", [0.3, 2.0], ids=["narrow", "wide"])
def test_a_lone_bar_of_any_width_still_owns_the_middle_half_of_its_frame(
    tmp_path, width
):
    """The rule gleplot chose: half-span = the width being drawn.

    That is GLE's own proportion. For a single-dataset bar set its two
    derivations are one number -- the half-span ``min_int/2`` and the width
    ``min_int/(nbars*2)`` at ``nbars`` = 1 -- so a bar GLE sizes and frames
    itself fills exactly half its frame. Measured here off the compiled page
    for a width GLE never chose: 0.3 and 2.0 both draw half of a 6 cm frame,
    centred, with a quarter-frame of clearance either side.
    """
    fig = glp.figure(data_prefix="dgc")
    ax = fig.add_subplot(111)
    ax.bar([1.0], [5.0], width=width)

    stem = f"g19_{str(width).replace('.', '_')}"
    text = _gleplot_script(fig, tmp_path, stem=stem)
    assert (
        f"    bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width {width:g}"
        in text
    )

    drawn = _drawn_bar_widths(tmp_path, text, stem)
    assert drawn == pytest.approx([width], abs=RANGE_TOLERANCE)

    probed = text.replace(
        "end graph",
        'end graph\nprint "PROBE " xgmin " " xgmax " " xg(xgmin) " " xg(xgmax)',
        1,
    )
    proc, out, eps = _compile_eps(tmp_path, probed, f"{stem}_probe")
    assert proc.returncode == 0, out
    assert "nan" not in eps
    found = re.search(r"PROBE\s+" + r"\s+".join([f"({_NUM})"] * 4), out)
    xgmin, xgmax, left_cm, right_cm = (float(g) for g in found.groups())
    assert (xgmin, xgmax) == pytest.approx(
        (1.0 - width, 1.0 + width), abs=RANGE_TOLERANCE
    )

    rects = list(_EPS_RECT.finditer(eps))
    assert rects, "no bar was drawn"
    lo_cm = min(float(m.group(1)) for m in rects)
    hi_cm = max(float(m.group(3)) for m in rects)
    frame_cm = right_cm - left_cm
    # Half the frame, centred -- and clear of both edges, which is what a
    # fixed 0.5 half-span would have lost: ``width 2`` in a 1-unit frame is
    # drawn edge to edge, clipped at both ends.
    assert (hi_cm - lo_cm) == pytest.approx(frame_cm / 2.0, abs=1e-3)
    assert left_cm < lo_cm < hi_cm < right_cm


def test_a_hand_written_single_bar_width_survives_the_round_trip(tmp_path):
    """The G19 wrinkle, end to end and on the page.

    ``bar d1 width 0.3`` over a one-row file used to come back as G16's
    derived ``width 0.5``. It now comes back as 0.3 -- and the re-emitted
    script compiles to a bar 0.3 data units wide, measured off the page,
    which is what makes the field more than a string that survives.
    """
    (tmp_path / "one.dat").write_text("1 5\n", encoding="utf-8")
    # The import list names one.dat gleplot's own: a bar on a file of the
    # user's own stays raw rather than rewrite it, and is not modelled.
    (tmp_path / "hand.gle").write_text(
        "! gleplot-meta-begin v2\n"
        "! gleplot: import-data = one.dat\n"
        "! gleplot-meta-end\n"
        "size 8 6\n"
        "begin graph\n"
        '   data "one.dat" d1=c1,c2\n'
        "   bar d1 fill red width 0.3\n"
        "end graph\n",
        encoding="utf-8",
    )

    figure = glp.open_gle(str(tmp_path / "hand.gle"))
    (bar,) = figure.axes_list[0].bars
    assert bar["width"] == 0.3

    out = tmp_path / "round.gle"
    figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "    bar d1 fill red width 0.3" in text
    assert "width 0.5" not in text

    assert _drawn_bar_widths(tmp_path, text, "round") == pytest.approx(
        [0.3], abs=RANGE_TOLERANCE
    )

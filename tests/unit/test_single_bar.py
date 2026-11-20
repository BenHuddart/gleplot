"""G16: the bar width GLE cannot derive, gleplot writes down.

A GLE bar set is sized by its data. ``drawBar`` takes the width from
``GLEDataPairs::getMinXInterval()`` -- the smallest strictly positive gap
between consecutive x values -- divided by twice the number of grouped
datasets, and ``get_dataset_ranges`` widens the x data range by half that
same interval either side. A dataset with no positive gap has neither: one
bar, or every bar at one x, or a descending x column. GLE's answer is
"invalid range for dimension X" where the range collapsed, and bar polygons
full of ``-nan`` where it did not.

So gleplot supplies both numbers from one nominal spacing, and this module
holds the emission side of that: which datasets get a width, what the width
is, and -- the point of the whole exercise -- that no dataset GLE can already
size changes by a byte. Every number here is justified against the live
binary in ``tests/integration/test_degenerate_autoscale_compiles.py``
(cross-cutting rule 2); none is re-derived from GLE's source in Python.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.writer import GLEWriter

from . import _single_bar_battery as sbb

NEIGHBOUR_SNAPSHOT = json.loads(
    (Path(__file__).parent / "single_bar_neighbour_emissions.json").read_text(
        encoding="utf-8"
    )
)

#: The width GLE itself computes for a bar set of one dataset at unit
#: spacing: ``min_int/(nbars*2)`` = ``1/2``. Measured off a compiled two-bar
#: chart in the integration battery, not asserted from GLE's source.
GLE_UNIT_SPACING_WIDTH = 0.5


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _axes():
    fig = glp.figure(data_prefix="sb")
    return fig, fig.add_subplot(111)


def _generate(fig):
    """Generate, refusing any warning: sizing a bar is not news."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        return fig._generate_gle_with_files()


def _bar_lines(text):
    return [
        line.strip() for line in text.splitlines() if line.strip().startswith("bar ")
    ]


def _axis_line(text, axis):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(f"{axis}axis ") or line.strip() == f"{axis}axis"
    ]
    assert len(lines) <= 1, lines
    return lines[0] if lines else None


# --------------------------------------------------------------------------- #
# The predicate: exactly the datasets GLE cannot measure
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "x,expected",
    [
        ([1.0, 2.0], 1.0),
        ([1.0, 2.0, 3.0], 1.0),
        ([0.0, 5.0, 5.25, 12.0], 0.25),
        ([1.0, 2.0, 2.0, 3.0], 1.0),
        ([1.0], float("inf")),
        ([], float("inf")),
        ([1.0, 1.0], float("inf")),
        ([3.0, 1.0], float("inf")),
    ],
    ids=[
        "two_points",
        "unit_spacing",
        "uneven_min_is_not_the_first_gap",
        "a_zero_gap_is_skipped",
        "one_point",
        "no_points",
        "every_x_equal",
        "descending",
    ],
)
def test_the_interval_helper_is_gles_own_rule(x, expected):
    """``getMinXInterval``: smallest *positive* consecutive gap, else infinite.

    Consecutive, not sorted -- which is why a descending column has none --
    and strictly positive, which is why a repeated x is skipped rather than
    making the interval zero.
    """
    assert GLEWriter.gle_bar_min_x_interval(np.array(x, dtype=float)) == expected


@pytest.mark.parametrize(
    "x,writes_width",
    [
        ([1.0, 2.0], False),
        ([0.0, 0.05, 0.1], False),
        ([1.0, 2.0, 2.0, 3.0], False),
        ([1.0], True),
        ([1.0, 1.0, 1.0], True),
        ([3.0, 1.0], True),
    ],
    ids=[
        "two_bars",
        "sub_unit_spacing",
        "repeated_x_with_a_gap_elsewhere",
        "one_bar",
        "every_x_equal",
        "descending",
    ],
)
def test_a_width_is_written_only_where_gle_has_none(x, writes_width):
    width = GLEWriter.bar_width_gle_cannot_derive(np.array(x, dtype=float))
    assert (width is not None) == writes_width
    if writes_width:
        assert width == GLE_UNIT_SPACING_WIDTH


def test_the_written_width_is_gles_own_formula_at_the_nominal_spacing():
    """``min_int/(nbars*2)`` with ``min_int`` = the nominal and ``nbars`` = 1.

    The nominal is what makes the two halves of G16 one decision: the same
    number sets the width and the half-interval the x range is widened by.
    """
    nominal = GLEWriter.BAR_FALLBACK_SPACING
    assert nominal == 1.0
    assert GLEWriter.bar_width_gle_cannot_derive(np.array([1.0])) == nominal / (1 * 2)
    assert nominal / (1 * 2) == GLE_UNIT_SPACING_WIDTH


# --------------------------------------------------------------------------- #
# What a single bar now emits
# --------------------------------------------------------------------------- #


def test_a_single_bar_writes_its_width_and_its_range():
    fig, ax = _axes()
    ax.bar([1], [5])

    text, _files = _generate(fig)
    assert _bar_lines(text) == ["bar d1 fill rgb255(31,119,180) width 0.5"]
    assert _axis_line(text, "x") == "xaxis min 0.5 max 1.5"


def test_the_lone_bar_sits_in_the_middle_half_of_the_frame():
    """Range and width read off the same nominal, so the bar cannot fall off.

    ``x ± spacing/2`` for the frame and ``spacing/2`` for the bar puts the
    drawn rectangle from ``x - 0.25`` to ``x + 0.25`` inside a frame running
    ``x - 0.5`` to ``x + 0.5`` -- centred, and clear of both edges. The
    compiled geometry is measured in the integration battery.
    """
    fig, ax = _axes()
    ax.bar([7.0], [5.0])
    _generate(fig)

    lo, hi = ax.get_xlim()
    width = GLEWriter.bar_width_gle_cannot_derive(np.array([7.0]))
    assert (lo, hi) == (6.5, 7.5)
    assert lo < 7.0 - width / 2 and 7.0 + width / 2 < hi


@pytest.mark.parametrize(
    "x,heights,expected_axis",
    [
        ([1.0, 1.0], [5.0, 3.0], "xaxis min 0.5 max 1.5"),
        ([3.0, 1.0], [5.0, 3.0], "xaxis min 1 max 3"),
    ],
    ids=["every_x_equal", "descending"],
)
def test_the_other_two_unmeasurable_shapes_are_fixed_the_same_way(
    x, heights, expected_axis
):
    """Same predicate, and only the collapsed one needs its range widened.

    A descending column already spans a range GLE accepts -- it fails on the
    width alone, and its emitted range must stay the data's.
    """
    fig, ax = _axes()
    ax.bar(x, heights)

    text, _files = _generate(fig)
    assert _bar_lines(text) == ["bar d1 fill rgb255(31,119,180) width 0.5"]
    assert _axis_line(text, "x") == expected_axis


def test_a_lone_bar_beside_other_data_takes_the_width_and_leaves_the_range():
    """The silent-garbage case: the range was fine, the polygons were ``-nan``."""
    fig, ax = _axes()
    ax.bar([1.0], [5.0])
    ax.plot([0.0, 10.0], [1.0, 9.0])

    text, _files = _generate(fig)
    assert _bar_lines(text) == ["bar d1 fill rgb255(31,119,180) width 0.5"]
    assert _axis_line(text, "x") == "xaxis min 0 max 10"


def test_an_explicit_range_around_a_lone_bar_is_still_the_callers():
    fig, ax = _axes()
    ax.bar([1.0], [5.0])
    ax.set_xlim(-2.0, 4.0)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis min -2 max 4"
    assert _bar_lines(text) == ["bar d1 fill rgb255(31,119,180) width 0.5"]


def test_a_lone_bar_on_a_log_x_axis_keeps_the_log_repairs_range():
    """The widened lower edge is non-positive; ``_apply_log_limits`` owns it.

    G16 must not hand a log axis a bound the engine would reject, so the
    widening steps aside and the existing repair produces the range.
    """
    fig, ax = _axes()
    ax.bar([0.5], [5.0])
    ax.set_xscale("log")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        text, _files = fig._generate_gle_with_files()

    line = _axis_line(text, "x")
    assert line is not None and "log" in line
    lo = float(line.split("min ")[1].split()[0])
    assert lo > 0.0


def test_a_measurable_bar_whose_log_range_collapses_is_not_widened():
    """A log axis can collapse a range GLE can still size bars from.

    ``bar([-1, 5], ...)`` has a gap of 6, so GLE derives its own width and
    nothing is written; the log axis nevertheless sees one positive value.
    The widening is keyed on the *width* predicate, not on the collapse, so
    it stays out of this -- the range is ``_apply_log_limits``' repair.
    """
    fig, ax = _axes()
    ax.bar([-1.0, 5.0], [5.0, 3.0])
    ax.set_xscale("log")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        text, _files = fig._generate_gle_with_files()

    assert _bar_lines(text) == ["bar d1 fill rgb255(31,119,180)"]
    assert _axis_line(text, "x") == "xaxis min 5 max 50 log"


def test_a_lone_bar_in_a_shared_grid_widens_both_panels():
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="sb")
    for ax in axes:
        ax.bar([2.0], [5.0])

    text, _files = _generate(fig)
    assert _bar_lines(text) == [
        "bar d1 fill rgb255(31,119,180) width 0.5",
        "bar d2 fill rgb255(31,119,180) width 0.5",
    ]
    assert text.count("xaxis min 1.5 max 2.5") == 2


def test_a_hidden_lone_bar_contributes_neither_width_nor_range():
    fig, ax = _axes()
    ax.bar([1.0], [5.0])
    ax.bars[-1]["visible"] = False
    ax.plot([0.0, 10.0], [1.0, 9.0])

    text, _files = _generate(fig)
    assert _bar_lines(text) == []
    assert _axis_line(text, "x") == "xaxis min 0 max 10"


def test_the_widened_range_is_the_axes_own_answer_too():
    """``get_xlim`` reports the range that will be drawn, as it does anywhere."""
    fig, ax = _axes()
    ax.bar([1.0], [5.0])
    _generate(fig)
    assert ax.get_xlim() == (0.5, 1.5)


# --------------------------------------------------------------------------- #
# No new model state, and a fixed point
# --------------------------------------------------------------------------- #


def test_serialization_gained_no_fields():
    """G16 adds no model state: the width is a write-time derivation.

    G19 later gave ``BarSeries`` a real ``width`` field, but it stays
    *absent* unless the caller (or a hand-written script) names one, so a
    bar sized by G16 still serializes exactly as it did -- which is what
    keeps the derivation, and this module's byte-identity battery, honest.
    See ``tests/unit/test_bar_width_field.py``.
    """
    fig, ax = _axes()
    ax.bar([1.0], [5.0])
    before = set(fig.to_dict()["figure"]["axes"][0]["bars"][0])

    _generate(fig)
    assert set(fig.to_dict()["figure"]["axes"][0]["bars"][0]) == before
    assert "width" not in before


@pytest.mark.parametrize(
    "x,heights",
    [([1.0], [5.0]), ([1.0, 1.0], [5.0, 3.0]), ([3.0, 1.0], [5.0, 3.0])],
    ids=["one_bar", "every_x_equal", "descending"],
)
def test_a_sized_bar_is_a_writer_parse_writer_fixed_point(
    tmp_path, x, heights, monkeypatch
):
    """The emitted ``width`` survives the round trip -- by re-derivation.

    The recognizer rebuilds the same one-x dataset, so the writer computes
    the same width again; ``tests/parser/test_fixed_point.py``'s empty
    exemption set stays empty without the model carrying a width field.
    """
    monkeypatch.chdir(tmp_path)
    fig, ax = _axes()
    ax.bar(x, heights)
    fig.savefig_gle("first.gle")
    first = Path("first.gle").read_text(encoding="utf-8")

    glp.open_gle("first.gle").savefig_gle("second.gle")
    assert Path("second.gle").read_text(encoding="utf-8") == first
    assert "width 0.5" in first


# --------------------------------------------------------------------------- #
# Byte-level regression guard
# --------------------------------------------------------------------------- #


def test_the_neighbour_snapshot_covers_the_whole_battery():
    assert sorted(NEIGHBOUR_SNAPSHOT) == sorted(sbb.BUILDER_IDS)


@pytest.mark.parametrize("name", sbb.BUILDER_IDS)
def test_a_measurable_bar_emits_byte_identically_to_pre_g16(name):
    """Every bar chart GLE could already size is untouched, warnings included."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        text, files = sbb.emit(name)

    reference = NEIGHBOUR_SNAPSHOT[name]
    assert text == reference["gle"]
    assert files == reference["files"]
    assert [str(w.message) for w in caught] == reference["warnings"]

"""G19: ``width`` as a real ``BarSeries`` field, and what it does to the range.

G16 taught the writer to *derive* a bar width for the three dataset shapes
GLE cannot size from its own data. G19 lets the document carry one instead:
``Axes.bar(..., width=w)`` (and a hand-written ``bar dN width w``, see
``tests/parser/test_bar_options.py``) put the number in the model, the writer
emits it verbatim, and G16's derivation steps aside.

The one design question that needed the engine to answer it is the range.
GLE widens a bar dataset's x data range by half the *data's* minimum x
interval -- ``get_dataset_ranges`` in ``graph2.cpp`` reads
``getMinXInterval()``, never ``br[b]->width`` -- so a width on the script
changes nothing about the range of a bar set GLE can measure. Measured on
4.3.10: two bars at x = 1, 2 autoscale to xgmin/xgmax = 0.4/2.6 with no
width, with ``width 0.2`` and with ``width 2`` alike. Where GLE *cannot*
measure, and gleplot supplies the range itself, the half-span is the width
being drawn -- which is the engine's own proportion, because half-interval
and derived width are the same number for a one-dataset bar set. The
compiled geometry behind both claims is measured in
``tests/integration/test_degenerate_autoscale_compiles.py`` (cross-cutting
rule 2); this module holds the model and emission side.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.series import BarSeries
from gleplot.writer import GLEWriter


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _axes():
    fig = glp.figure(data_prefix="bw")
    return fig, fig.add_subplot(111)


def _generate(fig):
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
# The field
# --------------------------------------------------------------------------- #


def test_width_is_a_declared_bar_field():
    assert "width" in BarSeries.FIELDS
    assert "width" not in BarSeries.ARRAY_FIELDS


def test_an_unset_width_stays_absent():
    """The default has to be *absent*, not ``None``.

    G16's derivation is keyed on there being no width, and every bar chart
    written before G19 has no such key; materializing one would change the
    serialized shape of every existing project.
    """
    fig, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0])
    assert "width" not in ax.bars[0]
    assert "width" not in fig.to_dict()["figure"]["axes"][0]["bars"][0]


def test_width_and_bottom_are_matplotlibs_positional_order():
    """bar(x, height, width, bottom) writes what the keyword call writes."""
    by_keyword, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], width=0.5, bottom=1)
    by_position, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], 0.5, 1)
    assert _generate(by_position) == _generate(by_keyword)
    with pytest.raises(TypeError, match="positional argument"):
        ax.bar([1.0], [5.0], 0.5, 1, "center")


@pytest.mark.parametrize("colour", ["red", ["red", "blue"]])
def test_a_colour_in_the_width_place_names_the_new_order(colour):
    fig, ax = _axes()
    with pytest.raises(
        TypeError, match=r"\(x, height, width, bottom\); pass a colour as color="
    ):
        ax.bar([1.0, 2.0], [5.0, 3.0], colour)
    with pytest.raises(TypeError, match=r"barh\(\) height must be a number or one"):
        ax.barh([1.0, 2.0], [5.0, 3.0], colour)
    assert ax.bars == []


def test_per_bar_widths_split_the_call_one_width_each():
    """#561: matplotlib takes one width per bar; GLE one per dataset."""
    fig, ax = _axes()
    ax.bar([1.0, 2.0, 3.0], [5.0, 3.0, 4.0], [0.4, 0.6, 0.4], label="w")
    ax.barh([5.0, 6.0], [1.0, 2.0], [0.3, 0.5])

    text, _files = _generate(fig)
    blue = "fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0"
    orange = "fill rgb255(255,127,14) color rgb255(255,127,14) lwidth 0"
    assert _bar_lines(text) == [
        f"bar d1 {blue} width 0.4",
        f"bar d2 {blue} width 0.6",
        f"bar d3 {blue} width 0.4",
        f"bar d4 {orange} width 0.3 horiz",
        f"bar d5 {orange} width 0.5 horiz",
    ]
    assert [bar.get("label") for bar in ax.bars[:3]] == ["w", None, None]


@pytest.mark.parametrize("widths", [[0.4], [0.4, 0.4], np.array([0.4, 0.4])])
def test_a_uniform_width_sequence_writes_the_scalar_script(widths):
    scalar, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], 0.4)
    expected = _generate(scalar)
    glp.close()
    sequence, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], widths)
    assert _generate(sequence) == expected
    assert len(ax.bars) == 1


def test_a_width_sequence_of_the_wrong_length_raises():
    fig, ax = _axes()
    with pytest.raises(
        ValueError, match=r"bar\(\) width has 3 values for 2 bars.*color="
    ):
        ax.bar([1.0, 2.0], [5.0, 3.0], (1, 0, 0))
    with pytest.raises(ValueError, match=r"width must be finite"):
        ax.bar([1.0, 2.0], [5.0, 3.0], [0.4, float("nan")])
    with pytest.raises(ValueError, match=r"barh\(\) height has 3 values for 2 bars"):
        ax.barh([1.0, 2.0], [5.0, 3.0], [0.1, 0.2, 0.3])
    with pytest.raises(TypeError, match=r"width must be a number or one per bar"):
        ax.bar([1.0, 2.0], [5.0, 3.0], [[0.4, 0.6]])
    assert ax.bars == []


def test_a_label_in_the_bottom_place_names_the_new_order():
    fig, ax = _axes()
    with pytest.raises(TypeError, match=r"bottom must be .* got 'counts'.*label="):
        ax.bar([1.0, 2.0], [5.0, 3.0], None, "counts")


def test_figure_and_module_bar_forward_width_and_bottom_positionally():
    fig, ax = _axes()
    fig.bar([1.0, 2.0], [5.0, 3.0], 0.5, 1)
    glp.bar([1.0, 2.0], [5.0, 3.0], 0.25, 2)
    first, second = ax.bars
    assert (first["width"], second["width"]) == (0.5, 0.25)
    assert (first["bottom"].tolist(), second["bottom"].tolist()) == ([1, 1], [2, 2])


def test_an_explicit_width_is_stored_as_a_float():
    fig, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], width=1)
    assert ax.bars[0]["width"] == 1.0
    assert isinstance(ax.bars[0]["width"], float)


def test_the_width_field_survives_serialization():
    fig, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], width=0.25)
    once = fig.to_dict()
    assert once["figure"]["axes"][0]["bars"][0]["width"] == 0.25

    restored = glp.Figure.from_dict(once)
    assert restored.axes_list[0].bars[0]["width"] == 0.25
    assert restored.to_dict() == once


# --------------------------------------------------------------------------- #
# Emission: the explicit width wins, and suppresses the derived one
# --------------------------------------------------------------------------- #


def test_a_measurable_bar_set_gains_the_width_it_was_given():
    """GLE could size this one; the caller asked for something else."""
    fig, ax = _axes()
    ax.bar([1.0, 2.0], [5.0, 3.0], width=0.25)

    text, _files = _generate(fig)
    assert _bar_lines(text) == [
        "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width 0.25"
    ]


def test_an_explicit_width_suppresses_the_derived_one():
    """The G16 shapes: one number is emitted, and it is the caller's.

    Without ``width=`` each of these emits ``width 0.5``; with it, 0.5 must
    not appear anywhere on the command.
    """
    for x, heights in (
        ([1.0], [5.0]),
        ([1.0, 1.0], [5.0, 3.0]),
        ([3.0, 1.0], [5.0, 3.0]),
    ):
        glp.close()
        fig, ax = _axes()
        ax.bar(x, heights, width=0.3)

        text, _files = _generate(fig)
        assert _bar_lines(text) == [
            "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width 0.3"
        ]
        assert GLEWriter.bar_width_gle_cannot_derive(np.asarray(x)) == 0.5


def test_the_two_writer_predicates_say_which_number_won():
    """``bar_width_to_emit`` is the single answer both halves are read off."""
    lone = np.array([1.0])
    pair = np.array([1.0, 2.0])

    # No explicit width: G16's derivation, and silence for a measurable set.
    assert GLEWriter.bar_width_to_emit(lone) == 0.5
    assert GLEWriter.bar_width_to_emit(pair) is None
    # An explicit width answers for every shape.
    assert GLEWriter.bar_width_to_emit(lone, 0.3) == 0.3
    assert GLEWriter.bar_width_to_emit(pair, 0.3) == 0.3


def test_zero_is_gles_own_no_width_given():
    """``drawBar``: ``if (br[b]->width == 0) br[b]->width = min_int/(nbars*2)``.

    So a stored 0 means "derive", exactly as it does to the engine -- and
    must not be emitted, which would leave the unmeasurable shapes with
    nothing to be sized by all over again.
    """
    assert GLEWriter.bar_explicit_width(0.0) is None
    assert GLEWriter.bar_width_to_emit(np.array([1.0]), 0.0) == 0.5
    assert GLEWriter.bar_width_to_emit(np.array([1.0, 2.0]), 0.0) is None


# --------------------------------------------------------------------------- #
# The range interaction, probed on GLE 4.3.10
# --------------------------------------------------------------------------- #


def test_a_width_never_pulls_a_range_gle_would_have_chosen():
    """Measured: GLE's own widening reads the DATA's interval, not the width.

    Two bars at x = 1, 2 give xgmin/xgmax = 0.4/2.6 on the live binary with
    no width, with ``width 0.2`` and with ``width 2``. So the range a
    measurable bar set gets is the data's, whatever width the script names:
    ``bar_range_half_span`` declines, and the emitted axis line does not
    move by a byte.
    """
    for width in (None, 0.2, 2.0):
        glp.close()
        fig, ax = _axes()
        ax.bar([1.0, 2.0], [5.0, 3.0], width=width)
        text, _files = _generate(fig)
        assert _axis_line(text, "x") == "xaxis min 1 max 2", width

    assert GLEWriter.bar_range_half_span(np.array([1.0, 2.0]), 0.2) is None
    assert GLEWriter.bar_range_half_span(np.array([1.0, 2.0]), 2.0) is None
    assert GLEWriter.bar_range_half_span(np.array([1.0, 2.0])) is None


@pytest.mark.parametrize(
    "width,expected",
    [
        (None, "xaxis min 0.5 max 1.5"),
        (0.3, "xaxis min 0.7 max 1.3"),
        (2.0, "xaxis min -1 max 3"),
    ],
    ids=["derived", "narrow", "wide"],
)
def test_the_range_gleplot_supplies_is_half_spanned_by_the_width(width, expected):
    """Where GLE cannot measure, the half-span is the width actually drawn.

    That keeps the lone bar in the middle half of its frame at any width --
    the same proportion GLE itself produces when it can measure, because
    ``min_int/2`` (its half-span) and ``min_int/(nbars*2)`` (its width) are
    one number for a single-dataset bar set. Measured in a 6 cm frame: this
    rule draws 3.0 cm of bar for ``width 0.3`` and for ``width 2`` alike,
    where a fixed 0.5 half-span draws 1.8 cm for the first and lets the
    second run edge to edge, clipped at both ends.
    """
    fig, ax = _axes()
    ax.bar([1.0], [5.0], width=width)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == expected
    assert ax.get_xlim() == (
        1.0 - (width if width is not None else 0.5),
        1.0 + (width if width is not None else 0.5),
    )


def test_the_bar_stays_inside_the_frame_at_any_width():
    """The invariant the half-span rule exists for."""
    for width in (0.05, 0.3, 1.0, 2.0, 50.0):
        glp.close()
        fig, ax = _axes()
        ax.bar([7.0], [5.0], width=width)
        _generate(fig)

        lo, hi = ax.get_xlim()
        assert lo < 7.0 - width / 2, width
        assert 7.0 + width / 2 < hi, width


def test_a_negative_width_still_gets_a_frame_that_holds_it():
    """A mirrored bar covers the same extent; the half-span is its size."""
    fig, ax = _axes()
    ax.bar([1.0], [5.0], width=-0.4)

    text, _files = _generate(fig)
    assert _bar_lines(text) == [
        "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width -0.4"
    ]
    assert _axis_line(text, "x") == "xaxis min 0.6 max 1.4"


def test_a_descending_column_with_a_width_keeps_the_datas_range():
    """Only a *collapsed* range is gleplot's to widen -- G16's rule, unchanged."""
    fig, ax = _axes()
    ax.bar([3.0, 1.0], [5.0, 3.0], width=0.2)

    text, _files = _generate(fig)
    assert _bar_lines(text) == [
        "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width 0.2"
    ]
    assert _axis_line(text, "x") == "xaxis min 1 max 3"


def test_an_explicit_range_around_a_widened_bar_is_still_the_callers():
    fig, ax = _axes()
    ax.bar([1.0], [5.0], width=0.3)
    ax.set_xlim(-2.0, 4.0)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis min -2 max 4"
    assert _bar_lines(text) == [
        "bar d1 fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0 width 0.3"
    ]


def test_a_hidden_bar_contributes_neither_its_width_nor_its_range():
    fig, ax = _axes()
    ax.bar([1.0], [5.0], width=0.3)
    ax.bars[-1]["visible"] = False
    ax.plot([0.0, 10.0], [1.0, 9.0])

    text, _files = _generate(fig)
    assert _bar_lines(text) == []
    assert _axis_line(text, "x") == "xaxis min 0 max 10"


# --------------------------------------------------------------------------- #
# Fixed point
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "x,heights,width",
    [
        ([1.0], [5.0], 0.3),
        ([1.0, 2.0], [5.0, 3.0], 0.25),
        ([3.0, 1.0], [5.0, 3.0], 0.2),
    ],
    ids=["one_bar", "two_bars", "descending"],
)
def test_an_explicit_width_is_a_writer_parse_writer_fixed_point(
    tmp_path, monkeypatch, x, heights, width
):
    """Emitted, re-parsed into the field, re-emitted byte-identically."""
    monkeypatch.chdir(tmp_path)
    fig, ax = _axes()
    ax.bar(x, heights, width=width)
    fig.savefig_gle("first.gle")
    first = Path("first.gle").read_text(encoding="utf-8")
    assert f"width {width:g}" in first

    reparsed = glp.open_gle("first.gle")
    assert reparsed.axes_list[0].bars[0]["width"] == width
    reparsed.savefig_gle("second.gle")
    assert Path("second.gle").read_text(encoding="utf-8") == first


def test_a_zero_among_per_bar_widths_takes_the_derived_width():
    """GLE reads ``width 0`` as "not given"; that piece gets the set's width."""
    fig, ax = _axes()
    ax.bar([1.0, 1.2], [3.0, 4.0], [0, 0.05])
    text, _files = _generate(fig)
    blue = "fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0"
    assert _bar_lines(text) == [f"bar d1 {blue} width 0.1", f"bar d2 {blue} width 0.05"]

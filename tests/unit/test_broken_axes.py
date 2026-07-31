"""Unit tests for the broken (split) x-axis.

Mirrors the ``tests/unit/test_plotting.py`` style -- assert the object model
each API call produces AND substrings of the generated GLE. The behaviour
worth pinning down is the assembly geometry (adjacent graph boxes whose
widths follow ``width_ratios``), the frame-side suppression that makes the
segments read as one panel, the seam decoration, and the fan-out contract
(declare a series once, get it in every segment, from one shared sidecar).
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp
from gleplot.brokenaxes import BrokenAxes
from gleplot.writer import GLEWriter


T = np.linspace(0.0, 3.0, 40)
A = np.exp(-T)


def _gle(fig):
    text, files = fig._generate_gle_with_files()
    return text, files


def _blocks(text):
    """(amove_x, amove_y, size_w, size_h) for each graph block, in order."""
    out = []
    pattern = re.compile(
        r"amove (\S+) (\S+)\nbegin graph\n    size (\S+) (\S+)", re.MULTILINE
    )
    for m in pattern.finditer(text):
        out.append(tuple(float(v) for v in m.groups()))
    return out


def _fig(**kwargs):
    fig = glp.figure(figsize=(6.0, 4.0), data_prefix="bx")
    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)], width_ratios=[1, 3], **kwargs
    )
    bax.set_ylim(0.0, 1.0)
    return fig, bax


# --------------------------------------------------------------------------- #
# Construction and validation
# --------------------------------------------------------------------------- #


def test_segments_are_real_axes_in_the_figure():
    fig, bax = _fig()
    assert isinstance(bax, BrokenAxes)
    assert len(bax) == 2
    assert list(bax) == bax.segments
    assert bax[0] is bax.segments[0]
    assert fig.axes_list == bax.segments
    assert fig.broken_axes == [bax]


def test_each_segment_gets_its_own_x_range():
    _fig_, bax = _fig()
    assert bax[0].get_xlim() == (0.0, 0.02)
    assert bax[1].get_xlim() == (0.02, 3.0)


def test_segments_share_one_position_in_the_grid():
    fig = glp.figure(data_prefix="bx")
    fig.add_subplot(2, 1, 1).plot(T, A)
    bax = fig.add_broken_xaxes([(0, 1), (1, 5)], position=(2, 1, 2))
    assert all(seg.position == (2, 1, 2) for seg in bax.segments)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(xlims=[(0, 1)]),  # only one segment
        dict(xlims=[(1, 0), (1, 2)]),  # reversed range
        dict(xlims=[(0, 1), (1, 2)], width_ratios=[1]),  # wrong length
        dict(xlims=[(0, 1), (1, 2)], width_ratios=[1, 0]),  # non-positive
        dict(xlims=[(0, 1), (1, 2)], divider="squiggle"),  # unknown style
    ],
)
def test_invalid_construction_raises(kwargs):
    fig = glp.figure(data_prefix="bx")
    xlims = kwargs.pop("xlims")
    with pytest.raises(ValueError):
        fig.add_broken_xaxes(xlims, **kwargs)


def test_set_xlim_is_refused_with_a_pointer_to_the_right_knob():
    _fig_, bax = _fig()
    with pytest.raises(TypeError, match="one range per segment"):
        bax.set_xlim(0, 1)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #


def test_segment_widths_follow_width_ratios_and_boxes_are_adjacent():
    fig, _bax = _fig(gap=0.0)
    text, _files = _gle(fig)
    blocks = _blocks(text)
    assert len(blocks) == 2

    (x0, y0, w0, h0), (x1, y1, w1, h1) = blocks
    assert h0 == h1 and y0 == y1  # same vertical extent: one shared y-axis
    assert w1 == pytest.approx(3 * w0, rel=1e-9)  # width_ratios=[1, 3]
    assert x1 == pytest.approx(x0 + w0, rel=1e-9)  # touching, no gap


def test_gap_separates_the_boxes_and_comes_out_of_the_cell():
    fig, _bax = _fig(gap=0.4)
    text, _files = _gle(fig)
    (x0, _y0, w0, _h0), (x1, _y1, w1, _h1) = _blocks(text)
    assert x1 == pytest.approx(x0 + w0 + 0.4, rel=1e-9)
    # The ratios still describe the plotted widths, not widths+gap.
    assert w1 == pytest.approx(3 * w0, rel=1e-9)


def test_segment_extent_rejects_a_cell_too_small_for_the_gaps():
    _fig_, bax = _fig(gap=2.0)
    with pytest.raises(ValueError, match="do not fit"):
        bax.segment_extent(0, 1.0)


# --------------------------------------------------------------------------- #
# Frame suppression: the assembly must read as one panel
# --------------------------------------------------------------------------- #


def test_inner_frame_sides_are_switched_off():
    _fig_, bax = _fig()
    left, right = bax.segments
    assert left._y2axis_off is True and left._yaxis_off is False
    assert right._yaxis_off is True and right._y2axis_off is False


def test_only_the_leftmost_segment_carries_the_y_axis():
    fig, bax = _fig()
    bax.set_ylabel("Asymmetry (%)")
    text, _files = _gle(fig)

    assert text.count('ytitle "Asymmetry (%)"') == 1
    assert "    y2axis off" in text
    assert re.search(r"^    yaxis .* off$", text, re.MULTILINE)
    assert "    ylabels off" in text


def test_three_segments_switch_off_both_inner_sides_of_the_middle_one():
    fig = glp.figure(data_prefix="bx")
    bax = fig.add_broken_xaxes([(0, 1), (1, 2), (2, 3)])
    a, b, c = bax.segments
    assert (a._yaxis_off, a._y2axis_off) == (False, True)
    assert (b._yaxis_off, b._y2axis_off) == (True, True)
    assert (c._yaxis_off, c._y2axis_off) == (True, False)


def test_rightmost_segment_asks_gle_for_its_outer_frame_edge():
    """``yaxis ... off`` also kills GLE's mirrored y2 axis unless re-asserted.

    The rightmost segment always has the y axis off (it belongs to the
    leftmost segment) and always wants its right-hand frame line: without an
    explicit ``y2axis on`` the panel renders open on the right and reads as
    clipped.
    """
    fig, bax = _fig()
    bax.set_ylabel("Asymmetry (%)")
    text, _files = _gle(fig)

    assert "    y2axis on" in text
    # Exactly one segment asks for it, and it is not the one that was
    # explicitly switched off.
    assert text.count("    y2axis on") == 1
    assert text.count("    y2axis off") == 1


def test_middle_segment_does_not_get_an_outer_frame_edge():
    fig = glp.figure(data_prefix="bx")
    bax = fig.add_broken_xaxes([(0, 1), (1, 2), (2, 3)])
    bax.set_ylim(0.0, 1.0)
    text, _files = _gle(fig)

    # Two inner sides switched off (segments 0 and 1), one outer edge on.
    assert text.count("    y2axis off") == 2
    assert text.count("    y2axis on") == 1


def test_contiguous_segments_drop_the_duplicated_seam_label():
    _fig_, bax = _fig()
    assert bax[1]._remove_first_xtick is True


def test_non_contiguous_segments_keep_both_boundary_labels():
    fig = glp.figure(data_prefix="bx")
    bax = fig.add_broken_xaxes([(0, 1), (5, 10)])
    assert bax[1]._remove_first_xtick is False


def test_trim_seam_labels_can_be_switched_off():
    fig = glp.figure(data_prefix="bx")
    bax = fig.add_broken_xaxes([(0, 1), (1, 2)], trim_seam_labels=False)
    assert bax[1]._remove_first_xtick is False


# --------------------------------------------------------------------------- #
# Seam decoration
# --------------------------------------------------------------------------- #


def test_line_divider_draws_one_rule_at_the_seam():
    fig, _bax = _fig(divider="line", gap=0.0)
    text, _files = _gle(fig)
    assert "amove xg(xgmax)+0 yg(ygmin)" in text
    assert "aline xg(xgmax)+0 yg(ygmax)" in text


def test_line_divider_is_centred_in_a_nonzero_gap():
    fig, _bax = _fig(divider="line", gap=0.4)
    text, _files = _gle(fig)
    assert "amove xg(xgmax)+0.2 yg(ygmin)" in text


def test_slash_divider_draws_four_strokes_and_defaults_to_a_small_gap():
    fig, bax = _fig(divider="slash")
    assert bax.gap == pytest.approx(0.15)
    text, _files = _gle(fig)
    assert text.count("aline xg(xgmax)") == 4  # two marks x two frame lines
    assert "yg(ygmin)" in text and "yg(ygmax)" in text


def test_divider_none_draws_nothing():
    fig, _bax = _fig(divider="none")
    text, _files = _gle(fig)
    assert "xg(xgmax)" not in text
    assert _fig(divider="none")[1].gap == 0.0


def test_divider_style_and_colour_are_emitted():
    fig, _bax = _fig(divider="line", divider_color="red", divider_lstyle=3)
    text, _files = _gle(fig)
    assert "set color RED" in text
    assert "set lstyle 3" in text


def test_seam_decoration_is_wrapped_so_state_does_not_leak():
    fig, _bax = _fig(divider="line")
    text, _files = _gle(fig)
    assert text.count("gsave") == text.count("grestore")


# --------------------------------------------------------------------------- #
# Shared titles
# --------------------------------------------------------------------------- #


def test_x_title_is_written_once_centred_on_the_whole_assembly():
    fig, bax = _fig()
    bax.set_xlabel("t (us)")
    text, _files = _gle(fig)

    assert text.count('write "t (us)"') == 1
    assert "xtitle" not in text  # not delegated to a single segment
    assert "set just tc" in text

    # Centred on the cell, i.e. midway between the left edge of the first box
    # and the right edge of the last.
    blocks = _blocks(text)
    centre = (blocks[0][0] + blocks[-1][0] + blocks[-1][2]) / 2.0
    written = float(re.search(r"amove ([\d.eE+-]+) yg\(ygmin\)-", text).group(1))
    assert written == pytest.approx(centre, abs=1e-4)


def test_title_is_written_above_the_assembly():
    fig, bax = _fig()
    bax.set_title("Fig. 2(a)")
    text, _files = _gle(fig)
    assert 'write "Fig. 2(a)"' in text
    assert "yg(ygmax)+" in text
    assert "set just bc" in text


def test_x_and_title_distances_are_overridable():
    fig, bax = _fig(xlabel_dist=1.25, title_dist=0.9)
    bax.set_xlabel("x")
    bax.set_title("t")
    text, _files = _gle(fig)
    assert "yg(ygmin)-1.25" in text
    assert "yg(ygmax)+0.9" in text


# --------------------------------------------------------------------------- #
# Fan-out
# --------------------------------------------------------------------------- #


def test_a_series_declared_once_appears_in_every_segment():
    fig, bax = _fig()
    bax.errorbar(T, A, yerr=0.05, fmt="none", marker="o")
    assert len(bax[0].errorbars) == 1
    assert len(bax[1].errorbars) == 1


def test_fanned_out_series_share_a_single_sidecar():
    fig, bax = _fig()
    bax.plot(T, A, color="red")
    text, files = _gle(fig)

    shared = bax[0].lines[0]["data_file"]
    assert bax[1].lines[0]["data_file"] == shared
    assert len(files) == 1
    assert text.count(f"data {shared}") == 2  # once per graph block


def test_guides_do_not_share_a_sidecar_because_their_extent_differs():
    """Regression: a shared file let the last segment written win, so an
    axhline only drew in one segment."""
    fig, bax = _fig()
    bax.axhline(0.5)
    left, right = bax[0].reflines[0], bax[1].reflines[0]
    assert left["data_file"] != right["data_file"]

    _text, files = _gle(fig)
    rows = {
        name: [
            [float(v) for v in ln.split()]
            for ln in files[name].strip().splitlines()
            if ln[0].isdigit() or ln[0] == "-"
        ]
        for name in (left["data_file"], right["data_file"])
    }
    assert rows[left["data_file"]] == [[0.0, 0.5], [0.02, 0.5]]
    assert rows[right["data_file"]] == [[0.02, 0.5], [3.0, 0.5]]


def test_axvspan_only_materializes_where_it_lands():
    fig, bax = _fig()
    bax.axvspan(1.0, 2.0, color="lightgray")
    _text, files = _gle(fig)
    # Both segments emit a band; GLE clips the left one out of view because
    # its x range (0-0.02) does not reach 1.0.
    left = bax[0].spans[0]["data_file"]
    assert "1 " in files[left] or "1.0" in files[left]


def test_fanout_returns_the_underlying_return_value_for_guides():
    _fig_, bax = _fig()
    entry = bax.axvline(0.5)
    assert entry is bax[0].reflines[0]


def test_text_goes_to_the_segment_that_contains_x():
    _fig_, bax = _fig()
    bax.text(1.0, 0.5, "late")
    assert bax[0].texts == []
    assert len(bax[1].texts) == 1


def test_text_outside_every_segment_warns_and_is_dropped():
    fig = glp.figure(data_prefix="bx")
    bax = fig.add_broken_xaxes([(0, 1), (5, 10)])
    with pytest.warns(UserWarning, match="falls in the break"):
        bax.text(3.0, 0.5, "in the gap")
    assert all(seg.texts == [] for seg in bax.segments)


# --------------------------------------------------------------------------- #
# Shared y state, ticks and legend
# --------------------------------------------------------------------------- #


def test_set_ylim_applies_to_every_segment():
    _fig_, bax = _fig()
    bax.set_ylim(-2.0, 7.0)
    assert all(seg.get_ylim() == (-2.0, 7.0) for seg in bax.segments)
    assert bax.get_ylim() == (-2.0, 7.0)


def test_per_segment_tick_intervals():
    fig, bax = _fig()
    bax.set_xticks(dticks=[0.01, 1.0])
    assert bax[0].xdticks == 0.01 and bax[1].xdticks == 1.0

    text, _files = _gle(fig)
    assert "dticks 0.01" in text and "dticks 1" in text


def test_scalar_tick_interval_applies_to_all_segments():
    _fig_, bax = _fig()
    bax.set_xticks(dsubticks=0.5)
    assert all(seg.xdsubticks == 0.5 for seg in bax.segments)


def test_tick_interval_sequence_of_the_wrong_length_raises():
    _fig_, bax = _fig()
    with pytest.raises(ValueError, match="one per"):
        bax.set_xticks(dticks=[1.0, 2.0, 3.0])


def test_explicit_tick_positions_on_one_segment():
    fig, bax = _fig()
    bax[0].set_xticks([0.0, 0.01, 0.02], ["0", "10", "20"])
    text, _files = _gle(fig)
    assert "    xplaces 0 0.01 0.02" in text
    assert '    xnames "0" "10" "20"' in text


def test_labels_without_places_raise():
    fig, bax = _fig()
    bax[0].xnames = ["a", "b"]
    with pytest.raises(ValueError, match="xnames"):
        _gle(fig)


def test_legend_is_suppressed_in_every_segment_by_default():
    fig, bax = _fig()
    bax.plot(T, A, label="2 K")
    text, _files = _gle(fig)
    assert text.count("key off") == 2
    assert "key pos" not in text


def test_legend_turns_exactly_one_segment_on():
    fig, bax = _fig()
    bax.plot(T, A, label="2 K")
    bax.legend()
    text, _files = _gle(fig)
    assert text.count("key pos") == 1
    assert text.count("key off") == 1


def test_legend_defaults_to_the_widest_segment():
    _fig_, bax = _fig()
    bax.plot(T, A, label="2 K")
    bax.legend()
    assert bax[1].legend_on is True
    assert bax[0].legend_on is False


def test_legend_segment_is_selectable():
    _fig_, bax = _fig()
    bax.plot(T, A, label="2 K")
    bax.legend(segment=0)
    assert bax[0].legend_on is True and bax[1].legend_on is False


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #


def test_round_trip_through_to_dict():
    fig, bax = _fig(divider="slash", gap=0.2)
    bax.plot(T, A, color="red", label="data")
    bax.set_xlabel("t")
    bax.set_ylabel("A")
    bax.axhline(0.1)

    restored = glp.Figure.from_dict(fig.to_dict())
    assert len(restored.broken_axes) == 1
    rb = restored.broken_axes[0]
    assert rb.xlims == bax.xlims
    assert rb.width_ratios == bax.width_ratios
    assert rb.divider == "slash" and rb.gap == pytest.approx(0.2)
    assert rb.xlabel_text == "t"
    assert rb.segments == restored.axes_list
    assert all(seg._break_owner is rb for seg in rb.segments)
    assert restored.to_dict() == fig.to_dict()


def test_regenerated_gle_is_byte_identical_after_a_round_trip():
    fig, bax = _fig(divider="slash")
    bax.errorbar(T, A, yerr=0.05, fmt="none", marker="o", label="data")
    bax.set_xlabel("t")
    restored = glp.Figure.from_dict(fig.to_dict())
    assert restored._generate_gle_with_files()[0] == fig._generate_gle_with_files()[0]


# --------------------------------------------------------------------------- #
# Writer-level frame contract
#
# GLE mirrors an axis onto the opposite side of the box by default, and that
# mirror is what closes the frame. Switching the primary side off takes the
# mirror with it, so a side that nobody turned off silently disappears. The
# writer re-asserts it.
# --------------------------------------------------------------------------- #


def _axes_block(**kwargs):
    writer = GLEWriter()
    writer.add_axes(xmin=0.0, xmax=1.0, ymin=0.0, ymax=1.0, **kwargs)
    return "\n".join(writer.lines_gle)


def test_writer_reasserts_the_mirrored_y2_side_when_the_y_axis_is_off():
    assert "    y2axis on" in _axes_block(yaxis_off=True)


def test_writer_does_not_reassert_a_y2_side_that_was_switched_off():
    text = _axes_block(yaxis_off=True, y2axis_off=True)
    assert "    y2axis off" in text
    assert "y2axis on" not in text


def test_writer_stays_silent_about_y2_when_the_y_axis_is_drawn():
    # GLE's own default already draws both sides; emitting anything here
    # would be noise (and would change every existing generated file).
    assert "y2axis" not in _axes_block()


def test_writer_reasserts_the_mirrored_x2_side_when_the_x_axis_is_off():
    assert "    x2axis on" in _axes_block(xaxis_off=True)


def test_writer_does_not_reassert_an_x2_side_that_was_switched_off():
    text = _axes_block(xaxis_off=True, x2axis_off=True)
    assert "    x2axis off" in text
    assert "x2axis on" not in text


def test_writer_stays_silent_about_x2_when_the_x_axis_is_drawn():
    assert "x2axis" not in _axes_block()

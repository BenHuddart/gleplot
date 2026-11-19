"""Axes styling survives .gle -> model -> .gle unchanged.

The recognizer half of plan task G10. Two bars:

* **Recovery** -- each styling clause the writer emits comes back as the
  model field it came from (not as passthrough), so the GUI can edit it.
* **Byte identity** -- re-saving reproduces the file exactly. The golden
  battery covers this for the styled builders too (see
  ``tests/parser/_golden_battery.py`` and ``test_fixed_point.py``); the cases
  here add hand-written shapes the writer never produces, where the correct
  answer is often "keep it verbatim as raw GLE" rather than "model it".
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot as glp
from gleplot.parser.recognizer import parse_gle_figure


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _write(tmp_path: Path, name: str, graph_body: str) -> Path:
    """A minimal single-graph .gle whose block body is ``graph_body``."""
    (tmp_path / "d.dat").write_text("0 0\n1 1\n2 4\n")
    path = tmp_path / name
    path.write_text(
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        f"{graph_body}"
        "end graph\n",
        encoding="utf-8",
    )
    return path


def _round_trip(fig, tmp_path: Path):
    """Save, parse, save again; return (first_text, second_text, warnings)."""
    first = tmp_path / "one.gle"
    fig.savefig_gle(str(first))
    text1 = first.read_text(encoding="utf-8")
    recognized = parse_gle_figure(first)
    second = tmp_path / "two.gle"
    recognized.figure.savefig_gle(str(second))
    return text1, second.read_text(encoding="utf-8"), recognized


def _styled_figure():
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], label="q")
    ax.set_title("Result")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_ylabel("Y2", axis="y2")
    ax.set_ylim(0, 10, axis="y2")
    ax.set_xlabel("X2", axis="x2")
    ax.set_xlim(0, 4, axis="x2")
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2 10", axis="y2")
    ax.set_tick_format("fix 2", axis="x2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14.0, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10.0, "BLUE", 0.35
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7.0, "GREEN", 45.0
    ax.y2ticklabel_size = 6.0
    ax.x2label_size = 9.0
    ax.x2ticklabel_angle = 20.0
    return fig, ax


# -- writer output round-trips -----------------------------------------------


def test_a_fully_styled_figure_re_emits_byte_identically(tmp_path):
    fig, _ = _styled_figure()
    text1, text2, recognized = _round_trip(fig, tmp_path)
    assert recognized.warnings == []
    assert text2 == text1


def test_the_styling_comes_back_on_the_model_not_in_passthrough(tmp_path):
    fig, original = _styled_figure()
    path = tmp_path / "styled.gle"
    fig.savefig_gle(str(path))
    ax = parse_gle_figure(path).figure.axes_list[0]

    assert ax.passthrough == []
    assert ax.xformat == "fix 1"
    assert ax.y2format == "sci 2 10"
    assert ax.xgrid == "both" and ax.ygrid == "both"
    assert ax.xgrid_lstyle == 2
    assert ax.xgrid_color == "GRAY40"
    # Sizes/widths are matplotlib points on the model and cm in the file, and
    # the writer rounds to 6 significant digits, so a recovered value lands
    # within ~1e-5 relative of the original rather than exactly on it. The
    # drift is below any UI precision and does not affect byte identity:
    # re-emitting the recovered value rounds to the same 6 digits (the
    # preceding test asserts that).
    assert ax.xgrid_lwidth == pytest.approx(0.4, rel=1e-4)
    assert ax.title_color == "RED" and ax.title_dist == 0.3
    assert ax.title_size == pytest.approx(14.0, rel=1e-4)
    assert ax.xlabel_color == "BLUE" and ax.xlabel_dist == 0.35
    assert ax.xlabel_size == pytest.approx(10.0, rel=1e-4)
    assert ax.xticklabel_color == "GREEN" and ax.xticklabel_angle == 45
    assert ax.xticklabel_size == pytest.approx(7.0, rel=1e-4)
    assert ax.y2ticklabel_size == pytest.approx(6.0, rel=1e-4)
    assert ax.x2format == "fix 2"
    assert ax.x2label_text == "X2"
    assert (ax.x2min, ax.x2max) == (0, 4)
    assert ax.x2label_size == pytest.approx(9.0, rel=1e-4)
    assert ax.x2ticklabel_angle == 20


@pytest.mark.parametrize("which", ["major", "both"])
def test_both_grid_modes_round_trip(tmp_path, which):
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.grid(True, which=which)
    text1, text2, recognized = _round_trip(fig, tmp_path)
    assert recognized.warnings == []
    assert text2 == text1
    assert recognized.figure.axes_list[0].xgrid == which


def test_an_unstyled_grid_round_trips_without_a_ticks_line(tmp_path):
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.grid(True)
    text1, text2, _ = _round_trip(fig, tmp_path)
    assert "xticks" not in text1
    assert text2 == text1


# -- hand-written shapes -----------------------------------------------------


def test_a_redundant_x2axis_lin_is_kept(tmp_path):
    """``lin`` with a linear bottom axis is not something the writer emits."""
    path = _write(tmp_path, "lin.gle", "   xaxis min 1 max 3\n   x2axis lin\n")
    recognized = parse_gle_figure(path)
    assert any(
        "x2axis lin" in line for line in recognized.figure.axes_list[0].passthrough
    )
    second = tmp_path / "two.gle"
    recognized.figure.savefig_gle(str(second))
    assert "x2axis lin" in second.read_text(encoding="utf-8")


def test_x2axis_off_is_reemitted(tmp_path):
    path = _write(tmp_path, "off.gle", "   x2axis off\n")
    recognized = parse_gle_figure(path)
    second = tmp_path / "two.gle"
    recognized.figure.savefig_gle(str(second))
    assert "x2axis off" in second.read_text(encoding="utf-8")


def test_a_hand_written_format_and_grid_are_recovered(tmp_path):
    path = _write(
        tmp_path,
        "hand.gle",
        '   xaxis min 0 max 2 format "fix 2" grid\n'
        "   xticks lstyle 2 color GRAY40\n",
    )
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.xformat == "fix 2"
    assert ax.xgrid == "major"
    assert ax.xgrid_lstyle == 2
    assert ax.xgrid_color == "GRAY40"
    assert ax.passthrough == []


def test_tick_styling_without_a_grid_stays_raw_gle(tmp_path):
    """Without a grid these style the ticks themselves, which the model does
    not express -- so the line is preserved rather than absorbed."""
    path = _write(tmp_path, "ticks.gle", "   xticks lstyle 2 color GRAY40\n")
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.xgrid is None
    assert ax.xgrid_lstyle is None
    assert any("xticks lstyle 2 color GRAY40" in line for line in ax.passthrough)
    assert any("not editable" in w for w in recognized.warnings)


def test_a_tick_length_keeps_the_whole_line_raw(tmp_path):
    path = _write(
        tmp_path, "len.gle", "   xaxis min 0 max 2 grid\n   xticks length -0.2\n"
    )
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.xgrid == "major"
    assert any("xticks length -0.2" in line for line in ax.passthrough)


def test_subticks_styled_differently_from_the_ticks_stay_raw(tmp_path):
    """One lstyle/lwidth pair describes both grids on the model, so a file
    that styles them apart cannot be folded into it."""
    path = _write(
        tmp_path,
        "sub.gle",
        "   xaxis min 0 max 2 grid\n"
        "   xticks lstyle 2\n"
        "   xsubticks on lstyle 5\n",
    )
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.xgrid == "major"  # not 'both': the subtick line was not absorbed
    assert ax.xgrid_lstyle == 2
    assert any("xsubticks on lstyle 5" in line for line in ax.passthrough)


def test_y2_grid_is_not_folded_into_the_y_grid(tmp_path):
    """GLE's grid is the axis' own ticks stretched across the graph; the model
    has no separate y2 grid, so 'y2axis grid' is preserved verbatim."""
    path = _write(tmp_path, "y2grid.gle", "   y2axis min 0 max 2 grid\n")
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.ygrid is None
    assert any("y2axis" in line and "grid" in line for line in ax.passthrough)


def test_a_bare_y2labels_on_is_preserved(tmp_path):
    """A visibility switch with nothing to style is not modeled."""
    path = _write(tmp_path, "y2on.gle", "   y2labels on\n")
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert any("y2labels on" in line for line in ax.passthrough)


@pytest.mark.parametrize(
    "body",
    [
        # No empty places on the primary axis: not the writer's switch.
        "   y2axis min 0 max 9\n   y2ticks on\n   xside color RED lstyle 2\n",
        # An empty places list, but no y2 scale in use.
        "   yticks off\n   ylabels off\n   y2ticks on\n   xside color RED lstyle 2\n",
    ],
)
def test_a_y2ticks_on_the_writer_would_not_write_stays_raw_in_order(tmp_path, body):
    path = _write(tmp_path, "y2ticks.gle", body)
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert [line.strip() for line in ax.passthrough][-2:] == [
        "y2ticks on",
        "xside color RED lstyle 2",
    ]


def test_hand_written_empty_places_with_a_twin_are_recovered(tmp_path):
    (tmp_path / "e.dat").write_text("0 5\n1 6\n2 7\n")
    body = (
        "   yticks off\n   ylabels off\n   y2ticks on\n   y2labels on\n"
        "   data e.dat d2=c1,c2\n   d2 line color RED y2axis\n"
    )
    ax = parse_gle_figure(_write(tmp_path, "twin.gle", body)).figure.axes_list[0]
    assert ax.yplaces == []
    assert ax._show_yticks
    assert not any("ticks" in line or "labels" in line for line in ax.passthrough)


def test_an_axis_title_with_an_unmodelled_option_stays_whole(tmp_path):
    """``adist`` has no model field, and an axis title is a single command
    -- re-emitting it shorn of it would silently drop it."""
    path = _write(tmp_path, "adist.gle", '   xtitle "X" hei 0.3 adist 0.4\n')
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.xlabel_text == ""
    assert ax.xlabel_size is None
    assert any('xtitle "X" hei 0.3 adist 0.4' in line for line in ax.passthrough)
    assert any("xtitle has unsupported options" in w for w in recognized.warnings)


def test_a_hand_written_axis_title_style_is_recovered(tmp_path):
    path = _write(tmp_path, "xt.gle", '   xtitle "X" hei 0.3 color RED dist 0.4\n')
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.xlabel_text == "X"
    assert ax.xlabel_color == "RED"
    assert ax.xlabel_dist == 0.4
    assert ax.xlabel_size == pytest.approx(8.505, rel=1e-9)


def test_tick_label_styling_alongside_labels_off_stays_raw(tmp_path):
    """The writer would drop the styling (labels that are off are not drawn),
    so absorbing it would lose it on the next save."""
    path = _write(tmp_path, "off.gle", "   xlabels off hei 0.3\n")
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax._show_xticks is True
    assert any("xlabels off hei 0.3" in line for line in ax.passthrough)


def test_an_rgb_expression_grid_colour_round_trips(tmp_path):
    fig = glp.figure(data_prefix="rgb")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.grid(True, color="#8c8c8c")
    text1, text2, recognized = _round_trip(fig, tmp_path)
    assert "rgb255(140,140,140)" in text1
    assert text2 == text1
    assert recognized.figure.axes_list[0].xgrid_color == "rgb255(140,140,140)"


def test_hand_written_fonts_axis_lines_and_tick_placement_are_recovered(tmp_path):
    path = _write(
        tmp_path,
        "gap10.gle",
        '   title "T" font texcmb\n'
        '   ytitle "Y" hei 0.3 font psh\n'
        "   xaxis nticks 5 ftick -2*pi shift 0.1 symticks\n"
        "   ynoticks 1 2\n"
        "   xside lwidth 0.05 color rgb255(140,140,140)\n",
    )
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert ax.passthrough == []
    assert (ax.title_font, ax.ylabel_font) == ("texcmb", "psh")
    assert (ax.xnticks, ax.xshift, ax.xsymticks) == (5, 0.1, True)
    assert ax.xftick == pytest.approx(-6.283185307179586)
    assert ax.ynoticks == [1.0, 2.0]
    assert ax.xside_color == "rgb255(140,140,140)"
    assert ax.xside_lwidth == pytest.approx(1.417, rel=1e-3)


@pytest.mark.parametrize(
    "body,kept",
    [
        # Options the model does not have keep the whole line.
        ("   xside off\n", "xside off"),
        ("   yside color RED lstyle 2\n", "yside color RED lstyle 2"),
        ("   xlabels font psh\n", "xlabels font psh"),
        ("   xnoticks a\n", "xnoticks a"),
        # symticks on|off and a fractional nticks are not the bare form.
        ("   xaxis symticks off\n", "xaxis symticks off"),
        ("   yaxis nticks 2.5\n", "yaxis nticks 2.5"),
        ("   xaxis shift auto\n", "xaxis shift auto"),
        # Tick placement is modelled on x and y only.
        ("   y2axis nticks 4\n", "y2axis nticks 4"),
    ],
)
def test_unmodelled_axis_line_and_tick_forms_stay_raw(tmp_path, body, kept):
    recognized = parse_gle_figure(_write(tmp_path, "raw.gle", body))
    ax = recognized.figure.axes_list[0]
    assert any(kept in line for line in ax.passthrough), ax.passthrough
    assert ax.xside_color is ax.yside_color is None
    assert ax.xnticks is ax.ynticks is ax.xsymticks is None


def test_a_second_noticks_line_stays_raw_after_the_first(tmp_path):
    """GLE replaces the list on each line, so the later one must still come
    last when the block is written again."""
    path = _write(tmp_path, "two.gle", "   xnoticks 1\n   xnoticks 2\n")
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.xnoticks == [1.0]
    assert any("xnoticks 2" in line for line in ax.passthrough)


def test_an_xside_after_its_x2side_stays_raw(tmp_path):
    """GLE copies ``xside`` onto the top line. The writer puts ``xside``
    first, so a later one is kept raw to keep overriding ``x2side``."""
    path = _write(tmp_path, "order.gle", "   x2side color RED\n   xside color BLUE\n")
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.x2side_color == "RED"
    assert ax.xside_color is None
    assert any("xside color BLUE" in line for line in ax.passthrough)


def test_hand_written_hidden_axis_lines_are_recovered(tmp_path):
    body = "   xside color GRAY off\n   x2side on\n   y2axis off\n"
    ax = parse_gle_figure(_write(tmp_path, "hidden.gle", body)).figure.axes_list[0]
    assert ax.xside_off is True and ax.xside_color == "GRAY"
    assert ax._y2axis_off is True
    assert ax.yside_off is None and ax._x2axis_off is False
    assert ax.passthrough == []


def test_an_on_that_is_an_axis_option_does_not_keep_x2axis_off_raw(tmp_path):
    body = "   xaxis symticks on\n   x2axis off\n"
    ax = parse_gle_figure(_write(tmp_path, "sym.gle", body)).figure.axes_list[0]
    assert ax._x2axis_off is True
    assert [line.strip() for line in ax.passthrough] == ["xaxis symticks on"]


@pytest.mark.parametrize(
    "body,raw",
    [
        # Without the top line switched back on, 'xside off' hides it too.
        ("   xside off\n   x2side color RED\n", ["xside off"]),
        ("   x2side on\n   xside off\n", ["x2side on", "xside off"]),
        # The demoted 'off' keeps its place ahead of the raw lines after it.
        ("   xside off\n   xside on\n", ["xside off", "xside on"]),
        ("   xside off\n   x2side lstyle 2 on\n", ["xside off", "x2side lstyle 2 on"]),
        # An 'on' that may switch the top or right axis back on.
        ("   x2axis off\n   x2labels on\n", ["x2axis off", "x2labels on"]),
        ("   yaxis on\n   y2axis off\n", ["yaxis on", "y2axis off"]),
    ],
)
def test_hidden_axis_lines_the_model_cannot_say_stay_raw(tmp_path, body, raw):
    ax = parse_gle_figure(_write(tmp_path, "hidden2.gle", body)).figure.axes_list[0]
    assert [line.strip() for line in ax.passthrough] == raw
    assert ax.xside_off is None
    assert ax._x2axis_off is ax._y2axis_off is False


@pytest.mark.parametrize(
    "body,raw",
    [
        # The first occurrence is raw GLE, written at the end of the block,
        # so a modeled second one would be written before it and lose.
        ("   xaxis symticks off\n   xaxis symticks\n", "xaxis symticks"),
        ("   yaxis nticks 2.5\n   yaxis nticks 4\n", "yaxis nticks 4"),
        # 'xaxis lwidth' / 'color' also set the line, on x and on x2.
        ("   xaxis lwidth 0.1\n   xside lwidth 0.05\n", "xside lwidth 0.05"),
        ("   xaxis color BLUE\n   x2side color RED\n", "x2side color RED"),
    ],
)
def test_a_later_option_after_a_raw_one_stays_raw_in_order(tmp_path, body, raw):
    ax = parse_gle_figure(_write(tmp_path, "order2.gle", body)).figure.axes_list[0]
    assert ax.passthrough[-1].strip() == raw, ax.passthrough
    assert ax.xsymticks is ax.ynticks is ax.xside_lwidth is ax.x2side_color is None


def _write_math(tmp_path: Path, head: str, tail: str = "") -> Path:
    """A single-graph .gle with ``head`` first in the block, ``tail`` last."""
    (tmp_path / "d.dat").write_text("0 0\n1 1\n2 4\n")
    path = tmp_path / "math.gle"
    path.write_text(
        "size 20.32 15.24\n"
        "begin graph\n"
        f"{head}"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        f"{tail}"
        "end graph\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "head",
    [
        "   math\n",
        "   size 10 8\n   scale 1 1\n   math\n",
        "   ! axes through the origin\n   MATH\n",
    ],
)
def test_math_ahead_of_everything_but_geometry_is_recovered(tmp_path, head):
    recognized = parse_gle_figure(_write_math(tmp_path, head))
    ax = recognized.figure.axes_list[0]
    assert ax.math_mode is True
    assert not any("math" in line.lower() for line in ax.passthrough)


@pytest.mark.parametrize(
    "head,tail",
    [
        # 'math' turns x2 off and resets offsets and symticks set before it,
        # so writing it first would change the plot.
        ('   title "T"\n   math\n', ""),
        ("", "   math\n"),
    ],
)
def test_math_after_other_statements_stays_raw(tmp_path, head, tail):
    ax = parse_gle_figure(_write_math(tmp_path, head, tail)).figure.axes_list[0]
    assert ax.math_mode is None
    assert any(line.strip().startswith("math") for line in ax.passthrough)


# -- tick marks, minor ticks and log labels (issue #73) ----------------------


def test_hand_written_tick_marks_are_recovered(tmp_path):
    path = _write(
        tmp_path,
        "marks.gle",
        "   xaxis nsubticks 3\n"
        "   xticks length -0.2 lwidth 0.03528 color RED\n"
        "   ysubticks off length 0.05\n"
        "   ylabels hei 0.3\n"
        "   ylabels log l25\n",
    )
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.passthrough == []
    assert ax.xnsubticks == 3
    assert ax.xtick_length == pytest.approx(0.2 / 0.03528)
    assert ax.xtick_direction == "out"
    assert ax.xtick_width == pytest.approx(1.0)
    assert ax.xtick_color == "RED"
    assert ax.yminorticks is False
    assert ax.ysubtick_length == pytest.approx(0.05 / 0.03528)
    assert ax.yloglabels == "l25"
    assert ax.yticklabel_size is not None  # the later line keeps 'hei'


def test_tick_marks_round_trip_byte_identically(tmp_path):
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    ax.plot([1, 10, 100], [1, 2, 3])
    ax.set_yscale("log")
    ax.tick_params(direction="out", length=4, width=0.7, color="blue")
    ax.tick_params(axis="y", which="minor", length=1.5)
    ax.tick_params(axis="x", which="minor", direction="in")
    ax.minorticks_on()
    ax.set_xticks(nsubticks=2, nofirst=True)
    ax.set_yticks(loglabels="n1", nolast=True)
    text1, text2, recognized = _round_trip(fig, tmp_path)
    assert text1 == text2
    restored = recognized.figure.axes_list[0]
    assert restored.passthrough == []
    assert restored.yloglabels == "n1" and restored.xnsubticks == 2
    assert restored.xtick_length == pytest.approx(4.0, rel=1e-4)
    assert restored._remove_first_xtick and restored._remove_last_ytick


@pytest.mark.parametrize(
    "body,kept",
    [
        ("   xticks off\n", "xticks off"),
        ("   xsubticks lstyle 2\n", "xsubticks lstyle 2"),
        ("   xaxis nsubticks 2.5\n", "xaxis nsubticks 2.5"),
        ("   xlabels log l3\n", "xlabels log l3"),
        ("   y2labels log l25\n", "y2labels log l25"),
    ],
)
def test_unmodelled_tick_mark_forms_stay_raw(tmp_path, body, kept):
    ax = parse_gle_figure(_write(tmp_path, "raw.gle", body)).figure.axes_list[0]
    assert any(kept in line for line in ax.passthrough), ax.passthrough
    assert ax.xtick_length is ax.xsubtick_length is ax.xnsubticks is None
    assert ax.xloglabels is None


@pytest.mark.parametrize(
    "body,raw",
    [
        ("   xticks length 0.1\n   xticks length 0.3\n", "xticks length 0.3"),
        ("   xlabels font psh log l1\n   xlabels log l25\n", "xlabels log l25"),
    ],
)
def test_a_later_tick_line_after_a_raw_one_stays_raw_in_order(tmp_path, body, raw):
    ax = parse_gle_figure(_write(tmp_path, "order3.gle", body)).figure.axes_list[0]
    assert ax.passthrough[-1].strip() == raw, ax.passthrough
    assert ax.xtick_length is ax.xloglabels is None


def test_hand_written_tick_intervals_are_recovered(tmp_path):
    """#155: ``dticks``/``dsubticks`` on x and y land on the model."""
    path = _write(
        tmp_path,
        "intervals.gle",
        "   xaxis dticks 0.5 dsubticks 0.25\n   yaxis min 0 dticks 2 dsubticks 1\n",
    )
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.passthrough == []
    assert (ax.xdticks, ax.xdsubticks) == (0.5, 0.25)
    assert (ax.ydticks, ax.ydsubticks) == (2.0, 1.0)


@pytest.mark.parametrize(
    "body,raw",
    [
        # An expression would be rounded by writing it back as a number.
        ("   xaxis dticks pi/2\n", "xaxis dticks pi/2"),
        ("   xaxis dsubticks pi\n", "xaxis dsubticks pi"),
        ("   xaxis dticks 0.1234567\n", "xaxis dticks 0.1234567"),
        ("   xaxis dticks 1e-11\n", "xaxis dticks 1e-11"),
        # Not an interval GLE can draw.
        ("   xaxis dticks 0\n", "xaxis dticks 0"),
        ("   xaxis dticks -1\n", "xaxis dticks -1"),
        # Tick intervals are modelled on x and y only.
        ("   y2axis dticks 1\n", "y2axis dticks 1"),
        # A repeat overrides the first, so it stays raw at the end.
        ("   xaxis dticks 1\n   xaxis dticks 2\n", "xaxis dticks 2"),
        ("   xaxis dsubticks 0.5\n   xaxis dsubticks 1\n", "xaxis dsubticks 1"),
    ],
)
def test_tick_interval_forms_the_model_cannot_hold_stay_raw(tmp_path, body, raw):
    ax = parse_gle_figure(_write(tmp_path, "raw.gle", body)).figure.axes_list[0]
    assert ax.passthrough[-1].strip() == raw, ax.passthrough
    if body.count("\n") == 1:
        assert ax.xdticks is ax.xdsubticks is None


def test_a_symmetric_tick_length_comes_back_as_the_whole_tick(tmp_path):
    path = _write(tmp_path, "sym.gle", "   xaxis symticks\n   xticks length 0.1\n")
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.passthrough == []
    assert ax.xsymticks is True
    assert ax.xtick_length == pytest.approx(0.2 / 0.03528)

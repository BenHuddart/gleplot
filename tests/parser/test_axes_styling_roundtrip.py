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
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2 10", axis="y2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14.0, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10.0, "BLUE", 0.35
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7.0, "GREEN", 45.0
    ax.y2ticklabel_size = 6.0
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


def test_an_axis_title_with_an_unmodelled_option_stays_whole(tmp_path):
    """``adist``/``font`` have no model field, and an axis title is a single
    command -- re-emitting it shorn of them would silently drop them."""
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

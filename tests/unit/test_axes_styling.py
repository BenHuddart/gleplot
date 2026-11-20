"""Axes styling: tick-label formats, grids, label/title styling, graph title.

The properties GLEstudio's SPEC 7.3 "Axes" bullet lists that gleplot 2.3.0
did not model at all (plan task G10). Everything here is *additive*: each
field defaults to None = "absent", and the writer emits nothing for it, so
the fixed-point battery's goldens are untouched (asserted directly by
``test_an_unstyled_figure_emits_no_styling_clause`` below and, across the
whole battery, by ``tests/parser/test_fixed_point.py``).

The GLE spellings asserted here come from the GLE 4.3.10 manual's graph
chapter (``title``/``xtitle``/``xlabels``/``xticks``/``xsubticks`` and the
``xaxis`` sub-commands ``format``, ``angle``, ``grid``) and were compiled
against the real binary in ``tests/integration/test_axes_styling_compiles.py``.
"""

import json
import re
import warnings

import numpy as np
import pytest

import gleplot as glp
from gleplot.axes import validate_tick_format
from gleplot.parser.units import fontsize_pt_to_cm, linewidth_pt_to_cm


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _fig(**kwargs):
    fig = glp.figure(data_prefix="style", **kwargs)
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9])
    return fig, ax


def _graph_lines(fig):
    """The statements inside the single graph block, stripped."""
    text = fig._generate_gle()
    body = text.split("begin graph", 1)[1].split("end graph", 1)[0]
    return [line.strip() for line in body.splitlines() if line.strip()]


def _line_starting(fig, prefix):
    matches = [line for line in _graph_lines(fig) if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {prefix!r} line, got {matches}"
    return matches[0]


# -- absence -----------------------------------------------------------------


def test_an_unstyled_figure_emits_no_styling_clause():
    fig, _ = _fig()
    # The preamble's 'set hei' is the figure font size, not axes styling, so
    # the check is on the graph block itself.
    body = "\n".join(_graph_lines(fig))
    for token in ("format", "angle", "grid", "hei", "dist", "xticks", "xlabels"):
        assert token not in body, f"unstyled figure emitted {token!r}"


# -- tick-label number format ------------------------------------------------


def test_tick_format_is_emitted_on_the_axis_line():
    fig, ax = _fig()
    ax.set_tick_format("fix 1", axis="x")
    assert 'xaxis min 1 max 3 format "fix 1"' == _line_starting(fig, "xaxis")


def test_tick_format_both_sets_x_and_y_but_not_y2():
    fig, ax = _fig()
    ax.set_tick_format("sci 2 10")
    assert ax.xformat == "sci 2 10"
    assert ax.yformat == "sci 2 10"
    assert ax.y2format is None


def test_y2_tick_format_turns_the_y2_labels_on():
    """GLE draws no y2 tick labels without ``y2labels on``, so a y2 format
    would otherwise be silently inert."""
    fig, ax = _fig()
    ax.set_tick_format("eng 2", axis="y2")
    lines = _graph_lines(fig)
    assert 'y2axis format "eng 2"' in lines
    assert "y2labels on" in lines
    assert lines.index("y2labels on") > lines.index('y2axis format "eng 2"')


def test_y2_limits_alone_turn_the_y2_labels_on():
    """Regression test: a y2 axis configured with limits but no styling and
    no plotted series used to compile with mirrored tick marks and no
    numbers -- GLE only auto-enables y2 labels for an axis a plotted
    dataset uses (see ``GLEWriter.add_axes``'s note on
    ``do_each_dataset_settings``), and nothing here plots on y2. Verified
    against the real binary in
    ``tests/integration/test_axes_styling_compiles.py::
    test_a_configured_y2_axis_labels_the_right_axis_even_unstyled``.
    """
    fig, ax = _fig()
    ax.set_ylim(0, 10, axis="y2")
    lines = _graph_lines(fig)
    assert "y2axis min 0 max 10" in lines
    assert "y2labels on" in lines


def test_y2_log_scale_alone_turns_the_y2_labels_on():
    fig, ax = _fig()
    ax.set_ylim(1, 100, axis="y2")
    ax.set_yscale("log", axis="y2")
    lines = _graph_lines(fig)
    assert "y2labels on" in lines


def test_y2_title_alone_turns_the_y2_labels_on():
    fig, ax = _fig()
    ax.set_ylabel("Right", axis="y2")
    lines = _graph_lines(fig)
    assert 'y2title "Right"' in lines
    assert "y2labels on" in lines


def test_no_y2_usage_emits_no_y2labels_line():
    fig, _ = _fig()
    assert "y2labels" not in fig._generate_gle()


def test_tick_format_is_cleared_by_none():
    fig, ax = _fig()
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format(None, axis="x")
    assert ax.xformat is None
    assert "format" not in fig._generate_gle()


@pytest.mark.parametrize(
    "fmt", ["fix 1", "sci 2 10 expdigits 2", "pi", "eng 2 num", "append °"]
)
def test_validate_accepts_real_gle_formats(fmt):
    assert validate_tick_format(fmt) == fmt


@pytest.mark.parametrize("fmt", ["", "   ", "wobble 2", "fix 1\nsci 2", 7])
def test_validate_rejects_what_could_not_be_a_format(fmt):
    with pytest.raises(ValueError):
        validate_tick_format(fmt)


def test_set_tick_format_rejects_an_unknown_axis():
    _, ax = _fig()
    with pytest.raises(ValueError, match="must be 'both', 'x', 'y', 'y2' or 'x2'"):
        ax.set_tick_format("fix 1", axis="z")


# -- grids -------------------------------------------------------------------


def test_grid_on_both_axes_is_a_grid_clause_per_axis():
    fig, ax = _fig()
    ax.grid(True)
    assert ax.xgrid == "major" and ax.ygrid == "major"
    assert _line_starting(fig, "xaxis").endswith(" grid")
    assert _line_starting(fig, "yaxis").endswith(" grid")


def test_grid_on_one_axis_only():
    fig, ax = _fig()
    ax.grid(True, axis="y")
    assert ax.xgrid is None
    assert "grid" not in _line_starting(fig, "xaxis")
    assert _line_starting(fig, "yaxis").endswith(" grid")


def test_grid_which_both_adds_the_subtick_grid_mode():
    fig, ax = _fig()
    ax.grid(True, which="both", axis="x")
    assert ax.xgrid == "both"
    assert "xsubticks on" in _graph_lines(fig)


def test_grid_which_minor_normalizes_to_both_with_a_warning():
    _, ax = _fig()
    with pytest.warns(UserWarning, match="minor-only grid is not expressible"):
        ax.grid(True, which="minor", axis="x")
    assert ax.xgrid == "both"


def test_grid_style_is_emitted_as_tick_style():
    fig, ax = _fig()
    ax.grid(True, axis="x", linestyle="--", linewidth=0.4, color="gray40")
    lines = _graph_lines(fig)
    width = f"{linewidth_pt_to_cm(0.4):.6g}"
    assert f"xticks lstyle 3 lwidth {width} color GRAY40" in lines
    assert lines.index(f"xticks lstyle 3 lwidth {width} color GRAY40") > lines.index(
        _line_starting(fig, "xaxis")
    )


def test_grid_style_repeats_lstyle_and_lwidth_on_the_subticks():
    """Subticks inherit the tick colour but not lstyle/lwidth (measured with
    GLE 4.3.10), so the subtick grid needs them again to match."""
    fig, ax = _fig()
    ax.grid(True, which="both", axis="y", linestyle=":", linewidth=0.5, color="red")
    width = f"{linewidth_pt_to_cm(0.5):.6g}"
    lines = _graph_lines(fig)
    assert f"yticks lstyle 2 lwidth {width} color RED" in lines
    assert f"ysubticks on lstyle 2 lwidth {width}" in lines


def test_grid_style_without_a_grid_is_not_emitted():
    """``xticks color ...`` on a gridless axis would restyle the ticks, which
    is not what the model says; the style waits for the grid."""
    fig, ax = _fig()
    ax.grid(True, axis="x", color="red")
    ax.grid(False, axis="x")
    assert ax.xgrid is None
    assert ax.xgrid_color == "RED"
    assert "xticks" not in fig._generate_gle()


def test_grid_with_no_arguments_toggles():
    _, ax = _fig()
    ax.grid()
    assert ax.xgrid == "major"
    ax.grid()
    assert ax.xgrid is None


def test_grid_style_arguments_imply_visible():
    _, ax = _fig()
    ax.grid(color="red")
    assert ax.xgrid == "major"


def test_enabling_the_major_layer_keeps_an_existing_subtick_grid():
    _, ax = _fig()
    ax.grid(True, which="both")
    ax.grid(True, which="major")
    assert ax.xgrid == "both"


def test_grid_false_which_minor_drops_back_to_the_main_grid():
    _, ax = _fig()
    ax.grid(True, which="both")
    with pytest.warns(UserWarning):
        ax.grid(False, which="minor")
    assert ax.xgrid == "major"


def test_grid_accepts_a_raw_gle_lstyle_number():
    _, ax = _fig()
    ax.grid(True, linestyle=7)
    assert ax.xgrid_lstyle == 7


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"which": "some"}, "must be 'major', 'minor' or 'both'"),
        ({"axis": "y2"}, "must be 'both', 'x' or 'y'"),
        ({"linestyle": "wiggly"}, "is not a matplotlib line style"),
        ({"linewidth": 0}, "must be positive"),
    ],
)
def test_grid_rejects_nonsense(kwargs, match):
    _, ax = _fig()
    with pytest.raises(ValueError, match=match):
        ax.grid(True, **kwargs)


def test_grid_takes_matplotlibs_line_aliases_and_warns_on_other_keywords():
    _, ax = _fig()
    with pytest.warns(
        UserWarning, match=r"grid\(\) ignores unsupported keyword\(s\): alpha"
    ):
        ax.grid(True, c="red", ls="--", lw=2, alpha=0.5)
    _, styled = _fig()
    styled.grid(True, color="red", linestyle="--", linewidth=2)
    assert (ax.xgrid_color, ax.xgrid_lstyle, ax.xgrid_lwidth) == (
        styled.xgrid_color,
        styled.xgrid_lstyle,
        styled.xgrid_lwidth,
    )


def test_grid_linestyle_follows_a_custom_style_config():
    fig = glp.figure(data_prefix="s", style=glp.GLEStyleConfig(line_style_dashed=9))
    ax = fig.add_subplot(111)
    ax.grid(True, linestyle="--")
    assert ax.xgrid_lstyle == 9


def test_show_grid_config_is_the_figure_wide_default():
    fig = glp.figure(data_prefix="s", graph=glp.GLEGraphConfig(show_grid=True))
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    assert ax.xgrid == "major" and ax.ygrid == "major"
    assert _line_starting(fig, "xaxis").endswith(" grid")


def test_show_grid_config_is_overridable_per_axes():
    fig = glp.figure(data_prefix="s", graph=glp.GLEGraphConfig(show_grid=True))
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.grid(False)
    assert "grid" not in fig._generate_gle()


# -- axis title and tick-label styling ---------------------------------------


def test_axis_title_styling_is_emitted_on_the_xtitle_line():
    fig, ax = _fig()
    ax.set_xlabel("Time")
    ax.xlabel_size = 10
    ax.xlabel_color = "BLUE"
    ax.xlabel_dist = 0.35
    hei = f"{fontsize_pt_to_cm(10):.6g}"
    assert (
        _line_starting(fig, "xtitle") == f'xtitle "Time" hei {hei} color BLUE dist 0.35'
    )


def test_y_and_y2_title_styling():
    fig, ax = _fig()
    ax.set_ylabel("L")
    ax.set_ylabel("R", axis="y2")
    ax.ylabel_color = "RED"
    ax.y2label_size = 8
    hei = f"{fontsize_pt_to_cm(8):.6g}"
    assert _line_starting(fig, "ytitle") == 'ytitle "L" color RED'
    assert _line_starting(fig, "y2title") == f'y2title "R" hei {hei}'


def test_tick_label_styling_is_its_own_labels_line():
    fig, ax = _fig()
    ax.xticklabel_size = 7
    ax.xticklabel_color = "GREEN"
    hei = f"{fontsize_pt_to_cm(7):.6g}"
    assert _line_starting(fig, "xlabels") == f"xlabels hei {hei} color GREEN"


def test_tick_label_angle_is_an_axis_option_not_a_labels_one():
    fig, ax = _fig()
    ax.yticklabel_angle = 30
    assert _line_starting(fig, "yaxis").endswith(" angle 30")
    assert "ylabels" not in fig._generate_gle()


def test_tick_label_styling_is_skipped_when_the_labels_are_off():
    fig, ax = _fig()
    ax.xticklabel_size = 7
    ax._show_xticks = False
    assert _line_starting(fig, "xlabels") == "xlabels off"


def test_y2_tick_label_styling_turns_the_labels_on():
    fig, ax = _fig()
    ax.y2ticklabel_size = 7
    ax.y2ticklabel_color = "BLUE"
    hei = f"{fontsize_pt_to_cm(7):.6g}"
    assert _line_starting(fig, "y2labels") == f"y2labels on hei {hei} color BLUE"


def test_x2_title_and_tick_label_styling():
    fig, ax = _fig()
    ax.set_xlabel("Top", axis="x2")
    ax.x2label_size = 8
    ax.x2ticklabel_size = 7
    ax.x2ticklabel_color = "BLUE"
    title_hei = f"{fontsize_pt_to_cm(8):.6g}"
    label_hei = f"{fontsize_pt_to_cm(7):.6g}"
    assert _line_starting(fig, "x2title") == f'x2title "Top" hei {title_hei}'
    assert _line_starting(fig, "x2labels") == f"x2labels on hei {label_hei} color BLUE"


# -- graph title -------------------------------------------------------------


def test_graph_title_styling():
    fig, ax = _fig()
    ax.set_title("Result")
    ax.title_size = 14
    ax.title_color = "RED"
    ax.title_dist = 0.3
    hei = f"{fontsize_pt_to_cm(14):.6g}"
    assert (
        _line_starting(fig, "title") == f'title "Result" hei {hei} color RED dist 0.3'
    )


def test_title_is_per_axes_so_each_subplot_carries_its_own():
    fig = glp.figure(data_prefix="style")
    top = fig.add_subplot(211)
    bottom = fig.add_subplot(212)
    for ax in (top, bottom):
        ax.plot([1, 2], [1, 2])
    top.set_title("A")
    top.title_color = "RED"
    bottom.set_title("B")
    text = fig._generate_gle()
    assert 'title "A" color RED' in text
    assert 'title "B"\n' in text


# -- title fonts -------------------------------------------------------------


def test_title_fonts_are_emitted_on_the_title_lines():
    fig, ax = _fig()
    ax.set_title("T", fontname="texcmb")
    ax.set_xlabel("X", fontname="texcmr")
    ax.set_ylabel("Y2", axis="y2", fontname="psh")
    assert _line_starting(fig, "title ") == 'title "T" font texcmb'
    assert _line_starting(fig, "xtitle") == 'xtitle "X" font texcmr'
    assert _line_starting(fig, "y2title") == 'y2title "Y2" font psh'


def test_a_title_font_sits_between_color_and_dist():
    fig, ax = _fig()
    ax.set_xlabel("X", fontname="texcmr")
    ax.xlabel_color, ax.xlabel_dist = "RED", 0.4
    assert _line_starting(fig, "xtitle") == 'xtitle "X" color RED font texcmr dist 0.4'


def test_the_twiny_view_passes_fontname_through():
    fig, ax = _fig()
    top = ax.twiny()
    top.set_xlabel("W", fontname="texcmr")
    top.set_ylabel("Y", fontname="psh")
    assert _line_starting(fig, "x2title") == 'x2title "W" font texcmr'
    assert _line_starting(fig, "ytitle") == 'ytitle "Y" font psh'


def test_relabelling_without_fontname_keeps_the_font():
    fig, ax = _fig()
    ax.set_xlabel("X", fontname="texcmr")
    ax.set_xlabel("New")
    assert _line_starting(fig, "xtitle") == 'xtitle "New" font texcmr'


@pytest.mark.parametrize(
    "fontname,error", [("", ValueError), ("two words", ValueError), (3, TypeError)]
)
def test_a_bad_fontname_is_rejected_at_the_call(fontname, error):
    _, ax = _fig()
    with pytest.raises(error, match="fontname"):
        ax.set_title("T", fontname=fontname)


# -- matplotlib text keywords on the titles ----------------------------------


def test_label_keywords_are_emitted_on_the_xtitle_line():
    fig, ax = _fig()
    ax.set_xlabel("T (K)", fontsize=9, color="gray", labelpad=4)
    hei = f"{fontsize_pt_to_cm(9):.6g}"
    dist = f"{fontsize_pt_to_cm(4):.6g}"
    assert (
        _line_starting(fig, "xtitle")
        == f'xtitle "T (K)" hei {hei} color GRAY dist {dist}'
    )


def test_title_keywords_are_emitted_on_the_title_line():
    fig, ax = _fig()
    ax.set_title("Run 12", fontsize=11, color="red", pad=6)
    hei = f"{fontsize_pt_to_cm(11):.6g}"
    dist = f"{fontsize_pt_to_cm(6):.6g}"
    assert (
        _line_starting(fig, "title ")
        == f'title "Run 12" hei {hei} color RED dist {dist}'
    )


def test_a_relative_fontsize_scales_the_style_fontsize():
    fig, ax = _fig()
    ax.set_ylabel("Y", fontsize="small")
    hei = f"{fontsize_pt_to_cm(fig.style.fontsize * 0.833):.6g}"
    assert _line_starting(fig, "ytitle") == f'ytitle "Y" hei {hei}'


def test_the_twin_views_pass_the_label_keywords_through():
    fig, ax = _fig()
    ax.twinx().set_ylabel("R", color="blue")
    ax.twiny().set_xlabel("W", fontsize=8)
    hei = f"{fontsize_pt_to_cm(8):.6g}"
    assert _line_starting(fig, "y2title") == 'y2title "R" color BLUE'
    assert _line_starting(fig, "x2title") == f'x2title "W" hei {hei}'


@pytest.mark.parametrize("via", ["module", "figure"])
def test_the_wrappers_pass_the_label_keywords_through(via):
    fig, ax = _fig()
    target = glp if via == "module" else fig
    target.xlabel("X", fontsize=9, labelpad=4)
    target.ylabel("Y", color="red")
    target.title("T", fontsize=11, pad=6)
    hei9, hei11 = f"{fontsize_pt_to_cm(9):.6g}", f"{fontsize_pt_to_cm(11):.6g}"
    dist4, dist6 = f"{fontsize_pt_to_cm(4):.6g}", f"{fontsize_pt_to_cm(6):.6g}"
    assert _line_starting(fig, "xtitle") == f'xtitle "X" hei {hei9} dist {dist4}'
    assert _line_starting(fig, "ytitle") == 'ytitle "Y" color RED'
    assert _line_starting(fig, "title ") == f'title "T" hei {hei11} dist {dist6}'


def test_the_module_wrappers_take_matplotlibs_positional_order():
    fig, ax = _fig()
    with pytest.warns(
        UserWarning, match=r"set_xlabel\(\) ignores unsupported keyword\(s\): fontdict"
    ):
        glp.xlabel("X", {"fontsize": 9}, 4)
    with pytest.warns(UserWarning, match=r"set_title\(loc='left'\) is drawn"):
        glp.title("T", None, "left", 6)
    with pytest.warns(
        UserWarning, match=r"set_ylabel\(\) ignores unsupported keyword\(s\): fontdict"
    ):
        glp.ylabel("Y", {"fontsize": 9}, 2)
    with pytest.warns(
        UserWarning, match=r"set_title\(\) ignores unsupported keyword\(s\): y"
    ):
        glp.title("T", y=1.1)
    dist4, dist6 = f"{fontsize_pt_to_cm(4):.6g}", f"{fontsize_pt_to_cm(6):.6g}"
    assert _line_starting(fig, "xtitle") == f'xtitle "X" dist {dist4}'
    assert _line_starting(fig, "title ") == f'title "T" dist {dist6}'
    dist2 = f"{fontsize_pt_to_cm(2):.6g}"
    assert _line_starting(fig, "ytitle") == f'ytitle "Y" dist {dist2}'


def test_relabelling_keeps_the_style_and_none_resets_it():
    fig, ax = _fig()
    ax.set_xlabel("X", fontsize=9, color="red", labelpad=2)
    ax.set_xlabel("New", fontsize=None)
    dist = f"{fontsize_pt_to_cm(2):.6g}"
    assert _line_starting(fig, "xtitle") == f'xtitle "New" color RED dist {dist}'


def test_other_text_keywords_warn_and_centre_is_silent():
    fig, ax = _fig()
    with pytest.warns(
        UserWarning,
        match=r"set_title\(\) ignores unsupported keyword\(s\): fontdict, fontweight",
    ):
        ax.set_title("T", {"fontsize": 9}, fontweight="bold")
    with pytest.warns(UserWarning, match=r"set_ylabel\(loc='top'\) is drawn centred"):
        ax.set_ylabel("Y", loc="top")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ax.set_xlabel("X", loc="center")
        ax.set_title("T", loc="center")
    assert _line_starting(fig, "title ") == 'title "T"'


@pytest.mark.parametrize(
    "call,error,match",
    [
        (lambda ax: ax.set_xlabel("X", fontsize=-1), ValueError, "fontsize"),
        (lambda ax: ax.set_ylabel("Y", fontsize="huge"), ValueError, "fontsize"),
        (lambda ax: ax.set_xlabel("X", labelpad="far"), TypeError, "labelpad"),
        (lambda ax: ax.set_title("T", pad=float("nan")), ValueError, "pad"),
        (lambda ax: ax.set_title("T", fontsize=float("nan")), ValueError, "fontsize"),
        (lambda ax: ax.set_xlabel("X", fontsize=[9]), TypeError, "fontsize"),
        (lambda ax: ax.set_xlabel("X", loc="top"), ValueError, "left, center, right"),
        (lambda ax: ax.set_ylabel("Y", loc="left"), ValueError, "bottom, center, top"),
    ],
)
def test_a_bad_title_keyword_is_rejected_at_the_call(call, error, match):
    _, ax = _fig()
    with pytest.raises(error, match=match):
        call(ax)


# -- axis lines --------------------------------------------------------------


def test_axis_line_both_styles_x_and_y_with_one_side_line_each():
    fig, ax = _fig()
    ax.set_axis_line(color="gray", linewidth=1.5)  # 1.5 pt = 0.05292 cm
    assert _line_starting(fig, "xside") == "xside color GRAY lwidth 0.05292"
    assert _line_starting(fig, "yside") == "yside color GRAY lwidth 0.05292"
    assert not any(line.startswith(("x2side", "y2side")) for line in _graph_lines(fig))


def test_the_top_and_right_lines_come_after_the_ones_gle_copies_onto_them():
    fig, ax = _fig()
    ax.set_axis_line("x2", color="red")
    ax.set_axis_line("y2", color="blue")
    ax.set_axis_line(color="gray")
    lines = _graph_lines(fig)
    assert lines.index("xside color GRAY") < lines.index("x2side color RED")
    assert lines.index("yside color GRAY") < lines.index("y2side color BLUE")


def test_an_axis_line_does_not_turn_the_y2_labels_on():
    fig, ax = _fig()
    ax.set_axis_line("y2", linewidth=0.5)
    assert not any("y2labels" in line for line in _graph_lines(fig))


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"axis": "z"}, ValueError),
        ({"linewidth": -1}, ValueError),
        ({"linewidth": float("nan")}, ValueError),
        ({"linewidth": "thick"}, TypeError),
    ],
)
def test_set_axis_line_rejects_nonsense(kwargs, error):
    _, ax = _fig()
    with pytest.raises(error, match="set_axis_line"):
        ax.set_axis_line(**kwargs)


def test_hiding_the_bottom_line_keeps_the_top_one_drawn():
    fig, ax = _fig()
    assert ax.set_axis_line("x", color="gray", visible=False) is ax
    lines = _graph_lines(fig)
    assert "xside color GRAY off" in lines
    # GLE copies 'xside off' onto the top edge, so the top is switched back on.
    assert lines.index("xside color GRAY off") < lines.index("x2side on")
    assert not any(line.startswith(("yside", "y2side")) for line in lines)


def test_hiding_the_top_and_right_edges_switches_those_axes_off():
    fig, ax = _fig()
    ax.set_axis_line("x2", visible=False)
    ax.set_axis_line("y2", visible=False)
    lines = _graph_lines(fig)
    assert "x2axis off" in lines and "y2axis off" in lines
    assert not any("side" in line for line in lines)


def test_hiding_both_bottom_and_top_writes_no_switch_back():
    fig, ax = _fig()
    ax.set_axis_line(visible=False)
    ax.set_axis_line("x2", visible=False)
    lines = _graph_lines(fig)
    assert "xside off" in lines and "yside off" in lines
    assert "x2axis off" in lines and "y2side on" in lines
    assert "x2side on" not in lines


def test_visible_true_draws_a_hidden_line_again():
    fig, ax = _fig()
    plain = _graph_lines(fig)
    for side in ("both", "x2", "y2"):
        ax.set_axis_line(side, visible=False)
        ax.set_axis_line(side, visible=True)
    assert _graph_lines(fig) == plain


def test_set_axis_off_hides_every_line_once():
    fig, ax = _fig()
    ax.set_axis_line(visible=False)
    ax.set_axis_off()
    lines = _graph_lines(fig)
    assert lines.count("xside off") == lines.count("yside off") == 1
    assert not any(line.startswith(("x2side", "y2side")) for line in lines)


@pytest.mark.parametrize(
    "setup,side",
    [
        (lambda ax: ax.twinx().plot([1, 2], [3, 4]), "y2"),
        (lambda ax: ax.set_ylabel("R", axis="y2"), "y2"),
        (lambda ax: ax.set_tick_format("fix 1", axis="y2"), "y2"),
        (lambda ax: ax.set_xlim(0, 5, axis="x2"), "x2"),
        (lambda ax: ax.set_xscale("log", axis="x2"), "x2"),
    ],
)
@pytest.mark.parametrize("hide_first", [False, True])
def test_hiding_an_edge_that_carries_a_scale_warns(setup, side, hide_first):
    fig, ax = _fig()
    if hide_first:
        ax.set_axis_line(side, visible=False)
    setup(ax)
    ax.set_axis_line(side, visible=False)
    with pytest.warns(UserWarning, match=f"with it the {side} scale"):
        _graph_lines(fig)


def test_hiding_an_unused_edge_does_not_warn():
    fig, ax = _fig()
    ax.set_axis_line("x2", visible=False)
    ax.set_axis_line("y2", visible=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _graph_lines(fig)


def test_set_axis_line_rejects_a_non_bool_visible():
    _, ax = _fig()
    with pytest.raises(TypeError, match=r"set_axis_line\(visible='no'\)"):
        ax.set_axis_line("x", visible="no")


# -- tick placement ----------------------------------------------------------


def test_tick_placement_is_emitted_on_the_axis_line():
    fig, ax = _fig()
    ax.set_xticks(nticks=5, ftick=0.5, shift=0.2, symticks=True)
    assert _line_starting(fig, "xaxis") == (
        "xaxis min 1 max 3 nticks 5 ftick 0.5 shift 0.2 symticks"
    )


def test_noticks_is_its_own_statement_and_an_empty_list_clears_it():
    fig, ax = _fig()
    ax.set_yticks(noticks=[2, 4.5])
    assert _line_starting(fig, "ynoticks") == "ynoticks 2 4.5"
    ax.set_yticks(noticks=[])
    assert not any(line.startswith("ynoticks") for line in _graph_lines(fig))


def test_an_empty_tick_list_switches_the_ticks_and_labels_off():
    """GLE reads a bare ``xplaces`` as automatic ticks (#181)."""
    fig, ax = _fig()
    ax.set_xticks([])
    ax.set_yticks([], labels=[])
    ax.grid(True, color="red")
    ax.set_yticks(noticks=[2])
    lines = _graph_lines(fig)
    assert lines[lines.index("xaxis min 1 max 3 grid") :][:5] == [
        "xaxis min 1 max 3 grid",
        "xticks off",
        "xlabels off",
        "yaxis min 1 max 9 grid",
        "yticks off",
    ]
    assert not any("places" in line or "names" in line for line in lines)
    assert [line for line in lines if line.startswith(("xticks", "yticks"))] == [
        "xticks off",
        "yticks off",
    ]


def test_an_empty_tick_list_on_a_log_axis_keeps_the_minor_ticks():
    """matplotlib keeps a log axis' minor ticks (#378); minorticks_off wins."""
    fig, ax = _fig()
    ax.set_xscale("log")
    ax.set_xticks([])
    lines = _graph_lines(fig)
    assert lines[lines.index("xticks off") :][:3] == [
        "xticks off",
        "xsubticks on",
        "xlabels off",
    ]
    ax.minorticks_off()
    assert "xsubticks on" not in _graph_lines(fig)


def test_an_empty_tick_list_keeps_minor_ticks_asked_for_but_not_on_a_grid():
    fig, ax = _fig()
    ax.set_xticks([])
    ax.minorticks_on()
    assert "xsubticks on" in _graph_lines(fig)
    _, gridded = _fig()
    gridded.set_xscale("log")
    gridded.set_xticks([])
    gridded.grid(True)
    assert not any("subticks" in line for line in _graph_lines(gridded.figure))


def test_an_empty_tick_list_on_a_hidden_frame_adds_no_second_ticks_off():
    """``axis('off')`` writes ``xticks off`` already, and it must stay one of
    the four lines the parser recovers as a hidden frame."""
    fig, ax = _fig()
    ax.axis("off")
    ax.set_xticks([])
    ax.set_yticks([], labels=[])
    lines = _graph_lines(fig)
    assert lines.count("xticks off") == 1
    assert lines.count("xlabels off") == 1
    assert not any("names" in line for line in lines)


def test_an_empty_tick_list_leaves_a_twin_scale_its_ticks():
    """GLE copies ``yticks off``/``ylabels off`` onto y2; a twin is put back."""
    fig, ax = _fig()
    ax.twinx().plot([1, 2, 3], [5, 6, 7])
    ax.set_yticks([])
    ax.set_xticks([])
    lines = _graph_lines(fig)
    assert lines[lines.index("yticks off") :][:4] == [
        "yticks off",
        "ylabels off",
        "y2ticks on",
        "y2labels on",
    ]
    assert "x2ticks on" not in lines and "x2labels on" not in lines


def test_symticks_false_goes_back_to_the_default():
    fig, ax = _fig()
    ax.set_xticks(symticks=True)
    ax.set_xticks(symticks=False)
    assert "symticks" not in _line_starting(fig, "xaxis")


@pytest.mark.parametrize(
    "kwargs,error",
    [
        ({"nticks": 0}, ValueError),
        ({"nticks": 2.5}, ValueError),
        ({"nticks": True}, ValueError),
        ({"ftick": "start"}, TypeError),
        ({"shift": float("inf")}, ValueError),
        ({"noticks": [1, None]}, TypeError),
    ],
)
def test_set_xticks_rejects_bad_placement(kwargs, error):
    _, ax = _fig()
    with pytest.raises(error, match="set_xticks"):
        ax.set_xticks(**kwargs)


def _origin_fig():
    """An axes in math mode whose limits both include 0."""
    fig, ax = _fig()
    ax.set_xlim(-1, 4)
    ax.set_ylim(-1, 9)
    ax.set_math_mode()
    return fig, ax


def test_math_mode_is_written_straight_after_the_geometry():
    fig, ax = _origin_fig()
    ax.set_title("T")
    lines = _graph_lines(fig)
    assert lines[lines.index("scale 1 1") + 1 :][:2] == ["math", 'title "T"']


def test_math_mode_false_goes_back_to_a_framing_box():
    fig, ax = _origin_fig()
    assert ax.set_math_mode(False) is ax
    assert ax.math_mode is None
    assert "math" not in _graph_lines(fig)


def test_math_mode_is_written_in_every_subplot_that_asks_for_it():
    fig, (left, right) = glp.subplots(1, 2, data_prefix="style")
    left.plot([-1, 2], [-1, 2])
    right.plot([-1, 2], [-1, 2])
    right.set_math_mode()
    assert fig._generate_gle().count("    math\n") == 1


def test_math_mode_warns_on_a_log_axis():
    fig, ax = _origin_fig()
    ax.set_ylim(1, 9)
    ax.set_yscale("log")
    with pytest.warns(UserWarning, match="log y axis") as record:
        fig._generate_gle()
    assert len(record) == 1


def test_math_mode_warns_when_zero_is_outside_the_limits():
    fig, ax = _origin_fig()
    ax.set_ylim(1, 9)
    with pytest.warns(UserWarning, match=r"x axis at y = 0.*y limits \(1, 9\)"):
        fig._generate_gle()


def test_math_mode_through_the_origin_does_not_warn():
    fig, ax = _origin_fig()
    ax.set_xlim(3, -3)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig._generate_gle()


def test_y2_limits_after_math_mode_still_turn_the_right_axis_on():
    fig, ax = _origin_fig()
    ax.set_ylim(0, 20, axis="y2")
    lines = _graph_lines(fig)
    assert lines.index("math") < lines.index("y2labels on")


def test_set_math_mode_rejects_a_non_bool():
    _, ax = _fig()
    with pytest.raises(TypeError, match="set_math_mode"):
        ax.set_math_mode("yes")


# -- figure-wide distance defaults (the ex-dead GLEGraphConfig fields) -------


def test_config_distances_are_the_default_for_the_per_axes_ones():
    fig = glp.figure(
        data_prefix="style",
        graph=glp.GLEGraphConfig(
            title_distance=0.2, xlabel_distance=0.3, ylabel_distance=0.4
        ),
    )
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.set_title("T")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_ylabel("Y2", axis="y2")
    lines = _graph_lines(fig)
    assert 'title "T" dist 0.2' in lines
    assert 'xtitle "X" dist 0.3' in lines
    assert 'ytitle "Y" dist 0.4' in lines
    assert 'y2title "Y2" dist 0.4' in lines


def test_a_per_axes_distance_wins_over_the_config_default():
    fig = glp.figure(data_prefix="style", graph=glp.GLEGraphConfig(xlabel_distance=0.3))
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.set_xlabel("X")
    ax.xlabel_dist = 0.9
    assert _line_starting(fig, "xtitle") == 'xtitle "X" dist 0.9'


def test_distance_defaults_are_absent_so_nothing_changes():
    assert glp.GLEGraphConfig().title_distance is None
    assert glp.GLEGraphConfig().xlabel_distance is None
    assert glp.GLEGraphConfig().ylabel_distance is None


# -- the other ex-dead config fields -----------------------------------------


def test_default_color_config_drives_an_uncoloured_line():
    fig = glp.figure(data_prefix="style", style=glp.GLEStyleConfig(default_color="red"))
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    assert "d1 line color RED" in fig._generate_gle()


def test_default_marker_color_config_drives_an_uncoloured_scatter():
    fig = glp.figure(
        data_prefix="style",
        style=glp.GLEStyleConfig(default_color="red", default_marker_color="green"),
    )
    ax = fig.add_subplot(111)
    ax.scatter([1, 2], [1, 2])
    text = fig._generate_gle()
    assert "color GREEN" in text
    assert "color RED" not in text


def test_array_default_colors_compare_and_serialise(tmp_path):
    def style():
        return glp.GLEStyleConfig(
            default_color=np.array([0.0, 1.0, 0.0]),
            default_marker_color=np.array([[1.0, 0.0, 0.0]]),
        )

    assert style() == style()
    fig = glp.figure(data_prefix="style", style=style())
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.scatter([1, 2], [1, 2])
    restored = glp.Figure.from_dict(json.loads(json.dumps(fig.to_dict())))
    assert restored.style == fig.style
    out = tmp_path / "style.gle"
    fig.savefig(str(out))
    text = out.read_text()
    assert "d1 line color rgb255(0,255,0)" in text
    assert "marker FCIRCLE msize 0.134164 color rgb255(255,0,0)" in text


def test_default_colors_out_of_the_box_are_the_historical_blue():
    fig, _ = _fig()
    assert "color BLUE" in fig._generate_gle()


def test_legend_offset_config_is_the_figure_wide_default():
    fig = glp.figure(
        data_prefix="style",
        graph=glp.GLEGraphConfig(legend_offset_x=0.2, legend_offset_y=0.4),
    )
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2], label="a")
    ax.legend()
    assert "offset 0.2 0.4" in fig._generate_gle()


def test_a_per_axes_legend_offset_wins_over_the_config_default():
    fig = glp.figure(
        data_prefix="style",
        graph=glp.GLEGraphConfig(legend_offset_x=0.2, legend_offset_y=0.4),
    )
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2], label="a")
    ax.legend(offset=(0.0, 0.9))
    assert "offset 0 0.9" in fig._generate_gle()


def test_zero_legend_offset_default_emits_nothing():
    fig, ax = _fig()
    ax.plot([1, 2], [1, 2], label="a")
    ax.legend()
    assert "offset" not in fig._generate_gle()


# -- serialization -----------------------------------------------------------


def _styled_axes(ax):
    ax.set_title("T")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_ylabel("Y2", axis="y2")
    ax.set_xlabel("X2", axis="x2")
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2", axis="y")
    ax.set_tick_format("eng 2", axis="y2")
    ax.set_tick_format("fix 2", axis="x2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14.0, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10.0, "BLUE", 0.35
    ax.ylabel_size, ax.ylabel_color, ax.ylabel_dist = 9.0, "GREEN", 0.36
    ax.y2label_size, ax.y2label_color, ax.y2label_dist = 8.0, "PURPLE", 0.37
    ax.x2label_size, ax.x2label_color, ax.x2label_dist = 8.5, "BROWN", 0.38
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7.0, "ORANGE", 30.0
    ax.yticklabel_size, ax.yticklabel_color, ax.yticklabel_angle = 6.5, "CYAN", 15.0
    ax.y2ticklabel_size, ax.y2ticklabel_color, ax.y2ticklabel_angle = 6.0, "PINK", 45.0
    ax.x2ticklabel_size, ax.x2ticklabel_color, ax.x2ticklabel_angle = 5.5, "GRAY", 20.0
    ax.set_title("T", fontname="texcmb")
    ax.set_xlabel("X", fontname="texcmr")
    ax.set_ylabel("Y", fontname="texcmss")
    ax.set_ylabel("Y2", axis="y2", fontname="texcmtt")
    ax.set_xlabel("X2", axis="x2", fontname="texcmti")
    for axis, color, width in (
        ("x", "RED", 1.0),
        ("y", "BLUE", 1.5),
        ("y2", "GREEN", 0.5),
        ("x2", "PURPLE", 0.75),
    ):
        ax.set_axis_line(axis, color=color, linewidth=width)
    ax.set_xticks(nticks=4, ftick=1, shift=0.2, symticks=True, noticks=[2])
    ax.set_yticks(nticks=3, ftick=0, shift=0.1, symticks=True, noticks=[4, 9])
    ax.set_xlim(-1, 4)
    ax.set_ylim(-1, 9)
    ax.set_math_mode()
    return ax


def test_every_styling_field_survives_to_dict_from_dict():
    from gleplot.axes import _STYLING_KEYS

    fig, ax = _fig()
    _styled_axes(ax)
    # Tick marks are not written on a gridded axis, but they are still kept.
    ax.tick_params(which="both", length=3, width=0.5, color="red", direction="out")
    ax.minorticks_on()
    ax.set_xticks(nsubticks=3, loglabels="l1", symticks=True)
    ax.set_yticks(nsubticks=1, loglabels="n1", symticks=True)
    ax.set_axis_line(visible=False)
    before = {key: getattr(ax, key) for key in _STYLING_KEYS}
    assert all(value is not None for value in before.values()), before

    restored = glp.Figure.from_dict(fig.to_dict())
    after = {key: getattr(restored.axes_list[0], key) for key in _STYLING_KEYS}
    assert after == before


def test_a_styled_figure_regenerates_identically_after_from_dict(tmp_path):
    fig, ax = _fig()
    _styled_axes(ax)
    text = fig._generate_gle()
    assert glp.Figure.from_dict(fig.to_dict())._generate_gle() == text


def test_a_pre_g10_payload_loads_as_unstyled():
    from gleplot.axes import _STYLING_KEYS

    fig, ax = _fig()
    payload = fig.to_dict()
    for axes_payload in payload["figure"]["axes"]:
        for key in _STYLING_KEYS:
            del axes_payload[key]
    restored = glp.Figure.from_dict(payload)
    assert all(getattr(restored.axes_list[0], key) is None for key in _STYLING_KEYS)


def test_warnings_are_not_raised_by_ordinary_styling():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig, ax = _fig()
        _styled_axes(ax)
        fig._generate_gle()


# -- tick marks, minor ticks and edge labels (issue #73) ----------------------


def _cm(points):
    return f"{linewidth_pt_to_cm(points):.6g}"


def test_tick_params_writes_the_tick_marks():
    fig, ax = _fig()
    ax.tick_params(axis="x", length=4, width=0.8, direction="in", color="red")
    ax.tick_params(axis="y", which="minor", length=2)
    lines = _graph_lines(fig)
    assert f"xticks length {_cm(4)} lwidth {_cm(0.8)} color RED" in lines
    assert f"ysubticks length {_cm(2)}" in lines
    assert not any(line.startswith(("yticks", "xsubticks")) for line in lines)


def test_direction_out_is_a_negative_length():
    fig, ax = _fig()
    ax.tick_params(axis="x", direction="out")  # matplotlib's 3.5 pt default
    ax.tick_params(axis="y", direction="out", length=5)
    lines = _graph_lines(fig)
    assert f"xticks length -{_cm(3.5)}" in lines
    assert f"yticks length -{_cm(5)}" in lines
    # A later length keeps the direction; a later direction keeps the length.
    ax.tick_params(axis="y", length=6)
    assert f"yticks length -{_cm(6)}" in _graph_lines(fig)
    ax.tick_params(axis="y", direction="in")
    assert f"yticks length {_cm(6)}" in _graph_lines(fig)


def test_minor_ticks_follow_an_outward_major_tick_unless_told_otherwise():
    fig, ax = _fig()
    ax.tick_params(axis="x", direction="out", length=4)
    ax.tick_params(axis="x", which="minor", width=0.5)
    # GLE draws a minor tick with no length at half the major one, same sign.
    assert f"xsubticks lwidth {_cm(0.5)}" in _graph_lines(fig)
    ax.tick_params(axis="x", which="minor", direction="in")
    # matplotlib's 2 pt minor default, inward.
    assert f"xsubticks length {_cm(2)} lwidth {_cm(0.5)}" in _graph_lines(fig)


def test_inout_is_symticks_with_half_the_length_on_each_side():
    fig, ax = _fig()
    ax.tick_params(direction="inout", length=6)
    assert (ax.xsymticks, ax.ysymticks) == (True, True)
    lines = _graph_lines(fig)
    assert any(line.startswith("xaxis") and line.endswith("symticks") for line in lines)
    assert f"xticks length {_cm(3)}" in lines
    ax.tick_params(direction="out")
    assert ax.xsymticks is None
    assert f"xticks length -{_cm(6)}" in _graph_lines(fig)
    ax.tick_params(direction="in", length=4)
    ax.tick_params(direction="inout")
    assert f"xticks length {_cm(2)}" in _graph_lines(fig)


def test_inout_for_minor_ticks_only_warns_and_leaves_the_major_ticks():
    _, ax = _fig()
    ax.tick_params(direction="out", length=4)
    with pytest.warns(UserWarning, match="which='both'"):
        ax.tick_params(which="minor", direction="inout", length=2)
    assert ax.xsymticks is None
    assert (ax.xtick_direction, ax.xsubtick_length) == ("out", 2.0)


def test_a_minor_direction_leaves_the_major_ticks_symmetric():
    _, ax = _fig()
    ax.tick_params(direction="inout", length=6)
    ax.tick_params(which="minor", direction="out")
    assert ax.xsymticks is True


def test_reset_drops_the_earlier_tick_marks():
    _, ax = _fig()
    ax.tick_params(direction="inout", length=4, color="red")
    ax.tick_params(reset=True, width=1)
    assert (ax.xtick_length, ax.xtick_color, ax.xtick_width) == (None, None, 1.0)
    assert ax.xsymticks is None


def test_loglabels_on_a_linear_axis_warns():
    fig, ax = _fig()
    ax.set_xticks(loglabels="l25")
    with pytest.warns(UserWarning, match="x axis is linear"):
        lines = _graph_lines(fig)
    assert "xlabels log l25" in lines


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"axis": "z"}, "axis='z'"),
        ({"which": "all"}, "which='all'"),
        ({"direction": "up"}, "direction='up'"),
        ({"length": -1}, "length=-1"),
        ({"width": -0.5}, "width=-0.5"),
    ],
)
def test_tick_params_rejects_bad_values(kwargs, match):
    _, ax = _fig()
    with pytest.raises(ValueError, match=match):
        ax.tick_params(**kwargs)


def test_tick_params_warns_about_keywords_it_cannot_honour():
    _, ax = _fig()
    with pytest.warns(UserWarning, match="labelsize, pad"):
        ax.tick_params(pad=3, labelsize=8, length=2)
    assert ax.xtick_length == 2.0


def test_tick_marks_on_a_gridded_axis_warn_and_are_not_written():
    fig, ax = _fig()
    ax.grid(True, axis="x")
    ax.tick_params(length=4, color="red")
    ax.minorticks_off()
    with pytest.warns(UserWarning, match="x axis has a grid"):
        lines = _graph_lines(fig)
    assert not any(line.startswith(("xticks", "xsubticks")) for line in lines)
    assert f"yticks length {_cm(4)} color RED" in lines
    assert "ysubticks off" in lines


def test_minorticks_on_and_off():
    fig, ax = _fig()
    ax.minorticks_on()
    assert {"xsubticks on", "ysubticks on"} <= set(_graph_lines(fig))
    ax.minorticks_off()
    assert {"xsubticks off", "ysubticks off"} <= set(_graph_lines(fig))


def test_nsubticks_loglabels_nofirst_and_nolast():
    fig, ax = _fig()
    ax.set_yscale("log")
    ax.set_xticks(nsubticks=4, nofirst=True, nolast=True)
    ax.set_xscale("log")
    ax.set_yticks(loglabels="l25b", nolast=True)
    lines = _graph_lines(fig)
    assert any(
        line.startswith("xaxis") and line.endswith("nsubticks 4 nofirst nolast")
        for line in lines
    ), lines
    assert any(line.startswith("yaxis") and line.endswith("nolast") for line in lines)
    assert "ylabels log l25b" in lines
    ax.set_xticks(nofirst=False)
    assert not ax._remove_first_xtick and ax._remove_last_xtick


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"nsubticks": 0}, "nsubticks=0"),
        ({"nsubticks": 2.5}, "nsubticks=2.5"),
        ({"loglabels": "l3"}, "loglabels='l3'"),
    ],
)
def test_set_xticks_rejects_bad_minor_and_label_options(kwargs, match):
    _, ax = _fig()
    with pytest.raises(ValueError, match=match):
        ax.set_xticks(**kwargs)


@pytest.mark.parametrize(
    "call, shown",
    [
        (lambda ax: ax.set_xlabel("X", axis="top"), "'x' or 'x2', got 'top'"),
        (lambda ax: ax.set_ylabel("Y", axis="y3"), "'y' or 'y2', got 'y3'"),
        (lambda ax: ax.figure.xlabel("X", axis="top"), "set_xlabel() axis"),
    ],
)
def test_a_label_axis_that_is_not_an_axis_raises(call, shown):
    _, ax = _fig()
    with pytest.raises(ValueError, match=re.escape(shown)):
        call(ax)
    with pytest.raises(TypeError, match=re.escape("got 2")):
        ax.set_xlabel("X", 2)
    assert (ax.xlabel_text, ax.ylabel_text) == ("", "")


def test_a_positional_fontdict_is_matplotlibs_and_labels_the_primary_axis():
    _, ax = _fig()
    with pytest.warns(UserWarning, match="fontdict"):
        ax.set_ylabel("Y", {"fontsize": 9})
    ax.set_xlabel("X", None)
    assert (ax.xlabel_text, ax.ylabel_text) == ("X", "Y")
    with pytest.warns(UserWarning, match="fontdict"):
        ax.twinx().set_ylabel("R", {"fontsize": 9})
    with pytest.warns(UserWarning, match="fontdict"):
        ax.twiny().set_xlabel("T", {"fontsize": 9})
    assert (ax.y2label_text, ax.x2label_text) == ("R", "T")


def test_grid_with_only_an_unknown_keyword_turns_the_grid_on():
    _, ax = _fig()
    ax.grid(True)
    with pytest.warns(UserWarning, match="alpha"):
        ax.grid(alpha=0.3)
    assert ax.xgrid


def test_title_aliases_c_and_size():
    _, ax = _fig()
    ax.set_title("T", c="red", size=12)
    assert (ax.title_color, ax.title_size) == ("RED", 12.0)

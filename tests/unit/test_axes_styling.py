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

import warnings

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
    with pytest.raises(ValueError, match="must be 'both', 'x', 'y' or 'y2'"):
        ax.set_tick_format("fix 1", axis="x2")


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
        ({"alpha": 0.5}, "unsupported keyword argument"),
    ],
)
def test_grid_rejects_nonsense(kwargs, match):
    _, ax = _fig()
    with pytest.raises(ValueError, match=match):
        ax.grid(True, **kwargs)


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
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2", axis="y")
    ax.set_tick_format("eng 2", axis="y2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14.0, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10.0, "BLUE", 0.35
    ax.ylabel_size, ax.ylabel_color, ax.ylabel_dist = 9.0, "GREEN", 0.36
    ax.y2label_size, ax.y2label_color, ax.y2label_dist = 8.0, "PURPLE", 0.37
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7.0, "ORANGE", 30.0
    ax.yticklabel_size, ax.yticklabel_color, ax.yticklabel_angle = 6.5, "CYAN", 15.0
    ax.y2ticklabel_size, ax.y2ticklabel_color, ax.y2ticklabel_angle = 6.0, "PINK", 45.0
    return ax


def test_every_styling_field_survives_to_dict_from_dict():
    from gleplot.axes import _STYLING_KEYS

    fig, ax = _fig()
    _styled_axes(ax)
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

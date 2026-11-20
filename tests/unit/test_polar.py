"""Polar axes: ``add_subplot(projection='polar')`` and the script it writes."""

from __future__ import annotations

import re
import warnings

import numpy as np
import pytest

import gleplot as glp
from gleplot.writer import polar_label_decimals, polar_ring_step, polar_window


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _polar(**figure_kwargs):
    fig = glp.figure(data_prefix="pl", **figure_kwargs)
    return fig, fig.add_subplot(projection="polar")


def _graph_lines(fig):
    text, _files = fig._generate_gle_with_files()
    body = text.split("begin graph", 1)[1].split("end graph", 1)[0]
    return [line.strip() for line in body.splitlines() if line.strip()], text


def test_a_plot_is_drawn_through_the_polar_let():
    fig, ax = _polar()
    ax.plot([0, np.pi / 2, np.pi], [1, 2, 1], label="r")
    lines, _text = _graph_lines(fig)
    i = lines.index("data pl_0.dat d1=c1,c2")
    assert lines[i + 1] == "let d2 = d1*cos(x),d1*sin(x)"
    assert lines[i + 2].startswith("d2 line ")
    assert lines[i + 2].endswith('key "r"')


def test_the_data_file_keeps_theta_and_r():
    fig, ax = _polar()
    ax.plot([0, 1.5], [2, 3])
    _text, files = fig._generate_gle_with_files()
    rows = [row.split() for row in files["pl_0.dat"].splitlines()[1:]]
    assert rows == [["0", "2"], ["1.5", "3"]]


def test_scatter_and_function_take_the_polar_let_too():
    fig, ax = _polar()
    ax.scatter([0, 1], [1, 1])
    ax.function("cos(2*x)")
    lines, _text = _graph_lines(fig)
    # The function is drawn first, below the scatter.
    assert lines[lines.index("let d1 = cos(2*x) from 0 to 6.28319") + 1 :][:2] == [
        "let d2 = d1*cos(x),d1*sin(x)",
        "d2 line color rgb255(31,119,180) lwidth 0.05292",
    ]
    i = lines.index("data pl_0.dat d3=c1,c2")
    assert lines[i + 1] == "let d4 = d3*cos(x),d3*sin(x)"
    assert lines[i + 2].startswith("d4 marker ")


def test_figure_wide_smoothing_does_not_reach_a_polar_line():
    """GLE cannot smooth x values out of order, which a polar curve has."""
    fig = glp.figure(data_prefix="pl", graph=glp.GLEGraphConfig(smooth_curves=True))
    fig.add_subplot(projection="polar").plot([0, 2, 1], [1, 1, 0.5])
    lines, _text = _graph_lines(fig)
    assert not any("smooth" in line for line in lines)
    _text, files = fig._generate_gle_with_files()
    assert [row.split()[0] for row in files["pl_0.dat"].splitlines()[1:]] == [
        "0",
        "2",
        "1",
    ]


def test_a_function_keeps_its_own_range():
    fig, ax = _polar()
    ax.function("x", xmin=1, xmax=3, step=0.5)
    lines, _text = _graph_lines(fig)
    assert "let d1 = x from 1 to 3 step 0.5" in lines


def test_the_frame_is_hidden_and_the_grid_drawn_in_layer_200():
    fig, ax = _polar()
    ax.plot([0, 1], [1, 2])
    lines, text = _graph_lines(fig)
    for line in ("xside off", "yside off", "xticks off", "yticks off"):
        assert line in lines
    i = lines.index("begin layer 200")
    assert lines[i + 1 : i + 3] == ["draw glp_polar_grid 2 0.5", "end layer"]
    assert "sub glp_polar_grid rmax step" in text
    assert "sub glp_polar_labels rmax step dp" in text


def test_the_labels_are_written_after_end_graph():
    fig, ax = _polar()
    ax.plot([0, 1], [1, 2])
    _lines, text = _graph_lines(fig)
    after = text.split("end graph", 1)[1].splitlines()
    assert after[1:4] == [
        "gsave",
        'glp_polar_labels 2 0.5 1 "^{\\circ}"',
        "grestore",
    ]


def test_with_usetex_the_degree_mark_is_latex_math():
    style = glp.GLEStyleConfig(usetex=True)
    fig = glp.figure(data_prefix="pl", style=style)
    fig.add_subplot(projection="polar").plot([0, 1], [1, 2])
    _lines, text = _graph_lines(fig)
    assert 'glp_polar_labels 2 0.5 1 "$^{\\circ}$"' in text


def test_a_cartesian_axes_beside_a_polar_one_is_unchanged():
    fig = glp.figure(data_prefix="pl")
    fig.add_subplot(1, 2, 1, projection="polar").plot([0, 1], [1, 2])
    fig.add_subplot(1, 2, 2).plot([0, 1], [1, 2])
    text, _files = fig._generate_gle_with_files()
    second = text.split("begin graph")[2]
    assert "cos(x)" not in second
    assert "glp_polar" not in second


def test_a_figure_without_polar_axes_has_no_polar_subs():
    fig = glp.figure(data_prefix="pl")
    fig.add_subplot().plot([0, 1], [1, 2])
    text, _files = fig._generate_gle_with_files()
    assert "glp_polar" not in text


def test_the_radial_limit_rounds_the_data_up_to_a_ring():
    fig, ax = _polar()
    ax.plot([0, 1, 2], [0.2, 1.37, -0.4])
    _lines, text = _graph_lines(fig)
    assert "draw glp_polar_grid 1.5 0.5" in text
    assert ax.get_ylim() == (0.0, 1.5)


def test_set_ylim_sets_the_radial_limit():
    fig, ax = _polar()
    ax.plot([0, 1], [1, 2])
    ax.set_ylim(0, 1.3)
    _lines, text = _graph_lines(fig)
    assert "draw glp_polar_grid 1.3 0.5" in text
    assert "glp_polar_labels 1.3 0.5 1" in text


def test_function_curves_alone_get_a_radial_limit_of_one():
    fig, ax = _polar()
    ax.function("cos(x)")
    _lines, text = _graph_lines(fig)
    assert "draw glp_polar_grid 1 0.2" in text


def test_the_window_gives_both_axes_the_same_scale():
    """Rings are circles: equal cm per unit on x and y, outer ring inset."""
    fig, ax = _polar(figsize=(6, 3))
    ax.plot([0, 1], [1, 2])
    lines, _text = _graph_lines(fig)
    w, h = (float(v) for v in lines[0].split()[1:])
    xmax = float(next(x for x in lines if x.startswith("xaxis")).split()[4])
    ymax = float(next(x for x in lines if x.startswith("yaxis")).split()[4])
    assert w / (2 * xmax) == pytest.approx(h / (2 * ymax), rel=1e-5)
    assert ymax > 2


@pytest.mark.parametrize(
    "rmax,step,dp",
    [(1, 0.2, 1), (1.5, 0.5, 1), (2, 0.5, 1), (4.2, 1, 0), (10, 2, 0), (0.25, 0.05, 2)],
)
def test_ring_steps_and_label_decimals(rmax, step, dp):
    assert polar_ring_step(rmax) == step
    assert polar_label_decimals(polar_ring_step(rmax)) == dp


def test_without_a_frame_the_window_is_square():
    assert polar_window(2.0, None, 0.4) == (2.0, 2.0)


def test_add_subplot_with_no_spec_is_the_only_subplot():
    fig = glp.figure()
    assert fig.add_subplot(projection="polar").position == (1, 1, 1)


def test_an_unknown_projection_raises():
    fig = glp.figure()
    with pytest.raises(ValueError, match="projection='3d'"):
        fig.add_subplot(projection="3d")


@pytest.mark.parametrize(
    "call",
    [
        lambda ax: ax.bar([1], [1]),
        lambda ax: ax.text(0, 1, "t"),
        lambda ax: ax.set_xlim(0, 1),
        lambda ax: ax.set_xticks([0, 1]),
        lambda ax: ax.minorticks_on(),
        lambda ax: ax.derived("d", "2*d"),
        lambda ax: ax.tick_params(labelsize=8),
        lambda ax: ax.step([0, 1], [1, 1]),
        lambda ax: ax.function2d("x*y", extent=(0, 1, 0, 1)),
        lambda ax: ax.image("a.png", extent=(0, 1, 0, 1)),
    ],
)
def test_cartesian_only_methods_raise_on_a_polar_axes(call):
    _fig, ax = _polar()
    with pytest.raises(NotImplementedError, match="not supported on a polar axes"):
        call(ax)


@pytest.mark.parametrize(
    "kwargs,shown",
    [
        ({"yaxis": "y2"}, "yaxis='y2'"),
        ({"offset": 1.0}, "offset=1.0"),
        ({"drawstyle": "steps"}, "drawstyle='steps'"),
        ({"line_mode": "impulses"}, "line_mode='impulses'"),
        ({"ds": "steps"}, "ds='steps'"),
        ({"xmax": 1.0}, "xmax=1.0"),
    ],
)
def test_cartesian_plot_keywords_raise_on_a_polar_axes(kwargs, shown):
    _fig, ax = _polar()
    with pytest.raises(ValueError, match=re.escape(shown)):
        ax.plot([0, 1], [1, 2], **kwargs)


def test_a_scatter_keyword_is_named_as_passed():
    _fig, ax = _polar()
    with pytest.raises(ValueError, match="yaxis='y2'"):
        ax.scatter([0, 1], [1, 2], yaxis="y2")


def test_drawstyle_default_is_accepted():
    _fig, ax = _polar()
    ax.plot([0, 1], [1, 2], drawstyle="default")
    ax.plot([0, 1], [1, 2], ds="default")
    assert len(ax.lines) == 2


def test_grid_true_is_a_no_op_and_hiding_warns():
    _fig, ax = _polar()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ax.grid(True)
    for call in (lambda: ax.grid(False), lambda: ax.grid(), lambda: ax.grid(color="r")):
        with pytest.warns(UserWarning, match="polar axes"):
            call()
    assert ax.xgrid is None and ax.ygrid is None


def test_the_figure_wide_grid_default_does_not_reach_a_polar_axes():
    fig = glp.figure(data_prefix="pl", graph=glp.GLEGraphConfig(show_grid=True))
    fig.add_subplot(projection="polar").plot([0, 1], [1, 2])
    lines, _text = _graph_lines(fig)
    assert not any(line.split()[-1] == "grid" for line in lines)


def test_a_shared_y_axis_leaves_the_radial_limit_alone():
    fig = glp.Figure(data_prefix="pl", sharey=True)
    fig.add_subplot(1, 2, 1).plot([0, 1], [-5, 10])
    fig.add_subplot(1, 2, 2, projection="polar").plot([0, 1], [1, 2])
    text, _files = fig._generate_gle_with_files()
    assert "draw glp_polar_grid 2 0.5" in text
    assert fig.axes_list[1].get_ylim() == (0.0, 2.0)


def test_a_tiny_radius_does_not_divide_by_zero():
    fig, ax = _polar()
    ax.plot([0, 1], [1e-10, 2e-10])
    fig._generate_gle_with_files()
    assert ax.get_ylim()[1] > 0


@pytest.mark.parametrize(
    "args,match", [((0.5, 2), "bottom=0.5"), ((0, -1), "top=-1"), ((0, 0), "top=0")]
)
def test_set_ylim_on_a_polar_axes_checks_the_radial_limits(args, match):
    _fig, ax = _polar()
    with pytest.raises(ValueError, match=match):
        ax.set_ylim(*args)


def test_the_polar_flag_survives_to_dict():
    fig, ax = _polar()
    ax.plot([0, 1], [1, 2])
    payload = fig.to_dict()
    assert payload["figure"]["axes"][0]["polar"] is True
    restored = glp.Figure.from_dict(payload)
    assert restored.axes_list[0]._polar is True
    assert restored._generate_gle_with_files()[0] == fig._generate_gle_with_files()[0]


def test_a_cartesian_axes_has_no_polar_key():
    fig = glp.figure()
    fig.add_subplot().plot([0, 1], [1, 2])
    assert "polar" not in fig.to_dict()["figure"]["axes"][0]


def test_set_ylim_on_a_polar_axes_rejects_the_y2_axis():
    _fig, ax = _polar()
    with pytest.raises(ValueError, match="axis='y2'"):
        ax.set_ylim(0, 1, axis="y2")


def test_a_frame_too_small_for_the_labels_still_gives_round_rings():
    xr, yr = polar_window(1.0, (1.0, 0.5), 0.4)
    # The ring fills the shorter side, with the labels outside the frame.
    assert (xr, yr) == (pytest.approx(2.0), pytest.approx(1.0))


def test_a_scatter_with_per_point_sizes_takes_the_polar_let():
    fig, ax = _polar()
    ax.scatter([0, 1, 2], [1, 2, 1.5], s=[10, 40, 90])
    lines, _text = _graph_lines(fig)
    i = lines.index("data pl_0.dat d1=c1,c2 d2=c1,c3")
    assert lines[i + 1] == "let d3 = d1*cos(x),d1*sin(x)"
    assert lines[i + 2].startswith("d3 marker glp_mdata_fcircle ")
    assert " mdata d2 " in lines[i + 2]

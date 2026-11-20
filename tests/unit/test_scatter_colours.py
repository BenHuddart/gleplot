"""``scatter``'s ``c``: per-point colours, one colour, or one colour per point.

A GLE dataset has one colour, so numeric ``c`` is drawn through ``mdata`` and
a generated marker sub that colours each point; a colour sequence becomes one
series per colour. These tests pin the emitted script and the arguments that
are rejected or warned about at the call.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import gleplot as glp

X = [1.0, 2.0, 3.0]
Y = [1.0, 4.0, 9.0]


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


def _ax():
    return glp.figure(data_prefix="t").add_subplot(111)


def _script(ax):
    return ax.figure._generate_gle_with_files()


# --------------------------------------------------------------------------- #
# numeric c -- colour-mapped
# --------------------------------------------------------------------------- #


def test_values_are_coloured_through_a_marker_sub():
    ax = _ax()
    ax.scatter(X, Y, c=[0, 150, 300], cmap="viridis", label="temp")
    text, files = _script(ax)

    assert (
        "sub gleplot_cdata_fcircle_viridis size data\n"
        "   gsave\n"
        "   set hei size\n"
        "   set color cmap_viridis(data)\n"
        "   marker FCIRCLE\n"
        "   grestore\n"
        "end sub\n"
        "define marker gleplot_cdata_fcircle_viridis gleplot_cdata_fcircle_viridis\n"
    ) in text
    assert "sub cmap_viridis z\n" in text
    assert (
        "    data t_0.dat d1=c1,c2 d2=c1,c3\n"
        "    let d3 = (d2-0)/(300-0)\n"
        "    d1 marker gleplot_cdata_fcircle_viridis msize 0.134164 mdata d3 "
        'key "temp"\n'
    ) in text
    # The values are written as given; the let maps them.
    assert files["t_0.dat"].splitlines() == [
        "x temp c",
        "1 1 0",
        "2 4 150",
        "3 9 300",
    ]


def test_default_cmap_and_limits_follow_the_data():
    ax = _ax()
    ax.scatter(X, Y, c=[2.5, -1.5, 7.0])
    series = ax.scatters[0]
    assert series["cmap"] == "viridis"
    assert (series["vmin"], series["vmax"]) == (-1.5, 7.0)
    assert series["color"] is None
    text, _files = _script(ax)
    assert "    let d3 = (d2+1.5)/(7+1.5)\n" in text


def test_explicit_limits_and_a_reversed_cmap():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3], cmap="plasma_r", vmin=-4, vmax=-2, marker="s")
    text, _files = _script(ax)
    assert "    let d3 = (d2+4)/(-2+4)\n" in text
    assert "marker gleplot_cdata_fsquare_plasma_r msize" in text
    assert "set color cmap_plasma_r(data)\n" in text


def test_equal_limits_give_the_first_colour():
    """matplotlib maps every value to 0 when vmin == vmax."""
    ax = _ax()
    ax.scatter(X, Y, c=[5, 5, 5])
    text, _files = _script(ax)
    assert "    let d3 = (d2-5)*0\n" in text


def test_gray_still_gets_a_sub():
    """A heatmap uses GLE's own gray; a marker needs a function."""
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3], cmap="gray")
    text, _files = _script(ax)
    assert "sub cmap_gray z\n" in text
    assert "set color cmap_gray(data)\n" in text


def test_one_sub_per_marker_and_cmap():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3])
    ax.scatter(X, Y, c=[4, 5, 6])
    ax.scatter(X, Y, c=[4, 5, 6], cmap="magma")
    text, _files = _script(ax)
    assert text.count("sub gleplot_cdata_fcircle_viridis ") == 1
    assert text.count("sub gleplot_cdata_fcircle_magma ") == 1
    assert text.count("sub cmap_viridis z") == 1


def test_a_heatmap_and_a_scatter_share_one_palette_sub():
    ax = _ax()
    ax.imshow(np.arange(4.0).reshape(2, 2), extent=(0, 10, 0, 10), cmap="viridis")
    ax.scatter(X, Y, c=[1, 2, 3])
    text, _files = _script(ax)
    assert text.count("sub cmap_viridis z") == 1


def test_points_without_a_colour_are_left_out():
    """matplotlib leaves a point whose value is not finite out of the plot and
    of the axis limits (``plotnonfinite=False``)."""
    ax = _ax()
    ax.scatter([1, 2, 30, 4], [1, 2, 30, 4], c=[1, np.nan, np.inf, 4])
    text, files = _script(ax)
    assert files["t_0.dat"].splitlines()[1:] == ["1 1 1", "4 4 4"]
    assert "    xaxis min 1 max 4\n" in text
    assert (ax.scatters[0]["vmin"], ax.scatters[0]["vmax"]) == (1.0, 4.0)


def test_figure_legend_draws_the_colour_marker():
    """``fig.legend()`` draws the swatch through the colour sub, like the
    in-graph key does."""
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3], label="pts")
    ax.figure.legend()
    text, _files = _script(ax)
    assert 'text "pts" marker gleplot_cdata_fcircle_viridis msize' in text


def test_three_numbers_for_three_points_are_values():
    """As in matplotlib: one number per point wins over an RGB reading."""
    ax = _ax()
    ax.scatter(X, Y, c=[1, 0, 0])
    assert list(ax.scatters[0]["cdata"]) == [1, 0, 0]


def test_per_point_colours_survive_to_dict():
    ax = _ax()
    ax.scatter(X, Y, c=[3, 1, 2], cmap="plasma", vmin=0)
    fig = ax.figure
    restored = glp.Figure.from_dict(fig.to_dict())
    series = restored.axes_list[0].scatters[0]
    assert isinstance(series["cdata"], np.ndarray)
    assert restored._generate_gle_with_files() == fig._generate_gle_with_files()


def test_no_marker_means_no_sub():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3], marker="None")
    text, _files = _script(ax)
    assert "gleplot_cdata" not in text


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"c": [1, 2]}, "does not match the 3 points"),
        ({"c": ["r", "g"]}, "does not match the 3 points"),
        ({"c": [1, 2, 3], "color": "red"}, "both c="),
        ({"c": [1, 2, 3], "vmin": 3, "vmax": 1}, "vmin <= vmax"),
        ({"c": 5}, "does not match the 3 points"),
        ({"c": [1, 2, 3], "vmin": np.nan}, "finite number"),
        ({"c": [1, 2, 3], "vmax": "high"}, "finite number"),
        ({"c": [1, 2, 3], "cmap": "nope"}, "Unknown cmap"),
        ({"c": [1, 2, 3], "mdist": 1.0}, r"mdist=1\.0"),
        ({"c": [1, 2, 3], "deresolve": 2}, "deresolve=2"),
    ],
)
def test_bad_colours_are_rejected_at_the_call(kwargs, match):
    ax = _ax()
    with pytest.raises(ValueError, match=match):
        ax.scatter(X, Y, **kwargs)
    assert ax.scatters == []


def test_per_point_sizes_with_per_point_colours_warn_and_draw_the_colours():
    ax = _ax()
    with pytest.warns(UserWarning, match=r"per-point colours \(c=\) at one size"):
        ax.scatter(X, Y, c=[1, 2, 3], s=[4, 16, 36])
    series = ax.scatters[0]
    assert "cdata" in series and "mdata" not in series


# --------------------------------------------------------------------------- #
# one colour, or one colour per point
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "c, color",
    [
        ("red", "red"),
        (["red"], "red"),
        ((1.0, 0.5, 0.0), (1.0, 0.5, 0.0)),
        ([[1.0, 0.5, 0.0]], (1.0, 0.5, 0.0)),
    ],
)
def test_one_colour_is_color(c, color):
    """Four points, so a three-number RGB is not one value per point."""
    a, b = _ax(), _ax()
    a.scatter(X + [4.0], Y + [16.0], c=c)
    b.scatter(X + [4.0], Y + [16.0], color=color)
    assert _script(a) == _script(b)


def test_one_rgb_row_is_one_colour_even_for_three_points():
    """matplotlib reads shape (1, 3) as one colour, not three values."""
    a, b = _ax(), _ax()
    a.scatter(X, Y, c=[[1, 0, 0]])
    b.scatter(X, Y, color=(1, 0, 0))
    assert _script(a) == _script(b)


def test_a_colour_per_point_is_one_series_per_colour():
    ax = _ax()
    ax.scatter(
        [1, 2, 3, 4],
        [1, 2, 3, 4],
        c=["g", "r", "g", (0, 0, 1)],
        s=[10, 20, 30, 40],
        label="pts",
        zorder=5,
    )
    groups = [(s["color"], list(s["x"]), s["label"], s["zorder"]) for s in ax.scatters]
    assert groups == [
        ("GREEN", [1, 3], "pts", 5.0),
        ("RED", [2], None, 5.0),
        ("rgb255(0,0,255)", [4], None, 5.0),
    ]
    # Sizes travel with their points.
    a = _ax()
    a.scatter([1, 3], [1, 3], color="g", s=[10, 30])
    assert list(ax.scatters[0]["mdata"]) == list(a.scatters[0]["mdata"])


def test_rgb_rows_are_a_colour_per_point():
    ax = _ax()
    ax.scatter(X, Y, c=np.array([[1, 0, 0], [0, 0, 1], [1, 0, 0]]))
    assert [s["color"] for s in ax.scatters] == ["rgb255(255,0,0)", "rgb255(0,0,255)"]


def test_an_array_of_names_is_a_colour_per_point():
    ax = _ax()
    ax.scatter(X, Y, c=np.array(["red", "blue", "red"]))
    assert [s["color"] for s in ax.scatters] == ["RED", "BLUE"]


def test_names_and_tuples_mix_in_a_colour_sequence():
    ax = _ax()
    ax.scatter(X, Y, c=[(1, 0, 0), "blue", (1, 0, 0)])
    assert [s["color"] for s in ax.scatters] == ["rgb255(255,0,0)", "BLUE"]


def test_polar_points_are_coloured_through_the_polar_let():
    ax = glp.figure(data_prefix="t").add_subplot(111, projection="polar")
    ax.scatter([0.0, 1.0, 2.0], [1, 2, 3], c=[1, 2, 3])
    text, _files = _script(ax)
    assert (
        "    let d3 = (d2-1)/(3-1)\n"
        "    let d4 = d1*cos(x),d1*sin(x)\n"
        "    d4 marker gleplot_cdata_fcircle_viridis msize 0.134164 mdata d3"
    ) in text


def test_strings_are_colours_even_when_they_read_as_numbers():
    """matplotlib reads ``'0.25'`` as a grey, never as a value to map."""
    ax = _ax()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        ax.scatter(X, Y, c=["0.25", "0.75", "0.25"])
    assert ax.scatters and all("cdata" not in s for s in ax.scatters)


# --------------------------------------------------------------------------- #
# keywords with nothing to act on
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs, name",
    [({"cmap": "viridis"}, "cmap"), ({"vmin": 0}, "vmin"), ({"vmax": 1}, "vmax")],
)
def test_colour_map_keywords_without_values_warn(kwargs, name):
    ax = _ax()
    with pytest.warns(UserWarning, match=rf"scatter\({name}=.*no values to colour-map"):
        ax.scatter(X, Y, c="red", **kwargs)
    assert "cdata" not in ax.scatters[0]


def test_norm_warns_and_is_ignored():
    a, b = _ax(), _ax()
    with pytest.warns(UserWarning, match=r"scatter\(norm='log'\) is ignored"):
        a.scatter(X, Y, c=[1, 2, 3], norm="log")
    b.scatter(X, Y, c=[1, 2, 3])
    assert _script(a) == _script(b)


def test_plain_scatter_is_untouched():
    """No ``c``: no warning, and the historical script."""
    ax = _ax()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ax.scatter(X, Y, color="red")
    assert "gleplot_cdata" not in _script(ax)[0]


# --------------------------------------------------------------------------- #
# colorbar
# --------------------------------------------------------------------------- #


def test_colorbar_shows_the_scatter_range():
    ax = _ax()
    ax.scatter(X, Y, c=[3, 1, 2], vmin=0, vmax=300)
    cb = ax.figure.colorbar(label="T (K)")
    assert ax.scatters[0]["colorbar"] is cb
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (0.0, 300.0, 60.0)
    text, _files = _script(ax)
    assert 'include "color.gle"' in text
    assert (
        "end graph\n"
        "gsave\n"
        "amove xg(xgmax)+0.3 yg(ygmin)\n"
        "color_range_vertical zmin 0 zmax 300 zstep (300-(0))/5*0.999999999 "
        'palette "cmap_viridis" width 0.5 height yg(ygmax)-yg(ygmin) '
        'format "fix 0" pixels 200\n'
        'amove xg(xgmax)+(0.3+0.5*5/3+0.2)+max(twidth(format$(0,"fix 0")),'
        'twidth(format$(300,"fix 0"))) (yg(ygmin)+yg(ygmax))/2\n'
        "set just tc\n"
        "begin rotate 90\n"
        'write "T (K)"\n'
        "end rotate\n"
        "grestore"
    ) in text


def test_colorbar_makes_room_beside_the_scatter():
    plain, barred = _ax(), _ax()
    for ax in (plain, barred):
        ax.scatter(X, Y, c=[1, 2, 3])
    barred.figure.colorbar()
    width = [
        float(_script(ax)[0].split("    size ", 1)[1].split()[0])
        for ax in (plain, barred)
    ]
    assert width[1] < width[0]


def test_colorbar_on_ax_takes_the_last_mapped_scatter_and_moves():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3])
    ax.scatter(X, Y, color="red")
    ax.scatter(X, Y, c=[4, 5, 6], cmap="magma")
    fig = ax.figure
    fig.colorbar(ax=ax)
    assert [("colorbar" in s) for s in ax.scatters] == [False, False, True]
    fig.colorbar(ax=ax, orientation="horizontal")
    text, _files = _script(ax)
    assert text.count("color_range_horizontal zmin 4 zmax 6") == 1
    assert "color_range_vertical zmin" not in text


def test_a_heatmap_keeps_the_bar_on_its_axes():
    ax = _ax()
    ax.imshow(np.arange(4.0).reshape(2, 2))
    ax.scatter(X, Y, c=[1, 2, 3])
    ax.figure.colorbar(ax=ax)
    assert "colorbar" not in ax.scatters[0]
    assert ax.heatmaps[0]["colorbar"] is not None


def test_colorbar_is_ambiguous_across_axes_until_ax_picks_one():
    fig, (a, b) = glp.subplots(1, 2)
    a.scatter(X, Y, c=[1, 2, 3])
    b.scatter(X, Y, c=[1, 2, 3], cmap="gray")
    with pytest.raises(ValueError, match="more than one axes"):
        fig.colorbar()
    fig.colorbar(ax=b)
    text, _files = fig._generate_gle_with_files()
    assert 'palette "gray"' in text


def test_colorbar_needs_a_mapped_scatter():
    ax = _ax()
    ax.scatter(X, Y, color="red")
    with pytest.raises(ValueError, match="colour-mapped scatter"):
        ax.figure.colorbar(ax=ax)
    with pytest.raises(TypeError, match="For a scatter, pass its axes as ax="):
        ax.figure.colorbar(ax)


def test_a_scatter_colorbar_survives_to_dict():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3])
    fig = ax.figure
    fig.colorbar(orientation="horizontal", label="v")
    restored = glp.Figure.from_dict(fig.to_dict())
    assert restored._generate_gle_with_files() == fig._generate_gle_with_files()


def test_a_heatmap_bar_replaces_the_scatter_bar_on_its_axes():
    ax = _ax()
    ax.scatter(X, Y, c=[1, 2, 3])
    fig = ax.figure
    fig.colorbar(ax=ax)
    im = ax.imshow(np.arange(4.0).reshape(2, 2), extent=(0, 10, 0, 10), cmap="plasma")
    fig.colorbar(im)
    assert "colorbar" not in ax.scatters[0]
    assert _script(ax)[0].count("\ncolor_range_vertical zmin") == 1


def test_a_lone_heatmap_still_takes_the_figure_bar():
    """``fig.colorbar()`` found the heatmap before scatters had bars."""
    fig, (a, b) = glp.subplots(1, 2)
    im = a.imshow(np.arange(4.0).reshape(2, 2))
    b.scatter(X, Y, c=[1, 2, 3])
    assert fig.colorbar() is im["colorbar"]

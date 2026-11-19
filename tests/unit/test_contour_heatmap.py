"""Unit tests for contour/heatmap (imshow-style) support: stored dicts + GLE.

Mirrors the ``tests/unit/test_plotting.py`` style -- assert the object-model
dicts each API call stores AND substrings of the generated GLE. Covers
``imshow``, ``pcolormesh``, ``contourf``, ``contour``, ``tripcolor``,
``tricontour``, ``Figure.colorbar``, palette emission, the ``.z``/points
sidecars, and the one-heatmap-per-axes rule.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot import axes as _axes_module
from gleplot import palettes


def _gle(fig):
    text, files = fig._generate_gle_with_files()
    return text, files


# --------------------------------------------------------------------------- #
# imshow (grid)
# --------------------------------------------------------------------------- #


def test_imshow_stores_heatmap_dict():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    Z = np.arange(12, dtype=float).reshape(3, 4)
    hm = ax.imshow(Z, extent=(0, 4, 0, 3), cmap="viridis", vmin=0, vmax=11)

    assert hm is ax.heatmaps[0]
    assert hm["type"] == "heatmap"
    assert hm["source"] == "grid"
    assert hm["extent"] == [0.0, 4.0, 0.0, 3.0]
    assert hm["cmap"] == "viridis"
    assert hm["vmin"] == 0.0 and hm["vmax"] == 11.0
    assert hm["pixels"] == [200, 200]
    assert hm["origin"] == "lower"
    assert hm["interpolation"] == "bicubic"
    assert hm["invert"] is False
    assert hm["data_file"] == "t_heatmap1.z"
    assert hm["colorbar"] is None


def test_imshow_default_extent_and_cmap():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    Z = np.zeros((5, 7))
    hm = ax.imshow(Z)
    assert hm["extent"] == [0.0, 7.0, 0.0, 5.0]
    assert hm["cmap"] == "viridis"  # graph.default_cmap


def test_imshow_emits_colormap_and_z_sidecar():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(
        np.arange(6.0).reshape(2, 3),
        extent=(0, 3, 0, 2),
        cmap="viridis",
        vmin=0,
        vmax=5,
    )
    text, files = _gle(fig)

    assert (
        'colormap "t_heatmap1.z" 200 200 zmin 0 zmax 5 palette gleplot_viridis' in text
    )
    assert "sub gleplot_viridis z" in text
    # .z sidecar: header + ny rows of nx values, y increasing.
    z = files["t_heatmap1.z"]
    assert z.startswith("! nx 3 ny 2 xmin 0 xmax 3 ymin 0 ymax 2\n")
    assert z.splitlines()[1] == "0 1 2"  # row ymin first
    assert z.splitlines()[2] == "3 4 5"


def test_imshow_origin_upper_flips_rows():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.array([[0.0, 1.0], [2.0, 3.0]]), extent=(0, 2, 0, 2), origin="upper")
    _, files = _gle(fig)
    rows = files["t_heatmap1.z"].splitlines()
    # origin='upper': row 0 (top) written last -> ymin row is [2, 3].
    assert rows[1] == "2 3"
    assert rows[2] == "0 1"


def test_imshow_gray_has_no_palette_clause():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="gray")
    text, _ = _gle(fig)
    assert "colormap" in text
    assert "palette" not in text.split("colormap", 1)[1].split("\n", 1)[0]
    assert "sub gleplot_" not in text


def test_imshow_rainbow_uses_color_switch():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="jet")  # alias -> rainbow
    text, _ = _gle(fig)
    line = [ln for ln in text.splitlines() if "colormap" in ln][0]
    assert " color" in line
    assert ax.heatmaps[0]["cmap"] == "rainbow"


def test_imshow_nearest_and_invert():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="viridis", interpolation="nearest", invert=True)
    line = [ln for ln in _gle(fig)[0].splitlines() if "colormap" in ln][0]
    assert " invert" in line
    assert " interpolate nearest" in line


def test_only_one_heatmap_per_axes():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="at most one heatmap"):
        ax.imshow(np.zeros((2, 2)))


def test_imshow_brewer_ramp_interpolates_its_colours():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="YlOrRd")
    text, _ = _gle(fig)
    assert ax.heatmaps[0]["cmap"] == "ylorrd"
    assert "palette gleplot_ylorrd" in text
    sub = text.split("sub gleplot_ylorrd z", 1)[1].split("end sub", 1)[0]
    # ColorBrewer YlOrRd runs #ffffcc -> #800026 over nine colours.
    assert "local b = 0.800000" in sub
    assert "then r = 0.741176+(0.501961-0.741176)*(z-7/8)*8" in sub


def test_imshow_brewer_qualitative_is_stepped():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="Set1")
    text, _ = _gle(fig)
    assert "palette gleplot_set1" in text
    sub = text.split("sub gleplot_set1 z", 1)[1].split("end sub", 1)[0]
    # Nine ColorBrewer Set1 colours, one equal band each: #e41a1c ... #999999.
    lines = sub.strip().splitlines()
    assert len(lines) == 9
    assert lines[0].strip() == "if z < 1/9 then return rgb(0.894118,0.101961,0.109804)"
    assert lines[-1].strip() == "return rgb(0.600000,0.600000,0.600000)"


def test_imshow_reversed_cmap_flips_z_in_its_own_sub():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    hm = ax.imshow(np.zeros((2, 2)), cmap="RdBu_r")
    fig.colorbar(hm)
    text, _ = _gle(fig)
    assert hm["cmap"] == "rdbu_r"
    assert "palette gleplot_rdbu_r" in text
    # The colorbar draws the same reversed palette.
    assert 'palette "gleplot_rdbu_r"' in text
    assert "sub gleplot_rdbu z" not in text
    sub = text.split("sub gleplot_rdbu_r z\n", 1)[1]
    assert sub.startswith("   z = 1-z\n")
    forward = palettes.palette_sub_text("RdBu").split("\n", 1)[1]
    assert sub.split("end sub", 1)[0] + "end sub" == "   z = 1-z\n" + forward


@pytest.mark.parametrize(
    "cmap, canonical", [("gray_r", "gray_r"), ("jet_r", "rainbow_r")]
)
def test_imshow_reversed_builtin_cmap_emits_a_sub(cmap, canonical):
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap=cmap)
    text, _ = _gle(fig)
    assert ax.heatmaps[0]["cmap"] == canonical
    line = [ln for ln in text.splitlines() if ln.lstrip().startswith("colormap")][0]
    assert line.endswith(f"palette gleplot_{canonical}")
    assert "color" not in line.split()
    assert f"sub gleplot_{canonical} z\n   z = 1-z\n" in text


def test_imshow_reversed_qualitative_lists_its_colours_backwards():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((2, 2)), cmap="Set1_r")
    text, _ = _gle(fig)
    sub = text.split("sub gleplot_set1_r z\n", 1)[1].split("end sub", 1)[0]
    # matplotlib's Set1_r: the nine bands in reverse, a boundary k/9 in the
    # band above it, as for the forward map.
    lines = sub.strip().splitlines()
    assert lines[0].strip() == "if z < 1/9 then return rgb(0.600000,0.600000,0.600000)"
    assert lines[-1].strip() == "return rgb(0.894118,0.101961,0.109804)"


def test_unknown_cmap_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="Unknown cmap") as err:
        ax.imshow(np.zeros((2, 2)), cmap="turbo")
    # The accepted names are listed as matplotlib spells them.
    assert "RdYlBu" in str(err.value)
    assert "'_r'" in str(err.value)
    with pytest.raises(ValueError, match="Unknown cmap 'viridis_r_r'"):
        ax.imshow(np.zeros((2, 2)), cmap="viridis_r_r")


# --------------------------------------------------------------------------- #
# function2d (expression)
# --------------------------------------------------------------------------- #


def test_function2d_emits_bare_expression_and_no_sidecar():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    hm = ax.function2d("sin(x)*cos(y)", extent=(0, 6.28, 0, 6.28), vmin=-1, vmax=1)
    text, files = _gle(fig)

    assert hm is ax.heatmaps[0]
    assert "data_file" not in hm
    assert (
        "    colormap sin(x)*cos(y) 200 200 zmin -1 zmax 1 palette gleplot_viridis"
        in text.splitlines()
    )
    assert "xaxis min 0 max 6.28" in text
    assert "yaxis min 0 max 6.28" in text
    assert files == {}


def test_function2d_defaults_to_the_unit_colour_range():
    """GLE does not scan an expression for its range; 0..1 is written out."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.function2d("x*y", extent=(0, 1, 0, 1), cmap="gray")
    line = [ln for ln in _gle(fig)[0].splitlines() if "colormap" in ln][0]
    assert line == "    colormap x*y 200 200 zmin 0 zmax 1"
    fig.colorbar()
    assert ax.heatmaps[0]["colorbar"]["zmin"] == 0.0
    assert ax.heatmaps[0]["colorbar"]["zmax"] == 1.0


def test_function2d_none_range_omits_the_clauses():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.function2d("x+y", extent=(0, 1, 0, 1), vmin=None, vmax=None, invert=True)
    line = [ln for ln in _gle(fig)[0].splitlines() if "colormap" in ln][0]
    assert line == "    colormap x+y 200 200 invert palette gleplot_viridis"
    # The colorbar shows the 0..1 GLE draws.
    cb = fig.colorbar()
    assert (cb["zmin"], cb["zmax"]) == (0.0, 1.0)


@pytest.mark.parametrize(
    "expression, match",
    [
        ("sin(x) * cos(y)", "first space"),
        ('"x*y"', "end of the expression"),
        ("x,y", "second expression"),
        ("sin(x", "bracket open"),
        ("", "empty"),
    ],
)
def test_function2d_rejects_expressions_gle_cannot_read(expression, match):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=match):
        ax.function2d(expression, extent=(0, 1, 0, 1))


def test_function2d_rejects_a_non_string_expression():
    ax = glp.figure().add_subplot(111)
    with pytest.raises(TypeError, match="must be a str"):
        ax.function2d(3.0, extent=(0, 1, 0, 1))


def test_function2d_rejects_a_bad_extent():
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="xmin < xmax"):
        ax.function2d("x", extent=(1, 0, 0, 1))
    for bad in [(0, 1, 0), None, ("a", 1, 2, 3), 5]:
        with pytest.raises(ValueError, match=r"four numbers .* got "):
            ax.function2d("x", extent=bad)


def test_function2d_counts_as_the_axes_heatmap():
    ax = glp.figure().add_subplot(111)
    ax.imshow(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="at most one heatmap"):
        ax.function2d("x", extent=(0, 1, 0, 1))


# --------------------------------------------------------------------------- #
# pcolormesh (cells)
# --------------------------------------------------------------------------- #


def test_pcolormesh_writes_a_cell_grid():
    """The header sits half a cell outside the mesh and row/column 0 repeat."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    hm = ax.pcolormesh(
        np.linspace(0, 4, 5), np.linspace(0, 3, 4), np.arange(12.0).reshape(3, 4)
    )
    text, files = _gle(fig)

    assert hm is ax.heatmaps[0]
    assert hm["cells"] is True
    assert hm["extent"] == [0.0, 4.0, 0.0, 3.0]
    assert hm["interpolation"] == "nearest"
    assert (
        'colormap "t_heatmap1.z" 200 200 palette gleplot_viridis interpolate nearest'
        in text
    )
    assert "    xaxis min 0 max 4" in text
    assert files["t_heatmap1.z"].splitlines() == [
        "! nx 5 ny 4 xmin -0.5 xmax 4.5 ymin -0.5 ymax 3.5",
        "! gleplot: cells xmin 0 xmax 4 ymin 0 ymax 3",
        "0 0 1 2 3",
        "0 0 1 2 3",
        "4 4 5 6 7",
        "8 8 9 10 11",
    ]


def test_pcolormesh_header_places_cells_the_extent_would_round_away():
    """The header has more digits than an extent, so edges stay on the cells."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.pcolormesh(np.linspace(1e5, 1e5 + 0.7, 8), [0.0, 1.0], np.zeros((1, 7)))
    _, files = _gle(fig)
    header, marker = files["t_heatmap1.z"].splitlines()[:2]
    assert marker == "! gleplot: cells xmin 100000 xmax 100001 ymin 0 ymax 1"
    # Half a cell outside the written edges 100000 and 100001 (7 cells).
    assert "xmin 99999.9285714 xmax 100001.071429" in header


def test_imshow_has_no_cells_field():
    ax = glp.figure().add_subplot(111)
    assert "cells" not in ax.imshow(np.zeros((2, 2)))


@pytest.mark.parametrize(
    "args, shading, extent",
    [
        # C alone: edges 0..n, or centres 0..n-1 for 'nearest'.
        ((), None, [0.0, 4.0, 0.0, 3.0]),
        ((), "nearest", [-0.5, 3.5, -0.5, 2.5]),
        # 'auto' picks 'flat' for edges and 'nearest' for centres.
        ((np.arange(5.0), np.arange(4.0)), "auto", [0.0, 4.0, 0.0, 3.0]),
        ((np.arange(4.0), np.arange(3.0)), None, [-0.5, 3.5, -0.5, 2.5]),
        ((np.arange(5.0), np.arange(4.0)), "flat", [0.0, 4.0, 0.0, 3.0]),
        (
            np.meshgrid(np.linspace(1, 2.5, 4), np.linspace(10, 30, 3)),
            "nearest",
            [0.75, 2.75, 5.0, 35.0],
        ),
    ],
)
def test_pcolormesh_shading_sets_the_cell_edges(args, shading, extent):
    ax = glp.figure().add_subplot(111)
    hm = ax.pcolormesh(*args, np.zeros((3, 4)), shading=shading)
    assert hm["extent"] == extent


def test_pcolormesh_takes_a_2d_x_with_a_1d_y():
    """matplotlib accepts the two in either form, so gleplot does too."""
    ax = glp.figure().add_subplot(111)
    X = np.tile(np.arange(5.0), (4, 1))
    hm = ax.pcolormesh(X, np.arange(4.0), np.zeros((3, 4)))
    assert hm["extent"] == [0.0, 4.0, 0.0, 3.0]


def test_pcolormesh_turns_decreasing_coordinates_round():
    ax = glp.figure().add_subplot(111)
    C = np.arange(6.0).reshape(2, 3)
    hm = ax.pcolormesh([3.0, 2.0, 1.0, 0.0], [5.0, 4.0, 3.0], C)
    assert hm["extent"] == [0.0, 3.0, 3.0, 5.0]
    np.testing.assert_array_equal(hm["z"], C[::-1, ::-1])


@pytest.mark.parametrize(
    "args, match",
    [
        ((np.arange(5.0), np.arange(3.0)), r"needs 5 x and 4 y .* got 5 and 3"),
        (([0.0, 1.0, 3.0, 4.0, 5.0], np.arange(4.0)), r"tripcolor\(x, y, z\)"),
        (
            (np.array([[0.0, 1.0], [0.5, 1.5]]), np.zeros((2, 2))),
            r"pcolormesh\(X, Y, C\): the 2-D X is not a regular grid",
        ),
        ((np.arange(5.0),), "takes C or X, Y, C"),
        ((np.zeros((2, 2, 2)), np.arange(4.0)), "needs 1-D X and Y"),
    ],
)
def test_pcolormesh_rejects_a_grid_it_cannot_draw(args, match):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=match):
        ax.pcolormesh(*args, np.zeros((3, 4)))


def test_pcolormesh_rejects_bad_input():
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="shading='smooth'"):
        ax.pcolormesh(np.zeros((2, 2)), shading="smooth")
    with pytest.raises(ValueError, match=r"needs a 2-D C; got shape \(3,\)"):
        ax.pcolormesh(np.zeros(3))
    with pytest.raises(ValueError, match="NaN"):
        ax.pcolormesh(np.array([[0.0, np.nan]]))
    with pytest.raises(ValueError, match="NaN"):
        ax.pcolormesh(np.ma.masked_array([[1.0, 2.0]], mask=[[0, 1]]))
    with pytest.raises(ValueError, match="pcolormesh X contains NaN"):
        ax.pcolormesh(np.ma.masked_array([0.0, 1, 2], mask=[0, 1, 0]), [0, 1], [[1, 2]])
    with pytest.raises(ValueError, match="at least two centres"):
        ax.pcolormesh(np.zeros((1, 3)), shading="nearest")
    ax.imshow(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="at most one heatmap"):
        ax.pcolormesh(np.zeros((2, 2)))


def test_pcolormesh_warns_for_what_gle_cannot_draw():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning) as record:
        ax.pcolormesh(
            np.zeros((2, 2)),
            shading="gouraud",
            alpha=0.5,
            norm="log",
            colorizer="c",
            data={},
            antialiased=True,
            linewidth=2,
            edgecolors=np.array([0.0, 0.0, 0.0]),
        )
    messages = " | ".join(str(w.message) for w in record)
    assert "shading='gouraud') is drawn as shading='nearest'" in messages
    assert "pcolormesh(alpha=...) is ignored: a GLE colormap is opaque" in messages
    assert "pcolormesh(norm=...) is ignored: colours are mapped linearly" in messages
    assert "pcolormesh(colorizer=...) is ignored: pass cmap=" in messages
    assert "pcolormesh(data=...) is ignored: pass the arrays themselves" in messages
    assert "antialiased=True) is ignored" in messages
    assert "unsupported keyword(s): edgecolors, linewidth" in messages


def test_pcolormesh_takes_the_edgecolors_it_draws_without_a_warning(recwarn):
    ax = glp.figure().add_subplot(111)
    ax.pcolormesh(np.zeros((2, 2)), edgecolors="None", edgecolor="face")
    ax = glp.figure().add_subplot(111)
    ax.pcolormesh(np.zeros((2, 2)), shading="Flat")
    assert not recwarn.list


def test_pcolormesh_warns_when_the_limits_reach_beyond_the_mesh():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.pcolormesh([0.0, 1, 2, 3], [0.0, 1, 2], np.zeros((2, 3)))
    ax.plot([-0.5, 2], [0, 1])
    with pytest.warns(UserWarning, match=r"The x limits \(-0.5 to 3\) reach beyond"):
        _gle(fig)


def test_pcolormesh_inside_its_own_limits_does_not_warn(recwarn):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.pcolormesh([0.0, 1, 2, 3], [0.0, 1, 2], np.zeros((2, 3)))
    ax.set_xlim(0.5, 2.5)
    _gle(fig)
    assert not recwarn.list


def test_pcolormesh_warns_when_a_log_axis_cannot_draw_it():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.pcolormesh([1.0, 4, 7, 10], [0.0, 1, 2], np.zeros((2, 3)))
    ax.set_xscale("log")
    with pytest.warns(UserWarning, match=r"not drawn: on a log x axis .* x = -0.5"):
        _gle(fig)


def test_pcolormesh_mesh_takes_a_colorbar():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    hm = ax.pcolormesh(np.arange(4.0).reshape(2, 2), cmap="magma")
    fig.colorbar(hm, ax=ax)
    text, _ = _gle(fig)
    assert 'palette "gleplot_magma"' in text


def test_module_level_pcolormesh():
    glp.figure()
    glp.pcolormesh(np.zeros((2, 2)))
    assert glp.gca().heatmaps[0]["cells"] is True


# --------------------------------------------------------------------------- #
# contourf (bands)
# --------------------------------------------------------------------------- #


def _ramp_contourf(fig, *levels, **kwargs):
    """A plane z = x + y over a fine grid: every band edge fits."""
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 41)
    y = np.linspace(0, 2, 21)
    return ax, ax.contourf(x, y, np.add.outer(y, x), *levels, **kwargs)


def test_contourf_writes_bands_through_its_own_palette_sub():
    fig = glp.figure(data_prefix="t")
    ax, hm = _ramp_contourf(
        fig, [1, 2, 3, 4], cmap="gray", vmin=0, extend="min", pixels=(80, 40)
    )
    text, files = _gle(fig)

    assert hm is ax.heatmaps[0]
    assert hm["levels"] == [1.0, 2.0, 3.0, 4.0]
    assert hm["extend"] == "min"
    assert hm["extent"] == [0.0, 4.0, 0.0, 2.0]
    lines = text.splitlines()
    start = lines.index("sub gleplot_contourf1 z")
    assert lines[start : start + 9] == [
        "sub gleplot_contourf1 z",
        "   ! gleplot: contourf cmap gray extend min vmin 0 levels 1 2 3 4",
        "   if z < 1 then return gleplot_gray(0)",
        "   if z > 4 then return rgb(1, 1, 1)",
        "   local t = 0.375",
        "   if z > 2 then t = 0.625",
        "   if z > 3 then t = 0.875",
        "   return gleplot_gray(t)",
        "end sub",
    ]
    assert "sub gleplot_gray z" in lines  # the band sub calls it
    assert (
        '    colormap "t_heatmap1.z" 80 40 zmin 0 zmax 1 palette gleplot_contourf1'
        in lines
    )
    # One node spacing past the last node: GLE's colormap places node k of n
    # at xmin + k (xmax - xmin) / n.
    assert files["t_heatmap1.z"].splitlines()[:2] == [
        "! nx 41 ny 21 xmin 0 xmax 4.1 ymin 0 ymax 2.1",
        "! gleplot: nodes xmin 0 xmax 4 ymin 0 ymax 2",
    ]


@pytest.mark.parametrize(
    "extend, under, over",
    [
        ("neither", "rgb(1, 1, 1)", "rgb(1, 1, 1)"),
        ("max", "rgb(1, 1, 1)", "gleplot_viridis(1)"),
        ("both", "gleplot_viridis(0)", "gleplot_viridis(1)"),
    ],
)
def test_contourf_extend_fills_beyond_the_levels(extend, under, over):
    fig = glp.figure()
    _ramp_contourf(fig, [1, 2, 3], extend=extend)
    text, _ = _gle(fig)
    assert f"   if z < 1 then return {under}" in text
    assert f"   if z > 3 then return {over}" in text


@pytest.mark.parametrize(
    "zmin, zmax, levels, extend, want",
    [
        # matplotlib 3.11's contourf(...).levels for the same range.
        (-1, 1, None, "neither", [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1]),
        (0.13, 0.87, 5, "neither", [0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9]),
        (-3.2, 17.9, 7, "both", [-3, 0, 3, 6, 9, 12, 15]),
        (0, 9.5, 3, "max", [0, 2.5, 5, 7.5]),
    ],
)
def test_contourf_picks_levels_as_matplotlib_does(zmin, zmax, levels, extend, want):
    ax = glp.figure().add_subplot(111)
    Z = np.array([[zmin, zmax], [zmin, zmax]], dtype=float)
    with pytest.warns(UserWarning, match="smooth heatmap"):
        hm = ax.contourf(Z, levels=levels, extend=extend)
    np.testing.assert_allclose(hm["levels"], want, rtol=1e-12)


def test_contourf_on_z_alone_puts_the_nodes_on_the_indices():
    ax = glp.figure().add_subplot(111)
    hm = ax.contourf(np.zeros((3, 5)) + np.arange(5.0), 2)
    assert hm["extent"] == [0.0, 4.0, 0.0, 2.0]
    assert len(hm["levels"]) >= 2


def test_contourf_draws_a_coarse_grid_smooth_and_says_so():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.warns(UserWarning, match=r"smooth heatmap, not bands.*fewer pixels="):
        ax.contourf(np.add.outer(np.arange(4.0), np.arange(5.0)) ** 2, [0, 10, 20, 49])
    text, _ = _gle(fig)
    assert "   return gleplot_viridis((z-(0))/49)" in text
    assert "local t" not in text


def test_contourf_on_a_fine_grid_does_not_warn(recwarn):
    _ramp_contourf(glp.figure(), 5)
    assert not recwarn.list


@pytest.mark.parametrize(
    "args, kwargs, match",
    [
        ((np.zeros((3, 3)), 4), {"levels": 4}, "levels both as an argument"),
        ((np.zeros((3, 3)),), {"levels": [1.0]}, "at least two finite levels"),
        ((np.zeros((3, 3)),), {"levels": [2.0, 1.0]}, "levels must increase"),
        ((np.zeros((3, 3)),), {"levels": 0}, "levels=0; expected a whole number"),
        ((np.zeros((3, 3)),), {"levels": np.inf}, "levels=inf; expected"),
        ((np.zeros((3, 3)),), {"levels": "auto"}, "levels='auto'; expected"),
        (
            (np.zeros((3, 3)),),
            {"levels": [0, 1], "vmin": 0.10000001, "vmax": 0.10000002},
            "vmin < vmax",
        ),
        ((np.zeros((3, 3)),), {"extend": "up"}, "extend='up'"),
        ((np.zeros((3, 3)),), {"levels": [0, 1], "vmin": 2}, "vmin < vmax"),
        ((np.zeros((1, 3)),), {"levels": [0, 1]}, "two grid nodes"),
        ((np.full((2, 2), 3.0),), {}, "closer together than the 6"),
        ((np.array([[0.0, np.nan], [1, 2]]),), {}, "NaN"),
        ((np.ma.masked_array(np.eye(2), mask=np.eye(2)),), {}, "NaN"),
        (
            ([0.0, 1.0, 3.0], [0.0, 1.0], np.zeros((2, 3))),
            {},
            r"contourf requires uniformly spaced x.*tripcolor\(x, y, z\)",
        ),
    ],
)
def test_contourf_rejects_input_it_cannot_draw(args, kwargs, match):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=match):
        ax.contourf(*args, **kwargs)


def test_contourf_warns_for_what_gle_cannot_draw():
    fig = glp.figure()
    with pytest.warns(UserWarning) as record:
        _ramp_contourf(fig, 4, colors="k", alpha=0.5, hatches=["/"], zorder=2)
    messages = " | ".join(str(w.message) for w in record)
    assert "contourf(colors=...) is ignored" in messages
    assert "contourf(alpha=...) is ignored" in messages
    assert "contourf(hatches=...) is ignored" in messages
    assert "unsupported keyword(s): zorder" in messages


def test_contourf_counts_as_the_axes_heatmap():
    ax = glp.figure().add_subplot(111)
    ax.imshow(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="at most one heatmap"):
        ax.contourf(np.add.outer(np.arange(3.0), np.arange(3.0)), [0, 1, 4])


def test_contourf_warns_when_the_limits_reach_past_its_last_node():
    fig = glp.figure()
    ax, _ = _ramp_contourf(fig, 4)
    ax.set_xlim(-1, 5)
    with pytest.warns(UserWarning, match=r"x limits reach 5, beyond the contourf"):
        _gle(fig)


def test_contourf_colorbar_warns_it_shows_no_bands():
    """The bar spans the outer levels, the scale the bands are coloured on."""
    fig = glp.figure()
    _, hm = _ramp_contourf(fig, [0.5, 2, 5.5])
    with pytest.warns(UserWarning, match="not its bands"):
        fig.colorbar(hm)
    assert (hm["colorbar"]["zmin"], hm["colorbar"]["zmax"]) == (0.5, 5.5)


def test_module_level_contourf():
    glp.figure()
    x = np.linspace(0, 1, 30)
    glp.contourf(x, x, np.add.outer(x, x), 3)
    assert "levels" in glp.gca().heatmaps[0]


# --------------------------------------------------------------------------- #
# contour (grid)
# --------------------------------------------------------------------------- #


def test_contour_stores_dict_and_emits_blocks():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 5)
    y = np.linspace(0, 3, 4)
    Z = np.outer(y, x)
    ct = ax.contour(
        x,
        y,
        Z,
        levels=[2.0, 4.0, 6.0],
        colors="red",
        linewidths=2.0,
        clabel=True,
        clabel_fmt="fix 2",
    )

    assert ct is ax.contours[0]
    assert ct["type"] == "contour"
    assert ct["source"] == "grid"
    assert ct["extent"] == [0.0, 4.0, 0.0, 3.0]
    assert ct["levels"] == [2.0, 4.0, 6.0]
    assert ct["color"] == "RED"
    assert ct["clabel"] is True
    assert ct["clabel_fmt"] == "fix 2"
    assert ct["data_file"] == "t_contour1.z"

    text, files = _gle(fig)
    assert "begin contour" in text
    assert '   data "t_contour1.z"' in text
    assert "   values 2 4 6" in text
    assert 'data "t_contour1-cdata.dat" d1=c1,c2' in text
    assert "d1 line color RED" in text
    # clabel: sub + call
    assert "sub gleplot_contour_labels" in text
    assert 'gleplot_contour_labels file "t_contour1-clabels.dat" format "fix 2"' in text
    assert "t_contour1.z" in files


def test_contour_non_uniform_x_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    x = np.array([0.0, 1.0, 3.0, 4.0])  # non-uniform
    y = np.linspace(0, 1, 3)
    with pytest.raises(ValueError, match="uniformly spaced"):
        ax.contour(x, y, np.zeros((3, 4)))


# --------------------------------------------------------------------------- #
# contour with matplotlib meshgrid (2-D X, Y) input
# --------------------------------------------------------------------------- #


def _peaks(x, y):
    X, Y = np.meshgrid(x, y)
    return np.sin(X) * np.cos(Y)


def test_contour_meshgrid_matches_1d_input():
    """The whole point: np.meshgrid input must be the same figure as 1-D input."""
    x = np.linspace(0, 3, 7)
    y = np.linspace(-1, 2, 5)
    Z = _peaks(x, y)
    X, Y = np.meshgrid(x, y)

    fig_1d = glp.figure(data_prefix="t")
    ct_1d = fig_1d.add_subplot(111).contour(x, y, Z, levels=[0.0, 0.5])
    fig_mesh = glp.figure(data_prefix="t")
    ct_mesh = fig_mesh.add_subplot(111).contour(X, Y, Z, levels=[0.0, 0.5])

    assert ct_mesh["extent"] == ct_1d["extent"]
    assert ct_mesh["levels"] == ct_1d["levels"]
    np.testing.assert_array_equal(ct_mesh["z"], ct_1d["z"])
    text_mesh, files_mesh = _gle(fig_mesh)
    text_1d, files_1d = _gle(fig_1d)
    assert text_mesh == text_1d
    assert files_mesh == files_1d


def test_contour_meshgrid_x_only():
    """A 2-D X with a 1-D y (and vice versa) is reduced independently."""
    x = np.linspace(0, 3, 4)
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y)
    Z = np.zeros((3, 4))

    ax = glp.figure(data_prefix="t").add_subplot(111)
    assert ax.contour(X, y, Z)["extent"] == [0.0, 3.0, 0.0, 1.0]
    assert ax.contour(x, Y, Z)["extent"] == [0.0, 3.0, 0.0, 1.0]


def test_contour_meshgrid_shape_mismatch_raises():
    x = np.linspace(0, 3, 4)
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y)  # (3, 4)
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="must match Z"):
        ax.contour(X, Y, np.zeros((4, 3)))


def test_contour_irregular_meshgrid_raises_and_points_at_tricontour():
    x = np.linspace(0, 3, 4)
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y)
    X = X.copy()
    X[1, 2] += 0.5  # a genuinely irregular (curvilinear) grid
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="not a regular grid"):
        ax.contour(X, Y, np.zeros((3, 4)))
    with pytest.raises(ValueError, match="tricontour"):
        ax.contour(X, Y, np.zeros((3, 4)))


def test_contour_ij_indexed_meshgrid_raises_with_a_fix():
    """indexing='ij' is transposed, not irregular; say so rather than misdraw."""
    x = np.linspace(0, 3, 4)
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y, indexing="ij")  # (4, 3)
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="indexing='ij'"):
        ax.contour(X, Y, np.zeros((4, 3)))


def test_contour_meshgrid_still_requires_uniform_spacing():
    x = np.array([0.0, 1.0, 3.0, 4.0])  # non-uniform
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y)
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match="uniformly spaced"):
        ax.contour(X, Y, np.zeros((3, 4)))


def test_contour_meshgrid_tolerates_rounding():
    """A grid built by arithmetic carries float noise; that is still regular."""
    x = np.linspace(0, 3, 4)
    y = np.linspace(0, 1, 3)
    X, Y = np.meshgrid(x, y)
    X = X + np.array([[0.0, 1e-13, 0.0, 0.0]] * 3)
    ax = glp.figure(data_prefix="t").add_subplot(111)
    assert ax.contour(X, Y, np.zeros((3, 4)))["extent"] == [0.0, 3.0, 0.0, 1.0]


def test_contour_int_levels_resolves_to_explicit_list():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    Z = np.arange(12, dtype=float).reshape(3, 4)  # min 0, max 11
    ct = ax.contour(Z, levels=3)
    # 3 levels evenly spaced strictly inside (0, 11).
    assert ct["levels"] == pytest.approx([2.75, 5.5, 8.25])
    text, _ = _gle(fig)
    assert "values 2.75 5.5 8.25" in text


def test_contour_default_levels_omits_values():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.contour(np.zeros((3, 4)))
    assert ax.contours[0]["levels"] is None
    text, _ = _gle(fig)
    block = text.split("begin contour", 1)[1].split("end contour", 1)[0]
    assert "values" not in block


# --------------------------------------------------------------------------- #
# tripcolor / tricontour (scattered)
# --------------------------------------------------------------------------- #


def test_tripcolor_stores_points_and_fitz():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([0.0, 1.0, 2.0, 3.0])
    z = np.array([1.0, 2.0, 3.0, 4.0])
    hm = ax.tripcolor(x, y, z, gridsize=(5, 5), extent=(0, 4, 0, 4), cmap="magma")

    assert hm["source"] == "points"
    assert hm["gridsize"] == [5, 5]
    assert hm["data_file"] == "t_points1.dat"
    assert np.allclose(hm["zpts"], z)

    text, files = _gle(fig)
    assert "begin fitz" in text
    assert '   data "t_points1.dat"' in text
    assert "   x from 0 to 4 step 1" in text
    assert "   y from 0 to 4 step 1" in text
    # points sidecar: raw triples, no header.
    pts = files["t_points1.dat"]
    assert pts.splitlines()[0] == "0 0 1"
    # colormap references the fitz-generated .z.
    assert 'colormap "t_points1.z" 200 200' in text


def test_tricontour_stores_ncontour_and_emits_contour_on_fitz_z():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 6)
    y = np.linspace(0, 4, 6)
    z = x + y
    ct = ax.tricontour(
        x, y, z, gridsize=(5, 5), extent=(0, 4, 0, 4), ncontour=4, levels=[2.0, 4.0]
    )

    assert ct["source"] == "points"
    assert ct["ncontour"] == 4
    assert ct["data_file"] == "t_points1.dat"

    text, _ = _gle(fig)
    assert "begin fitz" in text
    assert "   ncontour 4" in text
    assert '   data "t_points1.z"' in text  # contour reads fitz output
    assert 'data "t_points1-cdata.dat"' in text


# --------------------------------------------------------------------------- #
# colorbar
# --------------------------------------------------------------------------- #


def test_colorbar_attaches_to_heatmap_and_emits_call():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(
        np.arange(6.0).reshape(2, 3),
        extent=(0, 3, 0, 2),
        cmap="viridis",
        vmin=0,
        vmax=10,
    )
    cb = fig.colorbar(label="χ", format="fix 1", nticks=5, width=0.4, sep=0.5)

    assert ax.heatmaps[0]["colorbar"] is cb
    assert cb["zmin"] == 0.0 and cb["zmax"] == 10.0
    assert cb["zstep"] == 2.0  # (10-0)/5
    assert cb["width"] == 0.4 and cb["sep"] == 0.5

    text, _ = _gle(fig)
    assert "sub gleplot_colorbar_v" in text
    assert "amove xg(xgmax)+0.5 yg(ygmin)" in text
    assert (
        'gleplot_colorbar_v zmin 0 zmax 10 zstep 2 palette "gleplot_viridis" '
        'wd 0.4 hi yg(ygmax)-yg(ygmin) format "fix 1" label "χ"'
    ) in text


def test_colorbar_without_vmin_uses_data_range():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.array([[1.0, 2.0], [3.0, 7.0]]))
    cb = fig.colorbar()
    assert cb["zmin"] == 1.0 and cb["zmax"] == 7.0


def test_colorbar_no_heatmap_raises():
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2], [1, 2])
    with pytest.raises(ValueError, match="requires a heatmap"):
        fig.colorbar()


def test_colorbar_ambiguous_raises():
    fig, axes = glp.subplots(1, 2)
    axes[0].imshow(np.zeros((2, 2)))
    axes[1].imshow(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="ambiguous"):
        fig.colorbar()


def _two_heatmaps():
    fig, (a, b) = glp.subplots(1, 2, figsize=(10, 4), data_prefix="t")
    ha = a.imshow(np.array([[0.0, 1.0], [2.0, 3.0]]), cmap="viridis")
    hb = b.imshow(np.array([[10.0, 20.0], [30.0, 50.0]]), cmap="magma")
    return fig, a, b, ha, hb


def _placements(text):
    """``(x, y, w, h)`` of each graph, from its ``amove`` + ``size`` pair."""
    import re

    pairs = re.findall(
        r"^amove ([-0-9.e]+) ([-0-9.e]+)\nbegin graph\n\s+size ([-0-9.e]+) "
        r"([-0-9.e]+)",
        text,
        re.M,
    )
    return [tuple(float(v) for v in p) for p in pairs]


def test_colorbar_per_axes_gives_each_heatmap_its_own_bar():
    fig, a, b, ha, hb = _two_heatmaps()
    ca = fig.colorbar(ha, ax=a, label="a")
    cb = fig.colorbar(hb, label="b")

    assert ha["colorbar"] is ca and hb["colorbar"] is cb
    assert (ca["zmin"], ca["zmax"]) == (0.0, 3.0)
    assert (cb["zmin"], cb["zmax"]) == (10.0, 50.0)
    text, _ = _gle(fig)
    assert text.count("sub gleplot_colorbar_v") == 1
    assert 'palette "gleplot_viridis" wd 0.5' in text
    assert 'palette "gleplot_magma" wd 0.5' in text


def test_colorbar_ax_alone_picks_that_axes_heatmap():
    fig, a, b, ha, hb = _two_heatmaps()
    fig.colorbar(ax=b)
    assert hb["colorbar"] is not None and ha.get("colorbar") is None


def test_a_bar_beside_an_inner_column_widens_the_gap_after_it():
    fig, a, b, ha, hb = _two_heatmaps()
    (ax0, _, w0, _), (bx0, _, _, _) = _placements(_gle(fig)[0])
    plain_gap = bx0 - (ax0 + w0)

    fig.colorbar(ha)
    (ax1, _, w1, _), (bx1, _, _, _) = _placements(_gle(fig)[0])
    reserved, _below = fig._axes_colorbar_reserved_cm(a)

    assert bx1 - (ax1 + w1) == pytest.approx(plain_gap + reserved, abs=1e-4)


def test_horizontal_colorbar_is_drawn_below_and_reserves_the_bottom():
    fig = glp.figure(figsize=(6, 4), data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.array([[0.0, 1.0], [2.0, 4.0]]), cmap="viridis")
    ((_, y0, _, h0),) = _placements(_gle(fig)[0])

    cb = fig.colorbar(orientation="horizontal", label="z", width=0.4, sep=1.5)
    text, _ = _gle(fig)
    ((_, y1, _, h1),) = _placements(text)

    assert cb["orientation"] == "horizontal"
    assert "sub gleplot_colorbar_h" in text
    assert "sub gleplot_colorbar_v" not in text
    assert "amove xg(xgmin) yg(ygmin)-1.5\n" in text
    assert (
        'gleplot_colorbar_h zmin 0 zmax 4 zstep 0.8 palette "gleplot_viridis" '
        'wd xg(xgmax)-xg(xgmin) hi 0.4 format "fix 1" label "z"'
    ) in text
    _right, below = fig._axes_colorbar_reserved_cm(ax)
    assert y1 >= below - 1e-4
    assert y1 > y0 and h1 < h0


def test_horizontal_colorbar_default_sep_clears_the_x_decoration():
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).imshow(np.zeros((2, 2)) + [[0.0], [1.0]])
    assert fig.colorbar(orientation="horizontal")["sep"] == 1.57  # 3 hei + 0.3
    assert fig.colorbar(orientation="vertical")["sep"] == 0.3
    assert "orientation" not in fig.axes_list[0].heatmaps[0]["colorbar"]


def test_colorbar_rejects_bad_arguments():
    fig, a, b, ha, hb = _two_heatmaps()
    with pytest.raises(ValueError, match="orientation must be"):
        fig.colorbar(ha, orientation="diagonal")
    with pytest.raises(TypeError, match="mappable must be"):
        fig.colorbar("a label")
    with pytest.raises(TypeError, match="ax must be one Axes"):
        fig.colorbar(ha, ax=[a, b])
    with pytest.raises(ValueError, match="ax must be the axes holding"):
        fig.colorbar(ha, ax=b)
    other, oax = glp.subplots()
    with pytest.raises(ValueError, match="not a heatmap on this figure"):
        other.colorbar(ha)
    with pytest.raises(ValueError, match="not an axes of this figure"):
        other.colorbar(ax=a)
    oax.plot([0, 1], [0, 1])
    with pytest.raises(ValueError, match="needs a heatmap on ax"):
        other.colorbar(ax=oax)


def test_colorbar_cax_warns_and_draws_beside_the_heatmap():
    fig, a, b, ha, hb = _two_heatmaps()
    with pytest.warns(UserWarning, match="cax is not supported"):
        fig.colorbar(ha, b)
    assert ha["colorbar"] is not None and hb.get("colorbar") is None


# --------------------------------------------------------------------------- #
# autoscale from extent, module-level wrappers, palettes module
# --------------------------------------------------------------------------- #


def test_extent_drives_autoscale():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.imshow(np.zeros((4, 5)), extent=(2, 12, 1, 9))
    _gle(fig)  # triggers limit derivation
    assert ax.xmin == 2.0 and ax.xmax == 12.0
    assert ax.ymin == 1.0 and ax.ymax == 9.0


def test_module_level_wrappers():
    glp.figure(data_prefix="t")
    glp.imshow(np.zeros((2, 2)), cmap="viridis")
    glp.colorbar(label="v")
    ax = glp.gca()
    assert ax.heatmaps and ax.heatmaps[0]["colorbar"] is not None


def test_palette_sub_text_is_deterministic():
    a = palettes.palette_sub_text("viridis")
    b = palettes.palette_sub_text("viridis")
    assert a == b
    assert a.startswith("sub gleplot_viridis z")
    assert a.rstrip().endswith("end sub")
    assert palettes.palette_sub_text("gray") is None
    assert palettes.palette_sub_text("rainbow") is None


# --------------------------------------------------------------------------- #
# invalid-input guards (GLE cannot represent these; reject early with a clear
# ValueError rather than emit a broken sidecar / .gle that aborts at compile)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_imshow_nonfinite_z_raises(bad):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    Z = np.arange(12.0).reshape(3, 4)
    Z[1, 1] = bad
    with pytest.raises(ValueError, match="NaN or infinite"):
        ax.imshow(Z)


def test_contour_nonfinite_z_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    Z = np.arange(12.0).reshape(3, 4)
    Z[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN or infinite"):
        ax.contour(Z)


def test_tripcolor_nonfinite_z_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="NaN or infinite"):
        ax.tripcolor(
            [0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 0.0, 1.0], [0.0, np.nan, 1.0, 2.0]
        )


def test_imshow_reversed_extent_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="xmin < xmax"):
        ax.imshow(np.arange(12.0).reshape(3, 4), extent=(10, 0, 8, 0))


def test_imshow_degenerate_extent_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="ascending"):
        ax.imshow(np.arange(12.0).reshape(3, 4), extent=(0, 0, 0, 5))


def test_contour_levels_all_outside_range_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    Z = np.arange(12.0).reshape(3, 4)  # range [0, 11]
    with pytest.raises(ValueError, match="outside the data range"):
        ax.contour(Z, levels=[100, 200])


def test_contour_levels_partially_in_range_ok():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    Z = np.arange(12.0).reshape(3, 4)
    ct = ax.contour(Z, levels=[5, 200])  # 5 is in range -> fine
    assert ct["levels"] == [5.0, 200.0]


def test_colorbar_sub_guards_degenerate_range():
    """The colorbar sub must guard zmax == zmin (constant field) so it does not
    divide by zero and abort the render."""
    text = palettes.colorbar_sub_text()
    assert "if zmax = zmin then" in text


# --------------------------------------------------------------------------- #
# G8: unique per-figure / cross-figure contour+fitz sidecar stems
# (GLEstudio SPEC 9.1/10.8 -- see gleplot.compiler.remove_generated_intermediates
# and gleplot.figure.Figure.savefig for the paired compiled-output cleanup,
# exercised end-to-end with a real GLE binary in
# tests/integration/test_intermediate_cleanup.py).
# --------------------------------------------------------------------------- #


def test_two_contours_one_figure_get_distinct_stems():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ct1 = ax.contour(np.arange(12.0).reshape(3, 4), levels=[2, 4])
    ct2 = ax.contour(np.arange(12.0).reshape(3, 4) + 1, levels=[2, 4])
    assert ct1["data_file"] == "t_contour1.z"
    assert ct2["data_file"] == "t_contour2.z"


def test_heatmap_and_contour_share_kind_specific_counters():
    """A heatmap and a contour in the same figure use independent 'heatmap'/
    'contour' counters, so both legitimately start at 1 without colliding
    (different kind tokens in the name)."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    hm = ax.imshow(np.arange(12.0).reshape(3, 4))
    ct = ax.contour(np.arange(12.0).reshape(3, 4), levels=[2, 4])
    assert hm["data_file"] == "t_heatmap1.z"
    assert ct["data_file"] == "t_contour1.z"


def test_custom_prefix_figures_keep_independent_per_figure_counters():
    """A custom data_prefix is the caller's existing opt-in to predictable,
    figure-local numbering (same contract as plain '<prefix>_N.dat' series):
    two figures with different prefixes both legitimately start at 1."""
    fig1 = glp.figure(data_prefix="alpha")
    ct1 = fig1.add_subplot(111).contour(np.arange(12.0).reshape(3, 4), levels=[2, 4])
    fig2 = glp.figure(data_prefix="beta")
    ct2 = fig2.add_subplot(111).contour(np.arange(12.0).reshape(3, 4), levels=[2, 4])
    assert ct1["data_file"] == "alpha_contour1.z"
    assert ct2["data_file"] == "beta_contour1.z"


def test_default_prefix_figures_do_not_collide_across_figures():
    """Two figures left on the default prefix (no data_prefix given) must not
    both reserve 'data_contour1.z' if compiled into the same directory --
    the G8 cross-figure uniqueness requirement. Resets the shared globals
    first so the assertion is independent of what ran earlier in the
    session (mirrors tests/parser/test_fixed_point.py's counter reset)."""
    _axes_module._global_data_file_counter = 0
    _axes_module._global_sidecar_counters.clear()
    try:
        fig1 = glp.figure()
        ct1 = fig1.add_subplot(111).contour(
            np.arange(12.0).reshape(3, 4), levels=[2, 4]
        )
        fig2 = glp.figure()
        ct2 = fig2.add_subplot(111).contour(
            np.arange(12.0).reshape(3, 4), levels=[2, 4]
        )
        assert ct1["data_file"] == "data_contour1.z"
        assert ct2["data_file"] == "data_contour2.z"
    finally:
        _axes_module._global_data_file_counter = 0
        _axes_module._global_sidecar_counters.clear()


def test_sidecar_counters_round_trip_and_avoid_renumbering_collision():
    """to_dict/from_dict preserve the sidecar counters, so a contour added to
    a reloaded figure keeps counting forward instead of restarting at 1 and
    landing on an already-used name."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(12.0).reshape(3, 4), levels=[2, 4])
    d = fig.to_dict()
    assert d["figure"]["sidecar_counters"] == {"contour": 1}

    restored = glp.Figure.from_dict(d)
    ct2 = restored.axes_list[0].contour(
        np.arange(12.0).reshape(3, 4) + 1, levels=[2, 4]
    )
    assert ct2["data_file"] == "t_contour2.z"

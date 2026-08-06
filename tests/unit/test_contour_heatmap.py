"""Unit tests for contour/heatmap (imshow-style) support: stored dicts + GLE.

Mirrors the ``tests/unit/test_plotting.py`` style -- assert the object-model
dicts each API call stores AND substrings of the generated GLE. Covers
``imshow``, ``contour``, ``tripcolor``, ``tricontour``, ``Figure.colorbar``,
palette emission, the ``.z``/points sidecars, and the one-heatmap-per-axes rule.
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


def test_unknown_cmap_raises():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="Unknown cmap"):
        ax.imshow(np.zeros((2, 2)), cmap="turbo")


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

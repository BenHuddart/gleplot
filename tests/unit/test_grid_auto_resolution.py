"""Write-time resolution of a reference-backed grid series' autos (G13).

GLEstudio SPEC 14.5. The scripting API bakes a heatmap's/contour's ``extent``
-- and a colorbar's ``zmin``/``zmax``/``zstep`` -- at call time, from the
arrays it is handed. A **reference-backed** grid series has no arrays at call
time: they arrive per write from a
:class:`~gleplot.sources.DataProvider`, and a value baked from an earlier
write would go stale the moment a cell changed. So those become *auto* states
on such a series, and each write turns them back into numbers from the data
that write resolved.

Three things are under test here:

1. **Auto extent**, in both grid mode (``(0, nx, 0, ny)``) and points mode
   (the sample bounds) -- the same defaults ``imshow``/``tripcolor`` bake --
   including that it re-flows when the provider's data changes and that the
   document itself is never mutated by a write.
2. **Auto colorbar range**: ``Figure.colorbar()`` on a reference-backed
   heatmap no longer reads arrays it does not have (it used to raise a numpy
   ``TypeError`` from ``nanmin(None)``); with explicit ``vmin``/``vmax`` it
   proceeds as before, otherwise it records the auto marker and the write
   computes the range.
3. **Nothing raises at write time**: arrays that cannot produce an auto value
   skip the series with a structured record, exactly like a dangling
   reference.
"""

import copy
import warnings

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure
from gleplot.series import ContourSeries, HeatmapSeries
from gleplot.sources import DictDataProvider, GridRef, TableData
from gleplot.writer import (
    COLORBAR_AUTO_RANGE,
    COLORBAR_NTICKS,
    apply_grid_write_time_autos,
    auto_colorbar_range,
    auto_extent,
    resolve_figure,
)

# -- helpers ------------------------------------------------------------------


def _provider(**tables):
    return DictDataProvider({k: TableData.from_mapping(v) for k, v in tables.items()})


def _figure():
    glp.close()
    fig = glp.figure(figsize=(5, 4), data_prefix="g13")
    return fig, fig.add_subplot(111)


def _heatmap_grid(ax, table_id="t1", keys=("c0", "c1", "c2"), extent=None, **over):
    """A grid-mode heatmap backed by a GridRef, ``extent`` auto by default."""
    fields = dict(
        type="heatmap",
        source="grid",
        z=None,
        x=None,
        y=None,
        zpts=None,
        extent=extent,
        origin="lower",
        cmap="gray",
        vmin=None,
        vmax=None,
        interpolation="nearest",
        pixels=[64, 64],
        invert=False,
        gridsize=None,
        ncontour=None,
        label=None,
        data_file="g13_heatmap1.z",
        data_source=GridRef(table_id, {"z": list(keys)}),
        colorbar=None,
    )
    fields.update(over)
    hm = HeatmapSeries(**fields)
    ax.heatmaps.append(hm)
    return hm


def _heatmap_points(ax, table_id="t1", extent=None, **over):
    """A points-mode heatmap backed by a GridRef, ``extent`` auto by default."""
    fields = dict(
        type="heatmap",
        source="points",
        z=None,
        x=None,
        y=None,
        zpts=None,
        extent=extent,
        origin="lower",
        cmap="gray",
        vmin=None,
        vmax=None,
        interpolation="nearest",
        pixels=[64, 64],
        invert=False,
        gridsize=[8, 8],
        ncontour=None,
        label=None,
        data_file="g13_points1.dat",
        data_source=GridRef(table_id, {"x": "px", "y": "py", "zpts": "pz"}),
        colorbar=None,
    )
    fields.update(over)
    hm = HeatmapSeries(**fields)
    ax.heatmaps.append(hm)
    return hm


def _contour_grid(ax, table_id="t1", keys=("c0", "c1", "c2"), extent=None, **over):
    fields = dict(
        type="contour",
        source="grid",
        z=None,
        x=None,
        y=None,
        zpts=None,
        extent=extent,
        levels=None,
        color="BLACK",
        linewidth=1.0,
        linestyle=None,
        clabel=False,
        clabel_fmt="fix 1",
        gridsize=None,
        ncontour=None,
        label=None,
        data_file="g13_contour1.z",
        data_source=GridRef(table_id, {"z": list(keys)}),
    )
    fields.update(over)
    ct = ContourSeries(**fields)
    ax.contours.append(ct)
    return ct


def _contour_points(ax, table_id="t1", extent=None, **over):
    fields = dict(
        type="contour",
        source="points",
        z=None,
        x=None,
        y=None,
        zpts=None,
        extent=extent,
        levels=None,
        color="BLACK",
        linewidth=1.0,
        linestyle=None,
        clabel=False,
        clabel_fmt="fix 1",
        gridsize=[8, 8],
        ncontour=2,
        label=None,
        data_file="g13_cpoints1.dat",
        data_source=GridRef(table_id, {"x": "px", "y": "py", "zpts": "pz"}),
    )
    fields.update(over)
    ct = ContourSeries(**fields)
    ax.contours.append(ct)
    return ct


#: A 2-row x 3-column grid table: the resolved z is (ny=2, nx=3).
_GRID_TABLE = dict(c0=[1.0, 4.0], c1=[2.0, 5.0], c2=[3.0, 6.0])

#: Scattered samples spanning x in [2, 8] and y in [-1, 3].
_POINTS_TABLE = dict(
    px=[2.0, 5.0, 8.0, 4.0],
    py=[-1.0, 0.0, 3.0, 1.0],
    pz=[10.0, 20.0, 30.0, 40.0],
)


def _resolved(fig, provider):
    """``{(attr, index): resolved series}`` for one resolution pass."""
    resolution = resolve_figure(fig, provider)
    out = {}
    for ax in fig.axes_list:
        for attr in ("heatmaps", "contours"):
            for index, series in enumerate(getattr(ax, attr)):
                out[(attr, index)] = resolution.data(series)
    return out, resolution


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


# -- (a) auto extent, grid mode ------------------------------------------------


def test_grid_mode_auto_extent_is_zero_to_nx_by_zero_to_ny():
    """The same default ``Axes.imshow`` bakes: index space over the grid."""
    fig, ax = _figure()
    hm = _heatmap_grid(ax)

    resolved, resolution = _resolved(fig, _provider(t1=_GRID_TABLE))

    assert resolution.warnings == []
    # 2 rows x 3 stacked columns -> (ny=2, nx=3) -> (0, 3, 0, 2).
    assert resolved[("heatmaps", 0)]["extent"] == [0.0, 3.0, 0.0, 2.0]
    # The document keeps its auto state; only the write's copy is filled.
    assert hm["extent"] is None


def test_grid_mode_auto_extent_matches_what_imshow_would_have_baked():
    """The auto value is the creation API's default, not a lookalike."""
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    baked_fig, baked_ax = _figure()
    baked = baked_ax.imshow(z)

    fig, ax = _figure()
    _heatmap_grid(ax)
    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE))

    assert resolved[("heatmaps", 0)]["extent"] == baked["extent"]
    assert baked_fig is not fig


def test_grid_mode_auto_extent_reaches_the_z_sidecar_header_and_the_axis_limits():
    fig, ax = _figure()
    _heatmap_grid(ax)

    text, files = fig._generate_gle_with_files(data_provider=_provider(t1=_GRID_TABLE))

    assert fig.source_warnings == []
    assert files["g13_heatmap1.z"] == (
        "! nx 3 ny 2 xmin 0 xmax 4.5 ymin 0 ymax 4\n"
        "! gleplot: nodes xmin 0 xmax 3 ymin 0 ymax 2\n1 2 3\n4 5 6\n"
    )
    # Autoscale saw the resolved extent, so the graph window spans it.
    assert "xaxis min 0 max 3" in text
    assert "yaxis min 0 max 2" in text


def test_a_provider_data_change_reflows_into_the_grid_extent():
    """The staleness fix: a table that grew a row re-flows on the next write."""
    fig, ax = _figure()
    _heatmap_grid(ax)

    first, _ = _resolved(fig, _provider(t1=_GRID_TABLE))
    grown = {k: list(v) + [v[-1] + 1.0] for k, v in _GRID_TABLE.items()}
    second, _ = _resolved(fig, _provider(t1=grown))

    assert first[("heatmaps", 0)]["extent"] == [0.0, 3.0, 0.0, 2.0]
    assert second[("heatmaps", 0)]["extent"] == [0.0, 3.0, 0.0, 3.0]


def test_contour_grid_mode_gets_the_same_auto_extent():
    fig, ax = _figure()
    _contour_grid(ax)

    resolved, resolution = _resolved(fig, _provider(t1=_GRID_TABLE))

    assert resolution.warnings == []
    assert resolved[("contours", 0)]["extent"] == [0.0, 3.0, 0.0, 2.0]


# -- (a) auto extent, points mode ---------------------------------------------


def test_points_mode_auto_extent_is_the_sample_bounds():
    """The same default ``Axes.tripcolor``/``tricontour`` bake."""
    fig, ax = _figure()
    hm = _heatmap_points(ax)

    resolved, resolution = _resolved(fig, _provider(t1=_POINTS_TABLE))

    assert resolution.warnings == []
    assert resolved[("heatmaps", 0)]["extent"] == [2.0, 8.0, -1.0, 3.0]
    assert hm["extent"] is None


def test_points_mode_auto_extent_matches_what_tripcolor_would_have_baked():
    baked_fig, baked_ax = _figure()
    baked = baked_ax.tripcolor(
        _POINTS_TABLE["px"],
        _POINTS_TABLE["py"],
        _POINTS_TABLE["pz"],
        gridsize=(8, 8),
    )

    fig, ax = _figure()
    _heatmap_points(ax)
    resolved, _ = _resolved(fig, _provider(t1=_POINTS_TABLE))

    assert resolved[("heatmaps", 0)]["extent"] == baked["extent"]
    assert baked_fig is not fig


def test_points_mode_auto_extent_reaches_the_fitz_block():
    fig, ax = _figure()
    _heatmap_points(ax)

    text, files = fig._generate_gle_with_files(
        data_provider=_provider(t1=_POINTS_TABLE)
    )

    assert fig.source_warnings == []
    assert "g13_points1.dat" in files
    assert "x from 2 to 8" in text
    assert "y from -1 to 3" in text


def test_a_provider_data_change_reflows_into_the_points_extent():
    fig, ax = _figure()
    _heatmap_points(ax)

    first, _ = _resolved(fig, _provider(t1=_POINTS_TABLE))
    moved = copy.deepcopy(_POINTS_TABLE)
    moved["px"][2] = 20.0
    second, _ = _resolved(fig, _provider(t1=moved))

    assert first[("heatmaps", 0)]["extent"] == [2.0, 8.0, -1.0, 3.0]
    assert second[("heatmaps", 0)]["extent"] == [2.0, 20.0, -1.0, 3.0]


def test_contour_points_mode_gets_the_same_auto_extent():
    fig, ax = _figure()
    _contour_points(ax)

    resolved, resolution = _resolved(fig, _provider(t1=_POINTS_TABLE))

    assert resolution.warnings == []
    assert resolved[("contours", 0)]["extent"] == [2.0, 8.0, -1.0, 3.0]


# -- (a) an explicit extent is never recomputed --------------------------------


def test_an_explicit_extent_on_a_reference_backed_series_is_left_alone():
    """ "Explicit wizard values behave like any panel edit" (SPEC 14.5)."""
    fig, ax = _figure()
    _heatmap_grid(ax, extent=[-5.0, 5.0, -1.0, 1.0])
    _contour_points(ax, table_id="t2", extent=[0.0, 100.0, 0.0, 50.0])

    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE, t2=_POINTS_TABLE))

    assert resolved[("heatmaps", 0)]["extent"] == [-5.0, 5.0, -1.0, 1.0]
    assert resolved[("contours", 0)]["extent"] == [0.0, 100.0, 0.0, 50.0]


def test_an_inline_grid_series_is_untouched_by_the_auto_path():
    """Only a reference-backed series has autos; a baked one is emitted as-is."""
    fig, ax = _figure()
    hm = ax.imshow(np.arange(6, dtype=float).reshape(2, 3), extent=(1, 4, 2, 6))

    resolved, resolution = _resolved(fig, _provider())

    assert resolution.warnings == []
    # Recorded as ITSELF (no copy) -- the inline fast path.
    assert resolved[("heatmaps", 0)] is hm
    assert hm["extent"] == [1.0, 4.0, 2.0, 6.0]


# -- (a) unusable data skips rather than raises --------------------------------


def test_an_empty_grid_skips_the_series_with_a_structured_record():
    fig, ax = _figure()
    _heatmap_grid(ax, keys=("c0",))

    resolved, resolution = _resolved(fig, _provider(t1=dict(c0=[])))

    assert resolved[("heatmaps", 0)] is None
    assert [w.reason for w in resolution.warnings] == ["unusable-data"]
    record = resolution.warnings[0]
    assert record.series_id == "axes[0].heatmaps[0]"
    assert record.table_id == "t1"
    assert "cannot be plotted" in str(record)


def test_points_constant_in_y_skip_rather_than_emit_a_degenerate_extent():
    """GLE needs ymin < ymax; a flat sample set cannot supply one."""
    fig, ax = _figure()
    _heatmap_points(ax)

    flat = dict(px=[1.0, 2.0, 3.0], py=[7.0, 7.0, 7.0], pz=[1.0, 2.0, 3.0])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text, files = fig._generate_gle_with_files(data_provider=_provider(t1=flat))

    assert [w.reason for w in fig.source_warnings] == ["unusable-data"]
    assert files == {}
    assert "colormap" not in text
    # Still a valid script -- nothing raised.
    assert "begin graph" in text


def test_a_degenerate_auto_extent_does_not_raise_from_savefig(tmp_path):
    fig, ax = _figure()
    _heatmap_points(ax)
    flat = dict(px=[1.0, 1.0, 1.0], py=[1.0, 2.0, 3.0], pz=[1.0, 2.0, 3.0])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig.savefig_gle(str(tmp_path / "out.gle"), data_provider=_provider(t1=flat))

    assert (tmp_path / "out.gle").exists()
    assert [w.reason for w in fig.source_warnings] == ["unusable-data"]


# -- the in-place applier's contract -------------------------------------------


def test_apply_grid_write_time_autos_names_which_auto_it_could_not_compute():
    """Its return value is the diagnostic: ``None`` on success, else which."""
    ok = HeatmapSeries(
        type="heatmap",
        source="grid",
        z=np.array([[1.0, 2.0], [3.0, 4.0]]),
        x=None,
        y=None,
        zpts=None,
        extent=None,
        origin="lower",
        cmap="gray",
        vmin=None,
        vmax=None,
        interpolation="nearest",
        pixels=[64, 64],
        invert=False,
        gridsize=None,
        ncontour=None,
        label=None,
        data_file="x.z",
        colorbar={
            "label": None,
            "format": "fix 1",
            "width": 0.5,
            "sep": 0.3,
            "zmin": None,
            "zmax": None,
            "zstep": None,
            COLORBAR_AUTO_RANGE: True,
            COLORBAR_NTICKS: 5,
        },
    )
    assert apply_grid_write_time_autos(ok) is None
    assert ok["extent"] == [0.0, 2.0, 0.0, 2.0]
    assert ok["colorbar"]["zmax"] == 4.0

    no_extent = ok.copy()
    no_extent["extent"] = None
    no_extent["z"] = None
    assert apply_grid_write_time_autos(no_extent) == "extent"

    no_range = ok.copy()
    no_range["extent"] = [0.0, 2.0, 0.0, 2.0]
    no_range["z"] = np.full((2, 2), np.nan)
    assert apply_grid_write_time_autos(no_range) == "colorbar-range"


# -- (a) the pure helper -------------------------------------------------------


def test_auto_extent_helper_covers_both_modes_and_refuses_degenerate_input():
    grid = {"source": "grid", "z": np.zeros((4, 7))}
    assert auto_extent(grid) == [0.0, 7.0, 0.0, 4.0]

    points = {
        "source": "points",
        "x": np.array([1.0, 3.0]),
        "y": np.array([-2.0, 2.0]),
    }
    assert auto_extent(points) == [1.0, 3.0, -2.0, 2.0]

    assert auto_extent({"source": "grid", "z": None}) is None
    assert auto_extent({"source": "grid", "z": np.zeros((0, 3))}) is None
    assert auto_extent({"source": "points", "x": None, "y": None}) is None
    assert (
        auto_extent(
            {"source": "points", "x": np.array([1.0, 1.0]), "y": np.array([0.0, 1.0])}
        )
        is None
    )


# -- (b) Figure.colorbar() on a reference-backed heatmap -----------------------


def test_colorbar_on_a_reference_backed_heatmap_no_longer_crashes():
    """It used to raise ``TypeError`` from ``float(np.nanmin(None))``."""
    fig, ax = _figure()
    _heatmap_grid(ax)

    cb = fig.colorbar(label="z")

    assert cb[COLORBAR_AUTO_RANGE] is True
    assert cb[COLORBAR_NTICKS] == 5
    assert cb["zmin"] is None and cb["zmax"] is None and cb["zstep"] is None
    assert cb["label"] == "z"


def test_colorbar_with_explicit_vmin_vmax_proceeds_without_an_auto_marker():
    fig, ax = _figure()
    _heatmap_grid(ax, vmin=0.0, vmax=10.0)

    cb = fig.colorbar(nticks=4)

    assert COLORBAR_AUTO_RANGE not in cb
    assert COLORBAR_NTICKS not in cb
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (0.0, 10.0, 2.5)


def test_colorbar_nticks_is_carried_to_the_write_that_resolves_the_range():
    fig, ax = _figure()
    _heatmap_grid(ax)
    fig.colorbar(nticks=2)

    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE))

    cb = resolved[("heatmaps", 0)]["colorbar"]
    # Data range 1..6 -> span 5, divided into 2 intervals.
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (1.0, 6.0, 2.5)


def test_an_auto_colorbar_range_is_computed_from_the_resolved_grid():
    fig, ax = _figure()
    _heatmap_grid(ax)
    fig.colorbar()

    resolved, resolution = _resolved(fig, _provider(t1=_GRID_TABLE))

    assert resolution.warnings == []
    cb = resolved[("heatmaps", 0)]["colorbar"]
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (1.0, 6.0, 1.0)
    assert cb[COLORBAR_AUTO_RANGE] is True  # the marker survives on the copy


def test_an_auto_colorbar_range_is_computed_from_resolved_scattered_samples():
    fig, ax = _figure()
    _heatmap_points(ax)
    fig.colorbar()

    resolved, _ = _resolved(fig, _provider(t1=_POINTS_TABLE))

    cb = resolved[("heatmaps", 0)]["colorbar"]
    assert (cb["zmin"], cb["zmax"]) == (10.0, 40.0)
    assert cb["zstep"] == pytest.approx(6.0)


def test_an_auto_colorbar_range_still_honours_an_explicit_vmin_vmax():
    """A later ``vmin`` edit must show up on the bar (SPEC 14.5's panel rule)."""
    fig, ax = _figure()
    hm = _heatmap_grid(ax)
    fig.colorbar()
    hm["vmin"] = -10.0

    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE))

    cb = resolved[("heatmaps", 0)]["colorbar"]
    assert (cb["zmin"], cb["zmax"]) == (-10.0, 6.0)


def test_an_explicit_colorbar_range_is_not_recomputed_at_write_time():
    fig, ax = _figure()
    _heatmap_grid(ax, vmin=0.0, vmax=100.0)
    fig.colorbar()

    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE))

    cb = resolved[("heatmaps", 0)]["colorbar"]
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (0.0, 100.0, 20.0)


def test_the_write_never_bakes_the_resolved_range_back_onto_the_document():
    """A series ``copy()`` is shallow, so the colorbar dict must be replaced."""
    fig, ax = _figure()
    hm = _heatmap_grid(ax)
    cb = fig.colorbar()

    resolved, _ = _resolved(fig, _provider(t1=_GRID_TABLE))

    assert resolved[("heatmaps", 0)]["colorbar"] is not cb
    assert hm["colorbar"] is cb
    assert cb["zmin"] is None and cb["zmax"] is None and cb["zstep"] is None


def test_a_provider_data_change_alters_the_emitted_colorbar_range():
    """The staleness fix, at the level the script shows it."""
    fig, ax = _figure()
    _heatmap_grid(ax)
    fig.colorbar()

    before, _ = fig._generate_gle_with_files(data_provider=_provider(t1=_GRID_TABLE))
    edited = {k: [v * 10 for v in col] for k, col in _GRID_TABLE.items()}
    after, _ = fig._generate_gle_with_files(data_provider=_provider(t1=edited))

    assert "color_range_vertical zmin 1 zmax 6" in before
    assert "color_range_vertical zmin 10 zmax 60" in after


def test_an_auto_colorbar_on_an_all_nan_grid_skips_rather_than_raises():
    fig, ax = _figure()
    _heatmap_grid(ax, keys=("c0", "c1"))
    fig.colorbar()

    nan_table = dict(c0=[np.nan, np.nan], c1=[np.nan, np.nan])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text, files = fig._generate_gle_with_files(
            data_provider=_provider(t1=nan_table)
        )

    assert [w.reason for w in fig.source_warnings] == ["unusable-data"]
    assert files == {}
    assert "color_range_vertical" not in text
    assert 'include "color.gle"' not in text


def test_colorbar_without_data_and_without_a_reference_raises_a_clear_error():
    """The truly unresolvable case: a clear message, never a numpy traceback."""
    fig, ax = _figure()
    _heatmap_grid(ax, data_source=None)

    with pytest.raises(ValueError, match="cannot determine a colour range"):
        fig.colorbar()


def test_colorbar_on_an_inline_heatmap_is_unchanged():
    fig, ax = _figure()
    ax.imshow(np.array([[0.0, 2.0], [4.0, 8.0]]))

    cb = fig.colorbar()

    assert COLORBAR_AUTO_RANGE not in cb
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (0.0, 8.0, 1.6)


def test_auto_colorbar_range_helper_handles_the_edge_cases():
    grid = {"source": "grid", "z": np.array([[1.0, 2.0], [3.0, 4.0]])}
    assert auto_colorbar_range(grid) == (1.0, 4.0, 0.6)
    assert auto_colorbar_range(grid, 3) == (1.0, 4.0, 1.0)

    flat = {"source": "grid", "z": np.full((2, 2), 5.0)}
    # Zero span keeps Figure.colorbar's 1.0 fallback rather than dividing by 0.
    assert auto_colorbar_range(flat) == (5.0, 5.0, 1.0)

    assert auto_colorbar_range({"source": "grid", "z": None}) is None
    assert auto_colorbar_range({"source": "grid", "z": np.full((2, 2), np.nan)}) is None
    # One explicit bound is not enough on its own.
    assert auto_colorbar_range({"source": "grid", "z": None, "vmin": 0.0}) is None
    assert auto_colorbar_range(
        {"source": "grid", "z": None, "vmin": 0.0, "vmax": 4.0}
    ) == (0.0, 4.0, 0.8)


# -- layout: an unresolved auto range must not crash the margin estimator ------


def test_the_colorbar_margin_estimator_tolerates_an_unresolved_auto_range():
    """``_axes_colorbar_reserved_cm`` normally sees the resolved copy; asking
    it without a resolution (as the recognizer's legacy-``size`` check does)
    must fall back rather than raise on ``float(None)``."""
    fig, ax = _figure()
    _heatmap_grid(ax)
    fig.colorbar()

    reserved, _below = fig._axes_colorbar_reserved_cm(ax)

    assert reserved > 0


def test_autoscale_without_a_resolution_ignores_an_unresolved_auto_extent():
    fig, ax = _figure()
    _heatmap_grid(ax)
    ax.plot([0.0, 1.0], [0.0, 2.0])

    assert fig._get_data_xlim(ax) == (0.0, 1.0)
    assert fig._get_data_ylim(ax) == (0.0, 2.0)


# -- serialization of the new states (deliverable c, model level) --------------


def test_the_auto_states_survive_a_document_round_trip():
    fig, ax = _figure()
    _heatmap_grid(ax)
    fig.colorbar(label="z", nticks=3)

    restored = Figure.from_dict(fig.to_dict())
    hm = restored.axes_list[0].heatmaps[0]

    assert hm["extent"] is None
    assert hm["colorbar"][COLORBAR_AUTO_RANGE] is True
    assert hm["colorbar"][COLORBAR_NTICKS] == 3
    # ... and the restored document resolves to the same numbers.
    resolved, _ = _resolved(restored, _provider(t1=_GRID_TABLE))
    cb = resolved[("heatmaps", 0)]["colorbar"]
    assert (cb["zmin"], cb["zmax"], cb["zstep"]) == (1.0, 6.0, pytest.approx(5 / 3))
    assert resolved[("heatmaps", 0)]["extent"] == [0.0, 3.0, 0.0, 2.0]

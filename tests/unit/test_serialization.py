"""Unit tests for the figure/axes serialization layer.

Covers the JSON-safe conversion of numpy data, envelope validation on
``Figure.from_dict``, forward-compatibility (unknown-key tolerance), and
determinism of ``to_dict``.
"""

import copy
import json

import numpy as np
import pytest

import gleplot as glp
from gleplot import axes as glp_axes
from gleplot import Figure
from gleplot.axes import _STYLING_KEYS, Axes
from gleplot.figure import (
    PROJECT_FORMAT,
    PROJECT_VERSION,
    SUPPORTED_PROJECT_VERSIONS,
)
from gleplot.series import SERIES_ATTRS, SERIES_CLASSES, Series
from gleplot.sources import ColumnRef, GridRef, is_inline


def _simple_figure():
    fig = glp.figure(figsize=(8, 6), data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], color="red", label="q")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend()
    return fig


def _heatmap_contour_figure():
    fig = glp.figure(figsize=(7, 6), data_prefix="u")
    ax = fig.add_subplot(111)
    Z = np.arange(12, dtype=float).reshape(3, 4)
    ax.imshow(Z, extent=(0, 4, 0, 3), cmap="viridis", vmin=0, vmax=11)
    ax.contour(
        np.linspace(0, 4, 4),
        np.linspace(0, 3, 3),
        np.arange(12, dtype=float).reshape(3, 4),
        levels=[2.0, 6.0],
        colors="black",
        clabel=True,
    )
    fig.colorbar(label="signal")
    return fig


# -- Heatmap / contour serialization ---------------------------------------


def test_heatmap_contour_to_from_dict_roundtrip():
    fig = _heatmap_contour_figure()
    d = fig.to_dict()
    # JSON-serializable (2-D z becomes nested lists; colorbar nested dict).
    json.dumps(d)
    fig2 = Figure.from_dict(d)
    assert fig2.to_dict() == d


def test_heatmap_2d_z_restored_as_2d_float_array():
    fig = _heatmap_contour_figure()
    fig2 = Figure.from_dict(fig.to_dict())
    hm = fig2.axes_list[0].heatmaps[0]
    assert isinstance(hm["z"], np.ndarray)
    assert hm["z"].ndim == 2
    assert hm["z"].shape == (3, 4)
    assert hm["z"].dtype == float
    np.testing.assert_array_equal(hm["z"], np.arange(12).reshape(3, 4))


def test_heatmap_colorbar_dict_survives_roundtrip():
    fig = _heatmap_contour_figure()
    fig2 = Figure.from_dict(fig.to_dict())
    cb = fig2.axes_list[0].heatmaps[0]["colorbar"]
    assert cb is not None
    assert cb["label"] == "signal"
    assert cb["zmin"] == 0.0 and cb["zmax"] == 11.0


def test_points_series_1d_arrays_restored():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    x = np.array([0.0, 1.0, 2.0, 3.0])
    ax.tripcolor(x, x, x * 2, gridsize=(5, 5))
    fig2 = Figure.from_dict(fig.to_dict())
    hm = fig2.axes_list[0].heatmaps[0]
    assert hm["z"] is None
    for key in ("x", "y", "zpts"):
        assert isinstance(hm[key], np.ndarray)
        assert hm[key].ndim == 1


def test_regenerated_gle_identical_after_from_dict():
    fig = _heatmap_contour_figure()
    text1, files1 = fig._generate_gle_with_files()
    fig2 = Figure.from_dict(fig.to_dict())
    text2, files2 = fig2._generate_gle_with_files()
    assert text2 == text1
    assert files2 == files1


# -- Envelope shape ---------------------------------------------------------


def test_envelope_shape():
    fig = _simple_figure()
    d = fig.to_dict()
    assert d["format"] == PROJECT_FORMAT
    assert d["version"] == PROJECT_VERSION
    assert d["gleplot_version"] == glp.__version__
    assert "figure" in d
    assert isinstance(d["figure"]["axes"], list)


def test_to_dict_is_json_safe():
    fig = _simple_figure()
    d = fig.to_dict()
    # Must serialize without a custom encoder.
    text = json.dumps(d)
    reloaded = json.loads(text)
    assert reloaded == d


def test_numpy_conversion_to_native_types():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    ax.plot(x, y)
    line = fig.to_dict()["figure"]["axes"][0]["lines"][0]
    assert isinstance(line["x"], list)
    assert all(isinstance(v, float) for v in line["x"])
    # No numpy types leak through.
    assert not isinstance(line["x"][0], np.generic)


def test_numpy_scalar_limits_converted():
    fig = _simple_figure()
    ax = fig.axes_list[0]
    ax.xmin = np.float64(0.5)
    ax.xmax = np.int64(10)
    d = fig.to_dict()["figure"]["axes"][0]
    assert d["xmin"] == 0.5
    assert d["xmax"] == 10
    assert not isinstance(d["xmin"], np.generic)
    json.dumps(d)  # still json-safe


# -- Determinism ------------------------------------------------------------


def test_to_dict_deterministic():
    fig = _simple_figure()
    assert fig.to_dict() == fig.to_dict()


def test_round_trip_dict_equal():
    fig = _simple_figure()
    d1 = fig.to_dict()
    d2 = Figure.from_dict(d1).to_dict()
    assert d1 == d2


def test_round_trip_restores_arrays():
    fig = _simple_figure()
    fig2 = Figure.from_dict(fig.to_dict())
    line = fig2.axes_list[0].lines[0]
    assert isinstance(line["x"], np.ndarray)
    assert isinstance(line["y"], np.ndarray)


def test_errorbar_none_arrays_stay_none():
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.5)  # no xerr
    fig2 = Figure.from_dict(fig.to_dict())
    eb = fig2.axes_list[0].errorbars[0]
    assert eb["xerr_left"] is None
    assert eb["xerr_right"] is None
    assert isinstance(eb["yerr_up"], np.ndarray)


# -- Envelope validation ----------------------------------------------------


def test_wrong_format_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    d["format"] = "not-gleplot"
    with pytest.raises(ValueError, match="format"):
        Figure.from_dict(d)


def test_missing_format_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    del d["format"]
    with pytest.raises(ValueError):
        Figure.from_dict(d)


def test_unsupported_version_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    d["version"] = 999
    with pytest.raises(ValueError, match="version"):
        Figure.from_dict(d)


def test_missing_figure_block_raises():
    d = {"format": PROJECT_FORMAT, "version": PROJECT_VERSION}
    with pytest.raises(ValueError, match="figure"):
        Figure.from_dict(d)


# -- Forward compatibility --------------------------------------------------


def test_unknown_keys_ignored():
    fig = _simple_figure()
    d = fig.to_dict()
    d["extra_top_level"] = "ignored"
    d["figure"]["future_field"] = {"anything": 1}
    d["figure"]["axes"][0]["future_axes_field"] = [1, 2, 3]
    # Should reconstruct without error and preserve known state.
    fig2 = Figure.from_dict(d)
    assert fig2.axes_list[0].xlabel_text == "x"


def test_data_file_names_preserved():
    fig = _simple_figure()
    original = fig.axes_list[0].lines[0]["data_file"]
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2.axes_list[0].lines[0]["data_file"] == original


def test_used_data_files_round_tripped():
    fig = _simple_figure()
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2._used_data_files == fig._used_data_files


# -- Config overrides -------------------------------------------------------


def test_config_overrides_round_trip():
    style = glp.GLEStyleConfig(font="helvetica", fontsize=14)
    graph = glp.GLEGraphConfig(smooth_curves=False, legend_position="bl")
    marker = glp.GLEMarkerConfig(msize_scale=2.0, mdist=0.5)
    fig = glp.figure(style=style, graph=graph, marker=marker, data_prefix="u")
    fig.add_subplot(111).plot([1, 2], [3, 4])
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2.style.font == "helvetica"
    assert fig2.style.fontsize == 14
    assert fig2.graph.smooth_curves is False
    assert fig2.graph.legend_position == "bl"
    assert fig2.marker_config.msize_scale == 2.0
    assert fig2.marker_config.mdist == 0.5


# -- Empty figure -----------------------------------------------------------


def test_empty_figure_round_trip():
    fig = glp.figure(data_prefix="u")
    d = fig.to_dict()
    fig2 = Figure.from_dict(d)
    assert fig2.axes_list == []
    assert fig2.to_dict() == d


def test_from_dict_does_not_mutate_input():
    fig = _simple_figure()
    d = fig.to_dict()
    snapshot = copy.deepcopy(d)
    Figure.from_dict(d)
    assert d == snapshot


# -- Forward-compat: unknown keys inside config sub-dicts -------------------


def test_from_dict_ignores_unknown_style_graph_marker_keys():
    fig = _simple_figure()
    d = fig.to_dict()
    d["figure"]["config"]["style"]["not_a_real_style_field"] = "nonsense"
    d["figure"]["config"]["graph"]["not_a_real_graph_field"] = 123
    d["figure"]["config"]["marker"]["not_a_real_marker_field"] = [1, 2, 3]

    # Should not raise TypeError despite the unrecognized keys.
    fig2 = Figure.from_dict(d)

    # Known fields still round-trip correctly.
    assert fig2.style.font == fig.style.font
    assert fig2.graph.smooth_curves == fig.graph.smooth_curves
    assert fig2.marker_config.default_marker == fig.marker_config.default_marker


# -- Data-file counter round-trip (FIX 4) ------------------------------------


def test_global_data_counter_round_trips_across_fresh_process(monkeypatch):
    """Simulate loading a saved project in a fresh process (counter reset to 0)."""
    fig = glp.figure()  # no data_prefix -> uses the global counter
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.plot([1, 2, 3], [4, 5, 6])
    d = fig.to_dict()

    saved_counter = d["figure"]["global_data_counter"]
    assert saved_counter >= 2

    # Simulate a fresh process/session: reset the module-global counter.
    monkeypatch.setattr(glp_axes, "_global_data_file_counter", 0)

    fig2 = Figure.from_dict(d)
    ax2 = fig2.add_subplot(111)
    ax2.plot([7, 8, 9], [1, 2, 3])

    new_data_file = ax2.lines[-1]["data_file"]
    assert new_data_file == f"data_{saved_counter}.dat"


def test_global_data_counter_takes_max_with_in_process_value(monkeypatch):
    """When the in-process counter is already ahead, from_dict must not rewind it."""
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2], [1, 2])
    d = fig.to_dict()
    saved_counter = d["figure"]["global_data_counter"]

    # Simulate another figure in the same process having advanced the
    # counter further than the saved value.
    monkeypatch.setattr(glp_axes, "_global_data_file_counter", saved_counter + 10)

    Figure.from_dict(d)
    assert glp_axes._global_data_file_counter == saved_counter + 10


# -- Drift guards -------------------------------------------------------------
#
# These tests guard against a future dev adding a new stateful attribute to
# Axes.__init__ / Figure.__init__ without updating the serialization layer
# (to_dict / from_dict) to round-trip it. If either of these
# tests fails, it means `vars(instance)` grew a key that isn't accounted for
# below -- go update Axes.to_dict/from_dict (or Figure.to_dict/from_dict) and
# then extend the "covered" set (or, if the new attribute is genuinely
# runtime-only and must never be persisted, add it to the exclusion set
# instead, with a comment explaining why).

# Axes attributes that are intentionally NOT part of the serialized project
# format: `figure` is a back-reference to the parent Figure (set by the
# constructor from the caller, not user/plot state), reconstructed by
# Figure.from_dict passing itself into Axes.from_dict.
# `_break_owner` is the same kind of thing for a broken-axis segment: a
# back-reference to the BrokenAxes that owns it, rebound by Figure.from_dict
# once every axes exists (the grouping itself IS persisted, as
# figure["broken_axes"], by index into figure["axes"]).
_AXES_RUNTIME_ONLY_ATTRS = {
    "figure",
    "_break_owner",
    # Rebuilt in from_dict from the max ``_draw_seq`` on loaded series.
    "_draw_seq_counter",
}

# Axes attributes that ARE serialized, mapped to the to_dict()/from_dict()
# keys that cover them (some are stored under a different dict key name,
# e.g. the leading-underscore visibility/tick-removal flags).
_AXES_SERIALIZED_ATTRS = {
    "position",
    "xlabel_text",
    "ylabel_text",
    "y2label_text",
    "title_text",
    "xscale",
    "yscale",
    "y2scale",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "y2min",
    "y2max",
    "legend_on",
    "legend_pos",
    "legend_fontsize",
    "legend_frameon",
    "legend_offset",
    "_show_xlabel",
    "_show_ylabel",
    "_show_xticks",
    "_show_yticks",
    "_remove_last_xtick",
    "_remove_last_ytick",
    "_remove_first_xtick",
    "_remove_first_ytick",
    "lines",
    "scatters",
    "bars",
    "fills",
    "errorbars",
    "file_series",
    "texts",
    "heatmaps",
    "contours",
    "reflines",
    "spans",
    "passthrough",
    # Explicit page geometry: the placement rect (SPEC 3.3) and the verbatim
    # geometry statements kept for GLE geometry that inverts to no rect.
    "placement",
    "geometry_passthrough",
    "xdticks",
    "ydticks",
    "xdsubticks",
    "ydsubticks",
    "xplaces",
    "xnames",
    "yplaces",
    "ynames",
    "_xaxis_off",
    "_yaxis_off",
    "_x2axis_off",
    "_y2axis_off",
    "_break_index",
    # Axes styling (tick-label formats, grids, axis-title / tick-label /
    # graph-title size-colour-distance-angle). Enumerated by
    # ``gleplot.axes._STYLING_KEYS``, which is also what to_dict/from_dict
    # walk -- spliced in here rather than retyped so the two cannot drift.
    *_STYLING_KEYS,
}

# Figure attributes that are intentionally NOT part of the serialized
# project format:
#   - `compiler`: a GLECompiler instance (or None), resolved fresh from the
#     environment on construction; not user state and not portable across
#     machines/processes.
#   - `_current_axes`: a derived pointer into axes_list, recomputed by
#     from_dict as `axes_list[-1]` (or None), not independent state.
#   - `_source_warnings`: output of the LAST GLE generation (the
#     DanglingSourceRef records behind Figure.source_warnings), not document
#     state. Reset by every write and meaningless without the provider that
#     produced it, so persisting it would only ever be stale.
_FIGURE_RUNTIME_ONLY_ATTRS = {"compiler", "_current_axes", "_source_warnings"}

# Figure attributes that ARE serialized (style/graph/marker_config go into
# the 'config' sub-dict; axes_list is serialized element-by-element via
# Axes.to_dict/from_dict, not stored verbatim).
_FIGURE_SERIALIZED_ATTRS = {
    "figsize",
    "dpi",
    "sharex",
    "sharey",
    "data_prefix",
    "_local_data_counter",
    "_used_data_files",
    "_sidecar_counters",
    "_subplot_adjust",
    "height_ratios",
    "width_ratios",
    "style",
    "graph",
    "marker_config",
    "axes_list",
    "broken_axes",
    "passthrough_header",
    "passthrough_trailer",
    "metadata_extra",
}


def test_axes_instance_attrs_fully_accounted_for_in_serialization():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])

    actual_attrs = set(vars(ax).keys())
    accounted_for = _AXES_SERIALIZED_ATTRS | _AXES_RUNTIME_ONLY_ATTRS

    unaccounted = actual_attrs - accounted_for
    assert not unaccounted, (
        f"Axes gained new instance attribute(s) {unaccounted} that are not "
        "handled by Axes.to_dict()/from_dict() and not listed in the "
        "documented runtime-only exclusion set in this test file. Update "
        "Axes.to_dict/from_dict (and gleplot.series.SERIES_CLASSES if it's a "
        "new series list) or add it to _AXES_RUNTIME_ONLY_ATTRS with a "
        "comment explaining why it must not be persisted."
    )

    # Also guard against the lists going stale in the other direction (a
    # documented attr that Axes no longer actually has).
    stale = accounted_for - actual_attrs
    assert not stale, f"Stale entries in the Axes attribute lists: {stale}"


def test_figure_instance_attrs_fully_accounted_for_in_serialization():
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2, 3], [1, 2, 3])

    actual_attrs = set(vars(fig).keys())
    accounted_for = _FIGURE_SERIALIZED_ATTRS | _FIGURE_RUNTIME_ONLY_ATTRS

    unaccounted = actual_attrs - accounted_for
    assert not unaccounted, (
        f"Figure gained new instance attribute(s) {unaccounted} that are not "
        "handled by Figure.to_dict()/from_dict() and not listed in the "
        "documented runtime-only exclusion set in this test file. Update "
        "Figure.to_dict/from_dict or add it to _FIGURE_RUNTIME_ONLY_ATTRS "
        "with a comment explaining why it must not be persisted."
    )

    stale = accounted_for - actual_attrs
    assert not stale, f"Stale entries in the Figure attribute lists: {stale}"


# -- Series-class completeness ------------------------------------------------
#
# The same drift guard as above, one level down. Each series kind used to be
# an anonymous dict described by three hand-synced tables on Axes
# (_SERIES_ATTRS / _ARRAY_KEYS / _default_column_names); it is now a class in
# gleplot.series that declares its own fields. These tests are what makes the
# class the single source of truth: a field that is not declared cannot be
# constructed, and every field that IS declared must survive a round-trip.


def _figure_exercising_every_series_kind():
    """A figure touching every public series-producing entry point.

    One axes per heatmap/contour pair because GLE (and so Axes.imshow)
    allows at most one colormap per axes.
    """
    fig = glp.figure(figsize=(8, 10), data_prefix="cov")
    ax = fig.add_subplot(311)
    ax.plot([1.0, 2.0], [3.0, 4.0], marker="o", label="line", zorder=7)
    ax.scatter([1.0, 2.0], [3.0, 4.0], label="scatter", zorder=8)
    ax.bar([1.0, 2.0], [3.0, 4.0], color="red", label="bar", zorder=1)
    ax.fill_between([1.0, 2.0], [0.0, 1.0], [3.0, 4.0], label="fill")
    ax.errorbar(
        [1.0, 2.0],
        [3.0, 4.0],
        yerr=[0.1, 0.2],
        xerr=[0.3, 0.4],
        capsize=3,
        label="err",
        zorder=9,
    )
    ax.line_from_file("ext.dat", 1, 2, label="fline")
    ax.errorbar_from_file("ext.dat", 1, 2, yerr_col=3, capsize=2, label="ferr")
    ax.text(1.0, 2.0, "hello", color="blue", fontsize=9, bbox={"facecolor": "white"})
    ax.axvline(1.5, label="vline")
    ax.axhline(2.5, label="hline")
    ax.axvspan(1.0, 1.2, label="vspan")
    ax.axhspan(2.0, 2.2, label="hspan")

    ax2 = fig.add_subplot(312)
    ax2.imshow(np.arange(12, dtype=float).reshape(3, 4), extent=(0, 4, 0, 3))
    ax2.contour(
        np.linspace(0, 4, 4),
        np.linspace(0, 3, 3),
        np.arange(12, dtype=float).reshape(3, 4),
        levels=[2.0, 6.0],
        clabel=True,
    )

    ax3 = fig.add_subplot(313)
    pts_x = [0.0, 1.0, 2.0, 3.0]
    pts_y = [0.0, 1.0, 0.0, 1.0]
    pts_z = [1.0, 2.0, 3.0, 4.0]
    ax3.tripcolor(pts_x, pts_y, pts_z, gridsize=(4, 4))
    ax3.tricontour(pts_x, pts_y, pts_z, gridsize=(4, 4), ncontour=2)
    return fig


def _all_series(fig):
    """Yield ``(attr, series)`` for every series on every axes of ``fig``."""
    for ax in fig.axes_list:
        for attr in SERIES_ATTRS:
            for series in getattr(ax, attr):
                yield attr, series


def test_series_registry_matches_axes_attributes():
    """Every registry entry is a real Axes list, and every list is registered."""
    ax = glp.figure().add_subplot(111)
    for attr, series_cls in SERIES_CLASSES.items():
        assert isinstance(getattr(ax, attr), list), f"Axes has no list {attr!r}"
        assert series_cls.ATTR == attr
        assert set(series_cls.ARRAY_FIELDS) <= set(series_cls.FIELDS), (
            f"{series_cls.__name__}.ARRAY_FIELDS names undeclared field(s) "
            f"{sorted(set(series_cls.ARRAY_FIELDS) - set(series_cls.FIELDS))}"
        )
        assert series_cls.FIELDS, f"{series_cls.__name__} declares no fields"

    # Axes._SERIES_ATTRS is derived from the registry, not hand-maintained.
    assert Axes._SERIES_ATTRS == SERIES_ATTRS


def test_every_key_the_plotting_api_produces_is_a_declared_field():
    """No series may carry a key its class does not declare.

    This is the check that replaces the old hand-synced tables: adding a key
    at a call site without declaring it on the class fails here (and, for the
    keyword form, already fails at construction -- see the next test).
    """
    fig = _figure_exercising_every_series_kind()
    for attr, series in _all_series(fig):
        assert isinstance(series, SERIES_CLASSES[attr]), (
            f"{attr} holds a {type(series).__name__}; series must be built "
            f"through {SERIES_CLASSES[attr].__name__} so the schema applies"
        )
        stray = set(series) - set(type(series).FIELDS)
        assert not stray, (
            f"{type(series).__name__} carries undeclared key(s) {sorted(stray)}. "
            "Declare them as annotations on the class in gleplot/series.py -- "
            "that is the single place a series kind's schema lives."
        )


def test_series_reject_undeclared_construction_keywords():
    for series_cls in SERIES_CLASSES.values():
        with pytest.raises(TypeError, match="unknown field"):
            series_cls(definitely_not_a_field=1)


def test_optional_fields_stay_absent_rather_than_none():
    """``zorder``/``_draw_seq`` presence is meaningful; construction must not
    materialize unset fields (``sorted_zorder_drawables`` reads ``"zorder" in
    series`` to tell "explicit" from "kind default" apart)."""
    fig = glp.figure(data_prefix="u")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.plot([1, 2], [2, 3], zorder=4.5)
    assert "zorder" not in ax.lines[0]
    assert ax.lines[1]["zorder"] == 4.5
    # ... and the distinction survives serialization.
    restored = Figure.from_dict(fig.to_dict()).axes_list[0]
    assert "zorder" not in restored.lines[0]
    assert restored.lines[1]["zorder"] == 4.5


def test_every_declared_field_survives_a_full_round_trip():
    """to_dict -> from_dict -> to_dict is a fixed point for every field.

    A field declared on a class but dropped by the serialization layer shows
    up here as a missing key; one restored with the wrong type shows up as a
    value mismatch.
    """
    fig = _figure_exercising_every_series_kind()
    once = fig.to_dict()
    twice = Figure.from_dict(once).to_dict()
    assert twice == once

    seen_fields = {}
    for attr, series in _all_series(Figure.from_dict(once)):
        seen_fields.setdefault(attr, set()).update(series)
    # Every kind was actually exercised above (else the test proves nothing).
    assert set(seen_fields) == set(SERIES_ATTRS), (
        "the coverage figure no longer produces every series kind: missing "
        f"{sorted(set(SERIES_ATTRS) - set(seen_fields))}"
    )


def test_unknown_series_keys_are_preserved_for_forward_compatibility():
    """A project written by a newer gleplot round-trips through an older one.

    Axes.from_dict is deliberately lenient where the constructors are strict:
    a key the class does not declare is kept verbatim rather than dropped.
    """
    fig = _simple_figure()
    payload = fig.to_dict()
    payload["figure"]["axes"][0]["lines"][0]["future_field"] = "keep me"

    restored = Figure.from_dict(payload)
    assert restored.axes_list[0].lines[0]["future_field"] == "keep me"
    assert restored.to_dict()["figure"]["axes"][0]["lines"][0]["future_field"] == (
        "keep me"
    )


def test_declared_fields_are_readable_as_attributes():
    """The typed face of the classes: ``series.color`` is ``series["color"]``."""
    fig = _simple_figure()
    line = fig.axes_list[0].lines[0]
    assert isinstance(line, Series)
    assert line.color == line["color"]
    assert line.label == "q"
    line.label = "renamed"
    assert line["label"] == "renamed"
    # An unset optional field is an AttributeError, not a silent None.
    with pytest.raises(AttributeError):
        line.zorder


def test_series_copy_keeps_its_class():
    """``dict.copy()`` would downgrade a series to a plain dict."""
    fig = _simple_figure()
    line = fig.axes_list[0].lines[0]
    clone = line.copy()
    assert type(clone) is type(line)
    assert clone == line
    clone["label"] = "other"
    assert line["label"] == "q"


def test_series_deep_copy_round_trips():
    """Undo snapshots and preview copies deep-copy the model."""
    fig = _figure_exercising_every_series_kind()
    for _attr, series in _all_series(fig):
        clone = copy.deepcopy(series)
        assert type(clone) is type(series)
        assert list(clone) == list(series)


# -- Project version 1 -> 2: the ``data_source`` field ------------------------
#
# Version 2 adds one optional key per data-bearing series. It is optional in
# the strong sense: a series WITHOUT it is InlineData, which is exactly what
# every version-1 series is, so the two versions differ for a scripted figure
# by the envelope integer alone. These tests pin both directions.


def test_project_version_is_two():
    assert PROJECT_VERSION == 2
    assert SUPPORTED_PROJECT_VERSIONS == (1, 2)
    assert _simple_figure().to_dict()["version"] == 2


def test_version_2_dict_of_an_inline_figure_matches_the_version_1_shape():
    """The ONLY schema change for a scripted figure is the version integer."""
    fig = _figure_exercising_every_series_kind()
    d = fig.to_dict()

    as_v1 = copy.deepcopy(d)
    as_v1["version"] = 1
    # No series grew a key, so downgrading the envelope yields a dict a
    # version-1 build would have written verbatim.
    for ax_d in d["figure"]["axes"]:
        for attr in SERIES_ATTRS:
            for series_d in ax_d[attr]:
                assert "data_source" not in series_d

    restored = Figure.from_dict(as_v1)
    assert restored.to_dict()["figure"] == d["figure"]


def test_version_1_dict_still_loads_with_inline_implied():
    fig = _simple_figure()
    d = fig.to_dict()
    d["version"] = 1

    restored = Figure.from_dict(d)
    line = restored.axes_list[0].lines[0]
    assert "data_source" not in line
    assert is_inline(line)
    # ... and re-saving stamps the current version.
    assert restored.to_dict()["version"] == PROJECT_VERSION


def test_version_1_and_version_2_dicts_regenerate_identical_gle():
    fig = _figure_exercising_every_series_kind()
    d2 = fig.to_dict()
    d1 = copy.deepcopy(d2)
    d1["version"] = 1

    from_v1 = Figure.from_dict(d1)._generate_gle_with_files()
    from_v2 = Figure.from_dict(d2)._generate_gle_with_files()
    assert from_v1 == from_v2


def test_still_unsupported_versions_raise():
    fig = _simple_figure()
    for bad in (0, 3, "2", None):
        d = fig.to_dict()
        d["version"] = bad
        with pytest.raises(ValueError, match="version"):
            Figure.from_dict(d)


# -- Series-class completeness: the ``data_source`` field ---------------------


#: Every kind that owns bulk data and can therefore be table-backed. The
#: complement is asserted below so this list cannot silently go stale: the
#: kinds WITHOUT a source are the ones with no bulk data of their own
#: (``file_series`` already IS an external reference, ``texts`` hold a single
#: point, ``reflines``/``spans`` are declarations materialized at write time).
_SOURCE_BEARING_ATTRS = {
    "lines",
    "scatters",
    "bars",
    "fills",
    "errorbars",
    "heatmaps",
    "contours",
}


def test_every_data_bearing_series_class_declares_data_source():
    for attr, series_cls in SERIES_CLASSES.items():
        declared = "data_source" in series_cls.FIELDS
        assert declared == (attr in _SOURCE_BEARING_ATTRS), (
            f"{series_cls.__name__}: data_source declared={declared} but the "
            f"documented set says {attr in _SOURCE_BEARING_ATTRS}. A kind that "
            "owns bulk data must declare it; one that does not must not."
        )
        if declared:
            # Declared but absent by default -- the InlineData-is-implied rule.
            assert "data_source" not in series_cls()


def test_data_source_round_trips_for_every_class_that_declares_it():
    """to_dict -> JSON -> from_dict rebuilds the source as its own class."""
    sources = {
        "lines": ColumnRef("t1", {"x": "a", "y": "b"}),
        "scatters": ColumnRef("t1", {"x": "a", "y": "b"}),
        "bars": ColumnRef("t1", {"x": "a", "height": "b"}),
        "fills": ColumnRef("t1", {"x": "a", "y1": "b", "y2": "c"}),
        "errorbars": ColumnRef("t1", {"x": "a", "y": "b", "yerr_up": "c"}),
        "heatmaps": GridRef("t1", {"z": ["a", "b"]}),
        "contours": GridRef("t1", {"z": ["a", "b"]}),
    }
    assert set(sources) == _SOURCE_BEARING_ATTRS

    fig = _figure_exercising_every_series_kind()
    for attr, source in sources.items():
        for ax in fig.axes_list:
            for series in getattr(ax, attr):
                series["data_source"] = source

    once = fig.to_dict()
    json.dumps(once)  # a source must be JSON-safe like everything else
    twice = Figure.from_dict(once).to_dict()
    assert twice == once

    seen = set()
    for attr, series in _all_series(Figure.from_dict(once)):
        if attr not in _SOURCE_BEARING_ATTRS:
            continue
        seen.add(attr)
        restored = series["data_source"]
        assert type(restored) is type(sources[attr])
        assert restored == sources[attr]
        assert not is_inline(series)
    assert seen == _SOURCE_BEARING_ATTRS


def test_series_copy_keeps_its_data_source():
    fig = _simple_figure()
    line = fig.axes_list[0].lines[0]
    line["data_source"] = ColumnRef("t1", {"x": "a", "y": "b"})
    clone = line.copy()
    assert clone["data_source"] == line["data_source"]
    assert isinstance(copy.deepcopy(line)["data_source"], ColumnRef)

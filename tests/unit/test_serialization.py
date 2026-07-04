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
from gleplot.figure import PROJECT_FORMAT, PROJECT_VERSION


def _simple_figure():
    fig = glp.figure(figsize=(8, 6), data_prefix='u')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], color='red', label='q')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.legend()
    return fig


# -- Envelope shape ---------------------------------------------------------

def test_envelope_shape():
    fig = _simple_figure()
    d = fig.to_dict()
    assert d['format'] == PROJECT_FORMAT
    assert d['version'] == PROJECT_VERSION
    assert d['gleplot_version'] == glp.__version__
    assert 'figure' in d
    assert isinstance(d['figure']['axes'], list)


def test_to_dict_is_json_safe():
    fig = _simple_figure()
    d = fig.to_dict()
    # Must serialize without a custom encoder.
    text = json.dumps(d)
    reloaded = json.loads(text)
    assert reloaded == d


def test_numpy_conversion_to_native_types():
    fig = glp.figure(data_prefix='u')
    ax = fig.add_subplot(111)
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    ax.plot(x, y)
    line = fig.to_dict()['figure']['axes'][0]['lines'][0]
    assert isinstance(line['x'], list)
    assert all(isinstance(v, float) for v in line['x'])
    # No numpy types leak through.
    assert not isinstance(line['x'][0], np.generic)


def test_numpy_scalar_limits_converted():
    fig = _simple_figure()
    ax = fig.axes_list[0]
    ax.xmin = np.float64(0.5)
    ax.xmax = np.int64(10)
    d = fig.to_dict()['figure']['axes'][0]
    assert d['xmin'] == 0.5
    assert d['xmax'] == 10
    assert not isinstance(d['xmin'], np.generic)
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
    assert isinstance(line['x'], np.ndarray)
    assert isinstance(line['y'], np.ndarray)


def test_errorbar_none_arrays_stay_none():
    fig = glp.figure(data_prefix='u')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.5)  # no xerr
    fig2 = Figure.from_dict(fig.to_dict())
    eb = fig2.axes_list[0].errorbars[0]
    assert eb['xerr_left'] is None
    assert eb['xerr_right'] is None
    assert isinstance(eb['yerr_up'], np.ndarray)


# -- Envelope validation ----------------------------------------------------

def test_wrong_format_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    d['format'] = 'not-gleplot'
    with pytest.raises(ValueError, match='format'):
        Figure.from_dict(d)


def test_missing_format_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    del d['format']
    with pytest.raises(ValueError):
        Figure.from_dict(d)


def test_unsupported_version_raises():
    fig = _simple_figure()
    d = fig.to_dict()
    d['version'] = 999
    with pytest.raises(ValueError, match='version'):
        Figure.from_dict(d)


def test_missing_figure_block_raises():
    d = {'format': PROJECT_FORMAT, 'version': PROJECT_VERSION}
    with pytest.raises(ValueError, match='figure'):
        Figure.from_dict(d)


# -- Forward compatibility --------------------------------------------------

def test_unknown_keys_ignored():
    fig = _simple_figure()
    d = fig.to_dict()
    d['extra_top_level'] = 'ignored'
    d['figure']['future_field'] = {'anything': 1}
    d['figure']['axes'][0]['future_axes_field'] = [1, 2, 3]
    # Should reconstruct without error and preserve known state.
    fig2 = Figure.from_dict(d)
    assert fig2.axes_list[0].xlabel_text == 'x'


def test_data_file_names_preserved():
    fig = _simple_figure()
    original = fig.axes_list[0].lines[0]['data_file']
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2.axes_list[0].lines[0]['data_file'] == original


def test_used_data_files_round_tripped():
    fig = _simple_figure()
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2._used_data_files == fig._used_data_files


# -- Config overrides -------------------------------------------------------

def test_config_overrides_round_trip():
    style = glp.GLEStyleConfig(font='helvetica', fontsize=14)
    graph = glp.GLEGraphConfig(smooth_curves=False, legend_position='bl')
    marker = glp.GLEMarkerConfig(msize_scale=2.0, mdist=0.5)
    fig = glp.figure(style=style, graph=graph, marker=marker, data_prefix='u')
    fig.add_subplot(111).plot([1, 2], [3, 4])
    fig2 = Figure.from_dict(fig.to_dict())
    assert fig2.style.font == 'helvetica'
    assert fig2.style.fontsize == 14
    assert fig2.graph.smooth_curves is False
    assert fig2.graph.legend_position == 'bl'
    assert fig2.marker_config.msize_scale == 2.0
    assert fig2.marker_config.mdist == 0.5


# -- Empty figure -----------------------------------------------------------

def test_empty_figure_round_trip():
    fig = glp.figure(data_prefix='u')
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
    d['figure']['config']['style']['not_a_real_style_field'] = 'nonsense'
    d['figure']['config']['graph']['not_a_real_graph_field'] = 123
    d['figure']['config']['marker']['not_a_real_marker_field'] = [1, 2, 3]

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

    saved_counter = d['figure']['global_data_counter']
    assert saved_counter >= 2

    # Simulate a fresh process/session: reset the module-global counter.
    monkeypatch.setattr(glp_axes, '_global_data_file_counter', 0)

    fig2 = Figure.from_dict(d)
    ax2 = fig2.add_subplot(111)
    ax2.plot([7, 8, 9], [1, 2, 3])

    new_data_file = ax2.lines[-1]['data_file']
    assert new_data_file == f'data_{saved_counter}.dat'


def test_global_data_counter_takes_max_with_in_process_value(monkeypatch):
    """When the in-process counter is already ahead, from_dict must not rewind it."""
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2], [1, 2])
    d = fig.to_dict()
    saved_counter = d['figure']['global_data_counter']

    # Simulate another figure in the same process having advanced the
    # counter further than the saved value.
    monkeypatch.setattr(glp_axes, '_global_data_file_counter', saved_counter + 10)

    Figure.from_dict(d)
    assert glp_axes._global_data_file_counter == saved_counter + 10


# -- Drift guards -------------------------------------------------------------
#
# These tests guard against a future dev adding a new stateful attribute to
# Axes.__init__ / Figure.__init__ without updating the serialization layer
# (to_dict / from_dict / _ARRAY_KEYS) to round-trip it. If either of these
# tests fails, it means `vars(instance)` grew a key that isn't accounted for
# below -- go update Axes.to_dict/from_dict (or Figure.to_dict/from_dict) and
# then extend the "covered" set (or, if the new attribute is genuinely
# runtime-only and must never be persisted, add it to the exclusion set
# instead, with a comment explaining why).

# Axes attributes that are intentionally NOT part of the serialized project
# format: `figure` is a back-reference to the parent Figure (set by the
# constructor from the caller, not user/plot state), reconstructed by
# Figure.from_dict passing itself into Axes.from_dict.
_AXES_RUNTIME_ONLY_ATTRS = {'figure'}

# Axes attributes that ARE serialized, mapped to the to_dict()/from_dict()
# keys that cover them (some are stored under a different dict key name,
# e.g. the leading-underscore visibility/tick-removal flags).
_AXES_SERIALIZED_ATTRS = {
    'position', 'xlabel_text', 'ylabel_text', 'y2label_text', 'title_text',
    'xscale', 'yscale', 'y2scale', 'xmin', 'xmax', 'ymin', 'ymax',
    'y2min', 'y2max', 'legend_on', 'legend_pos',
    '_show_xlabel', '_show_ylabel', '_show_xticks', '_show_yticks',
    '_remove_last_xtick', '_remove_last_ytick',
    '_remove_first_xtick', '_remove_first_ytick',
    'lines', 'scatters', 'bars', 'fills', 'errorbars', 'file_series', 'texts',
    'passthrough',
}

# Figure attributes that are intentionally NOT part of the serialized
# project format:
#   - `compiler`: a GLECompiler instance (or None), resolved fresh from the
#     environment on construction; not user state and not portable across
#     machines/processes.
#   - `_current_axes`: a derived pointer into axes_list, recomputed by
#     from_dict as `axes_list[-1]` (or None), not independent state.
_FIGURE_RUNTIME_ONLY_ATTRS = {'compiler', '_current_axes'}

# Figure attributes that ARE serialized (style/graph/marker_config go into
# the 'config' sub-dict; axes_list is serialized element-by-element via
# Axes.to_dict/from_dict, not stored verbatim).
_FIGURE_SERIALIZED_ATTRS = {
    'figsize', 'dpi', 'sharex', 'sharey', 'data_prefix',
    '_local_data_counter', '_used_data_files', '_subplot_adjust',
    'style', 'graph', 'marker_config', 'axes_list',
    'passthrough_header', 'passthrough_trailer', 'metadata_extra',
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
        "Axes.to_dict/from_dict (and _ARRAY_KEYS/_SERIES_ATTRS if it's a new "
        "series list) or add it to _AXES_RUNTIME_ONLY_ATTRS with a comment "
        "explaining why it must not be persisted."
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

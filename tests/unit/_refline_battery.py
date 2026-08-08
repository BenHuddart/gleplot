"""Guide (axvline/axhline/axvspan/axhspan) figures whose limits *do* resolve.

G14 replaces the warn-and-drop that used to fire when the axis a guide spans
has neither data nor an explicit limit. Every figure in this battery is on the
*other* side of that branch -- the spanned axis resolves, so materialization
was and remains driven by real limits -- which makes the battery a byte-level
regression guard: ``tests/unit/test_refline_fallback.py`` asserts each
builder's emission against ``refline_resolvable_emissions.json``, a snapshot
captured from the pre-G14 writer (base commit 83dcdd9).

Each builder is a zero-argument callable returning a fresh
:class:`gleplot.Figure`; between them they exercise every way a guide's
spanned axis can be resolved (explicit ``set_?lim``, data, other guides, log
limits, shared axes) crossed with the guide-side variations that reach
``materialize_reflines`` / ``materialize_spans`` (orientation, fractional
extent, style, label/legend, visibility, subplots, table-backed data).
"""

from __future__ import annotations

import numpy as np

import gleplot as glp
from gleplot.series import LineSeries
from gleplot.sources import ColumnRef, DictDataProvider, TableData


X = np.array([0.0, 1.0, 2.0, 3.0])
Y = np.array([0.0, 1.0, 4.0, 9.0])


def _fig():
    fig = glp.figure(data_prefix="rlb")
    return fig, fig.add_subplot(111)


def guides_over_data():
    """Limits resolved from the plotted data alone."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.axvline(1.5)
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    ax.axhspan(3.0, 5.0)
    return fig


def guides_with_explicit_limits():
    """No data at all, but both limits are explicit -- the near-miss case."""
    fig, ax = _fig()
    ax.set_xlim(-2.0, 8.0)
    ax.set_ylim(-1.0, 4.0)
    ax.axvline(1.5)
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    ax.axhspan(1.0, 2.0)
    return fig


def guides_with_only_the_spanned_limit_explicit():
    """The spanned axis is explicit; the guide's own axis autoscales."""
    fig, ax = _fig()
    ax.set_ylim(0.0, 10.0)
    ax.axvline(1.5)
    ax.axvspan(2.0, 3.0)
    return fig


def guides_spanned_axis_resolved_by_other_guides():
    """No data: the y range comes from a *horizontal* guide's own value."""
    fig, ax = _fig()
    ax.axhline(0.0)
    ax.axhline(4.0)
    ax.axvline(1.5)
    ax.axvspan(0.5, 1.0)
    return fig


def guides_fractional_extents():
    """Non-default ``xmin``/``xmax`` / ``ymin``/``ymax`` axes fractions."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.axvline(1.5, ymin=0.25, ymax=0.75)
    ax.axhline(2.0, xmin=0.1, xmax=0.4)
    ax.axvspan(0.5, 1.0, ymin=0.2, ymax=0.6)
    ax.axhspan(3.0, 5.0, xmin=0.3, xmax=0.9)
    return fig


def guides_styled_and_labelled():
    """Colours, dash patterns, widths, alpha and legend keys."""
    fig, ax = _fig()
    ax.plot(X, Y, label="data")
    ax.axvline(1.5, color="red", linestyle="--", linewidth=2.0, label="threshold")
    ax.axhline(2.0, color="#336699", linestyle=":", linewidth=0.5, label="target")
    ax.axvspan(0.5, 1.0, color="orange", alpha=0.35, label="band")
    ax.axhspan(3.0, 5.0, color="lightgray", alpha=1.0)
    ax.legend()
    return fig


def guides_hidden_and_visible_mixed():
    """G11 visibility: a hidden guide materializes into nothing either way."""
    fig, ax = _fig()
    ax.plot(X, Y)
    hidden_line = ax.axvline(1.5)
    hidden_line["visible"] = False
    hidden_span = ax.axhspan(3.0, 5.0)
    hidden_span["visible"] = False
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    return fig


def guides_on_log_axes():
    """Log limits are resolved by ``_apply_log_limits`` before materializing."""
    fig, ax = _fig()
    ax.plot(np.array([1.0, 10.0, 100.0]), np.array([1.0, 10.0, 100.0]))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axvline(20.0)
    ax.axhline(5.0)
    ax.axvspan(2.0, 4.0)
    ax.axhspan(20.0, 40.0)
    return fig


def guides_on_inverted_axes():
    """Descending limits (emitted as ``negate``) still bound the extent."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.set_ylim(9.0, 0.0)
    ax.axvline(1.5)
    ax.axvspan(0.5, 1.0, ymin=0.25, ymax=0.75)
    return fig


def guides_in_a_shared_subplot_grid():
    """Shared-axis synchronization runs before materialization."""
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="rlb")
    for ax in axes:
        ax.plot(X, Y)
        ax.axvline(1.5)
        ax.axhspan(1.0, 2.0)
    return fig


def guides_beside_a_secondary_y_axis():
    """A y2 series must not change what the guides on y span."""
    fig, ax = _fig()
    ax.plot(X, Y, label="left")
    ax.plot(X, Y * 100.0, yaxis="y2", label="right")
    ax.axvline(1.5)
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    return fig


def guides_over_provider_backed_data():
    """Limits resolved from a table at write time (ColumnRef series)."""
    fig, ax = _fig()
    ax.lines.append(
        LineSeries(
            type="line",
            x=None,
            y=None,
            color="BLUE",
            marker=None,
            markersize=0.1,
            linestyle="-",
            linewidth=1.0,
            label="ref",
            yaxis="y",
            offset=0.0,
            data_file="rlb_ref.dat",
            column_names=["x", "y"],
            data_source=ColumnRef("t1", {"x": "k_x", "y": "k_y"}),
        )
    )
    ax.axvline(1.5)
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    ax.axhspan(3.0, 5.0)
    return fig


def _provider():
    return DictDataProvider(
        {
            "t1": TableData(
                keys=["k_x", "k_y"],
                names=["x", "y"],
                columns=[list(X), list(Y)],
            )
        }
    )


#: Builders needing a ``data_provider`` argument to ``_generate_gle_with_files``.
PROVIDERS = {"guides_over_provider_backed_data": _provider}


BUILDERS = [
    guides_over_data,
    guides_with_explicit_limits,
    guides_with_only_the_spanned_limit_explicit,
    guides_spanned_axis_resolved_by_other_guides,
    guides_fractional_extents,
    guides_styled_and_labelled,
    guides_hidden_and_visible_mixed,
    guides_on_log_axes,
    guides_on_inverted_axes,
    guides_in_a_shared_subplot_grid,
    guides_beside_a_secondary_y_axis,
    guides_over_provider_backed_data,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]


def emit(name: str):
    """``(gle_text, data_files)`` for the builder called ``name``."""
    builder = dict(zip(BUILDER_IDS, BUILDERS))[name]
    provider_factory = PROVIDERS.get(name)
    provider = provider_factory() if provider_factory else None
    return builder()._generate_gle_with_files(data_provider=provider)

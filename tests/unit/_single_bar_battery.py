"""Bar figures GLE can already size for itself -- G16's byte-identity guard.

G16 makes gleplot write a bar width (and, where the range would collapse, an
x range) for the bar datasets whose width GLE cannot derive. GLE derives that
width from ``GLEDataPairs::getMinXInterval()`` -- the smallest *positive* gap
between consecutive x values (``graph2.cpp``) -- so the datasets it cannot
size are exactly the ones with no such gap: one point, every x equal, or a
descending x column. Measured on GLE 4.3.10, all three are broken today: the
first two abort with "invalid range for dimension X" and the third compiles
to bar polygons whose every coordinate is ``-nan``.

Every builder here is on the *other* side of that predicate -- GLE finds a
positive interval, sizes the bars itself, and must keep receiving exactly the
script it receives now. ``tests/unit/test_single_bar.py`` asserts each
builder's emission against ``single_bar_neighbour_emissions.json``, a snapshot
captured from the pre-G16 writer (base commit ab65e90).

Between them the builders cross the ways a bar reaches the writer (inline
arrays, a provider-backed ``ColumnRef``, an unresolved file reference), the
spacings most at risk of an over-eager predicate (unit, sub-unit, uneven, a
*repeated* x that still leaves a positive gap elsewhere), and the company a
bar can keep (other series, another bar set, explicit limits, subplots, a
legend, a hidden sibling).
"""

from __future__ import annotations

import numpy as np

import gleplot as glp
from gleplot.series import BarSeries, FileSeries
from gleplot.sources import ColumnRef, DictDataProvider, TableData

X = np.array([1.0, 2.0, 3.0])
H = np.array([10.0, 24.0, 36.0])


def _fig():
    fig = glp.figure(data_prefix="sbb")
    return fig, fig.add_subplot(111)


# -- spacings GLE can measure ------------------------------------------------ #


def two_bars():
    """The smallest bar chart GLE can size: two points, one gap.

    The boundary case of the predicate -- one point fewer and gleplot has to
    supply the width itself.
    """
    fig, ax = _fig()
    ax.bar([1, 2], [5, 3])
    return fig


def five_bars_coloured():
    fig, ax = _fig()
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color="orange")
    ax.set_title("bar")
    return fig


def bars_at_sub_unit_spacing():
    """A gap far below the nominal spacing G16 falls back to."""
    fig, ax = _fig()
    ax.bar([0.0, 0.05, 0.1], [1.0, 2.0, 1.5])
    return fig


def bars_at_uneven_spacing():
    """The minimum gap is not the first gap."""
    fig, ax = _fig()
    ax.bar([0.0, 5.0, 5.25, 12.0], [1.0, 2.0, 1.5, 3.0])
    return fig


def bars_with_a_repeated_x():
    """A zero gap in the middle, and a positive one either side.

    GLE skips the zero and sizes from the rest, so this is a *measurable*
    dataset even though two of its points share an x -- the case a predicate
    written as "any duplicate x" would break.
    """
    fig, ax = _fig()
    ax.bar([1.0, 2.0, 2.0, 3.0], [5.0, 3.0, 4.0, 2.0])
    return fig


def bars_at_large_x():
    """Years, i.e. unit spacing a long way from the origin."""
    fig, ax = _fig()
    ax.bar([2021, 2022, 2023], [4.0, 6.0, 5.0])
    return fig


def bars_over_negative_x():
    fig, ax = _fig()
    ax.bar([-3.0, -2.0, -1.0], [1.0, -2.0, 3.0])
    return fig


# -- the company a bar keeps -------------------------------------------------- #


def bars_with_explicit_limits():
    fig, ax = _fig()
    ax.bar(X, H)
    ax.set_xlim(0.0, 4.0)
    ax.set_ylim(0.0, 40.0)
    return fig


def bars_beside_a_line():
    fig, ax = _fig()
    ax.bar(X, H, color="teal")
    ax.plot([0.0, 4.0], [5.0, 40.0], color="blue")
    return fig


def two_bar_sets():
    """Two independent ``bar`` commands, each its own GLE bar set."""
    fig, ax = _fig()
    ax.bar(X, H, color="red")
    ax.bar(X + 0.3, H * 0.5, color="blue")
    return fig


def bars_with_a_legend():
    fig, ax = _fig()
    ax.bar(X, H, color="green", label="counts")
    ax.legend()
    return fig


def bars_with_custom_column_names():
    fig, ax = _fig()
    ax.bar(X, H, label="counts")
    ax.set_xlabel("bin")
    return fig


def bars_on_a_log_y_axis():
    fig, ax = _fig()
    ax.bar(X, H)
    ax.set_yscale("log")
    return fig


def bars_in_a_shared_subplot_grid():
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="sbb")
    for i, ax in enumerate(axes):
        ax.bar(X, H + i)
    return fig


def a_hidden_single_bar_beside_measurable_bars():
    """The G16 branch behind a visibility gate.

    The hidden series is exactly the shape G16 fixes -- one point -- but it is
    not drawn, so it must contribute neither a width nor an x range: the
    script has to stay the one the visible three-bar series alone produces.
    """
    fig, ax = _fig()
    ax.bar(X, H)
    ax.bar([10.0], [1.0])
    ax.bars[-1]["visible"] = False
    return fig


# -- the other two ways a bar reaches the writer ------------------------------ #


def bars_over_provider_backed_data():
    fig, ax = _fig()
    ax.bars.append(
        BarSeries(
            x=X,
            height=H,
            colors=["RED"] * len(H),
            label=None,
            data_file="sbb_ref.dat",
            column_names=["x", "height"],
            data_source=ColumnRef("t1", {"x": "k_x", "height": "k_h"}),
        )
    )
    return fig


def a_bar_referencing_an_unresolved_file():
    """The recognizer's passthrough shape: a ``FileSeries`` bar (``add_file_series``).

    No in-memory points at all, so the predicate has nothing to measure and
    must not guess -- the statement is re-emitted verbatim (see the report's
    documented gap).
    """
    fig, ax = _fig()
    ax.file_series.append(
        FileSeries(
            series_type="bar",
            data_file="external.dat",
            x_col=1,
            y_col=2,
            color="RED",
            data_error="unresolved",
        )
    )
    ax.set_xlim(0.0, 4.0)
    ax.set_ylim(0.0, 10.0)
    return fig


def _provider():
    return DictDataProvider(
        {
            "t1": TableData(
                keys=["k_x", "k_h"],
                names=["x", "height"],
                columns=[list(X), list(H)],
            )
        }
    )


#: Builders needing a ``data_provider`` argument to ``_generate_gle_with_files``.
PROVIDERS = {"bars_over_provider_backed_data": _provider}


BUILDERS = [
    two_bars,
    five_bars_coloured,
    bars_at_sub_unit_spacing,
    bars_at_uneven_spacing,
    bars_with_a_repeated_x,
    bars_at_large_x,
    bars_over_negative_x,
    bars_with_explicit_limits,
    bars_beside_a_line,
    two_bar_sets,
    bars_with_a_legend,
    bars_with_custom_column_names,
    bars_on_a_log_y_axis,
    bars_in_a_shared_subplot_grid,
    a_hidden_single_bar_beside_measurable_bars,
    bars_over_provider_backed_data,
    a_bar_referencing_an_unresolved_file,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]


def emit(name: str):
    """``(gle_text, data_files)`` for the builder called ``name``."""
    builder = dict(zip(BUILDER_IDS, BUILDERS))[name]
    provider_factory = PROVIDERS.get(name)
    provider = provider_factory() if provider_factory else None
    glp.close()
    return builder()._generate_gle_with_files(data_provider=provider)

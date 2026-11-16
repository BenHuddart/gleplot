"""Figures that sit next to G15's degenerate-range branch without entering it.

G15 stops the writer from emitting ``xaxis min v max v`` for an axis whose
resolved range collapses to a single value, because GLE rejects that outright
("illegal range for xaxis", exit 1) even though it can autoscale such a graph
itself. A degenerate range therefore *never compiled*, which is what makes
"every currently-compiling emission is byte-identical" provable rather than
merely plausible: nothing that used to reach the engine may change.

Every builder here is on the other side of the branch -- each resolves to a
range with ``min != max`` (or to no range at all), so the new code must leave
it exactly as it was. Between them they cross the ways a range gets resolved
(data, explicit bounds, half-explicit bounds, guides, shared axes, log repair,
y2) with the shapes most at risk of an over-eager degeneracy test: spans of
almost nothing, ranges repaired *into* existence by ``_apply_log_limits``, and
axes that legitimately resolve to nothing at all.

``tests/unit/test_degenerate_autoscale.py`` asserts each builder's emission
against ``degenerate_neighbour_emissions.json``, captured from the pre-G15
writer (base commit 1757ce1), and pins the warnings raised on the way -- a
newly silent or newly noisy path is a behaviour change too.
"""

from __future__ import annotations

import warnings

import numpy as np

import gleplot as glp

X = np.array([0.0, 1.0, 2.0, 3.0])
Y = np.array([0.0, 1.0, 4.0, 9.0])


def _fig():
    fig = glp.figure(data_prefix="dgb")
    return fig, fig.add_subplot(111)


# -- the minimal non-degenerate cases --------------------------------------- #


def two_points():
    """The smallest figure with a range at all: two distinct points."""
    fig, ax = _fig()
    ax.plot(np.array([1.0, 2.0]), np.array([2.0, 3.0]))
    return fig


def tiny_but_nonzero_span():
    """A span far below any plausible epsilon, but not zero.

    The degeneracy test has to be exact equality, not a tolerance: this range
    is legal for GLE and must keep being written down.
    """
    fig, ax = _fig()
    ax.plot(np.array([1.0, 1.0000001]), np.array([2.0, 2.0000002]))
    return fig


def data_spanning_zero():
    fig, ax = _fig()
    ax.plot(np.array([-2.0, 0.0, 2.0]), np.array([-1.0, 0.0, 1.0]))
    return fig


# -- explicit and half-explicit bounds --------------------------------------- #


def explicit_limits():
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.set_xlim(-2.0, 8.0)
    ax.set_ylim(-1.0, 12.0)
    return fig


def half_explicit_lower_bound():
    """``set_xlim(v, None)``: the lower bound is the user's, the upper the data's."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.set_xlim(-5.0, None)
    ax.set_ylim(-5.0, None)
    return fig


def half_explicit_upper_bound():
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.set_xlim(None, 12.0)
    ax.set_ylim(None, 20.0)
    return fig


def inverted_axes():
    """Descending limits (written as ``negate``) are never degenerate."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.set_ylim(9.0, 0.0)
    return fig


def no_data_and_no_limits():
    """Both bounds unresolvable -- ``None``, not equal. GLE draws its 0..1 frame."""
    fig, _ax = _fig()
    return fig


def text_only_axes():
    """The SPEC 14.1 blank-project case: an annotation bounds nothing."""
    fig, ax = _fig()
    ax.text(0.5, 0.5, "hello")
    return fig


# -- log axes, whose repair already handles a collapsed range ---------------- #


def log_axes_over_positive_data():
    fig, ax = _fig()
    ax.plot(np.array([1.0, 10.0, 100.0]), np.array([1.0, 10.0, 100.0]))
    ax.set_xscale("log")
    ax.set_yscale("log")
    return fig


def log_axis_over_a_single_point():
    """Degenerate *before* ``_apply_log_limits``, which widens it to a decade.

    The most load-bearing entry in the battery: this range is resolved to
    ``5..5`` and then repaired to ``5..50`` -- a currently-compiling emission
    that a degeneracy test running in the wrong order would silently delete.
    """
    fig, ax = _fig()
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.set_xscale("log")
    ax.set_yscale("log")
    return fig


def log_axis_over_nonpositive_data():
    """The other ``_apply_log_limits`` repair path (zero in the data)."""
    fig, ax = _fig()
    ax.plot(np.array([0.0, 1.0, 10.0]), np.array([0.0, 1.0, 10.0]))
    ax.set_yscale("log")
    return fig


# -- series types that carry their own range needs --------------------------- #


def bars():
    """Bars need an explicit x range from gleplot; GLE cannot autoscale them."""
    fig, ax = _fig()
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color="orange")
    return fig


def errorbars():
    fig, ax = _fig()
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.5, xerr=0.2, marker="o", capsize=4)
    return fig


def scatter_and_fill():
    fig, ax = _fig()
    ax.scatter(X, Y, marker="o")
    ax.fill_between(X, Y, Y + 2.0)
    return fig


def guides_over_data():
    """Guides materialize against limits the data already resolved."""
    fig, ax = _fig()
    ax.plot(X, Y)
    ax.axvline(1.5)
    ax.axhline(2.0)
    ax.axvspan(0.5, 1.0)
    ax.axhspan(3.0, 5.0)
    return fig


# -- the two paths that resolve limits somewhere other than a single axes ---- #


def shared_x_subplots():
    """``_synchronize_x_limits`` unifies the panels before anything is written."""
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="dgb")
    for i, ax in enumerate(axes):
        ax.plot(X, Y + i)
    return fig


def secondary_y_axis_auto():
    """y2 carries data but no limits: nothing to emit, and nothing to defer."""
    fig, ax = _fig()
    ax.plot(X, Y, label="left")
    ax.plot(X, Y * 100.0 + 1.0, yaxis="y2", label="right")
    return fig


def secondary_y_axis_explicit():
    fig, ax = _fig()
    ax.plot(X, Y, label="left")
    ax.plot(X, Y * 100.0 + 1.0, yaxis="y2", label="right")
    ax.set_ylim(0.0, 1000.0, axis="y2")
    return fig


BUILDERS = [
    two_points,
    tiny_but_nonzero_span,
    data_spanning_zero,
    explicit_limits,
    half_explicit_lower_bound,
    half_explicit_upper_bound,
    inverted_axes,
    no_data_and_no_limits,
    text_only_axes,
    log_axes_over_positive_data,
    log_axis_over_a_single_point,
    log_axis_over_nonpositive_data,
    bars,
    errorbars,
    scatter_and_fill,
    guides_over_data,
    shared_x_subplots,
    secondary_y_axis_auto,
    secondary_y_axis_explicit,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]


def emit(name: str):
    """``(gle_text, data_files, warning_messages)`` for the builder ``name``.

    The warnings are part of the snapshot: ``_apply_log_limits`` speaks up when
    it repairs a range, and a change that made it stop -- or made a quiet path
    start -- would be a behaviour change no byte comparison could see.
    """
    builder = dict(zip(BUILDER_IDS, BUILDERS))[name]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        text, files = builder()._generate_gle_with_files()
    return text, files, [str(w.message) for w in caught]

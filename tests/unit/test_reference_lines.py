"""Unit tests for axvline/axhline/axvspan/axhspan.

Mirrors the ``tests/unit/test_plotting.py`` style -- assert the object-model
dicts each API call stores AND substrings of the generated GLE. The
interesting behaviour is that these are *declarations* until write time: the
concrete two-point datasets are built from the axis limits in force when the
figure is generated, so a ``set_ylim`` issued after ``axvline`` still wins.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp


X = np.array([0.0, 1.0, 2.0, 3.0])
Y = np.array([0.0, 1.0, 4.0, 9.0])


def _rows(files, name):
    """Parse a generated sidecar into a list of float rows (header skipped)."""
    lines = [ln for ln in files[name].strip().splitlines() if ln.strip()]
    out = []
    for ln in lines:
        try:
            out.append([float(tok) for tok in ln.split()])
        except ValueError:
            continue  # header row
    return out


def _fig():
    fig = glp.figure(data_prefix="rl")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    return fig, ax


# --------------------------------------------------------------------------- #
# Stored declarations
# --------------------------------------------------------------------------- #


def test_axvline_stores_declaration():
    fig, ax = _fig()
    entry = ax.axvline(1.5, color="red", linestyle="--", linewidth=2, label="Tn")

    assert entry is ax.reflines[0]
    assert entry["type"] == "refline"
    assert entry["orient"] == "v"
    assert entry["value"] == 1.5
    assert entry["span_lo"] == 0.0 and entry["span_hi"] == 1.0
    assert entry["color"] == "RED"
    assert entry["linestyle"] == "--"
    assert entry["linewidth"] == 2
    assert entry["label"] == "Tn"
    assert entry["data_file"].endswith(".dat")


def test_axhline_stores_declaration():
    fig, ax = _fig()
    entry = ax.axhline(2.0, xmin=0.25, xmax=0.75)
    assert entry["orient"] == "h"
    assert entry["value"] == 2.0
    assert entry["span_lo"] == 0.25 and entry["span_hi"] == 0.75
    assert entry["color"] == "BLACK"  # default


def test_axvspan_stores_declaration():
    fig, ax = _fig()
    entry = ax.axvspan(1.0, 2.0, color="lightgray", alpha=0.5)
    assert entry is ax.spans[0]
    assert entry["type"] == "span"
    assert entry["orient"] == "v"
    assert entry["start"] == 1.0 and entry["end"] == 2.0
    assert entry["color"] == "LIGHTGRAY"
    assert entry["alpha"] == 0.5


def test_axhspan_stores_declaration():
    fig, ax = _fig()
    entry = ax.axhspan(1.0, 3.0)
    assert entry["orient"] == "h"
    assert entry["start"] == 1.0 and entry["end"] == 3.0
    assert entry["color"] == "LIGHTGRAY"  # default


def test_out_of_range_fractions_raise():
    fig, ax = _fig()
    with pytest.raises(ValueError):
        ax.axvline(1.0, ymin=-0.1)
    with pytest.raises(ValueError):
        ax.axhline(1.0, xmax=1.5)
    with pytest.raises(ValueError):
        ax.axvspan(1.0, 2.0, ymax=2.0)


# --------------------------------------------------------------------------- #
# Materialization against the axis limits in force at write time
# --------------------------------------------------------------------------- #


def test_axvline_spans_the_full_y_range():
    fig, ax = _fig()
    ax.set_ylim(-10.0, 10.0)
    entry = ax.axvline(1.5)
    _text, files = fig._generate_gle_with_files()

    rows = _rows(files, entry["data_file"])
    assert rows == [[1.5, -10.0], [1.5, 10.0]]


def test_axvline_respects_a_later_set_ylim():
    """The declaration is realized at write time, not at call time."""
    fig, ax = _fig()
    entry = ax.axvline(1.5)
    ax.set_ylim(-1.0, 1.0)  # AFTER the axvline call
    _text, files = fig._generate_gle_with_files()

    rows = _rows(files, entry["data_file"])
    assert rows == [[1.5, -1.0], [1.5, 1.0]]


def test_axhline_fractional_extent_maps_onto_the_x_range():
    fig, ax = _fig()
    ax.set_xlim(0.0, 4.0)
    entry = ax.axhline(2.0, xmin=0.25, xmax=0.75)
    _text, files = fig._generate_gle_with_files()

    rows = _rows(files, entry["data_file"])
    assert rows == [[1.0, 2.0], [3.0, 2.0]]


def test_axvspan_becomes_a_fill_between_band():
    fig, ax = _fig()
    ax.set_ylim(0.0, 10.0)
    entry = ax.axvspan(1.0, 2.0, ymin=0.0, ymax=0.5)
    text, files = fig._generate_gle_with_files()

    # x, upper, lower
    assert _rows(files, entry["data_file"]) == [[1.0, 5.0, 0.0], [2.0, 5.0, 0.0]]
    assert "fill d1,d2 color LIGHTGRAY" in text


def test_axhspan_becomes_a_fill_between_band():
    fig, ax = _fig()
    ax.set_xlim(0.0, 4.0)
    entry = ax.axhspan(1.0, 3.0)
    _text, files = fig._generate_gle_with_files()
    assert _rows(files, entry["data_file"]) == [[0.0, 3.0, 1.0], [4.0, 3.0, 1.0]]


def test_writing_twice_does_not_duplicate_content():
    """Materialization must not mutate the axes (repeated saves are common)."""
    fig, ax = _fig()
    ax.axvline(1.5)
    ax.axvspan(1.0, 2.0)
    first, _ = fig._generate_gle_with_files()
    second, _ = fig._generate_gle_with_files()

    assert len(ax.reflines) == 1 and len(ax.spans) == 1
    assert len(ax.lines) == 1 and len(ax.fills) == 0
    assert first == second


# --------------------------------------------------------------------------- #
# Autoscaling
# --------------------------------------------------------------------------- #


def test_vertical_guides_extend_the_x_autoscale():
    fig = glp.figure(data_prefix="rl")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    ax.axvline(-5.0)
    ax.axvspan(8.0, 9.0)
    fig._generate_gle_with_files()
    assert ax.xmin == -5.0
    assert ax.xmax == 9.0


def test_horizontal_guides_extend_the_y_autoscale():
    fig = glp.figure(data_prefix="rl")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    ax.axhline(-3.0)
    ax.axhspan(20.0, 25.0)
    fig._generate_gle_with_files()
    assert ax.ymin == -3.0
    assert ax.ymax == 25.0


def test_fractional_extent_does_not_feed_back_into_autoscale():
    """axhline's x extent is an axes fraction, so it must not autoscale x."""
    fig = glp.figure(data_prefix="rl")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    ax.axhline(2.0, xmin=0.0, xmax=1.0)
    fig._generate_gle_with_files()
    assert ax.xmin == 0.0 and ax.xmax == 3.0


def test_guide_without_resolvable_limits_warns_and_is_dropped():
    fig = glp.figure(data_prefix="rl")
    ax = fig.add_subplot(111)
    ax.axvline(1.0)  # nothing else on the axes -> no y range to span
    with pytest.warns(UserWarning, match="axvline"):
        text, _files = fig._generate_gle_with_files()
    assert "data rl_" not in text


# --------------------------------------------------------------------------- #
# Layering, legend and serialization
# --------------------------------------------------------------------------- #


def test_guides_are_drawn_underneath_the_data():
    fig, ax = _fig()
    ax.set_ylim(0.0, 10.0)
    span = ax.axvspan(1.0, 2.0)
    ref = ax.axhline(5.0)
    text, _files = fig._generate_gle_with_files()
    # Search inside the graph block: the metadata header lists every sidecar
    # in sorted order, which is not the emission order.
    body = text[text.index("begin graph") :]

    order = [
        body.index(span["data_file"]),
        body.index(ref["data_file"]),
        body.index(ax.lines[0]["data_file"]),
    ]
    assert order == sorted(order)


def test_labelled_guide_shows_up_in_the_legend():
    fig, ax = _fig()
    ax.set_ylim(0.0, 10.0)
    ax.axvline(1.5, label="transition")
    text, _files = fig._generate_gle_with_files()
    assert 'key "transition"' in text
    assert "key pos" in text


def test_round_trip_through_to_dict():
    fig, ax = _fig()
    ax.axvline(1.5, color="red", linestyle=":")
    ax.axhspan(1.0, 2.0, color="lightgray")
    restored = glp.Figure.from_dict(fig.to_dict())

    assert restored.axes_list[0].reflines == ax.reflines
    assert restored.axes_list[0].spans == ax.spans


def test_figure_level_convenience_methods():
    fig = glp.figure(data_prefix="rl")
    fig.add_subplot(111).plot(X, Y)
    fig.axvline(1.0)
    fig.axhline(1.0)
    fig.axvspan(1.0, 2.0)
    fig.axhspan(1.0, 2.0)
    ax = fig.axes_list[0]
    assert len(ax.reflines) == 2 and len(ax.spans) == 2

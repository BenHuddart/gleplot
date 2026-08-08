"""G14: a guide on an axis that resolves to nothing spans GLE's own 0..1.

Before G14, ``axvline`` on an otherwise-empty axes emitted *nothing* plus a
``UserWarning``: with no data and no ``set_ylim`` there was no y range to span,
so the guide was dropped. It is now materialized over
:data:`gleplot.axes.EMPTY_AXIS_FALLBACK_RANGE`, which is the range GLE renders
for a graph block that gives no bounds (engine-verified in
``tests/integration/test_refline_fallback_compiles.py``) -- so the guide lands
across the frame the reader actually sees.

The other half of the task is that *nothing else moved*: every figure in
``_refline_battery`` has resolvable limits and must emit exactly the bytes the
pre-G14 writer produced, which ``refline_resolvable_emissions.json`` (captured
on base commit 83dcdd9) pins.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.axes import EMPTY_AXIS_FALLBACK_RANGE

from . import _refline_battery as rb


SNAPSHOT_PATH = Path(__file__).parent / "refline_resolvable_emissions.json"
SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _rows(files, name):
    """Parse a generated sidecar into a list of float rows (header skipped)."""
    out = []
    for line in files[name].strip().splitlines():
        if not line.strip():
            continue
        try:
            out.append([float(tok) for tok in line.split()])
        except ValueError:
            continue  # header row
    return out


def _empty_axes():
    fig = glp.figure(data_prefix="fb")
    return fig, fig.add_subplot(111)


def _generate(fig):
    """Generate, asserting no warning is raised on the way (G14 retired it)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        text, files = fig._generate_gle_with_files()
    assert [str(w.message) for w in caught] == []
    return text, files


# --------------------------------------------------------------------------- #
# The fallback itself
# --------------------------------------------------------------------------- #


def test_fallback_range_is_gles_own_empty_graph_range():
    """Pinned numerically here; pinned against the engine in the gle suite."""
    assert EMPTY_AXIS_FALLBACK_RANGE == (0.0, 1.0)


def test_axvline_on_an_empty_axes_emits_a_two_point_dataset_spanning_0_to_1():
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.5, 0.0], [0.5, 1.0]]
    assert entry["data_file"] in text


def test_axhline_on_an_empty_axes_spans_0_to_1_in_x():
    fig, ax = _empty_axes()
    entry = ax.axhline(0.5)
    _text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.0, 0.5], [1.0, 0.5]]


def test_axvspan_on_an_empty_axes_spans_0_to_1_in_y():
    fig, ax = _empty_axes()
    entry = ax.axvspan(0.4, 0.6)
    _text, files = _generate(fig)

    # fill sidecar rows are (x, upper, lower)
    assert _rows(files, entry["data_file"]) == [
        [0.4, 1.0, 0.0],
        [0.6, 1.0, 0.0],
    ]


def test_axhspan_on_an_empty_axes_spans_0_to_1_in_x():
    fig, ax = _empty_axes()
    entry = ax.axhspan(0.4, 0.6)
    _text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [
        [0.0, 0.6, 0.4],
        [1.0, 0.6, 0.4],
    ]


def test_the_fractional_extent_is_taken_against_the_fallback_range():
    """The 40%-60% placeholder band of SPEC 14.3 lands on 0.4..0.6."""
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5, ymin=0.4, ymax=0.6)
    _text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.5, 0.4], [0.5, 0.6]]


def test_a_half_specified_range_keeps_the_bound_it_has():
    """Substitution is per bound, not all-or-nothing."""
    fig, ax = _empty_axes()
    ax.set_ylim(-3.0, None)
    entry = ax.axvline(0.5)
    _text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.5, -3.0], [0.5, 1.0]]


def test_a_hidden_guide_still_materializes_into_nothing():
    """G11 visibility outranks the fallback: hidden means absent."""
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    entry["visible"] = False
    text, files = _generate(fig)

    assert files == {}
    assert "\n    data " not in text


def test_no_warning_is_raised_where_the_guide_used_to_be_dropped():
    """The G14 warning is retired -- not merely reworded."""
    for build in (
        lambda ax: ax.axvline(0.5),
        lambda ax: ax.axhline(0.5),
        lambda ax: ax.axvspan(0.4, 0.6),
        lambda ax: ax.axhspan(0.4, 0.6),
    ):
        fig, ax = _empty_axes()
        build(ax)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            fig._generate_gle_with_files()


def test_materialization_reruns_per_write_so_later_data_wins():
    """The fallback is a write-time stand-in, never stored on the axes."""
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    _text, files = _generate(fig)
    assert _rows(files, entry["data_file"]) == [[0.5, 0.0], [0.5, 1.0]]

    ax.plot(np.array([0.0, 1.0]), np.array([10.0, 20.0]))
    _text, files = _generate(fig)
    assert _rows(files, entry["data_file"]) == [[0.5, 10.0], [0.5, 20.0]]


def test_resolved_limits_are_never_overridden_by_the_fallback():
    fig, ax = _empty_axes()
    ax.set_ylim(100.0, 200.0)
    entry = ax.axvline(0.5)
    _text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.5, 100.0], [0.5, 200.0]]


# --------------------------------------------------------------------------- #
# Byte-level regression guard for every resolvable-limits path
# --------------------------------------------------------------------------- #


def test_the_snapshot_covers_the_whole_battery():
    assert sorted(SNAPSHOT) == sorted(rb.BUILDER_IDS)


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_resolvable_limits_emit_byte_identically_to_pre_g14(name):
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        text, files = rb.emit(name)

    reference = SNAPSHOT[name]
    assert text == reference["gle"]
    assert files == reference["files"]

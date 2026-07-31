"""The matplotlib->GLE marker table covers matplotlib's string marker set.

gleplot claims matplotlib compatibility but does not depend on matplotlib, so
the reference set below is transcribed from ``matplotlib.markers.MarkerStyle
.markers`` (matplotlib 3.x) rather than imported. Every *drawable string*
code in it must resolve to a real GLE marker; the integer tick and caret
markers (0-11) are deliberately unmapped -- GLE has no line-segment or caret
glyph -- and the "nothing" markers (``''``, ``' '``, ``'None'``) are not
markers at all.

``'d'`` (thin diamond) was missing until 1.9.0 and silently fell back to
FCIRCLE, drawing a circle where a diamond was asked for; ``'8'`` and
``'1'``-``'4'`` had the same fate.
"""

from __future__ import annotations

import pytest

from gleplot.markers import (
    GLE_MARKER_TYPES,
    MATPLOTLIB_TO_GLE_MARKERS,
    get_gle_marker,
)
from gleplot.parser import tables

#: matplotlib.markers.MarkerStyle.markers, string keys only, with the
#: descriptions matplotlib gives them.
MPL_STRING_MARKERS = {
    ".": "point",
    ",": "pixel",
    "o": "circle",
    "v": "triangle_down",
    "^": "triangle_up",
    "<": "triangle_left",
    ">": "triangle_right",
    "1": "tri_down",
    "2": "tri_up",
    "3": "tri_left",
    "4": "tri_right",
    "8": "octagon",
    "s": "square",
    "p": "pentagon",
    "P": "plus_filled",
    "*": "star",
    "h": "hexagon1",
    "H": "hexagon2",
    "+": "plus",
    "x": "x",
    "X": "x_filled",
    "D": "diamond",
    "d": "thin_diamond",
    "|": "vline",
    "_": "hline",
}

#: Integer tick (0-3) and caret (4-11) markers: judged non-mappable.
MPL_NON_MAPPABLE = tuple(range(12))


@pytest.mark.parametrize(
    "code", sorted(MPL_STRING_MARKERS), ids=lambda c: MPL_STRING_MARKERS[c]
)
def test_every_matplotlib_string_marker_is_mapped(code):
    assert code in MATPLOTLIB_TO_GLE_MARKERS, (
        f"matplotlib marker {code!r} ({MPL_STRING_MARKERS[code]}) has no GLE "
        "mapping and would fall back to a circle"
    )


def test_table_maps_nothing_matplotlib_does_not_define():
    assert set(MATPLOTLIB_TO_GLE_MARKERS) == set(MPL_STRING_MARKERS)


@pytest.mark.parametrize("code", sorted(MATPLOTLIB_TO_GLE_MARKERS))
def test_every_target_is_a_real_gle_marker(code):
    gle_name = MATPLOTLIB_TO_GLE_MARKERS[code]
    assert gle_name in tables.MARKERS  # GLE 4.3.10's stdmark table
    assert gle_name in GLE_MARKER_TYPES  # ...and one gleplot documents


# --------------------------------------------------------------------------- #
# the specific gaps closed in 1.9.0
# --------------------------------------------------------------------------- #


def test_thin_diamond_is_a_diamond():
    assert get_gle_marker("d") == "DIAMOND"


def test_thin_diamond_stays_distinct_from_diamond():
    """'D' and 'd' are case-significant in matplotlib; keep them apart."""
    assert get_gle_marker("D") != get_gle_marker("d")


@pytest.mark.parametrize(
    "code,expected",
    [
        ("8", "FCIRCLE"),
        ("1", "TRIANGLED"),
        ("2", "TRIANGLE"),
        ("3", "TRIANGLE"),
        ("4", "TRIANGLE"),
    ],
)
def test_remaining_added_codes(code, expected):
    assert get_gle_marker(code) == expected


@pytest.mark.parametrize("code", MPL_NON_MAPPABLE)
def test_tick_and_caret_markers_fall_back_rather_than_pretend(code):
    """No GLE glyph is a tick or a caret; take the default instead."""
    assert get_gle_marker(code) == "FCIRCLE"
    assert get_gle_marker(code, default="SQUARE") == "SQUARE"


# --------------------------------------------------------------------------- #
# the parser's inverse map must not drift
# --------------------------------------------------------------------------- #


def test_new_codes_round_trip_through_the_inverse_map():
    """mpl -> GLE -> mpl -> GLE lands on the same GLE glyph."""
    for code in MATPLOTLIB_TO_GLE_MARKERS:
        gle_name = MATPLOTLIB_TO_GLE_MARKERS[code]
        back = tables.GLE_MARKER_TO_MATPLOTLIB[gle_name]
        assert MATPLOTLIB_TO_GLE_MARKERS[back] == gle_name


def test_established_canonical_inverses_are_unchanged():
    """Appending codes must not steal an existing GLE name's inverse."""
    assert tables.GLE_MARKER_TO_MATPLOTLIB["TRIANGLE"] == "<"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["DIAMOND"] == "h"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["FCIRCLE"] == "o"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["FDIAMOND"] == "D"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["PLUS"] == "+"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["PCROSS"] == "x"
    assert tables.GLE_MARKER_TO_MATPLOTLIB["DOT"] == "."

"""Unit tests for open/outline marker support.

Mirrors the ``tests/unit/test_plotting.py`` style -- assert the object-model
dicts each API call stores AND substrings of the generated GLE. Covers the
three GLE fill families (solid / transparent outline / white-filled), both
matplotlib spellings that select an open marker (``fillstyle='none'`` and
``markerfacecolor='none'``, plus the ``mfc`` alias), literal GLE marker-name
passthrough, and the warning that replaced the old silent fallback.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot import markers as mk


X = np.array([0.0, 1.0, 2.0])
Y = np.array([1.0, 2.0, 3.0])


def _gle(fig):
    text, _files = fig._generate_gle_with_files()
    return text


# --------------------------------------------------------------------------- #
# markers.get_gle_marker / apply_marker_fill
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "code,solid,outline,white",
    [
        ("o", "FCIRCLE", "CIRCLE", "WCIRCLE"),
        ("s", "FSQUARE", "SQUARE", "WSQUARE"),
        ("^", "FTRIANGLE", "TRIANGLE", "WTRIANGLE"),
        ("v", "FTRIANGLED", "TRIANGLED", "WTRIANGLED"),
        ("D", "FDIAMOND", "DIAMOND", "WDIAMOND"),
        ("*", "FSTARR", "STARR", "WSTARR"),
    ],
)
def test_fill_families(code, solid, outline, white):
    assert mk.get_gle_marker(code) == solid
    assert mk.get_gle_marker(code, fill="full") == solid
    assert mk.get_gle_marker(code, fill="none") == outline
    assert mk.get_gle_marker(code, fill="white") == white


def test_shapes_without_a_fill_variant_are_unchanged():
    # PLUS/PCROSS/DOT are strokes, not areas: GLE has no filled/open pair.
    for code in ("+", "x", "."):
        solid = mk.get_gle_marker(code)
        assert mk.get_gle_marker(code, fill="none") == solid
        assert mk.get_gle_marker(code, fill="white") == solid


def test_full_fill_preserves_historical_mapping_verbatim():
    # These entries already point at outline shapes because GLE has no filled
    # counterpart; fill='full' must not "helpfully" normalize them.
    assert mk.get_gle_marker("<") == "TRIANGLE"
    assert mk.get_gle_marker("p") == "STARR"
    assert mk.get_gle_marker("h") == "DIAMOND"


def test_literal_gle_marker_name_passes_through():
    assert mk.get_gle_marker("wcircle") == "WCIRCLE"
    assert mk.get_gle_marker("OPLUS") == "OPLUS"
    # ...and is still subject to the requested fill.
    assert mk.get_gle_marker("fcircle", fill="none") == "CIRCLE"


def test_unknown_marker_warns_instead_of_falling_back_silently():
    with pytest.warns(UserWarning, match="Unrecognized marker"):
        assert mk.get_gle_marker("INVALID") == "FCIRCLE"


def test_invalid_fill_raises():
    with pytest.raises(ValueError):
        mk.get_gle_marker("o", fill="hatched")
    with pytest.raises(ValueError):
        mk.apply_marker_fill("FCIRCLE", fill="hatched")


def test_none_marker_returns_none():
    assert mk.get_gle_marker(None) is None
    assert mk.get_gle_marker("None") is None


def test_outline_and_white_tables_cover_every_code():
    assert set(mk.MATPLOTLIB_TO_GLE_OUTLINE_MARKERS) == set(
        mk.MATPLOTLIB_TO_GLE_MARKERS
    )
    assert set(mk.MATPLOTLIB_TO_GLE_WHITE_MARKERS) == set(mk.MATPLOTLIB_TO_GLE_MARKERS)


def test_every_emitted_marker_name_is_a_real_gle_marker():
    from gleplot.parser.tables import MARKERS

    for table in (
        mk.MATPLOTLIB_TO_GLE_MARKERS,
        mk.MATPLOTLIB_TO_GLE_OUTLINE_MARKERS,
        mk.MATPLOTLIB_TO_GLE_WHITE_MARKERS,
    ):
        for name in table.values():
            assert name in MARKERS


def test_is_valid_gle_marker_accepts_any_case():
    assert mk.is_valid_gle_marker("wcircle")
    assert mk.is_valid_gle_marker("FCIRCLE")
    assert not mk.is_valid_gle_marker("NOTAMARKER")
    assert not mk.is_valid_gle_marker("")


# --------------------------------------------------------------------------- #
# markers.resolve_marker_fill
# --------------------------------------------------------------------------- #


def test_resolve_marker_fill_spellings():
    assert mk.resolve_marker_fill() == "full"
    assert mk.resolve_marker_fill(fillstyle="none") == "none"
    assert mk.resolve_marker_fill(fillstyle="full") == "full"
    assert mk.resolve_marker_fill(markerfacecolor="none") == "none"
    assert mk.resolve_marker_fill(markerfacecolor="white") == "white"
    assert mk.resolve_marker_fill(markerfacecolor="w") == "white"
    assert mk.resolve_marker_fill(markerfacecolor="#FFFFFF") == "white"


def test_resolve_marker_fill_fillstyle_wins_over_facecolor():
    assert mk.resolve_marker_fill(fillstyle="full", markerfacecolor="none") == "full"


def test_resolve_marker_fill_warns_on_unsupported_values():
    with pytest.warns(UserWarning, match="fillstyle"):
        assert mk.resolve_marker_fill(fillstyle="left") == "full"
    with pytest.warns(UserWarning, match="markerfacecolor"):
        assert mk.resolve_marker_fill(markerfacecolor="red") == "full"


# --------------------------------------------------------------------------- #
# Axes plotting methods
# --------------------------------------------------------------------------- #


def test_plot_fillstyle_none_stores_and_emits_outline_marker():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, linestyle="none", marker="o", fillstyle="none")

    assert ax.scatters[0]["marker"] == "CIRCLE"
    assert "marker CIRCLE" in _gle(fig)


def test_plot_markerfacecolor_none_matches_fillstyle_none():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, marker="s", markerfacecolor="none")
    assert ax.lines[0]["marker"] == "SQUARE"


def test_plot_mfc_alias():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, marker="s", mfc="none")
    assert ax.lines[0]["marker"] == "SQUARE"
    # The alias must not leak into the series dict.
    assert "mfc" not in ax.lines[0]


def test_scatter_open_markers():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.scatter(X, Y, marker="D", fillstyle="none")
    assert ax.scatters[0]["marker"] == "DIAMOND"


def test_scatter_white_markers():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.scatter(X, Y, marker="o", markerfacecolor="white")
    assert ax.scatters[0]["marker"] == "WCIRCLE"


def test_errorbar_open_markers():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.errorbar(X, Y, yerr=0.1, fmt="none", marker="^", fillstyle="none")
    assert ax.errorbars[0]["marker"] == "TRIANGLE"
    assert "marker TRIANGLE" in _gle(fig)


def test_errorbar_from_file_open_markers(tmp_path):
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.errorbar_from_file("some.dat", 1, 2, yerr_col=3, marker="o", mfc="none")
    assert ax.file_series[0]["marker"] == "CIRCLE"


def test_filled_default_is_unchanged():
    fig = glp.figure(data_prefix="om")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, linestyle="none", marker="o")
    assert ax.scatters[0]["marker"] == "FCIRCLE"

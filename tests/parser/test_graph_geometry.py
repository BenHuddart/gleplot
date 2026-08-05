"""Graph geometry: recognition, modelling and re-emission.

Graph-level ``size`` / ``scale`` / ``fullsize`` used to be parsed into two
recognizer fields (``info["size_cm"]`` / ``info["scale_mode"]``) that nothing
ever read: a hand-written ``fullsize`` figure silently re-saved as
``scale auto``. These tests pin the replacement contract down:

* the invertible triple ``amove x y`` + ``size w h`` + ``scale 1 1`` becomes
  :attr:`Axes.placement` (a page-cm frame rect, SPEC 3.3) and re-emits as the
  same three statements;
* every other real geometry (``fullsize``, ``scale h v``, a bare ``size``) is
  kept verbatim in :attr:`Axes.geometry_passthrough`, re-emitted in the
  geometry slot, and reported with a ``layout:`` warning;
* ``scale auto`` / absent geometry stays auto ("GLE decides"), which is what
  every figure built through the scripting API carries -- so the writer's
  default emission is untouched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure, GLEGraphConfig, axes as _gleplot_axes
from gleplot.parser.recognizer import parse_gle_figure


@pytest.fixture(autouse=True)
def _reset_counter():
    _gleplot_axes._global_data_file_counter = 0
    glp.close()
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        glp.close()


def _canonical(tmp_path: Path) -> str:
    """A single-plot figure saved by gleplot itself -> its GLE text.

    Starting from the writer's own output means the fixtures below differ
    from a re-save ONLY in the geometry statements under test, so a
    byte-identity assertion is a statement about geometry and nothing else.
    """
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 0.0]), label="w")
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 1)
    fig.savefig_gle(str(tmp_path / "canonical.gle"))
    return (tmp_path / "canonical.gle").read_text(encoding="utf-8")


def _write(tmp_path: Path, text: str, name: str = "hand.gle") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _resave(figure, tmp_path: Path, name: str = "again.gle") -> str:
    out = tmp_path / name
    figure.savefig_gle(str(out))
    return out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Modelled: the invertible amove/size/scale-1-1 triple
# --------------------------------------------------------------------------- #


def test_invertible_triple_becomes_a_placement_rect(tmp_path):
    src = _canonical(tmp_path).replace(
        "begin graph\n    scale auto\n",
        "amove 2 3\nbegin graph\n    size 12 8\n    scale 1 1\n",
    )
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement == (2.0, 3.0, 12.0, 8.0)
    assert ax.geometry_passthrough == []
    # Fully modelled -> nothing to warn about.
    assert [w for w in rec.warnings if w.startswith("layout:")] == []


def test_invertible_triple_round_trips_byte_identically(tmp_path):
    src = _canonical(tmp_path).replace(
        "begin graph\n    scale auto\n",
        "amove 2 3\nbegin graph\n    size 12 8\n    scale 1 1\n",
    )
    rec = parse_gle_figure(_write(tmp_path, src))
    assert _resave(rec.figure, tmp_path) == src


def test_placement_emits_the_triple_for_a_scripted_figure(tmp_path):
    """The writer honours the model, whoever set it (GUI, script, parser)."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    ax.placement = (1.5, 2.5, 10.0, 7.0)

    text = _resave(fig, tmp_path, "placed.gle")
    assert "amove 1.5 2.5\nbegin graph\n    size 10 7\n    scale 1 1\n" in text
    assert "scale auto" not in text


# --------------------------------------------------------------------------- #
# Preserved: geometry that inverts to no rect
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "geometry",
    [
        "    fullsize",
        "    scale 0.8 0.8",
        "    size 8 6",
        "    size 8 6\n    scale 0.9 0.9",
    ],
    ids=["fullsize", "scale-factors", "bare-size", "size-and-factors"],
)
def test_unmodelled_geometry_survives_byte_identically_and_warns(geometry, tmp_path):
    src = _canonical(tmp_path).replace("    scale auto", geometry)
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.geometry_passthrough == geometry.split("\n")
    assert ax.placement is None
    assert any(w.startswith("layout:") for w in rec.warnings)

    # ... and it is re-emitted in the geometry slot, not normalized away.
    assert _resave(rec.figure, tmp_path) == src


def test_a_fullsize_figure_gleplot_itself_wrote_round_trips(tmp_path):
    """``GLEGraphConfig.scale_mode`` is a writer default, not per-axes state.

    It is not recovered as a config field -- but the geometry it emitted is
    kept per-axes and re-emitted, so the GLE text is a fixed point.
    """
    fig = Figure(
        figsize=(8, 6),
        graph=GLEGraphConfig(scale_mode="fullsize"),
        data_prefix="geom",
    )
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    src = _resave(fig, tmp_path, "fullsize.gle")
    assert "begin graph\n    fullsize\n" in src

    rec = parse_gle_figure(tmp_path / "fullsize.gle")
    assert rec.figure.axes_list[0].geometry_passthrough == ["    fullsize"]
    assert _resave(rec.figure, tmp_path, "fullsize2.gle") == src


def test_a_colorbar_figures_reserved_width_stays_derived(tmp_path):
    """The single-plot colorbar ``size`` line is model-derived, not geometry.

    The writer computes it from the recovered colorbar, so capturing it would
    only duplicate model state; the emitted line is identical either way.
    """
    from tests.parser import _golden_battery as golden

    fig = golden.heatmap_imshow_colorbar()
    src = _resave(fig, tmp_path, "cbar.gle")
    assert "\n    size " in src  # the reserved-width line under test

    rec = parse_gle_figure(tmp_path / "cbar.gle")
    ax = rec.figure.axes_list[0]
    assert ax.geometry_passthrough == []
    assert ax.placement is None
    assert [w for w in rec.warnings if w.startswith("layout:")] == []
    assert _resave(rec.figure, tmp_path, "cbar2.gle") == src


def test_a_hand_written_size_on_a_colorbar_figure_is_kept(tmp_path):
    """... but a size that is NOT the derived one is preserved, not replaced."""
    from tests.parser import _golden_battery as golden

    fig = golden.heatmap_imshow_colorbar()
    src = _resave(fig, tmp_path, "cbar.gle")
    line = next(ln for ln in src.splitlines() if ln.startswith("    size "))
    hand = src.replace(line, "    size 11 5")
    rec = parse_gle_figure(_write(tmp_path, hand, "cbar_hand.gle"))

    assert rec.figure.axes_list[0].geometry_passthrough == ["    size 11 5"]
    assert any(w.startswith("layout:") for w in rec.warnings)
    assert _resave(rec.figure, tmp_path, "cbar_hand2.gle") == hand


def test_geometry_passthrough_keeps_the_original_spelling(tmp_path):
    """Hand-written indentation/casing is preserved verbatim, not canonicalized."""
    src = _canonical(tmp_path).replace("    scale auto", "  FULLSIZE")
    rec = parse_gle_figure(_write(tmp_path, src))

    assert rec.figure.axes_list[0].geometry_passthrough == ["  FULLSIZE"]
    assert _resave(rec.figure, tmp_path) == src


def test_an_amove_that_is_not_a_placement_is_preserved_and_warned(tmp_path):
    """``amove`` + non-invertible geometry: the position still positions."""
    src = _canonical(tmp_path).replace(
        "begin graph\n    scale auto\n",
        "amove 2 3\nbegin graph\n    fullsize\n",
    )
    rec = parse_gle_figure(_write(tmp_path, src))

    assert rec.figure.axes_list[0].placement is None
    assert "amove 2 3" in rec.figure.passthrough_header
    assert any("amove" in w for w in rec.warnings if w.startswith("layout:"))
    assert _resave(rec.figure, tmp_path) == src


# --------------------------------------------------------------------------- #
# Auto: the default, and the guarantee that it stays the default
# --------------------------------------------------------------------------- #


def test_scale_auto_stays_auto(tmp_path):
    src = _canonical(tmp_path)
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement is None
    assert ax.geometry_passthrough == []
    assert [w for w in rec.warnings if w.startswith("layout:")] == []
    assert _resave(rec.figure, tmp_path) == src


def test_a_graph_with_no_geometry_at_all_is_auto(tmp_path):
    src = _canonical(tmp_path).replace("    scale auto\n", "")
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement is None
    assert ax.geometry_passthrough == []
    # Re-save adopts the writer's default emission (that IS the auto mode);
    # nothing was dropped, because there was nothing there.
    assert "    scale auto" in _resave(rec.figure, tmp_path)


def test_scripted_figures_keep_the_default_emission(tmp_path):
    """No explicit geometry on the model -> byte-for-byte the historical output."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

    assert ax.placement is None
    assert ax.geometry_passthrough == []
    text = _resave(fig, tmp_path, "default.gle")
    assert "begin graph\n    scale auto\n" in text
    assert "amove" not in text


# --------------------------------------------------------------------------- #
# Grids: unchanged modelling, but no silent drops either
# --------------------------------------------------------------------------- #


def test_grid_geometry_is_still_modelled_by_the_grid_path(tmp_path):
    """gleplot's own multi-plot output: canonical cells, no capture, no warning."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    for idx in (1, 2):
        ax = fig.add_subplot(2, 1, idx)
        ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    src = _resave(fig, tmp_path, "grid.gle")

    rec = parse_gle_figure(tmp_path / "grid.gle")
    for ax in rec.figure.axes_list:
        assert ax.geometry_passthrough == []
        assert ax.placement is None
    assert [w for w in rec.warnings if w.startswith("layout:")] == []
    assert _resave(rec.figure, tmp_path, "grid2.gle") == src


def test_unmodelled_subplot_geometry_is_preserved_and_warned(tmp_path):
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    for idx in (1, 2):
        ax = fig.add_subplot(2, 1, idx)
        ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    src = _resave(fig, tmp_path, "grid.gle")
    # Replace the SECOND cell's canonical geometry with a fullsize.
    head, sep, tail = src.rpartition("begin graph\n")
    lines = tail.split("\n")
    assert lines[0].startswith("    size ") and lines[1] == "    scale 1 1"
    hand = head + sep + "\n".join(["    fullsize"] + lines[2:])
    rec = parse_gle_figure(_write(tmp_path, hand, "grid_hand.gle"))

    axes = rec.figure.axes_list
    assert axes[0].geometry_passthrough == []
    assert axes[1].geometry_passthrough == ["    fullsize"]
    assert any(w.startswith("layout:") for w in rec.warnings)
    assert _resave(rec.figure, tmp_path, "grid_hand2.gle") == hand


def test_placement_overrides_the_computed_grid_cell(tmp_path):
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    for idx in (1, 2):
        ax = fig.add_subplot(2, 1, idx)
        ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    fig.axes_list[0].placement = (0.5, 9.0, 18.0, 5.0)

    text = _resave(fig, tmp_path, "grid_placed.gle")
    assert "amove 0.5 9\nbegin graph\n    size 18 5\n    scale 1 1\n" in text


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #


def test_geometry_round_trips_through_to_dict(tmp_path):
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    first = fig.add_subplot(2, 1, 1)
    second = fig.add_subplot(2, 1, 2)
    first.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    second.plot(np.array([0.0, 1.0]), np.array([1.0, 0.0]))
    first.placement = (1.0, 2.0, 3.0, 4.0)
    second.geometry_passthrough = ["    fullsize"]

    restored = Figure.from_dict(fig.to_dict())
    assert restored.axes_list[0].placement == (1.0, 2.0, 3.0, 4.0)
    assert restored.axes_list[0].geometry_passthrough == []
    assert restored.axes_list[1].placement is None
    assert restored.axes_list[1].geometry_passthrough == ["    fullsize"]
    # to_dict is JSON-safe: the rect is a list of plain floats.
    payload = fig.to_dict()["figure"]["axes"][0]["placement"]
    assert payload == [1.0, 2.0, 3.0, 4.0]
    assert all(type(v) is float for v in payload)


def test_a_payload_without_geometry_keys_loads_as_auto():
    """Pre-geometry projects (no keys at all) mean auto placement."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    fig.add_subplot(111).plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    d = fig.to_dict()
    for ax_d in d["figure"]["axes"]:
        ax_d.pop("placement")
        ax_d.pop("geometry_passthrough")

    restored = Figure.from_dict(d)
    assert restored.axes_list[0].placement is None
    assert restored.axes_list[0].geometry_passthrough == []

"""Graph geometry: recognition, modelling and re-emission.

Graph-level ``size`` / ``scale`` / ``fullsize`` used to be parsed into two
recognizer fields (``info["size_cm"]`` / ``info["scale_mode"]``) that nothing
ever read: a hand-written ``fullsize`` figure silently re-saved as
``scale auto``. These tests pin the replacement contract down:

* the invertible triple ``amove x y`` + ``size w h`` + ``scale 1 1`` becomes
  :attr:`Axes.placement` (a page-cm frame rect, SPEC 3.3) and re-emits as the
  same three statements -- and since metadata v2 that triple is what gleplot
  writes for EVERY graph block, a lone plot included;
* every other real geometry (``fullsize``, ``scale h v``, a bare ``size``) is
  kept verbatim in :attr:`Axes.geometry_passthrough`, re-emitted in the
  geometry slot, and reported with a ``layout:`` warning;
* ``scale auto`` / absent geometry still means auto ("GLE decides") on the way
  IN -- that is how metadata-v1 files and hand-written ones are read -- and
  such a figure re-saves with the explicit rect the layout computes for it:
  the documented one-time geometry migration.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure, GLEGraphConfig, axes as _gleplot_axes
from gleplot.parser import metadata as _metadata
from gleplot.parser.recognizer import parse_gle_figure

#: The placed-graph geometry gleplot emits: an ``amove`` in front of the block
#: and ``size``/``scale 1 1`` as its first statements.
_PLACED_RE = re.compile(
    r"amove [\d.-]+ [\d.-]+\nbegin graph\n    size [\d.-]+ [\d.-]+\n    scale 1 1\n"
)


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


def _with_geometry(text: str, geometry: str) -> str:
    """``text`` with its placed-graph geometry swapped for ``geometry``.

    ``geometry`` replaces everything from the ``amove`` through the block's
    geometry statements, and must therefore re-open the graph block itself
    (see the call sites). Asserts the substitution actually happened, so a
    change in the writer's emission fails loudly here rather than silently
    turning these tests into no-ops.
    """
    out, n = _PLACED_RE.subn(lambda _m: geometry, text, count=1)
    assert n == 1, "canonical output no longer carries a placed graph block"
    return out


def _legacy_v1(tmp_path: Path) -> str:
    """The same figure as gleplot <= metadata v1 would have written it.

    v1 output carried no page geometry at all on the single-plot path: a bare
    ``scale auto``, no ``amove``, and a ``v1`` marker on the metadata block.
    """
    text = _canonical(tmp_path)
    text = text.replace(_metadata.BEGIN_MARKER, "! gleplot-meta-begin v1")
    return _with_geometry(text, "begin graph\n    scale auto\n")


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
    src = _with_geometry(
        _canonical(tmp_path),
        "amove 2 3\nbegin graph\n    size 12 8\n    scale 1 1\n",
    )
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement == (2.0, 3.0, 12.0, 8.0)
    assert ax.geometry_passthrough == []
    # Fully modelled -> nothing to warn about.
    assert [w for w in rec.warnings if w.startswith("layout:")] == []


def test_invertible_triple_round_trips_byte_identically(tmp_path):
    src = _with_geometry(
        _canonical(tmp_path),
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


def test_the_default_emission_is_an_explicit_placement(tmp_path):
    """No placement on the model -> the layout computes one; never ``scale auto``.

    This is the G2.2 / SPEC 10.2 default-emission change: a lone plot is the
    1x1 case of the grid geometry, so its frame rect is deterministic and
    invertible rather than left to GLE's page fit.
    """
    src = _canonical(tmp_path)
    assert "scale auto" not in src
    assert _PLACED_RE.search(src) is not None
    assert _metadata.BEGIN_MARKER in src


def test_the_default_rect_is_the_one_by_one_grid_cell(tmp_path):
    """The lone plot's rect comes from the same routine a grid's cells do."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    _resave(fig, tmp_path, "one.gle")

    from gleplot.writer import GLEWriter

    writer = GLEWriter(fig.figsize, fig.dpi, style=fig.style, graph=fig.graph)
    rects, _cells = fig._layout_rects(writer, None)
    assert len(rects) == 1

    text = (tmp_path / "one.gle").read_text(encoding="utf-8")
    x, y, w, h = rects[0]
    fmt = GLEWriter._format_number
    assert f"amove {fmt(x)} {fmt(y)}\n" in text
    assert f"    size {fmt(w)} {fmt(h)}\n" in text
    # ... and the rect sits strictly inside the page, with the decoration
    # margins that keep GLE's outside-the-frame labels on it.
    assert 0 < x and 0 < y
    assert x + w < writer.width_cm and y + h < writer.height_cm


def test_a_lone_plot_honours_subplots_adjust(tmp_path):
    """A consequence of the unification: margins are settable for 1x1 too."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    fig.subplots_adjust(left=0.25, right=0.9, bottom=0.2, top=0.8)

    text = _resave(fig, tmp_path, "adjusted.gle")
    width_cm, height_cm = 8 * 2.54, 6 * 2.54
    assert f"amove {0.25 * width_cm:g} {0.2 * height_cm:g}\n" in text
    expected_w = (0.9 - 0.25) * width_cm
    expected_h = (0.8 - 0.2) * height_cm
    assert f"    size {expected_w:g} {expected_h:g}\n" in text


def test_a_single_axes_in_a_grid_slot_gets_that_slot(tmp_path):
    """``add_subplot(2, 2, 1)`` alone now occupies the top-left quadrant.

    The grid comes from the axes' own ``position``, so a figure with one axes
    declared at a grid slot is placed in that slot -- matplotlib's behaviour,
    and a consequence of there being a single geometry routine. Before
    explicit placement this figure filled the whole page.
    """
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    ax = fig.add_subplot(2, 2, 1)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

    text = _resave(fig, tmp_path, "quadrant.gle")
    rects = _rects_of(text)
    assert len(rects) == 1
    x, y, w, h = rects[0]
    width_cm, height_cm = 8 * 2.54, 6 * 2.54
    # Top-left quadrant: less than half the page each way, upper half.
    assert w < width_cm / 2
    assert h < height_cm / 2
    assert y > height_cm / 2


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
    src = _with_geometry(_canonical(tmp_path), f"begin graph\n{geometry}\n")
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


def test_a_colorbar_reserves_its_width_in_the_placement_rect(tmp_path):
    """The colorbar reservation is now the layout's right-hand margin.

    A vertical colorbar is drawn outside the frame, at ``xg(xgmax)+sep``; the
    rect must therefore stop short of the page edge by at least the width the
    bar, its ticks and its rotated label need.
    """
    from tests.parser import _golden_battery as golden

    fig = golden.heatmap_imshow_colorbar()
    _resave(fig, tmp_path, "cbar.gle")
    reserved = fig._axes_colorbar_reserved_cm(fig.axes_list[0])
    assert reserved > 0

    rec = parse_gle_figure(tmp_path / "cbar.gle")
    ax = rec.figure.axes_list[0]
    assert ax.geometry_passthrough == []
    x, _y, w, _h = ax.placement
    page_w = 2.54 * fig.figsize[0]
    # (the emitted size is rounded to 6 significant figures)
    assert page_w - (x + w) >= reserved - 1e-3
    assert [w for w in rec.warnings if w.startswith("layout:")] == []


def test_a_legacy_colorbar_size_line_migrates_instead_of_freezing(tmp_path):
    """A v1 colorbar file's bare ``size`` is recognized, not kept verbatim.

    v1 pinned the graph BOX for colorbar figures (a bare ``size W H``, no
    ``scale``, no ``amove``). That line is a pure function of the recovered
    colorbar, so it loads as auto placement and re-saves as a v2 rect that
    reserves the same width -- rather than freezing a legacy line forever in
    ``geometry_passthrough``.
    """
    from tests.parser import _golden_battery as golden
    from gleplot.writer import GLEWriter

    fig = golden.heatmap_imshow_colorbar()
    src = _resave(fig, tmp_path, "cbar.gle")
    reserved = fig._axes_colorbar_reserved_cm(fig.axes_list[0])
    page_w, page_h = 2.54 * fig.figsize[0], 2.54 * fig.figsize[1]
    graph_w = max(page_w - reserved, page_w * 0.3)
    fmt = GLEWriter._format_number
    legacy_size = f"    size {fmt(graph_w)} {fmt(page_h)}"
    legacy = _with_geometry(src, f"begin graph\n{legacy_size}\n")

    rec = parse_gle_figure(_write(tmp_path, legacy, "cbar_v1.gle"))
    ax = rec.figure.axes_list[0]
    assert ax.geometry_passthrough == []
    assert ax.placement is None
    assert [w for w in rec.warnings if w.startswith("layout:")] == []
    # Re-save migrates it to the explicit rect (which still reserves the bar).
    again = _resave(rec.figure, tmp_path, "cbar_v2.gle")
    assert _PLACED_RE.search(again) is not None


def test_a_hand_written_size_on_a_colorbar_figure_is_kept(tmp_path):
    """... but a bare size that is NOT the derived one is preserved."""
    from tests.parser import _golden_battery as golden

    fig = golden.heatmap_imshow_colorbar()
    src = _resave(fig, tmp_path, "cbar.gle")
    hand = _with_geometry(src, "begin graph\n    size 11 5\n")
    rec = parse_gle_figure(_write(tmp_path, hand, "cbar_hand.gle"))

    assert rec.figure.axes_list[0].geometry_passthrough == ["    size 11 5"]
    assert any(w.startswith("layout:") for w in rec.warnings)
    assert _resave(rec.figure, tmp_path, "cbar_hand2.gle") == hand


def test_geometry_passthrough_keeps_the_original_spelling(tmp_path):
    """Hand-written indentation/casing is preserved verbatim, not canonicalized."""
    src = _with_geometry(_canonical(tmp_path), "begin graph\n  FULLSIZE\n")
    rec = parse_gle_figure(_write(tmp_path, src))

    assert rec.figure.axes_list[0].geometry_passthrough == ["  FULLSIZE"]
    assert _resave(rec.figure, tmp_path) == src


def test_an_amove_that_is_not_a_placement_is_preserved_and_warned(tmp_path):
    """``amove`` + non-invertible geometry: the position still positions."""
    src = _with_geometry(_canonical(tmp_path), "amove 2 3\nbegin graph\n    fullsize\n")
    rec = parse_gle_figure(_write(tmp_path, src))

    assert rec.figure.axes_list[0].placement is None
    assert "amove 2 3" in rec.figure.passthrough_header
    assert any("amove" in w for w in rec.warnings if w.startswith("layout:"))
    assert _resave(rec.figure, tmp_path) == src


# --------------------------------------------------------------------------- #
# Auto on the way in, explicit on the way out: the v1 -> v2 migration
# --------------------------------------------------------------------------- #


def test_a_legacy_v1_file_loads_as_auto_placement(tmp_path):
    src = _legacy_v1(tmp_path)
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement is None
    assert ax.geometry_passthrough == []
    # Auto placement is modelled, not lost: no layout warning.
    assert [w for w in rec.warnings if w.startswith("layout:")] == []


def test_a_legacy_v1_file_reports_the_migration_once(tmp_path):
    src = _legacy_v1(tmp_path)
    rec = parse_gle_figure(_write(tmp_path, src))
    migration = [w for w in rec.warnings if "v1" in w and "geometry" in w]
    assert len(migration) == 1


def test_a_legacy_v1_file_re_saves_with_explicit_geometry(tmp_path):
    """The documented one-time byte diff: v1 in, v2 + a placement rect out."""
    src = _legacy_v1(tmp_path)
    rec = parse_gle_figure(_write(tmp_path, src))

    again = _resave(rec.figure, tmp_path, "migrated.gle")
    assert again != src
    assert "scale auto" not in again
    assert _PLACED_RE.search(again) is not None
    assert _metadata.BEGIN_MARKER in again
    # ... and it is a fixed point from then on.
    rec2 = parse_gle_figure(tmp_path / "migrated.gle")
    assert _resave(rec2.figure, tmp_path, "migrated2.gle") == again


def test_a_graph_with_no_geometry_at_all_is_auto(tmp_path):
    src = _with_geometry(_canonical(tmp_path), "begin graph\n")
    rec = parse_gle_figure(_write(tmp_path, src))

    ax = rec.figure.axes_list[0]
    assert ax.placement is None
    assert ax.geometry_passthrough == []
    # Re-save adopts the writer's default emission (an explicit rect);
    # nothing was dropped, because there was nothing there.
    assert _PLACED_RE.search(_resave(rec.figure, tmp_path)) is not None


def test_fullsize_scale_mode_still_opts_out_of_placement(tmp_path):
    """``GLEGraphConfig.scale_mode='fullsize'`` remains a writer-level opt-out.

    It asks GLE to fit the graph (labels included) to the whole page, so there
    is no rect to emit and no ``amove`` in front of the block.
    """
    fig = Figure(
        figsize=(8, 6),
        graph=GLEGraphConfig(scale_mode="fullsize"),
        data_prefix="geom",
    )
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))

    text = _resave(fig, tmp_path, "fullsize_mode.gle")
    assert "begin graph\n    fullsize\n" in text
    assert "amove" not in text


# --------------------------------------------------------------------------- #
# Grids: per-axes rects, recovered rather than re-derived
# --------------------------------------------------------------------------- #


def test_grid_geometry_comes_back_as_per_axes_placement(tmp_path):
    """gleplot's own multi-plot output: every cell recovered as a rect."""
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    for idx in (1, 2):
        ax = fig.add_subplot(2, 1, idx)
        ax.plot(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    src = _resave(fig, tmp_path, "grid.gle")

    rec = parse_gle_figure(tmp_path / "grid.gle")
    for ax in rec.figure.axes_list:
        assert ax.geometry_passthrough == []
        assert ax.placement is not None
        assert len(ax.placement) == 4
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
# subplots_adjust: the SPEC's canonical lossy case, now lossless
# --------------------------------------------------------------------------- #


def _grid(tmp_path, rows=2, cols=2, **figure_kwargs):
    fig = glp.figure(figsize=(8, 6), data_prefix="geom", **figure_kwargs)
    for idx in range(1, rows * cols + 1):
        ax = fig.add_subplot(rows, cols, idx)
        ax.plot(np.array([0.0, 1.0, 2.0]), np.array([0.0, float(idx), 0.0]))
    return fig


def _rects_of(text: str):
    """Every ``amove``/``size`` frame rect in emission order."""
    return [
        tuple(float(v) for v in m.groups())
        for m in re.finditer(
            r"amove ([\d.-]+) ([\d.-]+)\nbegin graph\n"
            r"    size ([\d.-]+) ([\d.-]+)\n    scale 1 1\n",
            text,
        )
    ]


def test_default_spacing_grid_round_trips_byte_identically(tmp_path):
    fig = _grid(tmp_path)
    src = _resave(fig, tmp_path, "grid.gle")
    rec = parse_gle_figure(tmp_path / "grid.gle")
    assert _resave(rec.figure, tmp_path, "grid2.gle") == src


def test_custom_subplots_adjust_survives_save_parse_save(tmp_path):
    """The SPEC 10.2 canonical loss: a non-default spacing used to be reset.

    The fractions themselves are still not recoverable -- but they were only
    ever the layout helper's input. What renders is the rects, and those come
    back verbatim, so the file is a byte-identical fixed point.
    """
    fig = _grid(tmp_path)
    fig.subplots_adjust(
        left=0.2, right=0.95, bottom=0.15, top=0.9, wspace=0.6, hspace=0.5
    )
    src = _resave(fig, tmp_path, "adjusted.gle")
    rects1 = _rects_of(src)
    assert len(rects1) == 4

    rec = parse_gle_figure(tmp_path / "adjusted.gle")
    # Every cell came back as a rect on the model...
    assert [ax.placement for ax in rec.figure.axes_list] == rects1
    # ... even though the fractions themselves did not.
    assert rec.figure._subplot_adjust == {}
    # ... and the re-save reproduces the adjusted layout, not the default one.
    again = _resave(rec.figure, tmp_path, "adjusted2.gle")
    assert again == src
    assert _rects_of(again) == rects1


def test_a_custom_adjusted_grid_does_not_re_save_as_the_default_one(tmp_path):
    """Guards the assertion above against a vacuous pass."""
    src_default = _resave(_grid(tmp_path), tmp_path, "default.gle")
    fig = _grid(tmp_path)
    fig.subplots_adjust(left=0.2, right=0.95, bottom=0.15, top=0.9, wspace=0.6)
    src_adjusted = _resave(fig, tmp_path, "adjusted.gle")
    assert _rects_of(src_adjusted) != _rects_of(src_default)


def test_height_and_width_ratios_survive_save_parse_save(tmp_path):
    """Unequal rows/columns are geometry too, and ride the same rects."""
    fig = _grid(tmp_path, height_ratios=[3, 1], width_ratios=[1, 2])
    src = _resave(fig, tmp_path, "ratios.gle")
    rects = _rects_of(src)
    assert len(rects) == 4
    # The ratios really did produce unequal cells.
    assert rects[0][3] != rects[2][3]
    assert rects[0][2] != rects[1][2]

    rec = parse_gle_figure(tmp_path / "ratios.gle")
    assert [ax.placement for ax in rec.figure.axes_list] == rects
    # The recovered figure carries no ratios of its own -- it does not need
    # them, because the rects they produced are the model now.
    assert rec.figure.height_ratios is None
    assert rec.figure.width_ratios is None
    assert _resave(rec.figure, tmp_path, "ratios2.gle") == src


# --------------------------------------------------------------------------- #
# Interactions: shared axes, colorbars, broken axes
# --------------------------------------------------------------------------- #


def test_shared_axes_label_suppression_survives_the_round_trip(tmp_path):
    """Placement must not disturb the inner-tick/label suppression flags."""
    fig, axes = glp.subplots(
        2, 2, figsize=(8, 6), sharex=True, sharey=True, data_prefix="geom"
    )
    for idx, ax in enumerate(axes, start=1):
        ax.plot(np.array([0.0, 1.0, 2.0]), np.array([0.0, float(idx), 0.0]))
        ax.set_xlabel("t")
        ax.set_ylabel("v")
    src = _resave(fig, tmp_path, "shared.gle")
    before = [
        (ax._show_xlabel, ax._show_ylabel, ax._show_xticks, ax._show_yticks)
        for ax in fig.axes_list
    ]
    # Sharing really does suppress something.
    assert not all(all(flags) for flags in before)

    rec = parse_gle_figure(tmp_path / "shared.gle")
    after = [
        (ax._show_xlabel, ax._show_ylabel, ax._show_xticks, ax._show_yticks)
        for ax in rec.figure.axes_list
    ]
    assert after == before
    assert _resave(rec.figure, tmp_path, "shared2.gle") == src


def test_a_colorbar_figure_round_trips_byte_identically(tmp_path):
    from tests.parser import _golden_battery as golden

    src = _resave(golden.heatmap_imshow_colorbar(), tmp_path, "cbar.gle")
    rec = parse_gle_figure(tmp_path / "cbar.gle")
    assert _resave(rec.figure, tmp_path, "cbar2.gle") == src


def test_broken_axes_still_emit_their_own_placement(tmp_path):
    """Broken axes already emitted amove/size; that must keep working.

    Each segment occupies a slice of its grid cell, so the segments share a
    row but have different widths and x offsets -- and every one of them is
    emitted as a placed graph block.
    """
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    bax = fig.add_broken_xaxes(xlims=[(0.0, 1.0), (8.0, 9.0)])
    bax.plot(np.array([0.0, 0.5, 8.5, 9.0]), np.array([1.0, 2.0, 3.0, 4.0]))

    text = _resave(fig, tmp_path, "broken.gle")
    rects = _rects_of(text)
    assert len(rects) == 2
    xs = [r[0] for r in rects]
    assert xs[0] < xs[1]
    assert rects[0][1] == rects[1][1]  # same row
    assert sum(r[2] for r in rects) < 2.54 * 8  # slices, not full cells


def test_broken_axes_recovery_is_no_worse_than_before(tmp_path):
    """Known limitation: segments come back as independent subplots.

    They keep their recovered rects, so the re-save reproduces the same
    geometry; only the *grouping* (and its seam decoration, which lands in
    passthrough) is not reconstructed.
    """
    fig = glp.figure(figsize=(8, 6), data_prefix="geom")
    bax = fig.add_broken_xaxes(xlims=[(0.0, 1.0), (8.0, 9.0)])
    bax.plot(np.array([0.0, 0.5, 8.5, 9.0]), np.array([1.0, 2.0, 3.0, 4.0]))
    src = _resave(fig, tmp_path, "broken.gle")

    rec = parse_gle_figure(tmp_path / "broken.gle")
    assert rec.figure.broken_axes == []  # the documented limitation
    assert len(rec.figure.axes_list) == 2
    assert [ax.placement for ax in rec.figure.axes_list] == _rects_of(src)


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

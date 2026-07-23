"""Recognizer tests for contour/heatmap: gleplot-authored recovery + hand-written
preservation.

The byte-identical fixed point over gleplot-authored contour/heatmap figures is
covered by ``test_fixed_point.py`` (golden battery); ``to_dict`` equivalence by
``test_recognizer.py``. Here we assert semantic recovery of the model fields and
that hand-written / foreign contour-heatmap content is NEVER lost (preserved
verbatim through passthrough, with a warning).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.parser.syntax import emit, parse_gle_source


def _save(fig, tmp_path: Path) -> Path:
    p = tmp_path / "f.gle"
    fig.savefig_gle(str(p))
    return p


# --------------------------------------------------------------------------- #
# Semantic recovery of gleplot-authored figures
# --------------------------------------------------------------------------- #


def test_imshow_colorbar_recovered(tmp_path):
    fig = glp.figure(figsize=(7, 6), data_prefix="g")
    ax = fig.add_subplot(111)
    ax.imshow(
        np.arange(12.0).reshape(3, 4),
        extent=(0, 4, 0, 3),
        cmap="inferno",
        vmin=0,
        vmax=11,
        interpolation="nearest",
        invert=True,
    )
    fig.colorbar(label="phi", format="fix 2", width=0.4, sep=0.6)
    path = _save(fig, tmp_path)

    rec = parse_gle_figure(path)
    assert rec.warnings == []
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["source"] == "grid"
    assert hm["cmap"] == "inferno"
    assert hm["vmin"] == 0.0 and hm["vmax"] == 11.0
    assert hm["invert"] is True
    assert hm["interpolation"] == "nearest"
    assert hm["extent"] == [0.0, 4.0, 0.0, 3.0]
    assert hm["z"].shape == (3, 4)
    cb = hm["colorbar"]
    assert cb["label"] == "phi" and cb["format"] == "fix 2"
    assert cb["width"] == 0.4 and cb["sep"] == 0.6


def test_tricontour_recovered_with_clabel(tmp_path):
    fig = glp.figure(figsize=(8, 6), data_prefix="g")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 12)
    y = np.linspace(0, 4, 12)
    z = np.sin(x) + y
    ax.tricontour(
        x,
        y,
        z,
        gridsize=(9, 9),
        extent=(0, 4, 0, 4),
        ncontour=5,
        levels=[1.0, 2.0, 3.0],
        colors="blue",
        clabel=True,
        clabel_fmt="fix 0",
    )
    path = _save(fig, tmp_path)

    rec = parse_gle_figure(path)
    assert rec.warnings == []
    ct = rec.figure.axes_list[0].contours[0]
    assert ct["source"] == "points"
    assert ct["gridsize"] == [9, 9]
    assert ct["ncontour"] == 5
    assert ct["levels"] == [1.0, 2.0, 3.0]
    assert ct["color"] == "BLUE"
    assert ct["clabel"] is True
    assert ct["clabel_fmt"] == "fix 0"


def test_generated_files_absent_are_tolerated(tmp_path):
    """The GLE-generated ``-cdata.dat``/``.z`` (fitz) files never exist at save
    time; recovery must not treat their references as broken series."""
    fig = glp.figure(figsize=(7, 6), data_prefix="g")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 6)
    y = np.linspace(0, 3, 5)
    ax.contour(x, y, np.outer(y, x), levels=[2.0, 4.0], colors="black")
    path = _save(fig, tmp_path)
    # No cdata file exists next to the .gle.
    assert not list(tmp_path.glob("*-cdata.dat"))

    rec = parse_gle_figure(path)
    ax2 = rec.figure.axes_list[0]
    assert len(ax2.contours) == 1
    assert not ax2.file_series  # not a broken file series
    assert not any("cdata" in p for p in ax2.passthrough)
    # No "data:" broken-reference warning for the generated cdata file.
    assert not any(w.startswith("data:") for w in rec.warnings)


# --------------------------------------------------------------------------- #
# Hand-written / foreign preservation (never lose content)
# --------------------------------------------------------------------------- #


def test_foreign_palette_colormap_preserved(tmp_path):
    """A colormap naming a NON-gleplot palette sub is kept verbatim + warned."""
    (tmp_path / "grid.z").write_text(
        "! nx 2 ny 2 xmin 0 xmax 1 ymin 0 ymax 1\n0 1\n1 2\n", encoding="utf-8"
    )
    src = (
        "size 10 10\n"
        "begin graph\n"
        '   colormap "grid.z" 100 100 palette my_custom_pal\n'
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert not ax.heatmaps  # unknown palette -> not modeled
    assert any("my_custom_pal" in line for line in ax.passthrough)
    assert any("unknown palette" in w for w in rec.warnings)
    # Round-trip preserves the line verbatim.
    text2, _ = rec.figure._generate_gle_with_files()
    assert 'colormap "grid.z" 100 100 palette my_custom_pal' in text2


def test_function_colormap_preserved(tmp_path):
    """A colormap of a function expression (not a .z file) is kept verbatim."""
    src = (
        "size 10 10\n"
        "begin graph\n"
        '   colormap "sin(x)*cos(y)" 100 100 color\n'
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert not ax.heatmaps
    assert any("sin(x)*cos(y)" in line for line in ax.passthrough)
    assert any("function expression" in w for w in rec.warnings)


def test_unreferenced_foreign_fitz_block_preserved(tmp_path):
    """A ``begin fitz`` whose output is never used stays opaque passthrough."""
    (tmp_path / "pts.dat").write_text("0 0 0\n1 1 1\n2 2 2\n", encoding="utf-8")
    src = (
        "size 10 10\n"
        "begin fitz\n"
        '   data "pts.dat"\n'
        "   x from 0 to 2 step 1\n"
        "   y from 0 to 2 step 1\n"
        "end fitz\n"
        "begin graph\n"
        "   data pts.dat d1=c1,c2\n"
        "   d1 marker circle\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    # The fitz block's output .z is never referenced by a colormap/contour, so
    # it is NOT consumed -> preserved verbatim in the trailer/header passthrough.
    text2, _ = rec.figure._generate_gle_with_files()
    assert "begin fitz" in text2
    assert 'data "pts.dat"' in text2


def test_fitz_feeding_foreign_colormap_preserved(tmp_path):
    """A ``begin fitz`` whose .z feeds a FOREIGN-palette colormap is preserved.

    Regression: the prescan used to drop the fitz block whenever its generated
    ``.z`` was merely *referenced* by a colormap -- even when that colormap
    named an unknown palette and was itself re-emitted verbatim as passthrough.
    Dropping the fitz block then left the preserved colormap line pointing at a
    grid nothing produces (content loss + broken output). The block must stay
    opaque when its consumer isn't reconstructed.
    """
    (tmp_path / "scatter.dat").write_text("0 0 0\n1 1 1\n2 2 2\n", encoding="utf-8")
    src = (
        "size 12 9\n"
        "sub mypal z\n"
        "   return rgb(z,0,1-z)\n"
        "end sub\n"
        "begin fitz\n"
        '   data "scatter.dat"\n'
        "   x from 0 to 10 step 0.5\n"
        "   y from 0 to 8 step 0.4\n"
        "   ncontour 5\n"
        "end fitz\n"
        "begin graph\n"
        '   colormap "scatter.z" 300 300 palette mypal\n'
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    assert not rec.figure.axes_list[0].heatmaps  # foreign palette -> not modeled
    text2, _ = rec.figure._generate_gle_with_files()
    assert "begin fitz" in text2
    assert 'data "scatter.dat"' in text2
    assert 'colormap "scatter.z" 300 300 palette mypal' in text2


def test_contour_cdata_with_unreadable_grid_preserved(tmp_path):
    """A gleplot-shaped contour whose grid ``.z`` is missing loses nothing.

    Regression: the prescan consumed the ``begin contour`` block and the graph
    ``data "<base>-cdata.dat"`` line by filename match, but reconstruction then
    bailed because the ``.z`` grid could not be read -- dropping the block and
    the data command and orphaning the ``dN line``. With no readable grid the
    block must stay opaque and the data command + display line preserved.
    """
    # NB: no ``mydata.z`` on disk -> grid unreadable.
    src = (
        "size 12 9\n"
        "begin contour\n"
        '   data "mydata.z"\n'
        "   values 0.2 0.4 0.6\n"
        "end contour\n"
        "begin graph\n"
        '   data "mydata-cdata.dat" d1=c1,c2\n'
        "   d1 line color red lwidth 0.05\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    assert not rec.figure.axes_list[0].contours  # unreadable grid -> not modeled
    text2, _ = rec.figure._generate_gle_with_files()
    assert "begin contour" in text2
    assert 'data "mydata.z"' in text2
    assert "mydata-cdata.dat" in text2
    assert "d1 line color red" in text2


def test_handwritten_gleplot_authored_style_recovers(tmp_path):
    """A hand-authored file using the gleplot idiom (quoted files, gleplot_
    palette) recovers as a heatmap even without a metadata block."""
    (tmp_path / "grid.z").write_text(
        "! nx 2 ny 2 xmin 0 xmax 1 ymin 0 ymax 1\n0 1\n1 2\n", encoding="utf-8"
    )
    from gleplot import palettes

    src = (
        "size 10 10\n" + palettes.palette_sub_text("viridis") + "\n" + "begin graph\n"
        '   colormap "grid.z" 100 100 palette gleplot_viridis\n'
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.heatmaps) == 1
    assert ax.heatmaps[0]["cmap"] == "viridis"
    # gleplot_ sub not flagged as a programmatic file.
    assert not any(w.startswith("programmatic:") for w in rec.warnings)


def test_structural_roundtrip_of_contour_file_unchanged(tmp_path):
    """The low-level structural parser round-trips a contour/heatmap file
    byte-for-byte (no semantic layer)."""
    fig = glp.figure(figsize=(7, 6), data_prefix="g")
    ax = fig.add_subplot(111)
    ax.imshow(np.arange(6.0).reshape(2, 3), extent=(0, 3, 0, 2), cmap="viridis")
    ax.contour(
        np.linspace(0, 3, 3),
        np.linspace(0, 2, 2),
        np.arange(6.0).reshape(2, 3),
        levels=[1.0, 3.0],
        clabel=True,
    )
    fig.colorbar(label="v")
    text = fig._generate_gle_with_files()[0]
    assert emit(parse_gle_source(text)) == text

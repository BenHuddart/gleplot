"""Recognizer tests for contour/heatmap: gleplot-authored recovery + hand-written
preservation.

The byte-identical fixed point over gleplot-authored contour/heatmap figures is
covered by ``test_fixed_point.py`` (golden battery); ``to_dict`` equivalence by
``test_recognizer.py``. Here we assert semantic recovery of the model fields and
that hand-written / foreign contour-heatmap content is NEVER lost (preserved
verbatim through passthrough, with a warning).
"""

from __future__ import annotations

import re
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


def test_a_colorbar_with_a_moved_label_stays_raw(tmp_path):
    """A label placed other than where the writer puts it keeps its group raw."""
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).imshow(np.arange(4.0).reshape(2, 2))
    fig.colorbar(label="phi")
    path = _save(fig, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "(yg(ygmin)+yg(ygmax))/2\n" in text
    path.write_text(text.replace("(yg(ygmin)+yg(ygmax))/2\n", "yg(ygmax)\n"))

    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].heatmaps[0]["colorbar"] is None
    out = rec.figure._generate_gle_with_files()[0]
    assert 'write "phi"' in out and out.count("color_range_vertical") == 1


def test_per_axes_and_horizontal_colorbars_recovered(tmp_path):
    fig, (a, b) = glp.subplots(1, 2, figsize=(10, 4), data_prefix="g")
    ha = a.imshow(np.arange(4.0).reshape(2, 2), cmap="viridis")
    hb = b.imshow(np.arange(4.0).reshape(2, 2) * 10, cmap="magma")
    fig.colorbar(ha, ax=a, label="a", width=0.4)
    fig.colorbar(hb, ax=b, orientation="horizontal", label="b", width=0.3, sep=1.2)

    rec = parse_gle_figure(_save(fig, tmp_path))
    assert rec.warnings == []
    ra, rb = (ax.heatmaps[0]["colorbar"] for ax in rec.figure.axes_list)
    assert "orientation" not in ra
    assert (ra["label"], ra["width"], ra["sep"]) == ("a", 0.4, 0.3)
    assert rb["orientation"] == "horizontal"
    assert (rb["label"], rb["width"], rb["sep"]) == ("b", 0.3, 1.2)
    assert (rb["zmin"], rb["zmax"]) == (0.0, 30.0)


@pytest.mark.parametrize(
    "orientation, amove",
    [
        ("horizontal", "amove xg(xgmin) yg(ygmin)+0.5\n"),
        ("vertical", "amove xg(xgmax)+-0.5 yg(ygmin)\n"),
    ],
)
def test_a_bar_inside_the_frame_keeps_its_negative_sep(tmp_path, orientation, amove):
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).imshow(np.arange(4.0).reshape(2, 2))
    fig.colorbar(orientation=orientation, sep=-0.5)
    path = _save(fig, tmp_path)
    assert amove in path.read_text()

    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].heatmaps[0]["colorbar"]["sep"] == -0.5


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


def test_contour_labels_on_another_file_stay_raw(tmp_path):
    """Only the labels of a contour read back are taken; others stay as written."""
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).contour(
        np.arange(9.0).reshape(3, 3), levels=[4.0], clabel=True
    )
    path = _save(fig, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "-clabels.dat" in text
    path.write_text(text.replace('-clabels.dat"', '-other.dat"'), encoding="utf-8")

    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].contours[0]["clabel"]
    out = rec.figure._generate_gle_with_files()[0]
    assert '-other.dat" format "fix 1"' in out
    assert out.count('include "contour.gle"') == 1


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


def test_pcolormesh_recovered(tmp_path):
    """The cell grid loads back as the mesh: C and its edges, not the padding."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    C = np.arange(6.0).reshape(2, 3)
    ax.pcolormesh(np.linspace(1, 4, 4), np.linspace(-1, 1, 3), C, cmap="magma")
    rec = parse_gle_figure(_save(fig, tmp_path))
    assert rec.warnings == []
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["cells"] is True
    assert hm["extent"] == [1.0, 4.0, -1.0, 1.0]
    np.testing.assert_array_equal(hm["z"], C)


def test_pcolormesh_recovers_the_edges_it_wrote(tmp_path):
    """Edges come from the marker line, not from undoing the rounded header."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.pcolormesh(np.linspace(0, 1, 4), np.linspace(0, 1, 8), np.zeros((7, 3)))
    rec = parse_gle_figure(_save(fig, tmp_path))
    assert rec.figure.axes_list[0].heatmaps[0]["extent"] == [0.0, 1.0, 0.0, 1.0]


@pytest.mark.parametrize(
    "header, rows, clause",
    [
        # first column not repeated
        ("xmin -0.5 xmax 2.5", ["0 1 2", "0 1 2"], " interpolate nearest"),
        # bicubic, not nearest
        ("xmin -0.5 xmax 2.5", ["0 0 1", "0 0 1"], ""),
        # header not half a cell outside the marker's edges
        ("xmin 0 xmax 3", ["0 0 1", "0 0 1"], " interpolate nearest"),
    ],
)
def test_cells_marker_on_another_grid_reads_as_imshow(tmp_path, header, rows, clause):
    """A marked grid that is not a mesh is drawn as written, and says so."""
    (tmp_path / "grid.z").write_text(
        f"! nx 3 ny 2 {header} ymin -0.5 ymax 1.5\n"
        "! gleplot: cells xmin 0 xmax 2 ymin 0 ymax 1\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    p = tmp_path / "f.gle"
    p.write_text(
        "size 10 10\nbegin graph\n"
        f'   colormap "grid.z" 100 100{clause}\nend graph\n',
        encoding="utf-8",
    )
    rec = parse_gle_figure(p)
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert "cells" not in hm
    # Its last row where colormap draws it: one spacing short of ymax.
    assert hm["extent"][2:] == [-0.5, 0.5]
    assert any("marked as a pcolormesh mesh" in w for w in rec.warnings)


def test_contourf_recovered(tmp_path):
    """Levels and colouring come from the band sub, edges from the marker."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 1, 31)
    Z = np.add.outer(x, x)
    ax.contourf(x, x, Z, [0.2, 0.7, 1.3], cmap="magma_r", vmax=2, extend="both")
    rec = parse_gle_figure(_save(fig, tmp_path))
    assert rec.warnings == []
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["levels"] == [0.2, 0.7, 1.3]
    assert (hm["extend"], hm["cmap"], hm["vmin"], hm["vmax"]) == (
        "both",
        "magma_r",
        None,
        2.0,
    )
    assert hm["extent"] == [0.0, 1.0, 0.0, 1.0]
    np.testing.assert_allclose(hm["z"], Z, rtol=1e-5)


def test_contourf_colormap_off_its_bar_range_is_kept_raw(tmp_path):
    """A band sub mapping from one range under a colormap on another."""
    rec = _contourf_file(
        tmp_path,
        "! gleplot: contourf cmap viridis extend neither levels 0 1 2\n"
        "   z = 0*(1-z)+2*z",
        "! gleplot: nodes xmin 0 xmax 1 ymin 0 ymax 1\n",
    )
    assert not rec.figure.axes_list[0].heatmaps
    assert any("unknown palette 'glp_contourf1'" in w for w in rec.warnings)


def _contourf_file(tmp_path, comment, marker, options=""):
    (tmp_path / "grid.z").write_text(
        "! nx 2 ny 2 xmin 0 xmax 2 ymin 0 ymax 2\n" + marker + "0 1\n1 2\n",
        encoding="utf-8",
    )
    p = tmp_path / "f.gle"
    p.write_text(
        "size 10 10\n"
        "sub glp_contourf1 z\n"
        f"   {comment}\n"
        "   return rgb(z, z, z)\n"
        "end sub\n"
        "begin graph\n"
        '   colormap "grid.z" 100 100 zmin 0 zmax 1 palette glp_contourf1'
        f"{options}\n"
        "end graph\n",
        encoding="utf-8",
    )
    return parse_gle_figure(p)


def test_contourf_without_its_marker_takes_its_edges_from_the_header(tmp_path):
    rec = _contourf_file(
        tmp_path, "! gleplot: contourf cmap viridis extend neither levels 0 1 2", ""
    )
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["extent"] == [0.0, 1.0, 0.0, 1.0]
    assert any("no marker line giving its edges" in w for w in rec.warnings)


@pytest.mark.parametrize(
    "comment, options",
    [
        ("! gleplot: contourf cmap viridis extend sideways levels 0 1 2", ""),
        ("! gleplot: contourf cmap viridis extend neither levels 0 1 2", " invert"),
    ],
)
def test_contourf_gleplot_cannot_read_keeps_its_band_sub(tmp_path, comment, options):
    """A contourf colormap kept as raw GLE keeps the sub it calls."""
    rec = _contourf_file(
        tmp_path,
        comment,
        "! gleplot: nodes xmin 0 xmax 1 ymin 0 ymax 1\n",
        options,
    )
    ax = rec.figure.axes_list[0]
    assert not ax.heatmaps
    assert any("palette glp_contourf1" in line for line in ax.passthrough)
    assert any("unknown palette 'glp_contourf1'" in w for w in rec.warnings)
    text, _ = rec.figure._generate_gle_with_files()
    assert "sub glp_contourf1 z" in text.splitlines()
    assert "   return rgb(z, z, z)" in text.splitlines()


@pytest.mark.parametrize(
    "header, extent, noted",
    [
        # One node spacing past the marker's edges: an imshow grid (#350).
        ("xmin 0 xmax 2 ymin 0 ymax 2", [0.0, 1.0, 0.0, 1.0], False),
        # Not: read where colormap draws its nodes, and said so.
        ("xmin 0 xmax 3 ymin 0 ymax 3", [0.0, 1.5, 0.0, 1.5], True),
    ],
)
def test_a_node_grid_under_a_plain_colormap_reads_its_own_edges(
    tmp_path, header, extent, noted
):
    (tmp_path / "grid.z").write_text(
        f"! nx 2 ny 2 {header}\n"
        "! gleplot: nodes xmin 0 xmax 1 ymin 0 ymax 1\n0 1\n1 2\n",
        encoding="utf-8",
    )
    p = tmp_path / "f.gle"
    p.write_text(
        'size 10 10\nbegin graph\n   colormap "grid.z" 100 100\nend graph\n',
        encoding="utf-8",
    )
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].heatmaps[0]["extent"] == extent
    assert any("node-grid marker" in w for w in rec.warnings) == noted


def test_a_grid_written_before_node_headers_still_loads(tmp_path):
    """A ``.z`` with no marker line keeps its nodes where colormap drew them.

    ``colormap`` puts the last of ``n`` nodes one ``(xmax - xmin) / n`` short
    of ``xmax``, so re-saving, one node spacing past that, draws it again.
    """
    (tmp_path / "grid.z").write_text(
        "! nx 2 ny 2 xmin 0 xmax 1 ymin 0 ymax 1\n0 1\n1 2\n", encoding="utf-8"
    )
    p = tmp_path / "f.gle"
    p.write_text(
        'size 10 10\nbegin graph\n   colormap "grid.z" 100 100\nend graph\n',
        encoding="utf-8",
    )
    rec = parse_gle_figure(p)
    heatmap = rec.figure.axes_list[0].heatmaps[0]
    assert heatmap["extent"] == [0.0, 0.5, 0.0, 0.5]
    assert heatmap["z"].tolist() == [[0.0, 1.0], [1.0, 2.0]]
    assert rec.warnings == []
    (tmp_path / "again").mkdir()
    rec.figure.savefig_gle(str(tmp_path / "again" / "f.gle"))
    header = (tmp_path / "again" / "grid.z").read_text().splitlines()[0]
    assert header == "! nx 2 ny 2 xmin 0 xmax 1 ymin 0 ymax 1"


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


def test_hand_written_function_colormap_recovered(tmp_path):
    """A bare expression after both axis ranges loads as a function heatmap."""
    src = (
        "size 10 10\n"
        "begin graph\n"
        "   xaxis min -2 max 2\n"
        "   yaxis min 0 max 1\n"
        "   colormap exp(-x^2)*y 100 80 color zmax 2\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    assert rec.warnings == []
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["source"] == "function"
    assert hm["expression"] == "exp(-x^2)*y"
    assert hm["extent"] == [-2.0, 2.0, 0.0, 1.0]
    assert hm["cmap"] == "rainbow"
    assert hm["pixels"] == [100, 80]
    assert hm["vmin"] is None and hm["vmax"] == 2.0
    text2, files2 = rec.figure._generate_gle_with_files()
    assert "    colormap exp(-x^2)*y 100 80 color zmax 2" in text2.splitlines()
    assert files2 == {}


def test_function_colormap_without_axis_ranges_preserved(tmp_path):
    """With no axis range to take the extent from, the line stays raw."""
    src = (
        "size 10 10\n"
        "begin graph\n"
        "   colormap sin(x)*cos(y) 100 100 color\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert not ax.heatmaps
    assert any("sin(x)*cos(y)" in line for line in ax.passthrough)
    assert any("no ascending xaxis and yaxis" in w for w in rec.warnings)


@pytest.mark.parametrize(
    "line, why",
    [
        ("colormap x*y*a 100 100 color zmin lo zmax hi", "zmin, zmax"),
        ("colormap atan2(y,x) 100 100 color zmin -pi zmax pi", "zmin, zmax"),
        ("colormap x*y 100 100 interpolate bilinear", "interpolate"),
        ("colormap d1*x 100 100", "expression gleplot cannot write back"),
    ],
)
def test_function_colormap_with_inexact_clauses_preserved(tmp_path, line, why):
    """A clause that would not be written back as it reads keeps the line raw."""
    src = (
        "size 10 10\n"
        "begin graph\n"
        "   xaxis min -1 max 1\n"
        "   yaxis min -1 max 1\n"
        f"   {line}\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert not ax.heatmaps
    assert any(line in kept for kept in ax.passthrough)
    assert any(why in w for w in rec.warnings)


def test_quoted_colormap_operand_preserved(tmp_path):
    """A quoted operand that is not a .z file is kept verbatim."""
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
    assert any("not a .z file" in w for w in rec.warnings)


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


def _fitz_colormap_file(tmp_path, block):
    (tmp_path / "pts.dat").write_text("0 0 0\n1 1 1\n2 0 2\n", encoding="utf-8")
    p = tmp_path / "f.gle"
    p.write_text(
        "size 12 9\n"
        "begin fitz\n"
        '   data "pts.dat"\n'
        f"{block}"
        "end fitz\n"
        "begin graph\n"
        '   colormap "pts.z" 200 200 color\n'
        "end graph\n",
        encoding="utf-8",
    )
    return parse_gle_figure(p)


def test_tripcolor_grid_is_read_from_its_marker(tmp_path):
    """#376: the marker gives the extent, GLE's node count the gridsize."""
    rec = _fitz_colormap_file(
        tmp_path,
        "   ! gleplot: nodes xmin 0 xmax 2 ymin 0 ymax 1\n"
        "   x from 0 to 2.4995 step 0.5\n"
        "   y from 0 to 1.4995 step 0.5\n",
    )
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["extent"] == [0.0, 2.0, 0.0, 1.0]
    assert hm["gridsize"] == [5, 3]
    assert not rec.warnings


def test_tripcolor_grid_without_its_marker_is_read_where_gle_draws_it(tmp_path):
    """A hand-written or older block: the colormap's last node is one header
    spacing short of ``to``, and re-saving draws it there."""
    rec = _fitz_colormap_file(
        tmp_path, "   x from 0 to 2 step 0.5\n   y from 0 to 1 step 0.5\n"
    )
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["extent"] == pytest.approx([0.0, 1.6, 0.0, 2 / 3])
    assert hm["gridsize"] == [5, 3]
    text = rec.figure._generate_gle_with_files()[0]
    assert "   x from 0 to 1.9996 step 0.4" in text


@pytest.mark.parametrize(
    "marker", ["xmin 0 xmax 3 ymin 0 ymax 1", "xmin 0 xmax 2 ymin 0 ymax"]
)
def test_tripcolor_marker_off_its_ranges_is_noted(tmp_path, marker):
    rec = _fitz_colormap_file(
        tmp_path,
        f"   ! gleplot: nodes {marker}\n"
        "   x from 0 to 2.4995 step 0.5\n"
        "   y from 0 to 1.4995 step 0.5\n",
    )
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["extent"][1] == pytest.approx(2.4995 * 4 / 5)
    assert any("does not match its ranges" in w for w in rec.warnings)


@pytest.mark.filterwarnings("ignore:The x limits reach")
@pytest.mark.parametrize("x_range", ["0 to 2 step 0", "2 to 0 step -0.5"])
def test_tripcolor_grid_with_a_range_gleplot_does_not_write_loads(tmp_path, x_range):
    """GLE refuses these ranges; the file loads over them as written, and saves."""
    rec = _fitz_colormap_file(
        tmp_path, f"   x from {x_range}\n   y from 0 to 1 step 0.5\n"
    )
    hm = rec.figure.axes_list[0].heatmaps[0]
    assert hm["extent"][:2] == [float(v) for v in x_range.split()[::2][:2]]
    text = rec.figure._generate_gle_with_files()[0]
    assert f"   x from {x_range.split()[0]} to " in text


@pytest.mark.parametrize(
    "clauses",
    ["zmin lo zmax 1", "zmin -pi zmax pi", "interpolate bilinear"],
)
def test_file_colormap_with_inexact_clauses_preserved(tmp_path, clauses):
    """#206: a ``.z`` colormap clause not written back as it reads stays raw.

    So does the ``begin fitz`` block producing the grid it reads.
    """
    (tmp_path / "scatter.dat").write_text("0 0 0\n1 1 1\n2 2 2\n", encoding="utf-8")
    line = f'colormap "scatter.z" 300 300 color {clauses}'
    src = (
        "size 12 9\n"
        "lo = 0\n"
        "begin fitz\n"
        '   data "scatter.dat"\n'
        "   x from 0 to 10 step 0.5\n"
        "   y from 0 to 8 step 0.4\n"
        "end fitz\n"
        "begin graph\n"
        f"   {line}\n"
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    assert not rec.figure.axes_list[0].heatmaps
    assert any("cannot write back as it reads" in w for w in rec.warnings)
    text2, _ = rec.figure._generate_gle_with_files()
    assert "begin fitz" in text2
    assert line in text2


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


@pytest.mark.parametrize("extra", ["   smooth 5", "   ! my note"])
def test_a_line_gleplot_does_not_write_in_a_contour_block_is_reported(tmp_path, extra):
    """#176: the contour is recovered and the dropped line is named."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(9.0).reshape(3, 3), levels=[4.0], clabel=True)
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("end contour", f"{extra}\nend contour")
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    (contour,) = rec.figure.axes_list[0].contours
    assert contour["levels"] == [4.0] and contour["clabel"]
    line_no = text.splitlines().index(extra) + 1
    (note,) = rec.notes
    assert extra.strip() in note.message and "not written back" in note.message
    assert note.source_span == (line_no, line_no)


@pytest.mark.parametrize("extra", ["   smoothness 5", "   ! my note"])
def test_a_line_gleplot_does_not_write_in_a_fitz_block_is_reported(tmp_path, extra):
    """#380: the scattered contour is recovered and the dropped line is named."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.tricontour([0.0, 1.0, 0.0, 1.0, 0.5], [0.0, 0.0, 1.0, 1.0, 0.5], [0, 1, 1, 2, 1])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("end fitz", f"{extra}\nend fitz")
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    assert len(rec.figure.axes_list[0].contours) == 1
    line_no = text.splitlines().index(extra) + 1
    (note,) = rec.notes
    assert extra.strip() in note.message and "begin fitz" in note.message
    assert note.source_span == (line_no, line_no)


@pytest.mark.parametrize("extra", ["   ncontour 5", "   ! my note"])
def test_a_line_a_tripcolor_fitz_block_does_not_write_is_reported(tmp_path, extra):
    """#380: a colormap's fitz block writes no ``ncontour`` either."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.tripcolor([0.0, 1.0, 0.0, 1.0, 0.5], [0.0, 0.0, 1.0, 1.0, 0.5], [0, 1, 1, 2, 1])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("end fitz", f"{extra}\nend fitz")
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    assert len(rec.figure.axes_list[0].heatmaps) == 1
    line_no = text.splitlines().index(extra) + 1
    (note,) = rec.notes
    assert extra.strip() in note.message and "begin fitz" in note.message
    assert note.source_span == (line_no, line_no)


@pytest.mark.parametrize(
    "extra", ["   ncontour nlev", "   ncontour 5.5", "   x from 0 to 2 step 0.5"]
)
def test_a_fitz_block_line_open_gle_cannot_read_keeps_the_block(tmp_path, extra):
    """#380: an unreadable or repeated line keeps the block as written."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.tricontour([0.0, 1.0, 0.0, 1.0, 0.5], [0.0, 0.0, 1.0, 1.0, 0.5], [0, 1, 1, 2, 1])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("end fitz", f"{extra}\nend fitz")
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    out, _ = rec.figure._generate_gle_with_files()
    assert extra in out


@pytest.mark.parametrize(
    "extra, named",
    [
        ("marker circle msize 0.2", "'marker', 'msize'"),
        ('key "levels"', "'key'"),
        ("smooth", "'smooth'"),
        ("y2axis", "'y2axis'"),
        ("nomiss deresolve 2 average", "'nomiss', 'deresolve', 'average'"),
        ("marker circle mscale 2", "'marker', 'mscale 2'"),
    ],
)
def test_what_a_contour_dataset_line_drops_is_reported(tmp_path, extra, named):
    """#296: what ``ContourSeries`` cannot hold is named, not dropped silently."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(9.0).reshape(3, 3), levels=[4.0])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8")
    line = next(s for s in text.splitlines() if s.strip().startswith("d1 line"))
    path.write_text(text.replace(line, f"{line} {extra}"), encoding="utf-8")

    rec = parse_gle_figure(path)
    (contour,) = rec.figure.axes_list[0].contours
    assert contour["levels"] == [4.0]
    (note,) = rec.notes
    assert note.message.startswith(f"{named} on a contour's dataset line: ")
    assert note.source_span is not None


def test_a_contour_dataset_line_without_line_is_reported(tmp_path):
    """#296: the writer draws the ``line`` the file left out."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(9.0).reshape(3, 3), levels=[4.0])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8")
    line = next(s for s in text.splitlines() if s.strip().startswith("d1 line"))
    path.write_text(text.replace(line, line.replace(" line", "")), encoding="utf-8")

    rec = parse_gle_figure(path)
    (note,) = rec.notes
    assert note.message.startswith("'no line' on a contour's dataset line: ")


@pytest.mark.parametrize(
    "levels", ["   values 4 lev", "   values 4\n   values 5", "   values"]
)
def test_contour_levels_gleplot_cannot_read_keep_the_block(tmp_path, levels):
    """A level that is not a number, or a second list, is not half read."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(9.0).reshape(3, 3), levels=[4.0])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("   values 4", levels)
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].contours
    text2, _ = rec.figure._generate_gle_with_files()
    assert text[text.index("begin contour") : text.index("end contour")] in text2


def test_handwritten_gleplot_authored_style_recovers(tmp_path):
    """A hand-authored file using the gleplot idiom (quoted files, cmap_
    palette) recovers as a heatmap even without a metadata block."""
    (tmp_path / "grid.z").write_text(
        "! nx 2 ny 2 xmin 0 xmax 1 ymin 0 ymax 1\n0 1\n1 2\n", encoding="utf-8"
    )
    from gleplot import palettes

    src = (
        "size 10 10\n" + palettes.palette_sub_text("viridis") + "\n" + "begin graph\n"
        '   colormap "grid.z" 100 100 palette cmap_viridis\n'
        "end graph\n"
    )
    p = tmp_path / "f.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.heatmaps) == 1
    assert ax.heatmaps[0]["cmap"] == "viridis"
    # The wrapper sub is not flagged as a programmatic file.
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


def test_a_gleplot_5_contour_label_sub_is_kept_as_raw_gle(tmp_path):
    path = tmp_path / "old.gle"
    path.write_text(
        "size 10 10\n"
        "sub gleplot_contour_labels file$ format$\n"
        "   write format$\n"
        "end sub\n"
        "begin graph\n    xaxis min 0 max 3\nend graph\n"
        "amove 0 0\n"
        'gleplot_contour_labels file "g_contour1-clabels.dat" format "fix 2"\n'
    )
    rec = parse_gle_figure(path)
    assert any("gleplot_contour_labels" in w for w in rec.warnings)
    text = rec.figure._generate_gle_with_files()[0]
    assert "sub gleplot_contour_labels file$ format$" in text
    assert 'gleplot_contour_labels file "g_contour1-clabels.dat" format "fix 2"' in text


def _as_gleplot_5(path: Path, cmap: str, old: str) -> None:
    """Rewrite a saved file the way gleplot 5 named ``cmap``'s palette sub."""
    text = path.read_text("utf-8").replace('include "palettes.gle"\n', "")
    text = text.replace("glp_", "gleplot_")
    text = text.replace(f"cmap_{cmap}", f"gleplot_{old}")
    path.write_text(text.replace(f"_cdata_fcircle_{cmap}", f"_cdata_fcircle_{old}"))


def test_a_gleplot_5_palette_sub_and_its_colormap_are_kept_as_raw_gle(tmp_path):
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).imshow(np.arange(4.0).reshape(2, 2), cmap="viridis")
    path = _save(fig, tmp_path)
    _as_gleplot_5(path, "viridis", "viridis")
    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].heatmaps
    assert any("'gleplot_viridis' is a sub gleplot 5 wrote" in w for w in rec.warnings)
    text = rec.figure._generate_gle_with_files()[0]
    assert "sub gleplot_viridis z" in text
    assert "palette gleplot_viridis" in text
    assert "cmap_viridis" not in text


@pytest.mark.parametrize("cmap, old", [("viridis", "viridis"), ("plasma", "rdbu")])
def test_a_gleplot_5_coloured_scatter_stays_raw(tmp_path, cmap, old):
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).scatter([0, 1], [0, 1], c=[0, 1], cmap=cmap)
    path = _save(fig, tmp_path)
    _as_gleplot_5(path, cmap, old)
    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].scatters
    text = rec.figure._generate_gle_with_files()[0]
    for kept in (
        f"sub gleplot_{old} z",
        f"sub gleplot_cdata_fcircle_{old} size data",
        f"set color gleplot_{old}(data)",
        f"define marker gleplot_cdata_fcircle_{old} gleplot_cdata_fcircle_{old}",
        f"marker gleplot_cdata_fcircle_{old} msize",
    ):
        assert kept in text
    assert "cmap_" not in text


def test_a_palette_sub_of_ones_own_keeps_its_colormap_raw(tmp_path):
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).imshow(np.arange(4.0).reshape(2, 2), cmap="magma")
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace("return magma(", "return viridis(")
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].heatmaps
    again = rec.figure._generate_gle_with_files()[0]
    assert again.count("sub cmap_magma z") == 1
    assert "   return viridis(max(0,min(1,z)))" in again
    # GLE looks the routine up when it reads the sub.
    assert again.index('include "palettes.gle"') < again.index("sub cmap_magma z")
    assert "palette cmap_magma" in again


def test_a_colormap_kept_raw_keeps_the_palette_sub_it_calls(tmp_path):
    fig = glp.figure(data_prefix="g")
    fig.add_subplot(111).imshow(np.arange(4.0).reshape(2, 2), cmap="magma")
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace(
        "palette cmap_magma", "palette cmap_magma interpolate bilinear"
    )
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path)
    assert not rec.figure.axes_list[0].heatmaps
    again = rec.figure._generate_gle_with_files()[0]
    assert again == text


def test_a_palette_sub_of_ones_own_is_kept_for_what_calls_it(tmp_path):
    """Nothing gleplot reads calls it, and its include stays ahead of it."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.imshow(np.arange(4.0).reshape(2, 2), cmap="magma")
    ax.scatter([0, 1], [0, 1], c=[0, 1], cmap="viridis")
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace(
        "return viridis(max(0,min(1,z)))", "return viridis(1-z)"
    )
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].heatmaps
    assert not rec.figure.axes_list[0].scatters
    again = rec.figure._generate_gle_with_files()[0]
    assert again.count("sub cmap_viridis z") == 1
    assert again.count('include "palettes.gle"') == 1
    assert again.index('include "palettes.gle"') < again.index("sub cmap_viridis z")
    assert "sub cmap_magma z" in again
    assert _resave(tmp_path, again) == again


def _resave(tmp_path: Path, text: str) -> str:
    path = tmp_path / "again.gle"
    path.write_text(text, encoding="utf-8")
    return parse_gle_figure(path).figure._generate_gle_with_files()[0]


def test_a_cut_short_palette_sub_is_kept_as_raw_gle(tmp_path):
    path = tmp_path / "short.gle"
    path.write_text("size 10 10\nsub cmap_viridis z\n", encoding="utf-8")
    text = parse_gle_figure(path).figure._generate_gle_with_files()[0]
    assert "sub cmap_viridis z" in text


def test_a_contour_line_with_no_color_or_width_stays_unset(tmp_path):
    """#454: GLE draws it in the current colour and width; so does the save."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    ax.contour(np.arange(9.0).reshape(3, 3), levels=[4.0])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8")
    line = next(s for s in text.splitlines() if s.strip().startswith("d1 line"))
    path.write_text(text.replace(line, "    d1 line"), encoding="utf-8")

    rec = parse_gle_figure(path)
    (contour,) = rec.figure.axes_list[0].contours
    assert contour["color"] is None and contour["linewidth"] is None
    again = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(again))
    assert "    d1 line\n" in again.read_text("utf-8")


def test_a_bar_kept_raw_between_graphs_keeps_the_palette_sub_it_calls(tmp_path):
    fig, (left, right) = glp.subplots(1, 2, data_prefix="g")
    left.scatter([0, 1], [0, 1], c=[0, 1], cmap="magma")
    fig.colorbar(ax=left)
    right.plot([0, 1], [0, 1])
    path = _save(fig, tmp_path)
    text = path.read_text("utf-8").replace(
        'palette "cmap_magma" width', 'palette "cmap_plasma" width'
    )
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path).figure
    assert "colorbar" not in rec.axes_list[0].scatters[0]
    kept = rec.axes_list[0].trailing_passthrough
    assert any("cmap_plasma" in line for line in kept)
    again = rec._generate_gle_with_files()[0]
    assert "sub cmap_plasma z" in again
    assert _resave(tmp_path, again) == again


def test_a_contourf_bar_whose_gap_cannot_be_read_keeps_its_colours(tmp_path):
    """Kept raw, the bar would lose the band sub's rescale it draws through."""
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 1, 5)
    cf = ax.contourf(x, x, np.add.outer(x, x), [0, 0.5, 1, 1.5, 2])
    fig.colorbar(cf)
    path = _save(fig, tmp_path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("xg(xgmax)+0.3 ", "xg(xgmax)-0.3 "), encoding="utf-8")
    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].heatmaps[0]["colorbar"]["sep"] == 0.3
    (note,) = rec.warnings
    assert "written back at the default gap" in note
    assert rec.figure._generate_gle_with_files()[0] == text


@pytest.mark.parametrize(
    "old, new",
    [
        # The label's gap from the bar, edited by hand.
        ("0.5*5/3+0.2)", "0.5*5/3+0.4)"),
        # The label itself, written another way.
        ('write "Z"', 'write "Z" ! the z axis'),
    ],
    ids=["label-gap", "label-line"],
)
def test_a_contourf_bar_kept_raw_keeps_the_rescale_it_draws_through(tmp_path, old, new):
    fig = glp.figure(data_prefix="g")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 1, 5)
    cf = ax.contourf(x, x, np.add.outer(x, x), [0, 0.5, 1, 1.5, 2])
    fig.colorbar(cf, label="Z")
    path = _save(fig, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert old in text
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path)
    (hm,) = rec.figure.axes_list[0].heatmaps
    assert hm["colorbar"] is None
    assert any("color_range_vertical" in line for line in rec.figure._trailer_lines())
    again = rec.figure._generate_gle_with_files()[0]
    assert "   z = 0*(1-z)+2*z" in again
    assert again == text


def test_a_band_sub_kept_raw_keeps_its_name(tmp_path):
    """#549: a graph kept raw inside 'begin translate' keeps the band sub it
    calls, so the band sub of the graph that is read takes another name."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="g")
    x = np.linspace(0, 1, 30)
    left.contourf(x, x, np.add.outer(x, x), [0, 0.3, 0.6, 1])
    right.contourf(x, x, np.add.outer(x, x), [0, 0.5, 1, 2])
    path = _save(fig, tmp_path)
    text = re.sub(
        r"amove [^\n]*\nbegin graph",
        "begin translate 0 0\nbegin graph",
        path.read_text(encoding="utf-8"),
        count=1,
    ).replace("end graph", "end graph\nend translate", 1)
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path).figure
    assert len(rec.axes_list) == 1
    again = rec._generate_gle_with_files()[0]
    assert re.findall(r"^sub (glp_contourf\d+)", again, re.MULTILINE) == [
        "glp_contourf1",
        "glp_contourf2",
    ]
    assert again.count("palette glp_contourf1") == 1
    assert again.count("palette glp_contourf2") == 1
    assert _resave(tmp_path, again) == again

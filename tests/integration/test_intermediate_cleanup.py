"""G8: unique per-figure contour/fitz stems + post-compile intermediate cleanup.

GLEstudio SPEC 9.1/10.8: ``begin contour``/``fitz`` make the ``gle`` binary
itself write extra files (``<stem>-cdata.dat``/``-clabels.dat``/
``-cvalues.dat``, and a points-sourced heatmap/contour's generated ``.z``)
into the directory it compiles from, as an undocumented side effect. These
tests exercise the real ``gle`` binary (skipped when it is not installed,
matching the convention in ``test_contour_compilation.py``) to verify:

- two contour series in one figure get distinct stems and both plot;
- a compiled ``savefig`` leaves no engine-generated intermediates behind;
- a user file with a similar-but-different name survives cleanup untouched;
- ``keep_intermediates=True`` opts out of cleanup.

Cross-figure stem uniqueness (default-prefix figures sharing the module-level
counter) and the exact-filename cleanup helper are covered without a
compiler in ``tests/unit/test_contour_heatmap.py`` and
``tests/unit/test_compiler.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")


def _grid_contour(ax, x, y, seed):
    rng = np.random.default_rng(seed)
    Z = np.sin(x[None, :] / 3 + rng.uniform()) * np.cos(y[:, None] / 3)
    return ax.contour(x, y, Z, levels=[-0.3, 0.0, 0.3], clabel=True, clabel_fmt="fix 2")


def test_two_contours_one_figure_distinct_stems_and_both_plot(tmp_path):
    """Two ``begin contour`` series in one figure never collide on filenames."""
    fig = glp.figure(figsize=(7, 6))
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 21)
    y = np.linspace(0, 8, 17)
    ct1 = _grid_contour(ax, x, y, seed=1)
    ct2 = _grid_contour(ax, x, y, seed=2)

    assert ct1["data_file"] != ct2["data_file"]

    out = fig.savefig(str(tmp_path / "two_contours.png"))
    assert out.exists() and out.stat().st_size > 0

    text, _ = fig._generate_gle_with_files()
    # Both contour blocks made it into the script, each reading its own .z.
    assert text.count("begin contour") == 2
    assert f'data "{ct1["data_file"]}"' in text
    assert f'data "{ct2["data_file"]}"' in text


def test_savefig_compile_cleans_up_contour_intermediates(tmp_path):
    """PNG/PDF export leaves no ``-cdata``/``-clabels``/``-cvalues``/fitz ``.z``."""
    for fmt in ("png", "pdf"):
        out_dir = tmp_path / fmt
        out_dir.mkdir()
        fig = glp.figure(figsize=(7, 6), data_prefix="t")
        ax = fig.add_subplot(111)
        x = np.linspace(0, 10, 21)
        y = np.linspace(0, 8, 17)
        _grid_contour(ax, x, y, seed=3)

        out = fig.savefig(str(out_dir / f"fig.{fmt}"))
        assert out.exists() and out.stat().st_size > 0

        leftovers = sorted(
            p.name
            for p in out_dir.iterdir()
            if p.name.endswith(("-cdata.dat", "-clabels.dat", "-cvalues.dat"))
        )
        assert leftovers == [], f"engine intermediates not cleaned up: {leftovers}"
        # The gleplot-written .z sidecar itself (grid source) is NOT an
        # engine intermediate -- it must survive cleanup.
        assert (out_dir / "t_contour1.z").exists()


def test_savefig_compile_cleans_up_fitz_z_for_points_source(tmp_path):
    """A points-sourced (fitz) contour's generated ``.z`` is also removed,
    while the raw points ``.dat`` gleplot wrote as fitz's input survives."""
    fig = glp.figure(figsize=(7, 6), data_prefix="t")
    ax = fig.add_subplot(111)
    rng = np.random.default_rng(9)
    xs = rng.uniform(0, 10, 80)
    ys = rng.uniform(0, 8, 80)
    zs = np.sin(xs) * np.cos(ys)
    ct = ax.tricontour(
        xs, ys, zs, gridsize=(21, 17), extent=(0, 10, 0, 8), ncontour=3, clabel=True
    )
    points_dat = ct["data_file"]
    fitz_z = points_dat[:-4] + ".z"

    out = fig.savefig(str(tmp_path / "fitz.png"))
    assert out.exists() and out.stat().st_size > 0

    remaining = {p.name for p in tmp_path.iterdir()}
    assert points_dat in remaining  # gleplot's own input sidecar: kept
    assert fitz_z not in remaining  # GLE's fitz output: cleaned up
    assert not any(
        n.endswith(("-cdata.dat", "-clabels.dat", "-cvalues.dat")) for n in remaining
    )


def test_similar_but_different_user_file_survives_cleanup(tmp_path):
    """A user file that merely LOOKS like a generated intermediate is never
    touched -- cleanup matches by exact name, never glob/prefix."""
    fig = glp.figure(figsize=(7, 6), data_prefix="t")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 21)
    y = np.linspace(0, 8, 17)
    _grid_contour(ax, x, y, seed=4)

    # Same suffix, different stem -- not this figure's own stem.
    decoy = tmp_path / "userdata_contour1-cdata.dat"
    decoy.write_text("do not delete me\n")
    # Same stem prefix, but this figure never reserves this exact name.
    decoy2 = tmp_path / "t_contour1-cdata.dat.bak"
    decoy2.write_text("do not delete me either\n")

    out = fig.savefig(str(tmp_path / "fig.png"))
    assert out.exists() and out.stat().st_size > 0

    assert decoy.exists()
    assert decoy.read_text() == "do not delete me\n"
    assert decoy2.exists()
    assert decoy2.read_text() == "do not delete me either\n"


def test_keep_intermediates_opts_out_of_cleanup(tmp_path):
    fig = glp.figure(figsize=(7, 6), data_prefix="t")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 21)
    y = np.linspace(0, 8, 17)
    _grid_contour(ax, x, y, seed=5)

    out = fig.savefig(str(tmp_path / "fig.png"), keep_intermediates=True)
    assert out.exists() and out.stat().st_size > 0

    names = {p.name for p in tmp_path.iterdir()}
    assert "t_contour1-cdata.dat" in names
    assert "t_contour1-clabels.dat" in names
    assert "t_contour1-cvalues.dat" in names

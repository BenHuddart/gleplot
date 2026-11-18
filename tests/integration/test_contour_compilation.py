"""End-to-end compilation of a contour/heatmap figure to PNG with real GLE.

Exercises the full pipeline (imshow/tripcolor + tricontour + colorbar + palette
subs + fitz/contour blocks) through the actual ``gle`` binary and asserts a
nonempty raster is produced. Skipped when GLE is not installed.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from tests.integration.conftest import darwin_gle_contour_crash

pytestmark = pytest.mark.gle


def test_tripcolor_only_compiles(tmp_path):
    """fitz gridding + colormap without any contour block (runs everywhere,
    including macOS — see darwin_gle_contour_crash)."""
    rng = np.random.default_rng(7)
    x = rng.uniform(0.0, 5.0, 200)
    y = rng.uniform(0.0, 3.0, 200)
    z = np.exp(-((x - 2.5) ** 2 + (y - 1.5) ** 2))

    fig = glp.figure(figsize=(7, 6), data_prefix="tponly")
    ax = fig.add_subplot(111)
    ax.tripcolor(x, y, z, gridsize=(40, 30), extent=(0.0, 5.0, 0.0, 3.0))

    out = fig.savefig(str(tmp_path / "tponly.png"))
    assert out.exists()
    assert out.stat().st_size > 0


@darwin_gle_contour_crash
def test_phase_diagram_like_tripcolor_tricontour_colorbar_compiles(tmp_path):
    # Synthetic susceptibility-like field chi(T, H): a Neel boundary
    # T_N(H) = T_N0 * sqrt(1 - (H/Hc)^2) with a ridge in chi at the boundary.
    rng = np.random.default_rng(3)
    T = rng.uniform(0.2, 5.0, 400)
    H = rng.uniform(0.0, 3.0, 400)
    Hc, TN0 = 3.2, 5.0
    boundary = TN0 * np.sqrt(np.clip(1.0 - (H / Hc) ** 2, 0.0, None))
    chi = np.exp(-((T - boundary) ** 2) / 0.4) + 0.05 * T

    fig = glp.figure(figsize=(9, 6), data_prefix="phase")
    ax = fig.add_subplot(111)
    ax.tripcolor(
        T, H, chi, gridsize=(60, 40), extent=(0.2, 5.0, 0.0, 3.0), cmap="viridis"
    )
    ax.tricontour(
        T,
        H,
        chi,
        gridsize=(60, 40),
        extent=(0.2, 5.0, 0.0, 3.0),
        ncontour=4,
        levels=[0.4, 0.7, 0.9],
        colors="white",
        clabel=True,
    )
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Magnetic field (T)")
    fig.colorbar(label="chi (emu/mol)", format="fix 1")

    out = fig.savefig(str(tmp_path / "phase.png"))
    assert out.exists()
    assert out.stat().st_size > 0


def test_imshow_colorbar_compiles(tmp_path):
    y, x = np.mgrid[0:40, 0:50]
    Z = np.sin(x / 6.0) * np.cos(y / 5.0)

    fig = glp.figure(figsize=(7, 6), data_prefix="im")
    ax = fig.add_subplot(111)
    ax.imshow(Z, extent=(0, 10, 0, 8), cmap="magma", vmin=-1, vmax=1)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.colorbar(label="signal")

    out = fig.savefig(str(tmp_path / "im.png"))
    assert out.exists()
    assert out.stat().st_size > 0


def test_function2d_colorbar_compiles(tmp_path):
    """GLE evaluates the bare expression; a quoted one would fail to compile."""
    fig = glp.figure(figsize=(7, 6), data_prefix="fn")
    ax = fig.add_subplot(111)
    ax.function2d("sin(x)*cos(y)", extent=(0, 6.28, 0, 6.28), vmin=-1, vmax=1)
    fig.colorbar(label="signal")

    out = fig.savefig(str(tmp_path / "fn.png"))
    assert out.exists()
    assert out.stat().st_size > 0


def test_constant_field_colorbar_compiles(tmp_path):
    """A constant Z (zmax == zmin) must not divide-by-zero in the colorbar sub
    and abort the render (regression: the degenerate-range guard)."""
    fig = glp.figure(figsize=(7, 6), data_prefix="const")
    ax = fig.add_subplot(111)
    ax.imshow(np.full((20, 25), 7.0), extent=(0, 10, 0, 8), cmap="viridis")
    fig.colorbar(label="constant")

    out = fig.savefig(str(tmp_path / "const.png"))
    assert out.exists()
    assert out.stat().st_size > 0


def test_all_palettes_compile(tmp_path):
    """Every supported palette, and its reversed form, compiles with a colorbar."""
    from gleplot.palettes import SUPPORTED_CMAPS

    y, x = np.mgrid[0:20, 0:24]
    Z = np.sin(x / 5.0) * np.cos(y / 4.0)
    for cmap in [name + r for name in SUPPORTED_CMAPS for r in ("", "_r")]:
        fig = glp.figure(figsize=(6, 5), data_prefix=f"pal_{cmap}")
        ax = fig.add_subplot(111)
        ax.imshow(Z, extent=(0, 10, 0, 8), cmap=cmap)
        fig.colorbar(label=cmap)
        out = fig.savefig(str(tmp_path / f"{cmap}.png"))
        assert out.exists() and out.stat().st_size > 0, cmap

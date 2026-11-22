"""Heatmap (imshow) example: a gridded 2-D Gaussian with a contour overlay."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_heatmap_imshow():
    """``imshow`` of a gridded 2-D Gaussian with a contour overlay and a colorbar.

    A single ``add_subplot(111)`` axes -- the canonical form. gleplot reserves
    room to the right of the graph for the colorbar automatically, so the bar,
    its tick numbers and its rotated label are not clipped at the page edge.
    """
    print("Creating example: Heatmap (imshow)...")

    nx, ny = 120, 100
    x = np.linspace(-3, 3, nx)
    y = np.linspace(-2.5, 2.5, ny)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2) / 2.0)

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Gridded heatmap. origin='lower' (the default) puts row 0 of Z at ymin,
    # matching np.meshgrid's row-0-is-y[0] layout, so no flipping is needed.
    ax.imshow(Z, extent=(x[0], x[-1], y[0], y[-1]), cmap="viridis")

    # Contour lines traced on the same grid, drawn on top of the heatmap.
    ax.contour(x, y, Z, levels=6, colors="white", linewidths=0.7)

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("2-D Gaussian (imshow + contour)")

    fig.colorbar(label="amplitude")

    fig.savefig_gle("example_heatmap_imshow.gle")
    print("  Saved to example_heatmap_imshow.gle")


def example_gridded_maps():
    """Three colour maps of gridded data, each with its colorbar. ``pcolormesh``
    colours each cell of a grid; ``contourf`` fills the bands between contour
    levels, here with ``contour`` lines and their labels on top; and
    ``function2d`` has GLE evaluate an expression at every pixel, so no data
    file is written. The colorbars are drawn by GLE's ``color.gle``.
    """
    print("Creating example: Gridded maps...")

    fig, (ax1, ax2, ax3) = glp.subplots(1, 3, figsize=(15, 4.5))

    # pcolormesh: a coarse grid, given by its cell edges.
    xe = np.arange(0, 9)
    ye = np.arange(0, 7)
    xc = 0.5 * (xe[:-1] + xe[1:])
    yc = 0.5 * (ye[:-1] + ye[1:])
    C = np.sin(xc[None, :] / 2) * np.cos(yc[:, None] / 2)
    mesh = ax1.pcolormesh(xe, ye, C, cmap="RdBu", vmin=-1, vmax=1)
    fig.colorbar(mesh, ax=ax1, label="C")
    ax1.set_xlabel("x")
    ax1.set_ylabel("y")
    ax1.set_title("pcolormesh")

    # contourf: filled bands between round-number levels, with labelled lines.
    x = np.linspace(-2, 2, 81)
    y = np.linspace(-2, 2, 81)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-((X - 0.5) ** 2 + Y**2)) - 0.7 * np.exp(-((X + 0.8) ** 2 + Y**2) * 2)
    bands = ax2.contourf(x, y, Z, levels=8, cmap="viridis")
    ax2.contour(x, y, Z, levels=[-0.4, 0.0, 0.4, 0.8], colors="white", clabel=True)
    fig.colorbar(bands, ax=ax2, label="Z")
    ax2.set_xlabel("x")
    ax2.set_title("contourf + contour")

    # function2d: GLE computes the map from the expression itself.
    image = ax3.function2d(
        "sin(x)*cos(y)", extent=(-3, 3, -3, 3), cmap="magma", vmin=-1, vmax=1
    )
    fig.colorbar(image, ax=ax3)
    ax3.set_xlabel("x")
    ax3.set_title("function2d: sin(x)cos(y)")

    fig.savefig("example_gridded_maps.gle")
    print("  ✓ Saved to example_gridded_maps.gle")


if __name__ == "__main__":
    example_heatmap_imshow()
    example_gridded_maps()

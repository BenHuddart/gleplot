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

    fig.colorbar()

    fig.savefig_gle("example_heatmap_imshow.gle")
    print("  Saved to example_heatmap_imshow.gle")


if __name__ == "__main__":
    example_heatmap_imshow()

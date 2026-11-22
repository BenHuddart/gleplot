"""Scatter plot example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_scatter_plot():
    """Scatter of random data with a linear trend line fitted to it."""
    print("Creating example: Scatter plot...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Create random data
    np.random.seed(42)
    n = 50
    x = np.random.randn(n)
    y = 2 * x + np.random.randn(n) * 0.5

    # Scatter plot
    ax.scatter(x, y, color="blue", s=20, marker="o", label="Data points")

    # Add trend line
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, p(x_line), color="red", linestyle="--", label="Trend")

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Scatter Plot with Trend Line")
    ax.legend()

    fig.savefig("example_scatter_plot.gle")
    print("  ✓ Saved to example_scatter_plot.gle")


def example_scatter_colormap():
    """Scatter with ``c=`` one number per point: each marker takes its colour
    from the colormap, through GLE's per-point marker colour. The colorbar
    beside it shows the scale, as for a heatmap.
    """
    print("Creating example: Colour-mapped scatter...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    rng = np.random.default_rng(7)
    n = 80
    x = rng.uniform(0, 10, n)
    y = rng.uniform(0, 10, n)
    distance = np.hypot(x - 5, y - 5)

    ax.scatter(x, y, s=60, c=distance, cmap="plasma", vmin=0, vmax=7)
    fig.colorbar(ax=ax, label="Distance from centre", nticks=7)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Colour-mapped Scatter")

    fig.savefig("example_scatter_colormap.gle")
    print("  ✓ Saved to example_scatter_colormap.gle")


if __name__ == "__main__":
    example_scatter_plot()
    example_scatter_colormap()

"""Polar plot example: a data curve, a function curve and a legend."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_polar_plot():
    """A polar axes from ``add_subplot(projection='polar')``.

    ``plot`` takes theta in radians and the radius; ``function`` draws the
    rose ``r = cos(2 theta)`` from GLE's own samples. The grid of rings and
    spokes, labelled with the angles and radii, replaces the frame, and
    ``set_ylim`` sets the outer ring.
    """
    print("Creating example: Polar Plot...")

    theta = np.linspace(0, 2 * np.pi, 200)
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(projection="polar")
    ax.plot(theta, 1 + 0.5 * np.cos(3 * theta), label="lobes")
    ax.function("cos(2*x)", color="C1", linestyle="--", label="rose")
    ax.set_ylim(0, 2)
    ax.set_title("Polar curves")
    ax.legend(loc="upper right")

    fig.savefig_gle("example_polar_plot.gle")
    print("  Saved to example_polar_plot.gle")


if __name__ == "__main__":
    example_polar_plot()

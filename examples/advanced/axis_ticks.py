"""Axis, tick and grid control example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_axis_and_ticks():
    """Four ways to change an axis. Tick positions with text labels and a
    grid; ``semilogy`` with minor ticks; outward ticks from ``tick_params``
    with a GLE number format from ``set_tick_format``; and an inverted y axis
    with only the bottom and left axis lines, from ``set_axis_line``.
    """
    print("Creating example: Axis and ticks...")

    fig, axes = glp.subplots(2, 2, figsize=(10, 8))

    # Text tick labels at chosen positions, and a grid behind the data.
    months = np.arange(1, 13)
    rain = np.array([78, 60, 64, 55, 52, 58, 50, 62, 65, 82, 85, 88])
    ax = axes[0, 0]
    ax.plot(months, rain, "o-")
    ax.set_xticks([1, 4, 7, 10], ["Jan", "Apr", "Jul", "Oct"])
    ax.set_xlim(0.5, 12.5)
    ax.set_ylim(40, 100)
    ax.grid(color="lightgray")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_title("set_xticks + grid")

    # A log y axis with minor ticks.
    x = np.linspace(0, 5, 50)
    ax = axes[0, 1]
    ax.semilogy(x, np.exp(2 * x), label="$e^{2x}$")
    ax.semilogy(x, 10 * np.exp(x), "--", label="$10 e^x$")
    ax.minorticks_on()
    ax.set_xlim(0, 5)
    ax.set_title("semilogy + minorticks_on")
    ax.legend(loc="upper left")

    # Outward ticks, and tick labels with a fixed number of decimals.
    ax = axes[1, 0]
    ax.plot(x / 10, np.sqrt(x / 10), color="C2")
    ax.tick_params(direction="out", length=5)
    ax.set_tick_format("fix 2")
    ax.set_xlim(0, 0.5)
    ax.set_ylim(0, 0.8)
    ax.set_title("tick_params + set_tick_format")

    # Depth increases downwards; the top and right axis lines are hidden.
    depth = np.linspace(0, 50, 60)
    ax = axes[1, 1]
    ax.plot(20 - 0.3 * depth + np.sin(depth / 3), depth, color="C3")
    ax.invert_yaxis()
    ax.set_axis_line("x2", visible=False)
    ax.set_axis_line("y2", visible=False)
    ax.set_xlabel("Temperature (C)")
    ax.set_ylabel("Depth (m)")
    ax.set_title("invert_yaxis + set_axis_line")

    fig.savefig("example_axis_ticks.gle")
    print("  ✓ Saved to example_axis_ticks.gle")


if __name__ == "__main__":
    example_axis_and_ticks()

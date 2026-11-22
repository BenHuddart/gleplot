"""Subplot examples.

Demonstrates how to create multi-panel figures using gleplot's subplot
support. Each subplot is a separate GLE graph block positioned with
``amove`` and given explicit dimensions via the ``size`` command.
"""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_side_by_side():
    """Two plots side by side in a 1x2 grid."""
    print("Creating example: Side-by-side subplots...")

    fig, axes = glp.subplots(1, 2, figsize=(14, 6))

    x = np.linspace(0, 2 * np.pi, 80)

    # Left: sine
    axes[0].plot(x, np.sin(x), color="blue", label="sin(x)")
    axes[0].set_xlabel("x (radians)")
    axes[0].set_ylabel("y")
    axes[0].set_title("Sine")
    axes[0].legend()

    # Right: cosine
    axes[1].plot(x, np.cos(x), color="red", label="cos(x)")
    axes[1].set_xlabel("x (radians)")
    axes[1].set_ylabel("y")
    axes[1].set_title("Cosine")
    axes[1].legend()

    fig.savefig("example_subplots_1x2.gle")
    print("  ✓ Saved to example_subplots_1x2.gle")


def example_stacked():
    """Two stacked panels: a fit with error bars on top and its residuals below."""
    print("Creating example: Stacked subplots...")

    fig, axes = glp.subplots(2, 1, figsize=(8, 10))

    x = np.linspace(0, 10, 60)

    # Top: linear data with error bars
    y1 = 2 * x + 3 + np.random.default_rng(42).normal(0, 1, len(x))
    axes[0].errorbar(
        x,
        y1,
        yerr=1.0,
        marker="o",
        linestyle="none",
        color="blue",
        label="Measurements",
    )
    axes[0].plot(x, 2 * x + 3, color="red", linestyle="--", label="Fit")
    axes[0].set_xlabel("x")
    axes[0].set_ylabel("y")
    axes[0].set_title("Linear Fit with Error Bars")
    axes[0].legend()

    # Bottom: residuals
    residuals = y1 - (2 * x + 3)
    axes[1].scatter(x, residuals, color="green", marker="o")
    axes[1].set_xlabel("x")
    axes[1].set_ylabel("Residual")
    axes[1].set_title("Residuals")
    axes[1].set_ylim(-4, 4)

    fig.savefig("example_subplots_2x1.gle")
    print("  ✓ Saved to example_subplots_2x1.gle")


def example_2x2_grid():
    """Four plot types in a 2x2 grid: line, scatter, bar, and asymmetric error
    bars.
    """
    print("Creating example: 2x2 subplot grid...")

    fig, axes = glp.subplots(2, 2, figsize=(12, 10))

    x = np.linspace(0, 2 * np.pi, 50)

    # Top-left: line plot
    axes[0, 0].plot(x, np.sin(x), color="blue", label="sin")
    axes[0, 0].plot(x, np.cos(x), color="red", linestyle="--", label="cos")
    axes[0, 0].set_title("Trig Functions")
    axes[0, 0].set_xlabel("x")
    axes[0, 0].set_ylabel("y")
    axes[0, 0].legend()

    # Top-right: scatter
    np.random.seed(42)
    xs = np.random.randn(40)
    ys = 0.8 * xs + np.random.randn(40) * 0.3
    axes[0, 1].scatter(xs, ys, color="green", marker="o", label="Data")
    axes[0, 1].set_title("Correlation")
    axes[0, 1].set_xlabel("x")
    axes[0, 1].set_ylabel("y")

    # Bottom-left: bar chart
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([12, 25, 18, 30, 22])
    axes[1, 0].bar(categories, values, color="blue")
    axes[1, 0].set_title("Bar Chart")
    axes[1, 0].set_xlabel("Category")
    axes[1, 0].set_ylabel("Count")

    # Bottom-right: error bars
    xm = np.array([1, 2, 3, 4, 5])
    ym = np.array([10, 18, 25, 35, 42])
    axes[1, 1].errorbar(
        xm,
        ym,
        yerr=([2, 3, 2, 4, 3], [3, 2, 4, 3, 5]),
        marker="s",
        linestyle="none",
        color="red",
        capsize=3,
        label="±err",
    )
    axes[1, 1].set_title("Error Bars")
    axes[1, 1].set_xlabel("x")
    axes[1, 1].set_ylabel("y")
    axes[1, 1].legend()

    fig.savefig("example_subplots_2x2.gle")
    print("  ✓ Saved to example_subplots_2x2.gle")


def example_1x3_comparison():
    """Three panels in a row comparing families of functions."""
    print("Creating example: 1x3 comparison...")

    fig, axes = glp.subplots(1, 3, figsize=(18, 5))

    x = np.linspace(0.1, 5, 80)

    axes[0].plot(x, x, color="blue", label="y = x")
    axes[0].plot(x, x**2, color="red", linestyle="--", label="y = x²")
    axes[0].set_title("Polynomial")
    axes[0].set_xlabel("x")
    axes[0].legend()

    axes[1].plot(x, np.log(x), color="green", label="y = ln(x)")
    axes[1].plot(x, np.sqrt(x), color="blue", linestyle="--", label="y = √x")
    axes[1].set_title("Roots & Logs")
    axes[1].set_xlabel("x")
    axes[1].legend()

    axes[2].plot(x, np.exp(-x), color="red", label="y = e⁻ˣ")
    axes[2].plot(x, 1 / x, color="blue", linestyle=":", label="y = 1/x")
    axes[2].set_title("Decay Functions")
    axes[2].set_xlabel("x")
    axes[2].set_ylim(0, 5)
    axes[2].legend()

    fig.savefig("example_subplots_1x3.gle")
    print("  ✓ Saved to example_subplots_1x3.gle")


def example_subplot_ratios():
    """A scatter with its marginal distributions. ``width_ratios`` and
    ``height_ratios`` size the grid's columns and rows; ``sharex='col'`` and
    ``sharey='row'`` give each column one x range and each row one y range, so
    the margins line up with the scatter. The corner axes is switched off.
    """
    print("Creating example: Subplot ratios...")

    fig, axes = glp.subplots(
        2,
        2,
        figsize=(7, 7),
        sharex="col",
        sharey="row",
        width_ratios=[4, 1],
        height_ratios=[1, 4],
    )
    top, corner = axes[0]
    main, right = axes[1]

    rng = np.random.default_rng(11)
    x = rng.normal(0, 1, 400)
    y = 0.6 * x + rng.normal(0, 0.8, 400)
    edges = np.linspace(-4, 4, 25)

    main.scatter(x, y, s=8, color="C0")
    main.set_xlim(-4, 4)
    main.set_ylim(-4, 4)
    main.set_xlabel("x")
    main.set_ylabel("y")

    # x margin: a histogram over the shared x range.
    top.hist(x, bins=24, range=(-4, 4), histtype="stepfilled", color="C0")

    # y margin: GLE's histogram is vertical, so the counts are drawn as bars.
    counts, _ = np.histogram(y, bins=edges)
    centres = 0.5 * (edges[:-1] + edges[1:])
    right.barh(centres, counts, height=edges[1] - edges[0], color="C0")

    right.set_xticks(dticks=25)
    top.set_yticks(dticks=25)
    corner.set_axis_off()

    fig.savefig("example_subplot_ratios.gle")
    print("  ✓ Saved to example_subplot_ratios.gle")


def example_inset_axes():
    """An inset made with ``fig.add_axes``, placed in figure fractions, zooms
    in on part of the main plot. ``set_facecolor`` fills an axes frame with
    GLE's graph ``background``: the main axes is tinted, and the inset is
    given a white background so the curves behind it do not show through.
    """
    print("Creating example: Inset axes...")

    fig, ax = glp.subplots(figsize=(8, 6))
    ax.set_facecolor("whitesmoke")

    x = np.linspace(0, 10, 1000)
    y = np.sin(3 * x) * np.exp(-x / 5) + 0.02 * np.sin(60 * x)
    ax.plot(x, y, color="C0")
    ax.axvspan(1.8, 2.4, color="lightgray")
    ax.set_xlim(0, 10)
    ax.set_ylim(-1.5, 1.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Signal")
    ax.set_title("Inset Axes")

    inset = fig.add_axes([0.55, 0.62, 0.3, 0.22], facecolor="white")
    inset.plot(x, y, color="C0")
    inset.set_xlim(1.8, 2.4)
    inset.set_ylim(-0.7, 0.8)
    inset.set_title("1.8 to 2.4 s")

    fig.savefig("example_inset_axes.gle")
    print("  ✓ Saved to example_inset_axes.gle")


if __name__ == "__main__":
    example_side_by_side()
    example_stacked()
    example_2x2_grid()
    example_1x3_comparison()
    example_subplot_ratios()
    example_inset_axes()
    print("\nAll subplot examples created.")

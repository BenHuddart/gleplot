"""Fill between curves example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_fill_between():
    """Shaded uncertainty band around a central line."""
    print("Creating example: Fill between...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Create data
    x = np.linspace(0, 2 * np.pi, 100)
    y_upper = np.sin(x) + 0.5
    y_lower = np.sin(x) - 0.5

    # Fill between
    ax.fill_between(x, y_lower, y_upper, color="lightblue", alpha=0.5, label="±0.5")

    # Plot center line
    ax.plot(x, np.sin(x), color="blue", label="sin(x)")

    ax.set_xlabel("x (radians)")
    ax.set_ylabel("y")
    ax.set_title("Fill Between Curves")
    ax.legend()

    fig.savefig("example_fill_between.gle")
    print("  ✓ Saved to example_fill_between.gle")


def example_fill_between_conditional():
    """Fill regions coloured differently depending on which curve is on top,
    using the ``where=`` parameter.
    """
    print("Creating example: Conditional fill between...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)

    # Fill above/below zero differently
    ax.fill_between(
        x, y1, y2, where=(y1 >= y2), color="lightblue", alpha=0.5, label="sin above cos"
    )
    ax.fill_between(
        x, y1, y2, where=(y1 < y2), color="lightcoral", alpha=0.5, label="sin below cos"
    )

    ax.plot(x, y1, color="blue", linewidth=2, label="sin(x)")
    ax.plot(x, y2, color="red", linewidth=2, linestyle="--", label="cos(x)")

    # Mark intersection points
    intersections_x = [np.pi / 4, 5 * np.pi / 4]
    intersections_y = [np.sin(np.pi / 4), np.sin(5 * np.pi / 4)]
    ax.scatter(
        intersections_x,
        intersections_y,
        color="black",
        marker="o",
        s=80,
        label="Intersections",
    )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Conditional Fill Between")
    ax.legend()
    ax.set_xlim(0, 10)

    fig.savefig("example_fill_between_conditional.gle")
    print("  ✓ Saved to example_fill_between_conditional.gle")


def example_area_fills():
    """Three more filled areas. ``fill_betweenx`` fills between two curves of
    ``y``; ``stackplot`` stacks layers as ``fill_between`` bands, taking the
    colour cycle; and ``fill`` fills one polygon. Each is a GLE ``fill``.
    """
    print("Creating example: Area fills...")

    fig, (ax1, ax2, ax3) = glp.subplots(1, 3, figsize=(14, 4.5))

    # fill_betweenx: a temperature profile against depth, with its spread.
    depth = np.linspace(0, 100, 101)
    temp = 25 - 15 * (1 - np.exp(-depth / 30))
    ax1.fill_betweenx(depth, temp - 2, temp + 2, color="lightblue", label="spread")
    ax1.plot(temp, depth, color="navy", label="mean")
    ax1.set_xlim(8, 28)
    ax1.invert_yaxis()
    ax1.set_xlabel("Temperature (C)")
    ax1.set_ylabel("Depth (m)")
    ax1.set_title("fill_betweenx")
    ax1.legend(loc="lower right")

    # stackplot: three layers stacked from zero.
    year = np.arange(2010, 2021)
    solar = np.linspace(1, 12, year.size)
    wind = np.linspace(5, 15, year.size)
    hydro = np.full(year.size, 8.0)
    ax2.stackplot(year, hydro, wind, solar, labels=["hydro", "wind", "solar"])
    ax2.set_xlim(2010, 2020)
    ax2.set_ylim(0, 40)
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Output (TWh)")
    ax2.set_title("stackplot")
    ax2.legend(loc="upper left")

    # fill: a closed polygon, here a regular hexagon and a triangle.
    t = np.linspace(0, 2 * np.pi, 7)[:-1]
    ax3.fill(np.cos(t), np.sin(t), color="khaki", label="hexagon")
    ax3.fill([-0.5, 0.5, 0.0], [-0.4, -0.4, 0.5], "C3", label="triangle")
    ax3.set_xlim(-1.5, 1.5)
    ax3.set_ylim(-1.5, 1.5)
    ax3.set_aspect("equal")
    ax3.set_title("fill")
    ax3.legend(loc="upper right")

    fig.savefig("example_area_fills.gle")
    print("  ✓ Saved to example_area_fills.gle")


def example_opaque_bands():
    """Uncertainty bands and a phase span drawn without transparency.
    ``GLEStyleConfig(opaque_backdrop="white")`` writes each ``alpha`` as the
    opaque colour it looks like over white, so the figure compiles to PDF or
    EPS without GLE's ``-cairo`` device, in GLE's default font, which draws
    the bars of ``|F|``. Where the bands overlap, the one drawn later hides
    the other instead of mixing with it.
    """
    print("Creating example: Opaque bands...")

    fig = glp.figure(figsize=(8, 6), style=glp.GLEStyleConfig(opaque_backdrop="white"))
    ax = fig.add_subplot(111)

    q = np.linspace(0, 4, 81)
    model_a = np.exp(-q) + 0.2
    model_b = 0.9 * np.exp(-0.6 * q) + 0.1
    ax.axvspan(1.0, 1.8, color="gray", alpha=0.3, label="ordered phase")
    ax.fill_between(
        q, model_a - 0.1, model_a + 0.1, color="C0", alpha=0.4, label="model A"
    )
    ax.fill_between(
        q, model_b - 0.1, model_b + 0.1, color="C1", alpha=0.4, label="model B"
    )
    ax.plot(q, model_a, color="C0")
    ax.plot(q, model_b, color="C1")

    rng = np.random.default_rng(3)
    q_obs = np.linspace(0.2, 3.8, 13)
    f_obs = np.exp(-q_obs) + 0.2 + rng.normal(0, 0.03, q_obs.size)
    ax.errorbar(q_obs, f_obs, yerr=0.05, fmt="o", color="black", label="data")

    ax.set_xlim(0, 4)
    ax.set_ylim(0, 1.4)
    ax.set_xlabel("q")
    ax.set_ylabel("|F|")
    ax.legend()

    fig.savefig("example_opaque_bands.gle")
    print("  ✓ Saved to example_opaque_bands.gle")


if __name__ == "__main__":
    example_fill_between()
    example_fill_between_conditional()
    example_area_fills()
    example_opaque_bands()

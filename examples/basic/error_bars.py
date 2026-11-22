"""Error bar plot examples.

Demonstrates how to create plots with error bars using gleplot,
including symmetric, asymmetric, and horizontal error bars.
"""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_symmetric_error_bars():
    """Symmetric vertical error bars showing measurement uncertainty."""
    print("Creating example: Symmetric error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Experimental data with constant uncertainty
    x = np.array([1, 2, 3, 4, 5, 6, 7, 8])
    y = np.array([2.1, 3.9, 6.2, 7.8, 10.1, 12.3, 13.8, 16.2])

    ax.errorbar(x, y, yerr=0.5, marker="o", fmt="-", color="blue", label="Measurement")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Distance (m)")
    ax.set_title("Symmetric Error Bars")
    ax.legend()

    fig.savefig("example_symmetric_error_bars.gle")
    print("  ✓ Saved to example_symmetric_error_bars.gle")


def example_asymmetric_error_bars():
    """Vertical error bars with different lower and upper extents."""
    print("Creating example: Asymmetric error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([10, 25, 40, 55, 70])

    # Different upper and lower error magnitudes
    yerr_lower = np.array([2, 3, 4, 5, 3])
    yerr_upper = np.array([5, 4, 6, 3, 7])

    ax.errorbar(
        x,
        y,
        yerr=(yerr_lower, yerr_upper),
        marker="s",
        linestyle="none",
        color="red",
        capsize=4,
        label="Asymmetric",
    )

    ax.set_xlabel("Category")
    ax.set_ylabel("Value")
    ax.set_title("Asymmetric Error Bars")
    ax.legend()

    fig.savefig("example_asymmetric_error_bars.gle")
    print("  ✓ Saved to example_asymmetric_error_bars.gle")


def example_horizontal_error_bars():
    """Horizontal and vertical error bars on the same points."""
    print("Creating example: Horizontal + vertical error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    np.random.seed(42)
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2.5, 4.0, 3.5, 5.0, 6.5])

    # Vertical and horizontal uncertainties
    yerr = np.array([0.4, 0.3, 0.5, 0.3, 0.4])
    xerr = np.array([0.2, 0.3, 0.15, 0.25, 0.2])

    ax.errorbar(
        x,
        y,
        yerr=yerr,
        xerr=xerr,
        marker="o",
        linestyle="none",
        color="blue",
        capsize=3,
        label="Data ± σ",
    )

    ax.set_xlabel("X measurement")
    ax.set_ylabel("Y measurement")
    ax.set_title("Horizontal and Vertical Error Bars")
    ax.legend()

    fig.savefig("example_horizontal_error_bars.gle")
    print("  ✓ Saved to example_horizontal_error_bars.gle")


def example_errorbar_with_line():
    """Error bars on points joined by a line, with an uncertainty that varies
    along the curve.
    """
    print("Creating example: Error bars with line...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.linspace(0, 2 * np.pi, 12)
    y = np.sin(x)

    # Error varies with the measurement
    yerr = 0.1 + 0.1 * np.abs(np.cos(x))

    ax.errorbar(
        x,
        y,
        yerr=yerr,
        marker="o",
        fmt="-",
        color="green",
        capsize=3,
        label="sin(x) ± δ",
    )

    ax.set_xlabel("x (radians)")
    ax.set_ylabel("sin(x)")
    ax.set_title("Error Bars on Line Plot")
    ax.legend()

    fig.savefig("example_errorbars_line.gle")
    print("  ✓ Saved to example_errorbars_line.gle")


def example_combined_errorbars():
    """Simultaneous horizontal and vertical error bars (uncertainty in both
    axes), overlaid with a fitted curve.
    """
    print("Creating example: Combined X and Y error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Calibration data with uncertainty in both axes
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([1.8, 4.2, 9.1, 16.3, 24.8])
    xerr = np.array([0.15, 0.20, 0.10, 0.25, 0.18])
    yerr = np.array([0.3, 0.5, 0.6, 0.8, 1.0])

    ax.errorbar(
        x,
        y,
        yerr=yerr,
        xerr=xerr,
        fmt="o",
        color="blue",
        capsize=4,
        label="Measured",
    )

    x_fit = np.linspace(0.5, 5.5, 100)
    ax.plot(x_fit, x_fit**2, color="red", linestyle="--", label="y = x\u00b2")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Combined X and Y Error Bars")
    ax.legend()

    fig.savefig("example_combined_errorbars.gle")
    print("  ✓ Saved to example_combined_errorbars.gle")


def example_errorbar_data_range():
    """A format string sets an error-bar series' marker and colour, as in
    matplotlib (``fmt='ko'``). ``ymin``/``ymax`` give a series its own data
    range, GLE's ``dN ymin ... ymax``: the fraction below is drawn as if the
    y axis ran from 0 to 1, so it shares the frame with the counts. The tick
    labels belong to the axis, so the legend names the second scale.
    """
    print("Creating example: Error bars with a data range...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    T = np.arange(10, 101, 10)
    counts = 900 * np.exp(-T / 40) + 50
    fraction = 1 / (1 + np.exp(-(T - 55) / 10))

    ax.errorbar(T, counts, yerr=np.sqrt(counts), fmt="ko", label="Counts")
    # Drawn against 0..1, whatever the axis range is.
    ax.errorbar(
        T,
        fraction,
        yerr=0.03,
        fmt="s--",
        color="C3",
        ymin=0,
        ymax=1,
        label="Ordered fraction (0 to 1)",
    )

    ax.set_xlim(0, 110)
    ax.set_ylim(0, 1000)
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Counts")
    ax.set_title("Error Bars with Their Own Data Range")
    ax.legend(loc="center right")

    fig.savefig("example_errorbar_data_range.gle")
    print("  ✓ Saved to example_errorbar_data_range.gle")


if __name__ == "__main__":
    example_symmetric_error_bars()
    example_asymmetric_error_bars()
    example_horizontal_error_bars()
    example_errorbar_with_line()
    example_combined_errorbars()
    example_errorbar_data_range()
    print("\nAll error bar examples created.")

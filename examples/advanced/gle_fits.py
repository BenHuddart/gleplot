"""Curves GLE computes itself: fits, functions and derived series."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_fits_and_functions():
    """Curves computed by GLE rather than in Python. On the left, ``fit`` has
    GLE fit the data: ``model='exp'`` with its fitted values shown in the
    legend, and a free ``expression`` fitted by least squares. On the right,
    ``function`` samples expressions in ``x`` and ``derived`` draws a curve
    computed from other series, here the difference of the two functions.
    """
    print("Creating example: Fits and functions...")

    fig, (ax1, ax2) = glp.subplots(1, 2, figsize=(11, 4.5))

    # Fits: GLE finds the coefficients when it draws the graph.
    rng = np.random.default_rng(5)
    t = np.linspace(0.2, 6, 25)
    counts = 80 * np.exp(-t / 1.5) + rng.normal(0, 1.5, t.size) + 3
    ax1.plot(t, counts, "ko", markersize=4, label="data")
    ax1.fit(
        t,
        counts,
        model="exp",
        color="C0",
        label="{prefactor:.1f} exp({exponent:.2f} t)",
    )
    ax1.fit(
        t,
        counts,
        expression="a*exp(-x/b)+c",
        xmin=0,
        xmax=6,
        color="C3",
        linestyle="--",
        label="a exp(-t/b) + c",
    )
    ax1.set_xlim(0, 6)
    ax1.set_ylim(0, 80)
    ax1.set_xlabel("t (ms)")
    ax1.set_ylabel("Counts")
    ax1.set_title("fit")
    ax1.legend(loc="upper right")

    # Functions and a derived curve: no data file is written for any of them.
    ax2.function("sin(x)", xmin=0, xmax=10, label="sin(x)")
    ax2.function("0.5*cos(2*x)", xmin=0, xmax=10, linestyle="--", label="cos(2x)/2")
    f, g = ax2.functions
    ax2.derived("d1-d2", [f, g], color="black", linewidth=1.5, label="difference")
    ax2.set_xlim(0, 10)
    ax2.set_ylim(-2, 2.5)
    ax2.set_xlabel("x")
    ax2.set_title("function and derived")
    ax2.legend(loc="upper right", ncol=3)

    fig.savefig("example_fits_functions.gle")
    print("  ✓ Saved to example_fits_functions.gle")


if __name__ == "__main__":
    example_fits_and_functions()

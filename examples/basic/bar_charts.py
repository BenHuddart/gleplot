"""Bar chart example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_bar_chart():
    """Bar chart of categorical data, one colour per bar."""
    print("Creating example: Bar chart...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Data
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([10, 24, 36, 18, 7])
    colors = ["red", "blue", "green", "orange", "purple"]

    # Bar chart
    ax.bar(categories, values, color=colors, label="Values")

    ax.set_xlabel("Category")
    ax.set_ylabel("Value")
    ax.set_title("Bar Chart Example")
    ax.legend()

    fig.savefig("example_bar_chart.gle")
    print("  ✓ Saved to example_bar_chart.gle")


def example_barh_and_stacked_bars():
    """Horizontal bars with ``barh``, and bars stacked with ``bottom=``. Each bar
    series is one GLE ``bar`` dataset; the tick labels name the categories.
    """
    print("Creating example: Horizontal and stacked bars...")

    fig, (ax1, ax2) = glp.subplots(1, 2, figsize=(10, 4.5))

    # Horizontal bars: y positions, then the bar lengths.
    methods = ["XRD", "NMR", "SQUID", "muSR", "Raman"]
    hours = np.array([12, 30, 8, 22, 5])
    ypos = np.arange(1, len(methods) + 1)
    ax1.barh(ypos, hours, height=0.6, color="steelblue")
    ax1.set_yticks(ypos, methods)
    ax1.set_xlim(0, 35)
    ax1.set_ylim(0.4, len(methods) + 0.6)
    ax1.set_xlabel("Beam time (hours)")
    ax1.set_title("barh")

    # Stacked bars: each layer starts where the one below it ends.
    quarters = np.arange(1, 5)
    a = np.array([5, 7, 6, 8])
    b = np.array([3, 2, 4, 3])
    c = np.array([2, 3, 2, 4])
    ax2.bar(quarters, a, width=0.6, label="Group A")
    ax2.bar(quarters, b, width=0.6, bottom=a, label="Group B")
    ax2.bar(quarters, c, width=0.6, bottom=a + b, label="Group C")
    ax2.set_xticks(quarters, ["Q1", "Q2", "Q3", "Q4"])
    ax2.set_xlim(0.4, 4.6)
    ax2.set_ylim(0, 20)
    ax2.set_ylabel("Samples")
    ax2.set_title("Stacked bar")
    ax2.legend(loc="upper left")

    fig.savefig("example_barh_stacked.gle")
    print("  ✓ Saved to example_barh_stacked.gle")


if __name__ == "__main__":
    example_bar_chart()
    example_barh_and_stacked_bars()

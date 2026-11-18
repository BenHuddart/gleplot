"""Pie chart example: labelled wedges with percentages."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_pie_chart():
    """``pie`` with labels, percentages and a title.

    The axis lines and ticks are hidden and the title stays, as in
    matplotlib. Without ``colors`` the wedges take matplotlib's default
    cycle.
    """
    print("Creating example: Pie Chart...")

    fig = glp.figure(figsize=(6, 5))
    ax = fig.add_subplot(111)
    ax.pie(
        [15, 30, 45, 10],
        labels=["Frogs", "Hogs", "Dogs", "Logs"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("Pets per household")

    fig.savefig_gle("example_pie_chart.gle")
    print("  Saved to example_pie_chart.gle")


if __name__ == "__main__":
    example_pie_chart()

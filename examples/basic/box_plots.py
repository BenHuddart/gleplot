"""Box plot example: three sample sets with fliers, means and a rug."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np

import gleplot as glp


def example_box_plot():
    """``boxplot`` of three sample sets, labelled, with their means.

    Whiskers reach the farthest data within 1.5 times the interquartile
    range; the points beyond them are drawn as fliers, as in matplotlib.
    A ``rug`` on the right edge marks every sample.
    """
    print("Creating example: Box Plot...")

    rng = np.random.default_rng(7)
    samples = [
        rng.normal(0, 1, 100),
        rng.normal(1, 2, 100),
        np.append(rng.normal(-1, 0.5, 100), [3.0, 3.5]),
    ]

    fig = glp.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.boxplot(samples, tick_labels=["Control", "Dose A", "Dose B"], showmeans=True)
    ax.rug(np.concatenate(samples), axis="y", position="right", color="gray")
    ax.set_ylabel("Response")
    ax.set_title("Response by group")

    fig.savefig_gle("example_box_plot.gle")
    print("  Saved to example_box_plot.gle")


if __name__ == "__main__":
    example_box_plot()

"""Data prefix naming example for gleplot."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_data_prefix():
    """Sidecar ``.dat`` files named by ``data_prefix`` on the figure and
    ``data_name`` on each series.
    """
    print("Creating example: data_prefix naming...")

    x = np.linspace(0.0, 1.0, 60)

    fig = glp.figure(figsize=(9, 5), data_prefix="experiment_17")
    ax = fig.add_subplot(111)

    ax.plot(
        x, x, color="blue", linewidth=2, label="linear", data_name="Linear Reference"
    )
    ax.plot(
        x,
        x**2,
        color="red",
        linestyle="--",
        linewidth=2,
        label="quadratic",
        data_name="Quadratic Reference",
    )
    ax.fill_between(
        x,
        x**2 - 0.04,
        x**2 + 0.04,
        color="pink",
        alpha=0.25,
        label="uncertainty",
        data_name="Quadratic Uncertainty",
    )

    ax.set_xlabel("Normalized input")
    ax.set_ylabel("Response")
    ax.set_title("Custom Data Prefix and Data Names")
    ax.legend(loc="top left")

    fig.savefig("example_data_prefix.gle")
    print("  + Saved to example_data_prefix.gle")
    print("  + Sidecar .dat files use experiment_17_* or sanitized data_name labels.")


if __name__ == "__main__":
    example_data_prefix()

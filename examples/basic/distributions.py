"""Histogram, step, stem and rug examples."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_distributions():
    """Four ways to show samples and sequences. ``hist`` bins the samples with
    GLE's own ``let dK = hist dJ``; ``step`` draws GLE's ``steps``, ``fsteps``
    and ``hist`` line modes for matplotlib's ``where='post'``, ``'pre'`` and
    ``'mid'``; ``stem`` draws GLE's ``impulses``; and ``rug`` marks each value
    on the frame with GLE's ``rugs.gle``.
    """
    print("Creating example: Distributions...")

    rng = np.random.default_rng(3)
    fig, axes = glp.subplots(2, 2, figsize=(10, 8))

    # Histograms: a filled one and an outline over it.
    a = rng.normal(0.0, 1.0, 500)
    b = rng.normal(1.5, 0.6, 300)
    ax = axes[0, 0]
    ax.hist(
        a,
        bins=20,
        range=(-4, 4),
        histtype="stepfilled",
        color="lightsteelblue",
        label="A",
    )
    ax.hist(b, bins=20, range=(-4, 4), histtype="step", color="darkred", label="B")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Value")
    ax.set_ylabel("Count")
    ax.set_title("hist")
    ax.legend(loc="upper left")

    # Step plots: the same points with the step before, after or around each.
    x = np.arange(8)
    y = np.array([1, 3, 2, 4, 3, 5, 4, 6])
    ax = axes[0, 1]
    ax.step(x, y, where="pre", label="pre")
    ax.step(x, y + 3, where="post", label="post")
    ax.step(x, y + 6, where="mid", label="mid")
    ax.plot(x, y, "ko", markersize=3)
    ax.plot(x, y + 3, "ko", markersize=3)
    ax.plot(x, y + 6, "ko", markersize=3)
    ax.set_xlim(-0.5, 7.5)
    ax.set_ylim(0, 14)
    ax.set_xlabel("n")
    ax.set_title("step")
    ax.legend(loc="lower right")

    # Stem plot: a decaying, oscillating sequence.
    n = np.arange(0, 25)
    ax = axes[1, 0]
    ax.stem(n, np.exp(-n / 8) * np.cos(n / 2))
    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_xlim(-1, 25)
    ax.set_ylim(-0.6, 1.1)
    ax.set_xlabel("n")
    ax.set_title("stem")

    # Rugs: each sample marked on the bottom and left edges of the frame.
    xs = rng.normal(0, 1, 60)
    ys = 0.5 * xs + rng.normal(0, 0.5, 60)
    ax = axes[1, 1]
    ax.scatter(xs, ys, s=12, color="black")
    ax.rug(xs, axis="x", color="C0")
    ax.rug(ys, axis="y", color="C1")
    ax.set_xlim(-3, 3)
    ax.set_ylim(-2, 2)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("rug")

    fig.savefig("example_distributions.gle")
    print("  ✓ Saved to example_distributions.gle")


if __name__ == "__main__":
    example_distributions()

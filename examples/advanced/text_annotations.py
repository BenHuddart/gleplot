"""Text annotation examples for gleplot."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_text_annotations():
    """Text placement, alignment, and boxed labels."""
    print("Creating example: Text annotations...")

    x = np.linspace(0.0, 10.0, 200)
    y = np.sin(x)

    fig = glp.figure(figsize=(9, 6))
    ax = fig.add_subplot(111)

    ax.plot(x, y, color="blue", linewidth=2, label="Signal")

    # Mark peak and trough labels with different alignments.
    ax.text(
        1.57,
        1.0,
        "Peak",
        color="darkblue",
        fontsize=11,
        ha="center",
        va="bottom",
        rotation=45,
    )
    ax.text(4.71, -1.0, "Trough", color="darkred", fontsize=11, ha="center", va="top")

    # Add an annotation with a filled background.
    ax.text(
        7.5,
        0.6,
        "Window: 7.0 to 8.0 s",
        color="black",
        fontsize=10,
        ha="left",
        va="center",
        bbox={"facecolor": "white"},
    )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title("Text Annotation Patterns")
    ax.legend(loc="upper right")

    fig.savefig("example_text_annotations.gle")
    print("  + Saved to example_text_annotations.gle")


def example_figure_text_and_legend():
    """Text for the whole figure. ``fig.suptitle`` centres a title above every
    axes, ``fig.text`` places panel labels in figure fractions, and
    ``fig.legend`` writes one legend for the series of both axes. ``annotate``
    points an arrow at a feature in data coordinates.
    """
    print("Creating example: Figure text and legend...")

    fig, (ax1, ax2) = glp.subplots(1, 2, figsize=(10, 4.5))

    x = np.linspace(0, 4 * np.pi, 200)
    for ax, damping in ((ax1, 0.1), (ax2, 0.3)):
        # Label one axes only: fig.legend lists every labelled series.
        labels = ("position", "velocity", "rest") if ax is ax1 else ("", "", "")
        ax.plot(x, np.exp(-damping * x) * np.cos(x), label=labels[0])
        ax.plot(x, -np.exp(-damping * x) * np.sin(x), "--", label=labels[1])
        ax.axhline(0, color="gray", linewidth=0.5, label=labels[2])
        ax.set_xlim(0, 4 * np.pi)
        ax.set_ylim(-1.1, 1.1)
        ax.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.set_title("Light damping")
    ax2.set_title("Heavy damping")

    ax2.annotate(
        "settled",
        xy=(9.5, 0.0),
        xytext=(8.0, 0.7),
        arrowprops=dict(arrowstyle="->"),
    )

    fig.suptitle("Damped Oscillator")
    fig.text(0.01, 0.88, "(a)", ha="left", va="top")
    fig.text(0.49, 0.88, "(b)", ha="left", va="top")
    fig.legend(loc="lower center", ncol=3)
    # The figure legend sits at the bottom of the page: leave room for it.
    fig.subplots_adjust(bottom=0.25)

    fig.savefig("example_figure_text_legend.gle")
    print("  ✓ Saved to example_figure_text_legend.gle")


if __name__ == "__main__":
    example_text_annotations()
    example_figure_text_and_legend()

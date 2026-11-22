"""Reference lines and shaded spans example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_reference_lines_and_spans():
    """Guides drawn over a signal. ``axhline``/``axvline`` span the axes,
    ``hlines``/``vlines`` draw segments between data coordinates, and
    ``axhspan``/``axvspan`` shade a band; ``alpha`` below 1 makes a band
    see-through, which gleplot compiles with GLE's ``-cairo`` device.
    """
    print("Creating example: Reference lines and spans...")

    fig = glp.figure(figsize=(9, 6))
    ax = fig.add_subplot(111)

    t = np.linspace(0, 10, 400)
    signal = np.exp(-t / 4) * np.sin(2 * t) + 0.05 * t

    # Shaded bands go first, so the data is drawn over them.
    ax.axvspan(2.0, 3.5, color="gold", alpha=0.4, label="pulse on")
    ax.axhspan(-0.1, 0.1, color="lightgray", label="noise floor")

    ax.plot(t, signal, color="black", label="signal")

    # Lines across the whole axes.
    ax.axhline(0.5, color="C3", linestyle="--", label="threshold")
    ax.axvline(5.5, color="C2", linestyle=":", linewidth=1.5)

    # Segments with data-coordinate ends: drop lines from each peak.
    peaks_t = np.array([0.8, 4.0, 7.1])
    peaks_y = np.exp(-peaks_t / 4) * np.sin(2 * peaks_t) + 0.05 * peaks_t
    ax.vlines(peaks_t, -1.0, peaks_y, colors="C0", linestyles="dashed")
    ax.hlines(peaks_y, 0, peaks_t, colors="C0", linestyles="dotted")
    ax.plot(peaks_t, peaks_y, "o", color="C0", markersize=8, label="peaks")

    ax.set_xlim(0, 10)
    ax.set_ylim(-1.0, 1.6)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Response")
    ax.set_title("Reference Lines and Spans")
    ax.legend(loc="upper right")

    fig.savefig("example_reference_lines.gle")
    print("  ✓ Saved to example_reference_lines.gle")


if __name__ == "__main__":
    example_reference_lines_and_spans()

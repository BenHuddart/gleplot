"""Basic line plotting example."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_basic_line_plot():
    """Sine and cosine as two line series. Given no colour, they take C0 and C1 from
    the axes' colour cycle, as in matplotlib."""
    print("Creating example: Basic line plot...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Create data
    x = np.linspace(0, 2 * np.pi, 100)
    y_sin = np.sin(x)
    y_cos = np.cos(x)

    # Plot: no color given, so each line takes the next colour of the cycle
    ax.plot(x, y_sin, label="sin(x)", linestyle="-")
    ax.plot(x, y_cos, label="cos(x)", linestyle="--")

    # Labels and title
    ax.set_xlabel("x (radians)")
    ax.set_ylabel("y")
    ax.set_title("Sine and Cosine Functions")
    ax.legend()

    # Save
    fig.savefig("example_basic_line_plot.gle")
    print("  ✓ Saved to example_basic_line_plot.gle")


def example_format_strings_and_gaps():
    """matplotlib format strings such as ``'o-'``, ``'s--'`` and ``'k^:'`` set the
    marker, line style and colour in one argument. A NaN in the data breaks the
    line, as in matplotlib: GLE leaves a gap at a missing value.
    """
    print("Creating example: Format strings and NaN gaps...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.linspace(0, 10, 21)

    # Colour letter, marker and line style in one string; without a colour
    # letter the series takes the next colour of the cycle.
    ax.plot(x, np.sqrt(x), "o-", label="'o-'")
    ax.plot(x, 0.3 * x, "s--", label="'s--'")
    ax.plot(x, 3 - 0.2 * x, "k^:", label="'k^:'")

    # Two missing readings: the line stops at a NaN and starts again after it.
    y = 1 + 0.5 * np.sin(x)
    y[[8, 9]] = np.nan
    ax.plot(x, y, "rD-", label="NaN gap")

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_ylim(0, 4)
    ax.set_title("Format Strings and NaN Gaps")
    ax.legend(loc="upper left")

    fig.savefig("example_format_strings.gle")
    print("  ✓ Saved to example_format_strings.gle")


if __name__ == "__main__":
    example_basic_line_plot()
    example_format_strings_and_gaps()

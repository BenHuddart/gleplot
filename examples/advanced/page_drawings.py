"""Page drawings example: GLE shapes placed on the page beside a graph."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_page_drawings():
    """GLE's drawing commands, placed on the page in centimetres from its
    bottom-left corner, outside any axes: a sketch of the experiment beside
    its data. ``circle``, ``ellipse``, ``arc``, ``bezier`` and ``curve``
    write GLE's commands of those names, ``polygon`` a closed GLE path, and
    ``table`` lines up columns of text.
    """
    print("Creating example: Page drawings...")

    # 10 x 5 inches is 25.4 x 12.7 cm; the graph takes the left half.
    fig, ax = glp.subplots(figsize=(10, 5))
    fig.subplots_adjust(left=0.08, right=0.5)

    angle = np.linspace(0, 180, 91)
    ax.plot(angle, np.cos(np.radians(angle)) ** 2, color="C0")
    ax.set_xlim(0, 180)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Polariser angle (degrees)")
    ax.set_ylabel("Transmitted intensity")
    ax.set_title("Malus's law")

    # Drawings are written in the order they are added: the beam first, so
    # the parts on the optical axis (y = 8 cm) are drawn over it.
    fig.curve([15.5, 23.6], [8.0, 8.0], (1, 0), (1, 0), color="orange")
    fig.circle(15.0, 8.0, 0.5, fill="gold")
    fig.ellipse(18.0, 8.0, 0.6, 3.0, fill="lightblue", color="steelblue")
    fig.polygon([20.8, 21.4, 21.4, 20.8], [6.5, 6.5, 9.5, 9.5], fill="lightgray")
    fig.circle(24.0, 8.0, 0.4, fill="black")
    # An arc for the polariser's rotation, and a Bezier reference path.
    fig.arc(21.1, 8.0, 2.0, 60, 120, color="C3", linewidth=1.5)
    fig.bezier([24.0, 22.0, 17.0, 15.0], [7.6, 3.5, 3.5, 7.5], color="gray")

    fig.table(
        15.0,
        3.0,
        "part        position\nsource      15 cm\nlens        18 cm\n"
        "polariser   21 cm\ndetector    24 cm",
    )

    fig.savefig("example_page_drawings.gle")
    print("  ✓ Saved to example_page_drawings.gle")


if __name__ == "__main__":
    example_page_drawings()

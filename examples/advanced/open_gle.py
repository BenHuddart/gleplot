"""Reading a GLE script back with open_gle and adding to it."""

import sys
from pathlib import Path

import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_open_gle():
    """``open_gle`` reads a ``.gle`` script, here one written by hand, back
    into a ``Figure``. Its graph becomes an ``Axes`` that takes new series
    like any other, and ``savefig`` writes the script again with them added.
    GLE that gleplot does not model is kept as it was.
    """
    print("Creating example: open_gle...")

    # A hand-written GLE script: a curve GLE computes, and a dashed line.
    Path("example_handwritten.gle").write_text("""size 16 13
set hei 0.45
amove 1.5 1.2
begin graph
    size 14 10.5
    scale 1 1
    title "A hand-written GLE graph"
    xtitle "x"
    ytitle "y"
    xaxis min 0 max 10
    yaxis min -2 max 1.5
    let d1 = sin(x) from 0 to 10 step 0.05
    d1 line color blue lwidth 0.05 key "sin(x), from the script"
    let d2 = 0 from 0 to 10 step 10
    d2 line lstyle 2 color gray
    key pos tr
end graph
""")

    fig = glp.open_gle("example_handwritten.gle")
    ax = fig.axes[0]

    # New series are added to the recovered axes as to any other.
    rng = np.random.default_rng(2)
    x = np.linspace(0.5, 9.5, 19)
    y = np.sin(x) + rng.normal(0, 0.15, x.size)
    ax.errorbar(x, y, yerr=0.15, fmt="o", color="C3", label="data, added in Python")
    ax.legend(loc="lower left")

    fig.savefig("example_open_gle.gle")
    print("  ✓ Saved to example_open_gle.gle")


if __name__ == "__main__":
    example_open_gle()

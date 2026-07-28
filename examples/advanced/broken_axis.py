"""Broken (split) x-axis panels: three seam styles, one shared y-axis.

A broken axis is the right tool when one dataset carries structure on two
wildly different scales and a log axis is not appropriate -- for instance a
relaxation measurement whose first 20 ns hold a fast Gaussian decay while the
remaining 3 us hold a slow exponential tail. Plotting 0-3 us linearly buries
the fast part in the first 0.7% of the panel; splitting the axis into a
narrow 0-0.02 us segment and a wide 0.02-3 us one gives both features room
while keeping a single y-axis and a single frame.

The three figures produced here differ only in how the seam is marked:

* ``broken_axis_slash`` -- the conventional double-slash break marks, with a
  small physical gap between the segments (the default when
  ``divider='slash'``).
* ``broken_axis_line`` -- a single vertical rule at the join, no gap. Reads
  as one panel that happens to be ruled.
* ``broken_axis_none`` -- no marker at all; use when the caption or the tick
  labels already make the break obvious.

The third figure also shows a three-segment split with unequal widths, and
per-segment tick intervals -- necessary because GLE's automatic tick choice
is made per graph block, and a narrow segment's ticks would otherwise collide
with a wide neighbour's at the seam.

Outputs (next to this file): ``broken_axis_slash.{gle,pdf}``,
``broken_axis_line.{gle,pdf}``, ``broken_axis_none.{gle,pdf}``.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def _relaxation(t, fast_amp=14.0, fast_rate=90.0, slow_amp=10.0, slow_rate=1.1):
    """A two-timescale decay: fast Gaussian + slow exponential + baseline."""
    return (
        fast_amp * np.exp(-((fast_rate * t) ** 2))
        + slow_amp * np.exp(-slow_rate * t)
        + 2.0
    )


def _save(fig, stem):
    out_dir = Path(__file__).parent
    fig.savefig_gle(str(out_dir / f"{stem}.gle"))
    print(f"Saved: {out_dir / f'{stem}.gle'}")
    try:
        fig.savefig(str(out_dir / f"{stem}.pdf"))
        print(f"Compiled: {out_dir / f'{stem}.pdf'}")
    except RuntimeError:
        print("GLE not available for compilation. GLE script saved.")


def example_broken_axis_slash():
    """Two segments, double-slash break marks, filled and open markers."""
    print("Creating example: broken x-axis with double-slash break marks...")
    rng = np.random.default_rng(3)

    # Sample densely where the fast decay lives, sparsely in the tail.
    t = np.concatenate(
        [np.linspace(0.0004, 0.02, 26), np.linspace(0.05, 3.0, 45)]
    )
    warm = _relaxation(t) + rng.normal(0.0, 0.25, t.size)
    cold = _relaxation(t, fast_amp=18.0, slow_amp=6.0) + rng.normal(0.0, 0.25, t.size)

    fig = glp.figure(figsize=(5.2, 3.4), data_prefix="brokenslash")
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.17, top=0.95)

    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)],
        width_ratios=[1, 3],
        divider="slash",
    )
    bax.set_ylim(0.0, 30.0)

    # Filled vs open markers is the usual way to separate two conditions in
    # one panel; both are declared once and appear in both segments.
    bax.errorbar(
        t, cold, yerr=0.35, fmt="none", marker="o", markersize=4,
        color="blue", capsize=2, label="2 K",
    )
    bax.errorbar(
        t, warm, yerr=0.35, fmt="none", marker="s", markersize=4,
        color="red", capsize=2, fillstyle="none", label="50 K",
    )

    # A background-level guide spanning the whole panel, drawn under the data.
    bax.axhline(2.0, color="gray", linestyle="--", linewidth=0.8)

    bax.set_ylabel("Asymmetry (%)")
    bax.set_xlabel("t (\\mu s)")
    bax[0].set_xticks(dticks=0.01)
    bax[1].set_xticks(dticks=1.0)
    bax.legend(loc="upper right")

    _save(fig, "broken_axis_slash")
    return fig


def example_broken_axis_line():
    """Two segments meeting at a single vertical rule, plus a shaded window."""
    print("Creating example: broken x-axis with a single divider rule...")

    t = np.concatenate([np.linspace(0.0004, 0.02, 30), np.linspace(0.05, 3.0, 60)])
    a = _relaxation(t)

    fig = glp.figure(figsize=(5.2, 3.4), data_prefix="brokenline")
    # The shared title is drawn just above the frame, so leave room for it:
    # unlike GLE's own `title`, it does not reserve space of its own.
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.17, top=0.87)

    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)],
        width_ratios=[1, 3],
        divider="line",
        gap=0.0,
    )
    bax.set_ylim(0.0, 30.0)

    # A shaded fitting window: it lies wholly inside the wide segment, and
    # GLE clips it out of the narrow one automatically.
    bax.axvspan(0.3, 1.2, color="lightcyan", label=None)

    bax.plot(t, a, color="blue", linewidth=1.5)
    bax.plot(t, _relaxation(t, slow_amp=0.0), color="red", linestyle=":", linewidth=1.2)

    bax.set_ylabel("Asymmetry (%)")
    bax.set_xlabel("t (\\mu s)")
    bax.set_title("Single-rule divider")
    bax[0].set_xticks(dticks=0.01)
    bax[1].set_xticks(dticks=1.0)

    _save(fig, "broken_axis_line")
    return fig


def example_broken_axis_none():
    """Three unequal segments with no seam marker and per-segment ticks."""
    print("Creating example: three-segment broken x-axis, no divider...")

    x = np.linspace(0.0, 100.0, 500)
    y = 5.0 + 3.0 * np.sin(x / 3.0) * np.exp(-x / 60.0)

    fig = glp.figure(figsize=(6.0, 2.8), data_prefix="brokennone")
    fig.subplots_adjust(left=0.11, right=0.97, bottom=0.22, top=0.92)

    bax = fig.add_broken_xaxes(
        [(0.0, 5.0), (5.0, 40.0), (40.0, 100.0)],
        width_ratios=[1, 2, 3],
        divider="none",
    )
    bax.set_ylim(0.0, 10.0)
    bax.plot(x, y, color="red", linewidth=1.5)

    bax.set_ylabel("Signal (a.u.)")
    bax.set_xlabel("x")
    # One tick interval per segment, in left-to-right order.
    bax.set_xticks(dticks=[2.0, 10.0, 20.0])

    _save(fig, "broken_axis_none")
    return fig


def main():
    example_broken_axis_slash()
    example_broken_axis_line()
    example_broken_axis_none()
    print("\nAll broken-axis examples created successfully!")


if __name__ == "__main__":
    main()

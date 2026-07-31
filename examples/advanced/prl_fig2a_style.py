"""PRL-style muon asymmetry panel with a broken time axis.

Reproduces the layout of Gomilsek et al., PRL 134, 046702 Fig. 2(a): a single
panel whose linear time axis is broken into a narrow 0-0.02 us segment and a
wide 0.02-3 us one (width ratio 1:3), sharing one y-axis. The data are
synthetic zero-field muon spin relaxation spectra at three temperatures, each
the sum of

    A(t) = A_fast * exp(-(sigma t)^2 / 2) + A_slow * exp(-lambda t) + A_bg

-- a fast Gaussian component from static nuclear/electronic moments (1/sigma
~ 0.01 us, entirely inside the narrow segment) plus a slow exponential from
dynamic fluctuations (1/lambda ~ 1 us, only resolvable across the wide one).
A single linear axis over 0-3 us would compress the whole Gaussian into the
first 0.7 % of the panel; that is what the break exists to fix.

Conventions on show, all of them things the target figure relies on:

* filled vs open markers to separate the three temperatures at a glance
  (``fillstyle='none'`` and ``markerfacecolor='white'``);
* dashed fit curves drawn over the points, from the model without noise;
* a dotted horizontal line at the instrumental background asymmetry, spanning
  both segments;
* per-segment tick intervals -- GLE chooses ticks per graph block, so the
  narrow segment needs its own spacing or its labels collide with the wide
  segment's at the seam;
* double-slash break marks on the top and bottom frame lines.

Outputs (next to this file): ``prl_fig2a_style.gle`` + sidecars and
``prl_fig2a_style.pdf``.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp
from gleplot import GLEStyleConfig


# Instrumental background asymmetry (%): the level the relaxation decays to.
A_BG = 2.4

#: (label, colour, marker, fill, fast amplitude, sigma, slow amplitude, lambda)
#: sigma is in us^-1, lambda in us^-1.
TEMPERATURES = [
    ("2 K", "blue", "o", "full", 13.0, 120.0, 9.5, 0.55),
    ("18 K", "red", "s", "none", 9.0, 105.0, 12.5, 1.05),
    ("60 K", "black", "^", "white", 4.5, 85.0, 15.0, 2.10),
]


def asymmetry(t, a_fast, sigma, a_slow, lam):
    """Two-timescale zero-field relaxation function (see module docstring)."""
    return (
        a_fast * np.exp(-((sigma * t) ** 2) / 2.0)
        + a_slow * np.exp(-lam * t)
        + A_BG
    )


def sample_times():
    """Measurement times: dense inside the fast decay, sparse in the tail.

    Real muSR data are binned uniformly in time; here the two segments are
    sampled at the densities each one can actually show, which keeps the
    marker count reasonable at print size.
    """
    fast = np.linspace(0.0005, 0.0195, 22)
    slow = np.linspace(0.045, 2.97, 42)
    return np.concatenate([fast, slow])


def example_prl_fig2a_style():
    """Build, save and compile the PRL Fig. 2(a)-style panel."""
    rng = np.random.default_rng(20260728)
    t = sample_times()
    # Fit curves are drawn from a dense grid so the dashes stay smooth across
    # both segments, independent of where the points happen to sit. np.unique
    # both sorts and drops the duplicated 0.02 knot where the two grids meet:
    # gleplot draws lines with GLE's `smooth` by default, and a repeated x
    # makes that spline blow up into a spike at the seam.
    t_model = np.unique(
        np.concatenate([np.linspace(0.0, 0.02, 60), np.linspace(0.02, 3.0, 160)])
    )

    # Only typography here: the line-style numbers come from the library
    # defaults, which map '--' and ':' onto the GLE styles that really render
    # dashed and dotted.
    style = GLEStyleConfig(fontsize=11, default_linewidth=1.1)

    # Single-column PRL panel: 3.4 in wide is the journal's column width.
    fig = glp.figure(figsize=(3.4, 2.7), dpi=300, style=style, data_prefix="prlfig2a")
    fig.subplots_adjust(left=0.17, right=0.98, bottom=0.19, top=0.96)

    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)],
        width_ratios=[1, 3],
        divider="slash",
        break_mark_size=0.17,
        # A little wider than the default so the marks clear the narrow
        # segment's last tick label ("0.02") on the bottom frame line.
        gap=0.22,
    )
    bax.set_ylim(0.0, 28.0)

    # Background level first, so every marker and fit line sits on top of it.
    bax.axhline(A_BG, color="gray", linestyle=":", linewidth=0.9)

    for label, color, marker, fill, a_fast, sigma, a_slow, lam in TEMPERATURES:
        clean = asymmetry(t, a_fast, sigma, a_slow, lam)
        err = np.full_like(t, 0.32)
        noisy = clean + rng.normal(0.0, err)

        # 'full' -> solid marker; 'none' -> transparent outline;
        # 'white' -> outline with an opaque white interior.
        face = {"full": None, "none": "none", "white": "white"}[fill]

        bax.errorbar(
            t,
            noisy,
            yerr=err,
            fmt="none",
            marker=marker,
            markersize=3.6,
            color=color,
            capsize=1.6,
            markerfacecolor=face,
            label=label,
        )
        bax.plot(
            t_model,
            asymmetry(t_model, a_fast, sigma, a_slow, lam),
            color=color,
            linestyle="--",
            linewidth=1.0,
        )

    bax.set_ylabel("Asymmetry (%)")
    bax.set_xlabel("t (\\mu s)")
    bax.set_yticks(dticks=5.0)
    # The narrow segment spans 0.02 us and the wide one 2.98: one tick
    # interval could not serve both.
    bax[0].set_xticks(dticks=0.01)
    bax[1].set_xticks(dticks=1.0)
    bax.legend(loc="upper right")

    out_dir = Path(__file__).parent
    fig.savefig_gle(str(out_dir / "prl_fig2a_style.gle"))
    print(f"Saved: {out_dir / 'prl_fig2a_style.gle'}")
    try:
        fig.savefig(str(out_dir / "prl_fig2a_style.pdf"))
        print(f"Compiled: {out_dir / 'prl_fig2a_style.pdf'}")
    except RuntimeError:
        print("GLE not available for compilation. GLE script saved.")
    return fig


def main():
    example_prl_fig2a_style()


if __name__ == "__main__":
    main()

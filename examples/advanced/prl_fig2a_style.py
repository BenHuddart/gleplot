"""PRL-style muon asymmetry panel on a logarithmic time axis.

After the layout of Gomilsek et al., PRL 134, 046702 Fig. 2(a). The data are
synthetic zero-field muon spin relaxation spectra at three temperatures, each
the sum of

    A(t) = A_fast * exp(-(sigma t)^2 / 2) + A_slow * exp(-lambda t) + A_bg

-- a fast Gaussian component from static nuclear/electronic moments (1/sigma
~ 0.01 us) plus a slow exponential from dynamic fluctuations (1/lambda ~ 1 us).
A linear axis over 0-3 us would compress the whole Gaussian into the first
0.7 % of the panel; a logarithmic one shows both timescales.

Conventions on show, all of them things the target figure relies on:

* filled vs open markers to separate the three temperatures at a glance
  (``fillstyle='none'`` and ``markerfacecolor='white'``);
* dashed fit curves drawn over the points, from the model without noise;
* a dotted horizontal line at the instrumental background asymmetry.

Outputs (in the current directory): ``prl_fig2a_style.gle`` + sidecars.
"""

import sys
from pathlib import Path

import numpy as np

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
    return a_fast * np.exp(-((sigma * t) ** 2) / 2.0) + a_slow * np.exp(-lam * t) + A_BG


def example_prl_fig2a_style():
    """A journal-style single panel on a logarithmic time axis, with fit
    curves over the data and a background line.
    """
    rng = np.random.default_rng(20260728)
    # Real muSR data are binned uniformly in time; logarithmic sampling keeps
    # the marker count reasonable at print size.
    t = np.geomspace(0.001, 3.0, 40)
    t_model = np.geomspace(0.001, 3.0, 200)

    # Only typography here: the line-style numbers come from the library
    # defaults, which map '--' and ':' onto the GLE styles that really render
    # dashed and dotted.
    style = GLEStyleConfig(fontsize=11, default_linewidth=1.1)

    # Single-column PRL panel: 3.4 in wide is the journal's column width.
    fig = glp.figure(figsize=(3.4, 2.7), dpi=300, style=style, data_prefix="prlfig2a")
    fig.subplots_adjust(left=0.17, right=0.98, bottom=0.19, top=0.96)
    ax = fig.add_subplot(111)
    ax.set_xscale("log")
    ax.set_xlim(0.001, 3.0)
    ax.set_ylim(0.0, 28.0)

    # Background level first, so every marker and fit line sits on top of it.
    ax.axhline(A_BG, color="gray", linestyle=":", linewidth=0.9)

    for label, color, marker, fill, a_fast, sigma, a_slow, lam in TEMPERATURES:
        clean = asymmetry(t, a_fast, sigma, a_slow, lam)
        err = np.full_like(t, 0.32)
        noisy = clean + rng.normal(0.0, err)

        # 'full' -> solid marker; 'none' -> transparent outline;
        # 'white' -> outline with an opaque white interior.
        face = {"full": None, "none": "none", "white": "white"}[fill]

        ax.errorbar(
            t,
            noisy,
            yerr=err,
            linestyle="none",
            marker=marker,
            markersize=3.6,
            color=color,
            capsize=1.6,
            markerfacecolor=face,
            label=label,
        )
        ax.plot(
            t_model,
            asymmetry(t_model, a_fast, sigma, a_slow, lam),
            color=color,
            linestyle="--",
            linewidth=1.0,
        )

    ax.set_ylabel("Asymmetry (%)")
    ax.set_xlabel("t (\\mu s)")
    ax.set_yticks(dticks=5.0)
    ax.legend(loc="upper right")

    fig.savefig_gle("prl_fig2a_style.gle")
    print("Saved: prl_fig2a_style.gle")
    return fig


def main():
    example_prl_fig2a_style()


if __name__ == "__main__":
    main()

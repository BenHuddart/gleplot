"""Antiferromagnet H-T phase diagram from synthetic susceptibility data.

Demonstrates the scattered-data heatmap/contour path (``tripcolor`` +
``tricontour``): magnetic susceptibility measurements are simulated at
scattered (temperature, field) points -- as a real experiment would collect
them, sweeping temperature at a handful of fixed applied fields -- rather
than on a perfect grid. gleplot writes the raw ``(x, y, z)`` triples to a
sidecar file and lets GLE's own ``fitz`` (Akima interpolation) grid them at
compile time.

The susceptibility chi(T, H) is modelled as a broad ridge that peaks along
the Neel transition line:

    T_N(H) = T_N0 * sqrt(1 - (H / Hc)^2)

(critical-field suppression of the ordering temperature), broadening as H
approaches the critical field Hc. A ``tricontour`` near the ridge's
half-height traces the transition boundary directly on top of the
``tripcolor`` heatmap.

The phase diagram itself is a single axes with a colorbar; the second panel
(susceptibility line cuts at representative fields) is a genuine companion
that shows the peak shifting to lower T and broadening as H -> Hc.

``vmax`` is set just above the physical peak (chi0 + amplitude ~ 1.05). GLE's
Akima gridding can overshoot the data range near a sharp ridge from
scattered/noisy samples, but gleplot's generated palette subroutines clamp
the normalized value into [0, 1], so any overshoot saturates at the palette's
brightest colour rather than producing stray speckles -- a tight ``vmax`` is
safe. (Setting ``vmax`` explicitly is still worthwhile: with ``vmax=None`` a
single overshoot node would auto-scale the whole colour range off the real
data.) Greek and math in labels use GLE's TeX-like markup directly, e.g.
``\\chi`` for the susceptibility symbol.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_phase_diagram():
    """Example: susceptibility phase diagram (tripcolor + tricontour + colorbar)."""
    print("Creating example: Antiferromagnet phase diagram...")

    rng = np.random.default_rng(11)

    T_N0 = 30.0  # zero-field Neel temperature (K)
    Hc = 9.5  # critical field (T)
    chi0 = 0.05  # paramagnetic background susceptibility (emu/mol)
    amplitude = 1.0  # peak height above background at the transition

    n_points = 3200
    H = rng.uniform(0.0, 0.92 * Hc, n_points)
    T = rng.uniform(1.5, 1.15 * T_N0, n_points)

    T_N = T_N0 * np.sqrt(1.0 - (H / Hc) ** 2)
    width = 2.0 + 1.4 * (H / Hc)  # critical broadening near Hc
    chi = chi0 + amplitude * np.exp(-((T - T_N) ** 2) / (2.0 * width**2))
    chi += rng.normal(0.0, 0.015 * amplitude, n_points)  # measurement noise

    fig, axes = glp.subplots(1, 2, figsize=(13, 6))
    fig.subplots_adjust(wspace=0.35)

    ax = axes[0]
    # Scattered-data heatmap: gridded at GLE compile time via `begin fitz`.
    # vmax sits just above the physical peak (chi0 + amplitude); the palette
    # subs clamp overshoot, so this stays speckle-free (see module docstring).
    ax.tripcolor(
        T,
        H,
        chi,
        gridsize=(90, 70),
        cmap="magma",
        vmin=0.0,
        vmax=chi0 + 1.15 * amplitude,
    )

    # Trace the transition boundary near the susceptibility ridge's
    # half-height, with inline value labels.
    boundary_level = chi0 + 0.55 * amplitude
    ax.tricontour(
        T,
        H,
        chi,
        gridsize=(90, 70),
        levels=[boundary_level],
        colors="black",
        linewidths=1.3,
        clabel=True,
        clabel_fmt="fix 2",
    )

    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Magnetic field (T)")
    ax.set_title("Antiferromagnet Phase Diagram (synthetic data)")

    # Greek chi via GLE's TeX-like markup. The '{}' after \chi is required:
    # GLE (like TeX) swallows the space right after a macro name, so
    # r'\chi (emu ...)' would render as "chi(emu ...)" with no gap.
    fig.colorbar(label=r"\chi{} (emu mol^{-1})", format="fix 2")

    # Companion panel: susceptibility line cuts at representative fields,
    # showing the peak shifting to lower T and broadening as H -> Hc.
    ax2 = axes[1]
    T_line = np.linspace(1.5, 1.15 * T_N0, 200)
    for H_val, color in ((0.0, "blue"), (5.0, "green"), (8.0, "red")):
        T_N_line = T_N0 * np.sqrt(1.0 - (H_val / Hc) ** 2)
        width_line = 2.0 + 1.4 * (H_val / Hc)
        chi_line = chi0 + amplitude * np.exp(
            -((T_line - T_N_line) ** 2) / (2.0 * width_line**2)
        )
        ax2.plot(T_line, chi_line, color=color, linewidth=2, label=f"H = {H_val:.0f} T")

    ax2.set_xlabel("Temperature (K)")
    # Same label as the colorbar above, but written as matplotlib-style
    # mathtext instead of GLE markup -- gleplot translates $...$ segments to
    # GLE markup at store time (here to r'\chi{} (emu mol^{-1})'), so both
    # styles render identically. Text outside the $...$ passes through.
    ax2.set_ylabel(r"$\chi$ (emu mol$^{-1}$)")
    ax2.set_title("Susceptibility line cuts")
    ax2.set_ylim(0, 1.2)
    ax2.legend()

    # Save the GLE script + its points sidecars next to this script (the
    # tracked-example convention: the .gle and its input sidecars live beside
    # the .py). PDF/PNG and GLE's own -cdata/-clabels/-cvalues derivatives are
    # build products (gitignored), so compilation is optional.
    output_dir = Path(__file__).parent
    gle_file = output_dir / "example_phase_diagram.gle"
    fig.savefig_gle(str(gle_file))
    print(f"  Saved to {gle_file}")

    try:
        png_file = output_dir / "example_phase_diagram.png"
        fig.savefig(str(png_file), dpi=150)
        print(f"  Compiled to {png_file}")
    except RuntimeError:
        print("  GLE not available for compilation; GLE script saved only.")


if __name__ == "__main__":
    example_phase_diagram()

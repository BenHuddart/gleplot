"""End-to-end compilation of the PRL-style figure primitives with real GLE.

Unit tests assert what gleplot *emits*; these assert that GLE *accepts* it.
That distinction matters here because every one of these features leans on
GLE syntax that fails loudly at compile time when it is wrong: ``dticks``,
the outline marker names (GLE rejects an unknown marker outright), and the
guides. Skipped when GLE is not installed.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


T = np.concatenate([np.linspace(0.0005, 0.0195, 20), np.linspace(0.05, 3.0, 30)])


def _asymmetry(t):
    return 14.0 * np.exp(-((90.0 * t) ** 2)) + 10.0 * np.exp(-1.1 * t) + 2.0


@pytest.mark.parametrize(
    "index,marker",
    list(enumerate(["o", "s", "^", "v", "D", "*", "+", "x", ".", "<", "p", "h", "H"])),
)
@pytest.mark.parametrize("fill", [None, "none", "white"])
def test_every_marker_and_fill_combination_is_a_name_gle_accepts(
    tmp_path, index, marker, fill
):
    """GLE rejects an unknown marker name outright, so this is a real check."""
    # The prefix is built from the index, not the marker symbol: '+' and '*'
    # are not valid characters in an unquoted GLE `data` filename.
    fig = glp.figure(figsize=(3, 3), data_prefix=f"mk{index}{fill or 'solid'}")
    ax = fig.add_subplot(111)
    ax.plot(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 1.5],
        linestyle="none",
        marker=marker,
        markerfacecolor=fill,
    )
    out = fig.savefig(str(tmp_path / "mk.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_reference_lines_and_spans_compile(tmp_path):
    x = np.linspace(0.0, 10.0, 60)
    fig = glp.figure(figsize=(6, 4), data_prefix="guides")
    ax = fig.add_subplot(111)
    ax.plot(x, np.sin(x), color="blue")
    ax.set_ylim(-1.5, 1.5)
    ax.axhline(0.0, color="gray", linestyle=":")
    ax.axvline(3.14159, color="red", linestyle="--", label="pi")
    ax.axvspan(6.0, 8.0, color="lightgray")
    ax.axhspan(-0.25, 0.25, xmin=0.0, xmax=0.4, color="lightcyan")

    out = fig.savefig(str(tmp_path / "guides.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_prl_fig2a_style_panel_compiles(tmp_path):
    """The acceptance figure: log time axis + open markers + guides + fits."""
    rng = np.random.default_rng(1)
    t_model = np.geomspace(0.0005, 3.0, 120)

    fig = glp.figure(figsize=(3.4, 2.7), dpi=300, data_prefix="prl")
    fig.subplots_adjust(left=0.17, right=0.98, bottom=0.19, top=0.96)
    ax = fig.add_subplot(111)
    ax.set_xscale("log")
    ax.set_ylim(0.0, 28.0)
    ax.axhline(2.4, color="gray", linestyle=":")

    for color, marker, face, scale in (
        ("blue", "o", None, 1.0),
        ("red", "s", "none", 0.8),
        ("black", "^", "white", 0.6),
    ):
        model = scale * _asymmetry(t_model) + 2.0
        ax.errorbar(
            T,
            scale * _asymmetry(T) + 2.0 + rng.normal(0, 0.3, T.size),
            yerr=0.3,
            linestyle="none",
            marker=marker,
            markersize=3.6,
            color=color,
            capsize=1.6,
            markerfacecolor=face,
            label=f"{color}",
        )
        ax.plot(t_model, model, color=color, linestyle="--", linewidth=1.0)

    ax.set_ylabel("Asymmetry (%)")
    ax.set_xlabel("t (\\mu s)")
    ax.legend(loc="upper right")

    out = fig.savefig(str(tmp_path / "prl.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_coloured_text_ending_a_panel_compiles_and_does_not_leak(tmp_path):
    """Real-GLE compile check for the 2026-07-29 colour-state-leak fix.

    ``tests/unit/test_text.py``'s ``TestColorStateDoesNotLeakAcrossPanels``
    pins the emitted GLE text; this confirms real GLE actually accepts the
    gsave/grestore-wrapped output (a syntax GLE could in principle reject)
    and produces a non-empty PDF.
    """
    fig, axes = glp.subplots(2, 1, sharex=True, figsize=(3.4, 4.0), data_prefix="leak")
    axes[0].plot([0, 1, 2], [0, 1, 2], color="blue")
    axes[0].text(1, 1, "PM", color="green", ha="center")
    axes[1].plot([0, 1, 2], [0, 2, 1], color="blue")
    axes[1].set_xlabel("t (\\mu s)")

    out = fig.savefig(str(tmp_path / "colour_leak.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_height_ratios_five_row_stack_compiles(tmp_path):
    """Real-GLE compile check for ``height_ratios``: the PRL LF/J(omega)
    figure shape this was built for -- 3 flush lambda panels, a SHORT
    separator row for tick labels, and a 4th panel.
    """
    fig, axes = glp.subplots(
        5,
        1,
        sharex=True,
        figsize=(3.386, 5.5),
        data_prefix="hratio",
        height_ratios=[3, 3, 3, 1, 4],
    )
    for i, ax in enumerate(axes[:3]):
        ax.plot(T, _asymmetry(T) * (i + 1) / 3.0, color="blue")
        ax.set_ylabel(f"\\lambda_{i} (\\mu s^{{-1}})")
    # The short separator row (index 3) intentionally carries no series --
    # it exists purely so the shared x tick labels have somewhere to sit
    # without stealing height from a real panel.
    axes[3].set_ylim(0.0, 1.0)
    axes[4].plot(T, np.cos(T * 5.0), color="red")
    axes[4].set_ylabel("J(\\omega)")
    axes[4].set_xlabel("t (\\mu s)")

    out = fig.savefig(str(tmp_path / "height_ratios_5row.pdf"))
    assert out.exists() and out.stat().st_size > 0

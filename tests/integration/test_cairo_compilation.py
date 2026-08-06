"""Real-GLE compile tests for Track G6 (Cairo device auto-enable).

Skipped when GLE is not installed, matching the rest of this package's
convention (see e.g. ``tests/integration/test_inverted_axis_compiles.py``).
Everything that doesn't need a real ``gle`` binary lives in
``tests/unit/test_cairo_support.py`` instead.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_alpha_fill_compiles_via_auto_cairo(tmp_path):
    """A fill_between(alpha<1) figure compiles to PDF with no extra caller
    effort: Figure.savefig() auto-detects the need for -cairo."""
    fig = glp.figure(data_prefix="g6")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), np.sqrt(x), color="lightblue", alpha=0.5)
    ax.plot(x, np.sqrt(x), color="blue")

    out = fig.savefig(str(tmp_path / "alpha_fill.pdf"))

    assert out.exists()
    assert out.stat().st_size > 0


def test_alpha_fill_compiles_to_png_via_auto_cairo(tmp_path):
    """The default preview device (PNG, SPEC §6.1) also needs -cairo for an
    alpha fill -- this is the case that would previously hard-fail every
    live-preview render of such a figure (semi-transparency error) once
    alpha started actually reaching the emitted colour."""
    fig = glp.figure(data_prefix="g6")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), np.sqrt(x), color="lightblue", alpha=0.5)

    out = fig.savefig(str(tmp_path / "alpha_fill.png"))

    assert out.exists()
    assert out.stat().st_size > 0


def test_axvspan_alpha_compiles_via_auto_cairo(tmp_path):
    fig = glp.figure(data_prefix="g6")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2, 3], [0, 1, 0.5, 2])
    ax.axvspan(1, 2, alpha=0.3, color="orange")

    out = fig.savefig(str(tmp_path / "span.pdf"))

    assert out.exists()
    assert out.stat().st_size > 0


def test_raw_rgba_color_compiles_via_auto_cairo(tmp_path):
    """A user-supplied rgba(...) colour on an ordinary series, not just
    fill_between's alpha, also triggers (and needs) auto-Cairo."""
    fig = glp.figure(data_prefix="g6")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2, 3], [0, 1, 0.5, 2], color="rgba255(200,30,30,120)")

    out = fig.savefig(str(tmp_path / "rgba_line.pdf"))

    assert out.exists()
    assert out.stat().st_size > 0


def test_opaque_figure_compiles_without_requesting_cairo(tmp_path):
    """Sanity/anti-regression: an ordinary figure with no transparency
    compiles fine with requires_cairo() False, i.e. without -cairo -- the
    behaviour every pre-G6 user relies on stays exactly as it was."""
    fig = glp.figure(data_prefix="g6")
    ax = fig.add_subplot(111)
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 2, 1], color="lightblue")
    ax.plot([0, 1, 2], [1, 2, 1], color="blue")

    assert fig.requires_cairo() is False

    out = fig.savefig(str(tmp_path / "opaque.pdf"))

    assert out.exists()
    assert out.stat().st_size > 0


def test_alpha_fill_gle_text_identical_regardless_of_cairo_flag(tmp_path):
    """The -cairo decision is compile-time only: the written .gle text for
    an alpha figure must be identical whether or not a compile (let alone
    Cairo) ever happens. Compiling fig_b with cairo=False would fail outright
    (GLE requires -cairo for its rgba255 colour) -- exactly why that decision
    must never leak into script generation -- so fig_b only writes its
    script (savefig_gle never compiles) rather than attempting that compile.
    """
    x = np.linspace(0, 5, 6)

    fig_a = glp.figure(data_prefix="g6")
    ax_a = fig_a.add_subplot(111)
    ax_a.fill_between(x, np.zeros_like(x), x, color="lightblue", alpha=0.4)
    fig_a.savefig(str(tmp_path / "a.pdf"), cairo=True)

    fig_b = glp.figure(data_prefix="g6")
    ax_b = fig_b.add_subplot(111)
    ax_b.fill_between(x, np.zeros_like(x), x, color="lightblue", alpha=0.4)
    fig_b.savefig_gle(str(tmp_path / "b.gle"))

    assert (tmp_path / "a.gle").read_text() == (tmp_path / "b.gle").read_text()
    assert (tmp_path / "a.pdf").exists()
    assert (tmp_path / "a.pdf").stat().st_size > 0

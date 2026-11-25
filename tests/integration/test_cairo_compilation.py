"""Real-GLE compile tests for Track G6 (Cairo device auto-enable).

Skipped when GLE is not installed, matching the rest of this package's
convention (see e.g. ``tests/integration/test_inverted_axis_compiles.py``).
Everything that doesn't need a real ``gle`` binary lives in
``tests/unit/test_cairo_support.py`` instead.
"""

from __future__ import annotations

import re
import warnings
from unittest import mock

import numpy as np
import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


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


def test_svg_draws_text_in_the_default_font(tmp_path):
    """GLE leaves PostScript-font text out of an SVG compiled without
    ``-cairo`` (#280); its glyphs are paths, so the title adds paths."""

    def paths(title, name):
        fig = glp.figure(data_prefix=name)
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1])
        ax.set_title(title)
        with pytest.warns(UserWarning, match="SVG output is drawn"):
            out = fig.savefig(str(tmp_path / f"{name}.svg"))
        return out.read_text(encoding="utf-8").count("<path")

    assert paths("A title in the default font", "titled") > paths("", "plain")


# --------------------------------------------------------------------------- #
# GLEStyleConfig(opaque_backdrop=...): native output, GLE's default font
# --------------------------------------------------------------------------- #

#: EPS colour operands of the inks below, as GLE writes them.
_RED_BAND = "1 0.498039 0.498039 setrgbcolor"  # 50% red over white
_BLUE_BAND = "0.498039 0.498039 1 setrgbcolor"  # 50% blue over white
_GREEN_SPAN = "0.701961 0.85098 0.701961 setrgbcolor"  # 30% green over white
_LINE = "0.0705882 0.203922 0.337255 setrgbcolor"  # #123456
_POINTS = "0.396078 0.262745 0.129412 setrgbcolor"  # #654321


def _opaque_figure(tmp_path, bands, log=False):
    """Bands, a span across the observations, file-backed points with error
    bars, a line on a twin axis and a label GLE's Cairo font misdraws."""
    (tmp_path / "obs.dat").write_text("1 2 0.3\n2 3 0.3\n3 2.5 0.3\n4 3.5 0.3\n")
    fig = glp.figure(
        style=glp.GLEStyleConfig(opaque_backdrop="white"), data_prefix="opaque"
    )
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 11)
    for color in bands:
        ax.fill_between(x, x * 0 + 1, x * 0 + 4, color=color, alpha=0.5, label=color)
    ax.axvspan(1.5, 2.5, color="green", alpha=0.3, label="phase")
    ax.errorbar_from_file("obs.dat", 1, 2, 3, color="#654321", label="obs")
    ax.set_xlim(0, 5)
    ax.set_ylim(0.5, 5)
    if log:
        ax.set_yscale("log")
    twin = ax.twinx()
    twin.plot(x, x**2 + 1, color="#123456", label="fit")
    twin.set_ylim(1, 30)
    ax.set_xlabel("|F| a_b <x>")
    ax.legend()
    return fig


def _save(fig, path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with mock.patch.object(
            fig.compiler, "compile", wraps=fig.compiler.compile
        ) as compile_:
            out = fig.savefig(str(path))
    assert compile_.call_args.kwargs["cairo"] is False
    return out


@pytest.mark.parametrize(
    "bands", [("red", "blue"), ("blue", "red")], ids=["red-first", "blue-first"]
)
@pytest.mark.parametrize("log", [False, True], ids=["linear", "log"])
def test_opaque_backdrop_compiles_natively(tmp_path, bands, log):
    """No -cairo: the span and the bands are drawn first, in their opaque
    colours, and every observation after them."""
    fig = _opaque_figure(tmp_path, bands, log)
    assert fig.requires_cairo() is False
    eps = _save(fig, tmp_path / "opaque.eps").read_text(encoding="latin-1")
    inks = {"red": _RED_BAND, "blue": _BLUE_BAND}
    # The span, then the bands in call order, then the observations.
    first = [eps.index(_GREEN_SPAN)] + [eps.index(inks[b]) for b in bands]
    assert first == sorted(first)
    assert max(first) < eps.index(_POINTS) and max(first) < eps.index(_LINE)
    assert "rgba" not in (tmp_path / "opaque.gle").read_text()
    pdf = _save(fig, tmp_path / "opaque.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")


def test_opaque_backdrop_keeps_the_default_font(tmp_path):
    """The label is drawn in GLE's default PostScript font, bars and all,
    where the Cairo device's texcmr draws '|' as another glyph."""
    fig = _opaque_figure(tmp_path, ("red",))
    eps = _save(fig, tmp_path / "font.eps").read_text(encoding="latin-1")
    assert "/Times-Roman f" in eps
    assert "texcmr" not in eps.lower()
    glyphs = re.findall(r"^\((.*)\) s$", eps, re.MULTILINE)
    label = ["\\174", "F", "\\174", " ", "a", "\\137", "b", " ", "\\74", "x", "\\76"]
    text = "".join(glyphs)
    assert "".join(g for g in label if g != " ") in text

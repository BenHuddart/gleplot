"""Tests for Track G6: Cairo device auto-enable for alpha/rgba figures.

Covers, at the unit level (no real GLE binary needed -- see
``tests/integration/test_cairo_compilation.py`` for the ``gle``-marked
end-to-end compile):

* ``gleplot.colors.apply_alpha`` -- the colour/alpha composition.
* ``gleplot.cairo_support`` -- the font-safety table and the
  ``requires_cairo`` predicate.
* ``Figure.requires_cairo`` -- the model-level predicate, across every place
  alpha/rgba can appear (``fill_between``, ``axvspan``/``axhspan``, a raw
  ``rgba(...)``/``rgba255(...)`` colour on any series).
* ``Figure.savefig`` -- auto vs. forced ``cairo``, and the font-substitution
  warning, via a mocked compiler (so no real GLE is needed here either).

Byte-stability for existing (no-alpha) users -- SPEC's explicit acceptance
bar for this track -- is covered from two angles: the default-alpha
regression (a plain ``fill_between``/``axvspan``/``axhspan`` call must not
start requiring Cairo just because this feature now exists) and the
compile-flag side (``build_compile_args``'s own defaulting is covered in
``tests/unit/test_compiler.py``).
"""

from __future__ import annotations

import warnings
from unittest import mock

import numpy as np
import pytest

import gleplot as glp
from gleplot.cairo_support import (
    CAIRO_SAFE_FONT,
    cairo_font_warning,
    figure_requires_cairo,
    is_cairo_safe_font,
)
from gleplot.colors import apply_alpha
from gleplot.config import GLEStyleConfig


@pytest.fixture(autouse=True)
def _reset():
    glp.close()
    yield
    glp.close()


# --------------------------------------------------------------------------- #
# gleplot.colors.apply_alpha
# --------------------------------------------------------------------------- #


class TestApplyAlpha:
    def test_alpha_none_returns_color_unchanged(self):
        assert apply_alpha("LIGHTBLUE", None) == "LIGHTBLUE"

    def test_alpha_at_least_one_returns_color_unchanged(self):
        # Exactly the byte-stability guarantee: an opaque fill's colour is
        # never rewritten, regardless of alpha's precise value at/above 1.
        assert apply_alpha("LIGHTBLUE", 1.0) == "LIGHTBLUE"
        assert apply_alpha("rgb255(10,20,30)", 2.5) == "rgb255(10,20,30)"

    def test_named_color_below_one_composes_rgba255(self):
        # LIGHTBLUE = (173, 216, 230); 0.5 * 255 = 127.5 -> rounds to 128.
        assert apply_alpha("LIGHTBLUE", 0.5) == "rgba255(173,216,230,128)"

    def test_rgb255_expr_below_one_composes_rgba255(self):
        assert apply_alpha("rgb255(10,20,30)", 0.4) == "rgba255(10,20,30,102)"

    def test_alpha_zero_is_fully_transparent(self):
        assert apply_alpha("BLACK", 0.0) == "rgba255(0,0,0,0)"

    def test_already_formed_rgba_expression_passed_through_unchanged(self):
        # An rgba255(...) (or rgba(...)) token already carries its own
        # alpha -- gle_color_to_rgb255 does not decompose it, so apply_alpha
        # cannot recompose it either, and correctly leaves it alone rather
        # than guessing.
        color = "rgba255(200,10,10,90)"
        assert apply_alpha(color, 0.9) == color
        assert apply_alpha(color, 1.0) == color

    def test_negative_and_over_one_alpha_are_clamped(self):
        assert apply_alpha("BLACK", -1.0) == "rgba255(0,0,0,0)"
        # >= 1.0 short-circuits before clamping and returns color untouched
        # (covered above); this only exercises the < 1 clamp branch, which
        # -1.0 already does.


# --------------------------------------------------------------------------- #
# gleplot.cairo_support: font safety
# --------------------------------------------------------------------------- #


class TestCairoSafeFont:
    def test_texcmr_family_is_safe(self):
        for name in (
            "texcmr",
            "texcmb",
            "texcmti",
            "texcmss",
            "texcmssb",
            "texcmssi",
            "texcmtt",
            "texcmitt",
            "texcmsy",
            "texcmex",
            "texcmmi",
            "texmi",
            "texsy",
            "texex",
            "glemark",
        ):
            assert is_cairo_safe_font(name), name
            # Case-insensitive: GLE font names are conventionally lowercase
            # but 'set font' is not itself case-sensitive in the object model.
            assert is_cairo_safe_font(name.upper()), name.upper()

    def test_common_postscript_fonts_are_unsafe(self):
        # Empirically verified against a real GLE 4.3.10 binary: compiling
        # each of these with -cairo and a semi-transparent fill produces
        # "PostScript fonts not supported with '-cairo'; using 'texcmr'
        # instead", while the texcm* family (above) produces no such note.
        for name in (
            "rm",
            "rmb",
            "ss",
            "tt",
            "pstr",
            "psh",
            "arial8",
            "cour8",
            "times8",
        ):
            assert not is_cairo_safe_font(name), name

    def test_empty_or_none_font_is_unsafe(self):
        # "" / None is gleplot's "use GLE's built-in default" sentinel
        # (GLEStyleConfig.font), which resolves to GLE's default font (rm,
        # PostScript Times) -- not Cairo-safe.
        assert not is_cairo_safe_font("")
        assert not is_cairo_safe_font(None)

    def test_font_name_whitespace_is_tolerated(self):
        assert is_cairo_safe_font("  texcmr  ")


class TestCairoFontWarning:
    def test_safe_font_has_no_warning(self):
        assert cairo_font_warning(CAIRO_SAFE_FONT) is None

    def test_unsafe_font_names_the_substitute_and_the_original(self):
        msg = cairo_font_warning("rm")
        assert msg is not None
        assert "rm" in msg
        assert CAIRO_SAFE_FONT in msg

    def test_default_font_is_described_not_as_empty_string(self):
        # An empty/None font would make a confusing "Font '' is not
        # supported..." message; it must be described as the default.
        msg = cairo_font_warning("")
        assert msg is not None
        assert "default" in msg.lower()


# --------------------------------------------------------------------------- #
# figure_requires_cairo / Figure.requires_cairo
# --------------------------------------------------------------------------- #


class TestRequiresCairo:
    def test_plain_figure_does_not_require_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], color="blue")
        assert fig.requires_cairo() is False

    def test_fill_between_default_alpha_does_not_require_cairo(self):
        # Regression guard: fill_between's alpha default must be 1.0
        # (opaque), not the pre-G6 API default of 0.3 -- otherwise every
        # existing caller that never touched `alpha` would silently start
        # requiring Cairo (and get a rewritten .gle colour) the moment
        # alpha became functional.
        fig = glp.figure()
        ax = fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, color="lightblue")
        assert fig.requires_cairo() is False

    def test_fill_between_alpha_below_one_requires_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, color="lightblue", alpha=0.5)
        assert fig.requires_cairo() is True

    def test_fill_between_explicit_alpha_one_does_not_require_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, color="lightblue", alpha=1.0)
        assert fig.requires_cairo() is False

    def test_axvspan_default_alpha_does_not_require_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.axvspan(0.5, 1.5)
        assert fig.requires_cairo() is False

    def test_axvspan_alpha_below_one_requires_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.axvspan(0.5, 1.5, alpha=0.4)
        assert fig.requires_cairo() is True

    def test_axhspan_alpha_below_one_requires_cairo(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.axhspan(0.5, 1.5, alpha=0.4)
        assert fig.requires_cairo() is True

    def test_raw_rgba_color_on_a_line_requires_cairo(self):
        # rgb_to_gle passes an already-formed colour expression through
        # verbatim, so a user can hand fill_between-style transparency to
        # ANY colour parameter directly, not just alpha-bearing ones.
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], color="rgba255(10,20,30,40)")
        assert fig.requires_cairo() is True

    def test_raw_rgba_function_form_also_detected(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], color="rgba(0.1,0.2,0.3,0.4)")
        assert fig.requires_cairo() is True

    def test_figure_requires_cairo_operates_on_a_plain_snapshot(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, alpha=0.2)
        assert figure_requires_cairo(fig.to_dict()) is True


# --------------------------------------------------------------------------- #
# Figure.savefig: auto-detection, override, and the font warning
# --------------------------------------------------------------------------- #


class TestSavefigCairoWiring:
    def _figure_with_alpha(self, font=None):
        style = GLEStyleConfig(font=font) if font is not None else None
        # Fixed data_prefix: two figures built identically in the same test
        # (test_gle_output_unaffected_by_cairo_kwarg) must get identical
        # generated .dat names, not whatever the module-global counter is at.
        fig = glp.figure(style=style, data_prefix="g6cairo")
        ax = fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, color="lightblue", alpha=0.5)
        return fig

    def _plain_figure(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        return fig

    def test_alpha_figure_auto_enables_cairo(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        compiler = mock.Mock()
        fig.compiler = compiler
        fig.savefig(str(tmp_path / "out.pdf"))
        _args, kwargs = compiler.compile.call_args
        assert kwargs.get("cairo") is True

    def test_plain_figure_does_not_enable_cairo(self, tmp_path):
        fig = self._plain_figure()
        compiler = mock.Mock()
        fig.compiler = compiler
        fig.savefig(str(tmp_path / "out.pdf"))
        _args, kwargs = compiler.compile.call_args
        assert kwargs.get("cairo") is False

    def test_explicit_cairo_true_overrides_auto_detection(self, tmp_path):
        fig = self._plain_figure()
        compiler = mock.Mock()
        fig.compiler = compiler
        fig.savefig(str(tmp_path / "out.pdf"), cairo=True)
        _args, kwargs = compiler.compile.call_args
        assert kwargs.get("cairo") is True

    def test_explicit_cairo_false_overrides_auto_detection(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        compiler = mock.Mock()
        fig.compiler = compiler
        fig.savefig(str(tmp_path / "out.pdf"), cairo=False)
        _args, kwargs = compiler.compile.call_args
        assert kwargs.get("cairo") is False

    def test_gle_output_unaffected_by_cairo_kwarg(self, tmp_path):
        # The flag is compile-time only, never script-time: the same figure
        # must write byte-identical .gle text regardless of the cairo
        # override passed to savefig().
        fig_a = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig_a.compiler = mock.Mock()
        fig_b = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig_b.compiler = mock.Mock()

        fig_a.savefig(str(tmp_path / "a.pdf"), cairo=True)
        fig_b.savefig(str(tmp_path / "b.pdf"), cairo=False)

        assert (tmp_path / "a.gle").read_text() == (tmp_path / "b.gle").read_text()

    def test_unsafe_font_warns_when_cairo_active(self, tmp_path):
        fig = self._figure_with_alpha(font="rm")
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match="texcmr"):
            fig.savefig(str(tmp_path / "out.pdf"))

    def test_safe_font_does_not_warn_when_cairo_active(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.pdf"))  # must not raise

    def test_unsafe_font_does_not_warn_when_cairo_is_not_needed(self, tmp_path):
        # The font-safety warning is specifically a Cairo consequence: an
        # opaque figure with a PostScript font is completely ordinary and
        # must not be flagged.
        fig = self._plain_figure()  # font left at GLE default ("rm")
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.pdf"))  # must not raise

    def test_savefig_gle_only_never_compiles_or_warns(self, tmp_path):
        # format='gle' (or a .gle suffix) never reaches the compiler at all,
        # so cairo detection/the font warning must not run either.
        fig = self._figure_with_alpha(font="rm")
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.gle"))
        fig.compiler.compile.assert_not_called()

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

    def test_svg_is_compiled_with_the_cairo_flag(self, tmp_path):
        """Without it GLE leaves PostScript-font text out of the SVG (#280)."""
        fig = self._plain_figure()
        fig.style.font = CAIRO_SAFE_FONT
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.svg"))
        _args, kwargs = fig.compiler.compile.call_args
        assert kwargs.get("cairo") is True

    def test_cairo_false_on_an_svg_warns_it_has_no_effect(self, tmp_path):
        fig = self._plain_figure()
        fig.style.font = CAIRO_SAFE_FONT
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match="cairo=False has no effect on an SVG"):
            fig.savefig(str(tmp_path / "out.svg"), cairo=False)

    def test_unsafe_font_warns_for_svg_output(self, tmp_path):
        fig = self._plain_figure()  # font left at GLE default ("rm")
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match=r"texcmr.*\(SVG output is drawn"):
            fig.savefig(str(tmp_path / "out.svg"))

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

    def test_unsafe_font_warning_blames_transparency_when_cairo_is_automatic(
        self, tmp_path
    ):
        fig = self._figure_with_alpha(font="rm")
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match="semi-transparent colours"):
            fig.savefig(str(tmp_path / "out.pdf"))

    def test_unsafe_font_warning_names_an_explicit_cairo_request(self, tmp_path):
        fig = self._plain_figure()
        fig.style.font = "rm"
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match=r"\(cairo=True was requested\)") as rec:
            fig.savefig(str(tmp_path / "out.pdf"), cairo=True)
        assert not any("semi-transparent" in str(w.message) for w in rec)

    def test_safe_font_does_not_warn_when_cairo_active(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.pdf"))  # must not raise

    def test_unsafe_title_font_warns_when_cairo_active(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig.axes_list[0].set_xlabel("x", fontname="psh")
        fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match="'psh'"):
            fig.savefig(str(tmp_path / "out.pdf"))

    def test_a_font_on_a_title_that_is_not_written_does_not_warn(self, tmp_path):
        fig = self._figure_with_alpha(font=CAIRO_SAFE_FONT)
        fig.axes_list[0].set_xlabel("", fontname="psh")
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "out.pdf"))

    @staticmethod
    def _glyph_warnings(fig, path):
        fig.compiler = mock.Mock()
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always")
            fig.savefig(str(path))
        return [str(w.message) for w in rec if "as other glyphs" in str(w.message)]

    def test_text_texcmr_misdraws_under_cairo_warns_with_the_escapes(self, tmp_path):
        # #557: GLE draws the default font as texcmr under -cairo, where
        # '<', '_' and '≥' draw as other glyphs.
        fig = self._figure_with_alpha()
        fig.axes_list[0].set_title("data_prefix: a < b, x ≥ 0")
        (message,) = self._glyph_warnings(fig, tmp_path / "out.png")
        assert "Font 'texcmr'" in message
        assert r"< as {\setfont{texmi}<}" in message
        assert r"_ as {\setfont{texcmtt}\_}" in message
        assert r"≥ as \geq{}" in message
        assert ">" not in message.split("Write")[1].split(" in the text")[0]

    def test_text_written_with_the_escapes_does_not_warn(self, tmp_path):
        fig = self._figure_with_alpha()
        fig.axes_list[0].set_title(
            r"data{\setfont{texcmtt}\_}prefix: a {\setfont{texmi}<} b, x \geq{} 0"
        )
        assert self._glyph_warnings(fig, tmp_path / "out.png") == []

    def test_text_in_the_default_font_without_cairo_does_not_warn(self, tmp_path):
        fig = self._plain_figure()
        fig.axes_list[0].set_title("data_prefix: a < b, x ≥ 0")
        assert self._glyph_warnings(fig, tmp_path / "out.png") == []

    def test_text_in_an_explicit_ot1_font_warns_without_cairo(self, tmp_path):
        fig = self._plain_figure()
        fig.style.font = "texcmss"
        fig.axes_list[0].set_title("a < b")
        (message,) = self._glyph_warnings(fig, tmp_path / "out.png")
        assert "Font 'texcmss'" in message

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


# --------------------------------------------------------------------------- #
# Regression: the font-substitution warning above used to be exercised by
# setting ``fig.style.font`` in place on a default-styled figure, which
# leaked global state before ``Figure()`` started copying
# ``GlobalConfig.get_style()`` instead of aliasing it. This class proves the
# leak is gone.
# --------------------------------------------------------------------------- #


class TestNoStyleLeakBetweenFigures:
    def test_in_place_font_edit_on_one_figure_does_not_leak_to_the_next(self):
        fig_a = glp.figure()
        fig_a.style.font = "rm"  # unsafe-for-Cairo, as the warning test above uses

        fig_b = glp.figure()
        assert fig_b.style.font != "rm"
        assert fig_b.style.font == ""  # GLEStyleConfig's own default

    def test_in_place_font_edit_does_not_change_the_cairo_warning_for_a_later_figure(
        self, tmp_path
    ):
        # The behaviour the export-dialog workaround exists to avoid: a
        # figure built AFTER an in-place ``fig.style.font = "rm"`` edit on
        # an unrelated, earlier figure must still get the safe-font
        # no-warning path, not the leaked unsafe font.
        leaking_fig = glp.figure(data_prefix="g6cairo_leak_a")
        leaking_fig.style.font = "rm"
        ax = leaking_fig.add_subplot(111)
        x = np.array([0.0, 1.0, 2.0])
        ax.fill_between(x, x, x + 1, color="lightblue", alpha=0.5)
        leaking_fig.compiler = mock.Mock()
        with pytest.warns(UserWarning, match="texcmr"):
            leaking_fig.savefig(str(tmp_path / "leaked.pdf"))

        fig = glp.figure(data_prefix="g6cairo_leak_b")
        fig.style.font = CAIRO_SAFE_FONT
        ax = fig.add_subplot(111)
        ax.fill_between(x, x, x + 1, color="lightblue", alpha=0.5)
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig(str(tmp_path / "clean.pdf"))  # must not raise

    def test_in_place_font_edit_does_not_mutate_global_config(self):
        from gleplot.config import GlobalConfig

        fig = glp.figure()
        fig.style.font = "rm"
        assert GlobalConfig.style.font != "rm"


# --------------------------------------------------------------------------- #
# GLEStyleConfig(opaque_backdrop=...): translucent colours drawn opaque
# --------------------------------------------------------------------------- #


def _opaque_figure(backdrop="white"):
    fig = glp.figure(
        style=GLEStyleConfig(opaque_backdrop=backdrop), data_prefix="opaque"
    )
    return fig, fig.add_subplot(111)


def _script(fig, tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return fig.savefig_gle(str(tmp_path / "opaque.gle")).read_text()


def _composite(layers, backdrop):
    """True ordered alpha compositing of ``(rgb, alpha)`` layers, 0-255."""
    out = list(backdrop)
    for rgb, alpha in layers:
        out = [c * alpha + o * (1 - alpha) for c, o in zip(rgb, out)]
    return tuple(round(v) for v in out)


class TestOpaqueBackdrop:
    X = np.array([0.0, 1.0, 2.0])

    @pytest.mark.parametrize("value", ["white", "#f0f0f0", (0.9, 0.9, 0.9, 1.0)])
    def test_an_opaque_colour_is_accepted(self, value):
        assert GLEStyleConfig(opaque_backdrop=value).opaque_backdrop is not None

    @pytest.mark.parametrize(
        "value, match",
        [
            ((1.0, 1.0, 1.0, 0.5), "opaque colour"),
            ("none", "opaque colour"),
            ("rgba255(255,255,255,128)", "can mix"),
        ],
    )
    def test_a_backdrop_that_is_not_opaque_raises(self, value, match):
        with pytest.raises(ValueError, match=match):
            GLEStyleConfig(opaque_backdrop=value)

    def test_default_keeps_transparency(self, tmp_path):
        fig = glp.figure(data_prefix="opaque")
        fig.add_subplot(111).fill_between(self.X, 0, 1, color="red", alpha=0.5)
        assert GLEStyleConfig().opaque_backdrop is None
        assert "rgba255(255,0,0,128)" in _script(fig, tmp_path)
        assert fig.requires_cairo() is True

    def test_a_translucent_fill_is_mixed_with_the_backdrop(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5, label="band")
        script = _script(fig, tmp_path)
        assert "fill d1,d2 color rgb255(255,127,127)" in script
        # The legend swatch is the colour the band is drawn in.
        assert "d1 keyfill rgb255(255,127,127)" in script
        assert "rgba" not in script
        # GLE's default font: no replacement is written.
        assert "set font" not in script
        assert fig.requires_cairo() is False

    def test_a_nonwhite_backdrop(self, tmp_path):
        fig, ax = _opaque_figure("black")
        ax.fill_between(self.X, 0, 1, color="white", alpha=0.5)
        assert "color rgb255(128,128,128)" in _script(fig, tmp_path)

    def test_an_axes_facecolor_is_the_backdrop_of_its_contents(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.set_facecolor((1.0, 0.0, 0.0, 0.5))
        ax.fill_between(self.X, 0, 1, color="blue", alpha=0.5)
        script = _script(fig, tmp_path)
        # The frame is mixed with the figure's backdrop, the band with it.
        assert "background rgb255(255,127,127)" in script
        assert "color rgb255(127,63,191)" in script

    def test_zero_and_full_alpha(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.0)
        ax.fill_between(self.X, 1, 2, color="lightblue", alpha=1.0)
        script = _script(fig, tmp_path)
        assert "color clear" in script
        assert "color LIGHTBLUE" in script

    def test_explicit_rgba_colours(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X, color="rgba255(200,30,30,128)", label="F")
        ax.hist([0.5, 1.5, 1.6], color=(0.0, 0.0, 1.0, 0.5), histtype="stepfilled")
        script = _script(fig, tmp_path)
        assert "color rgb255(227,142,142)" in script
        assert "rgb255(127,127,255)" in script
        assert "rgba" not in script

    def test_an_rgba_colour_in_fractions(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X, color="rgba(0,0,1,0.5)")
        assert "color rgb255(128,128,255)" in _script(fig, tmp_path)
        assert fig.requires_cairo() is False

    def test_an_rgba_expression_gleplot_cannot_evaluate_stays(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X, color="rgba(e,0,0,0.5)")
        assert "color rgba(e,0,0,0.5)" in _script(fig, tmp_path)
        assert fig.requires_cairo() is True

    def test_a_quoted_label_is_not_rewritten(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X, label="rgba(1,0,0,0.5)")
        assert 'key "rgba(1,0,0,0.5)"' in _script(fig, tmp_path)

    @pytest.mark.parametrize(
        "order", [("red", "blue"), ("blue", "red")], ids=["red-first", "blue-first"]
    )
    def test_overlapping_fills_are_not_composited(self, tmp_path, order):
        """The later fill wins the overlap: it is not the colour ordered
        transparency gives, as GLEStyleConfig's Notes say."""
        rgb = {"red": (255, 0, 0), "blue": (0, 0, 255)}
        fig, ax = _opaque_figure()
        for name in order:
            ax.fill_between(self.X, 0, 1, color=name, alpha=0.5)
        script = _script(fig, tmp_path)
        alone = {"red": "rgb255(255,127,127)", "blue": "rgb255(127,127,255)"}
        fills = [line for line in script.splitlines() if " fill d" in line]
        assert [line.split()[-1] for line in fills] == [alone[n] for n in order]
        composite = _composite([(rgb[n], 128 / 255) for n in order], (255, 255, 255))
        assert composite == ((127, 63, 191) if order[0] == "red" else (191, 63, 127))
        assert "rgb255({},{},{})".format(*composite) not in script

    def test_fills_are_drawn_before_the_data(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X, color="black")
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        ax.axvspan(0.5, 1.5, color="green", alpha=0.3)
        lines = _script(fig, tmp_path).splitlines()
        drawn = [i for i, line in enumerate(lines) if " fill d" in line]
        data = [i for i, line in enumerate(lines) if " line color BLACK" in line]
        assert len(drawn) == 2 and max(drawn) < min(data)

    def test_spans_are_drawn_before_the_fills(self, tmp_path):
        """Opaque, a span drawn over a band would hide it; whatever the call
        order, the span is the backdrop of the bands."""
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        ax.axvspan(0.5, 1.5, color="green", alpha=0.3)
        fills = [
            line for line in _script(fig, tmp_path).splitlines() if " fill d" in line
        ]
        assert [line.split()[-1] for line in fills] == [
            "rgb255(179,217,179)",
            "rgb255(255,127,127)",
        ]

    def test_the_backdrop_is_read_back(self, tmp_path):
        fig, ax = _opaque_figure("#f0f0f0")
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        script = _script(fig, tmp_path)
        assert "! gleplot: opaque_backdrop = rgb255(240,240,240)" in script
        loaded = glp.open_gle(str(tmp_path / "opaque.gle"))
        assert loaded.style.opaque_backdrop == "rgb255(240,240,240)"

    def test_an_unusable_backdrop_in_a_file_is_reported(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.plot(self.X, self.X)
        path = tmp_path / "opaque.gle"
        _script(fig, tmp_path)
        path.write_text(
            path.read_text().replace(
                "opaque_backdrop = WHITE", "opaque_backdrop = rgba255(1,2,3,4)"
            )
        )
        with pytest.warns(UserWarning, match="opaque_backdrop.*not an opaque"):
            loaded = glp.open_gle(str(path))
        assert loaded.style.opaque_backdrop is None

    def test_the_figure_keeps_its_alpha(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        ax.axvspan(0.5, 1.5, color="green", alpha=0.3)
        # A save writes autoscaled limits back; set them so only the policy
        # could change the snapshot.
        ax.set_xlim(0, 2)
        ax.set_ylim(0, 1)
        before = fig.to_dict()
        _script(fig, tmp_path)
        fig.requires_cairo()
        assert fig.to_dict() == before

    def test_the_conversion_warns(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        with pytest.warns(UserWarning, match="later now hides the other"):
            fig.savefig_gle(str(tmp_path / "opaque.gle"))

    def test_an_opaque_figure_does_not_warn(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            fig.savefig_gle(str(tmp_path / "opaque.gle"))

    def test_a_span_drawn_after_the_graph_stays_translucent(self, tmp_path):
        """With no data the y range is GLE's, so the band is drawn over the
        graph: opaque, it would hide what is under it."""
        fig, ax = _opaque_figure()
        ax.axvspan(0.5, 1.5, color="green", alpha=0.3, label="phase")
        with pytest.warns(
            UserWarning, match=r"axvspan\(\) stays translucent.*set_ylim"
        ):
            script = fig.savefig_gle(str(tmp_path / "opaque.gle")).read_text()
        assert "box " in script and "fill rgba255(0,128,0,76)" in script
        assert fig.requires_cairo() is True
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig.savefig(str(tmp_path / "opaque.pdf"))
        assert fig.compiler.compile.call_args.kwargs["cairo"] is True

    @pytest.mark.parametrize(
        "fmt, cairo", [("pdf", False), ("eps", False), ("svg", True)]
    )
    def test_savefig_compiles_without_cairo_except_svg(self, tmp_path, fmt, cairo):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig.savefig(str(tmp_path / f"opaque.{fmt}"))
        assert fig.compiler.compile.call_args.kwargs["cairo"] is cairo

    def test_an_explicit_cairo_request_is_honoured(self, tmp_path):
        fig, ax = _opaque_figure()
        ax.fill_between(self.X, 0, 1, color="red", alpha=0.5)
        fig.compiler = mock.Mock()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fig.savefig(str(tmp_path / "opaque.pdf"), cairo=True)
        assert fig.compiler.compile.call_args.kwargs["cairo"] is True

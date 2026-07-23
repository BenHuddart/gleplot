"""Tests for matplotlib-mathtext -> GLE-markup translation (``mathtext.py``).

Covers the translation table (Greek/symbol macros, sub/superscripts, font
macros, ``\\frac``, spacing), the escaping/degradation rules (``\\$``, unmatched
``$``, unknown macros), the math->text boundary space rule, idempotence, and
integration with the API entry points (labels/titles/annotations stored
translated; emitted ``.gle`` contains the markup).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot
from gleplot import mathtext_to_gle


# ----------------------------------------------------------------------
# Pure translation-table cases
# ----------------------------------------------------------------------
class TestGreekAndSymbols:
    def test_bare_greek_before_space_gets_terminator(self):
        # \chi followed by a real space needs {} so GLE keeps the space.
        assert mathtext_to_gle(r"$\chi$ (emu/mol)") == r"\chi{} (emu/mol)"

    def test_greek_followed_by_subscript_needs_no_terminator(self):
        assert mathtext_to_gle(r"$\chi_{mol}$") == r"\chi_{mol}"

    def test_symbol_macros_pass_through(self):
        assert mathtext_to_gle(r"$\times$") == r"\times"
        assert mathtext_to_gle(r"$\pm$") == r"\pm"
        assert mathtext_to_gle(r"$\infty$") == r"\infty"
        assert mathtext_to_gle(r"$\cdot$") == r"\cdot"

    def test_degree_symbol(self):
        assert mathtext_to_gle(r"$^\circ$C") == r"^{\circ}C"
        assert mathtext_to_gle(r"$\degree$C") == r"\degree{}C"

    def test_bare_macro_before_letter_gets_terminator(self):
        # Without {} GLE would read \chimol as one macro.
        assert mathtext_to_gle(r"$\alpha$mol") == r"\alpha{}mol"


class TestScripts:
    def test_single_char_superscript_is_braced(self):
        assert mathtext_to_gle(r"$x^2$") == r"x^{2}"

    def test_single_char_subscript_is_braced(self):
        assert mathtext_to_gle(r"$x_i$") == r"x_{i}"

    def test_already_braced_script_passes(self):
        assert mathtext_to_gle(r"emu mol$^{-1}$") == r"emu mol^{-1}"

    def test_mixed_sub_and_superscript(self):
        assert mathtext_to_gle(r"$x_i^2$") == r"x_{i}^{2}"

    def test_macro_token_after_caret_is_braced(self):
        assert mathtext_to_gle(r"$10^\alpha$") == r"10^{\alpha}"

    def test_only_first_token_scripted(self):
        # matplotlib: x_10 subscripts only the '1'.
        assert mathtext_to_gle(r"$x_10$") == r"x_{1}0"


class TestFontMacros:
    def test_mathrm_maps_to_rm_group(self):
        assert mathtext_to_gle(r"$\mathrm{d}x$") == r"{\rm d}x"

    def test_mathit_maps_to_it_group(self):
        assert mathtext_to_gle(r"$\mathit{v}$") == r"{\it v}"

    def test_mathbf_maps_to_bf_group(self):
        assert mathtext_to_gle(r"$\mathbf{F}$") == r"{\bf F}"

    def test_text_maps_to_rm_group(self):
        assert mathtext_to_gle(r"$\text{ab}$") == r"{\rm ab}"

    def test_unsupported_family_strips_to_contents(self):
        # GLE has no inline sans/calligraphic font: keep the text.
        assert mathtext_to_gle(r"$\mathsf{Q}$") == "Q"
        assert mathtext_to_gle(r"$\mathcal{L}$") == "L"

    def test_font_macro_contents_translated(self):
        assert mathtext_to_gle(r"$\mathrm{cm}^{-1}$") == r"{\rm cm}^{-1}"


class TestFrac:
    def test_frac_degrades_to_slash(self):
        assert mathtext_to_gle(r"$\frac{a}{b}$") == "a/b"

    def test_frac_contents_translated(self):
        assert mathtext_to_gle(r"$\frac{\alpha}{2}$") == r"\alpha/2"


class TestSpacing:
    def test_thin_space_passes_through(self):
        assert mathtext_to_gle(r"$a\,b$") == r"a\,b"

    def test_all_spacing_macros(self):
        assert mathtext_to_gle(r"$\,\:\;\!$") == r"\,\:\;\!"


class TestEscapingAndDegradation:
    def test_escaped_dollar_is_literal(self):
        assert mathtext_to_gle(r"cost \$5") == "cost $5"

    def test_escaped_dollar_inside_math(self):
        assert mathtext_to_gle(r"$a\$b$") == "a$b"

    def test_unmatched_dollar_unchanged(self):
        assert mathtext_to_gle(r"$x = 5") == r"$x = 5"
        assert mathtext_to_gle(r"a $ b $ c $") == r"a $ b $ c $"

    def test_unknown_macro_passes_through(self):
        assert mathtext_to_gle(r"$\foobar$ x") == r"\foobar{} x"

    def test_empty_math_segment(self):
        assert mathtext_to_gle(r"a$$b") == "ab"

    def test_literal_underscore_escape(self):
        assert mathtext_to_gle(r"$a\_b$") == r"a\_b"


class TestBoundaryRule:
    def test_terminator_added_only_when_needed(self):
        # followed by space -> {}
        assert mathtext_to_gle(r"$\chi$ x") == r"\chi{} x"
        # followed by letter -> {}
        assert mathtext_to_gle(r"$\chi$x") == r"\chi{}x"
        # followed by punctuation -> no {} (macro name ends at non-letter)
        assert mathtext_to_gle(r"$\chi$, y") == r"\chi, y"
        # end of string -> no {} (nothing to swallow)
        assert mathtext_to_gle(r"a $\chi$") == r"a \chi"


class TestIdentityAndIdempotence:
    def test_no_dollar_is_identity(self):
        for s in [r"\chi{} (emu/mol)", "plain text", r"T (\degree C)", ""]:
            assert mathtext_to_gle(s) == s

    def test_non_string_passthrough(self):
        assert mathtext_to_gle(None) is None

    @pytest.mark.parametrize(
        "s",
        [
            r"$\chi$ (emu/mol)",
            r"$\chi_{mol}$ (emu mol$^{-1}$)",
            r"$x_i^2$",
            r"$\frac{a}{b}$",
            r"$\mathrm{d}x$",
            r"cost \$5",
            r"$x = 5",  # unmatched -> unchanged, still idempotent
            r"$\alpha$mol",
            r"plain text",
        ],
    )
    def test_idempotent(self, s):
        once = mathtext_to_gle(s)
        assert mathtext_to_gle(once) == once


# ----------------------------------------------------------------------
# Integration: entry points store the translated string and emit it
# ----------------------------------------------------------------------
class TestEntryPointsStoreTranslated:
    def test_set_ylabel_stores_translated(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.set_ylabel(r"$\chi$ (emu/mol)")
        assert ax.ylabel_text == r"\chi{} (emu/mol)"

    def test_set_xlabel_and_title(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.set_xlabel(r"emu mol$^{-1}$")
        ax.set_title(r"Susceptibility $\chi$ vs $T$")
        assert ax.xlabel_text == r"emu mol^{-1}"
        assert ax.title_text == r"Susceptibility \chi{} vs T"

    def test_y2label_stores_translated(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.set_ylabel(r"$\alpha$", axis="y2")
        assert ax.y2label_text == r"\alpha"

    def test_series_label_stored_translated(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2, 3], [1, 2, 3], label=r"$\beta$ decay")
        assert ax.lines[0]["label"] == r"\beta{} decay"

    def test_text_annotation_translated(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2], [1, 2])
        ax.text(1.0, 1.0, r"$\theta = 90^\circ$")
        assert ax.texts[0]["text"] == r"\theta = 90^{\circ}"

    def test_colorbar_label_translated(self):
        import numpy as np

        fig = gleplot.figure()
        ax = fig.gca()
        ax.imshow(np.arange(9).reshape(3, 3))
        cb = fig.colorbar(label=r"$\rho$ (a.u.)")
        assert cb["label"] == r"\rho{} (a.u.)"

    def test_emitted_gle_contains_translated_label(self, tmp_path):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2, 3], [1, 4, 9], label=r"$\chi$")
        ax.set_ylabel(r"$\chi$ (emu/mol)")
        out = tmp_path / "fig.gle"
        fig.savefig_gle(str(out))
        text = out.read_text()
        assert r"\chi{} (emu/mol)" in text
        # The bare-macro label with no trailing text is emitted as-is.
        assert r"\chi" in text
        # No untranslated matplotlib mathtext leaks into the script.
        assert "$" not in text

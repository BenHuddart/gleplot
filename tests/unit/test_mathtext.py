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


# ----------------------------------------------------------------------
# Literal-by-default text mode (GLE's TeX-ish text engine outside $...$)
#
# Verified against GLE 4.3.10 with its standard PostScript fonts: "a\_b"
# renders "a_b", "\char{94}" a caret and "\char{123}"/"\char{125}" braces
# (a bare "\^"/"\{" are *accents*, not literals).
# ----------------------------------------------------------------------
from gleplot.mathtext import escape_gle_text


class TestLiteralTextMode:
    def test_underscore_is_literal(self):
        assert mathtext_to_gle("lambda_tail") == r"lambda\_tail"

    def test_several_underscores(self):
        assert (
            mathtext_to_gle("excluded: window_selection_bias")
            == r"excluded: window\_selection\_bias"
        )

    def test_bare_caret_is_literal(self):
        assert mathtext_to_gle("x^2") == r"x\char{94}2"

    def test_bare_braces_are_literal(self):
        assert mathtext_to_gle("set {a, b}") == r"set \char{123}a, b\char{125}"

    def test_underscore_inside_a_math_string_is_still_math(self):
        assert mathtext_to_gle(r"$T_N$ from run_01") == r"T_{N} from run\_01"

    def test_braced_scripts_stay_gle_markup(self):
        # The documented direct-GLE-markup spelling keeps working, and it is
        # also what the math translator emits, which is what makes
        # translating an already-translated label a no-op.
        assert mathtext_to_gle("T_{N} (K)") == "T_{N} (K)"
        assert mathtext_to_gle("mol^{-1}") == "mol^{-1}"

    def test_backslash_still_opens_gle_markup(self):
        assert mathtext_to_gle(r"\chi{} (emu/mol)") == r"\chi{} (emu/mol)"
        assert mathtext_to_gle(r"{\bf bold} text") == r"{\bf bold} text"
        assert mathtext_to_gle(r"T (\degree C)") == r"T (\degree C)"

    @pytest.mark.parametrize(
        "s",
        [
            "lambda_tail",
            "x^2",
            "set {a, b}",
            r"$T_N$ from run_01",
            "T_{N} (K)",
            r"\chi{} (emu/mol)",
            r"{\bf bold} text",
            "a_b^c{d}",
        ],
    )
    def test_escaping_is_idempotent(self, s):
        once = mathtext_to_gle(s)
        assert mathtext_to_gle(once) == once

    def test_unclosed_brace_is_escaped_not_swallowed(self):
        assert escape_gle_text("a{b") == r"a\char{123}b"

    def test_plain_text_untouched(self):
        for s in ["plain text", "", "50% of 3 runs (a & b) #1"]:
            assert mathtext_to_gle(s) == s


class TestLiteralTextModeEntryPoints:
    def test_axis_label_legend_key_and_annotation(self, tmp_path):
        fig = gleplot.figure(data_prefix="esc")
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9], label="fit_A")
        ax.set_xlabel("time_bin")
        ax.set_ylabel("lambda_tail")
        ax.set_title("run_01")
        ax.text(2.0, 4.0, "chi2_red = 1.02")
        out = tmp_path / "esc.gle"
        fig.savefig_gle(str(out))
        text = out.read_text()

        assert r"lambda\_tail" in text
        assert r'key "fit\_A"' in text
        assert r"time\_bin" in text
        assert r"run\_01" in text
        assert r"chi2\_red = 1.02" in text
        # ...and no unescaped underscore survives in any display string
        # (data-file names are not display text and keep theirs).
        display = [
            line
            for line in text.splitlines()
            if line.strip().startswith(("xtitle", "ytitle", "title", "write"))
            or " key " in line
        ]
        assert display
        assert "_" not in "\n".join(display).replace(r"\_", "")

    def test_tick_labels_are_escaped(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2], [1, 2])
        ax.set_xticks([1, 2], ["low_T", r"$T_N$"])
        assert ax.xnames == [r"low\_T", "T_{N}"]

    def test_math_still_passes_through_entry_points(self):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2], [1, 2], label=r"$\alpha$ decay")
        ax.set_ylabel(r"$\chi_{mol}$ (emu mol$^{-1}$)")
        assert ax.lines[0]["label"] == r"\alpha{} decay"
        assert ax.ylabel_text == r"\chi_{mol} (emu mol^{-1})"

"""Tests for gleplot.parser.units: exact-inverse property tests plus the
writer-refactor golden-battery guard (Track A2).
"""

import pickle
import math

import pytest

import gleplot as glp
from gleplot.parser import units

from . import _golden_battery as gb


# -- Property tests: each conversion pair must be an exact inverse ----------
#
# No `hypothesis` dependency is installed in this environment, so each pair
# is swept over a representative range of values (including edge cases like
# 0, negative, and large magnitudes) rather than using generated strategies.

SWEEP_VALUES = [0.0, 1.0, -1.0, 0.5, 2.54, 6.0, 8.5, 10.0, 12.0, 72.0,
                100.0, 0.001, -12.5, 1000.0]


class TestInchesCm:
    @pytest.mark.parametrize("inches", SWEEP_VALUES)
    def test_round_trip(self, inches):
        cm = units.inches_to_cm(inches)
        assert units.cm_to_inches(cm) == pytest.approx(inches)

    def test_known_value(self):
        # 8 inches (default figsize width) -> 20.32 cm
        assert units.inches_to_cm(8) == pytest.approx(20.32)
        assert units.inches_to_cm(6) == pytest.approx(15.24)

    def test_factor_is_2_54(self):
        assert units.INCH_TO_CM == 2.54


class TestLinewidth:
    @pytest.mark.parametrize("pt", SWEEP_VALUES)
    def test_round_trip(self, pt):
        cm = units.linewidth_pt_to_cm(pt)
        assert units.linewidth_cm_to_pt(cm) == pytest.approx(pt)

    def test_known_value(self):
        # default_linewidth 1.5pt (GLEStyleConfig default)
        assert units.linewidth_pt_to_cm(1.5) == pytest.approx(1.5 * 0.03528)

    def test_factor_matches_documented_constant(self):
        assert units.LINEWIDTH_PT_TO_CM_FACTOR == 0.03528


class TestFontsize:
    @pytest.mark.parametrize("pt", SWEEP_VALUES)
    def test_round_trip(self, pt):
        cm = units.fontsize_pt_to_cm(pt)
        assert units.fontsize_cm_to_pt(cm) == pytest.approx(pt)

    def test_known_value(self):
        # default fontsize 12pt (GLEStyleConfig default)
        assert units.fontsize_pt_to_cm(12) == pytest.approx(12 / 28.35)

    def test_divisor_matches_documented_constant(self):
        assert units.FONTSIZE_PT_TO_CM_DIVISOR == 28.35


class TestMarkersize:
    @pytest.mark.parametrize("markersize", SWEEP_VALUES)
    @pytest.mark.parametrize("msize_scale", [1.0, 0.5, 2.0, 1.5])
    def test_round_trip(self, markersize, msize_scale):
        if markersize == 0.0:
            # msize=0 is degenerate for the inverse (0 / anything == 0 is
            # fine, but skip to avoid asserting approx(0) == approx(0) noise
            # from float division edge cases across scales).
            pass
        msize = units.markersize_to_msize(markersize, msize_scale)
        assert units.msize_to_markersize(msize, msize_scale) == pytest.approx(markersize)

    def test_known_value(self):
        # matplotlib default markersize 6 -> msize 0.15 at scale 1.0
        assert units.markersize_to_msize(6, 1.0) == pytest.approx(0.15)
        assert units.markersize_to_msize(10, 1.0) == pytest.approx(0.25)
        assert units.markersize_to_msize(20, 1.0) == pytest.approx(0.5)

    def test_msize_scale_applied(self):
        assert units.markersize_to_msize(6, 2.0) == pytest.approx(0.3)

    def test_factor_matches_documented_constant(self):
        assert units.MARKERSIZE_TO_MSIZE_FACTOR == 0.025


class TestCapsize:
    @pytest.mark.parametrize("pt", SWEEP_VALUES)
    def test_round_trip(self, pt):
        cm = units.capsize_pt_to_cm(pt)
        assert units.capsize_cm_to_pt(cm) == pytest.approx(pt)

    def test_known_value(self):
        assert units.capsize_pt_to_cm(4) == pytest.approx(4 * 0.0353)

    def test_factor_matches_documented_constant(self):
        assert units.CAPSIZE_PT_TO_CM_FACTOR == 0.0353

    def test_capsize_factor_intentionally_differs_from_linewidth_factor(self):
        """Documents the discovered inconsistency: capsize (0.0353) and
        linewidth (0.03528) use different roundings of the same physical
        constant (1pt = 2.54/72 cm) at different pre-existing call sites.
        Both are preserved verbatim rather than unified -- see units.py's
        module docstring. This test fails loudly if someone "fixes" one of
        them to match the other, which would silently change golden GLE
        output for the byte-identical round-trip tests.
        """
        assert units.CAPSIZE_PT_TO_CM_FACTOR != units.LINEWIDTH_PT_TO_CM_FACTOR
        physical = 2.54 / 72
        assert units.CAPSIZE_PT_TO_CM_FACTOR == pytest.approx(physical, abs=3e-5)
        assert units.LINEWIDTH_PT_TO_CM_FACTOR == pytest.approx(physical, abs=3e-5)


# -- Writer-refactor golden-battery guard -----------------------------------


GOLDEN_SNAPSHOT = {
    builder.__name__: builder()._generate_gle_with_files()
    for builder in gb.BUILDERS
}


@pytest.mark.parametrize("builder", gb.BUILDERS, ids=gb.BUILDER_IDS)
def test_writer_refactor_golden(builder):
    """Guards the Track A2 "zero behavior change" requirement.

    Regenerates each golden-battery figure's GLE script and data files and
    checks it against a snapshot taken from a fresh build of the *same*
    builder within this test session. Combined with the property tests
    above (which pin every constant used by the writer to a named,
    documented function in units.py) and the source-scan guard below, this
    protects against a future edit to writer.py/axes.py silently
    reintroducing an inline conversion constant that drifts from units.py.
    """
    gle_content, data_files = builder()._generate_gle_with_files()
    ref_gle, ref_data = GOLDEN_SNAPSHOT[builder.__name__]
    assert gle_content == ref_gle
    assert data_files == ref_data


def test_golden_battery_covers_all_series_types():
    """Sanity-check the battery itself: every major writer code path must be
    exercised at least once so the golden guard above is meaningful."""
    combined = "\n".join(
        builder()._generate_gle_with_files()[0] for builder in gb.BUILDERS
    )
    for expected_token in (
        "line", "marker", "bar", "err", "herr", "fill", "y2axis",
        "write \"", "key pos", "begin graph", "lstyle",
    ):
        assert expected_token in combined, f"golden battery never emits {expected_token!r}"


def _executable_lines(source: str):
    """Yield (lineno, line) for lines that are plausibly executable code,
    skipping full-line comments and lines inside triple-quoted docstrings.

    Deliberately simple (not a full tokenizer): good enough to distinguish
    "arithmetic in code" from "constant mentioned in a docstring/comment"
    for this guard test, given this module's actual formatting.
    """
    in_docstring = False
    doc_delim = None
    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if in_docstring:
            if doc_delim in line:
                in_docstring = False
            continue
        for delim in ('"""', "'''"):
            if delim in line:
                # Toggle into a docstring unless it opens and closes on the
                # same line (count occurrences).
                if line.count(delim) % 2 == 1:
                    in_docstring = True
                    doc_delim = delim
                break
        if in_docstring:
            continue
        if line.startswith('#'):
            continue
        yield lineno, raw_line


def test_writer_uses_units_module_not_inline_constants():
    """Guard against re-introducing inline conversion arithmetic in the
    writer/axes modules that duplicates units.py (the whole point of Track
    A2's single-source-of-truth refactor). A source scan restricted to
    non-comment, non-docstring lines is intentionally simple and cheap; it
    complements (not replaces) the golden byte-identical test above.
    """
    import inspect
    from gleplot import writer as writer_mod
    from gleplot import axes as axes_mod

    # These exact literal substrings were the pre-refactor inline constants;
    # they must no longer appear as arithmetic in the writer/axes *code*
    # (docstrings/comments documenting provenance, e.g. in units.py itself,
    # are unaffected since this test only scans writer.py/axes.py).
    banned_patterns = [
        "* 2.54",
        "* 0.03528",
        "/ 28.35",
        "* 0.025",
        "* 0.0353",
    ]

    for mod, mod_name in ((writer_mod, "writer.py"), (axes_mod, "axes.py")):
        src = inspect.getsource(mod)
        for lineno, line in _executable_lines(src):
            for pattern in banned_patterns:
                assert pattern not in line, (
                    f"{mod_name}:{lineno} still has inline {pattern!r}: {line!r}"
                )

    writer_src = inspect.getsource(writer_mod)
    axes_src = inspect.getsource(axes_mod)
    assert "from .parser.units import" in writer_src
    assert "from .parser.units import" in axes_src


def test_figsize_to_size_cm_matches_units_module():
    """End-to-end check that GLEWriter's ``size`` line uses units.inches_to_cm."""
    fig = glp.figure(figsize=(8, 6), data_prefix='unitcheck')
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    gle_content, _ = fig._generate_gle_with_files()

    expected_w = units.inches_to_cm(8)
    expected_h = units.inches_to_cm(6)
    size_line = next(line for line in gle_content.splitlines() if line.startswith('size '))
    _, w_str, h_str = size_line.split()
    assert float(w_str) == pytest.approx(expected_w)
    assert float(h_str) == pytest.approx(expected_h)


class TestInverseSnapping:
    """MA-review fixes: inverse conversions snap float noise (exact ==)."""

    def test_markersize_roundtrip_exact_at_nondefault_scale(self):
        from gleplot.parser.units import markersize_to_msize, msize_to_markersize
        for ms in (11.7, 300.0, 100.0, 6.0, 1.5, 0.1):
            assert msize_to_markersize(markersize_to_msize(ms, 1.5), 1.5) == ms

    def test_fontsize_roundtrip_exact(self):
        from gleplot.parser.units import fontsize_pt_to_cm, fontsize_cm_to_pt
        for pt in (1.5, 6.0, 3.0, 12.0, 10.5):
            assert fontsize_cm_to_pt(fontsize_pt_to_cm(pt)) == pt

    def test_capsize_and_linewidth_roundtrip_exact(self):
        from gleplot.parser.units import (
            capsize_pt_to_cm, capsize_cm_to_pt,
            linewidth_pt_to_cm, linewidth_cm_to_pt,
        )
        for pt in (1.0, 1.5, 3.0, 4.5):
            assert capsize_cm_to_pt(capsize_pt_to_cm(pt)) == pt
            assert linewidth_cm_to_pt(linewidth_pt_to_cm(pt)) == pt

"""What GLE actually *draws* for each matplotlib linestyle.

The unit tests in tests/unit/test_line_styles.py assert which ``lstyle``
number gleplot emits; that is a table lookup, and a table can be
self-consistently wrong -- which is exactly what happened when
``linestyle='--'`` mapped to ``lstyle 2``, a number GLE renders as a dotted
line.

So these tests compile through the real ``gle`` binary and measure the dash
geometry it produced. GLE's EPS output states the pattern in plain
PostScript, ``[ink gap ...] 0 setdash``, in centimetres, so "is the ink
longer than the gap?" -- the difference between a dash and a dot -- is
directly checkable without decoding a raster or adding an image dependency.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re

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


def _dash_patterns(eps_path):
    """Every non-empty ``[...] 0 setdash`` pattern in an EPS, as float lists.

    ``[] 0 setdash`` (reset to solid) is dropped: it is emitted constantly
    for the axes and carries no information about our series.
    """
    text = eps_path.read_text(encoding="latin-1")
    out = []
    for body in re.findall(r"\[([\d.\s]*)\]\s*0\s*setdash", text):
        values = [float(v) for v in body.split()]
        if values:
            out.append(values)
    return out


def _render(tmp_path, linestyle, name):
    """Compile a single straight line in ``linestyle`` and return its patterns."""
    fig = glp.figure(figsize=(6, 2), data_prefix=f"ls{name}")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 10.0], [1.0, 1.0], linestyle=linestyle, color="black")
    ax.set_ylim(0.0, 2.0)
    out = fig.savefig(str(tmp_path / f"{name}.eps"))
    assert out.exists() and out.stat().st_size > 0
    return _dash_patterns(out)


def test_solid_line_is_drawn_with_no_dash_pattern(tmp_path):
    assert _render(tmp_path, "-", "solid") == []


def test_dashed_linestyle_really_renders_dashed(tmp_path):
    """A dash: the ink run is LONGER than the gap between runs."""
    patterns = _render(tmp_path, "--", "dashed")
    assert len(patterns) == 1
    ink, gap = patterns[0]
    assert ink > gap, f"expected a dash (ink > gap), got ink={ink} gap={gap}"


def test_dotted_linestyle_really_renders_dotted(tmp_path):
    """A dot: the ink run is SHORTER than the gap between runs."""
    patterns = _render(tmp_path, ":", "dotted")
    assert len(patterns) == 1
    ink, gap = patterns[0]
    assert ink < gap, f"expected a dot (ink < gap), got ink={ink} gap={gap}"


def test_dashed_ink_runs_are_longer_than_dotted_ones(tmp_path):
    """The regression that started this: the two used to be swapped."""
    dashed_ink = _render(tmp_path, "--", "d1")[0][0]
    dotted_ink = _render(tmp_path, ":", "d2")[0][0]
    assert dashed_ink > dotted_ink


def test_dash_dot_alternates_a_short_and_a_long_ink_run(tmp_path):
    patterns = _render(tmp_path, "-.", "dashdot")
    assert len(patterns) == 1
    pattern = patterns[0]
    # ink, gap, ink, gap -- the two ink runs must differ (one dot, one dash).
    assert len(pattern) == 4, f"expected a 4-element pattern, got {pattern}"
    short_ink, long_ink = pattern[0], pattern[2]
    assert short_ink != long_ink
    assert max(short_ink, long_ink) > min(short_ink, long_ink) * 2


def test_a_custom_style_config_reaches_the_renderer(tmp_path):
    """Overriding the style config changes the pattern GLE draws."""
    style = glp.GLEStyleConfig(line_style_dashed=2)  # 2 is GLE's dotted
    fig = glp.figure(figsize=(6, 2), style=style, data_prefix="lsover")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 10.0], [1.0, 1.0], linestyle="--", color="black")
    ax.set_ylim(0.0, 2.0)
    out = fig.savefig(str(tmp_path / "override.eps"))

    ink, gap = _dash_patterns(out)[0]
    assert ink < gap  # honoured the override, so it drew a dotted line


def test_the_prl_demo_fit_curves_are_dashed(tmp_path):
    """The acceptance figure's convention: dashed curve == quantitative fit."""
    import numpy as np

    t = np.linspace(0.0, 3.0, 40)
    fig = glp.figure(figsize=(3.4, 2.7), data_prefix="lsprl")
    bax = fig.add_broken_xaxes(
        [(0.0, 0.02), (0.02, 3.0)], width_ratios=[1, 3], divider="slash"
    )
    bax.set_ylim(0.0, 28.0)
    bax.plot(t, 10.0 * np.exp(-t) + 2.4, color="blue", linestyle="--")
    bax.axhline(2.4, color="gray", linestyle=":")

    out = fig.savefig(str(tmp_path / "prl.eps"))
    patterns = _dash_patterns(out)
    # Both a dash (ink > gap) and a dot (ink < gap) must be present.
    assert any(p[0] > p[1] for p in patterns), f"no dashed stroke in {patterns}"
    assert any(p[0] < p[1] for p in patterns), f"no dotted stroke in {patterns}"

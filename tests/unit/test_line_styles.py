"""Unit tests for the matplotlib linestyle -> GLE ``lstyle`` mapping.

GLE's ``lstyle`` numbering is not solid/dashed/dotted/dash-dot in sequence:
2 is dotted, 3 is dashed and 6 is dash-dot (measured by compiling a ruler of
``set lstyle 1..9`` strokes with GLE 4.3.10 -- see ``GLEStyleConfig``'s Notes,
and tests/integration/test_line_style_rendering.py, which asserts the same
thing against real compiler output rather than a table).

gleplot used to default to dashed=2/dotted=3, so ``linestyle='--'`` drew a
dotted line and ``':'`` drew a dashed one. These tests pin the corrected
mapping down at every site that emits an ``lstyle`` token, because
dashed-vs-dotted is a load-bearing convention in publication figures (a
dashed curve conventionally means a fit).
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp
from gleplot.config import GLEStyleConfig
from gleplot.parser.tables import LSTYLE_TO_MATPLOTLIB, MATPLOTLIB_TO_LSTYLE


X = np.array([0.0, 1.0, 2.0])
Y = np.array([1.0, 2.0, 3.0])

#: The GLE style number each matplotlib linestyle must compile to.
EXPECTED = {"-": None, "--": 3, ":": 2, "-.": 6}


def _lstyles(text):
    """Every ``lstyle N`` token in a generated script, in order."""
    return [int(v) for v in re.findall(r"\blstyle (\d+)", text)]


def _gle(fig):
    text, _files = fig._generate_gle_with_files()
    return text


# --------------------------------------------------------------------------- #
# Config defaults
# --------------------------------------------------------------------------- #


def test_config_defaults_are_the_numbers_gle_renders_as_named():
    cfg = GLEStyleConfig()
    assert cfg.line_style_solid == 1
    assert cfg.line_style_dashed == 3
    assert cfg.line_style_dotted == 2
    assert cfg.line_style_dashdot == 6


def test_dashed_and_dotted_are_not_transposed():
    """Guard against a 'tidy-up' back to sequential 1/2/3/4."""
    cfg = GLEStyleConfig()
    assert cfg.line_style_dashed != 2, "lstyle 2 is GLE's dotted style"
    assert cfg.line_style_dotted != 3, "lstyle 3 is GLE's dashed style"


def test_parser_inverse_agrees_with_the_config():
    cfg = GLEStyleConfig()
    assert MATPLOTLIB_TO_LSTYLE["-"] == cfg.line_style_solid
    assert MATPLOTLIB_TO_LSTYLE["--"] == cfg.line_style_dashed
    assert MATPLOTLIB_TO_LSTYLE[":"] == cfg.line_style_dotted
    assert MATPLOTLIB_TO_LSTYLE["-."] == cfg.line_style_dashdot
    assert LSTYLE_TO_MATPLOTLIB[3] == "--"
    assert LSTYLE_TO_MATPLOTLIB[2] == ":"


# --------------------------------------------------------------------------- #
# Every writer site that emits an lstyle token
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("linestyle,expected", EXPECTED.items())
def test_plot_line_emits_the_right_code(linestyle, expected):
    fig = glp.figure(data_prefix="lsp")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, linestyle=linestyle, color="black")
    assert _lstyles(_gle(fig)) == ([] if expected is None else [expected])


@pytest.mark.parametrize("linestyle,expected", EXPECTED.items())
def test_errorbar_with_marker_emits_the_right_code(linestyle, expected):
    fig = glp.figure(data_prefix="lse")
    ax = fig.add_subplot(111)
    ax.errorbar(X, Y, yerr=0.1, fmt=linestyle, marker="o", color="black")
    assert _lstyles(_gle(fig)) == ([] if expected is None else [expected])


@pytest.mark.parametrize("linestyle,expected", EXPECTED.items())
def test_errorbar_without_marker_emits_the_right_code(linestyle, expected):
    fig = glp.figure(data_prefix="lsn")
    ax = fig.add_subplot(111)
    ax.errorbar(X, Y, yerr=0.1, fmt=linestyle, color="black")
    assert _lstyles(_gle(fig)) == ([] if expected is None else [expected])


@pytest.mark.parametrize("linestyle,expected", EXPECTED.items())
def test_line_from_file_emits_the_right_code(linestyle, expected):
    fig = glp.figure(data_prefix="lsf")
    ax = fig.add_subplot(111)
    ax.line_from_file("external.dat", 1, 2, linestyle=linestyle, color="black")
    assert _lstyles(_gle(fig)) == ([] if expected is None else [expected])


def test_dash_dot_emits_exactly_one_lstyle_token():
    """Regression: add_plot_line used to append a stray hard-coded 'lstyle 4'
    after the configured dash-dot value, so '-.' silently rendered as GLE's
    sparse-dotted style and ignored the config entirely."""
    fig = glp.figure(data_prefix="lsdd")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, linestyle="-.", color="black")
    assert _lstyles(_gle(fig)) == [6]


# --------------------------------------------------------------------------- #
# Overrides still work
# --------------------------------------------------------------------------- #


def test_a_custom_style_config_is_honoured_everywhere():
    style = GLEStyleConfig(line_style_dashed=9, line_style_dotted=4, line_style_dashdot=7)
    fig = glp.figure(style=style, data_prefix="lsc")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, linestyle="--", color="black")
    ax.plot(X, Y + 1, linestyle=":", color="red")
    ax.plot(X, Y + 2, linestyle="-.", color="blue")
    assert _lstyles(_gle(fig)) == [9, 4, 7]


# --------------------------------------------------------------------------- #
# Guides and contours go through the same mapping
# --------------------------------------------------------------------------- #


def test_reference_lines_use_the_corrected_mapping():
    fig = glp.figure(data_prefix="lsg")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="black")
    ax.axhline(1.5, linestyle="--", color="gray")
    ax.axvline(1.0, linestyle=":", color="gray")
    assert _lstyles(_gle(fig)) == [3, 2]


def test_contour_linestyle_uses_the_corrected_mapping():
    from gleplot.axes import Axes

    assert Axes._linestyle_to_lstyle("--") == 3
    assert Axes._linestyle_to_lstyle(":") == 2
    assert Axes._linestyle_to_lstyle("-.") == 6
    # Solid deliberately yields None: no lstyle token at all (GLE's default).
    assert Axes._linestyle_to_lstyle("-") is None

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


#: Every call that draws a line from a ``linestyle`` keyword.
LINE_CALLS = {
    "plot": lambda ax, ls: ax.plot(X, Y, linestyle=ls),
    "step": lambda ax, ls: ax.step(X, Y, linestyle=ls),
    "stem": lambda ax, ls: ax.stem(X, Y, linestyle=ls),
    "errorbar": lambda ax, ls: ax.errorbar(X, Y, yerr=0.1, linestyle=ls),
    "axhline": lambda ax, ls: ax.axhline(1.5, linestyle=ls),
    "axvline": lambda ax, ls: ax.axvline(1.0, linestyle=ls),
    "line_from_file": lambda ax, ls: ax.line_from_file("f.dat", 1, 2, linestyle=ls),
    "hist": lambda ax, ls: ax.hist(Y, histtype="step", linestyle=ls),
}
NAMED = {"solid": None, "dashed": 3, "dotted": 2, "dashdot": 6}


@pytest.mark.parametrize("call", LINE_CALLS)
@pytest.mark.parametrize("name,expected", NAMED.items())
def test_matplotlib_line_style_names_draw_their_style(call, name, expected, recwarn):
    fig = glp.figure(data_prefix="lsn")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)  # gives the reference lines a range
    LINE_CALLS[call](ax, name)
    assert _lstyles(_gle(fig)) == ([] if expected is None else [expected])
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


@pytest.mark.parametrize("call", LINE_CALLS)
@pytest.mark.parametrize(
    "linestyle,match",
    [((0, (5, 2)), "dash pattern GLE cannot draw"), ("wavy", "not a line style")],
)
def test_a_style_gle_cannot_draw_warns_and_is_solid(call, linestyle, match):
    fig = glp.figure(data_prefix="lsw")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    with pytest.warns(UserWarning, match=f"{call}\\(\\) linestyle .*{match}"):
        LINE_CALLS[call](ax, linestyle)
    assert _lstyles(_gle(fig)) == []


def test_an_offset_with_no_dashes_is_a_silent_solid_line(recwarn):
    ax = glp.figure().add_subplot(111)
    ax.plot(X, Y, linestyle=(0, None))
    assert _lstyles(_gle(ax.figure)) == []
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_hist_warns_once_for_every_sample_set():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning) as record:
        ax.hist([[1.0, 2.0, 3.0], [1.0, 1.0, 2.0]], histtype="step", linestyle="wavy")
    assert sum("not a line style" in str(w.message) for w in record) == 1


@pytest.mark.parametrize("call", ["contour", "tricontour"])
def test_contour_line_style_names_draw_their_style(call):
    fig = glp.figure(data_prefix="lsc")
    ax = fig.add_subplot(111)
    if call == "contour":
        ax.contour([[0.0, 1.0], [1.0, 2.0]], linestyles="dashed")
    else:
        ax.tricontour(
            [0.0, 1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
            [0, 1, 1, 2],
            linestyles="dotted",
        )
    assert _lstyles(_gle(fig)) == ([3] if call == "contour" else [2])


@pytest.mark.parametrize("linestyle,expected", [("dashed", 3), ("wavy", 1)])
def test_a_reference_line_on_an_empty_axes_is_drawn(linestyle, expected, recwarn):
    # On an empty axes a reference line is drawn after the graph; an
    # unmapped style is drawn solid rather than vanishing.
    fig = glp.figure(data_prefix="lse")
    fig.add_subplot(111).axvline(0.5, linestyle=linestyle)
    style = f" lstyle {expected}" if expected != 1 else ""
    assert f"set color BLACK lwidth 0.05292{style}\ngraph_vline 0.5" in _gle(fig)


def test_dash_dot_emits_exactly_one_lstyle_token():
    """Regression: the line writer used to append a stray hard-coded 'lstyle 4'
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
    style = GLEStyleConfig(
        line_style_dashed=9, line_style_dotted=4, line_style_dashdot=7
    )
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


# --------------------------------------------------------------------------- #
# Line caps, joins and dash length (page-level 'set' commands)
# --------------------------------------------------------------------------- #


def _preamble(fig):
    """The lines between ``size`` and the blank line after ``set hei``."""
    lines = _gle(fig).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("size "))
    return lines[start + 1 : lines.index("", start + 1)]


def test_line_cap_join_and_dashlen_are_written_before_set_hei():
    style = GLEStyleConfig(line_cap="square", line_join="round", dashlen=0.1)
    fig = glp.figure(style=style)
    fig.add_subplot(111).plot(X, Y, linestyle="--")
    assert _preamble(fig) == [
        "set cap square",
        "set join round",
        "set dashlen 0.1",
        "set hei 0.42328",
    ]


def test_unset_line_cap_join_and_dashlen_write_nothing():
    fig = glp.figure()
    fig.add_subplot(111).plot(X, Y)
    assert _preamble(fig) == ["set hei 0.42328"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("line_cap", "projecting"),
        ("line_cap", "ROUND"),
        ("line_join", "miter"),
        ("dashlen", 0),
        ("dashlen", -0.1),
        ("dashlen", float("nan")),
    ],
)
def test_style_rejects_a_bad_line_end_value(field, value):
    with pytest.raises(ValueError, match=field):
        GLEStyleConfig(**{field: value})
    # Assigning later is checked too, and leaves the old value in place.
    style = GLEStyleConfig()
    with pytest.raises(ValueError, match=field):
        setattr(style, field, value)
    assert getattr(style, field) is None


@pytest.mark.parametrize(
    "field,value",
    [("line_cap", 1), ("line_join", 2), ("dashlen", "0.1"), ("dashlen", True)],
)
def test_style_rejects_a_line_end_value_of_the_wrong_type(field, value):
    with pytest.raises(TypeError, match=field):
        GLEStyleConfig(**{field: value})


def test_dashlen_accepts_any_real_number():
    assert _preamble_of(GLEStyleConfig(dashlen=np.float32(0.5))) == "set dashlen 0.5"
    assert _preamble_of(GLEStyleConfig(dashlen=1)) == "set dashlen 1"
    # Written in full, so a hand-written value survives a re-save.
    assert _preamble_of(GLEStyleConfig(dashlen=0.12345678)) == (
        "set dashlen 0.12345678"
    )


def _preamble_of(style):
    fig = glp.figure(style=style)
    fig.add_subplot(111).plot(X, Y)
    return _preamble(fig)[0]


def test_a_matching_per_series_keyword_is_honoured_silently(recwarn):
    fig = glp.figure(style=GLEStyleConfig(line_cap="round", line_join="bevel"))
    ax = fig.add_subplot(111)
    ax.plot(X, Y, solid_capstyle="round", solid_joinstyle="bevel")
    ax.plot(X, Y, linestyle="--", dash_capstyle="round", dash_joinstyle="bevel")
    # GLE's defaults, when the figure sets nothing, are butt caps and mitre joins.
    plain = glp.figure().add_subplot(111)
    plain.plot(X, Y, solid_capstyle="butt", solid_joinstyle="miter")
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_projecting_is_gle_square(recwarn):
    fig = glp.figure(style=GLEStyleConfig(line_cap="square"))
    fig.add_subplot(111).plot(X, Y, solid_capstyle="projecting")
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_a_differing_per_series_keyword_warns_and_changes_nothing():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.warns(UserWarning, match=r"solid_capstyle='round'.*line_cap='round'"):
        ax.plot(X, Y, solid_capstyle="round")
    with pytest.warns(UserWarning, match=r"dash_joinstyle='miter'.*line_join='mitre'"):
        glp.figure(style=GLEStyleConfig(line_join="round")).add_subplot(111).plot(
            X, Y, linestyle=":", dash_joinstyle="miter"
        )
    assert _preamble(fig) == ["set hei 0.42328"]


def test_keywords_for_the_other_kind_of_line_are_ignored(recwarn):
    """As in matplotlib: ``dash_*`` does not style a solid line, nor
    ``solid_*`` a dashed one, and neither styles a marker-only series."""
    ax = glp.figure().add_subplot(111)
    ax.plot(X, Y, dash_capstyle="round", dash_joinstyle="bevel")
    ax.plot(X, Y, linestyle="--", solid_capstyle="round")
    ax.plot(X, Y, linestyle="none", marker="o", solid_capstyle="round")
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


@pytest.mark.parametrize(
    "call",
    [
        lambda ax, **kw: ax.plot(X, Y, **kw),
        lambda ax, **kw: ax.axhline(0.5, **kw),
        lambda ax, **kw: ax.line_from_file("d.dat", 1, 2, **kw),
    ],
)
def test_linestyle_none_is_the_default_solid_line(call, recwarn):
    """matplotlib's ``None`` is the default style."""
    scripts = []
    for kw in ({}, {"linestyle": None}):
        ax = glp.figure(data_prefix="ls").add_subplot(111)
        call(ax, **kw)
        scripts.append(_gle(ax.figure))
    assert scripts[0] == scripts[1]
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_linestyle_none_takes_the_solid_line_keywords():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="solid_capstyle"):
        ax.plot(X, Y, linestyle=None, solid_capstyle="round")


@pytest.mark.parametrize("no_line", ["None", "none", "", " "])
def test_the_no_line_strings_still_draw_no_line(no_line):
    ax = glp.figure(data_prefix="ls").add_subplot(111)
    ax.plot(X, Y, linestyle=no_line, marker="o")
    ax.axhline(0.5, linestyle=no_line)
    assert ax.lines == [] and ax.scatters[0]["linestyle"] == no_line
    assert ax.reflines[0]["linestyle"] == no_line


def test_a_linestyle_drawn_solid_takes_the_solid_keywords():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning) as record:
        ax.plot(X, Y, linestyle="wavy", solid_capstyle="round")
    assert any("solid_capstyle" in str(w.message) for w in record)
    assert _lstyles(_gle(ax.figure)) == []


def test_a_named_dashed_style_takes_the_dash_keywords():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="dash_capstyle"):
        ax.plot(X, Y, linestyle="dashed", dash_capstyle="round")


def test_an_unknown_per_series_value_is_rejected_at_the_call():
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=r"solid_capstyle.*'square'"):
        ax.plot(X, Y, solid_capstyle="square")
    with pytest.raises(TypeError, match="dash_joinstyle"):
        ax.plot(X, Y, linestyle="--", dash_joinstyle=1)


# --------------------------------------------------------------------------- #
# matplotlib format strings on plot and errorbar
# --------------------------------------------------------------------------- #


def _same_script(draw_fmt, draw_keywords, recwarn):
    """The script a format string draws, and the one its keywords draw."""
    scripts = []
    for draw in (draw_fmt, draw_keywords):
        glp.close()
        fig = glp.figure(data_prefix="fmt")
        draw(fig.add_subplot(111))
        scripts.append(_gle(fig))
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
    return scripts


@pytest.mark.parametrize(
    "fmt, keywords",
    [
        ("ro", dict(color="r", marker="o", linestyle="none")),
        ("r--", dict(color="r", linestyle="--")),
        ("k:", dict(color="k", linestyle=":")),
        ("o", dict(marker="o", linestyle="none")),
        ("g", dict(color="g")),
        ("--s", dict(marker="s", linestyle="--")),
        ("C1-.", dict(color="C1", linestyle="-.")),
    ],
)
def test_plot_format_strings_draw_what_their_keywords_draw(fmt, keywords, recwarn):
    with_fmt, with_keywords = _same_script(
        lambda ax: ax.plot(X, Y, fmt),
        lambda ax: ax.plot(X, Y, **keywords),
        recwarn,
    )
    assert with_fmt == with_keywords


@pytest.mark.parametrize(
    "fmt, keywords",
    [
        ("ko", dict(color="k", marker="o", linestyle="none")),
        ("r--", dict(color="r", linestyle="--")),
        ("--o", dict(marker="o", linestyle="--")),
        ("", dict()),
    ],
)
def test_errorbar_format_strings_draw_what_their_keywords_draw(fmt, keywords, recwarn):
    with_fmt, with_keywords = _same_script(
        lambda ax: ax.errorbar(X, Y, yerr=0.1, fmt=fmt),
        lambda ax: ax.errorbar(X, Y, yerr=0.1, **keywords),
        recwarn,
    )
    assert with_fmt == with_keywords


def test_a_keyword_wins_over_the_format_string_with_a_warning():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="color is set by both color= and"):
        ax.plot(X, Y, "r", color="blue")
    assert ax.lines[0]["color"] == "BLUE"


def test_errorbar_fmt_none_draws_only_the_bars():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="marker='o' is not drawn"):
        ax.errorbar(X, Y, yerr=0.1, fmt="none", marker="o")
    series = ax.errorbars[0]
    assert series["marker"] is None and series["linestyle"] == "none"


def test_a_format_string_gleplot_cannot_draw_warns():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="format string gleplot can draw"):
        ax.plot(X, Y, "rq")
    with pytest.warns(UserWarning, match="format string gleplot can draw"):
        ax.errorbar(X, Y, yerr=0.1, fmt="red")


def test_a_linestyle_keyword_wins_over_the_format_in_plot_and_step():
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match="linestyle is set by both"):
        ax.plot(X, Y, "r--", ls=":")
    with pytest.warns(UserWarning, match="linestyle is set by both"):
        ax.step(X, Y, "r--", linestyle=":")
    assert [(s["color"], s["linestyle"]) for s in ax.lines] == [
        ("RED", ":"),
        ("RED", ":"),
    ]


def test_figure_plot_and_errorbar_forward_a_format_string():
    fig = glp.figure()
    fig.add_subplot(111)
    fig.plot(X, Y, "ro")
    fig.errorbar(X, Y, 0.1, None, "k--")
    ax = fig.gca()
    assert ax.scatters[0]["color"] == "RED"
    assert (ax.errorbars[0]["color"], ax.errorbars[0]["linestyle"]) == ("BLACK", "--")

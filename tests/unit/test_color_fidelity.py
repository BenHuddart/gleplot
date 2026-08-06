"""Requested colours must reach the GLE script exactly, never snapped.

``colors.rgb_to_gle`` used to map any hex string / RGB tuple onto one of about
eight named GLE colours by dominant channel. That silently substituted a
*different* colour: ``#8c8c8c`` and ``#999999`` (greys) both came out MAGENTA,
``#bbbbbb`` came out WHITE (invisible on a white page), and ``#9467bd``
(matplotlib's tab purple) came out MAGENTA -- so two distinct series could
collide onto one colour with nothing to warn the user.

GLE accepts ``rgb255(r,g,b)`` anywhere a colour name is accepted, so these
tests pin the replacement contract on the generated GLE text:

* a recognised GLE colour NAME (any case) still emits as that name;
* anything else emits as an exact ``rgb255(r,g,b)``;
* every emission context carries it -- lines, markers, error bars (including
  the bars-only ``color <c>`` path added for the errorbar-colour fix), bar
  fills, fill-between, contours, text, and the ``*_from_file`` series;
* the parser reads back what the writer emits, so colours survive a round trip.
"""

from __future__ import annotations

import re
import warnings

import numpy as np
import pytest

import gleplot as glp
from gleplot.colors import gle_color_to_rgb255, rgb_to_gle

#: The greys and purples from the original bug report, with the exact GLE
#: expression each must now emit.
REPORTED_COLORS = [
    ("#8c8c8c", "rgb255(140,140,140)"),  # was MAGENTA
    ("#999999", "rgb255(153,153,153)"),  # was MAGENTA
    ("#bbbbbb", "rgb255(187,187,187)"),  # was WHITE (invisible on white)
    ("#9467bd", "rgb255(148,103,189)"),  # matplotlib tab purple; was MAGENTA
]

#: matplotlib's default property cycle, by cycle reference and ``tab:`` name.
CYCLE_REFS = [f"C{i}" for i in range(10)]
TAB_NAMES = [
    "tab:blue",
    "tab:orange",
    "tab:green",
    "tab:red",
    "tab:purple",
    "tab:brown",
    "tab:pink",
    "tab:gray",
    "tab:olive",
    "tab:cyan",
]

#: Any GLE clause that introduces a colour value in the emitted script.
_COLOR_CLAUSE_RE = re.compile(
    r"\b(?:color|fill)\s+(rgb255\([^)]*\)|rgb\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)"
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig, tmp_path, name="f.gle"):
    gle_path = tmp_path / name
    fig.savefig_gle(str(gle_path))
    return gle_path.read_text(encoding="utf-8")


def _emitted_colors(script: str) -> list:
    """Every colour value the script assigns, in emission order."""
    return _COLOR_CLAUSE_RE.findall(script)


# --------------------------------------------------------------------------- #
# rgb_to_gle: the conversion contract
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("requested,expected", REPORTED_COLORS)
def test_reported_colors_convert_exactly(requested, expected):
    assert rgb_to_gle(requested) == expected


@pytest.mark.parametrize(
    "requested,expected",
    [
        ("red", "RED"),
        ("RED", "RED"),
        ("Blue", "BLUE"),
        ("b", "BLUE"),
        ("k", "BLACK"),
        ("darkblue", "DARKBLUE"),
        ("DARKGREEN", "DARKGREEN"),
        ("grey", "GRAY"),
        ("lightgrey", "LIGHTGRAY"),
        # Names GLE knows but gleplot's short list never did.
        ("salmon", "SALMON"),
        ("SteelBlue", "STEELBLUE"),
        ("gray30", "GRAY30"),
    ],
)
def test_named_colors_pass_through_as_names(requested, expected):
    assert rgb_to_gle(requested) == expected


@pytest.mark.parametrize(
    "requested,expected",
    [
        ((0.0, 0.0, 1.0), "rgb255(0,0,255)"),
        ((1.0, 0.0, 0.0), "rgb255(255,0,0)"),
        ((0.55, 0.4, 0.74), "rgb255(140,102,189)"),
        ([0.5, 0.5, 0.5], "rgb255(128,128,128)"),
        # Out-of-range components clamp rather than emit an invalid expression.
        ((-1.0, 0.5, 2.0), "rgb255(0,128,255)"),
        # Three-digit hex shorthand.
        ("#bbb", "rgb255(187,187,187)"),
        ("#1f77b4", "rgb255(31,119,180)"),
    ],
)
def test_non_name_colors_convert_to_exact_rgb255(requested, expected):
    assert rgb_to_gle(requested) == expected


@pytest.mark.parametrize(
    "expression",
    ["rgb255(140,140,140)", "rgb255(140, 140, 140)", "rgb(0.1,0.2,0.8)"],
)
def test_color_expressions_pass_through(expression):
    """Idempotence: a colour recovered from a script survives being re-converted.

    ``Figure.from_dict`` / the parser feed stored colours back through
    ``rgb_to_gle``, so an already-formed expression must not be mangled.
    """
    once = rgb_to_gle(expression)
    assert once == re.sub(r"\s+", "", expression)
    assert rgb_to_gle(once) == once


def test_unresolvable_color_still_falls_back_to_black():
    assert rgb_to_gle("definitely-not-a-colour") == "BLACK"
    assert rgb_to_gle("#12345") == "BLACK"


@pytest.mark.parametrize(
    "requested",
    ["definitely-not-a-colour", "#12345", "#zzzzzz"],
)
def test_unresolvable_color_warns_while_falling_back(requested):
    """No silent drops: an unrecognized name/hex string at least warns.

    ``rgb_to_gle`` used to swallow a typo'd or malformed colour into BLACK
    with no indication anything had happened -- the same failure mode
    ``markers.matplotlib_to_gle_marker`` already warns about for an
    unrecognized marker symbol.
    """
    with pytest.warns(UserWarning, match=re.escape(requested)):
        assert rgb_to_gle(requested) == "BLACK"


#: Every "grey"-spelled name that must map exactly like its "gray" form:
#: bare grey, the numbered ramp (GLE's ``defineOldGLEColors`` grey ramp,
#: matching the GRAY1..GRAY90 RGB values exactly), and named composites.
GREY_FAMILY = [
    "grey",
    "GREY",
    "Grey",
    "grey1",
    "grey5",
    "grey10",
    "grey20",
    "grey30",
    "grey40",
    "grey50",
    "grey60",
    "grey70",
    "grey80",
    "grey90",
    "darkgrey",
    "lightgrey",
]


@pytest.mark.parametrize("requested", GREY_FAMILY)
def test_grey_family_maps_to_gray_equivalent(requested):
    """British ``grey`` spellings must resolve exactly like their ``gray`` form.

    Regression test: ``rgb_to_gle('grey40')`` used to match nothing (only
    the bare ``gray``/``grey`` and ``lightgray``/``lightgrey`` pairs were in
    ``MATPLOTLIB_TO_GLE_COLORS``, and the numbered grey ramp -- ``grey10``..
    ``grey90`` -- was never checked at all) and fell through to the
    unrecognized-name fallback, silently turning a mid-grey into BLACK.
    """
    expected = requested.upper().replace("GREY", "GRAY")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert rgb_to_gle(requested) == expected
        # And the "gray" spelling resolves to the same token.
        assert (
            rgb_to_gle(requested.replace("grey", "gray").replace("GREY", "GRAY"))
            == expected
        )


def test_gle_color_to_rgb255_inverts_both_forms():
    assert gle_color_to_rgb255("rgb255(140,140,140)") == (140, 140, 140)
    assert gle_color_to_rgb255("rgb(0.0,0.0,1.0)") == (0, 0, 255)
    assert gle_color_to_rgb255("BLUE") == (0, 0, 255)
    assert gle_color_to_rgb255("not-a-colour") is None


# --------------------------------------------------------------------------- #
# No silent substitution in the generated script
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("requested,expected", REPORTED_COLORS)
def test_reported_colors_never_snap_in_the_script(requested, expected, tmp_path):
    """The exact expression is emitted and the snapped-to names are absent."""
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color=requested, label="s")
    script = _script(fig, tmp_path)

    assert expected in script
    emitted = _emitted_colors(script)
    assert "MAGENTA" not in emitted
    assert "WHITE" not in emitted


def test_two_close_greys_stay_distinct(tmp_path):
    """The reported collision: distinct series must keep distinct colours."""
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color="#8c8c8c", label="a")
    ax.plot([1, 2, 3], [3, 2, 1], color="#999999", label="b")
    ax.plot([1, 2, 3], [2, 2, 2], color="#bbbbbb", label="c")
    script = _script(fig, tmp_path)

    emitted = _emitted_colors(script)
    assert len(set(emitted)) == 3, emitted
    assert set(emitted) == {
        "rgb255(140,140,140)",
        "rgb255(153,153,153)",
        "rgb255(187,187,187)",
    }


@pytest.mark.parametrize("cycle", [CYCLE_REFS, TAB_NAMES], ids=["C0-C9", "tab-names"])
def test_matplotlib_default_cycle_emits_ten_distinct_colors(cycle, tmp_path):
    """All ten default-cycle colours must survive as ten different colours.

    Snapping collapsed the cycle onto a handful of names (C4 ``#9467bd`` and
    C6 ``#e377c2`` both became MAGENTA), so two series in a ten-series figure
    silently shared a colour.
    """
    fig = glp.figure()
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 6)
    for i, color in enumerate(cycle):
        ax.plot(x, x + i, color=color, label=f"s{i}")
    script = _script(fig, tmp_path)

    emitted = _emitted_colors(script)
    assert len(emitted) == 10
    assert len(set(emitted)) == 10, emitted
    assert all(c.startswith("rgb255(") for c in emitted), emitted


def test_hex_cycle_and_tab_names_agree(tmp_path):
    """``C4`` and ``tab:purple`` are the same colour, and it is the tab hex."""
    assert rgb_to_gle("C4") == rgb_to_gle("tab:purple") == rgb_to_gle("#9467bd")


# --------------------------------------------------------------------------- #
# Every emission context
# --------------------------------------------------------------------------- #


def _dataset_commands(script: str) -> list:
    """The ``dN <attributes>`` display commands, in emission order."""
    return [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]


def test_line_and_marker_contexts_carry_exact_color(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 6)
    ax.plot(x, x, color="#8c8c8c", label="line")
    ax.plot(x, x + 1, color="#9467bd", marker="o", label="line+marker")
    ax.plot(x, x + 2, color="#999999", marker="s", linestyle="none", label="marker")
    ax.scatter(x, x + 3, color="#bbbbbb", marker="D", label="scatter")
    script = _script(fig, tmp_path)

    cmds = _dataset_commands(script)
    assert " line " in cmds[0] and "color rgb255(140,140,140)" in cmds[0]
    assert " line " in cmds[1] and "color rgb255(148,103,189)" in cmds[1]
    assert "marker FSQUARE" in cmds[2] and "color rgb255(153,153,153)" in cmds[2]
    assert "color rgb255(187,187,187)" in cmds[3]


@pytest.mark.parametrize("capsize", [None, 0, 4])
def test_errorbar_bars_only_path_carries_exact_color(capsize, tmp_path):
    """The bars-only ``color <c>`` path (fmt='none') must carry rgb255 too.

    GLE draws error bars in the dataset's colour and an unstyled dataset
    renders black, so ``add_errorbar`` emits a bare ``color`` qualifier for a
    series with neither marker nor line. That qualifier must carry the exact
    colour, not a snapped name.
    """
    fig = glp.figure()
    ax = fig.add_subplot(111)
    kwargs = {} if capsize is None else {"capsize": capsize}
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, fmt="none", color="#8c8c8c", **kwargs)
    script = _script(fig, tmp_path)

    cmd = _dataset_commands(script)[0]
    assert re.search(r"\bcolor rgb255\(140,140,140\)", cmd), cmd
    assert re.search(r"\berr(?:up|down)? d\d+", cmd), cmd
    assert "MAGENTA" not in script


def test_errorbar_with_marker_and_line_carries_exact_color(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, color="#9467bd", marker="o", capsize=3)
    ax.errorbar([1, 2, 3], [3, 2, 1], yerr=0.2, color="#999999", linestyle="-")
    script = _script(fig, tmp_path)

    cmds = _dataset_commands(script)
    assert "color rgb255(148,103,189)" in cmds[0]
    assert "color rgb255(153,153,153)" in cmds[1]


def test_bar_fill_and_fill_between_carry_exact_color(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 6)
    ax.bar([1, 2, 3], [3, 5, 4], color="#bbbbbb")
    # alpha=0.4 (Track G6): the fill's colour is composed into rgba255(...)
    # (gleplot.colors.apply_alpha) -- 0.4 * 255 = 102 exactly.
    ax.fill_between(x, np.zeros_like(x), x, color="#999999", alpha=0.4)
    script = _script(fig, tmp_path)

    assert re.search(r"bar d\d+ fill rgb255\(187,187,187\)", script)
    assert re.search(r"fill d\d+,d\d+ color rgba255\(153,153,153,102\)", script)
    assert "WHITE" not in _emitted_colors(script)


def test_text_and_contour_carry_exact_color(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    y, x = np.mgrid[0:12, 0:14]
    ax.contour(
        np.sin(x / 4.0) * np.cos(y / 3.0),
        extent=(0, 10, 0, 8),
        levels=[-0.3, 0.3],
        colors="#9467bd",
    )
    ax.text(2.0, 2.0, "annotated", color="#8c8c8c", fontsize=12)
    script = _script(fig, tmp_path)

    assert "set color rgb255(140,140,140)" in script
    assert re.search(r"d\d+ line color rgb255\(148,103,189\)", script)


def test_file_series_contexts_carry_exact_color(tmp_path):
    data = tmp_path / "series.dat"
    data.write_text("1 2 0.1\n2 4 0.2\n3 6 0.3\n", encoding="utf-8")

    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.line_from_file(str(data), 1, 2, color="#8c8c8c", label="line")
    ax.errorbar_from_file(str(data), 1, 2, yerr_col=3, color="#9467bd", label="err")
    script = _script(fig, tmp_path)

    cmds = _dataset_commands(script)
    assert "line color rgb255(140,140,140)" in cmds[0]
    assert "color rgb255(148,103,189)" in cmds[1]


def test_named_colors_still_emit_as_names_in_the_script(tmp_path):
    fig = glp.figure()
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 6)
    ax.plot(x, x, color="red", label="r")
    ax.plot(x, x + 1, color="DarkBlue", label="db")
    ax.bar([1, 2], [1, 2], color="orange")
    ax.fill_between(x, np.zeros_like(x), x, color="lightblue")
    ax.text(1.0, 1.0, "t", color="green")
    script = _script(fig, tmp_path)

    emitted = _emitted_colors(script)
    for name in ("RED", "DARKBLUE", "ORANGE", "LIGHTBLUE", "GREEN"):
        assert name in emitted, emitted
    assert not any(c.startswith("rgb255(") for c in emitted), emitted


# --------------------------------------------------------------------------- #
# Parser round trip
# --------------------------------------------------------------------------- #


def test_round_trip_preserves_exact_colors(tmp_path):
    """open_gle must read back the rgb255 expressions the writer emits."""
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 6)
    ax.plot(x, x, color="#8c8c8c", label="line")
    ax.plot(x, x + 1, color="C4", marker="o", label="cycle")
    ax.plot(x, x + 2, color="darkred", label="named")
    ax.bar([1, 2, 3], [1, 2, 3], color="#bbbbbb")
    # alpha=0.4 (Track G6): the fill's colour is composed into rgba255(...)
    # (gleplot.colors.apply_alpha) -- 0.4 * 255 = 102 exactly -- and that
    # composed expression, not the plain rgb255 one, is what round-trips.
    ax.fill_between(x, np.zeros_like(x), x, color="#999999", alpha=0.4)
    ax.text(1.0, 1.0, "grey", color="#8c8c8c")
    first = _script(fig, tmp_path, "rt.gle")

    reopened = glp.open_gle(tmp_path / "rt.gle")
    rax = reopened.axes_list[0]

    assert rax.lines[0]["color"] == "rgb255(140,140,140)"
    assert rax.lines[1]["color"] == "rgb255(148,103,189)"
    assert rax.lines[2]["color"] == "DARKRED"
    assert rax.bars[0]["colors"][0] == "rgb255(187,187,187)"
    assert rax.fills[0]["color"] == "rgba255(153,153,153,102)"
    assert rax.texts[0]["color"] == "rgb255(140,140,140)"

    # ... and re-emitting is a fixed point.
    out_dir = tmp_path / "again"
    out_dir.mkdir()
    second = _script(reopened, out_dir, "rt.gle")
    assert second == first


def test_round_trip_of_a_hand_written_rgb255_script(tmp_path):
    """A colour expression a human typed is read as one value, not truncated.

    The lexer splits ``rgb255(140,140,140)`` into six tokens, so reading the
    single token after ``color`` would recover only ``rgb255`` and leave the
    components to be mis-scanned as further qualifiers. Whitespace inside the
    expression is normalised away, matching what the writer emits.
    """
    data = tmp_path / "hand.dat"
    data.write_text("1 1\n2 2\n3 3\n", encoding="utf-8")
    source = tmp_path / "hand.gle"
    source.write_text(
        "size 20 15\n"
        "begin graph\n"
        "   size 20 15\n"
        "   data hand.dat d1=c1,c2\n"
        "   d1 line color rgb255( 140 , 140 , 140 ) lwidth 0.05\n"
        "end graph\n",
        encoding="utf-8",
    )

    fig = glp.open_gle(source)
    # An externally-referenced .dat comes back as a reference-mode file series.
    series = fig.axes_list[0].file_series[0]
    assert series["color"] == "rgb255(140,140,140)"
    # The qualifier after the colour is still read correctly (0.05 cm -> pt).
    assert series["linewidth"] == pytest.approx(1.417, abs=1e-2)

"""Every errorbar dataset must carry its series colour.

GLE draws error bars -- and their caps -- in the *dataset's* colour, which is
only ever set by a ``color`` qualifier on the ``dN`` command; an unstyled
dataset falls back to black. ``Writer.add_errorbar`` used to emit ``color``
only from inside its marker branch or its line branch, so a bars-only series
(matplotlib's ``fmt="none"``) produced a bare ``dN err dM`` and rendered black
bars whatever colour was requested.

These tests pin the invariant on the generated GLE text: *no* emitted
errorbar command may reference ``err``/``errup``/``errdown``/``herr``/...
without also carrying a ``color``, for any dataset index, any capsize
(``capsize=0`` included) and both the in-memory and ``*_from_file`` paths.
"""

from __future__ import annotations

import re

import pytest

import gleplot as glp

#: Twelve requested colours -> the GLE names the writer must emit. More than
#: eight so a per-series assertion covers double-digit dataset indices
#: (``d17``, ``d19``, ... for the 9th series onwards), where the bug was first
#: noticed.
SERIES_COLORS = [
    ("red", "RED"),
    ("blue", "BLUE"),
    ("green", "GREEN"),
    ("magenta", "MAGENTA"),
    ("cyan", "CYAN"),
    ("orange", "ORANGE"),
    ("purple", "PURPLE"),
    ("brown", "BROWN"),
    ("pink", "PINK"),
    ("gray", "GRAY"),
    ("darkblue", "DARKBLUE"),
    ("darkgreen", "DARKGREEN"),
]

#: Any GLE qualifier that makes a dataset draw error bars.
_ERR_TOKENS = (
    "err",
    "errup",
    "errdown",
    "herr",
    "herrleft",
    "herrright",
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig, tmp_path):
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    return gle_path.read_text(encoding="utf-8")


def _dataset_commands(script: str) -> list[str]:
    """The ``dN <attributes>`` display commands, in emission order."""
    return [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]


def _errorbar_commands(script: str) -> list[str]:
    """Dataset commands that draw error bars."""
    out = []
    for cmd in _dataset_commands(script):
        words = cmd.split()[1:]
        if any(w in _ERR_TOKENS for w in words):
            out.append(cmd)
    return out


def _color_of(cmd: str) -> str | None:
    m = re.search(r"\bcolor\s+(\S+)", cmd)
    return m.group(1) if m else None


def _twelve_series_figure(**errorbar_kwargs):
    fig = glp.figure(figsize=(6, 12))
    ax = fig.add_subplot(111)
    for i, (requested, _expected) in enumerate(SERIES_COLORS):
        ax.errorbar(
            [1.0, 2.0, 3.0],
            [1.0 + i, 2.0 + i, 3.0 + i],
            yerr=[0.2, 0.3, 0.25],
            color=requested,
            label=f"s{i + 1}",
            **errorbar_kwargs,
        )
    return fig


# --------------------------------------------------------------------------- #
# Bars-only series (fmt="none") -- the regression
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("capsize", [0, 4])
def test_bars_only_series_colour_every_dataset(capsize, tmp_path):
    """12 bars-only series: each dataset carries its own requested colour."""
    fig = _twelve_series_figure(fmt="none", capsize=capsize)
    cmds = _errorbar_commands(_script(fig, tmp_path))

    assert len(cmds) == len(SERIES_COLORS)
    got = [_color_of(c) for c in cmds]
    assert got == [expected for _requested, expected in SERIES_COLORS]


@pytest.mark.parametrize("fmt", ["none", "None", "", " "])
def test_every_bars_only_fmt_spelling_emits_colour(fmt, tmp_path):
    """All of matplotlib's "no line, no marker" spellings keep the colour."""
    fig = glp.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, color="red", fmt=fmt, capsize=0)
    (cmd,) = _errorbar_commands(_script(fig, tmp_path))
    assert _color_of(cmd) == "RED"


def test_bars_only_capsize_zero_keeps_errwidth_and_colour(tmp_path):
    """``capsize=0`` still emits ``errwidth 0`` alongside the colour."""
    fig = glp.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, color="green", fmt="none", capsize=0)
    (cmd,) = _errorbar_commands(_script(fig, tmp_path))
    assert "errwidth 0" in cmd
    assert _color_of(cmd) == "GREEN"


def test_bars_only_asymmetric_and_horizontal_errors_carry_colour(tmp_path):
    """``errup``/``errdown``/``herr`` bars are coloured too."""
    fig = glp.figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.errorbar(
        [1, 2, 3],
        [1, 2, 3],
        yerr=([0.1, 0.1, 0.1], [0.3, 0.3, 0.3]),
        xerr=0.2,
        color="magenta",
        fmt="none",
        capsize=0,
    )
    (cmd,) = _errorbar_commands(_script(fig, tmp_path))
    assert "errup" in cmd and "errdown" in cmd and "herr" in cmd
    assert _color_of(cmd) == "MAGENTA"


# --------------------------------------------------------------------------- #
# The marker / line branches must stay coloured as well
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("capsize", [0, 4])
@pytest.mark.parametrize("fmt,marker", [("o", "o"), ("-", None), ("-o", None)])
def test_marker_and_line_series_colour_every_dataset(capsize, fmt, marker, tmp_path):
    """Marker-only, line-only and line+marker series, 12 deep, stay coloured."""
    kwargs = {"fmt": fmt, "capsize": capsize}
    if marker is not None:
        kwargs["marker"] = marker
    fig = _twelve_series_figure(**kwargs)
    cmds = _errorbar_commands(_script(fig, tmp_path))

    assert len(cmds) == len(SERIES_COLORS)
    got = [_color_of(c) for c in cmds]
    assert got == [expected for _requested, expected in SERIES_COLORS]


# --------------------------------------------------------------------------- #
# errorbar_from_file shares the invariant
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("capsize", [0, 4])
@pytest.mark.parametrize("marker", ["o", None])
def test_errorbar_from_file_colours_every_dataset(capsize, marker, tmp_path):
    fig = glp.figure(figsize=(6, 12))
    ax = fig.add_subplot(111)
    for i, (requested, _expected) in enumerate(SERIES_COLORS):
        ax.errorbar_from_file(
            "measured.dat",
            x_col=1,
            y_col=2 + i,
            yerr_col=3 + i,
            color=requested,
            marker=marker,
            capsize=capsize,
            label=f"s{i + 1}",
        )
    cmds = _errorbar_commands(_script(fig, tmp_path))

    assert len(cmds) == len(SERIES_COLORS)
    got = [_color_of(c) for c in cmds]
    assert got == [expected for _requested, expected in SERIES_COLORS]


# --------------------------------------------------------------------------- #
# Blanket invariant: no errorbar dataset may fall back to GLE's default style
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("capsize", [0, 4, None])
@pytest.mark.parametrize("fmt", ["none", "o", "-", "-o"])
def test_no_errorbar_dataset_is_left_unstyled(capsize, fmt, tmp_path):
    kwargs = {"fmt": fmt, "capsize": capsize}
    if fmt == "o":
        kwargs["marker"] = "o"
    fig = _twelve_series_figure(**kwargs)
    script = _script(fig, tmp_path)

    uncoloured = [c for c in _errorbar_commands(script) if _color_of(c) is None]
    assert (
        uncoloured == []
    ), "these errorbar datasets carry no colour and would render black:\n" + "\n".join(
        uncoloured
    )

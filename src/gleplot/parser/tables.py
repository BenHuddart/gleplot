"""Reference tables shared by the GLE writer and the (forthcoming) GLE parser.

All lookup tables that a parser must invert live here in one place:

- ``COLORS`` / color helpers: transcribed from GLE 4.3.10's
  ``src/gle/color.cpp`` (``defineDefaultColors`` -> ``defineGrays`` +
  ``defineSVGColors``) and the hex literals in ``src/gle/color.h``, i.e. the
  151 names GLE recognizes out of the box (SVG named colors plus the
  ``GRAY1``..``GRAY90`` grayscale ramp). The legacy ``defineOldGLEColors``
  table (old GLE color names like ``BAKERS_CHOCOLATE``) is intentionally
  *not* included -- gleplot's writer never emits those names.
- ``MARKERS`` / ``GLE_MARKER_TO_MATPLOTLIB``: transcribed from GLE 4.3.10's
  ``src/gle/pass.cpp`` (the ``stdmark[]`` array, lines ~2371-2468). The
  matplotlib-facing inverse map is derived programmatically from
  :data:`gleplot.markers.MATPLOTLIB_TO_GLE_MARKERS` so the two can never
  drift apart.
- ``LSTYLE_TO_MATPLOTLIB`` / ``MATPLOTLIB_TO_LSTYLE``: GLE ``lstyle`` integer
  <-> matplotlib linestyle string, derived programmatically from the
  ``line_style_*`` fields of ``GLEStyleConfig`` -- the same fields
  ``GLEWriter.add_line``/``add_errorbar_series``/``add_file_series``
  read when emitting -- so the parser's inverse cannot drift from the
  writer's forward choice. Also consumed by ``Axes.errorbar``'s ``fmt``
  parsing.
- ``KEY_POSITIONS``: long-form <-> short-form GLE legend position, mirroring
  ``GLEWriter.add_legend``'s ``pos_map`` and ``Axes.legend``'s ``loc_map``.
- ``LEGEND_SPACING_TO_KEY`` / ``KEY_ANCHOR_X`` / ``KEY_ANCHOR_Y``: the legend
  spacing keywords and the ``begin key`` ``absolute`` coordinates the writer
  emits for ``legend(bbox_to_anchor=...)``.

Provenance is documented per table below.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .. import markers as _markers

# The raw GLE name tables live with the modules that own the forward
# mappings; they are re-exported here so the parser has one place to look.
from ..colors import COLORS, gle_color_rgb, nearest_gle_color
from ..config import GLEStyleConfig
from ..markers import MARKERS
from ..palettes import SUPPORTED_CMAPS, canonical_cmap, cmap_needs_sub

__all__ = [
    "COLORS",
    "gle_color_rgb",
    "nearest_gle_color",
    "MARKERS",
    "GLE_MARKER_TO_MATPLOTLIB",
    "LSTYLE_TO_MATPLOTLIB",
    "MATPLOTLIB_TO_LSTYLE",
    "LINE_MODES",
    "DRAWSTYLE_TO_LINE_MODE",
    "resolve_line_mode",
    "NUMBER_FORMAT_KEYWORDS",
    "KEY_POSITIONS_LONG_TO_SHORT",
    "KEY_POSITIONS_SHORT_TO_LONG",
    "TEXT_HA_VALUES",
    "TEXT_VA_VALUES",
    "TEXT_BOX_PAD_CM",
    "text_align_to_just",
    "text_box_pad_token",
    "text_just_to_align",
    "PALETTE_SUB_TO_CMAP",
    "CMAP_TO_PALETTE_SUB",
]


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------


def _build_gle_marker_to_matplotlib() -> Dict[str, str]:
    """Invert :data:`gleplot.markers.MATPLOTLIB_TO_GLE_MARKERS`.

    Built programmatically (rather than hand-transcribed) so the parser's
    GLE->matplotlib marker map can never drift out of sync with the writer's
    matplotlib->GLE map in ``gleplot.markers``.

    Several matplotlib codes map to the same GLE name (e.g. ``'<'`` and
    ``'>'`` both map to ``'TRIANGLE'``; ``'+'``/``'P'``/``'|'``/``'_'`` all
    map to ``'PLUS'``; ``'x'``/``'X'`` both map to ``'PCROSS'``;
    ``'.'``/``','`` both map to ``'DOT'``). For each such GLE name, the
    *first* matplotlib code encountered in
    ``MATPLOTLIB_TO_GLE_MARKERS`` (dict iteration / insertion order) is kept
    as the canonical inverse -- i.e. the earliest-defined mpl code for that
    GLE name in ``gleplot/markers.py`` wins:

    - ``'<'`` (not ``'>'``) is canonical for ``TRIANGLE``
    - ``'+'`` (not ``'P'``, ``'|'``, ``'_'``) is canonical for ``PLUS``
    - ``'x'`` (not ``'X'``) is canonical for ``PCROSS``
    - ``'.'`` (not ``','``) is canonical for ``DOT``
    """
    inverse: Dict[str, str] = {}
    for mpl_code, gle_name in _markers.MATPLOTLIB_TO_GLE_MARKERS.items():
        if gle_name not in inverse:
            inverse[gle_name] = mpl_code
    return inverse


GLE_MARKER_TO_MATPLOTLIB: Dict[str, str] = _build_gle_marker_to_matplotlib()


# ---------------------------------------------------------------------------
# Line styles
# ---------------------------------------------------------------------------
#
# GLE ``lstyle`` integer <-> matplotlib linestyle string.
#
# DERIVED from ``GLEStyleConfig``'s defaults rather than transcribed, for the
# same reason ``GLE_MARKER_TO_MATPLOTLIB`` is: the writer emits ``lstyle
# {style.line_style_dashed}`` for ``'--'``, ``{...dotted}`` for ``':'`` and
# ``{...dashdot}`` for ``'-.'`` (see ``GLEWriter.add_line`` /
# ``add_errorbar_series`` / ``add_file_series``), so building the parser's
# inverse from the very same fields makes it impossible for the two to drift
# apart. They previously did: the config said dashed=2/dotted=3 while GLE
# 4.3.10 renders 2 as dotted and 3 as dashed, and this table faithfully
# reproduced the transposition on the way back in.
#
# Solid lines (``'-'``) never emit an ``lstyle`` token at all (GLE's default
# is style 1), but the pair is still listed so a hand-written ``lstyle 1``
# round-trips. The reverse map is also used by ``Axes.errorbar``'s ``fmt``
# parsing and by ``Axes._linestyle_to_lstyle`` for contour lines; it
# recognizes exactly ``'-'``, ``'--'``, ``':'``, ``'-.'``.
#
# NOTE: this is a module-level constant keyed off the *default* config. A
# figure that overrides ``line_style_dashed`` etc. will emit numbers this
# table cannot invert -- a pre-existing limitation of parsing without the
# producing config in hand.
def _build_lstyle_to_matplotlib() -> Dict[int, str]:
    """Invert the writer's linestyle -> ``lstyle`` choice, from the defaults."""
    defaults = GLEStyleConfig()
    return {
        defaults.line_style_solid: "-",
        defaults.line_style_dashed: "--",
        defaults.line_style_dotted: ":",
        defaults.line_style_dashdot: "-.",
    }


LSTYLE_TO_MATPLOTLIB: Dict[int, str] = _build_lstyle_to_matplotlib()

MATPLOTLIB_TO_LSTYLE: Dict[str, int] = {v: k for k, v in LSTYLE_TO_MATPLOTLIB.items()}


# ---------------------------------------------------------------------------
# Dataset line modes
# ---------------------------------------------------------------------------
#
# GLE 4.3.10 ``src/gle/graph2.cpp`` ``do_dataset``: ``STEPS``, ``FSTEPS``,
# ``HIST``, ``BAR`` and ``IMPULSES`` each assign ``dp[d]->line_mode`` (the
# last keyword wins). After the keyword loop, any non-plain mode sets
# ``line = true`` even when the ``line`` keyword itself was omitted.
#
# Drawing (``do_draw_*`` in the same file, and the manual's line-mode list):
#   steps     (x1,y1) -> (x2,y1) -> (x2,y2)   horizontal, then vertical
#   fsteps    (x1,y1) -> (x1,y2) -> (x2,y2)   vertical, then horizontal
#   hist      each point is the center of a bin
#   bar       hist, plus a separator down to the impulse origin
#   impulses  a vertical from the impulse origin to each point
#
# matplotlib's step drawstyles land on the first three. ``impulses`` is
# ``Axes.stem``. ``bar`` is this per-dataset line mode, not the graph-level
# ``bar`` command :meth:`Axes.bar` emits.
#   steps / steps-pre / where="pre"   -> fsteps
#   steps-post        / where="post"  -> steps
#   steps-mid         / where="mid"   -> hist

LINE_MODES: Tuple[str, ...] = ("steps", "fsteps", "hist", "bar", "impulses")

#: matplotlib ``drawstyle`` → GLE line mode. ``None`` is a plain polyline,
#: so the writer keeps emitting a bare ``line`` and old scripts stay
#: byte-identical. Keys are matplotlib's own spellings (case-sensitive).
DRAWSTYLE_TO_LINE_MODE: Dict[str, Optional[str]] = {
    "default": None,
    "steps": "fsteps",
    "steps-pre": "fsteps",
    "steps-post": "steps",
    "steps-mid": "hist",
}


def resolve_line_mode(
    drawstyle: Optional[str] = None,
    line_mode: Optional[str] = None,
    ds: Optional[str] = None,
) -> Optional[str]:
    """The GLE line mode for a plot call, or ``None`` for a plain polyline.

    ``ds`` is matplotlib's alias of ``drawstyle``. ``line_mode`` is the GLE
    token itself (see :data:`LINE_MODES`). When a drawstyle and a
    ``line_mode`` are both given they must name the same mode.
    """
    if ds is not None:
        if drawstyle is None:
            drawstyle = ds
        elif _drawstyle_mode(ds) != _drawstyle_mode(drawstyle):
            raise ValueError(
                f"drawstyle {drawstyle!r} and ds {ds!r} are different line modes"
            )
    from_style = _drawstyle_mode(drawstyle)
    if line_mode is None:
        return from_style
    mode = str(line_mode).strip().lower()
    if mode not in LINE_MODES:
        raise ValueError(f"line_mode must be one of {LINE_MODES}, got {line_mode!r}")
    if from_style is not None and from_style != mode:
        raise ValueError(
            f"drawstyle {drawstyle!r} is GLE {from_style!r}, "
            f"which disagrees with line_mode {line_mode!r}"
        )
    return mode


def _drawstyle_mode(drawstyle: Optional[str]) -> Optional[str]:
    if drawstyle is None:
        return None
    key = str(drawstyle).strip()
    try:
        return DRAWSTYLE_TO_LINE_MODE[key]
    except KeyError:
        known = ", ".join(repr(name) for name in DRAWSTYLE_TO_LINE_MODE)
        raise ValueError(
            f"drawstyle must be one of {known}, got {drawstyle!r}"
        ) from None


# ---------------------------------------------------------------------------
# Number-format keywords
# ---------------------------------------------------------------------------
#
# Every specifier GLE's number-format parser understands, transcribed from
# GLE 4.3.10 ``src/gle/numberformat.cpp``, ``GLENumberFormat::GLENumberFormat``
# (the ``if (name == ...)`` chain) -- the code behind both ``format$(x, fmt)``
# and the graph block's ``xaxis format "<fmt>"``. Documented in the manual
# under ``format$`` ("Programming"), which omits ``nozero``, ``add`` and
# ``otherwise``; the source is authoritative and they are included here.
#
# GLE does NOT abort on an unrecognized specifier -- it prints "Unknown
# specifier in number format string" and skips it -- so this table is used
# only for a light "did you mean a format string at all?" check
# (:func:`gleplot.axes.validate_tick_format`), never to reject arguments.
NUMBER_FORMAT_KEYWORDS: Tuple[str, ...] = (
    # Base formats (each starts a new format in the chain).
    "fix",
    "percent",
    "dec",
    "hex",
    "bin",
    "round",
    "sci",
    "eng",
    "frac",
    "pi",
    # Modifiers of the preceding format.
    "prefix",
    "nozeroes",
    "nozero",
    "sign",
    "pad",
    "min",
    "max",
    "append",
    "add",
    "prepend",
    "otherwise",
)


# ---------------------------------------------------------------------------
# Legend / key positions
# ---------------------------------------------------------------------------
#
# Long-form <-> short-form GLE legend position, mirroring
# ``GLEWriter.add_legend``'s ``pos_map`` (long -> short; falls through to the
# value as-is if already short-form) and
# ``gleplot.axes.MATPLOTLIB_TO_GLE_LEGEND_LOC`` (matplotlib ``loc`` ->
# gleplot's long form, which ``add_legend`` then maps to short form). All nine
# GLE key anchors are reachable from a matplotlib ``loc``, so all nine appear
# here.
KEY_POSITIONS_LONG_TO_SHORT: Dict[str, str] = {
    "top right": "tr",
    "top left": "tl",
    "top center": "tc",
    "bottom right": "br",
    "bottom left": "bl",
    "bottom center": "bc",
    "left center": "lc",
    "right center": "rc",
    "center": "cc",
}

# matplotlib legend spacing keyword -> GLE key option, in emission order. Both
# sides measure a length; matplotlib's in units of the legend font size, GLE's
# in cm, so the writer multiplies by the key text height. ``margins`` takes an
# x and a y; matplotlib's ``borderpad`` is one value for both.
LEGEND_SPACING_TO_KEY: Dict[str, str] = {
    "handlelength": "llen",
    "handletextpad": "dist",
    "columnspacing": "coldist",
    "borderpad": "margins",
}

# A ``begin key`` ``absolute`` coordinate for an axes fraction ``{}`` of the
# graph that has just ended. ``min``/``abs`` keep fraction 0 at the left
# (bottom) of the box on a ``negate`` axis, as matplotlib's axes coordinates do.
KEY_ANCHOR_X = "min(xg(xgmin),xg(xgmax))+{}*abs(xg(xgmax)-xg(xgmin))"
KEY_ANCHOR_Y = "min(yg(ygmin),yg(ygmax))+{}*abs(yg(ygmax)-yg(ygmin))"

# ---------------------------------------------------------------------------
# Palette subroutine names (contour/heatmap support)
# ---------------------------------------------------------------------------
#
# gleplot emits self-contained palette subroutines named ``gleplot_<name>``
# (see :mod:`gleplot.palettes`). The recognizer maps a ``colormap ... palette
# gleplot_<name>`` clause back to the canonical cmap name via this table (and
# treats any OTHER palette sub name as an unknown/foreign palette -> passthrough
# with a warning). It is built from ``gleplot.palettes.SUPPORTED_CMAPS``: every
# palette that requires an emitted sub. ``gray``/``rainbow`` need no sub and
# never appear as a ``palette`` clause (grayscale = no clause; rainbow = the
# ``color`` switch).
PALETTE_SUB_TO_CMAP: Dict[str, str] = {
    f"gleplot_{c}": c for c in map(canonical_cmap, SUPPORTED_CMAPS) if cmap_needs_sub(c)
}

CMAP_TO_PALETTE_SUB: Dict[str, str] = {v: k for k, v in PALETTE_SUB_TO_CMAP.items()}


KEY_POSITIONS_SHORT_TO_LONG: Dict[str, str] = {
    v: k for k, v in KEY_POSITIONS_LONG_TO_SHORT.items()
}


# ---------------------------------------------------------------------------
# Free-form text justification (``set just``)
# ---------------------------------------------------------------------------
#
# GLE's ``set just`` is one word or a two-letter code. The two-letter form is
# vertical then horizontal: ``t``/``c``/``b`` × ``l``/``c``/``r`` (manual,
# ``set just``: the ``tl tc tr / lc cc rc / bl bc br`` grid).
#
# The single-word forms are the vertically-centred row, not the baseline and
# not the bottom. Measured on GLE 4.3.10: ``set just left`` puts the current
# point on the vertical centre of the text, the same place as ``lc``; ``center``
# and ``right`` match ``cc`` and ``rc``. gleplot therefore emits the single
# word whenever ``va`` is ``center``, which is what every script written before
# vertical alignment was emitted already said.

TEXT_HA_VALUES: Tuple[str, ...] = ("left", "center", "right")
TEXT_VA_VALUES: Tuple[str, ...] = ("top", "center", "bottom")

_HA_LETTER = {"left": "l", "center": "c", "right": "r"}
_VA_LETTER = {"top": "t", "center": "c", "bottom": "b"}
_CENTERED_JUST = {"l": "left", "c": "center", "r": "right"}

#: ``set just`` token -> ``(ha, va)``. Includes the single-word aliases of the
#: centred row so a hand-written ``lc`` recovers the same alignment as ``left``.
_JUST_TO_ALIGN: Dict[str, Tuple[str, str]] = {
    "left": ("left", "center"),
    "center": ("center", "center"),
    "right": ("right", "center"),
    "tl": ("left", "top"),
    "tc": ("center", "top"),
    "tr": ("right", "top"),
    "lc": ("left", "center"),
    "cc": ("center", "center"),
    "rc": ("right", "center"),
    "bl": ("left", "bottom"),
    "bc": ("center", "bottom"),
    "br": ("right", "bottom"),
}


def text_align_to_just(ha: str, va: str) -> str:
    """GLE ``set just`` token for a matplotlib ``ha``/``va`` pair.

    An unknown ``va`` is treated as ``center`` and an unknown ``ha`` as
    ``left``, so a restored annotation keeps whichever half is valid.
    ``Axes.text`` already stores those fallbacks, but ``Figure.from_dict``
    writes the dict straight through. ``va='center'`` uses the single-word
    form (``left``/``center``/``right``) so a default annotation stays
    byte-identical to one emitted before ``va`` was written.
    """
    hl = _HA_LETTER.get(str(ha).strip().lower(), "l")
    vl = _VA_LETTER.get(str(va).strip().lower(), "c")
    if vl == "c":
        return _CENTERED_JUST[hl]
    return vl + hl


#: Margin, in cm, that ``begin box add`` puts around a text background.
#: GLE sizes the box from the ink inside the block; 0.05 cm is the pad
#: ``contour_labels`` in ``contour.gle`` uses. Not a model field: every box
#: gleplot draws uses :func:`text_box_pad_token`, and a hand-written box
#: whose ``add`` token is anything else stays unrecognized.
TEXT_BOX_PAD_CM = 0.05


def text_box_pad_token() -> str:
    """The ``add`` spelling written for :data:`TEXT_BOX_PAD_CM`.

    Same cut as ``GLEWriter._format_number`` for a modest positive number
    (``f"{value:.6g}"``). The recognizer accepts only this token, so a pad
    spelled any other way is not rewritten to this one.
    """
    return f"{TEXT_BOX_PAD_CM:.6g}"


def text_just_to_align(just: str) -> Optional[Tuple[str, str]]:
    """``(ha, va)`` for a ``set just`` token, or ``None`` if it is not one.

    The return is the matplotlib pair gleplot stores. ``left`` and ``lc`` both
    come back as ``('left', 'center')``, and re-emission uses
    :func:`text_align_to_just`, which writes the single word.
    """
    return _JUST_TO_ALIGN.get(str(just).strip().lower())


# -- annotation arrows ------------------------------------------------------
#
# ``Axes.annotate`` draws its arrow with ``join`` from the text's named box to
# a ``save``d point at ``xy``, so GLE clips the start at the box edge (the
# matplotlib ``patchA`` behaviour) instead of drawing over the text. The
# separator is the head placement; ``set arrowstyle`` is the tip shape.
# GLE's own default style is ``filled`` (core.cpp ``g.arrowstyle``), so the
# writer always states it.

#: GLE ``join`` separators: ``-`` is a bare line.
ARROW_JOIN_SEPS: Tuple[str, ...] = ("->", "<-", "<->", "-")
#: GLE ``set arrowstyle`` values gleplot writes.
ARROW_TIP_STYLES: Tuple[str, ...] = ("simple", "filled")

#: matplotlib ``arrowprops['arrowstyle']`` -> ``(join separator, tip style)``.
#: Open heads (``->``) are GLE ``simple``, triangle heads (``-|>``) ``filled``.
MPL_ARROWSTYLE_TO_GLE: Dict[str, Tuple[str, Optional[str]]] = {
    "-": ("-", None),
    "->": ("->", "simple"),
    "<-": ("<-", "simple"),
    "<->": ("<->", "simple"),
    "-|>": ("->", "filled"),
    "<|-": ("<-", "filled"),
    "<|-|>": ("<->", "filled"),
}

#: GLE ``xlabels log`` modes: which sub-decades of a log axis get a label
#: (``graph.cpp`` ``do_labels``).
LOG_LABEL_MODES: Tuple[str, ...] = ("off", "l1", "l25", "l25b", "n1")

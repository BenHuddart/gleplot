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
  <-> matplotlib linestyle string, as actually emitted by
  ``GLEWriter.add_plot_line``/``add_errorbar``/``add_plot_line_from_file``
  (which read ``style.line_style_dashed`` etc. -- default 2/3/4 -- from
  ``GLEStyleConfig``) and consumed by ``Axes.errorbar``'s ``fmt`` parsing.
- ``KEY_POSITIONS``: long-form <-> short-form GLE legend position, mirroring
  ``GLEWriter.add_legend``'s ``pos_map`` and ``Axes.legend``'s ``loc_map``.

Provenance is documented per table below.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .. import markers as _markers

__all__ = [
    "COLORS",
    "gle_color_rgb",
    "nearest_gle_color",
    "MARKERS",
    "GLE_MARKER_TO_MATPLOTLIB",
    "LSTYLE_TO_MATPLOTLIB",
    "MATPLOTLIB_TO_LSTYLE",
    "KEY_POSITIONS_LONG_TO_SHORT",
    "KEY_POSITIONS_SHORT_TO_LONG",
    "PALETTE_SUB_TO_CMAP",
    "CMAP_TO_PALETTE_SUB",
]


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
#
# Transcribed from GLE 4.3.10 ``src/gle/color.cpp`` lines ~131-299
# (``GLEColorList::defineGrays`` + ``GLEColorList::defineSVGColors``, called
# from ``defineDefaultColors``), with RGB values decoded from the
# ``0x01RRGGBB``-format hex literals in ``src/gle/color.h`` lines 66-218
# (the leading ``0x01`` byte is GLE's internal "color defined" flag, not part
# of the RGB value). Keys are the canonical uppercase GLE color names as
# ``defineColor`` registers them; GLE itself is case-insensitive.
COLORS: Dict[str, Tuple[int, int, int]] = {
    "ALICEBLUE": (240, 248, 255),
    "ANTIQUEWHITE": (250, 235, 215),
    "AQUA": (0, 255, 255),
    "AQUAMARINE": (127, 255, 212),
    "AZURE": (240, 255, 255),
    "BEIGE": (245, 245, 220),
    "BISQUE": (255, 228, 196),
    "BLACK": (0, 0, 0),
    "BLANCHEDALMOND": (255, 235, 205),
    "BLUE": (0, 0, 255),
    "BLUEVIOLET": (138, 43, 226),
    "BROWN": (165, 42, 42),
    "BURLYWOOD": (222, 184, 135),
    "CADETBLUE": (95, 158, 160),
    "CHARTREUSE": (127, 255, 0),
    "CHOCOLATE": (210, 105, 30),
    "CORAL": (255, 127, 80),
    "CORNFLOWERBLUE": (100, 149, 237),
    "CORNSILK": (255, 248, 220),
    "CRIMSON": (220, 20, 60),
    "CYAN": (0, 255, 255),
    "DARKBLUE": (0, 0, 139),
    "DARKCYAN": (0, 139, 139),
    "DARKGOLDENROD": (184, 134, 11),
    "DARKGRAY": (169, 169, 169),
    "DARKGREEN": (0, 100, 0),
    "DARKKHAKI": (189, 183, 107),
    "DARKMAGENTA": (139, 0, 139),
    "DARKOLIVEGREEN": (85, 107, 47),
    "DARKORANGE": (255, 140, 0),
    "DARKORCHID": (153, 50, 204),
    "DARKRED": (139, 0, 0),
    "DARKSALMON": (233, 150, 122),
    "DARKSEAGREEN": (143, 188, 143),
    "DARKSLATEBLUE": (72, 61, 139),
    "DARKSLATEGRAY": (47, 79, 79),
    "DARKTURQUOISE": (0, 206, 209),
    "DARKVIOLET": (148, 0, 211),
    "DEEPPINK": (255, 20, 147),
    "DEEPSKYBLUE": (0, 191, 255),
    "DIMGRAY": (105, 105, 105),
    "DODGERBLUE": (30, 144, 255),
    "FIREBRICK": (178, 34, 34),
    "FLORALWHITE": (255, 250, 240),
    "FORESTGREEN": (34, 139, 34),
    "FUCHSIA": (255, 0, 255),
    "GAINSBORO": (220, 220, 220),
    "GHOSTWHITE": (248, 248, 255),
    "GOLD": (255, 215, 0),
    "GOLDENROD": (218, 165, 32),
    "GRAY": (128, 128, 128),
    "GRAY1": (253, 253, 253),
    "GRAY10": (200, 200, 200),
    "GRAY20": (175, 175, 175),
    "GRAY30": (150, 150, 150),
    "GRAY40": (125, 125, 125),
    "GRAY5": (240, 240, 240),
    "GRAY50": (100, 100, 100),
    "GRAY60": (75, 75, 75),
    "GRAY70": (50, 50, 50),
    "GRAY80": (25, 25, 25),
    "GRAY90": (6, 6, 6),
    "GREEN": (0, 128, 0),
    "GREENYELLOW": (173, 255, 47),
    "HONEYDEW": (240, 255, 240),
    "HOTPINK": (255, 105, 180),
    "INDIANRED": (205, 92, 92),
    "INDIGO": (75, 0, 130),
    "IVORY": (255, 255, 240),
    "KHAKI": (240, 230, 140),
    "LAVENDER": (230, 230, 250),
    "LAVENDERBLUSH": (255, 240, 245),
    "LAWNGREEN": (124, 252, 0),
    "LEMONCHIFFON": (255, 250, 205),
    "LIGHTBLUE": (173, 216, 230),
    "LIGHTCORAL": (240, 128, 128),
    "LIGHTCYAN": (224, 255, 255),
    "LIGHTGOLDENRODYELLOW": (250, 250, 210),
    "LIGHTGRAY": (211, 211, 211),
    "LIGHTGREEN": (144, 238, 144),
    "LIGHTPINK": (255, 182, 193),
    "LIGHTSALMON": (255, 160, 122),
    "LIGHTSEAGREEN": (32, 178, 170),
    "LIGHTSKYBLUE": (135, 206, 250),
    "LIGHTSLATEGRAY": (119, 136, 153),
    "LIGHTSTEELBLUE": (176, 196, 222),
    "LIGHTYELLOW": (255, 255, 224),
    "LIME": (0, 255, 0),
    "LIMEGREEN": (50, 205, 50),
    "LINEN": (250, 240, 230),
    "MAGENTA": (255, 0, 255),
    "MAROON": (128, 0, 0),
    "MEDIUMAQUAMARINE": (102, 205, 170),
    "MEDIUMBLUE": (0, 0, 205),
    "MEDIUMORCHID": (186, 85, 211),
    "MEDIUMPURPLE": (147, 112, 219),
    "MEDIUMSEAGREEN": (60, 179, 113),
    "MEDIUMSLATEBLUE": (123, 104, 238),
    "MEDIUMSPRINGGREEN": (0, 250, 154),
    "MEDIUMTURQUOISE": (72, 209, 204),
    "MEDIUMVIOLETRED": (199, 21, 133),
    "MIDNIGHTBLUE": (25, 25, 112),
    "MINTCREAM": (245, 255, 250),
    "MISTYROSE": (255, 228, 225),
    "MOCCASIN": (255, 228, 181),
    "NAVAJOWHITE": (255, 222, 173),
    "NAVY": (0, 0, 128),
    "OLDLACE": (253, 245, 230),
    "OLIVE": (128, 128, 0),
    "OLIVEDRAB": (107, 142, 35),
    "ORANGE": (255, 165, 0),
    "ORANGERED": (255, 69, 0),
    "ORCHID": (218, 112, 214),
    "PALEGOLDENROD": (238, 232, 170),
    "PALEGREEN": (152, 251, 152),
    "PALETURQUOISE": (175, 238, 238),
    "PALEVIOLETRED": (219, 112, 147),
    "PAPAYAWHIP": (255, 239, 213),
    "PEACHPUFF": (255, 218, 185),
    "PERU": (205, 133, 63),
    "PINK": (255, 192, 203),
    "PLUM": (221, 160, 221),
    "POWDERBLUE": (176, 224, 230),
    "PURPLE": (128, 0, 128),
    "RED": (255, 0, 0),
    "ROSYBROWN": (188, 143, 143),
    "ROYALBLUE": (65, 105, 225),
    "SADDLEBROWN": (139, 69, 19),
    "SALMON": (250, 128, 114),
    "SANDYBROWN": (244, 164, 96),
    "SEAGREEN": (46, 139, 87),
    "SEASHELL": (255, 245, 238),
    "SIENNA": (160, 82, 45),
    "SILVER": (192, 192, 192),
    "SKYBLUE": (135, 206, 235),
    "SLATEBLUE": (106, 90, 205),
    "SLATEGRAY": (112, 128, 144),
    "SNOW": (255, 250, 250),
    "SPRINGGREEN": (0, 255, 127),
    "STEELBLUE": (70, 130, 180),
    "TAN": (210, 180, 140),
    "TEAL": (0, 128, 128),
    "THISTLE": (216, 191, 216),
    "TOMATO": (255, 99, 71),
    "TURQUOISE": (64, 224, 208),
    "VIOLET": (238, 130, 238),
    "WHEAT": (245, 222, 179),
    "WHITE": (255, 255, 255),
    "WHITESMOKE": (245, 245, 245),
    "YELLOW": (255, 255, 0),
    "YELLOWGREEN": (154, 205, 50),
}


def gle_color_rgb(name: str) -> Optional[Tuple[int, int, int]]:
    """Look up a GLE color name's RGB triple, case-insensitively.

    British "GREY" spellings (GREY, DARKGREY, LIGHTSLATEGREY, ...) are
    accepted as aliases for their "GRAY" forms: GLE's legacy color table
    supports them, and hand-written .gle files use them, so the tolerant
    parser must too. Returns ``None`` if ``name`` is not recognized.
    """
    key = str(name).strip().upper()
    hit = COLORS.get(key)
    if hit is None and "GREY" in key:
        hit = COLORS.get(key.replace("GREY", "GRAY"))
    return hit


def nearest_gle_color(r: int, g: int, b: int) -> str:
    """Find the GLE color name nearest to an RGB triple.

    Tries an exact match first; falls back to the color with the smallest
    Euclidean distance in RGB space. Ties are broken by the first match in
    :data:`COLORS`' iteration order (stable across calls since dicts
    preserve insertion order). Used by the GUI color swatch to snap an
    arbitrary picked color to its closest named GLE equivalent.
    """
    target = (int(r), int(g), int(b))
    for name, rgb in COLORS.items():
        if rgb == target:
            return name

    best_name = None
    best_dist = None
    for name, (cr, cg, cb) in COLORS.items():
        dist = (cr - target[0]) ** 2 + (cg - target[1]) ** 2 + (cb - target[2]) ** 2
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
#
# Transcribed from GLE 4.3.10 ``src/gle/pass.cpp`` lines ~2371-2418 (the
# ``stdmark[]`` array -- the current marker table; NOT the legacy
# ``stdmark_v35[]`` array that precedes it). This is the full set of marker
# names GLE's ``marker`` keyword accepts.
MARKERS = frozenset(
    {
        "ASTERISK",
        "ASTERIX",
        "CIRCLE",
        "CLUB",
        "CROSS",
        "DAG",
        "DDAG",
        "DIAMOND",
        "DIAMONDZ",
        "DOT",
        "FCIRCLE",
        "FDIAMOND",
        "FLOWER",
        "FSQUARE",
        "FSTARR",
        "FTRIANGLE",
        "FTRIANGLED",
        "HANDPEN",
        "HEART",
        "LETTER",
        "MINUS",
        "ODOT",
        "OMINUS",
        "OPLUS",
        "OTIMES",
        "PCROSS",
        "PHONE",
        "PLANE",
        "PLUS",
        "SCIRCLE",
        "SNAKE",
        "SPADE",
        "SQUARE",
        "SSQUARE",
        "STAR",
        "STAR2",
        "STAR3",
        "STAR4",
        "STARR",
        "TRIANGLE",
        "TRIANGLED",
        "TRIANGLEZ",
        "WCIRCLE",
        "WDIAMOND",
        "WTRIANGLE",
        "WTRIANGLED",
        "WSQUARE",
        "WSTARR",
    }
)


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
# GLE ``lstyle`` integer <-> matplotlib linestyle string. Verified against
# the actual mapping used at the writer call sites (not assumed):
# ``GLEWriter.add_plot_line``/``add_errorbar``/``add_plot_line_from_file``
# emit ``lstyle {style.line_style_dashed}`` for ``'--'``, ``{...dotted}`` for
# ``':'``, and ``{...dashdot}`` for ``'-.'`` (default field values 2/3/4 from
# ``GLEStyleConfig`` in ``src/gleplot/config.py``); solid lines (``'-'``)
# never emit an ``lstyle`` token at all (GLE's default is style 1). The
# reverse map used by ``Axes.errorbar``'s ``fmt`` string parsing recognizes
# exactly ``'-'``, ``'--'``, ``':'``, ``'-.'``.
LSTYLE_TO_MATPLOTLIB: Dict[int, str] = {
    1: "-",
    2: "--",
    3: ":",
    4: "-.",
}

MATPLOTLIB_TO_LSTYLE: Dict[str, int] = {v: k for k, v in LSTYLE_TO_MATPLOTLIB.items()}


# ---------------------------------------------------------------------------
# Legend / key positions
# ---------------------------------------------------------------------------
#
# Long-form <-> short-form GLE legend position, mirroring
# ``GLEWriter.add_legend``'s ``pos_map`` (long -> short; falls through to the
# value as-is if already short-form) and ``Axes.legend``'s ``loc_map``
# (matplotlib ``loc`` -> gleplot's long form, which ``add_legend`` then maps
# to short form). Only the four corner positions plus ``'center'`` are
# produced by the current writer/axes code; ``'tc'``/``'bc'``/``'lc'``/``'rc'``
# are valid GLE short forms with no long-form producer in gleplot today, so
# they map to themselves for completeness on the parser side.
KEY_POSITIONS_LONG_TO_SHORT: Dict[str, str] = {
    "top right": "tr",
    "top left": "tl",
    "bottom right": "br",
    "bottom left": "bl",
    "center": "cc",
}

# ---------------------------------------------------------------------------
# Palette subroutine names (contour/heatmap support)
# ---------------------------------------------------------------------------
#
# gleplot emits self-contained palette subroutines named ``gleplot_<name>``
# (see :mod:`gleplot.palettes`). The recognizer maps a ``colormap ... palette
# gleplot_<name>`` clause back to the canonical cmap name via this table (and
# treats any OTHER palette sub name as an unknown/foreign palette -> passthrough
# with a warning). Provenance: the ``<name>`` keys mirror
# ``gleplot.palettes.PALETTE_STOPS`` plus ``coolwarm`` -- the palettes that
# require an emitted sub. ``gray``/``rainbow`` need no sub and never appear as a
# ``palette`` clause (grayscale = no clause; rainbow = the ``color`` switch).
PALETTE_SUB_TO_CMAP: Dict[str, str] = {
    "gleplot_viridis": "viridis",
    "gleplot_magma": "magma",
    "gleplot_inferno": "inferno",
    "gleplot_plasma": "plasma",
    "gleplot_cividis": "cividis",
    "gleplot_coolwarm": "coolwarm",
}

CMAP_TO_PALETTE_SUB: Dict[str, str] = {v: k for k, v in PALETTE_SUB_TO_CMAP.items()}


KEY_POSITIONS_SHORT_TO_LONG: Dict[str, str] = {
    v: k for k, v in KEY_POSITIONS_LONG_TO_SHORT.items()
}
# Short forms with no long-form producer in gleplot's writer/axes today, but
# valid GLE key-position tokens a parser must still recognize.
KEY_POSITIONS_SHORT_TO_LONG.setdefault("tc", "top center")
KEY_POSITIONS_SHORT_TO_LONG.setdefault("bc", "bottom center")
KEY_POSITIONS_SHORT_TO_LONG.setdefault("lc", "left center")
KEY_POSITIONS_SHORT_TO_LONG.setdefault("rc", "right center")

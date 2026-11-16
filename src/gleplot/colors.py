"""Color utilities for gleplot.

Colour fidelity contract
------------------------
A colour that the user supplies as a **GLE colour name** (any case: ``red``,
``DARKBLUE``, ``gray55``) is passed through as that name. Anything else --
a hex string, an RGB tuple, a matplotlib cycle code -- is converted to an
**exact** GLE colour expression ``rgb255(r,g,b)``.

This replaces the original "snap to the nearest of ~8 named colours by
dominant channel" behaviour, which silently destroyed the requested colour:
``#8c8c8c`` and ``#999999`` (greys) both rendered MAGENTA, ``#bbbbbb``
rendered WHITE (invisible on a white page), and ``#9467bd`` (matplotlib's
tab purple) rendered MAGENTA -- so two distinct series could collide onto
one colour with no warning. GLE has supported ``rgb255(r,g,b)`` /
``rgb(r,g,b)`` colour expressions since 4.2, everywhere a colour name is
accepted, so the snapping was never necessary.

An already-formed GLE colour expression (``rgb255(140,140,140)``,
``rgb(0.55,0.4,0.74)``) is passed through unchanged apart from whitespace
normalisation. That matters for round-tripping: colours recovered from a
``.gle`` file by :mod:`gleplot.parser` are fed back through this function
when the figure is rebuilt.
"""

import re
import warnings
from typing import Dict, Optional, Tuple, Union

# Matplotlib color codes to GLE color names
MATPLOTLIB_TO_GLE_COLORS = {
    "b": "BLUE",
    "g": "GREEN",
    "r": "RED",
    "c": "CYAN",
    "m": "MAGENTA",
    "y": "YELLOW",
    "k": "BLACK",
    "w": "WHITE",
    # Named colors
    "blue": "BLUE",
    "green": "GREEN",
    "red": "RED",
    "cyan": "CYAN",
    "magenta": "MAGENTA",
    "yellow": "YELLOW",
    "black": "BLACK",
    "white": "WHITE",
    "orange": "ORANGE",
    "purple": "PURPLE",
    "brown": "BROWN",
    "pink": "PINK",
    "gray": "GRAY",
    "grey": "GRAY",
    "lightblue": "LIGHTBLUE",
    "lightgreen": "LIGHTGREEN",
    "lightcyan": "LIGHTCYAN",
    "lightgray": "LIGHTGRAY",
    "lightgrey": "LIGHTGRAY",
    "darkblue": "DARKBLUE",
    "darkgreen": "DARKGREEN",
    "darkred": "DARKRED",
    "darkgray": "DARKGRAY",
    "darkgrey": "DARKGRAY",
}

# Extended GLE color palette
GLE_COLORS = {
    "BLUE",
    "RED",
    "GREEN",
    "CYAN",
    "MAGENTA",
    "YELLOW",
    "BLACK",
    "WHITE",
    "ORANGE",
    "PURPLE",
    "BROWN",
    "PINK",
    "GRAY",
    "LIGHTBLUE",
    "LIGHTGREEN",
    "LIGHTCYAN",
    "LIGHTGRAY",
    "DARKBLUE",
    "DARKGREEN",
    "DARKRED",
    "DARKGRAY",
}

#: matplotlib's default property cycle (``tab10``), keyed by both the cycle
#: reference (``C0``..``C9``) and the ``tab:`` colour name. These are NOT GLE
#: colour names, so they resolve to exact ``rgb255`` expressions -- ten
#: distinct colours. (They previously all collapsed to a handful of snapped
#: names, e.g. C4 ``#9467bd`` and C6 ``#e377c2`` both rendering MAGENTA.)
MATPLOTLIB_CYCLE_HEX = {
    "c0": "#1f77b4",
    "tab:blue": "#1f77b4",
    "c1": "#ff7f0e",
    "tab:orange": "#ff7f0e",
    "c2": "#2ca02c",
    "tab:green": "#2ca02c",
    "c3": "#d62728",
    "tab:red": "#d62728",
    "c4": "#9467bd",
    "tab:purple": "#9467bd",
    "c5": "#8c564b",
    "tab:brown": "#8c564b",
    "c6": "#e377c2",
    "tab:pink": "#e377c2",
    "c7": "#7f7f7f",
    "tab:gray": "#7f7f7f",
    "tab:grey": "#7f7f7f",
    "c8": "#bcbd22",
    "tab:olive": "#bcbd22",
    "c9": "#17becf",
    "tab:cyan": "#17becf",
}

#: A GLE colour *expression* -- a function call such as ``rgb255(140,140,140)``,
#: ``rgb(0.1,0.2,0.8)`` or ``grey(0.5)``. Matched structurally (any identifier
#: applied to a parenthesised argument list) rather than against a fixed list
#: of function names, so a hand-written script's colour expression survives a
#: round trip untouched.
_COLOR_EXPR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\([^()]*\)$")

#: Every colour name GLE recognises out of the box, uppercase: GLE's own
#: 151-name table plus the names gleplot's matplotlib mapping emits.
_GLE_COLOR_NAMES = None  # type: Optional[frozenset]


def _gle_color_names() -> frozenset:
    """Every colour name GLE recognises out of the box, uppercase."""
    global _GLE_COLOR_NAMES
    if _GLE_COLOR_NAMES is None:
        _GLE_COLOR_NAMES = frozenset(COLORS) | frozenset(GLE_COLORS)
    return _GLE_COLOR_NAMES


def rgb_to_gle(color: Union[str, Tuple[float, float, float]]) -> str:
    """
    Convert a matplotlib color specification to a GLE color token.

    A recognised GLE colour name is returned as that name (uppercased);
    everything else is returned as an exact ``rgb255(r,g,b)`` expression, so
    no requested colour is ever silently replaced by a different one.

    Parameters
    ----------
    color : str or tuple
        Matplotlib color: a name, a single-letter code, a ``C0``..``C9``
        cycle reference, a ``tab:`` name, a ``#RRGGBB``/``#RGB`` hex string,
        an RGB tuple/list with components in [0, 1], or an already-formed
        GLE colour expression.

    Returns
    -------
    str
        A GLE colour token: an uppercase GLE colour name, or ``rgb255(r,g,b)``.

    Examples
    --------
    >>> rgb_to_gle('blue')
    'BLUE'
    >>> rgb_to_gle('b')
    'BLUE'
    >>> rgb_to_gle((0.0, 0.0, 1.0))
    'rgb255(0,0,255)'
    >>> rgb_to_gle('#8c8c8c')
    'rgb255(140,140,140)'
    >>> rgb_to_gle('rgb255(140, 140, 140)')
    'rgb255(140,140,140)'
    """
    # Handle tuple (R, G, B) with values in [0, 1]
    if isinstance(color, (tuple, list)):
        if len(color) >= 3:
            return _rgb01_to_gle(color[0], color[1], color[2])

    # Handle string colors
    if isinstance(color, str):
        text = color.strip()
        color_lower = text.lower()
        color_upper = text.upper()

        # Already a GLE colour expression, e.g. round-tripped rgb255(...).
        if _COLOR_EXPR_RE.match(text):
            return re.sub(r"\s+", "", text)

        # Check if it's already a GLE color name
        if color_upper in _gle_color_names():
            return color_upper

        # British "grey" spellings of any named grey -- bare GREY, the
        # numbered ramp GREY1/GREY5/GREY10..GREY90, DARKGREY, LIGHTGREY, etc.
        # -- alias their "gray" equivalents. GLE itself defines these grey
        # spellings as distinct colours (``defineOldGLEColors`` in
        # color.cpp), matching the gray ramp's RGB values, and
        # gle_color_rgb already treats GREY as an
        # alias for GRAY when reading a ``.gle`` file; this mirrors that
        # convention on the writing side so a name that round-trips one way
        # round-trips the other too. Without this, e.g. ``rgb_to_gle('grey40')``
        # matched nothing above and fell all the way through to the
        # unrecognized-name fallback, silently turning a mid-grey into BLACK.
        if "GREY" in color_upper:
            gray_variant = color_upper.replace("GREY", "GRAY")
            if gray_variant in _gle_color_names():
                return gray_variant

        # Check matplotlib color codes and named colors
        if color_lower in MATPLOTLIB_TO_GLE_COLORS:
            return MATPLOTLIB_TO_GLE_COLORS[color_lower]

        # matplotlib default property cycle: 'C0'..'C9' / 'tab:blue' / ...
        if color_lower in MATPLOTLIB_CYCLE_HEX:
            return _hex_to_gle(MATPLOTLIB_CYCLE_HEX[color_lower])

        # Try hex color
        if color_lower.startswith("#"):
            return _hex_to_gle(color_lower)

        # Unrecognized name: neither a GLE colour, a matplotlib code/cycle
        # reference, nor a hex string. gleplot's house rule is "no silent
        # drops" (nothing unexpressible is dropped without at least a
        # warning) -- see markers.matplotlib_to_gle_marker for the
        # established pattern this follows. The BLACK fallback is
        # deliberately kept (existing callers/tests depend on it), but it no
        # longer happens silently.
        warnings.warn(
            f"Unrecognized colour {color!r}: it is neither a GLE colour "
            f"name, a matplotlib colour code, nor a hex string. Falling "
            f"back to BLACK.",
            UserWarning,
            stacklevel=2,
        )

    # Default fallback
    return "BLACK"


def rgb255_expr(r: int, g: int, b: int) -> str:
    """Format an exact GLE colour expression from 0-255 components."""
    return "rgb255({},{},{})".format(_clamp255(r), _clamp255(g), _clamp255(b))


def apply_alpha(color: str, alpha: Optional[float]) -> str:
    """Compose a resolved GLE colour token with a transparency component.

    ``color`` must already be a resolved GLE colour token, i.e. what
    :func:`rgb_to_gle` returns (a colour name or an ``rgb255(...)``/``rgb(...)``
    expression) -- this is what every caller (``FillSeries``/``Span``) stores.

    When ``alpha`` is ``None`` or >= 1.0 (fully opaque), ``color`` is returned
    completely unchanged -- this is what keeps every existing (opaque) figure's
    generated ``.gle`` text byte-identical (gleplot's fixed-point contract):
    the alpha path never touches a script that has nothing to be transparent.

    Otherwise ``color`` is decomposed to its RGB components
    (:func:`gle_color_to_rgb255`) and re-expressed as GLE's
    ``rgba255(r,g,b,a)`` colour function (GLE >= 4.2), with ``a`` the 0-255
    scaled alpha. Rendering a script containing ``rgba255`` requires GLE's
    ``-cairo`` device flag (see ``gleplot.figure.Figure.requires_cairo`` and
    ``gleplot.compiler.build_compile_args``); composing the colour here is
    purely a *script-text* concern and is independent of that compile-time
    flag decision, so this function never needs to know whether Cairo will
    actually be used.

    A token :func:`gle_color_to_rgb255` cannot decompose (notably: an
    already-formed ``rgba255(...)``/``rgba(...)`` expression a user supplied
    directly, or round-tripped from a parsed ``.gle`` file) is returned
    unchanged -- it already carries its own alpha, so the separate ``alpha``
    field is redundant for it, exactly like :func:`rgb_to_gle`'s "already a
    GLE colour expression" pass-through.
    """
    if alpha is None:
        return color
    a = float(alpha)
    if a >= 1.0:
        return color
    a = max(0.0, min(1.0, a))
    rgb = gle_color_to_rgb255(color)
    if rgb is None:
        return color
    r, g, b = rgb
    return "rgba255({},{},{},{})".format(r, g, b, _clamp255(a * 255.0))


def gle_color_to_rgb255(color: str) -> Optional[Tuple[int, int, int]]:
    """Best-effort inverse of :func:`rgb_to_gle`, for colour swatches.

    Understands ``rgb255(r,g,b)``, ``rgb(r,g,b)`` (0-1 floats) and any GLE
    colour name. Returns ``None`` when the token cannot be resolved.
    """
    if not isinstance(color, str):
        return None
    text = re.sub(r"\s+", "", color)
    m = re.match(r"^(rgb255|rgb)\(([^()]*)\)$", text, re.IGNORECASE)
    if m:
        parts = [p for p in m.group(2).split(",") if p != ""]
        if len(parts) < 3:
            return None
        try:
            vals = [float(p) for p in parts[:3]]
        except ValueError:
            return None
        if m.group(1).lower() == "rgb":
            return tuple(_clamp255(round(v * 255.0)) for v in vals)  # type: ignore[return-value]
        return tuple(_clamp255(round(v)) for v in vals)  # type: ignore[return-value]

    return gle_color_rgb(text)


def _clamp255(value) -> int:
    """Clamp a numeric component into the 0-255 integer range."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(255, n))


def _rgb01_to_gle(r: float, g: float, b: float) -> str:
    """Convert an RGB triple with components in [0, 1] to ``rgb255(...)``."""
    return rgb255_expr(
        _clamp255(float(r) * 255.0),
        _clamp255(float(g) * 255.0),
        _clamp255(float(b) * 255.0),
    )


def _hex_to_gle(hex_color: str) -> str:
    """Convert a ``#RRGGBB`` or ``#RGB`` hex string to ``rgb255(...)``."""
    digits = hex_color.lstrip("#").strip()

    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)

    if len(digits) == 6:
        try:
            r = int(digits[0:2], 16)
            g = int(digits[2:4], 16)
            b = int(digits[4:6], 16)
        except ValueError:
            warnings.warn(
                f"Unrecognized colour {hex_color!r}: not a valid hex string. "
                f"Falling back to BLACK.",
                UserWarning,
                stacklevel=3,
            )
            return "BLACK"
        return rgb255_expr(r, g, b)

    warnings.warn(
        f"Unrecognized colour {hex_color!r}: not a valid hex string "
        f"(expected #RGB or #RRGGBB). Falling back to BLACK.",
        UserWarning,
        stacklevel=3,
    )
    return "BLACK"


def get_color_palette(name: str = "default") -> list:
    """Get a preset color palette."""
    palettes = {
        "default": ["BLUE", "RED", "GREEN", "CYAN", "MAGENTA", "YELLOW"],
        "dark": ["DARKBLUE", "DARKRED", "DARKGREEN", "DARKGRAY"],
        "light": ["LIGHTBLUE", "LIGHTGREEN", "LIGHTCYAN", "LIGHTGRAY"],
    }
    return palettes.get(name, palettes["default"])


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
    preserve insertion order).

    Nothing in gleplot's own emission path snaps a color: an arbitrary color
    is written out exactly as ``rgb255(r,g,b)`` (see
    :func:`gleplot.colors.rgb_to_gle`). This helper exists for callers who
    *want* a named approximation -- pass its result back in as the color.
    """
    target = (int(r), int(g), int(b))
    for name, rgb in COLORS.items():
        if rgb == target:
            return name

    # COLORS is never empty, so the first iteration always replaces this.
    best_name = "BLACK"
    best_dist = None
    for name, (cr, cg, cb) in COLORS.items():
        dist = (cr - target[0]) ** 2 + (cg - target[1]) ** 2 + (cb - target[2]) ** 2
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name

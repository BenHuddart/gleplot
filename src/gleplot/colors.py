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
from typing import Optional, Tuple, Union


# Matplotlib color codes to GLE color names
MATPLOTLIB_TO_GLE_COLORS = {
    'b': 'BLUE',
    'g': 'GREEN',
    'r': 'RED',
    'c': 'CYAN',
    'm': 'MAGENTA',
    'y': 'YELLOW',
    'k': 'BLACK',
    'w': 'WHITE',
    # Named colors
    'blue': 'BLUE',
    'green': 'GREEN',
    'red': 'RED',
    'cyan': 'CYAN',
    'magenta': 'MAGENTA',
    'yellow': 'YELLOW',
    'black': 'BLACK',
    'white': 'WHITE',
    'orange': 'ORANGE',
    'purple': 'PURPLE',
    'brown': 'BROWN',
    'pink': 'PINK',
    'gray': 'GRAY',
    'grey': 'GRAY',
    'lightblue': 'LIGHTBLUE',
    'lightgreen': 'LIGHTGREEN',
    'lightcyan': 'LIGHTCYAN',
    'lightgray': 'LIGHTGRAY',
    'lightgrey': 'LIGHTGRAY',
    'darkblue': 'DARKBLUE',
    'darkgreen': 'DARKGREEN',
    'darkred': 'DARKRED',
    'darkgray': 'DARKGRAY',
    'darkgrey': 'DARKGREY',
}

# Extended GLE color palette
GLE_COLORS = {
    'BLUE', 'RED', 'GREEN', 'CYAN', 'MAGENTA', 'YELLOW', 'BLACK', 'WHITE',
    'ORANGE', 'PURPLE', 'BROWN', 'PINK', 'GRAY', 'LIGHTBLUE', 'LIGHTGREEN',
    'LIGHTCYAN', 'LIGHTGRAY', 'DARKBLUE', 'DARKGREEN', 'DARKRED', 'DARKGRAY',
}

#: matplotlib's default property cycle (``tab10``), keyed by both the cycle
#: reference (``C0``..``C9``) and the ``tab:`` colour name. These are NOT GLE
#: colour names, so they resolve to exact ``rgb255`` expressions -- ten
#: distinct colours. (They previously all collapsed to a handful of snapped
#: names, e.g. C4 ``#9467bd`` and C6 ``#e377c2`` both rendering MAGENTA.)
MATPLOTLIB_CYCLE_HEX = {
    'c0': '#1f77b4', 'tab:blue': '#1f77b4',
    'c1': '#ff7f0e', 'tab:orange': '#ff7f0e',
    'c2': '#2ca02c', 'tab:green': '#2ca02c',
    'c3': '#d62728', 'tab:red': '#d62728',
    'c4': '#9467bd', 'tab:purple': '#9467bd',
    'c5': '#8c564b', 'tab:brown': '#8c564b',
    'c6': '#e377c2', 'tab:pink': '#e377c2',
    'c7': '#7f7f7f', 'tab:gray': '#7f7f7f', 'tab:grey': '#7f7f7f',
    'c8': '#bcbd22', 'tab:olive': '#bcbd22',
    'c9': '#17becf', 'tab:cyan': '#17becf',
}

#: A GLE colour *expression* -- a function call such as ``rgb255(140,140,140)``,
#: ``rgb(0.1,0.2,0.8)`` or ``grey(0.5)``. Matched structurally (any identifier
#: applied to a parenthesised argument list) rather than against a fixed list
#: of function names, so a hand-written script's colour expression survives a
#: round trip untouched.
_COLOR_EXPR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\([^()]*\)$")

#: Full GLE colour-name table, loaded lazily from the parser's transcription of
#: GLE's own table (151 names). Kept lazy so ``gleplot.colors`` stays a leaf
#: module with no import-time dependency on the parser package.
_GLE_COLOR_NAMES = None  # type: Optional[frozenset]


def _gle_color_names() -> frozenset:
    """Every colour name GLE recognises out of the box, uppercase."""
    global _GLE_COLOR_NAMES
    if _GLE_COLOR_NAMES is None:
        try:
            from .parser.tables import COLORS as _TABLE_COLORS

            _GLE_COLOR_NAMES = frozenset(_TABLE_COLORS) | frozenset(GLE_COLORS)
        except Exception:  # pragma: no cover - defensive; parser is in-tree
            _GLE_COLOR_NAMES = frozenset(GLE_COLORS)
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

        # Check matplotlib color codes and named colors
        if color_lower in MATPLOTLIB_TO_GLE_COLORS:
            return MATPLOTLIB_TO_GLE_COLORS[color_lower]

        # matplotlib default property cycle: 'C0'..'C9' / 'tab:blue' / ...
        if color_lower in MATPLOTLIB_CYCLE_HEX:
            return _hex_to_gle(MATPLOTLIB_CYCLE_HEX[color_lower])

        # Try hex color
        if color_lower.startswith('#'):
            return _hex_to_gle(color_lower)

    # Default fallback
    return 'BLACK'


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

    try:
        from .parser.tables import gle_color_rgb

        return gle_color_rgb(text)
    except Exception:  # pragma: no cover - defensive; parser is in-tree
        return None


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
    digits = hex_color.lstrip('#').strip()

    if len(digits) == 3:
        digits = ''.join(ch * 2 for ch in digits)

    if len(digits) == 6:
        try:
            r = int(digits[0:2], 16)
            g = int(digits[2:4], 16)
            b = int(digits[4:6], 16)
        except ValueError:
            return 'BLACK'
        return rgb255_expr(r, g, b)

    return 'BLACK'


def get_color_palette(name: str = 'default') -> list:
    """Get a preset color palette."""
    palettes = {
        'default': ['BLUE', 'RED', 'GREEN', 'CYAN', 'MAGENTA', 'YELLOW'],
        'dark': ['DARKBLUE', 'DARKRED', 'DARKGREEN', 'DARKGRAY'],
        'light': ['LIGHTBLUE', 'LIGHTGREEN', 'LIGHTCYAN', 'LIGHTGRAY'],
    }
    return palettes.get(name, palettes['default'])

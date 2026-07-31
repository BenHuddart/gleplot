"""Marker utilities for gleplot.

``MATPLOTLIB_TO_GLE_MARKERS`` covers every code in matplotlib's standard
*string* marker set (``matplotlib.markers.MarkerStyle.markers``). Two
conventions run through it:

* an **uppercase** code takes the filled GLE glyph and its **lowercase**
  partner the outline one, so a case-significant matplotlib pair stays
  visually distinct in GLE -- ``'D'``/``'d'`` -> ``FDIAMOND``/``DIAMOND``,
  ``'*'``/``'p'`` -> ``FSTARR``/``STARR``;
* where GLE has no corresponding glyph, several matplotlib codes collapse
  onto the closest one -- ``'<'``/``'>'`` -> ``TRIANGLE``, ``'x'``/``'X'``
  -> ``PCROSS``, ``'|'``/``'_'`` -> ``PLUS``.

Deliberately **not** mapped, having no GLE glyph that would not misrepresent
them: matplotlib's integer tick markers (``0``-``3``, tickleft/tickright/
tickup/tickdown -- single line segments drawn beside a point, not symbols
centred on it) and its caret markers (``4``-``11``). They fall through to the
``default`` of :func:`get_gle_marker`.

Order matters: ``gleplot.parser.tables._build_gle_marker_to_matplotlib``
inverts this dict and keeps the *first* matplotlib code seen for each GLE
name as the canonical one for reading GLE back. Append new codes; do not
insert them among the established entries.

Three families of GLE marker name matter here:

- **filled** (``FCIRCLE``, ``FSQUARE``, ...) -- solid ink, the historical
  gleplot default for every matplotlib marker code that has a filled form;
- **outline** (``CIRCLE``, ``SQUARE``, ...) -- stroked only, *transparent*
  inside, so a line or error bar underneath shows through. This is what
  matplotlib's ``fillstyle='none'`` / ``markerfacecolor='none'`` means;
- **white-filled** (``WCIRCLE``, ``WSQUARE``, ...) -- stroked outline with an
  opaque white interior that masks whatever is underneath. This is what
  matplotlib's ``markerfacecolor='white'`` means.

All three were verified against the GLE 4.3.10 binary at
``/usr/local/bin/gle`` by rendering every name over a coloured rule: the
``CIRCLE`` family lets the rule through, the ``W`` family hides it.

Filled-vs-open is a load-bearing semantic convention in publication figures
(e.g. zero-field vs longitudinal-field data on one panel), so the mapping is
exposed explicitly rather than being reachable only by naming a raw GLE
marker.
"""

import warnings
from typing import Dict, Optional

# Matplotlib to GLE marker mapping (the *filled* / default family).
#
# NOTE: a few entries here are already outline shapes because GLE has no
# filled counterpart for them: '<'/'>' (matplotlib's left/right triangles --
# GLE has no sideways triangle at all, so the up-triangle outline stands in),
# 'p' (pentagon -> STARR) and 'h' (hexagon -> DIAMOND). Those choices predate
# outline-marker support and are kept verbatim so existing scripts keep
# rendering identically; ``fill='none'`` still resolves them to their outline
# family member (which, for those three, is the same name).
MATPLOTLIB_TO_GLE_MARKERS = {
    'o': 'FCIRCLE',      # Circle
    's': 'FSQUARE',      # Square
    '^': 'FTRIANGLE',    # Triangle up
    'v': 'FTRIANGLED',   # Triangle down
    '<': 'TRIANGLE',     # Triangle left (outline)
    '>': 'TRIANGLE',     # Triangle right (outline)
    'D': 'FDIAMOND',     # Diamond
    '*': 'FSTARR',       # Star
    'p': 'STARR',        # Pentagon
    'H': 'HEART',        # Heart
    'h': 'DIAMOND',      # Hexagon
    '+': 'PLUS',         # Plus sign
    'P': 'PLUS',         # Plus alternate
    'x': 'PCROSS',       # X cross
    'X': 'PCROSS',       # X cross alternate
    '.': 'DOT',          # Point
    ',': 'DOT',          # Pixel
    '|': 'PLUS',         # Vertical line
    '_': 'PLUS',         # Horizontal line
    # Appended (see module docstring: order fixes the canonical inverse).
    'd': 'DIAMOND',      # Thin diamond -- outline partner of 'D'
    '8': 'FCIRCLE',      # Octagon -- filled, indistinguishable from a circle
    '1': 'TRIANGLED',    # tri_down  -- spokes of a down triangle
    '2': 'TRIANGLE',     # tri_up    -- spokes of an up triangle
    '3': 'TRIANGLE',     # tri_left  -- as '<', GLE has no directed triangle
    '4': 'TRIANGLE',     # tri_right -- as '>'
}

#: Accepted values for the ``fill`` argument of :func:`get_gle_marker`.
MARKER_FILLS = ("full", "none", "white")

#: Shape families that have all three fill variants in GLE. Keyed by an
#: internal family name; the values are the GLE marker names per fill mode.
#: Any GLE marker NOT listed here (PLUS, PCROSS, DOT, CROSS, STAR, HEART, ...)
#: has no fill concept and is returned unchanged by :func:`apply_marker_fill`.
MARKER_FILL_VARIANTS: Dict[str, Dict[str, str]] = {
    "circle": {"full": "FCIRCLE", "none": "CIRCLE", "white": "WCIRCLE"},
    "square": {"full": "FSQUARE", "none": "SQUARE", "white": "WSQUARE"},
    "triangle": {"full": "FTRIANGLE", "none": "TRIANGLE", "white": "WTRIANGLE"},
    "triangled": {"full": "FTRIANGLED", "none": "TRIANGLED", "white": "WTRIANGLED"},
    "diamond": {"full": "FDIAMOND", "none": "DIAMOND", "white": "WDIAMOND"},
    "star": {"full": "FSTARR", "none": "STARR", "white": "WSTARR"},
}

#: GLE marker name -> its shape family in :data:`MARKER_FILL_VARIANTS`.
_GLE_NAME_TO_FAMILY: Dict[str, str] = {
    name: family
    for family, variants in MARKER_FILL_VARIANTS.items()
    for name in variants.values()
}

#: Colour spellings that mean "white face" (matplotlib ``markerfacecolor``).
_WHITE_SPELLINGS = frozenset({"w", "white", "#fff", "#ffffff", "1.0", "1"})


def apply_marker_fill(gle_marker: Optional[str], fill: str = "full") -> Optional[str]:
    """Map a GLE marker name onto the requested fill variant.

    Parameters
    ----------
    gle_marker : str or None
        A GLE marker name (any case). ``None`` passes through.
    fill : {'full', 'none', 'white'}
        Desired fill: solid, transparent outline, or opaque white outline.

    Returns
    -------
    str or None
        The family member for ``fill``, or ``gle_marker`` unchanged when the
        shape has no fill variants (PLUS, PCROSS, DOT, ...). The returned
        name preserves the uppercase spelling gleplot emits.

    Raises
    ------
    ValueError
        If ``fill`` is not one of :data:`MARKER_FILLS`.
    """
    if fill not in MARKER_FILLS:
        raise ValueError(
            f"fill must be one of {MARKER_FILLS!r}, got {fill!r}"
        )
    if not gle_marker:
        return gle_marker
    name = str(gle_marker).upper()
    family = _GLE_NAME_TO_FAMILY.get(name)
    if family is None:
        return gle_marker
    return MARKER_FILL_VARIANTS[family][fill]


#: Matplotlib code -> transparent-outline GLE marker (``fillstyle='none'``).
MATPLOTLIB_TO_GLE_OUTLINE_MARKERS = {
    code: apply_marker_fill(name, "none")
    for code, name in MATPLOTLIB_TO_GLE_MARKERS.items()
}

#: Matplotlib code -> white-filled GLE marker (``markerfacecolor='white'``).
MATPLOTLIB_TO_GLE_WHITE_MARKERS = {
    code: apply_marker_fill(name, "white")
    for code, name in MATPLOTLIB_TO_GLE_MARKERS.items()
}

# GLE marker types (documentation for the names gleplot itself emits; the
# authoritative full list GLE accepts is ``gleplot.parser.tables.MARKERS``,
# transcribed from GLE's stdmark[] table).
GLE_MARKER_TYPES = {
    # Filled markers
    'FCIRCLE': 'Filled circle',
    'FSQUARE': 'Filled square',
    'FTRIANGLE': 'Filled triangle',
    'FTRIANGLED': 'Filled triangle down',
    'FDIAMOND': 'Filled diamond',
    'FSTARR': 'Filled star',

    # Outline markers (transparent interior)
    'CIRCLE': 'Circle outline',
    'SQUARE': 'Square outline',
    'TRIANGLE': 'Triangle outline',
    'TRIANGLED': 'Triangle outline down',
    'DIAMOND': 'Diamond outline',
    'STARR': 'Star outline',

    # White-filled markers (opaque interior, masks content underneath)
    'WCIRCLE': 'Circle, white fill',
    'WSQUARE': 'Square, white fill',
    'WTRIANGLE': 'Triangle, white fill',
    'WTRIANGLED': 'Triangle down, white fill',
    'WDIAMOND': 'Diamond, white fill',
    'WSTARR': 'Star, white fill',

    # Symbol markers
    'DOT': 'Small dot',
    'PLUS': 'Plus sign',
    'PCROSS': 'X cross',
    'CROSS': 'Cross',
    'CLUB': 'Club symbol',
    'HEART': 'Heart symbol',
    'SPADE': 'Spade symbol',
    'STAR': 'Star symbol',
    'DAG': 'Dagger symbol',
    'DDAG': 'Double dagger',
    'SNAKE': 'Snake symbol',
}


def _gle_marker_names() -> frozenset:
    """The full set of marker names GLE accepts (lazy, avoids a cycle).

    ``gleplot.parser.tables`` imports this module to build its inverse marker
    map, so the import has to happen at call time rather than at module load.
    """
    from .parser.tables import MARKERS

    return MARKERS


def get_gle_marker(
    matplotlib_marker: str,
    default: str = 'FCIRCLE',
    fill: str = 'full',
) -> Optional[str]:
    """
    Convert matplotlib marker to GLE marker name.

    Parameters
    ----------
    matplotlib_marker : str
        Matplotlib marker symbol (``'o'``, ``'s'``, ...) or a literal GLE
        marker name (``'wcircle'``, ``'FDIAMOND'``, ...), which is passed
        through after validation against GLE's own marker table.
    default : str
        GLE marker used when the symbol is not recognized. Unrecognized
        symbols also emit a :class:`UserWarning` -- gleplot used to fall back
        silently, which turned a typo into a wrong-shaped marker with no
        indication anything had happened.
    fill : {'full', 'none', 'white'}
        Fill style. ``'full'`` returns the historical mapping verbatim;
        ``'none'`` returns the transparent-outline family member and
        ``'white'`` the opaque white-filled one (shapes with no fill variant,
        e.g. ``PLUS``, are unaffected).

    Returns
    -------
    str or None
        GLE marker name, or ``None`` when no marker was requested.

    Raises
    ------
    ValueError
        If ``fill`` is not one of :data:`MARKER_FILLS`.

    Warns
    -----
    UserWarning
        If the marker symbol is neither a known matplotlib code nor a valid
        GLE marker name.
    """
    if fill not in MARKER_FILLS:
        raise ValueError(f"fill must be one of {MARKER_FILLS!r}, got {fill!r}")

    # matplotlib's *numeric* markers (0-3 tickleft/right/up/down, 4-11 the
    # carets) are a separate namespace from its string codes -- the int 1 is
    # tickright, the str '1' is tri_down -- and none of them has a GLE glyph
    # (see the module docstring). Take the default rather than stringifying
    # the number into the string table and drawing the wrong symbol.
    if isinstance(matplotlib_marker, (int, float)) and not isinstance(
        matplotlib_marker, bool
    ):
        return default

    if not matplotlib_marker or matplotlib_marker == 'None':
        return None

    marker = str(matplotlib_marker).strip()

    # Matplotlib marker codes are case-significant: 'D' (diamond) vs 'd'
    # (thin diamond), 'P' (filled plus) vs 'p' (pentagon), 'H' (hexagon2) vs
    # 'h' (hexagon1), 'X' vs 'x'. Try the exact code first so these map
    # correctly, then fall back to a case-insensitive lookup for robustness
    # against stray capitalization of unambiguous codes.
    if marker in MATPLOTLIB_TO_GLE_MARKERS:
        base = MATPLOTLIB_TO_GLE_MARKERS[marker]
    elif marker.lower() in MATPLOTLIB_TO_GLE_MARKERS:
        base = MATPLOTLIB_TO_GLE_MARKERS[marker.lower()]
    elif marker.upper() in _gle_marker_names():
        # A literal GLE marker name (e.g. 'wcircle', 'oplus'). Accept it and
        # normalize the spelling to the uppercase form gleplot emits.
        base = marker.upper()
    else:
        warnings.warn(
            f"Unrecognized marker {matplotlib_marker!r}: it is neither a "
            f"matplotlib marker code nor a GLE marker name. Falling back to "
            f"{default!r}.",
            UserWarning,
            stacklevel=2,
        )
        base = default

    # 'full' returns the table value verbatim so long-standing mappings that
    # already point at an outline shape ('<'/'>' -> TRIANGLE, 'p' -> STARR,
    # 'h' -> DIAMOND) keep rendering exactly as before.
    if fill == 'full':
        return base
    return apply_marker_fill(base, fill)


def resolve_marker_fill(
    fillstyle: Optional[str] = None,
    markerfacecolor: Optional[str] = None,
) -> str:
    """Reduce matplotlib's two fill controls to one of :data:`MARKER_FILLS`.

    matplotlib lets a caller open a marker two ways -- ``fillstyle='none'``
    or ``markerfacecolor='none'`` -- and both are common in the wild, so both
    are accepted here and collapse onto the same GLE outline shape.
    ``fillstyle`` wins when both are given (matching matplotlib, where
    ``fillstyle`` is a property of the marker style itself).

    Parameters
    ----------
    fillstyle : {'full', 'none', None}, optional
        matplotlib ``fillstyle``. The partial styles (``'top'``,
        ``'bottom'``, ``'left'``, ``'right'``) have no GLE equivalent and warn.
    markerfacecolor : str, optional
        matplotlib ``markerfacecolor`` / ``mfc``. ``'none'`` opens the
        marker; a white spelling (``'w'``, ``'white'``, ``'#ffffff'``) selects
        the opaque white-filled family. Any *other* colour warns and is
        ignored: a GLE marker is drawn in a single colour, so an edge colour
        differing from the face colour cannot be represented.

    Returns
    -------
    str
        ``'full'``, ``'none'`` or ``'white'``.
    """
    if fillstyle is not None:
        style = str(fillstyle).strip().lower()
        if style == "none":
            return "none"
        if style == "full":
            return "full"
        warnings.warn(
            f"fillstyle={fillstyle!r} has no GLE equivalent (GLE markers are "
            "either solid, outline, or white-filled); using a solid marker.",
            UserWarning,
            stacklevel=2,
        )
        return "full"

    if markerfacecolor is None:
        return "full"

    face = str(markerfacecolor).strip().lower()
    if face == "none":
        return "none"
    if face in _WHITE_SPELLINGS:
        return "white"
    warnings.warn(
        f"markerfacecolor={markerfacecolor!r} is ignored: GLE draws a marker "
        "in a single colour, so a face colour differing from the series "
        "colour cannot be represented. Use markerfacecolor='none' for an "
        "open marker or 'white' for a white-filled one.",
        UserWarning,
        stacklevel=2,
    )
    return "full"


def is_valid_gle_marker(marker: str) -> bool:
    """Check if marker is a valid GLE marker name.

    Validates against GLE's own ``stdmark[]`` table (case-insensitive), not
    just the subset gleplot documents in :data:`GLE_MARKER_TYPES`.
    """
    if not marker:
        return False
    return str(marker).upper() in _gle_marker_names()


def get_marker_size_scale(marker: str) -> float:
    """Get size scaling factor for marker (GLE msize vs matplotlib markersize)."""
    # GLE marker sizes typically need scaling down from matplotlib
    # Default scale is 0.1-0.15 for good visibility
    return 0.15

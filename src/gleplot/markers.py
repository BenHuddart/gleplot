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
"""

# Matplotlib to GLE marker mapping
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

# GLE marker types
GLE_MARKER_TYPES = {
    # Filled markers
    'FCIRCLE': 'Filled circle',
    'FSQUARE': 'Filled square',
    'FTRIANGLE': 'Filled triangle',
    'FTRIANGLED': 'Filled triangle down',
    'FDIAMOND': 'Filled diamond',
    'FSTARR': 'Filled star',
    
    # Outline markers
    'CIRCLE': 'Circle outline',
    'SQUARE': 'Square outline',
    'TRIANGLE': 'Triangle outline',
    'TRIANGLED': 'Triangle outline down',
    'DIAMOND': 'Diamond outline',
    'STARR': 'Star outline',
    
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


def get_gle_marker(matplotlib_marker: str, default: str = 'FCIRCLE') -> str:
    """
    Convert matplotlib marker to GLE marker name.

    Parameters
    ----------
    matplotlib_marker : str
        Matplotlib marker symbol
    default : str
        Default GLE marker if not found

    Returns
    -------
    str
        GLE marker name
    """
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
        return MATPLOTLIB_TO_GLE_MARKERS[marker]
    return MATPLOTLIB_TO_GLE_MARKERS.get(marker.lower(), default)


def is_valid_gle_marker(marker: str) -> bool:
    """Check if marker is a valid GLE marker name."""
    return marker in GLE_MARKER_TYPES


def get_marker_size_scale(marker: str) -> float:
    """Get size scaling factor for marker (GLE msize vs matplotlib markersize)."""
    # GLE marker sizes typically need scaling down from matplotlib
    # Default scale is 0.1-0.15 for good visibility
    return 0.15

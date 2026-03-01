"""Marker utilities for gleplot."""

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
    if not matplotlib_marker or matplotlib_marker == 'None':
        return None
    
    marker_lower = str(matplotlib_marker).lower().strip()
    return MATPLOTLIB_TO_GLE_MARKERS.get(marker_lower, default)


def is_valid_gle_marker(marker: str) -> bool:
    """Check if marker is a valid GLE marker name."""
    return marker in GLE_MARKER_TYPES


def get_marker_size_scale(marker: str) -> float:
    """Get size scaling factor for marker (GLE msize vs matplotlib markersize)."""
    # GLE marker sizes typically need scaling down from matplotlib
    # Default scale is 0.1-0.15 for good visibility
    return 0.15

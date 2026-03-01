"""Color utilities for gleplot."""

import re
from typing import Tuple, Union


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


def rgb_to_gle(color: Union[str, Tuple[float, float, float]]) -> str:
    """
    Convert matplotlib color specification to GLE color name.
    
    Parameters
    ----------
    color : str or tuple
        Matplotlib color (name, code, or RGB tuple)
        
    Returns
    -------
    str
        GLE color name in uppercase
        
    Examples
    --------
    >>> rgb_to_gle('blue')
    'BLUE'
    >>> rgb_to_gle('b')
    'BLUE'
    >>> rgb_to_gle((0.0, 0.0, 1.0))
    'BLUE'
    """
    # Handle tuple (R, G, B) with values in [0, 1]
    if isinstance(color, (tuple, list)):
        if len(color) >= 3:
            r, g, b = color[0], color[1], color[2]
            # Simple RGB to named color mapping
            return _rgb_tuple_to_gle(r, g, b)
    
    # Handle string colors
    if isinstance(color, str):
        color_lower = color.lower().strip()
        color_upper = color.upper()
        
        # Check if it's already a GLE color name
        if color_upper in GLE_COLORS:
            return color_upper
        
        # Check matplotlib color codes and named colors
        if color_lower in MATPLOTLIB_TO_GLE_COLORS:
            return MATPLOTLIB_TO_GLE_COLORS[color_lower]
        
        # Try hex color
        if color_lower.startswith('#'):
            return _hex_to_gle(color_lower)
    
    # Default fallback
    return 'BLACK'


def _rgb_tuple_to_gle(r: float, g: float, b: float) -> str:
    """Convert RGB tuple (0-1) to GLE color name."""
    # Simple mapping based on dominant channel
    rgb = [r, g, b]
    max_idx = rgb.index(max(rgb))
    min_val = min(rgb)
    max_val = max(rgb)
    
    if max_val < 0.3:
        return 'BLACK'
    elif min_val > 0.7:
        return 'WHITE'
    
    # Dominant color
    if max_idx == 0:  # Red dominant
        if g > 0.5:
            return 'MAGENTA'
        return 'RED'
    elif max_idx == 1:  # Green dominant
        if b > 0.5:
            return 'CYAN'
        return 'GREEN'
    else:  # Blue dominant
        if r > 0.5:
            return 'MAGENTA'
        if g > 0.5:
            return 'CYAN'
        return 'BLUE'


def _hex_to_gle(hex_color: str) -> str:
    """Convert hex color to GLE color name."""
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return _rgb_tuple_to_gle(r, g, b)
    
    return 'BLACK'


def get_color_palette(name: str = 'default') -> list:
    """Get a preset color palette."""
    palettes = {
        'default': ['BLUE', 'RED', 'GREEN', 'CYAN', 'MAGENTA', 'YELLOW'],
        'dark': ['DARKBLUE', 'DARKRED', 'DARKGREEN', 'DARKGRAY'],
        'light': ['LIGHTBLUE', 'LIGHTGREEN', 'LIGHTCYAN', 'LIGHTGRAY'],
    }
    return palettes.get(name, palettes['default'])

"""
gleplot - Matplotlib-like plotting library for GLE

A Python library for creating scientific plots using matplotlib-like syntax
that compiles directly to GLE (Graphics Layout Engine) format for publication-
quality vector graphics.

Features
--------
- Matplotlib-compatible API (plot, scatter, bar, fill_between)
- Native vector graphics output (PDF, PNG, EPS)
- Support for line styles, markers, and colors
- Logarithmic scales
- Legend and axis labels
- Direct GLE script generation

Usage
-----
    import gleplot as glp
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    ax.plot([1, 2, 3], [1, 4, 9], 'b-', label='quadratic')
    ax.scatter([1, 2, 3], [1, 2, 3], color='red', label='points')
    
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_title('Example Plot')
    ax.legend()
    
    fig.savefig('output.pdf')  # Saves as PDF
    fig.savefig('output.gle')  # Saves as GLE script only

Classes
-------
Figure
    Matplotlib-like figure container
Axes
    Matplotlib-like axes for plotting
    
Functions
---------
figure(figsize=(8, 6), dpi=100)
    Create a new figure
"""

__version__ = '0.1.0'
__author__ = 'gleplot contributors'

from .figure import Figure
from .axes import Axes
from .colors import rgb_to_gle, get_color_palette
from .markers import get_gle_marker
from .compiler import GLECompiler
from .config import (
    GLEStyleConfig,
    GLEGraphConfig,
    GLEMarkerConfig,
    GlobalConfig,
)

# Module-level convenience functions (for matplotlib compatibility)

_current_figure = None


def figure(figsize=(8, 6), dpi=100, style=None, graph=None, marker=None) -> Figure:
    """
    Create a new figure.
    
    Parameters
    ----------
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (8, 6)
    dpi : int, optional
        Dots per inch. Default: 100
    style : GLEStyleConfig, optional
        Style configuration. If None, uses global default.
    graph : GLEGraphConfig, optional
        Graph configuration. If None, uses global default.
    marker : GLEMarkerConfig, optional
        Marker configuration. If None, uses global default.
        
    Returns
    -------
    Figure
        New figure object
        
    Examples
    --------
    Create a figure with default settings:
    
    >>> fig = glp.figure()
    
    Create a figure with custom style:
    
    >>> style = glp.GLEStyleConfig(font='helvetica', fontsize=12)
    >>> fig = glp.figure(style=style)
    
    Or modify global defaults:
    
    >>> glp.GlobalConfig.style.font = 'helvetica'
    >>> fig = glp.figure()  # Will use helvetica font
    """
    global _current_figure
    _current_figure = Figure(figsize=figsize, dpi=dpi, style=style, graph=graph, marker=marker)
    return _current_figure


def gca():
    """Get current axes."""
    if _current_figure is None:
        figure()
    return _current_figure.gca()


def gcf():
    """Get current figure."""
    if _current_figure is None:
        figure()
    return _current_figure


def plot(*args, **kwargs):
    """Plot on current axes."""
    return gca().plot(*args, **kwargs)


def scatter(*args, **kwargs):
    """Scatter on current axes."""
    return gca().scatter(*args, **kwargs)


def bar(*args, **kwargs):
    """Bar chart on current axes."""
    return gca().bar(*args, **kwargs)


def fill_between(*args, **kwargs):
    """Fill between on current axes."""
    return gca().fill_between(*args, **kwargs)


def xlabel(label: str):
    """Set x label on current axes."""
    return gca().set_xlabel(label)


def ylabel(label: str):
    """Set y label on current axes."""
    return gca().set_ylabel(label)


def title(label: str):
    """Set title on current axes."""
    return gca().set_title(label)


def legend(**kwargs):
    """Add legend to current axes."""
    return gca().legend(**kwargs)


def savefig(filepath: str, **kwargs):
    """Save current figure."""
    return gcf().savefig(filepath, **kwargs)


def show():
    """Show current figure (placeholder)."""
    print(f"Figure saved to {gcf().figsize}")


def close(fig=None):
    """Close figure."""
    global _current_figure
    if fig is None:
        if _current_figure:
            _current_figure.close()
            _current_figure = None
    else:
        fig.close()


__all__ = [
    'Figure',
    'Axes',
    'figure',
    'gca',
    'gcf',
    'plot',
    'scatter',
    'bar',
    'fill_between',
    'xlabel',
    'ylabel',
    'title',
    'legend',
    'savefig',
    'show',
    'close',
    'rgb_to_gle',
    'get_color_palette',
    'get_gle_marker',
    'GLECompiler',
    'GLEStyleConfig',
    'GLEGraphConfig',
    'GLEMarkerConfig',
    'GlobalConfig',
]

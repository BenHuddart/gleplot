"""
gleplot - Matplotlib-like plotting library for GLE

A Python library for creating scientific plots using matplotlib-like syntax
that compiles directly to GLE (Graphics Layout Engine) format for publication-
quality vector graphics.

Features
--------
- Matplotlib-compatible API (plot, scatter, bar, fill_between, errorbar)
- Subplots with flexible grid layouts (subplots, add_subplot)
- Native vector graphics output (PDF, PNG, EPS)
- Support for line styles, markers, and colors
- Error bars (symmetric, asymmetric, horizontal)
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

__version__ = '0.1.5'
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


def figure(figsize=(8, 6), dpi=100, style=None, graph=None, marker=None, data_prefix=None) -> Figure:
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
    data_prefix : str, optional
        Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
        If None, uses global counter with ``data_`` prefix.
        
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
    _current_figure = Figure(figsize=figsize, dpi=dpi, style=style, graph=graph, marker=marker, data_prefix=data_prefix)
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


def errorbar(*args, **kwargs):
    """Error bar plot on current axes."""
    return gca().errorbar(*args, **kwargs)


def subplots(nrows: int = 1, ncols: int = 1, figsize=None, dpi=100,
             style=None, graph=None, marker=None,
             sharex: bool = False, sharey: bool = False,
             data_prefix=None):
    """
    Create a figure and a set of subplots.
    
    Convenience function matching ``matplotlib.pyplot.subplots()``.
    
    Parameters
    ----------
    nrows : int, optional
        Number of rows of subplots. Default: 1
    ncols : int, optional
        Number of columns of subplots. Default: 1
    figsize : tuple, optional
        Figure size (width, height) in inches. If None, auto-scales
        based on grid size (6 inches per column, 4 inches per row).
    dpi : int, optional
        Dots per inch. Default: 100
    style : GLEStyleConfig, optional
        Style configuration.
    graph : GLEGraphConfig, optional
        Graph configuration.
    marker : GLEMarkerConfig, optional
        Marker configuration.
    sharex : bool, optional
        If True, all subplots share the same x-axis. Only the bottom row
        will show x-axis labels and ticks. Default: False
    sharey : bool, optional
        If True, all subplots share the same y-axis. Only the leftmost column
        will show y-axis labels and ticks. Default: False
    data_prefix : str, optional
        Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
        If None, uses global counter with ``data_`` prefix.
    
    Returns
    -------
    fig : Figure
        The figure object.
    axes : Axes or list of Axes
        A single Axes if nrows*ncols == 1, otherwise a list of Axes
        arranged in row-major order.
    
    Examples
    --------
    Single plot:
    
    >>> fig, ax = glp.subplots()
    >>> ax.plot(x, y)
    
    2x2 grid:
    
    >>> fig, axes = glp.subplots(2, 2, figsize=(12, 10))
    >>> axes[0].plot(x, y1)   # top-left
    >>> axes[1].scatter(x, y2)  # top-right
    >>> axes[2].bar(x, y3)      # bottom-left
    >>> axes[3].plot(x, y4)     # bottom-right
    
    Shared x-axis (stacked plots):
    
    >>> fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 12))
    >>> # Only bottom subplot shows x-axis label and ticks
    """
    global _current_figure
    
    if figsize is None:
        figsize = (max(6, 6 * ncols), max(4, 4 * nrows))
    
    fig = Figure(figsize=figsize, dpi=dpi, style=style, graph=graph, marker=marker,
                 sharex=sharex, sharey=sharey, data_prefix=data_prefix)
    _current_figure = fig
    
    axes_list = []
    for idx in range(1, nrows * ncols + 1):
        ax = fig.add_subplot(nrows, ncols, idx)
        axes_list.append(ax)
    
    if len(axes_list) == 1:
        return fig, axes_list[0]
    return fig, axes_list


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
    'errorbar',
    'subplots',
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

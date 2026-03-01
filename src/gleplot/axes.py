"""Axes class for gleplot."""

import numpy as np
from typing import Optional, List, Union, Tuple
from .colors import rgb_to_gle
from .markers import get_gle_marker


class Axes:
    """Matplotlib-like axes for plotting."""
    
    def __init__(self, figure, position: Tuple[int, int, int] = None):
        """
        Initialize axes.
        
        Parameters
        ----------
        figure : Figure
            Parent figure
        position : tuple
            Subplot position (rows, cols, index) for future multi-plot support
        """
        self.figure = figure
        self.position = position
        
        # Axis properties
        self.xlabel_text = ''
        self.ylabel_text = ''
        self.title_text = ''
        self.xscale = 'linear'
        self.yscale = 'linear'
        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None
        self.legend_on = False
        self.legend_pos = 'top right'
        
        # Plot data storage
        self.lines = []  # List of line plot data
        self.scatters = []  # List of scatter plot data
        self.bars = []  # List of bar chart data
        self.fills = []  # List of fill_between data
        self.errorbars = []  # List of errorbar plot data
        
        self._line_counter = 0
    
    def plot(self, x, y, linestyle: str = '-', color: Optional[str] = None,
             marker: Optional[str] = None, markersize: float = 6,
             linewidth: float = 1, label: Optional[str] = None, **kwargs):
        """
        Plot line or scatter plot (if marker without line).
        
        Parameters
        ----------
        x, y : array-like
            Data coordinates
        linestyle : str
            Line style ('-', '--', ':', '-.')
        color : str, optional
            Color name or code ('b', 'red', etc.)
        marker : str, optional
            Marker symbol ('o', 's', '^', etc.) - omit for line only
        markersize : float
            Marker size (matplotlib convention, 1-100)
        linewidth : float
            Line width
        label : str, optional
            Legend label
        **kwargs
            Additional matplotlib-compatible arguments
        
        Returns
        -------
        Line2D
            Line object (for compatibility)
        """
        x = np.asarray(x)
        y = np.asarray(y)
        
        # Handle color
        if color is None:
            color = 'BLUE'
        else:
            color = rgb_to_gle(color)
        
        # Handle marker
        is_scatter = marker is not None and linestyle in ('', 'none', ' ', 'None')
        
        if is_scatter:
            gle_marker = get_gle_marker(marker)
            plot_type = 'scatter'
        else:
            gle_marker = None
            plot_type = 'line'
        
        # Scale markersize from matplotlib (1-100) to GLE msize (0.05-0.5)
        gle_markersize = markersize / 100 * 0.3
        
        line_data = {
            'type': plot_type,
            'x': x,
            'y': y,
            'color': color,
            'marker': gle_marker,
            'markersize': gle_markersize,
            'linestyle': linestyle,
            'linewidth': linewidth,
            'label': label,
            'data_file': f'data_{self._line_counter}.dat',
        }
        
        self._line_counter += 1
        
        if is_scatter:
            self.scatters.append(line_data)
        else:
            self.lines.append(line_data)
        
        return self  # Return self for method chaining
    
    def errorbar(self, x, y, yerr=None, xerr=None, fmt: str = '-',
                 color: Optional[str] = None, marker: Optional[str] = None,
                 markersize: float = 6, linewidth: float = 1,
                 label: Optional[str] = None, capsize: Optional[float] = None,
                 **kwargs):
        """
        Plot data with error bars.

        Parameters
        ----------
        x, y : array-like
            Data coordinates
        yerr : scalar, array-like, or tuple of (lower, upper), optional
            Vertical error bar sizes. Can be:
            - scalar: constant symmetric error for all points
            - 1D array: per-point symmetric error
            - tuple (lower, upper): per-point asymmetric error bars
        xerr : scalar, array-like, or tuple of (left, right), optional
            Horizontal error bar sizes. Same format as yerr.
        fmt : str
            Format string for the line/marker (e.g., '-o', '--s', 'none')
        color : str, optional
            Color name or code
        marker : str, optional
            Marker symbol ('o', 's', '^', etc.)
        markersize : float
            Marker size (matplotlib convention)
        linewidth : float
            Line width
        label : str, optional
            Legend label
        capsize : float, optional
            Width of error bar caps in GLE units (cm). Default: None (GLE default)
        **kwargs
            Additional arguments

        Returns
        -------
        self

        Examples
        --------
        Symmetric vertical error bars:

        >>> ax.errorbar(x, y, yerr=0.5)

        Asymmetric vertical error bars:

        >>> ax.errorbar(x, y, yerr=([0.2, 0.3], [0.5, 0.4]))

        Both vertical and horizontal error bars:

        >>> ax.errorbar(x, y, yerr=0.5, xerr=0.3)
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        # Handle color
        if color is None:
            color = 'BLUE'
        else:
            color = rgb_to_gle(color)

        # Parse fmt string for marker/linestyle
        # Simple parsing: check for marker chars and line styles
        parsed_marker = marker
        parsed_linestyle = fmt
        if fmt in ('', 'none', ' ', 'None'):
            parsed_linestyle = 'none'
        elif fmt == '-o' or fmt == 'o-':
            parsed_marker = parsed_marker or 'o'
            parsed_linestyle = '-'
        elif fmt == '-s' or fmt == 's-':
            parsed_marker = parsed_marker or 's'
            parsed_linestyle = '-'
        elif fmt in ('-', '--', ':', '-.'):
            parsed_linestyle = fmt
        elif len(fmt) == 1 and fmt in 'os^vD+x':
            parsed_marker = parsed_marker or fmt
            parsed_linestyle = 'none'

        # Determine GLE marker
        gle_marker = None
        if parsed_marker is not None:
            gle_marker = get_gle_marker(parsed_marker)

        # Scale markersize from matplotlib to GLE msize
        gle_markersize = markersize / 100 * 0.3

        # Process yerr
        yerr_up = None
        yerr_down = None
        if yerr is not None:
            if isinstance(yerr, (int, float)):
                # Scalar: constant symmetric error
                yerr_up = np.full(len(x), float(yerr))
                yerr_down = np.full(len(x), float(yerr))
            elif isinstance(yerr, (list, tuple)) and len(yerr) == 2:
                lower, upper = yerr
                lower = np.asarray(lower, dtype=float)
                upper = np.asarray(upper, dtype=float)
                if lower.ndim == 0:
                    yerr_down = np.full(len(x), float(lower))
                else:
                    yerr_down = lower
                if upper.ndim == 0:
                    yerr_up = np.full(len(x), float(upper))
                else:
                    yerr_up = upper
            else:
                # 1D array: symmetric error
                err_arr = np.asarray(yerr, dtype=float)
                yerr_up = err_arr
                yerr_down = err_arr

        # Process xerr
        xerr_left = None
        xerr_right = None
        if xerr is not None:
            if isinstance(xerr, (int, float)):
                xerr_left = np.full(len(x), float(xerr))
                xerr_right = np.full(len(x), float(xerr))
            elif isinstance(xerr, (list, tuple)) and len(xerr) == 2:
                left, right = xerr
                left = np.asarray(left, dtype=float)
                right = np.asarray(right, dtype=float)
                if left.ndim == 0:
                    xerr_left = np.full(len(x), float(left))
                else:
                    xerr_left = left
                if right.ndim == 0:
                    xerr_right = np.full(len(x), float(right))
                else:
                    xerr_right = right
            else:
                err_arr = np.asarray(xerr, dtype=float)
                xerr_left = err_arr
                xerr_right = err_arr

        errbar_data = {
            'type': 'errorbar',
            'x': x,
            'y': y,
            'yerr_up': yerr_up,
            'yerr_down': yerr_down,
            'xerr_left': xerr_left,
            'xerr_right': xerr_right,
            'color': color,
            'marker': gle_marker,
            'markersize': gle_markersize,
            'linestyle': parsed_linestyle,
            'linewidth': linewidth,
            'label': label,
            'capsize': capsize,
            'data_file': f'data_{self._line_counter}.dat',
        }

        self._line_counter += 1
        self.errorbars.append(errbar_data)

        return self

    def scatter(self, x, y, color: Optional[str] = None, s: float = 20,
                marker: str = 'o', label: Optional[str] = None, **kwargs):
        """
        Create scatter plot.
        
        Parameters
        ----------
        x, y : array-like
            Data coordinates
        color : str, optional
            Point color
        s : float
            Marker size (matplotlib convention)
        marker : str
            Marker symbol
        label : str, optional
            Legend label
        **kwargs
            Additional arguments
            
        Returns
        -------
        self
        """
        # scatter() uses 's' instead of markersize
        markersize = np.sqrt(s) * 2  # Rough conversion
        return self.plot(x, y, linestyle='none', color=color, marker=marker,
                        markersize=markersize, label=label)
    
    def bar(self, x, height, color: Optional[Union[str, List[str]]] = None,
            label: Optional[str] = None, **kwargs):
        """
        Create bar chart.
        
        Parameters
        ----------
        x : array-like
            Bar positions or categories
        height : array-like
            Bar heights
        color : str or list of str, optional
            Bar colors
        label : str, optional
            Legend label
        **kwargs
            Additional arguments
            
        Returns
        -------
        self
        """
        x = np.asarray(x, dtype=float)
        height = np.asarray(height, dtype=float)
        
        # Handle color
        if color is None:
            colors = ['RED'] * len(height)
        elif isinstance(color, str):
            colors = [rgb_to_gle(color)] * len(height)
        else:
            colors = [rgb_to_gle(c) for c in color]
        
        bar_data = {
            'x': x,
            'height': height,
            'colors': colors,
            'label': label,
            'data_file': f'data_{self._line_counter}.dat',
        }
        
        self._line_counter += 1
        self.bars.append(bar_data)
        
        return self
    
    def fill_between(self, x, y1, y2, color: Optional[str] = None,
                     alpha: float = 0.3, label: Optional[str] = None, **kwargs):
        """
        Fill area between two curves.
        
        Parameters
        ----------
        x : array-like
            x coordinates
        y1, y2 : array-like
            Two y series
        color : str, optional
            Fill color
        alpha : float
            Transparency (0-1)
        label : str, optional
            Legend label
        **kwargs
            Additional arguments
            
        Returns
        -------
        self
        """
        x = np.asarray(x)
        y1 = np.asarray(y1)
        y2 = np.asarray(y2)
        
        if color is None:
            color = 'LIGHTBLUE'
        else:
            color = rgb_to_gle(color)
        
        fill_data = {
            'x': x,
            'y1': y1,
            'y2': y2,
            'color': color,
            'alpha': alpha,
            'label': label,
            'data_file': f'data_{self._line_counter}.dat',
        }
        
        self._line_counter += 1
        self.fills.append(fill_data)
        
        return self
    
    def set_xlabel(self, label: str):
        """Set x-axis label."""
        self.xlabel_text = label
        return self
    
    def set_ylabel(self, label: str):
        """Set y-axis label."""
        self.ylabel_text = label
        return self
    
    def set_title(self, label: str):
        """Set subplot title."""
        self.title_text = label
        return self
    
    def set_xscale(self, scale: str):
        """Set x-axis scale ('linear' or 'log')."""
        self.xscale = scale
        return self
    
    def set_yscale(self, scale: str):
        """Set y-axis scale ('linear' or 'log')."""
        self.yscale = scale
        return self
    
    def set_xlim(self, xmin: float, xmax: float):
        """Set x-axis limits."""
        self.xmin = xmin
        self.xmax = xmax
        return self
    
    def set_ylim(self, ymin: float, ymax: float):
        """Set y-axis limits."""
        self.ymin = ymin
        self.ymax = ymax
        return self
    
    def legend(self, loc: str = 'best', **kwargs):
        """Add legend."""
        self.legend_on = True
        # Map matplotlib loc to GLE positions
        loc_map = {
            'best': 'top right',
            'upper right': 'top right',
            'upper left': 'top left',
            'lower left': 'bottom left',
            'lower right': 'bottom right',
            'center': 'center',
        }
        self.legend_pos = loc_map.get(loc, 'top right')
        return self
    
    def grid(self, visible: bool = True, **kwargs):
        """Toggle grid (placeholder for future implementation)."""
        # GLE grid support can be added later
        return self
    
    def get_xlim(self) -> Tuple[float, float]:
        """Get x-axis limits."""
        return self.xmin, self.xmax
    
    def get_ylim(self) -> Tuple[float, float]:
        """Get y-axis limits."""
        return self.ymin, self.ymax
    
    def has_plots(self) -> bool:
        """Check if axes has any plots."""
        return bool(self.lines or self.scatters or self.bars or self.fills or self.errorbars)

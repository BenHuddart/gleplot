"""Axes class for gleplot."""

import numpy as np
from typing import Optional, List, Union, Tuple
from .colors import rgb_to_gle
from .markers import get_gle_marker


# Global counter for unique data file names across all figures in a session
_global_data_file_counter = 0


def _get_next_data_file(figure=None):
    """Get next unique data file name.
    
    Parameters
    ----------
    figure : Figure, optional
        If provided and has a custom data_prefix, uses figure's local counter.
        Otherwise uses global counter.
    
    Returns
    -------
    str
        Data filename (e.g., 'data_5.dat' or 'mytest_2.dat')
    """
    if figure and figure.data_prefix:
        filename = f'{figure.data_prefix}_{figure._local_data_counter}.dat'
        figure._local_data_counter += 1
    else:
        global _global_data_file_counter
        filename = f'data_{_global_data_file_counter}.dat'
        _global_data_file_counter += 1
    return filename


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
        self.y2label_text = ''  # Secondary y-axis label
        self.title_text = ''
        self.xscale = 'linear'
        self.yscale = 'linear'
        self.y2scale = 'linear'  # Secondary y-axis scale
        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None
        self.y2min = None  # Secondary y-axis limits
        self.y2max = None
        self.legend_on = False
        self.legend_pos = 'top right'
        
        # Shared axes visibility control
        self._show_xlabel = True
        self._show_ylabel = True
        self._show_xticks = True
        self._show_yticks = True
        
        # Plot data storage
        self.lines = []  # List of line plot data
        self.scatters = []  # List of scatter plot data
        self.bars = []  # List of bar chart data
        self.fills = []  # List of fill_between data
        self.errorbars = []  # List of errorbar plot data
        self.file_series = []  # External-file series definitions (column references)
    
    def plot(self, x, y, linestyle: str = '-', color: Optional[str] = None,
             marker: Optional[str] = None, markersize: float = 6,
             linewidth: float = 1, label: Optional[str] = None,
             yaxis: str = 'y', **kwargs):
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
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
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
        
        # Scale markersize from matplotlib (typical 1-20, default 6) to GLE msize (0.05-0.5)
        # Formula: msize = markersize * 0.025 * scale_factor
        # Examples: markersize 6 → 0.15, markersize 10 → 0.25, markersize 20 → 0.5
        gle_markersize = markersize * 0.025 * self.figure.marker_config.msize_scale
        
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
            'yaxis': yaxis,  # 'y' or 'y2'
            'data_file': _get_next_data_file(self.figure),
        }
        
        if is_scatter:
            self.scatters.append(line_data)
        else:
            self.lines.append(line_data)
        
        return self  # Return self for method chaining
    
    def errorbar(self, x, y, yerr=None, xerr=None, fmt: str = '-',
                 color: Optional[str] = None, marker: Optional[str] = None,
                 markersize: float = 6, linewidth: float = 1,
                 label: Optional[str] = None, capsize: Optional[float] = None,
                 capsize_cm: Optional[float] = None,
                 yaxis: str = 'y',
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
            Marker size (matplotlib convention, 1-100)
        linewidth : float
            Line width
        label : str, optional
            Legend label
        capsize : float, optional
            Width of error bar caps in matplotlib points (typical: 3-5).
            Automatically converted to GLE cm units (points * 0.0353).
            Default: None (no caps)
        capsize_cm : float, optional
            Width of error bar caps directly in GLE cm units (typical: 0.05-0.15).
            If specified, this overrides `capsize`. Use this for direct control.
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
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

        # Scale markersize from matplotlib to GLE msize (with config scaling)
        gle_markersize = markersize * 0.025 * self.figure.marker_config.msize_scale

        # Convert capsize from matplotlib points to GLE cm
        # 1 point = 1/72 inch = 2.54/72 cm ≈ 0.0353 cm
        # Store the original capsize for the data structure, convert for GLE output
        gle_capsize = None
        stored_capsize = None
        if capsize_cm is not None:
            # Direct specification in cm takes precedence
            gle_capsize = capsize_cm
            stored_capsize = capsize_cm  # Store the cm value
        elif capsize is not None:
            # Convert from matplotlib points to cm for GLE
            gle_capsize = capsize * 0.0353
            stored_capsize = capsize  # Store original matplotlib value

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
            'capsize': stored_capsize,
            'gle_capsize': gle_capsize,  # Separate field for the GLE-converted value
            'yaxis': yaxis,  # 'y' or 'y2'
            'data_file': _get_next_data_file(self.figure),
        }
        self.errorbars.append(errbar_data)

        return self

    def errorbar_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        yerr_col: Optional[int] = None,
        color: Optional[str] = None,
        marker: Optional[str] = 'o',
        markersize: float = 6,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        yaxis: str = 'y',
    ):
        """Plot by referencing columns in an existing external data file.

        This avoids writing generated ``data_*.dat`` files. Column indices are
        1-based to match GLE conventions.
        """
        if x_col < 1 or y_col < 1 or (yerr_col is not None and yerr_col < 1):
            raise ValueError("Column indices must be >= 1")

        if color is None:
            gle_color = 'BLUE'
        else:
            gle_color = rgb_to_gle(color)

        gle_marker = get_gle_marker(marker) if marker else None
        gle_markersize = markersize * 0.025 * self.figure.marker_config.msize_scale
        gle_capsize = capsize * 0.0353 if capsize is not None else None

        self.file_series.append(
            {
                'data_file': data_file,
                'x_col': int(x_col),
                'y_col': int(y_col),
                'yerr_col': int(yerr_col) if yerr_col is not None else None,
                'color': gle_color,
                'marker': gle_marker,
                'markersize': gle_markersize,
                'label': label,
                'capsize': gle_capsize,
                'yaxis': yaxis,
            }
        )

        return self

    def scatter(self, x, y, color: Optional[str] = None, s: float = 20,
                marker: str = 'o', label: Optional[str] = None,
                yaxis: str = 'y', **kwargs):
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
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        **kwargs
            Additional arguments
            
        Returns
        -------
        self
        """
        # scatter() uses 's' instead of markersize
        # matplotlib scatter s is area in points^2, typical range 10-100, default ~36
        # Convert to markersize: since area ~ size^2, markersize ~ sqrt(s)
        # Use factor of 1.2 for better visibility
        markersize = np.sqrt(s) * 1.2
        return self.plot(x, y, linestyle='none', color=color, marker=marker,
                        markersize=markersize, label=label, yaxis=yaxis)
    
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
            'data_file': _get_next_data_file(self.figure),
        }
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
            'data_file': _get_next_data_file(self.figure),
        }
        self.fills.append(fill_data)
        
        return self
    
    def set_xlabel(self, label: str):
        """Set x-axis label."""
        self.xlabel_text = label
        return self
    
    def set_ylabel(self, label: str, axis: str = 'y'):
        """Set y-axis label.
        
        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == 'y2':
            self.y2label_text = label
        else:
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
    
    def set_yscale(self, scale: str, axis: str = 'y'):
        """Set y-axis scale.
        
        Parameters
        ----------
        scale : str
            Scale type: 'linear' or 'log'
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == 'y2':
            self.y2scale = scale
        else:
            self.yscale = scale
        return self
    
    def set_xlim(self, xmin: float, xmax: float):
        """Set x-axis limits."""
        self.xmin = xmin
        self.xmax = xmax
        return self
    
    def set_ylim(self, ymin: float, ymax: float, axis: str = 'y'):
        """Set y-axis limits.
        
        Parameters
        ----------
        ymin, ymax : float
            Axis limits
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == 'y2':
            self.y2min = ymin
            self.y2max = ymax
        else:
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
    
    def get_ylim(self, axis: str = 'y') -> Tuple[float, float]:
        """Get y-axis limits.
        
        Parameters
        ----------
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == 'y2':
            return self.y2min, self.y2max
        else:
            return self.ymin, self.ymax
    
    def has_plots(self) -> bool:
        """Check if axes has any plots."""
        return bool(self.lines or self.scatters or self.bars or self.fills or self.errorbars or self.file_series)
    
    def has_y2_plots(self) -> bool:
        """Check if axes has any plots using the y2 axis."""
        for plot_list in [self.lines, self.scatters, self.errorbars]:
            for plot_data in plot_list:
                if plot_data.get('yaxis') == 'y2':
                    return True
        return False

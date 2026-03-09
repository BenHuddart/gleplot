"""Figure class for gleplot."""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Literal
from .axes import Axes
from .writer import GLEWriter
from .compiler import GLECompiler
from .colors import rgb_to_gle
from .config import GLEStyleConfig, GLEGraphConfig, GLEMarkerConfig, GlobalConfig


class Figure:
    """Matplotlib-like figure for GLE plotting.
    
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
    """
    
    def __init__(self, figsize: Tuple[float, float] = (8, 6), dpi: int = 100,
                 style: Optional[GLEStyleConfig] = None,
                 graph: Optional[GLEGraphConfig] = None,
                 marker: Optional[GLEMarkerConfig] = None,
                 sharex: bool = False,
                 sharey: bool = False,
                 data_prefix: Optional[str] = None):
        """Initialize figure with optional configuration objects.
        
        Parameters
        ----------
        data_prefix : str, optional
            Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
            If None, uses global counter with ``data_`` prefix.
        """
        self.figsize = figsize
        self.dpi = dpi
        
        # Store configuration for passing to writer
        self.style = style or GlobalConfig.get_style()
        self.graph = graph or GlobalConfig.get_graph()
        self.marker_config = marker or GlobalConfig.get_marker()
        
        # Shared axes configuration
        self.sharex = sharex
        self.sharey = sharey
        
        # Custom data file naming
        self.data_prefix = data_prefix
        self._local_data_counter = 0  # Local counter when using custom prefix
        
        self.axes_list = []  # List of Axes objects
        self._current_axes = None  # Current working axes
        
        self.compiler = None
        try:
            self.compiler = GLECompiler()
        except RuntimeError:
            pass  # GLE not available, but can still write scripts
    
    def add_subplot(self, *args) -> Axes:
        """
        Add subplot to figure.
        
        Parameters
        ----------
        *args : int
            Subplot specification (rows, cols, index) or single int
            E.g., add_subplot(2, 2, 1) or add_subplot(221)
            
        Returns
        -------
        Axes
            New axes object
        """
        if len(args) == 1 and isinstance(args[0], int):
            # Parse single int format (e.g., 221)
            spec = str(args[0])
            if len(spec) == 3:
                rows, cols, idx = int(spec[0]), int(spec[1]), int(spec[2])
            else:
                raise ValueError(f"Invalid subplot spec: {args[0]}")
        else:
            rows, cols, idx = args
        
        ax = Axes(self, (rows, cols, idx))
        
        # Configure shared axes visibility
        # Convert 1-based index to row/col
        row = (idx - 1) // cols   # 0-based, 0 = top row
        col = (idx - 1) % cols    # 0-based, 0 = left col
        
        if self.sharex:
            # Only show x-axis labels/ticks on bottom row
            ax._show_xlabel = (row == rows - 1)
            ax._show_xticks = (row == rows - 1)
            # Remove last x-tick label if not the bottom row (to prevent overlap when subplots touch)
            ax._remove_last_xtick = (row < rows - 1)
            ax._remove_first_xtick = False
            # When sharing x, y-axes touch vertically - remove last (top) y-label from all but top row
            # (highest y-label of lower plots could overlap upward into the plot above)
            ax._remove_last_ytick = (row > 0)
            ax._remove_first_ytick = False
        else:
            ax._show_xlabel = True
            ax._show_xticks = True
            ax._remove_last_xtick = False
            ax._remove_first_xtick = False
            ax._remove_last_ytick = False
            ax._remove_first_ytick = False
        
        if self.sharey:
            # Only show y-axis labels/ticks on leftmost column
            ax._show_ylabel = (col == 0)
            ax._show_yticks = (col == 0)
            # When sharing y, x-axes touch horizontally - remove last x-label from all but rightmost
            ax._remove_last_xtick = (col < cols - 1)
            ax._remove_first_xtick = False
            # Y-axis labels don't overlap in horizontal arrangement (only shown on leftmost)
            # No need to remove first/last y-labels when plots are side-by-side
            if not self.sharex:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
        else:
            ax._show_ylabel = True
            ax._show_yticks = True
            if not self.sharex:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
            if not self.sharex:
                ax._remove_last_xtick = False
                ax._remove_first_xtick = False
                ax._remove_first_xtick = False
        
        self.axes_list.append(ax)
        self._current_axes = ax
        return ax
    
    def gca(self) -> Axes:
        """Get current axes (or create if needed)."""
        if self._current_axes is None:
            self.add_subplot(111)
        return self._current_axes
    
    # Convenience plotting methods (plot on current axes)
    
    def plot(self, x, y, **kwargs):
        """Plot on current axes."""
        return self.gca().plot(x, y, **kwargs)
    
    def scatter(self, x, y, **kwargs):
        """Scatter on current axes."""
        return self.gca().scatter(x, y, **kwargs)
    
    def bar(self, x, height, **kwargs):
        """Bar chart on current axes."""
        return self.gca().bar(x, height, **kwargs)
    
    def fill_between(self, x, y1, y2, **kwargs):
        """Fill between on current axes."""
        return self.gca().fill_between(x, y1, y2, **kwargs)
    
    def errorbar(self, x, y, **kwargs):
        """Error bar plot on current axes."""
        return self.gca().errorbar(x, y, **kwargs)
    
    def xlabel(self, label: str):
        """Set x label on current axes."""
        return self.gca().set_xlabel(label)
    
    def ylabel(self, label: str, axis: str = 'y'):
        """Set y label on current axes.
        
        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        return self.gca().set_ylabel(label, axis=axis)
    
    def title(self, label: str):
        """Set title on current axes."""
        return self.gca().set_title(label)
    
    def legend(self, **kwargs):
        """Add legend to current axes."""
        return self.gca().legend(**kwargs)
    
    # File I/O methods
    
    def savefig_gle(self, filepath: str, **kwargs) -> Path:
        """
        Save figure as GLE script.
        
        Parameters
        ----------
        filepath : str
            Output file path
        **kwargs
            Additional options
            
        Returns
        -------
        Path
            Path to created GLE file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate and save GLE content with data files
        gle_content, data_content = self._generate_gle_with_files()
        
        # Write script
        filepath.write_text(gle_content)
        
        # Write data files in same directory
        for filename, content in data_content.items():
            data_file = filepath.parent / filename
            data_file.write_text(content)
        
        return filepath
    
    def savefig(self, filepath: str, format: Optional[str] = None,
                dpi: Optional[int] = None, **kwargs) -> Path:
        """
        Save figure as GLE script and/or compiled output.
        
        Parameters
        ----------
        filepath : str
            Output file path
        format : {'pdf', 'png', 'eps'}, optional
            Output format. If None, saves as .gle script only.
            If format given but file ext different, uses format.
        dpi : int, optional
            DPI for raster formats
        **kwargs
            Additional arguments
            
        Returns
        -------
        Path
            Path to output file (GLE script or compiled output)
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine output format
        if format is None:
            if filepath.suffix == '.gle':
                format = 'gle'
            elif filepath.suffix == '.pdf':
                format = 'pdf'
            elif filepath.suffix == '.png':
                format = 'png'
            elif filepath.suffix == '.eps':
                format = 'eps'
            else:
                format = 'gle'  # Default
        
        # Write GLE script and data files
        base_path = filepath.with_suffix('.gle')
        gle_content, data_files = self._generate_gle_with_files()
        base_path.write_text(gle_content)
        
        # Write data files in same directory
        for filename, content in data_files.items():
            data_file = base_path.parent / filename
            data_file.write_text(content)
        
        # Compile if needed
        if format != 'gle':
            if not self.compiler:
                raise RuntimeError(
                    "GLE compiler not available. "
                    "Install GLE or use savefig_gle() to save script only."
                )
            
            output_dpi = dpi or self.dpi
            output_path = filepath.with_suffix(f'.{format}')
            self.compiler.compile(str(base_path), format, dpi=output_dpi)
            return output_path
        
        return base_path
    
    def _generate_gle(self) -> str:
        """Generate complete GLE script content."""
        content, _ = self._generate_gle_with_files()
        return content
    
    def _generate_gle_with_files(self) -> tuple:
        """
        Generate complete GLE script content with data files.
        
        Supports both single-plot and multi-subplot layouts.
        For a single axes (1,1,1), generates a simple graph block.
        For multiple axes, positions each graph using ``amove`` and
        explicit ``size`` commands based on the subplot grid.
        
        Uses figure's configured style, graph, and marker settings.
        
        Returns
        -------
        tuple
            (gle_content, data_files_dict)
        """
        # Pass configuration to writer
        writer = GLEWriter(self.figsize, self.dpi,
                          style=self.style,
                          graph=self.graph,
                          marker=self.marker_config)
        
        is_single = (len(self.axes_list) <= 1)
        
        if is_single:
            # Single plot — backward-compatible simple layout
            writer.add_preamble(include_graph_begin=True)
            writer.add_graph_size()
            
            if self.axes_list:
                self._write_axes_content(writer, self.axes_list[0])
            
            writer.finalize(include_graph_end=True)
        else:
            # Multi-subplot layout
            writer.add_preamble(include_graph_begin=False)
            
            # Determine grid dimensions from axes positions
            max_rows = max(ax.position[0] for ax in self.axes_list)
            max_cols = max(ax.position[1] for ax in self.axes_list)
            
            # Synchronize axis limits for shared axes
            if self.sharex:
                self._synchronize_x_limits()
            if self.sharey:
                self._synchronize_y_limits()
            
            # Calculate per-subplot dimensions in cm
            # Smart margins based on what labels are shown and subplot content
            
            # Check if any subplot has a title
            has_titles = any(ax.title_text for ax in self.axes_list)
            
            if self.sharex or self.sharey:
                # Top margin: more room needed if subplots have titles
                margin_top = 1.2 if has_titles else 0.5
                margin_right = 0.5
                # Bottom needs room for x-axis labels (when showing them)
                margin_bottom = 1.5 if self.sharex else 1.0
                # Left always needs room for y-axis labels in multi-subplot layouts
                margin_left = 1.5
            else:
                # Normal margins for non-shared layouts
                margin_top = 1.5 if has_titles else 1.0
                margin_bottom = 1.0
                margin_left = 1.0
                margin_right = 1.0
            
            # Spacing between subplots (cm) - zero when axes are shared (subplots touch)
            # When subplots touch, we use GLE commands like 'nolast' to remove overlapping labels
            if self.sharey:
                hspace = 0.0  # No gap - subplots touch when sharing y-axis
            else:
                hspace = 1.5
            
            if self.sharex:
                vspace = 0.0  # No gap - subplots touch when sharing x-axis
            else:
                vspace = 2.0
            
            usable_w = writer.width_cm - margin_left - margin_right - (max_cols - 1) * hspace
            usable_h = writer.height_cm - margin_bottom - margin_top - (max_rows - 1) * vspace
            
            cell_w = usable_w / max_cols
            cell_h = usable_h / max_rows
            
            for ax in self.axes_list:
                rows, cols, idx = ax.position
                # Convert 1-based index to row/col (row-major, top-to-bottom)
                row = (idx - 1) // cols   # 0-based, 0 = top row
                col = (idx - 1) % cols    # 0-based, 0 = left col
                
                # GLE coordinates: origin is bottom-left, y increases upward
                x_pos = margin_left + col * (cell_w + hspace)
                y_pos = writer.height_cm - margin_top - (row + 1) * cell_h - row * vspace
                
                writer.add_amove(x_pos, y_pos)
                writer.begin_graph()
                writer.add_graph_size(width_cm=cell_w, height_cm=cell_h,
                                      force_size=True)
                
                self._write_axes_content(writer, ax)
                
                writer.end_graph()
                writer.lines_gle.append('')  # Blank line between subplots
            
            writer.finalize(include_graph_end=False)
        
        return writer.get_gle_content(), writer.data_files
    
    def _write_axes_content(self, writer: GLEWriter, ax: Axes):
        """
        Write all plot content for a single Axes into the current graph block.
        
        This method is shared between single-plot and multi-subplot paths.
        
        Parameters
        ----------
        writer : GLEWriter
            The GLE writer to append commands to.
        ax : Axes
            The axes whose content should be written.
        """
        # Axis properties
        writer.add_axes(
            xlabel=ax.xlabel_text or None,
            ylabel=ax.ylabel_text or None,
            y2label=ax.y2label_text or None,
            title=ax.title_text or None,
            xlog=(ax.xscale == 'log'),
            ylog=(ax.yscale == 'log'),
            y2log=(ax.y2scale == 'log'),
            xmin=ax.xmin,
            xmax=ax.xmax,
            ymin=ax.ymin,
            ymax=ax.ymax,
            y2min=ax.y2min,
            y2max=ax.y2max,
            show_xlabel=ax._show_xlabel,
            show_ylabel=ax._show_ylabel,
            show_xticks=ax._show_xticks,
            show_yticks=ax._show_yticks,
            remove_last_xtick=getattr(ax, '_remove_last_xtick', False),
            remove_last_ytick=getattr(ax, '_remove_last_ytick', False),
            remove_first_xtick=getattr(ax, '_remove_first_xtick', False),
            remove_first_ytick=getattr(ax, '_remove_first_ytick', False),
        )
        
        # Add fill regions (background)
        for fill_data in ax.fills:
            writer.add_fill_between(
                fill_data['x'],
                fill_data['y1'],
                fill_data['y2'],
                fill_data['data_file'],
                fill_data['color'],
                fill_data['alpha']
            )
        
        # Add bar charts
        for bar_data in ax.bars:
            writer.add_bar_chart(
                bar_data['x'],
                bar_data['height'],
                bar_data['data_file'],
                bar_data['colors'],
                bar_data['label']
            )
        
        # Add line plots
        for line_data in ax.lines:
            writer.add_plot_line(
                line_data['x'],
                line_data['y'],
                line_data['data_file'],
                color=line_data['color'],
                linestyle=line_data['linestyle'],
                linewidth=line_data['linewidth'],
                label=line_data['label'],
                yaxis=line_data.get('yaxis', 'y'),
            )
        
        # Add scatter plots
        for scatter_data in ax.scatters:
            writer.add_plot_line(
                scatter_data['x'],
                scatter_data['y'],
                scatter_data['data_file'],
                color=scatter_data['color'],
                marker=scatter_data['marker'],
                markersize=scatter_data['markersize'],
                label=scatter_data['label'],
                yaxis=scatter_data.get('yaxis', 'y'),
            )
        
        # Add errorbar plots
        for eb_data in ax.errorbars:
            writer.add_errorbar(
                eb_data['x'],
                eb_data['y'],
                eb_data['data_file'],
                color=eb_data['color'],
                linestyle=eb_data['linestyle'],
                linewidth=eb_data['linewidth'],
                label=eb_data['label'],
                marker=eb_data['marker'],
                markersize=eb_data['markersize'],
                yerr_up=eb_data['yerr_up'],
                yerr_down=eb_data['yerr_down'],
                xerr_left=eb_data['xerr_left'],
                xerr_right=eb_data['xerr_right'],
                capsize=eb_data.get('gle_capsize', eb_data.get('capsize')),
                yaxis=eb_data.get('yaxis', 'y'),
            )

        # Add external-file series (no generated data files).
        for fs_data in ax.file_series:
            writer.add_errorbar_from_file(
                fs_data['data_file'],
                fs_data['x_col'],
                fs_data['y_col'],
                yerr_col=fs_data.get('yerr_col'),
                color=fs_data['color'],
                marker=fs_data.get('marker'),
                markersize=fs_data.get('markersize', 0.1),
                label=fs_data.get('label'),
                capsize=fs_data.get('capsize'),
                yaxis=fs_data.get('yaxis', 'y'),
            )
        
        # Add legend if needed
        legend_sources = ax.lines + ax.scatters + ax.bars + ax.errorbars + ax.file_series
        if ax.legend_on or any(series.get('label') for series in legend_sources):
            writer.add_legend(ax.legend_pos)
    
    def _synchronize_x_limits(self):
        """Synchronize x-axis limits across all axes when sharex is enabled."""
        # Find global x-axis limits
        xmin_global = None
        xmax_global = None
        
        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.xmin is None or ax.xmax is None:
                data_xmin, data_xmax = self._get_data_xlim(ax)
                if ax.xmin is None:
                    ax.xmin = data_xmin
                if ax.xmax is None:
                    ax.xmax = data_xmax
            
            # Track global limits
            if ax.xmin is not None:
                if xmin_global is None or ax.xmin < xmin_global:
                    xmin_global = ax.xmin
            if ax.xmax is not None:
                if xmax_global is None or ax.xmax > xmax_global:
                    xmax_global = ax.xmax
        
        # Apply global limits to all axes
        for ax in self.axes_list:
            ax.xmin = xmin_global
            ax.xmax = xmax_global
    
    def _synchronize_y_limits(self):
        """Synchronize y-axis limits across all axes when sharey is enabled."""
        # Find global y-axis limits
        ymin_global = None
        ymax_global = None
        
        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.ymin is None or ax.ymax is None:
                data_ymin, data_ymax = self._get_data_ylim(ax)
                if ax.ymin is None:
                    ax.ymin = data_ymin
                if ax.ymax is None:
                    ax.ymax = data_ymax
            
            # Track global limits
            if ax.ymin is not None:
                if ymin_global is None or ax.ymin < ymin_global:
                    ymin_global = ax.ymin
            if ax.ymax is not None:
                if ymax_global is None or ax.ymax > ymax_global:
                    ymax_global = ax.ymax
        
        # Apply global limits to all axes
        for ax in self.axes_list:
            ax.ymin = ymin_global
            ax.ymax = ymax_global
    
    def _get_data_xlim(self, ax: Axes) -> Tuple[Optional[float], Optional[float]]:
        """Calculate x-axis limits from data."""
        xmin, xmax = None, None
        
        for data_list in [ax.lines, ax.scatters, ax.bars, ax.errorbars]:
            for data in data_list:
                x = np.asarray(data['x'])
                if len(x) > 0:
                    if xmin is None or x.min() < xmin:
                        xmin = float(x.min())
                    if xmax is None or x.max() > xmax:
                        xmax = float(x.max())
        
        for fill_data in ax.fills:
            x = np.asarray(fill_data['x'])
            if len(x) > 0:
                if xmin is None or x.min() < xmin:
                    xmin = float(x.min())
                if xmax is None or x.max() > xmax:
                    xmax = float(x.max())
        
        return xmin, xmax
    
    def _get_data_ylim(self, ax: Axes) -> Tuple[Optional[float], Optional[float]]:
        """Calculate y-axis limits from data."""
        ymin, ymax = None, None
        
        for data_list in [ax.lines, ax.scatters]:
            for data in data_list:
                y = np.asarray(data['y'])
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())
        
        for bar_data in ax.bars:
            height = np.asarray(bar_data['height'])
            if len(height) > 0:
                if ymin is None or height.min() < ymin:
                    ymin = float(min(0, height.min()))
                if ymax is None or height.max() > ymax:
                    ymax = float(height.max())
        
        for fill_data in ax.fills:
            y1 = np.asarray(fill_data['y1'])
            y2 = np.asarray(fill_data['y2'])
            all_y = np.concatenate([y1, y2])
            if len(all_y) > 0:
                if ymin is None or all_y.min() < ymin:
                    ymin = float(all_y.min())
                if ymax is None or all_y.max() > ymax:
                    ymax = float(all_y.max())
        
        for eb_data in ax.errorbars:
            y = np.asarray(eb_data['y'])
            yerr_up = eb_data.get('yerr_up')
            yerr_down = eb_data.get('yerr_down')
            
            if len(y) > 0:
                y_with_err = y.copy()
                if yerr_up is not None:
                    y_with_err_up = y + np.asarray(yerr_up)
                    if ymax is None or y_with_err_up.max() > ymax:
                        ymax = float(y_with_err_up.max())
                if yerr_down is not None:
                    y_with_err_down = y - np.asarray(yerr_down)
                    if ymin is None or y_with_err_down.min() < ymin:
                        ymin = float(y_with_err_down.min())
                
                if ymin is None or y.min() < ymin:
                    ymin = float(y.min())
                if ymax is None or y.max() > ymax:
                    ymax = float(y.max())
        
        return ymin, ymax
    
    def view(self, dpi: Optional[int] = None, format: str = 'png') -> Optional[object]:
        """
        Display the figure inline (in Jupyter notebooks) or save to a temporary file.
        
        This method renders the figure to an image format and displays it if running
        in a Jupyter notebook or IPython environment. Otherwise, it saves to a
        temporary file and returns the path.
        
        Parameters
        ----------
        dpi : int, optional
            Resolution in dots per inch. If None, uses figure's dpi setting.
        format : {'png', 'pdf'}, optional
            Output format. Default is 'png' for inline display.
            
        Returns
        -------
        Path or None
            Path to the generated file, or None when displayed inline in Jupyter.
            
        Raises
        ------
        RuntimeError
            If GLE compiler is not available.
            
        Examples
        --------
        >>> import gleplot as glp
        >>> fig = glp.figure()
        >>> ax = fig.add_subplot(111)
        >>> ax.plot([1, 2, 3], [1, 4, 9])
        >>> fig.view()  # Display in notebook
        
        Notes
        -----
        Requires GLE to be installed for compilation.
        In non-Jupyter environments, saves to a temporary file instead.
        """
        import tempfile
        
        if not self.compiler:
            raise RuntimeError(
                "GLE compiler not available. Install GLE to use view()."
            )
        
        output_dpi = dpi or self.dpi
        
        # Try to detect Jupyter/IPython environment
        try:
            from IPython import get_ipython
            from IPython.display import Image, display
            
            ipython = get_ipython()
            in_notebook = ipython is not None and 'IPKernelApp' in get_ipython().config
        except ImportError:
            in_notebook = False
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            # Save to temporary file
            self.savefig(str(tmp_path), format=format, dpi=output_dpi)
            
            if in_notebook:
                # Display inline in Jupyter
                if format == 'png':
                    img = Image(filename=str(tmp_path))
                    display(img)
                    return None
                elif format == 'pdf':
                    # For PDF, try to display or provide a link
                    print(f"PDF saved to: {tmp_path}")
                    print("Note: PDF inline display limited in Jupyter. Consider using 'png' format.")
                    return tmp_path
            else:
                # Not in notebook - inform user of temp file location
                print(f"Plot saved to temporary file: {tmp_path}")
                print(f"Open this file to view the plot.")
                return tmp_path
                
        except Exception as e:
            # Clean up on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise e
    
    def close(self):
        """Close figure."""
        self.axes_list.clear()
        self._current_axes = None

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
                 marker: Optional[GLEMarkerConfig] = None):
        """Initialize figure with optional configuration objects."""
        self.figsize = figsize
        self.dpi = dpi
        
        # Store configuration for passing to writer
        self.style = style or GlobalConfig.get_style()
        self.graph = graph or GlobalConfig.get_graph()
        self.marker_config = marker or GlobalConfig.get_marker()
        
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
    
    def xlabel(self, label: str):
        """Set x label on current axes."""
        return self.gca().set_xlabel(label)
    
    def ylabel(self, label: str):
        """Set y label on current axes."""
        return self.gca().set_ylabel(label)
    
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
        
        writer.add_preamble()
        # Use auto-calculated graph size based on figure size
        writer.add_graph_size()
        
        # Add first axes (multi-axis support for future)
        if self.axes_list:
            ax = self.axes_list[0]
            
            # Axis properties
            writer.add_axes(
                xlabel=ax.xlabel_text or None,
                ylabel=ax.ylabel_text or None,
                title=ax.title_text or None,
                xlog=(ax.xscale == 'log'),
                ylog=(ax.yscale == 'log'),
                xmin=ax.xmin,
                xmax=ax.xmax,
                ymin=ax.ymin,
                ymax=ax.ymax,
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
                )
            
            # Add legend if needed
            if ax.legend_on or any(l.get('label') for l in ax.lines + ax.scatters + ax.bars):
                writer.add_legend(ax.legend_pos)
        
        writer.finalize()
        
        return writer.get_gle_content(), writer.data_files
    
    def close(self):
        """Close figure."""
        self.axes_list.clear()
        self._current_axes = None

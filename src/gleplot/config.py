"""Configuration and style settings for gleplot."""

from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class GLEStyleConfig:
    """GLE rendering style configuration.
    
    Attributes
    ----------
    font : str
        GLE font name (e.g., 'texcmr', 'timesroman', 'helvetica').
        Default: 'texcmr' (TeX Computer Modern Roman font)
    
    fontsize : float
        Font size in points. Default: 10
    
    default_linewidth : float
        Default line width in points (unit: 1/72 inch).
        Default: 1.0 point ≈ 0.035 cm
    
    default_color : str
        Default line/plot color (GLE color name). Default: 'BLUE'
    
    default_marker_color : str
        Default marker color. Default: 'BLUE'
    
    line_style_solid : int
        GLE line style for solid lines. Default: 1
    
    line_style_dashed : int
        GLE line style for dashed lines (--). Default: 2
    
    line_style_dotted : int
        GLE line style for dotted lines (:). Default: 3
    
    line_style_dashdot : int
        GLE line style for dash-dot lines (-.). Default: 4
    """
    font: str = 'texcmr'
    fontsize: float = 10
    default_linewidth: float = 1.0
    default_color: str = 'BLUE'
    default_marker_color: str = 'BLUE'
    line_style_solid: int = 1
    line_style_dashed: int = 2
    line_style_dotted: int = 3
    line_style_dashdot: int = 4
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


@dataclass
class GLEGraphConfig:
    """GLE graph configuration.
    
    Attributes
    ----------
    scale_mode : str
        Graph scaling mode: 'auto' (auto-sizes and centers), 'fixed' (uses specified size),
        or 'fullsize' (axes fill entire box, no margins). Default: 'auto'
    
    title_distance : float
        Distance (cm) from graph top to title. Default: 0.1
    
    xlabel_distance : float
        Distance (cm) from graph bottom to x-axis label. Default: 0.1
    
    ylabel_distance : float
        Distance (cm) from graph left to y-axis label. Default: 0.1
    
    legend_position : str
        Default legend position: 'tl', 'tr', 'bl', 'br', 'tc', 'bc', 'lc', 'rc', 'cc'.
        Options: 'top right', 'top left', 'bottom right', 'bottom left', 'center'.
        Default: 'tr' (top right)
    
    legend_offset_x : float
        Legend x-offset from position (cm). Default: 0.0
    
    legend_offset_y : float
        Legend y-offset from position (cm). Default: 0.0
    
    smooth_curves : bool
        Enable smooth curve fitting on line plots (GLE smooth keyword).
        Default: True
    
    show_grid : bool
        Show background grid. Default: False
    """
    scale_mode: str = 'auto'  # 'auto', 'fixed', 'fullsize'
    title_distance: float = 0.1
    xlabel_distance: float = 0.1
    ylabel_distance: float = 0.1
    legend_position: str = 'tr'
    legend_offset_x: float = 0.0
    legend_offset_y: float = 0.0
    smooth_curves: bool = True
    show_grid: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


@dataclass
class GLEMarkerConfig:
    """Marker style configuration.
    
    Attributes
    ----------
    default_marker : str
        Default marker type when creating scatter plots.
        Options: 'circle', 'square', 'triangle', 'diamond', 'cross',
        'fcircle', 'fsquare', 'ftriangle', 'fdiamond' (filled variants).
        Default: 'fcircle' (filled circle)
    
    msize_scale : float
        Scaling factor for marker sizes. Multiplies the msize value.
        Default: 1.0
    
    mdist : Optional[float]
        Default marker distance (space between markers on continuous lines).
        If None, markers appear at every point. Default: None
    """
    default_marker: str = 'fcircle'
    msize_scale: float = 1.0
    mdist: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


class GlobalConfigMeta(type):
    """Metaclass for GlobalConfig to provide attribute access."""
    
    _instance = None
    
    @property
    def style(cls) -> GLEStyleConfig:
        """Get global style configuration."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.style
    
    @property
    def graph(cls) -> GLEGraphConfig:
        """Get global graph configuration."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.graph
    
    @property
    def marker(cls) -> GLEMarkerConfig:
        """Get global marker configuration."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.marker


class GlobalConfig(metaclass=GlobalConfigMeta):
    """Global gleplot configuration.
    
    Provides singleton-like access to default configuration settings
    that apply to all new figures created.
    
    Access style, graph, and marker configurations directly as class attributes:
    
    Examples
    --------
    >>> from gleplot.config import GlobalConfig
    >>> # Change default font globally
    >>> GlobalConfig.style.font = 'helvetica'
    >>> # All new figures will use this font
    
    >>> # Or reset to defaults
    >>> GlobalConfig.reset()
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.style = GLEStyleConfig()
        self.graph = GLEGraphConfig()
        self.marker = GLEMarkerConfig()
        self._initialized = True
    
    @classmethod
    def reset(cls):
        """Reset all configurations to defaults."""
        instance = cls()
        instance.style = GLEStyleConfig()
        instance.graph = GLEGraphConfig()
        instance.marker = GLEMarkerConfig()
    
    @classmethod
    def get_style(cls) -> GLEStyleConfig:
        """Get global style configuration."""
        return cls.style
    
    @classmethod
    def get_graph(cls) -> GLEGraphConfig:
        """Get global graph configuration."""
        return cls.graph
    
    @classmethod
    def get_marker(cls) -> GLEMarkerConfig:
        """Get global marker configuration."""
        return cls.marker
    
    @classmethod
    def to_dict(cls) -> Dict[str, Dict[str, Any]]:
        """Export all configurations as dictionary."""
        return {
            'style': cls.style.to_dict(),
            'graph': cls.graph.to_dict(),
            'marker': cls.marker.to_dict(),
        }


# Module-level convenience access
style = GlobalConfig.get_style
graph = GlobalConfig.get_graph
marker = GlobalConfig.get_marker

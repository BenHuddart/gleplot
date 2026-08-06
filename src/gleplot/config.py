"""Configuration and style settings for gleplot."""

from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field, asdict


@dataclass
class GLEStyleConfig:
    """GLE rendering style configuration.

    Attributes
    ----------
    font : str or None
        GLE font name (e.g., 'times8', 'psagb', 'plti').
        If None or empty string, uses GLE's default font. Default: None

    fontsize : float
        Font size in points. Default: 12 (optimized for GLE/PDF readability)

    default_linewidth : float
        Default line width in points (unit: 1/72 inch).
        Default: 1.5 points ≈ 0.053 cm (increased for visibility in PDFs)

    default_color : str
        Colour used by :meth:`gleplot.Axes.plot`, :meth:`~gleplot.Axes.errorbar`,
        :meth:`~gleplot.Axes.errorbar_from_file` and
        :meth:`~gleplot.Axes.line_from_file` when the call passes no
        ``color``. Any spelling :func:`gleplot.colors.rgb_to_gle` accepts.
        Default: 'BLUE' -- the colour those methods hard-coded before this
        field was wired up, so the default changes nothing.
        (:meth:`~gleplot.Axes.bar` and :meth:`~gleplot.Axes.fill_between`
        keep their own distinct defaults, RED and LIGHTBLUE.)

    default_marker_color : str
        Same, for a marker-only series -- what :meth:`gleplot.Axes.scatter`
        produces, and :meth:`~gleplot.Axes.plot` with a marker and no line.
        Default: 'BLUE'

    line_style_solid : int
        GLE line style for solid lines. Default: 1

    line_style_dashed : int
        GLE line style for dashed lines (--). Default: 3

    line_style_dotted : int
        GLE line style for dotted lines (:). Default: 2

    line_style_dashdot : int
        GLE line style for dash-dot lines (-.). Default: 6

    Notes
    -----
    The ``line_style_*`` defaults are the GLE ``lstyle`` numbers that actually
    render as their names say, measured by compiling a ruler of ``set lstyle
    1..9`` strokes with GLE 4.3.10 and looking at the result:

    ==========  ==================
    ``lstyle``  renders as
    ==========  ==================
    1           solid
    2           dotted (dense)
    3           dashed
    4           dotted (sparse)
    5           dashed (long)
    6           dash-dot
    7           dash-dot (sparse)
    8           dash-dot (dense)
    9           dashed (long, sparse)
    ==========  ==================

    gleplot previously defaulted to dashed=2 / dotted=3 / dashdot=4, i.e.
    ``linestyle='--'`` drew a dotted line and ``':'`` drew a dashed one. Do
    not "restore" those numbers: they were transposed, and dashed-vs-dotted
    is load-bearing in publication figures where a dashed curve conventionally
    means a fit.
    """

    font: str = ""  # Empty string = GLE default font
    fontsize: float = 12  # Increased from 10 for better readability in GLE/PDF output
    default_linewidth: float = 1.5  # Increased from 1.0 for visibility
    default_color: str = "BLUE"
    default_marker_color: str = "BLUE"
    # See the "Notes" section above: these are GLE's real style numbers, not
    # a sequential 1/2/3/4 guess.
    line_style_solid: int = 1
    line_style_dashed: int = 3
    line_style_dotted: int = 2
    line_style_dashdot: int = 6

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

    title_distance : float or None
        Figure-wide default for ``Axes.title_dist`` -- the ``dist`` option of
        GLE's ``title`` command, in cm. A per-axes ``title_dist`` wins over
        it. ``None`` (the default) emits no ``dist`` at all, leaving GLE's
        own spacing.

        .. versionchanged:: 2.4
           Was an inert ``0.1`` that nothing read. It is now the default for
           the per-axes distance, and its default is ``None`` so that
           figures which never set it emit exactly the GLE they always did.
           A project serialized with the old inert ``0.1`` will, once
           reloaded, actually emit ``dist 0.1``.

    xlabel_distance : float or None
        Same, for ``Axes.xlabel_dist`` -- the ``dist`` option of GLE's
        ``xtitle`` command (distance between the axis title and the tick
        labels), in cm. Default: None.

    ylabel_distance : float or None
        Same, for ``Axes.ylabel_dist`` (GLE ``ytitle ... dist``) and, when
        the axes sets no distance of its own, ``Axes.y2label_dist``
        (``y2title ... dist``). Default: None.

    legend_position : str
        Default legend position: 'tl', 'tr', 'bl', 'br', 'tc', 'bc', 'lc', 'rc', 'cc'.
        Options: 'top right', 'top left', 'bottom right', 'bottom left', 'center'.
        Default: 'tr' (top right)

    legend_offset_x : float
        Figure-wide default legend x-offset from its anchor (cm), used by
        every axes whose own ``legend_offset`` is None. Default: 0.0.

    legend_offset_y : float
        The y half of the same default (cm). Default: 0.0.

        ``(0.0, 0.0)`` means "no offset", and emits no ``offset`` clause --
        so the defaults leave GLE output unchanged.

    smooth_curves : bool
        Draw line series as a fitted spline through the points (GLE's
        ``smooth`` keyword) instead of as a polyline joining them.
        **Opt-in**: a smoothed curve is an interpolation, not the data, so
        it must never be applied without being asked for. Default: False

    show_grid : bool
        Figure-wide default grid: when True, every axes that has not called
        :meth:`gleplot.Axes.grid` itself gets a main-tick grid on both axes
        (GLE ``xaxis grid`` / ``yaxis grid``). An axes that HAS called
        ``grid()`` -- including ``grid(False)`` -- keeps its own answer.
        Default: False

    default_cmap : str
        Default colour map used by ``imshow``/``tripcolor`` when ``cmap`` is
        not passed. One of the names in :data:`gleplot.palettes.SUPPORTED_CMAPS`.
        Default: 'viridis'

    colormap_pixels : int
        Default bitmap resolution (pixels per side) for ``colormap`` rendering
        when ``imshow(pixels=...)`` is not given. Default: 200
    """

    scale_mode: str = "auto"  # 'auto', 'fixed', 'fullsize'
    # None = emit no 'dist' option (GLE's atitledist/titlescale spacing).
    # See the class docstring for why these are no longer 0.1.
    title_distance: Optional[float] = None
    xlabel_distance: Optional[float] = None
    ylabel_distance: Optional[float] = None
    legend_position: str = "tr"
    legend_offset_x: float = 0.0
    legend_offset_y: float = 0.0
    smooth_curves: bool = False
    show_grid: bool = False
    default_cmap: str = "viridis"
    colormap_pixels: int = 200

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

    default_marker: str = "fcircle"
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
            "style": cls.style.to_dict(),
            "graph": cls.graph.to_dict(),
            "marker": cls.marker.to_dict(),
        }


# Module-level convenience access
style = GlobalConfig.get_style
graph = GlobalConfig.get_graph
marker = GlobalConfig.get_marker

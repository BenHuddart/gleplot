"""Configuration and style settings for gleplot."""

import math
import numbers
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from ._warn import warn_external
from .colors import _stored_color

#: GLE's ``set cap`` and ``set join`` words, in GLE's own numbering order, so
#: the first is GLE's default.
LINE_CAPS = ("butt", "round", "square")
LINE_JOINS = ("mitre", "round", "bevel")

#: ``GLEGraphConfig.scale_mode`` values; 'fixed' is accepted and warns.
_SCALE_MODES = ("auto", "fullsize", "fixed")

_LINE_WORDS = {
    "line_cap": (LINE_CAPS, "matplotlib's 'projecting' is 'square'."),
    "line_join": (LINE_JOINS, "matplotlib's 'miter' is 'mitre'."),
}


@dataclass
class GLEStyleConfig:
    """GLE rendering style configuration.

    Attributes
    ----------
    font : str or None
        GLE font name (e.g., 'texcmr', 'ss', 'psh'), not a family name such
        as 'helvetica', which GLE rejects. If None or empty string, uses
        GLE's default font. Default: ''

    fontsize : float
        Font size in points. Default: 12 (optimized for GLE/PDF readability)

    default_linewidth : float
        Default line width in points (unit: 1/72 inch).
        Default: 1.5 points ≈ 0.053 cm (increased for visibility in PDFs)
        A value other than the default is recorded in the saved file's
        metadata, so a figure opened with ``open_gle`` keeps it.

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

    line_cap : {'butt', 'round', 'square'} or None
        How every line in the figure ends (GLE ``set cap``). ``'square'`` is
        matplotlib's ``'projecting'``. None (the default) writes nothing and
        leaves GLE's own ``butt``.

    line_join : {'mitre', 'round', 'bevel'} or None
        How every line in the figure turns a corner (GLE ``set join``).
        ``'mitre'`` is matplotlib's ``'miter'``. None (the default) writes
        nothing and leaves GLE's own ``mitre``.

    dashlen : float or None
        Length in cm of the shortest dash in every line style (GLE ``set
        dashlen``). The ``lstyle`` digits are multiples of it, so a larger
        value stretches dashes and gaps alike. GLE does not scale dashes
        with the line width, so a thick dashed line can read as dotted;
        raise ``dashlen`` to open it up. None (the default) writes nothing
        and leaves GLE's own 0.04 cm.

    usetex : bool
        Typeset every label with LaTeX (GLE ``set texlabels 1``), as
        matplotlib's ``text.usetex`` does: titles, axis labels, tick labels,
        legend entries and text annotations. Strings reach LaTeX as written,
        so ``$...$`` is LaTeX math rather than gleplot's mathtext translation,
        and text outside it must be valid LaTeX (``\\_`` for an underscore).
        Labels already set keep their GLE markup, so set this when creating
        the figure. Compiling needs a LaTeX installation; SVG output is not
        available. Default: False

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

    Any GLE ``lstyle`` code is accepted, not only 1-9. GLE reads a code of
    more than one digit as alternating run lengths, black then white: ``42``
    is a dash four units long followed by a gap two units long.

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
    line_cap: Optional[str] = None
    line_join: Optional[str] = None
    dashlen: Optional[float] = None
    usetex: bool = False

    def __setattr__(self, name: str, value: Any) -> None:
        # Checked on every assignment, not only at construction:
        # ``fig.style.line_cap = ...`` is a documented way to restyle.
        if value is not None and name in _LINE_WORDS:
            words, hint = _LINE_WORDS[name]
            if not isinstance(value, str):
                raise TypeError(
                    f"{name} must be a string or None; got {value!r}. "
                    f"Accepted: {list(words)}."
                )
            if value not in words:
                raise ValueError(
                    f"{name} must be one of {list(words)} or None; got "
                    f"{value!r}. {hint}"
                )
        if value is not None and name == "dashlen":
            if not isinstance(value, numbers.Real) or isinstance(value, bool):
                raise TypeError(
                    f"dashlen must be a number of cm or None; got {value!r}."
                )
            # GLE's g_set_line_styled ignores 0; a negative dash is no dash.
            if not (math.isfinite(value) and float(value) > 0):
                raise ValueError(
                    f"dashlen must be a positive length in cm or None; got "
                    f"{value!r}. None keeps GLE's own 0.04 cm."
                )
        if name in ("default_color", "default_marker_color"):
            value = _stored_color(value)
        if name == "usetex" and not isinstance(value, bool):
            raise TypeError(
                f"usetex must be True or False; got {value!r} of type "
                f"{type(value).__name__}."
            )
        super().__setattr__(name, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


@dataclass
class GLEGraphConfig:
    """GLE graph configuration.

    Attributes
    ----------
    scale_mode : str
        Who sizes the graph. 'auto' (the default): gleplot places each axes
        frame from its subplot cell or ``add_axes`` rect, with margins for
        labels. 'fullsize': a figure with a single axes, other than one made
        with ``add_axes``, is written with GLE's ``fullsize``, filling the
        page with no margins; figures with several axes keep gleplot's
        layout. 'fixed': no effect, and warns; the figure is written as under
        'auto'. Any other value raises ``ValueError``.

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
        it must never be applied without being asked for. Applies to
        :meth:`~gleplot.Axes.plot`, :meth:`~gleplot.Axes.line_from_file` and
        the line drawn by :meth:`~gleplot.Axes.errorbar`. Fills, contour
        lines, step, stem and histogram lines, and a ``plot`` line broken by
        NaN (which warns) are never smoothed.
        Default: False

    show_grid : bool
        Figure-wide default grid: when True, every axes that has not called
        :meth:`gleplot.Axes.grid` itself gets a main-tick grid on both axes
        (GLE ``xaxis grid`` / ``yaxis grid``). An axes that HAS called
        ``grid()`` -- including ``grid(False)`` -- keeps its own answer.
        Default: False

    default_cmap : str
        Default colour map used by ``imshow``/``tripcolor`` when ``cmap`` is
        not passed. One of the names in :data:`gleplot.palettes.SUPPORTED_CMAPS`,
        or one with ``_r`` appended for its reversed form.
        Default: 'viridis'

    colormap_pixels : int
        Default bitmap resolution (pixels per side) for ``colormap`` rendering
        when ``imshow(pixels=...)`` is not given. Default: 200
    """

    scale_mode: str = "auto"  # 'auto' or 'fullsize' ('fixed' has no effect)
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

    def __setattr__(self, name: str, value: Any) -> None:
        # Checked on every assignment, as GLEStyleConfig's words are.
        if name == "scale_mode":
            if not isinstance(value, str):
                raise TypeError(
                    f"scale_mode must be 'auto' or 'fullsize'; got {value!r}."
                )
            if value not in _SCALE_MODES:
                raise ValueError(
                    f"scale_mode must be 'auto' or 'fullsize' ('fixed' is "
                    f"accepted but has no effect); got {value!r}."
                )
            if value == "fixed":
                warn_external(
                    "scale_mode='fixed' has no effect: gleplot places every "
                    "axes frame itself, as under 'auto'. Use 'auto', or "
                    "'fullsize' to let GLE size a single graph."
                )
        super().__setattr__(name, value)

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
        Default marker distance in cm along a line that has markers: GLE's
        ``mdist``, written on each marked line that does not pass its own
        ``mdist`` to ``plot``. If None, markers appear at every point.
        Default: None
    """

    default_marker: str = "fcircle"
    msize_scale: float = 1.0
    mdist: Optional[float] = None

    def __post_init__(self) -> None:
        # GLE's marker loop (graph2.cpp drawMarkers) never ends on a
        # negative mdist, and 0 is its own "every point".
        if self.mdist is not None and not (
            isinstance(self.mdist, (int, float))
            and not isinstance(self.mdist, bool)
            and math.isfinite(self.mdist)
            and self.mdist > 0
        ):
            raise ValueError(
                f"mdist must be a positive distance in cm or None; got "
                f"{self.mdist!r}. None draws a marker on every point."
            )

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
    >>> GlobalConfig.style.font = 'texcmss'  # TeX Computer Modern Sans Serif
    >>> # All new figures will use this font

    >>> # Or reset to defaults
    >>> GlobalConfig.reset()

    Notes
    -----
    **Copy-at-construction, not shared-by-reference.** ``GlobalConfig.style``
    (and ``.graph``, ``.marker``) really is one shared, mutable instance --
    editing it here, before any figure exists, is exactly how you change the
    default for every figure created afterwards. But :class:`gleplot.figure.Figure`
    and :class:`gleplot.writer.GLEWriter` each take an independent COPY of
    the current value at construction time (when their own ``style``/
    ``graph``/``marker`` argument is omitted), not a reference to this
    singleton. So:

    - ``GlobalConfig.style.font = 'x'`` then ``fig = Figure()`` -- ``fig``
      gets ``'x'`` (the default was read at construction time).
    - ``fig = Figure()`` then ``fig.style.font = 'x'`` -- only ``fig``
      changes; ``GlobalConfig.style.font`` and every other figure are
      unaffected. Before this was fixed, this in-place edit silently
      mutated ``GlobalConfig.style`` itself (since ``fig.style`` and
      ``GlobalConfig.style`` were the same object), leaking into every
      figure created afterwards in the process.
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

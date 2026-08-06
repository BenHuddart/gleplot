"""Axes class for gleplot."""

import numpy as np
import re
import warnings
from typing import Any, Optional, List, Sequence, Union, Tuple, Dict
from .colors import rgb_to_gle
from .config import GlobalConfig
from .markers import get_gle_marker, resolve_marker_fill
from .mathtext import mathtext_to_gle
from .palettes import canonical_cmap
from .parser.units import markersize_to_msize, capsize_pt_to_cm
from .parser.tables import (
    KEY_POSITIONS_LONG_TO_SHORT,
    KEY_POSITIONS_SHORT_TO_LONG,
    MATPLOTLIB_TO_LSTYLE,
)
from .series import (  # noqa: F401  (re-exported: historical import path)
    DRAWABLE_CLASSES,
    SERIES_ATTRS,
    SERIES_CLASSES,
    BarSeries,
    ContourSeries,
    ErrorbarSeries,
    FileSeries,
    FillSeries,
    HeatmapSeries,
    LineSeries,
    RefLine,
    ScatterSeries,
    Series,
    Span,
    TextAnnotation,
    _build_column_names,
    _build_errorbar_column_names,
    _looks_numeric,
    _unique_column_names,
    sanitize_column_name,
)

# Global counter for unique data file names across all figures in a session
_global_data_file_counter = 0

#: matplotlib ``legend(loc=...)`` strings -> gleplot's long-form key position.
#: GLE's key has nine anchors (tl/tc/tr, lc/cc/rc, bl/bc/br), so every
#: matplotlib location has an exact counterpart; only ``'best'`` has no
#: equivalent (GLE does not search for a clear spot) and maps to top right.
#: Provenance for the GLE side: GLE 4.3.10 manual, "The Key Module",
#: ``position``/``pos`` (the same nine values as ``justify``).
MATPLOTLIB_TO_GLE_LEGEND_LOC = {
    "best": "top right",
    "upper right": "top right",
    "upper left": "top left",
    "upper center": "top center",
    "lower left": "bottom left",
    "lower right": "bottom right",
    "lower center": "bottom center",
    "center left": "left center",
    "center right": "right center",
    "right": "right center",
    "center": "center",
}

#: matplotlib's relative font-size names as multipliers of the base font size
#: (matplotlib ``font_manager.font_scalings``). Used to resolve
#: ``legend(fontsize='small')`` against the figure style's fontsize.

#: Default ``zorder`` for drawable series kinds when the caller omits ``zorder``.
#: Matches the pre-zorder GLE emission stack: bars, then lines, scatters,
#: errorbars (later ``dN`` commands draw on top in GLE). Derived from the
#: series classes, which own the value (``LineSeries.ZORDER_DEFAULT``, ...).
SERIES_ZORDER_DEFAULT: Dict[str, float] = {
    kind: float(cls.ZORDER_DEFAULT or 0.0) for kind, cls in DRAWABLE_CLASSES.items()
}

#: Stable kind rank for legacy series dicts missing ``_draw_seq``; likewise
#: derived from the classes (``LineSeries.KIND_RANK``, ...).
_SERIES_KIND_RANK: Dict[str, int] = {
    kind: int(cls.KIND_RANK or 0) for kind, cls in DRAWABLE_CLASSES.items()
}

MATPLOTLIB_RELATIVE_FONTSIZES = {
    "xx-small": 0.579,
    "x-small": 0.694,
    "small": 0.833,
    "medium": 1.0,
    "large": 1.2,
    "x-large": 1.44,
    "xx-large": 1.728,
    "larger": 1.2,
    "smaller": 0.833,
}


def _to_jsonable(value):
    """Recursively convert a value into a JSON-serializable form.

    numpy arrays become lists, numpy scalars become native Python scalars,
    and tuples become lists. Nested dicts/lists are converted element-wise.
    ``None``, ``bool``, ``str`` and native numeric types pass through
    unchanged. This is the single conversion used by all serialization so
    that ``to_dict`` output is deterministic and ``json``-safe.
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, np.ndarray):
        if value.dtype.kind in "biufc":  # bool/int/uint/float/complex: numeric
            # ndarray.tolist() already recursively converts numeric dtypes to
            # native Python scalars (int/float/bool), so no need to re-wrap
            # every element in a Python-level comprehension (avoids iterating
            # large arrays twice).
            return value.tolist()
        # Object/other dtypes may hold values that aren't already
        # JSON-serializable (e.g. nested numpy scalars); recurse per element.
        return [_to_jsonable(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (int, float)):
        return value
    # Fallback: represent anything else by its string form (should not occur
    # for the authoritative state serialized here).
    return value


def _to_float_array(value):
    """Restore a numeric array field from JSON data as a float ndarray.

    Returns ``None`` when the incoming value is ``None`` so optional error
    arrays round-trip exactly.
    """
    if value is None:
        return None
    return np.asarray(value, dtype=float)


def _require_finite(arr: np.ndarray, what: str) -> None:
    """Raise ``ValueError`` if ``arr`` holds any NaN or infinity.

    GLE's ``.z`` grid and scattered-points readers have NO missing-value
    support -- a ``nan``/``inf`` in a sidecar is a hard parse error at compile
    time (and would silently corrupt the bitmap). matplotlib's ``imshow``
    tolerates NaN (renders transparent); GLE cannot, so we reject early with a
    clear message pointing at the offending data rather than emitting a broken
    sidecar.
    """
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            f"{what} contains NaN or infinite values, which GLE's colormap/"
            "contour grid cannot represent; mask or fill them before plotting"
        )


def _require_valid_extent(ext) -> None:
    """Validate an ``[xmin, xmax, ymin, ymax]`` extent for GLE.

    GLE's ``.z`` grid header and the graph axes both require strictly
    ascending ranges (``xmin < xmax``, ``ymin < ymax``); a reversed or
    degenerate extent otherwise emits a ``.z`` file and an ``xaxis``/``yaxis``
    range GLE rejects at compile time ("illegal range for xaxis"). Reject early
    with a clear message. (Unlike matplotlib, gleplot cannot express an axis
    flipped purely via ``extent``.)
    """
    x0, x1, y0, y1 = ext
    if not all(np.isfinite(v) for v in ext):
        raise ValueError(f"extent must contain finite values; got {ext}")
    if x0 >= x1 or y0 >= y1:
        raise ValueError(
            "extent must have xmin < xmax and ymin < ymax (GLE requires "
            f"ascending axis ranges); got (xmin={x0}, xmax={x1}, ymin={y0}, "
            f"ymax={y1})"
        )


def _axis_from_meshgrid(arr: np.ndarray, name: str) -> np.ndarray:
    """Reduce a matplotlib-style 2-D meshgrid coordinate array to its 1-D axis.

    ``np.meshgrid(x, y)`` (the default ``indexing='xy'``) returns an ``X``
    whose every row is ``x`` and a ``Y`` whose every column is ``y``. GLE's
    ``.z`` grid is defined by an extent plus a shape, so it needs those 1-D
    axes back. This extracts them, verifying the grid really is regular --
    the whole point of the check is that a grid we cannot represent must
    raise here rather than be silently misdrawn.

    Parameters
    ----------
    arr : ndarray, shape (ny, nx)
        The 2-D coordinate array (``X`` or ``Y``).
    name : {'x', 'y'}
        Which coordinate it is; decides the axis it must be constant along.

    Returns
    -------
    ndarray
        The 1-D axis (``arr[0, :]`` for ``x``, ``arr[:, 0]`` for ``y``).
    """
    # Tolerance relative to the coordinate's own span: np.meshgrid copies
    # values exactly, but a grid built by arithmetic can carry rounding.
    span = float(np.ptp(arr)) if arr.size else 0.0
    tol = max(1e-12, 1e-9 * span)

    along_rows = np.max(np.abs(arr - arr[0:1, :])) <= tol if arr.size else True
    along_cols = np.max(np.abs(arr - arr[:, 0:1])) <= tol if arr.size else True

    wanted, other = ("rows", "columns") if name == "x" else ("columns", "rows")
    constant = along_rows if name == "x" else along_cols
    transposed = along_cols if name == "x" else along_rows

    if constant:
        return arr[0, :] if name == "x" else arr[:, 0]
    if transposed:
        raise ValueError(
            f"contour(X, Y, Z): the 2-D {name.upper()} is constant along its "
            f"{other}, not its {wanted} -- this is the layout of "
            f"np.meshgrid(..., indexing='ij'). Rebuild the grid with the "
            f"default indexing='xy' (and Z of shape (len(y), len(x))), or "
            f"pass X.T, Y.T and Z.T."
        )
    raise ValueError(
        f"contour(X, Y, Z): the 2-D {name.upper()} is not a regular grid (its "
        f"{wanted} are not all identical), so it has no single 1-D {name} "
        f"axis. GLE contours a uniform rectangular grid; use tricontour(x, y, "
        f"z) for scattered or irregularly gridded data."
    )


def _sanitize_data_stem(name: object) -> str:
    """Convert an arbitrary data name to a safe filename stem."""
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "data"


#: Characters rejected in a figure-level ``data_prefix``.
#:
#: Two disjoint groups, both verified against GLE 4.3.10 rather than assumed:
#:
#: 1. ``!``, ``"``, ``+`` and any whitespace -- GLE's tokenizer cannot read
#:    these inside the *unquoted* filename of a ``data <file>`` statement.
#:    ``data mk+white_0.dat`` aborts the compile with
#:    ``>> Error: left hand side contains unquoted string``. A sweep of the
#:    printable ASCII punctuation found exactly these; ``. - # $ % & ( ) [ ] {
#:    } , ; : = @ ~ ^ * ? < > | \ ` '`` and non-ASCII all parse fine, so they
#:    are deliberately *not* rejected.
#: 2. ``/`` and ``\\`` -- path separators. A ``data_prefix`` names a filename
#:    stem, not a path; either one would redirect the sidecar into a
#:    directory (or, on the platform where it is not a separator, produce a
#:    filename that stops resolving when the script moves). Rejected on every
#:    platform so a prefix means the same thing everywhere.
#:
#: C0 control characters (including NUL) are rejected as well -- see
#: :func:`_validate_data_prefix`.
_DATA_PREFIX_FORBIDDEN = '!"+/\\'


def _describe_char(ch: str) -> str:
    """Render a character for an error message, naming invisible ones."""
    names = {" ": "space", "\t": "tab", "\n": "newline", "\r": "carriage return"}
    if ch in names:
        return names[ch]
    if ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F:
        return f"U+{ord(ch):04X}"
    return repr(ch)


def _validate_data_prefix(prefix: object) -> str:
    """Validate a figure-level ``data_prefix``, or raise ``ValueError``.

    Returns the prefix unchanged on success. Unlike :func:`_sanitize_data_stem`
    -- which quietly rewrites the *label-like* ``data_name=`` argument into a
    filename stem -- this rejects a bad prefix instead of repairing it. The
    whole point of ``data_prefix`` is that the caller can predict the sidecar
    filenames (batch pipelines glob for them), so silently renaming
    ``mk+white`` to ``mk_white`` would trade a GLE compile error for a missing
    file much further downstream. Sanitizing here would also lowercase, which
    would break documented usage such as ``data_prefix='experimentA'``.

    See :data:`_DATA_PREFIX_FORBIDDEN` for what is rejected and why.
    """
    if not isinstance(prefix, str):
        raise TypeError(
            f"data_prefix must be a str, got {type(prefix).__name__}: {prefix!r}"
        )
    if not prefix or not prefix.strip():
        raise ValueError(
            "data_prefix must be a non-empty filename stem; got "
            f"{prefix!r}. Pass None to use the default 'data_N.dat' naming."
        )

    bad = [
        (idx, ch)
        for idx, ch in enumerate(prefix)
        if ch in _DATA_PREFIX_FORBIDDEN
        or ch.isspace()
        or ord(ch) < 0x20
        or ord(ch) == 0x7F
    ]
    if bad:
        detail = ", ".join(f"{_describe_char(c)} at index {i}" for i, c in bad)
        raise ValueError(
            f"data_prefix {prefix!r} contains characters that cannot appear in "
            f"a GLE data filename: {detail}. Forbidden: whitespace, control "
            'characters, and any of ! " + / \\ (GLE cannot parse the first '
            "four in an unquoted 'data' statement; the last two are path "
            "separators). Most other punctuation, including . - _ and #, is "
            "allowed."
        )
    return prefix


def _reserve_data_filename(filename: str, figure=None) -> str:
    """Reserve a data filename and avoid collisions within a figure."""
    if not filename.endswith(".dat"):
        filename = f"{filename}.dat"

    if figure is None:
        return filename

    used = getattr(figure, "_used_data_files", None)
    if used is None:
        used = set()
        figure._used_data_files = used

    if filename not in used:
        used.add(filename)
        return filename

    stem = filename[:-4]
    suffix_idx = 1
    while True:
        candidate = f"{stem}_{suffix_idx}.dat"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix_idx += 1


def _reserve_sidecar(figure, kind: str, ext: str) -> str:
    """Reserve a named sidecar file ``<prefix>_<kind><N>.<ext>`` for a figure.

    Used for the contour/heatmap raw-content sidecars whose names GLE derives
    generated files from mechanically (``.z`` grids, scattered ``.dat``
    points). ``kind`` is ``'heatmap'``/``'contour'``/``'points'`` and ``ext``
    is ``'z'``/``'dat'``. ``N`` is a per-kind, 1-based counter kept on the
    figure. The reserved name is recorded in ``figure._used_data_files`` so it
    never collides with a generated ``data_N.dat`` (or another sidecar) and so
    it round-trips through ``Figure.to_dict``/``from_dict``.

    ``figure`` is optional only for symmetry with the other reservers; in
    practice a figure is always present when a heatmap/contour series is added.
    """
    prefix = figure.data_prefix if figure and figure.data_prefix else "data"

    counters = getattr(figure, "_sidecar_counters", None) if figure else None
    if figure is not None and counters is None:
        counters = {}
        figure._sidecar_counters = counters

    used = getattr(figure, "_used_data_files", None) if figure else None
    if figure is not None and used is None:
        used = set()
        figure._used_data_files = used

    idx = (counters.get(kind, 0) + 1) if counters is not None else 1
    while True:
        name = f"{prefix}_{kind}{idx}.{ext}"
        if used is None or name not in used:
            break
        idx += 1
    if counters is not None:
        counters[kind] = idx
    if used is not None:
        used.add(name)
    return name


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
        filename = f"{figure.data_prefix}_{figure._local_data_counter}.dat"
        figure._local_data_counter += 1
    else:
        global _global_data_file_counter
        filename = f"data_{_global_data_file_counter}.dat"
        _global_data_file_counter += 1
    return _reserve_data_filename(filename, figure)


def _resolve_data_file(figure=None, data_name: object = None) -> str:
    """Resolve a data filename from an optional user-provided name."""
    if data_name is None:
        return _get_next_data_file(figure)
    return _reserve_data_filename(_sanitize_data_stem(data_name), figure)


def _pop_marker_fill(kwargs: dict, fillstyle=None, markerfacecolor=None) -> str:
    """Resolve the marker fill mode from the plotting methods' kwargs.

    Accepts matplotlib's short aliases (``mfc`` for ``markerfacecolor``) out
    of ``**kwargs`` so a call copied straight from a matplotlib script works,
    and removes them so they never reach the series dict. Returns one of
    ``'full'`` / ``'none'`` / ``'white'`` (see
    :func:`gleplot.markers.resolve_marker_fill`).
    """
    mfc = kwargs.pop("mfc", None)
    if markerfacecolor is None:
        markerfacecolor = mfc
    return resolve_marker_fill(fillstyle=fillstyle, markerfacecolor=markerfacecolor)


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
        self.xlabel_text = ""
        self.ylabel_text = ""
        self.y2label_text = ""  # Secondary y-axis label
        self.title_text = ""
        self.xscale = "linear"
        self.yscale = "linear"
        self.y2scale = "linear"  # Secondary y-axis scale
        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None
        self.y2min = None  # Secondary y-axis limits
        self.y2max = None
        # Tri-state: None = auto (show a legend iff any series has a label),
        # True/False = explicit user choice (the GUI toggle writes these).
        self.legend_on = None
        self.legend_pos = "top right"
        # Legend text height in matplotlib points (None = inherit the figure
        # style's fontsize, i.e. whatever GLE's current ``set hei`` is) and
        # the legend box (matplotlib ``frameon``; False emits ``key nobox``).
        self.legend_fontsize = None
        self.legend_frameon = True
        self.legend_offset = None  # (dx_cm, dy_cm) or None

        # Shared axes visibility control
        self._show_xlabel = True
        self._show_ylabel = True
        self._show_xticks = True
        self._show_yticks = True
        # Edge tick-label suppression for touching subplots. Normally written
        # by Figure._apply_shared_axes_flags, but initialized here so a
        # directly-constructed Axes (e.g. a broken-axis segment) has them too.
        self._remove_last_xtick = False
        self._remove_last_ytick = False
        self._remove_first_xtick = False
        self._remove_first_ytick = False

        # Explicit tick control (GLE dticks/dsubticks/places/names). All None
        # means "let GLE choose", which is the historical behaviour.
        self.xdticks = None
        self.ydticks = None
        self.xdsubticks = None
        self.ydsubticks = None
        self.xplaces = None
        self.xnames = None
        self.yplaces = None
        self.ynames = None

        # Frame sides switched off entirely -- axis line, ticks and labels.
        # Used for the inner edges of a broken-axis assembly, where several
        # graph blocks butt together and must read as one panel.
        self._xaxis_off = False
        self._yaxis_off = False
        self._x2axis_off = False
        self._y2axis_off = False

        # Broken-axis membership (see :mod:`gleplot.brokenaxes`). Both stay
        # None on an ordinary axes; on a segment, ``_break_owner`` is the
        # BrokenAxes back-reference and ``_break_index`` its 0-based position
        # left-to-right.
        self._break_owner = None
        self._break_index = None

        # Plot data storage. One list per series kind, each holding the
        # matching :mod:`gleplot.series` class (which owns that kind's field
        # schema, array fields and sidecar header defaults).
        self.lines: List[LineSeries] = []
        self.scatters: List[ScatterSeries] = []
        self.bars: List[BarSeries] = []
        self.fills: List[FillSeries] = []
        self.errorbars: List[ErrorbarSeries] = []
        # External-file series definitions (column references).
        self.file_series: List[FileSeries] = []
        self.texts: List[TextAnnotation] = []  # In-plot text annotations
        self.heatmaps: List[HeatmapSeries] = []  # imshow/tripcolor colormaps
        self.contours: List[ContourSeries] = []  # contour/tricontour lines
        # Reference lines (axvline/axhline) and shaded bands (axvspan/
        # axhspan). Stored as *declarations* -- a value plus a fractional
        # extent along the other axis -- and turned into concrete two-point
        # line / band datasets only at write time, once the axis limits are
        # known. See :meth:`materialize_reflines` for why.
        self.reflines: List[RefLine] = []
        self.spans: List[Span] = []

        # Raw GLE lines recovered from a parsed .gle file that the recognizer
        # could not map onto the object model. Emitted verbatim inside this
        # axes' graph block, immediately before 'end graph'. One entry per
        # source line, no trailing newline. Default: empty (nothing to emit).
        self.passthrough: list = []

        # -- Graph geometry (page placement) --------------------------------
        #
        # Two mutually exclusive representations, both defaulting to "unset"
        # = AUTO placement ("GLE decides"), which is what every figure built
        # through the scripting API carries and what the writer's default
        # emission ('scale auto' single-plot / computed grid cells) means.
        #
        # ``placement`` is the explicit graph FRAME rectangle in page cm,
        # ``(x, y, width, height)`` with the origin at the bottom-left of the
        # page -- the invertible GLE triple ``amove x y`` + ``size w h`` +
        # ``scale 1 1``. It is authoritative when set: the writer emits that
        # triple verbatim instead of computing geometry.
        #
        # ``geometry_passthrough`` holds the graph block's geometry
        # statements verbatim (source order, original indentation) for GLE
        # geometry that is real but NOT invertible into a frame rect
        # ('fullsize', 'scale 0.8 0.8', a bare 'size w h', ...). The writer
        # emits these lines in the geometry slot -- the first thing inside
        # 'begin graph' -- INSTEAD of its own geometry line, so such a figure
        # re-emits byte-for-byte rather than being normalized to 'scale auto'.
        self.placement: Optional[Tuple[float, float, float, float]] = None
        self.geometry_passthrough: list = []

        # Monotonic tie-breaker for equal ``zorder`` (call / insertion order).
        self._draw_seq_counter = 0

    def _register_series_draw_meta(
        self, entry: dict, kind: str, zorder: Optional[float] = None
    ) -> None:
        entry["_draw_seq"] = self._draw_seq_counter
        self._draw_seq_counter += 1
        if zorder is not None:
            entry["zorder"] = float(zorder)

    def plot(
        self,
        x,
        y,
        linestyle: str = "-",
        color: Optional[str] = None,
        marker: Optional[str] = None,
        markersize: float = 6,
        linewidth: float = 1,
        label: Optional[str] = None,
        yaxis: str = "y",
        offset: float = 0.0,
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        zorder: Optional[float] = None,
        **kwargs,
    ):
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
        fillstyle : {'full', 'none'}, optional
            ``'none'`` draws an open (outline) marker instead of a filled one.
        markerfacecolor : str, optional
            ``'none'`` is equivalent to ``fillstyle='none'``; ``'white'``
            gives an outline marker with an opaque white interior. Also
            accepted as the matplotlib alias ``mfc``.
        zorder : float, optional
            Draw order relative to other data series on the same axes.
            Higher values are drawn on top. When omitted, lines and scatters
            keep gleplot's default layer (lines below scatters and error bars).
        **kwargs
            Additional matplotlib-compatible arguments

        Returns
        -------
        Line2D
            Line object (for compatibility)
        """
        data_name = kwargs.pop("data_name", None)
        if zorder is None and "zorder" in kwargs:
            zorder = kwargs.pop("zorder")
        marker_fill = _pop_marker_fill(kwargs, fillstyle, markerfacecolor)
        label = mathtext_to_gle(label)

        x = np.asarray(x)
        y = np.asarray(y)

        # Handle color
        if color is None:
            color = "BLUE"
        else:
            color = rgb_to_gle(color)

        # Handle marker. GLE supports markers on line datasets natively, so a
        # marker requested alongside a solid/dashed line must be preserved
        # (not silently dropped). Only when there is *no* line is the series a
        # true scatter.
        is_scatter = marker is not None and linestyle in ("", "none", " ", "None")

        gle_marker = (
            get_gle_marker(marker, fill=marker_fill) if marker is not None else None
        )
        plot_type = "scatter" if is_scatter else "line"

        # Scale markersize from matplotlib (typical 1-20, default 6) to GLE msize (0.05-0.5)
        # Examples: markersize 6 → 0.15, markersize 10 → 0.25, markersize 20 → 0.5
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )

        plot_fields = dict(
            type=plot_type,
            x=x,
            y=y,
            color=color,
            marker=gle_marker,
            markersize=gle_markersize,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            yaxis=yaxis,  # 'y' or 'y2'
            offset=float(offset),
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_build_column_names("x", ["y"], label),
        )

        if is_scatter:
            scatter_data = ScatterSeries(**plot_fields)
            self._register_series_draw_meta(scatter_data, "scatter", zorder)
            self.scatters.append(scatter_data)
        else:
            line_data = LineSeries(**plot_fields)
            self._register_series_draw_meta(line_data, "line", zorder)
            self.lines.append(line_data)

        return self  # Return self for method chaining

    def errorbar(
        self,
        x,
        y,
        yerr=None,
        xerr=None,
        fmt: str = "-",
        color: Optional[str] = None,
        marker: Optional[str] = None,
        markersize: float = 6,
        linewidth: float = 1,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        capsize_cm: Optional[float] = None,
        yaxis: str = "y",
        offset: float = 0.0,
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        zorder: Optional[float] = None,
        **kwargs,
    ):
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
            Automatically converted to GLE cm units via
            ``parser.units.capsize_pt_to_cm``. Default: None (no caps)
        capsize_cm : float, optional
            Width of error bar caps directly in GLE cm units (typical: 0.05-0.15).
            If specified, this overrides `capsize`. Use this for direct control.
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        fillstyle : {'full', 'none'}, optional
            ``'none'`` draws an open (outline) marker instead of a filled one.
        markerfacecolor : str, optional
            ``'none'`` is equivalent to ``fillstyle='none'``; ``'white'``
            gives an outline marker with an opaque white interior. Also
            accepted as the matplotlib alias ``mfc``.
        zorder : float, optional
            Draw order relative to other data series on the same axes.
            Higher values are drawn on top. When omitted, error bars sit
            above lines and scatters (the historical gleplot default).
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
        if zorder is None and "zorder" in kwargs:
            zorder = kwargs.pop("zorder")
        marker_fill = _pop_marker_fill(kwargs, fillstyle, markerfacecolor)
        label = mathtext_to_gle(label)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        # Handle color
        if color is None:
            color = "BLUE"
        else:
            color = rgb_to_gle(color)

        # Parse fmt string for marker/linestyle
        # Simple parsing: check for marker chars and line styles
        parsed_marker = marker
        parsed_linestyle = fmt
        if fmt in ("", "none", " ", "None"):
            parsed_linestyle = "none"
        elif fmt == "-o" or fmt == "o-":
            parsed_marker = parsed_marker or "o"
            parsed_linestyle = "-"
        elif fmt == "-s" or fmt == "s-":
            parsed_marker = parsed_marker or "s"
            parsed_linestyle = "-"
        elif fmt in ("-", "--", ":", "-."):
            parsed_linestyle = fmt
        elif len(fmt) == 1 and fmt in "os^vD+x":
            parsed_marker = parsed_marker or fmt
            parsed_linestyle = "none"

        # Determine GLE marker
        gle_marker = None
        if parsed_marker is not None:
            gle_marker = get_gle_marker(parsed_marker, fill=marker_fill)

        # Scale markersize from matplotlib to GLE msize (with config scaling)
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )

        # Convert capsize from matplotlib points to GLE cm.
        # Store the original capsize for the data structure, convert for GLE output
        gle_capsize = None
        stored_capsize = None
        if capsize_cm is not None:
            # Direct specification in cm takes precedence
            gle_capsize = capsize_cm
            stored_capsize = capsize_cm  # Store the cm value
        elif capsize is not None:
            # Convert from matplotlib points to cm for GLE
            gle_capsize = capsize_pt_to_cm(capsize)
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

        data_name = kwargs.pop("data_name", None)

        errbar_data = ErrorbarSeries(
            type="errorbar",
            x=x,
            y=y,
            yerr_up=yerr_up,
            yerr_down=yerr_down,
            xerr_left=xerr_left,
            xerr_right=xerr_right,
            color=color,
            marker=gle_marker,
            markersize=gle_markersize,
            linestyle=parsed_linestyle,
            linewidth=linewidth,
            label=label,
            capsize=stored_capsize,
            gle_capsize=gle_capsize,  # Separate field for the GLE-converted value
            yaxis=yaxis,  # 'y' or 'y2'
            offset=float(offset),
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_build_errorbar_column_names(
                label, yerr_up, yerr_down, xerr_left, xerr_right
            ),
        )
        self._register_series_draw_meta(errbar_data, "errorbar", zorder)
        self.errorbars.append(errbar_data)

        return self

    def errorbar_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        yerr_col: Optional[int] = None,
        color: Optional[str] = None,
        marker: Optional[str] = "o",
        markersize: float = 6,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        yaxis: str = "y",
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        **kwargs,
    ):
        """Plot by referencing columns in an existing external data file.

        This avoids writing generated ``data_*.dat`` files. Column indices are
        1-based to match GLE conventions.

        ``fillstyle='none'`` / ``markerfacecolor='none'`` (alias ``mfc``)
        select an open marker; ``markerfacecolor='white'`` selects a
        white-filled one.
        """
        if x_col < 1 or y_col < 1 or (yerr_col is not None and yerr_col < 1):
            raise ValueError("Column indices must be >= 1")

        marker_fill = _pop_marker_fill(kwargs, fillstyle, markerfacecolor)
        label = mathtext_to_gle(label)
        if color is None:
            gle_color = "BLUE"
        else:
            gle_color = rgb_to_gle(color)

        gle_marker = get_gle_marker(marker, fill=marker_fill) if marker else None
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )
        gle_capsize = capsize_pt_to_cm(capsize) if capsize is not None else None

        self.file_series.append(
            FileSeries(
                series_type="errorbar",
                data_file=data_file,
                x_col=int(x_col),
                y_col=int(y_col),
                yerr_col=int(yerr_col) if yerr_col is not None else None,
                color=gle_color,
                marker=gle_marker,
                markersize=gle_markersize,
                label=label,
                capsize=gle_capsize,
                yaxis=yaxis,
            )
        )

        return self

    def line_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
        yaxis: str = "y",
    ):
        """Plot a line by referencing columns in an external data file.

        This avoids creating generated ``data_*.dat`` files for overlay lines.
        Column indices are 1-based to match GLE conventions.
        """
        if x_col < 1 or y_col < 1:
            raise ValueError("Column indices must be >= 1")

        label = mathtext_to_gle(label)
        if color is None:
            gle_color = "BLUE"
        else:
            gle_color = rgb_to_gle(color)

        self.file_series.append(
            FileSeries(
                series_type="line",
                data_file=data_file,
                x_col=int(x_col),
                y_col=int(y_col),
                color=gle_color,
                linestyle=linestyle,
                linewidth=float(linewidth),
                label=label,
                yaxis=yaxis,
            )
        )

        return self

    #: Default ``scatter`` size, in matplotlib's points**2.
    SCATTER_DEFAULT_S = 20

    def scatter(
        self,
        x,
        y,
        color: Optional[str] = None,
        s: Optional[float] = None,
        marker: str = "o",
        label: Optional[str] = None,
        yaxis: str = "y",
        markersize: Optional[float] = None,
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        zorder: Optional[float] = None,
        **kwargs,
    ):
        """
        Create scatter plot.

        Accepts either sizing convention:

        * ``s`` -- matplotlib's ``scatter`` size, an **area in points**2**
          (matplotlib's own default is ~36; gleplot's is 20). Converted to a
          marker size with the square-root relation matplotlib defines between
          the two, ``markersize = sqrt(s)``, times gleplot's 1.2 visibility
          factor, and from there to GLE's ``msize`` the same way
          :meth:`plot` does it.
        * ``markersize`` -- a **diameter in points**, matplotlib's ``Line2D``
          convention and exactly what :meth:`plot` takes. Used as given, with
          no area conversion, so a ``scatter`` and a ``plot`` asking for the
          same ``markersize`` draw the same size of marker.

        Passing neither uses ``s = 20``. **Passing both is ambiguous and
        ``markersize`` wins** -- it is a size, not an area, so honouring it
        needs no conversion and leaves nothing to guess.

        Parameters
        ----------
        x, y : array-like
            Data coordinates
        color : str, optional
            Point color
        s : float, optional
            Marker area in points**2 (matplotlib ``scatter`` convention).
            Default 20 when neither ``s`` nor ``markersize`` is given.
            A per-point array is not supported: GLE's ``msize`` is a
            per-dataset attribute, so one series draws one marker size.
        marker : str
            Marker symbol
        label : str, optional
            Legend label
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        markersize : float, optional
            Marker diameter in points (matplotlib ``Line2D``/:meth:`plot`
            convention). Takes precedence over ``s``.
        fillstyle : {'full', 'none'}, optional
            ``'none'`` draws open (outline) markers instead of filled ones.
        markerfacecolor : str, optional
            ``'none'`` is equivalent to ``fillstyle='none'``; ``'white'``
            gives outline markers with an opaque white interior. Also
            accepted as the matplotlib alias ``mfc``.
        zorder : float, optional
            Draw order relative to other data series on the same axes.
            Higher values are drawn on top.
        **kwargs
            Additional arguments

        Returns
        -------
        self
        """
        label = mathtext_to_gle(label)

        if markersize is None:
            if s is None:
                s = self.SCATTER_DEFAULT_S
            if np.ndim(s) != 0:
                raise ValueError(
                    "scatter(s=...) must be a single size: GLE's msize is a "
                    "per-dataset attribute, so every point in a series is "
                    "drawn at one size. Plot one series per size instead."
                )
            # matplotlib: s is an area in points**2 and markersize a diameter
            # in points, so markersize = sqrt(s). The 1.2 is gleplot's own
            # visibility factor, kept so scatter sizes are unchanged.
            markersize = np.sqrt(float(s)) * 1.2
        elif np.ndim(markersize) != 0:
            raise ValueError(
                "scatter(markersize=...) must be a single size: GLE's msize "
                "is a per-dataset attribute, so every point in a series is "
                "drawn at one size. Plot one series per size instead."
            )
        return self.plot(
            x,
            y,
            linestyle="none",
            color=color,
            marker=marker,
            markersize=markersize,
            label=label,
            yaxis=yaxis,
            fillstyle=fillstyle,
            markerfacecolor=markerfacecolor,
            zorder=zorder,
            **kwargs,
        )

    def bar(
        self,
        x,
        height,
        color: Optional[Union[str, List[str]]] = None,
        label: Optional[str] = None,
        zorder: Optional[float] = None,
        **kwargs,
    ):
        """
        Create bar chart.

        Note: Due to GLE limitations, all bars in a chart use the same color.
        If a list of colors is provided, only the first color is used.

        Parameters
        ----------
        x : array-like
            Bar positions or categories
        height : array-like
            Bar heights
        color : str or list of str, optional
            Bar color. If a list is provided, only the first color is used
            due to GLE limitations. Default is 'red'.
        label : str, optional
            Legend label (currently not supported by GLE for bar charts)
        **kwargs
            Additional arguments

        Returns
        -------
        self

        Examples
        --------
        >>> fig = glp.figure()
        >>> ax = fig.add_subplot(111)
        >>> categories = np.array([1, 2, 3, 4, 5])
        >>> values = np.array([10, 24, 36, 18, 7])
        >>> ax.bar(categories, values, color='blue')
        >>> fig.savefig('bar_chart.pdf')
        """
        data_name = kwargs.pop("data_name", None)
        if zorder is None and "zorder" in kwargs:
            zorder = kwargs.pop("zorder")
        label = mathtext_to_gle(label)

        x = np.asarray(x, dtype=float)
        height = np.asarray(height, dtype=float)

        # Handle color - only first color is used due to GLE limitation
        if color is None:
            colors = ["RED"] * len(height)
        elif isinstance(color, str):
            colors = [rgb_to_gle(color)] * len(height)
        else:
            # Take first color only
            colors = [rgb_to_gle(color[0])] * len(height)

        bar_data = BarSeries(
            x=x,
            height=height,
            colors=colors,
            label=label,
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_build_column_names("x", ["height"], label),
        )
        self._register_series_draw_meta(bar_data, "bar", zorder)
        self.bars.append(bar_data)

        return self

    def fill_between(
        self,
        x,
        y1,
        y2,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        offset: float = 0.0,
        **kwargs,
    ):
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
            Transparency (0-1). Default 1.0 (opaque), matching matplotlib's
            ``fill_between`` and keeping every pre-Cairo-support figure's
            ``.gle`` output byte-identical unless a caller actually asks for
            transparency. Below 1.0, the fill is genuinely semi-transparent
            (``gleplot.colors.apply_alpha`` composes an ``rgba255(...)``
            colour) and rendering it requires GLE's Cairo device, which
            gleplot's compile pipeline enables automatically -- see
            :meth:`gleplot.figure.Figure.requires_cairo` and SPEC §6.1/§10.6.
        label : str, optional
            Legend label
        **kwargs
            Additional arguments

        Returns
        -------
        self
        """
        data_name = kwargs.pop("data_name", None)
        label = mathtext_to_gle(label)

        x = np.asarray(x)
        y1 = np.asarray(y1)
        y2 = np.asarray(y2)

        if color is None:
            color = "LIGHTBLUE"
        else:
            color = rgb_to_gle(color)

        fill_data = FillSeries(
            x=x,
            y1=y1,
            y2=y2,
            color=color,
            alpha=alpha,
            label=label,
            offset=float(offset),
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_unique_column_names(["x", "upper", "lower"]),
        )
        self.fills.append(fill_data)

        return self

    # -- reference lines & shaded spans ----------------------------------
    #
    # matplotlib's axvline/axhline/axvspan/axhspan take one data coordinate
    # (or a pair) and span the *whole* axis in the other direction. GLE has no
    # equivalent primitive: everything inside a graph block is a dataset, and
    # a dataset needs concrete numbers. Two consequences shape the design
    # below.
    #
    # 1. The concrete end points are computed at WRITE time, not call time
    #    (:meth:`materialize_reflines` / :meth:`materialize_spans`, called from
    #    ``Figure._write_axes_content`` after the axis limits are resolved).
    #    So a later ``set_ylim`` -- or autoscaling from data added after the
    #    axvline call -- is respected, exactly as in matplotlib. The generated
    #    ``.dat`` sidecar name, by contrast, is reserved at CALL time so it is
    #    stable across repeated saves of the same figure.
    #
    # 2. Spans are emitted with the ``fill``s and reference lines immediately
    #    after them, i.e. before bars/lines/scatters/errorbars, so data always
    #    draws on top of its guides. (matplotlib gives axvspan a lower zorder
    #    than lines for the same reason.)
    #
    # GLE clips datasets to the graph's axis range, so a guide whose value
    # falls outside the visible range simply does not appear -- which is what
    # makes these compose correctly with broken axes, where each segment shows
    # only the guides that land inside it.

    @staticmethod
    def _check_axes_fraction(lo: float, hi: float, names: str) -> Tuple[float, float]:
        """Validate a pair of axes-fraction bounds (matplotlib semantics)."""
        lo = float(lo)
        hi = float(hi)
        if not (0.0 <= lo <= 1.0) or not (0.0 <= hi <= 1.0):
            raise ValueError(f"{names} must be within [0, 1], got ({lo}, {hi})")
        return lo, hi

    def axvline(
        self,
        x: float = 0.0,
        ymin: float = 0.0,
        ymax: float = 1.0,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Draw a vertical reference line at data coordinate ``x``.

        Parameters
        ----------
        x : float
            Position of the line, in data coordinates.
        ymin, ymax : float
            Vertical extent as a fraction of the axes height (matplotlib
            semantics): ``0`` is the bottom of the axes, ``1`` the top.
        color : str, optional
            Line colour. Default: black.
        linestyle : str
            ``'-'``, ``'--'``, ``':'`` or ``'-.'``.
        linewidth : float
            Line width in points.
        label : str, optional
            Legend label.

        Returns
        -------
        dict
            The stored declaration (also appended to ``self.reflines``).

        Notes
        -----
        The line is realized as a two-point dataset whose end points are
        computed when the figure is written, so it tracks any axis limits set
        afterwards. It is drawn *underneath* the data series.
        """
        return self._add_refline(
            "v", x, ymin, ymax, color, linestyle, linewidth, label, kwargs
        )

    def axhline(
        self,
        y: float = 0.0,
        xmin: float = 0.0,
        xmax: float = 1.0,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Draw a horizontal reference line at data coordinate ``y``.

        ``xmin``/``xmax`` are the horizontal extent as a fraction of the axes
        width (matplotlib semantics). See :meth:`axvline` for the rest.
        """
        return self._add_refline(
            "h", y, xmin, xmax, color, linestyle, linewidth, label, kwargs
        )

    def _add_refline(
        self, orient, value, lo, hi, color, linestyle, linewidth, label, kwargs
    ):
        """Shared implementation of :meth:`axvline` / :meth:`axhline`."""
        names = "ymin/ymax" if orient == "v" else "xmin/xmax"
        lo, hi = self._check_axes_fraction(lo, hi, names)
        data_name = kwargs.pop("data_name", None)
        label = mathtext_to_gle(label)
        gle_color = "BLACK" if color is None else rgb_to_gle(color)

        entry = RefLine(
            type="refline",
            orient=orient,
            value=float(value),
            span_lo=lo,
            span_hi=hi,
            color=gle_color,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_build_column_names("x", ["y"], label),
        )
        self.reflines.append(entry)
        return entry

    def axvspan(
        self,
        xmin: float,
        xmax: float,
        ymin: float = 0.0,
        ymax: float = 1.0,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Shade the vertical band between data coordinates ``xmin`` and ``xmax``.

        Parameters
        ----------
        xmin, xmax : float
            Band edges, in data coordinates.
        ymin, ymax : float
            Vertical extent as a fraction of the axes height (matplotlib
            semantics).
        color : str, optional
            Fill colour. Default: light gray.
        alpha : float
            Transparency (0-1). Default 1.0 (opaque), matching matplotlib and
            keeping every pre-Cairo-support figure's ``.gle`` output
            byte-identical unless a caller actually asks for transparency.
            Below 1.0, the band is genuinely semi-transparent
            (``gleplot.colors.apply_alpha`` composes an ``rgba255(...)``
            colour, exactly as :meth:`fill_between` does -- spans are
            materialized into fills at write time) and rendering it requires
            GLE's Cairo device, which gleplot's compile pipeline enables
            automatically -- see :meth:`gleplot.figure.Figure.requires_cairo`
            and SPEC §6.1/§10.6.
        label : str, optional
            Legend label.

        Returns
        -------
        dict
            The stored declaration (also appended to ``self.spans``).
        """
        return self._add_span("v", xmin, xmax, ymin, ymax, color, alpha, label, kwargs)

    def axhspan(
        self,
        ymin: float,
        ymax: float,
        xmin: float = 0.0,
        xmax: float = 1.0,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Shade the horizontal band between data coordinates ``ymin`` and ``ymax``.

        ``xmin``/``xmax`` are the horizontal extent as a fraction of the axes
        width (matplotlib semantics). See :meth:`axvspan` for the rest,
        including the ``alpha`` behaviour.
        """
        return self._add_span("h", ymin, ymax, xmin, xmax, color, alpha, label, kwargs)

    def _add_span(self, orient, start, end, lo, hi, color, alpha, label, kwargs):
        """Shared implementation of :meth:`axvspan` / :meth:`axhspan`."""
        names = "ymin/ymax" if orient == "v" else "xmin/xmax"
        lo, hi = self._check_axes_fraction(lo, hi, names)
        data_name = kwargs.pop("data_name", None)
        label = mathtext_to_gle(label)
        gle_color = "LIGHTGRAY" if color is None else rgb_to_gle(color)

        entry = Span(
            type="span",
            orient=orient,
            start=float(start),
            end=float(end),
            span_lo=lo,
            span_hi=hi,
            color=gle_color,
            alpha=float(alpha),
            label=label,
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_unique_column_names(["x", "upper", "lower"]),
        )
        self.spans.append(entry)
        return entry

    @staticmethod
    def _fraction_to_data(lo: float, hi: float, vmin: float, vmax: float):
        """Map an axes-fraction pair onto the data range ``[vmin, vmax]``."""
        span = vmax - vmin
        return vmin + lo * span, vmin + hi * span

    def materialize_reflines(self, limits) -> List[LineSeries]:
        """Turn ``self.reflines`` into concrete two-point line series.

        Parameters
        ----------
        limits : tuple
            ``(xmin, xmax, ymin, ymax)`` -- the axis limits actually being
            written. Any of them may be ``None`` if they could not be
            resolved (an axes with no data at all), in which case the
            affected guides are skipped with a warning rather than emitting a
            dataset full of ``None``.

        Returns
        -------
        list of dict
            Line dicts in the same shape ``plot()`` produces, ready for
            ``GLEWriter.add_plot_line``. Nothing is stored back on the axes,
            so writing a figure twice does not duplicate content.
        """
        xmin, xmax, ymin, ymax = limits
        out: List[LineSeries] = []
        for entry in self.reflines:
            if entry["orient"] == "v":
                if ymin is None or ymax is None:
                    self._warn_unresolved("axvline", "y")
                    continue
                y0, y1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], ymin, ymax
                )
                x = np.array([entry["value"], entry["value"]], dtype=float)
                y = np.array([y0, y1], dtype=float)
            else:
                if xmin is None or xmax is None:
                    self._warn_unresolved("axhline", "x")
                    continue
                x0, x1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], xmin, xmax
                )
                x = np.array([x0, x1], dtype=float)
                y = np.array([entry["value"], entry["value"]], dtype=float)

            out.append(
                LineSeries(
                    type="line",
                    x=x,
                    y=y,
                    color=entry["color"],
                    marker=None,
                    markersize=0.1,
                    linestyle=entry["linestyle"],
                    linewidth=entry["linewidth"],
                    label=entry["label"],
                    yaxis="y",
                    offset=0.0,
                    data_file=entry["data_file"],
                    column_names=entry["column_names"],
                )
            )
        return out

    def materialize_spans(self, limits) -> List[FillSeries]:
        """Turn ``self.spans`` into concrete fill-between series.

        See :meth:`materialize_reflines`; the same contract applies (nothing
        is stored back, unresolvable limits skip with a warning).
        """
        xmin, xmax, ymin, ymax = limits
        out: List[FillSeries] = []
        for entry in self.spans:
            if entry["orient"] == "v":
                if ymin is None or ymax is None:
                    self._warn_unresolved("axvspan", "y")
                    continue
                y0, y1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], ymin, ymax
                )
                x = np.array([entry["start"], entry["end"]], dtype=float)
                upper = np.array([y1, y1], dtype=float)
                lower = np.array([y0, y0], dtype=float)
            else:
                if xmin is None or xmax is None:
                    self._warn_unresolved("axhspan", "x")
                    continue
                x0, x1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], xmin, xmax
                )
                x = np.array([x0, x1], dtype=float)
                upper = np.array([entry["end"], entry["end"]], dtype=float)
                lower = np.array([entry["start"], entry["start"]], dtype=float)

            out.append(
                FillSeries(
                    x=x,
                    y1=upper,
                    y2=lower,
                    color=entry["color"],
                    alpha=entry["alpha"],
                    label=entry["label"],
                    offset=0.0,
                    data_file=entry["data_file"],
                    column_names=entry["column_names"],
                )
            )
        return out

    @staticmethod
    def _warn_unresolved(what: str, axis: str) -> None:
        warnings.warn(
            f"{what}() was dropped: the {axis}-axis limits could not be "
            f"resolved (the axes has no data and no explicit set_{axis}lim), "
            f"so the line/band has no extent to span.",
            UserWarning,
            stacklevel=3,
        )

    def text(
        self,
        x: float,
        y: float,
        s: str,
        color: Optional[str] = None,
        fontsize: Optional[float] = None,
        ha: str = "left",
        va: str = "center",
        bbox: Optional[dict] = None,
        **kwargs,
    ):
        """Add free-form text annotation in data coordinates.

        Parameters
        ----------
        x, y : float
            Data coordinates.
        s : str
            Text to render.
        color : str, optional
            Text color.
        fontsize : float, optional
            Font size in points.
        ha : str, optional
            Horizontal alignment: 'left', 'center', or 'right'.
        va : str, optional
            Vertical alignment placeholder for API compatibility.
        bbox : dict, optional
            Optional text box settings. Supported key: ``facecolor``.
        """
        if color is None:
            gle_color = "BLACK"
        else:
            gle_color = rgb_to_gle(color)

        box_color = None
        if isinstance(bbox, dict):
            facecolor = bbox.get("facecolor")
            if facecolor is not None:
                box_color = rgb_to_gle(facecolor)

        self.texts.append(
            TextAnnotation(
                x=float(x),
                y=float(y),
                text=mathtext_to_gle(str(s)),
                color=gle_color,
                fontsize=float(fontsize) if fontsize is not None else None,
                ha=str(ha),
                va=str(va),
                box_color=box_color,
            )
        )
        return self

    # -- heatmaps & contours --------------------------------------------

    def _resolve_cmap(self, cmap: Optional[str]) -> str:
        """Return the canonical cmap name, falling back to the graph default."""
        if cmap is None:
            cmap = self.figure.graph.default_cmap
        return canonical_cmap(cmap)

    def _resolve_pixels(self, pixels) -> List[int]:
        """Normalize the ``pixels`` argument to a stored ``[px, py]`` int pair."""
        if pixels is None:
            px = int(self.figure.graph.colormap_pixels)
            return [px, px]
        if isinstance(pixels, (list, tuple)):
            px, py = int(pixels[0]), int(pixels[1])
            return [px, py]
        px = int(pixels)
        return [px, px]

    @staticmethod
    def _linestyle_to_lstyle(linestyle: Optional[str]) -> Optional[int]:
        """Map a matplotlib linestyle to a GLE ``lstyle`` int (None = solid)."""
        if linestyle in ("-", None, "", "solid"):
            return None
        return MATPLOTLIB_TO_LSTYLE.get(linestyle)

    def imshow(
        self,
        Z,
        extent=None,
        origin: str = "lower",
        cmap: Optional[str] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        interpolation: str = "bicubic",
        pixels=None,
        invert: bool = False,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Display gridded 2-D data ``Z`` as a colour map (heatmap).

        Parameters
        ----------
        Z : array-like, shape (ny, nx)
            Gridded scalar field.
        extent : tuple, optional
            ``(xmin, xmax, ymin, ymax)`` mapping the grid onto data
            coordinates. Default ``(0, nx, 0, ny)``.
        origin : {'lower', 'upper'}
            ``'lower'`` (default) puts row 0 of ``Z`` at ``ymin`` (the
            scientific convention; note this differs from matplotlib's
            ``'upper'`` default). ``'upper'`` flips the rows when writing the
            ``.z`` sidecar.
        cmap : str, optional
            Palette name (see :data:`gleplot.palettes.SUPPORTED_CMAPS`). When
            ``None``, uses the figure graph config's ``default_cmap``.
        vmin, vmax : float, optional
            Colour normalization range (GLE ``zmin``/``zmax``). ``None`` uses
            GLE's data-range default.
        interpolation : {'bicubic', 'nearest'}
            Sampling interpolation for the ``.z`` grid.
        pixels : int or (px, py), optional
            Bitmap resolution. Default from graph config ``colormap_pixels``.
        invert : bool
            Invert the colour mapping.
        label : str, optional
            Series label (not drawn by the colormap itself; kept for the GUI).

        Returns
        -------
        dict
            The stored heatmap series dict.
        """
        label = mathtext_to_gle(label)
        if origin not in ("lower", "upper"):
            raise ValueError("origin must be 'lower' or 'upper'")
        z = np.asarray(Z, dtype=float)
        if z.ndim != 2:
            raise ValueError("imshow requires a 2-D array Z")
        _require_finite(z, "imshow Z")
        ny, nx = z.shape
        if extent is None:
            ext = [0.0, float(nx), 0.0, float(ny)]
        else:
            ext = [float(v) for v in extent]
            if len(ext) != 4:
                raise ValueError("extent must be (xmin, xmax, ymin, ymax)")
            _require_valid_extent(ext)

        if self.heatmaps:
            raise ValueError(
                "GLE supports at most one heatmap (colormap) per axes; "
                "this axes already has one"
            )

        data_file = _reserve_sidecar(self.figure, "heatmap", "z")
        hm = HeatmapSeries(
            type="heatmap",
            source="grid",
            z=z,
            x=None,
            y=None,
            zpts=None,
            extent=ext,
            origin=origin,
            cmap=self._resolve_cmap(cmap),
            vmin=None if vmin is None else float(vmin),
            vmax=None if vmax is None else float(vmax),
            interpolation="nearest" if interpolation == "nearest" else "bicubic",
            pixels=self._resolve_pixels(pixels),
            invert=bool(invert),
            gridsize=None,
            ncontour=None,
            label=label,
            data_file=data_file,
            colorbar=None,
        )
        self.heatmaps.append(hm)
        return hm

    def contour(
        self,
        *args,
        levels=None,
        colors: str = "black",
        linewidths: float = 1.0,
        linestyles: str = "-",
        clabel: bool = False,
        clabel_fmt: str = "fix 1",
        label: Optional[str] = None,
        **kwargs,
    ):
        """Draw contour lines of gridded data.

        Signatures: ``contour(Z)`` or ``contour(x, y, Z)`` with 1-D ``x`` (nx),
        1-D ``y`` (ny), 2-D ``Z`` (ny, nx). ``x``/``y`` must be uniformly
        spaced.

        The matplotlib spelling ``contour(X, Y, Z)`` with 2-D ``X``/``Y`` from
        ``np.meshgrid`` is also accepted: the grid is checked for regularity
        (constant rows in ``X``, constant columns in ``Y``) and its 1-D axes
        extracted, since GLE's ``.z`` grid is an extent plus a shape. A
        genuinely irregular grid raises -- use :meth:`tricontour` for
        scattered data.

        Parameters
        ----------
        levels : None, int, or sequence
            ``None`` uses GLE's default 10 levels. An int ``n`` emits
            ``values from zmin to zmax step (zmax-zmin)/n``. A sequence emits
            ``values v1 v2 ...``.
        colors : str
            Contour line colour.
        linewidths : float
            Line width (matplotlib points).
        linestyles : str
            Line style ('-', '--', ':', '-.').
        clabel : bool
            Draw inline contour labels from the generated ``-clabels.dat``.
        clabel_fmt : str
            GLE ``format$`` string for the labels.

        Returns
        -------
        dict
            The stored contour series dict.
        """
        label = mathtext_to_gle(label)
        z, ext = self._grid_from_args(args)
        levels_resolved = self._resolve_levels(levels, z)
        # Explicit levels that all lie outside the data range would make GLE's
        # ``begin contour`` emit an EMPTY ``-cdata.dat`` (no crossings), and the
        # ``data "...-cdata.dat"`` line then aborts the whole compile with a
        # cryptic "column index out of range". We have the grid here, so reject
        # early with a clear message (a partially in-range level set is fine).
        if levels_resolved:
            zmn = float(np.min(z))
            zmx = float(np.max(z))
            if not any(zmn < lv < zmx for lv in levels_resolved):
                raise ValueError(
                    f"contour levels {levels_resolved} all lie outside the data "
                    f"range ({zmn}, {zmx}); no contour lines would be drawn"
                )
        data_file = _reserve_sidecar(self.figure, "contour", "z")
        ct = ContourSeries(
            type="contour",
            source="grid",
            z=z,
            x=None,
            y=None,
            zpts=None,
            extent=ext,
            levels=levels_resolved,
            color=rgb_to_gle(colors),
            linewidth=float(linewidths),
            linestyle=self._linestyle_to_lstyle(linestyles),
            clabel=bool(clabel),
            clabel_fmt=str(clabel_fmt),
            gridsize=None,
            ncontour=None,
            label=label,
            data_file=data_file,
        )
        self.contours.append(ct)
        return ct

    def _grid_from_args(self, args):
        """Parse ``contour`` positional args into ``(z_2d, extent)``."""
        if len(args) == 1:
            z = np.asarray(args[0], dtype=float)
            if z.ndim != 2:
                raise ValueError("contour(Z) requires a 2-D array")
            _require_finite(z, "contour Z")
            ny, nx = z.shape
            return z, [0.0, float(nx), 0.0, float(ny)]
        if len(args) == 3:
            x = np.asarray(args[0], dtype=float)
            y = np.asarray(args[1], dtype=float)
            z = np.asarray(args[2], dtype=float)
            # matplotlib's usual call passes the 2-D X, Y from np.meshgrid.
            # Accept those: check the grid is regular and take its 1-D axes,
            # which is what GLE's .z grid (extent + shape) is defined by.
            if z.ndim == 2:
                for coord, cname in ((x, "x"), (y, "y")):
                    if coord.ndim == 2 and coord.shape != z.shape:
                        raise ValueError(
                            f"contour(X, Y, Z): 2-D {cname.upper()} has shape "
                            f"{coord.shape} but Z has shape {z.shape}; a "
                            "meshgrid coordinate array must match Z"
                        )
                if x.ndim == 2:
                    x = _axis_from_meshgrid(x, "x")
                if y.ndim == 2:
                    y = _axis_from_meshgrid(y, "y")
            if x.ndim != 1 or y.ndim != 1 or z.ndim != 2:
                raise ValueError(
                    "contour(x, y, Z) requires 1-D x, 1-D y, 2-D Z (or "
                    "matplotlib's 2-D meshgrid X, Y matching Z's shape)"
                )
            if z.shape != (len(y), len(x)):
                raise ValueError(
                    f"Z shape {z.shape} does not match (len(y), len(x)) = "
                    f"({len(y)}, {len(x)})"
                )
            _require_finite(x, "contour x")
            _require_finite(y, "contour y")
            _require_finite(z, "contour Z")
            self._check_uniform(x, "x")
            self._check_uniform(y, "y")
            ext = [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])]
            _require_valid_extent(ext)
            return z, ext
        raise ValueError("contour expects contour(Z) or contour(x, y, Z)")

    @staticmethod
    def _check_uniform(v, name):
        """Validate that a 1-D coordinate array is uniformly spaced."""
        if len(v) < 2:
            return
        diffs = np.diff(v)
        step = diffs[0]
        if step == 0 or not np.allclose(diffs, step, rtol=1e-6, atol=1e-12):
            raise ValueError(
                f"contour requires uniformly spaced {name} (a .z grid is "
                "uniform); got non-uniform spacing"
            )

    @staticmethod
    def _resolve_levels(levels, z):
        """Resolve the ``levels`` argument to ``None`` or a list of floats.

        ``None`` -> ``None`` (GLE's default 10 levels). An int ``n`` is resolved
        at store time to ``n`` explicit levels evenly spaced strictly between the
        data's min and max -- emitted as an explicit ``values`` list rather than
        the GLE ``values from a to b step s`` form, because the recognizer models
        only the explicit-list form (round-trip safety). An explicit sequence is
        stored verbatim as floats.
        """
        if levels is None:
            return None
        if isinstance(levels, (int, np.integer)) and not isinstance(levels, bool):
            n = int(levels)
            if n < 1:
                raise ValueError("levels count must be >= 1")
            zmin = float(np.nanmin(z))
            zmax = float(np.nanmax(z))
            return [float(v) for v in np.linspace(zmin, zmax, n + 2)[1:-1]]
        return [float(v) for v in levels]

    def tripcolor(
        self,
        x,
        y,
        z,
        gridsize=(50, 50),
        extent=None,
        cmap: Optional[str] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        interpolation: str = "bicubic",
        pixels=None,
        invert: bool = False,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Heatmap from scattered ``(x, y, z)`` samples via GLE ``fitz`` gridding.

        Writes a points sidecar (raw ``x y z`` triples) and emits a
        ``begin fitz`` block that grids the data (Akima interpolation) to a
        ``.z`` file at GLE compile time, then a ``colormap`` of that grid.

        Parameters
        ----------
        x, y, z : array-like
            Equal-length 1-D scattered samples.
        gridsize : (nx, ny)
            Interpolation grid resolution.
        extent : tuple, optional
            ``(xmin, xmax, ymin, ymax)``. Default: data bounds.
        (remaining kwargs as :meth:`imshow`).
        """
        label = mathtext_to_gle(label)
        if self.heatmaps:
            raise ValueError(
                "GLE supports at most one heatmap (colormap) per axes; "
                "this axes already has one"
            )
        xa, ya, za, ext, gs = self._points_from_args(x, y, z, gridsize, extent)
        data_file = _reserve_sidecar(self.figure, "points", "dat")
        hm = HeatmapSeries(
            type="heatmap",
            source="points",
            z=None,
            x=xa,
            y=ya,
            zpts=za,
            extent=ext,
            origin="lower",
            cmap=self._resolve_cmap(cmap),
            vmin=None if vmin is None else float(vmin),
            vmax=None if vmax is None else float(vmax),
            interpolation="nearest" if interpolation == "nearest" else "bicubic",
            pixels=self._resolve_pixels(pixels),
            invert=bool(invert),
            gridsize=gs,
            ncontour=None,
            label=label,
            data_file=data_file,
            colorbar=None,
        )
        self.heatmaps.append(hm)
        return hm

    def tricontour(
        self,
        x,
        y,
        z,
        gridsize=(50, 50),
        extent=None,
        ncontour: int = 3,
        levels=None,
        colors: str = "black",
        linewidths: float = 1.0,
        linestyles: str = "-",
        clabel: bool = False,
        clabel_fmt: str = "fix 1",
        label: Optional[str] = None,
        **kwargs,
    ):
        """Contour lines from scattered ``(x, y, z)`` samples via GLE ``fitz``.

        Writes a points sidecar and emits a ``begin fitz`` block (gridding at
        compile time) followed by a ``begin contour`` block on the generated
        ``.z`` grid.

        Parameters
        ----------
        ncontour : int
            ``fitz`` neighbour-point count per interpolation node.
        (remaining kwargs as :meth:`contour`).
        """
        label = mathtext_to_gle(label)
        xa, ya, za, ext, gs = self._points_from_args(x, y, z, gridsize, extent)
        # For explicit-level or count resolution we approximate the grid range
        # from the scattered z-values (GLE grids at compile time).
        levels_resolved = self._resolve_levels(levels, za)
        data_file = _reserve_sidecar(self.figure, "points", "dat")
        ct = ContourSeries(
            type="contour",
            source="points",
            z=None,
            x=xa,
            y=ya,
            zpts=za,
            extent=ext,
            levels=levels_resolved,
            color=rgb_to_gle(colors),
            linewidth=float(linewidths),
            linestyle=self._linestyle_to_lstyle(linestyles),
            clabel=bool(clabel),
            clabel_fmt=str(clabel_fmt),
            gridsize=gs,
            ncontour=int(ncontour),
            label=label,
            data_file=data_file,
        )
        self.contours.append(ct)
        return ct

    @staticmethod
    def _points_from_args(x, y, z, gridsize, extent):
        """Validate scattered inputs; return (x, y, z, extent, [nx, ny])."""
        xa = np.asarray(x, dtype=float).ravel()
        ya = np.asarray(y, dtype=float).ravel()
        za = np.asarray(z, dtype=float).ravel()
        if not (len(xa) == len(ya) == len(za)):
            raise ValueError("x, y, z must have equal length")
        _require_finite(xa, "scattered x")
        _require_finite(ya, "scattered y")
        _require_finite(za, "scattered z")
        if len(xa) < 3:
            raise ValueError("scattered gridding needs at least 3 points")
        gs = [int(gridsize[0]), int(gridsize[1])]
        if gs[0] < 2 or gs[1] < 2:
            raise ValueError("gridsize entries must be >= 2")
        if extent is None:
            ext = [float(xa.min()), float(xa.max()), float(ya.min()), float(ya.max())]
        else:
            ext = [float(v) for v in extent]
            if len(ext) != 4:
                raise ValueError("extent must be (xmin, xmax, ymin, ymax)")
        _require_valid_extent(ext)
        return xa, ya, za, ext, gs

    def set_xlabel(self, label: str):
        """Set x-axis label."""
        self.xlabel_text = mathtext_to_gle(label)
        return self

    def set_ylabel(self, label: str, axis: str = "y"):
        """Set y-axis label.

        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        label = mathtext_to_gle(label)
        if axis == "y2":
            self.y2label_text = label
        else:
            self.ylabel_text = label
        return self

    def set_title(self, label: str):
        """Set subplot title."""
        self.title_text = mathtext_to_gle(label)
        return self

    def set_xscale(self, scale: str):
        """Set x-axis scale ('linear' or 'log')."""
        self.xscale = scale
        return self

    def set_yscale(self, scale: str, axis: str = "y"):
        """Set y-axis scale.

        Parameters
        ----------
        scale : str
            Scale type: 'linear' or 'log'
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == "y2":
            self.y2scale = scale
        else:
            self.yscale = scale
        return self

    def set_xlim(self, xmin: float, xmax: float):
        """Set x-axis limits."""
        self.xmin = xmin
        self.xmax = xmax
        return self

    def set_ylim(self, ymin: float, ymax: float, axis: str = "y"):
        """Set y-axis limits.

        Parameters
        ----------
        ymin, ymax : float
            Axis limits
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == "y2":
            self.y2min = ymin
            self.y2max = ymax
        else:
            self.ymin = ymin
            self.ymax = ymax
        return self

    def set_xticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks: Optional[float] = None,
        dsubticks: Optional[float] = None,
    ):
        """Control x-axis tick placement.

        Parameters
        ----------
        ticks : sequence of float, optional
            Explicit tick positions (GLE ``xplaces``). Passing ``None`` leaves
            the current setting alone; pass an empty sequence to draw no
            labelled ticks at all.
        labels : sequence of str, optional
            Tick labels (GLE ``xnames``), one per entry of ``ticks``.
        dticks : float, optional
            Major tick interval (GLE ``dticks``) -- the usual way to keep two
            segments of a broken axis from colliding at the seam.
        dsubticks : float, optional
            Minor tick interval (GLE ``dsubticks``).

        Returns
        -------
        self
        """
        if ticks is not None:
            self.xplaces = [float(t) for t in ticks]
        if labels is not None:
            # Tick labels are user-supplied display text like any other, so
            # they get the same mathtext translation / literal escaping.
            self.xnames = [mathtext_to_gle(str(lbl)) for lbl in labels]
        if dticks is not None:
            self.xdticks = float(dticks)
        if dsubticks is not None:
            self.xdsubticks = float(dsubticks)
        return self

    def set_yticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks: Optional[float] = None,
        dsubticks: Optional[float] = None,
    ):
        """Control y-axis tick placement. See :meth:`set_xticks`."""
        if ticks is not None:
            self.yplaces = [float(t) for t in ticks]
        if labels is not None:
            self.ynames = [mathtext_to_gle(str(lbl)) for lbl in labels]
        if dticks is not None:
            self.ydticks = float(dticks)
        if dsubticks is not None:
            self.ydsubticks = float(dsubticks)
        return self

    def legend(self, loc: str = "best", **kwargs):
        """Show a legend (GLE's graph ``key``).

        Parameters
        ----------
        loc : str
            matplotlib legend location. All eleven matplotlib strings map onto
            GLE's nine key anchors (``'best'`` is not computed -- like
            matplotlib's own ``'best'`` fallback in ambiguous cases it means
            top right). GLE short forms (``'tr'``, ``'bl'``, ...) are also
            accepted. An unrecognized value warns and uses top right.
        fontsize : float or str, optional
            Legend text height, in matplotlib points, emitted as GLE's
            ``key ... hei`` (the only lever on key size before this existed
            was the figure-wide style fontsize). matplotlib's relative names
            (``'small'``, ``'x-large'``, ...) are resolved against the
            figure's style fontsize at call time.
        frameon : bool, optional
            Draw the box around the key (default ``True``, as matplotlib).
            ``False`` emits GLE's ``key ... nobox``.
        ncol, ncols : int, optional
            Only a single column is expressible: GLE builds multi-column keys
            from ``separator`` commands in a standalone ``begin key`` block,
            which gleplot does not emit. ``1`` is accepted; anything else
            warns.
        **kwargs
            Any other matplotlib legend keyword has no GLE ``key`` equivalent
            and warns rather than being silently dropped.

        Returns
        -------
        self
        """
        self.legend_on = True

        # matplotlib's first positional argument may be a handles/labels
        # sequence. gleplot takes legend text from each series' ``label=``,
        # so an explicit sequence cannot be honoured -- say so.
        if loc is not None and not isinstance(loc, str):
            warnings.warn(
                "legend(): explicit handles/labels are not supported; legend "
                "text comes from each series' label= argument. The positional "
                "argument was ignored.",
                UserWarning,
                stacklevel=2,
            )
            loc = "best"

        self.legend_pos = self._resolve_legend_loc(loc)

        if "fontsize" in kwargs:
            fontsize = kwargs.pop("fontsize")
            self.legend_fontsize = (
                None if fontsize is None else self._resolve_legend_fontsize(fontsize)
            )

        if "frameon" in kwargs:
            frameon = kwargs.pop("frameon")
            self.legend_frameon = True if frameon is None else bool(frameon)

        if "offset" in kwargs:
            # gleplot extension (not a matplotlib kwarg): displace the key
            # from its anchor by (dx, dy) IN CM, GLE's ``key ... offset``.
            # GLE displaces INWARD from the anchored corner: for pos tr,
            # positive dx moves LEFT and positive dy moves DOWN (verified by
            # compiled pixel-diff; negative values can leave the canvas).
            offset = kwargs.pop("offset")
            if offset is None:
                self.legend_offset = None
            else:
                try:
                    dx, dy = (float(offset[0]), float(offset[1]))
                except (TypeError, ValueError, IndexError):
                    raise ValueError(
                        "legend(offset=...) expects a (dx_cm, dy_cm) pair of "
                        f"numbers, got {offset!r}"
                    ) from None
                self.legend_offset = (dx, dy)

        for name in ("ncol", "ncols"):
            if name in kwargs:
                ncol = kwargs.pop(name)
                if ncol is not None and int(ncol) != 1:
                    warnings.warn(
                        f"legend({name}={ncol!r}) is not supported: a GLE "
                        "graph-block key is always a single column (multiple "
                        "columns need a standalone 'begin key' block with "
                        "'separator' commands). Drawing one column.",
                        UserWarning,
                        stacklevel=2,
                    )

        for name in sorted(kwargs):
            warnings.warn(
                f"legend({name}=...) is not supported and was ignored: GLE's "
                "key command understands only position, text height "
                "(fontsize), the box (frameon), and offset.",
                UserWarning,
                stacklevel=2,
            )

        return self

    @staticmethod
    def _resolve_legend_loc(loc) -> str:
        """Map a matplotlib ``loc`` onto a gleplot long-form key position."""
        if loc is None:
            return "top right"
        key = str(loc).strip().lower()
        if key in MATPLOTLIB_TO_GLE_LEGEND_LOC:
            return MATPLOTLIB_TO_GLE_LEGEND_LOC[key]
        # A GLE short form ('tr', 'bl', ...) or an already-long gleplot form.
        if key in KEY_POSITIONS_SHORT_TO_LONG:
            return KEY_POSITIONS_SHORT_TO_LONG[key]
        if key in KEY_POSITIONS_LONG_TO_SHORT:
            return key
        warnings.warn(
            f"legend(loc={loc!r}) is not a recognized matplotlib location or "
            "GLE key position; using 'upper right'.",
            UserWarning,
            stacklevel=3,
        )
        return "top right"

    def _resolve_legend_fontsize(self, fontsize) -> float:
        """Resolve a matplotlib ``fontsize`` (number or name) to points."""
        if isinstance(fontsize, str):
            name = fontsize.strip().lower()
            if name not in MATPLOTLIB_RELATIVE_FONTSIZES:
                raise ValueError(
                    f"legend(fontsize={fontsize!r}) is not a number or one of "
                    f"{sorted(MATPLOTLIB_RELATIVE_FONTSIZES)}"
                )
            style = getattr(self.figure, "style", None) or GlobalConfig.get_style()
            return float(style.fontsize) * MATPLOTLIB_RELATIVE_FONTSIZES[name]
        size = float(fontsize)
        if size <= 0:
            raise ValueError(f"legend(fontsize={fontsize!r}) must be positive")
        return size

    def grid(self, visible: bool = True, **kwargs):
        """Toggle grid (placeholder for future implementation)."""
        # GLE grid support can be added later
        return self

    def get_xlim(self) -> Tuple[float, float]:
        """Get x-axis limits."""
        return self.xmin, self.xmax

    def get_ylim(self, axis: str = "y") -> Tuple[float, float]:
        """Get y-axis limits.

        Parameters
        ----------
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        if axis == "y2":
            return self.y2min, self.y2max
        else:
            return self.ymin, self.ymax

    def has_plots(self) -> bool:
        """Check if axes has any plots."""
        return bool(
            self.lines
            or self.scatters
            or self.bars
            or self.fills
            or self.errorbars
            or self.file_series
            or self.heatmaps
            or self.contours
            or self.reflines
            or self.spans
        )

    def has_y2_plots(self) -> bool:
        """Check if axes has any plots using the y2 axis."""
        y2_capable: Sequence[Sequence[Series]] = (
            self.lines,
            self.scatters,
            self.errorbars,
        )
        for plot_list in y2_capable:
            for plot_data in plot_list:
                if plot_data.get("yaxis") == "y2":
                    return True
        return False

    # -- Serialization ----------------------------------------------------
    #
    # The series list order, which keys hold numeric arrays, and the sidecar
    # header-row fallback all come from the series classes now (see
    # :mod:`gleplot.series`), so there is nothing left to keep in sync by
    # hand here.

    #: Series list attributes serialized on every axes, in a stable order.
    _SERIES_ATTRS: Tuple[str, ...] = SERIES_ATTRS

    def to_dict(self) -> dict:
        """Serialize this axes to a JSON-safe dictionary.

        Captures the subplot position, all axis/scale/limit/legend state,
        the shared-axes visibility flags, and every series list (lines,
        scatters, bars, fills, errorbars, file_series, texts) with their
        numeric data converted to plain Python lists. numpy arrays and
        scalars are converted so the result is directly ``json``-safe and
        deterministic.

        The ``data_file`` name stored on each generated series is preserved
        verbatim so that a round-trip produces byte-identical GLE regardless
        of the module-global data-file counter state.
        """
        payload: Dict[str, Any] = {
            "position": list(self.position) if self.position is not None else None,
            "xlabel_text": self.xlabel_text,
            "ylabel_text": self.ylabel_text,
            "y2label_text": self.y2label_text,
            "title_text": self.title_text,
            "xscale": self.xscale,
            "yscale": self.yscale,
            "y2scale": self.y2scale,
            "xmin": _to_jsonable(self.xmin),
            "xmax": _to_jsonable(self.xmax),
            "ymin": _to_jsonable(self.ymin),
            "ymax": _to_jsonable(self.ymax),
            "y2min": _to_jsonable(self.y2min),
            "y2max": _to_jsonable(self.y2max),
            "legend_on": self.legend_on,
            "legend_pos": self.legend_pos,
            "legend_fontsize": _to_jsonable(self.legend_fontsize),
            "legend_frameon": self.legend_frameon,
            "legend_offset": _to_jsonable(self.legend_offset),
            "show_xlabel": self._show_xlabel,
            "show_ylabel": self._show_ylabel,
            "show_xticks": self._show_xticks,
            "show_yticks": self._show_yticks,
            "remove_last_xtick": getattr(self, "_remove_last_xtick", False),
            "remove_last_ytick": getattr(self, "_remove_last_ytick", False),
            "remove_first_xtick": getattr(self, "_remove_first_xtick", False),
            "remove_first_ytick": getattr(self, "_remove_first_ytick", False),
            "xdticks": _to_jsonable(self.xdticks),
            "ydticks": _to_jsonable(self.ydticks),
            "xdsubticks": _to_jsonable(self.xdsubticks),
            "ydsubticks": _to_jsonable(self.ydsubticks),
            "xplaces": _to_jsonable(self.xplaces),
            "xnames": _to_jsonable(self.xnames),
            "yplaces": _to_jsonable(self.yplaces),
            "ynames": _to_jsonable(self.ynames),
            "xaxis_off": self._xaxis_off,
            "yaxis_off": self._yaxis_off,
            "x2axis_off": self._x2axis_off,
            "y2axis_off": self._y2axis_off,
            "break_index": self._break_index,
            # Explicit page geometry (see __init__): the frame rect, or the
            # verbatim geometry statements when no rect is invertible. Both
            # unset = auto placement.
            "placement": (
                [float(v) for v in self.placement]
                if self.placement is not None
                else None
            ),
            "geometry_passthrough": list(self.geometry_passthrough),
        }
        # Series lists, in registry order -- exactly where they appeared when
        # each was spelled out here by hand, so the key order (and therefore
        # the serialized bytes) is unchanged.
        for attr in SERIES_ATTRS:
            payload[attr] = [_to_jsonable(s) for s in getattr(self, attr)]
        payload["passthrough"] = list(self.passthrough)
        return payload

    @classmethod
    def from_dict(cls, figure, d: dict) -> "Axes":
        """Reconstruct an :class:`Axes` from a :meth:`to_dict` payload.

        Parameters
        ----------
        figure : Figure
            Parent figure the new axes is attached to.
        d : dict
            Axes payload produced by :meth:`to_dict`. Unknown keys are
            ignored for forward compatibility.

        Each series is rebuilt as its :mod:`gleplot.series` class, whose
        ``ARRAY_FIELDS`` say which values are restored to ``float`` numpy
        arrays; optional error arrays that were ``None`` stay ``None``. All
        style keys, labels and the ``data_file`` names are restored
        verbatim, as are any keys the class does not declare (a project
        written by a newer gleplot still round-trips).
        """
        position = d.get("position")
        if position is not None:
            position = tuple(position)
        ax = cls(figure, position)

        ax.xlabel_text = d.get("xlabel_text", "")
        ax.ylabel_text = d.get("ylabel_text", "")
        ax.y2label_text = d.get("y2label_text", "")
        ax.title_text = d.get("title_text", "")
        ax.xscale = d.get("xscale", "linear")
        ax.yscale = d.get("yscale", "linear")
        ax.y2scale = d.get("y2scale", "linear")
        ax.xmin = d.get("xmin")
        ax.xmax = d.get("xmax")
        ax.ymin = d.get("ymin")
        ax.ymax = d.get("ymax")
        ax.y2min = d.get("y2min")
        ax.y2max = d.get("y2max")
        ax.legend_on = d.get("legend_on")  # tri-state; missing key = auto
        ax.legend_pos = d.get("legend_pos", "top right")
        # Missing keys = a pre-1.9.2 payload: inherit the style fontsize and
        # draw the box, which is exactly what those figures rendered as.
        ax.legend_fontsize = d.get("legend_fontsize")
        ax.legend_frameon = d.get("legend_frameon", True)
        _offset = d.get("legend_offset")
        ax.legend_offset = (
            None if _offset is None else (float(_offset[0]), float(_offset[1]))
        )

        ax._show_xlabel = d.get("show_xlabel", True)
        ax._show_ylabel = d.get("show_ylabel", True)
        ax._show_xticks = d.get("show_xticks", True)
        ax._show_yticks = d.get("show_yticks", True)
        ax._remove_last_xtick = d.get("remove_last_xtick", False)
        ax._remove_last_ytick = d.get("remove_last_ytick", False)
        ax._remove_first_xtick = d.get("remove_first_xtick", False)
        ax._remove_first_ytick = d.get("remove_first_ytick", False)

        ax.xdticks = d.get("xdticks")
        ax.ydticks = d.get("ydticks")
        ax.xdsubticks = d.get("xdsubticks")
        ax.ydsubticks = d.get("ydsubticks")
        ax.xplaces = d.get("xplaces")
        ax.xnames = d.get("xnames")
        ax.yplaces = d.get("yplaces")
        ax.ynames = d.get("ynames")
        ax._xaxis_off = d.get("xaxis_off", False)
        ax._yaxis_off = d.get("yaxis_off", False)
        ax._x2axis_off = d.get("x2axis_off", False)
        ax._y2axis_off = d.get("y2axis_off", False)
        # ``_break_owner`` is a back-reference rebound by Figure.from_dict
        # after every axes exists (see gleplot.brokenaxes.BrokenAxes).
        ax._break_index = d.get("break_index")

        # Explicit page geometry. Missing keys = a pre-geometry payload, i.e.
        # auto placement -- exactly what those figures rendered as.
        _placement = d.get("placement")
        ax.placement = (
            None
            if _placement is None
            else (
                float(_placement[0]),
                float(_placement[1]),
                float(_placement[2]),
                float(_placement[3]),
            )
        )
        ax.geometry_passthrough = list(d.get("geometry_passthrough") or [])

        for attr, series_cls in SERIES_CLASSES.items():
            restored = []
            for payload in d.get(attr, []):
                item = series_cls._restore(payload)
                for key in series_cls.ARRAY_FIELDS:
                    item[key] = _to_float_array(item.get(key))
                # Older projects (pre Track E3) have no 'column_names' key at
                # all on their series; regenerate the same defaults the
                # plotting methods would produce so the next save still gets
                # a named header row instead of silently reverting to none.
                if "column_names" not in item:
                    defaults = item.default_column_names()
                    if defaults is not None:
                        item["column_names"] = defaults
                restored.append(item)
            setattr(ax, attr, restored)

        ax.passthrough = list(d.get("passthrough", []))

        max_seq = -1
        for attr in ("bars", "lines", "scatters", "errorbars"):
            for item in getattr(ax, attr):
                seq = item.get("_draw_seq")
                if seq is not None:
                    max_seq = max(max_seq, int(seq))
        ax._draw_seq_counter = max_seq + 1 if max_seq >= 0 else 0

        return ax


def sorted_zorder_drawables(ax: "Axes") -> List[Tuple[str, Series]]:
    """Bars, lines, scatters, and errorbars sorted by ``(zorder, call order)``.

    The kind name and both fallbacks come from the series classes
    (:data:`gleplot.series.DRAWABLE_CLASSES`), so a new drawable kind only
    has to declare ``KIND``/``ZORDER_DEFAULT``/``KIND_RANK`` to join the
    ordering. An explicit ``zorder`` on a series wins; ``_draw_seq`` records
    the call order and is absent only on pre-zorder projects, where the
    kind rank reproduces the old fixed emission stack.
    """
    items: List[Tuple[float, float, str, Series]] = []
    for kind, series_cls in DRAWABLE_CLASSES.items():
        series_list = getattr(ax, series_cls.ATTR)
        for idx, data in enumerate(series_list):
            z = (
                float(data["zorder"])
                if "zorder" in data
                else SERIES_ZORDER_DEFAULT[kind]
            )
            draw_seq = data.get("_draw_seq")
            if draw_seq is None:
                draw_seq = _SERIES_KIND_RANK[kind] * 1_000_000 + idx
            items.append((z, float(draw_seq), kind, data))
    items.sort(key=lambda t: (t[0], t[1]))
    return [(kind, data) for _z, _seq, kind, data in items]

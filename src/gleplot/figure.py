"""Figure class for gleplot."""

import math
import re
import warnings
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union, cast

import numpy as np

from . import axes as _axes_module
from . import palettes as _pal
from ._warn import warn_external, warn_unsupported_keywords
from .axes import (
    Axes,
    _finite_float,
    _rename_text_aliases,
    _resolve_fontsize,
    _text_fields,
    _validate_data_prefix,
    histogram_counts,
)
from .brokenaxes import BrokenAxes
from .cairo_support import cairo_font_warning, figure_requires_cairo
from .colors import apply_alpha, rgb_to_gle
from .compiler import (
    RASTER_COMPILE_FORMATS,
    SUFFIX_TO_COMPILE_FORMAT,
    CompileFormat,
    GLECompiler,
    _remove_tex_cache,
    remove_generated_intermediates,
)
from .config import (
    _SCALE_MODES,
    GLEGraphConfig,
    GLEMarkerConfig,
    GLEStyleConfig,
    GlobalConfig,
)
from .markers import MARKERS
from .parser import metadata as _gle_metadata
from .parser.tables import LEGEND_SPACING_TO_KEY
from .parser.units import fontsize_pt_to_cm, inches_to_cm
from .series import (
    SERIES_ATTRS,
    HeatmapSeries,
    ScatterSeries,
    Series,
    TextAnnotation,
    is_visible,
)
from .sources import DataSource, source_of
from .writer import (
    BOX_SUB,
    CDATA_SUB_PREFIX,
    COLORBAR_AUTO_RANGE,
    COLORBAR_LABEL_PAD,
    COLORBAR_NTICKS,
    DEFAULT_COLORBAR_NTICKS,
    IMAGE_SUBS,
    MDATA_SUB_PREFIX,
    POLAR_SUB,
    WEDGE_SUB,
    AxisStyle,
    DecimationPolicy,
    GLEWriter,
    KeyOptions,
    SourceResolution,
    _grid_z_file,
    cdata_sub_name,
    cdata_sub_text,
    colorbar_format,
    image_sub_name,
    legend_column_breaks,
    mdata_sub_text,
    polar_ring_step,
    polar_window,
    resolve_figure,
)

#: A ``marker gleplot_mdata_<name>`` reference in raw GLE; group 1 is the name.
_MDATA_MARKER_RE = re.compile(
    r"\bmarker\s+" + re.escape(MDATA_SUB_PREFIX) + r"(\w+)", re.IGNORECASE
)

#: A ``marker gleplot_cdata_<marker>_<cmap>`` reference in raw GLE; groups 1
#: and 2 are the marker and the colormap.
_CDATA_MARKER_RE = re.compile(
    r"\bmarker\s+" + re.escape(CDATA_SUB_PREFIX) + r"([a-z0-9]+)_(\w+)",
    re.IGNORECASE,
)


def _coloured_markers(ax: Axes, resolution: SourceResolution) -> Set[Tuple[str, str]]:
    """The ``(marker, cmap)`` of each per-point colour sub ``ax`` draws with.

    A dataset line kept as raw GLE may name one too: the parser dropped its
    sub, so it is written again.
    """
    found = {
        (str(sc["marker"]).lower(), sc["cmap"])
        for sc in resolution.visible(ax.scatters)
        if "cdata" in sc
    }
    for line in ax.passthrough:
        for marker, cmap in _CDATA_MARKER_RE.findall(line):
            try:
                canonical = _pal.canonical_cmap(cmap)
            except ValueError:
                continue
            if marker.upper() in MARKERS and canonical == cmap.lower():
                found.add((marker.lower(), canonical))
    return found


def _colorbar_holders(ax: Axes, resolution: SourceResolution) -> List[Series]:
    """The series of ``ax`` that may carry a colorbar, in emission order."""
    return [*resolution.visible(ax.heatmaps), *resolution.visible(ax.scatters)]


def _axes_colorbar_holder(ax: Axes) -> Optional[Series]:
    """The series ``colorbar(ax=ax)`` shows: the axes' heatmap, else its
    colour-mapped scatter drawn last (matplotlib's current image)."""
    if ax.heatmaps:
        return ax.heatmaps[0]
    mapped = [sc for sc in ax.scatters if "cdata" in sc]
    return mapped[-1] if mapped else None


#: Envelope identifiers for the gleplot project-file format.
PROJECT_FORMAT = "gleplot-project"

#: Version written by :meth:`Figure.to_dict`.
#:
#: 1 -- every series carries its own baked arrays.
#: 2 -- series may carry a ``data_source`` (:mod:`gleplot.sources`). A series
#:      WITHOUT one is inline, exactly as in version 1, so a version-2 dict
#:      for a figure built through the scripting API is identical to the
#:      version-1 dict it would have produced except for this integer.
PROJECT_VERSION = 2

#: Versions :meth:`Figure.from_dict` accepts. Version 1 is read as "every
#: series is :class:`~gleplot.sources.InlineData`", which needs no conversion
#: at all -- the absence of ``data_source`` already means exactly that.
SUPPORTED_PROJECT_VERSIONS = (1, 2)


def _on_y2(series: Series) -> bool:
    """Whether ``series`` is drawn against y2.

    A stepfilled histogram is drawn on the primary axis whatever its
    ``yaxis`` says (:meth:`Axes.hist` warns).
    """
    return series.get("yaxis") == "y2" and series.get("histtype") != "stepfilled"


def _refline_axis_values(ax, orient: str):
    """Data coordinates the guides of ``ax`` contribute to autoscaling.

    ``orient`` is ``'v'`` (vertical guides -> x coordinates) or ``'h'``
    (horizontal guides -> y coordinates). Only the guide's *data* coordinate
    counts: the extent along the other axis is an axes fraction, so feeding it
    back into autoscale would be circular. A hidden guide (SPEC 14.6)
    contributes nothing: it is not drawn, so it does not hold the axis open.
    A non-finite coordinate contributes nothing either (see :func:`_plottable`).
    """
    values = []
    for entry in getattr(ax, "reflines", ()):
        if entry["orient"] == orient and is_visible(entry):
            values.append(float(entry["value"]))
    for entry in getattr(ax, "spans", ()):
        if entry["orient"] == orient and is_visible(entry):
            values.append(float(entry["start"]))
            values.append(float(entry["end"]))
    return [v for v in values if math.isfinite(v)]


def _plottable(values: np.ndarray, positive_only: bool) -> np.ndarray:
    """``values``, restricted to what the axis can actually show.

    Non-finite entries are dropped, as matplotlib's autoscale ignores them: a
    NaN or infinite bound is an axis range GLE refuses to compile. With
    ``positive_only`` (a log axis) the non-positive entries are dropped too,
    mirroring matplotlib, which masks them rather than refusing to autoscale.
    """
    values = values[np.isfinite(values)]
    if not positive_only:
        return values
    return values[values > 0]


def _bar_position_extent(bar_data, positive_only: bool):
    """``(lo, hi)`` of a bar series on its category axis, or ``None``.

    The widening matches the loop this replaced: only a collapsed range
    whose width GLE cannot derive is padded, and a log axis keeps the
    positive edge for ``_apply_log_limits`` to repair.
    """
    raw = np.asarray(bar_data["x"], dtype=float)
    positions = _plottable(raw, positive_only)
    if len(positions) == 0:
        return None
    lo, hi = float(positions.min()), float(positions.max())
    half_span = GLEWriter.bar_range_half_span(raw, bar_data.get("width"))
    if lo == hi and half_span is not None:
        lo, hi = lo - half_span, hi + half_span
        if positive_only and lo <= 0:
            lo = hi
    return lo, hi


def _bar_value_extent(bar_data, positive_only: bool):
    """``(lo, hi, from_zero)`` of a bar series on its value axis, or ``None``.

    ``from_zero`` is the historical rule: the lower end becomes
    ``min(0, lo)`` only when that lower end actually moves the limit. A
    baseline uses the bottoms and the tops and does not add zero.
    """
    height = np.asarray(bar_data["height"], dtype=float)
    bottom = bar_data.get("bottom")
    if bottom is None:
        values = _plottable(height, positive_only)
        if len(values) == 0:
            return None
        return float(values.min()), float(values.max()), True
    base = np.asarray(bottom, dtype=float)
    stored = bar_data.get("top")
    tops = np.asarray(stored, dtype=float) if stored is not None else base + height
    values = _plottable(np.concatenate([base, tops]), positive_only)
    if len(values) == 0:
        return None
    return float(values.min()), float(values.max()), False


def _apply_bar_value_extent(extent, lo_bound, hi_bound, positive_only: bool):
    """Fold one bar value-extent into ``(lo_bound, hi_bound)``."""
    if extent is None:
        return lo_bound, hi_bound
    data_lo, data_hi, from_zero = extent
    if from_zero and not positive_only:
        if lo_bound is None or data_lo < lo_bound:
            lo_bound = min(0.0, data_lo)
    elif lo_bound is None or data_lo < lo_bound:
        lo_bound = data_lo
    if hi_bound is None or data_hi > hi_bound:
        hi_bound = data_hi
    return lo_bound, hi_bound


def _saved_graph_config(saved: Dict[str, Any]) -> GLEGraphConfig:
    """The ``GLEGraphConfig`` a saved figure holds.

    A ``scale_mode`` saved before it was checked, which drew as 'auto', is
    read as 'auto' with a warning, and a saved 'fixed' does not warn again:
    the figure keeps loading as it was drawn.
    """
    kwargs = _filtered_dataclass_kwargs(GLEGraphConfig, saved)
    mode = kwargs.get("scale_mode", "auto")
    if not isinstance(mode, str) or mode not in _SCALE_MODES:
        warn_external(
            f"The saved scale_mode {mode!r} is not a scale mode; it is read as "
            "'auto', which is how it was drawn."
        )
        kwargs["scale_mode"] = "auto"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="scale_mode='fixed'")
        return GLEGraphConfig(**kwargs)


def _filtered_dataclass_kwargs(cls, data: dict) -> dict:
    """Filter ``data`` down to the keys ``cls`` (a dataclass) accepts.

    Used when reconstructing config dataclasses (:class:`GLEStyleConfig`,
    :class:`GLEGraphConfig`, :class:`GLEMarkerConfig`) from a project dict, so
    that unknown keys saved by a newer/older version of gleplot are ignored
    instead of raising ``TypeError`` -- consistent with the forward-compat
    guarantee documented on :meth:`Figure.from_dict`.
    """
    allowed = cls.__dataclass_fields__.keys()
    return {k: v for k, v in data.items() if k in allowed}


def _json_drawing(drawing: dict) -> dict:
    """A copy of a page drawing whose point lists are not shared."""
    return {k: list(v) if isinstance(v, list) else v for k, v in drawing.items()}


def _page_positive(name: str, value) -> float:
    number = _finite_float(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be greater than 0, got {value!r}")
    return number


def _page_points(x, y, count: int, exact: bool = False):
    """``x`` and ``y`` as equal-length lists of ``count`` (or more) finite floats."""
    try:
        xs = [_finite_float(v, "x") for v in x]
        ys = [_finite_float(v, "y") for v in y]
    except TypeError as err:
        raise TypeError(
            f"x and y must be sequences of numbers, got x={x!r}, y={y!r}"
        ) from err
    if len(xs) != len(ys):
        raise ValueError(
            f"x and y must have the same length, got {len(xs)} and {len(ys)}"
        )
    if len(xs) != count if exact else len(xs) < count:
        need = "exactly" if exact else "at least"
        raise ValueError(f"x and y must hold {need} {count} points, got {len(xs)}")
    return xs, ys


def _page_slope(name: str, value) -> List[float]:
    try:
        slope = [_finite_float(v, name) for v in value]
    except TypeError as err:
        raise TypeError(f"{name} must be a (dx, dy) pair, got {value!r}") from err
    if len(slope) != 2:
        raise ValueError(f"{name} must be a (dx, dy) pair, got {value!r}")
    return slope


def _is_none_color(color) -> bool:
    return isinstance(color, str) and color.strip().lower() == "none"


def _page_text(kind: str, s) -> str:
    """Text for a ``begin tex``/``begin table`` block, one GLE line per line."""
    if not isinstance(s, str):
        raise TypeError(f"s must be a str, got {s!r}")
    if not s.strip():
        raise ValueError("s must contain some text, got an empty string")
    lines = s.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line in lines:
        words = line.split()
        # GLE reads a line starting with 'begin' or 'end' as block structure,
        # which would end the block early or leave it open.
        if words and words[0].lower() in ("begin", "end"):
            raise ValueError(
                f"s cannot have a line that starts with {words[0]!r}: GLE would "
                f"read it as the start or end of a block. Got line {line!r}."
            )
    # GLE puts the brace that closes its LaTeX box on the last line.
    if kind == "tex" and re.search(r"(?<!\\)%", lines[-1]):
        raise ValueError(
            "the last line of s cannot hold a LaTeX % comment: GLE closes its "
            "box on that line, so the comment would hide the closing brace. "
            f"Write \\% for a percent sign. Got line {lines[-1]!r}."
        )
    return "\n".join(lines)


_SHARE_MODES: Dict[str, Union[bool, str]] = {
    "all": True,
    "none": False,
    "row": "row",
    "col": "col",
}


def _share_mode(name: str, value: Any) -> Union[bool, str]:
    """A ``sharex``/``sharey`` value as stored: ``True``, ``False``, 'row' or 'col'.

    matplotlib's 'all' and 'none' are stored as the bools they mean.
    """
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value in _SHARE_MODES:
        return _SHARE_MODES[value]
    raise ValueError(
        f"{name}={value!r}: expected True, False, 'all', 'none', 'row' or 'col'."
    )


def _grid_cells(ax: Axes) -> Tuple[int, int, Tuple[int, int], Tuple[int, int]]:
    """``(rows, cols, (first_row, last_row), (first_col, last_col))`` of an axes.

    Rows and columns count from 0 at the top left and the ranges are
    inclusive. An ``index`` that is a ``(first, last)`` pair spans the
    rectangle of cells between those two, as matplotlib's does.

    Only for an axes in the grid: an :meth:`Figure.add_axes` inset has no
    position (see :meth:`Figure._grid_axes`).
    """
    position = ax.position
    assert position is not None, "an add_axes inset has no grid cells"
    rows, cols, idx = position
    first, last = idx if isinstance(idx, tuple) else (idx, idx)
    rows_ = sorted(((first - 1) // cols, (last - 1) // cols))
    cols_ = sorted(((first - 1) % cols, (last - 1) % cols))
    return rows, cols, (rows_[0], rows_[1]), (cols_[0], cols_[1])


def _aspect_rect(ax: Axes, rect: tuple) -> tuple:
    """``rect`` shrunk about its centre to the ratio ``ax._aspect`` asks for.

    Read after the limits are resolved. A y unit is ``aspect`` times an x
    unit, and a unit on a log axis is a decade, as in matplotlib. Unchanged
    for an 'auto' aspect, or (with a warning) for limits that do not give a
    ratio.
    """
    if ax._aspect is None:
        return rect
    if ax.geometry_passthrough:
        _warn_aspect_without_rect(ax, _RAW_GEOMETRY)
        return rect
    spans: List[float] = []
    for lo, hi, scale in (
        (ax.xmin, ax.xmax, ax.xscale),
        (ax.ymin, ax.ymax, ax.yscale),
    ):
        span = math.nan
        if lo is not None and hi is not None:
            if scale != "log":
                span = abs(hi - lo)
            elif lo > 0 and hi > 0:
                span = abs(math.log10(hi) - math.log10(lo))
        spans.append(span)
    x_span, y_span = spans
    if not all(math.isfinite(v) and v > 0 for v in spans):
        warn_external(
            "set_aspect() was skipped: the axes has no x and y range to "
            "measure units by. Plot data or set the limits with set_xlim "
            "and set_ylim."
        )
        return rect
    x, y, w, h = rect
    ratio = ax._aspect * y_span / x_span  # frame height over width
    if h > w * ratio:
        new_w, new_h = w, w * ratio
    else:
        new_w, new_h = h / ratio, h
    return (x + (w - new_w) / 2, y + (h - new_h) / 2, new_w, new_h)


#: Why set_aspect cannot apply, and what to do (_warn_aspect_without_rect).
_RAW_GEOMETRY = (
    "its size is GLE that gleplot keeps as written. Clear "
    "ax.geometry_passthrough to let gleplot size the frame"
)
_FULLSIZE = (
    "GLEGraphConfig(scale_mode='fullsize') lets GLE size it. Use the default "
    "scale_mode to let gleplot size the frame"
)


def _warn_aspect_without_rect(ax: Axes, reason: str) -> None:
    """Warn that ``ax``'s aspect is not applied, because ``reason``."""
    if ax._aspect is not None:
        warn_external(f"set_aspect() has no effect on this axes: {reason}.")


def _make_polar(ax: Axes) -> None:
    """Turn a new axes into a polar one."""
    # The polar grid and its labels replace the frame and ticks.
    ax._polar = True
    ax._frame_off = True
    ax._show_xticks = ax._show_yticks = False
    ax.xgrid = ax.ygrid = None


def _axes_options(
    caller: str, projection: Any, polar: Any, kwargs: Dict[str, Any]
) -> Tuple[Any, Any]:
    """``(projection, facecolor)`` from an ``add_subplot``/``add_axes`` call.

    ``polar=True`` is ``projection='polar'``; ``facecolor`` (alias ``fc``)
    is the one axes property honoured, and the others warn.
    """
    if polar:
        if projection not in (None, "polar"):
            raise ValueError(
                f"{caller}(polar=True, projection={projection!r}): pass "
                "only one of them."
            )
        projection = "polar"
    if projection not in (None, "rectilinear", "polar"):
        raise ValueError(
            f"{caller}(projection={projection!r}) is not supported; "
            "use None, 'rectilinear' or 'polar'."
        )
    if "facecolor" in kwargs and "fc" in kwargs:
        raise TypeError(f"{caller}() got both facecolor and fc; pass one.")
    facecolor = kwargs.pop("facecolor", kwargs.pop("fc", None))
    warn_unsupported_keywords(caller, kwargs, "Set them on the returned axes instead.")
    return projection, facecolor


def _subplot_span(rows: int, cols: int, idx) -> Union[int, Tuple[int, int]]:
    """Check an ``add_subplot`` ``(first, last)`` index, as matplotlib does.

    A span of one cell comes back as that cell's plain index, the form
    ``open_gle`` recovers it in.
    """
    n = rows * cols
    if (
        not isinstance(idx, tuple)
        or len(idx) != 2
        or not all(
            isinstance(i, (int, np.integer)) and not isinstance(i, bool) for i in idx
        )
    ):
        raise ValueError(
            "add_subplot() takes a spanning index as a (first, last) tuple of "
            f"two integers, got {idx!r}."
        )
    first, last = int(idx[0]), int(idx[1])
    if not (1 <= first <= last <= n):
        raise ValueError(
            f"add_subplot({rows}, {cols}, {idx!r}): the span must run from a "
            f"subplot number to the same or a later one, between 1 and {n}."
        )
    return first if first == last else (first, last)


@dataclass(frozen=True)
class _LegendLayout:
    """One axes' key, worked out before its series are written.

    ``entries`` are ``(series, label, swatch)`` in emission order and
    ``addition`` their indices in matplotlib addition order. ``external``
    means the in-graph key is off and a ``begin key`` block lists the
    entries in addition order instead; it is only ever set with ``show``.
    """

    entries: List[tuple]
    show: bool
    addition: List[int]
    external: bool
    ncol: int


#: The ``Axes`` tick-mark fields (``xtick_length``, ...) without the axis
#: prefix; also the :class:`AxisStyle` field names they are written from.
_TICK_MARK_FIELDS = (
    "tick_length",
    "tick_width",
    "tick_color",
    "tick_direction",
    "subtick_length",
    "subtick_width",
    "subtick_color",
    "subtick_direction",
    "minorticks",
)


def _cbar_format(cb: dict) -> Optional[str]:
    """The tick format a colorbar is written with, when it can be known.

    Its own, or the default :func:`gleplot.writer.colorbar_format` gives
    once its range is set (an auto-range bar's is set at write time).
    """
    if cb.get("format"):
        return cb["format"]
    if cb.get("zmin") is None or not cb.get("zstep"):
        return None
    return colorbar_format(float(cb["zmin"]), float(cb["zstep"]))


class Figure:
    """Matplotlib-like figure for GLE plotting.

    Parameters
    ----------
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (8, 6)
    dpi : int, optional
        Dots per inch. Default: 100
    style : GLEStyleConfig, optional
        Style configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.style` is taken at construction
        time -- see the "Global defaults are copied, not shared" note below.
        An explicitly passed ``style`` is stored by reference, as before.
    graph : GLEGraphConfig, optional
        Graph configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.graph` is taken at construction
        time (same note). An explicitly passed ``graph`` is stored by
        reference, as before.
    marker : GLEMarkerConfig, optional
        Marker configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.marker` is taken at construction
        time (same note). An explicitly passed ``marker`` is stored by
        reference, as before.

    Notes
    -----
    **Global defaults are copied, not shared.** ``GlobalConfig.style``/
    ``.graph``/``.marker`` are process-wide singletons. Setting
    ``GlobalConfig.style.font = 'texcmss'`` *before* creating a figure
    still changes that figure's default font, exactly as documented in
    :class:`gleplot.config.GlobalConfig`. But once a ``Figure`` exists, its
    ``style``/``graph``/``marker_config`` are independent objects (when no
    explicit config was passed in): editing ``fig.style.font`` in place (or
    reassigning ``fig.style``) affects only ``fig`` -- it can neither leak
    into other figures created earlier or later in the same process, nor
    mutate ``GlobalConfig`` itself. This is copy-AT-CONSTRUCTION semantics,
    the same rule matplotlib's ``rcParams`` snapshot follows for a new
    ``Figure``/``Axes``.

    This only applies to the *default*, taken from ``GlobalConfig``. A
    ``style``/``graph``/``marker`` object YOU pass in explicitly is still
    stored by reference, unchanged from before this note was added: two
    figures built with the same explicit config object still share it, and
    the object stays live for code that wants to mutate it after
    construction (:mod:`gleplot.parser.recognizer` does exactly this while
    reconstructing a ``Figure`` from parsed GLE text).
    """

    def __init__(
        self,
        figsize: Tuple[float, float] = (8, 6),
        dpi: int = 100,
        style: Optional[GLEStyleConfig] = None,
        graph: Optional[GLEGraphConfig] = None,
        marker: Optional[GLEMarkerConfig] = None,
        sharex: Union[bool, str] = False,
        sharey: Union[bool, str] = False,
        data_prefix: Optional[str] = None,
        height_ratios: Optional[Sequence[float]] = None,
        width_ratios: Optional[Sequence[float]] = None,
    ):
        """Initialize figure with optional configuration objects.

        Parameters
        ----------
        data_prefix : str, optional
            Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
            If None, uses global counter with ``data_`` prefix.

            Used verbatim -- it is never sanitized, so the sidecar names stay
            predictable (``'experimentA'`` yields ``experimentA_0.dat``, not
            ``experimenta_0.dat``). In exchange it is validated: a prefix
            containing whitespace, a control character, or any of
            ``! " + / \\`` raises ``ValueError`` here rather than producing a
            script GLE fails to parse. See
            :func:`gleplot.axes._validate_data_prefix`.

        Raises
        ------
        ValueError
            If ``data_prefix`` is empty/whitespace-only or contains a
            character that is not usable in a GLE data filename.
        height_ratios : sequence of float, optional
            Relative height of each subplot ROW, matplotlib-``gridspec``
            style, e.g. ``[3, 3, 3, 1, 4]`` for a 5-row grid whose 4th row is
            thin. ``None`` (default) keeps every row the same height -- the
            historical behaviour, byte-identical output. Applies only to the
            multi-subplot grid layout (``add_subplot``/:func:`gleplot.subplots`
            with more than one axes); ignored for a single (1,1,1) axes.
            Checked against the actual number of subplot rows at GLE-
            generation time (:meth:`Figure.savefig`/:meth:`savefig_gle`),
            since the grid shape is not always known yet when the figure is
            constructed -- a length mismatch raises :class:`ValueError` then,
            naming both the given length and the row count found.
        width_ratios : sequence of float, optional
            Relative width of each subplot COLUMN. Same semantics, defaults
            and validation timing as ``height_ratios``, but for columns.
        """
        self.figsize = figsize
        self.dpi = dpi

        # GLE's page-level 'size w h box' modifier: draws a border around
        # the whole page. Confirmed empirically against GLE 4.3.10 (the
        # manual documents no modifier at all for the page-level 'size'):
        # unlike a GRAPH's own 'size'/'scale', which accepts a whole family
        # of trailing modifiers (box/nobox/border/noborder/center/fullsize/
        # math -- GLE/src/gle/graph.cpp's do_remaining_entries), the
        # page-level form accepts ONLY the literal word 'box' and nothing
        # else; 'size 8 6 nobox' (or any other modifier) is a hard GLE
        # parse error ("found 'nobox', but expecting 'BOX'"), so there is no
        # page-level way to SPELL "no border" beyond omitting the word.
        # False (the default, i.e. no border, matching 'box' simply being
        # absent) reproduces every existing figure's output byte for byte.
        self.page_box: bool = False

        # Store configuration for passing to writer.
        #
        # When no explicit config is given, take a COPY of the global
        # default rather than the ``GlobalConfig`` singleton itself.
        # ``GLEStyleConfig``/``GLEGraphConfig``/``GLEMarkerConfig`` are all
        # flat dataclasses (str/float/int/bool/Optional[float] fields only,
        # no mutable members), so a shallow ``dataclasses.replace(...)`` --
        # equivalent to ``copy.copy`` here -- is a full, independent copy.
        # Without this, ``fig.style.font = ...`` on a figure that never
        # passed ``style=`` mutates the *same* object every other
        # default-styled ``Figure()`` in the process holds, because
        # ``GlobalConfig.get_style()`` returns one shared instance. This is
        # copy-AT-CONSTRUCTION semantics: changing ``GlobalConfig.style``
        # (etc.) before creating a figure still changes that figure's
        # defaults, same as before; only the *identity* is no longer
        # shared, so later in-place edits on one figure's config cannot
        # leak into another figure's, or into the global default itself.
        #
        # An EXPLICIT config object, by contrast, is still stored BY
        # REFERENCE, not copied: that is a narrower, pre-existing contract
        # the parser recognizer depends on. ``parser/recognizer.py`` builds
        # a ``GLEGraphConfig`` up front, hands it to ``Figure(graph=...)``,
        # then mutates ``smooth_curves`` on that same object afterwards
        # (see ``_apply_smooth``) once it has walked the parsed series and
        # knows whether they carried ``smooth`` -- it relies on
        # ``fig.graph is graph_cfg``. Only the ``GlobalConfig`` singleton is
        # a cross-figure hazard; an object the caller constructed and holds
        # no other reference to is not.
        self.style = style if style is not None else replace(GlobalConfig.get_style())
        if graph is None:
            # A 'fixed' global warned when it was set; copying it is quiet.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="scale_mode='fixed'")
                graph = replace(GlobalConfig.get_graph())
        self.graph = graph
        self.marker_config = (
            marker if marker is not None else replace(GlobalConfig.get_marker())
        )

        # Shared axes: True (every panel), 'row', 'col' or False.
        self.sharex = sharex
        self.sharey = sharey

        # Custom data file naming. Validated (not sanitized) so a prefix GLE
        # cannot parse fails here, at the point the bad value was supplied,
        # instead of at compile time inside a generated 'data <file>' line.
        self.data_prefix = (
            _validate_data_prefix(data_prefix) if data_prefix is not None else None
        )
        self._local_data_counter = 0  # Local counter when using custom prefix
        self._used_data_files: set[str] = set()
        # Per-kind (heatmap/contour/points) contour+fitz sidecar counters --
        # only ever populated when this figure has a custom data_prefix (see
        # axes._reserve_sidecar); a default-prefix figure shares the
        # module-level axes._global_sidecar_counters instead (G8).
        self._sidecar_counters: dict[str, int] = {}
        self._subplot_adjust: dict[str, float] = {}

        # Per-row/per-column relative sizes for the multi-subplot grid
        # (matplotlib-style height_ratios/width_ratios). None (the default)
        # means equal sizes -- see _grid_axis_sizes for how this combines
        # with subplots_adjust's wspace/hspace.
        self.height_ratios = (
            [float(r) for r in height_ratios] if height_ratios is not None else None
        )
        self.width_ratios = (
            [float(r) for r in width_ratios] if width_ratios is not None else None
        )

        self.axes_list: List[Axes] = []  # List of Axes objects
        self._current_axes: Optional[Axes] = None  # Current working axes
        # BrokenAxes assemblies. Their segments are ordinary Axes and live in
        # axes_list like any other subplot (so limits, series and emission all
        # work unchanged); this list only records the grouping, the seam
        # decoration and the shared titles.
        self.broken_axes: list = []

        # Raw GLE lines recovered from a parsed .gle file that the recognizer
        # could not map onto the object model, split into buckets by where
        # they sit relative to the graph block(s):
        #   passthrough_before_hei: preamble lines that sat, in the original,
        #     between a recognized 'size'/'set font' and a recognized
        #     'set hei' -- almost always empty. Non-empty only when the
        #     original had something like 'scale .6 .8' between them: 'hei'
        #     is in GLE's CURRENT user units, so a preceding 'scale'/similar
        #     CTM statement changes what the writer's own 'set hei' line
        #     actually renders as. Re-emitted right after 'set font'
        #     (if any) but BEFORE the writer's 'set hei' -- the one case
        #     where the writer cannot simply put its own preamble first (see
        #     GLEWriter.add_preamble).
        #   passthrough_header: emitted right after the standard preamble
        #     (after 'set hei ...' + blank line), before the first graph
        #     block/amove.
        #   passthrough_trailer: emitted at the very end of the script, after
        #     all graph blocks and deferred text annotations.
        # One entry per source line, no trailing newline. Default: empty.
        self.passthrough_before_hei: list = []
        self.passthrough_header: list = []
        self.passthrough_trailer: list = []

        # Shapes and text blocks drawn on the page in cm (Figure.circle ...
        # Figure.tex), one dict per call with its "kind", in call order.
        # Written after every graph block, before passthrough_trailer.
        self._drawings: List[dict] = []

        # Figure-level text in figure fractions and the figure legend
        # (Figure.suptitle, Figure.text, Figure.legend). Written after the
        # page drawings: the suptitle, the texts in call order, then the
        # legend, which lists the labelled series of every axes.
        self._suptitle: Optional[TextAnnotation] = None
        #: The figure texts (:meth:`text`), in call order. Their ``x`` and
        #: ``y`` are figure fractions.
        self.texts: List[TextAnnotation] = []
        self._legend: Optional[dict] = None

        # Unknown keys recovered from a parsed '! gleplot:' metadata block,
        # re-emitted verbatim in the metadata block on regeneration. Default:
        # empty (no extra keys).
        self.metadata_extra: dict = {}

        # Structured records for series skipped by the LAST write because
        # their data source was dangling (§3.2). Write-time output, not
        # document state: reset by every generation, never serialized.
        self._source_warnings: List = []

        # Structured records for series the LAST write appended a preview
        # ``deresolve`` clause to (§6.1/§10.7, G7). Write-time output, not
        # document state: reset (to ``[]``, since ``preview_decimation`` is a
        # per-call opt-in) by every generation, never serialized -- see
        # :attr:`preview_decimation_report`.
        self._preview_decimation_report: List = []

        self.compiler = None
        try:
            self.compiler = GLECompiler()
        except RuntimeError:
            pass  # GLE not available, but can still write scripts

    @property
    def source_warnings(self) -> List:
        """Series skipped by the most recent GLE generation, and why.

        A list of :class:`gleplot.sources.DanglingSourceRef` -- inspectable
        objects naming the series (axes index, series list, index, label) and
        the reference that could not be resolved (table id, column keys,
        reason). Empty for any figure whose series are all inline, which is
        every figure the scripting API builds.

        Reset at the start of each generation, so it always describes the
        latest ``savefig``/``savefig_gle`` rather than accumulating.
        """
        return list(self._source_warnings)

    @property
    def axes(self) -> List[Axes]:
        """The figure's axes, in the order they were added.

        A new list on each access, as in matplotlib: add axes with
        :meth:`add_subplot` or :meth:`add_axes`, not by changing the list.
        For a figure from :func:`gleplot.open_gle`, the order is that of the
        graph blocks in the file. Each segment of a broken axis
        (:meth:`add_broken_xaxes`, :meth:`add_broken_yaxes`) is an entry.

        Notes
        -----
        Unlike matplotlib, the secondary axes that :meth:`gleplot.Axes.twinx`
        and :meth:`gleplot.Axes.twiny` return are not entries: they draw on
        their parent axes' graph.
        """
        return list(self.axes_list)

    @property
    def preview_decimation_report(self) -> List:
        """Series the most recent generation actually decimated, and by how much.

        A list of :class:`gleplot.writer.DecimationRecord` (dataset name,
        label, factor, original point count) -- empty unless that generation
        call passed ``preview_decimation=N`` (``N`` > 1) AND at least one
        eligible series (line/scatter -- see
        :meth:`gleplot.writer.GLEWriter._deresolve_clause` for the full kind/
        threshold rule) met :attr:`gleplot.writer.GLEWriter.MIN_DERESOLVE_POINTS`.
        Always ``[]`` for a generation that did not pass the argument at all,
        matching the DEFAULT emission being byte-identical to a build before
        G7 existed.

        Reset at the start of each generation (mirrors :attr:`source_warnings`),
        so it always describes the latest ``savefig``/``savefig_gle`` rather
        than accumulating.
        """
        return list(self._preview_decimation_report)

    def subplots_adjust(
        self,
        *,
        left: Optional[float] = None,
        right: Optional[float] = None,
        bottom: Optional[float] = None,
        top: Optional[float] = None,
        wspace: Optional[float] = None,
        hspace: Optional[float] = None,
    ) -> None:
        """Store subplot layout overrides (matplotlib-compatible API).

        Parameters are normalized figure fractions except `wspace`/`hspace`,
        which follow matplotlib semantics (fraction of average subplot width/height).
        """
        candidate = dict(self._subplot_adjust)
        updates = {
            "left": left,
            "right": right,
            "bottom": bottom,
            "top": top,
            "wspace": wspace,
            "hspace": hspace,
        }
        for key, value in updates.items():
            if value is None:
                continue
            val = float(value)
            if key in {"left", "right", "bottom", "top"}:
                if not (0.0 <= val <= 1.0):
                    raise ValueError(f"{key} must be within [0, 1], got {val}")
            else:
                if val < 0.0:
                    raise ValueError(f"{key} must be >= 0, got {val}")
            candidate[key] = val

        left_val = candidate.get("left")
        right_val = candidate.get("right")
        if left_val is not None and right_val is not None and left_val >= right_val:
            raise ValueError("left must be less than right")

        bottom_val = candidate.get("bottom")
        top_val = candidate.get("top")
        if bottom_val is not None and top_val is not None and bottom_val >= top_val:
            raise ValueError("bottom must be less than top")

        self._subplot_adjust = candidate

    def add_subplot(
        self, *args, projection: Optional[str] = None, polar: bool = False, **kwargs
    ) -> Axes:
        """
        Add subplot to figure.

        Parameters
        ----------
        *args : int or (int, int)
            Subplot specification (rows, cols, index) or single int
            E.g., add_subplot(2, 2, 1) or add_subplot(221). Omitted, the
            figure's only subplot, ``(1, 1, 1)``. An index that is a
            ``(first, last)`` tuple spans every cell of the rectangle between
            those two, as in matplotlib: ``add_subplot(2, 2, (1, 2))`` takes
            the whole top row. Any other index, or one outside
            ``1..rows*cols``, raises ``ValueError``, as in matplotlib.
        projection : {None, 'rectilinear', 'polar'}, optional
            ``'polar'`` makes a polar axes: :meth:`Axes.plot` and
            :meth:`Axes.scatter` take ``(theta, r)`` with theta in radians,
            and :meth:`Axes.function` reads ``x`` in its expression as
            theta. ``set_ylim(0, rmax)`` sets the radial limit.
        polar : bool, default: False
            ``True`` is ``projection='polar'``.
        **kwargs
            Axes properties, as for :meth:`add_axes`: ``facecolor`` (alias
            ``fc``) is honoured, and the others warn and are ignored.

        Returns
        -------
        Axes
            New axes object

        Notes
        -----
        A polar axes draws a grid of rings and spokes with the angles and
        radii labelled, in place of the frame and ticks. It supports the
        three methods above, the legend, the title and the radial limit;
        other plotting methods and cartesian settings such as
        :meth:`Axes.set_xlim` raise ``NotImplementedError``.
        """
        projection, facecolor = _axes_options("add_subplot", projection, polar, kwargs)
        if not args:
            args = (1, 1, 1)
        if len(args) == 1 and isinstance(args[0], (int, np.integer)):
            # Parse single int format (e.g., 221)
            spec = str(int(args[0]))
            if len(spec) == 3:
                rows, cols, idx = int(spec[0]), int(spec[1]), int(spec[2])
            else:
                raise ValueError(f"Invalid subplot spec: {args[0]}")
        elif len(args) == 3:
            rows, cols, idx = args
        else:
            raise ValueError(
                f"add_subplot{args!r}: expected (rows, cols, index) or a "
                "three-digit integer such as 221."
            )
        for name, value in (("rows", rows), ("cols", cols)):
            if not isinstance(value, (int, np.integer)) or value < 1:
                raise ValueError(
                    f"add_subplot({rows!r}, {cols!r}, {idx!r}): {name} must be a "
                    f"positive integer, not {value!r}."
                )
        rows, cols = int(rows), int(cols)
        if isinstance(idx, (tuple, list)):
            idx = _subplot_span(rows, cols, idx)
        elif isinstance(idx, (int, np.integer)) and 1 <= idx <= rows * cols:
            idx = int(idx)
        else:
            raise ValueError(
                f"add_subplot({rows}, {cols}, {idx!r}): the subplot index must be "
                f"an integer from 1 to {rows * cols}, or a (first, last) tuple."
            )

        ax = Axes(self, (rows, cols, idx))

        # Derive shared-axes tick/label visibility flags from this figure's
        # current sharex/sharey settings. Kept as a separate method so callers
        # can re-apply the identical derivation after grid resize or sharing
        # toggles instead of duplicating the logic.
        self._apply_shared_axes_flags(ax)
        if projection == "polar":
            _make_polar(ax)
        if facecolor is not None:
            ax.set_facecolor(facecolor)

        self.axes_list.append(ax)
        self._current_axes = ax
        return ax

    def add_axes(self, rect, projection=None, polar=False, **kwargs) -> Axes:
        """Add an axes at a given place on the page, such as an inset.

        Parameters
        ----------
        rect : sequence of 4 floats
            ``[left, bottom, width, height]`` of the axes frame, in fractions
            of the figure: ``[0, 0, 1, 1]`` is the whole page.
        projection : {None, 'rectilinear', 'polar'}, optional
            As for :meth:`add_subplot`.
        polar : bool, default: False
            ``True`` is ``projection='polar'``.
        **kwargs
            Axes properties in matplotlib. ``facecolor`` (alias ``fc``) is
            passed to
            :meth:`Axes.set_facecolor`; the others are not supported: they
            warn and are ignored, so call the setters on the returned axes
            instead.

        Returns
        -------
        Axes
            The new axes, also the figure's current axes.

        Notes
        -----
        The axes stands outside the subplot grid: it does not move the grid,
        and ``sharex``/``sharey`` do not apply to it. It is written after the
        axes added before it, so it is drawn on top of them, but unlike
        matplotlib it has no background unless given a ``facecolor``, so
        what is behind it shows through.

        The rect is turned into centimetres from the figure's ``figsize``
        when this is called, and is kept as :attr:`Axes.placement`.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, ax = glp.subplots()
        >>> inset = fig.add_axes([0.55, 0.55, 0.3, 0.3])
        """
        try:
            if isinstance(rect, (Axes, str, dict)):
                raise TypeError
            values = [float(v) for v in rect]
            if len(values) != 4:
                raise TypeError
        except (TypeError, ValueError):
            raise TypeError(
                "add_axes(rect) takes [left, bottom, width, height] as four "
                f"numbers in figure fractions, got {rect!r}; adding an "
                "existing axes is not supported."
            ) from None
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"add_axes(rect) must be finite, got {rect!r}.")
        if values[2] <= 0 or values[3] <= 0:
            raise ValueError(
                f"add_axes(rect) needs a positive width and height, got {rect!r}."
            )
        projection, facecolor = _axes_options("add_axes", projection, polar, kwargs)

        width_cm, height_cm = (inches_to_cm(v) for v in self.figsize)
        ax = Axes(self, None)
        left, bottom, width, height = values
        ax.placement = (
            left * width_cm,
            bottom * height_cm,
            width * width_cm,
            height * height_cm,
        )
        if projection == "polar":
            _make_polar(ax)
        if facecolor is not None:
            ax.set_facecolor(facecolor)

        self.axes_list.append(ax)
        self._current_axes = ax
        return ax

    def add_broken_xaxes(self, xlims, **kwargs) -> BrokenAxes:
        """Add a panel whose x-axis is broken into adjacent segments.

        The segments share one y-axis: tick labels and the y title appear only
        on the leftmost one, the sides that face each other are switched off,
        and the seam is marked with a rule or double-slash break marks. Series
        are declared once on the returned object and fanned out to every
        segment, sharing a single data sidecar; GLE clips each dataset to its
        own segment's range.

        Parameters
        ----------
        xlims : sequence of (float, float)
            One ``(xmin, xmax)`` per segment, left to right; at least two.
        **kwargs
            Passed to :class:`gleplot.brokenaxes.BrokenAxes` --
            ``width_ratios``, ``position``, ``gap``, ``divider``,
            ``divider_color``, ``divider_linewidth``, ``divider_lstyle``,
            ``break_mark_size``, ``trim_seam_labels``, ``xlabel_dist``,
            ``title_dist``.

        Returns
        -------
        BrokenAxes

        Notes
        -----
        Plot through the returned object, not through the figure: this sets
        the figure's current axes to the *leftmost segment*, so a subsequent
        ``fig.plot(...)`` / :meth:`gca` would reach only that one segment.

        Examples
        --------
        >>> fig = glp.figure(figsize=(3.4, 2.6))
        >>> bax = fig.add_broken_xaxes([(0, 0.02), (0.02, 3)],
        ...                            width_ratios=[1, 3], divider='slash')
        >>> bax.errorbar(t, a, yerr=e, marker='o', linestyle='none')
        >>> bax.set_xlabel('t (us)')
        >>> bax.set_ylabel('Asymmetry (%)')
        """
        return self._add_broken(BrokenAxes(self, xlims, **kwargs))

    def add_broken_yaxes(self, ylims, **kwargs) -> BrokenAxes:
        """Add a panel whose y-axis is broken into stacked segments.

        The broken-y counterpart of :meth:`add_broken_xaxes`. The segments
        share one x-axis: its tick labels and title appear only on the bottom
        segment, the sides that face each other are switched off, and the
        seam is marked with a rule or double-slash break marks on the left
        and right frame lines. The y title and the title are written once,
        centred on the whole assembly.

        Parameters
        ----------
        ylims : sequence of (float, float)
            One ``(ymin, ymax)`` per segment, bottom to top; at least two.
        **kwargs
            Passed to :class:`gleplot.brokenaxes.BrokenAxes` --
            ``height_ratios``, ``position``, ``gap``, ``divider``,
            ``divider_color``, ``divider_linewidth``, ``divider_lstyle``,
            ``break_mark_size``, ``trim_seam_labels``, ``ylabel_dist``,
            ``title_dist``.

        Returns
        -------
        BrokenAxes

        Notes
        -----
        Plot through the returned object, not through the figure: this sets
        the figure's current axes to the *bottom segment*.

        The y title's default distance from the frame, 2.5 times the font
        height, clears tick labels up to about four characters wide. GLE
        does not report the width of the labels it draws, so for wider ones
        pass ``ylabel_dist`` (cm).

        Examples
        --------
        >>> fig = glp.figure()
        >>> bax = fig.add_broken_yaxes([(0, 1), (10, 12)], divider='slash')
        >>> bax.bar([1, 2, 3], [0.4, 0.8, 11.0])
        >>> bax.set_ylabel('counts')
        """
        return self._add_broken(BrokenAxes(self, ylims=ylims, **kwargs))

    def _add_broken(self, bax: BrokenAxes) -> BrokenAxes:
        """Put a broken-axis assembly's segments into the figure."""
        for seg in bax.segments:
            # Derive the grid-level sharing flags first, then let the
            # broken-axis rules (already applied by the constructor) stand
            # where they disagree: the assembly's internal geometry is not
            # negotiable, whereas sharex/sharey describe the grid around it.
            bax._reassert_frame_flags(seg, self._apply_shared_axes_flags)
            self.axes_list.append(seg)

        self.broken_axes.append(bax)
        self._current_axes = bax.segments[0]
        return bax

    @property
    def sharex(self) -> Union[bool, str]:
        """``True``, ``False``, 'row' or 'col'; set it as for :func:`subplots`."""
        return self._sharex

    @sharex.setter
    def sharex(self, value: Any) -> None:
        self._sharex = _share_mode("sharex", value)

    @property
    def sharey(self) -> Union[bool, str]:
        """``True``, ``False``, 'row' or 'col'; set it as for :func:`subplots`."""
        return self._sharey

    @sharey.setter
    def sharey(self, value: Any) -> None:
        self._sharey = _share_mode("sharey", value)

    def _hides_inner_labels(self, axis: str) -> bool:
        """Whether sharing ``axis`` hides the inner panels' tick labels.

        As matplotlib: x for ``True`` and 'col', y for ``True`` and 'row'.
        """
        mode, own = (self.sharex, "col") if axis == "x" else (self.sharey, "row")
        return mode is True or mode == own

    def _apply_shared_axes_flags(self, ax: Axes) -> None:
        """Set ``ax``'s shared-axes tick/label visibility flags.

        Reads ``ax.position`` (a ``(rows, cols, idx)`` tuple) together with this
        figure's ``sharex``/``sharey`` flags (as matplotlib, ``'col'`` hides
        inner x labels like ``True`` and ``'row'`` does not; ``sharey`` the
        other way round) and writes the ``_show_xlabel`` /
        ``_show_xticks`` / ``_remove_*`` visibility flags on ``ax`` accordingly.

        This is the single source of truth for that derivation: ``add_subplot``
        calls it for every new axes, and callers that mutate an axes' position
        or the figure's sharing after axes already exist call it to re-sync the
        flags to what a fresh ``add_subplot``
        would have produced. Changing the rules here changes them everywhere.
        """
        # A spanning axes is judged by its bottom row and its outer columns.
        # An inset shares nothing, which is what a lone 1x1 cell gets.
        rows, cols, (top_row, bottom_row), (left_col, right_col) = (
            _grid_cells(ax) if ax.position is not None else (1, 1, (0, 0), (0, 0))
        )

        # A panel spanning columns (rows) has a 'col' ('row') range of its
        # own, so it keeps its labels.
        hide_x = self._hides_inner_labels("x") and (
            self.sharex is True or left_col == right_col
        )
        hide_y = self._hides_inner_labels("y") and (
            self.sharey is True or top_row == bottom_row
        )
        if hide_x:
            # Only show x-axis labels/ticks on bottom row
            ax._show_xlabel = bottom_row == rows - 1
            ax._show_xticks = bottom_row == rows - 1
            # Remove last x-tick label if not the bottom row (to prevent overlap when subplots touch)
            ax._remove_last_xtick = bottom_row < rows - 1
            ax._remove_first_xtick = False
            # When sharing x, y-axes touch vertically - remove last (top) y-label from all but top row
            # (highest y-label of lower plots could overlap upward into the plot above)
            ax._remove_last_ytick = top_row > 0
            ax._remove_first_ytick = False
        else:
            ax._show_xlabel = True
            ax._show_xticks = True
            ax._remove_last_xtick = False
            ax._remove_first_xtick = False
            ax._remove_last_ytick = False
            ax._remove_first_ytick = False

        if hide_y:
            # Only show y-axis labels/ticks on leftmost column
            ax._show_ylabel = left_col == 0
            ax._show_yticks = left_col == 0
            # When sharing y, x-axes touch horizontally - remove last x-label from all but rightmost
            ax._remove_last_xtick = right_col < cols - 1
            ax._remove_first_xtick = False
            # Y-axis labels don't overlap in horizontal arrangement (only shown on leftmost)
            # No need to remove first/last y-labels when plots are side-by-side
            if not hide_x:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
        else:
            ax._show_ylabel = True
            ax._show_yticks = True
            if not hide_x:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
            if not hide_x:
                ax._remove_last_xtick = False
                ax._remove_first_xtick = False
                ax._remove_first_xtick = False

    @staticmethod
    def _grid_axis_sizes(
        ratios: Optional[Sequence[float]],
        n: int,
        avail_cm: float,
        gap_frac: Optional[float],
        default_gap_cm: float,
        param_name: str,
    ) -> Tuple[List[float], float]:
        """Per-cell sizes (cm) and the inter-cell gap (cm) along one grid axis.

        Shared by the row (``height_ratios``) and column (``width_ratios``)
        cases in the multi-subplot layout.

        Parameters
        ----------
        ratios : sequence of float, optional
            ``None`` for equal sizes (the pre-existing behaviour), or ``n``
            positive relative sizes, matplotlib ``height_ratios``/
            ``width_ratios`` style.
        n : int
            Number of rows (or columns) in the grid.
        avail_cm : float
            Total space available along this axis, after margins.
        gap_frac : float, optional
            A ``subplots_adjust`` ``wspace``/``hspace`` override: the gap as
            a fraction of the UNIT cell (the size a ratio of 1.0 gets).
            ``None`` uses ``default_gap_cm`` verbatim.
        default_gap_cm : float
            Gap (cm) to use when ``gap_frac`` is ``None``.
        param_name : str
            ``'height_ratios'`` or ``'width_ratios'``, for the error message.

        Returns
        -------
        sizes : list of float
            One size (cm) per row/column.
        gap : float
            The resolved gap (cm) between adjacent cells.

        Notes
        -----
        With uniform ratios (the default, ``ratios=None``) this reproduces
        the historical ``cell_w``/``cell_h`` and ``hspace``/``vspace``
        formulas exactly: a figure that does not use ``height_ratios``/
        ``width_ratios`` gets byte-identical output to before they existed.

        The gap is defined as a fraction of the UNIT cell -- the size a
        ratio of 1.0 would receive -- rather than of any one row/column's
        actual size, so it stays independent of the ratios themselves
        (a ``hspace`` chosen for a uniform grid keeps looking the same after
        some rows are made thinner or thicker).

        Raises
        ------
        ValueError
            If ``ratios`` is given but its length does not equal ``n``, or
            any entry is not strictly positive.
        """
        if ratios is None:
            resolved = [1.0] * n
        else:
            if len(ratios) != n:
                noun = "rows" if param_name == "height_ratios" else "columns"
                raise ValueError(
                    f"{param_name} has length {len(ratios)}, but the subplot "
                    f"grid has {n} {noun}"
                )
            if any(r <= 0 for r in ratios):
                raise ValueError(
                    f"{param_name} entries must all be positive, got {list(ratios)}"
                )
            resolved = [float(r) for r in ratios]

        total_ratio = float(sum(resolved))

        if n > 1 and gap_frac is not None:
            denom = total_ratio + gap_frac * (n - 1)
            unit = avail_cm / denom if denom > 0 else avail_cm / total_ratio
            gap = gap_frac * unit
        else:
            gap = default_gap_cm
            usable = avail_cm - (n - 1) * gap
            unit = usable / total_ratio

        sizes = [r * unit for r in resolved]
        return sizes, gap

    # -- page geometry ---------------------------------------------------
    #
    # ONE routine computes the frame rectangle of every axes, for every
    # figure: a lone plot is simply the 1x1 case of the subplot grid. Before
    # SPEC 3.3 / metadata v2 the single-plot path had no geometry at all (it
    # emitted a bare ``scale auto`` and let GLE auto-fit the page), which made
    # its layout non-invertible and forced a second, ad-hoc geometry hack for
    # the one case where auto-fit visibly broke (a colorbar clipped off the
    # right edge). Both are gone: the writer now always emits an explicit
    # ``amove x y`` + ``size w h`` + ``scale 1 1`` triple, and the recognizer
    # reads it straight back into ``Axes.placement``.
    #
    # GLE draws axis tick labels and axis titles OUTSIDE the frame rectangle,
    # so the margins below are *decoration* margins: space left blank around
    # the grid for those labels to occupy. They are expressed in units of the
    # figure's text height (``hei``), because the overflow scales with the
    # font -- measured against GLE 4.3.10, an 18 pt figure needs exactly the
    # same margins in ``hei`` units as a 12 pt one.

    #: Decoration margin (in units of ``hei``) for the layout's left edge --
    #: a horizontal run of y tick labels plus the rotated y-axis title.
    #: Measured worst cases: 3.11 hei for 4-character tick labels ("-0.5"),
    #: 4.72 hei for 7-character ones ("-0.0001"). The chosen value covers the
    #: former with slack; the latter needs ``subplots_adjust(left=...)``.
    _AUTO_MARGIN_LEFT_HEI = 4.0

    #: Same, bottom edge (one line of x tick labels + the x-axis title).
    #: Measured worst case 2.43 hei.
    _AUTO_MARGIN_BOTTOM_HEI = 3.0

    #: Same, top edge when any axes carries a title. Measured 1.49 hei.
    _AUTO_MARGIN_TITLE_HEI = 2.0

    #: Same, right edge when any axes carries a decorated secondary y-axis.
    #: Measured 3.28 hei.
    _AUTO_MARGIN_Y2_HEI = 4.0

    #: Same, top edge when any axes carries a secondary x scale. The bottom
    #: margin (tick labels plus the axis title) is the measured twin of this
    #: decoration; the top scale draws the same pair above the frame.
    _AUTO_MARGIN_X2_HEI = 3.0

    #: Same, for an edge with no axis title on it: only the outermost tick
    #: label's overhang past the frame corner. Measured worst case 0.52 hei.
    _AUTO_MARGIN_PLAIN_HEI = 1.5

    #: Lower bound on a computed frame extent, as a fraction of the page, so a
    #: very small ``figsize`` (or a very wide colorbar reservation) can never
    #: produce a zero or negative ``size``.
    _MIN_FRAME_FRACTION = 0.3

    @staticmethod
    def _axes_has_y2(ax: Axes) -> bool:
        """True if ``ax`` makes the writer decorate the secondary y-axis.

        Mirrors the conditions under which :meth:`GLEWriter.add_axes` emits a
        ``y2title``/``y2axis`` line -- the only ways the right-hand side of the
        frame acquires labels that need margin reserved for them.
        """
        return bool(
            ax.y2label_text
            or ax.y2min is not None
            or ax.y2max is not None
            or ax.y2scale == "log"
        )

    @staticmethod
    def _axes_has_x2(ax: Axes) -> bool:
        """True if ``ax`` draws a top scale that needs room above the frame.

        Limits, log, a title, tick-label styling, or a series bound to x2.
        Tick-label styling emits ``x2labels on`` with no dataset to hang
        those numbers on, so the top margin has to make room for them. A
        series alone still numbers the top axis: GLE turns those labels on
        for any dataset that uses it.
        """
        return bool(
            ax.x2label_text
            or ax.x2min is not None
            or ax.x2max is not None
            or ax.x2scale == "log"
            or ax.x2format is not None
            or ax.x2ticklabel_size is not None
            or ax.x2ticklabel_color is not None
            or ax.x2ticklabel_angle is not None
            or ax.has_x2_plots()
        )

    def _auto_margins_cm(self, writer, resolution) -> Tuple[float, float, float, float]:
        """``(left, right, bottom, top)`` decoration margins in page cm.

        **One policy, for every layout shape.** These are the margins of the
        whole grid, so what has to fit in them is the decoration of the
        *outermost* row and column -- exactly the decoration a lone plot
        carries, which is why the 1x1 case and the grid case cannot want
        different numbers. Each margin is therefore sized from the measured
        decoration overflow in units of ``hei`` (see the class constants
        above), whatever the grid's dimensions and whether or not its axes
        are shared.

        Grids used to keep fixed centimetre margins instead, inherited from
        before any of this was measured (left 1.0 cm plain / 1.5 cm shared).
        That is less than the ~1.32 cm a y-axis title plus tick labels like
        "-0.5" needs at the default 12 pt, so every such grid put ink off the
        left edge of the page. Sizing them like the lone plot fixes that, at
        the cost of moving every existing multi-plot figure's frames.

        The two conditionals are deliberately figure-wide rather than
        per-edge: a title anywhere in the grid reserves the top margin (it is
        the top row that will use it), and a decorated secondary y-axis
        anywhere reserves the right margin. Both over-reserve for the grid
        that puts its titled or y2-bearing axes somewhere other than the
        edge that needs the room -- the same trade the colorbar reservation
        below makes, and preferable to clipping.

        ``subplots_adjust`` overrides are applied last and win outright.
        """
        hei = fontsize_pt_to_cm(self.style.fontsize)
        titled = self._has_titles()
        grid_axes = self._grid_axes()
        has_y2 = any(self._axes_has_y2(ax) for ax in grid_axes)
        has_x2 = any(self._axes_has_x2(ax) for ax in grid_axes)
        margin_left = self._AUTO_MARGIN_LEFT_HEI * hei
        margin_bottom = self._AUTO_MARGIN_BOTTOM_HEI * hei
        if has_x2:
            margin_top = self._AUTO_MARGIN_X2_HEI * hei
            if titled:
                margin_top += self._AUTO_MARGIN_TITLE_HEI * hei
        else:
            margin_top = (
                self._AUTO_MARGIN_TITLE_HEI if titled else self._AUTO_MARGIN_PLAIN_HEI
            ) * hei
        margin_right = (
            self._AUTO_MARGIN_Y2_HEI if has_y2 else self._AUTO_MARGIN_PLAIN_HEI
        ) * hei
        if self._suptitle is not None:
            margin_top += self._suptitle_room_cm(writer.height_cm)

        # Convert margin overrides from normalized figure fractions to cm.
        if "left" in self._subplot_adjust:
            margin_left = self._subplot_adjust["left"] * writer.width_cm
        if "right" in self._subplot_adjust:
            margin_right = (1.0 - self._subplot_adjust["right"]) * writer.width_cm
        if "bottom" in self._subplot_adjust:
            margin_bottom = self._subplot_adjust["bottom"] * writer.height_cm
        if "top" in self._subplot_adjust:
            margin_top = (1.0 - self._subplot_adjust["top"]) * writer.height_cm

        # A colorbar beside the last column (or below the last row) takes the
        # outer margin; bars elsewhere widen an inner gap (_layout_rects).
        # With no colorbar, both margins are unchanged.
        col_extra, row_extra = self._colorbar_gaps_cm(resolution)
        max_rows, max_cols = self._grid_shape()
        if col_extra.get(max_cols - 1, 0.0) > 0:
            margin_right = max(margin_right, col_extra[max_cols - 1])
        if row_extra.get(max_rows - 1, 0.0) > 0:
            margin_bottom = max(margin_bottom, row_extra[max_rows - 1])

        return margin_left, margin_right, margin_bottom, margin_top

    def _suptitle_room_cm(self, page_height_cm: float) -> float:
        """How far the suptitle reaches down from the top of the page, in cm.

        The title's text height below its alignment point (all of it for
        ``va='top'``, half for ``'center'``), plus a quarter of it as a gap.
        """
        title = cast(TextAnnotation, self._suptitle)
        hei = fontsize_pt_to_cm(float(title.get("fontsize") or self.style.fontsize))
        below = {"top": 1.0, "center": 0.5}.get(title.get("va", "top"), 0.0)
        bottom_cm = float(title["y"]) * page_height_cm - below * hei
        return max(0.0, page_height_cm - bottom_cm) + 0.25 * hei

    def _grid_shape(self) -> Tuple[int, int]:
        """``(rows, cols)`` of the subplot grid the layout fills."""
        cells = [_grid_cells(ax) for ax in self._grid_axes()]
        max_rows = max((c[0] for c in cells), default=1)
        max_cols = max((c[1] for c in cells), default=1)
        return max_rows, max_cols

    def _colorbar_gaps_cm(
        self, resolution: Optional[SourceResolution]
    ) -> Tuple[Dict[int, float], Dict[int, float]]:
        """Room colorbars need, as ``({col: cm}, {row: cm})``.

        A vertical bar needs room to the right of its axes' grid column, a
        horizontal one below its row; each entry is the widest such bar in
        that column or row. Rows and columns count from 0 at the top left,
        as in :meth:`_layout_rects`.
        """
        col_extra: Dict[int, float] = {}
        row_extra: Dict[int, float] = {}
        for ax in self._grid_axes():
            vertical, horizontal = self._axes_colorbar_reserved_cm(ax, resolution)
            if not (vertical or horizontal):
                continue
            # A spanning axes' bar sits beside its last column / below its
            # last row.
            _rows, _cols, (_r0, row), (_c0, col) = _grid_cells(ax)
            col_extra[col] = max(col_extra.get(col, 0.0), vertical)
            row_extra[row] = max(row_extra.get(row, 0.0), horizontal)
        return col_extra, row_extra

    def _has_titles(self) -> bool:
        """True if any grid axes has a title (a broken axis titles the assembly)."""
        return any(ax.title_text for ax in self._grid_axes()) or any(
            bax.title_text for bax in self.broken_axes
        )

    def _grid_axes(self) -> List[Axes]:
        """The axes the subplot grid lays out: all but :meth:`add_axes` insets."""
        return [ax for ax in self.axes_list if ax.position is not None]

    def _share_groups(self, mode: Union[bool, str]) -> List[List[Axes]]:
        """The grid's cartesian axes in groups that share one range.

        ``True`` is one group; 'row' and 'col' group the panels by the rows
        or columns they span. A polar axes' limits are its own (see
        _resolve_axis_limits), and so are an inset's.
        """
        shared = [ax for ax in self._grid_axes() if not ax._polar]
        if mode not in ("row", "col"):
            return [shared]
        groups: Dict[Tuple[int, int], List[Axes]] = {}
        for ax in shared:
            _, _, row_span, col_span = _grid_cells(ax)
            groups.setdefault(row_span if mode == "row" else col_span, []).append(ax)
        return list(groups.values())

    def _layout_rects(self, writer, resolution) -> Tuple[List[tuple], List[tuple]]:
        """Default frame rect + grid cell for every axes, in ``axes_list`` order.

        Returns
        -------
        rects : list of (x, y, w, h)
            The frame rectangle in page cm the grid arrangement computes for
            each axes -- what the writer emits when the axes carries no
            explicit :attr:`Axes.placement` of its own. A broken-axis segment
            gets its slice of the cell rather than the whole cell.
        cells : list of (cell_x, cell_w, cell_y, cell_h)
            The un-sliced grid cell each axes sits in, which the broken-axis
            seam decoration needs in order to span the whole cell.

        The grid dimensions come from the axes' ``position`` tuples; sizes
        come from ``height_ratios``/``width_ratios`` (equal when unset) and
        the gaps from ``subplots_adjust``'s ``wspace``/``hspace`` (fixed
        defaults when unset). With one axes this degenerates to a single cell
        filling the page inside the margins -- no gaps are consulted at all.
        """
        margin_left, margin_right, margin_bottom, margin_top = self._auto_margins_cm(
            writer, resolution
        )

        max_rows, max_cols = self._grid_shape()
        # Colorbars beside inner columns / below inner rows widen the gap
        # after them; the last column's and row's are in the outer margins.
        col_extra, row_extra = self._colorbar_gaps_cm(resolution)
        col_gaps = [col_extra.get(c, 0.0) for c in range(max_cols - 1)]
        row_gaps = [row_extra.get(r, 0.0) for r in range(max_rows - 1)]

        # With a single cell there are no relative sizes to distribute, so
        # height_ratios/width_ratios are ignored rather than validated -- a
        # figure-level setting left over from a grid must not turn a lone
        # plot into a ValueError (see _grid_axis_sizes' length check).
        grid_axes = self._grid_axes()
        height_ratios = self.height_ratios if len(grid_axes) > 1 else None
        width_ratios = self.width_ratios if len(grid_axes) > 1 else None

        avail_w = max(
            writer.width_cm - margin_left - margin_right - sum(col_gaps),
            writer.width_cm * self._MIN_FRAME_FRACTION,
        )
        avail_h = max(
            writer.height_cm - margin_bottom - margin_top - sum(row_gaps),
            writer.height_cm * self._MIN_FRAME_FRACTION,
        )

        # Spacing between subplots; defaults preserve existing behavior.
        # Unlike the outer margins these are still fixed centimetres, and they
        # carry the same decoration an outer margin does (an inner column's y
        # title and tick labels live in the gap to its left). 1.5 cm clears
        # the measured 3.11 hei at the default 12 pt but not at, say, 18 pt,
        # where inner panels need ``subplots_adjust(wspace=...)``.
        default_hspace_cm = 0.0 if self._hides_inner_labels("y") else 1.5
        default_vspace_cm = 0.0 if self._hides_inner_labels("x") else 2.0
        wspace_frac = self._subplot_adjust.get("wspace")
        hspace_frac = self._subplot_adjust.get("hspace")

        # Per-column widths / per-row heights (cm), plus the resolved gap.
        # Equal-size unless height_ratios/width_ratios were given at
        # construction time (see _grid_axis_sizes); the equal-ratios path
        # reproduces the historical cell_w/cell_h/hspace/vspace formulas
        # exactly.
        col_widths, hspace = self._grid_axis_sizes(
            width_ratios,
            max_cols,
            avail_w,
            wspace_frac,
            default_hspace_cm,
            "width_ratios",
        )
        row_heights, vspace = self._grid_axis_sizes(
            height_ratios,
            max_rows,
            avail_h,
            hspace_frac,
            default_vspace_cm,
            "height_ratios",
        )

        # Cumulative left edge per column and bottom edge per row (GLE
        # coordinates: origin bottom-left, y increases upward), built once so
        # unequal row/column sizes are placed correctly -- with equal sizes
        # this reduces to the historical ``margin + i * (cell + gap)``
        # arithmetic.
        col_x_offsets = [margin_left]
        for w, extra in zip(col_widths[:-1], col_gaps):
            col_x_offsets.append(col_x_offsets[-1] + w + hspace + extra)

        row_y_bottoms = []
        consumed_h = margin_top
        for r, h in enumerate(row_heights):
            row_y_bottoms.append(writer.height_cm - consumed_h - h)
            consumed_h += h + vspace + (row_gaps[r] if r < len(row_gaps) else 0.0)

        rects: List[tuple] = []
        cells: List[tuple] = []
        for ax in self.axes_list:
            if ax.position is None:
                # An inset is not in the grid: its rect is its placement.
                # (Its cell is never read: only a broken-axis seam uses one.)
                if ax.placement is None:
                    raise ValueError(
                        "an axes from add_axes has no placement to draw it at; "
                        "set Axes.placement to its (x, y, width, height) in cm."
                    )
                rects.append(ax.placement)
                cells.append(
                    (
                        ax.placement[0],
                        ax.placement[2],
                        ax.placement[1],
                        ax.placement[3],
                    )
                )
                continue
            _rows, _cols, (top_row, bottom_row), (left_col, right_col) = _grid_cells(ax)
            cell_x = col_x_offsets[left_col]
            y_pos = row_y_bottoms[bottom_row]
            # A spanning axes covers its cells and the gaps between them. The
            # one-cell case keeps the plain cell size, so its arithmetic (and
            # emitted size) is unchanged.
            if right_col > left_col:
                cell_w = col_x_offsets[right_col] + col_widths[right_col] - cell_x
            else:
                cell_w = col_widths[left_col]
            if bottom_row > top_row:
                cell_h = row_y_bottoms[top_row] + row_heights[top_row] - y_pos
            else:
                cell_h = row_heights[top_row]

            # A broken-axis segment occupies a slice of its grid cell rather
            # than the whole thing; everything else about the emission is
            # identical to an ordinary subplot.
            owner = ax._break_owner
            x_pos, graph_w = cell_x, cell_w
            seg_y, graph_h = y_pos, cell_h
            if owner is not None and owner.axis == "y":
                dy, graph_h = owner.segment_extent(ax._break_index, cell_h)
                seg_y = y_pos + dy
            elif owner is not None:
                dx, graph_w = owner.segment_extent(ax._break_index, cell_w)
                x_pos = cell_x + dx

            rects.append((x_pos, seg_y, graph_w, graph_h))
            cells.append((cell_x, cell_w, y_pos, cell_h))

        return rects, cells

    def gca(self) -> Axes:
        """Get current axes (or create if needed)."""
        if self._current_axes is None:
            return self.add_subplot(111)
        return self._current_axes

    # Convenience plotting methods (plot on current axes)

    def plot(self, x, y, *args, **kwargs):
        """Plot on current axes. See :meth:`Axes.plot`."""
        return self.gca().plot(x, y, *args, **kwargs)

    def step(self, x, y, *args, **kwargs):
        """Step plot on current axes."""
        return self.gca().step(x, y, *args, **kwargs)

    def stem(self, *args, **kwargs):
        """Stem plot on current axes."""
        return self.gca().stem(*args, **kwargs)

    def scatter(self, x, y, *args, **kwargs):
        """Scatter on current axes. See :meth:`Axes.scatter`."""
        return self.gca().scatter(x, y, *args, **kwargs)

    def bar(self, x, height, **kwargs):
        """Bar chart on current axes."""
        return self.gca().bar(x, height, **kwargs)

    def barh(self, y, width, height=None, left=None, **kwargs):
        """Horizontal bars on the current axes. See :meth:`Axes.barh`."""
        return self.gca().barh(y, width, height, left, **kwargs)

    def fill_between(self, x, y1, y2=0, **kwargs):
        """Fill between on current axes. See :meth:`Axes.fill_between`."""
        return self.gca().fill_between(x, y1, y2, **kwargs)

    def fill_betweenx(self, y, x1, x2=0, **kwargs):
        """Fill between two x curves on the current axes.

        See :meth:`Axes.fill_betweenx`.
        """
        return self.gca().fill_betweenx(y, x1, x2, **kwargs)

    def stackplot(self, x, *args, **kwargs):
        """Stacked bands on the current axes. See :meth:`Axes.stackplot`."""
        return self.gca().stackplot(x, *args, **kwargs)

    def fill(self, x, y, *args, **kwargs):
        """Fill a polygon on the current axes. See :meth:`Axes.fill`."""
        return self.gca().fill(x, y, *args, **kwargs)

    def errorbar(self, x, y, *args, **kwargs):
        """Error bar plot on current axes. See :meth:`Axes.errorbar`."""
        return self.gca().errorbar(x, y, *args, **kwargs)

    def text(self, x, y, s, fontdict=None, **kwargs) -> TextAnnotation:
        """Add text to the figure, in figure fractions.

        Parameters
        ----------
        x, y : float
            Position as fractions of the page: ``(0, 0)`` is the bottom-left
            corner and ``(1, 1)`` the top-right, as matplotlib's figure
            coordinates.
        s : str
            The text.
        fontdict : dict, optional
            Text keywords, overridden by the same keyword passed directly.
        **kwargs
            ``color``, ``fontsize``, ``ha``, ``va``, ``rotation`` and
            ``bbox``, as for :meth:`Axes.text`. Any other keyword, including
            ``transform``, warns and is ignored.

        Returns
        -------
        TextAnnotation
            The stored text, also appended to :attr:`texts`.

        Notes
        -----
        Written after every axes, so it sits on top of them. Use
        :meth:`Axes.text` to place text in one axes' data coordinates.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, axes = glp.subplots(1, 2)
        >>> label = fig.text(0.02, 0.98, "(a)", ha="left", va="top")
        """
        if fontdict is not None and not isinstance(fontdict, dict):
            raise TypeError(
                f"text(fontdict=...) must be a dict of text keywords, got "
                f"{fontdict!r}"
            )
        options = {**(fontdict or {}), **kwargs}
        _rename_text_aliases("Figure.text", options)
        fields = _text_fields(
            self.style,
            "Figure.text",
            _finite_float(x, "x"),
            _finite_float(y, "y"),
            s,
            color=options.pop("color", None),
            fontsize=options.pop("fontsize", None),
            ha=options.pop("ha", "left"),
            va=options.pop("va", "center"),
            bbox=options.pop("bbox", None),
            rotation=options.pop("rotation", None),
            kwargs=options,
            supported="fontdict, color, fontsize, ha, va, rotation, bbox",
        )
        text = TextAnnotation(**fields)
        self.texts.append(text)
        return text

    def suptitle(self, t, **kwargs) -> TextAnnotation:
        """Add a centred title to the figure, above every axes.

        Parameters
        ----------
        t : str
            The title.
        x, y : float, default: 0.5, 0.98
            Position in figure fractions, as for :meth:`text`.
        ha : {'center', 'left', 'right'}, default: 'center'
            Horizontal alignment.
        va : {'top', 'center', 'bottom'}, default: 'top'
            Vertical alignment.
        fontsize : float or str, default: 'large'
            Points, or a matplotlib size name relative to the figure's
            ``GLEStyleConfig.fontsize``.
        **kwargs
            ``color``, ``rotation`` and ``bbox``, as for :meth:`text`. Any
            other keyword warns and is ignored.

        Returns
        -------
        TextAnnotation
            The stored title.

        Notes
        -----
        A second call replaces the title, as in matplotlib. Unlike
        matplotlib, the layout lowers the top of the axes to leave room for
        the title, unless ``subplots_adjust(top=...)`` sets that edge.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, axes = glp.subplots(1, 2)
        >>> title = fig.suptitle("Sample A")
        """
        _rename_text_aliases("suptitle", kwargs)
        fontsize = kwargs.pop("fontsize", None)
        fields = _text_fields(
            self.style,
            "suptitle",
            _finite_float(kwargs.pop("x", 0.5), "x"),
            _finite_float(kwargs.pop("y", 0.98), "y"),
            t,
            color=kwargs.pop("color", None),
            fontsize=_resolve_fontsize(
                self.style,
                "large" if fontsize is None else fontsize,
                "suptitle(fontsize",
            ),
            ha=kwargs.pop("ha", "center"),
            va=kwargs.pop("va", "top"),
            bbox=kwargs.pop("bbox", None),
            rotation=kwargs.pop("rotation", None),
            kwargs=kwargs,
            supported="x, y, color, fontsize, ha, va, rotation, bbox",
        )
        self._suptitle = TextAnnotation(**fields)
        return self._suptitle

    def axvline(self, x=0.0, **kwargs):
        """Vertical reference line on current axes."""
        return self.gca().axvline(x, **kwargs)

    def hlines(self, y, xmin, xmax, *args, **kwargs):
        """Horizontal segments on the current axes. See :meth:`Axes.hlines`."""
        return self.gca().hlines(y, xmin, xmax, *args, **kwargs)

    def vlines(self, x, ymin, ymax, *args, **kwargs):
        """Vertical segments on the current axes. See :meth:`Axes.vlines`."""
        return self.gca().vlines(x, ymin, ymax, *args, **kwargs)

    def axhline(self, y=0.0, **kwargs):
        """Horizontal reference line on current axes."""
        return self.gca().axhline(y, **kwargs)

    def axvspan(self, xmin, xmax, **kwargs):
        """Shaded vertical band on current axes."""
        return self.gca().axvspan(xmin, xmax, **kwargs)

    def axhspan(self, ymin, ymax, **kwargs):
        """Shaded horizontal band on current axes."""
        return self.gca().axhspan(ymin, ymax, **kwargs)

    def imshow(self, Z, **kwargs):
        """Display gridded data as a heatmap on current axes."""
        return self.gca().imshow(Z, **kwargs)

    def contour(self, *args, **kwargs):
        """Draw contour lines on current axes."""
        return self.gca().contour(*args, **kwargs)

    def tripcolor(self, x, y, z, **kwargs):
        """Scattered-data heatmap on current axes."""
        return self.gca().tripcolor(x, y, z, **kwargs)

    def tricontour(self, x, y, z, **kwargs):
        """Scattered-data contour lines on current axes."""
        return self.gca().tricontour(x, y, z, **kwargs)

    def colorbar(
        self,
        mappable=None,
        cax=None,
        ax=None,
        use_gridspec=True,
        *,
        orientation: Optional[str] = None,
        label: Optional[str] = None,
        format: Optional[str] = None,
        nticks: Optional[int] = None,
        width: float = 0.5,
        sep: Optional[float] = None,
        **kwargs,
    ):
        """Attach a colorbar to a heatmap or a colour-mapped scatter.

        Parameters
        ----------
        mappable : HeatmapSeries, optional
            The heatmap the bar shows, as returned by :meth:`Axes.imshow`,
            :meth:`Axes.pcolormesh`, :meth:`Axes.tripcolor` or
            :meth:`Axes.contourf`. Default: the
            heatmap on ``ax``, or, on an axes with no heatmap, its
            colour-mapped scatter (``scatter(c=...)``) drawn last. With no
            ``ax`` either: the one axes with a heatmap, or, if no axes has
            one, the one axes with a colour-mapped scatter.
            :meth:`Axes.scatter` returns the axes, not a mappable, so a
            scatter's bar is chosen by ``ax``.
        cax : Axes, optional
            Not supported: GLE draws the bar beside the axes it belongs to, not
            into another one. Passing it warns and is otherwise ignored.
        ax : Axes, optional
            The axes the bar is drawn beside. It must be the axes holding
            ``mappable``; with no ``mappable``, its heatmap is the one shown.
        use_gridspec : bool
            Accepted for matplotlib compatibility. The subplot grid always
            makes room for the bar, whatever its value.
        orientation : {'vertical', 'horizontal'}, optional
            ``'vertical'`` (the default, ``None``) draws the bar to the right
            of the axes; ``'horizontal'`` draws it below the axes, under the
            x tick labels and title.
        label : str, optional
            Colorbar axis label: rotated, to the right of a vertical bar's
            tick numbers; centred under a horizontal one's.
        format : str, optional
            GLE ``format$`` string for the tick labels (e.g. ``'fix 1'``).
            Default: fixed-point with as many decimals as the tick values
            need, from the first value and the tick step.
        nticks : int, optional
            Approximate number of tick intervals. Default: 5, or for a
            ``contourf`` with evenly spaced levels, a tick at every
            ``ceil(len(levels) / 10)``-th level (``nticks`` replacing the 10).
        width : float
            Bar thickness in cm: its width when vertical, its height when
            horizontal.
        sep : float, optional
            Gap (cm) between the axes frame and the bar. For a vertical bar
            it is measured from the frame's right edge (default 0.3). For a
            horizontal bar it is measured from the frame's bottom edge to
            the bar's top (default: clear of the x tick labels and title at
            the figure's font size when ``colorbar()`` is called).

        Returns
        -------
        dict
            The stored colorbar dict (also attached to the heatmap or scatter
            under ``'colorbar'``).

        Raises
        ------
        ValueError
            If there is nothing to show (no heatmap or colour-mapped scatter
            on the figure or on ``ax``, or more than one axes has one and
            neither ``mappable`` nor ``ax`` picks it), if ``mappable`` is not
            on this figure or
            not on ``ax``, if ``orientation`` is not an accepted value, if
            ``nticks`` is not a positive integer, or if the heatmap has neither z data nor explicit ``vmin``/``vmax``
            to derive a colour range from and no reference to resolve one
            from later.
        TypeError
            If ``mappable`` is not a heatmap or ``ax`` is not an ``Axes``.

        Notes
        -----
        A heatmap carries at most one bar, and each axes at most one
        heatmap, so a grid of heatmaps shows one bar per axes, each on its
        own scale. A ``contourf``'s bar shows its bands, from its first level
        to its last; with unevenly spaced levels it is ticked in equal steps,
        and it draws no ``extend`` end caps (both warn). A scatter's bar runs
        from its ``vmin`` to its ``vmax``;
        a scatter's bar gives way to the next bar called on its axes, so an
        axes shows one bar. The subplot grid makes room for every bar: a vertical bar
        widens the gap to the right of its column (or the right margin), and
        a horizontal one the gap below its row (or the bottom margin).

        **Reference-backed heatmaps** (SPEC 14.5). A heatmap whose numbers
        come from a :class:`~gleplot.sources.GridRef` has no arrays *here* --
        they arrive per write from the provider. Rather than read arrays it
        does not have, the colorbar records an **auto range** and each write
        computes ``zmin``/``zmax``/``zstep`` from the data that write
        resolved, so a table edit re-flows into the bar instead of leaving a
        range baked at ``colorbar()`` time. Explicit ``vmin``/``vmax`` on the
        heatmap short-circuit that and are used as-is, here and at write time
        alike.

        Any other keyword (``shrink``, ``pad``, ``extend``, ...) warns and is
        ignored.
        """
        warn_unsupported_keywords("colorbar", kwargs)
        if orientation not in (None, "vertical", "horizontal"):
            raise ValueError(
                f"colorbar() orientation must be 'vertical' or 'horizontal', "
                f"got {orientation!r}"
            )
        if ax is not None and not isinstance(ax, Axes):
            raise TypeError(
                f"colorbar() ax must be one Axes of this figure, got "
                f"{type(ax).__name__}; call colorbar() once per axes to give "
                f"each its own bar"
            )
        if nticks is not None and (
            isinstance(nticks, bool)
            or not isinstance(nticks, (int, np.integer))
            or nticks < 1
        ):
            raise ValueError(
                f"colorbar() nticks must be a positive integer (the number of "
                f"tick intervals) or None, got {nticks!r}"
            )
        if cax is not None:
            warn_external(
                "colorbar() cax is not supported: GLE draws the bar beside the "
                "axes of the heatmap or scatter it shows, so cax is ignored. "
                "Pass ax= (or nothing) instead."
            )
        hm, owner = self._colorbar_holder(mappable, ax)
        # An axes shows one bar: a scatter's bar gives way to the new one.
        for other in owner.scatters:
            other.pop("colorbar", None)

        zmin: Optional[float]
        zmax: Optional[float]
        if isinstance(hm, ScatterSeries):
            zmin, zmax = float(hm["vmin"]), float(hm["vmax"])
        elif "levels" in hm:
            # As in matplotlib, a contourf's bar spans its levels.
            zmin, zmax = float(hm["levels"][0]), float(hm["levels"][-1])
            if hm["extend"] != "neither":
                warn_external(
                    f"colorbar() of a contourf with extend={hm['extend']!r} "
                    "draws no triangular end caps: GLE's colorbar shows only "
                    "the range between the first and last level."
                )
        else:
            values = hm["z"] if hm["source"] == "grid" else hm["zpts"]
            have_values = values is not None and np.asarray(values).size > 0
            zmin = float(hm["vmin"]) if hm["vmin"] is not None else None
            zmax = float(hm["vmax"]) if hm["vmax"] is not None else None
            if have_values:
                if zmin is None:
                    zmin = float(np.nanmin(values))
                if zmax is None:
                    zmax = float(np.nanmax(values))
            elif hm["source"] == "function":
                # GLE maps a function colormap from 0 to 1 unless told otherwise.
                zmin = 0.0 if zmin is None else zmin
                zmax = 1.0 if zmax is None else zmax

        divisions = int(nticks) if nticks else DEFAULT_COLORBAR_NTICKS

        horizontal = orientation == "horizontal"
        if sep is None:
            if horizontal:
                hei = fontsize_pt_to_cm(self.style.fontsize)
                sep = round(self._AUTO_MARGIN_BOTTOM_HEI * hei + 0.3, 2)
            else:
                sep = 0.3
        cb = {
            "label": owner._text(label),
            "format": None if format is None else str(format),
            "width": float(width),
            "sep": float(sep),
            "zmin": zmin,
            "zmax": zmax,
            "zstep": None,
        }
        if horizontal:
            # Absent means vertical, so a vertical bar's dict is unchanged.
            cb["orientation"] = "horizontal"
        step = (
            self._contourf_colorbar_step(hm["levels"], nticks)
            if "levels" in hm
            else None
        )
        if step is not None:
            cb["zstep"] = step
        elif zmin is not None and zmax is not None:
            span = zmax - zmin
            cb["zstep"] = (span / divisions) if span > 0 else 1.0
        else:
            # No arrays and no explicit bound for at least one end. That is a
            # legal, resolvable state only for a reference-backed heatmap;
            # anything else has nowhere for a range to come from, and saying
            # so beats the numpy TypeError this used to raise.
            source = source_of(hm)
            if not (isinstance(source, DataSource) and source.is_reference()):
                raise ValueError(
                    "colorbar() cannot determine a colour range: this heatmap "
                    "carries no z data, and no reference-backed data source to "
                    "resolve one from at write time. Pass vmin/vmax explicitly, "
                    "or attach the colorbar after the data."
                )
            cb[COLORBAR_AUTO_RANGE] = True
            cb[COLORBAR_NTICKS] = divisions
        if cb["format"] is None and zmin is not None and cb["zstep"] is not None:
            cb["format"] = colorbar_format(zmin, float(cb["zstep"]))
        hm["colorbar"] = cb
        return cb

    @staticmethod
    def _contourf_colorbar_step(levels, nticks: Optional[int]) -> Optional[float]:
        """The tick step at the levels of a ``contourf``'s bar, if there is one.

        The colorbar sub ticks from the first level in equal steps, so evenly
        spaced levels are ticked at every ``ceil(len(levels) / nbins)``-th
        level, the step matplotlib's ``FixedLocator(levels, nbins=10)`` takes
        (``nticks`` replacing the 10). Uneven levels warn and get ``None``:
        the sub has no list of positions, so the bar is ticked as any other.
        """
        steps = np.diff(np.asarray(levels, dtype=float))
        if np.allclose(steps, steps[0], rtol=1e-6, atol=0):
            return float(steps[0] * math.ceil(len(levels) / (nticks or 10)))
        warn_external(
            "colorbar() of a contourf with unevenly spaced levels draws its "
            "bands at the levels but ticks the bar at even steps: GLE's "
            "colorbar cannot place ticks at a list of values. Use evenly "
            "spaced levels for ticks at the levels."
        )
        return None

    def _colorbar_holder(self, mappable, ax: Optional[Axes]) -> Tuple[Series, Axes]:
        """The heatmap or scatter :meth:`colorbar` attaches to, and its axes.

        With neither ``mappable`` nor ``ax``, the one axes with a heatmap
        wins, as before scatters could carry a bar; failing that, the one
        axes with a colour-mapped scatter.
        """
        if ax is not None and not any(a is ax for a in self.axes_list):
            raise ValueError(
                "colorbar() ax is not an axes of this figure; call colorbar() "
                "on the figure that holds it"
            )
        if mappable is None:
            if ax is not None:
                holder = _axes_colorbar_holder(ax)
                if holder is None:
                    raise ValueError(
                        "colorbar() needs a heatmap or a colour-mapped scatter "
                        "on ax: draw one there with ax.imshow(), "
                        "ax.pcolormesh(), ax.tripcolor() or "
                        "ax.scatter(..., c=values) first"
                    )
                return holder, ax
            bearing = [a for a in self.axes_list if a.heatmaps] or [
                a for a in self.axes_list if _axes_colorbar_holder(a)
            ]
            if not bearing:
                raise ValueError(
                    "colorbar() requires a heatmap (imshow/pcolormesh/tripcolor/"
                    "contourf/function2d) or a colour-mapped scatter "
                    "(scatter(..., c=values)) on some axes"
                )
            if len(bearing) > 1:
                raise ValueError(
                    "colorbar() is ambiguous: more than one axes has a heatmap "
                    "or a colour-mapped scatter. Pass the heatmap to show, as "
                    "imshow() returned it: fig.colorbar(im), or the axes: "
                    "fig.colorbar(ax=ax)"
                )
            (only,) = bearing
            return cast(Series, _axes_colorbar_holder(only)), only
        if not isinstance(mappable, HeatmapSeries):
            raise TypeError(
                f"colorbar() mappable must be the heatmap imshow(), pcolormesh(), "
                f"tripcolor() or contourf() returned, got {type(mappable).__name__}. "
                f"For a scatter, pass its axes as ax=...; pass a label as "
                f"label=..."
            )
        owner = next(
            (a for a in self.axes_list if any(h is mappable for h in a.heatmaps)),
            None,
        )
        if owner is None:
            raise ValueError(
                "colorbar() mappable is not a heatmap on this figure; call "
                "colorbar() on the figure that drew it"
            )
        if ax is not None and ax is not owner:
            raise ValueError(
                "colorbar() ax must be the axes holding mappable: gleplot draws "
                "the bar beside its heatmap's own axes"
            )
        return mappable, owner

    def xlabel(self, label: str, **kwargs):
        """Set x label on current axes.

        Keywords are as for :meth:`Axes.set_xlabel`.
        """
        return self.gca().set_xlabel(label, **kwargs)

    def ylabel(self, label: str, axis: str = "y", **kwargs):
        """Set y label on current axes.

        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right), as for
            :meth:`Axes.set_ylabel`.
        **kwargs
            As for :meth:`Axes.set_ylabel`.
        """
        return self.gca().set_ylabel(label, axis=axis, **kwargs)

    def title(self, label: str, **kwargs):
        """Set title on current axes.

        Keywords are as for :meth:`Axes.set_title`.
        """
        return self.gca().set_title(label, **kwargs)

    def legend(self, *args, **kwargs) -> "Figure":
        """Add one legend for the whole figure, listing every axes' series.

        Parameters
        ----------
        loc : str, default: 'upper right'
            The corner of the page the legend sits in, as a matplotlib
            location (``'upper center'``, ``'lower left'``, ...). As in
            matplotlib, ``'best'`` is not supported for a figure legend and
            raises ``ValueError``.
        bbox_to_anchor : tuple of float, optional
            ``(x, y)`` or ``(x, y, width, height)`` in figure fractions: the
            ``loc`` corner of the legend sits on that point, or on that
            corner of the box.
        ncol, ncols, fontsize, frameon, facecolor, labelcolor : optional
            As for :meth:`Axes.legend`.
        borderpad, handlelength, handletextpad, columnspacing : float, optional
            As for :meth:`Axes.legend`.
        **kwargs
            Any other matplotlib legend keyword warns and is ignored.

        Returns
        -------
        self

        Notes
        -----
        The entries are the labelled series of every axes, axes by axes in
        the order they were created, and each axes' series in the order they
        were added. Explicit handles and labels are not supported: legend
        text comes from each series' ``label=``. While a figure legend
        exists, an axes draws its own legend only if :meth:`Axes.legend` was
        called on it, as in matplotlib. The legend is a GLE ``begin key``
        block written after every axes, half a font size in from the page
        edges its corner is anchored to. A second call replaces the legend.
        The layout does not make room for it: leave room with
        ``subplots_adjust``.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, axes = glp.subplots(1, 2)
        >>> _ = axes[0].plot([0, 1], [0, 1], label="a")
        >>> _ = axes[1].plot([0, 1], [1, 0], label="b")
        >>> _ = fig.legend(loc="upper center", ncol=2)
        """
        if args:
            warn_external(
                "legend(): explicit handles/labels are not supported; legend "
                "text comes from each series' label= argument. The positional "
                "arguments were ignored.",
            )
        loc = kwargs.pop("loc", None)
        if isinstance(loc, str) and loc.strip().lower() == "best":
            raise ValueError(
                "legend(loc='best') is not supported for a figure legend, as "
                "in matplotlib. Pass a corner such as 'upper right'."
            )
        position = Axes._resolve_legend_loc(loc)
        ncol = 1
        for name in ("ncol", "ncols"):
            if name in kwargs:
                value = kwargs.pop(name)
                ncol = 1 if value is None else Axes._resolve_legend_ncol(value)
        fontsize = kwargs.pop("fontsize", None)
        frameon = kwargs.pop("frameon", None)
        facecolor = kwargs.pop("facecolor", None)
        labelcolor = Axes._resolve_legend_labelcolor(
            kwargs.pop("labelcolor", None), None
        )
        anchor = kwargs.pop("bbox_to_anchor", None)
        if anchor is not None:
            anchor = Axes._resolve_legend_anchor(anchor, position, "figure")
        spacing = {}
        for name in LEGEND_SPACING_TO_KEY:
            value = kwargs.pop(name, None)
            if value is not None:
                spacing[name] = _finite_float(value, f"legend({name}=...)")
        warn_unsupported_keywords(
            "Figure.legend",
            kwargs,
            "A figure legend takes loc, bbox_to_anchor, ncol, ncols, fontsize, "
            "frameon, facecolor, labelcolor, borderpad, handlelength, "
            "handletextpad and columnspacing.",
        )
        self._legend = {
            "loc": position,
            "anchor": None if anchor is None else list(anchor),
            "ncol": ncol,
            "fontsize": (
                None if fontsize is None else _resolve_fontsize(self.style, fontsize)
            ),
            "frameon": True if frameon is None else bool(frameon),
            "facecolor": None if facecolor is None else rgb_to_gle(facecolor),
            "labelcolor": labelcolor,
            "spacing": spacing,
        }
        return self

    # Free page drawing. Positions and sizes are in cm from the bottom-left
    # corner of the page, like Axes.placement, not in data coordinates.

    def _add_drawing(self, drawing: dict, fill=None, color=None, linewidth=None):
        if fill is not None and not _is_none_color(fill):
            drawing["fill"] = rgb_to_gle(fill)
        if _is_none_color(color):
            if drawing["kind"] not in ("circle", "ellipse", "polygon"):
                raise ValueError(
                    f"color='none' would leave the {drawing['kind']} invisible; "
                    "pass a colour, or leave it out for black"
                )
            drawing["color"] = "none"
        elif color is not None:
            drawing["color"] = rgb_to_gle(color)
        if linewidth is not None:
            drawing["linewidth"] = _page_positive("linewidth", linewidth)
        self._drawings.append(drawing)

    def _add_text_block(self, kind: str, x, y, s) -> None:
        self._drawings.append(
            {
                "kind": kind,
                "x": _finite_float(x, "x"),
                "y": _finite_float(y, "y"),
                "text": _page_text(kind, s),
            }
        )

    def circle(self, x, y, radius, *, fill=None, color=None, linewidth=None) -> None:
        """Draw a circle on the page, outside any axes.

        Parameters
        ----------
        x, y : float
            Centre, in cm from the bottom-left corner of the page.
        radius : float
            Radius in cm.
        fill : color, optional
            Fill colour. Default (or ``'none'``): not filled.
        color : color, optional
            Outline colour, or ``'none'`` for no outline. Default: black.
        linewidth : float, optional
            Outline width in points. Default: GLE's line width.

        Notes
        -----
        Page drawings are written after every axes, so they sit on top of
        them, in the order they were added. Writes GLE's ``circle``.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig = glp.figure()
        >>> fig.circle(2, 3, radius=0.4, fill="red")
        """
        drawing = {
            "kind": "circle",
            "x": _finite_float(x, "x"),
            "y": _finite_float(y, "y"),
            "radius": _page_positive("radius", radius),
        }
        self._add_drawing(drawing, fill, color, linewidth)

    def ellipse(
        self, x, y, width, height, *, fill=None, color=None, linewidth=None
    ) -> None:
        """Draw an ellipse on the page, outside any axes.

        Parameters
        ----------
        x, y : float
            Centre, in cm from the bottom-left corner of the page.
        width, height : float
            Diameters along x and y, in cm.
        fill : color, optional
            Fill colour. Default (or ``'none'``): not filled.
        color : color, optional
            Outline colour, or ``'none'`` for no outline. Default: black.
        linewidth : float, optional
            Outline width in points. Default: GLE's line width.

        Notes
        -----
        Writes GLE's ``ellipse``. See :meth:`circle` for the drawing order.
        """
        drawing = {
            "kind": "ellipse",
            "x": _finite_float(x, "x"),
            "y": _finite_float(y, "y"),
            "width": _page_positive("width", width),
            "height": _page_positive("height", height),
        }
        self._add_drawing(drawing, fill, color, linewidth)

    def arc(self, x, y, radius, theta1, theta2, *, color=None, linewidth=None) -> None:
        """Draw a circular arc on the page, outside any axes.

        Parameters
        ----------
        x, y : float
            Centre of the circle, in cm from the bottom-left corner of the page.
        radius : float
            Radius in cm.
        theta1, theta2 : float
            Start and end angles in degrees. The arc runs anticlockwise from
            ``theta1`` to ``theta2``; 0 is three o'clock.
        color : color, optional
            Line colour. Default: black.
        linewidth : float, optional
            Line width in points. Default: GLE's line width.

        Notes
        -----
        Writes GLE's ``arc``. See :meth:`circle` for the drawing order.
        """
        drawing = {
            "kind": "arc",
            "x": _finite_float(x, "x"),
            "y": _finite_float(y, "y"),
            "radius": _page_positive("radius", radius),
            "theta1": _finite_float(theta1, "theta1"),
            "theta2": _finite_float(theta2, "theta2"),
        }
        self._add_drawing(drawing, None, color, linewidth)

    def bezier(self, x, y, *, color=None, linewidth=None) -> None:
        """Draw a cubic Bézier curve on the page, outside any axes.

        Parameters
        ----------
        x, y : sequence of 4 floats
            The start point, the two control points and the end point, in cm
            from the bottom-left corner of the page.
        color : color, optional
            Line colour. Default: black.
        linewidth : float, optional
            Line width in points. Default: GLE's line width.

        Notes
        -----
        Writes GLE's ``bezier``. See :meth:`circle` for the drawing order.
        """
        xs, ys = _page_points(x, y, 4, exact=True)
        self._add_drawing({"kind": "bezier", "x": xs, "y": ys}, None, color, linewidth)

    def curve(
        self, x, y, start_slope, end_slope, *, color=None, linewidth=None
    ) -> None:
        """Draw a smooth curve through points on the page, outside any axes.

        Parameters
        ----------
        x, y : sequence of float
            At least two points the curve passes through, in order, in cm from
            the bottom-left corner of the page.
        start_slope, end_slope : (float, float)
            Tangent vector ``(dx, dy)`` of the curve at the first and last
            point. Its length matters as well as its direction: a longer
            vector carries the curve further that way before it turns.
        color : color, optional
            Line colour. Default: black.
        linewidth : float, optional
            Line width in points. Default: GLE's line width.

        Notes
        -----
        Writes GLE's ``curve``. See :meth:`circle` for the drawing order.
        """
        xs, ys = _page_points(x, y, 2)
        drawing = {
            "kind": "curve",
            "x": xs,
            "y": ys,
            "start_slope": _page_slope("start_slope", start_slope),
            "end_slope": _page_slope("end_slope", end_slope),
        }
        self._add_drawing(drawing, None, color, linewidth)

    def polygon(self, x, y, *, fill=None, color=None, linewidth=None) -> None:
        """Draw a closed polygon on the page, outside any axes.

        Parameters
        ----------
        x, y : sequence of float
            At least three corners, in order, in cm from the bottom-left corner
            of the page. The last corner is joined back to the first.
        fill : color, optional
            Fill colour. Default (or ``'none'``): not filled.
        color : color, optional
            Outline colour, or ``'none'`` for no outline. Default: black.
        linewidth : float, optional
            Outline width in points. Default: GLE's line width.

        Notes
        -----
        Writes a GLE ``begin path`` block. See :meth:`circle` for the drawing
        order.
        """
        xs, ys = _page_points(x, y, 3)
        self._add_drawing({"kind": "polygon", "x": xs, "y": ys}, fill, color, linewidth)

    def table(self, x, y, s) -> None:
        """Write text on the page with its columns lined up, outside any axes.

        Parameters
        ----------
        x, y : float
            Where the text starts, in cm from the bottom-left corner of the page.
        s : str
            The text. Words separated by more than one space are aligned in
            columns; a newline starts a row. A row cannot start with the word
            ``begin`` or ``end``.

        Notes
        -----
        Writes a GLE ``begin table`` block. The columns line up exactly only
        in a fixed-pitch font. See :meth:`circle` for the drawing order.
        """
        self._add_text_block("table", x, y, s)

    def tex(self, x, y, s) -> None:
        """Write a block of LaTeX on the page, outside any axes.

        Parameters
        ----------
        x, y : float
            Where the text starts, in cm from the bottom-left corner of the page.
        s : str
            LaTeX source, for example ``r"\\textbf{Note}"``. A line cannot start
            with the word ``begin`` or ``end``; ``\\begin{...}`` is fine. The
            last line cannot hold a ``%`` comment.

        Notes
        -----
        Writes a GLE ``begin tex`` block, so compiling the figure needs a
        LaTeX installation that GLE can find. GLE sets the text in one LaTeX
        box, so a newline in ``s`` does not start a new line in the output;
        use a ``tabular`` for several lines. See :meth:`circle` for the
        drawing order.
        """
        self._add_text_block("tex", x, y, s)

    # File I/O methods

    def absolutize_file_references(self, base_dir) -> None:
        """Rewrite relative data and image paths to absolute paths.

        Reference-mode series (``file_series``) carry their ``data_file``
        verbatim into the generated ``data`` command, and placed images
        (:meth:`Axes.image`) their ``file`` into the draw call, so a relative
        path is
        only valid when GLE runs in the directory the reference is relative
        to. Call this on a figure whose script will be generated or compiled
        SOMEWHERE ELSE: the live preview's temp session dir, an export to a
        different directory, or Save As across directories. Import-mode
        series regenerate their sidecars next to the script and are
        untouched. Paths are emitted in POSIX form (GLE accepts forward
        slashes on Windows); the writer quotes names containing spaces.
        """
        base = Path(base_dir)
        for ax in self.axes_list:
            for fs in ax.file_series:
                name = fs.get("data_file")
                if not name:
                    continue
                ref = Path(name)
                if not ref.is_absolute():
                    fs["data_file"] = (base / ref).resolve().as_posix()
            for image in ax.images:
                ref = Path(image["file"])
                if not ref.is_absolute():
                    image["file"] = (base / ref).resolve().as_posix()

    def savefig_gle(
        self,
        filepath: str,
        data_provider=None,
        preview_decimation: Optional[DecimationPolicy] = None,
        **kwargs,
    ) -> Path:
        """
        Save figure as GLE script.

        Parameters
        ----------
        filepath : str
            Output file path
        data_provider : DataProvider, optional
            Resolver for series whose ``data_source`` references a table
            (see :meth:`savefig` and :mod:`gleplot.sources`).
        preview_decimation : DecimationPolicy, optional
            Preview-only ``deresolve`` factor (SPEC §6.1/§10.7). ``None``
            (the default) emits byte-identically to a build before this
            option existed. A single ``int`` applies one factor to every
            eligible series (unchanged, byte-for-byte, since G7); a
            ``Mapping`` keyed by series label or a per-series
            ``Callable[[DecimationCandidate], Optional[int]]`` instead let a
            mixed figure (e.g. a 1k-point curve alongside a 500k-point
            trace) give each series its own factor -- see
            :data:`gleplot.writer.DecimationPolicy` for the full contract.
            When a resolved factor is given and > 1, large line/scatter
            series (see :attr:`gleplot.writer.GLEWriter.MIN_DERESOLVE_POINTS`)
            get a `` deresolve N`` clause on their ``dN`` line -- GLE then
            draws (and this call's caller may hit-test against) 1-in-N
            points instead of the full series, while axis autoscale is still
            computed from the full, undecimated data. A generation-time
            argument only: never stored on the figure, so ``to_dict``/
            ``from_dict`` and a *saved* ``.gle`` are unaffected -- pass it
            only when writing a throwaway preview copy, never the document
            being saved. See :attr:`preview_decimation_report` for what got
            decimated.
        folder : bool, optional
            If True, place the ``.gle`` script and generated data files
            in a sibling ``<name>.gleplot`` directory.
        **kwargs
            Any other keyword warns and is ignored.

        Returns
        -------
        Path
            Path to created GLE file
        """
        output_path, export_dir = self._resolve_export_paths(
            filepath,
            folder=kwargs.pop("folder", False),
        )
        warn_unsupported_keywords("savefig_gle", kwargs)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate and save GLE content with data files
        gle_content, data_content = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )

        # Write script
        output_path.write_text(gle_content, encoding="utf-8")

        # Write data files in same directory
        for filename, content in data_content.items():
            data_file = export_dir / filename
            data_file.write_text(content, encoding="utf-8")

        return output_path

    def savefig(
        self,
        filepath: str,
        format: Optional[str] = None,
        dpi: Optional[int] = None,
        data_provider=None,
        cairo: Optional[bool] = None,
        keep_intermediates: bool = False,
        preview_decimation: Optional[DecimationPolicy] = None,
        *,
        transparent: Optional[bool] = None,
        grayscale: bool = False,
        **kwargs,
    ) -> Path:
        """
        Save figure as GLE script and/or compiled output.

        Parameters
        ----------
        filepath : str
            Output file path
        format : {'pdf', 'png', 'eps', 'jpg', 'svg'}, optional
            Output format. If None, the format is auto-detected from the
            file suffix (``.jpeg`` maps to ``jpg``); an unrecognized or
            missing suffix defaults to saving the ``.gle`` script only.
            If format is given but the file extension differs, format wins.
            SVG raises ``ValueError`` for a figure whose style has
            ``usetex=True``: GLE cannot put LaTeX labels in SVG.
        dpi : int, optional
            DPI for raster formats
        cairo : bool, optional
            Whether to compile with GLE's ``-cairo`` device flag (SPEC
            §6.1/§10.6). ``None`` (the default) auto-detects via
            :meth:`requires_cairo` -- on for any figure using semi-
            transparency, off otherwise, so an ordinary opaque figure's
            compile behaviour (and its written ``.gle`` text -- the flag is
            compile-time only, never script-time) is completely unchanged.
            Pass ``True``/``False`` to force the flag either way. Ignored
            when ``format`` is ``'gle'`` (no compile happens). An ``'svg'``
            is always compiled with the flag, and ``False`` warns: GLE draws
            SVG through Cairo anyway, and without the flag it leaves out text
            in a PostScript font.

            When Cairo ends up active (auto, forced or SVG) and this figure's
            configured font (:attr:`style`'s ``font``) is not one of GLE's
            Cairo-safe fonts, a :class:`UserWarning` naming why Cairo is on
            (the figure's semi-transparent colours, ``cairo=True`` or SVG
            output) is raised: GLE itself substitutes a Cairo-safe font in
            that case (see :mod:`gleplot.cairo_support`), and SPEC's "no
            silent drops" rule means that substitution must never happen
            without gleplot saying so.
        data_provider : DataProvider, optional
            Supplies the tables that ``ColumnRef``/``GridRef`` series
            reference (:mod:`gleplot.sources`). Injected **here**, at write
            time, rather than held on the figure: the figure is a
            serializable document that ``to_dict`` round-trips and the
            provider is a live application object, so binding the two would
            make snapshots either lossy or impossible -- and passing it per
            write is what lets one figure be rendered against different
            tables (a preview vs an export, a what-if dataset). Figures whose
            series are all inline (everything the scripting API builds)
            ignore it entirely.

            References that cannot be resolved do not raise: the affected
            series is skipped and recorded in :attr:`source_warnings`.
        keep_intermediates : bool, optional
            If True, skip the post-compile cleanup of GLE-generated contour/
            ``fitz`` intermediates (``-cdata.dat``/``-clabels.dat``/
            ``-cvalues.dat``, and a points-sourced heatmap/contour's
            generated ``.z``) and of GLE's ``.gle/`` LaTeX cache entries
            that a compiled export otherwise removes from ``export_dir``
            afterwards -- see the "Engine intermediates" note below.
            Default False. Has no effect when ``format == 'gle'`` (no
            compile runs, so nothing was generated to clean up).
        preview_decimation : DecimationPolicy, optional
            Preview-only ``deresolve`` factor -- see :meth:`savefig_gle` for
            the full contract. Generation-time only, never stored on the
            figure. Compiling with this set still produces a real
            ``format`` output (PDF/PNG/...), just from a decimated preview
            script -- pass it for a live-preview compile, not for a save the
            user will treat as their document.
        transparent : bool, optional
            Give a PNG an alpha channel instead of a white background (GLE's
            ``-transparent``). ``None`` means ``False``. PDF, EPS and SVG
            output has no background to remove. ``True`` warns for a JPEG,
            which has no alpha channel, and for a grayscale PNG compiled
            without Cairo, which loses it.
        grayscale : bool, optional
            gleplot keyword, not a matplotlib one: compile with the colours
            GLE draws converted to their grey level (GLE's ``-nocolor``). A
            heatmap's image stays in colour in PDF, EPS and SVG, so ``True``
            warns there for a figure with a heatmap.

            ``transparent`` and ``grayscale`` act when GLE compiles, so they
            warn when only the ``.gle`` script is saved.
        folder : bool, optional
            If True, place the exported file, the intermediate ``.gle``
            script, and generated data files in a sibling
            ``<name>.gleplot`` directory.
        **kwargs
            Additional arguments. matplotlib's ``bbox_inches``,
            ``pad_inches``, ``facecolor`` and ``edgecolor`` are accepted and
            warn: the page is always ``figsize``, and its background is not
            settable. Any other keyword (``metadata``, ``orientation``, a
            misspelt one, ...) warns and is ignored.

        Returns
        -------
        Path
            Path to output file (GLE script or compiled output)

        Notes
        -----
        **Engine intermediates (GLEstudio SPEC 9.1/10.8).** Compiling a
        figure with a contour or a points-sourced (``fitz``) heatmap/contour
        makes the ``gle`` binary itself write extra files into ``export_dir``
        as an undocumented side effect -- ``<stem>-cdata.dat``,
        ``<stem>-clabels.dat``, ``<stem>-cvalues.dat``, and (points-sourced
        only) the generated ``<stem>.z``. These are never gleplot's own
        output, so on a successful compile (``format != 'gle'``) they are
        deleted from ``export_dir`` afterwards by exact name -- never by
        glob or prefix match, so a user's own file can only be caught if its
        name is a byte-for-byte match to one GLE itself would have written
        for *this* figure (see
        :func:`gleplot.compiler.remove_generated_intermediates`). Pass
        ``keep_intermediates=True`` to leave them in place, e.g. to inspect
        a contour's raw crossings while debugging. A failed compile raises
        before cleanup runs, so its intermediates (if any were written) are
        never removed -- they may help diagnose the failure.

        **LaTeX cache.** A figure GLE renders through LaTeX (:meth:`tex`,
        or ``GLEStyleConfig(usetex=True)``) makes GLE write a ``.gle/``
        cache directory into ``export_dir``. A successful compile removes
        this script's folder in it and any ``texpreamble.*`` files the
        compile created, then the directory if it is empty. Preamble files
        are left if they were already there, or if another figure's folder
        is in the cache, since other figures in the same directory share
        them. Two first-time compiles started together in one directory can
        still remove a preamble the other is using; give such parallel
        saves separate directories. ``keep_intermediates=True`` keeps the
        cache.
        """
        # matplotlib keywords with no GLE counterpart, and their defaults.
        for name, default in (
            ("bbox_inches", None),
            ("pad_inches", None),
            ("facecolor", "auto"),
            ("edgecolor", "auto"),
        ):
            value = kwargs.pop(name, default)
            if value is not None and not (isinstance(value, str) and value == default):
                warn_external(
                    f"savefig({name}=...) has no effect: GLE's page is the "
                    "figure's figsize, with a white background in PNG and JPEG "
                    "and none in PDF, EPS and SVG. Set the page size with "
                    "figsize, and pass transparent=True for a PNG without a "
                    "background."
                )
        output_path, export_dir = self._resolve_export_paths(
            filepath,
            folder=kwargs.pop("folder", False),
        )
        warn_unsupported_keywords("savefig", kwargs)

        # Determine output format from the file suffix. Driven by
        # SUFFIX_TO_COMPILE_FORMAT (shared with GLECompiler) so this can't
        # silently drift out of sync with what the compiler supports.
        # Unknown/missing suffixes (including '.gle') default to 'gle'.
        if format is None:
            format = SUFFIX_TO_COMPILE_FORMAT.get(output_path.suffix.lower(), "gle")
        if self.style.usetex and format.lower() == "svg":
            # GLE fails with "LaTeX expressions not supported in '.svg'".
            raise ValueError(
                f"savefig({str(filepath)!r}) cannot write SVG for a figure with "
                "style usetex=True: GLE typesets LaTeX labels only in PDF, EPS, "
                "PNG and JPG output. Save to one of those, or set "
                "fig.style.usetex = False before adding labels."
            )
        export_dir.mkdir(parents=True, exist_ok=True)

        # Write GLE script and data files
        base_path = output_path.with_suffix(".gle")
        gle_content, data_files = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )
        base_path.write_text(gle_content, encoding="utf-8")

        # Write data files in same directory
        for filename, content in data_files.items():
            data_file = export_dir / filename
            data_file.write_text(content, encoding="utf-8")

        if format == "gle":
            for name, value in (("transparent", transparent), ("grayscale", grayscale)):
                if value:
                    warn_external(
                        f"savefig({name}=True) has no effect when only the .gle "
                        "script is saved; it applies when GLE compiles, e.g. to "
                        "a .png or .pdf file name."
                    )
        elif grayscale and format.lower() not in RASTER_COMPILE_FORMATS:
            # GLE's -nocolor greys drawn colours; a colormap image is greyed
            # only when GLE rasterises the whole page.
            if any(ax.heatmaps for ax in self.axes_list):
                warn_external(
                    "savefig(grayscale=True) leaves heatmap images in colour in "
                    f"{format.upper()} output; save as PNG or JPEG, or draw the "
                    "heatmap with cmap='gray'."
                )

        # Compile if needed
        if format != "gle":
            if not self.compiler:
                raise RuntimeError(
                    "GLE compiler not available. "
                    "Install GLE or use savefig_gle() to save script only."
                )

            # SVG is always compiled with -cairo (build_compile_args).
            svg = format.lower() == "svg"
            if svg and cairo is False:
                warn_external(
                    "cairo=False has no effect on an SVG: GLE draws SVG with "
                    "its Cairo device, and gleplot passes -cairo so text in a "
                    "PostScript font is drawn. Save as PDF or EPS to compile "
                    "without Cairo."
                )
            effective_cairo = svg or (self.requires_cairo() if cairo is None else cairo)
            if svg:
                why = "SVG output is drawn by GLE's Cairo device"
            elif cairo is None:
                why = "figure requires Cairo for its semi-transparent colours"
            else:
                why = "cairo=True was requested"
            # GLE's Cairo device draws nothing for the 'postscript' command.
            if effective_cairo and any(
                image_sub_name(image["file"]) == "gleplot_postscript"
                for ax in self.axes_list
                for image in ax.images
                if is_visible(image)
            ):
                reason = "in SVG output" if svg else f"with GLE's Cairo device ({why})"
                warn_external(
                    f"image(...) EPS files are not drawn {reason}; convert the "
                    "image to PNG, or save as PDF, EPS or PNG without Cairo."
                )
            # Under usetex LaTeX draws every label, so no GLE font is used.
            if effective_cairo and not self.style.usetex:
                # Only titles that are written: one with no text, or an x/y
                # title hidden by shared axes, puts no font in the script.
                title_fonts = [
                    getattr(ax, f"{name}_font")
                    for ax in self.axes_list
                    for name, shown in (
                        ("title", True),
                        ("xlabel", ax._show_xlabel),
                        ("ylabel", ax._show_ylabel),
                        ("y2label", True),
                        ("x2label", True),
                    )
                    if shown
                    and getattr(ax, f"{name}_font")
                    and getattr(ax, f"{name}_text")
                ]
                for font in dict.fromkeys([self.style.font, *title_fonts]):
                    warning = cairo_font_warning(font)
                    if warning:
                        warn_external(f"{warning} ({why}).")

            output_dpi = dpi or self.dpi
            tex_cache = export_dir / ".gle"
            try:
                tex_cache_before = {p.name for p in tex_cache.iterdir()}
            except OSError:
                tex_cache_before = set()
            self.compiler.compile(
                str(base_path),
                cast(CompileFormat, format),
                dpi=output_dpi,
                cairo=effective_cairo,
                transparent=bool(transparent),
                grayscale=grayscale,
            )

            # Post-compile cleanup (G8): only on a *successful* compile --
            # compile() raises before this line otherwise -- and only for
            # this figure's own known contour/fitz stems (never a glob).
            if not keep_intermediates:
                remove_generated_intermediates(
                    export_dir, self._engine_intermediate_filenames()
                )
                _remove_tex_cache(tex_cache, base_path.stem, tex_cache_before)

            return output_path.with_suffix(f".{format}")

        return base_path

    @staticmethod
    def _resolve_export_paths(filepath: str, folder: bool = False) -> Tuple[Path, Path]:
        """Resolve output and export directory paths for save operations."""
        output_path = Path(filepath)
        export_dir = output_path.parent

        if folder:
            export_dir = output_path.parent / f"{output_path.stem}.gleplot"
            output_path = export_dir / output_path.name

        return output_path, export_dir

    def _generate_gle(
        self, data_provider=None, preview_decimation: Optional[DecimationPolicy] = None
    ) -> str:
        """Generate complete GLE script content."""
        content, _ = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )
        return content

    def _build_metadata_dict(self, data_files: dict, raw_sidecars=None) -> dict:
        """Assemble the ``! gleplot:`` metadata payload for this save.

        Parameters
        ----------
        data_files : dict
            The ``{filename: content}`` mapping the writer produced for this
            save -- i.e. every data sidecar the figure itself generated.
            Series added via ``*_from_file`` reference external files and
            never appear here, so they are correctly excluded from
            ``import-data``.

        Returns
        -------
        dict
            Suitable for :func:`gleplot.parser.metadata.emit_metadata`. Always
            includes ``dpi`` and ``import-data`` (per that function's
            ALWAYS_EMIT contract); ``sharex``/``sharey``/``msize_scale`` are
            included too but only rendered by ``emit_metadata`` when they
            differ from the documented defaults. Any ``metadata_extra`` keys
            recovered from a parsed file are passed through verbatim.
        """
        raw = set(raw_sidecars or ())
        data = {
            "dpi": self.dpi,
            "sharex": self.sharex,
            "sharey": self.sharey,
            "msize_scale": self.marker_config.msize_scale,
            # Raw-content sidecars (heatmap/contour ``.z`` grids, scattered
            # ``points.dat`` triples) are not columnar imports and must not be
            # vouched for as such -- excluded from ``import-data``.
            "import-data": sorted(k for k in data_files.keys() if k not in raw),
        }
        # Which graphs are add_axes insets, so open_gle need not guess.
        insets = [i + 1 for i, ax in enumerate(self.axes_list) if ax.position is None]
        if insets:
            data["insets"] = insets
        data.update(self.metadata_extra)
        return data

    def _generate_gle_with_files(
        self, data_provider=None, preview_decimation: Optional[DecimationPolicy] = None
    ) -> tuple:
        """
        Generate complete GLE script content with data files.

        Supports both single-plot and multi-subplot layouts.
        For a single axes (1,1,1), generates a simple graph block.
        For multiple axes, positions each graph using ``amove`` and
        explicit ``size`` commands based on the subplot grid.

        Uses figure's configured style, graph, and marker settings.

        Every series' data goes through ONE path: the source-resolution pass
        (:func:`gleplot.writer.resolve_figure`) runs first and hands the rest
        of this method an array-bearing series whether the numbers were baked
        in at ``plot()`` time or pulled from ``data_provider``'s tables.
        Series whose reference is dangling are skipped -- absent from
        autoscaling, the legend and the script -- and recorded in
        :attr:`source_warnings`; a figure in which every series is dangling
        still produces a valid ``.gle``. Hidden series (``visible = False``,
        SPEC 14.6) are skipped the same way and for the same distance, but
        silently: the user asked for it, so it is not a warning.

        Parameters
        ----------
        data_provider : DataProvider, optional
            See :meth:`savefig`.
        preview_decimation : DecimationPolicy, optional
            See :meth:`savefig_gle`. Forwarded to :class:`~gleplot.writer.GLEWriter`
            as a constructor argument only -- never read off ``self`` -- so
            this stays a pure function of its arguments plus the figure's
            already-serializable state.

        Returns
        -------
        tuple
            (gle_content, data_files_dict)
        """
        # Pass configuration to writer
        writer = GLEWriter(
            self.figsize,
            self.dpi,
            style=self.style,
            graph=self.graph,
            marker=self.marker_config,
            preview_decimation=preview_decimation,
        )

        # Source resolution, before anything reads a series' numbers.
        resolution = resolve_figure(self, data_provider)
        self._source_warnings = list(resolution.warnings)
        # Reset alongside source_warnings: both are write-time output for
        # THIS generation, not document state (see preview_decimation_report).
        self._preview_decimation_report = []

        is_single = len(self.axes_list) <= 1

        # A figure with NO axes that carries passthrough (e.g. a graph the
        # recognizer swallowed into an opaque 'begin translate/scale' wrapper,
        # preserved wholesale as header+trailer) must not fabricate a spurious
        # empty 'begin graph ... end graph'. Emit only the passthrough. A
        # genuinely empty figure with no passthrough keeps the historical
        # default empty graph block (existing tests rely on it).
        no_fabricate = not self.axes_list and (
            self.passthrough_header
            or self.passthrough_trailer
            or self._drawings
            or self._suptitle is not None
            or self.texts
        )

        # Palette / colorbar / contour-label subs needed by any axes. Emitted
        # once, right after the preamble, before any graph uses them.
        sub_texts = self._collect_sub_texts(resolution)

        if is_single and no_fabricate:
            writer.add_preamble(
                include_graph_begin=False,
                passthrough_header=self.passthrough_header,
                passthrough_before_hei=self.passthrough_before_hei,
                page_box=self.page_box,
            )
            self._write_page_content(writer, resolution)
            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )
        elif is_single:
            # Single plot -- the 1x1 case of the grid geometry, emitted through
            # a simpler block sequence (no inter-subplot blank lines, no
            # shared-axis synchronization). 'begin graph' is emitted explicitly
            # (not by the preamble) so palette subs and the fitz/contour
            # pre-graph blocks can precede it.
            writer.add_preamble(
                include_graph_begin=False,
                passthrough_header=self.passthrough_header,
                passthrough_before_hei=self.passthrough_before_hei,
                page_box=self.page_box,
            )
            writer.add_sub_defs(sub_texts)
            rects, _cells = self._layout_rects(writer, resolution)

            if self.axes_list:
                ax = self.axes_list[0]
                self._resolve_axis_limits(ax, resolution)

                self._emit_pre_graph_blocks(writer, ax, resolution)
                # Explicit placement (SPEC 3.3, metadata v2): the frame rect is
                # realized as 'amove x y' + 'size w h' + 'scale 1 1'. This is
                # the DEFAULT emission -- a lone plot is the 1x1 case of the
                # grid geometry (_layout_rects), so its rect is deterministic
                # and invertible instead of being left to GLE's 'scale auto'
                # page fit. The two exceptions below keep their own geometry.
                frame = None
                if ax.geometry_passthrough:
                    # Unmodelled GLE geometry recovered from a parsed file:
                    # re-emitted verbatim, and any amove it had is preserved in
                    # passthrough_header, so nothing is fabricated in front.
                    _warn_aspect_without_rect(ax, _RAW_GEOMETRY)
                    writer.begin_graph()
                    writer.add_graph_geometry_passthrough(ax.geometry_passthrough)
                elif self.graph.scale_mode == "fullsize" and ax.position is not None:
                    # An explicit writer-level opt-out of gleplot's own layout:
                    # GLE fits the graph (labels included) to the whole page.
                    # There is no rect to emit, so no amove either. An inset
                    # keeps the rect it was given.
                    _warn_aspect_without_rect(ax, _FULLSIZE)
                    writer.begin_graph()
                    writer.add_graph_size()
                else:
                    rect = _aspect_rect(
                        ax, ax.placement if ax.placement is not None else rects[0]
                    )
                    writer.add_amove(rect[0], rect[1])
                    writer.begin_graph()
                    writer.add_graph_size(
                        width_cm=rect[2], height_cm=rect[3], force_size=True
                    )
                    frame = (rect[2], rect[3])
                self._write_axes_content(writer, ax, resolution, frame)
                writer.end_graph(passthrough=ax.passthrough)
                self._emit_post_graph_calls(writer, ax, resolution)
            else:
                # No axes at all: there is nothing to place, so the historical
                # empty block stands. (A figure with passthrough took the
                # no-fabricate branch above; this is the truly empty figure.)
                writer.begin_graph()
                writer.add_graph_size()
                writer.end_graph()

            self._write_page_content(writer, resolution)
            if self.passthrough_trailer:
                writer.lines_gle.extend(self.passthrough_trailer)
        else:
            # Multi-subplot layout
            writer.add_preamble(
                include_graph_begin=False,
                passthrough_header=self.passthrough_header,
                passthrough_before_hei=self.passthrough_before_hei,
                page_box=self.page_box,
            )
            writer.add_sub_defs(sub_texts)

            # Resolve each panel's limits from its own data first, then let
            # sharing unify them. Doing it in this order means a shared LOG
            # axis is unified over ranges that are already positive, so the
            # union is positive too -- sanitizing after the unification would
            # instead give each panel its own repaired range and quietly break
            # the sharing.
            for ax in self.axes_list:
                self._resolve_axis_limits(ax, resolution)

            if self.sharex:
                self._synchronize_x_limits(resolution)
            if self.sharey:
                self._synchronize_y_limits(resolution)

            # Per-axes frame rectangles in cm, from the one geometry routine
            # (see _layout_rects). Default margins/spacing are heuristic but
            # can be overridden via subplots_adjust(left=..., right=...,
            # top=..., bottom=..., wspace=..., hspace=...).
            rects, cells = self._layout_rects(writer, resolution)

            for ax, rect, cell in zip(self.axes_list, rects, cells):
                # An explicit placement rect (SPEC 3.3) overrides the computed
                # grid cell: the rect IS the model, the grid is only a helper
                # that computes rects. Figures built through the scripting API
                # carry none and use the computed cell; a figure parsed back
                # from GLE carries the rect recovered from its own
                # amove/size/scale-1-1 triple, which is what makes a
                # subplots_adjust layout survive the round trip.
                x_pos, y_pos, graph_w, cell_h = _aspect_rect(
                    ax, ax.placement if ax.placement is not None else rect
                )

                self._emit_pre_graph_blocks(writer, ax, resolution)
                writer.add_amove(x_pos, y_pos)
                writer.begin_graph()
                frame = None
                if ax.geometry_passthrough:
                    writer.add_graph_geometry_passthrough(ax.geometry_passthrough)
                else:
                    writer.add_graph_size(
                        width_cm=graph_w, height_cm=cell_h, force_size=True
                    )
                    frame = (graph_w, cell_h)

                self._write_axes_content(writer, ax, resolution, frame)

                writer.end_graph(passthrough=ax.passthrough)
                self._emit_post_graph_calls(writer, ax, resolution)
                if ax._break_owner is not None:
                    self._emit_break_decoration(writer, ax._break_owner, ax, cell)
                writer.lines_gle.append("")  # Blank line between subplots

            self._write_page_content(writer, resolution)
            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )

        # Provider-table sidecars are only complete once every series that
        # references them has been emitted; render them now, before the
        # metadata block vouches for the figure's data files.
        writer.finalize_shared_sidecars()
        resolution.emit_warnings()

        # The graphutil.gle include, likewise: which guides were drawn
        # against GLE's own range is only settled once every graph block has
        # been written. Spliced before the metadata block so the metadata's
        # fixed index-2 insertion point is unaffected.
        writer.finalize_includes()

        # Splice the metadata block in after the two header comment lines
        # ('! GLE graphics file' / '! Generated by gleplot') and before the
        # 'size ...' line -- add_preamble always emits exactly those two
        # lines first, so index 2 is the fixed, stable insertion point.
        metadata_dict = self._build_metadata_dict(
            writer.data_files, writer.raw_sidecars
        )
        metadata_lines = _gle_metadata.emit_metadata(metadata_dict)
        if metadata_lines:
            writer.lines_gle[2:2] = metadata_lines

        self._preview_decimation_report = list(writer.decimation_report)
        return writer.get_gle_content(), writer.data_files

    # -- contour / heatmap helpers --------------------------------------

    def _engine_intermediate_filenames(self) -> "list[str]":
        """Exact basenames of GLE-generated intermediates this figure can produce.

        Used by :meth:`savefig` (G8, GLEstudio SPEC 9.1/10.8) to clean up
        after a compile. Computed purely from the object model -- every
        heatmap/contour on every axes, *not* filtered through a write's
        ``SourceResolution`` -- so a name reserved for a series that is
        dangling on this particular write (and therefore did not get a fresh
        ``begin contour``/``fitz`` block emitted) is still recognized as
        belonging to this figure if a stale file under that name is lying
        around from an earlier, successful compile.

        Two kinds of engine-generated file, mirroring :func:`gcontour.cpp`/
        :func:`fit.cpp` in GLE itself (see
        :func:`gleplot.compiler.remove_generated_intermediates`):

        - Every contour (grid- or points-sourced) can produce
          ``<stem>-cdata.dat``, ``<stem>-clabels.dat`` and
          ``<stem>-cvalues.dat``, where ``<stem>`` is ``_grid_z_file``
          with its ``.z`` extension stripped.
        - A points-sourced (``fitz``) heatmap or contour additionally
          produces the gridded ``<points-stem>.z`` file itself -- that ``.z``
          is GLE's *output*, distinct from the raw ``<points-stem>.dat``
          points sidecar gleplot wrote as ``fitz``'s input (kept: it is
          gleplot's own file, needed to recompile, not an engine byproduct).
          A grid-sourced heatmap/contour's ``.z`` is likewise gleplot's own
          written sidecar, not GLE-generated, and is never included here.
        """
        names: "list[str]" = []
        for ax in self.axes_list:
            for ct in ax.contours:
                z_file = _grid_z_file(ct)
                stem = z_file[:-2] if z_file.endswith(".z") else z_file
                names.append(f"{stem}-cdata.dat")
                names.append(f"{stem}-clabels.dat")
                names.append(f"{stem}-cvalues.dat")
                if ct.get("source") == "points":
                    names.append(z_file)  # the fitz-generated .z itself
            for hm in ax.heatmaps:
                if hm.get("source") == "points":
                    names.append(_grid_z_file(hm))
        return names

    # -- colorbar layout reservation ------------------------------------
    #
    # A colorbar is drawn AFTER the graph, outside the frame rectangle: a
    # vertical one at ``xg(xgmax)+sep``, a horizontal one with its top edge at
    # ``yg(ygmin)-sep``. The room computed here widens the layout's right or
    # bottom margin, or the grid gap after the bar's column or row
    # (:meth:`_colorbar_gaps_cm`), so the bar + ticks + label are neither
    # clipped off the page nor drawn over a neighbour. It is derived purely
    # from the colorbar dict (which the recognizer recovers verbatim), so it
    # recomputes identically on a writer -> recognizer -> writer round trip --
    # though since metadata v2 the emitted rect is also read straight back, so
    # the round trip no longer depends on the re-derivation matching.

    #: Smallest tick-label text height (cm) the reserved colorbar margin is
    #: sized for; the figure's own font size is used when it is larger, as
    #: ``color.gle`` writes the numbers in it.
    _CBAR_TEXT_HEI_CM = 0.42

    @staticmethod
    def _estimate_tick_chars(zmin, zmax, fmt) -> int:
        """Widest tick-number character count for a GLE ``fix N`` format.

        Deterministic estimate from the z-range and the ``format$`` string;
        used only to size the reserved colorbar margin (see
        :meth:`_colorbar_reserved_cm`).
        """
        decimals = 1
        parts = str(fmt).strip().lower().split()
        if len(parts) == 2 and parts[0] == "fix":
            try:
                decimals = max(int(parts[1]), 0)
            except ValueError:
                decimals = 1

        def width_of(v) -> int:
            # An auto range (SPEC 14.5) has no number here until the write
            # that resolves it; the 3-character floor below then sizes the
            # margin. Reserving from a resolved bar is the normal path --
            # ``_axes_colorbar_reserved_cm`` reads the resolution's copy --
            # so this only covers callers that ask without one.
            if v is None:
                return 0
            v = float(v)
            n = len(f"{abs(v):.{decimals}f}")
            if v < 0:
                n += 1  # minus sign
            return n

        return max(width_of(zmin), width_of(zmax), 3)

    def _colorbar_reserved_cm(self, cb: dict) -> float:
        """Right-hand space (cm), measured from ``xgmax``, a vertical bar needs.

        Sized from how ``color.gle``'s ``color_range_vertical`` lays out:
        the ``sep`` gap, the bar (``width``), then the tick marks and numbers
        to its right (a tick a third of the width long, a gap as long again),
        then the rotated ``label`` (see
        :meth:`gleplot.writer.GLEWriter.colorbar_label_lines`).
        """
        wd = float(cb["width"])
        sep = float(cb["sep"])
        hei = max(self._CBAR_TEXT_HEI_CM, fontsize_pt_to_cm(self.style.fontsize))
        nchars = self._estimate_tick_chars(cb["zmin"], cb["zmax"], _cbar_format(cb))
        tick_extent = 2 * wd / 3.0 + nchars * 0.6 * hei
        if cb.get("label"):
            tick_extent += COLORBAR_LABEL_PAD + hei
        return sep + wd + tick_extent + 0.3  # + safety pad

    def _colorbar_h_reserved_cm(self, cb: dict) -> Tuple[float, float]:
        """``(right, below)`` space (cm) a horizontal bar needs.

        ``below`` is measured down from ``ygmin``, following ``color.gle``'s
        ``color_range_horizontal``: the ``sep`` gap, the bar (``width``), then
        the ticks and numbers (a tick a third of the width long, a gap as
        long again), then the ``label`` under them. ``right`` is how far the
        last number, centred on the
        bar's end, runs past ``xgmax``. The text is the figure's own ``hei``,
        which the routine writes in, so the room grows with the font.
        """
        wd = float(cb["width"])
        hei = max(self._CBAR_TEXT_HEI_CM, fontsize_pt_to_cm(self.style.fontsize))
        below = float(cb["sep"]) + wd + 2 * wd / 3.0 + hei
        if cb.get("label"):
            below += COLORBAR_LABEL_PAD + hei
        nchars = self._estimate_tick_chars(cb["zmin"], cb["zmax"], _cbar_format(cb))
        right = nchars * 0.6 * hei / 2.0 + 0.3
        return right, below + 0.3  # + safety pad

    def _axes_colorbar_reserved_cm(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ) -> Tuple[float, float]:
        """``(right, below)`` room (cm) an axes' colorbars need (0 if none).

        A heatmap skipped for a dangling reference draws no colorbar, so it
        reserves no room either.
        """
        resolution = resolution or SourceResolution()
        right = below = 0.0
        for hm in _colorbar_holders(ax, resolution):
            cb = hm.get("colorbar")
            if not cb:
                continue
            if cb.get("orientation") == "horizontal":
                h_right, h_below = self._colorbar_h_reserved_cm(cb)
                right = max(right, h_right)
                below = max(below, h_below)
            else:
                right = max(right, self._colorbar_reserved_cm(cb))
        return right, below

    def _collect_sub_texts(self, resolution: Optional[SourceResolution] = None):
        """Gather the palette/wedge/box/rug/polar/image subs.

        Returns the deterministic ordered list of sub-definition texts: used
        palette subs (a heatmap's or a per-point colour's) sorted by name,
        then the pie-wedge sub (if any wedge), then the box-plot subs (if any
        box), then the rug subs (if any rug has a tick), then one per-point marker-size sub per marker
        that a scatter with ``mdata`` uses, sorted by name, then one per-point
        colour sub per marker and colormap that a scatter with ``cdata`` uses,
        sorted, then the polar subs
        (if any polar axes), then the image subs (if any placed image).
        Skipped (dangling) series contribute nothing, so a write that drops
        the only heatmap does not leave an unused palette sub behind.

        The ``graphutil.gle`` include for guides (:mod:`gleplot.guides`) is
        NOT decided here: which guides are drawn after ``end graph`` depends
        on limits that are still unresolved at this point in the write. The
        writer records it as the calls are emitted and splices it in beside
        these subs afterwards -- see
        :meth:`gleplot.writer.GLEWriter.finalize_includes`.
        """
        resolution = resolution or SourceResolution()
        used_cmaps = set()
        for ax in self.axes_list:
            for hm in resolution.visible(ax.heatmaps):
                if _pal.cmap_needs_sub(hm["cmap"]) and "levels" not in hm:
                    used_cmaps.add(hm["cmap"])
            for hm in _colorbar_holders(ax, resolution):
                cb = hm.get("colorbar")
                if cb and hm.get("invert"):
                    # The reversed palette add_colorbar draws (colorbar_cmap).
                    bar_cmap = _pal.colorbar_cmap(hm["cmap"], True)
                    if _pal.cmap_needs_sub(bar_cmap):
                        used_cmaps.add(bar_cmap)

        coloured: Set[Tuple[str, str]] = set()
        for ax in self.axes_list:
            coloured |= _coloured_markers(ax, resolution)
        # A per-point colour and a contourf's band sub call their palette
        # sub, gray and rainbow included.
        point_cmaps = {cmap for _marker, cmap in coloured} | {
            hm["cmap"]
            for ax in self.axes_list
            for hm in resolution.visible(ax.heatmaps)
            if "levels" in hm
        }

        subs = []
        for cmap in sorted(used_cmaps | point_cmaps):
            if cmap in point_cmaps:
                subs.append(_pal.point_palette_sub_text(cmap))
                continue
            text = _pal.palette_sub_text(cmap)
            if text:
                subs.append(text)
        if any(resolution.visible(ax.wedges) for ax in self.axes_list):
            subs.append(WEDGE_SUB)
        if any(resolution.visible(ax.boxes) for ax in self.axes_list):
            subs.append(BOX_SUB)
        sized_markers: Set[str] = set()
        for ax in self.axes_list:
            sized_markers.update(
                str(sc["marker"]).lower()
                for sc in resolution.visible(ax.scatters)
                if "mdata" in sc
            )
            # A dataset line kept as raw GLE may still name one of these
            # markers; the parser dropped its sub, so it is written again.
            for line in ax.passthrough:
                sized_markers.update(
                    name.lower()
                    for name in _MDATA_MARKER_RE.findall(line)
                    if name.upper() in MARKERS
                )
        subs.extend(mdata_sub_text(marker) for marker in sorted(sized_markers))
        subs.extend(cdata_sub_text(*pair) for pair in sorted(coloured))
        if any(ax._polar for ax in self.axes_list):
            subs.append(POLAR_SUB)
        used_images = {
            image_sub_name(image["file"])
            for ax in self.axes_list
            for image in resolution.visible(ax.images)
        }
        subs.extend(text for name, text in IMAGE_SUBS.items() if name in used_images)
        return subs

    def _write_page_content(
        self, writer: GLEWriter, resolution: SourceResolution
    ) -> None:
        """Everything drawn on the page after the axes, in a fixed order.

        The page drawings, then the suptitle and the figure texts, then the
        figure legend: the order the recognizer reads them back in.
        """
        for drawing in self._drawings:
            writer.add_page_drawing(drawing)
        if self._suptitle is not None:
            writer.add_figure_text(self._suptitle)
        for text in self.texts:
            writer.add_figure_text(text)
        if self._legend is not None:
            self._write_figure_legend(writer, resolution)

    def _write_figure_legend(
        self, writer: GLEWriter, resolution: SourceResolution
    ) -> None:
        """The ``Figure.legend`` key: every axes' entries in addition order.

        Each axes' entries are those its own key would list, so they are
        computed against the limits its graph was written with. A broken
        axis lists its series once, from its first segment. A broken y-axis
        routes ``axhline`` / ``axhspan`` to the segments they reach, so its
        other segments add the guides not already listed.
        """
        legend = cast(dict, self._legend)
        entries: List[tuple] = []
        for ax in self.axes_list:
            guides_only = False
            if ax._break_owner is not None and ax._break_index:
                if ax._break_owner.axis == "x":
                    continue
                guides_only = True
            limits = (ax.xmin, ax.xmax, ax.ymin, ax.ymax)
            found = self._legend_entries(writer, ax, resolution, limits)
            if guides_only:
                guides = {id(g) for g in (*ax.reflines, *ax.spans)}
                listed = {label for _series, label, _swatch in entries}
                found = [f for f in found if id(f[0]) in guides and f[1] not in listed]
            entries.extend(
                (resolution.data(series) or series, label, swatch)
                for series, label, swatch in (
                    found[i] for i in self._legend_addition_order(found)
                )
            )
        if not entries:
            warn_external(
                "Figure.legend(): no labelled series in any axes, so no legend "
                "was drawn. Pass label= when you plot a series.",
            )
            return
        key = KeyOptions(
            position=legend["loc"],
            fontsize=legend["fontsize"],
            frameon=legend["frameon"],
            background=legend["facecolor"],
            spacing=dict(legend["spacing"]),
            anchor=None if legend["anchor"] is None else tuple(legend["anchor"]),
            labelcolor=legend["labelcolor"],
        )
        breaks = legend_column_breaks(len(entries), legend["ncol"])
        writer.add_figure_legend(entries, breaks, key)

    def _emit_pre_graph_blocks(
        self, writer: GLEWriter, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Write sidecars + ``begin fitz``/``begin contour`` blocks for an axes.

        These execute before the graph reads the (generated) grid/contour
        files, so they are emitted immediately before the axes' ``begin graph``.
        """
        resolution = resolution or SourceResolution()
        for hm in resolution.visible(ax.heatmaps):
            writer.add_heatmap_data(hm)

        for ct in resolution.visible(ax.contours):
            writer.add_contour_data(ct)

    def _emit_post_graph_calls(
        self, writer: GLEWriter, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Write the post-graph colorbars and contour labels."""
        resolution = resolution or SourceResolution()
        for holder in _colorbar_holders(ax, resolution):
            writer.add_colorbar(holder)
        for ct in resolution.visible(ax.contours):
            writer.add_contour_labels(ct)

    def _legend_offset(self, ax: Axes) -> Optional[Tuple[float, float]]:
        """This axes' legend offset in cm, or the figure-wide default.

        ``Axes.legend_offset`` is None until ``legend(offset=...)`` sets it;
        the figure's :class:`~gleplot.config.GLEGraphConfig` then supplies
        ``(legend_offset_x, legend_offset_y)``. Those default to ``(0, 0)``,
        which means "no offset" and is returned as None so no ``offset``
        clause is written at all.
        """
        offset: Optional[Tuple[float, float]] = getattr(ax, "legend_offset", None)
        if offset is not None:
            return offset
        default = (float(self.graph.legend_offset_x), float(self.graph.legend_offset_y))
        return None if default == (0.0, 0.0) else default

    def _legend_entries(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution, limits
    ) -> List[tuple]:
        """Labelled series in emission order, each with its key swatch.

        The order is the one ``_write_axes_content`` draws: engine-range
        spans, plain fills, dataset-form spans, engine-range reflines,
        dataset-form reflines, z-ordered bars/lines/scatters/errorbars,
        then file series, then derived curves. Hidden and dangling series
        are already dropped.
        An empty label is not an entry.

        The series object is the one that carries ``_draw_seq`` (call
        order) or ``legend_seq`` (recovered from a ``begin key``). A
        materialized guide is not that object: the declaration is.
        """
        entries: List[tuple] = []

        def add(series, swatch: str) -> None:
            label = series.get("label")
            if label:
                entries.append((series, label, swatch))

        for span in ax.engine_range_guides(ax.spans, limits):
            token = span.get("swatch_color") or apply_alpha(
                span["color"], span.get("alpha", 1.0)
            )
            add(span, writer.legend_swatch(span["color"], fill=token))
        for series, fill in resolution.pairs(ax.fills):
            token = fill.get("swatch_color") or apply_alpha(
                fill["color"], fill.get("alpha", 1.0)
            )
            add(series, writer.legend_swatch(fill["color"], fill=token))
        for span in ax.dataset_form_guides(ax.spans, limits):
            token = span.get("swatch_color") or apply_alpha(
                span["color"], span.get("alpha", 1.0)
            )
            add(span, writer.legend_swatch(span["color"], fill=token))
        for ref in ax.engine_range_guides(ax.reflines, limits):
            add(
                ref,
                writer.legend_swatch(ref["color"], ref.get("linestyle"), ref),
            )
        for ref in ax.dataset_form_guides(ax.reflines, limits):
            add(
                ref,
                writer.legend_swatch(ref["color"], ref.get("linestyle"), ref),
            )
        for kind, series, data in resolution.drawables(ax):
            add(series, self._drawable_legend_swatch(writer, kind, data))
        for fs in resolution.visible(ax.file_series):
            add(fs, self._file_legend_swatch(writer, fs))
        for series in resolution.visible(ax.derived_series):
            if self._derived_operands(ax, resolution, series) is not None:
                add(series, self._drawable_legend_swatch(writer, "line", series))
        return entries

    @staticmethod
    def _drawable_legend_swatch(writer: GLEWriter, kind: str, data) -> str:
        if kind == "bar":
            colors = data.get("colors") or ["RED"]
            token = data.get("swatch_color")
            if token:
                return writer.legend_swatch(colors[0], fill=token)
            return writer.legend_swatch(
                colors[0], fill=colors[0], pattern=data.get("pattern")
            )
        if kind == "hist" and data.get("histtype") == "stepfilled":
            token = data.get("color") or "BLUE"
            return writer.legend_swatch(token, fill=token)
        marker = data.get("marker")
        if kind == "scatter" and "cdata" in data:
            # The colour sub draws the swatch as the in-graph key does.
            marker = cdata_sub_name(str(marker), data["cmap"])
        return writer.legend_swatch(
            data.get("color") or "BLUE",
            None if kind == "scatter" else data.get("linestyle", "-"),
            data,
            marker,
            data.get("markersize"),
        )

    @staticmethod
    def _file_legend_swatch(writer: GLEWriter, fs) -> str:
        kind = fs.get("series_type", "errorbar")
        if kind in ("bar", "fill"):
            token = fs.get("swatch_color") or fs.get("color") or "RED"
            return writer.legend_swatch(fs.get("color") or token, fill=token)
        return writer.legend_swatch(
            fs.get("color") or "BLUE",
            (
                None
                if kind == "errorbar" and not fs.get("linestyle")
                else fs.get("linestyle", "-" if kind == "line" else "none")
            ),
            fs,
            fs.get("marker"),
            fs.get("markersize"),
        )

    @staticmethod
    def _legend_addition_order(entries: List[tuple]) -> List[int]:
        """Indices of ``entries`` in matplotlib addition order.

        ``legend_seq`` is the order recovered from a ``begin key``.
        ``_draw_seq`` is the order the artists were added. If either is
        missing on any entry, the emission order stands: that is what a
        script written before call-order was recorded still round-trips as.
        """
        series = [item[0] for item in entries]
        if series and all(s.get("legend_seq") is not None for s in series):
            keys = [int(s["legend_seq"]) for s in series]
        elif series and all(s.get("_draw_seq") is not None for s in series):
            keys = [int(s["_draw_seq"]) for s in series]
        else:
            return list(range(len(series)))
        return sorted(range(len(series)), key=lambda i: (keys[i], i))

    def _axis_style(self, ax: Axes, prefix: str) -> AxisStyle:
        """Collect one axis' styling off ``ax`` into a writer :class:`AxisStyle`.

        Flat model attributes (``xformat``, ``xgrid``, ``xlabel_size``, ...)
        in, one parameter object out, with the figure-wide
        :class:`~gleplot.config.GLEGraphConfig` distances applied where the
        axes sets none: ``xlabel_distance`` for the x title,
        ``ylabel_distance`` for the y AND y2 titles (GLE's ``ytitle``/
        ``y2title`` are the same decoration on opposite sides).

        Only x and y have a ``grid``: GLE's grid is the axis' own ticks
        stretched across the graph, so a y2 grid would duplicate the y one.
        """
        graph_cfg = self.graph
        dist_default = (
            graph_cfg.xlabel_distance
            if prefix in ("x", "x2")
            else graph_cfg.ylabel_distance
        )
        title_dist = getattr(ax, f"{prefix}label_dist")
        grid = getattr(ax, f"{prefix}grid", None) if prefix in ("x", "y") else None
        marks: Dict[str, Any] = {}
        if prefix in ("x", "y"):
            marks = {
                name: getattr(ax, f"{prefix}{name}")
                for name in _TICK_MARK_FIELDS
                if getattr(ax, f"{prefix}{name}") is not None
            }
        if grid is not None and marks:
            # GLE's grid lines are the ticks drawn across the graph, so the
            # grid's style is the ticks' style.
            warn_external(
                f"The {prefix} axis has a grid, which GLE draws in place of "
                "its tick marks, so its tick_params()/minorticks settings are "
                "not written. Style the grid lines with grid(color=..., "
                f"linewidth=...), or turn the {prefix} grid off.",
            )
            marks = {}
        loglabels = getattr(ax, f"{prefix}loglabels", None)
        if loglabels is not None and getattr(ax, f"{prefix}scale", None) != "log":
            warn_external(
                f"set_{prefix}ticks(loglabels={loglabels!r}) only changes a log "
                f"axis, and the {prefix} axis is linear. Call "
                f"set_{prefix}scale('log'), or leave loglabels out.",
            )
        return AxisStyle(
            fmt=getattr(ax, f"{prefix}format"),
            grid=grid,
            grid_lstyle=getattr(ax, f"{prefix}grid_lstyle", None),
            grid_lwidth=getattr(ax, f"{prefix}grid_lwidth", None),
            grid_color=getattr(ax, f"{prefix}grid_color", None),
            title_size=getattr(ax, f"{prefix}label_size"),
            title_color=getattr(ax, f"{prefix}label_color"),
            title_dist=title_dist if title_dist is not None else dist_default,
            label_size=getattr(ax, f"{prefix}ticklabel_size"),
            label_color=getattr(ax, f"{prefix}ticklabel_color"),
            label_angle=getattr(ax, f"{prefix}ticklabel_angle"),
            title_font=getattr(ax, f"{prefix}label_font"),
            side_color=getattr(ax, f"{prefix}side_color"),
            side_lwidth=getattr(ax, f"{prefix}side_lwidth"),
            # x2 and y2 are hidden whole, through Axes._x2axis_off/_y2axis_off.
            side_off=getattr(ax, f"{prefix}side_off") if prefix in "xy" else None,
            nticks=getattr(ax, f"{prefix}nticks", None),
            ftick=getattr(ax, f"{prefix}ftick", None),
            shift=getattr(ax, f"{prefix}shift", None),
            symticks=getattr(ax, f"{prefix}symticks", None),
            noticks=getattr(ax, f"{prefix}noticks", None),
            nsubticks=getattr(ax, f"{prefix}nsubticks", None),
            loglabels=loglabels,
            **marks,
        )

    def _write_axes_content(
        self,
        writer: GLEWriter,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        frame: Optional[Tuple[float, float]] = None,
    ):
        """
        Write all plot content for a single Axes into the current graph block.

        This method is shared between single-plot and multi-subplot paths.

        Every series list is walked through ``resolution``, so a series is
        seen here already carrying its numbers (inline or resolved from a
        provider table) or not seen at all (dangling reference, or hidden --
        SPEC 14.6).

        Parameters
        ----------
        writer : GLEWriter
            The GLE writer to append commands to.
        ax : Axes
            The axes whose content should be written.
        resolution : SourceResolution, optional
            The write's source resolution. Omitted (``None``) means "every
            series is inline", which is what a direct caller outside
            :meth:`_generate_gle_with_files` gets.
        frame : (float, float), optional
            The graph's frame width and height in cm, when gleplot places it.
            A polar axes fits its window to it.

        Notes
        -----
        The axis setup comes first. The content phases then run in drawing
        order, back to front: heatmaps, contours and placed images, then the
        background guides and fills, then the z-ordered data series, file
        series, derived curves, box plots, rugs, pie wedges and texts, and the key
        last. :meth:`_prepare_legend` runs before any series is written,
        because the key's column breaks must be set on the writer before the
        datasets they fall between.
        """
        resolution = resolution or SourceResolution()
        writer.reserve_datasets(ax.passthrough)
        self._write_axis_setup(writer, ax, frame, resolution)
        self._warn_data_range_edges(ax, resolution)
        self._write_heatmaps(writer, ax, resolution)
        self._write_contours(writer, ax, resolution)
        for image in resolution.visible(ax.images):
            writer.add_image(image)
        limits = (ax.xmin, ax.xmax, ax.ymin, ax.ymax)
        legend = self._prepare_legend(writer, ax, resolution, limits)
        self._write_spans(writer, ax, limits)
        self._write_fills(writer, ax, resolution, limits)
        self._write_reflines(writer, ax, limits)
        self._write_drawables(writer, ax, resolution)
        self._write_file_series(writer, ax, resolution)
        self._write_derived(writer, ax, resolution)
        for box in resolution.visible(ax.boxes):
            writer.add_box(box)
        for rug in resolution.visible(ax.rugs):
            writer.add_rug(rug)
        for wedge in resolution.visible(ax.wedges):
            writer.add_wedge(wedge)
        self._write_texts(writer, ax)
        self._write_legend(writer, ax, legend, resolution)

    def _write_axis_setup(
        self,
        writer: GLEWriter,
        ax: Axes,
        frame: Optional[Tuple[float, float]],
        resolution: SourceResolution,
    ) -> None:
        """Titles, scales, ranges, ticks and grid of the graph block.

        A polar axes' ranges are the window :func:`~gleplot.writer.polar_window`
        fits to ``frame``, and its grid is the polar one. A linear axis
        missing a limit hands the writer its data extent, which sets how
        precisely the coordinates on it are written.
        """
        xmin, xmax, ymin, ymax = ax.xmin, ax.xmax, ax.ymin, ax.ymax
        # Set by _resolve_axis_limits on every polar axes. Rounded as the
        # script writes it, so a parsed figure derives the same window.
        rmax = (
            float(GLEWriter._format_number(ax.ymax))
            if ax._polar and ax.ymax is not None
            else None
        )
        data_extents = {}
        if rmax is not None:
            xr, yr = polar_window(rmax, frame, fontsize_pt_to_cm(self.style.fontsize))
            xmin, xmax, ymin, ymax = -xr, xr, -yr, yr
        else:
            scans = {
                "x": self._get_data_xlim,
                "y": self._get_data_ylim,
                "y2": self._get_data_y2lim,
                "x2": self._get_data_x2lim,
            }
            has_data = {
                "x": True,
                "y": True,
                "y2": ax.has_y2_plots(),
                "x2": ax.has_x2_plots(),
            }
            data_extents = {
                which: scan(ax, resolution)
                for which, scan in scans.items()
                if has_data[which]
                and None in self._axis_limits(ax, which)
                and getattr(ax, f"{which}scale") != "log"
            }
        if ax.math_mode:
            for name, other, scale, lo, hi in (
                ("x", "y", ax.xscale, ax.xmin, ax.xmax),
                ("y", "x", ax.yscale, ax.ymin, ax.ymax),
            ):
                if scale == "log":
                    warn_external(
                        f"set_math_mode() draws the axes through 0, which a log "
                        f"{name} axis does not contain, so GLE cannot draw this "
                        f"figure. Use a linear {name} scale, or call "
                        "set_math_mode(False)."
                    )
                elif (
                    lo is not None
                    and hi is not None
                    and not min(lo, hi) <= 0 <= max(lo, hi)
                ):
                    warn_external(
                        f"set_math_mode() draws the {other} axis at {name} = 0, "
                        f"which is outside the {name} limits ({lo:g}, {hi:g}), "
                        f"so that axis is not shown. Include 0 with "
                        f"set_{name}lim, or call set_math_mode(False)."
                    )
            writer.add_math_mode()
        for name, side in (("x2", "top"), ("y2", "right")):
            if not getattr(ax, f"_{name}axis_off") or ax._break_owner is not None:
                continue
            in_use = (
                any(
                    s.get(f"{name[0]}axis") == name
                    for s in (
                        *ax.lines,
                        *ax.scatters,
                        *ax.errorbars,
                        *ax.hists,
                        *ax.file_series,
                    )
                )
                or getattr(ax, f"{name}min") is not None
                or getattr(ax, f"{name}max") is not None
                or getattr(ax, f"{name}scale") == "log"
                or bool(getattr(ax, f"{name}label_text"))
                or getattr(ax, f"{name}format") is not None
                or any(
                    getattr(ax, f"{name}ticklabel_{prop}") is not None
                    for prop in ("size", "color", "angle")
                )
            )
            if in_use:
                warn_external(
                    f"set_axis_line({name!r}, visible=False) hides the {side} "
                    f"edge, and with it the {name} scale drawn there: its "
                    "ticks, tick labels and axis label. Call "
                    f"set_axis_line({name!r}, visible=True) to keep the scale."
                )
        writer.add_axes(
            xlabel=ax.xlabel_text or None,
            ylabel=ax.ylabel_text or None,
            y2label=ax.y2label_text or None,
            x2label=ax.x2label_text or None,
            title=ax.title_text or None,
            xlog=(ax.xscale == "log"),
            ylog=(ax.yscale == "log"),
            y2log=(ax.y2scale == "log"),
            x2log=(ax.x2scale == "log"),
            xmin=xmin,
            xmax=xmax,
            ymin=ymin,
            ymax=ymax,
            y2min=ax.y2min,
            y2max=ax.y2max,
            x2min=ax.x2min,
            x2max=ax.x2max,
            show_xlabel=ax._show_xlabel,
            show_ylabel=ax._show_ylabel,
            show_xticks=ax._show_xticks,
            show_yticks=ax._show_yticks,
            remove_last_xtick=getattr(ax, "_remove_last_xtick", False),
            remove_last_ytick=getattr(ax, "_remove_last_ytick", False),
            remove_first_xtick=getattr(ax, "_remove_first_xtick", False),
            remove_first_ytick=getattr(ax, "_remove_first_ytick", False),
            xdticks=ax.xdticks,
            ydticks=ax.ydticks,
            xdsubticks=ax.xdsubticks,
            ydsubticks=ax.ydsubticks,
            xplaces=ax.xplaces,
            yplaces=ax.yplaces,
            xnames=ax.xnames,
            ynames=ax.ynames,
            xaxis_off=ax._xaxis_off,
            yaxis_off=ax._yaxis_off,
            x2axis_off=ax._x2axis_off,
            y2axis_off=ax._y2axis_off,
            frame_off=ax._frame_off,
            xstyle=self._axis_style(ax, "x"),
            ystyle=self._axis_style(ax, "y"),
            y2style=self._axis_style(ax, "y2"),
            x2style=self._axis_style(ax, "x2"),
            x2_series=ax.has_x2_plots(),
            y2_series=ax.has_y2_plots(),
            title_size=ax.title_size,
            title_color=ax.title_color,
            title_dist=(
                ax.title_dist
                if ax.title_dist is not None
                else self.graph.title_distance
            ),
            title_font=ax.title_font,
            data_extents=data_extents,
        )
        if ax._facecolor is not None and not ax._frame_off:
            writer.add_background(ax._facecolor)
        if rmax is not None:
            writer.add_polar_frame(rmax)

    def _write_heatmaps(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution
    ) -> None:
        """Heatmap colormaps, drawn behind everything as the background."""
        for hm in resolution.visible(ax.heatmaps):
            if hm.get("cells"):
                self._warn_mesh_overhang(ax, hm)
            elif hm["source"] == "points" or GLEWriter.writes_node_grid(hm):
                self._warn_node_grid_overhang(ax, hm)
            writer.add_heatmap(hm)

    @staticmethod
    def _warn_data_range_edges(ax: Axes, resolution: SourceResolution) -> None:
        """Warn where a series' data range (``xmin`` ... ``ymax``) draws nothing.

        GLE takes a missing edge from the limit of the series' axis, so an
        edge given alone at or beyond the far limit leaves an empty range,
        and GLE stops with "invalid range". On a log axis an edge at or
        below zero hides the series. Only limits the script writes can be
        checked; ones left to GLE are not known here.
        """
        for series in resolution.visible(
            [*ax.lines, *ax.scatters, *ax.errorbars, *ax.file_series]
        ):
            for dim in ("x", "y"):
                lo, hi = series.get(f"{dim}min"), series.get(f"{dim}max")
                if lo is None and hi is None:
                    continue
                axis = series.get(f"{dim}axis") or dim
                name = (
                    f"series {series['label']!r}" if series.get("label") else "a series"
                )
                if getattr(ax, f"{axis}scale") == "log":
                    bad = [v for v in (lo, hi) if v is not None and v <= 0]
                    if bad:
                        warn_external(
                            f"The data range of {name} has {dim} edge {bad[0]:g} "
                            f"on the log {axis} axis, so GLE draws nothing of "
                            "it. Give positive edges."
                        )
                        continue
                limits = (getattr(ax, f"{axis}min"), getattr(ax, f"{axis}max"))
                if None in limits:
                    continue
                low, high = sorted(cast(Tuple[float, float], limits))
                if lo is not None and hi is None and lo >= high:
                    given, key, far, missing = lo, "min", high, "max"
                elif hi is not None and lo is None and hi <= low:
                    given, key, far, missing = hi, "max", low, "min"
                else:
                    continue
                warn_external(
                    f"The data range of {name} gives only {dim}{key} = "
                    f"{given:g}, and GLE takes the missing {dim}{missing} "
                    f"from the {axis} axis limit {far:g}, so the range is "
                    "empty and GLE stops with 'invalid range for dimension "
                    f"{dim.upper()}'. Give {dim}{missing} too, or widen the "
                    f"{axis} limits."
                )

    @staticmethod
    def _warn_node_grid_overhang(ax: Axes, grid: Series) -> None:
        """Warn where a grid heatmap's extra spacing would show.

        GLE draws the bitmap one node spacing past the grid's last node (see
        :meth:`GLEWriter.add_nodes_sidecar` and, for a ``tripcolor``,
        :meth:`GLEWriter.add_fitz_block`), and only the graph window hides
        it. Before the first node there is no bitmap, as matplotlib draws
        nothing there.
        """
        if "levels" in grid:
            kind = "contourf"
        else:
            kind = "tripcolor" if grid["source"] == "points" else "imshow"
        x0, x1, y0, y1 = grid["extent"]
        for name, lo, hi, a, b in (
            ("x", x0, x1, ax.xmin, ax.xmax),
            ("y", y0, y1, ax.ymin, ax.ymax),
        ):
            if a is not None and b is not None and max(a, b) > hi + 1e-9 * (hi - lo):
                warn_external(
                    f"The {name} limits reach {max(a, b):g}, beyond the {kind} "
                    f"grid's last {name} = {hi:g}, where GLE draws its last "
                    "values on for up to one grid spacing. Keep the upper "
                    f"{name} limit within the grid."
                )

    @staticmethod
    def _warn_mesh_overhang(ax: Axes, mesh: Series) -> None:
        """Warn where a ``pcolormesh`` bitmap's padding would show or vanish.

        GLE draws the mesh's bitmap half a cell past each edge (see
        :meth:`GLEWriter.add_cells_sidecar`), and only the graph window hides
        that half cell. On a log axis, a bitmap starting at or below zero is
        not drawn at all.
        """
        x0, x1, y0, y1 = mesh["extent"]
        ny, nx = np.shape(mesh["z"])
        for name, lo, hi, cells, scale, a, b in (
            ("x", x0, x1, nx, ax.xscale, ax.xmin, ax.xmax),
            ("y", y0, y1, ny, ax.yscale, ax.ymin, ax.ymax),
        ):
            half = (hi - lo) / cells / 2
            if scale == "log" and lo - half <= 0:
                warn_external(
                    f"The pcolormesh mesh is not drawn: on a log {name} axis "
                    "GLE draws nothing of a mesh whose bitmap starts at or "
                    f"below zero, and this one starts half a cell before its "
                    f"first edge, at {name} = {lo - half:g}. Start the mesh "
                    f"more than half a cell above zero, or use a linear "
                    f"{name} scale."
                )
            elif a is not None and b is not None:
                a, b = min(a, b), max(a, b)
                tol = 1e-9 * (hi - lo)
                if a < lo - tol or b > hi + tol:
                    warn_external(
                        f"The {name} limits ({a:g} to {b:g}) reach beyond "
                        "the pcolormesh mesh "
                        f"({lo:g} to {hi:g}), where its edge cells are drawn "
                        "up to half a cell too wide: GLE draws the mesh's "
                        "bitmap half a cell past each edge. Keep the "
                        f"{name} limits within the mesh to draw every cell "
                        "exactly."
                    )

    def _write_contours(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution
    ) -> None:
        """Contour polylines, above the heatmaps and below every series."""
        for ct in resolution.visible(ax.contours):
            writer.add_contour(ct)

    def _prepare_legend(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution, limits
    ) -> _LegendLayout:
        """Work out this axes' key and set the writer's column breaks.

        The breaks are set before any series is emitted, because GLE's
        in-graph ``key separator`` is written where the dataset stands.
        """
        entries = self._legend_entries(writer, ax, resolution, limits)
        n_legend = len(entries)
        # With a figure legend, an axes shows its own only if asked to.
        auto = n_legend > 0 and self._legend is None
        show = ax.legend_on if ax.legend_on is not None else auto
        # Addition order is matplotlib's legend order. GLE's in-graph
        # ``key separator`` is inserted where the statement stands, and a
        # dataset stays where it was first used, which is draw order. When
        # those two sequences differ, the graph key is turned off and a
        # ``begin key`` after ``end graph`` lists the entries in the order
        # they were added. When they agree, the in-graph key is unchanged.
        addition = self._legend_addition_order(entries)
        # An anchor or a text colour exists only in a ``begin key`` block,
        # which is measured against the graph that has just ended.
        # So does a fit's result: GLE evaluates the in-graph key before it
        # runs the fit.
        needs_block = n_legend > 0 and (
            ax.legend_bbox_to_anchor is not None
            or ax.legend_labelcolor is not None
            or any(writer.fit_label_shows_results(entry[0]) for entry in entries)
        )
        external = show and (needs_block or addition != list(range(n_legend)))
        # Reset even for a one-column key: the writer is reused across
        # subplots, and a previous axes' breaks must not leak.
        ncol = int(getattr(ax, "legend_ncol", 1) or 1)
        if show and ncol > 1 and not external:
            writer.set_legend_breaks(legend_column_breaks(n_legend, ncol))
        else:
            writer.set_legend_breaks(set())
        return _LegendLayout(entries, show, addition, external, ncol)

    @staticmethod
    def _write_spans(writer: GLEWriter, ax: Axes, limits) -> None:
        """axvspan/axhspan bands across an axis GLE has yet to scale.

        Drawn after ``end graph`` against the engine's own range instead of
        a literal fill over a range gleplot would have to invent (see
        gleplot.guides). The other bands are fills, written by
        :meth:`_write_fills`.
        """
        for span in ax.engine_range_guides(ax.spans, limits):
            writer.add_span(span)

    @staticmethod
    def _write_fills(
        writer: GLEWriter, ax: Axes, resolution: SourceResolution, limits
    ) -> None:
        """Fill regions, then the axvspan/axhspan bands realized as fills.

        The bands are declarations until the axis limits are known, and they
        belong in the same background layer as fills so the data series
        always draw on top of their guides.
        """
        # The declarations behind the materialized bands, in the same order
        # (see Axes.dataset_form_guides), so each fill can be preceded by the
        # provenance marker that makes it re-import as a Span (G18-lite).
        span_sources = ax.dataset_form_guides(ax.spans, limits)
        span_fills = ax.materialize_spans(limits)
        if len(span_sources) != len(span_fills):  # pragma: no cover - invariant
            raise AssertionError(
                "materialize_spans and dataset_form_guides disagree: "
                f"{len(span_fills)} vs {len(span_sources)}"
            )
        for fill_series, fill_data in resolution.pairs(ax.fills):
            writer.add_fill(fill_data, binding=resolution.binding(fill_series))
        # A materialized band is built after resolution, so it has no binding.
        for source, span_fill in zip(span_sources, span_fills):
            writer.add_span_dataset(source, span_fill)

    @staticmethod
    def _write_reflines(writer: GLEWriter, ax: Axes, limits) -> None:
        """Reference lines (axvline/axhline).

        Drawn above the shaded bands but still below every data series.
        Same split as the bands: a guide whose spanned axis is GLE's to
        scale is drawn after ``end graph``, the rest are marked datasets.
        """
        for ref in ax.engine_range_guides(ax.reflines, limits):
            writer.add_refline(ref)

        ref_sources = ax.dataset_form_guides(ax.reflines, limits)
        ref_datasets = ax.materialize_reflines(limits)
        if len(ref_sources) != len(ref_datasets):  # pragma: no cover - invariant
            raise AssertionError(
                "materialize_reflines and dataset_form_guides disagree: "
                f"{len(ref_datasets)} vs {len(ref_sources)}"
            )
        for source, ref_data in zip(ref_sources, ref_datasets):
            writer.add_refline_dataset(source, ref_data)

    def _write_drawables(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution
    ) -> None:
        """Bars, lines, scatters, histograms, curves and errorbars, in z-order.

        A bar group is written once, at its first member, as one ``bar``
        statement over all its members.
        """
        drawables = resolution.drawables(ax)
        emitted_groups: set = set()
        for kind, series, series_data in drawables:
            binding = resolution.binding(series)
            if kind == "bar":
                group_id = series_data.get("group")
                if group_id is None:
                    self._write_bar(writer, series_data, binding)
                elif group_id not in emitted_groups:
                    members = [
                        item[2]
                        for item in drawables
                        if item[0] == "bar" and item[2].get("group") == group_id
                    ]
                    writer.add_bar_group(members)
                    emitted_groups.add(group_id)
            elif kind == "line":
                self._write_line(writer, series_data, binding)
            elif kind == "scatter":
                self._write_scatter(writer, series_data, binding)
            elif kind == "hist":
                self._write_hist(writer, series_data)
            elif kind == "function":
                writer.add_function(series_data)
            elif kind == "fit":
                writer.add_fit(series_data)
            else:
                self._write_errorbar(writer, series_data, binding)

    @staticmethod
    def _write_bar(writer: GLEWriter, series_data, binding) -> None:
        writer.add_bar(series_data, binding=binding)

    @staticmethod
    def _write_line(writer: GLEWriter, series_data, binding) -> None:
        writer.add_line(series_data, binding=binding)

    @staticmethod
    def _write_scatter(writer: GLEWriter, series_data, binding) -> None:
        writer.add_scatter(series_data, binding=binding)

    @staticmethod
    def _write_hist(writer: GLEWriter, series_data) -> None:
        writer.add_hist(series_data)

    @staticmethod
    def _write_errorbar(writer: GLEWriter, series_data, binding) -> None:
        writer.add_errorbar_series(series_data, binding=binding)

    @staticmethod
    def _write_file_series(
        writer: GLEWriter, ax: Axes, resolution: SourceResolution
    ) -> None:
        """Series read from external files (no generated data files).

        Walked through the resolution like every other list, so a hidden
        one is skipped.
        """
        for fs_data in resolution.visible(ax.file_series):
            writer.add_file_series(fs_data)

    @staticmethod
    def _derived_operands(ax: Axes, resolution: SourceResolution, series):
        """The written forms of the series a derived series reads, or ``None``.

        ``None`` when a reference no longer points at a series ``derived``
        accepts, or one of those series is not drawn (hidden or dangling).
        """
        found = ax._derived_operands(series)
        if found is None:
            return None
        groups = tuple([resolution.data(item) for item in group] for group in found)
        if any(item is None for group in groups for item in group):
            return None
        return groups

    def _write_derived(
        self, writer: GLEWriter, ax: Axes, resolution: SourceResolution
    ) -> None:
        """Curves computed from other series, after every dataset they read."""
        for series in resolution.visible(ax.derived_series):
            operands = self._derived_operands(ax, resolution, series)
            if operands is None:
                warn_external(
                    f"derived() curve {series['expression']!r} was not drawn: a "
                    f"series in its sources or range is hidden or could not be "
                    f"loaded, or its place in ax.lines, ax.file_series, ... no "
                    f"longer holds a series derived() reads. Show that series, "
                    f"or call derived() again with the series as they are now."
                )
                continue
            writer.add_derived(series, *operands)

    @staticmethod
    def _write_texts(writer: GLEWriter, ax: Axes) -> None:
        for text_data in ax.texts:
            writer.add_text_annotation(text_data)

    def _write_legend(
        self,
        writer: GLEWriter,
        ax: Axes,
        legend: _LegendLayout,
        resolution: SourceResolution,
    ) -> None:
        """The key, if one is shown, else ``key off`` where GLE needs it.

        ``legend_on`` is tri-state: None means auto (show iff labels
        exist); True/False is an explicit user choice.

        The entry count is the same one the separators were placed against,
        so a series that is not drawn cannot vote for a key it will have no
        entry in (SPEC 14.6). Fills are in that count: their swatch is a
        ``keyfill`` line, not a ``key`` on the fill command.
        """
        n_legend = len(legend.entries)
        offset = self._legend_offset(ax)
        if legend.external and ax.legend_bbox_to_anchor is not None and offset:
            # Axes.legend already warned about an offset of its own.
            if ax.legend_offset is None:
                warn_external(
                    "GLEGraphConfig legend_offset_x/legend_offset_y has no "
                    "effect on a legend placed with bbox_to_anchor.",
                )
            offset = None
        key = KeyOptions(
            position=ax.legend_pos,
            fontsize=getattr(ax, "legend_fontsize", None),
            frameon=getattr(ax, "legend_frameon", True),
            offset=offset,
            compact=bool(getattr(ax, "legend_compact", False)),
            background=getattr(ax, "legend_facecolor", None),
            spacing=dict(ax.legend_spacing),
            anchor=ax.legend_bbox_to_anchor,
            labelcolor=ax.legend_labelcolor,
        )
        if legend.external:
            # ``key off`` hides the draw-order key. The visible one is the
            # block queued for end_graph, in addition order.
            writer.add_key_off()
            # The writer knows each series as written: its resolved form.
            ordered = [
                (resolution.data(series) or series, label, swatch)
                for series, label, swatch in (
                    legend.entries[i] for i in legend.addition
                )
            ]
            breaks = legend_column_breaks(n_legend, legend.ncol)
            writer.queue_external_legend(ordered, breaks, key)
        elif legend.show:
            writer.add_legend(key)
        elif n_legend > 0:
            # GLE draws an implicit key from per-dataset key "label" tokens;
            # it must be switched off explicitly.
            writer.add_key_off()

    def _emit_break_decoration(
        self,
        writer: GLEWriter,
        bax: BrokenAxes,
        seg: Axes,
        cell: Tuple[float, float, float, float],
    ):
        """Emit the seam marker, or the shared titles, after a segment's graph.

        Called right after each broken-axis segment's ``end graph``, which is
        the only point where GLE's ``xg()``/``yg()`` refer to that segment's
        box. Every segment but the last gets the seam decoration on its right
        edge; the last one carries the titles, which are centred on the whole
        assembly (``cell_x + cell_w/2``) rather than on any single graph.
        ``cell`` is ``(cell_x, cell_w, cell_y, cell_h)``. A broken y-axis is
        :meth:`_emit_ybreak_decoration`.
        """
        if bax.axis == "y":
            self._emit_ybreak_decoration(writer, bax, seg, cell)
            return
        cell_x, cell_w = cell[0], cell[1]
        index = seg._break_index
        is_last = index == len(bax.segments) - 1

        if not is_last:
            if bax.divider == "line":
                writer.add_break_divider(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    lstyle=bax.divider_lstyle,
                )
            elif bax.divider == "slash":
                size = bax.break_mark_size
                writer.add_break_marks(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    width_cm=0.65 * size,
                    height_cm=size,
                    separation_cm=0.3 * size,
                )
            return

        # Titles. GLE places its own xtitle one tick-label row below the frame;
        # 1.57 * the font height reproduces that offset (measured against a
        # native `xtitle` render, matching to ~0.02 cm), and the title sits
        # 0.55 * the font height above the frame.
        hei_cm = fontsize_pt_to_cm(self.style.fontsize)
        centre_x = cell_x + cell_w / 2.0
        if bax.xlabel_text:
            dist = bax.xlabel_dist if bax.xlabel_dist is not None else 1.57 * hei_cm
            writer.add_page_text(
                centre_x,
                f"yg(ygmin)-{writer._format_number(dist)}",
                bax.xlabel_text,
                just="tc",
            )
        self._emit_break_title(writer, bax, centre_x)

    def _emit_break_title(
        self, writer: GLEWriter, bax: BrokenAxes, centre_x: float
    ) -> None:
        """A broken axis' shared title, above the graph that just ended.

        GLE draws a graph's own ``title`` with its x axis, which the upper
        segments of a broken y-axis switch off, so either orientation writes
        it as page text centred on the assembly.
        """
        if bax.title_text:
            hei_cm = fontsize_pt_to_cm(self.style.fontsize)
            dist = bax.title_dist if bax.title_dist is not None else 0.55 * hei_cm
            writer.add_page_text(
                centre_x,
                f"yg(ygmax)+{writer._format_number(dist)}",
                bax.title_text,
                just="bc",
            )

    def _emit_ybreak_decoration(
        self,
        writer: GLEWriter,
        bax: BrokenAxes,
        seg: Axes,
        cell: Tuple[float, float, float, float],
    ):
        """The seam marker, or the shared titles, after a broken-y segment.

        Every segment but the top one gets the seam decoration on its top
        edge. The top one carries the title, as on a broken x-axis, and the
        y title, centred on the whole assembly (``cell_y + cell_h/2``) and
        ``ylabel_dist`` left of the frame. The x title is the bottom
        segment's own.
        """
        index = seg._break_index
        if index != len(bax.segments) - 1:
            if bax.divider == "line":
                writer.add_ybreak_divider(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    lstyle=bax.divider_lstyle,
                )
            elif bax.divider == "slash":
                size = bax.break_mark_size
                writer.add_ybreak_marks(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    width_cm=size,
                    height_cm=0.65 * size,
                    separation_cm=0.3 * size,
                )
            return
        self._emit_break_title(writer, bax, cell[0] + cell[1] / 2.0)
        if bax.ylabel_text:
            # GLE does not report its tick labels' width, so the distance is
            # a fixed multiple of the font height (see add_broken_yaxes).
            hei_cm = fontsize_pt_to_cm(self.style.fontsize)
            dist = bax.ylabel_dist if bax.ylabel_dist is not None else 2.5 * hei_cm
            writer.add_page_ytitle(
                f"xg(xgmin)-{writer._format_number(dist)}",
                cell[2] + cell[3] / 2.0,
                bax.ylabel_text,
            )

    # -- axis limits -----------------------------------------------------
    #
    # GLE derives an axis' range from the data when the script does not give
    # one, and REFUSES to compile a log axis whose range reaches zero or
    # below: "Error: illegal range for log axis: min = 0 max = 3". That makes
    # an omitted bound unusable on a log axis -- ``yaxis log`` over data
    # containing a zero is rejected exactly like ``yaxis min 0 log`` is -- so
    # gleplot has to resolve log limits itself and always emit a positive
    # ``min``. See :meth:`_apply_log_limits`.

    #: Range emitted for a log axis about which nothing positive is known
    #: (every value non-positive, or no in-memory data at all). Arbitrary, but
    #: legal, deterministic, and a decade wide so the axis still reads as
    #: logarithmic.
    _LOG_FALLBACK_RANGE = (1.0, 10.0)

    def _resolve_axis_limits(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Fill in ``ax``'s missing limits from its data, then make them legal.

        Autoscaling matters beyond aesthetics for bar charts (which need an
        explicit x range) and for every log axis (see above). Runs before the
        shared-axis synchronization, so what that unifies is already resolved.
        """
        if ax._polar:
            # The radial limit; the window itself is derived at write time
            # from it and the frame (_write_axis_setup).
            if ax.ymax is None:
                ax.ymax = self._polar_rmax(ax, resolution)
            ax.ymin = 0.0
            return

        # Which bounds are the AXES' own, and which this call is about to
        # invent. Only the invented ones may be handed back to GLE when the
        # result collapses (:meth:`_defer_degenerate_range`); a bound the
        # caller asked for is never dropped without saying so.
        was_auto = {
            "x": (ax.xmin is None, ax.xmax is None),
            "y": (ax.ymin is None, ax.ymax is None),
            "y2": (ax.y2min is None, ax.y2max is None),
            "x2": (ax.x2min is None, ax.x2max is None),
        }

        if ax.xmin is None or ax.xmax is None:
            data_xmin, data_xmax = self._get_data_xlim(ax, resolution)
            if ax.xmin is None:
                ax.xmin = data_xmin
            if ax.xmax is None:
                ax.xmax = data_xmax
        if ax.ymin is None or ax.ymax is None:
            data_ymin, data_ymax = self._get_data_ylim(ax, resolution)
            if ax.ymin is None:
                ax.ymin = data_ymin
            if ax.ymax is None:
                ax.ymax = data_ymax

        self._normalize_inverted_log_limits(ax)
        self._apply_log_limits(ax, resolution)

        # Last, so that a log axis is judged on the range its repair produced
        # (which is always increasing and positive) rather than on the
        # collapsed one it started from.
        for which, (lo_auto, hi_auto) in was_auto.items():
            self._defer_degenerate_range(ax, which, lo_auto, hi_auto, resolution)

    @staticmethod
    def _polar_rmax(ax: Axes, resolution: Optional[SourceResolution]) -> float:
        """A polar axes' automatic radial limit.

        The largest finite ``|r|`` among its lines and scatters, rounded up
        to the next ring of :func:`~gleplot.writer.polar_ring_step`; 1 when
        there is no such point. Function curves are not evaluated, so they
        do not count.
        """
        resolution = resolution or SourceResolution()
        largest = 0.0
        for series in resolution.visible(ax.lines) + resolution.visible(ax.scatters):
            r = np.abs(np.asarray(series["y"], dtype=float))
            r = r[np.isfinite(r)]
            if r.size:
                largest = max(largest, float(r.max()))
        if largest == 0.0:
            return 1.0
        step = polar_ring_step(largest)
        return float(GLEWriter._format_number(step * math.ceil(largest / step - 1e-9)))

    # -- degenerate ranges ------------------------------------------------
    #
    # An axis can resolve to a single value: one data point, a lone ``axvline``
    # that is the only thing bounding x, a table with one row. GLE will not
    # accept that written down -- ``xaxis min 1 max 1`` is "Error: illegal
    # range for xaxis: min = 1 max = 1" and exit 1, with or without a trailing
    # ``off``, and the same on ``y2axis`` (measured against GLE 4.3.10).
    #
    # GLE can nevertheless DRAW such a graph: left to itself it expands the
    # point into a nice-number range around it -- measured, again on 4.3.10,
    # for a single plotted point: (1, 2) -> x 0..2, y 1..3; (5, 7) -> 0..10,
    # 0..12; (-3, -3) -> -6..0 on both; (0, 0) -> -1..1 on both. So the
    # emission forbids what the engine allows, and the fix is to stop
    # emitting: the axis' range is left out of the script and GLE scales it.
    # Reproducing that arithmetic in Python would be a second, drifting
    # implementation of a number gleplot never needs to know.
    #
    # GLE widens from the datasets it draws, though. An axis no dataset
    # reaches (only box plots, rugs, text or images, drawn after ``end graph``
    # or by ``draw``) gets 0..1 from it, which clips what is drawn. There
    # gleplot writes its own margin, the value's magnitude either side (or 1
    # at zero): GLE's x range for a lone point, though not its rounded y one.

    def _defer_degenerate_range(
        self,
        ax: Axes,
        which: str,
        lo_auto: bool,
        hi_auto: bool,
        resolution: Optional[SourceResolution] = None,
    ) -> None:
        """Hand ``which``'s range back to GLE if it collapsed to a point,
        or give it a margin where GLE has no dataset to widen it from.

        Parameters
        ----------
        which:
            ``"x"``, ``"y"``, ``"y2"`` or ``"x2"``.
        lo_auto, hi_auto:
            Whether each bound was derived rather than asked for. A derived
            bound is simply dropped; GLE re-derives it, better. An explicit
            one is kept where it can be -- ``set_xlim(5, None)`` over a lone
            point at x=5 still emits ``xaxis min 5``, and GLE draws 5..10, so
            the user's bound is the frame edge and only the collapse is gone.

        When BOTH bounds were explicit the range is the caller's own empty
        one; there is no way to draw it, so it is dropped and said out loud,
        the way :meth:`_apply_log_limits` reports an impossible log range.

        Where no dataset GLE draws reaches the axis (see
        :meth:`_engine_can_scale`), the derived bounds are written as
        ``v - |v|`` and ``v + |v|`` instead (-1 and 1 at zero), so a lone box
        plot or rug is not clipped by GLE's 0..1.
        """
        lo, hi = self._axis_limits(ax, which)
        if lo is None or hi is None or lo != hi:
            return

        if not lo_auto and not hi_auto:
            setter = {
                "x": "set_xlim()",
                "y": "set_ylim()",
                "y2": "set_ylim(axis='y2')",
                "x2": "set_xlim(axis='x2')",
            }[which]
            instead = (
                "Leaving the range out of the script, so GLE autoscales around "
                "the value instead."
                if self._engine_can_scale(ax, which, resolution)
                else "Widening it by the value's magnitude either side instead."
            )
            warn_external(
                f"{which}-axis limits are both {lo!r}, an empty range that GLE "
                f'refuses to draw ("illegal range"). {instead} Call '
                f"{setter} with a non-empty range to choose your own.",
            )
            lo_auto = hi_auto = True

        if not self._engine_can_scale(ax, which, resolution):
            width = abs(lo) or 1.0
            self._set_axis_limits(
                ax,
                which,
                lo - width if lo_auto else lo,
                hi + width if hi_auto else hi,
            )
            return

        self._set_axis_limits(
            ax,
            which,
            None if lo_auto else lo,
            None if hi_auto else hi,
        )

    #: Series GLE does not scale an axis from: drawn after ``end graph`` or by
    #: a ``draw`` call, with no dataset.
    _ENGINE_BLIND = frozenset({"texts", "wedges", "boxes", "rugs", "images"})

    def _engine_can_scale(
        self, ax: Axes, which: str, resolution: Optional[SourceResolution]
    ) -> bool:
        """Whether ``ax`` draws a dataset GLE can widen ``which``'s range from.

        One drawn against that axis (a ``y2`` series does not scale ``y``)
        with at least one finite point on it; a series with no point arrays
        (a function curve, a grid) counts.
        """
        resolution = resolution or SourceResolution()
        field, axis = ("yaxis", which) if which[0] == "y" else ("xaxis", which)
        primary = axis in ("x", "y")
        for attr in SERIES_ATTRS:
            if attr in self._ENGINE_BLIND:
                continue
            for series in resolution.visible(getattr(ax, attr)):
                if (series.get(field, axis[0]) == axis[0]) != primary:
                    continue
                values = series.get(axis[0])
                if values is None or np.isfinite(np.asarray(values, dtype=float)).any():
                    return True
        return False

    def _normalize_inverted_log_limits(self, ax: Axes):
        """Undo an axis inversion on a log axis, which GLE cannot draw.

        Descending limits invert an axis (``set_ylim(3, 1)``, matplotlib's
        idiom), and :meth:`GLEWriter._axis_direction` emits that as GLE's
        ``negate``. But GLE's ``negate`` mirrors the value *linearly* before
        taking the logarithm -- ``fnAxisX`` in ``axis.cpp`` computes
        ``max - (v - min)`` and only then ``log10`` -- so on a log axis it
        does not reverse the decades, it smears them: measured against GLE
        4.3.10, ``yaxis min 1 max 100 log negate`` puts 1, 10 and 100 at
        7.00, 6.88 and 1.00 cm, with the first two decades on top of each
        other.

        There is no way to spell a reversed log axis in GLE, so the inversion
        is dropped rather than drawn wrong, and said out loud.
        """
        for which, scale in (
            ("x", ax.xscale),
            ("y", ax.yscale),
            ("y2", ax.y2scale),
            ("x2", ax.x2scale),
        ):
            if scale != "log":
                continue
            lo, hi = self._axis_limits(ax, which)
            if lo is None or hi is None or lo <= hi:
                continue
            warn_external(
                f"{which}-axis has descending limits ({lo!r} .. {hi!r}), "
                "which would invert it, but GLE cannot invert a log axis "
                f"(its 'negate' does not reverse the decades). Drawing "
                f"{hi!r} .. {lo!r} the usual way round instead.",
            )
            self._set_axis_limits(ax, which, hi, lo)

    def _apply_log_limits(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Force every log-scaled axis of ``ax`` onto a positive range.

        A log axis cannot show zero or negative values, and GLE will not
        compile a script that asks it to. matplotlib's answer is to keep
        drawing: it masks the non-positive values when autoscaling, and
        ignores a non-positive bound passed to ``set_xlim``/``set_ylim`` with
        a warning. gleplot does the same, and additionally has to *write down*
        the resulting range, because leaving a bound out would hand the
        decision back to GLE, which would fail on the same raw data.

        The replacement bound is therefore the axis' own data, bounded over
        its positive values only. The limits are stored back onto ``ax`` --
        like the ordinary autoscale above, which has always written what it
        derived back onto the axes -- so the model says what the script says,
        and a re-save (of this figure or of the file parsed back from it)
        finds nothing left to repair and warns no further.
        """
        for which, scale in (
            ("x", ax.xscale),
            ("y", ax.yscale),
            ("y2", ax.y2scale),
            ("x2", ax.x2scale),
        ):
            if scale != "log":
                continue
            lo, hi = self._axis_limits(ax, which)
            fixed = self._log_safe_range(ax, which, lo, hi, resolution)
            if fixed != (lo, hi):
                setter = {
                    "x": "set_xlim()",
                    "x2": "set_xlim(axis='x2')",
                    "y": "set_ylim()",
                    "y2": "set_ylim(axis='y2')",
                }[which]
                warn_external(
                    f"{which}-axis is log-scaled, but the range it resolved "
                    f"to ({lo!r} .. {hi!r}) is not an increasing positive "
                    "one, which GLE refuses to draw. Using "
                    f"{fixed[0]:g} .. {fixed[1]:g} instead, from the positive "
                    f"values plotted on it. Call {setter} with a positive "
                    "range to choose your own.",
                )
                self._set_axis_limits(ax, which, *fixed)

    def _log_safe_range(
        self,
        ax: Axes,
        which: str,
        lo: Optional[float],
        hi: Optional[float],
        resolution: Optional[SourceResolution],
    ) -> Tuple[Optional[float], Optional[float]]:
        """``lo``..``hi`` made legal for a log axis, or returned untouched.

        Untouched is the common answer, and deliberately so: an omitted bound
        is only a problem when the data GLE would autoscale over reaches zero.
        A log plot of positive data keeps emitting a bare ``yaxis log``, and a
        series gleplot cannot see the numbers of (a file series) keeps its
        autoscale as well -- guessing a range for data this process never read
        would be worse than the error it is trying to avoid.

        When the range does need fixing, only the offending bound is replaced,
        so ``set_ylim(0, 400)`` on a log axis keeps its 400.
        """
        scan = {
            "x": self._get_data_xlim,
            "y": self._get_data_ylim,
            "y2": self._get_data_y2lim,
            "x2": self._get_data_x2lim,
        }[which]

        # What the axis will actually span: the explicit bounds where given,
        # and what GLE would autoscale to where not.
        data_lo, data_hi = (None, None)
        if lo is None or hi is None:
            data_lo, data_hi = scan(ax, resolution)
        effective_lo = lo if lo is not None else data_lo
        effective_hi = hi if hi is not None else data_hi

        if effective_lo is None:
            # No visible data and no explicit bound: nothing to judge.
            return (lo, hi)
        if effective_lo > 0 and (effective_hi is None or effective_hi > effective_lo):
            return (lo, hi)

        pos_lo, pos_hi = scan(ax, resolution, positive_only=True)
        fallback_lo, decade = self._LOG_FALLBACK_RANGE
        new_lo = lo if (lo is not None and lo > 0) else pos_lo
        if new_lo is None:
            new_lo = fallback_lo
        new_hi = hi if (hi is not None and hi > new_lo) else pos_hi
        if new_hi is None or new_hi <= new_lo:
            new_hi = new_lo * decade
        return (float(new_lo), float(new_hi))

    @staticmethod
    def _axis_limits(ax: Axes, which: str) -> Tuple[Optional[float], Optional[float]]:
        if which == "x":
            return (ax.xmin, ax.xmax)
        if which == "x2":
            return (ax.x2min, ax.x2max)
        if which == "y":
            return (ax.ymin, ax.ymax)
        return (ax.y2min, ax.y2max)

    @classmethod
    def _axis_span(
        cls, ax: Axes, which: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """``(lower, upper)`` extent of an axis, whichever way round it reads."""
        lo, hi = cls._axis_limits(ax, which)
        if lo is not None and hi is not None and lo > hi:
            return (hi, lo)
        return (lo, hi)

    @classmethod
    def _axis_is_inverted(cls, ax: Axes, which: str) -> bool:
        """True if the axis' limits descend, i.e. it is drawn inverted."""
        lo, hi = cls._axis_limits(ax, which)
        return lo is not None and hi is not None and lo > hi

    @staticmethod
    def _set_axis_limits(
        ax: Axes, which: str, lo: Optional[float], hi: Optional[float]
    ):
        """Write a pair of bounds back onto ``ax``. ``None`` means auto."""
        if which == "x":
            ax.xmin, ax.xmax = lo, hi
        elif which == "x2":
            ax.x2min, ax.x2max = lo, hi
        elif which == "y":
            ax.ymin, ax.ymax = lo, hi
        else:
            ax.y2min, ax.y2max = lo, hi

    def _synchronize_x_limits(self, resolution: Optional[SourceResolution] = None):
        """Give each group of panels that share the x axis one x range."""

        # Read before the fill loop overwrites it: a bound nobody set on ANY
        # panel is one the shared range may hand back to GLE if it collapses
        # (see _defer_degenerate_range). The union of several panels is rarely
        # a point, but it is whenever they all sit on the same single value.
        for shared in self._share_groups(self.sharex):
            # Each group of panels sharing the axis gets its own range.
            lo_global = None
            hi_global = None
            inverted = False
            lo_auto = all(ax.xmin is None for ax in shared)
            hi_auto = all(ax.xmax is None for ax in shared)

            for ax in shared:
                # Calculate data limits if not explicitly set
                if ax.xmin is None or ax.xmax is None:
                    data_xmin, data_xmax = self._get_data_xlim(ax, resolution)
                    if ax.xmin is None:
                        ax.xmin = data_xmin
                    if ax.xmax is None:
                        ax.xmax = data_xmax

                # Track the global SPAN. A descending pair is an inverted axis
                # (see GLEWriter._axis_direction), so read its extent through
                # min/max rather than trusting the order, and carry the inversion
                # over to the shared result -- sharing an axis must not silently
                # flip a panel back the right way up.
                lo, hi = self._axis_span(ax, "x")
                inverted = inverted or self._axis_is_inverted(ax, "x")
                if lo is not None and (lo_global is None or lo < lo_global):
                    lo_global = lo
                if hi is not None and (hi_global is None or hi > hi_global):
                    hi_global = hi

            # Apply global limits to all axes
            for ax in shared:
                if inverted and lo_global is not None and hi_global is not None:
                    ax.xmin, ax.xmax = hi_global, lo_global
                else:
                    ax.xmin, ax.xmax = lo_global, hi_global
                self._defer_degenerate_range(ax, "x", lo_auto, hi_auto, resolution)

    def _synchronize_y_limits(self, resolution: Optional[SourceResolution] = None):
        """Give each group of panels that share the y axis one y range."""
        # See _synchronize_x_limits.
        for shared in self._share_groups(self.sharey):
            # Each group of panels sharing the axis gets its own range.
            lo_global = None
            hi_global = None
            inverted = False
            lo_auto = all(ax.ymin is None for ax in shared)
            hi_auto = all(ax.ymax is None for ax in shared)

            for ax in shared:
                # Calculate data limits if not explicitly set
                if ax.ymin is None or ax.ymax is None:
                    data_ymin, data_ymax = self._get_data_ylim(ax, resolution)
                    if ax.ymin is None:
                        ax.ymin = data_ymin
                    if ax.ymax is None:
                        ax.ymax = data_ymax

                # See _synchronize_x_limits on descending (inverted) pairs.
                lo, hi = self._axis_span(ax, "y")
                inverted = inverted or self._axis_is_inverted(ax, "y")
                if lo is not None and (lo_global is None or lo < lo_global):
                    lo_global = lo
                if hi is not None and (hi_global is None or hi > hi_global):
                    hi_global = hi

            # Apply global limits to all axes
            for ax in shared:
                if inverted and lo_global is not None and hi_global is not None:
                    ax.ymin, ax.ymax = hi_global, lo_global
                else:
                    ax.ymin, ax.ymax = lo_global, hi_global
                self._defer_degenerate_range(ax, "y", lo_auto, hi_auto, resolution)

    def _get_data_xlim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate x-axis limits from data.

        Reads through ``resolution``, so table-backed series autoscale from
        their resolved values and skipped (dangling) series contribute
        nothing -- the limits describe what will actually be drawn.

        With ``positive_only``, values <= 0 are dropped before bounding, which
        is what a log axis needs (:meth:`_apply_log_limits`); the result is
        ``(None, None)`` when nothing positive is plotted.
        """
        resolution = resolution or SourceResolution()
        xmin, xmax = None, None

        x_bearing: Sequence[Sequence[Series]] = (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.errorbars),
            resolution.visible(ax.fits),
        )
        for data_list in x_bearing:
            for data in data_list:
                if data.get("xaxis") == "x2":
                    continue
                x = np.asarray(data["x"], dtype=float)
                # yerr already widens the y range. xerr has to widen x the
                # same way, or the explicit ``xaxis`` written below clips a
                # horizontal whisker (``barh(..., xerr=)`` and ``xerr`` on
                # ``errorbar``). Series with no x error keep the old path.
                xerr_left = data.get("xerr_left")
                xerr_right = data.get("xerr_right")
                if xerr_left is None and xerr_right is None:
                    values = x
                else:
                    pieces = [x]
                    if xerr_left is not None:
                        pieces.append(x - np.asarray(xerr_left, dtype=float))
                    if xerr_right is not None:
                        pieces.append(x + np.asarray(xerr_right, dtype=float))
                    values = np.concatenate(pieces)
                values = _plottable(values, positive_only)
                if len(values) > 0:
                    if xmin is None or values.min() < xmin:
                        xmin = float(values.min())
                    if xmax is None or values.max() > xmax:
                        xmax = float(values.max())

        # Bars are the one series whose x extent is wider than its x values.
        # GLE's own ``get_dataset_ranges`` pushes a bar dataset's data range
        # out by half an inter-point interval either side "so that bars are
        # visible", and gleplot has always left that half-bar to the engine.
        # The engine cannot supply it when every point of the dataset shares
        # one x: there is no interval to halve, the range collapses, and G15's
        # deferral then hands GLE an axis it answers with "invalid range for
        # dimension X". For exactly those datasets gleplot applies GLE's rule
        # itself, with the nominal spacing the bar width comes from -- see
        # ``GLEWriter.bar_width_gle_cannot_derive`` for why that spacing is 1,
        # and why the range and the width have to be read off the same number.
        #
        # G19: a series carrying its own ``width`` supplies that number
        # instead, so the half-span still equals the width actually drawn.
        # Only for these same unmeasurable datasets: where GLE can measure an
        # interval it widens the range from the DATA, ignoring any width the
        # script names (measured -- see ``GLEWriter.bar_range_half_span``), so
        # a width must never start pulling a range gleplot did not write.
        for bar_data in resolution.visible(ax.bars):
            if bar_data.get("horiz"):
                xmin, xmax = _apply_bar_value_extent(
                    _bar_value_extent(bar_data, positive_only),
                    xmin,
                    xmax,
                    positive_only,
                )
                continue
            extent = _bar_position_extent(bar_data, positive_only)
            if extent is None:
                continue
            lo, hi = extent
            if xmin is None or lo < xmin:
                xmin = lo
            if xmax is None or hi > xmax:
                xmax = hi

        # A histogram's x extent is the bin window, not the sample values and
        # not the index column written beside them. The step outline and the
        # full-width bars both reach the edges.
        for hist in resolution.visible(ax.hists):
            if hist.get("xaxis") == "x2":
                continue
            lo = hist.get("hist_from")
            hi = hist.get("hist_to")
            if lo is None or hi is None or not (float(hi) > float(lo)):
                samples = _plottable(np.asarray(hist["samples"]), positive_only)
                if len(samples) == 0:
                    continue
                lo, hi = float(samples.min()), float(samples.max())
            else:
                lo, hi = float(lo), float(hi)
                if positive_only:
                    if lo <= 0:
                        lo = hi if hi > 0 else None
                    if hi <= 0:
                        hi = None
                    if lo is None or hi is None:
                        continue
            if xmin is None or lo < xmin:
                xmin = lo
            if xmax is None or hi > xmax:
                xmax = hi

        # A function, fit or derived curve spans its sampled range. Its y
        # values are GLE's to compute; a fit's data bounds y like any other
        # data.
        curves = (
            *resolution.visible(ax.functions),
            *resolution.visible(ax.fits),
            *resolution.visible(ax.derived_series),
        )
        for curve in curves:
            for value in (curve.get("let_from"), curve.get("let_to")):
                if value is None or (positive_only and value <= 0):
                    continue
                if xmin is None or value < xmin:
                    xmin = float(value)
                if xmax is None or value > xmax:
                    xmax = float(value)

        for fill_data in resolution.visible(ax.fills):
            x = _plottable(np.asarray(fill_data["x"]), positive_only)
            if len(x) > 0:
                if xmin is None or x.min() < xmin:
                    xmin = float(x.min())
                if xmax is None or x.max() > xmax:
                    xmax = float(x.max())

        for series in (
            resolution.visible(ax.heatmaps)
            + resolution.visible(ax.contours)
            + resolution.visible(ax.images)
        ):
            extent = series.get("extent")
            if not extent:
                # A reference-backed grid series with an auto extent (SPEC
                # 14.5) that has not been through write-time resolution --
                # e.g. an autoscale query with no resolution. It has no
                # numbers to contribute yet; a write resolves it first.
                continue
            x0, x1 = extent[0], extent[1]
            if not positive_only or x0 > 0:
                if xmin is None or x0 < xmin:
                    xmin = float(x0)
            if not positive_only or x1 > 0:
                if xmax is None or x1 > xmax:
                    xmax = float(x1)

        # A box spans its width, and at least half a unit either side of its
        # position: matplotlib's boxplot widens the x range to that. On a log
        # axis a padded end at or below zero drops out, the position stays.
        for box in resolution.visible(ax.boxes):
            pos = float(box["x"])
            half = max(0.5, float(box["width"]) / 2)
            ends = _plottable(np.array([pos - half, pos, pos + half]), positive_only)
            if len(ends) > 0:
                if xmin is None or ends.min() < xmin:
                    xmin = float(ends.min())
                if xmax is None or ends.max() > xmax:
                    xmax = float(ends.max())

        xs = [
            v
            for r in resolution.visible(ax.rugs)
            if r["axis"] == "x"
            for v in r["ticks"]
        ]
        all_x = _plottable(np.asarray(xs, dtype=float), positive_only)
        if len(all_x) > 0:
            if xmin is None or all_x.min() < xmin:
                xmin = float(all_x.min())
            if xmax is None or all_x.max() > xmax:
                xmax = float(all_x.max())

        # Vertical guides carry a data x-coordinate and, like matplotlib's
        # axvline/axvspan, participate in autoscaling. Horizontal ones do not:
        # their x extent is an axes FRACTION, so including it would be
        # circular.
        for value in _refline_axis_values(ax, "v"):
            if positive_only and value <= 0:
                continue
            if xmin is None or value < xmin:
                xmin = value
            if xmax is None or value > xmax:
                xmax = value

        return xmin, xmax

    def _get_data_ylim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate y-axis limits from data (see :meth:`_get_data_xlim`).

        The series drawn against y2 do not count: GLE scales y2 from its own
        datasets, as matplotlib's ``twinx`` scales each axis from its own
        artists. On an axes with no series on the primary axis at all, they
        still bound it, as they always have.
        """
        resolution = resolution or SourceResolution()
        ymin, ymax = None, None
        skip_y2 = any(
            not _on_y2(series)
            for attr in SERIES_ATTRS
            if attr != "texts"
            for series in resolution.visible(getattr(ax, attr))
        )

        # A series' ``offset`` shifts its trace vertically at plot time (the .dat
        # values stay raw), so autoscale must add it back when bounding the data
        # -- otherwise a waterfall stack falls off the auto-computed axis.
        offset_bearing: Sequence[Sequence[Series]] = (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.fits),
        )
        for data_list in offset_bearing:
            for data in data_list:
                if skip_y2 and _on_y2(data):
                    continue
                y = _plottable(
                    np.asarray(data["y"]) + data.get("offset", 0.0), positive_only
                )
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())

        for bar_data in resolution.visible(ax.bars):
            if bar_data.get("horiz"):
                extent = _bar_position_extent(bar_data, positive_only)
                if extent is None:
                    continue
                lo, hi = extent
                if ymin is None or lo < ymin:
                    ymin = lo
                if ymax is None or hi > ymax:
                    ymax = hi
                continue
            ymin, ymax = _apply_bar_value_extent(
                _bar_value_extent(bar_data, positive_only),
                ymin,
                ymax,
                positive_only,
            )

        for hist in resolution.visible(ax.hists):
            if skip_y2 and _on_y2(hist):
                continue
            hy0, hy1 = self._histogram_y_extent(hist, positive_only)
            if hy0 is None:
                continue
            if ymin is None or hy0 < ymin:
                ymin = hy0
            if ymax is None or hy1 > ymax:
                ymax = hy1

        for fill_data in resolution.visible(ax.fills):
            off = fill_data.get("offset", 0.0)
            # An axis or polygon fill has no second curve. The axis edge is
            # the limit being computed here, so it is not another sample.
            parts = [np.asarray(fill_data["y1"]) + off]
            y2 = fill_data.get("y2")
            if y2 is not None:
                parts.append(np.asarray(y2) + off)
            all_y = _plottable(np.concatenate(parts), positive_only)
            if len(all_y) > 0:
                if ymin is None or all_y.min() < ymin:
                    ymin = float(all_y.min())
                if ymax is None or all_y.max() > ymax:
                    ymax = float(all_y.max())

        for eb_data in resolution.visible(ax.errorbars):
            if skip_y2 and _on_y2(eb_data):
                continue
            y = np.asarray(eb_data["y"]) + eb_data.get("offset", 0.0)
            yerr_up = eb_data.get("yerr_up")
            yerr_down = eb_data.get("yerr_down")

            if len(y) > 0:
                if yerr_up is not None:
                    y_with_err_up = _plottable(y + np.asarray(yerr_up), positive_only)
                    if len(y_with_err_up) > 0 and (
                        ymax is None or y_with_err_up.max() > ymax
                    ):
                        ymax = float(y_with_err_up.max())
                if yerr_down is not None:
                    y_with_err_down = _plottable(
                        y - np.asarray(yerr_down), positive_only
                    )
                    if len(y_with_err_down) > 0 and (
                        ymin is None or y_with_err_down.min() < ymin
                    ):
                        ymin = float(y_with_err_down.min())

                y = _plottable(y, positive_only)
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())

        for series in (
            resolution.visible(ax.heatmaps)
            + resolution.visible(ax.contours)
            + resolution.visible(ax.images)
        ):
            extent = series.get("extent")
            if not extent:
                continue  # auto extent, unresolved -- see _get_data_xlim
            y0, y1 = extent[2], extent[3]
            if not positive_only or y0 > 0:
                if ymin is None or y0 < ymin:
                    ymin = float(y0)
            if not positive_only or y1 > 0:
                if ymax is None or y1 > ymax:
                    ymax = float(y1)

        for box in resolution.visible(ax.boxes):
            parts = [box["whislo"], box["q1"], box["med"], box["q3"], box["whishi"]]
            parts.extend(box["fliers"])
            if box.get("mean") is not None:
                parts.append(box["mean"])
            all_y = _plottable(np.asarray(parts, dtype=float), positive_only)
            if len(all_y) > 0:
                if ymin is None or all_y.min() < ymin:
                    ymin = float(all_y.min())
                if ymax is None or all_y.max() > ymax:
                    ymax = float(all_y.max())

        ys = [
            v
            for r in resolution.visible(ax.rugs)
            if r["axis"] == "y"
            for v in r["ticks"]
        ]
        all_y = _plottable(np.asarray(ys, dtype=float), positive_only)
        if len(all_y) > 0:
            if ymin is None or all_y.min() < ymin:
                ymin = float(all_y.min())
            if ymax is None or all_y.max() > ymax:
                ymax = float(all_y.max())

        # Horizontal guides carry a data y-coordinate (see _get_data_xlim for
        # the mirror-image reasoning).
        for value in _refline_axis_values(ax, "h"):
            if positive_only and value <= 0:
                continue
            if ymin is None or value < ymin:
                ymin = value
            if ymax is None or value > ymax:
                ymax = value

        return ymin, ymax

    def _get_data_y2lim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate secondary-y limits from the series drawn against y2.

        The mirror of :meth:`_get_data_ylim`, which leaves these series out:
        y2 limits are normally left to GLE, and the one thing gleplot has to know for
        itself is what a log-scaled y2 can legally span. Only the series kinds
        that carry a ``yaxis`` field can be on y2 at all; bars, fills, grids
        and reference lines are always primary.
        """
        resolution = resolution or SourceResolution()
        y2min, y2max = None, None

        for data_list in (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.errorbars),
        ):
            for data in data_list:
                if not _on_y2(data):
                    continue
                y = _plottable(
                    np.asarray(data["y"]) + data.get("offset", 0.0), positive_only
                )
                if len(y) > 0:
                    if y2min is None or y.min() < y2min:
                        y2min = float(y.min())
                    if y2max is None or y.max() > y2max:
                        y2max = float(y.max())

        for hist in resolution.visible(ax.hists):
            if not _on_y2(hist):
                continue
            hy0, hy1 = self._histogram_y_extent(hist, positive_only)
            if hy0 is None:
                continue
            if y2min is None or hy0 < y2min:
                y2min = hy0
            if y2max is None or hy1 > y2max:
                y2max = hy1

        return y2min, y2max

    def _get_data_x2lim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Secondary-x limits from the series drawn against x2.

        Same role as :meth:`_get_data_y2lim`: the top scale is left to GLE
        unless a log axis has to be given a positive range. Series on the
        primary x axis do not contribute, and these series do not contribute
        to that primary range either (see :meth:`_get_data_xlim`).
        """
        resolution = resolution or SourceResolution()
        x2min, x2max = None, None

        def _take(values: np.ndarray) -> None:
            nonlocal x2min, x2max
            values = _plottable(values, positive_only)
            if len(values) == 0:
                return
            lo = float(values.min())
            hi = float(values.max())
            if x2min is None or lo < x2min:
                x2min = lo
            if x2max is None or hi > x2max:
                x2max = hi

        for data_list in (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.errorbars),
        ):
            for data in data_list:
                if data.get("xaxis") != "x2":
                    continue
                x = np.asarray(data["x"], dtype=float)
                pieces = [x]
                if data.get("xerr_left") is not None:
                    pieces.append(x - np.asarray(data["xerr_left"], dtype=float))
                if data.get("xerr_right") is not None:
                    pieces.append(x + np.asarray(data["xerr_right"], dtype=float))
                _take(np.concatenate(pieces) if len(pieces) > 1 else x)

        for hist in resolution.visible(ax.hists):
            if hist.get("xaxis") != "x2":
                continue
            lo = hist.get("hist_from")
            hi = hist.get("hist_to")
            if lo is None or hi is None or not (float(hi) > float(lo)):
                _take(np.asarray(hist["samples"], dtype=float))
            else:
                _take(np.array([float(lo), float(hi)], dtype=float))

        return x2min, x2max

    @staticmethod
    def _histogram_y_extent(hist, positive_only: bool):
        """``(ymin, ymax)`` of one histogram's counts, or ``(None, None)``.

        The step outline and the bars both stand on zero, so a linear axis
        includes 0. A log axis cannot, and an all-zero histogram has nothing
        to show -- leaving the range unset lets a degenerate axis defer to
        GLE instead of writing ``min 0 max 0``.
        """
        counts = histogram_counts(
            hist["samples"],
            hist.get("hist_from"),
            hist.get("hist_to"),
            bins=hist.get("bins"),
            bin_step=hist.get("bin_step"),
        )
        if counts is None or len(counts) == 0 or float(np.max(counts)) == 0.0:
            return None, None
        if positive_only:
            positive = counts[counts > 0]
            if len(positive) == 0:
                return None, None
            return float(positive.min()), float(positive.max())
        return 0.0, float(np.max(counts))

    def view(self, dpi: Optional[int] = None, format: str = "png") -> Optional[object]:
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
            Path to the generated temporary file, or None when the figure was
            displayed inline in Jupyter. Nothing is printed; outside a notebook,
            open the returned path to see the figure. A PDF cannot be shown
            inline, so in a notebook ``format='pdf'`` warns and returns the path.
            The ``.gle`` script and data files compiled to make the image are
            removed; only the returned file is left, for the caller to delete.

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
        import shutil
        import tempfile

        if not self.compiler:
            raise RuntimeError("GLE compiler not available. Install GLE to use view().")

        output_dpi = dpi or self.dpi

        # Try to detect Jupyter/IPython environment
        try:
            from IPython import get_ipython
            from IPython.display import Image, display

            ipython = get_ipython()
            in_notebook = ipython is not None and "IPKernelApp" in get_ipython().config
        except ImportError:
            in_notebook = False

        # savefig writes the script, its sidecars and (for usetex) GLE's .gle/
        # working folder beside the output, so compile in a directory that is
        # removed afterwards and copy out only the file view() returns. The
        # removal ignores errors: on Windows a file can still be locked by GLE.
        work_dir = tempfile.mkdtemp()
        try:
            output = self.savefig(
                str(Path(work_dir) / f"figure.{format}"), format=format, dpi=output_dpi
            )
            if in_notebook and format == "png":
                display(Image(data=output.read_bytes(), format="png"))
                return None
            with tempfile.NamedTemporaryFile(suffix=output.suffix, delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copyfile(output, tmp_path)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        if in_notebook:
            warn_external(
                f"view(format={format!r}) cannot display {format.upper()} "
                f"inline; it was saved to {tmp_path}, which view() returns. "
                f"Use view(format='png') to display the figure in the notebook.",
            )
        return tmp_path

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the figure to a JSON-safe project dictionary.

        Produces the full, lossless object-model representation used by the
        project-file format and (later) undo/redo snapshots. The result is a
        top-level envelope::

            {
                "format": "gleplot-project",
                "version": 1,
                "gleplot_version": <installed gleplot version>,
                "figure": { ... }
            }

        The ``figure`` block captures figure-level parameters (``figsize``,
        ``dpi``, ``sharex``, ``sharey``, ``data_prefix``), the data-file
        naming state, subplot layout overrides, unrecognized-content
        passthrough buckets (``passthrough_header``, ``passthrough_trailer``)
        and metadata-block passthrough (``metadata_extra``), the per-figure
        style / graph / marker configuration overrides (serialized via each
        config's own ``to_dict``), and every axes with all of its series and
        state (including its own ``passthrough`` bucket) via
        :meth:`Axes.to_dict`.

        Only authoritative state is serialized. Axis limits are serialized as
        they currently sit on each axes: limits explicitly set by the user are
        captured, while limits left unset remain ``None`` and are re-derived
        from data at GLE-generation time -- keeping the format independent of
        that (order-dependent, potentially expensive) derivation. Calling
        ``to_dict`` twice on an unchanged figure yields an identical dict.

        The generated-series ``data_file`` names and the figure's set of used
        data-file names are round-tripped exactly, so regenerated GLE does not
        depend on the module-global data-file counter. The counter's current
        value is nonetheless also saved (``global_data_counter``) so that
        continued plotting after :meth:`from_dict` in a fresh process picks up
        where the original session left off instead of restarting at 0 and
        colliding with (or duplicating) previously used ``data_N.dat`` names.
        The contour/heatmap/fitz sidecar counters get the same treatment
        (``sidecar_counters`` for a figure with a custom ``data_prefix``,
        ``global_sidecar_counters`` for the shared default-prefix counter --
        see ``axes._reserve_sidecar``), so a figure reloaded via
        :meth:`from_dict` and then given a new contour/heatmap series keeps
        numbering forward rather than restarting at ``1``.

        Returns
        -------
        dict
            JSON-serializable project dictionary.
        """
        from . import __version__

        figure_block = {
            "figsize": list(self.figsize),
            "dpi": self.dpi,
            "sharex": self.sharex,
            "sharey": self.sharey,
            "data_prefix": self.data_prefix,
            "local_data_counter": self._local_data_counter,
            "global_data_counter": _axes_module._global_data_file_counter,
            "used_data_files": sorted(self._used_data_files),
            "sidecar_counters": dict(getattr(self, "_sidecar_counters", {}) or {}),
            "global_sidecar_counters": dict(_axes_module._global_sidecar_counters),
            "subplot_adjust": {k: float(v) for k, v in self._subplot_adjust.items()},
            "height_ratios": (
                list(self.height_ratios) if self.height_ratios is not None else None
            ),
            "width_ratios": (
                list(self.width_ratios) if self.width_ratios is not None else None
            ),
            "passthrough_before_hei": list(self.passthrough_before_hei),
            "passthrough_header": list(self.passthrough_header),
            "passthrough_trailer": list(self.passthrough_trailer),
            "page_box": self.page_box,
            "drawings": [_json_drawing(d) for d in self._drawings],
            "metadata_extra": dict(self.metadata_extra),
            "config": {
                "style": self.style.to_dict(),
                "graph": self.graph.to_dict(),
                "marker": self.marker_config.to_dict(),
            },
            "axes": [ax.to_dict() for ax in self.axes_list],
            # Broken-axis assemblies reference their segments by index into
            # "axes" (the segments themselves are serialized there in full).
            "broken_axes": [bax.to_dict() for bax in self.broken_axes],
        }
        # Figure-level text and legend, only when set: a figure without them
        # keeps the snapshot it always had.
        if self._suptitle is not None:
            figure_block["suptitle"] = dict(self._suptitle)
        if self.texts:
            figure_block["texts"] = [dict(text) for text in self.texts]
        if self._legend is not None:
            figure_block["legend"] = _json_drawing(
                {**self._legend, "spacing": dict(self._legend["spacing"])}
            )

        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_VERSION,
            "gleplot_version": __version__,
            "figure": figure_block,
        }

    def requires_cairo(self) -> bool:
        """Whether rendering this figure needs GLE's ``-cairo`` device flag.

        True whenever the figure uses semi-transparency anywhere it can
        appear -- a ``fill_between``/``fill``/``axvspan``/``axhspan`` with
        ``alpha < 1`` (:meth:`Axes.fill_between`, :meth:`Axes.fill`,
        :meth:`Axes.axvspan`, :meth:`Axes.axhspan`), or any colour
        expressed directly as
        ``rgba(...)``/``rgba255(...)``. See
        :func:`gleplot.cairo_support.figure_requires_cairo` for the exact
        rule and :func:`gleplot.compiler.build_compile_args` for where the
        answer turns into a compiler flag.

        Built on :meth:`to_dict` (per SPEC's "render always works from a
        to_dict() snapshot" rule) rather than a live-model walk; axvspan/
        axhspan declarations carry their ``alpha`` from the moment they're
        created, so this sees them correctly even though their concrete x/y
        coordinates are only materialized later, at write time
        (:meth:`Axes.materialize_spans`).

        Returns
        -------
        bool
        """
        return figure_requires_cairo(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "Figure":
        """Reconstruct an equivalent :class:`Figure` from a project dict.

        Parameters
        ----------
        d : dict
            A project dictionary as produced by :meth:`to_dict`.

        Returns
        -------
        Figure
            A figure equivalent to the one that was serialized: round-tripping
            through :meth:`to_dict` reproduces an equal dictionary and
            regenerated GLE (with the same ``data_prefix``) is byte-identical.

        Raises
        ------
        ValueError
            If the envelope ``format`` is missing/unrecognized or the
            ``version`` is unsupported.

        Notes
        -----
        Unknown keys inside the envelope, the ``figure`` block, and the
        ``config`` sub-dicts (``style``/``graph``/``marker``) are ignored for
        forward compatibility.

        The module-global data-file counter (used to name auto-generated
        ``data_N.dat`` series when a figure has no custom ``data_prefix``) is
        restored to ``max(current in-process value, saved value)``. Taking
        the max means that in a fresh process this simply continues the
        saved sequence, while in a long-running process with other figures
        already using the counter, it never rewinds and risks a future
        collision.
        """
        fmt = d.get("format")
        if fmt != PROJECT_FORMAT:
            raise ValueError(
                f"Unrecognized project format {fmt!r}; expected {PROJECT_FORMAT!r}"
            )
        version = d.get("version")
        if version not in SUPPORTED_PROJECT_VERSIONS:
            raise ValueError(
                f"Unsupported project version {version!r}; this build supports "
                f"version(s) {', '.join(str(v) for v in SUPPORTED_PROJECT_VERSIONS)}"
            )

        fig_block = d.get("figure")
        if not isinstance(fig_block, dict):
            raise ValueError("Project envelope is missing a 'figure' object")

        config = fig_block.get("config") or {}
        style = (
            GLEStyleConfig(
                **_filtered_dataclass_kwargs(GLEStyleConfig, config["style"])
            )
            if config.get("style")
            else None
        )
        graph = _saved_graph_config(config["graph"]) if config.get("graph") else None
        marker = (
            GLEMarkerConfig(
                **_filtered_dataclass_kwargs(GLEMarkerConfig, config["marker"])
            )
            if config.get("marker")
            else None
        )

        figsize = fig_block.get("figsize", (8, 6))
        figsize = tuple(figsize)

        fig = cls(
            figsize=figsize,
            dpi=fig_block.get("dpi", 100),
            style=style,
            graph=graph,
            marker=marker,
            sharex=fig_block.get("sharex", False),
            sharey=fig_block.get("sharey", False),
            height_ratios=fig_block.get("height_ratios"),
            width_ratios=fig_block.get("width_ratios"),
        )

        # Restore the prefix verbatim, bypassing __init__'s validation. This is
        # recorded state, not a user-supplied value: the recognizer derives a
        # prefix from filenames already present in a parsed .gle, and those can
        # legitimately contain characters __init__ rejects (a quoted
        # 'data "my file_0.dat"' yields the prefix 'my file'). Re-validating
        # here would make such a figure impossible to round-trip -- and would
        # break snapshots restored through ``from_dict``.
        fig.data_prefix = fig_block.get("data_prefix")

        fig._local_data_counter = fig_block.get("local_data_counter", 0)
        fig._used_data_files = set(fig_block.get("used_data_files", []))
        fig._sidecar_counters = dict(fig_block.get("sidecar_counters") or {})
        fig._subplot_adjust = {
            k: float(v) for k, v in (fig_block.get("subplot_adjust") or {}).items()
        }
        fig.passthrough_before_hei = list(fig_block.get("passthrough_before_hei", []))
        fig.passthrough_header = list(fig_block.get("passthrough_header", []))
        fig.passthrough_trailer = list(fig_block.get("passthrough_trailer", []))
        fig.page_box = bool(fig_block.get("page_box", False))
        fig._drawings = [_json_drawing(d) for d in fig_block.get("drawings", [])]
        suptitle = fig_block.get("suptitle")
        fig._suptitle = (
            None
            if suptitle is None
            else cast(TextAnnotation, TextAnnotation._restore(suptitle))
        )
        fig.texts = [
            cast(TextAnnotation, TextAnnotation._restore(t))
            for t in fig_block.get("texts", [])
        ]
        legend = fig_block.get("legend")
        fig._legend = (
            None
            if legend is None
            else {**_json_drawing(legend), "spacing": dict(legend["spacing"])}
        )
        fig.metadata_extra = dict(fig_block.get("metadata_extra", {}))

        saved_counter = fig_block.get("global_data_counter", 0)
        _axes_module._global_data_file_counter = max(
            _axes_module._global_data_file_counter, saved_counter
        )

        # Same "never rewind" treatment for the global sidecar (contour/
        # heatmap/fitz) counters (G8): take the per-kind max so continued
        # plotting in this process picks up past the highest index either
        # side has seen, instead of risking a future collision.
        saved_sidecar_counters = fig_block.get("global_sidecar_counters") or {}
        for _kind, _saved_idx in saved_sidecar_counters.items():
            _axes_module._global_sidecar_counters[_kind] = max(
                _axes_module._global_sidecar_counters.get(_kind, 0), _saved_idx
            )

        fig.axes_list = [
            Axes.from_dict(fig, ax_d) for ax_d in fig_block.get("axes", [])
        ]
        # Rebind the broken-axis groupings once every segment exists; this also
        # restores each segment's ``_break_owner`` back-reference (the one
        # piece of segment state Axes.from_dict cannot recover on its own).
        fig.broken_axes = [
            BrokenAxes.from_dict(fig, b_d) for b_d in fig_block.get("broken_axes", [])
        ]
        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

        return fig

    def close(self):
        """Close figure."""
        self.axes_list.clear()
        self.broken_axes.clear()
        self._drawings.clear()
        self._suptitle = None
        self.texts.clear()
        self._legend = None
        self._current_axes = None

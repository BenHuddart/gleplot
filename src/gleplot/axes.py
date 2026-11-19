"""Axes class for gleplot."""

import functools
import math
import os
import re
import uuid
from numbers import Real
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

import numpy as np

from ._warn import warn_external, warn_unsupported_keywords
from .colors import _rgba_parts, apply_alpha, hatch_to_gle, rgb_to_gle
from .config import LINE_CAPS, LINE_JOINS, GlobalConfig
from .markers import MATPLOTLIB_TO_GLE_MARKERS, get_gle_marker, resolve_marker_fill
from .mathtext import mathtext_to_gle
from .palettes import canonical_cmap
from .parser.tables import (
    FIT_MODEL_TO_ROUTINE,
    FIT_PLACEHOLDER_RE,
    FIT_PLACEHOLDER_SPEC_RE,
    FIT_RESULT_PLACEHOLDERS,
    KEY_POSITIONS_LONG_TO_SHORT,
    KEY_POSITIONS_SHORT_TO_LONG,
    LEGEND_SPACING_TO_KEY,
    LOG_LABEL_MODES,
    MATPLOTLIB_TO_LSTYLE,
    MPL_ARROWSTYLE_TO_GLE,
    NUMBER_FORMAT_KEYWORDS,
    TEXT_HA_VALUES,
    TEXT_VA_VALUES,
    resolve_line_mode,
)
from .parser.units import capsize_pt_to_cm, fontsize_pt_to_cm, markersize_to_msize
from .series import (  # noqa: F401  (re-exported: historical import path)
    _DATASET_NAME_RE,
    DRAWABLE_CLASSES,
    SERIES_ATTRS,
    SERIES_CLASSES,
    BarSeries,
    Box,
    ContourSeries,
    DerivedSeries,
    ErrorbarSeries,
    FileSeries,
    FillSeries,
    FitSeries,
    FunctionSeries,
    HeatmapSeries,
    HistSeries,
    LineSeries,
    PlacedImage,
    RefLine,
    Rug,
    ScatterSeries,
    Series,
    Span,
    TextAnnotation,
    Wedge,
    _build_column_names,
    _build_errorbar_column_names,
    _looks_numeric,
    _unique_column_names,
    is_visible,
    sanitize_column_name,
    sorted_zorder_drawables,
)
from .writer import (
    CONTOURF_EXTENDS,
    RUG_EDGES,
    GLEWriter,
    contourf_bands_fit,
    image_sub_name,
)

_Method = TypeVar("_Method", bound=Callable[..., Any])


def _cartesian_only(method: _Method) -> _Method:
    """Make ``method`` raise ``NotImplementedError`` on a polar axes."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._polar:
            raise NotImplementedError(
                f"{method.__name__}() is not supported on a polar axes. A polar "
                "axes draws plot(), scatter() and function() curves; see the "
                "plot types guide."
            )
        return method(self, *args, **kwargs)

    return cast(_Method, wrapper)


def _text_fields(
    style,
    caller,
    x,
    y,
    s,
    *,
    color,
    fontsize,
    ha,
    va,
    bbox,
    rotation,
    kwargs,
    supported,
) -> Dict[str, Any]:
    """Validated :class:`TextAnnotation` fields for ``text``/``annotate``.

    ``caller`` names the public method in warnings, which are attributed
    to that method's caller, and ``supported`` lists its keywords for the
    warning about the rest. ``style`` is the figure's
    :class:`~gleplot.config.GLEStyleConfig`: under ``usetex`` the text is
    stored as given, for LaTeX, else as GLE markup, and a matplotlib size
    name is relative to its font size.
    """
    if color is None:
        gle_color = "BLACK"
    else:
        gle_color = rgb_to_gle(color)

    ha_norm = str(ha).strip().lower()
    if ha_norm not in TEXT_HA_VALUES:
        warn_external(
            f"{caller}(ha={ha!r}) is not supported; using 'left'. "
            f"Supported values: {', '.join(repr(v) for v in TEXT_HA_VALUES)}.",
        )
        ha_norm = "left"

    va_norm = str(va).strip().lower()
    if va_norm not in TEXT_VA_VALUES:
        warn_external(
            f"{caller}(va={va!r}) is not supported; using 'center'. "
            "GLE aligns text to its top, center, or bottom "
            f"({', '.join(repr(v) for v in TEXT_VA_VALUES)}); "
            "there is no separate baseline.",
        )
        va_norm = "center"

    # Same cut as the writer's ``_format_number``: an angle that would
    # print as ``0`` is not stored, so the dict stays free of a rotation
    # key the script will not mention.
    angle = None
    if rotation is not None:
        try:
            angle = float(rotation)
        except (TypeError, ValueError):
            warn_external(
                f"{caller}(rotation={rotation!r}) is not a number and was " "ignored.",
            )
            angle = None
        else:
            if not np.isfinite(angle):
                warn_external(
                    f"{caller}(rotation={rotation!r}) is not finite and was "
                    "ignored.",
                )
                angle = None
            elif abs(angle) < 1e-10:
                angle = None

    box_color = None
    if bbox is not None and not isinstance(bbox, dict):
        warn_external(
            f"{caller}(bbox={bbox!r}) is not a dict and was ignored. "
            "Pass bbox={'facecolor': ...} to draw a filled background.",
        )
    elif isinstance(bbox, dict):
        if "facecolor" in bbox:
            facecolor = bbox.get("facecolor")
        elif "fill" in bbox:
            facecolor = bbox.get("fill")
        else:
            facecolor = None
        unsupported = sorted(key for key in bbox if key not in ("facecolor", "fill"))
        if unsupported:
            warn_external(
                f"{caller}(bbox=...) ignores "
                f"{unsupported}: only facecolor (alias fill) is emitted, "
                "as GLE 'begin box fill'. The outline, pad, and box "
                "style have no separate setting.",
            )
        if facecolor is None:
            warn_external(
                f"{caller}(bbox=...) has no facecolor; no background box " "was drawn.",
            )
        else:
            box_color = rgb_to_gle(facecolor)

    for name in sorted(kwargs):
        warn_external(
            f"{caller}({name}=...) is not supported and was ignored. "
            f"Supported arguments: {supported}.",
        )

    fields = dict(
        x=float(x),
        y=float(y),
        text=str(s) if style.usetex else mathtext_to_gle(str(s)),
        color=gle_color,
        fontsize=(
            None
            if fontsize is None
            else (
                _resolve_fontsize(style, fontsize, f"{caller}(fontsize")
                if isinstance(fontsize, str)
                and fontsize.strip().lower() in MATPLOTLIB_RELATIVE_FONTSIZES
                else float(fontsize)
            )
        ),
        ha=ha_norm,
        va=va_norm,
        box_color=box_color,
    )
    if angle is not None:
        fields["rotation"] = angle
    return fields


def _resolve_fontsize(style, fontsize, argument: str = "legend(fontsize") -> float:
    """Resolve a matplotlib ``fontsize`` (number or name) to points.

    ``argument`` is the call up to the value, e.g. ``"legend(fontsize"``,
    and names the argument in the error. A name is relative to ``style``'s
    font size.
    """
    if isinstance(fontsize, str):
        name = fontsize.strip().lower()
        if name not in MATPLOTLIB_RELATIVE_FONTSIZES:
            raise ValueError(
                f"{argument}={fontsize!r}) is not a number or one of "
                f"{sorted(MATPLOTLIB_RELATIVE_FONTSIZES)}"
            )
        return float(style.fontsize) * MATPLOTLIB_RELATIVE_FONTSIZES[name]
    size = _finite_float(fontsize, f"{argument}=...)")
    if size <= 0:
        raise ValueError(f"{argument}={fontsize!r}) must be positive")
    return size


class _Transform:
    """``Axes.transAxes`` / ``Axes.transData``: a coordinate system ``text`` reads.

    Only a marker. gleplot draws no transform itself: the GLE script places
    axes-fraction text against the graph box GLE drew.
    """

    __slots__ = ("axes", "kind")

    def __init__(self, axes: "Axes", kind: str):
        self.axes = axes
        self.kind = kind

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Transform):
            return NotImplemented
        return self.axes is other.axes and self.kind == other.kind

    def __hash__(self) -> int:
        return hash((id(self.axes), self.kind))

    def __repr__(self) -> str:
        return f"<gleplot {self.kind} transform>"


# Global counter for unique data file names across all figures in a session
_global_data_file_counter = 0

#: Global, per-kind counters for contour/heatmap/fitz sidecar reservations
#: (``kind`` in ``{'heatmap', 'contour', 'points'}``) made by figures that use
#: the default ``data_`` prefix -- the ``_reserve_sidecar`` analogue of
#: ``_global_data_file_counter`` above. A figure with a *custom*
#: ``data_prefix`` keeps its own per-figure counters instead (see
#: ``_reserve_sidecar``): a caller who sets distinct prefixes per figure has
#: already opted into predictable, figure-local numbering, exactly as for
#: plain ``data_N.dat`` series. Figures left on the default prefix have not,
#: so they share this counter -- the fix for G8's cross-figure stem
#: uniqueness requirement (GLEstudio SPEC 9.1/10.8): two default-prefix
#: figures compiled into the same directory no longer both try to write
#: ``data_contour1.z``.
_global_sidecar_counters: Dict[str, int] = {}

#: The range GLE itself renders for a graph block that gives no bounds for an
#: axis, measured on GLE 4.3.10 (``begin graph`` / ``size`` / ``scale 1 1`` /
#: ``end graph`` followed by ``print xgmin xgmax ygmin ygmax`` -> ``0 1 0 1``)
#: and pinned by ``tests/integration/test_refline_fallback_compiles.py``.
#:
#: G14 used it as the stand-in range to *materialize* a guide over when the
#: axis it spans resolved to nothing. Since G17 such a guide is emitted as a
#: ``draw`` reading GLE's own ``xgmin``/``ygmax`` instead
#: (:mod:`gleplot.guides`), so the constant no longer decides where anything
#: lands: it survives as the measured statement of what an unbounded GLE axis
#: does -- the value the draw form reproduces by construction on a truly empty
#: axes -- and as the safety net in :meth:`Axes._spanned_range`.
EMPTY_AXIS_FALLBACK_RANGE = (0.0, 1.0)

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

#: Default ``zorder`` per drawable series kind when the caller omits one.
#: Derived from the series classes, which own the value
#: (``LineSeries.ZORDER_DEFAULT``, ...). gleplot itself reads the classes
#: directly; this mapping is kept as public API for callers that present the
#: defaults.
SERIES_ZORDER_DEFAULT: Dict[str, float] = {
    kind: float(cls.ZORDER_DEFAULT or 0.0) for kind, cls in DRAWABLE_CLASSES.items()
}

#: matplotlib's relative font-size names as multipliers of the base font size
#: (matplotlib ``font_manager.font_scalings``). Used to resolve
#: ``legend(fontsize='small')`` against the figure style's fontsize.
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


def _is_one_color(color) -> bool:
    """True for one colour, false for a per-bar sequence.

    An RGB(A) tuple is one colour. A list of names, or a longer array, is
    a sequence.
    """
    if isinstance(color, str):
        return True
    if isinstance(color, np.ndarray):
        return color.ndim == 0 or (
            color.ndim == 1
            and color.size in (3, 4)
            and np.issubdtype(color.dtype, np.number)
        )
    if isinstance(color, (tuple, list)):
        return (
            bool(color)
            and len(color) in (3, 4)
            and isinstance(color[0], (int, float, np.integer, np.floating))
        )
    return False


def _gle_bar_color(color) -> str:
    """A bar colour as a GLE token. ``'none'`` stays ``none``."""
    if isinstance(color, str) and color.strip().lower() == "none":
        return "none"
    return rgb_to_gle(color)


def _bar_color_list(color, n: int, default: Optional[str]) -> List[Optional[str]]:
    """One face or edge colour per bar.

    ``None`` repeats ``default`` (itself ``None`` when the caller omitted
    the edge). A sequence of one broadcasts. Any other length must match
    the bars.
    """
    if color is None:
        return [default] * n
    if _is_one_color(color):
        return [_gle_bar_color(color)] * n
    seq = list(color)
    if len(seq) == 1:
        return [_gle_bar_color(seq[0])] * n
    if len(seq) != n:
        raise ValueError(
            f"color sequence length {len(seq)} does not match the {n} bars"
        )
    return [_gle_bar_color(item) for item in seq]


def _bar_patterns(hatch, n: int) -> List[Optional[str]]:
    """One GLE pattern (or ``None``) per bar, as matplotlib cycles ``hatch``.

    A sequence must have one entry, or one per bar. A hatch GLE cannot
    draw warns and that bar stays solid.
    """
    if hatch is None:
        return [None] * n
    if isinstance(hatch, str):
        items = [hatch]
    else:
        try:
            items = list(hatch)
        except TypeError:
            raise TypeError(
                "bar() hatch must be a string such as '//', or a sequence of "
                f"them; got {hatch!r}"
            ) from None
    if len(items) not in (1, n):
        raise ValueError(
            f"bar() hatch sequence length {len(items)} does not match the {n} bars"
        )
    patterns: List[Optional[str]] = []
    unsupported: List[str] = []
    for item in items:
        if item is None or item == "":
            patterns.append(None)
            continue
        if not isinstance(item, str):
            raise TypeError(
                "bar() hatch must be a string such as '//', or a sequence of "
                f"them; got {item!r}"
            )
        pattern = hatch_to_gle(item)
        if pattern is None and item not in unsupported:
            unsupported.append(item)
        patterns.append(pattern)
    if unsupported:
        names = ", ".join(repr(item) for item in unsupported)
        warn_external(
            f"bar() hatch {names} has no GLE pattern; those bars are drawn "
            "solid. GLE hatches diagonally only: use '/', '\\\\' or 'x', "
            "repeated (e.g. '//') for a denser hatch.",
        )
    return patterns * n if len(patterns) == 1 else patterns


def _bar_style_aliases(kwargs, color, edgecolor, linewidth, linestyle):
    """Pull matplotlib's short names out of ``kwargs``.

    ``color`` wins over ``facecolor`` / ``fc`` / ``c``. The same for
    ``edgecolor`` over ``ec``, ``linewidth`` over ``lw``, and ``linestyle``
    over ``ls``.
    """

    def take(*names):
        found = None
        hit = False
        for name in names:
            if name not in kwargs:
                continue
            value = kwargs.pop(name)
            if not hit:
                found = value
                hit = True
        return found, hit

    face, saw_face = take("facecolor", "fc", "c")
    if saw_face and color is not None:
        warn_external(
            "bar() got both color and facecolor; color wins.",
        )
    elif color is None and saw_face:
        color = face
    edge, saw_edge = take("ec")
    if saw_edge and edgecolor is not None:
        warn_external(
            "bar() got both edgecolor and ec; edgecolor wins.",
        )
    elif edgecolor is None and saw_edge:
        edgecolor = edge
    width, saw_width = take("lw")
    if saw_width and linewidth is not None:
        warn_external(
            "bar() got both linewidth and lw; linewidth wins.",
        )
    elif linewidth is None and saw_width:
        linewidth = width
    style, saw_style = take("ls")
    if saw_style and linestyle is not None:
        warn_external(
            "bar() got both linestyle and ls; linestyle wins.",
        )
    elif linestyle is None and saw_style:
        linestyle = style
    return color, edgecolor, linewidth, linestyle


def _bar_baseline(bottom, n: int):
    """The baseline array, or ``None`` when the bars start at zero.

    An all-zero baseline is matplotlib's default and is not stored, so a
    ``bottom=0`` chart keeps the historical script.
    """
    if bottom is None:
        return None
    arr = np.asarray(bottom, dtype=float)
    if arr.ndim == 0:
        if not np.isfinite(arr):
            raise ValueError("bar() bottom must be finite")
        if float(arr) == 0.0:
            return None
        return np.full(n, float(arr))
    flat = arr.ravel()
    if flat.size != n:
        raise ValueError(f"bar() bottom length {flat.size} does not match the {n} bars")
    if not np.all(np.isfinite(flat)):
        raise ValueError("bar() bottom must be finite")
    if np.all(flat == 0):
        return None
    return flat


def _bar_edge_style(linewidth, linestyle) -> dict:
    """Scalar edge width and linestyle. A sequence warns and keeps the first."""
    result: Dict[str, Any] = {}
    if linewidth is not None:
        if np.ndim(linewidth) != 0:
            warn_external(
                "bar() linewidth is one number per dataset; the first value "
                "is used.",
            )
            linewidth = np.ravel(np.asarray(linewidth, dtype=float))[0]
        value = float(linewidth)
        if not np.isfinite(value):
            raise ValueError("bar() linewidth must be finite")
        result["linewidth"] = value
    if linestyle is not None:
        if not isinstance(linestyle, str):
            warn_external(
                "bar() linestyle is one style per dataset; the first value " "is used.",
            )
            linestyle = list(linestyle)[0]
        key = str(linestyle).strip().lower()
        key = {
            "solid": "-",
            "dashed": "--",
            "dotted": ":",
            "dashdot": "-.",
        }.get(key, key)
        if key not in ("-", "--", ":", "-.", "none"):
            warn_external(
                f"bar() linestyle {linestyle!r} is not a GLE edge style; "
                "the edge stays solid.",
            )
        else:
            result["linestyle"] = key
    return result


def _bar_width_for_split(x: np.ndarray) -> float:
    """Thickness of each piece when one ``bar()`` call becomes several.

    A one-point dataset has no gap, so GLE cannot derive a width. Use the
    width the combined set would have been given: half the smallest positive
    gap, or the nominal ``0.5`` when there is none.
    """
    derived = GLEWriter.bar_width_gle_cannot_derive(x)
    if derived is not None:
        return float(derived)
    return float(GLEWriter.gle_bar_min_x_interval(x) / 2.0)


def _bar_error_limits(err, n: int, name: str):
    """``(minus, plus)`` error arrays of length ``n``, or ``(None, None)``.

    Matplotlib's shapes: a scalar, shape ``(n,)`` (symmetric), or shape
    ``(2, n)`` (first row minus, second row plus). A length-1 sequence and
    a shape ``(2, 1)`` broadcast across the bars.
    """
    if err is None:
        return None, None
    try:
        arr = np.asarray(err, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bar() {name} must be numeric") from exc
    if arr.ndim == 0 or (arr.ndim == 1 and arr.size == 1):
        value = float(np.ravel(arr)[0])
        if not np.isfinite(value):
            raise ValueError(f"bar() {name} must be finite")
        filled = np.full(n, value)
        return filled, filled.copy()
    if arr.ndim == 1:
        if arr.size != n:
            raise ValueError(
                f"bar() {name} length {arr.size} does not match the {n} bars"
            )
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"bar() {name} must be finite")
        return arr.copy(), arr.copy()
    if arr.ndim == 2 and arr.shape[0] == 2 and arr.shape[1] in (1, n):
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"bar() {name} must be finite")
        if arr.shape[1] == n:
            return arr[0].copy(), arr[1].copy()
        lower = np.full(n, float(arr[0, 0]))
        upper = np.full(n, float(arr[1, 0]))
        return lower, upper
    raise ValueError(f"bar() {name} must be a scalar, shape ({n},), or shape (2, {n})")


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


def _finite_float(value: Any, what: str) -> float:
    """``value`` as a finite float, or an error naming ``what``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise TypeError(f"{what} must be a number, got {value!r}") from None
    if not np.isfinite(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return number


def _count(value: Any, what: str) -> int:
    """``value`` as a positive whole number; ``what`` is ``"method(name"``."""
    number = _finite_float(value, f"{what}=...)")
    if isinstance(value, bool) or not number.is_integer() or number < 1:
        raise ValueError(f"{what}={value!r}) must be a positive whole number")
    return int(number)


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


#: matplotlib's ``MaxNLocator`` default steps, extended a decade either way
#: (``MaxNLocator._staircase``).
_LOCATOR_STEPS = np.array(
    [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8]
    + [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 15]
)


def _nice_levels(zmin: float, zmax: float, n: int, extend: str) -> List[float]:
    """The filled-contour levels matplotlib's ``contourf(levels=n)`` picks.

    A port of ``MaxNLocator(n + 1, min_n_ticks=1).tick_values`` and
    ``ContourSet._autolev`` for a linear scale: round-number levels that
    span ``zmin`` to ``zmax``, one past each end trimmed off, and with
    ``extend`` the outermost level on that side dropped so the extended
    band holds the rest.
    """
    nbins = n + 1
    lo, hi = float(zmin), float(zmax)
    # matplotlib.transforms._nonsingular(expander=1e-13, tiny=1e-14)
    biggest = max(abs(lo), abs(hi))
    if biggest < 1e20 * np.finfo(float).tiny:
        lo, hi = -1e-13, 1e-13
    elif hi - lo <= biggest * 1e-14:
        if hi == 0 and lo == 0:
            lo, hi = -1e-13, 1e-13
        else:
            lo, hi = lo - 1e-13 * abs(lo), hi + 1e-13 * abs(hi)
    # matplotlib.ticker.scale_range
    span = hi - lo
    mean = (hi + lo) / 2
    if abs(mean) / span < 100:
        offset = 0.0
    else:
        offset = math.copysign(10 ** (math.log10(abs(mean)) // 1), mean)
    scale = 10 ** (math.log10(span / nbins) // 1)
    lo, hi = lo - offset, hi - offset
    steps = _LOCATOR_STEPS * scale
    large = np.nonzero(steps >= (hi - lo) / nbins)[0]
    istep = large[0] if len(large) else len(steps) - 1
    # ticker._Edge_integer: more slop when the offset dwarfs the step.
    for step in steps[: istep + 1][::-1]:
        tol = 1e-10
        if offset:
            tol = min(0.4999, max(1e-10, 10 ** (np.log10(abs(offset) / step) - 12)))
        best = (lo // step) * step
        d, m = divmod(lo - best, step)
        low = d + 1 if abs(m / step - 1) < tol else d
        d, m = divmod(hi - best, step)
        high = d if abs(m / step) < tol else d + 1
        ticks = np.arange(low, high + 1) * step + best
        if ((ticks <= hi) & (ticks >= lo)).sum() >= 1:
            break
    lev = ticks + offset
    under = np.nonzero(lev < zmin)[0]
    i0 = under[-1] if len(under) else 0
    over = np.nonzero(lev > zmax)[0]
    i1 = over[0] + 1 if len(over) else len(lev)
    if extend in ("min", "both"):
        i0 += 1
    if extend in ("max", "both"):
        i1 -= 1
    if i1 - i0 < 3:
        i0, i1 = 0, len(lev)
    return [float(v) for v in lev[i0:i1]]


def _axis_from_meshgrid(
    arr: np.ndarray, name: str, call: str, scattered: str
) -> np.ndarray:
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
    call : str
        The call the error names, such as ``'contour(X, Y, Z)'``.
    scattered : str
        The call the error suggests for scattered data instead.

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
            f"{call}: the 2-D {name.upper()} is constant along its "
            f"{other}, not its {wanted} -- this is the layout of "
            f"np.meshgrid(..., indexing='ij'). Rebuild the grid with the "
            f"default indexing='xy' (and Z of shape (len(y), len(x))), or "
            f"pass X.T, Y.T and Z.T."
        )
    raise ValueError(
        f"{call}: the 2-D {name.upper()} is not a regular grid (its "
        f"{wanted} are not all identical), so it has no single 1-D {name} "
        f"axis. A GLE .z grid is uniform and rectangular; use {scattered} "
        f"for scattered or irregularly gridded data."
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
    is ``'z'``/``'dat'``. ``N`` is a per-kind, 1-based counter. The reserved
    name is recorded in ``figure._used_data_files`` so it never collides with
    a generated ``data_N.dat`` (or another sidecar) and so it round-trips
    through ``Figure.to_dict``/``from_dict``.

    **Which counter, and why (G8: cross-figure stem uniqueness).** This
    mirrors the existing ``data_prefix`` contract from
    :func:`_get_next_data_file`/:func:`_resolve_data_file`:

    - A figure with a *custom* ``data_prefix`` keeps a per-figure counter
      (``figure._sidecar_counters``), exactly as before. Distinct series
      within that one figure never collide (the counter is monotonic and the
      candidate is re-checked against ``used`` regardless); distinct figures
      are the caller's responsibility to keep apart, same as for
      ``<prefix>_N.dat`` -- give them different prefixes.
    - A figure left on the *default* prefix (``data_prefix is None``, i.e.
      the emitted prefix is the literal ``"data"``) shares the **module-level**
      ``_global_sidecar_counters`` instead of a fresh per-figure one. Two such
      figures compiled into the same directory therefore get distinct
      ``data_contour1.z``/``data_contour2.z`` stems instead of both starting
      at 1 and colliding -- the GLEstudio SPEC 9.1/10.8 requirement ("two
      figures compiled in one directory ... must not collide"). This is the
      same per-process guarantee (not cross-process) that
      ``_global_data_file_counter`` already provides for plain data files.

    ``figure`` is optional only for symmetry with the other reservers; in
    practice a figure is always present when a heatmap/contour series is added.
    """
    has_custom_prefix = bool(figure and figure.data_prefix)
    prefix = figure.data_prefix if has_custom_prefix else "data"

    if has_custom_prefix:
        counters = getattr(figure, "_sidecar_counters", None)
        if counters is None:
            counters = {}
            figure._sidecar_counters = counters
    else:
        counters = _global_sidecar_counters

    used = getattr(figure, "_used_data_files", None) if figure else None
    if figure is not None and used is None:
        used = set()
        figure._used_data_files = used

    idx = counters.get(kind, 0) + 1
    while True:
        name = f"{prefix}_{kind}{idx}.{ext}"
        if used is None or name not in used:
            break
        idx += 1
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


#: The axes-styling attributes added by GLEstudio plan task G10 (tick-label
#: formats, grids, axis-title / tick-label / graph-title styling), in
#: serialization order. All default to ``None`` = "absent, emit nothing", so
#: :meth:`Axes.to_dict` gained keys without any figure's GLE changing. One
#: list drives ``to_dict``, ``from_dict`` and the writer's styling payload,
#: so the three cannot drift apart.
_STYLING_KEYS: Tuple[str, ...] = (
    "xformat",
    "yformat",
    "y2format",
    "x2format",
    "xgrid",
    "ygrid",
    "xgrid_lstyle",
    "xgrid_lwidth",
    "xgrid_color",
    "ygrid_lstyle",
    "ygrid_lwidth",
    "ygrid_color",
    "xlabel_size",
    "xlabel_color",
    "xlabel_dist",
    "ylabel_size",
    "ylabel_color",
    "ylabel_dist",
    "y2label_size",
    "y2label_color",
    "y2label_dist",
    "x2label_size",
    "x2label_color",
    "x2label_dist",
    "xticklabel_size",
    "xticklabel_color",
    "xticklabel_angle",
    "yticklabel_size",
    "yticklabel_color",
    "yticklabel_angle",
    "y2ticklabel_size",
    "y2ticklabel_color",
    "y2ticklabel_angle",
    "x2ticklabel_size",
    "x2ticklabel_color",
    "x2ticklabel_angle",
    "title_size",
    "title_color",
    "title_dist",
    "title_font",
    "xlabel_font",
    "ylabel_font",
    "y2label_font",
    "x2label_font",
    "xside_color",
    "xside_lwidth",
    "yside_color",
    "yside_lwidth",
    "y2side_color",
    "y2side_lwidth",
    "x2side_color",
    "x2side_lwidth",
    "xside_off",
    "yside_off",
    "xnticks",
    "xftick",
    "xshift",
    "xsymticks",
    "xnoticks",
    "ynticks",
    "yftick",
    "yshift",
    "ysymticks",
    "ynoticks",
    "math_mode",
    "xtick_length",
    "xtick_width",
    "xtick_color",
    "xtick_direction",
    "xsubtick_length",
    "xsubtick_width",
    "xsubtick_color",
    "xsubtick_direction",
    "xminorticks",
    "xnsubticks",
    "xloglabels",
    "ytick_length",
    "ytick_width",
    "ytick_color",
    "ytick_direction",
    "ysubtick_length",
    "ysubtick_width",
    "ysubtick_color",
    "ysubtick_direction",
    "yminorticks",
    "ynsubticks",
    "yloglabels",
)

#: The ``which=`` values of :meth:`Axes.tick_params`, as the model's field
#: stems: ``xtick_*`` holds the major ticks, ``xsubtick_*`` the minor ones.
_TICK_KINDS = {"major": ("tick",), "minor": ("subtick",), "both": ("tick", "subtick")}

#: A GLE font name as ``set font`` / ``xtitle ... font`` take it: one bare
#: word such as ``texcmr`` or ``psh``.
_GLE_FONT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def _gle_font_name(fontname: object, method: str) -> str:
    """``fontname`` checked as a GLE font name, for ``method``'s error."""
    if not isinstance(fontname, str):
        raise TypeError(
            f"{method}(fontname=...) must be a GLE font name string such as "
            f"'texcmr', got {fontname!r}"
        )
    if not _GLE_FONT_NAME.match(fontname):
        raise ValueError(
            f"{method}(fontname={fontname!r}) is not a GLE font name: use one "
            "word of letters, digits and underscores, such as 'texcmr' or 'psh'"
        )
    return fontname


def validate_tick_format(fmt: str) -> str:
    """Light validation of a GLE number-format string; returns it stripped.

    Used by :meth:`Axes.set_tick_format` and available to callers building a
    format string interactively (GLEstudio's format preset builder). The
    check is deliberately weak, because GLE's own parser is:
    :data:`gleplot.parser.tables.NUMBER_FORMAT_KEYWORDS` documents that an
    unrecognized specifier is skipped with a printed note, not an error. So
    this only rules out the strings that could not possibly be a format --
    empty, multi-line, or not starting with a keyword GLE knows -- and lets
    everything else (including arguments this version has never seen)
    through unchanged.

    Parameters
    ----------
    fmt : str
        Candidate format string, e.g. ``"fix 1"`` or ``"sci 2 10 expsign"``.

    Returns
    -------
    str
        ``fmt`` with surrounding whitespace removed.

    Raises
    ------
    ValueError
        If ``fmt`` is not a string, is blank, spans multiple lines, or does
        not begin with a GLE number-format keyword.
    """
    if not isinstance(fmt, str):
        raise ValueError(f"format must be a string, got {type(fmt).__name__}")
    text = fmt.strip()
    if not text:
        raise ValueError("format string is empty; use None to clear the format")
    if "\n" in text or "\r" in text:
        raise ValueError(f"format string must be a single line: {fmt!r}")
    first = text.split()[0].lower()
    if first not in NUMBER_FORMAT_KEYWORDS:
        raise ValueError(
            f"format string {fmt!r} does not start with a GLE number-format "
            f"keyword ({', '.join(NUMBER_FORMAT_KEYWORDS)})"
        )
    return text


def _let_expression_problem(expression: str) -> Optional[str]:
    """Why ``expression`` cannot be one expression of a ``let``, or ``None``.

    GLE ends a ``let`` expression at the first space, and reads a comma
    outside brackets as the start of a second (parametric) expression.
    """
    if not expression:
        return "it is empty"
    if any(ch.isspace() for ch in expression):
        return "GLE ends the expression at the first space; remove the spaces"
    for ch in "!;\"'&":
        if ch in expression:
            return f"GLE reads {ch!r} as the end of the expression"
    depth = 0
    for ch in expression:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return "it closes a bracket it never opened"
        elif ch == "," and depth == 0:
            return "a comma outside brackets starts a second expression"
    if depth != 0:
        return "it leaves a bracket open"
    return None


def _function_expression_problem(expression: str) -> Optional[str]:
    """Why ``expression`` cannot be the body of a function ``let``, or ``None``.

    As :func:`_let_expression_problem`, and a dataset name would point at
    whatever dataset gleplot numbers ``dN``.
    """
    problem = _let_expression_problem(expression)
    if problem is None and _DATASET_NAME_RE.search(expression):
        return "it names a dataset (dN); gleplot numbers datasets itself"
    return problem


#: Linestyle spellings that mean "draw no curve". Shared with ``plot``.
_NO_LINE = ("", "none", " ", "None")

#: Single-character colors legal inside a matplotlib format string.
_FMT_COLOR_CHARS = frozenset("bgrcmykw")

#: Single-character markers legal inside a matplotlib format string.
_FMT_MARKERS = frozenset(MATPLOTLIB_TO_GLE_MARKERS)


def _split_plot_format(fmt):
    """``(linestyle, marker, color)`` from a matplotlib format string.

    A missing component is ``None``. A blank string or ``'none'`` returns
    ``('none', 'none', None)``. ``fmt is None`` means the caller did not
    pass a format, which is not the same as ``'none'``.
    """
    if fmt is None:
        return None, None, None
    text = str(fmt).strip()
    if text.lower() in ("", "none"):
        return "none", "none", None
    linestyle = None
    marker = None
    color = None
    i = 0
    n = len(text)
    while i < n:
        pair = text[i : i + 2]
        if pair in ("--", "-."):
            linestyle = pair
            i += 2
            continue
        char = text[i]
        if char in "-:":
            linestyle = char
            i += 1
            continue
        if char == "C" and i + 1 < n and text[i + 1].isdigit():
            color = pair
            i += 2
            continue
        if char in _FMT_COLOR_CHARS:
            color = char
            i += 1
            continue
        if char in _FMT_MARKERS:
            marker = char
            i += 1
            continue
        raise ValueError(f"unrecognized character {char!r} in format string {fmt!r}")
    return linestyle, marker, color


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


def _pop_line_alias(kwargs: dict, caller: str, alias: str, name: str, value, default):
    """``value``, or what ``kwargs`` gives matplotlib's ``alias`` for it.

    The alias is removed from ``kwargs``. ``None`` is matplotlib's "the
    default", for the alias and for ``value`` alike. A ``value`` other than
    ``None`` and its ``default`` was passed by name, and wins over the alias
    with a warning (matplotlib raises for the pair).
    """
    if alias not in kwargs:
        return value
    short = kwargs.pop(alias)
    if short is None:
        return value
    if value is not None and (default is None or value != default):
        warn_external(f"{caller}() got both {name} and {alias}; {name} wins.")
        return value
    return short


def _contour_line_keywords(name: str, linewidths, linestyles, kwargs: dict):
    """``(linewidths, linestyles)`` after matplotlib's singular aliases.

    ``contour`` and ``tricontour`` share this. The plural wins when it is
    not left at its default, else the first alias given; a later name of
    the same pair warns. Consumes ``kwargs``: what is left warns too.
    """
    resolved = []
    for plural, value, default, aliases in (
        ("linewidths", linewidths, 1.0, ("linewidth", "lw")),
        ("linestyles", linestyles, "-", ("linestyle", "ls")),
    ):
        given = value is not None and not (np.ndim(value) == 0 and value == default)
        winner = plural if given else None
        for alias in aliases:
            short = kwargs.pop(alias, None)
            if short is None:
                continue
            if winner is None:
                value, winner = short, alias
            else:
                warn_external(f"{name}() got both {winner} and {alias}; {winner} wins.")
        resolved.append(value)
    warn_unsupported_keywords(name, kwargs)
    return resolved[0], resolved[1]


_MPL_CAPSTYLES = {"butt": "butt", "round": "round", "projecting": "square"}
_MPL_JOINSTYLES = {"miter": "mitre", "round": "round", "bevel": "bevel"}

#: matplotlib's per-line cap and join keywords -> (whether it styles a solid
#: or a dashed line, the GLEStyleConfig field, GLE's default, matplotlib
#: value -> GLE word).
_LINE_END_KEYWORDS = {
    "solid_capstyle": (True, "line_cap", LINE_CAPS[0], _MPL_CAPSTYLES),
    "dash_capstyle": (False, "line_cap", LINE_CAPS[0], _MPL_CAPSTYLES),
    "solid_joinstyle": (True, "line_join", LINE_JOINS[0], _MPL_JOINSTYLES),
    "dash_joinstyle": (False, "line_join", LINE_JOINS[0], _MPL_JOINSTYLES),
}


def _pop_line_ends(kwargs: dict, linestyle, style) -> None:
    """Take matplotlib's cap and join keywords out of a ``plot`` call.

    GLE caps and joins every line in the figure alike (``set cap``/``set
    join``), so a keyword is honoured only when it asks for what the
    figure already draws, and warns otherwise. Like matplotlib, the
    ``solid_*`` keywords concern a solid line, the ``dash_*`` ones a dashed
    line, and neither a series drawn without a line.
    """
    # The writer's own tests: no line for None or a _NO_LINE value, and a
    # dash only where the linestyle maps to an lstyle.
    drawn = linestyle is not None and linestyle not in _NO_LINE
    solid = Axes._linestyle_to_lstyle(linestyle) is None
    for keyword, (for_solid, field, gle_default, words) in _LINE_END_KEYWORDS.items():
        value = kwargs.pop(keyword, None)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(
                f"{keyword} must be a string; got {value!r}. "
                f"Accepted: {list(words)}."
            )
        if value not in words:
            raise ValueError(f"{keyword} must be one of {list(words)}; got {value!r}.")
        if not drawn or solid != for_solid:
            continue
        figure_word = getattr(style, field) or gle_default
        if words[value] != figure_word:
            warn_external(
                f"plot({keyword}={value!r}) is not applied: GLE sets "
                f"{field.replace('_', ' ')}s for the whole figure, which "
                f"draws {figure_word!r}. Pass style=GLEStyleConfig("
                f"{field}={words[value]!r}) to figure() to change every line.",
            )


def histogram_counts(samples, hist_from, hist_to, bins=None, bin_step=None):
    """Bin counts the way GLE's ``let dK = hist`` does (``GLELet::doHistogram``).

    ``bins`` wins over ``bin_step``, matching the engine: a ``bins`` value
    other than "not given" selects equal-width bins and the ``step`` clause
    is ignored. With neither, GLE uses 10 bins. The last bin includes the
    right edge; every other right edge is exclusive. Samples outside
    ``[hist_from, hist_to]`` are not counted.

    Returns ``None`` when the window is missing or empty, which is GLE
    choosing the window itself (axis limits, else a rounded data range).
    Callers that need matplotlib's data range pass that window in.
    """
    if hist_from is None or hist_to is None:
        return None
    lo = float(hist_from)
    hi = float(hist_to)
    if not (hi > lo) or not np.isfinite(lo) or not np.isfinite(hi):
        return None

    if bins is not None:
        n_bins = int(round(float(bins)))
        if n_bins < 1:
            return None
        edges = lo + (hi - lo) * np.arange(n_bins + 1, dtype=float) / n_bins
    elif bin_step is not None:
        step = float(bin_step)
        if not (step > 0) or not np.isfinite(step):
            return None
        # graph2.cpp builds the edges in a loop that steps ``i * step`` from
        # ``from`` so the last edge can sit past ``to`` when step does not
        # divide the window. Recomputing ``from + i*step`` (rather than
        # adding step each time) is what that loop does to avoid drift.
        edges_list = []
        i = 0
        value = lo
        while value < hi:
            edges_list.append(value)
            i += 1
            value = lo + i * step
        edges_list.append(value)
        edges = np.asarray(edges_list, dtype=float)
    else:
        edges = lo + (hi - lo) * np.arange(11, dtype=float) / 10.0

    if len(edges) < 2:
        return None
    values = np.asarray(samples, dtype=float).ravel()
    values = values[np.isfinite(values)]
    counts = np.zeros(len(edges) - 1, dtype=float)
    if len(values) == 0:
        return counts
    # side="right" places a value on the left edge of a bin into that bin
    # (``yv >= edge[j] && yv < edge[j+1]``). The right edge of the window
    # falls past the last edge and is counted into the last bin, which is
    # the ``yv == getTo()`` branch in doHistogram.
    idx = np.searchsorted(edges, values, side="right") - 1
    last = len(counts) - 1
    on_hi = values == hi
    inside = (idx >= 0) & (idx <= last) & ~on_hi
    if np.any(inside):
        np.add.at(counts, idx[inside], 1.0)
    if np.any(on_hi):
        counts[last] += float(np.count_nonzero(on_hi))
    return counts


def _split_histogram_samples(x):
    """Read ``Axes.hist``'s ``x`` the way matplotlib does.

    A 1d array is one sample set. A 2d array is one set per column. Any
    other sequence of sequences is one set per element, lengths free to
    differ; a sequence of numbers is one set.
    """
    if isinstance(x, np.ndarray):
        if x.ndim == 0:
            raise ValueError("hist() x must be one or more 1d sample arrays")
        if x.ndim == 1:
            return [np.asarray(x, dtype=float)]
        if x.ndim == 2:
            if x.shape[1] < 1:
                raise ValueError("hist() x has no columns")
            return [np.asarray(x[:, i], dtype=float) for i in range(x.shape[1])]
        raise ValueError(f"hist() x must be 1d or 2d, got {x.ndim} dimensions")
    if isinstance(x, (str, bytes)):
        raise ValueError("hist() x must be one or more 1d sample arrays")
    try:
        items = list(x)
    except TypeError:
        raise ValueError("hist() x must be one or more 1d sample arrays")
    if len(items) == 0:
        raise ValueError("hist() received no samples")
    first = items[0]
    if isinstance(first, (str, bytes)):
        raise ValueError("hist() x must be one or more 1d sample arrays")
    if np.isscalar(first):
        return [np.asarray(items, dtype=float)]
    sets = []
    for item in items:
        arr = np.asarray(item, dtype=float)
        if arr.ndim != 1:
            raise ValueError("each hist() dataset must be 1-dimensional")
        sets.append(arr)
    return sets


def _as_bin_count(bins):
    """An integer bin count, or ``None`` when ``bins`` is something else.

    ``True`` is an ``int`` subclass and is not a bin count.
    """
    if isinstance(bins, bool) or bins is None:
        return None
    if isinstance(bins, (int, np.integer)):
        return int(bins)
    if isinstance(bins, (float, np.floating)) and float(bins).is_integer():
        return int(bins)
    return None


def _as_curve(name: str, value, n: int) -> np.ndarray:
    """Broadcast ``value`` to a length-``n`` float array.

    A scalar (or a length-1 array) becomes a constant curve, which is how
    matplotlib treats ``fill_between``'s default ``y2=0``.
    """
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0 or arr.size == 1:
        return np.full(n, float(np.ravel(arr)[0]))
    flat = np.ravel(arr)
    if flat.size != n:
        raise ValueError(f"{name} has length {flat.size}, expected {n}")
    return flat


def _is_scalar_zero(value) -> bool:
    """True for the default ``y2=0``, not for an array of zeros."""
    arr = np.asarray(value)
    if arr.ndim != 0:
        return False
    number = float(arr)
    return number == 0.0 and np.isfinite(number)


def _curve_crossing(x0, diff0, x1, diff1):
    """x where ``y1 - y2`` crosses 0 between two samples, or None.

    This is the point matplotlib's ``interpolate=True`` adds: the root of
    the difference, not a midpoint of the boolean mask.
    """
    if not (
        np.isfinite(diff0)
        and np.isfinite(diff1)
        and np.isfinite(x0)
        and np.isfinite(x1)
    ):
        return None
    if diff0 == 0.0 and diff1 == 0.0:
        return None
    if diff0 == 0.0:
        return float(x0)
    if diff1 == 0.0:
        return float(x1)
    if diff0 * diff1 > 0.0:
        return None
    frac = diff0 / (diff0 - diff1)
    return float(x0 + frac * (x1 - x0))


#: The ``fill_between`` keywords ``stackplot`` passes on to every layer.
_STACKPLOT_BAND_KEYWORDS = frozenset(
    {"alpha", "where", "interpolate", "step", "offset", "data_name"}
    | {"xmin", "xmax", "ymin", "ymax"}
)


#: matplotlib's named line styles, as the symbols ``plot`` takes.
_NAMED_LINESTYLES = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}


def _segment_linestyle(name: str, style) -> str:
    """One ``hlines`` / ``vlines`` line style as a ``plot`` linestyle.

    ``'none'`` (matplotlib's no-line styles) means the segment is not drawn.
    """
    if isinstance(style, str):
        key = style.strip().lower()
        key = _NAMED_LINESTYLES.get(key, key)
        if key in ("-", "--", ":", "-."):
            return key
        if key in ("none", ""):
            return "none"
        raise ValueError(
            f"{name}() linestyles must be 'solid', 'dashed', 'dotted', "
            f"'dashdot', '-', '--', ':', '-.' or 'none', got {style!r}"
        )
    warn_external(
        f"{name}() linestyle {style!r} is a dash pattern GLE cannot draw; "
        "the segment is solid."
    )
    return "-"


def _is_dash_pattern(value) -> bool:
    """matplotlib's ``(offset, on_off_sequence)`` line style."""
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], Real)
        and (value[1] is None or isinstance(value[1], (tuple, list)))
    )


def _line_style(caller: str, linestyle):
    """A line's matplotlib ``linestyle`` as the symbol the writer draws.

    The symbols, ``None`` and the no-line values pass through; a named
    style becomes its symbol. A dash pattern or an unknown style warns and
    is drawn solid.
    """
    if linestyle is None:
        return None
    if isinstance(linestyle, str):
        if linestyle in ("-", "--", ":", "-.") or linestyle in _NO_LINE:
            return linestyle
        if linestyle in _NAMED_LINESTYLES:
            return _NAMED_LINESTYLES[linestyle]
    if _is_dash_pattern(linestyle):
        warn_external(
            f"{caller}() linestyle {linestyle!r} is a dash pattern GLE cannot "
            "draw; the line is drawn solid. Pass '--', ':' or '-.' instead."
        )
    else:
        warn_external(
            f"{caller}() linestyle {linestyle!r} is not a line style; the line "
            "is drawn solid. Pass '-', '--', ':', '-.', 'solid', 'dashed', "
            "'dotted', 'dashdot' or 'none'."
        )
    return "-"


def _color_list(name: str, colors, default: list) -> list:
    """A ``colors`` argument as a list to cycle over layers or segments.

    ``None`` is ``default``. A string or an RGB(A) tuple is one colour; the
    rows of a 2-D array are tuples, the form ``rgb_to_gle`` reads.
    """
    if colors is None:
        return list(default)
    if isinstance(colors, str):
        return [colors]
    if np.ndim(colors) == 1 and all(
        isinstance(v, (int, float, np.number)) for v in colors
    ):
        if len(colors) == 0:
            raise ValueError(f"{name}() colors must not be empty, got {colors!r}")
        return [tuple(colors)]
    found = [tuple(c) if np.ndim(c) == 1 else c for c in colors]
    if not found:
        raise ValueError(f"{name}() colors must not be empty, got {colors!r}")
    return found


def _where_windows(x, y1, y2, where, interpolate: bool):
    """GLE clip windows for a matplotlib ``where`` mask.

    One dict per contiguous run of True samples long enough to have area.
    ``xmin`` / ``xmax`` are omitted on a side the run already reaches.
    ``[]`` means the mask fills nothing. ``None`` means ``x`` is not a
    finite, strictly monotonic sequence, so a rectangle cannot express
    the mask.
    """
    n = int(len(x))
    mask = np.asarray(where, dtype=bool)
    if mask.size != n:
        raise ValueError(f"where has length {mask.size}, expected {n} to match x")
    mask = np.ravel(mask)
    if n == 0 or not np.any(mask):
        return []
    if np.all(mask):
        # No clip. Monotonicity does not matter when every sample is filled.
        return [{}]
    if not np.all(np.isfinite(x)):
        return None
    delta = np.diff(np.asarray(x, dtype=float))
    # A repeated x cannot be split by a rectangle: the True and False samples
    # that share it would both fall inside the clip. Require a strict order.
    if n >= 2 and not (np.all(delta > 0.0) or np.all(delta < 0.0)):
        return None
    if n == 1:
        return []

    changes = (np.flatnonzero(mask[:-1] != mask[1:]) + 1).tolist()
    if mask[0]:
        changes = [0] + changes
    if mask[-1]:
        changes.append(n)
    windows = []
    for idx0, idx1 in zip(changes[::2], changes[1::2]):
        left = float(x[idx0])
        right = float(x[idx1 - 1])
        crossed = False
        if interpolate and y2 is not None and idx0 > 0:
            hit = _curve_crossing(
                x[idx0 - 1],
                y1[idx0 - 1] - y2[idx0 - 1],
                x[idx0],
                y1[idx0] - y2[idx0],
            )
            if hit is not None:
                left = hit
                crossed = True
        if interpolate and y2 is not None and idx1 < n:
            hit = _curve_crossing(
                x[idx1 - 1],
                y1[idx1 - 1] - y2[idx1 - 1],
                x[idx1],
                y1[idx1] - y2[idx1],
            )
            if hit is not None:
                right = hit
                crossed = True
        if (idx1 - idx0) < 2 and not crossed:
            # An isolated True has no segment. matplotlib draws no area
            # unless interpolate extends it to a crossing.
            continue
        # The clip is the x-range of the run. Compare with the data extent
        # so a crossing that lands on the neighboring sample still cuts off
        # any points beyond it, and a decreasing x uses the same edges.
        lo = float(min(left, right))
        hi = float(max(left, right))
        data_lo = float(np.min(x))
        data_hi = float(np.max(x))
        clip = {}
        if lo > data_lo:
            clip["xmin"] = lo
        if hi < data_hi:
            clip["xmax"] = hi
        windows.append(clip)
    return windows


def _positional_fill_color(value):
    """A matplotlib color in ``fill(x, y, color)``, or None if it is data."""
    if isinstance(value, str):
        return value
    if (
        isinstance(value, (tuple, list))
        and len(value) in (3, 4)
        and all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in value
        )
    ):
        return value
    return None


def _apply_xaxis(fields: dict, xaxis: str) -> None:
    """Record a secondary-x binding, or reject a name GLE cannot draw.

    Absent means the primary x axis, which is what every series stored
    before ``xaxis`` existed, so the key is written only for ``'x2'``.
    """
    if xaxis == "x":
        return
    if xaxis != "x2":
        raise ValueError(f"xaxis must be 'x' or 'x2', got {xaxis!r}")
    fields["xaxis"] = "x2"


def _file_read_options(skiprows, comment, max_rows) -> Dict[str, Any]:
    """The ``*_from_file`` reading options that were given, validated.

    Only non-default ones are returned, so a call that passes none stores
    the historical shape.
    """
    for name, value in (("skiprows", skiprows), ("max_rows", max_rows)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, np.integer))
        ):
            raise TypeError(f"{name} must be an integer; got {value!r}")
    if comment is not None and not isinstance(comment, str):
        raise TypeError(f"comment must be a string such as '#'; got {comment!r}")
    fields: Dict[str, Any] = {}
    if skiprows < 0:
        raise ValueError(f"skiprows must be >= 0; got {skiprows!r}")
    if skiprows:
        fields["skiprows"] = int(skiprows)
    if comment is not None:
        if not comment or '"' in comment or any(ch.isspace() for ch in comment):
            raise ValueError(
                "comment must be a non-empty string with no whitespace or "
                f"double quote, such as '#'; got {comment!r}"
            )
        fields["comment"] = comment
    if max_rows is not None:
        if max_rows < 1:
            raise ValueError(
                f"max_rows must be >= 1, or None to read every row; got {max_rows!r}"
            )
        fields["max_rows"] = int(max_rows)
    return fields


def _check_file_columns(x_col, **y_cols) -> None:
    """Reject a column index GLE cannot read: ``x_col`` 0 is the row index."""
    if x_col < 0:
        raise ValueError(
            f"x_col must be >= 0 (0 uses the row number as x), got {x_col!r}"
        )
    for name, col in y_cols.items():
        if col is not None and col < 1:
            raise ValueError(f"{name} must be >= 1, got {col!r}")


def _dataset_qualifiers(
    mdist, deresolve, deresolve_average, xmin, xmax, ymin, ymax
) -> Dict[str, Any]:
    """The ``plot`` dataset-qualifier fields that were given, validated.

    Only the given ones are returned: an absent field is the historical
    behaviour (see :class:`~gleplot.series.LineSeries`).
    """
    for name, value in (
        ("mdist", mdist),
        ("xmin", xmin),
        ("xmax", xmax),
        ("ymin", ymin),
        ("ymax", ymax),
    ):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float, np.number))
        ):
            raise TypeError(f"{name} must be a number; got {value!r}")
    fields: Dict[str, Any] = {}
    if mdist is not None:
        if not np.isfinite(mdist) or mdist <= 0:
            raise ValueError(
                f"mdist must be a positive distance in cm; got {mdist!r}. "
                "Omit it to draw a marker on every point."
            )
        fields["mdist"] = float(mdist)
    if deresolve is not None:
        if (
            isinstance(deresolve, bool)
            or not isinstance(deresolve, (int, np.integer))
            or deresolve < 1
        ):
            raise ValueError(
                f"deresolve must be an integer >= 1; got {deresolve!r}. "
                "deresolve=N draws one point in every N."
            )
        fields["deresolve"] = int(deresolve)
    if deresolve_average:
        if deresolve is None:
            raise ValueError(
                "deresolve_average=True needs deresolve=N: it averages each "
                "window of N points."
            )
        fields["deresolve_average"] = True
    for name, value in (("xmin", xmin), ("xmax", xmax), ("ymin", ymin), ("ymax", ymax)):
        if value is None:
            continue
        if not np.isfinite(value):
            raise ValueError(f"{name} must be a finite number; got {value!r}")
        fields[name] = float(value)
    for lo, hi in (("xmin", "xmax"), ("ymin", "ymax")):
        if lo in fields and hi in fields and fields[lo] >= fields[hi]:
            raise ValueError(
                f"{lo} must be less than {hi}; got {lo}={fields[lo]!r}, "
                f"{hi}={fields[hi]!r}"
            )
    return fields


class SecondaryXAxis:
    """The top scale of an axes, as matplotlib's ``Axes.twiny`` returns.

    Not a second subplot. GLE draws the top scale on the same graph, so
    this view writes that scale: plotting methods bind the series with
    ``xaxis='x2'``, and the limit, label, and scale setters address it.
    The y axis stays the one this view was opened on.
    """

    def __init__(self, axes: "Axes"):
        self._axes = axes

    def plot(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.plot(*args, **kwargs)

    def scatter(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.scatter(*args, **kwargs)

    def errorbar(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.errorbar(*args, **kwargs)

    def step(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.step(*args, **kwargs)

    def stem(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.stem(*args, **kwargs)

    def hist(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.hist(*args, **kwargs)

    def line_from_file(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.line_from_file(*args, **kwargs)

    def errorbar_from_file(self, *args, **kwargs):
        kwargs["xaxis"] = "x2"
        return self._axes.errorbar_from_file(*args, **kwargs)

    def set_xlim(self, xmin: Optional[float], xmax: Optional[float]):
        return self._axes.set_xlim(xmin, xmax, axis="x2")

    def get_xlim(self) -> Tuple[Optional[float], Optional[float]]:
        return self._axes.get_xlim(axis="x2")

    def set_xlabel(self, label: str, **kwargs):
        return self._axes.set_xlabel(label, axis="x2", **kwargs)

    def set_xscale(self, scale: str):
        return self._axes.set_xscale(scale, axis="x2")

    def set_tick_format(self, fmt: Optional[str]):
        return self._axes.set_tick_format(fmt, axis="x2")

    def set_ylim(self, ymin: Optional[float], ymax: Optional[float], axis: str = "y"):
        return self._axes.set_ylim(ymin, ymax, axis=axis)

    def set_ylabel(self, label: str, axis: str = "y", **kwargs):
        return self._axes.set_ylabel(label, axis=axis, **kwargs)

    def set_yscale(self, scale: str, axis: str = "y"):
        return self._axes.set_yscale(scale, axis=axis)

    def invert_xaxis(self):
        return self._axes._invert_axis("x2", "invert_xaxis")

    def invert_yaxis(self):
        return self._axes.invert_yaxis()


class SecondaryYAxis:
    """The right-hand scale of an axes, as matplotlib's ``Axes.twinx`` returns.

    Not a second subplot. GLE draws the right scale on the same graph, so
    this view writes that scale: plotting methods bind the series with
    ``yaxis='y2'``, and the limit, label, and scale setters address it.
    The x axis stays the one this view was opened on.
    """

    def __init__(self, axes: "Axes"):
        self._axes = axes

    def plot(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.plot(*args, **kwargs)

    def scatter(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.scatter(*args, **kwargs)

    def errorbar(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.errorbar(*args, **kwargs)

    def step(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.step(*args, **kwargs)

    def stem(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.stem(*args, **kwargs)

    def hist(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.hist(*args, **kwargs)

    def line_from_file(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.line_from_file(*args, **kwargs)

    def errorbar_from_file(self, *args, **kwargs):
        kwargs["yaxis"] = "y2"
        return self._axes.errorbar_from_file(*args, **kwargs)

    def set_ylim(self, ymin: Optional[float], ymax: Optional[float]):
        return self._axes.set_ylim(ymin, ymax, axis="y2")

    def get_ylim(self) -> Tuple[Optional[float], Optional[float]]:
        return self._axes.get_ylim(axis="y2")

    def set_ylabel(self, label: str, **kwargs):
        return self._axes.set_ylabel(label, axis="y2", **kwargs)

    def set_yscale(self, scale: str):
        return self._axes.set_yscale(scale, axis="y2")

    def set_tick_format(self, fmt: Optional[str]):
        return self._axes.set_tick_format(fmt, axis="y2")

    def invert_yaxis(self):
        return self._axes._invert_axis("y2", "invert_yaxis")

    def set_xlim(self, xmin: Optional[float], xmax: Optional[float], axis: str = "x"):
        return self._axes.set_xlim(xmin, xmax, axis=axis)

    def set_xlabel(self, label: str, axis: str = "x", **kwargs):
        return self._axes.set_xlabel(label, axis=axis, **kwargs)

    def set_xscale(self, scale: str, axis: str = "x"):
        return self._axes.set_xscale(scale, axis=axis)

    def invert_xaxis(self):
        return self._axes.invert_xaxis()


def _point_sizes(name: str, values: Any, n_points: int) -> np.ndarray:
    """``scatter``'s per-point ``s`` or ``markersize`` as a float array.

    Raises ``ValueError`` unless the sizes are finite and not negative, and
    there is one, or one per point (matplotlib's rule).
    """
    try:
        sizes = np.asarray(values, dtype=float).ravel()
    except (TypeError, ValueError):
        raise ValueError(
            f"scatter({name}=...) must be a number or a sequence of numbers, "
            f"got {values!r}."
        ) from None
    if sizes.size not in (1, n_points):
        raise ValueError(
            f"scatter({name}=...) has {sizes.size} sizes for {n_points} points; "
            "pass one size, or one per point."
        )
    if not np.all(np.isfinite(sizes)) or np.any(sizes < 0):
        raise ValueError(
            f"scatter({name}=...) sizes must be finite and not negative, got "
            f"{values!r}."
        )
    return sizes


def _scatter_c(c: Any, n_points: int) -> Tuple[str, Any]:
    """Classify ``scatter``'s ``c`` the way matplotlib does.

    Returns ``('color', one colour)``, ``('colors', one colour per point)``
    or ``('values', float array)``. Numbers, one per point, are values to
    colour-map, even when there are three or four of them. Raises
    ``ValueError`` for any other count.
    """
    if isinstance(c, str):
        return "color", c
    items: Optional[List[Any]] = None
    if isinstance(c, np.ndarray):
        if c.dtype.kind in "OSU":
            items = c.ravel().tolist()
    else:
        try:
            items = list(c)
        except TypeError:
            pass
    # A string is a colour even when it reads as a number ('0.5' is a grey).
    if items is None or not any(isinstance(item, str) for item in items):
        try:
            numbers = np.asarray(c, dtype=float)
        except (TypeError, ValueError):
            numbers = None
        if numbers is not None:
            one_row = numbers.shape in ((1, 3), (1, 4))
            if numbers.size == n_points and not one_row:
                return "values", numbers.ravel()
            if one_row or (numbers.ndim == 1 and numbers.size in (3, 4)):
                return "color", tuple(numbers.ravel().tolist())
            if numbers.shape in ((n_points, 3), (n_points, 4)):
                return "colors", [tuple(row) for row in numbers.tolist()]
            items = None
    if items is not None and len(items) == 1:
        return "color", items[0]
    if items and len(items) == n_points:
        return "colors", items
    raise ValueError(
        f"scatter(c=...) does not match the {n_points} points: got {c!r}. "
        "Pass one number per point to colour-map, one colour, or one colour "
        "per point."
    )


def _is_straight_connection(connection: Any) -> bool:
    """Whether a matplotlib ``connectionstyle`` is a straight ``arc3``."""
    kind, _, params = str(connection).partition(",")
    if kind.strip() != "arc3":
        return False
    for param in params.split(","):
        key, _, value = param.partition("=")
        if key.strip() == "rad":
            try:
                return float(value) == 0.0
            except ValueError:
                return False
    return True


class Axes:
    """Matplotlib-like axes for plotting."""

    def __init__(self, figure, position: Optional[tuple] = None):
        """
        Initialize axes.

        Parameters
        ----------
        figure : Figure
            Parent figure
        position : tuple
            Subplot position ``(rows, cols, index)``; ``index`` is an int, or
            a ``(first, last)`` tuple for an axes spanning several cells.
            ``None`` for an axes outside the grid, placed by its
            :attr:`placement` (:meth:`gleplot.Figure.add_axes`).
        """
        self.figure = figure
        self.position = position

        #: Stable opaque identity for this axes: a uuid4 hex string assigned
        #: once at construction and never recomputed from position/content, so
        #: it survives ``to_dict``/``from_dict`` round-trips and axes
        #: reordering. Deliberately NOT emitted into GLE output (writer.py
        #: never reads this attribute) -- it lives only in the dict/project
        #: layer. A parsed ``.gle`` file has no
        #: id to recover, so the recognizer's freshly constructed ``Axes``
        #: objects get a new one here.
        self.axes_id: str = uuid.uuid4().hex

        # Axis properties
        self.xlabel_text = ""
        self.ylabel_text = ""
        self.y2label_text = ""  # Secondary y-axis label
        self.x2label_text = ""  # Secondary x-axis (top) label
        self.title_text = ""
        self.xscale = "linear"
        self.yscale = "linear"
        self.y2scale = "linear"  # Secondary y-axis scale
        self.x2scale = "linear"  # Secondary x-axis scale
        # Axis limits. ``None`` = auto (derived from the data at GLE-generation
        # time); a DESCENDING pair inverts the axis (GLE ``negate``). Annotated
        # explicitly: the ``= None`` initializers alone would have a type
        # checker infer the declared type as bare ``None`` and reject the
        # "None = auto" assignments every downstream editor makes.
        self.xmin: Optional[float] = None
        self.xmax: Optional[float] = None
        self.ymin: Optional[float] = None
        self.ymax: Optional[float] = None
        self.y2min: Optional[float] = None  # Secondary y-axis limits
        self.y2max: Optional[float] = None
        self.x2min: Optional[float] = None  # Secondary x-axis limits
        self.x2max: Optional[float] = None
        # Tri-state: None = auto (show a legend iff any series has a label),
        # True/False = explicit choice (what an editor's legend toggle writes).
        self.legend_on: Optional[bool] = None
        self.legend_pos = "top right"
        # Legend text height in matplotlib points (None = inherit the figure
        # style's fontsize, i.e. whatever GLE's current ``set hei`` is) and
        # the legend box (matplotlib ``frameon``; False emits ``key nobox``).
        self.legend_fontsize: Optional[float] = None
        self.legend_frameon = True
        #: ``(dx_cm, dy_cm)`` or None (= the figure graph config's
        #: ``legend_offset_x``/``legend_offset_y``, themselves ``0, 0`` by
        #: default, i.e. no ``offset`` clause at all).
        self.legend_offset: Optional[Tuple[float, float]] = None
        # Column count for the graph key. 1 omits ``key separator``. GLE
        # packs columns the way matplotlib's ``np.array_split`` does, so
        # the extra entries go in the first columns.
        self.legend_ncol: int = 1
        # GLE ``compact``: line and marker share one swatch field.
        self.legend_compact: bool = False
        # Legend-box fill, emitted as GLE ``background``. None omits it.
        # matplotlib's name is ``facecolor``; GLE's ``boxcolor`` is the
        # fill-swatch stroke, not this.
        self.legend_facecolor: Optional[str] = None
        # matplotlib ``borderpad``/``handlelength``/``handletextpad``/
        # ``columnspacing`` in legend font-size units, keyed by that name
        # (``LEGEND_SPACING_TO_KEY``). An absent name emits nothing.
        self.legend_spacing: Dict[str, float] = {}
        # The point, in axes fractions, that the ``legend_pos`` corner of the
        # key sits on (matplotlib ``bbox_to_anchor``). None keeps the key
        # inside the graph at ``legend_pos``.
        self.legend_bbox_to_anchor: Optional[Tuple[float, float]] = None
        # One colour for every entry's text (GLE ``textcolor``). None leaves
        # the text in the current colour.
        self.legend_labelcolor: Optional[str] = None

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
        self.xdticks: Optional[float] = None
        self.ydticks: Optional[float] = None
        self.xdsubticks: Optional[float] = None
        self.ydsubticks: Optional[float] = None
        self.xplaces: Optional[List[float]] = None
        self.xnames: Optional[List[str]] = None
        self.yplaces: Optional[List[float]] = None
        self.ynames: Optional[List[str]] = None

        # -- Axes styling (all None = "absent", emit nothing) ---------------
        #
        # Every field below defaults to None and is emitted only when set, so
        # a figure that never touches them produces exactly the GLE it always
        # did. Sizes are matplotlib POINTS (converted to GLE ``hei`` cm at
        # write time), distances are page CENTIMETRES (GLE's own unit for
        # ``dist``), angles are DEGREES, and colours are anything
        # :func:`gleplot.colors.rgb_to_gle` accepts.

        #: Tick-label number format per axis -- GLE ``xaxis format "<fmt>"``
        #: (see :meth:`set_tick_format` for the syntax and validation).
        self.xformat: Optional[str] = None
        self.yformat: Optional[str] = None
        self.y2format: Optional[str] = None
        self.x2format: Optional[str] = None

        #: Functional grid per axis: None (no grid), ``'major'`` (grid lines
        #: at the main ticks) or ``'both'`` (grid lines at main ticks AND
        #: subticks). Set through :meth:`grid`. GLE draws the grid by making
        #: that axis' ticks span the graph, so ``'both'`` is ``xaxis grid``
        #: plus ``xsubticks on``. x2/y2 have no grid of their own: they are
        #: the far ends of the x/y ticks.
        #
        # ``GLEGraphConfig.show_grid`` is the figure-wide default and is read
        # HERE, once, at construction: a later ``grid(False)`` then simply
        # switches it off, and the answer always lives in the model (so it
        # serializes and round-trips) rather than being re-derived at write
        # time from a config the axes may since have disagreed with.
        # ``from_dict``/the recognizer overwrite these straight after, so a
        # loaded figure keeps what it was saved with.
        _grid_default = "major" if self._figure_shows_grid(figure) else None
        self.xgrid: Optional[str] = _grid_default
        self.ygrid: Optional[str] = _grid_default
        #: Grid line style, width (points) and colour. Emitted as ``xticks
        #: lstyle/lwidth/color`` and, when the grid covers subticks, the
        #: matching ``xsubticks`` clause -- in GLE the grid lines ARE the
        #: ticks, so these style the ticks too. Only written when the
        #: corresponding grid is on; a style with no grid would be a silent
        #: no-op.
        self.xgrid_lstyle: Optional[int] = None
        self.xgrid_lwidth: Optional[float] = None
        self.xgrid_color: Optional[str] = None
        self.ygrid_lstyle: Optional[int] = None
        self.ygrid_lwidth: Optional[float] = None
        self.ygrid_color: Optional[str] = None

        #: Axis-title styling -- the ``xtitle``/``ytitle``/``y2title`` text is
        #: ``xlabel_text``/... above; these are its ``hei``/``color``/``dist``
        #: options. ``*_dist`` is the gap between the title and the tick
        #: labels (None = the figure graph config's ``xlabel_distance`` /
        #: ``ylabel_distance``, themselves None = GLE's ``atitledist``).
        self.xlabel_size: Optional[float] = None
        self.xlabel_color: Optional[str] = None
        self.xlabel_dist: Optional[float] = None
        self.ylabel_size: Optional[float] = None
        self.ylabel_color: Optional[str] = None
        self.ylabel_dist: Optional[float] = None
        self.y2label_size: Optional[float] = None
        self.y2label_color: Optional[str] = None
        self.y2label_dist: Optional[float] = None
        self.x2label_size: Optional[float] = None
        self.x2label_color: Optional[str] = None
        self.x2label_dist: Optional[float] = None

        #: Tick-label styling: ``xlabels hei/color`` plus ``xaxis angle``
        #: (which rotates the tick labels, not the axis).
        self.xticklabel_size: Optional[float] = None
        self.xticklabel_color: Optional[str] = None
        self.xticklabel_angle: Optional[float] = None
        self.yticklabel_size: Optional[float] = None
        self.yticklabel_color: Optional[str] = None
        self.yticklabel_angle: Optional[float] = None
        #: y2 tick labels are OFF in GLE unless ``y2labels on`` is given, so
        #: setting any y2 tick-label property (including ``y2format``) also
        #: turns them on -- otherwise the property would be inert. See
        #: :meth:`GLEWriter.add_axes`.
        self.y2ticklabel_size: Optional[float] = None
        self.y2ticklabel_color: Optional[str] = None
        self.y2ticklabel_angle: Optional[float] = None
        #: x2 tick labels are off unless ``x2labels on`` is given, the same
        #: rule as y2. See :meth:`GLEWriter.add_axes`.
        self.x2ticklabel_size: Optional[float] = None
        self.x2ticklabel_color: Optional[str] = None
        self.x2ticklabel_angle: Optional[float] = None

        #: Graph-title styling (GLE ``title "..." hei/color/dist``). GLE's
        #: title belongs to the graph block, so it lives here, per axes,
        #: rather than on the figure. ``title_dist`` None = the figure graph
        #: config's ``title_distance`` (itself None = GLE's default).
        self.title_size: Optional[float] = None
        self.title_color: Optional[str] = None
        self.title_dist: Optional[float] = None

        #: GLE font of the graph title and of each axis title (``title ...
        #: font F``, ``xtitle ... font F``). Set through ``fontname=`` on
        #: :meth:`set_title`, :meth:`set_xlabel` and :meth:`set_ylabel`.
        self.title_font: Optional[str] = None
        self.xlabel_font: Optional[str] = None
        self.ylabel_font: Optional[str] = None
        self.y2label_font: Optional[str] = None
        self.x2label_font: Optional[str] = None

        #: Axis-line colour and width (points), GLE ``xside color C lwidth
        #: W``. GLE copies an x or y setting onto x2 or y2, so these also
        #: style the opposite edge unless that edge has its own. Set through
        #: :meth:`set_axis_line`.
        self.xside_color: Optional[str] = None
        self.xside_lwidth: Optional[float] = None
        self.yside_color: Optional[str] = None
        self.yside_lwidth: Optional[float] = None
        self.y2side_color: Optional[str] = None
        self.y2side_lwidth: Optional[float] = None
        self.x2side_color: Optional[str] = None
        self.x2side_lwidth: Optional[float] = None
        #: The bottom or left axis line hidden (True, GLE ``xside off``),
        #: its ticks and tick labels kept. None draws it. Set through
        #: ``set_axis_line(visible=False)``, which hides the top and right
        #: sides through ``_x2axis_off`` / ``_y2axis_off``.
        self.xside_off: Optional[bool] = None
        self.yside_off: Optional[bool] = None

        #: Tick placement beyond ``dticks``: GLE ``xaxis nticks N ftick F
        #: shift S symticks`` and ``xnoticks p1 p2 ...``. ``shift`` is in
        #: cm; ``symticks`` is True or None. Set through :meth:`set_xticks`
        #: and :meth:`set_yticks`.
        self.xnticks: Optional[int] = None
        self.xftick: Optional[float] = None
        self.xshift: Optional[float] = None
        self.xsymticks: Optional[bool] = None
        self.xnoticks: Optional[List[float]] = None
        self.ynticks: Optional[int] = None
        self.yftick: Optional[float] = None
        self.yshift: Optional[float] = None
        self.ysymticks: Optional[bool] = None
        self.ynoticks: Optional[List[float]] = None

        #: Tick marks, set through :meth:`tick_params`: GLE ``xticks length
        #: L lwidth W color C`` for the major ticks and the same on
        #: ``xsubticks`` for the minor ones. Lengths and widths are points,
        #: the length being matplotlib's whole tick (GLE draws half of it on
        #: each side under ``xsymticks``). Direction is ``'in'``, ``'out'``
        #: or None; GLE writes ``'out'`` as a negative length.
        self.xtick_length: Optional[float] = None
        self.xtick_width: Optional[float] = None
        self.xtick_color: Optional[str] = None
        self.xtick_direction: Optional[str] = None
        self.xsubtick_length: Optional[float] = None
        self.xsubtick_width: Optional[float] = None
        self.xsubtick_color: Optional[str] = None
        self.xsubtick_direction: Optional[str] = None
        self.ytick_length: Optional[float] = None
        self.ytick_width: Optional[float] = None
        self.ytick_color: Optional[str] = None
        self.ytick_direction: Optional[str] = None
        self.ysubtick_length: Optional[float] = None
        self.ysubtick_width: Optional[float] = None
        self.ysubtick_color: Optional[str] = None
        self.ysubtick_direction: Optional[str] = None
        #: Minor ticks switched on (True, ``xsubticks on``) or off (False,
        #: ``xsubticks off``); None leaves GLE's default. Set through
        #: :meth:`minorticks_on` / :meth:`minorticks_off`.
        self.xminorticks: Optional[bool] = None
        self.yminorticks: Optional[bool] = None
        #: Minor ticks between two major ones (GLE ``xaxis nsubticks N``) and
        #: which sub-decades of a log axis are labelled (GLE ``xlabels log
        #: MODE``). Set through :meth:`set_xticks` / :meth:`set_yticks`.
        self.xnsubticks: Optional[int] = None
        self.ynsubticks: Optional[int] = None
        self.xloglabels: Optional[str] = None
        self.yloglabels: Optional[str] = None

        #: GLE math mode (``math`` in the graph block): the x and y axes
        #: cross at (0, 0) and the top and right axes are hidden. True or
        #: None. Set through :meth:`set_math_mode`.
        self.math_mode: Optional[bool] = None

        # Frame sides switched off entirely -- axis line, ticks and labels.
        # Used for the inner edges of a broken-axis assembly, where several
        # graph blocks butt together and must read as one panel.
        self._xaxis_off = False
        self._yaxis_off = False
        self._x2axis_off = False
        self._y2axis_off = False
        # Every axis line and tick mark hidden, the axes kept (Axes.pie).
        self._frame_off = False
        # A polar axes (Figure.add_subplot(projection='polar')): x is theta
        # in radians, y is r, and ylim is (0, rmax).
        self._polar = False

        # Broken-axis membership (see :mod:`gleplot.brokenaxes`). Both stay
        # None on an ordinary axes; on a segment, ``_break_owner`` is the
        # BrokenAxes back-reference and ``_break_index`` its 0-based position
        # left-to-right.
        self._break_owner: Any = None
        self._break_index: Optional[int] = None

        # Plot data storage. One list per series kind, each holding the
        # matching :mod:`gleplot.series` class (which owns that kind's field
        # schema, array fields and sidecar header defaults).
        self.lines: List[LineSeries] = []
        self.scatters: List[ScatterSeries] = []
        self.bars: List[BarSeries] = []
        self.hists: List[HistSeries] = []
        self.functions: List[FunctionSeries] = []
        self.fits: List[FitSeries] = []
        self.derived_series: List[DerivedSeries] = []
        self.fills: List[FillSeries] = []
        self.errorbars: List[ErrorbarSeries] = []
        # External-file series definitions (column references).
        self.file_series: List[FileSeries] = []
        self.texts: List[TextAnnotation] = []  # In-plot text annotations
        self.heatmaps: List[HeatmapSeries] = []  # imshow/pcolormesh/tripcolor
        self.contours: List[ContourSeries] = []  # contour/tricontour lines
        # Reference lines (axvline/axhline) and shaded bands (axvspan/
        # axhspan). Stored as *declarations* -- a value plus a fractional
        # extent along the other axis -- and turned into concrete two-point
        # line / band datasets only at write time, once the axis limits are
        # known. See :meth:`materialize_reflines` for why.
        self.reflines: List[RefLine] = []
        self.spans: List[Span] = []
        self.wedges: List[Wedge] = []  # pie slices
        self.boxes: List[Box] = []  # box plot boxes
        self.images: List[PlacedImage] = []  # placed image files
        self.rugs: List[Rug] = []  # rugs

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
        # A y unit's length over an x unit's (set_aspect); None is 'auto'.
        # Resolved into the frame rect when the figure is written, so it is
        # not recovered from a .gle file: the rect it produced is.
        self._aspect: Optional[float] = None

        # Monotonic tie-breaker for equal ``zorder`` (call / insertion order).
        self._draw_seq_counter = 0

    @staticmethod
    def _figure_shows_grid(figure) -> bool:
        """Whether ``figure``'s graph config asks for a grid by default."""
        graph = getattr(figure, "graph", None)
        if graph is None:
            graph = GlobalConfig.get_graph()
        return bool(getattr(graph, "show_grid", False))

    def _style(self):
        """This figure's :class:`~gleplot.config.GLEStyleConfig`.

        Falls back to the process-global style for an axes constructed
        without a figure (only the test helpers do that).
        """
        return getattr(self.figure, "style", None) or GlobalConfig.get_style()

    def _text(self, s):
        """Display text ``s`` as stored: GLE markup, or as given for LaTeX.

        Under ``GLEStyleConfig.usetex`` GLE hands every label to LaTeX, which
        must receive the string the user wrote.
        """
        return s if self._style().usetex else mathtext_to_gle(s)

    def _resolve_color(self, color, marker_only: bool = False) -> str:
        """Resolve a series colour argument to a GLE colour.

        ``None`` means "use the figure style's default"
        (``default_marker_color`` for a marker-only series,
        ``default_color`` otherwise -- both ``'BLUE'`` out of the box, the
        colour these call sites used to hard-code). Anything else goes
        through :func:`gleplot.colors.rgb_to_gle` as usual; so does the
        configured default, so it may be spelled the matplotlib way.
        """
        style = self._style()
        if color is None:
            color = style.default_marker_color if marker_only else style.default_color
        return rgb_to_gle(color)

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
        linewidth: Optional[float] = 1,
        label: Optional[str] = None,
        yaxis: str = "y",
        xaxis: str = "x",
        offset: float = 0.0,
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        zorder: Optional[float] = None,
        drawstyle: Optional[str] = None,
        line_mode: Optional[str] = None,
        mdist: Optional[float] = None,
        deresolve: Optional[int] = None,
        deresolve_average: bool = False,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
        **kwargs,
    ):
        """
        Plot line or scatter plot (if marker without line).

        Parameters
        ----------
        x, y : array-like
            Data coordinates
        linestyle : str
            Line style: ``'-'``, ``'--'``, ``':'``, ``'-.'``, matplotlib's
            names ``'solid'``, ``'dashed'``, ``'dotted'``, ``'dashdot'``,
            or ``'none'`` for no line. A dash tuple or any other value
            warns and is drawn solid.
        color : str, optional
            Color name or code ('b', 'red', etc.)
        marker : str, optional
            Marker symbol ('o', 's', '^', etc.) - omit for line only
        markersize : float
            Marker size (matplotlib convention, 1-100)
        linewidth : float or None
            Line width in points; ``None`` means the default width.
        label : str, optional
            Legend label
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        xaxis : str, optional
            Which x-axis to use: 'x' (bottom, default) or 'x2' (top)
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
        drawstyle : str, optional
            ``'default'``, ``'steps'``, ``'steps-pre'``, ``'steps-mid'`` or
            ``'steps-post'``. ``'default'`` (and omitting it) is a straight
            polyline. The step styles are GLE line modes: ``'steps'`` and
            ``'steps-pre'`` emit ``line fsteps`` (matplotlib ``where='pre'``),
            ``'steps-post'`` emits ``line steps``, and ``'steps-mid'`` emits
            ``line hist``. ``ds`` is accepted as an alias. An unknown value
            raises ``ValueError``.
        line_mode : {'steps', 'fsteps', 'hist', 'bar', 'impulses'}, optional
            The GLE line mode itself, for a caller that already speaks GLE.
            ``'impulses'`` is what :meth:`stem` uses; ``'bar'`` is GLE's
            per-dataset bar outline, not :meth:`bar`. Must agree with
            ``drawstyle`` when both are passed. Omitted, the series stays a
            plain ``line`` and the script is unchanged.
        mdist : float, optional
            Draw the markers every ``mdist`` cm along the curve instead of
            one per data point (GLE ``mdist``). Needs a ``marker``; without
            one it warns and is dropped. Omitted, a marked line takes
            ``GLEMarkerConfig.mdist`` from the figure, and when that is
            ``None`` too every point gets a marker. matplotlib's
            ``markevery`` has no GLE equivalent: it warns and is ignored.
        deresolve : int, optional
            Draw one point in every ``deresolve`` (GLE ``deresolve``). GLE
            keeps the first and last point of a line.
        deresolve_average : bool, optional
            Draw each window of ``deresolve`` points as its mean, at the
            middle x of the window (GLE ``deresolve N average``). Needs
            ``deresolve``.
        xmin, xmax, ymin, ymax : float, optional
            Clip window for this series in data coordinates (GLE's ``dN
            xmin ... ymax``): nothing is drawn outside it. An omitted edge
            is open. ``xmin`` must be below ``xmax``, ``ymin`` below
            ``ymax``.
        **kwargs
            Additional matplotlib-compatible arguments. ``lw``, ``ls``,
            ``c`` and ``ms`` are matplotlib's short names for
            ``linewidth``, ``linestyle``, ``color`` and ``markersize``.
            matplotlib raises for a name passed with its short name; here
            the full name wins, with a warning, unless it is left at its
            default. ``solid_capstyle``,
            ``dash_capstyle``, ``solid_joinstyle`` and ``dash_joinstyle``
            take matplotlib's values; GLE caps and joins every line in the
            figure alike, so one that differs from the figure's
            :class:`~gleplot.GLEStyleConfig` ``line_cap``/``line_join``
            warns and is not applied. Any other keyword (``alpha``,
            ``markeredgecolor``, ...) warns and is ignored.

        Returns
        -------
        Line2D
            Line object (for compatibility)
        """
        data_name = kwargs.pop("data_name", None)
        if zorder is None and "zorder" in kwargs:
            zorder = kwargs.pop("zorder")
        # Private: the public method this call came through, for its warnings.
        caller = kwargs.pop("_caller", "plot")
        # matplotlib's scatter and stem take no Line2D keywords, so these
        # short names are no aliases there.
        if caller not in ("scatter", "stem"):
            linestyle = _pop_line_alias(
                kwargs, caller, "ls", "linestyle", linestyle, "-"
            )
            linewidth = _pop_line_alias(kwargs, caller, "lw", "linewidth", linewidth, 1)
            color = _pop_line_alias(kwargs, caller, "c", "color", color, None)
            markersize = _pop_line_alias(
                kwargs, caller, "ms", "markersize", markersize, 6
            )
        linestyle = _line_style(caller, linestyle)
        marker_fill = _pop_marker_fill(kwargs, fillstyle, markerfacecolor)
        _pop_line_ends(kwargs, linestyle, self._style())
        label = self._text(label)
        ds = kwargs.pop("ds", None)
        if self._polar:
            for name, value, default in (
                ("yaxis", yaxis, "y"),
                ("xaxis", xaxis, "x"),
                ("offset", offset, 0),
                ("drawstyle", drawstyle, None),
                ("ds", ds, None),
                ("line_mode", line_mode, None),
                ("xmin", xmin, None),
                ("xmax", xmax, None),
                ("ymin", ymin, None),
                ("ymax", ymax, None),
            ):
                if value != default and not (
                    name == "drawstyle" and value == "default"
                ):
                    raise ValueError(
                        f"{name}={value!r} is not supported on a polar axes, "
                        "where plot() and scatter() take only theta and r; "
                        "leave it out."
                    )
        mode = resolve_line_mode(drawstyle, line_mode, ds)
        qualifiers = _dataset_qualifiers(
            mdist, deresolve, deresolve_average, xmin, xmax, ymin, ymax
        )
        if kwargs.pop("markevery", None) is not None:
            warn_external(
                "plot(markevery=...) is ignored: GLE cannot mark every Nth "
                "point. Pass mdist= (cm along the curve) to space the markers "
                "out instead.",
            )
        warn_unsupported_keywords(caller, kwargs)
        if "mdist" in qualifiers and marker is None:
            warn_external(
                "plot(mdist=...) spaces markers, and this series has no "
                "marker; mdist is ignored. Pass marker= to draw markers.",
            )
            del qualifiers["mdist"]

        x = np.asarray(x)
        y = np.asarray(y)

        # Handle marker. GLE supports markers on line datasets natively, so a
        # marker requested alongside a solid/dashed line must be preserved
        # (not silently dropped). Only when there is *no* line is the series a
        # true scatter.
        is_scatter = marker is not None and linestyle in _NO_LINE
        # A GLE line mode is a qualifier of ``line``. With the line switched
        # off there is nothing for it to qualify, and storing it would not
        # survive a round trip (the writer emits no ``line`` token).
        if mode and linestyle in _NO_LINE:
            warn_external(
                f"line mode {mode!r} needs a drawn line; linestyle={linestyle!r} "
                "omits it, so the series is drawn without that mode.",
            )
            mode = None

        # Handle color. Which style default applies depends on what this
        # series turns out to be, which is why it is resolved after
        # ``is_scatter``: a marker-only series is what ``scatter()`` produces
        # and takes ``default_marker_color``.
        color = self._resolve_color(color, marker_only=is_scatter)

        gle_marker = (
            get_gle_marker(marker, fill=marker_fill) if marker is not None else None
        )
        plot_type = "scatter" if is_scatter else "line"

        # Scale markersize from matplotlib (typical 1-20, default 6) to GLE msize (0.05-0.5)
        # Examples: markersize 6 → 0.15, markersize 10 → 0.25, markersize 20 → 0.5
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )

        # matplotlib reads None as the default width; 1 is the writer's
        # "style default" (see GLEWriter.add_line).
        if linewidth is None:
            linewidth = 1

        plot_fields = dict(
            type=plot_type,
            x=x,
            y=y,
            color=color,
            marker=gle_marker,
            markersize=gle_markersize,
            linestyle=linestyle,
            linewidth=linewidth,
            nomiss=False,
            label=label,
            yaxis=yaxis,  # 'y' or 'y2'
            offset=float(offset),
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_build_column_names("x", ["y"], label),
        )
        _apply_xaxis(plot_fields, xaxis)
        plot_fields.update(qualifiers)
        if mode:
            plot_fields["line_mode"] = mode
            # graph2.cpp transform_data() runs fitbez before drawLine()
            # switches on the mode, so a figure-wide smooth_curves would
            # draw the steps through the spline. Pin this series off.
            # A script that writes both keywords keeps the smooth it asked
            # for; this only stops the default from applying.
            plot_fields["smooth_mode"] = "none"

        if is_scatter:
            scatter_data = ScatterSeries(**plot_fields)
            self._register_series_draw_meta(scatter_data, "scatter", zorder)
            self.scatters.append(scatter_data)
        else:
            line_data = LineSeries(**plot_fields)
            self._register_series_draw_meta(line_data, "line", zorder)
            self.lines.append(line_data)

        return self  # Return self for method chaining

    @_cartesian_only
    def step(self, x, y, *args, where: str = "pre", **kwargs):
        """Draw a step plot.

        A thin wrapper around :meth:`plot` that selects a GLE line mode.
        ``where`` follows matplotlib:

        - ``'pre'`` (default): the interval ``(x[i-1], x[i]]`` has value
          ``y[i]``. GLE ``line fsteps`` (vertical, then horizontal).
        - ``'post'``: the interval ``[x[i], x[i+1])`` has value ``y[i]``.
          GLE ``line steps`` (horizontal, then vertical).
        - ``'mid'``: the step is halfway between the x positions, and each
          point is a bin center. GLE ``line hist``.

        A positional format string is accepted and ignored, with a warning:
        pass ``color``, ``linestyle`` and ``marker`` as keywords. ``where``
        wins over an explicit ``drawstyle``.

        Returns
        -------
        self
        """
        where_key = str(where).strip().lower()
        if where_key not in ("pre", "post", "mid"):
            raise ValueError(f"where must be 'pre', 'post', or 'mid', got {where!r}")
        if args:
            warn_external(
                "step() format strings are not applied; pass color, "
                "linestyle and marker as keywords.",
            )
        if "drawstyle" in kwargs or "ds" in kwargs:
            warn_external(
                "step() sets the drawstyle from where=; the drawstyle "
                "argument was ignored.",
            )
            kwargs.pop("drawstyle", None)
            kwargs.pop("ds", None)
        kwargs["drawstyle"] = "steps-" + where_key
        return self.plot(x, y, _caller="step", **kwargs)

    @_cartesian_only
    def stem(
        self,
        *args,
        linefmt=None,
        markerfmt=None,
        basefmt=None,
        bottom=0,
        label: Optional[str] = None,
        orientation: str = "vertical",
        **kwargs,
    ):
        """Draw a stem plot as GLE ``line impulses``.

        One positional argument is the y values, with ``x = 0 .. n-1``.
        Two are ``x, y``. The stems and their head markers are one GLE
        dataset, so they share a color. The default head is a filled
        circle; pass ``markerfmt='none'`` for stems alone.

        GLE's impulse origin is not matplotlib's ``bottom``. It is 0 when
        the y range includes 0, otherwise the range edge nearest 0 (the
        axis range, unless the dataset sets its own). No baseline is drawn.
        ``orientation='horizontal'`` warns and still draws vertical stems.

        Returns
        -------
        self
            gleplot's other plotting methods return the axes, not a
            matplotlib ``StemContainer``.
        """
        if len(args) == 1:
            y = np.asarray(args[0])
            if getattr(y, "ndim", 1) == 0:
                raise TypeError("stem() y must be a sequence of values")
            x = np.arange(len(y), dtype=float)
        elif len(args) == 2:
            x, y = args
        else:
            raise TypeError(
                f"stem() takes 1 or 2 positional arguments ({len(args)} given)"
            )

        if "use_line_collection" in kwargs:
            kwargs.pop("use_line_collection")
            warn_external(
                "stem(use_line_collection=...) is ignored.",
            )
        if "data" in kwargs:
            kwargs.pop("data")
            warn_external(
                "stem(data=...) is not supported and was ignored. "
                "Pass the x and y arrays directly.",
            )

        orient = str(orientation).strip().lower()
        if orient not in ("vertical", "horizontal"):
            raise ValueError(
                "orientation must be 'vertical' or 'horizontal', "
                f"got {orientation!r}"
            )
        if orient == "horizontal":
            warn_external(
                "stem(orientation='horizontal') is not supported: GLE "
                "impulses are vertical. Drawing a vertical stem of the "
                "given (x, y).",
            )

        try:
            bottom_value = float(bottom)
        except (TypeError, ValueError):
            warn_external(
                f"stem(bottom={bottom!r}) is not a number and was ignored.",
            )
            bottom_value = 0.0
        if bottom_value != 0.0:
            warn_external(
                "stem(bottom=...) does not move GLE's impulse origin. "
                "Impulses meet 0 when the y range includes 0, otherwise "
                "the range edge nearest 0. No baseline is drawn.",
            )

        if basefmt is not None and str(basefmt).strip().lower() not in ("", "none"):
            warn_external(
                "stem(basefmt=...) is not drawn. GLE impulses have no "
                "separate baseline; the verticals end at the impulse origin.",
            )

        line_ls, _line_marker, line_color = _split_plot_format(linefmt)
        _mark_ls, mark_marker, mark_color = _split_plot_format(markerfmt)

        if "linestyle" in kwargs:
            linestyle = kwargs.pop("linestyle")
        elif linefmt is None or line_ls is None:
            linestyle = "-"
        else:
            linestyle = line_ls

        if "marker" in kwargs:
            marker = kwargs.pop("marker")
        elif markerfmt is None:
            marker = "o"
        elif _mark_ls == "none":
            # 'none' / '' asks for no head marker. A color-only markerfmt
            # (no 'none', no marker character) keeps the default circle.
            marker = None
        else:
            marker = "o" if mark_marker is None else mark_marker

        if "color" not in kwargs:
            if (
                line_color is not None
                and mark_color is not None
                and line_color != mark_color
            ):
                warn_external(
                    "stem() line and marker colors differ "
                    f"({line_color!r} vs {mark_color!r}); GLE draws both in "
                    "the line color, because impulses and markers are one "
                    "dataset.",
                )
                kwargs["color"] = line_color
            elif line_color is not None:
                kwargs["color"] = line_color
            elif mark_color is not None:
                warn_external(
                    "stem() marker color applies to the impulses too: GLE "
                    "draws the stems and the markers as one dataset.",
                )
                kwargs["color"] = mark_color
        if label is not None:
            kwargs["label"] = label

        if linestyle in _NO_LINE:
            warn_external(
                "stem() draws no stems when the line format is 'none'; "
                "only markers are emitted.",
            )
        else:
            kwargs["line_mode"] = "impulses"
        return self.plot(
            x, y, linestyle=linestyle, marker=marker, _caller="stem", **kwargs
        )

    @_cartesian_only
    def hist(
        self,
        x,
        bins=10,
        range=None,
        density: bool = False,
        weights=None,
        cumulative: bool = False,
        bottom=None,
        histtype: str = "bar",
        align: str = "mid",
        orientation: str = "vertical",
        rwidth=None,
        log: bool = False,
        color=None,
        label=None,
        stacked: bool = False,
        **kwargs,
    ):
        """Bin samples and draw the counts.

        GLE bins the samples with ``let dK = hist dJ`` and stores a point at
        each bin centre. ``histtype='step'`` draws that dataset with
        ``line hist``. ``histtype='stepfilled'`` draws it as adjoining bars
        of one bin width from zero: ``fill x1`` would chord the centres and
        fill to the axis minimum, which is not the histogram.

        The drawn heights are counts, matplotlib's default. ``density``,
        ``weights``, ``cumulative``, ``bottom``, ``stacked`` and ``rwidth``
        are accepted and ignored, with a warning. ``histtype='bar'`` and
        ``'barstacked'`` warn and are drawn as a step outline; bar gaps and
        stacks belong to the bar grammar. Bins are equal width. The window
        is always written into the ``let`` (data min/max when ``range`` is
        omitted, widened by half a unit when every sample is the same
        value), so GLE does not re-bin over the axis.

        Returns this axes. matplotlib's ``(counts, edges, patches)`` is not
        available: the counts are computed by GLE at draw time.
        """

        def warn(message: str) -> None:
            warn_external(message)

        if density:
            warn("hist(density=True) is not supported; drawing counts.")
        if weights is not None:
            warn("hist(weights=...) is not supported and was ignored.")
        if cumulative:
            warn("hist(cumulative=True) is not supported; drawing raw counts.")
        if bottom not in (None, 0, 0.0):
            warn("hist(bottom=...) is not supported. Bins are drawn from zero.")
        if stacked:
            warn("hist(stacked=True) is not supported; each series is separate.")
        if rwidth is not None:
            warn("hist(rwidth=...) is not supported and was ignored.")
        if "data" in kwargs:
            kwargs.pop("data")
            warn(
                "hist(data=...) is not supported and was ignored. "
                "Pass the sample arrays directly."
            )

        style_name = str(histtype).strip().lower()
        if style_name in ("bar", "barstacked"):
            warn(
                f"hist(histtype={histtype!r}) is drawn as a step outline. "
                "Bar gaps, edges and stacks wait for the bar grammar."
            )
            style_name = "step"
        elif style_name not in ("step", "stepfilled"):
            raise ValueError(
                "histtype must be 'bar', 'barstacked', 'step' or "
                f"'stepfilled', got {histtype!r}"
            )

        align_name = str(align).strip().lower()
        if align_name not in ("left", "mid", "right"):
            raise ValueError(f"align must be 'left', 'mid' or 'right', got {align!r}")
        if align_name != "mid":
            warn(
                f"hist(align={align!r}) is not supported. GLE stores bin "
                "centres, so the bars stay centred."
            )

        orient = str(orientation).strip().lower()
        if orient not in ("vertical", "horizontal"):
            raise ValueError(
                "orientation must be 'vertical' or 'horizontal', "
                f"got {orientation!r}"
            )
        if orient == "horizontal":
            warn(
                "hist(orientation='horizontal') is not supported. Drawing "
                "a vertical histogram."
            )

        linestyle = kwargs.pop("linestyle", "-")
        linewidth = kwargs.pop("linewidth", 1)
        yaxis = kwargs.pop("yaxis", "y")
        xaxis = kwargs.pop("xaxis", "x")
        zorder = kwargs.pop("zorder", None)
        edgecolor = kwargs.pop("edgecolor", None)
        alpha = kwargs.pop("alpha", None)
        warn_unsupported_keywords("hist", kwargs)

        if yaxis not in ("y", "y2"):
            raise ValueError(f"yaxis must be 'y' or 'y2', got {yaxis!r}")
        if xaxis not in ("x", "x2"):
            raise ValueError(f"xaxis must be 'x' or 'x2', got {xaxis!r}")
        draw_yaxis = yaxis
        draw_xaxis = xaxis
        if style_name == "stepfilled" and yaxis == "y2":
            warn(
                "hist(histtype='stepfilled', yaxis='y2') is drawn on the "
                "primary y axis: GLE's bar command has no y2axis."
            )
            draw_yaxis = "y"
        if style_name == "stepfilled" and xaxis == "x2":
            warn(
                "hist(histtype='stepfilled', xaxis='x2') is drawn on the "
                "primary x axis: GLE's bar command has no x2axis."
            )
            draw_xaxis = "x"

        sets = _split_histogram_samples(x)
        finite_sets = []
        dropped = False
        for samples in sets:
            keep = np.isfinite(samples)
            if not np.all(keep):
                dropped = True
            kept = samples[keep]
            if len(kept) == 0:
                raise ValueError("hist() has no finite samples to bin")
            finite_sets.append(np.asarray(kept, dtype=float))
        if dropped:
            warn("hist() dropped non-finite samples.")

        window, n_bins = self._histogram_window(finite_sets, bins, range, warn)
        colors = self._per_histogram(color, len(finite_sets), broadcast_str=True)
        labels = self._per_histogram(label, len(finite_sets), broadcast_str=False)
        edges = self._per_histogram(edgecolor, len(finite_sets), broadcast_str=True)
        alphas = self._per_histogram(alpha, len(finite_sets), broadcast_str=True)
        if _is_dash_pattern(linestyle):
            # One dash tuple, not one style per sample set.
            linestyle = _line_style("hist", linestyle)
        linestyles = self._per_histogram(
            linestyle, len(finite_sets), broadcast_str=True
        )
        linewidths = self._per_histogram(
            linewidth, len(finite_sets), broadcast_str=True
        )

        bar_width = (window[1] - window[0]) / n_bins
        for samples, one_color, one_label, one_edge, one_alpha, one_ls, one_lw in zip(
            finite_sets, colors, labels, edges, alphas, linestyles, linewidths
        ):
            one_color, color_alpha = _rgba_parts(one_color)
            series_alpha = color_alpha if one_alpha is None else one_alpha
            ink = self._resolve_color(one_color)
            if series_alpha is not None:
                ink = apply_alpha(ink, series_alpha)
            fields = dict(
                samples=np.asarray(samples, dtype=float),
                bins=n_bins,
                hist_from=float(window[0]),
                hist_to=float(window[1]),
                histtype=style_name,
                color=ink,
                data_file=_resolve_data_file(self.figure),
            )
            if one_label is not None:
                fields["label"] = self._text(str(one_label))
            if style_name == "step":
                fields["linestyle"] = (
                    "-" if one_ls is None else _line_style("hist", one_ls)
                )
                fields["linewidth"] = float(1 if one_lw is None else one_lw)
                fields["yaxis"] = draw_yaxis
                _apply_xaxis(fields, draw_xaxis)
            else:
                # The stroke is the fill unless the caller named an edge, so
                # the shared boundary of two bins is not a second ink.
                stroke = ink
                if one_edge is not None:
                    stroke = self._resolve_color(one_edge)
                    if series_alpha is not None:
                        stroke = apply_alpha(stroke, series_alpha)
                fields["edgecolor"] = stroke
                fields["bar_width"] = float(bar_width)
                if one_ls not in (None, "-", "solid"):
                    warn(
                        "hist(histtype='stepfilled') ignores linestyle: "
                        "GLE's bar stroke has no lstyle in this form."
                    )
                try:
                    lw_value = float(one_lw) if one_lw is not None else 1.0
                except (TypeError, ValueError):
                    lw_value = 1.0
                if lw_value not in (0.0, 1.0):
                    warn(
                        "hist(histtype='stepfilled') ignores linewidth: "
                        "GLE's bar stroke has no lwidth in this form."
                    )
            entry = HistSeries(**fields)
            self._register_series_draw_meta(entry, "hist", zorder)
            self.hists.append(entry)

        if log:
            self.set_yscale("log", axis=draw_yaxis)
        return self

    def function(
        self,
        expression: str,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        step: Optional[float] = None,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
        zorder: Optional[float] = None,
    ):
        """Draw a curve that GLE samples from an expression in ``x``.

        Written as ``let dK = expression from xmin to xmax step step``, so
        the points are computed by GLE and no data file is written. Use
        :meth:`plot` when you already have the arrays.

        Parameters
        ----------
        expression : str
            A GLE expression in ``x``, such as ``"sin(x)"`` or
            ``"exp(-x^2/2)"``. It is written as given, without spaces.
        xmin, xmax : float, optional
            The sampled range. Omitted, GLE uses the x axis range; on a polar
            axes, ``x`` is theta and the range is 0 to 2 pi.
        step : float, optional
            Distance between samples. Omitted, GLE takes 100 points. On a
            log x axis GLE reads ``step`` as the number of points.
        color : str, optional
            Line colour; the style's default colour when omitted.
        linestyle : {'-', '--', ':', '-.'}
            Line style.
        linewidth : float
            Line width in points.
        label : str, optional
            Legend entry.
        zorder : float, optional
            Drawing order, as for :meth:`plot`.

        Returns
        -------
        Axes
            This axes.

        Notes
        -----
        gleplot does not evaluate the expression, so ``xmin`` and ``xmax``
        widen the x range but nothing widens the y range. Alone on an axes,
        the curve is scaled by GLE. Beside other data, call :meth:`set_ylim`
        if the curve leaves that data's range. On a polar axes the radial
        limit is 1 unless data or :meth:`set_ylim` sets it.
        """
        self._check_let_expression("function", expression)
        if self._polar:
            xmin = 0.0 if xmin is None else xmin
            xmax = 2 * np.pi if xmax is None else xmax
        fields = self._let_curve_fields(
            "function",
            xmin,
            xmax,
            step,
            color,
            linestyle,
            linewidth,
            label,
        )
        fields["expression"] = expression
        entry = FunctionSeries(**fields)
        self._register_series_draw_meta(entry, "function", zorder)
        self.functions.append(entry)
        return self

    @_cartesian_only
    def fit(
        self,
        x,
        y,
        expression: Optional[str] = None,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        step: Optional[float] = None,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
        zorder: Optional[float] = None,
        model: Optional[str] = None,
    ):
        """Draw the curve GLE fits to ``x`` and ``y``.

        Give either ``expression`` or ``model``. With ``expression``, written
        as ``let dK = fit dJ with expression from xmin to xmax step step``,
        GLE finds the coefficients, the names in ``expression`` other than
        ``x``, that fit the data best by least squares. With ``model``, GLE
        fits one of four curves in closed form with its own routine:

        ============  ===================  ============
        ``model``     curve                GLE routine
        ============  ===================  ============
        ``"linear"``  ``y = a*x+b``        ``linfit``
        ``"exp"``     ``y = a*exp(b*x)``   ``logefit``
        ``"exp10"``   ``y = a*10^(b*x)``   ``log10fit``
        ``"power"``   ``y = a*x^b``        ``powxfit``
        ============  ===================  ============

        Either way GLE draws the fitted curve. The data itself is not drawn:
        plot it with :meth:`scatter` or :meth:`plot`. To fit in Python
        instead, draw the fitted curve with :meth:`plot`.

        Parameters
        ----------
        x, y : array-like
            The data to fit, of equal length.
        expression : str, optional
            A GLE expression in ``x``, such as ``"a*exp(-x/b)+c"``. It is
            written as given, without spaces.
        xmin, xmax : float, optional
            The range the fitted curve is drawn over. Omitted, GLE uses the
            x axis range. Every point is fitted either way.
        step : float, optional
            Distance between curve samples. Omitted, GLE takes 100 points.
            On a log x axis GLE reads ``step`` as the number of points. Not
            with ``model``: GLE always draws a model at 100 points.
        color : str, optional
            Line colour; the style's default colour when omitted.
        linestyle : {'-', '--', ':', '-.'}
            Line style.
        linewidth : float
            Line width in points.
        label : str, optional
            Legend entry. With ``model``, it can show the fitted values:
            see the Notes.
        zorder : float, optional
            Drawing order, as for :meth:`plot`.
        model : {'linear', 'exp', 'exp10', 'power'}, optional
            A curve GLE fits in closed form, in place of ``expression``. It
            needs points at two or more distinct x. ``"exp"`` and
            ``"exp10"`` need every y above 0, and ``"power"`` every x and y
            above 0: GLE fits a straight line to their logs.

        Returns
        -------
        Axes
            This axes.

        Notes
        -----
        GLE starts every coefficient of an ``expression`` at 0, and keeps
        the fitted values to itself, so they cannot be read back in Python.
        To start from other values, or to use the fitted ones, fit in Python
        and draw the curve with :meth:`plot`.

        With ``model``, the label can show what GLE fitted. Each of these
        placeholders is replaced by a number when GLE draws the legend:

        - ``"linear"``: ``{slope}`` (a), ``{offset}`` (b) and ``{rsq}``;
        - ``"exp"``, ``"exp10"`` and ``"power"``: ``{prefactor}`` (a),
          ``{exponent}`` (b) and ``{rsq}``.

        ``{rsq}`` is the r-squared of the fit. Add ``:.Nf`` for N decimal
        places or ``:.Ne`` for scientific notation, the same format specs
        as in Python: ``label="slope {slope:.2f}, r$^2$ {rsq:.3f}"``. Such a
        legend is drawn after the graph, as for ``bbox_to_anchor``, because
        GLE fits the data only once the graph is drawn. A placeholder of
        another model, another format, or a ``"`` in a label with a
        placeholder raises ``ValueError``.

        In a hand-written ``let dK = logefit dJ s o r`` (and the same for
        ``log10fit`` and ``powxfit``), GLE stores the exponent ``b`` in the
        first variable and the prefactor ``a`` in the second, the other way
        round from what the GLE manual says.

        The data bounds the x and y ranges, as for :meth:`plot`, and
        ``xmin`` and ``xmax`` widen the x range.
        """
        arrays = []
        for name, value in (("x", x), ("y", y)):
            try:
                arrays.append(np.asarray(value, dtype=float).ravel())
            except (TypeError, ValueError):
                raise TypeError(
                    f"fit() {name} must be a sequence of numbers, got {value!r}"
                ) from None
        x_arr, y_arr = arrays
        if x_arr.shape != y_arr.shape:
            raise ValueError(
                f"fit() x and y must have the same length, got "
                f"{x_arr.size} and {y_arr.size}"
            )
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        if not np.any(finite):
            raise ValueError("fit() needs at least one point with finite x and y")
        if model is None:
            if expression is None:
                raise ValueError(
                    "fit() needs an expression such as 'a*exp(-x/b)+c' or a "
                    "model such as 'linear'; got neither"
                )
            self._check_let_expression("fit", expression)
        else:
            if expression is not None:
                raise ValueError(
                    f"fit() takes an expression or a model, not both; got "
                    f"expression={expression!r} and model={model!r}"
                )
            self._check_fit_model(model, x_arr[finite], y_arr[finite], step)
        fields = self._let_curve_fields(
            "fit",
            xmin,
            xmax,
            step,
            color,
            linestyle,
            linewidth,
            label if model is None else None,
        )
        if model is None:
            fields["expression"] = expression
        else:
            fields["model"] = model
            if label is not None:
                fields["label"] = self._fit_label(str(label), model)
        fields["x"] = x_arr
        fields["y"] = y_arr
        fields["data_file"] = _resolve_data_file(self.figure)
        entry = FitSeries(**fields)
        self._register_series_draw_meta(entry, "fit", zorder)
        self.fits.append(entry)
        return self

    #: The series lists :meth:`derived` reads: the kinds drawn as one
    #: dataset. Of ``file_series``, only the ``line_from_file`` variant.
    _DERIVED_SOURCE_ATTRS: Tuple[str, ...] = (
        "lines",
        "scatters",
        "file_series",
        "functions",
        "fits",
    )

    @_cartesian_only
    def derived(
        self,
        expression: str,
        sources,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        step: Optional[float] = None,
        nsteps: Optional[int] = None,
        where: Optional[str] = None,
        range=None,
        color: Optional[str] = None,
        linestyle: str = "-",
        linewidth: float = 1,
        label: Optional[str] = None,
    ):
        """Draw a curve GLE computes from other series on this axes.

        Written as ``let dK = expression``, in which ``d1`` ... ``dn``
        stand for ``sources[0]`` ... ``sources[n-1]``; gleplot puts in the
        names it gives those series. GLE takes the x values of every
        source, reads each source's y at those x (interpolating between its
        points where it has none), and evaluates the expression there.
        Unless the sources share their x values, none may repeat an x
        value. The numbers stay inside GLE, so this also works on series
        read from a file with :meth:`line_from_file`::

            ax.line_from_file("run1.dat", 1, 2)
            ax.line_from_file("run2.dat", 1, 2)
            a, b = ax.file_series
            ax.derived("d1-d2", [a, b], label="difference")

        Parameters
        ----------
        expression : str
            A GLE expression in ``x`` and ``d1`` ... ``dn``, such as
            ``"d1-d2"`` or ``"(d1+d2)/2"``. It is written without spaces.
        sources : series or list of series
            The series ``d1`` ... ``dn`` stand for, at most 10, each used in
            ``expression`` or ``where``. Each is a line, scatter, file line,
            function or fit series of this axes, taken from ``ax.lines``,
            ``ax.scatters``, ``ax.file_series``, ``ax.functions`` or
            ``ax.fits``. A source with an ``offset`` is read without it.
        xmin, xmax : float, optional
            Also compute the curve at x values from ``xmin`` to ``xmax``.
        step : float, optional
            Distance between those extra x values.
        nsteps : int, optional
            The number of points from ``xmin`` to ``xmax``, in place of
            ``step``.
        where : str, optional
            Keep only the points where this GLE expression is true, such as
            ``"d1>0"`` or ``"(x>1)and(x<5)"``. Written without spaces.
        range : series or list of series, optional
            Compute the curve only at the x values of these series, taken
            from the same lists as ``sources``. Omitted, every source's x
            values are used.
        color : str, optional
            Line colour; the style's default colour when omitted.
        linestyle : {'-', '--', ':', '-.'}
            Line style.
        linewidth : float
            Line width in points.
        label : str, optional
            Legend entry.

        Returns
        -------
        Axes
            This axes.

        Notes
        -----
        The curve is drawn on top of every other data series of the axes,
        after the series it reads, and against the primary x and y axes,
        whichever axes its sources use. Only GLE's single-expression form is
        written: the parametric ``let ds = x-exp, y-exp`` is not.

        Each source is stored as its list and its position there, such as
        ``ax.lines[1]``. Removing or inserting a series before it in that
        list makes the curve read whichever series then stands there. If a
        source is hidden or cannot be loaded when the figure is saved, or
        its position no longer holds a series ``derived`` accepts, the
        curve is left out with a warning.

        gleplot does not evaluate the expression, so the curve does not
        widen the y range. Call :meth:`set_ylim` if it leaves the range of
        the other data.
        """
        source_refs = self._derived_refs("sources", sources)
        if len(source_refs) > 10:
            raise ValueError(
                f"derived() sources holds {len(source_refs)} series, but GLE "
                f"reads at most 10 datasets in one let; split the expression"
            )
        texts = [expression] if where is None else [expression, where]
        for name, text in zip(("expression", "where"), texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"derived() {name} must be a str such as 'd1-d2', got "
                    f"{type(text).__name__}"
                )
            problem = _let_expression_problem(text)
            if problem is not None:
                raise ValueError(
                    f"derived() {name} {text!r} cannot be used: {problem}."
                )
        used = {
            int(match.group(0)[1:])
            for text in texts
            for match in _DATASET_NAME_RE.finditer(text)
        }
        count = len(source_refs)
        for k in sorted(used):
            if not 1 <= k <= count:
                raise ValueError(
                    f"derived() names d{k}, but sources holds {count} series: "
                    f"d1 ... d{count} stand for sources[0] ... sources[{count - 1}]"
                )
        for k, _ in enumerate(source_refs, 1):
            if k not in used:
                raise ValueError(
                    f"derived() never uses sources[{k - 1}]: write d{k} in the "
                    f"expression or where, or leave it out of sources"
                )
        if nsteps is not None:
            if isinstance(nsteps, bool) or not isinstance(nsteps, (int, np.integer)):
                raise TypeError(
                    f"derived() nsteps must be an int, got {type(nsteps).__name__}"
                )
            if nsteps < 2:
                raise ValueError(f"derived() nsteps must be 2 or more, got {nsteps!r}")
            if step is not None:
                raise ValueError(
                    f"derived() takes step or nsteps, not both; got step={step!r} "
                    f"and nsteps={nsteps!r}"
                )
        fields = self._let_curve_fields(
            "derived", xmin, xmax, step, color, linestyle, linewidth, label
        )
        fields["expression"] = expression
        fields["sources"] = source_refs
        if nsteps is not None:
            fields["let_nsteps"] = int(nsteps)
        if where is not None:
            fields["let_where"] = where
        if range is not None:
            fields["let_range"] = self._derived_refs("range", range)
        entry = DerivedSeries(**fields)
        self._register_series_draw_meta(entry, "derived")
        self.derived_series.append(entry)
        return self

    def _derived_refs(self, name, value) -> List[List[Any]]:
        """``[attr, index]`` of each series in ``value``, for :meth:`derived`."""
        items = [value] if isinstance(value, Series) else value
        if not isinstance(items, (list, tuple)) or not items:
            raise TypeError(
                f"derived() {name} must be a series of this axes, such as "
                f"ax.lines[0], or a non-empty list of them; got "
                f"{type(value).__name__}"
            )
        refs: List[List[Any]] = []
        for item in items:
            if not isinstance(item, Series):
                raise TypeError(
                    f"derived() {name} must hold series of this axes, such as "
                    f"ax.lines[0]; got {type(item).__name__}"
                )
            ref = self._series_ref(item)
            if ref is None:
                raise ValueError(
                    f"derived() {name} must hold line, scatter, line_from_file, "
                    f"function or fit series of this axes, from ax.lines, "
                    f"ax.scatters, ax.file_series, ax.functions or ax.fits; got "
                    f"a {type(item).__name__} that is not one of them"
                )
            if ref in refs:
                raise ValueError(
                    f"derived() {name} holds ax.{ref[0]}[{ref[1]}] twice; "
                    f"give each series once"
                )
            refs.append(ref)
        return refs

    def _series_ref(self, series) -> Optional[List[Any]]:
        """``[attr, index]`` of ``series`` if :meth:`derived` can read it."""
        for attr in self._DERIVED_SOURCE_ATTRS:
            for index, candidate in enumerate(getattr(self, attr)):
                if candidate is series:
                    if attr == "file_series" and series.get("series_type") != "line":
                        return None
                    return [attr, index]
        return None

    def _derived_operands(self, series) -> Optional[Tuple[List[Any], List[Any]]]:
        """The series a :class:`DerivedSeries` reads: its sources and range.

        ``None`` when a stored ``[attr, index]`` no longer points at a
        series :meth:`derived` accepts.
        """
        groups: List[List[Any]] = []
        for key in ("sources", "let_range"):
            group = []
            for ref in series.get(key, []):
                if not isinstance(ref, (list, tuple)) or len(ref) != 2:
                    return None
                attr, index = ref
                if (
                    attr not in self._DERIVED_SOURCE_ATTRS
                    or not isinstance(index, int)
                    or not 0 <= index < len(getattr(self, attr))
                ):
                    return None
                items = getattr(self, attr)
                if self._series_ref(items[index]) != [attr, index]:
                    return None
                group.append(items[index])
            groups.append(group)
        return groups[0], groups[1]

    @staticmethod
    def _check_fit_model(model, x, y, step) -> None:
        """Reject a ``fit`` ``model`` GLE cannot fit to the finite ``x``, ``y``."""
        if not isinstance(model, str):
            raise TypeError(
                f"fit() model must be a str such as 'linear', got "
                f"{type(model).__name__}"
            )
        if model not in FIT_MODEL_TO_ROUTINE:
            raise ValueError(
                f"fit() model must be one of "
                f"{', '.join(map(repr, FIT_MODEL_TO_ROUTINE))}, got {model!r}"
            )
        # GLE writes the fitted curve as a new ``let ... from a to b``, so a
        # step never reaches it.
        if step is not None:
            raise ValueError(
                f"fit() step has no effect with a model (GLE draws the curve at "
                f"100 points), got step={step!r}; leave it out"
            )
        # The routines fit log(y), and powxfit log(x) too, by ordinary least
        # squares, which aborts GLE on under two points or one distinct x.
        logs = []
        if model in ("exp", "exp10", "power"):
            logs.append(("y", y))
        if model == "power":
            logs.append(("x", x))
        for name, values in logs:
            if np.any(values <= 0):
                raise ValueError(
                    f"fit() model {model!r} needs every {name} above 0, got "
                    f"{name}={float(values[values <= 0][0])!r}; drop those points "
                    f"or use an expression"
                )
        if np.unique(x).size < 2:
            raise ValueError(
                f"fit() model {model!r} needs points at two or more distinct x, "
                f"got x={x.tolist()!r}"
            )

    def _fit_label(self, label: str, model: str) -> str:
        """A model fit's ``label`` as display text, its placeholders kept.

        Rejects a placeholder ``model`` does not fill, a format GLE's
        ``format$`` cannot match, and a ``"`` beside a placeholder: GLE
        string expressions have no escape for it.
        """
        names = FIT_RESULT_PLACEHOLDERS[model]
        found = list(FIT_PLACEHOLDER_RE.finditer(label))
        for match in found:
            name, spec = match.groups()
            if name not in names:
                raise ValueError(
                    f"fit() label placeholder {match.group(0)!r} is not filled by "
                    f"model={model!r}, which fills "
                    f"{', '.join('{' + n + '}' for n in names)}"
                )
            if spec is not None and not FIT_PLACEHOLDER_SPEC_RE.fullmatch(spec):
                raise ValueError(
                    f"fit() label placeholder {match.group(0)!r} has format "
                    f"{spec!r}; use .Nf or .Ne, such as {{{name}:.2f}}"
                )
        if not found:
            return self._text(label)
        if '"' in label:
            raise ValueError(
                f"fit() label {label!r} cannot contain a double quote beside a "
                f"placeholder; use two single quotes instead"
            )
        if self._style().usetex:
            return label
        # Each placeholder passes through mathtext as a braced private-use
        # marker, so it is still one group after ``^`` or ``_`` in math.
        # Outside math, mathtext escapes those braces, which go again.
        index = iter(range(len(found)))
        marked = FIT_PLACEHOLDER_RE.sub(
            lambda m: f"{{\ue000{next(index)}\ue001}}", label
        )
        return re.sub(
            r"(?:\\char\{123\})?\ue000(\d+)\ue001(?:\\char\{125\})?",
            lambda m: found[int(m.group(1))].group(0),
            self._text(marked),
        )

    @staticmethod
    def _check_let_expression(caller, expression) -> None:
        """Reject an expression ``function``/``fit``/``function2d`` cannot write."""
        example = {"function": "sin(x)", "function2d": "sin(x)*cos(y)"}.get(
            caller, "a*exp(-x/b)+c"
        )
        if not isinstance(expression, str):
            raise TypeError(
                f"{caller}() expression must be a str such as {example!r}, got "
                f"{type(expression).__name__}"
            )
        problem = _function_expression_problem(expression)
        if problem is not None:
            raise ValueError(
                f"{caller}() expression {expression!r} cannot be used: {problem}."
            )

    def _let_curve_fields(
        self,
        caller,
        xmin,
        xmax,
        step,
        color,
        linestyle,
        linewidth,
        label,
    ) -> Dict[str, Any]:
        """Check the arguments :meth:`function` and :meth:`fit` share.

        Returns the series fields they set, named for ``caller`` in errors.
        """
        if linestyle not in ("-", "--", ":", "-."):
            raise ValueError(
                f"{caller}() linestyle must be '-', '--', ':' or '-.', "
                f"got {linestyle!r}"
            )
        bounds = {}
        for name, value in (("xmin", xmin), ("xmax", xmax), ("step", step)):
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise TypeError(
                    f"{caller}() {name} must be a number, got {value!r}"
                ) from None
            if not np.isfinite(number):
                raise ValueError(f"{caller}() {name} must be finite, got {value!r}")
            bounds[name] = number
        if "step" in bounds and bounds["step"] <= 0:
            raise ValueError(f"{caller}() step must be positive, got {step!r}")
        if "xmin" in bounds and "xmax" in bounds and bounds["xmin"] >= bounds["xmax"]:
            raise ValueError(
                f"{caller}() needs xmin < xmax, got xmin={xmin!r}, xmax={xmax!r}"
            )

        fields: Dict[str, Any] = {}
        for name, key in (
            ("xmin", "let_from"),
            ("xmax", "let_to"),
            ("step", "let_step"),
        ):
            if name in bounds:
                fields[key] = bounds[name]
        fields["color"] = self._resolve_color(color)
        fields["linestyle"] = linestyle
        try:
            fields["linewidth"] = float(linewidth)
        except (TypeError, ValueError):
            raise TypeError(
                f"{caller}() linewidth must be a number of points, got {linewidth!r}"
            ) from None
        if label is not None:
            fields["label"] = self._text(str(label))
        return fields

    def _histogram_window(self, sets, bins, range, warn):
        """``(lo, hi)`` and the equal-width bin count for one ``hist`` call.

        A sequence of edges that is not equal-width is equalized over its
        first and last edge: GLE's ``bins`` and ``step`` are one width.
        """
        count = _as_bin_count(bins)
        if count is not None:
            if count < 1:
                raise ValueError(f"bins must be at least 1, got {bins!r}")
            if range is None:
                pooled = np.concatenate(sets)
                lo = float(np.min(pooled))
                hi = float(np.max(pooled))
                if lo == hi:
                    lo -= 0.5
                    hi += 0.5
            else:
                lo, hi = self._histogram_range(range)
            return (lo, hi), count

        if isinstance(bins, str):
            warn(f"hist(bins={bins!r}) is not supported. Using 10 equal-width bins.")
            return self._histogram_window(sets, 10, range, warn)

        try:
            edges = np.asarray(list(bins), dtype=float)
        except (TypeError, ValueError):
            raise ValueError(
                "bins must be an integer or a sequence of edges, " f"got {bins!r}"
            )
        if edges.ndim != 1 or len(edges) < 2:
            raise ValueError("bins edge sequence must contain at least two values")
        if not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
            raise ValueError("bins edges must be finite and strictly increasing")
        widths = np.diff(edges)
        if not np.allclose(widths, widths[0]):
            warn(
                "hist() equalized unequal bin edges over "
                f"[{edges[0]}, {edges[-1]}]. GLE histograms are equal width."
            )
        if range is not None:
            warn("hist() used the bin edges as the window and ignored range.")
        return (float(edges[0]), float(edges[-1])), int(len(edges) - 1)

    @staticmethod
    def _histogram_range(range):
        try:
            lo, hi = range
            lo = float(lo)
            hi = float(hi)
        except (TypeError, ValueError):
            raise ValueError(
                "range must be a pair of finite numbers, got " f"{range!r}"
            )
        if not np.isfinite(lo) or not np.isfinite(hi) or not hi > lo:
            raise ValueError(
                "range must be a pair of finite numbers with max > min, "
                f"got {range!r}"
            )
        return lo, hi

    @staticmethod
    def _per_histogram(value, n: int, broadcast_str: bool):
        """One value per sample set.

        A string broadcasts to every set when ``broadcast_str`` is set (a
        single colour) and otherwise labels only the first set. A sequence
        cycles. An RGB(A) tuple or 1-D array is one colour, not one channel
        per set.
        """
        if value is None:
            return [None] * n
        if isinstance(value, str):
            if broadcast_str:
                return [value] * n
            out: List[Optional[str]] = [None] * n
            out[0] = value
            return out
        if (
            isinstance(value, np.ndarray)
            and value.ndim == 1
            and value.size in (3, 4)
            and np.issubdtype(value.dtype, np.number)
        ):
            value = tuple(value.tolist())
        if (
            isinstance(value, tuple)
            and len(value) in (3, 4)
            and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) for c in value
            )
        ):
            return [value] * n
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return [value] * n
        try:
            seq = list(value)
        except TypeError:
            return [value] * n
        if len(seq) == 0:
            return [None] * n
        return [seq[i % len(seq)] for i in range(n)]

    @_cartesian_only
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
        linewidth: Optional[float] = 1,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        capsize_cm: Optional[float] = None,
        yaxis: str = "y",
        xaxis: str = "x",
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
        linewidth : float or None
            Line width in points; ``None`` means the default width.
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
            ``linestyle`` (alias ``ls``) overrides the line style ``fmt``
            gives, as in matplotlib, except under ``fmt='none'``. ``lw``, ``c`` and ``ms`` are
            matplotlib's short names for ``linewidth``, ``color`` and
            ``markersize``; the full name wins, with a warning, unless it is
            left at its default. Any other keyword (``ecolor``,
            ``elinewidth``, ``capthick``, ...) warns and is ignored.

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
        data_name = kwargs.pop("data_name", None)
        linewidth = _pop_line_alias(kwargs, "errorbar", "lw", "linewidth", linewidth, 1)
        color = _pop_line_alias(kwargs, "errorbar", "c", "color", color, None)
        markersize = _pop_line_alias(
            kwargs, "errorbar", "ms", "markersize", markersize, 6
        )
        linestyle = _pop_line_alias(
            kwargs, "errorbar", "ls", "linestyle", kwargs.pop("linestyle", None), None
        )
        linestyle = _line_style("errorbar", linestyle)
        warn_unsupported_keywords("errorbar", kwargs)
        label = self._text(label)
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        # Handle color (see _resolve_color: None = the style default).
        color = self._resolve_color(color)

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
        # As in matplotlib, a linestyle keyword overrides fmt's, except that
        # fmt='none' draws no data line whatever the keywords say.
        if linestyle is not None and fmt.lower() != "none":
            parsed_linestyle = linestyle

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

        # matplotlib reads None as the default width; 1 is the writer's
        # "style default" (see GLEWriter.add_errorbar_series).
        if linewidth is None:
            linewidth = 1

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
        _apply_xaxis(errbar_data, xaxis)
        self._register_series_draw_meta(errbar_data, "errorbar", zorder)
        self.errorbars.append(errbar_data)

        return self

    @_cartesian_only
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
        xaxis: str = "x",
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        skiprows: int = 0,
        comment: Optional[str] = None,
        max_rows: Optional[int] = None,
        **kwargs,
    ):
        """Plot by referencing columns in an existing external data file.

        This avoids writing generated ``data_*.dat`` files. Column indices are
        1-based to match GLE conventions; ``x_col=0`` uses the row number as
        x (see :meth:`line_from_file`).

        ``fillstyle='none'`` / ``markerfacecolor='none'`` (alias ``mfc``)
        select an open marker; ``markerfacecolor='white'`` selects a
        white-filled one.

        ``skiprows``, ``comment`` and ``max_rows`` control how GLE reads
        the file, as for :meth:`line_from_file`. ``c`` and ``ms`` are
        accepted for ``color`` and ``markersize``, as by :meth:`errorbar`;
        any other keyword warns and is ignored.
        """
        _check_file_columns(x_col, y_col=y_col, yerr_col=yerr_col)
        read_options = _file_read_options(skiprows, comment, max_rows)

        marker_fill = _pop_marker_fill(kwargs, fillstyle, markerfacecolor)
        caller = "errorbar_from_file"
        color = _pop_line_alias(kwargs, caller, "c", "color", color, None)
        markersize = _pop_line_alias(kwargs, caller, "ms", "markersize", markersize, 6)
        warn_unsupported_keywords(caller, kwargs)
        label = self._text(label)
        gle_color = self._resolve_color(color)

        gle_marker = get_gle_marker(marker, fill=marker_fill) if marker else None
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )
        gle_capsize = capsize_pt_to_cm(capsize) if capsize is not None else None

        entry = FileSeries(
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
            **read_options,
        )
        _apply_xaxis(entry, xaxis)
        self._register_series_draw_meta(entry, "errorbar")
        self.file_series.append(entry)

        return self

    @_cartesian_only
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
        xaxis: str = "x",
        drawstyle: Optional[str] = None,
        line_mode: Optional[str] = None,
        skiprows: int = 0,
        comment: Optional[str] = None,
        max_rows: Optional[int] = None,
    ):
        """Plot a line by referencing columns in an external data file.

        This avoids creating generated ``data_*.dat`` files for overlay lines.
        Column indices are 1-based to match GLE conventions. ``x_col=0``
        uses the row number (1, 2, 3, ...) as x; when the file's first
        column is text, GLE then labels those x positions with it.

        ``drawstyle`` and ``line_mode`` are the same line modes as
        :meth:`plot`. ``linestyle='none'`` warns and drops the mode: there
        is no line for it to qualify. The series is still a line reference;
        this method has no scatter form.

        ``skiprows`` skips that many leading lines of the file, ``comment``
        replaces GLE's comment marker ``!``, and ``max_rows`` stops after
        that many data rows (comment and blank lines do not count). They
        are GLE's ``ignore``, ``comment`` and ``numrows`` options. GLE
        itself reads a ``.gz`` file, so ``data_file`` may name one.
        """
        _check_file_columns(x_col, y_col=y_col)
        read_options = _file_read_options(skiprows, comment, max_rows)

        label = self._text(label)
        gle_color = self._resolve_color(color)
        linestyle = _line_style("line_from_file", linestyle)
        mode = resolve_line_mode(drawstyle, line_mode)
        if mode and linestyle in _NO_LINE:
            warn_external(
                f"line mode {mode!r} needs a drawn line; linestyle={linestyle!r} "
                "omits it, so the series is drawn without that mode.",
            )
            mode = None

        fields = dict(
            series_type="line",
            data_file=data_file,
            x_col=int(x_col),
            y_col=int(y_col),
            color=gle_color,
            linestyle=linestyle,
            linewidth=float(linewidth),
            nomiss=False,
            label=label,
            yaxis=yaxis,
            **read_options,
        )
        _apply_xaxis(fields, xaxis)
        if mode:
            fields["line_mode"] = mode
        entry = FileSeries(**fields)
        self._register_series_draw_meta(entry, "line")
        self.file_series.append(entry)

        return self

    #: Default ``scatter`` size, in matplotlib's points**2.
    SCATTER_DEFAULT_S = 20

    def scatter(
        self,
        x,
        y,
        color: Optional[str] = None,
        s: Optional[Union[float, Sequence[float]]] = None,
        marker: str = "o",
        label: Optional[str] = None,
        yaxis: str = "y",
        xaxis: str = "x",
        markersize: Optional[Union[float, Sequence[float]]] = None,
        fillstyle: Optional[str] = None,
        markerfacecolor: Optional[str] = None,
        zorder: Optional[float] = None,
        *,
        c: Any = None,
        cmap: Optional[str] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        norm: Any = None,
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
        s : float or array-like, optional
            Marker area in points**2 (matplotlib ``scatter`` convention).
            Default 20 when neither ``s`` nor ``markersize`` is given. An
            array gives each point its own size; see Notes.
        marker : str
            Marker symbol
        label : str, optional
            Legend label
        yaxis : str, optional
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        markersize : float or array-like, optional
            Marker diameter in points (matplotlib ``Line2D``/:meth:`plot`
            convention). Takes precedence over ``s``. An array gives each
            point its own size; see Notes.
        fillstyle : {'full', 'none'}, optional
            ``'none'`` draws open (outline) markers instead of filled ones.
        markerfacecolor : str, optional
            ``'none'`` is equivalent to ``fillstyle='none'``; ``'white'``
            gives outline markers with an opaque white interior. Also
            accepted as the matplotlib alias ``mfc``.
        zorder : float, optional
            Draw order relative to other data series on the same axes.
            Higher values are drawn on top.
        c : array-like or color, optional
            One number per point colours each point through ``cmap``, as in
            matplotlib. One colour is the same as ``color``; a sequence with
            one colour per point is drawn as one series per distinct colour.
            Cannot be combined with ``color``.
        cmap : str, optional
            Colormap for numeric ``c``. Default: the figure graph config's
            ``default_cmap``.
        vmin, vmax : float, optional
            The values given the colormap's first and last colour. Default:
            the smallest and largest finite value of ``c``. A value outside
            them takes the end colour.
        norm : optional
            Not supported: colours are always mapped linearly from ``vmin``
            to ``vmax``. Passing it warns.
        **kwargs
            Passed to :meth:`plot`, which owns ``mdist``, ``deresolve``,
            ``deresolve_average`` and the ``xmin`` / ``xmax`` / ``ymin`` /
            ``ymax`` clip window.

        Returns
        -------
        self

        Notes
        -----
        Per-point sizes (a bubble chart) take one finite, non-negative value
        per point; a one-element array is a single size. GLE's ``mdata``
        scales only a marker drawn by a subroutine, so the script gets a
        ``gleplot_mdata_<marker>`` sub that draws the built-in marker at each
        point's size. The legend marker's area is halfway between the largest
        and smallest point's, as in matplotlib's legend. Per-point sizes
        cannot be combined with ``mdist`` or ``deresolve``.

        Per-point colours (numeric ``c``) work the same way: the script gets
        a ``gleplot_cdata_<marker>_<cmap>`` sub that draws the built-in
        marker in each point's colour. The values are written to the data
        file as given, and a ``let`` maps them onto the colormap. A point
        whose value is not finite is left out, as matplotlib leaves it out
        of the plot and its limits. The legend marker takes the
        colormap's last colour. Per-point colours cannot be combined with
        per-point sizes, ``mdist`` or ``deresolve``.

        A colour sequence draws one series per distinct colour, in the order
        each first appears; only the first carries ``label``.
        """
        values = None
        colors = None
        if c is not None:
            if color is not None:
                raise ValueError(
                    f"scatter() got both c={c!r} and color={color!r}; pass one "
                    "of them."
                )
            kind, found = _scatter_c(c, int(np.size(x)))
            if kind == "color":
                color = found
            elif kind == "colors":
                colors = found
            else:
                values = found
        if values is None:
            for name, value in (("cmap", cmap), ("vmin", vmin), ("vmax", vmax)):
                if value is not None:
                    warn_external(
                        f"scatter({name}={value!r}) is ignored: there are no "
                        "values to colour-map. Pass c= with one number per "
                        "point."
                    )
        if norm is not None:
            warn_external(
                f"scatter(norm={norm!r}) is ignored: gleplot maps colours "
                "linearly from vmin to vmax. Pass vmin= and vmax= instead."
            )
        if colors is not None:
            return self._scatter_by_color(
                x,
                y,
                colors,
                s=s,
                markersize=markersize,
                label=label,
                marker=marker,
                yaxis=yaxis,
                xaxis=xaxis,
                fillstyle=fillstyle,
                markerfacecolor=markerfacecolor,
                zorder=zorder,
                **kwargs,
            )
        mapping = None
        if values is not None:
            mapping = self._color_mapping(values, cmap, vmin, vmax)
        label = self._text(label)

        default_size = float(np.sqrt(self.SCATTER_DEFAULT_S) * 1.2)
        diameters = None
        size = default_size
        if markersize is None:
            if s is None:
                s = self.SCATTER_DEFAULT_S
            # matplotlib: s is an area in points**2 and markersize a diameter
            # in points, so markersize = sqrt(s). The 1.2 is gleplot's own
            # visibility factor, kept so scatter sizes are unchanged.
            if np.ndim(s) == 0:
                size = float(np.sqrt(np.asarray(s, dtype=float)) * 1.2)
            else:
                diameters = np.sqrt(_point_sizes("s", s, np.size(x))) * 1.2
        elif np.ndim(markersize) == 0:
            size = float(np.asarray(markersize, dtype=float))
        else:
            diameters = _point_sizes("markersize", markersize, np.size(x))
        mdata = None
        if diameters is not None and diameters.size == 1:
            size = float(diameters[0])
        elif diameters is not None and diameters.size > 1:
            if mapping is not None:
                raise ValueError(
                    "scatter() cannot give each point both its own colour (c=) "
                    "and its own size (s= or markersize=) yet: GLE carries one "
                    "per-point value on a dataset. Pass one size, or one colour."
                )
            # The legend marker's area is halfway between the largest and
            # smallest point's, as in matplotlib's scatter legend.
            size = float(np.sqrt((diameters.max() ** 2 + diameters.min() ** 2) / 2))
            if size == 0.0:
                # GLE reads msize 0 as "the font height": keep the default
                # size and scale every point down to nothing.
                size = default_size
            mdata = diameters / size
        per_point = (
            "colour" if mapping is not None else "size" if mdata is not None else None
        )
        for qualifier in ("mdist", "deresolve") if per_point else ():
            if kwargs.get(qualifier) is not None:
                raise ValueError(
                    f"scatter({qualifier}={kwargs[qualifier]!r}) cannot be "
                    f"combined with per-point {per_point}s: GLE ignores per-point "
                    f"{per_point}s under {qualifier}. Pass one {per_point}, or "
                    f"drop {qualifier}."
                )
        if mapping is not None and not np.all(np.isfinite(mapping["cdata"])):
            # matplotlib leaves a point with no colour out (plotnonfinite).
            keep = np.isfinite(mapping["cdata"])
            x = np.asarray(x)[keep]
            y = np.asarray(y)[keep]
            mapping["cdata"] = mapping["cdata"][keep]
        count = len(self.scatters)
        self.plot(
            x,
            y,
            linestyle="none",
            color=color,
            marker=marker,
            markersize=size,
            label=label,
            yaxis=yaxis,
            xaxis=xaxis,
            fillstyle=fillstyle,
            markerfacecolor=markerfacecolor,
            zorder=zorder,
            _caller="scatter",
            **kwargs,
        )
        # No marker draws nothing, so there is no size to give each point.
        if (
            mdata is not None
            and len(self.scatters) > count
            and self.scatters[-1]["marker"]
        ):
            series = self.scatters[-1]
            series["mdata"] = mdata
            series["column_names"] = series.default_column_names()
        if (
            mapping is not None
            and len(self.scatters) > count
            and self.scatters[-1]["marker"]
        ):
            series = self.scatters[-1]
            # The marker sub sets each point's colour; the line carries none.
            series["color"] = None
            series.update(mapping)
            series["column_names"] = series.default_column_names()
        return self

    def _color_mapping(self, values, cmap, vmin, vmax) -> Dict[str, Any]:
        """``scatter``'s ``cdata``, ``cmap``, ``vmin`` and ``vmax`` fields.

        Raises ``ValueError`` for an unknown ``cmap``, a limit that is not a
        finite number, or ``vmin`` above ``vmax``.
        """
        limits: List[Optional[float]] = []
        for name, value in (("vmin", vmin), ("vmax", vmax)):
            try:
                number = None if value is None else float(value)
            except (TypeError, ValueError):
                number = float("nan")
            if number is not None and not np.isfinite(number):
                raise ValueError(
                    f"scatter({name}=...) must be a finite number, got {value!r}."
                )
            limits.append(number)
        finite = values[np.isfinite(values)]
        lo, hi = limits
        if lo is None:
            lo = float(finite.min()) if finite.size else (hi or 0.0)
        if hi is None:
            hi = float(finite.max()) if finite.size else lo
        if lo > hi:
            raise ValueError(
                f"scatter() needs vmin <= vmax, got vmin={lo!r} and vmax={hi!r}."
            )
        return {
            "cdata": values,
            "cmap": self._resolve_cmap(cmap),
            "vmin": lo,
            "vmax": hi,
        }

    def _scatter_by_color(self, x, y, colors, s, markersize, label, **kwargs):
        """``scatter`` with one colour per point: one series per colour.

        A GLE dataset has one colour. The series follow the order in which
        each colour first appears, and only the first carries ``label``.
        """
        n_points = len(colors)
        for name, sizes in (("s", s), ("markersize", markersize)):
            if sizes is not None and np.ndim(sizes) > 0:
                _point_sizes(name, sizes, n_points)
        groups: Dict[str, List[int]] = {}
        for point, item in enumerate(colors):
            groups.setdefault(rgb_to_gle(item), []).append(point)
        x = np.asarray(x)
        y = np.asarray(y)

        def subset(sizes, mask):
            if sizes is not None and np.ndim(sizes) > 0 and np.size(sizes) > 1:
                return np.asarray(sizes, dtype=float).ravel()[mask]
            return sizes

        for index, (token, mask) in enumerate(groups.items()):
            self.scatter(
                x[mask],
                y[mask],
                color=token,
                s=subset(s, mask),
                markersize=subset(markersize, mask),
                label=label if index == 0 else None,
                **kwargs,
            )
        return self

    @_cartesian_only
    def bar(
        self,
        x,
        height,
        color: Optional[Union[str, Sequence]] = None,
        label: Optional[str] = None,
        zorder: Optional[float] = None,
        width: Optional[float] = None,
        bottom=None,
        align: str = "center",
        edgecolor=None,
        linewidth: Optional[float] = None,
        linestyle: Optional[str] = None,
        yerr=None,
        xerr=None,
        ecolor=None,
        capsize: Optional[float] = None,
        capsize_cm: Optional[float] = None,
        error_kw: Optional[dict] = None,
        **kwargs,
    ):
        """
        Create a bar chart.

        One GLE dataset has one face colour and one edge colour. A colour
        sequence therefore becomes one series per bar (each its own
        ``bar dN``), so the bars keep the positions in ``x``. A grouped
        chart is two calls with the x of the second shifted by the width,
        which is what matplotlib does; a hand-written ``bar d1,d2 fill
        c1,c2`` is the engine's own side-by-side form and round-trips as
        one command.

        ``bottom`` stacks: the bar runs from that baseline to
        ``bottom + height`` (GLE ``bar dTo from dFrom``). ``edgecolor`` is
        the stroke (GLE ``color``); ``linewidth`` and ``linestyle`` are
        ``lwidth`` and ``lstyle``. ``barh`` is the horizontal form.

        Parameters
        ----------
        x : array-like
            Bar positions.
        height : array-like
            Bar lengths. With ``bottom``, the top is ``bottom + height``.
        color : str or sequence, optional
            Face colour. A sequence must have one entry, or one per bar.
            Default ``'red'``. ``facecolor`` / ``fc`` / ``c`` are aliases.
        label : str, optional
            Legend label. Emitted as ``dN key`` after the bar; the bar fill
            is the swatch. On a per-bar colour split, only the first bar
            carries it.
        width : float, optional
            Bar thickness in DATA units (G19), GLE's ``bar dN ... width w``.
            The default, ``None``, is the engine's own behaviour and
            gleplot's historical one: GLE sizes the set from the data,
            taking half the smallest gap between consecutive x values.
            Deliberately *not* matplotlib's constant ``0.8`` default -- every
            bar chart written before this parameter existed must keep
            emitting the script it emits now. Note also that ``width`` is a
            keyword here where matplotlib's is positional: this method's
            third positional parameter has always been ``color``.
        bottom : float or array-like, optional
            Baseline. ``0`` (matplotlib's default) draws from zero and is
            not written. An array must have one value per bar.
        align : {'center', 'edge'}, optional
            GLE centers every bar on its x value. ``'edge'`` warns and is
            drawn centered.
        edgecolor : str or sequence, optional
            Stroke colour (GLE ``color``). ``'none'`` emits ``lwidth 0``:
            GLE has no missing edge. ``ec`` is an alias.
        linewidth, linestyle : optional
            Edge width in points and matplotlib linestyle. ``lw`` / ``ls``
            are aliases. Omitted, the command carries neither keyword.
        yerr, xerr : float or array-like, optional
            Vertical and horizontal errors at the bar tip. A scalar or a
            length-``n`` sequence is symmetric. Shape ``(2, n)`` is
            asymmetric: the first row is the minus side, the second the
            plus side. Shape ``(2, 1)`` broadcasts. On a horizontal bar the
            tip is ``left + width``; ``xerr`` runs along the length.
        ecolor : color or sequence, optional
            Whisker colour. Default black. One colour is one error-bar
            series; a sequence of different colours is one series per bar.
        capsize : float, optional
            Cap width in matplotlib points, written as GLE ``errwidth`` /
            ``herrwidth``. Omitted, the keyword is left off and GLE draws
            its own cap (one third of the font height). ``capsize=0`` is
            that same default: GLE treats a zero width as "not given".
            ``capsize_cm`` is the width in centimetres and wins over
            ``capsize``.
        error_kw : dict, optional
            ``ecolor``, ``capsize``, ``capsize_cm`` and ``zorder`` override
            the matching arguments. Any other key is ignored, with a
            warning. A ``zorder`` here, or on the bar, is raised by ``0.01``
            so the whisker is drawn above the bar.
        horiz : bool, optional
            Emit ``horiz``. :meth:`barh` sets this.
        **kwargs
            ``hatch`` is a matplotlib hatch string, or a sequence with one
            per bar. ``'/'``, ``'\\'`` and ``'x'`` are GLE's ``SHADE``,
            ``RSHADE`` and ``GRID`` patterns; repeated (``'//'``) they are
            the denser ``SHADE2``, ``RSHADE2`` and ``GRID2``. As in
            matplotlib, the hatch is drawn in ``edgecolor`` (black when it
            is not given or ``'none'``) over the face colour. GLE has no
            other pattern, so any other hatch warns and the bar is solid. Anything else GLE cannot draw is accepted and
            warned about.

        Returns
        -------
        self
        """
        data_name = kwargs.pop("data_name", None)
        if zorder is None and "zorder" in kwargs:
            zorder = kwargs.pop("zorder")
        horiz = bool(kwargs.pop("horiz", False))
        color, edgecolor, linewidth, linestyle = _bar_style_aliases(
            kwargs, color, edgecolor, linewidth, linestyle
        )
        hatch = kwargs.pop("hatch", None)
        align_name = str(align).strip().lower()
        if align_name not in ("center", "edge"):
            raise ValueError("align must be 'center' or 'edge', got " f"{align!r}")
        if align_name == "edge":
            warn_external(
                "bar(align='edge') is drawn centered: GLE places each bar "
                "on its x value.",
            )
        warn_unsupported_keywords("bar", kwargs)
        if error_kw is None:
            error_extra: Dict[str, Any] = {}
        elif isinstance(error_kw, dict):
            error_extra = dict(error_kw)
        else:
            raise TypeError("bar() error_kw must be a dict")
        if "ecolor" in error_extra:
            ecolor = error_extra.pop("ecolor")
        if "capsize" in error_extra:
            capsize = error_extra.pop("capsize")
        if "capsize_cm" in error_extra:
            capsize_cm = error_extra.pop("capsize_cm")
        err_zorder = error_extra.pop("zorder", None)
        if err_zorder is None:
            err_zorder = zorder
        if err_zorder is not None:
            err_zorder = float(err_zorder) + 0.01
        if (yerr is not None or xerr is not None) and error_extra:
            names = ", ".join(sorted(str(key) for key in error_extra))
            warn_external(
                f"bar() ignores unsupported error_kw key(s): {names}.",
            )
        label = self._text(label)

        x = np.asarray(x, dtype=float).ravel()
        height = np.asarray(height, dtype=float).ravel()
        if x.shape != height.shape:
            raise ValueError(
                f"bar() x and height must have the same length, got "
                f"{x.size} and {height.size}"
            )
        n = int(x.size)
        if n == 0:
            raise ValueError("bar() needs at least one bar")

        faces = _bar_color_list(color, n, default="RED")
        edges = _bar_color_list(edgecolor, n, default=None)
        # GLE's ``fill`` is the hatch ink and ``background`` the face, so a
        # hatched bar fills with its edge colour: matplotlib's hatch colour,
        # which falls back to black when the edge is missing or 'none'.
        fills: List[Optional[str]] = []
        patterns: List[Optional[str]] = []
        backgrounds: List[Optional[str]] = []
        for pattern, face, edge in zip(_bar_patterns(hatch, n), faces, edges):
            patterns.append(pattern)
            if pattern is None:
                fills.append(face)
                backgrounds.append(None)
            else:
                fills.append(edge if edge not in (None, "none") else "BLACK")
                backgrounds.append("CLEAR" if face == "none" else face)
        baseline = _bar_baseline(bottom, n)
        style = _bar_edge_style(linewidth, linestyle)
        # Reject a bad error before any series is stored, so a raise leaves
        # the axes as they were.
        y_lo, y_hi = _bar_error_limits(yerr, n, "yerr")
        x_lo, x_hi = _bar_error_limits(xerr, n, "xerr")
        err_colors = None
        if yerr is not None or xerr is not None:
            err_colors = _bar_color_list(
                "black" if ecolor is None else ecolor, n, default="BLACK"
            )

        # One dataset, one face and one edge. Differing colours are separate
        # series so each bar is a ``bar dN`` at its own x. Uniform colours
        # stay one series: that is every bar chart gleplot has ever written.
        vary = len(set(zip(fills, edges, patterns, backgrounds))) > 1
        if not vary:
            self._append_bar(
                x,
                height,
                fills,
                label,
                data_name,
                width,
                zorder,
                baseline,
                edges[0],
                style,
                horiz,
                patterns[0],
                backgrounds[0],
            )
        else:
            # A one-point dataset has no gap for GLE to measure, so each piece
            # carries the thickness the combined set would have been given.
            piece_width = width
            if piece_width is None:
                piece_width = _bar_width_for_split(x)
            for index in range(n):
                self._append_bar(
                    x[index : index + 1],
                    height[index : index + 1],
                    [fills[index]],
                    label if index == 0 else None,
                    data_name if index == 0 else None,
                    piece_width,
                    zorder,
                    None if baseline is None else baseline[index : index + 1],
                    edges[index],
                    style,
                    horiz,
                    patterns[index],
                    backgrounds[index],
                )
        self._add_bar_errors(
            x,
            height,
            baseline,
            horiz,
            y_lo,
            y_hi,
            x_lo,
            x_hi,
            err_colors,
            capsize,
            capsize_cm,
            err_zorder,
        )
        return self

    @_cartesian_only
    def barh(
        self,
        y,
        width,
        height: Optional[float] = None,
        left=None,
        align: str = "center",
        **kwargs,
    ):
        """Horizontal bars. See :meth:`bar`.

        ``width`` is the bar length (matplotlib's second positional) and
        ``height`` is the thickness. Thickness defaults to GLE's own
        derivation, the same as :meth:`bar`'s ``width``, not matplotlib's
        ``0.8``. ``left`` is the baseline (``bar``'s ``bottom``). ``xerr``
        and ``yerr`` are the same errors as :meth:`bar`: ``xerr`` runs
        along the length, from the tip.
        """
        if "width" in kwargs:
            raise TypeError(
                "barh() got width=: the bar length is the second positional "
                "argument, and the thickness is height="
            )
        return self.bar(
            y,
            width,
            width=height,
            bottom=left,
            align=align,
            horiz=True,
            **kwargs,
        )

    def _append_bar(
        self,
        x,
        height,
        colors,
        label,
        data_name,
        width,
        zorder,
        bottom,
        edgecolor,
        style,
        horiz,
        pattern=None,
        background=None,
    ):
        """Store one bar dataset. Optional keys stay absent."""
        fields = dict(
            x=np.asarray(x, dtype=float),
            height=np.asarray(height, dtype=float),
            colors=list(colors),
            label=label,
            data_file=_resolve_data_file(self.figure, data_name),
        )
        if bottom is not None:
            base = np.asarray(bottom, dtype=float)
            # The sidecar column is this top. Keeping it means the next save
            # writes those values back instead of a fresh subtraction.
            fields["bottom"] = base
            fields["top"] = base + np.asarray(height, dtype=float)
            fields["column_names"] = ["x", "bottom", "top"]
        else:
            fields["column_names"] = _build_column_names("x", ["height"], label)
        if width is not None:
            # Absent, not None: an unset width is the engine's to derive.
            fields["width"] = float(width)
        if edgecolor is not None:
            fields["edgecolor"] = edgecolor
        if style.get("linewidth") is not None:
            fields["linewidth"] = style["linewidth"]
        if style.get("linestyle") is not None:
            fields["linestyle"] = style["linestyle"]
        if horiz:
            fields["horiz"] = True
        if pattern is not None:
            fields["pattern"] = pattern
            fields["background"] = background
        bar_data = BarSeries(**fields)
        self._register_series_draw_meta(bar_data, "bar", zorder)
        self.bars.append(bar_data)

    def _add_bar_errors(
        self,
        x,
        height,
        baseline,
        horiz,
        y_lo,
        y_hi,
        x_lo,
        x_hi,
        colors,
        capsize,
        capsize_cm,
        zorder,
    ):
        """Draw whiskers at the bar tips as a markerless error-bar series.

        GLE's ``horiz`` swaps a bar's axes only inside ``draw_bar``. An
        ``err`` / ``herr`` dataset is not swapped, so the whisker is a
        separate series sitting on the tip in graph coordinates:
        ``(x, top)`` when the bar is vertical, ``(top, y)`` when it is
        horizontal. ``yerr`` stays vertical and ``xerr`` stays horizontal.
        The series is the same one :meth:`errorbar` writes, which is what
        makes the script round-trip.
        """
        if colors is None:
            return
        tops = np.asarray(height, dtype=float)
        if baseline is not None:
            tops = tops + np.asarray(baseline, dtype=float)
        category = np.asarray(x, dtype=float)
        if horiz:
            ex, ey = tops, category
        else:
            ex, ey = category, tops

        def _arg(lower, upper, sl=slice(None)):
            if lower is None:
                return None
            return (np.asarray(lower)[sl], np.asarray(upper)[sl])

        common = dict(
            fmt="none",
            capsize=capsize,
            capsize_cm=capsize_cm,
            zorder=zorder,
        )
        if len(set(colors)) == 1:
            self.errorbar(
                ex,
                ey,
                yerr=_arg(y_lo, y_hi),
                xerr=_arg(x_lo, x_hi),
                color=colors[0],
                **common,
            )
            return
        for index, color in enumerate(colors):
            sl = slice(index, index + 1)
            self.errorbar(
                ex[sl],
                ey[sl],
                yerr=_arg(y_lo, y_hi, sl),
                xerr=_arg(x_lo, x_hi, sl),
                color=color,
                **common,
            )

    @_cartesian_only
    def fill_between(
        self,
        x,
        y1,
        y2=0,
        where=None,
        interpolate: bool = False,
        step=None,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        offset: float = 0.0,
        baseline: Optional[str] = None,
        **kwargs,
    ):
        """Fill between two curves, or from one curve down to an axis.

        Two arrays emit GLE's ``fill dA,dB``. A scalar ``y2`` (the default
        ``0``) is broadcast to a constant second curve, so a curve that
        crosses the constant still fills on both sides of it. ``baseline``
        is the axis form instead: ``"x1"`` emits ``fill x1,dN`` (the curve
        to the bottom of the y axis) and ``"x2"`` emits ``fill dN,x2`` (to
        the top). That edge is the axis limit, not y=0.

        ``where`` selects x intervals. Each contiguous run of True samples
        that has area becomes its own fill, clipped with ``xmin`` / ``xmax``.
        A run is the samples matplotlib fills between: both ends True, so
        one isolated True draws nothing. ``interpolate=True`` moves a clip
        edge to where the two curves cross beside that run. GLE's clip is a
        rectangle, so an ``x`` that turns around or repeats a value cannot
        be expressed that way and the mask is ignored, with a warning.
        ``step`` is accepted and
        ignored: ``fill`` has no step mode.

        ``xmin``, ``xmax``, ``ymin`` and ``ymax`` keywords are that same
        clip in data coordinates, not axes fractions. On an ``x1`` fill,
        ``ymin`` is also the line the region closes on. Passing ``where``
        together with ``xmin`` or ``xmax`` raises ``ValueError``.

        ``alpha`` below 1 composes an ``rgba255(...)`` colour. Rendering it
        needs GLE's Cairo device, which the compile pipeline enables.

        Returns this axes. A mask that fills nothing adds no series.
        """

        def warn(message: str) -> None:
            warn_external(message)

        color, clip, data_name = self._fill_keywords(
            "fill_between", color, step, kwargs
        )

        if baseline is not None:
            baseline = str(baseline).strip().lower()
            if baseline not in ("x1", "x2"):
                raise ValueError("baseline must be 'x1' or 'x2', got " f"{baseline!r}")
            if not _is_scalar_zero(y2):
                raise ValueError(
                    "baseline= fills to an axis and replaces y2. "
                    "Pass the curve as y1, or omit baseline to fill between "
                    "two curves."
                )
        if where is not None and ("xmin" in clip or "xmax" in clip):
            raise ValueError(
                "fill_between() takes where= or an xmin/xmax clip, not both"
            )

        label = self._text(label)
        x_arr = np.asarray(x, dtype=float)
        if x_arr.ndim != 1:
            raise ValueError("fill_between() x must be 1-dimensional")
        if x_arr.size == 0:
            raise ValueError("fill_between() needs at least one x value")
        n = int(x_arr.size)
        y1_arr = _as_curve("y1", y1, n)
        y2_arr = None if baseline else _as_curve("y2", y2, n)
        if baseline and interpolate:
            warn(
                "fill_between(interpolate=True) looks for a crossing of the "
                "two curves. An axis fill has no second curve, so the clip "
                "stays on the samples."
            )
            interpolate = False

        if color is None:
            gle_color = "LIGHTBLUE"
        else:
            # alpha= overrides an RGBA colour's own alpha, as in matplotlib.
            gle_color = rgb_to_gle(color if alpha == 1.0 else _rgba_parts(color)[0])

        if where is None:
            windows: List[dict] = [dict(clip)]
        else:
            found = _where_windows(x_arr, y1_arr, y2_arr, where, bool(interpolate))
            if found is None:
                warn(
                    "fill_between(where=) needs a finite, strictly monotonic x "
                    "to become a GLE clip window; the mask was ignored."
                )
                windows = [dict(clip)]
            else:
                windows = []
                for window in found:
                    merged = dict(clip)
                    merged.update(window)
                    windows.append(merged)
        if not windows:
            return self

        single = baseline is not None
        band_names = ["x", "y"] if single else ["x", "upper", "lower"]
        for index, window in enumerate(windows):
            fields = dict(
                x=x_arr,
                y1=y1_arr,
                color=gle_color,
                alpha=float(alpha),
                label=label if index == 0 else None,
                offset=float(offset),
                data_file=_resolve_data_file(self.figure, data_name),
                column_names=_unique_column_names(band_names),
            )
            if single:
                fields["target"] = baseline
                fields["y2"] = None
            else:
                fields["y2"] = y2_arr
            fields.update(window)
            fill_data = FillSeries(**fields)
            # Call order, so a legend can list this band where it was added.
            # Fills are not z-ordered drawables; the field is legend order only.
            self._register_series_draw_meta(fill_data, "fill")
            self.fills.append(fill_data)
        return self

    @staticmethod
    def _fill_keywords(name: str, color, step, kwargs: dict):
        """``(color, clip, data_name)`` from a band call's keywords.

        Shared by :meth:`fill_between` and :meth:`fill_betweenx`. Consumes
        ``kwargs``; what is left after the known keywords warns.
        """
        data_name = kwargs.pop("data_name", None)
        if "data" in kwargs:
            kwargs.pop("data")
            warn_external(
                f"{name}(data=...) is not supported and was ignored. "
                "Pass the arrays directly."
            )
        facecolor = kwargs.pop("facecolor", None)
        if facecolor is None:
            facecolor = kwargs.pop("fc", None)
        if color is None and facecolor is not None:
            color = facecolor
        elif facecolor is not None:
            warn_external(f"{name}() got both color and facecolor; color wins.")
        clip = {}
        for key in ("xmin", "xmax", "ymin", "ymax"):
            if key in kwargs and kwargs[key] is not None:
                clip[key] = float(kwargs.pop(key))
            else:
                kwargs.pop(key, None)
        if step is not None:
            warn_external(
                f"{name}(step=) is not a GLE fill mode; the band is "
                "drawn through the samples."
            )
        warn_unsupported_keywords(name, kwargs)
        return color, clip, data_name

    @_cartesian_only
    def fill_betweenx(
        self,
        y,
        x1,
        x2=0,
        where=None,
        step=None,
        interpolate: bool = False,
        *,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Fill between two curves ``x1(y)`` and ``x2(y)``.

        The horizontal form of :meth:`fill_between`. GLE's two-curve fill is
        vertical, so the band is the closed polygon ``fill dN`` that
        :meth:`fill` draws: ``(x1, y)`` forward, then ``(x2, y)`` back. A
        scalar ``x2`` (the default ``0``) is a constant curve. Curves that
        cross fill on both sides of the crossing, as in matplotlib.

        ``where`` selects y intervals, as it selects x intervals on
        :meth:`fill_between`: each contiguous run of True samples becomes
        its own polygon, clipped with ``ymin`` / ``ymax``. ``interpolate=True``
        moves a clip edge to where the two curves cross beside that run.
        ``y`` has to be finite and strictly monotonic for the mask; otherwise
        it is ignored, with a warning. ``step`` is accepted and ignored.

        ``xmin``, ``xmax``, ``ymin`` and ``ymax`` keywords clip the polygon in
        data coordinates. Passing ``where`` together with ``ymin`` or ``ymax``
        raises ``ValueError``. ``alpha`` below 1 composes an ``rgba255(...)``
        colour, as on :meth:`fill_between`.

        The model holds the polygon, so a figure read back with
        :func:`gleplot.open_gle` has a :meth:`fill` series in its place.

        Returns this axes. A mask that fills nothing adds no series.
        """
        color, clip, data_name = self._fill_keywords(
            "fill_betweenx", color, step, kwargs
        )
        if where is not None and ("ymin" in clip or "ymax" in clip):
            raise ValueError(
                "fill_betweenx() takes where= or a ymin/ymax clip, not both"
            )

        y_arr = np.asarray(y, dtype=float)
        if y_arr.ndim != 1:
            raise ValueError("fill_betweenx() y must be 1-dimensional")
        if y_arr.size == 0:
            raise ValueError("fill_betweenx() needs at least one y value")
        n = int(y_arr.size)
        x1_arr = _as_curve("x1", x1, n)
        x2_arr = _as_curve("x2", x2, n)

        if where is None:
            windows: List[dict] = [dict(clip)]
        else:
            size = np.asarray(where).size
            if size != n:
                raise ValueError(
                    f"fill_betweenx() where has length {size}, expected {n} "
                    "to match y"
                )
            found = _where_windows(y_arr, x1_arr, x2_arr, where, bool(interpolate))
            if found is None:
                warn_external(
                    "fill_betweenx(where=) needs a finite, strictly monotonic y "
                    "to become a GLE clip window; the mask was ignored."
                )
                windows = [dict(clip)]
            else:
                windows = []
                for window in found:
                    merged = dict(clip)
                    for key, value in window.items():
                        merged["y" + key[1:]] = value
                    windows.append(merged)

        vertex_x = np.concatenate([x1_arr, x2_arr[::-1]])
        vertex_y = np.concatenate([y_arr, y_arr[::-1]])
        for index, window in enumerate(windows):
            self.fill(
                vertex_x,
                vertex_y,
                color=color,
                alpha=alpha,
                label=label if index == 0 else None,
                data_name=data_name,
                **window,
            )
        return self

    @_cartesian_only
    def stackplot(
        self,
        x,
        *args,
        labels=(),
        colors=None,
        baseline: str = "zero",
        **kwargs,
    ) -> List[FillSeries]:
        """Stack the curves in ``args`` as filled bands over ``x``.

        Each layer is a :meth:`fill_between` band from the running sum below
        it to the running sum including it, so the remaining keywords
        (``alpha``, ``where``, ...) are passed to every band. An argument may
        be a 2-D array, one row per layer.

        Parameters
        ----------
        x : array-like
            The shared x values.
        *args : array-like
            The layers, bottom first.
        labels : sequence of str
            One legend label per layer. Layers past the end have none.
        colors : sequence of colors, optional
            Cycled over the layers. Default: matplotlib's ``'C0'`` to
            ``'C9'``, starting at ``'C0'`` on every call.
        baseline : {'zero', 'sym', 'wiggle', 'weighted_wiggle'}
            The lower edge of the stack, computed as matplotlib does.

        Returns
        -------
        list of FillSeries
            The bands added, bottom first.

        Raises
        ------
        ValueError
            If ``baseline`` is not an accepted value, no layer is given, or
            ``colors`` is empty.

        Notes
        -----
        ``hatch`` is accepted and ignored, with a warning: a graph ``fill``
        has no pattern. The bands read back from a ``.gle`` file as separate
        :meth:`fill_between` series.
        """
        if "data" in kwargs:
            kwargs.pop("data")
            warn_external(
                "stackplot(data=...) is not supported and was ignored. "
                "Pass the arrays directly."
            )
        if "hatch" in kwargs:
            kwargs.pop("hatch")
            warn_external("stackplot(hatch=) is ignored. A graph fill has no pattern.")
        accepted = ("zero", "sym", "wiggle", "weighted_wiggle")
        if baseline not in accepted:
            raise ValueError(
                f"stackplot() baseline must be one of {accepted!r}, "
                f"got {baseline!r}"
            )
        if not args:
            raise ValueError("stackplot() needs at least one layer after x")
        y = np.vstack(args)

        # matplotlib's baselines (lib/matplotlib/stackplot.py), dtypes
        # included: integer layers give 'weighted_wiggle' an integer
        # ``inv_total`` there too, and the same curves here.
        stack = np.cumsum(y, axis=0, dtype=np.promote_types(y.dtype, np.float32))
        first_line: Any = 0.0
        if baseline == "sym":
            first_line = -np.sum(y, 0) * 0.5
            stack += first_line[None, :]
        elif baseline == "wiggle":
            m = y.shape[0]
            first_line = (y * (m - 0.5 - np.arange(m)[:, None])).sum(0)
            first_line /= -m
            stack += first_line
        elif baseline == "weighted_wiggle":
            total = np.sum(y, 0)
            inv_total = np.zeros_like(total)
            mask = total > 0
            inv_total[mask] = 1.0 / total[mask]
            increase = np.hstack((y[:, 0:1], np.diff(y)))
            below_size = total - stack
            below_size += 0.5 * y
            move_up = below_size * inv_total
            move_up[:, 0] = 0.5
            center = (move_up - 0.5) * increase
            center = np.cumsum(center.sum(0))
            first_line = center - 0.5 * total
            stack += first_line

        # As in matplotlib, a facecolor keyword replaces ``colors``. ``color``
        # is an alias here, and wins over facecolor as on fill_between.
        face = kwargs.pop("facecolor", None)
        if face is None:
            face = kwargs.pop("fc", None)
        if "color" in kwargs:
            if face is not None:
                warn_external("stackplot() got both color and facecolor; color wins.")
            face = kwargs.pop("color")
        if face is not None:
            colors = face
        colors = _color_list("stackplot", colors, [f"C{i}" for i in range(10)])
        if y.ndim != 2 or y.shape[1] != np.size(x):
            raise ValueError(
                f"stackplot() each layer must have one value per x ({np.size(x)}), "
                f"got layers of shape {y.shape}"
            )
        unknown = set(kwargs) - _STACKPLOT_BAND_KEYWORDS
        warn_unsupported_keywords("stackplot", unknown)
        for name in unknown:
            kwargs.pop(name)
        label_iter = iter(labels)
        lower = [first_line] + [stack[i, :] for i in range(len(y) - 1)]
        added: List[FillSeries] = []
        for i, bottom in enumerate(lower):
            before = len(self.fills)
            self.fill_between(
                x,
                stack[i, :],
                bottom,
                color=colors[i % len(colors)],
                label=next(label_iter, None),
                **kwargs,
            )
            added.extend(cast(List[FillSeries], self.fills[before:]))
        return added

    @_cartesian_only
    def fill(
        self,
        x,
        y,
        *args,
        color: Optional[str] = None,
        alpha: float = 1.0,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Fill the polygon with vertices ``(x, y)``.

        Emits GLE's ``fill dN``, which closes the last vertex back to the
        first. This is not a general path: one polygon, no curves or holes.
        A third positional argument may be a color (``fill(x, y, "b")``).
        Further polygons in the same call are ignored, with a warning.

        ``alpha`` below 1 is an ``rgba255(...)`` colour, as on
        :meth:`fill_between`. ``xmin`` / ``xmax`` / ``ymin`` / ``ymax`` clip
        the polygon in data coordinates. GLE fills the interior and does not
        stroke an edge, so ``edgecolor`` and ``linewidth`` are ignored.
        """

        def warn(message: str) -> None:
            warn_external(message)

        data_name = kwargs.pop("data_name", None)
        if "data" in kwargs:
            kwargs.pop("data")
            warn(
                "fill(data=...) is not supported and was ignored. "
                "Pass the vertex arrays directly."
            )
        if args:
            positional = _positional_fill_color(args[0])
            if positional is not None:
                if color is None:
                    color = positional
                args = args[1:]
            if args:
                warn("fill() models one polygon; extra polygons were ignored.")
        facecolor = kwargs.pop("facecolor", None)
        if facecolor is None:
            facecolor = kwargs.pop("fc", None)
        if color is None and facecolor is not None:
            color = facecolor
        elif facecolor is not None:
            warn("fill() got both color and facecolor; color wins.")
        for dropped in ("edgecolor", "linewidth", "linestyle"):
            if dropped in kwargs:
                kwargs.pop(dropped)
                warn(
                    f"fill({dropped}=) is ignored. GLE's polygon fill does "
                    "not stroke an edge."
                )
        clip = {}
        for key in ("xmin", "xmax", "ymin", "ymax"):
            if key in kwargs and kwargs[key] is not None:
                clip[key] = float(kwargs.pop(key))
            else:
                kwargs.pop(key, None)
        warn_unsupported_keywords("fill", kwargs)

        label = self._text(label)
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        if x_arr.ndim != 1 or y_arr.ndim != 1:
            raise ValueError("fill() x and y must be 1-dimensional")
        if x_arr.size == 0:
            raise ValueError("fill() needs at least one vertex")
        if y_arr.size != x_arr.size:
            raise ValueError(f"fill() y has length {y_arr.size}, expected {x_arr.size}")
        if color is None:
            gle_color = "LIGHTBLUE"
        else:
            # alpha= overrides an RGBA colour's own alpha, as in matplotlib.
            gle_color = rgb_to_gle(color if alpha == 1.0 else _rgba_parts(color)[0])
        fill_data = FillSeries(
            x=x_arr,
            y1=y_arr,
            y2=None,
            color=gle_color,
            alpha=float(alpha),
            label=label,
            offset=0.0,
            target="polygon",
            data_file=_resolve_data_file(self.figure, data_name),
            column_names=_unique_column_names(["x", "y"]),
            **clip,
        )
        self._register_series_draw_meta(fill_data, "fill")
        self.fills.append(fill_data)
        return self

    # -- data-bounded segments (hlines / vlines) ---------------------------

    @_cartesian_only
    def hlines(
        self,
        y,
        xmin,
        xmax,
        colors=None,
        linestyles="solid",
        *,
        label="",
        **kwargs,
    ):
        """Draw horizontal segments at each ``y`` from ``xmin`` to ``xmax``.

        Unlike :meth:`axhline`, the ends are data coordinates. See
        :meth:`vlines`, which this mirrors, for how the segments are drawn.
        """
        return self._add_segments(
            "hlines", "h", y, xmin, xmax, colors, linestyles, label, kwargs
        )

    @_cartesian_only
    def vlines(
        self,
        x,
        ymin,
        ymax,
        colors=None,
        linestyles="solid",
        *,
        label="",
        **kwargs,
    ):
        """Draw vertical segments at each ``x`` from ``ymin`` to ``ymax``.

        Unlike :meth:`axvline`, the ends are data coordinates.

        Parameters
        ----------
        x : float or array-like
            Where the segments are.
        ymin, ymax : float or array-like
            Their ends. A scalar applies to every segment.
        colors : color or sequence of colors, optional
            Cycled over the segments. Default: matplotlib's ``'C0'``. Alias
            ``color``.
        linestyles : str or sequence of str
            ``'solid'``, ``'dashed'``, ``'dotted'``, ``'dashdot'``, their
            symbols ``'-'``, ``'--'``, ``':'``, ``'-.'``, or ``'none'`` (the
            segment is not drawn), cycled over the segments. Alias
            ``linestyle`` / ``ls``.
        label : str
            Legend label for the whole set. Empty means no legend entry.
        **kwargs
            ``linewidths`` (alias ``linewidth``, ``lw``), in points, a
            number or one per segment, and ``zorder``. Others warn.

        Returns
        -------
        Axes
            This axes. matplotlib returns a ``LineCollection``.

        Raises
        ------
        ValueError
            If the ends do not match the positions in length, or a line
            style is not one of the above.

        Notes
        -----
        The segments are one line dataset per distinct style, with a missing
        value (``*``) between segments so GLE does not join them. The legend
        entry is on the first of those datasets. A segment with a NaN end is
        not drawn. A dash pattern given as a tuple warns and is drawn solid.
        A figure read back with :func:`gleplot.open_gle` has a :meth:`plot`
        line with NaN gaps in its place.
        """
        return self._add_segments(
            "vlines", "v", x, ymin, ymax, colors, linestyles, label, kwargs
        )

    def _add_segments(
        self, name, orient, pos, lo, hi, colors, linestyles, label, kwargs
    ):
        """Shared implementation of :meth:`hlines` / :meth:`vlines`."""
        if "data" in kwargs:
            kwargs.pop("data")
            warn_external(
                f"{name}(data=...) is not supported and was ignored. "
                "Pass the arrays directly."
            )
        # matplotlib's LineCollection aliases. The plural name wins, as the
        # first of fill_between's color/facecolor pair does there.
        if "color" in kwargs:
            alias = kwargs.pop("color")
            if colors is None:
                colors = alias
            else:
                warn_external(f"{name}() got both colors and color; colors wins.")
        for key in ("linestyle", "ls"):
            if key in kwargs:
                alias = kwargs.pop(key)
                if linestyles == "solid":
                    linestyles = alias
                else:
                    warn_external(
                        f"{name}() got both linestyles and {key}; linestyles wins."
                    )
        given = [k for k in ("linewidths", "linewidth", "lw") if k in kwargs]
        widths: Any = kwargs.pop(given[0]) if given else None
        for key in given[1:]:
            kwargs.pop(key)
            warn_external(f"{name}() got both {given[0]} and {key}; {given[0]} wins.")
        zorder = kwargs.pop("zorder", None)
        warn_unsupported_keywords(name, kwargs)

        lo_name, hi_name = ("xmin", "xmax") if orient == "h" else ("ymin", "ymax")
        pos_arr = np.ravel(np.asarray(pos, dtype=float))
        n = int(pos_arr.size)
        ends = []
        for arg_name, value in ((lo_name, lo), (hi_name, hi)):
            arr = np.ravel(np.asarray(value, dtype=float))
            if arr.size == 1:
                arr = np.full(n, arr[0])
            if arr.size != n:
                raise ValueError(
                    f"{name}() {arg_name} has length {arr.size}, expected 1 or "
                    f"{n} to match the positions"
                )
            ends.append(arr)

        one_style = isinstance(linestyles, str) or _is_dash_pattern(linestyles)
        styles = [
            _segment_linestyle(name, s)
            for s in ([linestyles] if one_style else linestyles)
        ]
        palette = [rgb_to_gle(c) for c in _color_list(name, colors, ["C0"])]
        try:
            if widths is None:
                width_list: List[Optional[float]] = [None]
            elif np.ndim(widths) == 0:
                width_list = [float(widths)]
            else:
                width_list = [float(w) for w in widths]
        except (TypeError, ValueError):
            raise ValueError(
                f"{name}() linewidths must be a number of points or one per "
                f"segment, got {widths!r}"
            ) from None
        if not styles or not width_list:
            raise ValueError(
                f"{name}() linestyles and linewidths must not be empty, got "
                f"{linestyles!r} and {widths!r}"
            )

        # One dataset per distinct style, in first-use order.
        groups: Dict[tuple, List[int]] = {}
        for i in range(n):
            if not (
                np.isfinite(pos_arr[i])
                and np.isfinite(ends[0][i])
                and np.isfinite(ends[1][i])
            ):
                continue
            key = (
                palette[i % len(palette)],
                styles[i % len(styles)],
                width_list[i % len(width_list)],
            )
            if key[1] == "none":
                continue
            groups.setdefault(key, []).append(i)

        text = label if label else None
        for (color, style, width), members in groups.items():
            along: List[float] = []
            across: List[float] = []
            for k, i in enumerate(members):
                if k:
                    along.append(np.nan)
                    across.append(np.nan)
                along.extend([ends[0][i], ends[1][i]])
                across.extend([pos_arr[i], pos_arr[i]])
            x, y = (along, across) if orient == "h" else (across, along)
            self.plot(
                np.array(x),
                np.array(y),
                linestyle=style,
                color=color,
                linewidth=width,
                label=text,
                zorder=zorder,
            )
            series = self.lines[-1]
            # The NaN rows are gaps, written as GLE missing values. A lone
            # segment has none, so it stays a plain two-point line. A
            # figure-wide smooth would fit a curve through the segments.
            if len(members) > 1:
                series["gaps"] = True
            series["smooth_mode"] = "none"
            text = None
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
    #    ``Figure._write_fills`` and ``Figure._write_reflines`` after the axis
    #    limits are resolved). So a later ``set_ylim`` -- or autoscaling from
    #    data added after the axvline call -- is respected, exactly as in
    #    matplotlib. The generated ``.dat`` sidecar name, by contrast, is
    #    reserved at CALL time so it is stable across repeated saves of the
    #    same figure.
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

    @_cartesian_only
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
            ``'-'``, ``'--'``, ``':'`` or ``'-.'``, or matplotlib's name for
            one (``'dashed'``, ...). A dash tuple or any other value warns
            and is drawn solid.
        linewidth : float
            Line width in points.
        label : str, optional
            Legend label.
        **kwargs
            ``lw``, ``ls`` and ``c`` are matplotlib's short names for
            ``linewidth``, ``linestyle`` and ``color``; the full name wins,
            with a warning, unless it is left at its default. Any other
            keyword (``alpha``, ``zorder``, ``transform``, ...) warns and is
            ignored.

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

    @_cartesian_only
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
        caller = "axvline" if orient == "v" else "axhline"
        names = "ymin/ymax" if orient == "v" else "xmin/xmax"
        lo, hi = self._check_axes_fraction(lo, hi, names)
        data_name = kwargs.pop("data_name", None)
        linestyle = _pop_line_alias(kwargs, caller, "ls", "linestyle", linestyle, "-")
        linestyle = _line_style(caller, linestyle)
        linewidth = _pop_line_alias(kwargs, caller, "lw", "linewidth", linewidth, 1)
        color = _pop_line_alias(kwargs, caller, "c", "color", color, None)
        warn_unsupported_keywords(caller, kwargs)
        label = self._text(label)
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
        self._register_series_draw_meta(entry, "refline")
        self.reflines.append(entry)
        return entry

    @_cartesian_only
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
        **kwargs
            ``facecolor`` (``fc``) is accepted for ``color``; ``color``
            wins, with a warning, when both are given. Any other keyword
            (``edgecolor``, ``hatch``, ``zorder``, ...) warns and is ignored.

        Returns
        -------
        dict
            The stored declaration (also appended to ``self.spans``).
        """
        return self._add_span("v", xmin, xmax, ymin, ymax, color, alpha, label, kwargs)

    @_cartesian_only
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
        caller = "axvspan" if orient == "v" else "axhspan"
        names = "ymin/ymax" if orient == "v" else "xmin/xmax"
        lo, hi = self._check_axes_fraction(lo, hi, names)
        data_name = kwargs.pop("data_name", None)
        face = _pop_line_alias(
            kwargs, caller, "fc", "facecolor", kwargs.pop("facecolor", None), None
        )
        if face is not None and color is not None:
            warn_external(f"{caller}() got both color and facecolor; color wins.")
        elif face is not None:
            color = face
        warn_unsupported_keywords(caller, kwargs)
        label = self._text(label)
        if alpha != 1.0:
            # alpha= overrides an RGBA colour's own alpha, as in matplotlib.
            color = _rgba_parts(color)[0]
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
        self._register_series_draw_meta(entry, "span")
        self.spans.append(entry)
        return entry

    @staticmethod
    def _fraction_to_data(lo: float, hi: float, vmin: float, vmax: float):
        """Map an axes-fraction pair onto the data range ``[vmin, vmax]``."""
        span = vmax - vmin
        return vmin + lo * span, vmin + hi * span

    @staticmethod
    def guide_spanned_bounds(entry, limits):
        """The ``(lo, hi)`` bounds of the axis ``entry`` spans, from ``limits``.

        A ``'v'`` guide (``axvline``/``axvspan``) is positioned in x and spans
        y; a ``'h'`` guide is the transpose.
        """
        xmin, xmax, ymin, ymax = limits
        return (ymin, ymax) if entry["orient"] == "v" else (xmin, xmax)

    @classmethod
    def guide_needs_engine_range(cls, entry, limits) -> bool:
        """Whether this guide has to be drawn against GLE's own range (G17).

        True exactly when a bound of the axis the guide spans is ``None`` at
        write time -- an axes with nothing to resolve that axis from (G14), or
        a range that collapsed and was handed back to the engine (G15). Such a
        guide cannot be materialized into a literal dataset without inventing
        the very range GLE has yet to choose, so it is emitted as a layered
        ``draw`` over ``xgmin``/``ygmax`` instead (:mod:`gleplot.guides`).

        False -- the overwhelmingly common case -- keeps the historical
        two-point dataset emission untouched, byte for byte.
        """
        lo, hi = cls.guide_spanned_bounds(entry, limits)
        return lo is None or hi is None

    def engine_range_guides(self, series_list, limits) -> List[Series]:
        """The visible guides in ``series_list`` routed to the draw form."""
        return [
            entry
            for entry in series_list
            if is_visible(entry) and self.guide_needs_engine_range(entry, limits)
        ]

    def dataset_form_guides(self, series_list, limits) -> List[Series]:
        """The visible guides in ``series_list`` that materialize into datasets.

        The exact complement of :meth:`engine_range_guides` among the visible
        entries -- both filter on the same two predicates -- and therefore
        positionally aligned, by construction, with what
        :meth:`materialize_reflines` / :meth:`materialize_spans` return for
        the same ``limits``. That alignment is what lets the writer put each
        materialized dataset's provenance marker (G18-lite) back beside the
        declaration it came from; ``Figure._write_fills`` and
        ``Figure._write_reflines`` check the two lists are the same length
        rather than trusting it silently.
        """
        return [
            entry
            for entry in series_list
            if is_visible(entry) and not self.guide_needs_engine_range(entry, limits)
        ]

    def materialize_reflines(self, limits) -> List[LineSeries]:
        """Turn ``self.reflines`` into concrete two-point line series.

        Parameters
        ----------
        limits : tuple
            ``(xmin, xmax, ymin, ymax)`` -- the axis limits actually being
            written.

        Returns
        -------
        list of dict
            Line dicts in the same shape ``plot()`` produces, ready for
            ``GLEWriter.add_line``. Nothing is stored back on the axes,
            so writing a figure twice does not duplicate content.

        Two kinds of guide materialize into nothing here: hidden ones
        (``visible = False``, SPEC 14.6), and -- since G17 -- ones whose
        spanned axis has an unresolved bound. The latter are the figures the
        literal dataset got wrong; they are emitted as ``draw`` calls instead
        (see :meth:`guide_needs_engine_range` and :mod:`gleplot.guides`), and
        :meth:`engine_range_guides` is how the writer collects them.
        """
        xmin, xmax, ymin, ymax = limits
        out: List[LineSeries] = []
        for entry in self.reflines:
            if not is_visible(entry):
                continue
            if self.guide_needs_engine_range(entry, limits):
                continue
            if entry["orient"] == "v":
                y0, y1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], *self._spanned_range(ymin, ymax)
                )
                x = np.array([entry["value"], entry["value"]], dtype=float)
                y = np.array([y0, y1], dtype=float)
            else:
                x0, x1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], *self._spanned_range(xmin, xmax)
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
        is stored back; hidden bands, and bands across an axis with an
        unresolved bound, materialize into nothing).
        """
        xmin, xmax, ymin, ymax = limits
        out: List[FillSeries] = []
        for entry in self.spans:
            if not is_visible(entry):
                continue
            if self.guide_needs_engine_range(entry, limits):
                continue
            if entry["orient"] == "v":
                y0, y1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], *self._spanned_range(ymin, ymax)
                )
                x = np.array([entry["start"], entry["end"]], dtype=float)
                upper = np.array([y1, y1], dtype=float)
                lower = np.array([y0, y0], dtype=float)
            else:
                x0, x1 = self._fraction_to_data(
                    entry["span_lo"], entry["span_hi"], *self._spanned_range(xmin, xmax)
                )
                x = np.array([x0, x1], dtype=float)
                upper = np.array([entry["end"], entry["end"]], dtype=float)
                lower = np.array([entry["start"], entry["start"]], dtype=float)

            fill = FillSeries(
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
            if entry.get("swatch_color"):
                fill["swatch_color"] = entry["swatch_color"]
            out.append(fill)
        return out

    @staticmethod
    def _spanned_range(lo: Optional[float], hi: Optional[float]):
        """The range a guide spans, with GLE's default standing in for gaps.

        **Since G17 this is a safety net, not the live path.** A guide whose
        spanned axis has an unresolved bound no longer reaches
        :meth:`materialize_reflines`/:meth:`materialize_spans` at all -- it is
        emitted as a ``draw`` that reads GLE's own ``xgmin``/``ygmax``
        (:mod:`gleplot.guides`). This substitution now only applies to a
        direct call with a ``None`` bound.

        What it used to do, and why that was not good enough
        ---------------------------------------------------

        An axes with no data and no explicit limit resolves to ``None`` --
        gleplot then emits no ``min``/``max`` for that axis and GLE draws its
        own default 0..1 frame, so materializing over
        :data:`EMPTY_AXIS_FALLBACK_RANGE` put the guide across the frame that
        got rendered instead of dropping it (G14, GLEstudio SPEC 14.3).
        Substitution is per bound, so a half-specified range
        (``set_ylim(0, None)`` on an empty axes) keeps the bound it has.

        Since G15 a bound can also be ``None`` because the range it resolved
        to *collapsed to a single value* and was handed back to GLE
        (:meth:`Figure._defer_degenerate_range`). There the fallback stood in
        for a frame GLE had not chosen yet, and the guide came out wrong in
        **two** ways, not one. It was measured against 0..1 rather than
        against the rendered frame -- and, because the materialized dataset is
        a real dataset, its ``0`` and ``1`` rows then *joined GLE's autoscale
        and moved the frame itself*. Measured on GLE 4.3.10 for
        ``plot([5], [7])`` + ``axvline(5, ymin=0, ymax=1)``: the engine chose
        ``ygmin=0 ygmax=7`` (instead of the ``0..12`` it picks for the lone
        point alone) and the guide, declaring the full frame height, covered
        14.3 % of it. The circularity is exactly the one
        :meth:`Figure._refline_axis_values` avoids on gleplot's side of the
        line, reintroduced inside the engine where gleplot cannot see it.
        """
        fallback_lo, fallback_hi = EMPTY_AXIS_FALLBACK_RANGE
        return (
            fallback_lo if lo is None else lo,
            fallback_hi if hi is None else hi,
        )

    @_cartesian_only
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
        rotation: Optional[float] = None,
        **kwargs,
    ):
        """Add free-form text annotation in data coordinates or axes fractions.

        Parameters
        ----------
        x, y : float
            Data coordinates, or axes fractions with
            ``transform=ax.transAxes``.
        s : str
            Text to render.
        color : str, optional
            Text color.
        fontsize : float or str, optional
            Font size in points, or a matplotlib size name (``'small'``,
            ``'large'``, ...) relative to the figure's font size.
        ha : {'left', 'center', 'right'}, optional
            Horizontal alignment. The alignment point is ``(x, y)``.
        va : {'top', 'center', 'bottom'}, optional
            Vertical alignment. GLE's ``set just`` has those three positions
            and no separate baseline; anything else warns and uses
            ``'center'``.
        bbox : dict, optional
            Filled background behind the text. The supported key is
            ``facecolor`` (``fill`` is accepted as an alias). The box is GLE's
            ``begin box fill`` with a fixed 0.05 cm pad and no outline.
            Other keys (``edgecolor``, ``linewidth``, ``pad``, ``boxstyle``,
            ...) warn and are ignored.
        rotation : float, optional
            Counter-clockwise rotation in degrees about the alignment point
            (GLE ``begin rotate``). ``0`` omits the block.
        transform : optional
            ``ax.transAxes`` reads ``x`` and ``y`` as fractions of this axes'
            frame: ``(0, 0)`` is its bottom-left corner and ``(1, 1)`` its
            top-right, whatever the limits, scale or direction of the axes.
            ``ax.transData`` (or leaving it out) means data coordinates. Any
            other transform warns and the position is read as data
            coordinates.
        **kwargs
            Any other matplotlib text keyword warns and is ignored. This is
            not a general page-drawing API.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, ax = glp.subplots()
        >>> _ = ax.text(0.05, 0.95, "(b)", transform=ax.transAxes, va="top")
        """
        transform = self._text_transform(kwargs.pop("transform", None))
        fields = _text_fields(
            self._style(),
            "text",
            x,
            y,
            s,
            color=color,
            fontsize=fontsize,
            ha=ha,
            va=va,
            bbox=bbox,
            rotation=rotation,
            kwargs=kwargs,
            supported="color, fontsize, ha, va, rotation, bbox, transform",
        )
        if transform is not None:
            fields["transform"] = transform
        self.texts.append(TextAnnotation(**fields))
        return self

    def _text_transform(self, transform) -> Optional[str]:
        """The ``TextAnnotation.transform`` for ``text(transform=...)``.

        None is data coordinates, the absent field.
        """
        if transform is None:
            return None
        if isinstance(transform, _Transform) and transform.axes is self:
            return None if transform.kind == "data" else transform.kind
        if isinstance(transform, _Transform):
            reason = "it belongs to a different axes"
        else:
            reason = "only this axes' transAxes and transData are supported"
        warn_external(
            f"text(transform={transform!r}) was ignored: {reason}. The "
            "position was read as data coordinates. Call text() on the axes "
            "the transform belongs to, with transform=ax.transAxes for axes "
            "fractions.",
        )
        return None

    @property
    def transAxes(self) -> _Transform:
        """Axes fractions, for ``text(transform=ax.transAxes)``.

        ``(0, 0)`` is the bottom-left corner of the frame and ``(1, 1)`` the
        top-right, as in matplotlib.
        """
        return _Transform(self, "axes")

    @property
    def transData(self) -> _Transform:
        """Data coordinates, for ``text(transform=ax.transData)``: the default."""
        return _Transform(self, "data")

    @_cartesian_only
    def annotate(
        self,
        text: str,
        xy: Sequence[float],
        xytext: Optional[Sequence[float]] = None,
        xycoords: str = "data",
        textcoords: Optional[str] = None,
        arrowprops: Optional[dict] = None,
        annotation_clip: Optional[bool] = None,
        **kwargs,
    ) -> TextAnnotation:
        """Annotate the point ``xy`` with ``text``, optionally with an arrow.

        Parameters
        ----------
        text : str
            The label.
        xy : (float, float)
            The annotated point, in data coordinates. The arrow tip.
        xytext : (float, float), optional
            Where the text goes, in data coordinates. Default: ``xy`` (and
            then no arrow is drawn, as in matplotlib, where it has no length).
        xycoords, textcoords : str
            Only ``'data'`` is supported. Any other system warns and the
            numbers are read as data coordinates.
        arrowprops : dict, optional
            Draw an arrow from the text to ``xy``. GLE ``join`` starts it at
            the edge of the text box (0.05 cm pad) and ends it on ``xy``. A
            ``xy`` inside the text's own box draws the arrow back across
            the text (matplotlib draws nothing); move ``xytext`` clear.
            Supported keys:

            * ``arrowstyle``: ``'-'``, ``'->'``, ``'<-'``, ``'<->'`` (open
              heads, GLE ``simple``) and ``'-|>'``, ``'<|-'``, ``'<|-|>'``
              (triangle heads, GLE ``filled``). ``'fancy'``, ``'simple'``,
              ``'wedge'`` warn and draw ``'-|>'``. Without ``arrowstyle``
              (matplotlib's legacy ``width``/``headwidth``/``shrink`` form)
              the arrow is ``'-|>'``.
            * ``color``, else ``edgecolor``/``ec``, else ``facecolor``/``fc``:
              the one arrow colour. Default black.
            * ``linewidth``/``lw``: points. Default: GLE's current ``lwidth``.

            Other keys (``connectionstyle`` other than straight ``arc3``,
            ``shrinkA``/``shrinkB``, ``linestyle``, ``alpha``, head-size
            parameters, ...) warn and are ignored.
        annotation_clip : bool, optional
            Not modelled: the annotation is always drawn. Warns if given.
        **kwargs
            Text keywords, as for :meth:`text`: ``color``, ``fontsize``,
            ``ha``, ``va``, ``rotation``, ``bbox``.

        Returns
        -------
        TextAnnotation
            The stored annotation (also appended to ``self.texts``).
        """
        for name, value in (("xycoords", xycoords), ("textcoords", textcoords)):
            if value is not None and value != "data":
                warn_external(
                    f"annotate({name}={value!r}) is not supported; the "
                    "coordinates are read as 'data'.",
                )
        if annotation_clip is not None:
            warn_external(
                "annotate(annotation_clip=...) is not supported and was "
                "ignored; the annotation is always drawn.",
            )

        x, y = (float(v) for v in xy)
        tx, ty = (x, y) if xytext is None else (float(v) for v in xytext)
        text_kwargs = {
            key: kwargs.pop(key, default)
            for key, default in (
                ("color", None),
                ("fontsize", None),
                ("ha", "left"),
                ("va", "center"),
                ("bbox", None),
                ("rotation", None),
            )
        }
        fields = _text_fields(
            self._style(),
            "annotate",
            tx,
            ty,
            text,
            kwargs=kwargs,
            supported=(
                "xytext, xycoords, textcoords, arrowprops, color, fontsize, "
                "ha, va, rotation, bbox"
            ),
            **text_kwargs,
        )
        if arrowprops is not None and not isinstance(arrowprops, dict):
            warn_external(
                f"annotate(arrowprops={arrowprops!r}) is not a dict; no arrow "
                "was drawn.",
            )
        elif arrowprops is not None and xytext is not None:
            fields.update(self._annotate_arrow(x, y, arrowprops))
        entry = TextAnnotation(**fields)
        self.texts.append(entry)
        return entry

    @staticmethod
    def _annotate_arrow(x: float, y: float, arrowprops: dict) -> Dict[str, Any]:
        """The arrow fields of an annotation from matplotlib ``arrowprops``."""
        props = dict(arrowprops)
        unsupported = []
        if "arrowstyle" in props:
            raw = props.pop("arrowstyle")
            # matplotlib's "->, head_width=0.4" form: the head-size
            # parameters have no counterpart here.
            name, _, params = str(raw).partition(",")
            name = name.strip()
            if params.strip():
                unsupported.append(f"arrowstyle parameters {params.strip()!r}")
            if name in MPL_ARROWSTYLE_TO_GLE:
                sep, tip = MPL_ARROWSTYLE_TO_GLE[name]
            else:
                warn_external(
                    f"annotate(arrowprops={{'arrowstyle': {raw!r}}}) has no GLE "
                    "equivalent; drawn as '-|>'.",
                )
                sep, tip = MPL_ARROWSTYLE_TO_GLE["-|>"]
        else:
            # The legacy YAArrow form is a filled arrow.
            sep, tip = MPL_ARROWSTYLE_TO_GLE["-|>"]

        color = None
        for key in ("color", "edgecolor", "ec", "facecolor", "fc"):
            value = props.pop(key, None)
            if color is None and value is not None:
                color = value

        linewidth = None
        for key in ("linewidth", "lw"):
            value = props.pop(key, None)
            if linewidth is None and value is not None:
                linewidth = float(value)

        connection = props.pop("connectionstyle", None)
        if connection is not None and not _is_straight_connection(connection):
            unsupported.append("connectionstyle (drawn straight)")

        unsupported.extend(sorted(props))
        if unsupported:
            warn_external(
                f"annotate(arrowprops=...) ignores {unsupported}. Supported "
                "keys: arrowstyle, color, edgecolor/ec, facecolor/fc, "
                "linewidth/lw.",
            )

        fields: Dict[str, Any] = dict(xy=[x, y], arrow=sep)
        if tip is not None:
            fields["arrowstyle"] = tip
        fields["arrow_color"] = "BLACK" if color is None else rgb_to_gle(color)
        if linewidth is not None:
            fields["arrow_linewidth"] = linewidth
        return fields

    @_cartesian_only
    def pie(
        self,
        x,
        explode=None,
        labels=None,
        colors=None,
        autopct=None,
        pctdistance: float = 0.6,
        shadow=False,
        labeldistance: Optional[float] = 1.1,
        startangle: float = 0,
        radius: float = 1,
        counterclock: bool = True,
        wedgeprops: Optional[dict] = None,
        textprops: Optional[dict] = None,
        center=(0, 0),
        frame: bool = False,
        rotatelabels: bool = False,
        *,
        normalize: bool = True,
        hatch=None,
    ):
        """Draw a pie chart: one wedge per value of ``x``.

        Parameters
        ----------
        x : 1-D array-like
            Wedge sizes, non-negative and finite.
        explode : array-like, optional
            Not supported: a non-zero offset warns and the wedge is drawn in
            place.
        labels : sequence of str, optional
            One label per wedge, drawn ``labeldistance`` radii from the
            centre. Labels are text beside the wedges, not legend entries.
        colors : sequence of colors, optional
            Cycled over the wedges. Default: matplotlib's ``'C0'`` to ``'C9'``.
        autopct : str or callable, optional
            Percentage text inside each wedge: a format string applied as
            ``autopct % pct`` or a function called as ``autopct(pct)``.
        pctdistance : float
            Radii from the centre of the ``autopct`` text.
        shadow : bool or dict
            Not supported: warns.
        labeldistance : float or None
            Radii from the centre of the labels. ``None`` draws no labels.
        startangle : float
            Degrees counter-clockwise from +x at which the first wedge starts.
        radius : float
            Pie radius in data units.
        counterclock : bool
            Direction in which the wedges follow each other.
        wedgeprops : dict, optional
            Not supported: warns. Wedges have no outline.
        textprops : dict, optional
            ``fontsize`` (alias ``size``) sets the label and percentage
            height, in points or as a matplotlib size name such as
            ``'large'``. Other keys warn.
        center : (float, float)
            Pie centre in data coordinates.
        frame : bool
            ``False`` (the default) hides the axes. ``True`` keeps them; the
            limits are still set as for ``False``.
        rotatelabels : bool
            Not supported: warns. Labels are horizontal.
        normalize : bool
            ``True`` scales ``x`` to a full circle. ``False`` draws each value
            as a fraction of the circle, and needs ``sum(x) <= 1``.
        hatch : str or sequence, optional
            Not supported: warns.

        Returns
        -------
        tuple
            ``(wedges, texts)``, or ``(wedges, texts, autotexts)`` when
            ``autopct`` is given. ``wedges`` are the stored
            :class:`~gleplot.series.Wedge` entries (also appended to
            ``self.wedges``); ``texts`` and ``autotexts`` are the strings
            drawn, one per wedge (``texts`` is empty when ``labeldistance``
            is ``None``).

        Notes
        -----
        Sets both limits to ``center`` +/- 1.25, as matplotlib does. The
        radius is measured on the axis with fewer centimetres per unit, so
        the pie stays circular in a cell that is not square, as with
        matplotlib's equal aspect. The wedges are drawn after the graph
        block, above the axes' other series.
        """
        sizes = np.asarray(x, dtype=float)
        if sizes.ndim != 1:
            raise ValueError(
                f"pie(x) must be 1-D; got an array of shape {sizes.shape}."
            )
        if np.any(sizes < 0):
            raise ValueError(f"pie(x) must be non-negative; got {x!r}.")
        if not np.all(np.isfinite(sizes)):
            raise ValueError(f"pie(x) must be finite; got {x!r}.")
        total = float(sizes.sum())
        if total == 0:
            raise ValueError(f"pie(x) has all sizes zero; got {x!r}.")
        if normalize:
            fracs = sizes / total
        elif total > 1:
            raise ValueError(
                f"pie(x, normalize=False) needs sum(x) <= 1; got sum {total}. "
                "Pass normalize=True to scale x to a full circle."
            )
        else:
            fracs = sizes
        n = len(sizes)
        label_list = [None] * n if labels is None else list(labels)
        if len(label_list) != n:
            raise ValueError(
                f"pie(labels=...) needs one label per wedge ({n}); "
                f"got {len(label_list)}."
            )
        if explode is not None:
            offsets = list(explode)
            if len(offsets) != n:
                raise ValueError(
                    f"pie(explode=...) needs one offset per wedge ({n}); "
                    f"got {len(offsets)}."
                )
            if any(float(v) != 0 for v in offsets):
                warn_external(
                    "pie(explode=...) is not supported; the wedges are drawn "
                    "unexploded. See the matplotlib migration guide."
                )
        if autopct is not None and not (isinstance(autopct, str) or callable(autopct)):
            raise TypeError(
                f"pie(autopct={autopct!r}) must be a format string such as "
                "'%1.1f%%' or a function taking the percentage."
            )
        if not isinstance(radius, Real):
            raise TypeError(f"pie(radius={radius!r}) must be a real number.")
        if radius <= 0:
            raise ValueError(f"pie(radius={radius!r}) must be positive.")
        if not isinstance(startangle, Real):
            raise TypeError(f"pie(startangle={startangle!r}) must be a real number.")

        for name, value in (
            ("shadow", shadow),
            ("rotatelabels", rotatelabels),
            ("wedgeprops", wedgeprops),
            ("hatch", hatch),
        ):
            if value:
                warn_external(
                    f"pie({name}=...) is not supported and was ignored. See "
                    "the matplotlib migration guide."
                )
        fontsize = None
        for key, value in (textprops or {}).items():
            if key in ("fontsize", "size"):
                fontsize = _resolve_fontsize(
                    self._style(), value, f"pie(textprops={key!r}"
                )
            else:
                warn_external(
                    f"pie(textprops={{{key!r}: ...}}) is not supported and was "
                    "ignored. Supported keys: fontsize, size."
                )

        if colors is None:
            palette = [f"C{i}" for i in range(10)]
        else:
            palette = list(colors)
            if not palette:
                raise ValueError(
                    "pie(colors=[]) needs at least one colour; pass None for "
                    "matplotlib's default cycle."
                )
        cx, cy = float(center[0]), float(center[1])
        wedges: List[Wedge] = []
        texts: List[str] = []
        autotexts: List[str] = []
        theta1 = float(startangle) / 360.0
        for i, (frac, label) in enumerate(zip(fracs, label_list)):
            theta2 = theta1 + frac if counterclock else theta1 - frac
            text = None
            if labeldistance is not None:
                shown = "" if label is None else str(label)
                texts.append(shown)
                text = self._text(shown) if shown else None
            autotext = None
            if autopct is not None:
                pct = 100.0 * float(frac)
                raw = autopct % pct if isinstance(autopct, str) else autopct(pct)
                raw = str(raw)
                if self._style().usetex:
                    # As matplotlib does: LaTeX reads a bare % as a comment.
                    raw = re.sub(r"(?<!\\)%", r"\\%", raw)
                autotext = self._text(raw)
                autotexts.append(raw)
            entry = Wedge(
                type="wedge",
                x=cx,
                y=cy,
                r=float(radius),
                theta1=360.0 * min(theta1, theta2),
                theta2=360.0 * max(theta1, theta2),
                color=rgb_to_gle(palette[i % len(palette)]),
                label=text,
                labeldistance=1.1 if labeldistance is None else float(labeldistance),
                autotext=autotext,
                pctdistance=float(pctdistance),
                fontsize=fontsize,
            )
            self.wedges.append(entry)
            wedges.append(entry)
            theta1 = theta2

        self.set_xlim(cx - 1.25, cx + 1.25)
        self.set_ylim(cy - 1.25, cy + 1.25)
        if frame:
            warn_external(
                "pie(frame=True) keeps the axes, but the limits are still set "
                "to center +/- 1.25; call set_xlim/set_ylim to change them."
            )
        else:
            self._frame_off = True
            self._show_xticks = self._show_yticks = False
        if autopct is not None:
            return wedges, texts, autotexts
        return wedges, texts

    @_cartesian_only
    def boxplot(
        self,
        x,
        *,
        notch=None,
        sym=None,
        vert=None,
        orientation="vertical",
        whis=None,
        positions=None,
        widths=None,
        patch_artist=None,
        bootstrap=None,
        usermedians=None,
        conf_intervals=None,
        meanline=None,
        showmeans=None,
        showcaps=None,
        showbox=None,
        showfliers=None,
        boxprops=None,
        tick_labels=None,
        flierprops=None,
        medianprops=None,
        meanprops=None,
        capprops=None,
        whiskerprops=None,
        manage_ticks=True,
        autorange=False,
        zorder=None,
        capwidths=None,
        label=None,
        data=None,
    ):
        """Draw a vertical box plot: one box per sample set in ``x``.

        Parameters
        ----------
        x : array-like or sequence of array-like
            The samples. A 1-D array or a list of numbers is one box; a 2-D
            array is one box per column; a sequence of arrays is one box per
            array. Values must be finite.
        notch : bool, optional
            Not supported: ``True`` warns and the box is drawn unnotched.
        sym : str, optional
            ``''`` hides the fliers. Any other value warns: fliers are black
            open circles.
        vert : bool, optional
            Deprecated in matplotlib; ``False`` asks for horizontal boxes,
            which are not supported yet and raise ``ValueError``.
        orientation : {'vertical'}
            Only ``'vertical'`` is supported; ``'horizontal'`` raises
            ``ValueError``.
        whis : float or (float, float), default: 1.5
            A float puts the whisker ends at the farthest data within
            ``whis`` times the interquartile range of the box. A pair gives
            the percentiles of the whisker ends. Data beyond the whiskers are
            drawn as fliers.
        positions : array-like, optional
            Box positions along x. Default ``1, 2, ..., N``.
        widths : float or array-like, optional
            Box widths in data units. Default ``0.15 * (max(positions) -
            min(positions))``, clipped to between 0.15 and 0.5.
        patch_artist : bool, optional
            Not supported: ``True`` warns; boxes are not filled.
        bootstrap, conf_intervals : optional
            Only used for notches, which are not supported: warn.
        usermedians : array-like, optional
            One median per box; ``None`` entries are computed.
        meanline : bool, optional
            Not supported: ``True`` warns; the mean is a marker.
        showmeans : bool, default: False
            Draw each box's mean as a green triangle.
        showcaps : bool, default: True
            Draw the caps at the whisker ends.
        showbox : bool, default: True
            Not supported: ``False`` warns and the box is drawn.
        showfliers : bool, default: True
            Draw the points beyond the whiskers.
        boxprops, flierprops, medianprops : dict, optional
            Not supported: warn. The style is matplotlib's default.
        meanprops, capprops, whiskerprops : dict, optional
            Not supported: warn.
        tick_labels : sequence of str, optional
            One x tick label per box, used with ``manage_ticks``.
        manage_ticks : bool, default: True
            Put x ticks at the box positions, labelled with ``tick_labels``
            when given.
        autorange : bool, default: False
            When a box's first and third quartiles are equal, put its
            whiskers at the data minimum and maximum.
        zorder : float, optional
            Not supported: warns. Boxes are drawn above the other series.
        capwidths : float or array-like, optional
            Cap widths in data units. Default half the box width.
        label : str or sequence of str, optional
            Not supported: warns. Boxes have no legend entry.
        data : optional
            Not supported: warns. Pass the samples directly.

        Returns
        -------
        dict
            Matplotlib's keys -- ``'boxes'``, ``'medians'``, ``'whiskers'``,
            ``'caps'``, ``'fliers'`` and ``'means'`` -- each mapped to the
            list of stored :class:`~gleplot.series.Box` entries (also
            appended to ``self.boxes``). One entry holds every part of its
            box.

        Raises
        ------
        ValueError
            For horizontal boxes, non-finite samples, a ``whis`` that is
            neither a number nor a pair, or a per-box argument whose length
            is not the number of boxes.

        Notes
        -----
        The boxes are drawn after the graph block, above the axes' other
        series, clipped to the frame; a flier or mean outside the axis
        ranges is not drawn. The x range covers each box and half a unit
        either side of its position, as matplotlib's does with
        ``manage_ticks``; the y range covers the whiskers, the median and
        the drawn fliers and means.
        """
        if vert is not None:
            orientation = "vertical" if vert else "horizontal"
        if orientation != "vertical":
            raise ValueError(
                f"boxplot(orientation={orientation!r}) is not supported; only "
                "'vertical' box plots can be drawn."
            )

        if isinstance(x, np.ndarray) and x.ndim > 2:
            raise ValueError(
                f"boxplot(x) must have 2 or fewer dimensions; got an array of "
                f"shape {x.shape}."
            )
        if isinstance(x, np.ndarray) and x.ndim == 2:
            groups = [x[:, j] for j in range(x.shape[1])]
        elif isinstance(x, np.ndarray) or all(np.ndim(v) == 0 for v in x):
            groups = [x]
        else:
            groups = list(x)
        samples = [np.asarray(g, dtype=float).ravel() for g in groups]
        n = len(samples)
        for i, values in enumerate(samples):
            if not np.all(np.isfinite(values)):
                raise ValueError(
                    f"boxplot(x) must be finite; box {i} has NaN or infinite "
                    "values. Drop them before plotting."
                )

        def per_box(name, value, default):
            if value is None:
                return list(default)
            if np.ndim(value) == 0 and not isinstance(value, str):
                return [value] * n
            items = list(value)
            if len(items) != n:
                raise ValueError(
                    f"boxplot({name}=...) needs one value per box ({n}); "
                    f"got {len(items)}."
                )
            return items

        pos = [float(p) for p in per_box("positions", positions, range(1, n + 1))]
        default_width = float(np.clip(0.15 * np.ptp(pos), 0.15, 0.5)) if pos else 0.5
        box_widths = [float(w) for w in per_box("widths", widths, [default_width] * n)]
        cap_widths = [
            float(c)
            for c in per_box("capwidths", capwidths, [w / 2 for w in box_widths])
        ]
        medians = per_box("usermedians", usermedians, [None] * n)
        names = None if tick_labels is None else per_box("tick_labels", tick_labels, [])

        if whis is None:
            whis = 1.5
        if not (isinstance(whis, Real) or np.shape(whis) == (2,)):
            raise ValueError(
                f"boxplot(whis={whis!r}) must be a number, or a pair of "
                "percentiles such as (5, 95)."
            )
        showcaps = True if showcaps is None else bool(showcaps)
        showfliers = True if showfliers is None else bool(showfliers)
        if sym == "":
            showfliers = False
        elif sym is not None:
            warn_external(
                f"boxplot(sym={sym!r}) is not supported; fliers are drawn as "
                "black open circles. Pass sym='' to hide them."
            )
        for name, asked in (
            ("notch", bool(notch)),
            ("patch_artist", bool(patch_artist)),
            ("bootstrap", bootstrap is not None),
            ("conf_intervals", conf_intervals is not None),
            ("meanline", bool(meanline)),
            ("showbox", showbox is not None and not showbox),
            ("boxprops", boxprops is not None),
            ("flierprops", flierprops is not None),
            ("medianprops", medianprops is not None),
            ("meanprops", meanprops is not None),
            ("capprops", capprops is not None),
            ("whiskerprops", whiskerprops is not None),
            ("zorder", zorder is not None),
            ("label", label is not None and len(label) > 0),
            ("data", data is not None),
        ):
            if asked:
                warn_external(
                    f"boxplot({name}=...) is not supported and was ignored. "
                    "See the matplotlib migration guide."
                )

        boxes: List[Box] = []
        for i, values in enumerate(samples):
            if len(values) == 0:
                continue
            q1, med, q3 = (float(q) for q in np.percentile(values, [25, 50, 75]))
            iqr = q3 - q1
            reach = (0, 100) if iqr == 0 and autorange else whis
            if isinstance(reach, Real):
                loval, hival = q1 - reach * iqr, q3 + reach * iqr
            else:
                loval, hival = np.percentile(values, reach)
            inside_hi = values[values <= hival]
            whishi = (
                q3 if len(inside_hi) == 0 or inside_hi.max() < q3 else inside_hi.max()
            )
            inside_lo = values[values >= loval]
            whislo = (
                q1 if len(inside_lo) == 0 or inside_lo.min() > q1 else inside_lo.min()
            )
            fliers = np.concatenate([values[values < whislo], values[values > whishi]])
            entry = Box(
                type="box",
                x=pos[i],
                width=box_widths[i],
                capwidth=cap_widths[i] if showcaps else 0.0,
                whislo=float(whislo),
                q1=q1,
                med=med if medians[i] is None else float(medians[i]),
                q3=q3,
                whishi=float(whishi),
                fliers=[float(f) for f in fliers] if showfliers else [],
                mean=float(values.mean()) if showmeans else None,
            )
            self.boxes.append(entry)
            boxes.append(entry)

        if manage_ticks:
            # Matplotlib adds the positions to the ticks already there.
            places = list(self.xplaces or [])
            if names is not None or self.xnames:
                old = list(self.xnames or [f"{p:g}" for p in places])
                if names is None:
                    new = [f"{p:g}" for p in pos]
                else:
                    new = [str(self._text(str(s))) for s in names]
                self.xnames = old + new
            self.xplaces = places + pos
        keys = ("whiskers", "caps", "boxes", "medians", "fliers", "means")
        return {key: list(boxes) for key in keys}

    # -- placed images --------------------------------------------------

    @_cartesian_only
    def image(self, fname, extent) -> PlacedImage:
        """Place an image file over a rectangle in data coordinates.

        Unlike :meth:`imshow`, which colours a 2-D array, this draws an
        existing picture: a micrograph, a photograph, a logo.

        Parameters
        ----------
        fname : str or path-like
            A PNG, JPEG, GIF, TIFF or EPS file. GLE reads it when the figure
            is compiled; a relative path is read from the folder the ``.gle``
            script is saved in.
        extent : (left, right, bottom, top)
            The rectangle the image is stretched over, in data coordinates.

        Returns
        -------
        PlacedImage
            The stored image entry (also appended to ``self.images``).

        Raises
        ------
        ValueError
            If the file extension is not one GLE can place, the path holds a
            double quote, or ``extent`` is not four finite numbers with
            ``left < right`` and ``bottom < top``.
        TypeError
            If ``fname`` is not a string or path, or ``extent`` is not a
            sequence of numbers.

        Notes
        -----
        The image is drawn behind the grid and the data, and clipped to the
        axes. Its extent takes part in autoscaling, and on a log axis it must
        be positive. An EPS file is drawn only when GLE compiles through
        PostScript: not to SVG, and not with GLE's Cairo device, which a
        figure with semi-transparent colours needs.
        """
        if not isinstance(fname, (str, os.PathLike)):
            raise TypeError(
                f"image(fname={fname!r}) must be a file path (str or " "path-like)."
            )
        path = os.fspath(fname)
        if image_sub_name(path) is None:
            raise ValueError(
                f"image(fname={path!r}) has an extension GLE cannot place; "
                "use a .png, .jpg, .jpeg, .gif, .tif, .tiff or .eps file."
            )
        if '"' in path:
            raise ValueError(
                f"image(fname={path!r}) contains a double quote, which a GLE "
                "string cannot hold; rename the file."
            )
        try:
            if isinstance(extent, str):
                raise TypeError
            ext = [float(v) for v in extent]
        except (TypeError, ValueError):
            raise TypeError(
                f"image(extent={extent!r}) must be four numbers "
                "(left, right, bottom, top)."
            ) from None
        if len(ext) != 4:
            raise ValueError(
                f"image(extent={extent!r}) must be four numbers "
                "(left, right, bottom, top)."
            )
        _require_valid_extent(ext)
        entry = PlacedImage(type="image", file=path, extent=ext)
        self.images.append(entry)
        return entry

    @_cartesian_only
    def rug(self, x, axis="x", length=0.3, position=None, color="black", linewidth=1.0):
        """Draw a rug: one short tick on the frame at each value of ``x``.

        Matplotlib has no rug; this is gleplot API.

        Parameters
        ----------
        x : array-like
            The values, in data coordinates along ``axis``. Must be finite.
        axis : {'x', 'y'}, default: 'x'
            ``'x'`` puts the ticks on a horizontal edge at the x values;
            ``'y'`` on a vertical edge at the y values.
        length : float, default: 0.3
            Tick length in cm, into the axes from the frame. A negative
            length points out of the axes, as GLE's ``ticks length`` does.
        position : str, optional
            The frame edge: ``'bottom'`` (the default), ``'top'`` or
            ``'both'`` for ``axis='x'``; ``'left'`` (the default),
            ``'right'`` or ``'both'`` for ``axis='y'``.
        color : color, default: 'black'
        linewidth : float, default: 1.0
            Line width in points.

        Returns
        -------
        Rug
            The stored :class:`~gleplot.series.Rug` (also appended to
            ``self.rugs``).

        Raises
        ------
        ValueError
            For an unknown ``axis`` or ``position``, non-finite values, a
            zero or non-finite ``length``, or a ``linewidth`` that is not
            more than 0.
        TypeError
            For a ``length`` or ``linewidth`` that is not a number.

        Notes
        -----
        The rug is drawn after the graph block, above the axes' other
        series; a value outside the axis range draws no tick. The values
        widen the autoscaled range of their axis.
        """
        if axis not in RUG_EDGES:
            raise ValueError(f"rug(axis={axis!r}) must be 'x' or 'y'.")
        if position is None:
            position = RUG_EDGES[axis][0]
        if position not in RUG_EDGES[axis]:
            raise ValueError(
                f"rug(position={position!r}) with axis={axis!r} must be one of "
                f"{', '.join(repr(p) for p in RUG_EDGES[axis])}."
            )
        for name, value in (("length", length), ("linewidth", linewidth)):
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError(
                    f"rug({name}={value!r}) must be a number; got "
                    f"{type(value).__name__}."
                )
        values = np.asarray(x, dtype=float).ravel()
        if not np.all(np.isfinite(values)):
            raise ValueError(
                "rug(x) must be finite; it has NaN or infinite values. Drop them "
                "before plotting."
            )
        if not np.isfinite(length) or length == 0:
            raise ValueError(
                f"rug(length={length!r}) must be a non-zero length in cm; a "
                "negative length points out of the axes."
            )
        if not np.isfinite(linewidth) or linewidth <= 0:
            raise ValueError(
                f"rug(linewidth={linewidth!r}) must be a line width in points, "
                "more than 0."
            )
        entry = Rug(
            type="rug",
            axis=axis,
            ticks=[float(v) for v in values],
            length=float(length),
            position=position,
            color=rgb_to_gle(color),
            linewidth=float(linewidth),
        )
        self.rugs.append(entry)
        return entry

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

    @_cartesian_only
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
            Palette name (see :data:`gleplot.palettes.SUPPORTED_CMAPS`), or
            one with ``_r`` appended for its reversed form, as in matplotlib.
            When ``None``, uses the figure graph config's ``default_cmap``.
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
            Series label (not drawn by the colormap itself; kept so an
            application can list the series by name).

        Returns
        -------
        dict
            The stored heatmap series dict.

        Notes
        -----
        Other matplotlib keywords (``alpha``, ``norm``, ``aspect``, ...)
        warn and are ignored: a GLE colormap is opaque and maps colours
        linearly from ``vmin`` to ``vmax``.
        """
        warn_unsupported_keywords("imshow", kwargs)
        label = self._text(label)
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

    @_cartesian_only
    def function2d(
        self,
        expression: str,
        extent,
        cmap: Optional[str] = None,
        vmin: Optional[float] = 0.0,
        vmax: Optional[float] = 1.0,
        pixels=None,
        invert: bool = False,
        label: Optional[str] = None,
    ):
        """Draw a heatmap that GLE computes from an expression in ``x`` and ``y``.

        Written as one ``colormap`` line, such as
        ``colormap sin(x)*cos(y) 200 200 zmin -1 zmax 1``: GLE evaluates the
        expression at every pixel, so no data file is written. Use
        :meth:`imshow` when you already have the array.

        Parameters
        ----------
        expression : str
            A GLE expression in ``x`` and ``y``, such as ``"sin(x)*cos(y)"``
            or ``"exp(-(x^2+y^2)/2)"``. It is written as given, without
            spaces.
        extent : (xmin, xmax, ymin, ymax)
            The region to show. It sets the axis range the way an
            :meth:`imshow` extent does.
        cmap : str, optional
            Palette name, as for :meth:`imshow`.
        vmin, vmax : float, optional
            The values drawn at the two ends of the colour scale (GLE
            ``zmin``/``zmax``). ``None`` leaves the clause out, and GLE then
            uses 0 and 1.
        pixels : int or (px, py), optional
            Bitmap resolution, as for :meth:`imshow`.
        invert : bool
            Invert the colour mapping.
        label : str, optional
            Series label (not drawn by the colormap itself).

        Returns
        -------
        dict
            The stored heatmap series dict.

        Notes
        -----
        GLE does not look for the range of the expression's values, so the
        colour scale runs from ``vmin`` to ``vmax`` (0 to 1 by default)
        rather than from the smallest value to the largest as :meth:`imshow`
        does. Set them to the range of your function. Values outside are
        drawn in the end colours.

        GLE fills the whole graph with the map. When other data or
        :meth:`set_xlim` widens the axes beyond ``extent``, the map covers
        that wider range too.
        """
        self._check_let_expression("function2d", expression)
        try:
            ext = [float(v) for v in extent]
        except (TypeError, ValueError):
            ext = []
        if len(ext) != 4:
            raise ValueError(
                "function2d() extent must be four numbers (xmin, xmax, ymin, "
                f"ymax), got {extent!r}"
            )
        _require_valid_extent(ext)
        if self.heatmaps:
            raise ValueError(
                "GLE supports at most one heatmap (colormap) per axes; "
                "this axes already has one"
            )
        hm = HeatmapSeries(
            type="heatmap",
            source="function",
            expression=expression,
            z=None,
            x=None,
            y=None,
            zpts=None,
            extent=ext,
            origin="lower",
            cmap=self._resolve_cmap(cmap),
            vmin=None if vmin is None else float(vmin),
            vmax=None if vmax is None else float(vmax),
            interpolation="bicubic",
            pixels=self._resolve_pixels(pixels),
            invert=bool(invert),
            gridsize=None,
            ncontour=None,
            label=self._text(label),
            colorbar=None,
        )
        self.heatmaps.append(hm)
        return hm

    @_cartesian_only
    def pcolormesh(
        self,
        *args,
        alpha=None,
        norm=None,
        cmap: Optional[str] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        colorizer=None,
        shading: Optional[str] = None,
        antialiased: bool = False,
        data=None,
        pixels=None,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Colour each cell of a rectangular grid by its value.

        Signatures: ``pcolormesh(C)`` or ``pcolormesh(X, Y, C)`` with ``C`` of
        shape ``(ny, nx)``. ``X`` and ``Y`` are 1-D, or the 2-D arrays
        ``np.meshgrid`` returns. Their spacing must be uniform: a GLE ``.z``
        grid is an extent plus a shape. An irregular grid raises; use
        :meth:`tripcolor` for scattered or irregularly gridded data.

        Parameters
        ----------
        alpha : float, optional
            Not supported: a GLE colormap is opaque. Passing it warns.
        norm : optional
            Not supported: colours are always mapped linearly from ``vmin``
            to ``vmax``. Passing it warns.
        cmap : str, optional
            Palette name, as for :meth:`imshow`.
        vmin, vmax : float, optional
            The values given the colormap's first and last colour. ``None``
            uses the data's range.
        colorizer : optional
            Not supported; pass ``cmap``, ``vmin`` and ``vmax``. Passing it
            warns.
        shading : {'auto', 'flat', 'nearest', 'gouraud'}, optional
            ``'flat'`` takes ``X`` and ``Y`` as the cell edges, one longer
            than ``C`` along each axis. ``'nearest'`` takes them as the cell
            centres, the same shape as ``C``, and puts each edge halfway
            between two centres. ``'auto'`` (the default, as ``None``) picks
            whichever of the two the shapes fit. ``'gouraud'`` warns and is
            drawn as ``'nearest'``.
        antialiased : bool
            Not supported: the mesh is drawn as one bitmap. ``True`` warns.
        data : optional
            Not supported; pass the arrays directly. Passing it warns.
        pixels : int or (px, py), optional
            Bitmap resolution, as for :meth:`imshow`. Each cell edge is drawn
            to within one of these pixels.
        label : str, optional
            Series label (not drawn by the colormap itself).

        Returns
        -------
        dict
            The stored heatmap series dict, which
            :meth:`gleplot.Figure.colorbar` takes as its ``mappable``.

        Notes
        -----
        Like :meth:`imshow`, a mesh is the axes' one heatmap, and its values
        must be finite: a ``NaN`` or a masked value raises ``ValueError``,
        where matplotlib leaves the cell blank. The mesh's bitmap runs half a
        cell past each edge, which the axes frame normally hides; saving
        warns when the axis limits reach beyond the mesh, or when a log axis
        puts that half cell at or below zero, where GLE does not draw it. Coordinates that decrease are drawn the same as
        increasing ones, as in matplotlib. ``edgecolors='none'`` and
        ``'face'`` are what is drawn; other keywords (another
        ``edgecolors``, ``linewidth``, ``zorder``, ...) warn and are ignored.
        """
        label = self._text(label)
        shading = "auto" if shading is None else str(shading).lower()
        if shading not in ("auto", "flat", "nearest", "gouraud"):
            raise ValueError(
                f"pcolormesh() got shading={shading!r}; expected 'auto', "
                "'flat', 'nearest' or 'gouraud'"
            )
        if shading == "gouraud":
            warn_external(
                "pcolormesh(shading='gouraud') is drawn as shading='nearest': "
                "gleplot colours each cell flat."
            )
            shading = "nearest"
        for name, value, why in (
            ("alpha", alpha, "a GLE colormap is opaque"),
            ("norm", norm, "colours are mapped linearly; pass vmin= and vmax="),
            ("colorizer", colorizer, "pass cmap=, vmin= and vmax= instead"),
            ("data", data, "pass the arrays themselves"),
        ):
            if value is not None:
                warn_external(f"pcolormesh({name}=...) is ignored: {why}.")
        if antialiased:
            warn_external(
                "pcolormesh(antialiased=True) is ignored: the mesh is drawn as "
                "one bitmap."
            )
        for key in ("edgecolors", "edgecolor"):
            edge = kwargs.get(key)
            if edge is None or (
                isinstance(edge, str) and edge.lower() in ("none", "face")
            ):
                kwargs.pop(key, None)
        warn_unsupported_keywords("pcolormesh", kwargs)
        z, ext = self._mesh_from_args(args, shading)
        if self.heatmaps:
            raise ValueError(
                "GLE supports at most one heatmap (colormap) per axes; "
                "this axes already has one"
            )
        hm = HeatmapSeries(
            type="heatmap",
            source="grid",
            z=z,
            x=None,
            y=None,
            zpts=None,
            extent=ext,
            origin="lower",
            cmap=self._resolve_cmap(cmap),
            vmin=None if vmin is None else float(vmin),
            vmax=None if vmax is None else float(vmax),
            interpolation="nearest",
            cells=True,
            pixels=self._resolve_pixels(pixels),
            invert=False,
            gridsize=None,
            ncontour=None,
            label=label,
            data_file=_reserve_sidecar(self.figure, "heatmap", "z"),
            colorbar=None,
        )
        self.heatmaps.append(hm)
        return hm

    def _mesh_from_args(self, args, shading):
        """Parse ``pcolormesh`` positional args into ``(C, cell-edge extent)``.

        ``shading`` is ``'auto'``, ``'flat'`` or ``'nearest'``. Coordinates
        that decrease are turned round, flipping ``C`` with them, so the
        extent ascends as GLE requires.
        """
        if len(args) not in (1, 3):
            raise ValueError(
                "pcolormesh() takes C or X, Y, C as positional arguments; got "
                f"{len(args)} of them"
            )
        # A masked value has no colour GLE can leave blank, so it raises as
        # NaN does rather than being drawn with the value under the mask.
        z = np.ma.filled(np.ma.asarray(args[-1], dtype=float), np.nan)
        if z.ndim != 2:
            raise ValueError(f"pcolormesh() needs a 2-D C; got shape {z.shape}")
        _require_finite(z, "pcolormesh C")
        ny, nx = z.shape
        if len(args) == 1:
            if shading == "nearest":
                x, y = np.arange(nx, dtype=float), np.arange(ny, dtype=float)
            else:
                x = np.arange(nx + 1, dtype=float)
                y = np.arange(ny + 1, dtype=float)
        else:
            x = np.ma.filled(np.ma.asarray(args[0], dtype=float), np.nan)
            y = np.ma.filled(np.ma.asarray(args[1], dtype=float), np.nan)
            _require_finite(x, "pcolormesh X")
            _require_finite(y, "pcolormesh Y")
            if x.ndim == 2:
                x = _axis_from_meshgrid(
                    x, "x", "pcolormesh(X, Y, C)", "tripcolor(x, y, z)"
                )
            if y.ndim == 2:
                y = _axis_from_meshgrid(
                    y, "y", "pcolormesh(X, Y, C)", "tripcolor(x, y, z)"
                )
            if x.ndim != 1 or y.ndim != 1:
                raise ValueError(
                    "pcolormesh(X, Y, C) needs 1-D X and Y, or the 2-D X and Y "
                    "np.meshgrid returns"
                )
        if shading == "auto":
            shading = "nearest" if (len(x), len(y)) == (nx, ny) else "flat"
        want = (nx + 1, ny + 1) if shading == "flat" else (nx, ny)
        if (len(x), len(y)) != want:
            raise ValueError(
                f"pcolormesh(shading={shading!r}) needs {want[0]} x and "
                f"{want[1]} y coordinates for C of shape {z.shape}; got "
                f"{len(x)} and {len(y)}"
            )
        if shading == "nearest" and (nx < 2 or ny < 2):
            raise ValueError(
                "pcolormesh(shading='nearest') needs at least two centres along "
                f"each axis to size the cells; C has shape {z.shape}. Pass the "
                "cell edges instead."
            )
        self._check_uniform(x, "x", "pcolormesh", "tripcolor(x, y, z)")
        self._check_uniform(y, "y", "pcolormesh", "tripcolor(x, y, z)")
        if shading == "nearest":
            dx, dy = (x[1] - x[0]) / 2, (y[1] - y[0]) / 2
            x = np.array([x[0] - dx, x[-1] + dx])
            y = np.array([y[0] - dy, y[-1] + dy])
        if x[-1] < x[0]:
            x, z = x[::-1], z[:, ::-1]
        if y[-1] < y[0]:
            y, z = y[::-1], z[::-1]
        ext = [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])]
        _require_valid_extent(ext)
        return z, ext

    @_cartesian_only
    def contourf(
        self,
        *args,
        levels=None,
        cmap: Optional[str] = None,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        extend: str = "neither",
        pixels=None,
        label: Optional[str] = None,
        **kwargs,
    ):
        """Fill the bands between contour levels of gridded data.

        Signatures, as in matplotlib: ``contourf(Z)``, ``contourf(X, Y, Z)``,
        and either with ``levels`` as one more positional argument. ``X`` and
        ``Y`` give the grid's nodes: 1-D, or the 2-D arrays ``np.meshgrid``
        returns, uniformly spaced and increasing. Without them the nodes are
        at ``0 .. nx - 1`` and ``0 .. ny - 1``. An irregular grid raises; use
        :meth:`tripcolor` for scattered or irregularly gridded data.

        Parameters
        ----------
        levels : int or sequence, optional
            The band edges. An int ``n`` picks about ``n`` round-number
            levels spanning the data, the way matplotlib's ``MaxNLocator``
            does; ``None`` is ``7``. A sequence is used as given, and must
            increase.
        cmap : str, optional
            Palette name, as for :meth:`imshow`.
        vmin, vmax : float, optional
            The values given the colormap's first and last colour; each band
            takes the colour of its middle value. Default: the first and
            last level.
        extend : {'neither', 'min', 'max', 'both'}
            Which side's values beyond the levels are filled, with the
            colormap's end colour. With ``'neither'`` they are white.
        pixels : int or (px, py), optional
            Bitmap resolution, as for :meth:`imshow`.
        label : str, optional
            Series label (not drawn by the colormap itself).

        Returns
        -------
        dict
            The stored heatmap series dict.

        Notes
        -----
        GLE has no filled contour. A ``contourf`` is a heatmap whose palette
        sub (``gleplot_contourf<k>``) colours each value by the band it falls
        in. GLE's colormap smooths the grid with a cubic B-spline first, so a
        band edge is drawn near its level, not on it. When some edge would
        land more than one bitmap pixel away (a coarse grid for the number
        of ``pixels``), the call warns and the heatmap is drawn smooth,
        coloured by value between the outer levels. That decision assumes the
        axis limits are the grid's extent.

        Like :meth:`imshow`, it is the axes' one heatmap, and values must be
        finite: a ``NaN`` or a masked value raises ``ValueError``. Values
        beyond the levels are white with ``extend='neither'``, where
        matplotlib leaves them blank. Other keywords (``colors``, ``alpha``,
        ``norm``, ``hatches``, ...) warn and are ignored.
        """
        label = self._text(label)
        if extend not in CONTOURF_EXTENDS:
            raise ValueError(
                f"contourf() got extend={extend!r}; expected 'neither', 'min', "
                "'max' or 'both'"
            )
        # A masked value has no colour GLE can leave blank, so it raises as
        # NaN does rather than being drawn with the value under the mask.
        grid = [np.ma.filled(np.ma.asarray(a, dtype=float), np.nan) for a in args]
        if len(grid) in (2, 4):
            if levels is not None:
                raise ValueError(
                    "contourf() got levels both as an argument and as levels=; "
                    "pass them once"
                )
            levels = grid.pop()
        if len(grid) == 1:
            z = grid[0]
            if z.ndim != 2:
                raise ValueError(
                    f"contourf(Z) requires a 2-D array; got shape {z.shape}"
                )
            _require_finite(z, "contourf Z")
            ext = [0.0, float(z.shape[1] - 1), 0.0, float(z.shape[0] - 1)]
        else:
            z, ext = self._grid_from_args(grid, "contourf", "tripcolor(x, y, z)")
        if min(z.shape) < 2:
            raise ValueError(
                "contourf() needs at least two grid nodes along each axis; Z "
                f"has shape {z.shape}"
            )
        _require_valid_extent(ext)
        levels = self._filled_levels(levels, z, extend)
        # Compared as written: the band sub divides by their difference.
        lo, hi = (
            float(GLEWriter._format_number(float(v)))
            for v in (
                levels[0] if vmin is None else vmin,
                levels[-1] if vmax is None else vmax,
            )
        )
        if not lo < hi:
            raise ValueError(
                f"contourf() needs vmin < vmax; got vmin={lo!r}, vmax={hi!r}"
            )
        for key in ("colors", "alpha", "norm", "hatches", "data"):
            if kwargs.pop(key, None) is not None:
                warn_external(
                    f"contourf({key}=...) is ignored: GLE fills the bands from "
                    "the colormap. Pass cmap=, vmin= and vmax= instead."
                )
        warn_unsupported_keywords("contourf", kwargs)
        if self.heatmaps:
            raise ValueError(
                "GLE supports at most one heatmap (colormap) per axes; "
                "this axes already has one"
            )
        hm = HeatmapSeries(
            type="heatmap",
            source="grid",
            z=z,
            x=None,
            y=None,
            zpts=None,
            extent=ext,
            origin="lower",
            cmap=self._resolve_cmap(cmap),
            vmin=None if vmin is None else float(vmin),
            vmax=None if vmax is None else float(vmax),
            interpolation="bicubic",
            levels=levels,
            extend=extend,
            pixels=self._resolve_pixels(pixels),
            invert=False,
            gridsize=None,
            ncontour=None,
            label=label,
            data_file=_reserve_sidecar(self.figure, "heatmap", "z"),
            colorbar=None,
        )
        if not contourf_bands_fit(hm):
            warn_external(
                "contourf() is drawn as a smooth heatmap, not bands: GLE "
                "smooths the grid, and on this one some band edges would land "
                "more than one pixel from their levels. Pass a finer Z, or "
                "fewer pixels=, to get bands."
            )
        self.heatmaps.append(hm)
        return hm

    @staticmethod
    def _filled_levels(levels, z, extend):
        """``contourf``'s band edges: matplotlib's for a count, else as given."""
        if levels is None or np.ndim(levels) == 0:
            n = 7 if levels is None else levels
            try:
                whole = float(n) == int(float(n))
            except (TypeError, ValueError, OverflowError):
                whole = False
            if not whole or int(float(n)) < 1:
                raise ValueError(
                    f"contourf() got levels={levels!r}; expected a whole number "
                    "of levels >= 1, or a sequence of at least two increasing "
                    "values"
                )
            out = _nice_levels(
                float(np.min(z)), float(np.max(z)), int(float(n)), extend
            )
        else:
            out = [float(v) for v in np.ravel(levels)]
            if len(out) < 2 or not all(np.isfinite(out)):
                raise ValueError(
                    "contourf() needs at least two finite levels, the edges of "
                    f"one band; got {levels!r}"
                )
            if np.any(np.diff(out) <= 0):
                raise ValueError(f"contourf() levels must increase; got {levels!r}")
        written = [float(GLEWriter._format_number(v)) for v in out]
        if np.any(np.diff(written) <= 0):
            raise ValueError(
                f"contourf() levels {out} are closer together than the 6 "
                "significant digits gleplot writes them with. Pass levels= "
                "with fewer or wider-spaced values (or subtract the offset "
                "from Z)."
            )
        return out

    @_cartesian_only
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

        Notes
        -----
        As in matplotlib, ``linewidth`` (``lw``) and ``linestyle`` (``ls``)
        are accepted for ``linewidths`` and ``linestyles``. Other matplotlib
        keywords (``alpha``, ``extent``, ``origin``, ...) warn and are
        ignored; pass ``x`` and ``y`` to place the grid.
        """
        linewidths, linestyles = _contour_line_keywords(
            "contour", linewidths, linestyles, kwargs
        )
        label = self._text(label)
        z, ext = self._grid_from_args(args, "contour", "tricontour(x, y, z)")
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

    def _grid_from_args(self, args, func, scattered):
        """Parse ``contour`` positional args into ``(z_2d, extent)``.

        ``func`` is the method the errors name, and ``scattered`` the call
        they suggest for data on another grid.
        """
        if len(args) == 1:
            z = np.asarray(args[0], dtype=float)
            if z.ndim != 2:
                raise ValueError(f"{func}(Z) requires a 2-D array")
            _require_finite(z, f"{func} Z")
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
                            f"{func}(X, Y, Z): 2-D {cname.upper()} has shape "
                            f"{coord.shape} but Z has shape {z.shape}; a "
                            "meshgrid coordinate array must match Z"
                        )
                if x.ndim == 2:
                    x = _axis_from_meshgrid(x, "x", f"{func}(X, Y, Z)", scattered)
                if y.ndim == 2:
                    y = _axis_from_meshgrid(y, "y", f"{func}(X, Y, Z)", scattered)
            if x.ndim != 1 or y.ndim != 1 or z.ndim != 2:
                raise ValueError(
                    f"{func}(x, y, Z) requires 1-D x, 1-D y, 2-D Z (or "
                    "matplotlib's 2-D meshgrid X, Y matching Z's shape)"
                )
            if z.shape != (len(y), len(x)):
                raise ValueError(
                    f"Z shape {z.shape} does not match (len(y), len(x)) = "
                    f"({len(y)}, {len(x)})"
                )
            _require_finite(x, f"{func} x")
            _require_finite(y, f"{func} y")
            _require_finite(z, f"{func} Z")
            self._check_uniform(x, "x", func, scattered)
            self._check_uniform(y, "y", func, scattered)
            ext = [float(x[0]), float(x[-1]), float(y[0]), float(y[-1])]
            _require_valid_extent(ext)
            return z, ext
        raise ValueError(f"{func} expects {func}(Z) or {func}(x, y, Z)")

    @staticmethod
    def _check_uniform(v, name, func, scattered):
        """Validate that a 1-D coordinate array is uniformly spaced.

        ``func`` is the method the error names and ``scattered`` the call it
        suggests for data on another grid.
        """
        if len(v) < 2:
            return
        diffs = np.diff(v)
        step = diffs[0]
        if step == 0 or not np.allclose(diffs, step, rtol=1e-6, atol=1e-12):
            raise ValueError(
                f"{func} requires uniformly spaced {name} (a .z grid is "
                f"uniform); got non-uniform spacing. Use {scattered} for "
                "scattered or irregularly gridded data."
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

    @_cartesian_only
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

        Notes
        -----
        The remaining keyword arguments are as for :meth:`imshow`; others
        warn and are ignored.
        """
        warn_unsupported_keywords("tripcolor", kwargs)
        label = self._text(label)
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

    @_cartesian_only
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

        Notes
        -----
        The remaining keyword arguments are as for :meth:`contour`, aliases
        included; others warn and are ignored.
        """
        linewidths, linestyles = _contour_line_keywords(
            "tricontour", linewidths, linestyles, kwargs
        )
        label = self._text(label)
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

    def set_xlabel(
        self,
        label: str,
        axis: str = "x",
        *,
        labelpad: Optional[float] = None,
        loc: Optional[str] = None,
        fontname: Optional[str] = None,
        **kwargs,
    ):
        """Set x-axis label.

        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'x' (bottom, default) or 'x2' (top)
        labelpad : float, optional
            Gap between the label and the tick labels, in points (GLE
            ``xtitle ... dist``). ``None`` keeps the current gap.
        loc : str, optional
            ``'left'``, ``'center'`` or ``'right'``. GLE centres axis
            titles, so the other two warn.
        fontname : str, optional
            GLE font for the label, such as ``'texcmr'`` (GLE ``xtitle ...
            font``). ``None`` keeps the current font.
        **kwargs
            ``fontsize`` (points, or a name such as ``'small'``) and
            ``color``; ``None`` for either goes back to the default. Other
            matplotlib text keywords warn and are ignored.
        """
        prefix = "x2" if axis == "x2" else "x"
        setattr(self, f"{prefix}label_text", self._text(label))
        self._style_title(
            f"{prefix}label", "set_xlabel", "labelpad", labelpad, loc, fontname, kwargs
        )
        return self

    def set_ylabel(
        self,
        label: str,
        axis: str = "y",
        *,
        labelpad: Optional[float] = None,
        loc: Optional[str] = None,
        fontname: Optional[str] = None,
        **kwargs,
    ):
        """Set y-axis label.

        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        labelpad : float, optional
            Gap between the label and the tick labels, in points (GLE
            ``ytitle ... dist``). ``None`` keeps the current gap.
        loc : str, optional
            ``'bottom'``, ``'center'`` or ``'top'``. GLE centres axis
            titles, so the other two warn.
        fontname : str, optional
            GLE font for the label (GLE ``ytitle ... font``). ``None`` keeps
            the current font.
        **kwargs
            ``fontsize`` (points, or a name such as ``'small'``) and
            ``color``; ``None`` for either goes back to the default. Other
            matplotlib text keywords warn and are ignored.
        """
        prefix = "y2" if axis == "y2" else "y"
        setattr(self, f"{prefix}label_text", self._text(label))
        self._style_title(
            f"{prefix}label", "set_ylabel", "labelpad", labelpad, loc, fontname, kwargs
        )
        return self

    def set_title(
        self,
        label: str,
        fontdict: Optional[Dict[str, Any]] = None,
        loc: Optional[str] = None,
        pad: Optional[float] = None,
        *,
        fontname: Optional[str] = None,
        **kwargs,
    ):
        """Set subplot title.

        Parameters
        ----------
        label : str
            Title text
        fontdict : dict, optional
            Not supported; warns and is ignored. Pass ``fontsize`` and
            ``color`` as keywords.
        loc : str, optional
            ``'left'``, ``'center'`` or ``'right'``. GLE centres the
            title, so the other two warn.
        pad : float, optional
            Gap between the title and the top of the axes, in points (GLE
            ``title ... dist``). ``None`` keeps the current gap.
        fontname : str, optional
            GLE font for the title (GLE ``title ... font``). ``None`` keeps
            the current font.
        **kwargs
            ``fontsize`` (points, or a name such as ``'large'``) and
            ``color``; ``None`` for either goes back to the default. Other
            matplotlib text keywords warn and are ignored.
        """
        self.title_text = self._text(label)
        if fontdict is not None:
            kwargs["fontdict"] = fontdict
        self._style_title("title", "set_title", "pad", pad, loc, fontname, kwargs)
        return self

    def _style_title(self, prefix, caller, pad_name, pad, loc, fontname, kwargs):
        """Store a title's ``fontsize``/``color``/pad/font on ``{prefix}_*``.

        ``pad`` is in points and is stored as GLE's ``dist`` in cm; the
        size stays in points, as ``legend(fontsize=)`` keeps it, and the
        writer converts it to ``hei``.
        """
        if loc is not None:
            places = ("bottom", "center", "top")
            if caller != "set_ylabel":
                places = ("left", "center", "right")
            if loc not in places:
                raise ValueError(
                    f"{caller}(loc={loc!r}) must be one of {', '.join(places)}"
                )
            if loc != "center":
                warn_external(
                    f"{caller}(loc={loc!r}) is drawn centred: GLE centres "
                    "every title.",
                )
        if "fontsize" in kwargs:
            fontsize = kwargs.pop("fontsize")
            setattr(
                self,
                f"{prefix}_size",
                (
                    None
                    if fontsize is None
                    else _resolve_fontsize(
                        self._style(), fontsize, f"{caller}(fontsize"
                    )
                ),
            )
        if "color" in kwargs:
            color = kwargs.pop("color")
            setattr(
                self, f"{prefix}_color", None if color is None else rgb_to_gle(color)
            )
        if pad is not None:
            points = _finite_float(pad, f"{caller}({pad_name}=...)")
            # Kept at the precision the file carries, so the distance reads
            # back from the saved script as the same number.
            cm = GLEWriter._format_number(fontsize_pt_to_cm(points))
            setattr(self, f"{prefix}_dist", float(cm))
        if fontname is not None:
            setattr(self, f"{prefix}_font", _gle_font_name(fontname, caller))
        if kwargs:
            warn_external(
                f"{caller}(): "
                + ", ".join(sorted(kwargs))
                + f" not supported in gleplot and ignored. {caller}() takes "
                f"fontsize, color, {pad_name} and fontname.",
            )

    def set_axis_line(
        self,
        axis: str = "both",
        *,
        color: Any = None,
        linewidth: Optional[float] = None,
        visible: Optional[bool] = None,
    ):
        """Set the colour, width and visibility of an axis line (GLE ``xside``).

        Only the line is styled; ticks, tick labels and the grid keep their
        own colour. This is gleplot's form of matplotlib's
        ``ax.spines[...].set_color()`` / ``.set_linewidth()`` /
        ``.set_visible()``, with ``'x'``, ``'y'``, ``'x2'`` and ``'y2'``
        for the bottom, left, top and right spines.

        Parameters
        ----------
        axis : {'both', 'x', 'y', 'x2', 'y2'}
            Which axis line. ``'both'`` means x and y.
        color : color, optional
            Any colour :func:`gleplot.colors.rgb_to_gle` accepts. ``None``
            keeps the current colour.
        linewidth : float, optional
            Line width in points. ``None`` keeps the current width.
        visible : bool, optional
            ``False`` hides the line, ``True`` shows it again. ``None``
            keeps the current visibility.

        Returns
        -------
        Axes
            ``self``.

        Raises
        ------
        ValueError
            On an unknown ``axis`` or a negative ``linewidth``.
        TypeError
            If ``visible`` is not a bool or None.

        Notes
        -----
        GLE copies an x setting onto the top edge and a y setting onto the
        right edge. So ``axis='x'`` styles the top line too, unless
        ``axis='x2'`` gives the top line its own style. Visibility is not
        copied: ``visible=False`` hides only the edge it names.

        Hiding the bottom or left line keeps its ticks and tick labels, as
        in matplotlib. Hiding the top or right edge also removes the tick
        marks GLE mirrors there (matplotlib draws none there by default),
        and with them any top or right scale: a ``twiny`` / ``twinx``
        scale, a ``yaxis='y2'`` series' numbers, a y2 label. ``savefig``
        warns in that case.

        Examples
        --------
        The open-frame look of ``ax.spines[["top", "right"]].set_visible(False)``:

        >>> import gleplot as glp
        >>> fig, ax = glp.subplots()
        >>> for side in ("x2", "y2"):
        ...     _ = ax.set_axis_line(side, visible=False)
        """
        if axis not in ("both", "x", "y", "x2", "y2"):
            raise ValueError(
                f"set_axis_line(axis={axis!r}) must be 'both', 'x', 'y', "
                "'x2' or 'y2'"
            )
        if visible is not None and not isinstance(visible, (bool, np.bool_)):
            raise TypeError(
                f"set_axis_line(visible={visible!r}) must be True, False or None"
            )
        width = None
        if linewidth is not None:
            width = _finite_float(linewidth, "set_axis_line(linewidth=...)")
            if width < 0:
                raise ValueError(
                    f"set_axis_line(linewidth={linewidth!r}) must be a "
                    "non-negative width in points"
                )
        for name in ("x", "y") if axis == "both" else (axis,):
            if color is not None:
                setattr(self, f"{name}side_color", rgb_to_gle(color))
            if width is not None:
                setattr(self, f"{name}side_lwidth", width)
            if visible is None:
                continue
            if name in ("x", "y"):
                setattr(self, f"{name}side_off", None if visible else True)
                continue
            setattr(self, f"_{name}axis_off", not visible)
        return self

    @_cartesian_only
    def set_math_mode(self, on: bool = True):
        """Draw the x and y axes through the origin (GLE ``math``).

        The x axis is drawn at y = 0 and the y axis at x = 0, with ticks on
        both sides of each, and the top and right axes are hidden. This is
        gleplot's form of matplotlib's
        ``ax.spines['left'].set_position('zero')`` and
        ``ax.spines['bottom'].set_position('zero')`` with the top and right
        spines hidden.

        Parameters
        ----------
        on : bool, default: True
            ``False`` goes back to axes framing the plot.

        Returns
        -------
        Axes
            ``self``.

        Raises
        ------
        TypeError
            If ``on`` is not a bool.

        Notes
        -----
        Both axes move together; moving only one of them is not supported.
        A right or top axis that is in use (a ``yaxis='y2'`` series, a y2 or
        x2 label or limit) is still drawn. Both limits need to include 0:
        a log axis cannot be drawn this way, and an axis whose crossing
        point is outside the other's limits is not shown. ``savefig`` warns
        in both cases.
        """
        if not isinstance(on, (bool, np.bool_)):
            raise TypeError(f"set_math_mode(on={on!r}) must be True or False")
        self.math_mode = True if on else None
        return self

    @_cartesian_only
    def set_xscale(self, scale: str, axis: str = "x"):
        """Set x-axis scale.

        Parameters
        ----------
        scale : str
            Scale type: 'linear' or 'log'
        axis : str, optional
            Which axis: 'x' (bottom, default) or 'x2' (top)
        """
        if axis == "x2":
            self.x2scale = scale
        else:
            self.xscale = scale
        return self

    @_cartesian_only
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

    @_cartesian_only
    def set_xlim(self, xmin: Optional[float], xmax: Optional[float], axis: str = "x"):
        """Set x-axis limits.

        ``None`` puts that bound back on AUTO -- derived from the data at
        GLE-generation time -- which is what an editor's "auto" checkbox
        means and what a freshly created axes carries.

        Parameters
        ----------
        xmin, xmax : float or None
            Axis limits; ``None`` = auto.
        axis : str, optional
            Which axis: 'x' (bottom, default) or 'x2' (top)
        """
        if axis == "x2":
            self.x2min = xmin
            self.x2max = xmax
        else:
            self.xmin = xmin
            self.xmax = xmax
        return self

    @_cartesian_only
    def twiny(self) -> SecondaryXAxis:
        """Open the top x axis as its own data scale.

        The returned view plots against that scale (``xaxis='x2'``) and
        shares this axes' y axis. Limits, log, and the axis label set on
        the view are the top scale; they do not move the bottom one.

        GLE's top axis is the same graph, not a second subplot, so the
        view is not an entry of :attr:`Figure.axes_list`.
        """
        return SecondaryXAxis(self)

    @_cartesian_only
    def twinx(self, axes_class=None, *, delta_zorder=0.0, **kwargs) -> SecondaryYAxis:
        """Open the right-hand y axis as its own data scale.

        The returned view plots against that scale (``yaxis='y2'``) and
        shares this axes' x axis. Limits, log, the tick format and the axis
        label set on the view are the right scale; they do not move the
        left one.

        Parameters
        ----------
        axes_class, delta_zorder, **kwargs
            Accepted for matplotlib compatibility. GLE's right axis is part
            of this graph, not a new axes, so they have no effect and warn.

        Returns
        -------
        SecondaryYAxis
            A view of this axes bound to the right scale. It is not an entry
            of :attr:`Figure.axes_list`.
        """
        ignored = [
            name
            for name, given in (
                ("axes_class", axes_class is not None),
                ("delta_zorder", delta_zorder != 0.0),
            )
            if given
        ] + sorted(kwargs)
        if ignored:
            warn_external(
                f"twinx() ignores {', '.join(ignored)}: the right-hand scale is "
                "drawn on this graph, not on a new axes."
            )
        return SecondaryYAxis(self)

    @_cartesian_only
    def invert_xaxis(self):
        """Draw the x axis the other way round, as matplotlib does.

        Returns
        -------
        Axes
            ``self``.

        Notes
        -----
        gleplot inverts an axis by storing its limits in descending order
        (see :meth:`set_xlim`). An automatic limit is replaced by the end of
        the data plotted so far, so the limits are fixed from then on: data
        plotted afterwards does not widen the axis. Plot first, then invert.
        With nothing plotted, this warns and does nothing; call
        ``set_xlim(right, left)`` instead. GLE picks the automatic range of
        the :meth:`twiny` and :meth:`twinx` scales itself, so inverting one
        of those needs its limits set first. GLE cannot invert a log axis, so
        ``savefig`` warns and draws one the usual way round.
        """
        return self._invert_axis("x", "invert_xaxis")

    @_cartesian_only
    def invert_yaxis(self):
        """Draw the y axis the other way round. See :meth:`invert_xaxis`.

        Returns
        -------
        Axes
            ``self``.
        """
        return self._invert_axis("y", "invert_yaxis")

    def _invert_axis(self, which: str, method: str):
        """Swap ``which``'s limits, filling an automatic one from the data."""
        lo = getattr(self, f"{which}min")
        hi = getattr(self, f"{which}max")
        if (lo is None or hi is None) and which in ("x2", "y2"):
            # The figure autoscales only x and y at save time; GLE picks the
            # x2/y2 range itself, so there is no range here to fill from.
            setter = "set_xlim" if which == "x2" else "set_ylim"
            view = "twiny" if which == "x2" else "twinx"
            warn_external(
                f"{method}() did nothing: GLE chooses the automatic range of "
                f"the {which} axis, so there are no limits to swap. Call "
                f"{setter}() on the {view}() view with the limits in "
                "descending order."
            )
            return self
        if lo is None or hi is None:
            data_lim = (
                self.figure._get_data_xlim
                if which == "x"
                else self.figure._get_data_ylim
            )
            data_lo, data_hi = data_lim(
                self, positive_only=getattr(self, f"{which}scale") == "log"
            )
            lo = data_lo if lo is None else lo
            hi = data_hi if hi is None else hi
        if lo is None or hi is None or lo == hi:
            setter = (
                "set_xlim(right, left)" if which == "x" else "set_ylim(top, bottom)"
            )
            warn_external(
                f"{method}() did nothing: the {which} axis has automatic limits "
                "and no data range to invert. Plot the data first, or call "
                f"{setter}."
            )
            return self
        setattr(self, f"{which}min", hi)
        setattr(self, f"{which}max", lo)
        return self

    @_cartesian_only
    def semilogx(self, *args, **kwargs):
        """:meth:`plot` with a log x axis.

        Parameters
        ----------
        *args, **kwargs
            Passed to :meth:`plot`. matplotlib's ``base``, ``subs`` and
            ``nonpositive`` are accepted; GLE draws base-10 decades with its
            own minor ticks, so any other value warns and has no effect.

        Returns
        -------
        Axes
            What :meth:`plot` returns.
        """
        self._check_log_kwargs("semilogx", kwargs)
        result = self.plot(*args, _caller="semilogx", **kwargs)
        self.set_xscale("log")
        return result

    @_cartesian_only
    def semilogy(self, *args, **kwargs):
        """:meth:`plot` with a log y axis. See :meth:`semilogx`.

        Returns
        -------
        Axes
            What :meth:`plot` returns.
        """
        self._check_log_kwargs("semilogy", kwargs)
        result = self.plot(*args, _caller="semilogy", **kwargs)
        self.set_yscale("log")
        return result

    @_cartesian_only
    def loglog(self, *args, **kwargs):
        """:meth:`plot` with log x and y axes. See :meth:`semilogx`.

        Returns
        -------
        Axes
            What :meth:`plot` returns.
        """
        self._check_log_kwargs("loglog", kwargs)
        result = self.plot(*args, _caller="loglog", **kwargs)
        self.set_xscale("log")
        self.set_yscale("log")
        return result

    @staticmethod
    def _check_log_kwargs(method: str, kwargs: Dict[str, Any]) -> None:
        """Pop matplotlib's log-scale keywords, warning on what GLE cannot do."""
        base = kwargs.pop("base", 10)
        ignored = [
            f"{name}={kwargs.pop(name)!r}"
            for name in ("subs", "nonpositive")
            if name in kwargs
        ]
        if base != 10:
            ignored.insert(0, f"base={base!r}")
        if ignored:
            warn_external(
                f"{method}() ignores {', '.join(ignored)}: GLE draws a log axis "
                "in base-10 decades with its own minor ticks, and cannot plot "
                "values <= 0 on it."
            )

    def set_ylim(self, ymin: Optional[float], ymax: Optional[float], axis: str = "y"):
        """Set y-axis limits.

        Parameters
        ----------
        ymin, ymax : float or None
            Axis limits; ``None`` = auto (see :meth:`set_xlim`).
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)

        Notes
        -----
        On a polar axes these are the radial limits: ``ymin`` must be 0 or
        ``None``, and ``ymax``, the outer ring, positive or ``None``.
        """
        if self._polar:
            if axis != "y":
                raise ValueError(
                    f"set_ylim(axis={axis!r}) is not supported on a polar axes; "
                    "use axis='y'."
                )
            if ymin not in (None, 0):
                raise ValueError(
                    f"set_ylim(ymin={ymin!r}) is not supported on a polar axes: "
                    "the radial axis starts at 0. Pass 0 or None."
                )
            if ymax is not None and not ymax > 0:
                raise ValueError(
                    f"set_ylim(ymax={ymax!r}) on a polar axes must be positive."
                )
        if axis == "y2":
            self.y2min = ymin
            self.y2max = ymax
        else:
            self.ymin = ymin
            self.ymax = ymax
        return self

    @_cartesian_only
    def set_xticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks: Optional[float] = None,
        dsubticks: Optional[float] = None,
        nticks: Optional[int] = None,
        ftick: Optional[float] = None,
        shift: Optional[float] = None,
        symticks: Optional[bool] = None,
        noticks: Optional[Sequence[float]] = None,
        nsubticks: Optional[int] = None,
        loglabels: Optional[str] = None,
        nofirst: Optional[bool] = None,
        nolast: Optional[bool] = None,
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
        nticks : int, optional
            Number of major ticks (GLE ``nticks``).
        ftick : float, optional
            Position of the first major tick (GLE ``ftick``); the others
            follow at the tick interval.
        shift : float, optional
            Move the tick labels along the axis by this many cm (GLE
            ``shift``), to label the space between two ticks.
        symticks : bool, optional
            Draw the ticks both inside and outside the frame (GLE
            ``symticks``). ``False`` goes back to inside only.
        noticks : sequence of float, optional
            Positions at which no tick is drawn (GLE ``xnoticks``). An empty
            sequence clears them.
        nsubticks : int, optional
            Number of minor ticks between two major ticks (GLE
            ``nsubticks``). ``dsubticks`` wins when both are set.
        loglabels : {'off', 'l1', 'l25', 'l25b', 'n1'}, optional
            Which sub-decades of a log axis get a label (GLE ``xlabels
            log``): ``'off'`` labels the decades only, ``'l1'`` adds 1 to 9,
            ``'l25'`` adds 2 and 5, ``'l25b'`` is ``'l25'`` with a 1 at each
            decade, and ``'n1'`` labels 1 to 9 without the exponent.
        nofirst, nolast : bool, optional
            Leave out the first or last tick label (GLE ``nofirst`` /
            ``nolast``), so the labels of two touching plots do not overlap.
            ``False`` puts the label back.

        Returns
        -------
        self

        Raises
        ------
        ValueError
            If ``nticks`` or ``nsubticks`` is not a positive whole number, or
            ``loglabels`` is not one of the modes above.

        Notes
        -----
        The keywords from ``dticks`` on are gleplot's, not matplotlib's.
        ``None`` leaves each setting as it is. GLE copies the x settings
        onto the top axis.
        """
        if ticks is not None:
            self.xplaces = [float(t) for t in ticks]
        if labels is not None:
            # Tick labels are user-supplied display text like any other, so
            # they get the same mathtext translation / literal escaping.
            self.xnames = [str(self._text(str(lbl))) for lbl in labels]
        if dticks is not None:
            self.xdticks = float(dticks)
        if dsubticks is not None:
            self.xdsubticks = float(dsubticks)
        self._set_tick_options(
            "x", "set_xticks", nticks, ftick, shift, symticks, noticks
        )
        self._set_minor_and_edge_labels(
            "x", "set_xticks", nsubticks, loglabels, nofirst, nolast
        )
        return self

    @_cartesian_only
    def set_yticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks: Optional[float] = None,
        dsubticks: Optional[float] = None,
        nticks: Optional[int] = None,
        ftick: Optional[float] = None,
        shift: Optional[float] = None,
        symticks: Optional[bool] = None,
        noticks: Optional[Sequence[float]] = None,
        nsubticks: Optional[int] = None,
        loglabels: Optional[str] = None,
        nofirst: Optional[bool] = None,
        nolast: Optional[bool] = None,
    ):
        """Control y-axis tick placement. See :meth:`set_xticks`."""
        if ticks is not None:
            self.yplaces = [float(t) for t in ticks]
        if labels is not None:
            self.ynames = [str(self._text(str(lbl))) for lbl in labels]
        if dticks is not None:
            self.ydticks = float(dticks)
        if dsubticks is not None:
            self.ydsubticks = float(dsubticks)
        self._set_tick_options(
            "y", "set_yticks", nticks, ftick, shift, symticks, noticks
        )
        self._set_minor_and_edge_labels(
            "y", "set_yticks", nsubticks, loglabels, nofirst, nolast
        )
        return self

    @_cartesian_only
    def set_xticklabels(self, labels, *, minor=False, fontdict=None, **kwargs):
        """Label the x ticks placed by :meth:`set_xticks` (GLE ``xnames``).

        Parameters
        ----------
        labels : sequence of str
            One label per tick position.
        minor : bool
            GLE does not label minor ticks: ``True`` warns and does nothing.
        fontdict, **kwargs
            matplotlib text properties. They warn and have no effect; style
            tick labels with :meth:`tick_params` or :meth:`set_tick_format`.

        Returns
        -------
        Axes
            ``self``.

        Raises
        ------
        ValueError
            If the number of labels is not the number of tick positions.
        """
        return self._set_ticklabels("x", labels, minor, fontdict, kwargs)

    @_cartesian_only
    def set_yticklabels(self, labels, *, minor=False, fontdict=None, **kwargs):
        """Label the y ticks placed by :meth:`set_yticks`. See
        :meth:`set_xticklabels`.

        Returns
        -------
        Axes
            ``self``.
        """
        return self._set_ticklabels("y", labels, minor, fontdict, kwargs)

    def _set_ticklabels(self, prefix, labels, minor, fontdict, kwargs):
        method = f"set_{prefix}ticklabels"
        if minor:
            warn_external(
                f"{method}(minor=True) did nothing: GLE does not label minor " "ticks."
            )
            return self
        labels = list(labels)
        places = getattr(self, f"{prefix}places")
        if places is None or len(places) != len(labels):
            have = "no fixed ticks" if places is None else f"{len(places)} ticks"
            raise ValueError(
                f"{method}() got {len(labels)} labels for {have}; it needs one "
                f"label per tick position. Call set_{prefix}ticks(ticks, labels) "
                "to set both."
            )
        ignored = (["fontdict"] if fontdict is not None else []) + sorted(kwargs)
        if ignored:
            warn_external(
                f"{method}() ignores {', '.join(ignored)}; style tick labels "
                "with tick_params() or set_tick_format()."
            )
        setter = self.set_xticks if prefix == "x" else self.set_yticks
        return setter(labels=labels)

    @_cartesian_only
    def axis(self, arg=None, /, *, emit=True, **kwargs):
        """Get or set the axis limits, or hide the axes, as matplotlib does.

        Parameters
        ----------
        arg : None, bool, str or sequence of 4 floats
            ``None`` only reads the limits. ``'off'`` or ``False`` calls
            :meth:`set_axis_off`, ``'on'`` or ``True`` :meth:`set_axis_on`.
            ``'tight'`` and ``'auto'`` put x and y back on automatic limits,
            which gleplot fits to the data. ``'equal'``, ``'scaled'``,
            ``'image'`` and ``'square'`` warn and have no effect; use
            :meth:`set_aspect` instead. ``[xmin, xmax, ymin, ymax]`` sets the
            limits.
        emit : bool
            Accepted for matplotlib compatibility; ``False`` warns, since
            gleplot has no limit-change callbacks.
        **kwargs
            ``xmin``, ``xmax``, ``ymin``, ``ymax``: set just those limits.

        Returns
        -------
        tuple
            ``(xmin, xmax, ymin, ymax)``; ``None`` is an automatic limit.

        Raises
        ------
        ValueError
            On an unknown string option.
        TypeError
            If ``arg`` is a sequence of the wrong length, or on any other
            keyword, or limit keywords passed together with ``arg``.
        """
        unknown = sorted(set(kwargs) - {"xmin", "xmax", "ymin", "ymax"})
        if unknown or (kwargs and arg is not None):
            raise TypeError(
                f"axis() got an unexpected keyword argument "
                f"{(unknown or sorted(kwargs))[0]!r}; it takes xmin, xmax, ymin "
                "and ymax, and only when no positional argument is given."
            )
        if not emit:
            warn_external(
                "axis(emit=False) has no effect: gleplot has no limit-change "
                "callbacks to silence."
            )
        if isinstance(arg, (bool, np.bool_)):
            arg = "on" if arg else "off"
        if isinstance(arg, str):
            option = arg.lower()
            if option == "on":
                self.set_axis_on()
            elif option == "off":
                self.set_axis_off()
            elif option in ("tight", "auto"):
                self.set_xlim(None, None)
                self.set_ylim(None, None)
            elif option in ("equal", "scaled", "image", "square"):
                warn_external(
                    f"axis({arg!r}) has no effect. Use ax.set_aspect('equal') "
                    "to give a unit the same length on both axes."
                )
            else:
                raise ValueError(
                    f"axis({arg!r}) is not a known option; use 'on', 'off', "
                    "'tight', 'auto', 'equal', 'scaled', 'image' or 'square'."
                )
            return (*self.get_xlim(), *self.get_ylim())
        if arg is not None:
            arg = list(arg)
            if len(arg) != 4:
                raise TypeError(
                    "axis() takes [xmin, xmax, ymin, ymax] as its first "
                    f"argument; got {arg!r}."
                )
            kwargs = dict(zip(("xmin", "xmax", "ymin", "ymax"), arg))
        for name in ("x", "y"):
            lo = kwargs.get(f"{name}min")
            hi = kwargs.get(f"{name}max")
            # matplotlib leaves a limit passed as None where it was.
            if lo is not None or hi is not None:
                old_lo, old_hi = getattr(self, f"get_{name}lim")()
                getattr(self, f"set_{name}lim")(
                    old_lo if lo is None else lo, old_hi if hi is None else hi
                )
        return (*self.get_xlim(), *self.get_ylim())

    @_cartesian_only
    def set_aspect(self, aspect, adjustable=None, anchor=None, share=False):
        """Fix the ratio of a y unit's length to an x unit's, as matplotlib does.

        Parameters
        ----------
        aspect : {'auto', 'equal'} or float
            ``'auto'`` lets the frame fill its place. ``'equal'`` gives a
            unit the same length on both axes, and a number ``a`` makes a y
            unit ``a`` times as long as an x unit. On a log axis a unit is
            a decade.
        adjustable : {None, 'box', 'datalim'}, optional
            gleplot always adjusts the box; ``'datalim'`` warns.
        anchor : None, str or (float, float), optional
            gleplot always centres the box in its place; anything but
            ``None`` or ``'C'`` warns.
        share : bool, default: False
            ``True`` warns: the aspect is set on this axes only.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If ``aspect`` is not ``'auto'``, ``'equal'`` or a finite positive
            number, or ``adjustable`` or ``anchor`` is not one of matplotlib's
            values.
        TypeError
            If ``aspect`` is neither a string nor a number.
        NotImplementedError
            On a polar axes or a broken-axis segment.

        Notes
        -----
        When the figure is saved, the frame is shrunk about its centre
        until its sides have the ratio the axis limits and the aspect call
        for. The limits are those the figure is saved with; with no data
        to set them, the aspect warns and is skipped.

        The frame is written into the ``.gle`` script as its rectangle, so
        a figure opened again with :func:`gleplot.open_gle` keeps that
        rectangle but not the aspect: changing its limits afterwards does
        not reshape the frame.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig, ax = glp.subplots()
        >>> ax.set_aspect("equal")
        """
        if self._break_owner is not None:
            raise NotImplementedError(
                "set_aspect() is not supported on a broken-axis segment: the "
                "segments share one height. Choose figsize and the limits "
                "instead."
            )
        if isinstance(aspect, str) and aspect in ("auto", "equal"):
            value: Optional[float] = None if aspect == "auto" else 1.0
        else:
            try:
                value = float(aspect)
            except TypeError:
                raise TypeError(
                    f"set_aspect(aspect={aspect!r}) must be 'auto', 'equal' or "
                    "a finite positive number."
                ) from None
            except ValueError:
                value = float("nan")
            if not (np.isfinite(value) and value > 0):
                raise ValueError(
                    f"set_aspect(aspect={aspect!r}) must be 'auto', 'equal' or "
                    "a finite positive number."
                )
        if adjustable not in (None, "box", "datalim"):
            raise ValueError(
                f"set_aspect(adjustable={adjustable!r}) is not supported; use "
                "None, 'box' or 'datalim'."
            )
        if isinstance(anchor, str):
            if anchor not in ("C", "SW", "S", "SE", "E", "NE", "N", "NW", "W"):
                raise ValueError(
                    f"set_aspect(anchor={anchor!r}) must be one of 'C', 'SW', "
                    "'S', 'SE', 'E', 'NE', 'N', 'NW', 'W' or an (x, y) pair."
                )
            centred = anchor == "C"
        else:
            centred = anchor is None
        if adjustable == "datalim":
            warn_external(
                "set_aspect(adjustable='datalim') is not supported: gleplot "
                "resizes the box instead. Set the limits with set_xlim and "
                "set_ylim to choose them yourself."
            )
        if not centred:
            warn_external(
                f"set_aspect(anchor={anchor!r}) is not supported: gleplot "
                "centres the resized box in its place."
            )
        if share:
            warn_external(
                "set_aspect(share=True) is not supported: the aspect is set on "
                "this axes only. Call set_aspect on each axes."
            )
        self._aspect = value

    def get_aspect(self):
        """The aspect :meth:`set_aspect` set: ``'auto'`` or a float.

        ``'equal'`` reads back as ``1.0``, and a polar axes, whose units are
        always equal, as ``1.0``.
        """
        if self._polar:
            return 1.0
        return "auto" if self._aspect is None else self._aspect

    @_cartesian_only
    def set_axis_off(self):
        """Hide the axis lines, ticks and tick labels.

        The plotted data, the title and the legend stay. Undo with
        :meth:`set_axis_on`.

        Returns
        -------
        Axes
            ``self``.

        Notes
        -----
        Unlike matplotlib, the axis labels stay: a hidden label would not be
        written to the ``.gle`` file, so :func:`open_gle` could not bring it
        back. This warns when an axis label is set; remove it with
        ``set_xlabel('')`` / ``set_ylabel('')``.
        """
        self._frame_off = True
        self._show_xticks = self._show_yticks = False
        if any(
            (self.xlabel_text, self.ylabel_text, self.x2label_text, self.y2label_text)
        ):
            warn_external(
                "set_axis_off() keeps the axis labels; remove them with "
                "set_xlabel('') and set_ylabel('')."
            )
        return self

    @_cartesian_only
    def set_axis_on(self):
        """Show the axes again after :meth:`set_axis_off`.

        Tick labels come back except where ``sharex`` or ``sharey`` hides
        them on an inner subplot.

        Returns
        -------
        Axes
            ``self``.
        """
        self._frame_off = False
        # The sharing rule is the one source of the tick-label visibility,
        # but it also resets flags set_axis_off never touched (axis titles,
        # nofirst/nolast); only the two tick-label flags are taken from it.
        kept = {
            name: getattr(self, name)
            for name in (
                "_show_xlabel",
                "_show_ylabel",
                "_remove_first_xtick",
                "_remove_last_xtick",
                "_remove_first_ytick",
                "_remove_last_ytick",
            )
        }
        self.figure._apply_shared_axes_flags(self)
        for name, value in kept.items():
            setattr(self, name, value)
        return self

    def _set_tick_options(
        self, prefix, method, nticks, ftick, shift, symticks, noticks
    ) -> None:
        """The GLE-only placement keywords shared by set_xticks/set_yticks."""
        if nticks is not None:
            setattr(self, f"{prefix}nticks", _count(nticks, f"{method}(nticks"))
        if ftick is not None:
            setattr(
                self, f"{prefix}ftick", _finite_float(ftick, f"{method}(ftick=...)")
            )
        if shift is not None:
            setattr(
                self, f"{prefix}shift", _finite_float(shift, f"{method}(shift=...)")
            )
        if symticks is not None:
            # GLE's default is ticks inside only, which None already writes.
            setattr(self, f"{prefix}symticks", True if symticks else None)
        if noticks is not None:
            positions = [_finite_float(v, f"{method}(noticks=...)") for v in noticks]
            setattr(self, f"{prefix}noticks", positions or None)

    def _set_minor_and_edge_labels(
        self, prefix, method, nsubticks, loglabels, nofirst, nolast
    ) -> None:
        """``nsubticks``, ``loglabels``, ``nofirst`` and ``nolast``."""
        if nsubticks is not None:
            setattr(
                self, f"{prefix}nsubticks", _count(nsubticks, f"{method}(nsubticks")
            )
        if loglabels is not None:
            if loglabels not in LOG_LABEL_MODES:
                raise ValueError(
                    f"{method}(loglabels={loglabels!r}) must be one of "
                    + ", ".join(repr(mode) for mode in LOG_LABEL_MODES)
                )
            setattr(self, f"{prefix}loglabels", loglabels)
        if nofirst is not None:
            setattr(self, f"_remove_first_{prefix}tick", bool(nofirst))
        if nolast is not None:
            setattr(self, f"_remove_last_{prefix}tick", bool(nolast))

    @_cartesian_only
    def tick_params(self, axis: str = "both", **kwargs):
        """Change the appearance of the tick marks.

        Parameters
        ----------
        axis : {'x', 'y', 'both'}
            Which axis. GLE draws the x settings on the top axis too, and
            the y settings on the right one.
        **kwargs
            ``which`` ({'major', 'minor', 'both'}, default ``'major'``),
            ``reset`` (bool: go back to GLE's default ticks first),
            ``direction`` ({'in', 'out', 'inout'}), ``length`` and ``width``
            (points), and ``color``. Any other matplotlib keyword warns and
            is ignored.

        Returns
        -------
        Axes
            ``self``.

        Raises
        ------
        ValueError
            On an unknown ``axis``, ``which`` or ``direction``, or a
            negative ``length`` or ``width``.

        Notes
        -----
        GLE writes these as ``xticks length L lwidth W color C`` and
        ``xsubticks ...``. GLE's ticks point into the frame unless told
        otherwise, and pointing them out needs a length: ``direction='out'``
        with no length uses matplotlib's default (3.5 points for major
        ticks, 2 for minor). Minor ticks with no colour of their own are
        drawn in the major ticks' colour.

        ``'inout'`` is GLE's ``symticks``, which is one setting for the
        major and minor ticks of an axis, so it is not taken with
        ``which='minor'``. ``'in'`` or ``'out'`` for the major ticks turns
        it off again, and so does ``reset``.

        An axis with a grid draws the grid lines in place of its ticks, so
        these settings are not written for it; :meth:`grid` styles them.
        """
        if axis not in ("x", "y", "both"):
            raise ValueError(f"tick_params(axis={axis!r}) must be 'x', 'y' or 'both'")
        which = kwargs.pop("which", "major")
        if which not in _TICK_KINDS:
            raise ValueError(
                f"tick_params(which={which!r}) must be 'major', 'minor' or 'both'"
            )
        reset = kwargs.pop("reset", False)
        direction = kwargs.pop("direction", None)
        if direction is not None and direction not in ("in", "out", "inout"):
            raise ValueError(
                f"tick_params(direction={direction!r}) must be 'in', 'out' "
                "or 'inout'"
            )
        if direction == "inout" and which == "minor":
            warn_external(
                "tick_params(direction='inout') draws the major and minor "
                "ticks of an axis on both sides together in GLE; ignored for "
                "which='minor'. Use which='both'.",
            )
            direction = None
        values: Dict[str, Any] = {}
        for name in ("length", "width"):
            value = kwargs.pop(name, None)
            if value is not None:
                size = _finite_float(value, f"tick_params({name}=...)")
                if size < 0:
                    raise ValueError(
                        f"tick_params({name}={value!r}) must be a non-negative "
                        "size in points"
                    )
                values[name] = size
        color = kwargs.pop("color", None)
        if color is not None:
            values["color"] = rgb_to_gle(color)
        if direction in ("in", "out"):
            values["direction"] = direction
        if kwargs:
            warn_external(
                "tick_params(): "
                + ", ".join(sorted(kwargs))
                + " not supported in gleplot and ignored. Tick marks take "
                "direction, length, width and color; tick labels are styled "
                "through set_tick_format() and the Axes xticklabel_* / "
                "yticklabel_* attributes.",
            )
        for prefix in ("x", "y") if axis == "both" else (axis,):
            for kind in _TICK_KINDS[which]:
                if reset:
                    for name in ("length", "width", "color", "direction"):
                        setattr(self, f"{prefix}{kind}_{name}", None)
                for name, value in values.items():
                    setattr(self, f"{prefix}{kind}_{name}", value)
            if direction == "inout":
                setattr(self, f"{prefix}symticks", True)
            elif which != "minor" and (reset or direction is not None):
                setattr(self, f"{prefix}symticks", None)
        return self

    @_cartesian_only
    def minorticks_on(self):
        """Draw minor ticks on both axes (GLE ``xsubticks on``)."""
        self.xminorticks = True
        self.yminorticks = True

    @_cartesian_only
    def minorticks_off(self):
        """Hide the minor ticks of both axes (GLE ``xsubticks off``)."""
        self.xminorticks = False
        self.yminorticks = False

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
            Number of columns. Emitted as GLE ``key separator`` between
            entries, packed like matplotlib (column-major, the first
            columns one entry longer). ``ncols`` wins when both are passed.
            An integer less than 1 raises ``ValueError``. A count larger
            than the number of entries collapses to one entry per column.
        compact : bool, optional
            GLE's ``compact``: draw the line and the marker as one swatch.
            Default ``False`` omits the token. Not a matplotlib keyword.
        facecolor : color, optional
            Legend-box fill, emitted as GLE ``background``. ``boxcolor`` is
            not this: in GLE it strokes the fill swatch, and it warns.
        bbox_to_anchor : tuple of float, optional
            ``(x, y)`` or ``(x, y, width, height)`` in axes fractions, as in
            matplotlib: the ``loc`` corner of the legend sits on that point,
            or on that corner of the box. ``(1.02, 1)`` with
            ``loc='upper left'`` puts the legend beside the graph. Emitted as
            GLE ``justify`` and ``absolute`` in a ``begin key`` block after
            the graph, measured against the graph GLE drew. Replaces
            ``offset``. Like ``loc``, it applies to this call only: a call
            without it puts the legend back inside the graph. The page does
            not grow to fit a legend placed outside the graph.
        borderpad, handlelength, handletextpad, columnspacing : float, optional
            Space inside the box, line-swatch length, gap between swatch and
            text, and gap between columns, in units of the legend font size
            as in matplotlib. Emitted as GLE ``margins``, ``llen``, ``dist``
            and ``coldist`` in cm. GLE's ``dist`` is also the gap between a
            marker and a line swatch. ``None`` restores GLE's own spacing.
        labelcolor : color, optional
            One colour for the text of every entry, emitted as GLE
            ``textcolor`` on each entry of a ``begin key`` block after the
            graph. matplotlib's ``'linecolor'``, ``'markerfacecolor'`` and
            ``'markeredgecolor'`` and a list of colours warn and are ignored.
        **kwargs
            Any other matplotlib legend keyword (``title``, ``labelspacing``,
            ...) has no GLE ``key`` equivalent and warns rather than being
            silently dropped.

        Returns
        -------
        self
        """
        self.legend_on = True

        # matplotlib's first positional argument may be a handles/labels
        # sequence. gleplot takes legend text from each series' ``label=``,
        # so an explicit sequence cannot be honoured -- say so.
        if loc is not None and not isinstance(loc, str):
            warn_external(
                "legend(): explicit handles/labels are not supported; legend "
                "text comes from each series' label= argument. The positional "
                "argument was ignored.",
            )
            loc = "best"

        self.legend_pos = self._resolve_legend_loc(loc)

        if "fontsize" in kwargs:
            fontsize = kwargs.pop("fontsize")
            self.legend_fontsize = (
                None if fontsize is None else _resolve_fontsize(self._style(), fontsize)
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

        # matplotlib gives ``ncols`` precedence over ``ncol`` when both
        # are passed (legend.py pops ncols second). Same order here.
        for name in ("ncol", "ncols"):
            if name in kwargs:
                ncol = kwargs.pop(name)
                self.legend_ncol = (
                    1 if ncol is None else self._resolve_legend_ncol(ncol)
                )

        if "compact" in kwargs:
            compact = kwargs.pop("compact")
            self.legend_compact = False if compact is None else bool(compact)

        if "facecolor" in kwargs:
            facecolor = kwargs.pop("facecolor")
            self.legend_facecolor = None if facecolor is None else rgb_to_gle(facecolor)

        for name in LEGEND_SPACING_TO_KEY:
            if name in kwargs:
                value = kwargs.pop(name)
                if value is None:
                    self.legend_spacing.pop(name, None)
                else:
                    self.legend_spacing[name] = _finite_float(
                        value, f"legend({name}=...)"
                    )

        # The anchor is resolved against this call's ``loc``, which every
        # call sets, so it is set (or cleared) by every call too: as in
        # matplotlib, where each call builds a new legend.
        anchor = kwargs.pop("bbox_to_anchor", None)
        self.legend_bbox_to_anchor = (
            None
            if anchor is None
            else self._resolve_legend_anchor(anchor, self.legend_pos)
        )
        if self.legend_bbox_to_anchor is not None and self.legend_offset is not None:
            warn_external(
                "legend(offset=...) has no effect while bbox_to_anchor is set: "
                "the legend is placed at the anchor. Move it with "
                "bbox_to_anchor instead.",
            )

        if "labelcolor" in kwargs:
            self.legend_labelcolor = self._resolve_legend_labelcolor(
                kwargs.pop("labelcolor"), self.legend_labelcolor
            )

        if "boxcolor" in kwargs:
            kwargs.pop("boxcolor")
            warn_external(
                "legend(boxcolor=...) was ignored. In GLE, boxcolor strokes "
                "the fill swatch; the legend-box fill is `background`, which "
                "gleplot takes from legend(facecolor=...).",
            )

        for name in sorted(kwargs):
            warn_external(
                f"legend({name}=...) is not supported and was ignored: GLE's "
                "key command understands loc, bbox_to_anchor, fontsize, "
                "frameon, offset, ncol, compact, facecolor, labelcolor, "
                "borderpad, handlelength, handletextpad and columnspacing.",
            )

        return self

    @staticmethod
    def _resolve_legend_anchor(
        anchor, pos: str, coords: str = "axes"
    ) -> Optional[Tuple[float, float]]:
        """The ``coords``-fraction point a ``bbox_to_anchor`` puts corner ``pos`` on.

        ``coords`` is ``'axes'`` for ``Axes.legend``, ``'figure'`` for
        ``Figure.legend``, and names the fractions in messages.

        A 4-tuple is matplotlib's box: the legend's ``pos`` corner goes on
        the same corner of the box (its centre for a ``center`` side).
        """
        what = "legend(bbox_to_anchor=...)"
        if hasattr(anchor, "bounds") and not isinstance(anchor, (tuple, list)):
            # A matplotlib Bbox is in display coordinates unless a
            # bbox_transform says otherwise; gleplot has neither.
            warn_external(
                f"{what} was ignored: a Bbox object is not supported. Pass "
                f"(x, y) or (x, y, width, height) in {coords} fractions.",
            )
            return None
        try:
            if isinstance(anchor, str):
                raise TypeError
            values = [_finite_float(v, what) for v in anchor]
        except TypeError:
            values = []
        if len(values) not in (2, 4):
            raise ValueError(
                f"{what} expects (x, y) or (x, y, width, height) in {coords} "
                f"fractions, got {anchor!r}"
            )
        x, y = values[0], values[1]
        if len(values) == 4:
            width, height = values[2], values[3]
            words = pos.split()
            x += width * (0.0 if "left" in words else 1.0 if "right" in words else 0.5)
            y += height * (1.0 if "top" in words else 0.0 if "bottom" in words else 0.5)
        return (x, y)

    @staticmethod
    def _resolve_legend_labelcolor(labelcolor, current: Optional[str]):
        """A GLE colour for ``legend(labelcolor=...)``, or ``current`` if ignored."""
        if labelcolor is None:
            return None
        per_entry = isinstance(labelcolor, str) and labelcolor.strip().lower() in (
            "linecolor",
            "markerfacecolor",
            "mfc",
            "markeredgecolor",
            "mec",
        )
        # An RGB(A) tuple is one colour; any other sequence is one per entry.
        is_list = isinstance(labelcolor, (list, tuple, np.ndarray)) and not (
            len(labelcolor) in (3, 4) and all(isinstance(v, Real) for v in labelcolor)
        )
        if per_entry or is_list:
            warn_external(
                f"legend(labelcolor={labelcolor!r}) was ignored: gleplot gives "
                "every legend entry the same text colour. Pass one colour, "
                "e.g. labelcolor='gray'.",
            )
            return current
        return rgb_to_gle(labelcolor)

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
        warn_external(
            f"legend(loc={loc!r}) is not a recognized matplotlib location or "
            "GLE key position; using 'upper right'.",
        )
        return "top right"

    @staticmethod
    def _resolve_legend_ncol(ncol) -> int:
        """An integer column count of at least 1.

        ``bool`` is rejected: it is an ``int`` subclass, and ``True`` would
        otherwise silently become one column.
        """
        if isinstance(ncol, bool) or not isinstance(ncol, (int, float)):
            raise ValueError(f"legend(ncol=...) must be an integer >= 1, got {ncol!r}")
        try:
            as_int = int(ncol)
            as_float = float(ncol)
        except (TypeError, ValueError):
            raise ValueError(
                f"legend(ncol=...) must be an integer >= 1, got {ncol!r}"
            ) from None
        if as_int < 1 or as_float != as_int:
            raise ValueError(f"legend(ncol=...) must be an integer >= 1, got {ncol!r}")
        return as_int

    def grid(
        self,
        visible: Optional[bool] = None,
        which: str = "major",
        axis: str = "both",
        color: Optional[str] = None,
        linestyle: Optional[Union[str, int]] = None,
        linewidth: Optional[float] = None,
        **kwargs,
    ):
        """Turn the graph grid on or off, matplotlib-style.

        GLE has no separate grid object: ``xaxis grid`` makes that axis'
        ticks long enough to reach the opposite side, and the resulting lines
        ARE the grid (manual, "Graph Commands": ``xaxis grid``). Three
        consequences the model is honest about:

        * A grid always covers the **main ticks**. ``which='minor'`` alone is
          not expressible; it is normalized to ``'both'`` with a warning
          rather than silently dropped.
        * ``which='both'`` adds ``xsubticks on``, GLE's "grid lines at each
          subtick" mode.
        * Grid style is tick style (``xticks lstyle/lwidth/color``), so it
          also restyles the ticks of that axis.

        Parameters
        ----------
        visible : bool, optional
            True/False to switch the grid on/off. ``None`` (the default)
            means "on" when any style argument is given, and otherwise
            TOGGLES the targeted axes, as matplotlib does.
        which : {'major', 'minor', 'both'}
            Which ticks carry grid lines. ``'minor'`` is normalized to
            ``'both'`` (see above).
        axis : {'both', 'x', 'y'}
            Which axis' grid to change. x2/y2 have no grid of their own --
            they are where the x/y grid lines end.
        color : str, optional
            Grid line colour (any :func:`gleplot.colors.rgb_to_gle` spelling).
        linestyle : str or int, optional
            matplotlib line style (``'-'``, ``'--'``, ``':'``, ``'-.'``) or a
            raw GLE ``lstyle`` number.
        linewidth : float, optional
            Grid line width in points.

        Returns
        -------
        Axes
            ``self``, so calls can be chained (gleplot has always returned
            this; matplotlib returns None).

        Raises
        ------
        ValueError
            On an unknown ``which``/``axis``/``linestyle`` value, a
            non-positive ``linewidth``, or an unsupported keyword argument.

        Notes
        -----
        On a polar axes the polar grid is always drawn in its own style:
        ``grid(True)`` does nothing, and hiding or styling it warns.

        Examples
        --------
        >>> ax.grid(True, which='both', linestyle=':', color='grey40')
        """
        if self._polar:
            styled = not (color is None and linestyle is None and linewidth is None)
            # Without True, matplotlib's grid() toggles, which here would hide.
            if visible is not True or styled or kwargs:
                warn_external(
                    "grid() cannot hide or restyle the grid of a polar axes; "
                    "it is always drawn, in grey. This call was ignored."
                )
            return self
        for key in kwargs:
            raise ValueError(
                f"grid() got an unsupported keyword argument {key!r}; "
                "supported style arguments are color, linestyle and linewidth"
            )
        if which not in ("major", "minor", "both"):
            raise ValueError(
                f"grid(which={which!r}) must be 'major', 'minor' or 'both'"
            )
        if axis not in ("both", "x", "y"):
            raise ValueError(f"grid(axis={axis!r}) must be 'both', 'x' or 'y'")

        targets = ("x", "y") if axis == "both" else (axis,)
        styled = color is not None or linestyle is not None or linewidth is not None

        mode = which
        if which == "minor":
            mode = "both"
            warn_external(
                "grid(which='minor'): GLE draws grid lines from the main "
                "ticks whenever the grid is on, so a minor-only grid is not "
                "expressible; using which='both'.",
            )

        lstyle = self._resolve_grid_lstyle(linestyle)
        if linewidth is not None and float(linewidth) <= 0:
            raise ValueError(f"grid(linewidth={linewidth!r}) must be positive")

        for name in targets:
            current = getattr(self, f"{name}grid")
            if visible is None:
                on = True if styled else current is None
            else:
                on = bool(visible)
            if not on:
                # which='minor' off = drop back to a main-tick grid; anything
                # else switches the grid off entirely.
                setattr(self, f"{name}grid", "major" if mode == "both" else None)
            elif mode == "major" and current == "both":
                pass  # enabling the major layer must not drop the subticks
            else:
                setattr(self, f"{name}grid", mode)
            if color is not None:
                setattr(self, f"{name}grid_color", rgb_to_gle(color))
            if lstyle is not None:
                setattr(self, f"{name}grid_lstyle", lstyle)
            if linewidth is not None:
                setattr(self, f"{name}grid_lwidth", float(linewidth))
        return self

    def _resolve_grid_lstyle(
        self, linestyle: Optional[Union[str, int]]
    ) -> Optional[int]:
        """matplotlib line style -> GLE ``lstyle`` number (ints pass through).

        Reads the figure's own :class:`~gleplot.config.GLEStyleConfig` so a
        custom ``line_style_dashed`` (etc.) applies to the grid exactly as it
        does to line series.
        """
        if linestyle is None:
            return None
        if isinstance(linestyle, bool):
            raise ValueError(f"grid(linestyle={linestyle!r}) is not a line style")
        if isinstance(linestyle, int):
            return int(linestyle)
        style = getattr(self.figure, "style", None) or GlobalConfig.get_style()
        mapping = {
            "-": style.line_style_solid,
            "solid": style.line_style_solid,
            "--": style.line_style_dashed,
            "dashed": style.line_style_dashed,
            ":": style.line_style_dotted,
            "dotted": style.line_style_dotted,
            "-.": style.line_style_dashdot,
            "dashdot": style.line_style_dashdot,
        }
        key = str(linestyle).strip().lower()
        if key not in mapping:
            raise ValueError(
                f"grid(linestyle={linestyle!r}) is not a matplotlib line style "
                f"({sorted(mapping)}) or a GLE lstyle number"
            )
        return int(mapping[key])

    @_cartesian_only
    def set_tick_format(self, fmt: Optional[str], axis: str = "both"):
        """Set the tick-label number format (GLE ``xaxis format "<fmt>"``).

        ``fmt`` is a GLE format string -- the same syntax as the ``format$()``
        function (manual, "Programming": ``format$``): a base format
        (``fix``, ``sci``, ``eng``, ``round``, ``percent``, ``frac``, ``pi``,
        ``dec``, ``hex``, ``bin``, ``append``) with its arguments, optionally
        followed by modifiers (``nozeroes``, ``sign``, ``pad``, ``prefix``,
        ``prepend``, ``min``, ``max``) and optionally several formats
        combined, e.g. ``"sci 2 10 min 1e2 fix 0"``.

        It is stored as a free-form string: GLE is the authority on the
        syntax and a friendly preset builder belongs in a GUI, not here.
        Validation is deliberately light -- non-empty, single-line, and
        starting with a keyword GLE knows -- so that format strings this
        version has never heard of still round-trip.

        Parameters
        ----------
        fmt : str or None
            The format string, or None to clear it (GLE's automatic
            labelling).
        axis : {'both', 'x', 'y', 'y2', 'x2'}
            Which axis to apply it to. ``'both'`` means x and y (not y2
            or x2, which are distinct axes with their own data ranges).

        Returns
        -------
        Axes
            ``self``.

        Raises
        ------
        ValueError
            On an unknown ``axis``, or a format string that is empty,
            multi-line, or does not begin with a GLE format keyword.

        Notes
        -----
        GLE's y2 and x2 tick labels are off unless ``y2labels on`` /
        ``x2labels on`` is given, so setting ``axis='y2'`` or ``axis='x2'``
        also turns them on at write time -- see
        :meth:`gleplot.writer.GLEWriter.add_axes`.
        """
        if axis not in ("both", "x", "y", "y2", "x2"):
            raise ValueError(
                "set_tick_format(axis={!r}) must be 'both', 'x', 'y', "
                "'y2' or 'x2'".format(axis)
            )
        value = None if fmt is None else validate_tick_format(fmt)
        for name in ("x", "y") if axis == "both" else (axis,):
            setattr(self, f"{name}format", value)
        return self

    def get_xlim(self, axis: str = "x") -> Tuple[Optional[float], Optional[float]]:
        """Get x-axis limits (``None`` = auto).

        Parameters
        ----------
        axis : str, optional
            Which axis: 'x' (bottom, default) or 'x2' (top)
        """
        if axis == "x2":
            return self.x2min, self.x2max
        return self.xmin, self.xmax

    def get_ylim(self, axis: str = "y") -> Tuple[Optional[float], Optional[float]]:
        """Get y-axis limits (``None`` = auto, see :meth:`get_xlim`).

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
            or self.hists
            or self.functions
            or self.fits
            or self.fills
            or self.errorbars
            or self.file_series
            or self.heatmaps
            or self.contours
            or self.reflines
            or self.spans
            or self.wedges
            or self.boxes
            or self.rugs
            or self.derived_series
            or self.images
        )

    def has_y2_plots(self) -> bool:
        """Check if axes has any plots using the y2 axis."""
        y2_capable: Sequence[Sequence[Series]] = (
            self.lines,
            self.scatters,
            self.errorbars,
            self.hists,
        )
        for plot_list in y2_capable:
            for plot_data in plot_list:
                if plot_data.get("yaxis") == "y2":
                    return True
        return False

    def has_x2_plots(self) -> bool:
        """Check if axes has any plots using the x2 axis."""
        x2_capable: Sequence[Sequence[Series]] = (
            self.lines,
            self.scatters,
            self.errorbars,
            self.hists,
            self.file_series,
        )
        for plot_list in x2_capable:
            for plot_data in plot_list:
                if plot_data.get("xaxis") == "x2":
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
            # Stable opaque identity (see __init__); a legacy dict saved
            # before this field existed simply has no key here, and
            # from_dict tolerates that by minting a fresh id on load.
            "axes_id": self.axes_id,
            "position": (
                [list(v) if isinstance(v, tuple) else v for v in self.position]
                if self.position is not None
                else None
            ),
            "xlabel_text": self.xlabel_text,
            "ylabel_text": self.ylabel_text,
            "y2label_text": self.y2label_text,
            "x2label_text": self.x2label_text,
            "title_text": self.title_text,
            "xscale": self.xscale,
            "yscale": self.yscale,
            "y2scale": self.y2scale,
            "x2scale": self.x2scale,
            "xmin": _to_jsonable(self.xmin),
            "xmax": _to_jsonable(self.xmax),
            "ymin": _to_jsonable(self.ymin),
            "ymax": _to_jsonable(self.ymax),
            "y2min": _to_jsonable(self.y2min),
            "y2max": _to_jsonable(self.y2max),
            "x2min": _to_jsonable(self.x2min),
            "x2max": _to_jsonable(self.x2max),
            "legend_on": self.legend_on,
            "legend_pos": self.legend_pos,
            "legend_fontsize": _to_jsonable(self.legend_fontsize),
            "legend_frameon": self.legend_frameon,
            "legend_offset": _to_jsonable(self.legend_offset),
            "legend_ncol": self.legend_ncol,
            "legend_compact": self.legend_compact,
            "legend_facecolor": self.legend_facecolor,
            "legend_spacing": dict(self.legend_spacing),
            "legend_bbox_to_anchor": _to_jsonable(self.legend_bbox_to_anchor),
            "legend_labelcolor": self.legend_labelcolor,
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
            "frame_off": self._frame_off,
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
        # Axes styling (see __init__ and _STYLING_KEYS). Every one of these
        # is None on a figure that never asked for it, and the writer emits
        # nothing for a None -- so adding them left existing output untouched.
        for key in _STYLING_KEYS:
            payload[key] = _to_jsonable(getattr(self, key))
        # Series lists, in registry order -- exactly where they appeared when
        # each was spelled out here by hand, so the key order (and therefore
        # the serialized bytes) is unchanged.
        for attr in SERIES_ATTRS:
            payload[attr] = [_to_jsonable(s) for s in getattr(self, attr)]
        payload["passthrough"] = list(self.passthrough)
        if self._polar:
            # Only on a polar axes, so every other payload is unchanged.
            payload["polar"] = True
        if self._aspect is not None:
            # Likewise only when set.
            payload["aspect"] = self._aspect
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

        Notes
        -----
        Each series is rebuilt as its :mod:`gleplot.series` class, whose
        ``ARRAY_FIELDS`` say which values are restored to ``float`` numpy
        arrays; optional error arrays that were ``None`` stay ``None``. All
        style keys, labels and the ``data_file`` names are restored
        verbatim, as are any keys the class does not declare (a project
        written by a newer gleplot still round-trips).
        """
        position = d.get("position")
        if position is not None:
            position = tuple(tuple(v) if isinstance(v, list) else v for v in position)
        ax = cls(figure, position)

        # Stable opaque identity (see __init__). ``cls(figure, position)``
        # already minted a fresh id; keep that fresh id unless the payload
        # carries a real one to restore -- this is the tolerant path for a
        # legacy dict saved before axes_id existed (missing key) or any
        # payload with a malformed/empty value.
        _axes_id = d.get("axes_id")
        if isinstance(_axes_id, str) and _axes_id:
            ax.axes_id = _axes_id

        ax.xlabel_text = d.get("xlabel_text", "")
        ax.ylabel_text = d.get("ylabel_text", "")
        ax.y2label_text = d.get("y2label_text", "")
        ax.x2label_text = d.get("x2label_text", "")
        ax.title_text = d.get("title_text", "")
        ax.xscale = d.get("xscale", "linear")
        ax.yscale = d.get("yscale", "linear")
        ax.y2scale = d.get("y2scale", "linear")
        ax.x2scale = d.get("x2scale", "linear")
        ax.xmin = d.get("xmin")
        ax.xmax = d.get("xmax")
        ax.ymin = d.get("ymin")
        ax.ymax = d.get("ymax")
        ax.y2min = d.get("y2min")
        ax.y2max = d.get("y2max")
        ax.x2min = d.get("x2min")
        ax.x2max = d.get("x2max")
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
        # Missing keys = a figure saved before swatches/columns: one column,
        # no compact token, no box fill. Those defaults emit nothing new.
        ax.legend_ncol = int(d.get("legend_ncol", 1) or 1)
        ax.legend_compact = bool(d.get("legend_compact", False))
        ax.legend_facecolor = d.get("legend_facecolor")
        ax.legend_spacing = {
            str(k): float(v) for k, v in (d.get("legend_spacing") or {}).items()
        }
        _anchor = d.get("legend_bbox_to_anchor")
        ax.legend_bbox_to_anchor = (
            None if _anchor is None else (float(_anchor[0]), float(_anchor[1]))
        )
        ax.legend_labelcolor = d.get("legend_labelcolor")

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
        # Axes styling. A missing key = a payload written before G10, whose
        # figure had no styling at all -- which is what None means, so the
        # plain ``.get`` default is also the correct migration.
        for _styling_key in _STYLING_KEYS:
            setattr(ax, _styling_key, d.get(_styling_key))
        ax._xaxis_off = d.get("xaxis_off", False)
        ax._yaxis_off = d.get("yaxis_off", False)
        ax._x2axis_off = d.get("x2axis_off", False)
        ax._y2axis_off = d.get("y2axis_off", False)
        ax._frame_off = d.get("frame_off", False)
        ax._polar = d.get("polar", False)
        ax._aspect = d.get("aspect")
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
                # ``bottom`` / ``top`` are arrays but not in ``ARRAY_FIELDS``:
                # that loop inserts a missing key, and a bar with no baseline
                # must keep the key absent so its snapshot stays historical.
                # Nor are a scatter's optional ``mdata`` and ``cdata``.
                optional = {
                    BarSeries: ("bottom", "top"),
                    ScatterSeries: ("mdata", "cdata"),
                }
                for key in optional.get(series_cls, ()):
                    if key in item and item[key] is not None:
                        item[key] = _to_float_array(item[key])
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
        for attr in (
            "bars",
            "hists",
            "functions",
            "fits",
            "lines",
            "scatters",
            "errorbars",
            "fills",
            "reflines",
            "spans",
            "file_series",
            "derived_series",
        ):
            for item in getattr(ax, attr):
                seq = item.get("_draw_seq")
                if seq is not None:
                    max_seq = max(max_seq, int(seq))
        ax._draw_seq_counter = max_seq + 1 if max_seq >= 0 else 0

        return ax

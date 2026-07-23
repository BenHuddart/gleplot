"""Axes class for gleplot."""

import numpy as np
import re
from typing import Optional, List, Union, Tuple
from .colors import rgb_to_gle
from .markers import get_gle_marker
from .mathtext import mathtext_to_gle
from .palettes import canonical_cmap
from .parser.units import markersize_to_msize, capsize_pt_to_cm
from .parser.tables import MATPLOTLIB_TO_LSTYLE

# Global counter for unique data file names across all figures in a session
_global_data_file_counter = 0


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


def _sanitize_data_stem(name: object) -> str:
    """Convert an arbitrary data name to a safe filename stem."""
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name).strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "data"


def _looks_numeric(token: str) -> bool:
    """True if ``token`` would parse as a float (int/float/exponent form).

    GLE's own header auto-detection (see ``graph.cpp: auto_has_header`` /
    ``isFloatMiss``) treats the first row of a data file as a header ONLY
    if *every* cell in that row fails float conversion; a single numeric-
    looking header token would make GLE read the whole header row as data
    instead. Column names must never satisfy this check.
    """
    try:
        float(token)
        return True
    except ValueError:
        return False


def sanitize_column_name(name: object, fallback: str = "col") -> str:
    """Sanitize an arbitrary label into a safe GLE data-file column header token.

    Rules (documented here as the single source of truth for the sanitizer):

    1. Keep only ``[A-Za-z0-9_]`` characters; every other character
       (whitespace, punctuation, unicode, ...) becomes a single ``_``.
    2. Lowercase the result.
    3. Collapse consecutive underscores to one and strip leading/trailing
       underscores.
    4. If the result is empty, fall back to ``fallback``.
    5. If the result would itself parse as a number (e.g. a label of
       ``"2024"``), prefix it with ``fallback + "_"`` so it can never be
       mistaken for a data value -- GLE's header auto-detection requires
       *every* first-row token to be non-numeric, and a purely numeric
       column name would silently defeat the header row for the whole
       file (see :func:`_looks_numeric`).
    6. The result never contains whitespace (guaranteed by step 1), since
       header tokens are whitespace/space-separated on the header line.

    Uniqueness across a file's column names is NOT handled here (a single
    label sanitizes deterministically); see :func:`_unique_column_names`
    for de-duplication via ``_2``, ``_3``, ... suffixes.
    """
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(name).strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = fallback
    if _looks_numeric(text):
        text = f"{fallback}_{text}"
    return text


def _unique_column_names(names: List[str]) -> List[str]:
    """De-duplicate a list of column name tokens with stable ``_2``, ``_3``, ... suffixes.

    The first occurrence of a name is kept as-is; subsequent occurrences of
    the same (already-sanitized) name are suffixed with ``_2``, ``_3``, etc.
    (matching :func:`_reserve_data_filename`'s collision convention). This
    keeps sanitize_column_name pure/stateless while still guaranteeing
    uniqueness within one sidecar's header row.
    """
    seen: dict = {}
    result = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            candidate = f"{name}_{seen[name]}"
            while candidate in seen:
                seen[name] += 1
                candidate = f"{name}_{seen[name]}"
            seen[candidate] = 1
            result.append(candidate)
    return result


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


def _build_errorbar_column_names(
    label: Optional[str],
    yerr_up,
    yerr_down,
    xerr_left,
    xerr_right,
) -> List[str]:
    """Build the sidecar header row for an errorbar series.

    Mirrors :meth:`gleplot.writer.GLEWriter.add_errorbar`'s column-building
    order exactly (x, y, then vertical error column(s), then horizontal
    error column(s)), so the header row lines up 1:1 with the data columns
    the writer actually emits:

    - symmetric y error (``yerr_up == yerr_down``, both given) -> one
      ``'err'`` column
    - asymmetric -> ``'err_up'`` and/or ``'err_down'`` columns, in that order
    - symmetric x error (``xerr_left == xerr_right``, both given) -> one
      ``'xerr'`` column
    - asymmetric -> ``'xerr_left'`` and/or ``'xerr_right'`` columns

    The primary y column is named from ``label`` when given (else ``'y'``);
    error columns always keep their stable suffix names (never derived from
    the label) since GLE never auto-keys off an error dataset's column name
    directly relevant here -- only the uniqueness pass can rename them.
    """
    y_names = ["y"]

    has_yerr = yerr_up is not None or yerr_down is not None
    has_xerr = xerr_left is not None or xerr_right is not None
    yerr_symmetric = (
        has_yerr
        and yerr_up is not None
        and yerr_down is not None
        and np.array_equal(yerr_up, yerr_down)
    )
    xerr_symmetric = (
        has_xerr
        and xerr_left is not None
        and xerr_right is not None
        and np.array_equal(xerr_left, xerr_right)
    )

    if has_yerr:
        if yerr_symmetric:
            y_names.append("err")
        else:
            if yerr_up is not None:
                y_names.append("err_up")
            if yerr_down is not None:
                y_names.append("err_down")

    if has_xerr:
        if xerr_symmetric:
            y_names.append("xerr")
        else:
            if xerr_left is not None:
                y_names.append("xerr_left")
            if xerr_right is not None:
                y_names.append("xerr_right")

    return _build_column_names("x", y_names, label)


def _build_column_names(
    x_name: str, y_names: List[str], label: Optional[str]
) -> List[str]:
    """Build a sidecar header row: one name for x, then one per y-like column.

    Parameters
    ----------
    x_name : str
        Base name for the x column (conventionally ``'x'``).
    y_names : list of str
        Base (pre-uniqueness) names for the remaining columns in file order,
        e.g. ``['y']`` for a plain line, ``['y', 'err']`` for a symmetric
        errorbar, ``['upper', 'lower']`` for a fill, ``['height']`` for a
        bar chart. When ``label`` is given, the FIRST entry of ``y_names``
        (the primary data column) is derived from the sanitized label
        instead of its own base name; the rest keep their stable suffixes.
    label : str, optional
        Series label (e.g. the ``label=`` argument to ``plot``/``errorbar``/
        ...). When present, sanitized and used as the primary data column's
        name in place of its generic base name (e.g. ``'y'``). When absent
        (``None`` or empty), the generic base name is kept as-is.

    Returns
    -------
    list of str
        ``[x_name] + y_names`` with the primary column optionally renamed
        from ``label``, then de-duplicated for uniqueness within the file.
    """
    names = [x_name]
    for i, base in enumerate(y_names):
        if i == 0 and label:
            names.append(sanitize_column_name(label, fallback=base))
        else:
            names.append(base)
    return _unique_column_names(names)


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
        self.texts = []  # In-plot text annotations
        self.heatmaps = []  # imshow/tripcolor colormap series
        self.contours = []  # contour/tricontour line series

        # Raw GLE lines recovered from a parsed .gle file that the recognizer
        # could not map onto the object model. Emitted verbatim inside this
        # axes' graph block, immediately before 'end graph'. One entry per
        # source line, no trailing newline. Default: empty (nothing to emit).
        self.passthrough: list = []

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
        **kwargs
            Additional matplotlib-compatible arguments

        Returns
        -------
        Line2D
            Line object (for compatibility)
        """
        data_name = kwargs.pop("data_name", None)
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

        gle_marker = get_gle_marker(marker) if marker is not None else None
        plot_type = "scatter" if is_scatter else "line"

        # Scale markersize from matplotlib (typical 1-20, default 6) to GLE msize (0.05-0.5)
        # Examples: markersize 6 → 0.15, markersize 10 → 0.25, markersize 20 → 0.5
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )

        line_data = {
            "type": plot_type,
            "x": x,
            "y": y,
            "color": color,
            "marker": gle_marker,
            "markersize": gle_markersize,
            "linestyle": linestyle,
            "linewidth": linewidth,
            "label": label,
            "yaxis": yaxis,  # 'y' or 'y2'
            "offset": float(offset),
            "data_file": _resolve_data_file(self.figure, data_name),
            "column_names": _build_column_names("x", ["y"], label),
        }

        if is_scatter:
            self.scatters.append(line_data)
        else:
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
            gle_marker = get_gle_marker(parsed_marker)

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

        errbar_data = {
            "type": "errorbar",
            "x": x,
            "y": y,
            "yerr_up": yerr_up,
            "yerr_down": yerr_down,
            "xerr_left": xerr_left,
            "xerr_right": xerr_right,
            "color": color,
            "marker": gle_marker,
            "markersize": gle_markersize,
            "linestyle": parsed_linestyle,
            "linewidth": linewidth,
            "label": label,
            "capsize": stored_capsize,
            "gle_capsize": gle_capsize,  # Separate field for the GLE-converted value
            "yaxis": yaxis,  # 'y' or 'y2'
            "offset": float(offset),
            "data_file": _resolve_data_file(self.figure, data_name),
            "column_names": _build_errorbar_column_names(
                label, yerr_up, yerr_down, xerr_left, xerr_right
            ),
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
        marker: Optional[str] = "o",
        markersize: float = 6,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        yaxis: str = "y",
    ):
        """Plot by referencing columns in an existing external data file.

        This avoids writing generated ``data_*.dat`` files. Column indices are
        1-based to match GLE conventions.
        """
        if x_col < 1 or y_col < 1 or (yerr_col is not None and yerr_col < 1):
            raise ValueError("Column indices must be >= 1")

        label = mathtext_to_gle(label)
        if color is None:
            gle_color = "BLUE"
        else:
            gle_color = rgb_to_gle(color)

        gle_marker = get_gle_marker(marker) if marker else None
        gle_markersize = markersize_to_msize(
            markersize, self.figure.marker_config.msize_scale
        )
        gle_capsize = capsize_pt_to_cm(capsize) if capsize is not None else None

        self.file_series.append(
            {
                "series_type": "errorbar",
                "data_file": data_file,
                "x_col": int(x_col),
                "y_col": int(y_col),
                "yerr_col": int(yerr_col) if yerr_col is not None else None,
                "color": gle_color,
                "marker": gle_marker,
                "markersize": gle_markersize,
                "label": label,
                "capsize": gle_capsize,
                "yaxis": yaxis,
            }
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
            {
                "series_type": "line",
                "data_file": data_file,
                "x_col": int(x_col),
                "y_col": int(y_col),
                "color": gle_color,
                "linestyle": linestyle,
                "linewidth": float(linewidth),
                "label": label,
                "yaxis": yaxis,
            }
        )

        return self

    def scatter(
        self,
        x,
        y,
        color: Optional[str] = None,
        s: float = 20,
        marker: str = "o",
        label: Optional[str] = None,
        yaxis: str = "y",
        **kwargs,
    ):
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
        label = mathtext_to_gle(label)
        # scatter() uses 's' instead of markersize
        # matplotlib scatter s is area in points^2, typical range 10-100, default ~36
        # Convert to markersize: since area ~ size^2, markersize ~ sqrt(s)
        # Use factor of 1.2 for better visibility
        markersize = np.sqrt(s) * 1.2
        return self.plot(
            x,
            y,
            linestyle="none",
            color=color,
            marker=marker,
            markersize=markersize,
            label=label,
            yaxis=yaxis,
        )

    def bar(
        self,
        x,
        height,
        color: Optional[Union[str, List[str]]] = None,
        label: Optional[str] = None,
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

        bar_data = {
            "x": x,
            "height": height,
            "colors": colors,
            "label": label,
            "data_file": _resolve_data_file(self.figure, data_name),
            "column_names": _build_column_names("x", ["height"], label),
        }
        self.bars.append(bar_data)

        return self

    def fill_between(
        self,
        x,
        y1,
        y2,
        color: Optional[str] = None,
        alpha: float = 0.3,
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
            Transparency (0-1)
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

        fill_data = {
            "x": x,
            "y1": y1,
            "y2": y2,
            "color": color,
            "alpha": alpha,
            "label": label,
            "offset": float(offset),
            "data_file": _resolve_data_file(self.figure, data_name),
            "column_names": _unique_column_names(["x", "upper", "lower"]),
        }
        self.fills.append(fill_data)

        return self

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
            {
                "x": float(x),
                "y": float(y),
                "text": mathtext_to_gle(str(s)),
                "color": gle_color,
                "fontsize": float(fontsize) if fontsize is not None else None,
                "ha": str(ha),
                "va": str(va),
                "box_color": box_color,
            }
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
        hm = {
            "type": "heatmap",
            "source": "grid",
            "z": z,
            "x": None,
            "y": None,
            "zpts": None,
            "extent": ext,
            "origin": origin,
            "cmap": self._resolve_cmap(cmap),
            "vmin": None if vmin is None else float(vmin),
            "vmax": None if vmax is None else float(vmax),
            "interpolation": "nearest" if interpolation == "nearest" else "bicubic",
            "pixels": self._resolve_pixels(pixels),
            "invert": bool(invert),
            "gridsize": None,
            "ncontour": None,
            "label": label,
            "data_file": data_file,
            "colorbar": None,
        }
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
        ct = {
            "type": "contour",
            "source": "grid",
            "z": z,
            "x": None,
            "y": None,
            "zpts": None,
            "extent": ext,
            "levels": levels_resolved,
            "color": rgb_to_gle(colors),
            "linewidth": float(linewidths),
            "linestyle": self._linestyle_to_lstyle(linestyles),
            "clabel": bool(clabel),
            "clabel_fmt": str(clabel_fmt),
            "gridsize": None,
            "ncontour": None,
            "label": label,
            "data_file": data_file,
        }
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
            if x.ndim != 1 or y.ndim != 1 or z.ndim != 2:
                raise ValueError("contour(x, y, Z) requires 1-D x, 1-D y, 2-D Z")
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
        hm = {
            "type": "heatmap",
            "source": "points",
            "z": None,
            "x": xa,
            "y": ya,
            "zpts": za,
            "extent": ext,
            "origin": "lower",
            "cmap": self._resolve_cmap(cmap),
            "vmin": None if vmin is None else float(vmin),
            "vmax": None if vmax is None else float(vmax),
            "interpolation": "nearest" if interpolation == "nearest" else "bicubic",
            "pixels": self._resolve_pixels(pixels),
            "invert": bool(invert),
            "gridsize": gs,
            "ncontour": None,
            "label": label,
            "data_file": data_file,
            "colorbar": None,
        }
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
        ct = {
            "type": "contour",
            "source": "points",
            "z": None,
            "x": xa,
            "y": ya,
            "zpts": za,
            "extent": ext,
            "levels": levels_resolved,
            "color": rgb_to_gle(colors),
            "linewidth": float(linewidths),
            "linestyle": self._linestyle_to_lstyle(linestyles),
            "clabel": bool(clabel),
            "clabel_fmt": str(clabel_fmt),
            "gridsize": gs,
            "ncontour": int(ncontour),
            "label": label,
            "data_file": data_file,
        }
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

    def legend(self, loc: str = "best", **kwargs):
        """Add legend."""
        self.legend_on = True
        # Map matplotlib loc to GLE positions
        loc_map = {
            "best": "top right",
            "upper right": "top right",
            "upper left": "top left",
            "lower left": "bottom left",
            "lower right": "bottom right",
            "center": "center",
        }
        self.legend_pos = loc_map.get(loc, "top right")
        return self

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
        )

    def has_y2_plots(self) -> bool:
        """Check if axes has any plots using the y2 axis."""
        for plot_list in [self.lines, self.scatters, self.errorbars]:
            for plot_data in plot_list:
                if plot_data.get("yaxis") == "y2":
                    return True
        return False

    # -- Serialization ----------------------------------------------------
    #
    # Which keys in each series dict hold numeric arrays. ``from_dict`` uses
    # this to restore ndarrays where the object model expects them; every
    # other key is a JSON scalar/string/None and is restored verbatim.
    _ARRAY_KEYS = {
        "lines": ("x", "y"),
        "scatters": ("x", "y"),
        "bars": ("x", "height"),
        "fills": ("x", "y1", "y2"),
        "errorbars": ("x", "y", "yerr_up", "yerr_down", "xerr_left", "xerr_right"),
        "file_series": (),
        "texts": (),
        "heatmaps": ("z", "x", "y", "zpts"),
        "contours": ("z", "x", "y", "zpts"),
    }

    # Series list attributes serialized on every axes, in a stable order.
    _SERIES_ATTRS = (
        "lines",
        "scatters",
        "bars",
        "fills",
        "errorbars",
        "file_series",
        "texts",
        "heatmaps",
        "contours",
    )

    @staticmethod
    def _default_column_names(attr: str, item: dict) -> Optional[List[str]]:
        """Regenerate ``column_names`` for a series loaded from an older project.

        Projects saved before Track E3 (named sidecar column headers) have no
        ``'column_names'`` key on their series dicts at all. Rather than
        leaving it absent (which would produce a headerless sidecar on the
        next save -- a silent format regression), recompute the same default
        names :meth:`plot`/:meth:`errorbar`/:meth:`bar`/:meth:`fill_between`
        would have produced for equivalent arguments, using the already
        JSON-scalar/array-restored ``item``. Returns ``None`` for
        ``file_series``/``texts`` (no generated sidecar, nothing to name).
        """
        label = item.get("label")
        if attr in ("lines", "scatters"):
            return _build_column_names("x", ["y"], label)
        if attr == "bars":
            return _build_column_names("x", ["height"], label)
        if attr == "fills":
            return _unique_column_names(["x", "upper", "lower"])
        if attr == "errorbars":
            return _build_errorbar_column_names(
                label,
                item.get("yerr_up"),
                item.get("yerr_down"),
                item.get("xerr_left"),
                item.get("xerr_right"),
            )
        return None

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
        return {
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
            "show_xlabel": self._show_xlabel,
            "show_ylabel": self._show_ylabel,
            "show_xticks": self._show_xticks,
            "show_yticks": self._show_yticks,
            "remove_last_xtick": getattr(self, "_remove_last_xtick", False),
            "remove_last_ytick": getattr(self, "_remove_last_ytick", False),
            "remove_first_xtick": getattr(self, "_remove_first_xtick", False),
            "remove_first_ytick": getattr(self, "_remove_first_ytick", False),
            "lines": [_to_jsonable(d) for d in self.lines],
            "scatters": [_to_jsonable(d) for d in self.scatters],
            "bars": [_to_jsonable(d) for d in self.bars],
            "fills": [_to_jsonable(d) for d in self.fills],
            "errorbars": [_to_jsonable(d) for d in self.errorbars],
            "file_series": [_to_jsonable(d) for d in self.file_series],
            "texts": [_to_jsonable(d) for d in self.texts],
            "heatmaps": [_to_jsonable(d) for d in self.heatmaps],
            "contours": [_to_jsonable(d) for d in self.contours],
            "passthrough": list(self.passthrough),
        }

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

        Numeric data in series is restored to ``float`` numpy arrays where the
        object model expects arrays (see ``_ARRAY_KEYS``); optional error
        arrays that were ``None`` stay ``None``. All style keys, labels and
        the ``data_file`` names are restored verbatim.
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

        ax._show_xlabel = d.get("show_xlabel", True)
        ax._show_ylabel = d.get("show_ylabel", True)
        ax._show_xticks = d.get("show_xticks", True)
        ax._show_yticks = d.get("show_yticks", True)
        ax._remove_last_xtick = d.get("remove_last_xtick", False)
        ax._remove_last_ytick = d.get("remove_last_ytick", False)
        ax._remove_first_xtick = d.get("remove_first_xtick", False)
        ax._remove_first_ytick = d.get("remove_first_ytick", False)

        for attr in cls._SERIES_ATTRS:
            array_keys = cls._ARRAY_KEYS[attr]
            restored = []
            for series in d.get(attr, []):
                item = dict(series)
                for key in array_keys:
                    item[key] = _to_float_array(item.get(key))
                # Older projects (pre Track E3) have no 'column_names' key at
                # all on their series dicts; regenerate the same defaults the
                # plotting methods would produce so the next save still gets
                # a named header row instead of silently reverting to none.
                if "column_names" not in item:
                    defaults = cls._default_column_names(attr, item)
                    if defaults is not None:
                        item["column_names"] = defaults
                restored.append(item)
            setattr(ax, attr, restored)

        ax.passthrough = list(d.get("passthrough", []))

        return ax

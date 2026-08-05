"""Typed series classes for :class:`gleplot.axes.Axes`.

Every drawable an axes owns -- lines, scatters, bars, fills, error bars,
external-file references, text annotations, heatmaps, contours, reference
lines and shaded spans -- used to be an anonymous ``dict`` in one of eleven
parallel lists on ``Axes``, with three hand-synchronised tables kept
alongside them (``Axes._SERIES_ATTRS`` for the list order,
``Axes._ARRAY_KEYS`` for which keys hold ndarrays, and
``Axes._default_column_names`` for the sidecar header row a legacy project
has to regenerate). Nothing tied a key name to the table entries that
described it, so adding a field meant remembering three unrelated places.

This module collapses that triple into one class per series kind. Each class
declares its fields as plain class-level annotations; the metaclass hook
turns those annotations into :attr:`Series.FIELDS`, and the class also owns
its :attr:`Series.ARRAY_FIELDS` and its
:meth:`Series.default_column_names` implementation. The registry
:data:`SERIES_CLASSES` maps the ``Axes`` list attribute onto its class and
fixes the serialization/emission order.

Wire compatibility
------------------

The classes are ``dict`` **subclasses** that hold *all* of their state as
their own items and none as instance attributes. That is deliberate and is
what keeps this refactor behaviour-preserving:

* ``Axes.to_dict()`` output is unchanged -- ``_to_jsonable`` already turns
  any mapping into a plain ``dict``, and construction inserts fields in the
  declared order, so the serialized shape (and therefore the ``.gle`` and
  ``.dat`` bytes the writer produces) is byte-for-byte what it was.
* The writer, the recognizer and the GUI panels address series by key
  (``series["color"]``, ``series.get("label")``, ``"zorder" in series``);
  every one of those call sites keeps working untouched.
* Optional fields stay *absent* rather than becoming ``None``. ``zorder``
  and ``_draw_seq`` are only meaningful when set, and ``sorted_zorder_
  drawables`` distinguishes the two cases, so ``__init__`` stores only the
  fields it is actually given.
* Having no instance ``__dict__`` state means ``copy``/``deepcopy``/pickle
  round-trip a series without any custom protocol support.

On top of that the declared fields are readable as attributes
(``series.color`` is ``series["color"]``), which is what gives static type
checking something to work with and what the ``source`` abstraction will
hang off next.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np

__all__ = [
    "Series",
    "LineSeries",
    "ScatterSeries",
    "BarSeries",
    "FillSeries",
    "ErrorbarSeries",
    "FileSeries",
    "TextAnnotation",
    "HeatmapSeries",
    "ContourSeries",
    "RefLine",
    "Span",
    "SERIES_CLASSES",
    "SERIES_ATTRS",
    "sanitize_column_name",
]


# -- sidecar column-name helpers ---------------------------------------------
#
# These live here rather than in axes.py because they encode series *schema*
# knowledge: which columns a kind writes to its ``.dat`` sidecar and in what
# order. ``gleplot.axes`` re-exports them, so the historical import path
# (``from gleplot.axes import sanitize_column_name``) still works.


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
    """De-duplicate column name tokens with stable ``_2``, ``_3``, ... suffixes.

    The first occurrence of a name is kept as-is; subsequent occurrences of
    the same (already-sanitized) name are suffixed with ``_2``, ``_3``, etc.
    (matching ``_reserve_data_filename``'s collision convention). This
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


def _build_errorbar_column_names(
    label: Optional[str],
    yerr_up: Any,
    yerr_down: Any,
    xerr_left: Any,
    xerr_right: Any,
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


# -- the base class -----------------------------------------------------------


class Series(Dict[str, Any]):
    """Base class for every typed series: a ``dict`` that knows its schema.

    Subclasses declare their fields as bare class-level annotations, in the
    order they are serialized::

        class MySeries(Series):
            ATTR = "mine"
            ARRAY_FIELDS = ("x",)

            x: np.ndarray
            label: Optional[str]

    A class-level annotation that also has a *value* (every ``ClassVar``
    below does) is configuration, not a field, and is skipped.

    Only the fields actually passed to :meth:`__init__` are stored, so
    "absent" and "present but ``None``" stay distinguishable -- ``zorder``
    relies on that. Unknown keyword arguments are rejected: that is the
    check which now enforces what the hand-synced tables used to.
    """

    #: The ``Axes`` list attribute this kind lives in (``"lines"``, ...).
    ATTR: str = ""

    #: Draw-order kind name for the cross-kind z-ordering in
    #: ``gleplot.axes.sorted_zorder_drawables``; ``None`` for kinds that are
    #: not part of that ordering (fills, texts, heatmaps, contours, ...).
    KIND: Optional[str] = None

    #: Default ``zorder`` when the caller omitted one. Matches the
    #: pre-zorder GLE emission stack: bars, then lines, scatters, errorbars
    #: (later ``dN`` commands draw on top in GLE).
    ZORDER_DEFAULT: Optional[float] = None

    #: Stable tie-break rank for legacy series that predate ``_draw_seq``.
    KIND_RANK: Optional[int] = None

    #: Fields holding numeric arrays, restored as float ndarrays by
    #: ``Axes.from_dict``. Everything else is a JSON scalar/string/None.
    ARRAY_FIELDS: Tuple[str, ...] = ()

    #: Declared field names in serialization order. Derived from the class
    #: annotations by :meth:`__init_subclass__`; never written by hand.
    FIELDS: Tuple[str, ...] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: List[str] = []
        for base in reversed(cls.__mro__):
            annotations = vars(base).get("__annotations__", {})
            for name in annotations:
                # A class-level annotation carrying a value is configuration
                # (ATTR, ARRAY_FIELDS, ...), not a data field.
                if name in vars(base) or name.startswith("__"):
                    continue
                if name not in fields:
                    fields.append(name)
        cls.FIELDS = tuple(fields)

    def __init__(self, **kwargs: Any) -> None:
        unknown = [key for key in kwargs if key not in self.FIELDS]
        if unknown:
            raise TypeError(
                f"{type(self).__name__} got unknown field(s) "
                f"{sorted(unknown)!r}. Declare them on the class (that is the "
                "single place a series kind's schema lives) or fix the caller."
            )
        super().__init__((name, kwargs[name]) for name in self.FIELDS if name in kwargs)

    @classmethod
    def _restore(cls, payload: Dict[str, Any]) -> "Series":
        """Rebuild a series from a :meth:`Axes.to_dict` payload.

        Lenient where :meth:`__init__` is strict: keys the class does not
        declare are preserved verbatim (after the declared ones) so a project
        written by a newer gleplot still round-trips through an older one,
        which is the forward-compatibility promise ``Axes.from_dict`` makes.
        """
        obj = cls(**{k: v for k, v in payload.items() if k in cls.FIELDS})
        for key, value in payload.items():
            if key not in cls.FIELDS:
                obj[key] = value
        return obj

    def copy(self) -> "Series":
        """A shallow copy of the same class (``dict.copy`` returns a ``dict``)."""
        return self._restore(self)

    def default_column_names(self) -> Optional[List[str]]:
        """Regenerate ``column_names`` for a series that has none stored.

        Projects saved before Track E3 (named sidecar column headers) have no
        ``'column_names'`` key on their series at all, and a hand-written
        ``.dat`` recovered by the recognizer may have no header row to
        recover names from. Rather than leaving it absent -- which would
        produce a headerless sidecar on the next save, a silent format
        regression -- each kind recomputes the same default names its
        plotting method would have produced for equivalent arguments.

        Returns ``None`` for kinds that generate no sidecar of their own
        (file references, texts, heatmaps, contours): there is nothing to
        name.
        """
        return None

    def __getattr__(self, name: str) -> Any:
        # Only reached when normal attribute lookup fails, so methods and
        # class attributes are never shadowed by same-named items.
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} has no attribute {name!r}"
            ) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.FIELDS:
            self[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in self.FIELDS:
            try:
                del self[name]
            except KeyError:
                raise AttributeError(
                    f"{type(self).__name__!r} has no attribute {name!r}"
                ) from None
        else:
            super().__delattr__(name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict.__repr__(self)})"


# -- data series --------------------------------------------------------------


class _XYSeries(Series):
    """Shared schema of the two series ``Axes.plot`` produces.

    ``plot()`` builds one dict and files it under ``lines`` or ``scatters``
    depending on whether a marker was requested without a line, so the two
    kinds have identical fields and differ only in where they live and how
    they z-order.
    """

    ARRAY_FIELDS = ("x", "y")

    type: str
    x: np.ndarray
    y: np.ndarray
    color: str
    marker: Optional[str]
    markersize: float
    linestyle: str
    linewidth: float
    label: Optional[str]
    yaxis: str
    offset: float
    data_file: Optional[str]
    column_names: Optional[List[str]]
    #: Display-command order within the axes; absent on pre-zorder projects.
    _draw_seq: int
    #: Only present when the caller asked for an explicit draw order.
    zorder: float

    def default_column_names(self) -> Optional[List[str]]:
        return _build_column_names("x", ["y"], self.get("label"))


class LineSeries(_XYSeries):
    """A line (optionally marker-decorated) dataset -- ``Axes.plot``."""

    ATTR = "lines"
    KIND = "line"
    ZORDER_DEFAULT = 3.0
    KIND_RANK = 1


class ScatterSeries(_XYSeries):
    """A marker-only dataset -- ``Axes.scatter`` / ``plot(linestyle='none')``."""

    ATTR = "scatters"
    KIND = "scatter"
    ZORDER_DEFAULT = 4.0
    KIND_RANK = 2


class BarSeries(Series):
    """A bar chart -- ``Axes.bar``."""

    ATTR = "bars"
    KIND = "bar"
    ZORDER_DEFAULT = 2.0
    KIND_RANK = 0
    ARRAY_FIELDS = ("x", "height")

    x: np.ndarray
    height: np.ndarray
    #: One colour per bar; GLE only honours the first, but the list length
    #: is what the GUI edits against.
    colors: Optional[List[str]]
    label: Optional[str]
    data_file: Optional[str]
    column_names: Optional[List[str]]
    _draw_seq: int
    zorder: float

    def default_column_names(self) -> Optional[List[str]]:
        return _build_column_names("x", ["height"], self.get("label"))


class FillSeries(Series):
    """A filled band between two curves -- ``Axes.fill_between``."""

    ATTR = "fills"
    ARRAY_FIELDS = ("x", "y1", "y2")

    x: np.ndarray
    y1: np.ndarray
    y2: np.ndarray
    color: str
    alpha: float
    label: Optional[str]
    offset: float
    data_file: Optional[str]
    column_names: Optional[List[str]]

    def default_column_names(self) -> Optional[List[str]]:
        return _unique_column_names(["x", "upper", "lower"])


class ErrorbarSeries(Series):
    """A dataset with x and/or y error bars -- ``Axes.errorbar``."""

    ATTR = "errorbars"
    KIND = "errorbar"
    ZORDER_DEFAULT = 5.0
    KIND_RANK = 3
    ARRAY_FIELDS = ("x", "y", "yerr_up", "yerr_down", "xerr_left", "xerr_right")

    type: str
    x: np.ndarray
    y: np.ndarray
    yerr_up: Optional[np.ndarray]
    yerr_down: Optional[np.ndarray]
    xerr_left: Optional[np.ndarray]
    xerr_right: Optional[np.ndarray]
    color: str
    marker: Optional[str]
    markersize: float
    linestyle: str
    linewidth: float
    label: Optional[str]
    #: Cap size as the caller gave it (matplotlib points, or cm when set
    #: through ``capsize_cm``); ``gle_capsize`` is the emitted cm value.
    capsize: Optional[float]
    gle_capsize: Optional[float]
    yaxis: str
    offset: float
    data_file: Optional[str]
    column_names: Optional[List[str]]
    _draw_seq: int
    zorder: float

    def default_column_names(self) -> Optional[List[str]]:
        return _build_errorbar_column_names(
            self.get("label"),
            self.get("yerr_up"),
            self.get("yerr_down"),
            self.get("xerr_left"),
            self.get("xerr_right"),
        )


class FileSeries(Series):
    """A reference to columns of an existing external data file.

    One class covers every ``series_type`` (``'line'``, ``'errorbar'``,
    ``'bar'``, ``'fill'``) because the variants are the same *kind* of thing
    -- a column reference plus style -- and share one list on the axes and
    one writer dispatch. The union of their fields is declared here and, as
    everywhere else, only the fields a given call actually supplies are
    stored, so each variant keeps exactly the shape it had.
    """

    ATTR = "file_series"

    series_type: str
    data_file: str
    x_col: int
    y_col: int
    #: ``'fill'`` variant: the two bounding columns.
    y1_col: int
    y2_col: int
    #: ``'errorbar'`` variant.
    yerr_col: Optional[int]
    color: str
    marker: Optional[str]
    markersize: float
    linestyle: str
    linewidth: float
    label: Optional[str]
    capsize: Optional[float]
    yaxis: str
    #: Why the referenced data could not be loaded, when it could not be.
    #: Present only on entries the recognizer degraded to a bare reference.
    data_error: str
    _draw_seq: int


class TextAnnotation(Series):
    """Free-form text drawn in data coordinates -- ``Axes.text``."""

    ATTR = "texts"

    x: float
    y: float
    text: str
    color: str
    fontsize: Optional[float]
    ha: str
    va: str
    box_color: Optional[str]


class _GridSeries(Series):
    """Base of the two gridded-data kinds (heatmaps and contours).

    Both accept either a regular grid (``source='grid'``, ``z`` plus
    ``extent``) or scattered samples gridded by GLE's ``fitz``
    (``source='points'``, ``x``/``y``/``zpts`` plus ``gridsize``), and both
    hold their bulk data in the same four array fields.

    The shared fields are re-declared in full by each subclass rather than
    inherited: field order here is serialization order, and the two kinds
    interleave their common and their own fields differently.
    """

    ARRAY_FIELDS = ("z", "x", "y", "zpts")


class HeatmapSeries(_GridSeries):
    """A colormap image -- ``Axes.imshow`` / ``Axes.tripcolor``."""

    ATTR = "heatmaps"

    type: str
    #: ``'grid'`` or ``'points'``.
    source: str
    z: Optional[np.ndarray]
    x: Optional[np.ndarray]
    y: Optional[np.ndarray]
    zpts: Optional[np.ndarray]
    extent: Optional[List[float]]
    origin: str
    cmap: str
    vmin: Optional[float]
    vmax: Optional[float]
    interpolation: str
    pixels: Optional[List[int]]
    invert: bool
    gridsize: Optional[List[int]]
    ncontour: Optional[int]
    label: Optional[str]
    data_file: str
    #: Colorbar declaration dict, or ``None`` for no colorbar.
    colorbar: Optional[Dict[str, Any]]


class ContourSeries(_GridSeries):
    """Contour lines -- ``Axes.contour`` / ``Axes.tricontour``."""

    ATTR = "contours"

    type: str
    #: ``'grid'`` or ``'points'``.
    source: str
    z: Optional[np.ndarray]
    x: Optional[np.ndarray]
    y: Optional[np.ndarray]
    zpts: Optional[np.ndarray]
    extent: Optional[List[float]]
    levels: Optional[List[float]]
    color: str
    linewidth: float
    linestyle: Optional[int]
    clabel: bool
    clabel_fmt: str
    gridsize: Optional[List[int]]
    ncontour: Optional[int]
    label: Optional[str]
    data_file: str


class RefLine(Series):
    """A full-width/height guide line -- ``Axes.axvline`` / ``Axes.axhline``.

    Stores the *declaration* only. The concrete two-point dataset is built at
    write time by ``Axes.materialize_reflines`` so the guide tracks whatever
    axis limits end up being used.
    """

    ATTR = "reflines"

    type: str
    #: ``'v'`` or ``'h'``.
    orient: str
    value: float
    #: Extent along the other axis, as a fraction of the axes box.
    span_lo: float
    span_hi: float
    color: str
    linestyle: str
    linewidth: float
    label: Optional[str]
    data_file: Optional[str]
    column_names: Optional[List[str]]

    def default_column_names(self) -> Optional[List[str]]:
        return _build_column_names("x", ["y"], self.get("label"))


class Span(Series):
    """A shaded band -- ``Axes.axvspan`` / ``Axes.axhspan``.

    Like :class:`RefLine`, a declaration materialized into a fill at write
    time (``Axes.materialize_spans``).
    """

    ATTR = "spans"

    type: str
    #: ``'v'`` or ``'h'``.
    orient: str
    start: float
    end: float
    span_lo: float
    span_hi: float
    color: str
    alpha: float
    label: Optional[str]
    data_file: Optional[str]
    column_names: Optional[List[str]]

    def default_column_names(self) -> Optional[List[str]]:
        return _unique_column_names(["x", "upper", "lower"])


# -- registry -----------------------------------------------------------------

#: Every series list an axes owns, in the order they are serialized by
#: ``Axes.to_dict`` and walked by ``Axes.from_dict``. This single mapping
#: replaces the old ``Axes._SERIES_ATTRS`` / ``Axes._ARRAY_KEYS`` /
#: ``Axes._default_column_names`` triple: order comes from the mapping,
#: array-ness from ``cls.ARRAY_FIELDS``, and the header-row fallback from
#: ``cls.default_column_names``.
SERIES_CLASSES: Dict[str, Type[Series]] = {
    cls.ATTR: cls
    for cls in (
        LineSeries,
        ScatterSeries,
        BarSeries,
        FillSeries,
        ErrorbarSeries,
        FileSeries,
        TextAnnotation,
        HeatmapSeries,
        ContourSeries,
        RefLine,
        Span,
    )
}

#: The registry's keys, i.e. the ``Axes`` series list attribute names.
SERIES_ATTRS: Tuple[str, ...] = tuple(SERIES_CLASSES)

#: The subset that takes part in cross-kind z-ordering, keyed by ``KIND``
#: and ordered by ``KIND_RANK`` -- i.e. bars, lines, scatters, errorbars,
#: the fixed emission stack that predates ``zorder`` and is still the
#: tie-break order in ``gleplot.axes.sorted_zorder_drawables``.
DRAWABLE_CLASSES: Dict[str, Type[Series]] = {}
for _cls in sorted(
    (c for c in SERIES_CLASSES.values() if c.KIND is not None),
    key=lambda c: c.KIND_RANK or 0,
):
    DRAWABLE_CLASSES[str(_cls.KIND)] = _cls
del _cls

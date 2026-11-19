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
* The writer, the recognizer and applications built on gleplot address
  series by key
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
checking something to work with.

Where the numbers come from: ``data_source``
--------------------------------------------

Every kind that owns bulk data declares a ``data_source`` field holding a
:class:`gleplot.sources.DataSource`. It follows the same
"absent means the historical behaviour" rule as ``zorder``: a series with no
``data_source`` key is an :class:`~gleplot.sources.InlineData` series whose
arrays live in its own ``ARRAY_FIELDS``, which is exactly what the scripting
API produces and exactly the shape every pre-existing project has. A series
whose ``data_source`` is a :class:`~gleplot.sources.ColumnRef` /
:class:`~gleplot.sources.GridRef` instead carries ``None`` in those array
fields until the write-time resolution pass fills them in from a
:class:`~gleplot.sources.DataProvider` (see ``gleplot.writer.resolve_figure``).

The field is spelled ``data_source``, not ``source``: ``HeatmapSeries`` and
``ContourSeries`` have had a ``source`` field since long before this
abstraction existed (it holds ``'grid'`` or ``'points'``, i.e. which *grid
mode* the series uses), and those two kinds are precisely the ones that need
a ``GridRef``. Renaming the older field would have changed the serialized
shape of every heatmap and contour ever saved for no gain.

Whether it is drawn at all: ``visible``
---------------------------------------

Every *drawable* kind declares a ``visible`` field (GLEstudio SPEC 14.6).
It follows the same "absent means the historical behaviour" rule as
``zorder`` and ``data_source``: a series with no ``visible`` key is drawn,
so no existing project changes shape, and :func:`is_visible` is the single
reader of the field. Only ``visible = False`` hides.

Hidden means hidden *everywhere the figure is rendered*: the writer skips
the series' entire emission -- its ``.dat`` sidecar, its display command and
its ``key "..."`` legend entry -- and it is excluded from auto-limit
computation, so limits may re-fit when a series is hidden (explicit limits
are of course untouched). The one place it is NOT skipped is the model,
which keeps the arrays, the label and the reserved data-file name so that
un-hiding restores byte-identical output.

``TextAnnotation`` deliberately has no ``visible``: SPEC 7.5 lists texts as
their own branch of the structure tree, beside series rather than among
them, and G11 is per-*series* visibility.

Hidden is orthogonal to *dangling* (SPEC 3.2, ``DanglingSourceRef``):
"hidden because asked" and "skipped because broken" are different states
and neither is ever reported as the other.

How the curve is drawn: ``smooth_mode`` / ``svg_smooth``
--------------------------------------------------------

:class:`LineSeries` declares two independent smoothing fields (GLEstudio
SPEC 14.7), mirroring the two independent clauses of GLE's ``dn`` grammar
(``graph.tex``: ``dn smooth | smoothm`` and ``dn svg_smooth [m]``):

* ``smooth_mode`` -- ``'none'``, ``'smooth'`` or ``'smoothm'``. GLE's
  ``smooth`` fits a piecewise cubic *as a function of x*
  (``fitbez(data, multi=false)``); ``smoothm`` is the multi-valued variant
  (``multi=true``) for curves with more than one y per x -- a hysteresis
  loop, a closed contour. It is deliberately **not** a boolean: collapsing
  ``smoothm`` into ``smooth`` would silently redraw such a curve as a
  function of x.
* ``svg_smooth`` -- the iteration count of GLE's 7-point Savitzky-Golay
  filter (``savgol.cpp``), an integer >= 1; absent means off.

Both follow the "absent means the historical behaviour" rule ``visible``
and ``zorder`` follow. An absent ``smooth_mode`` defers to the figure-wide
:attr:`gleplot.config.GLEGraphConfig.smooth_curves`, which is exactly what
every project written before this field did; a *present* one wins for that
series, including ``'none'`` on a figure whose default is smoothed. The two
fields are orthogonal: a series may carry either, both or neither, and the
writer emits ``svg_smooth m`` **before** the mode token because that is the
only order in which GLE keeps both (``graph2.cpp``'s ``SVG_SMOOTH`` branch
clears ``smooth``/``smoothm``, while ``SMOOTH`` leaves ``svg_smooth``
alone). :func:`smooth_mode` and :func:`svg_smooth_iterations` are the
single readers.

The scope is ``LineSeries`` only (SPEC 14.7). Error bars and file-reference
series still take the figure-wide flag: GLE would accept the qualifier on
them, but v1.1 models it only where the semantics are documented.
"""

import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type

import numpy as np

from .sources import DataSource, source_from_dict

__all__ = [
    "Series",
    "LineSeries",
    "ScatterSeries",
    "BarSeries",
    "HistSeries",
    "FunctionSeries",
    "FitSeries",
    "FillSeries",
    "ErrorbarSeries",
    "FileSeries",
    "TextAnnotation",
    "HeatmapSeries",
    "ContourSeries",
    "RefLine",
    "Span",
    "Wedge",
    "Box",
    "Rug",
    "DerivedSeries",
    "PlacedImage",
    "SERIES_CLASSES",
    "SERIES_ATTRS",
    "SMOOTH_MODES",
    "is_visible",
    "normalize_smooth_mode",
    "normalize_svg_smooth",
    "sanitize_column_name",
    "smooth_mode",
    "svg_smooth_iterations",
    "sorted_zorder_drawables",
]


def is_visible(series: Mapping[str, Any]) -> bool:
    """Whether ``series`` should be drawn (GLEstudio SPEC 14.6).

    The single reader of the ``visible`` field, so the "absent means drawn"
    rule lives in exactly one place. A value of ``None`` also reads as drawn:
    an unset or malformed flag must never make a series disappear silently
    (SPEC 8.1.4 -- no silent drops), and showing something the user did not
    ask to hide is the recoverable direction of that error.

    Kinds that declare no ``visible`` field (``TextAnnotation``) are always
    drawn, which is what the default already says.
    """
    flag = series.get("visible", True)
    return True if flag is None else bool(flag)


#: The three values ``smooth_mode`` may take (GLEstudio SPEC 14.7), spelled
#: exactly as GLE spells the corresponding ``dn`` keyword so the writer can
#: emit the token verbatim. ``'none'`` is the explicit "do not smooth this
#: series", which is NOT the same as the field being absent -- see
#: :func:`normalize_smooth_mode`.
SMOOTH_MODES: Tuple[str, ...] = ("none", "smooth", "smoothm")


def normalize_smooth_mode(value: Any) -> Optional[str]:
    """Coerce a stored ``smooth_mode`` to a member of :data:`SMOOTH_MODES`.

    Returns ``None`` for "not declared", which the writer reads as *defer to
    the figure-wide* ``GLEGraphConfig.smooth_curves``. That is the only
    reading under which every project written before this field keeps its
    exact bytes, so absent has to stay distinguishable from ``'none'``.

    A value that is neither absent nor a known mode (a stale string, a
    boolean from a caller that assumed a flag) also reads as ``None``: an
    unrecognized mode must never be *guessed* into a smoothing that
    reinterpolates the data, and deferring to the figure default is the same
    recoverable direction :func:`is_visible` takes.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    return text if text in SMOOTH_MODES else None


def normalize_svg_smooth(value: Any) -> Optional[int]:
    """Coerce a stored ``svg_smooth`` to an iteration count, or ``None``.

    ``None`` means the filter is off. Iterations are integers >= 1: GLE runs
    the 7-point Savitzky-Golay pass ``m`` times (``graph2.cpp``, which itself
    coerces a parsed ``0`` up to ``1`` -- "if they say svg_smooth they want it
    at least once"). A non-numeric or sub-1 stored value is off rather than
    an error, for the same reason as :func:`normalize_smooth_mode`: the
    recoverable direction is drawing the data.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 1 else None


def smooth_mode(series: Mapping[str, Any]) -> Optional[str]:
    """The declared smooth mode of ``series``, or ``None`` if it defers.

    The single reader of the field; see :func:`normalize_smooth_mode` for
    what the two "nothing here" cases mean. Kinds that declare no
    ``smooth_mode`` (everything but :class:`LineSeries`, SPEC 14.7) always
    defer, which is what returning ``None`` for a missing key already says.
    """
    return normalize_smooth_mode(series.get("smooth_mode"))


def svg_smooth_iterations(series: Mapping[str, Any]) -> Optional[int]:
    """Savitzky-Golay iterations for ``series``, or ``None`` when off.

    The single reader of the field. Independent of :func:`smooth_mode`:
    GLE's two clauses are independent and so are these two fields.
    """
    return normalize_svg_smooth(series.get("svg_smooth"))


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

    Mirrors :meth:`gleplot.writer.GLEWriter.add_errorbar_series`'s column-building
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


def _own_annotations(cls: type) -> Mapping[str, Any]:
    """Names annotated in ``cls``'s own body, in declaration order.

    Python 3.14 evaluates annotations lazily (PEP 649): a class body no
    longer stores ``__annotations__`` in its namespace, so reading
    ``vars(cls)`` finds nothing there. Only the names matter here, so ask for
    forward references rather than forcing every annotation to resolve while
    the class is still being created.
    """
    if sys.version_info >= (3, 14):
        import annotationlib

        if "__annotate_func__" not in vars(cls) and "__annotations__" not in vars(cls):
            return {}
        return annotationlib.get_annotations(
            cls, format=annotationlib.Format.FORWARDREF
        )
    own: Mapping[str, Any] = vars(cls).get("__annotations__", {})
    return own


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
    #: ``sorted_zorder_drawables``; ``None`` for kinds that are
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
            for name in _own_annotations(base):
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
        # A serialized source is a plain mapping; rebuild it as its class so
        # ``source_of(series)`` hands back something with behaviour. An
        # unrecognized ``kind`` survives verbatim (see source_from_dict).
        if obj.get("data_source") is not None:
            obj["data_source"] = source_from_dict(obj["data_source"])
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
    #: ``None`` is a recovered ``dN`` line that set no colour: the writer
    #: writes none, and GLE draws in the current colour.
    color: Optional[str]
    marker: Optional[str]
    markersize: float
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that drew a line but set no
    #: ``lwidth``: the writer writes none (GLE's current line width).
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    #: GLE's ``nomiss qualifier: draw the line through a missing value
    #: instead of leaving a gap (GLE default: gap). Only meaningful when a
    #: line is drawn, but preserved verbatim on scatter-only series too so a
    #: hand-written file that sets it never loses the setting on re-save.
    nomiss: bool
    label: Optional[str]
    yaxis: str
    #: ``'x2'`` binds the series to the top scale. Absent means the
    #: primary x axis, so a series stored before this field existed is
    #: unchanged.
    xaxis: str
    offset: float
    data_file: Optional[str]
    column_names: Optional[List[str]]
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    #: Display-command order within the axes; absent on pre-zorder projects.
    _draw_seq: int
    #: Only present when the caller asked for an explicit draw order.
    zorder: float
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: GLE ``mdist``: markers every this many cm along the curve instead of
    #: one per point. Absent: a marker on every point (or the figure's
    #: ``GLEMarkerConfig.mdist`` on a marked line).
    mdist: float
    #: GLE ``deresolve``: draw one point in every N. Absent: every point.
    deresolve: int
    #: GLE ``deresolve N average``: each window of N points is drawn as its
    #: mean. Only present together with ``deresolve``.
    deresolve_average: bool
    #: GLE's per-dataset range, in data coordinates: the series is drawn as
    #: if its axes ran over it, and nothing outside it is drawn. Absent:
    #: that edge is the limit of the axis the series is drawn against.
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def default_column_names(self) -> Optional[List[str]]:
        return _build_column_names("x", ["y"], self.get("label"))


class LineSeries(_XYSeries):
    """A line (optionally marker-decorated) dataset -- ``Axes.plot``.

    The one kind that carries the smoothing fields (SPEC 14.7); see the
    module docstring for why they are two independent fields and why the
    mode is not a boolean.
    """

    ATTR = "lines"
    KIND = "line"
    ZORDER_DEFAULT = 3.0
    KIND_RANK = 1

    #: ``'none'`` / ``'smooth'`` / ``'smoothm'``; absent (the default) defers
    #: to the figure-wide ``GLEGraphConfig.smooth_curves``. See
    #: :func:`smooth_mode`.
    smooth_mode: str
    #: Savitzky-Golay iterations (int >= 1); absent (the default) means off.
    #: Independent of ``smooth_mode``. See :func:`svg_smooth_iterations`.
    svg_smooth: int
    #: GLE ``dn line`` mode (``steps``, ``fsteps``, ``hist``, ``bar``,
    #: ``impulses``). Absent means a plain polyline, so a series that never
    #: asked for one keeps the historical dict shape and the writer emits a
    #: bare ``line``. See :data:`gleplot.parser.tables.LINE_MODES`.
    line_mode: str
    #: The non-finite rows are gaps: the writer writes them as GLE missing
    #: values (``*``), which break the line, so each run of points is its
    #: own polyline (``Axes.plot`` / ``step`` with NaN, ``Axes.hlines`` /
    #: ``Axes.vlines``). Absent: NaN is written ``nan``, which GLE drops,
    #: joining the neighbours.
    gaps: bool


class ScatterSeries(_XYSeries):
    """A marker-only dataset -- ``Axes.scatter`` / ``plot(linestyle='none')``."""

    ATTR = "scatters"
    KIND = "scatter"
    ZORDER_DEFAULT = 4.0
    KIND_RANK = 2

    #: GLE ``mdata``: each point's marker size as a multiple of
    #: ``markersize``, one per point. Absent: every marker at ``markersize``.
    mdata: np.ndarray
    #: ``scatter(c=...)``: one value per point, coloured through ``cmap``
    #: from ``vmin`` (its first colour) to ``vmax`` (its last). Absent: every
    #: point in ``color``. ``cmap``, ``vmin`` and ``vmax`` are present
    #: exactly when this is.
    cdata: np.ndarray
    cmap: str
    vmin: float
    vmax: float
    #: Colorbar declaration dict of a colour-mapped scatter, as on
    #: :attr:`HeatmapSeries.colorbar`, with ``zmin``/``zmax`` its ``vmin``
    #: and ``vmax``. Absent: no colorbar. See :meth:`gleplot.Figure.colorbar`.
    colorbar: Dict[str, Any]

    def default_column_names(self) -> Optional[List[str]]:
        if "mdata" in self:
            return _build_column_names("x", ["y", "mdata"], self.get("label"))
        if "cdata" in self:
            return _build_column_names("x", ["y", "c"], self.get("label"))
        return super().default_column_names()


class BarSeries(Series):
    """A bar chart -- ``Axes.bar``."""

    ATTR = "bars"
    KIND = "bar"
    ZORDER_DEFAULT = 2.0
    KIND_RANK = 0
    ARRAY_FIELDS = ("x", "height")

    x: np.ndarray
    height: np.ndarray
    #: Face colour of each bar in this dataset. One GLE dataset has one
    #: fill: a call that asks for a different colour per bar becomes one
    #: series per bar, and a grouped ``bar d1,d2 fill c1,c2`` is several
    #: series that share :attr:`group`. A single series whose ``fill`` list
    #: is longer than one dataset keeps the extra tokens in
    #: :attr:`fill_list` (GLE stores them and draws the first). With a
    #: :attr:`pattern`, GLE's ``fill`` is the hatch ink, so this is too.
    colors: Optional[List[str]]
    #: GLE fill pattern (``bar ... pattern SHADE``: ``SHADE``, ``RSHADE``
    #: or ``GRID``, optionally numbered 1-5), matplotlib's ``hatch``.
    #: Absent: a solid fill. The pattern also reaches the legend swatch.
    pattern: Optional[str]
    #: Colour under the hatch (``bar ... background``), matplotlib's face
    #: colour when :attr:`pattern` is set. Absent: GLE's white.
    background: Optional[str]
    #: Authored ``fill`` tokens when they are not just :attr:`colors`' first
    #: entry. The writer emits this list verbatim. Absent on an API series.
    fill_list: Optional[List[str]]
    #: Stroke colour (GLE ``color``). Absent: the writer emits no ``color``
    #: keyword, and GLE strokes in black. ``"none"`` is matplotlib's missing
    #: edge; GLE has no such edge, so the writer emits ``lwidth 0``.
    edgecolor: Optional[str]
    #: Authored ``color`` list when a command names more than one edge.
    #: Emitted verbatim. Absent when :attr:`edgecolor` is the whole story.
    edge_list: Optional[List[str]]
    #: Edge width in points. Absent: nothing is written, and GLE keeps the
    #: line width already in force. ``0`` is written (it is how a missing
    #: edge is spelled).
    linewidth: Optional[float]
    #: Edge linestyle. Absent: GLE's solid default, and no ``lstyle`` token.
    #: ``'-'`` is stored only when a script or a caller named the style, so
    #: a hand-written ``lstyle 1`` is not dropped.
    linestyle: Optional[str]
    #: A ``lstyle`` token that is not one of the four matplotlib styles
    #: (a comma list, or a number the style map does not know). Re-emitted
    #: as written. Absent when :attr:`linestyle` carries it.
    lstyle: Optional[str]
    #: True emits ``horiz`` (matplotlib ``barh``). Absent is vertical, so a
    #: plain bar keeps the historical dict shape.
    horiz: bool
    #: Baseline of each bar (matplotlib ``bottom``, or ``left`` on
    #: ``barh``). Absent draws from 0 and the y column is the height.
    #: Present: ``bar dTo from dFrom``. The to-dataset's y is :attr:`top`
    #: when a script was recovered, otherwise ``bottom + height``.
    bottom: Optional[np.ndarray]
    #: Exact to-dataset y recovered from a ``from`` command. The writer
    #: prefers it so the sidecar stays the bytes that were read.
    top: Optional[np.ndarray]
    #: Series that share this id were one ``bar d1,d2,...`` command and are
    #: written as one. Absent on an independent bar.
    group: Optional[int]
    #: ``bar ... dist``, the gap from the left of one bar to the left of
    #: the next in a group. Absent: GLE's own ``width * 1.4``.
    dist: Optional[float]
    #: Bar width in DATA units (GLE's ``bar dN ... width w``), or absent
    #: (G19). Absent is the historical behaviour and the default: GLE sizes
    #: the set from the data itself -- ``drawBar`` takes
    #: ``getMinXInterval()/(nbars*2)`` whenever ``width`` is 0 (its "not
    #: given" sentinel) -- and gleplot only writes a width down for the
    #: datasets that derivation cannot serve (G16,
    #: :meth:`gleplot.writer.GLEWriter.bar_width_gle_cannot_derive`). A
    #: value here is the caller's own number: it is emitted verbatim and
    #: suppresses G16's derived one. ``0`` is GLE's own "no width given",
    #: so it is read as absent rather than emitted.
    width: Optional[float]
    label: Optional[str]
    data_file: Optional[str]
    column_names: Optional[List[str]]
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    _draw_seq: int
    zorder: float
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: Legend swatch colour when a ``keyfill`` is not the bar fill. Absent
    #: means the swatch is the bar fill (``update_key_fill`` already copied it).
    swatch_color: Optional[str]

    def default_column_names(self) -> Optional[List[str]]:
        if self.get("bottom") is not None:
            # The sidecar is the baseline and the top, not the segment
            # height. The legend label is the ``key``, not the header.
            return ["x", "bottom", "top"]
        return _build_column_names("x", ["height"], self.get("label"))


class HistSeries(Series):
    """A binned sample count -- ``Axes.hist``.

    The sidecar holds the raw samples (GLE bins them with ``let dK = hist``).
    ``histtype`` selects the drawing: ``step`` is ``dK line hist``;
    ``stepfilled`` is ``bar dK`` on that same result, one bin wide, from zero.
    """

    ATTR = "hists"
    KIND = "hist"
    ZORDER_DEFAULT = 2.0
    KIND_RANK = 4
    ARRAY_FIELDS = ("samples",)

    samples: np.ndarray
    #: ``step`` (``line hist``) or ``stepfilled`` (adjoining bars).
    histtype: str
    #: Inclusive start of the bin window. Absent: GLE chooses (axis, else data).
    hist_from: Optional[float]
    #: Exclusive end of the bin window, except the last bin which includes it.
    hist_to: Optional[float]
    #: Equal-width bin count (GLE ``bins``). Absent when ``bin_step`` is set,
    #: and when both were omitted (GLE's own default of 10).
    bins: Optional[int]
    #: Bin width (GLE ``step``). Used only when ``bins`` is absent.
    bin_step: Optional[float]
    #: ``stepfilled`` bar width in data units. Absent: GLE derives one, which
    #: is half the bin and leaves gaps, so the writer sets this for API series.
    bar_width: Optional[float]
    #: ``None`` is a recovered ``dN`` line that set no colour: the writer
    #: writes none, and GLE draws in the current colour.
    color: Optional[str]
    #: Stroke on a ``stepfilled`` bar. Absent: GLE's black edge.
    edgecolor: Optional[str]
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that drew a line but set no
    #: ``lwidth``: the writer writes none (GLE's current line width).
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    yaxis: str
    #: ``'x2'`` binds the histogram to the top scale. Absent means the
    #: primary x axis. A ``stepfilled`` histogram cannot use it: GLE's
    #: ``bar`` command has no ``x2axis``.
    xaxis: str
    data_file: Optional[str]
    column_names: Optional[List[str]]
    data_source: Optional[DataSource]
    _draw_seq: int
    zorder: float
    visible: bool

    def default_column_names(self) -> Optional[List[str]]:
        # A header would name the *sample* dataset. GLE copies that name into
        # the legend of every used dataset, and ``let hist`` uses it, so the
        # samples would appear as their own key. The histogram's label is the
        # key on the binned dataset instead.
        return None


class FunctionSeries(Series):
    """A curve GLE samples from an expression -- ``Axes.function``.

    Written as ``let dK = <expression> [from a] [to b] [step h]`` and drawn
    with ``dK line``. There is no sidecar: GLE evaluates the expression.
    """

    ATTR = "functions"
    KIND = "function"
    ZORDER_DEFAULT = 3.0
    KIND_RANK = 5

    #: A GLE expression in ``x``, written verbatim into the ``let``.
    expression: str
    #: ``from``, ``to`` and ``step`` of the ``let``. Absent: GLE's default
    #: (the x axis range, sampled at 100 points). On a log x axis GLE reads
    #: ``step`` as a point count.
    let_from: float
    let_to: float
    let_step: float
    #: ``None`` is a recovered ``dN`` line that set no colour: the writer
    #: writes none, and GLE draws in the current colour.
    color: Optional[str]
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that set no ``lwidth``.
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    _draw_seq: int
    zorder: float
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


class FitSeries(Series):
    """A curve GLE fits to data -- ``Axes.fit``.

    The sidecar holds the data, read as a dataset that is never drawn. It
    has no header: GLE keys every dataset a ``let`` uses, so a header would
    give the data its own legend entry.
    ``let dK = fit dJ with <expression> [from a] [to b] [step h]`` fits the
    coefficients and samples the fitted curve, which ``dK line`` draws. A
    series with a ``model`` instead has no expression, and its ``let`` is
    the closed-form routine for that model: ``let dK = linfit dJ ...``.
    """

    ATTR = "fits"
    KIND = "fit"
    ZORDER_DEFAULT = 3.0
    KIND_RANK = 6
    ARRAY_FIELDS = ("x", "y")

    x: np.ndarray
    y: np.ndarray
    #: A GLE expression in ``x``; every other name in it is a coefficient.
    #: Absent on a ``model`` fit.
    expression: str
    #: ``"linear"``, ``"exp"``, ``"exp10"`` or ``"power"``: the key of
    #: :data:`gleplot.parser.tables.FIT_MODEL_TO_ROUTINE`. Absent on an
    #: ``expression`` fit.
    model: str
    #: ``from``, ``to`` and ``step`` of the ``let``, as on
    #: :class:`FunctionSeries`.
    let_from: float
    let_to: float
    let_step: float
    #: ``None`` is a recovered ``dN`` line that set no colour: the writer
    #: writes none, and GLE draws in the current colour.
    color: Optional[str]
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that set no ``lwidth``.
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    data_file: Optional[str]
    _draw_seq: int
    zorder: float
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


#: A dataset name inside a GLE expression, such as ``d1``.
_DATASET_NAME_RE = re.compile(r"(?<![A-Za-z0-9_])d[0-9]+(?![A-Za-z0-9_])", re.I)


class DerivedSeries(Series):
    """A curve GLE computes from other series -- ``Axes.derived``.

    Written as ``let dK = <expression> [from a] [to b] [step h] [nsteps n]
    [where w] [range dA,dB]`` and drawn with ``dK line``, after every other
    data series of the axes, so the datasets it reads are already defined.
    In ``expression`` and ``let_where``, ``d1`` ... ``dn`` stand for
    ``sources[0]`` ... ``sources[n-1]``; the writer puts in the names it
    gave those series.
    """

    ATTR = "derived_series"

    #: A GLE expression over ``x`` and ``d1`` ... ``dn``.
    expression: str
    #: ``[attr, index]`` of each operand: the ``Axes`` list and the position
    #: in it of a line, scatter, file line, function or fit series.
    sources: List[List[Any]]
    #: ``from``, ``to`` and ``step`` of the ``let``, as on
    #: :class:`FunctionSeries`. Absent: GLE's default.
    let_from: float
    let_to: float
    let_step: float
    #: GLE ``nsteps``: the number of points between ``from`` and ``to``.
    let_nsteps: int
    #: GLE ``where``: keep only the points where this expression is true.
    let_where: str
    #: GLE ``range``: ``[attr, index]`` of each series whose x values the
    #: result is computed at, as for ``sources``. Absent: every operand's.
    let_range: List[List[Any]]
    #: ``None`` is a recovered ``dN`` line that set no colour.
    color: Optional[str]
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that set no ``lwidth``.
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    _draw_seq: int
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


class FillSeries(Series):
    """A filled region -- ``Axes.fill_between`` or ``Axes.fill``.

    Absent ``target`` is the two-curve band ``fill dA,dB``. ``target``
    ``"x1"`` / ``"x2"`` fills one curve to that axis (``fill x1,dN`` /
    ``fill dN,x2``). ``"polygon"`` is ``Axes.fill``: ``fill dN`` closes the
    vertices. ``xmin`` / ``xmax`` / ``ymin`` / ``ymax`` are GLE's clip
    window; an absent edge is not clipped. On an ``x1`` fill, ``ymin`` is
    also the line the region closes on (GLE's rule, not a second clip).
    """

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
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: Call order, for the legend. Fills are not z-ordered drawables, so this
    #: does not change ink. Absent on a series a script did not record it for.
    _draw_seq: int
    #: Legend swatch colour when it is not the fill colour. Absent means the
    #: swatch is ``apply_alpha(color, alpha)``.
    swatch_color: Optional[str]
    #: ``"x1"``, ``"x2"`` or ``"polygon"``. Absent: two-curve ``fill dA,dB``.
    target: str
    #: Clip window in data coordinates. Absent: that edge is open.
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def default_column_names(self) -> Optional[List[str]]:
        if self.get("target") in ("x1", "x2", "polygon"):
            return _unique_column_names(["x", "y"])
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
    #: ``None`` is a recovered ``dN`` line that set no colour: the writer
    #: writes none, and GLE draws in the current colour.
    color: Optional[str]
    marker: Optional[str]
    markersize: float
    linestyle: str
    #: ``None`` is a recovered ``dN`` line that drew a line but set no
    #: ``lwidth``: the writer writes none (GLE's current line width).
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    #: Cap size as the caller gave it (matplotlib points, or cm when set
    #: through ``capsize_cm``); ``gle_capsize`` is the emitted cm value.
    capsize: Optional[float]
    gle_capsize: Optional[float]
    yaxis: str
    #: ``'x2'`` binds the series to the top scale. Absent means the
    #: primary x axis.
    xaxis: str
    offset: float
    data_file: Optional[str]
    column_names: Optional[List[str]]
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    _draw_seq: int
    zorder: float
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: GLE's per-dataset range, as on ``_XYSeries``; the error bars are
    #: drawn against it too. Absent: that edge is the axis limit.
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    #: ``mdist``, ``deresolve`` and ``deresolve_average`` as on
    #: ``_XYSeries``, read from a file only: :meth:`Axes.errorbar` does not
    #: take them, since GLE thins the markers but not the error bars.
    mdist: float
    deresolve: int
    deresolve_average: bool

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
    #: ``None`` (``'line'`` and ``'errorbar'`` variants) is a recovered
    #: ``dN`` line that set no colour: the writer writes none.
    color: Optional[str]
    marker: Optional[str]
    markersize: float
    linestyle: str
    #: ``None`` (``'line'`` variant) is a recovered ``dN`` line that set no
    #: ``lwidth``: the writer writes none.
    linewidth: Optional[float]
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    #: ``'line'`` variant only: GLE's ``nomiss`` qualifier (see
    #: ``_XYSeries.nomiss``).
    nomiss: bool
    #: ``'line'`` variant only: GLE ``dn line`` mode. Absent means a plain
    #: polyline. See :attr:`LineSeries.line_mode`.
    line_mode: str
    label: Optional[str]
    capsize: Optional[float]
    yaxis: str
    #: ``'x2'`` binds the referenced columns to the top scale. Absent
    #: means the primary x axis.
    xaxis: str
    #: Why the recognizer did not load the referenced data, when it did not:
    #: the file is unreadable, or GLE reads it in a way the loader does not.
    #: Present only on entries the recognizer degraded to a bare reference.
    data_error: str
    _draw_seq: int
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: Legend swatch colour when a bar or fill ``keyfill`` is not ``color``.
    swatch_color: Optional[str]
    #: ``'fill'`` variant: ``"x1"``, ``"x2"`` or ``"polygon"``. Absent means
    #: the two-curve ``fill dA,dB``.
    target: str
    #: The ``fill`` command's clip window on the ``'fill'`` variant (absent:
    #: not clipped on that edge); the dataset's range (``_XYSeries.xmin``)
    #: on ``'line'`` and ``'errorbar'``.
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    #: ``'line'`` and ``'errorbar'`` variants: see ``_XYSeries.mdist``,
    #: ``deresolve`` and ``deresolve_average``.
    mdist: float
    deresolve: int
    deresolve_average: bool
    #: How GLE reads ``data_file``: ``ignore`` (leading lines skipped),
    #: ``comment`` (the comment marker, replacing GLE's ``!``) and
    #: ``numrows`` (data rows read). Absent: GLE's default.
    skiprows: int
    comment: str
    max_rows: int


class TextAnnotation(Series):
    """Free-form text drawn in data coordinates or axes fractions -- ``Axes.text``.

    The one kind with no ``visible`` field: SPEC 7.5's structure tree lists
    texts as their own branch beside the series, and G11 is per-*series*
    visibility (see the module docstring).
    """

    ATTR = "texts"

    x: float
    y: float
    text: str
    color: str
    fontsize: Optional[float]
    ha: str
    va: str
    box_color: Optional[str]
    #: Degrees counter-clockwise about the alignment point (GLE ``begin
    #: rotate``, which rotates about the current point). Absent means 0, so
    #: a text that does not rotate keeps the historical dict shape.
    rotation: float
    #: ``'axes'``: ``x`` and ``y`` are fractions of the frame
    #: (``Axes.text(transform=ax.transAxes)``). Absent means data coordinates.
    transform: str
    #: ``Axes.annotate`` arrow, all absent on a plain text. ``xy`` is the
    #: arrow tip ``[x, y]`` in data coordinates; ``arrow`` is the GLE
    #: ``join`` separator (``'->'``, ``'<-'``, ``'<->'`` or ``'-'``);
    #: ``arrowstyle`` is the GLE tip style (``'simple'``/``'filled'``),
    #: present exactly when ``arrow`` has a head; ``arrow_linewidth`` is in
    #: points, absent for GLE's ambient ``lwidth``.
    xy: List[float]
    arrow: str
    arrowstyle: str
    arrow_color: str
    arrow_linewidth: float


class _GridSeries(Series):
    """Base of the two gridded-data kinds (heatmaps and contours).

    Both accept either a regular grid (``source='grid'``, ``z`` plus
    ``extent``) or scattered samples gridded by GLE's ``fitz``
    (``source='points'``, ``x``/``y``/``zpts`` plus ``gridsize``), and both
    hold their bulk data in the same four array fields. A heatmap may also be
    an expression GLE evaluates itself (``source='function'``), with no
    arrays at all.

    The shared fields are re-declared in full by each subclass rather than
    inherited: field order here is serialization order, and the two kinds
    interleave their common and their own fields differently.

    ``extent`` may be ``None`` on a **reference-backed** grid series (one
    whose ``data_source`` is a :class:`~gleplot.sources.GridRef`), meaning
    *auto*: each write computes it from the arrays that write resolved --
    ``(0, nx, 0, ny)`` in grid mode, the sample bounds in points mode, the
    same defaults ``Axes.imshow``/``Axes.tripcolor`` bake when handed arrays
    (SPEC 14.5). A series that owns its arrays always carries a concrete
    extent, because the creation APIs had the arrays and baked it.
    See :func:`gleplot.writer.apply_grid_write_time_autos`.
    """

    ARRAY_FIELDS = ("z", "x", "y", "zpts")


class HeatmapSeries(_GridSeries):
    """A colormap image -- ``Axes.imshow`` / ``Axes.pcolormesh`` /
    ``Axes.contourf`` / ``Axes.tripcolor`` / ``Axes.function2d``."""

    ATTR = "heatmaps"

    type: str
    #: ``'grid'``, ``'points'`` or ``'function'``.
    source: str
    #: The GLE expression in ``x`` and ``y`` a ``'function'`` heatmap maps;
    #: absent on the other sources. Such a heatmap has no arrays and no
    #: ``data_file``: GLE evaluates the expression at every pixel.
    expression: str
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
    #: ``True`` on a ``'grid'`` heatmap from ``Axes.pcolormesh``: ``extent``
    #: holds the outer cell edges and each value colours one whole cell.
    #: Absent means ``imshow``'s placement.
    cells: bool
    #: The band edges of a ``'grid'`` heatmap from ``Axes.contourf``, which
    #: colours each value by its band; ``extent`` then holds the grid's first
    #: and last nodes. Absent on every other heatmap.
    levels: List[float]
    #: Which side of a ``contourf``'s levels is filled: ``'neither'``,
    #: ``'min'``, ``'max'`` or ``'both'``. Present exactly when ``levels`` is.
    extend: str
    pixels: Optional[List[int]]
    invert: bool
    gridsize: Optional[List[int]]
    ncontour: Optional[int]
    label: Optional[str]
    data_file: str
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    #: Colorbar declaration dict, or ``None`` for no colorbar. Its
    #: ``zmin``/``zmax``/``zstep`` are concrete numbers, except on a
    #: reference-backed heatmap that carries ``auto_range = True``, where
    #: they are ``None`` and each write computes them from the resolved data
    #: (SPEC 14.5). Its ``orientation`` key is ``'horizontal'`` for a bar
    #: below the axes; absent means vertical. See
    #: :meth:`gleplot.Figure.colorbar`.
    colorbar: Optional[Dict[str, Any]]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


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
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    linestyle: Optional[int]
    clabel: bool
    clabel_fmt: str
    gridsize: Optional[List[int]]
    ncontour: Optional[int]
    label: Optional[str]
    data_file: str
    #: Where the numbers come from; absent means InlineData (this
    #: series' own array fields). See :mod:`gleplot.sources`.
    data_source: Optional[DataSource]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


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
    #: Set by ``open_gle`` on a width of 0 or 1 pt read from a file, which
    #: is then written as given. Absent, 0 and 1 mean the style's default.
    _lwidth_verbatim: bool
    label: Optional[str]
    data_file: Optional[str]
    column_names: Optional[List[str]]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: Call order, for the legend. Reference lines are written after the
    #: fills, so this does not change ink.
    _draw_seq: int

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
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool
    #: Call order, for the legend. Spans are emitted with the fills, so this
    #: does not change ink.
    _draw_seq: int
    #: Legend swatch colour when it is not the band colour.
    swatch_color: Optional[str]

    def default_column_names(self) -> Optional[List[str]]:
        return _unique_column_names(["x", "upper", "lower"])


class Wedge(Series):
    """One pie slice -- ``Axes.pie`` stores one per value.

    Drawn after the graph block by the ``gleplot_wedge`` sub, which also
    writes the slice's label and percentage text.
    """

    ATTR = "wedges"

    type: str
    #: Centre, in data coordinates.
    x: float
    y: float
    #: Radius, in data units.
    r: float
    #: Start and end angle, degrees counter-clockwise from +x; ``theta1``
    #: is the smaller.
    theta1: float
    theta2: float
    color: str
    #: Text ``labeldistance`` radii from the centre; ``None`` draws none.
    label: Optional[str]
    labeldistance: float
    #: ``autopct`` text ``pctdistance`` radii from the centre; ``None``
    #: draws none.
    autotext: Optional[str]
    pctdistance: float
    #: Points; ``None`` is the current text height.
    fontsize: Optional[float]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


class Box(Series):
    """One box of a box plot -- ``Axes.boxplot`` stores one per sample set.

    Drawn after the graph block by the ``gleplot_box`` sub, then one
    ``gleplot_box_flier`` call per flier and a ``gleplot_box_mean`` call
    when the mean is shown.
    """

    ATTR = "boxes"

    type: str
    #: Position, in data coordinates along x.
    x: float
    #: Box and cap widths, in data units; a ``capwidth`` of 0 draws no caps.
    width: float
    capwidth: float
    #: Whisker ends, quartiles and median, in data coordinates along y.
    whislo: float
    q1: float
    med: float
    q3: float
    whishi: float
    #: Points beyond the whiskers, drawn as markers.
    fliers: List[float]
    #: Drawn as a marker; ``None`` draws none.
    mean: Optional[float]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


class PlacedImage(Series):
    """An external image file stretched over a data extent -- ``Axes.image``.

    Drawn inside the graph block by the ``gleplot_bitmap`` sub (PNG, JPEG,
    GIF, TIFF) or the ``gleplot_postscript`` sub (EPS), in a layer below the
    grid and the data.
    """

    ATTR = "images"

    type: str
    #: The image path exactly as given; GLE reads a relative path from the
    #: folder the ``.gle`` script is in.
    file: str
    #: ``[left, right, bottom, top]`` in data coordinates, each pair
    #: ascending.
    extent: List[float]
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


class Rug(Series):
    """One rug -- ``Axes.rug`` stores one per call.

    Its values are written to :attr:`data_file` and loaded as a dataset in
    the graph; ``xrug`` or ``yrug`` from GLE's ``rugs.gle`` draws them after
    the graph block.
    """

    ATTR = "rugs"

    type: str
    #: ``'x'`` (ticks along the x axis, at x values) or ``'y'``.
    axis: str
    #: Where the ticks are, in data coordinates along :attr:`axis`.
    ticks: List[float]
    #: Tick length in cm, into the axes from the frame; negative points out.
    length: float
    #: Frame edge: ``'bottom'``/``'top'`` for x, ``'left'``/``'right'`` for
    #: y, or ``'both'``.
    position: str
    color: str
    #: Points.
    linewidth: float
    #: The sidecar the values are written to, one per line.
    data_file: str
    #: Drawn at all; absent (the default) means yes. See :func:`is_visible`.
    visible: bool


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
        HistSeries,
        FunctionSeries,
        FitSeries,
        Wedge,
        Box,
        Rug,
        DerivedSeries,
        PlacedImage,
    )
}

#: The registry's keys, i.e. the ``Axes`` series list attribute names.
SERIES_ATTRS: Tuple[str, ...] = tuple(SERIES_CLASSES)

#: The subset that takes part in cross-kind z-ordering, keyed by ``KIND``
#: and ordered by ``KIND_RANK`` -- i.e. bars, lines, scatters, errorbars,
#: the fixed emission stack that predates ``zorder`` and is still the
#: tie-break order in ``sorted_zorder_drawables``.
DRAWABLE_CLASSES: Dict[str, Type[Series]] = {}
for _cls in sorted(
    (c for c in SERIES_CLASSES.values() if c.KIND is not None),
    key=lambda c: c.KIND_RANK or 0,
):
    DRAWABLE_CLASSES[str(_cls.KIND)] = _cls
del _cls


def sorted_zorder_drawables(ax: Any) -> List[Tuple[str, Series]]:
    """Bars, lines, scatters, and errorbars sorted by ``(zorder, call order)``.

    ``ax`` is anything carrying the series lists under their ``ATTR`` names,
    in practice a :class:`gleplot.axes.Axes`. It lives here rather than in
    ``axes`` so the writer can order drawables without importing ``axes``.

    The kind name and both fallbacks come from :data:`DRAWABLE_CLASSES`, so a
    new drawable kind only has to declare ``KIND``/``ZORDER_DEFAULT``/
    ``KIND_RANK`` to join the ordering. An explicit ``zorder`` on a series
    wins; ``_draw_seq`` records the call order and is absent only on
    pre-zorder projects, where the kind rank reproduces the old fixed
    emission stack (bars, then lines, scatters, errorbars).
    """
    items: List[Tuple[float, float, str, Series]] = []
    for kind, series_cls in DRAWABLE_CLASSES.items():
        default_z = float(series_cls.ZORDER_DEFAULT or 0.0)
        kind_rank = int(series_cls.KIND_RANK or 0)
        for idx, data in enumerate(getattr(ax, str(series_cls.ATTR))):
            z = float(data["zorder"]) if "zorder" in data else default_z
            draw_seq = data.get("_draw_seq")
            if draw_seq is None:
                draw_seq = kind_rank * 1_000_000 + idx
            items.append((z, float(draw_seq), kind, data))
    items.sort(key=lambda t: (t[0], t[1]))
    return [(kind, data) for _z, _seq, kind, data in items]

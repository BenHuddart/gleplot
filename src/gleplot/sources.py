"""Where a series' numbers come from: the ``data_source`` abstraction.

Historically every series baked its numpy arrays into itself at ``plot()``
time, and that is still exactly what the scripting API does. This module adds
the *other* possibility -- a series that holds a **reference** into a table
owned by something outside the figure (a GUI's data manager, a watched file,
a database query) and is resolved to concrete arrays only when the ``.gle``
is written.

The three source kinds
----------------------

:class:`InlineData`
    The arrays live on the series itself (``series["x"]``, ``series["y"]``,
    ...). This is the default and the **implied legacy form**: a series with
    no ``data_source`` key at all *is* an ``InlineData`` series, which is why
    a project written before this module existed loads unchanged and why
    ``Figure.to_dict()`` of a scripted figure still produces the historical
    per-series shape byte for byte.

:class:`ColumnRef`
    Columnar data: a ``table_id`` plus one column key per *series role*
    (``{'x': ..., 'y': ...}`` for a line, ``{'x': ..., 'height': ...}`` for
    a bar, ``{'x': ..., 'y': ..., 'yerr_up': ...}`` for an errorbar, ...).
    The role names are the series class's own ``ARRAY_FIELDS``, so one
    generic resolver covers every kind and a new kind needs no new code here.

:class:`GridRef`
    The same thing for gridded data (heatmaps and contours): a role may map
    to a *list* of column keys, which resolves to a 2-D array built by
    stacking those columns (the ``z`` grid). Scattered-sample grid series
    (``source='points'``) use the plain one-key-per-role form for
    ``x``/``y``/``zpts``.

Identity and renaming
---------------------

``table_id`` is an opaque, stable identity (a UUID in GLEstudio) and a column
key is likewise stable; the column's *display name* is a property of the
table, not of the reference. Renaming a table or a column therefore never
breaks a reference -- the reference does not mention the name. The display
name is used for one thing only: the header row of the ``.dat`` sidecar.

Dangling references never crash a write
---------------------------------------

A reference can go bad: the table was deleted, a watched file came back
without the column, or the figure is being written with no provider at all.
None of that is an error at write time. The affected series is **skipped**
and a :class:`DanglingSourceRef` -- a structured, inspectable record, not a
string -- is produced for it. A figure whose every series is dangling still
writes a valid (empty) ``.gle``. See ``gleplot.writer.resolve_figure`` for
the resolution pass and ``Figure.source_warnings`` for where the records
surface.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only
    from typing import Protocol
else:  # pragma: no cover - Python 3.7 has no typing.Protocol
    try:
        from typing import Protocol
    except ImportError:
        Protocol = object

__all__ = [
    "DataSource",
    "InlineData",
    "ColumnRef",
    "GridRef",
    "TableData",
    "DictDataProvider",
    "DataProvider",
    "ProviderTable",
    "DanglingSourceRef",
    "DanglingSourceWarning",
    "source_from_dict",
    "source_of",
    "is_inline",
    "resolve_reference",
]

#: A column key maps either to a single column (1-D) or, for a ``z`` grid, to
#: an ordered list of columns stacked into a 2-D array.
ColumnKey = str
RoleSpec = Union[ColumnKey, List[ColumnKey]]


# -- the source classes -------------------------------------------------------


class DataSource(Dict[str, Any]):
    """Base class for the three source kinds.

    Like :class:`gleplot.series.Series`, a ``dict`` **subclass** holding all
    of its state as items and none as instance attributes. That is what makes
    a source free to serialize (``_to_jsonable`` already turns any mapping
    into a plain dict), free to ``copy``/``deepcopy``/pickle, and free to
    compare -- the same reasoning that governs the series classes, applied one
    level down.

    ``kind`` is always the first item, so the serialized key order is stable.
    """

    #: Discriminator written as the ``kind`` item and read by
    #: :func:`source_from_dict`.
    KIND: str = ""

    def __init__(self, **fields: Any) -> None:
        super().__init__(kind=self.KIND, **fields)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} has no attribute {name!r}"
            ) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict.__repr__(self)})"

    def is_reference(self) -> bool:
        """True for the kinds that need a :class:`DataProvider` to resolve."""
        return False


class InlineData(DataSource):
    """The arrays are baked into the series itself.

    Carries no state beyond its discriminator: everything it "holds" is
    already on the series. Constructing one is therefore optional --
    :func:`source_of` returns an ``InlineData`` for any series that has no
    ``data_source`` key, which is what keeps the scripting API's output
    (and its serialized form) unchanged.
    """

    KIND = "inline"


class _TableRef(DataSource):
    """Shared implementation of the two provider-backed kinds.

    ``columns`` maps a series *role* -- one of the series class's
    ``ARRAY_FIELDS`` -- onto the stable key of the table column that supplies
    it. Roles the series has but the mapping omits are left alone, so an
    errorbar can reference ``x``/``y`` from a table while keeping constant or
    absent error columns.
    """

    def __init__(self, table_id: str, columns: Mapping[str, RoleSpec]) -> None:
        super().__init__(table_id=str(table_id), columns=dict(columns))

    def is_reference(self) -> bool:
        return True

    def column_keys(self) -> List[ColumnKey]:
        """Every column key this reference mentions, in role order, deduped."""
        keys: List[ColumnKey] = []
        for spec in self["columns"].values():
            for key in spec if isinstance(spec, list) else [spec]:
                if key not in keys:
                    keys.append(key)
        return keys


class ColumnRef(_TableRef):
    """Columnar data pulled from a provider table.

    ``ColumnRef('t1', {'x': 'time', 'y': 'signal'})`` says: my x column is
    the table column whose stable key is ``'time'``, my y column is
    ``'signal'``. Two series referencing the same ``table_id`` share one
    ``.dat`` sidecar holding the union of the columns they mention.
    """

    KIND = "column-ref"


class GridRef(_TableRef):
    """Gridded data pulled from a provider table.

    Two shapes, matching the two ``HeatmapSeries``/``ContourSeries`` grid
    modes (the series' own ``source`` field, which predates this module and
    is unrelated to ``data_source``):

    - ``source='grid'``: ``GridRef('t1', {'z': ['c0', 'c1', 'c2']})`` --
      the listed columns are stacked left-to-right into the 2-D ``z`` grid,
      so a table laid out like a spreadsheet resolves to the grid it looks
      like.
    - ``source='points'``: ``GridRef('t1', {'x': ..., 'y': ..., 'zpts': ...})``
      -- scattered samples, one key per role, gridded by GLE's ``fitz``.

    Grid series write their own raw ``.z``/points sidecar per series (that is
    what GLE's ``colormap``/``fitz`` read), so unlike :class:`ColumnRef` they
    never share a sidecar.
    """

    KIND = "grid-ref"


_SOURCE_CLASSES = {cls.KIND: cls for cls in (InlineData, ColumnRef, GridRef)}


def source_from_dict(payload: Any) -> Any:
    """Rebuild a :class:`DataSource` from a serialized payload.

    A payload whose ``kind`` this build does not know is returned **verbatim**
    rather than dropped or rejected: that is the same forward-compatibility
    promise ``Series._restore`` makes for undeclared keys. Such a source is
    treated as unresolvable at write time (a :class:`DanglingSourceRef` with
    reason ``'unknown-kind'``), never as a crash.
    """
    if isinstance(payload, DataSource):
        return payload
    if not isinstance(payload, Mapping):
        return payload
    cls = _SOURCE_CLASSES.get(str(payload.get("kind", "")))
    if cls is InlineData:
        return InlineData()
    if cls is not None:
        return cls(
            table_id=payload.get("table_id", ""),
            columns=payload.get("columns") or {},
        )
    return dict(payload)


def source_of(series: Mapping[str, Any]) -> Any:
    """The series' source, with a missing ``data_source`` meaning inline.

    This is the single place the "absent means :class:`InlineData`" rule is
    implemented; every consumer goes through it rather than testing for the
    key itself.
    """
    source = series.get("data_source")
    if source is None:
        return InlineData()
    return source


def is_inline(series: Mapping[str, Any]) -> bool:
    """True if ``series`` carries its own arrays (the scripting-API default)."""
    source = source_of(series)
    return not (isinstance(source, DataSource) and source.is_reference())


# -- the provider side --------------------------------------------------------


class ProviderTable(Protocol):
    """The shape :class:`DataProvider` hands back for a ``table_id``.

    Deliberately behavioural rather than structural: a GLEstudio table is a
    live, editable spreadsheet model with undo and column metadata, and
    nothing is gained by forcing it to expose gleplot's field names. Four
    methods is the whole contract.
    """

    def column_keys(self) -> Sequence[ColumnKey]:
        """Stable keys of every column, in table order."""
        ...  # pragma: no cover

    def has_column(self, key: ColumnKey) -> bool:
        """Whether ``key`` names a column that currently exists."""
        ...  # pragma: no cover

    def column_name(self, key: ColumnKey) -> str:
        """The column's *display* name -- used only for sidecar headers."""
        ...  # pragma: no cover

    def column_values(self, key: ColumnKey) -> np.ndarray:
        """The column's values as a 1-D float array."""
        ...  # pragma: no cover


class DataProvider(Protocol):
    """Supplies the tables that :class:`ColumnRef`/:class:`GridRef` name.

    One method. A provider is passed **at write time**
    (``Figure.savefig(..., data_provider=...)``) and is never stored on the
    figure: the figure is a serializable document and the provider is a live
    application object, so binding them would make ``to_dict()`` either lossy
    or impossible, and would stop the same figure being rendered against
    different tables (preview vs export, or a what-if dataset).
    """

    def get_table(self, table_id: str) -> Optional[ProviderTable]:
        """The table with this id, or ``None`` if there is no such table."""
        ...  # pragma: no cover


class TableData:
    """A concrete, in-memory :class:`ProviderTable`.

    Keeps the three parallel lists a table needs: stable ``keys``, display
    ``names``, and the column ``columns`` themselves. Renaming a column means
    changing ``names`` and leaves every reference to it intact -- which is the
    property the whole reference model rests on, made testable here.
    """

    def __init__(
        self,
        keys: Sequence[ColumnKey],
        names: Sequence[str],
        columns: Sequence[Sequence[float]],
    ) -> None:
        if not (len(keys) == len(names) == len(columns)):
            raise ValueError(
                f"TableData needs one name and one column per key: got "
                f"{len(keys)} keys, {len(names)} names, {len(columns)} columns"
            )
        arrays = [np.asarray(col, dtype=float) for col in columns]
        lengths = {len(col) for col in arrays}
        if len(lengths) > 1:
            raise ValueError(
                f"TableData columns must all have the same length; got {sorted(lengths)}"
            )
        self.keys: List[ColumnKey] = [str(k) for k in keys]
        self.names: List[str] = [str(n) for n in names]
        self.columns: List[np.ndarray] = arrays
        self._by_key = dict(zip(self.keys, range(len(self.keys))))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Sequence[float]]) -> "TableData":
        """Build a table whose column keys *are* their display names.

        The convenient form for scripts and tests, where there is no rename
        story to model.
        """
        keys = list(mapping)
        return cls(keys, keys, [mapping[k] for k in keys])

    @classmethod
    def from_data_table(cls, table: Any) -> "TableData":
        """Adapt a :class:`gleplot.dataio.DataTable` (a loaded ``.dat`` file).

        Column keys are positional (``c0``, ``c1``, ...) because a loaded
        file's header names are display text that an edit may change, while
        position is what the file itself is keyed by. Non-numeric columns are
        dropped: they cannot be plotted, and offering them as referenceable
        would only produce dangling references later.
        """
        keys, names, columns = [], [], []
        for idx, (name, column) in enumerate(zip(table.column_names, table.columns)):
            if table.is_numeric and not table.is_numeric[idx]:
                continue
            keys.append(f"c{idx}")
            names.append(name)
            columns.append(column)
        return cls(keys, names, columns)

    # -- ProviderTable ------------------------------------------------------

    def column_keys(self) -> List[ColumnKey]:
        return list(self.keys)

    def has_column(self, key: ColumnKey) -> bool:
        return key in self._by_key

    def column_name(self, key: ColumnKey) -> str:
        return self.names[self._by_key[key]]

    def column_values(self, key: ColumnKey) -> np.ndarray:
        return self.columns[self._by_key[key]]

    def __repr__(self) -> str:
        return f"TableData(keys={self.keys!r}, rows={len(self.columns[0]) if self.columns else 0})"


class DictDataProvider:
    """A :class:`DataProvider` over a plain ``{table_id: table}`` mapping.

    Enough for scripts, tests and simple embedders; GLEstudio supplies its own
    provider backed by the project's live tables.
    """

    def __init__(self, tables: Optional[Mapping[str, ProviderTable]] = None) -> None:
        self.tables: Dict[str, ProviderTable] = dict(tables or {})

    def get_table(self, table_id: str) -> Optional[ProviderTable]:
        return self.tables.get(table_id)


# -- the dangling-reference record --------------------------------------------


class DanglingSourceWarning(UserWarning):
    """Warning category for a series skipped because its source is dangling.

    Carries the structured record on ``.ref`` so a caller that installs a
    ``warnings`` filter still gets the inspectable object rather than only
    the rendered message.
    """

    def __init__(self, ref: "DanglingSourceRef") -> None:
        super().__init__(str(ref))
        self.ref = ref


class DanglingSourceRef:
    """A reference that could not be resolved, and the series it belonged to.

    Deliberately an object rather than a formatted string: GLEstudio shows
    these in the structure tree with retarget/remove actions, so it needs the
    identity of the series (which axes, which list, which index) and of the
    missing thing (which table, which columns) separately from any wording.
    ``str()`` renders the human-readable form for CLI use.

    Attributes
    ----------
    axes_index : int
        Index of the axes in ``figure.axes_list``.
    series_attr : str
        The axes list the series lives in (``'lines'``, ``'heatmaps'``, ...).
    series_index : int
        Index within that list.
    label : str or None
        The series' label, when it has one -- the only user-facing name a
        series has.
    table_id : str
        The ``table_id`` the reference names (``''`` for a source whose kind
        this build does not understand).
    missing_columns : tuple of str
        The column keys that could not be resolved. Empty when the whole
        table is missing.
    reason : str
        One of ``'no-provider'``, ``'unknown-table'``, ``'missing-column'``,
        ``'unknown-kind'``.
    """

    __slots__ = (
        "axes_index",
        "series_attr",
        "series_index",
        "label",
        "table_id",
        "missing_columns",
        "reason",
    )

    #: Every value ``reason`` can take, with its wording.
    REASONS = {
        "no-provider": "no data provider was supplied for this write",
        "unknown-table": "no table with that id",
        "missing-column": "column(s) not found in the table",
        "unknown-kind": "unrecognized data-source kind",
    }

    def __init__(
        self,
        axes_index: int,
        series_attr: str,
        series_index: int,
        label: Optional[str],
        table_id: str,
        reason: str,
        missing_columns: Iterable[str] = (),
    ) -> None:
        self.axes_index = int(axes_index)
        self.series_attr = series_attr
        self.series_index = int(series_index)
        self.label = label
        self.table_id = table_id
        self.reason = reason
        self.missing_columns: Tuple[str, ...] = tuple(missing_columns)

    @property
    def series_id(self) -> str:
        """A stable, printable identifier: ``axes[0].lines[2]``."""
        return f"axes[{self.axes_index}].{self.series_attr}[{self.series_index}]"

    @property
    def message(self) -> str:
        """The rendered, human-readable form (also what ``str()`` returns)."""
        who = self.series_id
        if self.label:
            who += f" ({self.label!r})"
        detail = self.REASONS.get(self.reason, self.reason)
        if self.missing_columns:
            detail += ": " + ", ".join(repr(c) for c in self.missing_columns)
        return (
            f"{who} was skipped: its data source references table "
            f"{self.table_id!r} but {detail}"
        )

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return (
            f"DanglingSourceRef({self.series_id}, table_id={self.table_id!r}, "
            f"reason={self.reason!r}, missing_columns={self.missing_columns!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DanglingSourceRef):
            return NotImplemented
        return all(
            getattr(self, name) == getattr(other, name) for name in self.__slots__
        )

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))


# -- resolution ---------------------------------------------------------------


class ResolvedReference:
    """The arrays a reference resolved to, plus what they came from.

    ``values`` is what gets written into the series copy the writer emits;
    ``column_keys`` and ``display_names`` are what the sidecar layer needs to
    build a shared ``.dat`` (which physical column each role landed in, and
    what to call it in the header row).
    """

    __slots__ = ("table_id", "values", "column_keys", "display_names")

    def __init__(
        self,
        table_id: str,
        values: Dict[str, np.ndarray],
        column_keys: Dict[str, RoleSpec],
        display_names: Dict[str, str],
    ) -> None:
        self.table_id = table_id
        self.values = values
        self.column_keys = column_keys
        self.display_names = display_names


def resolve_reference(
    source: Any,
    provider: Optional[DataProvider],
    roles: Sequence[str],
) -> Tuple[Optional[ResolvedReference], Optional[str], Tuple[str, ...]]:
    """Resolve one reference against a provider.

    Parameters
    ----------
    source : DataSource
        A :class:`ColumnRef` or :class:`GridRef` (inline sources never reach
        here), or an unrecognized payload from a newer gleplot.
    provider : DataProvider or None
        ``None`` is not an error here; it is the ``'no-provider'`` failure,
        reported like any other so the caller has one code path.
    roles : sequence of str
        The series class's ``ARRAY_FIELDS``. Roles the reference does not
        mention are skipped, and mentioned roles the class does not declare
        are ignored -- a reference written by a newer gleplot for a field
        this build lacks degrades to "that field keeps its inline value"
        rather than to an error.

    Returns
    -------
    (resolved, reason, missing)
        Exactly one of ``resolved`` / ``reason`` is set. ``missing`` lists the
        offending column keys when ``reason`` is ``'missing-column'``.
    """
    if not isinstance(source, _TableRef):
        return None, "unknown-kind", ()

    table_id = source["table_id"]
    if provider is None:
        return None, "no-provider", ()

    table = provider.get_table(table_id)
    if table is None:
        return None, "unknown-table", ()

    wanted = {
        role: spec for role, spec in source["columns"].items() if role in set(roles)
    }
    missing = [
        key
        for key in source.column_keys()
        if not table.has_column(key)
        # only complain about keys this build actually needs
        and any(
            key in (spec if isinstance(spec, list) else [spec])
            for spec in wanted.values()
        )
    ]
    if missing:
        return None, "missing-column", tuple(missing)

    values: Dict[str, np.ndarray] = {}
    display_names: Dict[str, str] = {}
    for role, spec in wanted.items():
        if isinstance(spec, list):
            # A ``z`` grid: stack the listed columns left-to-right. Column j
            # of the grid is column ``spec[j]`` of the table, so the array's
            # shape is (n_rows, n_listed_columns) -- the same orientation the
            # ``.z`` sidecar writer expects.
            values[role] = np.column_stack(
                [np.asarray(table.column_values(k), dtype=float) for k in spec]
            )
            for key in spec:
                display_names[key] = table.column_name(key)
        else:
            values[role] = np.asarray(table.column_values(spec), dtype=float)
            display_names[spec] = table.column_name(spec)

    return (
        ResolvedReference(table_id, values, dict(wanted), display_names),
        None,
        (),
    )

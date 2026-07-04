"""Pure-Python delimited data file loading and resolution for gleplot.

This module has no Qt dependency and no dependency on :mod:`gleplot.gui`,
so it can be imported by the core GLE parser (``gleplot.parser``) as well
as by the GUI data manager. It provides two layers:

1. **Loading** (:func:`load_data_file`, :class:`DataTable`): parses
   comma/tab/semicolon/whitespace-delimited text files (``.csv``,
   ``.dat``, ``.txt``, ...) into a column-oriented :class:`DataTable`.
   This is the original implementation from
   ``gleplot.gui.data.loader`` (moved here unchanged as part of the
   GLE-parsing project's Track A3 -- ``gleplot.gui.data.loader`` is now a
   thin backwards-compatible shim re-exporting these same names).

2. **Resolution** (:func:`resolve_data_reference`, :func:`extract_columns`,
   :func:`classify_data_file`): a parser-facing layer used to turn a
   ``data "file.dat" d1=c1,c2`` command referenced from a ``.gle`` script
   into loaded numpy arrays, without ever raising for missing/unreadable/
   malformed files -- callers get structured error information back
   instead, so a broken data reference can be surfaced as a "broken
   series" in the editor rather than crashing the parse.

Format handling (loading layer)
--------------------------------
- Delimiter sniffing via :class:`csv.Sniffer` on a sample of the file,
  falling back to arbitrary-whitespace splitting when sniffing fails or
  the sniffed delimiter doesn't actually separate the row into multiple
  fields.
- Comment lines (leading ``#`` or ``!``, ignoring leading whitespace) are
  skipped entirely and never considered for header/data detection.
- Header detection: the first non-comment, non-blank row is treated as a
  header if and only if at least one of its fields is a genuine
  non-numeric *label* -- i.e. it fails float conversion AND is not a
  missing-value token. A first data row consisting entirely of missing
  tokens (e.g. ``* * *``) is therefore kept as an all-NaN DATA row, not
  mistaken for a header.
- Header/column alignment: if a detected header's token count does not
  match the data column count (e.g. a whitespace-split multi-word header
  like ``Temperature (K) Resistance (Ohm)`` yielding 4 tokens over 2
  data columns), the row is still skipped as a header, but its tokens are
  not used to name columns; positional names (``col1``..``colN``) are
  synthesized and a warning is recorded on ``DataTable.warnings``.
  Delimited files (comma/tab/semicolon) split multi-word names correctly,
  so their headers align and are used verbatim.
- Missing values: empty fields and the GLE-convention tokens ``*``,
  ``?``, ``-``, ``.`` (only when they are the *entire* field, not part
  of a longer token) as well as ``nan``/``NaN`` (case-insensitive) become
  ``np.nan``.
- Ragged rows (inconsistent field counts) are right-padded with NaN up to
  the widest row seen; a human-readable warning is recorded for each
  padded row on ``DataTable.warnings``.
- Columns where every non-missing value parses as a float are numeric
  (``dtype=float64``); otherwise the column is kept as-is with
  ``dtype=object`` and flagged not numeric via ``DataTable.is_numeric``.
- Encoding: ``utf-8-sig`` first (tolerates a UTF-8 BOM and plain UTF-8
  files alike), falling back to ``latin-1`` so no file fails to load
  outright.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

__all__ = [
    "DataTable",
    "load_data_file",
    "ResolvedData",
    "resolve_data_reference",
    "extract_columns",
    "ColumnExtractionError",
    "classify_data_file",
]

#: Standalone tokens (case-sensitive, whole-field match) treated as missing
#: data, per GLE conventions plus common conventions from other tools.
_MISSING_TOKENS = {"*", "?", "-", "."}
#: Additional case-insensitive missing tokens.
_MISSING_TOKENS_CI = {"nan", ""}

#: Delimiters tried by the Sniffer / candidate list, in preference order.
_CANDIDATE_DELIMITERS = [",", "\t", ";"]


@dataclass
class DataTable:
    """A loaded delimited data file, column-oriented.

    Attributes
    ----------
    column_names : list of str
        One name per column. Synthesized as ``col1``, ``col2``, ... when
        the file has no header row.
    columns : list of numpy.ndarray
        One array per column, same order as ``column_names``. Numeric
        columns have ``dtype=float64`` (missing values are ``np.nan``);
        non-numeric columns have ``dtype=object`` holding the raw string
        tokens (missing values are ``None``).
    is_numeric : list of bool
        Per-column flag: ``True`` if the column is a numeric float array.
    n_rows : int
        Number of data rows (excludes the header row and comment lines).
    path : pathlib.Path
        Path the table was loaded from.
    delimiter : str
        The delimiter used to split fields. ``r"\\s+"`` denotes
        whitespace-splitting rather than a literal single-character
        delimiter.
    has_header : bool
        Whether the first non-comment row was consumed as a header.
    warnings : list of str
        Human-readable warnings, e.g. about ragged rows that were padded.
    """

    column_names: List[str]
    columns: List[np.ndarray]
    n_rows: int
    path: Path
    delimiter: str
    has_header: bool
    is_numeric: List[bool] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def n_cols(self) -> int:
        """Number of columns."""
        return len(self.column_names)

    def numeric_column_names(self) -> List[str]:
        """Names of columns that are numeric (selectable as plot data)."""
        return [
            name
            for name, numeric in zip(self.column_names, self.is_numeric)
            if numeric
        ]

    def numeric_column_indices(self) -> List[int]:
        """0-based indices of columns that are numeric."""
        return [i for i, numeric in enumerate(self.is_numeric) if numeric]


def _is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith("!")


def _read_text(path: Union[str, Path]) -> str:
    """Read file text, tolerating a UTF-8 BOM and falling back to latin-1."""
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _sniff_delimiter(sample_lines: List[str]) -> Optional[str]:
    """Try csv.Sniffer on a sample; return a delimiter char or None."""
    sample = "\n".join(sample_lines)
    if not sample.strip():
        return None
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_CANDIDATE_DELIMITERS))
        return dialect.delimiter
    except csv.Error:
        pass

    # Sniffer failed (e.g. single column, ambiguous, or ragged rows with
    # inconsistent field counts). Fall back to counting occurrences of
    # each candidate delimiter across the sample lines; pick the one that
    # appears on every non-empty line (count > 0), even if the exact
    # count varies row-to-row (ragged data), since that's still a strong
    # signal of a real field separator rather than incidental
    # punctuation. Prefer the delimiter with the most consistent counts
    # when more than one candidate qualifies.
    non_empty = [l for l in sample_lines if l.strip()]
    if not non_empty:
        return None
    best_delim = None
    best_variety = None
    for delim in _CANDIDATE_DELIMITERS:
        counts = [l.count(delim) for l in non_empty]
        if not all(c > 0 for c in counts):
            continue
        variety = len(set(counts))
        if best_variety is None or variety < best_variety:
            best_delim = delim
            best_variety = variety
    return best_delim


def _split_line(line: str, delimiter: Optional[str]) -> List[str]:
    """Split a single line into fields using the resolved delimiter.

    ``delimiter is None`` means whitespace-splitting.
    """
    if delimiter is None:
        return line.split()
    # csv module handles quoted fields correctly for comma/semicolon/tab.
    reader = csv.reader(io.StringIO(line), delimiter=delimiter)
    try:
        return next(reader)
    except StopIteration:
        return []


def _normalize_token(token: str) -> Optional[str]:
    """Return the token stripped, or None if it represents a missing value."""
    stripped = token.strip()
    if stripped in _MISSING_TOKENS:
        return None
    if stripped.lower() in _MISSING_TOKENS_CI:
        return None
    return stripped


def _try_float(token: Optional[str]) -> Optional[float]:
    """Convert a normalized token to float, or None if missing/not numeric."""
    if token is None:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def load_data_file(
    path: Union[str, Path], max_preview_rows: Optional[int] = None
) -> DataTable:
    """Load a delimited text data file into a :class:`DataTable`.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the data file (``.csv``, ``.dat``, ``.txt``, or any
        delimited text file).
    max_preview_rows : int, optional
        If given, only the first ``max_preview_rows`` data rows are
        parsed into ``columns`` (the rest of the file is ignored). This
        is a performance aid for large files when only a preview is
        needed; ``n_rows`` reflects the number of rows actually loaded.

    Returns
    -------
    DataTable

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the file contains no data rows at all.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    text = _read_text(path)
    raw_lines = text.splitlines()

    # Filter out comment and blank lines up front; header/data detection
    # and delimiter sniffing both operate on this filtered list only.
    content_lines = [l for l in raw_lines if l.strip() and not _is_comment(l)]

    if not content_lines:
        raise ValueError(f"No data rows found in {path}")

    sample_lines = content_lines[:20]
    delimiter = _sniff_delimiter(sample_lines)

    # Validate the sniffed delimiter actually splits the first line into
    # more than one field; otherwise fall back to whitespace splitting.
    if delimiter is not None:
        first_fields = _split_line(content_lines[0], delimiter)
        if len(first_fields) <= 1:
            delimiter = None

    split_rows = [_split_line(line, delimiter) for line in content_lines]

    # Header detection: the first row is a header iff at least one field is a
    # genuine non-numeric label -- i.e. it fails float conversion AND is not a
    # missing-value token. A missing token ('*', '?', '-', '.', '', 'nan')
    # also "fails float conversion", but a first data row consisting entirely
    # of missing values (e.g. '* * *') is real DATA (all-NaN), not a header;
    # only a field that is a real word/label marks the row as a header.
    first_row = split_rows[0]
    first_row_is_header = any(
        _normalize_token(tok) is not None and _try_float(_normalize_token(tok)) is None
        for tok in first_row
    )

    has_header = first_row_is_header
    if has_header:
        header_fields = [f.strip() for f in first_row]
        data_rows = split_rows[1:]
    else:
        header_fields = None
        data_rows = split_rows

    if max_preview_rows is not None:
        data_rows = data_rows[:max_preview_rows]

    if not data_rows:
        raise ValueError(f"No data rows found in {path}")

    warnings: List[str] = []

    # Column count is determined by the DATA rows, not the header. A header
    # whose token count differs from the data column count is a *misalignment*
    # (typically a whitespace-split multi-word header, e.g. header
    # 'Temperature (K) Resistance (Ohm)' = 4 tokens over 2 data columns): we
    # still skip the row as a header (it is not data), but we cannot trust its
    # tokens to name columns 1:1, so we synthesize positional names and warn.
    data_col_count = max(len(row) for row in data_rows)
    header_mismatch = (
        header_fields is not None and len(header_fields) != data_col_count
    )
    if header_mismatch:
        warnings.append(
            f"Header row has {len(header_fields)} field(s) but the data has "
            f"{data_col_count} column(s); the header does not align with the "
            "columns (e.g. multi-word names split on whitespace). Using "
            "positional column names (col1..colN) instead."
        )
    max_cols = data_col_count

    padded_rows: List[List[str]] = []
    for row_idx, row in enumerate(data_rows):
        if len(row) < max_cols:
            pad_count = max_cols - len(row)
            warnings.append(
                f"Row {row_idx + 1} has {len(row)} field(s), expected "
                f"{max_cols}; padded {pad_count} missing value(s) with NaN."
            )
            row = row + [""] * pad_count
        elif len(row) > max_cols:
            # Shouldn't normally happen since max_cols is the max data-row
            # width, but guard defensively.
            warnings.append(
                f"Row {row_idx + 1} has {len(row)} field(s), expected "
                f"{max_cols}; extra field(s) truncated."
            )
            row = row[:max_cols]
        padded_rows.append(row)

    if header_fields is None or header_mismatch:
        # No header, or a header that doesn't align 1:1 with the columns.
        column_names = [f"col{i + 1}" for i in range(max_cols)]
    else:
        column_names = list(header_fields)
        # Pad header names if the header row itself was short.
        while len(column_names) < max_cols:
            column_names.append(f"col{len(column_names) + 1}")
        # Fill blank header names with a positional placeholder.
        column_names = [
            name if name else f"col{i + 1}" for i, name in enumerate(column_names)
        ]

    # Build columns.
    columns: List[np.ndarray] = []
    is_numeric: List[bool] = []
    n_rows = len(padded_rows)

    for col_idx in range(max_cols):
        raw_values = [row[col_idx] for row in padded_rows]
        normalized = [_normalize_token(v) for v in raw_values]
        floats = [_try_float(v) for v in normalized]

        # Numeric iff every non-missing token parsed as a float. A
        # column that is entirely missing is treated as numeric (all NaN)
        # since there's no string content to preserve.
        column_is_numeric = all(
            f is not None or n is None for f, n in zip(floats, normalized)
        )

        if column_is_numeric:
            arr = np.array(
                [np.nan if f is None else f for f in floats], dtype=np.float64
            )
            columns.append(arr)
            is_numeric.append(True)
        else:
            obj_values = [n for n in normalized]  # None for missing, str otherwise
            arr = np.array(obj_values, dtype=object)
            columns.append(arr)
            is_numeric.append(False)

    return DataTable(
        column_names=column_names,
        columns=columns,
        n_rows=n_rows,
        path=path,
        delimiter=delimiter if delimiter is not None else r"\s+",
        has_header=has_header,
        is_numeric=is_numeric,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Parser-facing data resolution layer
# ---------------------------------------------------------------------------


@dataclass
class ResolvedData:
    """Result of resolving a ``data "..."`` reference from a ``.gle`` script.

    Exactly one of the following holds:

    - Success: ``exists`` is ``True``, ``resolved_path`` is set, ``table``
      is a loaded :class:`DataTable`, ``error`` is ``None``.
    - Failure (missing file, unreadable, malformed/empty): ``table`` is
      ``None`` and ``error`` holds a human-readable message. ``exists``
      reflects whether a filesystem entry was found at all (``False`` for
      "file not found", ``True`` for "found but failed to parse" such as
      an unreadable/empty file), and ``resolved_path`` is still populated
      with the path that was attempted (useful for diagnostics / "broken
      series" UI even when nothing could be loaded).

    This type never results from a raised exception -- construction
    always goes through :func:`resolve_data_reference`, which catches
    everything :func:`load_data_file` can raise.

    Attributes
    ----------
    resolved_path : pathlib.Path or None
        The absolute path that was attempted, resolved relative to the
        ``.gle`` file's directory (or used as-is if already absolute).
        ``None`` only if ``referenced_name`` itself couldn't be
        interpreted as a path at all (defensive; not expected in
        practice).
    exists : bool
        Whether ``resolved_path`` existed on disk at resolution time.
    table : DataTable or None
        The loaded table on success, else ``None``.
    error : str or None
        Human-readable error message on failure, else ``None``.
    """

    resolved_path: Optional[Path]
    exists: bool
    table: Optional[DataTable]
    error: Optional[str]


def resolve_data_reference(
    gle_path: Union[str, Path], referenced_name: str
) -> ResolvedData:
    """Resolve and load a data file referenced from a ``.gle`` script.

    Parameters
    ----------
    gle_path : str or pathlib.Path
        Path to the ``.gle`` file doing the referencing. Only its parent
        directory is used (the file itself need not exist).
    referenced_name : str
        The file name/path as written in the GLE ``data`` command, e.g.
        ``"file.dat"`` or ``"subdir/file.dat"``. Interpreted relative to
        ``gle_path``'s directory unless it is already absolute.

    Returns
    -------
    ResolvedData
        Never raises: missing files, unreadable files, and malformed/
        empty files are all reported via ``.error`` rather than an
        exception, so a parser can represent a broken ``data`` command as
        structured "broken series" info instead of aborting the parse.
    """
    ref = Path(referenced_name)
    if ref.is_absolute():
        resolved_path = ref
    else:
        gle_dir = Path(gle_path).parent
        resolved_path = gle_dir / ref

    exists = resolved_path.exists()
    if not exists:
        return ResolvedData(
            resolved_path=resolved_path,
            exists=False,
            table=None,
            error=f"Data file not found: {resolved_path}",
        )

    try:
        table = load_data_file(resolved_path)
    except (OSError, ValueError) as exc:
        return ResolvedData(
            resolved_path=resolved_path,
            exists=True,
            table=None,
            error=str(exc),
        )

    return ResolvedData(
        resolved_path=resolved_path,
        exists=True,
        table=table,
        error=None,
    )


class ColumnExtractionError(ValueError):
    """Raised by :func:`extract_columns` for out-of-bounds or non-numeric
    column requests.

    This is a :class:`ValueError` subclass carrying a clear message; per
    the documented convention (see :func:`extract_columns`), column
    extraction problems raise rather than returning a sentinel, since a
    bad column index/reference is a caller (parser) bug or a malformed
    GLE script that should be caught and turned into a broken-series
    diagnostic by the caller, not silently propagated as ``None`` data.
    """


def extract_columns(
    table: DataTable,
    x_col_1based: int,
    y_col_1based: int,
    extra_cols: Optional[List[int]] = None,
) -> dict:
    """Extract numeric columns from a :class:`DataTable` by 1-based index.

    GLE data commands and column references (``d1=c1,c2``) are 1-based,
    matching GLE script syntax, whereas :class:`DataTable.columns` is
    0-based Python list indexing. This function does the conversion.

    Parameters
    ----------
    table : DataTable
        The loaded table to extract from.
    x_col_1based : int
        1-based index of the X column.
    y_col_1based : int
        1-based index of the Y column.
    extra_cols : list of int, optional
        Additional 1-based column indices to extract (e.g. error-bar or
        extra Y columns for multi-column ``data`` commands). Each is
        keyed ``"c3"``, ``"c4"``, ... in the result, using the column's
        own 1-based index as the suffix (*not* its position in
        ``extra_cols``), so callers can match a result key back to the
        GLE column reference that produced it.

    Returns
    -------
    dict
        Keys ``"x"``, ``"y"``, and ``"c{n}"`` for each entry in
        ``extra_cols``, values are ``numpy.ndarray`` (``dtype=float64``).

    Raises
    ------
    ColumnExtractionError
        If any requested column index is out of bounds (``< 1`` or
        ``> table.n_cols``) or refers to a non-numeric column. This is
        the chosen error convention for this function (as opposed to
        returning ``None`` + a side-channel error): callers that need
        to represent a bad reference as a non-fatal "broken series"
        (e.g. the parser) should catch ``ColumnExtractionError`` around
        the call, rather than checking a result field on every call site.

    Notes
    -----
    Missing values are already ``np.nan`` in numeric columns (per
    :func:`load_data_file`'s GLE-convention token handling: ``*``, ``?``,
    ``-``, ``.``, empty, ``nan``), so no further missing-value handling
    is needed here.
    """

    def _get(col_1based: int, key: str) -> np.ndarray:
        # GLE column 0 is the synthesized point index (1, 2, 3, ...), used when
        # a data command has no x column (single-column file / NOX). Mirror
        # GLE's ``data_command`` (graph.cpp: ``column == 0`` -> ``j + 1``).
        if col_1based == 0:
            return np.arange(1, table.n_rows + 1, dtype=np.float64)
        if col_1based < 1 or col_1based > table.n_cols:
            raise ColumnExtractionError(
                f"Column {col_1based} ({key}) out of bounds: table "
                f"{table.path} has {table.n_cols} column(s) "
                f"(1-based indices 1..{table.n_cols})."
            )
        idx = col_1based - 1
        if not table.is_numeric[idx]:
            name = table.column_names[idx]
            raise ColumnExtractionError(
                f"Column {col_1based} ({key}) -- {name!r} in {table.path} -- "
                "is not numeric and cannot be used as plot data."
            )
        return table.columns[idx]

    result = {
        "x": _get(x_col_1based, "x"),
        "y": _get(y_col_1based, "y"),
    }
    for col in extra_cols or []:
        result[f"c{col}"] = _get(col, f"c{col}")
    return result


def classify_data_file(
    gle_path: Union[str, Path],
    referenced_name: str,
    import_list: Optional[List[str]] = None,
) -> str:
    """Classify a ``data`` reference as an ``"import"`` or a ``"reference"``.

    - ``"import"``: the data was copied into the project by gleplot's
      own export (a sidecar ``.dat`` file next to the ``.gle`` script)
      and should round-trip as in-memory/editable series data.
    - ``"reference"``: the ``.gle`` script points at an external file in
      place (via ``line_from_file`` / ``errorbar_from_file``-style
      commands) and the data should stay a file reference rather than
      being pulled into the project.

    Parameters
    ----------
    gle_path : str or pathlib.Path
        Path to the ``.gle`` file doing the referencing (unused since the
        filename heuristic was removed; retained for API stability).
    referenced_name : str
        The file name/path as written in the GLE ``data`` command.
    import_list : list of str, optional
        Authoritative list of file names/paths that gleplot's own writer
        recorded as "imported" (copied) data files, parsed from the
        ``! gleplot`` metadata comment block gleplot itself wrote into
        the ``.gle`` file when exporting. When this is not ``None``,
        membership in this list (matched against ``referenced_name``,
        both as given and as a bare filename) *fully decides* the
        classification. When it is ``None`` (no metadata block present --
        e.g. a hand-authored or third-party ``.gle`` script), the
        reference is ALWAYS classified ``"reference"``.

    Returns
    -------
    str
        ``"import"`` or ``"reference"``.

    Notes
    -----
    **Only the metadata block's import-data list can vouch a file as
    gleplot-owned.** Every ``.gle`` gleplot itself saves carries the
    ``! gleplot`` metadata block naming its import sidecars, so genuine
    gleplot-authored sidecars are always vouched via ``import_list`` and
    correctly classified ``"import"``.

    When ``import_list is None`` there is no authoritative signal that
    gleplot owns any referenced file, so classification is conservative:
    every reference is treated as an external ``"reference"``. This is a
    deliberate safety property -- classifying a file as ``"import"``
    causes gleplot to adopt (and, on the next ``savefig_gle``, REWRITE)
    that file. A hand-authored ``.gle`` sitting next to an ordinary
    user data file whose name happens to look like a sidecar (e.g.
    ``results_2024.dat``) must NEVER have its data silently overwritten.
    Such files remain read-only references: still plottable and
    editable-in-style, but never rewritten.

    (Historically a filename heuristic -- ``<prefix>_<digits>.dat`` in
    the same directory -- classified such files as ``"import"``; that
    produced a silent user-data-overwrite false positive and has been
    removed. The metadata block is now the sole source of truth.)
    """
    if import_list is None:
        return "reference"
    candidates = {referenced_name, Path(referenced_name).name}
    imported = {str(n) for n in import_list} | {
        Path(str(n)).name for n in import_list
    }
    return "import" if candidates & imported else "reference"

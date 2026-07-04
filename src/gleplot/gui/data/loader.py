"""Pure-Python delimited data file loading for the gleplot GUI data manager.

This module has no Qt dependency so it can be unit tested directly and
reused outside the GUI. It loads comma/tab/semicolon/whitespace-delimited
text files (``.csv``, ``.dat``, ``.txt``, ...) into a :class:`DataTable`:
a simple column-oriented structure with one 1-D numpy array (or an object
array for non-numeric columns) per column.

Format handling
---------------
- Delimiter sniffing via :class:`csv.Sniffer` on a sample of the file,
  falling back to arbitrary-whitespace splitting when sniffing fails or
  the sniffed delimiter doesn't actually separate the row into multiple
  fields.
- Comment lines (leading ``#`` or ``!``, ignoring leading whitespace) are
  skipped entirely and never considered for header/data detection.
- Header detection: the first non-comment, non-blank row is treated as a
  header if and only if at least one of its fields fails float
  conversion (after missing-value normalization the missing tokens count
  as "not a float" too, so a header row of plain names is always
  detected as a header).
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

    # Header detection: the first row is a header iff at least one field
    # fails float conversion after missing-value normalization.
    first_row = split_rows[0]
    first_row_is_header = any(
        _try_float(_normalize_token(tok)) is None for tok in first_row
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

    max_cols = max(len(row) for row in data_rows)
    if header_fields is not None:
        max_cols = max(max_cols, len(header_fields))

    warnings: List[str] = []
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
            # Shouldn't normally happen since max_cols is the max, but
            # guard defensively in case header_fields was shorter.
            warnings.append(
                f"Row {row_idx + 1} has {len(row)} field(s), expected "
                f"{max_cols}; extra field(s) truncated."
            )
            row = row[:max_cols]
        padded_rows.append(row)

    if header_fields is None:
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

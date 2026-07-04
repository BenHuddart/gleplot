"""Unit tests for gleplot.dataio: loading, resolution, and classification.

Covers:
- Shim equivalence: gleplot.gui.data.loader re-exports the exact same
  DataTable/load_data_file objects (proves the shim didn't fork behavior).
- Qt-freeness: importing gleplot.dataio must not import PySide6 or
  gleplot.gui.
- resolve_data_reference: relative/absolute/missing/unreadable/malformed.
- extract_columns: happy path, out-of-bounds, non-numeric.
- classify_data_file: metadata-list-driven only. With no metadata block
  (import_list is None) every reference is conservatively classified
  'reference' -- the old filename heuristic (and its user-data-overwrite
  false positive) has been removed (Finding 1).

tests/gui/test_data_loader.py and tests/gui/test_data_panel.py are run
unmodified elsewhere to prove the shim in the GUI context; this file
covers the new gleplot.dataio surface directly.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from gleplot.dataio import (
    ColumnExtractionError,
    DataTable,
    ResolvedData,
    classify_data_file,
    extract_columns,
    load_data_file,
    resolve_data_reference,
)


def _write(tmp_path: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding=encoding)
    return p


# ---------------------------------------------------------------------------
# Shim equivalence
# ---------------------------------------------------------------------------


def test_shim_reexports_same_objects():
    from gleplot.gui.data.loader import DataTable as ShimDataTable
    from gleplot.gui.data.loader import load_data_file as shim_load_data_file

    assert ShimDataTable is DataTable
    assert shim_load_data_file is load_data_file


def test_shim_gui_data_package_reexports_same_objects():
    from gleplot.gui.data import DataTable as PkgDataTable
    from gleplot.gui.data import load_data_file as pkg_load_data_file

    assert PkgDataTable is DataTable
    assert pkg_load_data_file is load_data_file


# ---------------------------------------------------------------------------
# Qt-free / gui-free import assertion
# ---------------------------------------------------------------------------


def test_dataio_import_does_not_pull_in_qt_or_gui():
    """Importing gleplot.dataio in a fresh subprocess must not import
    PySide6 or gleplot.gui (the core parser depends on dataio and must
    stay usable in headless/no-Qt environments).
    """
    code = (
        "import sys\n"
        "import gleplot.dataio\n"
        "bad = [m for m in sys.modules if m == 'PySide6' or m.startswith('PySide6.') "
        "or m == 'gleplot.gui' or m.startswith('gleplot.gui.')]\n"
        "print(','.join(bad))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, result.stderr
    leaked = result.stdout.strip()
    assert leaked == "", f"gleplot.dataio import pulled in: {leaked}"


# ---------------------------------------------------------------------------
# resolve_data_reference
# ---------------------------------------------------------------------------


def test_resolve_relative_path(tmp_path):
    gle_path = tmp_path / "plot.gle"
    _write(tmp_path, "file.dat", "x y\n1 2\n3 4\n")

    result = resolve_data_reference(gle_path, "file.dat")

    assert isinstance(result, ResolvedData)
    assert result.exists is True
    assert result.error is None
    assert result.resolved_path == tmp_path / "file.dat"
    assert result.table is not None
    assert result.table.n_rows == 2


def test_resolve_relative_path_subdirectory(tmp_path):
    gle_path = tmp_path / "plot.gle"
    subdir = tmp_path / "data"
    subdir.mkdir()
    (subdir / "file.dat").write_text("1 2\n3 4\n", encoding="utf-8")

    result = resolve_data_reference(gle_path, "data/file.dat")

    assert result.exists is True
    assert result.error is None
    assert result.resolved_path == subdir / "file.dat"


def test_resolve_absolute_path(tmp_path):
    gle_path = tmp_path / "sub" / "plot.gle"
    data_path = tmp_path / "elsewhere" / "file.dat"
    data_path.parent.mkdir(parents=True)
    data_path.write_text("1 2\n3 4\n", encoding="utf-8")

    result = resolve_data_reference(gle_path, str(data_path))

    assert result.exists is True
    assert result.error is None
    assert result.resolved_path == data_path
    assert result.table is not None


def test_resolve_missing_file_does_not_raise(tmp_path):
    gle_path = tmp_path / "plot.gle"

    result = resolve_data_reference(gle_path, "does_not_exist.dat")

    assert result.exists is False
    assert result.table is None
    assert result.error is not None
    assert "not found" in result.error.lower()
    assert result.resolved_path == tmp_path / "does_not_exist.dat"


def test_resolve_malformed_empty_file_does_not_raise(tmp_path):
    gle_path = tmp_path / "plot.gle"
    _write(tmp_path, "empty.dat", "")

    result = resolve_data_reference(gle_path, "empty.dat")

    assert result.exists is True
    assert result.table is None
    assert result.error is not None
    assert "no data rows" in result.error.lower()


def test_resolve_unreadable_file_does_not_raise(tmp_path):
    """A directory at the referenced path is 'exists' but unreadable as
    a data file; this must surface as a structured error, not raise.
    """
    gle_path = tmp_path / "plot.gle"
    bogus = tmp_path / "not_a_file.dat"
    bogus.mkdir()

    result = resolve_data_reference(gle_path, "not_a_file.dat")

    assert result.exists is True
    assert result.table is None
    assert result.error is not None


# ---------------------------------------------------------------------------
# extract_columns
# ---------------------------------------------------------------------------


def _make_table(tmp_path) -> DataTable:
    p = _write(tmp_path, "t.csv", "x,y,label,z\n1,10,foo,100\n2,20,bar,200\n3,30,baz,300\n")
    return load_data_file(p)


def test_extract_columns_happy_path(tmp_path):
    table = _make_table(tmp_path)

    result = extract_columns(table, x_col_1based=1, y_col_1based=2)

    assert set(result.keys()) == {"x", "y"}
    np.testing.assert_allclose(result["x"], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(result["y"], [10.0, 20.0, 30.0])


def test_extract_columns_with_extra_cols(tmp_path):
    table = _make_table(tmp_path)

    result = extract_columns(table, x_col_1based=1, y_col_1based=2, extra_cols=[4])

    assert set(result.keys()) == {"x", "y", "c4"}
    np.testing.assert_allclose(result["c4"], [100.0, 200.0, 300.0])


def test_extract_columns_out_of_bounds_low_raises(tmp_path):
    table = _make_table(tmp_path)

    # A negative column index is still out of bounds. (Column 0 is now valid --
    # it is GLE's synthesized point index; see the dedicated test below.)
    with pytest.raises(ColumnExtractionError):
        extract_columns(table, x_col_1based=-1, y_col_1based=2)


def test_extract_columns_column_zero_is_point_index(tmp_path):
    # GLE column 0 denotes the synthesized 1-based point index (used when a
    # data command has no x column, e.g. a single-column file / NOX).
    table = _make_table(tmp_path)

    result = extract_columns(table, x_col_1based=0, y_col_1based=2)

    np.testing.assert_allclose(result["x"], np.arange(1, table.n_rows + 1))


def test_extract_columns_out_of_bounds_high_raises(tmp_path):
    table = _make_table(tmp_path)

    with pytest.raises(ColumnExtractionError):
        extract_columns(table, x_col_1based=1, y_col_1based=99)


def test_extract_columns_non_numeric_raises(tmp_path):
    table = _make_table(tmp_path)

    # Column 3 is "label", a non-numeric (object dtype) column.
    with pytest.raises(ColumnExtractionError):
        extract_columns(table, x_col_1based=1, y_col_1based=3)


def test_extract_columns_non_numeric_extra_col_raises(tmp_path):
    table = _make_table(tmp_path)

    with pytest.raises(ColumnExtractionError):
        extract_columns(table, x_col_1based=1, y_col_1based=2, extra_cols=[3])


def test_extract_columns_missing_values_are_nan(tmp_path):
    p = _write(tmp_path, "m.csv", "x,y\n1,*\n2,5\n")
    table = load_data_file(p)

    result = extract_columns(table, x_col_1based=1, y_col_1based=2)

    assert np.isnan(result["y"][0])
    assert result["y"][1] == 5.0


# ---------------------------------------------------------------------------
# classify_data_file
# ---------------------------------------------------------------------------


def test_classify_with_import_list_membership(tmp_path):
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "data_1.dat", import_list=["data_1.dat"]) == "import"
    assert classify_data_file(gle_path, "external.dat", import_list=["data_1.dat"]) == "reference"


def test_classify_with_import_list_matches_bare_filename(tmp_path):
    gle_path = tmp_path / "plot.gle"

    # import_list entries may be bare names or full paths; referenced_name
    # may likewise be given as a relative path -- match on both forms.
    assert (
        classify_data_file(
            gle_path, "subdir/data_1.dat", import_list=["data_1.dat"]
        )
        == "import"
    )


def test_classify_with_import_list_empty_list_means_reference(tmp_path):
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "anything_1.dat", import_list=[]) == "reference"


def test_classify_no_metadata_is_always_reference(tmp_path):
    """Finding 1: with no metadata block (import_list is None) EVERY
    reference is classified 'reference' -- conservative by design so a
    hand-authored .gle can never cause gleplot to adopt and rewrite a
    user's data file. The old filename heuristic is gone.
    """
    gle_path = tmp_path / "plot.gle"

    # Names that used to match the sidecar heuristic are now 'reference'.
    assert classify_data_file(gle_path, "data_1.dat", import_list=None) == "reference"
    assert classify_data_file(gle_path, "mystudy_42.dat", import_list=None) == "reference"
    # Ordinary names were always 'reference'; still are.
    assert classify_data_file(gle_path, "readings.dat", import_list=None) == "reference"
    assert classify_data_file(gle_path, "data.dat", import_list=None) == "reference"
    # Subdirectory / absolute references -- still 'reference'.
    assert classify_data_file(gle_path, "sub/data_1.dat", import_list=None) == "reference"
    absolute = tmp_path / "data_1.dat"
    assert classify_data_file(gle_path, str(absolute), import_list=None) == "reference"


def test_classify_no_metadata_ordinary_user_file_not_overwritten(tmp_path):
    """Finding 1 root fix: an ordinary user file whose name happens to
    look like a sidecar (results_2024.dat) sitting next to a
    metadata-less .gle is classified 'reference', NOT 'import'. This is
    the eliminated silent-user-data-overwrite false positive.
    """
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "results_2024.dat", import_list=None) == "reference"


def test_classify_vouched_by_import_list_is_import(tmp_path):
    """A file is 'import' iff the metadata block's import-data list vouches
    for it (the sole source of truth after Finding 1).
    """
    gle_path = tmp_path / "plot.gle"

    assert (
        classify_data_file(gle_path, "results_2024.dat", import_list=["results_2024.dat"])
        == "import"
    )
    # A vouched name is import even where the heuristic never would have
    # matched (no digits suffix), proving the list -- not the name -- decides.
    assert (
        classify_data_file(gle_path, "readings.dat", import_list=["readings.dat"])
        == "import"
    )


# ---------------------------------------------------------------------------
# Track E3: named column headers in generated sidecars -- data-dock benefit
# ---------------------------------------------------------------------------
#
# gleplot's own generated sidecars now carry a header row by default (see
# gleplot.axes.sanitize_column_name / gleplot.writer.GLEWriter.add_data_file).
# These tests prove load_data_file (the function the GUI's data dock combo
# boxes are built on -- see gleplot.gui.data.panel) surfaces the REAL column
# names for such a sidecar with ZERO changes needed on the GUI side: the dock
# already renders whatever load_data_file().column_names contains.


def test_load_data_file_surfaces_gleplot_header_names(tmp_path):
    """A gleplot-generated sidecar's header row becomes DataTable.column_names
    verbatim (not the synthesized 'col1'/'col2' placeholders), so a GUI data
    dock built on load_data_file shows the real names automatically.
    """
    p = _write(tmp_path, "series.dat", "x signal\n1 2\n2 4\n3 6\n")

    table = load_data_file(p)

    assert table.has_header is True
    assert table.column_names == ["x", "signal"]
    assert table.numeric_column_names() == ["x", "signal"]


def test_load_data_file_surfaces_gleplot_writer_output_end_to_end(tmp_path):
    """End-to-end: gleplot.writer.GLEWriter.add_data_file's own header-row
    output, round-tripped through load_data_file, yields the exact names
    that were passed in -- proving the writer and the loader agree on
    format with no adapter needed.
    """
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_data_file(
        "series.dat",
        [np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 6.0]), np.array([0.1, 0.2, 0.3])],
        column_names=["x", "signal", "err"],
    )
    p = tmp_path / "series.dat"
    p.write_text(writer.data_files["series.dat"], encoding="utf-8")

    table = load_data_file(p)

    assert table.column_names == ["x", "signal", "err"]
    assert table.n_rows == 3
    assert table.numeric_column_names() == ["x", "signal", "err"]


def test_load_data_file_renamed_column_survives(tmp_path):
    """A user-renamed column header (as it would be after an edit + resave)
    is exactly what the dock sees -- sanitized names are not re-derived on
    load, the header row is authoritative.
    """
    p = _write(tmp_path, "series.dat", "time amplitude_mv\n0 1\n1 2\n")

    table = load_data_file(p)

    assert table.column_names == ["time", "amplitude_mv"]


# ---------------------------------------------------------------------------
# Comment-line column-header recovery (bug report: GLE-style fit-parameter
# exports carry column names in a trailing COMMENT line, not an inline
# header row). See gleplot.dataio._recover_comment_header.
# ---------------------------------------------------------------------------


def test_comment_header_recovered_after_multi_comment_block(tmp_path):
    """Real-world shape from the bug report: several prose/parameter
    comment lines, then a final comment line naming the columns, then
    numeric data with no inline header. The last comment line's tokens
    become column_names; has_header stays False (still a comment) and
    header_source records where the names came from.
    """
    content = (
        "! Fit parameter data for GLE export\n"
        "! Global fitting parameters:\n"
        "!   A_1 (%) = 11.8654 +/- 0.0543966\n"
        "! x y\n"
        "1.0 2.0\n"
        "2.0 4.0\n"
        "3.0 6.0\n"
    )
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["x", "y"]
    assert table.header_source == "comment"
    assert table.n_rows == 3
    np.testing.assert_allclose(table.columns[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(table.columns[1], [2.0, 4.0, 6.0])


def test_comment_header_rejected_trailing_prose_comment(tmp_path):
    """The LAST comment line before the data is prose, not column names
    ('Global fitting parameters:' -- one token, mismatched against 2 data
    columns) -- rejected, positional col1/col2 names used instead.
    """
    content = (
        "! Fit parameter data for GLE export\n"
        "! Global fitting parameters:\n"
        "1.0 2.0\n"
        "2.0 4.0\n"
    )
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["col1", "col2"]
    assert table.header_source is None


def test_comment_header_rejected_mismatched_token_count(tmp_path):
    """A comment line naming only 1 column above 2 data columns is
    rejected (token count must equal the data column count exactly).
    """
    content = "! x\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["col1", "col2"]
    assert table.header_source is None


def test_comment_header_rejected_all_numeric_comment(tmp_path):
    """A comment line that is itself all-numeric tokens (e.g. a stray
    results line someone commented out) is not mistaken for column names
    -- same 'genuine label' rule as ordinary header detection.
    """
    content = "! 9.9 8.8\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["col1", "col2"]
    assert table.header_source is None


def test_comment_header_inline_header_takes_precedence(tmp_path):
    """When the file already HAS an inline header row, comment-header
    recovery must never run at all -- the inline header always wins, even
    if a preceding comment line also looks like plausible column names.
    """
    content = "! a b\nx y\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is True
    assert table.column_names == ["x", "y"]
    assert table.header_source == "row"


def test_comment_header_not_attempted_when_inline_header_mismatched(tmp_path):
    """A mismatched inline header (e.g. whitespace-split multi-word names)
    is still a real header row -- comment-header recovery must not
    second-guess it even though has_header ends up reporting True with
    positional names.
    """
    content = "! p q\nTemperature (K) Resistance (Ohm)\n1.0 100.0\n2.0 200.0\n"
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is True
    assert table.column_names == ["col1", "col2"]
    assert table.header_source == "row"


def test_comment_header_blank_lines_tolerated_between_comment_and_data(tmp_path):
    """Blank lines between the comment header and the first data row are
    tolerated -- 'immediately preceding' walks back past blanks.
    """
    content = "! x y\n\n\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["x", "y"]
    assert table.header_source == "comment"


def test_comment_header_delimited_file(tmp_path):
    """Comment-header recovery also applies to delimited (comma) files --
    tokenization uses the SAME delimiter logic as the data rows.
    """
    content = "! x,signal\n1.0,2.0\n2.0,4.0\n"
    p = _write(tmp_path, "fit.csv", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.delimiter == ","
    assert table.column_names == ["x", "signal"]
    assert table.header_source == "comment"


def test_comment_header_no_comment_line_no_recovery(tmp_path):
    """No comment line at all -- ordinary headerless file, unaffected."""
    p = _write(tmp_path, "plain.dat", "1.0 2.0\n3.0 4.0\n")

    table = load_data_file(p)

    assert table.has_header is False
    assert table.column_names == ["col1", "col2"]
    assert table.header_source is None


def test_comment_header_not_immediately_preceding_is_rejected(tmp_path):
    """A comment line that is NOT immediately before the first data row
    (something else -- here, more comments only, so this is somewhat
    degenerate) -- specifically: a comment line separated from the first
    data row by a non-comment/non-blank line never happens in practice
    (that line would itself be data), so this test instead confirms that
    only the LAST qualifying comment line (nearest the data) is used, not
    an earlier one with a different, non-matching token count.
    """
    content = (
        "! one\n"
        "! x y\n"
        "1.0 2.0\n"
        "3.0 4.0\n"
    )
    p = _write(tmp_path, "fit.dat", content)

    table = load_data_file(p)

    assert table.column_names == ["x", "y"]
    assert table.header_source == "comment"


# ---------------------------------------------------------------------------
# Indexed comment-header recovery ('! c N = name' block): a stricter,
# unambiguous sibling of the last-comment-line heuristic above. See
# gleplot.dataio._recover_indexed_comment_header.
# ---------------------------------------------------------------------------


def test_indexed_comment_header_recovered(tmp_path):
    """Real-world shape: a prose preamble, one 'c N = name' line per column,
    a separator comment, then an aligned prose name row whose token count
    does NOT match the column count (so it could never qualify under the
    positional last-comment-line heuristic on its own) -- then numeric data.
    The indexed block alone is sufficient to recover full column_names.
    """
    content = (
        "! some prose header\n"
        "!   c 1 = run_id\n"
        "!   c 2 = field_strength (G)\n"
        "!   c 3 = temperature (K)\n"
        "!   c 4 = phase (rad)\n"
        "!   c 5 = amplitude (mV)\n"
        "!   c 6 = decay_rate\n"
        "!   c 7 = err_rate (unit-1)\n"
        "!\n"
        "!   run_id   field_strength(G) temperature(K) phase(rad) amplitude(mV) decay_rate err_rate\n"
        "1 100.0 0.1 0.5 1.2 0.02 0.001\n"
        "2 200.0 0.2 0.6 1.3 0.03 0.002\n"
        "3 300.0 0.3 0.7 1.4 0.04 0.003\n"
    )
    p = _write(tmp_path, "run.dat", content)

    table = load_data_file(p)

    assert table.has_header is False
    assert table.header_source == "comment"
    assert table.column_names == [
        "run_id",
        "field_strength (G)",
        "temperature (K)",
        "phase (rad)",
        "amplitude (mV)",
        "decay_rate",
        "err_rate (unit-1)",
    ]
    assert table.n_rows == 3


def test_indexed_comment_header_unicode_name_preserved(tmp_path):
    """A column name containing unicode (mu, superscript -1) survives intact
    into DataTable.column_names -- exercises the utf-8-sig-first decode path
    end to end.
    """
    content = (
        "! c 1 = t\n"
        "! c 2 = rate (μs⁻¹)\n"
        "0.0 1.0\n"
        "1.0 2.0\n"
    )
    p = _write(tmp_path, "unicode.dat", content, encoding="utf-8-sig")

    table = load_data_file(p)

    assert table.header_source == "comment"
    assert table.column_names == ["t", "rate (μs⁻¹)"]


def test_indexed_comment_header_case_and_whitespace_tolerant(tmp_path):
    """'c'/'C', and arbitrary whitespace around the index and '=', are all
    tolerated.
    """
    content = (
        "!C1=alpha\n"
        "!   c   2   =   beta  \n"
        "1 2\n"
        "3 4\n"
    )
    p = _write(tmp_path, "case.dat", content)

    table = load_data_file(p)

    assert table.header_source == "comment"
    # Trailing whitespace in 'beta  ' is stripped (name stripped at the ends
    # only; see docstring -- internal whitespace would be preserved).
    assert table.column_names == ["alpha", "beta"]


def test_indexed_comment_header_precedence_over_last_line_heuristic(tmp_path):
    """When BOTH an indexed 'c N = name' block and a qualifying last-comment
    -line positional header are present, the indexed block wins -- it is
    unambiguous, so it is tried FIRST regardless of what the last comment
    line looks like.
    """
    content = (
        "! c 1 = alpha\n"
        "! c 2 = beta\n"
        "! gamma delta\n"  # would qualify under the positional heuristic
        "1.0 2.0\n"
        "3.0 4.0\n"
    )
    p = _write(tmp_path, "precedence.dat", content)

    table = load_data_file(p)

    assert table.header_source == "comment"
    assert table.column_names == ["alpha", "beta"]


def test_indexed_comment_header_rejected_incomplete_coverage(tmp_path):
    """Only c2/c3 named for a 3-column file (c1 missing) -- coverage is not
    exactly 1..n_cols, so the WHOLE indexed block is rejected (no partial
    adoption); falls back to positional col1..col3.
    """
    content = "! c 2 = b\n! c 3 = c\n1 2 3\n4 5 6\n"
    p = _write(tmp_path, "incomplete.dat", content)

    table = load_data_file(p)

    assert table.header_source is None
    assert table.column_names == ["col1", "col2", "col3"]


def test_indexed_comment_header_rejected_duplicate_index(tmp_path):
    """Two lines both naming column 1 -- ambiguous, whole block rejected."""
    content = "! c 1 = a\n! c 1 = a2\n! c 2 = b\n1 2\n3 4\n"
    p = _write(tmp_path, "dup.dat", content)

    table = load_data_file(p)

    assert table.header_source is None
    assert table.column_names == ["col1", "col2"]


def test_indexed_comment_header_rejected_out_of_range_index(tmp_path):
    """A named index beyond the data's column count -- coverage can never
    be exactly 1..n_cols, so the whole block is rejected.
    """
    content = "! c 1 = a\n! c 2 = b\n! c 5 = ghost\n1 2\n3 4\n"
    p = _write(tmp_path, "oor.dat", content)

    table = load_data_file(p)

    assert table.header_source is None
    assert table.column_names == ["col1", "col2"]


def test_indexed_comment_header_inline_header_takes_precedence(tmp_path):
    """An inline header row always wins over an indexed comment block too
    (same rule as the positional heuristic) -- comment-header recovery of
    either kind is only attempted when there is no inline header at all.
    """
    content = "! c 1 = a\n! c 2 = b\nx y\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "inline_wins.dat", content)

    table = load_data_file(p)

    assert table.has_header is True
    assert table.column_names == ["x", "y"]
    assert table.header_source == "row"


def test_indexed_comment_header_leaves_has_header_false_for_vouch_safety(tmp_path):
    """Same vouch-safety invariant as the positional heuristic: an indexed
    comment-derived header must never flip has_header to True, or a vouched
    sidecar would be adopted and rewritten with a new inline header line on
    the next save (see gleplot.parser.recognizer._recovered_column_names,
    which gates strictly on has_header).
    """
    content = "! c 1 = x\n! c 2 = y\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "data_1.dat", content)

    table = load_data_file(p)

    assert table.column_names == ["x", "y"]
    assert table.header_source == "comment"
    assert table.has_header is False, (
        "indexed comment-derived column names must not be reported as an "
        "inline header row, or a vouched sidecar would be rewritten with a "
        "new header line on next save"
    )


# ---------------------------------------------------------------------------
# Vouched-sidecar round-trip safety (interaction with
# gleplot.parser.recognizer._recovered_column_names): a sidecar whose ONLY
# header is a comment-derived one must NOT be adopted as an inline header
# by the recognizer's metadata-vouch path, because that would cause the
# writer to rewrite the file with a NEW inline header line on next save,
# changing its bytes. _recovered_column_names only reads column_names when
# has_header is True, and comment-header recovery always leaves has_header
# False, so this is a property test of that invariant at the dataio level
# (the full recognizer round-trip is covered in
# tests/parser/test_recognizer_adversarial.py).
# ---------------------------------------------------------------------------


def test_comment_header_leaves_has_header_false_for_vouch_safety(tmp_path):
    """Direct dataio-level check of the interaction invariant: a
    comment-derived header must never flip has_header to True, since
    gleplot.parser.recognizer._recovered_column_names gates on has_header
    (not on column_names being non-default) to decide whether a vouched
    import series' column_names may be recovered and re-emitted as an
    inline header on next save.
    """
    content = "! x y\n1.0 2.0\n3.0 4.0\n"
    p = _write(tmp_path, "data_1.dat", content)

    table = load_data_file(p)

    assert table.column_names == ["x", "y"]
    assert table.has_header is False, (
        "comment-derived column names must not be reported as an inline "
        "header row, or a vouched sidecar would be rewritten with a new "
        "header line on next save"
    )

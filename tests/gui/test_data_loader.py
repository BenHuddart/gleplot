"""Unit tests for gleplot.gui.data.loader (pure Python, no Qt).

Covers delimiter sniffing (comma/tab/semicolon/whitespace), header
detection, comment-line skipping, missing-value tokens, mixed string
columns, ragged-row padding with warnings, BOM handling, and small
edge-case files (single column, single row).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from gleplot.gui.data.loader import DataTable, load_data_file


def _write(tmp_path: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding=encoding)
    return p


def test_comma_with_header(tmp_path):
    p = _write(tmp_path, "a.csv", "x,y,z\n1,2,3\n4,5,6\n")
    table = load_data_file(p)
    assert table.has_header is True
    assert table.column_names == ["x", "y", "z"]
    assert table.delimiter == ","
    assert table.n_rows == 2
    assert all(table.is_numeric)
    np.testing.assert_allclose(table.columns[0], [1.0, 4.0])
    np.testing.assert_allclose(table.columns[2], [3.0, 6.0])


def test_whitespace_no_header(tmp_path):
    p = _write(tmp_path, "a.dat", "1 2 3\n4 5 6\n7 8 9\n")
    table = load_data_file(p)
    assert table.has_header is False
    assert table.column_names == ["col1", "col2", "col3"]
    assert table.delimiter == r"\s+"
    assert table.n_rows == 3
    np.testing.assert_allclose(table.columns[1], [2.0, 5.0, 8.0])


def test_whitespace_multiple_spaces(tmp_path):
    p = _write(tmp_path, "a.dat", "1.0    2.0     3.0\n4.0  5.0  6.0\n")
    table = load_data_file(p)
    assert table.has_header is False
    assert table.n_rows == 2
    np.testing.assert_allclose(table.columns[0], [1.0, 4.0])


def test_tab_delimited(tmp_path):
    p = _write(tmp_path, "a.tsv", "time\tsignal\n0.0\t1.5\n1.0\t2.5\n")
    table = load_data_file(p)
    assert table.delimiter == "\t"
    assert table.has_header is True
    assert table.column_names == ["time", "signal"]
    np.testing.assert_allclose(table.columns[1], [1.5, 2.5])


def test_semicolon_delimited(tmp_path):
    p = _write(tmp_path, "a.csv", "x;y\n1;2\n3;4\n5;6\n")
    table = load_data_file(p)
    assert table.delimiter == ";"
    assert table.has_header is True
    np.testing.assert_allclose(table.columns[0], [1.0, 3.0, 5.0])


def test_comment_lines_hash_and_bang(tmp_path):
    p = _write(
        tmp_path,
        "a.dat",
        "# a comment\n! another comment\nx,y\n1,2\n# mid-file comment\n3,4\n",
    )
    table = load_data_file(p)
    assert table.has_header is True
    assert table.column_names == ["x", "y"]
    assert table.n_rows == 2
    np.testing.assert_allclose(table.columns[0], [1.0, 3.0])
    np.testing.assert_allclose(table.columns[1], [2.0, 4.0])


def test_missing_value_tokens(tmp_path):
    p = _write(
        tmp_path,
        "a.csv",
        "x,y,z,w\n1,*,3,?\n4,5,-,.\n7,nan,NaN,8\n,10,11,12\n",
    )
    table = load_data_file(p)
    assert table.has_header is True
    assert all(table.is_numeric)
    y = table.columns[1]
    assert np.isnan(y[0])
    assert y[1] == 5.0
    assert np.isnan(y[2])
    z = table.columns[2]
    assert z[0] == 3.0
    assert np.isnan(z[1])
    assert np.isnan(z[2])
    w = table.columns[3]
    assert np.isnan(w[0])
    assert np.isnan(w[1])
    assert w[2] == 8.0
    x = table.columns[0]
    assert np.isnan(x[3])


def test_mixed_string_column(tmp_path):
    p = _write(tmp_path, "a.csv", "label,value\nfoo,1\nbar,2\nbaz,3\n")
    table = load_data_file(p)
    assert table.is_numeric == [False, True]
    assert table.numeric_column_names() == ["value"]
    assert table.numeric_column_indices() == [1]
    label_col = table.columns[0]
    assert list(label_col) == ["foo", "bar", "baz"]
    np.testing.assert_allclose(table.columns[1], [1.0, 2.0, 3.0])


def test_ragged_rows_padded_with_warning(tmp_path):
    p = _write(tmp_path, "a.csv", "x,y,z\n1,2,3\n4,5\n6,7,8,9\n")
    table = load_data_file(p)
    assert table.n_rows == 3
    assert len(table.warnings) >= 1
    # max_cols should be 4 because of the row with an extra field.
    assert table.n_cols == 4
    # Second data row ("4,5") should be padded with NaN in the missing slots.
    row1 = [col[1] for col in table.columns[:3]]
    assert row1[0] == 4.0
    assert row1[1] == 5.0
    assert np.isnan(row1[2])


def test_utf8_bom(tmp_path):
    content = "x,y\n1,2\n3,4\n"
    p = tmp_path / "bom.csv"
    p.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    table = load_data_file(p)
    assert table.column_names == ["x", "y"]
    assert table.n_rows == 2


def test_latin1_fallback(tmp_path):
    p = tmp_path / "latin1.csv"
    # 'café' encoded as latin-1 is not valid utf-8, so this exercises the
    # fallback decode path.
    content = "label,value\ncafé,1\n"
    p.write_bytes(content.encode("latin-1"))
    table = load_data_file(p)
    assert table.n_rows == 1
    assert table.columns[0][0] == "café"


def test_single_column_file(tmp_path):
    p = _write(tmp_path, "a.dat", "1\n2\n3\n4\n")
    table = load_data_file(p)
    assert table.n_cols == 1
    assert table.has_header is False
    np.testing.assert_allclose(table.columns[0], [1.0, 2.0, 3.0, 4.0])


def test_single_row_file(tmp_path):
    p = _write(tmp_path, "a.csv", "x,y,z\n1,2,3\n")
    table = load_data_file(p)
    assert table.n_rows == 1
    np.testing.assert_allclose(table.columns[0], [1.0])
    np.testing.assert_allclose(table.columns[2], [3.0])


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data_file(tmp_path / "does_not_exist.csv")


def test_empty_file_raises(tmp_path):
    p = _write(tmp_path, "empty.csv", "")
    with pytest.raises(ValueError):
        load_data_file(p)


def test_max_preview_rows(tmp_path):
    lines = "x,y\n" + "".join(f"{i},{i*2}\n" for i in range(50))
    p = _write(tmp_path, "big.csv", lines)
    table = load_data_file(p, max_preview_rows=10)
    assert table.n_rows == 10


def test_numeric_header_row_not_misdetected(tmp_path):
    # A header consisting purely of numbers is ambiguous, but since GLE data
    # files rarely have numeric-looking headers, the loader should treat the
    # first row as data when every field parses as a float.
    p = _write(tmp_path, "a.csv", "1,2,3\n4,5,6\n")
    table = load_data_file(p)
    assert table.has_header is False
    assert table.n_rows == 2


# ---------------------------------------------------------------------------
# Finding 2: an all-missing first row is DATA (all-NaN), not a header.
# ---------------------------------------------------------------------------


def test_all_missing_first_row_is_data_not_header(tmp_path):
    # First row '* * *' is entirely missing-value tokens -> it must be kept as
    # an all-NaN DATA row, NOT consumed as a header (regression: missing tokens
    # fail float conversion, but a missing token is not a real label).
    p = _write(tmp_path, "a.dat", "* * *\n1 2 3\n4 5 6\n")
    table = load_data_file(p)
    assert table.has_header is False
    assert table.n_rows == 3
    assert table.n_cols == 3
    # First row is all NaN, preserved as data.
    for col in table.columns:
        assert np.isnan(col[0])
    np.testing.assert_allclose(table.columns[0][1:], [1.0, 4.0])


def test_real_header_still_detected_alongside_finding2(tmp_path):
    # A genuine text header must still be detected as a header (the Finding 2
    # fix only excludes all-missing rows, not real labels).
    p = _write(tmp_path, "a.dat", "x y z\n1 2 3\n4 5 6\n")
    table = load_data_file(p)
    assert table.has_header is True
    assert table.column_names == ["x", "y", "z"]
    assert table.n_rows == 2


def test_partially_missing_first_row_with_label_is_header(tmp_path):
    # A row mixing a real label with missing tokens ('name * *') still counts
    # as a header (at least one field is a genuine non-numeric label).
    p = _write(tmp_path, "a.dat", "name * *\n1 2 3\n")
    table = load_data_file(p)
    assert table.has_header is True
    assert table.n_rows == 1


# ---------------------------------------------------------------------------
# Finding 3: multi-word header token count mismatch -> positional names + warn.
# ---------------------------------------------------------------------------


def test_whitespace_multiword_header_mismatch_uses_positional_names(tmp_path):
    # Whitespace-delimited header 'Temperature (K) Resistance (Ohm)' splits
    # into 4 tokens over 2 data columns -> the row is still skipped as a
    # header, but positional names are synthesized and a warning is recorded.
    content = "Temperature (K) Resistance (Ohm)\n1.0 100.0\n2.0 200.0\n"
    p = _write(tmp_path, "a.dat", content)
    table = load_data_file(p)
    assert table.has_header is True
    assert table.n_cols == 2
    assert table.column_names == ["col1", "col2"]
    # The two data rows survive (header consumed, not treated as data).
    assert table.n_rows == 2
    np.testing.assert_allclose(table.columns[0], [1.0, 2.0])
    np.testing.assert_allclose(table.columns[1], [100.0, 200.0])
    assert any(
        "does not align" in w or "positional" in w for w in table.warnings
    )


def test_delimited_multiword_header_unaffected(tmp_path):
    # For a COMMA-delimited file the same multi-word names are single fields,
    # so the header aligns 1:1 with the columns and is used verbatim (no
    # positional fallback, no mismatch warning).
    content = "Temperature (K),Resistance (Ohm)\n1.0,100.0\n2.0,200.0\n"
    p = _write(tmp_path, "a.csv", content)
    table = load_data_file(p)
    assert table.delimiter == ","
    assert table.has_header is True
    assert table.column_names == ["Temperature (K)", "Resistance (Ohm)"]
    assert not any(
        "does not align" in w or "positional" in w for w in table.warnings
    )


# ---------------------------------------------------------------------------
# Comment-line column-header recovery (bug report): a real-world .dat file
# with GLE-style comment-only metadata (fit parameters etc.) whose LAST
# comment line before the data actually names the columns. The Data dock's
# combo boxes are built directly on load_data_file().column_names (see
# gleplot.gui.data.panel), so this is exactly the surface the reported bug
# (dock showing col1/col2 instead of real names) is fixed through.
# ---------------------------------------------------------------------------


def test_comment_header_names_surface_for_data_dock(tmp_path):
    content = (
        "! Fit parameter data for GLE export\n"
        "! Global fitting parameters:\n"
        "!   A_1 (%) = 11.8654 +/- 0.0543966\n"
        "! temperature resistance\n"
        "1.0 2.0\n"
        "2.0 4.0\n"
    )
    p = _write(tmp_path, "fit.dat", content)
    table = load_data_file(p)
    # The dock reads table.column_names directly and unconditionally --
    # this is the exact fix for the reported "shows col1/col2" bug.
    assert table.column_names == ["temperature", "resistance"]
    assert table.has_header is False
    assert table.header_source == "comment"
    assert table.numeric_column_names() == ["temperature", "resistance"]


def test_comment_header_rejected_mismatched_count_dock_sees_positional(tmp_path):
    # A comment line with the wrong token count is rejected -- the dock
    # falls back to the same positional col1/col2 names as any other
    # headerless file, matching pre-fix behavior (no regression for
    # genuinely non-header comment lines).
    content = "! Global fitting parameters:\n1.0 2.0\n2.0 4.0\n"
    p = _write(tmp_path, "fit.dat", content)
    table = load_data_file(p)
    assert table.column_names == ["col1", "col2"]
    assert table.header_source is None

"""Unit tests for gleplot.dataio: loading, resolution, and classification.

Covers:
- Shim equivalence: gleplot.gui.data.loader re-exports the exact same
  DataTable/load_data_file objects (proves the shim didn't fork behavior).
- Qt-freeness: importing gleplot.dataio must not import PySide6 or
  gleplot.gui.
- resolve_data_reference: relative/absolute/missing/unreadable/malformed.
- extract_columns: happy path, out-of-bounds, non-numeric.
- classify_data_file: metadata-list-driven and heuristic-driven
  (including the documented false-positive case).

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


def test_classify_heuristic_sidecar_pattern_is_import(tmp_path):
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "data_1.dat", import_list=None) == "import"
    assert classify_data_file(gle_path, "mystudy_42.dat", import_list=None) == "import"


def test_classify_heuristic_non_matching_name_is_reference(tmp_path):
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "readings.dat", import_list=None) == "reference"
    assert classify_data_file(gle_path, "data.dat", import_list=None) == "reference"


def test_classify_heuristic_subdirectory_is_reference(tmp_path):
    gle_path = tmp_path / "plot.gle"

    # Even a name matching the sidecar pattern is 'reference' if it's not
    # in the same directory as the .gle file -- gleplot always writes
    # sidecars alongside the script.
    assert classify_data_file(gle_path, "sub/data_1.dat", import_list=None) == "reference"


def test_classify_heuristic_absolute_path_is_reference(tmp_path):
    gle_path = tmp_path / "plot.gle"
    absolute = tmp_path / "data_1.dat"

    assert classify_data_file(gle_path, str(absolute), import_list=None) == "reference"


def test_classify_heuristic_false_positive_documented_case(tmp_path):
    """Documented false-positive: an ordinary user file that happens to
    match '<prefix>_<digits>.dat' in the same directory as the script is
    misclassified as 'import' by the heuristic. This is expected/known
    behavior (see classify_data_file's docstring) -- callers should
    prefer passing import_list when available to avoid it.
    """
    gle_path = tmp_path / "plot.gle"

    assert classify_data_file(gle_path, "results_2024.dat", import_list=None) == "import"


def test_classify_heuristic_false_positive_avoided_with_import_list(tmp_path):
    """The same false-positive-prone name is correctly classified as
    'reference' once the caller supplies the authoritative import_list.
    """
    gle_path = tmp_path / "plot.gle"

    assert (
        classify_data_file(gle_path, "results_2024.dat", import_list=["data_1.dat"])
        == "reference"
    )

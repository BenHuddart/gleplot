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

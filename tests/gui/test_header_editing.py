"""Tests for Track G1: editable column headers in DataPanel (offscreen Qt).

Covers the ownership rule (figure-owned sidecar vs. external reference vs.
user-loaded-in-memory), the rename UX entry point (``_on_header_double_clicked``
/ ``_rename_column``), propagation to the DataTable/preview header/combos/
series ``column_names``, validation (sanitize/uniqueness/float rejection),
no-op-on-unchanged, and persistence through a save+reparse round trip.

Follows the local-stub-document pattern from ``tests/gui/test_data_panel.py``.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.gui.data.panel import DataPanel, _EXTERNAL_HEADER_TOOLTIP


class StubDocument(QObject):
    """Minimal duck-typed FigureDocument stub wrapping a real Figure."""

    figure_changed = Signal()
    figure_replaced = Signal()
    project_path_changed = Signal(str)

    def __init__(self, figure=None, project_path=None):
        super().__init__()
        self._figure = figure
        self.project_path = project_path
        self.notify_changed_count = 0

    @property
    def figure(self):
        return self._figure

    @figure.setter
    def figure(self, value):
        self._figure = value

    def notify_changed(self):
        self.notify_changed_count += 1
        self.figure_changed.emit()


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def figure():
    fig = glp.figure()
    fig.add_subplot(111)
    return fig


@pytest.fixture
def document(figure):
    return StubDocument(figure)


def _write_csv(tmp_path: Path, name: str = "data.csv") -> Path:
    p = tmp_path / name
    p.write_text("x,y,yerr\n1,2,0.1\n2,4,0.2\n3,6,0.3\n4,8,0.4\n")
    return p


def _select_only_item(panel):
    """Select the panel's sole file-list item (mirrors user click)."""
    assert panel.file_list.count() == 1
    panel.file_list.setCurrentItem(panel.file_list.item(0))


def _opened_document_with_sidecar(tmp_path, label="squares"):
    """A document wrapping a figure parsed back from a real savefig_gle.

    The resulting import-mode line series' data_file is the regenerated
    sidecar (e.g. "ownfig_0.dat"), making it FIGURE-OWNED once the panel's
    populate_from_figure resolves it against project_path.
    """
    from gleplot.parser.recognizer import parse_gle_figure

    fig = glp.figure(data_prefix="ownfig")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0.0, 1.0, 2.0], [0.0, 1.0, 4.0], label=label)
    gle_path = tmp_path / "ownfig.gle"
    fig.savefig_gle(str(gle_path))
    rec = parse_gle_figure(gle_path)
    doc = StubDocument(rec.figure, project_path=gle_path)
    return doc, gle_path


# ----------------------------------------------------------------------
# Ownership / editability matrix
# ----------------------------------------------------------------------
class TestEditabilityMatrix:
    def test_figure_owned_sidecar_is_editable(self, qapp, tmp_path):
        doc, gle_path = _opened_document_with_sidecar(tmp_path)
        panel = DataPanel(doc)
        panel.populate_from_figure()
        _select_only_item(panel)

        assert panel._is_editable_table(panel._current_key) is True
        assert len(panel._owning_series_for_key(panel._current_key)) == 1

    def test_user_loaded_not_yet_referenced_is_editable(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        panel.load_file(str(csv_path))
        _select_only_item(panel)

        assert panel._is_editable_table(panel._current_key) is True
        # Not figure-owned (no series references it at all).
        assert panel._owning_series_for_key(panel._current_key) == []

    def test_file_series_referenced_external_is_not_editable(
        self, qapp, document, figure, tmp_path
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        panel.load_file(str(csv_path))
        _select_only_item(panel)

        panel.mode_combo.setCurrentText("Reference file")
        panel.plot_type_combo.setCurrentText("Line")
        x_idx = panel.x_combo.findText("x")
        y_idx = panel.y_combo.findText("y")
        panel.x_combo.setCurrentIndex(x_idx)
        panel.y_combo.setCurrentIndex(y_idx)
        panel.add_series()

        assert panel._is_editable_table(panel._current_key) is False
        assert panel._is_referenced_externally(panel._current_key) is True

    def test_header_tooltip_set_for_external_file(self, qapp, document, figure, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        panel.load_file(str(csv_path))
        _select_only_item(panel)

        panel.mode_combo.setCurrentText("Reference file")
        x_idx = panel.x_combo.findText("x")
        y_idx = panel.y_combo.findText("y")
        panel.x_combo.setCurrentIndex(x_idx)
        panel.y_combo.setCurrentIndex(y_idx)
        panel.add_series()

        # Re-select to force _populate_preview to re-run with the now
        # up-to-date ownership state.
        panel.file_list.setCurrentItem(None)
        _select_only_item(panel)

        header_item = panel.preview_table.horizontalHeaderItem(0)
        assert header_item.toolTip() == _EXTERNAL_HEADER_TOOLTIP


# ----------------------------------------------------------------------
# Rename happy path + propagation
# ----------------------------------------------------------------------
class TestRenamePropagation:
    def test_rename_user_loaded_table_updates_table_header_and_combos(
        self, qapp, document, tmp_path
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        y_idx = table.column_names.index("y")
        panel._rename_column(panel._current_key, table, y_idx, "Height (cm)")

        assert table.column_names[y_idx] == "height_cm"
        header_item = panel.preview_table.horizontalHeaderItem(y_idx)
        assert header_item.text() == "height_cm"
        # Combo item text updated at the same 0-based index.
        combo_idx = panel.y_combo.findData(y_idx)
        assert panel.y_combo.itemText(combo_idx) == "height_cm"

    def test_rename_preserves_current_combo_selections(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        yerr_idx = table.column_names.index("yerr")
        sel = panel.yerr_combo.findText("yerr")
        panel.yerr_combo.setCurrentIndex(sel)

        panel._rename_column(panel._current_key, table, yerr_idx, "sigma")

        # Selection (by underlying column index) survives the text change.
        assert panel.yerr_combo.currentData() == yerr_idx
        assert panel.yerr_combo.currentText() == "sigma"

    def test_rename_figure_owned_sidecar_propagates_to_series_column_names(
        self, qapp, tmp_path
    ):
        doc, gle_path = _opened_document_with_sidecar(tmp_path)
        panel = DataPanel(doc)
        panel.populate_from_figure()
        _select_only_item(panel)

        table = panel._current_table
        key = panel._current_key
        y_idx = 1  # ['x', 'squares'] for a labeled line -> index 1 is primary y
        before_count = doc.notify_changed_count

        panel._rename_column(key, table, y_idx, "Renamed Y")

        assert table.column_names[y_idx] == "renamed_y"
        owners = panel._owning_series_for_key(key)
        assert len(owners) == 1
        assert owners[0]["column_names"][y_idx] == "renamed_y"
        # Label (legend text) must NOT be retroactively renamed.
        assert owners[0]["label"] == "squares"
        assert doc.notify_changed_count == before_count + 1

    def test_column_renamed_signal_emitted_with_1based_index(
        self, qapp, document, tmp_path
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        received = []
        panel.column_renamed.connect(lambda *args: received.append(args))

        y_idx = table.column_names.index("y")
        panel._rename_column(panel._current_key, table, y_idx, "height")

        assert len(received) == 1
        key, one_based_idx, new_name = received[0]
        assert key == panel._current_key
        assert one_based_idx == y_idx + 1
        assert new_name == "height"


# ----------------------------------------------------------------------
# Validation: sanitize / uniqueness / float rejection / no-op
# ----------------------------------------------------------------------
class TestValidation:
    def test_rename_sanitizes_punctuation_and_case(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        panel._rename_column(panel._current_key, table, 0, "My Column!!")
        assert table.column_names[0] == "my_column"

    def test_rename_rejects_name_that_parses_as_float(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        panel._rename_column(panel._current_key, table, 0, "2024")
        # sanitize_column_name prefixes numeric-looking results with the
        # fallback ("col"), so the header can never look like a data value.
        assert table.column_names[0] != "2024"
        assert not table.column_names[0].replace("_", "").isdigit()

    def test_rename_auto_suffixes_on_collision(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        # Rename "yerr" (index 2) to collide with existing "y" (index 1).
        panel._rename_column(panel._current_key, table, 2, "y")

        assert table.column_names[1] == "y"
        assert table.column_names[2] == "y_2"

    def test_rename_noop_when_unchanged_after_sanitization(
        self, qapp, document, tmp_path
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        received = []
        panel.column_renamed.connect(lambda *args: received.append(args))
        before = document.notify_changed_count

        panel._rename_column(panel._current_key, table, 0, "X")  # sanitizes to "x"

        assert table.column_names[0] == "x"
        assert document.notify_changed_count == before
        assert received == []


# ----------------------------------------------------------------------
# Double-click entry point
# ----------------------------------------------------------------------
class TestHeaderDoubleClickEntryPoint:
    def test_double_click_on_external_header_shows_message_and_does_not_rename(
        self, qapp, document, figure, tmp_path, monkeypatch
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        panel.load_file(str(csv_path))
        _select_only_item(panel)

        panel.mode_combo.setCurrentText("Reference file")
        x_idx = panel.x_combo.findText("x")
        y_idx = panel.y_combo.findText("y")
        panel.x_combo.setCurrentIndex(x_idx)
        panel.y_combo.setCurrentIndex(y_idx)
        panel.add_series()
        panel.file_list.setCurrentItem(None)
        _select_only_item(panel)

        shown = []
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "information", lambda *a, **k: shown.append(a)
        )

        original_names = list(panel._current_table.column_names)
        panel._on_header_double_clicked(0)

        assert len(shown) == 1
        assert panel._current_table.column_names == original_names

    def test_double_click_on_editable_header_prompts_and_renames(
        self, qapp, document, tmp_path, monkeypatch
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        from PySide6.QtWidgets import QInputDialog

        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("new name", True)
        )

        panel._on_header_double_clicked(0)

        assert table.column_names[0] == "new_name"

    def test_double_click_cancelled_dialog_does_not_rename(
        self, qapp, document, tmp_path, monkeypatch
    ):
        panel = DataPanel(document)
        csv_path = _write_csv(tmp_path)
        table = panel.load_file(str(csv_path))
        _select_only_item(panel)

        from PySide6.QtWidgets import QInputDialog

        monkeypatch.setattr(
            QInputDialog, "getText", lambda *a, **k: ("ignored", False)
        )

        panel._on_header_double_clicked(0)

        assert table.column_names[0] == "x"


# ----------------------------------------------------------------------
# Persistence through save + reopen
# ----------------------------------------------------------------------
class TestPersistence:
    def test_renamed_header_persists_through_save_and_reparse(self, qapp, tmp_path):
        from gleplot.parser.recognizer import parse_gle_figure

        doc, gle_path = _opened_document_with_sidecar(tmp_path)
        panel = DataPanel(doc)
        panel.populate_from_figure()
        _select_only_item(panel)

        table = panel._current_table
        key = panel._current_key
        panel._rename_column(key, table, 1, "Distance")

        # Re-save: the writer reads column_names straight off the series
        # dict, which _rename_column mutated in place.
        doc.notify_changed()
        fig = doc.figure
        fig.savefig_gle(str(gle_path))

        sidecar_text = (tmp_path / "ownfig_0.dat").read_text()
        header_line = sidecar_text.splitlines()[0]
        assert "distance" in header_line.split()

        # Reopen: the recognizer recovers column_names from the sidecar's
        # header row for the reparsed series.
        rec = parse_gle_figure(gle_path)
        ax = rec.figure.axes_list[0]
        assert ax.lines[0]["column_names"][1] == "distance"

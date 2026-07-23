"""Tests for gleplot.gui.data.panel.DataPanel (offscreen Qt).

Uses a local stub "document" satisfying the duck-typed FigureDocument
contract (``.figure``, ``.notify_changed()``, ``.figure_replaced``
signal) wrapping a *real* ``gleplot.figure.Figure`` -- only the document
object itself is stubbed, per the task's testing guidance.
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
from gleplot.gui.data.panel import DataPanel


class StubDocument(QObject):
    """Minimal duck-typed FigureDocument stub wrapping a real Figure."""

    figure_changed = Signal()
    figure_replaced = Signal()

    def __init__(self, figure=None):
        super().__init__()
        self._figure = figure
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


def test_panel_constructs(qapp, document):
    panel = DataPanel(document)
    assert panel.add_series_button.isEnabled() is False  # no file loaded yet


def test_load_file_populates_table(qapp, document, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)

    table = panel.load_file(str(csv_path))

    assert table is not None
    assert panel.file_list.count() == 1
    assert panel.file_list.item(0).text() == "data.csv"
    assert panel.preview_table.rowCount() == 4
    assert panel.preview_table.columnCount() == 3
    headers = [panel.preview_table.horizontalHeaderItem(i).text() for i in range(3)]
    assert headers == ["x", "y", "yerr"]


def test_column_combos_populated_after_load(qapp, document, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    x_items = [panel.x_combo.itemText(i) for i in range(panel.x_combo.count())]
    y_items = [panel.y_combo.itemText(i) for i in range(panel.y_combo.count())]
    yerr_items = [panel.yerr_combo.itemText(i) for i in range(panel.yerr_combo.count())]

    assert x_items == ["x", "y", "yerr"]
    assert y_items == ["x", "y", "yerr"]
    assert yerr_items == ["(none)", "x", "y", "yerr"]


def test_add_series_button_enabled_with_figure_and_numeric_columns(
    qapp, document, tmp_path
):
    panel = DataPanel(document)
    assert panel.add_series_button.isEnabled() is False

    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))
    assert panel.add_series_button.isEnabled() is True


def test_add_series_button_disabled_without_figure(qapp, tmp_path):
    doc = StubDocument(figure=None)
    panel = DataPanel(doc)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    assert panel.add_series_button.isEnabled() is False


def test_add_series_button_disabled_without_numeric_columns(qapp, document, tmp_path):
    panel = DataPanel(document)
    p = tmp_path / "labels.csv"
    p.write_text("name\nfoo\nbar\n")
    panel.load_file(str(p))

    assert panel.add_series_button.isEnabled() is False


def test_default_label_follows_y_column(qapp, document, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    assert panel.label_edit.text() == panel.y_combo.currentText()

    # Changing the Y column should update the default label, since the
    # user hasn't manually edited it yet.
    idx = panel.y_combo.findText("yerr")
    panel.y_combo.setCurrentIndex(idx)
    assert panel.label_edit.text() == "yerr"


def test_label_user_edit_sticks(qapp, document, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    panel.label_edit.setText("My Custom Label")
    panel.label_edit.textEdited.emit("My Custom Label")

    idx = panel.y_combo.findText("yerr")
    panel.y_combo.setCurrentIndex(idx)
    assert panel.label_edit.text() == "My Custom Label"


def test_add_series_import_line(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    # x=x(0), y=y(1) is the default combo selection.
    panel.plot_type_combo.setCurrentText("Line")
    panel.mode_combo.setCurrentText("Import data")
    panel.label_edit.setText("My Line")

    panel.add_series()

    ax = figure.gca()
    assert len(ax.lines) == 1
    line = ax.lines[0]
    assert line["label"] == "My Line"
    assert list(line["x"]) == [1.0, 2.0, 3.0, 4.0]
    assert list(line["y"]) == [2.0, 4.0, 6.0, 8.0]
    assert document.notify_changed_count == 1


def test_add_series_import_scatter(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))
    panel.plot_type_combo.setCurrentText("Scatter")

    panel.add_series()

    ax = figure.gca()
    assert len(ax.scatters) == 1
    assert len(ax.lines) == 0


def test_add_series_import_line_with_markers(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))
    panel.plot_type_combo.setCurrentText("Line+markers")

    panel.add_series()

    ax = figure.gca()
    # "Line+markers" calls plot(marker='o') with the default solid linestyle.
    # The series lands in `lines` (it's a line, not a scatter) and — now that
    # Axes.plot() preserves markers on line datasets — the marker is stored
    # on the line series and will render via GLE's `line ... marker` support.
    assert len(ax.lines) == 1
    assert len(ax.scatters) == 0
    assert ax.lines[0]["linestyle"] == "-"
    assert ax.lines[0]["marker"] == "FCIRCLE"


def test_add_series_import_errorbar(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    panel.plot_type_combo.setCurrentText("Error bars")
    yerr_idx = panel.yerr_combo.findText("yerr")
    panel.yerr_combo.setCurrentIndex(yerr_idx)

    panel.add_series()

    ax = figure.gca()
    assert len(ax.errorbars) == 1
    eb = ax.errorbars[0]
    assert list(eb["y"]) == [2.0, 4.0, 6.0, 8.0]
    assert list(eb["yerr_up"]) == [0.1, 0.2, 0.3, 0.4]
    assert list(eb["yerr_down"]) == [0.1, 0.2, 0.3, 0.4]


def test_add_series_reference_file_line(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    panel.mode_combo.setCurrentText("Reference file")
    panel.plot_type_combo.setCurrentText("Line")
    # Defaults: x_combo -> "y" (index 1), y_combo -> "x" (index 0) per
    # panel's auto-select; explicitly set for clarity.
    x_idx = panel.x_combo.findText("x")
    y_idx = panel.y_combo.findText("y")
    panel.x_combo.setCurrentIndex(x_idx)
    panel.y_combo.setCurrentIndex(y_idx)

    panel.add_series()

    ax = figure.gca()
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert fs["series_type"] == "line"
    assert fs["data_file"] == str(csv_path.resolve())
    # x is column 0 (0-based) -> 1-based col 1; y is column 1 -> col 2.
    assert fs["x_col"] == 1
    assert fs["y_col"] == 2


def test_add_series_reference_file_errorbar_columns(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    panel.mode_combo.setCurrentText("Reference file")
    panel.plot_type_combo.setCurrentText("Error bars")

    x_idx = panel.x_combo.findText("x")
    y_idx = panel.y_combo.findText("y")
    yerr_idx = panel.yerr_combo.findText("yerr")
    panel.x_combo.setCurrentIndex(x_idx)
    panel.y_combo.setCurrentIndex(y_idx)
    panel.yerr_combo.setCurrentIndex(yerr_idx)

    panel.add_series()

    ax = figure.gca()
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert fs["series_type"] == "errorbar"
    assert fs["x_col"] == 1
    assert fs["y_col"] == 2
    assert fs["yerr_col"] == 3


def test_series_added_signal_emitted(qapp, document, figure, tmp_path):
    panel = DataPanel(document)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))
    panel.label_edit.setText("Signal Test")

    received = []
    panel.series_added.connect(received.append)

    panel.add_series()

    assert received == ["Signal Test"]


def test_figure_replaced_reevaluates_button_state(qapp, tmp_path):
    doc = StubDocument(figure=None)
    panel = DataPanel(doc)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))
    assert panel.add_series_button.isEnabled() is False

    fig = glp.figure()
    fig.add_subplot(111)
    doc.figure = fig
    doc.figure_replaced.emit()

    assert panel.add_series_button.isEnabled() is True


def test_add_series_noop_without_figure(qapp, tmp_path):
    doc = StubDocument(figure=None)
    panel = DataPanel(doc)
    csv_path = _write_csv(tmp_path)
    panel.load_file(str(csv_path))

    # Directly invoking the slot should be a safe no-op (guarded).
    panel.add_series()
    assert doc.notify_changed_count == 0


def test_load_bad_file_does_not_crash(qapp, document, tmp_path):
    panel = DataPanel(document)
    missing = tmp_path / "does_not_exist.csv"

    result = panel.load_file(str(missing))

    assert result is None
    assert panel.file_list.count() == 1
    assert "failed to load" in panel.file_list.item(0).text()


class TestPopulateFromFigure:
    """Opened figures surface their referenced data files in the panel."""

    def _opened_document(self, tmp_path, qapp):
        from gleplot.parser.recognizer import parse_gle_figure

        fig = glp.figure(data_prefix="popfig")
        ax = fig.add_subplot(1, 1, 1)
        ax.plot([0.0, 1.0, 2.0], [0.0, 1.0, 4.0], label="squares")
        gle_path = tmp_path / "popfig.gle"
        fig.savefig_gle(str(gle_path))
        rec = parse_gle_figure(gle_path)
        doc = StubDocument(rec.figure)
        doc.project_path = gle_path
        return doc, gle_path

    def test_populate_adds_referenced_sidecars(self, qapp, tmp_path):
        doc, gle_path = self._opened_document(tmp_path, qapp)
        panel = DataPanel(doc)
        assert panel.file_list.count() == 0
        panel.populate_from_figure()
        assert panel.file_list.count() == 1
        assert "popfig_0.dat" in panel.file_list.item(0).text()
        # Columns become available for adding further series.
        assert panel.x_combo.count() > 0

    def test_populate_is_additive_and_idempotent(self, qapp, tmp_path):
        doc, gle_path = self._opened_document(tmp_path, qapp)
        panel = DataPanel(doc)
        panel.populate_from_figure()
        count = panel.file_list.count()
        panel.populate_from_figure()
        assert panel.file_list.count() == count

    def test_populate_skips_missing_files(self, qapp, tmp_path):
        doc, gle_path = self._opened_document(tmp_path, qapp)
        (tmp_path / "popfig_0.dat").unlink()
        panel = DataPanel(doc)
        panel.populate_from_figure()
        assert panel.file_list.count() == 0

    def test_populate_runs_on_figure_replaced(self, qapp, tmp_path):
        doc, gle_path = self._opened_document(tmp_path, qapp)
        panel = DataPanel(doc)
        # Simulate the open flow: installing a figure emits figure_replaced.
        doc.figure_replaced.emit()
        assert panel.file_list.count() == 1


# ----------------------------------------------------------------------
# Scattered (x, y, z) heatmap / contour series (Phase B)
# ----------------------------------------------------------------------
def _write_xyz_csv(tmp_path: Path, name: str = "xyz.csv") -> Path:
    p = tmp_path / name
    p.write_text(
        "x,y,z\n0,0,1\n1,0,2\n0,1,3\n1,1,4\n0.5,0.5,2.5\n",
    )
    return p


class TestScatteredHeatmapContour:
    def test_plot_types_include_heatmap_and_contour(self, qapp, document):
        panel = DataPanel(document)
        items = [
            panel.plot_type_combo.itemText(i)
            for i in range(panel.plot_type_combo.count())
        ]
        assert "Heatmap (scattered x,y,z)" in items
        assert "Contour (scattered x,y,z)" in items

    def test_z_row_hidden_by_default_visible_for_xyz(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        # Default plot type is "Line": Z hidden, Y-error visible, mode enabled.
        # (The panel is never shown top-level in an offscreen test, so
        # isVisible() is always False; isHidden() reflects the explicit
        # setVisible state we drive.)
        assert panel.z_combo.isHidden() is True
        assert panel.yerr_combo.isHidden() is False
        assert panel.mode_combo.isEnabled() is True

        panel.plot_type_combo.setCurrentText("Heatmap (scattered x,y,z)")
        assert panel.z_combo.isHidden() is False
        assert panel.yerr_combo.isHidden() is True
        # fitz gridding needs the raw triples we write, so import mode only.
        assert panel.mode_combo.isEnabled() is False
        assert panel.mode_combo.currentText() == "Import data"

    def test_z_combo_populated(self, qapp, document, tmp_path):
        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        z_items = [panel.z_combo.itemText(i) for i in range(panel.z_combo.count())]
        assert z_items == ["x", "y", "z"]
        # Defaults to the third numeric column.
        assert panel.z_combo.currentText() == "z"

    def test_add_tripcolor_series(self, qapp, document, figure, tmp_path):
        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        panel.plot_type_combo.setCurrentText("Heatmap (scattered x,y,z)")
        panel.label_edit.setText("field")

        panel.add_series()

        ax = figure.gca()
        assert len(ax.heatmaps) == 1
        hm = ax.heatmaps[0]
        assert hm["source"] == "points"
        assert hm["label"] == "field"
        assert list(hm["zpts"]) == [1.0, 2.0, 3.0, 4.0, 2.5]
        assert document.notify_changed_count == 1

    def test_add_tricontour_series(self, qapp, document, figure, tmp_path):
        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        panel.plot_type_combo.setCurrentText("Contour (scattered x,y,z)")
        panel.label_edit.setText("levels")

        panel.add_series()

        ax = figure.gca()
        assert len(ax.contours) == 1
        ct = ax.contours[0]
        assert ct["source"] == "points"
        assert ct["label"] == "levels"
        assert len(ax.heatmaps) == 0
        assert document.notify_changed_count == 1

    def test_one_heatmap_per_axes_guard(
        self, qapp, document, figure, tmp_path, monkeypatch
    ):
        from gleplot.gui.data import panel as panel_mod

        seen = []
        monkeypatch.setattr(
            panel_mod.QMessageBox,
            "information",
            lambda *a, **k: seen.append(a),
        )

        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        panel.plot_type_combo.setCurrentText("Heatmap (scattered x,y,z)")
        panel.add_series()
        assert len(figure.gca().heatmaps) == 1
        count_after_first = document.notify_changed_count

        # A second heatmap on the same axes is refused with a message, not a
        # crash, and does not mutate the figure.
        panel.add_series()
        assert len(figure.gca().heatmaps) == 1
        assert document.notify_changed_count == count_after_first
        assert len(seen) == 1

    def test_tricontour_does_not_trip_heatmap_guard(
        self, qapp, document, figure, tmp_path
    ):
        panel = DataPanel(document)
        panel.load_file(str(_write_xyz_csv(tmp_path)))
        # A heatmap plus a contour on the same axes is allowed (separate lists).
        panel.plot_type_combo.setCurrentText("Heatmap (scattered x,y,z)")
        panel.add_series()
        panel.plot_type_combo.setCurrentText("Contour (scattered x,y,z)")
        panel.add_series()
        assert len(figure.gca().heatmaps) == 1
        assert len(figure.gca().contours) == 1

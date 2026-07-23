"""Tests for the gleplot GUI property panels (Phase 1, Track F).

These tests exercise FigurePanel, AxesPanel, and SeriesPanel against a real
``gleplot.Figure``/``Axes`` object model, wrapped in a minimal stub document
that mimics the duck-typed ``FigureDocument`` contract (``figure`` property,
``figure_changed``/``figure_replaced`` signals, ``notify_changed()``).

Skips cleanly when PySide6 is not installed (same convention as
``test_scaffold.py``).
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

import gleplot
from gleplot.gui.panels import AxesPanel, FigurePanel, SeriesPanel


# ----------------------------------------------------------------------
# Stub document (Track D's real FigureDocument is not imported per the
# file-ownership rules for this track).
# ----------------------------------------------------------------------
class StubDocument(QObject):
    figure_changed = Signal()
    figure_replaced = Signal()

    def __init__(self, figure=None):
        super().__init__()
        self._figure = figure
        self.notify_count = 0

    @property
    def figure(self):
        return self._figure

    def set_figure(self, figure):
        self._figure = figure
        self.figure_replaced.emit()

    def notify_changed(self):
        self.notify_count += 1
        self.figure_changed.emit()


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _make_figure():
    fig = gleplot.figure(figsize=(8, 6), dpi=100)
    ax = fig.gca()
    ax.plot(
        [1, 2, 3], [1, 4, 9], color="blue", linestyle="--", linewidth=2, label="line a"
    )
    ax.scatter([1, 2, 3], [3, 2, 1], color="red", marker="s", label="scatter a")
    ax.set_title("My title")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.legend(loc="upper left")
    return fig


@pytest.fixture
def document(qapp):
    return StubDocument(_make_figure())


# ------------------------------------------------------------------
# FigurePanel
# ------------------------------------------------------------------
class TestFigurePanel:
    def test_populate_from_model(self, document):
        panel = FigurePanel(document)
        assert panel.width_spin.value() == pytest.approx(8.0)
        assert panel.height_spin.value() == pytest.approx(6.0)
        assert panel.dpi_spin.value() == 100

    def test_refresh_on_figure_replaced(self, document):
        panel = FigurePanel(document)
        new_fig = gleplot.figure(figsize=(10, 4), dpi=200)
        document.set_figure(new_fig)
        assert panel.width_spin.value() == pytest.approx(10.0)
        assert panel.height_spin.value() == pytest.approx(4.0)
        assert panel.dpi_spin.value() == 200

    def test_write_back_size(self, document):
        panel = FigurePanel(document)
        before = document.notify_count
        panel.width_spin.setValue(12.5)
        panel.height_spin.setValue(5.5)
        panel.width_spin.editingFinished.emit()
        panel.height_spin.editingFinished.emit()
        assert document.figure.figsize == (12.5, 5.5)
        assert document.notify_count == before + 2

    def test_write_back_dpi(self, document):
        panel = FigurePanel(document)
        before = document.notify_count
        panel.dpi_spin.setValue(300)
        panel.dpi_spin.editingFinished.emit()
        assert document.figure.dpi == 300
        assert document.notify_count == before + 1

    def test_programmatic_refresh_does_not_notify(self, document):
        panel = FigurePanel(document)
        before = document.notify_count
        panel.refresh()
        assert document.notify_count == before


# ------------------------------------------------------------------
# AxesPanel
# ------------------------------------------------------------------
class TestAxesPanel:
    def test_populate_from_model(self, document):
        panel = AxesPanel(document)
        assert panel.title_edit.text() == "My title"
        assert panel.xlabel_edit.text() == "X"
        assert panel.ylabel_edit.text() == "Y"
        assert panel.legend_enabled_check.isChecked() is True
        assert panel.legend_loc_combo.currentText() == "top left"

    def test_refresh_on_figure_replaced(self, document):
        panel = AxesPanel(document)
        new_fig = gleplot.figure()
        new_fig.gca().set_title("Other title")
        document.set_figure(new_fig)
        assert panel.title_edit.text() == "Other title"

    def test_write_back_title(self, document):
        panel = AxesPanel(document)
        before = document.notify_count
        panel.title_edit.setText("Changed title")
        panel.title_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.title_text == "Changed title"
        assert document.notify_count == before + 1

    def test_write_back_legend_loc(self, document):
        panel = AxesPanel(document)
        before = document.notify_count
        panel.legend_loc_combo.setCurrentText("bottom right")
        ax = document.figure.gca()
        assert ax.legend_pos == "bottom right"
        assert document.notify_count == before + 1

    def test_write_back_legend_enabled(self, document):
        panel = AxesPanel(document)
        panel.legend_enabled_check.setChecked(False)
        ax = document.figure.gca()
        assert ax.legend_on is False

    def test_write_back_scale(self, document):
        panel = AxesPanel(document)
        panel.xscale_combo.setCurrentText("log")
        ax = document.figure.gca()
        assert ax.xscale == "log"

    def test_limits_blank_is_none(self, document):
        panel = AxesPanel(document)
        ax = document.figure.gca()
        ax.xmin = 1.0
        panel.refresh()
        panel.xmin_edit.setText("")
        panel.xmin_edit.editingFinished.emit()
        assert ax.xmin is None

    def test_limits_valid_float(self, document):
        panel = AxesPanel(document)
        before = document.notify_count
        panel.xmax_edit.setText("3.5")
        panel.xmax_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.xmax == pytest.approx(3.5)
        assert document.notify_count == before + 1

    def test_limits_invalid_text_reverted(self, document):
        panel = AxesPanel(document)
        ax = document.figure.gca()
        ax.ymin = 2.0
        panel.refresh()
        before = document.notify_count
        panel.ymin_edit.setText("not-a-number")
        panel.ymin_edit.editingFinished.emit()
        # Model unchanged, notify not called, field reverted to model value.
        assert ax.ymin == 2.0
        assert document.notify_count == before
        assert panel.ymin_edit.text() == "2"

    def test_programmatic_refresh_does_not_notify(self, document):
        panel = AxesPanel(document)
        before = document.notify_count
        panel.refresh()
        assert document.notify_count == before

    def test_set_axes_hook(self, document):
        panel = AxesPanel(document)
        fig = document.figure
        other_ax = fig.add_subplot(2, 1, 2)
        other_ax.set_title("Second axes")
        panel.set_axes(other_ax)
        assert panel.title_edit.text() == "Second axes"


# ------------------------------------------------------------------
# SeriesPanel
# ------------------------------------------------------------------
class TestSeriesPanel:
    def test_populate_series_list(self, document):
        panel = SeriesPanel(document)
        texts = [
            panel.series_list.item(i).text() for i in range(panel.series_list.count())
        ]
        assert texts == ["line: line a", "scatter: scatter a"]

    def test_select_line_shows_correct_controls(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        assert panel.linestyle_combo.isEnabled() is True
        assert panel.linewidth_spin.isEnabled() is True
        # GLE renders markers on line datasets natively, so a line series now
        # exposes the marker + marker-size controls too (they take real effect
        # end-to-end via Axes.plot's preserved marker and the writer's
        # `line ... marker` emission).
        assert panel.marker_combo.isEnabled() is True
        assert panel.markersize_spin.isEnabled() is True
        assert panel.linestyle_combo.currentText() == "--"
        assert panel.linewidth_spin.value() == pytest.approx(2.0)

    def test_set_marker_on_line_series_stores_gle_marker(self, document):
        """A marker chosen on a line series is stored on the line dict."""
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)  # the line series
        panel.marker_combo.setCurrentText("o")
        ax = document.figure.gca()
        assert ax.lines[0]["marker"] == "FCIRCLE"
        assert ax.lines[0]["linestyle"] == "--"  # line style is preserved

    def test_select_scatter_shows_correct_controls(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(1)
        assert panel.marker_combo.isEnabled() is True
        assert panel.markersize_spin.isEnabled() is True
        assert panel.linestyle_combo.isEnabled() is False
        assert panel.linewidth_spin.isEnabled() is False
        assert panel.marker_combo.currentText() == "s"

    def test_write_back_color_stores_gle_name(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        before = document.notify_count

        # Simulate the user picking pure green in the color dialog by
        # calling the same conversion path _on_color_clicked uses,
        # bypassing the modal QColorDialog itself.
        from gleplot.colors import rgb_to_gle

        ax = document.figure.gca()
        series = ax.lines[0]
        series["color"] = rgb_to_gle((0.0, 1.0, 0.0))
        document.notify_changed()

        assert ax.lines[0]["color"] == "GREEN"
        assert document.notify_count == before + 1

    def test_write_back_marker_stores_gle_marker_name(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(1)
        panel.marker_combo.setCurrentText("^")
        ax = document.figure.gca()
        assert ax.scatters[0]["marker"] == "FTRIANGLE"

    def test_write_back_marker_none(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(1)
        panel.marker_combo.setCurrentText("none")
        ax = document.figure.gca()
        assert ax.scatters[0]["marker"] is None

    def test_write_back_linestyle(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        panel.linestyle_combo.setCurrentText(":")
        ax = document.figure.gca()
        assert ax.lines[0]["linestyle"] == ":"

    def test_write_back_linewidth(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        before = document.notify_count
        panel.linewidth_spin.setValue(4.0)
        panel.linewidth_spin.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.lines[0]["linewidth"] == pytest.approx(4.0)
        assert document.notify_count == before + 1

    def test_write_back_markersize_uses_gle_scale(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(1)
        panel.markersize_spin.setValue(10.0)
        panel.markersize_spin.editingFinished.emit()
        ax = document.figure.gca()
        scale = document.figure.marker_config.msize_scale
        assert ax.scatters[0]["markersize"] == pytest.approx(10.0 * 0.025 * scale)

    def test_offset_field_enabled_and_populated_for_line(self, document):
        ax = document.figure.gca()
        ax.lines[0]["offset"] = 3.5
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        assert panel.offset_spin.isEnabled() is True
        assert panel.offset_spin.value() == pytest.approx(3.5)

    def test_write_back_offset(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        before = document.notify_count
        panel.offset_spin.setValue(-6.0)
        panel.offset_spin.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.lines[0]["offset"] == pytest.approx(-6.0)
        assert document.notify_count == before + 1

    def test_write_back_label_refreshes_list_text(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        panel.label_edit.setText("renamed line")
        panel.label_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.lines[0]["label"] == "renamed line"
        assert panel.series_list.item(0).text() == "line: renamed line"

    def test_remove_deletes_from_correct_list(self, document):
        panel = SeriesPanel(document)
        ax = document.figure.gca()
        assert len(ax.scatters) == 1
        panel.series_list.setCurrentRow(1)  # the scatter row
        panel.remove_button.click()
        assert len(ax.scatters) == 0
        assert len(ax.lines) == 1  # untouched

    def test_reorder_within_kind(self, document):
        ax = document.figure.gca()
        ax.plot([0], [0], color="black", label="line b")
        panel = SeriesPanel(document)
        assert len(ax.lines) == 2

        panel.series_list.setCurrentRow(1)  # second line row ("line b")
        panel.up_button.click()
        assert ax.lines[0]["label"] == "line b"
        assert ax.lines[1]["label"] == "line a"

    def test_programmatic_refresh_does_not_notify(self, document):
        panel = SeriesPanel(document)
        before = document.notify_count
        panel.refresh()
        assert document.notify_count == before

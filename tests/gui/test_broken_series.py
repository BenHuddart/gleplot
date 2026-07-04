"""Tests for SeriesPanel's broken (`file_series` + `data_error`) support.

Track C2: a ``data`` reference whose backing file was missing/unreadable at
parse time becomes a ``file_series`` entry carrying a ``'data_error'`` string
key (see ``gleplot.parser.recognizer``). These tests build an *authentic*
broken figure the same way ``tests/parser/test_recognizer.py`` does: generate
a real ``.gle`` + sidecar ``.dat`` via the public API, delete the ``.dat``,
then re-parse with ``parse_gle_figure`` -- so the exact schema (keys,
``data_error`` text) comes from the real recognizer rather than being
hand-guessed.

Skips cleanly when PySide6 is not installed (same convention as
``test_panels.py``).
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
from gleplot.gui.panels import SeriesPanel
from gleplot.parser.recognizer import parse_gle_figure


# ----------------------------------------------------------------------
# Stub document (mirrors tests/gui/test_panels.py's StubDocument; Track D's
# real FigureDocument is not imported per the file-ownership rules).
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


def _make_broken_figure(tmp_path):
    """A figure with one broken file_series entry (deleted sidecar .dat)."""
    fig = gleplot.figure(data_prefix="broken")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], color="blue", label="quad")

    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    # The sidecar data file gleplot generated for the plot() call above.
    dat_path = tmp_path / "broken_0.dat"
    assert dat_path.exists()
    dat_path.unlink()

    recognized = parse_gle_figure(gle_path)
    return recognized, gle_path, dat_path


@pytest.fixture
def broken(tmp_path):
    recognized, gle_path, dat_path = _make_broken_figure(tmp_path)
    return recognized, gle_path, dat_path


@pytest.fixture
def document(qapp, broken):
    recognized, _gle_path, _dat_path = broken
    return StubDocument(recognized.figure)


# ------------------------------------------------------------------
# Sanity: the fixture really does produce a broken file_series entry with
# the schema this panel relies on.
# ------------------------------------------------------------------
def test_fixture_produces_broken_file_series(document):
    ax = document.figure.gca()
    assert ax.lines == []
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert fs["data_file"] == "broken_0.dat"
    assert "data_error" in fs and fs["data_error"]


# ------------------------------------------------------------------
# List rendering: marker + tooltip
# ------------------------------------------------------------------
class TestBrokenSeriesRendering:
    def test_list_shows_warning_marker(self, document):
        panel = SeriesPanel(document)
        assert panel.series_list.count() == 1
        text = panel.series_list.item(0).text()
        assert "⚠" in text  # warning sign
        assert "missing data" in text

    def test_list_tooltip_carries_error_text(self, document):
        panel = SeriesPanel(document)
        ax = document.figure.gca()
        expected_error = ax.file_series[0]["data_error"]
        tooltip = panel.series_list.item(0).toolTip()
        assert tooltip == expected_error

    def test_selecting_broken_series_shows_error_strip_and_locate_button(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        # Widget visibility only reflects reality once the panel itself is
        # shown (see tests/gui/test_export_dialog.py); assert on the
        # explicit "should be shown" flag instead (setVisible(True) called).
        assert panel.error_label.isHidden() is False
        assert panel.locate_button.isHidden() is False
        ax = document.figure.gca()
        assert panel.error_label.text() == ax.file_series[0]["data_error"]

    def test_color_and_label_stay_enabled_others_disabled(self, document):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)
        assert panel.color_button.isEnabled() is True
        assert panel.label_edit.isEnabled() is True
        # No real data loaded -> marker/linestyle/linewidth/markersize
        # controls are not meaningful for a broken reference.
        assert panel.linestyle_combo.isEnabled() is False
        assert panel.linewidth_spin.isEnabled() is False
        assert panel.marker_combo.isEnabled() is False
        assert panel.markersize_spin.isEnabled() is False

    def test_non_broken_series_hides_error_strip(self, qapp):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2, 3], [1, 2, 3], label="ok")
        doc = StubDocument(fig)
        panel = SeriesPanel(doc)
        panel.series_list.setCurrentRow(0)
        assert panel.error_label.isHidden() is True
        assert panel.locate_button.isHidden() is True


# ------------------------------------------------------------------
# Locate flow
# ------------------------------------------------------------------
class TestLocateFlow:
    def test_locate_updates_path_clears_error_and_notifies(self, document, tmp_path, monkeypatch):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)

        replacement = tmp_path / "replacement.dat"
        replacement.write_text("1 1\n2 4\n3 9\n", encoding="utf-8")

        monkeypatch.setattr(
            "gleplot.gui.panels.series_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (str(replacement), "")),
        )

        before = document.notify_count
        panel._on_locate_clicked()

        ax = document.figure.gca()
        fs = ax.file_series[0]
        assert fs["data_file"] == str(replacement.resolve()) or fs["data_file"] == os.path.abspath(str(replacement))
        assert "data_error" not in fs
        assert document.notify_count == before + 1

    def test_locate_emits_series_repointed_with_new_path(self, document, tmp_path, monkeypatch):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)

        replacement = tmp_path / "replacement2.dat"
        replacement.write_text("1 1\n2 4\n3 9\n", encoding="utf-8")

        monkeypatch.setattr(
            "gleplot.gui.panels.series_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (str(replacement), "")),
        )

        received = []
        panel.series_repointed.connect(received.append)
        panel._on_locate_clicked()

        assert len(received) == 1
        assert received[0] == os.path.abspath(str(replacement))

    def test_locate_cancelled_dialog_leaves_series_untouched(self, document, monkeypatch):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)

        monkeypatch.setattr(
            "gleplot.gui.panels.series_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )

        before = document.notify_count
        panel._on_locate_clicked()

        ax = document.figure.gca()
        assert "data_error" in ax.file_series[0]
        assert document.notify_count == before

    def test_repaired_series_regenerates_data_command_with_new_path(
        self, document, tmp_path, monkeypatch
    ):
        """After locate, savefig_gle emits a `data` command with the new path."""
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)

        replacement = tmp_path / "repaired.dat"
        replacement.write_text("1 1\n2 4\n3 9\n", encoding="utf-8")

        monkeypatch.setattr(
            "gleplot.gui.panels.series_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (str(replacement), "")),
        )
        panel._on_locate_clicked()

        out = tmp_path / "resaved.gle"
        document.figure.savefig_gle(str(out))
        text = out.read_text(encoding="utf-8")

        abs_path = os.path.abspath(str(replacement))
        assert abs_path in text

    def test_locate_list_item_loses_warning_marker_after_repair(
        self, document, tmp_path, monkeypatch
    ):
        panel = SeriesPanel(document)
        panel.series_list.setCurrentRow(0)

        replacement = tmp_path / "repaired2.dat"
        replacement.write_text("1 1\n2 4\n3 9\n", encoding="utf-8")

        monkeypatch.setattr(
            "gleplot.gui.panels.series_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (str(replacement), "")),
        )
        panel._on_locate_clicked()

        text = panel.series_list.item(0).text()
        assert "⚠" not in text
        assert "missing data" not in text

"""Tests for gleplot.gui.panels.texts_panel.TextsPanel (Track F2).

Mirrors the stub-document + real-Figure pattern in ``tests/gui/test_panels.py``
(Track F, Phase 1). All fixture data is synthetic.
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
from gleplot.colors import rgb_to_gle
from gleplot.gui.panels import TextsPanel


# ----------------------------------------------------------------------
# Stub document (same shape as test_panels.py's StubDocument; duplicated
# here per this track's file-ownership rules rather than importing across
# test modules).
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
    ax.plot([1, 2, 3], [1, 4, 9], color="blue", label="sin data")
    ax.text(3.1, 0.98, "sin peak", color="red", fontsize=14, ha="left")
    ax.text(1.0, 0.2, "second annotation with a longer body of text than thirty chars")
    return fig


@pytest.fixture
def document(qapp):
    return StubDocument(_make_figure())


# ------------------------------------------------------------------
# List population
# ------------------------------------------------------------------
class TestPopulation:
    def test_populate_from_figure(self, document):
        panel = TextsPanel(document)
        assert panel.text_list.count() == 2
        assert "sin peak" in panel.text_list.item(0).text()
        assert "(3.1, 0.98)" in panel.text_list.item(0).text()

    def test_list_preview_truncates_long_text(self, document):
        panel = TextsPanel(document)
        text = panel.text_list.item(1).text()
        assert "..." in text
        assert len(text.split(" — ")[0]) <= 33  # 30 chars + ellipsis

    def test_empty_axes_disables_panel(self, qapp):
        fig = gleplot.figure()
        doc = StubDocument(fig)
        panel = TextsPanel(doc)
        assert panel.text_list.count() == 0
        assert panel.text_edit.isEnabled() is False

    def test_refresh_on_figure_replaced(self, document):
        panel = TextsPanel(document)
        new_fig = gleplot.figure()
        new_fig.gca().text(0.0, 0.0, "only annotation")
        document.set_figure(new_fig)
        assert panel.text_list.count() == 1
        assert "only annotation" in panel.text_list.item(0).text()

    def test_set_axes_retarget(self, qapp):
        fig = gleplot.figure()
        ax1 = fig.gca()
        ax1.text(0.0, 0.0, "ax1 text")
        # add_subplot immediately retargets fig.gca() to the new axes.
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.text(1.0, 1.0, "ax2 text")

        doc = StubDocument(fig)
        panel = TextsPanel(doc)
        # Panel targets gca() by default, which is now ax2.
        assert panel.text_list.count() == 1
        assert "ax2 text" in panel.text_list.item(0).text()

        panel.set_axes(ax1)
        assert panel.text_list.count() == 1
        assert "ax1 text" in panel.text_list.item(0).text()

        panel.set_axes(ax2)
        assert "ax2 text" in panel.text_list.item(0).text()

    def test_keeps_selection_by_index_across_refresh(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(1)
        document.notify_changed()  # triggers figure_changed -> refresh()
        assert panel.text_list.currentRow() == 1


# ------------------------------------------------------------------
# Selection -> editor fields
# ------------------------------------------------------------------
class TestSelectionReflectsEditor:
    def test_selecting_entry_populates_editor(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        assert panel.text_edit.toPlainText() == "sin peak"
        assert panel.x_edit.text() == "3.1"
        assert panel.y_edit.text() == "0.98"
        assert panel.ha_combo.currentText() == "left"
        assert panel.custom_size_check.isChecked() is True
        assert panel.fontsize_spin.value() == pytest.approx(14.0)

    def test_default_color_and_fontsize(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(1)
        # second annotation has no explicit color/fontsize
        assert panel.custom_size_check.isChecked() is False
        assert panel.fontsize_spin.isEnabled() is False

    def test_va_and_box_color_disabled_with_tooltip(self, document):
        panel = TextsPanel(document)
        assert panel.va_combo.isEnabled() is False
        assert "not rendered" in panel.va_combo.toolTip()
        assert panel.box_color_button.isEnabled() is False
        assert "not rendered" in panel.box_color_button.toolTip()


# ------------------------------------------------------------------
# Edit paths: each writes the exact key + notifies
# ------------------------------------------------------------------
class TestEdits:
    def test_edit_text_commits_on_focus_out_via_event_filter(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.text_edit.setPlainText("renamed peak")
        panel._on_text_committed()  # simulate focus-out (eventFilter hook)
        ax = document.figure.gca()
        assert ax.texts[0]["text"] == "renamed peak"
        assert document.notify_count == before + 1

    def test_edit_text_strips_newlines(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        panel.text_edit.setPlainText("line one\nline two")
        panel._on_text_committed()
        ax = document.figure.gca()
        assert ax.texts[0]["text"] == "line one line two"
        assert "\n" not in panel.text_edit.toPlainText()

    def test_edit_x(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.x_edit.setText("5.5")
        panel.x_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.texts[0]["x"] == pytest.approx(5.5)
        assert document.notify_count == before + 1

    def test_edit_y(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.y_edit.setText("-2.25")
        panel.y_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.texts[0]["y"] == pytest.approx(-2.25)
        assert document.notify_count == before + 1

    def test_edit_invalid_coord_reverts(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.x_edit.setText("not a number")
        panel.x_edit.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.texts[0]["x"] == pytest.approx(3.1)
        assert panel.x_edit.text() == "3.1"
        assert document.notify_count == before

    def test_edit_color_stores_gle_name(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count

        # Bypass the modal QColorDialog, matching series_panel's test
        # pattern: simulate the conversion _on_color_clicked performs.
        ax = document.figure.gca()
        entry = ax.texts[0]
        entry["color"] = rgb_to_gle((0.0, 1.0, 0.0))
        document.notify_changed()

        assert ax.texts[0]["color"] == "GREEN"
        assert document.notify_count == before + 1

    def test_edit_fontsize_custom_to_value(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.fontsize_spin.setValue(22.0)
        panel.fontsize_spin.editingFinished.emit()
        ax = document.figure.gca()
        assert ax.texts[0]["fontsize"] == pytest.approx(22.0)
        assert document.notify_count == before + 1

    def test_toggle_custom_size_off_writes_none(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)  # fontsize=14 (custom)
        before = document.notify_count
        panel.custom_size_check.setChecked(False)
        ax = document.figure.gca()
        assert ax.texts[0]["fontsize"] is None
        assert panel.fontsize_spin.isEnabled() is False
        assert document.notify_count == before + 1

    def test_toggle_custom_size_on_writes_default(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(1)  # fontsize=None (inherit)
        before = document.notify_count
        panel.custom_size_check.setChecked(True)
        ax = document.figure.gca()
        assert ax.texts[1]["fontsize"] is not None
        assert panel.fontsize_spin.isEnabled() is True
        assert document.notify_count == before + 1

    def test_edit_ha(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.ha_combo.setCurrentText("right")
        ax = document.figure.gca()
        assert ax.texts[0]["ha"] == "right"
        assert document.notify_count == before + 1


# ------------------------------------------------------------------
# Add / Remove
# ------------------------------------------------------------------
class TestAddRemove:
    def test_add_uses_public_api_and_correct_schema(self, document):
        panel = TextsPanel(document)
        ax = document.figure.gca()
        before_count = len(ax.texts)
        before_notify = document.notify_count

        panel.add_button.click()

        assert len(ax.texts) == before_count + 1
        new_entry = ax.texts[-1]
        assert set(new_entry.keys()) == {
            "x", "y", "text", "color", "fontsize", "ha", "va", "box_color",
        }
        assert new_entry["color"] == "BLACK"
        assert new_entry["fontsize"] is None
        assert new_entry["ha"] == "left"
        assert document.notify_count == before_notify + 1
        # newly-added entry is selected
        assert panel.current_index == before_count

    def test_add_uses_limit_midpoint_when_limits_set(self, qapp):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.set_xlim(0.0, 10.0)
        ax.set_ylim(-4.0, 4.0)
        doc = StubDocument(fig)
        panel = TextsPanel(doc)
        panel.add_button.click()
        entry = ax.texts[-1]
        assert entry["x"] == pytest.approx(5.0)
        assert entry["y"] == pytest.approx(0.0)

    def test_add_defaults_to_half_when_limits_unset(self, qapp):
        fig = gleplot.figure()
        ax = fig.gca()
        doc = StubDocument(fig)
        panel = TextsPanel(doc)
        panel.add_button.click()
        entry = ax.texts[-1]
        assert entry["x"] == pytest.approx(0.5)
        assert entry["y"] == pytest.approx(0.5)

    def test_remove_deletes_correct_entry(self, document):
        panel = TextsPanel(document)
        ax = document.figure.gca()
        panel.text_list.setCurrentRow(0)
        before = document.notify_count
        panel.remove_button.click()
        assert len(ax.texts) == 1
        assert ax.texts[0]["text"] == "second annotation with a longer body of text than thirty chars"
        assert document.notify_count == before + 1


# ------------------------------------------------------------------
# Guards
# ------------------------------------------------------------------
class TestGuards:
    def test_refresh_does_not_notify(self, document):
        panel = TextsPanel(document)
        before = document.notify_count
        panel.refresh()
        assert document.notify_count == before

    def test_set_axes_does_not_notify(self, document):
        panel = TextsPanel(document)
        ax = document.figure.gca()
        before = document.notify_count
        panel.set_axes(ax)
        assert document.notify_count == before


# ------------------------------------------------------------------
# Selection sync hook: text_selected / select_text / current_index
# ------------------------------------------------------------------
class TestSelectionSignal:
    def test_user_selection_emits_text_selected(self, document):
        panel = TextsPanel(document)
        received = []
        panel.text_selected.connect(received.append)
        panel.text_list.setCurrentRow(1)
        assert received == [1]

    def test_select_text_does_not_emit(self, document):
        panel = TextsPanel(document)
        received = []
        panel.text_selected.connect(received.append)
        panel.select_text(1)
        assert received == []
        assert panel.current_index == 1

    def test_refresh_does_not_emit_text_selected(self, document):
        panel = TextsPanel(document)
        received = []
        panel.text_selected.connect(received.append)
        panel.refresh()
        assert received == []

    def test_current_index_tracks_list_selection(self, document):
        panel = TextsPanel(document)
        panel.text_list.setCurrentRow(1)
        assert panel.current_index == 1
        panel.select_text(0)
        assert panel.current_index == 0

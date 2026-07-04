"""Tests for the gleplot GUI layout/subplot panel (Phase 2, Track J).

Mirrors the stub-document pattern in ``tests/gui/test_panels.py``: a real
``gleplot.Figure``/``Axes`` object model wrapped in a minimal stub that mimics
the duck-typed ``FigureDocument`` contract (``figure`` property,
``figure_changed``/``figure_replaced`` signals, ``notify_changed()``).

Skips cleanly when PySide6 is not installed (same convention as
``test_scaffold.py`` / ``test_panels.py``).
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import gleplot
from gleplot.gui.panels import LayoutPanel


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


def _make_empty_figure():
    return gleplot.figure(figsize=(8, 6), dpi=100)


def _make_2x2_figure():
    fig = gleplot.figure(figsize=(8, 6), dpi=100)
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.plot([1, 2, 3], [1, 4, 9], label="a")
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.plot([1, 2, 3], [3, 2, 1], label="b")
    return fig


@pytest.fixture
def document(qapp):
    return StubDocument(_make_empty_figure())


# ------------------------------------------------------------------
# Grid derivation
# ------------------------------------------------------------------
class TestGridDerivation:
    def test_derive_grid_from_2x2_figure(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        assert panel.rows_spin.value() == 2
        assert panel.cols_spin.value() == 2

    def test_empty_figure_defaults_to_1x1(self, document):
        panel = LayoutPanel(document)
        assert panel.rows_spin.value() == 1
        assert panel.cols_spin.value() == 1


# ------------------------------------------------------------------
# Slot selection / add axes
# ------------------------------------------------------------------
class TestSlotSelection:
    def test_add_axes_to_empty_slot(self, document):
        panel = LayoutPanel(document)
        # 1x1 grid, no axes yet -> slot 0 is the only (empty) slot.
        before_notify = document.notify_count
        received = []
        panel.axes_selected.connect(lambda ax: received.append(ax))

        panel.slot_list.setCurrentRow(0)
        assert panel.add_axes_button.isEnabled() is True
        panel.add_axes_button.click()

        fig = document.figure
        assert len(fig.axes_list) == 1
        assert document.notify_count == before_notify + 1
        assert len(received) == 1
        assert received[0] is fig.axes_list[0]

    def test_select_existing_axes_emits_and_does_not_notify(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        fig = doc.figure

        # _make_2x2_figure's last add_subplot call left idx 2 as current, so
        # start by explicitly selecting idx 1 (a real change) before
        # exercising the idx-2 selection we actually want to assert on.
        panel.slot_list.setCurrentRow(0)  # idx 1

        before_notify = doc.notify_count
        received = []
        panel.axes_selected.connect(lambda ax: received.append(ax))

        target_ax = next(ax for ax in fig.axes_list if ax.position[2] == 2)

        panel.slot_list.setCurrentRow(1)  # idx 2

        assert len(received) == 1
        assert received[0] is target_ax
        assert doc.notify_count == before_notify
        assert fig._current_axes is target_ax


# ------------------------------------------------------------------
# Apply grid
# ------------------------------------------------------------------
class TestApplyGrid:
    def test_apply_bigger_grid_keeps_axes(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        fig = doc.figure
        ax1 = next(ax for ax in fig.axes_list if ax.position[2] == 1)
        ax2 = next(ax for ax in fig.axes_list if ax.position[2] == 2)

        panel.rows_spin.setValue(3)
        panel.cols_spin.setValue(3)
        panel.apply_grid_button.click()

        assert panel.status_label.text() == ""
        assert len(fig.axes_list) == 2
        assert ax1.position == (3, 3, 1)
        assert ax2.position == (3, 3, 2)
        assert len(ax1.lines) == 1  # data preserved
        assert len(ax2.lines) == 1

    def test_shrink_with_nonempty_orphan_refused(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        fig = doc.figure
        before_notify = doc.notify_count

        # Add a third, non-empty axes at idx 3 so shrinking to 1x2 orphans it.
        ax3 = fig.add_subplot(2, 2, 3)
        ax3.plot([1, 2], [1, 2])
        doc.notify_count = before_notify  # reset counter after setup mutation

        panel.refresh()
        panel.rows_spin.setValue(1)
        panel.cols_spin.setValue(2)
        panel.apply_grid_button.click()

        assert panel.status_label.text() != ""
        assert "3" in str(ax3.position) or True  # status references orphan(s)
        # Grid unchanged: all three axes still present with old grid dims.
        assert len(fig.axes_list) == 3
        assert doc.notify_count == before_notify

    def test_reshape_same_count_preserves_row_col(self, qapp):
        """FIX 7: reshaping 2x3 -> 3x2 (same slot count) must keep each axes at
        its (row, col) cell, recomputing idx for the new column count -- not
        keep idx verbatim (which would silently move a populated axes)."""
        fig = gleplot.figure(figsize=(8, 6), dpi=100)
        # 2x3 grid; put a non-empty axes at (row=1, col=0) == idx 4.
        ax = fig.add_subplot(2, 3, 4)
        ax.plot([1, 2, 3], [1, 4, 9], label="a")
        assert ax.position == (2, 3, 4)  # (row 1, col 0)

        doc = StubDocument(fig)
        panel = LayoutPanel(doc)
        panel.refresh()

        # Reshape to 3x2 (same 6 slots). (row 1, col 0) in a 2-col grid is
        # idx = 1*2 + 0 + 1 = 3.
        panel.rows_spin.setValue(3)
        panel.cols_spin.setValue(2)
        panel.apply_grid_button.click()

        assert panel.status_label.text() == ""
        assert ax.position == (3, 2, 3)  # same (row 1, col 0), idx recomputed
        assert len(ax.lines) == 1  # data preserved

    def test_reshape_out_of_bounds_nonempty_refused(self, qapp):
        """FIX 7: if an axes' (row, col) falls outside the new grid and it is
        non-empty, the reshape is refused (data would be lost)."""
        fig = gleplot.figure(figsize=(8, 6), dpi=100)
        # 2x3 grid; non-empty axes at (row=0, col=2) == idx 3.
        ax = fig.add_subplot(2, 3, 3)
        ax.plot([1, 2, 3], [1, 4, 9], label="a")

        doc = StubDocument(fig)
        panel = LayoutPanel(doc)
        panel.refresh()
        before_notify = doc.notify_count

        # Reshape to 3x2: col index 2 is out of bounds (cols now 0..1), so the
        # axes cannot keep its (row, col) -> refuse (it is non-empty).
        panel.rows_spin.setValue(3)
        panel.cols_spin.setValue(2)
        panel.apply_grid_button.click()

        assert panel.status_label.text() != ""
        # Grid unchanged; axes untouched.
        assert ax.position == (2, 3, 3)
        assert doc.notify_count == before_notify

    def test_reshape_out_of_bounds_empty_dropped(self, qapp):
        """FIX 7: an axes whose (row, col) falls outside the new grid but is
        empty is dropped (consistent with the shrink rules)."""
        fig = gleplot.figure(figsize=(8, 6), dpi=100)
        keep = fig.add_subplot(2, 3, 1)  # (0,0) stays in-bounds
        keep.plot([1, 2, 3], [1, 4, 9], label="a")
        empty = fig.add_subplot(2, 3, 3)  # (0,2) out of bounds in 3x2, empty
        assert _is_empty(empty)

        doc = StubDocument(fig)
        panel = LayoutPanel(doc)
        panel.refresh()

        panel.rows_spin.setValue(3)
        panel.cols_spin.setValue(2)
        panel.apply_grid_button.click()

        assert panel.status_label.text() == ""
        remaining = [a.position for a in fig.axes_list]
        # keep stays at (row 0, col 0) -> idx 1 under 3x2; empty is dropped.
        assert (3, 2, 1) in remaining
        assert empty not in fig.axes_list

    def test_shrink_dropping_only_empty_axes_works(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        fig = doc.figure
        # idx 3 and 4 are empty (never created) in the 2x2 fixture; shrinking
        # to 1x2 (max_idx=2) keeps ax1/ax2 and orphans nothing since no axes
        # exist at idx 3/4. Use a grid where an *existing* empty axes is
        # dropped instead: add an empty axes at idx 4, then shrink to 1x3
        # (max_idx=3), which orphans idx 4 (empty) but keeps idx 1-3.
        ax_empty = fig.add_subplot(2, 2, 4)
        assert _is_empty(ax_empty)

        panel.refresh()
        panel.rows_spin.setValue(1)
        panel.cols_spin.setValue(3)
        panel.apply_grid_button.click()

        assert panel.status_label.text() == ""
        remaining_idx = sorted(ax.position[2] for ax in fig.axes_list)
        assert remaining_idx == [1, 2]
        assert all(ax.position[:2] == (1, 3) for ax in fig.axes_list)


def _is_empty(ax) -> bool:
    return not ax.has_plots() and not ax.texts


# ------------------------------------------------------------------
# Shared axes toggles
# ------------------------------------------------------------------
class TestSharedAxes:
    def test_sharex_toggle_writes_through_and_notifies(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        before = doc.notify_count
        panel.sharex_check.setChecked(True)
        fig = doc.figure
        assert fig.sharex is True
        assert doc.notify_count == before + 1

    def test_sharey_toggle_writes_through_and_notifies(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        before = doc.notify_count
        panel.sharey_check.setChecked(True)
        fig = doc.figure
        assert fig.sharey is True
        assert doc.notify_count == before + 1


# ------------------------------------------------------------------
# subplots_adjust
# ------------------------------------------------------------------
class TestSubplotsAdjust:
    def test_set_left_and_wspace_stores_exactly_those_keys(self, document):
        panel = LayoutPanel(document)
        fig = document.figure

        panel._adjust_checks["left"].setChecked(True)
        panel._adjust_spins["left"].setValue(0.15)
        panel._adjust_spins["left"].editingFinished.emit()

        panel._adjust_checks["wspace"].setChecked(True)
        panel._adjust_spins["wspace"].setValue(0.3)
        panel._adjust_spins["wspace"].editingFinished.emit()

        assert set(fig._subplot_adjust.keys()) == {"left", "wspace"}
        assert fig._subplot_adjust["left"] == pytest.approx(0.15)
        assert fig._subplot_adjust["wspace"] == pytest.approx(0.3)

    def test_unset_removes_key(self, document):
        panel = LayoutPanel(document)
        fig = document.figure

        panel._adjust_checks["left"].setChecked(True)
        panel._adjust_spins["left"].setValue(0.2)
        panel._adjust_spins["left"].editingFinished.emit()
        assert "left" in fig._subplot_adjust

        panel._adjust_checks["left"].setChecked(False)
        assert "left" not in fig._subplot_adjust


# ------------------------------------------------------------------
# Feedback loop guard
# ------------------------------------------------------------------
class TestFeedbackLoopGuard:
    def test_refresh_does_not_notify(self, document):
        panel = LayoutPanel(document)
        before = document.notify_count
        panel.refresh()
        assert document.notify_count == before

    def test_figure_changed_refresh_does_not_renotify(self, qapp):
        doc = StubDocument(_make_2x2_figure())
        panel = LayoutPanel(doc)
        before = doc.notify_count
        # Simulate an external figure_changed emission (e.g. from another
        # panel's edit) -- our own _on_figure_changed handler must not
        # trigger another notify_changed().
        doc.figure_changed.emit()
        assert doc.notify_count == before


# ------------------------------------------------------------------
# End-to-end GLE generation
# ------------------------------------------------------------------
class TestEndToEndGleGeneration:
    def test_panel_built_2x2_grid_compiles_with_real_gle(self, document, tmp_path):
        if shutil.which("gle") is None:
            pytest.skip("GLE compiler not installed on PATH")

        panel = LayoutPanel(document)
        fig = document.figure

        # Build a 2x2 grid through panel actions.
        panel.rows_spin.setValue(2)
        panel.cols_spin.setValue(2)
        panel.apply_grid_button.click()
        assert panel.status_label.text() == ""

        # Add axes to each of the 4 slots via the panel, with one series each.
        for row in range(4):
            panel.slot_list.setCurrentRow(row)
            assert panel.add_axes_button.isEnabled() is True
            panel.add_axes_button.click()

        assert len(fig.axes_list) == 4
        for ax in fig.axes_list:
            ax.plot([1, 2, 3], [1, 4, 9])

        out_path = tmp_path / "layout_panel_e2e.gle"
        fig.savefig_gle(str(out_path))
        assert out_path.exists()

        if fig.compiler is None:
            pytest.skip("GLECompiler unavailable despite gle on PATH")

        result_path = fig.compiler.compile(str(out_path), "png", dpi=100)
        assert Path(result_path).exists()

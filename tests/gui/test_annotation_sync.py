"""Tests for the Texts-panel <-> annotation-overlay selection sync contract.

Covers the integration point between the two Track-F pieces:

* ``gleplot/gui/annotations.py`` -- ``AnnotationOverlay.select_annotation`` /
  ``selection_changed``.
* ``gleplot/gui/panels/texts_panel.py`` -- ``TextsPanel.select_text`` /
  ``current_index`` / ``text_selected``.
* ``gleplot/gui/main_window.py`` -- the wiring between the two.

These drive the *real* GLE render pipeline on the offscreen Qt platform (the
same async harness pattern as ``test_annotations.py``), since the overlay only
has live ``AnnotationItem``s after a real render lands a calibration geometry.
All figures are synthetic.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import gleplot as glp  # noqa: E402
from gleplot.compiler import find_gle  # noqa: E402
from gleplot.gui.annotations import AnnotationOverlay  # noqa: E402
from gleplot.gui.document import FigureDocument  # noqa: E402
from gleplot.gui.main_window import MainWindow  # noqa: E402
from gleplot.gui.panels import TextsPanel  # noqa: E402
from gleplot.gui.preview import PreviewController, PreviewView  # noqa: E402

_GLE_AVAILABLE = find_gle() is not None


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _wait_until(predicate, timeout_ms=15000):
    if predicate():
        return True
    loop = QEventLoop()
    timed_out = {"value": False}
    poll = QTimer()
    poll.setInterval(20)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.setInterval(timeout_ms)

    def check():
        if predicate():
            loop.quit()

    def on_deadline():
        timed_out["value"] = True
        loop.quit()

    poll.timeout.connect(check)
    deadline.timeout.connect(on_deadline)
    poll.start()
    deadline.start()
    loop.exec()
    poll.stop()
    deadline.stop()
    return not timed_out["value"]


# ----------------------------------------------------------------------
# Lightweight harness: document + PNG-mode controller + view + overlay +
# texts panel, wired exactly like MainWindow's _connect_preview_signals.
# ----------------------------------------------------------------------
class _Harness:
    def __init__(self, doc):
        self.doc = doc
        self.ctrl = PreviewController(doc, debounce_ms=50)
        self.ctrl._render_format = "png"
        self.view = PreviewView()
        self.overlay = AnnotationOverlay(doc, self.view)
        self.texts_panel = TextsPanel(doc)
        self.renders = []
        self.ctrl.render_succeeded.connect(self._on_succeeded)
        self.ctrl.geometry_ready.connect(self.view.set_geometry)
        self.ctrl.geometry_ready.connect(self.overlay.set_geometry)
        self.ctrl.render_succeeded.connect(self._show_and_rebuild)

        # The sync wiring under test (mirrors MainWindow).
        self.texts_panel.text_selected.connect(self._on_panel_selected)
        self.overlay.selection_changed.connect(self._on_overlay_selected)
        self.panel_selected_calls = []
        self.overlay_selected_calls = []

    def _on_panel_selected(self, index):
        self.panel_selected_calls.append(index)
        ax = self.texts_panel.current_axes()
        if ax is None:
            return
        texts = list(getattr(ax, "texts", []) or [])
        td = texts[index] if 0 <= index < len(texts) else None
        self.overlay.select_annotation(td)

    def _on_overlay_selected(self, text_dict):
        self.overlay_selected_calls.append(text_dict)
        if text_dict is None:
            self.texts_panel.select_text(-1)
            return
        owning_ax, index = self._find_text_owner(text_dict)
        if owning_ax is None:
            return
        if self.texts_panel.current_axes() is not owning_ax:
            self.texts_panel.set_axes(owning_ax)
        self.texts_panel.select_text(index)

    def _find_text_owner(self, text_dict):
        figure = self.doc.figure
        if figure is None:
            return None, -1
        for ax in list(getattr(figure, "axes_list", []) or []):
            texts = getattr(ax, "texts", None) or []
            for i, td in enumerate(texts):
                if td is text_dict:
                    return ax, i
        return None, -1

    def _on_succeeded(self, path):
        self.renders.append(path)

    def _show_and_rebuild(self, path):
        self.view.show_image(path)
        self.overlay.on_render_succeeded(path)

    def render_and_wait(self, prev_count=None):
        target = prev_count if prev_count is not None else len(self.renders)
        self.ctrl.request_render()
        return _wait_until(lambda: len(self.renders) > target)

    def shutdown(self):
        self.ctrl.shutdown()


def _doc_with_two_annotations():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.plot([0, 10], [0, 10], label="line")
    ax.text(2.0, 8.0, "alpha")
    ax.text(6.0, 3.0, "beta")
    doc.set_figure(fig)
    return doc


def _doc_with_two_axes():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(6, 3))
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.plot([0, 10], [0, 10], label="line1")
    ax1.text(2.0, 8.0, "left-text")

    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.plot([0, 10], [10, 0], label="line2")
    ax2.text(5.0, 5.0, "right-text")

    doc.set_figure(fig)
    return doc


# ----------------------------------------------------------------------
# Panel -> overlay: selecting a row highlights the corresponding item.
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_panel_selection_highlights_overlay_item(qapp):
    doc = _doc_with_two_annotations()
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        assert len(h.overlay.items) == 2

        h.texts_panel.select_text(1)
        # select_text is programmatic (no emit), so the sync wiring above is
        # NOT triggered by it; drive it explicitly the way a user click would
        # (text_list.setCurrentRow while not updating) -- simplest is to call
        # the handler that a user-driven change would invoke.
        h._on_panel_selected(1)

        beta_item = next(it for it in h.overlay.items if it.text_dict["text"] == "beta")
        alpha_item = next(it for it in h.overlay.items if it.text_dict["text"] == "alpha")
        assert beta_item.isSelected() is True
        assert alpha_item.isSelected() is False
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Overlay -> panel: a user-driven canvas selection updates current_index.
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_overlay_selection_updates_panel_current_index(qapp):
    doc = _doc_with_two_annotations()
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        beta_item = next(it for it in h.overlay.items if it.text_dict["text"] == "beta")

        # Simulate the *user* path: toggle Qt selection directly on the item
        # (this is exactly what Qt's selection machinery does on a real
        # mouse-press -- see AnnotationItem.mousePressEvent's setSelected(True)
        # call), which fires itemChange(ItemSelectedHasChanged) unguarded and
        # therefore routes to AnnotationOverlay._on_item_selection_changed.
        beta_item.setSelected(True)

        assert h.overlay_selected_calls[-1] is beta_item.text_dict
        assert h.texts_panel.current_index == 1
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# No infinite loop: bounded signal counts in both directions.
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_selection_sync_has_no_loop(qapp):
    doc = _doc_with_two_annotations()
    h = _Harness(doc)
    try:
        assert h.render_and_wait()

        # Panel-driven selection: exactly one panel->overlay call, and the
        # overlay's no-emit select_annotation() must not produce any
        # overlay->panel callback.
        h.panel_selected_calls.clear()
        h.overlay_selected_calls.clear()
        h.texts_panel.select_text(1)
        h._on_panel_selected(1)
        assert len(h.overlay_selected_calls) == 0

        # Overlay-driven (user) selection: exactly one selection_changed
        # emission, and the panel's no-emit select_text() must not produce
        # any panel->overlay callback.
        h.panel_selected_calls.clear()
        h.overlay_selected_calls.clear()
        alpha_item = next(it for it in h.overlay.items if it.text_dict["text"] == "alpha")
        alpha_item.setSelected(True)
        assert len(h.overlay_selected_calls) == 1
        assert len(h.panel_selected_calls) == 0

        # Deselecting also bounded: one call, dict is None.
        h.overlay_selected_calls.clear()
        alpha_item.setSelected(False)
        assert len(h.overlay_selected_calls) == 1
        assert h.overlay_selected_calls[-1] is None
        assert h.panel_selected_calls == []
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Selection survives a rebuild (re-render replaces AnnotationItem instances).
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_selection_survives_rebuild(qapp):
    doc = _doc_with_two_annotations()
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        beta_dict = doc.figure.axes_list[0].texts[1]
        h.overlay.select_annotation(beta_dict)

        old_beta_item = next(
            it for it in h.overlay.items if it.text_dict is beta_dict
        )
        assert old_beta_item.isSelected() is True

        # Trigger a rebuild (a fresh render): items are recreated, but the
        # dict identity is unchanged, so the remembered selection re-applies.
        n_before = len(h.renders)
        doc.notify_changed()
        assert _wait_until(lambda: len(h.renders) > n_before)

        new_beta_item = next(
            it for it in h.overlay.items if it.text_dict is beta_dict
        )
        assert new_beta_item is not old_beta_item  # rebuild really replaced it
        assert new_beta_item.isSelected() is True

        alpha_item = next(
            it for it in h.overlay.items if it.text_dict["text"] == "alpha"
        )
        assert alpha_item.isSelected() is False
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Cross-axes selection retargets the panel.
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_cross_axes_selection_retargets_panel(qapp):
    doc = _doc_with_two_axes()
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        assert len(h.overlay.items) == 2

        left_ax = doc.figure.axes_list[0]
        right_ax = doc.figure.axes_list[1]

        # Panel initially targets gca() (the last-added axes == right_ax).
        h.texts_panel.set_axes(right_ax)
        assert h.texts_panel.current_axes() is right_ax

        # Select the item that lives on the OTHER axes (left_ax).
        left_item = next(
            it for it in h.overlay.items if it.text_dict["text"] == "left-text"
        )
        left_item.setSelected(True)

        # The panel must have been retargeted to left_ax and now shows index 0.
        assert h.texts_panel.current_axes() is left_ax
        assert h.texts_panel.current_index == 0
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Full MainWindow smoke: everything constructs and wires without error.
# ----------------------------------------------------------------------
def test_main_window_texts_tab_and_wiring_smoke(qapp):
    window = MainWindow()
    try:
        # Texts tab present, positioned after Series and before Raw GLE.
        tabs = window.properties_tabs
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert "Texts" in labels
        series_idx = labels.index("Series")
        texts_idx = labels.index("Texts")
        raw_idx = labels.index("Raw GLE")
        assert series_idx < texts_idx < raw_idx
        assert tabs.widget(texts_idx) is window.texts_panel

        # Signals exist and are connected (no exceptions constructing/wiring).
        assert hasattr(window.annotation_overlay, "selection_changed")
        assert hasattr(window.texts_panel, "text_selected")

        # Retargeting wiring: layout_panel.axes_selected also reaches texts_panel.
        fig = glp.Figure(figsize=(4, 3))
        ax = fig.add_subplot(1, 1, 1)
        ax.text(1.0, 1.0, "hello")
        window.document.set_figure(fig)
        window.layout_panel.axes_selected.emit(ax)
        assert window.texts_panel.current_axes() is ax
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()

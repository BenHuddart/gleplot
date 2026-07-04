"""Tests for the interactive annotation overlay (Track F1).

These drive the *real* GLE render pipeline on the offscreen Qt platform (the
same async pattern as ``test_calibration_integration.py``) and exercise the
overlay's placement accuracy, drag/edit/delete/add flows, enable/disable
behaviour, and log-axis inverse. All figures are synthetic.

The overlay is tested in PNG render mode: ``RasterViewMapping`` maps
``cm <-> scene`` directly from the installed :class:`PreviewGeometry` (no SVG
file to load), which keeps the position math deterministic and independent of
the SVG backend's availability. The overlay code path itself is identical for
both mappings.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QPointF, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import gleplot as glp  # noqa: E402
from gleplot.compiler import find_gle  # noqa: E402
from gleplot.gui.annotations import AnnotationOverlay  # noqa: E402
from gleplot.gui.document import FigureDocument  # noqa: E402
from gleplot.gui.preview import PreviewController, PreviewView  # noqa: E402

_GLE_AVAILABLE = find_gle() is not None

#: Scene-position tolerance (px). GLE prints calibration to ~2-3 sig figs, and
#: our hit-rect is a generous approximation, so a few px is expected slack.
_SCENE_TOL = 8.0
#: Data-coordinate tolerance for inverse-mapped drops.
_DATA_TOL = 0.15


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


class _Harness:
    """A document + PNG-mode controller + view + overlay, wired like the window."""

    def __init__(self, doc):
        self.doc = doc
        self.ctrl = PreviewController(doc, debounce_ms=50)
        # Force PNG so RasterViewMapping is used deterministically.
        self.ctrl._render_format = "png"
        self.view = PreviewView()
        self.overlay = AnnotationOverlay(doc, self.view)
        self.renders = []
        self.ctrl.render_succeeded.connect(self._on_succeeded)
        self.ctrl.geometry_ready.connect(self.view.set_geometry)
        self.ctrl.geometry_ready.connect(self.overlay.set_geometry)
        self.ctrl.render_succeeded.connect(self._show_and_rebuild)

    def _on_succeeded(self, path):
        self.renders.append(path)

    def _show_and_rebuild(self, path):
        # Mirror the main window: show the image (updates view_mapping), then
        # the overlay rebuilds against the fresh render.
        self.view.show_image(path)
        self.overlay.on_render_succeeded(path)

    def render_and_wait(self, prev_count=None):
        target = (prev_count if prev_count is not None else len(self.renders))
        self.ctrl.request_render()
        return _wait_until(lambda: len(self.renders) > target)

    def shutdown(self):
        self.ctrl.shutdown()


def _doc_with_annotation(x=6.0, y=0.0, text="hello", **text_kw):
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(2, 12)
    ax.set_ylim(-1, 1)
    ax.plot([2, 12], [-1, 1], label="line")
    ax.text(x, y, text, **text_kw)
    doc.set_figure(fig)
    return doc


# ----------------------------------------------------------------------
# Position accuracy
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_item_lands_at_known_data_coords(qapp):
    doc = _doc_with_annotation(x=6.0, y=0.0, text="hello")
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        assert h.overlay.enabled
        assert len(h.overlay.items) == 1
        item = h.overlay.items[0]

        # Expected scene pos: data -> cm -> scene, via the same contracts.
        geom = h.ctrl.last_geometry
        mapping = h.view.view_mapping()
        cal = geom.axes[0]
        cx, cy = cal.data_to_cm(6.0, 0.0)
        vx, vy = mapping.cm_to_view(cx, cy)

        assert item.pos().x() == pytest.approx(vx, abs=_SCENE_TOL)
        assert item.pos().y() == pytest.approx(vy, abs=_SCENE_TOL)
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Drag: model updated + no jump on the follow-up render
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_drag_updates_model_and_no_jump(qapp):
    doc = _doc_with_annotation(x=6.0, y=0.0, text="drag")
    h = _Harness(doc)
    notify_count = {"n": 0}
    doc.figure_changed.connect(lambda: notify_count.__setitem__("n", notify_count["n"] + 1))
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]

        # Target a new data point (10, 0.5); compute its scene pos and move
        # the item there, then commit via the overlay (the tested path).
        mapping = h.view.view_mapping()
        cal = h.ctrl.last_geometry.axes[0]
        tcx, tcy = cal.data_to_cm(10.0, 0.5)
        tvx, tvy = mapping.cm_to_view(tcx, tcy)
        item.sync_position(QPointF(tvx, tvy))

        n_before = len(h.renders)
        h.overlay.commit_item_move(item)

        # Model updated to the target data coords (inverse transform).
        td = doc.figure.axes_list[0].texts[0]
        assert td["x"] == pytest.approx(10.0, abs=_DATA_TOL)
        assert td["y"] == pytest.approx(0.5, abs=_DATA_TOL)
        # Exactly one notify (one undo step) from the commit.
        assert notify_count["n"] == 1

        # The follow-up render rebuilds the item at the dropped position: no
        # jump. Capture the dropped scene pos, wait for the re-render, compare.
        dropped = QPointF(item.pos())
        assert _wait_until(lambda: len(h.renders) > n_before)
        rebuilt = h.overlay.items[0]
        assert rebuilt.pos().x() == pytest.approx(dropped.x(), abs=_SCENE_TOL)
        assert rebuilt.pos().y() == pytest.approx(dropped.y(), abs=_SCENE_TOL)
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Inline edit: change text, and empty-commit deletes
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_edit_commit_updates_text(qapp):
    doc = _doc_with_annotation(text="old")
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]
        n_before = len(h.renders)
        h.overlay.commit_item_text(item, "new text")
        assert doc.figure.axes_list[0].texts[0]["text"] == "new text"
        assert _wait_until(lambda: len(h.renders) > n_before)
        assert h.overlay.items[0].text_dict["text"] == "new text"
    finally:
        h.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_empty_edit_commit_deletes(qapp):
    doc = _doc_with_annotation(text="bye")
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]
        assert len(doc.figure.axes_list[0].texts) == 1
        h.overlay.commit_item_text(item, "   ")
        assert doc.figure.axes_list[0].texts == []
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_delete_item_removes_from_model(qapp):
    doc = _doc_with_annotation(text="rm")
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]
        h.overlay.delete_item(item)
        assert doc.figure.axes_list[0].texts == []
        assert h.overlay.items == []
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Add-text flow (synthetic click)
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_add_text_appends_correct_dict(qapp):
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(2, 12)
    ax.set_ylim(-1, 1)
    ax.plot([2, 12], [-1, 1], label="line")
    doc.set_figure(fig)

    h = _Harness(doc)
    placed = {"n": 0}
    h.overlay.add_text_placed.connect(lambda: placed.__setitem__("n", placed["n"] + 1))
    try:
        assert h.render_and_wait()
        assert h.overlay.enabled
        assert len(doc.figure.axes_list[0].texts) == 0

        h.overlay.begin_add_text()
        assert h.overlay.add_mode

        # Click at the scene position of data (7, 0.0).
        mapping = h.view.view_mapping()
        cal = h.ctrl.last_geometry.axes[0]
        cx, cy = cal.data_to_cm(7.0, 0.0)
        vx, vy = mapping.cm_to_view(cx, cy)
        assert h.overlay._place_text_at(QPointF(vx, vy)) is True

        texts = doc.figure.axes_list[0].texts
        assert len(texts) == 1
        td = texts[0]
        # Schema matches Axes.text() exactly.
        assert set(td.keys()) == {
            "x", "y", "text", "color", "fontsize", "ha", "va", "box_color"
        }
        assert td["text"] == "text"
        assert td["color"] == "BLACK"
        assert td["fontsize"] is None
        assert td["ha"] == "left"
        assert td["va"] == "center"
        assert td["box_color"] is None
        assert td["x"] == pytest.approx(7.0, abs=_DATA_TOL)
        assert td["y"] == pytest.approx(0.0, abs=_DATA_TOL)
        assert placed["n"] == 1
        assert not h.overlay.add_mode
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Disable on None geometry; re-enable on next good geometry
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_overlay_disables_on_none_geometry_and_reenables(qapp):
    doc = _doc_with_annotation(text="tog")
    h = _Harness(doc)
    states = []
    h.overlay.overlay_enabled_changed.connect(states.append)
    try:
        assert h.render_and_wait()
        assert h.overlay.enabled
        assert h.overlay.items

        # Simulate a failed render / parse failure: geometry_ready(None).
        h.overlay.set_geometry(None)
        assert h.overlay.enabled is False
        assert h.overlay.items == []
        assert h.view.annotations_enabled is False

        # A subsequent good render re-enables and rebuilds.
        n_before = len(h.renders)
        doc.notify_changed()
        assert _wait_until(lambda: len(h.renders) > n_before)
        assert h.overlay.enabled is True
        assert h.overlay.items
        assert states[-1] is True
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Log axis: drag maps to correct data coords (exercises log inverse)
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_log_axis_drag_correct_data_coords(qapp):
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 100)
    ax.set_ylim(0.1, 1000)
    ax.plot([1, 100], [0.1, 1000], label="log")
    ax.text(10.0, 10.0, "logtext")
    doc.set_figure(fig)

    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]
        cal = h.ctrl.last_geometry.axes[0]
        assert cal.x_log and cal.y_log

        # Drag to data (50, 100) -- a geometric-space target.
        mapping = h.view.view_mapping()
        tcx, tcy = cal.data_to_cm(50.0, 100.0)
        tvx, tvy = mapping.cm_to_view(tcx, tcy)
        item.sync_position(QPointF(tvx, tvy))
        h.overlay.commit_item_move(item)

        td = doc.figure.axes_list[0].texts[0]
        # Log inverse: allow a few percent relative slack.
        assert td["x"] == pytest.approx(50.0, rel=0.05)
        assert td["y"] == pytest.approx(100.0, rel=0.05)
    finally:
        h.shutdown()


# ----------------------------------------------------------------------
# Mid-render drag: an active drag is not teleported by a rebuild
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_active_drag_not_rebuilt_midrender(qapp):
    doc = _doc_with_annotation(x=6.0, y=0.0, text="mid")
    h = _Harness(doc)
    try:
        assert h.render_and_wait()
        item = h.overlay.items[0]

        # Simulate an in-progress drag: mark interacting + move to an arbitrary
        # scene position the model does NOT reflect.
        item._dragging = True
        held = QPointF(37.0, 42.0)
        item.sync_position(held)

        # A render lands (e.g. from a prior debounce): rebuild must preserve the
        # interacting item at its held position, not snap it to the model coords.
        h.overlay.on_render_succeeded(h.renders[-1])
        assert item in h.overlay.items
        assert item.pos().x() == pytest.approx(held.x())
        assert item.pos().y() == pytest.approx(held.y())
    finally:
        item._dragging = False
        h.shutdown()


# ----------------------------------------------------------------------
# Pan-vs-drag: hover suspends ScrollHandDrag, leave restores it
# ----------------------------------------------------------------------
def test_suspend_pan_toggles_view_drag_mode(qapp):
    from PySide6.QtWidgets import QGraphicsView

    view = PreviewView()
    assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag
    view.suspend_pan(True)
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    view.suspend_pan(False)
    assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag
    # Idempotent: double-suspend / double-restore are safe.
    view.suspend_pan(True)
    view.suspend_pan(True)
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    view.suspend_pan(False)
    assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag


def test_overlay_disabled_without_geometry(qapp):
    """With no geometry ever installed, the overlay stays disabled (no GLE)."""
    doc = _doc_with_annotation()
    view = PreviewView()
    overlay = AnnotationOverlay(doc, view)
    assert overlay.enabled is False
    assert overlay.items == []
    # begin_add_text is a no-op while disabled.
    overlay.begin_add_text()
    assert overlay.add_mode is False

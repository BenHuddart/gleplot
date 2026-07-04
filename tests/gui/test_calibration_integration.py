"""Integration tests for preview calibration (Track E1).

These drive a *real* GLE compile through :class:`PreviewController` on the
offscreen Qt platform and assert that the ``gleplot-cal`` protocol produces a
:class:`PreviewGeometry` whose cm rectangles match GLE's own reported values.
They skip cleanly when PySide6 is unavailable and are ``xfail`` when GLE is not
installed (the pipeline is correct but cannot compile).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import gleplot as glp  # noqa: E402
from gleplot.compiler import find_gle  # noqa: E402
from gleplot.gui.document import FigureDocument  # noqa: E402
from gleplot.gui.geometry import PreviewGeometry  # noqa: E402
from gleplot.gui.preview import PreviewController  # noqa: E402

_GLE_AVAILABLE = find_gle() is not None

# Tolerance for comparing our computed cm values against GLE's printed values.
# GLE prints with ~2-3 significant figures (e.g. "4.33"), so 0.05 cm is safe.
_CM_TOL = 0.05


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class GeomRecorder:
    """Records render_succeeded / geometry_ready ordering and payloads."""

    def __init__(self, controller):
        self.succeeded = []
        self.failed = []
        self.geometries = []
        self.events = []  # ordered ("geom"|"success", payload)
        controller.render_succeeded.connect(self._on_succeeded)
        controller.render_failed.connect(self._on_failed)
        controller.geometry_ready.connect(self._on_geometry)

    def _on_succeeded(self, path):
        self.succeeded.append(path)
        self.events.append(("success", path))

    def _on_failed(self, errors, raw):
        self.failed.append((errors, raw))

    def _on_geometry(self, geom):
        self.geometries.append(geom)
        self.events.append(("geom", geom))


def _wait_until(predicate, timeout_ms=10000):
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
    if predicate():
        return True
    loop.exec()
    poll.stop()
    deadline.stop()
    return not timed_out["value"]


def _single_axes_doc():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(2, 12)
    ax.set_ylim(-1, 1)
    ax.plot([2, 12], [-1, 1], label="line")
    doc.set_figure(fig)
    return doc


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_single_axes_calibration_matches_gle(qapp):
    doc = _single_axes_doc()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = GeomRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 15000)
        assert not rec.failed, rec.failed
        assert rec.succeeded

        geom = ctrl.last_geometry
        assert isinstance(geom, PreviewGeometry)
        assert len(geom.axes) == 1
        cal = geom.axes[0]
        assert cal.index == 0
        assert cal.x_range == pytest.approx((2.0, 12.0))
        assert cal.y_range == pytest.approx((-1.0, 1.0))

        # data_to_cm of the low corner equals GLE's reported (x0, y0) corner.
        cx, cy = cal.data_to_cm(2.0, -1.0)
        assert cx == pytest.approx(cal.cm_rect[0], abs=1e-9)
        assert cy == pytest.approx(cal.cm_rect[1], abs=1e-9)
        # High corner too.
        cx, cy = cal.data_to_cm(12.0, 1.0)
        assert cx == pytest.approx(cal.cm_rect[2], abs=1e-9)
        assert cy == pytest.approx(cal.cm_rect[3], abs=1e-9)

        # Page size from figsize (4x3 in -> cm).
        assert geom.page_size_cm[0] == pytest.approx(4 * 2.54)
        assert geom.page_size_cm[1] == pytest.approx(3 * 2.54)
        assert geom.dpi == ctrl.preview_dpi
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_geometry_ready_fires_before_render_succeeded(qapp):
    doc = _single_axes_doc()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = GeomRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 15000)
        assert not rec.failed, rec.failed
        # The first two ordered events must be geom then success.
        kinds = [k for k, _ in rec.events]
        assert kinds[0] == "geom"
        assert kinds[1] == "success"
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_subplot_grid_yields_four_distinct_calibrations(qapp):
    doc = FigureDocument()
    fig = glp.Figure(figsize=(6, 5))
    data = {
        1: ([1, 2, 3], [1, 4, 9]),
        2: ([1, 2, 3], [9, 4, 1]),
        3: ([1, 2, 3], [2, 5, 2]),
        4: ([1, 2, 3], [3, 1, 3]),
    }
    for idx, (x, y) in data.items():
        ax = fig.add_subplot(2, 2, idx)
        ax.plot(x, y, label=f"s{idx}")
    doc.set_figure(fig)

    ctrl = PreviewController(doc, debounce_ms=50)
    rec = GeomRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 15000)
        assert not rec.failed, rec.failed

        geom = ctrl.last_geometry
        assert geom is not None
        assert len(geom.axes) == 4
        assert [c.index for c in geom.axes] == [0, 1, 2, 3]

        # All four boxes are distinct.
        rects = [c.cm_rect for c in geom.axes]
        assert len(set(rects)) == 4

        # Row-major order: subplot 1 (top-left) has the largest y (top of page)
        # and subplot 3 (bottom-left) a smaller y; both share the left x.
        # cm_rect[3] is the top (high-y) cm edge.
        top_left = geom.axes[0].cm_rect
        bottom_left = geom.axes[2].cm_rect
        assert top_left[0] == pytest.approx(bottom_left[0], abs=_CM_TOL)  # same x0
        assert top_left[3] > bottom_left[3]  # top row is higher on the page
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_log_scale_calibration_maps_geometric_midpoint(qapp):
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 100)
    ax.set_ylim(0.1, 1000)
    ax.plot([1, 100], [0.1, 1000], label="log")
    doc.set_figure(fig)

    ctrl = PreviewController(doc, debounce_ms=50)
    rec = GeomRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 15000)
        assert not rec.failed, rec.failed

        geom = ctrl.last_geometry
        assert geom is not None
        cal = geom.axes[0]
        assert cal.x_log is True
        assert cal.y_log is True

        # Geometric midpoint of x (10) maps to the cm midpoint of the box.
        cx, _ = cal.data_to_cm(10.0, 1.0)
        assert cx == pytest.approx((cal.cm_rect[0] + cal.cm_rect[2]) / 2, abs=1e-6)
        # geomean(0.1, 1000) = 10 -> cm midpoint of y box.
        _, cy = cal.data_to_cm(1.0, 10.0)
        assert cy == pytest.approx((cal.cm_rect[1] + cal.cm_rect[3]) / 2, abs=1e-6)
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_calibration_absent_still_renders_with_none_geometry(qapp, monkeypatch):
    """If no calibration prints are injected, render still succeeds and
    geometry_ready(None) fires -- calibration never blocks a render."""
    doc = _single_axes_doc()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = GeomRecorder(ctrl)

    # Skip the injection step: the script compiles fine but emits no cal lines.
    monkeypatch.setattr(PreviewController, "_inject_calibration", staticmethod(lambda p: None))

    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 15000)
        assert not rec.failed, rec.failed
        assert rec.succeeded  # render still fires
        assert ctrl.last_geometry is None
        assert rec.geometries and rec.geometries[-1] is None
    finally:
        ctrl.shutdown()


def test_preview_script_never_in_user_saves(qapp, tmp_path):
    """User-facing saves go through the public figure API, which is untouched;
    they must never contain the preview-only 'gleplot-cal' marker."""
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([1, 2, 3], [1, 4, 9], label="s")
    out = tmp_path / "user.gle"
    fig.savefig_gle(str(out))
    assert "gleplot-cal" not in out.read_text(encoding="utf-8")


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_injection_present_in_preview_but_not_saved(qapp, tmp_path):
    """The preview temp script DOES contain the marker; the injection helper is
    what the controller applies to its private copy."""
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([1, 2, 3], [1, 4, 9], label="s")
    script = tmp_path / "preview.gle"
    fig.savefig_gle(str(script))
    assert "gleplot-cal" not in script.read_text(encoding="utf-8")
    # Apply the controller's private injection to the temp copy.
    PreviewController._inject_calibration(script)
    injected = script.read_text(encoding="utf-8")
    assert 'print "gleplot-cal 0 ' in injected
    # Exactly one graph block -> exactly one calibration print.
    assert injected.count("gleplot-cal") == 1

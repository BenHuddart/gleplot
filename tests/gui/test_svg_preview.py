"""Tests for the SVG vector preview + PNG fallback (Track E2).

These drive a *real* GLE compile (``gle -d svg`` / ``gle -d png``) through
:class:`PreviewController` on the offscreen Qt platform. They skip cleanly
when PySide6 or QtSvg are unavailable, and are ``xfail`` when GLE itself is
not installed (the pipeline is correct but cannot produce output).
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
from gleplot.gui.preview import (  # noqa: E402
    PreviewController,
    PreviewView,
    RasterViewMapping,
    SvgViewMapping,
    _QTSVG_AVAILABLE,
)

_GLE_AVAILABLE = find_gle() is not None

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover
    QSvgRenderer = None


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class SignalRecorder:
    """Records emissions from a controller's signals and can wait for one."""

    def __init__(self, controller):
        self.started = 0
        self.succeeded = []
        self.failed = []
        self.skipped = 0
        self.geometries = []
        self.fallbacks = []
        controller.render_started.connect(self._on_started)
        controller.render_succeeded.connect(self._on_succeeded)
        controller.render_failed.connect(self._on_failed)
        controller.render_skipped_empty.connect(self._on_skipped)
        controller.geometry_ready.connect(self.geometries.append)
        controller.fallback_activated.connect(self.fallbacks.append)

    def _on_started(self):
        self.started += 1

    def _on_succeeded(self, path):
        self.succeeded.append(path)

    def _on_failed(self, errors, raw):
        self.failed.append((errors, raw))

    def _on_skipped(self):
        self.skipped += 1


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


def _make_sin_document():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    x = np.linspace(0, 2 * np.pi, 50)
    ax.plot(x, np.sin(x), label="sin")
    doc.set_figure(fig)
    return doc


def _single_axes_doc():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(2, 12)
    ax.set_ylim(-1, 1)
    ax.plot([2, 12], [-1, 1], label="line")
    doc.set_figure(fig)
    return doc


# --------------------------------------------------------------------------- #
# PreviewController: SVG render end-to-end
# --------------------------------------------------------------------------- #
def test_png_is_default_render_format(qapp):
    """PNG is always the startup format; SVG is strictly opt-in."""
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    try:
        assert ctrl.render_format == "png"
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_svg_opt_in_probes_and_switches(qapp):
    """With QtSvg + a working GLE/Cairo install, opting in switches to SVG."""
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    try:
        assert ctrl.svg_available
        ctrl.render_format = "svg"
        assert ctrl.render_format == "svg"
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_svg_render_succeeds_and_is_valid(qapp):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.render_format = "svg"  # opt-in (runs the probe)
        assert ctrl.render_format == "svg"
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 10000)
        assert not rec.failed, rec.failed
        assert rec.succeeded

        path = rec.succeeded[-1]
        assert path.endswith(".svg")
        p = Path(path)
        assert p.exists()
        assert p.stat().st_size > 0

        renderer = QSvgRenderer(path)
        assert renderer.isValid()
        assert not renderer.defaultSize().isEmpty()

        # geometry_ready fired with a non-None geometry before render_succeeded.
        assert rec.geometries
        assert rec.geometries[-1] is not None
        assert ctrl.last_geometry is not None
        # No fallback should have been triggered on a clean SVG render.
        assert not rec.fallbacks
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_svg_calibration_print_line_present(qapp):
    """gleplot-cal is parsed from an SVG compile just like a PNG compile."""
    doc = _single_axes_doc()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.render_format = "svg"  # opt-in (runs the probe)
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 10000)
        assert not rec.failed, rec.failed
        geom = ctrl.last_geometry
        assert geom is not None
        assert len(geom.axes) == 1
        cal = geom.axes[0]
        assert cal.x_range == pytest.approx((2.0, 12.0))
        assert cal.y_range == pytest.approx((-1.0, 1.0))
    finally:
        ctrl.shutdown()


# --------------------------------------------------------------------------- #
# Fallback path
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_svg_fallback_on_invalid_output(qapp, monkeypatch, tmp_path):
    """A forced invalid-SVG condition triggers fallback and an automatic PNG."""
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    # Opt in BEFORE poisoning the validator: the opt-in probe calls
    # _svg_output_problem too, and must pass with the real validation so this
    # test exercises the *live-render* fallback path, not the probe path.
    ctrl.render_format = "svg"
    assert ctrl.render_format == "svg"

    # Force every SVG-output validation to report a problem, regardless of
    # what GLE actually produced -- this simulates the exit-0-but-degraded
    # PostScript-font-on-Cairo failure mode (see preview.py module docstring)
    # without depending on a specific user font configuration.
    monkeypatch.setattr(
        ctrl,
        "_svg_output_problem",
        staticmethod(lambda output, raw: "forced failure for test"),
    )

    try:
        ctrl.request_render()
        # First render (svg, forced-invalid) triggers the fallback and an
        # automatic re-render in png; wait for that png to land.
        assert _wait_until(
            lambda: rec.fallbacks and rec.succeeded, 15000
        )
        assert rec.fallbacks == ["forced failure for test"]
        assert ctrl.render_format == "png"
        assert not ctrl.svg_available

        final_path = rec.succeeded[-1]
        assert final_path.endswith(".png")
        assert Path(final_path).exists()
        assert Path(final_path).stat().st_size > 0

        # Sticky: attempting to re-enable SVG is a silent no-op.
        ctrl.render_format = "svg"
        assert ctrl.render_format == "png"
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_svg_opt_in_refused_when_probe_fails(qapp, monkeypatch):
    """A failed opt-in probe keeps PNG and activates the sticky fallback."""
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        monkeypatch.setattr(ctrl, "_probe_svg_support", lambda: False)

        ctrl.render_format = "svg"

        assert ctrl.render_format == "png"
        assert not ctrl.svg_available
        assert rec.fallbacks  # UI was told why the opt-in was refused
        # Sticky: a second attempt is silently ignored, without re-probing.
        ctrl.render_format = "svg"
        assert ctrl.render_format == "png"
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_render_format_setter_rejects_bad_value(qapp):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    try:
        with pytest.raises(ValueError):
            ctrl.render_format = "pdf"
    finally:
        ctrl.shutdown()


# --------------------------------------------------------------------------- #
# PreviewView: SVG display + zoom preservation
# --------------------------------------------------------------------------- #
def _write_svg(path: Path, w: float, h: float):
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}pt" height="{h}pt" '
        f'viewBox="0 0 {w} {h}" version="1.1">\n'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="white"/>\n'
        f"</svg>\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(not _QTSVG_AVAILABLE, reason="QtSvg not installed")
def test_view_show_svg_image_preserves_transform_on_same_size(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)
    view.show()

    p1 = tmp_path / "a.svg"
    p2 = tmp_path / "b.svg"
    _write_svg(p1, 200, 150)
    _write_svg(p2, 200, 150)

    view.show_image(str(p1))
    view.scale(1.5, 1.5)
    before = view.transform().m11()
    view.show_image(str(p2))
    after = view.transform().m11()

    assert abs(before - after) < 1e-6
    assert view.last_good_path == str(p2)


@pytest.mark.skipif(not _QTSVG_AVAILABLE, reason="QtSvg not installed")
def test_view_show_svg_image_refits_on_size_change(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)
    view.show()

    p1 = tmp_path / "a.svg"
    p2 = tmp_path / "big.svg"
    _write_svg(p1, 200, 150)
    _write_svg(p2, 600, 450)

    view.show_image(str(p1))
    view.scale(2.0, 2.0)
    changed = view.transform().m11()
    view.show_image(str(p2))
    refit = view.transform().m11()

    assert abs(changed - refit) > 1e-6


@pytest.mark.skipif(not _QTSVG_AVAILABLE, reason="QtSvg not installed")
def test_view_switching_formats_refits(qapp, tmp_path):
    """A format switch (png <-> svg) is treated as a size change: refit."""

    def _write_png(path, w, h):
        from PySide6.QtGui import QPixmap

        pix = QPixmap(w, h)
        pix.fill()
        pix.save(str(path), "PNG")

    view = PreviewView()
    view.resize(400, 300)
    view.show()

    png_path = tmp_path / "a.png"
    svg_path = tmp_path / "a.svg"
    _write_png(png_path, 200, 150)
    _write_svg(svg_path, 200, 150)  # same nominal size, different format

    view.show_image(str(png_path))
    view.scale(2.0, 2.0)
    changed = view.transform().m11()
    view.show_image(str(svg_path))
    refit = view.transform().m11()

    assert abs(changed - refit) > 1e-6


@pytest.mark.skipif(not _QTSVG_AVAILABLE, reason="QtSvg not installed")
def test_view_mapping_none_when_nothing_shown(qapp):
    view = PreviewView()
    assert view.view_mapping() is None


@pytest.mark.skipif(not _QTSVG_AVAILABLE, reason="QtSvg not installed")
def test_view_mapping_svg_round_trip(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)
    view.show()

    # A page 578x434pt (== 20.32x15.24cm + 1pt margin each side), matching
    # the empirically derived GLE Cairo SVG viewBox convention.
    svg_path = tmp_path / "page.svg"
    _write_svg(svg_path, 578, 434)
    view.show_image(str(svg_path))

    mapping = view.view_mapping()
    assert isinstance(mapping, SvgViewMapping)
    assert mapping.page_size_cm == pytest.approx((20.32, 15.24), abs=1e-6)

    for cx, cy in [(0.0, 0.0), (20.32, 15.24), (10.0, 7.0), (2.25, 1.5)]:
        vx, vy = mapping.cm_to_view(cx, cy)
        cx2, cy2 = mapping.view_to_cm(vx, vy)
        assert cx2 == pytest.approx(cx, abs=1e-6)
        assert cy2 == pytest.approx(cy, abs=1e-6)

    # Y orientation: page origin (bottom-left in cm) is near the bottom of
    # the view (large vy); the top of the page (cy = page height) is near
    # the top of the view (vy close to the margin).
    vx0, vy0 = mapping.cm_to_view(0.0, 0.0)
    vx1, vy1 = mapping.cm_to_view(0.0, 15.24)
    assert vy1 < vy0


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_view_mapping_raster_round_trip_and_data_lands_in_axes_rect(qapp):
    """cm->view->cm identity for the raster mapping, and a data point lands
    inside the axes' on-screen rect once geometry + image are both installed.
    """
    doc = _single_axes_doc()
    ctrl = PreviewController(doc, debounce_ms=50)
    ctrl.render_format = "png"
    rec = SignalRecorder(ctrl)
    view = PreviewView()
    view.resize(400, 300)
    view.show()
    ctrl.geometry_ready.connect(view.set_geometry)
    ctrl.render_succeeded.connect(view.show_image)

    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 10000)
        assert not rec.failed, rec.failed

        mapping = view.view_mapping()
        assert isinstance(mapping, RasterViewMapping)

        geom = ctrl.last_geometry
        assert geom is not None
        cal = geom.axes[0]

        for cx, cy in [
            (cal.cm_rect[0], cal.cm_rect[1]),
            (cal.cm_rect[2], cal.cm_rect[3]),
        ]:
            vx, vy = mapping.cm_to_view(cx, cy)
            cx2, cy2 = mapping.view_to_cm(vx, vy)
            assert cx2 == pytest.approx(cx, abs=1e-6)
            assert cy2 == pytest.approx(cy, abs=1e-6)

        # A data point at the low corner maps (data -> cm -> view) inside the
        # scene rect (== "on screen", modulo view zoom/pan which only scales
        # the whole scene uniformly and never moves content outside it).
        x, y = 2.0, -1.0  # low corner of the axes' data range
        cx, cy = cal.data_to_cm(x, y)
        vx, vy = mapping.cm_to_view(cx, cy)
        scene_rect = view._scene.sceneRect()
        assert scene_rect.contains(vx, vy)
    finally:
        ctrl.shutdown()


# --------------------------------------------------------------------------- #
# main_window: toggle action state transitions
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_main_window_vector_preview_toggle(qapp, tmp_path, monkeypatch):
    from gleplot.gui.main_window import MainWindow
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings=settings)
    try:
        action = win.action_vector_preview
        ctrl = win.preview_controller

        if not ctrl.svg_available:
            pytest.skip("SVG not available in this environment")

        assert action.isChecked() == (ctrl.render_format == "svg")
        assert action.isEnabled()

        # Toggling off switches the controller to png.
        action.setChecked(False)
        assert ctrl.render_format == "png"

        # Toggling back on switches back to svg.
        action.setChecked(True)
        assert ctrl.render_format == "svg"

        # Simulate a fallback: the action unchecks itself and disables.
        ctrl.fallback_activated.emit("simulated failure")
        assert not action.isChecked()
        assert not action.isEnabled()
    finally:
        win.close()

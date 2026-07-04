"""Tests for the live preview engine (Track D).

These are integration tests: they drive a real GLE compile through
:class:`PreviewController` on the offscreen Qt platform, spinning the event
loop with :class:`QEventLoop`/:class:`QTimer` (no pytest-qt). They skip
cleanly when PySide6 is unavailable and are marked ``xfail`` when GLE itself
is not installed (the pipeline is correct but cannot produce a PNG).
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.compiler import find_gle
from gleplot.gui.document import FigureDocument
from gleplot.gui.preview import PreviewController, PreviewView

_GLE_AVAILABLE = find_gle() is not None


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
        controller.render_started.connect(self._on_started)
        controller.render_succeeded.connect(self._on_succeeded)
        controller.render_failed.connect(self._on_failed)
        controller.render_skipped_empty.connect(self._on_skipped)

    def _on_started(self):
        self.started += 1

    def _on_succeeded(self, path):
        self.succeeded.append(path)

    def _on_failed(self, errors, raw):
        self.failed.append((errors, raw))

    def _on_skipped(self):
        self.skipped += 1


def _wait_until(predicate, timeout_ms=10000):
    """Spin the Qt event loop until ``predicate()`` is true or timeout.

    Returns True if the predicate became true, False on timeout.
    """
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


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_render_succeeds_and_produces_png(qapp):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.succeeded or rec.failed, 10000)
        assert not rec.failed, rec.failed
        assert rec.succeeded
        png = Path(rec.succeeded[-1])
        assert png.exists()
        assert png.stat().st_size > 1000  # non-trivial PNG
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_second_render_lands_after_mutation(qapp):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.request_render()
        assert _wait_until(lambda: len(rec.succeeded) >= 1, 10000)
        first = rec.succeeded[-1]

        # Mutate: add a second series and notify.
        x = np.linspace(0, 2 * np.pi, 50)
        doc.figure.axes_list[0].plot(x, np.cos(x), label="cos")
        doc.notify_changed()

        assert _wait_until(lambda: len(rec.succeeded) >= 2, 10000)
        second = rec.succeeded[-1]
        # A newer, distinctly-numbered render landed.
        assert second != first
        assert Path(second).exists()
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_render_failure_parses_structured_errors(qapp, monkeypatch):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)

    # Inject an invalid GLE line into the script-writing step so GLE fails
    # with a structured, line-numbered error.
    original = ctrl._write_script

    def broken_write(work_fig, session):
        original(work_fig, session)
        script = session / "preview.gle"
        text = script.read_text(encoding="utf-8")
        script.write_text(text + "\nthis_is_not_valid_gle @@@\n", encoding="utf-8")

    monkeypatch.setattr(ctrl, "_write_script", broken_write)

    try:
        ctrl.request_render()
        assert _wait_until(lambda: rec.failed or rec.succeeded, 10000)
        assert rec.failed, "expected a render failure"
        errors, raw = rec.failed[-1]
        assert errors
        # At least one structured error should carry a line number.
        assert any(getattr(e, "line", None) is not None for e in errors)
    finally:
        ctrl.shutdown()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_rapid_changes_are_coalesced(qapp):
    doc = _make_sin_document()
    ctrl = PreviewController(doc, debounce_ms=50)
    rec = SignalRecorder(ctrl)
    try:
        # Fire many changes rapidly. The debounce should collapse them, and
        # any overlap coalesces so only a small number of renders start.
        for _ in range(5):
            doc.notify_changed()
        assert _wait_until(lambda: len(rec.succeeded) >= 1, 10000)
        # Let things settle in case a coalesced follow-up render is pending.
        _wait_until(lambda: False, 400)

        # Far fewer renders started than change events fired.
        assert rec.started <= 3, f"too many renders started: {rec.started}"
        # The final displayed render corresponds to the latest requested seq.
        assert ctrl._running_seq == ctrl._requested_seq
    finally:
        ctrl.shutdown()


def test_empty_document_skips_render(qapp):
    doc = FigureDocument()
    doc.new_figure()  # one empty subplot, no series
    ctrl = PreviewController(doc, debounce_ms=20)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.request_render()
        # No GLE process should be launched.
        assert rec.started == 0
        assert rec.skipped >= 1
        assert not rec.succeeded
    finally:
        ctrl.shutdown()


def test_no_figure_skips_render(qapp):
    doc = FigureDocument()  # figure is None
    ctrl = PreviewController(doc, debounce_ms=20)
    rec = SignalRecorder(ctrl)
    try:
        ctrl.request_render()
        assert rec.started == 0
        assert rec.skipped >= 1
    finally:
        ctrl.shutdown()


# ----------------------------------------------------------------------
# PreviewView
# ----------------------------------------------------------------------
def _write_png(path: Path, w: int, h: int):
    pix = QPixmap(w, h)
    pix.fill()
    pix.save(str(path), "PNG")


def test_view_show_image_preserves_transform_on_same_size(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)
    view.show()

    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    _write_png(p1, 200, 150)
    _write_png(p2, 200, 150)

    view.show_image(str(p1))
    # Zoom in, then show a same-size image; transform must be preserved.
    view.scale(1.5, 1.5)
    before = view.transform().m11()
    view.show_image(str(p2))
    after = view.transform().m11()

    assert abs(before - after) < 1e-6
    assert view.last_good_path == str(p2)


def test_view_show_image_refits_on_size_change(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)
    view.show()

    p1 = tmp_path / "a.png"
    p2 = tmp_path / "big.png"
    _write_png(p1, 200, 150)
    _write_png(p2, 600, 450)

    view.show_image(str(p1))
    view.scale(2.0, 2.0)
    changed = view.transform().m11()
    view.show_image(str(p2))
    refit = view.transform().m11()

    # Different size => refit, so the transform changes.
    assert abs(changed - refit) > 1e-6


def test_view_placeholder_hidden_when_image_present(qapp, tmp_path):
    view = PreviewView()
    view.resize(400, 300)

    # Placeholder shows when nothing is present.
    view.show_placeholder("empty")
    assert view._placeholder_item is not None

    # Once an image is shown, placeholder is cleared...
    p = tmp_path / "a.png"
    _write_png(p, 100, 100)
    view.show_image(str(p))
    assert view._placeholder_item is None

    # ...and a subsequent placeholder request (transient error) is a no-op:
    # the last good image stays.
    view.show_placeholder("compile error")
    assert view._placeholder_item is None
    assert view.last_good_path == str(p)

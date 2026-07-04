"""End-to-end integration test for the gleplot GUI editor (Phase 1, M1).

Drives the *whole* assembled application programmatically on the offscreen Qt
platform, exercising the real editing loop:

    File ▸ New  ->  load a CSV in the Data panel  ->  add a series  ->
    live GLE render lands a PNG  ->  edit the series (color) via the
    document/preview path  ->  a second, newer render lands.

This is a genuine integration test: a real ``MainWindow`` is constructed, the
real :class:`PreviewController` runs a real GLE compile off-thread via
``QProcess``, and we spin the Qt event loop waiting deterministically on the
controller's signals (no ``pytest-qt``). It is marked ``xfail`` when GLE is not
installed (the wiring is exercised, but no PNG can be produced).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from gleplot.compiler import find_gle
from gleplot.gui.main_window import MainWindow

_GLE_AVAILABLE = find_gle() is not None

#: Generous timeout for a real GLE round-trip on a loaded CI box.
_RENDER_TIMEOUT_MS = 20000


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _wait_until(predicate, timeout_ms=_RENDER_TIMEOUT_MS):
    """Spin the Qt event loop until ``predicate()`` is true or timeout.

    Returns True if the predicate became true, False on timeout. Deterministic:
    the poll runs on the event loop, so queued signals (render results) are
    delivered before the predicate is re-checked.
    """
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


class _RenderRecorder:
    """Records render outcomes emitted by the window's preview controller."""

    def __init__(self, controller):
        self.succeeded = []
        self.failed = []
        controller.render_succeeded.connect(lambda p: self.succeeded.append(p))
        controller.render_failed.connect(
            lambda errs, raw: self.failed.append((errs, raw))
        )


def _write_csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text("x,y\n0,0\n1,1\n2,4\n3,9\n4,16\n")
    return p


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_full_editing_loop_new_load_add_render_edit(qapp, tmp_path):
    """New figure -> load CSV -> add series -> render -> edit color -> re-render."""
    window = MainWindow()
    # Shorten the debounce so the test isn't dominated by the debounce wait.
    window.preview_controller.debounce_ms = 50
    recorder = _RenderRecorder(window.preview_controller)

    try:
        # 1) File ▸ New: install a fresh single-subplot figure.
        window._on_new()
        assert window.document.figure is not None
        assert not window.document.is_dirty  # new_figure() starts clean

        # 2) Load a CSV into the Data panel and add a series from its columns.
        csv_path = _write_csv(tmp_path)
        table = window.data_panel.load_file(str(csv_path))
        assert table is not None
        assert window.data_panel.add_series_button.isEnabled()

        window.data_panel.add_series()

        # Adding a series mutates the figure -> document is dirty, title shows *.
        assert window.document.is_dirty
        assert window.windowTitle().endswith("*")
        ax = window.document.figure.gca()
        assert len(ax.lines) == 1

        # 3) The live preview should render the figure to a PNG.
        assert _wait_until(lambda: recorder.succeeded or recorder.failed)
        assert not recorder.failed, recorder.failed
        assert recorder.succeeded, "expected at least one successful render"
        first_png = Path(recorder.succeeded[-1])
        assert first_png.exists()
        assert first_png.stat().st_size > 0

        renders_after_first = len(recorder.succeeded)

        # 4) Edit the series color via the document/preview path (the same path
        #    SeriesPanel uses: mutate the series dict, then notify_changed()).
        ax.lines[0]["color"] = "RED"
        window.document.notify_changed()

        # 5) A second, newer render must land.
        assert _wait_until(lambda: len(recorder.succeeded) > renders_after_first)
        assert not recorder.failed, recorder.failed
        second_png = Path(recorder.succeeded[-1])
        assert second_png.exists()
        # The controller names outputs per render sequence, so the newer render
        # is a distinct file from the first.
        assert str(second_png) != str(first_png)
    finally:
        # Tear down the render engine and window cleanly (also covers the
        # closeEvent shutdown path when not dirty-confirming via a dialog).
        window.preview_controller.shutdown()
        window.deleteLater()

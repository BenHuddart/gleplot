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

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from gleplot.compiler import find_gle
from gleplot.gui import file_ops
from gleplot.gui.export_dialog import ExportDialog
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


def _scratch_settings(tmp_path: Path) -> QSettings:
    """An ini-backed QSettings so recent-files writes never touch the real store."""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_full_m2_workflow(qapp, tmp_path):
    """Full M2 loop: new -> edit -> undo/redo -> save -> export -> reopen -> edit.

    Exercises the wired-together file/undo/export machinery end to end against a
    real GLE compile, spinning the event loop on the preview controller's
    signals rather than sleeping.
    """
    settings = _scratch_settings(tmp_path)
    window = MainWindow()
    window.preview_controller.debounce_ms = 50
    recorder = _RenderRecorder(window.preview_controller)

    try:
        # 1) New figure + load CSV + add a series.
        window._on_new()
        csv_path = _write_csv(tmp_path)
        assert window.data_panel.load_file(str(csv_path)) is not None
        window.data_panel.add_series()
        ax = window.document.figure.gca()
        assert len(ax.lines) == 1

        # 2) First render lands.
        assert _wait_until(lambda: recorder.succeeded or recorder.failed)
        assert not recorder.failed, recorder.failed
        n_after_first = len(recorder.succeeded)

        # 3) Change color and notify -> second render.
        state_before_edit = window.document.figure.to_dict()
        ax.lines[0]["color"] = "RED"
        window.document.notify_changed()
        assert _wait_until(lambda: len(recorder.succeeded) > n_after_first)
        assert not recorder.failed, recorder.failed
        state_after_edit = window.document.figure.to_dict()
        assert state_after_edit != state_before_edit

        # 4) Undo -> state reverts, redo becomes available.
        assert window.undo_stack.undo() is True
        assert window.undo_stack.can_redo is True
        assert window.document.figure.to_dict() == state_before_edit

        # 5) Redo -> state re-applied.
        assert window.undo_stack.redo() is True
        assert window.document.figure.to_dict() == state_after_edit

        # 6) Save to a tmp .gle via file_ops (explicit path, scratch settings).
        gle_path = tmp_path / "project.gle"
        assert file_ops.save_project_current(
            window, window.document, path=gle_path, settings=settings,
        ) is True
        window.undo_stack.mark_saved()
        assert gle_path.exists()
        assert window.document.is_dirty is False
        assert window.undo_stack.is_saved_position is True

        # 7) Export a PNG through the ExportDialog programmatically.
        png_path = tmp_path / "figure.png"
        dialog = ExportDialog(window.document, window, settings=settings)
        dialog._path_edit.setText(str(png_path))
        dialog._format_combo.setCurrentText("png")
        dialog._on_export_clicked()
        assert png_path.exists()
        assert png_path.stat().st_size > 0

        # 8) File-New-equivalent then reopen the saved project.
        window._on_new()
        assert window.document.figure is not None
        recorder.succeeded.clear()
        recorder.failed.clear()

        assert file_ops.open_project(
            window, window.document, path=gle_path, settings=settings,
        ) is True
        # Restored series present + a render lands for the reopened figure.
        reopened_ax = window.document.figure.gca()
        assert len(reopened_ax.lines) == 1
        assert reopened_ax.lines[0].get("color", "").upper() == "RED"
        assert window.document.is_dirty is False
        assert _wait_until(lambda: recorder.succeeded or recorder.failed)
        assert not recorder.failed, recorder.failed

        # 9) Continue editing: add a second series -> dirty again + render.
        n_before_second = len(recorder.succeeded)
        assert window.data_panel.load_file(str(csv_path)) is not None
        window.data_panel.add_series()
        assert len(reopened_ax.lines) == 2
        assert window.document.is_dirty is True
        assert _wait_until(lambda: len(recorder.succeeded) > n_before_second)
        assert not recorder.failed, recorder.failed
    finally:
        window.preview_controller.shutdown()
        window._cleanup_gle_temp_dirs()
        window.deleteLater()


def _write_gle(tmp_path: Path) -> Path:
    """A minimal valid GLE script (no external data files)."""
    p = tmp_path / "hand.gle"
    p.write_text(
        "size 8 6\n"
        "begin graph\n"
        "   title \"hand-written\"\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 10\n"
        "   let d1 = x\n"
        "   d1 line\n"
        "end graph\n"
    )
    return p


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_gle_preview_mode(qapp, tmp_path):
    """Open a hand-written .gle read-only, then File ▸ New restores editing."""
    gle_path = _write_gle(tmp_path)
    window = MainWindow()
    window.preview_controller.debounce_ms = 50
    try:
        # Enter GLE-preview mode directly via the main-window entry method.
        window._enter_gle_preview_mode(gle_path)

        assert window.is_gle_preview_mode is True
        # Preview shows the compiled image (last_good_path set + pixmap item).
        assert window.preview_view.last_good_path is not None
        assert window.preview_view._pixmap_item is not None

        # Editing docks disabled; Save/Save As disabled; Export stays enabled.
        assert window.data_panel.isEnabled() is False
        assert window.properties_tabs.isEnabled() is False
        assert window.action_save.isEnabled() is False
        assert window.action_save_as.isEnabled() is False
        assert window.action_undo.isEnabled() is False
        assert window.action_export.isEnabled() is True

        # Title reflects preview mode.
        assert "(preview)" in window.windowTitle()
        # A temp dir is owned for cleanup.
        assert window._gle_temp_dirs

        # File ▸ New restores document editing mode.
        window._on_new()
        assert window.is_gle_preview_mode is False
        assert window.data_panel.isEnabled() is True
        assert window.properties_tabs.isEnabled() is True
        assert window.action_save.isEnabled() is True
        assert window.document.figure is not None
        # Temp dirs were cleaned up on leaving the mode.
        assert not window._gle_temp_dirs
    finally:
        window.preview_controller.shutdown()
        window._cleanup_gle_temp_dirs()
        window.deleteLater()

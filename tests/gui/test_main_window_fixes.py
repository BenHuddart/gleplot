"""Regression tests for Phase-2 main-window fixes (FIX 2, FIX 10).

Offscreen, plain-pytest tests driving a real :class:`MainWindow`. Skip cleanly
when PySide6 is unavailable.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtWidgets import QApplication, QMessageBox

import numpy as np

from gleplot.gui.main_window import MainWindow


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


# ----------------------------------------------------------------------
# FIX 2: _confirm_discard_if_dirty must consult document.is_dirty even in
# GLE-preview mode (entering preview does NOT discard the dirty document).
# ----------------------------------------------------------------------
def test_confirm_discard_prompts_when_dirty_even_in_gle_preview(qapp, monkeypatch):
    window = MainWindow()
    try:
        # Make the document dirty (an unsaved edit exists).
        window.document.new_figure()
        window.document.notify_changed()
        assert window.document.is_dirty is True

        # Simulate being in GLE-preview mode (the VIEW is elsewhere, but the
        # dirty document is still held).
        window._gle_preview_path = Path("hand.gle")
        assert window.is_gle_preview_mode is True

        prompted = {"count": 0}

        def fake_question(*args, **kwargs):
            prompted["count"] += 1
            return QMessageBox.StandardButton.Cancel

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))

        result = window._confirm_discard_if_dirty("Open a file")

        # The dialog MUST have been invoked (not auto-returned True), and since
        # the user chose Cancel the helper must refuse.
        assert prompted["count"] == 1
        assert result is False
    finally:
        window._gle_preview_path = None
        window.preview_controller.shutdown()
        window.deleteLater()


def test_confirm_discard_no_prompt_when_clean_in_gle_preview(qapp, monkeypatch):
    window = MainWindow()
    try:
        window.document.new_figure()  # clean
        assert window.document.is_dirty is False
        window._gle_preview_path = Path("hand.gle")

        prompted = {"count": 0}

        def fake_question(*args, **kwargs):
            prompted["count"] += 1
            return QMessageBox.StandardButton.Cancel

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))

        # Clean document -> safe to proceed, no prompt.
        assert window._confirm_discard_if_dirty("Open a file") is True
        assert prompted["count"] == 0
    finally:
        window._gle_preview_path = None
        window.preview_controller.shutdown()
        window.deleteLater()


# ----------------------------------------------------------------------
# FIX 10: undo/redo (set_figure) must NOT reset the preview view; File-New
# and project-open must.
# ----------------------------------------------------------------------
def _seed_view_state(window):
    """Simulate an image having been shown at a known size + saved zoom."""
    window.preview_view._has_shown_image = True
    window.preview_view._last_image_size = (640, 480)


def test_undo_set_figure_preserves_preview_view_state(qapp):
    window = MainWindow()
    try:
        # New figure + a real edit so undo has something to restore.
        fig = window.document.new_figure()
        ax = fig.gca()
        x = np.linspace(0, 1, 10)
        ax.plot(x, x, label="s")
        window.document.notify_changed()  # records an undo step

        # Pretend the preview rendered an image (seeds the same-size fast path).
        _seed_view_state(window)

        # Undo -> set_figure fires figure_replaced. The view state must be
        # PRESERVED (so a same-size re-render keeps the zoom/pan).
        assert window.undo_stack.undo() is True
        assert window.preview_view._has_shown_image is True
        assert window.preview_view._last_image_size == (640, 480)
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()


def test_file_new_resets_preview_view(qapp):
    window = MainWindow()
    try:
        window.document.new_figure()
        _seed_view_state(window)

        # File>New must reset the view so the fresh figure starts framed.
        window._on_new()
        assert window.preview_view._has_shown_image is False
        assert window.preview_view._last_image_size is None
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()


def test_open_project_resets_preview_view(qapp, tmp_path):
    from gleplot.figure import Figure
    from gleplot.project import save_project

    src = tmp_path / "proj.glep"
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="s")
    save_project(fig, src)

    window = MainWindow()
    try:
        window.document.new_figure()
        _seed_view_state(window)

        # A successful project open must reset the view (a genuinely different
        # document arrived).
        window._dispatch_open(str(src))
        assert window.preview_view._has_shown_image is False
        assert window.preview_view._last_image_size is None
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()

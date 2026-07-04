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
    # Track C3 (native-.gle rewiring): _dispatch_open now parses a .gle as the
    # native editable format and installs it into the document. A genuinely
    # different document arriving must reset the preview view (so the reopened
    # figure starts framed). This .gle has no programmatic constructs, so it
    # opens editable with no read-only-preview prompt.
    from gleplot.figure import Figure

    src = tmp_path / "proj.gle"
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="s")
    fig.savefig_gle(str(src))

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


# ----------------------------------------------------------------------
# Finding 1: entering GLE-preview mode hard-disables the annotation overlay so
# a stray drag/click cannot mutate the hidden document figure.
# ----------------------------------------------------------------------
def _enter_preview_stubbed(window, monkeypatch, path):
    """Enter GLE-preview mode without a real GLE compile."""
    from gleplot.gui import gle_viewer
    from gleplot.gui.gle_viewer import GlePreviewResult

    monkeypatch.setattr(
        gle_viewer,
        "compile_gle_preview",
        lambda p, **kw: GlePreviewResult(
            png_path=None, errors=[], raw_output="", success=False, work_dir=None
        ),
    )
    window._enter_gle_preview_mode(Path(path))


def test_enter_gle_preview_disables_overlay(qapp, monkeypatch):
    window = MainWindow()
    try:
        overlay = window.annotation_overlay
        # Pretend a prior document render left the overlay live.
        overlay._enabled = True
        overlay._add_mode = True

        _enter_preview_stubbed(window, monkeypatch, "hand.gle")

        assert window.is_gle_preview_mode is True
        # Overlay hard-disabled: no items, add-mode cancelled, disabled flag set.
        assert overlay._disabled is True
        assert overlay.enabled is False
        assert overlay.add_mode is False
        assert overlay.items == []
    finally:
        window._gle_preview_path = None
        window.preview_controller.shutdown()
        window.deleteLater()


def test_overlay_commit_paths_noop_while_disabled(qapp, monkeypatch):
    """Belt-and-braces: disabled commit paths mutate nothing and never notify."""
    window = MainWindow()
    try:
        # Build a document with one annotation and a live overlay item.
        fig = window.document.new_figure()
        ax = fig.gca()
        ax.plot([0, 1], [0, 1], label="s")
        ax.text(0.5, 0.5, "keepme")

        from gleplot.gui.annotations import AnnotationItem
        from gleplot.gui.geometry import AxesCalibration

        cal = AxesCalibration(0, (0, 1), (0, 1), False, False, (1.0, 1.0, 4.0, 4.0))
        overlay = window.annotation_overlay
        item = AnnotationItem(overlay, ax.texts[0], cal)
        overlay._items = [item]

        _enter_preview_stubbed(window, monkeypatch, "hand.gle")
        assert overlay._disabled is True

        notified = {"n": 0}
        window.document.figure_changed.connect(
            lambda: notified.__setitem__("n", notified["n"] + 1)
        )
        # All commit paths must be inert while disabled.
        overlay.commit_item_move(item)
        overlay.commit_item_text(item, "changed")
        overlay.delete_item(item)
        assert notified["n"] == 0
        # The annotation dict is untouched.
        assert ax.texts[0]["text"] == "keepme"
        assert ax.texts[0]["x"] == pytest.approx(0.5)
    finally:
        window._gle_preview_path = None
        window.preview_controller.shutdown()
        window.deleteLater()


def test_leave_gle_preview_reenables_overlay(qapp, monkeypatch):
    window = MainWindow()
    try:
        _enter_preview_stubbed(window, monkeypatch, "hand.gle")
        assert window.annotation_overlay._disabled is True

        window._leave_gle_preview_mode()
        assert window.is_gle_preview_mode is False
        # Disabled state lifted; overlay is free to rebuild on the next render.
        assert window.annotation_overlay._disabled is False
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()


# ----------------------------------------------------------------------
# Finding 2: while in GLE-preview mode, can_undo/redo transitions must NOT
# re-enable the Undo/Redo actions; _update_gle_mode_actions is authoritative.
# ----------------------------------------------------------------------
def test_undo_action_stays_disabled_in_preview_mode(qapp, monkeypatch):
    window = MainWindow()
    try:
        _enter_preview_stubbed(window, monkeypatch, "hand.gle")
        # _update_gle_mode_actions ran on enter: both actions disabled.
        assert window.action_undo.isEnabled() is False
        assert window.action_redo.isEnabled() is False

        # A can_undo_changed(True) landing while in preview mode (the underlying
        # document stack keeps ticking) must NOT re-enable the action.
        window.undo_stack.can_undo_changed.emit(True)
        window.undo_stack.can_redo_changed.emit(True)
        assert window.action_undo.isEnabled() is False
        assert window.action_redo.isEnabled() is False
    finally:
        window._gle_preview_path = None
        window.preview_controller.shutdown()
        window.deleteLater()


def test_undo_action_restored_on_leaving_preview_mode(qapp, monkeypatch):
    window = MainWindow()
    try:
        # Create a real undo step so the stack reports can_undo True.
        fig = window.document.new_figure()
        fig.gca().plot([0, 1], [0, 1], label="s")
        window.document.notify_changed()
        assert window.undo_stack.can_undo is True
        assert window.action_undo.isEnabled() is True

        _enter_preview_stubbed(window, monkeypatch, "hand.gle")
        assert window.action_undo.isEnabled() is False

        window._leave_gle_preview_mode()
        # Back in document mode, the action reflects the live stack again.
        assert window.action_undo.isEnabled() is True

        # And a subsequent transition once again drives the action.
        window.undo_stack.can_undo_changed.emit(False)
        assert window.action_undo.isEnabled() is False
    finally:
        window.preview_controller.shutdown()
        window.deleteLater()

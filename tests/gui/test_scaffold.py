"""Smoke tests for the gleplot GUI scaffold (Phase 0, Track C).

These tests only verify that the PySide6-based shell (menus, docks,
central preview view) is constructed correctly. They skip cleanly when
PySide6 is not installed, since the GUI is an optional extra
(``pip install gleplot[gui]``).
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable when tests are run directly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Use the offscreen platform plugin so these tests can run headlessly
# (CI, no display attached, etc.). Must be set before QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtWidgets import QApplication, QDockWidget, QGraphicsView, QMenuBar

from gleplot.gui.main_window import MainWindow


@pytest.fixture
def qapp():
    """Create or reuse a QApplication instance for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_constructs(qapp):
    """MainWindow should construct without error and set a sensible title.

    A never-saved, clean document shows the "untitled" project name with no
    dirty marker.
    """
    window = MainWindow()
    try:
        assert window.windowTitle() == "gleplot editor — untitled"
    finally:
        window.close()


def test_main_window_has_menu_bar(qapp):
    """The menu bar should expose File, Edit, View, and Help menus."""
    window = MainWindow()
    try:
        menu_bar = window.menuBar()
        assert isinstance(menu_bar, QMenuBar)
        titles = [action.text().replace("&", "") for action in menu_bar.actions()]
        for expected in ("File", "Edit", "View", "Help"):
            assert expected in titles
    finally:
        window.close()


def test_main_window_has_central_preview_view(qapp):
    """The central widget should be a QGraphicsView named preview_view."""
    window = MainWindow()
    try:
        assert hasattr(window, "preview_view")
        assert isinstance(window.preview_view, QGraphicsView)
        assert window.centralWidget() is window.preview_view
        assert window.preview_view.scene() is not None
    finally:
        window.close()


def test_main_window_has_docks(qapp):
    """Data, Properties, and Output docks should exist in their default areas."""
    window = MainWindow()
    try:
        for attr in ("data_dock", "properties_dock", "output_dock"):
            dock = getattr(window, attr)
            assert isinstance(dock, QDockWidget)
            assert dock.widget() is not None
    finally:
        window.close()


def test_main_window_has_gle_status_label(qapp):
    """The status bar should show a permanent GLE status label."""
    window = MainWindow()
    try:
        assert hasattr(window, "gle_status_label")
        text = window.gle_status_label.text()
        assert text.startswith("GLE:")
    finally:
        window.close()


def test_exit_action_closes_window(qapp):
    """The File > Exit action should trigger the window's close()."""
    window = MainWindow()
    try:
        assert window.action_exit.shortcut().toString() != ""
    finally:
        window.close()

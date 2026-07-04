"""Main window for the gleplot GUI editor.

This module defines :class:`MainWindow`, the top-level shell for the
gleplot plot editor. It provides the menu bar, dock widgets, central
preview area, and status bar that later development tracks (preview
engine, data manager, property panels) will populate with real
functionality. For now most actions are disabled or no-op placeholders.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

import gleplot

#: Placeholder text shown in the central preview view before a figure exists.
_NO_FIGURE_TEXT = "No figure — File ▸ New to start"


def _detect_gle_status() -> str:
    """Return a human-readable GLE detection status string.

    Uses ``gleplot.compiler.find_gle`` to locate GLE. The GUI must not crash
    if detection fails for any reason (missing GLE, unexpected environment,
    etc.), so any exception here degrades gracefully to "GLE: not found"
    rather than propagating.
    """
    try:
        from gleplot.compiler import find_gle

        path = find_gle()
    except Exception:  # noqa: BLE001 - status detection must never crash the GUI
        return "GLE: not found"

    if path:
        return f"GLE: {path}"
    return "GLE: not found"


def _make_placeholder_dock_widget(text: str) -> QWidget:
    """Create a simple placeholder widget with a centered label."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    return widget


class MainWindow(QMainWindow):
    """Top-level window for the gleplot plot editor.

    Attributes
    ----------
    preview_view : QGraphicsView
        Central widget used by later tracks to render the live plot preview.
    data_dock, properties_dock, output_dock : QDockWidget
        Dock widgets reserved for the data manager, property panels, and
        compiler/output log respectively.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("gleplot editor")
        self.resize(1200, 800)

        self._create_central_widget()
        self._create_docks()
        self._create_actions()
        self._create_menus()
        self._create_status_bar()

        self._apply_default_dock_layout()

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------
    def _create_central_widget(self) -> None:
        """Create the central QGraphicsView used for the plot preview."""
        self.preview_view = QGraphicsView(self)
        scene = QGraphicsScene(self)
        self.preview_view.setScene(scene)

        placeholder = scene.addText(_NO_FIGURE_TEXT)
        placeholder.setDefaultTextColor(Qt.GlobalColor.gray)

        self.setCentralWidget(self.preview_view)

    # ------------------------------------------------------------------
    # Dock widgets
    # ------------------------------------------------------------------
    def _create_docks(self) -> None:
        """Create the Data, Properties, and Output dock widgets."""
        self.data_dock = QDockWidget("Data", self)
        self.data_dock.setObjectName("data_dock")
        self.data_dock.setWidget(_make_placeholder_dock_widget("No data loaded"))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_dock)

        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("properties_dock")
        self.properties_dock.setWidget(
            _make_placeholder_dock_widget("No selection")
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)

        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setObjectName("output_dock")
        self.output_dock.setWidget(_make_placeholder_dock_widget("No output yet"))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)

    def _apply_default_dock_layout(self) -> None:
        """Apply a sensible default size/visibility for the docks."""
        self.resizeDocks([self.data_dock], [250], Qt.Orientation.Horizontal)
        self.resizeDocks([self.properties_dock], [300], Qt.Orientation.Horizontal)
        self.resizeDocks([self.output_dock], [180], Qt.Orientation.Vertical)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _create_actions(self) -> None:
        """Create QActions for the menu bar."""
        # File menu
        self.action_new = QAction("&New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.setEnabled(False)

        self.action_open = QAction("&Open…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.setEnabled(False)

        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.setEnabled(False)

        self.action_save_as = QAction("Save &As…", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.setEnabled(False)

        self.action_export = QAction("&Export…", self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.setEnabled(False)

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_exit.triggered.connect(self.close)

        # Edit menu
        self.action_undo = QAction("&Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.setEnabled(False)

        self.action_redo = QAction("&Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.setEnabled(False)

        # View menu (dock toggles)
        self.action_toggle_data = self.data_dock.toggleViewAction()
        self.action_toggle_properties = self.properties_dock.toggleViewAction()
        self.action_toggle_output = self.output_dock.toggleViewAction()

        # Help menu
        self.action_about = QAction("&About", self)
        self.action_about.triggered.connect(self._show_about_dialog)

    def _create_menus(self) -> None:
        """Create the menu bar and populate it with actions."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.action_toggle_data)
        view_menu.addAction(self.action_toggle_properties)
        view_menu.addAction(self.action_toggle_output)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.action_about)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create the status bar with a permanent GLE-detection label."""
        status_bar = self.statusBar()
        self.gle_status_label = QLabel(_detect_gle_status())
        status_bar.addPermanentWidget(self.gle_status_label)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _show_about_dialog(self) -> None:
        """Show the About dialog with gleplot version and GLE status."""
        version = getattr(gleplot, "__version__", "unknown")
        gle_status = _detect_gle_status()
        QMessageBox.about(
            self,
            "About gleplot editor",
            f"gleplot editor\n\ngleplot version: {version}\n{gle_status}",
        )

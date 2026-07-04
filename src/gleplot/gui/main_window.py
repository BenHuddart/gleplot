"""Main window for the gleplot GUI editor.

This module defines :class:`MainWindow`, the top-level shell for the gleplot
plot editor. It wires the Phase 1 components together into a working editing
loop:

* a shared :class:`~gleplot.gui.document.FigureDocument` (single source of
  truth);
* a central :class:`~gleplot.gui.preview.PreviewView` driven by a
  :class:`~gleplot.gui.preview.PreviewController` (debounced, async GLE
  render);
* a Data dock (:class:`~gleplot.gui.data.panel.DataPanel`) for loading data and
  creating series;
* a Properties dock with Figure/Axes/Series property panels;
* an Output dock (:class:`~gleplot.gui.error_panel.ErrorPanel`) for compile
  errors.

File ▸ New is functional; Open/Save/Save As/Export remain disabled placeholders
for Phase 2 (see the notes on :meth:`_create_actions` for where those hooks
should attach).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

import gleplot
from gleplot.compiler import GLEError
from gleplot.gui.data.panel import DataPanel
from gleplot.gui.document import FigureDocument
from gleplot.gui.error_panel import ErrorPanel
from gleplot.gui.panels import AxesPanel, FigurePanel, SeriesPanel
from gleplot.gui.preview import PreviewController, PreviewView

#: Placeholder shown in the preview before any renderable figure exists.
_EMPTY_PREVIEW_TEXT = "Nothing to render yet — load data and add a series"

#: How long transient status-bar messages linger (milliseconds).
_STATUS_MS = 4000

#: Base window title; a " *" suffix is appended while the document is dirty.
_BASE_TITLE = "gleplot editor"


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


class MainWindow(QMainWindow):
    """Top-level window for the gleplot plot editor.

    Attributes
    ----------
    document : FigureDocument
        The shared observable document all panels and the preview bind to.
    preview_view : PreviewView
        Central widget showing the live rendered PNG.
    preview_controller : PreviewController
        Debounced async GLE render engine driving ``preview_view``.
    data_panel : DataPanel
        Data-loading / series-creation panel (Data dock).
    figure_panel, axes_panel, series_panel : QWidget
        Property panels hosted in the Properties dock's tab widget.
    error_panel : ErrorPanel
        Compile-error list (Output dock).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_BASE_TITLE)
        self.resize(1200, 800)

        # The document must exist before any panel/controller that binds to it.
        self.document = FigureDocument()

        self._create_central_widget()
        self._create_docks()
        self._create_actions()
        self._create_menus()
        self._create_status_bar()

        self._connect_document_signals()
        self._connect_preview_signals()

        self._apply_default_dock_layout()

    # ------------------------------------------------------------------
    # Central widget / preview
    # ------------------------------------------------------------------
    def _create_central_widget(self) -> None:
        """Install the live-preview view and its render controller."""
        self.preview_view = PreviewView(self)
        self.preview_view.show_placeholder(_EMPTY_PREVIEW_TEXT)
        self.setCentralWidget(self.preview_view)

        self.preview_controller = PreviewController(self.document, parent=self)

    # ------------------------------------------------------------------
    # Dock widgets
    # ------------------------------------------------------------------
    def _create_docks(self) -> None:
        """Create the Data, Properties, and Output dock widgets."""
        # Data dock -----------------------------------------------------
        self.data_dock = QDockWidget("Data", self)
        self.data_dock.setObjectName("data_dock")
        self.data_panel = DataPanel(self.document)
        self.data_dock.setWidget(self.data_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_dock)

        # Properties dock ----------------------------------------------
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("properties_dock")

        self.properties_tabs = QTabWidget(self.properties_dock)
        self.figure_panel = FigurePanel(self.document)
        self.axes_panel = AxesPanel(self.document)
        self.series_panel = SeriesPanel(self.document)
        self.properties_tabs.addTab(self.figure_panel, "Figure")
        self.properties_tabs.addTab(self.axes_panel, "Axes")
        self.properties_tabs.addTab(self.series_panel, "Series")
        self.properties_dock.setWidget(self.properties_tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)

        # Output dock ---------------------------------------------------
        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setObjectName("output_dock")
        self.error_panel = ErrorPanel(self.output_dock)
        self.output_dock.setWidget(self.error_panel)
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
        """Create QActions for the menu bar.

        Phase 2 note: Open/Save/Save As/Export are intentionally left disabled
        here. When those land, connect ``action_open``/``action_save``/... to
        slots that (for Open) build a Figure and call ``document.set_figure``,
        and (for Save) call ``document.mark_clean`` on success. Export should
        reuse the same snapshot->GLE path the preview controller uses.
        """
        # File menu
        self.action_new = QAction("&New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._on_new)

        self.action_open = QAction("&Open…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.setEnabled(False)  # Phase 2

        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.setEnabled(False)  # Phase 2

        self.action_save_as = QAction("Save &As…", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.setEnabled(False)  # Phase 2

        self.action_export = QAction("&Export…", self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.setEnabled(False)  # Phase 2

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

        # View menu (preview zoom + dock toggles)
        self.action_fit_window = QAction("&Fit to window", self)
        self.action_fit_window.setShortcut(QKeySequence("Ctrl+0"))
        self.action_fit_window.triggered.connect(self.preview_view.fit_to_window)

        self.action_actual_size = QAction("&Actual size", self)
        self.action_actual_size.setShortcut(QKeySequence("Ctrl+1"))
        self.action_actual_size.triggered.connect(self.preview_view.zoom_actual_size)

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
        view_menu.addAction(self.action_fit_window)
        view_menu.addAction(self.action_actual_size)
        view_menu.addSeparator()
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
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_document_signals(self) -> None:
        self.document.dirty_changed.connect(self._on_dirty_changed)
        self.document.figure_replaced.connect(self.preview_view.reset_view)
        self.data_panel.series_added.connect(self._on_series_added)

    def _connect_preview_signals(self) -> None:
        pc = self.preview_controller
        pc.render_started.connect(self._on_render_started)
        pc.render_succeeded.connect(self._on_render_succeeded)
        pc.render_failed.connect(self._on_render_failed)
        pc.render_skipped_empty.connect(self._on_render_skipped_empty)

    # ------------------------------------------------------------------
    # Preview slots
    # ------------------------------------------------------------------
    def _on_render_started(self) -> None:
        self.statusBar().showMessage("Rendering…", _STATUS_MS)

    def _on_render_succeeded(self, path: str) -> None:
        self.preview_view.show_image(path)
        self.error_panel.clear()
        self.statusBar().showMessage("Rendered", 1500)

    def _on_render_failed(self, errors: List[GLEError], raw: str) -> None:
        self.error_panel.set_errors(errors, raw)
        self.statusBar().showMessage(
            f"Compile failed ({len(errors)} errors)", _STATUS_MS
        )

    def _on_render_skipped_empty(self) -> None:
        self.error_panel.clear()
        self.preview_view.show_placeholder(_EMPTY_PREVIEW_TEXT)

    # ------------------------------------------------------------------
    # Document slots
    # ------------------------------------------------------------------
    def _on_dirty_changed(self, dirty: bool) -> None:
        self.setWindowTitle(f"{_BASE_TITLE} *" if dirty else _BASE_TITLE)

    def _on_series_added(self, label: str) -> None:
        self.statusBar().showMessage(f"Added series: {label}", _STATUS_MS)

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        """File ▸ New: replace the document with a fresh single-subplot figure.

        If there are unsaved changes, confirm discarding them first.
        """
        if not self._confirm_discard_if_dirty("Start a new figure"):
            return
        self.document.new_figure()

    def _confirm_discard_if_dirty(self, action_desc: str) -> bool:
        """Return True if it's safe to proceed (clean, or user chose Discard)."""
        if not self.document.is_dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Discard changes?",
            f"The current figure has unsaved changes.\n\n{action_desc} anyway?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        """Confirm discard on a dirty document, then tear down the render engine."""
        if not self._confirm_discard_if_dirty("Exit"):
            event.ignore()
            return
        self.preview_controller.shutdown()
        event.accept()

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

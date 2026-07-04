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

File ▸ New/Open/Save/Save As/Export and Edit ▸ Undo/Redo are all functional
(Phase 2, M2). ``.gle`` is the native, editable on-disk format: File ▸ Open
parses a ``.gle`` file through :func:`gleplot.parser.recognizer.parse_gle_figure`
(tolerantly, preserving any unrecognized content as raw GLE) and installs it as
an editable figure. The window supports two modes:

* **document mode** -- the normal editable-figure workflow, driven by the
  :class:`FigureDocument` / :class:`PreviewController` loop;
* **GLE-preview mode** -- a read-only view compiled once with
  :mod:`gleplot.gui.gle_viewer`. This is now a *fallback*, offered when a
  ``.gle`` uses GLE programming constructs (a ``programmatic:`` recognizer
  warning) that editing might restructure, or when a file cannot be opened as
  an editable figure at all.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

import gleplot
from gleplot.compiler import GLEError
from gleplot.gui import file_ops, gle_viewer
from gleplot.gui.data.panel import DataPanel
from gleplot.gui.document import FigureDocument
from gleplot.gui.error_panel import ErrorPanel
from gleplot.gui.export_dialog import run_export_dialog
from gleplot.gui.panels import (
    AxesPanel,
    FigurePanel,
    LayoutPanel,
    RawGlePanel,
    SeriesPanel,
)
from gleplot.gui.preview import PreviewController, PreviewView
from gleplot.gui.undo import UndoStack
from gleplot.parser.recognizer import parse_gle_figure

#: Placeholder shown in the preview before any renderable figure exists.
_EMPTY_PREVIEW_TEXT = "Nothing to render yet — load data and add a series"

#: How long transient status-bar messages linger (milliseconds).
_STATUS_MS = 4000

#: Base window title prefix.
_BASE_TITLE = "gleplot editor"

#: Filter for the File ▸ Open dialog. ``.gle`` is the native editable format.
_OPEN_FILTER = "GLE figure (*.gle);;All files (*)"

#: Export formats recognised (by suffix) in GLE-preview mode.
_GLE_EXPORT_SUFFIXES = {"pdf", "png", "eps", "svg", "jpg"}


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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        settings: Optional[QSettings] = None,
    ) -> None:
        super().__init__(parent)
        #: Optional injected QSettings store, forwarded to file_ops calls so
        #: tests/embedders can isolate recent-files/last-dir state from the
        #: user's real settings. ``None`` preserves prior behavior (each
        #: file_ops call falls back to QSettings("gleplot", "gleplot")).
        self._settings = settings
        self.resize(1200, 800)

        # GLE-preview mode state. ``_gle_preview_path`` is the .gle file being
        # previewed (None => document mode). ``_gle_temp_dirs`` accumulates the
        # mkdtemp'd compile output directories we own and must clean up.
        self._gle_preview_path: Optional[Path] = None
        self._gle_temp_dirs: List[Path] = []

        # The document must exist before any panel/controller that binds to it.
        self.document = FigureDocument()

        self._create_central_widget()
        self._create_docks()
        self._create_actions()
        self._create_menus()
        self._create_status_bar()

        # UndoStack observes the document; construct it after the preview
        # controller so both are wired as independent observers (order is
        # irrelevant per UndoStack's contract).
        self.undo_stack = UndoStack(self.document)

        self._connect_document_signals()
        self._connect_preview_signals()
        self._connect_undo_signals()

        self._apply_default_dock_layout()
        self._update_window_title()

        # Start with an editable figure so first-run users can add series
        # immediately instead of having to discover File > New (the document
        # starts clean; the preview shows its empty-state placeholder).
        self.document.new_figure()

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
        self.layout_panel = LayoutPanel(self.document)
        self.figure_panel = FigurePanel(self.document)
        self.axes_panel = AxesPanel(self.document)
        self.series_panel = SeriesPanel(self.document)
        self.raw_gle_panel = RawGlePanel(self.document)
        self.properties_tabs.addTab(self.layout_panel, "Layout")
        self.properties_tabs.addTab(self.figure_panel, "Figure")
        self.properties_tabs.addTab(self.axes_panel, "Axes")
        self.properties_tabs.addTab(self.series_panel, "Series")
        self.properties_tabs.addTab(self.raw_gle_panel, "Raw GLE")
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
        """Create QActions for the menu bar."""
        # File menu
        self.action_new = QAction("&New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._on_new)

        self.action_open = QAction("&Open…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._on_open)

        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self._on_save)

        self.action_save_as = QAction("Save &As…", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.triggered.connect(self._on_save_as)

        self.action_export = QAction("&Export…", self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.triggered.connect(self._on_export)

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_exit.triggered.connect(self.close)

        # Edit menu
        self.action_undo = QAction("&Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.setEnabled(False)
        self.action_undo.triggered.connect(self._on_undo)

        self.action_redo = QAction("&Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.setEnabled(False)
        self.action_redo.triggered.connect(self._on_redo)

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

        self.recent_menu = file_menu.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._rebuild_recent_menu)

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
        self.document.project_path_changed.connect(self._on_project_path_changed)
        # NOTE (FIX 10): we deliberately do NOT connect figure_replaced to
        # preview_view.reset_view. figure_replaced also fires on every
        # undo/redo (UndoStack restores via set_figure), and a blanket reset
        # would discard the user's zoom/pan on each step. reset_view is instead
        # called explicitly only where a *genuinely different* document arrives:
        # File New (_on_new), a successful project open (_dispatch_open), and
        # entering/leaving GLE-preview mode. Undo/redo then preserves zoom via
        # PreviewView's same-size fast path.
        self.data_panel.series_added.connect(self._on_series_added)
        # Layout tab drives which axes the Axes/Series property panels edit.
        self.layout_panel.axes_selected.connect(self.axes_panel.set_axes)
        self.layout_panel.axes_selected.connect(self.series_panel.set_axes)
        # A broken series repointed at a real data file: confirm via status bar.
        self.series_panel.series_repointed.connect(self._on_series_repointed)

    def _connect_preview_signals(self) -> None:
        pc = self.preview_controller
        pc.render_started.connect(self._on_render_started)
        pc.render_succeeded.connect(self._on_render_succeeded)
        pc.render_failed.connect(self._on_render_failed)
        pc.render_skipped_empty.connect(self._on_render_skipped_empty)

    def _connect_undo_signals(self) -> None:
        us = self.undo_stack
        us.can_undo_changed.connect(self.action_undo.setEnabled)
        us.can_redo_changed.connect(self.action_redo.setEnabled)
        # Seed initial enabled state (signals only fire on transitions).
        self.action_undo.setEnabled(us.can_undo)
        self.action_redo.setEnabled(us.can_redo)

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
        # While showing a static .gle preview, no document signals should be
        # driving the controller -- but guard anyway so a stray empty-render
        # signal never clears the read-only preview image.
        if self.is_gle_preview_mode:
            return
        self.error_panel.clear()
        self.preview_view.show_placeholder(_EMPTY_PREVIEW_TEXT)

    # ------------------------------------------------------------------
    # Document slots
    # ------------------------------------------------------------------
    def _on_dirty_changed(self, dirty: bool) -> None:
        self._update_window_title()

    def _on_project_path_changed(self, path: str) -> None:
        self._update_window_title()

    def _on_series_added(self, label: str) -> None:
        self.statusBar().showMessage(f"Added series: {label}", _STATUS_MS)

    def _on_series_repointed(self, path: str) -> None:
        self.statusBar().showMessage(
            f"Relinked series data to {Path(path).name}", _STATUS_MS
        )

    def _update_window_title(self) -> None:
        """Recompute the window title from the current mode/document state.

        Format: ``gleplot editor — <name>`` with a trailing ``*`` appended
        while the document is dirty. ``name`` is the project file's basename
        ("untitled" if never saved), or ``<file.gle> (preview)`` in
        GLE-preview mode (which is read-only and so never shows the marker).
        """
        if self.is_gle_preview_mode:
            name = f"{self._gle_preview_path.name} (preview)"
            dirty = False
        else:
            path = self.document.project_path
            name = path.name if path is not None else "untitled"
            dirty = self.document.is_dirty
        suffix = " *" if dirty else ""
        self.setWindowTitle(f"{_BASE_TITLE} — {name}{suffix}")

    # ------------------------------------------------------------------
    # Mode state
    # ------------------------------------------------------------------
    @property
    def is_gle_preview_mode(self) -> bool:
        """Whether the window is showing a read-only hand-written ``.gle``."""
        return self._gle_preview_path is not None

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        """File ▸ New: replace the document with a fresh single-subplot figure.

        If there are unsaved changes, confirm discarding them first. Leaving
        GLE-preview mode (if active) restores document editing.
        """
        if not self._confirm_discard_if_dirty("Start a new figure"):
            return
        self._leave_gle_preview_mode()
        self.document.new_figure()
        # A fresh figure carries no recovery warnings from a prior Open.
        self.error_panel.clear_warnings()
        # A genuinely new document: frame it fresh (FIX 10). set_figure alone no
        # longer resets the view, so do it explicitly here.
        self.preview_view.reset_view()

    def _on_open(self) -> None:
        """File ▸ Open: pick a ``.gle`` figure and open it as an editable figure.

        ``.gle`` is the native, editable format: the chosen file is parsed and
        installed into the document. Files using GLE programming constructs
        offer a read-only-preview fallback instead (see :meth:`_dispatch_open`).
        Dirty documents are confirmed first.
        """
        if not self._confirm_discard_if_dirty("Open a file"):
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Open", "", _OPEN_FILTER,
        )
        if not chosen:
            return
        self._dispatch_open(chosen)

    def _dispatch_open(self, path_str: str) -> None:
        """Open ``path_str`` as an editable ``.gle`` figure (native format).

        Design (single-parse probe)
        ---------------------------
        ``.gle`` is now the native editable format, but a file that uses GLE
        *programming* constructs (``sub``/``if``/``for``/...) is flagged by the
        recognizer with a ``programmatic:`` warning -- editing it may
        restructure those constructs, so we offer a read-only preview first.
        Deciding between edit and read-only preview needs the recognizer's
        warnings, which means running the parse. To avoid parsing twice, this
        method runs :func:`parse_gle_figure` **once** as a probe *without*
        touching the document, inspects the warnings, then commits to exactly
        one mode:

        * *programmatic file* -> ask (default: read-only preview). Read-only
          discards the probed figure and enters GLE-preview mode; the document
          is never mutated, so it keeps its prior (sane) state.
        * *editable* -> install the already-parsed figure via
          :func:`file_ops.install_recognized` (no re-parse), reset the view,
          surface the recognizer warnings in the Output dock, and update the
          status bar.
        * *parse raised* (unexpected failure / legacy ``.glep``) -> offer the
          read-only GLE preview as a fallback.
        """
        path = Path(path_str)

        # Legacy .glep is no longer editable; route it straight to open_project
        # (which rejects it with a clear message) then offer a preview fallback.
        if path.suffix.lower() == ".glep":
            self._leave_gle_preview_mode()
            if not file_ops.open_project(
                self, self.document, path=path, settings=self._settings
            ):
                self._offer_preview_fallback(path)
            else:
                self.preview_view.reset_view()
            return

        # Probe: parse ONCE without mutating the document.
        try:
            rec = parse_gle_figure(path)
        except Exception as exc:  # noqa: BLE001 - unexpected recognizer failure
            QMessageBox.critical(self, "Open Failed", str(exc))
            self._offer_preview_fallback(path)
            return

        programmatic = any(w.startswith("programmatic:") for w in rec.warnings)
        if programmatic:
            reply = QMessageBox.question(
                self,
                "Programmatic GLE file",
                f"'{path.name}' contains GLE programming constructs "
                "(sub/if/for/...).\n\n"
                "Editing it in the figure editor may restructure those "
                "constructs. Open a read-only preview instead, or edit anyway?",
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Open,
            )
            # 'Open' button = read-only preview (default); 'Yes' = edit anyway.
            if reply != QMessageBox.StandardButton.Yes:
                # Read-only: discard the probed figure, leave the document as-is.
                self._enter_gle_preview_mode(path)
                return

        # Editable open: commit the already-parsed figure (no second parse).
        self._leave_gle_preview_mode()
        file_ops.install_recognized(
            self.document, rec, path, settings=self._settings
        )
        # A genuinely different document arrived: frame it fresh (FIX 10).
        self.preview_view.reset_view()
        self._surface_open_warnings(path)

    def _surface_open_warnings(self, path: Path) -> None:
        """Show recovery warnings in the Output dock + a status-bar summary."""
        warnings = self.document.open_warnings
        self.error_panel.set_warnings(warnings)
        if warnings:
            self.statusBar().showMessage(
                f"Opened {path.name} ({len(warnings)} warnings)", _STATUS_MS
            )
        else:
            self.statusBar().showMessage(f"Opened {path.name}", _STATUS_MS)

    def _offer_preview_fallback(self, path: Path) -> None:
        """Offer a read-only GLE preview after an editable open failed.

        Only meaningful for ``.gle`` files (a legacy ``.glep`` cannot be
        compiled as a GLE script). Asks the user, and enters GLE-preview mode
        on confirmation.
        """
        if path.suffix.lower() != ".gle":
            return
        reply = QMessageBox.question(
            self,
            "Open read-only preview?",
            f"'{path.name}' could not be opened as an editable figure.\n\n"
            "Open it as a read-only GLE preview instead?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._enter_gle_preview_mode(path)

    def _on_save(self) -> None:
        """File ▸ Save: save to the current project path (prompting if unset)."""
        if self.is_gle_preview_mode:
            return
        if file_ops.save_project_current(self, self.document, settings=self._settings):
            self.undo_stack.mark_saved()

    def _on_save_as(self) -> None:
        """File ▸ Save As: save to a newly chosen project path."""
        if self.is_gle_preview_mode:
            return
        if file_ops.save_project_as(self, self.document, settings=self._settings):
            self.undo_stack.mark_saved()

    def _on_export(self) -> None:
        """File ▸ Export: export the document, or the previewed ``.gle``."""
        if self.is_gle_preview_mode:
            self._export_gle_preview()
        else:
            exported_path = run_export_dialog(self.document, self)
            if exported_path is not None:
                self.statusBar().showMessage(
                    f"Exported {exported_path}", _STATUS_MS
                )

    def _export_gle_preview(self) -> None:
        """Export the currently-previewed ``.gle`` via a Save dialog."""
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Export GLE Preview", "",
            "PDF (*.pdf);;PNG (*.png);;EPS (*.eps);;SVG (*.svg);;JPEG (*.jpg)",
        )
        if not chosen:
            return
        target = Path(chosen)
        fmt = target.suffix.lower().lstrip(".")
        if fmt not in _GLE_EXPORT_SUFFIXES:
            QMessageBox.critical(
                self, "Export Failed",
                f"Unsupported export format: .{fmt}\n"
                f"Choose one of: {', '.join(sorted(_GLE_EXPORT_SUFFIXES))}.",
            )
            return
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            result = gle_viewer.export_gle_file(
                self._gle_preview_path, target, format=fmt,
            )
        finally:
            QApplication.restoreOverrideCursor()
        if result.success:
            self.statusBar().showMessage(f"Exported to {target}", _STATUS_MS)
        else:
            msg = "\n".join(e.message for e in result.errors) or "Export failed."
            QMessageBox.critical(self, "Export Failed", msg)

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------
    def _rebuild_recent_menu(self) -> None:
        """Repopulate the Open Recent submenu from persisted recent files."""
        self.recent_menu.clear()
        recents = file_ops.get_recent_files(settings=self._settings)
        if not recents:
            empty = self.recent_menu.addAction("(none)")
            empty.setEnabled(False)
            return
        for path_str in recents:
            action = self.recent_menu.addAction(path_str)
            action.triggered.connect(
                lambda _checked=False, p=path_str: self._on_recent_chosen(p)
            )

    def _on_recent_chosen(self, path_str: str) -> None:
        """Open a recent-file entry (native ``.gle`` figures)."""
        if not self._confirm_discard_if_dirty("Open a file"):
            return
        self._dispatch_open(path_str)

    # ------------------------------------------------------------------
    # Edit actions
    # ------------------------------------------------------------------
    def _on_undo(self) -> None:
        self.undo_stack.undo()

    def _on_redo(self) -> None:
        self.undo_stack.redo()

    # ------------------------------------------------------------------
    # GLE-preview mode
    # ------------------------------------------------------------------
    def _enter_gle_preview_mode(self, gle_path: Path) -> None:
        """Compile ``gle_path`` and show it read-only (fallback preview mode).

        Compiles synchronously (~300ms) under a wait cursor. On success the
        rendered PNG replaces the preview; on failure the errors are listed and
        the mode is still entered (with whatever placeholder is showing) so the
        user can read the compile output.
        """
        # Clean up any prior preview's temp dirs before starting a new one.
        self._cleanup_gle_temp_dirs()
        self._gle_preview_path = gle_path
        self._set_document_widgets_enabled(False)
        self._update_gle_mode_actions()

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            result = gle_viewer.compile_gle_preview(gle_path)
        finally:
            QApplication.restoreOverrideCursor()

        # We own the mkdtemp'd output dir (output_dir omitted above), and
        # gle_viewer always reports it via work_dir -- even on failure paths --
        # so track it unconditionally to avoid leaking a directory on every
        # failed .gle preview (FIX 5).
        if result.work_dir is not None:
            self._gle_temp_dirs.append(Path(result.work_dir))

        if result.success and result.png_path is not None:
            self.error_panel.clear()
            self.preview_view.reset_view()
            self.preview_view.show_image(str(result.png_path))
        else:
            self.error_panel.set_errors(result.errors, result.raw_output)
            self.preview_view.show_placeholder(
                f"Could not compile {gle_path.name} — see Output panel"
            )

        self._update_window_title()
        self.statusBar().showMessage(
            f"Read-only preview of {gle_path.name} — "
            "File ▸ New to start an editable figure",
            0,
        )

    def _leave_gle_preview_mode(self) -> None:
        """Return to document editing mode, cleaning up preview temp dirs.

        A no-op when already in document mode. Re-enables the data/properties
        docks and File/Edit actions; the actual document flow (New/Open) is the
        caller's responsibility and its ``figure_replaced`` will re-render over
        the static preview image.
        """
        if not self.is_gle_preview_mode:
            return
        self._gle_preview_path = None
        self._cleanup_gle_temp_dirs()
        self._set_document_widgets_enabled(True)
        self._update_gle_mode_actions()
        self.statusBar().clearMessage()
        self._update_window_title()
        # Returning from the static .gle image to the (different) document view
        # is a genuine view change: frame the document's figure fresh (FIX 10).
        # The caller (New/Open) also resets, but leaving standalone must too.
        self.preview_view.reset_view()

    def _set_document_widgets_enabled(self, enabled: bool) -> None:
        """Enable/disable the editing docks for document vs GLE-preview mode."""
        self.data_panel.setEnabled(enabled)
        self.properties_tabs.setEnabled(enabled)

    def _update_gle_mode_actions(self) -> None:
        """Sync action enablement to the current mode.

        Save/Save As and Undo/Redo are meaningless for a read-only ``.gle``
        preview; Export stays enabled (it routes to ``export_gle_file``).
        """
        editable = not self.is_gle_preview_mode
        self.action_save.setEnabled(editable)
        self.action_save_as.setEnabled(editable)
        if editable:
            self.action_undo.setEnabled(self.undo_stack.can_undo)
            self.action_redo.setEnabled(self.undo_stack.can_redo)
        else:
            self.action_undo.setEnabled(False)
            self.action_redo.setEnabled(False)

    def _cleanup_gle_temp_dirs(self) -> None:
        """Remove all owned GLE-preview compile output directories."""
        for d in self._gle_temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._gle_temp_dirs = []

    def _confirm_discard_if_dirty(self, action_desc: str) -> bool:
        """Return True if it's safe to proceed (clean, or user chose Discard).

        The dirty check consults ``document.is_dirty`` regardless of mode.
        GLE-preview mode only relocates the *view* to a read-only ``.gle`` --
        the underlying document still holds the (possibly dirty) editable
        figure. Skipping the check in preview mode would let a second Open (or
        New/close) silently destroy unsaved edits.
        """
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
        self._cleanup_gle_temp_dirs()
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

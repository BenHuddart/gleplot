"""Export dialog for the gleplot GUI editor.

:class:`ExportDialog` lets the user pick a destination path, output format,
DPI (for raster formats), and whether to bundle the export as a
``.gleplot`` folder (script + data files alongside the compiled output),
then produces it through the same async compile service the live preview
uses (:mod:`gleplot.gui.compile_core`, :mod:`gleplot.gui.compile_service`).

Snapshot semantics
-------------------
Exporting **never** runs GLE generation against the live, in-editing
:class:`~gleplot.figure.Figure`: doing so would mutate any axis limits the
user left on "auto", coupling the exported geometry to incidental edit
order (see the same rationale in :mod:`gleplot.gui.preview`). Instead the
export button takes an immediate ``to_dict()`` snapshot of the document's
figure, rebuilds a throwaway working figure from it via ``Figure.from_dict``,
and exports *that* -- the live figure is left untouched.

Non-blocking compile (Track G3)
--------------------------------
Exporting used to call :meth:`~gleplot.figure.Figure.savefig`, which for any
compiled format shelled out via a blocking ``subprocess.run`` on the GUI
thread -- for a large or slow-to-render figure this froze the whole
application for the duration of the compile. The compile step now goes
through :class:`~gleplot.gui.compile_service.CompileProcessRunner` (the same
"thin QProcess adapter" the live preview uses): :meth:`_on_export_clicked`
writes the script/data files synchronously (plain file I/O, not a compile --
see :meth:`~gleplot.figure.Figure.savefig_gle`), launches the compile, and
returns immediately. The result arrives later via
:meth:`_on_compile_finished`, connected to the runner's ``finished`` signal;
the GUI event loop -- and this dialog's own Cancel button, now repurposed to
abort an in-flight compile -- stays responsive throughout.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gleplot.cairo_support import cairo_font_warning
from gleplot.compiler import GLECompileError, build_compile_args, find_gle
from gleplot.figure import Figure
from gleplot.gui.compile_core import CompileOutcome
from gleplot.gui.compile_service import CompileProcessRunner
from gleplot.gui.document import FigureDocument
from gleplot.gui.error_panel import format_gle_error

__all__ = ["ExportDialog", "run_export_dialog"]

#: Formats offered in the export dialog. 'gle' exports the script only (no
#: compile step); the rest are compiled through the async compile service.
FORMATS = ("pdf", "png", "eps", "svg", "jpg", "gle")

#: Formats for which the DPI control is meaningful (raster output).
_DPI_FORMATS = frozenset({"png", "jpg"})

_ORG = "gleplot"
_APP = "gleplot"
_KEY_LAST_DIR = "export_dialog/last_dir"


class ExportDialog(QDialog):
    """Modal dialog to export a :class:`FigureDocument`'s figure to disk.

    Parameters
    ----------
    document : FigureDocument
        Document whose ``figure`` is exported. If ``document.figure`` is
        ``None`` at construction time, the Export button is disabled (there
        is nothing to export yet).
    parent : QWidget, optional
        Parent widget.
    settings : QSettings, optional
        Settings store for the last-used export directory. Defaults to
        ``QSettings("gleplot", "gleplot")``.

    Attributes (post-export, for tests/callers)
    --------------------------------------------
    selected_path : Path or None
        The path last exported to (set right before the export attempt).
    selected_format : str
        Currently selected format, one of :data:`FORMATS`.
    selected_dpi : int
        Currently selected DPI value.
    folder_bundle : bool
        Whether "export as folder bundle" is checked.
    """

    def __init__(
        self,
        document: FigureDocument,
        parent: Optional[QWidget] = None,
        settings: Optional[QSettings] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Figure")
        self._document = document
        self._settings = settings or QSettings(_ORG, _APP)
        self._syncing = False

        self.selected_path: Optional[Path] = None
        self.selected_format: str = "pdf"
        self.selected_dpi: int = 300
        self.folder_bundle: bool = False

        # The in-flight compile job, or None between exports. See the
        # "Non-blocking compile" section of the module docstring.
        self._runner: Optional[CompileProcessRunner] = None

        self._build_ui()
        self._connect_signals()
        self._sync_dpi_enabled()

        if document.figure is None:
            self._export_button.setEnabled(False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit(self)
        self._browse_button = QPushButton("Browse…", self)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(self._browse_button)
        form.addRow("Destination:", path_row)

        self._format_combo = QComboBox(self)
        self._format_combo.addItems(list(FORMATS))
        self._format_combo.setCurrentText(self.selected_format)
        form.addRow("Format:", self._format_combo)

        self._dpi_spin = QSpinBox(self)
        self._dpi_spin.setRange(50, 1200)
        self._dpi_spin.setValue(self.selected_dpi)
        form.addRow("DPI:", self._dpi_spin)

        self._folder_check = QCheckBox(
            "Export as folder bundle (.gleplot folder with script and data)",
            self,
        )
        form.addRow(self._folder_check)

        layout.addLayout(form)

        self._error_box = QPlainTextEdit(self)
        self._error_box.setReadOnly(True)
        self._error_box.setVisible(False)
        self._error_box.setMaximumHeight(120)
        layout.addWidget(self._error_box)

        self._status_label = QLabel("", self)
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox(self)
        self._export_button = buttons.addButton(
            "Export",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self._cancel_button = buttons.addButton(
            QDialogButtonBox.StandardButton.Cancel,
        )
        layout.addWidget(buttons)

        self._export_button.clicked.connect(self._on_export_clicked)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

    def _connect_signals(self) -> None:
        self._browse_button.clicked.connect(self._on_browse)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        self._path_edit.textChanged.connect(self._on_path_text_changed)
        self._dpi_spin.valueChanged.connect(self._on_dpi_changed)
        self._folder_check.toggled.connect(self._on_folder_toggled)

    # ------------------------------------------------------------------
    # Suffix <-> format sync
    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        start_dir = self._settings.value(_KEY_LAST_DIR, "", type=str) or ""
        chosen, _ = QFileDialog.getSaveFileName(
            self,
            "Export Figure",
            start_dir,
            "All supported (*.pdf *.png *.eps *.svg *.jpg *.gle);;All files (*)",
        )
        if chosen:
            self._path_edit.setText(chosen)

    def _on_path_text_changed(self, text: str) -> None:
        if self._syncing:
            return
        suffix = Path(text).suffix.lower().lstrip(".")
        if suffix in FORMATS:
            self._syncing = True
            try:
                self._format_combo.setCurrentText(suffix)
                self.selected_format = suffix
            finally:
                self._syncing = False
        self._sync_dpi_enabled()

    def _on_format_changed(self, fmt: str) -> None:
        self.selected_format = fmt
        if not self._syncing:
            self._syncing = True
            try:
                current = self._path_edit.text()
                if current:
                    new_path = str(Path(current).with_suffix(f".{fmt}"))
                    self._path_edit.setText(new_path)
            finally:
                self._syncing = False
        self._sync_dpi_enabled()

    def _sync_dpi_enabled(self) -> None:
        self._dpi_spin.setEnabled(self.selected_format in _DPI_FORMATS)

    def _on_dpi_changed(self, value: int) -> None:
        self.selected_dpi = value

    def _on_folder_toggled(self, checked: bool) -> None:
        self.folder_bundle = checked

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _on_export_clicked(self) -> None:
        path_text = self._path_edit.text().strip()
        if not path_text:
            self._show_error("Please choose a destination path.")
            return

        path = Path(path_text)
        self.selected_path = path
        self.selected_format = self._format_combo.currentText()
        self.selected_dpi = self._dpi_spin.value()
        self.folder_bundle = self._folder_check.isChecked()

        fig = self._document.figure
        if fig is None:
            self._show_error("No figure to export.")
            return

        self._hide_error()
        self._status_label.setText("Exporting…")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self._begin_export(fig, path)
        except (OSError, RuntimeError, ValueError) as exc:
            QApplication.restoreOverrideCursor()
            self._show_error(str(exc))

    def _begin_export(self, fig, path: Path) -> None:
        """Write the script/data files, then launch (or skip) the compile.

        The script/data write is plain file I/O (:meth:`Figure.savefig_gle`)
        -- fast and synchronous, unlike the GLE compile itself, which never
        runs on this thread (see the module docstring). Any exception raised
        here (bad path, unwritable directory, ...) propagates to
        :meth:`_on_export_clicked`'s ``except`` clause.
        """
        # CRITICAL: never export from the live figure -- GLE generation
        # mutates unset axis limits in place. Snapshot + rebuild first.
        snap = fig.to_dict()
        work = Figure.from_dict(snap)
        # Reference-mode series carry paths relative to the project's
        # directory; the export may compile in a different directory, so
        # absolutize them on the throwaway copy.
        project_path = getattr(self._document, "project_path", None)
        if project_path:
            work.absolutize_file_references(Path(project_path).parent)

        # Write the .gle script (+ any data sidecars) via the same public API
        # Figure.savefig() itself uses -- savefig_gle() does not compile, so
        # this is ordinary (fast) file I/O and stays on the GUI thread.
        # folder_bundle handling (creating <stem>.gleplot/) is entirely
        # savefig_gle()'s existing, already-tested behaviour; we only choose
        # where the compiled output lands relative to the script it writes.
        gle_target = path.with_suffix(".gle")
        script_path = work.savefig_gle(str(gle_target), folder=self.folder_bundle)
        export_dir = script_path.parent

        if self.selected_format == "gle":
            self._finish_success(script_path)
            return

        # Writability preflight (SPEC §6.1: "export validates writability up
        # front and reports clearly") -- fail fast with a clear message
        # rather than launching a compile doomed to fail partway through.
        if not os.access(export_dir, os.W_OK):
            raise OSError(f"Destination directory is not writable: {export_dir}")

        gle_path = find_gle()
        if not gle_path:
            raise RuntimeError(
                "GLE executable not found. Install GLE, or export as 'gle' "
                "to save the script only."
            )

        # Cairo (Track G6): auto-detected from the same snapshot the script
        # was written from -- on for any figure using semi-transparency
        # (an alpha fill/span, or a raw rgba(...)/rgba255(...) colour), off
        # otherwise, so an ordinary opaque figure's export command line is
        # unaffected. Only 'svg' is unconditionally Cairo-backed regardless
        # of this flag (see build_compile_args' Notes); every other format
        # needs it to even accept a semi-transparent colour.
        cairo = work.requires_cairo()
        if cairo and self.selected_format != "svg":
            # GLE itself substitutes a Cairo-safe font when this flag is
            # set (see gleplot.cairo_support); SPEC's "no silent drops"
            # means that swap must never happen unreported. 'svg' is
            # excluded here because this dialog does not run any pre-emptive
            # font handling for it at all (unlike gleplot.gui.preview's
            # SVG-preview path) -- an SVG export with a PostScript font has
            # its own pre-existing failure mode independent of Track G6/
            # alpha, out of scope for this warning.
            warning = cairo_font_warning(work.style.font)
            if warning:
                warnings.warn(warning, UserWarning, stacklevel=2)

        output_name = script_path.with_suffix(f".{self.selected_format}").name
        output_path = export_dir / output_name
        args = build_compile_args(
            self.selected_format,
            output_name,
            script_path.name,
            dpi=self.selected_dpi,
            cairo=cairo,
        )

        self._export_button.setEnabled(False)
        self._cancel_button.setText("Cancel Export")

        runner = CompileProcessRunner(parent=self)
        runner.finished.connect(self._on_compile_finished)
        self._runner = runner
        runner.start(gle_path, export_dir, args, output_path)

    def _on_cancel_clicked(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            self._runner = None
            QApplication.restoreOverrideCursor()
            self._reset_buttons()
            self._status_label.setText("Export cancelled.")
            return
        self.reject()

    def _on_compile_finished(self, outcome: CompileOutcome) -> None:
        self._runner = None
        QApplication.restoreOverrideCursor()
        self._reset_buttons()

        if not outcome.ok:
            exc = GLECompileError(
                "GLE export failed",
                errors=outcome.errors,
                raw_output=outcome.raw_output,
            )
            self._show_error(self._format_compile_error(exc))
            return

        assert self.selected_path is not None  # set in _on_export_clicked
        self._finish_success(self.selected_path)

    def _finish_success(self, path: Path) -> None:
        self._settings.setValue(_KEY_LAST_DIR, str(path.parent))
        self._status_label.setText(f"Exported to {path}")
        self.accept()

    def _reset_buttons(self) -> None:
        self._export_button.setEnabled(True)
        self._cancel_button.setText("Cancel")

    @staticmethod
    def _format_compile_error(exc: GLECompileError) -> str:
        """Format a compile exception: a header line plus one canonical
        per-error line each (via the shared :func:`format_gle_error`, so the
        export dialog and the ErrorPanel render individual errors identically).
        """
        lines = [str(exc)]
        for err in getattr(exc, "errors", []) or []:
            lines.append(format_gle_error(err))
        return "\n".join(lines)

    def _show_error(self, message: str) -> None:
        self._status_label.setText("Export failed.")
        self._error_box.setPlainText(message)
        self._error_box.setVisible(True)

    def _hide_error(self) -> None:
        self._error_box.setVisible(False)
        self._error_box.clear()


def run_export_dialog(
    document: FigureDocument,
    parent: Optional[QWidget] = None,
) -> Optional[Path]:
    """Convenience: construct, show, and return the export dialog's result.

    Returns
    -------
    Path or None
        The exported path if the user completed an export, or ``None`` if
        the dialog was cancelled.
    """
    dialog = ExportDialog(document, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.selected_path
    return None

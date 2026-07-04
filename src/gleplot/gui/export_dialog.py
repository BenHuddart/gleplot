"""Export dialog for the gleplot GUI editor.

:class:`ExportDialog` lets the user pick a destination path, output format,
DPI (for raster formats), and whether to bundle the export as a
``.gleplot`` folder (script + data files alongside the compiled output),
then drives :meth:`~gleplot.figure.Figure.savefig` to produce it.

Snapshot semantics
-------------------
Exporting **never** runs GLE generation against the live, in-editing
:class:`~gleplot.figure.Figure`: doing so would mutate any axis limits the
user left on "auto", coupling the exported geometry to incidental edit
order (see the same rationale in :mod:`gleplot.gui.preview`). Instead the
export button takes an immediate ``to_dict()`` snapshot of the document's
figure, rebuilds a throwaway working figure from it via ``Figure.from_dict``,
and exports *that* -- the live figure is left untouched.
"""

from __future__ import annotations

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

from gleplot.compiler import GLECompileError
from gleplot.figure import Figure
from gleplot.gui.document import FigureDocument
from gleplot.gui.error_panel import format_gle_error

__all__ = ['ExportDialog', 'run_export_dialog']

#: Formats offered in the export dialog. 'gle' exports the script only (no
#: compile step), the rest go through GLECompiler via Figure.savefig.
FORMATS = ('pdf', 'png', 'eps', 'svg', 'jpg', 'gle')

#: Formats for which the DPI control is meaningful (raster output).
_DPI_FORMATS = frozenset({'png', 'jpg'})

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
        self.selected_format: str = 'pdf'
        self.selected_dpi: int = 300
        self.folder_bundle: bool = False

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
            "Export as folder bundle (.gleplot folder with script and data)", self,
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
            "Export", QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self._cancel_button = buttons.addButton(
            QDialogButtonBox.StandardButton.Cancel,
        )
        layout.addWidget(buttons)

        self._export_button.clicked.connect(self._on_export_clicked)
        self._cancel_button.clicked.connect(self.reject)

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
            self, "Export Figure", start_dir,
            "All supported (*.pdf *.png *.eps *.svg *.jpg *.gle);;All files (*)",
        )
        if chosen:
            self._path_edit.setText(chosen)

    def _on_path_text_changed(self, text: str) -> None:
        if self._syncing:
            return
        suffix = Path(text).suffix.lower().lstrip('.')
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
                    new_path = str(Path(current).with_suffix(f'.{fmt}'))
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
            # CRITICAL: never export from the live figure -- GLE generation
            # mutates unset axis limits in place. Snapshot + rebuild first.
            snap = fig.to_dict()
            work = Figure.from_dict(snap)
            # Reference-mode series carry paths relative to the project's
            # directory; the export may compile in a different directory,
            # so absolutize them on the throwaway copy.
            project_path = getattr(self._document, "project_path", None)
            if project_path:
                work.absolutize_file_references(Path(project_path).parent)
            work.savefig(
                str(path),
                format=self.selected_format,
                dpi=self.selected_dpi,
                folder=self.folder_bundle,
            )
        except GLECompileError as exc:
            self._show_error(self._format_compile_error(exc))
            return
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._settings.setValue(_KEY_LAST_DIR, str(path.parent))
        self._status_label.setText(f"Exported to {path}")
        self.accept()

    @staticmethod
    def _format_compile_error(exc: GLECompileError) -> str:
        """Format a compile exception: a header line plus one canonical
        per-error line each (via the shared :func:`format_gle_error`, so the
        export dialog and the ErrorPanel render individual errors identically).
        """
        lines = [str(exc)]
        for err in getattr(exc, 'errors', []) or []:
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

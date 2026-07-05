"""GLE Setup dialog for the gleplot GUI editor.

The desktop builds deliberately do **not** bundle GLE -- it is a runtime
prerequisite the user installs separately (see the release notes). This dialog
(**Tools ▸ GLE Setup…**) lets the user tell gleplot where their GLE executable
lives when auto-detection can't find it, or to pin a specific binary among
several installed versions.

Discovery model
---------------
The choice is stored as an *override* string:

* empty (``""``) -> **auto-detect**: gleplot resolves GLE via
  :func:`gleplot.compiler.autodetect_gle` (``GLE_PATH`` env -> ``PATH`` ->
  well-known install locations);
* a path -> that exact binary is used, taking precedence over everything else
  (:func:`gleplot.compiler.find_gle` consults the override first).

The dialog only *returns* the chosen override string (via :meth:`chosen_path`);
persisting it to ``QSettings`` and pushing it into
:func:`gleplot.compiler.set_gle_path_override` is the caller's (main window's)
responsibility, mirroring how :mod:`gleplot.gui.export_dialog` leaves settings
handling to the window.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gleplot.compiler import GLECompiler, autodetect_gle

__all__ = ["GleSetupDialog", "run_gle_setup_dialog"]

#: File dialog filter for picking the executable (platform-aware: Windows
#: binaries end in ``.exe``, POSIX ones have no suffix).
if sys.platform == "win32":
    _EXE_FILTER = "GLE executable (gle.exe);;Executables (*.exe);;All files (*)"
else:
    _EXE_FILTER = "GLE executable (gle);;All files (*)"


class GleSetupDialog(QDialog):
    """Modal dialog to view / change the configured GLE executable.

    Parameters
    ----------
    current_override : str, optional
        The currently-persisted override (``""``/``None`` == auto-detect).
    parent : QWidget, optional
        Dialog parent.
    """

    def __init__(
        self,
        current_override: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("GLE Setup")
        self.setModal(True)
        # Normalize None -> "" so the field/roundtrip logic is uniform.
        self._override = current_override or ""

        layout = QVBoxLayout(self)

        intro = QLabel(
            "gleplot uses GLE to render the live preview and to export "
            "compiled figures (PDF / PNG / EPS …). GLE is installed "
            "separately. Point gleplot at your GLE executable below, or leave "
            "this blank to auto-detect it.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Path row: line edit + Browse + Auto-detect.
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(self._override, self)
        self.path_edit.setPlaceholderText("(auto-detect)")
        self.path_edit.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.path_edit, 1)

        self.browse_button = QPushButton("Browse…", self)
        self.browse_button.clicked.connect(self._on_browse)
        path_row.addWidget(self.browse_button)

        self.detect_button = QPushButton("Auto-detect", self)
        self.detect_button.clicked.connect(self._on_autodetect)
        path_row.addWidget(self.detect_button)
        layout.addLayout(path_row)

        # Status line: validates the current selection (or the auto-detected
        # path when the field is blank) and reports the GLE version.
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_status()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    def chosen_path(self) -> str:
        """Return the override string to persist (``""`` == auto-detect)."""
        return self.path_edit.text().strip()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_path_changed(self, _text: str) -> None:
        self._refresh_status()

    def _on_browse(self) -> None:
        """Pick a GLE executable via a file dialog."""
        start_dir = ""
        current = self.path_edit.text().strip()
        if current:
            parent = Path(current).parent
            if parent.exists():
                start_dir = str(parent)
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Locate GLE executable", start_dir, _EXE_FILTER,
        )
        if chosen:
            self.path_edit.setText(chosen)

    def _on_autodetect(self) -> None:
        """Fill the field with the auto-detected GLE path (override ignored)."""
        detected = autodetect_gle()
        if detected:
            self.path_edit.setText(detected)
        else:
            # Leave the field as-is but report the miss in the status line.
            self._set_status(
                "Could not auto-detect GLE on this system. Install GLE or use "
                "Browse… to locate it.",
                ok=False,
            )

    # ------------------------------------------------------------------
    # Validation / status
    # ------------------------------------------------------------------
    def _refresh_status(self) -> None:
        """Validate the effective GLE path and update the status line.

        Blank field -> validate whatever :func:`autodetect_gle` finds (that is
        what gleplot will actually use). A path -> validate that path.
        Validation runs ``gle -info`` via :class:`GLECompiler` to confirm the
        binary is real and to surface its version.
        """
        text = self.path_edit.text().strip()
        effective = text or autodetect_gle()

        if not effective:
            self._set_status(
                "No GLE executable configured or detected — preview and "
                "compiled export will be unavailable.",
                ok=False,
            )
            return

        if not Path(effective).exists():
            self._set_status(f"Path does not exist: {effective}", ok=False)
            return

        version = self._probe_version(effective)
        prefix = "Using auto-detected GLE" if not text else "GLE"
        if version:
            self._set_status(f"{prefix}: {effective}\n{version}", ok=True)
        else:
            # File exists but didn't respond to -info: still usable, warn softly.
            self._set_status(
                f"{prefix}: {effective}\n(could not read version, but the file "
                "exists)",
                ok=True,
            )

    @staticmethod
    def _probe_version(path: str) -> Optional[str]:
        """Return GLE's ``-info`` string for ``path``, or None on failure."""
        try:
            info = GLECompiler(path).info()
        except Exception:  # noqa: BLE001 - validation must never raise
            return None
        version = info.get("version")
        if version:
            # GLE -info can be multi-line; keep the first non-empty line.
            first = next((ln for ln in version.splitlines() if ln.strip()), "")
            return first.strip() or None
        return None

    def _set_status(self, text: str, *, ok: bool) -> None:
        self.status_label.setText(text)
        # Green-ish for a valid selection, red-ish for a problem. Kept subtle so
        # it reads on both light and dark palettes.
        color = "#2e7d32" if ok else "#c62828"
        self.status_label.setStyleSheet(f"color: {color};")


def run_gle_setup_dialog(
    current_override: Optional[str] = None,
    parent: Optional[QWidget] = None,
) -> Optional[str]:
    """Run the GLE Setup dialog modally.

    Parameters
    ----------
    current_override : str, optional
        The currently-persisted override string.
    parent : QWidget, optional
        Dialog parent.

    Returns
    -------
    str or None
        The chosen override string (``""`` == auto-detect) if the user
        accepted, or ``None`` if they cancelled (leave the setting unchanged).
    """
    _ = QApplication.instance()  # dialogs require a running QApplication
    dialog = GleSetupDialog(current_override=current_override, parent=parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen_path()
    return None

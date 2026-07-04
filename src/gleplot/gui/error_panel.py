"""Compiler-error panel for the gleplot GUI editor.

Defines :class:`ErrorPanel`, a small widget that lists the structured
:class:`~gleplot.compiler.GLEError` entries produced by a failed GLE compile
and exposes the raw compiler output in a collapsible details area. It is a
pure view: it holds no document state and only emits
:data:`ErrorPanel.error_activated` when the user double-clicks an error that
carries a source line number (a future code view will use this to jump to the
offending line).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gleplot.compiler import GLEError


def format_gle_error(err: GLEError) -> str:
    """Render a single :class:`GLEError` as a one-line label.

    This is the *canonical* one-line rendering of a GLE error used across the
    GUI (the error list and the export dialog both call it, so their formatting
    stays consistent). Format:

    * ``"line L, col C: message"`` when both line and column are known;
    * ``"line L: message"`` when only the line is known;
    * ``"message"`` when neither is known.
    """
    location = ""
    if err.line is not None and err.column is not None:
        location = f"line {err.line}, col {err.column}: "
    elif err.line is not None:
        location = f"line {err.line}: "
    return f"{location}{err.message}"


class ErrorPanel(QWidget):
    """List GLE compile errors plus a collapsible raw-output view.

    Signals
    -------
    error_activated(int)
        Emitted with a 1-based source line number when the user
        double-clicks an error entry that has a line number. Errors without a
        line number do not emit.
    """

    error_activated = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._list = QListWidget(self)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._details_toggle = QPushButton("Show details", self)
        self._details_toggle.setCheckable(True)
        self._details_toggle.toggled.connect(self._on_details_toggled)

        self._details = QPlainTextEdit(self)
        self._details.setReadOnly(True)
        self._details.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)
        layout.addWidget(self._details_toggle)
        layout.addWidget(self._details)

    # ------------------------------------------------------------------
    # Slots / public API
    # ------------------------------------------------------------------
    def set_errors(self, errors: List[GLEError], raw: str = "") -> None:
        """Populate the panel with structured errors and raw output.

        Parameters
        ----------
        errors : list of GLEError
            Structured errors (as returned by
            :func:`gleplot.compiler.parse_gle_errors`). Each becomes one list
            row formatted as ``"line L, col C: message"`` (the location
            prefix is omitted where line/column are unknown).
        raw : str, optional
            Raw combined compiler output, shown in the collapsible details
            area.
        """
        self._list.clear()
        for err in errors:
            item = QListWidgetItem(self._format_error(err))
            # Stash the line number on the item so double-click can emit it
            # without re-parsing the label. None when the error has no line.
            item.setData(_LINE_ROLE, err.line)
            self._list.addItem(item)

        self._details.setPlainText(raw or "")

    def clear(self) -> None:
        """Remove all listed errors and clear the raw-output area."""
        self._list.clear()
        self._details.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _format_error(err: GLEError) -> str:
        """Render a single :class:`GLEError` as a one-line label.

        Thin wrapper over the module-level :func:`format_gle_error` (the shared
        canonical formatter) kept for internal call-site brevity.
        """
        return format_gle_error(err)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        line = item.data(_LINE_ROLE)
        if line is not None:
            self.error_activated.emit(int(line))

    def _on_details_toggled(self, checked: bool) -> None:
        self._details.setVisible(checked)
        self._details_toggle.setText("Hide details" if checked else "Show details")


# Qt.UserRole; imported lazily to keep the module import cheap when Qt enums
# aren't needed at import time. Defined at module scope so the item data role
# is stable across calls.
from PySide6.QtCore import Qt  # noqa: E402

_LINE_ROLE = int(Qt.ItemDataRole.UserRole)

"""Compiler-error panel for the gleplot GUI editor.

Defines :class:`ErrorPanel`, a small widget that lists the structured
:class:`~gleplot.compiler.GLEError` entries produced by a failed GLE compile
and exposes the raw compiler output in a collapsible details area. It is a
pure view: it holds no document state and only emits
:data:`ErrorPanel.error_activated` when the user double-clicks an error that
carries a source line number (a future code view will use this to jump to the
offending line).

It also renders **recognizer warnings** -- the ``list[str]`` recovery notes
produced by :func:`gleplot.parser.recognizer.parse_gle_figure` when opening a
``.gle`` file (prefixed ``structure:``/``metadata:``/``data:``/``legend:``/
``smooth:``/``layout:``; see that module's "Warnings taxonomy"). These are
informational, not compile failures, so they render in a visually distinct
section (a ``⚠``-prefixed list, styled differently from the error list) via
:meth:`set_warnings`/:meth:`clear_warnings` -- separate from, and unaffected
by, :meth:`set_errors`/:meth:`clear`. Purely for display: double-clicking a
warning does nothing (no line numbers are attached to recognizer warnings).
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

        # Recognizer warnings (informational; see module docstring), shown
        # above the error list in their own visually-distinct list widget.
        # Hidden whenever there are no warnings to show.
        self._warnings_list = QListWidget(self)
        self._warnings_list.setStyleSheet(
            "QListWidget { color: #8a6d3b; background-color: #fff8e6; }"
        )
        self._warnings_list.setVisible(False)

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
        layout.addWidget(self._warnings_list)
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

    def set_warnings(self, warnings: List[str]) -> None:
        """Populate the panel with recognizer warnings.

        Parameters
        ----------
        warnings : list of str
            Recovery notes as returned on
            ``RecognizedFigure.warnings``/``document.open_warnings``
            (prefixed ``structure:``/``metadata:``/``data:``/``legend:``/
            ``smooth:``/``layout:``). Each becomes one ``⚠``-prefixed list
            row. Independent of :meth:`set_errors`/:meth:`clear` -- calling
            this does not touch the error list, and calling those does not
            touch the warnings list.

        An empty list hides the warnings section entirely (same as
        :meth:`clear_warnings`).
        """
        self._warnings_list.clear()
        for warning in warnings:
            self._warnings_list.addItem(QListWidgetItem(f"⚠ {warning}"))
        self._warnings_list.setVisible(bool(warnings))

    def clear_warnings(self) -> None:
        """Remove all listed warnings and hide the warnings section."""
        self._warnings_list.clear()
        self._warnings_list.setVisible(False)

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

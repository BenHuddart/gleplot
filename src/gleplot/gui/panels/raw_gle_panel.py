"""Read-only viewer for preserved ("passthrough") raw GLE content.

When the recognizer (``gleplot.parser.recognizer``) cannot map a line of a
parsed ``.gle`` file onto the object model, it keeps the raw text instead of
dropping it, split into three buckets:

* :attr:`~gleplot.figure.Figure.passthrough_header` -- lines recovered from
  before the first graph block, re-emitted right after the standard preamble.
* :attr:`~gleplot.axes.Axes.passthrough` (one bucket per axes) -- lines
  recovered from inside that axes' graph block, re-emitted immediately before
  its ``end graph``.
* :attr:`~gleplot.figure.Figure.passthrough_trailer` -- lines recovered from
  after the last graph block, re-emitted at the very end of the script.

:class:`RawGlePanel` is a pure, read-only view onto these three buckets: it
never edits them (there is nothing to edit -- unrecognized text is opaque by
definition) and holds no state beyond what it displays. It exists so users
opening a hand-edited or exotic ``.gle`` file can see, at a glance, exactly
what content will be written back verbatim on save, without having to guess
from a diff after the fact.

The document is duck-typed (same convention as the other ``gui/panels``
modules) so this module never imports ``gleplot.gui.document``:

.. code-block:: python

    class FigureDocument(QObject):
        figure_changed = Signal()
        figure_replaced = Signal()

        @property
        def figure(self): ...  # Optional[gleplot.Figure]
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

#: Shown at the top of the panel when the current figure has no preserved
#: raw GLE content at all (all three buckets empty on every axes).
_EMPTY_STATE_TEXT = "No raw GLE content — everything in this file is editable."


class RawGlePanel(QWidget):
    """Read-only viewer of a figure's preserved passthrough GLE content.

    Parameters
    ----------
    document
        Duck-typed document exposing ``figure`` (Optional[gleplot.Figure])
        and ``figure_changed``/``figure_replaced`` signals.

    Layout
    ------
    A summary label ("N preserved lines will be written back verbatim on
    save") followed by one read-only :class:`QPlainTextEdit` section per
    non-empty bucket, in file order: ``Header``, then one ``Axes (r,c)``
    section per axes with a non-empty ``passthrough`` list (in
    ``figure.axes_list`` order), then ``Trailer``. When every bucket is
    empty, only the friendly empty-state message is shown.
    """

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._layout = QVBoxLayout(self)

        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        self._layout.addWidget(self.summary_label)

        self.empty_label = QLabel(_EMPTY_STATE_TEXT, self)
        self.empty_label.setWordWrap(True)
        self._layout.addWidget(self.empty_label)

        # Populated/cleared dynamically per refresh(): list of (QLabel
        # section-title, QPlainTextEdit) pairs currently attached to the
        # layout, so refresh() can tear them down before rebuilding.
        self._section_widgets: list[QWidget] = []

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self.refresh)
        self._document.figure_replaced.connect(self.refresh)

    # ------------------------------------------------------------------
    # Model -> UI
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Full refresh: rebuild every section from the current figure."""
        figure = self._document.figure

        # Tear down previously-built section widgets.
        for widget in self._section_widgets:
            self._layout.removeWidget(widget)
            widget.deleteLater()
        self._section_widgets = []

        if figure is None:
            self.summary_label.setText("")
            self.empty_label.setVisible(True)
            return

        buckets = _collect_buckets(figure)
        total_lines = sum(len(lines) for _title, lines in buckets)

        if total_lines == 0:
            self.summary_label.setText("")
            self.empty_label.setVisible(True)
            return

        self.empty_label.setVisible(False)
        noun = "line" if total_lines == 1 else "lines"
        self.summary_label.setText(
            f"{total_lines} preserved {noun} will be written back verbatim on save"
        )

        for title, lines in buckets:
            if not lines:
                continue
            title_label = QLabel(title, self)
            title_label.setStyleSheet("font-weight: bold;")
            self._layout.addWidget(title_label)
            self._section_widgets.append(title_label)

            text_view = QPlainTextEdit(self)
            text_view.setReadOnly(True)
            text_view.setPlainText("\n".join(lines))
            self._layout.addWidget(text_view)
            self._section_widgets.append(text_view)


def _collect_buckets(figure) -> list:
    """Return ``[(title, lines), ...]`` for every passthrough bucket, in
    file order: header, one per axes (in ``axes_list`` order), trailer.

    Axes sections are titled ``"Axes (r,c)"`` using the same 0-based
    ``(row, col)`` derivation as :class:`~gleplot.gui.panels.layout_panel.
    LayoutPanel` (``r = (idx-1)//cols``, ``c = (idx-1)%cols``, with
    ``cols`` taken from the grid-wide max over every axes' ``position``).
    """
    buckets = []

    header = list(getattr(figure, "passthrough_header", []) or [])
    buckets.append(("Header", header))

    axes_list = list(getattr(figure, "axes_list", []) or [])
    cols = 1
    if axes_list:
        cols = max((ax.position[1] for ax in axes_list if ax.position), default=1) or 1

    for ax in axes_list:
        lines = list(getattr(ax, "passthrough", []) or [])
        if ax.position:
            idx = ax.position[2]
            r = (idx - 1) // cols
            c = (idx - 1) % cols
            title = f"Axes ({r},{c})"
        else:
            title = "Axes"
        buckets.append((title, lines))

    trailer = list(getattr(figure, "passthrough_trailer", []) or [])
    buckets.append(("Trailer", trailer))

    return buckets

"""Figure-level property panel.

:class:`FigurePanel` binds a small set of controls (figure size in inches
and DPI) to the ``figsize``/``dpi`` attributes of the current
``gleplot.Figure`` held by a document object.

The document is duck-typed (see the module docstring convention used across
``gui/panels``) so this module never imports ``gleplot.gui.document``:

.. code-block:: python

    class FigureDocument(QObject):
        figure_changed = Signal()
        figure_replaced = Signal()

        @property
        def figure(self): ...  # Optional[gleplot.Figure]

        def notify_changed(self): ...
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)


class FigurePanel(QWidget):
    """Property panel for figure-level attributes (size, DPI).

    Parameters
    ----------
    document
        Object exposing ``figure`` (Optional[gleplot Figure]),
        ``figure_changed``/``figure_replaced`` signals, and
        ``notify_changed()``.
    """

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        # Guards against feedback loops: True while this panel is writing to
        # the model or refreshing its own widgets from the model, so that
        # editingFinished handlers triggered by programmatic changes don't
        # write back into the model / call notify_changed redundantly.
        self._updating = False

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(2.0, 30.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setDecimals(2)
        self.width_spin.setSuffix(" in")

        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(2.0, 30.0)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.setDecimals(2)
        self.height_spin.setSuffix(" in")

        self.dpi_spin = QSpinBox(self)
        self.dpi_spin.setRange(50, 600)
        self.dpi_spin.setSingleStep(10)

        layout.addRow("Width", self.width_spin)
        layout.addRow("Height", self.height_spin)
        layout.addRow("DPI", self.dpi_spin)

        self.setEnabled(False)

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self.refresh)
        self._document.figure_replaced.connect(self.refresh)

        self.width_spin.editingFinished.connect(self._on_size_edited)
        self.height_spin.editingFinished.connect(self._on_size_edited)
        self.dpi_spin.editingFinished.connect(self._on_dpi_edited)

    # ------------------------------------------------------------------
    # Model -> UI
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Repopulate widgets from the current figure (full refresh)."""
        figure = self._document.figure
        self.setEnabled(figure is not None)
        if figure is None:
            return

        self._updating = True
        try:
            width, height = figure.figsize
            self.width_spin.setValue(float(width))
            self.height_spin.setValue(float(height))
            self.dpi_spin.setValue(int(figure.dpi))
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # UI -> Model
    # ------------------------------------------------------------------
    def _on_size_edited(self) -> None:
        if self._updating:
            return
        figure = self._document.figure
        if figure is None:
            return

        self._updating = True
        try:
            figure.figsize = (self.width_spin.value(), self.height_spin.value())
        finally:
            self._updating = False
        self._document.notify_changed()

    def _on_dpi_edited(self) -> None:
        if self._updating:
            return
        figure = self._document.figure
        if figure is None:
            return

        self._updating = True
        try:
            figure.dpi = self.dpi_spin.value()
        finally:
            self._updating = False
        self._document.notify_changed()

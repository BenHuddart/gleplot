"""Shared document model for the gleplot GUI editor.

This module defines :class:`FigureDocument`, the single source of truth that
all GUI components (data manager, property panels, live preview) observe and
mutate. It wraps a gleplot :class:`~gleplot.figure.Figure` and turns edits to
that figure into Qt signals so views can react without polling.

The document deliberately owns *no* rendering or persistence logic -- it only
holds the current :class:`Figure`, tracks a dirty flag, and broadcasts two
kinds of change:

``figure_changed``
    The *state* of the current figure was mutated in place (a series added,
    an axis label changed, a limit set, ...). Panels that mutate the figure
    must call :meth:`notify_changed` afterwards so observers (notably the
    preview engine) refresh.

``figure_replaced``
    A brand-new :class:`Figure` object was installed via :meth:`set_figure`
    (File ▸ New / Open). Observers should re-read everything and reset any
    view state (e.g. fit-to-window in the preview) rather than assume the
    previous figure's geometry.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from gleplot.figure import Figure


class FigureDocument(QObject):
    """Observable wrapper around a gleplot :class:`Figure`.

    Parameters
    ----------
    figure : Figure, optional
        Initial figure to wrap. May be ``None`` (the empty/no-document
        state), in which case a figure can be installed later with
        :meth:`set_figure` or :meth:`new_figure`.

    Signals
    -------
    figure_changed()
        Emitted after any in-place mutation of the current figure's state,
        via :meth:`notify_changed`.
    figure_replaced()
        Emitted when a *new* :class:`Figure` object is installed via
        :meth:`set_figure` (including :meth:`new_figure`).
    dirty_changed(bool)
        Emitted whenever the dirty flag transitions. ``True`` means there are
        unsaved changes; ``False`` means the document is clean.
    """

    figure_changed = Signal()
    figure_replaced = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, figure: Optional[Figure] = None) -> None:
        super().__init__()
        self._figure: Optional[Figure] = figure
        self._dirty: bool = False

    # ------------------------------------------------------------------
    # Figure access
    # ------------------------------------------------------------------
    @property
    def figure(self) -> Optional[Figure]:
        """The currently wrapped :class:`Figure`, or ``None``."""
        return self._figure

    def set_figure(self, fig: Optional[Figure]) -> None:
        """Install a new figure object and emit :data:`figure_replaced`.

        Installing a document is treated as a clean starting point: the dirty
        flag is reset to ``False`` (emitting :data:`dirty_changed` if it was
        previously dirty). Use this for File ▸ New and File ▸ Open. Panels
        that mutate the *existing* figure should call :meth:`notify_changed`
        instead.
        """
        self._figure = fig
        self.figure_replaced.emit()
        self._set_dirty(False)

    def new_figure(self) -> Figure:
        """Create a fresh single-subplot figure, install it, and return it.

        Convenience for File ▸ New: builds a gleplot :class:`Figure` with one
        ``add_subplot(1, 1, 1)`` axes, installs it via :meth:`set_figure`
        (which emits :data:`figure_replaced` and clears the dirty flag), and
        returns the new figure for the caller to populate.
        """
        fig = Figure()
        fig.add_subplot(1, 1, 1)
        self.set_figure(fig)
        return fig

    def notify_changed(self) -> None:
        """Announce an in-place mutation of the current figure.

        Panels call this after mutating :attr:`figure` (adding a series,
        editing a label, changing limits, ...). Emits :data:`figure_changed`
        and marks the document dirty.
        """
        self.figure_changed.emit()
        self._set_dirty(True)

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        """Whether the document has unsaved changes."""
        return self._dirty

    def mark_clean(self) -> None:
        """Clear the dirty flag (e.g. after a successful save)."""
        self._set_dirty(False)

    def _set_dirty(self, value: bool) -> None:
        """Set the dirty flag, emitting :data:`dirty_changed` on a change."""
        if value != self._dirty:
            self._dirty = value
            self.dirty_changed.emit(value)

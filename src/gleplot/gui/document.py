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

from pathlib import Path
from typing import Optional, Union

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
    project_path_changed(str)
        Emitted whenever :attr:`project_path` changes, e.g. after File ▸ Open
        or the first File ▸ Save As of a new document. The argument is the
        string form of the new path (empty string when cleared to ``None``).
    """

    figure_changed = Signal()
    figure_replaced = Signal()
    dirty_changed = Signal(bool)
    project_path_changed = Signal(str)

    def __init__(self, figure: Optional[Figure] = None) -> None:
        super().__init__()
        self._figure: Optional[Figure] = figure
        self._dirty: bool = False
        self._project_path: Optional[Path] = None
        #: Recovery warnings from the most recent File ▸ Open (see
        #: :func:`gleplot.parser.recognizer.parse_gle_figure`), one string per
        #: warning, each prefixed by its category (``structure:``,
        #: ``metadata:``, ``data:``, ``legend:``, ``smooth:``, ``layout:``).
        #: Plain attribute -- no signal is emitted when it changes.
        #:
        #: Ordering contract with :mod:`gleplot.gui.file_ops`: :meth:`set_figure`
        #: unconditionally RESETS this to ``[]`` (a freshly installed figure,
        #: whether from ``new_figure()`` or a not-yet-classified ``Open``, starts
        #: with no open-warnings). ``file_ops.open_project`` then calls
        #: ``set_figure`` first and assigns the recognizer's ``warnings`` list
        #: to this attribute AFTER, so the reset doesn't wipe the real warnings.
        #: A successful save (``file_ops.save_project_current`` /
        #: ``save_project_as``) clears it back to ``[]``, since a save resolves
        #: the session's open-time warnings (the just-written ``.gle`` is exactly
        #: what's in memory, warnings and all, so there is nothing left to warn
        #: about until the next Open). The main window reads this list after
        #: ``figure_replaced`` fires to decide whether to show a recovery-warnings
        #: banner/dialog.
        self.open_warnings: list[str] = []

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
        previously dirty), the project path is cleared to ``None`` (emitting
        :data:`project_path_changed`), and :attr:`open_warnings` is reset to
        ``[]``. Use this for File ▸ New and File ▸ Open. Panels that mutate the
        *existing* figure should call :meth:`notify_changed` instead.

        Clearing the project path here is what makes File ▸ New after editing a
        saved project route the next Save to Save-As instead of silently
        overwriting the old ``.gle``. Loaders that install a figure and then
        assign a real path and warnings (e.g.
        :func:`gleplot.gui.file_ops.open_project`) must call ``set_figure``
        *before* setting ``project_path`` / ``open_warnings`` -- the order
        already used -- so the freshly loaded path and recognizer warnings
        survive the reset performed here.
        """
        self._figure = fig
        self.project_path = None
        self.open_warnings = []
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
    # Project path tracking
    # ------------------------------------------------------------------
    @property
    def project_path(self) -> Optional[Path]:
        """Filesystem path of the ``.gle`` file this document was loaded
        from or last saved to, or ``None`` for a not-yet-saved document."""
        return self._project_path

    @project_path.setter
    def project_path(self, value: Optional[Union[str, Path]]) -> None:
        new_path = Path(value) if value is not None else None
        if new_path != self._project_path:
            self._project_path = new_path
            self.project_path_changed.emit(str(new_path) if new_path else "")

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

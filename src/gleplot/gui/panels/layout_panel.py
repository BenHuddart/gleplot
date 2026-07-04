"""Subplot grid / layout panel with axes-slot selection.

:class:`LayoutPanel` lets the user inspect and edit the subplot grid of the
current figure: view/change the (rows, cols) grid, pick which grid slot is
"current" (selecting an existing axes or adding a new one to an empty slot),
toggle ``sharex``/``sharey``, and edit ``subplots_adjust`` margins/spacing.

The document is duck-typed (see the module docstring convention used across
``gui/panels``, e.g. ``figure_panel.py``) so this module never imports
``gleplot.gui.document``:

.. code-block:: python

    class FigureDocument(QObject):
        figure_changed = Signal()
        figure_replaced = Signal()

        @property
        def figure(self): ...  # Optional[gleplot.Figure]

        def notify_changed(self): ...

Notes on the underlying object model (see ``gleplot/figure.py`` and
``gleplot/axes.py``):

- Each :class:`~gleplot.axes.Axes` carries a ``position`` tuple
  ``(rows, cols, idx)`` where ``idx`` is the 1-based, row-major slot index
  (matplotlib/GLE ``add_subplot`` convention). The grid dimensions used by
  the multi-subplot GLE writer path are derived as
  ``max(ax.position[0] for ax in axes_list)`` /
  ``max(ax.position[1] ...)`` -- *not* stored anywhere else on the figure.
  This means every axes' ``position`` must agree on ``(rows, cols)`` for a
  consistent layout; :meth:`LayoutPanel._apply_grid` rewrites the
  ``(rows, cols)`` components of every axes' ``position`` tuple whenever the
  grid size changes, otherwise a stale axes could report the old grid size and
  desync the writer's row/col arithmetic. Crucially it preserves each axes'
  geometric ``(row, col)`` *cell* rather than its flat ``idx``: since ``idx``
  is row-major over the column count, keeping ``idx`` verbatim across a reshape
  that changes the column count (e.g. 2x3 -> 3x2) would silently relocate a
  populated axes to a different cell. Instead ``_apply_grid`` decodes each
  axes' ``(row, col)`` from its stored dims and recomputes
  ``idx = row * new_cols + col + 1``. An axes whose ``(row, col)`` falls
  outside the new grid follows the same refuse-if-non-empty / drop-if-empty
  rules used when shrinking.
- ``Figure.add_subplot(rows, cols, idx)`` also derives shared-axes tick/label
  visibility flags (``_show_xlabel`` etc.) from ``figure.sharex``/``sharey``
  at *call time*. Those flags are re-derived by
  :meth:`Figure._generate_gle_with_files`'s ``sharex``/``sharey`` branches
  only for axis-limit synchronization, not for the visibility flags
  themselves -- so toggling ``sharex``/``sharey`` after axes already exist
  does not retroactively fix up ``_show_xlabel`` etc. on old axes. This
  panel recomputes those flags for every existing axes by calling the core
  single source of truth (``Figure._apply_shared_axes_flags``, which
  ``add_subplot`` also uses) whenever the grid is (re)applied or sharing is
  toggled, so the visible effect matches what a fresh ``add_subplot`` call
  would have produced.
- ``Figure._subplot_adjust`` is a sparse dict: only explicitly-set keys
  (``left``/``right``/``bottom``/``top``/``wspace``/``hspace``) are present;
  an unset key falls back to the writer's built-in default margin/spacing.
  This panel mirrors that sparseness with per-field checkboxes.
- An axes is considered "empty" (safe to drop when shrinking the grid) when
  it has no series (``Axes.has_plots()``) *and* no text annotations
  (``Axes.texts``); ``has_plots()`` alone does not check ``texts``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

#: subplots_adjust keys, in the order the spacing group lays out its fields.
_ADJUST_KEYS = ("left", "right", "bottom", "top", "wspace", "hspace")


def _axes_is_empty(ax) -> bool:
    """An axes is safe to drop when shrinking the grid: no series, no text."""
    return not ax.has_plots() and not ax.texts


class LayoutPanel(QWidget):
    """Panel for the subplot grid, axes-slot selection, sharing and spacing.

    Parameters
    ----------
    document
        Duck-typed document exposing ``figure``, ``figure_changed``/
        ``figure_replaced`` signals, and ``notify_changed()``.

    Signals
    -------
    axes_selected(object)
        Emitted with the :class:`~gleplot.axes.Axes` the user selected in the
        slot list (an existing axes picked directly, or a newly-created axes
        after "Add axes here"). Selecting an existing axes is a *view* change
        only -- it does not call ``document.notify_changed()``.
    """

    axes_selected = Signal(object)

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._updating = False
        #: (rows, cols, idx) for each slot in the currently-listed grid, in
        #: the same order as ``self.slot_list`` rows.
        self._slots: list[tuple[int, int, int]] = []
        self._selected_slot: Optional[tuple[int, int, int]] = None
        #: Grid size as last displayed/applied by this panel. The figure
        #: itself has no explicit grid-size field -- it is only ever implied
        #: by the max over existing axes' positions (see
        #: ``_current_grid_dims``) -- so when the figure has zero axes there
        #: is nothing to derive a grown grid from after applying it. This
        #: tracks the panel's own notion of "current grid" so growing an
        #: all-empty grid (e.g. 1x1 -> 2x2 with no axes yet) is not silently
        #: reset back to 1x1 on the next refresh.
        self._displayed_grid: tuple[int, int] = (1, 1)

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        grid_group = QGroupBox("Grid", self)
        grid_form = QFormLayout(grid_group)
        self.rows_spin = QSpinBox(grid_group)
        self.rows_spin.setRange(1, 6)
        self.cols_spin = QSpinBox(grid_group)
        self.cols_spin.setRange(1, 6)
        grid_form.addRow("Rows", self.rows_spin)
        grid_form.addRow("Cols", self.cols_spin)

        self.apply_grid_button = QPushButton("Apply grid", grid_group)
        grid_form.addRow(self.apply_grid_button)

        self.status_label = QLabel("", grid_group)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: red;")
        grid_form.addRow(self.status_label)
        outer.addWidget(grid_group)

        slots_group = QGroupBox("Axes slots", self)
        slots_layout = QVBoxLayout(slots_group)
        self.slot_list = QListWidget(slots_group)
        slots_layout.addWidget(self.slot_list)
        self.add_axes_button = QPushButton("Add axes here", slots_group)
        self.add_axes_button.setEnabled(False)
        slots_layout.addWidget(self.add_axes_button)
        outer.addWidget(slots_group)

        share_group = QGroupBox("Shared axes", self)
        share_form = QFormLayout(share_group)
        self.sharex_check = QCheckBox(share_group)
        self.sharey_check = QCheckBox(share_group)
        share_form.addRow("Share X", self.sharex_check)
        share_form.addRow("Share Y", self.sharey_check)
        outer.addWidget(share_group)

        spacing_group = QGroupBox("Spacing", self)
        spacing_form = QFormLayout(spacing_group)
        self._adjust_checks: dict[str, QCheckBox] = {}
        self._adjust_spins: dict[str, QDoubleSpinBox] = {}
        for key in _ADJUST_KEYS:
            row = QWidget(spacing_group)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            check = QCheckBox(spacing_group)
            spin = QDoubleSpinBox(spacing_group)
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.01)
            spin.setDecimals(2)
            spin.setEnabled(False)
            row_layout.addWidget(check)
            row_layout.addWidget(spin)
            spacing_form.addRow(key, row)
            self._adjust_checks[key] = check
            self._adjust_spins[key] = spin
        outer.addWidget(spacing_group)

        outer.addStretch(1)
        self.setEnabled(False)

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self._on_figure_changed)
        self._document.figure_replaced.connect(self._on_figure_replaced)

        self.apply_grid_button.clicked.connect(self._on_apply_grid_clicked)
        self.slot_list.currentRowChanged.connect(self._on_slot_selected)
        self.add_axes_button.clicked.connect(self._on_add_axes_clicked)

        self.sharex_check.toggled.connect(self._on_sharex_toggled)
        self.sharey_check.toggled.connect(self._on_sharey_toggled)

        for key in _ADJUST_KEYS:
            self._adjust_checks[key].toggled.connect(
                lambda checked, k=key: self._on_adjust_check_toggled(k, checked)
            )
            self._adjust_spins[key].editingFinished.connect(
                lambda k=key: self._on_adjust_value_edited(k)
            )

    # ------------------------------------------------------------------
    # Model -> UI
    # ------------------------------------------------------------------
    def _on_figure_changed(self) -> None:
        """Cheap re-sync guarded against feedback loops triggered by our own
        writes (all of which route through ``_updating``)."""
        if self._updating:
            return
        self.refresh()

    def _on_figure_replaced(self) -> None:
        """Handle a brand-new figure being installed (New/Open/undo/redo).

        ``refresh`` rebuilds the slot list, but selecting the current row via
        ``setCurrentRow`` inside ``refresh`` runs under the ``_updating`` guard,
        so ``_on_slot_selected`` (and therefore ``axes_selected``) does *not*
        fire during it. Worse, when the new figure happens to make the current
        slot index the *same* as before, ``setCurrentRow`` is a no-op and would
        never re-emit even outside the guard.

        Downstream panels (AxesPanel/SeriesPanel) drop their axes override on
        ``figure_replaced`` and need a fresh ``axes_selected`` to re-target onto
        the corresponding slot of the *new* figure. So after refreshing we
        explicitly re-emit ``axes_selected`` for the newly-resolved current
        Axes. A re-entrancy guard prevents a duplicate emission if a genuine
        row change during refresh already emitted (it currently cannot, but the
        guard keeps this correct if that ever changes).
        """
        self.refresh()
        figure = self._document.figure
        if figure is None:
            return
        current = figure._current_axes
        if current is None and figure.axes_list:
            current = figure.axes_list[-1]
        if current is not None:
            figure._current_axes = current
            self.axes_selected.emit(current)

    def refresh(self) -> None:
        """Full rebuild from the current figure's state."""
        figure = self._document.figure
        self.setEnabled(figure is not None)
        if figure is None:
            return

        self._updating = True
        try:
            self.status_label.setText("")

            derived_rows, derived_cols = self._current_grid_dims(figure)
            disp_rows, disp_cols = self._displayed_grid
            # An all-empty figure derives to 1x1 regardless of what grid size
            # was last applied through this panel; never shrink the
            # panel-tracked size just because refresh() ran (see
            # _displayed_grid docstring in __init__).
            rows = max(derived_rows, disp_rows)
            cols = max(derived_cols, disp_cols)
            self._displayed_grid = (rows, cols)
            self.rows_spin.setValue(rows)
            self.cols_spin.setValue(cols)

            self._rebuild_slot_list(figure, rows, cols)

            self.sharex_check.setChecked(bool(figure.sharex))
            self.sharey_check.setChecked(bool(figure.sharey))

            for key in _ADJUST_KEYS:
                value = figure._subplot_adjust.get(key)
                check = self._adjust_checks[key]
                spin = self._adjust_spins[key]
                if value is None:
                    check.setChecked(False)
                    spin.setEnabled(False)
                else:
                    check.setChecked(True)
                    spin.setEnabled(True)
                    spin.setValue(value)
        finally:
            self._updating = False

    @staticmethod
    def _current_grid_dims(figure) -> tuple[int, int]:
        """Derive (rows, cols) from the max over axes positions.

        An empty figure (no axes) defaults to 1x1.
        """
        if not figure.axes_list:
            return 1, 1
        rows = max(ax.position[0] for ax in figure.axes_list)
        cols = max(ax.position[1] for ax in figure.axes_list)
        return rows, cols

    def _rebuild_slot_list(self, figure, rows: int, cols: int) -> None:
        by_idx = {ax.position[2]: ax for ax in figure.axes_list}
        current = figure._current_axes

        self._slots = []
        self.slot_list.clear()
        selected_row = -1
        for idx in range(1, rows * cols + 1):
            r = (idx - 1) // cols
            c = (idx - 1) % cols
            self._slots.append((rows, cols, idx))
            ax = by_idx.get(idx)
            if ax is not None:
                suffix = " (current)" if ax is current else ""
                label = f"({r},{c}) -- idx {idx}{suffix}"
            else:
                label = f"({r},{c}) -- idx {idx} (empty)"
            self.slot_list.addItem(label)
            if ax is not None and ax is current:
                selected_row = idx - 1

        if selected_row >= 0:
            self.slot_list.setCurrentRow(selected_row)
            self._selected_slot = self._slots[selected_row]
            self.add_axes_button.setEnabled(False)
        else:
            self.slot_list.setCurrentRow(-1)
            self._selected_slot = None
            self.add_axes_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Grid apply
    # ------------------------------------------------------------------
    def _on_apply_grid_clicked(self) -> None:
        figure = self._document.figure
        if figure is None:
            return

        new_rows = self.rows_spin.value()
        new_cols = self.cols_spin.value()
        self._apply_grid(figure, new_rows, new_cols)

    def _apply_grid(self, figure, new_rows: int, new_cols: int) -> None:
        old_rows, old_cols = self._displayed_grid
        if new_rows == old_rows and new_cols == old_cols:
            self.status_label.setText("")
            return

        # Preserve each axes' geometric (row, col) cell across the reshape,
        # deriving a *new* idx for the new column count -- rather than keeping
        # the flat idx verbatim (which silently relocates a populated axes to a
        # different cell when the column count changes, e.g. 2x3 -> 3x2). The
        # (row, col) is decoded from the axes' own stored grid dims (its
        # ``position`` records the grid it was registered under), so a mixed or
        # stale grid still decodes correctly.
        def _new_idx(ax) -> Optional[int]:
            ax_rows, ax_cols, idx = ax.position
            row = (idx - 1) // ax_cols
            col = (idx - 1) % ax_cols
            if row >= new_rows or col >= new_cols:
                return None  # (row, col) falls outside the new grid
            return row * new_cols + col + 1

        # An axes whose (row, col) no longer fits and still holds content
        # cannot be relocated without losing data -> refuse (same rule as a
        # shrink). Empty out-of-bounds axes are dropped.
        orphaned_nonempty = [
            ax for ax in figure.axes_list
            if _new_idx(ax) is None and not _axes_is_empty(ax)
        ]
        if orphaned_nonempty:
            positions = ", ".join(str(ax.position) for ax in orphaned_nonempty)
            self.status_label.setText(
                "Cannot reshape grid: axes with data would fall outside the "
                f"new grid (positions: {positions}). Remove their content first."
            )
            return

        self.status_label.setText("")

        # Drop out-of-bounds axes (guaranteed empty by the check above) and
        # re-register the rest at their preserved (row, col) under the new dims.
        kept = [ax for ax in figure.axes_list if _new_idx(ax) is not None]
        dropped = [ax for ax in figure.axes_list if _new_idx(ax) is None]
        figure.axes_list = kept
        if figure._current_axes in dropped:
            figure._current_axes = kept[-1] if kept else None

        for ax in figure.axes_list:
            ax.position = (new_rows, new_cols, _new_idx(ax))
            # Re-derive shared-axes visibility flags via the core single source
            # of truth (Figure._apply_shared_axes_flags reads ax.position and
            # figure.sharex/sharey), matching a fresh add_subplot.
            figure._apply_shared_axes_flags(ax)

        self._displayed_grid = (new_rows, new_cols)
        self._document.notify_changed()
        self.refresh()

    # ------------------------------------------------------------------
    # Slot selection
    # ------------------------------------------------------------------
    def _on_slot_selected(self, row: int) -> None:
        if self._updating:
            return
        if row < 0 or row >= len(self._slots):
            self._selected_slot = None
            self.add_axes_button.setEnabled(False)
            return

        figure = self._document.figure
        if figure is None:
            return

        self._selected_slot = self._slots[row]
        rows, cols, idx = self._selected_slot
        by_idx = {ax.position[2]: ax for ax in figure.axes_list}
        ax = by_idx.get(idx)

        if ax is not None:
            self.add_axes_button.setEnabled(False)
            # Selection is a VIEW change only -- do not notify_changed().
            figure._current_axes = ax
            self.axes_selected.emit(ax)
        else:
            self.add_axes_button.setEnabled(True)

    def _on_add_axes_clicked(self) -> None:
        if self._selected_slot is None:
            return
        figure = self._document.figure
        if figure is None:
            return

        rows, cols, idx = self._selected_slot
        ax = figure.add_subplot(rows, cols, idx)
        self._document.notify_changed()
        self.refresh()
        self.axes_selected.emit(ax)

    # ------------------------------------------------------------------
    # Shared axes (sharex/sharey)
    # ------------------------------------------------------------------
    def _on_sharex_toggled(self, checked: bool) -> None:
        self._write_share("sharex", checked)

    def _on_sharey_toggled(self, checked: bool) -> None:
        self._write_share("sharey", checked)

    def _write_share(self, attr: str, value: bool) -> None:
        if self._updating:
            return
        figure = self._document.figure
        if figure is None:
            return

        setattr(figure, attr, value)

        # Re-derive every axes' shared visibility flags to reflect the new
        # sharing setting, via the core single source of truth.
        for ax in figure.axes_list:
            figure._apply_shared_axes_flags(ax)

        self._document.notify_changed()

    # ------------------------------------------------------------------
    # Spacing (subplots_adjust)
    # ------------------------------------------------------------------
    def _on_adjust_check_toggled(self, key: str, checked: bool) -> None:
        if self._updating:
            return
        figure = self._document.figure
        if figure is None:
            return

        spin = self._adjust_spins[key]
        spin.setEnabled(checked)

        if checked:
            figure._subplot_adjust[key] = spin.value()
        else:
            figure._subplot_adjust.pop(key, None)

        self._document.notify_changed()

    def _on_adjust_value_edited(self, key: str) -> None:
        if self._updating:
            return
        if not self._adjust_checks[key].isChecked():
            return
        figure = self._document.figure
        if figure is None:
            return

        figure._subplot_adjust[key] = self._adjust_spins[key].value()
        self._document.notify_changed()

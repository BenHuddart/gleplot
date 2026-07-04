"""Text-annotation property panel.

:class:`TextsPanel` shows the list of free-form text annotations
(``ax.texts``) on the current axes and an editor for whichever annotation is
selected. It is the property-panel half of Track F2; a parallel track
(``gleplot/gui/annotations.py``) builds an on-canvas drag overlay for the
same data. Integration (selection sync between the two) happens in a later
step -- see the "Integration notes" in this module's tests / the track
report for how ``select_text``/``current_index``/``text_selected`` are meant
to be wired to the overlay.

Stored-representation conventions mirrored here (see ``gleplot/axes.py``,
``Axes.text``, ~line 719 at the time of writing):

- Each entry in ``ax.texts`` is a plain dict with keys ``x``, ``y``, ``text``,
  ``color``, ``fontsize``, ``ha``, ``va``, ``box_color``, all in **data
  coordinates** for x/y.
- ``color``: GLE color name string, or ``None`` meaning "inherit default"
  (rendered/written as ``'BLACK'`` -- see ``Axes.text`` and
  ``GLEWriter.add_text``). This panel always writes an explicit GLE color
  name (never re-introduces ``None``), matching how the color button works
  in ``series_panel.py``: once a color is picked, it's stored explicitly.
- ``fontsize``: ``float`` points, or ``None`` meaning "inherit the default
  text size". The editor exposes this as a "Custom size" checkbox + a
  ``QDoubleSpinBox``; unchecking writes ``None`` back.
- ``ha``: one of ``'left'``, ``'center'``, ``'right'`` (``GLEWriter.add_text``
  maps anything else to ``'left'``).
- ``va`` and ``box_color`` are stored on the dict (and, in ``box_color``'s
  case, round-tripped through ``rgb_to_gle`` by ``Axes.text``'s ``bbox``
  argument) but **neither has any effect on the GLE output**:
  ``figure.py``'s render loop never passes ``va`` to
  ``GLEWriter.add_text`` at all, and the writer explicitly ignores the
  ``box_color`` parameter it does receive (see the comment by
  ``_ = box_color`` in ``writer.py``). This panel displays both, but the
  controls are disabled and carry a tooltip noting they are not rendered by
  GLE output, so no in-place mutation path is wired for them.

Mutations follow the standard panel pattern (see ``axes_panel.py`` /
``series_panel.py``): edit the dict in place, then
``document.notify_changed()``.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gleplot.colors import rgb_to_gle

#: Best-effort inverse of the GLE named-color table, copied from
#: series_panel.py so the color dialog can show a representative swatch.
#: colors.py has no official GLE-name -> RGB inverse; unmapped names
#: (unlikely, since only this fixed palette is ever stored) fall back to
#: black.
_GLE_COLOR_TO_RGB = {
    "BLUE": (0, 0, 255),
    "RED": (255, 0, 0),
    "GREEN": (0, 128, 0),
    "CYAN": (0, 255, 255),
    "MAGENTA": (255, 0, 255),
    "YELLOW": (255, 255, 0),
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "ORANGE": (255, 165, 0),
    "PURPLE": (128, 0, 128),
    "BROWN": (165, 42, 42),
    "PINK": (255, 192, 203),
    "GRAY": (128, 128, 128),
    "LIGHTBLUE": (173, 216, 230),
    "LIGHTGREEN": (144, 238, 144),
    "LIGHTCYAN": (224, 255, 255),
    "LIGHTGRAY": (211, 211, 211),
    "DARKBLUE": (0, 0, 139),
    "DARKGREEN": (0, 100, 0),
    "DARKRED": (139, 0, 0),
    "DARKGRAY": (169, 169, 169),
}

#: Horizontal-alignment values accepted by Axes.text/GLEWriter.add_text.
_HA_VALUES = ("left", "center", "right")

#: Vertical-alignment values Axes.text accepts for API compatibility. Stored
#: but never emitted by the writer -- see module docstring.
_VA_VALUES = ("top", "center", "bottom")

#: Tooltip used on the va combo and box_color swatch: both are stored on the
#: text dict but have no effect on the GLE output.
_NO_EFFECT_TOOLTIP = "Stored but not rendered by GLE output."

#: fontsize spin box range, in points.
_FONTSIZE_MIN = 4.0
_FONTSIZE_MAX = 72.0
_FONTSIZE_DEFAULT = 12.0

#: Number of characters of the annotation text shown in the list entry
#: before truncation (plus an ellipsis).
_LIST_TEXT_PREVIEW_LEN = 30


def _preview_text(text: str) -> str:
    text = text or ""
    # Collapse embedded newlines for the one-line list preview.
    flat = " ".join(text.splitlines())
    if len(flat) > _LIST_TEXT_PREVIEW_LEN:
        return flat[:_LIST_TEXT_PREVIEW_LEN].rstrip() + "..."
    return flat


def _format_coord(value) -> str:
    try:
        return f"{float(value):.3g}"
    except (TypeError, ValueError):
        return "?"


def _format_entry(entry: dict) -> str:
    preview = _preview_text(entry.get("text", "")) or "(empty)"
    x = _format_coord(entry.get("x"))
    y = _format_coord(entry.get("y"))
    return f"{preview} — ({x}, {y})"


class TextsPanel(QWidget):
    """Annotation list + editor for the text annotations of the current axes.

    Parameters
    ----------
    document
        Duck-typed document exposing ``figure``, ``figure_changed``/
        ``figure_replaced`` signals, and ``notify_changed()``.

    Notes
    -----
    Integration hook for the on-canvas drag overlay (built in parallel in
    ``gleplot/gui/annotations.py``): external code can call
    :meth:`select_text` to programmatically select an annotation (e.g. after
    a canvas click) without triggering :data:`text_selected`, and can read
    :attr:`current_index` to find out what's currently selected. When the
    *user* changes the list selection (click, arrow keys, ...),
    :data:`text_selected` fires so the overlay can highlight the
    corresponding on-canvas handle.

    Signals
    -------
    text_selected(int)
        Emitted with the newly-selected row index when the user changes the
        list selection. Not emitted for programmatic selection changes
        (:meth:`select_text`, :meth:`refresh`, ``set_axes``).
    """

    text_selected = Signal(int)

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._updating = False
        self._axes = None  # explicit override, mirrors AxesPanel.set_axes
        self._current_color_rgb = (0, 0, 0)

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # Axes targeting (mirrors AxesPanel/SeriesPanel)
    # ------------------------------------------------------------------
    def set_axes(self, ax) -> None:
        """Target a specific axes instead of the figure's current axes."""
        self._axes = ax
        self.refresh()

    def _current_axes(self):
        if self._axes is not None:
            return self._axes
        figure = self._document.figure
        if figure is None:
            return None
        return figure.gca()

    def current_axes(self):
        """Public accessor for the axes this panel currently targets.

        Sync hook for the annotation overlay (``gleplot/gui/annotations.py``):
        used to decide whether a selected ``text_dict`` belongs to this
        panel's target axes, or whether the panel needs retargeting first via
        :meth:`set_axes`.
        """
        return self._current_axes()

    # ------------------------------------------------------------------
    # Public selection API (sync hook for the on-canvas overlay)
    # ------------------------------------------------------------------
    @property
    def current_index(self) -> int:
        """Row index of the currently-selected annotation, or -1 if none."""
        return self.text_list.currentRow()

    def select_text(self, index: int) -> None:
        """Programmatically select annotation ``index``.

        Does not emit :data:`text_selected` (guarded), since this is meant
        to be called *in response to* an external selection (e.g. a canvas
        click on the drag overlay), not as a user action against this panel.
        """
        was_updating = self._updating
        self._updating = True
        try:
            self.text_list.setCurrentRow(index)
            self._populate_editor(self._selected_entry())
        finally:
            self._updating = was_updating

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        self.text_list = QListWidget(self)
        outer.addWidget(self.text_list)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton("Add", self)
        self.remove_button = QPushButton("Remove", self)
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.remove_button)
        outer.addLayout(buttons_row)

        form = QFormLayout()

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setMaximumHeight(60)
        self.text_edit.setTabChangesFocus(True)

        self.x_edit = QLineEdit(self)
        self.y_edit = QLineEdit(self)

        color_row = QHBoxLayout()
        self.color_button = QPushButton(self)
        self.color_button.setFixedWidth(60)
        color_row.addWidget(self.color_button)
        color_row.addStretch(1)

        size_row = QHBoxLayout()
        self.custom_size_check = QCheckBox("Custom size", self)
        self.fontsize_spin = QDoubleSpinBox(self)
        self.fontsize_spin.setRange(_FONTSIZE_MIN, _FONTSIZE_MAX)
        self.fontsize_spin.setDecimals(1)
        self.fontsize_spin.setSingleStep(1.0)
        self.fontsize_spin.setSuffix(" pt")
        size_row.addWidget(self.custom_size_check)
        size_row.addWidget(self.fontsize_spin)
        size_row.addStretch(1)

        self.ha_combo = QComboBox(self)
        self.ha_combo.addItems(_HA_VALUES)

        self.va_combo = QComboBox(self)
        self.va_combo.addItems(_VA_VALUES)
        self.va_combo.setEnabled(False)
        self.va_combo.setToolTip(_NO_EFFECT_TOOLTIP)

        self.box_color_button = QPushButton(self)
        self.box_color_button.setFixedWidth(60)
        self.box_color_button.setEnabled(False)
        self.box_color_button.setToolTip(_NO_EFFECT_TOOLTIP)

        form.addRow("Text", self.text_edit)
        form.addRow("X", self.x_edit)
        form.addRow("Y", self.y_edit)
        form.addRow("Color", color_row)
        form.addRow("Font size", size_row)
        form.addRow("Horiz. align", self.ha_combo)
        form.addRow("Vert. align", self.va_combo)
        form.addRow("Box color", self.box_color_button)

        outer.addLayout(form)

        self._style_form = form
        self._set_editor_enabled(False)

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self.refresh)
        self._document.figure_replaced.connect(self._on_figure_replaced)

        self.text_list.currentRowChanged.connect(self._on_list_selection_changed)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)

        # Commit on focus-out for the multi-line text editor: editingFinished
        # doesn't exist on QPlainTextEdit, so we hook focusOutEvent via an
        # event filter (documented choice below).
        self.text_edit.installEventFilter(self)

        self.x_edit.editingFinished.connect(self._on_x_edited)
        self.y_edit.editingFinished.connect(self._on_y_edited)
        self.color_button.clicked.connect(self._on_color_clicked)
        self.custom_size_check.toggled.connect(self._on_custom_size_toggled)
        self.fontsize_spin.editingFinished.connect(self._on_fontsize_edited)
        self.ha_combo.currentTextChanged.connect(self._on_ha_changed)

    def _on_figure_replaced(self) -> None:
        """Handle a brand-new figure being installed (New/Open/undo/redo).

        Mirrors AxesPanel/SeriesPanel: the ``_axes`` override points at the
        old figure's (now dead) Axes, so drop it and fall back to the live
        ``document.figure.gca()``.
        """
        self._axes = None
        self.refresh()

    # ------------------------------------------------------------------
    # eventFilter: commit multi-line text on focus-out
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt override)
        if obj is self.text_edit and event.type() == event.Type.FocusOut:
            self._on_text_committed()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Model -> UI: list population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Full refresh: rebuild the annotation list and the editor."""
        ax = self._current_axes()
        self.setEnabled(ax is not None)

        self._updating = True
        try:
            previous_row = self.text_list.currentRow()
            self.text_list.clear()

            if ax is not None:
                for entry in ax.texts:
                    item = QListWidgetItem(_format_entry(entry))
                    self.text_list.addItem(item)

            if 0 <= previous_row < self.text_list.count():
                self.text_list.setCurrentRow(previous_row)
            elif self.text_list.count() > 0:
                self.text_list.setCurrentRow(0)
            else:
                self._populate_editor(None)
        finally:
            self._updating = False

        # Populate the editor for whatever ended up selected (outside the
        # guard so this exercises the same code path as user selection, but
        # without emitting text_selected -- selection here is a side effect
        # of refresh(), not a user action).
        self._populate_editor(self._selected_entry())

    def _selected_entry(self) -> Optional[dict]:
        ax = self._current_axes()
        if ax is None:
            return None
        row = self.text_list.currentRow()
        if 0 <= row < len(ax.texts):
            return ax.texts[row]
        return None

    def _on_list_selection_changed(self, row: int) -> None:
        self._populate_editor(self._selected_entry())
        if not self._updating:
            self.text_selected.emit(row)

    # ------------------------------------------------------------------
    # Model -> UI: editor
    # ------------------------------------------------------------------
    def _populate_editor(self, entry: Optional[dict]) -> None:
        was_updating = self._updating
        self._updating = True
        try:
            if entry is None:
                self._set_editor_enabled(False)
                # Preserve an in-progress edit: a focused editor must not be
                # clobbered by an external refresh (e.g. a canvas drag commit
                # firing figure_changed while the user is mid-type). This
                # normally only fires when there is genuinely no selection, but
                # guarding keeps the discipline uniform.
                if not self.text_edit.hasFocus():
                    self.text_edit.setPlainText("")
                if not self.x_edit.hasFocus():
                    self.x_edit.setText("")
                if not self.y_edit.hasFocus():
                    self.y_edit.setText("")
                return

            self._set_editor_enabled(True)

            # Skip overwriting any editor the user is currently editing: a
            # refresh triggered externally (canvas drag commit -> figure_changed)
            # must not discard uncommitted typed text. The list and all
            # non-focused fields still refresh. The focused field commits
            # normally on blur via its editingFinished/focus-out path.
            if not self.text_edit.hasFocus():
                self.text_edit.setPlainText(entry.get("text", "") or "")
            if not self.x_edit.hasFocus():
                self.x_edit.setText(_format_coord(entry.get("x", 0.0)))
            if not self.y_edit.hasFocus():
                self.y_edit.setText(_format_coord(entry.get("y", 0.0)))

            color_value = entry.get("color") or "BLACK"
            rgb = _GLE_COLOR_TO_RGB.get(str(color_value).upper(), (0, 0, 0))
            self._current_color_rgb = rgb
            self._update_color_swatch(rgb)

            fontsize = entry.get("fontsize")
            has_custom = fontsize is not None
            self.custom_size_check.setChecked(has_custom)
            self.fontsize_spin.setEnabled(has_custom)
            self.fontsize_spin.setValue(float(fontsize) if has_custom else _FONTSIZE_DEFAULT)

            self._set_combo_text(self.ha_combo, entry.get("ha") or "left")

            va = entry.get("va")
            if va in _VA_VALUES:
                self._set_combo_text(self.va_combo, va)

            box_color = entry.get("box_color")
            box_rgb = _GLE_COLOR_TO_RGB.get(str(box_color).upper(), None) if box_color else None
            if box_rgb is not None:
                self.box_color_button.setStyleSheet(
                    f"background-color: rgb({box_rgb[0]}, {box_rgb[1]}, {box_rgb[2]});"
                )
                self.box_color_button.setText(QColor(*box_rgb).name())
            else:
                self.box_color_button.setStyleSheet("")
                self.box_color_button.setText("(none)")
        finally:
            self._updating = was_updating

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.text_edit.setEnabled(enabled)
        self.x_edit.setEnabled(enabled)
        self.y_edit.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        self.custom_size_check.setEnabled(enabled)
        self.fontsize_spin.setEnabled(enabled and self.custom_size_check.isChecked())
        self.ha_combo.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        # va_combo / box_color_button stay disabled always (no-effect).

    def _update_color_swatch(self, rgb: tuple) -> None:
        color = QColor(*rgb)
        self.color_button.setStyleSheet(
            f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
        )
        self.color_button.setText(color.name())

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _refresh_selected_list_text(self) -> None:
        entry = self._selected_entry()
        row = self.text_list.currentRow()
        if entry is None or row < 0:
            return
        self._updating = True
        try:
            item = self.text_list.item(row)
            item.setText(_format_entry(entry))
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # UI -> Model: edits
    # ------------------------------------------------------------------
    def _on_text_committed(self) -> None:
        """Commit the multi-line text editor on focus-out.

        Commit-semantics choice: GLE's ``write`` command (emitted by
        ``GLEWriter.add_text``) is single-line, so embedded newlines are
        stripped (joined with a space) before being written back to the
        dict. ``QPlainTextEdit`` has no ``editingFinished`` signal (that's
        QLineEdit-only), so focus-out via an installed event filter is used
        instead of an explicit Apply button -- it matches the
        editingFinished-on-blur discipline used everywhere else in this
        panel family without adding an extra always-visible button for a
        field that's usually a one-line label anyway.
        """
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return

        raw = self.text_edit.toPlainText()
        flattened = " ".join(raw.splitlines())
        if flattened == entry.get("text", ""):
            return

        entry["text"] = flattened

        # Reflect the stripped form back into the widget so the displayed
        # text matches exactly what will be written to GLE.
        self._updating = True
        try:
            if flattened != raw:
                self.text_edit.setPlainText(flattened)
        finally:
            self._updating = False

        self._document.notify_changed()
        self._refresh_selected_list_text()

    def _on_x_edited(self) -> None:
        self._write_float(self.x_edit, "x")

    def _on_y_edited(self) -> None:
        self._write_float(self.y_edit, "y")

    def _write_float(self, edit: QLineEdit, key: str) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return

        text = edit.text().strip()
        try:
            value = float(text)
        except ValueError:
            value = None
        # Reject non-finite coordinates (nan/inf, incl. overflow like 1e400):
        # they would produce corrupted GLE output and NaN geometry downstream.
        if value is None or not math.isfinite(value):
            # Invalid text: revert the field to the current model value.
            self._updating = True
            try:
                edit.setText(_format_coord(entry.get(key, 0.0)))
            finally:
                self._updating = False
            return

        entry[key] = value
        self._updating = True
        try:
            edit.setText(_format_coord(value))
        finally:
            self._updating = False
        self._document.notify_changed()
        self._refresh_selected_list_text()

    def _on_color_clicked(self) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return
        initial = QColor(*self._current_color_rgb)
        color = QColorDialog.getColor(initial, self, "Text color")
        if not color.isValid():
            return
        rgb01 = (color.redF(), color.greenF(), color.blueF())
        gle_color = rgb_to_gle(rgb01)

        entry["color"] = gle_color
        self._current_color_rgb = (
            int(color.red()),
            int(color.green()),
            int(color.blue()),
        )
        self._update_color_swatch(self._current_color_rgb)
        self._document.notify_changed()

    def _on_custom_size_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return

        self._updating = True
        try:
            self.fontsize_spin.setEnabled(checked)
            if checked:
                self.fontsize_spin.setValue(_FONTSIZE_DEFAULT)
        finally:
            self._updating = False

        entry["fontsize"] = float(self.fontsize_spin.value()) if checked else None
        self._document.notify_changed()

    def _on_fontsize_edited(self) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None or not self.custom_size_check.isChecked():
            return
        entry["fontsize"] = float(self.fontsize_spin.value())
        self._document.notify_changed()

    def _on_ha_changed(self, text: str) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return
        entry["ha"] = text
        self._document.notify_changed()

    # ------------------------------------------------------------------
    # Add / Remove
    # ------------------------------------------------------------------
    def _on_add_clicked(self) -> None:
        ax = self._current_axes()
        if ax is None:
            return

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        x = (xmin + xmax) / 2.0 if xmin is not None and xmax is not None else 0.5
        y = (ymin + ymax) / 2.0 if ymin is not None and ymax is not None else 0.5

        # Public Axes.text API, per spec, rather than appending to ax.texts
        # directly -- keeps this panel's "add" path exercising the same
        # validation/defaulting logic as any other caller (color -> 'BLACK',
        # ha default, etc.).
        ax.text(x, y, "New text")
        self._document.notify_changed()

        self._updating = True
        try:
            self.refresh()
        finally:
            self._updating = False
        # Select the newly-added (last) entry.
        self.select_text(len(ax.texts) - 1)

    def _on_remove_clicked(self) -> None:
        if self._updating:
            return
        ax = self._current_axes()
        if ax is None:
            return
        row = self.text_list.currentRow()
        if 0 <= row < len(ax.texts):
            del ax.texts[row]
        self._document.notify_changed()
        self.refresh()

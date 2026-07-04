"""Series (line/scatter/bar/fill/errorbar/file-series) property panel.

:class:`SeriesPanel` shows an aggregated list of every series drawn on the
current axes and a style editor for whichever series is selected.

Stored-representation conventions mirrored here (see ``gleplot/axes.py``):

- ``color``: GLE color name string (e.g. ``'BLUE'``), produced by
  ``colors.rgb_to_gle``. There is no official GLE-name -> RGB inverse in
  ``colors.py``; :data:`_GLE_COLOR_TO_RGB` below is this panel's best-effort
  inverse (built from the same named-color table) purely so the color
  dialog can show a representative swatch. Colors that can't be mapped
  (unlikely, since only the fixed GLE palette is ever stored) fall back to
  black, as instructed.
- ``marker``: GLE marker name string (e.g. ``'FCIRCLE'``) or ``None`` for
  no marker, produced by ``markers.get_gle_marker``. The combo shows
  matplotlib-style codes ('o', 's', '^', ...) and translates through
  ``get_gle_marker`` on write, with an explicit 'none' option stored as
  ``None``.
- ``linestyle``: raw string as passed to ``Axes.plot``/``errorbar``:
  ``'-'``, ``'--'``, ``':'``, ``'-.'``, or ``'none'``. Stored verbatim,
  no conversion.
- ``linewidth``: matplotlib-scale float, stored verbatim (``Axes.plot``
  never rescales it).
- ``markersize``: stored in **GLE msize units**. ``Axes.plot`` converts via
  ``gle_markersize = markersize * 0.025 * figure.marker_config.msize_scale``.
  This panel shows the user a matplotlib-scale number and inverts that
  formula on read/write so edits round-trip through the same conversion.
- ``label``: stored verbatim, ``None`` allowed.

Series kinds and their applicable controls:

===========  =====  =======  ==========  =========  =====
kind         color  marker   linestyle   linewidth  label
===========  =====  =======  ==========  =========  =====
line         yes    yes      yes         yes        yes
scatter      yes    yes      no          no         yes
errorbar     yes    yes      yes         yes        yes
bar          yes*   no       no          no         yes
fill         yes    no       no          no         yes
file_series  yes    depends  depends     depends    yes
===========  =====  =======  ==========  =========  =====

``bar`` stores a per-point ``colors`` list rather than a single ``color``
key (GLE only supports one color per bar chart in practice, so all entries
are kept equal — see ``Axes.bar``); this panel edits index 0 and rewrites
the whole list to match, preserving the "one color" invariant.

``file_series`` entries have a ``series_type`` key (``'line'`` or
``'errorbar'``) that determines which of marker/linestyle/linewidth apply,
mirroring ``Axes.line_from_file``/``Axes.errorbar_from_file``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gleplot.colors import rgb_to_gle
from gleplot.markers import get_gle_marker

#: Stable iteration order for aggregating series across an axes. Must match
#: Axes._SERIES_ATTRS (writer emission order) so list positions stay
#: meaningful, even though this panel only needs "some stable order".
_KIND_ATTRS = (
    ("line", "lines"),
    ("scatter", "scatters"),
    ("bar", "bars"),
    ("fill", "fills"),
    ("errorbar", "errorbars"),
    ("file_series", "file_series"),
)

#: matplotlib-style marker codes shown in the combo box, plus 'none'.
_MARKER_CODES = ("none", "o", "s", "^", "v", "D", "*", "p", "+", "x", ".")

#: linestyle codes as stored verbatim in the series dicts.
_LINESTYLE_CODES = ("-", "--", ":", "-.", "none")

#: Best-effort inverse of colors.MATPLOTLIB_TO_GLE_COLORS / GLE_COLORS,
#: for initializing the QColorDialog swatch from a stored GLE color name.
#: colors.py has no official reverse mapping; these RGB triples are chosen
#: to render sensibly and are not meant to be exact GLE hues.
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

#: Inverse of markers.MATPLOTLIB_TO_GLE_MARKERS, best-effort (several
#: matplotlib codes map to the same GLE marker; we pick one representative
#: matplotlib code per GLE name so a stored marker can be shown selected).
_GLE_MARKER_TO_CODE = {
    "FCIRCLE": "o",
    "FSQUARE": "s",
    "FTRIANGLE": "^",
    "FTRIANGLED": "v",
    "TRIANGLE": "^",
    "FDIAMOND": "D",
    "FSTARR": "*",
    "STARR": "p",
    "PLUS": "+",
    "PCROSS": "x",
    "DOT": ".",
}

# GLE msize = markersize * 0.025 * msize_scale  =>  markersize = msize / (0.025 * msize_scale)
_MSIZE_PER_MPL_UNIT = 0.025


class SeriesPanel(QWidget):
    """Aggregated series list + style editor for the current axes.

    Parameters
    ----------
    document
        Duck-typed document exposing ``figure``, ``figure_changed``/
        ``figure_replaced`` signals, and ``notify_changed()``.

    Notes
    -----
    Ordering limitation: Up/Down only reorders within the series' own kind
    list (e.g. moving a line only changes its position among ``ax.lines``).
    The relative draw order *between* kinds (lines, then scatters, then
    bars, ...) is fixed by ``Axes._SERIES_ATTRS`` / the GLEWriter emission
    order and cannot be changed from this panel.
    """

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._updating = False
        self._axes = None  # explicit override, mirrors AxesPanel.set_axes
        # Parallel to the QListWidget rows: (kind, list_ref, index_in_list)
        self._entries: list[tuple[str, list, int]] = []

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # Axes targeting (Phase 2 hook, mirrors AxesPanel)
    # ------------------------------------------------------------------
    def set_axes(self, ax) -> None:
        self._axes = ax
        self.refresh()

    def _current_axes(self):
        if self._axes is not None:
            return self._axes
        figure = self._document.figure
        if figure is None:
            return None
        return figure.gca()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        self.series_list = QListWidget(self)
        outer.addWidget(self.series_list)

        buttons_row = QHBoxLayout()
        self.remove_button = QPushButton("Remove", self)
        self.up_button = QPushButton("Up", self)
        self.down_button = QPushButton("Down", self)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addWidget(self.up_button)
        buttons_row.addWidget(self.down_button)
        outer.addLayout(buttons_row)

        form = QFormLayout()

        self.label_edit = QLineEdit(self)

        color_row = QHBoxLayout()
        self.color_button = QPushButton(self)
        self.color_button.setFixedWidth(60)
        color_row.addWidget(self.color_button)
        color_row.addStretch(1)

        self.linestyle_combo = QComboBox(self)
        self.linestyle_combo.addItems(_LINESTYLE_CODES)

        self.marker_combo = QComboBox(self)
        self.marker_combo.addItems(_MARKER_CODES)

        self.linewidth_spin = QDoubleSpinBox(self)
        self.linewidth_spin.setRange(0.1, 20.0)
        self.linewidth_spin.setSingleStep(0.25)
        self.linewidth_spin.setDecimals(2)

        self.markersize_spin = QDoubleSpinBox(self)
        self.markersize_spin.setRange(0.5, 100.0)
        self.markersize_spin.setSingleStep(0.5)
        self.markersize_spin.setDecimals(2)

        form.addRow("Label", self.label_edit)
        form.addRow("Color", color_row)
        form.addRow("Line style", self.linestyle_combo)
        form.addRow("Marker", self.marker_combo)
        form.addRow("Line width", self.linewidth_spin)
        form.addRow("Marker size", self.markersize_spin)

        outer.addLayout(form)

        # Keep references to (widget, form-row-label-widget) so we can hide
        # rows that don't apply to the selected series kind.
        self._style_form = form
        self._current_color_rgb = (0, 0, 0)

        self._set_style_controls_enabled(False)

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self.refresh)
        self._document.figure_replaced.connect(self._on_figure_replaced)

        self.series_list.currentRowChanged.connect(self._on_selection_changed)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        self.up_button.clicked.connect(self._on_up_clicked)
        self.down_button.clicked.connect(self._on_down_clicked)

        self.label_edit.editingFinished.connect(self._on_label_edited)
        self.color_button.clicked.connect(self._on_color_clicked)
        self.linestyle_combo.currentTextChanged.connect(self._on_linestyle_changed)
        self.marker_combo.currentTextChanged.connect(self._on_marker_changed)
        self.linewidth_spin.editingFinished.connect(self._on_linewidth_edited)
        self.markersize_spin.editingFinished.connect(self._on_markersize_edited)

    def _on_figure_replaced(self) -> None:
        """Handle a brand-new figure being installed (New/Open/undo/redo).

        Mirrors :meth:`AxesPanel._on_figure_replaced`: the ``_axes`` override
        points at the old figure's (now dead) Axes, so drop it and fall back to
        the live ``document.figure.gca()``. LayoutPanel re-emits
        ``axes_selected`` afterwards to re-target the correct slot.
        """
        self._axes = None
        self.refresh()

    # ------------------------------------------------------------------
    # Model -> UI: list population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Full refresh: rebuild the series list and the style editor."""
        ax = self._current_axes()
        self.setEnabled(ax is not None)

        self._updating = True
        try:
            previous_row = self.series_list.currentRow()
            self.series_list.clear()
            self._entries = []

            if ax is not None:
                for kind, attr in _KIND_ATTRS:
                    series_list = getattr(ax, attr)
                    for index, series in enumerate(series_list):
                        label = series.get("label") or f"series {index}"
                        item = QListWidgetItem(f"{kind}: {label}")
                        self.series_list.addItem(item)
                        self._entries.append((kind, series_list, index))

            if 0 <= previous_row < self.series_list.count():
                self.series_list.setCurrentRow(previous_row)
            elif self.series_list.count() > 0:
                self.series_list.setCurrentRow(0)
            else:
                self._populate_style_editor(None)
        finally:
            self._updating = False

        # Populate style editor for whatever ended up selected (outside the
        # guard, so this path exercises the same code as user selection).
        self._on_selection_changed(self.series_list.currentRow())

    def _selected_entry(self) -> Optional[tuple[str, list, int]]:
        row = self.series_list.currentRow()
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def _selected_series_dict(self) -> Optional[dict]:
        entry = self._selected_entry()
        if entry is None:
            return None
        _kind, series_list, index = entry
        if index >= len(series_list):
            return None
        return series_list[index]

    # ------------------------------------------------------------------
    # Model -> UI: style editor
    # ------------------------------------------------------------------
    def _on_selection_changed(self, row: int) -> None:
        entry = self._selected_entry()
        if entry is None:
            self._populate_style_editor(None)
            return
        kind, series_list, index = entry
        series = series_list[index] if index < len(series_list) else None
        self._populate_style_editor(kind, series)

    def _populate_style_editor(self, kind: Optional[str], series: Optional[dict] = None) -> None:
        was_updating = self._updating
        self._updating = True
        try:
            if kind is None or series is None:
                self._set_style_controls_enabled(False)
                return

            applicable = _applicable_controls(kind, series)
            self._set_style_controls_enabled(True, applicable)

            self.label_edit.setText(series.get("label") or "")

            color_value = self._series_color(kind, series)
            rgb = _GLE_COLOR_TO_RGB.get(str(color_value).upper(), (0, 0, 0))
            self._current_color_rgb = rgb
            self._update_color_swatch(rgb)

            if applicable.get("linestyle"):
                self._set_combo_text(self.linestyle_combo, series.get("linestyle") or "-")

            if applicable.get("marker"):
                marker_name = series.get("marker")
                code = _GLE_MARKER_TO_CODE.get(marker_name, "none") if marker_name else "none"
                self._set_combo_text(self.marker_combo, code)

            if applicable.get("linewidth"):
                self.linewidth_spin.setValue(float(series.get("linewidth") or 1.0))

            if applicable.get("markersize"):
                gle_size = series.get("markersize") or 0.0
                scale = self._msize_scale()
                mpl_size = gle_size / (_MSIZE_PER_MPL_UNIT * scale) if scale else 0.0
                self.markersize_spin.setValue(float(mpl_size))
        finally:
            self._updating = was_updating

    def _msize_scale(self) -> float:
        figure = self._document.figure
        if figure is None:
            return 1.0
        return float(getattr(figure.marker_config, "msize_scale", 1.0) or 1.0)

    @staticmethod
    def _series_color(kind: str, series: dict):
        if kind == "bar":
            colors = series.get("colors") or []
            return colors[0] if colors else "BLACK"
        return series.get("color", "BLACK")

    def _set_style_controls_enabled(self, enabled: bool, applicable: Optional[dict] = None) -> None:
        applicable = applicable or {}
        self.label_edit.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        self.linestyle_combo.setEnabled(enabled and applicable.get("linestyle", False))
        self.marker_combo.setEnabled(enabled and applicable.get("marker", False))
        self.linewidth_spin.setEnabled(enabled and applicable.get("linewidth", False))
        self.markersize_spin.setEnabled(enabled and applicable.get("markersize", False))
        self.remove_button.setEnabled(enabled)
        self.up_button.setEnabled(enabled)
        self.down_button.setEnabled(enabled)

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

    # ------------------------------------------------------------------
    # List operations: remove / reorder
    # ------------------------------------------------------------------
    def _on_remove_clicked(self) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return
        _kind, series_list, index = entry
        if index < len(series_list):
            del series_list[index]
        self._document.notify_changed()
        self.refresh()

    def _on_up_clicked(self) -> None:
        self._reorder(-1)

    def _on_down_clicked(self) -> None:
        self._reorder(1)

    def _reorder(self, delta: int) -> None:
        if self._updating:
            return
        entry = self._selected_entry()
        if entry is None:
            return
        _kind, series_list, index = entry
        new_index = index + delta
        if new_index < 0 or new_index >= len(series_list):
            return
        series_list[index], series_list[new_index] = (
            series_list[new_index],
            series_list[index],
        )
        self._document.notify_changed()

        self._updating = True
        try:
            self.refresh()
        finally:
            self._updating = False
        # Keep the moved item selected at its new row.
        row_shift = 1 if delta > 0 else -1
        new_row = self.series_list.currentRow() + row_shift
        # After refresh(), selection defaults to previous_row (unchanged
        # numeric row), which already points at the moved item's new slot
        # within this kind since kinds are contiguous blocks; no further
        # action needed. row_shift kept for clarity/documentation only.
        del new_row

    # ------------------------------------------------------------------
    # UI -> Model: style edits
    # ------------------------------------------------------------------
    def _on_label_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None:
            return
        series["label"] = self.label_edit.text() or None
        self._document.notify_changed()
        self._refresh_selected_list_text()

    def _refresh_selected_list_text(self) -> None:
        entry = self._selected_entry()
        row = self.series_list.currentRow()
        if entry is None or row < 0:
            return
        kind, series_list, index = entry
        series = series_list[index]
        label = series.get("label") or f"series {index}"
        self._updating = True
        try:
            self.series_list.item(row).setText(f"{kind}: {label}")
        finally:
            self._updating = False

    def _on_color_clicked(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None:
            return
        initial = QColor(*self._current_color_rgb)
        color = QColorDialog.getColor(initial, self, "Series color")
        if not color.isValid():
            return
        rgb01 = (color.redF(), color.greenF(), color.blueF())
        gle_color = rgb_to_gle(rgb01)

        entry = self._selected_entry()
        kind = entry[0] if entry else None
        if kind == "bar":
            count = len(series.get("colors") or [1])
            series["colors"] = [gle_color] * max(count, 1)
        else:
            series["color"] = gle_color

        self._current_color_rgb = (
            int(color.red()),
            int(color.green()),
            int(color.blue()),
        )
        self._update_color_swatch(self._current_color_rgb)
        self._document.notify_changed()

    def _on_linestyle_changed(self, text: str) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.linestyle_combo.isEnabled():
            return
        series["linestyle"] = text
        self._document.notify_changed()

    def _on_marker_changed(self, text: str) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.marker_combo.isEnabled():
            return
        series["marker"] = get_gle_marker(text) if text != "none" else None
        self._document.notify_changed()

    def _on_linewidth_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.linewidth_spin.isEnabled():
            return
        series["linewidth"] = float(self.linewidth_spin.value())
        self._document.notify_changed()

    def _on_markersize_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.markersize_spin.isEnabled():
            return
        scale = self._msize_scale()
        mpl_value = float(self.markersize_spin.value())
        series["markersize"] = mpl_value * _MSIZE_PER_MPL_UNIT * scale
        self._document.notify_changed()


def _applicable_controls(kind: str, series: dict) -> dict:
    """Return which style controls apply to a series of the given kind.

    Mirrors the fields each ``Axes`` method actually stores (see module
    docstring table). ``file_series`` depends on its own ``series_type``.
    """
    if kind == "line":
        # GLE renders markers on line datasets natively (Axes.plot preserves
        # a marker alongside a solid/dashed line), so a line series may carry
        # both a line style and a marker with a marker size.
        return {"color": True, "marker": True, "linestyle": True,
                "linewidth": True, "markersize": True}
    if kind == "scatter":
        return {"color": True, "marker": True, "linestyle": False,
                "linewidth": False, "markersize": True}
    if kind == "errorbar":
        return {"color": True, "marker": True, "linestyle": True,
                "linewidth": True, "markersize": True}
    if kind == "bar":
        return {"color": True, "marker": False, "linestyle": False,
                "linewidth": False, "markersize": False}
    if kind == "fill":
        return {"color": True, "marker": False, "linestyle": False,
                "linewidth": False, "markersize": False}
    if kind == "file_series":
        series_type = series.get("series_type")
        if series_type == "errorbar":
            return {"color": True, "marker": True, "linestyle": False,
                    "linewidth": False, "markersize": True}
        return {"color": True, "marker": False, "linestyle": True,
                "linewidth": True, "markersize": False}
    return {"color": False, "marker": False, "linestyle": False,
            "linewidth": False, "markersize": False}

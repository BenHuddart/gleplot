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
- ``offset``: vertical shift applied at plot time (waterfall/overlay). Stored
  verbatim as a float; the writer emits ``let dK = dJ+offset`` so the .dat
  file keeps its raw values (see ``writer.GLEWriter._apply_offset``).

Series kinds and their applicable controls:

===========  =====  =======  ==========  =========  =====  ======
kind         color  marker   linestyle   linewidth  label  offset
===========  =====  =======  ==========  =========  =====  ======
line         yes    yes      yes         yes        yes    yes
scatter      yes    yes      no          no         yes    yes
errorbar     yes    yes      yes         yes        yes    yes
bar          yes*   no       no          no         yes    no
fill         yes    no       no          no         yes    yes
file_series  yes    depends  depends     depends    yes    no
heatmap      no     no       no          no         yes    no
contour      yes    no       no          yes        yes    no
===========  =====  =======  ==========  =========  =====  ======

``heatmap`` (``imshow``/``tripcolor``) and ``contour``
(``contour``/``tricontour``) additionally expose their own dedicated
controls, applicable only to that kind:

===========  ==================================================================
kind         extra controls
===========  ==================================================================
heatmap      palette, colour min/max (blank = auto), pixels, interpolation,
             invert, colorbar toggle + colorbar label/format
contour      levels ("0.1 0.2 0.3" explicit list, or "n=10" for n auto levels,
             blank = GLE default), contour labels toggle + label format
===========  ==================================================================

For ``heatmap`` the ``color`` control is disabled (a colormap has no single
line colour); ``contour`` reuses the shared ``color`` and ``line width``
controls for its line styling. Both kinds keep ``label`` editable. Because
GLE allows at most one heatmap per axes, this panel never *creates* a
heatmap (that happens in the Data dock, which guards the limit); it only
edits an existing one.

``bar`` stores a per-point ``colors`` list rather than a single ``color``
key (GLE only supports one color per bar chart in practice, so all entries
are kept equal — see ``Axes.bar``); this panel edits index 0 and rewrites
the whole list to match, preserving the "one color" invariant.

``file_series`` entries have a ``series_type`` key (``'line'`` or
``'errorbar'``) that determines which of marker/linestyle/linewidth apply,
mirroring ``Axes.line_from_file``/``Axes.errorbar_from_file``.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gleplot.colors import rgb_to_gle
from gleplot.markers import get_gle_marker
from gleplot.mathtext import mathtext_to_gle
from gleplot.palettes import SUPPORTED_CMAPS, canonical_cmap

#: Marker prefixed onto the label of a ``file_series`` entry carrying a
#: ``data_error`` (broken data reference), both in the aggregated list and
#: in the tooltip lead-in.
_BROKEN_MARKER = "⚠"  # warning sign

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
    ("heatmap", "heatmaps"),
    ("contour", "contours"),
)

#: Interpolation modes shown in the heatmap interpolation combo, matching the
#: values stored on a heatmap dict by ``Axes.imshow``/``Axes.tripcolor``.
_INTERPOLATION_MODES = ("bicubic", "nearest")

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

    Broken ``file_series`` entries (a ``data`` reference whose file was
    missing/unreadable when the ``.gle`` was parsed -- see
    ``gleplot.parser.recognizer``) carry a ``'data_error'`` key. Such an
    entry renders in the list with a warning marker and a tooltip holding
    the error text; when selected, an error strip and a "Locate file..."
    button appear above the style form so the user can repoint the
    ``'data_file'`` key at a real file. Style controls that only affect
    regeneration (color, label) stay enabled; the rest follow the normal
    per-kind applicability rules.

    Signals
    -------
    series_repointed(str)
        Emitted with the new absolute file path after a broken
        ``file_series`` entry has been successfully repointed via the
        "Locate file..." flow.
    """

    series_repointed = Signal(str)

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

        # Error strip + "Locate file..." button, shown only when the
        # selected series is a broken file_series entry (carries
        # 'data_error'). Lives above the style form so it reads as part of
        # the style-editor area for the selected series.
        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setVisible(False)
        outer.addWidget(self.error_label)

        self.locate_button = QPushButton("Locate file...", self)
        self.locate_button.setVisible(False)
        outer.addWidget(self.locate_button)

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

        # Vertical offset (waterfall/overlay). A non-zero value shifts the trace
        # in the GLE script (via 'let dK = dJ+off'); the .dat file stays raw.
        self.offset_spin = QDoubleSpinBox(self)
        self.offset_spin.setRange(-1.0e9, 1.0e9)
        self.offset_spin.setSingleStep(0.1)
        self.offset_spin.setDecimals(6)
        self.offset_spin.setToolTip(
            "Vertical offset applied at plot time (waterfall/overlay stacking). "
            "The data file keeps its raw values."
        )

        form.addRow("Label", self.label_edit)
        form.addRow("Color", color_row)
        form.addRow("Line style", self.linestyle_combo)
        form.addRow("Marker", self.marker_combo)
        form.addRow("Line width", self.linewidth_spin)
        form.addRow("Marker size", self.markersize_spin)
        form.addRow("Offset", self.offset_spin)

        # ---- heatmap-only controls (imshow/tripcolor) -----------------
        self.palette_combo = QComboBox(self)
        self.palette_combo.addItems(SUPPORTED_CMAPS)

        # vmin/vmax as free-text so an empty field means "auto" (GLE's
        # data-range default); a spin box has no blank state.
        self.vmin_edit = QLineEdit(self)
        self.vmin_edit.setPlaceholderText("auto")
        self.vmax_edit = QLineEdit(self)
        self.vmax_edit.setPlaceholderText("auto")

        self.pixels_spin = QSpinBox(self)
        self.pixels_spin.setRange(2, 4000)
        self.pixels_spin.setSingleStep(50)
        self.pixels_spin.setToolTip(
            "Bitmap resolution of the colormap (applied to both axes)."
        )

        self.interp_combo = QComboBox(self)
        self.interp_combo.addItems(_INTERPOLATION_MODES)

        self.invert_check = QCheckBox("Invert colours", self)

        self.colorbar_check = QCheckBox("Show colorbar", self)
        self.cbar_label_edit = QLineEdit(self)
        self.cbar_format_edit = QLineEdit(self)
        self.cbar_format_edit.setToolTip(
            'GLE format$ string for the colorbar tick labels, e.g. "fix 1".'
        )

        form.addRow("Palette", self.palette_combo)
        form.addRow("Colour min", self.vmin_edit)
        form.addRow("Colour max", self.vmax_edit)
        form.addRow("Pixels", self.pixels_spin)
        form.addRow("Interpolation", self.interp_combo)
        form.addRow("", self.invert_check)
        form.addRow("", self.colorbar_check)
        form.addRow("Colorbar label", self.cbar_label_edit)
        form.addRow("Colorbar format", self.cbar_format_edit)

        # ---- contour-only controls (contour/tricontour) ---------------
        self.levels_edit = QLineEdit(self)
        self.levels_edit.setPlaceholderText("auto (e.g. 0.1 0.2 0.3 or n=10)")
        self.levels_edit.setToolTip(
            "Explicit contour levels ('0.1 0.2 0.3'), or 'n=10' for n "
            "evenly-spaced auto levels, or blank for GLE's default."
        )

        self.clabel_check = QCheckBox("Label contours", self)
        self.clabel_format_edit = QLineEdit(self)
        self.clabel_format_edit.setToolTip(
            'GLE format$ string for the inline contour labels, e.g. "fix 1".'
        )

        form.addRow("Levels", self.levels_edit)
        form.addRow("", self.clabel_check)
        form.addRow("Label format", self.clabel_format_edit)

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
        self.offset_spin.editingFinished.connect(self._on_offset_edited)
        self.locate_button.clicked.connect(self._on_locate_clicked)

        # heatmap controls
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)
        self.vmin_edit.editingFinished.connect(self._on_vmin_edited)
        self.vmax_edit.editingFinished.connect(self._on_vmax_edited)
        self.pixels_spin.editingFinished.connect(self._on_pixels_edited)
        self.interp_combo.currentTextChanged.connect(self._on_interp_changed)
        self.invert_check.toggled.connect(self._on_invert_toggled)
        self.colorbar_check.toggled.connect(self._on_colorbar_toggled)
        self.cbar_label_edit.editingFinished.connect(self._on_cbar_label_edited)
        self.cbar_format_edit.editingFinished.connect(self._on_cbar_format_edited)

        # contour controls
        self.levels_edit.editingFinished.connect(self._on_levels_edited)
        self.clabel_check.toggled.connect(self._on_clabel_toggled)
        self.clabel_format_edit.editingFinished.connect(self._on_clabel_format_edited)

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
                        text, tooltip = _format_entry(kind, series, index)
                        item = QListWidgetItem(text)
                        if tooltip:
                            item.setToolTip(tooltip)
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

    def _populate_style_editor(
        self, kind: Optional[str], series: Optional[dict] = None
    ) -> None:
        was_updating = self._updating
        self._updating = True
        try:
            if kind is None or series is None:
                self._set_style_controls_enabled(False)
                self._set_error_strip_visible(False)
                return

            data_error = series.get("data_error")
            self._set_error_strip_visible(
                bool(data_error), str(data_error) if data_error else ""
            )

            applicable = _applicable_controls(kind, series)
            self._set_style_controls_enabled(True, applicable)

            self.label_edit.setText(series.get("label") or "")

            color_value = self._series_color(kind, series)
            rgb = _GLE_COLOR_TO_RGB.get(str(color_value).upper(), (0, 0, 0))
            self._current_color_rgb = rgb
            self._update_color_swatch(rgb)

            if applicable.get("linestyle"):
                self._set_combo_text(
                    self.linestyle_combo, series.get("linestyle") or "-"
                )

            if applicable.get("marker"):
                marker_name = series.get("marker")
                code = (
                    _GLE_MARKER_TO_CODE.get(marker_name, "none")
                    if marker_name
                    else "none"
                )
                self._set_combo_text(self.marker_combo, code)

            if applicable.get("linewidth"):
                self.linewidth_spin.setValue(float(series.get("linewidth") or 1.0))

            if applicable.get("markersize"):
                gle_size = series.get("markersize") or 0.0
                scale = self._msize_scale()
                mpl_size = gle_size / (_MSIZE_PER_MPL_UNIT * scale) if scale else 0.0
                self.markersize_spin.setValue(float(mpl_size))

            if applicable.get("offset"):
                self.offset_spin.setValue(float(series.get("offset") or 0.0))

            if applicable.get("palette"):
                self._set_combo_text(
                    self.palette_combo, series.get("cmap") or "viridis"
                )

            if applicable.get("vmin"):
                self.vmin_edit.setText(_float_to_text(series.get("vmin")))
            if applicable.get("vmax"):
                self.vmax_edit.setText(_float_to_text(series.get("vmax")))

            if applicable.get("pixels"):
                pixels = series.get("pixels") or [200, 200]
                self.pixels_spin.setValue(int(pixels[0]))

            if applicable.get("interpolation"):
                self._set_combo_text(
                    self.interp_combo, series.get("interpolation") or "bicubic"
                )

            if applicable.get("invert"):
                self.invert_check.setChecked(bool(series.get("invert")))

            if applicable.get("colorbar"):
                cb = series.get("colorbar")
                self.colorbar_check.setChecked(cb is not None)
                self.cbar_label_edit.setText((cb or {}).get("label") or "")
                self.cbar_format_edit.setText((cb or {}).get("format") or "fix 1")
                self._sync_colorbar_fields_enabled()

            if applicable.get("levels"):
                self.levels_edit.setText(_levels_to_text(series.get("levels")))

            if applicable.get("clabel"):
                self.clabel_check.setChecked(bool(series.get("clabel")))
                self.clabel_format_edit.setText(series.get("clabel_fmt") or "fix 1")
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

    def _set_error_strip_visible(self, visible: bool, message: str = "") -> None:
        """Show/hide the broken-series error strip + "Locate file..." button."""
        self.error_label.setVisible(visible)
        self.locate_button.setVisible(visible)
        if visible:
            self.error_label.setText(message)
            self.error_label.setToolTip(message)

    def _set_style_controls_enabled(
        self, enabled: bool, applicable: Optional[dict] = None
    ) -> None:
        applicable = applicable or {}
        self.label_edit.setEnabled(enabled)
        # ``color`` applies to every historical kind (default True), but is
        # disabled for a heatmap, which has no single line colour.
        self.color_button.setEnabled(enabled and applicable.get("color", True))
        self.linestyle_combo.setEnabled(enabled and applicable.get("linestyle", False))
        self.marker_combo.setEnabled(enabled and applicable.get("marker", False))
        self.linewidth_spin.setEnabled(enabled and applicable.get("linewidth", False))
        self.markersize_spin.setEnabled(enabled and applicable.get("markersize", False))
        self.offset_spin.setEnabled(enabled and applicable.get("offset", False))

        # heatmap-only controls
        self.palette_combo.setEnabled(enabled and applicable.get("palette", False))
        self.vmin_edit.setEnabled(enabled and applicable.get("vmin", False))
        self.vmax_edit.setEnabled(enabled and applicable.get("vmax", False))
        self.pixels_spin.setEnabled(enabled and applicable.get("pixels", False))
        self.interp_combo.setEnabled(enabled and applicable.get("interpolation", False))
        self.invert_check.setEnabled(enabled and applicable.get("invert", False))
        self.colorbar_check.setEnabled(enabled and applicable.get("colorbar", False))
        # colorbar label/format follow the colorbar toggle (see
        # _sync_colorbar_fields_enabled); disable outright off-heatmap.
        if not (enabled and applicable.get("colorbar", False)):
            self.cbar_label_edit.setEnabled(False)
            self.cbar_format_edit.setEnabled(False)

        # contour-only controls
        self.levels_edit.setEnabled(enabled and applicable.get("levels", False))
        self.clabel_check.setEnabled(enabled and applicable.get("clabel", False))
        self.clabel_format_edit.setEnabled(enabled and applicable.get("clabel", False))

        self.remove_button.setEnabled(enabled)
        self.up_button.setEnabled(enabled)
        self.down_button.setEnabled(enabled)

    def _sync_colorbar_fields_enabled(self) -> None:
        """Enable colorbar label/format only while the colorbar toggle is on."""
        on = self.colorbar_check.isEnabled() and self.colorbar_check.isChecked()
        self.cbar_label_edit.setEnabled(on)
        self.cbar_format_edit.setEnabled(on)

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
        series["label"] = mathtext_to_gle(self.label_edit.text() or None)
        self._document.notify_changed()
        self._refresh_selected_list_text()

    def _refresh_selected_list_text(self) -> None:
        entry = self._selected_entry()
        row = self.series_list.currentRow()
        if entry is None or row < 0:
            return
        kind, series_list, index = entry
        series = series_list[index]
        text, tooltip = _format_entry(kind, series, index)
        self._updating = True
        try:
            item = self.series_list.item(row)
            item.setText(text)
            item.setToolTip(tooltip or "")
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

    def _on_offset_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.offset_spin.isEnabled():
            return
        series["offset"] = float(self.offset_spin.value())
        self._document.notify_changed()

    # ------------------------------------------------------------------
    # UI -> Model: heatmap edits
    # ------------------------------------------------------------------
    def _on_palette_changed(self, text: str) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.palette_combo.isEnabled():
            return
        series["cmap"] = canonical_cmap(text)
        self._document.notify_changed()

    def _on_vmin_edited(self) -> None:
        self._edit_optional_float("vmin", self.vmin_edit)

    def _on_vmax_edited(self) -> None:
        self._edit_optional_float("vmax", self.vmax_edit)

    def _edit_optional_float(self, key: str, edit: QLineEdit) -> None:
        """Store a blank-means-``None`` float from ``edit`` under ``key``.

        Reverts the field to the stored value if the text can't be parsed as a
        float (rather than silently coercing garbage to a number).
        """
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not edit.isEnabled():
            return
        text = edit.text().strip()
        if not text:
            value = None
        else:
            try:
                value = float(text)
            except ValueError:
                edit.setText(_float_to_text(series.get(key)))
                return
        series[key] = value
        self._document.notify_changed()

    def _on_pixels_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.pixels_spin.isEnabled():
            return
        px = int(self.pixels_spin.value())
        series["pixels"] = [px, px]
        self._document.notify_changed()

    def _on_interp_changed(self, text: str) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.interp_combo.isEnabled():
            return
        series["interpolation"] = "nearest" if text == "nearest" else "bicubic"
        self._document.notify_changed()

    def _on_invert_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.invert_check.isEnabled():
            return
        series["invert"] = bool(checked)
        self._document.notify_changed()

    def _on_colorbar_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.colorbar_check.isEnabled():
            return
        if checked:
            if series.get("colorbar") is None:
                series["colorbar"] = self._make_colorbar_dict(
                    series,
                    self.cbar_label_edit.text() or None,
                    self.cbar_format_edit.text() or "fix 1",
                )
        else:
            series["colorbar"] = None
        self._sync_colorbar_fields_enabled()
        self._document.notify_changed()

    def _on_cbar_label_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.cbar_label_edit.isEnabled():
            return
        cb = series.get("colorbar")
        if cb is None:
            return
        cb["label"] = mathtext_to_gle(self.cbar_label_edit.text() or None)
        self._document.notify_changed()

    def _on_cbar_format_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.cbar_format_edit.isEnabled():
            return
        cb = series.get("colorbar")
        if cb is None:
            return
        cb["format"] = self.cbar_format_edit.text() or "fix 1"
        self._document.notify_changed()

    @staticmethod
    def _series_z_range(series: dict) -> tuple:
        """Return ``(zmin, zmax)`` for a heatmap/contour from its stored data.

        Mirrors ``Figure.colorbar``/``Axes._resolve_levels``: a ``vmin``/
        ``vmax`` override wins; otherwise the range is taken from the gridded
        ``z`` (grid source) or the scattered ``zpts`` (points source).
        """
        vmin = series.get("vmin")
        vmax = series.get("vmax")
        data = series.get("z") if series.get("source") == "grid" else series.get("zpts")
        if data is None:
            arr = None
        else:
            arr = np.asarray(data, dtype=float)
        if vmin is not None:
            zmin = float(vmin)
        elif arr is not None and arr.size:
            zmin = float(np.nanmin(arr))
        else:
            zmin = 0.0
        if vmax is not None:
            zmax = float(vmax)
        elif arr is not None and arr.size:
            zmax = float(np.nanmax(arr))
        else:
            zmax = 1.0
        return zmin, zmax

    def _make_colorbar_dict(self, series: dict, label, fmt: str) -> dict:
        """Build a colorbar dict for ``series`` matching ``Figure.colorbar``.

        Targets the selected heatmap directly (rather than calling
        ``Figure.colorbar``, which errors when more than one axes has a
        heatmap) so the panel works regardless of sibling axes.
        """
        zmin, zmax = self._series_z_range(series)
        span = zmax - zmin
        zstep = (span / 5.0) if span > 0 else 1.0
        return {
            "label": mathtext_to_gle(label),
            "format": fmt or "fix 1",
            "width": 0.5,
            "sep": 0.3,
            "zmin": zmin,
            "zmax": zmax,
            "zstep": zstep,
        }

    # ------------------------------------------------------------------
    # UI -> Model: contour edits
    # ------------------------------------------------------------------
    def _on_levels_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.levels_edit.isEnabled():
            return
        try:
            levels = self._parse_levels_text(self.levels_edit.text(), series)
        except ValueError:
            self.levels_edit.setText(_levels_to_text(series.get("levels")))
            return
        series["levels"] = levels
        self._document.notify_changed()

    def _parse_levels_text(self, text: str, series: dict):
        """Parse the levels field to ``None`` or a list of floats.

        Accepts a blank field (``None`` -> GLE's default 10 levels), an
        ``"n=<int>"`` form (``n`` evenly-spaced levels strictly between the
        data's min and max, matching ``Axes._resolve_levels``), or an explicit
        whitespace/comma-separated list of numbers.
        """
        text = text.strip()
        if not text:
            return None
        low = text.lower()
        if low.startswith("n="):
            n = int(low[2:].strip())
            if n < 1:
                raise ValueError("levels count must be >= 1")
            zmin, zmax = self._series_z_range(series)
            return [float(v) for v in np.linspace(zmin, zmax, n + 2)[1:-1]]
        return [float(tok) for tok in text.replace(",", " ").split()]

    def _on_clabel_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.clabel_check.isEnabled():
            return
        series["clabel"] = bool(checked)
        self._document.notify_changed()

    def _on_clabel_format_edited(self) -> None:
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or not self.clabel_format_edit.isEnabled():
            return
        series["clabel_fmt"] = self.clabel_format_edit.text() or "fix 1"
        self._document.notify_changed()

    def _on_locate_clicked(self) -> None:
        """Repoint a broken ``file_series`` entry at a real file on disk.

        Only meaningful for the currently-selected series, and only while it
        actually carries a ``data_error``. Updates the ``'data_file'`` key to
        the chosen file's *absolute* path, drops ``'data_error'``, notifies
        the document, and emits :data:`series_repointed`. Deliberately does
        not attempt to re-load the array data here: ``file_series`` entries
        are reference-mode (the writer regenerates a ``data`` command from
        ``'data_file'`` directly -- see ``Figure._render_axes`` /
        ``GLEWriter.add_plot_line_from_file``/``add_errorbar_from_file``), so
        the next preview compile validates the new path naturally. If the
        chosen path is still wrong, GLE's own compile error will surface in
        the Output dock.
        """
        if self._updating:
            return
        series = self._selected_series_dict()
        if series is None or "data_error" not in series:
            return

        start_dir = ""
        existing = series.get("data_file")
        if existing:
            start_dir = os.path.dirname(os.path.abspath(str(existing)))

        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Locate data file",
            start_dir,
            "Data files (*.dat *.csv *.txt);;All files (*)",
        )
        if not path:
            return

        abs_path = os.path.abspath(path)
        series["data_file"] = abs_path
        series.pop("data_error", None)
        self._document.notify_changed()
        self.refresh()
        self.series_repointed.emit(abs_path)


def _format_entry(kind: str, series: dict, index: int) -> tuple[str, Optional[str]]:
    """Return ``(list_item_text, tooltip_or_None)`` for one aggregated entry.

    A ``file_series`` entry carrying ``'data_error'`` (broken data
    reference -- see ``gleplot.parser.recognizer``) renders with a leading
    warning marker and a "(missing data)" suffix; the tooltip carries the
    full error text. Everything else renders as before (``"kind: label"``,
    no tooltip).
    """
    data_error = series.get("data_error")
    if data_error:
        file_label = series.get("label") or series.get("data_file") or f"series {index}"
        text = f"{_BROKEN_MARKER} {kind}: {file_label} (missing data)"
        return text, str(data_error)
    label = series.get("label") or f"series {index}"
    return f"{kind}: {label}", None


def _applicable_controls(kind: str, series: dict) -> dict:
    """Return which style controls apply to a series of the given kind.

    Mirrors the fields each ``Axes`` method actually stores (see module
    docstring table). ``file_series`` depends on its own ``series_type``.
    """
    if kind == "line":
        # GLE renders markers on line datasets natively (Axes.plot preserves
        # a marker alongside a solid/dashed line), so a line series may carry
        # both a line style and a marker with a marker size.
        return {
            "color": True,
            "marker": True,
            "linestyle": True,
            "linewidth": True,
            "markersize": True,
            "offset": True,
        }
    if kind == "scatter":
        return {
            "color": True,
            "marker": True,
            "linestyle": False,
            "linewidth": False,
            "markersize": True,
            "offset": True,
        }
    if kind == "errorbar":
        return {
            "color": True,
            "marker": True,
            "linestyle": True,
            "linewidth": True,
            "markersize": True,
            "offset": True,
        }
    if kind == "bar":
        return {
            "color": True,
            "marker": False,
            "linestyle": False,
            "linewidth": False,
            "markersize": False,
        }
    if kind == "fill":
        return {
            "color": True,
            "marker": False,
            "linestyle": False,
            "linewidth": False,
            "markersize": False,
            "offset": True,
        }
    if kind == "file_series":
        if series.get("data_error"):
            # Broken reference: the file couldn't be read, so there is no
            # basis for showing/editing marker, linestyle, linewidth, or
            # markersize (several of those depend on series_type, which is
            # still known, but "meaningful" here means "backed by real
            # data"). Color and label are metadata only and always safe to
            # edit -- they affect regeneration regardless of whether the
            # data loads.
            return {
                "color": True,
                "marker": False,
                "linestyle": False,
                "linewidth": False,
                "markersize": False,
            }
        series_type = series.get("series_type")
        if series_type == "errorbar":
            return {
                "color": True,
                "marker": True,
                "linestyle": False,
                "linewidth": False,
                "markersize": True,
            }
        return {
            "color": True,
            "marker": False,
            "linestyle": True,
            "linewidth": True,
            "markersize": False,
        }
    if kind == "heatmap":
        # A colormap has no single line colour; it exposes palette + range +
        # sampling controls plus an optional colorbar instead.
        return {
            "color": False,
            "marker": False,
            "linestyle": False,
            "linewidth": False,
            "markersize": False,
            "offset": False,
            "palette": True,
            "vmin": True,
            "vmax": True,
            "pixels": True,
            "interpolation": True,
            "invert": True,
            "colorbar": True,
        }
    if kind == "contour":
        # Contour lines reuse the shared color + line-width controls, and add
        # a levels editor and inline-label toggle.
        return {
            "color": True,
            "marker": False,
            "linestyle": False,
            "linewidth": True,
            "markersize": False,
            "offset": False,
            "levels": True,
            "clabel": True,
        }
    return {
        "color": False,
        "marker": False,
        "linestyle": False,
        "linewidth": False,
        "markersize": False,
    }


def _float_to_text(value) -> str:
    """Render an optional float for a blank-means-``None`` line edit."""
    if value is None:
        return ""
    return repr(float(value))


def _levels_to_text(levels) -> str:
    """Render a contour ``levels`` value (``None`` or list) as edit text."""
    if not levels:
        return ""
    return " ".join(repr(float(v)) for v in levels)

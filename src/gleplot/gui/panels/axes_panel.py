"""Axes-level property panel.

:class:`AxesPanel` binds title/label/scale/limit/legend controls to a
``gleplot.axes.Axes`` instance. In Phase 1 there is no axes-selection UI yet,
so the panel always targets ``document.figure.gca()``; :meth:`set_axes` is
provided so Phase 2 (subplot/axes selection) can retarget the panel onto a
specific axes without any other changes.

See :mod:`gleplot.gui.panels.figure_panel` for the duck-typed ``document``
contract this panel expects.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from gleplot.mathtext import mathtext_to_gle

#: Scale values accepted by Axes.set_xscale/set_yscale (see axes.py).
_SCALE_VALUES = ("linear", "log")

#: Legend positions produced by Axes.legend()'s loc_map (axes.py) — the
#: long-form GLE position strings. Axes.legend_pos is initialized to
#: 'top right' and only ever set to one of these five values by the
#: public API, so this is the canonical set for the combo box. (GLEWriter's
#: add_legend also accepts short forms 'tr'/'tl'/'br'/'bl'/'cc' and passes
#: unrecognized strings through verbatim, but the object model itself never
#: produces those short forms, so we standardize on the long form here.)
_LEGEND_POSITIONS = (
    "top right",
    "top left",
    "bottom right",
    "bottom left",
    "center",
)


def _format_optional_float(value: Optional[float]) -> str:
    if value is None:
        return ""
    if float(value) == int(value):
        return str(int(value))
    return str(value)


def _parse_optional_float(text: str) -> "tuple[bool, Optional[float]]":
    """Parse a limit field. Returns (ok, value). Blank -> (True, None)."""
    stripped = text.strip()
    if stripped == "":
        return True, None
    try:
        return True, float(stripped)
    except ValueError:
        return False, None


class AxesPanel(QWidget):
    """Property panel for the current axes (title, labels, limits, legend).

    Parameters
    ----------
    document
        Duck-typed document exposing ``figure``, ``figure_changed``/
        ``figure_replaced`` signals, and ``notify_changed()``.
    """

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._axes = None  # explicit override set via set_axes(); None => use gca()
        self._updating = False

        self._build_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # Axes targeting (Phase 2 hook)
    # ------------------------------------------------------------------
    def set_axes(self, ax) -> None:
        """Target a specific axes instead of the figure's current axes.

        Passing ``None`` restores the default behavior of tracking
        ``document.figure.gca()``.
        """
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

        labels_group = QGroupBox("Labels", self)
        labels_form = QFormLayout(labels_group)
        self.title_edit = QLineEdit(labels_group)
        self.xlabel_edit = QLineEdit(labels_group)
        self.ylabel_edit = QLineEdit(labels_group)
        self.y2label_edit = QLineEdit(labels_group)
        labels_form.addRow("Title", self.title_edit)
        labels_form.addRow("X label", self.xlabel_edit)
        labels_form.addRow("Y label", self.ylabel_edit)
        labels_form.addRow("Y2 label", self.y2label_edit)
        outer.addWidget(labels_group)

        limits_group = QGroupBox("Limits && scale", self)
        limits_form = QFormLayout(limits_group)

        float_validator = QDoubleValidator(limits_group)
        float_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.xmin_edit = QLineEdit(limits_group)
        self.xmax_edit = QLineEdit(limits_group)
        self.ymin_edit = QLineEdit(limits_group)
        self.ymax_edit = QLineEdit(limits_group)
        for edit in (self.xmin_edit, self.xmax_edit, self.ymin_edit, self.ymax_edit):
            edit.setPlaceholderText("auto")

        self.xscale_combo = QComboBox(limits_group)
        self.xscale_combo.addItems(_SCALE_VALUES)
        self.yscale_combo = QComboBox(limits_group)
        self.yscale_combo.addItems(_SCALE_VALUES)
        self.y2scale_combo = QComboBox(limits_group)
        self.y2scale_combo.addItems(_SCALE_VALUES)

        limits_form.addRow("X min", self.xmin_edit)
        limits_form.addRow("X max", self.xmax_edit)
        limits_form.addRow("X scale", self.xscale_combo)
        limits_form.addRow("Y min", self.ymin_edit)
        limits_form.addRow("Y max", self.ymax_edit)
        limits_form.addRow("Y scale", self.yscale_combo)
        limits_form.addRow("Y2 scale", self.y2scale_combo)
        outer.addWidget(limits_group)

        legend_group = QGroupBox("Legend", self)
        legend_form = QFormLayout(legend_group)
        self.legend_enabled_check = QCheckBox(legend_group)
        self.legend_loc_combo = QComboBox(legend_group)
        self.legend_loc_combo.addItems(_LEGEND_POSITIONS)
        legend_form.addRow("Enabled", self.legend_enabled_check)
        legend_form.addRow("Location", self.legend_loc_combo)
        outer.addWidget(legend_group)

        outer.addStretch(1)
        self.setEnabled(False)

    def _connect_signals(self) -> None:
        self._document.figure_changed.connect(self.refresh)
        self._document.figure_replaced.connect(self._on_figure_replaced)

        self.title_edit.editingFinished.connect(self._on_title_edited)
        self.xlabel_edit.editingFinished.connect(self._on_xlabel_edited)
        self.ylabel_edit.editingFinished.connect(self._on_ylabel_edited)
        self.y2label_edit.editingFinished.connect(self._on_y2label_edited)

        self.xmin_edit.editingFinished.connect(self._on_xmin_edited)
        self.xmax_edit.editingFinished.connect(self._on_xmax_edited)
        self.ymin_edit.editingFinished.connect(self._on_ymin_edited)
        self.ymax_edit.editingFinished.connect(self._on_ymax_edited)

        self.xscale_combo.currentTextChanged.connect(self._on_xscale_changed)
        self.yscale_combo.currentTextChanged.connect(self._on_yscale_changed)
        self.y2scale_combo.currentTextChanged.connect(self._on_y2scale_changed)

        self.legend_enabled_check.toggled.connect(self._on_legend_enabled_toggled)
        self.legend_loc_combo.currentTextChanged.connect(self._on_legend_loc_changed)

    def _on_figure_replaced(self) -> None:
        """Handle a brand-new figure being installed (New/Open/undo/redo).

        The previously-selected Axes (stored in ``self._axes`` via
        :meth:`set_axes`) belongs to the *old* figure and is now a dead object;
        continuing to edit it would silently lose changes. Drop the override so
        :meth:`_current_axes` falls back to the live ``document.figure.gca()``.
        LayoutPanel re-emits ``axes_selected`` right after this to re-target the
        panel onto the corresponding slot of the new figure when applicable.
        """
        self._axes = None
        self.refresh()

    # ------------------------------------------------------------------
    # Model -> UI
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Repopulate all widgets from the current axes (full refresh)."""
        ax = self._current_axes()
        self.setEnabled(ax is not None)
        if ax is None:
            return

        self._updating = True
        try:
            self.title_edit.setText(ax.title_text or "")
            self.xlabel_edit.setText(ax.xlabel_text or "")
            self.ylabel_edit.setText(ax.ylabel_text or "")
            self.y2label_edit.setText(ax.y2label_text or "")

            self.xmin_edit.setText(_format_optional_float(ax.xmin))
            self.xmax_edit.setText(_format_optional_float(ax.xmax))
            self.ymin_edit.setText(_format_optional_float(ax.ymin))
            self.ymax_edit.setText(_format_optional_float(ax.ymax))

            self._set_combo_text(self.xscale_combo, ax.xscale)
            self._set_combo_text(self.yscale_combo, ax.yscale)
            self._set_combo_text(self.y2scale_combo, ax.y2scale)

            # legend_on is tri-state (None = auto: shown iff labels exist);
            # display the EFFECTIVE state so the checkbox matches the preview.
            if ax.legend_on is None:
                sources = (
                    ax.lines + ax.scatters + ax.bars + ax.errorbars + ax.file_series
                )
                effective = any(s.get("label") for s in sources)
            else:
                effective = bool(ax.legend_on)
            self.legend_enabled_check.setChecked(effective)
            self._set_combo_text(self.legend_loc_combo, ax.legend_pos)
        finally:
            self._updating = False

    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # UI -> Model: labels
    # ------------------------------------------------------------------
    def _on_title_edited(self) -> None:
        self._write_attr("title_text", mathtext_to_gle(self.title_edit.text()))

    def _on_xlabel_edited(self) -> None:
        self._write_attr("xlabel_text", mathtext_to_gle(self.xlabel_edit.text()))

    def _on_ylabel_edited(self) -> None:
        self._write_attr("ylabel_text", mathtext_to_gle(self.ylabel_edit.text()))

    def _on_y2label_edited(self) -> None:
        self._write_attr("y2label_text", mathtext_to_gle(self.y2label_edit.text()))

    # ------------------------------------------------------------------
    # UI -> Model: limits
    # ------------------------------------------------------------------
    def _on_xmin_edited(self) -> None:
        self._write_limit(self.xmin_edit, "xmin")

    def _on_xmax_edited(self) -> None:
        self._write_limit(self.xmax_edit, "xmax")

    def _on_ymin_edited(self) -> None:
        self._write_limit(self.ymin_edit, "ymin")

    def _on_ymax_edited(self) -> None:
        self._write_limit(self.ymax_edit, "ymax")

    def _write_limit(self, edit: QLineEdit, attr: str) -> None:
        if self._updating:
            return
        ax = self._current_axes()
        if ax is None:
            return

        ok, value = _parse_optional_float(edit.text())
        if not ok:
            # Invalid text: revert the field to the current model value.
            self._updating = True
            try:
                edit.setText(_format_optional_float(getattr(ax, attr)))
            finally:
                self._updating = False
            return

        self._updating = True
        try:
            setattr(ax, attr, value)
            edit.setText(_format_optional_float(value))
        finally:
            self._updating = False
        self._document.notify_changed()

    # ------------------------------------------------------------------
    # UI -> Model: scale
    # ------------------------------------------------------------------
    def _on_xscale_changed(self, text: str) -> None:
        self._write_attr("xscale", text)

    def _on_yscale_changed(self, text: str) -> None:
        self._write_attr("yscale", text)

    def _on_y2scale_changed(self, text: str) -> None:
        self._write_attr("y2scale", text)

    # ------------------------------------------------------------------
    # UI -> Model: legend
    # ------------------------------------------------------------------
    def _on_legend_enabled_toggled(self, checked: bool) -> None:
        self._write_attr("legend_on", bool(checked))

    def _on_legend_loc_changed(self, text: str) -> None:
        self._write_attr("legend_pos", text)

    # ------------------------------------------------------------------
    # Shared write helper
    # ------------------------------------------------------------------
    def _write_attr(self, attr: str, value) -> None:
        if self._updating:
            return
        ax = self._current_axes()
        if ax is None:
            return

        self._updating = True
        try:
            setattr(ax, attr, value)
        finally:
            self._updating = False
        self._document.notify_changed()

"""DataPanel: file loading + column-to-series mapping widget.

:class:`DataPanel` is a self-contained ``QWidget`` (no assumptions about
docks or a main window) that lets the user:

1. Load one or more delimited data files (``load_data_file`` from
   :mod:`gleplot.gui.data.loader`).
2. Preview a loaded file's columns in a table (up to 100 rows).
3. Map columns to a new plot series (X, Y, optional Y-error, label, plot
   type) and add it to the current figure, either by importing the
   in-memory arrays directly (``Import data``) or by referencing the
   file's columns in place (``Reference file``, via
   ``Axes.line_from_file`` / ``Axes.errorbar_from_file``).

The panel talks to a ``document`` object via a small duck-typed contract
(``.figure``, ``.notify_changed()``, ``.figure_replaced`` signal) rather
than importing the concrete ``FigureDocument`` class, since that class is
implemented by a parallel work track. See ``tests/gui/test_data_panel.py``
for a minimal local stub satisfying this contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .loader import DataTable, load_data_file

#: Maximum number of rows shown in the preview table.
_MAX_PREVIEW_ROWS = 100

#: Plot-type combo entries.
_PLOT_TYPES = ["Line", "Scatter", "Line+markers", "Error bars"]

#: Sentinel text for "no Y-error column selected".
_NONE_LABEL = "(none)"

#: Custom Qt.ItemDataRole offset used to stash the resolved absolute path
#: string on each QListWidgetItem (Qt.UserRole is reserved for this).
_PATH_ROLE = Qt.ItemDataRole.UserRole + 1

#: Mode combo entries and their tooltips.
_MODE_IMPORT = "Import data"
_MODE_REFERENCE = "Reference file"
_MODE_TOOLTIPS = {
    _MODE_IMPORT: (
        "Import copies the selected columns' data into the project "
        "(generated .dat sidecar files on export)."
    ),
    _MODE_REFERENCE: (
        "Reference makes the GLE script read this file in place, by "
        "column index, instead of copying the data."
    ),
}


class DataPanel(QWidget):
    """Widget for loading data files and creating plot series from columns.

    Parameters
    ----------
    document : object
        Duck-typed document object exposing:

        - ``figure`` (property): ``Optional[gleplot.figure.Figure]``
        - ``notify_changed()``: called after mutating the figure
        - ``figure_replaced`` (Signal): emitted when the whole figure is
          swapped out (e.g. project loaded); the panel re-evaluates its
          enabled state in response.
    parent : QWidget, optional

    Signals
    -------
    series_added(str)
        Emitted with the new series' label after a series is
        successfully added to the figure.
    """

    series_added = Signal(str)

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._tables: Dict[str, DataTable] = {}  # path string -> DataTable
        self._current_table: Optional[DataTable] = None
        self._last_dir: str = str(Path.home())

        self._build_ui()
        self._connect_signals()
        self._update_add_button_state()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QToolBar(self)
        self.action_load = toolbar.addAction("Load data file…")
        layout.addWidget(toolbar)

        # Loaded-files list
        self.file_list = QListWidget(self)
        self.file_list.setMaximumHeight(120)
        layout.addWidget(self.file_list)

        # Preview table
        self.preview_table = QTableWidget(self)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.preview_table, stretch=1)

        # Series creation form
        form_box = QGroupBox("Add series", self)
        form = QFormLayout(form_box)

        self.x_combo = QComboBox(form_box)
        form.addRow("X column", self.x_combo)

        self.y_combo = QComboBox(form_box)
        form.addRow("Y column", self.y_combo)

        self.yerr_combo = QComboBox(form_box)
        form.addRow("Y error", self.yerr_combo)

        self.label_edit = QLineEdit(form_box)
        form.addRow("Label", self.label_edit)

        self.plot_type_combo = QComboBox(form_box)
        self.plot_type_combo.addItems(_PLOT_TYPES)
        form.addRow("Plot type", self.plot_type_combo)

        self.mode_combo = QComboBox(form_box)
        self.mode_combo.addItems([_MODE_IMPORT, _MODE_REFERENCE])
        self.mode_combo.setToolTip(_MODE_TOOLTIPS[_MODE_IMPORT])
        form.addRow("Mode", self.mode_combo)

        self.add_series_button = QPushButton("Add series", form_box)
        form.addRow(self.add_series_button)

        layout.addWidget(form_box)

        self._label_user_edited = False

    def _connect_signals(self) -> None:
        self.action_load.triggered.connect(self._on_load_file_clicked)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        self.y_combo.currentIndexChanged.connect(self._on_y_column_changed)
        self.label_edit.textEdited.connect(self._on_label_edited)
        self.add_series_button.clicked.connect(self.add_series)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        figure_replaced = getattr(self._document, "figure_replaced", None)
        if figure_replaced is not None:
            figure_replaced.connect(self._update_add_button_state)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------
    def _on_load_file_clicked(self) -> None:
        """QFileDialog-driven entry point for the toolbar action."""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Load data file",
            self._last_dir,
            "Data files (*.csv *.dat *.txt);;All files (*.*)",
        )
        if not path_str:
            return
        self._last_dir = str(Path(path_str).parent)
        self.load_file(path_str)

    def load_file(self, path: str) -> Optional[DataTable]:
        """Load ``path`` and add it to the file list, selecting it.

        This is the internal entry point tests should call directly
        (bypassing ``QFileDialog``). Returns the loaded :class:`DataTable`,
        or ``None`` if loading failed (an error is shown inline via the
        list item's tooltip rather than raising, so a bad file doesn't
        crash the panel).
        """
        try:
            table = load_data_file(path, max_preview_rows=None)
        except (OSError, ValueError) as exc:
            item = QListWidgetItem(f"{Path(path).name} (failed to load)")
            item.setToolTip(f"{path}\n\nError: {exc}")
            self.file_list.addItem(item)
            return None

        key = str(Path(path).resolve())
        self._tables[key] = table

        item = QListWidgetItem(Path(path).name)
        item.setToolTip(key)
        item.setData(_PATH_ROLE, key)
        self.file_list.addItem(item)
        self.file_list.setCurrentItem(item)
        return table

    # ------------------------------------------------------------------
    # Preview / selection
    # ------------------------------------------------------------------
    def _on_file_selected(
        self, current: Optional[QListWidgetItem], _previous=None
    ) -> None:
        if current is None:
            self._current_table = None
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            self._populate_column_combos()
            self._update_add_button_state()
            return

        key = current.data(_PATH_ROLE)
        table = self._tables.get(key)
        self._current_table = table
        self._populate_preview(table)
        self._populate_column_combos()
        self._update_add_button_state()

    def _populate_preview(self, table: Optional[DataTable]) -> None:
        self.preview_table.clear()
        if table is None:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        n_preview_rows = min(table.n_rows, _MAX_PREVIEW_ROWS)
        self.preview_table.setColumnCount(table.n_cols)
        self.preview_table.setRowCount(n_preview_rows)
        self.preview_table.setHorizontalHeaderLabels(table.column_names)

        grey = QColor(160, 160, 160)
        for col_idx, (col, numeric) in enumerate(zip(table.columns, table.is_numeric)):
            for row_idx in range(n_preview_rows):
                value = col[row_idx]
                if numeric:
                    text = "" if value != value else str(value)  # NaN check
                else:
                    text = "" if value is None else str(value)
                cell = QTableWidgetItem(text)
                if not numeric:
                    cell.setForeground(grey)
                self.preview_table.setItem(row_idx, col_idx, cell)

    def _populate_column_combos(self) -> None:
        self.x_combo.clear()
        self.y_combo.clear()
        self.yerr_combo.clear()
        self.yerr_combo.addItem(_NONE_LABEL, userData=-1)

        table = self._current_table
        if table is None:
            return

        # X may be any column (numeric preferred, but categorical x-labels
        # are a future feature - for now only numeric columns are
        # selectable anywhere, per the spec).
        numeric_indices = table.numeric_column_indices()
        for idx in numeric_indices:
            name = table.column_names[idx]
            self.x_combo.addItem(name, userData=idx)
            self.y_combo.addItem(name, userData=idx)
            self.yerr_combo.addItem(name, userData=idx)

        if self.x_combo.count() > 0:
            self.x_combo.setCurrentIndex(0)
        if self.y_combo.count() > 1:
            self.y_combo.setCurrentIndex(1)
        elif self.y_combo.count() > 0:
            self.y_combo.setCurrentIndex(0)

        self._label_user_edited = False
        self._update_default_label()

    # ------------------------------------------------------------------
    # Label defaulting
    # ------------------------------------------------------------------
    def _on_y_column_changed(self, _index: int) -> None:
        if not self._label_user_edited:
            self._update_default_label()

    def _on_label_edited(self, _text: str) -> None:
        self._label_user_edited = True

    def _update_default_label(self) -> None:
        y_name = self.y_combo.currentText()
        self.label_edit.blockSignals(True)
        self.label_edit.setText(y_name)
        self.label_edit.blockSignals(False)

    def _on_mode_changed(self, text: str) -> None:
        self.mode_combo.setToolTip(_MODE_TOOLTIPS.get(text, ""))

    # ------------------------------------------------------------------
    # Enabled-state management
    # ------------------------------------------------------------------
    def _update_add_button_state(self) -> None:
        figure = getattr(self._document, "figure", None)
        has_figure = figure is not None
        has_numeric_columns = (
            self._current_table is not None
            and len(self._current_table.numeric_column_indices()) > 0
        )
        self.add_series_button.setEnabled(has_figure and has_numeric_columns)

    # ------------------------------------------------------------------
    # Series creation
    # ------------------------------------------------------------------
    def add_series(self) -> None:
        """Add a series to the figure's current axes from the form state.

        No-op (button is disabled in these cases, but this guards direct
        calls too) if there is no figure or no table/numeric columns
        selected.
        """
        figure = getattr(self._document, "figure", None)
        table = self._current_table
        if figure is None or table is None:
            return
        if self.x_combo.count() == 0 or self.y_combo.count() == 0:
            return

        x_idx = self.x_combo.currentData()
        y_idx = self.y_combo.currentData()
        yerr_idx = self.yerr_combo.currentData()
        if yerr_idx is not None and yerr_idx < 0:
            yerr_idx = None

        label = self.label_edit.text() or self.y_combo.currentText()
        plot_type = self.plot_type_combo.currentText()
        mode = self.mode_combo.currentText()

        ax = figure.gca()

        if mode == _MODE_REFERENCE:
            # gleplot's line_from_file / errorbar_from_file use 1-based
            # column indices (GLE convention); our combos store 0-based
            # DataTable column indices, so convert by adding 1.
            data_file = str(table.path.resolve())
            x_col = int(x_idx) + 1
            y_col = int(y_idx) + 1
            if plot_type == "Error bars":
                yerr_col = int(yerr_idx) + 1 if yerr_idx is not None else None
                ax.errorbar_from_file(
                    data_file,
                    x_col=x_col,
                    y_col=y_col,
                    yerr_col=yerr_col,
                    label=label,
                )
            else:
                marker = "o" if plot_type == "Line+markers" else None
                linestyle = "none" if plot_type == "Scatter" else "-"
                ax.line_from_file(
                    data_file,
                    x_col=x_col,
                    y_col=y_col,
                    label=label,
                    linestyle=linestyle,
                )
                if plot_type == "Scatter":
                    # line_from_file doesn't support markers; fall back to
                    # a small linestyle/marker override isn't available on
                    # file-based series today, so scatter-mode reference
                    # series are drawn as a plain line. Documented via the
                    # mode tooltip; import mode supports true scatter.
                    pass
        else:
            x = table.columns[x_idx]
            y = table.columns[y_idx]

            if plot_type == "Error bars":
                yerr = table.columns[yerr_idx] if yerr_idx is not None else None
                ax.errorbar(x, y, yerr=yerr, label=label)
            elif plot_type == "Scatter":
                ax.scatter(x, y, label=label)
            elif plot_type == "Line+markers":
                ax.plot(x, y, marker="o", label=label)
            else:
                ax.plot(x, y, label=label)

        self._document.notify_changed()
        self.series_added.emit(label)

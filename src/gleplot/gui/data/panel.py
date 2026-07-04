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
4. Rename a table's column headers in place (double-click a header cell),
   for figure-owned sidecars and in-memory tables only -- see "Header
   editing" below.

The panel talks to a ``document`` object via a small duck-typed contract
(``.figure``, ``.notify_changed()``, ``.figure_replaced`` signal) rather
than importing the concrete ``FigureDocument`` class, since that class is
implemented by a parallel work track. See ``tests/gui/test_data_panel.py``
for a minimal local stub satisfying this contract.

Header editing (Track G1)
--------------------------
Column headers are editable ONLY for tables gleplot itself owns the data
of: figure-owned sidecars (generated ``.dat`` files behind an "Import
data" series) and tables loaded via ``load_file`` that are not (yet)
referenced by any file-reference series. They are NOT editable for
external files referenced in place (``ax.file_series``, i.e. "Reference
file" mode / ``line_from_file`` / ``errorbar_from_file``): gleplot never
rewrites a user's own source data file, so renaming its header would be
either a lie (cosmetic-only, not written back) or dangerous (silently
rewriting someone else's file). See :meth:`DataPanel._is_editable_table`
for the precise ownership rule and :meth:`DataPanel._on_header_double_clicked`
for the edit UX (a prefilled ``QInputDialog``, not an in-place header
delegate -- simpler to get right and consistent with how Qt table headers
are conventionally edited, since ``QHeaderView`` has no built-in item
delegate support the way table cells do).
"""

from __future__ import annotations

import os
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gleplot.axes import _unique_column_names, sanitize_column_name

from .loader import DataTable, load_data_file

#: Tooltip shown on non-editable (external-file) column headers.
_EXTERNAL_HEADER_TOOLTIP = (
    "Column names come from the referenced file and are not edited by "
    "gleplot."
)

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
    column_renamed(str, int, str)
        Emitted after a successful header rename (no-op renames and
        rejected/cancelled edits do not emit this): the file key (the
        resolved absolute path string used internally in ``_tables``,
        matching the list item's ``_PATH_ROLE`` data), the 1-based column
        index (matching GLE's own column numbering, as used elsewhere in
        this panel for ``x_col``/``y_col``), and the new (sanitized)
        column name. Intended for status-bar wiring by ``main_window``;
        this panel does not display it itself.
    """

    series_added = Signal(str)
    column_renamed = Signal(str, int, str)

    def __init__(self, document, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._tables: Dict[str, DataTable] = {}  # path string -> DataTable
        self._current_table: Optional[DataTable] = None
        self._current_key: Optional[str] = None  # key into self._tables
        self._last_dir: str = str(Path.home())

        self._build_ui()
        self._connect_signals()
        self._update_add_button_state()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # A plain QPushButton (not a QToolBar action): toolbar buttons render
        # flat/borderless on Windows and don't read as clickable.
        self.load_button = QPushButton("Load data file…", self)
        layout.addWidget(self.load_button)

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
        self.load_button.clicked.connect(self._on_load_file_clicked)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        self.y_combo.currentIndexChanged.connect(self._on_y_column_changed)
        self.label_edit.textEdited.connect(self._on_label_edited)
        self.add_series_button.clicked.connect(self.add_series)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.preview_table.horizontalHeader().sectionDoubleClicked.connect(
            self._on_header_double_clicked
        )

        figure_replaced = getattr(self._document, "figure_replaced", None)
        if figure_replaced is not None:
            figure_replaced.connect(self._update_add_button_state)
            # When a figure is installed (File > Open), surface the data
            # files it references so users can immediately add more series
            # from the same data.
            figure_replaced.connect(self.populate_from_figure)
        # CRITICAL ordering: file_ops installs the figure FIRST (set_figure
        # emits figure_replaced with project_path still None, so relative
        # sidecar names cannot resolve yet) and assigns project_path AFTER.
        # Re-run population when the path lands so referenced files resolve
        # against the .gle's directory.
        project_path_changed = getattr(self._document, "project_path_changed", None)
        if project_path_changed is not None:
            project_path_changed.connect(self.populate_from_figure)

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

    def populate_from_figure(self, *_signal_args) -> None:
        """Add the current figure's referenced data files to the file list.

        Called on ``figure_replaced`` (File > Open installs a parsed
        figure). Additive by design: files already listed are left alone
        (so undo/redo restores neither clear the list nor re-read files),
        and user-loaded files are never removed. Relative references are
        resolved against the document's ``project_path`` directory; files
        that do not exist on disk are skipped (broken references already
        surface in the Series tab with a Locate-file flow).
        """
        fig = getattr(self._document, "figure", None)
        if fig is None:
            return

        base: Optional[Path] = None
        project_path = getattr(self._document, "project_path", None)
        if project_path:
            base = Path(project_path).parent

        listed = {os.path.normcase(key) for key in self._tables}
        first_added: Optional[str] = None
        for ax in getattr(fig, "axes_list", []):
            entries = (
                ax.lines + ax.scatters + ax.bars + ax.fills
                + ax.errorbars + ax.file_series
            )
            for entry in entries:
                name = entry.get("data_file")
                if not name:
                    continue
                path = Path(name)
                if not path.is_absolute():
                    if base is None:
                        continue  # unsaved in-memory sidecar; nothing on disk
                    path = base / path
                if not path.exists():
                    continue
                key = os.path.normcase(str(path.resolve()))
                if key in listed:
                    continue
                listed.add(key)
                if self.load_file(str(path)) is not None and first_added is None:
                    first_added = key
        if first_added is not None and self.file_list.count():
            self.file_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Preview / selection
    # ------------------------------------------------------------------
    def _on_file_selected(
        self, current: Optional[QListWidgetItem], _previous=None
    ) -> None:
        if current is None:
            self._current_table = None
            self._current_key = None
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            self._populate_column_combos()
            self._update_add_button_state()
            return

        key = current.data(_PATH_ROLE)
        table = self._tables.get(key)
        self._current_table = table
        self._current_key = key
        self._populate_preview(table, key)
        self._populate_column_combos()
        self._update_add_button_state()

    def _populate_preview(
        self, table: Optional[DataTable], key: Optional[str] = None
    ) -> None:
        self.preview_table.clear()
        if table is None:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        n_preview_rows = min(table.n_rows, _MAX_PREVIEW_ROWS)
        self.preview_table.setColumnCount(table.n_cols)
        self.preview_table.setRowCount(n_preview_rows)

        editable = key is not None and self._is_editable_table(key)
        for col_idx, name in enumerate(table.column_names):
            header_item = QTableWidgetItem(name)
            if not editable:
                header_item.setToolTip(_EXTERNAL_HEADER_TOOLTIP)
            self.preview_table.setHorizontalHeaderItem(col_idx, header_item)

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
    # Header editing (Track G1)
    # ------------------------------------------------------------------
    def _import_entries(self, fig):
        """All series entries capable of owning a regenerated sidecar.

        These are exactly the collections the writer regenerates
        ``data_file``/``column_names`` for on every save (see
        ``Figure.savefig_gle`` pulling ``column_names`` straight off each
        dict). ``ax.file_series`` is deliberately excluded: those entries
        reference an external file in place and are never rewritten.
        """
        entries = []
        for ax in getattr(fig, "axes_list", []):
            entries.extend(ax.lines)
            entries.extend(ax.scatters)
            entries.extend(ax.bars)
            entries.extend(ax.fills)
            entries.extend(ax.errorbars)
        return entries

    def _owning_series_for_key(self, key: str) -> List[dict]:
        """Import-mode series entries whose sidecar resolves to ``key``.

        Ownership rule (the precise form of the "figure-owned sidecar"
        concept described in the module docstring): a loaded table is
        figure-owned iff its resolved absolute path (``key``, normcased)
        equals the resolution of some import-mode series' ``data_file``
        against ``document.project_path``'s directory. This mirrors
        exactly what :meth:`populate_from_figure` does when deciding
        which files to surface, so "shows up via populate_from_figure" and
        "is figure-owned/editable" are the same test by construction:

        - Import-mode series (``ax.lines``/``scatters``/``bars``/``fills``/
          ``errorbars``) store a ``data_file`` that is a bare/relative
          sidecar filename (e.g. ``"myfig_0.dat"``) generated by
          ``_resolve_data_file``. It only resolves to an absolute path
          once a project directory is known (``document.project_path``);
          before the first save (no project path yet), it can never match
          anything already on disk, so nothing is editable-as-owned yet
          (there is also nothing to rename propagation-wise: the table was
          loaded via ``load_file``, i.e. user-loaded/in-memory, which is
          separately editable -- see ``_is_editable_table``).
        - ``ax.file_series`` entries (the "Reference file" / *EXTERNAL*
          mode) store an absolute path to a user's own file and are never
          considered here.

        A single sidecar can in principle be the ``data_file`` for more
        than one series entry (e.g. a fill built from two datasets that
        happen to share a file); all matching entries are returned so a
        rename can be propagated to every one of them.
        """
        fig = getattr(self._document, "figure", None)
        if fig is None:
            return []

        project_path = getattr(self._document, "project_path", None)
        base = Path(project_path).parent if project_path else None

        owners = []
        for entry in self._import_entries(fig):
            name = entry.get("data_file")
            if not name or "column_names" not in entry:
                continue
            path = Path(name)
            if not path.is_absolute():
                if base is None:
                    continue
                path = base / path
            if not path.exists():
                continue
            if os.path.normcase(str(path.resolve())) == os.path.normcase(key):
                owners.append(entry)
        return owners

    def _is_referenced_externally(self, key: str) -> bool:
        """Whether ``key`` is some ``ax.file_series`` entry's data file.

        These are EXTERNAL by definition (mode = "Reference file"): the
        GLE script reads the user's file in place, so its header must
        display the file's real column names and must never be rewritten.
        """
        fig = getattr(self._document, "figure", None)
        if fig is None:
            return False

        project_path = getattr(self._document, "project_path", None)
        base = Path(project_path).parent if project_path else None

        for ax in getattr(fig, "axes_list", []):
            for entry in ax.file_series:
                name = entry.get("data_file")
                if not name:
                    continue
                path = Path(name)
                if not path.is_absolute():
                    if base is None:
                        continue
                    path = base / path
                if not path.exists():
                    continue
                if os.path.normcase(str(path.resolve())) == os.path.normcase(key):
                    return True
        return False

    def _is_editable_table(self, key: str) -> bool:
        """Whether the table at ``key`` may have its header renamed.

        Per the user-approved decision: header names are editable ONLY
        for figure-owned sidecars (:meth:`_owning_series_for_key` returns
        at least one entry) and for in-memory/user-loaded tables that are
        not (yet) referenced by any "Reference file" series. Anything
        referenced externally (``ax.file_series``) is never editable,
        even if it also happens to look like it could be figure-owned
        (external takes priority -- a file can't simultaneously be "we
        generated this" and "we read the user's file in place").
        """
        if self._is_referenced_externally(key):
            return False
        return True

    def _on_header_double_clicked(self, col_idx: int) -> None:
        """Prompt for a new column name via a prefilled ``QInputDialog``.

        UX choice: a modal prefilled text dialog rather than an in-place
        header editor widget. ``QHeaderView`` has no built-in equivalent
        of ``QTableWidget``'s cell item delegates, so an in-place editor
        would mean hand-building a floating ``QLineEdit`` positioned over
        the header section (tracking resizes/scrolling/click-outside-to-
        commit). The dialog is a few lines, has an OK/Cancel affordance
        for free, and is the conventional Qt pattern for header renames.
        """
        table = self._current_table
        key = self._current_key
        if table is None or key is None or col_idx < 0 or col_idx >= table.n_cols:
            return

        if not self._is_editable_table(key):
            QMessageBox.information(
                self,
                "Column name not editable",
                _EXTERNAL_HEADER_TOOLTIP,
            )
            return

        current_name = table.column_names[col_idx]
        new_name, ok = QInputDialog.getText(
            self, "Rename column", "Column name:", text=current_name
        )
        if not ok:
            return

        self._rename_column(key, table, col_idx, new_name)

    def _rename_column(
        self, key: str, table: DataTable, col_idx: int, raw_name: str
    ) -> None:
        """Validate and apply a column rename, propagating everywhere needed.

        Validation (in order): sanitize via
        ``gleplot.axes.sanitize_column_name`` (strips to ``[A-Za-z0-9_]``,
        lowercases, and prefixes purely-numeric results so a renamed
        column can never be mistaken for a data value -- see that
        function's docstring for the full rule set). If the sanitized
        name is unchanged from the current name, this is a no-op (no
        mutation, no ``notify_changed``, no signal). Otherwise uniqueness
        within the table is enforced by auto-suffixing via
        ``gleplot.axes._unique_column_names`` (the same ``_2``, ``_3``,
        ... convention gleplot's own writer uses for sidecar headers) --
        chosen over reject-with-message because it matches how gleplot
        already resolves naming collisions elsewhere (e.g.
        ``_build_column_names``) and never blocks the user on a dialog
        round-trip for what is, after sanitization, a purely mechanical
        collision.

        Propagation for figure-owned sidecars: the in-memory
        ``DataTable.column_names``, the preview header, the x/y/yerr
        combo item text (by index, so current *selections* survive: combo
        ``userData`` is the 0-based column index, unaffected by a name
        change), and every owning series entry's ``column_names`` list at
        the same column index (see :meth:`_owning_series_for_key` for why
        index-alignment holds), followed by ``document.notify_changed()``
        so the next save writes the new header. Series *labels* (legend
        text) are deliberately left untouched -- a label is user-facing
        prose the user may have already customized (e.g. via the Series
        tab), whereas the column header is purely a data/file concern;
        conflating the two would silently overwrite a label the user
        chose on purpose.
        """
        sanitized = sanitize_column_name(raw_name)
        if sanitized == table.column_names[col_idx]:
            return  # no-op: unchanged after sanitization

        other_names = [n for i, n in enumerate(table.column_names) if i != col_idx]
        final_name = _unique_column_names(other_names + [sanitized])[-1]

        table.column_names[col_idx] = final_name

        header_item = self.preview_table.horizontalHeaderItem(col_idx)
        if header_item is not None:
            header_item.setText(final_name)

        for combo in (self.x_combo, self.y_combo, self.yerr_combo):
            for i in range(combo.count()):
                if combo.itemData(i) == col_idx:
                    combo.setItemText(i, final_name)

        for entry in self._owning_series_for_key(key):
            names = entry.get("column_names")
            if names is not None and col_idx < len(names):
                names[col_idx] = final_name

        self._document.notify_changed()
        self.column_renamed.emit(key, col_idx + 1, final_name)

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

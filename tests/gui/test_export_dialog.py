"""Tests for :mod:`gleplot.gui.export_dialog` (Track H).

Drives the dialog programmatically (no real dialogs shown) by setting
widget state directly and invoking the private export slot, matching the
pattern used by ``test_preview.py`` for driving Qt objects synchronously.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.compiler import find_gle
from gleplot.gui.document import FigureDocument
from gleplot.gui.export_dialog import ExportDialog

_GLE_AVAILABLE = find_gle() is not None


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def scratch_settings(tmp_path):
    ini_path = tmp_path / "export_settings.ini"
    return QSettings(str(ini_path), QSettings.Format.IniFormat)


def _make_document():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([1, 2, 3], [1, 4, 9], label="sq")
    doc.set_figure(fig)
    return doc


def _set_path(dialog, path):
    dialog._path_edit.setText(str(path))


# ----------------------------------------------------------------------
# FIX 9: export dialog and ErrorPanel share one GLEError formatter.
# ----------------------------------------------------------------------
def test_export_dialog_uses_shared_gle_error_formatter(qapp):
    """ExportDialog._format_compile_error renders each error via the shared
    format_gle_error helper (same canonical format as ErrorPanel)."""
    from gleplot.compiler import GLECompileError, GLEError
    from gleplot.gui.error_panel import ErrorPanel, format_gle_error

    err = GLEError(file="foo.gle", line=7, column=3, message="bad token")
    exc = GLECompileError("compile failed", errors=[err], raw_output="raw")

    formatted = ExportDialog._format_compile_error(exc)

    # The per-error line matches the canonical helper output exactly.
    canonical = format_gle_error(err)
    assert canonical == "line 7, col 3: bad token"
    assert canonical in formatted
    # And the same helper backs ErrorPanel's own per-error rendering.
    assert ErrorPanel._format_error(err) == canonical


# ----------------------------------------------------------------------
# Construction guards
# ----------------------------------------------------------------------
def test_export_button_disabled_when_no_figure(qapp, scratch_settings):
    doc = FigureDocument()  # figure is None
    dialog = ExportDialog(doc, settings=scratch_settings)
    assert dialog._export_button.isEnabled() is False


def test_export_button_enabled_when_figure_present(qapp, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)
    assert dialog._export_button.isEnabled() is True


# ----------------------------------------------------------------------
# Suffix <-> combo sync
# ----------------------------------------------------------------------
def test_changing_combo_rewrites_path_suffix(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    _set_path(dialog, tmp_path / "plot.pdf")
    dialog._format_combo.setCurrentText("png")

    assert dialog._path_edit.text().endswith(".png")
    assert dialog.selected_format == "png"


def test_setting_path_with_known_suffix_selects_combo(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    _set_path(dialog, tmp_path / "plot.svg")

    assert dialog._format_combo.currentText() == "svg"
    assert dialog.selected_format == "svg"


def test_dpi_enabled_only_for_raster_formats(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    dialog._format_combo.setCurrentText("png")
    assert dialog._dpi_spin.isEnabled() is True

    dialog._format_combo.setCurrentText("pdf")
    assert dialog._dpi_spin.isEnabled() is False

    dialog._format_combo.setCurrentText("jpg")
    assert dialog._dpi_spin.isEnabled() is True

    dialog._format_combo.setCurrentText("svg")
    assert dialog._dpi_spin.isEnabled() is False


# ----------------------------------------------------------------------
# Export behavior
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_png_produces_file(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.png"
    _set_path(dialog, target)
    dialog._dpi_spin.setValue(100)

    dialog._on_export_clicked()

    assert target.exists(), dialog._error_box.toPlainText()
    assert dialog.selected_path == target
    assert dialog.result() == 1  # QDialog.Accepted


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_pdf_produces_file(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.pdf"
    _set_path(dialog, target)

    dialog._on_export_clicked()

    assert target.exists(), dialog._error_box.toPlainText()


def test_export_gle_produces_script_only(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.gle"
    _set_path(dialog, target)

    dialog._on_export_clicked()

    assert target.exists(), dialog._error_box.toPlainText()
    assert dialog.result() == 1


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_folder_bundle_creates_gleplot_dir(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "bundle.pdf"
    _set_path(dialog, target)
    dialog._folder_check.setChecked(True)

    dialog._on_export_clicked()

    bundle_dir = tmp_path / "bundle.gleplot"
    assert bundle_dir.exists(), dialog._error_box.toPlainText()
    assert bundle_dir.is_dir()
    assert dialog.folder_bundle is True


def test_export_failure_shows_errors_and_does_not_close(qapp, tmp_path, scratch_settings, monkeypatch):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "fail.pdf"
    _set_path(dialog, target)

    # Force a compile failure regardless of GLE availability by making
    # Figure.savefig raise GLECompileError.
    from gleplot.compiler import GLECompileError
    from gleplot.figure import Figure

    def broken_savefig(self, *args, **kwargs):
        raise GLECompileError("boom", errors=[], raw_output="boom output")

    monkeypatch.setattr(Figure, "savefig", broken_savefig)

    dialog._on_export_clicked()

    assert not target.exists()
    # Widget visibility only reflects reality once the dialog itself is
    # shown; here we assert on the explicit "should be shown" flag instead
    # (setVisible(True) was called) plus the actual error text.
    assert dialog._error_box.isHidden() is False
    assert "boom" in dialog._error_box.toPlainText()
    assert dialog.result() != 1  # not accepted


# ----------------------------------------------------------------------
# Snapshot rule: live figure must not be mutated by export
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_does_not_mutate_live_figure(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    before = doc.figure.to_dict()

    dialog = ExportDialog(doc, settings=scratch_settings)
    target = tmp_path / "snapshot_check.pdf"
    _set_path(dialog, target)

    dialog._on_export_clicked()

    after = doc.figure.to_dict()
    assert before == after
    assert target.exists()

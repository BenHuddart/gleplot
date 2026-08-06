"""Tests for :mod:`gleplot.gui.export_dialog` (Track H).

Drives the dialog programmatically (no real dialogs shown) by setting
widget state directly and invoking the private export slot, matching the
pattern used by ``test_preview.py`` for driving Qt objects synchronously.
"""

import os
import sys
import warnings
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.cairo_support import CAIRO_SAFE_FONT
from gleplot.compiler import find_gle
from gleplot.gui.compile_core import CompileOutcome
from gleplot.gui.document import FigureDocument
from gleplot.gui.export_dialog import ExportDialog

_GLE_AVAILABLE = find_gle() is not None


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _wait_until(predicate, timeout_ms=10000):
    """Spin the Qt event loop until ``predicate()`` is true or timeout.

    Export now compiles asynchronously (Track G3): ``_on_export_clicked()``
    returns as soon as the compile job is *launched*, not once it finishes.
    Tests that assert on the exported file (or on error/cancel state) must
    pump the event loop until the job's ``finished`` signal has actually been
    delivered -- this mirrors ``tests/gui/test_preview.py``'s helper of the
    same name and purpose. Returns True if the predicate became true, False
    on timeout.
    """
    loop = QEventLoop()
    timed_out = {"value": False}

    poll = QTimer()
    poll.setInterval(20)

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.setInterval(timeout_ms)

    def check():
        if predicate():
            loop.quit()

    def on_deadline():
        timed_out["value"] = True
        loop.quit()

    poll.timeout.connect(check)
    deadline.timeout.connect(on_deadline)
    poll.start()
    deadline.start()
    if predicate():
        return True
    loop.exec()
    poll.stop()
    deadline.stop()
    return not timed_out["value"]


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
    assert _wait_until(lambda: dialog._runner is None, 10000)

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
    assert _wait_until(lambda: dialog._runner is None, 10000)

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
    assert _wait_until(lambda: dialog._runner is None, 10000)

    bundle_dir = tmp_path / "bundle.gleplot"
    assert bundle_dir.exists(), dialog._error_box.toPlainText()
    assert bundle_dir.is_dir()
    assert dialog.folder_bundle is True


def test_export_failure_shows_errors_and_does_not_close(
    qapp, tmp_path, scratch_settings, monkeypatch
):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "fail.pdf"
    _set_path(dialog, target)

    # Force a failure deterministically, regardless of GLE availability, by
    # making the GLE-discovery the compile step relies on fail. (Export no
    # longer calls Figure.savefig() for compiled formats -- see the module
    # docstring -- so monkeypatching that is no longer a valid way to force
    # a failure; find_gle() is the equivalent unconditional choke point.)
    import gleplot.gui.export_dialog as export_dialog_module

    monkeypatch.setattr(export_dialog_module, "find_gle", lambda: None)

    dialog._on_export_clicked()

    assert not target.exists()
    # Widget visibility only reflects reality once the dialog itself is
    # shown; here we assert on the explicit "should be shown" flag instead
    # (setVisible(True) was called) plus the actual error text.
    assert dialog._error_box.isHidden() is False
    assert "GLE executable not found" in dialog._error_box.toPlainText()
    assert dialog.result() != 1  # not accepted
    # This path fails synchronously (before any process is launched), so no
    # job was ever started.
    assert dialog._runner is None


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
    assert _wait_until(lambda: dialog._runner is None, 10000)

    after = doc.figure.to_dict()
    assert before == after
    assert target.exists()


# ----------------------------------------------------------------------
# Track G3: export runs through the async compile service, not the GUI
# thread. See the module docstring in gleplot/gui/export_dialog.py.
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_click_returns_before_compile_finishes(qapp, tmp_path, scratch_settings):
    """_on_export_clicked() must return as soon as the job is *launched*,
    not once GLE has actually finished -- the opposite (call blocks until
    the file exists) is exactly the old, GUI-thread-blocking behaviour this
    track replaces."""
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "nonblocking.pdf"
    _set_path(dialog, target)

    dialog._on_export_clicked()

    # The call above must have returned control without waiting for GLE: a
    # real compile always takes measurably longer than zero event-loop
    # turns, so if this call had blocked (subprocess.run-style) the output
    # would already exist here.
    assert not target.exists()
    assert dialog._runner is not None
    assert dialog._runner.is_running

    assert _wait_until(lambda: dialog._runner is None, 10000)
    assert target.exists(), dialog._error_box.toPlainText()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_gui_thread_stays_responsive_during_export(qapp, tmp_path, scratch_settings):
    """The event loop keeps servicing other timers while a compile is in
    flight -- proof the compile isn't blocking the GUI thread. A timer
    ticking every 5ms is used as a stand-in for "the UI can still repaint,
    handle clicks, etc." while waiting for the compile service."""
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "responsive.pdf"
    _set_path(dialog, target)

    ticks = {"count": 0}
    responsiveness_timer = QTimer()
    responsiveness_timer.setInterval(5)
    responsiveness_timer.timeout.connect(
        lambda: ticks.__setitem__("count", ticks["count"] + 1)
    )
    responsiveness_timer.start()

    try:
        dialog._on_export_clicked()
        assert _wait_until(lambda: dialog._runner is None, 10000)
    finally:
        responsiveness_timer.stop()

    assert target.exists(), dialog._error_box.toPlainText()
    # The responsiveness timer must have fired multiple times *during* the
    # compile -- if the GUI thread were blocked (e.g. by a synchronous
    # subprocess.run call), no Qt timer could fire at all until the compile
    # returned, and this would be 0.
    assert (
        ticks["count"] > 0
    ), "GUI-thread timer never fired -- export blocked the event loop"


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_cancel_during_export_stops_the_job(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "cancelled.pdf"
    _set_path(dialog, target)

    dialog._on_export_clicked()
    # No event-loop turn has happened yet, so the job cannot have finished:
    # cancelling here deterministically stops it before completion.
    assert dialog._runner is not None
    dialog._on_cancel_clicked()

    assert dialog._runner is None
    assert dialog.result() != 1  # not accepted
    assert "cancel" in dialog._status_label.text().lower()

    # Give the killed process a moment to actually die and confirm no
    # output ever landed.
    _wait_until(lambda: False, 300)
    assert not target.exists()


# ----------------------------------------------------------------------
# G8 follow-up: post-compile engine-intermediate cleanup in the export
# dialog's own async compile path (Figure.savefig() already had this via
# G8; the export dialog bypasses savefig() and needed its own hookup --
# see the module docstring "Engine-intermediate cleanup").
# ----------------------------------------------------------------------
def _make_contour_document():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(7, 6), data_prefix="t")
    ax = fig.add_subplot(1, 1, 1)
    x = np.linspace(0, 10, 21)
    y = np.linspace(0, 8, 17)
    rng = np.random.default_rng(0)
    Z = np.sin(x[None, :] / 3) * np.cos(y[:, None] / 3 + rng.uniform())
    ax.contour(x, y, Z, levels=[-0.3, 0.0, 0.3], clabel=True, clabel_fmt="fix 2")
    doc.set_figure(fig)
    return doc


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_contour_cleans_up_engine_intermediates(
    qapp, tmp_path, scratch_settings
):
    """A compiled contour export leaves only the intended artifacts behind:
    the compiled output, the .gle script, the gleplot-written .z sidecar --
    but none of GLE's own -cdata/-clabels/-cvalues byproducts."""
    doc = _make_contour_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "contour.pdf"
    _set_path(dialog, target)

    dialog._on_export_clicked()
    assert _wait_until(lambda: dialog._runner is None, 15000)

    assert target.exists(), dialog._error_box.toPlainText()

    names = {p.name for p in tmp_path.iterdir()}
    leftovers = {
        n for n in names if n.endswith(("-cdata.dat", "-clabels.dat", "-cvalues.dat"))
    }
    assert leftovers == set(), f"engine intermediates not cleaned up: {leftovers}"
    # gleplot's own written artifacts must survive cleanup.
    assert "contour.gle" in names
    assert "t_contour1.z" in names


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_gle_format_never_triggers_cleanup(qapp, tmp_path, scratch_settings):
    """No compile runs for the 'gle' format, so no cleanup pass is needed;
    the .z sidecar (gleplot's own, not an engine intermediate) survives."""
    doc = _make_contour_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "contour.gle"
    _set_path(dialog, target)

    dialog._on_export_clicked()

    assert target.exists(), dialog._error_box.toPlainText()
    assert (tmp_path / "t_contour1.z").exists()


def test_cleanup_runs_only_after_a_successful_compile(qapp, tmp_path, scratch_settings):
    """Unit-level check of the gating itself (no real GLE needed):
    _on_compile_finished must call remove_generated_intermediates on a
    successful outcome and must NOT call it on a failed one -- a failed
    export's intermediates survive for debugging, mirroring
    Figure.savefig()'s own behaviour."""
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)
    dialog.selected_path = tmp_path / "out.pdf"
    dialog._export_dir = tmp_path
    dialog._export_intermediate_names = ["stem-cdata.dat"]

    with mock.patch(
        "gleplot.gui.export_dialog.remove_generated_intermediates"
    ) as cleanup:
        failed = CompileOutcome(ok=False, output_path=None, raw_output="boom")
        dialog._on_compile_finished(failed)
        cleanup.assert_not_called()
        # Intentionally left in place on failure -- reset for the next check.
        assert dialog._export_dir == tmp_path

        dialog.selected_path = tmp_path / "out.pdf"
        dialog._export_dir = tmp_path
        dialog._export_intermediate_names = ["stem-cdata.dat"]
        ok = CompileOutcome(ok=True, output_path=dialog.selected_path, raw_output="")
        dialog._on_compile_finished(ok)
        cleanup.assert_called_once_with(tmp_path, ["stem-cdata.dat"])
        # Cleared after use so a stale value is never reused by a later export.
        assert dialog._export_dir is None
        assert dialog._export_intermediate_names == []


# ----------------------------------------------------------------------
# G6 follow-up: SVG font pre-injection (found during Track G6). Parity
# with gleplot.gui.preview's SVG preview path -- see the module docstring
# "SVG font pre-injection".
# ----------------------------------------------------------------------
def _make_document_with_font(font):
    # Figure() with no explicit `style=` falls back to
    # GlobalConfig.get_style()'s shared, mutable singleton -- setting
    # `fig.style.font` in place would leak into every other Figure()
    # created afterwards in this test session. Pass an independent
    # GLEStyleConfig instead so this is fully test-local.
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3), style=glp.GLEStyleConfig(font=font))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([1, 2, 3], [1, 4, 9], label="sq")
    doc.set_figure(fig)
    return doc


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_svg_postscript_font_substituted_and_warns(
    qapp, tmp_path, scratch_settings
):
    # No explicit font set (the default): the script therefore carries no
    # `set font` line at all, so GLE's own built-in default resolves --
    # PostScript ('rm'/Times), not Cairo-safe. This is exactly the case
    # inject_svg_safe_font() must fill in: an *explicit* unsafe font choice
    # is a separate case that inject_svg_safe_font() intentionally leaves
    # alone (see its docstring's "explicit choice always wins" rule).
    doc = _make_document()
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.svg"
    _set_path(dialog, target)

    with pytest.warns(UserWarning, match="texcmr"):
        dialog._on_export_clicked()
    assert _wait_until(lambda: dialog._runner is None, 15000)

    assert target.exists(), dialog._error_box.toPlainText()
    # The script-side substitution actually landed in the compiled copy.
    script_text = (tmp_path / "out.gle").read_text(encoding="utf-8")
    assert f"set font {CAIRO_SAFE_FONT}" in script_text


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_svg_safe_font_no_warning_no_double_injection(
    qapp, tmp_path, scratch_settings
):
    doc = _make_document_with_font(CAIRO_SAFE_FONT)
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.svg"
    _set_path(dialog, target)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dialog._on_export_clicked()  # must not raise/warn
    assert _wait_until(lambda: dialog._runner is None, 15000)

    assert target.exists(), dialog._error_box.toPlainText()
    script_text = (tmp_path / "out.gle").read_text(encoding="utf-8")
    # The user's own explicit choice is untouched -- exactly one such line.
    assert script_text.count("set font") == 1
    assert f"set font {CAIRO_SAFE_FONT}" in script_text


def test_export_non_svg_format_does_not_run_svg_font_injection(
    qapp, tmp_path, scratch_settings
):
    """The SVG-only font pre-injection must never run for any other format
    -- checked directly against the call, so this needs no real GLE."""
    doc = _make_document_with_font("rm")
    dialog = ExportDialog(doc, settings=scratch_settings)

    target = tmp_path / "out.pdf"
    _set_path(dialog, target)

    with mock.patch(
        "gleplot.gui.export_dialog.inject_svg_safe_font"
    ) as inject, mock.patch("gleplot.gui.export_dialog.find_gle", return_value=None):
        # find_gle() is forced to fail so this stays synchronous and
        # deterministic (no real compile needed) -- inject_svg_safe_font is
        # only reached, if at all, before that failure for svg-format
        # exports, so its call state is unaffected by exercising this path.
        dialog._on_export_clicked()
    inject.assert_not_called()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_svg_cairo_flag_composes_with_font_and_cleanup(
    qapp, tmp_path, scratch_settings
):
    """Composition check: a figure needing -cairo for alpha AND carrying
    contour engine-intermediates AND an unsafe font, exported as SVG --
    all three tracks (G6 cairo/alpha, G6-follow-up font injection, G8
    cleanup) must fire together correctly."""
    doc = FigureDocument()
    # No explicit font -- see test_export_svg_postscript_font_substituted_
    # and_warns for why that (not an explicit unsafe choice) is the case
    # that actually exercises the substitution.
    fig = glp.Figure(figsize=(7, 6), data_prefix="t")
    ax = fig.add_subplot(1, 1, 1)
    x = np.linspace(0, 10, 21)
    y = np.linspace(0, 8, 17)
    ax.fill_between(x, np.zeros_like(x), np.ones_like(x) * 3, alpha=0.4)
    rng = np.random.default_rng(1)
    Z = np.sin(x[None, :] / 3) * np.cos(y[:, None] / 3 + rng.uniform())
    ax.contour(x, y, Z, levels=[-0.3, 0.0, 0.3], clabel=True, clabel_fmt="fix 2")
    doc.set_figure(fig)

    assert fig.requires_cairo() is True

    dialog = ExportDialog(doc, settings=scratch_settings)
    target = tmp_path / "combo.svg"
    _set_path(dialog, target)

    from gleplot.compiler import build_compile_args as real_build_args

    captured = {}

    def _spy(*args, **kwargs):
        result = real_build_args(*args, **kwargs)
        captured["cairo"] = kwargs.get("cairo")
        captured["args"] = result
        return result

    with mock.patch(
        "gleplot.gui.export_dialog.build_compile_args", side_effect=_spy
    ), pytest.warns(UserWarning, match="texcmr"):
        dialog._on_export_clicked()
    assert _wait_until(lambda: dialog._runner is None, 15000)

    assert target.exists(), dialog._error_box.toPlainText()
    # The alpha fill still drives -cairo regardless of the new SVG font path.
    assert captured["cairo"] is True
    assert "-cairo" in captured["args"]

    # Font substitution landed in the compiled script copy.
    script_text = (tmp_path / "combo.gle").read_text(encoding="utf-8")
    assert f"set font {CAIRO_SAFE_FONT}" in script_text

    # And cleanup still ran despite the extra svg/font handling in the way.
    leftovers = {
        p.name
        for p in tmp_path.iterdir()
        if p.name.endswith(("-cdata.dat", "-clabels.dat", "-cvalues.dat"))
    }
    assert leftovers == set()
    assert (tmp_path / "t_contour1.z").exists()

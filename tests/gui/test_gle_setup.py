"""Tests for the GLE Setup feature (Tools ▸ GLE Setup…).

Covers the persisted override roundtrip, that ``MainWindow`` applies the
persisted override to the process-global :func:`gleplot.compiler` state at
startup, and that changing the path via the handler refreshes the preview
controller + status label. Offscreen, plain-pytest; skips when PySide6 is
absent.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QSettings

from gleplot import compiler
from gleplot.gui.gle_setup_dialog import GleSetupDialog
from gleplot.gui.main_window import MainWindow, _GLE_PATH_KEY


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def scratch_settings(tmp_path):
    """An ini-backed QSettings isolated to a scratch file for this test."""
    ini_path = tmp_path / "settings.ini"
    return QSettings(str(ini_path), QSettings.Format.IniFormat)


@pytest.fixture(autouse=True)
def _reset_override():
    """Never leak the process-global GLE override between tests."""
    compiler.set_gle_path_override(None)
    yield
    compiler.set_gle_path_override(None)


# ----------------------------------------------------------------------
# Persistence roundtrip
# ----------------------------------------------------------------------
def test_override_persists_and_reapplies_on_next_window(
    qapp, tmp_path, scratch_settings
):
    # A real, existing file stands in for a GLE binary.
    fake_gle = tmp_path / "gle.exe"
    fake_gle.write_text("")

    w1 = MainWindow(settings=scratch_settings)
    try:
        w1._write_gle_override(str(fake_gle))
    finally:
        w1.close()

    assert scratch_settings.value(_GLE_PATH_KEY, "", type=str) == str(fake_gle)

    # A freshly-constructed window must apply the persisted override at startup
    # (before it resolves GLE for the preview / status bar).
    w2 = MainWindow(settings=scratch_settings)
    try:
        assert compiler._gle_path_override == str(fake_gle)
        # find_gle honours the override (the file exists).
        assert compiler.find_gle() == str(fake_gle)
    finally:
        w2.close()


def test_startup_with_no_setting_leaves_override_unset(qapp, scratch_settings):
    w = MainWindow(settings=scratch_settings)
    try:
        assert compiler._gle_path_override is None
    finally:
        w.close()


# ----------------------------------------------------------------------
# On-change handler
# ----------------------------------------------------------------------
def test_on_gle_setup_applies_choice(qapp, tmp_path, scratch_settings, monkeypatch):
    fake_gle = tmp_path / "gle.exe"
    fake_gle.write_text("")

    w = MainWindow(settings=scratch_settings)
    try:
        # Simulate the dialog returning the chosen path (accepted).
        monkeypatch.setattr(
            "gleplot.gui.main_window.run_gle_setup_dialog",
            lambda current_override, parent: str(fake_gle),
        )
        w._on_gle_setup()

        # Persisted + applied to the process-global override + preview cache.
        assert scratch_settings.value(_GLE_PATH_KEY, "", type=str) == str(fake_gle)
        assert compiler._gle_path_override == str(fake_gle)
        assert w.preview_controller._gle_path == str(fake_gle)
        assert str(fake_gle) in w.gle_status_label.text()
    finally:
        w.close()


def test_on_gle_setup_cancel_is_noop(qapp, scratch_settings, monkeypatch):
    w = MainWindow(settings=scratch_settings)
    try:
        before = compiler._gle_path_override
        monkeypatch.setattr(
            "gleplot.gui.main_window.run_gle_setup_dialog",
            lambda current_override, parent: None,  # cancelled
        )
        w._on_gle_setup()
        assert compiler._gle_path_override == before
        # Nothing was written.
        assert scratch_settings.value(_GLE_PATH_KEY, "", type=str) == ""
    finally:
        w.close()


# ----------------------------------------------------------------------
# Dialog behaviour
# ----------------------------------------------------------------------
def test_dialog_reports_missing_path(qapp):
    dialog = GleSetupDialog(current_override=r"C:\nope\gle.exe")
    assert "does not exist" in dialog.status_label.text()
    assert dialog.chosen_path() == r"C:\nope\gle.exe"


def test_dialog_autodetect_fills_field(qapp, tmp_path, monkeypatch):
    fake_gle = tmp_path / "gle"
    fake_gle.write_text("")
    monkeypatch.setattr(
        "gleplot.gui.gle_setup_dialog.autodetect_gle", lambda: str(fake_gle)
    )
    dialog = GleSetupDialog(current_override="")
    dialog._on_autodetect()
    assert dialog.chosen_path() == str(fake_gle)

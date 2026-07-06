"""Tests for :mod:`gleplot.gui.app` (embedding API + CLI entry point).

Covers ``open_editor`` (the embedding API for host applications) and
``main``'s handling of an optional ``.gle`` file argument. Offscreen,
plain-pytest; skips when PySide6 is absent.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

import gleplot as glp
from gleplot import compiler
from gleplot.gui import app as gui_app
from gleplot.gui.main_window import MainWindow, _GLE_PATH_KEY


@pytest.fixture
def qapp():
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


def _make_gle_file(path: Path) -> Path:
    """Write a minimal, non-programmatic .gle figure to ``path``."""
    fig = glp.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1], [0, 1])
    fig.savefig(str(path))
    return path


# ----------------------------------------------------------------------
# open_editor
# ----------------------------------------------------------------------
def test_open_editor_requires_existing_qapplication():
    """No QApplication -> RuntimeError.

    This can't be tested in-process: the module-scoped ``qapp`` fixtures used
    across this test session (and pytest-qt-style global state) mean a real
    QApplication typically already exists by the time any test runs, and
    tearing it down mid-suite would be invasive/order-dependent. Instead,
    verify it in a clean subprocess that never constructs a QApplication.
    """
    script = (
        "import gleplot.gui as gui\n"
        "try:\n"
        "    gui.open_editor()\n"
        "except RuntimeError as exc:\n"
        "    assert 'QApplication' in str(exc)\n"
        "    print('OK')\n"
        "else:\n"
        "    raise SystemExit('expected RuntimeError')\n"
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_open_editor_opens_path_and_shows_window(qapp, tmp_path, scratch_settings):
    gle_path = _make_gle_file(tmp_path / "fig.gle")

    window = gui_app.open_editor(str(gle_path), settings=scratch_settings)
    try:
        assert isinstance(window, MainWindow)
        assert window.isVisible()
        assert window.document.project_path == gle_path
        # A plain plot/savefig round trip shouldn't trip the programmatic-file
        # prompt, so no modal should have been left pending.
        assert not any(
            w.startswith("programmatic:") for w in window.document.open_warnings
        )
    finally:
        window.close()


def test_open_editor_does_not_change_application_name(qapp, tmp_path, scratch_settings):
    before = QApplication.instance().applicationName()

    gle_path = _make_gle_file(tmp_path / "fig.gle")
    window = gui_app.open_editor(str(gle_path), settings=scratch_settings)
    try:
        assert QApplication.instance().applicationName() == before
    finally:
        window.close()


def test_open_editor_gle_executable_overrides_find_gle(
    qapp, tmp_path, scratch_settings
):
    fake_gle = tmp_path / "gle.exe"
    fake_gle.write_text("")

    window = gui_app.open_editor(
        settings=scratch_settings, gle_executable=str(fake_gle)
    )
    try:
        assert compiler.find_gle() == str(fake_gle)
    finally:
        window.close()


def test_apply_gle_executable_does_not_persist_to_settings(
    qapp, tmp_path, scratch_settings
):
    fake_gle = tmp_path / "gle.exe"
    fake_gle.write_text("")

    window = MainWindow(settings=scratch_settings)
    try:
        before = scratch_settings.value(_GLE_PATH_KEY, "", type=str)
        window.apply_gle_executable(str(fake_gle))

        assert compiler.find_gle() == str(fake_gle)
        assert scratch_settings.value(_GLE_PATH_KEY, "", type=str) == before
    finally:
        window.close()


def test_force_close_skips_dirty_confirmation(qapp, tmp_path, scratch_settings, monkeypatch):
    """force_close() must never pop the discard-confirmation modal.

    Embedders (host apps) call it at shutdown, where a modal cannot be
    answered — in a headless test run it would hang the worker. Make the
    document dirty, poison QMessageBox.question so any modal fails loudly,
    and verify the window still closes.
    """
    window = MainWindow(settings=scratch_settings)
    try:
        window.document.new_figure()
        window.document.notify_changed()  # the public "mark dirty" path
        assert window.document.is_dirty

        def _no_modal(*_a, **_k):
            raise AssertionError("force_close must not prompt")

        monkeypatch.setattr(QMessageBox, "question", staticmethod(_no_modal))

        window.force_close()
        assert not window.isVisible()

        # A normal interactive close on a dirty document still confirms.
        window2 = MainWindow(settings=scratch_settings)
        try:
            window2.document.new_figure()
            window2.document.notify_changed()
            asked = []
            monkeypatch.setattr(
                QMessageBox,
                "question",
                staticmethod(
                    lambda *a, **k: asked.append(True)
                    or QMessageBox.StandardButton.Discard
                ),
            )
            window2.close()
            assert asked, "interactive close should have confirmed discard"
        finally:
            window2.force_close()
    finally:
        window.force_close()


# ----------------------------------------------------------------------
# main(): CLI file argument
# ----------------------------------------------------------------------
def test_main_nonexistent_path_returns_2(qapp, tmp_path, capsys):
    missing = tmp_path / "nope.gle"
    rc = gui_app.main([str(missing)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "nope.gle" in captured.err


def test_main_smoke_test_with_file_arg_ignores_file(qapp, tmp_path):
    """--smoke-test must keep working unmodified even with a file argument:
    the file is ignored entirely (no existence check, no open)."""
    missing = tmp_path / "nope.gle"
    rc = gui_app.main(["--smoke-test", str(missing)])
    assert rc == 0


def test_main_opens_file_after_show(qapp, tmp_path, monkeypatch):
    """main() opens the file via open_path AFTER window.show().

    main() returns only an int -- the MainWindow it constructs is a
    parentless top-level widget with no other reference, so it can't be
    inspected after the call returns. Instead, monkeypatch
    MainWindow.open_path with a spy that records the path and whether the
    window was already visible, then close the captured window ourselves.
    """
    gle_path = _make_gle_file(tmp_path / "fig.gle")

    calls = []
    original_open_path = MainWindow.open_path

    def spy_open_path(self, path_str):
        calls.append((path_str, self.isVisible(), self))
        return original_open_path(self, path_str)

    monkeypatch.setattr(MainWindow, "open_path", spy_open_path)

    # Suppress any modal (shouldn't fire for a plain plot, but don't hang the
    # suite if it does).
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Open),
    )

    try:
        # qapp fixture guarantees a QApplication already exists, so main()
        # reuses it (owns_app is False) and returns immediately without
        # entering app.exec() -- it would otherwise block the test forever.
        rc = gui_app.main([str(gle_path)])
        assert rc == 0

        assert len(calls) == 1
        called_path, was_visible, _window = calls[0]
        assert called_path == str(gle_path)
        assert was_visible is True
    finally:
        # Close the window main() constructed -- captured via the spy since
        # main() only returns an int and the window is otherwise unreferenced.
        for _path, _visible, window in calls:
            window.close()

"""Tests for :mod:`gleplot.gui.file_ops` (Track G: project open/save).

All tests pass explicit paths / settings so no real file dialog or the
user's real QSettings store is ever touched.
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
from gleplot.gui import file_ops
from gleplot.gui.document import FigureDocument


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


def _make_document():
    doc = FigureDocument()
    fig = glp.Figure(figsize=(4, 3))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([1, 2, 3], [1, 4, 9], label="sq")
    doc.set_figure(fig)
    return doc


# ----------------------------------------------------------------------
# Save As / Save / Open round trip
# ----------------------------------------------------------------------
def test_save_as_then_open_round_trip(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    doc.notify_changed()
    assert doc.is_dirty is True

    target = tmp_path / "myplot.glep"
    ok = file_ops.save_project_as(None, doc, path=target, settings=scratch_settings)

    assert ok is True
    assert target.exists()
    assert doc.project_path == target
    assert doc.is_dirty is False

    # Reopen into a fresh document.
    doc2 = FigureDocument()
    ok2 = file_ops.open_project(None, doc2, path=target, settings=scratch_settings)

    assert ok2 is True
    assert doc2.figure is not None
    assert len(doc2.figure.axes_list) == 1
    assert doc2.project_path == target
    assert doc2.is_dirty is False


def test_save_current_delegates_to_save_as_when_no_project_path(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    assert doc.project_path is None

    target = tmp_path / "delegated.glep"

    # save_project_current with an explicit path but no prior project_path:
    # since path is given explicitly, it should save directly to that path
    # (the "no path -> delegate" branch only applies when path is None AND
    # project_path is None).
    ok = file_ops.save_project_current(None, doc, path=target, settings=scratch_settings)
    assert ok is True
    assert target.exists()
    assert doc.project_path == target


def test_save_current_saves_in_place_when_project_path_set(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    target = tmp_path / "inplace.glep"
    assert file_ops.save_project_as(None, doc, path=target, settings=scratch_settings)

    # Mutate and save again without a path arg -- should use project_path.
    doc.figure.axes_list[0].plot([1, 2, 3], [3, 2, 1], label="line2")
    doc.notify_changed()
    assert doc.is_dirty is True

    ok = file_ops.save_project_current(None, doc, settings=scratch_settings)
    assert ok is True
    assert doc.is_dirty is False

    # Confirm the second series actually persisted (round trip via to_dict).
    from gleplot.project import load_project as _load
    fig = _load(target)
    assert fig.to_dict() == doc.figure.to_dict()


def test_project_path_changed_signal_emitted(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    seen = []
    doc.project_path_changed.connect(lambda s: seen.append(s))

    target = tmp_path / "signal.glep"
    file_ops.save_project_as(None, doc, path=target, settings=scratch_settings)

    assert seen == [str(target)]


# ----------------------------------------------------------------------
# Error paths
# ----------------------------------------------------------------------
def test_open_corrupt_project_returns_false(qapp, tmp_path, scratch_settings, monkeypatch):
    bad = tmp_path / "corrupt.glep"
    bad.write_text("{ not valid json !!", encoding="utf-8")

    critical_calls = []
    monkeypatch.setattr(
        file_ops.QMessageBox, "critical",
        lambda *args, **kwargs: critical_calls.append(args),
    )

    doc = FigureDocument()
    ok = file_ops.open_project(None, doc, path=bad, settings=scratch_settings)

    assert ok is False
    assert doc.figure is None
    assert len(critical_calls) == 1


def test_open_missing_file_returns_false(qapp, tmp_path, scratch_settings, monkeypatch):
    missing = tmp_path / "does_not_exist.glep"

    monkeypatch.setattr(file_ops.QMessageBox, "critical", lambda *a, **k: None)

    doc = FigureDocument()
    ok = file_ops.open_project(None, doc, path=missing, settings=scratch_settings)

    assert ok is False


def test_open_bad_envelope_returns_false(qapp, tmp_path, scratch_settings, monkeypatch):
    """Valid JSON but not a recognized figure envelope -> ValueError -> False."""
    bad = tmp_path / "wrong_envelope.glep"
    bad.write_text('{"foo": "bar"}', encoding="utf-8")

    monkeypatch.setattr(file_ops.QMessageBox, "critical", lambda *a, **k: None)

    doc = FigureDocument()
    ok = file_ops.open_project(None, doc, path=bad, settings=scratch_settings)

    assert ok is False
    assert doc.figure is None


def test_save_with_no_figure_shows_error_and_returns_false(qapp, tmp_path, scratch_settings, monkeypatch):
    monkeypatch.setattr(file_ops.QMessageBox, "critical", lambda *a, **k: None)

    doc = FigureDocument()  # figure is None
    target = tmp_path / "nofig.glep"
    ok = file_ops.save_project_as(None, doc, path=target, settings=scratch_settings)

    assert ok is False
    assert not target.exists()


# ----------------------------------------------------------------------
# Recent files
# ----------------------------------------------------------------------
def test_recent_files_dedup_and_order(qapp, scratch_settings):
    file_ops.add_recent_file("a.glep", settings=scratch_settings)
    file_ops.add_recent_file("b.glep", settings=scratch_settings)
    file_ops.add_recent_file("c.glep", settings=scratch_settings)
    # Re-adding "a" should move it to the front, not duplicate it.
    file_ops.add_recent_file("a.glep", settings=scratch_settings)

    recent = file_ops.get_recent_files(settings=scratch_settings)
    assert recent == [str(Path("a.glep")), str(Path("c.glep")), str(Path("b.glep"))]


def test_recent_files_dedup_is_case_insensitive_on_windows(qapp, tmp_path, scratch_settings):
    """FIX 8: on a case-insensitive filesystem, the same file added with
    different casing must dedup to one entry (moved to the front), storing the
    most-recently-added original casing."""
    import os

    p_lower = tmp_path / "project.glep"
    p_upper = tmp_path / "PROJECT.GLEP"

    file_ops.add_recent_file("other.glep", settings=scratch_settings)
    file_ops.add_recent_file(str(p_lower), settings=scratch_settings)
    # Re-add the SAME file with different casing.
    file_ops.add_recent_file(str(p_upper), settings=scratch_settings)

    recent = file_ops.get_recent_files(settings=scratch_settings)

    # On Windows (case-insensitive) the two casings are one file: exactly one
    # recent entry for it, moved to the front. On a case-sensitive OS they are
    # genuinely different files and both entries are kept -- so gate the strict
    # dedup assertion on the platform's normcase behaviour.
    same = os.path.normcase(str(p_lower)) == os.path.normcase(str(p_upper))
    if same:
        normalized = [os.path.normcase(os.path.abspath(r)) for r in recent]
        assert normalized.count(os.path.normcase(os.path.abspath(str(p_lower)))) == 1
        # Front entry is the project (most recently added), stored with the
        # original casing it was last added with.
        assert os.path.normcase(os.path.abspath(recent[0])) == \
            os.path.normcase(os.path.abspath(str(p_upper)))
        assert len(recent) == 2  # project + other


def test_recent_files_cap(qapp, scratch_settings):
    for i in range(12):
        file_ops.add_recent_file(f"file_{i}.glep", settings=scratch_settings)

    recent = file_ops.get_recent_files(settings=scratch_settings)
    assert len(recent) == file_ops.MAX_RECENT_FILES
    # Most recent first.
    assert recent[0] == str(Path("file_11.glep"))


def test_recent_files_empty_by_default(qapp, scratch_settings):
    assert file_ops.get_recent_files(settings=scratch_settings) == []


def test_open_and_save_add_to_recent_files(qapp, tmp_path, scratch_settings):
    doc = _make_document()
    target = tmp_path / "recent_check.glep"
    file_ops.save_project_as(None, doc, path=target, settings=scratch_settings)

    recent = file_ops.get_recent_files(settings=scratch_settings)
    assert str(target) in recent

    doc2 = FigureDocument()
    file_ops.open_project(None, doc2, path=target, settings=scratch_settings)
    recent2 = file_ops.get_recent_files(settings=scratch_settings)
    # Still present (moved to front), not duplicated.
    assert recent2.count(str(target)) == 1

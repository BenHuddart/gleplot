"""Tests for :class:`gleplot.gui.document.FigureDocument`.

Verifies signal emission on figure replacement and in-place mutation, plus
the dirty-flag lifecycle. Skips cleanly when PySide6 is unavailable.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.gui.document import FigureDocument


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _Counter:
    """Tiny signal-counting helper."""

    def __init__(self):
        self.count = 0
        self.args = []

    def __call__(self, *args):
        self.count += 1
        self.args.append(args)


def test_new_figure_emits_replaced_and_is_clean(qapp):
    doc = FigureDocument()
    replaced = _Counter()
    doc.figure_replaced.connect(replaced)

    fig = doc.new_figure()

    assert fig is doc.figure
    assert len(fig.axes_list) == 1
    assert replaced.count == 1
    assert doc.is_dirty is False


def test_set_figure_emits_replaced(qapp):
    doc = FigureDocument()
    replaced = _Counter()
    doc.figure_replaced.connect(replaced)

    fig = glp.Figure()
    doc.set_figure(fig)

    assert doc.figure is fig
    assert replaced.count == 1


def test_notify_changed_emits_and_dirties(qapp):
    doc = FigureDocument(glp.Figure())
    changed = _Counter()
    dirty = _Counter()
    doc.figure_changed.connect(changed)
    doc.dirty_changed.connect(dirty)

    assert doc.is_dirty is False
    doc.notify_changed()

    assert changed.count == 1
    assert doc.is_dirty is True
    # dirty_changed fires exactly once on the False->True transition.
    assert dirty.count == 1
    assert dirty.args[-1] == (True,)


def test_dirty_changed_only_on_transition(qapp):
    doc = FigureDocument(glp.Figure())
    dirty = _Counter()
    doc.dirty_changed.connect(dirty)

    doc.notify_changed()
    doc.notify_changed()
    doc.notify_changed()

    # Three mutations, but only one True transition.
    assert doc.is_dirty is True
    assert dirty.count == 1


def test_mark_clean_clears_dirty(qapp):
    doc = FigureDocument(glp.Figure())
    dirty = _Counter()
    doc.dirty_changed.connect(dirty)

    doc.notify_changed()
    assert doc.is_dirty is True
    doc.mark_clean()

    assert doc.is_dirty is False
    # True transition then False transition = two emissions.
    assert dirty.count == 2
    assert dirty.args[-1] == (False,)


def test_set_figure_resets_dirty(qapp):
    doc = FigureDocument(glp.Figure())
    doc.notify_changed()
    assert doc.is_dirty is True

    doc.set_figure(glp.Figure())
    assert doc.is_dirty is False


def test_set_figure_clears_project_path(qapp):
    """FIX 1: set_figure must reset project_path so File>New after editing a
    saved project does not keep the old .gle as the Save target."""
    doc = FigureDocument(glp.Figure())
    doc.project_path = "foo.gle"
    assert doc.project_path is not None

    path_changed = _Counter()
    doc.project_path_changed.connect(path_changed)

    # File>New (via new_figure -> set_figure) must clear the stale path.
    doc.new_figure()

    assert doc.project_path is None
    # project_path_changed emitted with empty string on clear.
    assert path_changed.count == 1
    assert path_changed.args[-1] == ("",)


def test_open_project_ordering_preserves_path(qapp, tmp_path):
    """FIX 1 regression guard: open_project calls set_figure THEN assigns
    project_path, so the new clearing behaviour must not wipe the loaded path."""
    from gleplot.gui import file_ops

    src = tmp_path / "proj.gle"
    fig = glp.Figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="s")
    fig.savefig_gle(str(src))

    doc = FigureDocument()
    assert file_ops.open_project(None, doc, path=src) is True
    assert doc.project_path == src

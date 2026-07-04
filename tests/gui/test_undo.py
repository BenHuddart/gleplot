"""Tests for :class:`gleplot.gui.undo.UndoStack` (Phase 2, Track I).

Snapshot-based undo/redo over a :class:`FigureDocument`. These are offscreen,
plain-pytest tests (no pytest-qt); they wrap real ``gleplot.Figure`` objects.
Skips cleanly when PySide6 is unavailable. One integration test drives the real
:class:`PreviewController` and is marked ``xfail`` when GLE is not installed.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import gleplot as glp
from gleplot.compiler import find_gle
from gleplot.gui.document import FigureDocument
from gleplot.gui.preview import PreviewController
from gleplot.gui.undo import UndoStack, _estimate_size

_GLE_AVAILABLE = find_gle() is not None


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class _Counter:
    """Tiny signal-counting helper (mirrors test_document.py)."""

    def __init__(self):
        self.count = 0
        self.args = []

    def __call__(self, *args):
        self.count += 1
        self.args.append(args)


def _fig_with_series(n=1):
    """Build a real Figure with ``n`` line series on a single subplot."""
    fig = glp.Figure()
    ax = fig.add_subplot(1, 1, 1)
    x = np.linspace(0, 1, 10)
    for i in range(n):
        ax.plot(x, x * (i + 1), label=f"s{i}")
    return fig


def _add_series(doc):
    """Add one series to the document's figure and notify (a real mutation)."""
    ax = doc.figure.axes_list[0]
    x = np.linspace(0, 1, 10)
    ax.plot(x, x * (len(ax.lines) + 1), label=f"s{len(ax.lines)}")
    doc.notify_changed()


def _wait(ms):
    """Spin the Qt event loop for ``ms`` milliseconds."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _content(fig):
    """Authoritative editable figure content, ignoring the process-global
    data-file counter.

    ``Figure.to_dict`` embeds gleplot's live module-global
    ``_global_data_file_counter`` (and ``from_dict`` restores it via ``max``),
    so a snapshot taken before an edit and one taken after undoing that edit
    differ only in ``global_data_counter`` -- an inherent, documented artifact,
    not something undo restores. We compare the ``axes`` block plus the
    figure-level parameters that undo IS responsible for.
    """
    d = fig.to_dict()["figure"]
    return {
        "figsize": d["figsize"],
        "dpi": d["dpi"],
        "sharex": d["sharex"],
        "sharey": d["sharey"],
        "subplot_adjust": d["subplot_adjust"],
        "config": d["config"],
        "axes": d["axes"],
    }


# ----------------------------------------------------------------------
# Recording / coalescing
# ----------------------------------------------------------------------
def test_push_on_notify_after_mutation(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    # Baseline seeded at construction.
    assert stack.count == 1

    _add_series(doc)
    assert stack.count == 2
    _add_series(doc)
    assert stack.count == 3


def test_no_push_when_nothing_changed(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    assert stack.count == 1

    # Two notify_changed in a row with no real mutation coalesce to zero pushes.
    doc.notify_changed()
    doc.notify_changed()
    assert stack.count == 1


def test_seed_baseline_at_construction(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    assert stack.count == 1
    assert stack.index == 0
    assert stack.can_undo is False
    assert stack.can_redo is False


def test_no_baseline_when_document_empty(qapp):
    doc = FigureDocument()  # figure is None
    stack = UndoStack(doc)
    assert stack.count == 0
    assert stack.index == -1
    assert stack.can_undo is False


# ----------------------------------------------------------------------
# Undo / redo restore
# ----------------------------------------------------------------------
def test_undo_restores_previous_state(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    baseline = _content(doc.figure)

    _add_series(doc)
    after_edit = _content(doc.figure)
    assert after_edit != baseline

    assert stack.undo() is True
    assert _content(doc.figure) == baseline


def test_redo_reapplies_state(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)

    _add_series(doc)
    after_edit = _content(doc.figure)

    stack.undo()
    assert stack.redo() is True
    assert _content(doc.figure) == after_edit


def test_undo_at_baseline_returns_false(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    assert stack.undo() is False


def test_redo_without_undo_returns_false(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    _add_series(doc)
    assert stack.redo() is False


def test_single_edit_undo_reaches_pristine_baseline(qapp):
    """Baseline semantics: one edit then undo returns to the pristine figure."""
    doc = FigureDocument()
    doc.new_figure()  # pristine single-subplot figure
    stack = UndoStack(doc)
    pristine = _content(doc.figure)

    _add_series(doc)
    assert _content(doc.figure) != pristine

    stack.undo()
    assert _content(doc.figure) == pristine


def test_edit_after_undo_clears_redo(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)

    _add_series(doc)  # index 1
    _add_series(doc)  # index 2
    assert stack.count == 3

    stack.undo()  # back to index 1
    assert stack.can_redo is True

    # A fresh edit from index 1 truncates the redo tail (old index 2).
    _add_series(doc)
    assert stack.can_redo is False
    assert stack.count == 3  # baseline, first edit, new edit
    assert stack.index == 2


# ----------------------------------------------------------------------
# can_undo / can_redo transitions and signals
# ----------------------------------------------------------------------
def test_can_undo_redo_signals_on_transitions(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    undo_sig = _Counter()
    redo_sig = _Counter()
    stack.can_undo_changed.connect(undo_sig)
    stack.can_redo_changed.connect(redo_sig)

    # First edit: can_undo False->True (one emit); can_redo stays False.
    _add_series(doc)
    assert undo_sig.count == 1
    assert undo_sig.args[-1] == (True,)
    assert redo_sig.count == 0

    # Second edit: can_undo already True (no emit); can_redo still False.
    _add_series(doc)
    assert undo_sig.count == 1

    # Undo: can_redo False->True (one emit); can_undo still True.
    stack.undo()
    assert redo_sig.count == 1
    assert redo_sig.args[-1] == (True,)

    # Undo to baseline: can_undo True->False; can_redo already True.
    stack.undo()
    assert undo_sig.count == 2
    assert undo_sig.args[-1] == (False,)


# ----------------------------------------------------------------------
# figure_replaced resets the stack
# ----------------------------------------------------------------------
def test_figure_replaced_resets_stack(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    _add_series(doc)
    _add_series(doc)
    assert stack.count == 3

    # Simulate File > Open: a brand-new figure is installed.
    doc.set_figure(_fig_with_series(2))
    assert stack.count == 1
    assert stack.index == 0
    assert stack.can_undo is False
    assert stack.can_redo is False
    # New/Open starts clean and saved.
    assert stack.is_saved_position is True


# ----------------------------------------------------------------------
# Capacity eviction
# ----------------------------------------------------------------------
def test_capacity_evicts_oldest(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc, capacity=3)
    baseline = _content(doc.figure)

    _add_series(doc)  # count 2
    _add_series(doc)  # count 3 (at capacity)
    assert stack.count == 3

    _add_series(doc)  # count would be 4 -> evict oldest (baseline)
    assert stack.count == 3
    assert stack.index == 2  # cursor still points at newest

    # Undo all the way back: the oldest reachable state is NOT the baseline.
    stack.undo()
    stack.undo()
    assert stack.can_undo is False
    assert _content(doc.figure) != baseline


# ----------------------------------------------------------------------
# Restore does NOT record / no loops
# ----------------------------------------------------------------------
def test_restore_does_not_record(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    _add_series(doc)
    assert stack.count == 2

    stack.undo()
    # Undo must not have pushed anything (the guard suppresses our recording of
    # the figure_replaced/figure_changed it triggers).
    assert stack.count == 2
    stack.redo()
    assert stack.count == 2


def test_restore_no_infinite_loop_signal_counter(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)

    replaced = _Counter()
    changed = _Counter()
    doc.figure_replaced.connect(replaced)
    doc.figure_changed.connect(changed)

    _add_series(doc)  # one figure_changed
    assert changed.count == 1

    # Undo emits exactly one figure_replaced (bounded, no loop). Since we are
    # returning to the saved/baseline position, no re-dirty notify fires.
    stack.undo()
    assert replaced.count == 1
    assert changed.count == 1  # no extra figure_changed from the restore


# ----------------------------------------------------------------------
# Dirty / saved-state interplay
# ----------------------------------------------------------------------
def test_dirty_interplay_saved_position(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)

    _add_series(doc)  # index 1, dirty
    assert doc.is_dirty is True

    # Save at index 1.
    doc.mark_clean()
    stack.mark_saved()
    assert doc.is_dirty is False
    assert stack.is_saved_position is True

    _add_series(doc)  # index 2, moved away from saved
    assert doc.is_dirty is True

    # Undo back to the saved position (index 1): document becomes clean again.
    stack.undo()
    assert stack.index == 1
    assert stack.is_saved_position is True
    assert doc.is_dirty is False

    # Undo again to baseline (index 0): away from saved -> re-dirtied.
    stack.undo()
    assert stack.is_saved_position is False
    assert doc.is_dirty is True

    # Redo back to saved position: clean again.
    stack.redo()
    assert stack.is_saved_position is True
    assert doc.is_dirty is False


def test_undo_away_from_saved_redirties(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    # Baseline (index 0) is the saved position after construction.
    _add_series(doc)  # index 1
    doc.mark_clean()
    stack.mark_saved()  # saved at index 1

    stack.undo()  # index 0, differs from saved index 1
    assert doc.is_dirty is True


# ----------------------------------------------------------------------
# Size guard
# ----------------------------------------------------------------------
def test_size_guard_reduces_effective_capacity(qapp):
    doc = FigureDocument(_fig_with_series(1))
    # Very small byte limit so every real snapshot trips the guard, halving the
    # effective capacity from 10 to 5.
    stack = UndoStack(doc, capacity=10, max_snapshot_bytes=1)
    for _ in range(20):
        _add_series(doc)
    assert stack.count == 5


def test_size_guard_unlimited_by_default(qapp):
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc, capacity=10)
    for _ in range(20):
        _add_series(doc)
    assert stack.count == 10


def test_estimate_size_positive():
    snap = _fig_with_series(2).to_dict()
    assert _estimate_size(snap) > 0


def test_capacity_below_two_rejected(qapp):
    doc = FigureDocument(_fig_with_series(1))
    with pytest.raises(ValueError):
        UndoStack(doc, capacity=1)


# ----------------------------------------------------------------------
# FIX 4: restore-failure must not desync the cursor from the document.
# ----------------------------------------------------------------------
def test_undo_restore_failure_does_not_desync_cursor(qapp, monkeypatch):
    """If Figure.from_dict raises during undo, the cursor must NOT move: a
    later successful undo/redo must still behave correctly."""
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)

    _add_series(doc)  # index 1
    _add_series(doc)  # index 2
    assert stack.index == 2
    assert stack.can_undo is True
    assert stack.can_redo is False

    # Snapshot the state BEFORE the failed undo (the document must be untouched).
    state_before = _content(doc.figure)
    index_before = stack.index

    # Make the next restore raise once. undo.py imports the same Figure class
    # object (from gleplot.figure), so patching glp.Figure patches its lookup.
    real_from_dict = glp.Figure.from_dict
    calls = {"n": 0}

    def flaky_from_dict(d):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_from_dict(d)

    monkeypatch.setattr(glp.Figure, "from_dict", staticmethod(flaky_from_dict))

    # The undo fails. It must either return False or re-raise, but crucially it
    # must NOT leave the cursor advanced past the still-current document state.
    try:
        result = stack.undo()
    except RuntimeError:
        result = None  # re-raise is an acceptable contract

    # Cursor unchanged, document unchanged.
    assert stack.index == index_before
    assert _content(doc.figure) == state_before
    # can_undo/can_redo still consistent with the unchanged cursor.
    assert stack.can_undo is True
    assert stack.can_redo is False

    # A subsequent successful undo now works and moves exactly one step.
    monkeypatch.undo()  # restore real from_dict
    assert stack.undo() is True
    assert stack.index == index_before - 1
    assert stack.can_redo is True


# ----------------------------------------------------------------------
# Integration with the real PreviewController
# ----------------------------------------------------------------------
@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_undo_drives_single_coalesced_preview_render(qapp):
    """undo() triggers a bounded, coalesced preview render burst -- no loop."""
    doc = FigureDocument(_fig_with_series(1))
    stack = UndoStack(doc)
    ctrl = PreviewController(doc, debounce_ms=50)

    started = _Counter()
    finished = _Counter()
    ctrl.render_started.connect(started)
    ctrl.render_succeeded.connect(finished)
    ctrl.render_failed.connect(finished)

    try:
        _add_series(doc)  # a real edit -> preview render
        # Let the edit's render settle.
        _wait(1500)
        started_after_edit = started.count

        # Undo: emits figure_replaced (+ possibly a re-dirty figure_changed).
        # The preview must re-render the restored state, coalesced into a small
        # bounded number of renders -- and must NOT loop.
        stack.undo()
        _wait(1500)

        renders_from_undo = started.count - started_after_edit
        assert renders_from_undo >= 1, "undo did not trigger a preview render"
        assert renders_from_undo <= 3, (
            f"undo triggered too many renders ({renders_from_undo}); possible loop"
        )

        # Settle further and confirm it has stopped (no runaway loop).
        stable = started.count
        _wait(800)
        assert started.count == stable, "preview kept rendering after undo settled"
    finally:
        ctrl.shutdown()

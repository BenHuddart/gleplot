"""Snapshot-based undo/redo for the gleplot GUI editor (Phase 2, Track I).

This module implements :class:`UndoStack`, which records the editing history of
a :class:`~gleplot.gui.document.FigureDocument` as a linear sequence of
serialized figure snapshots and lets the user step backward (undo) and forward
(redo) through them.

Why snapshots
-------------
gleplot :class:`~gleplot.figure.Figure` objects have a deterministic,
byte-stable serialization (:meth:`Figure.to_dict` / :meth:`Figure.from_dict`,
documented as suitable for undo). Rather than tracking individual reversible
commands, the stack simply captures ``document.figure.to_dict()`` after every
mutation. A snapshot is a plain JSON-safe ``dict`` (numpy already converted to
lists by ``to_dict``), so equality comparison, storage, and reconstruction are
all trivial. The tradeoff -- memory -- is bounded by ``capacity`` and, if set,
``max_snapshot_bytes`` (see below).

Position model
--------------
The history is a single list ``_snapshots`` plus an integer cursor ``_index``
pointing at the snapshot that reflects the *current* document state. This is
cleaner than two stacks: ``can_undo`` is ``_index > 0`` and ``can_redo`` is
``_index < len(_snapshots) - 1``. A new edit truncates everything after the
cursor (clearing the "redo" tail) before appending.

Baseline semantics
-------------------
When a figure is first installed (at construction, if the document already has
one, or on every ``figure_replaced``), its snapshot is seeded as the bottom
entry (index 0). That baseline is the pristine state the *first* edit can be
undone back to. Once the stack exceeds ``capacity`` the oldest entries -- the
baseline included -- are evicted; after enough edits the pristine state is no
longer reachable. This is the standard bounded-history tradeoff.

Signal flow (the subtle part)
-----------------------------
Recording -- driven by the document's own signals:

* ``figure_changed`` (from ``notify_changed``): a panel mutated the figure in
  place. We push ``figure.to_dict()`` (unless it equals the current top, i.e.
  a no-op ``notify_changed`` -- those must not create empty undo steps) and
  clear the redo tail.
* ``figure_replaced`` (from ``set_figure`` / ``new_figure``): a brand-new
  figure was installed (File New/Open). We RESET the whole history and seed the
  new baseline. Open/New start clean, so the saved-position marker is set here.

Restoring -- ``undo()`` / ``redo()``:

    undo()  ->  move cursor  ->  Figure.from_dict(snapshot)
            ->  document.set_figure(fig)           # emits figure_replaced
                                                   #   -> preview re-renders
            ->  (optionally) document.notify_changed()  # re-dirty if needed
                                                   #   -> emits figure_changed
                                                   #   -> preview coalesces the
                                                   #      second render (debounce)

The critical re-entrancy hazard: ``set_figure`` emits ``figure_replaced`` and
``notify_changed`` emits ``figure_changed`` -- both of which this stack listens
to. During a restore we must NOT let those signals record anything (that would
corrupt the history or, worse, loop). A single guard flag ``_restoring`` is
raised around the whole restore; our own ``figure_changed`` / ``figure_replaced``
handlers no-op while it is set. Crucially the guard suppresses only *our
recording* -- the signals still fire, so the preview controller (which is a
separate observer) DOES re-render the restored state. That is the desired
behaviour: after an undo the preview must show the restored figure.

Dirty / saved-state interplay
-----------------------------
``set_figure`` marks the document clean, which is wrong after an undo: the
restored state is generally *not* the last-saved state. We track a
``_saved_index`` marker. Integration code calls :meth:`mark_saved` after a
successful project save; :meth:`reset` (via ``figure_replaced``) also marks the
current position saved since New/Open start clean. After every ``undo`` /
``redo`` we compare the cursor to ``_saved_index``: if they differ we re-dirty
the document via ``document.notify_changed()`` (inside the guard so it does not
record a snapshot but still drives the preview); if they match we leave the
document clean (``set_figure`` already cleared the flag). :attr:`is_saved_position`
exposes the comparison.

Memory / size guard
--------------------
Snapshots can be large for figures with big datasets. ``max_snapshot_bytes``
(default ``None`` = unlimited) caps memory: when the *most recent* snapshot's
estimated size exceeds the limit, the effective capacity is reduced so fewer
snapshots are retained (down to a floor of 2 so at least one undo remains
possible). Size is estimated with a cheap recursive ``sys.getsizeof`` walk
rather than ``json.dumps`` -- the latter is accurate but far too slow to run on
every edit for a large figure. The estimate is a rough proxy for retained
memory, not an exact byte count; it only needs to be monotonic enough to
trigger the capacity reduction. Deliberately simple: a correct, dumb bound
beats a clever, fragile one.
"""

from __future__ import annotations

import sys
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from gleplot.figure import Figure
from gleplot.gui.document import FigureDocument


def _estimate_size(obj, _seen: Optional[set] = None) -> int:
    """Rough recursive ``sys.getsizeof`` estimate of a snapshot's memory.

    Walks dicts/lists/tuples/sets and sums the shallow sizes of the containers
    and their contents, guarding against cycles (snapshots never contain them,
    but the guard is cheap insurance). This is intentionally approximate: it is
    used only to decide whether a snapshot is "big" relative to
    ``max_snapshot_bytes``, not to report an exact footprint. It is far cheaper
    than ``len(json.dumps(obj))`` because it avoids building the serialized
    string.
    """
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return 0
    _seen.add(obj_id)

    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for key, value in obj.items():
            size += _estimate_size(key, _seen)
            size += _estimate_size(value, _seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            size += _estimate_size(item, _seen)
    return size


class UndoStack(QObject):
    """Linear snapshot-based undo/redo history over a :class:`FigureDocument`.

    Parameters
    ----------
    document : FigureDocument
        The document to observe and mutate. The stack connects to its
        ``figure_changed`` and ``figure_replaced`` signals to record history,
        and drives ``set_figure`` / ``notify_changed`` to restore snapshots.
    capacity : int, optional
        Maximum number of snapshots retained (default 50). Oldest entries --
        including the baseline -- are evicted once exceeded.
    max_snapshot_bytes : int, optional
        If set, an approximate per-snapshot memory limit. When the newest
        snapshot's estimated size exceeds it, the effective capacity is reduced
        (floor 2) so fewer large snapshots are kept. Default ``None`` =
        unlimited.
    parent : QObject, optional
        Qt parent.

    Signals
    -------
    can_undo_changed(bool)
        Emitted only when :attr:`can_undo` transitions.
    can_redo_changed(bool)
        Emitted only when :attr:`can_redo` transitions.
    """

    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)

    def __init__(
        self,
        document: FigureDocument,
        capacity: int = 50,
        max_snapshot_bytes: Optional[int] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        if capacity < 2:
            raise ValueError("capacity must be at least 2")
        self._document = document
        self._capacity = capacity
        self._max_snapshot_bytes = max_snapshot_bytes

        self._snapshots: List[dict] = []
        self._index: int = -1
        self._saved_index: int = -1

        # Re-entrancy guard: while set, our own recording handlers no-op so a
        # restore's set_figure/notify_changed do not corrupt history or loop.
        self._restoring: bool = False

        # Cached transition state so we only emit can_*_changed on real edges.
        self._last_can_undo = False
        self._last_can_redo = False

        document.figure_changed.connect(self._on_figure_changed)
        document.figure_replaced.connect(self._on_figure_replaced)

        # Seed a baseline if the document already wraps a figure.
        if document.figure is not None:
            self._seed_baseline(document.figure)

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        """Whether there is an earlier snapshot to restore."""
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        """Whether there is a later snapshot to re-apply."""
        return 0 <= self._index < len(self._snapshots) - 1

    @property
    def count(self) -> int:
        """Number of snapshots currently retained."""
        return len(self._snapshots)

    @property
    def index(self) -> int:
        """Cursor into the snapshot list (the current state), or -1 if empty."""
        return self._index

    @property
    def is_saved_position(self) -> bool:
        """Whether the cursor is at the last-saved position.

        When ``True`` the current state matches what was last persisted (or the
        pristine New/Open baseline), so the document can legitimately be clean.
        """
        return self._index == self._saved_index

    # ------------------------------------------------------------------
    # Saved-state marker
    # ------------------------------------------------------------------
    def mark_saved(self) -> None:
        """Record the current cursor as the last-saved position.

        Integration code calls this after a successful project save. Undo/redo
        that returns to this position leaves the document clean; moving away
        from it re-dirties the document.
        """
        self._saved_index = self._index

    # ------------------------------------------------------------------
    # Recording (document signal handlers)
    # ------------------------------------------------------------------
    def _on_figure_changed(self) -> None:
        """Record an in-place mutation (from ``notify_changed``)."""
        if self._restoring:
            return
        fig = self._document.figure
        if fig is None:
            return
        self._push(fig.to_dict())

    def _on_figure_replaced(self) -> None:
        """Reset history for a newly installed figure (New/Open)."""
        if self._restoring:
            return
        fig = self._document.figure
        self.reset(fig)

    def _seed_baseline(self, fig: Optional[Figure]) -> None:
        """Install ``fig``'s snapshot as the sole baseline entry."""
        self._snapshots = [fig.to_dict()] if fig is not None else []
        self._index = 0 if self._snapshots else -1
        self._saved_index = self._index
        self._emit_transitions()

    def reset(self, fig: Optional[Figure] = None) -> None:
        """Clear all history and seed ``fig`` (or the document's figure).

        Used on ``figure_replaced``. The seeded position is marked saved since
        File New/Open starts from a clean, persisted-or-pristine state.
        """
        if fig is None:
            fig = self._document.figure
        self._seed_baseline(fig)

    def _push(self, snapshot: dict) -> None:
        """Append ``snapshot`` as the new current state, clearing the redo tail.

        Coalesces a no-op push (snapshot equal to the current top) and enforces
        the capacity / size-guard bounds.
        """
        # Coalesce: a notify_changed that did not actually change anything must
        # not create an empty undo step.
        if self._index >= 0 and self._snapshots[self._index] == snapshot:
            return

        # Truncate any redo tail: a new edit invalidates the forward history.
        del self._snapshots[self._index + 1:]

        # If the saved position was in the truncated tail, it is unreachable now.
        if self._saved_index > self._index:
            self._saved_index = -1

        self._snapshots.append(snapshot)
        self._index = len(self._snapshots) - 1

        self._enforce_capacity(snapshot)
        self._emit_transitions()

    def _effective_capacity(self, latest: dict) -> int:
        """Capacity after applying the optional per-snapshot size guard."""
        cap = self._capacity
        if self._max_snapshot_bytes is not None:
            if _estimate_size(latest) > self._max_snapshot_bytes:
                # Big snapshots: keep fewer of them. Floor of 2 preserves at
                # least one undo step.
                cap = max(2, self._capacity // 2)
        return cap

    def _enforce_capacity(self, latest: dict) -> None:
        """Evict oldest snapshots beyond the effective capacity."""
        cap = self._effective_capacity(latest)
        excess = len(self._snapshots) - cap
        if excess > 0:
            del self._snapshots[:excess]
            self._index -= excess
            if self._index < 0:
                self._index = 0
            # Shift or invalidate the saved marker.
            if self._saved_index >= 0:
                self._saved_index -= excess
                if self._saved_index < 0:
                    self._saved_index = -1

    # ------------------------------------------------------------------
    # Restoring
    # ------------------------------------------------------------------
    def undo(self) -> bool:
        """Restore the previous snapshot. Returns ``False`` if none.

        Re-raises if the restore itself fails (see :meth:`_restore_at`); on
        failure the cursor and document are left untouched (no desync).
        """
        if not self.can_undo:
            return False
        self._restore_at(self._index - 1)
        return True

    def redo(self) -> bool:
        """Re-apply the next snapshot. Returns ``False`` if none.

        Re-raises if the restore itself fails (see :meth:`_restore_at`); on
        failure the cursor and document are left untouched (no desync).
        """
        if not self.can_redo:
            return False
        self._restore_at(self._index + 1)
        return True

    def _restore_at(self, target_index: int) -> None:
        """Rebuild and install the snapshot at ``target_index``.

        The cursor (``self._index``) is committed to ``target_index`` *only*
        after the figure is successfully rebuilt and installed. If
        ``Figure.from_dict`` or any ``figure_replaced``/``figure_changed`` slot
        raises, the cursor and document are left exactly as they were and the
        exception propagates -- so a failed undo/redo never desyncs the cursor
        from the document (FIX 4). The re-entrancy guard is always cleared in
        ``finally``.

        Guards recording around ``set_figure`` (which emits ``figure_replaced``
        and marks the document clean) and the optional re-dirty
        ``notify_changed`` (which emits ``figure_changed``). The guard blocks
        only *our* handlers; the signals still fire so the preview re-renders.
        """
        snapshot = self._snapshots[target_index]

        self._restoring = True
        try:
            # Build first: if from_dict raises we have mutated nothing.
            fig = Figure.from_dict(snapshot)
            # Emits figure_replaced -> preview re-renders; also marks clean.
            self._document.set_figure(fig)
            # Commit the cursor only once the restore has succeeded.
            self._index = target_index
            # If we are not back at the saved position, the restored state has
            # unsaved differences: re-dirty. notify_changed also drives a
            # second preview render, which the debounce coalesces.
            if self._index != self._saved_index:
                self._document.notify_changed()
        finally:
            self._restoring = False

        self._emit_transitions()

    # ------------------------------------------------------------------
    # Transition signalling
    # ------------------------------------------------------------------
    def _emit_transitions(self) -> None:
        """Emit can_undo/redo_changed only on genuine transitions."""
        cu = self.can_undo
        cr = self.can_redo
        if cu != self._last_can_undo:
            self._last_can_undo = cu
            self.can_undo_changed.emit(cu)
        if cr != self._last_can_redo:
            self._last_can_redo = cr
            self.can_redo_changed.emit(cr)

"""Qt-free core of the async GLE compile service (Track G3).

This module holds every piece of the compile pipeline that has no business
depending on Qt:

* :class:`RenderCoalescer` -- the sequence-number bookkeeping behind SPEC
  §6.1's "overlapping renders coalesce so only the newest state is shown"
  rule, factored out as a plain, independently testable state machine.
* :class:`CompileOutcome` / :func:`evaluate_compile_output` -- turning a
  finished process's exit code and output file into a structured result,
  reusing :func:`gleplot.compiler.parse_gle_errors` for the failure case
  (never reimplementing GLE error parsing).
* :func:`create_session_dir` / :func:`remove_session_dir` -- the temp
  session-directory bookkeeping a compile needs a writable working directory
  for (GLE's contour/``fitz`` paths write intermediate files next to the
  script; see SPEC §6.1).
* :data:`DEFAULT_WATCHDOG_MS` -- the single source of truth for how long a
  compile may run before it is considered hung. The actual kill mechanics
  need a real process handle and a timer, so they live in the Qt adapter
  (:mod:`gleplot.gui.compile_service`); this module only owns the constant.

Device-flag construction (``-d``/``-r``/future ``-cairo``) is unified in
:func:`gleplot.compiler.build_compile_args`, not duplicated here.

Two callers consume this module:

* :class:`gleplot.gui.preview.PreviewController` -- debounced, coalesced
  live-preview renders.
* :class:`gleplot.gui.export_dialog.ExportDialog` -- one-shot exports.

Both drive the actual OS process through
:class:`gleplot.gui.compile_service.CompileProcessRunner`, the "thin
QProcess adapter" that is the one Qt-specific piece of the pipeline.

Nothing in this module imports PySide6 or any other Qt binding -- verified
by ``tests/unit/test_compile_core.py::test_imports_without_pyside6``, which
imports this module in a subprocess with PySide6 unimportable and confirms
it never entered ``sys.modules``.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from gleplot.compiler import GLEError, parse_gle_errors

__all__ = [
    "DEFAULT_WATCHDOG_MS",
    "RenderCoalescer",
    "CompileOutcome",
    "evaluate_compile_output",
    "create_session_dir",
    "remove_session_dir",
]

#: Default watchdog timeout (milliseconds) for one compile job. A render
#: exceeding this is killed (SPEC §6.1: "watchdog kills hung compiles").
#: Single source of truth for both the preview controller and the export
#: path's :class:`~gleplot.gui.compile_service.CompileProcessRunner`.
DEFAULT_WATCHDOG_MS = 15000


@dataclass
class RenderCoalescer:
    """Sequence-number coalescing policy: "only the newest state is shown".

    A pure state machine with no timers or processes of its own -- the Qt
    adapter (or, in :class:`~gleplot.gui.preview.PreviewController`, the
    controller itself) drives it: :meth:`request` when a change arrives,
    :meth:`begin` when a job actually launches, :meth:`finish` when one
    completes (naturally or via a watchdog kill).

    The rule (SPEC §6.1, "overlapping renders coalesce so only the newest
    state is shown"): while a job is running, further requests don't start a
    second one; they set :attr:`pending`, so exactly one more job launches --
    built from the *latest* requested state -- as soon as the current one
    finishes. A result that finishes after an even-newer request already
    landed is treated the same way (:meth:`is_stale`), so a slow, superseded
    compile can never clobber a newer one that finished (or started) first.

    Examples
    --------
    Five rapid requests while nothing is running collapse to exactly one
    launch, and that launch always reflects the latest request::

        >>> c = RenderCoalescer()
        >>> for _ in range(5):
        ...     seq = c.request()
        >>> seq
        5
        >>> c.begin(seq)  # one job launches, from the latest state
        >>> c.pending
        False

    A request that lands *while* a job is running is coalesced into exactly
    one follow-up, not one per request::

        >>> c = RenderCoalescer()
        >>> first = c.request()
        >>> c.begin(first)
        >>> c.request(); c.request(); c.request()
        2
        3
        4
        >>> c.finish(first)  # a newer request landed mid-run -> restart
        True
        >>> c.pending
        False
    """

    requested_seq: int = 0
    running_seq: int = 0
    pending: bool = False

    def request(self) -> int:
        """Record a new request. Returns the new requested sequence number."""
        self.requested_seq += 1
        return self.requested_seq

    def begin(self, seq: int) -> None:
        """Record that sequence ``seq`` has just started running."""
        self.running_seq = seq

    def mark_pending(self) -> None:
        """Record that a request landed while a job was already running."""
        self.pending = True

    def is_stale(self, finished_seq: int) -> bool:
        """Whether a job that finished as ``finished_seq`` is superseded."""
        return finished_seq < self.requested_seq

    def finish(self, finished_seq: int) -> bool:
        """Record that the job launched as ``finished_seq`` has finished.

        Returns whether a follow-up job should launch immediately: either a
        newer request arrived mid-run (:attr:`pending`) or this result is
        itself stale (:meth:`is_stale`). Always clears :attr:`pending`.
        """
        restart = self.pending or self.is_stale(finished_seq)
        self.pending = False
        return restart

    def reset(self) -> None:
        """Return to the initial idle state (e.g. on controller shutdown)."""
        self.requested_seq = 0
        self.running_seq = 0
        self.pending = False


@dataclass
class CompileOutcome:
    """Structured result of one GLE compile job.

    ``raw_output`` is always populated (combined stdout+stderr) regardless
    of success, since some callers need it even when ``ok`` is True (e.g.
    the preview controller's calibration-record parsing reads GLE's
    ``print`` output from a *successful* compile). ``errors`` is populated
    whenever ``ok`` is False.
    """

    ok: bool
    output_path: Optional[Path]
    raw_output: str
    errors: List[GLEError] = field(default_factory=list)
    timed_out: bool = False


def evaluate_compile_output(
    exit_code: int,
    output_path: Optional[Path],
    raw_output: str,
    min_size: int = 1,
) -> CompileOutcome:
    """Turn a finished process's exit code / output file into a :class:`CompileOutcome`.

    A job is successful when the process exited ``0`` *and* the expected
    output file exists with at least ``min_size`` bytes (a 0-byte file is
    what a killed-mid-write GLE process can leave behind, so an existence
    check alone is not enough). On failure,
    :func:`~gleplot.compiler.parse_gle_errors` extracts structured errors
    from ``raw_output``; if it finds none (GLE printed nothing recognizable
    as a diagnostic) a single generic :class:`~gleplot.compiler.GLEError` is
    synthesized so callers never have to handle an empty error list on a
    failed outcome.
    """
    path = Path(output_path) if output_path is not None else None
    ok = (
        exit_code == 0
        and path is not None
        and path.exists()
        and path.stat().st_size >= min_size
    )
    errors: List[GLEError] = []
    if not ok:
        errors = parse_gle_errors(raw_output)
        if not errors:
            errors = [
                GLEError(
                    file=None,
                    line=None,
                    column=None,
                    message="GLE render failed (no output produced).",
                )
            ]
    return CompileOutcome(ok=ok, output_path=path, raw_output=raw_output, errors=errors)


def create_session_dir(prefix: str = "gleplot_compile_") -> Path:
    """Create a fresh temp session directory for a compile job.

    Compilation needs a writable working directory (GLE's contour/``fitz``
    paths write intermediate files next to the script; SPEC §6.1). Preview
    creates one lazily and reuses it for the controller's lifetime; a
    one-shot job (like export) that already targets a writable destination
    directory has no need for one at all.
    """
    return Path(tempfile.mkdtemp(prefix=prefix))


def remove_session_dir(path: Optional[Path]) -> None:
    """Remove a session directory created by :func:`create_session_dir`.

    Silently ignores ``None`` or an already-removed path -- this is teardown
    code and must never raise.
    """
    if path is not None and Path(path).exists():
        shutil.rmtree(path, ignore_errors=True)

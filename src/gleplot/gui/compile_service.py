"""Thin QProcess adapter for the async GLE compile service (Track G3).

:class:`CompileProcessRunner` is the one Qt-specific piece of the compile
pipeline: it owns launching a ``gle`` invocation via
:class:`~PySide6.QtCore.QProcess`, enforcing the watchdog timeout, collecting
its output streams, and turning the result into a
:class:`~gleplot.gui.compile_core.CompileOutcome` via
:func:`~gleplot.gui.compile_core.evaluate_compile_output`. Argument
construction (:func:`gleplot.compiler.build_compile_args`), sequence
coalescing (:class:`~gleplot.gui.compile_core.RenderCoalescer`), and result
evaluation are all Qt-free and live in :mod:`gleplot.gui.compile_core`.

Both consumers of the compile service use this same class:

* :class:`~gleplot.gui.preview.PreviewController` -- one runner per
  debounced/coalesced render.
* :class:`~gleplot.gui.export_dialog.ExportDialog` -- one runner per export,
  with a Cancel button wired to :meth:`CompileProcessRunner.cancel`.

A runner is single-use: construct a new instance per job (cheap -- it is a
thin wrapper around one :class:`QProcess`), call :meth:`start`, and consume
the :data:`finished` signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Union

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from gleplot.compiler import GLEError
from gleplot.gui.compile_core import (
    DEFAULT_WATCHDOG_MS,
    CompileOutcome,
    evaluate_compile_output,
)

__all__ = ["CompileProcessRunner"]


class CompileProcessRunner(QObject):
    """Runs one GLE compile invocation off the caller's blocking code path.

    Unlike calling :func:`subprocess.run` directly (what
    ``gui/export_dialog.py`` used to do), starting a job here never blocks
    the calling thread: :meth:`start` returns immediately after launching
    the :class:`QProcess`, and the result arrives later via the
    :data:`finished` signal, processed on the Qt event loop like any other
    I/O completion.

    Signals
    -------
    started()
        Emitted synchronously from :meth:`start`, right before the process
        is actually launched.
    finished(object)
        Emitted exactly once per job, with a
        :class:`~gleplot.gui.compile_core.CompileOutcome` -- whether the
        process finished normally, was killed by the watchdog, or failed to
        start at all. Never emitted for a job stopped via :meth:`cancel`.
    """

    started = Signal()
    finished = Signal(object)  # CompileOutcome

    def __init__(
        self,
        watchdog_ms: int = DEFAULT_WATCHDOG_MS,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._watchdog_ms = watchdog_ms
        self._process: Optional[QProcess] = None
        self._output_path: Optional[Path] = None

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(watchdog_ms)
        self._watchdog.timeout.connect(self._on_watchdog_timeout)

    @property
    def is_running(self) -> bool:
        """Whether a job is currently in flight."""
        return self._process is not None

    def start(
        self,
        gle_path: str,
        working_dir: Union[str, Path],
        args: Sequence[str],
        output_path: Optional[Union[str, Path]],
    ) -> None:
        """Launch ``gle_path args`` in ``working_dir``.

        Parameters
        ----------
        gle_path : str
            Path to the ``gle`` executable (see
            :func:`gleplot.compiler.find_gle`).
        working_dir : str or Path
            Process working directory. GLE writes intermediate files
            relative to this (contour/``fitz`` outputs), so it must be
            writable -- see SPEC §6.1.
        args : sequence of str
            Command-line arguments, typically built by
            :func:`gleplot.compiler.build_compile_args`.
        output_path : str or Path, optional
            The file the compile is expected to produce; used by
            :func:`~gleplot.gui.compile_core.evaluate_compile_output` to
            decide success. ``None`` is accepted for callers that only care
            about the exit code (evaluated as failure unless a path is
            given, matching the "no expected output" case).

        Raises
        ------
        RuntimeError
            If a job is already running on this instance -- construct a new
            :class:`CompileProcessRunner` per job instead of reusing one.
        """
        if self._process is not None:
            raise RuntimeError(
                "CompileProcessRunner.start() called while a job is already "
                "running; construct a new instance per job."
            )

        self._output_path = Path(output_path) if output_path is not None else None

        proc = QProcess(self)
        proc.setWorkingDirectory(str(working_dir))
        # Keep stdout/stderr separate on read (some GLE builds put
        # diagnostics on one stream and print()-style output on the other);
        # they are concatenated when building the outcome, same as before.
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.finished.connect(self._on_process_finished)
        proc.errorOccurred.connect(self._on_process_error)
        self._process = proc

        self._watchdog.start()
        self.started.emit()
        proc.start(gle_path, list(args))

    def cancel(self) -> None:
        """Kill the running job, if any, without emitting :data:`finished`.

        Used both for teardown (a controller/dialog going away mid-render)
        and for an explicit user cancel action.
        """
        self._teardown(kill=True)

    # ------------------------------------------------------------------
    # QProcess callbacks
    # ------------------------------------------------------------------
    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        self._watchdog.stop()
        proc = self._process
        self._process = None

        raw = ""
        if proc is not None:
            stdout = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
            stderr = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
            raw = stdout + stderr
            proc.deleteLater()

        outcome = evaluate_compile_output(exit_code, self._output_path, raw)
        self.finished.emit(outcome)

    def _on_process_error(self, error) -> None:
        # A start/crash error; ``finished`` may or may not follow. Only act
        # here when the process never started at all -- if it did start and
        # later fails, ``finished`` handles it (matching QProcess's own
        # contract: FailedToStart is the one QProcess::ProcessError that is
        # never followed by a ``finished`` signal).
        if error != QProcess.ProcessError.FailedToStart:
            return
        self._watchdog.stop()
        proc = self._process
        self._process = None
        if proc is not None:
            proc.deleteLater()
        outcome = CompileOutcome(
            ok=False,
            output_path=self._output_path,
            raw_output="FailedToStart",
            errors=[
                GLEError(
                    file=None,
                    line=None,
                    column=None,
                    message="GLE process failed to start.",
                )
            ],
        )
        self.finished.emit(outcome)

    def _on_watchdog_timeout(self) -> None:
        """Kill a job that exceeded the watchdog timeout and report it."""
        proc = self._process
        if proc is None:
            return
        # Disconnect first so kill() doesn't also drive _on_process_finished
        # -- this method reports the synthetic timeout outcome itself.
        try:
            proc.finished.disconnect(self._on_process_finished)
        except (RuntimeError, TypeError):
            pass
        proc.kill()
        proc.waitForFinished(2000)
        proc.deleteLater()
        self._process = None

        outcome = CompileOutcome(
            ok=False,
            output_path=self._output_path,
            raw_output="watchdog timeout",
            errors=[
                GLEError(
                    file=None,
                    line=None,
                    column=None,
                    message=(
                        f"GLE render timed out after "
                        f"{self._watchdog_ms // 1000}s and was killed."
                    ),
                )
            ],
            timed_out=True,
        )
        self.finished.emit(outcome)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    def _teardown(self, kill: bool) -> None:
        self._watchdog.stop()
        if self._process is None:
            return
        try:
            self._process.finished.disconnect(self._on_process_finished)
        except (RuntimeError, TypeError):
            pass
        try:
            self._process.errorOccurred.disconnect(self._on_process_error)
        except (RuntimeError, TypeError):
            pass
        if kill:
            self._process.kill()
            self._process.waitForFinished(2000)
        self._process.deleteLater()
        self._process = None

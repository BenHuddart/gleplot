"""Tests for gleplot.gui.compile_service.CompileProcessRunner (Track G3).

The "thin QProcess adapter": owns launching one GLE compile invocation,
enforcing the watchdog timeout, and turning the result into a
gleplot.gui.compile_core.CompileOutcome. These tests exercise it directly
(no PreviewController/ExportDialog involved) using real, short-lived
subprocesses so the watchdog-kill path is exercised deterministically and
quickly, without depending on GLE being installed.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from gleplot.gui.compile_core import CompileOutcome
from gleplot.gui.compile_service import CompileProcessRunner

#: A real, always-available executable used as a stand-in for `gle` --
#: CompileProcessRunner has no GLE-specific knowledge, so any long/short-
#: lived process exercises its launch/watchdog/finish mechanics identically.
_SLEEP = "/bin/sleep"
_TRUE = "/bin/true" if Path("/bin/true").exists() else "/usr/bin/true"


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _wait_until(predicate, timeout_ms=5000):
    loop = QEventLoop()
    timed_out = {"value": False}

    poll = QTimer()
    poll.setInterval(10)

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


def _run_and_wait(runner, gle_path, working_dir, args, output_path, timeout_ms=5000):
    results = []
    runner.finished.connect(results.append)
    runner.start(gle_path, working_dir, args, output_path)
    assert _wait_until(lambda: results, timeout_ms), "job never finished"
    return results[0]


# ---------------------------------------------------------------------------
# Watchdog kill (Track G3 acceptance criterion 2)
# ---------------------------------------------------------------------------
def test_watchdog_kills_hung_process_and_reports_timeout(qapp, tmp_path):
    """A process that runs far longer than the watchdog timeout must be
    killed, and reported via `finished` as a timed-out failure -- well
    before it would exit on its own."""
    runner = CompileProcessRunner(watchdog_ms=150, parent=None)
    outcome = _run_and_wait(
        runner,
        _SLEEP,
        tmp_path,
        ["30"],  # would run for 30s if not killed
        output_path=None,
        timeout_ms=5000,  # generous ceiling; the watchdog should fire ~150ms in
    )
    assert isinstance(outcome, CompileOutcome)
    assert outcome.ok is False
    assert outcome.timed_out is True
    assert outcome.errors
    assert "timed out" in outcome.errors[0].message
    assert not runner.is_running


def test_watchdog_does_not_fire_for_a_fast_process(qapp, tmp_path):
    """A process finishing well within the watchdog window must not be
    reported as timed out."""
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    outcome = _run_and_wait(
        runner,
        _TRUE,
        tmp_path,
        [],
        output_path=None,
        timeout_ms=5000,
    )
    assert outcome.timed_out is False
    # /bin/true exits 0 with no output file requested -> evaluate_compile_output
    # reports failure only because no output_path was given/produced; the
    # important assertion here is specifically that the watchdog didn't fire.


# ---------------------------------------------------------------------------
# Normal finish / output evaluation
# ---------------------------------------------------------------------------
def test_successful_job_reports_ok_with_output_file(qapp, tmp_path):
    out = tmp_path / "out.txt"
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    # `sh -c "echo hi > out.txt"` via /bin/sh -- avoids any GLE dependency
    # while still producing a real output file for evaluate_compile_output.
    outcome = _run_and_wait(
        runner,
        "/bin/sh",
        tmp_path,
        ["-c", f"echo hi > {out.name}"],
        output_path=out,
    )
    assert outcome.ok is True
    assert outcome.output_path == out
    assert outcome.errors == []


def test_failed_to_start_reports_structured_error(qapp, tmp_path):
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    outcome = _run_and_wait(
        runner,
        str(tmp_path / "does_not_exist_at_all"),
        tmp_path,
        [],
        output_path=None,
    )
    assert outcome.ok is False
    assert outcome.errors
    assert "failed to start" in outcome.errors[0].message.lower()


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------
def test_cancel_kills_process_without_emitting_finished(qapp, tmp_path):
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    results = []
    runner.finished.connect(results.append)
    runner.start(_SLEEP, tmp_path, ["30"], output_path=None)
    assert runner.is_running

    runner.cancel()

    assert not runner.is_running
    # Give the event loop a couple of turns in case a stray signal was
    # already queued; cancel() must not have emitted `finished`.
    _wait_until(lambda: False, 200)
    assert results == []


def test_is_running_reflects_process_lifecycle(qapp, tmp_path):
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    assert not runner.is_running
    outcome_holder = []
    runner.finished.connect(outcome_holder.append)
    runner.start(_TRUE, tmp_path, [], output_path=None)
    assert runner.is_running
    assert _wait_until(lambda: outcome_holder, 5000)
    assert not runner.is_running


def test_start_while_running_raises(qapp):
    runner = CompileProcessRunner(watchdog_ms=5000, parent=None)
    runner.start(_SLEEP, Path("."), ["5"], output_path=None)
    try:
        with pytest.raises(RuntimeError):
            runner.start(_SLEEP, Path("."), ["5"], output_path=None)
    finally:
        runner.cancel()

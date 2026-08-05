"""Unit tests for gleplot.gui.compile_core: the Qt-free async compile core.

Covers:
- Qt-freeness: importing gleplot.gui.compile_core must not import PySide6
  (Track G3 acceptance criterion 4 -- see gleplot.gui.geometry for the
  established pattern of a Qt-free module living under gleplot.gui).
- RenderCoalescer: the "overlapping renders coalesce to the newest state"
  policy (SPEC §6.1), exercised as a pure state machine with no Qt/GLE
  involved.
- evaluate_compile_output: turning exit-code/output-file/raw-text into a
  structured CompileOutcome, reusing gleplot.compiler.parse_gle_errors.
- create_session_dir / remove_session_dir: session temp-dir bookkeeping.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gleplot.compiler import GLEError
from gleplot.gui.compile_core import (
    DEFAULT_WATCHDOG_MS,
    CompileOutcome,
    RenderCoalescer,
    create_session_dir,
    evaluate_compile_output,
    remove_session_dir,
)


# ---------------------------------------------------------------------------
# Qt-free import assertion (Track G3 acceptance criterion 4)
# ---------------------------------------------------------------------------
def test_compile_core_import_does_not_pull_in_qt():
    """Importing gleplot.gui.compile_core in a fresh subprocess must not
    import PySide6 -- the module is the Qt-free core of the async compile
    service; only gleplot.gui.compile_service (the "thin QProcess adapter")
    is allowed to depend on Qt.
    """
    code = (
        "import sys\n"
        "import gleplot.gui.compile_core\n"
        "bad = [m for m in sys.modules if m == 'PySide6' or m.startswith('PySide6.')]\n"
        "print(','.join(bad))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )
    assert result.returncode == 0, result.stderr
    leaked = result.stdout.strip()
    assert leaked == "", f"gleplot.gui.compile_core import pulled in: {leaked}"


# ---------------------------------------------------------------------------
# RenderCoalescer
# ---------------------------------------------------------------------------
def test_coalescer_starts_idle():
    c = RenderCoalescer()
    assert c.requested_seq == 0
    assert c.running_seq == 0
    assert c.pending is False


def test_single_request_launches_and_finishes_cleanly():
    c = RenderCoalescer()
    seq = c.request()
    assert seq == 1
    c.begin(seq)
    assert c.running_seq == 1
    # Nothing newer arrived and this isn't stale -> no restart needed.
    assert c.finish(seq) is False
    assert c.pending is False


def test_rapid_successive_requests_collapse_to_newest():
    """Five rapid requests while nothing is running must still result in
    exactly one launch, and that launch must reflect the *latest* request
    (SPEC §6.1: "overlapping renders coalesce so only the newest state is
    shown"). This mirrors what PreviewController._start_render /
    ._launch do around a single RenderCoalescer.
    """
    c = RenderCoalescer()
    launches = 0
    last_seq = None

    # Simulate a controller: only ever launches when nothing is running,
    # exactly as PreviewController._start_render / ._launch do.
    running = False
    for _ in range(5):
        seq = c.request()
        if not running:
            c.begin(seq)
            running = True
            launches += 1
            last_seq = seq
        else:
            c.mark_pending()

    assert launches == 1
    # The one launch is the *first* request (nothing was running yet); the
    # four that landed mid-run are coalesced into a single pending restart,
    # not four separate launches.
    assert last_seq == 1
    assert c.requested_seq == 5
    assert c.pending is True  # four extra requests landed mid-run

    # Finishing the one in-flight job reports a restart is needed (pending),
    # and the restart launches from the latest requested sequence (5), not
    # from each intermediate request individually.
    assert c.finish(last_seq) is True
    assert c.pending is False
    seq2 = c.requested_seq
    assert seq2 == 5
    c.begin(seq2)
    assert c.finish(seq2) is False  # settled: no further restart


def test_stale_result_triggers_restart_even_without_pending():
    """A result that finishes after an even-newer request already landed
    (but *before* mark_pending() was called, e.g. the request bumped the
    sequence in the same turn the previous job's finish() is processed)
    must still be recognised as stale and trigger a restart."""
    c = RenderCoalescer()
    seq1 = c.request()
    c.begin(seq1)
    # A second request lands and is itself launched as a *new* job before
    # the first one's finish() is even processed (out-of-order completion) --
    # is_stale() is the guard against showing the older result.
    seq2 = c.request()
    assert c.is_stale(seq1) is True
    assert c.is_stale(seq2) is False
    # finish() on the stale seq1 reports a restart is needed even though
    # `pending` was never explicitly set.
    assert c.finish(seq1) is True


def test_finish_always_clears_pending():
    c = RenderCoalescer()
    seq = c.request()
    c.begin(seq)
    c.mark_pending()
    assert c.pending is True
    c.finish(seq)
    assert c.pending is False


def test_reset_returns_to_idle():
    c = RenderCoalescer()
    c.request()
    c.request()
    c.begin(2)
    c.mark_pending()
    c.reset()
    assert c.requested_seq == 0
    assert c.running_seq == 0
    assert c.pending is False


# ---------------------------------------------------------------------------
# evaluate_compile_output
# ---------------------------------------------------------------------------
def test_evaluate_success(tmp_path):
    out = tmp_path / "out.png"
    out.write_bytes(b"\x89PNG\r\n")
    outcome = evaluate_compile_output(0, out, "GLE 4.3.9[foo.gle]-C-R-\n")
    assert isinstance(outcome, CompileOutcome)
    assert outcome.ok is True
    assert outcome.output_path == out
    assert outcome.errors == []
    assert outcome.timed_out is False


def test_evaluate_nonzero_exit_is_failure_with_parsed_errors(tmp_path):
    raw = (
        ">> bad.gle (3) |let d1 = sin(x frum 0 to 2*pi|\n"
        ">>                                           ^\n"
        ">> Error: expected closing ')'\n"
    )
    outcome = evaluate_compile_output(1, tmp_path / "missing.pdf", raw)
    assert outcome.ok is False
    assert len(outcome.errors) == 1
    assert outcome.errors[0].line == 3
    assert "expected closing" in outcome.errors[0].message


def test_evaluate_missing_output_file_is_failure_even_with_exit_zero(tmp_path):
    # A killed-mid-write or otherwise-lying exit code shouldn't be trusted
    # over the actual filesystem state.
    outcome = evaluate_compile_output(0, tmp_path / "never_written.pdf", "")
    assert outcome.ok is False
    assert outcome.errors  # synthesized generic error, since raw is empty
    assert "no output produced" in outcome.errors[0].message


def test_evaluate_zero_byte_output_is_failure(tmp_path):
    out = tmp_path / "empty.pdf"
    out.write_bytes(b"")
    outcome = evaluate_compile_output(0, out, "")
    assert outcome.ok is False


def test_evaluate_unparseable_failure_output_synthesizes_generic_error(tmp_path):
    outcome = evaluate_compile_output(
        1, tmp_path / "missing.pdf", "totally unstructured blowup"
    )
    assert outcome.ok is False
    assert len(outcome.errors) == 1
    assert isinstance(outcome.errors[0], GLEError)


def test_evaluate_none_output_path_is_failure():
    outcome = evaluate_compile_output(0, None, "")
    assert outcome.ok is False


def test_evaluate_raw_output_preserved_on_success(tmp_path):
    # Some callers (the preview controller's calibration parsing) need the
    # raw text even on a successful compile.
    out = tmp_path / "out.png"
    out.write_bytes(b"\x89PNG\r\n")
    raw = "GLE banner\ngleplot-cal 0 0 1 0 1 0 0 1 1\n"
    result = evaluate_compile_output(0, out, raw)
    assert result.ok is True
    assert result.raw_output == raw


# ---------------------------------------------------------------------------
# Session directory helpers
# ---------------------------------------------------------------------------
def test_create_session_dir_returns_existing_writable_directory():
    d = create_session_dir(prefix="gleplot_test_session_")
    try:
        assert d.exists()
        assert d.is_dir()
        probe = d / "probe.txt"
        probe.write_text("ok")
        assert probe.read_text() == "ok"
    finally:
        remove_session_dir(d)
    assert not d.exists()


def test_remove_session_dir_is_idempotent_and_accepts_none():
    d = create_session_dir()
    remove_session_dir(d)
    assert not d.exists()
    # Second removal, and a None path, must not raise.
    remove_session_dir(d)
    remove_session_dir(None)


def test_default_watchdog_ms_is_positive():
    assert DEFAULT_WATCHDOG_MS > 0

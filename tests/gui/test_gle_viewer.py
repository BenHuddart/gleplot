"""Tests for :mod:`gleplot.gui.gle_viewer` (Track G/H: hand-written .gle preview/export).

These exercise the real GLE compiler and are marked ``xfail`` (non-strict)
when GLE is not installed, matching the convention in ``test_preview.py``.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from gleplot.compiler import find_gle
from gleplot.gui import gle_viewer
from gleplot.gui.gle_viewer import compile_gle_preview, export_gle_file

_GLE_AVAILABLE = find_gle() is not None

_VALID_GLE = """\
size 10 8
begin graph
    scale auto
    xaxis min 0 max 3
    yaxis min 0 max 9
    let d1 = x^2 from 0 to 3
    d1 line color blue
end graph
"""

_INVALID_GLE = """\
size 10 8
begin graph
    let d1 = sin(x frum 0 to 2*pi
end graph
"""


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_compile_gle_preview_valid_file_succeeds(tmp_path):
    gle_path = _write(tmp_path, "valid.gle", _VALID_GLE)

    result = compile_gle_preview(gle_path, dpi=100)

    assert result.success is True
    assert result.png_path is not None
    assert result.png_path.exists()
    assert result.png_path.suffix == ".png"
    assert result.errors == []


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_compile_gle_preview_respects_output_dir(tmp_path):
    src_dir = tmp_path / "src_dir"
    src_dir.mkdir()
    gle_path = _write(src_dir, "valid.gle", _VALID_GLE)
    out_dir = tmp_path / "out_dir"

    result = compile_gle_preview(gle_path, dpi=100, output_dir=out_dir)

    assert result.success is True
    assert result.png_path.parent == out_dir


def test_compile_gle_preview_invalid_file_reports_structured_errors(tmp_path):
    gle_path = _write(tmp_path, "invalid.gle", _INVALID_GLE)

    result = compile_gle_preview(gle_path, dpi=100)

    assert result.success is False
    assert result.png_path is None
    assert result.errors
    # Structured errors should carry line numbers when GLE is available;
    # when GLE itself is missing we still get a single synthetic error.
    if _GLE_AVAILABLE:
        assert any(e.line is not None for e in result.errors)


def test_compile_gle_preview_missing_file_reports_error(tmp_path):
    missing = tmp_path / "nope.gle"

    result = compile_gle_preview(missing)

    assert result.success is False
    assert result.png_path is None
    assert result.errors
    assert "not found" in result.errors[0].message.lower()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_gle_file_to_pdf(tmp_path):
    gle_path = _write(tmp_path, "valid.gle", _VALID_GLE)
    target = tmp_path / "export_out" / "result.pdf"

    result = export_gle_file(gle_path, target, format="pdf")

    assert result.success is True
    assert result.png_path == target
    assert target.exists()


@pytest.mark.xfail(not _GLE_AVAILABLE, reason="GLE not installed", strict=False)
def test_export_gle_file_to_png_with_dpi(tmp_path):
    gle_path = _write(tmp_path, "valid.gle", _VALID_GLE)
    target = tmp_path / "result.png"

    result = export_gle_file(gle_path, target, format="png", dpi=100)

    assert result.success is True
    assert target.exists()


def test_export_gle_file_invalid_reports_errors(tmp_path):
    gle_path = _write(tmp_path, "invalid.gle", _INVALID_GLE)
    target = tmp_path / "result.pdf"

    result = export_gle_file(gle_path, target, format="pdf")

    assert result.success is False
    assert not target.exists()
    assert result.errors


# ----------------------------------------------------------------------
# FIX 5: a failed compile must still expose work_dir (temp-dir leak fix).
# ----------------------------------------------------------------------
def test_failed_compile_exposes_work_dir(tmp_path, monkeypatch):
    """When _compile creates a temp dir (output_dir omitted) but the compile
    fails, the created dir must be reported via result.work_dir so the caller
    can clean it up (otherwise every failed .gle preview leaks a directory)."""
    from gleplot.compiler import GLECompileError

    gle_path = _write(tmp_path, "valid.gle", _VALID_GLE)

    class _FakeCompiler:
        def compile(self, *args, **kwargs):
            raise GLECompileError("boom", raw_output="synthetic failure")

    monkeypatch.setattr(gle_viewer, "GLECompiler", _FakeCompiler)

    result = compile_gle_preview(gle_path, dpi=100)  # output_dir omitted -> mkdtemp

    assert result.success is False
    assert result.png_path is None
    # The created working directory must be exposed for cleanup.
    assert result.work_dir is not None
    assert result.work_dir.exists()

    # Cleanup the leaked-but-now-tracked dir.
    import shutil
    shutil.rmtree(result.work_dir, ignore_errors=True)


def test_caller_supplied_output_dir_is_the_work_dir(tmp_path, monkeypatch):
    """When output_dir is supplied, work_dir reports that same dir (the caller
    owns it either way, but main_window only auto-cleans mkdtemp'd dirs)."""
    from gleplot.compiler import GLECompileError

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    gle_path = _write(src_dir, "valid.gle", _VALID_GLE)
    out_dir = tmp_path / "out"

    class _FakeCompiler:
        def compile(self, *args, **kwargs):
            raise GLECompileError("boom", raw_output="synthetic failure")

    monkeypatch.setattr(gle_viewer, "GLECompiler", _FakeCompiler)

    result = compile_gle_preview(gle_path, dpi=100, output_dir=out_dir)
    assert result.success is False
    assert result.work_dir == out_dir


# ----------------------------------------------------------------------
# FIX 6: a locked/unreadable sidecar must not crash File>Open -- the copy
# loop must produce a structured failure instead of raising.
# ----------------------------------------------------------------------
def test_sidecar_copy_permissionerror_is_structured_failure(tmp_path, monkeypatch):
    """A PermissionError from shutil.copy2 while bringing sidecar data files
    into the work dir must produce a failed GlePreviewResult, not an
    uncaught exception that crashes File>Open."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    gle_path = _write(src_dir, "plot.gle", _VALID_GLE)
    # A sibling .dat that the copy loop will try to bring along.
    (src_dir / "data.dat").write_text("1 2\n3 4\n", encoding="utf-8")

    real_copy2 = gle_viewer.shutil.copy2

    def flaky_copy2(src, dst, *args, **kwargs):
        if str(src).endswith(".dat"):
            raise PermissionError(f"locked: {src}")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(gle_viewer.shutil, "copy2", flaky_copy2)

    # Must NOT raise; must return a structured failure naming the file.
    result = compile_gle_preview(gle_path, dpi=100, output_dir=tmp_path / "work")

    assert result.success is False
    assert result.errors
    assert any("data.dat" in (e.message or "") for e in result.errors)
    # work_dir still exposed for cleanup.
    assert result.work_dir is not None

"""Reference-mode data paths: quoting, absolutizing, and preview compiles.

Regression tests for the v1-verification bug where opening a .gle whose
series reference data files by relative path broke the live preview: the
preview compiles a temp-dir copy, where relative references cannot
resolve. Also covers filename quoting for paths containing spaces (e.g.
OneDrive directories).
"""

from pathlib import Path

import pytest

import gleplot as glp
from gleplot.compiler import find_gle, GLECompiler
from gleplot.figure import Figure
from gleplot.parser.recognizer import parse_gle_figure

requires_gle = pytest.mark.skipif(find_gle() is None, reason="GLE not installed")


def _write_data(path: Path) -> None:
    path.write_text("0 0\n1 1\n2 4\n3 9\n", encoding="utf-8")


def _reference_figure(data_path: str):
    fig = glp.figure(data_prefix="refpath")
    ax = fig.add_subplot(1, 1, 1)
    ax.line_from_file(data_path, 1, 2, label="ref")
    return fig


class TestFilenameQuoting:
    def test_plain_names_stay_bare(self, tmp_path):
        _write_data(tmp_path / "plain.dat")
        fig = _reference_figure("plain.dat")
        out = tmp_path / "fig.gle"
        fig.savefig_gle(str(out))
        assert "data plain.dat" in out.read_text()

    def test_spacey_names_are_quoted(self, tmp_path):
        fig = _reference_figure("my data file.dat")
        out = tmp_path / "fig.gle"
        fig.savefig_gle(str(out))
        assert 'data "my data file.dat"' in out.read_text()

    def test_quoted_spacey_path_round_trips(self, tmp_path):
        spacey = tmp_path / "dir with spaces"
        spacey.mkdir()
        _write_data(spacey / "d.dat")
        abs_posix = (spacey / "d.dat").resolve().as_posix()
        fig = _reference_figure(abs_posix)
        out = tmp_path / "fig.gle"
        fig.savefig_gle(str(out))
        rec = parse_gle_figure(out)
        fs = rec.figure.axes_list[0].file_series
        assert len(fs) == 1
        assert fs[0]["data_file"] == abs_posix
        assert "data_error" not in fs[0]


class TestAbsolutize:
    def test_relative_becomes_absolute_posix(self, tmp_path):
        _write_data(tmp_path / "rel.dat")
        fig = _reference_figure("rel.dat")
        fig.absolutize_file_references(tmp_path)
        got = fig.axes_list[0].file_series[0]["data_file"]
        assert Path(got).is_absolute()
        assert "\\" not in got
        assert got == (tmp_path / "rel.dat").resolve().as_posix()

    def test_absolute_left_untouched(self, tmp_path):
        _write_data(tmp_path / "abs.dat")
        abs_posix = (tmp_path / "abs.dat").resolve().as_posix()
        fig = _reference_figure(abs_posix)
        fig.absolutize_file_references(tmp_path / "elsewhere")
        assert fig.axes_list[0].file_series[0]["data_file"] == abs_posix


@requires_gle
class TestPreviewStyleCompile:
    def test_temp_dir_compile_of_relative_references(self, tmp_path):
        """The preview pipeline: parse -> snapshot copy -> absolutize ->
        generate in a DIFFERENT directory -> compile with real GLE."""
        project = tmp_path / "project dir"  # spaces on purpose
        project.mkdir()
        _write_data(project / "measured.dat")
        fig = _reference_figure("measured.dat")
        gle_path = project / "fig.gle"
        fig.savefig_gle(str(gle_path))

        rec = parse_gle_figure(gle_path)
        assert not any(w.startswith("data:") for w in rec.warnings)

        # Simulate PreviewController: disposable copy, absolutize, temp dir.
        work = Figure.from_dict(rec.figure.to_dict())
        work.absolutize_file_references(project)
        session = tmp_path / "session"
        session.mkdir()
        script = session / "preview.gle"
        work.savefig_gle(str(script))
        out = GLECompiler().compile(str(script), output_format="png", dpi=80)
        assert Path(out).exists()
        assert Path(out).stat().st_size > 1000

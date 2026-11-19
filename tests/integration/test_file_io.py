"""Integration tests for file I/O operations."""

from unittest.mock import Mock

import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler
from tests.parser.test_recognizer import _CUSTOM_MARKER_DAT, _CUSTOM_MARKER_SRC


class TestFileIO:
    """Test file I/O operations."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path):
        """Create fresh figure and temp directory for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([1, 2, 3], [1, 4, 9], label="test")

        self.tempdir = tmp_path
        yield
        glp.close()

    def test_save_gle_script(self):
        """Test saving as GLE script."""
        output_file = self.tempdir / "test.gle"
        result = self.fig.savefig_gle(str(output_file))

        assert result.exists()
        content = result.read_text()
        assert "begin graph" in content
        assert "end graph" in content

    def test_save_with_gle_extension(self):
        """Test saving with .gle extension."""
        output_file = self.tempdir / "test.gle"
        result = self.fig.savefig(str(output_file))

        assert result.exists()
        assert result.suffix == ".gle"

    def test_gle_content_has_data(self):
        """Test GLE content includes data files."""
        output_file = self.tempdir / "test.gle"
        result = self.fig.savefig(str(output_file))

        content = result.read_text()
        assert "data_" in content

    def test_save_gle_script_in_folder(self):
        """Test saving a GLE export into a dedicated folder."""
        output_file = self.tempdir / "test.gle"
        result = self.fig.savefig_gle(str(output_file), folder=True)

        export_dir = self.tempdir / "test.gleplot"
        assert result == export_dir / "test.gle"
        assert result.exists()
        assert export_dir.is_dir()
        assert len(list(export_dir.glob("*.dat"))) >= 1
        assert not output_file.exists()

    def test_save_without_extension_in_folder_defaults_to_gle(self):
        """Test folder exports also work when savefig infers the .gle suffix."""
        output_file = self.tempdir / "batch_run"
        result = self.fig.savefig(str(output_file), folder=True)

        export_dir = self.tempdir / "batch_run.gleplot"
        assert result == export_dir / "batch_run.gle"
        assert result.exists()
        assert len(list(export_dir.glob("*.dat"))) >= 1
        assert not (self.tempdir / "batch_run.gle").exists()

    def test_save_compiled_output_in_folder_uses_foldered_gle_path(self):
        """Test compiled exports route the intermediate GLE file into the folder."""
        compiler = Mock()
        self.fig.compiler = compiler

        output_file = self.tempdir / "report.pdf"
        result = self.fig.savefig(str(output_file), folder=True)

        export_dir = self.tempdir / "report.gleplot"
        assert result == export_dir / "report.pdf"
        assert (export_dir / "report.gle").exists()
        assert len(list(export_dir.glob("*.dat"))) >= 1
        compiler.compile.assert_called_once_with(
            str(export_dir / "report.gle"),
            "pdf",
            dpi=self.fig.dpi,
            cairo=False,
            transparent=False,
            grayscale=False,
        )
        assert not output_file.exists()

    @pytest.mark.gle
    def test_savefig_auto_detects_jpg(self):
        """savefig should auto-detect the 'jpg' format from a .jpg suffix."""
        output_file = self.tempdir / "test.jpg"
        result = self.fig.savefig(str(output_file))

        assert result.suffix == ".jpg"
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.gle
    def test_savefig_auto_detects_jpeg_as_jpg(self):
        """A .jpeg suffix should compile via GLE's 'jpg' device and produce a .jpg file."""
        output_file = self.tempdir / "test.jpeg"
        result = self.fig.savefig(str(output_file))

        assert result.suffix == ".jpg"
        assert result.exists()
        assert result.stat().st_size > 0

    @pytest.mark.gle
    def test_savefig_auto_detects_svg(self):
        """savefig should auto-detect the 'svg' format from a .svg suffix."""
        output_file = self.tempdir / "test.svg"
        # The default font is a PostScript one, which SVG's Cairo swaps.
        with pytest.warns(UserWarning, match="SVG output is drawn"):
            result = self.fig.savefig(str(output_file))

        assert result.suffix == ".svg"
        assert result.exists()
        assert result.stat().st_size > 0

    def test_savefig_unknown_suffix_defaults_to_gle(self):
        """An unrecognized suffix should preserve the existing default: .gle only."""
        output_file = self.tempdir / "test.unknownext"
        result = self.fig.savefig(str(output_file))

        assert result.suffix == ".gle"
        assert result.exists()

    def test_save_gle_script_uses_utf8_for_unicode_labels(self):
        """GLE scripts should preserve Unicode labels across platforms."""
        label = "Time (\u03bcs)"
        self.ax.set_xlabel(label)
        output_file = self.tempdir / "unicode.gle"

        result = self.fig.savefig_gle(str(output_file))

        raw = result.read_bytes()
        assert label.encode("utf-8") in raw
        assert (
            raw.decode("utf-8").splitlines()
            == result.read_text(encoding="utf-8").splitlines()
        )


@pytest.mark.gle
def test_reopened_custom_marker_definitions_compile(tmp_path):
    """A re-saved script still defines the custom markers its datasets use."""
    for name, content in _CUSTOM_MARKER_DAT.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    src = tmp_path / "cm.gle"
    src.write_text(_CUSTOM_MARKER_SRC, encoding="utf-8")
    out = tmp_path / "again.gle"
    with pytest.warns(UserWarning, match="programmatic:"):
        fig = glp.open_gle(str(src))
    fig.savefig_gle(str(out))
    # GLE rejects a marker name it has no definition for.
    assert GLECompiler().compile(str(out), output_format="pdf").exists()

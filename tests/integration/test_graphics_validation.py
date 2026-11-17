"""Advanced graphics validation tests using image analysis."""

import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler

from .graphics_analysis import (
    EPSAnalyzer,
    PDFAnalyzer,
    PNGAnalyzer,
    validate_graphics_file,
)

pytestmark = pytest.mark.gle


class TestGraphicsValidation:
    """Test validation of generated graphics files using image analysis."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path):
        """Set up test fixtures."""
        glp.close()
        self.tempdir = tmp_path
        self.compiler = GLECompiler()

        # Create a test figure
        self.fig = glp.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([1, 2, 3, 4, 5], [1, 4, 2, 5, 3], label="Test", color="blue")
        self.ax.set_title("Test Graphics")
        yield
        glp.close()

    def test_validate_pdf_structure(self):
        """Test PDF structure validation."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        pdf_file = self.compiler.compile(str(gle_file), output_format="pdf")

        # Validate using analyzer
        analyzer = PDFAnalyzer(pdf_file)
        assert analyzer.is_valid_pdf()
        assert analyzer.has_valid_structure()

    def test_validate_eps_structure(self):
        """Test EPS structure validation."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        eps_file = self.compiler.compile(str(gle_file), output_format="eps")

        # Validate using analyzer
        analyzer = EPSAnalyzer(eps_file)
        assert analyzer.is_valid_eps()
        assert analyzer.has_valid_structure()

    def test_validate_png_structure(self):
        """Test PNG structure validation."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        png_file = self.compiler.compile(str(gle_file), output_format="png", dpi=150)

        # Validate using analyzer
        analyzer = PNGAnalyzer(png_file)
        assert analyzer.is_valid_png()

    def test_pdf_has_page_info(self):
        """Test that PDF has page count information."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        pdf_file = self.compiler.compile(str(gle_file), output_format="pdf")

        analyzer = PDFAnalyzer(pdf_file)
        page_count = analyzer.get_page_count()

        # Should have at least 1 page
        if page_count is not None:
            assert page_count >= 1

    def test_eps_has_bounding_box(self):
        """Test that EPS has bounding box information."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        eps_file = self.compiler.compile(str(gle_file), output_format="eps")

        analyzer = EPSAnalyzer(eps_file)
        bbox = analyzer.get_bounding_box()

        # Should have valid bounding box (x1, y1, x2, y2)
        if bbox is not None:
            assert len(bbox) == 4
            assert bbox[0] < bbox[2]  # x1 < x2
            assert bbox[1] < bbox[3]  # y1 < y2

    def test_png_has_dimensions(self):
        """Test that PNG has valid image dimensions."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        png_file = self.compiler.compile(str(gle_file), output_format="png", dpi=150)

        analyzer = PNGAnalyzer(png_file)
        dimensions = analyzer.get_image_dimensions()

        # Should have valid dimensions
        if dimensions is not None:
            assert len(dimensions) == 2
            width, height = dimensions
            assert width > 0
            assert height > 0

    def test_png_color_depth(self):
        """Test that PNG has valid color depth."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        png_file = self.compiler.compile(str(gle_file), output_format="png", dpi=150)

        analyzer = PNGAnalyzer(png_file)
        bit_depth = analyzer.get_color_depth()

        # Valid bit depths are 1, 2, 4, 8, 16
        if bit_depth is not None:
            assert bit_depth in [1, 2, 4, 8, 16]

    def test_validate_graphics_file_helper(self):
        """Test the generic graphics file validation helper."""
        gle_file = self.tempdir / "test.gle"
        self.fig.savefig(str(gle_file))

        # Test PDF
        pdf_file = self.compiler.compile(str(gle_file), output_format="pdf")
        result = validate_graphics_file(pdf_file)
        assert result["exists"]
        assert result["format"] == "pdf"
        assert result["valid"]

        # Test EPS
        eps_file = self.compiler.compile(str(gle_file), output_format="eps")
        result = validate_graphics_file(eps_file)
        assert result["exists"]
        assert result["format"] == "eps"
        assert result["valid"]

        # Test PNG
        png_file = self.compiler.compile(str(gle_file), output_format="png", dpi=150)
        result = validate_graphics_file(png_file)
        assert result["exists"]
        assert result["format"] == "png"
        assert result["valid"]


class TestGraphicsFormattingConsistency:
    """Test formatting consistency across different graphics formats."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path):
        """Set up test fixtures."""
        glp.close()
        self.tempdir = tmp_path
        self.compiler = GLECompiler()
        yield
        glp.close()

    def test_same_figure_multiple_formats(self):
        """Test that same figure can be compiled to multiple formats."""
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3, 4, 5], [1, 4, 2, 5, 3], color="blue", label="Series")
        ax.scatter([2, 4], [4, 5], color="red", label="Points")
        ax.set_title("Multi-Format Test")
        ax.set_xlabel("X Axis")
        ax.set_ylabel("Y Axis")
        ax.legend()

        gle_file = self.tempdir / "test.gle"
        fig.savefig(str(gle_file))

        # Compile to all formats
        pdf_file = self.compiler.compile(str(gle_file), output_format="pdf")
        eps_file = self.compiler.compile(str(gle_file), output_format="eps")
        png_file = self.compiler.compile(str(gle_file), output_format="png", dpi=150)

        # All should exist and have reasonable sizes
        for f in [pdf_file, eps_file, png_file]:
            assert f.exists()
            assert f.stat().st_size > 1024

        # Validate each format
        pdf_result = validate_graphics_file(pdf_file)
        eps_result = validate_graphics_file(eps_file)
        png_result = validate_graphics_file(png_file)

        assert pdf_result["valid"]
        assert eps_result["valid"]
        assert png_result["valid"]

    def test_complex_plot_all_formats(self):
        """Test complex plot formatting across all formats."""
        fig = glp.figure(figsize=(10, 8))
        ax = fig.add_subplot(111)

        # Create complex plot
        import numpy as np

        x = np.linspace(0, 10, 50)
        y1 = np.sin(x)
        y2 = np.cos(x)

        ax.fill_between(x, y1 - 0.1, y1 + 0.1, color="lightblue", alpha=0.5)
        ax.plot(x, y1, color="blue", label="sin(x)", linestyle="-")
        ax.plot(x, y2, color="red", label="cos(x)", linestyle="--")
        ax.scatter(x[::5], y1[::5], color="blue", marker="o", s=30)
        ax.scatter(x[::5], y2[::5], color="red", marker="s", s=30)

        ax.set_xscale("linear")
        ax.set_yscale("linear")
        ax.set_xlabel("X (different colors)")
        ax.set_ylabel("Y (with fill)")
        ax.set_title("Complex Plot: Lines, Fill, Scatter")
        ax.legend()

        gle_file = self.tempdir / "complex.gle"
        fig.savefig(str(gle_file))

        # alpha=0.5 is real (Track G6): the fill's colour is now written as
        # rgba255(...), which GLE only accepts under -cairo. This calls
        # GLECompiler.compile() directly (bypassing Figure.savefig()'s
        # auto-detection via requires_cairo()), so the flag must be explicit.
        # Compile to all formats
        pdf_file = self.compiler.compile(str(gle_file), output_format="pdf", cairo=True)
        eps_file = self.compiler.compile(str(gle_file), output_format="eps", cairo=True)
        png_file = self.compiler.compile(
            str(gle_file), output_format="png", dpi=200, cairo=True
        )

        # All should be valid
        for f in [pdf_file, eps_file, png_file]:
            result = validate_graphics_file(f)
            assert result["valid"], f"Invalid {result['format']} file"

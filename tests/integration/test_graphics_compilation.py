"""Integration tests for graphics file generation and validation."""

import shutil
import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp
from gleplot.compiler import GLECompiler
from tests._tempdir import make_tempdir


class TestGraphicsCompilation(unittest.TestCase):
    """Test compilation of GLE files to graphics formats."""
    
    def setUp(self):
        """Create test figure and temporary directory."""
        glp.close()
        self.fig = glp.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        
        # Create sample plot
        self.ax.plot([1, 2, 3, 4, 5], [1, 4, 2, 5, 3], label='Test line', color='blue')
        self.ax.scatter([2, 4], [4, 5], label='Test points', color='red')
        self.ax.set_xlabel('X Axis')
        self.ax.set_ylabel('Y Axis')
        self.ax.set_title('Test Plot for Graphics Compilation')
        self.ax.legend()
        
        self.tempdir = make_tempdir()
        
        # Initialize compiler
        try:
            self.compiler = GLECompiler()
            self.gle_available = True
        except RuntimeError:
            self.gle_available = False
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        # Clean up temp files (skip if KEEP_TEST_FILES is set)
        import os
        if not os.environ.get('KEEP_TEST_FILES'):
            shutil.rmtree(self.tempdir, ignore_errors=True)
        else:
            print(f"\nTest files preserved in: {self.tempdir}")
    
    def test_save_gle_script(self):
        """Test saving GLE script file."""
        gle_file = self.tempdir / 'test.gle'
        result = self.fig.savefig(str(gle_file))
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.gle')
        
        # Verify GLE content
        content = result.read_text()
        self.assertIn('begin graph', content)
        self.assertIn('end graph', content)
        self.assertIn('X Axis', content)
        self.assertIn('Y Axis', content)
        self.assertIn('Test Plot', content)
    
    def test_compile_to_pdf(self):
        """Test compiling GLE to PDF format."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        pdf_file = self.tempdir / 'test.pdf'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to PDF
        result = self.compiler.compile(str(gle_file), output_format='pdf')
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.pdf')
        self.assertTrue(result.stat().st_size > 0)
    
    def test_compile_to_eps(self):
        """Test compiling GLE to EPS format."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        eps_file = self.tempdir / 'test.eps'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to EPS
        result = self.compiler.compile(str(gle_file), output_format='eps')
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.eps')
        self.assertTrue(result.stat().st_size > 0)
    
    def test_compile_to_png(self):
        """Test compiling GLE to PNG format."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        png_file = self.tempdir / 'test.png'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to PNG with specific DPI
        result = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.png')
        self.assertTrue(result.stat().st_size > 0)

    def test_save_pdf_in_folder(self):
        """Test compiled exports keep all generated files in a dedicated folder."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")

        pdf_file = self.tempdir / 'test.pdf'
        result = self.fig.savefig(str(pdf_file), folder=True)

        export_dir = self.tempdir / 'test.gleplot'
        self.assertEqual(result, export_dir / 'test.pdf')
        self.assertTrue(result.exists())
        self.assertTrue((export_dir / 'test.gle').exists())
        self.assertGreaterEqual(len(list(export_dir.glob('*.dat'))), 1)
        self.assertFalse(pdf_file.exists())
    
    def test_pdf_contains_elements(self):
        """Test that PDF contains expected text elements."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to PDF
        pdf_file = self.compiler.compile(str(gle_file), output_format='pdf')
        
        # Read PDF content (basic check)
        content = pdf_file.read_bytes()
        
        # PDF should contain the expected structure
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertIn(b'stream', content)
        self.assertIn(b'endstream', content)
    
    def test_eps_contains_elements(self):
        """Test that EPS contains expected PostScript elements."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to EPS
        eps_file = self.compiler.compile(str(gle_file), output_format='eps')
        
        # Read EPS content
        content = eps_file.read_text(errors='ignore')
        
        # EPS should be valid PostScript
        self.assertIn('%!PS-Adobe', content)
        self.assertIn('showpage', content)
    
    def test_png_valid_header(self):
        """Test that PNG has valid image header."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        gle_file = self.tempdir / 'test.gle'
        
        # Create GLE file
        self.fig.savefig(str(gle_file))
        
        # Compile to PNG
        png_file = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        
        # Read PNG header
        content = png_file.read_bytes()
        
        # PNG signature
        png_signature = b'\x89PNG\r\n\x1a\n'
        self.assertTrue(content.startswith(png_signature))


class TestImageProperties(unittest.TestCase):
    """Test properties of generated graphics files."""
    
    def setUp(self):
        """Set up test fixtures."""
        glp.close()
        self.tempdir = make_tempdir()
        
        # Initialize compiler
        try:
            self.compiler = GLECompiler()
            self.gle_available = True
        except RuntimeError:
            self.gle_available = False
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        import os
        if not os.environ.get('KEEP_TEST_FILES'):
            shutil.rmtree(self.tempdir, ignore_errors=True)
        else:
            print(f"\nTest files preserved in: {self.tempdir}")
    
    def test_pdf_file_size_reasonable(self):
        """Test that PDF file size is reasonable."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        
        gle_file = self.tempdir / 'test.gle'
        fig.savefig(str(gle_file))
        
        pdf_file = self.compiler.compile(str(gle_file), output_format='pdf')
        
        # PDF should be at least a few KB
        file_size = pdf_file.stat().st_size
        self.assertGreater(file_size, 1024)  # At least 1KB
        self.assertLess(file_size, 10 * 1024 * 1024)  # Less than 10MB
    
    def test_eps_file_size_reasonable(self):
        """Test that EPS file size is reasonable."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        
        gle_file = self.tempdir / 'test.gle'
        fig.savefig(str(gle_file))
        
        eps_file = self.compiler.compile(str(gle_file), output_format='eps')
        
        # EPS should be at least a few KB
        file_size = eps_file.stat().st_size
        self.assertGreater(file_size, 1024)  # At least 1KB
        self.assertLess(file_size, 10 * 1024 * 1024)  # Less than 10MB
    
    def test_png_file_size_reasonable(self):
        """Test that PNG file size is reasonable."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        
        gle_file = self.tempdir / 'test.gle'
        fig.savefig(str(gle_file))
        
        png_file = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        
        # PNG should be at least a few KB
        file_size = png_file.stat().st_size
        self.assertGreater(file_size, 1024)  # At least 1KB
        self.assertLess(file_size, 10 * 1024 * 1024)  # Less than 10MB


class TestGraphicsWithAdvancedFeatures(unittest.TestCase):
    """Test graphics generation with advanced gleplot features."""
    
    def setUp(self):
        """Set up test fixtures."""
        glp.close()
        self.tempdir = make_tempdir()
        
        try:
            self.compiler = GLECompiler()
            self.gle_available = True
        except RuntimeError:
            self.gle_available = False
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        import os
        if not os.environ.get('KEEP_TEST_FILES'):
            shutil.rmtree(self.tempdir, ignore_errors=True)
        else:
            print(f"\nTest files preserved in: {self.tempdir}")
    
    def test_compile_with_fill_between(self):
        """Test compiling plot with fill_between to PDF."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        
        x = [1, 2, 3, 4, 5]
        y1 = [1, 2, 1.5, 3, 2.5]
        y2 = [2, 3, 2.5, 4, 3.5]
        
        ax.fill_between(x, y1, y2, color='lightblue', alpha=0.5)
        ax.plot(x, [(a + b) / 2 for a, b in zip(y1, y2)], color='blue')
        ax.set_title('Fill Between Plot')
        
        gle_file = self.tempdir / 'fill_between.gle'
        fig.savefig(str(gle_file))
        
        pdf_file = self.compiler.compile(str(gle_file), output_format='pdf')
        
        self.assertTrue(pdf_file.exists())
        self.assertGreater(pdf_file.stat().st_size, 1024)
    
    def test_compile_with_log_scale(self):
        """Test compiling plot with log scale to PDF."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        
        x = [1, 10, 100, 1000]
        y = [1, 100, 10000, 1000000]
        
        ax.plot(x, y, marker='o', linestyle='-', color='blue')
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_title('Log-Log Plot')
        
        gle_file = self.tempdir / 'log_scale.gle'
        fig.savefig(str(gle_file))
        
        pdf_file = self.compiler.compile(str(gle_file), output_format='pdf')
        
        self.assertTrue(pdf_file.exists())
        self.assertGreater(pdf_file.stat().st_size, 1024)
    
    def test_compile_with_multiple_colors(self):
        """Test compiling plot with multiple colors to PNG."""
        if not self.gle_available:
            self.skipTest("GLE compiler not available")
        
        fig = glp.figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        
        colors = ['red', 'blue', 'green', 'orange', 'purple']
        for i, color in enumerate(colors):
            ax.plot([1, 2, 3], [i*1 + 1, i*1 + 2, i*1 + 3], 
                   color=color, label=f'Series {i+1}')
        
        ax.legend()
        ax.set_title('Multi-Color Plot')
        
        gle_file = self.tempdir / 'multi_color.gle'
        fig.savefig(str(gle_file))
        
        png_file = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        
        self.assertTrue(png_file.exists())
        self.assertGreater(png_file.stat().st_size, 1024)


class TestHeaderRowRenderingUnchanged(unittest.TestCase):
    """Track E3: named sidecar column headers must not change GLE rendering.

    GLE auto-detects a non-numeric first row of a data file as a column
    header (``auto_has_header`` in the GLE source) and, when unset, copies
    the header's own-column text into that dataset's ``key_name`` -- i.e. a
    header row can silently invent a legend entry for a series that never
    asked for one. gleplot's writer neutralizes this by always emitting an
    explicit ``key`` clause (the real label, or ``key ""``) whenever a
    header row is present -- see ``writer.GLEWriter._key_clause`` /
    ``add_bar_chart`` / ``add_fill_between``.

    This test proves the fix holds for a REAL GLE compile: a battery figure
    covering every generated-sidecar series type (line labeled + unlabeled,
    bar unlabeled, errorbar labeled + unlabeled, fill unlabeled) renders to
    byte-identical PNG bytes whether or not the sidecars carry a header row
    and the corresponding key-suppression tokens -- i.e. identical to the
    pre-Track-E3 (headerless, no explicit key for unlabeled series) output.
    """

    def setUp(self):
        glp.close()
        self.tempdir = make_tempdir()
        try:
            self.compiler = GLECompiler()
            self.gle_available = True
        except RuntimeError:
            self.gle_available = False

    def tearDown(self):
        glp.close()
        import os
        if not os.environ.get('KEEP_TEST_FILES'):
            shutil.rmtree(self.tempdir, ignore_errors=True)

    def _build_battery_figure(self):
        import numpy as np
        fig = glp.figure(figsize=(8, 6), data_prefix='battery')
        ax = fig.add_subplot(111)
        x = np.linspace(0, 10, 20)
        ax.plot(x, np.sin(x), color='red', label='sin wave')
        ax.plot(x, np.cos(x), color='blue')  # unlabeled line
        ax.bar([1, 2, 3], [4, 5, 6], color='orange')  # unlabeled bar
        ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.3, color='green',
                    marker='o', label='measurements')
        ax.errorbar([1, 2, 3], [5, 3, 1], yerr=0.2, color='purple',
                    marker='s')  # unlabeled errorbar
        ax.fill_between(x, np.zeros_like(x), np.abs(np.sin(x)) * 0.3,
                         color='lightblue')  # unlabeled fill
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title('battery')
        ax.legend()
        return fig

    @staticmethod
    def _strip_header_feature(gle_text: str, data_files: dict) -> tuple:
        """Reconstruct the pre-Track-E3 equivalent: headerless sidecars and
        no explicit ``key`` clause for unlabeled series (bare omission).
        """
        stripped_text_lines = []
        for line in gle_text.splitlines():
            stripped = line.rstrip()
            if stripped.strip().startswith('d') and stripped.strip().endswith('key ""'):
                # Standalone 'dN key ""' suppression line (bar/fill) -> drop
                # entirely, matching the pre-feature output which never had it.
                if stripped.strip().split() == [stripped.strip().split()[0], 'key', '""']:
                    continue
            # Inline ' key ""' suffix on a dataset display line -> remove.
            stripped = stripped.replace(' key ""', '')
            stripped_text_lines.append(stripped)
        stripped_text = '\n'.join(stripped_text_lines)

        stripped_data = {}
        for name, content in data_files.items():
            lines = content.splitlines()
            # First line is a header iff it's non-numeric (mirrors GLE's own
            # auto_has_header check well enough for this synthetic battery,
            # whose data rows are always purely numeric).
            if lines and not _looks_like_data_row(lines[0]):
                lines = lines[1:]
            stripped_data[name] = '\n'.join(lines) + '\n'
        return stripped_text, stripped_data

    def test_battery_figure_renders_identically_with_and_without_headers(self):
        if not self.gle_available:
            self.skipTest("GLE compiler not available")

        fig = self._build_battery_figure()
        with_headers_dir = self.tempdir / 'with_headers'
        with_headers_dir.mkdir()
        gle_path = with_headers_dir / 'battery.gle'
        fig.savefig_gle(str(gle_path))

        gle_text = gle_path.read_text(encoding='utf-8')
        data_files = {
            p.name: p.read_text(encoding='utf-8')
            for p in with_headers_dir.glob('*.dat')
        }
        # Sanity: headers are actually present (the feature is active).
        self.assertTrue(any(
            not _looks_like_data_row(content.splitlines()[0])
            for content in data_files.values()
        ), "expected at least one sidecar with a header row")
        self.assertIn('key ""', gle_text)

        pre_change_dir = self.tempdir / 'pre_change'
        pre_change_dir.mkdir()
        stripped_text, stripped_data = self._strip_header_feature(gle_text, data_files)
        (pre_change_dir / 'battery.gle').write_text(stripped_text, encoding='utf-8')
        for name, content in stripped_data.items():
            (pre_change_dir / name).write_text(content, encoding='utf-8')

        with_headers_png = self.compiler.compile(
            str(gle_path), output_format='png', dpi=100
        )
        pre_change_png = self.compiler.compile(
            str(pre_change_dir / 'battery.gle'), output_format='png', dpi=100
        )

        self.assertEqual(
            with_headers_png.read_bytes(), pre_change_png.read_bytes(),
            "sidecar header rows changed the compiled PNG output"
        )


def _looks_like_data_row(line: str) -> bool:
    """True if every whitespace-separated token on ``line`` parses as a
    float -- i.e. it's a DATA row, not a header row (mirrors GLE's own
    ``auto_has_header`` / ``isFloatMiss`` check: a header row has at least
    one non-numeric cell)."""
    tokens = line.split()
    if not tokens:
        return True
    for tok in tokens:
        try:
            float(tok)
        except ValueError:
            return False
    return True


if __name__ == '__main__':
    unittest.main()

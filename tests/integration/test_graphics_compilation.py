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


if __name__ == '__main__':
    unittest.main()

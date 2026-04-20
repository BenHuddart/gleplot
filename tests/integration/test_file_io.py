"""Integration tests for file I/O operations."""

import shutil
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp
from tests._tempdir import make_tempdir


class TestFileIO(unittest.TestCase):
    """Test file I/O operations."""
    
    def setUp(self):
        """Create fresh figure and temp directory for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([1, 2, 3], [1, 4, 9], label='test')
        
        self.tempdir = make_tempdir()
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        shutil.rmtree(self.tempdir, ignore_errors=True)
    
    def test_save_gle_script(self):
        """Test saving as GLE script."""
        output_file = self.tempdir / 'test.gle'
        result = self.fig.savefig_gle(str(output_file))
        
        self.assertTrue(result.exists())
        content = result.read_text()
        self.assertIn('begin graph', content)
        self.assertIn('end graph', content)
    
    def test_save_with_gle_extension(self):
        """Test saving with .gle extension."""
        output_file = self.tempdir / 'test.gle'
        result = self.fig.savefig(str(output_file))
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.gle')
    
    def test_gle_content_has_data(self):
        """Test GLE content includes data files."""
        output_file = self.tempdir / 'test.gle'
        result = self.fig.savefig(str(output_file))
        
        content = result.read_text()
        self.assertIn('data_', content)

    def test_save_gle_script_in_folder(self):
        """Test saving a GLE export into a dedicated folder."""
        output_file = self.tempdir / 'test.gle'
        result = self.fig.savefig_gle(str(output_file), folder=True)

        export_dir = self.tempdir / 'test.gleplot'
        self.assertEqual(result, export_dir / 'test.gle')
        self.assertTrue(result.exists())
        self.assertTrue(export_dir.is_dir())
        self.assertGreaterEqual(len(list(export_dir.glob('*.dat'))), 1)
        self.assertFalse(output_file.exists())

    def test_save_without_extension_in_folder_defaults_to_gle(self):
        """Test folder exports also work when savefig infers the .gle suffix."""
        output_file = self.tempdir / 'batch_run'
        result = self.fig.savefig(str(output_file), folder=True)

        export_dir = self.tempdir / 'batch_run.gleplot'
        self.assertEqual(result, export_dir / 'batch_run.gle')
        self.assertTrue(result.exists())
        self.assertGreaterEqual(len(list(export_dir.glob('*.dat'))), 1)
        self.assertFalse((self.tempdir / 'batch_run.gle').exists())

    def test_save_compiled_output_in_folder_uses_foldered_gle_path(self):
        """Test compiled exports route the intermediate GLE file into the folder."""
        compiler = Mock()
        self.fig.compiler = compiler

        output_file = self.tempdir / 'report.pdf'
        result = self.fig.savefig(str(output_file), folder=True)

        export_dir = self.tempdir / 'report.gleplot'
        self.assertEqual(result, export_dir / 'report.pdf')
        self.assertTrue((export_dir / 'report.gle').exists())
        self.assertGreaterEqual(len(list(export_dir.glob('*.dat'))), 1)
        compiler.compile.assert_called_once_with(str(export_dir / 'report.gle'), 'pdf', dpi=self.fig.dpi)
        self.assertFalse(output_file.exists())

    def test_save_gle_script_uses_utf8_for_unicode_labels(self):
        """GLE scripts should preserve Unicode labels across platforms."""
        label = 'Time (\u03bcs)'
        self.ax.set_xlabel(label)
        output_file = self.tempdir / 'unicode.gle'

        result = self.fig.savefig_gle(str(output_file))

        raw = result.read_bytes()
        self.assertIn(label.encode('utf-8'), raw)
        self.assertEqual(
            raw.decode('utf-8').splitlines(),
            result.read_text(encoding='utf-8').splitlines(),
        )


if __name__ == '__main__':
    unittest.main()

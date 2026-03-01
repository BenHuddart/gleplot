"""Integration tests for file I/O operations."""

import sys
from pathlib import Path
import tempfile
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


class TestFileIO(unittest.TestCase):
    """Test file I/O operations."""
    
    def setUp(self):
        """Create fresh figure and temp directory for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([1, 2, 3], [1, 4, 9], label='test')
        
        self.tempdir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_save_gle_script(self):
        """Test saving as GLE script."""
        output_file = Path(self.tempdir) / 'test.gle'
        result = self.fig.savefig_gle(str(output_file))
        
        self.assertTrue(result.exists())
        content = result.read_text()
        self.assertIn('begin graph', content)
        self.assertIn('end graph', content)
    
    def test_save_with_gle_extension(self):
        """Test saving with .gle extension."""
        output_file = Path(self.tempdir) / 'test.gle'
        result = self.fig.savefig(str(output_file))
        
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.gle')
    
    def test_gle_content_has_data(self):
        """Test GLE content includes data files."""
        output_file = Path(self.tempdir) / 'test.gle'
        result = self.fig.savefig(str(output_file))
        
        content = result.read_text()
        self.assertIn('data_', content)


if __name__ == '__main__':
    unittest.main()

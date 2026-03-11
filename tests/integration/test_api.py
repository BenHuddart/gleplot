"""Integration tests for Figure API and GLE generation."""

import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


class TestFigureAPI(unittest.TestCase):
    """Test Figure class API."""
    
    def setUp(self):
        """Create test figure."""
        glp.close()
    
    def tearDown(self):
        """Clean up."""
        glp.close()
    
    def test_figure_creation(self):
        """Test creating a figure."""
        fig = glp.figure()
        self.assertIsNotNone(fig)
        self.assertEqual(fig.figsize, (8, 6))
    
    def test_figure_custom_size(self):
        """Test figure with custom size."""
        fig = glp.figure(figsize=(10, 8))
        self.assertEqual(fig.figsize, (10, 8))
    
    def test_add_subplot(self):
        """Test adding subplot."""
        fig = glp.figure()
        ax = fig.add_subplot(111)
        
        self.assertIsNotNone(ax)
        self.assertEqual(len(fig.axes_list), 1)
    
    def test_gca_creates_axes(self):
        """Test gca() creates axes if needed."""
        fig = glp.figure()
        ax = fig.gca()
        
        self.assertIsNotNone(ax)
        self.assertEqual(len(fig.axes_list), 1)
    
    def test_convenience_functions(self):
        """Test module-level convenience functions."""
        glp.plot([1, 2, 3], [1, 2, 3])
        glp.scatter([1, 2, 3], [1, 2, 3])
        glp.bar([1, 2, 3], [10, 20, 30])
        glp.text(2, 2, 'A')
        
        fig = glp.gcf()
        ax = fig.gca()
        
        self.assertEqual(len(ax.lines), 1)
        self.assertEqual(len(ax.scatters), 1)
        self.assertEqual(len(ax.bars), 1)
        self.assertEqual(len(ax.texts), 1)


class TestGLEGeneration(unittest.TestCase):
    """Test GLE script generation."""
    
    def setUp(self):
        """Create test figure with plot."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up."""
        glp.close()
    
    def test_gle_preamble(self):
        """Test GLE includes required preamble."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        
        gle = self.fig._generate_gle()
        
        self.assertIn('begin graph', gle)
        self.assertIn('end graph', gle)
        self.assertIn('size', gle)
    
    def test_gle_with_labels(self):
        """Test GLE includes axis labels."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        self.ax.set_xlabel('X Label')
        self.ax.set_ylabel('Y Label')
        self.ax.set_title('Title')
        
        gle = self.fig._generate_gle()
        
        self.assertIn('xtitle', gle)
        self.assertIn('ytitle', gle)
        self.assertIn('title', gle)
    
    def test_gle_with_log_scale(self):
        """Test GLE includes log scale."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        self.ax.set_xscale('log')
        
        gle = self.fig._generate_gle()
        
        # Check that xaxis has log keyword (format: "xaxis min X max Y log")
        self.assertIn('xaxis', gle)
        self.assertIn('log', gle)
        # Verify log appears on an xaxis line
        for line in gle.split('\n'):
            if 'xaxis' in line and 'log' in line:
                break
        else:
            self.fail('xaxis with log scale not found in GLE output')


if __name__ == '__main__':
    unittest.main()

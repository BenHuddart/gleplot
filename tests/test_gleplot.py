"""
Test suite for gleplot library.

Tests cover:
- Basic line plotting
- Scatter plots
- Bar charts
- Fill between
- Multiple axes
- Axis properties
- Color and marker mapping
- File I/O
"""

import sys
import numpy as np
from pathlib import Path
import tempfile
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp
from gleplot.colors import rgb_to_gle
from gleplot.markers import get_gle_marker


class TestBasicPlotting(unittest.TestCase):
    """Test basic line plotting functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_simple_line_plot(self):
        """Test basic line plotting."""
        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]
        
        self.ax.plot(x, y)
        
        self.assertEqual(len(self.ax.lines), 1)
        self.assertTrue(self.ax.has_plots())
    
    def test_line_with_color(self):
        """Test line with color specification."""
        self.ax.plot([1, 2, 3], [1, 2, 3], color='red')
        
        self.assertEqual(len(self.ax.lines), 1)
        self.assertEqual(self.ax.lines[0]['color'], 'RED')
    
    def test_line_with_style(self):
        """Test line with different styles."""
        self.ax.plot([1, 2, 3], [1, 2, 3], linestyle='--')
        
        self.assertEqual(self.ax.lines[0]['linestyle'], '--')
    
    def test_line_with_label(self):
        """Test line with legend label."""
        label = 'test line'
        self.ax.plot([1, 2, 3], [1, 2, 3], label=label)
        
        self.assertEqual(self.ax.lines[0]['label'], label)
    
    def test_multiple_lines(self):
        """Test multiple line plots on same axes."""
        self.ax.plot([1, 2, 3], [1, 2, 3], label='line 1')
        self.ax.plot([1, 2, 3], [3, 2, 1], label='line 2')
        
        self.assertEqual(len(self.ax.lines), 2)


class TestScatterPlots(unittest.TestCase):
    """Test scatter plot functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_simple_scatter(self):
        """Test basic scatter plot."""
        self.ax.scatter([1, 2, 3], [1, 2, 3])
        
        self.assertEqual(len(self.ax.scatters), 1)
    
    def test_scatter_with_color(self):
        """Test scatter with color."""
        self.ax.scatter([1, 2, 3], [1, 2, 3], color='blue')
        
        self.assertEqual(self.ax.scatters[0]['color'], 'BLUE')
    
    def test_scatter_with_marker(self):
        """Test scatter with different marker."""
        self.ax.scatter([1, 2, 3], [1, 2, 3], marker='s')
        
        # scatter() should use marker 's' (square)
        self.assertEqual(self.ax.scatters[0]['marker'], 'FSQUARE')
    
    def test_plot_as_scatter(self):
        """Test plot() with marker creates scatter."""
        self.ax.plot([1, 2, 3], [1, 2, 3], marker='o', linestyle='none')
        
        # Should be in scatters list, not lines
        self.assertEqual(len(self.ax.scatters), 1)
        self.assertEqual(len(self.ax.lines), 0)


class TestBarCharts(unittest.TestCase):
    """Test bar chart functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_simple_bar(self):
        """Test basic bar chart."""
        self.ax.bar([1, 2, 3], [10, 20, 30])
        
        self.assertEqual(len(self.ax.bars), 1)
    
    def test_bar_with_color(self):
        """Test bar with single color."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color='red')
        
        self.assertEqual(len(self.ax.bars[0]['colors']), 3)
        self.assertEqual(self.ax.bars[0]['colors'][0], 'RED')
    
    def test_bar_with_multiple_colors(self):
        """Test bar with per-bar colors."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color=['red', 'green', 'blue'])
        
        colors = self.ax.bars[0]['colors']
        self.assertEqual(colors[0], 'RED')
        self.assertEqual(colors[1], 'GREEN')
        self.assertEqual(colors[2], 'BLUE')


class TestFillBetween(unittest.TestCase):
    """Test fill_between functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_simple_fill(self):
        """Test basic fill_between."""
        x = [1, 2, 3]
        y1 = [1, 2, 3]
        y2 = [2, 4, 6]
        
        self.ax.fill_between(x, y1, y2)
        
        self.assertEqual(len(self.ax.fills), 1)
    
    def test_fill_with_color(self):
        """Test fill_between with color."""
        self.ax.fill_between([1, 2, 3], [1, 2, 3], [2, 4, 6], color='lightblue')
        
        self.assertEqual(self.ax.fills[0]['color'], 'LIGHTBLUE')


class TestAxisProperties(unittest.TestCase):
    """Test axis property setting."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_axis_labels(self):
        """Test setting axis labels."""
        self.ax.set_xlabel('X axis')
        self.ax.set_ylabel('Y axis')
        self.ax.set_title('Test Plot')
        
        self.assertEqual(self.ax.xlabel_text, 'X axis')
        self.assertEqual(self.ax.ylabel_text, 'Y axis')
        self.assertEqual(self.ax.title_text, 'Test Plot')
    
    def test_axis_limits(self):
        """Test setting axis limits."""
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 100)
        
        self.assertEqual(self.ax.xmin, 0)
        self.assertEqual(self.ax.xmax, 10)
        self.assertEqual(self.ax.ymin, 0)
        self.assertEqual(self.ax.ymax, 100)
    
    def test_axis_scales(self):
        """Test setting axis scales."""
        self.ax.set_xscale('log')
        self.ax.set_yscale('log')
        
        self.assertEqual(self.ax.xscale, 'log')
        self.assertEqual(self.ax.yscale, 'log')
    
    def test_legend(self):
        """Test adding legend."""
        self.ax.legend(loc='upper left')
        
        self.assertTrue(self.ax.legend_on)
        self.assertEqual(self.ax.legend_pos, 'top left')


class TestColorMapping(unittest.TestCase):
    """Test color conversion utilities."""
    
    def test_single_letter_colors(self):
        """Test single-letter color codes."""
        self.assertEqual(rgb_to_gle('b'), 'BLUE')
        self.assertEqual(rgb_to_gle('r'), 'RED')
        self.assertEqual(rgb_to_gle('g'), 'GREEN')
        self.assertEqual(rgb_to_gle('k'), 'BLACK')
    
    def test_named_colors(self):
        """Test named colors."""
        self.assertEqual(rgb_to_gle('red'), 'RED')
        self.assertEqual(rgb_to_gle('blue'), 'BLUE')
        self.assertEqual(rgb_to_gle('green'), 'GREEN')
    
    def test_rgb_tuple(self):
        """Test RGB tuple conversion."""
        # Pure blue
        color = rgb_to_gle((0.0, 0.0, 1.0))
        self.assertEqual(color, 'BLUE')
        
        # Pure red
        color = rgb_to_gle((1.0, 0.0, 0.0))
        self.assertEqual(color, 'RED')


class TestMarkerMapping(unittest.TestCase):
    """Test marker conversion utilities."""
    
    def test_basic_markers(self):
        """Test basic matplotlib markers."""
        self.assertEqual(get_gle_marker('o'), 'FCIRCLE')
        self.assertEqual(get_gle_marker('s'), 'FSQUARE')
        self.assertEqual(get_gle_marker('^'), 'FTRIANGLE')
        self.assertEqual(get_gle_marker('+'), 'PLUS')
    
    def test_invalid_marker(self):
        """Test invalid marker returns default."""
        result = get_gle_marker('INVALID')
        self.assertEqual(result, 'FCIRCLE')  # Default


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
        
        fig = glp.gcf()
        ax = fig.gca()
        
        self.assertEqual(len(ax.lines), 1)
        self.assertEqual(len(ax.scatters), 1)
        self.assertEqual(len(ax.bars), 1)


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
        
        self.assertIn('log on', gle)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()

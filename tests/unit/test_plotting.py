"""Unit tests for plotting functionality."""

import sys
import numpy as np
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


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


if __name__ == '__main__':
    unittest.main()

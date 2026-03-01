"""Unit tests for axis properties."""

import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


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


class TestSubplots(unittest.TestCase):
    """Test subplot (multi-graph) functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_add_subplot_three_args(self):
        """Test add_subplot with three separate arguments."""
        fig = glp.figure()
        ax = fig.add_subplot(2, 3, 4)
        
        self.assertEqual(ax.position, (2, 3, 4))
        self.assertEqual(len(fig.axes_list), 1)
    
    def test_add_subplot_shorthand(self):
        """Test add_subplot with single int shorthand (e.g., 221)."""
        fig = glp.figure()
        ax = fig.add_subplot(221)
        
        self.assertEqual(ax.position, (2, 2, 1))
    
    def test_multiple_subplots(self):
        """Test creating multiple subplots."""
        fig = glp.figure()
        ax1 = fig.add_subplot(2, 2, 1)
        ax2 = fig.add_subplot(2, 2, 2)
        ax3 = fig.add_subplot(2, 2, 3)
        ax4 = fig.add_subplot(2, 2, 4)
        
        self.assertEqual(len(fig.axes_list), 4)
        # Current axes should be the last one added
        self.assertIs(fig._current_axes, ax4)
    
    def test_subplots_function_single(self):
        """Test subplots() convenience function for single plot."""
        fig, ax = glp.subplots()
        
        self.assertIsInstance(fig, glp.Figure)
        self.assertIsInstance(ax, glp.Axes)
        self.assertEqual(len(fig.axes_list), 1)
    
    def test_subplots_function_grid(self):
        """Test subplots() convenience function for grid."""
        fig, axes = glp.subplots(2, 3)
        
        self.assertIsInstance(axes, list)
        self.assertEqual(len(axes), 6)
        self.assertEqual(fig.figsize, (18, 8))  # 6*3, 4*2
    
    def test_subplots_function_custom_figsize(self):
        """Test subplots() with custom figsize."""
        fig, axes = glp.subplots(2, 2, figsize=(10, 8))
        
        self.assertEqual(fig.figsize, (10, 8))
        self.assertEqual(len(axes), 4)
    
    def test_subplot_independent_axes(self):
        """Test that subplots have independent axis properties."""
        fig, axes = glp.subplots(1, 2)
        axes[0].set_title('Left')
        axes[0].set_xlabel('x1')
        axes[1].set_title('Right')
        axes[1].set_xlabel('x2')
        
        self.assertEqual(axes[0].title_text, 'Left')
        self.assertEqual(axes[1].title_text, 'Right')
        self.assertEqual(axes[0].xlabel_text, 'x1')
        self.assertEqual(axes[1].xlabel_text, 'x2')
    
    def test_subplot_independent_data(self):
        """Test that subplots hold independent data."""
        fig, axes = glp.subplots(1, 2)
        axes[0].plot([1, 2, 3], [1, 4, 9])
        axes[1].scatter([1, 2, 3], [3, 2, 1])
        
        self.assertEqual(len(axes[0].lines), 1)
        self.assertEqual(len(axes[0].scatters), 0)
        self.assertEqual(len(axes[1].lines), 0)
        self.assertEqual(len(axes[1].scatters), 1)
    
    def test_single_subplot_gle_no_amove(self):
        """Test that single subplot generates simple GLE without amove."""
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9])
        
        gle = fig._generate_gle()
        self.assertNotIn('amove', gle)
        # Should have exactly one begin/end graph
        self.assertEqual(gle.count('begin graph'), 1)
        self.assertEqual(gle.count('end graph'), 1)
    
    def test_multi_subplot_gle_has_amove(self):
        """Test that multi-subplot generates amove positioning."""
        fig = glp.figure()
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.plot([1, 2, 3], [1, 4, 9])
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.scatter([1, 2, 3], [3, 2, 1])
        
        gle = fig._generate_gle()
        self.assertIn('amove', gle)
        self.assertEqual(gle.count('begin graph'), 2)
        self.assertEqual(gle.count('end graph'), 2)
    
    def test_2x2_subplot_gle_structure(self):
        """Test GLE structure of a 2x2 subplot grid."""
        fig = glp.figure(figsize=(12, 10))
        for i in range(1, 5):
            ax = fig.add_subplot(2, 2, i)
            ax.plot([1, 2, 3], [i, i*2, i*3])
            ax.set_title(f'Plot {i}')
        
        gle = fig._generate_gle()
        # Should have 4 graph blocks
        self.assertEqual(gle.count('begin graph'), 4)
        self.assertEqual(gle.count('end graph'), 4)
        # Each should have a title
        for i in range(1, 5):
            self.assertIn(f'title "Plot {i}"', gle)
        # Should have explicit size for each subplot
        self.assertIn('size', gle)
    
    def test_subplot_mixed_types(self):
        """Test subplots with different plot types."""
        import numpy as np
        fig, axes = glp.subplots(2, 2, figsize=(12, 10))
        
        axes[0].plot([1, 2, 3], [1, 4, 9], color='blue')
        axes[1].scatter([1, 2, 3], [3, 6, 2], color='red')
        axes[2].bar([1, 2, 3], [10, 20, 30], color='green')
        axes[3].errorbar([1, 2, 3], [5, 10, 15], yerr=1, marker='o')
        
        gle = fig._generate_gle()
        # Should contain all plot types
        self.assertIn('line', gle)
        self.assertIn('marker', gle)
        self.assertIn('bar', gle)
        self.assertIn('err', gle)
    
    def test_subplot_savefig(self):
        """Test saving multi-subplot figure."""
        import tempfile
        import os
        
        fig, axes = glp.subplots(1, 2)
        axes[0].plot([1, 2, 3], [1, 4, 9])
        axes[1].scatter([1, 2, 3], [3, 2, 1])
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'subplots.gle')
            fig.savefig(path)
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn('amove', content)
            self.assertEqual(content.count('begin graph'), 2)


if __name__ == '__main__':
    unittest.main()

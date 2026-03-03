"""Unit tests for plotting functionality."""

import sys
import numpy as np
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

# Check if IPython is available for conditional testing
try:
    import IPython
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False

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


class TestErrorBars(unittest.TestCase):
    """Test error bar functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_symmetric_yerr_scalar(self):
        """Test symmetric vertical error bars with scalar value."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, yerr=0.5, marker='o')
        
        self.assertEqual(len(self.ax.errorbars), 1)
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb['yerr_up'], [0.5, 0.5, 0.5])
        np.testing.assert_array_equal(eb['yerr_down'], [0.5, 0.5, 0.5])
    
    def test_symmetric_yerr_array(self):
        """Test symmetric vertical error bars with array."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        yerr = [0.3, 0.5, 0.4]
        self.ax.errorbar(x, y, yerr=yerr, marker='o')
        
        eb = self.ax.errorbars[0]
        np.testing.assert_array_almost_equal(eb['yerr_up'], [0.3, 0.5, 0.4])
        np.testing.assert_array_almost_equal(eb['yerr_down'], [0.3, 0.5, 0.4])
    
    def test_asymmetric_yerr(self):
        """Test asymmetric vertical error bars."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        yerr = ([1, 2, 3], [3, 2, 1])
        self.ax.errorbar(x, y, yerr=yerr, marker='o')
        
        eb = self.ax.errorbars[0]
        np.testing.assert_array_almost_equal(eb['yerr_down'], [1, 2, 3])
        np.testing.assert_array_almost_equal(eb['yerr_up'], [3, 2, 1])
    
    def test_horizontal_error_bars(self):
        """Test horizontal error bars."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, xerr=0.2, marker='o')
        
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb['xerr_left'], [0.2, 0.2, 0.2])
        np.testing.assert_array_equal(eb['xerr_right'], [0.2, 0.2, 0.2])
    
    def test_both_xerr_and_yerr(self):
        """Test vertical and horizontal error bars together."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, yerr=0.5, xerr=0.3, marker='o')
        
        eb = self.ax.errorbars[0]
        self.assertIsNotNone(eb['yerr_up'])
        self.assertIsNotNone(eb['xerr_left'])
    
    def test_errorbar_with_capsize(self):
        """Test error bar cap width."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, capsize=0.2)
        
        eb = self.ax.errorbars[0]
        self.assertEqual(eb['capsize'], 0.2)
    
    def test_errorbar_with_label(self):
        """Test error bar with legend label."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, label='Data')
        
        eb = self.ax.errorbars[0]
        self.assertEqual(eb['label'], 'Data')
    
    def test_errorbar_with_color(self):
        """Test error bar with custom color."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, color='red')
        
        eb = self.ax.errorbars[0]
        self.assertEqual(eb['color'], 'RED')
    
    def test_errorbar_has_plots(self):
        """Test that errorbar counts in has_plots()."""
        self.assertFalse(self.ax.has_plots())
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5)
        self.assertTrue(self.ax.has_plots())
    
    def test_errorbar_gle_generation(self):
        """Test GLE script generation for error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, yerr=0.5, marker='o', color='blue', label='Test')
        
        gle = self.fig._generate_gle()
        self.assertIn('err d2', gle)
        self.assertIn('marker FCIRCLE', gle)
        self.assertIn('key "Test"', gle)
    
    def test_errorbar_asymmetric_gle(self):
        """Test GLE generation for asymmetric error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, yerr=([1, 2, 3], [3, 2, 1]), marker='s',
                        fmt='none', color='red')
        
        gle = self.fig._generate_gle()
        self.assertIn('errup', gle)
        self.assertIn('errdown', gle)
    
    def test_errorbar_horizontal_gle(self):
        """Test GLE generation for horizontal error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, xerr=0.3, marker='o', fmt='none')
        
        gle = self.fig._generate_gle()
        self.assertIn('herr', gle)
    
    def test_figure_errorbar_method(self):
        """Test Figure-level errorbar convenience method."""
        self.fig.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5)
        
        ax = self.fig.gca()
        self.assertEqual(len(ax.errorbars), 1)


@unittest.skipUnless(IPYTHON_AVAILABLE, "IPython not installed")
class TestViewDisplay(unittest.TestCase):
    """Test figure view behavior across environments."""

    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.fig.add_subplot(111).plot([1, 2, 3], [1, 4, 9])

    def tearDown(self):
        """Clean up after each test."""
        glp.close()

    @patch('IPython.display.display')
    @patch('IPython.display.Image')
    @patch('IPython.get_ipython')
    @patch.object(glp.Figure, 'savefig')
    def test_view_notebook_png_displays_once_and_returns_none(
        self,
        mock_savefig,
        mock_get_ipython,
        mock_image,
        mock_display,
    ):
        """Notebook PNG view should display once and not return a rich object."""
        mock_get_ipython.return_value = Mock(config={'IPKernelApp': True})
        image_obj = object()
        mock_image.return_value = image_obj

        result = self.fig.view(format='png')

        self.assertIsNone(result)
        mock_savefig.assert_called_once()
        mock_image.assert_called_once()
        mock_display.assert_called_once_with(image_obj)

    @patch('IPython.get_ipython')
    @patch.object(glp.Figure, 'savefig')
    def test_view_non_notebook_returns_temp_path(self, mock_savefig, mock_get_ipython):
        """Non-notebook view should return temp file path."""
        mock_get_ipython.return_value = None

        result = self.fig.view(format='png')

        self.assertIsNotNone(result)
        self.assertEqual(result.suffix, '.png')
        mock_savefig.assert_called_once()


if __name__ == '__main__':
    unittest.main()

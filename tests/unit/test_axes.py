"""Unit tests for axis properties."""

import sys
from pathlib import Path
import re
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

    @staticmethod
    def _extract_amove_points(gle):
        """Return all amove coordinates as (x, y) float tuples."""
        return [
            (float(x), float(y))
            for x, y in re.findall(r'^amove\s+([0-9.]+)\s+([0-9.]+)$', gle, re.MULTILINE)
        ]

    @staticmethod
    def _extract_sizes(gle):
        """Return all graph size commands as (width, height) float tuples."""
        return [
            (float(w), float(h))
            for w, h in re.findall(r'^\s*size\s+([0-9.]+)\s+([0-9.]+)$', gle, re.MULTILINE)
        ]
    
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

    def test_subplots_adjust_changes_multiplot_geometry(self):
        """subplots_adjust should alter amove geometry in generated GLE."""
        fig, axes = glp.subplots(3, 1, figsize=(8, 9))
        for idx, ax in enumerate(axes):
            ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3])

        gle_default = fig._generate_gle()
        default_points = self._extract_amove_points(gle_default)
        self.assertEqual(len(default_points), 3)
        default_x = default_points[0][0]

        fig.subplots_adjust(left=0.2, right=0.98, bottom=0.12, top=0.95, hspace=0.45)
        gle_adjusted = fig._generate_gle()
        adjusted_points = self._extract_amove_points(gle_adjusted)
        self.assertEqual(len(adjusted_points), 3)
        adjusted_x = adjusted_points[0][0]

        # Increased normalized left margin should shift all subplots right.
        self.assertGreater(adjusted_x, default_x)

    def test_subplots_adjust_wspace_hspace_reduce_cell_size(self):
        """Positive wspace/hspace should reduce per-panel graph size."""
        fig, axes = glp.subplots(2, 2, figsize=(10, 8))
        for idx, ax in enumerate(axes):
            ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3])

        default_sizes = self._extract_sizes(fig._generate_gle())
        # First size command is global canvas size; subsequent entries are subplot sizes.
        default_subplot_sizes = default_sizes[1:]
        self.assertEqual(len(default_subplot_sizes), 4)

        fig.subplots_adjust(wspace=0.6, hspace=0.5)
        adjusted_sizes = self._extract_sizes(fig._generate_gle())
        adjusted_subplot_sizes = adjusted_sizes[1:]
        self.assertEqual(len(adjusted_subplot_sizes), 4)

        self.assertLess(adjusted_subplot_sizes[0][0], default_subplot_sizes[0][0])
        self.assertLess(adjusted_subplot_sizes[0][1], default_subplot_sizes[0][1])

    def test_subplots_adjust_validation_errors(self):
        """subplots_adjust should validate bounds and axis ordering."""
        fig = glp.figure()

        with self.assertRaisesRegex(ValueError, r'left must be within \[0, 1\]'):
            fig.subplots_adjust(left=-0.01)

        with self.assertRaisesRegex(ValueError, r'wspace must be >= 0'):
            fig.subplots_adjust(wspace=-0.5)

        with self.assertRaisesRegex(ValueError, 'left must be less than right'):
            fig.subplots_adjust(left=0.8, right=0.3)

        with self.assertRaisesRegex(ValueError, 'bottom must be less than top'):
            fig.subplots_adjust(bottom=0.7, top=0.2)

    def test_subplots_adjust_invalid_update_does_not_mutate_state(self):
        """Invalid updates should not partially overwrite previous settings."""
        fig = glp.figure()
        fig.subplots_adjust(left=0.15, right=0.9, top=0.95, bottom=0.1)

        with self.assertRaisesRegex(ValueError, 'left must be less than right'):
            fig.subplots_adjust(right=0.1)

        self.assertEqual(fig._subplot_adjust['left'], 0.15)
        self.assertEqual(fig._subplot_adjust['right'], 0.9)
        self.assertEqual(fig._subplot_adjust['top'], 0.95)
        self.assertEqual(fig._subplot_adjust['bottom'], 0.1)
    
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


class TestGridRatios(unittest.TestCase):
    """Test height_ratios/width_ratios on the multi-subplot grid."""

    def setUp(self):
        glp.close()

    def tearDown(self):
        glp.close()

    @staticmethod
    def _extract_sizes(gle):
        """Return all graph size commands as (width, height) float tuples."""
        return [
            (float(w), float(h))
            for w, h in re.findall(r'^\s*size\s+([0-9.]+)\s+([0-9.]+)$', gle, re.MULTILINE)
        ]

    @staticmethod
    def _extract_amove_points(gle):
        return [
            (float(x), float(y))
            for x, y in re.findall(r'^amove\s+([0-9.]+)\s+([0-9.]+)$', gle, re.MULTILINE)
        ]

    def test_default_omitted_height_ratios_is_byte_identical(self):
        """Omitting height_ratios must reproduce the pre-existing equal-row output."""
        from gleplot import axes as _gleplot_axes

        def build(**kwargs):
            fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 9), **kwargs)
            for idx, ax in enumerate(axes):
                ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3], color='blue')
            return fig

        glp.close()
        _gleplot_axes._global_data_file_counter = 0
        without = build()._generate_gle()
        glp.close()
        _gleplot_axes._global_data_file_counter = 0
        explicit_none = build(height_ratios=None, width_ratios=None)._generate_gle()

        self.assertEqual(without, explicit_none)

    def test_height_ratios_scales_row_sizes_proportionally(self):
        """A 3:1 height_ratios pair should split the plotting height 3:1."""
        fig, axes = glp.subplots(2, 1, sharex=True, figsize=(3.386, 4.0),
                                  height_ratios=[3, 1])
        for ax in axes:
            ax.plot([0, 1], [0, 1], color='blue')

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]  # drop the page 'size' command
        self.assertEqual(len(sizes), 2)
        top_h, bottom_h = sizes[0][1], sizes[1][1]
        self.assertAlmostEqual(top_h / bottom_h, 3.0, places=6)
        # Widths are unaffected by height_ratios.
        self.assertAlmostEqual(sizes[0][0], sizes[1][0], places=6)

    def test_width_ratios_scales_column_sizes_proportionally(self):
        """A 1:3 width_ratios pair should split the plotting width 1:3."""
        fig, axes = glp.subplots(1, 2, figsize=(10, 5), width_ratios=[1, 3])
        for ax in axes:
            ax.plot([0, 1], [0, 1], color='blue')

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        self.assertEqual(len(sizes), 2)
        left_w, right_w = sizes[0][0], sizes[1][0]
        self.assertAlmostEqual(right_w / left_w, 3.0, places=6)

    def test_height_ratios_five_row_stack_with_short_separator(self):
        """3 flush panels + a short separator row + a 4th panel, PRL-shaped."""
        fig, axes = glp.subplots(5, 1, sharex=True, figsize=(3.386, 5.5),
                                  height_ratios=[3, 3, 3, 1, 4])
        for ax in axes:
            ax.plot([0, 1], [0, 1], color='blue')

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        self.assertEqual(len(sizes), 5)
        heights = [h for _, h in sizes]
        # sharex=True -> zero vertical gap, so heights sum exactly to the
        # available plotting height (figure height minus margins).
        for a, b in ((0, 1), (1, 2)):
            self.assertAlmostEqual(heights[a], heights[b], places=6)
        self.assertAlmostEqual(heights[0] / heights[3], 3.0, places=6)
        self.assertAlmostEqual(heights[4] / heights[3], 4.0, places=6)

        # Panels are flush (sharex -> zero vspace): each row's top edge
        # meets the previous row's bottom edge exactly.
        amoves = self._extract_amove_points(gle)
        self.assertEqual(len(amoves), 5)
        for i in range(4):
            top_of_next = amoves[i + 1][1] + heights[i + 1]
            bottom_of_this = amoves[i][1]
            self.assertAlmostEqual(top_of_next, bottom_of_this, places=6)

    def test_height_ratios_length_mismatch_raises(self):
        fig, axes = glp.subplots(3, 1, height_ratios=[1, 2])
        with self.assertRaisesRegex(
            ValueError, r'height_ratios has length 2, but the subplot grid has 3 rows'
        ):
            fig._generate_gle()

    def test_width_ratios_length_mismatch_raises(self):
        fig, axes = glp.subplots(1, 2, width_ratios=[1, 2, 3])
        with self.assertRaisesRegex(
            ValueError, r'width_ratios has length 3, but the subplot grid has 2 columns'
        ):
            fig._generate_gle()

    def test_non_positive_ratio_raises(self):
        fig, axes = glp.subplots(2, 1, height_ratios=[1, 0])
        with self.assertRaisesRegex(ValueError, 'height_ratios entries must all be positive'):
            fig._generate_gle()

    def test_height_ratios_via_figure_and_add_subplot(self):
        """height_ratios also works through Figure()/add_subplot, not just subplots()."""
        fig = glp.figure(figsize=(3.386, 4.0), height_ratios=[3, 1])
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.plot([0, 1], [0, 1], color='blue')
        ax2.plot([0, 1], [0, 1], color='blue')

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        self.assertEqual(len(sizes), 2)
        self.assertAlmostEqual(sizes[0][1] / sizes[1][1], 3.0, places=6)

    def test_single_row_width_ratios_ignored_for_single_axes(self):
        """A single (1,1,1) axes must ignore height_ratios/width_ratios entirely."""
        fig = glp.figure(height_ratios=[1, 2, 3])
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1], color='blue')
        # Must not raise even though height_ratios has length 3 (there is
        # only ever 1 row on the single-axes path, which never validates it).
        gle = fig._generate_gle()
        self.assertIn('begin graph', gle)


class TestSecondaryYAxis(unittest.TestCase):
    """Test secondary y-axis (y2axis) functionality."""
    
    def setUp(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
    
    def test_y2_label(self):
        """Test setting y2axis label."""
        self.ax.set_ylabel('Primary Y', axis='y')
        self.ax.set_ylabel('Secondary Y', axis='y2')
        
        self.assertEqual(self.ax.ylabel_text, 'Primary Y')
        self.assertEqual(self.ax.y2label_text, 'Secondary Y')
    
    def test_y2_limits(self):
        """Test setting y2axis limits."""
        self.ax.set_ylim(0, 100, axis='y')
        self.ax.set_ylim(0, 1000, axis='y2')
        
        self.assertEqual(self.ax.ymin, 0)
        self.assertEqual(self.ax.ymax, 100)
        self.assertEqual(self.ax.y2min, 0)
        self.assertEqual(self.ax.y2max, 1000)
    
    def test_y2_scale(self):
        """Test setting y2axis scale."""
        self.ax.set_yscale('linear', axis='y')
        self.ax.set_yscale('log', axis='y2')
        
        self.assertEqual(self.ax.yscale, 'linear')
        self.assertEqual(self.ax.y2scale, 'log')
    
    def test_get_y2_limits(self):
        """Test getting y2axis limits."""
        self.ax.set_ylim(10, 20, axis='y2')
        
        y2min, y2max = self.ax.get_ylim(axis='y2')
        self.assertEqual(y2min, 10)
        self.assertEqual(y2max, 20)
    
    def test_plot_on_y2axis(self):
        """Test plotting on y2axis."""
        import numpy as np
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        
        self.ax.plot(x, y, yaxis='y2', label='Y2 Data')
        
        self.assertEqual(len(self.ax.lines), 1)
        self.assertEqual(self.ax.lines[0]['yaxis'], 'y2')
    
    def test_scatter_on_y2axis(self):
        """Test scatter plot on y2axis."""
        import numpy as np
        x = np.array([1, 2, 3])
        y = np.array([100, 200, 300])
        
        self.ax.scatter(x, y, yaxis='y2', label='Y2 Scatter')
        
        self.assertEqual(len(self.ax.scatters), 1)
        self.assertEqual(self.ax.scatters[0]['yaxis'], 'y2')
    
    def test_errorbar_on_y2axis(self):
        """Test errorbar plot on y2axis."""
        import numpy as np
        x = np.array([1, 2, 3])
        y = np.array([50, 100, 150])
        yerr = np.array([5, 10, 15])
        
        self.ax.errorbar(x, y, yerr=yerr, yaxis='y2', label='Y2 Error')
        
        self.assertEqual(len(self.ax.errorbars), 1)
        self.assertEqual(self.ax.errorbars[0]['yaxis'], 'y2')
    
    def test_mixed_y_and_y2_plots(self):
        """Test mixing plots on y and y2 axes."""
        import numpy as np
        x = np.array([1, 2, 3])
        
        self.ax.plot(x, x**2, yaxis='y', label='Y Data')
        self.ax.plot(x, x**3, yaxis='y2', label='Y2 Data')
        
        self.assertEqual(len(self.ax.lines), 2)
        self.assertEqual(self.ax.lines[0]['yaxis'], 'y')
        self.assertEqual(self.ax.lines[1]['yaxis'], 'y2')
    
    def test_has_y2_plots(self):
        """Test has_y2_plots helper method."""
        import numpy as np
        x = np.array([1, 2, 3])
        
        # Initially no y2 plots
        self.assertFalse(self.ax.has_y2_plots())
        
        # Add plot on y axis
        self.ax.plot(x, x**2, yaxis='y')
        self.assertFalse(self.ax.has_y2_plots())
        
        # Add plot on y2 axis
        self.ax.plot(x, x**3, yaxis='y2')
        self.assertTrue(self.ax.has_y2_plots())
    
    def test_y2_gle_generation(self):
        """Test that y2axis generates correct GLE code."""
        import numpy as np
        x = np.array([1, 2, 3])
        
        self.ax.plot(x, x**2, color='red', label='Y1', yaxis='y')
        self.ax.plot(x, x**3, color='blue', label='Y2', yaxis='y2')
        self.ax.set_ylabel('Primary', axis='y')
        self.ax.set_ylabel('Secondary', axis='y2')
        self.ax.set_ylim(0, 10, axis='y')
        self.ax.set_ylim(0, 30, axis='y2')
        
        gle = self.fig._generate_gle()
        
        # Check for y2axis directives
        self.assertIn('y2title "Secondary"', gle)
        self.assertIn('y2axis min 0 max 30', gle)
        self.assertIn('y2axis', gle)  # y2axis keyword on plot command
    
    def test_y2_log_scale_gle(self):
        """Test that y2axis log scale generates correct GLE code."""
        import numpy as np
        x = np.array([1, 2, 3, 4])
        y = np.array([10, 100, 1000, 10000])
        
        self.ax.plot(x, y, yaxis='y2')
        self.ax.set_yscale('log', axis='y2')
        
        gle = self.fig._generate_gle()
        self.assertIn('y2axis log', gle)
    
    def test_y2_with_figure_convenience_methods(self):
        """Test y2axis with figure-level ylabel convenience method."""
        self.fig.ylabel('Primary Y', axis='y')
        self.fig.ylabel('Secondary Y', axis='y2')
        
        ax = self.fig.gca()
        self.assertEqual(ax.ylabel_text, 'Primary Y')
        self.assertEqual(ax.y2label_text, 'Secondary Y')


if __name__ == '__main__':
    unittest.main()

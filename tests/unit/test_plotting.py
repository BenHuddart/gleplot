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

    def test_line_with_data_name(self):
        """Test semantic data file naming for line plots."""
        self.ax.plot([1, 2, 3], [3, 2, 1], data_name='Observed Signal')
        self.assertEqual(self.ax.lines[0]['data_file'], 'observed_signal.dat')

    def test_line_with_marker_stays_a_line(self):
        """plot() with a marker AND a solid line keeps it a line series.

        Regression: previously a marker requested alongside the default solid
        linestyle was silently dropped (the line branch forced marker=None).
        """
        self.ax.plot([1, 2, 3], [1, 2, 3], marker='o')

        self.assertEqual(len(self.ax.lines), 1)
        self.assertEqual(len(self.ax.scatters), 0)
        self.assertEqual(self.ax.lines[0]['marker'], 'FCIRCLE')

    def test_line_without_marker_stores_none(self):
        """A plain line still stores marker=None (schema unchanged)."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        self.assertIn('marker', self.ax.lines[0])
        self.assertIsNone(self.ax.lines[0]['marker'])

    def test_line_with_marker_emits_line_and_marker_gle(self):
        """Generated GLE for a line+marker series contains both tokens."""
        self.ax.plot([1, 2, 3], [1, 2, 3], marker='o', label='pts')
        gle = self.fig._generate_gle()
        # The dataset draw command must carry a line AND a marker directive.
        draw_lines = [
            ln for ln in gle.splitlines()
            if ' line' in ln and 'marker' in ln
        ]
        self.assertTrue(
            draw_lines,
            f"Expected a draw command with both 'line' and 'marker'.\n{gle}",
        )


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
        """A colour sequence is one series per bar, each with a real width."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color=['red', 'green', 'blue'])

        self.assertEqual(len(self.ax.bars), 3)
        self.assertEqual(
            [bar['colors'][0] for bar in self.ax.bars],
            ['RED', 'GREEN', 'BLUE'],
        )
        self.assertEqual([bar['width'] for bar in self.ax.bars], [0.5, 0.5, 0.5])
        text = self.fig._generate_gle()
        self.assertEqual(text.count('bar d'), 3)
        self.assertIn('fill RED', text)
        self.assertIn('fill GREEN', text)
        self.assertIn('fill BLUE', text)
        self.assertIn('width 0.5', text)

    def test_bar_uniform_color_list_stays_one_series(self):
        """The same colour repeated is still the historical one-dataset bar."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color=['red', 'red', 'red'])
        self.assertEqual(len(self.ax.bars), 1)
        self.assertEqual(self.ax.bars[0]['colors'], ['RED', 'RED', 'RED'])
        self.assertNotIn('width', self.ax.bars[0])

    def test_bar_edge_and_stack_and_barh(self):
        """Stroke, baseline, and horizontal bars reach the script."""
        self.ax.bar(
            [1, 2], [3, 4], color='red', edgecolor='k', linewidth=2, linestyle='--'
        )
        self.ax.bar([1, 2], [1, 1], bottom=[3, 4], color='white')
        self.ax.barh([1, 2], [3, 4])
        text = self.fig._generate_gle()
        self.assertIn('color BLACK', text)
        self.assertIn('lstyle', text)
        self.assertIn('lwidth', text)
        self.assertIn('from', text)
        self.assertIn('horiz', text)
        stacked = self.ax.bars[1]
        self.assertTrue((stacked['bottom'] == [3, 4]).all())
        self.assertNotIn('bottom', self.ax.bars[0])

    def test_bar_zero_baseline_is_not_stored(self):
        self.ax.bar([1, 2], [3, 4], bottom=0)
        self.assertNotIn('bottom', self.ax.bars[0])
        self.assertNotIn('from', self.fig._generate_gle())

    def test_bar_align_edge_and_hatch_warn(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.ax.bar([1, 2], [3, 4], align='edge', hatch='//')
        messages = ' '.join(str(item.message) for item in caught)
        self.assertIn('centered', messages)
        self.assertIn('hatch', messages)

    def test_bar_color_length_must_match(self):
        with self.assertRaises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], color=['red', 'blue'])

    def test_bar_with_data_name(self):
        """Test semantic data file naming for bar plots."""
        self.ax.bar([1, 2, 3], [10, 20, 30], data_name='Bar Data #1')
        self.assertEqual(self.ax.bars[0]['data_file'], 'bar_data_1.dat')

    def test_bar_yerr_sits_on_the_tip(self):
        """Symmetric and asymmetric y errors are whiskers at bottom+height."""
        self.ax.bar([1, 2, 3], [4, 5, 6], yerr=0.5, capsize=3, label='h')
        self.assertEqual(len(self.ax.bars), 1)
        self.assertEqual(len(self.ax.errorbars), 1)
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb['x'], [1, 2, 3])
        np.testing.assert_array_equal(eb['y'], [4, 5, 6])
        np.testing.assert_array_equal(eb['yerr_up'], [0.5, 0.5, 0.5])
        np.testing.assert_array_equal(eb['yerr_down'], [0.5, 0.5, 0.5])
        self.assertIsNone(eb['xerr_left'])
        self.assertIsNone(eb['label'])
        self.assertEqual(eb['linestyle'], 'none')
        self.assertIsNone(eb['marker'])
        self.assertEqual(eb['color'], 'BLACK')
        self.assertEqual(eb['capsize'], 3)
        text = self.fig._generate_gle()
        self.assertIn('err ', text)
        self.assertIn('errwidth', text)
        self.assertNotIn('herr', text)
        self.assertEqual(text.count('key "h"'), 1)
        self.assertEqual(self.ax.ymax, 6.5)

        glp.close()
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.bar(
            [1, 2],
            [4, 5],
            bottom=[1, 2],
            yerr=([0.1, 0.2], [0.3, 0.4]),
        )
        eb = ax.errorbars[0]
        np.testing.assert_array_equal(eb['y'], [5, 7])
        np.testing.assert_array_equal(eb['yerr_down'], [0.1, 0.2])
        np.testing.assert_array_equal(eb['yerr_up'], [0.3, 0.4])
        self.assertIn('errup', fig._generate_gle())
        self.assertIn('errdown', fig._generate_gle())

    def test_barh_xerr_sits_on_the_tip(self):
        """Horizontal length errors run from left+width, and widen x."""
        self.ax.barh([1, 2], [4, 5], left=1, xerr=0.5, yerr=0.25, capsize=4)
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb['x'], [5, 6])
        np.testing.assert_array_equal(eb['y'], [1, 2])
        np.testing.assert_array_equal(eb['xerr_left'], [0.5, 0.5])
        np.testing.assert_array_equal(eb['yerr_up'], [0.25, 0.25])
        text = self.fig._generate_gle()
        self.assertIn('horiz', text)
        self.assertIn('herr ', text)
        self.assertIn('err ', text)
        self.assertEqual(self.ax.xmax, 6.5)
        self.assertEqual(self.ax.ymax, 2.25)

    def test_bar_error_shapes_and_colors(self):
        """(2, n) is asymmetric; a colour sequence is one whisker series each."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.ax.bar(
                [1, 2],
                [3, 4],
                yerr=np.array([[0.1, 0.2], [0.3, 0.4]]),
                ecolor=['red', 'blue'],
                error_kw={'capsize': 2, 'elinewidth': 1.5},
            )
        messages = ' '.join(str(item.message) for item in caught)
        self.assertIn('elinewidth', messages)
        self.assertEqual(len(self.ax.errorbars), 2)
        self.assertEqual(
            [eb['color'] for eb in self.ax.errorbars],
            ['RED', 'BLUE'],
        )
        np.testing.assert_array_equal(self.ax.errorbars[0]['yerr_down'], [0.1])
        np.testing.assert_array_equal(self.ax.errorbars[1]['yerr_up'], [0.4])
        self.assertEqual(self.ax.errorbars[0]['capsize'], 2)

        before = len(self.ax.bars)
        with self.assertRaises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], yerr=[0.1, 0.2])
        self.assertEqual(len(self.ax.bars), before)
        with self.assertRaises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], yerr=float('nan'))
        with self.assertRaises(ValueError):
            self.ax.bar([1, 2], [3, 4], xerr=[0.1, float('nan')])
        with self.assertRaises(TypeError):
            self.ax.bar([1, 2], [3, 4], yerr=0.1, error_kw='nope')

        glp.close()
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.bar([1, 2, 3], [4, 5, 6], yerr=[[0.2], [0.5]], capsize_cm=0.1)
        eb = ax.errorbars[0]
        np.testing.assert_array_equal(eb['yerr_down'], [0.2, 0.2, 0.2])
        np.testing.assert_array_equal(eb['yerr_up'], [0.5, 0.5, 0.5])
        self.assertEqual(eb['gle_capsize'], 0.1)
        self.assertEqual(len(ax.errorbars), 1)
        ax.bar([10, 20, 30], [1, 1, 1], yerr=[0.4], xerr=0.2)
        whisker = ax.errorbars[1]
        np.testing.assert_array_equal(whisker['x'], [10, 20, 30])
        np.testing.assert_array_equal(whisker['y'], [1, 1, 1])
        np.testing.assert_array_equal(whisker['yerr_up'], [0.4, 0.4, 0.4])
        np.testing.assert_array_equal(whisker['xerr_right'], [0.2, 0.2, 0.2])

    def test_bar_error_kw_capsize_and_zorder(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.ax.bar(
                [1, 2],
                [3, 4],
                yerr=0.2,
                capsize=5,
                zorder=4,
                ecolor='green',
                error_kw={'ecolor': 'red', 'zorder': 8, 'capsize': 1},
            )
        messages = ' '.join(str(item.message) for item in caught)
        self.assertNotIn('error_kw', messages)
        eb = self.ax.errorbars[0]
        self.assertEqual(eb['color'], 'RED')
        self.assertEqual(eb['capsize'], 1)
        self.assertEqual(eb['zorder'], 8.01)
        self.assertEqual(self.ax.bars[0]['zorder'], 4)

    def test_bar_without_errors_adds_no_whisker(self):
        self.ax.bar([1, 2, 3], [4, 5, 6], capsize=3, ecolor='red')
        self.assertEqual(self.ax.errorbars, [])
        self.assertNotIn('err ', self.fig._generate_gle())


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

    def test_fill_with_data_name(self):
        """Test semantic data file naming for generated fill data."""
        self.ax.fill_between([1, 2, 3], [1, 2, 3], [2, 4, 6], data_name='Component Lambda 2D Fill')
        self.assertEqual(self.ax.fills[0]['data_file'], 'component_lambda_2d_fill.dat')

    def test_data_name_collision_is_disambiguated(self):
        """Test that duplicate custom names are made unique automatically."""
        self.ax.plot([1, 2], [1, 2], data_name='model-range')
        self.ax.plot([1, 2], [2, 3], data_name='model-range')

        self.assertEqual(self.ax.lines[0]['data_file'], 'model-range.dat')
        self.assertEqual(self.ax.lines[1]['data_file'], 'model-range_1.dat')

    def _script(self):
        return self.fig._generate_gle()

    def test_default_y2_is_a_constant_zero_curve(self):
        """Omitting y2 fills to 0, matplotlib's default, as a second dataset."""
        self.ax.fill_between([0, 1, 2], [1, -1, 1])
        series = self.ax.fills[0]
        self.assertIsNone(series.get("target"))
        self.assertEqual(list(series["y2"]), [0.0, 0.0, 0.0])
        script = self._script()
        self.assertIn("fill d1,d2 color LIGHTBLUE", script)
        self.assertNotIn("fill x1", script)

    def test_baseline_emits_an_axis_fill(self):
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x1", label="down")
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x2", ymin=3)
        script = self._script()
        self.assertIn("fill x1,d1 color LIGHTBLUE", script)
        self.assertIn('d1 keyfill LIGHTBLUE key "down"', script)
        self.assertIn("fill d2,x2 color LIGHTBLUE ymin 3", script)
        self.assertIsNone(self.ax.fills[0]["y2"])
        self.assertEqual(self.ax.fills[1]["target"], "x2")
        self.assertEqual(self.ax.fills[1]["ymin"], 3.0)

    def test_issue_example_fills_to_zero_where_x_is_positive(self):
        """``fill_between(x, y, where=(x > 0))`` is a constant zero curve, clipped."""
        x = [-1.0, 0.0, 1.0, 2.0]
        self.ax.fill_between(x, [1.0, 1.0, 1.0, 1.0], where=[v > 0 for v in x])
        self.assertEqual(len(self.ax.fills), 1)
        self.assertEqual(list(self.ax.fills[0]["y2"]), [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(self.ax.fills[0]["xmin"], 1.0)
        self.assertIn("fill d1,d2 color LIGHTBLUE xmin 1", self._script())

    def test_where_on_a_decreasing_x_uses_data_edges(self):
        self.ax.fill_between(
            [4, 3, 2, 1],
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            where=[False, True, True, False],
        )
        self.assertEqual(self.ax.fills[0].get("xmin"), 2.0)
        self.assertEqual(self.ax.fills[0].get("xmax"), 3.0)

    def test_where_clips_each_true_run(self):
        x = [0, 1, 2, 3, 4]
        self.ax.fill_between(
            x,
            [1, 1, 1, 1, 1],
            [0, 0, 0, 0, 0],
            where=[True, True, False, True, True],
            label="band",
        )
        self.assertEqual(len(self.ax.fills), 2)
        self.assertEqual(self.ax.fills[0].get("xmax"), 1.0)
        self.assertNotIn("xmin", self.ax.fills[0])
        self.assertEqual(self.ax.fills[1].get("xmin"), 3.0)
        self.assertEqual(self.ax.fills[0]["label"], "band")
        self.assertIsNone(self.ax.fills[1]["label"])
        script = self._script()
        self.assertIn("fill d1,d2 color LIGHTBLUE xmax 1", script)
        self.assertIn("fill d3,d4 color LIGHTBLUE xmin 3", script)

    def test_isolated_true_draws_nothing(self):
        self.ax.fill_between([0, 1, 2], [1, 1, 1], where=[False, True, False])
        self.assertEqual(self.ax.fills, [])
        self.assertNotIn("fill ", self._script())

    def test_interpolate_moves_the_clip_to_the_crossing(self):
        self.ax.fill_between(
            [0, 1, 2],
            [0, 0, 2],
            [1, 1, 0],
            where=[False, False, True],
            interpolate=True,
        )
        self.assertEqual(len(self.ax.fills), 1)
        self.assertAlmostEqual(self.ax.fills[0]["xmin"], 4.0 / 3.0)
        self.assertIn("xmin 1.33333", self._script())

    def test_repeated_x_ignores_where(self):
        """A shared x cannot be split into True and False by a rectangle."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between(
                [0, 1, 1, 2],
                [1, 1, 5, 5],
                [0, 0, 0, 0],
                where=[True, True, False, False],
            )
        self.assertTrue(any("monotonic" in str(w.message) for w in caught))
        self.assertEqual(len(self.ax.fills), 1)
        self.assertNotIn("xmax", self.ax.fills[0])

    def test_polygon_and_axis_fill_round_trip_through_to_dict(self):
        self.ax.fill([0, 1, 0], [0, 1, 2], alpha=0.4)
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x1", ymin=0)
        restored = glp.Figure.from_dict(self.fig.to_dict())
        fills = restored.axes_list[0].fills
        self.assertEqual(fills[0]["target"], "polygon")
        self.assertIsNone(fills[0]["y2"])
        self.assertEqual(fills[1]["target"], "x1")
        self.assertIsNone(fills[1]["y2"])
        self.assertEqual(fills[1]["ymin"], 0.0)
        self.assertEqual(restored.to_dict(), self.fig.to_dict())

    def test_non_monotonic_where_warns_and_is_ignored(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between([0, 2, 1], [1, 1, 1], where=[True, False, True])
        self.assertTrue(any("monotonic" in str(w.message) for w in caught))
        self.assertEqual(len(self.ax.fills), 1)
        self.assertNotIn("xmin", self.ax.fills[0])
        self.assertNotIn("xmax", self.ax.fills[0])

    def test_where_and_explicit_x_clip_conflict(self):
        with self.assertRaises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], where=[True, True], xmin=0)

    def test_baseline_rejects_a_second_curve(self):
        with self.assertRaises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], [0, 0], baseline="x1")

    def test_polygon_fill_closes_one_dataset(self):
        returned = self.ax.fill([0, 1, 0], [0, 1, 2], alpha=0.4, label="tri")
        self.assertIs(returned, self.ax)
        series = self.ax.fills[0]
        self.assertEqual(series["target"], "polygon")
        self.assertIsNone(series["y2"])
        script = self._script()
        self.assertIn("fill d1 color rgba255(", script)
        self.assertIn("d1 keyfill rgba255(", script)
        self.assertIn('key "tri"', script)
        self.assertNotIn("fill d1,d2", script)

    def test_step_and_edge_keywords_warn(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between([0, 1], [1, 1], step="pre", hatch="//")
            self.ax.fill(
                [0, 1, 0],
                [0, 1, 2],
                edgecolor="black",
                linewidth=2,
                linestyle="--",
            )
        messages = " ".join(str(w.message) for w in caught)
        self.assertIn("step", messages)
        self.assertIn("hatch", messages)
        self.assertIn("edgecolor", messages)
        self.assertIn("linewidth", messages)
        self.assertIn("linestyle", messages)

    def test_where_length_and_baseline_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], where=[True])
        with self.assertRaises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], baseline="y")
        with self.assertRaises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], [2, 3, 4])
        with self.assertRaises(ValueError):
            self.ax.fill([[0, 1], [1, 0]], [0, 1])

    def test_full_mask_and_empty_mask(self):
        self.ax.fill_between([0, 1, 2], [1, 1, 1], where=[True, True, True])
        self.assertNotIn("xmin", self.ax.fills[0])
        self.ax.fill_between([0, 1], [1, 1], where=[False, False])
        self.assertEqual(len(self.ax.fills), 1)

    def test_non_finite_x_ignores_where(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between(
                [0, float("nan"), 2], [1, 1, 1], where=[True, False, True]
            )
        self.assertTrue(any("monotonic" in str(w.message) for w in caught))
        self.assertNotIn("xmin", self.ax.fills[0])

    def test_axis_interpolate_stays_on_the_samples(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between(
                [0, 1, 2],
                [1, 1, 1],
                baseline="x1",
                where=[False, True, True],
                interpolate=True,
            )
        self.assertTrue(any("interpolate" in str(w.message) for w in caught))
        self.assertEqual(self.ax.fills[0]["xmin"], 1.0)

    def test_interpolate_moves_the_right_edge_to_the_crossing(self):
        self.ax.fill_between(
            [0, 1, 2],
            [2, 0, 0],
            [0, 1, 1],
            where=[True, False, False],
            interpolate=True,
        )
        self.assertAlmostEqual(self.ax.fills[0]["xmax"], 2.0 / 3.0)
        self.assertNotIn("xmin", self.ax.fills[0])

    def test_polygon_takes_one_color_and_one_polygon(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill(
                [0, 1, 0],
                [0, 1, 2],
                (0.0, 0.0, 1.0),
                [2, 3, 2],
                [0, 1, 2],
            )
        self.assertTrue(any("extra polygons" in str(w.message) for w in caught))
        self.assertIn("rgb255(0,0,255)", self.ax.fills[0]["color"])
        self.assertEqual(len(self.ax.fills), 1)


class TestDataPrefixValidation(unittest.TestCase):
    """Test that a figure-level data_prefix is validated, not sanitized.

    Unlike ``data_name`` (a label, sanitized into a stem by the tests above),
    ``data_prefix`` is used verbatim to build sidecar filenames. A prefix GLE
    cannot parse must therefore fail in Python at the point it is supplied,
    rather than producing a script that aborts at compile time with
    ``>> Error: left hand side contains unquoted string``.
    """

    def tearDown(self):
        glp.close()

    def test_plus_in_prefix_raises_instead_of_failing_at_compile_time(self):
        """The reported reproducer: 'mk+white' produced unparseable GLE."""
        with self.assertRaises(ValueError) as ctx:
            glp.figure(data_prefix='mk+white')

        message = str(ctx.exception)
        self.assertIn('mk+white', message)  # names the offending value
        self.assertIn("'+'", message)       # ...and the offending character

    def test_forbidden_characters_are_rejected(self):
        """Every character GLE cannot read in an unquoted data filename."""
        # '!', '"' and '+' were confirmed against GLE 4.3.10 by compiling a
        # data file containing each; '/' and '\\' are path separators.
        for prefix in ['a!b', 'a"b', 'a+b', 'a/b', 'a\\b']:
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError):
                    glp.figure(data_prefix=prefix)

    def test_whitespace_and_control_characters_are_rejected(self):
        for prefix in ['a b', 'a\tb', 'a\nb', 'a\x00b', 'a\x1fb']:
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError):
                    glp.figure(data_prefix=prefix)

    def test_empty_prefix_is_rejected(self):
        for prefix in ['', '   ']:
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError):
                    glp.figure(data_prefix=prefix)

    def test_non_string_prefix_raises_type_error(self):
        with self.assertRaises(TypeError):
            glp.figure(data_prefix=42)

    def test_none_prefix_keeps_default_naming(self):
        """None is not a bad value -- it selects the global data_N counter."""
        fig = glp.figure(data_prefix=None)
        self.assertIsNone(fig.data_prefix)

    def test_valid_prefix_is_preserved_verbatim(self):
        """Case and legal punctuation must survive: no sanitizing here.

        Sanitizing would lowercase, silently turning the documented
        ``data_prefix='experimentA'`` into ``experimenta_0.dat``.
        """
        for prefix in ['experimentA', 'run42', 'exp-1.2', 'a#b', 'a,b', 'a=b']:
            with self.subTest(prefix=prefix):
                fig = glp.figure(data_prefix=prefix)
                self.assertEqual(fig.data_prefix, prefix)

    def test_valid_prefix_drives_sidecar_filenames(self):
        fig = glp.figure(data_prefix='experimentA')
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.plot([1, 2, 3], [3, 2, 1])

        self.assertEqual(ax.lines[0]['data_file'], 'experimentA_0.dat')
        self.assertEqual(ax.lines[1]['data_file'], 'experimentA_1.dat')

    def test_subplots_validates_prefix_too(self):
        with self.assertRaises(ValueError):
            glp.subplots(1, 2, data_prefix='mk+white')

    def test_from_dict_restores_a_prefix_init_would_reject(self):
        """Recorded state round-trips even when it would fail validation.

        The recognizer derives a prefix from filenames already present in a
        parsed .gle, and a quoted ``data "my file_0.dat"`` yields the prefix
        ``my file``. from_dict restores such a figure verbatim -- validating
        there would make the figure impossible to reload and would break GUI
        undo/redo, which restores every snapshot through from_dict.
        """
        fig = glp.figure()
        fig.add_subplot(111).plot([1, 2], [1, 2])
        fig.data_prefix = 'my file'

        restored = glp.Figure.from_dict(fig.to_dict())

        self.assertEqual(restored.data_prefix, 'my file')


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
        self.assertAlmostEqual(self.ax.xmin, 0.7)
        self.assertAlmostEqual(self.ax.xmax, 3.3)
    
    def test_figure_errorbar_method(self):
        """Test Figure-level errorbar convenience method."""
        self.fig.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5)
        
        ax = self.fig.gca()
        self.assertEqual(len(ax.errorbars), 1)


class TestErrorbarFromFile(unittest.TestCase):
    """Test errorbar_from_file functionality for direct column references."""
    
    def setUp(self):
        """Create fresh figure and test data file for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        
        # Create a temporary data file
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.dat', delete=False)
        self.data_path = Path(self.temp_file.name)
        
        # Write test data: x, y, yerr
        self.temp_file.write("! Test data file\n")
        self.temp_file.write("! x  y  yerr\n")
        self.temp_file.write("1.0  10.0  0.5\n")
        self.temp_file.write("2.0  20.0  0.8\n")
        self.temp_file.write("3.0  30.0  0.6\n")
        self.temp_file.write("4.0  40.0  0.7\n")
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        # Remove temp file
        if self.data_path.exists():
            self.data_path.unlink()
    
    def test_errorbar_from_file_basic(self):
        """Test basic errorbar_from_file with column references."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            marker='o',
            color='blue'
        )
        
        self.assertEqual(len(self.ax.file_series), 1)
        series = self.ax.file_series[0]
        self.assertEqual(series['data_file'], str(self.data_path))
        self.assertEqual(series['x_col'], 1)
        self.assertEqual(series['y_col'], 2)
        self.assertEqual(series['yerr_col'], 3)
        self.assertEqual(series['marker'], 'FCIRCLE')  # 'o' -> 'FCIRCLE'
        self.assertEqual(series['color'], 'BLUE')
    
    def test_errorbar_from_file_without_errors(self):
        """Test errorbar_from_file without error column."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=None,
            marker='s',
            color='red'
        )
        
        series = self.ax.file_series[0]
        self.assertIsNone(series['yerr_col'])
    
    def test_errorbar_from_file_with_label(self):
        """Test errorbar_from_file with legend label."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            label='Test Data',
            marker='o'
        )
        
        series = self.ax.file_series[0]
        self.assertEqual(series['label'], 'Test Data')
    
    def test_errorbar_from_file_y2axis(self):
        """Test errorbar_from_file on secondary y-axis."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            yaxis='y2',
            marker='o',
            color='green'
        )
        
        series = self.ax.file_series[0]
        self.assertEqual(series['yaxis'], 'y2')
    
    def test_errorbar_from_file_with_capsize(self):
        """Test errorbar_from_file with capsize parameter."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            capsize=4,
            marker='o'
        )
        
        series = self.ax.file_series[0]
        # Capsize is converted: capsize * 0.0353
        self.assertAlmostEqual(series['capsize'], 0.1412, places=4)
    
    def test_errorbar_from_file_gle_generation(self):
        """Test GLE script generation for errorbar_from_file."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            marker='o',
            color='blue',
            label='File Data'
        )
        
        gle = self.fig._generate_gle()
        # Check for data command with column references
        self.assertIn('data', gle)
        self.assertIn('d1=c1,c2', gle)  # x_col=1, y_col=2
        self.assertIn('d2=c1,c3', gle)   # yerr includes x_col
        self.assertIn('key "File Data"', gle)
    
    def test_errorbar_from_file_has_plots(self):
        """Test that errorbar_from_file counts in has_plots()."""
        self.assertFalse(self.ax.has_plots())
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3
        )
        self.assertTrue(self.ax.has_plots())


class TestLineFromFile(unittest.TestCase):
    """Test line_from_file functionality for direct file-based line overlays."""

    def setUp(self):
        """Create fresh figure and test data file for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)

        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.fit', delete=False)
        self.data_path = Path(self.temp_file.name)
        self.temp_file.write("! Model fit curve\n")
        self.temp_file.write("1.0  10.0\n")
        self.temp_file.write("2.0  12.0\n")
        self.temp_file.write("3.0  13.0\n")
        self.temp_file.close()

    def tearDown(self):
        """Clean up after each test."""
        glp.close()
        if self.data_path.exists():
            self.data_path.unlink()

    def test_line_from_file_basic(self):
        """Test basic line_from_file column references."""
        self.ax.line_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            color='red',
            linewidth=2,
            label='Fit',
        )

        self.assertEqual(len(self.ax.file_series), 1)
        series = self.ax.file_series[0]
        self.assertEqual(series['series_type'], 'line')
        self.assertEqual(series['data_file'], str(self.data_path))
        self.assertEqual(series['x_col'], 1)
        self.assertEqual(series['y_col'], 2)
        self.assertEqual(series['color'], 'RED')
        self.assertEqual(series['linewidth'], 2.0)
        self.assertEqual(series['label'], 'Fit')

    def test_line_from_file_gle_generation(self):
        """Test GLE script generation for line_from_file."""
        self.ax.line_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            color='red',
            linestyle='-',
            linewidth=1,
            label='Fit line',
        )

        gle = self.fig._generate_gle()
        self.assertIn('data', gle)
        self.assertIn('d1=c1,c2', gle)
        self.assertIn('line color RED', gle)
        self.assertIn('key "Fit line"', gle)


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


class TestLineModes(unittest.TestCase):
    """Step, stem and histogram outlines are GLE line modes."""

    def setUp(self):
        glp.close()
        self.fig = glp.figure(data_prefix='modes')
        self.ax = self.fig.add_subplot(111)

    def tearDown(self):
        glp.close()

    def _draw(self):
        return [
            ln.strip()
            for ln in self.fig._generate_gle().splitlines()
            if ' line' in ln
        ]

    def test_plain_plot_stays_a_plain_line(self):
        self.ax.plot([0, 1, 2], [1, 2, 1])
        self.assertNotIn('line_mode', self.ax.lines[0])
        draw = ' '.join(self._draw())
        for mode in ('steps', 'fsteps', 'hist', 'impulses', 'bar'):
            self.assertNotIn(' line %s' % mode, draw)

    def test_step_where_selects_the_gle_mode(self):
        cases = (('pre', 'fsteps'), ('post', 'steps'), ('mid', 'hist'))
        for where, mode in cases:
            with self.subTest(where=where):
                glp.close()
                fig = glp.figure(data_prefix='modes')
                ax = fig.add_subplot(111)
                ax.step([0, 1, 2], [1, 0, 1], where=where, color='black')
                self.assertEqual(ax.lines[0]['line_mode'], mode)
                self.assertIn(' line %s ' % mode, fig._generate_gle())

    def test_drawstyle_names_and_the_steps_alias(self):
        self.ax.plot([0, 1], [1, 2], drawstyle='steps')
        self.ax.plot([0, 1], [2, 1], ds='steps-post')
        self.ax.plot([0, 1], [0, 1], drawstyle='default')
        self.assertEqual(self.ax.lines[0]['line_mode'], 'fsteps')
        self.assertEqual(self.ax.lines[1]['line_mode'], 'steps')
        self.assertNotIn('line_mode', self.ax.lines[2])

    def test_unknown_where_or_drawstyle_raises(self):
        with self.assertRaises(ValueError):
            self.ax.step([0, 1], [0, 1], where='side')
        with self.assertRaises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle='steps-left')
        with self.assertRaises(ValueError):
            self.ax.plot([0, 1], [0, 1], line_mode='spline')
        with self.assertRaises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle='steps-pre', ds='steps-post')
        with self.assertRaises(ValueError):
            self.ax.stem([0, 1], orientation='sideways')
        with self.assertRaises(TypeError):
            self.ax.stem()
        with self.assertWarns(UserWarning):
            self.ax.stem([0, 1], [1, 2], bottom='low')

    def test_drawstyle_and_line_mode_must_agree(self):
        with self.assertRaises(ValueError):
            self.ax.plot(
                [0, 1], [0, 1], drawstyle='steps-post', line_mode='hist'
            )

    def test_step_format_string_warns_and_is_not_applied(self):
        with self.assertWarns(UserWarning):
            self.ax.step([0, 1], [0, 1], 'r--')
        self.assertEqual(self.ax.lines[0]['line_mode'], 'fsteps')
        self.assertEqual(self.ax.lines[0]['color'], 'BLUE')

    def test_line_mode_with_no_line_warns_and_is_dropped(self):
        with self.assertWarns(UserWarning):
            self.ax.plot(
                [0, 1],
                [0, 1],
                drawstyle='steps-mid',
                linestyle='none',
                marker='o',
            )
        self.assertEqual(len(self.ax.scatters), 1)
        self.assertNotIn('line_mode', self.ax.scatters[0])

    def test_stem_emits_impulses_and_a_head_marker(self):
        returned = self.ax.stem([0, 1, 2], [1, 0, 1], label='spikes')
        self.assertIs(returned, self.ax)
        series = self.ax.lines[0]
        self.assertEqual(series['line_mode'], 'impulses')
        self.assertEqual(series['marker'], 'FCIRCLE')
        self.assertEqual(series['label'], 'spikes')
        gle = self.fig._generate_gle()
        self.assertIn(' line impulses ', gle)
        self.assertIn('marker FCIRCLE', gle)

    def test_stem_of_y_alone_uses_integer_x(self):
        self.ax.stem([4, 5, 6])
        np.testing.assert_array_equal(self.ax.lines[0]['x'], [0.0, 1.0, 2.0])

    def test_stem_linefmt_sets_color_and_linestyle(self):
        self.ax.stem([0, 1], [1, 2], linefmt='r--', markerfmt='none')
        series = self.ax.lines[0]
        self.assertEqual(series['color'], 'RED')
        self.assertEqual(series['linestyle'], '--')
        self.assertIsNone(series['marker'])
        self.assertEqual(series['line_mode'], 'impulses')

    def test_stem_gaps_warn(self):
        with self.assertWarns(UserWarning):
            self.ax.stem([0, 1], [1, 2], bottom=1)
        with self.assertWarns(UserWarning):
            self.ax.stem([0, 1], [1, 2], orientation='horizontal')
        with self.assertWarns(UserWarning):
            self.ax.stem([0, 1], [1, 2], basefmt='C3-')
        self.assertEqual(len(self.ax.lines), 3)
        self.assertTrue(all(ln['line_mode'] == 'impulses' for ln in self.ax.lines))

    def test_stem_none_line_draws_markers_only(self):
        with self.assertWarns(UserWarning):
            self.ax.stem([0, 1], [1, 2], linefmt='none')
        self.assertEqual(len(self.ax.lines), 0)
        self.assertEqual(len(self.ax.scatters), 1)

    def test_line_from_file_drawstyle(self):
        self.ax.line_from_file('wave.csv', 1, 2, drawstyle='steps-mid')
        self.assertEqual(self.ax.file_series[0]['line_mode'], 'hist')
        self.assertIn(' line hist ', self.fig._generate_gle())

    def test_line_from_file_drops_a_mode_when_the_line_is_off(self):
        with self.assertWarns(UserWarning):
            self.ax.line_from_file(
                'wave.csv', 1, 2, linestyle='none', drawstyle='steps-mid'
            )
        self.assertNotIn('line_mode', self.ax.file_series[0])

    def test_a_line_mode_stays_unsmoothed_when_the_figure_smooths(self):
        self.fig.graph.smooth_curves = True
        self.ax.plot([0, 1, 2], [0, 1, 0])
        self.ax.step([0, 1, 2], [1, 0, 1], where='pre')
        self.ax.line_from_file('wave.csv', 1, 2, drawstyle='steps-post')
        self.assertEqual(self.ax.lines[1]['smooth_mode'], 'none')
        gle = self.fig._generate_gle()
        step_cmd = [ln for ln in gle.splitlines() if 'fsteps' in ln]
        file_cmd = [ln for ln in gle.splitlines() if ' line steps ' in ln]
        self.assertEqual(len(step_cmd), 1)
        self.assertEqual(len(file_cmd), 1)
        self.assertNotIn('smooth', step_cmd[0])
        self.assertNotIn('smooth', file_cmd[0])
        self.assertIn(' line smooth ', gle)

    def test_line_mode_survives_to_dict(self):
        self.ax.step([0, 1, 2], [1, 2, 1], where='post')
        restored = glp.Figure.from_dict(self.fig.to_dict())
        self.assertEqual(restored.axes_list[0].lines[0]['line_mode'], 'steps')

    def test_module_and_figure_helpers(self):
        glp.close()
        fig = glp.figure()
        fig.step([0, 1], [1, 0], where='mid')
        glp.stem([0, 1], [1, 0])
        lines = fig.gca().lines
        self.assertEqual(
            [ln['line_mode'] for ln in lines], ['hist', 'impulses']
        )

    def test_marker_color_only_warns_that_stems_share_it(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.ax.stem([0, 1], [1, 2], markerfmt='gs')
        self.assertTrue(any(issubclass(w.category, UserWarning) for w in caught))
        self.assertEqual(self.ax.lines[0]['color'], 'GREEN')
        self.assertEqual(self.ax.lines[0]['marker'], 'FSQUARE')


class TestHistogram(unittest.TestCase):
    """Counts via ``let dK = hist``, drawn as a step or adjoining bars."""

    def setUp(self):
        glp.close()
        self.fig = glp.figure(data_prefix="hist")
        self.ax = self.fig.add_subplot(111)

    def tearDown(self):
        glp.close()

    def _script(self):
        return self.fig._generate_gle()

    def test_figure_wide_smoothing_does_not_round_the_bin_edges(self):
        self.fig.graph.smooth_curves = True
        self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="step")
        line = next(ln for ln in self._script().splitlines() if "line hist" in ln)
        self.assertNotIn("smooth", line)

    def test_step_emits_a_let_and_a_hist_line(self):
        self.ax.hist(
            [0, 0.2, 0.5, 0.9], bins=20, range=(0, 1), histtype="step", label="n"
        )
        script = self._script()
        self.assertIn("let d2 = hist d1 from 0 to 1 bins 20", script)
        self.assertIn("d2 line hist color BLUE", script)
        self.assertIn('key "n"', script)
        self.assertNotIn("bar d2", script)
        self.assertEqual(len(self.ax.hists), 1)
        self.assertEqual(self.ax.hists[0]["histtype"], "step")

    def test_stepfilled_is_a_full_width_bar_on_the_binned_dataset(self):
        self.ax.hist(
            [0, 0.2, 0.5, 0.9],
            bins=20,
            range=(0, 1),
            histtype="stepfilled",
            color="red",
            label="n",
        )
        script = self._script()
        self.assertIn("let d2 = hist d1 from 0 to 1 bins 20", script)
        self.assertIn("bar d2 fill RED color RED width 0.05", script)
        self.assertIn('d2 key "n"', script)
        self.assertNotIn("line hist", script)

    def test_bar_histtype_warns_and_draws_a_step(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="bar")
        self.assertTrue(any("step outline" in str(w.message) for w in caught))
        self.assertIn("line hist", self._script())
        self.assertNotIn("bar d", self._script())

    def test_density_align_and_orientation_warn(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.hist(
                [0, 1],
                bins=4,
                range=(0, 1),
                histtype="step",
                density=True,
                align="left",
                orientation="horizontal",
            )
        messages = " ".join(str(w.message) for w in caught)
        self.assertIn("density", messages)
        self.assertIn("align", messages)
        self.assertIn("horizontal", messages)
        self.assertIn("line hist", self._script())

    def test_range_and_bin_rules(self):
        import warnings

        returned = self.ax.hist([0.2, 0.8], bins=4, histtype="step")
        self.assertIs(returned, self.ax)
        self.assertIn("let d2 = hist d1 from 0.2 to 0.8 bins 4", self._script())

        self.ax.hist([3, 3, 3], bins=2, histtype="step")
        self.assertIn("from 2.5 to 3.5 bins 2", self._script())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.hist([0, 1], bins=[0, 1, 3], histtype="step")
            self.ax.hist([0, 1], bins="auto", range=(0, 1), histtype="step")
        messages = " ".join(str(w.message) for w in caught)
        self.assertIn("equal width", messages)
        self.assertIn("auto", messages)
        script = self._script()
        self.assertIn("from 0 to 3 bins 2", script)
        self.assertIn("bins 10", script)

        self.ax.hist(
            [0, 1], bins=2, range=(0, 1), histtype="step", color="red", alpha=0.5
        )
        self.assertIn("rgba255", self._script())

    def test_a_step_clause_round_trips_without_inventing_bins(self):
        import tempfile
        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.hist([0, 0.5, 1], bins=4, range=(0, 1), histtype="step")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "figure.gle"
            self.fig.savefig_gle(str(src))
            text = src.read_text(encoding="utf-8").replace("bins 4", "step 0.25", 1)
            src.write_text(text, encoding="utf-8")
            ax = parse_gle_figure(src).figure.axes_list[0]
            self.assertNotIn("bins", ax.hists[0])
            self.assertEqual(ax.hists[0]["bin_step"], 0.25)
            dst = Path(tmp) / "again.gle"
            ax.figure.savefig_gle(str(dst))
            self.assertEqual(dst.read_text(encoding="utf-8"), text)

    def test_empty_inverted_range_and_bad_histtype_raise(self):
        with self.assertRaises(ValueError):
            self.ax.hist([], bins=4, range=(0, 1), histtype="step")
        with self.assertRaises(ValueError):
            self.ax.hist([0, 1], bins=4, range=(1, 0), histtype="step")
        with self.assertRaises(ValueError):
            self.ax.hist([0, 1], bins=4, histtype="nope")

    def test_counts_and_axis_limits_follow_gle_binning(self):
        from gleplot.axes import histogram_counts

        samples = [0, 0, 1, 1, 1]
        counts = histogram_counts(samples, 0, 2, bins=2)
        self.assertTrue(np.array_equal(counts, [2, 3]))
        right = histogram_counts([2], 0, 2, bins=2)
        self.assertTrue(np.array_equal(right, [0, 1]))
        outside = histogram_counts([-1, 3], 0, 2, bins=2)
        self.assertTrue(np.array_equal(outside, [0, 0]))
        # ``step`` that lands on the window end does not add a further edge.
        # One that does not divides past ``to``; the sample still in range
        # falls in that last, wider bin.
        on_end = histogram_counts([0, 0.5, 1], 0, 1, bin_step=0.5)
        self.assertTrue(np.array_equal(on_end, [1, 2]))
        overshoot = histogram_counts([0.9], 0, 1, bin_step=0.4)
        self.assertTrue(np.array_equal(overshoot, [0, 0, 1]))

        self.ax.hist(samples, bins=2, range=(0, 2), histtype="step")
        script = self._script()
        self.assertIn("xaxis min 0 max 2", script)
        self.assertIn("yaxis min 0 max 3", script)

    def test_step_and_stepfilled_round_trip(self):
        import tempfile

        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.hist(
            [0, 0, 1, 1, 1], bins=2, range=(0, 2), histtype="step", label="step"
        )
        self.ax.hist(
            [0.5, 1.5],
            bins=2,
            range=(0, 2),
            histtype="stepfilled",
            color="red",
            label="filled",
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "figure.gle"
            self.fig.savefig_gle(str(src))
            original = src.read_text(encoding="utf-8")
            recognized = parse_gle_figure(src)
            ax = recognized.figure.axes_list[0]
            self.assertEqual(len(ax.hists), 2)
            self.assertEqual(ax.lines, [])
            self.assertEqual(ax.bars, [])
            self.assertTrue(np.allclose(ax.hists[0]["samples"], [0, 0, 1, 1, 1]))
            self.assertEqual(ax.hists[0]["histtype"], "step")
            self.assertEqual(ax.hists[1]["histtype"], "stepfilled")
            self.assertEqual(ax.hists[1]["label"], "filled")
            dst = Path(tmp) / "again.gle"
            recognized.figure.savefig_gle(str(dst))
            self.assertEqual(dst.read_text(encoding="utf-8"), original)

    def test_a_line_hist_of_ordinary_points_stays_a_line(self):
        import tempfile

        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.plot([0, 1, 2], [1, 2, 1], drawstyle="steps-mid")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "figure.gle"
            self.fig.savefig_gle(str(src))
            ax = parse_gle_figure(src).figure.axes_list[0]
        self.assertEqual(len(ax.lines), 1)
        self.assertEqual(ax.lines[0].get("line_mode"), "hist")
        self.assertEqual(ax.hists, [])

    def test_a_hist_let_without_the_hist_mode_stays_raw(self):
        import tempfile

        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="step")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "figure.gle"
            self.fig.savefig_gle(str(src))
            text = src.read_text(encoding="utf-8").replace(" line hist", " line")
            src.write_text(text, encoding="utf-8")
            ax = parse_gle_figure(src).figure.axes_list[0]
        self.assertEqual(ax.hists, [])
        raw = "\n".join(ax.passthrough)
        self.assertIn("let d2 = hist d1", raw)
        self.assertIn("d2 line", raw)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for plotting functionality."""

import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Check if IPython is available for conditional testing
try:
    import IPython  # noqa: F401

    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


import gleplot as glp


class TestBasicPlotting:
    """Test basic line plotting functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_simple_line_plot(self):
        """Test basic line plotting."""
        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]

        self.ax.plot(x, y)

        assert len(self.ax.lines) == 1
        assert self.ax.has_plots()

    def test_line_with_color(self):
        """Test line with color specification."""
        self.ax.plot([1, 2, 3], [1, 2, 3], color="red")

        assert len(self.ax.lines) == 1
        assert self.ax.lines[0]["color"] == "RED"

    def test_line_with_style(self):
        """Test line with different styles."""
        self.ax.plot([1, 2, 3], [1, 2, 3], linestyle="--")

        assert self.ax.lines[0]["linestyle"] == "--"

    def test_line_with_label(self):
        """Test line with legend label."""
        label = "test line"
        self.ax.plot([1, 2, 3], [1, 2, 3], label=label)

        assert self.ax.lines[0]["label"] == label

    def test_multiple_lines(self):
        """Test multiple line plots on same axes."""
        self.ax.plot([1, 2, 3], [1, 2, 3], label="line 1")
        self.ax.plot([1, 2, 3], [3, 2, 1], label="line 2")

        assert len(self.ax.lines) == 2

    def test_line_with_data_name(self):
        """Test semantic data file naming for line plots."""
        self.ax.plot([1, 2, 3], [3, 2, 1], data_name="Observed Signal")
        assert self.ax.lines[0]["data_file"] == "observed_signal.dat"

    def test_line_with_marker_stays_a_line(self):
        """plot() with a marker AND a solid line keeps it a line series.

        Regression: previously a marker requested alongside the default solid
        linestyle was silently dropped (the line branch forced marker=None).
        """
        self.ax.plot([1, 2, 3], [1, 2, 3], marker="o")

        assert len(self.ax.lines) == 1
        assert len(self.ax.scatters) == 0
        assert self.ax.lines[0]["marker"] == "FCIRCLE"

    def test_line_without_marker_stores_none(self):
        """A plain line still stores marker=None (schema unchanged)."""
        self.ax.plot([1, 2, 3], [1, 2, 3])
        assert "marker" in self.ax.lines[0]
        assert self.ax.lines[0]["marker"] is None

    def test_line_with_marker_emits_line_and_marker_gle(self):
        """Generated GLE for a line+marker series contains both tokens."""
        self.ax.plot([1, 2, 3], [1, 2, 3], marker="o", label="pts")
        gle = self.fig._generate_gle()
        # The dataset draw command must carry a line AND a marker directive.
        draw_lines = [ln for ln in gle.splitlines() if " line" in ln and "marker" in ln]
        assert (
            draw_lines
        ), f"Expected a draw command with both 'line' and 'marker'.\n{gle}"


class TestScatterPlots:
    """Test scatter plot functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_simple_scatter(self):
        """Test basic scatter plot."""
        self.ax.scatter([1, 2, 3], [1, 2, 3])

        assert len(self.ax.scatters) == 1

    def test_scatter_with_color(self):
        """Test scatter with color."""
        self.ax.scatter([1, 2, 3], [1, 2, 3], color="blue")

        assert self.ax.scatters[0]["color"] == "BLUE"

    def test_scatter_with_marker(self):
        """Test scatter with different marker."""
        self.ax.scatter([1, 2, 3], [1, 2, 3], marker="s")

        # scatter() should use marker 's' (square)
        assert self.ax.scatters[0]["marker"] == "FSQUARE"

    def test_plot_as_scatter(self):
        """Test plot() with marker creates scatter."""
        self.ax.plot([1, 2, 3], [1, 2, 3], marker="o", linestyle="none")

        # Should be in scatters list, not lines
        assert len(self.ax.scatters) == 1
        assert len(self.ax.lines) == 0


class TestBarCharts:
    """Test bar chart functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_simple_bar(self):
        """Test basic bar chart."""
        self.ax.bar([1, 2, 3], [10, 20, 30])

        assert len(self.ax.bars) == 1

    def test_bar_with_color(self):
        """Test bar with single color."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color="red")

        assert len(self.ax.bars[0]["colors"]) == 3
        assert self.ax.bars[0]["colors"][0] == "RED"

    def test_bar_with_multiple_colors(self):
        """A colour sequence is one series per bar, each with a real width."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color=["red", "green", "blue"])

        assert len(self.ax.bars) == 3
        assert [bar["colors"][0] for bar in self.ax.bars] == ["RED", "GREEN", "BLUE"]
        assert [bar["width"] for bar in self.ax.bars] == [0.5, 0.5, 0.5]
        text = self.fig._generate_gle()
        assert text.count("bar d") == 3
        assert "fill RED" in text
        assert "fill GREEN" in text
        assert "fill BLUE" in text
        assert "width 0.5" in text

    def test_bar_uniform_color_list_stays_one_series(self):
        """The same colour repeated is still the historical one-dataset bar."""
        self.ax.bar([1, 2, 3], [10, 20, 30], color=["red", "red", "red"])
        assert len(self.ax.bars) == 1
        assert self.ax.bars[0]["colors"] == ["RED", "RED", "RED"]
        assert "width" not in self.ax.bars[0]

    def test_bar_edge_and_stack_and_barh(self):
        """Stroke, baseline, and horizontal bars reach the script."""
        self.ax.bar(
            [1, 2], [3, 4], color="red", edgecolor="k", linewidth=2, linestyle="--"
        )
        self.ax.bar([1, 2], [1, 1], bottom=[3, 4], color="white")
        self.ax.barh([1, 2], [3, 4])
        text = self.fig._generate_gle()
        assert "color BLACK" in text
        assert "lstyle" in text
        assert "lwidth" in text
        assert "from" in text
        assert "horiz" in text
        stacked = self.ax.bars[1]
        assert (stacked["bottom"] == [3, 4]).all()
        assert "bottom" not in self.ax.bars[0]

    def test_bar_zero_baseline_is_not_stored(self):
        self.ax.bar([1, 2], [3, 4], bottom=0)
        assert "bottom" not in self.ax.bars[0]
        assert "from" not in self.fig._generate_gle()

    def test_bar_align_edge_and_hatch_warn(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.bar([1, 2], [3, 4], align="edge", hatch="//")
        messages = " ".join(str(item.message) for item in caught)
        assert "centered" in messages
        assert "hatch" in messages

    def test_bar_color_length_must_match(self):
        with pytest.raises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], color=["red", "blue"])

    def test_bar_with_data_name(self):
        """Test semantic data file naming for bar plots."""
        self.ax.bar([1, 2, 3], [10, 20, 30], data_name="Bar Data #1")
        assert self.ax.bars[0]["data_file"] == "bar_data_1.dat"

    def test_bar_yerr_sits_on_the_tip(self):
        """Symmetric and asymmetric y errors are whiskers at bottom+height."""
        self.ax.bar([1, 2, 3], [4, 5, 6], yerr=0.5, capsize=3, label="h")
        assert len(self.ax.bars) == 1
        assert len(self.ax.errorbars) == 1
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb["x"], [1, 2, 3])
        np.testing.assert_array_equal(eb["y"], [4, 5, 6])
        np.testing.assert_array_equal(eb["yerr_up"], [0.5, 0.5, 0.5])
        np.testing.assert_array_equal(eb["yerr_down"], [0.5, 0.5, 0.5])
        assert eb["xerr_left"] is None
        assert eb["label"] is None
        assert eb["linestyle"] == "none"
        assert eb["marker"] is None
        assert eb["color"] == "BLACK"
        assert eb["capsize"] == 3
        text = self.fig._generate_gle()
        assert "err " in text
        assert "errwidth" in text
        assert "herr" not in text
        assert text.count('key "h"') == 1
        assert self.ax.ymax == 6.5

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
        np.testing.assert_array_equal(eb["y"], [5, 7])
        np.testing.assert_array_equal(eb["yerr_down"], [0.1, 0.2])
        np.testing.assert_array_equal(eb["yerr_up"], [0.3, 0.4])
        assert "errup" in fig._generate_gle()
        assert "errdown" in fig._generate_gle()

    def test_barh_xerr_sits_on_the_tip(self):
        """Horizontal length errors run from left+width, and widen x."""
        self.ax.barh([1, 2], [4, 5], left=1, xerr=0.5, yerr=0.25, capsize=4)
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb["x"], [5, 6])
        np.testing.assert_array_equal(eb["y"], [1, 2])
        np.testing.assert_array_equal(eb["xerr_left"], [0.5, 0.5])
        np.testing.assert_array_equal(eb["yerr_up"], [0.25, 0.25])
        text = self.fig._generate_gle()
        assert "horiz" in text
        assert "herr " in text
        assert "err " in text
        assert self.ax.xmax == 6.5
        assert self.ax.ymax == 2.25

    def test_bar_error_shapes_and_colors(self):
        """(2, n) is asymmetric; a colour sequence is one whisker series each."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.bar(
                [1, 2],
                [3, 4],
                yerr=np.array([[0.1, 0.2], [0.3, 0.4]]),
                ecolor=["red", "blue"],
                error_kw={"capsize": 2, "elinewidth": 1.5},
            )
        messages = " ".join(str(item.message) for item in caught)
        assert "elinewidth" in messages
        assert len(self.ax.errorbars) == 2
        assert [eb["color"] for eb in self.ax.errorbars] == ["RED", "BLUE"]
        np.testing.assert_array_equal(self.ax.errorbars[0]["yerr_down"], [0.1])
        np.testing.assert_array_equal(self.ax.errorbars[1]["yerr_up"], [0.4])
        assert self.ax.errorbars[0]["capsize"] == 2

        before = len(self.ax.bars)
        with pytest.raises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], yerr=[0.1, 0.2])
        assert len(self.ax.bars) == before
        with pytest.raises(ValueError):
            self.ax.bar([1, 2, 3], [4, 5, 6], yerr=float("nan"))
        with pytest.raises(ValueError):
            self.ax.bar([1, 2], [3, 4], xerr=[0.1, float("nan")])
        with pytest.raises(TypeError):
            self.ax.bar([1, 2], [3, 4], yerr=0.1, error_kw="nope")

        glp.close()
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.bar([1, 2, 3], [4, 5, 6], yerr=[[0.2], [0.5]], capsize_cm=0.1)
        eb = ax.errorbars[0]
        np.testing.assert_array_equal(eb["yerr_down"], [0.2, 0.2, 0.2])
        np.testing.assert_array_equal(eb["yerr_up"], [0.5, 0.5, 0.5])
        assert eb["gle_capsize"] == 0.1
        assert len(ax.errorbars) == 1
        ax.bar([10, 20, 30], [1, 1, 1], yerr=[0.4], xerr=0.2)
        whisker = ax.errorbars[1]
        np.testing.assert_array_equal(whisker["x"], [10, 20, 30])
        np.testing.assert_array_equal(whisker["y"], [1, 1, 1])
        np.testing.assert_array_equal(whisker["yerr_up"], [0.4, 0.4, 0.4])
        np.testing.assert_array_equal(whisker["xerr_right"], [0.2, 0.2, 0.2])

    def test_bar_error_kw_capsize_and_zorder(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.bar(
                [1, 2],
                [3, 4],
                yerr=0.2,
                capsize=5,
                zorder=4,
                ecolor="green",
                error_kw={"ecolor": "red", "zorder": 8, "capsize": 1},
            )
        messages = " ".join(str(item.message) for item in caught)
        assert "error_kw" not in messages
        eb = self.ax.errorbars[0]
        assert eb["color"] == "RED"
        assert eb["capsize"] == 1
        assert eb["zorder"] == 8.01
        assert self.ax.bars[0]["zorder"] == 4

    def test_bar_without_errors_adds_no_whisker(self):
        self.ax.bar([1, 2, 3], [4, 5, 6], capsize=3, ecolor="red")
        assert self.ax.errorbars == []
        assert "err " not in self.fig._generate_gle()


class TestFillBetween:
    """Test fill_between functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_simple_fill(self):
        """Test basic fill_between."""
        x = [1, 2, 3]
        y1 = [1, 2, 3]
        y2 = [2, 4, 6]

        self.ax.fill_between(x, y1, y2)

        assert len(self.ax.fills) == 1

    def test_fill_with_color(self):
        """Test fill_between with color."""
        self.ax.fill_between([1, 2, 3], [1, 2, 3], [2, 4, 6], color="lightblue")

        assert self.ax.fills[0]["color"] == "LIGHTBLUE"

    def test_fill_with_data_name(self):
        """Test semantic data file naming for generated fill data."""
        self.ax.fill_between(
            [1, 2, 3], [1, 2, 3], [2, 4, 6], data_name="Component Lambda 2D Fill"
        )
        assert self.ax.fills[0]["data_file"] == "component_lambda_2d_fill.dat"

    def test_data_name_collision_is_disambiguated(self):
        """Test that duplicate custom names are made unique automatically."""
        self.ax.plot([1, 2], [1, 2], data_name="model-range")
        self.ax.plot([1, 2], [2, 3], data_name="model-range")

        assert self.ax.lines[0]["data_file"] == "model-range.dat"
        assert self.ax.lines[1]["data_file"] == "model-range_1.dat"

    def _script(self):
        return self.fig._generate_gle()

    def test_default_y2_is_a_constant_zero_curve(self):
        """Omitting y2 fills to 0, matplotlib's default, as a second dataset."""
        self.ax.fill_between([0, 1, 2], [1, -1, 1])
        series = self.ax.fills[0]
        assert series.get("target") is None
        assert list(series["y2"]) == [0.0, 0.0, 0.0]
        script = self._script()
        assert "fill d1,d2 color LIGHTBLUE" in script
        assert "fill x1" not in script

    def test_baseline_emits_an_axis_fill(self):
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x1", label="down")
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x2", ymin=3)
        script = self._script()
        assert "fill x1,d1 color LIGHTBLUE" in script
        assert 'd1 keyfill LIGHTBLUE key "down"' in script
        assert "fill d2,x2 color LIGHTBLUE ymin 3" in script
        assert self.ax.fills[0]["y2"] is None
        assert self.ax.fills[1]["target"] == "x2"
        assert self.ax.fills[1]["ymin"] == 3.0

    def test_issue_example_fills_to_zero_where_x_is_positive(self):
        """``fill_between(x, y, where=(x > 0))`` is a constant zero curve, clipped."""
        x = [-1.0, 0.0, 1.0, 2.0]
        self.ax.fill_between(x, [1.0, 1.0, 1.0, 1.0], where=[v > 0 for v in x])
        assert len(self.ax.fills) == 1
        assert list(self.ax.fills[0]["y2"]) == [0.0, 0.0, 0.0, 0.0]
        assert self.ax.fills[0]["xmin"] == 1.0
        assert "fill d1,d2 color LIGHTBLUE xmin 1" in self._script()

    def test_where_on_a_decreasing_x_uses_data_edges(self):
        self.ax.fill_between(
            [4, 3, 2, 1],
            [1, 1, 1, 1],
            [0, 0, 0, 0],
            where=[False, True, True, False],
        )
        assert self.ax.fills[0].get("xmin") == 2.0
        assert self.ax.fills[0].get("xmax") == 3.0

    def test_where_clips_each_true_run(self):
        x = [0, 1, 2, 3, 4]
        self.ax.fill_between(
            x,
            [1, 1, 1, 1, 1],
            [0, 0, 0, 0, 0],
            where=[True, True, False, True, True],
            label="band",
        )
        assert len(self.ax.fills) == 2
        assert self.ax.fills[0].get("xmax") == 1.0
        assert "xmin" not in self.ax.fills[0]
        assert self.ax.fills[1].get("xmin") == 3.0
        assert self.ax.fills[0]["label"] == "band"
        assert self.ax.fills[1]["label"] is None
        script = self._script()
        assert "fill d1,d2 color LIGHTBLUE xmax 1" in script
        assert "fill d3,d4 color LIGHTBLUE xmin 3" in script

    def test_isolated_true_draws_nothing(self):
        self.ax.fill_between([0, 1, 2], [1, 1, 1], where=[False, True, False])
        assert self.ax.fills == []
        assert "fill " not in self._script()

    def test_interpolate_moves_the_clip_to_the_crossing(self):
        self.ax.fill_between(
            [0, 1, 2],
            [0, 0, 2],
            [1, 1, 0],
            where=[False, False, True],
            interpolate=True,
        )
        assert len(self.ax.fills) == 1
        assert self.ax.fills[0]["xmin"] == pytest.approx(4.0 / 3.0, abs=5e-8)
        assert "xmin 1.33333" in self._script()

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
        assert any("monotonic" in str(w.message) for w in caught)
        assert len(self.ax.fills) == 1
        assert "xmax" not in self.ax.fills[0]

    def test_polygon_and_axis_fill_round_trip_through_to_dict(self):
        self.ax.fill([0, 1, 0], [0, 1, 2], alpha=0.4)
        self.ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x1", ymin=0)
        restored = glp.Figure.from_dict(self.fig.to_dict())
        fills = restored.axes_list[0].fills
        assert fills[0]["target"] == "polygon"
        assert fills[0]["y2"] is None
        assert fills[1]["target"] == "x1"
        assert fills[1]["y2"] is None
        assert fills[1]["ymin"] == 0.0
        assert restored.to_dict() == self.fig.to_dict()

    def test_non_monotonic_where_warns_and_is_ignored(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between([0, 2, 1], [1, 1, 1], where=[True, False, True])
        assert any("monotonic" in str(w.message) for w in caught)
        assert len(self.ax.fills) == 1
        assert "xmin" not in self.ax.fills[0]
        assert "xmax" not in self.ax.fills[0]

    def test_where_and_explicit_x_clip_conflict(self):
        with pytest.raises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], where=[True, True], xmin=0)

    def test_baseline_rejects_a_second_curve(self):
        with pytest.raises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], [0, 0], baseline="x1")

    def test_polygon_fill_closes_one_dataset(self):
        returned = self.ax.fill([0, 1, 0], [0, 1, 2], alpha=0.4, label="tri")
        assert returned is self.ax
        series = self.ax.fills[0]
        assert series["target"] == "polygon"
        assert series["y2"] is None
        script = self._script()
        assert "fill d1 color rgba255(" in script
        assert "d1 keyfill rgba255(" in script
        assert 'key "tri"' in script
        assert "fill d1,d2" not in script

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
        assert "step" in messages
        assert "hatch" in messages
        assert "edgecolor" in messages
        assert "linewidth" in messages
        assert "linestyle" in messages

    def test_where_length_and_baseline_are_rejected(self):
        with pytest.raises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], where=[True])
        with pytest.raises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], baseline="y")
        with pytest.raises(ValueError):
            self.ax.fill_between([0, 1], [1, 1], [2, 3, 4])
        with pytest.raises(ValueError):
            self.ax.fill([[0, 1], [1, 0]], [0, 1])

    def test_full_mask_and_empty_mask(self):
        self.ax.fill_between([0, 1, 2], [1, 1, 1], where=[True, True, True])
        assert "xmin" not in self.ax.fills[0]
        self.ax.fill_between([0, 1], [1, 1], where=[False, False])
        assert len(self.ax.fills) == 1

    def test_non_finite_x_ignores_where(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.fill_between(
                [0, float("nan"), 2], [1, 1, 1], where=[True, False, True]
            )
        assert any("monotonic" in str(w.message) for w in caught)
        assert "xmin" not in self.ax.fills[0]

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
        assert any("interpolate" in str(w.message) for w in caught)
        assert self.ax.fills[0]["xmin"] == 1.0

    def test_interpolate_moves_the_right_edge_to_the_crossing(self):
        self.ax.fill_between(
            [0, 1, 2],
            [2, 0, 0],
            [0, 1, 1],
            where=[True, False, False],
            interpolate=True,
        )
        assert self.ax.fills[0]["xmax"] == pytest.approx(2.0 / 3.0, abs=5e-8)
        assert "xmin" not in self.ax.fills[0]

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
        assert any("extra polygons" in str(w.message) for w in caught)
        assert "rgb255(0,0,255)" in self.ax.fills[0]["color"]
        assert len(self.ax.fills) == 1


class TestDataPrefixValidation:
    """Test that a figure-level data_prefix is validated, not sanitized.

    Unlike ``data_name`` (a label, sanitized into a stem by the tests above),
    ``data_prefix`` is used verbatim to build sidecar filenames. A prefix GLE
    cannot parse must therefore fail in Python at the point it is supplied,
    rather than producing a script that aborts at compile time with
    ``>> Error: left hand side contains unquoted string``.
    """

    @pytest.fixture(autouse=True)
    def _teardown(self):
        yield
        glp.close()

    def test_plus_in_prefix_raises_instead_of_failing_at_compile_time(self):
        """The reported reproducer: 'mk+white' produced unparseable GLE."""
        with pytest.raises(ValueError) as ctx:
            glp.figure(data_prefix="mk+white")

        message = str(ctx.value)
        assert "mk+white" in message  # names the offending value
        assert "'+'" in message  # ...and the offending character

    def test_forbidden_characters_are_rejected(self):
        """Every character GLE cannot read in an unquoted data filename."""
        # '!', '"' and '+' were confirmed against GLE 4.3.10 by compiling a
        # data file containing each; '/' and '\\' are path separators.
        for prefix in ["a!b", 'a"b', "a+b", "a/b", "a\\b"]:
            with pytest.raises(ValueError):
                glp.figure(data_prefix=prefix)

    def test_whitespace_and_control_characters_are_rejected(self):
        for prefix in ["a b", "a\tb", "a\nb", "a\x00b", "a\x1fb"]:
            with pytest.raises(ValueError):
                glp.figure(data_prefix=prefix)

    def test_empty_prefix_is_rejected(self):
        for prefix in ["", "   "]:
            with pytest.raises(ValueError):
                glp.figure(data_prefix=prefix)

    def test_non_string_prefix_raises_type_error(self):
        with pytest.raises(TypeError):
            glp.figure(data_prefix=42)

    def test_none_prefix_keeps_default_naming(self):
        """None is not a bad value -- it selects the global data_N counter."""
        fig = glp.figure(data_prefix=None)
        assert fig.data_prefix is None

    def test_valid_prefix_is_preserved_verbatim(self):
        """Case and legal punctuation must survive: no sanitizing here.

        Sanitizing would lowercase, silently turning the documented
        ``data_prefix='experimentA'`` into ``experimenta_0.dat``.
        """
        for prefix in ["experimentA", "run42", "exp-1.2", "a#b", "a,b", "a=b"]:
            fig = glp.figure(data_prefix=prefix)
            assert fig.data_prefix == prefix

    def test_valid_prefix_drives_sidecar_filenames(self):
        fig = glp.figure(data_prefix="experimentA")
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3])
        ax.plot([1, 2, 3], [3, 2, 1])

        assert ax.lines[0]["data_file"] == "experimentA_0.dat"
        assert ax.lines[1]["data_file"] == "experimentA_1.dat"

    def test_subplots_validates_prefix_too(self):
        with pytest.raises(ValueError):
            glp.subplots(1, 2, data_prefix="mk+white")

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
        fig.data_prefix = "my file"

        restored = glp.Figure.from_dict(fig.to_dict())

        assert restored.data_prefix == "my file"


class TestErrorBars:
    """Test error bar functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_symmetric_yerr_scalar(self):
        """Test symmetric vertical error bars with scalar value."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, yerr=0.5, marker="o")

        assert len(self.ax.errorbars) == 1
        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb["yerr_up"], [0.5, 0.5, 0.5])
        np.testing.assert_array_equal(eb["yerr_down"], [0.5, 0.5, 0.5])

    def test_symmetric_yerr_array(self):
        """Test symmetric vertical error bars with array."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        yerr = [0.3, 0.5, 0.4]
        self.ax.errorbar(x, y, yerr=yerr, marker="o")

        eb = self.ax.errorbars[0]
        np.testing.assert_array_almost_equal(eb["yerr_up"], [0.3, 0.5, 0.4])
        np.testing.assert_array_almost_equal(eb["yerr_down"], [0.3, 0.5, 0.4])

    def test_asymmetric_yerr(self):
        """Test asymmetric vertical error bars."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        yerr = ([1, 2, 3], [3, 2, 1])
        self.ax.errorbar(x, y, yerr=yerr, marker="o")

        eb = self.ax.errorbars[0]
        np.testing.assert_array_almost_equal(eb["yerr_down"], [1, 2, 3])
        np.testing.assert_array_almost_equal(eb["yerr_up"], [3, 2, 1])

    def test_horizontal_error_bars(self):
        """Test horizontal error bars."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, xerr=0.2, marker="o")

        eb = self.ax.errorbars[0]
        np.testing.assert_array_equal(eb["xerr_left"], [0.2, 0.2, 0.2])
        np.testing.assert_array_equal(eb["xerr_right"], [0.2, 0.2, 0.2])

    def test_both_xerr_and_yerr(self):
        """Test vertical and horizontal error bars together."""
        x = [1, 2, 3]
        y = [10, 20, 30]
        self.ax.errorbar(x, y, yerr=0.5, xerr=0.3, marker="o")

        eb = self.ax.errorbars[0]
        assert eb["yerr_up"] is not None
        assert eb["xerr_left"] is not None

    def test_errorbar_with_capsize(self):
        """Test error bar cap width."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, capsize=0.2)

        eb = self.ax.errorbars[0]
        assert eb["capsize"] == 0.2

    def test_errorbar_with_label(self):
        """Test error bar with legend label."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, label="Data")

        eb = self.ax.errorbars[0]
        assert eb["label"] == "Data"

    def test_errorbar_with_color(self):
        """Test error bar with custom color."""
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5, color="red")

        eb = self.ax.errorbars[0]
        assert eb["color"] == "RED"

    def test_errorbar_has_plots(self):
        """Test that errorbar counts in has_plots()."""
        assert not self.ax.has_plots()
        self.ax.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5)
        assert self.ax.has_plots()

    def test_errorbar_gle_generation(self):
        """Test GLE script generation for error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, yerr=0.5, marker="o", color="blue", label="Test")

        gle = self.fig._generate_gle()
        assert "err d2" in gle
        assert "marker FCIRCLE" in gle
        assert 'key "Test"' in gle

    def test_errorbar_asymmetric_gle(self):
        """Test GLE generation for asymmetric error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(
            x, y, yerr=([1, 2, 3], [3, 2, 1]), marker="s", fmt="none", color="red"
        )

        gle = self.fig._generate_gle()
        assert "errup" in gle
        assert "errdown" in gle

    def test_errorbar_horizontal_gle(self):
        """Test GLE generation for horizontal error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, xerr=0.3, marker="o", fmt="none")

        gle = self.fig._generate_gle()
        assert "herr" in gle
        assert self.ax.xmin == pytest.approx(0.7, abs=5e-8)
        assert self.ax.xmax == pytest.approx(3.3, abs=5e-8)

    def test_figure_errorbar_method(self):
        """Test Figure-level errorbar convenience method."""
        self.fig.errorbar([1, 2, 3], [10, 20, 30], yerr=0.5)

        ax = self.fig.gca()
        assert len(ax.errorbars) == 1


class TestErrorbarFromFile:
    """Test errorbar_from_file functionality for direct column references."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path):
        """Create fresh figure and test data file for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)

        # Create a temporary data file
        self.data_path = tmp_path / "data.dat"
        self.data_path.write_text(
            "! Test data file\n"
            "! x  y  yerr\n"
            "1.0  10.0  0.5\n"
            "2.0  20.0  0.8\n"
            "3.0  30.0  0.6\n"
            "4.0  40.0  0.7\n"
        )
        yield
        glp.close()

    def test_errorbar_from_file_basic(self):
        """Test basic errorbar_from_file with column references."""
        self.ax.errorbar_from_file(
            str(self.data_path), x_col=1, y_col=2, yerr_col=3, marker="o", color="blue"
        )

        assert len(self.ax.file_series) == 1
        series = self.ax.file_series[0]
        assert series["data_file"] == str(self.data_path)
        assert series["x_col"] == 1
        assert series["y_col"] == 2
        assert series["yerr_col"] == 3
        assert series["marker"] == "FCIRCLE"  # 'o' -> 'FCIRCLE'
        assert series["color"] == "BLUE"

    def test_errorbar_from_file_without_errors(self):
        """Test errorbar_from_file without error column."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=None,
            marker="s",
            color="red",
        )

        series = self.ax.file_series[0]
        assert series["yerr_col"] is None

    def test_errorbar_from_file_with_label(self):
        """Test errorbar_from_file with legend label."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            label="Test Data",
            marker="o",
        )

        series = self.ax.file_series[0]
        assert series["label"] == "Test Data"

    def test_errorbar_from_file_y2axis(self):
        """Test errorbar_from_file on secondary y-axis."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            yaxis="y2",
            marker="o",
            color="green",
        )

        series = self.ax.file_series[0]
        assert series["yaxis"] == "y2"

    def test_errorbar_from_file_with_capsize(self):
        """Test errorbar_from_file with capsize parameter."""
        self.ax.errorbar_from_file(
            str(self.data_path), x_col=1, y_col=2, yerr_col=3, capsize=4, marker="o"
        )

        series = self.ax.file_series[0]
        # Capsize is converted: capsize * 0.0353
        assert series["capsize"] == pytest.approx(0.1412, abs=5e-5)

    def test_errorbar_from_file_gle_generation(self):
        """Test GLE script generation for errorbar_from_file."""
        self.ax.errorbar_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            yerr_col=3,
            marker="o",
            color="blue",
            label="File Data",
        )

        gle = self.fig._generate_gle()
        # Check for data command with column references
        assert "data" in gle
        assert "d1=c1,c2" in gle  # x_col=1, y_col=2
        assert "d2=c1,c3" in gle  # yerr includes x_col
        assert 'key "File Data"' in gle

    def test_errorbar_from_file_has_plots(self):
        """Test that errorbar_from_file counts in has_plots()."""
        assert not self.ax.has_plots()
        self.ax.errorbar_from_file(str(self.data_path), x_col=1, y_col=2, yerr_col=3)
        assert self.ax.has_plots()


class TestLineFromFile:
    """Test line_from_file functionality for direct file-based line overlays."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path):
        """Create fresh figure and test data file for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)

        self.data_path = tmp_path / "data.fit"
        self.data_path.write_text(
            "! Model fit curve\n" "1.0  10.0\n" "2.0  12.0\n" "3.0  13.0\n"
        )
        yield
        glp.close()

    def test_line_from_file_basic(self):
        """Test basic line_from_file column references."""
        self.ax.line_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            color="red",
            linewidth=2,
            label="Fit",
        )

        assert len(self.ax.file_series) == 1
        series = self.ax.file_series[0]
        assert series["series_type"] == "line"
        assert series["data_file"] == str(self.data_path)
        assert series["x_col"] == 1
        assert series["y_col"] == 2
        assert series["color"] == "RED"
        assert series["linewidth"] == 2.0
        assert series["label"] == "Fit"

    def test_line_from_file_gle_generation(self):
        """Test GLE script generation for line_from_file."""
        self.ax.line_from_file(
            str(self.data_path),
            x_col=1,
            y_col=2,
            color="red",
            linestyle="-",
            linewidth=1,
            label="Fit line",
        )

        gle = self.fig._generate_gle()
        assert "data" in gle
        assert "d1=c1,c2" in gle
        assert "line color RED" in gle
        assert 'key "Fit line"' in gle


@pytest.mark.skipif(not IPYTHON_AVAILABLE, reason="IPython not installed")
class TestViewDisplay:
    """Test figure view behavior across environments."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.fig.add_subplot(111).plot([1, 2, 3], [1, 4, 9])
        yield
        glp.close()

    @patch("IPython.display.display")
    @patch("IPython.display.Image")
    @patch("IPython.get_ipython")
    @patch.object(glp.Figure, "savefig")
    def test_view_notebook_png_displays_once_and_returns_none(
        self,
        mock_savefig,
        mock_get_ipython,
        mock_image,
        mock_display,
    ):
        """Notebook PNG view should display once and not return a rich object."""
        mock_get_ipython.return_value = Mock(config={"IPKernelApp": True})
        image_obj = object()
        mock_image.return_value = image_obj

        result = self.fig.view(format="png")

        assert result is None
        mock_savefig.assert_called_once()
        mock_image.assert_called_once()
        mock_display.assert_called_once_with(image_obj)

    @patch("IPython.get_ipython")
    @patch.object(glp.Figure, "savefig")
    def test_view_non_notebook_returns_temp_path(self, mock_savefig, mock_get_ipython):
        """Non-notebook view should return temp file path."""
        mock_get_ipython.return_value = None

        result = self.fig.view(format="png")

        assert result is not None
        assert result.suffix == ".png"
        mock_savefig.assert_called_once()


@pytest.fixture
def viewable_figure(tmp_path, monkeypatch):
    """A figure whose ``view()`` needs no GLE and writes only under tmp_path."""
    glp.close()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2, 3], [1, 4, 9])
    fig.compiler = Mock()
    monkeypatch.setattr(glp.Figure, "savefig", Mock())
    yield fig
    glp.close()


def test_view_outside_notebook_returns_path_and_prints_nothing(
    viewable_figure, tmp_path, capsys
):
    result = viewable_figure.view()

    assert result.parent == tmp_path
    assert result.suffix == ".png"
    assert capsys.readouterr() == ("", "")


def test_view_pdf_in_notebook_warns_and_returns_path(viewable_figure, capsys):
    pytest.importorskip("IPython")
    with patch("IPython.get_ipython", return_value=Mock(config={"IPKernelApp": 1})):
        with pytest.warns(UserWarning, match="format='png'") as record:
            result = viewable_figure.view(format="pdf")

    assert result.suffix == ".pdf"
    assert record[0].filename == __file__
    assert capsys.readouterr() == ("", "")


def test_show_views_the_current_figure(viewable_figure, tmp_path, capsys):
    result = glp.show()

    assert result.parent == tmp_path
    assert result.suffix == ".png"
    glp.Figure.savefig.assert_called_once()
    assert capsys.readouterr() == ("", "")


class TestLineModes:
    """Step, stem and histogram outlines are GLE line modes."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="modes")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _draw(self):
        return [
            ln.strip() for ln in self.fig._generate_gle().splitlines() if " line" in ln
        ]

    def test_plain_plot_stays_a_plain_line(self):
        self.ax.plot([0, 1, 2], [1, 2, 1])
        assert "line_mode" not in self.ax.lines[0]
        draw = " ".join(self._draw())
        for mode in ("steps", "fsteps", "hist", "impulses", "bar"):
            assert " line %s" % mode not in draw

    def test_step_where_selects_the_gle_mode(self):
        cases = (("pre", "fsteps"), ("post", "steps"), ("mid", "hist"))
        for where, mode in cases:
            glp.close()
            fig = glp.figure(data_prefix="modes")
            ax = fig.add_subplot(111)
            ax.step([0, 1, 2], [1, 0, 1], where=where, color="black")
            assert ax.lines[0]["line_mode"] == mode
            assert " line %s " % mode in fig._generate_gle()

    def test_drawstyle_names_and_the_steps_alias(self):
        self.ax.plot([0, 1], [1, 2], drawstyle="steps")
        self.ax.plot([0, 1], [2, 1], ds="steps-post")
        self.ax.plot([0, 1], [0, 1], drawstyle="default")
        assert self.ax.lines[0]["line_mode"] == "fsteps"
        assert self.ax.lines[1]["line_mode"] == "steps"
        assert "line_mode" not in self.ax.lines[2]

    def test_unknown_where_or_drawstyle_raises(self):
        with pytest.raises(ValueError):
            self.ax.step([0, 1], [0, 1], where="side")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-left")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], line_mode="spline")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-pre", ds="steps-post")
        with pytest.raises(ValueError):
            self.ax.stem([0, 1], orientation="sideways")
        with pytest.raises(TypeError):
            self.ax.stem()
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], bottom="low")

    def test_drawstyle_and_line_mode_must_agree(self):
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-post", line_mode="hist")

    def test_step_format_string_warns_and_is_not_applied(self):
        with pytest.warns(UserWarning):
            self.ax.step([0, 1], [0, 1], "r--")
        assert self.ax.lines[0]["line_mode"] == "fsteps"
        assert self.ax.lines[0]["color"] == "BLUE"

    def test_line_mode_with_no_line_warns_and_is_dropped(self):
        with pytest.warns(UserWarning):
            self.ax.plot(
                [0, 1],
                [0, 1],
                drawstyle="steps-mid",
                linestyle="none",
                marker="o",
            )
        assert len(self.ax.scatters) == 1
        assert "line_mode" not in self.ax.scatters[0]

    def test_stem_emits_impulses_and_a_head_marker(self):
        returned = self.ax.stem([0, 1, 2], [1, 0, 1], label="spikes")
        assert returned is self.ax
        series = self.ax.lines[0]
        assert series["line_mode"] == "impulses"
        assert series["marker"] == "FCIRCLE"
        assert series["label"] == "spikes"
        gle = self.fig._generate_gle()
        assert " line impulses " in gle
        assert "marker FCIRCLE" in gle

    def test_stem_of_y_alone_uses_integer_x(self):
        self.ax.stem([4, 5, 6])
        np.testing.assert_array_equal(self.ax.lines[0]["x"], [0.0, 1.0, 2.0])

    def test_stem_linefmt_sets_color_and_linestyle(self):
        self.ax.stem([0, 1], [1, 2], linefmt="r--", markerfmt="none")
        series = self.ax.lines[0]
        assert series["color"] == "RED"
        assert series["linestyle"] == "--"
        assert series["marker"] is None
        assert series["line_mode"] == "impulses"

    def test_stem_gaps_warn(self):
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], bottom=1)
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], orientation="horizontal")
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], basefmt="C3-")
        assert len(self.ax.lines) == 3
        assert all(ln["line_mode"] == "impulses" for ln in self.ax.lines)

    def test_stem_none_line_draws_markers_only(self):
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], linefmt="none")
        assert len(self.ax.lines) == 0
        assert len(self.ax.scatters) == 1

    def test_line_from_file_drawstyle(self):
        self.ax.line_from_file("wave.csv", 1, 2, drawstyle="steps-mid")
        assert self.ax.file_series[0]["line_mode"] == "hist"
        assert " line hist " in self.fig._generate_gle()

    def test_line_from_file_drops_a_mode_when_the_line_is_off(self):
        with pytest.warns(UserWarning):
            self.ax.line_from_file(
                "wave.csv", 1, 2, linestyle="none", drawstyle="steps-mid"
            )
        assert "line_mode" not in self.ax.file_series[0]

    def test_a_line_mode_stays_unsmoothed_when_the_figure_smooths(self):
        self.fig.graph.smooth_curves = True
        self.ax.plot([0, 1, 2], [0, 1, 0])
        self.ax.step([0, 1, 2], [1, 0, 1], where="pre")
        self.ax.line_from_file("wave.csv", 1, 2, drawstyle="steps-post")
        assert self.ax.lines[1]["smooth_mode"] == "none"
        gle = self.fig._generate_gle()
        step_cmd = [ln for ln in gle.splitlines() if "fsteps" in ln]
        file_cmd = [ln for ln in gle.splitlines() if " line steps " in ln]
        assert len(step_cmd) == 1
        assert len(file_cmd) == 1
        assert "smooth" not in step_cmd[0]
        assert "smooth" not in file_cmd[0]
        assert " line smooth " in gle

    def test_line_mode_survives_to_dict(self):
        self.ax.step([0, 1, 2], [1, 2, 1], where="post")
        restored = glp.Figure.from_dict(self.fig.to_dict())
        assert restored.axes_list[0].lines[0]["line_mode"] == "steps"

    def test_module_and_figure_helpers(self):
        glp.close()
        fig = glp.figure()
        fig.step([0, 1], [1, 0], where="mid")
        glp.stem([0, 1], [1, 0])
        lines = fig.gca().lines
        assert [ln["line_mode"] for ln in lines] == ["hist", "impulses"]

    def test_marker_color_only_warns_that_stems_share_it(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.stem([0, 1], [1, 2], markerfmt="gs")
        assert any(issubclass(w.category, UserWarning) for w in caught)
        assert self.ax.lines[0]["color"] == "GREEN"
        assert self.ax.lines[0]["marker"] == "FSQUARE"


class TestHistogram:
    """Counts via ``let dK = hist``, drawn as a step or adjoining bars."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="hist")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _script(self):
        return self.fig._generate_gle()

    def test_figure_wide_smoothing_does_not_round_the_bin_edges(self):
        self.fig.graph.smooth_curves = True
        self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="step")
        line = next(ln for ln in self._script().splitlines() if "line hist" in ln)
        assert "smooth" not in line

    def test_step_emits_a_let_and_a_hist_line(self):
        self.ax.hist(
            [0, 0.2, 0.5, 0.9], bins=20, range=(0, 1), histtype="step", label="n"
        )
        script = self._script()
        assert "let d2 = hist d1 from 0 to 1 bins 20" in script
        assert "d2 line hist color BLUE" in script
        assert 'key "n"' in script
        assert "bar d2" not in script
        assert len(self.ax.hists) == 1
        assert self.ax.hists[0]["histtype"] == "step"

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
        assert "let d2 = hist d1 from 0 to 1 bins 20" in script
        assert "bar d2 fill RED color RED width 0.05" in script
        assert 'd2 key "n"' in script
        assert "line hist" not in script

    def test_bar_histtype_warns_and_draws_a_step(self):
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="bar")
        assert any("step outline" in str(w.message) for w in caught)
        assert "line hist" in self._script()
        assert "bar d" not in self._script()

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
        assert "density" in messages
        assert "align" in messages
        assert "horizontal" in messages
        assert "line hist" in self._script()

    def test_range_and_bin_rules(self):
        import warnings

        returned = self.ax.hist([0.2, 0.8], bins=4, histtype="step")
        assert returned is self.ax
        assert "let d2 = hist d1 from 0.2 to 0.8 bins 4" in self._script()

        self.ax.hist([3, 3, 3], bins=2, histtype="step")
        assert "from 2.5 to 3.5 bins 2" in self._script()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.ax.hist([0, 1], bins=[0, 1, 3], histtype="step")
            self.ax.hist([0, 1], bins="auto", range=(0, 1), histtype="step")
        messages = " ".join(str(w.message) for w in caught)
        assert "equal width" in messages
        assert "auto" in messages
        script = self._script()
        assert "from 0 to 3 bins 2" in script
        assert "bins 10" in script

        self.ax.hist(
            [0, 1], bins=2, range=(0, 1), histtype="step", color="red", alpha=0.5
        )
        assert "rgba255" in self._script()

    def test_a_step_clause_round_trips_without_inventing_bins(self, tmp_path):
        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.hist([0, 0.5, 1], bins=4, range=(0, 1), histtype="step")
        src = tmp_path / "figure.gle"
        self.fig.savefig_gle(str(src))
        text = src.read_text(encoding="utf-8").replace("bins 4", "step 0.25", 1)
        src.write_text(text, encoding="utf-8")
        ax = parse_gle_figure(src).figure.axes_list[0]
        assert "bins" not in ax.hists[0]
        assert ax.hists[0]["bin_step"] == 0.25
        dst = tmp_path / "again.gle"
        ax.figure.savefig_gle(str(dst))
        assert dst.read_text(encoding="utf-8") == text

    def test_empty_inverted_range_and_bad_histtype_raise(self):
        with pytest.raises(ValueError):
            self.ax.hist([], bins=4, range=(0, 1), histtype="step")
        with pytest.raises(ValueError):
            self.ax.hist([0, 1], bins=4, range=(1, 0), histtype="step")
        with pytest.raises(ValueError):
            self.ax.hist([0, 1], bins=4, histtype="nope")

    def test_counts_and_axis_limits_follow_gle_binning(self):
        from gleplot.axes import histogram_counts

        samples = [0, 0, 1, 1, 1]
        counts = histogram_counts(samples, 0, 2, bins=2)
        assert np.array_equal(counts, [2, 3])
        right = histogram_counts([2], 0, 2, bins=2)
        assert np.array_equal(right, [0, 1])
        outside = histogram_counts([-1, 3], 0, 2, bins=2)
        assert np.array_equal(outside, [0, 0])
        # ``step`` that lands on the window end does not add a further edge.
        # One that does not divides past ``to``; the sample still in range
        # falls in that last, wider bin.
        on_end = histogram_counts([0, 0.5, 1], 0, 1, bin_step=0.5)
        assert np.array_equal(on_end, [1, 2])
        overshoot = histogram_counts([0.9], 0, 1, bin_step=0.4)
        assert np.array_equal(overshoot, [0, 0, 1])

        self.ax.hist(samples, bins=2, range=(0, 2), histtype="step")
        script = self._script()
        assert "xaxis min 0 max 2" in script
        assert "yaxis min 0 max 3" in script

    def test_step_and_stepfilled_round_trip(self, tmp_path):
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
        src = tmp_path / "figure.gle"
        self.fig.savefig_gle(str(src))
        original = src.read_text(encoding="utf-8")
        recognized = parse_gle_figure(src)
        ax = recognized.figure.axes_list[0]
        assert len(ax.hists) == 2
        assert ax.lines == []
        assert ax.bars == []
        assert np.allclose(ax.hists[0]["samples"], [0, 0, 1, 1, 1])
        assert ax.hists[0]["histtype"] == "step"
        assert ax.hists[1]["histtype"] == "stepfilled"
        assert ax.hists[1]["label"] == "filled"
        dst = tmp_path / "again.gle"
        recognized.figure.savefig_gle(str(dst))
        assert dst.read_text(encoding="utf-8") == original

    def test_a_line_hist_of_ordinary_points_stays_a_line(self, tmp_path):
        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.plot([0, 1, 2], [1, 2, 1], drawstyle="steps-mid")
        src = tmp_path / "figure.gle"
        self.fig.savefig_gle(str(src))
        ax = parse_gle_figure(src).figure.axes_list[0]
        assert len(ax.lines) == 1
        assert ax.lines[0].get("line_mode") == "hist"
        assert ax.hists == []

    def test_a_hist_let_without_the_hist_mode_stays_raw(self, tmp_path):
        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.hist([0, 1], bins=4, range=(0, 1), histtype="step")
        src = tmp_path / "figure.gle"
        self.fig.savefig_gle(str(src))
        text = src.read_text(encoding="utf-8").replace(" line hist", " line")
        src.write_text(text, encoding="utf-8")
        ax = parse_gle_figure(src).figure.axes_list[0]
        assert ax.hists == []
        raw = "\n".join(ax.passthrough)
        assert "let d2 = hist d1" in raw
        assert "d2 line" in raw


def test_add_plot_line_keywords_reach_the_emitted_line():
    """The keyword form of ``GLEWriter.add_line`` maps every argument to its
    field; in gleplot only scatters still call it, so the line fields are
    pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_plot_line(
        [0, 1, 2],
        [1, 2, 3],
        "k.dat",
        color="RED",
        linestyle="--",
        linewidth=2,
        label="k",
        marker="FCIRCLE",
        markersize=0.2,
        nomiss=True,
        yaxis="y2",
        xaxis="x2",
        offset=1.5,
        column_names=["x", "k"],
        smooth_mode="smoothm",
        svg_smooth=2,
    )
    writer.add_plot_line([0, 1, 2], [1, 2, 3], "s.dat", line_mode="steps")
    assert writer.lines_gle == [
        "    data k.dat d1=c1,c2",
        "    let d2 = d1+1.5",
        "    d2 line svg_smooth 2 smoothm nomiss color RED lwidth 0.07056 lstyle 3"
        ' marker FCIRCLE msize 0.2 x2axis y2axis key "k"',
        "    data s.dat d3=c1,c2",
        "    d3 line steps color BLUE lwidth 0.05292",
    ]


def test_add_errorbar_keywords_reach_the_emitted_dataset():
    """The keyword form of ``GLEWriter.add_errorbar_series`` maps every
    argument to its field (``capsize`` to ``gle_capsize``); gleplot itself no
    longer calls it, so the mapping is pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_errorbar(
        [0, 1, 2],
        [1, 2, 3],
        "e.dat",
        color="RED",
        linestyle=":",
        linewidth=2,
        label="e",
        marker="FSQUARE",
        markersize=0.2,
        yerr_up=np.array([0.1, 0.2, 0.3]),
        yerr_down=np.array([0.3, 0.2, 0.1]),
        xerr_left=np.array([0.1, 0.1, 0.1]),
        xerr_right=np.array([0.1, 0.1, 0.1]),
        capsize=0.25,
        yaxis="y2",
        xaxis="x2",
        offset=2.0,
        column_names=["x", "e", "up", "down", "xe"],
    )
    assert writer.lines_gle == [
        "    data e.dat d1=c1,c2 d2=c1,c3 d3=c1,c4 d4=c1,c5",
        "    let d5 = d1+2",
        "    d5 marker FSQUARE msize 0.2 color RED line lwidth 0.07056 lstyle 2"
        " errup d2 errdown d3 errwidth 0.25 herr d4 herrwidth 0.25"
        ' x2axis y2axis key "e"',
    ]
    assert writer.data_files["e.dat"].splitlines()[0] == "x e up down xe"


def test_add_bar_chart_keywords_reach_the_emitted_bar():
    """The keyword form of ``GLEWriter.add_bar`` maps every argument to its
    field (``heights`` to ``height``); gleplot itself no longer calls it, so
    the mapping is pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_bar_chart(
        [1, 2],
        [5, 3],
        "a.dat",
        ["RED", "RED"],
        "a",
        column_names=["x", "a"],
        width=0.3,
        swatch_color="GREEN",
        edgecolor="BLACK",
        edge_list=["BLACK", "GRAY"],
        fill_list=["RED", "BLUE"],
        linestyle="--",
        linewidth=1.5,
        horiz=True,
        dist=0.4,
    )
    writer.add_bar_chart(
        [1, 2], [1, 1], "b.dat", ["WHITE"], None, bottom=[5, 3], top=[6, 4], lstyle="9"
    )
    assert writer.lines_gle == [
        "    data a.dat d1=c1,c2",
        "    bar d1 fill RED,BLUE color BLACK,GRAY lstyle 3 lwidth 0.05292"
        " width 0.3 dist 0.4 horiz",
        '    d1 keyfill GREEN key "a"',
        "    data b.dat d2=c1,c2 d3=c1,c3",
        "    bar d3 from d2 fill WHITE lstyle 9",
    ]
    assert writer.data_files == {"a.dat": "x a\n1 5\n2 3\n", "b.dat": "1 5 6\n2 3 4\n"}


def test_add_fill_between_keywords_reach_the_emitted_fill():
    """The keyword form of ``GLEWriter.add_fill`` maps every argument to its
    field; gleplot itself no longer calls it, so the mapping is pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_fill_between(
        [0, 1],
        [2, 3],
        [1, 1],
        "a.dat",
        color="GREEN",
        alpha=1.0,
        offset=0.5,
        column_names=["x", "u", "l"],
        label="a",
        swatch_color="BLACK",
        xmin=0.2,
        xmax=0.8,
    )
    writer.add_fill_between(
        [0, 1],
        [1, 2],
        None,
        "b.dat",
        color="ORANGE",
        alpha=0.5,
        target="x1",
        ymin=0.5,
        ymax=2.5,
    )
    assert writer.lines_gle == [
        "    data a.dat d1=c1,c2 d2=c1,c3",
        "    let d3 = d1+0.5",
        "    let d4 = d2+0.5",
        "    fill d3,d4 color GREEN xmin 0.2 xmax 0.8",
        '    d3 keyfill BLACK key "a"',
        '    d4 key ""',
        "    data b.dat d5=c1,c2",
        "    fill x1,d5 color rgba255(255,165,0,128) ymin 0.5 ymax 2.5",
    ]
    assert writer.data_files == {
        "a.dat": "x u l\n0 2 1\n1 3 1\n",
        "b.dat": "0 1\n1 2\n",
    }


def test_add_histogram_keywords_reach_the_emitted_histogram():
    """The keyword form of ``GLEWriter.add_hist`` maps every argument to its
    field; gleplot itself no longer calls it, so the mapping is pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_histogram(
        [0.1, 0.6],
        "a.dat",
        histtype="step",
        color="GREEN",
        linestyle=":",
        linewidth=2,
        label="a",
        yaxis="y2",
        xaxis="x2",
        hist_from=0,
        hist_to=1,
        bins=2,
    )
    writer.add_histogram(
        [0.1, 0.6],
        "b.dat",
        histtype="stepfilled",
        color="RED",
        label="b",
        hist_from=0,
        hist_to=1,
        bin_step=0.5,
        edgecolor="BLACK",
        bar_width=0.5,
    )
    assert writer.lines_gle == [
        "    data a.dat d1=c1,c2",
        "    let d2 = hist d1 from 0 to 1 bins 2",
        '    d2 line hist color GREEN lwidth 0.07056 lstyle 2 x2axis y2axis key "a"',
        "    data b.dat d3=c1,c2",
        "    let d4 = hist d3 from 0 to 1 step 0.5",
        "    bar d4 fill RED color BLACK width 0.5",
        '    d4 key "b"',
    ]


def test_from_file_keywords_reach_the_emitted_references():
    """The keyword forms of ``GLEWriter.add_file_series`` map every argument
    to its field; gleplot itself no longer calls them, so the mapping is
    pinned here."""
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_plot_line_from_file(
        "a.dat",
        1,
        2,
        color="GREEN",
        linestyle="--",
        linewidth=2,
        label="line",
        yaxis="y2",
        xaxis="x2",
        marker="CIRCLE",
        markersize=0.2,
        nomiss=True,
        line_mode="steps",
    )
    writer.add_errorbar_from_file(
        "a.dat",
        1,
        2,
        yerr_col=3,
        color="RED",
        marker="FSQUARE",
        markersize=0.3,
        label="err",
        capsize=0.1,
        yaxis="y2",
        xaxis="x2",
    )
    writer.add_bar_from_file(
        "a.dat", 1, 4, color="ORANGE", label="bar", swatch_color="BLACK"
    )
    writer.add_fill_from_file(
        "a.dat",
        1,
        2,
        3,
        color="GRAY10",
        label="band",
        swatch_color="GRAY20",
        xmin=0.5,
        xmax=1.5,
        ymin=0,
        ymax=2,
    )
    writer.add_fill_from_file("a.dat", 1, 2, color="BLUE", target="x2")
    assert writer.lines_gle == [
        "    data a.dat d1=c1,c2",
        "    d1 line steps nomiss color GREEN lwidth 0.07056 lstyle 3 "
        'marker CIRCLE msize 0.2 x2axis y2axis key "line"',
        "    data a.dat d2=c1,c2 d3=c1,c3",
        "    d2 marker FSQUARE msize 0.3 color RED err d3 errwidth 0.1 "
        'x2axis y2axis key "err"',
        "    data a.dat d4=c1,c4",
        "    bar d4 fill ORANGE",
        '    d4 keyfill BLACK key "bar"',
        "    data a.dat d5=c1,c2 d6=c1,c3",
        "    fill d5,d6 color GRAY10 xmin 0.5 xmax 1.5 ymin 0 ymax 2",
        '    d5 keyfill GRAY20 key "band"',
        "    data a.dat d7=c1,c2",
        "    fill d7,x2 color BLUE",
    ]

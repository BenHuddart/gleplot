"""Unit tests for plotting functionality."""

import re
import tempfile
import warnings
from pathlib import Path
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
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
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

    def test_matplotlib_short_names_are_honoured(self, recwarn):
        self.ax.plot([0, 1], [0, 1], lw=2.5, ls="--", c="red", ms=10, marker="o")
        self.ax.plot([0, 1], [1, 0], linewidth=2.5, linestyle="--", color="red")
        short, full = self.ax.lines
        assert (short["linewidth"], short["linestyle"], short["color"]) == (
            2.5,
            "--",
            "RED",
        )
        assert short["markersize"] == 0.25
        assert (full["linewidth"], full["linestyle"], full["color"]) == (
            2.5,
            "--",
            "RED",
        )
        assert not recwarn.list

    @pytest.mark.parametrize(
        "name, alias, value, short, stored",
        [("linewidth", "lw", 3, 2, 3), ("color", "c", "red", "blue", "RED")],
    )
    def test_full_name_wins_over_its_short_name(
        self, name, alias, value, short, stored
    ):
        with pytest.warns(UserWarning, match=f"both {name} and {alias}; {name} wins"):
            self.ax.plot([0, 1], [0, 1], **{name: value, alias: short})
        assert self.ax.lines[0][name] == stored

    def test_unsupported_keywords_warn_and_are_ignored(self):
        with pytest.warns(UserWarning) as caught:
            self.ax.plot([0, 1], [0, 1], alpha=0.5, mec="k", transform=None)
        messages = [str(w.message) for w in caught]
        assert messages == [
            "plot() ignores unsupported keyword(s): alpha, mec, transform."
        ]
        assert caught[0].filename == __file__
        assert "alpha" not in self.ax.lines[0]

    def test_a_short_name_given_none_keeps_the_default(self, recwarn):
        self.ax.plot([0, 1], [0, 1], marker="o", ls=None, lw=None, ms=None, c=None)
        line = self.ax.lines[0]
        assert (line["linestyle"], line["linewidth"]) == ("-", 1)
        assert line["markersize"] == pytest.approx(0.15)
        assert not recwarn.list

    @pytest.mark.parametrize("name", ["step", "semilogy", "scatter", "stem"])
    def test_wrappers_of_plot_warn_under_their_own_name(self, name):
        with pytest.warns(UserWarning) as caught:
            getattr(self.ax, name)([1, 2], [1, 2], alpha=0.5)
        assert [str(w.message) for w in caught] == [
            f"{name}() ignores unsupported keyword(s): alpha."
        ]

    @pytest.mark.parametrize("name", ["scatter", "stem"])
    def test_scatter_and_stem_take_no_line_short_names(self, name):
        with pytest.warns(UserWarning) as caught:
            getattr(self.ax, name)([1, 2], [1, 2], lw=3, ms=12)
        assert [str(w.message) for w in caught] == [
            f"{name}() ignores unsupported keyword(s): lw, ms."
        ]


class TestScatterPlots:
    """Test scatter plot functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
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

    @pytest.mark.parametrize(
        "extra, drawn",
        [
            ({}, "marker FCIRCLE"),
            ({"s": [10, 40]}, "marker gleplot_mdata_fcircle "),
            ({"c": [1, 2]}, "marker gleplot_cdata_fcircle_"),
        ],
    )
    def test_scatter_marker_none_is_the_default_circle(self, extra, drawn):
        """matplotlib reads marker=None as rcParams['scatter.marker'], 'o'."""
        self.ax.scatter([1, 2], [1, 2], marker=None, **extra)
        assert drawn in self.fig._generate_gle()

    def test_plot_as_scatter(self):
        """Test plot() with marker creates scatter."""
        self.ax.plot([1, 2, 3], [1, 2, 3], marker="o", linestyle="none")

        # Should be in scatters list, not lines
        assert len(self.ax.scatters) == 1
        assert len(self.ax.lines) == 0


class TestBarCharts:
    """Test bar chart functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
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
            self.ax.bar([1, 2], [3, 4], align="edge", hatch="|")
        messages = " ".join(str(item.message) for item in caught)
        assert "centered" in messages
        assert "hatch '|' has no GLE pattern" in messages
        assert "pattern" not in self.fig._generate_gle()

    def test_bar_hatch_is_a_pattern_over_the_face(self):
        """The ink is the edge colour (black by default), the face goes under."""
        self.ax.bar([1, 2], [3, 4], color="yellow", hatch="//")
        self.ax.bar([1, 2], [1, 1], hatch="\\", edgecolor="blue")
        self.ax.bar([1, 2], [2, 2], hatch="x", color="none")
        script = self.fig._generate_gle()
        assert "bar d1 fill BLACK pattern SHADE2 background YELLOW\n" in script
        assert "fill BLUE pattern RSHADE background RED color BLUE" in script
        assert "fill BLACK pattern GRID background CLEAR\n" in script

    def test_bar_hatch_under_a_none_edge_is_black(self):
        """matplotlib falls back to black when the edge it would use is 'none'."""
        self.ax.bar([1, 2], [3, 4], color="yellow", hatch="/", edgecolor="none")
        script = self.fig._generate_gle()
        assert "fill BLACK pattern SHADE background YELLOW lwidth 0" in script

    def test_bar_hatch_sequence_splits_per_bar(self):
        self.ax.bar([1, 2, 3], [3, 4, 5], hatch=["/", "", "x"], label="mix")
        bars = self.ax.bars
        assert [bar.get("pattern") for bar in bars] == ["SHADE", None, "GRID"]
        assert bars[1]["colors"] == ["RED"] and "background" not in bars[1]

    def test_bar_hatch_sequence_length_and_type_are_checked(self):
        with pytest.raises(ValueError, match="hatch sequence length 2"):
            self.ax.bar([1, 2, 3], [3, 4, 5], hatch=["/", "x"])
        with pytest.raises(TypeError, match="hatch must be a string"):
            self.ax.bar([1, 2], [3, 4], hatch=[1, 2])
        with pytest.raises(TypeError, match="got 5"):
            self.ax.bar([1, 2], [3, 4], hatch=5)
        assert self.ax.bars == []

    def test_barh_hatch(self):
        self.ax.barh([1, 2], [3, 4], hatch="xx", color="teal")
        assert "pattern GRID2 background TEAL horiz" in self.fig._generate_gle()

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

    def test_a_nan_bar_is_written_missing(self):
        """GLE skips a missing (``*``) bar but draws ``nan`` as garbage (#317)."""
        self.ax.bar([1, 2, 3], [1, np.nan, 3])
        self.ax.bar([1, 2, 3], [1, np.nan, 1], bottom=[1, 2, 3])
        _text, files = self.fig._generate_gle_with_files()
        plain, stacked = (files[name].splitlines()[1:] for name in sorted(files))
        assert plain == ["1 1", "2 *", "3 3"]
        # A ``from`` and its ``to`` dataset must be missing at the same rows.
        assert stacked == ["1 1 2", "2 * *", "3 3 4"]

    def test_a_nan_table_bar_gets_its_own_missing_column(self):
        """The table's column stays as it is: another series may read it."""
        from gleplot.sources import ColumnRef, DictDataProvider, TableData

        self.ax.bar([1, 2, 3], [1, 2, 3])
        self.ax.plot([1, 2, 3], [1, 2, 3])
        for series in (self.ax.bars[0], self.ax.lines[0]):
            series["data_source"] = ColumnRef("t", {"x": "x", "height": "y", "y": "y"})
        table = TableData.from_mapping({"x": [1, 2, 3], "y": [1, np.nan, 3]})
        text, files = self.fig._generate_gle_with_files(
            data_provider=DictDataProvider({"t": table})
        )
        (name,) = files
        rows = [line.split() for line in files[name].splitlines()]
        assert rows == [
            ["x", "height", "y"],
            ["1", "1", "1"],
            ["2", "*", "nan"],
            ["3", "3", "3"],
        ]
        assert f"data {name} d1=c1,c2\n" in text
        assert f"data {name} d2=c1,c3\n" in text


class TestFillBetween:
    """Test fill_between functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
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

    def test_fill_betweenx_is_the_polygon_x1_forward_then_x2_back(self):
        returned = self.ax.fill_betweenx([0, 1, 2], [1, 2, 3], label="side")
        assert returned is self.ax
        series = self.ax.fills[0]
        assert series["target"] == "polygon"
        assert list(series["x"]) == [1, 2, 3, 0, 0, 0]
        assert list(series["y1"]) == [0, 1, 2, 2, 1, 0]
        script = self._script()
        assert "fill d1 color LIGHTBLUE" in script
        assert 'key "side"' in script

    def test_fill_betweenx_takes_matplotlib_positional_order(self):
        """``(y, x1, x2, where, step, interpolate)``: step before interpolate."""
        self.ax.fill_betweenx(
            [0, 1, 2], [2, 0, 0], [0, 1, 1], [True, False, False], None, True
        )
        assert self.ax.fills[0]["ymax"] == pytest.approx(2.0 / 3.0, abs=5e-8)
        assert "ymin" not in self.ax.fills[0]
        assert "xmin" not in self.ax.fills[0]

    def test_fill_betweenx_where_clips_each_run_in_y(self):
        self.ax.fill_betweenx(
            [0, 1, 2, 3, 4], 1.0, where=[True, True, False, True, True], color="red"
        )
        assert [(f.get("ymin"), f.get("ymax")) for f in self.ax.fills] == [
            (None, 1.0),
            (3.0, None),
        ]
        assert "fill d2 color RED ymin 3" in self._script()

    def test_fill_betweenx_rejects_bad_arguments(self):
        with pytest.raises(ValueError, match="to match y"):
            self.ax.fill_betweenx([0, 1], [1, 1], where=[True])
        with pytest.raises(ValueError, match="where= or a ymin/ymax clip"):
            self.ax.fill_betweenx([0, 1], [1, 1], where=[True, True], ymin=0)
        with pytest.raises(ValueError, match="x2 has length 3"):
            self.ax.fill_betweenx([0, 1], [1, 1], [2, 3, 4])
        with pytest.raises(ValueError, match="at least one y"):
            self.ax.fill_betweenx([], [])
        with pytest.raises(ValueError, match="1-dimensional"):
            self.ax.fill_betweenx([[0, 1]], [1, 1])

    def test_fill_betweenx_and_stackplot_warn_on_data(self):
        with pytest.warns(UserWarning, match=r"fill_betweenx\(data=\.\.\.\)"):
            self.ax.fill_betweenx([0, 1], [1, 1], data={})
        with pytest.warns(UserWarning, match=r"stackplot\(data=\.\.\.\)"):
            self.ax.stackplot([0, 1], [1, 1], data={})

    def test_fill_betweenx_mask_on_unordered_y_warns(self):
        with pytest.warns(UserWarning, match="strictly monotonic y"):
            self.ax.fill_betweenx([0, 2, 1], [1, 1, 1], where=[True, False, True])
        assert "ymin" not in self.ax.fills[0]

    def test_stackplot_stacks_bands_and_returns_them(self):
        bands = self.ax.stackplot(
            [0, 1, 2], [1, 1, 1], [[1, 2, 1], [2, 2, 2]], labels=["a", "b"]
        )
        assert bands == self.ax.fills
        assert [list(b["y1"]) for b in bands] == [[1, 1, 1], [2, 3, 2], [4, 5, 4]]
        assert list(bands[0]["y2"]) == [0, 0, 0]
        assert [list(b["y2"]) for b in bands[1:]] == [[1, 1, 1], [2, 3, 2]]
        assert [b["label"] for b in bands] == ["a", "b", None]
        assert [b["color"] for b in bands] == [
            "rgb255(31,119,180)",
            "rgb255(255,127,14)",
            "rgb255(44,160,44)",
        ]

    @pytest.mark.parametrize(
        "baseline, first",
        [
            ("zero", [0.0, 0.0]),
            ("sym", [-1.5, -2.0]),
            ("wiggle", [-1.25, -2.0]),
            ("weighted_wiggle", [-1.5, -1.75]),
        ],
    )
    def test_stackplot_baselines_follow_matplotlib(self, baseline, first):
        """First lines checked against matplotlib 3.11's ``stackplot``."""
        bands = self.ax.stackplot(
            [0, 1], [1.0, 2.0], [2.0, 2.0], baseline=baseline, colors=["k"]
        )
        assert list(bands[0]["y2"]) == pytest.approx(first)
        assert all(b["color"] == "BLACK" for b in bands)

    def test_stackplot_facecolor_replaces_colors_and_hatch_warns(self):
        with pytest.warns(UserWarning, match="hatch"):
            bands = self.ax.stackplot([0, 1], [1, 1], [1, 1], fc="red", hatch="//")
        assert [b["color"] for b in bands] == ["RED", "RED"]

    @pytest.mark.parametrize(
        "colors",
        ["red", (1, 0, 0), np.array([1.0, 0.0, 0.0]), np.array([[1.0, 0, 0]] * 2)],
    )
    def test_stackplot_reads_a_single_colour_or_an_rgb_array(self, colors):
        bands = self.ax.stackplot([0, 1], [1, 1], [1, 1], colors=colors)
        assert {b["color"] for b in bands} <= {"RED", "rgb255(255,0,0)"}

    def test_stackplot_color_wins_over_facecolor_with_a_warning(self):
        with pytest.warns(UserWarning, match="color wins"):
            bands = self.ax.stackplot([0, 1], [1, 1], color="red", facecolor="b")
        assert bands[0]["color"] == "RED"

    def test_stackplot_names_its_own_arguments(self):
        with pytest.raises(ValueError, match=r"stackplot\(\) each layer"):
            self.ax.stackplot([0, 1, 2], [1, 2])
        with pytest.warns(UserWarning, match=r"stackplot\(\) ignores .*edgecolor"):
            self.ax.stackplot([0, 1], [1, 1], edgecolor="k", alpha=0.5)
        assert self.ax.fills[0]["alpha"] == 0.5

    def test_figure_and_module_wrappers_reach_the_current_axes(self):
        assert self.fig.fill_betweenx([0, 1], [1, 1], 2) is self.ax
        assert len(self.fig.stackplot([0, 1], [1, 1])) == 1
        assert glp.fill_betweenx([0, 1], [1, 1]) is self.ax
        assert len(glp.stackplot([0, 1], [1, 1], [1, 1])) == 2
        assert len(self.ax.fills) == 5

    def test_stackplot_rejects_bad_arguments(self):
        with pytest.raises(ValueError, match="baseline must be one of"):
            self.ax.stackplot([0, 1], [1, 1], baseline="median")
        with pytest.raises(ValueError, match="at least one layer"):
            self.ax.stackplot([0, 1])
        with pytest.raises(ValueError, match="colors must not be empty"):
            self.ax.stackplot([0, 1], [1, 1], colors=[])


class TestSegmentLines:
    """``hlines`` / ``vlines``: data-bounded segments as lines with gaps."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="seg")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _generate(self):
        return self.fig._generate_gle_with_files()

    def test_vlines_is_one_line_with_missing_value_gaps(self):
        returned = self.ax.vlines([1, 2], 0, [3, 4], label="peaks")
        assert returned is self.ax
        (series,) = self.ax.lines
        assert series["gaps"] is True
        assert series["smooth_mode"] == "none"
        assert series["color"] == "rgb255(31,119,180)"  # matplotlib's 'C0'
        assert series["label"] == "peaks"
        text, files = self._generate()
        assert 'd1 line color rgb255(31,119,180) lwidth 0.05292 key "peaks"' in text
        assert files["seg_0.dat"] == "x peaks\n1 0\n1 3\n* *\n2 0\n2 4\n"

    def test_hlines_runs_from_xmin_to_xmax(self):
        self.ax.hlines([1, 2], [0, 5], 3, colors="r", linestyles="dashed")
        (series,) = self.ax.lines
        assert series["linestyle"] == "--"
        _text, files = self._generate()
        assert files["seg_0.dat"] == "x y\n0 1\n3 1\n* *\n5 2\n3 2\n"

    def test_one_dataset_per_style_and_the_label_on_the_first(self):
        self.ax.vlines(
            [1, 2, 3], 0, 1, colors=["k", "r"], linestyles=["-", ":"], lw=[1, 2, 1]
        )
        styles = [(s["color"], s["linestyle"], s["linewidth"]) for s in self.ax.lines]
        assert styles == [("BLACK", "-", 1.0), ("RED", ":", 2.0)]
        assert [len(s["x"]) for s in self.ax.lines] == [5, 2]
        assert "gaps" not in self.ax.lines[1]  # one segment: no gap row

    def test_label_goes_on_the_first_group_only(self):
        self.ax.vlines([1, 2], 0, 1, colors=["k", "r"], label="pair")
        assert [s["label"] for s in self.ax.lines] == ["pair", None]

    def test_a_segment_with_a_nan_end_is_not_drawn(self):
        self.ax.vlines([1, 2, 3], 0, [1, float("nan"), 2])
        assert list(self.ax.lines[0]["x"][[0, 1, 3, 4]]) == [1, 1, 3, 3]
        assert len(self.ax.lines[0]["x"]) == 5

    def test_autoscale_skips_the_gap_rows(self):
        self.ax.vlines([1, 4], -1, [2, 3])
        text, _files = self._generate()
        assert "xaxis min 1 max 4" in text
        assert "yaxis min -1 max 3" in text

    def test_a_table_backed_gap_series_breaks_at_its_gaps(self):
        """It gets its own ``*`` column; the table's stays for the other line."""
        from gleplot.sources import ColumnRef, DictDataProvider, TableData

        self.ax.plot([0, 1, 2], [0, 1, 2])
        self.ax.plot([0, 1, 2], [0, 1, 2])
        self.ax.lines[0]["gaps"] = True
        for line in self.ax.lines:
            line["data_source"] = ColumnRef("t", {"x": "x", "y": "y"})
        self.ax.set_xlim(0, 2)
        self.ax.set_ylim(0, 2)
        table = TableData.from_mapping({"x": [0, 1, 2], "y": [0, float("nan"), 2]})
        text, files = self.fig._generate_gle_with_files(
            data_provider=DictDataProvider({"t": table})
        )
        (name,) = files
        assert files[name].splitlines() == ["x y y_2", "0 0 0", "1 * nan", "2 2 2"]
        assert f"data {name} d1=c1,c2" in text
        assert f"data {name} d2=c1,c3" in text

    def test_a_table_backed_gap_in_x_gets_its_own_x_column(self):
        from gleplot.sources import ColumnRef, DictDataProvider, TableData

        self.ax.plot([0, 1, 2], [0, 1, 2])
        self.ax.lines[0]["gaps"] = True
        self.ax.lines[0]["data_source"] = ColumnRef("t", {"x": "x", "y": "y"})
        self.ax.set_xlim(0, 2)
        self.ax.set_ylim(0, 2)
        table = TableData.from_mapping({"x": [0, float("nan"), 2], "y": [0, 1, 2]})
        text, files = self.fig._generate_gle_with_files(
            data_provider=DictDataProvider({"t": table})
        )
        (name,) = files
        assert files[name].splitlines() == ["x y", "0 0", "* 1", "2 2"]
        assert f"data {name} d1=c1,c2" in text

    def test_plot_breaks_its_line_at_nan(self):
        """matplotlib breaks a line at NaN; GLE at a missing value, ``*``."""
        self.ax.plot([0, float("nan"), 2], [0, float("nan"), 2])
        self.ax.step([0, 1, 2], [0, float("nan"), 2])
        self.ax.set_xlim(0, 2)
        self.ax.set_ylim(0, 2)
        _text, files = self._generate()
        assert files["seg_0.dat"].splitlines()[1:] == ["0 0", "* *", "2 2"]
        assert "*" in files["seg_1.dat"] and "nan" not in files["seg_1.dat"]

    def test_markers_alone_and_a_line_without_nan_keep_nan_rows(self):
        self.ax.plot([0, float("nan"), 2], [0, 1, 2], linestyle="none", marker="o")
        self.ax.plot([0, 1, 2], [0, 1, 2])
        self.ax.set_xlim(0, 2)
        self.ax.set_ylim(0, 2)
        _text, files = self._generate()
        assert "nan 1" in files["seg_0.dat"]
        assert "*" not in files["seg_0.dat"] + files["seg_1.dat"]

    def test_an_infinity_breaks_the_line_too(self):
        self.ax.plot([0, 1, 2], [0, float("inf"), 2])
        self.ax.set_xlim(0, 2)
        self.ax.set_ylim(0, 2)
        _text, files = self._generate()
        assert files["seg_0.dat"].splitlines()[1:] == ["0 0", "1 *", "2 2"]

    def test_a_gapped_line_warns_that_it_is_not_smoothed_or_thinned(self):
        self.fig.graph.smooth_curves = True
        with pytest.warns(UserWarning) as record:
            self.ax.plot([0, 1, 2, 3], [0, float("nan"), 2, 3], deresolve=2)
        messages = " ".join(str(w.message) for w in record)
        assert "unsmoothed" in messages and "deresolve" in messages
        assert "deresolve" not in self.ax.lines[0]

    def test_figure_and_module_wrappers(self):
        assert self.fig.vlines(1, 0, 1) is self.ax
        assert self.fig.hlines(1, 0, 1) is self.ax
        assert glp.vlines([1, 2], 0, 1) is self.ax
        assert glp.hlines(1, 0, 1, "k") is self.ax
        assert len(self.ax.lines) == 4

    def test_colors_forms(self):
        self.ax.vlines([1, 2], 0, 1, colors=(1, 0, 0))
        self.ax.vlines([1, 2], 0, 1, colors=np.array([[0, 0, 1.0], [0, 0, 1.0]]))
        assert [s["color"] for s in self.ax.lines] == [
            "rgb255(255,0,0)",
            "rgb255(0,0,255)",
        ]

    def test_bad_arguments_are_rejected_or_warned(self):
        with pytest.raises(ValueError, match=r"vlines\(\) ymax has length 3"):
            self.ax.vlines([1, 2], 0, [1, 2, 3])
        with pytest.raises(ValueError, match="linestyles must be"):
            self.ax.hlines(1, 0, 1, linestyles="wavy")
        with pytest.raises(ValueError, match="colors must not be empty"):
            self.ax.vlines(1, 0, 1, colors=[])
        with pytest.warns(UserWarning, match="dash pattern"):
            self.ax.vlines(1, 0, 1, linestyles=[(0, (5, 5))])
        with pytest.warns(
            UserWarning, match=r"ignores unsupported keyword\(s\): alpha"
        ):
            self.ax.vlines(1, 0, 1, alpha=0.5)
        with pytest.warns(UserWarning, match=r"hlines\(data=\.\.\.\)"):
            self.ax.hlines(1, 0, 1, data={})
        with pytest.raises(ValueError, match="must not be empty"):
            self.ax.vlines(1, 0, 1, linestyles=[])
        with pytest.raises(ValueError, match=r"linewidths must be .* 'thick'"):
            self.ax.vlines(1, 0, 1, lw="thick")

    def test_matplotlib_singular_aliases_are_honoured(self):
        self.ax.vlines([1, 2], 0, 1, color="k", linestyle="--", linewidth=2)
        self.ax.hlines(1, 0, 1, ls=":")
        assert [(s["color"], s["linestyle"]) for s in self.ax.lines] == [
            ("BLACK", "--"),
            ("rgb255(31,119,180)", ":"),
        ]
        assert self.ax.lines[0]["linewidth"] == 2.0

    def test_both_names_of_one_property_warn_and_the_plural_wins(self):
        with pytest.warns(UserWarning) as record:
            self.ax.vlines(
                1,
                0,
                1,
                colors="r",
                color="b",
                linestyles=":",
                ls="--",
                lw=3,
                linewidths=1,
            )
        messages = " ".join(str(w.message) for w in record)
        assert "colors wins" in messages
        assert "linestyles wins" in messages
        assert "linewidths wins" in messages
        series = self.ax.lines[0]
        assert (series["color"], series["linestyle"], series["linewidth"]) == (
            "RED",
            ":",
            1.0,
        )

    def test_one_dash_tuple_is_one_style_and_none_draws_nothing(self):
        with pytest.warns(UserWarning) as record:
            self.ax.vlines(1, 0, 1, linestyles=(0, (5, 2)))
        assert len(record) == 1
        self.ax.vlines([2, 3, 4], 0, 1, linestyles=["-", "None"])
        assert [list(s["x"][[0, -1]]) for s in self.ax.lines] == [[1, 1], [2, 4]]
        assert len(self.ax.lines[1]["x"]) == 5

    def test_a_gaps_line_gets_no_preview_deresolve(self):
        self.ax.vlines(np.arange(600.0), 0, 1)
        self.ax.plot(np.arange(1200.0), np.ones(1200))
        writer_text = self.fig._generate_gle_with_files(preview_decimation=3)[0]
        assert "d1 line" in writer_text and "deresolve" not in (
            writer_text.split("d1 line")[1].splitlines()[0]
        )
        assert "deresolve 3" in writer_text.split("d2 line")[1].splitlines()[0]

    def test_nothing_finite_adds_nothing(self):
        assert self.ax.vlines([], 0, 1) is self.ax
        assert self.ax.lines == []

    def test_gaps_survive_open_gle(self, tmp_path):
        from gleplot.parser.recognizer import parse_gle_figure

        self.ax.vlines([1, 2], 0, 1)
        self.ax.plot([0, 1], [0, 1])
        path = self.fig.savefig_gle(str(tmp_path / "seg.gle"))
        lines = parse_gle_figure(path).figure.axes_list[0].lines
        assert [s.get("gaps") for s in lines] == [True, None]
        assert lines[0]["smooth_mode"] == "none"


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
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_matplotlib_keywords_are_honoured(self, recwarn):
        self.ax.errorbar([1, 2], [1, 2], yerr=0.1, lw=2, c="red", ms=10, ls="--")
        series = self.ax.errorbars[0]
        assert (series["linewidth"], series["color"], series["linestyle"]) == (
            2,
            "RED",
            "--",
        )
        assert series["markersize"] == pytest.approx(0.25)
        assert not recwarn.list

    def test_linestyle_overrides_fmt_but_not_fmt_none(self):
        with pytest.warns(UserWarning, match="the keyword wins"):
            self.ax.errorbar([1, 2], [1, 2], yerr=0.1, fmt="--", linestyle=":")
        self.ax.errorbar([1, 2], [1, 2], yerr=0.1, fmt="none", ls="--")
        assert [s["linestyle"] for s in self.ax.errorbars] == [":", "none"]

    def test_a_none_full_name_leaves_the_short_name_alone(self, recwarn):
        self.ax.errorbar([1, 2], [1, 2], yerr=0.1, linewidth=None, lw=3)
        assert self.ax.errorbars[0]["linewidth"] == 3
        assert not recwarn.list

    def test_unsupported_keywords_warn_and_are_ignored(self):
        with pytest.warns(UserWarning) as caught:
            self.ax.errorbar([1, 2], [1, 2], yerr=0.1, ecolor="k", elinewidth=2)
        assert [str(w.message) for w in caught] == [
            "errorbar() ignores unsupported keyword(s): ecolor, elinewidth."
        ]
        assert caught[0].filename == __file__

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
            x, y, yerr=([1, 2, 3], [3, 2, 1]), marker="s", linestyle="none", color="red"
        )

        gle = self.fig._generate_gle()
        assert "errup" in gle
        assert "errdown" in gle

    def test_errorbar_horizontal_gle(self):
        """Test GLE generation for horizontal error bars."""
        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])
        self.ax.errorbar(x, y, xerr=0.3, marker="o", linestyle="none")

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

    def test_unsupported_keywords_warn_and_are_ignored(self):
        with pytest.warns(
            UserWarning, match=r"^errorbar_from_file\(\) ignores .*: ecolor\.$"
        ):
            self.ax.errorbar_from_file(str(self.data_path), 1, 2, 3, ecolor="k")
        assert len(self.ax.file_series) == 1

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

    def test_errorbar_from_file_takes_the_data_range(self, recwarn):
        self.ax.errorbar_from_file(str(self.data_path), 1, 2, 3, xmin=0.5, ymax=12)
        assert not recwarn.list
        series = self.ax.file_series[0]
        assert (series["xmin"], series["ymax"]) == (0.5, 12.0)
        assert "xmax" not in series
        with pytest.raises(ValueError, match="ymin must be less than ymax"):
            self.ax.errorbar_from_file(str(self.data_path), 1, 2, ymin=3, ymax=1)

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


def _fake_savefig(*args, **kwargs):
    """Write what a real ``savefig`` leaves beside its output, without GLE."""
    out = Path(args[-1])
    out.write_bytes(b"image")
    out.with_suffix(".gle").write_text("size 10 10\n")
    out.with_name(out.stem + "_0.dat").write_text("1 2\n")
    (out.parent / ".gle").mkdir()
    (out.parent / ".gle" / "texpreamble.tex").write_text("")
    return out


@pytest.mark.skipif(not IPYTHON_AVAILABLE, reason="IPython not installed")
class TestViewDisplay:
    """Test figure view behavior across environments."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self, tmp_path, monkeypatch):
        """Create fresh figure for each test."""
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        glp.close()
        self.fig = glp.figure()
        self.fig.add_subplot(111).plot([1, 2, 3], [1, 4, 9])
        yield
        glp.close()

    @patch("IPython.display.display")
    @patch("IPython.display.Image")
    @patch("IPython.get_ipython")
    @patch.object(glp.Figure, "savefig", autospec=True, side_effect=_fake_savefig)
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
        mock_image.assert_called_once_with(data=b"image", format="png")
        mock_display.assert_called_once_with(image_obj)

    @patch("IPython.get_ipython")
    @patch.object(glp.Figure, "savefig", autospec=True, side_effect=_fake_savefig)
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
    monkeypatch.setattr(glp.Figure, "savefig", Mock(side_effect=_fake_savefig))
    yield fig
    glp.close()


def test_view_outside_notebook_returns_path_and_prints_nothing(
    viewable_figure, tmp_path, capsys
):
    result = viewable_figure.view()

    assert result.parent == tmp_path
    assert result.suffix == ".png"
    assert result.read_bytes() == b"image"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("fmt", ["png", "pdf"])
def test_view_leaves_only_the_returned_file(viewable_figure, tmp_path, fmt):
    result = viewable_figure.view(format=fmt)

    assert sorted(tmp_path.iterdir()) == [result]


def test_view_svg_in_notebook_warns_and_returns_path(viewable_figure, tmp_path):
    pytest.importorskip("IPython")
    with patch("IPython.get_ipython", return_value=Mock(config={"IPKernelApp": 1})):
        with pytest.warns(UserWarning, match="cannot display SVG inline"):
            result = viewable_figure.view(format="svg")

    assert sorted(tmp_path.iterdir()) == [result]
    assert result.suffix == ".svg"


def test_view_cleans_up_when_savefig_fails(viewable_figure, tmp_path):
    glp.Figure.savefig.side_effect = RuntimeError("compile failed")

    with pytest.raises(RuntimeError, match="compile failed"):
        viewable_figure.view()

    assert list(tmp_path.iterdir()) == []


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


def test_close_all_closes_the_current_figure():
    """matplotlib's close('all'); gleplot tracks one figure."""
    fig = glp.figure()
    glp.plot([1, 2], [1, 2])
    glp.close("all")
    assert fig.axes_list == []
    assert glp.gcf() is not fig


def test_closing_the_current_figure_starts_a_new_one():
    fig = glp.figure()
    glp.plot([1, 2], [1, 2])
    glp.close(fig)
    assert fig.axes_list == []
    assert glp.gcf() is not fig


@pytest.mark.parametrize("fig", [1, "fig1"])
def test_close_by_number_or_label_warns_and_closes_nothing(fig):
    current = glp.figure()
    glp.plot([1, 2], [1, 2])
    with pytest.warns(UserWarning, match="closes nothing"):
        glp.close(fig)
    assert glp.gcf() is current and current.axes_list


@pytest.mark.parametrize("fig", [2.0, True])
def test_close_rejects_a_wrong_type(fig):
    with pytest.raises(TypeError, match=rf"close\({fig!r}\)"):
        glp.close(fig)


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

    def test_drawstyle_wins_over_ds_with_a_warning(self):
        with pytest.warns(UserWarning, match="got both drawstyle and ds"):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-pre", ds="steps-post")
        assert self.ax.lines[0]["line_mode"] == "fsteps"
        self.ax.plot([0, 1], [0, 1], drawstyle="default", ds="steps-post")
        assert self.ax.lines[1]["line_mode"] == "steps"

    def test_unknown_where_or_drawstyle_raises(self):
        with pytest.raises(ValueError):
            self.ax.step([0, 1], [0, 1], where="side")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-left")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], line_mode="spline")
        with pytest.raises(ValueError):
            self.ax.stem([0, 1], orientation="sideways")
        with pytest.raises(TypeError):
            self.ax.stem()
        with pytest.warns(UserWarning):
            self.ax.stem([0, 1], [1, 2], bottom="low")

    def test_drawstyle_and_line_mode_must_agree(self):
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], drawstyle="steps-post", line_mode="hist")

    def test_step_reads_a_format_string_as_plot_does(self):
        self.ax.step([0, 1], [0, 1], "r--")
        assert self.ax.lines[0]["line_mode"] == "fsteps"
        assert self.ax.lines[0]["color"] == "RED"
        assert self.ax.lines[0]["linestyle"] == "--"
        with pytest.warns(UserWarning, match="one format string"):
            self.ax.step([0, 1], [0, 1], "r--", "b")

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

    def test_from_file_reading_options_are_stored_only_when_given(self):
        self.ax.line_from_file("wave.csv", 1, 2)
        self.ax.errorbar_from_file(
            "wave.csv", 0, 2, skiprows=1, comment="#", max_rows=4
        )
        plain, read = self.ax.file_series
        assert not {"skiprows", "comment", "max_rows"} & set(plain)
        assert (read["x_col"], read["skiprows"], read["comment"]) == (0, 1, "#")
        assert read["max_rows"] == 4

    def test_from_file_accepts_numpy_integer_counts(self):
        self.ax.line_from_file(
            "wave.csv", 1, 2, skiprows=np.int64(2), max_rows=np.int32(5)
        )
        series = self.ax.file_series[0]
        assert (series["skiprows"], series["max_rows"]) == (2, 5)
        assert type(series["skiprows"]) is int and type(series["max_rows"]) is int

    @pytest.mark.parametrize(
        "kwargs, error, match",
        [
            ({"skiprows": -1}, ValueError, "skiprows must be >= 0; got -1"),
            ({"skiprows": 1.5}, TypeError, "skiprows must be an integer; got 1.5"),
            ({"max_rows": True}, TypeError, "max_rows must be an integer"),
            ({"max_rows": 0}, ValueError, "max_rows must be >= 1, or None"),
            ({"comment": 3}, TypeError, "comment must be a string"),
            ({"comment": ""}, ValueError, "comment must be a non-empty string"),
            ({"comment": "a b"}, ValueError, "comment must be"),
            ({"comment": '"'}, ValueError, "comment must be"),
            ({"x_col": -1}, ValueError, "x_col must be >= 0"),
            ({"y_col": 0}, ValueError, "y_col must be >= 1, got 0"),
        ],
    )
    def test_from_file_rejects_bad_reading_arguments(self, kwargs, error, match):
        call = {"data_file": "wave.csv", "x_col": 1, "y_col": 2, **kwargs}
        with pytest.raises(error, match=match):
            self.ax.line_from_file(**call)
        with pytest.raises(error, match=match):
            self.ax.errorbar_from_file(**call)
        assert self.ax.file_series == []

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


class TestDatasetQualifiers:
    """``mdist``, ``deresolve [average]`` and the per-dataset data range."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="qual")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _dn_lines(self, fig=None):
        script = (fig or self.fig)._generate_gle()
        return [ln.strip() for ln in script.splitlines() if ln.strip()[:2] == "d1"]

    def test_absent_keywords_leave_the_series_and_script_unchanged(self):
        self.ax.plot([0, 1, 2], [1, 2, 1], marker="o")
        for name in ("mdist", "deresolve", "deresolve_average", "xmin", "ymax"):
            assert name not in self.ax.lines[0]
        assert self._dn_lines() == [
            'd1 line color BLUE lwidth 0.05292 marker FCIRCLE msize 0.15 key ""'
        ]

    def test_each_qualifier_is_written_on_the_dataset_line(self):
        self.ax.plot(
            [0, 1, 2],
            [1, 2, 1],
            marker="o",
            mdist=0.5,
            deresolve=3,
            deresolve_average=True,
            xmin=0.5,
            xmax=1.5,
            ymin=0,
            ymax=2,
        )
        (line,) = self._dn_lines()
        assert line.endswith(
            "msize 0.15 mdist 0.5 deresolve 3 average "
            'xmin 0.5 xmax 1.5 ymin 0 ymax 2 key ""'
        )

    def test_scatter_passes_the_qualifiers_to_plot(self):
        self.ax.scatter([0, 1, 2], [1, 2, 1], deresolve=2, ymin=1.5)
        assert self.ax.scatters[0]["deresolve"] == 2
        (line,) = self._dn_lines()
        assert " color BLUE deresolve 2 ymin 1.5 " in line

    def test_marker_config_mdist_is_the_default_for_marked_lines(self):
        fig = glp.figure(data_prefix="qual", marker=glp.GLEMarkerConfig(mdist=0.7))
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1], marker="o")
        ax.plot([0, 1], [1, 0])
        ax.scatter([0, 1], [1, 1])
        ax.plot([0, 1], [2, 2], marker="s", mdist=1.2)
        script = fig._generate_gle()
        mdists = [
            ln.split("mdist ")[1].split()[0]
            for ln in script.splitlines()
            if "mdist" in ln
        ]
        assert mdists == ["0.7", "1.2"]

    @pytest.mark.parametrize("mdist", [0, -1.0, float("inf"), "1", True])
    def test_marker_config_rejects_a_bad_mdist(self, mdist):
        with pytest.raises(ValueError, match="mdist"):
            glp.GLEMarkerConfig(mdist=mdist)

    def test_markevery_warns_and_is_ignored(self):
        with pytest.warns(UserWarning, match="markevery"):
            self.ax.plot([0, 1], [0, 1], marker="o", markevery=2)
        assert "mdist" not in self.ax.lines[0]

    def test_mdist_without_a_marker_warns_and_is_dropped(self):
        with pytest.warns(UserWarning, match="no marker"):
            self.ax.plot([0, 1], [0, 1], mdist=1.0)
        assert "mdist" not in self.ax.lines[0]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"mdist": 0},
            {"mdist": -1.0},
            {"mdist": float("nan")},
            {"deresolve": 0},
            {"deresolve": 2.5},
            {"deresolve": True},
            {"deresolve_average": True},
            {"xmin": 2, "xmax": 1},
            {"ymin": 1, "ymax": 1},
            {"ymax": float("inf")},
        ],
    )
    def test_bad_values_raise_at_the_call(self, kwargs):
        kwargs.setdefault("marker", "o")
        with pytest.raises(ValueError):
            self.ax.plot([0, 1], [0, 1], **kwargs)
        assert self.ax.lines == []

    @pytest.mark.parametrize("kwargs", [{"mdist": "1cm"}, {"xmin": None, "xmax": "a"}])
    def test_wrong_types_raise_type_error(self, kwargs):
        with pytest.raises(TypeError):
            self.ax.plot([0, 1], [0, 1], marker="o", **kwargs)

    def test_errorbar_takes_the_data_range(self):
        self.ax.errorbar([0, 1, 2], [1, 2, 1], yerr=0.1, xmin=0.5, ymax=1.5)
        (line,) = self._dn_lines()
        assert line.endswith(' err d2 xmin 0.5 ymax 1.5 key ""')
        with pytest.raises(ValueError, match="xmin must be less than xmax"):
            self.ax.errorbar([0, 1], [0, 1], yerr=0.1, xmin=2, xmax=1)
        with pytest.raises(TypeError, match="ymin"):
            self.ax.errorbar([0, 1], [0, 1], yerr=0.1, ymin="a")
        with pytest.warns(UserWarning, match="deresolve"):
            self.ax.errorbar([0, 1], [0, 1], yerr=0.1, deresolve=2)
        assert len(self.ax.errorbars) == 2
        assert "deresolve" not in self.ax.errorbars[1]

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            ({"ymin": 100}, "only ymin = 100, .* missing ymax from the y axis limit 9"),
            ({"xmax": -1}, "only xmax = -1, .* missing xmin from the x axis limit 0"),
        ],
    )
    def test_a_lone_edge_past_the_axis_limit_warns_at_save(self, kwargs, match):
        """GLE fills the other edge from the axis limit: an empty range."""
        self.ax.plot([0, 1, 2, 3], [0, 1, 4, 9], **kwargs)
        with pytest.warns(UserWarning, match=match):
            self.fig._generate_gle()

    def test_a_non_positive_edge_on_a_log_axis_warns_at_save(self):
        self.ax.plot([1, 2], [1, 10], ymin=0, ymax=20)
        self.ax.set_yscale("log")
        with pytest.warns(UserWarning, match="y edge 0 on the log y axis"):
            self.fig._generate_gle()

    def test_a_lone_edge_past_a_log_axis_limit_warns_at_save(self):
        self.ax.plot([1, 2], [1, 10], ymin=1000)
        self.ax.set_yscale("log")
        self.ax.set_ylim(1, 100)
        with pytest.warns(UserWarning, match="only ymin = 1000"):
            self.fig._generate_gle()

    def test_a_range_gle_can_draw_does_not_warn(self, recwarn):
        self.ax.plot([0, 1, 2, 3], [0, 1, 4, 9], ymin=100, ymax=200)
        self.ax.plot([0, 1, 2, 3], [0, 1, 4, 9], ymin=2)
        self.fig._generate_gle()
        assert not recwarn.list


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


class TestFunction:
    """Curves GLE samples from an expression with ``let``."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="fn")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _script(self):
        return self.fig._generate_gle()

    def test_emits_a_let_and_a_line_with_no_data_file(self):
        self.ax.function("sin(x)", xmin=0, xmax=6.28, step=0.05, label="sine")
        text, files = self.fig._generate_gle_with_files()
        assert "let d1 = sin(x) from 0 to 6.28 step 0.05" in text
        assert 'd1 line color BLUE lwidth 0.05292 key "sine"' in text
        assert "    data " not in text
        assert files == {}
        assert self.ax.functions[0]["expression"] == "sin(x)"

    def test_omitted_range_and_step_are_left_to_gle(self):
        self.ax.function("x^2", color="red", linestyle=":")
        lines = self._script().splitlines()
        assert "    let d1 = x^2" in lines
        assert "    d1 line color RED lwidth 0.05292 lstyle 2" in lines

    def test_figure_wide_smoothing_leaves_the_curve_alone(self):
        self.fig.graph.smooth_curves = True
        self.ax.function("sin(x)", xmin=0, xmax=1)
        line = next(ln for ln in self._script().splitlines() if "d1 line" in ln)
        assert "smooth" not in line

    def test_the_range_widens_x_and_nothing_sets_y(self):
        self.ax.plot([1, 2], [5, 6])
        self.ax.function("sin(x)", xmin=-1, xmax=4)
        script = self._script()
        assert "xaxis min -1 max 4" in script
        assert "yaxis min 5 max 6" in script

    def test_a_curve_alone_leaves_y_to_gle(self):
        self.ax.function("sin(x)", xmin=0, xmax=3)
        script = self._script()
        assert "xaxis min 0 max 3" in script
        assert "yaxis min" not in script

    def test_draws_in_call_order_with_other_series(self):
        self.ax.function("sin(x)", xmin=0, xmax=1)
        self.ax.plot([0, 1], [0, 1])
        lines = self._script().splitlines()
        assert lines.index("    let d1 = sin(x) from 0 to 1") < next(
            i for i, ln in enumerate(lines) if ln.startswith("    data ")
        )

    def test_a_hidden_curve_writes_nothing(self):
        self.ax.function("sin(x)", xmin=0, xmax=1)
        self.ax.functions[0]["visible"] = False
        assert "let " not in self._script()

    @pytest.mark.parametrize(
        "expression, message",
        [
            ("sin(x) + 1", "first space"),
            ("sin(x),cos(x)", "second expression"),
            ("d1*2", "names a dataset"),
            ("", "empty"),
            ("x!c", "end of the expression"),
            ("x;y", "end of the expression"),
            ("sin(x", "leaves a bracket open"),
            ("x)*(2", "never opened"),
        ],
    )
    def test_rejects_an_expression_gle_would_misread(self, expression, message):
        with pytest.raises(ValueError, match=message):
            self.ax.function(expression)
        assert self.ax.functions == []

    def test_a_comma_inside_brackets_is_one_expression(self):
        self.ax.function("max(x,1)", xmin=0, xmax=2)
        assert "let d1 = max(x,1) from 0 to 2" in self._script()

    def test_rejects_a_non_string_expression(self):
        with pytest.raises(TypeError, match="expression must be a str"):
            self.ax.function(lambda x: x)

    @pytest.mark.parametrize(
        "kwargs, error, message",
        [
            ({"xmin": 2, "xmax": 1}, ValueError, "xmin < xmax"),
            ({"step": 0}, ValueError, "step must be positive"),
            ({"xmin": float("nan")}, ValueError, "xmin must be finite"),
            ({"xmax": "end"}, TypeError, "xmax must be a number"),
            ({"linestyle": "none"}, ValueError, "linestyle must be"),
            ({"linewidth": "thick"}, TypeError, "linewidth must be a number"),
        ],
    )
    def test_rejects_bad_options_when_called(self, kwargs, error, message):
        with pytest.raises(error, match=message):
            self.ax.function("x", **kwargs)


class TestFit:
    """Curves GLE fits to data with ``let ... = fit``."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="ft")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _script(self):
        return self.fig._generate_gle()

    def test_emits_the_data_a_fit_let_and_a_line(self):
        self.ax.fit(
            [0, 1, 2],
            [1.0, 0.5, 0.25],
            "a*exp(-x*k)",
            xmin=0,
            xmax=3,
            step=0.1,
            label="fit",
        )
        text, files = self.fig._generate_gle_with_files()
        assert (
            "    data ft_0.dat d1=c1,c2\n"
            "    let d2 = fit d1 with a*exp(-x*k) from 0 to 3 step 0.1\n"
            '    d2 line color BLUE lwidth 0.05292 key "fit"\n'
        ) in text
        # No header row: GLE would key the data dataset the let reads.
        assert files["ft_0.dat"].splitlines()[0].split() == ["0", "1"]

    def test_omitted_range_and_step_are_left_to_gle(self):
        self.ax.fit([0, 1], [0, 1], "a*x+b", color="red", linestyle=":")
        lines = self._script().splitlines()
        assert "    let d2 = fit d1 with a*x+b" in lines
        assert "    d2 line color RED lwidth 0.05292 lstyle 2" in lines

    def test_the_data_bounds_both_axes_and_the_range_widens_x(self):
        self.ax.fit([1, 2], [5, 6], "a*x+b", xmin=-1, xmax=4)
        script = self._script()
        assert "xaxis min -1 max 4" in script
        assert "yaxis min 5 max 6" in script

    def test_a_hidden_fit_writes_nothing(self):
        self.ax.fit([0, 1], [0, 1], "a*x")
        self.ax.fits[0]["visible"] = False
        text, files = self.fig._generate_gle_with_files()
        assert "let " not in text
        assert files == {}

    def test_rejects_data_of_different_lengths(self):
        with pytest.raises(ValueError, match="same length, got 2 and 3"):
            self.ax.fit([0, 1], [0, 1, 2], "a*x")
        assert self.ax.fits == []

    def test_rejects_data_that_is_not_numbers(self):
        with pytest.raises(TypeError, match="fit\\(\\) x must be a sequence"):
            self.ax.fit(["a", "b"], [1, 2], "k*x")

    def test_rejects_data_with_no_finite_point(self):
        with pytest.raises(ValueError, match="at least one point"):
            self.ax.fit([0.0, np.nan], [np.nan, 1.0], "a*x")

    def test_checks_the_expression_and_options_as_function_does(self):
        with pytest.raises(ValueError, match=r"fit\(\) expression .* first space"):
            self.ax.fit([0, 1], [0, 1], "a * x")
        with pytest.raises(TypeError, match="such as 'a\\*exp"):
            self.ax.fit([0, 1], [0, 1], 3)
        with pytest.raises(ValueError, match=r"fit\(\) step must be positive"):
            self.ax.fit([0, 1], [0, 1], "a*x", step=-1)
        assert self.ax.fits == []

    @pytest.mark.parametrize(
        "model, routine",
        [
            ("linear", "linfit"),
            ("exp", "logefit"),
            ("exp10", "log10fit"),
            ("power", "powxfit"),
        ],
    )
    def test_a_model_writes_its_closed_form_routine(self, model, routine):
        self.ax.fit([1, 2, 3], [2.0, 4.0, 8.0], model=model, xmin=0.5)
        assert (
            "    data ft_0.dat d1=c1,c2\n"
            f"    let d2 = {routine} d1 from 0.5\n"
            "    d2 line color BLUE lwidth 0.05292\n"
        ) in self._script()
        assert "expression" not in self.ax.fits[0]

    @pytest.mark.parametrize(
        "args, kwargs, message",
        [
            ((), {}, "needs an expression .* or a model .*got neither"),
            (("a*x",), {"model": "linear"}, "not both; got expression='a\\*x'"),
            ((), {"model": "quadratic"}, "'linear', 'exp', 'exp10', 'power', got"),
            ((), {"model": "exp"}, "'exp' needs every y above 0, got y=-1.0"),
            ((), {"model": "power"}, "'power' needs every y above 0, got y=-1.0"),
            ((), {"model": "linear", "step": 0.1}, "step has no effect with a model"),
        ],
    )
    def test_rejects_a_bad_expression_and_model_choice(self, args, kwargs, message):
        with pytest.raises(ValueError, match=message):
            self.ax.fit([0, 1, 2], [-1.0, 1.0, 2.0], *args, **kwargs)
        assert self.ax.fits == []

    def test_rejects_a_model_that_is_not_a_str(self):
        with pytest.raises(TypeError, match="model must be a str .* got list"):
            self.ax.fit([0, 1], [0, 1], model=["linear"])

    def test_power_rejects_x_at_or_below_zero(self):
        with pytest.raises(
            ValueError, match="'power' needs every x above 0, got x=0.0"
        ):
            self.ax.fit([0, 1, 2], [1.0, 1.0, 2.0], model="power")

    @pytest.mark.parametrize("x", [[1.0], [2.0, 2.0, 2.0]])
    def test_a_model_needs_two_distinct_x(self, x):
        with pytest.raises(ValueError, match="two or more distinct x, got x="):
            self.ax.fit(x, [1.0] * len(x), model="linear")

    def test_a_log_model_ignores_points_that_are_not_finite(self):
        self.ax.fit([np.nan, 1, 2], [-1.0, 1.0, 2.0], model="exp10")
        assert self.ax.fits[0]["model"] == "exp10"

    def test_a_label_placeholder_shows_the_fit_in_a_key_after_the_graph(self):
        self.ax.fit(
            [1, 2, 3],
            [2.0, 4.0, 5.0],
            model="linear",
            label="$y$ = {slope:.2f}x + {offset:.1e}, r$^2$ {rsq}",
        )
        self.ax.legend()
        expression = (
            '"y = "+format$(fit1_slope,"fix 2")+"x + "+'
            'format$(fit1_offset,"sci 2 e expdigits 2 expsign")+", r^{2} "+'
            "num$(fit1_rsq)"
        )
        assert (
            "    let d2 = linfit d1 fit1_slope fit1_offset fit1_rsq\n"
            f"    d2 line color BLUE lwidth 0.05292 key {expression}\n"
            "    key off\n"
            "end graph\n"
            "begin key\n"
            "    position tr\n"
            f"    text {expression} color BLUE lwidth 0.05292 lstyle 1\n"
            "end key"
        ) in self._script()

    @pytest.mark.parametrize("model", ["exp", "exp10", "power"])
    def test_a_log_model_names_the_exponent_first(self, model):
        self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model=model, label="{prefactor:.3f}")
        script = self._script()
        assert " d1 fit1_exponent fit1_prefactor fit1_rsq\n" in script
        assert 'text format$(fit1_prefactor,"fix 3") color' in script

    def test_each_fit_has_its_own_result_variables(self):
        for label in ("{slope}", "fit", "{rsq:.2f}"):
            self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model="linear", label=label)
        lets = [line for line in self._script().splitlines() if "linfit" in line]
        assert lets == [
            "    let d2 = linfit d1 fit1_slope fit1_offset fit1_rsq",
            "    let d4 = linfit d3",
            "    let d6 = linfit d5 fit2_slope fit2_offset fit2_rsq",
        ]

    def test_a_hidden_legend_keeps_the_key_off(self):
        self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model="linear", label="{slope}")
        self.ax.legend_on = False
        script = self._script()
        assert "    key off\n" in script
        assert "begin key" not in script

    def test_placeholders_are_text_on_an_expression_fit(self):
        self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], "a*x", label="{slope}")
        assert 'key "\\char{123}slope\\char{125}"' in self._script()

    def test_a_usetex_label_keeps_its_math_around_a_placeholder(self):
        fig = glp.figure(style=glp.GLEStyleConfig(usetex=True), data_prefix="ft")
        ax = fig.add_subplot(111)
        ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model="linear", label="$r^2={rsq:.3f}$")
        assert 'key "$r^2="+format$(fit1_rsq,"fix 3")+"$"' in fig._generate_gle()

    def test_a_placeholder_can_be_a_superscript(self):
        self.ax.fit(
            [1, 2, 3], [2.0, 4.0, 5.0], model="power", label="$x^{exponent:.1f}$"
        )
        assert self.ax.fits[0]["label"] == "x^{{exponent:.1f}}"
        assert 'key "x^{"+format$(fit1_exponent,"fix 1")+"}"' in self._script()

    def test_a_label_placeholder_its_model_does_not_fill_is_text(self):
        # Axes.fit rejects it; a label set on the series directly is written
        # as text rather than failing at save.
        self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model="linear", label="fit")
        self.ax.fits[0]["label"] = "{prefactor} {slope:x}"
        assert 'key "{prefactor} {slope:x}"' in self._script()

    def test_a_reference_backed_fit_shows_its_results(self):
        from gleplot.sources import ColumnRef, DictDataProvider, TableData

        self.ax.fit([1, 2], [1.0, 2.0], model="linear", label="s={slope:.2f}")
        self.ax.fits[0]["data_source"] = ColumnRef("t1", {"x": "a", "y": "b"})
        provider = DictDataProvider(
            {"t1": TableData.from_mapping({"a": [1.0, 2.0], "b": [1.0, 3.0]})}
        )
        text, _files = self.fig._generate_gle_with_files(data_provider=provider)
        assert '    text "s="+format$(fit1_slope,"fix 2") color' in text

    @pytest.mark.parametrize(
        "model, label, message",
        [
            ("exp", "{slope}", r"'\{slope\}' is not filled by model='exp'"),
            ("linear", "{prefactor}", r"which fills \{slope\}, \{offset\}"),
            ("linear", "{rsq:.2g}", "has format '.2g'; use .Nf or .Ne"),
            ("linear", "{rsq:3f}", "has format '3f'"),
            ("power", 'a "b" {rsq}', "cannot contain a double quote"),
        ],
    )
    def test_rejects_a_label_gle_cannot_fill(self, model, label, message):
        with pytest.raises(ValueError, match=message):
            self.ax.fit([1, 2, 3], [2.0, 4.0, 5.0], model=model, label=label)
        assert self.ax.fits == []


class TestDerived:
    """Curves GLE computes from other series with a dataset ``let``."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        self.fig = glp.figure(data_prefix="dv")
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def _script(self):
        return self.fig._generate_gle()

    def test_names_each_source_by_the_dataset_it_was_written_as(self):
        ax = self.ax
        ax.line_from_file("run1.dat", 1, 2)
        ax.plot([0, 1, 2], [1, 2, 3])
        ax.derived("d1-d2", [ax.lines[0], ax.file_series[0]], label="diff")
        assert (
            "    data dv_0.dat d1=c1,c2\n"
            '    d1 line color BLUE lwidth 0.05292 key ""\n'
            "    data run1.dat d2=c1,c2\n"
            "    d2 line color BLUE lwidth 0.05292\n"
            "    let d3 = d1-d2\n"
            '    d3 line color BLUE lwidth 0.05292 key "diff"\n'
        ) in self._script()

    def test_writes_every_option_and_reads_an_offset_source_raw(self):
        ax = self.ax
        ax.scatter([0, 1, 2], [1, 2, 3], offset=2)
        ax.function("sin(x)", xmin=0, xmax=2)
        ax.derived(
            "d2*d1",
            [ax.scatters[0], ax.functions[0]],
            xmin=0,
            xmax=2,
            nsteps=11,
            where="d1>1",
            range=[ax.functions[0], ax.scatters[0]],
            color="red",
            linestyle="--",
        )
        script = self._script()
        assert "    let d1 = sin(x) from 0 to 2\n" in script
        assert "    data dv_0.dat d2=c1,c2\n    let d3 = d2+2\n" in script
        assert (
            "    let d4 = d1*d2 from 0 to 2 nsteps 11 where d2>1 range d1,d2\n"
            "    d4 line color RED lwidth 0.05292 lstyle 3\n"
        ) in script

    def test_is_written_after_the_file_series_it_reads(self):
        ax = self.ax
        ax.line_from_file("a.dat", 1, 2)
        ax.derived("2*d1", [ax.file_series[0]], step=0.5)
        ax.plot([0, 1], [0, 1])
        script = self._script()
        assert script.index("let d3 = 2*d2 step 0.5") > script.index("data a.dat d2")

    def test_a_hidden_source_leaves_the_curve_out_with_a_warning(self):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.derived("d1+1", [ax.lines[0]], label="shifted")
        ax.lines[0]["visible"] = False
        with pytest.warns(
            UserWarning, match=r"derived\(\) curve 'd1\+1' was not drawn"
        ):
            script = self._script()
        assert "let" not in script
        assert "shifted" not in script

    def test_a_removed_source_leaves_the_curve_out_with_a_warning(self):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.derived("d1+1", [ax.lines[0]])
        ax.lines.clear()
        with pytest.warns(UserWarning, match="no longer holds a series"):
            assert "let" not in self._script()

    @pytest.mark.parametrize("ref", [["lines"], ["bars", 0], ["lines", "0"]])
    def test_a_stored_reference_it_cannot_follow_leaves_the_curve_out(self, ref):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.bar([0, 1], [1, 2])
        ax.derived("d1+1", [ax.lines[0]])
        ax.derived_series[0]["sources"] = [ref]
        with pytest.warns(UserWarning, match="was not drawn"):
            assert "let" not in self._script()

    def test_a_source_replaced_by_another_kind_leaves_the_curve_out(self):
        ax = self.ax
        ax.line_from_file("a.dat", 1, 2)
        ax.derived("d1+1", [ax.file_series[0]])
        ax.file_series[0]["series_type"] = "errorbar"
        ax.file_series[0]["color"] = "BLUE"
        with pytest.warns(UserWarning, match="was not drawn"):
            assert "let" not in self._script()

    def test_references_survive_a_project_round_trip(self):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.function("x")
        ax.derived("d1-d2", [ax.functions[0], ax.lines[0]], range=ax.lines[0])
        restored = glp.Figure.from_dict(self.fig.to_dict())
        [entry] = restored.axes_list[0].derived_series
        assert entry["sources"] == [["functions", 0], ["lines", 0]]
        assert entry["let_range"] == [["lines", 0]]
        assert restored._generate_gle() == self._script()

    @pytest.mark.parametrize(
        "kwargs, error, message",
        [
            ({"expression": "d1 - d2"}, ValueError, "first space"),
            ({"expression": "d1,d2"}, ValueError, "second expression"),
            ({"expression": 3}, TypeError, "expression must be a str"),
            ({"expression": "d3"}, ValueError, "names d3, but sources holds 2"),
            ({"expression": "d0+d1+d2"}, ValueError, "names d0"),
            ({"expression": "d1"}, ValueError, r"never uses sources\[1\]"),
            ({"expression": "d1", "where": "d2>0"}, None, None),
            ({"where": "d1 > 0"}, ValueError, r"where 'd1 > 0' cannot be used"),
            ({"nsteps": 1}, ValueError, "nsteps must be 2 or more"),
            ({"nsteps": 2.5}, TypeError, "nsteps must be an int"),
            ({"nsteps": True}, TypeError, "nsteps must be an int"),
            ({"nsteps": 5, "step": 0.1}, ValueError, "step or nsteps, not both"),
            ({"xmin": 2, "xmax": 1}, ValueError, "xmin < xmax"),
            ({"linestyle": "steps"}, ValueError, "linestyle must be"),
            ({"range": "d1"}, TypeError, "range must be a series"),
            ({"range": []}, TypeError, "range must be a series"),
        ],
    )
    def test_checks_its_arguments_when_called(self, kwargs, error, message):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.plot([0, 1], [1, 2])
        args = {"expression": "d1-d2", "sources": [ax.lines[0], ax.lines[1]]}
        args.update(kwargs)
        if error is None:
            ax.derived(**args)
            assert len(ax.derived_series) == 1
            return
        with pytest.raises(error, match=message):
            ax.derived(**args)
        assert ax.derived_series == []

    def test_accepts_only_one_dataset_series_of_this_axes(self):
        ax = self.ax
        ax.plot([0, 1], [0, 1])
        ax.bar([0, 1], [1, 2])
        ax.errorbar_from_file("e.dat", 1, 2, yerr_col=3, color="red")
        other = self.fig.add_subplot(212)
        other.plot([0, 1], [0, 1])
        with pytest.raises(ValueError, match="got a BarSeries"):
            ax.derived("d1", [ax.bars[0]])
        with pytest.raises(ValueError, match="got a FileSeries"):
            ax.derived("d1", [ax.file_series[0]])
        with pytest.raises(ValueError, match="got a LineSeries"):
            ax.derived("d1", [other.lines[0]])
        with pytest.raises(TypeError, match="got ndarray"):
            ax.derived("d1", [np.array([0, 1])])
        with pytest.raises(TypeError, match="got NoneType"):
            ax.derived("d1", None)
        with pytest.raises(ValueError, match=r"ax.lines\[0\] twice"):
            ax.derived("d1-d2", [ax.lines[0], ax.lines[0]])
        assert ax.derived_series == []

    def test_reads_at_most_ten_datasets(self):
        ax = self.ax
        for k in range(11):
            ax.plot([0, 1], [k, k])
        expression = "+".join(f"d{k}" for k in range(1, 12))
        with pytest.raises(ValueError, match="at most 10 datasets"):
            ax.derived(expression, ax.lines)
        ax.derived(expression.rsplit("+", 1)[0], ax.lines[:10])

    def test_widens_the_x_range_like_a_function(self):
        ax = self.ax
        ax.plot([1, 2], [1, 2])
        ax.derived("d1*2", [ax.lines[0]], xmin=0, xmax=5)
        assert "xaxis min 0 max 5" in self._script()


def test_add_line_writes_every_field():
    from gleplot.series import LineSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_line(
        LineSeries(
            x=[0, 1, 2],
            y=[1, 2, 3],
            data_file="k.dat",
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
    )
    writer.add_line(
        LineSeries(
            x=[0, 1, 2],
            y=[1, 2, 3],
            data_file="s.dat",
            color="BLUE",
            linestyle="-",
            linewidth=1.0,
            label=None,
            line_mode="steps",
        )
    )
    assert writer.lines_gle == [
        "    data k.dat d1=c1,c2",
        "    let d2 = d1+1.5",
        "    d2 line svg_smooth 2 smoothm nomiss color RED lwidth 0.07056 lstyle 3"
        ' marker FCIRCLE msize 0.2 x2axis y2axis key "k"',
        "    data s.dat d3=c1,c2",
        "    d3 line steps color BLUE lwidth 0.05292",
    ]


def test_add_errorbar_series_writes_every_field():
    from gleplot.series import ErrorbarSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_errorbar_series(
        ErrorbarSeries(
            x=[0, 1, 2],
            y=[1, 2, 3],
            data_file="e.dat",
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
            gle_capsize=0.25,
            yaxis="y2",
            xaxis="x2",
            offset=2.0,
            column_names=["x", "e", "up", "down", "xe"],
        )
    )
    assert writer.lines_gle == [
        "    data e.dat d1=c1,c2 d2=c1,c3 d3=c1,c4 d4=c1,c5",
        "    let d5 = d1+2",
        "    d5 marker FSQUARE msize 0.2 color RED line lwidth 0.07056 lstyle 2"
        " errup d2 errdown d3 errwidth 0.25 herr d4 herrwidth 0.25"
        ' x2axis y2axis key "e"',
    ]
    assert writer.data_files["e.dat"].splitlines()[0] == "x e up down xe"


def test_add_bar_writes_every_field():
    from gleplot.series import BarSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_bar(
        BarSeries(
            x=[1, 2],
            height=[5, 3],
            data_file="a.dat",
            colors=["RED", "RED"],
            label="a",
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
    )
    writer.add_bar(
        BarSeries(
            x=[1, 2],
            height=[1, 1],
            data_file="b.dat",
            colors=["WHITE"],
            label=None,
            bottom=[5, 3],
            top=[6, 4],
            lstyle="9",
        )
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


def test_add_fill_writes_every_field():
    from gleplot.series import FillSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_fill(
        FillSeries(
            x=[0, 1],
            y1=[2, 3],
            y2=[1, 1],
            data_file="a.dat",
            color="GREEN",
            alpha=1.0,
            offset=0.5,
            column_names=["x", "u", "l"],
            label="a",
            swatch_color="BLACK",
            xmin=0.2,
            xmax=0.8,
        )
    )
    writer.add_fill(
        FillSeries(
            x=[0, 1],
            y1=[1, 2],
            y2=None,
            data_file="b.dat",
            color="ORANGE",
            alpha=0.5,
            target="x1",
            ymin=0.5,
            ymax=2.5,
        )
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


def test_add_hist_writes_every_field():
    from gleplot.series import HistSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_hist(
        HistSeries(
            samples=[0.1, 0.6],
            data_file="a.dat",
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
    )
    writer.add_hist(
        HistSeries(
            samples=[0.1, 0.6],
            data_file="b.dat",
            histtype="stepfilled",
            color="RED",
            label="b",
            hist_from=0,
            hist_to=1,
            bin_step=0.5,
            edgecolor="BLACK",
            bar_width=0.5,
        )
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


def test_add_file_series_writes_every_field_of_each_variant():
    from gleplot.series import FileSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    for series in (
        FileSeries(
            series_type="line",
            data_file="a.dat",
            x_col=1,
            y_col=2,
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
        ),
        FileSeries(
            series_type="errorbar",
            data_file="a.dat",
            x_col=1,
            y_col=2,
            yerr_col=3,
            color="RED",
            marker="FSQUARE",
            markersize=0.3,
            label="err",
            capsize=0.1,
            yaxis="y2",
            xaxis="x2",
        ),
        FileSeries(
            series_type="bar",
            data_file="a.dat",
            x_col=1,
            y_col=4,
            color="ORANGE",
            label="bar",
            swatch_color="BLACK",
        ),
        FileSeries(
            series_type="fill",
            data_file="a.dat",
            x_col=1,
            y1_col=2,
            y2_col=3,
            color="GRAY10",
            label="band",
            swatch_color="GRAY20",
            xmin=0.5,
            xmax=1.5,
            ymin=0,
            ymax=2,
        ),
        FileSeries(
            series_type="fill",
            data_file="a.dat",
            x_col=1,
            y1_col=2,
            color="BLUE",
            target="x2",
        ),
    ):
        writer.add_file_series(series)
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


def test_a_two_curve_file_fill_without_its_second_column_raises():
    """No ``y2_col`` and no ``target`` would write ``c None`` into the data line."""
    from gleplot.series import FileSeries
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    fill = FileSeries(series_type="fill", data_file="a.dat", x_col=1, y1_col=2)
    with pytest.raises(ValueError, match="needs y2_col .* or target"):
        writer.add_file_series(fill)
    fill.update(target="X1", y2_col=3)
    with pytest.raises(ValueError, match="target must be .* got target='X1'"):
        writer.add_file_series(fill)
    assert writer.lines_gle == []


def test_add_text_annotation_writes_every_field():
    from gleplot.series import TextAnnotation
    from gleplot.writer import GLEWriter

    writer = GLEWriter()
    writer.add_text_annotation(
        TextAnnotation(
            x=1,
            y=2,
            text="plain",
            color="RED",
            fontsize=14,
            ha="right",
            va="top",
            box_color="YELLOW",
            rotation=30,
        )
    )
    writer.add_text_annotation(
        TextAnnotation(
            x=3,
            y=4,
            text="arrow",
            xy=[5, 6],
            arrow="->",
            arrowstyle="filled",
            arrow_color="BLUE",
            arrow_linewidth=2,
        )
    )
    writer.end_graph()
    assert writer.lines_gle == [
        "end graph",
        "gsave",
        "set hei 0.493827",
        "set color RED",
        "set just tr",
        "amove xg(1) yg(2)",
        "begin rotate 30",
        "begin box fill YELLOW add 0.05 nobox",
        'write "plain"',
        "end box",
        "end rotate",
        "set color BLACK",
        "set just left",
        "amove xg(3) yg(4)",
        "begin box add 0.05 nobox name ann1",
        'write "arrow"',
        "end box",
        "amove xg(5) yg(6)",
        "save ann1_xy",
        "gsave",
        "set color BLUE",
        "set lwidth 0.07056",
        "set arrowstyle filled",
        "join ann1 -> ann1_xy",
        "grestore",
        "grestore",
    ]


@pytest.mark.parametrize(
    "draw",
    [
        lambda ax, **kw: ax.plot([0, 1], [0, 1], **kw),
        lambda ax, **kw: ax.errorbar([0, 1], [0, 1], yerr=[1, 1], **kw),
        lambda ax, **kw: ax.line_from_file("f.dat", 1, 2, **kw),
        lambda ax, **kw: ax.axhline(0.5, **kw),
        lambda ax, **kw: ax.axvline(0.5, **kw),
    ],
    ids=["plot", "errorbar", "line_from_file", "axhline", "axvline"],
)
def test_linewidth_none_means_the_default_width(draw):
    """matplotlib reads ``linewidth=None`` as the default width."""

    def script(**kw):
        glp.close()
        fig = glp.figure(data_prefix="lw")
        draw(fig.add_subplot(111), **kw)
        return fig._generate_gle_with_files()[0]

    assert script(linewidth=None) == script()


_LINE_WIDTH_CALLS = [
    ("plot", lambda ax, **kw: ax.plot([0, 1], [0, 1], **kw)),
    ("errorbar", lambda ax, **kw: ax.errorbar([0, 1], [0, 1], yerr=[1, 1], **kw)),
    ("line_from_file", lambda ax, **kw: ax.line_from_file("f.dat", 1, 2, **kw)),
    ("axhline", lambda ax, **kw: ax.axhline(0.5, **kw)),
]


@pytest.mark.parametrize("name, draw", _LINE_WIDTH_CALLS)
def test_a_linewidth_that_is_not_a_number_raises(name, draw):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(TypeError, match=rf"{name}\(\) linewidth .*'thick'"):
        draw(ax, linewidth="thick")


@pytest.mark.parametrize("name, draw", _LINE_WIDTH_CALLS)
@pytest.mark.parametrize("width", [float("nan"), float("inf"), -3])
def test_a_non_finite_or_negative_linewidth_raises(name, draw, width):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=rf"{name}\(\) linewidth must be"):
        draw(ax, linewidth=width)


@pytest.mark.parametrize(
    "name, draw",
    [
        ("vlines", lambda ax: ax.vlines([0.5], 0, 1, linewidths=-2)),
        ("hist", lambda ax: ax.hist([1.0, 2.0], histtype="step", linewidth=-2)),
        ("function", lambda ax: ax.function("x", 0, 1, linewidth=float("nan"))),
    ],
)
def test_other_line_calls_reject_a_bad_linewidth_by_their_own_name(name, draw):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=rf"{name}\(\) linewidth must be"):
        draw(ax)


@pytest.mark.parametrize(
    "draw, error, shown",
    [
        (lambda ax: ax.axhline(float("nan")), ValueError, "axhline(y=...) must be"),
        (lambda ax: ax.axvline(float("inf")), ValueError, "axvline(x=...) must be"),
        (lambda ax: ax.axvline("mid"), TypeError, "axvline(x=...) must be a number"),
        (lambda ax: ax.axvspan(float("nan"), 1), ValueError, "axvspan(xmin=...)"),
        (lambda ax: ax.axhspan(0, float("inf")), ValueError, "axhspan(ymax=...)"),
    ],
)
def test_a_reference_line_position_must_be_a_finite_number(draw, error, shown):
    ax = glp.figure().add_subplot(111)
    with pytest.raises(error, match=re.escape(shown)):
        draw(ax)
    assert ax.reflines == [] and ax.spans == []


@pytest.mark.parametrize(
    "draw, shown",
    [
        (lambda bax: bax.axhline(float("nan")), "axhline(y=...)"),
        (lambda bax: bax.axhspan(0, float("nan")), "axhspan(ymax=...)"),
    ],
)
def test_a_broken_y_axis_guide_position_must_be_a_finite_number(draw, shown):
    fig = glp.figure()
    bax = fig.add_broken_yaxes(ylims=[(0, 1), (2, 3)])
    with pytest.raises(ValueError, match=re.escape(shown)):
        draw(bax)


@pytest.mark.parametrize("no_line", ["none", "None", "", " "])
def test_line_from_file_without_a_line_writes_no_line_token(no_line, tmp_path):
    fig = glp.figure(data_prefix="lf")
    ax = fig.add_subplot(111)
    ax.line_from_file("f.dat", 1, 2, color="red", linestyle=no_line)
    out = tmp_path / "fig.gle"
    fig.savefig(str(out))
    assert "    d1 color RED lwidth 0.05292" in out.read_text().splitlines()


@pytest.mark.parametrize(
    "draw",
    [
        lambda ax, **kw: ax.plot([0, 1], [0, 1], **kw),
        lambda ax, **kw: ax.plot([0, 1], [0, 1], marker="o", **kw),
        lambda ax, **kw: ax.errorbar([0, 1], [0, 1], yerr=[1, 1], **kw),
        lambda ax, **kw: ax.line_from_file("f.dat", 1, 2, **kw),
        lambda ax, **kw: ax.axhline(0.5, **kw),
        lambda ax, **kw: ax.axvline(0.5, **kw),
        lambda ax, **kw: ax.step([0, 1, 2], [0, 1, 0], marker="o", **kw),
        lambda ax, **kw: ax.line_from_file("f.dat", 1, 2, drawstyle="steps", **kw),
    ],
    ids=[
        "plot",
        "plot-marker",
        "errorbar",
        "line_from_file",
        "axhline",
        "axvline",
        "step",
        "line_from_file-steps",
    ],
)
def test_linewidth_zero_draws_no_line(draw, tmp_path, recwarn):
    """matplotlib's ``lw=0`` draws no stroke, the same as ``linestyle='none'``,
    and says nothing about a line mode it drops with the line."""

    def script(**kw):
        glp.close()
        fig = glp.figure(data_prefix="lw")
        draw(fig.add_subplot(111), **kw)
        out = tmp_path / "fig.gle"
        fig.savefig(str(out))
        return out.read_text()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        no_line = script(linestyle="none")
    recwarn.clear()
    assert script(linewidth=0) == no_line
    assert not recwarn.list
    assert script(linewidth=0) != script()


def test_segments_with_linewidth_zero_are_left_out():
    ax = glp.figure(data_prefix="lw").add_subplot(111)
    ax.hlines([0.5, 1], 0, 1, linewidths=[0, 2])
    ax.vlines([0.5], 0, 1, linewidths=0)
    assert [s["linewidth"] for s in ax.lines] == [2.0]


@pytest.mark.parametrize(
    "name, draw",
    [
        ("function", lambda ax: ax.function("x", 0, 1, linewidth=0)),
        ("hist", lambda ax: ax.hist([1.0, 2.0], histtype="step", linewidth=0)),
    ],
)
def test_a_curve_that_is_only_its_line_warns_on_linewidth_zero(name, draw):
    ax = glp.figure().add_subplot(111)
    with pytest.warns(UserWarning, match=rf"{name}\(\) cannot leave out"):
        draw(ax)


def _saved(fig, tmp_path):
    """The saved script and its sidecars, by file name."""
    out = tmp_path / "fig.gle"
    fig.savefig(str(out))
    return {p.name: p.read_text() for p in tmp_path.iterdir() if p.is_file()}


def test_values_six_figures_would_merge_are_written_apart(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    stamps = [1.7e9, 1.7e9 + 60, 1.7e9 + 121]
    ax.plot(stamps, [1.0, 2.0, 3.0])
    ax.set_xlim(stamps[0], stamps[-1])
    files = _saved(fig, tmp_path)
    assert files["p_0.dat"] == "x y\n1700000000 1\n1700000060 2\n1700000121 3\n"
    assert "xaxis min 1700000000 max 1700000121" in files["fig.gle"]


def test_small_and_large_values_keep_their_figures(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([1.23456789e12, 2.5e12], [1e-12, 2e-12])
    assert (
        _saved(fig, tmp_path)["p_0.dat"] == "x y\n1.234568e+12 1e-12\n2.5e+12 2e-12\n"
    )


def test_float_noise_and_faithful_columns_keep_six_figures(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([0.1, 0.123456789, 2.5e10], np.cos([0.0, np.pi / 2, np.pi]))
    ax.plot([1.0, 1.0 - 1e-16], [2.0, 3.0])
    # Samples near a peak differ by far less than the curve's height.
    ax.plot(np.linspace(0, 10, 20000), np.sin(np.linspace(0, 10, 20000)))
    files = _saved(fig, tmp_path)
    assert files["p_0.dat"] == "x y\n0.1 1\n0.123457 0\n2.500e+10 -1\n"
    assert files["p_1.dat"] == "x y\n1 2\n1 3\n"
    rows = [line.split() for line in files["p_2.dat"].splitlines()[1:]]
    digits = (y.split("e")[0].lstrip("-").replace(".", "").lstrip("0") for _, y in rows)
    assert max(len(d) for d in digits) <= 6


def test_a_heatmap_grid_keeps_values_six_figures_would_merge(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.imshow(1.0 + 1e-8 * np.arange(4.0).reshape(2, 2), extent=(0, 2, 0, 2))
    grid = next(v for k, v in _saved(fig, tmp_path).items() if k.endswith(".z"))
    assert grid.splitlines()[2:] == ["1 1.00000001", "1.00000002 1.00000003"]


def test_raised_columns_zero_nothing_six_figures_kept(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0, 2.0, 3.0], [0.001, 0.002, 1e5, 1e5 + 0.3])
    assert _saved(fig, tmp_path)["p_0.dat"].splitlines()[1:] == [
        "0 0.001",
        "1 0.002",
        "2 100000",
        "3 100000.3",
    ]


def test_a_log_limit_below_1e10_is_not_written_zero(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1e-11, 1.0])
    ax.set_yscale("log")
    ax.set_ylim(1e-12, 1.0)
    assert "yaxis min 1e-12 max 1 log" in _saved(fig, tmp_path)["fig.gle"]


def test_a_timestamp_heatmap_extent_keeps_its_width(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.imshow(np.arange(6.0).reshape(2, 3), extent=(1.7e9, 1.7e9 + 60, 0, 1))
    grid = next(v for k, v in _saved(fig, tmp_path).items() if k.endswith(".z"))
    header, marker = grid.splitlines()[:2]
    assert header.startswith("! nx 3 ny 2 xmin 1700000000 xmax 1700000090 ymin 0")
    assert marker.startswith("! gleplot: nodes xmin 1.7e+09 xmax 1.70000006e+09")


def test_coordinates_on_a_timestamp_axis_keep_their_figures(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([1.7e9, 1.7e9 + 120], [1.0, 3.0])
    ax.axvline(1.7e9 + 30)
    ax.text(1.7e9 + 90, 2.0, "t")
    ax.set_xticks([1.7e9 + 30])
    files = _saved(fig, tmp_path)
    script = files["fig.gle"]
    assert "xplaces 1.70000003e+09" in script
    assert "refline v value 1.70000003e+09" in script
    assert "amove xg(1.70000009e+09) yg(2)" in script
    assert "x y\n1.70000003e+09 1\n1.70000003e+09 3\n" in files.values()


def test_a_one_sided_limit_is_held_to_the_data_it_bounds(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([1.0, 2.0], [1.7e9, 1.7e9 + 120], yaxis="y2")
    ax.set_ylim(1.7e9 + 30, None, axis="y2")
    assert "y2axis min 1.70000003e+09" in _saved(fig, tmp_path)["fig.gle"]


def test_coordinates_on_a_log_axis_keep_six_figures(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([1e11, 1e13], [1.0, 2.0])
    ax.set_xscale("log")
    ax.axvline(3.1415926535e12)
    ax.text(2.718281828e11, 1.5, "t")
    script = _saved(fig, tmp_path)["fig.gle"]
    assert "refline v value 3.142e+12" in script
    assert "amove xg(2.718e+11) yg(1.5)" in script


def test_coordinates_six_figures_keep_are_unchanged(tmp_path):
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.axvline(1 / 3)
    ax.text(2 / 3, 1 / 7, "t")
    files = _saved(fig, tmp_path)
    assert "amove xg(0.666667) yg(0.142857)" in files["fig.gle"]
    assert "refline v value 0.333333" in files["fig.gle"]


_MASKED = np.ma.masked_array([1.0, 77.0, 3.0], mask=[False, True, False])
_NAN = np.array([1.0, np.nan, 3.0])
_ONES = [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    "draw",
    [
        lambda ax, v: ax.plot(_ONES, v),
        lambda ax, v: ax.plot(v, _ONES),
        lambda ax, v: ax.step(_ONES, v),
        lambda ax, v: ax.stem(_ONES, v),
        lambda ax, v: ax.scatter(_ONES, v),
        lambda ax, v: ax.scatter(_ONES, _ONES, c=v),
        lambda ax, v: ax.bar(_ONES, v),
        lambda ax, v: ax.barh(_ONES, v),
        lambda ax, v: ax.errorbar(_ONES, v, yerr=0.1),
        lambda ax, v: ax.errorbar(_ONES, _ONES, xerr=v, yerr=v),
        lambda ax, v: ax.errorbar(_ONES, _ONES, yerr=[v, v]),
        lambda ax, v: ax.fill_between(_ONES, v),
        lambda ax, v: ax.fill_betweenx(_ONES, v),
        lambda ax, v: ax.hist(v),
        lambda ax, v: ax.hist(np.ma.column_stack([v, v])),
        lambda ax, v: ax.vlines(v, 0, 1),
        lambda ax, v: ax.hlines(_ONES, 0, v),
    ],
    ids=[
        "plot-y",
        "plot-x",
        "step",
        "stem",
        "scatter",
        "scatter-c",
        "bar",
        "barh",
        "errorbar",
        "errorbar-err",
        "errorbar-asymmetric",
        "fill_between",
        "fill_betweenx",
        "hist",
        "hist-2d",
        "vlines",
        "hlines",
    ],
)
def test_a_masked_value_is_a_nan(draw):
    """matplotlib leaves a masked point out where it leaves a NaN out (#318)."""
    emitted = []
    for values in (_MASKED, _NAN):
        glp.close()
        fig = glp.figure(data_prefix="p")
        draw(fig.add_subplot(111), values)
        emitted.append(fig._generate_gle_with_files())
    glp.close()
    assert emitted[0] == emitted[1]
    text, files = emitted[0]
    assert "max 77" not in text
    assert not any("77" in sidecar for sidecar in files.values())


def test_fill_draws_the_value_under_the_mask_as_matplotlib_does():
    fig = glp.figure(data_prefix="p")
    fig.add_subplot(111).fill(_ONES, _MASKED)
    _text, files = fig._generate_gle_with_files()
    glp.close()
    assert "2 77" in "".join(files.values())


def test_an_unmasked_or_non_numeric_masked_array_is_left_as_it_is():
    """No mask leaves integers whole; colour names are not numbers."""
    stamps = np.ma.masked_array([1700000000, 1700000031, 1700000060])
    fig = glp.figure(data_prefix="p")
    ax = fig.add_subplot(111)
    ax.plot(stamps, _ONES)
    ax.scatter(_ONES, _ONES, c=np.ma.masked_array(["r", "g", "b"], mask=[0, 1, 0]))
    _text, files = fig._generate_gle_with_files()
    glp.close()
    assert "1700000031 2" in "".join(files.values())


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"s": [10, 20, 30]}, {"c": [1, np.nan, 3]}, {"c": ["r", "g", "b"]}],
    ids=["plain", "sizes", "nan-colour", "colour-names"],
)
def test_scatter_x_and_y_of_different_sizes_are_rejected_at_the_call(kwargs):
    """As in matplotlib, not a numpy error later at save (#458)."""
    ax = glp.figure().add_subplot(111)
    with pytest.raises(ValueError, match=r"x and y must be the same size, got 3 x"):
        ax.scatter([1, 2, 3], [1, 2], **kwargs)
    assert not ax.scatters
    glp.close()

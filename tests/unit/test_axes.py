"""Unit tests for axis properties."""

import json
import re

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure


class TestAxisProperties:
    """Test axis property setting."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_axis_labels(self):
        """Test setting axis labels."""
        self.ax.set_xlabel("X axis")
        self.ax.set_ylabel("Y axis")
        self.ax.set_title("Test Plot")

        assert self.ax.xlabel_text == "X axis"
        assert self.ax.ylabel_text == "Y axis"
        assert self.ax.title_text == "Test Plot"

    def test_axis_limits(self):
        """Test setting axis limits."""
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(0, 100)

        assert self.ax.xmin == 0
        assert self.ax.xmax == 10
        assert self.ax.ymin == 0
        assert self.ax.ymax == 100

    def test_axis_limits_take_matplotlib_keywords(self):
        """left/right, bottom/top, a (lo, hi) pair, and xmin/xmax aliases."""
        ax = self.ax
        ax.set_xlim(left=1, right=9)
        ax.set_xlim(right=5)  # an omitted limit is kept
        assert ax.get_xlim() == (1, 5)
        ax.set_xlim(xmax=None)  # None is still auto
        assert (ax.xmin, ax.xmax) == (1, None)
        ax.set_ylim((2, 8))
        ax.set_ylim(bottom=0)
        assert (ax.ymin, ax.ymax) == (0, 8)
        ax.set_ylim(top=4, axis="y2")
        ax.twinx().set_ylim(bottom=-1)
        assert (ax.y2min, ax.y2max) == (-1, 4)
        ax.twiny().set_xlim(left=3)
        assert (ax.x2min, ax.x2max) == (3, None)
        assert "xaxis min 1" in self.fig._generate_gle()

    def test_axis_limits_follow_matplotlib_on_none(self):
        """A pair with right=None unpacks; a None gives way to its alias."""
        self.ax.set_xlim((2, 3), None)
        assert self.ax.get_xlim() == (2, 3)
        self.ax.set_xlim(left=None, xmin=1)
        assert self.ax.get_xlim() == (1, 3)
        self.ax.set_ylim(4, ymin=None)
        assert self.ax.ymin == 4

    def test_axis_limits_store_numpy_scalars_as_python_numbers(self):
        self.ax.set_xlim(np.int64(1), np.array(2.5))
        assert self.ax.get_xlim() == (1, 2.5)
        assert [type(v) for v in self.ax.get_xlim()] == [int, float]
        with pytest.raises(ValueError, match=r"set_xlim\(xmax=nan\)"):
            self.ax.set_xlim(xmax=np.float64("nan"))

    def test_axis_limits_return_the_new_limits(self):
        """As matplotlib: (low, high), with None for an automatic limit."""
        assert self.ax.set_xlim(1, 2) == (1, 2)
        assert self.ax.set_xlim(right=None) == (1, None)
        assert self.ax.set_ylim(top=5, axis="y2") == (None, 5)
        assert self.ax.twiny().set_xlim(3, 4) == (3, 4)

    def test_axis_limits_reject_a_limit_and_its_alias(self):
        with pytest.raises(TypeError, match=r"'left' \(0\) and 'xmin' \(1\)"):
            self.ax.set_xlim(0, xmin=1)
        with pytest.raises(TypeError, match="'top' .* and 'ymax'"):
            self.ax.set_ylim(top=1, ymax=2)
        with pytest.raises(ValueError, match="two entries"):
            self.ax.set_xlim((0, 1, 2))

    @pytest.mark.parametrize(
        "call, error",
        [
            (lambda ax: ax.set_xlim(0, 1, "y"), ValueError),
            (lambda ax: ax.set_ylim(0, 1, "x2"), ValueError),
            (lambda ax: ax.set_xlim(0, float("nan")), ValueError),
            (lambda ax: ax.set_ylim(bottom=float("inf")), ValueError),
            (lambda ax: ax.set_xlim("0", 1), TypeError),
            (lambda ax: ax.set_xlim("05"), TypeError),
            (lambda ax: ax.set_xlim(True, 2), TypeError),
            (lambda ax: ax.set_xlim(np.array([1.0]), 2), TypeError),
        ],
    )
    def test_axis_limits_reject_a_bad_axis_or_limit(self, call, error):
        with pytest.raises(error, match=r"set_[xy]lim\("):
            call(self.ax)
        assert self.ax.get_xlim() == (None, None)
        assert self.ax.get_ylim() == (None, None)

    def test_axis_limits_warn_on_emit_and_auto(self):
        with pytest.warns(UserWarning, match="ignores unsupported keyword.*auto"):
            self.ax.set_xlim(0, 1, auto=True)
        with pytest.warns(UserWarning, match="emit"):
            self.ax.set_ylim(0, 1, emit=False)

    def test_axis_scales(self):
        """Test setting axis scales."""
        self.ax.set_xscale("log")
        self.ax.set_yscale("log")

        assert self.ax.xscale == "log"
        assert self.ax.yscale == "log"

    def test_legend(self):
        """Test adding legend."""
        self.ax.legend(loc="upper left")

        assert self.ax.legend_on
        assert self.ax.legend_pos == "top left"


class TestSubplots:
    """Test subplot (multi-graph) functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        yield
        glp.close()

    @staticmethod
    def _extract_amove_points(gle):
        """Return all amove coordinates as (x, y) float tuples."""
        return [
            (float(x), float(y))
            for x, y in re.findall(
                r"^amove\s+([0-9.]+)\s+([0-9.]+)$", gle, re.MULTILINE
            )
        ]

    @staticmethod
    def _extract_sizes(gle):
        """Return all graph size commands as (width, height) float tuples."""
        return [
            (float(w), float(h))
            for w, h in re.findall(
                r"^\s*size\s+([0-9.]+)\s+([0-9.]+)$", gle, re.MULTILINE
            )
        ]

    def test_add_subplot_three_args(self):
        """Test add_subplot with three separate arguments."""
        fig = glp.figure()
        ax = fig.add_subplot(2, 3, 4)

        assert ax.position == (2, 3, 4)
        assert len(fig.axes_list) == 1

    def test_figure_axes_lists_axes_in_order_as_a_copy(self):
        """fig.axes is matplotlib's list of axes, a new list on each access."""
        fig, (ax1, ax2) = glp.subplots(1, 2)
        inset = fig.add_axes([0.6, 0.6, 0.3, 0.3])
        ax1.twinx()

        axes = fig.axes
        assert axes == [ax1, ax2, inset]
        axes.clear()
        assert fig.axes == [ax1, ax2, inset]
        with pytest.raises(AttributeError):
            fig.axes = []
        assert glp.figure().axes == []

        broken = glp.figure()
        bax = broken.add_broken_xaxes([(0, 1), (5, 6)])
        assert broken.axes == list(bax.segments)

    def test_add_subplot_shorthand(self):
        """Test add_subplot with single int shorthand (e.g., 221)."""
        fig = glp.figure()
        ax = fig.add_subplot(221)

        assert ax.position == (2, 2, 1)

    def test_multiple_subplots(self):
        """Test creating multiple subplots."""
        fig = glp.figure()
        fig.add_subplot(2, 2, 1)
        fig.add_subplot(2, 2, 2)
        fig.add_subplot(2, 2, 3)
        ax4 = fig.add_subplot(2, 2, 4)

        assert len(fig.axes_list) == 4
        # Current axes should be the last one added
        assert fig._current_axes is ax4

    def test_subplots_function_single(self):
        """Test subplots() convenience function for single plot."""
        fig, ax = glp.subplots()

        assert isinstance(fig, glp.Figure)
        assert isinstance(ax, glp.Axes)
        assert len(fig.axes_list) == 1

    def test_subplots_function_grid(self):
        """Test subplots() convenience function for grid."""
        fig, axes = glp.subplots(2, 3)

        assert isinstance(axes, np.ndarray)
        assert axes.shape == (2, 3)
        assert list(axes.flat) == fig.axes_list
        assert axes[1, 2] is fig.axes_list[5]
        assert fig.figsize == (18, 8)  # 6*3, 4*2

    def test_subplots_squeeze(self):
        """A single row or column squeezes to 1-D; squeeze=False keeps 2-D."""
        _, row = glp.subplots(1, 3)
        _, col = glp.subplots(3, 1)
        assert row.shape == (3,) and col.shape == (3,)
        _, lone = glp.subplots(squeeze=False)
        assert lone.shape == (1, 1) and isinstance(lone[0, 0], glp.Axes)
        _, grid = glp.subplots(1, 3, squeeze=False)
        assert grid.shape == (1, 3)

    def test_subplots_takes_only_the_grid_positionally(self):
        """matplotlib's order: everything after ncols is keyword-only."""
        with pytest.raises(TypeError):
            glp.subplots(2, 2, (8, 6))
        fig, axes = glp.subplots(
            2,
            3,
            sharex=True,
            sharey=True,
            squeeze=False,
            width_ratios=[1, 2, 3],
            height_ratios=[4, 5],
            figsize=(8, 6),
        )
        assert fig.figsize == (8, 6) and axes.shape == (2, 3)
        assert fig.sharex and fig.sharey
        assert list(fig.width_ratios) == [1, 2, 3]
        assert list(fig.height_ratios) == [4, 5]

    @pytest.mark.parametrize(
        "value, stored",
        [
            (True, True),
            (False, False),
            ("all", True),
            ("none", False),
            ("row", "row"),
            ("col", "col"),
        ],
    )
    def test_subplots_share_takes_matplotlib_strings(self, value, stored):
        fig, _ = glp.subplots(2, 2, sharex=value, sharey=value)
        assert (fig.sharex, fig.sharey) == (stored, stored)
        assert Figure.from_dict(fig.to_dict()).sharex == stored

    @pytest.mark.parametrize("value", [1, "yes", None])
    def test_subplots_share_rejects_other_values(self, value):
        with pytest.raises(ValueError, match="sharex="):
            glp.subplots(2, 2, sharex=value)
        fig = glp.figure()
        fig.sharex = "all"
        assert fig.sharex is True
        with pytest.raises(ValueError, match="sharex="):
            fig.sharex = value

    def test_a_panel_spanning_columns_keeps_its_x_labels_with_sharex_col(self):
        fig = Figure(sharex="col")
        top = fig.add_subplot(2, 2, (1, 2))
        left = fig.add_subplot(2, 2, 3)
        fig.add_subplot(2, 2, 4)
        assert top._show_xticks and left._show_xticks
        assert not Figure(sharex="col").add_subplot(2, 2, 1)._show_xticks

    def test_subplots_sharex_row_keeps_labels_and_shares_each_row(self):
        fig, axes = glp.subplots(2, 2, sharex="row")
        axes[0, 0].plot([0, 1], [0, 1])
        axes[0, 1].plot([5, 9], [0, 1])
        axes[1, 0].plot([20, 30], [0, 1])
        axes[1, 1].plot([20, 21], [0, 1])
        gle = fig._generate_gle()
        assert "xlabels off" not in gle
        assert gle.count("xaxis min 0 max 9") == 2
        assert gle.count("xaxis min 20 max 30") == 2

    def test_subplots_passes_matplotlib_subplot_and_gridspec_keywords(self):
        fig, axes = glp.subplots(
            1,
            2,
            subplot_kw={"projection": "polar"},
            gridspec_kw={"width_ratios": [1, 2], "wspace": 0.3, "left": 0.2},
        )
        assert all(ax._polar for ax in axes)
        assert list(fig.width_ratios) == [1, 2]
        assert fig._subplot_adjust["wspace"] == 0.3
        assert fig._subplot_adjust["left"] == 0.2
        _, grid = glp.subplots(squeeze=False, subplot_kw={"polar": True})
        assert grid[0, 0]._polar

    def test_subplots_warns_on_what_it_cannot_use(self):
        with pytest.warns(UserWarning) as record:
            glp.subplots(
                1, 2, num=3, layout="constrained", gridspec_kw={"figure": None}
            )
        (message,) = [str(w.message) for w in record]
        for name in ("num", "layout", "gridspec_kw['figure']"):
            assert name in message
        with pytest.warns(UserWarning, match=r"add_subplot\(\) ignores alpha"):
            glp.subplots(subplot_kw={"alpha": 0.5, "facecolor": "red"})

    def test_subplots_checks_its_keywords_before_replacing_the_figure(self):
        current = glp.figure()
        for kwargs in (
            {"gridspec_kw": {"wspace": -1}},
            {"subplot_kw": {"polar": True, "projection": "rectilinear"}},
        ):
            with pytest.raises(ValueError, match=r"subplots\(gridspec_kw|polar=True"):
                glp.subplots(1, 2, **kwargs)
            assert glp.gcf() is current
        with pytest.raises(ValueError, match="height_ratios"):
            glp.subplots(2, height_ratios=[1, 2], gridspec_kw={"height_ratios": [1, 2]})

    def test_subplots_rejects_a_ratio_given_twice(self):
        with pytest.raises(ValueError, match="width_ratios"):
            glp.subplots(
                1, 2, width_ratios=[1, 2], gridspec_kw={"width_ratios": [1, 2]}
            )

    def test_subplots_array_is_row_major(self):
        """axes[row, col] is the panel add_subplot numbers row by row."""
        fig, axes = glp.subplots(3, 2)
        assert axes[2, 0] is fig.axes_list[4]
        assert axes[0, 1].position == (3, 2, 2)

    @pytest.mark.parametrize("kwargs", [{"nrows": 0}, {"ncols": -1}])
    def test_subplots_rejects_a_non_positive_grid(self, kwargs):
        name, value = next(iter(kwargs.items()))
        with pytest.raises(ValueError, match=rf"{name}={value}"):
            glp.subplots(**kwargs)

    @pytest.mark.parametrize("value", [2.0, "2", None])
    def test_subplots_rejects_a_non_int_grid(self, value):
        with pytest.raises(TypeError, match="nrows"):
            glp.subplots(nrows=value)

    def test_subplots_function_custom_figsize(self):
        """Test subplots() with custom figsize."""
        fig, axes = glp.subplots(2, 2, figsize=(10, 8))

        assert fig.figsize == (10, 8)
        assert axes.shape == (2, 2)

    def test_subplot_independent_axes(self):
        """Test that subplots have independent axis properties."""
        fig, axes = glp.subplots(1, 2)
        axes[0].set_title("Left")
        axes[0].set_xlabel("x1")
        axes[1].set_title("Right")
        axes[1].set_xlabel("x2")

        assert axes[0].title_text == "Left"
        assert axes[1].title_text == "Right"
        assert axes[0].xlabel_text == "x1"
        assert axes[1].xlabel_text == "x2"

    def test_subplot_independent_data(self):
        """Test that subplots hold independent data."""
        fig, axes = glp.subplots(1, 2)
        axes[0].plot([1, 2, 3], [1, 4, 9])
        axes[1].scatter([1, 2, 3], [3, 2, 1])

        assert len(axes[0].lines) == 1
        assert len(axes[0].scatters) == 0
        assert len(axes[1].lines) == 0
        assert len(axes[1].scatters) == 1

    def test_single_subplot_gle_is_explicitly_placed(self):
        """A single subplot is the 1x1 case: one placed graph block.

        Since metadata v2 the lone plot carries the same explicit frame
        rectangle every subplot does -- ``amove`` + ``size`` + ``scale 1 1``
        -- instead of leaving the layout to GLE's ``scale auto`` page fit.
        """
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9])

        gle = fig._generate_gle()
        assert gle.count("amove") == 1
        assert "scale auto" not in gle
        assert "    scale 1 1" in gle
        # Should have exactly one begin/end graph
        assert gle.count("begin graph") == 1
        assert gle.count("end graph") == 1

    def test_multi_subplot_gle_has_amove(self):
        """Test that multi-subplot generates amove positioning."""
        fig = glp.figure()
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.plot([1, 2, 3], [1, 4, 9])
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.scatter([1, 2, 3], [3, 2, 1])

        gle = fig._generate_gle()
        assert "amove" in gle
        assert gle.count("begin graph") == 2
        assert gle.count("end graph") == 2

    def test_2x2_subplot_gle_structure(self):
        """Test GLE structure of a 2x2 subplot grid."""
        fig = glp.figure(figsize=(12, 10))
        for i in range(1, 5):
            ax = fig.add_subplot(2, 2, i)
            ax.plot([1, 2, 3], [i, i * 2, i * 3])
            ax.set_title(f"Plot {i}")

        gle = fig._generate_gle()
        # Should have 4 graph blocks
        assert gle.count("begin graph") == 4
        assert gle.count("end graph") == 4
        # Each should have a title
        for i in range(1, 5):
            assert f'title "Plot {i}"' in gle
        # Should have explicit size for each subplot
        assert "size" in gle

    def test_subplots_adjust_changes_multiplot_geometry(self):
        """subplots_adjust should alter amove geometry in generated GLE."""
        fig, axes = glp.subplots(3, 1, figsize=(8, 9))
        for idx, ax in enumerate(axes):
            ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3])

        gle_default = fig._generate_gle()
        default_points = self._extract_amove_points(gle_default)
        assert len(default_points) == 3
        default_x = default_points[0][0]

        fig.subplots_adjust(left=0.2, right=0.98, bottom=0.12, top=0.95, hspace=0.45)
        gle_adjusted = fig._generate_gle()
        adjusted_points = self._extract_amove_points(gle_adjusted)
        assert len(adjusted_points) == 3
        adjusted_x = adjusted_points[0][0]

        # Increased normalized left margin should shift all subplots right.
        assert adjusted_x > default_x

    def test_subplots_adjust_wspace_hspace_reduce_cell_size(self):
        """Positive wspace/hspace should reduce per-panel graph size."""
        fig, axes = glp.subplots(2, 2, figsize=(10, 8))
        for idx, ax in enumerate(axes.flat):
            ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3])

        default_sizes = self._extract_sizes(fig._generate_gle())
        # First size command is global canvas size; subsequent entries are subplot sizes.
        default_subplot_sizes = default_sizes[1:]
        assert len(default_subplot_sizes) == 4

        fig.subplots_adjust(wspace=0.6, hspace=0.5)
        adjusted_sizes = self._extract_sizes(fig._generate_gle())
        adjusted_subplot_sizes = adjusted_sizes[1:]
        assert len(adjusted_subplot_sizes) == 4

        assert adjusted_subplot_sizes[0][0] < default_subplot_sizes[0][0]
        assert adjusted_subplot_sizes[0][1] < default_subplot_sizes[0][1]

    def test_subplots_adjust_validation_errors(self):
        """subplots_adjust should validate bounds and axis ordering."""
        fig = glp.figure()

        with pytest.raises(ValueError, match=r"left must be within \[0, 1\]"):
            fig.subplots_adjust(left=-0.01)

        with pytest.raises(ValueError, match=r"wspace must be >= 0"):
            fig.subplots_adjust(wspace=-0.5)

        with pytest.raises(ValueError, match="left must be less than right"):
            fig.subplots_adjust(left=0.8, right=0.3)

        with pytest.raises(ValueError, match="bottom must be less than top"):
            fig.subplots_adjust(bottom=0.7, top=0.2)

    def test_subplots_adjust_invalid_update_does_not_mutate_state(self):
        """Invalid updates should not partially overwrite previous settings."""
        fig = glp.figure()
        fig.subplots_adjust(left=0.15, right=0.9, top=0.95, bottom=0.1)

        with pytest.raises(ValueError, match="left must be less than right"):
            fig.subplots_adjust(right=0.1)

        assert fig._subplot_adjust["left"] == 0.15
        assert fig._subplot_adjust["right"] == 0.9
        assert fig._subplot_adjust["top"] == 0.95
        assert fig._subplot_adjust["bottom"] == 0.1

    def test_subplot_mixed_types(self):
        """Test subplots with different plot types."""

        fig, axes = glp.subplots(2, 2, figsize=(12, 10))

        axes[0, 0].plot([1, 2, 3], [1, 4, 9], color="blue")
        axes[0, 1].scatter([1, 2, 3], [3, 6, 2], color="red")
        axes[1, 0].bar([1, 2, 3], [10, 20, 30], color="green")
        axes[1, 1].errorbar([1, 2, 3], [5, 10, 15], yerr=1, marker="o")

        gle = fig._generate_gle()
        # Should contain all plot types
        assert "line" in gle
        assert "marker" in gle
        assert "bar" in gle
        assert "err" in gle

    def test_add_subplot_span_covers_its_cells_and_the_gap(self):
        """A (first, last) index spans the rectangle of cells, as matplotlib's."""
        fig = glp.figure()
        top = fig.add_subplot(2, 2, (1, 2))
        left = fig.add_subplot(2, 2, 3)
        right = fig.add_subplot(2, 2, 4)
        assert top.position == (2, 2, (1, 2))
        for ax in (top, left, right):
            ax.plot([1, 2], [1, 2])

        gle = fig._generate_gle()
        (tx, ty), (lx, ly), (rx, _ry) = self._extract_amove_points(gle)
        (tw, th), (_lw, lh), (rw, _rh) = self._extract_sizes(gle)[1:]
        assert tx == pytest.approx(lx)
        assert tx + tw == pytest.approx(rx + rw, abs=1e-4)
        assert th == pytest.approx(lh)
        assert ty > ly

    def test_add_subplot_span_corners_in_either_column_order(self):
        """(2, 3) names the rectangle from the top right to the bottom left."""
        fig = glp.figure()
        ax = fig.add_subplot(2, 2, (2, 3))
        ax.plot([1, 2], [1, 2])
        fig.add_subplot(2, 2, (1, 4)).plot([1, 2], [1, 2])
        sizes = self._extract_sizes(fig._generate_gle())[1:]
        assert sizes[0] == sizes[1]

    def test_add_subplot_one_cell_span_is_a_plain_index(self):
        assert glp.figure().add_subplot(2, 2, (2, 2)).position == (2, 2, 2)

    @pytest.mark.parametrize(
        "index, match",
        [
            ((1, 5), "between 1 and 4"),
            ((0, 2), "between 1 and 4"),
            ((3, 2), "between 1 and 4"),
            ((1, 2, 3), "two integers"),
            ((1.0, 2), "two integers"),
            ([1, 2], "tuple"),
        ],
    )
    def test_add_subplot_bad_span_raises(self, index, match):
        fig = glp.figure()
        with pytest.raises(ValueError, match=match):
            fig.add_subplot(2, 2, index)

    def test_add_subplot_span_shared_x_labels_its_bottom_row(self):
        """With sharex, a span reaching the bottom row keeps its x labels."""
        fig = glp.Figure(sharex=True)
        fig.add_subplot(2, 2, (1, 3)).plot([1, 2], [1, 2])
        fig.add_subplot(2, 2, 2).plot([1, 2], [1, 2])
        fig.add_subplot(2, 2, 4).plot([1, 2], [1, 2])
        tall, upper, lower = fig._generate_gle().split("begin graph")[1:]
        assert "xlabels off" not in tall
        assert "xlabels off" in upper
        assert "xlabels off" not in lower

    def test_add_subplot_span_round_trips_through_to_dict(self):
        fig = glp.figure()
        fig.add_subplot(2, 2, (1, 2)).plot([1, 2], [1, 2])
        payload = fig.to_dict()
        restored = Figure.from_dict(json.loads(json.dumps(payload)))
        assert restored.axes_list[0].position == (2, 2, (1, 2))
        assert restored.to_dict() == payload

    @pytest.mark.parametrize("idx", [5, 0, -1, 1.0, "1", None])
    def test_add_subplot_rejects_an_index_off_the_grid(self, idx):
        """As matplotlib: an integer from 1 to rows*cols, at the call."""
        fig = glp.figure()
        with pytest.raises(ValueError, match=r"from 1 to 4"):
            fig.add_subplot(2, 2, idx)
        assert fig.axes_list == []

    def test_add_subplot_accepts_a_numpy_integer_index(self):
        ax = glp.figure().add_subplot(2, 2, np.int64(4))
        assert ax.position == (2, 2, 4) and type(ax.position[2]) is int

    @pytest.mark.parametrize(
        "args", [(0, 2, 1), (-1, -2, 1), (2.5, 2, 1), (2, "2", 1), (2, 2)]
    )
    def test_add_subplot_rejects_a_bad_grid(self, args):
        with pytest.raises(ValueError, match=r"add_subplot\("):
            glp.figure().add_subplot(*args)

    def test_add_subplot_numpy_grid_serializes(self):
        fig = glp.figure()
        fig.add_subplot(np.int64(2), np.int64(2), 1)
        fig.add_subplot(np.int64(223))
        json.dumps(fig.to_dict())
        assert [ax.position for ax in fig.axes_list] == [(2, 2, 1), (2, 2, 3)]

    def test_add_subplot_rejects_a_zero_three_digit_index(self):
        with pytest.raises(ValueError, match=r"add_subplot\(2, 2, 0\)"):
            glp.figure().add_subplot(220)

    def test_add_axes_places_the_frame_in_figure_fractions(self):
        fig = glp.figure(figsize=(10 / 2.54, 5 / 2.54))
        inset = fig.add_axes([0.5, 0.2, 0.4, 0.6])
        assert inset.position is None
        assert inset.placement == pytest.approx((5.0, 1.0, 4.0, 3.0))
        assert fig.gca() is inset
        inset.plot([1, 2], [1, 2])
        gle = fig._generate_gle()
        assert self._extract_amove_points(gle) == [(5.0, 1.0)]
        assert self._extract_sizes(gle)[1] == (4.0, 3.0)

    def test_add_axes_inset_leaves_the_grid_alone(self):
        """The grid, its margins and its sharing ignore an inset."""

        def build(with_inset):
            fig, (left, right) = glp.subplots(1, 2, sharex=True, sharey=True)
            left.plot([0, 1], [0, 1])
            right.plot([0, 2], [0, 3])
            if with_inset:
                inset = fig.add_axes([0.2, 0.5, 0.2, 0.3])
                inset.plot([10, 20], [100, 200])
                inset.set_title("inset")
            return fig._generate_gle()

        plain, with_inset = build(False), build(True)
        assert self._extract_amove_points(with_inset)[:2] == (
            self._extract_amove_points(plain)
        )
        assert self._extract_sizes(with_inset)[:3] == self._extract_sizes(plain)
        blocks = with_inset.split("begin graph")
        assert "ylabels off" in blocks[2]
        inset_block = blocks[3]
        assert "xaxis min 10 max 20" in inset_block
        assert "labels off" not in inset_block

    @pytest.mark.parametrize(
        "rect, error",
        [
            ([0.1, 0.1, 0.3], TypeError),
            ("abcd", TypeError),
            ("1234", TypeError),
            ([0.1, 0.1, float("nan"), 0.3], ValueError),
            ([0.1, 0.1, 0.0, 0.3], ValueError),
            ([0.1, 0.1, 0.3, -0.3], ValueError),
        ],
    )
    def test_add_axes_bad_rect_raises(self, rect, error):
        with pytest.raises(error, match="rect"):
            glp.figure().add_axes(rect)

    def test_add_axes_inset_without_placement_raises_on_save(self):
        fig = glp.figure()
        inset = fig.add_axes([0.1, 0.1, 0.5, 0.5])
        inset.plot([1, 2], [1, 2])
        fig.add_subplot(111).plot([1, 2], [1, 2])
        inset.placement = None
        with pytest.raises(ValueError, match="placement"):
            fig._generate_gle()

    def test_add_axes_axes_properties_warn(self):
        with pytest.warns(UserWarning, match="ignores alpha"):
            glp.figure().add_axes([0.1, 0.1, 0.5, 0.5], alpha=0.5)

    def test_add_axes_facecolor_fills_the_inset_frame(self, recwarn):
        fig = glp.figure()
        fig.add_subplot(111).plot([1, 2], [1, 2])
        inset = fig.add_axes([0.5, 0.5, 0.3, 0.3], facecolor="w")
        inset.plot([1, 2], [2, 1])
        assert not recwarn.list
        blocks = fig._generate_gle().split("begin graph")
        assert "background" not in blocks[1]
        assert "    background WHITE\n" in blocks[2]

    @pytest.mark.parametrize(
        "color, written", [("C0", "rgb255(31,119,180)"), (None, None), ("none", None)]
    )
    def test_set_facecolor(self, color, written):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.set_facecolor("red")
        ax.set_facecolor(color)
        ax.plot([1, 2], [1, 2])
        lines = fig._generate_gle().splitlines()
        backgrounds = [line for line in lines if line.startswith("    background")]
        assert backgrounds == ([f"    background {written}"] if written else [])
        assert ax.to_dict().get("facecolor") == written

    @pytest.mark.parametrize(
        "color, written",
        [((1, 1, 1, 0), None), ((1, 0, 0, 0.5), "rgba255(255,0,0,128)")],
    )
    def test_set_facecolor_alpha(self, color, written, recwarn):
        ax = glp.figure().add_subplot(111)
        ax.set_facecolor(color)
        assert ax._facecolor == written
        assert not recwarn.list

    def test_set_facecolor_draws_nothing_where_the_frame_is_off(self):
        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.set_facecolor("w")
        ax.pie([1, 2, 3])
        assert "background" not in fig._generate_gle()
        with pytest.warns(UserWarning, match="no effect on a polar axes"):
            fig.add_axes([0.1, 0.1, 0.3, 0.3], polar=True, fc="w")

    def test_add_axes_takes_fc_or_facecolor_not_both(self):
        inset = glp.figure().add_axes([0.1, 0.1, 0.3, 0.3], fc="w")
        assert inset._facecolor == "WHITE"
        with pytest.raises(TypeError, match="both facecolor and fc"):
            glp.figure().add_axes([0.1, 0.1, 0.3, 0.3], fc="w", facecolor="w")

    def test_add_axes_polar(self):
        inset = glp.figure().add_axes([0.1, 0.1, 0.5, 0.5], polar=True)
        with pytest.raises(NotImplementedError):
            inset.set_xlim(0, 1)

    def test_add_axes_polar_and_another_projection_raises(self):
        with pytest.raises(ValueError, match="only one"):
            glp.figure().add_axes(
                [0.1, 0.1, 0.5, 0.5], projection="rectilinear", polar=True
            )

    def test_add_axes_lone_inset_keeps_its_rect_in_fullsize_mode(self):
        fig = glp.figure(graph=glp.GLEGraphConfig(scale_mode="fullsize"))
        fig.add_axes([0.25, 0.25, 0.5, 0.5]).plot([1, 2], [1, 2])
        gle = fig._generate_gle()
        assert "fullsize" not in gle
        assert len(self._extract_amove_points(gle)) == 1

    def test_add_axes_round_trips_through_to_dict(self):
        fig, ax = glp.subplots()
        ax.plot([1, 2], [1, 2])
        fig.add_axes([0.5, 0.5, 0.3, 0.3]).plot([1, 2], [2, 1])
        payload = fig.to_dict()
        restored = Figure.from_dict(json.loads(json.dumps(payload)))
        assert restored.axes_list[1].position is None
        assert restored.to_dict() == payload
        assert restored._generate_gle() == fig._generate_gle()

    def test_subplot_savefig(self, tmp_path):
        """Test saving multi-subplot figure."""
        fig, axes = glp.subplots(1, 2)
        axes[0].plot([1, 2, 3], [1, 4, 9])
        axes[1].scatter([1, 2, 3], [3, 2, 1])

        path = tmp_path / "subplots.gle"
        fig.savefig(str(path))
        assert path.exists()
        content = path.read_text()
        assert "amove" in content
        assert content.count("begin graph") == 2


class TestGridRatios:
    """Test height_ratios/width_ratios on the multi-subplot grid."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        yield
        glp.close()

    @staticmethod
    def _extract_sizes(gle):
        """Return all graph size commands as (width, height) float tuples."""
        return [
            (float(w), float(h))
            for w, h in re.findall(
                r"^\s*size\s+([0-9.]+)\s+([0-9.]+)$", gle, re.MULTILINE
            )
        ]

    @staticmethod
    def _extract_amove_points(gle):
        return [
            (float(x), float(y))
            for x, y in re.findall(
                r"^amove\s+([0-9.]+)\s+([0-9.]+)$", gle, re.MULTILINE
            )
        ]

    def assert_emitted_almost_equal(self, actual, expected):
        """Compare quantities read back from emitted GLE text.

        The writer emits 6 significant digits (GLEWriter._format_number), so
        a value recovered from the script -- or a ratio or sum of two of them
        -- is only good to ~1e-5 relative, however exactly the model's rects
        divide. Anything tighter tests the margins' decimal expansion rather
        than the layout.
        """
        assert actual == pytest.approx(expected, abs=1e-5 * max(1.0, abs(expected)))

    def test_default_omitted_height_ratios_is_byte_identical(self):
        """Omitting height_ratios must reproduce the pre-existing equal-row output."""
        from gleplot import axes as _gleplot_axes

        def build(**kwargs):
            fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 9), **kwargs)
            for idx, ax in enumerate(axes):
                ax.plot([1, 2, 3], [idx + 1, idx + 2, idx + 3], color="blue")
            return fig

        glp.close()
        _gleplot_axes._global_data_file_counter = 0
        without = build()._generate_gle()
        glp.close()
        _gleplot_axes._global_data_file_counter = 0
        explicit_none = build(height_ratios=None, width_ratios=None)._generate_gle()

        assert without == explicit_none

    def test_height_ratios_scales_row_sizes_proportionally(self):
        """A 3:1 height_ratios pair should split the plotting height 3:1."""
        fig, axes = glp.subplots(
            2, 1, sharex=True, figsize=(3.386, 4.0), height_ratios=[3, 1]
        )
        for ax in axes:
            ax.plot([0, 1], [0, 1], color="blue")

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]  # drop the page 'size' command
        assert len(sizes) == 2
        top_h, bottom_h = sizes[0][1], sizes[1][1]
        self.assert_emitted_almost_equal(top_h / bottom_h, 3.0)
        # Widths are unaffected by height_ratios.
        assert sizes[0][0] == pytest.approx(sizes[1][0], abs=5e-7)

    def test_width_ratios_scales_column_sizes_proportionally(self):
        """A 1:3 width_ratios pair should split the plotting width 1:3."""
        fig, axes = glp.subplots(1, 2, figsize=(10, 5), width_ratios=[1, 3])
        for ax in axes:
            ax.plot([0, 1], [0, 1], color="blue")

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        assert len(sizes) == 2
        left_w, right_w = sizes[0][0], sizes[1][0]
        self.assert_emitted_almost_equal(right_w / left_w, 3.0)

    def test_height_ratios_five_row_stack_with_short_separator(self):
        """3 flush panels + a short separator row + a 4th panel, PRL-shaped."""
        fig, axes = glp.subplots(
            5, 1, sharex=True, figsize=(3.386, 5.5), height_ratios=[3, 3, 3, 1, 4]
        )
        for ax in axes:
            ax.plot([0, 1], [0, 1], color="blue")

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        assert len(sizes) == 5
        heights = [h for _, h in sizes]
        # sharex=True -> zero vertical gap, so heights sum exactly to the
        # available plotting height (figure height minus margins).
        for a, b in ((0, 1), (1, 2)):
            assert heights[a] == pytest.approx(heights[b], abs=5e-7)
        self.assert_emitted_almost_equal(heights[0] / heights[3], 3.0)
        self.assert_emitted_almost_equal(heights[4] / heights[3], 4.0)

        # Panels are flush (sharex -> zero vspace): each row's top edge
        # meets the previous row's bottom edge exactly.
        amoves = self._extract_amove_points(gle)
        assert len(amoves) == 5
        for i in range(4):
            top_of_next = amoves[i + 1][1] + heights[i + 1]
            bottom_of_this = amoves[i][1]
            self.assert_emitted_almost_equal(top_of_next, bottom_of_this)

    def test_height_ratios_length_mismatch_raises(self):
        fig, axes = glp.subplots(3, 1, height_ratios=[1, 2])
        with pytest.raises(
            ValueError,
            match=r"height_ratios has length 2, but the subplot grid has 3 rows",
        ):
            fig._generate_gle()

    def test_width_ratios_length_mismatch_raises(self):
        fig, axes = glp.subplots(1, 2, width_ratios=[1, 2, 3])
        with pytest.raises(
            ValueError,
            match=r"width_ratios has length 3, but the subplot grid has 2 columns",
        ):
            fig._generate_gle()

    def test_non_positive_ratio_raises(self):
        fig, axes = glp.subplots(2, 1, height_ratios=[1, 0])
        with pytest.raises(
            ValueError, match="height_ratios entries must all be positive"
        ):
            fig._generate_gle()

    def test_height_ratios_via_figure_and_add_subplot(self):
        """height_ratios also works through Figure()/add_subplot, not just subplots()."""
        fig = glp.figure(figsize=(3.386, 4.0), height_ratios=[3, 1])
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.plot([0, 1], [0, 1], color="blue")
        ax2.plot([0, 1], [0, 1], color="blue")

        gle = fig._generate_gle()
        sizes = self._extract_sizes(gle)[1:]
        assert len(sizes) == 2
        assert sizes[0][1] / sizes[1][1] == pytest.approx(3.0, abs=5e-7)

    def test_single_row_width_ratios_ignored_for_single_axes(self):
        """A single (1,1,1) axes must ignore height_ratios/width_ratios entirely."""
        fig = glp.figure(height_ratios=[1, 2, 3])
        ax = fig.add_subplot(111)
        ax.plot([0, 1], [0, 1], color="blue")
        # Must not raise even though height_ratios has length 3 (there is
        # only ever 1 row on the single-axes path, which never validates it).
        gle = fig._generate_gle()
        assert "begin graph" in gle


class TestSecondaryYAxis:
    """Test secondary y-axis (y2axis) functionality."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        """Create fresh figure for each test."""
        glp.close()
        self.fig = glp.figure()
        self.ax = self.fig.add_subplot(111)
        yield
        glp.close()

    def test_y2_label(self):
        """Test setting y2axis label."""
        self.ax.set_ylabel("Primary Y", axis="y")
        self.ax.set_ylabel("Secondary Y", axis="y2")

        assert self.ax.ylabel_text == "Primary Y"
        assert self.ax.y2label_text == "Secondary Y"

    def test_y2_limits(self):
        """Test setting y2axis limits."""
        self.ax.set_ylim(0, 100, axis="y")
        self.ax.set_ylim(0, 1000, axis="y2")

        assert self.ax.ymin == 0
        assert self.ax.ymax == 100
        assert self.ax.y2min == 0
        assert self.ax.y2max == 1000

    def test_y2_scale(self):
        """Test setting y2axis scale."""
        self.ax.set_yscale("linear", axis="y")
        self.ax.set_yscale("log", axis="y2")

        assert self.ax.yscale == "linear"
        assert self.ax.y2scale == "log"

    def test_get_y2_limits(self):
        """Test getting y2axis limits."""
        self.ax.set_ylim(10, 20, axis="y2")

        y2min, y2max = self.ax.get_ylim(axis="y2")
        assert y2min == 10
        assert y2max == 20

    def test_plot_on_y2axis(self):
        """Test plotting on y2axis."""
        import numpy as np

        x = np.array([1, 2, 3])
        y = np.array([10, 20, 30])

        self.ax.plot(x, y, yaxis="y2", label="Y2 Data")

        assert len(self.ax.lines) == 1
        assert self.ax.lines[0]["yaxis"] == "y2"

    def test_scatter_on_y2axis(self):
        """Test scatter plot on y2axis."""
        import numpy as np

        x = np.array([1, 2, 3])
        y = np.array([100, 200, 300])

        self.ax.scatter(x, y, yaxis="y2", label="Y2 Scatter")

        assert len(self.ax.scatters) == 1
        assert self.ax.scatters[0]["yaxis"] == "y2"

    def test_errorbar_on_y2axis(self):
        """Test errorbar plot on y2axis."""
        import numpy as np

        x = np.array([1, 2, 3])
        y = np.array([50, 100, 150])
        yerr = np.array([5, 10, 15])

        self.ax.errorbar(x, y, yerr=yerr, yaxis="y2", label="Y2 Error")

        assert len(self.ax.errorbars) == 1
        assert self.ax.errorbars[0]["yaxis"] == "y2"

    def test_mixed_y_and_y2_plots(self):
        """Test mixing plots on y and y2 axes."""
        import numpy as np

        x = np.array([1, 2, 3])

        self.ax.plot(x, x**2, yaxis="y", label="Y Data")
        self.ax.plot(x, x**3, yaxis="y2", label="Y2 Data")

        assert len(self.ax.lines) == 2
        assert self.ax.lines[0]["yaxis"] == "y"
        assert self.ax.lines[1]["yaxis"] == "y2"

    def test_has_y2_plots(self):
        """Test has_y2_plots helper method."""
        import numpy as np

        x = np.array([1, 2, 3])

        # Initially no y2 plots
        assert not self.ax.has_y2_plots()

        # Add plot on y axis
        self.ax.plot(x, x**2, yaxis="y")
        assert not self.ax.has_y2_plots()

        # Add plot on y2 axis
        self.ax.plot(x, x**3, yaxis="y2")
        assert self.ax.has_y2_plots()

    def test_has_y2_plots_counts_a_file_series(self):
        """A file series on the right scale is a y2 plot, as on x2 (#229)."""
        self.ax.line_from_file("data.dat", 1, 2)
        assert not self.ax.has_y2_plots()
        self.ax.line_from_file("data.dat", 1, 3, yaxis="y2")
        assert self.ax.has_y2_plots()

    def test_y2_gle_generation(self):
        """Test that y2axis generates correct GLE code."""
        import numpy as np

        x = np.array([1, 2, 3])

        self.ax.plot(x, x**2, color="red", label="Y1", yaxis="y")
        self.ax.plot(x, x**3, color="blue", label="Y2", yaxis="y2")
        self.ax.set_ylabel("Primary", axis="y")
        self.ax.set_ylabel("Secondary", axis="y2")
        self.ax.set_ylim(0, 10, axis="y")
        self.ax.set_ylim(0, 30, axis="y2")

        gle = self.fig._generate_gle()

        # Check for y2axis directives
        assert 'y2title "Secondary"' in gle
        assert "y2axis min 0 max 30" in gle
        assert "y2axis" in gle  # y2axis keyword on plot command

    def test_primary_autoscale_leaves_out_the_y2_series(self):
        """GLE scales y2 from its own datasets, so the left range is the left's."""
        self.ax.plot([1, 2, 3], [2, 4, 6])
        self.ax.plot([1, 2, 3], [20, 30, 40], yaxis="y2")
        self.ax.errorbar([1, 2], [50, 60], yerr=5, yaxis="y2")
        self.ax.hist([1, 1, 2, 2, 2, 2, 2, 2, 2, 2], yaxis="y2")
        lines = self.fig._generate_gle().splitlines()
        assert "    yaxis min 2 max 6" in lines

    def test_primary_autoscale_counts_what_is_drawn_on_the_primary_axis(self):
        """A stepfilled histogram is drawn on the left whatever yaxis says,
        and a function curve, which GLE bounds itself, keeps y2 out too."""
        with pytest.warns(UserWarning, match="stepfilled"):
            self.ax.hist([1, 1, 2], histtype="stepfilled", yaxis="y2")
        self.ax.plot([1, 2], [20, 40], yaxis="y2")
        assert "    yaxis min 0 max 2" in self.fig._generate_gle().splitlines()

        fig = glp.figure()
        ax = fig.add_subplot(111)
        ax.function("sin(x)", 1, 3)
        ax.plot([1, 2, 3], [20, 30, 40], yaxis="y2")
        assert not any(
            line.strip().startswith("yaxis min")
            for line in fig._generate_gle().splitlines()
        )

    def test_primary_autoscale_with_only_y2_series_spans_them(self):
        """With nothing on the left, its range is still the one y2 would copy."""
        self.ax.plot([1, 2, 3], [20, 30, 40], yaxis="y2")
        assert "    yaxis min 20 max 40" in self.fig._generate_gle().splitlines()

    def test_y2_log_scale_gle(self):
        """Test that y2axis log scale generates correct GLE code."""
        import numpy as np

        x = np.array([1, 2, 3, 4])
        y = np.array([10, 100, 1000, 10000])

        self.ax.plot(x, y, yaxis="y2")
        self.ax.set_yscale("log", axis="y2")

        gle = self.fig._generate_gle()
        assert "y2axis log" in gle

    def test_y2_with_figure_convenience_methods(self):
        """Test y2axis with figure-level ylabel convenience method."""
        self.fig.ylabel("Primary Y", axis="y")
        self.fig.ylabel("Secondary Y", axis="y2")

        ax = self.fig.gca()
        assert ax.ylabel_text == "Primary Y"
        assert ax.y2label_text == "Secondary Y"


class TestDecorationMargins:
    """One margin policy for every layout shape (Figure._auto_margins_cm).

    The compiled proof that these margins are big enough lives in
    ``tests/integration/test_ink_on_page.py``, which needs a GLE binary.
    These assertions are on the model alone, so they run everywhere.
    """

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        glp.close()
        yield
        glp.close()

    @staticmethod
    def _margins(fig):
        """``(left, right, bottom, top)`` cm for a figure, as the writer sees it."""
        from gleplot.writer import GLEWriter

        writer = GLEWriter(fig.figsize, fig.dpi, style=fig.style, graph=fig.graph)
        return fig._auto_margins_cm(writer, None)

    @staticmethod
    def _build(rows, cols, **kwargs):
        fig, axes = glp.subplots(rows, cols, figsize=(8, 6), squeeze=False, **kwargs)
        for ax in axes.flat:
            ax.plot([0, 1, 2], [-1.0, -0.5, -1.0], color="blue")
            ax.set_xlabel("time")
            ax.set_ylabel("voltage")
        return fig

    def test_a_grid_gets_the_same_margins_as_a_lone_plot(self):
        """The grid's outer decoration is the lone plot's decoration."""
        lone = self._margins(self._build(1, 1))
        for shape in ((1, 2), (2, 1), (2, 2), (3, 3)):
            assert self._margins(self._build(*shape)) == lone

    def test_shared_axes_do_not_get_their_own_margins(self):
        """Sharing suppresses INNER labels; the outer edges are unchanged."""
        plain = self._margins(self._build(2, 2))
        for kwargs in (
            {"sharex": True},
            {"sharey": True},
            {"sharex": True, "sharey": True},
        ):
            assert self._margins(self._build(2, 2, **kwargs)) == plain

    def test_grid_margins_scale_with_the_font_size(self):
        """A fixed-cm margin that fits at 12 pt clips at 18 pt; these do not."""
        small = self._margins(self._build(2, 2, style=glp.GLEStyleConfig(fontsize=9)))
        large = self._margins(self._build(2, 2, style=glp.GLEStyleConfig(fontsize=18)))
        for a, b in zip(small, large):
            assert b / a == pytest.approx(2.0, abs=5e-7)

    def test_grid_left_margin_covers_a_y_title_plus_wide_tick_labels(self):
        """The measured requirement the old fixed 1.0 cm / 1.5 cm missed.

        A rotated y-axis title plus 4-character tick labels ("-0.5") occupy
        3.11 hei, measured against GLE 4.3.10 -- 1.32 cm at the default
        12 pt, which the old grid margins were below.
        """
        from gleplot.parser.units import fontsize_pt_to_cm

        fig = self._build(2, 2)
        left = self._margins(fig)[0]
        assert left >= 3.11 * fontsize_pt_to_cm(fig.style.fontsize)
        assert left > 1.32

    def test_a_titled_grid_reserves_more_top_margin(self):
        titled = self._build(2, 2)
        titled.axes_list[0].set_title("panel")
        assert self._margins(titled)[3] > self._margins(self._build(2, 2))[3]

    def test_a_grid_with_a_secondary_y_axis_reserves_more_right_margin(self):
        with_y2 = self._build(1, 2)
        with_y2.axes_list[-1].set_ylabel("current", axis="y2")
        assert self._margins(with_y2)[1] > self._margins(self._build(1, 2))[1]

    def test_subplots_adjust_still_overrides_the_computed_margins(self):
        fig = self._build(2, 2)
        fig.subplots_adjust(left=0.25, right=0.9, bottom=0.2, top=0.8)
        left, right, bottom, top = self._margins(fig)
        width_cm, height_cm = 8 * 2.54, 6 * 2.54
        assert left == pytest.approx(0.25 * width_cm, abs=5e-7)
        assert right == pytest.approx(0.1 * width_cm, abs=5e-7)
        assert bottom == pytest.approx(0.2 * height_cm, abs=5e-7)
        assert top == pytest.approx(0.2 * height_cm, abs=5e-7)

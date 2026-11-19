"""Shared golden-battery figure builders for the writer-refactor guard test.

Reuses the same battery style as ``tests/integration/test_project_io.py``:
each builder is a zero-argument callable constructing a fresh
:class:`gleplot.Figure` exercising a distinct writer code path (series
types, subplots, text, y2 axis, file-series, legends, log scales, etc.).
``test_units.py`` snapshots ``_generate_gle_with_files()`` output for every
builder before and after the units/tables refactor and asserts byte-for-byte
identity, guarding the "zero behavior change" requirement for Track A2.
"""

import warnings

import numpy as np

import gleplot as glp
from gleplot.series import FileSeries


def single_line():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color="blue", label="quad")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("single line")
    return fig


def multi_series_styles():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 20)
    ax.plot(x, np.sin(x), color="red", linestyle="--", linewidth=2, label="sin")
    ax.plot(x, np.cos(x), color="green", linestyle=":", label="cos")
    ax.plot(
        x,
        np.sin(x) * 0.5,
        color="blue",
        marker="o",
        linestyle="none",
        markersize=8,
        label="half",
    )
    ax.plot(
        x, np.cos(x) * 0.5, color="black", linestyle="-.", linewidth=3, label="dashdot"
    )
    ax.legend(loc="upper left")
    return fig


def scatter():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.scatter(
        [1, 2, 3, 4], [4, 3, 2, 1], color="purple", s=40, marker="s", label="pts"
    )
    ax.legend()
    return fig


def bar():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color="orange")
    ax.set_title("bar")
    return fig


def bar_edge():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar(
        [1, 2, 3],
        [4, 5, 6],
        color="orange",
        edgecolor="black",
        linewidth=1.5,
        linestyle="--",
        width=0.4,
    )
    return fig


def bar_per_color():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [4, 5, 6], color=["red", "green", "blue"], label="bars")
    ax.legend()
    return fig


def bar_stack():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [2, 3, 1], color="gray", label="base")
    ax.bar([1, 2, 3], [1, 1, 2], bottom=[2, 3, 1], color="white", label="top")
    ax.legend()
    return fig


def bar_missing():
    """A NaN height is a missing row, plain and on a baseline (#317)."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [2, np.nan, 1], color="gray")
    ax.bar([1, 2, 3], [1, np.nan, 2], bottom=[2, 3, 1], color="white")
    return fig


def bar_recovered_fields():
    """Bar fields only a recovered script sets, set here on the series.

    A fill list longer than the one dataset, an edge colour list, a raw
    ``lstyle``, a key swatch colour, a stored baseline top and ``dist``.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2], [5, 3], color="red", label="first")
    ax.bar([1, 2], [1, 1], bottom=[5, 3], color="white", label="stacked")
    first, stacked = ax.bars
    first["fill_list"] = ["RED", "BLUE"]
    first["edgecolor"] = "BLACK"
    first["edge_list"] = ["BLACK", "GRAY"]
    first["lstyle"] = "9"
    first["swatch_color"] = "GREEN"
    stacked["top"] = [6.0, 4.0]
    stacked["dist"] = 0.4
    ax.legend()
    return fig


def bar_hatch():
    """``hatch`` as GLE ``pattern`` / ``background``: one series, a per-bar
    split, a hidden face, a stack and a horizontal bar, with a legend."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [2, 3, 1], color="yellow", hatch="//", label="dense")
    ax.bar([1, 2, 3], [1, 1, 2], bottom=[2, 3, 1], hatch="x", edgecolor="blue")
    ax.bar([5, 6], [1, 2], hatch=["\\", "/"], color="none", label="split")
    ax.barh([1, 2], [3, 4], hatch="xx", color="teal")
    ax.legend()
    return fig


def barh():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.barh([1, 2, 3], [4, 5, 6], color="teal", height=0.4)
    return fig


def bar_yerr():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.bar(
        [1, 2, 3],
        [4, 5, 6],
        yerr=([0.2, 0.3, 0.4], [0.5, 0.4, 0.3]),
        capsize=3,
        color="orange",
        label="measured",
    )
    ax.legend()
    return fig


def barh_xerr():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.barh([1, 2, 3], [4, 5, 6], xerr=0.4, capsize=4, color="teal", left=1)
    return fig


def errorbar_symmetric():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.errorbar(
        [1, 2, 3], [2, 4, 6], yerr=0.5, color="red", marker="o", capsize=4, label="sym"
    )
    ax.legend()
    return fig


def errorbar_asymmetric_xy():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.errorbar(
        [1, 2, 3],
        [2, 4, 6],
        yerr=([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]),
        xerr=0.2,
        capsize=3,
        color="blue",
        marker="s",
    )
    return fig


def errorbar_field_options():
    """Errorbar fields the other builders leave at their defaults.

    Offset, the y2 and x2 axes, a dashed line with a width and no marker,
    and bars only (``fmt="none"``).
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [1, 2, 3]
    ax.errorbar(
        x,
        [2, 4, 6],
        yerr=0.5,
        fmt="--",
        linewidth=2,
        offset=1.0,
        color="red",
        label="dashed",
    )
    ax.errorbar(
        x,
        [20, 30, 40],
        yerr=2.0,
        fmt="none",
        yaxis="y2",
        color="blue",
        label="bars",
    )
    ax.errorbar(
        x, [3, 1, 2], xerr=0.1, marker="o", xaxis="x2", color="green", label="top"
    )
    ax.legend()
    return fig


def errorbar_data_range():
    """An errorbar data range: all four edges, and one edge with an offset."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0.0, 5.0, 11)
    ax.errorbar(
        x,
        np.sin(x),
        yerr=0.2,
        xerr=0.1,
        marker="o",
        color="blue",
        xmin=0.5,
        xmax=4.5,
        ymin=-0.8,
        ymax=0.8,
        label="window",
    )
    ax.errorbar(x, 0.2 * x, yerr=0.1, fmt="none", offset=1.0, color="red", ymax=1.5)
    ax.legend()
    return fig


def fill_between():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), x**0.5, color="lightblue", alpha=0.4)
    ax.plot(x, x**0.5, color="blue")
    return fig


def raw_lines_reading_modelled_datasets():
    """Raw lines in a second panel that read its modelled datasets.

    ``_gle_name`` is what ``open_gle`` sets when a kept raw line reads a
    series' dataset: here the names the panel's series are written under.
    The ``let`` target and the comment are not reads.
    """
    fig, (top, bottom) = glp.subplots(2, 1, data_prefix="golden")
    top.plot([1, 2, 3], [1, 2, 1])
    bottom.plot([1, 2, 3], [0, 1, 0], color="red")
    bottom.plot([1, 2, 3], [2, 3, 2], color="blue")
    bottom.lines[0]["_gle_name"] = "d2"
    bottom.lines[1]["_gle_name"] = "d3"
    bottom.passthrough = [
        "   fill d2,d3 color gray foo",
        '   let d9 = d3*2 ! "d2"',
    ]
    return fig


def text_annotations():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.text(
        1.5,
        2.0,
        "peak",
        color="red",
        fontsize=14,
        ha="center",
        va="bottom",
        rotation=45,
        bbox={"facecolor": "white"},
    )
    ax.text(2.5, 1.0, "boxed", bbox={"facecolor": "yellow"})
    return fig


def axes_fraction_text():
    """Text in axes fractions (``transform=ax.transAxes``) on a log x axis
    and an inverted y axis, around a data-coordinate text that shares its
    sticky ``set`` state."""
    fig, axes = glp.subplots(1, 2, data_prefix="golden")
    left, right = axes
    left.plot([1, 10, 100], [1, 2, 3])
    left.set_xscale("log")
    left.text(0.05, 0.95, "(a)", transform=left.transAxes, ha="left", va="top")
    left.text(10, 2, "data", transform=left.transData)
    left.text(
        0.5,
        0.1,
        "boxed",
        transform=left.transAxes,
        ha="center",
        rotation=30,
        bbox={"facecolor": "yellow"},
    )
    right.plot([0, 1], [0, 1])
    right.set_ylim(1, 0)
    right.text(1.02, -0.05, "(b)", transform=right.transAxes, color="red")
    return fig


def annotations_with_arrows():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 3, 2])
    ax.annotate("peak", xy=(2, 3), xytext=(2.4, 3.5), arrowprops={"arrowstyle": "->"})
    ax.annotate(
        "both",
        xy=(1, 1),
        xytext=(2.5, 1.2),
        color="red",
        ha="center",
        rotation=15,
        bbox={"facecolor": "yellow"},
        arrowprops={"arrowstyle": "<|-|>", "color": (0.2, 0.4, 0.6), "lw": 1.5},
    )
    ax.annotate("bare", xy=(3, 2), xytext=(2.8, 2.8), arrowprops={"arrowstyle": "-"})
    ax.annotate("no arrow", xy=(1.2, 2.5))
    return fig


def secondary_yaxis():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color="blue", label="left", yaxis="y")
    ax.plot([1, 2, 3], [100, 200, 300], color="red", label="right", yaxis="y2")
    ax.set_ylabel("left y")
    ax.set_ylabel("right y", axis="y2")
    # A log axis needs a strictly positive range, or GLE will not compile the
    # script this builder is here to produce. (It asked for 0..400 until
    # 2026-08-06; nothing noticed, because the batteries round-trip their GLE
    # rather than compiling it. See tests/unit/test_log_limits.py.)
    ax.set_ylim(50, 400, axis="y2")
    ax.set_yscale("log", axis="y2")
    ax.legend()
    return fig


def axis_helpers():
    """matplotlib's axis helpers: twinx, invert, semilogy, tick labels, and
    a second panel with ``axis('off')``."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(121)
    ax.semilogy([1, 2, 3], [1, 10, 100], color="blue", label="left")
    right = ax.twinx()
    right.plot([1, 2, 3], [5, 6, 7], color="red", label="right")
    right.set_ylim(0, 10)
    right.invert_yaxis()
    right.set_ylabel("right y")
    ax.invert_xaxis()
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["a", "b", "c"])
    ax.legend()
    off = fig.add_subplot(122)
    off.plot([1, 2, 3], [1, 4, 9], color="blue")
    off.axis("off")
    return fig


def secondary_xaxis():
    """Top scale as its own data axis, under a log bottom axis.

    The log bottom axis is what makes GLE copy ``log`` onto x2; the linear
    top scale has to answer with ``lin``. Limits stay positive on the log
    axis and include 0 on the linear one.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color="blue", label="energy")
    ax.set_xscale("log")
    top = ax.twiny()
    top.plot([0, 5, 10], [1, 2, 3], color="red", label="wavelength")
    top.set_xlim(0, 10)
    top.set_xlabel("wavelength")
    ax.legend()
    return fig


def legend_positions_all():
    figs = []
    for loc in (
        "upper right",
        "upper left",
        "lower left",
        "lower right",
        "center",
        "best",
    ):
        fig = glp.figure(data_prefix="golden")
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], label=loc)
        ax.legend(loc=loc)
        figs.append(fig)
    return figs[0]


def legend_full_options():
    """``key pos``/``offset``/``hei`` together, offset with a negative
    component -- the combination the writer itself emits for any legend
    that sets an offset and a fontsize, e.g.
    ``key pos bl offset 1.5 -0.5 hei 0.31746``. Regression coverage for a
    recognizer gap: 'offset dx dy' tokenizes a negative component as an OP
    '-' followed by a NUMBER (GLE has no signed-literal token), which
    ``_scan_key_options`` failed to recognize, silently dropping the whole
    'key' line to raw passthrough with 'pos'/'offset'/'hei' all reverting to
    their model defaults. ``legend_positions_all`` above only exercises bare
    ``loc=``, with no offset/fontsize, so it never touched this path.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="series 1")
    ax.legend(loc="lower left", fontsize=9.0, offset=(1.5, -0.5))
    return fig


def legend_spacing():
    """matplotlib spacing keywords as the in-graph ``llen``/``dist``/
    ``coldist``/``margins``, in font-size units of the figure's text height.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="a", marker="o")
    ax.plot([1, 2, 3], [3, 2, 1], label="b")
    ax.legend(
        ncol=2, handlelength=1.5, handletextpad=0.5, columnspacing=1.0, borderpad=0.3
    )
    return fig


def legend_anchored():
    """``bbox_to_anchor``, ``labelcolor`` and spacing in a ``begin key`` block:
    ``justify`` plus ``absolute`` read from the graph that has just ended,
    and ``textcolor`` on every entry. The negative fraction is ``+-``.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="a")
    ax.plot([1, 2, 3], [3, 2, 1], label="b", linestyle="--")
    ax.legend(
        loc="upper right",
        bbox_to_anchor=(-0.1, 1.0),
        labelcolor="gray",
        fontsize=8,
        handlelength=1.2,
        borderpad=0.3,
        ncol=2,
    )
    return fig


def subplots_sharex():
    fig, axes = glp.subplots(3, 1, sharex=True, data_prefix="golden")
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f"s{i}")
        ax.set_ylabel(f"y{i}")
    axes[-1].set_xlabel("shared x")
    return fig


def subplots_sharex_with_colored_text():
    """A coloured text ending one panel must not leak into the next panel.

    Regression coverage for the 2026-07-29 library gap: the writer used to
    emit a bare ``set color`` for graph-data-coordinate text (queued in
    ``_pending_graph_text_lines``, flushed right after ``end graph``), which
    is GLE *page-level* sticky state shared by the whole script -- so a
    coloured label ending one panel coloured the NEXT panel's axes/ticks.
    ``GLEWriter.end_graph`` now wraps that flush in gsave/grestore (see
    ``tests/unit/test_text.py``'s ``TestColorStateDoesNotLeakAcrossPanels``
    for the direct assertion); this builder exercises the same fix through a
    full multi-subplot writer -> recognizer -> writer fixed point.
    """
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="golden")
    axes[0].plot([1, 2, 3], [1, 2, 3], color="blue")
    axes[0].text(2, 2, "PM", color="green", ha="center")
    axes[1].plot([1, 2, 3], [3, 2, 1], color="blue")
    axes[1].set_xlabel("shared x")
    return fig


def subplots_grid_mixed():
    fig, axes = glp.subplots(2, 2, data_prefix="golden")
    axes[0, 0].plot([1, 2, 3], [1, 2, 3])
    axes[0, 1].scatter([1, 2, 3], [3, 2, 1], marker="o")
    axes[1, 0].bar([1, 2, 3], [2, 4, 6], color="red")
    axes[1, 1].errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, capsize=3)
    fig.subplots_adjust(hspace=0.4, wspace=0.4)
    return fig


def subplots_spanning():
    """Cells spanning columns, rows, and a whole row, with shared x."""
    fig = glp.Figure(data_prefix="golden", sharex=True)
    fig.add_subplot(3, 3, (1, 2)).plot([1, 2, 3], [1, 2, 3])
    fig.add_subplot(3, 3, (3, 6)).bar([1, 2, 3], [2, 4, 6])
    for idx in (4, 5):
        fig.add_subplot(3, 3, idx).scatter([1, 2, 3], [3, 2, 1], marker="o")
    fig.add_subplot(3, 3, (7, 9)).plot([1, 2, 3], [3, 1, 2])
    return fig


def inset_axes():
    """An inset over the left panel of a shared-y pair, unshared itself."""
    fig, (left, right) = glp.subplots(1, 2, sharey=True, data_prefix="golden")
    left.plot([1, 2, 3], [1, 4, 9])
    right.plot([1, 2, 3], [9, 4, 1])
    inset = fig.add_axes([0.2, 0.55, 0.2, 0.25])
    inset.plot([10, 20], [100, 200], color="red")
    inset.set_title("zoom")
    return fig


def inset_facecolor():
    """A shaded panel under a white inset that hides the curve behind it."""
    fig, ax = glp.subplots(data_prefix="golden")
    ax.plot([0, 1], [0, 1])
    ax.set_facecolor("whitesmoke")
    inset = fig.add_axes([0.5, 0.2, 0.3, 0.3], facecolor="white")
    inset.plot([0, 1], [1, 0], color="red")
    return fig


def insets_off_panel():
    """Insets the frames do not nest: one across a panel edge, one in the margin.

    Only the ``insets`` metadata line tells ``open_gle`` they are not grid
    panels, which with sharey would otherwise join the shared y range.
    """
    fig, (left, right) = glp.subplots(1, 2, sharey=True, data_prefix="golden")
    left.plot([1, 2, 3], [1, 4, 9])
    right.plot([1, 2, 3], [9, 4, 1])
    fig.add_axes([0.45, 0.05, 0.2, 0.2]).plot([10, 20], [100, 200])
    fig.add_axes([0.0, 0.0, 0.08, 0.1]).plot([0, 1], [5, 6])
    return fig


def inset_alone():
    """A figure whose only axes is placed by add_axes."""
    fig = glp.figure(data_prefix="golden")
    fig.add_axes([0.3, 0.2, 0.5, 0.6]).plot([1, 2, 3], [3, 1, 2])
    return fig


def aspect_ratios():
    """An equal-aspect panel beside a log panel with a numeric aspect."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    left.plot([-1, 0, 1, 0, -1], [0, 1, 0, -1, 0])
    left.set_aspect("equal")
    right.plot([1, 2, 3], [1, 10, 100])
    right.set_yscale("log")
    right.set_aspect(0.5)
    return fig


def file_series():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.line_from_file(
        "external.dat", 1, 2, color="blue", linestyle="--", label="line-file"
    )
    ax.errorbar_from_file(
        "external.dat",
        1,
        2,
        yerr_col=3,
        color="red",
        marker="o",
        capsize=4,
        label="eb-file",
    )
    ax.legend()
    return fig


def file_series_data_range():
    """An errorbar file reference with its own data range."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.errorbar_from_file("external.dat", 1, 2, yerr_col=3, xmin=0.5, ymax=12)
    return fig


def errorbar_thinned_from_a_file():
    """An error-bar dataset with the mdist and deresolve only a file can give.

    Axes.errorbar does not take them; open_gle keeps them (#343).
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.errorbar([0, 1, 2, 3], [1, 2, 1, 2], yerr=0.1, marker="o")
    ax.errorbars[0].update(mdist=0.4, deresolve=2, deresolve_average=True)
    return fig


def file_series_without_a_line():
    """``line_from_file(linestyle='none')``: a dataset with no ``line`` token,
    one with a marker as well, and one feeding a derived curve."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.line_from_file("external.dat", 1, 2, color="green", linestyle="none", label="x")
    ax.line_from_file("external.dat", 1, 3, linestyle="none", linewidth=2)
    ax.file_series[-1].update(marker="CIRCLE", markersize=0.2)
    ax.derived("2*d1", ax.file_series[0], label="twice")
    return fig


def log_axis_without_major_ticks():
    """``set_xticks([])`` on a log axis keeps the minor ticks, as matplotlib,
    unless ``minorticks_off`` took them away."""
    fig = glp.figure(data_prefix="golden")
    for index, minor in ((1, None), (2, False), (3, True)):
        ax = fig.add_subplot(1, 3, index)
        ax.plot([1, 10, 100], [1, 2, 3])
        if index < 3:
            ax.set_xscale("log")
        ax.set_xticks([])
        if minor is not None:
            ax.xminorticks = minor
    return fig


def line_with_nan_gaps():
    """A NaN breaks a plotted and a stepped line, written as GLE's ``*``."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    nan = float("nan")
    ax.plot([0, 1, 2, 3, 4], [0, 1, nan, 3, 4], color="red", label="broken")
    ax.step([0, 1, 2, 3], [1, nan, 2, 2], where="post")
    return fig


def file_series_field_options():
    """File-series fields the ``file_series`` builder leaves at their defaults.

    A wide stepped line on the y2 axis with a marker and ``nomiss``, a
    marker-less errorbar reference with no error column on the x2 axis, and
    the bar and fill references the recognizer keeps for a file gleplot
    did not write: a labelled bar with a swatch colour, a clipped two-curve fill, a
    fill to ``x1`` and a labelled polygon fill. ``marker``, ``markersize``
    and ``nomiss`` on a line reference, and every bar and fill reference,
    come only from a recovered script, so they are set on the series here.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.line_from_file(
        "external.dat",
        1,
        2,
        color="green",
        linewidth=2,
        yaxis="y2",
        drawstyle="steps-pre",
        label="stepped",
    )
    ax.file_series[0].update(marker="CIRCLE", markersize=0.2, nomiss=True)
    ax.errorbar_from_file("external.dat", 1, 3, color="red", marker=None, xaxis="x2")
    ax.file_series.extend(
        [
            FileSeries(
                series_type="bar",
                data_file="external.dat",
                x_col=1,
                y_col=4,
                color="ORANGE",
                label="bars",
                swatch_color="RED",
            ),
            FileSeries(
                series_type="fill",
                data_file="external.dat",
                x_col=1,
                y1_col=2,
                y2_col=3,
                color="GRAY10",
                xmin=0.5,
                ymax=2.0,
            ),
            FileSeries(
                series_type="fill",
                data_file="external.dat",
                x_col=1,
                y1_col=2,
                color="GRAY20",
                target="x1",
            ),
            FileSeries(
                series_type="fill",
                data_file="external.dat",
                x_col=1,
                y1_col=3,
                color="BLUE",
                target="polygon",
                label="polygon",
                swatch_color="CYAN",
            ),
        ]
    )
    ax.legend()
    return fig


def file_series_read_options():
    """How GLE reads a referenced file: ``ignore``, ``comment``, ``numrows``.

    A line reference with all three and the row number as x (``c0``), an
    errorbar reference with two, and the bar and fill references the
    recognizer keeps for a file gleplot did not write, which carry the options of
    the ``data`` statement they came from. ``!`` and ``;`` are comment
    markers that only survive quoted.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.line_from_file(
        "external.dat", 0, 2, color="blue", skiprows=3, comment="#", max_rows=100
    )
    ax.errorbar_from_file(
        "external.dat", 1, 2, yerr_col=3, color="red", comment=";", max_rows=5
    )
    ax.file_series.extend(
        [
            FileSeries(
                series_type="bar",
                data_file="external.dat",
                x_col=1,
                y_col=4,
                color="ORANGE",
                skiprows=1,
                comment="!",
            ),
            FileSeries(
                series_type="fill",
                data_file="external.dat",
                x_col=1,
                y1_col=2,
                y2_col=3,
                color="GRAY10",
                skiprows=2,
            ),
            FileSeries(
                series_type="fill",
                data_file="external.dat",
                x_col=1,
                y1_col=2,
                color="GRAY20",
                target="x1",
                max_rows=7,
            ),
        ]
    )
    return fig


def large_markersize_and_linewidth():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot(
        [1, 2, 3],
        [1, 2, 3],
        linewidth=0.25,
        marker="D",
        markersize=20,
        label="thin-big",
    )
    ax.plot([1, 2, 3], [3, 2, 1], linewidth=4.5, label="thick")
    ax.legend()
    return fig


def exact_rgb_colors():
    """Every colour-carrying emission context, driven by exact (non-name) colours.

    Hex / tuple / matplotlib-cycle colours emit as ``rgb255(r,g,b)``; a named
    colour still emits as its name. Both forms must survive the round trip.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 6, 12)
    ax.plot(x, np.sin(x), color="#8c8c8c", label="grey line")
    ax.plot(x, np.cos(x), color="C4", marker="o", label="cycle purple")
    ax.plot(
        x,
        np.sin(x) * 0.4,
        color=(0.72, 0.73, 0.13),
        marker="s",
        linestyle="none",
        label="tuple",
    )
    ax.plot(x, np.cos(x) * 0.4, color="darkred", label="named")
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.4, color="#9467bd", marker="D", capsize=3)
    ax.bar([4.5, 5.0, 5.5], [1.0, 1.4, 0.8], color="#bbbbbb")
    ax.fill_between(x, np.zeros_like(x), np.sin(x) * 0.2, color="#999999", alpha=0.4)
    ax.text(2.0, 1.2, "grey label", color="#8c8c8c", fontsize=12)
    ax.legend()
    return fig


def custom_figsize_and_dpi():
    fig = glp.figure(figsize=(10, 4), dpi=150, data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    return fig


def heatmap_imshow_colorbar():
    """imshow (grid .z sidecar) + a vertical colorbar."""
    fig = glp.figure(figsize=(7, 6), data_prefix="golden")
    ax = fig.add_subplot(111)
    y, x = np.mgrid[0:16, 0:21]
    Z = np.sin(x / 6.0) * np.cos(y / 5.0)
    ax.imshow(Z, extent=(0, 10, 0, 8), cmap="viridis", vmin=-1, vmax=1)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.colorbar(label="signal", format="fix 1")
    return fig


def heatmap_grid_colorbars():
    """A 2x2 grid of heatmaps, each with its own bar on its own scale.

    Vertical bars beside the left column, horizontal ones under the right
    column: inner and outer gaps in both directions, and both colorbar subs.
    """
    fig, _axs = glp.subplots(2, 2, figsize=(10, 8), data_prefix="golden")
    y, x = np.mgrid[0:6, 0:8]
    for k, ax in enumerate(fig.axes_list):
        hm = ax.imshow((k + 1) * x * y, cmap=("viridis", "magma")[k % 2])
        fig.colorbar(
            hm,
            ax=ax,
            label=f"z{k}",
            orientation=("vertical", "horizontal")[k % 2],
            width=0.4,
        )
    return fig


def heatmap_field_options():
    """Heatmap fields the other builders leave at their defaults.

    A grayscale ``origin='upper'`` image sampled ``nearest`` at an explicit
    pixel count, and an inverted rainbow image: the two colormap modes that
    write no ``palette`` sub.
    """
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    Z = np.arange(12, dtype=float).reshape(3, 4)
    left.imshow(
        Z,
        extent=(0, 4, 0, 3),
        origin="upper",
        cmap="gray",
        interpolation="nearest",
        pixels=(40, 30),
    )
    right.imshow(Z, extent=(0, 4, 0, 3), cmap="rainbow", invert=True)
    return fig


def heatmap_inverted_colorbars():
    """Colorbars of inverted images draw the reversed palette.

    A vertical bar for an inverted ``viridis_r`` image (forward ``viridis``
    bar) and a horizontal one for an inverted ``gray`` image (a
    ``gleplot_gray_r`` sub).
    """
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    Z = np.arange(12, dtype=float).reshape(3, 4)
    hm = left.imshow(Z, extent=(0, 4, 0, 3), cmap="viridis_r", invert=True)
    fig.colorbar(hm, ax=left)
    hm = right.imshow(Z, extent=(0, 4, 0, 3), cmap="gray", invert=True)
    fig.colorbar(hm, ax=right, orientation="horizontal")
    return fig


def heatmap_brewer_palettes():
    """ColorBrewer cmaps: an interpolated diverging ramp and a stepped set."""
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    Z = np.arange(12, dtype=float).reshape(3, 4)
    left.imshow(Z, extent=(0, 4, 0, 3), cmap="RdBu")
    right.imshow(Z, extent=(0, 4, 0, 3), cmap="Set1")
    return fig


def heatmap_reversed_palettes():
    """Reversed cmaps: a ramp with its colorbar, a stepped set, both built-ins."""
    fig, ((ramp, stepped), (gray, rainbow)) = glp.subplots(
        2, 2, figsize=(9, 8), data_prefix="golden"
    )
    Z = np.arange(12, dtype=float).reshape(3, 4)
    hm = ramp.imshow(Z, extent=(0, 4, 0, 3), cmap="RdBu_r")
    fig.colorbar(hm, ax=ramp)
    stepped.imshow(Z, extent=(0, 4, 0, 3), cmap="Set1_r")
    gray.imshow(Z, extent=(0, 4, 0, 3), cmap="gray_r")
    rainbow.imshow(Z, extent=(0, 4, 0, 3), cmap="jet_r")
    return fig


def heatmap_pcolormesh():
    """pcolormesh cells: edges from a meshgrid, and centres that decrease.

    The left mesh has a colorbar; the right one's y centres run downwards,
    so its rows are flipped before they are written.
    """
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    X, Y = np.meshgrid(np.linspace(0, 2, 5), np.linspace(-1, 0.5, 4))
    hm = left.pcolormesh(X, Y, np.arange(12, dtype=float).reshape(3, 4) ** 1.5)
    fig.colorbar(hm, ax=left)
    right.pcolormesh(
        np.linspace(0.1, 0.7, 4),
        np.linspace(3.3, 1.1, 3),
        np.arange(12, dtype=float).reshape(3, 4),
        cmap="RdBu",
        vmin=0,
        pixels=(80, 60),
    )
    return fig


def heatmap_contourf():
    """contourf bands, with the fields the defaults leave out.

    Left: matplotlib's default levels over a meshgrid. Right: explicit
    levels, a reversed palette, vmin and extend='max', at a pixel count.
    """
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    x = np.linspace(0, 4, 41)
    y = np.linspace(-1, 2, 31)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(1.5 * X) * np.cos(Y)
    left.contourf(X, Y, Z)
    right.contourf(
        x,
        y,
        Z,
        [-0.6, -0.2, 0.3, 0.7],
        cmap="RdBu_r",
        vmin=-1,
        extend="max",
        pixels=(120, 90),
    )
    return fig


def heatmap_contourf_smooth():
    """A contourf on a grid too coarse for its bands, drawn smooth instead."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", r"contourf\(\) is drawn as a smooth")
        ax.contourf(np.add.outer(np.arange(4.0), np.arange(5.0)) ** 2, 5, extend="both")
    return fig


def heatmap_contourf_colorbar():
    """contourf bars drawn through the band sub, vertical and horizontal.

    Left: levels below zero and more than ten of them, so the ticks thin.
    Right: a horizontal bar on uneven levels, ticked at even steps.
    """
    fig, (left, right) = glp.subplots(1, 2, figsize=(9, 4), data_prefix="golden")
    x = np.linspace(0, 4, 41)
    y = np.linspace(-1, 2, 31)
    Z = np.sin(1.5 * x)[None, :] * np.cos(y)[:, None]
    fig.colorbar(left.contourf(x, y, Z, np.linspace(-1, 1, 13)))
    cf = right.contourf(x, y, Z, [-0.6, 0.2, 0.5], cmap="plasma")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "colorbar.. of a contourf with unevenly")
        fig.colorbar(cf, orientation="horizontal", label="z", format="fix 2")
    return fig


def heatmap_function():
    """An expression heatmap with a colorbar."""
    fig = glp.figure(figsize=(7, 6), data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.function2d("sin(x)*cos(y)", extent=(0, 6.28, 0, 6.28), vmin=-1, vmax=1)
    fig.colorbar(label="z")
    return fig


def heatmap_function_field_options():
    """Expression heatmap fields :func:`heatmap_function` leaves at defaults.

    The expression has a comma inside brackets and no colour range is
    written (GLE's 0 to 1).
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.function2d(
        "atan2(y,x)",
        extent=(-1, 1, -1, 1),
        cmap="rainbow",
        vmin=None,
        vmax=None,
        pixels=(60, 40),
        invert=True,
    )
    return fig


def contour_grid_levels_clabel():
    """Gridded contour (contour(x, y, Z)) with explicit levels + clabels."""
    fig = glp.figure(figsize=(7, 6), data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 26)
    y = np.linspace(0, 8, 21)
    Z = np.sin(x[None, :] / 6.0) * np.cos(y[:, None] / 5.0)
    ax.contour(
        x,
        y,
        Z,
        levels=[-0.5, 0.0, 0.5],
        colors="black",
        linewidths=1.0,
        clabel=True,
        clabel_fmt="fix 2",
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    return fig


def contour_field_options():
    """Contour fields the other builders leave at their defaults.

    A dashed, wider gridded contour at GLE's default levels, and a dotted
    scattered contour with no ``ncontour`` (which only a recovered script
    leaves unset, so it is cleared on the series here); neither is labelled.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 4, 5)
    y = np.linspace(0, 3, 4)
    Z = x[None, :] + y[:, None]
    ax.contour(x, y, Z, colors="red", linewidths=2, linestyles="--")
    xs = np.array([0.0, 4.0, 0.0, 4.0, 2.0])
    ys = np.array([0.0, 0.0, 3.0, 3.0, 1.5])
    ax.tricontour(
        xs,
        ys,
        xs * ys,
        gridsize=(5, 4),
        extent=(0, 4, 0, 3),
        levels=[2.0, 6.0],
        colors="blue",
        linestyles=":",
    )
    ax.contours[1]["ncontour"] = None
    return fig


def tripcolor_tricontour_combo():
    """Scattered tripcolor + tricontour on one axes, with a colorbar."""
    fig = glp.figure(figsize=(8, 6), data_prefix="golden")
    ax = fig.add_subplot(111)
    rng = np.random.default_rng(7)
    xs = rng.uniform(0, 10, 150)
    ys = rng.uniform(0, 8, 150)
    zs = np.sin(xs) * np.cos(ys)
    ax.tripcolor(xs, ys, zs, gridsize=(51, 41), extent=(0, 10, 0, 8), cmap="magma")
    ax.tricontour(
        xs,
        ys,
        zs,
        gridsize=(51, 41),
        extent=(0, 10, 0, 8),
        ncontour=3,
        levels=[-0.4, 0.0, 0.4],
        colors="white",
        clabel=True,
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    fig.colorbar(label="z", format="fix 1")
    return fig


def custom_tick_labels():
    """xplaces/xnames + yplaces/ynames (explicit set_xticks/set_yticks)."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue", label="quad")
    ax.set_xticks([0, 1, 2], ["a", "b", "c"])
    ax.set_yticks([0, 2, 4], ["low", "mid", "high"])
    ax.legend()
    return fig


def no_ticks():
    """``set_xticks([])`` / ``set_yticks([])``: no ticks and no labels (#181)."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue")
    ax.set_xticks([])
    ax.set_yticks([])
    return fig


def no_ticks_styled():
    """Empty tick lists on a gridded axis and beside a styled one.

    Styling an axis with no ticks is not written (there is nothing to style),
    so only the axes that keep their ticks are styled here.
    """
    fig, (gridded, styled) = glp.subplots(1, 2, data_prefix="golden")
    gridded.plot([0, 1, 2], [0, 1, 4], color="blue")
    gridded.grid(True)
    gridded.set_xticks([])
    gridded.set_yticks([0, 2, 4])
    styled.plot([0, 1, 2], [1, 2, 3], color="green")
    styled.tick_params(axis="x", direction="out", length=5, color="red")
    styled.set_yticks([])
    return fig


def no_ticks_twins():
    """Empty tick lists under twin scales, and beside hidden axis lines.

    GLE copies ``yticks off``/``ylabels off`` onto y2, so a twin scale is
    switched back on; four ``... off`` lines that are not ``axis('off')``
    must not be read back as a hidden frame.
    """
    fig, (twinned, sides) = glp.subplots(1, 2, data_prefix="golden")
    twinned.plot([0, 1, 2], [0, 1, 4], color="blue")
    twinned.twinx().plot([0, 1, 2], [5, 6, 7], color="red")
    twinned.twiny().plot([10, 20, 30], [1, 2, 3], color="green")
    twinned.set_xticks([])
    twinned.set_yticks([])
    sides.plot([0, 1, 2], [4, 1, 0], color="red")
    sides.set_xticks([])
    sides.set_yticks([])
    sides.set_axis_line("x", visible=False)
    sides.set_axis_line("y", visible=False)
    return fig


def tick_intervals():
    """``dticks``/``dsubticks`` on x and y (set_xticks/set_yticks, #155)."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue", label="quad")
    ax.set_xticks(dticks=0.5, dsubticks=0.25)
    ax.set_yticks(dticks=1, dsubticks=0.5)
    ax.legend()
    return fig


def tick_label_nofirst_nolast():
    """``nofirst``/``nolast`` on both x and y.

    No layout sets ``nofirst`` on y; a recovered ``yaxis ... nofirst`` does,
    so the flags are set on the axes here.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue", label="quad")
    ax._remove_first_xtick = ax._remove_last_xtick = True
    ax._remove_first_ytick = ax._remove_last_ytick = True
    ax.legend()
    return fig


def axes_styling_full():
    """Every axes-styling field at once: formats, a subtick grid with style,
    axis-title and tick-label size/colour/angle, and a styled graph title."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], color="blue", label="quad")
    ax.set_title("Styled")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_ylabel("Y2", axis="y2")
    ax.set_ylim(0, 10, axis="y2")
    ax.set_tick_format("fix 1", axis="x")
    ax.set_tick_format("sci 2 10", axis="y2")
    ax.grid(True, which="both", linestyle=":", linewidth=0.4, color="gray40")
    ax.title_size, ax.title_color, ax.title_dist = 14, "RED", 0.3
    ax.xlabel_size, ax.xlabel_color, ax.xlabel_dist = 10, "BLUE", 0.35
    ax.ylabel_size, ax.ylabel_color = 9, "GREEN"
    ax.y2label_size = 8
    ax.xticklabel_size, ax.xticklabel_color, ax.xticklabel_angle = 7, "ORANGE", 45
    ax.yticklabel_color = "CYAN"
    ax.y2ticklabel_size = 6
    ax.legend()
    return fig


def axis_lines_fonts_and_tick_placement():
    """Title fonts, axis-line colour and width, and GLE tick placement."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9], color="blue", label="quad")
    ax.set_ylim(0, 20, axis="y2")
    ax.set_title("Fonts", fontname="texcmb")
    ax.set_xlabel("t", fontname="texcmr")
    ax.set_ylabel("y", fontname="texcmss")
    ax.set_ylabel("y2", axis="y2", fontname="texcmtt")
    ax.set_axis_line(color="gray", linewidth=1.2)
    ax.set_axis_line("x2", color="red")
    ax.set_axis_line("y2", linewidth=0.5)
    ax.set_xticks(nticks=4, ftick=0, shift=0.25, noticks=[2])
    ax.set_yticks(symticks=True, noticks=[1, 4])
    ax.legend()
    return fig


def title_text_keywords():
    """matplotlib's fontsize, color and labelpad/pad on the title setters."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue")
    ax.set_title("Run 12", fontsize=11, color="#404040", pad=6)
    ax.set_xlabel("T (K)", fontsize=9, color="gray", labelpad=4)
    ax.set_ylabel("y", fontsize="small")
    ax.twinx().set_ylabel("y2", color="red", labelpad=3)
    return fig


def tick_marks_and_minor_ticks():
    """Tick-mark length, width, colour and direction, and minor ticks."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(121)
    ax.plot([1, 10, 100], [1, 2, 3], color="blue")
    ax.set_xscale("log")
    ax.tick_params(axis="x", length=4, width=0.8, direction="out", color="red")
    ax.tick_params(axis="y", which="minor", length=2, color="gray")
    ax.minorticks_on()
    ax.set_xticks(loglabels="l25", nofirst=True)
    ax.set_yticks(nsubticks=4, nolast=True)
    right = fig.add_subplot(122)
    right.plot([0, 1, 2], [2, 0, 1], color="green")
    right.tick_params(direction="inout", length=6)
    right.minorticks_off()
    return fig


def math_mode_axes():
    """Axes crossing at the origin (GLE math mode)."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([-2, -1, 0, 1, 2], [3, 0, -1, 0, 3], color="blue")
    ax.set_title("Math mode")
    ax.set_math_mode()
    return fig


def hidden_axis_lines():
    """Axis lines hidden per side: the open frame, and a lone bottom line."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(121)
    ax.plot([0, 1, 2], [0, 1, 4], color="blue")
    ax.set_title("Open")
    ax.set_axis_line("x2", visible=False)
    ax.set_axis_line("y2", visible=False)
    right = fig.add_subplot(122)
    right.plot([0, 1, 2], [4, 1, 0], color="red")
    right.set_axis_line("x", color="gray", visible=False)
    right.set_axis_line("y", visible=False)
    right.set_axis_line("y2", color="green")
    return fig


def line_modes():
    """Step, histogram-outline and stem line modes on one axes."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.step(x, [1, 2, 2, 1], where="pre", color="blue", label="pre")
    ax.step(x, [1, 3, 1, 2], where="post", color="red")
    ax.plot(x, [0, 1, 0, 1], drawstyle="steps-mid", color="green", label="mid")
    ax.stem(x, [1, 0, 1, 0], label="stem")
    ax.legend()
    return fig


def line_field_options():
    """Line fields no other builder sets: offset, ``nomiss`` and smoothing.

    ``nomiss``, ``smooth_mode`` and ``svg_smooth`` have no ``plot`` keyword;
    a recovered file sets them, so they are set on the series here. The
    figure-wide default is smooth so that every line is smoothed: the
    recognizer infers that default from the lines, and a mix would change it.
    """
    fig = glp.figure(data_prefix="golden", graph=glp.GLEGraphConfig(smooth_curves=True))
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.plot(x, [1, 2, 1, 2], color="blue", offset=1.5, label="shifted")
    ax.plot(x, [0, 1, 0, 1], color="red", label="joined")
    ax.plot(x, [2, 3, 2, 3], color="green", label="smoothed")
    ax.lines[1]["nomiss"] = True
    ax.lines[2]["smooth_mode"] = "smoothm"
    ax.lines[2]["svg_smooth"] = 2
    ax.legend()
    return fig


def dataset_qualifiers():
    """GLE's ``mdist``, ``deresolve [average]`` and data-range qualifiers.

    On a marked line, a line, a scatter, and a line and an errorbar file
    reference. File references get them only from a recovered script, so
    they are set on the series there.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0.0, 6.0, 25)
    ax.plot(x, np.sin(x), color="blue", marker="o", mdist=1.5, label="spaced")
    ax.plot(x, np.cos(x), color="red", deresolve=3, deresolve_average=True)
    ax.plot(x, 0.1 * x, color="green", deresolve=2, xmin=1.0, ymax=0.5, label="cut")
    ax.scatter(x, 0.2 * x, color="black", marker="s", xmax=4.0, ymin=0.1)
    ax.line_from_file("external.dat", 1, 2, color="blue")
    ax.file_series[0].update(
        marker="CIRCLE", markersize=0.2, mdist=2.0, deresolve=4, xmin=0.5
    )
    ax.errorbar_from_file("external.dat", 1, 2, yerr_col=3, color="red", marker="o")
    ax.file_series[1].update(deresolve=2, deresolve_average=True, ymax=3.0)
    ax.legend()
    return fig


def scatter_field_options():
    """Scatter fields the other builders leave at their defaults.

    A labelled scatter on the y2 and x2 axes, a marker-only ``plot`` shifted
    by ``offset``, and an unlabelled scatter, whose header row still needs
    an empty ``key``.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.scatter(x, [3, 1, 2, 0], color="green", marker="^", yaxis="y2", label="top")
    ax.scatter(x, [1, 2, 3, 4], color="red", marker="o", xaxis="x2", label="right")
    ax.plot(
        x,
        [0, 1, 0, 1],
        color="blue",
        linestyle="none",
        marker="s",
        offset=0.5,
        label="shifted",
    )
    ax.scatter(x, [2, 2, 1, 1], color="black", marker="x")
    ax.legend()
    return fig


def scatter_per_point_sizes():
    """Per-point marker sizes (GLE ``mdata`` through a generated marker sub).

    ``s`` and ``markersize`` arrays, two marker shapes sharing nothing, an
    offset, the top axis and a data range, and a size of 0.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.scatter(x, [1, 2, 3, 4], s=[10, 40, 90, 0], color="red", label="bubbles")
    ax.scatter(
        x,
        [4, 3, 2, 1],
        markersize=[2, 4, 6, 8],
        marker="s",
        fillstyle="none",
        offset=0.5,
        xaxis="x2",
        ymax=3.0,
    )
    ax.legend()
    return fig


def scatter_per_point_colours():
    """Per-point colours (GLE ``mdata`` through a generated colour sub).

    Values with explicit limits (a negative ``vmin``, values outside them),
    the default limits on the top axis with an offset and a data range,
    equal limits on a built-in palette, and a colour sequence.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.scatter(
        x,
        [1, 2, 3, 4],
        c=[-2, 5, 7.5, 12],
        cmap="plasma_r",
        vmin=-1.5,
        vmax=10,
        label="mapped",
    )
    ax.scatter(
        x,
        [4, 3, 2, 1],
        c=[0.25, 0.5, 0.75, 1.0],
        marker="s",
        fillstyle="none",
        offset=0.5,
        xaxis="x2",
        ymax=3.0,
    )
    ax.scatter(x, [2, 2, 2, 2], c=[3, 3, 3, 3], cmap="gray", marker="^")
    ax.scatter(x, [3, 1, 3, 1], c=["red", "blue", "red", "green"], label="listed")
    ax.legend()
    return fig


def scatter_colorbars():
    """A colorbar on each of two colour-mapped scatters.

    A vertical bar on the last of two mapped scatters in one axes, and a
    horizontal bar on a built-in palette with its own label, width and gap.
    """
    fig, (a, b) = glp.subplots(1, 2, data_prefix="golden")
    a.scatter([0, 1, 2], [1, 2, 3], c=[1, 2, 3], cmap="magma")
    a.scatter([0, 1, 2], [3, 2, 1], c=[-4, 0, 9.5], vmin=-5, vmax=10)
    fig.colorbar(ax=a, label="T (K)", nticks=3)
    b.scatter([0, 1, 2], [1, 2, 3], c=[10, 20, 30], cmap="gray", marker="s")
    fig.colorbar(
        ax=b, orientation="horizontal", label="v", format="fix 0", width=0.3, sep=1.2
    )
    return fig


def fill_forms():
    """Axis fill, a clipped band, and a closed polygon."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.fill_between(x, [1, 2, 2, 1], baseline="x1", color="gray", label="axis")
    ax.fill_between(
        x,
        [1, 3, 2, 2],
        [0, 1, 1, 0],
        where=[False, True, True, False],
        color="blue",
        alpha=0.4,
    )
    ax.fill([0, 1, 0.5], [0, 0, 1], color="red", alpha=0.4, label="poly")
    ax.legend()
    return fig


def fill_field_options():
    """Fill fields the other builders leave at their defaults.

    An offset band with its own key swatch colour (a recovered ``keyfill``),
    and a fill to the top axis clipped in y.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.fill_between(
        x, [2, 3, 3, 2], [1, 1, 1, 1], offset=0.5, color="green", label="shifted"
    )
    ax.fills[0]["swatch_color"] = "BLACK"
    ax.fill_between(
        x, [1, 2, 2, 1], baseline="x2", ymin=0.5, ymax=2.5, color="orange", label="top"
    )
    ax.legend()
    return fig


def fill_orientations():
    """``fill_betweenx`` with a ``where`` mask, and a symmetric ``stackplot``."""
    fig = glp.figure(data_prefix="golden")
    left, right = fig.add_subplot(121), fig.add_subplot(122)
    y = [0, 1, 2, 3]
    left.fill_betweenx(y, [1, 2, 2, 1], [0, 0.5, 0.5, 0], color="green", label="x")
    left.fill_betweenx(y, 3, where=[False, True, True, True], alpha=0.4)
    left.legend()
    right.stackplot([0, 1, 2], [1, 2, 1], [2, 1, 2], labels=["a", "b"], baseline="sym")
    right.legend()
    return fig


def segment_lines():
    """``vlines`` in two colours and dashed ``hlines``: lines with ``*`` gaps."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.vlines([1, 2, 3, 4], 0, [3, 1.5, 4, 2], colors=["k", "red"], label="peaks")
    ax.hlines([0.5, 3.5], 0.5, [3, 4.5], linestyles="dashed", lw=2)
    ax.legend()
    return fig


def histogram():
    """One step outline and one filled histogram, both labelled."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.hist(
        [0, 0.2, 0.4, 0.6, 0.9],
        bins=4,
        range=(0, 1),
        histtype="step",
        color="blue",
        label="step",
    )
    ax.hist(
        [0.1, 0.3, 0.5, 0.7],
        bins=4,
        range=(0, 1),
        histtype="stepfilled",
        color="red",
        label="filled",
    )
    ax.legend()
    return fig


def function_curves():
    """Two GLE-sampled curves: one with a range, step, style and label, one bare."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.function(
        "exp(-x^2/2)",
        xmin=-3,
        xmax=3,
        step=0.1,
        color="red",
        linestyle="--",
        linewidth=2,
        label="gauss",
    )
    ax.function("x/3")
    ax.legend()
    return fig


def function_curves_beside_modelled_lets():
    """Function and derived curves after a histogram's and a colour's ``let``.

    Each function curve has a series after it, so one kept raw would move.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.hist([0, 0.2, 0.4, 0.6, 0.9], bins=4, range=(0, 1), histtype="step")
    ax.function("sin(x)", xmin=0, xmax=1)
    ax.errorbar([0.2, 0.5], [0.3, 0.6], yerr=[0.1, 0.1])
    ax.scatter([0.1, 0.4, 0.8], [0.2, 0.5, 0.7], c=[0.1, 0.5, 0.9])
    ax.function("x/2", xmin=0, xmax=1)
    ax.plot([0, 1], [1, 0])
    ax.derived("d1*2", [ax.lines[0]])
    ax.plot([0, 1], [0.5, 0.5])
    return fig


def one_point_default_width():
    """A 1 pt default width: each kind's ``lwidth 0.03528`` comes back as 1 pt.

    The writer reads 1 pt as "the style default", so a recovered 1 pt width
    is kept as given rather than widened to the default it was loaded with.
    """
    fig = glp.figure(
        style=glp.GLEStyleConfig(default_linewidth=1.0), data_prefix="golden"
    )
    ax = fig.add_subplot(131)
    ax.plot([0, 1, 2], [1, 2, 1], label="line")
    ax.errorbar([0, 1, 2], [2, 3, 2], yerr=0.2, fmt="o-")
    ax.hist([0.2, 0.4, 0.4, 1.6], bins=2, range=(0, 2), histtype="step")
    ax.axhline(1.5, label="guide")
    ax.legend()
    curves = fig.add_subplot(132)
    curves.function("x/2", xmin=0, xmax=2)
    curves.contour([[0.0, 1.0, 2.0], [1.0, 2.0, 3.0]], levels=[1.5])
    # Nothing resolves the y range, so this guide is drawn after the graph.
    guides = fig.add_subplot(133)
    guides.axvline(1.0, label="drawn")
    guides.set_xlim(0, 2)
    guides.legend()
    return fig


def guides_after_graph():
    """Guides on an axis gleplot cannot range, drawn after ``end graph``.

    A dashed, labelled line; one over a fraction of the frame; one with no
    line; a translucent labelled band with its own swatch; and a band over a
    fraction. The second axes' collapsed range sends its guides there too.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(121)
    ax.set_ylim(-3.0, None)
    ax.axvline(0.5, color="red", linestyle="--", linewidth=2.0, label="cut")
    ax.axvline(0.7, ymin=0.2, ymax=0.6)
    ax.axvline(0.8, linestyle="none")
    band = ax.axvspan(0.1, 0.3, color="orange", alpha=0.35, label="window")
    band["swatch_color"] = "BLUE"
    ax.axvspan(-0.4, -0.2, ymin=0.25)
    ax.legend()
    point = fig.add_subplot(122)
    point.plot([5.0], [7.0], marker="o")
    point.axhline(7.0, xmin=0.1, xmax=0.9, label="level")
    point.axhspan(6.0, 8.0, xmin=0.5)
    point.legend()
    return fig


def fit_curves():
    """Two GLE-fitted curves: one with a range, step, style and label, one bare."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0.0, 4.0, 9)
    ax.scatter(x, 2.0 * np.exp(-x / 1.5) + 0.3)
    ax.fit(
        x,
        2.0 * np.exp(-x / 1.5) + 0.3,
        "a*exp(-x/b)+c",
        xmin=0,
        xmax=5,
        step=0.05,
        color="red",
        linestyle="--",
        linewidth=2,
        label="decay",
    )
    ax.fit(x, 0.5 * x, "k*x")
    ax.legend()
    return fig


def closed_form_fits():
    """The four closed-form fits: ranged, styled and labelled, and bare."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(1.0, 4.0, 7)
    y = 1.5 * x**1.3
    ax.scatter(x, y)
    ax.fit(x, y, model="linear", xmin=0.5, xmax=4.5, label="linear")
    ax.fit(x, y, model="exp", color="red", linestyle=":")
    ax.fit(x, y, model="exp10", linewidth=2)
    ax.fit(x, y, model="power", xmin=1, label="power")
    ax.legend()
    return fig


def fit_result_legends():
    """Fit results in two subplots' legends, beside a plain entry."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    x = np.linspace(1.0, 4.0, 7)
    y = 1.5 * x**1.3
    left.scatter(x, y, label="data")
    left.fit(x, y, model="linear", label="$y$ = {slope:.2f}x + {offset:.2f}")
    left.fit(x, y, model="exp", label="{prefactor:.2e} e^{{exponent}x}", color="red")
    left.legend()
    right.fit(x, y, model="power", label="r$^2$ = {rsq:.3f}")
    right.fit(x, y, model="exp10", label="plain")
    right.legend(loc="lower right")
    return fig


def derived_curves():
    """Curves GLE computes from other series, with each option.

    Sources of every accepted kind, one with an offset (read without it),
    and a file line; then ``from``/``to``/``nsteps``, ``where``, ``range``
    and a ``step``. Each names its sources in the order they first appear,
    which is the order the recognizer gives them.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0.0, 4.0, 9)
    ax.plot(x, x**2, label="square")
    ax.scatter(x, x, offset=1.0)
    ax.line_from_file("external.dat", 1, 2, color="blue")
    ax.function("sin(x)", xmin=0, xmax=4)
    ax.fit(x, 0.5 * x, model="linear")
    ax.derived(
        "d1-d2",
        [ax.lines[0], ax.file_series[0]],
        color="red",
        linestyle="--",
        linewidth=2,
        label="difference",
    )
    ax.derived(
        "d1*d2+d3",
        [ax.fits[0], ax.functions[0], ax.scatters[0]],
        xmin=0,
        xmax=4,
        nsteps=20,
        where="d3>1",
        range=ax.fits[0],
    )
    ax.derived("(d1+d2)/2", [ax.lines[0], ax.scatters[0]], xmin=1, step=0.5)
    ax.legend()
    return fig


def histogram_field_options():
    """Histogram fields the other builders leave at their defaults.

    A dashed, wider step outline on the y2 and x2 axes, a stepfilled
    histogram with an edge colour, and a bin width (``bin_step``) in place of
    a bin count, which only a recovered script sets.
    """
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    samples = [0.1, 0.3, 0.35, 0.6, 0.8]
    ax.hist(
        samples,
        bins=4,
        range=(0, 1),
        histtype="step",
        linestyle="--",
        linewidth=2,
        yaxis="y2",
        xaxis="x2",
        color="green",
        label="dashed",
    )
    ax.hist(
        samples,
        bins=4,
        range=(0, 1),
        histtype="stepfilled",
        edgecolor="black",
        color="red",
        label="edged",
    )
    ax.hist(samples, bins=4, range=(0, 1), histtype="step", color="blue")
    stepped = ax.hists[2]
    del stepped["bins"]
    stepped["bin_step"] = 0.25
    ax.legend()
    return fig


def axes_styling_grid_only():
    """The plainest grid: no style clause, no other styling."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="red")
    ax.grid(True)
    return fig


def contour_in_second_subplot():
    """A contour on the second subplot: its block sits between the graphs."""
    fig, axs = glp.subplots(1, 2, data_prefix="golden")
    axs[0].plot([0, 1], [0, 1])
    x = np.linspace(0, 4, 5)
    y = np.linspace(0, 3, 4)
    axs[1].contour(x, y, x[None, :] + y[:, None], levels=[2.0])
    return fig


def trailer_stray_amoves():
    """Two ``amove``s after the last graph: neither prefixes a graph block."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4])
    fig.passthrough_trailer = ["amove 1 1", "amove 2 2"]
    return fig


def trailer_amove_after_subplots():
    """#216: an ``amove`` trailer after a subplot grid's last blank line."""
    fig = glp.figure(data_prefix="golden")
    fig.add_subplot(121).plot([0, 1], [0, 1])
    fig.add_subplot(122).plot([0, 1], [1, 0])
    fig.passthrough_trailer = ["amove 1 1", "circle 0.4"]
    return fig


def pie_chart():
    """A titled pie with labels and percentages, then a text drawn after it."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.pie(
        [15, 30, 45, 10],
        labels=["Frogs", "Hogs", "Dogs", "Logs"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("pets")
    ax.text(0, 1.2, "after", ha="center")
    return fig


def pie_field_options():
    """Off-centre pies beside a line plot: colours, fontsize, no labels."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    left.plot([0, 1], [0, 1], color="blue")
    right.text(2, 1, "centre", color="red")
    right.pie(
        [0.2, 0.3],
        labels=["a", "b"],
        colors=["red", "#00ff00"],
        textprops={"fontsize": 14},
        center=(2, 1),
        radius=0.8,
        counterclock=False,
        normalize=False,
    )
    right.pie([1, 1, 2], labeldistance=None, center=(2, 1), radius=0.3)
    return fig


def line_cap_join_dashlen():
    """Page-level ``set cap``/``set join``/``set dashlen`` from the style."""
    style = glp.GLEStyleConfig(line_cap="round", line_join="bevel", dashlen=0.125)
    fig = glp.figure(style=style, data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0], color="black", linewidth=4)
    ax.plot([0, 1, 2], [1, 0, 1], color="red", linestyle="--")
    return fig


def boxplot_chart():
    """Labelled boxes with fliers and means, then a text drawn after them."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.boxplot(
        [[1.5, 2.25, 3, 3.5, 4, 9.75], [2, 3, 4], [-1, 0.5, 1, 1.25, 1.5, 6]],
        tick_labels=["low", "mid", "$\\alpha$"],
        showmeans=True,
    )
    ax.set_title("spread")
    ax.text(2, 8, "after", ha="center")
    return fig


def boxplot_field_options():
    """Boxes beside a line plot: positions, widths, no caps, percentiles."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    left.plot([0, 1], [0, 1], color="blue")
    right.plot([0, 10], [0, 4], color="red")
    right.boxplot(
        np.array([[0.5, 1.0], [1.0, 2.0], [2.0, 2.5], [3.0, 3.5]]),
        positions=[2, 6],
        widths=[1, 2],
        whis=(10, 90),
        showcaps=False,
        usermedians=[None, 2.75],
        manage_ticks=False,
    )
    right.boxplot([1, 1, 1, 1, 4], positions=[8], capwidths=0.5, autorange=True)
    return fig


def rug_field_options():
    """Rugs on every edge beside a scatter and a box, in two subplots."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    left.scatter([1.25, 2, 3.5], [0.5, 2, 1.5], color="C0")
    left.rug([1.25, 2, 3.5], color="C0")
    left.rug([0.5, 2, 1.5], axis="y", position="right", length=-0.2)
    left.rug([4.75], position="top", color="red", linewidth=0.5)
    right.boxplot([1, 2, 3, 9])
    right.rug([1, 2, 3, 9], axis="y", position="both", linewidth=2)
    right.rug([0.5, 1.5], position="both", length=0.15)
    return fig


def usetex_labels():
    """Page-level ``set texlabels 1``; labels reach LaTeX as written."""
    fig = glp.figure(style=glp.GLEStyleConfig(usetex=True), data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], label=r"$y = x^2$")
    ax.set_xlabel(r"$\mu_0 H$ (T)")
    ax.set_title(r"run\_01")
    ax.text(1, 2, r"$\sqrt{5}$")
    ax.legend()
    return fig


def page_drawings():
    """Every page drawing kind over a plot, then a trailer line after them."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4])
    fig.circle(2, 3, radius=0.4, fill="red", color="blue", linewidth=2)
    fig.ellipse(5, 3, 2, 1, fill="#10c810")
    fig.circle(8, 8, 0.3, fill="blue", color="none")
    fig.arc(5, 6, 1, 20, 160, linewidth=0.5)
    fig.bezier([1, 2, 3, 4], [1, 3, -1, 1])
    fig.curve([6.1, 7.2, 8.3], [1, 2.2, 1], (1, 0), (1, -0.5), color="green")
    fig.polygon([7, 9, 8], [5, 5, 7], fill="yellow", color="black")
    fig.polygon([1, 2, 2, 1], [8, 8, 9, 9])
    fig.polygon([3, 4, 4], [8, 8, 9], fill="gray", color="none")
    fig.table(0.5, 7, "a   bb   c\n1   22   333")
    fig.tex(0.5, 5, r"\textbf{Note} $x^2$")
    fig.passthrough_trailer = ["amove 1 1"]
    return fig


def page_drawings_subplots():
    """Page drawings after a subplot grid's last blank line."""
    fig = glp.figure(data_prefix="golden")
    fig.add_subplot(121).plot([0, 1], [0, 1])
    fig.add_subplot(122).plot([0, 1], [1, 0])
    fig.circle(10, 7.5, radius=1)
    fig.polygon([1, 3, 2], [1, 1, 2], fill="gray")
    return fig


def page_drawings_only():
    """A figure with no axes: the page drawings follow the preamble."""
    fig = glp.figure(data_prefix="golden")
    fig.ellipse(4, 3, 3, 2, color="red")
    fig.table(1, 1, "x  y\n1  2")
    return fig


def figure_text_and_suptitle():
    """A suptitle over a titled grid, figure texts after page drawings, and
    a trailer line after them."""
    fig, axes = glp.subplots(1, 2, figsize=(8, 4), data_prefix="golden")
    axes[0].plot([0, 1], [0, 1])
    axes[1].plot([0, 1], [1, 0])
    axes[1].set_title("right")
    fig.circle(1, 1, radius=0.3)
    fig.suptitle("Sample A", color="blue", fontsize="x-large")
    fig.text(0.02, 0.98, "(a)", ha="left", va="top")
    fig.text(
        0.6,
        0.03,
        r"$\alpha$ note",
        color="red",
        fontsize=9,
        rotation=15,
        bbox={"facecolor": "white"},
    )
    fig.text(-0.01, 0.5, "edge", ha="right")
    fig.passthrough_trailer = ["amove 1 1"]
    return fig


def figure_text_only():
    """A figure with no axes: a suptitle placed off its default, and a text."""
    fig = glp.figure(data_prefix="golden")
    fig.suptitle("left title", x=0.1, ha="left")
    fig.text(0.5, 0.5, "centre", ha="center", va="center")
    return fig


def figure_legend():
    """A figure legend over two axes: an addition order that is not the draw
    order, an axes key asked for, an auto key turned off, columns."""
    fig, axes = glp.subplots(1, 2, figsize=(8, 4), data_prefix="golden")
    axes[0].scatter([0, 1], [1, 0], label="points", color="red")
    axes[0].plot([0, 1], [0, 1], label="rise")
    axes[1].plot([0, 1], [1, 0], label="fall", linestyle="--")
    axes[1].bar([0.5], [0.5], width=0.2, label="bar")
    axes[1].legend(loc="upper left")
    fig.legend(loc="lower center", ncol=3, frameon=False, labelcolor="gray")
    fig.subplots_adjust(bottom=0.25)
    return fig


def legend_curves():
    """#236: a histogram and a function curve listed by ``begin key`` blocks,
    an axes legend with ``labelcolor`` and a figure legend."""
    fig, axes = glp.subplots(1, 2, figsize=(8, 4), data_prefix="golden")
    axes[0].plot([0, 1, 2], [0, 1, 0], label="line")
    axes[0].hist([0.2, 0.5, 0.6, 1.4], histtype="step", label="hist")
    axes[0].legend(labelcolor="blue")
    axes[1].scatter([0, 1], [1, 0], label="pts")
    axes[1].function("x", xmin=0, xmax=1, label="f")
    fig.legend(loc="lower center", ncol=4)
    fig.subplots_adjust(bottom=0.25)
    return fig


def figure_legend_options():
    """A figure legend anchored off the page corner, with every option."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0], label="a", marker="o")
    ax.fill_between([0, 1, 2], [0, 0.5, 0], color="green", alpha=0.3, label="b")
    fig.legend(
        loc="center left",
        bbox_to_anchor=(0.8, 0.5, 0.2, 0.2),
        fontsize=10,
        facecolor="lightyellow",
        borderpad=0.3,
        handlelength=1.5,
        handletextpad=0.5,
        columnspacing=1.0,
        ncol=2,
    )
    return fig


def polar_plot():
    """A titled polar axes: a marked line, a function curve and a scatter."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(projection="polar")
    theta = np.linspace(0, 2 * np.pi, 9)
    ax.plot(theta, 1 + 0.5 * np.cos(3 * theta), marker="o", label="lobes")
    ax.function("cos(2*x)", color="green", linestyle="--", label="rose")
    ax.scatter([0.5, 3, 4], [0.3, 1.1, 0.7], color="red")
    ax.set_title("polar")
    ax.legend()
    return fig


def polar_field_options():
    """A polar axes after a cartesian one with text: an explicit radial limit
    off the ring step, and a function range and step.
    """
    fig = glp.figure(figsize=(8, 3), data_prefix="golden")
    left = fig.add_subplot(1, 2, 1)
    left.plot([0, 1], [0, 1], color="blue")
    left.text(0.5, 0.5, "left", color="red")
    right = fig.add_subplot(1, 2, 2, projection="polar")
    right.plot([0, 1, 2, 3], [0.2, 0.8, 1.2, 0.4], color="black", linewidth=2)
    right.function("x/4", xmin=0, xmax=4, step=0.1)
    right.set_ylim(0, 1.3)
    return fig


def placed_images():
    """A bitmap and an EPS under a line, a bitmap alone on a log axes."""
    fig, (left, right) = glp.subplots(1, 2, data_prefix="golden")
    left.image("figures/micrograph.png", extent=(0, 10, 0, 5))
    left.plot([0, 12], [1, 4], color="red")
    left.image("logo.EPS", extent=(8.5, 11.25, -1, 0.5))
    right.image("my photos/scan.jpeg", extent=(1, 100, 0.5, 2.5))
    right.set_xscale("log")
    return fig


def data_beyond_six_figures():
    """Columns that six significant figures would merge, zero or cut."""
    fig, (left, right, grid) = glp.subplots(1, 3, data_prefix="golden")
    stamps = 1.7e9 + np.array([0.0, 60.0, 121.0])
    left.plot(stamps, [1.0, 2.0, 3.0])
    left.set_xlim(stamps[0], stamps[-1])
    left.plot(stamps, [1e-12, 2.5e-12, 4e-12])
    right.plot([1.23456789e12, 2.5e12], np.cos([0.0, np.pi / 2]))
    # On its own axes: other data would reach past the grid's last node.
    grid.imshow(1.0 + 1e-8 * np.arange(6.0).reshape(2, 3), extent=(0, 3, 0, 2))
    return fig


def coordinates_beyond_six_figures():
    """Lone coordinates on a timestamp axis: guides, text, ticks, a limit."""
    fig, (left, right, ticks, narrow) = glp.subplots(1, 4, data_prefix="golden")
    ticks.plot([1.7e9, 1.7e9 + 120], [1.0, 3.0])
    ticks.set_xticks(dticks=30, ftick=1.7e9 + 30)
    ticks.rug([1.7e9 + 30, 1.7e9 + 60])
    ticks.axhspan(1.5, 2.5)
    # A band narrower than its axis: marker and fill must write it alike.
    narrow.plot([4.156750504153, 4.156755839588], [1.0, 2.0])
    narrow.axvspan(4.156746290208, 4.156748511543)
    left.plot([1.7e9, 1.7e9 + 120], [1.0, 3.0])
    left.axvline(1.7e9 + 30)
    left.axvspan(1.7e9 + 40, 1.7e9 + 40.5)
    left.text(1.7e9 + 90, 2.0, "t")
    left.set_xticks([1.7e9 + 30])
    right.plot([1.0, 2.0], [1.7e9, 1.7e9 + 120], yaxis="y2")
    right.set_ylim(1.7e9 + 30, None, axis="y2")
    return fig


BUILDERS = [
    coordinates_beyond_six_figures,
    single_line,
    multi_series_styles,
    scatter,
    bar,
    bar_edge,
    bar_per_color,
    bar_stack,
    bar_missing,
    bar_recovered_fields,
    bar_hatch,
    barh,
    bar_yerr,
    barh_xerr,
    errorbar_symmetric,
    errorbar_asymmetric_xy,
    errorbar_field_options,
    errorbar_data_range,
    fill_between,
    raw_lines_reading_modelled_datasets,
    text_annotations,
    axes_fraction_text,
    annotations_with_arrows,
    secondary_yaxis,
    axis_helpers,
    secondary_xaxis,
    legend_positions_all,
    legend_full_options,
    legend_spacing,
    legend_anchored,
    subplots_sharex,
    subplots_sharex_with_colored_text,
    subplots_grid_mixed,
    subplots_spanning,
    inset_axes,
    inset_facecolor,
    insets_off_panel,
    inset_alone,
    aspect_ratios,
    file_series,
    file_series_data_range,
    errorbar_thinned_from_a_file,
    file_series_without_a_line,
    log_axis_without_major_ticks,
    line_with_nan_gaps,
    file_series_field_options,
    file_series_read_options,
    large_markersize_and_linewidth,
    exact_rgb_colors,
    custom_figsize_and_dpi,
    heatmap_imshow_colorbar,
    heatmap_grid_colorbars,
    heatmap_field_options,
    heatmap_inverted_colorbars,
    heatmap_brewer_palettes,
    heatmap_reversed_palettes,
    heatmap_pcolormesh,
    heatmap_contourf,
    heatmap_contourf_smooth,
    heatmap_contourf_colorbar,
    heatmap_function,
    heatmap_function_field_options,
    contour_grid_levels_clabel,
    contour_field_options,
    tripcolor_tricontour_combo,
    custom_tick_labels,
    no_ticks,
    no_ticks_styled,
    no_ticks_twins,
    tick_intervals,
    tick_label_nofirst_nolast,
    line_modes,
    line_field_options,
    dataset_qualifiers,
    scatter_field_options,
    scatter_per_point_sizes,
    scatter_per_point_colours,
    scatter_colorbars,
    fill_forms,
    fill_field_options,
    fill_orientations,
    segment_lines,
    histogram,
    function_curves,
    function_curves_beside_modelled_lets,
    one_point_default_width,
    guides_after_graph,
    fit_curves,
    closed_form_fits,
    fit_result_legends,
    derived_curves,
    histogram_field_options,
    axes_styling_full,
    axis_lines_fonts_and_tick_placement,
    title_text_keywords,
    tick_marks_and_minor_ticks,
    math_mode_axes,
    hidden_axis_lines,
    axes_styling_grid_only,
    contour_in_second_subplot,
    trailer_stray_amoves,
    trailer_amove_after_subplots,
    pie_chart,
    pie_field_options,
    line_cap_join_dashlen,
    boxplot_chart,
    boxplot_field_options,
    rug_field_options,
    usetex_labels,
    page_drawings,
    page_drawings_subplots,
    page_drawings_only,
    figure_text_and_suptitle,
    figure_text_only,
    figure_legend,
    legend_curves,
    figure_legend_options,
    polar_plot,
    polar_field_options,
    placed_images,
    data_beyond_six_figures,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]

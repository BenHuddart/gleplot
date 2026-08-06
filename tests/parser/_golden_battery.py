"""Shared golden-battery figure builders for the writer-refactor guard test.

Reuses the same battery style as ``tests/integration/test_project_io.py``:
each builder is a zero-argument callable constructing a fresh
:class:`gleplot.Figure` exercising a distinct writer code path (series
types, subplots, text, y2 axis, file-series, legends, log scales, etc.).
``test_units.py`` snapshots ``_generate_gle_with_files()`` output for every
builder before and after the units/tables refactor and asserts byte-for-byte
identity, guarding the "zero behavior change" requirement for Track A2.
"""

import numpy as np

import gleplot as glp


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


def fill_between():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), x**0.5, color="lightblue", alpha=0.4)
    ax.plot(x, x**0.5, color="blue")
    return fig


def text_annotations():
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.text(1.5, 2.0, "peak", color="red", fontsize=14, ha="center")
    ax.text(2.5, 1.0, "boxed", bbox={"facecolor": "yellow"})
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
    axes[0].plot([1, 2, 3], [1, 2, 3])
    axes[1].scatter([1, 2, 3], [3, 2, 1], marker="o")
    axes[2].bar([1, 2, 3], [2, 4, 6], color="red")
    axes[3].errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, capsize=3)
    fig.subplots_adjust(hspace=0.4, wspace=0.4)
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


def axes_styling_grid_only():
    """The plainest grid: no style clause, no other styling."""
    fig = glp.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 4], color="red")
    ax.grid(True)
    return fig


BUILDERS = [
    single_line,
    multi_series_styles,
    scatter,
    bar,
    errorbar_symmetric,
    errorbar_asymmetric_xy,
    fill_between,
    text_annotations,
    secondary_yaxis,
    legend_positions_all,
    legend_full_options,
    subplots_sharex,
    subplots_sharex_with_colored_text,
    subplots_grid_mixed,
    file_series,
    large_markersize_and_linewidth,
    exact_rgb_colors,
    custom_figsize_and_dpi,
    heatmap_imshow_colorbar,
    contour_grid_levels_clabel,
    tripcolor_tricontour_combo,
    custom_tick_labels,
    axes_styling_full,
    axes_styling_grid_only,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]

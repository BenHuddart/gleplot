"""matplotlib's axis helper methods, each a thin layer over existing output.

``twinx`` is the view of the right-hand scale (``yaxis='y2'``), ``invert_*``
stores descending limits (GLE ``negate``), ``semilogx``/``semilogy``/
``loglog`` set the scale and plot, ``set_*ticklabels`` writes ``xnames``,
and ``axis('off')`` hides the frame.
"""

import re
import warnings

import numpy as np
import pytest

import gleplot as glp


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return fig._generate_gle()


def _axes():
    fig = glp.figure(data_prefix="helpers")
    return fig, fig.add_subplot(111)


def _axis_line(text, name):
    match = re.search(rf"^\s*{name} (.*)$", text, re.MULTILINE)
    return match.group(1) if match else None


# -- twinx ------------------------------------------------------------------


def test_twinx_plots_on_the_right_scale_like_yaxis_y2():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3], color="blue")
    right = ax.twinx()
    right.plot([1, 2, 3], [10, 20, 30], color="red")
    right.set_ylim(0, 40)
    right.set_ylabel("right")
    right.set_yscale("linear")
    right.set_tick_format("fix 1")
    via_view = _script(fig)

    glp.close()
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3], color="blue")
    ax.plot([1, 2, 3], [10, 20, 30], color="red", yaxis="y2")
    ax.set_ylim(0, 40, axis="y2")
    ax.set_ylabel("right", axis="y2")
    ax.set_tick_format("fix 1", axis="y2")
    assert via_view == _script(fig)
    assert right.get_ylim() == (0, 40)


@pytest.mark.parametrize(
    "call",
    [
        lambda r: r.scatter([1, 2], [3, 4]),
        lambda r: r.errorbar([1, 2], [3, 4], yerr=[0.1, 0.1]),
        lambda r: r.step([1, 2], [3, 4]),
        lambda r: r.stem([1, 2], [3, 4]),
        lambda r: r.hist([1, 2, 2, 3], histtype="step"),
    ],
    ids=["scatter", "errorbar", "step", "stem", "hist"],
)
def test_twinx_binds_every_plotting_method_to_y2(call):
    fig, ax = _axes()
    call(ax.twinx())
    assert " y2axis" in _script(fig)


def test_twinx_shares_the_x_axis():
    fig, ax = _axes()
    right = ax.twinx()
    right.set_xlim(0, 5)
    right.set_xlabel("time")
    right.set_xscale("log")
    right.invert_xaxis()
    assert ax.get_xlim() == (5, 0)
    assert ax.xlabel_text == "time"
    assert ax.xscale == "log"


def test_twinx_warns_on_matplotlib_keywords_it_cannot_use():
    _fig, ax = _axes()
    with pytest.warns(
        UserWarning,
        match="twinx\\(\\) ignores unsupported keyword\\(s\\): delta_zorder",
    ):
        ax.twinx(delta_zorder=1.0)


def test_twin_keywords_warn_by_name_whatever_their_value():
    _fig, ax = _axes()
    with pytest.warns(UserWarning, match=r"ignores unsupported keyword\(s\): label"):
        ax.twinx(label=None)


def test_twiny_takes_matplotlibs_signature_and_warns_on_its_keywords():
    _fig, ax = _axes()
    with pytest.warns(
        UserWarning,
        match="twiny\\(\\) ignores unsupported keyword\\(s\\): axes_class, delta_zorder, zorder",
    ):
        top = ax.twiny(object, delta_zorder=1.0, zorder=3)
    top.plot([1, 2], [3, 4])
    assert ax.lines[-1]["xaxis"] == "x2"


def test_module_level_twinx_and_twiny_use_the_current_axes():
    fig, ax = _axes()
    glp.twinx().plot([1, 2], [3, 4])
    glp.twiny().plot([1, 2], [3, 4])
    assert [s["yaxis"] for s in ax.lines] == ["y2", "y"]
    assert ax.lines[1]["xaxis"] == "x2"


# -- invert -----------------------------------------------------------------


def test_invert_yaxis_swaps_explicit_limits():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.set_ylim(0, 5)
    ax.invert_yaxis()
    assert ax.get_ylim() == (5, 0)
    assert _axis_line(_script(fig), "yaxis") == "min 0 max 5 negate"
    ax.invert_yaxis()
    assert ax.get_ylim() == (0, 5)


def test_invert_xaxis_fills_automatic_limits_from_the_data():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.invert_xaxis()
    assert ax.get_xlim() == (3, 1)
    assert _axis_line(_script(fig), "xaxis") == "min 1 max 3 negate"


def test_invert_keeps_an_explicit_bound_and_fills_the_other():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.set_ylim(0, None)
    ax.invert_yaxis()
    assert ax.get_ylim() == (9, 0)


def test_invert_with_no_data_warns_and_does_nothing():
    _fig, ax = _axes()
    with pytest.warns(UserWarning, match=r"set_ylim\(top, bottom\)"):
        ax.invert_yaxis()
    assert ax.get_ylim() == (None, None)


def test_invert_on_a_twin_scale_needs_its_limits():
    _fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 4, 9], yaxis="y2")
    right = ax.twinx()
    with pytest.warns(
        UserWarning, match="GLE chooses the automatic range of the y2 axis"
    ):
        right.invert_yaxis()
    right.set_ylim(0, 10)
    right.invert_yaxis()
    assert right.get_ylim() == (10, 0)
    top = ax.twiny()
    top.set_xlim(0, 1)
    top.invert_xaxis()
    assert ax.get_xlim(axis="x2") == (1, 0)


def test_invert_fills_a_log_axis_from_the_positive_data_only():
    _fig, ax = _axes()
    ax.semilogy([1, 2, 3], [0, 10, 100])
    ax.invert_yaxis()
    assert ax.get_ylim() == (100, 10)


def test_invert_on_a_log_axis_keeps_the_save_time_warning():
    fig, ax = _axes()
    ax.semilogy([1, 2, 3], [1, 10, 100])
    ax.invert_yaxis()
    with pytest.warns(UserWarning, match="GLE cannot invert a log axis"):
        fig._generate_gle()


# -- semilogx / semilogy / loglog --------------------------------------------


@pytest.mark.parametrize(
    "method, scales",
    [
        ("semilogx", ("log", "linear")),
        ("semilogy", ("linear", "log")),
        ("loglog", ("log", "log")),
    ],
)
def test_semilog_sets_the_scale_and_plots(method, scales):
    _fig, ax = _axes()
    getattr(ax, method)([1, 10, 100], [1, 10, 100], label="a")
    assert (ax.xscale, ax.yscale) == scales
    assert ax.lines[0]["label"] == "a"


def test_semilog_base_10_is_silent_and_other_bases_warn():
    _fig, ax = _axes()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ax.semilogx([1, 10], [1, 2], base=10)
    with pytest.warns(UserWarning, match=r"semilogy\(\) ignores base=2, subs="):
        ax.semilogy([1, 10], [1, 2], base=2, subs=[2, 5])


def test_a_rejected_semilog_call_leaves_the_scale_alone():
    _fig, ax = _axes()
    with pytest.raises(TypeError):
        ax.semilogy([1, 2])
    assert ax.yscale == "linear"


def test_module_level_semilog_wrappers():
    _fig, ax = _axes()
    glp.loglog([1, 10], [1, 10])
    assert (ax.xscale, ax.yscale) == ("log", "log")


# -- set_xticklabels / set_yticklabels ---------------------------------------


def test_set_xticklabels_writes_xnames_for_the_placed_ticks():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["a", "b", "c"])
    ax.set_yticks([1, 3])
    ax.set_yticklabels(["low", "high"])
    text = _script(fig)
    assert '    xnames "a" "b" "c"' in text
    assert '    ynames "low" "high"' in text


def test_set_xticklabels_without_matching_ticks_raises():
    _fig, ax = _axes()
    with pytest.raises(ValueError, match="2 labels for no fixed ticks"):
        ax.set_xticklabels(["a", "b"])
    ax.set_yticks([1, 2, 3])
    with pytest.raises(ValueError, match="2 labels for 3 ticks"):
        ax.set_yticklabels(["a", "b"])


def test_set_xticklabels_warns_on_what_it_cannot_honour():
    _fig, ax = _axes()
    ax.set_xticks([1, 2])
    with pytest.warns(
        UserWarning, match=r"ignores unsupported keyword\(s\): fontdict, rotation"
    ):
        ax.set_xticklabels(["a", "b"], fontdict={}, rotation=45)
    assert ax.xnames == ["a", "b"]
    with pytest.warns(UserWarning, match="minor=True"):
        ax.set_xticklabels(["c", "d"], minor=True)
    assert ax.xnames == ["a", "b"]


# -- axis() -----------------------------------------------------------------


def test_axis_off_hides_the_frame_ticks_and_tick_labels():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.axis("off")
    text = _script(fig)
    for line in ("xside off", "yside off", "xticks off", "yticks off"):
        assert f"    {line}\n" in text
    assert "    xlabels off\n" in text and "    ylabels off\n" in text


def test_axis_on_restores_the_script():
    fig, ax = _axes()
    ax.plot([1, 2, 3], [1, 2, 3])
    before = _script(fig)
    ax.axis(np.bool_(False))
    assert ax._frame_off
    ax.axis(True)
    assert _script(fig) == before


def test_axis_on_keeps_shared_tick_labels_hidden():
    fig, axes = glp.subplots(2, 1, sharex=True)
    top = axes[0]
    top.set_xticks(nofirst=True)
    top.axis("off")
    top.axis("on")
    assert top._show_xticks is False and top._remove_first_xtick is True


def test_axis_off_warns_that_axis_labels_stay():
    _fig, ax = _axes()
    ax.set_xlabel("x")
    with pytest.warns(UserWarning, match="keeps the axis labels"):
        ax.axis("off")


def test_axis_reads_and_sets_limits():
    _fig, ax = _axes()
    assert ax.axis() == (None, None, None, None)
    assert ax.axis([0, 1, 2, 3]) == (0, 1, 2, 3)
    assert ax.axis(xmax=5) == (0, 5, 2, 3)
    assert glp.axis("tight") == (None, None, None, None)


def test_axis_rejects_what_matplotlib_rejects():
    _fig, ax = _axes()
    with pytest.raises(ValueError, match="'sideways'"):
        ax.axis("sideways")
    with pytest.raises(TypeError, match=r"\[xmin, xmax, ymin, ymax\]"):
        ax.axis([0, 1])
    with pytest.raises(TypeError, match="together with"):
        ax.axis([0, 1, 0, 1], xmin=0)


def test_axis_warns_on_an_unknown_keyword():
    _fig, ax = _axes()
    with pytest.warns(
        UserWarning, match=r"axis\(\) ignores unsupported keyword\(s\): zmin"
    ):
        ax.axis(xmin=0, zmin=0)
    assert ax.get_xlim()[0] == 0


def test_axis_checks_every_limit_before_setting_any():
    _fig, ax = _axes()
    with pytest.raises(ValueError, match=r"axis\(ymin=nan\)"):
        ax.axis([0, 1, float("nan"), 2])
    with pytest.raises(TypeError, match=r"axis\(ymax='2'\)"):
        ax.axis(xmin=0, ymax="2")
    with pytest.raises(TypeError, match=r"axis\(xmin=\(0, 1\)\)"):
        ax.axis(xmin=(0, 1))
    assert ax.axis() == (None, None, None, None)


def test_axis_emit_false_warns():
    _fig, ax = _axes()
    with pytest.warns(UserWarning, match="emit=False"):
        ax.axis([0, 1, 0, 1], emit=False)


def test_axis_equal_warns():
    _fig, ax = _axes()
    with pytest.warns(UserWarning, match="set_aspect"):
        ax.axis("equal")


@pytest.mark.parametrize(
    "call, name",
    [
        (lambda fig, ax: glp.figure(num=3), "figure"),
        (lambda fig, ax: glp.subplots(num=3), "subplots"),
        (lambda fig, ax: fig.add_subplot(212, title="t"), "add_subplot"),
    ],
)
def test_calls_without_kwargs_before_now_warn_on_unknown_keywords(call, name):
    fig, ax = _axes()
    with pytest.warns(UserWarning, match=rf"{name}\(\) ignores unsupported keyword"):
        call(fig, ax)


def test_add_subplot_polar_true_is_projection_polar():
    fig = glp.figure()
    assert fig.add_subplot(111, polar=True)._polar


def test_subplots_takes_gridspec_kw_ratios():
    fig, axes = glp.subplots(2, 1, gridspec_kw={"height_ratios": [3, 1]})
    expected, _ = glp.subplots(2, 1, height_ratios=[3, 1])
    assert (
        fig.to_dict()["figure"]["height_ratios"]
        == expected.to_dict()["figure"]["height_ratios"]
    )

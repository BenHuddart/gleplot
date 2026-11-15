"""The top scale is a data axis, the way y2 already is.

``Axes.twiny`` is the matplotlib view. The series binding is ``xaxis='x2'``,
stored only when it is the top scale so a primary-x series dict is unchanged.
GLE copies ``xaxis log`` onto x2, so a linear top scale under a log bottom
axis is written ``x2axis lin``; a log bottom axis with no top scale is not.
"""

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


def test_twiny_emits_a_top_data_scale():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], color="blue")
    top = ax.twiny()
    top.plot([0, 5, 10], [1, 4, 9], color="red")
    top.set_xlim(0, 10)
    top.set_xlabel("wavelength")

    text = _script(fig)
    assert " x2axis" in text
    assert "x2axis min 0 max 10" in text
    assert 'x2title "wavelength"' in text
    assert "x2labels on" in text
    assert "x2axis lin" not in text
    assert "x2axis log" not in text


def test_top_scale_x_does_not_widen_the_bottom_axis():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    ax.twiny().plot(np.array([100.0, 200.0]), np.array([9.0, 10.0]))

    text = _script(fig)
    assert "xaxis min 1 max 2" in text
    assert "yaxis min 3 max 10" in text
    assert (ax.x2min, ax.x2max) == (None, None)


def test_a_linear_top_scale_under_a_log_bottom_axis_says_lin():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xscale("log")
    ax.twiny().plot(np.array([0.0, 5.0, 10.0]), np.array([1.0, 2.0, 3.0]))

    text = _script(fig)
    assert "xaxis min 1 max 3 log" in text
    assert "x2axis lin" in text
    assert "x2labels on" not in text


def test_a_log_bottom_axis_with_no_top_scale_does_not_say_lin():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xscale("log")
    assert "x2axis" not in _script(fig)


def test_both_scales_log_emits_log_not_lin():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xscale("log")
    top = ax.twiny()
    top.plot(np.array([10.0, 20.0, 30.0]), np.array([1.0, 2.0, 3.0]))
    top.set_xscale("log")
    top.set_xlim(10, 30)

    text = _script(fig)
    assert "x2axis min 10 max 30 log" in text
    assert "x2axis lin" not in text
    assert "x2labels on" in text


def test_a_primary_series_does_not_store_xaxis():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [3, 4])
    assert "xaxis" not in ax.lines[0]


def test_an_unknown_xaxis_is_rejected():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    with pytest.raises(ValueError, match="xaxis"):
        ax.plot([1, 2], [3, 4], xaxis="x3")


def test_a_filled_histogram_on_x2_warns_and_stays_on_x():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    with pytest.warns(UserWarning, match="stepfilled"):
        ax.hist([1.0, 2.0, 2.0, 3.0], histtype="stepfilled", xaxis="x2")
    assert ax.hists[0].get("xaxis") != "x2"
    assert "x2axis" not in _script(fig)


def test_a_step_histogram_can_use_x2():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.hist([1.0, 2.0, 2.0, 3.0], histtype="step", xaxis="x2")
    assert ax.hists[0].get("xaxis") == "x2"
    assert "x2axis" in _script(fig)


def _graph_height(text: str) -> float:
    for line in text.splitlines():
        if line.startswith("    size "):
            return float(line.split()[2])
    raise AssertionError("graph size line missing")


def test_tick_label_styling_reserves_room_above_the_frame():
    plain = glp.figure(data_prefix="x2")
    ax = plain.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    plain_height = _graph_height(_script(plain))

    styled = glp.figure(data_prefix="x2")
    ax = styled.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.set_tick_format("fix 1", axis="x2")
    assert _graph_height(_script(styled)) < plain_height


def test_tick_format_on_x2_emits_format_and_labels():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.set_xlim(0, 10, axis="x2")
    ax.set_tick_format("fix 1", axis="x2")
    text = _script(fig)
    assert 'x2axis min 0 max 10 format "fix 1"' in text
    assert "x2labels on" in text


def test_scatter_and_errorbar_tokens():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.scatter([1, 2], [3, 4], xaxis="x2")
    ax.errorbar([1, 2], [3, 4], yerr=[0.1, 0.1], xaxis="x2")
    text = _script(fig)
    assert text.count(" x2axis") >= 2


def test_an_inverted_top_scale_is_negated():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.set_xlim(10, 0, axis="x2")
    assert "x2axis min 0 max 10 negate" in _script(fig)


def test_log_repair_on_x2_includes_horizontal_error():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.errorbar([10, 20], [1, 2], xerr=[9, 1], xaxis="x2")
    ax.set_xscale("log", axis="x2")
    ax.set_xlim(0, 100, axis="x2")
    assert "x2axis min 1 max 100 log" in _script(fig)


def test_log_repair_on_x2_uses_the_histogram_window():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2], [1, 2])
    ax.hist([2.0, 3.0, 4.0], bins=2, histtype="step", xaxis="x2")
    ax.set_xscale("log", axis="x2")
    ax.set_xlim(0, 10, axis="x2")
    assert "x2axis min 2 max 10 log" in _script(fig)


def test_a_file_series_can_bind_to_x2():
    fig = glp.figure(data_prefix="x2")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.set_xscale("log")
    ax.line_from_file("wave.dat", 1, 2, xaxis="x2")
    text = _script(fig)
    assert "x2axis lin" in text
    assert "x2axis" in text.split("wave.dat", 1)[-1].split("end graph", 1)[0]


def test_limits_round_trip_through_the_view():
    fig = glp.figure()
    ax = fig.add_subplot(111)
    top = ax.twiny()
    top.set_xlim(2, 8)
    assert top.get_xlim() == (2, 8)
    assert ax.get_xlim(axis="x2") == (2, 8)
    assert ax.get_xlim() == (None, None)

"""``Axes.boxplot``: the stored boxes, the emitted script, and what it rejects."""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.series import Box

#: Quartiles 3.25 / 5.5 / 7.75, whiskers 1 and 9, one flier at 100, mean 14.5.
SAMPLE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _box_lines(text: str):
    return [ln for ln in text.splitlines() if ln.startswith("gleplot_box")]


def _setting(text: str, keyword: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith(keyword)]
    return lines[0] if lines else None


def test_one_box_with_tukey_whiskers_and_a_flier():
    fig, ax = glp.subplots()
    result = ax.boxplot(SAMPLE)
    assert all(isinstance(b, Box) for b in ax.boxes)
    assert result["boxes"] == ax.boxes
    assert set(result) == {"whiskers", "caps", "boxes", "medians", "fliers", "means"}
    assert _box_lines(_script(fig)) == [
        "gleplot_box 1 0.15 0.075 1 3.25 5.5 7.75 9",
        "gleplot_box_flier 1 100",
    ]


def test_showmeans_adds_the_mean():
    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE, showmeans=True)
    assert _box_lines(_script(fig))[-1] == "gleplot_box_mean 1 14.5"


def test_a_percentile_pair_sets_the_whisker_ends():
    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE, whis=(0, 100))
    assert _box_lines(_script(fig)) == ["gleplot_box 1 0.15 0.075 1 3.25 5.5 7.75 100"]


def test_whiskers_stop_at_the_box_when_no_datum_reaches_past_it():
    fig, ax = glp.subplots()
    ax.boxplot([0.5, 1, 2, 3], whis=(10, 90))
    assert _box_lines(_script(fig)) == [
        "gleplot_box 1 0.15 0.075 0.875 0.875 1.5 2.25 2.25",
        "gleplot_box_flier 1 0.5",
        "gleplot_box_flier 1 3",
    ]


def test_autorange_uses_the_data_range_when_the_quartiles_meet():
    fig, ax = glp.subplots()
    ax.boxplot([1, 1, 1, 1, 4], autorange=True)
    ax.boxplot([1, 1, 1, 1, 4], positions=[2])
    lines = _box_lines(_script(fig))
    assert lines[0] == "gleplot_box 1 0.15 0.075 1 1 1 1 4"
    assert lines[1:] == ["gleplot_box 2 0.15 0.075 1 1 1 1 1", "gleplot_box_flier 2 4"]


def test_columns_of_a_2d_array_and_items_of_a_list_are_boxes():
    data = np.array([[1.0, 10.0, 5.0], [2.0, 20.0, 6.0], [3.0, 30.0, 7.0]])
    _fig, ax = glp.subplots()
    ax.boxplot(data)
    assert [b["med"] for b in ax.boxes] == [2.0, 20.0, 6.0]
    assert [b["x"] for b in ax.boxes] == [1.0, 2.0, 3.0]
    # 0.15 * (3 - 1), within matplotlib's 0.15 .. 0.5 clip.
    assert [b["width"] for b in ax.boxes] == pytest.approx([0.3] * 3)

    _fig, ax = glp.subplots()
    ax.boxplot([[1, 2, 3], np.array([4.0, 5.0])])
    assert [b["med"] for b in ax.boxes] == [2.0, 4.5]


def test_positions_widths_capwidths_and_usermedians_are_per_box():
    _fig, ax = glp.subplots()
    ax.boxplot(
        [[1, 2, 3], [4, 5, 6]],
        positions=[2, 6],
        widths=[1, 2],
        capwidths=0.25,
        usermedians=[None, 5.5],
    )
    assert [(b["x"], b["width"], b["capwidth"], b["med"]) for b in ax.boxes] == [
        (2.0, 1.0, 0.25, 2.0),
        (6.0, 2.0, 0.25, 5.5),
    ]


def test_hidden_caps_and_fliers():
    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE, showcaps=False, showfliers=False)
    ax.boxplot(SAMPLE, positions=[2], sym="")
    assert _box_lines(_script(fig)) == [
        "gleplot_box 1 0.15 0 1 3.25 5.5 7.75 9",
        "gleplot_box 2 0.15 0.075 1 3.25 5.5 7.75 9",
    ]


def test_the_limits_cover_the_boxes_and_what_is_drawn_beyond_them():
    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE)
    text = _script(fig)
    assert _setting(text, "xaxis") == "xaxis min 0.5 max 1.5"
    assert _setting(text, "yaxis") == "yaxis min 1 max 100"

    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE, showfliers=False, widths=3)
    text = _script(fig)
    assert _setting(text, "xaxis") == "xaxis min -0.5 max 2.5"
    assert _setting(text, "yaxis") == "yaxis min 1 max 9"


def test_ticks_go_at_the_positions_with_the_tick_labels():
    fig, ax = glp.subplots()
    ax.boxplot([[1, 2], [3, 4]], tick_labels=["a", "$\\alpha$"])
    text = _script(fig)
    assert _setting(text, "xplaces") == "xplaces 1 2"
    assert _setting(text, "xnames") == 'xnames "a" "\\alpha"'

    fig, ax = glp.subplots()
    ax.boxplot([[1, 2]], positions=[1.5])
    ax.boxplot([[3, 4]], positions=[3], tick_labels=["b"])
    text = _script(fig)
    assert _setting(text, "xplaces") == "xplaces 1.5 3"
    assert _setting(text, "xnames") == 'xnames "1.5" "b"'

    fig, ax = glp.subplots()
    ax.boxplot([[1, 2]], tick_labels=["a"], manage_ticks=False)
    text = _script(fig)
    assert _setting(text, "xplaces") is None
    assert _setting(text, "xnames") is None


def test_the_subs_are_defined_once_and_only_when_a_box_is_drawn():
    fig, (left, right) = glp.subplots(1, 2)
    left.boxplot(SAMPLE)
    right.boxplot(SAMPLE)
    text = _script(fig)
    for sub in ("gleplot_box", "gleplot_box_flier", "gleplot_box_mean"):
        assert text.count(f"sub {sub} ") == 1

    fig, ax = glp.subplots()
    ax.plot([0, 1], [0, 1])
    assert "gleplot_box" not in _script(fig)


def test_a_hidden_box_is_not_written():
    fig, ax = glp.subplots()
    ax.boxplot(SAMPLE)
    ax.boxes[0]["visible"] = False
    assert "gleplot_box" not in _script(fig)


def test_an_empty_sample_set_draws_no_box():
    _fig, ax = glp.subplots()
    ax.boxplot([[], [1, 2]])
    assert [b["x"] for b in ax.boxes] == [2.0]


def test_module_level_boxplot_draws_on_the_current_axes():
    fig = glp.figure()
    glp.boxplot(SAMPLE)
    assert len(fig.gca().boxes) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"notch": True},
        {"patch_artist": True},
        {"bootstrap": 1000},
        {"conf_intervals": [None]},
        {"meanline": True},
        {"showbox": False},
        {"boxprops": {"color": "red"}},
        {"flierprops": {"marker": "x"}},
        {"medianprops": {"color": "k"}},
        {"meanprops": {"color": "k"}},
        {"capprops": {"color": "k"}},
        {"whiskerprops": {"color": "k"}},
        {"zorder": 3},
        {"label": "a"},
        {"data": {}},
        {"sym": "r+"},
    ],
)
def test_unsupported_keywords_warn_and_the_box_is_still_drawn(kwargs):
    _fig, ax = glp.subplots()
    with pytest.warns(UserWarning, match="boxplot"):
        ax.boxplot(SAMPLE, **kwargs)
    assert len(ax.boxes) == 1


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"orientation": "horizontal"}, "orientation='horizontal'"),
        ({"vert": False}, "orientation='horizontal'"),
        ({"whis": "wide"}, "whis='wide'"),
        ({"positions": [1, 2]}, r"positions=\.\.\.\) needs one value per box \(1\)"),
        ({"widths": [1, 2]}, "widths"),
        ({"tick_labels": ["a", "b"]}, "tick_labels"),
    ],
)
def test_bad_arguments_are_rejected_at_the_call(kwargs, match):
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match=match):
        ax.boxplot(SAMPLE, **kwargs)
    assert ax.boxes == []


def test_non_finite_samples_are_rejected():
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="box 1 has NaN"):
        ax.boxplot([[1, 2], [1, float("nan")]])

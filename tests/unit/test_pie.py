"""``Axes.pie``: the stored wedges, the emitted script, and what it rejects."""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.series import Wedge


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _wedge_lines(text: str):
    return [ln for ln in text.splitlines() if ln.startswith("gleplot_wedge ")]


def test_wedges_labels_and_percentages_are_one_call_each():
    fig, ax = glp.subplots()
    wedges, texts, autotexts = ax.pie(
        [1, 3], labels=["a", "b"], autopct="%1.0f%%", startangle=90
    )
    assert all(isinstance(w, Wedge) for w in wedges)
    assert ax.wedges == wedges
    assert texts == ["a", "b"]
    assert autotexts == ["25%", "75%"]
    assert _wedge_lines(_script(fig)) == [
        'gleplot_wedge 0 0 1 90 180 "rgb255(31,119,180)" "a" 1.1 "25%" 0.6',
        'gleplot_wedge 0 0 1 180 450 "rgb255(255,127,14)" "b" 1.1 "75%" 0.6',
    ]


def test_the_sub_is_defined_once_and_only_when_a_wedge_is_drawn():
    fig, (left, right) = glp.subplots(1, 2)
    left.pie([1, 1])
    right.pie([1, 2])
    assert _script(fig).count("sub gleplot_wedge ") == 1

    fig, ax = glp.subplots()
    ax.plot([0, 1], [0, 1])
    assert "gleplot_wedge" not in _script(fig)


def test_a_hidden_wedge_is_not_written():
    fig, ax = glp.subplots()
    wedges, _texts = ax.pie([1, 1])
    for wedge in wedges:
        wedge["visible"] = False
    assert "gleplot_wedge" not in _script(fig)


def test_the_frame_is_hidden_but_the_title_kept():
    fig, ax = glp.subplots()
    ax.pie([1, 1])
    ax.set_title("pets")
    text = _script(fig)
    graph = text[text.index("begin graph") : text.index("end graph")]
    assert 'title "pets"' in graph
    assert "    xaxis min -1.25 max 1.25\n" in graph
    assert "    yaxis min -1.25 max 1.25\n" in graph
    for line in (
        "xlabels off",
        "ylabels off",
        "xside off",
        "yside off",
        "xticks off",
        "yticks off",
    ):
        assert f"    {line}\n" in graph
    # 'xaxis off' would take the title with it (GLE draws it with x2).
    assert "axis off" not in graph


def test_center_moves_the_limits_and_the_wedges():
    fig, ax = glp.subplots()
    ax.pie([1], center=(2, -1), radius=0.5)
    assert ax.get_xlim() == (0.75, 3.25)
    assert ax.get_ylim() == (-2.25, 0.25)
    assert _wedge_lines(_script(fig)) == [
        'gleplot_wedge 2 -1 0.5 0 360 "rgb255(31,119,180)" "" 1.1 "" 0.6'
    ]


def test_clockwise_and_unnormalized_angles():
    fig, ax = glp.subplots()
    ax.pie([0.25, 0.25], counterclock=False, normalize=False)
    assert [(w["theta1"], w["theta2"]) for w in ax.wedges] == [
        (-90.0, 0.0),
        (-180.0, -90.0),
    ]


def test_colors_cycle_and_default_to_the_matplotlib_cycle():
    fig, ax = glp.subplots()
    ax.pie([1, 1, 1], colors=["red", "#00ff00"])
    assert [w["color"] for w in ax.wedges] == ["RED", "rgb255(0,255,0)", "RED"]

    fig, ax = glp.subplots()
    ax.pie([1] * 11)
    assert ax.wedges[10]["color"] == ax.wedges[0]["color"] == "rgb255(31,119,180)"


def test_labeldistance_none_draws_no_labels():
    fig, ax = glp.subplots()
    wedges, texts = ax.pie([1, 1], labels=["a", "b"], labeldistance=None)
    assert texts == []
    assert [w["label"] for w in wedges] == [None, None]


def test_callable_autopct_and_mathtext_labels():
    fig, ax = glp.subplots()
    _w, _t, autotexts = ax.pie(
        [1, 1], labels=[r"$\alpha$", "b"], autopct=lambda p: f"{p:.0f} pc"
    )
    assert autotexts == ["50 pc", "50 pc"]
    assert ax.wedges[0]["label"] == r"\alpha"


def test_textprops_fontsize_sets_the_text_height():
    fig, ax = glp.subplots()
    ax.pie([1, 1], labels=["a", "b"], textprops={"size": 14})
    lines = _script(fig).splitlines()
    first = next(i for i, ln in enumerate(lines) if ln.startswith("gleplot_wedge"))
    assert lines[first - 1] == "set hei 0.493827"
    assert ax.wedges[0]["fontsize"] == 14.0


def test_textprops_takes_a_matplotlib_size_name():
    fig, ax = glp.subplots()
    ax.pie([1, 1], textprops={"fontsize": "large"})
    assert ax.wedges[0]["fontsize"] == pytest.approx(fig.style.fontsize * 1.2)
    with pytest.raises(ValueError, match="textprops='fontsize'"):
        ax.pie([1, 1], textprops={"fontsize": "huge"})


def test_texts_has_one_entry_per_wedge():
    fig, ax = glp.subplots()
    _wedges, texts = ax.pie([1, 1, 1], labels=["a", None, "c"])
    assert texts == ["a", "", "c"]
    assert [w["label"] for w in ax.wedges] == ["a", None, "c"]
    _wedges, texts = ax.pie([1, 1])
    assert texts == ["", ""]


def test_numpy_numbers_are_real_numbers():
    fig, ax = glp.subplots()
    ax.pie([1, 1], startangle=np.int64(90), radius=np.int32(1))
    assert ax.wedges[0]["theta1"] == 90.0


def test_module_level_pie_uses_the_current_axes():
    glp.figure()
    wedges, _texts = glp.pie([1, 2])
    assert glp.gca().wedges == wedges


@pytest.mark.parametrize(
    "kwargs",
    [
        {"explode": [0.1, 0]},
        {"shadow": True},
        {"wedgeprops": {"width": 0.3}},
        {"hatch": "//"},
        {"rotatelabels": True},
        {"textprops": {"color": "red"}},
        {"frame": True},
    ],
)
def test_unsupported_options_warn(kwargs):
    fig, ax = glp.subplots()
    with pytest.warns(UserWarning, match="pie"):
        ax.pie([1, 1], **kwargs)
    assert len(ax.wedges) == 2


def test_a_zero_explode_does_not_warn(recwarn):
    fig, ax = glp.subplots()
    ax.pie([1, 1], explode=[0, 0])
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_frame_true_keeps_the_axes():
    fig, ax = glp.subplots()
    with pytest.warns(UserWarning, match="frame=True"):
        ax.pie([1, 1], frame=True)
    assert "xside off" not in _script(fig)


@pytest.mark.parametrize(
    "x, kwargs, error, match",
    [
        ([[1, 2]], {}, ValueError, "1-D"),
        ([1, -1], {}, ValueError, "non-negative"),
        ([1, float("nan")], {}, ValueError, "finite"),
        ([0, 0], {}, ValueError, "all sizes zero"),
        ([0.6, 0.6], {"normalize": False}, ValueError, "sum"),
        ([1, 2], {"labels": ["a"]}, ValueError, "one label per wedge"),
        ([1, 2], {"explode": [0]}, ValueError, "one offset per wedge"),
        ([1, 2], {"radius": 0}, ValueError, "positive"),
        ([1, 2], {"radius": "1"}, TypeError, "real number"),
        ([1, 2], {"startangle": None}, TypeError, "real number"),
        ([1, 2], {"autopct": 3}, TypeError, "format string"),
        ([1, 2], {"colors": []}, ValueError, "at least one colour"),
    ],
)
def test_bad_arguments_are_rejected_at_the_call(x, kwargs, error, match):
    fig, ax = glp.subplots()
    with pytest.raises(error, match=match):
        ax.pie(x, **kwargs)
    assert ax.wedges == []

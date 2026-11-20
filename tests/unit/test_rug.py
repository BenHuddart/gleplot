"""``Axes.rug``: the stored rug, the emitted script, and what it rejects."""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.series import Rug


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _rug_lines(text: str):
    """The ``set`` and call lines that draw each rug after the graph."""
    lines = text.splitlines()
    return [
        line
        for k, line in enumerate(lines)
        if line.startswith(("xrug ", "yrug "))
        or (line.startswith("set color") and lines[k + 1].startswith(("xrug", "yrug")))
    ]


def test_the_values_are_a_dataset_drawn_by_xrug():
    fig, ax = glp.subplots()
    rug = ax.rug([1, 2.5, 4])
    assert isinstance(rug, Rug)
    assert ax.rugs == [rug]
    text, files = fig._generate_gle_with_files()
    assert 'include "rugs.gle"' in text
    assert f"    data {rug['data_file']} d1=c1,c2" in text
    # The other column is missing, so the values stay out of GLE's autoscale.
    assert files[rug["data_file"]] == "x y\n1 *\n2.5 *\n4 *\n"
    # rugs.gle takes a positive length out of the axes; gleplot into them.
    assert _rug_lines(text) == [
        "set color BLACK lwidth 0.03528 cap butt",
        'xrug "d1" -0.3 "bottom"',
    ]


def test_y_rug_with_its_own_edge_length_colour_and_width():
    fig, ax = glp.subplots()
    rug = ax.rug(
        np.array([[0.5], [2.0]]), axis="y", length=-0.2, color="C1", linewidth=2
    )
    text, files = fig._generate_gle_with_files()
    assert files[rug["data_file"]] == "x y\n* 0.5\n* 2\n"
    assert _rug_lines(text) == [
        "set color rgb255(255,127,14) lwidth 0.07056 cap butt",
        'yrug "d1" 0.2 "left"',
    ]


@pytest.mark.parametrize(
    "axis, position", [("x", "top"), ("x", "both"), ("y", "right"), ("y", "both")]
)
def test_every_edge_of_each_axis_is_accepted(axis, position):
    fig, ax = glp.subplots()
    ax.rug([1.0], axis=axis, position=position)
    assert _rug_lines(_script(fig))[1] == f'{axis}rug "d1" -0.3 "{position}"'


@pytest.mark.parametrize("values", [None, []])
def test_no_tick_no_include(values):
    fig, ax = glp.subplots()
    ax.plot([0, 1], [0, 1])
    if values is not None:
        ax.rug(values)
    text = _script(fig)
    assert "xrug" not in text
    assert "include" not in text


def test_rugs_are_drawn_before_the_text():
    fig, ax = glp.subplots()
    ax.text(1, 1, "t")
    ax.rug([1.0])
    lines = _script(fig).splitlines()
    end = lines.index("end graph")
    calls = [ln.split()[0] for ln in lines[end:] if ln.startswith(("amove", "xrug"))]
    assert calls == ["xrug", "amove"]


def test_the_values_widen_the_autoscaled_range_of_their_axis_only():
    fig, ax = glp.subplots()
    ax.plot([2, 3], [2, 3])
    ax.rug([0.5, 6])
    ax.rug([10], axis="y")
    text = _script(fig)
    assert "xaxis min 0.5 max 6" in text
    assert "yaxis min 2 max 10" in text


def test_a_log_axis_ignores_values_it_cannot_show():
    fig, ax = glp.subplots()
    ax.set_xscale("log")
    ax.plot([1, 10], [1, 2])
    ax.rug([-1, 0, 100])
    with pytest.warns(UserWarning, match="log-scaled"):
        text = _script(fig)
    assert "xaxis min 1 max 100 log" in text


def test_polar_axes_rejects_a_rug():
    fig = glp.figure()
    ax = fig.add_subplot(111, projection="polar")
    with pytest.raises(NotImplementedError, match="rug"):
        ax.rug([1.0])


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"axis": "z"}, "axis='z'"),
        ({"position": "left"}, "position='left'"),
        ({"axis": "y", "position": "bottom"}, "position='bottom'"),
        ({"length": 0}, "length=0"),
        ({"length": float("nan")}, "length=nan"),
        ({"linewidth": -1}, "linewidth=-1"),
        ({"linewidth": 0}, "linewidth=0"),
    ],
)
def test_bad_arguments_raise_at_the_call(kwargs, message):
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match=message):
        ax.rug([1.0], **kwargs)
    assert ax.rugs == []


def test_non_finite_values_raise():
    _fig, ax = glp.subplots()
    with pytest.raises(ValueError, match="finite"):
        ax.rug([1.0, np.nan])


@pytest.mark.parametrize("kwargs", [{"length": None}, {"linewidth": "2"}])
def test_a_length_or_width_that_is_not_a_number_is_a_type_error(kwargs):
    _fig, ax = glp.subplots()
    name = next(iter(kwargs))
    with pytest.raises(TypeError, match=f"rug\\({name}="):
        ax.rug([1.0], **kwargs)


def test_a_rug_saved_without_a_data_file_gets_one_on_load():
    fig, ax = glp.subplots()
    ax.rug([1.0, 2.0])
    payload = fig.to_dict()
    del payload["figure"]["axes"][0]["rugs"][0]["data_file"]
    restored = glp.Figure.from_dict(payload)
    rug = restored.axes_list[0].rugs[0]
    text, files = restored._generate_gle_with_files()
    assert files[rug["data_file"]] == "x y\n1 *\n2 *\n"


def test_a_log_axis_writes_no_tick_it_cannot_place():
    fig, ax = glp.subplots()
    ax.set_xscale("log")
    ax.plot([1, 10], [1, 2])
    rug = ax.rug([-1, 0, 100])
    with pytest.warns(UserWarning, match="log-scaled"):
        _text, files = fig._generate_gle_with_files()
    assert files[rug["data_file"]] == "x y\n100 *\n"

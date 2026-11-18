"""Reading box plot boxes back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from gleplot.writer import BOX_SUB


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _graph(after: str) -> str:
    return (
        "size 10 10\n\n"
        + BOX_SUB
        + "\n\nbegin graph\n"
        + "    xaxis min 0 max 3\n"
        + "    yaxis min 0 max 10\n"
        + "end graph\n"
        + after
    )


def _parse(tmp_path, after: str):
    path = tmp_path / "box.gle"
    path.write_text(_graph(after))
    return parse_gle_figure(path)


def test_box_calls_come_back_with_their_fliers_and_mean(tmp_path):
    recognized = _parse(
        tmp_path,
        "gsave\n"
        "gleplot_box 1 0.5 0.25 1 2 3 4 5\n"
        "gleplot_box_flier 1 9\n"
        "gleplot_box_flier 1 0.5\n"
        "gleplot_box_mean 1 3.5\n"
        "gleplot_box 2 0.5 0 2 3 4 5 6\n"
        "grestore\n",
    )
    ax = recognized.figure.axes_list[0]
    assert [dict(b) for b in ax.boxes] == [
        {
            "type": "box",
            "x": 1.0,
            "width": 0.5,
            "capwidth": 0.25,
            "whislo": 1.0,
            "q1": 2.0,
            "med": 3.0,
            "q3": 4.0,
            "whishi": 5.0,
            "fliers": [9.0, 0.5],
            "mean": 3.5,
        },
        {
            "type": "box",
            "x": 2.0,
            "width": 0.5,
            "capwidth": 0.0,
            "whislo": 2.0,
            "q1": 3.0,
            "med": 4.0,
            "q3": 5.0,
            "whishi": 6.0,
            "fliers": [],
            "mean": None,
        },
    ]
    assert ax.texts == []
    assert recognized.warnings == []


@pytest.mark.parametrize(
    "calls",
    [
        # Too few numbers.
        "gleplot_box 1 0.5 0.25 1 2 3 4\n",
        # A flier at another position belongs to no box.
        "gleplot_box 1 0.5 0.25 1 2 3 4 5\ngleplot_box_flier 2 9\n",
        # A flier after the mean: the writer never puts one there.
        "gleplot_box 1 0.5 0.25 1 2 3 4 5\n"
        "gleplot_box_mean 1 3\n"
        "gleplot_box_flier 1 9\n",
    ],
)
def test_box_calls_not_in_the_writers_shape_stay_raw_gle(tmp_path, calls):
    figure = _parse(tmp_path, "gsave\n" + calls + "grestore\n").figure
    assert figure.axes_list[0].boxes == []
    text = figure._generate_gle_with_files()[0]
    for line in calls.splitlines():
        assert line in text

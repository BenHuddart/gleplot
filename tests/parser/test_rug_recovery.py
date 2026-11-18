"""Reading rugs back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from gleplot.writer import RUG_SUB


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _parse(tmp_path, after: str):
    path = tmp_path / "rug.gle"
    path.write_text(
        "size 10 10\n\n"
        + RUG_SUB
        + "\n\nbegin graph\n"
        + "    xaxis min 0 max 3\n"
        + "    yaxis min 0 max 10\n"
        + "end graph\n"
        + after
    )
    return parse_gle_figure(path)


def test_each_run_of_matching_calls_is_one_rug(tmp_path):
    recognized = _parse(
        tmp_path,
        "gsave\n"
        'gleplot_xrug 1 0.3 "bottom" "BLACK" 0.03528\n'
        'gleplot_xrug 2 0.3 "bottom" "BLACK" 0.03528\n'
        'gleplot_xrug 2.5 0.3 "top" "BLACK" 0.03528\n'
        'gleplot_yrug 4 -0.2 "both" "rgb255(255,0,0)" 0.07056\n'
        "grestore\n",
    )
    ax = recognized.figure.axes_list[0]
    assert [dict(r) for r in ax.rugs] == [
        {
            "type": "rug",
            "axis": "x",
            "ticks": [1.0, 2.0],
            "length": 0.3,
            "position": "bottom",
            "color": "BLACK",
            "linewidth": pytest.approx(1.0, abs=1e-3),
        },
        {
            "type": "rug",
            "axis": "x",
            "ticks": [2.5],
            "length": 0.3,
            "position": "top",
            "color": "BLACK",
            "linewidth": pytest.approx(1.0, abs=1e-3),
        },
        {
            "type": "rug",
            "axis": "y",
            "ticks": [4.0],
            "length": -0.2,
            "position": "both",
            "color": "rgb255(255,0,0)",
            "linewidth": pytest.approx(2.0, abs=1e-3),
        },
    ]
    assert ax.texts == []
    assert recognized.warnings == []


@pytest.mark.parametrize(
    "call",
    [
        # Too few arguments.
        'gleplot_xrug 1 0.3 "bottom" "BLACK"',
        # An edge of the other axis.
        'gleplot_xrug 1 0.3 "left" "BLACK" 0.03528',
        # The colour is not a string.
        'gleplot_yrug 1 0.3 "left" 2 0.03528',
    ],
)
def test_rug_calls_not_in_the_writers_shape_stay_raw_gle(tmp_path, call):
    figure = _parse(tmp_path, "gsave\n" + call + "\ngrestore\n").figure
    assert figure.axes_list[0].rugs == []
    assert call in figure._generate_gle_with_files()[0]

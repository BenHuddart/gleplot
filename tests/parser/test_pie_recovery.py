"""Reading pie wedges and a hidden frame back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from gleplot.writer import WEDGE_SUB


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _graph(body: str, after: str = "") -> str:
    return (
        "size 10 10\n\n"
        + WEDGE_SUB
        + "\n\nbegin graph\n"
        + "    xaxis min -1.25 max 1.25\n"
        + "    yaxis min -1.25 max 1.25\n"
        + body
        + "end graph\n"
        + after
    )


_WEDGES = (
    "gsave\n"
    'gleplot_wedge 0 0 1 0 90 "RED" "a" 1.1 "25%" 0.6\n'
    'gleplot_wedge 0 0 1 90 360 "BLUE" "" 1.1 "" 0.6\n'
    "grestore\n"
)


def test_wedge_calls_come_back_as_wedges(tmp_path):
    path = tmp_path / "pie.gle"
    path.write_text(_graph("", _WEDGES))
    recognized = parse_gle_figure(path)
    ax = recognized.figure.axes_list[0]
    assert [(w["color"], w["label"], w["autotext"]) for w in ax.wedges] == [
        ("RED", "a", "25%"),
        ("BLUE", None, None),
    ]
    assert ax.texts == []
    assert recognized.warnings == []


def test_a_wedge_in_another_colour_is_noted(tmp_path):
    path = tmp_path / "pie.gle"
    path.write_text(_graph("", _WEDGES.replace("gsave\n", "gsave\nset color RED\n")))
    recognized = parse_gle_figure(path)
    assert len(recognized.figure.axes_list[0].wedges) == 2
    assert any("pie wedge text" in w for w in recognized.warnings)


def test_a_malformed_wedge_call_stays_raw_gle(tmp_path):
    path = tmp_path / "pie.gle"
    path.write_text(_graph("", 'gsave\ngleplot_wedge 0 0 1 0 90 "RED"\ngrestore\n'))
    figure = parse_gle_figure(path).figure
    assert figure.axes_list[0].wedges == []
    assert 'gleplot_wedge 0 0 1 0 90 "RED"' in figure._generate_gle_with_files()[0]


_FRAME_OFF = "    xside off\n    yside off\n    xticks off\n    yticks off\n"


def test_the_four_frame_lines_come_back_as_a_hidden_frame(tmp_path):
    path = tmp_path / "frame.gle"
    path.write_text(_graph(_FRAME_OFF))
    figure = parse_gle_figure(path).figure
    assert figure.axes_list[0].passthrough == []
    assert _FRAME_OFF + "end graph" in figure._generate_gle_with_files()[0]


@pytest.mark.parametrize(
    "body",
    [
        "    xside off\n    yside off\n    xticks off\n",
        _FRAME_OFF + "    xside off\n",
    ],
    ids=["one-missing", "one-repeated"],
)
def test_an_incomplete_frame_stays_raw_gle(tmp_path, body):
    path = tmp_path / "frame.gle"
    path.write_text(_graph(body))
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert "    xside off" in ax.passthrough

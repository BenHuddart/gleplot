"""Reading pie wedges and a hidden frame back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _graph(body: str, after: str = "") -> str:
    return (
        'size 10 10\n\ninclude "piesub.gle"\n\nbegin graph\n'
        "    xaxis min -1.25 max 1.25\n"
        "    yaxis min -1.25 max 1.25\n" + body + "end graph\n" + after
    )


_S = "min(xg(1)-xg(0),yg(1)-yg(0))"
_WEDGES = (
    "gsave\n"
    "gsave\n"
    "set color RED lwidth 0.0001\n"
    "amove xg(0) yg(0)\n"
    f'pie_text 0 90 1*{_S} "RED" ""\n'
    "grestore\n"
    "set just left\n"
    f"amove xg(0)+1.1*1*{_S}*cos(torad((0+90)/2)) "
    f"yg(0)+1.1*1*{_S}*sin(torad((0+90)/2))\n"
    'write "a"\n'
    "set just center\n"
    f"amove xg(0)+0.6*1*{_S}*cos(torad((0+90)/2)) "
    f"yg(0)+0.6*1*{_S}*sin(torad((0+90)/2))\n"
    'write "25%"\n'
    "gsave\n"
    "set color BLUE lwidth 0.0001\n"
    "amove xg(0) yg(0)\n"
    f'pie_text 90 360 1*{_S} "BLUE" ""\n'
    "grestore\n"
    "grestore\n"
)


def test_wedges_come_back_as_wedges(tmp_path):
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
    text = recognized.figure._generate_gle_with_files()[0]
    assert text.count('include "piesub.gle"') == 1


def test_a_wedge_in_another_colour_is_noted(tmp_path):
    path = tmp_path / "pie.gle"
    path.write_text(_graph("", _WEDGES.replace("gsave\n", "gsave\nset color RED\n", 1)))
    recognized = parse_gle_figure(path)
    assert len(recognized.figure.axes_list[0].wedges) == 2
    assert any("pie wedge text" in w for w in recognized.warnings)


@pytest.mark.parametrize(
    "old,new",
    [
        ('"RED" ""', '"RED" "a"'),
        ("set color RED lwidth 0.0001", "set color RED lwidth 0.02"),
        ("amove xg(0)+1.1*", "amove xg(0)+1.2*"),
    ],
    ids=["pie-text-label", "outline", "moved-label"],
)
def test_a_wedge_not_in_the_writers_shape_stays_raw_gle(tmp_path, old, new):
    path = tmp_path / "pie.gle"
    edited = _WEDGES.replace(old, new, 1)
    path.write_text(_graph("", edited))
    figure = parse_gle_figure(path).figure
    assert figure.axes_list[0].wedges[:1] == [] or (
        figure.axes_list[0].wedges[0]["color"] == "BLUE"
    )
    text = figure._generate_gle_with_files()[0]
    assert new in text
    assert 'include "piesub.gle"' in text


def test_a_gleplot_5_wedge_sub_is_kept_as_raw_gle(tmp_path):
    path = tmp_path / "old.gle"
    path.write_text(
        "size 10 10\n"
        "sub gleplot_wedge cx cy r a1 a2 clr$ lbl$ ld pct$ pd\n"
        "   amove xg(cx) yg(cy)\n"
        "end sub\n"
        "begin graph\n    xaxis min -1 max 1\nend graph\n"
        "gsave\n"
        'gleplot_wedge 0 0 1 0 90 "RED" "a" 1.1 "25%" 0.6\n'
        "grestore\n"
    )
    recognized = parse_gle_figure(path)
    assert recognized.figure.axes_list[0].wedges == []
    text = recognized.figure._generate_gle_with_files()[0]
    assert "sub gleplot_wedge cx cy r a1 a2 clr$ lbl$ ld pct$ pd" in text
    assert 'gleplot_wedge 0 0 1 0 90 "RED" "a" 1.1 "25%" 0.6' in text


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

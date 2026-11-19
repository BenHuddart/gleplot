"""Reading rugs back from a ``.gle`` file."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _parse(tmp_path, data: str, after: str, rows="x y\n1 *\n2 *\n"):
    (tmp_path / "r.dat").write_text(rows)
    path = tmp_path / "rug.gle"
    path.write_text(
        'size 10 10\n\ninclude "rugs.gle"\n\nbegin graph\n'
        "    xaxis min 0 max 3\n"
        "    yaxis min 0 max 10\n" + data + "end graph\n" + after
    )
    return parse_gle_figure(path)


_GROUP = (
    "gsave\n"
    "set color RED lwidth 0.07056 cap butt\n"
    'xrug "d1" -0.3 "top"\n'
    "grestore\n"
)


def test_a_rug_is_read_from_its_dataset_and_call(tmp_path):
    recognized = _parse(
        tmp_path, '    data "r.dat" d1=c1,c2\n', "gsave\n" + _GROUP + "grestore\n"
    )
    ax = recognized.figure.axes_list[0]
    assert [dict(r) for r in ax.rugs] == [
        {
            "type": "rug",
            "axis": "x",
            "ticks": [1.0, 2.0],
            "length": 0.3,
            "position": "top",
            "color": "RED",
            "linewidth": pytest.approx(2.0, abs=1e-3),
            "data_file": "r.dat",
        }
    ]
    assert ax.passthrough == [] and ax.texts == []
    assert recognized.warnings == []
    text = recognized.figure._generate_gle_with_files()[0]
    assert text.count('include "rugs.gle"') == 1


@pytest.mark.parametrize(
    "data,group",
    [
        # The dataset shares its statement with another.
        ('    data "r.dat" d1=c1,c2 d2=c1,c2\n', _GROUP),
        # The call names a dataset the graph does not load.
        ('    data "r.dat" d3=c1,c2\n', _GROUP),
        # An edge of the other axis.
        ('    data "r.dat" d1=c1,c2\n', _GROUP.replace('"top"', '"left"')),
        # A style the writer does not write.
        ('    data "r.dat" d1=c1,c2\n', _GROUP.replace(" cap butt", "")),
    ],
    ids=["shared-statement", "unknown-dataset", "wrong-edge", "other-style"],
)
def test_rugs_not_in_the_writers_shape_stay_raw_gle(tmp_path, data, group):
    figure = _parse(tmp_path, data, "gsave\n" + group + "grestore\n").figure
    assert figure.axes_list[0].rugs == []
    text = figure._generate_gle_with_files()[0]
    assert group.splitlines()[2] in text
    assert data.strip() in text
    assert 'include "rugs.gle"' in text


def test_a_gleplot_5_rug_sub_is_kept_as_raw_gle(tmp_path):
    path = tmp_path / "old.gle"
    path.write_text(
        "size 10 10\n"
        "sub gleplot_xrug x len pos$ clr$ lw\n"
        "   amove xg(x) yg(ygmin)\n"
        "   rline 0 len\n"
        "end sub\n"
        "begin graph\n    xaxis min 0 max 3\nend graph\n"
        "gsave\n"
        'gleplot_xrug 1 0.3 "bottom" "BLACK" 0.03528\n'
        "grestore\n"
    )
    recognized = parse_gle_figure(path)
    assert recognized.figure.axes_list[0].rugs == []
    assert any("gleplot_xrug" in w for w in recognized.warnings)
    text = recognized.figure._generate_gle_with_files()[0]
    assert "sub gleplot_xrug x len pos$ clr$ lw" in text
    assert 'gleplot_xrug 1 0.3 "bottom" "BLACK" 0.03528' in text

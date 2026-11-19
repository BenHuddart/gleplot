"""Reading free page drawings (``Figure.circle`` ... ``Figure.tex``) back."""

from __future__ import annotations

import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from tests.parser import _golden_battery as golden


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _drawings(fig) -> list:
    return fig.to_dict()["figure"]["drawings"]


def _resave(recognized, tmp_path) -> str:
    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    return out.read_text()


@pytest.mark.parametrize(
    "builder",
    [golden.page_drawings, golden.page_drawings_subplots, golden.page_drawings_only],
)
def test_written_drawings_come_back_as_drawings(builder, tmp_path):
    fig = builder()
    path = tmp_path / "figure.gle"
    fig.savefig_gle(str(path))
    recognized = parse_gle_figure(path)
    assert _drawings(recognized.figure) == _drawings(fig)
    assert recognized.figure.passthrough_trailer == fig.passthrough_trailer
    assert recognized.figure.passthrough_header == []
    assert recognized.warnings == []


_GRAPH = "size 10 10\n\nbegin graph\n    xaxis min 0 max 1\nend graph\n"

_CIRCLE = "gsave\namove 2 3\ncircle 0.4 fill RED\ngrestore\n"


def test_a_drawing_after_the_graph_is_recovered(tmp_path):
    recognized = parse_gle_figure(_GRAPH + _CIRCLE)
    assert _drawings(recognized.figure) == [
        {"kind": "circle", "x": 2.0, "y": 3.0, "radius": 0.4, "fill": "RED"}
    ]
    assert recognized.figure.passthrough_trailer == []
    assert _resave(recognized, tmp_path).endswith(_CIRCLE.rstrip("\n"))


@pytest.mark.parametrize(
    "after",
    [
        # Not the writer's spelling of the number.
        "gsave\namove 2 3\ncircle .4 fill RED\ngrestore\n",
        # A command the drawing does not have.
        "gsave\nset lstyle 2\namove 2 3\ncircle 0.4\ngrestore\n",
        # Two commands in one group.
        "gsave\namove 2 3\ncircle 0.4\ncircle 0.2\ngrestore\n",
        # Never closed.
        "gsave\namove 2 3\ncircle 0.4\n",
        # A command that is not a page drawing.
        "gsave\namove 2 3\nbox 1 1\ngrestore\n",
        # A value that is not a number.
        "gsave\namove 2 3\ncircle r\ngrestore\n",
        # After content that stays raw: moving it would reorder the page.
        "amove 1 1\n" + _CIRCLE,
    ],
    ids=[
        "number",
        "lstyle",
        "two-commands",
        "unclosed",
        "box",
        "not-a-number",
        "after-raw",
    ],
)
def test_other_groups_stay_raw_and_resave_unchanged(after, tmp_path):
    recognized = parse_gle_figure(_GRAPH + after)
    assert _drawings(recognized.figure) == []
    assert _resave(recognized, tmp_path).endswith(after.rstrip("\n"))


def test_a_raw_group_ends_the_drawings_and_keeps_its_place(tmp_path):
    raw = "gsave\namove 2 3\ncircle .4\ngrestore\n"
    recognized = parse_gle_figure(_GRAPH + _CIRCLE + raw + _CIRCLE)
    assert len(_drawings(recognized.figure)) == 1
    assert _resave(recognized, tmp_path).endswith(_CIRCLE + raw + _CIRCLE.rstrip())


def test_drawings_before_other_content_in_a_file_without_graphs_stay_raw(tmp_path):
    text = "size 10 10\n\n" + _CIRCLE + "amove 1 1\n"
    recognized = parse_gle_figure(text)
    assert _drawings(recognized.figure) == []
    assert _resave(recognized, tmp_path).endswith(_CIRCLE + "amove 1 1")


def test_a_blank_line_after_the_last_graph_is_kept(tmp_path):
    """#216: a later ``amove`` with no graph after it is not a subplot gap."""
    after = "\namove 1 1\ncircle 0.4\n"
    recognized = parse_gle_figure(_GRAPH + after)
    assert recognized.figure.passthrough_trailer == ["", "amove 1 1", "circle 0.4"]
    assert _resave(recognized, tmp_path).endswith("end graph\n" + after.rstrip("\n"))

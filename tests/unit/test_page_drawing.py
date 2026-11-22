"""Free page drawing: ``Figure.circle`` ... ``Figure.tex`` and their script."""

from __future__ import annotations

import pytest

import gleplot as glp


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _after_graph(fig) -> list:
    lines = _script(fig).splitlines()
    return lines[lines.index("end graph") + 1 :]


def _plotted():
    fig = glp.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1])
    return fig


def test_circle_with_fill_outline_colour_and_width():
    fig = _plotted()
    fig.circle(2, 3, radius=0.4, fill="red", color="blue", linewidth=2)
    assert _after_graph(fig) == [
        "gsave",
        "set color BLUE",
        "set lwidth 0.07056",
        "amove 2 3",
        "circle 0.4 fill RED",
        "grestore",
    ]


def test_each_shape_is_one_command_at_its_point():
    fig = _plotted()
    fig.ellipse(5, 3, 2, 1)
    fig.arc(5, 6, 1, 20, 160)
    fig.bezier([1, 2, 3, 4], [1, 3, -1, 1])
    assert _after_graph(fig) == [
        "gsave",
        "amove 5 3",
        "ellipse 1 0.5",
        "grestore",
        "gsave",
        "amove 5 6",
        "arc 1 20 160",
        "grestore",
        "gsave",
        "amove 1 1",
        "bezier 2 3 3 -1 4 1",
        "grestore",
    ]


def test_curve_points_are_written_as_steps_between_the_slopes():
    fig = _plotted()
    fig.curve([6, 7, 8.5], [1, 2, 1], (1, 0), (0, -1))
    assert _after_graph(fig)[1:3] == ["amove 6 1", "curve 1 0 1 1 1.5 -1 0 -1"]


def test_polygon_is_a_closed_stroked_path_block():
    fig = _plotted()
    fig.polygon([7, 9, 8], [5, 5, 7], fill="yellow")
    assert _after_graph(fig) == [
        "gsave",
        "begin path stroke fill YELLOW",
        "    amove 7 5",
        "    aline 9 5",
        "    aline 8 7",
        "    closepath",
        "end path",
        "grestore",
    ]


@pytest.mark.parametrize("kind", ["table", "tex"])
def test_text_blocks_keep_their_lines_verbatim(kind):
    fig = _plotted()
    getattr(fig, kind)(0.5, 7, "a   bb\n  1   22")
    assert _after_graph(fig) == [
        "gsave",
        "amove 0.5 7",
        f"begin {kind}",
        "a   bb",
        "  1   22",
        f"end {kind}",
        "grestore",
    ]


def test_color_none_drops_the_outline_and_fill_none_the_fill():
    fig = _plotted()
    fig.circle(1, 1, 0.5, fill="red", color="none", linewidth=2)
    fig.ellipse(1, 1, 2, 1, fill="none")
    fig.polygon([0, 1, 1], [0, 0, 1], fill="gray", color="none")
    lines = _after_graph(fig)
    assert "circle 0.5 fill RED nostroke" in lines
    assert "ellipse 1 0.5" in lines
    assert "begin path fill GRAY" in lines
    assert not any(line.startswith("set color") for line in lines)


def test_a_zero_alpha_colour_is_none():
    fig = _plotted()
    fig.circle(1, 1, 0.5, fill="red", color=(0, 0, 0, 0))
    fig.ellipse(1, 1, 2, 1, fill=(1, 0, 0, 0))
    lines = _after_graph(fig)
    assert "circle 0.5 fill RED nostroke" in lines
    assert "ellipse 1 0.5" in lines


def test_curve_steps_land_on_the_written_points():
    fig = _plotted()
    fig.curve([0.1, 0.2, 0.3], [0, 0.7, 0.1], (1, 0), (1, 0))
    assert _after_graph(fig)[2] == "curve 1 0 0.1 0.7 0.1 -0.6 1 0"


def test_a_percent_sign_is_fine_but_not_a_comment_on_the_last_line():
    fig = _plotted()
    fig.tex(1, 1, "50\\% % a comment\nmore")
    with pytest.raises(ValueError, match="last line of s cannot hold"):
        fig.tex(1, 1, "first\nlast % comment")


def test_drawings_follow_every_graph_in_call_order_before_the_trailer():
    fig, (left, right) = glp.subplots(1, 2)
    left.plot([0, 1], [0, 1])
    right.plot([0, 1], [1, 0])
    fig.tex(1, 1, r"\textbf{Note}")
    fig.circle(2, 2, 1)
    fig.passthrough_trailer = ["! kept"]
    text = _script(fig)
    tail = text[text.rindex("end graph") :].splitlines()
    assert tail.index("begin tex") < tail.index("circle 1") < tail.index("! kept")
    assert tail[-1] == "! kept"


def test_a_figure_with_only_drawings_has_no_graph_block():
    fig = glp.figure()
    fig.circle(2, 2, 1)
    text = _script(fig)
    assert "begin graph" not in text
    assert text.splitlines()[-3:] == ["amove 2 2", "circle 1", "grestore"]


def test_drawings_survive_to_dict_and_from_dict():
    fig = _plotted()
    fig.curve([0, 1], [0, 1], (1, 0), (1, 0), color="red")
    fig.tex(1, 2, "x")
    copy = glp.Figure.from_dict(fig.to_dict())
    assert copy.to_dict() == fig.to_dict()
    assert _script(copy) == _script(fig)


def test_an_rgba_fill_needs_cairo():
    fig = glp.figure()
    fig.circle(1, 1, 0.5, fill="rgba255(255,0,0,128)")
    assert fig.requires_cairo()


@pytest.mark.parametrize(
    "call, error, match",
    [
        (lambda f: f.circle(1, 1, 0), ValueError, "radius must be greater than 0"),
        (lambda f: f.circle("a", 1, 1), TypeError, "x must be a number"),
        (lambda f: f.circle(1, float("nan"), 1), ValueError, "y must be finite"),
        (lambda f: f.ellipse(1, 1, 2, -1), ValueError, "height must be greater"),
        (lambda f: f.arc(1, 1, 1, 0, None), TypeError, "theta2 must be a number"),
        (lambda f: f.bezier([0, 1, 2], [0, 1, 2]), ValueError, "exactly 4 points"),
        (lambda f: f.curve([0], [0], (1, 0), (1, 0)), ValueError, "at least 2"),
        (lambda f: f.curve([0, 1], [0, 1], (1,), (1, 0)), ValueError, "start_slope"),
        (lambda f: f.curve([0, 1], [0, 1], (1, 0), 1), TypeError, "end_slope"),
        (lambda f: f.polygon([0, 1, 2], [0, 1]), ValueError, "same length"),
        (lambda f: f.polygon(1, 2), TypeError, "sequences of numbers"),
        (lambda f: f.circle(1, 1, 1, linewidth=0), ValueError, "linewidth"),
        (lambda f: f.tex(1, 1, ""), ValueError, "some text"),
        (lambda f: f.table(1, 1, 3), TypeError, "s must be a str"),
        (lambda f: f.tex(1, 1, "a\nend tex"), ValueError, "start or end of a block"),
        (lambda f: f.table(1, 1, "Begin here"), ValueError, "'Begin'"),
        (lambda f: f.arc(1, 1, 1, 0, 90, color="none"), ValueError, "invisible"),
    ],
)
def test_bad_arguments_are_rejected_at_the_call(call, error, match):
    fig = glp.figure()
    with pytest.raises(error, match=match):
        call(fig)
    assert "gsave" not in _script(fig)


def test_a_latex_begin_command_is_fine_in_a_tex_block():
    fig = glp.figure()
    fig.tex(1, 1, "\\begin{tabular}{c}\nx\n\\end{tabular}")
    assert "\\end{tabular}" in _script(fig).splitlines()

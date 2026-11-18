"""Reading a polar axes back from a ``.gle`` file."""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.parser import parse_gle_figure
from gleplot.series import FunctionSeries, LineSeries, ScatterSeries


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _written(tmp_path):
    fig = glp.figure(data_prefix="pr")
    ax = fig.add_subplot(projection="polar")
    ax.plot([0, 1, 2], [1, 2, 1.5], color="red", label="r")
    ax.scatter([0.5, 3], [1, 0.5])
    ax.function("cos(2*x)", color="green")
    ax.set_ylim(0, 2.5)
    path = tmp_path / "polar.gle"
    fig.savefig(str(path))
    return path


def _recognize(path, text=None):
    if text is not None:
        path.write_text(text)
    return parse_gle_figure(path)


def test_a_written_polar_axes_comes_back_polar(tmp_path):
    recognized = _recognize(_written(tmp_path))
    ax = recognized.figure.axes_list[0]
    assert ax._polar
    assert ax.get_ylim() == (0.0, 2.5)
    assert ax.get_xlim() == (None, None)
    assert recognized.warnings == []


def test_its_curves_come_back_in_theta_and_r(tmp_path):
    recognized = _recognize(_written(tmp_path))
    ax = recognized.figure.axes_list[0]
    (line,) = ax.lines
    (scatter,) = ax.scatters
    (function,) = ax.functions
    assert isinstance(line, LineSeries) and line["label"] == "r"
    np.testing.assert_allclose(line["x"], [0, 1, 2])
    np.testing.assert_allclose(line["y"], [1, 2, 1.5])
    assert isinstance(scatter, ScatterSeries)
    np.testing.assert_allclose(scatter["y"], [1, 0.5])
    assert isinstance(function, FunctionSeries)
    assert function["expression"] == "cos(2*x)"
    assert ax.passthrough == []


def test_a_grid_in_another_layer_stays_raw_and_is_noted(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace("begin layer 200", "begin layer 300")
    recognized = _recognize(path, text)
    ax = recognized.figure.axes_list[0]
    assert not ax._polar
    assert "        draw gleplot_polar_grid 2.5 0.5" in ax.passthrough
    assert any("gleplot_polar_grid" in w for w in recognized.warnings)
    # Not a polar graph, so the curves' lets stay as written.
    assert "    let d2 = d1*cos(x),d1*sin(x)" in ax.passthrough


def test_a_grid_with_another_ring_step_stays_raw(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace(
        "draw gleplot_polar_grid 2.5 0.5", "draw gleplot_polar_grid 2.5 0.25"
    )
    recognized = _recognize(path, text)
    assert not recognized.figure.axes_list[0]._polar
    assert any("gleplot_polar_grid" in w for w in recognized.warnings)


def test_a_missing_label_call_is_noted(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace("gleplot_polar_labels 2.5 0.5 1\n", "")
    recognized = _recognize(path, text)
    assert recognized.figure.axes_list[0]._polar
    assert any("gleplot_polar_labels" in w for w in recognized.warnings)


def test_an_edited_window_is_noted(tmp_path):
    path = _written(tmp_path)
    lines = path.read_text().splitlines(keepends=True)
    i = next(k for k, line in enumerate(lines) if line.strip().startswith("yaxis min"))
    lines[i] = "    yaxis min -9 max 9\n"
    recognized = _recognize(path, "".join(lines))
    ax = recognized.figure.axes_list[0]
    assert ax._polar and ax.get_ylim() == (0.0, 2.5)
    assert any("x and y ranges" in w for w in recognized.warnings)


def test_a_polar_let_outside_a_polar_graph_stays_raw(tmp_path):
    path = tmp_path / "plain.gle"
    path.write_text(
        "size 10 10\n"
        "begin graph\n"
        "    data plain.dat d1=c1,c2\n"
        "    let d2 = d1*cos(x),d1*sin(x)\n"
        "    d2 line color RED\n"
        "end graph\n"
    )
    (tmp_path / "plain.dat").write_text("0 1\n1 2\n")
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert not ax._polar
    assert "    let d2 = d1*cos(x),d1*sin(x)" in ax.passthrough


def test_a_polar_let_with_an_undeclared_source_stays_raw(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace(
        "let d2 = d1*cos(x),d1*sin(x)", "let d2 = d9*cos(x),d9*sin(x)"
    )
    ax = _recognize(path, text).figure.axes_list[0]
    assert ax._polar
    assert "    let d2 = d9*cos(x),d9*sin(x)" in ax.passthrough


def test_a_full_page_polar_graph_round_trips(tmp_path):
    fig = glp.figure(graph=glp.GLEGraphConfig(scale_mode="fullsize"))
    fig.add_subplot(projection="polar").plot([0, 1], [1, 2])
    path = tmp_path / "full.gle"
    fig.savefig(str(path))
    assert "xaxis min -2 max 2" in path.read_text()
    recognized = parse_gle_figure(path)
    assert recognized.figure.axes_list[0]._polar
    assert not any("x and y ranges" in w for w in recognized.warnings)
    again = tmp_path / "again.gle"
    recognized.figure.savefig(str(again))
    assert again.read_text() == path.read_text()


def _round_trip(tmp_path, fig):
    path = tmp_path / "a.gle"
    fig.savefig(str(path))
    recognized = parse_gle_figure(path)
    again = tmp_path / "b.gle"
    recognized.figure.savefig(str(again))
    return path.read_text(), again.read_text().replace("b.gle", "a.gle"), recognized


def test_a_radial_limit_with_many_digits_round_trips(tmp_path):
    """The window is derived from rmax as the script writes it."""
    fig = glp.figure(data_prefix="pr")
    ax = fig.add_subplot(projection="polar")
    ax.plot([0, 1], [0.1, 0.2])
    ax.set_ylim(0, 10 / 21)
    first, second, recognized = _round_trip(tmp_path, fig)
    assert second == first
    assert recognized.warnings == []


def test_a_dataset_drawn_without_a_polar_let_stays_raw(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace(
        "end graph", "    data pr_0.dat d9=c1,c2\n    d9 line color RED\nend graph", 1
    )
    recognized = _recognize(path, text)
    ax = recognized.figure.axes_list[0]
    assert "    d9 line color RED" in ax.passthrough
    assert "    data pr_0.dat d9=c1,c2" in ax.passthrough
    assert len(ax.lines) == 1
    assert any("without a polar let" in w for w in recognized.warnings)


def test_a_polar_curve_whose_data_is_missing_keeps_its_polar_let(tmp_path):
    path = _written(tmp_path)
    (tmp_path / "pr_0.dat").unlink()
    recognized = _recognize(path)
    again = tmp_path / "again.gle"
    recognized.figure.savefig(str(again))
    # The line, the scatter and the function: each drawn through its let.
    assert again.read_text().count("*cos(x),") == 3


def test_a_blank_line_before_the_label_call_is_tolerated(tmp_path):
    path = _written(tmp_path)
    text = path.read_text().replace(
        "gsave\ngleplot_polar_labels", "gsave\n\ngleplot_polar_labels"
    )
    recognized = _recognize(path, text)
    again = tmp_path / "again.gle"
    recognized.figure.savefig(str(again))
    assert again.read_text().count("gleplot_polar_labels 2.5") == 1
    assert recognized.warnings == []

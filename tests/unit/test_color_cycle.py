"""matplotlib's per-axes colour cycle: which call takes, and advances, which.

matplotlib keeps two cycles over ``'C0'``..``'C9'`` per axes, one for lines
and one for patches. The expected colours here were read off matplotlib 3.11
for the same calls.
"""

import json
import warnings

import pytest

import gleplot as glp
from gleplot.colors import rgb_to_gle
from gleplot.parser.recognizer import parse_gle_figure

C = [rgb_to_gle(f"C{n}") for n in range(10)]
X = [1.0, 2.0, 3.0]
Y = [1.0, 3.0, 2.0]


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _ax(**kwargs):
    fig = glp.figure(data_prefix="cyc", **kwargs)
    return fig, fig.add_subplot(111)


CALLS = {
    "plot": lambda ax: ax.plot(X, Y),
    "step": lambda ax: ax.step(X, Y),
    "marker_only_plot": lambda ax: ax.plot(X, Y, "o"),
    "errorbar": lambda ax: ax.errorbar(X, Y, yerr=0.1),
    "hist": lambda ax: ax.hist(Y),
    "hist_step": lambda ax: ax.hist(Y, histtype="step"),
    "stackplot": lambda ax: ax.stackplot(X, Y),
    "function": lambda ax: ax.function("sin(x)", 0, 3),
    "scatter": lambda ax: ax.scatter(X, Y),
    "bar": lambda ax: ax.bar(X, Y),
    "barh": lambda ax: ax.barh(X, Y),
    "fill": lambda ax: ax.fill(X, Y),
    "fill_between": lambda ax: ax.fill_between(X, Y),
    "fill_betweenx": lambda ax: ax.fill_betweenx(X, Y),
    "stem": lambda ax: ax.stem(X, Y),
    "hlines": lambda ax: ax.hlines(Y, 0, 1),
    "vlines": lambda ax: ax.vlines(Y, 0, 1),
}

#: The cycle each call advances, as matplotlib does; None advances neither.
CYCLE = {
    "plot": "lines",
    "step": "lines",
    "marker_only_plot": "lines",
    "errorbar": "lines",
    "hist": "lines",
    "hist_step": "lines",
    "stackplot": "lines",
    "function": "lines",
    "scatter": "patches",
    "bar": "patches",
    "barh": "patches",
    "fill": "patches",
    "fill_between": "patches",
    "fill_betweenx": "patches",
    "stem": None,
    "hlines": None,
    "vlines": None,
}


def _colors(ax):
    """Every series colour on ``ax``, in call order."""
    found = []
    for attr in ("lines", "scatters", "errorbars", "hists", "functions", "fills"):
        found += [(s["_draw_seq"], s.get("color")) for s in getattr(ax, attr)]
    found += [(s["_draw_seq"], s["colors"][0]) for s in ax.bars]
    return [color for _seq, color in sorted(found)]


@pytest.mark.parametrize("name", sorted(CALLS))
def test_each_call_takes_the_next_colour_of_its_own_cycle(name):
    """After a plot and a scatter, each call draws C1, or C0 if it takes none."""
    fig, ax = _ax()
    ax.plot(X, Y)
    ax.scatter(X, Y)
    CALLS[name](ax)
    assert set(_colors(ax)[2:]) == {C[1] if CYCLE[name] else C[0]}
    expected = {"lines": 1, "patches": 1}
    if CYCLE[name]:
        expected[CYCLE[name]] = 2
    assert ax._color_cycles == expected


def test_successive_plots_cycle_and_wrap_after_ten():
    fig, ax = _ax()
    for _ in range(12):
        ax.plot(X, Y)
    assert _colors(ax) == C + C[:2]
    text = fig._generate_gle()
    assert "d1 line color rgb255(31,119,180) " in text
    assert "d2 line color rgb255(255,127,14) " in text


def test_lines_and_patches_cycle_separately_as_in_matplotlib():
    fig, ax = _ax()
    ax.plot(X, Y)
    ax.bar(X, Y)
    ax.plot(X, Y)
    ax.scatter(X, Y)
    assert _colors(ax) == [C[0], C[0], C[1], C[1]]


def test_one_colour_per_data_set_or_layer():
    fig, ax = _ax()
    ax.hist([Y, Y, Y])
    ax.stackplot(X, Y, Y)
    assert _colors(ax) == C[:5]


def test_a_colour_given_takes_nothing_from_the_cycle():
    fig, ax = _ax()
    ax.plot(X, Y, color="red")
    ax.plot(X, Y, "g--")
    ax.scatter(X, Y, c=[1.0, 2.0, 3.0])
    ax.bar(X, Y, color="k")
    ax.plot(X, Y)
    ax.scatter(X, Y)
    assert _colors(ax)[-2:] == [C[0], C[0]]


def test_a_secondary_axis_has_cycles_of_its_own():
    """matplotlib's twinx is another axes, so its first line is C0 again."""
    fig, ax = _ax()
    ax.plot(X, Y)
    ax.twinx().plot(X, Y)
    ax.plot(X, Y)
    assert [s["color"] for s in ax.lines] == [C[0], C[0], C[1]]


def test_a_configured_default_colour_replaces_the_cycle():
    style = glp.GLEStyleConfig(default_color="BLUE", default_marker_color="red")
    fig, ax = _ax(style=style)
    ax.plot(X, Y)
    ax.plot(X, Y)
    ax.scatter(X, Y)
    ax.bar(X, Y)
    assert _colors(ax) == ["BLUE", "BLUE", "RED", C[0]]


def test_an_opened_file_continues_each_cycle(tmp_path):
    fig, ax = _ax()
    ax.plot(X, Y)
    ax.bar(X, Y)
    ax.plot(X, Y, color="red")
    ax.errorbar(X, Y, yerr=0.1)
    ax.twinx().plot(X, Y)
    path = tmp_path / "c.gle"
    fig.savefig_gle(str(path))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        loaded = parse_gle_figure(path).figure.axes_list[0]
    assert loaded._color_cycles == ax._color_cycles
    loaded.plot(X, Y)
    loaded.scatter(X, Y)
    assert loaded.lines[-1]["color"] == C[2]
    assert loaded.scatters[-1]["color"] == C[1]


def test_a_restored_snapshot_continues_each_cycle():
    fig, ax = _ax()
    ax.plot(X, Y)
    ax.fill_between(X, Y)
    restored = glp.Figure.from_dict(json.loads(json.dumps(fig.to_dict())))
    again = restored.axes_list[0]
    again.plot(X, Y)
    again.fill(X, Y)
    assert again.lines[-1]["color"] == C[1]
    assert again.fills[-1]["color"] == C[1]

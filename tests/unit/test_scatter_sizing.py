"""``scatter`` takes matplotlib's ``s`` *and* ``Line2D``'s ``markersize``.

The two are different quantities in matplotlib and gleplot keeps them that
way:

* ``s`` is an **area in points**2** (``scatter``'s convention), converted with
  the square-root relation matplotlib defines between area and diameter --
  ``markersize = sqrt(s)`` -- times gleplot's historical 1.2 visibility
  factor;
* ``markersize`` is a **diameter in points** (``plot``'s convention), used as
  given.

``markersize`` used to be swallowed by ``**kwargs``: ``ax.scatter(x, y,
markersize=12)`` silently drew the default size. These tests pin both
spellings, their precedence when both are passed, and the fact that a
``scatter`` and a ``plot`` given the same ``markersize`` produce the same GLE
``msize``.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp
from gleplot.parser.units import markersize_to_msize

X = [1.0, 2.0, 3.0]
Y = [1.0, 4.0, 9.0]


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


def _ax():
    return glp.figure(data_prefix="t").add_subplot(111)


def _msize(ax) -> float:
    """The GLE ``msize`` emitted for the axes' single series."""
    text, _files = ax.figure._generate_gle_with_files()
    sizes = re.findall(r"\bmsize\s+(\S+)", text)
    assert len(sizes) == 1, sizes
    return float(sizes[0])


# --------------------------------------------------------------------------- #
# s -- matplotlib's scatter convention (area in points**2)
# --------------------------------------------------------------------------- #


def test_default_size_is_unchanged():
    """No size given: still s=20, i.e. the pre-1.9.0 rendering."""
    ax = _ax()
    ax.scatter(X, Y)
    assert ax.scatters[0]["markersize"] == pytest.approx(
        markersize_to_msize(np.sqrt(20) * 1.2)
    )


@pytest.mark.parametrize("s", [1, 4, 20, 36, 100, 400])
def test_s_uses_the_sqrt_relation(s):
    ax = _ax()
    ax.scatter(X, Y, s=s)
    assert _msize(ax) == pytest.approx(markersize_to_msize(np.sqrt(s) * 1.2))


def test_s_quadrupled_doubles_the_marker():
    """Area semantics: 4x the area is 2x the diameter."""
    a, b = _ax(), _ax()
    a.scatter(X, Y, s=25)
    b.scatter(X, Y, s=100)
    assert _msize(b) == pytest.approx(2 * _msize(a))


def test_s_and_c_are_matplotlibs_positional_order():
    """scatter(x, y, s, c), as in matplotlib; everything after is keyword-only."""
    ax = _ax()
    ax.scatter(X, Y, 50, "red")
    assert _msize(ax) == pytest.approx(markersize_to_msize(np.sqrt(50) * 1.2))
    assert ax.scatters[0]["color"] == "RED"
    with pytest.raises(TypeError):
        ax.scatter(X, Y, 50, "red", "o")


def test_a_colour_in_the_old_third_position_names_the_new_order():
    ax = _ax()
    with pytest.raises(TypeError, match=r"\(x, y, s, c\); pass a colour as color="):
        ax.scatter(X, Y, "red")


def test_a_nan_scalar_size_leaves_every_point_out():
    """As in matplotlib, a scatter with no size draws no point."""
    ax = _ax()
    ax.scatter(X, Y, float("nan"))
    _text, files = ax.figure._generate_gle_with_files()
    rows = [line.split() for line in files["t_0.dat"].splitlines()[1:]]
    assert [y for _x, y in rows] == ["nan"] * len(X)  # GLE skips a nan row


@pytest.mark.parametrize("size", [-4, float("inf")])
def test_a_scalar_size_must_be_not_negative_or_infinite(size):
    with pytest.raises(ValueError, match="not be negative or infinite"):
        _ax().scatter(X, Y, size)


def test_figure_and_module_scatter_forward_s_and_c_positionally():
    fig = glp.figure()
    fig.add_subplot(111)
    fig.scatter(X, Y, 50, "red")
    glp.scatter(X, Y, 50, "blue")
    first, second = fig.gca().scatters
    assert (first["color"], second["color"]) == ("RED", "BLUE")
    assert first["markersize"] == second["markersize"]


# --------------------------------------------------------------------------- #
# markersize -- Line2D's convention (diameter in points)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("markersize", [1, 6, 12, 20])
def test_markersize_is_used_as_given(markersize):
    ax = _ax()
    ax.scatter(X, Y, markersize=markersize)
    assert _msize(ax) == pytest.approx(markersize_to_msize(markersize))


@pytest.mark.parametrize("markersize", [4, 6, 15])
def test_scatter_and_plot_agree_on_markersize(markersize):
    """The same number means the same marker in both APIs."""
    a, b = _ax(), _ax()
    a.scatter(X, Y, markersize=markersize)
    b.plot(X, Y, marker="o", linestyle="none", markersize=markersize)
    assert _msize(a) == pytest.approx(_msize(b))


def test_markersize_wins_when_both_are_given():
    ax = _ax()
    ax.scatter(X, Y, s=400, markersize=6)
    assert _msize(ax) == pytest.approx(markersize_to_msize(6))


def test_msize_scale_still_applies_to_both_spellings():
    glp.GlobalConfig.marker.msize_scale = 2.0
    a, b = _ax(), _ax()
    a.scatter(X, Y, s=36)
    b.scatter(X, Y, markersize=6)
    assert a.scatters[0]["markersize"] == pytest.approx(
        markersize_to_msize(np.sqrt(36) * 1.2, 2.0)
    )
    assert b.scatters[0]["markersize"] == pytest.approx(markersize_to_msize(6, 2.0))


# --------------------------------------------------------------------------- #
# per-point sizes
# --------------------------------------------------------------------------- #


def test_per_point_s_writes_mdata_through_a_marker_sub():
    """GLE's ``mdata`` only scales a sub-defined marker, so one is emitted."""
    ax = _ax()
    ax.scatter(X, Y, s=[100, 400, 900], color="red", label="pop")
    text, files = ax.figure._generate_gle_with_files()

    assert (
        "sub glp_mdata_fcircle size data\n"
        "   if data > 0 then\n"
        "      gsave\n"
        "      set hei size*data\n"
        "      marker FCIRCLE\n"
        "      grestore\n"
        "   end if\n"
        "end sub\n"
        "define marker glp_mdata_fcircle glp_mdata_fcircle\n"
    ) in text
    assert "data t_0.dat d1=c1,c2 d2=c1,c3\n" in text
    # The legend marker's area is halfway between the extremes (matplotlib).
    base = np.sqrt((100 + 900) / 2) * 1.2
    msize = markersize_to_msize(base)
    assert re.search(
        rf"d1 marker glp_mdata_fcircle msize {msize:.6g} mdata d2 color RED "
        r'key "pop"\n',
        text,
    )
    rows = [line.split() for line in files["t_0.dat"].splitlines()]
    assert rows[0] == ["x", "pop", "mdata"]
    scales = [float(row[2]) for row in rows[1:]]
    expected = np.sqrt([100, 400, 900]) * 1.2 / base
    assert scales == pytest.approx(expected, rel=1e-5)


def test_per_point_markersize_is_a_diameter():
    ax = _ax()
    ax.scatter(X, Y, markersize=[2, 4, 8], marker="s")
    series = ax.scatters[0]
    base = np.sqrt((2**2 + 8**2) / 2)
    assert series["markersize"] == pytest.approx(markersize_to_msize(base))
    assert series["mdata"] == pytest.approx(np.array([2, 4, 8]) / base)
    text, _files = ax.figure._generate_gle_with_files()
    assert "sub glp_mdata_fsquare size data" in text
    assert "marker FSQUARE\n" in text


def test_one_sub_per_marker_shape():
    ax = _ax()
    ax.scatter(X, Y, s=[1, 2, 3])
    ax.scatter(X, Y, s=[4, 5, 6])
    ax.scatter(X, Y, s=[4, 5, 6], marker="^")
    text, _files = ax.figure._generate_gle_with_files()
    assert text.count("sub glp_mdata_fcircle ") == 1
    assert text.count("sub glp_mdata_ftriangle ") == 1


def test_all_zero_sizes_keep_a_drawable_legend_marker():
    """``msize 0`` is GLE's font height, so the base stays the default."""
    ax = _ax()
    ax.scatter(X, Y, s=[0, 0, 0])
    series = ax.scatters[0]
    assert series["markersize"] == pytest.approx(markersize_to_msize(np.sqrt(20) * 1.2))
    assert list(series["mdata"]) == [0, 0, 0]


@pytest.mark.parametrize("kwargs", [{"s": [30]}, {"markersize": np.array([6.0])}])
def test_a_one_element_array_is_one_size(kwargs):
    """matplotlib broadcasts a length-1 ``s``; so does gleplot."""
    a, b = _ax(), _ax()
    a.scatter(X, Y, **kwargs)
    b.scatter(X, Y, **{k: float(np.ravel(v)[0]) for k, v in kwargs.items()})
    assert "mdata" not in a.scatters[0]
    assert a.figure._generate_gle_with_files() == b.figure._generate_gle_with_files()


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"s": [10, 20]}, "2 sizes for 3 points"),
        ({"markersize": [1, 2, 3, 4]}, "4 sizes for 3 points"),
        ({"s": [10, -1, 20]}, "not be negative or infinite"),
        ({"s": [10, np.inf, 20]}, "not be negative or infinite"),
        ({"s": [-4]}, "not be negative or infinite"),
        ({"s": ["a", "b", "c"]}, "number or a sequence of numbers"),
        ({"s": [10, 20, 30], "mdist": 1.0}, r"mdist=1\.0"),
        ({"s": [10, 20, 30], "deresolve": 2}, "deresolve=2"),
    ],
)
def test_bad_per_point_sizes_are_rejected_at_the_call(kwargs, match):
    ax = _ax()
    with pytest.raises(ValueError, match=match):
        ax.scatter(X, Y, **kwargs)


def test_empty_sizes_draw_an_empty_series():
    ax = _ax()
    ax.scatter([], [], s=[])
    assert "mdata" not in ax.scatters[0]


def test_a_point_gle_would_drop_is_written_missing():
    """GLE drops NaN (and, on a log axis, negative) points from the drawn
    dataset but not from the sizes, then refuses the mismatch."""
    ax = _ax()
    ax.scatter([1, 2, 3, 4], [1, np.nan, -3, 4], s=[10, 20, 30, 40])
    ax.set_yscale("log")
    ax.set_ylim(0.5, 5)
    _text, files = ax.figure._generate_gle_with_files()
    rows = [line.split()[:2] for line in files["t_0.dat"].splitlines()[1:]]
    assert rows == [["1", "1"], ["*", "*"], ["*", "*"], ["4", "4"]]


@pytest.mark.parametrize("per_point", [{"s": [10, 20, 30]}, {"c": [1, 2, 3]}])
@pytest.mark.parametrize(
    "y, scale, dropped",
    [([1, np.nan, 9], "linear", "nan"), ([1, -4, 9], "log", "-4")],
    ids=["nan", "log-negative"],
)
def test_a_table_point_gle_would_drop_is_written_missing(per_point, y, scale, dropped):
    """A provider-backed scatter gets its own masked x and y columns (#201).

    The table's columns stay as they are, because the line reads them too.
    """
    from gleplot.sources import ColumnRef, DictDataProvider, TableData

    ax = _ax()
    ax.scatter(X, Y, **per_point)
    ax.plot(X, Y)
    ax.set_xlim(0.5, 4)
    ax.set_ylim(0.5, 10)
    ax.set_yscale(scale)
    for series in (ax.scatters[0], ax.lines[0]):
        series["data_source"] = ColumnRef("t", {"x": "x", "y": "y"})
    table = TableData.from_mapping({"x": [1, 2, 3], "y": y})
    text, files = ax.figure._generate_gle_with_files(
        data_provider=DictDataProvider({"t": table})
    )

    (name,) = files
    rows = [line.split()[:4] for line in files[name].splitlines()]
    assert rows == [
        ["x", "y", "x_2", "y_2"],
        ["1", "1", "1", "1"],
        ["2", dropped, "*", "*"],
        ["3", "9", "3", "9"],
    ]
    assert f"data {name} d1=c1,c2\n" in text
    assert f"data {name} d2=c3,c4 d3=c3,c5\n" in text


def test_no_marker_means_no_sub():
    ax = _ax()
    ax.scatter(X, Y, s=[10, 20, 30], marker="None")
    text, _files = ax.figure._generate_gle_with_files()
    assert "gleplot_mdata" not in text


def test_per_point_sizes_survive_to_dict():
    ax = _ax()
    ax.scatter(X, Y, s=[10, 20, 30])
    fig = ax.figure
    restored = glp.Figure.from_dict(fig.to_dict())
    series = restored.axes_list[0].scatters[0]
    assert isinstance(series["mdata"], np.ndarray)
    assert series["mdata"] == pytest.approx(ax.scatters[0]["mdata"])
    assert restored._generate_gle_with_files() == fig._generate_gle_with_files()


# --------------------------------------------------------------------------- #
# the rest of the call is untouched
# --------------------------------------------------------------------------- #


def test_other_arguments_still_work_alongside_markersize():
    ax = _ax()
    ax.scatter(X, Y, color="red", marker="s", label="pts", markersize=9)
    series = ax.scatters[0]
    assert series["color"] == "RED"
    assert series["marker"] == "FSQUARE"
    assert series["label"] == "pts"
    assert series["markersize"] == pytest.approx(markersize_to_msize(9))

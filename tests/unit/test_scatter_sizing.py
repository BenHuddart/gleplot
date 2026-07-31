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


def test_s_is_still_positional():
    """scatter(x, y, color, s) -- the historical positional order holds."""
    ax = _ax()
    ax.scatter(X, Y, "red", 50)
    assert _msize(ax) == pytest.approx(markersize_to_msize(np.sqrt(50) * 1.2))


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


@pytest.mark.parametrize("kwargs", [{"s": [10, 20, 30]}, {"markersize": [4, 5, 6]}])
def test_per_point_sizes_are_rejected_clearly(kwargs):
    """GLE's msize is per dataset -- fail loudly instead of emitting garbage."""
    ax = _ax()
    with pytest.raises(ValueError, match="per-dataset"):
        ax.scatter(X, Y, **kwargs)


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

"""A series is drawn, and written to disk, in the order its points were given.

matplotlib joins consecutive points in the order you pass them; that order is
part of the data. gleplot used to sort every ``plot``/``errorbar`` series by
ascending x before writing its ``.dat`` file -- a habit left over from GLE's
``smooth``, which fits a piecewise cubic as a function of x and so needs
monotonic input. Once smoothing became opt-in (and off by default), that sort
was silently reordering the great majority of series, which had never asked
for it: any curve whose x is non-monotonic *by design* -- a hysteresis loop, a
parametric or closed curve, a field sweep taken up and back down -- came out
redrawn in the wrong order, and the data file on disk no longer matched what
the caller passed.

These tests pin the contract on the generated data files and GLE text:

* **by default the emitted rows are the input rows, in the input order** --
  for ``plot``, ``scatter``, ``errorbar`` (every column staying paired with
  its point), ``fill_between``, and the offset paths;
* **a smoothed series is the one exception**: when the line will actually
  carry ``smooth``, the rows are sorted by x (stably) so GLE gets the
  monotonic input it needs -- and a series that draws no line is never sorted
  even with smoothing on, because it never gets the qualifier.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _rows(fig) -> np.ndarray:
    """The numeric rows of the figure's single generated data file."""
    _script, files = fig._generate_gle_with_files()
    assert len(files) == 1, f"expected one data file, got {sorted(files)}"
    (content,) = files.values()
    out = []
    for line in content.splitlines():
        try:
            out.append([float(tok) for tok in line.split()])
        except ValueError:
            continue  # the sidecar header row
    return np.array(out)


def _dataset_command(fig) -> str:
    """The ``dN <attributes>`` display command for the (single) series."""
    script, _files = fig._generate_gle_with_files()
    cmds = [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]
    assert len(cmds) == 1, cmds
    return cmds[0]


#: A closed curve: the unit circle parameterised by angle. Its x runs
#: 1 -> -1 -> 1, so sorting by x tears the loop into two overlapping arcs and
#: the figure no longer closes. Endpoints coincide (t = 0 and t = 2*pi).
T = np.linspace(0.0, 2.0 * np.pi, 13)
CIRCLE_X = np.cos(T)
CIRCLE_Y = np.sin(T)

#: A hysteresis loop: the field is swept up, then back down over the same
#: points, with a different response on the return leg.
SWEEP_UP = np.linspace(0.0, 1.0, 6)
HYST_X = np.concatenate([SWEEP_UP, SWEEP_UP[::-1]])
HYST_Y = np.concatenate([SWEEP_UP**2, SWEEP_UP[::-1] ** 0.5])


def _smooth():
    return glp.GLEGraphConfig(smooth_curves=True)


# --------------------------------------------------------------------------- #
# the default: input order, everywhere
# --------------------------------------------------------------------------- #


def test_closed_loop_rows_are_the_input_rows_in_order():
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y]))


def test_closed_loop_closes():
    """The drawn figure returns to where it started.

    A bare ``line`` dataset is a polyline through the rows in file order, so
    the drawn curve closes exactly when the first and last rows coincide --
    which they do here only because nothing reordered them. (Sorted by x, the
    first row would be the leftmost point and the last the rightmost: an open
    curve.)
    """
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    rows = _rows(fig)

    assert re.search(r"\bline\b", _dataset_command(fig))
    assert not re.search(r"\bsmooth\b", _dataset_command(fig))
    assert len(rows) == len(CIRCLE_X)
    assert np.allclose(rows[0], rows[-1])
    # ...and it is a loop, not a degenerate there-and-back: the vertices are
    # all distinct apart from the repeated endpoint.
    assert len(np.unique(rows[:-1], axis=0)) == len(rows) - 1


def test_hysteresis_loop_keeps_both_sweeps():
    """The return leg stays a return leg instead of being merged into the up leg."""
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(HYST_X, HYST_Y)
    rows = _rows(fig)

    assert np.allclose(rows, np.column_stack([HYST_X, HYST_Y]))
    # The x column is not monotonic -- exactly the case the old sort destroyed.
    assert np.any(np.diff(rows[:, 0]) < 0)


def test_scatter_preserves_input_order():
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).scatter(CIRCLE_X, CIRCLE_Y)
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y]))


def test_marker_and_line_series_preserves_input_order():
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y, marker="o")
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y]))


def test_points_sharing_an_x_keep_their_input_order():
    """A vertical segment stays traced in the direction it was given."""
    x = np.array([0.0, 1.0, 1.0, 1.0, 2.0])
    y = np.array([0.0, 3.0, 1.0, 2.0, 0.0])
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(x, y)
    assert np.allclose(_rows(fig), np.column_stack([x, y]))


def test_errorbar_rows_keep_each_point_with_its_error():
    """Order is preserved and the error column stays bound to its own point."""
    yerr = np.linspace(0.01, 0.13, len(CIRCLE_X))
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).errorbar(CIRCLE_X, CIRCLE_Y, yerr=yerr, fmt="-")
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y, yerr]))


def test_errorbar_asymmetric_and_horizontal_errors_stay_paired():
    n = len(HYST_X)
    # matplotlib's asymmetric form: a (lower, upper) pair per direction.
    y_lo, y_hi = np.linspace(0.01, 0.06, n), np.linspace(0.11, 0.16, n)
    x_lo, x_hi = np.linspace(0.21, 0.26, n), np.linspace(0.31, 0.36, n)
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).errorbar(
        HYST_X, HYST_Y, yerr=(y_lo, y_hi), xerr=(x_lo, x_hi), fmt="-"
    )
    rows = _rows(fig)

    # Columns are x, y, then the error magnitudes in the order add_errorbar
    # appends them: y up/down, then x left/right.
    assert rows.shape == (n, 6)
    expected = np.column_stack([HYST_X, HYST_Y, y_hi, y_lo, x_lo, x_hi])
    assert np.allclose(rows, expected)


def test_fill_between_preserves_input_order():
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).fill_between(HYST_X, HYST_Y - 0.1, HYST_Y + 0.1)
    rows = _rows(fig)
    assert np.allclose(rows[:, 0], HYST_X)
    assert np.allclose(rows[:, 1], HYST_Y - 0.1)
    assert np.allclose(rows[:, 2], HYST_Y + 0.1)


def test_offset_series_is_written_raw_and_in_order():
    """The offset lives in the GLE script; the file keeps the caller's rows."""
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y, offset=5.0)
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y]))


def test_every_series_in_a_multi_series_figure_keeps_its_order():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    for i in range(4):
        ax.plot(CIRCLE_X, CIRCLE_Y + i, label=f"s{i}")
    _script, files = fig._generate_gle_with_files()
    assert len(files) == 4
    for i, name in enumerate(sorted(files)):
        rows = np.array(
            [
                [float(tok) for tok in ln.split()]
                for ln in files[name].splitlines()
                if not ln.startswith("x")
            ]
        )
        assert np.allclose(rows, np.column_stack([CIRCLE_X, CIRCLE_Y + i]))


# --------------------------------------------------------------------------- #
# the exception: a line that will actually be smoothed
# --------------------------------------------------------------------------- #


def test_smoothed_line_is_sorted_by_x():
    """GLE's ``smooth`` needs monotonic x, so opting in re-sorts the rows."""
    fig = glp.figure(data_prefix="t", graph=_smooth())
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    rows = _rows(fig)

    assert re.search(r"\bline smooth\b", _dataset_command(fig))
    assert np.all(np.diff(rows[:, 0]) >= 0)
    # Same points, only reordered -- nothing dropped or invented.
    assert np.allclose(
        np.sort(rows, axis=0),
        np.sort(np.column_stack([CIRCLE_X, CIRCLE_Y]), axis=0),
    )


def test_smoothed_sort_is_stable_for_tied_x():
    x = np.array([0.0, 1.0, 1.0, 1.0, 2.0])
    y = np.array([0.0, 3.0, 1.0, 2.0, 0.0])
    fig = glp.figure(data_prefix="t", graph=_smooth())
    fig.add_subplot(111).plot(x, y)
    assert np.allclose(_rows(fig)[:, 1], y)  # ties keep their input order


def test_smoothed_errorbar_sorts_rows_but_keeps_errors_paired():
    yerr = np.linspace(0.01, 0.13, len(CIRCLE_X))
    fig = glp.figure(data_prefix="t", graph=_smooth())
    fig.add_subplot(111).errorbar(CIRCLE_X, CIRCLE_Y, yerr=yerr, fmt="-")
    rows = _rows(fig)

    assert np.all(np.diff(rows[:, 0]) >= 0)
    order = np.argsort(CIRCLE_X, kind="stable")
    assert np.allclose(rows, np.column_stack([CIRCLE_X, CIRCLE_Y, yerr])[order])


def test_global_smoothing_opt_in_also_sorts():
    glp.GlobalConfig.graph.smooth_curves = True
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    assert np.all(np.diff(_rows(fig)[:, 0]) >= 0)


def test_scatter_is_not_sorted_even_when_smoothing_is_on():
    """No line means no ``smooth`` qualifier, so there is nothing to sort for."""
    fig = glp.figure(data_prefix="t", graph=_smooth())
    fig.add_subplot(111).scatter(CIRCLE_X, CIRCLE_Y)
    assert not re.search(r"\bsmooth\b", _dataset_command(fig))
    assert np.allclose(_rows(fig), np.column_stack([CIRCLE_X, CIRCLE_Y]))


def test_fill_between_is_not_sorted_even_when_smoothing_is_on():
    """``fill dA,dB`` takes no ``smooth``, so a band keeps the caller's order."""
    fig = glp.figure(data_prefix="t", graph=_smooth())
    fig.add_subplot(111).fill_between(HYST_X, HYST_Y - 0.1, HYST_Y + 0.1)
    assert np.allclose(_rows(fig)[:, 0], HYST_X)


# --------------------------------------------------------------------------- #
# round trip
# --------------------------------------------------------------------------- #


def test_open_gle_recovers_the_loop_in_order(tmp_path):
    path = tmp_path / "loop.gle"
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    fig.savefig_gle(str(path))

    line = glp.open_gle(str(path)).axes_list[0].lines[0]
    assert np.allclose(line["x"], CIRCLE_X)
    assert np.allclose(line["y"], CIRCLE_Y)


def test_reopening_and_resaving_does_not_reorder(tmp_path):
    first, second = tmp_path / "a.gle", tmp_path / "b.gle"
    fig = glp.figure(data_prefix="t")
    fig.add_subplot(111).plot(CIRCLE_X, CIRCLE_Y)
    fig.savefig_gle(str(first))
    glp.open_gle(str(first)).savefig_gle(str(second))

    rows = np.array(
        [
            [float(tok) for tok in ln.split()]
            for ln in (tmp_path / "t_0.dat").read_text().splitlines()
            if not ln.startswith("x")
        ]
    )
    assert np.allclose(rows, np.column_stack([CIRCLE_X, CIRCLE_Y]))

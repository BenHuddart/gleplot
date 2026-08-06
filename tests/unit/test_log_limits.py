"""A log axis is always emitted with a range GLE will compile.

GLE derives an axis' range from the data when the script does not give one,
and refuses to compile a log axis whose range reaches zero:

    Error: illegal range for log axis: min = 0 max = 3

That makes an omitted bound unusable on a log axis -- ``yaxis log`` over data
containing a zero is rejected exactly like ``yaxis min 0 log`` is -- so
gleplot resolves log limits itself (``Figure._apply_log_limits``), masking
the non-positive values the way matplotlib does and warning about what it
did.

The compiled half of this contract, which needs a GLE binary, lives in
``tests/integration/test_log_axis_compiles.py``.
"""

import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


AXIS_RE = re.compile(r'^\s*(x|y|y2)axis (.*)$', re.MULTILINE)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def axis_clauses(fig):
    """``{'x': 'min 1 max 3 log', ...}`` for the emitted axis commands."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        gle = fig._generate_gle()
    return {name: body.strip() for name, body in AXIS_RE.findall(gle)}


def figure_with(y, *, ylim=None, scale_axis='y', **kwargs):
    fig = glp.figure(data_prefix='log', **kwargs)
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.asarray(y, dtype=float))
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.set_yscale('log', axis=scale_axis)
    return fig


# -- the reported defect ----------------------------------------------------


def test_an_explicit_zero_lower_limit_is_replaced():
    """set_ylim(0, 400) on a log axis: the 0 goes, the 400 stays."""
    fig = figure_with([1.0, 2.0, 3.0], ylim=(0, 400))
    assert axis_clauses(fig)['y'] == 'min 1 max 400 log'


def test_an_explicit_negative_lower_limit_is_replaced():
    fig = figure_with([1.0, 2.0, 3.0], ylim=(-5, 400))
    assert axis_clauses(fig)['y'] == 'min 1 max 400 log'


def test_the_replacement_is_warned_about():
    fig = figure_with([1.0, 2.0, 3.0], ylim=(0, 400))
    with pytest.warns(UserWarning, match=r'y-axis is log-scaled'):
        fig._generate_gle()


def test_the_repaired_limits_are_stored_on_the_axes():
    """What the figure now means -- so the GUI's panels show it too."""
    fig = figure_with([1.0, 2.0, 3.0], ylim=(0, 400))
    axis_clauses(fig)
    assert (fig.axes_list[0].ymin, fig.axes_list[0].ymax) == (1.0, 400.0)


def test_a_second_save_neither_changes_nor_warns_again():
    """The repair is a fixed point: it has nothing left to do on re-save."""
    fig = figure_with([1.0, 2.0, 3.0], ylim=(0, 400))
    first = axis_clauses(fig)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        second = {
            name: body.strip() for name, body in AXIS_RE.findall(fig._generate_gle())
        }
    assert second == first


# -- the same hole on every axis -------------------------------------------


def test_the_primary_x_axis_has_the_same_policy():
    fig = glp.figure(data_prefix='log')
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xscale('log')
    assert axis_clauses(fig)['x'] == 'min 2 max 3 log'


def test_the_secondary_y_axis_has_the_same_policy():
    fig = glp.figure(data_prefix='log')
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([100.0, 200.0, 300.0]), yaxis='y2')
    ax.set_ylim(0, 400, axis='y2')
    ax.set_yscale('log', axis='y2')
    assert axis_clauses(fig)['y2'] == 'min 100 max 400 log'


# -- autoscale: mask the non-positive values, like matplotlib ---------------


def test_a_zero_in_the_data_is_masked_rather_than_autoscaled_over():
    fig = figure_with([0.0, 2.0, 3.0])
    assert axis_clauses(fig)['y'] == 'min 2 max 3 log'


def test_negative_data_is_masked_too():
    fig = figure_with([-1.0, 2.0, 3.0])
    assert axis_clauses(fig)['y'] == 'min 2 max 3 log'


def test_an_inverted_range_on_a_log_axis_is_repaired():
    """GLE rejects min >= max as hard as it rejects min <= 0."""
    fig = figure_with([1.0, 2.0, 3.0], ylim=(3, 1))
    lo, hi = re.match(r'min (\S+) max (\S+) log', axis_clauses(fig)['y']).groups()
    assert 0 < float(lo) < float(hi)


def test_all_non_positive_data_falls_back_to_a_legal_decade():
    """No positive value anywhere: still emit something GLE can draw."""
    fig = figure_with([-3.0, -2.0, -1.0])
    assert axis_clauses(fig)['y'] == 'min 1 max 10 log'


# -- restraint: leave alone what GLE already handles ------------------------


def test_positive_data_keeps_its_ordinary_autoscaled_range():
    """The common case must come out exactly as ordinary autoscale left it."""
    fig = figure_with([10.0, 100.0, 1000.0])
    assert axis_clauses(fig)['y'] == 'min 10 max 1000 log'


def test_an_omitted_bound_on_a_positive_secondary_axis_stays_omitted():
    """y2 limits are GLE's business unless gleplot sees a reason to intervene."""
    fig = glp.figure(data_prefix='log')
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([10.0, 100.0, 1000.0]), yaxis='y2')
    ax.set_yscale('log', axis='y2')

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert axis_clauses(fig)['y2'] == 'log'


def test_a_file_series_keeps_its_autoscale():
    """gleplot never read those numbers; inventing a range would be worse."""
    fig = glp.figure(data_prefix='log')
    ax = fig.add_subplot(111)
    ax.line_from_file('external.dat', 1, 2)
    ax.set_yscale('log')

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert axis_clauses(fig)['y'] == 'log'


def test_a_linear_axis_is_never_touched():
    """Zero is a perfectly good limit on a linear axis."""
    fig = glp.figure(data_prefix='log')
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([0.0, 2.0, 3.0]))
    ax.set_ylim(0, 400)

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert axis_clauses(fig)['y'] == 'min 0 max 400'


# -- shared axes ------------------------------------------------------------


def test_a_shared_log_axis_stays_shared_after_the_repair():
    """Sharing unifies ranges that are already positive, not the other way."""
    fig, axes = glp.subplots(2, 1, sharey=True, data_prefix='log')
    axes[0].plot(np.array([1.0, 2.0, 3.0]), np.array([0.0, 2.0, 3.0]))
    axes[1].plot(np.array([1.0, 2.0, 3.0]), np.array([-1.0, 40.0, 50.0]))
    for ax in axes:
        ax.set_yscale('log')

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        fig._generate_gle()
    limits = [(ax.ymin, ax.ymax) for ax in fig.axes_list]
    assert limits[0] == limits[1]
    # ... and the union is the positive union, not a per-panel guess.
    assert limits[0] == (2.0, 50.0)

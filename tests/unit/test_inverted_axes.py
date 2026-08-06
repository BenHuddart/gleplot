"""Descending limits invert an axis, the way they do in matplotlib.

``ax.set_ylim(3, 1)`` is matplotlib's idiom for inverting an axis. GLE will
not take the descending range -- "Error: illegal range for yaxis: min = 3
max = 1" -- but it has a keyword for exactly this: ``negate`` mirrors data
coordinates inside an ascending range. So the descending pair stays the
model, and ``GLEWriter._axis_direction`` is the one place it becomes GLE.

The compiled half of this contract lives in
``tests/integration/test_inverted_axis_compiles.py``.
"""

import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp
from gleplot.parser.recognizer import parse_gle_figure


AXIS_RE = re.compile(r'^\s*(x|y|y2)axis (.*)$', re.MULTILINE)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def axis_clauses(fig):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        gle = fig._generate_gle()
    return {name: body.strip() for name, body in AXIS_RE.findall(gle)}


def plot(**limits):
    fig = glp.figure(data_prefix='inv')
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    if 'xlim' in limits:
        ax.set_xlim(*limits['xlim'])
    if 'ylim' in limits:
        ax.set_ylim(*limits['ylim'])
    return fig


# -- the reported defect ----------------------------------------------------


def test_descending_y_limits_emit_an_ascending_range_and_negate():
    assert axis_clauses(plot(ylim=(3, 1)))['y'] == 'min 1 max 3 negate'


def test_descending_x_limits_emit_an_ascending_range_and_negate():
    assert axis_clauses(plot(xlim=(3, 1)))['x'] == 'min 1 max 3 negate'


def test_a_descending_secondary_y_axis_is_inverted_too():
    fig = glp.figure(data_prefix='inv')
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0]), yaxis='y2')
    ax.set_ylim(40, 5, axis='y2')
    assert axis_clauses(fig)['y2'] == 'min 5 max 40 negate'


def test_inverting_is_silent():
    """It does exactly what was asked; there is nothing to report."""
    fig = plot(ylim=(3, 1))
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        fig._generate_gle()


def test_ascending_limits_are_untouched():
    assert axis_clauses(plot(ylim=(1, 3)))['y'] == 'min 1 max 3'


def test_the_descending_pair_stays_on_the_model():
    """No separate inverted flag: the limit order IS the inversion."""
    fig = plot(ylim=(3, 1))
    axis_clauses(fig)
    assert (fig.axes_list[0].ymin, fig.axes_list[0].ymax) == (3, 1)
    assert fig.axes_list[0].get_ylim() == (3, 1)


# -- round trip -------------------------------------------------------------


def test_negate_survives_save_parse_save(tmp_path):
    fig = plot(ylim=(3, 1), xlim=(3, 1))
    first = tmp_path / 'inv.gle'
    fig.savefig_gle(str(first))
    text = first.read_text(encoding='utf-8')
    assert text.count('negate') == 2

    recovered = parse_gle_figure(first)
    ax = recovered.figure.axes_list[0]
    assert (ax.ymin, ax.ymax) == (3.0, 1.0)
    assert (ax.xmin, ax.xmax) == (3.0, 1.0)
    # ... modelled, not shovelled into passthrough ...
    assert ax.passthrough == []
    assert recovered.warnings == []

    second = tmp_path / 'inv2.gle'
    recovered.figure.savefig_gle(str(second))
    assert second.read_text(encoding='utf-8') == text


def test_a_hand_written_negate_without_both_bounds_stays_in_passthrough(tmp_path):
    """An inversion the model cannot express must not be silently dropped."""
    src = (
        'size 20.32 15.24\n'
        'set hei 0.42328\n'
        '\n'
        'amove 1.69312 1.26984\n'
        'begin graph\n'
        '    size 16.9338 13.3352\n'
        '    scale 1 1\n'
        '    yaxis negate\n'
        'end graph\n'
    )
    path = tmp_path / 'hand.gle'
    path.write_text(src, encoding='utf-8')

    recovered = parse_gle_figure(path)
    ax = recovered.figure.axes_list[0]
    assert (ax.ymin, ax.ymax) == (None, None)
    assert '    yaxis negate' in ax.passthrough
    assert any('yaxis' in w for w in recovered.warnings)


def test_serialization_round_trips_an_inverted_axis():
    fig = plot(ylim=(3, 1))
    restored = glp.Figure.from_dict(fig.to_dict())
    ax = restored.axes_list[0]
    assert (ax.ymin, ax.ymax) == (3, 1)


# -- log axes cannot be inverted -------------------------------------------


def test_a_descending_log_axis_is_normalized_rather_than_drawn_wrong():
    """GLE's negate mirrors linearly, then takes the log: unusable."""
    fig = plot(ylim=(100, 1))
    fig.axes_list[0].set_yscale('log')
    clause = axis_clauses(fig)['y']
    assert clause == 'min 1 max 100 log'
    assert 'negate' not in clause


def test_the_log_normalization_says_so():
    fig = plot(ylim=(100, 1))
    fig.axes_list[0].set_yscale('log')
    with pytest.warns(UserWarning, match='cannot invert a log axis'):
        fig._generate_gle()


def test_a_descending_log_axis_reaching_zero_is_still_made_positive():
    """The two repairs compose: undo the inversion, then fix the range."""
    fig = plot(ylim=(3, 0))
    fig.axes_list[0].set_yscale('log')
    assert axis_clauses(fig)['y'] == 'min 1 max 3 log'


# -- shared axes ------------------------------------------------------------


def test_sharing_an_inverted_axis_keeps_it_inverted():
    """Sharing unifies the span; it must not flip a panel back upright."""
    fig, axes = glp.subplots(2, 1, sharey=True, data_prefix='inv')
    for ax in axes:
        ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    axes[0].set_ylim(9, 1)
    axes[1].set_ylim(4, 2)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        gle = fig._generate_gle()
    assert [(ax.ymin, ax.ymax) for ax in fig.axes_list] == [(9, 1), (9, 1)]
    assert gle.count('yaxis min 1 max 9 negate') == 2

"""Integration tests for lossless figure serialization and project I/O.

The key guarantee under test: for a battery of figures exercising every
plotting feature, ``fig.to_dict() -> from_dict() -> to_dict()`` is an equal
dictionary, and the generated GLE script (plus every emitted data file) is
byte-identical before and after a round-trip.

Each figure is described by a zero-argument *builder* so it can be
constructed twice from a pristine state. A fixed ``data_prefix`` makes the
generated data-file names deterministic and independent of the module-global
counter, which is what makes the byte-for-byte GLE comparison meaningful.
"""

import numpy as np
import pytest

import gleplot as glp
from gleplot import Figure, save_project, load_project


# -- Figure builders (one per feature area) ---------------------------------

def _single_line():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color='blue', label='quad')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('single line')
    return fig


def _multi_series_styles():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 20)
    ax.plot(x, np.sin(x), color='red', linestyle='--', linewidth=2, label='sin')
    ax.plot(x, np.cos(x), color='green', linestyle=':', label='cos')
    ax.plot(x, np.sin(x) * 0.5, color='blue', marker='o', linestyle='none',
            markersize=8, label='half')
    ax.legend(loc='upper left')
    return fig


def _scatter():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3, 4], [4, 3, 2, 1], color='purple', s=40, marker='s',
               label='pts')
    ax.legend()
    return fig


def _bar():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color='orange')
    ax.set_title('bar')
    return fig


def _errorbar_symmetric():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.5, color='red', marker='o',
                capsize=4, label='sym')
    ax.legend()
    return fig


def _errorbar_asymmetric():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6],
                yerr=([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]),
                color='blue', marker='s', capsize=3)
    return fig


def _errorbar_xerr():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.3, xerr=0.2, capsize=5,
                color='green', marker='^')
    return fig


def _fill_between():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), x ** 0.5, color='lightblue', alpha=0.4)
    ax.plot(x, x ** 0.5, color='blue')
    return fig


def _text_annotations():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.text(1.5, 2.0, 'peak', color='red', fontsize=14, ha='center')
    ax.text(2.5, 1.0, 'boxed', bbox={'facecolor': 'yellow'})
    return fig


def _log_scales():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    x = np.array([1, 10, 100, 1000], dtype=float)
    ax.plot(x, x ** 2, color='blue')
    ax.set_xscale('log')
    ax.set_yscale('log')
    return fig


def _limits():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16])
    ax.set_xlim(0, 5)
    ax.set_ylim(-1, 20)
    return fig


def _legend_positions():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label='a')
    ax.legend(loc='lower right')
    return fig


def _secondary_yaxis():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color='blue', label='left', yaxis='y')
    ax.plot([1, 2, 3], [100, 200, 300], color='red', label='right', yaxis='y2')
    ax.set_ylabel('left y')
    ax.set_ylabel('right y', axis='y2')
    ax.set_ylim(0, 400, axis='y2')
    ax.set_yscale('log', axis='y2')
    ax.legend()
    return fig


def _subplots_sharex():
    fig, axes = glp.subplots(3, 1, sharex=True, data_prefix='fig')
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f's{i}')
        ax.set_ylabel(f'y{i}')
    axes[-1].set_xlabel('shared x')
    return fig


def _subplots_sharey_adjust():
    fig, axes = glp.subplots(1, 3, sharey=True, data_prefix='fig')
    for i, ax in enumerate(axes):
        ax.bar([1, 2, 3], [i + 1, i + 2, i + 3], color='teal')
        ax.set_title(f'c{i}')
    fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.15, wspace=0.3)
    return fig


def _subplots_grid():
    fig, axes = glp.subplots(2, 2, data_prefix='fig')
    axes[0].plot([1, 2, 3], [1, 2, 3])
    axes[1].scatter([1, 2, 3], [3, 2, 1], marker='o')
    axes[2].bar([1, 2, 3], [2, 4, 6], color='red')
    axes[3].errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, capsize=3)
    fig.subplots_adjust(hspace=0.4, wspace=0.4)
    return fig


def _file_series():
    fig = glp.figure(data_prefix='fig')
    ax = fig.add_subplot(111)
    ax.line_from_file('external.dat', 1, 2, color='blue', linestyle='--',
                      label='line-file')
    ax.errorbar_from_file('external.dat', 1, 2, yerr_col=3, color='red',
                          marker='o', capsize=4, label='eb-file')
    ax.legend()
    return fig


def _data_prefix_multi():
    # Multiple generated series to exercise data_prefix counter round-trip.
    fig = glp.figure(data_prefix='myrun')
    ax = fig.add_subplot(111)
    for i in range(4):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f'l{i}')
    ax.legend()
    return fig


BUILDERS = [
    _single_line,
    _multi_series_styles,
    _scatter,
    _bar,
    _errorbar_symmetric,
    _errorbar_asymmetric,
    _errorbar_xerr,
    _fill_between,
    _text_annotations,
    _log_scales,
    _limits,
    _legend_positions,
    _secondary_yaxis,
    _subplots_sharex,
    _subplots_sharey_adjust,
    _subplots_grid,
    _file_series,
    _data_prefix_multi,
]

BUILDER_IDS = [b.__name__.lstrip('_') for b in BUILDERS]


# -- The key tests ----------------------------------------------------------

@pytest.mark.parametrize('builder', BUILDERS, ids=BUILDER_IDS)
def test_dict_round_trip_equal(builder):
    """to_dict -> from_dict -> to_dict yields an equal dict."""
    fig = builder()
    d1 = fig.to_dict()
    d2 = Figure.from_dict(d1).to_dict()
    assert d1 == d2


@pytest.mark.parametrize('builder', BUILDERS, ids=BUILDER_IDS)
def test_gle_byte_identical_after_round_trip(builder):
    """Generated GLE script and data files are byte-identical after a
    serialization round-trip.

    Both sides are built from a pristine figure so that in-place limit
    derivation during GLE generation cannot leak across the comparison.
    """
    gle_before, data_before = builder()._generate_gle_with_files()
    fig_after = Figure.from_dict(builder().to_dict())
    gle_after, data_after = fig_after._generate_gle_with_files()

    assert gle_after == gle_before
    assert data_after == data_before


@pytest.mark.parametrize('builder', BUILDERS, ids=BUILDER_IDS)
def test_project_file_round_trip(builder, tmp_path):
    """save_project/load_project preserve the figure losslessly and produce
    identical GLE, and the file is valid indented UTF-8 JSON."""
    fig = builder()
    path = tmp_path / 'project.glep'
    returned = save_project(fig, path)
    assert returned == path
    assert path.exists()

    # Human-readable, UTF-8, indented.
    text = path.read_text(encoding='utf-8')
    assert '\n  ' in text  # indent=2 produced nested indentation

    loaded = load_project(path)
    assert loaded.to_dict() == fig.to_dict()

    gle_reference, data_reference = builder()._generate_gle_with_files()
    gle_loaded, data_loaded = loaded._generate_gle_with_files()
    assert gle_loaded == gle_reference
    assert data_loaded == data_reference


def test_load_project_rejects_bad_envelope(tmp_path):
    bad = tmp_path / 'bad.glep'
    bad.write_text('{"format": "something-else", "version": 1}', encoding='utf-8')
    with pytest.raises(ValueError):
        load_project(bad)


def test_gui_workflow_empty_mutate_serialize(tmp_path):
    """Mirrors the GUI lifecycle: create empty figure, add axes + series,
    serialize, reload, and mutate again -- all lossless."""
    # Construct an empty figure.
    fig = glp.figure(data_prefix='gui')
    assert fig.axes_list == []

    # Add an axes and a series (GUI mutation of the object model).
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color='blue', label='v1')

    # Serialize / reload.
    path = tmp_path / 's.glep'
    save_project(fig, path)
    fig2 = load_project(path)

    # Mutate the reloaded model further.
    fig2.axes_list[0].plot([1, 2, 3], [3, 2, 1], color='red', label='v2')
    assert len(fig2.axes_list[0].lines) == 2

    # Re-serialization is still lossless.
    d = fig2.to_dict()
    assert Figure.from_dict(d).to_dict() == d

"""Shared golden-battery figure builders for the writer-refactor guard test.

Reuses the same battery style as ``tests/integration/test_project_io.py``:
each builder is a zero-argument callable constructing a fresh
:class:`gleplot.Figure` exercising a distinct writer code path (series
types, subplots, text, y2 axis, file-series, legends, log scales, etc.).
``test_units.py`` snapshots ``_generate_gle_with_files()`` output for every
builder before and after the units/tables refactor and asserts byte-for-byte
identity, guarding the "zero behavior change" requirement for Track A2.
"""

import numpy as np

import gleplot as glp


def single_line():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color='blue', label='quad')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('single line')
    return fig


def multi_series_styles():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    x = np.linspace(0, 10, 20)
    ax.plot(x, np.sin(x), color='red', linestyle='--', linewidth=2, label='sin')
    ax.plot(x, np.cos(x), color='green', linestyle=':', label='cos')
    ax.plot(x, np.sin(x) * 0.5, color='blue', marker='o', linestyle='none',
            markersize=8, label='half')
    ax.plot(x, np.cos(x) * 0.5, color='black', linestyle='-.', linewidth=3, label='dashdot')
    ax.legend(loc='upper left')
    return fig


def scatter():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3, 4], [4, 3, 2, 1], color='purple', s=40, marker='s',
               label='pts')
    ax.legend()
    return fig


def bar():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3, 4, 5], [10, 24, 36, 18, 7], color='orange')
    ax.set_title('bar')
    return fig


def errorbar_symmetric():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6], yerr=0.5, color='red', marker='o',
                capsize=4, label='sym')
    ax.legend()
    return fig


def errorbar_asymmetric_xy():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [2, 4, 6],
                yerr=([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]),
                xerr=0.2, capsize=3,
                color='blue', marker='s')
    return fig


def fill_between():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    x = np.linspace(0, 5, 10)
    ax.fill_between(x, np.zeros_like(x), x ** 0.5, color='lightblue', alpha=0.4)
    ax.plot(x, x ** 0.5, color='blue')
    return fig


def text_annotations():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    ax.text(1.5, 2.0, 'peak', color='red', fontsize=14, ha='center')
    ax.text(2.5, 1.0, 'boxed', bbox={'facecolor': 'yellow'})
    return fig


def secondary_yaxis():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], color='blue', label='left', yaxis='y')
    ax.plot([1, 2, 3], [100, 200, 300], color='red', label='right', yaxis='y2')
    ax.set_ylabel('left y')
    ax.set_ylabel('right y', axis='y2')
    ax.set_ylim(0, 400, axis='y2')
    ax.set_yscale('log', axis='y2')
    ax.legend()
    return fig


def legend_positions_all():
    figs = []
    for loc in ('upper right', 'upper left', 'lower left', 'lower right', 'center', 'best'):
        fig = glp.figure(data_prefix='golden')
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], label=loc)
        ax.legend(loc=loc)
        figs.append(fig)
    return figs[0]


def subplots_sharex():
    fig, axes = glp.subplots(3, 1, sharex=True, data_prefix='golden')
    for i, ax in enumerate(axes):
        ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f's{i}')
        ax.set_ylabel(f'y{i}')
    axes[-1].set_xlabel('shared x')
    return fig


def subplots_grid_mixed():
    fig, axes = glp.subplots(2, 2, data_prefix='golden')
    axes[0].plot([1, 2, 3], [1, 2, 3])
    axes[1].scatter([1, 2, 3], [3, 2, 1], marker='o')
    axes[2].bar([1, 2, 3], [2, 4, 6], color='red')
    axes[3].errorbar([1, 2, 3], [1, 2, 3], yerr=0.2, capsize=3)
    fig.subplots_adjust(hspace=0.4, wspace=0.4)
    return fig


def file_series():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.line_from_file('external.dat', 1, 2, color='blue', linestyle='--',
                      label='line-file')
    ax.errorbar_from_file('external.dat', 1, 2, yerr_col=3, color='red',
                          marker='o', capsize=4, label='eb-file')
    ax.legend()
    return fig


def large_markersize_and_linewidth():
    fig = glp.figure(data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], linewidth=0.25, marker='D', markersize=20, label='thin-big')
    ax.plot([1, 2, 3], [3, 2, 1], linewidth=4.5, label='thick')
    ax.legend()
    return fig


def custom_figsize_and_dpi():
    fig = glp.figure(figsize=(10, 4), dpi=150, data_prefix='golden')
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    return fig


BUILDERS = [
    single_line,
    multi_series_styles,
    scatter,
    bar,
    errorbar_symmetric,
    errorbar_asymmetric_xy,
    fill_between,
    text_annotations,
    secondary_yaxis,
    legend_positions_all,
    subplots_sharex,
    subplots_grid_mixed,
    file_series,
    large_markersize_and_linewidth,
    custom_figsize_and_dpi,
]

BUILDER_IDS = [b.__name__ for b in BUILDERS]

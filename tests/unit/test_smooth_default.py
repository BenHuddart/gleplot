"""A drawn curve must be the data unless smoothing is explicitly asked for.

GLE's ``smooth`` qualifier replaces the polyline through a dataset's points
with a fitted piecewise cubic: the rendered curve passes near, not through,
the measurements, overshoots steep steps and rings around noise. gleplot used
to emit it on every line series by default (``GLEGraphConfig.smooth_curves``
defaulted to ``True``), so every figure any downstream project ever drew was
an interpolation presented as data.

These tests pin the contract on the generated GLE text:

* **by default no emitted command carries a ``smooth`` token** -- for any
  line-drawing path (``plot``, line+marker, ``errorbar`` in each of its
  branches, ``line_from_file``), and for the paths that never smooth
  (``fill_between``, contour lines);
* **opting in emits it** on exactly those line-drawing paths, per figure
  (``GLEGraphConfig(smooth_curves=True)``) or globally
  (``GlobalConfig.graph.smooth_curves``), and still never on a fill or a
  contour polyline.
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


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return text


def _dataset_commands(script: str) -> list[str]:
    """The ``dN <attributes>`` display commands, in emission order."""
    return [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]


def _line_commands(script: str) -> list[str]:
    """Dataset commands that actually draw a line (the smoothable ones)."""
    return [c for c in _dataset_commands(script) if re.search(r"\bline\b", c)]


def _has_smooth(script: str) -> bool:
    return re.search(r"\bsmooth\b", script) is not None


# --------------------------------------------------------------------------- #
# builders -- one per emission path that can draw a line
# --------------------------------------------------------------------------- #

X = np.linspace(0.0, 1.0, 9)
#: Deliberately jagged: a spline through this is visibly not the data.
Y = np.array([0.0, 1.0, 0.05, 0.95, 0.1, 0.9, 0.15, 0.85, 0.2])


def _fig_plot(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red")
    return fig


def _fig_plot_with_marker(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red", marker="o")
    return fig


def _fig_plot_dashed(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="blue", linestyle="--")
    return fig


def _fig_errorbar_line_only(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.errorbar(X, Y, yerr=0.05 * np.ones_like(X), fmt="-", color="green")
    return fig


def _fig_errorbar_line_and_marker(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.errorbar(X, Y, yerr=0.05 * np.ones_like(X), fmt="-", marker="o", color="green")
    return fig


def _fig_line_from_file(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.line_from_file("model.dat", 1, 2, color="purple")
    return fig


def _fig_secondary_axis(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red")
    ax.plot(X, Y * 2, color="blue", yaxis="y2")
    return fig


#: Every builder whose figure draws at least one line.
LINE_BUILDERS = [
    _fig_plot,
    _fig_plot_with_marker,
    _fig_plot_dashed,
    _fig_errorbar_line_only,
    _fig_errorbar_line_and_marker,
    _fig_line_from_file,
    _fig_secondary_axis,
]


def _fig_scatter(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.scatter(X, Y, color="red")
    return fig


def _fig_fill_between(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.fill_between(X, Y - 0.1, Y + 0.1, color="lightblue")
    return fig


def _fig_contour(graph=None):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    gx = np.linspace(0, 4, 5)
    gy = np.linspace(0, 3, 4)
    ax.contour(gx, gy, np.outer(gy, gx), levels=[2.0, 4.0], colors="red")
    return fig


#: Builders whose figures must never carry ``smooth``, opted in or not:
#: a scatter has no line, GLE's ``fill dA,dB`` takes no ``smooth``, and a
#: contour polyline comes out of GLE's own gridding of the surface.
NEVER_SMOOTH_BUILDERS = [_fig_scatter, _fig_fill_between, _fig_contour]

ALL_BUILDERS = LINE_BUILDERS + NEVER_SMOOTH_BUILDERS


# --------------------------------------------------------------------------- #
# the default: no smoothing anywhere
# --------------------------------------------------------------------------- #


def test_config_default_is_off():
    assert glp.GLEGraphConfig().smooth_curves is False
    assert glp.GlobalConfig.graph.smooth_curves is False
    assert glp.figure().graph.smooth_curves is False


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=lambda b: b.__name__)
def test_no_smooth_token_by_default(builder):
    """Not one ``smooth`` anywhere in the script, on any path."""
    assert not _has_smooth(_script(builder()))


def test_plain_plot_emits_bare_line():
    """The exact token sequence: ``line`` goes straight into ``color``."""
    cmds = _line_commands(_script(_fig_plot()))
    assert len(cmds) == 1
    assert re.search(r"\bline color RED\b", cmds[0])


def test_default_holds_for_every_line_in_a_multi_series_figure():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    for i in range(12):
        ax.plot(X, Y + i, label=f"s{i}")
    script = _script(fig)
    assert not _has_smooth(script)
    assert len(_line_commands(script)) == 12


# --------------------------------------------------------------------------- #
# opting in
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("builder", LINE_BUILDERS, ids=lambda b: b.__name__)
def test_per_figure_opt_in_smooths_every_line(builder):
    graph = glp.GLEGraphConfig(smooth_curves=True)
    cmds = _line_commands(_script(builder(graph=graph)))
    assert cmds, "builder drew no line command"
    for cmd in cmds:
        assert re.search(r"\bline smooth\b", cmd), cmd


@pytest.mark.parametrize("builder", NEVER_SMOOTH_BUILDERS, ids=lambda b: b.__name__)
def test_opt_in_never_smooths_fills_scatters_or_contours(builder):
    graph = glp.GLEGraphConfig(smooth_curves=True)
    assert not _has_smooth(_script(builder(graph=graph)))


def test_global_opt_in_applies_to_new_figures():
    glp.GlobalConfig.graph.smooth_curves = True
    assert _has_smooth(_script(_fig_plot()))


def test_global_reset_restores_the_off_default():
    glp.GlobalConfig.graph.smooth_curves = True
    glp.GlobalConfig.reset()
    assert glp.GlobalConfig.graph.smooth_curves is False
    assert not _has_smooth(_script(_fig_plot()))


def test_opt_in_keeps_the_rest_of_the_command_intact():
    """``smooth`` is inserted, nothing else moves."""
    off = _line_commands(_script(_fig_plot_dashed()))[0]
    on = _line_commands(
        _script(_fig_plot_dashed(glp.GLEGraphConfig(smooth_curves=True)))
    )[0]
    assert on == off.replace(" line ", " line smooth ", 1)


# --------------------------------------------------------------------------- #
# round trips
# --------------------------------------------------------------------------- #


def test_serialization_round_trip_preserves_the_flag():
    for value in (False, True):
        fig = glp.figure(graph=glp.GLEGraphConfig(smooth_curves=value))
        assert glp.Figure.from_dict(fig.to_dict()).graph.smooth_curves is value


def test_open_gle_recovers_unsmoothed_figures_as_unsmoothed(tmp_path):
    path = tmp_path / "plain.gle"
    _fig_plot().savefig_gle(str(path))
    assert glp.open_gle(str(path)).graph.smooth_curves is False


def test_open_gle_recovers_smoothed_figures_as_smoothed(tmp_path):
    path = tmp_path / "smoothed.gle"
    _fig_plot(glp.GLEGraphConfig(smooth_curves=True)).savefig_gle(str(path))
    assert glp.open_gle(str(path)).graph.smooth_curves is True

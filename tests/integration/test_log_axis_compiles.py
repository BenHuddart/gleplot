"""Every log axis gleplot emits is one the real GLE binary will compile.

This is the acceptance bar the unit tests in ``tests/unit/test_log_limits.py``
stand in for: GLE rejects a log axis whose range reaches zero, with

    Error: illegal range for log axis: min = 0 max = 3

and none of the writer/recognizer batteries would notice, because they
round-trip their GLE as text rather than compiling it. Every figure below
produced an uncompilable script until 2026-08-06. Skipped when GLE is not
installed.

The repair warns, loudly and by design; the warning is asserted in the unit
tests, and silenced here so these cases test compilation and nothing else.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = [
    pytest.mark.skipif(not _gle_available(), reason="GLE binary not available"),
    pytest.mark.filterwarnings("ignore:.*log-scaled.*:UserWarning"),
]


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _assert_compiles(fig, tmp_path, name):
    """Compile ``fig`` to PDF. ``savefig`` raises if GLE rejects the script."""
    out = fig.savefig(str(tmp_path / f"{name}.pdf"))
    assert out.exists() and out.stat().st_size > 0


def test_an_explicit_zero_limit_on_a_log_y2_axis_compiles(tmp_path):
    """The reported defect, as the golden battery used to build it."""
    fig = glp.figure(data_prefix="logc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), label="left")
    ax.plot(
        np.array([1.0, 2.0, 3.0]),
        np.array([100.0, 200.0, 300.0]),
        label="right",
        yaxis="y2",
    )
    ax.set_ylim(0, 400, axis="y2")
    ax.set_yscale("log", axis="y2")
    _assert_compiles(fig, tmp_path, "y2zero")


@pytest.mark.parametrize(
    "y",
    [[0.0, 2.0, 3.0], [-1.0, 2.0, 3.0], [-3.0, -2.0, -1.0]],
    ids=["zero", "negative", "all-negative"],
)
def test_autoscaled_log_y_over_non_positive_data_compiles(y, tmp_path):
    """No explicit limits at all: GLE would autoscale straight into the error."""
    fig = glp.figure(data_prefix="logc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array(y))
    ax.set_yscale("log")
    _assert_compiles(fig, tmp_path, "autoscale")


def test_autoscaled_log_x_over_non_positive_data_compiles(tmp_path):
    fig = glp.figure(data_prefix="logc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([0.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xscale("log")
    _assert_compiles(fig, tmp_path, "xauto")


def test_an_explicit_zero_limit_on_a_log_x_axis_compiles(tmp_path):
    fig = glp.figure(data_prefix="logc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    ax.set_xlim(0, 10)
    ax.set_xscale("log")
    _assert_compiles(fig, tmp_path, "xzero")


def test_a_shared_log_axis_grid_compiles(tmp_path):
    fig, axes = glp.subplots(2, 1, sharey=True, data_prefix="logc")
    axes[0].plot(np.array([1.0, 2.0, 3.0]), np.array([0.0, 2.0, 3.0]))
    axes[1].plot(np.array([1.0, 2.0, 3.0]), np.array([-1.0, 40.0, 50.0]))
    for ax in axes:
        ax.set_yscale("log")
    _assert_compiles(fig, tmp_path, "shared")


def test_the_golden_battery_secondary_yaxis_figure_compiles(tmp_path):
    """The builder itself, which is meant to exercise the y2-log writer path."""
    from tests.parser import _golden_battery as golden

    _assert_compiles(golden.secondary_yaxis(), tmp_path, "golden")


def test_an_ordinary_positive_log_plot_still_compiles(tmp_path):
    """Guards the repair against breaking the case that always worked."""
    fig = glp.figure(data_prefix="logc")
    ax = fig.add_subplot(111)
    ax.plot(np.array([1.0, 2.0, 3.0]), np.array([10.0, 100.0, 1000.0]))
    ax.set_yscale("log")
    _assert_compiles(fig, tmp_path, "positive")

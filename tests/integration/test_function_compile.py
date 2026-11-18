"""Function and fit curves compile on GLE.

The script text is asserted in ``tests/unit/test_plotting.py``. This checks
what a string match cannot: that the ``let`` gleplot writes, with and
without a range, beside ordinary data, is a script GLE accepts, for an
expression fit and for each closed-form routine.
"""

from __future__ import annotations

import pytest

import gleplot as glp

pytestmark = pytest.mark.gle


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def test_function_curves_compile(tmp_path):
    fig = glp.figure(data_prefix="fnc")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.function("exp(-x^2/2)", xmin=-3, xmax=3, step=0.1, linestyle="--", label="g")
    ax.function("max(x,1)")
    ax.legend()
    out = tmp_path / "function.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


def test_fit_curves_compile(tmp_path):
    fig = glp.figure(data_prefix="fit")
    ax = fig.add_subplot(111)
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    y = [2.3, 1.33, 0.83, 0.57, 0.44]
    ax.scatter(x, y)
    ax.fit(x, y, "a*exp(-x/b)+c", xmin=0, xmax=5, step=0.1, label="fit")
    ax.fit(x, y, "k*x+m", linestyle="--")
    ax.legend()
    out = tmp_path / "fit.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


def test_closed_form_fits_compile(tmp_path):
    fig = glp.figure(data_prefix="cff")
    ax = fig.add_subplot(111)
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.1, 2.9, 5.2, 8.1]
    ax.scatter(x, y)
    for model in ("linear", "exp", "exp10", "power"):
        ax.fit(x, y, model=model, xmin=0.5, xmax=4.5, label=model)
    ax.legend()
    out = tmp_path / "closed.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

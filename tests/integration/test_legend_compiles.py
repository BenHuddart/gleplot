"""Bar, fill, and span legend swatches compile on GLE 4.3.10.

The script text is asserted in ``tests/unit/test_legend.py``. This checks
the part a string match cannot: that ``dN key``, ``keyfill``, ``key
separator``, ``compact``, ``background``, the spacing options, and an
anchored ``begin key`` whose ``absolute`` reads ``xg()``/``yg()`` of the
graph that has just ended are a script GLE accepts.
Skipped when the binary is missing.
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


def test_swatches_columns_and_background_compile(tmp_path):
    fig = glp.figure(data_prefix="legc")
    ax = fig.add_subplot(111)
    ax.bar([0, 1, 2], [1, 3, 2], color="C0", label="control")
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 2, 1], label="band", alpha=0.3)
    ax.plot([0, 1, 2], [0.5, 1.5, 0.5], label="fit")
    ax.axvspan(0.4, 1.2, color="orange", alpha=0.4, label="window")
    ax.legend(ncol=2, compact=True, facecolor="green")
    out = tmp_path / "legend.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(ncol=2, handlelength=1.5, handletextpad=0.5, columnspacing=1.0),
        dict(loc="upper right", bbox_to_anchor=(-0.1, 1.0), borderpad=0.2),
        dict(loc="lower center", bbox_to_anchor=(0, 1.02, 1, 0.2), labelcolor="gray"),
    ],
)
def test_spacing_anchor_and_labelcolor_compile(tmp_path, kwargs):
    fig = glp.figure(data_prefix="legc")
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0.5, 1.5, 0.5], label="fit", marker="o")
    ax.plot([0, 1, 2], [1.5, 0.5, 1.5], label="data", linestyle="--")
    ax.set_xlim(2, 0)  # an inverted axis: the anchor still measures from the left
    ax.legend(**kwargs)
    out = tmp_path / "legend.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(loc="lower center", ncol=2, frameon=False, labelcolor="gray"),
        dict(loc="center left", bbox_to_anchor=(-0.1, 0.5), facecolor="yellow"),
    ],
)
def test_figure_legend_compiles(tmp_path, kwargs):
    """A page-level ``begin key`` placed with ``pagewidth()``/``pageheight()``."""
    fig, axes = glp.subplots(1, 2, data_prefix="legf")
    axes[0].plot([0, 1, 2], [0.5, 1.5, 0.5], label="fit", marker="o")
    axes[1].bar([0, 1], [1, 2], label="counts")
    fig.legend(**kwargs)
    out = tmp_path / "legend.pdf"
    fig.savefig(str(out))
    assert out.is_file()
    assert out.stat().st_size > 0

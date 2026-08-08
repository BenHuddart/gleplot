"""Compiled proof for write-time grid autos (G13; GLEstudio SPEC 14.5).

``tests/unit/test_grid_auto_resolution.py`` asserts on the script gleplot
emits for a reference-backed heatmap/contour whose ``extent`` -- and whose
colorbar range -- are computed per write. This file asserts that GLE 4.3.10
actually accepts that script:

* a :class:`~gleplot.sources.GridRef` heatmap with an auto extent and an auto
  colorbar range, resolved through a
  :class:`~gleplot.sources.DictDataProvider`, compiles;
* editing the provider's data and writing again changes the emitted
  ``zmin``/``zmax`` -- and the *rendered* colorbar tick labels -- which is the
  staleness fix made observable: a range baked at ``colorbar()`` time could
  not do this, because at ``colorbar()`` time there were no arrays to bake;
* the points path (auto extent -> ``begin fitz``'s ``x from ... to ...``)
  compiles too.

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler
from gleplot.series import ContourSeries, HeatmapSeries
from gleplot.sources import DictDataProvider, GridRef, TableData


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


def _provider(**tables):
    return DictDataProvider({k: TableData.from_mapping(v) for k, v in tables.items()})


#: One glyph per ``(c) s`` call in GLE's EPS output, in drawing order.
_SHOW_RE = re.compile(r"^\((.*)\) s$", re.MULTILINE)


def _drawn_text(path) -> str:
    """Every character GLE actually drew, concatenated in drawing order.

    GLE emits one show call per glyph, with non-ASCII-safe characters as
    octal escapes (``\\56`` for ``.``). Joining them recovers the label text
    -- enough to read a colorbar's tick numbers back out of the compiled
    output rather than trusting the script that asked for them.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for glyph in _SHOW_RE.findall(text):
        out.append(re.sub(r"\\([0-7]{1,3})", lambda m: chr(int(m.group(1), 8)), glyph))
    return "".join(out)


def _grid_table(scale: float = 1.0):
    """A 4-row x 3-column grid; ``scale`` moves the z range wholesale."""
    base = np.arange(12, dtype=float).reshape(4, 3) * scale
    return {f"c{j}": base[:, j].tolist() for j in range(3)}


def _grid_heatmap_figure():
    """A heatmap with BOTH autos left for write time, plus a colorbar."""
    fig = glp.figure(figsize=(6, 5), data_prefix="g13ref")
    ax = fig.add_subplot(111)
    ax.heatmaps.append(
        HeatmapSeries(
            type="heatmap",
            source="grid",
            z=None,
            x=None,
            y=None,
            zpts=None,
            extent=None,  # auto: (0, nx, 0, ny) per write
            origin="lower",
            cmap="viridis",
            vmin=None,
            vmax=None,
            interpolation="bicubic",
            pixels=[64, 64],
            invert=False,
            gridsize=None,
            ncontour=None,
            label=None,
            data_file="g13ref_heatmap1.z",
            data_source=GridRef("t1", {"z": ["c0", "c1", "c2"]}),
            colorbar=None,
        )
    )
    fig.colorbar(label="signal")  # auto range: no arrays to bake one from
    return fig


@pytest.mark.gle
def test_a_grid_ref_heatmap_with_a_colorbar_compiles(tmp_path):
    fig = _grid_heatmap_figure()
    hm = fig.axes_list[0].heatmaps[0]
    assert hm["extent"] is None
    assert hm["colorbar"]["zmin"] is None

    out = fig.savefig(
        str(tmp_path / "gridref.pdf"), data_provider=_provider(t1=_grid_table())
    )

    assert fig.source_warnings == []
    assert (tmp_path / "gridref.pdf").exists()
    assert (tmp_path / "gridref.pdf").stat().st_size > 0
    assert out is not None
    # The document is still in its auto state -- the write filled a copy.
    assert hm["extent"] is None
    assert hm["colorbar"]["zmin"] is None


@pytest.mark.gle
def test_a_provider_data_change_alters_the_compiled_colorbar_range(tmp_path):
    """The staleness fix, observable in the compiled PostScript.

    Same figure object, same colorbar, two writes against two versions of the
    table: the emitted ``zmin``/``zmax`` follow the data, and so do the tick
    numbers GLE draws next to the bar.
    """
    fig = _grid_heatmap_figure()

    first = fig._generate_gle(data_provider=_provider(t1=_grid_table()))
    second = fig._generate_gle(data_provider=_provider(t1=_grid_table(scale=10.0)))

    assert "gleplot_colorbar_v zmin 0 zmax 11" in first
    assert "gleplot_colorbar_v zmin 0 zmax 110" in second

    fig.savefig(
        str(tmp_path / "before.eps"),
        format="eps",
        data_provider=_provider(t1=_grid_table()),
    )
    fig.savefig(
        str(tmp_path / "after.eps"),
        format="eps",
        data_provider=_provider(t1=_grid_table(scale=10.0)),
    )

    before = _drawn_text(tmp_path / "before.eps")
    after = _drawn_text(tmp_path / "after.eps")

    # GLE drew the bar's ticks from the range THIS write resolved, not from a
    # value baked when the series had no arrays at all. (The colorbar is the
    # last thing on the page, so its tick run plus its label is the tail.)
    assert before.endswith("0.02.24.46.68.811.0signal")
    assert after.endswith("0.022.044.066.088.0110.0signal")


@pytest.mark.gle
def test_a_points_mode_grid_ref_auto_extent_compiles(tmp_path):
    """The auto extent becomes ``begin fitz``'s ``x from ... to ...``."""
    rng = np.random.default_rng(7)
    px = rng.uniform(0.0, 4.0, 40)
    py = rng.uniform(-2.0, 2.0, 40)
    pz = np.sin(px) + np.cos(py)

    fig = glp.figure(figsize=(6, 5), data_prefix="g13pts")
    ax = fig.add_subplot(111)
    ax.contours.append(
        ContourSeries(
            type="contour",
            source="points",
            z=None,
            x=None,
            y=None,
            zpts=None,
            extent=None,  # auto: the sample bounds per write
            levels=None,
            color="BLACK",
            linewidth=1.0,
            linestyle=None,
            clabel=False,
            clabel_fmt="fix 1",
            gridsize=[20, 20],
            ncontour=3,
            label=None,
            data_file="g13pts_contour1.dat",
            data_source=GridRef("t1", {"x": "px", "y": "py", "zpts": "pz"}),
        )
    )

    provider = _provider(t1={"px": px.tolist(), "py": py.tolist(), "pz": pz.tolist()})
    script = fig._generate_gle(data_provider=provider)
    assert f"x from {px.min():g} to {px.max():g}" in script

    fig.savefig(str(tmp_path / "pts.pdf"), data_provider=provider)

    assert fig.source_warnings == []
    assert (tmp_path / "pts.pdf").stat().st_size > 0

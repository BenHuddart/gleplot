"""The recognizer fixed-point test: writer -> recognizer -> writer is stable.

For every figure in the golden battery (and the project-I/O battery), saving
to ``.gle``, parsing it back with :func:`parse_gle_figure`, and saving again
must produce byte-identical GLE text AND byte-identical ``.dat`` sidecars.

This is the acceptance bar for Track B1: ``.gle`` is a lossless native save
format for gleplot's own output.

**There are no exemptions.** There used to be three: builders whose
``subplots_adjust`` overrides baked into cm geometry that the grid path could
not invert, so they re-saved with default spacing. Since metadata v2 every
graph block carries an explicit ``amove``/``size``/``scale 1 1`` frame rect
which the recognizer reads straight back into ``Axes.placement``, so the
geometry is recovered rather than re-derived and the exemption set is empty --
the exit criterion of SPEC 10.2. Keep it that way: a builder that cannot make
this test pass is a writer/recognizer bug, not a candidate for a new exemption.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot
from gleplot import axes as _gleplot_axes
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.series import SERIES_CLASSES
from gleplot.sources import is_inline
from gleplot.writer import COLORBAR_AUTO_RANGE
from tests.integration import test_project_io as project_battery
from tests.parser import _golden_battery as golden

#: Builders exempted from byte-identity. Empty, and asserted to stay empty:
#: this is the SPEC 10.2 exit criterion (see the module docstring).
_EXEMPT: frozenset = frozenset()


def test_the_exemption_set_is_empty():
    """SPEC 10.2 exit criterion, asserted rather than merely documented."""
    assert _EXEMPT == frozenset()


@pytest.fixture(autouse=True)
def _reset_counter():
    """Deterministic global data-file counter around every test."""
    _gleplot_axes._global_data_file_counter = 0
    gleplot.close()
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        gleplot.close()


def _save(fig, directory: Path):
    """Save ``fig`` into ``directory`` and return (gle_text, {name: dat_bytes})."""
    gle_path = directory / "figure.gle"
    fig.savefig_gle(str(gle_path))
    text = gle_path.read_text(encoding="utf-8")
    # Compare both columnar ``.dat`` sidecars and raw ``.z``/points sidecars
    # (heatmap/contour grids and scattered points) for byte identity.
    data = {
        p.name: p.read_bytes()
        for p in directory.iterdir()
        if p.suffix in (".dat", ".z")
    }
    return text, data


def _round_trip(builder, tmp_path: Path):
    """Return (text1, data1, text2, data2, warnings) for a builder."""
    dir1 = tmp_path / "first"
    dir2 = tmp_path / "second"
    dir1.mkdir()
    dir2.mkdir()

    _gleplot_axes._global_data_file_counter = 0
    text1, data1 = _save(builder(), dir1)

    _gleplot_axes._global_data_file_counter = 0
    recognized = parse_gle_figure(dir1 / "figure.gle")
    text2, data2 = _save(recognized.figure, dir2)

    return text1, data1, text2, data2, recognized.warnings


# -- Golden battery ---------------------------------------------------------


@pytest.mark.parametrize("name", golden.BUILDER_IDS)
def test_golden_battery_fixed_point(name, tmp_path):
    builder = getattr(golden, name)
    text1, data1, text2, data2, _ = _round_trip(builder, tmp_path)

    assert name not in _EXEMPT
    assert data2 == data1, f"{name}: data files differ after round-trip"
    assert text2 == text1, f"{name}: GLE text differs after round-trip"


# -- Project-I/O battery ----------------------------------------------------


@pytest.mark.parametrize(
    "builder", project_battery.BUILDERS, ids=project_battery.BUILDER_IDS
)
def test_project_battery_fixed_point(builder, tmp_path):
    text1, data1, text2, data2, _ = _round_trip(builder, tmp_path)

    assert builder.__name__ not in _EXEMPT
    assert data2 == data1, f"{builder.__name__}: data files differ"
    assert text2 == text1, f"{builder.__name__}: GLE text differs"


# -- Why the G13 auto states cannot reach this battery ----------------------
#
# SPEC 14.5 lets a *reference-backed* grid series defer its ``extent`` and its
# colorbar range to write time. That would be a fixed-point hazard if a
# recognized figure could carry one: the second write would recompute from a
# provider this battery does not have. It cannot -- the recognizer only ever
# reconstructs concrete numbers out of the script it is reading, and it has no
# way to invent a ``table_id``. Asserted here rather than merely reasoned
# about, so the empty exemption set above stays a fact about the code.


def _every_series(figure):
    for ax in figure.axes_list:
        for attr in SERIES_CLASSES:
            for series in getattr(ax, attr, []) or []:
                yield attr, series


@pytest.mark.parametrize("name", golden.BUILDER_IDS)
def test_recognized_figures_carry_no_reference_backed_series(name, tmp_path):
    """Parser output is inline throughout, so no auto state is reachable."""
    builder = getattr(golden, name)
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "figure.gle"
    builder().savefig_gle(str(gle_path))

    _gleplot_axes._global_data_file_counter = 0
    recognized = parse_gle_figure(gle_path).figure

    for attr, series in _every_series(recognized):
        assert is_inline(series), (
            f"{name}: recognized {attr} series carries a reference data_source; "
            "the fixed-point battery would then depend on a data provider"
        )
        if attr in ("heatmaps", "contours"):
            # A concrete extent, never the SPEC 14.5 auto state.
            assert series.get("extent") is not None
            assert len(series["extent"]) == 4
        cb = series.get("colorbar") if attr == "heatmaps" else None
        if cb:
            assert COLORBAR_AUTO_RANGE not in cb
            assert cb["zmin"] is not None and cb["zmax"] is not None
            assert cb["zstep"] is not None

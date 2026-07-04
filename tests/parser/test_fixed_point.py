"""The recognizer fixed-point test: writer -> recognizer -> writer is stable.

For every figure in the golden battery (and the project-I/O battery), saving
to ``.gle``, parsing it back with :func:`parse_gle_figure`, and saving again
must produce byte-identical GLE text AND byte-identical ``.dat`` sidecars.

This is the acceptance bar for Track B1: ``.gle`` is a lossless native save
format for gleplot's own output. A small, explicitly enumerated set of builders
is exempted because they use ``subplots_adjust`` overrides that bake into
non-invertible cm geometry (see the recognizer module docstring, normalization
#3); those are asserted to differ ONLY in the layout geometry and to still
round-trip everything else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot
from gleplot import axes as _gleplot_axes
from gleplot.parser.recognizer import parse_gle_figure

from tests.parser import _golden_battery as golden
from tests.integration import test_project_io as project_battery


# Builders whose GLE text is NOT byte-identical after a round-trip because they
# use subplots_adjust (documented layout loss). Their data files must still
# round-trip byte-identically, and the layout that IS emitted must be valid.
_SUBPLOT_ADJUST_EXEMPT = {
    "subplots_grid_mixed",       # golden battery
    "_subplots_grid",            # project battery (default hspace/wspace)
    "_subplots_sharey_adjust",   # project battery
}


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
    data = {p.name: p.read_bytes() for p in directory.glob("*.dat")}
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

    # Data sidecars are ALWAYS byte-identical (even for the adjust-exempt
    # builders: only page geometry differs, not the data).
    assert data2 == data1, f"{name}: data files differ after round-trip"

    if name in _SUBPLOT_ADJUST_EXEMPT:
        # Documented subplots_adjust loss: the text differs only in the baked
        # amove/size geometry. Everything that is not layout geometry must be
        # unchanged, so strip the geometry lines and compare the rest.
        assert _strip_layout(text1) == _strip_layout(text2), (
            f"{name}: non-layout content changed after round-trip"
        )
    else:
        assert text2 == text1, f"{name}: GLE text differs after round-trip"


# -- Project-I/O battery ----------------------------------------------------

@pytest.mark.parametrize(
    "builder", project_battery.BUILDERS, ids=project_battery.BUILDER_IDS
)
def test_project_battery_fixed_point(builder, tmp_path):
    text1, data1, text2, data2, _ = _round_trip(builder, tmp_path)

    assert data2 == data1, f"{builder.__name__}: data files differ"

    if builder.__name__ in _SUBPLOT_ADJUST_EXEMPT:
        assert _strip_layout(text1) == _strip_layout(text2)
    else:
        assert text2 == text1, f"{builder.__name__}: GLE text differs"


def _strip_layout(text: str) -> str:
    """Drop the layout-geometry lines (``amove``/``size``) for adjust-exempt
    comparison. What remains -- titles, axes, series, keys, data commands --
    must be identical, proving only the subplot geometry was lost."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("amove ") or s.startswith("size "):
            continue
        out.append(line)
    return "\n".join(out)

"""Series vertical-offset (waterfall/overlay) emission and autoscale.

A non-zero ``offset`` on a plot/errorbar/fill series shifts the trace
vertically *at plot time* -- the writer emits ``let dK = dJ+offset`` and
displays ``dK`` -- so the generated ``.dat`` file keeps its raw values. These
tests pin that the offset never reaches the data file, that the ``let`` is
shaped the way GLE requires (operator glued to its operands, ``-`` for a
negative offset), and that autoscale bounds the *shifted* trace so a stack
never falls off the auto-computed axis. The recognizer round-trip lives in
``tests/parser/test_series_offset.py``.
"""

from __future__ import annotations

import pytest

import gleplot as glp


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _script_and_data(fig, tmp_path):
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    script = gle_path.read_text(encoding="utf-8")
    dats = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.glob("*.dat")}
    return script, dats


def _numeric_rows(dat_text: str) -> list[list[float]]:
    """Return the numeric data rows of a .dat file, skipping the column-name
    header row and any ``!`` comment lines."""
    rows = []
    for ln in dat_text.splitlines():
        parts = ln.split()
        if not parts or ln.startswith("!"):
            continue
        try:
            rows.append([float(p) for p in parts])
        except ValueError:
            continue  # header row (column names)
    return rows


def test_offset_stored_on_series_dict():
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 2, 3], offset=5.0)
    ax.errorbar([0, 1], [1, 2], yerr=[0.1, 0.1], offset=-2.5)
    ax.fill_between([0, 1], [0, 0], [1, 1], offset=3.0)
    assert ax.lines[0]["offset"] == 5.0
    assert ax.errorbars[0]["offset"] == -2.5
    assert ax.fills[0]["offset"] == 3.0


def test_default_offset_is_zero_and_emits_no_let(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 2, 3], data_name="plain")
    assert ax.lines[0]["offset"] == 0.0
    script, _ = _script_and_data(fig, tmp_path)
    assert "let " not in script


def test_line_offset_emits_let_and_keeps_data_raw(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0, 2.0], [1.0, 2.0, 3.0], offset=5.0, data_name="wave")
    script, dats = _script_and_data(fig, tmp_path)

    # A 'let dK = dJ+5' shifts a fresh dataset; the display command references
    # the shifted dataset, not the raw one.
    assert "let " in script
    assert "+5" in script.replace(" ", "")
    # The .dat file holds the RAW y values (1, 2, 3), never 6, 7, 8.
    ys = [row[1] for row in _numeric_rows(dats["wave.dat"])]
    assert ys == [1.0, 2.0, 3.0]


def test_negative_offset_emits_minus(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [1, 2], offset=-2.0, data_name="neg")
    script, _ = _script_and_data(fig, tmp_path)
    glued = script.replace(" ", "")
    assert "-2" in glued
    # Never the ill-formed 'd?+-2' that GLE rejects.
    assert "+-2" not in glued


def test_errorbar_offset_keeps_error_dataset_on_raw_column(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.errorbar(
        [0, 1, 2], [1, 2, 3], yerr=[0.1, 0.1, 0.1],
        fmt="none", marker="o", offset=5.0, data_name="eb",
    )
    script, dats = _script_and_data(fig, tmp_path)
    # Error magnitudes ride along with the shifted centre: the 'err dN' clause
    # references a dataset bound to the raw error column, so the .dat error
    # column is untouched.
    errs = [row[2] for row in _numeric_rows(dats["eb.dat"])]
    assert errs == [0.1, 0.1, 0.1]
    assert " err d" in script


def test_fill_offset_shifts_both_edges(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.fill_between([0, 1, 2], [0, 0, 0], [1, 1, 1], offset=4.0, data_name="band")
    script, dats = _script_and_data(fig, tmp_path)
    # Two 'let' datasets (one per band edge), both shifted by +4.
    assert script.replace(" ", "").count("+4") == 2
    rows = _numeric_rows(dats["band.dat"])
    # Raw edges are still 0 and 1, not 4 and 5.
    assert [r[1] for r in rows] == [0.0, 0.0, 0.0]
    assert [r[2] for r in rows] == [1.0, 1.0, 1.0]


def test_autoscale_bounds_the_shifted_trace(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0.0, 1.0, 2.0], offset=10.0, data_name="hi")
    script, _ = _script_and_data(fig, tmp_path)
    # The autoscaled y-max must clear the shifted top (12), not the raw top (2).
    ymax_line = next(ln for ln in script.splitlines() if "yaxis" in ln and "max" in ln)
    ymax = float(ymax_line.split("max")[1].split()[0])
    assert ymax >= 12.0

"""Recognizer round-trip for series vertical offsets (waterfall/overlay).

The writer emits a non-zero offset as ``let dK = dJ+offset`` and displays the
shifted dataset ``dK`` (see ``tests/unit/test_offset.py``). The recognizer must
map ``dK`` back to ``dJ``'s data file/columns and recover the offset as an
editable series property, so an offset figure survives Open -> edit -> Save
without losing the trace (the pre-feature behaviour: the ``let`` line was
unrecognized and the series vanished).
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot import axes as _gleplot_axes
from gleplot.parser.recognizer import parse_gle_figure


@pytest.fixture(autouse=True)
def _fresh():
    _gleplot_axes._global_data_file_counter = 0
    glp.close()
    yield
    _gleplot_axes._global_data_file_counter = 0
    glp.close()


def _save(fig, tmp_path, name="f.gle"):
    p = tmp_path / name
    fig.savefig_gle(str(p))
    return p


def _only(seq):
    assert len(seq) == 1, f"expected exactly one, got {len(seq)}"
    return seq[0]


def test_line_offset_round_trips(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0.0, 1.0, 2.0], [1.0, 2.0, 3.0], offset=5.0, data_name="wave")
    gle = _save(fig, tmp_path)

    rec = parse_gle_figure(gle)
    assert rec.warnings == []
    line = _only(rec.figure.axes_list[0].lines)
    assert line["offset"] == 5.0
    # Recovered y is the RAW column, not the shifted display values.
    np.testing.assert_allclose(line["y"], [1.0, 2.0, 3.0])


def test_errorbar_offset_round_trips_with_raw_errors(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.errorbar(
        [0.0, 1.0, 2.0], [1.0, 2.0, 3.0], yerr=[0.1, 0.2, 0.3],
        fmt="none", marker="o", offset=-4.0, data_name="eb",
    )
    gle = _save(fig, tmp_path)

    rec = parse_gle_figure(gle)
    assert rec.warnings == []
    eb = _only(rec.figure.axes_list[0].errorbars)
    assert eb["offset"] == -4.0
    np.testing.assert_allclose(eb["y"], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(eb["yerr_up"], [0.1, 0.2, 0.3])


def test_fill_offset_round_trips(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.fill_between([0.0, 1.0], [0.0, 0.0], [1.0, 1.0], offset=3.0, data_name="band")
    gle = _save(fig, tmp_path)

    rec = parse_gle_figure(gle)
    assert rec.warnings == []
    fill = _only(rec.figure.axes_list[0].fills)
    assert fill["offset"] == 3.0
    np.testing.assert_allclose(fill["y1"], [0.0, 0.0])
    np.testing.assert_allclose(fill["y2"], [1.0, 1.0])


def test_zero_offset_absent_let_recovers_zero(tmp_path):
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 2, 3], data_name="plain")
    gle = _save(fig, tmp_path)
    assert "let " not in gle.read_text(encoding="utf-8")

    rec = parse_gle_figure(gle)
    assert _only(rec.figure.axes_list[0].lines)["offset"] == 0.0


def test_offset_is_idempotent_on_resave(tmp_path):
    """Open -> Save must preserve the offset and the raw data."""
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    ax.errorbar([0.0, 1.0, 2.0], [1.0, 2.0, 3.0], yerr=[0.1, 0.1, 0.1],
                fmt="none", marker="o", offset=7.0, data_name="eb")
    first = _save(fig, tmp_path, "first.gle")

    rec = parse_gle_figure(first)
    second = tmp_path / "second.gle"
    rec.figure.savefig_gle(str(second))

    rec2 = parse_gle_figure(second)
    eb = _only(rec2.figure.axes_list[0].errorbars)
    assert eb["offset"] == 7.0
    np.testing.assert_allclose(eb["y"], [1.0, 2.0, 3.0])
    # Every emitted script must define the shifted dataset via a 'let'.
    assert "let " in second.read_text(encoding="utf-8")


def test_unrecognized_let_preserved_as_raw_gle(tmp_path):
    """A general 'let' (not the offset shape) is kept verbatim, not dropped."""
    src = (
        "size 20 15\n"
        "begin graph\n"
        "   data wave.dat d1=c1,c2\n"
        "   let d2 = 3*x^2\n"
        "   d1 line color black\n"
        "end graph\n"
    )
    (tmp_path / "wave.dat").write_text("0 1\n1 2\n2 3\n", encoding="utf-8")
    p = tmp_path / "g.gle"
    p.write_text(src, encoding="utf-8")

    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # The offset-shape recognizer must not have claimed this let; it survives
    # as passthrough so a re-save does not silently delete it.
    assert any("let d2 = 3*x^2" in line for line in ax.passthrough)

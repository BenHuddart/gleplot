"""G19: what the recognizer does with GLE's fifteen ``bar`` sub-commands.

Before G19 ``_parse_bar_command`` looked for exactly two things -- the
dataset name(s) and ``fill`` -- and silently discarded everything else. A
hand-written ``bar d1 horiz`` came back as a vertical bar chart with no
warning; a hand-written ``bar d1 width 0.3`` on a single point came back with
G16's *derived* ``width 0.5``, quietly overwriting the author's number with
gleplot's. Both are "no silent drops" violations (GLEstudio SPEC 8.1.4).

G19's answer is the split the plan approved:

* ``width`` becomes a real ``BarSeries`` field, so it round-trips as itself;
* every other unmodelled sub-command degrades the WHOLE ``bar`` command to
  raw passthrough with a categorized note -- the 557aa42 stacked-bar
  precedent, keep both sides raw rather than model half and drop half.

The degrade list is read off GLE 4.3.10's own parser (``do_bar`` in
``graph.cpp``), not off the manual, so it is the grammar and not the five
options anyone happened to think of.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot as glp
from gleplot.parser.recognizer import (
    _BAR_UNMODELLED_OPTIONS,
    ImportCategory,
    parse_gle_figure,
)

_TWO_DAT = "1 5\n2 3\n"
_ONE_DAT = "1 5\n"


def _write(tmp_path, name, body, dats):
    for dat_name, dat_content in dats.items():
        (tmp_path / dat_name).write_text(dat_content, encoding="utf-8")
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _script(bar_line, dat="two.dat"):
    return (
        "size 8 6\n"
        "begin graph\n"
        f'   data "{dat}" d1=c1,c2\n'
        f"   {bar_line}\n"
        "end graph\n"
    )


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


# --------------------------------------------------------------------------- #
# ``width`` -- the field
# --------------------------------------------------------------------------- #


def test_a_hand_written_width_lands_in_the_model(tmp_path):
    p = _write(
        tmp_path, "w.gle", _script("bar d1 fill red width 0.3"), {"two.dat": _TWO_DAT}
    )
    rec = parse_gle_figure(p)

    (bar,) = rec.figure.axes_list[0].bars
    assert bar["width"] == 0.3
    assert rec.warnings == []


def test_a_bar_with_no_width_carries_no_width_key(tmp_path):
    """G16's derivation depends on the key staying absent."""
    p = _write(tmp_path, "n.gle", _script("bar d1 fill red"), {"two.dat": _TWO_DAT})
    (bar,) = parse_gle_figure(p).figure.axes_list[0].bars
    assert "width" not in bar


def test_the_width_may_come_before_the_fill(tmp_path):
    p = _write(
        tmp_path, "o.gle", _script("bar d1 width 0.3 fill red"), {"two.dat": _TWO_DAT}
    )
    (bar,) = parse_gle_figure(p).figure.axes_list[0].bars
    assert bar["width"] == 0.3
    assert bar["colors"] == ["red", "red"]


def test_a_width_expression_is_evaluated(tmp_path):
    """GLE takes ``next_exp`` here, and so does the recognizer."""
    p = _write(
        tmp_path, "e.gle", _script("bar d1 fill red width 3/4"), {"two.dat": _TWO_DAT}
    )
    (bar,) = parse_gle_figure(p).figure.axes_list[0].bars
    assert bar["width"] == 0.75


def test_the_g16_wrinkle_a_single_point_width_is_the_authors_number(
    tmp_path, monkeypatch
):
    """The regression G19 was ledgered for.

    ``bar d1 width 0.3`` over a one-row data file used to round-trip to
    ``width 0.5`` -- G16's derived nominal -- because the model had nowhere
    to put 0.3. Now it round-trips as itself, and the range gleplot supplies
    for the unmeasurable dataset is half-spanned by that same 0.3.
    """
    monkeypatch.chdir(tmp_path)
    p = _write(
        tmp_path,
        "one.gle",
        _script("bar d1 fill red width 0.3", dat="one.dat"),
        {"one.dat": _ONE_DAT},
    )
    rec = parse_gle_figure(p)
    (bar,) = rec.figure.axes_list[0].bars
    assert bar["width"] == 0.3

    rec.figure.savefig_gle("out.gle")
    text = Path("out.gle").read_text(encoding="utf-8")
    assert "    bar d1 fill red width 0.3" in text
    assert "width 0.5" not in text
    assert "    xaxis min 0.7 max 1.3" in text

    # ... and re-emitting what we just parsed changes nothing.
    glp.open_gle("out.gle").savefig_gle("again.gle")
    assert Path("again.gle").read_text(encoding="utf-8") == text


# --------------------------------------------------------------------------- #
# Everything else -- degrade the whole command to raw
# --------------------------------------------------------------------------- #


def test_the_degrade_list_is_gles_whole_bar_grammar():
    """``do_bar``'s ``kw(...)`` chain, minus the two gleplot models.

    Anything outside this set is "unrecognised bar sub command" to GLE
    itself, so the enumeration cannot be short of the grammar.
    """
    grammar = {
        "dist",
        "width",
        "3d",
        "notop",
        "horiz",
        "lstyle",
        "style",
        "lwidth",
        "from",
        "color",
        "side",
        "top",
        "fill",
        "pattern",
        "background",
    }
    modelled = {"fill", "width"}
    assert set(_BAR_UNMODELLED_OPTIONS) == grammar - modelled


@pytest.mark.parametrize(
    "option",
    [
        "dist 0.1",
        "3d 0.2 0.2",
        "notop",
        "horiz",
        "lstyle 12",
        "style ...",
        "lwidth 0.02",
        "color blue",
        "side green",
        "top black",
        "pattern grid5",
        "background white",
    ],
)
def test_an_unmodelled_option_keeps_the_whole_command_raw(tmp_path, option):
    """Whole command, whole note, and the ``data`` line restored verbatim.

    Nothing is modelled: a half-modelled ``horiz`` chart would come back
    vertical, a half-modelled ``3d`` one flat. And because the dataset ends
    up entirely unconsumed, the existing reconciliation restores its
    ``data`` statement byte-for-byte, so GLE reads the author's own file.
    """
    bar_line = f"bar d1 fill red {option}"
    p = _write(tmp_path, "u.gle", _script(bar_line), {"two.dat": _TWO_DAT})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]

    assert ax.bars == []
    assert f"   {bar_line}" in ax.passthrough
    assert '   data "two.dat" d1=c1,c2' in ax.passthrough

    keyword = option.split()[0]
    (note,) = rec.notes
    assert note.category is ImportCategory.STRUCTURE
    assert keyword in note.message
    assert "raw GLE" in note.message


def test_several_unmodelled_options_are_named_together(tmp_path):
    p = _write(
        tmp_path,
        "m.gle",
        _script("bar d1 fill red horiz dist 0.1"),
        {"two.dat": _TWO_DAT},
    )
    rec = parse_gle_figure(p)
    (note,) = rec.notes
    assert "horiz" in note.message and "dist" in note.message


def test_a_width_gleplot_cannot_evaluate_degrades_rather_than_vanishing(tmp_path):
    """``width bw`` is a GLE expression with no number behind it here."""
    p = _write(
        tmp_path, "v.gle", _script("bar d1 fill red width bw"), {"two.dat": _TWO_DAT}
    )
    rec = parse_gle_figure(p)

    assert rec.figure.axes_list[0].bars == []
    assert "   bar d1 fill red width bw" in rec.figure.axes_list[0].passthrough
    (note,) = rec.notes
    assert note.category is ImportCategory.STRUCTURE
    assert "width" in note.message


def test_a_width_on_an_unresolved_dataset_degrades_too(tmp_path):
    """``FileSeries`` has no width, so the reference form would drop it."""
    p = tmp_path / "x.gle"
    p.write_text(
        _script("bar d1 fill red width 0.3", dat="missing.dat"), encoding="utf-8"
    )
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]

    assert ax.bars == [] and ax.file_series == []
    assert "   bar d1 fill red width 0.3" in ax.passthrough
    assert any("width" in n.message for n in rec.notes)


def test_a_stacked_bar_keeps_its_own_older_note(tmp_path):
    """``from`` reaches the multi-dataset branch first (557aa42); unchanged."""
    p = _write(
        tmp_path,
        "s.gle",
        "size 8 6\n"
        "begin graph\n"
        '   data "two.dat" d1=c1,c2\n'
        '   data "two.dat" d2=c1,c2\n'
        "   bar d2 from d1 fill white\n"
        "end graph\n",
        {"two.dat": _TWO_DAT},
    )
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].bars == []
    assert any("multi-dataset bar group" in n.message for n in rec.notes)


def test_a_degraded_bar_is_a_parse_emit_parse_fixed_point(tmp_path, monkeypatch):
    """Raw means raw: the command and its data line come back out untouched."""
    monkeypatch.chdir(tmp_path)
    bar_line = "bar d1 fill red horiz dist 0.1"
    _write(tmp_path, "h.gle", _script(bar_line), {"two.dat": _TWO_DAT})

    glp.open_gle("h.gle").savefig_gle("first.gle")
    first = Path("first.gle").read_text(encoding="utf-8")
    # Verbatim -- the author's own indentation included.
    assert f"   {bar_line}\n" in first
    assert '   data "two.dat" d1=c1,c2\n' in first

    glp.open_gle("first.gle").savefig_gle("second.gle")
    assert Path("second.gle").read_text(encoding="utf-8") == first

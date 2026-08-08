"""Per-series smoothing: the ``smooth_mode`` / ``svg_smooth`` fields (G12).

GLE offers two independent smoothing options on a dataset display command
(``graph.tex``: ``dn smooth | smoothm`` and ``dn svg_smooth [m]``), and
gleplot used to model neither per series -- only one figure-wide
``GLEGraphConfig.smooth_curves`` boolean, which could not express "this curve
is smoothed and that one is not", could not express ``smoothm`` at all, and
dropped ``svg_smooth`` on the floor. GLEstudio SPEC 14.7 closes that gap.

What these tests pin:

* **the model** -- two fields, on ``LineSeries`` only, with an absent field
  meaning "defer to the figure-wide default" and ``'none'`` meaning "do not
  smooth this one" (two states a boolean cannot hold apart);
* **the emission** -- the exact token order ``line svg_smooth m mode``, which
  is not cosmetic: GLE's own keyword loop clears ``smooth``/``smoothm`` when
  it sees ``svg_smooth``, so the other order silently drops the mode;
* **point order** -- ``smooth`` sorts rows by x (it is a fit *of a function of
  x*), ``smoothm`` and ``svg_smooth`` must not (that is what ``smoothm`` is
  for);
* **the round trip** -- hand-written fixtures for each clause and for the
  combination parse into the model fields and re-emit byte-identically.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import find_gle
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.parser.report import ImportCategory
from gleplot.series import (
    SMOOTH_MODES,
    LineSeries,
    normalize_smooth_mode,
    normalize_svg_smooth,
    smooth_mode,
    svg_smooth_iterations,
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


X = np.linspace(0.0, 1.0, 9)
Y = np.array([0.0, 1.0, 0.05, 0.95, 0.1, 0.9, 0.15, 0.85, 0.2])


def _script(fig) -> str:
    text, _files = fig._generate_gle_with_files()
    return str(text)


def _dataset_commands(script: str) -> list[str]:
    return [ln.strip() for ln in script.splitlines() if re.match(r"\s+d\d+\s+\S", ln)]


def _one_line_figure(graph=None, **fields):
    fig = glp.figure(data_prefix="t", graph=graph)
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red")
    ax.lines[0].update(fields)
    return fig


# --------------------------------------------------------------------------- #
# the model
# --------------------------------------------------------------------------- #


def test_the_mode_is_three_valued_not_a_boolean():
    """``smoothm`` is a mode of its own, not a flavour of ``smooth``."""
    assert SMOOTH_MODES == ("none", "smooth", "smoothm")


def test_the_fields_are_absent_by_default():
    """Absent means "defer"; the scope guard lives in test_serialization.py."""
    assert "smooth_mode" not in LineSeries()
    assert "svg_smooth" not in LineSeries()


def test_absent_and_none_are_different_states():
    """Absent defers to the figure default; ``'none'`` overrides it."""
    assert smooth_mode({}) is None
    assert smooth_mode({"smooth_mode": "none"}) == "none"


@pytest.mark.parametrize("value", ["smooth", "SMOOTH", " smoothm ", "none"])
def test_mode_reader_normalizes_case_and_whitespace(value):
    assert normalize_smooth_mode(value) == value.strip().lower()


@pytest.mark.parametrize("value", ["spline", "", True, 3, "smooth_curves"])
def test_an_unrecognized_mode_defers_rather_than_guessing(value):
    """Never *invent* an interpolation from a value we do not understand."""
    assert normalize_smooth_mode(value) is None


@pytest.mark.parametrize(
    "value,expected", [(1, 1), (3, 3), ("4", 4), (2.0, 2), (0, None), (-1, None)]
)
def test_svg_iterations_normalize_to_an_int_at_least_one(value, expected):
    assert normalize_svg_smooth(value) == expected


@pytest.mark.parametrize("value", [None, True, False, "many", object()])
def test_a_malformed_iteration_count_reads_as_off(value):
    assert normalize_svg_smooth(value) is None
    assert svg_smooth_iterations({"svg_smooth": value}) is None


def test_the_two_fields_are_independent():
    series = {"smooth_mode": "smoothm", "svg_smooth": 2}
    assert smooth_mode(series) == "smoothm"
    assert svg_smooth_iterations(series) == 2


# --------------------------------------------------------------------------- #
# emission
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", ["smooth", "smoothm"])
def test_a_per_series_mode_emits_its_own_token(mode):
    cmd = _dataset_commands(_script(_one_line_figure(smooth_mode=mode)))[0]
    assert re.search(rf"\bline {mode} color RED\b", cmd), cmd


def test_svg_smooth_emits_its_iteration_count():
    cmd = _dataset_commands(_script(_one_line_figure(svg_smooth=3)))[0]
    assert re.search(r"\bline svg_smooth 3 color RED\b", cmd), cmd


def test_both_clauses_appear_on_one_line_with_svg_smooth_first():
    """The order is load-bearing, not cosmetic -- see the module docstring."""
    cmd = _dataset_commands(
        _script(_one_line_figure(smooth_mode="smooth", svg_smooth=2))
    )[0]
    assert re.search(r"\bline svg_smooth 2 smooth color RED\b", cmd), cmd


def test_the_combination_never_emits_the_order_gle_would_cancel():
    """``smooth`` before ``svg_smooth`` is the order GLE throws the mode away in."""
    script = _script(_one_line_figure(smooth_mode="smoothm", svg_smooth=2))
    assert "smoothm svg_smooth" not in script
    assert "svg_smooth 2 smoothm" in script


def test_a_series_mode_beats_the_figure_wide_default():
    graph = glp.GLEGraphConfig(smooth_curves=True)
    cmd = _dataset_commands(_script(_one_line_figure(graph, smooth_mode="none")))[0]
    assert " line color RED" in cmd, cmd
    assert "smooth" not in cmd


def test_an_absent_mode_still_defers_to_the_figure_wide_default():
    graph = glp.GLEGraphConfig(smooth_curves=True)
    cmd = _dataset_commands(_script(_one_line_figure(graph)))[0]
    assert " line smooth color RED" in cmd, cmd


def test_svg_smooth_composes_with_the_figure_wide_default():
    """The mode field is absent, so the figure default supplies the mode."""
    graph = glp.GLEGraphConfig(smooth_curves=True)
    cmd = _dataset_commands(_script(_one_line_figure(graph, svg_smooth=2)))[0]
    assert " line svg_smooth 2 smooth color RED" in cmd, cmd


def test_a_hidden_smoothed_series_emits_nothing_at_all():
    """G11 and G12 compose: hidden wins, whatever the curve would look like."""
    script = _script(_one_line_figure(smooth_mode="smoothm", visible=False))
    assert not _dataset_commands(script)
    assert "smooth" not in script


def test_smoothing_never_reaches_a_series_that_draws_no_line():
    """No line, no curve to smooth -- and GLE's keyword would switch one on."""
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red", marker="o")
    # A *line* series whose line is off: the field is legal but has nothing
    # to qualify, and emitting it would draw the line the caller turned off.
    ax.lines[0]["linestyle"] = "none"
    ax.lines[0]["smooth_mode"] = "smooth"
    script = _script(fig)
    assert "smooth" not in script


def test_scatters_and_fills_are_untouched_by_a_neighbours_smoothing():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot(X, Y, color="red")
    ax.scatter(X, Y + 1, color="blue")
    ax.fill_between(X, Y - 0.1, Y + 0.1, color="grey10")
    ax.lines[0]["smooth_mode"] = "smoothm"
    cmds = _dataset_commands(_script(fig))
    smoothed = [c for c in cmds if "smooth" in c]
    assert len(smoothed) == 1 and "smoothm" in smoothed[0]


def test_the_default_emission_is_byte_identical_to_before_the_fields_existed():
    """A figure that sets neither field must not move a single character."""
    plain = _script(_one_line_figure())
    explicit_default = _script(_one_line_figure(smooth_mode="none"))
    assert plain == explicit_default


# --------------------------------------------------------------------------- #
# point order
# --------------------------------------------------------------------------- #

#: Deliberately non-monotonic in x: a loop that is not a function of x.
LOOP_X = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
LOOP_Y = np.array([0.0, 1.0, 0.0, -1.0, 0.0])


def _written_rows(fig, tmp_path: Path) -> list[str]:
    fig.savefig_gle(str(tmp_path / "f.gle"))
    dat = next(p for p in tmp_path.iterdir() if p.suffix == ".dat")
    return dat.read_text(encoding="utf-8").splitlines()[1:]


def _loop_figure(**fields):
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot(LOOP_X, LOOP_Y, color="red")
    ax.lines[0].update(fields)
    return fig


def test_smooth_sorts_rows_by_x(tmp_path):
    """GLE's ``smooth`` fits a function of x and needs ascending x."""
    xs = [
        float(r.split()[0])
        for r in _written_rows(_loop_figure(smooth_mode="smooth"), tmp_path)
    ]
    assert xs == sorted(xs)


def test_smoothm_keeps_the_callers_point_order(tmp_path):
    """Sorting a multi-valued curve is exactly what ``smoothm`` exists to avoid."""
    xs = [
        float(r.split()[0])
        for r in _written_rows(_loop_figure(smooth_mode="smoothm"), tmp_path)
    ]
    assert xs == list(LOOP_X)


def test_svg_smooth_keeps_the_callers_point_order(tmp_path):
    """A moving-window filter over reordered rows is a different filter."""
    xs = [
        float(r.split()[0]) for r in _written_rows(_loop_figure(svg_smooth=2), tmp_path)
    ]
    assert xs == list(LOOP_X)


def test_a_series_none_mode_defeats_the_figure_wide_sort(tmp_path):
    fig = glp.figure(data_prefix="t", graph=glp.GLEGraphConfig(smooth_curves=True))
    ax = fig.add_subplot(111)
    ax.plot(LOOP_X, LOOP_Y, color="red")
    ax.lines[0]["smooth_mode"] = "none"
    xs = [float(r.split()[0]) for r in _written_rows(fig, tmp_path)]
    assert xs == list(LOOP_X)


# --------------------------------------------------------------------------- #
# serialization
# --------------------------------------------------------------------------- #


def test_the_fields_round_trip_through_to_dict():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot(X, Y)
    ax.plot(X, Y + 1)
    ax.lines[0]["smooth_mode"] = "smoothm"
    ax.lines[0]["svg_smooth"] = 4
    ax.lines[1]["smooth_mode"] = "none"

    once = fig.to_dict()
    restored = glp.Figure.from_dict(once)
    assert restored.to_dict() == once
    assert restored.axes_list[0].lines[0]["smooth_mode"] == "smoothm"
    assert restored.axes_list[0].lines[0]["svg_smooth"] == 4
    assert restored.axes_list[0].lines[1]["smooth_mode"] == "none"
    assert "smooth_mode" not in restored.axes_list[0].lines[0].get("nonexistent", {})


def test_a_reference_backed_series_carries_its_smoothing_through_resolution():
    """The fields must survive the write-time source resolution copy."""
    from gleplot.sources import ColumnRef, DictDataProvider, TableData

    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([], [], color="red")
    line = ax.lines[0]
    line["data_source"] = ColumnRef("t1", {"x": "a", "y": "b"})
    line["smooth_mode"] = "smoothm"
    line["svg_smooth"] = 2
    provider = DictDataProvider(
        {"t1": TableData.from_mapping({"a": [0.0, 1.0], "b": [0.0, 1.0]})}
    )
    text, _files = fig._generate_gle_with_files(data_provider=provider)
    assert "svg_smooth 2 smoothm" in text


# --------------------------------------------------------------------------- #
# round trip: hand-written fixtures
# --------------------------------------------------------------------------- #

#: A hand-written script in the writer's canonical form, carrying one dataset
#: per clause: the mode alone (``smooth``), its multi-valued variant
#: (``smoothm``) and the Savitzky-Golay filter alone (``svg_smooth 3``).
CLAUSE_FIXTURE = """! GLE graphics file
! Generated by gleplot
! gleplot-meta-begin v2
! gleplot: dpi = 100
! gleplot: import-data = sm_0.dat, sm_1.dat, sm_2.dat
! gleplot-meta-end

size 20.32 15.24
set hei 0.42328

amove 1.69312 1.26984
begin graph
    size 17.992 13.3352
    scale 1 1
    xaxis min 0 max 3
    yaxis min 0 max 9
    data sm_0.dat d1=c1,c2
    d1 line smooth color RED lwidth 0.05292 key "a"
    data sm_1.dat d2=c1,c2
    d2 line smoothm color BLUE lwidth 0.05292 key "b"
    data sm_2.dat d3=c1,c2
    d3 line svg_smooth 3 color GREEN lwidth 0.05292 key "c"
    key pos tr
end graph"""

#: The same, with both clauses on one ``dN`` line -- the combination GLE
#: accepts only in this order.
COMBINATION_FIXTURE = """! GLE graphics file
! Generated by gleplot
! gleplot-meta-begin v2
! gleplot: dpi = 100
! gleplot: import-data = sm_0.dat, sm_1.dat, sm_2.dat
! gleplot-meta-end

size 20.32 15.24
set hei 0.42328

amove 1.69312 1.26984
begin graph
    size 17.992 13.3352
    scale 1 1
    xaxis min 0 max 3
    yaxis min 0 max 9
    data sm_0.dat d1=c1,c2
    d1 line svg_smooth 2 smooth color RED lwidth 0.05292 key "a"
    data sm_1.dat d2=c1,c2
    d2 line svg_smooth 5 smoothm color BLUE lwidth 0.05292 key "b"
    data sm_2.dat d3=c1,c2
    d3 line color GREEN lwidth 0.05292 key "c"
    key pos tr
end graph"""


def _write_fixture(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "f.gle"
    path.write_text(source, encoding="utf-8")
    for index, name in enumerate("abc"):
        (tmp_path / f"sm_{index}.dat").write_text(
            f"x {name}\n0 1\n1 4\n2 7\n3 9\n", encoding="utf-8"
        )
    return path


def _resave(recovered, tmp_path: Path) -> str:
    out = tmp_path / "again"
    out.mkdir()
    for dat in tmp_path.glob("sm_*.dat"):
        shutil.copy(dat, out / dat.name)
    recovered.savefig_gle(str(out / "f.gle"))
    return (out / "f.gle").read_text(encoding="utf-8")


def test_each_clause_parses_into_its_model_fields(tmp_path):
    rec = parse_gle_figure(_write_fixture(tmp_path, CLAUSE_FIXTURE))
    d1, d2, d3 = rec.figure.axes_list[0].lines
    # The figure-wide default is inferred as smooth (two of the three
    # datasets carry GLE's smooth flag), so d1 defers to it and the two that
    # differ carry an explicit field -- the "absent means the default" rule.
    assert rec.figure.graph.smooth_curves is True
    assert smooth_mode(d1) is None and svg_smooth_iterations(d1) is None
    assert smooth_mode(d2) == "smoothm" and svg_smooth_iterations(d2) is None
    assert smooth_mode(d3) == "none" and svg_smooth_iterations(d3) == 3


def test_each_clause_re_emits_byte_identically(tmp_path):
    rec = parse_gle_figure(_write_fixture(tmp_path, CLAUSE_FIXTURE))
    assert _resave(rec.figure, tmp_path) == CLAUSE_FIXTURE


def test_the_combination_clause_parses_into_both_fields(tmp_path):
    rec = parse_gle_figure(_write_fixture(tmp_path, COMBINATION_FIXTURE))
    d1, d2, d3 = rec.figure.axes_list[0].lines
    assert smooth_mode(d1) is None and svg_smooth_iterations(d1) == 2
    assert smooth_mode(d2) == "smoothm" and svg_smooth_iterations(d2) == 5
    assert smooth_mode(d3) == "none" and svg_smooth_iterations(d3) is None


def test_the_combination_clause_re_emits_byte_identically(tmp_path):
    rec = parse_gle_figure(_write_fixture(tmp_path, COMBINATION_FIXTURE))
    assert _resave(rec.figure, tmp_path) == COMBINATION_FIXTURE


def test_a_bare_svg_smooth_dataset_is_recovered_as_a_line(tmp_path):
    """GLE's ``svg_smooth`` sets the line flag; ``d3 svg_smooth 3`` draws one."""
    source = CLAUSE_FIXTURE.replace(
        "d3 line svg_smooth 3 color GREEN", "d3 svg_smooth 3 color GREEN"
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    assert not rec.figure.axes_list[0].scatters
    d3 = rec.figure.axes_list[0].lines[2]
    assert svg_smooth_iterations(d3) == 3
    # Canonicalized: the implied ``line`` keyword is written out.
    assert "d3 line svg_smooth 3" in _resave(rec.figure, tmp_path)


def test_svg_smooth_cancels_an_earlier_mode_exactly_as_gle_does(tmp_path):
    """``d1 smooth svg_smooth 2`` is ``d1 svg_smooth 2``; the mode is dead."""
    source = CLAUSE_FIXTURE.replace(
        "d1 line smooth color RED", "d1 line smooth svg_smooth 2 color RED"
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    d1 = rec.figure.axes_list[0].lines[0]
    assert svg_smooth_iterations(d1) == 2
    assert smooth_mode(d1) == "none"
    # The inert token is dropped on re-save (documented normalization #7).
    assert "d1 line svg_smooth 2 color RED" in _resave(rec.figure, tmp_path)


def test_zero_iterations_recover_as_one_like_gle(tmp_path):
    """graph2.cpp: "if they say svg_smooth they want it at least once"."""
    source = CLAUSE_FIXTURE.replace("svg_smooth 3", "svg_smooth 0")
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    assert svg_smooth_iterations(rec.figure.axes_list[0].lines[2]) == 1


def test_a_uniformly_smoothed_file_recovers_without_per_series_fields(tmp_path):
    """The pre-G12 shape is preserved: no new keys where none are needed."""
    source = CLAUSE_FIXTURE.replace("d2 line smoothm", "d2 line smooth").replace(
        "d3 line svg_smooth 3", "d3 line smooth"
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    assert rec.figure.graph.smooth_curves is True
    for line in rec.figure.axes_list[0].lines:
        assert "smooth_mode" not in line
        assert "svg_smooth" not in line
    assert not [n for n in rec.notes if n.category is ImportCategory.SMOOTH]


def test_mixed_smoothing_round_trips_and_says_what_it_changed(tmp_path):
    """The mixed note is about the figure-wide default, not about the lines."""
    rec = parse_gle_figure(_write_fixture(tmp_path, CLAUSE_FIXTURE))
    notes = [n for n in rec.notes if n.category is ImportCategory.SMOOTH]
    assert len(notes) == 1
    assert notes[0].source_span is None
    assert "figure-wide default" in notes[0].message


def test_unmodelled_smoothing_on_an_errorbar_warns_instead_of_vanishing(tmp_path):
    """SPEC 14.7 scopes the fields to line series; the rest must not go quiet."""
    source = CLAUSE_FIXTURE.replace(
        '    d3 line svg_smooth 3 color GREEN lwidth 0.05292 key "c"\n',
        "    data sm_2.dat d4=c1,c2\n"
        '    d3 line svg_smooth 3 err d4 color GREEN lwidth 0.05292 key "c"\n',
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    notes = [n for n in rec.notes if n.category is ImportCategory.SMOOTH]
    unmodelled = [n for n in notes if "error-bar" in n.message]
    assert len(unmodelled) == 1
    assert unmodelled[0].source_span is not None
    assert "svg_smooth 3" in unmodelled[0].message


def test_an_errorbar_that_would_gain_smoothing_is_reported_too(tmp_path):
    """The gap cuts both ways: an unsmoothed errorbar in a smoothed figure.

    Nothing in the file says "do not smooth this one" that the model can
    hold, so re-saving would quietly smooth it. That is a change to the
    picture and has to be said out loud (SPEC 8.1.4), not just the reverse
    case where a clause is lost.
    """
    source = CLAUSE_FIXTURE.replace("d2 line smoothm", "d2 line smooth").replace(
        '    d3 line svg_smooth 3 color GREEN lwidth 0.05292 key "c"\n',
        "    data sm_2.dat d4=c1,c2\n"
        '    d3 line smooth key "c"\n'
        "    data sm_2.dat d5=c1,c2\n"
        '    d5 line err d4 color GREEN lwidth 0.05292 key "e"\n',
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    notes = [n for n in rec.notes if n.category is ImportCategory.SMOOTH]
    gained = [n for n in notes if "no smoothing" in n.message]
    assert len(gained) == 1
    assert "error-bar" in gained[0].message
    assert "'smooth'" in gained[0].message


def test_a_marker_only_dataset_is_never_reported(tmp_path):
    """No line, no smooth qualifier -- the default cannot touch it."""
    source = CLAUSE_FIXTURE.replace("d2 line smoothm", "d2 line smooth").replace(
        '    d3 line svg_smooth 3 color GREEN lwidth 0.05292 key "c"\n',
        "    data sm_2.dat d4=c1,c2\n"
        '    d3 line smooth key "c"\n'
        "    data sm_2.dat d5=c1,c2\n"
        '    d5 marker circle err d4 color GREEN key "e"\n',
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    assert not [n for n in rec.notes if n.category is ImportCategory.SMOOTH]


def test_a_smoothed_errorbar_matching_the_default_is_not_reported(tmp_path):
    """A clause the figure-wide default reproduces exactly loses nothing."""
    source = CLAUSE_FIXTURE.replace("d2 line smoothm", "d2 line smooth").replace(
        '    d3 line svg_smooth 3 color GREEN lwidth 0.05292 key "c"\n',
        "    data sm_2.dat d4=c1,c2\n"
        '    d3 line smooth err d4 color GREEN lwidth 0.05292 key "c"\n',
    )
    rec = parse_gle_figure(_write_fixture(tmp_path, source))
    assert not [n for n in rec.notes if n.category is ImportCategory.SMOOTH]


# --------------------------------------------------------------------------- #
# the engine actually accepts what we emit
# --------------------------------------------------------------------------- #


@pytest.mark.gle
@pytest.mark.parametrize(
    "fields",
    [
        {"smooth_mode": "smooth"},
        {"smooth_mode": "smoothm"},
        {"svg_smooth": 3},
        {"smooth_mode": "smooth", "svg_smooth": 2},
        {"smooth_mode": "smoothm", "svg_smooth": 2},
    ],
    ids=["smooth", "smoothm", "svg", "svg+smooth", "svg+smoothm"],
)
def test_gle_compiles_every_clause_combination(fields, tmp_path):
    fig = _one_line_figure(**fields)
    out = fig.savefig(str(tmp_path / "out.png"))
    assert Path(out).exists()


@pytest.mark.gle
def test_the_emitted_combination_really_applies_both_filters(tmp_path):
    """Proof the token order matters: swapping it changes the picture.

    ``svg_smooth m smooth`` (what the writer emits) renders differently from
    ``smooth svg_smooth m`` (which GLE reduces to ``svg_smooth m``). If the
    writer ever emitted the second order, this test goes red.
    """
    fig = _one_line_figure(smooth_mode="smooth", svg_smooth=2)
    fig.savefig_gle(str(tmp_path / "ours.gle"))
    ours = (tmp_path / "ours.gle").read_text(encoding="utf-8")
    assert " line svg_smooth 2 smooth " in ours

    swapped = ours.replace(" line svg_smooth 2 smooth ", " line smooth svg_smooth 2 ")
    (tmp_path / "swapped.gle").write_text(swapped, encoding="utf-8")

    gle = find_gle()
    assert gle, "the gle marker should have skipped this test"
    renders = {}
    for name in ("ours", "swapped"):
        subprocess.run(
            [gle, "-d", "png", "-r", "100", f"{name}.gle"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        renders[name] = (tmp_path / f"{name}.png").read_bytes()
    assert renders["ours"] != renders["swapped"]

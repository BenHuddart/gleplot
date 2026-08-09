"""G15: an axis range that collapses to a point is GLE's to scale, not ours.

``Figure._resolve_axis_limits`` used to write down whatever autoscale
produced, including ``xaxis min 0.5 max 0.5`` for a lone ``axvline`` or a
single data point. GLE rejects that -- "Error: illegal range for xaxis:
min = 0.5 max = 0.5", exit 1 -- although it will happily scale the same graph
itself. So the emission is dropped and the engine decides; the numbers it
decides on are pinned against the live binary in
``tests/integration/test_degenerate_autoscale_compiles.py`` (cross-cutting
rule 2), never reproduced here.

Two things this module also has to prove, because the change lives in the
middle of the autoscale path:

* nothing that used to compile changed by a byte -- a degenerate range never
  reached the engine, so "currently compiling" and "not degenerate" are the
  same set (``_degenerate_battery`` + the wide digest sweep below);
* an explicit bound is never dropped in silence.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp

from . import _degenerate_battery as db


NEIGHBOUR_SNAPSHOT = json.loads(
    (Path(__file__).parent / "degenerate_neighbour_emissions.json").read_text(
        encoding="utf-8"
    )
)
WIDE_DIGESTS = json.loads(
    (Path(__file__).parent / "wide_battery_digests.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    yield
    glp.close()


def _axes():
    fig = glp.figure(data_prefix="dg")
    return fig, fig.add_subplot(111)


def _generate(fig):
    """Generate, refusing any warning: deferring an autoscale is not news."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        return fig._generate_gle_with_files()


def _axis_line(text, axis):
    """The single ``<axis>axis ...`` settings line, or ``None`` if unemitted."""
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(f"{axis}axis ") or line.strip() == f"{axis}axis"
    ]
    assert len(lines) <= 1, lines
    return lines[0] if lines else None


# --------------------------------------------------------------------------- #
# A collapsed range is left out of the script
# --------------------------------------------------------------------------- #


def test_a_single_data_point_writes_no_range_at_all():
    fig, ax = _axes()
    ax.plot(np.array([1.0]), np.array([2.0]))

    text, _files = _generate(fig)
    assert _axis_line(text, "x") is None
    assert _axis_line(text, "y") is None


def test_a_column_of_points_defers_only_the_axis_that_collapsed():
    """``plot([1, 1], [2, 3])``: x is a point, y is a range. Only x goes."""
    fig, ax = _axes()
    ax.plot(np.array([1.0, 1.0]), np.array([2.0, 3.0]))

    text, _files = _generate(fig)
    assert _axis_line(text, "x") is None
    assert _axis_line(text, "y") == "yaxis min 2 max 3"


def test_a_row_of_points_defers_only_y():
    fig, ax = _axes()
    ax.plot(np.array([2.0, 3.0]), np.array([1.0, 1.0]))

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis min 2 max 3"
    assert _axis_line(text, "y") is None


def test_the_model_keeps_the_deferred_bounds_on_auto():
    """What the model says and what the script says stay the same thing.

    The rest of the autoscale path writes its resolved numbers back onto the
    axes (so a re-save finds nothing left to repair); the deferral has to
    write back ``None``, the model's word for "GLE decides", or a second write
    would resurrect the illegal range.
    """
    fig, ax = _axes()
    ax.plot(np.array([1.0]), np.array([2.0]))

    _generate(fig)
    assert (ax.xmin, ax.xmax, ax.ymin, ax.ymax) == (None, None, None, None)

    # ...and generating again is idempotent, not cumulative.
    text_again, _ = _generate(fig)
    assert _axis_line(text_again, "x") is None


def test_deferring_is_not_worth_a_warning():
    """An autoscaled bound nobody asked for is nobody's business."""
    fig, ax = _axes()
    ax.plot(np.array([1.0]), np.array([2.0]))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig._generate_gle_with_files()
    assert [str(w.message) for w in caught] == []


# --------------------------------------------------------------------------- #
# An explicit bound survives, or is dropped out loud
# --------------------------------------------------------------------------- #


def test_an_explicit_lower_bound_outlives_its_collapsed_partner():
    """``set_xlim(5, None)`` over data that stops at 5 keeps the 5.

    Only the derived bound is dropped, and GLE then draws 5..6 (engine-probed
    in the integration module) -- the user's bound is still the frame's edge.
    """
    fig, ax = _axes()
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.set_xlim(5.0, None)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis min 5"
    assert (ax.xmin, ax.xmax) == (5.0, None)


def test_an_explicit_upper_bound_outlives_its_collapsed_partner():
    fig, ax = _axes()
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.set_xlim(None, 5.0)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis max 5"
    assert (ax.xmin, ax.xmax) == (None, 5.0)


def test_a_range_the_caller_asked_for_is_dropped_but_not_in_silence():
    fig, ax = _axes()
    ax.plot(np.array([1.0, 2.0]), np.array([2.0, 3.0]))
    ax.set_xlim(5.0, 5.0)

    with pytest.warns(UserWarning, match=r"x-axis limits are both 5\.0"):
        text, _files = fig._generate_gle_with_files()

    assert _axis_line(text, "x") is None
    assert (ax.xmin, ax.xmax) == (None, None)
    # The other axis is untouched by its neighbour's trouble.
    assert _axis_line(text, "y") == "yaxis min 2 max 3"


def test_a_collapsed_secondary_y_range_is_deferred_too():
    """``y2axis min v max v`` is the same GLE error; y2 is only ever explicit."""
    fig, ax = _axes()
    ax.plot(np.array([1.0, 2.0]), np.array([2.0, 3.0]))
    ax.plot(np.array([1.0, 2.0]), np.array([9.0, 9.0]), yaxis="y2")
    ax.set_ylim(5.0, 5.0, axis="y2")

    with pytest.warns(UserWarning, match=r"y2-axis limits are both 5\.0"):
        text, _files = fig._generate_gle_with_files()

    assert "y2axis min" not in text
    assert (ax.y2min, ax.y2max) == (None, None)


# --------------------------------------------------------------------------- #
# Guides (SPEC 14.3) -- the case that sent G14 to the supervisor
# --------------------------------------------------------------------------- #


def test_a_lone_axvline_leaves_both_axes_to_the_engine():
    """Neither axis is written down, and no dataset stands in for either.

    G14 wrote a two-point dataset over 0..1 here. Since G17 the guide is a
    ``draw`` (``tests/unit/test_refline_fallback.py``), so the block carries
    no ranges *and* nothing that could imply one.
    """
    fig, ax = _axes()
    ax.axvline(0.5)

    text, files = _generate(fig)
    assert _axis_line(text, "x") is None
    assert _axis_line(text, "y") is None
    assert files == {}
    assert 'draw gleplot_vline 0.5 0 1 "BLACK" 0.05292 1 ""' in text


def test_a_lone_axhline_leaves_both_axes_to_the_engine():
    fig, ax = _axes()
    ax.axhline(0.5)

    text, files = _generate(fig)
    assert _axis_line(text, "x") is None
    assert _axis_line(text, "y") is None
    assert files == {}
    assert 'draw gleplot_hline 0.5 0 1 "BLACK" 0.05292 1 ""' in text


def test_two_guides_still_pin_their_own_axis():
    """Two distinct values are a range; nothing is deferred."""
    fig, ax = _axes()
    ax.axvline(0.25)
    ax.axvline(0.75)

    text, _files = _generate(fig)
    assert _axis_line(text, "x") == "xaxis min 0.25 max 0.75"


def test_a_guide_spanning_a_deferred_axis_is_handed_to_the_engine():
    """The seam between G14 and G15, closed by G17.

    A guide's fractional extent used to be measured against the range gleplot
    resolved. When that range collapsed, gleplot no longer HAS one -- GLE
    picks it, after the script is written -- so materialization reached for
    the same 0..1 fallback it used for an unbounded axis, and the guide's own
    ``0``/``1`` rows then joined GLE's autoscale and moved the frame as well.
    It now goes out as a ``draw`` that reads ``ygmin``/``ygmax`` from inside
    the block, so the extent is taken against the range GLE actually chose and
    the guide takes no part in choosing it. Measured against the engine in
    ``tests/integration/test_guide_draw_form_compiles.py``.

    The lone data point is still the only thing bounding the figure: it keeps
    its own sidecar, and the guide contributes none.
    """
    fig, ax = _axes()
    ax.plot(np.array([5.0]), np.array([7.0]))  # y collapses to 7..7
    ax.axvline(5.0, ymin=0.0, ymax=1.0)

    text, files = _generate(fig)
    assert list(files) == ["dg_0.dat"]
    assert files["dg_0.dat"] == "x y\n5 7\n"
    assert 'draw gleplot_vline 5 0 1 "BLACK" 0.05292 1 ""' in text


# --------------------------------------------------------------------------- #
# Log axes: repaired first, so never seen as degenerate
# --------------------------------------------------------------------------- #


def test_a_log_axis_keeps_the_range_its_own_repair_invented():
    """``_apply_log_limits`` widens 5..5 to a decade; G15 must not undo that.

    A log axis MUST carry an explicit positive min (GLE refuses ``yaxis log``
    over data reaching zero exactly as it refuses ``yaxis min 0 log``), which
    is why the deferral runs after the log repair rather than before it.
    """
    fig, ax = _axes()
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.set_xscale("log")
    ax.set_yscale("log")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        text, _files = fig._generate_gle_with_files()

    assert _axis_line(text, "x") == "xaxis min 5 max 50 log"
    assert _axis_line(text, "y") == "yaxis min 7 max 70 log"


# --------------------------------------------------------------------------- #
# Shared axes: the union is what gets judged
# --------------------------------------------------------------------------- #


def test_a_shared_axis_whose_union_collapses_is_deferred_on_every_panel():
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="dg")
    for ax in axes:
        ax.plot(np.array([1.0]), np.array([2.0]))

    text, _files = _generate(fig)
    assert "xaxis min" not in text
    assert all(ax.xmin is None and ax.xmax is None for ax in axes)


def test_a_shared_axis_whose_union_resolves_is_untouched():
    """One collapsed panel does not cost the grid its shared range."""
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="dg")
    axes[0].plot(np.array([1.0]), np.array([2.0]))
    axes[1].plot(np.array([1.0, 4.0]), np.array([2.0, 3.0]))

    text, _files = _generate(fig)
    assert text.count("xaxis min 1 max 4") == 2
    assert all(ax.xmin == 1.0 and ax.xmax == 4.0 for ax in axes)


# --------------------------------------------------------------------------- #
# Round trip
# --------------------------------------------------------------------------- #


def _round_trip(build, tmp_path):
    """``(first_write, second_write)`` for ``build``, through the parser."""
    from gleplot import axes as _axes_module
    from gleplot.parser.recognizer import parse_gle_figure

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    _axes_module._global_data_file_counter = 0
    glp.close()
    build().savefig_gle(str(first_dir / "figure.gle"))
    first = (first_dir / "figure.gle").read_text(encoding="utf-8")

    _axes_module._global_data_file_counter = 0
    glp.close()
    parse_gle_figure(first_dir / "figure.gle").figure.savefig_gle(
        str(second_dir / "figure.gle")
    )
    return first, (second_dir / "figure.gle").read_text(encoding="utf-8")


def _single_point():
    fig, ax = _axes()
    ax.plot(np.array([1.0]), np.array([2.0]))
    return fig


def _column_of_points():
    fig, ax = _axes()
    ax.plot(np.array([1.0, 1.0]), np.array([2.0, 3.0]))
    return fig


def _half_explicit():
    fig, ax = _axes()
    ax.plot(np.array([5.0]), np.array([7.0]))
    ax.set_xlim(5.0, None)
    return fig


def _shared_and_deferred():
    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix="dg")
    for ax in axes:
        ax.plot(np.array([1.0]), np.array([2.0]))
    return fig


@pytest.mark.parametrize(
    "build",
    [_single_point, _column_of_points, _half_explicit, _shared_and_deferred],
    ids=["single_point", "column_of_points", "half_explicit", "shared_and_deferred"],
)
def test_a_deferred_figure_is_a_writer_parse_writer_fixed_point(build, tmp_path):
    """The SPEC 10.2 invariant survives a range gleplot chose not to write.

    Nothing is written down, so the parser recovers auto limits and the second
    write re-derives the same collapse and defers it again. (What it must NOT
    do is recover the range GLE picked -- gleplot never sees that number, and
    `project.json`/the model stay on auto.)
    """
    first, second = _round_trip(build, tmp_path)
    assert second == first


@pytest.mark.parametrize(
    "build_guide,spanned",
    [
        (lambda ax: ax.axvline(0.5), "y"),
        (lambda ax: ax.axvspan(0.4, 0.6), "y"),
        (lambda ax: ax.axhline(0.5, label="limit"), "x"),
    ],
    ids=["axvline", "axvspan", "labelled-axhline"],
)
def test_a_drawn_guide_costs_the_round_trip_nothing(build_guide, spanned, tmp_path):
    """The seam G14 opened and G17 closed -- now a fixed point.

    G14 realized a guide as a real two-point dataset at write time. On the way
    back in the parser saw data, not a declaration, so that dataset *bounded*
    the axis it had been drawn across -- and since gleplot had written no
    range for that axis, the second write autoscaled over it and emitted one
    (``yaxis min 0 max 1``, verified on the pre-G15 base 1757ce1 for both a
    lone ``axvline`` and a lone ``axvspan``). G15 moved one more figure into
    the seam rather than creating it.

    A guide with nothing to measure against is now emitted as a ``draw``,
    which owns no data, declares its own kind, and is recognized straight back
    into a ``RefLine``/``Span``. So there is nothing for autoscale to find and
    nothing to reconstruct: the two writes agree, byte for byte.
    """

    def build():
        fig, ax = _axes()
        build_guide(ax)
        return fig

    first, second = _round_trip(build, tmp_path)
    # The axis the guide SPANS is the one at issue: it has nothing to resolve
    # it, and no re-read dataset invents one on the second write either. (A
    # band's own edges legitimately bound the axis it is positioned on, and
    # gleplot writes that range on both passes -- as it always did.)
    assert _axis_line(first, spanned) is None
    assert _axis_line(second, spanned) is None
    assert first == second


def test_serialization_gained_no_fields():
    """G15 adds no model state: the deferral is a write-time decision."""
    fig, ax = _axes()
    ax.plot(np.array([1.0]), np.array([2.0]))
    before = set(fig.to_dict()["figure"]["axes"][0])

    _generate(fig)
    assert set(fig.to_dict()["figure"]["axes"][0]) == before
    assert {"xmin", "xmax", "ymin", "ymax", "y2min", "y2max"} <= before


# --------------------------------------------------------------------------- #
# Byte-level regression guards
# --------------------------------------------------------------------------- #


def test_the_neighbour_snapshot_covers_the_whole_battery():
    assert sorted(NEIGHBOUR_SNAPSHOT) == sorted(db.BUILDER_IDS)


@pytest.mark.parametrize("name", db.BUILDER_IDS)
def test_a_resolvable_range_emits_byte_identically_to_pre_g15(name):
    """Every figure GLE could already compile is untouched, warnings included.

    One entry has moved since capture, and only one: G18-lite gave
    ``guides_over_data`` a ``! gleplot:guide ...`` comment over each of its
    four materialized guides (:mod:`gleplot.guides`). Comments only -- no
    statement, no dataset index and no sidecar byte changed, and the wide
    digest sweep below (which contains no guides at all) is untouched.
    ``tests/unit/test_refline_fallback.py`` pins that pure-insertion property
    for the whole guide battery.
    """
    text, files, raised = db.emit(name)

    reference = NEIGHBOUR_SNAPSHOT[name]
    assert text == reference["gle"]
    assert files == reference["files"]
    assert raised == reference["warnings"]


def _digest(text, files):
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    for name in sorted(files):
        h.update(b"\0" + name.encode("utf-8") + b"\0" + files[name].encode("utf-8"))
    return h.hexdigest()


def _wide_battery():
    """The golden + project batteries, as ``(id, builder)`` pairs.

    43 figures between them, covering every series type, subplot shape,
    legend, colorbar, file-series and passthrough path the writer has -- a
    much wider net than a hand-picked list, at the price of a digest instead
    of readable text. ``degenerate_neighbour_emissions.json`` is the readable
    half; this is the breadth.
    """
    from tests.integration import test_project_io as project
    from tests.parser import _golden_battery as golden

    for label, builders in (("golden", golden.BUILDERS), ("project", project.BUILDERS)):
        for builder in builders:
            yield f"{label}:{builder.__name__.lstrip('_')}", builder


WIDE_CASES = list(_wide_battery())


def test_the_digest_sweep_covers_both_batteries():
    assert sorted(WIDE_DIGESTS) == sorted(name for name, _ in WIDE_CASES)


@pytest.mark.parametrize("name,builder", WIDE_CASES, ids=[n for n, _ in WIDE_CASES])
def test_the_wide_battery_hashes_to_its_pre_g15_emission(name, builder):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        text, files = builder()._generate_gle_with_files()
    assert _digest(text, files) == WIDE_DIGESTS[name]

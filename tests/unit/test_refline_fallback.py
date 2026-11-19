"""G14/G17: a guide on an axis that resolves to nothing is GLE's to range.

Before G14, ``axvline`` on an otherwise-empty axes emitted *nothing* plus a
``UserWarning``: with no data and no ``set_ylim`` there was no y range to span,
so the guide was dropped. G14 materialized it over
:data:`gleplot.axes.EMPTY_AXIS_FALLBACK_RANGE` instead -- a literal two-point
dataset over 0..1, GLE's own bound-less range.

**G17 replaced that dataset with a ``draw`` call.** Guessing the range wrong
was only half the problem; the guessing dataset also *joined GLE's autoscale*,
so on any axes that was not completely empty it moved the frame it was
guessing at (measured: a guide declaring 100 % of the frame covering 14.3 % of
it -- see ``tests/integration/test_guide_draw_form_compiles.py``). A guide
emitted as ``draw gleplot_vline ...`` inside its own layer reads GLE's
``ygmin``/``ygmax`` after the range is fixed, so it spans the rendered frame by
construction and contributes nothing to choosing it. This module now pins that
emission; the constant survives as the measured statement of what an unbounded
GLE axis does, which is what the draw form reproduces on an empty axes.

The other half of the task is unchanged and is the point of the file: *nothing
else moved*. Every figure in ``_refline_battery`` has resolvable limits and
must emit exactly the bytes the pre-G14 writer produced, which
``refline_resolvable_emissions.json`` (captured on base commit 83dcdd9) pins --
byte for byte, through G14 and G17 alike. One entry has moved since:
``guides_beside_a_secondary_y_axis`` narrowed its primary ``yaxis`` range,
and the vertical guides that span it, when the series on y2 stopped counting
toward that range (#142).

**G18-lite adds one line per materialized guide, and only that.** The snapshot
was regenerated for it: every guide-bearing entry gained its
``! gleplot:guide ...`` provenance comment (:mod:`gleplot.guides`) and nothing
else -- no statement changed, no dataset index moved, no sidecar byte moved.
That claim is not left to the eye of whoever read the diff:
``test_the_g18_lite_marker_is_a_pure_insertion`` stubs the marker methods out
and requires the emission to equal this snapshot with its marker lines
deleted, which is the pre-G18-lite text this file has pinned all along.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot as glp
from gleplot.axes import EMPTY_AXIS_FALLBACK_RANGE
from gleplot.guides import GUIDE_MARKER_PREFIX
from gleplot.writer import GLEWriter

from . import _refline_battery as rb

SNAPSHOT_PATH = Path(__file__).parent / "refline_resolvable_emissions.json"
SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _rows(files, name):
    """Parse a generated sidecar into a list of float rows (header skipped)."""
    out = []
    for line in files[name].strip().splitlines():
        if not line.strip():
            continue
        try:
            out.append([float(tok) for tok in line.split()])
        except ValueError:
            continue  # header row
    return out


def _empty_axes():
    fig = glp.figure(data_prefix="fb")
    return fig, fig.add_subplot(111)


def _generate(fig):
    """Generate, asserting no warning is raised on the way (G14 retired it)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        text, files = fig._generate_gle_with_files()
    assert [str(w.message) for w in caught] == []
    return text, files


# --------------------------------------------------------------------------- #
# The fallback itself
# --------------------------------------------------------------------------- #


def test_fallback_range_is_gles_own_empty_graph_range():
    """Pinned numerically here; pinned against the engine in the gle suite."""
    assert EMPTY_AXIS_FALLBACK_RANGE == (0.0, 1.0)


def _draw_calls(text):
    """Every ``draw gleplot_*`` line in a script, stripped."""
    return [
        ln.strip() for ln in text.splitlines() if ln.strip().startswith("draw gleplot_")
    ]


def test_axvline_on_an_empty_axes_is_drawn_over_gles_own_y_range():
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_vline 0.5 0 1 "BLACK" 0.05292 1 ""']
    # No literal dataset, and therefore no sidecar to feed GLE's autoscale.
    assert files == {}
    assert entry["data_file"] not in text


def test_axhline_on_an_empty_axes_is_drawn_over_gles_own_x_range():
    fig, ax = _empty_axes()
    ax.axhline(0.5)
    text, files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_hline 0.5 0 1 "BLACK" 0.05292 1 ""']
    assert files == {}


def test_axvspan_on_an_empty_axes_is_drawn_over_gles_own_y_range():
    fig, ax = _empty_axes()
    ax.axvspan(0.4, 0.6)
    text, files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_vspan 0.4 0.6 0 1 "LIGHTGRAY" ""']
    assert files == {}


def test_axhspan_on_an_empty_axes_is_drawn_over_gles_own_x_range():
    fig, ax = _empty_axes()
    ax.axhspan(0.4, 0.6)
    text, files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_hspan 0.4 0.6 0 1 "LIGHTGRAY" ""']
    assert files == {}


def test_the_fractional_extent_travels_as_a_fraction():
    """The 40%-60% placeholder band of SPEC 14.3 stays 0.4..0.6 of the frame.

    The fraction is no longer resolved into data coordinates at write time --
    it is handed to GLE as a fraction and resolved inside the graph block.
    """
    fig, ax = _empty_axes()
    ax.axvline(0.5, ymin=0.4, ymax=0.6)
    text, _files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_vline 0.5 0.4 0.6 "BLACK" 0.05292 1 ""']


def test_one_resolvable_bound_is_not_enough_to_materialize():
    """The routing is per axis, not per bound.

    ``set_ylim(-3, None)`` pins the bottom of the frame and leaves the top to
    GLE. G14 mixed the two -- the real ``-3`` with a fabricated ``1`` -- which
    put the guide's top edge wherever 1 happened to land. The draw form needs
    no such mixture: ``ygmin`` is the -3 gleplot wrote and ``ygmax`` is
    whatever GLE chose.
    """
    fig, ax = _empty_axes()
    ax.set_ylim(-3.0, None)
    ax.axvline(0.5)
    text, files = _generate(fig)

    assert "yaxis min -3" in text
    assert _draw_calls(text) == ['draw gleplot_vline 0.5 0 1 "BLACK" 0.05292 1 ""']
    assert files == {}


def test_a_guide_carries_every_styling_field_the_dataset_form_did():
    """colour, linestyle, width and label all survive the draw form."""
    fig, ax = _empty_axes()
    ax.axvline(0.5, color="red", linestyle="--", linewidth=2.0, label='say "hi"')
    text, _files = _generate(fig)

    assert _draw_calls(text) == [
        'draw gleplot_vline 0.5 0 1 "RED" 0.07056 3 "say \\"hi\\""'
    ]
    # A draw call owns no dataset and so cannot carry 'key'; the legend entry
    # rides on a separate data-free dN line with the same style.
    assert '    d1 line color RED lwidth 0.07056 lstyle 3 key "say ""hi"""' in text


def test_a_lineless_guide_draws_nothing_but_is_still_declared():
    """``linestyle='none'`` -> lstyle 0, GLE's own "no style set" sentinel."""
    fig, ax = _empty_axes()
    ax.axvline(0.5, linestyle="none")
    text, _files = _generate(fig)

    assert _draw_calls(text) == ['draw gleplot_vline 0.5 0 1 "BLACK" 0.05292 0 ""']


def test_a_translucent_band_keeps_its_rgba_colour():
    """Alpha is folded into the colour exactly as ``add_fill`` folds it."""
    fig, ax = _empty_axes()
    ax.axvspan(0.4, 0.6, color="orange", alpha=0.35)
    text, _files = _generate(fig)

    assert _draw_calls(text) == [
        'draw gleplot_vspan 0.4 0.6 0 1 "rgba255(255,165,0,89)" ""'
    ]


def test_the_guide_subs_are_emitted_once_and_only_when_used():
    fig, ax = _empty_axes()
    ax.axvline(0.1)
    ax.axvline(0.2)
    ax.axvspan(0.4, 0.6)
    text, _files = _generate(fig)

    assert text.count("sub gleplot_vline ") == 1
    assert text.count("sub gleplot_vspan ") == 1
    assert "sub gleplot_hline " not in text
    assert "sub gleplot_hspan " not in text


def test_a_resolvable_guide_pulls_in_no_guide_sub_at_all():
    fig, ax = _empty_axes()
    ax.set_ylim(0.0, 10.0)
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert "sub gleplot_" not in text
    assert "draw gleplot_" not in text
    assert _rows(files, entry["data_file"]) == [[0.5, 0.0], [0.5, 10.0]]


def test_a_hidden_guide_still_materializes_into_nothing():
    """G11 visibility outranks the routing: hidden means absent, both ways."""
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    entry["visible"] = False
    text, files = _generate(fig)

    assert files == {}
    assert "\n    data " not in text
    assert "gleplot_vline" not in text


def test_no_warning_is_raised_where_the_guide_used_to_be_dropped():
    """The G14 warning is retired -- not merely reworded."""
    for build in (
        lambda ax: ax.axvline(0.5),
        lambda ax: ax.axhline(0.5),
        lambda ax: ax.axvspan(0.4, 0.6),
        lambda ax: ax.axhspan(0.4, 0.6),
    ):
        fig, ax = _empty_axes()
        build(ax)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            fig._generate_gle_with_files()


def test_the_routing_reruns_per_write_so_later_data_wins():
    """Which form a guide takes is a write-time decision, never stored.

    This is the asymmetry candidate 1a buys its byte-identity with: adding
    data to the axes switches the guide from the draw form back to the
    literal dataset, silently, because the axis it spans now resolves.
    """
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    text, files = _generate(fig)
    assert _draw_calls(text) == ['draw gleplot_vline 0.5 0 1 "BLACK" 0.05292 1 ""']
    assert files == {}

    ax.plot(np.array([0.0, 1.0]), np.array([10.0, 20.0]))
    text, files = _generate(fig)
    assert _draw_calls(text) == []
    assert _rows(files, entry["data_file"]) == [[0.5, 10.0], [0.5, 20.0]]


def test_resolved_limits_keep_the_literal_dataset():
    fig, ax = _empty_axes()
    ax.set_ylim(100.0, 200.0)
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert _rows(files, entry["data_file"]) == [[0.5, 100.0], [0.5, 200.0]]
    assert "gleplot_vline" not in text


# --------------------------------------------------------------------------- #
# Guides survive the round trip AS guides, which is new in G17
# --------------------------------------------------------------------------- #


def _neg_adjacent_refline(entry):
    """Force ``span_lo`` negative, so a refline's ``value lo`` are adjacent.

    ``axvline``/``axhline``'s public API clamps ``ymin``/``xmin`` (here
    ``span_lo``) to ``[0, 1]`` (matplotlib semantics), so it alone can never
    reproduce G17.1's merge bug: ``draw gleplot_vline value lo hi ...`` needs
    ``value`` AND ``lo`` both negative and adjacent, and the public
    constructor forbids a negative ``lo``. The model enforces nothing at this
    level -- a ``RefLine`` is a plain dict, and GLEstudio's ``project.json``
    is authoritative and can set ``span_lo`` to anything -- so this is a
    state the recognizer still has to read correctly even though the
    convenience constructor never produces it directly.
    """
    entry["span_lo"] = -3.0
    return entry


@pytest.mark.parametrize(
    "build",
    [
        lambda ax: ax.axvline(0.5, color="red", linestyle="--", label="thr"),
        lambda ax: ax.axhline(-2.5, xmin=0.25, xmax=0.75, linewidth=3.0),
        lambda ax: ax.axvspan(0.4, 0.6, color="orange", alpha=0.35),
        lambda ax: ax.axhspan(1.0, 2.0, xmin=0.1, xmax=0.9, label="band"),
        # G17.1: two adjacent negative coordinates in the draw call's own
        # argument list (`draw gleplot_vspan -4 -3 ...` used to merge into one
        # `-7` argument and fall to passthrough before whitespace splitting).
        lambda ax: _neg_adjacent_refline(
            ax.axvline(-4.0, color="red", label='say "hi" there')
        ),
        lambda ax: _neg_adjacent_refline(ax.axhline(-4.0, linewidth=2.0)),
        lambda ax: ax.axvspan(-4.0, -3.0, color="orange"),
        lambda ax: ax.axhspan(-4.0, -3.0, xmin=0.1, xmax=0.9, label="band"),
    ],
    ids=[
        "axvline",
        "axhline",
        "axvspan",
        "axhspan",
        "axvline-adjacent-negatives",
        "axhline-adjacent-negatives",
        "axvspan-adjacent-negatives",
        "axhspan-adjacent-negatives",
    ],
)
def test_a_drawn_guide_round_trips_as_a_guide(build, tmp_path):
    """emit -> parse -> model is a RefLine/Span -> emit is byte-identical.

    The dataset form cannot do this: it re-parses as an ordinary series, so
    every guide lost its SPEC 14.3 identity on the way back in. The draw call
    names its own kind, so this is the new fixed point.
    """
    import gleplot as glp

    fig, ax = _empty_axes()
    original = build(ax)
    first = tmp_path / "a.gle"
    fig.savefig_gle(str(first))

    parsed = glp.open_gle(str(first))
    ax2 = parsed.axes_list[0]
    guides = ax2.reflines + ax2.spans
    assert len(guides) == 1
    recovered = guides[0]

    # Every field survives except the two the writer normalizes on the way
    # out for EVERY series kind: 'linewidth' is emitted in cm through the
    # style config's default (so the model's sentinel 1 comes back as the
    # 1.5 pt actually drawn), and 'data_file' names a sidecar the draw form
    # never writes, so a fresh one is reserved on the way in.
    for field in ("type", "orient", "span_lo", "span_hi", "label"):
        assert recovered[field] == original[field], field
    if original["type"] == "refline":
        assert recovered["value"] == original["value"]
        assert recovered["color"] == original["color"]
        assert recovered["linestyle"] == original["linestyle"]
    else:
        assert (recovered["start"], recovered["end"]) == (
            original["start"],
            original["end"],
        )

    # Nothing leaked into passthrough or into a phantom data series.
    assert ax2.passthrough == []
    assert ax2.lines == [] and ax2.fills == []

    second = tmp_path / "b.gle"
    parsed.savefig_gle(str(second))
    assert second.read_text(encoding="utf-8") == first.read_text(encoding="utf-8")


def test_the_documented_g17_1_case_recovers_as_a_span(tmp_path):
    """``draw gleplot_vspan -4 -3 0 1 "LIGHTGRAY" ""`` recovers as a Span.

    Before G17.1, ``_guide_call_args`` read ``-4 -3`` as the one expression
    ``-4-3`` (``_collect_value`` treats a bare ``-`` as a binary operator
    regardless of the whitespace around it), so this five-argument read
    fell one short of the six ``gleplot_vspan`` takes and the whole block
    degraded to raw passthrough. GLE itself splits sub-call arguments on
    whitespace (probe-verified on GLE 4.3.10), so the *rendering* was
    always correct -- only the recognizer's identity recovery was wrong.
    """
    from gleplot.parser.recognizer import parse_gle_figure

    block = '   begin layer 349\n      draw gleplot_vspan -4 -3 0 1 "LIGHTGRAY" ""\n   end layer'
    src = tmp_path / "hand.gle"
    src.write_text(_HAND_WRITTEN.format(block=block), encoding="utf-8")

    recognized = parse_gle_figure(str(src))
    ax = recognized.figure.axes_list[0]

    assert ax.reflines == []
    assert len(ax.spans) == 1
    span = ax.spans[0]
    assert (span["start"], span["end"]) == (-4.0, -3.0)
    assert (span["span_lo"], span["span_hi"]) == (0.0, 1.0)
    assert span["color"] == "LIGHTGRAY"
    assert ax.passthrough == []
    assert not any(w.startswith("structure:") for w in recognized.warnings)


_HAND_WRITTEN = """\
! GLE graphics file
size 20.32 15.24
begin graph
   size 17.992 13.3352
   scale 1 1
{block}
end graph
"""


@pytest.mark.parametrize(
    "block",
    [
        # Not a gleplot guide sub at all.
        "   begin layer 699\n      draw my_own_marker 1 2\n   end layer",
        # Right sub, wrong number of arguments.
        '   begin layer 699\n      draw gleplot_vline 0.5 0 1 "BLACK"\n   end layer',
        # Right sub and arity, but the z-order has been edited by hand.
        '   begin layer 42\n      draw gleplot_vline 0.5 0 1 "BLACK" 0.05 1 ""'
        "\n   end layer",
        # A bare draw with no layer block around it.
        '   draw gleplot_vline 0.5 0 1 "BLACK" 0.05 1 ""',
        # gleplot's own guide-sub prefix, but not one of the four calls it
        # actually writes.
        '   begin layer 699\n      draw gleplot_typo 1 0 1 "BLACK" 0.05 1 ""'
        "\n   end layer",
    ],
    ids=["foreign-sub", "wrong-arity", "edited-layer", "no-layer", "unknown-prefix"],
)
def test_only_the_writers_own_shape_is_read_back_as_a_guide(block, tmp_path):
    """Everything else survives verbatim instead of being reinterpreted.

    Recognition keys off the literal call name AND the shape the writer
    emits. A near miss is not half-read into a mangled guide and is not
    dropped: it stays raw GLE, which is what re-emitting it byte-for-byte
    requires.
    """
    import gleplot as glp

    src = tmp_path / "hand.gle"
    src.write_text(_HAND_WRITTEN.format(block=block), encoding="utf-8")

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        parsed = glp.open_gle(str(src))
    # Whatever open_gle reports for a near miss is a structure note.
    assert all(str(w.message).startswith("structure: ") for w in record)
    ax = parsed.axes_list[0]
    assert ax.reflines == [] and ax.spans == []
    assert any("draw " in line for line in ax.passthrough)

    out = tmp_path / "hand-again.gle"
    parsed.savefig_gle(str(out))
    assert block.strip().splitlines()[-1].strip() in out.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "block,call,expect_note",
    [
        (
            "   begin layer 699\n      draw my_own_marker 1 2\n   end layer",
            "my_own_marker",
            False,
        ),
        (
            '   begin layer 699\n      draw gleplot_vline 0.5 0 1 "BLACK"\n   end layer',
            "gleplot_vline",
            True,
        ),
        (
            '   begin layer 42\n      draw gleplot_vline 0.5 0 1 "BLACK" 0.05 1 ""'
            "\n   end layer",
            "gleplot_vline",
            True,
        ),
        (
            '   draw gleplot_vline 0.5 0 1 "BLACK" 0.05 1 ""',
            "gleplot_vline",
            False,
        ),
        (
            '   begin layer 699\n      draw gleplot_typo 1 0 1 "BLACK" 0.05 1 ""'
            "\n   end layer",
            "gleplot_typo",
            True,
        ),
    ],
    ids=["foreign-sub", "wrong-arity", "edited-layer", "no-layer", "unknown-prefix"],
)
def test_a_degraded_gleplot_guide_block_is_never_silent(
    block, call, expect_note, tmp_path
):
    """G17.1: identity loss on a gleplot_*-shaped block is noted, not silent.

    A block that is not even shaped like a gleplot guide call -- no
    ``gleplot_`` prefix on the call name, or no enclosing layer at all --
    is not gleplot's own to explain and stays quietly-preserved raw GLE,
    exactly as before. But a block that IS recognizably gleplot's -- the
    call has the guide-sub prefix, or the call name and arity match but the
    layer was edited, or the arity itself is wrong -- degrades to
    passthrough with a ``structure:`` note now, the same "no silent drops"
    rule already applied to the G18-lite marker's own tampering cases.
    """
    from gleplot.parser.recognizer import parse_gle_figure

    src = tmp_path / "hand.gle"
    src.write_text(_HAND_WRITTEN.format(block=block), encoding="utf-8")

    recognized = parse_gle_figure(str(src))
    ax = recognized.figure.axes_list[0]
    assert ax.reflines == [] and ax.spans == []

    matching = [
        w
        for w in recognized.warnings
        if w.startswith("structure:") and f"'draw {call}'" in w
    ]
    if expect_note:
        assert len(matching) == 1, recognized.warnings
    else:
        assert matching == [], matching


# --------------------------------------------------------------------------- #
# Byte-level regression guard for every resolvable-limits path
# --------------------------------------------------------------------------- #


def test_the_snapshot_covers_the_whole_battery():
    assert sorted(SNAPSHOT) == sorted(rb.BUILDER_IDS)


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_resolvable_limits_emit_byte_identically_to_pre_g14(name):
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        text, files = rb.emit(name)

    reference = SNAPSHOT[name]
    assert text == reference["gle"]
    assert files == reference["files"]


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_the_g18_lite_marker_is_a_pure_insertion(name, monkeypatch):
    """Suppress the marker and the pre-G18-lite bytes come back, exactly.

    This is what "additive bytes only" means, made checkable: the emission
    with the marker methods stubbed out must equal the snapshot with its
    marker lines deleted -- same ``data`` statements, same dataset indices,
    same sidecars, same everything. If adding a comment had shifted a dataset
    number or a byte of a sidecar, the two sides would not meet.
    """
    monkeypatch.setattr(
        GLEWriter, "add_refline_marker", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        GLEWriter, "add_span_marker", lambda *a, **k: None, raising=True
    )
    text, files = rb.emit(name)

    reference = SNAPSHOT[name]
    # Whole physical lines, so a trailing newline is neither added nor lost.
    unmarked = re.sub(
        r"^[ \t]*" + re.escape(GUIDE_MARKER_PREFIX) + r"[^\n]*\n",
        "",
        reference["gle"],
        flags=re.MULTILINE,
    )
    assert text == unmarked
    assert files == reference["files"]


@pytest.mark.parametrize("name", rb.BUILDER_IDS)
def test_every_marker_in_the_snapshot_stands_over_a_data_statement(name):
    """The marker's binding is positional, so its position is part of the pin."""
    lines = [line.strip() for line in SNAPSHOT[name]["gle"].splitlines()]
    for i, line in enumerate(lines):
        if line.startswith(GUIDE_MARKER_PREFIX):
            assert lines[i + 1].startswith("data "), lines[i + 1]

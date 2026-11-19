"""G14/G17: a guide on an axis that resolves to nothing is GLE's to range.

Before G14, ``axvline`` on an otherwise-empty axes emitted *nothing* plus a
``UserWarning``: with no data and no ``set_ylim`` there was no y range to span,
so the guide was dropped. G14 materialized it over
:data:`gleplot.axes.EMPTY_AXIS_FALLBACK_RANGE` instead -- a literal two-point
dataset over 0..1, GLE's own bound-less range.

**G17 replaced that dataset with a drawing against GLE's own range.**
Guessing the range wrong was only half the problem; the guessing dataset also
*joined GLE's autoscale*, so on any axes that was not completely empty it moved
the frame it was guessing at (measured: a guide declaring 100 % of the frame
covering 14.3 % of it -- see
``tests/integration/test_guide_draw_form_compiles.py``). The guide is drawn
after ``end graph``, with ``graph_vline``/``graph_hline`` from GLE's
``graphutil.gle`` or a ``box``, where ``ygmin``/``ygmax`` hold the range GLE
chose, so it spans the rendered frame by construction and contributes nothing
to choosing it (:mod:`gleplot.guides`). This module pins that emission; the
constant survives as the measured statement of what an unbounded GLE axis
does, which the after-graph form reproduces on an empty axes.

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
``test_the_g18_lite_marker_is_a_pure_insertion`` stubs the marker out
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
    """The drawing lines of every guide drawn after ``end graph``, stripped.

    The marker, ``gsave`` and ``grestore`` around each are left out.
    """
    after = text.split("\nend graph", 1)[1].split("begin key")[0]
    return [
        ln.strip()
        for ln in after.splitlines()
        if ln.strip()
        and ln.strip() not in ("gsave", "grestore")
        and not ln.strip().startswith(GUIDE_MARKER_PREFIX)
    ]


def test_axvline_on_an_empty_axes_is_drawn_over_gles_own_y_range():
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert _draw_calls(text) == ["set color BLACK lwidth 0.05292", "graph_vline 0.5"]
    assert 'include "graphutil.gle"' in text
    # No literal dataset, and therefore no sidecar to feed GLE's autoscale.
    assert files == {}
    assert entry["data_file"] not in text


def test_axhline_on_an_empty_axes_is_drawn_over_gles_own_x_range():
    fig, ax = _empty_axes()
    ax.axhline(0.5)
    text, files = _generate(fig)

    assert _draw_calls(text) == ["set color BLACK lwidth 0.05292", "graph_hline 0.5"]
    assert files == {}


def test_axvspan_on_an_empty_axes_is_drawn_over_gles_own_y_range():
    fig, ax = _empty_axes()
    ax.axvspan(0.4, 0.6)
    text, files = _generate(fig)

    assert _draw_calls(text) == [
        "amove xg(0.4) yg(ygmin)",
        "box xg(0.6)-xg(0.4) yg(ygmax)-yg(ygmin) fill LIGHTGRAY nobox",
    ]
    # A band needs no routine from GLE's library.
    assert "include" not in text
    assert files == {}


def test_axhspan_on_an_empty_axes_is_drawn_over_gles_own_x_range():
    fig, ax = _empty_axes()
    ax.axhspan(0.4, 0.6)
    text, files = _generate(fig)

    assert _draw_calls(text) == [
        "amove xg(xgmin) yg(0.4)",
        "box xg(xgmax)-xg(xgmin) yg(0.6)-yg(0.4) fill LIGHTGRAY nobox",
    ]
    assert files == {}


def test_the_fractional_extent_travels_as_a_fraction():
    """The 40%-60% placeholder band of SPEC 14.3 stays 0.4..0.6 of the frame.

    The fraction is not resolved into data coordinates at write time -- it is
    written as an expression in the range GLE chose.
    """
    fig, ax = _empty_axes()
    ax.axvline(0.5, ymin=0.4, ymax=0.6)
    text, _files = _generate(fig)

    assert _draw_calls(text) == [
        "set color BLACK lwidth 0.05292",
        "graph_vline 0.5 ygmin+(ygmax-ygmin)*0.4 ygmin+(ygmax-ygmin)*0.6",
    ]


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
    assert _draw_calls(text) == ["set color BLACK lwidth 0.05292", "graph_vline 0.5"]
    assert files == {}


def test_a_guide_carries_every_styling_field_the_dataset_form_did():
    """colour, linestyle, width and label all survive the after-graph form."""
    fig, ax = _empty_axes()
    ax.axvline(0.5, color="red", linestyle="--", linewidth=2.0, label='say "hi"')
    text, _files = _generate(fig)

    assert _draw_calls(text) == [
        "set color RED lwidth 0.07056 lstyle 3",
        "graph_vline 0.5",
    ]
    assert '! gleplot:guide refline v value 0.5 extent 0,1 label "say \\"hi\\""' in (
        text
    )
    # The drawing owns no dataset and so cannot carry 'key'; the legend entry
    # rides on a separate data-free dN line with the same style.
    assert '    d1 line color RED lwidth 0.07056 lstyle 3 key "say ""hi"""' in text


@pytest.mark.parametrize("linestyle", ["none", None])
def test_a_lineless_guide_draws_nothing_but_is_still_declared(linestyle):
    """No line: the style is written, the call is not."""
    fig, ax = _empty_axes()
    ax.axvline(0.5, linestyle=linestyle)
    text, _files = _generate(fig)

    assert _draw_calls(text) == ["set color BLACK lwidth 0.05292"]
    assert "include" not in text


def test_a_translucent_band_keeps_its_rgba_colour():
    """Alpha is folded into the colour exactly as ``add_fill`` folds it."""
    fig, ax = _empty_axes()
    ax.axvspan(0.4, 0.6, color="orange", alpha=0.35)
    text, _files = _generate(fig)

    assert _draw_calls(text)[1] == (
        "box xg(0.6)-xg(0.4) yg(ygmax)-yg(ygmin) fill rgba255(255,165,0,89) nobox"
    )


def test_graphutil_is_included_once_and_only_when_used():
    fig, ax = _empty_axes()
    ax.axvline(0.1)
    ax.axvline(0.2)
    ax.axvspan(0.4, 0.6)
    text, _files = _generate(fig)

    assert text.count('include "graphutil.gle"') == 1


def test_a_resolvable_guide_is_not_drawn_after_the_graph():
    fig, ax = _empty_axes()
    ax.set_ylim(0.0, 10.0)
    entry = ax.axvline(0.5)
    text, files = _generate(fig)

    assert "include" not in text
    assert "graph_vline" not in text
    assert _rows(files, entry["data_file"]) == [[0.5, 0.0], [0.5, 10.0]]


def test_a_hidden_guide_still_materializes_into_nothing():
    """G11 visibility outranks the routing: hidden means absent, both ways."""
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    entry["visible"] = False
    text, files = _generate(fig)

    assert files == {}
    assert "\n    data " not in text
    assert "graph_vline" not in text


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
    data to the axes switches the guide from the after-graph form back to the
    literal dataset, silently, because the axis it spans now resolves.
    """
    fig, ax = _empty_axes()
    entry = ax.axvline(0.5)
    text, files = _generate(fig)
    assert _draw_calls(text) == ["set color BLACK lwidth 0.05292", "graph_vline 0.5"]
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
    assert "graph_vline" not in text


# --------------------------------------------------------------------------- #
# Guides survive the round trip AS guides, which is new in G17
# --------------------------------------------------------------------------- #


def _neg_adjacent_refline(entry):
    """Force ``span_lo`` negative, beside a negative ``value``.

    ``axvline``/``axhline``'s public API clamps ``ymin``/``xmin`` (here
    ``span_lo``) to ``[0, 1]`` (matplotlib semantics). The model enforces
    nothing at this level -- a ``RefLine`` is a plain dict -- so this is a
    state the recognizer still has to read correctly: the marker's pairs are
    comma-separated so ``-4 -3`` is not read as ``-7``.
    """
    entry["span_lo"] = -3.0
    return entry


@pytest.mark.parametrize(
    "build",
    [
        lambda ax: ax.axvline(0.5, color="red", linestyle="--", label="thr"),
        lambda ax: ax.axhline(-2.5, xmin=0.25, xmax=0.75, linewidth=3.0),
        lambda ax: ax.axvline(0.5, linestyle="none", label="hidden line"),
        lambda ax: ax.axvspan(0.4, 0.6, color="orange", alpha=0.35),
        lambda ax: ax.axhspan(1.0, 2.0, xmin=0.1, xmax=0.9, label="band"),
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
        "axvline-no-line",
        "axvspan",
        "axhspan",
        "axvline-adjacent-negatives",
        "axhline-adjacent-negatives",
        "axvspan-adjacent-negatives",
        "axhspan-adjacent-negatives",
    ],
)
def test_a_drawn_guide_round_trips_as_a_guide(build, tmp_path):
    """emit -> parse -> model is a RefLine/Span -> emit is byte-identical."""
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
    # 1.5 pt actually drawn), and 'data_file' names a sidecar the after-graph
    # form never writes, so a fresh one is reserved on the way in.
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


@pytest.mark.parametrize(
    "build,old,new",
    [
        (lambda ax: ax.axvline(0.5), "graph_vline 0.5", "graph_vline 0.7"),
        (lambda ax: ax.axvline(0.5), "lwidth 0.05292", "lstyle 2"),
        (lambda ax: ax.axvline(0.5), "lwidth 0.05292", "lwidth 0.05292 lstyle 2.5"),
        (lambda ax: ax.axvline(0.5), "lwidth 0.05292", "lwidth 0.05292 cap round"),
        (lambda ax: ax.axvline(0.5), "set color", "set hei 1 color"),
        (lambda ax: ax.axvline(0.5), "gsave", "begin rotate 0"),
        (lambda ax: ax.axvspan(0.4, 0.6), " fill LIGHTGRAY", ""),
        (lambda ax: ax.axvspan(0.4, 0.6), "fill LIGHTGRAY", "fill"),
        (lambda ax: ax.axvspan(0.4, 0.6), " nobox", ""),
    ],
    ids=[
        "moved",
        "no-lwidth",
        "fractional-lstyle",
        "extra-option",
        "other-setting",
        "no-gsave",
        "no-fill",
        "fill-without-colour",
        "outlined",
    ],
)
def test_an_edited_guide_drawing_is_kept_raw_with_a_note(build, old, new, tmp_path):
    """A drawing that no longer matches its marker is not half-read."""
    from gleplot.parser.recognizer import parse_gle_figure

    fig, ax = _empty_axes()
    build(ax)
    first = tmp_path / "a.gle"
    fig.savefig_gle(str(first))
    text = first.read_text(encoding="utf-8")
    assert old in text
    edited = text.replace(old, new, 1)
    first.write_text(edited, encoding="utf-8")

    recognized = parse_gle_figure(str(first))
    ax2 = recognized.figure.axes_list[0]
    assert ax2.reflines == [] and ax2.spans == []
    assert any(
        w.startswith("structure:") and "gleplot:guide" in w for w in recognized.warnings
    )
    second = tmp_path / "b.gle"
    recognized.figure.savefig_gle(str(second))
    out = second.read_text(encoding="utf-8")
    assert edited.split("end graph\n", 1)[1].strip() in out


def test_a_hand_written_graphutil_include_is_kept(tmp_path):
    """Without a guide to regenerate it, the include is the user's own."""
    from gleplot.parser.recognizer import parse_gle_figure

    src = tmp_path / "hand.gle"
    src.write_text(
        'size 10 8\ninclude "graphutil.gle"\nbegin graph\n   size 8 6\n'
        "end graph\ngraph_hline 0.5\n",
        encoding="utf-8",
    )
    recognized = parse_gle_figure(str(src))
    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert 'include "graphutil.gle"' in text
    assert "graph_hline 0.5" in text


_LEGACY_GUIDE_FILE = """\
! GLE graphics file
size 20.32 15.24
sub gleplot_vline v lo hi clr$ lw ls label$
   if ls > 0 then
      set color cvtcolor(clr$) lwidth lw lstyle ls
      amove xg(v) yg(ygmin+(ygmax-ygmin)*lo)
      aline xg(v) yg(ygmin+(ygmax-ygmin)*hi)
   end if
end sub
begin graph
   size 17.992 13.3352
   xaxis min 0 max 1
   begin layer 699
      draw gleplot_vline 0.5 0 1 "RED" 0.05292 1 ""
   end layer
end graph
"""


def test_a_gleplot_5_guide_sub_is_kept_as_raw_gle(tmp_path):
    """The old guide subs are no longer read: the sub and its call both stay."""
    src = tmp_path / "old.gle"
    src.write_text(_LEGACY_GUIDE_FILE, encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = glp.open_gle(str(src))
    assert parsed.axes_list[0].reflines == []

    out = tmp_path / "again.gle"
    parsed.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "sub gleplot_vline v lo hi clr$ lw ls label$" in text
    assert 'draw gleplot_vline 0.5 0 1 "RED" 0.05292 1 ""' in text


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
    with the marker stubbed out must equal the snapshot with its
    marker lines deleted -- same ``data`` statements, same dataset indices,
    same sidecars, same everything. If adding a comment had shifted a dataset
    number or a byte of a sidecar, the two sides would not meet.
    """
    monkeypatch.setattr(
        GLEWriter, "guide_marker", classmethod(lambda *a, **k: "@stub"), raising=True
    )
    text, files = rb.emit(name)
    text = re.sub(r"^[ \t]*@stub\n", "", text, flags=re.MULTILINE)

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

"""How guides (axhline/axvline/axhspan/axvspan) are written, and read back.

A ``RefLine``/``Span`` declares its extent along the axis it crosses as an
*axes fraction*. gleplot writes it in one of two plain-GLE forms.

**The dataset form** -- the common case. The fraction is measured against the
axis range gleplot resolved and the guide is written as a literal two-point
dataset (``Axes.materialize_reflines`` / ``materialize_spans``): a
``dN line`` for a line, ``fill dA,dB`` for a band. Drawn inside the graph,
bands with the fills and lines below the data, clipped to the frame.

**The after-graph form** -- only when gleplot has no range for the spanned
axis: the axes carries no data and no limit for it (G14), or the range it
resolved to collapsed and was handed back to the engine (G15,
``Figure._defer_degenerate_range``). A literal dataset would then join GLE's
autoscale and move the frame it was measured against, so the guide is drawn
after ``end graph``, where ``xgmin``/``xgmax``/``ygmin``/``ygmax`` hold the
range GLE chose (``Axes.guide_needs_engine_range``). A line is a call of
``graph_hline``/``graph_vline`` from GLE's include library (``graphutil.gle``)
under its own ``set color ... lwidth ... lstyle``; a band is a ``box`` between
``xg()``/``yg()`` page coordinates. Each is wrapped in ``gsave``/``grestore``
so its style does not leak into the next graph.

GLE constraints that rule out drawing these inside the graph block (verified
on GLE 4.3.10):

* A graph ``draw`` command's arguments are evaluated when GLE parses the line
  (``GLEGraphDrawCommand::createGraphDrawCommand``), before the axis range
  exists, so ``draw graph_hline 2`` -- whose defaults are ``xgmin``/``xgmax``
  -- draws nothing.
* A ``draw`` call carries no colour, line style or width of its own, and a
  ``set`` before ``begin graph`` restyles the axes too, so a guide drawn there
  cannot have its own style.

The cost, confined to these engine-range guides: they draw above the data and
the axes (a band covers the ticks inside the frame), and a line is not clipped
to the frame. ``docs/guides/MATPLOTLIB_MIGRATION.md`` records it.

A labelled after-graph guide gets its legend entry from a data-free ``dN``
line inside the graph (``dN line ... key`` for a line, ``dN keyfill ... key``
for a band), which draws no ink and takes no part in autoscale.

Both forms are preceded by a ``! gleplot:guide`` provenance marker, so a
re-read file recovers a ``RefLine``/``Span`` rather than the plain commands it
was written as. See the block comment on :data:`GUIDE_MARKER_PREFIX` for the
grammar.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "GRAPHUTIL_INCLUDE",
    "GUIDE_MARKER_PREFIX",
    "GUIDE_MARKER_KINDS",
    "GUIDE_MARKER_ORIENTS",
    "GUIDE_MARKER_FIELDS",
    "GUIDE_MARKER_LABEL",
    "fraction_expr",
]

#: The gleinc file whose ``graph_hline``/``graph_vline`` draw after-graph lines.
GRAPHUTIL_INCLUDE = "graphutil.gle"


# -- the provenance marker (G18-lite) ---------------------------------------
#
# The dataset form is a literal two-point dataset
# plus a ``dN line`` / ``fill dA,dB`` command (``Axes.materialize_reflines`` /
# ``materialize_spans``). Nothing in those bytes says "this is a guide", so
# until G18-lite every ``.gle`` re-import silently demoted a RefLine/Span to
# the LineSeries/FillSeries it had materialized into.
#
# A **comment** closes that with zero rendering impact by construction (GLE
# never reads past ``!``), so the emission stays additive to the byte:
# sidecars, dataset indices and every visible command are what they always
# were.
#
# Grammar -- one line, immediately above the guide's own ``data`` statement
# (dataset form) or the ``gsave`` that opens its drawing (after-graph form)::
#
#     ! gleplot:guide refline v value 1.5 extent 0,1
#     ! gleplot:guide span v range 0.5,1 extent 0.2,0.6 label "band"
#
# Keyword-tagged and GLE-lexable: the recognizer runs the same tokenizer and
# the same ``_collect_value`` / ``_string_value`` helpers it uses on real
# statements, so an escaped quote needs no bespoke handling here.
#
# **The pair separator is a comma, and that is load-bearing.** GLE's lexer
# reads a sign as an operator, so two space-separated numbers whose second is
# negative are one expression to ``_collect_value``: ``range -4 -3`` collects
# as -7, not as (-4, -3). A comma is not a value operator, so it ends the
# expression -- and it is GLE's own separator for a pair (``d1=c1,c2``,
# ``fill dA,dB``), so the marker reads like the script around it. No space
# inside the pair, for the same reason gleplot writes none in a ``bar``
# comma-list.
#
# **The marker carries the model residue and nothing else.** Everything a
# visible command already states unambiguously is read back from that command,
# so there is exactly one source of truth per field:
#
#   * colour / linestyle / linewidth -> the ``dN line ...`` / ``fill ...``
#     command;
#   * a refline's label              -> its ``key "..."`` clause;
#   * the sidecar and its header row -> the ``data`` statement and the
#     ``.dat`` file itself.
#
# What is left is unrecoverable from the script at any price, and is exactly
# what the marker exists to carry:
#
#   * **kind and orientation** -- derivable only from the *shape* of the
#     dataset, which recognition is forbidden to key off (a hand-written
#     two-point line must stay a plain line);
#   * **the coordinate(s)** -- ``value``, or a band's ``range a b``: they live
#     in the ``.dat`` sidecar, not in the script;
#   * **the fractional extent** -- ``extent lo hi`` is an axes fraction, and
#     the emitted rows are that fraction already resolved against the axis
#     range; inverting it would need that range to be recoverable, which for
#     an autoscaled axis it is not;
#   * **a span's label** -- GLE's ``fill dA,dB`` has no ``key`` option, so the
#     dataset form has never had anywhere to put it (the after-graph form has the
#     same gap; see ``GLEWriter.add_span``). Omitted from the marker when
#     empty, so an unlabelled band costs no extra bytes.
#
# A span's ``alpha`` is deliberately NOT carried: it is folded into the
# emitted colour by ``colors.apply_alpha`` and comes back folded (alpha 1.0
# over an ``rgba255(...)`` colour text), exactly as a hand-written fill does
# and exactly as the after-graph form does. Carrying it would mean carrying the
# unfolded colour with it -- two sources of truth for one visible token.
#
# On the after-graph form the drawing repeats the coordinates, and the
# colour, width and style come from its ``set`` line or ``box ... fill``. The
# recognizer accepts the drawing only when it is exactly what the writer would
# write from the marker and those values, so the two cannot disagree.

#: Prefix of the dataset-form provenance-marker comment. Distinct from the
#: metadata block's ``! gleplot: key = value`` lines (no space after the
#: colon, and a keyword rather than a key) and emitted nowhere else.
GUIDE_MARKER_PREFIX = "! gleplot:guide"

#: The model kinds a marker can name.
GUIDE_MARKER_KINDS: Tuple[str, ...] = ("refline", "span")

#: The orientations a marker can name.
GUIDE_MARKER_ORIENTS: Tuple[str, ...] = ("v", "h")

#: ``kind -> ((keyword, arity), ...)`` for the required numeric fields, in
#: emission order. The recognizer accepts them in any order but requires all
#: of them: a marker missing one describes nothing it could rebuild.
GUIDE_MARKER_FIELDS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "refline": (("value", 1), ("extent", 2)),
    "span": (("range", 2), ("extent", 2)),
}

#: The optional trailing string field: a band's legend label, and on the
#: after-graph form any guide's (its legend entry is a separate line).
GUIDE_MARKER_LABEL = "label"


def fraction_expr(axis: str, fraction: str) -> str:
    """The data coordinate at ``fraction`` of GLE's own ``axis`` range.

    ``axis`` is ``"x"`` or ``"y"`` and ``fraction`` the number as written.
    ``0`` and ``1`` are the range ends themselves. No spaces: a call argument
    ends at whitespace.
    """
    if fraction == "0":
        return f"{axis}gmin"
    if fraction == "1":
        return f"{axis}gmax"
    return f"{axis}gmin+({axis}gmax-{axis}gmin)*{fraction}"

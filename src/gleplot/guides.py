"""Self-contained GLE subroutines for guides GLE has to range for itself (G17).

A ``RefLine``/``Span`` declares its extent along the axis it crosses as an
*axes fraction*. Turning that into a drawable normally means measuring the
fraction against the axis range gleplot resolved and writing a literal
two-point dataset (``Axes.materialize_reflines`` / ``materialize_spans``).
That only works when gleplot HAS a range for the spanned axis. It does not
when

* the axes carries no data and no explicit limit for that axis (G14), or
* the range it resolved to collapsed to a single value and was handed back to
  the engine (G15, ``Figure._defer_degenerate_range``).

In both cases GLE picks the range *after* the script is written, so a literal
dataset is guesswork -- and, worse, a guessing dataset joins the engine's own
autoscale and moves the very frame it was guessing at (measured: a guide
declaring 100 % of the frame covered 14.3 % of it).

For exactly those guides gleplot emits a graph-block ``draw`` of the
subroutines below instead. Inside a ``draw``, GLE exposes the range it chose
as ``xgmin``/``xgmax``/``ygmin``/``ygmax`` and the data->page maps ``xg()``/
``yg()`` (manual, graph module: "the subroutine can use the functions xg(),
yg(), and variables xgmin, ygmin, etc."), so the fraction is measured against
the frame the reader actually sees and the guide contributes nothing to
choosing it. A guide whose spanned axis *does* resolve keeps the literal
dataset emission, byte for byte -- see ``Axes.guide_needs_engine_range``.

Conventions this module fixes
-----------------------------

**Layers.** A bare ``draw`` lands on top of everything (GLE's
``src/gle/graph.h``: ``DRAW_COMMAND`` shares layer 700 with lines and markers,
and draw commands are drawn last within a layer). Today's stacking -- bands
behind the fills, guide lines above the axis but below the data -- is
reproduced exactly by wrapping each call in its own layer just under GLE's
own: :data:`SPAN_LAYER` (349) sits below ``FILL``/``BAR`` (350),
:data:`REFLINE_LAYER` (699) below ``LINE``/``MARKER`` (700) and above
``AXIS`` (500).

**Colours are strings.** A GLE colour name is a parser-level constant, not a
value a sub parameter can carry: ``draw s orange`` passes the *variable*
``orange`` (undefined -> 0 -> black). The colour therefore travels as a
string and is converted inside the sub with GLE's ``cvtcolor()``, which
accepts both a name (``"BLACK"``) and a colour expression
(``"rgba255(255,165,0,89)"``) -- verified against GLE 4.3.10 to render
identically to the literal form, alpha included.

**``ls = 0`` means "no line".** ``linestyle='none'`` on a guide is a real
state (the dataset form emits a dataset that draws nothing). Zero is GLE's
own "no style set" sentinel (``graph2.cpp``: ``dp[dn]->lstyle[0] != 0``), so
the sub draws nothing for it and the declaration still round-trips.

**``label$`` is carried, not drawn.** A ``draw`` owns no dataset, so it
cannot carry ``key``; a labelled *refline* gets its legend entry from a
separate data-free ``dN ... key "..."`` bridge (which contributes no ink and
no autoscale -- probe-verified). The parameter exists so that every field of
the model is recoverable from the call line alone, which is what lets the
recognizer key off the literal sub name and nothing else. Spans keep the
legend behaviour the fill form has always had: none.

Like :mod:`gleplot.palettes`, the sub text is a pure function of its name, so
the recognizer can drop ``sub gleplot_*`` bodies wholesale and regenerate them
canonically -- which is what keeps the writer -> parse -> writer fixed point
byte-identical.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

__all__ = [
    "REFLINE_LAYER",
    "SPAN_LAYER",
    "GUIDE_SUB_NAMES",
    "guide_sub_name",
    "guide_sub_text",
    "guide_sub_texts",
    "GUIDE_CALL_KINDS",
]


#: Graph layer for a ``Span`` draw call -- just under GLE's ``FILL``/``BAR``
#: (350), i.e. behind every fill, exactly where the materialized band sat.
SPAN_LAYER = 349

#: Graph layer for a ``RefLine`` draw call -- just under GLE's
#: ``LINE``/``MARKER`` (700) and above ``AXIS`` (500), i.e. above the axis but
#: below every data series, exactly where the materialized guide line sat.
REFLINE_LAYER = 699


def guide_sub_name(kind: str, orient: str) -> str:
    """``gleplot_<v|h><line|span>`` for a guide kind and orientation."""
    stem = "line" if kind == "refline" else "span"
    return f"gleplot_{orient}{stem}"


#: Every sub name this module can emit, and what each maps back to:
#: ``call name -> (model kind, orientation)``. The recognizer keys off these
#: literal names and never off the shape of the call, so a hand-written
#: two-point line can never be mistaken for a guide.
GUIDE_CALL_KINDS: Dict[str, Tuple[str, str]] = {
    "gleplot_hline": ("refline", "h"),
    "gleplot_hspan": ("span", "h"),
    "gleplot_vline": ("refline", "v"),
    "gleplot_vspan": ("span", "v"),
}

#: The sub names, in the deterministic order :func:`guide_sub_texts` emits.
GUIDE_SUB_NAMES: Tuple[str, ...] = tuple(sorted(GUIDE_CALL_KINDS))


# The two fraction->data expressions, written without spaces: GLE's expression
# parser treats a space as a token separator inside a command's argument list,
# so ``ygmin + (ygmax-ygmin)*lo`` would be read as several arguments.
_Y_FRAC = "ygmin+(ygmax-ygmin)*{}"
_X_FRAC = "xgmin+(xgmax-xgmin)*{}"


_SUB_BODIES: Dict[str, List[str]] = {
    "gleplot_vline": [
        "sub gleplot_vline v lo hi clr$ lw ls label$",
        "   ! Vertical guide at data x = v, spanning the fraction lo..hi of the",
        "   ! range GLE chose for this block. ls = 0 is linestyle 'none'.",
        "   ! label$ is carried for round-trip recovery; the legend entry, if",
        "   ! any, is a separate data-free 'dN ... key' line. See guides.py.",
        "   if ls > 0 then",
        "      gsave",
        "      set color cvtcolor(clr$) lwidth lw lstyle ls",
        f"      amove xg(v) yg({_Y_FRAC.format('lo')})",
        f"      aline xg(v) yg({_Y_FRAC.format('hi')})",
        "      grestore",
        "   end if",
        "end sub",
    ],
    "gleplot_hline": [
        "sub gleplot_hline v lo hi clr$ lw ls label$",
        "   ! Horizontal guide at data y = v, spanning the fraction lo..hi of",
        "   ! the range GLE chose for this block. See gleplot_vline.",
        "   if ls > 0 then",
        "      gsave",
        "      set color cvtcolor(clr$) lwidth lw lstyle ls",
        f"      amove xg({_X_FRAC.format('lo')}) yg(v)",
        f"      aline xg({_X_FRAC.format('hi')}) yg(v)",
        "      grestore",
        "   end if",
        "end sub",
    ],
    "gleplot_vspan": [
        "sub gleplot_vspan a b lo hi clr$ label$",
        "   ! Shaded band between data x = a and x = b, spanning the fraction",
        "   ! lo..hi of the range GLE chose for this block. 'nobox' keeps the",
        "   ! band outline-free, like the 'fill dA,dB' form it stands in for.",
        "   gsave",
        f"   local y0 = yg({_Y_FRAC.format('lo')})",
        f"   local y1 = yg({_Y_FRAC.format('hi')})",
        "   amove xg(a) y0",
        "   box xg(b)-xg(a) y1-y0 fill (cvtcolor(clr$)) nobox",
        "   grestore",
        "end sub",
    ],
    "gleplot_hspan": [
        "sub gleplot_hspan a b lo hi clr$ label$",
        "   ! Shaded band between data y = a and y = b, spanning the fraction",
        "   ! lo..hi of the range GLE chose for this block. See gleplot_vspan.",
        "   gsave",
        f"   local x0 = xg({_X_FRAC.format('lo')})",
        f"   local x1 = xg({_X_FRAC.format('hi')})",
        "   amove x0 yg(a)",
        "   box x1-x0 yg(b)-yg(a) fill (cvtcolor(clr$)) nobox",
        "   grestore",
        "end sub",
    ],
}


def guide_sub_text(name: str) -> str:
    """Canonical ``sub <name> ... end sub`` text for one guide sub."""
    return "\n".join(_SUB_BODIES[name])


def guide_sub_texts(names: Sequence[str]) -> List[str]:
    """The requested guide subs' texts, deduplicated and name-sorted.

    Deterministic in the set of names, never in the order they were
    discovered, so two writes of the same figure emit the same bytes.
    """
    return [guide_sub_text(n) for n in sorted(set(names))]

"""Semantic recognizer: a parsed ``.gle`` document -> a gleplot Figure/Axes model.

This is the inverse of :mod:`gleplot.writer` (the "writer dialect"). It takes
GLE source that gleplot itself wrote -- or a tolerantly-close hand-written
variant of it -- and reconstructs the :class:`~gleplot.figure.Figure` object
model, so ``.gle`` can serve as the editor's native save format.

Public API
----------
- :func:`parse_gle_figure` (path or text) -> :class:`RecognizedFigure`
- :func:`gleplot.open_gle` (registered as a convenience wrapper)

Prime invariant
---------------
For any figure gleplot's writer produced::

    text1 = fig.savefig_gle(path)
    fig2  = parse_gle_figure(path)
    text2 = fig2.savefig_gle(path2)   # same data_prefix recovered

``text2`` is byte-identical to ``text1``, and the regenerated ``.dat`` sidecars
are byte-identical too. ``fig2.to_dict()`` equals ``fig.to_dict()`` up to the
DOCUMENTED NORMALIZATIONS below.

Documented normalizations (``to_dict`` differences that are intentional/lossless
for rendering, applied by the test-side ``normalize()`` helper)
---------------------------------------------------------------------------
1. **Legend "explicit True" -> None (auto).** The writer emits ``key pos P``
   for both an explicit ``legend(loc=...)`` (``legend_on=True``) and the
   auto case (``legend_on=None`` with labels present). It is impossible to tell
   them apart from the emitted GLE, so a recovered ``key pos P`` with any
   labeled series becomes ``legend_on=None`` (auto). Rendering is identical.
2. **Scatter vs. line-with-linestyle-none.** ``ax.plot(..., marker=..., linestyle='none')``
   is stored as a *scatter* by the object model, and the writer emits the
   marker-only ``dN marker M msize S color C`` form. The recognizer classifies
   a marker-only (no ``line`` token) dataset as a scatter with
   ``linestyle='none'`` -- matching the object model exactly.
3. **subplots_adjust survives as geometry, not as fractions.** The layout
   helper bakes ``subplots_adjust`` overrides into ``amove``/``size`` cm
   geometry, and the fractions themselves are not uniquely invertible, so a
   recovered figure still comes back with an empty ``_subplot_adjust``. The
   *layout* nevertheless round-trips byte-identically, whatever spacing was
   used, because every graph block's rect is recovered per-axes into
   :attr:`Axes.placement` (#13) and re-emitted verbatim -- the rects are the
   model, the fractions were only the helper's input. This retires the former
   documented loss (a non-default ``subplots_adjust`` re-saving with DEFAULT
   spacing) and with it the fixed-point test's exemption set.
4. **global_data_counter.** ``to_dict`` records the process-global
   ``data_N.dat`` counter. The recognizer cannot know the original session's
   counter, so it derives the counter state from the recovered sidecar names
   (``data_prefix`` + ``_local_data_counter``) and leaves the module global as
   found. This never affects GLE bytes (data-file names are stored verbatim).
5. **Numeric-noise snapping.** Values recovered from GLE cm units are mapped
   back through the inverse unit functions (``*_cm_to_pt`` etc.), which snap to
   12 significant digits. The forward writer path snaps identically, so the
   values match.
6. **Axis limits.** The writer always emits ``xaxis min/max`` from the
   (possibly data-derived) limits. On parse those become explicit ``xmin/xmax``.
   If the original figure left limits ``None`` (data-derived at write time),
   the recovered figure has them explicit instead -- but they equal the derived
   values, so re-save is byte-identical. (A ``to_dict`` difference the test
   normalizes by re-deriving.)
7. **Smoothing (hand-written only).** Line datasets recover their smoothing
   exactly: SPEC 14.7's per-series ``smooth_mode``
   (``none``/``smooth``/``smoothm``) and ``svg_smooth`` iterations are read
   off the ``dN`` line, so mixed smoothing across a figure round-trips. Two
   normalizations remain. (a) GLE's ``dn`` keyword loop is a left-to-right
   state machine in which ``svg_smooth`` clears ``smooth``/``smoothm``, so
   ``d1 smooth svg_smooth 2`` draws exactly what ``d1 svg_smooth 2`` draws;
   the recognizer replays that state machine and re-emits the canonical
   ``svg_smooth 2`` without the dead token (an inert token removed, not a
   behaviour changed), and ``svg_smooth 0`` recovers as ``1`` because GLE
   itself coerces it. (b) ``graph.smooth_curves`` is still inferred from the
   line datasets, because it is what the kinds *without* a per-series field
   (error bars, file references) follow; a mixed figure sets it ``True`` and
   warns, and a smoothing clause on one of those kinds that the inferred
   default cannot reproduce warns rather than disappearing.
8. **Constant / percentage error -> data column (hand-written only).** A
   ``dN ... err 0.5`` (constant) or ``dN ... err 10%`` (percentage) carries no
   error data column; GLE synthesizes the error at draw time. The recognizer
   converts it to a concrete per-point error array on the model (constant:
   value at every point; percentage: ``value/100 * abs(y)`` for vertical error,
   ``* abs(x)`` for horizontal -- matching ``graph2.cpp`` ``getErrorBarData``),
   which re-saves as a real ``.dat`` error column, and warns. This applies to
   a gleplot sidecar only. On a file read in place (any hand-written ``data``
   reference) or one that cannot be loaded, the original ``dN`` line is kept
   in the axes passthrough instead, its ``data`` statement is kept (see #14)
   and a ``data:`` warning is emitted.
9. **Axis-remainder passthrough (hand-written only).** Unrecognized ``xaxis``/
   ``yaxis``/``y2axis``/``x2axis`` sub-tokens (``hei``/``dticks pi/2``/
   ``y2axis dticks 1``/``format "..."``/...) are peeled off the recognized
   ``min``/``max``/``log``/``nofirst``/``nolast`` (which populate the model) and
   re-emitted as a *supplementary* axis line in the axes passthrough. GLE axis
   lines are cumulative, so the model-emitted axis line + the passthrough line
   together reproduce the intended result. ``STRING`` options keep their quotes.
   Original source spacing is preserved (so ``dticks pi/2`` stays valid). A
   ``structure:`` warning is emitted.
10. **title/key with unsupported options kept raw (hand-written only).** A
    ``title "T" hei 0.6 off`` or ``key pos tr hei 0.3 nobox offset ...``
    carries modifiers that cannot be modeled and for which cumulative
    re-emission would produce a *competing* title/key line. The WHOLE original
    line is preserved in the axes passthrough, the model field is left unset
    (so the writer emits no competing line), and a ``structure:`` warning fires.
11. **Empty-axes no-fabrication.** A parse that yields zero axes but non-empty
    passthrough (e.g. a graph swallowed into an opaque ``begin translate/scale``
    wrapper) re-saves with ONLY the passthrough -- no spurious empty
    ``begin graph ... end graph`` is fabricated. A genuinely empty figure with
    no passthrough keeps the historical default empty graph block.
12. **Programmatic-file warning.** A file using GLE programming constructs
    (top-level ``sub``/``if``/``for``/``while``/``until``/``next``/``else``/
    ``return``) is flagged with a ``programmatic:`` warning -- the syntax parser
    has no control-flow awareness, so editing may restructure such files. Parse
    behavior is unchanged; this is advisory only.

13. **Graph geometry is modelled, never dropped.** Graph-level ``size`` /
    ``scale`` / ``fullsize`` (and the ``amove`` in front of the block) map onto
    the axes as follows -- this replaces the historical behaviour, where they
    were parsed into two fields nothing read and vanished *without warning*,
    so a hand-written ``fullsize`` figure silently re-saved as ``scale auto``:

    * ``amove x y`` + ``size w h`` + ``scale 1 1`` -- the one invertible
      geometry (``scale 1 1`` makes the axis frame fill the graph box) --
      becomes ``Axes.placement``, a frame rect in page cm (SPEC 3.3). The
      writer re-emits exactly those three statements. No warning: modelled.
      This is what every gleplot-written file carries since metadata v2, for
      a lone plot exactly as for a subplot grid, which is what makes gleplot's
      own output a byte-identical fixed point with no exemptions.
    * No geometry at all, or exactly ``scale auto``, means AUTO placement
      ("GLE decides"; ``placement`` stays ``None``). That is how gleplot wrote
      single plots up to metadata v1, and how a hand-written file that says
      nothing about geometry is read. Such a figure re-saves with the explicit
      rect the layout computes for it -- a deliberate one-time geometry change,
      see the migration policy in :mod:`gleplot.parser.metadata`. This parser
      does not resolve auto against the range GLE would have chosen.
    * Anything else real -- ``fullsize``, ``scale h v`` with actual factors, a
      bare ``size`` with no ``scale 1 1``, several statements we do not model
      -- is kept VERBATIM in ``Axes.geometry_passthrough`` and re-emitted in
      the geometry slot (first thing inside ``begin graph``), so such figures
      are a byte-identical fixed point instead of being normalized. A
      ``layout:`` warning reports that the geometry is not editable.
    * An ``amove`` that did not become a placement rect is preserved verbatim
      in ``passthrough_header`` ahead of the block, also with a ``layout:``
      warning -- but only for a SINGLE-graph file. With several graphs the
      ``amove`` positions are modelled (they are what the grid is inferred
      from), so re-emitting them would duplicate every subplot's position.

    Two consequences worth naming. A metadata-v1 single-plot figure whose bare
    ``size`` is exactly the colorbar reserved-width line that release derived
    (``Figure._axes_colorbar_reserved_cm``) is recognized as such and loads as
    auto placement, so it migrates to a v2 rect instead of freezing a legacy
    line in passthrough. And a figure written with
    ``GLEGraphConfig.scale_mode='fullsize'`` comes back with the geometry
    per-axes rather than as the config field (the config is a writer default,
    not per-axes state); the emitted GLE is identical either way.

14. **Bar groups and stacks on gleplot's own file are series; a fill that
    shares their file is not.** A bar or fill on a file gleplot did not
    write (one the metadata's import list does not name) is never loaded,
    so the file is never rewritten: a fill and a plain ``bar dN fill C``
    become :class:`~gleplot.series.FileSeries` references, and any other
    ``bar`` command on it (a ``width``, group, stack, pattern, ...) stays
    raw with every bar on its ``data`` statement. On gleplot's own file,
    ``bar d1,d2 fill c1,c2`` is several :class:`~gleplot.series.BarSeries`
    that share a ``group`` id and are written back as one command.
    ``bar d2 from d1`` is one series whose baseline is ``d1``. A command
    that also carries an unmodelled sub-command (``3d``, ``side``,
    ``style``, ...) stays raw, and so does every bar whose datasets share
    a ``data`` statement with a ``fill`` the recognizer cannot take: that
    fill still needs the author's data line, and rewriting the file for
    the bar would drop the columns it reads. When every dataset a ``data``
    statement declares ends up referenced only by such passthrough text,
    the original ``data`` statement is restored verbatim, ahead of the
    passthrough content that depends on it. When the statement declares a
    mix of modeled and orphaned datasets and reads a file in place, a
    ``data`` statement naming just the orphaned datasets (same file, same
    columns) is added instead; on a gleplot sidecar, which the writer
    rewrites, such a mix is not reconstructed and a ``data:`` warning flags
    it. A one-curve fill (``fill x1,dN``,
    ``fill dN,x2``, ``fill dN``) whose ``data`` statement also declares
    other datasets is left verbatim for the same reason.

Tolerances for hand-written input
---------------------------------
Attribute order within a dataset command may vary; axis lines may be given
cumulatively (multiple ``xaxis`` lines merge); numbers may be expressions
(``2*pi``) resolved via :func:`~gleplot.parser.expr.eval_gle_number`; keywords
are case-insensitive; single-quoted strings and ``;``-joined statements are
accepted; British ``GREY`` colors are accepted. Anything not recognized is
preserved verbatim in the appropriate passthrough bucket (header / trailer /
axes / axes geometry / between one axes and the next) so it re-emits
unchanged. A blank (or comment-only) line separating two post-graph text
clusters, or between ``end graph`` and the first cluster, is
tolerated by :meth:`_Recognizer._try_one_text` (:meth:`_Recognizer._skip_blanks`)
-- the writer itself never emits such a blank line, but a human editing the
file for readability may add one; recognition proceeds exactly as if it were
absent, and re-emission is canonical (no blank line re-inserted).

Warnings taxonomy
-----------------
Every recovered ambiguity or loss is recorded as an
:class:`~gleplot.parser.report.ImportNote` on ``RecognizedFigure.notes``
(GLEstudio plan G4; SPEC 8.1.5 / 10.4) -- category, a human-readable message,
and a ``source_span`` into the original file where one is determinable.
``RecognizedFigure.warnings`` is a *derived* view: ``"category: message"`` for
each note, in order, reproducing exactly the strings this API returned before
notes existed, so it is still the right thing to check with
``any(w.startswith("data:") ...)`` or similar. New code should prefer
``notes`` for anything that wants a category as data or a location.

- ``ImportCategory.METADATA`` (``"metadata: ..."``)     -- forwarded from
  ``parse_metadata``.
- ``ImportCategory.STRUCTURE`` (``"structure: ..."``)   -- forwarded from the
  syntax parser, or a construct this module recognizes but cannot fully model
  (unsupported title/key/axis options, a repeated styling line, a names/places
  mismatch, an unknown colormap palette, a multi-dataset ``bar``/``fill``
  group, a graph nested in a transform wrapper, ...).
- ``ImportCategory.DATA`` (``"data: ..."``)             -- a ``data``
  reference could not be loaded / a column could not be extracted (broken
  series; emitted verbatim on re-save), a dataset redefinition, or a
  constant-error conversion.
- ``ImportCategory.LEGEND`` (``"legend: ..."``)         -- a hand-written
  implicit legend was assumed, or a ``key`` line has unsupported options.
- ``ImportCategory.SMOOTH`` (``"smooth: ..."``)         -- mixed per-series
  smooth flags, or a smoothing clause on a dataset kind with no per-series
  smoothing field (SPEC 14.7).
- ``ImportCategory.LAYOUT`` (``"layout: ..."``)         -- multi-graph grid
  could not be inferred cleanly (n x 1 fallback), share flags were guessed,
  or graph geometry / an ``amove`` was preserved verbatim rather than
  modelled (normalization #13). Geometry is never dropped silently.
- ``ImportCategory.PROGRAMMATIC`` (``"programmatic: ..."``) -- the file uses
  GLE programming constructs (sub/if/for/...); editing may restructure them
  (advisory; parse unchanged).

SPEC 8.1.5 additionally names a v1.1 ``mathtext:`` category (reverse
mathtext translation for imported labels, SPEC 9) with no current emission
site -- not in :class:`~gleplot.parser.report.ImportCategory` yet, since the
taxonomy tracks what is actually emitted.

Source-span coverage
---------------------
``source_span`` is only ever the location the recognizer actually had at the
point it raised the note -- never guessed. Coverage by category:

======================  ==========================================================
Category                Span coverage
======================  ==========================================================
``structure``           Real, usually single-line: almost every site fires from
                        a method that already holds the triggering ``Statement``.
                        A few aggregate over more than one line (a names/places
                        pair split across two statements; a translate/scale
                        wrapper spans its ``begin``..``end``) and use the min/max
                        line of the statements actually responsible.
``data``                Real for every site: the series-build call chain
                        (``_parse_series_command`` -> ``_build_errorbar`` /
                        ``_build_contour_from_cdata`` /
                        ``_load_series``) threads the triggering ``dN``/``bar``/
                        ``fill`` statement's line down to every data-resolution
                        failure raised while building that series.
``legend``              Real for ``key`` line rejections (the statement).
                        The implicit-legend inference is a whole-axes
                        conclusion (no ``key`` statement exists to blame) and
                        uses the owning graph block's ``begin``..``end`` span.
``layout``              Real for a single graph's geometry (min/max line of its
                        ``size``/``scale``/``fullsize`` statements) and its
                        ``amove``. The multi-graph grid-inference fallbacks are
                        a whole-arrangement conclusion; span is the min/max of
                        whatever amove lines the figure does have (``None`` if
                        none do).
``smooth``              ``None`` for the mixed-flags note: that one is a true
                        whole-figure aggregate over every line dataset (across
                        every graph block), and no single line is more
                        responsible than any other. Real for the
                        unmodelled-clause note, which blames the one ``dN``
                        statement that carried the clause.
``programmatic``        Real, single-line: the specific top-level statement
                        whose keyword tripped the guard.
``metadata``            The whole ``! gleplot-meta-begin``..``! gleplot-meta-end``
                        block's span (``parse_metadata`` does not track a
                        per-line origin for its own warnings; the block is the
                        finest location available at the call site).
======================  ==========================================================
"""

from __future__ import annotations

import collections
import copy
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import numpy as np

from ..axes import (
    _GLE_FONT_NAME,
    Axes,
    _function_expression_problem,
    _let_expression_problem,
    _resolve_data_file,
)
from ..colors import _COLOR_EXPR_RE, GLE_PATTERNS, _gle_color_names
from ..config import GLEGraphConfig, GLEMarkerConfig, GLEStyleConfig
from ..dataio import (
    ColumnExtractionError,
    GLEDataLayout,
    classify_data_file,
    extract_columns,
    gle_data_layout,
    resolve_data_reference,
)
from ..figure import Figure, _share_mode
from ..guides import (
    GRAPHUTIL_INCLUDE,
    GUIDE_MARKER_FIELDS,
    GUIDE_MARKER_KINDS,
    GUIDE_MARKER_LABEL,
    GUIDE_MARKER_ORIENTS,
    GUIDE_MARKER_PREFIX,
)
from ..palettes import canonical_cmap, colorbar_cmap, palette_call_name
from ..series import (
    _DATASET_NAME_RE,
    SERIES_CLASSES,
    BarSeries,
    ContourSeries,
    DerivedSeries,
    ErrorbarSeries,
    FileSeries,
    FillSeries,
    FitSeries,
    FunctionSeries,
    HeatmapSeries,
    HistSeries,
    LineSeries,
    PlacedImage,
    RefLine,
    Rug,
    ScatterSeries,
    Series,
    Span,
    TextAnnotation,
)
from ..writer import (
    CDATA_SUB_PREFIX,
    CELLS_MARKER,
    COLOR_INCLUDE,
    COLORBAR_STEP_SCALE,
    CONTOUR_INCLUDE,
    CONTOURF_EXTENDS,
    CONTOURF_MARKER,
    IMAGE_LAYER,
    IMAGE_SUBS,
    MDATA_SUB_PREFIX,
    NAME_QUOTE,
    NODES_MARKER,
    POLAR_GRID_LAYER,
    RUG_EDGES,
    RUGS_INCLUDE,
    GLEWriter,
    KeyOptions,
    _format_data_filename,
    image_sub_name,
    legend_column_breaks,
    legend_corner,
    polar_degree_mark,
    polar_label_decimals,
    polar_ring_step,
    polar_window,
)
from . import metadata as _metadata
from .expr import eval_gle_number
from .lexer import Token, TokenType, tokenize_line
from .report import ImportCategory, ImportNote
from .syntax import (
    BlankOrComment,
    GraphBlock,
    OpaqueBlock,
    SourceLine,
    Statement,
    parse_gle_source,
)
from .tables import (
    ARROW_JOIN_SEPS,
    ARROW_TIP_STYLES,
    FIT_PLACEHOLDER_RE,
    FIT_RESULT_PLACEHOLDERS,
    FIT_ROUTINE_TO_MODEL,
    KEY_ANCHOR_X,
    KEY_ANCHOR_Y,
    KEY_POSITIONS_SHORT_TO_LONG,
    LEGEND_SPACING_TO_KEY,
    LINE_MODES,
    LOG_LABEL_MODES,
    LSTYLE_TO_MATPLOTLIB,
    MARKERS,
    PALETTE_SUB_TO_CMAP,
    text_box_pad_token,
    text_just_to_align,
)
from .units import (
    capsize_cm_to_pt,
    cm_to_inches,
    fontsize_cm_to_pt,
    fontsize_pt_to_cm,
    inches_to_cm,
    linewidth_cm_to_pt,
)

__all__ = ["ImportCategory", "ImportNote", "RecognizedFigure", "parse_gle_figure"]


_DATASET_RE = re.compile(r"^d\d+$", re.IGNORECASE)

#: ``let dK = (dJ-a)/(b-a)`` (or ``(dJ-a)*0``): a per-point colour's values
#: mapped onto the colormap (``GLEWriter._add_coloured_scatter``). A negative
#: ``a`` is written ``+|a|``. Groups: target, source, operator, ``|a|``, ``b``.
_CDATA_LET_RE = re.compile(
    r"^\s*let\s+(d\d+)\s*=\s*\((d\d+)([+-])(\d[\w.+-]*)\)"
    r"(?:/\((-?\d[\w.+-]*)\3\4\)|\*0)\s*$",
    re.IGNORECASE,
)

#: ``define marker gleplot_X gleplot_X`` (lower-cased): the line that makes a
#: generated per-point-size sub a marker (``writer.mdata_sub_text``).
_GLEPLOT_DEFINE_MARKER_RE = re.compile(r"^define\s+marker\s+(gleplot_\w+)\s+\1$")
# The statement a contourf band sub starts with when it is also a colorbar's
# palette (writer.GLEWriter.add_contourf_sub), lower-cased.
_CONTOURF_RESCALE_RE = re.compile(r"^z = (\S+)\*\(1-z\)\+(\S+)\*z$")

#: What :meth:`_Recognizer._try_one_text` returns for a polar axes' label
#: call, which the axes regenerates; compared by identity.
_POLAR_LABELS: Dict[str, Any] = {"polar_labels": True}


#: Every ``bar`` sub-command GLE 4.3.10 accepts that gleplot has no model
#: for. Enumerated from ``do_bar`` in ``graph.cpp``, whose ``kw(...)`` chain
#: is exhaustive (anything else is "unrecognised bar sub command"):
#:
#:     DIST WIDTH 3D NOTOP HORIZ LSTYLE STYLE LWIDTH FROM
#:     COLOR SIDE TOP FILL PATTERN BACKGROUND
#:
#: ``fill`` and ``width`` are the original fields. ``color`` / ``lstyle`` /
#: ``lwidth`` are the edge, ``horiz`` is :meth:`~gleplot.Axes.barh`,
#: ``from`` is the stack, ``dist`` is the group spacing, and ``pattern`` /
#: ``background`` are the hatch. What is left changes the drawing in a way
#: the series cannot carry (3-D extrusion, an unmodelled style), so a
#: command that names one stays raw.
_BAR_UNMODELLED_OPTIONS = frozenset(
    {
        "3d",
        "notop",
        "side",
        "top",
        "style",
    }
)

#: Keywords ``do_bar`` accepts, modelled or not. A token that is not in
#: this set is "unrecognised bar sub command" and the command stays raw.
_BAR_KEYWORDS = frozenset(
    {
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
)


def _collect_bar_list(
    toks: List[Token], start: int, read
) -> Tuple[Optional[list], int]:
    """A comma-separated list starting at ``start``.

    GLE keeps the commas inside one token (``red,blue``). The gleplot lexer
    splits them, so a list is value, comma, value. ``read(toks, i)`` returns
    ``(item or None, next_index)``. ``(None, start)`` when nothing is there.
    """
    item, nxt = read(toks, start)
    if item is None:
        return None, start
    items = [item]
    while nxt < len(toks) and toks[nxt].type is TokenType.OP and toks[nxt].value == ",":
        item, nxt2 = read(toks, nxt + 1)
        if item is None:
            break
        items.append(item)
        nxt = nxt2
    return items, nxt


def _bar_dataset_token(toks: List[Token], start: int) -> Tuple[Optional[str], int]:
    if start < len(toks) and _DATASET_RE.match(toks[start].value):
        return toks[start].value.lower(), start + 1
    return None, start


def _bar_color_token(toks: List[Token], start: int) -> Tuple[Optional[str], int]:
    return _collect_color(toks, start)


def _scan_bar_command(toks: List[Token]) -> dict:
    """The modelled fields of one ``bar`` command, plus why it cannot be one.

    ``fills`` / ``edges`` / ``patterns`` / ``backgrounds`` are ``None`` when
    the keyword was absent, and the authored list otherwise (a longer fill
    or edge list than the dataset count is stored and re-emitted; GLE draws
    only the first of a one-dataset command).
    ``unmodelled`` names every keyword that has no field. ``bad_value`` is
    a width, dist, or lwidth the expression evaluator could not read.
    """
    scanned: Dict[str, Any] = {
        "datasets": [],
        "from_names": [],
        "fills": None,
        "edges": None,
        "patterns": None,
        "backgrounds": None,
        "width": None,
        "dist": None,
        "linewidth_cm": None,
        "linestyle": None,
        "lstyle": None,
        "horiz": False,
        "unmodelled": [],
        "bad_value": False,
    }
    i = 1
    m = len(toks)
    while i < m:
        tok = toks[i]
        if tok.type is TokenType.OP and tok.value == ",":
            i += 1
            continue
        if tok.type is TokenType.WORD and _DATASET_RE.match(tok.value):
            scanned["datasets"].append(tok.value.lower())
            i += 1
            continue
        break

    def reject(word: str) -> None:
        if word not in scanned["unmodelled"]:
            scanned["unmodelled"].append(word)

    while i < m:
        tok = toks[i]
        word = tok.value.lower()
        if tok.type is TokenType.OP:
            i += 1
            continue
        if word == "horiz":
            scanned["horiz"] = True
            i += 1
            continue
        if word == "notop":
            reject(word)
            i += 1
            continue
        if word == "3d":
            reject(word)
            i += 1
            for _ in range(2):
                val, nxt = _collect_value(toks, i)
                if val is None:
                    break
                i = nxt
            continue
        if word in ("width", "dist", "lwidth"):
            val, nxt = _collect_value(toks, i + 1)
            if val is None:
                scanned["bad_value"] = True
                reject(word)
                i += 1
                continue
            if word == "width":
                scanned["width"] = val
            elif word == "dist":
                scanned["dist"] = val
            else:
                scanned["linewidth_cm"] = val
            i = nxt
            continue
        if word == "lstyle":
            text, nxt = _collect_bar_list(toks, i + 1, _bar_lstyle_piece)
            if not text:
                scanned["bad_value"] = True
                reject(word)
                i += 1
                continue
            joined = ",".join(text)
            mapped = None
            if len(text) == 1:
                try:
                    mapped = LSTYLE_TO_MATPLOTLIB.get(int(text[0]))
                except (TypeError, ValueError):
                    mapped = None
            if mapped:
                scanned["linestyle"] = mapped
            else:
                scanned["lstyle"] = joined
            i = nxt
            continue
        if word == "from":
            names, nxt = _collect_bar_list(toks, i + 1, _bar_dataset_token)
            if not names:
                scanned["bad_value"] = True
                reject(word)
                i += 1
                continue
            scanned["from_names"] = names
            i = nxt
            continue
        if word in ("fill", "color"):
            items, nxt = _collect_bar_list(toks, i + 1, _bar_color_token)
            if not items:
                scanned["bad_value"] = True
                reject(word)
                i += 1
                continue
            scanned["fills" if word == "fill" else "edges"] = items
            i = nxt
            continue
        if word in ("pattern", "background"):
            items, nxt = _collect_bar_list(toks, i + 1, _bar_color_token)
            if not items or (
                word == "pattern"
                and any(item.upper() not in GLE_PATTERNS for item in items)
            ):
                # An expression or a name GLE does not ship: no model.
                reject(word)
                i = nxt if items else i + 1
                continue
            scanned[word + "s"] = items
            i = nxt
            continue
        if word in _BAR_UNMODELLED_OPTIONS or word not in _BAR_KEYWORDS:
            reject(word)
            i += 1
            if word == "style" and i < m and toks[i].value.lower() not in _BAR_KEYWORDS:
                i += 1
                continue
            if word in ("side", "top"):
                _items, nxt = _collect_bar_list(toks, i, _bar_color_token)
                if _items:
                    i = nxt
            continue
        i += 1
    scanned["patterns_fit"] = _bar_patterns_fit(scanned)
    return scanned


def _bar_patterns_fit(scanned: dict) -> bool:
    """Whether ``pattern`` / ``background`` map onto the datasets one each.

    The writer emits one pattern per dataset, and a background only under
    a pattern: GLE gives a ``background`` with no ``pattern`` a ``SHADE``
    fill. A pattern with no ``fill`` token of its own is drawn in GLE's
    default ink, which the series has no token for.
    """
    patterns = scanned["patterns"] or []
    backgrounds = scanned["backgrounds"] or []
    fills = scanned["fills"] or []
    return (
        len(backgrounds) <= len(patterns) <= min(len(fills), len(scanned["datasets"]))
    )


def _bar_lstyle_piece(toks: List[Token], start: int) -> Tuple[Optional[str], int]:
    """One piece of an ``lstyle`` value. A keyword ends the value."""
    if start >= len(toks):
        return None, start
    tok = toks[start]
    if tok.type is TokenType.WORD and tok.value.lower() in _BAR_KEYWORDS:
        return None, start
    return tok.value, start + 1


def _bar_scan_is_plain(scanned: dict) -> bool:
    """A single dataset, a fill, and at most a width.

    That is the shape :class:`~gleplot.series.FileSeries` can still carry
    when the file is not loaded (with no width), and the shape a histogram ``bar dK fill``
    already owns. Anything else on an unreadable file stays raw.
    """
    fills = scanned["fills"]
    return (
        len(scanned["datasets"]) == 1
        and not scanned["from_names"]
        and not scanned["horiz"]
        and scanned["dist"] is None
        and scanned["linestyle"] is None
        and scanned["lstyle"] is None
        and scanned["linewidth_cm"] is None
        and not scanned["edges"]
        and not scanned["patterns"]
        and not scanned["backgrounds"]
        and (fills is None or len(fills) == 1)
        and not scanned["unmodelled"]
        and not scanned["bad_value"]
    )


@dataclass
class RecognizedFigure:
    """Result of :func:`parse_gle_figure`.

    Attributes
    ----------
    figure : Figure
        The reconstructed object model.
    notes : tuple of ImportNote
        Structured recovery notes: category, message, and a source span where
        one can be determined. ``warnings`` is derived from these.
    warnings : list of str
        Human-readable ``"category: message"`` strings, one per note, in the
        same order. Computed on each access from :attr:`notes`.
    """

    figure: Figure
    notes: Tuple[ImportNote, ...] = field(default_factory=tuple)

    @property
    def warnings(self) -> List[str]:
        return [note.rendered for note in self.notes]


# --------------------------------------------------------------------------- #
# Token-stream helpers
# --------------------------------------------------------------------------- #


def _words_and_values(stmt: Statement) -> List[Token]:
    """Tokens of a statement, dropping comments."""
    return [t for t in stmt.tokens if t.type is not TokenType.COMMENT]


#: Subs earlier gleplot versions wrote, for parts GLE's include library now
#: draws or that gleplot no longer provides (pie, box plot). No longer
#: written or read: a file that defines them keeps them as raw GLE,
#: with the calls that use them.
_LEGACY_SUBS = frozenset(
    {
        "gleplot_hline",
        "gleplot_hspan",
        "gleplot_vline",
        "gleplot_vspan",
        "gleplot_xrug",
        "gleplot_yrug",
        "gleplot_colorbar_v",
        "gleplot_colorbar_h",
        "gleplot_contour_labels",
        "gleplot_wedge",
        "gleplot_box",
        "gleplot_box_flier",
        "gleplot_box_mean",
    }
)


def _guide_marker_text(node) -> Optional[str]:
    """The ``! gleplot:guide ...`` text of ``node``, or ``None`` (G18-lite).

    Matched on the literal prefix and nothing else -- a comment-only line is
    the only place it can appear, and gleplot is the only thing that writes
    one, so this can never claim a user's comment.
    """
    if not isinstance(node, BlankOrComment):
        return None
    for tok in node.statement.tokens:
        if tok.type is TokenType.COMMENT and tok.value.startswith(GUIDE_MARKER_PREFIX):
            return tok.value
    return None


def _first_statement_of(source_line) -> Statement:
    """Build a throwaway :class:`Statement` from a raw block inner line.

    Opaque-block inner lines are stored as bare :class:`SourceLine`s (never
    tokenized into statements). The contour/fitz block parsers need their
    tokens, so this tokenizes one line's text into a Statement wrapper.
    """
    return Statement(
        tokens=tokenize_line(source_line.text),
        raw=source_line.text,
        line_no=source_line.line_no,
        sub_index=0,
        source_line=source_line,
    )


def _meaningful_statements(lines) -> List[Statement]:
    """Non-blank statements tokenized from opaque-block inner lines."""
    out = []
    for src in lines:
        stmt = _first_statement_of(src)
        if not stmt.is_blank:
            out.append(stmt)
    return out


def _plain_write_string(stmt: Optional[Statement]) -> Optional[str]:
    """The string of a bare ``write "T"``, or ``None`` if it is not one."""
    if stmt is None:
        return None
    toks = _words_and_values(stmt)
    if toks and toks[0].type is TokenType.WORD and toks[0].value.lower() == "write":
        return _string_expr_value(toks[1:])
    return None


def _is_end_named(stmt: Statement, name: str) -> bool:
    """True for exactly ``end <name>`` and nothing else."""
    toks = _words_and_values(stmt)
    return (
        len(toks) == 2
        and toks[0].type is TokenType.WORD
        and toks[0].value.lower() == "end"
        and toks[1].type is TokenType.WORD
        and toks[1].value.lower() == name
    )


def _plain_rotate_angle(stmt: Statement) -> Optional[float]:
    """Angle of ``begin rotate <number>``.

    A single numeric literal, with an optional leading minus. The lexer keeps
    that minus as its own token (``begin rotate -15``), so both shapes are
    accepted. An expression (``2*pi``) is left unrecognized so re-save does
    not rewrite it as a decimal.
    """
    toks = _words_and_values(stmt)
    if len(toks) < 3 or len(toks) > 4:
        return None
    if toks[0].value.lower() != "begin" or toks[1].value.lower() != "rotate":
        return None
    rest = toks[2:]
    if (
        len(rest) == 2
        and rest[0].type is TokenType.OP
        and rest[0].value == "-"
        and rest[1].type is TokenType.NUMBER
    ):
        val = _num(rest[1])
        return None if val is None else -val
    if len(rest) == 1 and rest[0].type is TokenType.NUMBER:
        return _num(rest[0])
    return None


def _text_box_head(stmt: Statement) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """``(fill, name)`` of ``begin box [fill C] add P nobox [name N]``, or ``None``.

    These are the only boxes the writer emits around a text: a background
    (``fill``), an annotation's arrow anchor (``name``), or both. ``P`` has
    to be the pad token it writes (:func:`text_box_pad_token`). An outline
    (no ``nobox``), a different pad, rounded corners, a box with neither
    ``fill`` nor ``name``, or a different keyword order stays unrecognized
    so a hand-written box is not rewritten.
    """
    toks = _words_and_values(stmt)
    if len(toks) < 5:
        return None
    if toks[0].value.lower() != "begin" or toks[1].value.lower() != "box":
        return None
    color = None
    nxt = 2
    if toks[2].value.lower() == "fill":
        color, nxt = _collect_color(toks, 3)
        if color is None:
            return None
    if nxt + 2 >= len(toks):
        return None
    if toks[nxt].value.lower() != "add":
        return None
    if toks[nxt + 1].type is not TokenType.NUMBER:
        return None
    if toks[nxt + 1].value != text_box_pad_token():
        return None
    if toks[nxt + 2].value.lower() != "nobox":
        return None
    nxt += 3
    name = None
    if nxt < len(toks):
        if (
            nxt + 2 != len(toks)
            or toks[nxt].value.lower() != "name"
            or toks[nxt + 1].type is not TokenType.WORD
        ):
            return None
        name = toks[nxt + 1].value
    if color is None and name is None:
        return None
    return color, name


def _rotate_or_box_body(
    lines,
) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    """Inner lines of ``begin rotate``: a write, or one box around it.

    Returns ``(text, box_color, box_name)``; the last two are ``None`` for a
    bare write (see :func:`_text_box_head`).
    """
    stmts = _meaningful_statements(lines)
    if len(stmts) == 1:
        text = _plain_write_string(stmts[0])
        if text is None:
            return None
        return text, None, None
    if len(stmts) != 3:
        return None
    head = _text_box_head(stmts[0])
    text = _plain_write_string(stmts[1])
    if head is None or text is None or not _is_end_named(stmts[2], "box"):
        return None
    return text, head[0], head[1]


def _boxed_write(
    block: OpaqueBlock,
) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    """A top-level ``begin box`` whose body is exactly one ``write``.

    Returns ``(text, box_color, box_name)`` as :func:`_rotate_or_box_body`.
    """
    if block.end is None:
        return None
    head = _text_box_head(block.begin)
    if head is None or not _is_end_named(block.end, "box"):
        return None
    stmts = _meaningful_statements(block.inner_lines)
    if len(stmts) != 1:
        return None
    text = _plain_write_string(stmts[0])
    if text is None:
        return None
    return text, head[0], head[1]


def _as_float(value, default: float) -> float:
    """Best-effort float from a recovered named-argument value."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_value(tok: Token) -> str:
    """Unwrap a STRING token's value.

    Strips the surrounding quotes, then undoes the doubled quote GLE 4.3.10
    embeds a quote with. A backslash is text, as it is to GLE.
    """
    v = tok.value
    q = tok.quote
    if q and len(v) >= 2 and v[0] == q:
        inner = v[1:-1] if v.endswith(q) else v[1:]
    else:
        inner = v
    if q:
        inner = inner.replace(q + q, q)
    return inner


#: A quoted string in a ``! gleplot:guide`` marker, where a backslash
#: escapes the character after it (:meth:`GLEWriter.guide_marker`).
_MARKER_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _string_expr_value(toks: List[Token]) -> Optional[str]:
    """The text of a GLE string expression, or ``None`` if it is not one.

    Reads one quoted string, or the ``"a"+chr$(34)+"b"`` form the writer
    gives text holding both kinds of quote, since GLE's expression parser
    rejects an escaped or doubled quote. Any other expression, including a
    hand-written concatenation, is ``None``, so it stays as written.
    """
    if len(toks) == 1 and toks[0].type is TokenType.STRING:
        return _string_value(toks[0])
    if any(b.start != a.end for a, b in zip(toks, toks[1:])):
        return None
    parts: List[str] = []
    i, n = 0, len(toks)
    while True:
        if i < n and toks[i].type is TokenType.STRING:
            parts.append(_string_value(toks[i]))
            i += 1
        elif (
            i + 3 < n
            and toks[i].value.lower() == "chr$"
            and toks[i + 1].value == "("
            and toks[i + 2].value == "34"
            and toks[i + 3].value == ")"
        ):
            parts.append('"')
            i += 4
        else:
            return None
        if i == n:
            text = "".join(parts)
            source = "".join(t.value for t in toks)
            return text if GLEWriter._gle_string_expr(text) == source else None
        if toks[i].type is not TokenType.OP or toks[i].value != "+":
            return None
        i += 1


def _num(tok: Token) -> Optional[float]:
    """Evaluate a single token as a number (expression-tolerant)."""
    return eval_gle_number([tok])


# Tokens that can appear inside a numeric value expression (so a leading sign
# or ``2*pi`` is collected as one value rather than truncated).
_VALUE_OPS = frozenset({"+", "-", "*", "/", "^", "(", ")"})


def _collect_value(toks: List[Token], start: int) -> Tuple[Optional[float], int]:
    """Collect and evaluate a numeric-value expression starting at ``start``.

    Consumes a maximal run of NUMBER / value-operator / numeric-WORD (``pi``,
    ``e``) tokens so that ``min -1`` and ``min 2*pi`` are read as single
    values. Returns ``(value_or_None, next_index)``. If nothing numeric is
    present, returns ``(None, start)`` (the caller should not advance).
    """
    m = len(toks)
    j = start
    run: List[Token] = []
    depth = 0
    # Track whether the last appended token was an operand (NUMBER / ')' /
    # constant). Two space-separated operands are two separate VALUES, not one
    # expression, so an operand may only follow the start, an operator, or '('.
    last_was_operand = False
    while j < m:
        t = toks[j]
        if t.type is TokenType.NUMBER:
            if last_was_operand:
                break
            run.append(t)
            last_was_operand = True
            j += 1
            continue
        if t.type is TokenType.WORD and t.value.lower() in ("pi", "e"):
            if last_was_operand:
                break
            run.append(t)
            last_was_operand = True
            j += 1
            continue
        if t.type is TokenType.OP and t.value in _VALUE_OPS:
            if t.value == "(":
                if last_was_operand:
                    break  # ``2 (`` -> stop; not a function-call value
                depth += 1
                last_was_operand = False
            elif t.value == ")":
                if depth == 0:
                    break
                depth -= 1
                last_was_operand = True
            else:
                # binary/unary arithmetic operator
                last_was_operand = False
            run.append(t)
            j += 1
            continue
        break
    if not run or depth != 0:
        return None, start
    val = eval_gle_number(run)
    if val is None:
        return None, start
    return val, j


def _oriented(
    lo: Optional[float], hi: Optional[float], negate: bool
) -> Tuple[Optional[float], Optional[float]]:
    """Axis limits as the gleplot model spells them: descending if inverted.

    GLE writes an inverted axis as an ascending range plus ``negate``; the
    model writes it as a descending limit pair, the way matplotlib's
    ``set_ylim(3, 1)`` does. ``negate`` is only recognized on a line that
    also pins both bounds (see ``_parse_axis_line``), so this can always
    express what it was given.
    """
    if negate and lo is not None and hi is not None:
        return (hi, lo)
    return (lo, hi)


#: Page-level ``set`` words recognized onto :class:`GLEStyleConfig` fields.
_PAGE_STATE_FIELDS = {
    "cap": "line_cap",
    "join": "line_join",
    "dashlen": "dashlen",
    "texlabels": "usetex",
}


def _page_state_value(field: str, tok: Token) -> Any:
    """The ``GLEStyleConfig.<field>`` value of a ``set`` argument, or None.

    None leaves the statement raw: a word or length ``GLEStyleConfig``
    rejects, a length written as an expression, or a ``texlabels`` switch
    spelled other than the writer's ``1`` (``0`` is GLE's default, and
    dropping it would lose the line).
    """
    if field == "usetex":
        return True if tok.value == "1" else None
    if field != "dashlen":
        value: Any = tok.value.lower()
    elif tok.type is TokenType.NUMBER:
        value = float(tok.value)
    else:
        return None
    try:
        GLEStyleConfig(**{field: value})
    except ValueError:
        return None
    return value


def _collect_values(toks: List[Token], start: int) -> List[float]:
    """Collect every numeric value from ``start`` to the end of ``toks``.

    Used for graph-geometry statements (``size 8 6``, ``scale 1 1``), whose
    arguments are a flat run of numbers. Stops at the first token that is not
    the start of a numeric value, so ``scale auto`` yields ``[]``.
    """
    vals: List[float] = []
    i = start
    while i < len(toks):
        val, nxt = _collect_value(toks, i)
        if val is None:
            break
        vals.append(val)
        i = nxt
    return vals


@dataclass
class _GraphGeometryStmt:
    """One recovered graph-geometry statement (``size``/``scale``/``fullsize``).

    ``words`` are the lowercased argument tokens (so ``scale auto`` is
    recognizable), ``values`` their numeric evaluation where they are numbers,
    ``raw`` the verbatim source line (indentation included) used for
    byte-preserving re-emission, and ``line_no`` its 1-indexed source line
    (``None`` only when built without an originating statement).
    """

    keyword: str
    words: List[str]
    values: List[float]
    raw: str
    line_no: Optional[int] = None


@dataclass
class _GraphDatasets:
    """What pass 1 over one graph block collects, for pass 2 and after.

    ``datasets`` maps each dataset name to its (file, x column, y column);
    dataset refs are graph-local. ``merged_attr_toks`` holds each dataset's
    attribute tokens from all of its ``dN ...`` lines (the leading ``dN``
    excluded), in first-appearance order; ``merged_attr_raw`` holds the
    verbatim text of those lines, so a dataset kept as passthrough
    (unresolved file, unconvertible errorbar, ...) re-emits the ORIGINAL
    line(s) byte-for-byte instead of rejoining tokens with inserted spaces
    -- see _dn_passthrough_lines / the 'err 10%' -> 'err 10 %' corruption
    this guards against (GLE rejects the space). ``data_stmts`` pairs the
    raw text of each ``data`` statement with the names it declares, its
    source line, what it defines them as (file, x and y column) and its
    read options, in body order, so one whose datasets end up unmodeled
    can be restored. ``emitted`` starts empty and is filled by pass 2: the
    dataset names whose ``dN`` statement has been handled.
    """

    datasets: Dict[str, Tuple[str, int, int]] = field(default_factory=dict)
    merged_attr_toks: Dict[str, List[Token]] = field(default_factory=dict)
    merged_attr_raw: Dict[str, List[str]] = field(default_factory=dict)
    data_stmts: List[
        Tuple[List[str], str, int, Dict[str, Tuple[str, int, int]], Dict[str, Any]]
    ] = field(default_factory=list)
    emitted: Set[str] = field(default_factory=set)


@dataclass
class _PendingAmove:
    """A page-level ``amove`` that may yet place the next graph block.

    ``raw`` is its verbatim source line, so it can be preserved if no graph
    block follows; ``line_no`` its 1-indexed source line.
    """

    position: Tuple[float, float]
    raw: str
    line_no: Optional[int]


def _dn_fields(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Series fields every ``dN`` display line maps the same way, from its attributes.

    ``attrs`` is :meth:`_Recognizer._scan_series_attrs` output. A line with no
    ``color`` recovers ``color=None``: GLE draws it in the current colour, and
    the writer leaves ``color`` out again. ``xaxis`` is set only for a dataset
    on the top axis.
    """
    fields: Dict[str, Any] = {
        "color": attrs["color"],
        "label": attrs["label"],
        "yaxis": "y2" if attrs["y2axis"] else "y",
    }
    if attrs.get("x2axis"):
        fields["xaxis"] = "x2"
    return fields


def _dn_markersize(attrs: Dict[str, Any]) -> float:
    """A ``dN`` line's ``msize``, kept raw since the writer emits it verbatim.

    GLE's default ``msize`` is 0.15.
    """
    return attrs["msize"] if attrs["msize"] is not None else 0.15


def _dn_width(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """A ``dN`` line's ``lwidth`` as series fields, in matplotlib points.

    The model stores points; the writer converts back to cm. ``None`` when
    the dataset draws a line but sets no ``lwidth``: GLE draws it at the
    current line width, and the writer leaves ``lwidth`` out again. 1.0 when
    it draws no line, since no width is written for it.
    """
    if attrs["lwidth"] is not None:
        return _width_fields(linewidth_cm_to_pt(attrs["lwidth"]))
    return {"linewidth": None if attrs["has_line"] else 1.0}


def _width_fields(linewidth: float) -> Dict[str, Any]:
    """``linewidth`` read from a file, marked to be written as given.

    The writer reads 0 and 1 pt as the style's default width; a file that
    wrote one of them meant that width.
    """
    fields: Dict[str, Any] = {"linewidth": linewidth}
    if linewidth in (0.0, 1.0):
        fields["_lwidth_verbatim"] = True
    return fields


def _plain_function_line(toks: List[Token]) -> bool:
    """True when ``dK`` attribute tokens are what ``add_function`` writes.

    That is ``line`` with any of ``color``, ``lwidth``, a dashed ``lstyle``
    and a non-empty ``key``. A solid or unknown ``lstyle`` number, a marker,
    smoothing or an axis switch would be lost or changed on save.
    """
    has_line = False
    i = 0
    m = len(toks)
    while i < m:
        word = toks[i].value.lower()
        if word == "line" and not has_line:
            has_line = True
            i += 1
        elif word == "color" and i + 1 < m:
            _val, nxt = _collect_color(toks, i + 1)
            if nxt == i + 1:
                return False
            i = nxt
        elif word == "lwidth" and i + 1 < m:
            val, nxt = _collect_value(toks, i + 1)
            if val is None:
                return False
            i = nxt
        elif word == "lstyle" and i + 1 < m:
            val, nxt = _collect_value(toks, i + 1)
            if val is None or not float(val).is_integer():
                return False
            if LSTYLE_TO_MATPLOTLIB.get(int(val)) in (None, "-"):
                return False
            i = nxt
        elif (
            word == "key"
            and i + 1 < m
            and toks[i + 1].type is TokenType.STRING
            and _string_value(toks[i + 1])
        ):
            i += 2
        else:
            return False
    return has_line


def _is_number_literal(toks: List[Token]) -> bool:
    """True when ``toks`` is one number, optionally signed: ``2``, ``-1.5``."""
    if toks and toks[0].type is TokenType.OP and toks[0].value in ("-", "+"):
        toks = toks[1:]
    return len(toks) == 1 and toks[0].type is TokenType.NUMBER


def _glued_run(toks: List[Token], start: int) -> Tuple[str, int]:
    """The text of ``toks[start]`` and the tokens glued to it, and the end.

    GLE ends a ``let`` expression at the first space, so the expression is
    exactly the tokens with no space between them.
    """
    end = start + 1
    while end < len(toks) and toks[end].span[0] == toks[end - 1].span[1]:
        end += 1
    return "".join(tok.value for tok in toks[start:end]), end


#: A name GLE can take as a fit's result variable.
_RESULT_VAR_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")

#: The options of a fit ``let`` (graph2.cpp ``GLELet::parseFitFunction``).
_FIT_LET_WORDS = frozenset(
    {
        "from",
        "to",
        "step",
        "rsq",
        "with",
        "eqstr",
        "format",
        "xmin",
        "xmax",
        "ymin",
        "ymax",
        "limit_data",
        "limit_data_x",
        "limit_data_y",
    }
)

#: The ``format$`` formats GLEWriter._fit_key_expression writes.
_FIT_FIX_RE = re.compile(r"fix (\d+)")
_FIT_SCI_RE = re.compile(r"sci ([1-9]\d*) e expdigits 2 expsign")


def _fit_label_from_key(toks: List[Token], names: Dict[str, str]) -> Optional[str]:
    """The label :meth:`GLEWriter._fit_key_expression` wrote as ``toks``.

    ``names`` maps each result variable to its placeholder. None for any
    other expression: a term that is not a string, ``num$(v)`` or a
    ``format$`` the writer uses, a variable not in ``names``, or a string
    with a quote or something that reads as a placeholder.
    """

    def is_op(i: int, value: str) -> bool:
        return i < len(toks) and toks[i].type is TokenType.OP and toks[i].value == value

    def var(i: int) -> Optional[str]:
        if i < len(toks) and toks[i].type is TokenType.WORD:
            return names.get(toks[i].value.lower())
        return None

    parts = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        word = tok.value.lower() if tok.type is TokenType.WORD else None
        if tok.type is TokenType.STRING:
            text = _string_value(tok)
            if not text or '"' in text or FIT_PLACEHOLDER_RE.search(text):
                return None
            parts.append(text)
            i += 1
        elif word == "num$" and is_op(i + 1, "(") and var(i + 2) and is_op(i + 3, ")"):
            parts.append("{" + str(var(i + 2)) + "}")
            i += 4
        elif (
            word == "format$"
            and is_op(i + 1, "(")
            and var(i + 2)
            and is_op(i + 3, ",")
            and i + 4 < len(toks)
            and toks[i + 4].type is TokenType.STRING
            and is_op(i + 5, ")")
        ):
            fmt = _string_value(toks[i + 4])
            fix = _FIT_FIX_RE.fullmatch(fmt)
            sci = _FIT_SCI_RE.fullmatch(fmt)
            if fix:
                spec = f":.{int(fix.group(1))}f"
            elif sci:
                spec = f":.{int(sci.group(1)) - 1}e"
            else:
                return None
            parts.append("{" + str(var(i + 2)) + spec + "}")
            i += 6
        else:
            return None
        if i < len(toks):
            if not is_op(i, "+") or i + 1 == len(toks):
                return None
            i += 1
    return "".join(parts)


def _read_let_range(
    toks: List[Token], i: int, fields: Dict[str, Any], fit: bool = False
) -> bool:
    """Read ``from``/``to``/``step`` options from ``toks[i:]`` into ``fields``.

    Each takes a plain number, so the value written back is the one read.
    With ``fit``, a fit let's ``with <expression>`` is read too. False on
    any other token, or an option given twice.
    """
    names = {"from": "let_from", "to": "let_to", "step": "let_step"}
    while i < len(toks):
        word = toks[i].value.lower()
        if word == "with" and fit and i + 1 < len(toks):
            if "expression" in fields:
                return False
            expression, i = _glued_run(toks, i + 1)
            if _function_expression_problem(expression) is not None:
                return False
            fields["expression"] = expression
            continue
        key = names.get(word)
        if key is None or key in fields:
            return False
        value, i = _read_let_number(toks, i + 1)
        if value is None:
            return False
        fields[key] = value
    return True


def _let_target_expression(toks: List[Token]) -> Optional[Tuple[str, str, int]]:
    """``(target, expression, end)`` of ``let dK = <expression> ...``, or None.

    The expression is the run of tokens after ``=`` with no space between
    them, which is where GLE's own parser ends it; ``end`` indexes the
    token after it.
    """
    if len(toks) < 4:
        return None
    target = toks[1].value.lower()
    eq = toks[2]
    if not _DATASET_RE.match(target) or eq.type is not TokenType.OP:
        return None
    if eq.value != "=":
        return None
    expression, end = _glued_run(toks, 3)
    return target, expression, end


def _mention_count(texts: List[str], name: str) -> int:
    """How many times the dataset ``name`` is named in ``texts``."""
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", re.IGNORECASE
    )
    return sum(len(pattern.findall(text)) for text in texts)


def _read_let_number(toks: List[Token], j: int) -> Tuple[Optional[float], int]:
    """A plain, optionally signed number at ``toks[j]``, and the index after it.

    ``None`` when there is none, so the value written back is the one read.
    """
    sign = ""
    if j < len(toks) and toks[j].type is TokenType.OP:
        if toks[j].value not in ("-", "+"):
            return None, j
        sign = toks[j].value
        j += 1
    if j >= len(toks) or toks[j].type is not TokenType.NUMBER:
        return None, j
    return float(sign + toks[j].value), j + 1


def _read_derived_options(toks: List[Token], i: int, fields: Dict[str, Any]) -> bool:
    """Read the options of a dataset ``let`` from ``toks[i:]`` into ``fields``.

    ``from``, ``to``, ``step`` and ``nsteps`` take a plain number, ``where``
    an expression without spaces and ``range`` a comma list of datasets
    (kept under ``_range_names``). False on any other token, an option given
    twice, or ``step`` with ``nsteps``, which :meth:`gleplot.Axes.derived`
    rejects.
    """
    names = {
        "from": "let_from",
        "to": "let_to",
        "step": "let_step",
        "nsteps": "let_nsteps",
    }
    while i < len(toks):
        word = toks[i].value.lower()
        if word in ("where", "range") and i + 1 < len(toks):
            key = "let_where" if word == "where" else "_range_names"
            if key in fields:
                return False
            text, i = _glued_run(toks, i + 1)
            if word == "where":
                if _let_expression_problem(text) is not None:
                    return False
                fields[key] = text
                continue
            listed = text.lower().split(",")
            if len(set(listed)) != len(listed) or not all(
                _DATASET_RE.match(name) for name in listed
            ):
                return False
            fields[key] = listed
            continue
        option = names.get(word)
        if option is None or option in fields:
            return False
        value, i = _read_let_number(toks, i + 1)
        if value is None:
            return False
        if option == "let_nsteps":
            if value != int(value) or value < 2:
                return False
            fields[option] = int(value)
        else:
            fields[option] = value
    return "let_step" not in fields or "let_nsteps" not in fields


def _pt_or_none(hei: Optional[float]) -> Optional[float]:
    """GLE ``hei`` in cm -> matplotlib points, passing None through."""
    return None if hei is None else fontsize_cm_to_pt(hei)


def _collect_color(toks: List[Token], start: int) -> Tuple[Optional[str], int]:
    """Collect a colour value starting at ``start``.

    A GLE colour is either a bare name (``BLUE``, ``gray55``) or a colour
    *expression* -- an identifier applied to a parenthesised argument list,
    e.g. ``rgb255(140,140,140)``, ``rgb(0.55,0.4,0.74)``, ``grey(0.5)``. The
    lexer splits an expression into several tokens (``rgb255`` ``(`` ``140``
    ``,`` ...), so reading ``toks[start].value`` alone would recover only the
    function name and leave the arguments to be mis-scanned as further
    qualifiers.

    Returns ``(color_text, next_index)``; the expression form is rejoined
    without whitespace, matching what the writer emits. Returns
    ``(None, start)`` when there is no token to read.
    """
    m = len(toks)
    if start >= m:
        return None, start

    head = toks[start]
    nxt = start + 1
    if not (
        head.type is TokenType.WORD
        and nxt < m
        and toks[nxt].type is TokenType.OP
        and toks[nxt].value == "("
    ):
        return head.value, start + 1

    parts = [head.value]
    depth = 0
    j = nxt
    while j < m:
        t = toks[j]
        parts.append(t.value)
        j += 1
        if t.type is TokenType.OP and t.value == "(":
            depth += 1
        elif t.type is TokenType.OP and t.value == ")":
            depth -= 1
            if depth == 0:
                return "".join(parts), j
    # Unbalanced parentheses: don't swallow the rest of the statement.
    return head.value, start + 1


_KEY_SPACING_WORDS = frozenset(LEGEND_SPACING_TO_KEY.values())


def _key_entry_textcolor(toks: List[Token]) -> Optional[str]:
    """The ``textcolor`` of a ``begin key`` entry; None if absent, "" if odd."""
    found: Optional[str] = None
    for i, t in enumerate(toks):
        if t.type is TokenType.WORD and t.value.lower() == "textcolor":
            color, nxt = _collect_color(toks, i + 1)
            if found is not None or color is None or nxt == i + 1:
                return ""
            found = color
    return found


def _key_anchor_fraction(text: str, template: str) -> Optional[float]:
    """The axes fraction in a ``KEY_ANCHOR_X``/``_Y`` coordinate, else None."""
    head, tail = template.split("{}")
    if not (text.startswith(head) and text.endswith(tail)):
        return None
    try:
        return float(text[len(head) : len(text) - len(tail)])
    except ValueError:
        return None


def _axes_fraction_point(raw: str, keyword: str) -> Optional[Tuple[float, float]]:
    """``(x, y)`` axes fractions of the writer's ``KEYWORD X Y``, else None."""
    words = raw.split()
    if len(words) != 3 or words[0].lower() != keyword:
        return None
    x = _key_anchor_fraction(words[1], KEY_ANCHOR_X)
    y = _key_anchor_fraction(words[2], KEY_ANCHOR_Y)
    if x is None or y is None:
        return None
    return (x, y)


_FIGURE_ANCHOR_NUMBER = r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?"
_FIGURE_ANCHOR_RE = re.compile(
    rf"absolute pagewidth\(\)\*({_FIGURE_ANCHOR_NUMBER})(?:[+-]\S+)? "
    rf"pageheight\(\)\*({_FIGURE_ANCHOR_NUMBER})(?:[+-]\S+)?"
)


def _figure_anchor(raw: str) -> Optional[Tuple[float, float]]:
    """``(x, y)`` figure fractions of a ``Figure.legend`` ``absolute`` line.

    The shifts after the fractions are not read back: they follow from the
    key's position and text height, and the caller checks the whole line
    against :meth:`GLEWriter.figure_legend_absolute`.
    """
    found = _FIGURE_ANCHOR_RE.fullmatch(raw.strip())
    if found is None:
        return None
    return (float(found.group(1)), float(found.group(2)))


_FIGURE_POINT_RE = re.compile(
    rf"amove pagewidth\(\)\*({_FIGURE_ANCHOR_NUMBER}) "
    rf"pageheight\(\)\*({_FIGURE_ANCHOR_NUMBER})"
)


def _is_default_suptitle(text: TextAnnotation) -> bool:
    """Whether ``text`` is where ``Figure.suptitle`` puts a title by default."""
    return (
        text["x"] == 0.5
        and text["y"] == 0.98
        and (text["ha"], text["va"]) == ("center", "top")
        and text.get("fontsize") is not None
    )


def _key_anchor(raw: str) -> Optional[Tuple[float, float]]:
    """``(x, y)`` axes fractions of the writer's ``absolute X Y``, else None."""
    return _axes_fraction_point(raw, "absolute")


def _legend_spacing(cm_by_word, fontsize, fig) -> Dict[str, float]:
    """Key spacing in cm, keyed by GLE word -> font-size units by matplotlib name.

    The inverse of ``GLEWriter._key_options``: the key text height is the
    legend fontsize, else the figure style's.
    """
    points = fontsize if fontsize is not None else fig.style.fontsize
    hei = fontsize_pt_to_cm(float(points))
    return {
        name: cm_by_word[word] / hei
        for name, word in LEGEND_SPACING_TO_KEY.items()
        if word in cm_by_word
    }


def _page_drawing_fields(words: List[str], drawing: Dict[str, Any]) -> bool:
    """Read a drawing command's values onto ``drawing``; False if not one.

    ``words`` is the command split on whitespace, after its ``amove``. The
    counts are only a first filter: the caller compares the drawing's
    rendering with the source, which settles every other detail.
    """
    kind, values = words[0], words[1:]
    if values[-1:] == ["nostroke"] and kind in ("circle", "ellipse"):
        drawing["color"] = "none"
        values = values[:-1]
    if values[-2:-1] == ["fill"] and kind in ("circle", "ellipse"):
        drawing["fill"] = values[-1]
        values = values[:-2]
    numbers = [float(v) for v in values]
    if kind == "circle" and len(numbers) == 1:
        drawing["radius"] = numbers[0]
    elif kind == "ellipse" and len(numbers) == 2:
        drawing["width"], drawing["height"] = (2 * v for v in numbers)
    elif kind == "arc" and len(numbers) == 3:
        drawing["radius"], drawing["theta1"], drawing["theta2"] = numbers
    elif kind == "bezier" and len(numbers) == 6:
        drawing["x"] = [drawing.pop("x"), *numbers[0::2]]
        drawing["y"] = [drawing.pop("y"), *numbers[1::2]]
    elif kind == "curve" and len(numbers) >= 6 and len(numbers) % 2 == 0:
        # The points between the two slopes are steps from the point before,
        # written to 12 digits: rounding the sum to 12 drops the float noise.
        xs, ys = [drawing.pop("x")], [drawing.pop("y")]
        for dx, dy in zip(numbers[2:-2:2], numbers[3:-2:2]):
            xs.append(float(GLEWriter._format_number(xs[-1] + dx, 12)))
            ys.append(float(GLEWriter._format_number(ys[-1] + dy, 12)))
        drawing.update(x=xs, y=ys, start_slope=numbers[:2], end_slope=numbers[-2:])
    else:
        return False
    drawing["kind"] = kind
    return True


def _page_drawing(lines: List[str]) -> Optional[Dict[str, Any]]:
    """The ``Figure`` page drawing a ``gsave`` .. ``grestore`` group draws.

    ``None`` when the group is not one ``GLEWriter.page_drawing_lines``
    writes, so it stays passthrough.
    """
    drawing: Dict[str, Any] = {}
    body = lines[1:-1]
    try:
        while body and body[0].startswith("set "):
            word, value = body[0].split()[1:]
            if word == "color":
                drawing["color"] = value
            elif word == "lwidth":
                drawing["linewidth"] = linewidth_cm_to_pt(float(value))
            else:
                return None
            body = body[1:]
        head = body[0].split()
        if head[:2] == ["begin", "path"]:
            options = head[2:]
            if options[:1] == ["stroke"]:
                options = options[1:]
            else:
                drawing["color"] = "none"
            if options[:1] == ["fill"]:
                drawing["fill"] = options[1]
            corners = [line.split()[1:] for line in body[1:-2]]
            drawing.update(
                kind="polygon",
                x=[float(x) for x, _ in corners],
                y=[float(y) for _, y in corners],
            )
        else:
            _amove, x, y = head
            drawing.update(x=float(x), y=float(y))
            block = body[1].split()
            if block[0] == "begin" and block[1:] in (["table"], ["tex"]):
                drawing.update(kind=block[1], text="\n".join(body[2:-1]))
            elif len(body) != 2 or not _page_drawing_fields(block, drawing):
                return None
        if GLEWriter.page_drawing_lines(drawing) != lines:
            return None
    except (IndexError, KeyError, ValueError):
        return None
    return drawing


# --------------------------------------------------------------------------- #
# The recognizer
# --------------------------------------------------------------------------- #


# GLE's error-bar keyword -> the ``_gle_names`` role of its dataset.
_ERROR_ROLES = {
    "err": "yerr",
    "errup": "yerr_up",
    "errdown": "yerr_down",
    "herr": "xerr",
    "herrleft": "xerr_left",
    "herrright": "xerr_right",
}


class _Recognizer:
    """Stateful recognizer for one document. See :func:`parse_gle_figure`."""

    def __init__(self, text: str, gle_path: Path):
        self.text = text
        self.gle_path = gle_path
        # The lines of a ``begin key`` right after the graph being parsed:
        # a fit's result variables may be named only by its let, its key,
        # and that block restating the key.
        self._key_after_graph: List[str] = []
        # The guides drawn after the graph being parsed, read before it.
        self._post_graph_guides: List[Series] = []
        # The rug groups after it, by dataset, and the rugs read from their
        # datasets (with the 'data' statement's text) awaiting their group.
        self._post_graph_rugs: Dict[str, dict] = {}
        self._ready_rugs: Dict[str, Tuple[Rug, str]] = {}
        # The rugs.gle / color.gle include lines, as (file, text) in file
        # order, held back until the rugs and colorbars are read.
        self._held_includes: List[Tuple[str, str]] = []
        # The figure legend (Figure.legend) recovered after the last graph,
        # as Figure._legend without its spacing, or None. Set before the
        # axes are assembled: it decides what their 'key off' meant.
        self._figure_legend: Optional[Dict[str, Any]] = None
        # The page's text height in points ('set hei'), for the figure
        # legend's distance from the page edge.
        self._page_fontsize = 12.0
        self.notes: List[ImportNote] = []
        # dataset name (lower) -> (data_file, xcol_1based, ycol_1based)
        self._datasets: Dict[str, Tuple[str, int, int]] = {}
        # dataset name (lower) -> the FileSeries reading fields (skiprows,
        # comment, max_rows) its 'data' statement set; absent when none.
        self._data_read_options: Dict[str, Dict[str, Any]] = {}
        # Datasets of this graph left undefined so that whatever reads them
        # stays raw GLE (see _hold_dataset).
        self._held_datasets: Set[str] = set()
        # Files a note has already said gleplot does not load, this graph.
        self._noted_unloaded: Set[str] = set()
        # resolved-table cache per data_file name
        self._table_cache: Dict[str, object] = {}
        self._layout_cache: Dict[Tuple[Any, ...], Optional[GLEDataLayout]] = {}
        self._import_list: Optional[List[str]] = None
        # 1-based numbers of the graphs the metadata names as insets; None
        # in a file with no gleplot metadata, whose insets are recognized
        # by their frames.
        self._insets: Optional[Set[int]] = None
        self._used_prefix_indices: Dict[str, int] = {}  # prefix -> max index+1
        self._used_data_files: set = set()
        # Sticky text-cluster state (GLE 'set hei'/'set color'/'set just' are
        # interpreter-global and persist across clusters/graphs until changed
        # -- see _try_one_text). fontsize stays None until a 'set hei' is
        # actually seen, matching the writer (which only emits 'set hei' when
        # a text's fontsize is not None).
        self._text_fontsize: Optional[float] = None
        self._text_color: str = "BLACK"
        self._text_just: str = "left"
        # The radial limit of the polar axes whose label call the text
        # cluster after its graph may start with; None when none is due.
        self._polar_labels_rmax: Optional[float] = None
        # The degree mark that call ends with (GLE or LaTeX text).
        self._polar_degree = polar_degree_mark(False)
        # Contour/heatmap recognition state.
        # Line numbers spanned by gleplot_<name> subroutine definitions
        # (palette / colorbar / contour-labels). Dropped everywhere, like the
        # metadata block, and regenerated canonically from the model on re-save.
        self._gleplot_sub_lines: set = set()
        # gleplot_contourf<k> sub name (lower case) -> its colouring comment
        # line (writer.CONTOURF_MARKER), and -> the line numbers it spans,
        # read while those subs are scanned.
        self._contourf_subs: Dict[str, str] = {}
        self._contourf_sub_spans: Dict[str, set] = {}
        # gleplot_contourf<k> sub name -> the (zmin, zmax) its first statement
        # maps the colormap's 0..1 back from, when it is a colorbar's palette.
        self._contourf_rescales: Dict[str, Tuple[float, float]] = {}
        # fitz output ``.z`` file -> {points_file, extent, gridsize, ncontour}
        self._fitz_blocks: Dict[str, dict] = {}
        # contour ``.z`` file -> {levels}
        self._contour_blocks: Dict[str, dict] = {}
        # Line numbers of fitz/contour blocks recognized as gleplot-authored
        # (consumed into a series), dropped from passthrough.
        self._consumed_block_lines: set = set()
        # Per-series smoothing (SPEC 14.7), reconciled in _apply_smooth once
        # the figure-wide default is known: (LineSeries, mode, svg_iterations).
        self._smooth_lines: List[Tuple[Series, str, Optional[int]]] = []
        # Smoothing seen on a dataset kind that has no per-series field
        # (error bars, file references):
        # (kind, mode, svg_iterations, span, line_mode or None).
        # Also reconciled in _apply_smooth -- only the ones the figure-wide
        # default cannot reproduce are worth a warning. A line mode is
        # pinned unsmoothed by the writer, so it is reconciled separately.
        self._unmodelled_smooth: List[
            Tuple[str, str, Optional[int], Optional[Tuple[int, int]], Optional[str]]
        ] = []

    # -- notes -------------------------------------------------------------

    @staticmethod
    def _stmt_span(stmt) -> Optional[Tuple[int, int]]:
        """``(line_no, line_no)`` for a statement, or ``None`` when unknown.

        A :class:`~gleplot.parser.syntax.Statement` is always confined to one
        physical line (the lexer/splitter never spans a statement across
        lines), so a single statement's span always has ``start == end``.
        """
        if stmt is None or getattr(stmt, "line_no", None) is None:
            return None
        return (stmt.line_no, stmt.line_no)

    @staticmethod
    def _opt_line_no(stmt) -> Optional[int]:
        """``stmt.line_no``, or ``None`` when ``stmt`` is ``None``."""
        return stmt.line_no if stmt is not None else None

    def _note(
        self,
        category: ImportCategory,
        message: str,
        source_span: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Record one structured recovery note (see :class:`ImportNote`).

        The sole append point for :attr:`notes` -- every recovery warning in
        this class goes through here so ``RecognizedFigure.warnings`` (a
        derived view) and the structured report can never drift apart.
        """
        self.notes.append(
            ImportNote(category=category, message=message, source_span=source_span)
        )

    # -- public driver ---------------------------------------------------

    def run(self) -> RecognizedFigure:
        doc = parse_gle_source(self.text)
        self._scan_document(doc)
        meta = self._read_metadata()

        # Walk the top-level nodes, splitting into preamble / graph blocks /
        # deferred-text clusters / trailer.
        nodes = list(doc.nodes)

        # Detect a graph swallowed into an opaque transform wrapper (begin
        # translate/scale/rotate/origin ... begin graph ...). We do NOT descend
        # into transform wrappers (documented limitation) -- the whole wrapper is
        # preserved as raw GLE -- but we warn so the editor can flag it.
        self._warn_graph_in_transform(nodes)

        # Locate graph blocks and the amove that precedes each (multi-plot).
        graph_indices = [i for i, n in enumerate(nodes) if isinstance(n, GraphBlock)]

        # --- Preamble: everything before the first graph-related node. ---
        first_graph_start = self._first_graph_region_start(nodes, graph_indices)
        # With no graph at all, the page drawings close the file.
        preamble_end, drawings, texts = self._trailing_page_content(
            nodes, first_graph_start
        )
        fig = self._new_figure(meta, nodes[:preamble_end])
        self._page_fontsize = float(fig.style.fontsize)

        # --- Graph blocks + interspersed amove/text/trailer. ---
        smooth_flags: List[bool] = []  # per line-dataset across the whole fig
        parsed_axes, page, fig.passthrough_trailer = self._parse_graph_region(
            nodes, first_graph_start, fig.marker_config, smooth_flags
        )
        fig._drawings = drawings + page[0]
        texts = texts + page[1]
        # Q: which text is the suptitle? The one Figure.suptitle writes by
        # default, first; a fig.text with the same arguments reads back as it.
        if texts and _is_default_suptitle(texts[0]):
            fig._suptitle = texts.pop(0)
        fig.texts = texts
        if self._figure_legend is not None:
            legend = dict(self._figure_legend)
            legend["spacing"] = _legend_spacing(
                legend["spacing"], legend["fontsize"], fig
            )
            fig._legend = legend

        # --- Assemble axes into the figure. ---
        self._assemble_axes(fig, parsed_axes, fig.sharex, fig.sharey)

        # --- smooth handling (global). ---
        self._apply_smooth(fig, fig.graph, smooth_flags)

        # --- data-file naming state for byte-identical re-save. ---
        self._finalize_data_state(fig)
        # The writer includes rugs.gle only for a rug, color.gle only for a
        # colorbar, contour.gle only for contour labels; an include nothing
        # read back will regenerate stays.
        regenerated = {
            RUGS_INCLUDE: any(ax.rugs for ax in fig.axes_list),
            CONTOUR_INCLUDE: any(
                ct.get("clabel") for ax in fig.axes_list for ct in ax.contours
            ),
            COLOR_INCLUDE: any(
                s.get("colorbar")
                for ax in fig.axes_list
                for s in list(ax.heatmaps) + list(ax.scatters)
            ),
        }
        fig.passthrough_header.extend(
            text for name, text in self._held_includes if not regenerated[name]
        )
        self._note_dropped_comments(doc, fig)

        return RecognizedFigure(figure=fig, notes=tuple(self.notes))

    def _note_dropped_comments(self, doc, fig: Figure) -> None:
        """Note each comment after a statement that the figure does not keep.

        gleplot writes a statement it models (or regenerates) from the
        figure, so a ``! comment`` at the end of its line is not written
        back. A statement kept as raw GLE is stored with its comment: a line
        whose last statement is one of the figure's stored lines is kept.
        """
        kept: Optional[Set[str]] = None

        def strings(value: Any) -> List[str]:
            if isinstance(value, str):
                return value.splitlines()
            if isinstance(value, dict):
                return [s for v in value.values() for s in strings(v)]
            if isinstance(value, (list, tuple)):
                return [s for v in value for s in strings(v)]
            return []

        for sl in doc.lines:
            toks = tokenize_line(sl.text)
            if len(toks) < 2 or toks[-1].type is not TokenType.COMMENT:
                continue
            if kept is None:
                kept = {line.strip() for line in strings(fig.to_dict())}
            last = sl.text.rsplit(";", 1)[-1].strip()
            if sl.text.strip() in kept or last in kept:
                continue
            self._note(
                ImportCategory.STRUCTURE,
                f"the comment {toks[-1].value!r} on this line is not written "
                "back on save: gleplot writes the statement it follows from "
                "the figure",
                (sl.line_no, sl.line_no),
            )

    def _scan_document(self, doc) -> None:
        """Whole-file scans the per-node passes depend on, and their notes."""
        # Line ranges of gleplot_<name> subs (palette/colorbar/clabel), dropped
        # like metadata and regenerated canonically from the model on re-save.
        self._gleplot_sub_lines = self._scan_gleplot_sub_lines()

        # Structure warnings from within our own generated subs (e.g. an ``end
        # if`` the flat parser sees as an unmatched ``end``) are noise -- those
        # lines are dropped and regenerated. Suppress them; keep the rest.
        for w in doc.warnings:
            if w.line_no in self._gleplot_sub_lines:
                continue
            self._note(ImportCategory.STRUCTURE, str(w), (w.line_no, w.line_no))

        # 1-based line numbers spanned by the '! gleplot' metadata block; these
        # lines carry parsed values and must be dropped wherever they appear
        # (including inside a graph body) so they never leak into passthrough
        # and re-emit as a stale duplicate block.
        self._meta_lines = self._metadata_line_numbers()

        # Pre-scan fitz/contour blocks and cross-reference them against the
        # colormap / cdata references in the graph blocks, so a gleplot-authored
        # heatmap/contour can be reconstructed and its blocks dropped from
        # passthrough (foreign/unreferenced blocks stay opaque passthrough).
        self._prescan_contour_heatmap(doc.nodes)

        # Guard: files using GLE programming constructs are not safe to edit.
        self._check_programmatic_constructs(doc.nodes)

        # A gleinc include is regenerated when what calls it after a graph
        # is read back; otherwise it stays as written.
        self._gleplot_sub_lines |= self._regenerated_include_lines(doc.nodes)

    def _regenerated_include_lines(self, nodes) -> Set[int]:
        """Lines of the gleinc ``include``s the writer may write again.

        ``graphutil.gle`` when some graph is followed by a guide line that
        will be read back. ``rugs.gle``, ``color.gle`` and ``contour.gle``
        always, their text held in ``_held_includes`` until the rugs,
        colorbars and contour labels are read.
        """
        names: Set[str] = set()
        for k, node in enumerate(nodes):
            if not isinstance(node, GraphBlock):
                continue
            guides, end = self._scan_post_graph_guides(nodes, k + 1, notes=False)
            if any(g["type"] == "refline" and g["linestyle"] != "none" for g in guides):
                names.add(GRAPHUTIL_INCLUDE)
        # The writer writes rugs.gle's include exactly when the model has a
        # rug, which is only known once the graphs are read: hold the lines
        # back, and put them in the header again if no rug was read.
        names.add(RUGS_INCLUDE)
        names.add(COLOR_INCLUDE)
        names.add(CONTOUR_INCLUDE)
        lines = set()
        for node in nodes:
            if not (
                isinstance(node, Statement)
                and (node.keyword or "").lower() == "include"
                and len(_words_and_values(node)) == 2
            ):
                continue
            name = self._first_string(_words_and_values(node))
            if name in names:
                lines.add(node.line_no)
            if name in (RUGS_INCLUDE, COLOR_INCLUDE, CONTOUR_INCLUDE):
                self._held_includes.append((name, self._stmt_text(node)))
        return lines

    def _read_metadata(self) -> Dict[str, Any]:
        """The metadata block, parsed from the whole file, tolerantly."""
        meta, meta_warnings = _metadata.parse_metadata(self.text.splitlines())
        meta_span = (
            (min(self._meta_lines), max(self._meta_lines)) if self._meta_lines else None
        )
        for meta_msg in meta_warnings:
            self._note(ImportCategory.METADATA, meta_msg, meta_span)
        if "import-data" in meta:
            self._import_list = list(meta.get("import-data") or [])
        if meta:
            # A gleplot file names its insets; one without the key has none.
            self._insets = set(meta.get("insets") or [])
        return meta

    def _meta_number(self, meta: Dict[str, Any], key: str) -> Union[int, float]:
        """The metadata's number ``key``, or its default when it is absent.

        A value that is not a finite number is reported and ignored.
        """
        default = float(_metadata.DEFAULTS[key])
        value = meta.get(key, default)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            # An int stays an int, so the next save writes it the same way.
            return value
        self._note(
            ImportCategory.METADATA,
            f"{key} = {value!r} is not a number; using {default}",
            None,
        )
        return default

    def _meta_color(self, meta: Dict[str, Any], key: str) -> str:
        """The metadata's GLE colour ``key``, or its default when it is absent.

        A value that is not a colour token the writer records (a GLE colour
        name or an expression such as ``rgb255(...)``) is reported and
        ignored.
        """
        default = str(_metadata.DEFAULTS[key])
        value = meta.get(key, default)
        if isinstance(value, str) and (
            value in _gle_color_names() or _COLOR_EXPR_RE.match(value)
        ):
            return value
        self._note(
            ImportCategory.METADATA,
            f"{key} = {value!r} is not a GLE colour; using {default}",
            None,
        )
        return default

    def _new_figure(self, meta: Dict[str, Any], pre_nodes) -> Figure:
        """The ``Figure`` described by the metadata and the preamble."""
        dpi = int(meta.get("dpi", 100))
        shares = []
        for key in ("sharex", "sharey"):
            value = meta.get(key, False)
            try:
                shares.append(_share_mode(key, value))
            except ValueError:
                shares.append(bool(value))
                self._note(
                    ImportCategory.METADATA,
                    f"metadata: {key} = {value!r} is not true, false, 'all', "
                    f"'none', 'row' or 'col'; read as {shares[-1]}.",
                )
        sharex, sharey = shares
        msize_scale = self._meta_number(meta, "msize_scale")
        known = (
            "dpi",
            "sharex",
            "sharey",
            "msize_scale",
            "default_linewidth",
            "default_color",
            "default_marker_color",
            "import-data",
            "insets",
        )
        metadata_extra = {k: v for k, v in meta.items() if k not in known}

        (
            figsize,
            font,
            fontsize,
            page_box,
            page_state,
            passthrough_before_hei,
            passthrough_header,
        ) = self._parse_preamble(pre_nodes)

        # Build style/graph/marker configs.
        style = GLEStyleConfig(
            **page_state,
            default_linewidth=self._meta_number(meta, "default_linewidth"),
            default_color=self._meta_color(meta, "default_color"),
            default_marker_color=self._meta_color(meta, "default_marker_color"),
        )
        self._polar_degree = polar_degree_mark(bool(style.usetex))
        style.font = font
        style.fontsize = fontsize
        graph_cfg = GLEGraphConfig()
        marker_cfg = GLEMarkerConfig()
        marker_cfg.msize_scale = msize_scale

        # Figure keeps explicit configs by reference: _apply_smooth relies on
        # ``fig.graph`` being this ``graph_cfg``.
        fig = Figure(
            figsize=figsize,
            dpi=dpi,
            style=style,
            graph=graph_cfg,
            marker=marker_cfg,
            sharex=sharex,
            sharey=sharey,
        )
        fig.metadata_extra = metadata_extra
        fig.page_box = page_box
        fig.passthrough_before_hei = passthrough_before_hei
        fig.passthrough_header = passthrough_header
        return fig

    # -- graph region ------------------------------------------------------

    def _parse_graph_region(
        self,
        nodes,
        start: int,
        marker_cfg: GLEMarkerConfig,
        smooth_flags: List[bool],
    ) -> Tuple[
        List[dict], Tuple[List[Dict[str, Any]], List[TextAnnotation]], List[str]
    ]:
        """The graph blocks and the page-level statements between and after them.

        Returns the parsed info of each graph block, in order, the page
        drawings and figure texts, and the trailer passthrough lines. Raw
        GLE between two graph blocks goes on the info of the first, as its
        ``trailing_passthrough``. A figure legend is left on
        ``self._figure_legend``.
        """
        parsed_axes: List[dict] = []
        drawings: List[Dict[str, Any]] = []
        texts: List[TextAnnotation] = []
        page_done = False
        trailer: List[str] = []
        # The ``amove`` that will place the next graph block, if one does.
        pending: Optional[_PendingAmove] = None
        last_graph = max(
            (k for k, node in enumerate(nodes) if isinstance(node, GraphBlock)),
            default=-1,
        )

        def raw_out() -> List[str]:
            # Raw GLE between two graph blocks stays after the first: an
            # xg()/yg() in it addresses that graph.
            if parsed_axes and i < last_graph:
                return parsed_axes[-1]["trailing_passthrough"]
            return trailer

        i = start
        n = len(nodes)
        while i < n:
            node = nodes[i]
            if isinstance(node, GraphBlock):
                if parsed_axes:
                    # The writer separates the graphs with its own blank line.
                    kept = parsed_axes[-1]["trailing_passthrough"]
                    while kept and not kept[-1].strip():
                        kept.pop()
                axes_info, i = self._parse_placed_graph(
                    nodes, i, pending, marker_cfg, smooth_flags
                )
                parsed_axes.append(axes_info)
                pending = None
                continue

            # Page drawings, figure texts and the figure legend follow every
            # graph block and come before any trailer; with several graphs,
            # after the writer's blank line.
            if not page_done and not trailer and pending is None and i > last_graph:
                page_done = True
                start_at = i
                if len(parsed_axes) > 1 and self._raw_lines(node) == [""]:
                    start_at = i + 1
                drawings, texts, after = self._consume_page_content(
                    nodes, start_at, parsed_axes
                )
                if after != i:
                    i = after
                    continue

            # Non-graph node between/after graphs.
            amove = self._match_amove(node)
            if amove is not None:
                # A previously pending amove reached here without a graph
                # block ever consuming it as a placement prefix -- a second
                # amove overwrites GLE's "current point" too, so the first
                # one can no longer be "the amove immediately before a graph
                # block" either. It can never become a placement prefix now:
                # flush it byte-verbatim as raw GLE, in stream order, rather
                # than silently overwriting and losing it.
                if pending is not None:
                    raw_out().append(pending.raw)
                pending = _PendingAmove(
                    position=amove,
                    raw=self._stmt_text(node),
                    line_no=getattr(node, "line_no", None),
                )
                i += 1
                continue

            if isinstance(node, BlankOrComment):
                blank = not self._stmt_text(node.statement).strip()
                # A comment between an amove and its graph leaves the amove
                # placing the graph; a blank line inside raw GLE between
                # graphs stays in it.
                out = raw_out()
                if not blank and pending is not None and i < last_graph:
                    if out is trailer:
                        self._note(
                            ImportCategory.STRUCTURE,
                            "comment between the first graph's 'amove' and "
                            "'begin graph' is not written back on save",
                            self._stmt_span(node.statement),
                        )
                    else:
                        out.extend(self._raw_lines(node))
                    i += 1
                    continue
                if blank and pending is None and out is not trailer and out:
                    out.extend(self._raw_lines(node))
                    i += 1
                    continue

            if self._is_regenerated_page_node(nodes, i):
                i += 1
                continue

            # Anything else between or after the graphs is raw GLE. A
            # pending amove can no longer become a placement prefix once a
            # real statement sits between it and the next graph block (if
            # any) -- flush it ahead of this node, byte-verbatim, preserving
            # stream order.
            if pending is not None:
                raw_out().append(pending.raw)
                pending = None
            raw_out().extend(self._raw_lines(node))
            i += 1

        # End of document: a still-pending amove has no following graph
        # block left to become a placement prefix for -- preserve it
        # byte-verbatim as the last trailer statement instead of dropping it
        # (see module docstring: an amove is either consumed as a placement
        # prefix or preserved verbatim, never silently lost).
        if pending is not None:
            trailer.append(pending.raw)

        return parsed_axes, (drawings, texts), trailer

    def _consume_page_content(
        self, nodes, i: int, parsed_axes: List[dict]
    ) -> Tuple[List[Dict[str, Any]], List[TextAnnotation], int]:
        """Page drawings, figure texts and the figure legend at ``nodes[i]``.

        In the order ``Figure._write_page_content`` writes them. Returns the
        drawings, the texts and the next index; a legend is left on
        ``self._figure_legend``.
        """
        drawings, i = self._consume_page_drawings(nodes, i)
        texts: List[TextAnnotation] = []
        while i < len(nodes):
            end = self._group_end(nodes, i)
            if end is None:
                break
            text = self._figure_text(nodes[i : end + 1])
            if text is None:
                break
            texts.append(text)
            i = end + 1
        if parsed_axes and i < len(nodes):
            legend = self._figure_legend_block(nodes[i], parsed_axes)
            if legend is not None:
                self._figure_legend = legend
                i += 1
        return drawings, texts, i

    def _group_end(self, nodes, i: int) -> Optional[int]:
        """Index of the ``grestore`` closing a ``gsave`` at ``nodes[i]``."""
        stmt = self._as_statement(nodes[i])
        if stmt is None or stmt.keyword != "gsave":
            return None
        for end in range(i + 1, len(nodes)):
            if isinstance(nodes[end], Statement) and nodes[end].keyword == "grestore":
                return end
        return None

    def _figure_text(self, group) -> Optional[TextAnnotation]:
        """The ``Figure.text`` a ``gsave`` .. ``grestore`` group writes, or None.

        ``None`` unless :meth:`GLEWriter.figure_text_lines` reproduces the
        group exactly, so anything else stays passthrough.
        """

        def words(k: int) -> List[Token]:
            stmt = self._as_statement(group[k]) if k < len(group) else None
            return _words_and_values(stmt) if stmt is not None else []

        fields: Dict[str, Any] = {"fontsize": None}
        k = 1
        toks = words(k)
        if [t.value.lower() for t in toks[:2]] == ["set", "hei"]:
            hei = _num(toks[2]) if len(toks) == 3 else None
            if hei is None:
                return None
            fields["fontsize"] = fontsize_cm_to_pt(hei)
            k += 1
            toks = words(k)
        if [t.value.lower() for t in toks[:2]] != ["set", "color"]:
            return None
        color, _nxt = _collect_color(toks, 2)
        toks = words(k + 1)
        if [t.value.lower() for t in toks[:2]] != ["set", "just"] or len(toks) != 3:
            return None
        align = text_just_to_align(toks[2].value.lower())
        amove = self._as_statement(group[k + 2]) if k + 2 < len(group) else None
        found = None if amove is None else _FIGURE_POINT_RE.fullmatch(amove.raw.strip())
        if color is None or align is None or found is None:
            return None
        drawn = self._match_text_draw(group, k + 3)
        if drawn is None or drawn[0] != len(group) - 1 or drawn[4] is not None:
            return None
        _next, text_str, box_color, rotation, _name = drawn
        fields.update(
            x=float(found.group(1)),
            y=float(found.group(2)),
            text=text_str,
            color=color,
            ha=align[0],
            va=align[1],
            box_color=box_color,
        )
        if rotation is not None and abs(rotation) >= 1e-10:
            fields["rotation"] = rotation
        text = TextAnnotation(**fields)
        lines = [line for node in group for line in self._raw_lines(node)]
        if GLEWriter.figure_text_lines(text) != lines:
            return None
        return text

    def _figure_legend_block(self, node, parsed_axes) -> Optional[Dict[str, Any]]:
        """The ``Figure.legend`` a ``begin key`` block after the graphs draws.

        Taken only when its entries are exactly the labelled series of every
        graph, graph by graph, and every line is the one the writer would
        write: the ``justify`` + page ``absolute`` placement, column breaks
        where ``legend_column_breaks`` puts them. Stamps each graph's
        ``legend_seq`` with the order its entries are listed in. Returns
        ``Figure._legend`` with the spacing still in cm by GLE word.
        """
        if not isinstance(node, OpaqueBlock) or node.block_type != "key":
            return None
        fit_labels: Dict[str, str] = {}
        for info in parsed_axes:
            fit_labels.update(info["_fit_key_labels"])
        parsed = self._parse_external_key(node, fit_labels, _figure_anchor)
        if (
            parsed is None
            or parsed["anchor"] is None
            or parsed["offset"] is not None
            or parsed["compact"]
        ):
            return None
        labels = parsed["labels"]
        ncol = parsed["separators"] + 1
        if parsed["breaks"] != legend_column_breaks(len(labels), ncol):
            return None
        fontsize = None if parsed["hei"] is None else fontsize_cm_to_pt(parsed["hei"])
        position = KEY_POSITIONS_SHORT_TO_LONG[parsed["pos"]]
        anchor = parsed["anchor"]
        key = KeyOptions(position=position, fontsize=fontsize, anchor=anchor)
        absolute = GLEWriter.figure_legend_absolute(key, self._page_fontsize)
        if absolute != parsed["absolute"]:
            return None
        chunks = []
        start = 0
        for info in parsed_axes:
            pool = self._legend_pool(info)
            chunk = labels[start : start + len(pool)]
            if sorted(chunk) != sorted(series["label"] for series in pool):
                return None
            if len(set(chunk)) != len(chunk):
                return None
            chunks.append((info, chunk))
            start += len(pool)
        if start != len(labels):
            return None
        for info, chunk in chunks:
            self._assign_legend_seq(info, chunk)
        return {
            "loc": position,
            "anchor": None if anchor == legend_corner(position) else list(anchor),
            "ncol": ncol,
            "fontsize": fontsize,
            "frameon": not parsed["nobox"],
            "facecolor": parsed["background"],
            "labelcolor": parsed["labelcolor"],
            "spacing": parsed["spacing"],
        }

    def _trailing_page_content(
        self, nodes, start: int
    ) -> Tuple[int, List[Dict[str, Any]], List[TextAnnotation]]:
        """Where page content that ends ``nodes[:start]`` begins, and its parts.

        Only a file with no graph block ends its preamble with page drawings
        and figure texts. Returns the start index, the drawings and texts.
        """
        if start != len(nodes):
            return start, [], []
        i = 0
        while i < start:
            drawings, texts, after = self._consume_page_content(nodes, i, [])
            if (drawings or texts) and after == start:
                return i, drawings, texts
            i = max(after, i + 1)
        return start, [], []

    def _consume_page_drawings(self, nodes, i) -> Tuple[List[Dict[str, Any]], int]:
        """The run of ``Figure`` page drawings at ``nodes[i]``, and the next index."""
        drawings: List[Dict[str, Any]] = []
        while i < len(nodes):
            end = self._group_end(nodes, i)
            if end is None:
                break
            lines = [
                line for node in nodes[i : end + 1] for line in self._raw_lines(node)
            ]
            drawing = _page_drawing(lines)
            if drawing is None:
                break
            drawings.append(drawing)
            i = end + 1
        return drawings, i

    def _parse_placed_graph(
        self,
        nodes,
        i: int,
        pending: Optional[_PendingAmove],
        marker_cfg: GLEMarkerConfig,
        smooth_flags: List[bool],
    ) -> Tuple[dict, int]:
        """The graph block at ``nodes[i]``, its ``amove``, and what follows it.

        Returns the graph's parsed info and the index of the first node after
        everything consumed with it.
        """
        self._post_graph_guides, guides_end = self._scan_post_graph_guides(nodes, i + 1)
        self._post_graph_rugs = self._scan_post_graph_rugs(nodes, guides_end)
        after = nodes[guides_end] if guides_end < len(nodes) else None
        self._key_after_graph = (
            [sl.text for sl in after.inner_lines]
            if isinstance(after, OpaqueBlock) and after.block_type == "key"
            else []
        )
        axes_info = self._parse_graph_block(nodes[i], marker_cfg, smooth_flags)
        axes_info["amove"] = pending.position if pending is not None else None
        # Verbatim source line of the amove, so one that does not become a
        # placement rect can still be preserved (see _apply_geometry), and its
        # 1-indexed source line, so notes about it can carry a real span.
        axes_info["amove_raw"] = pending.raw if pending is not None else None
        axes_info["amove_line_no"] = pending.line_no if pending is not None else None
        # A ``begin key`` we emitted for addition-order columns sits
        # immediately after this graph, before its deferred text.
        after_key = self._consume_external_legend(nodes, guides_end, axes_info)
        # Greedily consume deferred text cluster that follows. A polar
        # axes' tick-label call leads it (see _try_one_text).
        self._polar_labels_rmax = axes_info["polar_rmax"]
        texts, consumed = self._consume_text_cluster(nodes, after_key)
        self._polar_labels_rmax = None
        for node in nodes[after_key:consumed]:
            # The matcher skips comments as it skips blank lines; the
            # model has nowhere to keep one in place.
            if (
                isinstance(node, BlankOrComment)
                and self._stmt_text(node.statement).strip()
            ):
                self._note(
                    ImportCategory.STRUCTURE,
                    "comment among the text or rug commands after "
                    "'end graph' is not written back on save",
                    self._stmt_span(node.statement),
                )
        if axes_info["polar_rmax"] is not None and not any(
            t is _POLAR_LABELS for t in texts
        ):
            self._note(
                ImportCategory.STRUCTURE,
                "the polar axes has no 'gleplot_polar_labels' call matching "
                "its grid after 'end graph'; the tick labels are written "
                "again on save",
                None,
            )
        texts = [t for t in texts if t is not _POLAR_LABELS]
        # A rug whose call stayed raw needs the 'data' statement it reads.
        for rug, raw in self._ready_rugs.values():
            axes_info["passthrough"].append(raw)
        self._ready_rugs = {}
        axes_info["texts"] = [t for t in texts if not isinstance(t, Rug)]
        axes_info["rugs"] = [t for t in texts if isinstance(t, Rug)]
        # Then consume any post-graph colorbar / contour-label sub
        # calls belonging to this axes.
        return axes_info, self._consume_post_graph_calls(nodes, consumed, axes_info)

    def _is_regenerated_page_node(self, nodes, i: int) -> bool:
        """Whether ``nodes[i]``, outside any graph, is regenerated on re-save."""
        node = nodes[i]
        # Blank line directly separating subplots: skip silently only when
        # between graphs (writer emits a blank between subplots). Otherwise
        # it is trailer content, as a comment always is.
        if (
            isinstance(node, BlankOrComment)
            and not self._stmt_text(node.statement).strip()
            and self._more_graphs_after(nodes, i)
        ):
            return True

        # A gleplot_<name> sub between graphs: a contourf's band sub goes
        # right before the graph that calls it.
        first = node.begin if isinstance(node, OpaqueBlock) else node
        if isinstance(first, (Statement, BlankOrComment)) and (
            first.line_no in self._gleplot_sub_lines
        ):
            return True

        # fitz/contour blocks consumed into a recognized series (their
        # geometry lives on the model; regenerated on re-save).
        return (
            isinstance(node, OpaqueBlock)
            and node.block_type in ("fitz", "contour")
            and node.begin.line_no in self._consumed_block_lines
        )

    # -- programmatic-construct guard -----------------------------------

    #: Top-level statement keywords that mark a GLE *programmatic* file (control
    #: flow / subroutines). The syntax parser has no awareness of these, so a
    #: graph inside such a construct parses as a top-level graph and editing it
    #: would restructure the file. We only *warn*; parse behavior is unchanged.
    _PROGRAMMATIC_KEYWORDS = frozenset(
        {
            "sub",
            "if",
            "for",
            "while",
            "until",
            "next",
            "else",
            "return",
        }
    )

    #: Opaque wrapper block types that establish a coordinate transform. A
    #: graph nested inside one of these is preserved wholesale as raw GLE.
    _TRANSFORM_WRAPPERS = frozenset({"translate", "scale", "rotate", "origin"})

    def _warn_graph_in_transform(self, nodes) -> None:
        for node in nodes:
            if not isinstance(node, OpaqueBlock):
                continue
            if node.block_type not in self._TRANSFORM_WRAPPERS:
                continue
            end_line = (
                node.end.line_no
                if node.end is not None
                else (
                    node.inner_lines[-1].line_no
                    if node.inner_lines
                    else node.begin.line_no
                )
            )
            for sl in node.inner_lines:
                stripped = sl.text.strip().lower()
                if stripped.startswith("begin graph"):
                    self._note(
                        ImportCategory.STRUCTURE,
                        "graph inside begin translate/scale is "
                        "preserved as raw GLE, not editable",
                        (node.begin.line_no, end_line),
                    )
                    break

    def _check_programmatic_constructs(self, nodes) -> None:
        for node in nodes:
            if not isinstance(node, Statement):
                continue
            # gleplot_<name> subroutine bodies use sub/if/return/else etc., but
            # are our own self-contained palettes/colorbar/labels -- not a
            # user-authored programmatic file. Don't flag them.
            if node.source_line is not None and node.line_no in self._gleplot_sub_lines:
                continue
            kw = node.keyword
            if kw is not None and kw in self._PROGRAMMATIC_KEYWORDS:
                self._note(
                    ImportCategory.PROGRAMMATIC,
                    "file contains GLE programming constructs "
                    "(sub/if/for); opening for editing may restructure them -- "
                    "consider read-only preview",
                    (node.line_no, node.line_no),
                )
                return

    # -- preamble --------------------------------------------------------

    def _first_graph_region_start(self, nodes, graph_indices) -> int:
        """Index of the first node that belongs to the graph region.

        That is the first ``amove`` immediately preceding the first graph
        block (multi-plot), or the first graph block itself (single-plot).
        Everything before it is preamble.
        """
        if not graph_indices:
            return len(nodes)
        first_graph = graph_indices[0]
        # Look back for an amove directly before the first graph (skipping a
        # blank line if any).
        j = first_graph - 1
        # allow a single amove (with optional trailing blank) right before.
        while j >= 0 and isinstance(nodes[j], BlankOrComment):
            j -= 1
        if j >= 0 and self._match_amove(nodes[j]) is not None:
            return j
        return first_graph

    def _parse_preamble(
        self, pre_nodes
    ) -> Tuple[
        Tuple[float, float], str, float, bool, Dict[str, Any], List[str], List[str]
    ]:
        figsize = (8.0, 6.0)
        font = ""
        fontsize = 12.0
        # GLE's page-level 'size w h box' outline modifier (default: no
        # outline; see the 'size' branch below for the empirically-verified
        # grammar). Figure.page_box.
        page_box = False
        passthrough: List[str] = []
        # Lines that sat, in the original, between a recognized 'size'/'set
        # font' and a recognized 'set hei' -- e.g. clip.gle's own
        # 'scale .6 .8' (appendix/fig/clip.gle, GLEstudio's rendered-fidelity
        # corpus). 'hei' is a length in GLE's CURRENT user units, so such a
        # statement changes what 'set hei' actually renders as; the writer
        # must reproduce that relative order (GLEWriter.add_preamble emits
        # this bucket BEFORE its own 'set hei' line, unlike ``passthrough``,
        # which always goes after). Almost always empty: only 'size'/'set
        # font' being seen at all (``started``) without 'set hei' having
        # been seen yet (``hei_seen``) diverts passthrough here instead of
        # to the normal bucket, so a file with nothing between them (the
        # overwhelming majority) never populates it.
        before_hei: List[str] = []
        started = False
        hei_seen = False
        # Only the FIRST 'set font'/'set hei' in the preamble is recognized
        # onto the model at all -- a SECOND one is a real, later restyle
        # (GLE's 'current point'-like sticky state: text drawn after it uses
        # the new value, text already described by the first keeps its own).
        # Collapsing every occurrence into a single global default (the
        # previous behavior: the LAST one silently overwrote fontsize/font
        # with no note and no passthrough) is a genuine rendered-fidelity
        # bug, not just a re-emission nicety -- appendix/fig/clip.gle's own
        # 'set hei .3' (a small caption) followed later by 'set hei 10'
        # (body text) collapsed to a single hei=10 default, so the caption
        # rendered 33x too large after round-trip. A second occurrence now
        # falls through to passthrough like any unrecognized statement.
        font_seen = False
        # 'set cap'/'set join'/'set dashlen'/'set texlabels' ->
        # GLEStyleConfig line_cap/line_join/dashlen/usetex. The writer emits
        # them before any passthrough, so only a first occurrence that no
        # drawing statement precedes is recognized: re-emitted earlier, it
        # still reaches every stroke and label it reached before. Anything
        # later stays raw where it was.
        page_state: Dict[str, Any] = {}
        statement_passed = False
        # Whether a 'set hei ...' will ever be recognized ANYWHERE in this
        # preamble at all. Without this guard, a preamble with 'size'/'set
        # font' but NO 'set hei' statement (the writer's own default then
        # applies) would have ``started and not hei_seen`` stay true for
        # the rest of the walk -- there being no 'hei' to eventually land
        # before -- and every remaining passthrough line would wrongly
        # divert into ``before_hei`` instead of the normal bucket.
        will_see_hei = any(
            isinstance(node, Statement)
            and node.keyword == "set"
            and len(_words_and_values(node)) >= 3
            and _words_and_values(node)[1].value.lower() == "hei"
            and _collect_value(_words_and_values(node), 2)[0] is not None
            for node in pre_nodes
        )

        # Track which lines belong to the metadata block, or to a gleplot_<name>
        # sub definition, so we drop them (both are regenerated canonically).
        meta_line_nos = self._meta_lines | self._gleplot_sub_lines

        def _passthrough(text: str, statement: bool = True) -> None:
            nonlocal statement_passed
            statement_passed = statement_passed or statement
            before = will_see_hei and started and not hei_seen
            (before_hei if before else passthrough).append(text)

        for node in pre_nodes:
            if isinstance(node, OpaqueBlock):
                # begin box / begin rotate nested inside a gleplot_<name> sub
                # body (e.g. the colorbar sub) -> drop with the sub.
                if node.begin.line_no in self._gleplot_sub_lines:
                    continue
                # Consumed fitz/contour blocks: their geometry lives on the
                # model, regenerated on re-save; drop the raw block here.
                if (
                    node.block_type in ("fitz", "contour")
                    and node.begin.line_no in self._consumed_block_lines
                ):
                    continue

            if isinstance(node, BlankOrComment):
                stmt = node.statement
                if stmt.line_no in meta_line_nos:
                    continue
                # Drop the two canonical header comment lines and blank lines;
                # keep any other comment as header passthrough.
                text = stmt.source_line.text if stmt.source_line else stmt.raw
                stripped = text.strip()
                if stripped in ("! GLE graphics file", "! Generated by gleplot", ""):
                    continue
                _passthrough(text, statement=False)
                continue

            if isinstance(node, Statement):
                if node.source_line and node.line_no in meta_line_nos:
                    continue
                kw = node.keyword
                toks = _words_and_values(node)
                if kw == "size" and len(toks) >= 3:
                    w, nxt = _collect_value(toks, 1)
                    h, nxt2 = _collect_value(toks, nxt)
                    if w is not None and h is not None:
                        # The page-level 'size w h' command has its OWN,
                        # much narrower grammar than a graph's 'size'/
                        # 'scale' (GLE/src/gle/graph.cpp's do_remaining_
                        # entries, which accepts box/nobox/border/noborder/
                        # center/fullsize/math in any combination) --
                        # confirmed empirically (GLE 4.3.10, gle-manual has
                        # no documented modifier at all for the page-level
                        # form): 'size 8 6 box' draws a border around the
                        # whole page and compiles; 'size 8 6 nobox' (or
                        # border/noborder/center/fullsize/math/anything
                        # else) is a hard parse error, "found 'X', but
                        # expecting 'BOX'". There is no way to SAY "no
                        # border" at the page level beyond omitting the
                        # word -- 'box' is the only accepted trailing
                        # token, and at most one of it.
                        trailing = toks[nxt2:]
                        if not trailing:
                            figsize = (cm_to_inches(w), cm_to_inches(h))
                            started = True
                            continue
                        if len(trailing) == 1 and trailing[0].value.lower() == "box":
                            figsize = (cm_to_inches(w), cm_to_inches(h))
                            page_box = True
                            started = True
                            continue
                        # Anything else here is not valid GLE at all (GLE
                        # itself would refuse to compile it) -- kept fully
                        # raw rather than guessing at a meaning for it.
                        # figsize keeps its prior value (the default, or
                        # whatever an EARLIER 'size' recognized).
                        _passthrough(self._stmt_text(node))
                        continue
                if kw == "set" and len(toks) >= 2:
                    sub = toks[1].value.lower()
                    if sub == "font" and len(toks) >= 3 and not font_seen:
                        font = toks[2].value
                        started = True
                        font_seen = True
                        continue
                    if sub == "hei" and len(toks) >= 3 and not hei_seen:
                        hei, _ = _collect_value(toks, 2)
                        if hei is not None:
                            fontsize = fontsize_cm_to_pt(hei)
                            started = True
                            hei_seen = True
                            continue
                    field = _PAGE_STATE_FIELDS.get(sub)
                    # Exactly three tokens: a trailing comment would be lost.
                    if (
                        field is not None
                        and field not in page_state
                        and not statement_passed
                        and len(node.tokens) == 3
                    ):
                        value = _page_state_value(field, toks[2])
                        if value is not None:
                            page_state[field] = value
                            continue
                # Unrecognized preamble statement -> header passthrough.
                _passthrough(self._stmt_text(node))
                continue

            # Opaque block in the preamble -> header passthrough (raw lines).
            # A texpreamble block draws nothing, so the page state after it
            # (GLE's usual 'set texlabels 1') is still recognized.
            drawn = getattr(node, "block_type", "") != "texpreamble"
            for line in self._raw_lines(node):
                _passthrough(line, statement=drawn)

        return figsize, font, fontsize, page_box, page_state, before_hei, passthrough

    def _metadata_line_numbers(self) -> set:
        """1-based line numbers spanned by the ``! gleplot`` metadata block."""
        nums: set = set()
        in_block = False
        for idx, line in enumerate(self.text.splitlines(), start=1):
            s = line.strip()
            if not in_block:
                if s.startswith("! gleplot-meta-begin"):
                    in_block = True
                    nums.add(idx)
                continue
            nums.add(idx)
            if s == _metadata.END_MARKER:
                in_block = False
        return nums

    # -- graph block -----------------------------------------------------

    def _parse_graph_block(self, block: GraphBlock, marker_cfg, smooth_flags) -> dict:
        """Parse one ``begin graph`` .. ``end graph`` into an axes-info dict.

        Pass 1 decides which lets the writer may renumber before pass 2
        knows whether a derived let's datasets all became series. When one
        did not, the block is parsed again from the state before it, with
        that let raw from the start, so every let beside it stays raw too.
        """
        if not any(
            isinstance(child, Statement) and child.keyword == "let"
            for child in block.body
        ):
            return self._parse_graph_block_once(block, marker_cfg, smooth_flags, set())
        # The file caches only memoize reads, so they are shared, not copied.
        saved = copy.deepcopy(
            {
                k: v
                for k, v in vars(self).items()
                if k not in ("_table_cache", "_layout_cache")
            }
        )
        saved_flags = list(smooth_flags)
        info = self._parse_graph_block_once(block, marker_cfg, smooth_flags, set())
        if not info["_derived_failed"]:
            return info
        vars(self).update(saved)
        smooth_flags[:] = saved_flags
        return self._parse_graph_block_once(
            block, marker_cfg, smooth_flags, info["_derived_failed"]
        )

    def _parse_graph_block_once(
        self, block: GraphBlock, marker_cfg, smooth_flags, raw_lets
    ) -> dict:
        """One parse of a graph block, keeping the lets in ``raw_lets`` raw.

        Pass 1 collects the block's datasets and merges each one's ``dN``
        lines; pass 2 walks the body in order, dispatching every statement and
        building one series per dataset the first time its name appears.
        """
        info = self._new_graph_info(block)
        info["_raw_derived"] = raw_lets
        info["_derived_failed"] = set()

        # Guides drawn after 'end graph' (gleplot.guides), already read by
        # _parse_placed_graph. They come first, as the writer writes them;
        # a labelled one's legend bridge is a 'dN' statement in this block
        # that pass 1's dataset-merging would otherwise take for a series.
        self._seed_post_graph_guides(block, info)

        # Guide provenance markers (G18-lite), bound to the dataset each one
        # describes. Also scanned up front: the binding has to exist before
        # pass 2 builds the series that dataset's display command produces.
        self._prescan_guide_markers(block, info)

        frame_off_lines = self._prescan_frame_off(block)
        info["frame_off"] = bool(frame_off_lines)
        info["_switched_on"] = self._prescan_switched_on(block)
        polar_line = self._prescan_polar(block, info)
        math_line = self._prescan_math(block)
        if math_line is not None:
            info["math_mode"] = True

        pass1 = self._collect_datasets(block, info)
        self._claim_guide_bridges(block, info, pass1)
        self._claim_rug_datasets(pass1)
        self._mark_bars_that_stay_raw(block, pass1.datasets, info)

        for child in block.body:
            if isinstance(child, OpaqueBlock):
                if child.line_no == polar_line:
                    continue
                image = self._image_block(child)
                if image is not None:
                    info["images"].append(image)
                else:
                    info["passthrough"].extend(self._raw_lines(child))
            elif isinstance(child, BlankOrComment):
                self._parse_graph_comment(child, info)
            elif isinstance(child, Statement) and (
                child.line_no in frame_off_lines or child.line_no == math_line
            ):
                continue
            elif isinstance(child, Statement) and not self._skip_meta_stmt(child):
                self._dispatch_graph_statement(
                    child, pass1, info, marker_cfg, smooth_flags
                )

        self._commit_derived_lets(info)
        self._flush_hist_lets(info)
        self._restore_orphaned_data_stmts(pass1, info)
        self._bind_raw_readers(info)
        self._note_raw_lets(info)
        self._discard_guide_markers(info)
        self._reconcile_places_names(info)
        self._reconcile_axis_styling(info)
        return info

    @staticmethod
    def _new_graph_info(block: GraphBlock) -> Dict[str, Any]:
        """The empty axes-info dict that parsing ``block`` fills in."""
        info: Dict[str, Any] = {
            # Graph-geometry statements ('size'/'scale'/'fullsize') in source
            # order, as _GraphGeometryStmt records. Classified into a
            # placement rect / verbatim geometry passthrough by
            # _apply_geometry once the whole figure is known (a single graph
            # and a grid member are handled differently).
            "geometry_stmts": [],
            "title": None,
            "xlabel": None,
            "ylabel": None,
            "y2label": None,
            "x2label": None,
            "xmin": None,
            "xmax": None,
            "xlog": False,
            "xnegate": False,
            "ymin": None,
            "ymax": None,
            "ylog": False,
            "ynegate": False,
            "y2min": None,
            "y2max": None,
            "y2log": False,
            "y2negate": False,
            "x2min": None,
            "x2max": None,
            "x2log": False,
            "x2negate": False,
            # ``xaxis log`` copies onto x2. ``lin`` is how a script undoes
            # that. Kept only so a redundant ``lin`` (primary axis not log)
            # can be handed back to passthrough; the writer recomputes the
            # token it will actually emit.
            "x2lin": False,
            "xlabels_off": False,
            "ylabels_off": False,
            # -- axes styling (GLEstudio plan G10) ------------------------
            # Tick-label number format (GLE 'xaxis format "..."'), tick-label
            # rotation ('xaxis angle') and grid ('xaxis grid'); the graph
            # title's and each axis title's hei/color/dist; the tick labels'
            # hei/color. All None/False = not present in the source, which is
            # also the model default, so a file without them round-trips
            # untouched.
            "title_hei": None,
            "title_color": None,
            "title_dist": None,
            "xformat": None,
            "yformat": None,
            "y2format": None,
            "x2format": None,
            "xangle": None,
            "yangle": None,
            "y2angle": None,
            "x2angle": None,
            "xgrid": False,
            "ygrid": False,
            "xtitle_hei": None,
            "xtitle_color": None,
            "xtitle_dist": None,
            "ytitle_hei": None,
            "ytitle_color": None,
            "ytitle_dist": None,
            "y2title_hei": None,
            "y2title_color": None,
            "y2title_dist": None,
            "x2title_hei": None,
            "x2title_color": None,
            "x2title_dist": None,
            "xlabels_hei": None,
            "xlabels_color": None,
            "ylabels_hei": None,
            "ylabels_color": None,
            "y2labels_hei": None,
            "y2labels_color": None,
            "x2labels_hei": None,
            "x2labels_color": None,
            # Title fonts ('title'/'xtitle ... font F'), axis lines ('xside
            # color C lwidth W') and tick placement ('xaxis nticks/ftick/
            # shift/symticks', 'xnoticks ...'). None = absent, as above.
            "title_font": None,
            "xtitle_font": None,
            "ytitle_font": None,
            "y2title_font": None,
            "x2title_font": None,
            "xside": None,
            "yside": None,
            "y2side": None,
            "x2side": None,
            "y2axis_off": False,
            "x2axis_off": False,
            "xnticks": None,
            "ynticks": None,
            "xftick": None,
            "yftick": None,
            "xshift": None,
            "yshift": None,
            "xsymticks": None,
            "ysymticks": None,
            "xnoticks": None,
            "ynoticks": None,
            "xnsubticks": None,
            "ynsubticks": None,
            "xdticks": None,
            "ydticks": None,
            "xdsubticks": None,
            "ydsubticks": None,
            # 'xlabels log MODE' (x and y only).
            "xloglabels": None,
            "yloglabels": None,
            # A bare 'math' ahead of everything but geometry (_prescan_math).
            "math_mode": None,
            "facecolor": None,
            # (prefix, keyword) of every axis-line option (and tick-label
            # "loglabels") kept as raw GLE.
            # Raw lines are written at the end of the block, so a later
            # occurrence of the same option is not modeled either: it would
            # be written before the raw one and lose to it.
            "_raw_axis_opts": set(),
            # Deferred lines: an 'xticks'/'xsubticks' style is grid style
            # when that axis has a grid (the grid lines ARE the ticks) and
            # tick marks when it has none, and a 'y2labels on' is only
            # implied when some y2 tick-label property is modeled. Whether
            # that holds is not known until the whole block has been read --
            # GLE statement order is free -- so they are parked here and resolved by
            # _reconcile_axis_styling, which sends the unusable ones back to
            # passthrough verbatim.
            "_xticks": None,
            "_yticks": None,
            "_xsubticks": None,
            "_ysubticks": None,
            "_y2labels_on_raw": None,
            "_y2labels_on_line": None,
            "_x2labels_on_raw": None,
            "_x2labels_on_line": None,
            # The raw text of a bare 'y2ticks on' / 'x2ticks on', judged once
            # the block is read (see _reconcile_axis_styling).
            "_y2ticks_on": None,
            "_x2ticks_on": None,
            "nofirst_x": False,
            "nolast_x": False,
            "nofirst_y": False,
            "nolast_y": False,
            "xplaces": None,
            "yplaces": None,
            "xnames": None,
            "ynames": None,
            # Raw source text of a parsed '*places'/'*names' line, kept only
            # so it can be restored to passthrough verbatim if a later
            # length-mismatch check (see _reconcile_places_names) finds the pairing
            # unrepresentable on the model.
            "_xplaces_raw": None,
            "_yplaces_raw": None,
            "_xnames_raw": None,
            "_ynames_raw": None,
            "key_line": False,  # a modelled 'key' option line was read
            "key_pos": None,  # short-form position or None
            "key_off": False,
            "key_hei": None,  # 'hei' in cm, or None (= inherit 'set hei')
            "key_nobox": False,
            "key_offset": None,  # (dx_cm, dy_cm) or None
            "key_compact": False,
            "key_background": None,  # GLE colour text, or None
            "key_spacing": {},  # GLE word (llen, dist, ...) -> cm
            "key_separators": 0,  # bare ``key separator`` lines -> ncol - 1
            "_draw_seq_counter": 0,  # display-command order = GLE draw order
            "lines": [],
            "scatters": [],
            "bars": [],
            "hists": [],
            "functions": [],
            "fits": [],
            "derived_series": [],
            "fills": [],
            "errorbars": [],
            "file_series": [],
            "heatmaps": [],
            "contours": [],
            # Placed images, from ``begin layer`` / ``draw gleplot_bitmap``
            # (or ``gleplot_postscript``) blocks -- see _image_block.
            "images": [],
            # Guides recovered from a ``! gleplot:guide`` marker, over the
            # dataset they materialized into (G18-lite) or over their drawing
            # after ``end graph``. Recognition keys off the literal marker
            # and nothing else, so a hand-written two-point line is never
            # mistaken for one -- see _prescan_guide_markers and
            # _scan_post_graph_guides.
            "reflines": [],
            "spans": [],
            # dataset name (the first one the guide's 'data' statement
            # declares) -> the parsed marker claiming it. Consumed when the
            # dataset's own display command turns out to match what the
            # marker says; whatever is left when the block ends is a marker
            # whose emission was edited out from under it, and degrades to a
            # plain-series parse with a note (see _discard_guide_markers).
            "_guide_markers": {},
            # Source lines of every marker comment, matched or not: a marker
            # is gleplot's own byte and never reaches passthrough, so it can
            # never be re-emitted beside a dataset it no longer describes.
            "_guide_marker_lines": set(),
            # Dataset names carrying nothing but a recovered guide's legend
            # entry (the data-free ``dN ... key "..."`` bridge the writer
            # emits for a labelled guide drawn after the graph). Skipped in
            # pass 2 rather than fabricated into a phantom series, exactly as
            # ``_key_suppress_datasets`` is.
            "_guide_key_datasets": set(),
            "passthrough": [],
            "trailing_passthrough": [],
            "series_order": [],  # to preserve ordering info if needed
            # Dataset names (e.g. 'd1') consumed by a 'bar'/'fill' command.
            # The writer emits a standalone 'dN key ""' statement right after
            # 'bar'/'fill' to neutralize GLE's auto-key-from-header behavior
            # (bar/fill have no 'key' sub-option of their own -- see
            # gleplot.writer.GLEWriter.add_bar/add_fill). That
            # bare 'dN key ""' would otherwise look like a brand-new,
            # unlabeled line/scatter series to the generic dN-dispatch below;
            # this set lets pass 2 recognize and skip it as a suppression
            # marker instead of fabricating a phantom series.
            "_key_suppress_datasets": set(),
            # Dataset name -> the bar/fill/span/file-series entry that owns
            # it. A following ``dN key "label"`` or ``dN keyfill C key
            # "label"`` sets that entry's label instead of becoming a series.
            "_key_label_owners": {},
            # dataset name (e.g. 'd10') -> vertical offset, for datasets the
            # writer defines via 'let dK = dJ+off' to stack a waterfall/overlay
            # trace at plot time. The recovered series carries the RAW file
            # values plus this offset as an editable property (the offset never
            # touches the .dat file). See _parse_let_command.
            "_dataset_offsets": {},
            # Names of 'let' targets recognized as offset aliases, so pass 2
            # consumes those 'let' lines instead of preserving them as raw GLE.
            "_offset_let_datasets": set(),
            # Names of 'let' SOURCE datasets (the dJ in 'let dK = dJ+off'),
            # consumed indirectly through the alias -- see _parse_let_command
            # and the 'data'-statement reconciliation in _restore_orphaned_data_stmts.
            "_let_source_datasets": set(),
            # Datasets whose ``dN`` line stays raw GLE (an unmodelled
            # ``mdata``, with the size dataset it names; a constant error
            # that cannot become a column). Their ``data`` statement is kept
            # too: nothing else writes it.
            "_raw_datasets": set(),
            # Target of each ``let`` in the block -> the line of its first.
            "_let_lines": {},
            # Let targets kept raw that another note already explains.
            "_explained_lets": set(),
            # ``let dK = (dJ-a)/(b-a)`` statements that map a per-point
            # colour's values (``_CDATA_LET_RE``), keyed by target, with the
            # source, the limits and the raw text. Consumed by the scatter
            # whose ``mdata`` names the target, or kept raw with it.
            "_colour_lets": {},
            # ``let dK = hist dJ ...`` recorded in pass 1, keyed by the
            # target. The target is not registered as a file dataset: its
            # points are bin centres GLE computes, and a later plain ``dK
            # line`` must not be read as a plot of the samples.
            "_hist_lets": {},
            # Target -> the let statement's own text, until a modellable
            # display command consumes it. Anything left is raw GLE.
            "_hist_let_pending": {},
            # ``let dK = <expression> [from a] [to b] [step h]`` targets
            # whose only use is a plain ``dK line``, -> FunctionSeries fields.
            # Decided at the end of pass 1, so a let that stays raw keeps
            # its place in the block.
            "_function_lets": {},
            # Model fit key expression -> label (_model_fit_attr_toks).
            "_fit_key_labels": {},
            # ``let dK = <expression naming datasets> [options]`` targets
            # whose only use is a plain ``dK line`` -> DerivedSeries fields.
            # Decided at the end of pass 2, once the series its datasets
            # became are known; until then its lines are passthrough.
            "_derived_lets": {},
            # Raw dataset name -> the line, scatter, file line, function or
            # fit series built from it: what a derived let's ``dN`` reads.
            "_dataset_series": {},
            # Raw dataset name -> (series, role): the series a raw line that
            # reads the name is bound to, and which of its datasets
            # (``_XYSeries._gle_names``). See ``_note_raw_name``.
            "_raw_names": {},
            # Offset alias target -> its source (``let dK = dJ+off``).
            "_offset_let_sources": {},
            # A polar axes (GLEWriter.add_polar_frame): the radial limit from
            # its grid draw, or None. In a polar graph, each
            # ``let dK = dJ*cos(x),dJ*sin(x)`` maps dK -> dJ: the block is read
            # as if dJ were drawn, in (theta, r).
            "polar_rmax": None,
            "_polar_aliases": {},
            # Dataset names whose ``bar`` commands stay raw: an unmodelled
            # sub-command, a ``fill`` that still needs the original data
            # line, or a group whose x columns do not match. Filled at the
            # end of pass 1. See ``_mark_bars_that_stay_raw``.
            "_bar_hold_raw": set(),
            "_bar_group_next": 1,
        }
        # This graph block's own (begin, end) line span -- the fallback
        # location for a note about the block as a whole (no single statement
        # is more specific), e.g. an implicit legend inferred from labeled
        # series with no 'key' command anywhere in it. Assigned outside the
        # literal above so it does not widen that dict's inferred value type.
        info["_block_span"] = (
            block.begin.line_no,
            block.end.line_no if block.end is not None else block.begin.line_no,
        )
        return info

    def _collect_datasets(self, block: GraphBlock, info) -> _GraphDatasets:
        """Pass 1: collect data commands and merge each dataset's ``dN`` lines.

        This fixes forward references ('d1 line ...' appearing before its
        'data' command) and multi-line attribute accumulation ('d1 line' /
        'd1 lwidth X' / 'd1 key "A"' on separate lines are ONE series, not
        three).
        """
        pass1 = _GraphDatasets()
        # GLE clears its datasets at 'begin graph'; so do the options.
        self._data_read_options.clear()
        self._held_datasets.clear()
        self._noted_unloaded.clear()
        redefined = self._redefined_let_datasets(block)
        for child in block.body:
            if not isinstance(child, Statement) or self._skip_meta_stmt(child):
                continue
            kw = child.keyword
            target = self._let_target(child) if kw == "let" else None
            if target is not None:
                info["_let_lines"].setdefault(target, child.line_no)
            if target is not None and target in redefined:
                self._hold_dataset(target, pass1.datasets)
                continue
            if kw == "data":
                names = self._parse_data_command(
                    _words_and_values(child), pass1.datasets, line_no=child.line_no
                )
                if redefined.intersection(names):
                    # Read by a redefined let: the statement stays as
                    # written, with every line reading its datasets.
                    for name in names:
                        self._hold_dataset(name, pass1.datasets)
                    names = []
                # One defining no dataset (an unresolved file, a lone text
                # column GLE reads as x labels, or an option gleplot cannot
                # write back) is restored as written.
                pass1.data_stmts.append(
                    (
                        names,
                        self._stmt_text(child),
                        child.line_no,
                        {name: pass1.datasets[name] for name in names},
                        (
                            dict(self._data_read_options.get(names[0], {}))
                            if names
                            else {}
                        ),
                    )
                )
                if names:
                    # An axis or polygon fill uses one of these names.
                    # Modelling it while the statement still declares
                    # others would drop this line and rewrite the file
                    # down to that one curve (see _parse_fill_command).
                    group = info.setdefault("_dataset_group", {})
                    for name in names:
                        group[name] = names
            elif kw == "let" and self._polar_let(child, pass1, info):
                continue
            elif kw == "let":
                # 'let dK = dJ+off' -- register dK as an offset alias of dJ
                # (dJ's 'data' command precedes it in body order, so dJ is
                # already known here in pass 1). A 'let dK = hist dJ' is
                # recorded separately: the display command that follows
                # decides whether it becomes a histogram.
                let_toks = _words_and_values(child)
                if self._hold_let_target(let_toks, pass1.datasets):
                    continue
                self._parse_let_command(let_toks, pass1.datasets, info)
                self._record_hist_let(
                    let_toks,
                    pass1.datasets,
                    info,
                    self._stmt_text(child),
                    child.line_no,
                )
                self._record_function_let(let_toks, info)
                self._record_fit_let(let_toks, pass1.datasets, info)
                self._record_derived_let(let_toks, info)
                self._record_colour_let(child, pass1.datasets, info)
            elif kw is not None and _DATASET_RE.match(kw):
                kw = info["_polar_aliases"].get(kw, kw)
                if kw not in pass1.merged_attr_toks:
                    pass1.merged_attr_toks[kw] = []
                    pass1.merged_attr_raw[kw] = []
                pass1.merged_attr_toks[kw].extend(_words_and_values(child)[1:])
                pass1.merged_attr_raw[kw].append(self._stmt_text(child))
        self._keep_unloaded_offset_lets(pass1, info)
        # Histogram and colour lets are filtered first: a function let stays
        # modelled beside the ones still recorded.
        self._keep_owned_hist_lets(block, pass1, info)
        self._keep_colour_lets(pass1, info)
        self._keep_plain_derived_lets(block, pass1, info)
        self._keep_plain_function_lets(block, pass1, info)
        return pass1

    @staticmethod
    def _let_target(stmt) -> Optional[str]:
        """The ``dK`` a ``let`` statement defines, lowercased, or None."""
        toks = _words_and_values(stmt)
        if len(toks) < 2 or not _DATASET_RE.match(toks[1].value):
            return None
        return toks[1].value.lower()

    def _redefined_let_datasets(self, block: GraphBlock) -> Set[str]:
        """The datasets a ``let`` redefined by a later ``let`` reads or makes.

        gleplot models a dataset that one ``let`` defines. When a later
        ``let`` in ``block`` redefines it, both stay raw GLE, and so does
        each dataset they read and each ``let`` that reads one of those
        (each target is noted once).
        """
        lets = []
        for child in block.body:
            if isinstance(child, Statement) and child.keyword == "let":
                target = self._let_target(child)
                if target is not None:
                    toks = _words_and_values(child)
                    reads = " ".join(tok.value for tok in toks[2:])
                    names = {m.lower() for m in _DATASET_NAME_RE.findall(reads)}
                    lets.append((target, names, child.line_no))
        counts = collections.Counter(target for target, _names, _line in lets)
        held: Set[str] = set()
        for target, _names, line_no in lets:
            if counts[target] > 1 and target not in held:
                held.add(target)
                self._note(
                    ImportCategory.DATA,
                    f"{target} is defined by more than one let; those lets, "
                    "the data they read and the lines that draw them were "
                    "kept as raw GLE",
                    (line_no, line_no),
                )
        grown = True
        while grown:
            size = len(held)
            for target, names, _line_no in lets:
                if target in held:
                    held |= names
                elif names & held:
                    held.add(target)
            grown = len(held) != size
        return held

    def _record_colour_let(self, stmt, datasets, info) -> None:
        """Record a per-point colour's ``let`` (see ``_CDATA_LET_RE``)."""
        raw = self._stmt_text(stmt)
        match = _CDATA_LET_RE.match(raw)
        if match is None or match.group(2).lower() not in datasets:
            return
        target, source, op, shift, high = match.groups()
        try:
            low = float(shift) if op == "-" else -float(shift)
            high_value = low if high is None else float(high)
        except ValueError:
            return
        info["_colour_lets"][target.lower()] = {
            "source": source.lower(),
            "vmin": low,
            "vmax": high_value,
            "raw": raw,
        }

    @staticmethod
    def _keep_colour_lets(pass1: _GraphDatasets, info) -> None:
        """Drop each recorded colour let that is not one scatter's ``mdata``.

        Kept: a target with no line of its own that exactly one dataset line
        names as ``mdata`` with a ``gleplot_cdata_`` marker, so that line's
        builder either models the let or keeps it raw beside itself.
        """
        if not info["_colour_lets"]:
            return
        users: Dict[str, int] = {}
        for attr_toks in pass1.merged_attr_toks.values():
            words = [tok.value.lower() for tok in attr_toks]
            pairs = dict(zip(words, words[1:]))
            if pairs.get("marker", "").startswith(CDATA_SUB_PREFIX):
                target = pairs.get("mdata")
                if target is not None:
                    users[target] = users.get(target, 0) + 1
        for target in list(info["_colour_lets"]):
            if (
                target in pass1.merged_attr_toks
                or target in pass1.datasets
                or users.get(target) != 1
            ):
                del info["_colour_lets"][target]

    def _parse_graph_comment(self, child: BlankOrComment, info) -> None:
        """Keep a blank line or comment inside a graph block as passthrough."""
        if child.line_no in info["_guide_marker_lines"]:
            # A guide provenance marker: consumed by the prescan, and
            # regenerated from the RefLine/Span on the next save.
            return
        # Blank/comment inside a graph block that the writer never
        # emits -> preserve as axes passthrough (hand-written).
        stmt = child.statement
        if self._skip_meta_stmt(stmt):
            return
        text = stmt.source_line.text if stmt.source_line else stmt.raw
        info["passthrough"].append(text)

    @staticmethod
    def _is_polar_alias(toks, info) -> bool:
        """Whether this ``let`` is a polar curve's (see :meth:`_prescan_polar`)."""
        return len(toks) > 1 and toks[1].value.lower() in info["_polar_aliases"]

    def _polar_let(self, stmt, pass1: _GraphDatasets, info) -> bool:
        """Pass 1 for a polar ``let``: True if it stands for its source.

        Its source must be declared before it, by a ``data`` statement or a
        function ``let``; otherwise the alias is dropped and the ``let``
        is read like any other.
        """
        toks = _words_and_values(stmt)
        if not self._is_polar_alias(toks, info):
            return False
        target = toks[1].value.lower()
        source = info["_polar_aliases"][target]
        if source in pass1.datasets or source in info["_function_lets"]:
            return True
        del info["_polar_aliases"][target]
        return False

    @staticmethod
    def _let_is_consumed(toks, info) -> bool:
        """True if pass 1 already modeled this ``let`` statement.

        A recognized offset alias is consumed (the offset now lives on the
        aliased series). A recorded histogram let is held until its display
        command consumes it (or the block ends and it is flushed as raw GLE).
        Anything else is preserved as raw GLE.
        """
        target = toks[1].value.lower() if len(toks) > 1 else None
        return (
            target in info["_polar_aliases"]
            or target in info["_offset_let_datasets"]
            or target in info["_hist_lets"]
            or target in info["_function_lets"]
            or target in info["_colour_lets"]
        )

    def _parse_dataset_line(
        self, stmt, pass1: _GraphDatasets, info, marker_cfg, smooth_flags
    ) -> None:
        """Build the series for a ``dN`` statement from its merged attributes.

        Only the first statement naming a dataset builds anything; the rest
        were merged into it in pass 1.
        """
        name = info["_polar_aliases"].get(stmt.keyword, stmt.keyword)
        if (
            info["polar_rmax"] is not None
            and stmt.keyword not in info["_polar_aliases"]
        ):
            # In a polar graph gleplot draws every dataset through a polar
            # let; one drawn as it is would be redrawn through one on save.
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"'{stmt.keyword}' is drawn in a polar graph without a polar "
                "let; it was kept as raw GLE",
                (stmt.line_no, stmt.line_no),
            )
            return
        if name in pass1.emitted:
            return
        if name in info["_guide_key_datasets"]:
            # The data-free legend bridge of a recovered guide: the
            # label now lives on the RefLine or Span, and the writer
            # regenerates this line from it. Consume silently.
            pass1.emitted.add(name)
            return
        attr_toks = pass1.merged_attr_toks.get(name, [])
        if name in info["_key_suppress_datasets"]:
            found = self._suppressed_key_label(attr_toks)
            owner = info["_key_label_owners"].get(name)
            if found and owner is not None:
                # ``dN key "label"`` / ``dN keyfill C key "label"``
                # after a bar or fill. The swatch text belongs on
                # that series; the line is not a second series.
                # A keyfill colour that is not the fill colour is
                # kept, so the next save does not repaint the swatch.
                label, keyfill = found
                owner["label"] = label
                self._note_swatch_color(owner, keyfill)
                pass1.emitted.add(name)
                return
        if name in info["_key_suppress_datasets"] and self._is_bare_key_suppression(
            attr_toks
        ):
            # 'dN key ""' with no other attributes, following a
            # 'bar'/'fill' command that already consumed this
            # dataset -- the writer's auto-key-from-header
            # suppression marker (see writer.add_bar /
            # add_fill), not a real second series. Consume
            # silently: no series, no passthrough (matches what the
            # writer will regenerate from the bar/fill entry's
            # column_names on next save).
            pass1.emitted.add(name)
            return
        if name in info["_hist_lets"] and name not in info["_key_suppress_datasets"]:
            # ``dK line hist`` on a ``let dK = hist`` target. A
            # following ``dK key`` belongs to a stepfilled bar and
            # was consumed by the key-suppression path above.
            merged = [Token(TokenType.WORD, name, (0, 0))] + attr_toks
            self._commit_hist_line(
                name,
                merged,
                pass1.datasets,
                info,
                line_no=stmt.line_no,
                raw_stmts=pass1.merged_attr_raw.get(name, []),
            )
            pass1.emitted.add(name)
            return
        if name in info["_function_lets"]:
            self._build_function_series(name, attr_toks, info)
            pass1.emitted.add(name)
            return
        if name in info["_derived_lets"]:
            # Its place in the key is where its line stands.
            info["_derived_lets"][name]["_attr_toks"] = attr_toks
            info["_derived_lets"][name]["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            merged = [Token(TokenType.WORD, name, (0, 0))] + attr_toks
            raw = pass1.merged_attr_raw.get(name, [])
            self._hold_derived_lines(
                name, self._dn_passthrough_lines(merged, raw), info
            )
            pass1.emitted.add(name)
            return
        pass1.emitted.add(name)
        merged = [Token(TokenType.WORD, name, (0, 0))] + attr_toks
        self._parse_series_command(
            merged,
            pass1.datasets,
            info,
            marker_cfg,
            smooth_flags,
            line_no=stmt.line_no,
            raw_stmts=pass1.merged_attr_raw.get(name, []),
        )

    def _flush_hist_lets(self, info) -> None:
        """Keep a histogram ``let`` no display command consumed as raw GLE."""
        for target, raw in list(info["_hist_let_pending"].items()):
            info["passthrough"].append(raw)
            self._note(
                ImportCategory.DATA,
                "histogram let "
                + target
                + " was not paired with a plain 'line hist' or "
                "'bar dN fill'; kept as raw GLE",
                None,
            )
        info["_hist_let_pending"].clear()

    def _restore_orphaned_data_stmts(self, pass1: _GraphDatasets, info) -> None:
        """Keep the ``data`` statements that raw GLE still depends on.

        A statement none of whose datasets became a series is re-emitted
        verbatim. One that also defines datasets only raw ``dN`` lines draw
        gets a statement of its own for those, when :meth:`_orphan_data_clause`
        can write one.
        """
        # A 'data' statement's own text is never itself modeled -- pass 1
        # only uses it to populate ``datasets`` for lookups, on the
        # assumption that whichever series ends up consuming each dataset
        # name will carry its 'data_file' and have the writer regenerate an
        # equivalent 'data' line. That assumption breaks when a dataset ends
        # up referenced only by raw passthrough text (e.g. a multi-dataset
        # 'bar'/'fill' group kept verbatim, see _parse_bar_command /
        # _parse_fill_command) -- nothing then carries 'data_file' for it, so
        # the writer would silently omit the statement that defines the
        # dataset the passthrough text still refers to, corrupting the
        # regenerated GLE. Restore any 'data' statement whose datasets are
        # entirely unconsumed, ahead of the passthrough content that (being
        # later in body order) may depend on it.
        # A held dataset is drawn by raw lines too (see _hold_dataset).
        raw = info["_raw_datasets"] | self._held_datasets
        consumed = (
            set(info["_key_suppress_datasets"])
            | pass1.emitted
            | info["_let_source_datasets"]
        ) - raw
        # A dataset may also be consumed indirectly, referenced by NAME from
        # another dataset's own attributes rather than having a 'dN ...'
        # line of its own -- e.g. errorbar's 'd1 ... err d2 ...' points at a
        # sibling dataset holding the error column. Such a reference is
        # resolved by the consuming series' own 'data_file'/columns, so it
        # is not orphaned even though it never appears in ``pass1.emitted``.
        for name, attr_toks in pass1.merged_attr_toks.items():
            if name in raw:
                continue
            for t in attr_toks:
                if _DATASET_RE.match(t.value):
                    consumed.add(t.value.lower())
        # What the raw dN lines draw: their own datasets and any they name.
        raw_refs = set(raw)
        for name in raw:
            for t in pass1.merged_attr_toks.get(name, ()):
                if _DATASET_RE.match(t.value):
                    raw_refs.add(t.value.lower())
        # Raw lines that may read a dataset; a comment or a string never does.
        raw_code = [re.sub(r'"[^"]*"|!.*', "", line) for line in info["passthrough"]]
        restored: List[str] = []
        for names, text, data_line_no, defs, read_options in pass1.data_stmts:
            if not any(n in consumed for n in names):
                restored.append(text)
            elif not all(n in consumed for n in names):
                # Mixed: some of this statement's datasets became real
                # series (the writer will regenerate a 'data' line for
                # those), others are orphaned (raw text refers to them but
                # nothing carries 'data_file' for them), and any others are
                # read by nothing. Re-emitting the whole original line would
                # duplicate the modeled portion; dropping it silently loses
                # the orphans.
                orphans = [
                    n
                    for n in names
                    if n not in consumed
                    and (n in raw_refs or _mention_count(raw_code, n))
                ]
                if not orphans:
                    # The rest are read by nothing: dropping them loses nothing.
                    continue
                clause = self._orphan_data_clause(
                    [(n, defs[n]) for n in orphans], read_options, info
                )
                if clause is not None:
                    restored.append(clause)
                    continue
                # Otherwise surface it instead of guessing.
                #
                # A bar that cannot be modeled (an unmodelled sub-command, or
                # a dataset shared with a fill that stays raw) is held with
                # every name on its data statement, so this branch is not
                # how a stack is kept consistent. For an imported (owned)
                # file there is no narrower fix: synthesizing a second 'data'
                # clause for just the orphaned names would reference columns
                # the modeled series' OWN regenerated sidecar no longer
                # carries (GLEWriter always rewrites an owned series' data
                # file with exactly the columns it uses -- see
                # GLEWriter.add_bar/_write_columns), which would
                # silently corrupt the file instead of fixing the reference.
                self._note(
                    ImportCategory.DATA,
                    "'"
                    + text.strip()
                    + "' mixes datasets that became series with datasets "
                    "only referenced by raw GLE; the raw reference(s) may "
                    "not resolve after save",
                    (data_line_no, data_line_no),
                )
        if restored:
            info["passthrough"][0:0] = restored

    def _orphan_data_clause(self, defs, read_options, info) -> Optional[str]:
        """A ``data`` statement defining just ``defs``, or ``None``.

        ``defs`` pairs each dataset name with its (file, x column, y column).
        Only for a file read in place that no recovered series writes: the
        columns the original statement gave these datasets are then still
        there on re-save. An index-x dataset is written with ``c0``, which
        GLE reads as the point index.
        """
        data_file = defs[0][1][0]
        if self._is_import(data_file) or any(
            series.get("data_file") == data_file
            for attr in SERIES_CLASSES
            if attr != FileSeries.ATTR
            for series in info.get(attr, ())
        ):
            return None
        clauses = []
        for name, (_file, xcol, ycol) in defs:
            clauses.append(f" {name}=c{xcol},c{ycol}")
        return (
            f"    data {_format_data_filename(data_file)}"
            + "".join(clauses)
            + GLEWriter._data_read_clause(FileSeries(**read_options))
        )

    # -- guides drawn against GLE's own range (G17) -----------------------

    #: ``let dK = dJ*cos(x),dJ*sin(x)``, as GLEWriter._polar_dataset writes it.
    _POLAR_LET_RE = re.compile(
        r"^\s*let\s+(d\d+)\s*=\s*(d\d+)\*cos\(x\),\2\*sin\(x\)\s*$", re.IGNORECASE
    )

    def _prescan_polar(self, block: GraphBlock, info) -> Optional[int]:
        """Find a polar axes' grid draw, and its curves' polar ``let`` lines.

        The grid is the ``begin layer`` block
        :meth:`gleplot.writer.GLEWriter.add_polar_frame` writes, matched
        exactly: its layer, a lone ``draw gleplot_polar_grid rmax step``,
        and the ring step gleplot derives from ``rmax``. On a match the
        radial limit goes in ``info["polar_rmax"]``, every polar ``let`` in
        the block in ``info["_polar_aliases"]``, and the block's line number
        is returned so pass 2 skips it. Anything else returns ``None`` and
        stays raw GLE.
        """
        for child in block.body:
            if not isinstance(child, OpaqueBlock) or child.block_type != "layer":
                continue
            inner = [sl for sl in child.inner_lines if sl.text.strip()]
            if len(inner) != 1:
                continue
            stmt = _first_statement_of(inner[0])
            toks = _words_and_values(stmt)
            if (
                len(toks) < 2
                or (stmt.keyword or "").lower() != "draw"
                or toks[1].value.lower() != "gleplot_polar_grid"
            ):
                continue
            args = self._guide_call_args(toks, 2)
            if (
                self._layer_number(child) != POLAR_GRID_LAYER
                or len(args) != 2
                or not all(isinstance(v, (int, float)) for v in args)
                or not float(cast(float, args[0])) > 0
                or float(cast(float, args[1]))
                != polar_ring_step(float(cast(float, args[0])))
            ):
                self._note(
                    ImportCategory.STRUCTURE,
                    "'draw gleplot_polar_grid' is not in the form gleplot "
                    "writes; the block was left as raw GLE instead of being "
                    "read back as a polar axes",
                    (stmt.line_no, stmt.line_no),
                )
                return None
            info["polar_rmax"] = float(cast(float, args[0]))
            for other in block.body:
                if isinstance(other, Statement) and other.keyword == "let":
                    match = self._POLAR_LET_RE.match(self._stmt_text(other))
                    if match:
                        target, source = match.group(1).lower(), match.group(2).lower()
                        info["_polar_aliases"][target] = source
            return child.line_no
        return None

    #: The graph-block lines ``Axes._frame_off`` writes, each bare.
    _FRAME_OFF_KEYWORDS = ("xside", "yside", "xticks", "yticks")

    @classmethod
    def _prescan_frame_off(cls, block: GraphBlock) -> Set[int]:
        """Line numbers of the four ``... off`` lines a hidden frame writes.

        ``xside off``, ``yside off``, ``xticks off`` and ``yticks off`` are
        recovered together as ``Axes._frame_off``, and only when each appears
        exactly once. Otherwise the set is empty and every one of them stays
        raw GLE, as before. An ``xticks off`` directly followed by
        ``xlabels off`` is an empty places list (see
        :meth:`_is_empty_places`), not part of a hidden frame.
        """
        found: Dict[str, List[int]] = {kw: [] for kw in cls._FRAME_OFF_KEYWORDS}
        statements = [c for c in block.body if isinstance(c, Statement)]
        for child, following in zip(statements, statements[1:] + [None]):
            kw = (child.keyword or "").lower()
            if kw not in found or not cls._is_bare_off(child):
                continue
            if (
                kw in ("xticks", "yticks")
                and following is not None
                and (following.keyword or "").lower() == f"{kw[0]}labels"
                and cls._is_bare_off(following)
            ):
                continue
            found[kw].append(child.line_no)
        if any(len(lines) != 1 for lines in found.values()):
            return set()
        return {lines[0] for lines in found.values()}

    @staticmethod
    def _is_bare_off(stmt: Statement) -> bool:
        """``<keyword> off`` and nothing else."""
        toks = _words_and_values(stmt)
        return len(toks) == 2 and toks[1].value.lower() == "off"

    #: The statements whose ``on`` may switch the top or right axis on.
    _SWITCH_ON_KEYWORDS = {
        "xaxis": "x2",
        "x2axis": "x2",
        "xlabels": "x2",
        "x2labels": "x2",
        "yaxis": "y2",
        "y2axis": "y2",
        "ylabels": "y2",
        "y2labels": "y2",
    }
    #: Axis options that take ``on``/``off`` as their own argument.
    _ON_OFF_OPTIONS = ("symticks", "first", "last", "roundrange")

    @classmethod
    def _prescan_switched_on(cls, block: GraphBlock) -> Set[str]:
        """``'x2'`` / ``'y2'`` when a statement may switch that axis on.

        An ``on`` on an ``xaxis``/``x2axis``/``xlabels``/``x2labels`` line
        (and the y twins) turns the top (right) axis back on wherever it
        stands, since GLE copies an x setting onto x2. An ``x2axis off``
        is modeled as ``Axes._x2axis_off`` only without one, because the
        writer would put the ``off`` back in a different place.
        """
        found: Set[str] = set()
        for child in block.body:
            if not isinstance(child, Statement):
                continue
            prefix = cls._SWITCH_ON_KEYWORDS.get((child.keyword or "").lower())
            if prefix is None:
                continue
            words = [t.value.lower() for t in _words_and_values(child)]
            if any(
                word == "on" and words[i - 1] not in cls._ON_OFF_OPTIONS
                for i, word in enumerate(words[1:], 1)
            ):
                found.add(prefix)
        return found

    @staticmethod
    def _prescan_math(block: GraphBlock) -> Optional[int]:
        """Line number of a bare ``math`` recovered as ``Axes.math_mode``.

        Only a ``math`` that nothing but graph geometry precedes is
        recovered, because the writer puts it there. ``math`` overrides axis
        offsets, ``symticks`` and x2/y2 ``on`` set before it, so moving a
        later one to the top could change the plot: it stays raw GLE.
        """
        for child in block.body:
            if isinstance(child, BlankOrComment):
                continue
            if not isinstance(child, Statement):
                return None
            kw = (child.keyword or "").lower()
            if kw in ("size", "scale", "fullsize"):
                continue
            if kw == "math" and len(_words_and_values(child)) == 1:
                return child.line_no
            return None
        return None

    # -- guides drawn after 'end graph' (gleplot.guides) ------------------

    def _scan_post_graph_guides(
        self, nodes, start: int, notes: bool = True
    ) -> Tuple[List[Series], int]:
        """The guides drawn after a graph's ``end graph``, and where they end.

        Each is a ``! gleplot:guide`` marker followed by the ``gsave`` ..
        ``grestore`` group the writer draws it with. A group is taken only
        when it is exactly what the writer writes from the marker and the
        style it states; the first one that is not ends the scan, is left as
        raw GLE, and gets a note (unless ``notes`` is off, for a prescan).
        """
        guides: List[Series] = []
        i = start
        while i < len(nodes):
            text = _guide_marker_text(nodes[i])
            if text is None:
                break
            group = [text.strip()]
            j = i + 1
            while j < len(nodes) and len(group) < 6:
                st = self._as_statement(nodes[j])
                if st is None:
                    break
                group.append(self._stmt_text(st).strip())
                j += 1
                if (st.keyword or "").lower() == "grestore":
                    break
            entry = self._post_graph_guide(group)
            if entry is None:
                if notes:
                    self._note(
                        ImportCategory.STRUCTURE,
                        "'" + group[0] + "' is not followed by the drawing "
                        "gleplot writes for it after 'end graph'; the lines "
                        "were kept as raw GLE instead of being read back as a "
                        "guide",
                        (nodes[i].statement.line_no, nodes[i].statement.line_no),
                    )
                break
            guides.append(entry)
            i = j
        return guides, i

    def _post_graph_guide(self, group: List[str]) -> Optional[Series]:
        """A ``RefLine``/``Span`` from its after-graph lines, or ``None``."""
        marker = self._parse_guide_marker(group[0])
        if marker is None or len(group) < 4 or group[1].lower() != "gsave":
            return None
        fields = marker["fields"]
        lo, hi = fields["extent"]
        if marker["kind"] == "span":
            box = tokenize_line(group[3])
            fill = [k for k, t in enumerate(box) if t.value.lower() == "fill"]
            if not fill:
                return None
            color, _nxt = _collect_color(box, fill[0] + 1)
            if color is None:
                return None
            span = Span(
                type="span",
                orient=marker["orient"],
                start=fields["range"][0],
                end=fields["range"][1],
                span_lo=lo,
                span_hi=hi,
                color=color,
                # The colour is the exact text re-emitted, alpha folded in.
                alpha=1.0,
                label=marker["label"],
                data_file=None,
            )
            edges = self._written_position(marker, "range")
            if edges is None:
                return None
            expected = GLEWriter.span_draw_lines(span, color, edges)
            return span if expected == group else None
        toks = [t for t in tokenize_line(group[2]) if t.type is not TokenType.COMMENT]
        if [t.value.lower() for t in toks[:2]] != ["set", "color"]:
            return None
        color, k = _collect_color(toks, 2)
        if color is None or k >= len(toks) or toks[k].value.lower() != "lwidth":
            return None
        lwidth, k = _collect_value(toks, k + 1)
        lstyle: Optional[int] = None
        linestyle = "-"
        if k < len(toks) and toks[k].value.lower() == "lstyle":
            number, k = _collect_value(toks, k + 1)
            if number is None or number != int(number):
                return None
            lstyle = int(number)
            linestyle = LSTYLE_TO_MATPLOTLIB.get(lstyle, "-")
        if lwidth is None or k != len(toks):
            return None
        if len(group) == 4:
            linestyle = "none"
        ref = RefLine(
            type="refline",
            orient=marker["orient"],
            value=fields["value"][0],
            span_lo=lo,
            span_hi=hi,
            color=color,
            linestyle=linestyle,
            **_width_fields(linewidth_cm_to_pt(lwidth)),
            label=marker["label"],
            data_file=None,
        )
        value = self._written_position(marker, "value")
        if value is None:
            return None
        expected = GLEWriter.refline_draw_lines(ref, lwidth, lstyle, value[0])
        return ref if expected == group else None

    @staticmethod
    def _written_position(marker: dict, key: str) -> Optional[List[str]]:
        """A guide marker's ``key`` numbers as written, if gleplot's own.

        The writer writes them at the precision of the axis they lie on,
        which is not known here, and draws the guide with the same text: a
        number as six or more significant figures write it. ``None`` for
        any other spelling (``2.50``), which is then kept as raw GLE.
        """
        texts = marker["texts"][key]
        for text, value in zip(texts, marker["fields"][key]):
            if text != GLEWriter._format_number(value) and not any(
                text == f"{value:.{p}g}" for p in range(6, 18)
            ):
                return None
        return texts

    def _seed_post_graph_guides(self, block: GraphBlock, info) -> None:
        """Put the guides read after this graph on its axes, first."""
        guides, self._post_graph_guides = self._post_graph_guides, []
        for entry in guides:
            info[entry.ATTR].append(entry)
        info["_post_graph_guides"] = guides

    def _claim_guide_bridges(self, block: GraphBlock, info, pass1) -> None:
        """Claim the legend lines of the guides drawn after this graph.

        A labelled guide's legend entry is a data-free ``dN`` statement in
        the graph (:meth:`_guide_key_dataset`); each is claimed in order, so
        it is regenerated from the guide rather than read as a series. A
        ``dN`` that pass 1 found filled, by a ``data`` statement (named or
        numbered by GLE) or a ``let``, is never a bridge.
        """
        body = list(block.body)
        filled: Set[str] = set(pass1.datasets)
        for child in body:
            if isinstance(child, Statement) and (child.keyword or "").lower() == "let":
                filled.update(
                    t.value.lower()
                    for t in _words_and_values(child)
                    if t.type is TokenType.WORD and _DATASET_RE.match(t.value)
                )
        claimed = cast(set, info["_guide_key_datasets"])
        for entry in info.pop("_post_graph_guides", []):
            if not entry.get("label"):
                continue
            for j, child in enumerate(body):
                if not isinstance(child, Statement):
                    continue
                name = (child.keyword or "").lower()
                if name in claimed or name in filled:
                    continue
                if self._guide_key_dataset(body, j, entry) == name:
                    claimed.add(name)
                    break

    def _image_block(self, node: OpaqueBlock) -> Optional[PlacedImage]:
        """A placed image's ``begin layer`` / ``draw`` block, or ``None``.

        Like a guide block, it has to match what the writer emits: a
        ``layer`` block at :data:`~gleplot.writer.IMAGE_LAYER` holding one
        ``draw`` of the image sub for the file's extension, with the file
        and an ascending extent. A block that names an image sub but does
        not match is left as raw GLE with a ``structure:`` note.
        """
        if node.block_type != "layer":
            return None
        inner = [sl for sl in node.inner_lines if sl.text.strip()]
        if len(inner) != 1:
            return None
        stmt = _first_statement_of(inner[0])
        toks = _words_and_values(stmt)
        if len(toks) < 2 or (stmt.keyword or "").lower() != "draw":
            return None
        call = toks[1].value.lower()
        if call not in IMAGE_SUBS:
            return None
        args = self._guide_call_args(toks, 2)
        if (
            len(args) == 5
            and isinstance(args[0], str)
            and image_sub_name(args[0]) == call
            and all(isinstance(v, (int, float)) for v in args[1:])
            and self._layer_number(node) == IMAGE_LAYER
        ):
            x0, x1, y0, y1 = (float(cast(float, v)) for v in args[1:])
            if x0 < x1 and y0 < y1:
                return PlacedImage(type="image", file=args[0], extent=[x0, x1, y0, y1])
        self._note(
            ImportCategory.STRUCTURE,
            f"'draw {call}' does not match the image block gleplot writes "
            f"(layer {IMAGE_LAYER}, a file whose type fits the call, and an "
            "ascending extent); the block was left as raw GLE instead of "
            "being read back as an image",
            (stmt.line_no, stmt.line_no),
        )
        return None

    @staticmethod
    def _layer_number(node: OpaqueBlock) -> Optional[int]:
        """``N`` from a ``begin layer N`` opener, or ``None``."""
        toks = _words_and_values(node.begin)
        value, _nxt = _collect_value(toks, 2)  # 'begin' 'layer' N
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _split_call_words(toks: List[Token], start: int) -> List[List[Token]]:
        """Group ``toks[start:]`` into whitespace-delimited runs.

        GLE's own sub-call parser splits arguments on whitespace, full stop
        (probe-verified on GLE 4.3.10: ``draw sub -4 -3 0 1`` passes four
        separate arguments). That is a
        different rule from
        :func:`_collect_value`'s expression grammar, which accepts a bare
        ``-`` as a binary operator regardless of the whitespace around it and
        so reads ``-4 -3`` as the one expression ``-4-3`` (G17.1). Splitting
        on the token *spans* recovered from the lexer -- a gap between two
        tokens starts a new word, no gap keeps them in the same one --
        mirrors GLE's rule exactly and still keeps a spaceless expression
        like ``2*pi`` or a signed literal like ``-4`` (lexed as ``OP '-'`` +
        ``NUMBER '4'`` with no gap between them) together as one argument.
        """
        words: List[List[Token]] = []
        current: List[Token] = []
        prev_end: Optional[int] = None
        for tok in toks[start:]:
            if tok.type is TokenType.COMMENT:
                break
            if prev_end is not None and tok.start != prev_end:
                words.append(current)
                current = []
            current.append(tok)
            prev_end = tok.end
        if current:
            words.append(current)
        return words

    @classmethod
    def _guide_call_args(cls, toks: List[Token], start: int) -> List[object]:
        """The positional arguments of a ``draw gleplot_*`` call.

        Split positionally on whitespace (:meth:`_split_call_words`), not by
        :func:`_collect_value`'s maximal-expression scan -- see that method's
        docstring for why (G17.1). Each resulting word is either a string
        (read by :func:`_string_expr_value`, so an embedded quote survives)
        or a numeric expression
        evaluated whole by :func:`eval_gle_number`. A word that is neither
        ends the scan, which makes the caller reject the call rather than
        half-read it.
        """
        out: List[object] = []
        for word in cls._split_call_words(toks, start):
            text = _string_expr_value(word)
            if text is not None:
                out.append(text)
                continue
            value = eval_gle_number(word)
            if value is None:
                break
            out.append(value)
        return out

    @staticmethod
    def _guide_key_dataset(body, start: int, entry) -> Optional[str]:
        """The ``dN`` name carrying ``entry``'s legend entry, if it has one.

        Checks the first statement at or after ``body[start]``: a line
        ``dN ... key`` for a labelled ``RefLine``, ``dN keyfill ... key``
        for a labelled ``Span``, matched on the key text.
        """
        label = entry.get("label")
        if entry.get("type") not in ("refline", "span") or not label:
            return None
        j = start
        while j < len(body) and isinstance(body[j], BlankOrComment):
            j += 1
        if j >= len(body) or not isinstance(body[j], Statement):
            return None
        stmt = body[j]
        name = (stmt.keyword or "").lower()
        if not _DATASET_RE.match(name):
            return None
        toks = _words_and_values(stmt)
        matched = False
        keyfill = None
        k = 0
        while k < len(toks):
            word = toks[k].value.lower() if toks[k].type is TokenType.WORD else None
            if (
                word == "key"
                and k + 1 < len(toks)
                and toks[k + 1].type is TokenType.STRING
                and _string_value(toks[k + 1]) == label
            ):
                matched = True
                k += 2
                continue
            if word == "keyfill":
                color, nxt = _collect_color(toks, k + 1)
                if color is None or nxt == k + 1:
                    return None
                keyfill = color
                k = nxt
                continue
            k += 1
        if not matched:
            return None
        # A keyfill that is not the band's own colour has to survive the
        # next save. The box still paints the band; only the swatch uses
        # this token.
        if entry.get("type") == "span" and keyfill and keyfill != entry.get("color"):
            entry["swatch_color"] = keyfill
        return name

    # -- guides materialized as datasets, marked by a comment (G18-lite) --

    def _prescan_guide_markers(self, block: GraphBlock, info) -> None:
        """Bind each ``! gleplot:guide`` comment to the dataset it describes.

        The marker carries the model residue the emitted commands cannot
        state -- kind, orientation, coordinates, fractional extent, a band's
        label (:mod:`gleplot.guides`) -- and names its guide by *position*:
        the ``data`` statement it stands immediately above. That statement's
        first dataset name is the key, so when pass 2 reaches that dataset's
        own display command it knows to build a ``RefLine``/``Span`` from the
        two halves rather than the plain series the bytes look like.

        Recognition keys off the literal marker only. A two-point dataset
        with no marker over it -- anything hand-written, and every ``.gle``
        gleplot wrote before G18-lite -- parses exactly as it always did.
        """
        body = list(block.body)
        markers = cast(dict, info["_guide_markers"])
        for i, child in enumerate(body):
            text = _guide_marker_text(child)
            if text is None:
                continue
            span = (child.line_no, child.line_no)
            # Consumed here whatever happens next: a marker is gleplot's own
            # byte, so it must never reach passthrough and be re-emitted
            # beside a dataset it no longer describes.
            cast(set, info["_guide_marker_lines"]).add(child.line_no)
            marker = self._parse_guide_marker(text)
            if marker is None:
                self._note(
                    ImportCategory.STRUCTURE,
                    "'" + text.strip() + "' is not a readable gleplot guide "
                    "marker; it was dropped and the dataset below it imports "
                    "as a plain series",
                    span,
                )
                continue
            name = self._marked_dataset_name(body, i + 1, marker["kind"])
            # A line's label is its key clause here; only the after-graph
            # form carries one in the marker.
            if marker["kind"] == "refline" and marker["label"] is not None:
                name = None
            if name is None or name in markers:
                self._note(
                    ImportCategory.STRUCTURE,
                    "'" + text.strip() + "' does not stand over the 'data' "
                    "statement of the guide it describes; it was dropped and "
                    "the commands below it import as plain series",
                    span,
                )
                continue
            marker["span"] = span
            marker["text"] = text.strip()
            markers[name] = marker

    def _parse_guide_marker(self, text: str) -> Optional[dict]:
        """One ``! gleplot:guide`` comment -> its fields, or ``None``.

        Lexed with GLE's own tokenizer, so a negative coordinate needs no
        bespoke handling; the label's escaped quote is restated first. Every
        required field of the
        kind must be present exactly once (in any order); an unknown keyword,
        a repeat, a missing field or a stray token rejects the whole marker
        rather than half-reading it -- a marker that cannot be read in full
        describes nothing that could be rebuilt from it.
        """
        # The label escapes a quote with a backslash, which the lexer, like
        # GLE, does not read: restate each string with the quote doubled.
        body = _MARKER_STRING_RE.sub(
            lambda m: '"' + m.group(1).replace('\\"', '""') + '"',
            text[len(GUIDE_MARKER_PREFIX) :],
        )
        toks = [t for t in tokenize_line(body) if t.type is not TokenType.COMMENT]
        if len(toks) < 2:
            return None
        kind = toks[0].value.lower()
        orient = toks[1].value.lower()
        if kind not in GUIDE_MARKER_KINDS or orient not in GUIDE_MARKER_ORIENTS:
            return None
        required = dict(GUIDE_MARKER_FIELDS[kind])
        fields: Dict[str, List[float]] = {}
        texts: Dict[str, List[str]] = {}
        label: Optional[str] = None
        i = 2
        m = len(toks)
        while i < m:
            word = toks[i].value.lower()
            if word == GUIDE_MARKER_LABEL:
                if label is not None or i + 1 >= m:
                    return None
                if toks[i + 1].type is not TokenType.STRING:
                    return None
                label = _string_value(toks[i + 1])
                i += 2
                continue
            arity = required.get(word)
            if arity is None or word in fields:
                return None
            values: List[float] = []
            written: List[str] = []
            j = i + 1
            for position in range(arity):
                if position:
                    # The separator is required, not decoration: GLE's lexer
                    # reads a leading sign as an operator, so without the
                    # comma 'range -4 -3' collects as the one expression -7.
                    if j >= m or toks[j].value != ",":
                        return None
                    j += 1
                start = j
                value, j = _collect_value(toks, j)
                if value is None:
                    return None
                values.append(value)
                written.append("".join(t.value for t in toks[start:j]))
            fields[word] = values
            texts[word] = written
            i = j
        if set(fields) != set(required):
            return None
        return {
            "kind": kind,
            "orient": orient,
            "fields": fields,
            "texts": texts,
            "label": label,
        }

    @staticmethod
    def _marked_dataset_name(body, start: int, kind: str) -> Optional[str]:
        """The first dataset name of the ``data`` statement a marker stands on.

        Blank lines between the marker and its ``data`` statement are
        tolerated (gleplot emits none, a human might add one); another marker
        is not -- that would mean this one's own emission is gone. The
        dataset count is checked against the kind, so a marker over the wrong
        statement is rejected here rather than mis-bound.
        """
        j = start
        while j < len(body) and isinstance(body[j], BlankOrComment):
            if _guide_marker_text(body[j]) is not None:
                return None
            j += 1
        if j >= len(body) or not isinstance(body[j], Statement):
            return None
        stmt = body[j]
        if (stmt.keyword or "").lower() != "data":
            return None
        names = [
            t.value.lower()
            for t in _words_and_values(stmt)
            if t.type is TokenType.WORD and _DATASET_RE.match(t.value)
        ]
        # A refline is one dataset (x,y); a band is two (x,upper and x,lower).
        if len(names) != (1 if kind == "refline" else 2):
            return None
        return names[0]

    def _take_guide_marker(self, d_name: str, kind: str, info) -> Optional[dict]:
        """Claim the marker on ``d_name``, if it is one of ``kind``."""
        marker = cast(dict, info["_guide_markers"]).get(d_name)
        if marker is None or marker["kind"] != kind:
            return None
        return marker

    @staticmethod
    def _guide_coord_matches(value: float, *found: float) -> bool:
        """Whether an emitted coordinate is the one the marker claims.

        Both sides are written by ``GLEWriter._format_number`` -- the marker's
        number and the sidecar's rows alike -- so they agree exactly; the
        tolerance is for the parse, not for the difference between a guide at
        1.5 and a guide someone moved to 2.
        """
        return all(
            math.isclose(value, other, rel_tol=1e-9, abs_tol=1e-12) for other in found
        )

    def _refline_from_marker(self, marker, entry, attrs, d_name, info):
        """Rebuild a ``RefLine`` from its marker plus its own ``dN`` command.

        Returns ``None`` -- leaving the marker unclaimed, which
        :meth:`_discard_guide_markers` turns into a note -- whenever the
        emission and the marker disagree, i.e. whenever one side was edited
        after the other was written:

        * the dataset is not the two rows a guide materializes into, or its
          constant coordinate is not the one the marker claims (someone moved
          the guide by editing the ``.dat``);
        * the display command carries something no guide emission has: a
          marker, a ``y2axis`` binding, an offset ``let``, smoothing, a
          dataset qualifier (``mdist``, ``deresolve``, a data range);
        * or lacks the ``color`` and ``lwidth`` every guide emission writes.

        Never guessed at, never half-applied: the caller then appends the
        plain ``LineSeries`` it already built, which is exactly what this file
        recovered before G18-lite.
        """
        if attrs["marker"] is not None or attrs["y2axis"] or attrs.get("x2axis"):
            return None
        if entry.get("offset") or attrs["smooth_mode"] != "none":
            return None
        # A line mode is not something a guide emission carries. Keeping the
        # series as a line is what preserves ``steps`` / ``impulses`` / ...
        if attrs.get("line_mode"):
            return None
        if attrs["svg_smooth"] is not None or attrs["qualifiers"]:
            return None
        if entry["color"] is None or entry["linewidth"] is None:
            return None
        x = np.asarray(entry["x"], dtype=float)
        y = np.asarray(entry["y"], dtype=float)
        if x.size != 2 or y.size != 2:
            return None
        (value,) = marker["fields"]["value"]
        along = x if marker["orient"] == "v" else y
        if not self._guide_coord_matches(value, *along.tolist()):
            return None
        lo, hi = marker["fields"]["extent"]
        ref = RefLine(
            type="refline",
            orient=marker["orient"],
            value=value,
            span_lo=lo,
            span_hi=hi,
            # Style, label and sidecar come from the visible commands: the
            # marker carries only what they cannot state (gleplot.guides).
            color=entry["color"],
            linestyle=entry["linestyle"],
            **_width_fields(entry["linewidth"]),
            label=entry["label"],
            data_file=entry["data_file"],
        )
        if "column_names" in entry:
            ref["column_names"] = entry["column_names"]
        del cast(dict, info["_guide_markers"])[d_name]
        return ref

    def _span_from_marker(self, marker, entry, d_name, info):
        """Rebuild a ``Span`` from its marker plus its own ``fill`` command.

        The band's edges are its dataset's two constant columns and its
        position is the other column's two rows, so the same cross-check as
        :meth:`_refline_from_marker` applies to both. ``alpha`` comes back
        1.0 over the emitted colour text, exactly as a hand-written fill's
        does -- see the ``alpha`` note in :meth:`_parse_fill_command`, and
        :mod:`gleplot.guides` for why the marker deliberately does not carry
        it.
        """
        if entry.get("offset") or entry.get("_offset2"):
            return None
        x = np.asarray(entry["x"], dtype=float)
        upper = np.asarray(entry["y1"], dtype=float)
        lower = np.asarray(entry["y2"], dtype=float)
        if x.size != 2 or upper.size != 2 or lower.size != 2:
            return None
        start, end = marker["fields"]["range"]
        if marker["orient"] == "v":
            ok = (
                self._guide_coord_matches(start, x[0])
                and self._guide_coord_matches(end, x[1])
                and self._guide_coord_matches(upper[0], upper[1])
                and self._guide_coord_matches(lower[0], lower[1])
            )
        else:
            # The x column is this band's fractional extent, already resolved
            # against the axis range -- unrecoverable, and the marker's own
            # business (gleplot.guides). Only the edges are cross-checkable.
            ok = self._guide_coord_matches(
                end, *upper.tolist()
            ) and self._guide_coord_matches(start, *lower.tolist())
        if not ok:
            return None
        lo, hi = marker["fields"]["extent"]
        span = Span(
            type="span",
            orient=marker["orient"],
            start=start,
            end=end,
            span_lo=lo,
            span_hi=hi,
            color=entry["color"],
            alpha=entry["alpha"],
            label=marker["label"],
            data_file=entry["data_file"],
        )
        if "column_names" in entry:
            span["column_names"] = entry["column_names"]
        del cast(dict, info["_guide_markers"])[d_name]
        return span

    def _discard_guide_markers(self, info) -> None:
        """Note every marker whose emission did not match it, and drop it.

        Reached when the ``.gle`` was edited on one side only: the display
        command deleted or restyled beyond what a guide emits, the sidecar
        moved, the dataset never displayed at all. The commands themselves
        are untouched (they have already become plain series, or passthrough,
        by the ordinary rules); what is lost is the guide identity the marker
        claimed, which is the smaller loss and the only one that was already
        inconsistent with the file.
        """
        markers = cast(dict, info["_guide_markers"])
        for marker in markers.values():
            self._note(
                ImportCategory.STRUCTURE,
                "'"
                + marker["text"]
                + "' does not describe the commands beside it (the file was "
                "edited); the marker was dropped and they import as plain "
                "series, not as a guide",
                marker["span"],
            )
        markers.clear()

    def _x2_lin_will_emit(self, info) -> bool:
        """Whether :meth:`GLEWriter.add_axes` will write ``x2axis ... lin``.

        Mirrors that method's ``x2_lin``: the primary axis is log, the top
        scale is linear, and the top scale is actually in use. A ``lin``
        outside that case is preserved as passthrough instead of dropped.
        """
        if not info["xlog"] or info["x2log"]:
            return False
        if (
            info["x2min"] is not None
            or info["x2max"] is not None
            or bool(info["x2label"])
            or info["x2format"] is not None
            or info["x2angle"] is not None
            or info["x2labels_hei"] is not None
            or info["x2labels_color"] is not None
        ):
            return True
        for group in ("lines", "scatters", "errorbars", "hists", "file_series"):
            for series in info[group]:
                if series.get("xaxis") == "x2":
                    return True
        return False

    def _reconcile_axis_styling(self, info) -> None:
        """Decide what the parked ``*ticks``/``y2labels on`` lines meant.

        Run once the whole graph block has been read, because GLE does not
        fix the order of these statements relative to the ``xaxis ... grid``
        that gives them their meaning:

        * ``xticks``/``xsubticks`` style is grid style when that axis HAS a
          grid. Without one it is the tick marks (see
          :meth:`_reconcile_tick_marks`).
        * A subtick grid must be styled exactly like the main grid for one
          ``lstyle``/``lwidth`` pair to describe both (subticks inherit only
          the tick colour -- see ``GLEWriter._add_grid_style``). A file that
          styles them differently keeps its ``xsubticks`` line as raw GLE.
        * ``y2labels on`` is implied by any modeled y2 tick-label property,
          OR by the y2 axis being configured at all (explicit limits, log
          scale or title -- see ``GLEWriter.add_axes``'s ``y2_used``, which
          this mirrors): GLE only auto-enables y2 labels on its own when a
          plotted dataset uses the axis, not when it is merely configured,
          so the writer now emits ``y2labels on`` for that case too. Only
          when NEITHER holds is it a bare visibility switch the model does
          not have, preserved as passthrough.
        * ``xside off`` hides the bottom line alone (``Axes.xside_off``)
          only when the top line is switched back on after it
          (``x2side on``) or the top axis is off: GLE copies it onto x2.
          Otherwise it hides both lines, which the model cannot say, and
          the ``off`` stays raw GLE where it stood among the raw lines (the
          y twin likewise).
        """
        demoted = []
        for prefix, mirror in (("x", "x2"), ("y", "y2")):
            side = info[f"{prefix}side"]
            if side is None or not side["off"]:
                continue
            restore = info[f"{mirror}side"]
            if (restore is not None and restore["off"] is False) or info[
                f"{mirror}axis_off"
            ]:
                continue
            side["off"] = None
            demoted.append((side["at"], prefix, mirror))
        # Latest first, so an insert does not shift the other's index.
        for at, prefix, mirror in sorted(demoted, reverse=True):
            info["passthrough"].insert(at, f"    {prefix}side off")
            self._note(
                ImportCategory.STRUCTURE,
                f"'{prefix}side off' also hides the {mirror} line; kept as raw "
                "GLE, not editable",
                None,
            )
        for prefix in ("x", "y"):
            ticks = info[f"_{prefix}ticks"]
            subticks = info[f"_{prefix}subticks"]
            gridded = info[f"{prefix}grid"]
            if self._is_empty_places(prefix, ticks, subticks, info):
                # 'xticks off' + 'xlabels off' is how GLEWriter writes an
                # empty places list (GLE ignores an empty 'xplaces'). On a
                # log axis it adds 'xsubticks on' for matplotlib's minor
                # ticks, so a log axis without it had them switched off.
                info[f"{prefix}places"] = []
                info[f"{prefix}labels_off"] = False
                info[f"_{prefix}ticks"] = None
                info[f"_{prefix}subticks"] = None
                log = info[f"{prefix}log"]
                if not gridded and log == (subticks is None):
                    # A log axis without the line had its minor ticks
                    # switched off; a linear one with it had them asked for.
                    on = subticks is not None
                    info[f"_{prefix}subtick_marks"] = dict(
                        length=None, lwidth=None, color=None, on=on, off=not on
                    )
                continue
            if not gridded:
                self._reconcile_tick_marks(prefix, ticks, subticks, info)
                continue
            if ticks is not None and not (
                ticks["ok"]
                and not ticks["on"]
                and not ticks["off"]
                and ticks["length"] is None
            ):
                info["passthrough"].append(ticks["raw"])
                ticks_line = ticks["line_no"]
                self._note(
                    ImportCategory.STRUCTURE,
                    f"{prefix}ticks styling without a modeled grid; "
                    "kept as raw GLE, not editable",
                    (ticks_line, ticks_line) if ticks_line is not None else None,
                )
                info[f"_{prefix}ticks"] = ticks = None
            if subticks is None:
                continue
            styled_alike = subticks["lstyle"] == (
                ticks["lstyle"] if ticks else None
            ) and subticks["lwidth"] == (ticks["lwidth"] if ticks else None)
            if not (
                subticks["ok"]
                and subticks["on"]
                and subticks["length"] is None
                and subticks["color"] is None
                and styled_alike
            ):
                info["passthrough"].append(subticks["raw"])
                subticks_line = subticks["line_no"]
                self._note(
                    ImportCategory.STRUCTURE,
                    f"{prefix}subticks line is not a modeled grid "
                    "mode; kept as raw GLE, not editable",
                    (
                        (subticks_line, subticks_line)
                        if subticks_line is not None
                        else None
                    ),
                )
                info[f"_{prefix}subticks"] = None
        for prefix in ("y2", "x2"):
            # The writer switches a twin scale back on with both lines.
            reenabled = (
                self._twin_reenabled(prefix, info)
                and info[f"_{prefix}labels_on_raw"] is not None
            )
            ticks_on = info[f"_{prefix}ticks_on"]
            if ticks_on is not None and reenabled:
                passthrough = info["passthrough"]
                del passthrough[
                    next(i for i, x in enumerate(passthrough) if x is ticks_on)
                ]
            raw = info[f"_{prefix}labels_on_raw"]
            if raw is None:
                continue
            implied = (
                info[f"{prefix}format"] is not None
                or info[f"{prefix}angle"] is not None
                or info[f"{prefix}labels_hei"] is not None
                or info[f"{prefix}labels_color"] is not None
                or info[f"{prefix}min"] is not None
                or info[f"{prefix}max"] is not None
                or info[f"{prefix}log"]
                or bool(info[f"{prefix}label"])
                or (reenabled and ticks_on is not None)
            )
            if not implied:
                info["passthrough"].append(raw)
                line_no = info[f"_{prefix}labels_on_line"]
                self._note(
                    ImportCategory.STRUCTURE,
                    f"'{prefix}labels on' with nothing to style; kept as "
                    "raw GLE, not editable",
                    (line_no, line_no) if line_no is not None else None,
                )
        if info["x2lin"] and not self._x2_lin_will_emit(info):
            # A ``lin`` the writer will not reproduce (the primary axis is
            # not log, or the top scale is not in use). Keep the token.
            info["passthrough"].append("    x2axis lin")
            self._note(
                ImportCategory.STRUCTURE,
                "'x2axis lin' is not part of the top scale this figure "
                "re-emits; kept as raw GLE",
                None,
            )

    def _reconcile_places_names(self, info) -> None:
        """Drop a ``*names`` list the writer could never reproduce.

        ``GLEWriter.add_axis_config`` raises if ``xnames``/``ynames`` is set
        without a same-length ``xplaces``/``yplaces`` (see writer.py). A
        hand-written file can pair them inconsistently -- unmatched lengths,
        or names with no places at all -- which the model cannot represent.
        Fall back to raw passthrough for both recovered lines in that case so
        re-emission stays cumulative-equivalent instead of raising on save.
        """
        for prefix in ("x", "y"):
            places_field = f"{prefix}places"
            names_field = f"{prefix}names"
            names = info[names_field]
            places = info[places_field]
            if names is None:
                continue
            if places is not None and len(names) == len(places):
                continue
            lines: List[int] = []
            for key in (places_field, names_field):
                raw = info.pop(f"_{key}_raw", None)
                raw_line = info.pop(f"_{key}_raw_line", None)
                if raw is not None:
                    info["passthrough"].append(raw)
                if raw_line is not None:
                    lines.append(raw_line)
                info[key] = None
            self._note(
                ImportCategory.STRUCTURE,
                f"{prefix}names/{prefix}places length mismatch; "
                "kept as raw GLE, not editable",
                (min(lines), max(lines)) if lines else None,
            )

    def _skip_meta_stmt(self, stmt) -> bool:
        """True if this statement's physical line is inside the metadata block."""
        return stmt.source_line is not None and stmt.line_no in self._meta_lines

    @staticmethod
    def _is_bare_key_suppression(attr_toks: List[Token]) -> bool:
        """True if a dataset's merged attribute tokens are exactly ``key ""``.

        Used to recognize the writer's auto-key-from-header suppression
        marker (a standalone ``dN key ""`` statement emitted after a
        ``bar``/``fill`` command -- see ``writer.add_bar`` /
        ``add_fill``) so it isn't mistaken for a real second series
        on that dataset. Exactly 2 tokens: the ``key`` keyword and an empty
        string literal.
        """
        if len(attr_toks) != 2:
            return False
        kw_tok, val_tok = attr_toks
        if kw_tok.value.lower() != "key":
            return False
        if val_tok.type is not TokenType.STRING:
            return False
        return _string_value(val_tok) == ""

    @staticmethod
    def _suppressed_key_label(
        attr_toks: List[Token],
    ) -> Optional[Tuple[str, Optional[str]]]:
        """The label on a bar/fill swatch line, or None if this isn't one.

        Accepted, in either order, and with nothing else present:

        * ``key "label"``
        * ``keyfill COLOR key "label"``

        Returns ``(label, keyfill_or_None)``. ``COLOR`` is a bare name or a
        colour expression (``rgba255(...)``), collected the same way as a
        fill colour. An empty ``key ""`` is not a label; that line stays
        the header-suppression marker.
        """
        i = 0
        n = len(attr_toks)
        label = None
        keyfill = None
        while i < n:
            tok = attr_toks[i]
            word = tok.value.lower() if tok.type is TokenType.WORD else None
            if (
                word == "key"
                and i + 1 < n
                and attr_toks[i + 1].type is TokenType.STRING
            ):
                if label is not None:
                    return None
                label = _string_value(attr_toks[i + 1])
                i += 2
            elif word == "keyfill":
                if keyfill is not None:
                    return None
                color, nxt = _collect_color(attr_toks, i + 1)
                if color is None or nxt == i + 1:
                    return None
                keyfill = color
                i = nxt
            else:
                return None
        if not label:
            return None
        return label, keyfill

    @staticmethod
    def _note_swatch_color(owner, keyfill: Optional[str]) -> None:
        """Keep a keyfill colour that is not the series' own fill colour.

        The field stays absent when the two tokens are the same string, so
        a script gleplot wrote (they always are) does not grow a new key.
        """
        if not keyfill:
            return
        if owner.get("colors"):
            expected = owner["colors"][0]
        else:
            expected = owner.get("color")
        if expected is None or keyfill != expected:
            owner["swatch_color"] = keyfill

    def _dispatch_graph_statement(
        self, stmt, pass1: _GraphDatasets, info, marker_cfg, smooth_flags
    ):
        """Pass 2: hand one graph-block statement to the parser for its keyword."""
        kw = stmt.keyword
        toks = _words_and_values(stmt)
        if not toks:
            return

        if kw == "data":
            return  # already handled in pass 1
        if kw == "let" and self._let_is_consumed(toks, info):
            return
        if (
            kw == "let"
            and len(toks) > 1
            and toks[1].value.lower() in info["_derived_lets"]
        ):
            self._hold_derived_lines(
                toks[1].value.lower(), [self._stmt_text(stmt)], info
            )
            return
        if kw is not None and _DATASET_RE.match(kw):
            before = {
                attr: len(info[attr])
                for attr in Axes._DERIVED_SOURCE_ATTRS + ("errorbars",)
            }
            self._parse_dataset_line(stmt, pass1, info, marker_cfg, smooth_flags)
            self._note_dataset_series(kw, before, info)
            return
        if kw in ("size", "scale", "fullsize"):
            self._parse_geometry_line(kw, toks, info, stmt)
            return
        if kw == "title":
            self._parse_title_line(toks, info, stmt)
            return
        # Read back only as the writer writes it: a word or colour expression
        # with no comment after it, in a graph whose frame is drawn.
        if (
            kw == "background"
            and len(toks) == len(stmt.tokens)
            and len(toks) > 1
            and toks[1].type is TokenType.WORD
            and not info["frame_off"]
        ):
            color, nxt = _collect_color(toks, 1)
            if color is not None and nxt == len(toks):
                # GLE keeps the last one, wherever it stands in the block.
                info["facecolor"] = color
                return
        if kw in ("xtitle", "ytitle", "y2title", "x2title"):
            self._parse_axis_title_line(kw, toks, info, stmt)
            return
        if kw in ("xaxis", "yaxis", "y2axis", "x2axis"):
            self._parse_axis_line(kw, toks, info, stmt)
            return
        if kw in ("xlabels", "ylabels", "y2labels", "x2labels"):
            self._parse_labels_line(kw, toks, info, stmt)
            return
        if kw in ("xticks", "yticks", "xsubticks", "ysubticks"):
            self._parse_ticks_line(kw, toks, info, stmt)
            return
        if (
            kw in ("y2ticks", "x2ticks")
            and len(toks) == 2
            and toks[1].value.lower() == "on"
            and info[f"_{kw[:2]}ticks_on"] is None
        ):
            # Kept in place as raw GLE unless it turns out to be the
            # writer's (see _reconcile_axis_styling).
            raw = self._stmt_text(stmt)
            info["passthrough"].append(raw)
            info[f"_{kw[:2]}ticks_on"] = raw
            return
        if kw in ("xplaces", "yplaces", "xnames", "ynames"):
            self._parse_places_or_names_line(kw, toks, info, stmt)
            return
        if kw in ("xnoticks", "ynoticks"):
            self._parse_noticks_line(kw, toks, info, stmt)
            return
        if kw in ("xside", "yside", "y2side", "x2side"):
            self._parse_side_line(kw, toks, info, stmt)
            return
        if kw == "bar":
            self._parse_bar_command(toks, pass1.datasets, info, stmt)
            return
        if kw == "fill":
            self._parse_fill_command(toks, pass1.datasets, info, stmt)
            return
        if kw == "key":
            self._parse_key_command(toks, info, stmt)
            return
        if kw == "colormap":
            self._parse_colormap(toks, info, stmt)
            return

        # Unrecognized statement inside a graph block -> axes passthrough.
        info["passthrough"].append(self._stmt_text(stmt))

    def _parse_geometry_line(self, kw, toks, info, stmt) -> None:
        """Record a ``size``/``scale``/``fullsize`` statement.

        Recorded verbatim (plus its parsed arguments) and classified later by
        _apply_geometry -- never dropped.
        """
        info["geometry_stmts"].append(
            _GraphGeometryStmt(
                keyword=kw,
                words=[t.value.lower() for t in toks[1:]],
                values=_collect_values(toks, 1),
                raw=self._stmt_text(stmt),
                line_no=self._opt_line_no(stmt),
            )
        )

    # -- text styling (title / axis titles / tick labels) ----------------

    _TEXT_PREFIX = {
        "xtitle": "x",
        "ytitle": "y",
        "y2title": "y2",
        "x2title": "x2",
        "xlabels": "x",
        "ylabels": "y",
        "y2labels": "y2",
        "x2labels": "x2",
    }

    def _parse_text_options(self, toks, start):
        """Peel ``hei H`` / ``color C`` / ``font F`` / ``dist D`` off a line.

        These options are shared by GLE's ``title``, ``xtitle`` family and
        ``xlabels`` family, in any order. Returns ``(options, remainder)``:
        a dict with ``hei``/``color``/``font``/``dist`` (None where absent)
        and the tokens that were none of them, which the caller decides
        what to do with -- there is no "ignore the rest" path.
        """
        opts = {"hei": None, "color": None, "font": None, "dist": None}
        remainder: List[Token] = []
        i = start
        m = len(toks)
        while i < m:
            w = toks[i].value.lower()
            if w in ("hei", "dist") and i + 1 < m:
                value, nxt = _collect_value(toks, i + 1)
                if value is not None:
                    opts[w] = value
                    i = nxt
                    continue
            elif w == "color" and i + 1 < m:
                color, nxt = _collect_color(toks, i + 1)
                if color is not None:
                    opts["color"] = color
                    i = nxt
                    continue
            elif (
                w == "font"
                and i + 1 < m
                and toks[i + 1].type is TokenType.WORD
                and _GLE_FONT_NAME.match(toks[i + 1].value)
            ):
                opts["font"] = toks[i + 1].value
                i += 2
                continue
            remainder.append(toks[i])
            i += 1
        return opts, remainder

    @staticmethod
    def _string_index(toks) -> Optional[int]:
        """Index of the first STRING token, or None."""
        for i, t in enumerate(toks):
            if t.type is TokenType.STRING:
                return i
        return None

    def _parse_title_line(self, toks, info, stmt) -> None:
        """``title "T" [hei H] [color C] [font F] [dist D]``.

        Anything else on the line (``off``, a second string, a token before
        the text) cannot be represented, and GLE's ``title`` is a
        single command -- a supplementary line would replace it rather than
        add to it, the way a second ``xaxis`` line accumulates. So an
        unrepresentable title keeps its WHOLE original line as raw GLE and
        leaves ``title_text`` unset, exactly as before this method understood
        any options at all.
        """
        idx = self._string_index(toks)
        opts, remainder = self._parse_text_options(toks, idx + 1) if idx else ({}, [])
        if idx != 1 or remainder:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "title has unsupported options; kept as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return
        info["title"] = _string_value(toks[idx])
        info["title_hei"] = opts["hei"]
        info["title_color"] = opts["color"]
        info["title_dist"] = opts["dist"]
        info["title_font"] = opts["font"]

    def _parse_axis_title_line(self, kw, toks, info, stmt) -> None:
        """``xtitle "L" [hei H] [color C] [font F] [dist D]`` (and y/y2 twins).

        Same all-or-nothing rule as :meth:`_parse_title_line`: ``adist``
        and ``y2title``'s ``rotate`` are not modeled, and an axis
        title is a single command, so such a line is preserved verbatim
        instead of being re-emitted shorn of its options.
        """
        prefix = self._TEXT_PREFIX[kw]
        idx = self._string_index(toks)
        opts, remainder = self._parse_text_options(toks, idx + 1) if idx else ({}, [])
        if idx != 1 or remainder:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"{kw} has unsupported options; kept as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return
        info[f"{prefix}label"] = _string_value(toks[idx])
        info[f"{prefix}title_hei"] = opts["hei"]
        info[f"{prefix}title_color"] = opts["color"]
        info[f"{prefix}title_dist"] = opts["dist"]
        info[f"{prefix}title_font"] = opts["font"]

    def _parse_labels_line(self, kw, toks, info, stmt) -> None:
        """``xlabels [off] [hei H] [color C]`` (and y/y2 twins).

        ``off`` is the writer's tick-label suppression for shared axes.
        ``on`` is modeled for y2 and x2, where it is what makes any
        tick-label property visible at all (GLE draws no y2/x2 labels
        without it) -- and only if such a property is actually present,
        which :meth:`_reconcile_axis_styling` decides once the block has
        been read.
        ``log MODE`` is modeled on x and y. ``dist``/``font`` are not
        modeled on tick labels, so a line carrying them is kept whole as raw
        GLE.
        """
        prefix = self._TEXT_PREFIX[kw]
        opts, remainder = self._parse_text_options(toks, 1)
        leftover: List[Token] = []
        off = False
        on = False
        loglabels = None
        k = 0
        while k < len(remainder):
            word = remainder[k].value.lower()
            following = remainder[k + 1].value.lower() if k + 1 < len(remainder) else ""
            if word == "off" and prefix in ("x", "y"):
                off = True
            elif word == "on" and prefix in ("y2", "x2"):
                on = True
            elif (
                word == "log"
                and prefix in ("x", "y")
                and loglabels is None
                and following in LOG_LABEL_MODES
            ):
                loglabels = following
                k += 1
            else:
                leftover.append(remainder[k])
            k += 1
        if (
            leftover
            or opts["font"] is not None
            or (
                off
                and (
                    opts["hei"] is not None
                    or opts["color"] is not None
                    or loglabels is not None
                )
            )
            or (
                loglabels is not None
                and (
                    info[f"{prefix}loglabels"] is not None
                    or (prefix, "loglabels") in info["_raw_axis_opts"]
                )
            )
        ):
            if any(tok.value.lower() == "log" for tok in remainder):
                # A later modeled 'log' would be written ahead of this raw
                # line and lose to it, so it stays raw too.
                info["_raw_axis_opts"].add((prefix, "loglabels"))
            # Unmodeled option, or styling on labels that are switched off
            # (which the writer would drop): keep the line verbatim.
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"unrecognized {kw} options; kept as raw GLE, not editable",
                (stmt.line_no, stmt.line_no) if stmt is not None else None,
            )
            return
        if off:
            info[f"{prefix}labels_off"] = True
        if on:
            info[f"_{prefix}labels_on_raw"] = self._stmt_text(stmt)
            info[f"_{prefix}labels_on_line"] = (
                stmt.line_no if stmt is not None else None
            )
        # GLE label settings are cumulative: a line without 'hei' (say
        # 'xlabels log l25') keeps the one an earlier line set.
        if opts["hei"] is not None:
            info[f"{prefix}labels_hei"] = opts["hei"]
        if opts["color"] is not None:
            info[f"{prefix}labels_color"] = opts["color"]
        if loglabels is not None:
            info[f"{prefix}loglabels"] = loglabels

    @staticmethod
    def _twin_reenabled(prefix, info) -> bool:
        """Whether the writer switches twin scale ``prefix`` back on.

        It does after an empty places list on the primary axis, whose
        ``ticks off``/``labels off`` GLE copies onto the twin, when the twin
        is configured or carries a dataset (``Axes.has_y2_plots`` /
        ``has_x2_plots``) and is not itself off.
        """
        primary = prefix[0]
        if info[f"{primary}places"] != [] or info[f"{prefix}axis_off"]:
            return False
        if (
            info[f"{prefix}min"] is not None
            or info[f"{prefix}max"] is not None
            or info[f"{prefix}log"]
            or bool(info[f"{prefix}label"])
        ):
            return True
        groups = ("lines", "scatters", "errorbars", "hists", "file_series")
        axis = "yaxis" if primary == "y" else "xaxis"
        return any(s.get(axis) == prefix for group in groups for s in info[group])

    @staticmethod
    def _is_empty_places(prefix, ticks, subticks, info) -> bool:
        """Whether the axis says no ticks and no labels, and nothing more.

        Only a bare ``xticks off`` with a bare ``xlabels off`` qualifies, on
        an axis with no places, names, no-tick positions or subtick line: the
        writer would drop any of those beside an empty places list. An axis
        without a grid may add a bare ``xsubticks on``, which the writer
        writes there for minor ticks.
        """
        style = ("lstyle", "lwidth", "length", "color")
        return (
            ticks is not None
            and ticks["ok"]
            and ticks["off"]
            and all(ticks[k] is None for k in style)
            and (
                subticks is None
                or (
                    not info[f"{prefix}grid"]
                    and subticks["ok"]
                    and subticks["on"]
                    and all(subticks[k] is None for k in style)
                )
            )
            and info[f"{prefix}labels_off"]
            and info[f"{prefix}places"] is None
            and info[f"{prefix}names"] is None
            and info[f"{prefix}noticks"] is None
        )

    def _reconcile_tick_marks(self, prefix, ticks, subticks, info) -> None:
        """``xticks``/``xsubticks`` on an axis with no grid: tick marks.

        The model holds ``length``/``lwidth``/``color`` on both, and
        ``on``/``off`` on the minor ticks. Anything else (``lstyle``,
        ``xticks on|off``) keeps the line as raw GLE.
        """
        for kind, parsed in (("tick", ticks), ("subtick", subticks)):
            if parsed is None:
                continue
            switch = kind == "tick" and (parsed["on"] or parsed["off"])
            if not parsed["ok"] or parsed["lstyle"] is not None or switch:
                info["passthrough"].append(parsed["raw"])
                line_no = parsed["line_no"]
                self._note(
                    ImportCategory.STRUCTURE,
                    f"{prefix}{kind}s options the model does not hold; kept "
                    "as raw GLE, not editable",
                    (line_no, line_no) if line_no is not None else None,
                )
                continue
            info[f"_{prefix}{kind}_marks"] = parsed

    def _parse_ticks_line(self, kw, toks, info, stmt) -> None:
        """``xticks``/``xsubticks`` style, parked for later reconciliation.

        On an axis with a grid these are grid styling (see
        :class:`gleplot.writer.AxisStyle`); without one they are the tick
        marks of ``Axes.tick_params``. GLE allows the ``xaxis ... grid``
        that decides it to appear anywhere in the block, so the line is
        recorded here and judged by :meth:`_reconcile_axis_styling`; any
        other sub-command means the line is not ours and goes back to
        passthrough untouched.
        """
        prefix = "x" if kw.startswith("x") else "y"
        key = f"_{prefix}subticks" if "sub" in kw else f"_{prefix}ticks"
        parsed: Dict[str, Any] = {
            "raw": self._stmt_text(stmt),
            "line_no": stmt.line_no if stmt is not None else None,
            "lstyle": None,
            "lwidth": None,
            "length": None,
            "color": None,
            "on": False,
            "off": False,
            "ok": True,
        }
        i = 1
        m = len(toks)
        while i < m:
            word = toks[i].value.lower()
            if word in ("lstyle", "lwidth", "length") and i + 1 < m:
                value, nxt = _collect_value(toks, i + 1)
                if value is not None and parsed[word] is None:
                    parsed[word] = value
                    i = nxt
                    continue
            elif word == "color" and i + 1 < m:
                color, nxt = _collect_color(toks, i + 1)
                if color is not None:
                    parsed["color"] = color
                    i = nxt
                    continue
            elif word in ("on", "off") and not (parsed["on"] or parsed["off"]):
                parsed[word] = True
                i += 1
                continue
            parsed["ok"] = False
            i += 1
        if info[key] is not None:
            # A second style line for the same ticks; the model holds one.
            parsed["ok"] = False
            prev_line_no = info[key]["line_no"]
            info["passthrough"].append(info[key]["raw"])
            self._note(
                ImportCategory.STRUCTURE,
                f"repeated {kw} line; kept as raw GLE, not editable",
                (prev_line_no, prev_line_no) if prev_line_no is not None else None,
            )
        info[key] = parsed

    # -- axis line parsing ----------------------------------------------

    def _parse_axis_line(self, kw, toks, info, stmt=None):
        prefix = {"xaxis": "x", "yaxis": "y", "y2axis": "y2", "x2axis": "x2"}[kw]
        remainder: List[Token] = []
        negate_toks: List[Token] = []
        i = 1
        m = len(toks)
        while i < m:
            w = toks[i].value.lower()
            if w == "min" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    info[f"{prefix}min"] = v
                    i = nxt
                    continue
                i += 2
                continue
            if w == "max" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    info[f"{prefix}max"] = v
                    i = nxt
                    continue
                i += 2
                continue
            if w == "log":
                info[f"{prefix}log"] = True
                i += 1
                continue
            if w == "lin" and prefix == "x2":
                # Undoes the ``xaxis log`` copy. Whether the writer emits
                # it again is decided in ``_reconcile_axis_styling``.
                info["x2lin"] = True
                i += 1
                continue
            if w == "negate":
                negate_toks.append(toks[i])
                i += 1
                continue
            if w == "nofirst":
                info[f"nofirst_{prefix}"] = True
                i += 1
                continue
            if w == "nolast":
                info[f"nolast_{prefix}"] = True
                i += 1
                continue
            if (
                w == "off"
                and prefix in ("x2", "y2")
                and prefix not in info["_switched_on"]
            ):
                info[f"{prefix}axis_off"] = True
                i += 1
                continue
            if (
                w == "format"
                and i + 1 < m
                and toks[i + 1].type is TokenType.STRING
                and info[f"{prefix}format"] is None
            ):
                info[f"{prefix}format"] = _string_value(toks[i + 1])
                i += 2
                continue
            if w == "angle" and i + 1 < m and info[f"{prefix}angle"] is None:
                value, nxt = _collect_value(toks, i + 1)
                if value is not None:
                    info[f"{prefix}angle"] = value
                    i = nxt
                    continue
            nxt = self._take_tick_placement(w, toks, i, prefix, info)
            if nxt is not None:
                i = nxt
                continue
            if w == "grid" and prefix in ("x", "y"):
                # y2 and x2 have no grid on the model: GLE's grid is the
                # axis' own ticks stretched across the graph, so
                # 'y2axis grid' / 'x2axis grid' would redraw the primary
                # grid from the other side. Left unrecognized (and
                # therefore preserved) rather than folded into ygrid/xgrid.
                info[f"{prefix}grid"] = True
                i += 1
                continue
            # Unrecognized axis sub-token (hei, an expression dticks, any
            # option on y2/x2, a repeat, ...). GLE axis lines are cumulative,
            # so we peel the recognized options into the model and re-emit
            # the UNRECOGNIZED remainder as a supplementary axis line in
            # passthrough. e.g. 'xaxis min 0 max 2*pi dticks pi/2 grid' ->
            # model gets min/max/grid; passthrough gets 'xaxis dticks pi/2'.
            remainder.append(toks[i])
            info["_raw_axis_opts"].add((prefix, w))
            # A recognized keyword may take a value; unrecognized ones we cannot
            # know the arity of, so we copy tokens verbatim one at a time (their
            # own values ride along as further 'remainder' tokens).
            i += 1

        # ``negate`` becomes a descending limit pair on the model, which needs
        # BOTH bounds to exist -- on this line or (GLE axis lines being
        # cumulative) an earlier one. Without them the inversion has nowhere
        # to live, so it goes back to passthrough with the rest of the
        # unmodelled options rather than being dropped.
        if negate_toks:
            if info[f"{prefix}min"] is not None and info[f"{prefix}max"] is not None:
                info[f"{prefix}negate"] = True
            else:
                remainder.extend(negate_toks)
                remainder.sort(key=lambda t: t.start)

        if remainder:
            rendered = self._render_remainder(remainder, stmt)
            info["passthrough"].append(f"    {kw} {rendered}")
            self._note(
                ImportCategory.STRUCTURE,
                f"unrecognized {kw} options ({rendered}) preserved as "
                "a supplementary axis line (cumulative); not editable",
                self._stmt_span(stmt),
            )

    @staticmethod
    def _take_tick_placement(w, toks, i, prefix, info) -> Optional[int]:
        """Model ``nticks``/``ftick``/``shift``/``symticks``/``nsubticks``/
        ``dticks``/``dsubticks``.

        Returns the index after the option when it is one of them, on x or
        y, and fits the model; otherwise None. A repeat, a fractional
        ``nticks``/``nsubticks``, a ``dticks``/``dsubticks`` written as an
        expression or ``symticks on|off`` is left to the remainder, which
        keeps it as raw GLE, and so is any later occurrence of the same
        option (see ``_raw_axis_opts``).
        """
        if prefix not in ("x", "y") or (prefix, w) in info["_raw_axis_opts"]:
            return None
        m = len(toks)
        if w == "symticks":
            following = toks[i + 1].value.lower() if i + 1 < m else ""
            if following in ("on", "off") or info[f"{prefix}symticks"]:
                return None
            info[f"{prefix}symticks"] = True
            return i + 1
        if (
            w not in ("nticks", "ftick", "shift", "nsubticks", "dticks", "dsubticks")
            or info[f"{prefix}{w}"] is not None
        ):
            return None
        value, nxt = _collect_value(toks, i + 1)
        if value is None:
            return None
        if w in ("dticks", "dsubticks") and (
            toks[i + 1].type is not TokenType.NUMBER
            or nxt != i + 2
            or value <= 0
            or float(GLEWriter._format_number(value)) != value
        ):
            # Only a positive literal the writer writes back unchanged is
            # modelled. An expression ('dticks pi/2', 'dticks pi') or a
            # value it would round stays raw GLE, exactly as written.
            return None
        if w in ("nticks", "nsubticks"):
            if not float(value).is_integer() or value < 1:
                return None
            value = int(value)
        info[f"{prefix}{w}"] = value
        return nxt

    def _parse_noticks_line(self, kw, toks, info, stmt) -> None:
        """``xnoticks p1 p2 ...`` (and y): positions with no tick.

        GLE replaces the list on every ``xnoticks``, so a second line is
        kept as raw GLE after the modeled one, which keeps the last list
        in force.
        """
        prefix = kw[0]
        values: List[float] = []
        i = 1
        while i < len(toks):
            value, i = _collect_value(toks, i)
            if value is None:
                values = []
                break
            values.append(value)
        if not values or info[f"{prefix}noticks"] is not None:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"unrecognized {kw} line preserved as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return
        info[f"{prefix}noticks"] = values

    def _parse_side_line(self, kw, toks, info, stmt) -> None:
        """``xside [color C] [lwidth W] [off]`` (and y/y2/x2): the axis line.

        ``off`` is modeled on x and y, and ``on`` on x2 and y2 only after a
        modeled x or y ``off``, where it is the writer switching the copied
        ``off`` back off the opposite edge (see
        :meth:`_reconcile_axis_styling`). ``lstyle`` is not modeled, and
        neither is a repeated line, so those stay raw GLE. GLE copies an ``xside`` onto
        x2, and the writer puts ``xside`` before ``x2side``, so an
        ``xside`` that comes after a modeled ``x2side`` stays raw GLE too:
        re-emitted at the end of the block it still overrides the top line,
        as it did. For the same reason an ``xside`` after a raw ``xaxis
        color``/``lwidth`` (which set the line too, and which GLE also
        copies onto x2) stays raw.
        """
        prefix = kw[: -len("side")]
        color: Optional[str] = None
        lwidth: Optional[float] = None
        off: Optional[bool] = None
        source = info.get({"x2": "xside", "y2": "yside"}.get(prefix, ""))
        switch = (
            "off"
            if prefix in ("x", "y")
            else "on" if source is not None and source["off"] else None
        )
        ok = len(toks) > 1
        i = 1
        while i < len(toks) and ok:
            word = toks[i].value.lower()
            if word == "color" and color is None:
                color, i = _collect_color(toks, i + 1)
                ok = color is not None
            elif word == "lwidth" and lwidth is None:
                lwidth, i = _collect_value(toks, i + 1)
                ok = lwidth is not None
            elif word == switch and off is None and i == len(toks) - 1:
                off = word == "off"
                i += 1
            else:
                ok = False
        mirror = {"x": "x2side", "y": "y2side"}.get(prefix)
        sources = {prefix, {"x2": "x", "y2": "y"}.get(prefix, prefix)}
        raw_before = any(
            (source, word) in info["_raw_axis_opts"]
            for source in sources
            for word in ("color", "lwidth")
        )
        if (
            not ok
            or raw_before
            or info[kw] is not None
            or (mirror and info[mirror] is not None)
        ):
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"unrecognized {kw} line preserved as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return
        # 'at' is where a demoted 'off' goes back into passthrough, so it
        # stays ahead of the raw lines that followed it.
        info[kw] = {
            "color": color,
            "lwidth": lwidth,
            "off": off,
            "at": len(info["passthrough"]),
        }

    def _render_remainder(self, remainder, stmt) -> str:
        """Reconstruct remainder tokens preserving original source spacing.

        Slicing contiguous runs of remainder tokens straight from the source
        segment keeps ``pi/2`` intact (rendering token-by-token would insert
        spaces around the ``/`` and GLE would reject ``pi / 2`` after
        ``dticks``). Non-contiguous runs are joined with a single space.
        """
        raw = stmt.raw if stmt is not None and stmt.raw else None
        if raw is None:
            return " ".join(self._token_text(t) for t in remainder)
        runs: List[str] = []
        run_start = remainder[0].start
        run_end = remainder[0].end
        for t in remainder[1:]:
            if t.start == run_end:  # directly adjacent (no gap)
                run_end = t.end
            else:
                runs.append(raw[run_start:run_end])
                run_start, run_end = t.start, t.end
        runs.append(raw[run_start:run_end])
        return " ".join(s.strip() for s in runs if s.strip())

    def _token_text(self, tok) -> str:
        """Source-faithful text for a single token (STRING keeps its quotes)."""
        if tok.type is TokenType.STRING:
            q = tok.quote or '"'
            inner = _string_value(tok)
            return q + inner.replace(q, q + q) + q
        return tok.value

    # -- explicit tick places/names ---------------------------------------

    def _parse_places_or_names_line(self, kw, toks, info, stmt) -> None:
        """``xplaces v1 v2 ...`` / ``xnames "a" "b" ...`` (and y variants).

        Each is a standalone statement (sibling to ``xaxis``/``yaxis``, not
        one of its sub-tokens) so it is dispatched here directly. A line that
        does not fully parse as a number list (``*places``) or string list
        (``*names``) is kept verbatim in the axes passthrough instead --
        final ``*places``/``*names`` pairing (length match) is checked once
        the whole graph block has been read, in :meth:`_reconcile_places_names`.
        """
        is_names = kw.endswith("names")
        prefix = "x" if kw.startswith("x") else "y"
        field = f"{prefix}names" if is_names else f"{prefix}places"

        values: List = []
        i = 1
        m = len(toks)
        if is_names:
            while i < m and toks[i].type is TokenType.STRING:
                # GLE strips a name's outer double quotes and nothing else
                # (do_names in graph.cpp), so a doubled quote is two quotes.
                raw = toks[i].value
                if toks[i].quote == '"' and len(raw) >= 2 and raw.endswith('"'):
                    name = raw[1:-1]
                else:
                    name = _string_value(toks[i])
                values.append(name.replace(NAME_QUOTE, '"'))
                i += 1
        else:
            while i < m:
                v, nxt = _collect_value(toks, i)
                if v is None:
                    break
                values.append(v)
                i = nxt

        if i != m or not values:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                f"unrecognized {kw} line preserved as raw GLE, not editable",
                (stmt.line_no, stmt.line_no) if stmt is not None else None,
            )
            return

        info[field] = values
        info[f"_{field}_raw"] = self._stmt_text(stmt)
        info[f"_{field}_raw_line"] = stmt.line_no if stmt is not None else None

    # -- data command ----------------------------------------------------

    def _parse_data_command(
        self, toks, datasets, line_no: Optional[int] = None
    ) -> List[str]:
        """``data FILE d1=c1,c2 d2=c1,c3 ...`` -> register datasets.

        Returns the dataset names this call registered (empty if the
        statement was empty, malformed, or its file could not be resolved
        for auto column mapping), so the caller can pair them with the
        statement's raw text for later reconciliation.

        ``line_no`` is the originating ``data`` statement's 1-indexed source
        line, threaded through by the caller so this method's own notes
        (redefinition / unresolved auto-mapping) can carry a real span.

        Handles three GLE forms (semantics verified against
        ``GLE/src/gle/graph.cpp`` ``data_command`` / ``read_data_description``):

        * **Explicit** ``d1=c1,c2`` -- x/y columns given verbatim.
        * **Positional** ``data f.dat d1 d3`` -- dataset names with no ``=``:
          each ``!xygiven`` dataset gets x = c1 and y assigned by its *position*
          among the given datasets (``d1`` -> c2, ``d3`` -> c3), NOT by dataset
          number.
        * **Auto** ``data f.dat`` -- no dataset clauses: register d1=c1,c2,
          d2=c1,c3, ... one per column past the x column (up to the file's
          column count), when the file resolves.

        In both of the last two, x is the point index (``c0``) instead under
        ``nox`` or for a single-column file, with y starting at c1; and when
        every value in the first column is text, with y starting at c2 (the
        text labels the x axis). The column count and the text test read the
        file as GLE does, under the statement's reading options
        (:func:`gleplot.dataio.gle_data_layout`).

        The reading options ``ignore n``, ``comment c`` and ``numrows n``
        may appear anywhere after the file name; each named dataset records
        them (see :attr:`_data_read_options`). Any other word (``delimiters``,
        a count that is not a plain number) cannot be written back: the
        statement is reported and returns no names, so it is kept as written,
        and the datasets it names are held undefined (:meth:`_hold_dataset`).

        The filename token is *unwrapped* (STRING tokens have their quotes
        stripped) so ``data "wave.dat"`` registers ``wave.dat`` rather than the
        quote-embedded literal (which would never resolve).
        """
        if len(toks) < 2:
            return []
        data_file, i = self._read_filename(toks, 1)
        m = len(toks)

        # Collect dataset clauses in the order given: (name, explicit_cols|None).
        given: List[Tuple[str, Optional[Tuple[int, int]]]] = []
        read_options: Dict[str, Any] = {}
        nox = False
        unread: List[str] = []
        while i < m:
            name_tok = toks[i]
            option = name_tok.value.lower() if name_tok.type is TokenType.WORD else ""
            if option in ("ignore", "numrows") and i + 1 < m:
                count = toks[i + 1].value
                if toks[i + 1].type is TokenType.NUMBER and count.isdigit():
                    field = "skiprows" if option == "ignore" else "max_rows"
                    read_options[field] = int(count)
                    i += 2
                    continue
            if option == "comment" and i + 1 < m:
                read_options["comment"], i = self._read_filename(toks, i + 1)
                continue
            if option == "nox":
                # It only moves the x of datasets given without columns, and
                # those are written back with explicit columns.
                nox = True
                i += 1
                continue
            if name_tok.type is not TokenType.WORD or not _DATASET_RE.match(
                name_tok.value
            ):
                unread.append(name_tok.value)
                i += 1
                continue
            name = name_tok.value.lower()
            if i + 1 < m and toks[i + 1].value == "=":
                cols = []
                j = i + 2
                while j < m:
                    t = toks[j]
                    if (
                        t.type is TokenType.WORD
                        and t.value.lower().startswith("c")
                        and t.value[1:].isdigit()
                    ):
                        cols.append(int(t.value[1:]))
                        j += 1
                        if j < m and toks[j].value == ",":
                            j += 1
                            continue
                        break
                    else:
                        break
                if len(cols) >= 2:
                    given.append((name, (cols[0], cols[1])))
                i = j
            else:
                # Positional dataset name (no '=').
                given.append((name, None))
                i += 1

        # Warn (last-wins) about a redefinition of an already-registered name.
        for name, _cols in given:
            if name in datasets:
                self._note(
                    ImportCategory.DATA,
                    f"dataset {name} redefined by a later 'data' command; "
                    "using the last definition",
                    (line_no, line_no) if line_no is not None else None,
                )

        if unread:
            for name, _cols in given:
                self._hold_dataset(name, datasets)
            self._note(
                ImportCategory.DATA,
                f"'{' '.join(unread)}' on the 'data' statement for "
                f"'{data_file}' is not modelled; the statement and every "
                "line that reads its datasets were kept as raw GLE, which "
                "still draws but is not editable",
                (line_no, line_no) if line_no is not None else None,
            )
            return []

        need_auto = not given or any(c is None for _n, c in given)
        ncols = self._file_column_count(data_file, read_options) if need_auto else None

        # x column / first y column, as GLE's data_command assigns them: x is
        # the point index (c0) under 'nox', for a single-column file, and when
        # every value in the first column is text (it then labels the x axis).
        if need_auto and self._first_column_is_labels(data_file, read_options):
            cx, cy_first = 0, 2
        elif nox or (ncols is not None and ncols <= 1):
            cx, cy_first = 0, 1
        else:
            cx, cy_first = 1, 2

        if not given:
            # Auto-mapping: one dataset per column past the x column.
            if ncols is None:
                # File unresolved: cannot auto-map. Record a broken reference
                # so referencing is not silently dropped.
                self._note(
                    ImportCategory.DATA,
                    f"'{data_file}' could not be resolved; auto column "
                    "mapping (data with no dN clauses) skipped",
                    (line_no, line_no) if line_no is not None else None,
                )
                return []
            names = [f"d{k + 1}" for k in range(ncols + 1 - cy_first)]
            for k, name in enumerate(names):
                self._register_dataset(
                    name, data_file, cx, k + cy_first, datasets, read_options
                )
            return names

        # Explicit and/or positional clauses.
        for pos, (name, explicit) in enumerate(given):
            if explicit is not None:
                self._register_dataset(
                    name, data_file, explicit[0], explicit[1], datasets, read_options
                )
            else:
                # Positional: y column follows GLE's position-based assignment.
                ycol = pos + cy_first
                self._register_dataset(
                    name, data_file, cx, ycol, datasets, read_options
                )
        return [name for name, _cols in given]

    def _hold_dataset(self, name, datasets) -> None:
        """Leave dataset ``name`` undefined, so whatever reads it stays raw.

        A line reading a dataset no ``data`` statement defines is kept as
        written; that is how a statement gleplot cannot write back keeps
        every reader of its datasets with it.
        """
        datasets.pop(name, None)
        self._datasets.pop(name, None)
        self._data_read_options.pop(name, None)
        self._held_datasets.add(name)

    def _hold_let_target(self, toks, datasets) -> bool:
        """Hold a ``let``'s target when it reads a held dataset.

        The ``let`` stays raw and redefines its target, so a ``dK`` line
        drawing the target reads the ``let``, not an earlier ``data``.
        """
        if len(toks) < 2 or not self._held_datasets:
            return False
        read = " ".join(tok.value for tok in toks[2:])
        if not {m.lower() for m in _DATASET_NAME_RE.findall(read)} & (
            self._held_datasets
        ):
            return False
        self._hold_dataset(toks[1].value.lower(), datasets)
        return True

    def _register_dataset(
        self, name, data_file, xcol, ycol, datasets, read_options=None
    ):
        datasets[name] = (data_file, xcol, ycol)
        self._datasets[name] = (data_file, xcol, ycol)
        self._held_datasets.discard(name)
        if read_options:
            self._data_read_options[name] = read_options
        else:
            self._data_read_options.pop(name, None)

    def _parse_let_command(self, toks, datasets, info):
        """``let dK = dJ+off`` / ``let dK = dJ-off`` -> register dK as an
        offset alias of dJ.

        Recognizes only the exact vertical-shift shape gleplot's writer emits
        (see :meth:`gleplot.writer.GLEWriter._apply_offset`): a target dataset,
        ``=``, a source dataset already registered by a ``data`` command, a
        single ``+``/``-``, and a numeric value. dK is registered pointing at
        dJ's file and columns, and the signed offset is recorded in
        ``info["_dataset_offsets"]`` so the recovered series carries the raw
        file values plus an editable offset. Anything richer (a general GLE
        ``let`` expression) is left unregistered and preserved as raw GLE.

        Tokens (keyword included): ``let dK = dJ <op> <number...>``.
        """
        # let dK = dJ <op> number  -> at least 6 tokens.
        if len(toks) < 6:
            return
        target = toks[1].value.lower()
        eq = toks[2]
        source = toks[3].value.lower()
        op = toks[4].value
        if not _DATASET_RE.match(target) or not _DATASET_RE.match(source):
            return
        if eq.type is not TokenType.OP or eq.value != "=":
            return
        if op not in ("+", "-"):
            return
        # A series on a file gleplot did not write is a FileSeries
        # reference, which has no offset to carry the shift.
        if source not in datasets or not self._is_import(datasets[source][0]):
            return
        magnitude = eval_gle_number(toks[5:])
        if magnitude is None:
            return
        offset = -magnitude if op == "-" else magnitude
        data_file, xcol, ycol = datasets[source]
        self._register_dataset(target, data_file, xcol, ycol, datasets)
        info["_dataset_offsets"][target] = float(offset)
        info["_offset_let_datasets"].add(target)
        info["_offset_let_sources"][target] = source
        # 'source' is consumed by this alias (its file/columns are what the
        # aliased series actually reads) even though it never gets its own
        # 'dN ...' statement -- see the 'data'-statement reconciliation in
        # _restore_orphaned_data_stmts.
        info["_let_source_datasets"].add(source)

    def _record_hist_let(self, toks, datasets, info, raw: str, line_no) -> None:
        """Record ``let dK = hist dJ [from a] [to b] [bins n] [step w]``.

        Options may appear in any order, which is how GLE's
        ``parseHistogram`` reads them. An unknown token, a missing value, or
        a source dataset this block never declared means this is not a
        histogram let -- it stays unregistered and pass 2 keeps the line.
        The target is deliberately not entered in ``datasets``.
        """
        if len(toks) < 5:
            return
        target = toks[1].value.lower()
        eq = toks[2]
        kind = toks[3].value.lower()
        source = toks[4].value.lower()
        if not _DATASET_RE.match(target) or not _DATASET_RE.match(source):
            return
        if eq.type is not TokenType.OP or eq.value != "=":
            return
        if kind != "hist" or source not in datasets:
            return
        if target in info["_hist_lets"]:
            return
        options = {}
        i = 5
        while i < len(toks):
            key = toks[i].value.lower()
            if key not in ("from", "to", "bins", "step"):
                return
            j = i + 1
            while j < len(toks) and toks[j].value.lower() not in (
                "from",
                "to",
                "bins",
                "step",
            ):
                j += 1
            if j == i + 1:
                return
            value = eval_gle_number(toks[i + 1 : j])
            if value is None:
                return
            options[key] = float(value)
            i = j
        info["_hist_lets"][target] = {
            "source": source,
            "hist_from": options.get("from"),
            "hist_to": options.get("to"),
            "bins": options.get("bins"),
            "bin_step": options.get("step"),
            "line_no": line_no,
        }
        info["_hist_let_pending"][target] = raw

    def _record_function_let(self, toks, info) -> None:
        """Record ``let dK = <expression> [from a] [to b] [step h]``.

        The expression is the run of tokens after ``=`` with no space
        between them, which is where GLE's own parser ends it. It must pass
        the check :meth:`gleplot.Axes.function` makes. ``from``, ``to`` and
        ``step`` take a plain number each, so the value written back is
        the one read. Anything else stays raw GLE.
        """
        found = _let_target_expression(toks)
        if found is None or found[0] in info["_function_lets"]:
            return
        target, expression, end = found
        if _function_expression_problem(expression) is not None:
            return
        fields: Dict[str, Any] = {"expression": expression}
        if _read_let_range(toks, end, fields):
            info["_function_lets"][target] = fields

    def _record_fit_let(self, toks, datasets, info) -> None:
        """Record ``let dK = fit dJ with <expression> [from a] [to b] [step h]``.

        Or ``let dK = <routine> dJ [from a] [to b]`` for one of the
        closed-form routines in
        :data:`~gleplot.parser.tables.FIT_ROUTINE_TO_MODEL`. GLE reads the
        options in any order. The expression is read as for
        :meth:`_record_function_let`, and ``dJ`` must be a dataset this
        block's ``data`` commands declare. Any other option (``rsq``,
        ``eqstr``, a data window, a ``limit_data`` option, a routine's
        ``step``, which GLE ignores) stays raw GLE, and so do result
        variables after anything but a routine. The record joins the
        function lets: the same rules decide whether it is modelled, and
        :meth:`_keep_plain_function_lets` adds the ones for its data and
        reads a routine's key (:meth:`_model_fit_attr_toks`).
        """
        if len(toks) < 5:
            return
        routine = toks[3].value.lower()
        model = FIT_ROUTINE_TO_MODEL.get(routine)
        if routine != "fit" and model is None:
            return
        target = toks[1].value.lower()
        source = toks[4].value.lower()
        eq = toks[2]
        if not _DATASET_RE.match(target) or source not in datasets:
            return
        if eq.type is not TokenType.OP or eq.value != "=":
            return
        if target in info["_function_lets"]:
            return
        fields: Dict[str, Any] = {"_fit_source": source}
        end = len(toks)
        if model is not None:
            fields["model"] = model
            # Up to three result variables end the statement. GLE reads
            # options until a word that is not one, so only the first
            # variable cannot have an option's name.
            while (
                end > 5
                and len(toks) - end < 3
                and toks[end - 1].type is TokenType.WORD
                and _RESULT_VAR_RE.match(toks[end - 1].value)
            ):
                end -= 1
            while end < len(toks) and toks[end].value.lower() in _FIT_LET_WORDS:
                end += 1
            names = [tok.value.lower() for tok in toks[end:]]
            statement = " ".join(tok.value for tok in toks)
            if any(_mention_count([statement], name) != 1 for name in names):
                return
            if names:
                fields["_result_vars"] = names
        if not _read_let_range(toks[:end], 5, fields, fit=model is None):
            return
        # Axes.fit rejects a step with a model, since GLE ignores it.
        if model is not None and "let_step" not in fields:
            info["_function_lets"][target] = fields
        elif "expression" in fields:
            info["_function_lets"][target] = fields

    def _keep_plain_function_lets(self, block, pass1: _GraphDatasets, info) -> None:
        """Drop each recorded function let that cannot be modelled whole.

        A function let is modelled only when its target is named by that
        ``let`` and by its own ``dK`` lines, and nothing else: a ``fill``,
        a ``bar`` or another ``let`` that reads the dataset needs the name
        the file gave it. The ``dK`` lines must also be a plain line that
        :meth:`gleplot.writer.GLEWriter.add_function` writes back the same.
        """
        # A derived let reads the curve through the name the writer gives it,
        # and a polar let stands for its source.
        texts = self._non_dataset_texts(
            block, skip=set(info["_derived_lets"]) | set(info["_polar_aliases"])
        )
        keyed = {}
        for target, fields in list(info["_function_lets"].items()):
            if "model" in fields:
                found = self._model_fit_attr_toks(target, fields, pass1)
                if found is None:
                    del info["_function_lets"][target]
                else:
                    keyed[target] = found
        for target in list(info["_function_lets"]):
            mentions = _mention_count(texts, target)
            attr_toks = (
                keyed[target][0]
                if target in keyed
                else pass1.merged_attr_toks.get(target)
            )
            drawn_as_is = (
                info["polar_rmax"] is not None
                and target not in info["_polar_aliases"].values()
            )
            if (
                drawn_as_is
                or mentions != 1
                or not attr_toks
                or not _plain_function_line(attr_toks)
                or not self._load_fit_data(texts, pass1, info, target)
            ):
                del info["_function_lets"][target]
        for target, (attr_toks, run, label) in keyed.items():
            if target in info["_function_lets"]:
                pass1.merged_attr_toks[target] = attr_toks
                if run is not None:
                    info["_fit_key_labels"][run] = label
        # The writer renumbers the datasets it writes, but not the ones in raw
        # lines. Beside a let that stays raw, a renumbered curve could take
        # that let's name, so then every function and derived let stays raw.
        for child in block.body:
            if isinstance(child, Statement) and child.keyword == "let":
                toks = _words_and_values(child)
                target = toks[1].value.lower() if len(toks) > 1 else None
                if (
                    target not in info["_function_lets"]
                    and target not in info["_offset_let_datasets"]
                    and target not in info["_derived_lets"]
                    and target not in info["_polar_aliases"]
                    and target not in info["_hist_lets"]
                    and target not in info["_colour_lets"]
                ):
                    info["_function_lets"].clear()
                    info["_derived_lets"].clear()
                    return

    def _model_fit_attr_toks(self, target, fields, pass1: _GraphDatasets):
        """The ``dK`` tokens of a model fit as a plain line, or None.

        A key that is a string expression of the fit's result variables, as
        :meth:`gleplot.writer.GLEWriter.add_fit` writes it, becomes one
        string holding the label with its placeholders. Returns ``(tokens,
        expression, label)``, the expression None for any other key. None
        when the key cannot come back the same: a plain key that reads as a
        placeholder, an expression the writer would not write, or a result
        variable named anywhere but its ``let``, that key, and the
        ``begin key`` after the graph restating it.
        """
        attr_toks = list(pass1.merged_attr_toks.get(target) or [])
        variables = fields.get("_result_vars", [])
        names = dict(zip(variables, FIT_RESULT_PLACEHOLDERS[fields["model"]]))
        start = next(
            (
                i + 1
                for i, tok in enumerate(attr_toks[:-1])
                if tok.type is TokenType.WORD and tok.value.lower() == "key"
            ),
            None,
        )
        run: Optional[str] = None
        label: Optional[str] = None
        if start is not None:
            text, end = _glued_run(attr_toks, start)
            key = attr_toks[start:end]
            if len(key) == 1 and key[0].type is TokenType.STRING:
                if FIT_PLACEHOLDER_RE.search(_string_value(key[0])):
                    return None
            elif names:
                run = text
                label = _fit_label_from_key(key, names)
                if label is None:
                    return None
                attr_toks[start:end] = [
                    Token(
                        TokenType.STRING,
                        f'"{label}"',
                        (key[0].span[0], key[-1].span[1]),
                        quote='"',
                    )
                ]
        restated = 0
        if run is not None:
            for line in self._key_after_graph:
                entry = [
                    t for t in tokenize_line(line) if t.type is not TokenType.COMMENT
                ]
                if (
                    len(entry) > 1
                    and entry[0].value.lower() == "text"
                    and _glued_run(entry, 1)[0] == run
                ):
                    restated += 1
        # Counted in the raw text, so a name inside a string or a
        # ``\expr{}`` counts too.
        lines = self.text.splitlines()
        for var in variables:
            in_key = _mention_count([run], var) if run is not None else 0
            if _mention_count(lines, var) != 1 + in_key * (1 + restated):
                return None
        return attr_toks, run, label

    def _non_dataset_texts(self, block, skip=()) -> List[str]:
        """The text of every statement in ``block`` but its ``dN`` lines.

        The ``let`` of each target in ``skip`` is left out too, and so are
        strings: a title or a file name never reads a dataset.
        """
        texts: List[str] = []
        for child in block.body:
            if isinstance(child, OpaqueBlock):
                texts.extend(self._raw_lines(child))
            elif isinstance(child, Statement) and not (
                child.keyword is not None and _DATASET_RE.match(child.keyword)
            ):
                toks = _words_and_values(child)
                if (
                    child.keyword == "let"
                    and len(toks) > 1
                    and toks[1].value.lower() in skip
                ):
                    continue
                texts.append(
                    " ".join(t.value for t in toks if t.type is not TokenType.STRING)
                )
        return texts

    def _record_derived_let(self, toks, info) -> None:
        """Record ``let dK = <expression> [options]`` that names datasets.

        The expression is read as for :meth:`_record_function_let`, and
        must name at least one ``dN``; the options are those
        :func:`_read_derived_options` reads. Whether the datasets it names
        are series gleplot models is known only at the end of pass 2.
        """
        found = _let_target_expression(toks)
        if found is None:
            return
        target, expression, end = found
        if target in info["_derived_lets"] or target in info["_raw_derived"]:
            return
        if _let_expression_problem(expression) is not None:
            return
        if not _DATASET_NAME_RE.search(expression):
            return
        fields: Dict[str, Any] = {"expression": expression}
        if _read_derived_options(toks, end, fields):
            info["_derived_lets"][target] = fields

    def _keep_plain_derived_lets(self, block, pass1: _GraphDatasets, info) -> None:
        """Drop each recorded derived let whose target is not a plain curve.

        As for a function let, the target must be named by its ``let`` and
        its own ``dK`` lines only, and those lines must be a plain line. A
        ``let dK = dJ+off`` read as an offset is a derived let instead when
        ``dJ`` is drawn too: the writer never draws the dataset it offsets.
        """
        if not info["_derived_lets"]:
            return
        texts = self._non_dataset_texts(block)
        for target in list(info["_derived_lets"]):
            if target in info["_offset_let_datasets"]:
                source = info["_offset_let_sources"][target]
                if source not in pass1.merged_attr_toks:
                    del info["_derived_lets"][target]
                    continue
                self._unregister_offset_let(target, pass1, info)
            attr_toks = pass1.merged_attr_toks.get(target)
            if (
                target in pass1.datasets
                or _mention_count(texts, target) != 1
                or not attr_toks
                or not _plain_function_line(attr_toks)
            ):
                del info["_derived_lets"][target]

    def _keep_unloaded_offset_lets(self, pass1: _GraphDatasets, info) -> None:
        """Leave raw each offset let on a file whose datasets do not all load.

        Unloaded, a series is a reference to the file, which has no offset:
        the let stays as written, with the lines that draw its target. Every
        ``data`` statement of the block is known here, with its options.
        """
        for target in list(info["_offset_let_datasets"]):
            source = info["_offset_let_sources"][target]
            data_file = pass1.datasets.get(source, (None,))[0]
            if not all(
                self._loads(*entry)
                for entry in pass1.datasets.values()
                if entry[0] == data_file
            ):
                self._unregister_offset_let(target, pass1, info)

    @staticmethod
    def _unregister_offset_let(target, pass1: _GraphDatasets, info) -> None:
        """Undo :meth:`_parse_let_command` for ``target``."""
        source = info["_offset_let_sources"].pop(target)
        pass1.datasets.pop(target, None)
        info["_dataset_offsets"].pop(target, None)
        info["_offset_let_datasets"].discard(target)
        if source not in info["_offset_let_sources"].values():
            info["_let_source_datasets"].discard(source)

    @staticmethod
    def _hold_derived_lines(target, lines, info) -> None:
        """Keep a recorded derived let's lines as passthrough, for now.

        Their places are remembered, so :meth:`_commit_derived_lets` can
        take them out again if the let becomes a series.
        """
        held = info["_derived_lets"][target].setdefault("_held", [])
        for line in lines:
            held.append((len(info["passthrough"]), line))
            info["passthrough"].append(line)

    @staticmethod
    def _note_dataset_series(name, before, info) -> None:
        """Remember the series pass 2 just built from dataset ``name``.

        ``before`` holds the length of each list a derived let can read
        before the dataset was parsed. An offset series is noted under the
        dataset it offsets, and a polar curve under the one it is computed
        from: those are the names the writer gives the series, which a
        derived let or a raw line that reads it is bound to.
        """
        grown = [attr for attr, size in before.items() if len(info[attr]) != size]
        if len(grown) != 1 or len(info[grown[0]]) != before[grown[0]] + 1:
            return
        entry = info[grown[0]][-1]
        name = info["_polar_aliases"].get(name.lower(), name.lower())
        raw = info["_offset_let_sources"].get(name, name)
        if grown[0] == "errorbars":
            kind = "errorbar"
        elif grown[0] == "file_series":
            kind = entry.get("series_type")
        else:
            kind = "line"
        if kind == "line":
            info["_dataset_series"][raw] = entry
        if kind in ("line", "errorbar"):
            # A drawn dataset is its series' own: it outranks a fill or bar
            # that also reads it.
            info["_raw_names"][raw] = (entry, "data")
            if raw != name:
                info["_raw_names"][name] = (entry, "offset")

    @staticmethod
    def _note_raw_name(info, name, entry, role) -> None:
        """Remember that ``entry`` writes dataset ``name`` as its ``role``.

        A raw line that reads ``name`` is bound to it (see
        :meth:`_bind_raw_readers`). The first series to claim a name keeps
        it, except that a drawn line or error bar outranks any other
        (:meth:`_note_dataset_series`).
        """
        info["_raw_names"].setdefault(name.lower(), (entry, role))

    def _note_raw_lets(self, info) -> None:
        """Note each ``let`` kept as raw GLE whose target raw GLE uses.

        A let a held statement or a histogram note already explains gets no
        second note.
        """
        defined, read, _bare = GLEWriter.raw_dataset_use(info["passthrough"])
        for target, line_no in info["_let_lines"].items():
            if (
                target not in defined & read
                or target in self._held_datasets
                or target in info["_explained_lets"]
            ):
                continue
            self._note(
                ImportCategory.STRUCTURE,
                f"the let defining {target} is not modelled; it and the lines "
                "that use it were kept as raw GLE and still draw, but are not "
                "editable. To edit the curve, compute its values with numpy "
                "and plot them with Axes.plot()",
                (line_no, line_no),
            )

    @staticmethod
    def _bind_raw_readers(info) -> None:
        """Mark each series whose dataset a raw line in the block reads.

        The series keeps its name here in ``_gle_names``, and the writer
        renames the raw references to the name it writes the series under
        (:meth:`gleplot.writer.GLEWriter._bind_raw_reads`). A name a raw
        ``data`` or ``let`` defines is that raw dataset's, not the series'.
        """
        defined, read, _bare = GLEWriter.raw_dataset_use(info["passthrough"])
        for name, (entry, role) in info["_raw_names"].items():
            if name in read - defined:
                entry.setdefault("_gle_names", {})[role] = name

    def _commit_derived_lets(self, info) -> None:
        """Turn the recorded derived lets into series, if every one can be.

        Each must name only datasets a line, scatter, file line, function
        or fit series came from. If one does not, its target goes in
        ``_derived_failed`` and nothing is built: the block is parsed again
        with that let raw (see :meth:`_parse_graph_block`).
        """
        passthrough = info["passthrough"]
        built = []
        for target, record in info["_derived_lets"].items():
            held = record.get("_held", [])
            names: List[str] = []
            for text in (record["expression"], record.get("let_where", "")):
                for match in _DATASET_NAME_RE.finditer(text):
                    if match.group(0).lower() not in names:
                        names.append(match.group(0).lower())
            sources = self._derived_refs(names, info)
            ranges = self._derived_refs(record.get("_range_names", []), info)
            if (
                "_attr_toks" not in record
                or len(held) < 2
                or sources is None
                or ranges is None
                or len(sources) > 10
                or any(
                    i >= len(passthrough) or passthrough[i] is not line
                    for i, line in held
                )
            ):
                info["_derived_failed"].add(target)
                continue
            built.append((record, names, sources, ranges))
        if info["_derived_failed"]:
            return
        taken: List[int] = []
        for record, names, sources, ranges in built:
            taken.extend(i for i, _line in record["_held"])
            placeholders = {name: f"d{k}" for k, name in enumerate(names, 1)}

            def rename(text: str) -> str:
                return _DATASET_NAME_RE.sub(
                    lambda m: placeholders[m.group(0).lower()], text
                )

            fields: Dict[str, Any] = {
                "expression": rename(record["expression"]),
                "sources": sources,
            }
            for key in ("let_from", "let_to", "let_step", "let_nsteps"):
                if key in record:
                    fields[key] = record[key]
            if "let_where" in record:
                fields["let_where"] = rename(record["let_where"])
            if ranges:
                fields["let_range"] = ranges
            fields.update(self._let_curve_style(record["_attr_toks"]))
            entry = DerivedSeries(**fields)
            entry["_draw_seq"] = record["_draw_seq"]
            info["derived_series"].append(entry)
        for i in sorted(taken, reverse=True):
            del passthrough[i]

    @staticmethod
    def _derived_refs(names, info) -> Optional[List[List[Any]]]:
        """``[attr, index]`` of the series each dataset in ``names`` became."""
        refs: List[List[Any]] = []
        for name in names:
            entry = info["_dataset_series"].get(name)
            if entry is None:
                return None
            ref = next(
                (
                    [attr, index]
                    for attr in Axes._DERIVED_SOURCE_ATTRS
                    for index, item in enumerate(info[attr])
                    if item is entry
                ),
                None,
            )
            if ref is None or ref in refs:
                return None
            refs.append(ref)
        return refs

    def _load_fit_data(self, texts, pass1: _GraphDatasets, info, target) -> bool:
        """Load the data of a recorded fit let into its record.

        True for a function let, which has no data. A fit's ``dJ`` must be
        read by its ``let`` alone, from a gleplot sidecar of its own:
        :meth:`gleplot.writer.GLEWriter.add_fit` rewrites that file with
        just the two columns it fits, which would break any other reader,
        and a file of the caller's own is never rewritten.
        """
        record = info["_function_lets"][target]
        source = record.get("_fit_source")
        if source is None:
            return True
        if not self._owns_sidecar(texts, pass1, info, source):
            return False
        data_file, xcol, ycol = pass1.datasets[source]
        loaded = self._load_series(data_file, xcol, ycol)
        if loaded.get("error"):
            return False
        record["x"] = np.asarray(loaded["x"], dtype=float)
        record["y"] = np.asarray(loaded["y"], dtype=float)
        record["data_file"] = data_file
        return True

    def _owns_sidecar(self, texts, pass1: _GraphDatasets, info, source) -> bool:
        """True when ``source`` is read by its ``let`` alone, from a sidecar.

        The writer rewrites a fit's or histogram's data file with just the
        columns it reads, which would break any other reader of the file, and
        a file of the caller's own is never rewritten. ``texts`` are the
        statements that may read ``source`` (see :meth:`_non_dataset_texts`):
        its ``data`` statement and the ``let`` must be the only two.
        """
        if source not in pass1.datasets:
            return False
        data_file = pass1.datasets[source][0]
        return not (
            source in pass1.merged_attr_toks
            or source in self._data_read_options
            or info.get("_dataset_group", {}).get(source) != [source]
            or _mention_count(texts, source) != 2
            or [entry[0] for entry in pass1.datasets.values()].count(data_file) != 1
            or not self._is_import(data_file)
        )

    def _keep_owned_hist_lets(self, block, pass1: _GraphDatasets, info) -> None:
        """Leave raw each histogram let whose samples it does not own.

        Pass 2 then keeps the ``let`` and its display as written, and the
        source dataset stays defined under its own name for the raw ``let``.
        """
        if not info["_hist_lets"]:
            return
        texts = self._non_dataset_texts(block)
        for target, record in list(info["_hist_lets"].items()):
            source = record["source"]
            if self._owns_sidecar(texts, pass1, info, source):
                continue
            del info["_hist_lets"][target]
            info["_hist_let_pending"].pop(target, None)
            info["_raw_datasets"].add(source)
            info["_explained_lets"].add(target)
            line_no = record["line_no"]
            self._note(
                ImportCategory.DATA,
                f"histogram let {target} reads {source}, which is not in a "
                "gleplot data file only the let reads, so it was kept as raw "
                "GLE and its file is not rewritten. To edit it, load the "
                "samples and call ax.hist()",
                (line_no, line_no) if line_no is not None else None,
            )

    def _build_function_series(self, name, attr_toks, info) -> None:
        """Append the ``FunctionSeries`` or ``FitSeries`` for a kept let."""
        fields = dict(info["_function_lets"][name])
        source = fields.pop("_fit_source", None)
        fields.pop("_result_vars", None)
        fields.update(self._let_curve_style(attr_toks))
        entry: Series
        if source is None:
            entry = FunctionSeries(**fields)
            info["functions"].append(entry)
        else:
            entry = FitSeries(**fields)
            info["fits"].append(entry)
            info["_let_source_datasets"].add(source)
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1

    def _let_curve_style(self, attr_toks) -> Dict[str, Any]:
        """The style fields of a plain ``dK line`` drawing a let's curve."""
        attrs = self._scan_series_attrs(attr_toks)
        style: Dict[str, Any] = {
            "color": attrs["color"],
            "linestyle": attrs["linestyle"] or "-",
            **_dn_width(attrs),
        }
        if attrs["label"]:
            style["label"] = attrs["label"]
        return style

    def _abandon_hist(self, info, target, extra_lines, message, span) -> None:
        """Keep a histogram let, and the display that could not model it."""
        raw = info["_hist_let_pending"].pop(target, None)
        if raw:
            info["passthrough"].append(raw)
        info["passthrough"].extend(extra_lines)
        self._note(ImportCategory.DATA, message, span)

    def _commit_hist_line(
        self, name, toks, datasets, info, line_no=None, raw_stmts=None
    ) -> None:
        """``dK line hist`` on a recorded histogram let, or raw GLE."""
        attrs = self._scan_series_attrs(toks[1:])
        plain = (
            self._hist_line_tokens_ok(toks)
            and attrs["line_mode"] == "hist"
            and attrs["marker"] is None
            and not attrs["nomiss"]
            and not attrs["err_refs"]
            and not attrs["err_consts"]
            and attrs["smooth_mode"] == "none"
            and attrs["svg_smooth"] is None
        )
        span = (line_no, line_no) if line_no is not None else None
        if not plain:
            self._abandon_hist(
                info,
                name,
                self._dn_passthrough_lines(toks, raw_stmts),
                "histogram let "
                + name
                + " is not a plain 'line hist'; kept as raw GLE",
                span,
            )
            return
        entry = self._build_hist_series(
            info,
            name,
            datasets,
            line_no,
            histtype="step",
            linestyle=attrs["linestyle"],
            **_dn_width(attrs),
            **_dn_fields(attrs),
        )
        if entry is None:
            self._abandon_hist(
                info,
                name,
                self._dn_passthrough_lines(toks, raw_stmts),
                "histogram let "
                + name
                + " could not be read from its sample file; kept as raw GLE",
                span,
            )

    @staticmethod
    def _hist_line_tokens_ok(toks) -> bool:
        """True when every token is one ``line hist`` may round-trip.

        A histogram line only round-trips color, width, style, key and
        y2axis; anything else, read by ``_scan_series_attrs`` or not, keeps
        the line raw.
        """
        i = 1
        m = len(toks)
        while i < m:
            word = toks[i].value.lower()
            if word in ("line", "hist", "y2axis", "x2axis"):
                i += 1
                continue
            if word == "color" and i + 1 < m:
                _val, nxt = _collect_color(toks, i + 1)
                if nxt == i + 1:
                    return False
                i = nxt
                continue
            if word in ("lwidth", "lstyle") and i + 1 < m:
                val, nxt = _collect_value(toks, i + 1)
                if val is None:
                    return False
                i = nxt
                continue
            if word == "key" and i + 1 < m and toks[i + 1].type is TokenType.STRING:
                i += 2
                continue
            return False
        return True

    def _try_hist_bar(self, scanned, datasets, info, stmt, toks) -> bool:
        """Model ``bar dK fill`` on a histogram let. True if this call owned it.

        A filled histogram is one dataset, one fill, an optional edge colour
        and an optional width. ``horiz``, ``from``, a group, or an edge
        style belong to ordinary bars; on a histogram let they stay raw.
        """
        d_names = scanned["datasets"]
        if len(d_names) != 1 or d_names[0] not in info["_hist_lets"]:
            return False
        d_name = d_names[0]
        fills = scanned["fills"]
        edges = scanned["edges"]
        fancy = (
            scanned["horiz"]
            or scanned["from_names"]
            or scanned["dist"] is not None
            or scanned["linestyle"] is not None
            or scanned["lstyle"] is not None
            or scanned["linewidth_cm"] is not None
            or (fills is not None and len(fills) != 1)
            or (edges is not None and len(edges) != 1)
            or scanned["patterns"]
            or scanned["backgrounds"]
            or scanned["unmodelled"]
            or scanned["bad_value"]
            or d_name in info["_bar_hold_raw"]
        )
        line = self._bar_fill_passthrough_line(toks, stmt)
        span = self._stmt_span(stmt)
        if fancy or not fills:
            self._abandon_hist(
                info,
                d_name,
                [line],
                "histogram let "
                + d_name
                + " is not a plain 'bar dN fill'; kept as raw GLE",
                span,
            )
            return True
        fields = {"histtype": "stepfilled", "color": fills[0]}
        if edges:
            fields["edgecolor"] = edges[0]
        if scanned["width"] is not None:
            fields["bar_width"] = float(scanned["width"])
        entry = self._build_hist_series(
            info, d_name, datasets, self._opt_line_no(stmt), **fields
        )
        if entry is None:
            self._abandon_hist(
                info,
                d_name,
                [line],
                "histogram let "
                + d_name
                + " could not be read from its sample file; kept as raw GLE",
                span,
            )
            return True
        info["_key_suppress_datasets"].add(d_name)
        info["_key_label_owners"][d_name] = entry
        return True

    def _build_hist_series(self, info, target, datasets, line_no, **fields):
        """Load the let source's y column and append a ``HistSeries``.

        Returns the entry, or ``None`` when the sample file cannot be read
        (the caller keeps the let and the display as raw GLE).
        """
        record = info["_hist_lets"][target]
        source = record["source"]
        data_file, xcol, ycol = datasets[source]
        loaded = self._load_series(data_file, xcol, ycol, line_no=line_no)
        if loaded is None or loaded.get("error"):
            return None
        stored = dict(fields)
        stored["samples"] = np.asarray(loaded["y"], dtype=float)
        stored["data_file"] = data_file
        for key, integral in (
            ("hist_from", False),
            ("hist_to", False),
            ("bins", True),
            ("bin_step", False),
        ):
            value = record.get(key)
            if value is None:
                continue
            number = float(value)
            stored[key] = int(number) if integral and number.is_integer() else number
        if stored.get("label") is None:
            stored.pop("label", None)
        entry = HistSeries(**stored)
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        info["hists"].append(entry)
        self._note_raw_name(info, target, entry, "hist")
        info["_let_source_datasets"].add(source)
        info["_hist_let_pending"].pop(target, None)
        return entry

    #: OP token values that may appear glued mid-filename (hyphenated names,
    #: relative paths, and -- defensively -- a literal '+') when assembling
    #: an unquoted filename from contiguous tokens. See ``_read_filename``.
    _FILENAME_MERGE_OPS = frozenset({"-", "+", "/"})

    @classmethod
    def _read_filename(cls, toks, idx: int) -> Tuple[str, int]:
        """Assemble a data-command filename starting at ``toks[idx]``.

        A quoted filename is a single ``STRING`` token; unwrap it exactly as
        before. An *unquoted* filename may lex as several tokens with no gap
        between them -- e.g. ``20_main.dat`` (``NUMBER``-turned-``WORD`` by
        the lexer, but still possibly split for other digit/word
        combinations), ``my-file.dat`` (``WORD OP('-') WORD``), or
        ``sub/dir/file.dat`` (``WORD OP('/') WORD OP('/') WORD``). Merge a
        maximal run of *span-contiguous* tokens (no whitespace between them)
        whose type is ``WORD``/``NUMBER``, or ``OP`` with a value in
        :data:`_FILENAME_MERGE_OPS`, into one filename string. A whitespace
        gap, ``COMMENT``, ``STRING``, or any other ``OP`` (``=``, ``,``,
        ``(``, ``)``, ``*``, ``^``, ``;``) stops the run -- this is what
        keeps the normal ``data data_0.dat d1=c1,c2`` case correct (the gap
        before ``d1`` stops the merge).

        Returns ``(filename, next_index)`` where ``next_index`` is the index
        of the first token not consumed, so the ``dN=cX,cY`` parsing that
        follows starts in the right place.
        """
        tok = toks[idx]
        if tok.type is TokenType.STRING:
            return _string_value(tok), idx + 1

        parts = [tok.value]
        end = tok.end
        j = idx + 1
        while j < len(toks):
            nxt = toks[j]
            if nxt.start != end:
                break
            if nxt.type is TokenType.WORD or nxt.type is TokenType.NUMBER:
                pass
            elif nxt.type is TokenType.OP and nxt.value in cls._FILENAME_MERGE_OPS:
                pass
            else:
                break
            parts.append(nxt.value)
            end = nxt.end
            j += 1
        return "".join(parts), j

    def _gle_layout(self, data_file, read_options=None) -> Optional[GLEDataLayout]:
        """How GLE reads the file under ``read_options``, or None.

        None when the file is missing or unreadable, or when GLE would stop
        on it (an unterminated string), which is noted.
        """
        options = read_options or {}
        comment = options.get("comment", "!")
        ignore = options.get("skiprows", 0)
        numrows = options.get("max_rows", 0)
        key = (data_file, comment, ignore, numrows)
        if key not in self._layout_cache:
            resolved = self._resolve_table(data_file)
            layout = None
            if resolved.exists and resolved.resolved_path is not None:
                try:
                    layout = gle_data_layout(
                        resolved.resolved_path,
                        comment=comment,
                        ignore=ignore,
                        numrows=numrows,
                    )
                except OSError:
                    layout = None
                except ValueError as exc:
                    self._note(
                        ImportCategory.DATA,
                        f"GLE cannot read '{data_file}' ({exc}); its columns "
                        "are not mapped from the file",
                        None,
                    )
                    layout = None
            self._layout_cache[key] = layout
        return self._layout_cache[key]

    def _file_column_count(self, data_file, read_options=None) -> Optional[int]:
        """Columns GLE reads from the file, or None if it cannot read it."""
        layout = self._gle_layout(data_file, read_options)
        return None if layout is None else layout.n_cols

    def _first_column_is_labels(self, data_file, read_options=None) -> bool:
        """Whether GLE reads the file's first column as x-axis labels.

        GLE (``auto_all_labels_column``) does so when every value in it
        below the header is text; ``nan`` and ``inf`` are text to GLE.
        """
        layout = self._gle_layout(data_file, read_options)
        return layout is not None and layout.labels_column

    # -- bar / fill ------------------------------------------------------

    def _bar_fill_passthrough_line(self, toks, stmt) -> str:
        """Raw text for a ``bar``/``fill`` line that falls back to passthrough.

        Prefer the statement's verbatim source line: re-joining tokens with a
        single space (the old fallback) inserts spaces into comma lists like
        ``d1,d2`` -- GLE parses ``bar d1 , d2`` as an illegal identifier, so
        the passthrough copy must stay byte-identical to the source.
        """
        if stmt is not None:
            return self._stmt_text(stmt)
        return "    " + " ".join(t.value for t in toks)

    def _mark_bars_that_stay_raw(self, block, datasets, info) -> None:
        """Names whose ``bar`` commands must stay raw, expanded to the file.

        A fill that shares the data statement still needs the author's
        line. An unmodelled sub-command, a ``from`` list that is not the
        same length as the datasets, or a group whose x columns disagree
        all do the same: modeling any bar on that file would rewrite the
        sidecar and drop what the raw command reads. On a file gleplot did
        not write, a bar a file reference cannot carry (anything but a plain
        bar with no width) does the same, so a sibling reference does not
        write a ``data`` statement that leaves the raw command's undefined.
        """
        seed = set()
        for child in block.body:
            if not isinstance(child, Statement) or self._skip_meta_stmt(child):
                continue
            toks = _words_and_values(child)
            if child.keyword == "fill":
                for tok in toks:
                    if _DATASET_RE.match(tok.value):
                        seed.add(tok.value.lower())
                continue
            if child.keyword != "bar":
                continue
            scanned = _scan_bar_command(toks)
            names = list(scanned["datasets"]) + list(scanned["from_names"])
            if (
                scanned["unmodelled"]
                or scanned["bad_value"]
                or not scanned["patterns_fit"]
            ):
                seed.update(names)
                continue
            if scanned["from_names"] and len(scanned["from_names"]) != len(
                scanned["datasets"]
            ):
                seed.update(names)
                continue
            # A histogram let is not a file dataset. The hist path decides
            # whether ``bar dK fill`` (including its edge colour) is a
            # stepfilled histogram. Holding it here would abandon that bar.
            if (
                scanned["datasets"]
                and not scanned["from_names"]
                and all(name in info["_hist_lets"] for name in scanned["datasets"])
            ):
                continue
            plain = _bar_scan_is_plain(scanned)
            if any(
                name in datasets and not self._is_import(datasets[name][0])
                for name in names
            ):
                # A bar on a file of the caller's own is a FileSeries
                # reference, which carries only a plain bar with no width.
                if not plain or scanned["width"] is not None:
                    seed.update(names)
                continue
            if plain:
                continue
            loaded = []
            failed = False
            for name in scanned["datasets"] + scanned["from_names"]:
                if name not in datasets:
                    failed = True
                    break
                data_file, xcol, ycol = datasets[name]
                row = self._load_series(data_file, xcol, ycol, line_no=child.line_no)
                if row is None or row.get("error"):
                    failed = True
                    break
                loaded.append(row)
            if failed or not self._bar_xs_match(loaded):
                seed.update(names)
        info["_bar_hold_raw"] = self._expand_bar_hold(info, seed)

    @staticmethod
    def _expand_bar_hold(info, names):
        """``names`` plus every sibling declared on the same data statement."""
        group_map = info.get("_dataset_group", {})
        held: set = set()
        pending = list(names)
        while pending:
            name = pending.pop()
            if name in held:
                continue
            held.add(name)
            for sibling in group_map.get(name, ()):
                if sibling not in held:
                    pending.append(sibling)
        return held

    @staticmethod
    def _bar_xs_match(loaded) -> bool:
        """True when every loaded dataset has the same x column."""
        if len(loaded) < 2:
            return True
        ref = np.asarray(loaded[0]["x"], dtype=float)
        for row in loaded[1:]:
            other = np.asarray(row["x"], dtype=float)
            if ref.shape != other.shape or not np.allclose(
                ref, other, rtol=0, atol=0, equal_nan=True
            ):
                return False
        return True

    @staticmethod
    def _bar_gaps_match(loaded_to, loaded_from) -> bool:
        """True when each ``from`` dataset is missing where its ``to`` is.

        GLE refuses a stack whose two datasets disagree, and the writer
        writes such a row missing in both, which would drop the other value.
        """
        for to_row, from_row in zip(loaded_to, loaded_from):
            to_gaps = np.isnan(np.asarray(to_row["y"], dtype=float))
            from_gaps = np.isnan(np.asarray(from_row["y"], dtype=float))
            if not np.array_equal(to_gaps, from_gaps):
                return False
        return True

    def _keep_bar_raw(self, scanned, info, stmt, toks, user_file=None) -> None:
        """Passthrough for a ``bar`` command, with the note that says why.

        ``user_file`` is the data file, not one gleplot wrote, that the bar
        reads when that is why it stays raw.
        """
        for name in scanned["datasets"]:
            raw = info["_hist_let_pending"].pop(name, None)
            if raw:
                info["passthrough"].append(raw)
        info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
        if scanned["unmodelled"]:
            message = (
                "bar sub-command(s) "
                + ", ".join(scanned["unmodelled"])
                + " have no model; the whole 'bar' command is kept as raw "
                "GLE, not editable"
            )
        elif not scanned["patterns_fit"]:
            message = (
                "bar pattern/background lists that are not one pattern per "
                "dataset, each under a fill, have no model; the whole 'bar' "
                "command is kept as raw GLE, not editable"
            )
        elif user_file is not None:
            message = (
                f"bar on '{user_file}', a data file gleplot did not write, is "
                "kept as raw GLE, not editable, so the file is not rewritten"
            )
        elif len(scanned["datasets"]) > 1 or scanned["from_names"]:
            shown = list(scanned["datasets"])
            for name in scanned["from_names"]:
                if name not in shown:
                    shown.append(name)
            message = (
                "multi-dataset bar group ("
                + ",".join(shown)
                + ") kept as raw GLE, not editable"
            )
        else:
            message = "bar command kept as raw GLE, not editable"
        self._note(ImportCategory.STRUCTURE, message, self._stmt_span(stmt))

    def _parse_bar_command(self, toks, datasets, info, stmt=None):
        """``bar``: one series, a group, or a stack. Unmodelled stays raw.

        A group (``bar d1,d2 fill c1,c2``) is one series per dataset, sharing
        ``group`` and one sidecar. ``from`` stores the baseline and the
        exact top, so the writer can emit ``bar dTo from dFrom`` without
        rebuilding the top by subtraction. A command with an unmodelled
        keyword, or one whose file is shared with a raw ``fill``, is kept
        whole. A bar on a file gleplot did not write is never loaded: a
        plain one is a :class:`~gleplot.series.FileSeries` reference, and
        :meth:`_mark_bars_that_stay_raw` holds any other.
        """
        scanned = _scan_bar_command(toks)
        if self._try_hist_bar(scanned, datasets, info, stmt, toks):
            return

        names = list(scanned["datasets"])
        from_names = list(scanned["from_names"])
        involved = names + from_names
        held = any(name in info["_bar_hold_raw"] for name in involved)
        mismatched_from = bool(from_names) and len(from_names) != len(names)
        if (
            scanned["unmodelled"]
            or scanned["bad_value"]
            or held
            or mismatched_from
            or not scanned["patterns_fit"]
        ):
            user_files = [
                datasets[name][0]
                for name in involved
                if name in datasets and not self._is_import(datasets[name][0])
            ]
            self._keep_bar_raw(
                scanned, info, stmt, toks, user_files[0] if user_files else None
            )
            return
        if not names or any(name not in datasets for name in involved):
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
            return

        # A file of the caller's own is referenced, never rewritten: a bar
        # on it is not loaded, so no sidecar is written over it.
        failed = not all(self._is_import(datasets[name][0]) for name in involved)
        fail_error: Optional[str] = None
        loaded = []
        for name in involved if not failed else ():
            data_file, xcol, ycol = datasets[name]
            row = self._load_series(
                data_file, xcol, ycol, line_no=self._opt_line_no(stmt)
            )
            if row is None or row.get("error"):
                failed = True
                fail_error = (row or {}).get("error", "unresolved")
                break
            loaded.append(row)
        loaded_to, loaded_from = loaded[: len(names)], loaded[len(names) :]
        if failed:
            if _bar_scan_is_plain(scanned) and len(names) == 1:
                if scanned["width"] is not None:
                    # FileSeries has no width, so the reference form would
                    # drop the one number the author wrote down.
                    info["passthrough"].append(
                        self._bar_fill_passthrough_line(toks, stmt)
                    )
                    self._note(
                        ImportCategory.STRUCTURE,
                        "bar width on an unresolved dataset ("
                        + names[0]
                        + ") has no model; the whole 'bar' command is kept "
                        "as raw GLE, not editable",
                        self._stmt_span(stmt),
                    )
                    return
                data_file, xcol, ycol = datasets[names[0]]
                fills = scanned["fills"]
                fs = FileSeries(
                    series_type="bar",
                    data_file=data_file,
                    x_col=xcol,
                    y_col=ycol,
                    color=(fills[0] if fills else "RED"),
                    **self._data_read_options.get(names[0], {}),
                )
                if fail_error is not None:
                    fs["data_error"] = fail_error
                info["file_series"].append(fs)
                self._note_raw_name(info, names[0], fs, "data")
                info["_key_suppress_datasets"].add(names[0])
                info["_key_label_owners"][names[0]] = fs
                return
            self._keep_bar_raw(scanned, info, stmt, toks)
            return
        if not self._bar_xs_match(loaded_to + loaded_from) or not self._bar_gaps_match(
            loaded_to, loaded_from
        ):
            self._keep_bar_raw(scanned, info, stmt, toks)
            return

        data_file = datasets[names[0]][0]
        group_id = None
        if len(names) > 1:
            group_id = info["_bar_group_next"]
            info["_bar_group_next"] += 1
        fills = scanned["fills"]
        edges = scanned["edges"]
        patterns = scanned["patterns"] or []
        backgrounds = scanned["backgrounds"] or []
        style = {}
        if scanned["width"] is not None:
            style["width"] = scanned["width"]
        if scanned["dist"] is not None:
            style["dist"] = scanned["dist"]
        if scanned["horiz"]:
            style["horiz"] = True
        if scanned["linestyle"]:
            style["linestyle"] = scanned["linestyle"]
        if scanned["lstyle"]:
            style["lstyle"] = scanned["lstyle"]
        if scanned["linewidth_cm"] is not None:
            style["linewidth"] = linewidth_cm_to_pt(scanned["linewidth_cm"])

        for index, name in enumerate(names):
            row = loaded_to[index]
            data_file_i, xcol, ycol = datasets[name]
            y = np.asarray(row["y"], dtype=float)
            fields = dict(
                x=np.asarray(row["x"], dtype=float),
                data_file=data_file,
                label=None,
            )
            if from_names:
                base = np.asarray(loaded_from[index]["y"], dtype=float)
                fields["bottom"] = base
                fields["top"] = y.copy()
                fields["height"] = y - base
            else:
                fields["height"] = y
            if fills is None:
                face = "RED"
            elif index < len(fills):
                face = fills[index]
            else:
                face = "RED"
            fields["colors"] = [face] * len(y)
            if group_id is not None and index == 0:
                fields["fill_list"] = list(fills) if fills is not None else []
                if edges:
                    fields["edge_list"] = list(edges)
            elif group_id is None:
                if fills is not None and len(fills) != 1:
                    fields["fill_list"] = list(fills)
                if edges:
                    if len(edges) == 1:
                        fields["edgecolor"] = edges[0]
                    else:
                        fields["edge_list"] = list(edges)
                        fields["edgecolor"] = edges[0]
            elif edges and index < len(edges) and index != 0:
                fields["edgecolor"] = edges[index]
            if index < len(patterns):
                fields["pattern"] = patterns[index]
                if index < len(backgrounds):
                    fields["background"] = backgrounds[index]
            fields.update(style)
            if group_id is not None:
                fields["group"] = group_id
            entry = BarSeries(**fields)
            if not from_names:
                column_names = self._recovered_column_names(data_file_i, [xcol, ycol])
                if column_names is not None:
                    entry["column_names"] = column_names
            entry["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            info["bars"].append(entry)
            self._note_raw_name(info, name, entry, "data")
            if from_names:
                self._note_raw_name(info, from_names[index], entry, "from")
            info["_key_suppress_datasets"].add(name)
            info["_key_label_owners"][name] = entry
        for name in from_names:
            info["_key_suppress_datasets"].add(name)

    def _parse_fill_command(self, toks, datasets, info, stmt=None):
        """``fill dA,dB``, ``fill x1,dN``, ``fill dN,x2`` or ``fill dN``.

        Each form may carry ``color`` and a clip window (``xmin`` / ``xmax``
        / ``ymin`` / ``ymax``), in any order. Anything else — a third
        dataset, an unknown keyword — stays raw, so a multi-dataset fill
        group is not reduced to one series.
        """

        def passthrough():
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))

        i = 1
        m = len(toks)
        operands = []
        option_names = ("color", "xmin", "xmax", "ymin", "ymax")
        while i < m:
            word = toks[i].value.lower()
            if word in option_names:
                break
            if toks[i].type is TokenType.OP and toks[i].value == ",":
                i += 1
                continue
            if _DATASET_RE.match(word) or word in ("x1", "x2"):
                operands.append(word)
                i += 1
                continue
            passthrough()
            return

        color = "LIGHTBLUE"
        clips = {}
        while i < m:
            word = toks[i].value.lower()
            if word == "color" and i + 1 < m:
                val, nxt = _collect_color(toks, i + 1)
                if val is None or nxt == i + 1:
                    passthrough()
                    return
                color = val
                i = nxt
                continue
            if word in ("xmin", "xmax", "ymin", "ymax"):
                val, nxt = _collect_value(toks, i + 1)
                if val is None:
                    passthrough()
                    return
                clips[word] = val
                i = nxt
                continue
            passthrough()
            return

        target = None
        d_names: List[str] = []
        if (
            len(operands) == 2
            and operands[0] == "x1"
            and _DATASET_RE.match(operands[1])
        ):
            target = "x1"
            d_names = [operands[1]]
        elif (
            len(operands) == 2
            and operands[1] == "x2"
            and _DATASET_RE.match(operands[0])
        ):
            target = "x2"
            d_names = [operands[0]]
        elif len(operands) == 2 and all(_DATASET_RE.match(name) for name in operands):
            d_names = list(operands)
        elif len(operands) == 1 and _DATASET_RE.match(operands[0]):
            target = "polygon"
            d_names = [operands[0]]
        else:
            passthrough()
            return
        if any(name not in datasets for name in d_names):
            passthrough()
            return
        if len({datasets[name][0] for name in d_names}) != 1:
            # The fill's series names one file, so both curves must be in it.
            passthrough()
            self._note(
                ImportCategory.STRUCTURE,
                "fill between curves from two data files ("
                + ",".join(d_names)
                + ") has no model; it is kept as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return
        if target is not None:
            # ``data f.dat`` with several columns registers d1, d2, ... .
            # A one-curve fill owns only one of them. Taking it would make
            # the statement mixed: the writer rewrites the file to that
            # curve's columns and the sibling datasets (a grouped ``bar``,
            # or simply the unused columns) no longer resolve. Leave the
            # fill verbatim so the original ``data`` line can be restored.
            # gleplot's own scripts name the one curve explicitly
            # (``d1=c1,c2``), so those still model.
            group = info.get("_dataset_group", {}).get(d_names[0], d_names)
            if any(name not in d_names for name in group):
                passthrough()
                return

        for name in d_names:
            info["_key_suppress_datasets"].add(name)
        f1, xc1, yc1 = datasets[d_names[0]]
        yc2 = None
        if target is None:
            _f2, _xc2, yc2 = datasets[d_names[1]]
        # A file of the caller's own is referenced, never rewritten: a fill
        # on it is not loaded, so no sidecar is written over it.
        loaded: Dict[str, Any] = {}
        if self._is_import(f1):
            loaded = self._load_series(
                f1,
                xc1,
                yc1,
                extra_cols=[yc2] if yc2 is not None else None,
                line_no=self._opt_line_no(stmt),
            )
        if not loaded or loaded.get("error"):
            fs_fields = dict(
                series_type="fill",
                data_file=f1,
                x_col=xc1,
                y1_col=yc1,
                color=color,
            )
            if loaded.get("error"):
                fs_fields["data_error"] = loaded["error"]
            if target is None:
                fs_fields["y2_col"] = yc2
            else:
                fs_fields["target"] = target
            fs_fields.update(clips)
            fs_fields.update(self._data_read_options.get(d_names[0], {}))
            fs = FileSeries(**fs_fields)
            info["file_series"].append(fs)
            self._note_fill_names(info, d_names, fs)
            info["_key_label_owners"][d_names[0]] = fs
            return
        y2 = loaded.get(f"c{yc2}") if yc2 is not None else None
        # 1.0 (opaque), not a guessed fraction: ``color`` as parsed here IS
        # the exact GLE colour text (verbatim, via _collect_color) that will
        # be re-emitted. apply_alpha passes an rgba expression through
        # unchanged, and 1.0 keeps a plain colour a no-op, so a round-tripped
        # fill stays byte-identical (Track G6).
        fill_fields = dict(
            x=loaded["x"],
            y1=loaded["y"],
            y2=y2,
            color=color,
            alpha=1.0,
            label=None,
            offset=info["_dataset_offsets"].get(d_names[0], 0.0),
            data_file=f1,
        )
        if target is None:
            offset2 = info["_dataset_offsets"].get(d_names[1], 0.0)
            if offset2 != fill_fields["offset"]:
                fill_fields["_offset2"] = offset2
        else:
            fill_fields["target"] = target
        fill_fields.update(clips)
        column_names = self._recovered_column_names(
            f1, [xc1, yc1] if target is not None else [xc1, yc1, yc2]
        )
        if column_names is not None:
            fill_fields["column_names"] = column_names
        fill_entry = FillSeries(**fill_fields)
        # A marked fill is an axvspan/axhspan that materialized into this
        # dataset pair (G18-lite). A clip window is not part of a span, so
        # a clipped fill stays a fill and keeps the window.
        if target is None and not clips:
            marker = self._take_guide_marker(d_names[0], "span", info)
            if marker is not None:
                span_entry = self._span_from_marker(
                    marker, fill_entry, d_names[0], info
                )
                if span_entry is not None:
                    info["spans"].append(span_entry)
                    info["_key_label_owners"][d_names[0]] = span_entry
                    return
        info["fills"].append(fill_entry)
        self._note_fill_names(info, d_names, fill_entry)
        info["_key_label_owners"][d_names[0]] = fill_entry

    @classmethod
    def _note_error_names(cls, info, err_refs, entry) -> None:
        """Note an error bar's error datasets for :meth:`_bind_raw_readers`.

        ``err_refs`` maps GLE's ``err``, ``errup``, ... to the dataset each
        names; the role is the writer's name for that error.
        """
        for kind, name in err_refs.items():
            cls._note_raw_name(info, name, entry, _ERROR_ROLES[kind])

    def _note_fill_names(self, info, d_names, entry) -> None:
        """Note a fill's curves for :meth:`_bind_raw_readers`.

        A curve read through an offset alias (``let dK = dJ+off``) is
        written as the source and its alias, as for a line.
        """
        roles = (("data", "offset"), ("second", "second_offset"))
        for name, (role, alias_role) in zip(d_names, roles):
            source = info["_offset_let_sources"].get(name, name)
            self._note_raw_name(info, source, entry, role)
            if source != name:
                self._note_raw_name(info, name, entry, alias_role)

    # -- key -------------------------------------------------------------

    def _parse_key_command(self, toks, info, stmt=None):
        rest = [t.value.lower() for t in toks[1:]]
        # Exactly 'key off' -> recognized.
        if rest == ["off"]:
            info["key_off"] = True
            return
        # A column break. ``lstyle`` is not what we emit; that line stays raw
        # so a styled separator is not rewritten as a bare one.
        if rest == ["separator"]:
            info["key_separators"] = info.get("key_separators", 0) + 1
            return
        # The modelled option set, in any order: 'pos P', 'hei H', 'nobox',
        # 'offset X Y', 'compact', 'background COLOR', 'llen L', 'dist D',
        # 'coldist C', 'margins M M' -- exactly what GLEWriter.add_legend emits. Parse into a scratch
        # dict first so a later unmodelled token leaves ``info`` untouched.
        # Scanned from the Token list (not the lowered strings above) because
        # a negative literal like the writer's own 'offset 1.5 -0.5' tokenizes
        # as an OP '-' followed by a NUMBER, not a single signed NUMBER token.
        parsed = self._scan_key_options(toks[1:])
        if (
            parsed is not None
            and "offset" in parsed
            and parsed.get("pos", info["key_pos"]) is None
        ):
            # Without 'pos', GLE measures 'offset' from the graph origin, not
            # inward from a corner as the model's legend_offset does.
            parsed = None
        if parsed is not None:
            info["key_line"] = True
            info["key_pos"] = parsed.get("pos", info["key_pos"])
            info["key_hei"] = parsed.get("hei", info["key_hei"])
            info["key_nobox"] = parsed.get("nobox", info["key_nobox"])
            info["key_offset"] = parsed.get("offset", info["key_offset"])
            if parsed.get("compact"):
                info["key_compact"] = True
            if parsed.get("background"):
                info["key_background"] = parsed["background"]
            info["key_spacing"].update(parsed.get("spacing", {}))
            return
        # Any richer form ('justify', 'absolute', unequal 'margins', a
        # styled separator) carries options we cannot model; a cumulative
        # re-emit would produce a competing 'key' line. Keep the WHOLE original line as raw GLE
        # (legend untouched) and warn.
        line = (
            self._stmt_text(stmt)
            if stmt is not None
            else ("    " + " ".join(t.value for t in toks))
        )
        info["passthrough"].append(line)
        self._note(
            ImportCategory.LEGEND,
            "key has unsupported options; kept as raw GLE, not editable",
            self._stmt_span(stmt),
        )

    @staticmethod
    def _key_literal_number(toks: List[Token], i: int) -> Tuple[Optional[float], int]:
        """Read a literal (non-expression) number at ``toks[i]``.

        Accepts a single ``NUMBER`` token, or an OP ``-`` immediately
        followed by one -- GLE's tokenizer never fuses a leading sign into
        the NUMBER token, so ``offset 1.5 -0.5`` lexes as
        ``NUMBER('1.5') OP('-') NUMBER('0.5')``. Deliberately does not fall
        back to :func:`_collect_value`'s full expression grammar (``2*pi``
        etc.): ``hei``/``offset`` only model literal numbers, exactly as
        before this fix -- an expression still falls through to raw
        passthrough of the whole ``key`` line.
        """
        if i >= len(toks):
            return None, i
        t = toks[i]
        if t.type is TokenType.NUMBER:
            try:
                return float(t.value), i + 1
            except ValueError:
                return None, i
        if (
            t.type is TokenType.OP
            and t.value == "-"
            and i + 1 < len(toks)
            and toks[i + 1].type is TokenType.NUMBER
        ):
            try:
                return -float(toks[i + 1].value), i + 2
            except ValueError:
                return None, i
        return None, i

    @classmethod
    def _scan_key_options(cls, toks: List[Token]):
        """Scan the tokens after ``key`` into the modelled option dict.

        Returns ``None`` as soon as a token outside the modelled set appears,
        so the caller can fall back to raw passthrough. A ``pos``/``hei``
        without its value, or a non-numeric ``hei``/``offset`` component, is
        likewise unmodelled.
        """
        out: dict = {}
        i = 0
        n = len(toks)
        while i < n:
            t = toks[i]
            word = t.value.lower() if t.type is TokenType.WORD else None
            if word == "nobox":
                out["nobox"] = True
                i += 1
            elif word in ("pos", "position") and i + 1 < n:
                out["pos"] = toks[i + 1].value.lower()
                i += 2
            elif word == "hei" and i + 1 < n:
                hei, nxt = cls._key_literal_number(toks, i + 1)
                if hei is None:
                    return None  # an expression, not a literal height
                out["hei"] = hei
                i = nxt
            elif word == "offset" and i + 1 < n:
                dx, nxt = cls._key_literal_number(toks, i + 1)
                if dx is None:
                    return None  # expressions, not literal displacements
                dy, nxt2 = cls._key_literal_number(toks, nxt)
                if dy is None:
                    return None
                out["offset"] = (dx, dy)
                i = nxt2
            elif word == "compact":
                out["compact"] = True
                i += 1
            elif word == "background" and i + 1 < n:
                color, nxt = _collect_color(toks, i + 1)
                if color is None or nxt == i + 1:
                    return None
                out["background"] = color
                i = nxt
            elif word in _KEY_SPACING_WORDS and i + 1 < n:
                length, nxt = cls._key_literal_number(toks, i + 1)
                if length is None:
                    return None
                if word == "margins":
                    # One matplotlib borderpad is both margins.
                    second, nxt = cls._key_literal_number(toks, nxt)
                    if second != length:
                        return None
                out.setdefault("spacing", {})[word] = length
                i = nxt
            else:
                return None
        return out or None

    # -- series command --------------------------------------------------

    def _parse_series_command(
        self,
        toks,
        datasets,
        info,
        marker_cfg,
        smooth_flags,
        line_no=None,
        raw_stmts=None,
    ):
        """Parse a ``dN ...`` dataset display command into a series entry.

        ``toks`` are the dataset's merged attribute tokens, led by ``dN``.
        ``line_no`` is the first body-order statement that named this
        dataset (the same anchor pass 1 merged its attributes from), threaded
        through so notes raised while building the series carry a real span.

        ``raw_stmts`` is the verbatim source text of each physical 'dN ...'
        statement that fed ``toks`` (usually just one), threaded through so a
        passthrough fallback can re-emit byte-identical source instead of
        rejoining tokens with inserted spaces.
        """
        d_name = toks[0].value.lower()
        attrs = self._scan_series_attrs(toks[1:])

        # File-vs-import classification decided later per data_file. First
        # figure out the data_file for the main dataset.
        if d_name not in datasets:
            # A dataset raw GLE defines (a 'let' kept raw) -> passthrough,
            # and a raw line, so the 'data' statements of the datasets it
            # names are kept (_restore_orphaned_data_stmts).
            info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
            info["_raw_datasets"].add(d_name)
            return
        data_file, xcol, ycol = datasets[d_name]

        # A ``data "<base>-cdata.dat" dN=c1,c2`` + ``dN line ...`` pair is a
        # contour series' generated polyline, not a broken file line series --
        # but only when the prescan actually recognized (and will reconstruct)
        # the feeding contour/fitz block. A ``-cdata.dat`` reference with no
        # recognized block falls through to ordinary file-series handling so the
        # ``data`` command and its display line are preserved verbatim.
        if isinstance(data_file, str) and data_file.endswith("-cdata.dat"):
            zfile = data_file[: -len("-cdata.dat")] + ".z"
            if zfile in self._contour_blocks or zfile in self._fitz_blocks:
                self._build_contour_from_cdata(
                    data_file, toks, info, line_no=line_no, raw_stmts=raw_stmts
                )
                return

        if attrs["mdata"] is not None and str(attrs["marker"] or "").lower().startswith(
            CDATA_SUB_PREFIX
        ):
            self._build_coloured_scatter(
                info, d_name, datasets, attrs, toks, line_no, raw_stmts
            )
            return
        if attrs["mdata"] is not None:
            self._build_sized_scatter(
                info, d_name, datasets, attrs, toks, line_no, raw_stmts
            )
            return

        if attrs["unread"] and self._keep_unread_line_raw(
            d_name, attrs, info, toks, line_no, raw_stmts
        ):
            return

        has_line = attrs["has_line"]
        has_marker = attrs["marker"] is not None
        is_errorbar = bool(attrs["err_refs"]) or bool(attrs["err_consts"])

        # Determine import vs reference for THIS data_file.
        is_import = self._is_import(data_file)

        if is_errorbar:
            if not is_import and self._keep_file_errorbar_raw(
                d_name, datasets, attrs, info, toks, line_no, raw_stmts
            ):
                return
            self._observe_unmodelled_smoothing("error-bar", attrs, line_no)
            self._build_errorbar(
                info,
                datasets,
                data_file,
                xcol,
                ycol,
                attrs,
                is_import,
                orig_toks=toks,
                line_no=line_no,
                raw_stmts=raw_stmts,
            )
            return

        if not is_import:
            self._observe_unmodelled_smoothing("file-reference", attrs, line_no)
            self._build_file_series(
                info, d_name, data_file, xcol, ycol, attrs, has_line
            )
            return

        # Import series: load arrays.
        loaded = self._load_series(data_file, xcol, ycol, line_no=line_no)
        if loaded is None or loaded.get("error"):
            self._observe_unmodelled_smoothing("file-reference", attrs, line_no)
            self._build_file_series(
                info,
                d_name,
                data_file,
                xcol,
                ycol,
                attrs,
                has_line,
                error=(loaded or {}).get("error", "unresolved"),
            )
            return
        x = loaded["x"]
        y = loaded["y"]

        linestyle = attrs["linestyle"] if has_line else "none"

        is_scatter = has_marker and not has_line
        entry = (ScatterSeries if is_scatter else LineSeries)(
            type="scatter" if is_scatter else "line",
            x=x,
            y=y,
            marker=attrs["marker"],
            markersize=_dn_markersize(attrs),
            linestyle=linestyle,
            **_dn_width(attrs),
            nomiss=attrs["nomiss"],
            **_dn_fields(attrs),
            offset=info["_dataset_offsets"].get(d_name, 0.0),
            data_file=data_file,
        )
        entry.update(attrs["qualifiers"])
        column_names = self._recovered_column_names(data_file, [xcol, ycol])
        if column_names is not None:
            entry["column_names"] = column_names
        if is_scatter:
            entry["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            info["scatters"].append(entry)
        else:
            if attrs["line_mode"]:
                entry["line_mode"] = attrs["line_mode"]
            if self._has_gle_missing(data_file, [xcol, ycol]):
                entry["gaps"] = True
            # A marked line is an axvline/axhline that materialized into this
            # dataset (G18-lite): it becomes the declaration it came from,
            # never a drawable, so it takes no ``_draw_seq`` and no smoothing
            # bookkeeping. A mismatch falls straight through to the plain
            # LineSeries below -- the pre-G18-lite recovery, unchanged.
            marker = self._take_guide_marker(d_name, "refline", info)
            if marker is not None:
                refline = self._refline_from_marker(marker, entry, attrs, d_name, info)
                if refline is not None:
                    info["reflines"].append(refline)
                    return
            entry["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            info["lines"].append(entry)
            smooth_flags.append(attrs["smooth"])
            # Per-series smoothing is stamped on the entry only once the
            # figure-wide default is known -- see _apply_smooth.
            self._smooth_lines.append(
                (entry, attrs["smooth_mode"], attrs["svg_smooth"])
            )

    def _keep_unread_line_raw(
        self, d_name, attrs, info, toks, line_no, raw_stmts
    ) -> bool:
        """Keep a ``dN`` line with unread tokens as written, when it can be.

        A series built from the line would drop them on re-save. The line
        stays raw, with its dataset kept defined, unless something else
        the writer emits depends on the series: a dataset drawn through a
        ``let`` the recognizer consumed (an offset alias, a polar curve), or
        one on a secondary axis, which the layout reserves room for. Then
        the series is modelled and the note says what is dropped. Returns
        whether the line was kept raw.
        """
        unread = " ".join(attrs["unread"])
        span = (line_no, line_no) if line_no is not None else None
        if (
            d_name in info["_offset_let_datasets"]
            or info["polar_rmax"] is not None
            or attrs["y2axis"]
            or attrs["x2axis"]
        ):
            self._note(
                ImportCategory.DATA,
                f"'{unread}' on {d_name} is not modelled and was dropped on " "re-save",
                span,
            )
            return False
        info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
        info["_raw_datasets"].add(d_name)
        self._note(
            ImportCategory.DATA,
            f"'{unread}' on {d_name} is not modelled; the dataset line was "
            "kept as raw GLE and still draws, but is not editable",
            span,
        )
        return True

    def _build_coloured_scatter(
        self, info, d_name, datasets, attrs, toks, line_no, raw_stmts
    ) -> None:
        """A ``dN`` line with a ``gleplot_cdata_`` marker -> per-point colours.

        Modelled only in the form :meth:`GLEWriter.add_scatter` writes: a
        marker-only dataset whose marker is a ``gleplot_cdata_<marker>_<cmap>``
        sub and whose ``mdata`` is a recorded colour let of a column of the
        same imported file. Anything else stays raw GLE, the let with it, and
        gets a note.
        """
        name = str(attrs["marker"]).lower()
        builtin, _, cmap = name[len(CDATA_SUB_PREFIX) :].partition("_")
        try:
            known_cmap = canonical_cmap(cmap) == cmap
        except ValueError:
            known_cmap = False
        let = info["_colour_lets"].get(attrs["mdata"])
        modelled = self._build_mdata_scatter(
            info,
            d_name,
            datasets,
            attrs,
            (toks, line_no, raw_stmts),
            marker=builtin.upper() if known_cmap and let is not None else "",
            extra_ref=datasets.get(let["source"]) if let is not None else None,
            fields=lambda values: {
                "cdata": np.asarray(values, dtype=float),
                "cmap": cmap,
                "vmin": let["vmin"],
                "vmax": let["vmax"],
            },
            what=f"per-point colours ('mdata' with marker {name})",
            values="values",
            raw_before=[let["raw"]] if let is not None else [],
        )
        if modelled:
            # The values' dataset is read through the let, not a line of its own.
            info["_let_source_datasets"].add(let["source"])

    def _build_sized_scatter(
        self, info, d_name, datasets, attrs, toks, line_no, raw_stmts
    ) -> None:
        """A ``dN`` line with ``mdata`` -> a scatter with per-point sizes.

        Modelled only in the form :meth:`GLEWriter.add_scatter` writes: a
        marker-only dataset whose marker is a ``gleplot_mdata_<marker>`` sub
        and whose sizes are a column of the same imported file. Anything else
        (a marker sub of the user's own, a built-in marker, which GLE draws
        at one size whatever ``mdata`` says, a line, error bars) stays raw
        GLE with a note.
        """
        marker = str(attrs["marker"] or "").lower()
        self._build_mdata_scatter(
            info,
            d_name,
            datasets,
            attrs,
            (toks, line_no, raw_stmts),
            marker=(
                marker[len(MDATA_SUB_PREFIX) :].upper()
                if marker.startswith(MDATA_SUB_PREFIX)
                else ""
            ),
            extra_ref=datasets.get(attrs["mdata"]),
            fields=lambda sizes: {"mdata": np.asarray(sizes, dtype=float)},
            what="per-point marker sizes ('mdata')",
            values="sizes",
            raw_before=[],
        )

    def _build_mdata_scatter(
        self,
        info,
        d_name,
        datasets,
        attrs,
        source,
        *,
        marker: str,
        extra_ref,
        fields,
        what: str,
        values: str,
        raw_before: List[str],
    ) -> bool:
        """Model a ``dN ... mdata dK`` scatter, or keep it raw with a note.

        ``marker`` is the built-in marker the generated sub draws (empty when
        the sub is not one gleplot writes), ``extra_ref`` the dataset holding
        the per-point column, and ``fields`` maps that column to the series
        fields. ``source`` is the statement's ``(toks, line_no, raw_stmts)``.
        Returns whether the scatter was modelled.
        """
        toks, line_no, raw_stmts = source
        data_file, xcol, ycol = datasets[d_name]
        loaded: Dict[str, Any] = {}
        if (
            marker in MARKERS
            and not attrs["unread"]
            and not attrs["has_line"]
            and not attrs["err_refs"]
            and not attrs["err_consts"]
            and extra_ref is not None
            and extra_ref[0] == data_file
            and self._is_import(data_file)
        ):
            loaded = self._load_series(
                data_file, xcol, ycol, extra_cols=[extra_ref[2]], line_no=line_no
            )
        extra = None
        if extra_ref is not None and not loaded.get("error"):
            extra = loaded.get(f"c{extra_ref[2]}")
        if extra is None or len(extra) != len(loaded["x"]):
            info["passthrough"].extend(raw_before)
            info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
            info["_raw_datasets"].update((d_name, attrs["mdata"]))
            # A file that could not be read already has its own note.
            if loaded.get("error"):
                why = "its data could not be read"
            elif attrs["unread"]:
                why = f"the line also has '{' '.join(attrs['unread'])}'"
            else:
                why = (
                    "they are modelled only on a marker-only scatter gleplot "
                    f"wrote, with the {values} in its own data file"
                )
            self._note(
                ImportCategory.DATA,
                f"{what} on {d_name} were not modelled because {why}; the "
                "dataset line was kept as raw GLE, not editable",
                (line_no, line_no) if line_no is not None else None,
            )
            return False
        entry = ScatterSeries(
            type="scatter",
            x=loaded["x"],
            y=loaded["y"],
            marker=marker,
            markersize=_dn_markersize(attrs),
            linestyle="none",
            **_dn_width(attrs),
            nomiss=attrs["nomiss"],
            **_dn_fields(attrs),
            offset=info["_dataset_offsets"].get(d_name, 0.0),
            data_file=data_file,
            **fields(extra),
        )
        entry.update(attrs["qualifiers"])
        column_names = self._recovered_column_names(
            data_file, [xcol, ycol, extra_ref[2]]
        )
        if column_names is not None:
            entry["column_names"] = column_names
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        info["scatters"].append(entry)
        return True

    def _scan_series_attrs(self, toks) -> dict:
        """Flat scan of dataset attribute tokens (order-tolerant).

        Order-tolerant with one deliberate exception: the smoothing keywords.
        GLE's own ``dn`` keyword loop (``graph2.cpp``) is a left-to-right
        state machine in which ``svg_smooth`` *clears* ``smooth``/``smoothm``
        while ``smooth``/``smoothm`` leave ``svg_smooth`` alone, so
        ``d1 smooth svg_smooth 2`` and ``d1 svg_smooth 2 smooth`` are two
        different pictures. This scan replays that state machine rather than
        collecting flags, so the recovered model is what GLE would draw --
        verified against GLE 4.3.10.

        All three keywords also set GLE's ``line`` flag (a smoothed dataset
        draws a curve whether or not ``line`` was written), which is why they
        set ``has_line`` here, exactly as ``lstyle`` already does.

        Every token the scan does not read (a keyword no series models, such
        as ``mscale`` or ``mcolor``, or a value it cannot evaluate) is listed
        in ``unread``, so a caller keeps the line raw instead of dropping it.
        """
        a: Dict[str, Any] = {
            "has_line": False,
            # True when the dataset ends up with GLE's ``smooth`` flag set,
            # i.e. mode is smooth or smoothm. Feeds the figure-wide
            # smooth_curves inference in :meth:`_apply_smooth`.
            "smooth": False,
            # SPEC 14.7: 'none' | 'smooth' | 'smoothm', and the Savitzky-Golay
            # iteration count (>= 1) or None.
            "smooth_mode": "none",
            "svg_smooth": None,
            "nomiss": False,
            "color": None,
            "lwidth": None,
            "lstyle": None,
            "linestyle": "-",
            # GLE line mode (steps/fsteps/hist/bar/impulses), or None for a
            # plain polyline. Last keyword wins, matching graph2.cpp.
            "line_mode": None,
            "marker": None,
            "msize": None,
            # ``mdata dK``: the dataset of per-point marker sizes, or None.
            "mdata": None,
            "y2axis": False,
            "x2axis": False,
            "label": None,
            "err_refs": {},  # kind -> dataset name (err/errup/errdown/herr/herrleft/herrright)
            "err_consts": {},  # kind -> (value: float, is_percent: bool) for literals
            "errwidth": None,
            "herrwidth": None,
            # mdist / deresolve / deresolve_average / xmin..ymax, each only
            # when written: the series fields of the same names.
            "qualifiers": {},
            # Source text of every token the scan did not read: a keyword
            # no series models, or a value it could not evaluate.
            "unread": [],
        }
        i = 0
        m = len(toks)
        while i < m:
            t = toks[i]
            w = t.value.lower()
            if w == "line":
                a["has_line"] = True
                i += 1
                continue
            if w in LINE_MODES:
                # graph2.cpp assigns line_mode and, after the keyword loop,
                # any non-plain mode implies ``line`` even without the
                # keyword. The last mode keyword wins.
                a["has_line"] = True
                a["line_mode"] = w
                i += 1
                continue
            if w in ("smooth", "smoothm"):
                # graph2.cpp: both set line = true and smooth = true; smoothm
                # additionally sets the multi-valued flag. Neither touches
                # svg_smooth.
                a["has_line"] = True
                a["smooth"] = True
                a["smooth_mode"] = w
                i += 1
                continue
            if w == "svg_smooth" and i + 1 < m:
                # graph2.cpp: svg_iter = next_exp (coerced up to 1 -- "if they
                # say svg_smooth they want it at least once"), line = true,
                # and smooth/smoothm are CLEARED.
                v, nxt = _collect_value(toks, i + 1)
                if v is None:
                    # No evaluable argument: GLE itself rejects this line
                    # ("constant, function, or unary operator expected"), so
                    # there is no engine behaviour to mirror. Skip the keyword
                    # and let the remaining tokens scan normally.
                    a["unread"].append(t.value)
                    i += 1
                    continue
                a["has_line"] = True
                a["svg_smooth"] = max(1, int(v))
                a["smooth"] = False
                a["smooth_mode"] = "none"
                i = nxt
                continue
            if w == "nomiss":
                a["nomiss"] = True
                i += 1
                continue
            if w in ("mdist", "xmin", "xmax", "ymin", "ymax") and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None and math.isfinite(v):
                    a["qualifiers"][w] = float(v)
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "deresolve" and i + 1 < m:
                # graph2.cpp: deresolve = (int) next_exp, and ``average`` is
                # read only as the very next token; a later deresolve resets
                # it.
                v, nxt = _collect_value(toks, i + 1)
                if v is None or not math.isfinite(v):
                    a["unread"].append(t.value)
                    i += 1
                    continue
                a["qualifiers"]["deresolve"] = int(v)
                a["qualifiers"].pop("deresolve_average", None)
                if nxt < m and toks[nxt].value.lower() == "average":
                    a["qualifiers"]["deresolve_average"] = True
                    nxt += 1
                i = nxt
                continue
            if w == "color" and i + 1 < m:
                val, nxt = _collect_color(toks, i + 1)
                a["color"] = val
                i = nxt
                continue
            if w == "lwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["lwidth"] = v
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "lstyle" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["lstyle"] = int(v)
                    a["linestyle"] = LSTYLE_TO_MATPLOTLIB.get(int(v), "-")
                    # GLE draws a line whenever EITHER the 'line' keyword is
                    # given OR 'lstyle' names a style at all (GLE's own
                    # draw-a-line test, graph2.cpp: 'dp[dn]->line ||
                    # dp[dn]->lstyle[0] != 0') -- 'dN lstyle 2 color red'
                    # with no 'line' keyword anywhere (the GLE manual's own
                    # nomiss example) is a real, visible line, not a bare
                    # dataset. Missing this made has_line False, which fed
                    # linestyle="none" into the model and, downstream, an
                    # unconditional 'marker None' from the writer's
                    # no-line branch (see GLEWriter.add_line).
                    a["has_line"] = True
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "marker" and i + 1 < m:
                a["marker"] = toks[i + 1].value
                i += 2
                continue
            if w == "mdata" and i + 1 < m:
                a["mdata"] = toks[i + 1].value.lower()
                i += 2
                continue
            if w == "msize" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["msize"] = v
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if (
                w in ("err", "errup", "errdown", "herr", "herrleft", "herrright")
                and i + 1 < m
            ):
                nxt_tok = toks[i + 1]
                nxt_val = nxt_tok.value.lower()
                if nxt_tok.type is TokenType.WORD and _DATASET_RE.match(nxt_val):
                    # Reference to another dataset's y column.
                    a["err_refs"][w] = nxt_val
                    i += 2
                    continue
                # Literal constant or percentage: 'err 0.5' or 'err 10%'.
                const, nxt = _collect_value(toks, i + 1)
                if const is not None:
                    is_percent = nxt < m and toks[nxt].value == "%"
                    if is_percent:
                        nxt += 1
                    a["err_consts"][w] = (const, is_percent)
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "errwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["errwidth"] = v
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "herrwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["herrwidth"] = v
                    i = nxt
                    continue
                a["unread"].append(t.value)
                i += 1
                continue
            if w == "y2axis":
                a["y2axis"] = True
                i += 1
                continue
            if w == "x2axis":
                a["x2axis"] = True
                i += 1
                continue
            if w == "key" and i + 1 < m and toks[i + 1].type is TokenType.STRING:
                # 'key ""' is never a real user label -- the writer only ever
                # emits it as an auto-key-from-header suppression marker
                # (see writer._key_clause), for a series whose label is
                # None. Recover it as None (not '') so the object model
                # round-trips exactly; the writer regenerates the same
                # 'key ""' from column_names + no label on next save.
                label_value = _string_value(toks[i + 1])
                a["label"] = label_value if label_value != "" else None
                i += 2
                continue
            a["unread"].append(t.value)
            i += 1
        return a

    def _note_dropped_line_mode(self, attrs, span) -> None:
        """Warn when an error-bar dataset's line mode will not be re-emitted.

        The mode is modelled on line series. An error bar that also says
        ``steps`` (and so on) used to drop the keyword silently because the
        scanner skipped it. Now that the keyword is recognized, say so.
        Callers that keep the original ``dN`` line as passthrough must not
        call this: the mode is still in the script.
        """
        mode = attrs.get("line_mode")
        if not mode:
            return
        self._note(
            ImportCategory.DATA,
            f"line mode {mode!r} on an error-bar dataset is not modelled "
            "and was dropped on re-save",
            span,
        )

    def _keep_file_errorbar_raw(
        self, d_name, datasets, attrs, info, toks, line_no, raw_stmts
    ) -> bool:
        """Keep an error-bar line on a user's file raw if a reference loses part.

        :meth:`gleplot.axes.Axes.errorbar_from_file` draws markers and one
        symmetric vertical error read from the same file; a connecting line,
        its ``lwidth``, ``nomiss``, horizontal or one-sided errors, or an
        error from elsewhere have no field there. When the line sets one it
        stays raw, with its datasets kept defined, unless the writer depends
        on its series (see :meth:`_keep_unread_line_raw`); then the note says
        what is dropped. Returns whether the line was kept raw.
        """
        data_file = datasets[d_name][0]
        err_ref = attrs["err_refs"].get("err")
        unwritable = [
            word
            for word, present in (
                ("a connecting line", attrs["has_line"]),
                ("lwidth", attrs["lwidth"] is not None),
                ("nomiss", attrs["nomiss"]),
                (
                    f"err {err_ref} not read from that file",
                    err_ref is not None
                    and datasets.get(err_ref, (None,))[0] != data_file,
                ),
            )
            if present
        ]
        unwritable += [kind for kind in attrs["err_refs"] if kind != "err"]
        if not unwritable:
            return False
        what = ", ".join(unwritable)
        span = (line_no, line_no) if line_no is not None else None
        if (
            d_name in info["_offset_let_datasets"]
            or info["polar_rmax"] is not None
            or attrs["y2axis"]
            or attrs["x2axis"]
        ):
            self._note(
                ImportCategory.DATA,
                f"{what} on error-bar dataset {d_name} is not modelled and was "
                "dropped on re-save",
                span,
            )
            return False
        self._passthrough_original_dn(info, toks, raw_stmts)
        info["_raw_datasets"].add(d_name)
        info["_raw_datasets"].update(attrs["err_refs"].values())
        self._note(
            ImportCategory.DATA,
            f"{what} on an error-bar dataset read from '{data_file}' is not "
            "modelled; its 'dN ... err' line was kept as raw GLE and still "
            "draws, but is not editable. To edit it, load the columns and plot "
            "them with Axes.errorbar()",
            span,
        )
        return True

    def _build_errorbar(
        self,
        info,
        datasets,
        data_file,
        xcol,
        ycol,
        attrs,
        is_import,
        orig_toks=None,
        line_no=None,
        raw_stmts=None,
    ):
        """Reconstruct an errorbar entry, matching Axes.errorbar's dict schema."""
        span = (line_no, line_no) if line_no is not None else None
        # Resolve error column indices from referenced datasets.
        err = attrs["err_refs"]
        err_consts = attrs["err_consts"]

        # Constant / percentage errors ('err 0.5', 'err 10%') carry no data
        # column; GLE synthesizes the error at draw time. We convert them to a
        # concrete data column on save. This requires the y (and, for herr, x)
        # arrays, so it only works when the referencing series can be loaded.
        if err_consts and (not is_import):
            # A file reference stays a reference: its data is never pulled
            # into a gleplot sidecar. Keep the ORIGINAL dN line raw, and its
            # dataset defined (_restore_orphaned_data_stmts).
            self._passthrough_original_dn(info, orig_toks, raw_stmts)
            if orig_toks:
                info["_raw_datasets"].add(orig_toks[0].value.lower())
            self._note(
                ImportCategory.DATA,
                f"a constant error bar on a dataset read from '{data_file}' "
                "is not modelled; its 'dN ... err' line was kept as raw GLE "
                "and still draws, but is not editable. To edit it, load the "
                "columns and plot them with Axes.errorbar(x, y, yerr=...)",
                span,
            )
            return

        def col_of(ref_name):
            ref = ref_name.lower()
            if ref in datasets:
                _f, _xc, yc = datasets[ref]
                return yc
            return None

        yerr_up_col = None
        yerr_down_col = None
        xerr_left_col = None
        xerr_right_col = None
        if "err" in err:
            yerr_up_col = yerr_down_col = col_of(err["err"])
        else:
            if "errup" in err:
                yerr_up_col = col_of(err["errup"])
            if "errdown" in err:
                yerr_down_col = col_of(err["errdown"])
        if "herr" in err:
            xerr_left_col = xerr_right_col = col_of(err["herr"])
        else:
            if "herrleft" in err:
                xerr_left_col = col_of(err["herrleft"])
            if "herrright" in err:
                xerr_right_col = col_of(err["herrright"])

        # capsize: writer emits errwidth (from gle_capsize) for yerr, herrwidth
        # for xerr; both derive from the SAME stored capsize. Recover via
        # capsize_cm_to_pt.
        cap_cm = (
            attrs["errwidth"] if attrs["errwidth"] is not None else attrs["herrwidth"]
        )
        gle_capsize = cap_cm
        stored_capsize = capsize_cm_to_pt(cap_cm) if cap_cm is not None else None

        marker = attrs["marker"]
        markersize = _dn_markersize(attrs)
        # The writer emits ' line lwidth ...' when a linestyle is present with a
        # marker; a marker-only errorbar with no 'line' token has linestyle
        # 'none'. Recover linestyle from lstyle / presence of line.
        linestyle = attrs["linestyle"] if attrs["has_line"] else "none"
        read_options = (
            self._data_read_options.get(orig_toks[0].value.lower(), {})
            if orig_toks
            else {}
        )

        if not is_import:
            # File-series errorbar reference.
            yerr_col = yerr_up_col if yerr_up_col is not None else None
            info["file_series"].append(
                FileSeries(
                    series_type="errorbar",
                    data_file=data_file,
                    x_col=xcol,
                    y_col=ycol,
                    yerr_col=yerr_col,
                    marker=marker,
                    markersize=markersize,
                    capsize=gle_capsize,
                    **_dn_fields(attrs),
                    **attrs["qualifiers"],
                    **read_options,
                )
            )
            self._note_error_names(info, err, info["file_series"][-1])
            return

        extra = [
            c
            for c in (yerr_up_col, yerr_down_col, xerr_left_col, xerr_right_col)
            if c is not None
        ]
        loaded = self._load_series(
            data_file, xcol, ycol, extra_cols=extra, line_no=line_no
        )
        if loaded is None or loaded.get("error"):
            if err_consts:
                # Cannot synthesize a constant-error column without the y data.
                self._passthrough_original_dn(info, orig_toks, raw_stmts)
                self._note(
                    ImportCategory.DATA,
                    "constant error but the dataset could not be loaded; "
                    "original 'dN ... err' line kept as raw GLE",
                    span,
                )
                return
            yerr_col = yerr_up_col if yerr_up_col is not None else None
            self._note_dropped_line_mode(attrs, span)
            info["file_series"].append(
                FileSeries(
                    series_type="errorbar",
                    data_file=data_file,
                    x_col=xcol,
                    y_col=ycol,
                    yerr_col=yerr_col,
                    marker=marker,
                    markersize=markersize,
                    capsize=gle_capsize,
                    **_dn_fields(attrs),
                    **attrs["qualifiers"],
                    **read_options,
                    data_error=(loaded or {}).get("error", "unresolved"),
                )
            )
            self._note_error_names(info, err, info["file_series"][-1])
            return

        def col_arr(c):
            return loaded.get(f"c{c}") if c is not None else None

        offset = (
            info["_dataset_offsets"].get(orig_toks[0].value.lower(), 0.0)
            if orig_toks
            else 0.0
        )

        yerr_up = col_arr(yerr_up_col)
        yerr_down = col_arr(yerr_down_col)
        xerr_left = col_arr(xerr_left_col)
        xerr_right = col_arr(xerr_right_col)

        # Synthesize constant / percentage error arrays. GLE semantics
        # (graph2.cpp setupdown/getErrorBarData): a literal value is a constant
        # per-point error; 'N%' is N/100 * abs(value along the error dimension)
        # -- for vertical err the value dimension is y, for horizontal it is x.
        if err_consts:
            self._note(
                ImportCategory.DATA,
                "constant error expression converted to a data column on save",
                span,
            )
            # A percentage is of the value GLE draws: an offset's y is shifted.
            y_arr = loaded["y"] + offset
            x_arr = loaded["x"]

            def const_arr(value, is_percent, horizontal):
                base = x_arr if horizontal else y_arr
                if is_percent:
                    return (value / 100.0) * np.abs(base)
                return np.full(len(base), float(value))

            if "err" in err_consts:
                v, p = err_consts["err"]
                yerr_up = const_arr(v, p, False)
                yerr_down = yerr_up
            else:
                if "errup" in err_consts:
                    v, p = err_consts["errup"]
                    yerr_up = const_arr(v, p, False)
                if "errdown" in err_consts:
                    v, p = err_consts["errdown"]
                    yerr_down = const_arr(v, p, False)
            if "herr" in err_consts:
                v, p = err_consts["herr"]
                xerr_left = const_arr(v, p, True)
                xerr_right = xerr_left
            else:
                if "herrleft" in err_consts:
                    v, p = err_consts["herrleft"]
                    xerr_left = const_arr(v, p, True)
                if "herrright" in err_consts:
                    v, p = err_consts["herrright"]
                    xerr_right = const_arr(v, p, True)

        entry = ErrorbarSeries(
            type="errorbar",
            x=loaded["x"],
            y=loaded["y"],
            yerr_up=yerr_up,
            yerr_down=yerr_down,
            xerr_left=xerr_left,
            xerr_right=xerr_right,
            marker=marker,
            markersize=markersize,
            linestyle=linestyle,
            **_dn_width(attrs),
            capsize=stored_capsize,
            gle_capsize=gle_capsize,
            **_dn_fields(attrs),
            offset=offset,
            data_file=data_file,
        )
        entry.update(attrs["qualifiers"])
        if not err_consts:
            # Column indices in the SAME order the writer emits them (x, y,
            # then y-error column(s) collapsed to one when symmetric i.e.
            # yerr_up_col == yerr_down_col, then x-error likewise) -- see
            # gleplot.writer.GLEWriter.add_errorbar_series. Constant/percentage
            # errors (err_consts) have no backing file column at all (the
            # array was synthesized above), so column_names is left absent
            # and regenerated from stable defaults on next save, same as any
            # pre-Track-E3 project.
            cols = [xcol, ycol]
            seen_err_cols = []
            for c in (yerr_up_col, yerr_down_col, xerr_left_col, xerr_right_col):
                if c is not None and c not in seen_err_cols:
                    seen_err_cols.append(c)
            cols.extend(seen_err_cols)
            column_names = self._recovered_column_names(data_file, cols)
            if column_names is not None:
                entry["column_names"] = column_names
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        self._note_dropped_line_mode(attrs, span)
        info["errorbars"].append(entry)
        self._note_error_names(info, err, entry)

    def _passthrough_original_dn(self, info, orig_toks, raw_stmts=None):
        """Keep a dataset display line as raw GLE in axes passthrough.

        Used when a ``dN ... err <literal>`` cannot be converted (broken /
        unresolved data): rather than silently dropping the error bars we
        re-emit the original line verbatim so GLE still draws it.
        """
        info["passthrough"].extend(self._dn_passthrough_lines(orig_toks, raw_stmts))

    def _dn_passthrough_lines(self, orig_toks, raw_stmts=None) -> List[str]:
        """Verbatim source line(s) for a ``dN ...`` statement kept as passthrough.

        Prefers the statement's own raw source text over rejoining tokens
        with inserted spaces: a rejoin turns ``err 10%`` (NUMBER '10' + WORD
        '%', directly adjacent in the source -- see lexer.py's
        ``_NUMBER_MERGE_STOPPERS``) into ``err 10 %``, which GLE rejects as
        an unrecognised sub-command. ``raw_stmts`` may hold more than one
        line when a dataset's attributes were merged from several physical
        ``dN ...`` statements; each is re-emitted on its own line, matching
        the original source structure. Falls back to a token rejoin only
        when no raw text is available (defensive; every real ``dN`` line
        should have one).
        """
        if raw_stmts:
            return list(raw_stmts)
        if not orig_toks:
            return []
        rendered = " ".join(self._token_text(t) for t in orig_toks)
        return ["    " + rendered]

    def _build_file_series(
        self, info, d_name, data_file, xcol, ycol, attrs, has_line, error=None
    ):
        markersize = _dn_markersize(attrs)
        # A 'd1 line marker circle lwidth X' reference is a line (carrying
        # line/lwidth/linestyle) that ALSO has a marker -- not an errorbar.
        # Classifying it as an errorbar would drop the whole styled line, so
        # the marker is kept as an additional field. A dataset without a line
        # that still sets ``lwidth`` is the writer's line reference with
        # ``linestyle='none'``: an errorbar reference never writes a width.
        if has_line or attrs["lwidth"] is not None:
            entry = FileSeries(
                series_type="line",
                data_file=data_file,
                x_col=xcol,
                y_col=ycol,
                linestyle=attrs["linestyle"] if has_line else "none",
                **_dn_width(attrs),
                nomiss=attrs["nomiss"],
                **_dn_fields(attrs),
            )
            if attrs["line_mode"]:
                entry["line_mode"] = attrs["line_mode"]
            if attrs["marker"] is not None:
                entry["marker"] = attrs["marker"]
                entry["markersize"] = markersize
        else:
            # Marker-only (or bare) reference -> errorbar-style entry (which the
            # writer emits as a marker-only dataset).
            entry = FileSeries(
                series_type="errorbar",
                data_file=data_file,
                x_col=xcol,
                y_col=ycol,
                yerr_col=None,
                marker=attrs["marker"],
                markersize=markersize,
                capsize=None,
                **_dn_fields(attrs),
            )
        entry.update(attrs["qualifiers"])
        entry.update(self._data_read_options.get(d_name, {}))
        if error is not None:
            entry["data_error"] = error
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        info["file_series"].append(entry)

    # -- data loading ----------------------------------------------------

    # -- contour / heatmap recognition ----------------------------------

    def _scan_gleplot_sub_lines(self) -> set:
        """1-based line numbers spanned by ``sub gleplot_<name>`` definitions.

        gleplot emits self-contained palette subs (see
        :mod:`gleplot.palettes`). Their bodies use ``sub``/``if``/``return``
        etc.; they are dropped wherever they appear (like the metadata block) and
        regenerated canonically from the model on re-save, so they never leak
        into passthrough nor trip the programmatic-construct guard.
        """
        nums: set = set()
        in_sub = False
        sub_name = ""
        for idx, line in enumerate(self.text.splitlines(), start=1):
            low = line.strip().lower()
            if not in_sub:
                if low.startswith("sub gleplot_") and (low.split()[1] in _LEGACY_SUBS):
                    self._note(
                        ImportCategory.STRUCTURE,
                        f"'{low.split()[1]}' is a sub an earlier gleplot "
                        "wrote, which gleplot no longer reads; it and the "
                        "calls that use it were kept as raw GLE",
                        (idx, idx),
                    )
                elif low.startswith("sub gleplot_"):
                    in_sub = True
                    sub_name = low.split()[1]
                    nums.add(idx)
                    if sub_name.startswith("gleplot_contourf"):
                        self._contourf_sub_spans[sub_name] = {idx}
                elif _GLEPLOT_DEFINE_MARKER_RE.match(low):
                    # The ``define marker`` naming a per-point-size sub
                    # (writer.mdata_sub_text) is part of that sub.
                    nums.add(idx)
                continue
            nums.add(idx)
            if sub_name.startswith("gleplot_contourf"):
                self._contourf_sub_spans[sub_name].add(idx)
                if low.startswith(CONTOURF_MARKER + " "):
                    self._contourf_subs[sub_name] = line.strip()
                rescale = _CONTOURF_RESCALE_RE.match(low)
                if rescale:
                    try:
                        self._contourf_rescales[sub_name] = (
                            float(rescale.group(1)),
                            float(rescale.group(2)),
                        )
                    except ValueError:
                        pass
            if low == "end sub" or low.startswith("end sub "):
                in_sub = False
        return nums

    def _prescan_contour_heatmap(self, nodes) -> None:
        """Parse fitz/contour blocks and decide which are gleplot-authored.

        Builds ``self._fitz_blocks`` (keyed by the ``.z`` file the block
        generates) and ``self._contour_blocks`` (keyed by the ``.z`` file the
        block reads), then cross-references them against the ``colormap`` /
        ``data "*-cdata.dat"`` references inside the graph blocks. A block is
        recorded as *consumed* (its lines dropped from passthrough, its geometry
        reconstructed onto the model) only when it is actually referenced -- a
        foreign or unreferenced ``begin fitz``/``begin contour`` stays opaque
        passthrough with no loss.
        """
        raw_fitz: Dict[str, Tuple[dict, OpaqueBlock]] = {}
        raw_contour: Dict[str, Tuple[dict, OpaqueBlock]] = {}
        for node in nodes:
            if not isinstance(node, OpaqueBlock):
                continue
            if node.block_type == "fitz":
                info = self._parse_fitz_block(node)
                if info is not None:
                    raw_fitz[info["zfile"]] = (info, node)
            elif node.block_type == "contour":
                info = self._parse_contour_block(node)
                if info is not None:
                    raw_contour[info["zfile"]] = (info, node)

        colormap_files, cdata_bases = self._referenced_grid_files(nodes)

        # A contour block is ours iff its cdata polyline is drawn in a graph AND
        # its data source can actually be reconstructed (scattered points via a
        # feeding fitz block, or the grid ``.z`` on disk). If the data can't be
        # read the reconstruction would bail to passthrough, so we must NOT drop
        # the block here -- keep it opaque and lose nothing.
        for zfile, (info, node) in raw_contour.items():
            base = zfile[:-2] if zfile.endswith(".z") else zfile
            if base not in cdata_bases:
                continue
            fitz_pair = raw_fitz.get(zfile)
            if fitz_pair is not None:
                if self._read_points(fitz_pair[0]["points_file"]) is None:
                    continue
            elif self._read_z_grid(zfile) is None:
                continue
            self._contour_blocks[zfile] = info
            self._mark_block_consumed(node)
            self._note_dropped_block_lines(info["dropped"], "contour", zfile)

        # A fitz block is ours iff its generated .z feeds a recognized colormap
        # or a recognized contour block, AND its scattered points are readable.
        for zfile, (info, node) in raw_fitz.items():
            if zfile not in colormap_files and zfile not in self._contour_blocks:
                continue
            if self._read_points(info["points_file"]) is None:
                continue
            self._fitz_blocks[zfile] = info
            self._mark_block_consumed(node)
            dropped = list(info["dropped"])
            if zfile not in self._contour_blocks and info["ncontour_line"]:
                # A colormap's grid: the writer writes no ncontour for it.
                dropped.append(info["ncontour_line"])
            self._note_dropped_block_lines(dropped, "fitz", zfile)

    def _note_dropped_block_lines(self, lines, kind: str, zfile: str) -> None:
        """Note each line of a recovered ``begin <kind>`` block not written back."""
        for sl in sorted(lines, key=lambda sl: sl.line_no):
            self._note(
                ImportCategory.DATA,
                f"{sl.text.strip()!r} in the begin {kind} block for "
                f"{zfile!r} is not modelled and is not written back on "
                "save; add it to the saved file by hand if you need it",
                (sl.line_no, sl.line_no),
            )

    def _mark_block_consumed(self, node: OpaqueBlock) -> None:
        if node.begin.source_line is not None:
            self._consumed_block_lines.add(node.begin.line_no)

    def _referenced_grid_files(self, nodes) -> Tuple[set, set]:
        """Scan graph blocks for ``colormap`` files and ``-cdata.dat`` bases.

        Only colormaps that are *structurally recognizable* as gleplot heatmaps
        (known/built-in palette, ``.z``/``.gz`` file, no unrecognized options)
        contribute their grid file. A foreign colormap (unknown palette,
        function expression, extra options) is re-emitted verbatim as
        passthrough and must NOT cause the ``begin fitz`` block that generates
        its ``.z`` to be dropped -- otherwise the preserved colormap line would
        reference a grid nothing produces (content loss + broken output).
        """
        colormap_files: set = set()
        cdata_bases: set = set()
        for node in nodes:
            if not isinstance(node, GraphBlock):
                continue
            for child in node.body:
                if not isinstance(child, Statement):
                    continue
                kw = child.keyword
                toks = _words_and_values(child)
                if kw == "colormap":
                    self._keep_contourf_sub_unless_readable(toks)
                    zfile = self._colormap_recognizable_zfile(toks)
                    if zfile is not None:
                        colormap_files.add(zfile)
                elif kw == "data" and len(toks) >= 2:
                    fname, _ = self._read_filename(toks, 1)
                    if fname.endswith("-cdata.dat"):
                        cdata_bases.add(fname[: -len("-cdata.dat")])
        return colormap_files, cdata_bases

    def _colormap_recognizable_zfile(self, toks) -> Optional[str]:
        """Return the grid ``.z`` file iff this ``colormap`` is reconstructable.

        Mirrors the accept criteria of :meth:`_parse_colormap` (palette known
        or ``color``/grayscale, a ``.z``/``.gz`` file rather than a function
        expression, no unrecognized options, and ``zmin``/``zmax``/
        ``interpolate`` values written back as they read) but WITHOUT touching disk --
        data readability is handled separately. Returns ``None`` for any
        colormap that :meth:`_parse_colormap` would send to passthrough, so the
        prescan never drops the fitz block feeding a foreign colormap.
        """
        if len(toks) < 4:
            return None
        zfile, idx = self._read_filename(toks, 1)
        px = _num(toks[idx]) if idx < len(toks) else None
        py = _num(toks[idx + 1]) if idx + 1 < len(toks) else None
        if px is None or py is None:
            return None
        i = idx + 2
        m = len(toks)
        color = False
        palette = None
        unknown = False
        while i < m:
            w = toks[i].value.lower()
            if w == "color":
                color = True
                i += 1
            elif w == "invert":
                i += 1
            elif w in ("zmin", "zmax") and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                unknown = unknown or not _is_number_literal(toks[i + 1 : nxt])
                i = nxt if v is not None else i + 2
            elif w == "palette" and i + 1 < m:
                palette = toks[i + 1].value
                i += 2
            elif w == "interpolate" and i + 1 < m:
                mode = toks[i + 1].value.lower()
                unknown = unknown or mode not in ("bicubic", "nearest")
                i += 2
            else:
                unknown = True
                i += 1
        if unknown:
            return None
        if not color and palette is not None:
            if PALETTE_SUB_TO_CMAP.get(palette.lower()) is None:
                return None
        if not zfile.lower().endswith((".z", ".gz")):
            return None
        return zfile

    def _parse_fitz_block(self, node: OpaqueBlock) -> Optional[dict]:
        """Parse a ``begin fitz`` block matching gleplot's shape, or ``None``.

        Recovers ``points_file``, ``extent`` (x0,x1,y0,y1), ``gridsize``
        (nx,ny from the ``from..to..step`` ranges) and optional ``ncontour``,
        as a contour reads the grid; ``ranges`` keeps the ranges and
        ``marker`` the node-grid comment line a heatmap's block holds, from
        which :meth:`_fitz_heatmap_grid` reads a colormap's grid instead.
        ``zfile`` is the generated grid name (points base + ``.z``).
        ``dropped`` lists the other non-blank lines, which are not rewritten,
        and ``ncontour_line`` the ``ncontour`` line, which only a contour
        writes back. A ``data``, ``x``, ``y`` or ``ncontour`` line it cannot
        read whole, or a repeated one (a marker line too), keeps the block as
        written.
        """
        data_file = None
        xr = yr = None
        ncontour = None
        ncontour_line = None
        marker = None
        dropped: List[SourceLine] = []
        seen: Set[str] = set()
        for sl in node.inner_lines:
            if sl.text.strip().startswith(NODES_MARKER + " "):
                if marker is not None:
                    return None
                marker = sl
                continue
            toks = _words_and_values(_first_statement_of(sl))
            if not toks:
                if sl.text.strip():
                    dropped.append(sl)
                continue
            kw = toks[0].value.lower()
            if kw not in ("data", "x", "y", "ncontour"):
                dropped.append(sl)
                continue
            if kw in seen or len(toks) < 2:
                return None
            seen.add(kw)
            if kw == "data":
                data_file, _ = self._read_filename(toks, 1)
            elif kw in ("x", "y"):
                rng = self._parse_from_to_step(toks)
                if rng is None:
                    return None
                if kw == "x":
                    xr = rng
                else:
                    yr = rng
            else:
                n = _num(toks[1])
                if len(toks) != 2 or n is None or n != int(n):
                    return None
                ncontour = int(n)
                ncontour_line = sl
        if data_file is None or xr is None or yr is None:
            return None
        x0, x1, xstep = xr
        y0, y1, ystep = yr
        nx = int(round((x1 - x0) / xstep)) + 1 if xstep else 2
        ny = int(round((y1 - y0) / ystep)) + 1 if ystep else 2
        zfile = (
            data_file[:-4] + ".z" if data_file.endswith(".dat") else data_file + ".z"
        )
        return {
            "points_file": data_file,
            "zfile": zfile,
            "extent": [x0, x1, y0, y1],
            "gridsize": [nx, ny],
            "ncontour": ncontour,
            "ranges": (xr, yr),
            "marker": marker,
            "dropped": dropped,
            "ncontour_line": ncontour_line,
        }

    def _fitz_heatmap_grid(self, fitz: dict) -> Tuple[List[float], List[int]]:
        """A ``colormap``'s ``(extent, gridsize)`` over a fitz block's grid.

        A block :meth:`GLEWriter.add_fitz_block` wrote for a heatmap gives
        the extent on its marker line and has GLE's node count,
        ``floor((to - from) / step + 1)``. Any other block, such as a
        hand-written one or one an earlier gleplot wrote, has its last node
        where ``colormap`` draws it, one spacing short of ``to``, so
        re-saving draws it where it was.
        """
        (x0, x1, xs), (y0, y1, ys) = fitz["ranges"]
        if min(xs, ys) <= 0 or x1 <= x0 or y1 <= y0:
            return list(fitz["extent"]), list(fitz["gridsize"])
        counts = [math.floor((x1 - x0) / xs + 1), math.floor((y1 - y0) / ys + 1)]
        sl = fitz["marker"]
        if sl is not None:
            edges = self._marker_edges(sl.text.strip())
            if (
                edges is not None
                and min(counts) >= 2
                and edges[0] == x0
                and edges[2] == y0
                and abs(x0 + (counts[0] - 1) * xs - edges[1]) <= 0.01 * xs
                and abs(y0 + (counts[1] - 1) * ys - edges[3]) <= 0.01 * ys
            ):
                return edges, counts
            self._note(
                ImportCategory.DATA,
                f"the begin fitz block for {fitz['zfile']!r} has a node-grid "
                "marker line that does not match its ranges; read where GLE "
                "draws its nodes, and the marker line is rewritten on re-save",
                (sl.line_no, sl.line_no),
            )
        if min(counts) < 2:
            return list(fitz["extent"]), list(fitz["gridsize"])
        extent = [x0, x1 - (x1 - x0) / counts[0], y0, y1 - (y1 - y0) / counts[1]]
        return extent, counts

    def _parse_contour_block(self, node: OpaqueBlock) -> Optional[dict]:
        """Parse a ``begin contour`` block matching gleplot's shape, or ``None``.

        Recovers the ``.z`` file it reads and the explicit ``values`` list
        (``None`` when a bare block using GLE's default 10 levels), and lists
        under ``dropped`` the other non-blank lines, which are not rewritten.
        A ``data`` or ``values`` line it cannot read whole (``values from a
        to b step s`` among them), or a repeated one, keeps the block as
        written.
        """
        zfile = None
        levels: Optional[List[float]] = None
        dropped: List[SourceLine] = []
        seen: Set[str] = set()
        for sl in node.inner_lines:
            toks = _words_and_values(_first_statement_of(sl))
            if not toks:
                if sl.text.strip():
                    dropped.append(sl)
                continue
            kw = toks[0].value.lower()
            if kw not in ("data", "values"):
                dropped.append(sl)
                continue
            if kw in seen or len(toks) < 2:
                return None
            seen.add(kw)
            if kw == "data":
                zfile, _ = self._read_filename(toks, 1)
                continue
            levels = []
            k = 1
            while k < len(toks):
                v, k = _collect_value(toks, k)
                if v is None:
                    return None
                levels.append(v)
        if zfile is None:
            return None
        return {"zfile": zfile, "levels": levels, "dropped": dropped}

    @staticmethod
    def _parse_from_to_step(toks) -> Optional[Tuple[float, float, float]]:
        """Parse ``<axis> from A to B step C`` -> (A, B, C)."""
        words = {t.value.lower(): idx for idx, t in enumerate(toks)}
        try:
            fi, ti, si = words["from"], words["to"], words["step"]
        except KeyError:
            return None
        a = eval_gle_number(toks[fi + 1 : ti])
        b = eval_gle_number(toks[ti + 1 : si])
        c = eval_gle_number(toks[si + 1 :])
        if a is None or b is None or c is None:
            return None
        return (a, b, c)

    def _parse_colormap(self, toks, info, stmt) -> None:
        """Parse a ``colormap`` statement into a heatmap series (or passthrough)."""
        if len(toks) < 4:
            info["passthrough"].append(self._stmt_text(stmt))
            return
        # GLE reads the operand as a file name when it ends in .z/.gz and as
        # an expression in x and y otherwise; an expression is never quoted,
        # and ends at the first space.
        expression = None
        zfile = ""
        if toks[1].type is not TokenType.STRING:
            operand, idx = _glued_run(toks, 1)
            if not operand.lower().endswith((".z", ".gz")):
                expression = operand
        if expression is None:
            zfile, idx = self._read_filename(toks, 1)
        px = _num(toks[idx]) if idx < len(toks) else None
        py = _num(toks[idx + 1]) if idx + 1 < len(toks) else None
        if px is None or py is None:
            info["passthrough"].append(self._stmt_text(stmt))
            return
        i = idx + 2
        m = len(toks)
        color = invert = False
        vmin = vmax = None
        palette = None
        interpolation = "bicubic"
        unknown = False
        # False when a clause would not be written back as it reads: a
        # zmin/zmax that is not a plain number, or an interpolate mode the
        # model has no value for.
        exact = True
        while i < m:
            w = toks[i].value.lower()
            if w == "color":
                color = True
                i += 1
            elif w == "invert":
                invert = True
                i += 1
            elif w == "zmin" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                vmin = v
                exact = exact and _is_number_literal(toks[i + 1 : nxt])
                i = nxt if v is not None else i + 2
            elif w == "zmax" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                vmax = v
                exact = exact and _is_number_literal(toks[i + 1 : nxt])
                i = nxt if v is not None else i + 2
            elif w == "palette" and i + 1 < m:
                palette = toks[i + 1].value
                i += 2
            elif w == "interpolate" and i + 1 < m:
                interpolation = toks[i + 1].value.lower()
                exact = exact and interpolation in ("bicubic", "nearest")
                i += 2
            else:
                unknown = True
                i += 1

        # cmap resolution.
        cmap: Optional[str]
        if color:
            cmap = "rainbow"
        elif palette is not None and palette.lower() in self._contourf_subs:
            self._parse_contourf_colormap(
                zfile,
                [int(px), int(py)],
                self._contourf_subs[palette.lower()],
                info,
                stmt,
            )
            return
        elif palette is not None:
            cmap = PALETTE_SUB_TO_CMAP.get(palette.lower())
            if cmap is None:
                # Foreign / unknown palette sub -> keep the whole colormap raw.
                info["passthrough"].append(self._stmt_text(stmt))
                self._note(
                    ImportCategory.STRUCTURE,
                    f"colormap uses unknown palette {palette!r}; "
                    "kept as raw GLE, not editable",
                    self._stmt_span(stmt),
                )
                return
        else:
            cmap = "gray"

        if unknown:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "colormap has unrecognized options; kept as raw GLE",
                self._stmt_span(stmt),
            )
            return

        if expression is None and not zfile.lower().endswith((".z", ".gz")):
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "colormap of a quoted name that is not a .z file; kept as raw GLE",
                self._stmt_span(stmt),
            )
            return

        if expression is not None:
            # GLE fills the whole graph with a function colormap, so its
            # extent is the axis range, which must already be read.
            extent = [info["xmin"], info["xmax"], info["ymin"], info["ymax"]]
            reason = None
            if _function_expression_problem(expression) is not None:
                reason = "colormap of an expression gleplot cannot write back"
            elif not exact:
                reason = (
                    "colormap of a function expression with a zmin, zmax or "
                    "interpolate value gleplot cannot write back as it reads"
                )
            elif any(v is None for v in extent) or not (
                extent[0] < extent[1] and extent[2] < extent[3]
            ):
                reason = (
                    "colormap of a function expression with no ascending "
                    "xaxis and yaxis min and max before it"
                )
            if reason is not None:
                info["passthrough"].append(self._stmt_text(stmt))
                self._note(
                    ImportCategory.STRUCTURE,
                    f"{reason}; kept as raw GLE",
                    self._stmt_span(stmt),
                )
                return
            hm = HeatmapSeries(
                type="heatmap",
                source="function",
                expression=expression,
                z=None,
                x=None,
                y=None,
                zpts=None,
                extent=[float(v) for v in extent],
                origin="lower",
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest" if interpolation == "nearest" else "bicubic",
                pixels=[int(px), int(py)],
                invert=invert,
                gridsize=None,
                ncontour=None,
                label=None,
                colorbar=None,
            )
            info["heatmaps"].append(hm)
            return

        if not exact:
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "colormap of a .z file with a zmin, zmax or interpolate value "
                "gleplot cannot write back as it reads; kept as raw GLE",
                self._stmt_span(stmt),
            )
            return

        fitz = self._fitz_blocks.get(zfile)
        if fitz is not None:
            pts = self._read_points(fitz["points_file"])
            if pts is None:
                info["passthrough"].append(self._stmt_text(stmt))
                self._note(
                    ImportCategory.DATA,
                    f"could not read scattered points {fitz['points_file']!r} "
                    "for heatmap; kept colormap as raw GLE",
                    self._stmt_span(stmt),
                )
                return
            extent, gridsize = self._fitz_heatmap_grid(fitz)
            hm = HeatmapSeries(
                type="heatmap",
                source="points",
                z=None,
                x=pts[0],
                y=pts[1],
                zpts=pts[2],
                extent=extent,
                origin="lower",
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest" if interpolation == "nearest" else "bicubic",
                pixels=[int(px), int(py)],
                invert=invert,
                gridsize=gridsize,
                ncontour=None,
                label=None,
                data_file=fitz["points_file"],
                colorbar=None,
            )
        else:
            grid = self._read_z_grid(zfile)
            if grid is None:
                info["passthrough"].append(self._stmt_text(stmt))
                self._note(
                    ImportCategory.DATA,
                    f"could not read grid {zfile!r} for heatmap; "
                    "kept colormap as raw GLE",
                    self._stmt_span(stmt),
                )
                return
            z, extent, marker = grid
            cells = marker is not None and marker.startswith(CELLS_MARKER)
            if cells:
                mesh = self._mesh_from_cells_grid(z, extent, marker, interpolation)
                if mesh is None:
                    self._note(
                        ImportCategory.DATA,
                        f"grid {zfile!r} is marked as a pcolormesh mesh but is "
                        "not one gleplot wrote (it needs interpolate nearest, "
                        "a repeated first row and column, and a header half a "
                        "cell outside the edges the marker gives); read as an "
                        "imshow heatmap where GLE draws its nodes, and the "
                        "marker is dropped on re-save",
                        self._stmt_span(stmt),
                    )
                    cells = False
                else:
                    z, extent = mesh
            if not cells:
                extent = self._imshow_node_extent(zfile, z, extent, marker, stmt)
            hm = HeatmapSeries(
                type="heatmap",
                source="grid",
                z=z,
                x=None,
                y=None,
                zpts=None,
                extent=extent,
                origin="lower",
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest" if interpolation == "nearest" else "bicubic",
                **({"cells": True} if cells else {}),
                pixels=[int(px), int(py)],
                invert=invert,
                gridsize=None,
                ncontour=None,
                label=None,
                data_file=zfile,
                colorbar=None,
            )
        info["heatmaps"].append(hm)

    def _build_contour_from_cdata(
        self, cdata_file, toks, info, line_no=None, raw_stmts=None
    ) -> None:
        """Build a contour series from its ``dN line`` and the fitz/contour blocks."""
        span = (line_no, line_no) if line_no is not None else None
        base = cdata_file[: -len("-cdata.dat")]
        zfile = base + ".z"
        attrs = self._scan_series_attrs(toks[1:])
        dropped = self._contour_line_extras(attrs)
        if dropped:
            # ContourSeries has no such fields; say so rather than lose them.
            self._note(
                ImportCategory.DATA,
                f"{', '.join(repr(word) for word in dropped)} on a contour's "
                "dataset line: not modelled, so not written back on save. Add "
                "it to the saved file by hand if you need it",
                span,
            )
        color = attrs["color"]
        width = (
            _width_fields(linewidth_cm_to_pt(attrs["lwidth"]))
            if attrs["lwidth"] is not None
            else {"linewidth": None}
        )
        lstyle = attrs["lstyle"]  # int or None (None = solid)

        cblock = self._contour_blocks.get(zfile, {})
        levels = cblock.get("levels")

        fitz = self._fitz_blocks.get(zfile)
        if fitz is not None:
            pts = self._read_points(fitz["points_file"])
            if pts is None:
                info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
                self._note(
                    ImportCategory.DATA,
                    f"could not read scattered points {fitz['points_file']!r} "
                    "for contour; kept line as raw GLE",
                    span,
                )
                return
            ct = ContourSeries(
                type="contour",
                source="points",
                z=None,
                x=pts[0],
                y=pts[1],
                zpts=pts[2],
                extent=list(fitz["extent"]),
                levels=levels,
                color=color,
                **width,
                linestyle=lstyle,
                clabel=False,
                clabel_fmt="fix 1",
                gridsize=list(fitz["gridsize"]),
                ncontour=fitz["ncontour"],
                label=None,
                data_file=fitz["points_file"],
            )
        else:
            grid = self._read_z_grid(zfile)
            if grid is None:
                info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
                self._note(
                    ImportCategory.DATA,
                    f"could not read grid {zfile!r} for contour; "
                    "kept line as raw GLE",
                    span,
                )
                return
            z, extent, _cells = grid
            ct = ContourSeries(
                type="contour",
                source="grid",
                z=z,
                x=None,
                y=None,
                zpts=None,
                extent=extent,
                levels=levels,
                color=color,
                **width,
                linestyle=lstyle,
                clabel=False,
                clabel_fmt="fix 1",
                gridsize=None,
                ncontour=None,
                label=None,
                data_file=zfile,
            )
        info["contours"].append(ct)

    @staticmethod
    def _contour_line_extras(attrs) -> List[str]:
        """What a contour's dataset line sets that ``ContourSeries`` cannot hold.

        ``attrs`` is the line's :meth:`_scan_series_attrs`. Only its
        colour, ``lwidth`` and ``lstyle`` are modelled, and the writer
        always draws the ``line``; everything else is named here as GLE
        spells it, so the note can say it was dropped.
        """
        extras = [
            word
            for word, present in (
                ("no line", not attrs["has_line"]),
                ("marker", attrs["marker"] is not None),
                ("msize", attrs["msize"] is not None),
                ("mdata", attrs["mdata"] is not None),
                ("key", attrs["label"] is not None),
                (attrs["smooth_mode"], attrs["smooth_mode"] != "none"),
                ("svg_smooth", attrs["svg_smooth"] is not None),
                ("nomiss", attrs["nomiss"]),
                (str(attrs["line_mode"]), attrs["line_mode"] is not None),
                ("y2axis", attrs["y2axis"]),
                ("x2axis", attrs["x2axis"]),
                ("error bars", bool(attrs["err_refs"] or attrs["err_consts"])),
                ("errwidth", attrs["errwidth"] is not None),
                ("herrwidth", attrs["herrwidth"] is not None),
            )
            if present
        ]
        extras.extend(
            "average" if name == "deresolve_average" else name
            for name in attrs["qualifiers"]
        )
        if attrs["unread"]:
            extras.append(" ".join(attrs["unread"]))
        return extras

    def _read_z_grid(
        self, filename
    ) -> Optional[Tuple[np.ndarray, List[float], Optional[str]]]:
        """Read a ``.z`` grid sidecar -> (z (ny,nx), [x0,x1,y0,y1], cells).

        Returns ``None`` when the file cannot be resolved/parsed. The array is
        returned y-increasing (row 0 = ymin), matching GLE's ``.z`` convention;
        the recovered heatmap/contour therefore always uses ``origin='lower'``
        (a documented, rendering-neutral normalization). ``cells`` is the
        ``pcolormesh`` or ``contourf`` marker line
        (:meth:`GLEWriter.add_cells_sidecar`,
        :meth:`GLEWriter.add_nodes_sidecar`) when the file has one, else
        ``None``; the grid and header are returned as written.
        """
        text = self._read_sidecar_text(filename)
        if text is None:
            return None
        header = None
        cells = None
        values: List[float] = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.startswith("!"):
                if header is None:
                    header = s
                elif s.startswith((CELLS_MARKER + " ", NODES_MARKER + " ")):
                    cells = s
                continue
            for tok in s.replace(",", " ").split():
                try:
                    values.append(float(tok))
                except ValueError:
                    return None
        if header is None:
            return None
        meta = self._parse_z_header(header)
        if meta is None:
            return None
        nx, ny, x0, x1, y0, y1 = meta
        if len(values) != nx * ny:
            return None
        z = np.asarray(values, dtype=float).reshape(ny, nx)
        return z, [x0, x1, y0, y1], cells

    def _contourf_colormap_ok(self, toks) -> bool:
        """Whether a ``colormap`` is one a ``contourf`` heatmap can be read from.

        It must be the statement :meth:`GLEWriter.add_heatmap` writes for
        one (a ``.z`` file, ``zmin``/``zmax`` and its band sub as palette,
        nothing else), the sub's comment line must parse, and the grid must
        be readable. ``zmin 0 zmax 1`` passes values through; any other
        range must be the one the sub maps back from, as with a colorbar.
        Checked before anything is dropped, so that a colormap kept as raw
        GLE keeps its band sub too.
        """
        if len(toks) < 4 or toks[1].type is not TokenType.STRING:
            return False
        zfile, idx = self._read_filename(toks, 1)
        if (
            idx + 8 > len(toks)
            or _num(toks[idx]) is None
            or _num(toks[idx + 1]) is None
            or toks[idx + 2].value.lower() != "zmin"
            or not zfile.lower().endswith((".z", ".gz"))
        ):
            return False
        zmin, at = _collect_value(toks, idx + 3)
        if at + 4 > len(toks) or toks[at].value.lower() != "zmax":
            return False
        zmax, at = _collect_value(toks, at + 1)
        rest = [t.value.lower() for t in toks[at:]]
        if len(rest) != 2 or rest[0] != "palette":
            return False
        if (zmin, zmax) != self._contourf_rescales.get(rest[1], (0.0, 1.0)):
            return False
        comment = self._contourf_subs.get(rest[1])
        return (
            comment is not None
            and self._contourf_fields(comment) is not None
            and self._read_z_grid(zfile) is not None
        )

    def _keep_contourf_sub_unless_readable(self, toks) -> None:
        """Keep a ``contourf`` band sub as raw GLE if its colormap will be.

        A ``colormap`` naming a ``gleplot_contourf<k>`` palette that
        :meth:`_contourf_colormap_ok` rejects is kept as raw GLE (as an
        unknown palette), so the sub it calls must be kept too.
        """
        words = [t.value.lower() for t in toks]
        if "palette" not in words[:-1]:
            return
        name = words[words.index("palette") + 1]
        if name in self._contourf_subs and not self._contourf_colormap_ok(toks):
            del self._contourf_subs[name]
            self._gleplot_sub_lines -= self._contourf_sub_spans.pop(name, set())

    def _parse_contourf_colormap(self, zfile, pixels, comment, info, stmt):
        """Rebuild a ``contourf`` heatmap from its colormap and band sub.

        ``comment`` is the colouring line of the band sub; the colormap was
        checked by :meth:`_contourf_colormap_ok` before the sub was dropped.
        The grid's edges come from the ``.z`` file's marker line.
        """
        fields = self._contourf_fields(comment)
        grid = self._read_z_grid(zfile)
        if fields is None or grid is None:  # checked in the prescan
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "colormap with a gleplot contourf palette that gleplot cannot "
                "read back; kept as raw GLE",
                self._stmt_span(stmt),
            )
            return
        z, header, marker = grid
        ny, nx = z.shape
        extent = self._nodes_extent(marker, header, nx, ny)
        if extent is None:
            x0, x1, y0, y1 = header
            extent = [x0, x1 - (x1 - x0) / nx, y0, y1 - (y1 - y0) / ny]
            self._note(
                ImportCategory.DATA,
                f"contourf grid {zfile!r} has no marker line giving its edges; "
                "they were worked out from its header and may be rounded",
                self._stmt_span(stmt),
            )
        info["heatmaps"].append(
            HeatmapSeries(
                type="heatmap",
                source="grid",
                z=z,
                x=None,
                y=None,
                zpts=None,
                extent=extent,
                origin="lower",
                cmap=fields["cmap"],
                vmin=fields.get("vmin"),
                vmax=fields.get("vmax"),
                interpolation="bicubic",
                levels=fields["levels"],
                extend=fields["extend"],
                pixels=pixels,
                invert=False,
                gridsize=None,
                ncontour=None,
                label=None,
                data_file=zfile,
                colorbar=None,
            )
        )

    @staticmethod
    def _contourf_fields(comment: str) -> Optional[Dict[str, Any]]:
        """The colouring a ``contourf`` band sub's comment line records.

        ``cmap <name> extend <side> [vmin V] [vmax V] levels V V ...``, as
        :meth:`GLEWriter.add_contourf_sub` writes it; ``None`` otherwise.
        """
        words = comment[len(CONTOURF_MARKER) :].split()
        if len(words) < 4 or words[0] != "cmap" or words[2] != "extend":
            return None
        try:
            cmap = canonical_cmap(words[1])
        except ValueError:
            return None
        if words[3] not in CONTOURF_EXTENDS or "levels" not in words:
            return None
        fields: Dict[str, Any] = {"cmap": cmap, "extend": words[3]}
        at = words.index("levels")
        options = words[4:at]
        try:
            levels = [float(v) for v in words[at + 1 :]]
            for key, value in zip(options[0::2], options[1::2]):
                if key not in ("vmin", "vmax") or key in fields:
                    return None
                fields[key] = float(value)
        except ValueError:
            return None
        if len(options) % 2 or len(levels) < 2 or np.any(np.diff(levels) <= 0):
            return None
        fields["levels"] = levels
        return fields

    def _imshow_node_extent(self, zfile, z, header, marker, stmt) -> List[float]:
        """An imshow grid's extent: its first and last nodes, as GLE draws it.

        A grid :meth:`GLEWriter.add_nodes_sidecar` wrote gives them on its
        marker line. Any other grid of two or more nodes each way, such as a
        hand-written one or one an earlier gleplot wrote, has its last node
        where ``colormap`` draws it, one spacing short of the header's
        ``xmax``/``ymax``, so re-saving draws it where it was. A grid one node
        wide or tall is read over its header, as the writer writes it.
        """
        ny, nx = z.shape
        nodes = self._nodes_extent(marker, header, nx, ny)
        if nodes is not None:
            return nodes
        if marker is not None and marker.startswith(NODES_MARKER):
            self._note(
                ImportCategory.DATA,
                f"grid {zfile!r} has a node-grid marker line that does not "
                "match its header; read where GLE draws its nodes, and the "
                "marker line is rewritten on re-save",
                self._stmt_span(stmt),
            )
        if min(nx, ny) < 2:
            return list(header)
        x0, x1, y0, y1 = header
        return [x0, x1 - (x1 - x0) / nx, y0, y1 - (y1 - y0) / ny]

    @staticmethod
    def _marker_edges(marker: Optional[str]) -> Optional[List[float]]:
        """The ``xmin xmax ymin ymax`` a node-grid marker line gives, or ``None``."""
        if marker is None or not marker.startswith(NODES_MARKER):
            return None
        words = marker[len(NODES_MARKER) :].split()
        if words[0::2] != ["xmin", "xmax", "ymin", "ymax"] or len(words) != 8:
            return None
        try:
            return [float(v) for v in words[1::2]]
        except ValueError:
            return None

    @staticmethod
    def _nodes_extent(marker, header, nx, ny) -> Optional[List[float]]:
        """The edges a node grid's marker line gives, or ``None``.

        ``None`` without the line, or when the header is not one node
        spacing past them as :meth:`GLEWriter.add_nodes_sidecar` writes it.
        """
        edges = _Recognizer._marker_edges(marker)
        if edges is None or min(nx, ny) < 2:
            return None
        x0, x1, y0, y1 = edges
        want = [x0, x1 + (x1 - x0) / (nx - 1), y0, y1 + (y1 - y0) / (ny - 1)]
        span = max(abs(v) for v in want + [x1 - x0, y1 - y0])
        if not np.allclose(header, want, rtol=0, atol=1e-9 * span):
            return None
        return [x0, x1, y0, y1]

    @staticmethod
    def _mesh_from_cells_grid(z, header, marker, interpolation):
        """Undo :meth:`GLEWriter.add_cells_sidecar`: ``(C, cell edges)``.

        The edges are the ones the ``marker`` line gives. ``None`` when the
        grid is not one that method writes: sampled other than ``nearest``,
        smaller than two by two, without its first row and column repeated,
        or with a ``header`` that is not half a cell outside those edges.
        """
        ny, nx = z.shape
        if interpolation != "nearest" or nx < 2 or ny < 2:
            return None
        if not (np.array_equal(z[0], z[1]) and np.array_equal(z[:, 0], z[:, 1])):
            return None
        words = marker[len(CELLS_MARKER) :].split()
        if words[0::2] != ["xmin", "xmax", "ymin", "ymax"]:
            return None
        try:
            x0, x1, y0, y1 = (float(v) for v in words[1::2])
        except ValueError:
            return None
        hx = (x1 - x0) / (nx - 1) / 2
        hy = (y1 - y0) / (ny - 1) / 2
        want = [x0 - hx, x1 + hx, y0 - hy, y1 + hy]
        span = max(abs(v) for v in want + [x1 - x0, y1 - y0])
        if not np.allclose(header, want, rtol=0, atol=1e-9 * span):
            return None
        return z[1:, 1:], [x0, x1, y0, y1]

    @staticmethod
    def _parse_z_header(header: str):
        """Parse ``! nx N ny N xmin V xmax V ymin V ymax V`` -> tuple or None."""
        parts = header.lstrip("!").replace(",", " ").split()
        kv = {}
        i = 0
        while i + 1 < len(parts):
            key = parts[i].lower()
            try:
                kv[key] = float(parts[i + 1])
            except ValueError:
                return None
            i += 2
        try:
            nx = int(kv["nx"])
            ny = int(kv["ny"])
            x0 = kv["xmin"]
            x1 = kv["xmax"]
            y0 = kv["ymin"]
            y1 = kv["ymax"]
        except (KeyError, ValueError):
            return None
        return nx, ny, x0, x1, y0, y1

    def _read_points(self, filename):
        """Read a scattered ``x y z`` triples sidecar -> (x, y, z) ndarrays."""
        text = self._read_sidecar_text(filename)
        if text is None:
            return None
        xs, ys, zs = [], [], []
        for raw in text.splitlines():
            s = raw.strip()
            if not s or s.startswith("!"):
                continue
            parts = s.split()
            if len(parts) < 3:
                return None
            try:
                xs.append(float(parts[0]))
                ys.append(float(parts[1]))
                zs.append(float(parts[2]))
            except ValueError:
                return None
        if not xs:
            return None
        return (
            np.asarray(xs, dtype=float),
            np.asarray(ys, dtype=float),
            np.asarray(zs, dtype=float),
        )

    def _read_sidecar_text(self, filename) -> Optional[str]:
        """Read a raw sidecar file's text, resolving relative to the .gle path."""
        p = Path(filename)
        if not p.is_absolute():
            p = self.gle_path.parent / p
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    # -- post-graph addition-order legend --------------------------------

    def _consume_external_legend(self, nodes, start, info) -> int:
        """Consume a ``begin key`` that restates this graph's legend.

        Only a block whose entries are exactly the labelled series is
        taken. Anything else stays in the stream and is preserved
        verbatim, the same as any other opaque block.
        """
        if start >= len(nodes) or not isinstance(nodes[start], OpaqueBlock):
            return start
        block = nodes[start]
        if block.block_type != "key":
            return start
        parsed = self._parse_external_key(block, info["_fit_key_labels"])
        if parsed is None:
            return start
        if not self._assign_legend_seq(info, parsed["labels"]):
            return start
        info["external_key"] = parsed
        return start + 1

    def _parse_external_key(
        self, block, fit_labels, anchor_of=_key_anchor
    ) -> Optional[dict]:
        """Modelled options and entry labels of a ``begin key`` block.

        ``fit_labels`` maps the key expression of each model fit in the
        graph to its label (:meth:`_model_fit_attr_toks`).

        Globals (``position``, ``offset``, ``hei``, ``nobox``, ``compact``,
        ``background``) have to come before the entries, which is how
        :meth:`gleplot.writer.GLEWriter.queue_external_legend` writes them.
        A ``separator`` counts as one column break; ``breaks`` holds the
        entry count before each. Swatch tokens after ``text`` are ignored:
        the next save rebuilds them from the series. ``anchor_of`` reads the
        ``absolute`` line: axes fractions by default, figure fractions for
        a ``Figure.legend``.
        """
        options: dict = {}
        labels: List[str] = []
        textcolors: List[Optional[str]] = []
        separators = 0
        breaks: Set[int] = set()
        started = False
        for sl in block.inner_lines:
            raw = sl.text.strip()
            if not raw or raw.startswith("!"):
                continue
            toks = [t for t in tokenize_line(raw) if t.type is not TokenType.COMMENT]
            if not toks:
                continue
            head = toks[0].value.lower() if toks[0].type is TokenType.WORD else None
            if head == "separator" and len(toks) == 1:
                if not labels:
                    return None
                separators += 1
                breaks.add(len(labels))
                started = True
                continue
            if head == "text":
                if len(toks) < 2:
                    return None
                run = _glued_run(toks, 1)[0]
                if run in fit_labels:
                    labels.append(fit_labels[run])
                elif toks[1].type is TokenType.STRING and run == toks[1].value:
                    labels.append(_string_value(toks[1]))
                else:
                    return None
                textcolors.append(_key_entry_textcolor(toks))
                started = True
                continue
            if started:
                return None
            if (
                head == "justify"
                and len(toks) == 2
                and "justify" not in options
                and toks[1].value.lower() in KEY_POSITIONS_SHORT_TO_LONG
            ):
                options["justify"] = toks[1].value.lower()
                continue
            if head == "absolute" and "anchor" not in options:
                options["absolute"] = raw
                anchor = anchor_of(raw)
                if anchor is None:
                    return None
                options["anchor"] = anchor
                continue
            scanned = self._scan_key_options(toks)
            if not scanned:
                return None
            # The writer puts each spacing option on its own line.
            options.setdefault("spacing", {}).update(scanned.pop("spacing", {}))
            options.update(scanned)
        # Either 'position' or the 'justify' + 'absolute' pair the writer
        # emits for an anchored key, never a mix. One text colour for all.
        anchored = "justify" in options and "anchor" in options and "pos" not in options
        positioned = "pos" in options and not (
            "justify" in options or "anchor" in options
        )
        if not labels or not (anchored or positioned):
            return None
        if anchored and options.get("offset") is not None:
            return None
        if len(set(textcolors)) != 1 or textcolors[0] == "":
            return None
        return {
            "pos": options["justify"] if anchored else options["pos"],
            "anchor": options.get("anchor"),
            "labelcolor": textcolors[0],
            "spacing": options.get("spacing", {}),
            "hei": options.get("hei"),
            "nobox": bool(options.get("nobox")),
            "offset": options.get("offset"),
            "compact": bool(options.get("compact")),
            "background": options.get("background"),
            "separators": separators,
            "breaks": breaks,
            "absolute": options.get("absolute"),
            "labels": labels,
        }

    @staticmethod
    def _legend_pool(info) -> List[Series]:
        """The labelled series of a parsed graph a ``begin key`` may list."""
        pool = []
        for group in (
            "spans",
            "fills",
            "reflines",
            "bars",
            "lines",
            "scatters",
            "errorbars",
            "hists",
            "functions",
            "fits",
            "file_series",
            "derived_series",
        ):
            for series in info.get(group, []):
                if series.get("label"):
                    pool.append(series)
        return pool

    @staticmethod
    def _assign_legend_seq(info, labels: List[str]) -> bool:
        """Stamp ``legend_seq`` so the next save rebuilds this entry order.

        Returns False, and changes nothing, when ``labels`` is not exactly
        the labelled series, or names one twice: the entries carry no
        series identity besides the label, so which of two same-label
        series an entry lists is unknown.
        """
        pool = _Recognizer._legend_pool(info)
        by_label = {s["label"]: s for s in pool}
        if not len(labels) == len(set(labels)) == len(by_label) == len(pool):
            return False
        if set(labels) != set(by_label):
            return False
        for i, label in enumerate(labels):
            by_label[label]["legend_seq"] = i
        return True

    # -- post-graph colorbar / contour-label calls ----------------------

    def _consume_post_graph_calls(self, nodes, start, axes_info) -> int:
        """Consume the colorbar and contour-label groups.

        A colorbar is a ``gsave`` .. ``grestore`` group (:meth:`_colorbar_group`)
        whose ``amove`` is ``xg(xgmax)+S yg(ygmin)`` for a vertical bar and
        ``xg(xgmin) yg(ygmin)-S`` for a horizontal one; a contour's labels are
        a ``contour_labels`` call alone in its own ``gsave`` .. ``grestore``,
        on that contour's ``-clabels.dat`` file. Attaches the recovered colorbar
        to this axes' heatmap and sets ``clabel`` on the matching contour.
        Returns the index of the first node not consumed.
        """
        i = start
        n = len(nodes)
        while i < n:
            consumed = self._try_one_post_call(nodes, i, axes_info)
            if consumed is None:
                break
            i = consumed
        return i

    def _try_one_post_call(self, nodes, i, axes_info) -> Optional[int]:
        colorbar = self._colorbar_group(nodes, i)
        if colorbar is not None:
            end, toks, amove_sep, label = colorbar
            self._apply_colorbar_call(toks, amove_sep, label, axes_info)
            return end
        # gsave, contour_labels file F format "..." , grestore.
        stmts = [
            st for st in map(self._as_statement, nodes[i : i + 3]) if st is not None
        ]
        words = [(st.keyword or "").lower() for st in stmts]
        if words != ["gsave", "contour_labels", "grestore"]:
            return None
        toks = _words_and_values(stmts[1])
        args = self._named_args(toks[1:])
        if set(args) != {"file", "format"} or len(toks) != 5:
            return None
        return i + 3 if self._apply_clabel_call(toks, axes_info) else None

    def _colorbar_group(
        self, nodes, i
    ) -> Optional[Tuple[int, List[Token], object, Optional[str]]]:
        """The ``gsave`` .. ``grestore`` group drawing one colorbar, at ``i``.

        ``gsave``, the ``amove`` to the bar (and, for a horizontal one, the
        ``rmove`` down by its thickness), the ``color_range_vertical`` or
        ``color_range_horizontal`` call, the label's lines if it has one,
        ``grestore``: what :meth:`gleplot.writer.GLEWriter.add_colorbar`
        writes. Returns ``(next_index, call tokens, sep, label)`` or ``None``.
        """
        stmts: List[Statement] = []
        j = i
        while j < len(nodes) and len(stmts) < 4:
            st = self._as_statement(nodes[j])
            if st is None:
                break
            stmts.append(st)
            j += 1
            if (st.keyword or "").lower().startswith("color_range_"):
                break
        words = [(st.keyword or "").lower() for st in stmts]
        if len(words) < 3 or words[0] != "gsave":
            return None
        expected = {
            "color_range_vertical": ["amove"],
            "color_range_horizontal": ["amove", "rmove"],
        }.get(words[-1])
        if expected is None or words[1:-1] != expected:
            return None
        toks = _words_and_values(stmts[-1])
        # Only the call the writer writes: every argument, at 200 steps.
        horizontal = words[-1] == "color_range_horizontal"
        length = "width" if horizontal else "height"
        args = self._named_args(toks[1:], expr_arg=length)
        required = self._CALL_ARG_NAMES - {"file", length}
        if not required <= set(args) or args["pixels"] != 200:
            return None
        sep = self._amove_colorbar_sep(_words_and_values(stmts[1]))
        # The label's lines, up to the closing grestore.
        body: List[object] = []
        while j < len(nodes) and len(body) < 5:
            st = self._as_statement(nodes[j])
            if st is not None and (st.keyword or "").lower() == "grestore":
                break
            body.append(nodes[j])
            j += 1
        if j == len(nodes) or self._as_statement(nodes[j]) is None:
            return None
        label = None
        if body:
            label = self._colorbar_label(body, args, sep, horizontal)
            if label is None:
                return None
        return j + 1, toks, sep, label

    def _colorbar_label(self, body, args, sep, horizontal) -> Optional[str]:
        """The label a colorbar group's ``body`` writes, or ``None``.

        ``body`` must be exactly the lines
        :meth:`gleplot.writer.GLEWriter.colorbar_label_lines` writes for the
        bar read from ``args`` and ``sep``.
        """
        last = body[-1]
        if isinstance(last, OpaqueBlock) and last.block_type == "rotate":
            inner = _rotate_or_box_body(last.inner_lines)
            label = (
                inner[0] if inner is not None and inner[1:] == (None, None) else None
            )
        else:
            label = _plain_write_string(self._as_statement(last))
        if not label or sep is None:
            return None
        cb = {
            "label": label,
            "sep": sep,
            "width": _as_float(args.get("height" if horizontal else "width"), 0.5),
            "zmin": _as_float(args.get("zmin"), 0.0),
            "zmax": _as_float(args.get("zmax"), 1.0),
            "format": str(args.get("format")),
        }
        if horizontal:
            cb["orientation"] = "horizontal"
        written = GLEWriter.colorbar_label_lines(cb)
        read = [line.strip() for node in body for line in self._raw_lines(node)]
        return label if read == written else None

    @staticmethod
    def _amove_colorbar_sep(toks) -> Optional[float]:
        """Recover ``S`` from a colorbar's ``amove`` (else None).

        ``xg(xgmax)+S yg(ygmin)`` places a vertical bar and
        ``xg(xgmin) yg(ygmin)-S`` a horizontal one (``+|S|`` when ``S < 0``).
        """
        text = " ".join(t.value for t in toks)
        m = re.search(r"xgmax\s*\)\s*\+\s*([0-9.eE+-]+)", text)
        sign = 1.0
        if m is None:
            m = re.search(r"ygmin\s*\)\s*([+-])\s*([0-9.eE+-]+)", text)
            if m is None:
                return None
            sign = -1.0 if m.group(1) == "+" else 1.0
        try:
            return sign * float(m.group(m.lastindex or 1))
        except ValueError:
            return None

    def _apply_colorbar_call(self, toks, sep, label, axes_info) -> None:
        # A vertical bar's thickness is its ``width`` and its length the
        # ``height`` expression; a horizontal bar's are the other way round.
        horizontal = toks[0].value.lower() == "color_range_horizontal"
        thickness, length = ("height", "width") if horizontal else ("width", "height")
        args = self._named_args(toks[1:], expr_arg=length)
        heatmaps = axes_info.get("heatmaps") or []
        palette = args.get("palette")
        zrange = (_as_float(args.get("zmin"), 0.0), _as_float(args.get("zmax"), 1.0))
        # A bar in a colour-mapped scatter's palette is that scatter's (the
        # last such one drawn, one with the bar's range first) unless the
        # heatmap shares the palette. An inverted heatmap's bar draws the
        # reversed palette (older files: the forward one); in that palette
        # a scatter keeps only a bar with its range. Any other bar is the
        # heatmap's.
        mapped = [
            sc
            for sc in axes_info.get("scatters") or []
            if "cdata" in sc and palette_call_name(sc["cmap"]) == palette
        ]
        in_range = [sc for sc in mapped if (sc["vmin"], sc["vmax"]) == zrange]
        if heatmaps and (
            not mapped
            or palette_call_name(heatmaps[0]["cmap"]) == palette
            or (
                not in_range
                and palette
                == palette_call_name(
                    colorbar_cmap(heatmaps[0]["cmap"], heatmaps[0].get("invert", False))
                )
            )
        ):
            holders = heatmaps[:1]
        else:
            holders = (in_range or mapped)[-1:]
        if not holders:
            self._note(
                ImportCategory.STRUCTURE,
                f"a {toks[0].value} call was dropped: its axes has no heatmap or "
                f"colour-mapped scatter in palette {args.get('palette')!r} to "
                "attach it to",
                None,
            )
            return
        hm = holders[0]
        cb = {
            "label": label,
            "format": args.get("format") or "fix 1",
            "width": _as_float(args.get(thickness), 0.5),
            "sep": sep if sep is not None else 0.3,
            "zmin": _as_float(args.get("zmin"), 0.0),
            "zmax": _as_float(args.get("zmax"), 1.0),
            # Written scaled by COLORBAR_STEP_SCALE (see add_colorbar).
            "zstep": _as_float(args.get("zstep"), 0.0) / float(COLORBAR_STEP_SCALE),
        }
        if horizontal:
            cb["orientation"] = "horizontal"
        hm["colorbar"] = cb

    def _apply_clabel_call(self, toks, axes_info) -> bool:
        """Set ``clabel`` on the contour whose labels file the call reads.

        Returns whether one did; a call on any other file stays raw GLE.
        """
        args = self._named_args(toks[1:])
        fname = args.get("file")
        fmt = args.get("format")
        contours = axes_info.get("contours") or []
        if not isinstance(fname, str) or not fname.endswith("-clabels.dat"):
            return False
        base = fname[: -len("-clabels.dat")]
        for ct in contours:
            df = ct["data_file"]
            ct_base = (
                df[:-4]
                if df.endswith(".dat")
                else (df[:-2] if df.endswith(".z") else df)
            )
            if ct_base == base and not ct.get("clabel"):
                ct["clabel"] = True
                ct["clabel_fmt"] = fmt
                return True
        return False

    #: Recognized colorbar/clabel call argument names (used to delimit the
    #: unmodeled bar-length expression argument).
    _CALL_ARG_NAMES = frozenset(
        {
            "zmin",
            "zmax",
            "zstep",
            "palette",
            "width",
            "height",
            "format",
            "pixels",
            "file",
        }
    )

    def _named_args(self, toks, expr_arg: str = "hi") -> dict:
        """Parse GLE named-argument call tokens ``name value name value ...``.

        String values (quoted) are unwrapped; numeric values are collected with
        the expression-tolerant :func:`_collect_value` (so signed numbers like
        ``-1`` are read whole). ``expr_arg`` names the colorbar's length
        argument (``hi yg(...)-yg(...)`` on a vertical bar, ``wd
        xg(...)-xg(...)`` on a horizontal one): a multi-token expression that
        is not modeled (the bar always spans the graph), skipped up to the
        next recognized arg name.
        """
        args: dict = {}
        i = 0
        m = len(toks)
        while i < m:
            name = toks[i].value.lower()
            i += 1
            if i >= m:
                break
            if name == expr_arg:
                while i < m and toks[i].value.lower() not in self._CALL_ARG_NAMES:
                    i += 1
                continue
            val_tok = toks[i]
            if val_tok.type is TokenType.STRING:
                args[name] = _string_value(val_tok)
                i += 1
                continue
            if name in ("palette", "format", "label", "file"):
                # A word/filename value (single token, or an unquoted
                # hyphenated filename run).
                if name == "file":
                    fname, nxt = self._read_filename(toks, i)
                    args[name] = fname
                    i = nxt
                else:
                    args[name] = val_tok.value
                    i += 1
                continue
            v, nxt = _collect_value(toks, i)
            if v is not None:
                args[name] = v
                i = nxt
            else:
                i += 1
        return args

    def _resolve_table(self, data_file):
        if data_file in self._table_cache:
            return self._table_cache[data_file]
        resolved = resolve_data_reference(self.gle_path, data_file)
        self._table_cache[data_file] = resolved
        return resolved

    def _load_series(self, data_file, xcol, ycol, extra_cols=None, line_no=None):
        """Return {'x','y','c{n}'...} or {'error': msg}.

        ``line_no`` is the caller's originating ``dN``/``bar``/``fill``
        statement, when the caller has one, so a resolution/extraction
        failure can carry a real span instead of ``None``.
        """
        span = (line_no, line_no) if line_no is not None else None
        resolved = self._resolve_table(data_file)
        if resolved.error is not None or resolved.table is None:
            self._note(ImportCategory.DATA, str(resolved.error), span)
            return {"error": resolved.error}
        reason = self._not_loaded_reason(data_file)
        if reason is not None:
            error = f"'{data_file}' {reason}; gleplot does not load it"
            if data_file not in self._noted_unloaded:
                self._noted_unloaded.add(data_file)
                self._note(
                    ImportCategory.DATA,
                    f"{error}, so the series drawn from it are kept as "
                    "written in the file and are not editable as data",
                    span,
                )
            return {"error": error}
        try:
            cols = extract_columns(resolved.table, xcol, ycol, extra_cols or [])
        except ColumnExtractionError as exc:
            self._note(ImportCategory.DATA, str(exc), span)
            return {"error": str(exc)}
        return cols

    def _not_loaded_reason(self, data_file) -> Optional[str]:
        """Why a resolved ``data_file`` is not loaded into arrays, or None."""
        if any(
            self._datasets[name][0] == data_file for name in self._data_read_options
        ):
            # The loader reads the whole file, so arrays loaded from it would
            # hold rows GLE does not draw.
            return "is read with 'ignore', 'comment' or 'numrows'"
        if self._first_column_is_labels(data_file):
            # GLE names the x axis from that column; a sidecar written from
            # loaded arrays would drop it.
            return "has text in its first column, which GLE draws as x labels"
        return None

    def _loads(self, data_file, xcol, ycol) -> bool:
        """Whether :meth:`_load_series` would load these columns, unnoted."""
        resolved = self._resolve_table(data_file)
        if (
            resolved.error is not None
            or resolved.table is None
            or self._not_loaded_reason(data_file)
        ):
            return False
        try:
            extract_columns(resolved.table, xcol, ycol, [])
        except ColumnExtractionError:
            return False
        return True

    def _is_import(self, data_file) -> bool:
        cls = classify_data_file(self.gle_path, data_file, self._import_list)
        return cls == "import"

    def _has_gle_missing(self, data_file, cols_1based) -> bool:
        """Whether a column of an imported sidecar holds a GLE missing value.

        The writer writes a ``gaps`` line's NaN rows as ``*`` and any other
        NaN as ``nan``; both load as NaN, but only the first breaks the line,
        so the token is what tells them apart
        (:attr:`gleplot.dataio.DataTable.gle_missing`).
        """
        resolved = self._resolve_table(data_file)
        if resolved.table is None:
            return False
        flags = resolved.table.gle_missing
        return any(0 < col <= len(flags) and flags[col - 1] for col in cols_1based)

    def _recovered_column_names(self, data_file, cols_1based) -> Optional[List[str]]:
        """Recover a series' ``column_names`` from its sidecar's header row.

        Parameters
        ----------
        data_file : str
            The sidecar file name (an "import" series' data file).
        cols_1based : list of int
            1-based column indices in the SAME order the object model's
            ``column_names`` list expects them (x, then y, then any error/
            extra columns) -- matching how :mod:`gleplot.axes` builds
            ``column_names`` and how :mod:`gleplot.writer` writes the
            header row (one name per array passed to ``add_data_file``, in
            that same order).

        Returns
        -------
        list of str, or None
            ``None`` when the table couldn't be resolved, or has no real
            header row (:attr:`DataTable.has_header` is ``False`` --
            e.g. a hand-written headerless ``.dat``): in that case
            ``column_names`` is left absent on the recovered series and
            ``Axes.from_dict``-style default regeneration (mirrored here at
            series-build time, see ``Series.default_column_names``) fills it
            in on next save, same as any pre-Track-E3 project.

            A column index of ``0`` (GLE's synthesized point-index column,
            no real file column behind it) recovers as ``'x'`` -- matching
            the default a fresh ``ax.plot`` would assign -- since there is
            no header cell to read for a column that doesn't exist in the
            file.

        Invariant (post Finding-1)
        --------------------------
        This copies the sidecar's header text VERBATIM into
        ``column_names`` (no re-sanitization). That is only reached for
        *import* series, and after the Finding-1 conservative
        classification a file is only ever an import when the ``.gle``
        metadata block's ``import-data`` list vouches for it -- i.e. it
        is a sidecar gleplot itself wrote, whose header was already
        sanitized by the writer at export time. So verbatim copy is
        exactly what preserves byte-identity on re-save: even a
        hand-edited (unsanitary) header in a vouched sidecar round-trips
        byte-for-byte, because the recovered ``column_names`` re-emit the
        same header the file already holds. Hand-authored data files with
        no metadata vouch are classified ``reference`` and never reach
        this code, so an unsanitized user header can never be adopted and
        rewritten here.
        """
        resolved = self._resolve_table(data_file)
        if resolved.error is not None or resolved.table is None:
            return None
        table = resolved.table
        if not table.has_header:
            return None
        names = []
        for col in cols_1based:
            if col == 0:
                names.append("x")
                continue
            if col < 1 or col > table.n_cols:
                return None
            names.append(table.column_names[col - 1])
        return names

    # -- amove / text cluster / trailer ---------------------------------

    def _match_amove(self, node) -> Optional[Tuple[float, float]]:
        """If node is a plain ``amove X Y`` statement, return (x, y)."""
        if not isinstance(node, Statement):
            return None
        if node.keyword != "amove":
            return None
        toks = _words_and_values(node)
        # Reject amove xg()/yg() (that's a text-cluster amove).
        joined = " ".join(t.value for t in toks).lower()
        if "xg" in joined or "yg" in joined:
            return None
        nums = [v for v in (_num(t) for t in toks[1:]) if v is not None]
        if len(nums) >= 2:
            return (nums[0], nums[1])
        return None

    def _consume_text_cluster(self, nodes, start) -> Tuple[List[dict], int]:
        """Greedily match the writer's deferred-text pattern after end graph.

        Pattern per text (every ``set`` is optional, in any subset, in order):
            [set hei H]
            [set color C]
            [set just J]
            amove xg(X) yg(Y)      -- or KEY_ANCHOR_X/_Y for axes fractions
            [begin rotate A
               [begin box fill C add P nobox]
               write "T"
               [end box]
             end rotate]
            -- or, with no rotation, the box block or the bare ``write``
            directly under the ``amove``.

        ``J`` is a horizontal word (``left``/``center``/``right``, vertically
        centred) or a two-letter code (``tl`` .. ``br``). ``begin rotate`` /
        ``begin box`` are opaque blocks: the ``write`` lives in the block's
        inner lines, not as a sibling statement. A box or rotation that is
        not this exact shape fails the cluster, so the lines stay passthrough.

        ``set hei``/``set color``/``set just`` are GLE *interpreter-global*
        state: once set, they apply to every subsequent cluster (including
        clusters in later graphs) until changed again -- mirroring GLE's own
        stateful semantics. This lets a single ``set hei`` shared by multiple
        clusters, or a cluster with no ``set just`` at all, still recover the
        correct fontsize/color/ha via the sticky ``self._text_*`` state.

        A non-empty run of clusters is wrapped in ``gsave``/``grestore`` by
        the writer (:meth:`gleplot.writer.GLEWriter.end_graph`), so that page-
        level text state does not leak into the next graph's axes/ticks.
        That wrapper is recognized and swallowed here: if the run starts with
        a ``gsave`` and, after every cluster we can match, is immediately
        followed by a ``grestore``, both are consumed along with the
        clusters and the sticky ``self._text_*`` state is reset back to
        ambient (matching what ``grestore`` just did to the REAL GLE state --
        see the writer's matching reset in ``end_graph``). If no cluster
        matches, or the run isn't closed by a ``grestore``, nothing is
        consumed here at all (not even the ``gsave``) and it falls through to
        ordinary passthrough handling, same as any other content this
        recognizer does not model (e.g. the broken-axis seam decoration).

        Returns (texts, next_index).
        """
        i = start
        n = len(nodes)

        j = self._skip_blanks(nodes, i)
        gsave_stmt = self._as_statement(nodes[j]) if j < n else None
        wrapped = gsave_stmt is not None and gsave_stmt.keyword == "gsave"
        scan_start = j + 1 if wrapped else i

        texts: List[dict] = []
        k = scan_start
        while k < n:
            consumed, text = self._try_one_text(nodes, k)
            if text is None:
                break
            texts.append(text)
            k = consumed

        if wrapped:
            if texts:
                m = self._skip_blanks(nodes, k)
                grestore_stmt = self._as_statement(nodes[m]) if m < n else None
                if grestore_stmt is not None and grestore_stmt.keyword == "grestore":
                    self._text_fontsize = None
                    self._text_color = "BLACK"
                    self._text_just = "left"
                    return texts, m + 1
            # Unclosed or empty: back off entirely, leave 'gsave' untouched.
            return [], i

        return texts, k

    def _try_one_text(self, nodes, i) -> Tuple[int, Optional[dict]]:
        """Try to match one text cluster starting at ``i``.

        On success returns ``(next_index, text_dict)``. On failure returns
        ``(i, None)`` with the ORIGINAL ``i`` unchanged (never an
        intermediate position), so the caller (:meth:`_consume_text_cluster`)
        can safely discard partial progress and hand every skipped node back
        to the ordinary passthrough walk untouched.

        Blank/comment-only lines are tolerated *between* cluster elements
        (a hand-edited file may have a blank line separating annotations for
        readability) via :meth:`_skip_blanks`, but this skip is provisional:
        it only survives if the pattern goes on to match a full cluster.
        Nothing here treats a blank line as a hard stop -- a blank line
        followed by an unrelated statement simply falls through to the
        ``return i, None`` below, restoring the untouched original ``i``.
        """
        start = i
        n = len(nodes)
        x = y = None
        text_str = None

        rug_group = self._rug_group(nodes, i)
        if rug_group is not None:
            end, group = rug_group
            ready = self._ready_rugs.pop(group["dataset"], None)
            if ready is None:
                return start, None
            return end, ready[0]

        # Optional 'set hei H' / 'set color C' / 'set just J', in any order,
        # each independently optional. Every hit updates sticky state
        # immediately so a later cluster with no 'set just' inherits the
        # last-seen value (GLE semantics: 'set' is global interpreter state).
        while True:
            i = self._skip_blanks(nodes, i)
            stmt = self._as_statement(nodes[i]) if i < n else None
            if stmt is None or stmt.keyword != "set":
                break
            toks = _words_and_values(stmt)
            if len(toks) < 3:
                break
            sub = toks[1].value.lower()
            if sub == "hei":
                v = _num(toks[2])
                if v is None:
                    break
                self._text_fontsize = fontsize_cm_to_pt(v)
                i += 1
                continue
            if sub == "color":
                val, _nxt = _collect_color(toks, 2)
                if val is None:
                    break
                self._text_color = val
                i += 1
                continue
            if sub == "just":
                just = toks[2].value.lower()
                if text_just_to_align(just) is not None:
                    self._text_just = just
                i += 1
                continue
            break

        # The polar tick labels, written as the cluster's first statement.
        i = self._skip_blanks(nodes, i)
        stmt = self._as_statement(nodes[i]) if i < n else None
        if (
            stmt is not None
            and i == self._skip_blanks(nodes, start)
            and (stmt.keyword or "").lower() == "gleplot_polar_labels"
            and self._is_polar_labels_call(stmt)
        ):
            self._polar_labels_rmax = None
            return i + 1, _POLAR_LABELS

        # 'amove xg(X) yg(Y)' -- mandatory: this is what makes the run of
        # 'set' statements above a text cluster rather than unrelated
        # passthrough. If absent, nothing was consumed as a text cluster (any
        # 'set' statements walked above are left for the caller/passthrough
        # by returning the ORIGINAL start index).
        i = self._skip_blanks(nodes, i)
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "amove":
            return start, None
        fraction = _axes_fraction_point(stmt.raw, "amove")
        if fraction is not None:
            x, y = fraction
        else:
            x, y = self._parse_xg_yg(_words_and_values(stmt))
        if x is None or y is None:
            return start, None
        i += 1

        # 'write "T"', optionally inside ``begin rotate`` and/or
        # ``begin box fill ... nobox``. A blank line may separate the amove
        # from the draw in a hand-edited file; tolerate it the same way.
        drawn = self._match_text_draw(nodes, i)
        if drawn is None:
            return start, None
        i, text_str, box_color, rotation, box_name = drawn
        # A named box exists only to anchor an annotation arrow, so the
        # arrow must follow; a name without one is not the writer's shape.
        arrow_fields: Dict[str, Any] = {}
        if box_name is not None:
            matched = self._match_annotation_arrow(nodes, i, box_name)
            if matched is None:
                return start, None
            i, arrow_fields = matched

        ha, va = text_just_to_align(self._text_just) or ("left", "center")
        fields = dict(
            x=x,
            y=y,
            text=text_str,
            color=self._text_color,
            fontsize=self._text_fontsize,
            ha=ha,
            va=va,
            box_color=box_color,
        )
        # Absent means unrotated, matching Axes.text (a zero angle is not
        # stored, and the writer does not emit ``begin rotate`` for it).
        if rotation is not None and abs(rotation) >= 1e-10:
            fields["rotation"] = rotation
        if fraction is not None:
            fields["transform"] = "axes"
        fields.update(arrow_fields)
        return i, TextAnnotation(**fields)

    def _rug_group(self, nodes, i) -> Optional[Tuple[int, dict]]:
        """The ``gsave`` .. ``grestore`` group drawing one rug, at ``i``.

        ``set color C lwidth W cap butt`` then ``xrug "dN" L "pos"`` (or
        ``yrug``), exactly as :meth:`gleplot.writer.GLEWriter.add_rug`
        writes it. Returns ``(next_index, fields)`` or ``None``.
        """
        stmts = []
        j = i
        for _ in range(4):
            j = self._skip_blanks(nodes, j)
            stmt = self._as_statement(nodes[j]) if j < len(nodes) else None
            if stmt is None:
                return None
            stmts.append(_words_and_values(stmt))
            j += 1
        opening, style, call, closing = stmts
        words = [[t.value.lower() for t in toks] for toks in stmts]
        if words[0] != ["gsave"] or words[3] != ["grestore"]:
            return None
        if words[1][:2] != ["set", "color"]:
            return None
        color, k = _collect_color(style, 2)
        if color is None or words[1][k : k + 1] != ["lwidth"]:
            return None
        lwidth, k = _collect_value(style, k + 1)
        if lwidth is None or words[1][k:] != ["cap", "butt"]:
            return None
        axis = {"xrug": "x", "yrug": "y"}.get(words[2][0])
        args = self._guide_call_args(call, 1)
        if axis is None or len(args) != 3:
            return None
        dataset, length, position = args
        if (
            not isinstance(dataset, str)
            or not _DATASET_RE.match(dataset)
            or not isinstance(length, (int, float))
            or position not in RUG_EDGES[axis]
        ):
            return None
        fields = {
            "axis": axis,
            "dataset": dataset.lower(),
            "length": -float(length),
            "position": position,
            "color": color,
            "linewidth": linewidth_cm_to_pt(float(lwidth)),
        }
        return j, fields

    def _scan_post_graph_rugs(self, nodes, start) -> Dict[str, dict]:
        """The rug groups after a graph, before the next one, by dataset."""
        found: Dict[str, Optional[dict]] = {}
        for k in range(start, len(nodes)):
            if isinstance(nodes[k], GraphBlock):
                break
            group = self._rug_group(nodes, k)
            if group is not None:
                name = group[1]["dataset"]
                # Two calls on one dataset: neither is the writer's.
                found[name] = None if name in found else group[1]
        return {name: g for name, g in found.items() if g is not None}

    def _claim_rug_datasets(self, pass1: _GraphDatasets) -> None:
        """Turn each rug group after this graph into a ``Rug``, from its data.

        The group's dataset must be the only one its ``data`` statement
        declares, as ``c1,c2``, from a file no other statement reads, with no
        ``dN`` line of its own and every tick finite. Its statement is then
        consumed; the rug and the statement's text wait in ``_ready_rugs``
        for the text cluster to take the group.
        """
        rugs, self._post_graph_rugs = self._post_graph_rugs, {}
        files = [
            d[0] for _n, _t, _l, defs, _o in pass1.data_stmts for d in defs.values()
        ]
        for names, text, line_no, defs, _options in pass1.data_stmts:
            if len(names) != 1 or names[0] not in rugs:
                continue
            if names[0] in pass1.merged_attr_toks or files.count(defs[names[0]][0]) > 1:
                continue
            fields = rugs[names[0]]
            data_file, xcol, ycol = defs[names[0]]
            if (xcol, ycol) != (1, 2):
                continue
            cols = self._load_series(data_file, xcol, ycol, line_no=line_no)
            if "error" in cols:
                continue
            ticks = np.asarray(cols[fields["axis"]], dtype=float)
            if not np.all(np.isfinite(ticks)) or ticks.size == 0:
                continue
            pass1.emitted.add(names[0])
            rug = Rug(
                type="rug",
                axis=fields["axis"],
                ticks=[float(v) for v in ticks],
                length=fields["length"],
                position=fields["position"],
                color=fields["color"],
                linewidth=fields["linewidth"],
                data_file=data_file,
            )
            self._ready_rugs[names[0]] = (rug, text)

    def _is_polar_labels_call(self, stmt) -> bool:
        """Whether ``stmt`` is the label call of the polar axes just parsed.

        It must be ``gleplot_polar_labels rmax step dp deg$`` with the values
        :meth:`gleplot.writer.GLEWriter.add_polar_frame` writes for that
        axes' radial limit and the figure's ``usetex``.
        """
        rmax = self._polar_labels_rmax
        if rmax is None:
            return False
        step = polar_ring_step(rmax)
        expected = [rmax, step, polar_label_decimals(step)]
        args = self._guide_call_args(_words_and_values(stmt), 1)
        return (
            len(args) == 4
            and args[3] == self._polar_degree
            and all(
                isinstance(v, (int, float)) and float(v) == e
                for v, e in zip(args[:3], expected)
            )
        )

    def _match_text_draw(self, nodes, i):
        """The draw half of one text cluster, after its ``amove``.

        Returns ``(next_index, text, box_color, rotation, box_name)`` or
        ``None``. ``rotation`` is ``None`` when there is no ``begin rotate``.
        ``box_color``/``box_name`` are ``None`` when the box has no fill /
        name, or there is no box. Anything that is not the writer's shape
        (an outline, a ``round`` corner, an angle expression) returns
        ``None`` so the caller leaves the nodes for passthrough.
        """
        n = len(nodes)
        i = self._skip_blanks(nodes, i)
        node = nodes[i] if i < n else None
        if isinstance(node, OpaqueBlock) and node.end is not None:
            if node.block_type == "rotate":
                angle = _plain_rotate_angle(node.begin)
                body = _rotate_or_box_body(node.inner_lines)
                if angle is None or body is None:
                    return None
                return (i + 1,) + body[:2] + (angle, body[2])
            if node.block_type == "box":
                boxed = _boxed_write(node)
                if boxed is None:
                    return None
                return (i + 1,) + boxed[:2] + (None, boxed[2])
        stmt = self._as_statement(node) if node is not None else None
        text_str = _plain_write_string(stmt) if stmt is not None else None
        if text_str is None:
            return None
        return i + 1, text_str, None, None, None

    def _match_annotation_arrow(self, nodes, i, box_name: str):
        """The ``Axes.annotate`` arrow after a text drawn in box ``box_name``.

        Pattern (exactly the writer's order, blank lines tolerated)::

            amove xg(X) yg(Y)
            save TIP
            gsave
            set color C
            [set lwidth W]
            [set arrowstyle S]     -- present exactly when SEP has a head
            join BOX SEP TIP
            grestore

        Returns ``(next_index, fields)`` with the arrow fields of
        :class:`~gleplot.series.TextAnnotation`, or ``None``. The ``set``
        lines are inside the ``gsave``, so they never touch the sticky text
        state.
        """
        n = len(nodes)

        def tokens_at(k):
            k = self._skip_blanks(nodes, k)
            stmt = self._as_statement(nodes[k]) if k < n else None
            return k, (_words_and_values(stmt) if stmt is not None else [])

        def words(toks, count):
            return [t.value.lower() for t in toks[:count]]

        i, toks = tokens_at(i)
        if words(toks, 1) != ["amove"]:
            return None
        x, y = self._parse_xg_yg(toks)
        if x is None or y is None:
            return None

        i, toks = tokens_at(i + 1)
        if len(toks) != 2 or words(toks, 1) != ["save"]:
            return None
        if toks[1].type is not TokenType.WORD:
            return None
        tip = toks[1].value

        i, toks = tokens_at(i + 1)
        if len(toks) != 1 or words(toks, 1) != ["gsave"]:
            return None

        i, toks = tokens_at(i + 1)
        if len(toks) < 3 or words(toks, 2) != ["set", "color"]:
            return None
        color, nxt = _collect_color(toks, 2)
        if color is None or nxt != len(toks):
            return None

        linewidth = tip_style = None
        i, toks = tokens_at(i + 1)
        if len(toks) == 3 and words(toks, 2) == ["set", "lwidth"]:
            width = _num(toks[2]) if toks[2].type is TokenType.NUMBER else None
            if width is None:
                return None
            linewidth = linewidth_cm_to_pt(width)
            i, toks = tokens_at(i + 1)
        if len(toks) == 3 and words(toks, 2) == ["set", "arrowstyle"]:
            tip_style = toks[2].value.lower()
            if tip_style not in ARROW_TIP_STYLES:
                return None
            i, toks = tokens_at(i + 1)

        # GLE object names are case-sensitive (``join lab`` does not find
        # ``name Lab``), so they must match exactly.
        if (
            len(toks) < 4
            or words(toks, 1) != ["join"]
            or toks[1].value != box_name
            or toks[-1].value != tip
        ):
            return None
        sep = "".join(t.value for t in toks[2:-1])
        if sep not in ARROW_JOIN_SEPS or (sep == "-") != (tip_style is None):
            return None

        i, toks = tokens_at(i + 1)
        if len(toks) != 1 or words(toks, 1) != ["grestore"]:
            return None

        fields: Dict[str, Any] = {"xy": [x, y], "arrow": sep}
        if tip_style is not None:
            fields["arrowstyle"] = tip_style
        fields["arrow_color"] = color
        if linewidth is not None:
            fields["arrow_linewidth"] = linewidth
        return i + 1, fields

    def _skip_blanks(self, nodes, i) -> int:
        """Advance past any run of ``BlankOrComment`` nodes at ``i``.

        Used by :meth:`_try_one_text` to tolerate a blank line separating
        the elements of a hand-edited text cluster (e.g. between
        ``end graph`` and the first cluster, or between two clusters).
        Never looks past the end of ``nodes``.
        """
        n = len(nodes)
        while i < n and isinstance(nodes[i], BlankOrComment):
            i += 1
        return i

    def _parse_xg_yg(self, toks) -> Tuple[Optional[float], Optional[float]]:
        """Parse ``amove xg(X) yg(Y)`` argument expressions."""
        x = y = None
        i = 0
        m = len(toks)
        while i < m:
            w = toks[i].value.lower()
            if w in ("xg", "yg") and i + 1 < m and toks[i + 1].value == "(":
                # collect tokens until ')'
                j = i + 2
                inner = []
                while j < m and toks[j].value != ")":
                    inner.append(toks[j])
                    j += 1
                val = eval_gle_number(inner)
                if w == "xg":
                    x = val
                else:
                    y = val
                i = j + 1
                continue
            i += 1
        return x, y

    @staticmethod
    def _more_graphs_after(nodes, i) -> bool:
        return any(isinstance(node, GraphBlock) for node in nodes[i + 1 :])

    # -- axes assembly ---------------------------------------------------

    def _assemble_axes(self, fig, parsed_axes, sharex, sharey):
        positions = self._infer_positions(parsed_axes)

        for idx, info in enumerate(parsed_axes):
            ax = Axes(fig, positions[idx])
            self._populate_axes(ax, info)
            fig._apply_shared_axes_flags(ax)
            # Restore explicit visibility flags recovered from GLE (override
            # the derived ones where the GLE said something different).
            self._restore_visibility_flags(ax, info)
            fig.axes_list.append(ax)

        self._apply_geometry(fig, parsed_axes)
        for info, ax in zip(parsed_axes, fig.axes_list):
            if info["polar_rmax"] is not None:
                self._apply_polar(fig, ax, info)

        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

    def _apply_polar(self, fig, ax, info) -> None:
        """Make ``ax`` the polar axes its grid draw declared.

        The model keeps the radial limit only; the writer derives the
        window from it and the frame. A window other than that one is
        noted, since the next save writes the derived one. A graph whose
        placement was not recovered is laid out again on save, so its
        window is not checked.
        """
        rmax = info["polar_rmax"]
        ax._polar = True
        ax.xmin = ax.xmax = None
        ax.ymin, ax.ymax = 0.0, rmax
        if ax.placement is not None:
            frame: Optional[Tuple[float, float]] = (ax.placement[2], ax.placement[3])
        elif ax.geometry_passthrough:
            frame = None
        else:
            return
        xr, yr = polar_window(rmax, frame, fontsize_pt_to_cm(fig.style.fontsize))
        num = GLEWriter._format_number
        found = [info["xmin"], info["xmax"], info["ymin"], info["ymax"]]
        if [num(v) if v is not None else None for v in found] != [
            num(-xr),
            num(xr),
            num(-yr),
            num(yr),
        ] or (info["xnegate"] or info["ynegate"]):
            self._note(
                ImportCategory.STRUCTURE,
                "the polar axes' x and y ranges are not the ones gleplot "
                "writes for its radial limit and size; they are written "
                "again on save",
                None,
            )

    # -- graph geometry --------------------------------------------------

    def _apply_geometry(self, fig, parsed_axes) -> None:
        """Map each graph block's recovered geometry onto the axes model.

        Three outcomes per axes, in order of preference (SPEC 3.3 / 8.1.3):

        * **modelled** -- the invertible triple ``amove x y`` + ``size w h`` +
          ``scale 1 1`` becomes :attr:`Axes.placement`, a frame rect in page
          cm that the writer re-emits as the same three statements;
        * **auto** -- no geometry at all, or exactly ``scale auto`` (the
          writer's own default emission): nothing is stored, placement stays
          ``None``, meaning GLE decides;
        * **preserved** -- any other geometry (``fullsize``, ``scale h v``
          with real factors, a bare ``size`` with no ``scale 1 1``, several
          statements in an order we do not model) is kept verbatim in
          :attr:`Axes.geometry_passthrough` and re-emitted in the geometry
          slot, with a ``layout:`` warning saying it is not editable.

        Multi-graph figures take the same three outcomes per graph block. Their
        ``amove`` positions still become grid positions
        (:meth:`_infer_positions`), but the rect they form with the block's
        ``size w h`` + ``scale 1 1`` is ALSO captured as
        :attr:`Axes.placement` rather than left to the grid path to re-derive.
        That is what makes a ``subplots_adjust`` layout survive save -> parse
        -> save: the writer honours the recovered rects verbatim instead of
        recomputing default spacing (this retired documented normalization #3).
        """
        single = len(parsed_axes) == 1
        for info, ax in zip(parsed_axes, fig.axes_list):
            stmts = info.get("geometry_stmts") or []
            self._apply_axes_geometry(fig, ax, info, stmts, preserve_amove=single)

    def _apply_axes_geometry(self, fig, ax, info, stmts, preserve_amove: bool) -> None:
        """Classify one graph block's geometry (see :meth:`_apply_geometry`).

        ``preserve_amove`` controls what happens to an ``amove`` that did not
        become part of a placement rect. With a single graph there is no grid
        to hold the position, so it is kept verbatim in the figure's header
        passthrough (SPEC 8.1.4: no silent geometry loss). With several graphs
        the ``amove`` positions ARE modelled -- they are what
        :meth:`_infer_positions` reads the grid off -- so re-emitting them
        would duplicate every subplot's position line.
        """
        amove = info.get("amove")
        triple = self._invertible_triple(stmts)
        if triple is not None and amove is not None:
            ax.placement = (amove[0], amove[1], triple[0], triple[1])
            return

        if self._is_auto_geometry(stmts):
            # Legacy (metadata v1) geometry, or a hand-written 'scale auto':
            # placement stays None and the next save adopts the computed
            # explicit rect. See the metadata module's migration policy.
            pass
        elif triple is not None:
            # 'size w h' + 'scale 1 1' with no amove in front. The pair pins
            # the box but not its position, so it inverts to no rect; the grid
            # path (or the single-plot default) supplies the position and
            # re-emits an equivalent block.
            pass
        elif self._is_writer_derived_size(fig, ax, stmts):
            # A metadata-v1 single-plot colorbar emission (a bare 'size'
            # reserving room for the bar to the right of the graph). It was
            # derived from the colorbar, so capturing it would only duplicate
            # model state; on re-save the reservation becomes the layout's
            # right-hand margin instead.
            pass
        else:
            ax.geometry_passthrough = [s.raw for s in stmts]
            geom_lines = [s.line_no for s in stmts if s.line_no is not None]
            self._note(
                ImportCategory.LAYOUT,
                "graph geometry ("
                + ", ".join(sorted({s.keyword for s in stmts}))
                + ") is preserved as raw GLE, not editable",
                (min(geom_lines), max(geom_lines)) if geom_lines else None,
            )

        # An 'amove' that did not become a placement rect still positions the
        # graph. Preserve it verbatim ahead of the block rather than dropping
        # it (SPEC 8.1.4: no silent geometry loss).
        raw_amove = info.get("amove_raw")
        if preserve_amove and amove is not None and raw_amove is not None:
            fig.passthrough_header.append(raw_amove)
            amove_line = info.get("amove_line_no")
            self._note(
                ImportCategory.LAYOUT,
                "graph position (amove) is preserved as raw GLE, not editable",
                (amove_line, amove_line) if amove_line is not None else None,
            )

    @staticmethod
    def _invertible_triple(stmts) -> Optional[Tuple[float, float]]:
        """``(w, h)`` iff ``stmts`` are exactly ``size w h`` + ``scale 1 1``.

        That pair -- with an ``amove`` in front of the block -- is the only
        graph geometry that inverts to a frame rectangle (SPEC 3.3), because
        ``scale 1 1`` makes the axis frame fill the graph box exactly.
        """
        if len(stmts) != 2:
            return None
        size_st, scale_st = stmts
        if size_st.keyword != "size" or len(size_st.values) != 2:
            return None
        if scale_st.keyword != "scale" or scale_st.values != [1.0, 1.0]:
            return None
        return (size_st.values[0], size_st.values[1])

    @staticmethod
    def _is_auto_geometry(stmts) -> bool:
        """True for "GLE decides": no geometry, or exactly ``scale auto``."""
        if not stmts:
            return True
        return (
            len(stmts) == 1
            and stmts[0].keyword == "scale"
            and stmts[0].words == ["auto"]
        )

    @staticmethod
    def _is_writer_derived_size(fig, ax, stmts) -> bool:
        """True iff ``stmts`` are the legacy (metadata v1) colorbar ``size`` line.

        gleplot v1 output pinned a single-plot graph BOX -- a bare ``size W H``
        with no ``scale`` and no ``amove`` -- when the axes had a colorbar, so
        the bar and its labels were not clipped off the right of the page. That
        line is a pure function of the recovered colorbar
        (``Figure._axes_colorbar_reserved_cm``), so it carries no information
        the model does not already hold: recognizing it here lets such a file
        load as auto placement and re-save as a v2 rect whose right-hand margin
        reserves the same width. Compared as emitted text, so a hand-written
        bare ``size`` that does NOT match is captured verbatim instead of being
        silently replaced.

        Kept for backward compatibility only; the current writer never emits
        this form.
        """
        if len(stmts) != 1 or stmts[0].keyword != "size":
            return False
        reserved, _below = fig._axes_colorbar_reserved_cm(ax)
        if reserved <= 0:
            return False
        width_cm = inches_to_cm(fig.figsize[0])
        height_cm = inches_to_cm(fig.figsize[1])
        graph_w = max(width_cm - reserved, width_cm * 0.3)
        expected = (
            f"    size {GLEWriter._format_number(graph_w)} "
            f"{GLEWriter._format_number(height_cm)}"
        )
        return stmts[0].raw == expected

    def _infer_positions(self, parsed_axes) -> List[Optional[tuple]]:
        """Infer (rows, cols, idx) per axes; ``None`` for an inset.

        The insets (:meth:`Figure.add_axes`) are the graphs the metadata's
        ``insets`` names, or, in a file without that key, each graph whose
        frame rect lies inside another graph's. The grid is inferred from
        the other graphs.
        """
        if self._insets is not None:
            inset = self._named_insets(parsed_axes, self._insets)
        else:
            inset = self._nested_graphs(parsed_axes)
        grid = iter(
            self._infer_grid_positions(
                [info for info, is_inset in zip(parsed_axes, inset) if not is_inset]
            )
        )
        return [None if is_inset else next(grid) for is_inset in inset]

    def _named_insets(self, parsed_axes, numbers) -> List[bool]:
        """Per graph, whether the metadata names it as an inset.

        A named graph whose frame rect was not recovered cannot be placed
        outside the grid, so it stays in it; that, and a number naming no
        graph, is noted.
        """
        inset = []
        for k, info in enumerate(parsed_axes):
            named = k + 1 in numbers
            if named and self._frame_rect(info) is None:
                self._note(
                    ImportCategory.LAYOUT,
                    f"graph {k + 1} is listed as an inset but has no amove + "
                    "size + scale 1 1 frame; it is laid out in the grid",
                    None,
                )
                named = False
            inset.append(named)
        stray = sorted(n for n in numbers if not 1 <= n <= len(parsed_axes))
        if stray:
            self._note(
                ImportCategory.LAYOUT,
                f"the metadata lists insets {stray} but the file has "
                f"{len(parsed_axes)} graphs; those numbers are ignored",
                None,
            )
        return inset

    def _nested_graphs(self, parsed_axes) -> List[bool]:
        """Per graph, whether its frame rect lies inside another graph's."""
        rects = [self._frame_rect(info) for info in parsed_axes]
        return [
            a is not None
            and any(
                b is not None and _rect_inside(a, b) and not _rect_inside(b, a)
                for b in rects
            )
            for a in rects
        ]

    def _frame_rect(self, info) -> Optional[Tuple[float, float, float, float]]:
        """``(x0, y0, x1, y1)`` of a graph placed by ``amove`` + size + scale 1 1."""
        size = self._invertible_triple(info.get("geometry_stmts") or [])
        amove = info.get("amove")
        if size is None or amove is None:
            return None
        x, y = amove
        return (x, y, x + size[0], y + size[1])

    def _infer_grid_positions(self, parsed_axes) -> List[tuple]:
        """Infer (rows, cols, idx) per axes from recovered amove positions."""
        n = len(parsed_axes)
        if n <= 1:
            return [(1, 1, 1)]

        amoves = [info.get("amove") for info in parsed_axes]
        # Whatever amove lines the figure DOES have, spanning the arrangement
        # under judgment here -- the most specific location determinable for
        # an aggregate that is, by definition, about more than one graph
        # block. None when no axes in the figure carried a recovered amove.
        amove_lines = [
            info.get("amove_line_no")
            for info in parsed_axes
            if info.get("amove_line_no") is not None
        ]
        arrangement_span = (min(amove_lines), max(amove_lines)) if amove_lines else None
        if any(a is None for a in amoves):
            # Hand-written multi-graph with no amove grid -> n x 1 fallback.
            self._note(
                ImportCategory.LAYOUT,
                "multi-graph without amove positions; using n x 1 grid",
                arrangement_span,
            )
            return [(n, 1, k + 1) for k in range(n)]

        positions = _clean_grid(amoves)
        if positions is None:
            positions = self._infer_spans(parsed_axes)
        if positions is None:
            # A frame set_aspect shrank keeps its cell's centre, not its corner.
            rects = [self._frame_rect(info) for info in parsed_axes]
            frames = [r for r in rects if r is not None]
            if len(frames) == n:
                positions = _clean_grid(
                    [((r[0] + r[2]) / 2, (r[1] + r[3]) / 2) for r in frames]
                )
        if positions is None:
            self._note(
                ImportCategory.LAYOUT,
                "amove positions do not form a clean grid; using n x 1 fallback",
                arrangement_span,
            )
            return [(n, 1, k + 1) for k in range(n)]
        return positions

    def _infer_spans(self, parsed_axes) -> Optional[List[tuple]]:
        """Grid positions for graphs that tile a grid with spanning cells.

        Each graph's frame rect (its ``amove`` + ``size w h`` + ``scale 1 1``)
        is placed on the columns and rows its clustered edges mark out (see
        :func:`_grid_bands`): a graph that starts in one column or row and
        ends in another spans those cells, and gets ``add_subplot``'s
        ``(first, last)`` index. ``None`` unless every graph has such a rect
        and together they cover each cell of the grid exactly once.
        """
        rects = []
        for info in parsed_axes:
            rect = self._frame_rect(info)
            if rect is None:
                return None
            rects.append(rect)

        cols_ = _grid_bands([r[0] for r in rects], [r[2] for r in rects])
        rows_ = _grid_bands([r[3] for r in rects], [r[1] for r in rects], reverse=True)
        rows, cols = len(rows_[1]), len(cols_[1])

        positions: List[tuple] = []
        covered: Set[Tuple[int, int]] = set()
        for x0, y0, x1, y1 in rects:
            c0, c1 = _band_span(cols_, x0, x1)
            r0, r1 = _band_span(rows_, y1, y0)
            if c0 is None or c1 is None or r0 is None or r1 is None:
                return None
            if c0 > c1 or r0 > r1:
                return None
            cells = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
            if cells & covered:
                return None
            covered |= cells
            first, last = r0 * cols + c0 + 1, r1 * cols + c1 + 1
            positions.append((rows, cols, first if first == last else (first, last)))
        if len(covered) != rows * cols:
            return None
        return positions

    def _populate_axes(self, ax, info):
        ax.title_text = info["title"] or ""
        ax.xlabel_text = info["xlabel"] or ""
        ax.ylabel_text = info["ylabel"] or ""
        ax.y2label_text = info["y2label"] or ""
        ax.x2label_text = info["x2label"] or ""
        ax.xscale = "log" if info["xlog"] else "linear"
        ax.yscale = "log" if info["ylog"] else "linear"
        ax.y2scale = "log" if info["y2log"] else "linear"
        ax.x2scale = "log" if info["x2log"] else "linear"
        # ``negate`` is GLE's spelling of an inverted axis; the model spells
        # the same thing as a descending limit pair, which is what the writer
        # turns back into ``negate`` (see GLEWriter._axis_direction).
        ax.xmin, ax.xmax = _oriented(info["xmin"], info["xmax"], info["xnegate"])
        ax.ymin, ax.ymax = _oriented(info["ymin"], info["ymax"], info["ynegate"])
        ax.y2min, ax.y2max = _oriented(info["y2min"], info["y2max"], info["y2negate"])
        ax.x2min, ax.x2max = _oriented(info["x2min"], info["x2max"], info["x2negate"])
        ax.xplaces = info["xplaces"]
        ax.yplaces = info["yplaces"]
        ax.xnames = info["xnames"]
        ax.ynames = info["ynames"]
        self._populate_axes_styling(ax, info)

        ax.lines = info["lines"]
        ax.scatters = info["scatters"]
        ax.bars = info["bars"]
        ax.hists = info["hists"]
        ax.functions = info["functions"]
        ax.fits = info["fits"]
        ax.fills = info["fills"]
        ax.errorbars = info["errorbars"]
        ax.file_series = info["file_series"]
        ax.derived_series = info["derived_series"]
        ax.texts = info["texts"]
        ax.images = info["images"]
        ax.rugs = info["rugs"]
        ax.heatmaps = info["heatmaps"]
        ax.contours = info["contours"]
        # Guides recovered from their provenance markers (gleplot.guides),
        # over a dataset or over a drawing after the graph.
        ax.reflines = info["reflines"]
        ax.spans = info["spans"]
        ax.passthrough = info["passthrough"]
        ax.trailing_passthrough = info["trailing_passthrough"]

        # A series whose sidecar had no real header row (hand-written .dat,
        # or a headerless import from an older gleplot version) has no
        # 'column_names' recovered above. Regenerate the same stable
        # defaults Axes.from_dict falls back to for pre-Track-E3 projects,
        # so the next save still gets a named header row.
        for attr in (
            "lines",
            "scatters",
            "bars",
            "fills",
            "errorbars",
            "reflines",
            "spans",
        ):
            for item in getattr(ax, attr):
                if "column_names" not in item:
                    defaults = item.default_column_names()
                    if defaults is not None:
                        item["column_names"] = defaults

        # Legend tri-state recovery.
        labels_present = self._labels_present(info)
        external = info.get("external_key")
        if external:
            # ``key off`` inside the graph only suppresses the draw-order
            # key. The visible legend is the ``begin key`` that followed.
            pos_short = external["pos"]
            ax.legend_pos = KEY_POSITIONS_SHORT_TO_LONG.get(pos_short, pos_short)
            ax.legend_on = None if labels_present else True
            if external.get("hei") is not None:
                ax.legend_fontsize = fontsize_cm_to_pt(external["hei"])
            ax.legend_frameon = not external.get("nobox")
            ax.legend_offset = external.get("offset")
            if external.get("separators"):
                ax.legend_ncol = int(external["separators"]) + 1
            if external.get("compact"):
                ax.legend_compact = True
            if external.get("background"):
                ax.legend_facecolor = external["background"]
            ax.legend_bbox_to_anchor = external["anchor"]
            ax.legend_labelcolor = external["labelcolor"]
            ax.legend_spacing = _legend_spacing(
                external["spacing"], ax.legend_fontsize, ax.figure
            )
        elif info["key_off"]:
            ax.legend_on = False
        elif info["key_line"]:
            # A 'key' option line; without 'pos' GLE's key sits top right,
            # the model's default position.
            pos_short = info["key_pos"]
            if pos_short is not None:
                ax.legend_pos = KEY_POSITIONS_SHORT_TO_LONG.get(pos_short, pos_short)
            # A key line + labels -> auto (None); + no labels -> True.
            ax.legend_on = None if labels_present else True
            if info["key_hei"] is not None:
                ax.legend_fontsize = fontsize_cm_to_pt(info["key_hei"])
            ax.legend_frameon = not info["key_nobox"]
            ax.legend_offset = info["key_offset"]
        else:
            if labels_present:
                # Hand-written implicit key: GLE draws a key from the per-series
                # key "label" tokens even without 'key pos'. Re-save will add
                # 'key pos tr' (default), visually equivalent.
                self._note(
                    ImportCategory.LEGEND,
                    "labeled series with no 'key' command; assuming "
                    "auto legend (re-save adds 'key pos tr')",
                    info.get("_block_span"),
                )
                ax.legend_on = None
            else:
                ax.legend_on = None
        if self._figure_legend is not None and labels_present:
            # With a figure legend an axes draws its own key only when asked
            # (Figure._prepare_legend): a key shown was asked for, and
            # 'key off' is the default.
            ax.legend_on = None if ax.legend_on is False else True

        if info["key_spacing"] and not external:
            ax.legend_spacing = _legend_spacing(
                info["key_spacing"], ax.legend_fontsize, ax.figure
            )
        nsep = info.get("key_separators") or 0
        if nsep:
            ax.legend_ncol = int(nsep) + 1
        if info.get("key_compact"):
            ax.legend_compact = True
        if info.get("key_background"):
            ax.legend_facecolor = info["key_background"]

    def _populate_axes_styling(self, ax, info) -> None:
        """Copy the recognized axes styling onto the model.

        Units are converted back to the model's: GLE's ``hei``/``lwidth`` are
        cm, the model keeps matplotlib points (``fontsize_cm_to_pt`` /
        ``linewidth_cm_to_pt``); ``dist`` and angles are already in the
        model's units (cm and degrees).
        """
        ax.title_size = _pt_or_none(info["title_hei"])
        ax.title_color = info["title_color"]
        ax.title_dist = info["title_dist"]
        ax.title_font = info["title_font"]
        for prefix in ("x", "y", "y2", "x2"):
            setattr(ax, f"{prefix}label_font", info[f"{prefix}title_font"])
            side = info[f"{prefix}side"]
            if side is not None:
                setattr(ax, f"{prefix}side_color", side["color"])
                if prefix in ("x", "y") and side["off"]:
                    setattr(ax, f"{prefix}side_off", True)
                if side["lwidth"] is not None:
                    setattr(
                        ax, f"{prefix}side_lwidth", linewidth_cm_to_pt(side["lwidth"])
                    )
            setattr(ax, f"{prefix}format", info[f"{prefix}format"])
            setattr(ax, f"{prefix}label_size", _pt_or_none(info[f"{prefix}title_hei"]))
            setattr(ax, f"{prefix}label_color", info[f"{prefix}title_color"])
            setattr(ax, f"{prefix}label_dist", info[f"{prefix}title_dist"])
            setattr(
                ax,
                f"{prefix}ticklabel_size",
                _pt_or_none(info[f"{prefix}labels_hei"]),
            )
            setattr(ax, f"{prefix}ticklabel_color", info[f"{prefix}labels_color"])
            setattr(ax, f"{prefix}ticklabel_angle", info[f"{prefix}angle"])
        ax.math_mode = info["math_mode"]
        ax._facecolor = info["facecolor"]
        for prefix in ("x", "y"):
            for name in (
                "nticks",
                "ftick",
                "shift",
                "symticks",
                "noticks",
                "nsubticks",
                "loglabels",
                "dticks",
                "dsubticks",
            ):
                setattr(ax, f"{prefix}{name}", info[f"{prefix}{name}"])
            for kind in ("tick", "subtick"):
                marks = info.get(f"_{prefix}{kind}_marks")
                if marks is None:
                    continue
                length = marks["length"]
                if length is not None:
                    # GLE's signed per-side length -> the model's whole tick
                    # and direction (see GLEWriter._add_tick_mark_style).
                    whole = abs(length) * (2.0 if info[f"{prefix}symticks"] else 1.0)
                    setattr(ax, f"{prefix}{kind}_length", linewidth_cm_to_pt(whole))
                    if length < 0:
                        setattr(ax, f"{prefix}{kind}_direction", "out")
                if marks["lwidth"] is not None:
                    setattr(
                        ax, f"{prefix}{kind}_width", linewidth_cm_to_pt(marks["lwidth"])
                    )
                setattr(ax, f"{prefix}{kind}_color", marks["color"])
                if kind == "subtick" and (marks["on"] or marks["off"]):
                    setattr(ax, f"{prefix}minorticks", bool(marks["on"]))
            if not info[f"{prefix}grid"]:
                continue
            setattr(
                ax,
                f"{prefix}grid",
                "both" if info[f"_{prefix}subticks"] is not None else "major",
            )
            ticks = info[f"_{prefix}ticks"]
            if ticks is None:
                continue
            lstyle = ticks["lstyle"]
            setattr(ax, f"{prefix}grid_lstyle", None if lstyle is None else int(lstyle))
            setattr(
                ax,
                f"{prefix}grid_lwidth",
                (
                    None
                    if ticks["lwidth"] is None
                    else linewidth_cm_to_pt(ticks["lwidth"])
                ),
            )
            setattr(ax, f"{prefix}grid_color", ticks["color"])

    def _labels_present(self, info) -> bool:
        # Fills and spans count: a labelled one emits ``keyfill`` (on the
        # fill's first dataset, or on the data-free span bridge). Reflines
        # count for the same reason, via their line bridge.
        for group in (
            "lines",
            "scatters",
            "bars",
            "hists",
            "functions",
            "fills",
            "errorbars",
            "file_series",
            "reflines",
            "spans",
            "derived_series",
        ):
            for s in info[group]:
                if s.get("label"):
                    return True
        return False

    def _restore_visibility_flags(self, ax, info):
        """Reproduce the writer's emission conditions for tick visibility.

        The writer emits:
          - ``xlabels off``          when ``show_xticks`` is False, or
                                     with ``xticks off`` for empty ``xplaces``
          - ``ylabels off``          when ``show_yticks`` is False (or as x)
          - ``xaxis ... nofirst``    when ``remove_first_xtick``
          - ``xaxis ... nolast``     when ``remove_last_xtick``
          - (same for y)
        Recover those flags from what we saw so re-save matches. But titles
        (``show_xlabel``/``show_ylabel``) are only *emitted* when the title
        text is present AND the flag is True; if a shared axes hid the title,
        the xtitle simply won't appear. We recover show_xlabel from whether a
        title was expected. Since the object model derives these from
        sharex/sharey via _apply_shared_axes_flags already, we override only
        the tick-removal flags which are directly observable.
        """
        ax._frame_off = info["frame_off"]
        ax._x2axis_off = info["x2axis_off"]
        ax._y2axis_off = info["y2axis_off"]
        ax._show_xticks = not info["xlabels_off"]
        ax._show_yticks = not info["ylabels_off"]
        ax._remove_first_xtick = info["nofirst_x"]
        ax._remove_last_xtick = info["nolast_x"]
        ax._remove_first_ytick = info["nofirst_y"]
        ax._remove_last_ytick = info["nolast_y"]
        # show_xlabel/show_ylabel: the writer hides the title by NOT emitting
        # xtitle. If we recovered no xlabel text but sharex hid it, the derived
        # flag already handles emission. Keep the derived show_* flags EXCEPT
        # when we observed a title was absent due to hiding: not distinguishable
        # from "no label", so leave as derived.

    # -- smooth ----------------------------------------------------------

    def _observe_unmodelled_smoothing(self, kind, attrs, line_no):
        """Record the smoothing state of a kind with no per-series field.

        SPEC 14.7 scopes ``smooth_mode``/``svg_smooth`` to line series, so an
        error-bar or file-reference dataset is re-emitted with whatever the
        figure-wide default turns out to be. That cuts *both* ways -- such a
        dataset can lose a smoothing clause it had, and it can gain one it
        never had -- so its state is recorded whether or not it is smoothed,
        and :meth:`_apply_smooth` decides which ones actually change once the
        default is known.

        Only line-drawing datasets are recorded: the writer emits the
        qualifier from inside its ``has_line`` branch, so a marker-only
        dataset is unaffected by the default in either direction.
        """
        if not attrs["has_line"]:
            return
        span = (line_no, line_no) if line_no is not None else None
        self._unmodelled_smooth.append(
            (
                kind,
                attrs["smooth_mode"],
                attrs["svg_smooth"],
                span,
                attrs.get("line_mode"),
            )
        )

    def _apply_smooth(self, fig, graph_cfg, smooth_flags):
        """Recover both layers of smoothing: the figure default and per-series.

        ``graph.smooth_curves`` is still a real figure-wide setting -- it is
        what the writer applies to every line-drawing kind that has no
        per-series field of its own (error bars, file references) and the
        default new line series inherit. It is inferred from the line
        datasets as before.

        On top of it, SPEC 14.7's per-series ``smooth_mode``/``svg_smooth``
        are stamped onto the recovered :class:`LineSeries` -- but only where
        they differ from what the figure-wide default already produces. That
        is the same "absent means the historical behaviour" rule the field
        itself follows, and it is what keeps a uniformly smoothed (or
        uniformly unsmoothed) file's recovered ``to_dict`` exactly the shape
        it had before this field existed.
        """
        if smooth_flags:
            if all(smooth_flags):
                graph_cfg.smooth_curves = True
            elif not any(smooth_flags):
                graph_cfg.smooth_curves = False
            else:
                graph_cfg.smooth_curves = True
                # No span: this is an aggregate over every line dataset in the
                # whole figure (mixed True/False across possibly several graph
                # blocks), not a property of any one of them -- see the span
                # coverage table in the module docstring.
                self._note(
                    ImportCategory.SMOOTH,
                    "mixed per-series smooth flags; each line dataset keeps "
                    "its own mode, and the figure-wide default (which error "
                    "bars and file references follow) becomes smooth",
                )
        # else: no line datasets -- leave the default (False). The writer
        # emits nothing that depends on it, so byte-identity is unaffected.

        default_mode = "smooth" if graph_cfg.smooth_curves else "none"
        for entry, mode, iterations in self._smooth_lines:
            # A line mode with no smooth keyword must stay unsmoothed even
            # when that matches the figure default. Otherwise a later
            # smooth_curves flip splines the points before the join
            # (graph2.cpp transform_data, then drawLine). A line with gaps
            # (hlines / vlines) is pinned the same way: GLE cannot smooth
            # its repeated x ("Identical X values"). An explicit smooth on
            # the same dataset still follows the default rule.
            pin_unsmoothed = (
                bool(entry.get("line_mode")) or bool(entry.get("gaps"))
            ) and mode == "none"
            if mode != default_mode or pin_unsmoothed:
                entry["smooth_mode"] = mode
            if iterations is not None:
                entry["svg_smooth"] = iterations

        # Kinds with no per-series field of their own take whatever the
        # figure-wide default gives them. Warn about exactly the ones that
        # differ from it -- a smoothed errorbar in a smoothed figure loses
        # nothing and must not be reported as if it did (SPEC 8.1.4).
        for kind, mode, iterations, span, line_mode in self._unmodelled_smooth:
            if line_mode and mode == "none" and iterations is None:
                # The writer pins this mode unsmoothed, which is what the
                # dataset already says.
                continue
            if line_mode and (mode != "none" or iterations is not None):
                self._note(
                    ImportCategory.SMOOTH,
                    f"{self._smooth_clause_text(mode, iterations)} on a {kind} "
                    f"dataset with line mode {line_mode!r} is dropped on "
                    "re-save. GLE would smooth the points before drawing "
                    "that mode, which replaces the discrete join.",
                    span,
                )
                continue
            if mode == default_mode and iterations is None:
                continue
            self._note(
                ImportCategory.SMOOTH,
                f"{self._smooth_clause_text(mode, iterations)} on a {kind} "
                "dataset is not modelled per-series (SPEC 14.7 scopes that to "
                "line series); it re-saves with the figure-wide default "
                f"({self._smooth_clause_text(default_mode, None)})",
                span,
            )

    @staticmethod
    def _smooth_clause_text(mode, iterations):
        """Human-readable form of a (mode, iterations) pair, for a note."""
        parts = []
        if iterations is not None:
            parts.append(f"svg_smooth {iterations}")
        if mode != "none":
            parts.append(mode)
        return f"'{' '.join(parts)}'" if parts else "no smoothing"

    # -- data-file naming state -----------------------------------------

    def _finalize_data_state(self, fig):
        """Set data_prefix / counters / used-files so re-save reuses names."""
        used = set()
        sidecars = set()
        for ax in fig.axes_list:
            # Guides count: a dataset-form guide (G18-lite) owns its sidecar
            # exactly as the plain series it used to be recovered as did, and
            # the name has to stay reserved -- otherwise the next series
            # added would be handed a name a guide is still writing to. A
            # draw-form guide (G17) has no data_file yet at this point; it is
            # given one below, from the state this loop settles.
            for s in (
                ax.lines
                + ax.scatters
                + ax.bars
                + ax.fills
                + ax.errorbars
                + ax.reflines
                + ax.spans
            ):
                df = s.get("data_file")
                if df:
                    used.add(df)
            for s in ax.heatmaps + ax.contours:
                df = s.get("data_file")
                if df:
                    sidecars.add(df)
        # Every reserved file (columnar sidecars + heatmap/contour/points raw
        # sidecars) is tracked so collision avoidance and to_dict round-trip see
        # the full set.
        fig._used_data_files = set(used) | set(sidecars)

        # Derive prefix from the columnar sidecar convention <prefix>_<N>.dat
        # first; fall back to the heatmap/contour/points sidecar convention
        # <prefix>_<kind><N>.<ext> when there are no columnar series.
        prefix, max_idx = self._derive_prefix(used)
        if prefix is None:
            prefix, _ = self._derive_prefix_from_sidecars(sidecars)
            if prefix is not None:
                fig.data_prefix = prefix
        elif prefix is not None:
            fig.data_prefix = prefix
            fig._local_data_counter = max_idx + 1

        # A guide recovered from its after-graph drawing owns no sidecar --
        # that form has none to own. Reserve one anyway, from the figure's own
        # naming state now that it is settled, so that adding data later (and
        # thereby resolving the axis the guide spans) puts the guide straight
        # back onto the literal-dataset path with a name that collides with
        # nothing.

        for ax in fig.axes_list:
            for guide in list(ax.reflines) + list(ax.spans):
                if not guide.get("data_file"):
                    guide["data_file"] = _resolve_data_file(fig, None)

    @staticmethod
    def _derive_prefix_from_sidecars(names) -> Tuple[Optional[str], int]:
        """Return the shared prefix of ``<prefix>_<kind><N>.<ext>`` sidecars.

        Recognizes ``heatmap``/``contour``/``points`` kinds with ``.z``/``.dat``
        extensions. Returns ``(None, -1)`` when there is no single confident
        prefix (or it is the default ``data``).
        """
        pat = re.compile(r"^(.*)_(?:heatmap|contour|points)\d+\.(?:z|dat)$")
        prefixes = set()
        for name in names:
            mobj = pat.match(name)
            if mobj:
                prefixes.add(mobj.group(1))
        if len(prefixes) == 1:
            pfx = next(iter(prefixes))
            if pfx == "data":
                return None, -1
            return pfx, 0
        return None, -1

    @staticmethod
    def _derive_prefix(used) -> Tuple[Optional[str], int]:
        """Return (prefix, max_index) from generated sidecar names, or (None,-1).

        Recognizes ``<prefix>_<N>.dat``. All generated files must share the
        same prefix for a confident derivation; if they disagree, fall back to
        None (the figure keeps global-counter naming, which is fine because the
        stored ``data_file`` names are re-emitted verbatim anyway).
        """
        pat = re.compile(r"^(.*)_(\d+)\.dat$")
        prefixes: Dict[str, List[int]] = {}
        for name in used:
            mobj = pat.match(name)
            if not mobj:
                continue
            pfx, idx = mobj.group(1), int(mobj.group(2))
            prefixes.setdefault(pfx, []).append(idx)
        if len(prefixes) == 1:
            pfx, idxs = next(iter(prefixes.items()))
            # Default gleplot prefix is 'data' -> that means no custom prefix.
            if pfx == "data":
                return None, -1
            return pfx, max(idxs)
        return None, -1

    # -- misc helpers ----------------------------------------------------

    @staticmethod
    def _as_statement(node) -> Optional[Statement]:
        if isinstance(node, Statement):
            return node
        if isinstance(node, BlankOrComment):
            return None
        return None

    @staticmethod
    def _first_string(toks) -> Optional[str]:
        for t in toks:
            if t.type is TokenType.STRING:
                return _string_value(t)
        return None

    @staticmethod
    def _title_has_unsupported_options(toks) -> bool:
        """True if a ``title`` line carries tokens beyond ``title "T"``.

        The only recognized form is the keyword followed by exactly one string
        literal. Trailing modifiers (``hei 0.6``, ``font roman``, ``dist ...``)
        cannot be represented on the model, so the whole line is preserved raw.
        """
        # toks[0] is 'title'. The recognized form is exactly one string and
        # nothing after it. Any token after that first string is unsupported.
        seen_string = False
        for t in toks[1:]:
            if t.type is TokenType.STRING and not seen_string:
                seen_string = True
                continue
            # Any further token (word/number/op/second string) is unsupported.
            return True
        return False

    @staticmethod
    def _stmt_text(stmt) -> str:
        """Raw text of a statement's physical line (verbatim passthrough)."""
        if stmt.source_line is not None:
            return stmt.source_line.text
        return stmt.raw

    def _raw_lines(self, node) -> List[str]:
        """Raw source lines for a node (for passthrough), verbatim."""
        out: List[str] = []
        if isinstance(node, OpaqueBlock):
            if node.begin.source_line is not None:
                out.append(node.begin.source_line.text)
            for sl in node.inner_lines:
                out.append(sl.text)
            if node.end is not None and node.end.source_line is not None:
                out.append(node.end.source_line.text)
            return out
        if isinstance(node, Statement):
            return [self._stmt_text(node)]
        if isinstance(node, BlankOrComment):
            return [self._stmt_text(node.statement)]
        return out


# --------------------------------------------------------------------------- #
# Grid-clustering helpers
# --------------------------------------------------------------------------- #


def _cluster(values, tol=0.5, reverse=False):
    """Cluster near-equal floats into ordered groups (representative values)."""
    uniq = sorted(set(values), reverse=reverse)
    clusters = []
    for v in uniq:
        placed = False
        for c in clusters:
            if abs(c[0] - v) <= tol:
                c.append(v)
                placed = True
                break
        if not placed:
            clusters.append([v])
    # representative = mean of each cluster
    reps = [sum(c) / len(c) for c in clusters]
    return reps


def _clean_grid(points) -> Optional[List[tuple]]:
    """``(rows, cols, idx)`` per point, if the points form a full grid.

    Columns and rows are the clustered x and y values (the top row has the
    highest y); ``None`` unless there is one point per cell.
    """
    col_clusters = _cluster([p[0] for p in points])
    row_clusters = _cluster([p[1] for p in points], reverse=True)
    rows, cols = len(row_clusters), len(col_clusters)
    if rows * cols != len(points):
        return None
    return [
        (
            rows,
            cols,
            _which_cluster(p[1], row_clusters, reverse=True) * cols
            + _which_cluster(p[0], col_clusters)
            + 1,
        )
        for p in points
    ]


def _rect_inside(inner, outer, tol=1e-3) -> bool:
    """True if rect ``inner`` lies within ``outer`` (both ``(x0, y0, x1, y1)``)."""
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def _grid_bands(starts, ends, reverse=False):
    """Columns (or rows) marked out by the start and end edges of frame rects.

    Returns ``(edges, bands)``: the clustered edges in order, and each band
    as a pair of indices into them. Every interval between neighbouring
    edges is a band, except one running from an edge where only frames end
    to an edge where only frames start: that is the gap between two cells.
    A cell no frame starts or ends in on its own (one a spanning frame
    covers) merges with its neighbour into one band.
    """
    edges = _cluster(list(starts) + list(ends), reverse=reverse)
    is_start = {_which_cluster(v, edges) for v in starts}
    is_end = {_which_cluster(v, edges) for v in ends}
    bands = [
        (i, i + 1) for i in range(len(edges) - 1) if i in is_start or i + 1 in is_end
    ]
    return edges, bands


def _band_span(grid, start, end):
    """``(first, last)`` band indices a frame from ``start`` to ``end`` covers.

    ``None`` for an end that does not sit on a band's edge.
    """
    edges, bands = grid
    i, j = _which_cluster(start, edges), _which_cluster(end, edges)
    first = next((k for k, band in enumerate(bands) if band[0] == i), None)
    last = next((k for k, band in enumerate(bands) if band[1] == j), None)
    return first, last


def _which_cluster(value, reps, tol=None, reverse=False):
    """Return the 0-based index of the cluster ``value`` belongs to."""
    best = 0
    best_d = None
    for k, r in enumerate(reps):
        d = abs(r - value)
        if best_d is None or d < best_d:
            best_d = d
            best = k
    return best


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def parse_gle_figure(
    path_or_text: Union[str, Path],
    *,
    base_dir: Optional[Union[str, Path]] = None,
) -> RecognizedFigure:
    """Recognize a ``.gle`` document into a :class:`RecognizedFigure`.

    Parameters
    ----------
    path_or_text : str or pathlib.Path
        Either a filesystem path to a ``.gle`` file, or the GLE source text
        itself. A value is treated as a path when it is a :class:`pathlib.Path`,
        or when it is a ``str`` that names an existing file; otherwise it is
        treated as source text.
    base_dir : str or pathlib.Path, optional
        Directory used to resolve relative ``data`` references when
        ``path_or_text`` is raw text (defaults to the current directory). When
        ``path_or_text`` is a path, its parent directory is used and
        ``base_dir`` is ignored.

    Returns
    -------
    RecognizedFigure
        ``.figure`` is the reconstructed model; ``.notes`` lists the recovery
        notes.
    """
    text, gle_path = _resolve_input(path_or_text, base_dir)
    rec = _Recognizer(text, gle_path)
    return rec.run()


def _resolve_input(path_or_text, base_dir) -> Tuple[str, Path]:
    if isinstance(path_or_text, Path):
        p = path_or_text
        return p.read_text(encoding="utf-8"), p
    if isinstance(path_or_text, str):
        # Heuristic: a short single-line string that exists as a file is a path;
        # multi-line content is source text.
        looks_like_path = "\n" not in path_or_text and len(path_or_text) < 4096
        if looks_like_path:
            candidate = Path(path_or_text)
            try:
                if candidate.exists() and candidate.is_file():
                    return candidate.read_text(encoding="utf-8"), candidate
            except OSError:
                pass
        # Raw source text.
        base = Path(base_dir) if base_dir is not None else Path(".")
        # Synthesize a pseudo gle_path in base_dir so relative data refs resolve.
        return path_or_text, base / "__inline__.gle"
    raise TypeError(f"Unsupported input type: {type(path_or_text)!r}")

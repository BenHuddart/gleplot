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
7. **Mixed ``smooth`` (hand-written only).** The writer applies ``smooth``
   globally (``graph.smooth_curves``). If a hand-written file has some line
   datasets ``smooth`` and some not, the recovered figure sets
   ``smooth_curves=True`` -- preserving the smoothing that is in the file
   rather than silently dropping it -- and warns; re-save then applies smooth
   to all line datasets.
8. **Constant / percentage error -> data column (hand-written only).** A
   ``dN ... err 0.5`` (constant) or ``dN ... err 10%`` (percentage) carries no
   error data column; GLE synthesizes the error at draw time. The recognizer
   converts it to a concrete per-point error array on the model (constant:
   value at every point; percentage: ``value/100 * abs(y)`` for vertical error,
   ``* abs(x)`` for horizontal -- matching ``graph2.cpp`` ``getErrorBarData``),
   which re-saves as a real ``.dat`` error column, and warns. If the referencing
   series cannot be loaded (broken ref), the original ``dN`` line is kept in the
   axes passthrough instead and a ``data:`` warning is emitted.
9. **Axis-remainder passthrough (hand-written only).** Unrecognized ``xaxis``/
   ``yaxis``/``y2axis`` sub-tokens (``off``/``grid``/``dticks``/``dsubticks``/
   ``nticks``/``format "..."``/...) are peeled off the recognized
   ``min``/``max``/``log``/``nofirst``/``nolast`` (which populate the model) and
   re-emitted as a *supplementary* axis line in the axes passthrough. GLE axis
   lines are cumulative, so the model-emitted axis line + the passthrough line
   together reproduce the intended result. ``STRING`` options keep their quotes.
   Original source spacing is preserved (so ``dticks pi/2`` stays valid). A
   ``structure:`` warning is emitted.
10. **title/key with unsupported options kept raw (hand-written only).** A
    ``title "T" hei 0.6 font roman`` or ``key pos tr hei 0.3 nobox offset ...``
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
      see the migration policy in :mod:`gleplot.parser.metadata`. Resolving
      auto against what GLE would actually have chosen needs a calibration
      render and happens in the editor, not here.
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

14. **Multi-dataset ``bar``/``fill`` groups kept raw (hand-written only).**
    ``bar dN,dM,... fill c1,c2,...`` groups several datasets into GLE's
    automatic side-by-side layout (see the GLE manual's
    ``bar d1,d2,d3 fill gray10,gray40,black`` example); ``BarSeries`` has no
    concept of a shared group, only an independent per-dataset bar. The whole
    statement is kept verbatim in the axes passthrough (all datasets and
    colors intact) with a ``structure:`` warning, instead of silently
    modeling only one dataset and dropping the rest. When every dataset a
    ``data`` statement declares ends up referenced only by such passthrough
    text (nothing then carries its ``data_file`` for the writer to
    regenerate from), the original ``data`` statement is restored verbatim
    too, ahead of the passthrough content that depends on it -- otherwise
    the regenerated file would reference datasets GLE was never told how to
    load. A ``data`` statement declaring a MIX of modeled and orphaned
    datasets is not currently reconstructed (re-emitting it whole would
    duplicate the modeled portion); a ``data:`` warning flags this instead
    of resolving it silently either way.

Tolerances for hand-written input
---------------------------------
Attribute order within a dataset command may vary; axis lines may be given
cumulatively (multiple ``xaxis`` lines merge); numbers may be expressions
(``2*pi``) resolved via :func:`~gleplot.parser.expr.eval_gle_number`; keywords
are case-insensitive; single-quoted strings and ``;``-joined statements are
accepted; British ``GREY`` colors are accepted. Anything not recognized is
preserved verbatim in the appropriate passthrough bucket (header / trailer /
axes / axes geometry) so it re-emits unchanged. A blank (or comment-only) line
separating two post-graph text clusters, or between ``end graph`` and the first
cluster, is
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
  smooth flags.
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
                        (``_build_series_from_attrs`` -> ``_parse_series_command``
                        -> ``_build_errorbar`` / ``_build_contour_from_cdata`` /
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
``smooth``              Always ``None``. The note is a true whole-figure
                        aggregate over every line dataset (across every graph
                        block); no single line is more responsible than any
                        other.
``programmatic``        Real, single-line: the specific top-level statement
                        whose keyword tripped the guard.
``metadata``            The whole ``! gleplot-meta-begin``..``! gleplot-meta-end``
                        block's span (``parse_metadata`` does not track a
                        per-line origin for its own warnings; the block is the
                        finest location available at the call site).
======================  ==========================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import numpy as np

from ..axes import Axes
from ..config import GLEGraphConfig, GLEMarkerConfig, GLEStyleConfig
from ..figure import Figure
from ..series import (
    BarSeries,
    ContourSeries,
    ErrorbarSeries,
    FileSeries,
    FillSeries,
    HeatmapSeries,
    LineSeries,
    ScatterSeries,
    TextAnnotation,
)
from . import metadata as _metadata
from .expr import eval_gle_number
from .lexer import Token, TokenType
from .report import ImportCategory, ImportNote
from .syntax import (
    BlankOrComment,
    GraphBlock,
    OpaqueBlock,
    Statement,
    parse_gle_source,
)
from .tables import (
    KEY_POSITIONS_SHORT_TO_LONG,
    LSTYLE_TO_MATPLOTLIB,
    PALETTE_SUB_TO_CMAP,
)
from .units import (
    capsize_cm_to_pt,
    cm_to_inches,
    fontsize_cm_to_pt,
    inches_to_cm,
    linewidth_cm_to_pt,
)
from ..dataio import (
    ColumnExtractionError,
    classify_data_file,
    extract_columns,
    resolve_data_reference,
)

__all__ = ["ImportCategory", "ImportNote", "RecognizedFigure", "parse_gle_figure"]


_DATASET_RE = re.compile(r"^d\d+$", re.IGNORECASE)


def _bar_stack_names(toks: List[Token]) -> Optional[Tuple[str, str]]:
    """``(dN, dM)`` for a ``bar dN from dM ...`` statement, else ``None``.

    GLE's stacked-bar form (the manual's 'stacked bar chart' example): ``dN``
    draws stacked on top of ``dM``. Detected up front, in pass 1, so an
    EARLIER, independent ``bar dM fill ...`` statement can still be
    recognized as part of this later stack -- see ``_bar_stack_datasets``
    and its use in :meth:`_Recognizer._parse_bar_command`.
    """
    words = [t.value.lower() for t in toks]
    for i, word in enumerate(words):
        if word == "from" and 0 < i < len(words) - 1:
            prev_word, next_word = words[i - 1], words[i + 1]
            if _DATASET_RE.match(prev_word) and _DATASET_RE.match(next_word):
                return prev_word, next_word
    return None


@dataclass
class RecognizedFigure:
    """Result of :func:`parse_gle_figure`.

    Attributes
    ----------
    figure : Figure
        The reconstructed object model.
    notes : tuple of ImportNote
        Structured recovery notes (category, message, and a source span where
        determinable) -- see the module "Warnings taxonomy" for the span
        coverage achievable per category. This is the source of truth;
        ``warnings`` is derived from it.
    warnings : list of str
        Human-readable ``"category: message"`` strings, one per note, in the
        same order -- kept for backward compatibility with every consumer
        written against the pre-G4 string API. Computed on each access from
        :attr:`notes`, never stored independently.
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


def _first_statement_of(source_line) -> Statement:
    """Build a throwaway :class:`Statement` from a raw block inner line.

    Opaque-block inner lines are stored as bare :class:`SourceLine`s (never
    tokenized into statements). The contour/fitz block parsers need their
    tokens, so this tokenizes one line's text into a Statement wrapper.
    """
    from .lexer import tokenize_line

    return Statement(
        tokens=tokenize_line(source_line.text),
        raw=source_line.text,
        line_no=source_line.line_no,
        sub_index=0,
        source_line=source_line,
    )


def _as_float(value, default: float) -> float:
    """Best-effort float from a recovered named-argument value."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_value(tok: Token) -> str:
    """Unwrap a STRING token's value: strip quotes, unescape ``\\"``/``\\'``."""
    v = tok.value
    q = tok.quote
    if q and len(v) >= 2 and v[0] == q:
        inner = v[1:-1] if v.endswith(q) else v[1:]
    else:
        inner = v
    # Writer only escapes '"'; unescape both quote styles defensively.
    return inner.replace('\\"', '"').replace("\\'", "'")


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


# --------------------------------------------------------------------------- #
# The recognizer
# --------------------------------------------------------------------------- #


class _Recognizer:
    """Stateful recognizer for one document. See :func:`parse_gle_figure`."""

    def __init__(self, text: str, gle_path: Path):
        self.text = text
        self.gle_path = gle_path
        self.notes: List[ImportNote] = []
        # dataset name (lower) -> (data_file, xcol_1based, ycol_1based)
        self._datasets: Dict[str, Tuple[str, int, int]] = {}
        # resolved-table cache per data_file name
        self._table_cache: Dict[str, object] = {}
        self._import_list: Optional[List[str]] = None
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
        # Contour/heatmap recognition state.
        # Line numbers spanned by gleplot_<name> subroutine definitions
        # (palette / colorbar / contour-labels). Dropped everywhere, like the
        # metadata block, and regenerated canonically from the model on re-save.
        self._gleplot_sub_lines: set = set()
        # fitz output ``.z`` file -> {points_file, extent, gridsize, ncontour}
        self._fitz_blocks: Dict[str, dict] = {}
        # contour ``.z`` file -> {levels}
        self._contour_blocks: Dict[str, dict] = {}
        # Line numbers of fitz/contour blocks recognized as gleplot-authored
        # (consumed into a series), dropped from passthrough.
        self._consumed_block_lines: set = set()

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

        # Metadata block (parsed from the whole file, tolerantly).
        meta, meta_warnings = _metadata.parse_metadata(self.text.splitlines())
        meta_span = (
            (min(self._meta_lines), max(self._meta_lines)) if self._meta_lines else None
        )
        for meta_msg in meta_warnings:
            self._note(ImportCategory.METADATA, meta_msg, meta_span)
        if "import-data" in meta:
            self._import_list = list(meta.get("import-data") or [])

        dpi = int(meta.get("dpi", 100))
        sharex = bool(meta.get("sharex", False))
        sharey = bool(meta.get("sharey", False))
        msize_scale = float(meta.get("msize_scale", 1.0))
        metadata_extra = {
            k: v
            for k, v in meta.items()
            if k not in ("dpi", "sharex", "sharey", "msize_scale", "import-data")
        }

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

        figsize = (8.0, 6.0)
        font = ""
        fontsize = 12.0
        passthrough_header: List[str] = []

        # --- Preamble: everything before the first graph-related node. ---
        first_graph_start = self._first_graph_region_start(nodes, graph_indices)

        figsize, font, fontsize, passthrough_header = self._parse_preamble(
            nodes[:first_graph_start]
        )

        # Build style/graph/marker configs.
        style = GLEStyleConfig()
        style.font = font
        style.fontsize = fontsize
        graph_cfg = GLEGraphConfig()
        marker_cfg = GLEMarkerConfig()
        marker_cfg.msize_scale = msize_scale

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
        fig.passthrough_header = passthrough_header

        # --- Graph blocks + interspersed amove/text/trailer. ---
        # Collect (amove_position, GraphBlock, deferred_text_nodes) tuples plus
        # trailing passthrough.
        parsed_axes: List[dict] = []
        smooth_flags: List[bool] = []  # per line-dataset across the whole fig

        i = first_graph_start
        trailer: List[str] = []
        pending_amove: Optional[Tuple[float, float]] = None
        # Verbatim source line of ``pending_amove``, so an amove that does not
        # become a placement rect can still be preserved (see _apply_geometry).
        pending_amove_raw: Optional[str] = None
        # 1-indexed source line of that same ``amove``, so notes about it
        # (layout: preserved verbatim / used for grid inference) can carry a
        # real span instead of ``None``.
        pending_amove_line: Optional[int] = None

        n = len(nodes)
        while i < n:
            node = nodes[i]
            if isinstance(node, GraphBlock):
                axes_info = self._parse_graph_block(node, marker_cfg, smooth_flags)
                axes_info["amove"] = pending_amove
                axes_info["amove_raw"] = pending_amove_raw
                axes_info["amove_line_no"] = pending_amove_line
                pending_amove = None
                pending_amove_raw = None
                pending_amove_line = None
                # Greedily consume deferred text cluster that follows.
                texts, consumed = self._consume_text_cluster(nodes, i + 1)
                axes_info["texts"] = texts
                # Then consume any post-graph colorbar / contour-label sub
                # calls belonging to this axes.
                consumed = self._consume_post_graph_calls(nodes, consumed, axes_info)
                parsed_axes.append(axes_info)
                i = consumed
                continue

            # Non-graph node between/after graphs.
            amove = self._match_amove(node)
            if amove is not None:
                # A previously pending amove reached here without a graph
                # block ever consuming it as a placement prefix -- a second
                # amove overwrites GLE's "current point" too, so the first
                # one can no longer be "the amove immediately before a graph
                # block" either. It can never become a placement prefix now:
                # flush it byte-verbatim into the trailer, in stream order,
                # rather than silently overwriting and losing it.
                if pending_amove_raw is not None:
                    trailer.append(pending_amove_raw)
                pending_amove = amove
                pending_amove_raw = self._stmt_text(node)
                pending_amove_line = getattr(node, "line_no", None)
                i += 1
                continue

            # Blank line directly separating subplots: skip silently only when
            # between graphs (writer emits a blank between subplots). Otherwise
            # it is trailer content.
            if isinstance(node, BlankOrComment) and self._more_graphs_after(nodes, i):
                i += 1
                continue

            # fitz/contour blocks consumed into a recognized series (their
            # geometry lives on the model; regenerated on re-save).
            if (
                isinstance(node, OpaqueBlock)
                and node.block_type in ("fitz", "contour")
                and node.begin.line_no in self._consumed_block_lines
            ):
                i += 1
                continue

            # Anything else after the graphs -> trailer passthrough. A
            # pending amove can no longer become a placement prefix once a
            # real statement sits between it and the next graph block (if
            # any) -- flush it ahead of this node, byte-verbatim, preserving
            # stream order.
            if pending_amove_raw is not None:
                trailer.append(pending_amove_raw)
                pending_amove = None
                pending_amove_raw = None
                pending_amove_line = None
            trailer.extend(self._raw_lines(node))
            i += 1

        # End of document: a still-pending amove has no following graph
        # block left to become a placement prefix for -- preserve it
        # byte-verbatim as the last trailer statement instead of dropping it
        # (see module docstring: an amove is either consumed as a placement
        # prefix or preserved verbatim, never silently lost).
        if pending_amove_raw is not None:
            trailer.append(pending_amove_raw)
            pending_amove = None
            pending_amove_raw = None
            pending_amove_line = None

        fig.passthrough_trailer = trailer

        # --- Assemble axes into the figure. ---
        self._assemble_axes(fig, parsed_axes, sharex, sharey)

        # --- smooth handling (global). ---
        self._apply_smooth(fig, graph_cfg, smooth_flags)

        # --- data-file naming state for byte-identical re-save. ---
        self._finalize_data_state(fig)

        return RecognizedFigure(figure=fig, notes=tuple(self.notes))

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
    ) -> Tuple[Tuple[float, float], str, float, List[str]]:
        figsize = (8.0, 6.0)
        font = ""
        fontsize = 12.0
        passthrough: List[str] = []

        # Track which lines belong to the metadata block, or to a gleplot_<name>
        # sub definition, so we drop them (both are regenerated canonically).
        meta_line_nos = self._meta_lines | self._gleplot_sub_lines

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
                passthrough.append(text)
                continue

            if isinstance(node, Statement):
                if node.source_line and node.line_no in meta_line_nos:
                    continue
                kw = node.keyword
                toks = _words_and_values(node)
                if kw == "size" and len(toks) >= 3:
                    w, nxt = _collect_value(toks, 1)
                    h, _ = _collect_value(toks, nxt)
                    if w is not None and h is not None:
                        figsize = (cm_to_inches(w), cm_to_inches(h))
                        continue
                if kw == "set" and len(toks) >= 2:
                    sub = toks[1].value.lower()
                    if sub == "font" and len(toks) >= 3:
                        font = toks[2].value
                        continue
                    if sub == "hei" and len(toks) >= 3:
                        hei, _ = _collect_value(toks, 2)
                        if hei is not None:
                            fontsize = fontsize_cm_to_pt(hei)
                            continue
                # Unrecognized preamble statement -> header passthrough.
                passthrough.append(self._stmt_text(node))
                continue

            # Opaque block in the preamble -> header passthrough (raw lines).
            passthrough.extend(self._raw_lines(node))

        return figsize, font, fontsize, passthrough

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
        """Parse one ``begin graph`` .. ``end graph`` into an axes-info dict."""
        info = {
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
            "xangle": None,
            "yangle": None,
            "y2angle": None,
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
            "xlabels_hei": None,
            "xlabels_color": None,
            "ylabels_hei": None,
            "ylabels_color": None,
            "y2labels_hei": None,
            "y2labels_color": None,
            # Deferred lines: an 'xticks'/'xsubticks' style is only part of
            # the model when that axis has a grid (the grid lines ARE the
            # ticks), and a 'y2labels on' is only implied when some y2
            # tick-label property is modeled. Whether that holds is not known
            # until the whole block has been read -- GLE statement order is
            # free -- so they are parked here and resolved by
            # _reconcile_axis_styling, which sends the unusable ones back to
            # passthrough verbatim.
            "_xticks": None,
            "_yticks": None,
            "_xsubticks": None,
            "_ysubticks": None,
            "_y2labels_on_raw": None,
            "_y2labels_on_line": None,
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
            # length-mismatch check (see _parse_graph_block) finds the pairing
            # unrepresentable on the model.
            "_xplaces_raw": None,
            "_yplaces_raw": None,
            "_xnames_raw": None,
            "_ynames_raw": None,
            "key_pos": None,  # short-form position or None
            "key_off": False,
            "key_hei": None,  # 'hei' in cm, or None (= inherit 'set hei')
            "key_nobox": False,
            "key_offset": None,  # (dx_cm, dy_cm) or None
            "_draw_seq_counter": 0,  # display-command order = GLE draw order
            "lines": [],
            "scatters": [],
            "bars": [],
            "fills": [],
            "errorbars": [],
            "file_series": [],
            "heatmaps": [],
            "contours": [],
            "passthrough": [],
            "series_order": [],  # to preserve ordering info if needed
            # Dataset names (e.g. 'd1') consumed by a 'bar'/'fill' command.
            # The writer emits a standalone 'dN key ""' statement right after
            # 'bar'/'fill' to neutralize GLE's auto-key-from-header behavior
            # (bar/fill have no 'key' sub-option of their own -- see
            # gleplot.writer.GLEWriter.add_bar_chart/add_fill_between). That
            # bare 'dN key ""' would otherwise look like a brand-new,
            # unlabeled line/scatter series to the generic dN-dispatch below;
            # this set lets pass 2 recognize and skip it as a suppression
            # marker instead of fabricating a phantom series.
            "_key_suppress_datasets": set(),
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
            # and the 'data'-statement reconciliation in _parse_graph_block.
            "_let_source_datasets": set(),
            # Both dataset names of every 'bar dN from dM ...' (GLE's
            # stacked-bar form) found ANYWHERE in this block, collected up
            # front in pass 1 -- so an EARLIER, independent 'bar dM fill
            # ...' statement can still recognize dM as part of a later
            # stack and stay raw instead of being modeled twice over (once
            # as its own BarSeries, once folded into the stack's raw text).
            # See _parse_bar_command.
            "_bar_stack_datasets": set(),
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

        # Local dataset map for THIS block (dataset refs are graph-local).
        datasets: Dict[str, Tuple[str, int, int]] = {}

        # --- Pass 1: collect data commands and merge per-dataset attribute
        # tokens across multiple 'dN ...' lines. This fixes forward references
        # ('d1 line ...' appearing before its 'data' command) and multi-line
        # attribute accumulation ('d1 line' / 'd1 lwidth X' / 'd1 key "A"' on
        # separate lines are ONE series, not three).
        #
        # merged_attr_toks: name(lower) -> flat token list (attributes only,
        # excluding the leading 'dN'), in first-appearance order.
        merged_attr_toks: Dict[str, List[Token]] = {}
        dataset_order: List[str] = []

        # merged_attr_raw: name(lower) -> verbatim source text of each 'dN
        # ...' statement contributing to that dataset's merged attributes, in
        # the same order as merged_attr_toks was built. Used when a dataset
        # ends up kept as passthrough (unresolved file, unconvertible
        # errorbar, etc.) so the fallback can re-emit the ORIGINAL line(s)
        # byte-for-byte instead of rejoining tokens with inserted spaces --
        # see _dn_passthrough_lines / the 'err 10%' -> 'err 10 %' corruption
        # this guards against (GLE rejects the space).
        merged_attr_raw: Dict[str, List[str]] = {}

        # Raw text of each 'data' statement, paired with the dataset names it
        # declares and its source line, in body order -- used after pass 2 to
        # restore a 'data' statement whose datasets ended up entirely
        # unmodeled (see the reconciliation below the pass-2 loop).
        data_stmts: List[Tuple[List[str], str, int]] = []

        for child in block.body:
            if isinstance(child, Statement):
                if self._skip_meta_stmt(child):
                    continue
                kw = child.keyword
                if kw == "data":
                    names = self._parse_data_command(
                        _words_and_values(child), datasets, line_no=child.line_no
                    )
                    if names:
                        data_stmts.append(
                            (names, self._stmt_text(child), child.line_no)
                        )
                    continue
                if kw == "let":
                    # 'let dK = dJ+off' -- register dK as an offset alias of dJ
                    # (dJ's 'data' command precedes it in body order, so dJ is
                    # already known here in pass 1).
                    self._parse_let_command(_words_and_values(child), datasets, info)
                    continue
                if kw == "bar":
                    # Look ahead for GLE's stacked-bar form ('bar dN from dM
                    # ...') anywhere in the block, before pass 2 decides
                    # whether an EARLIER, independent 'bar dM fill ...'
                    # becomes its own BarSeries (see _parse_bar_command). No
                    # 'continue': pass 2 still needs to dispatch this
                    # statement itself.
                    stacked = _bar_stack_names(_words_and_values(child))
                    if stacked is not None:
                        cast(set, info["_bar_stack_datasets"]).update(stacked)
                if kw is not None and _DATASET_RE.match(kw):
                    name = kw
                    if name not in merged_attr_toks:
                        merged_attr_toks[name] = []
                        merged_attr_raw[name] = []
                        dataset_order.append(name)
                    merged_attr_toks[name].extend(_words_and_values(child)[1:])
                    merged_attr_raw[name].append(self._stmt_text(child))
                    continue

        # --- Pass 2: walk the body in order, dispatching non-dN statements
        # (axis/title/key/bar/fill/passthrough) and emitting exactly one series
        # per merged dataset the first time that dataset name is encountered.
        emitted: set = set()
        for child in block.body:
            if isinstance(child, OpaqueBlock):
                info["passthrough"].extend(self._raw_lines(child))
                continue
            if isinstance(child, BlankOrComment):
                # Blank/comment inside a graph block that the writer never
                # emits -> preserve as axes passthrough (hand-written).
                stmt = child.statement
                if self._skip_meta_stmt(stmt):
                    continue
                text = stmt.source_line.text if stmt.source_line else stmt.raw
                info["passthrough"].append(text)
                continue
            if not isinstance(child, Statement):
                continue
            if self._skip_meta_stmt(child):
                continue

            kw = child.keyword
            if kw == "data":
                continue  # already handled in pass 1
            if kw == "let":
                # Recognized offset alias -> consumed (the offset now lives on
                # the aliased series). An unrecognized 'let' falls through to
                # generic dispatch, which preserves it as raw GLE.
                toks = _words_and_values(child)
                target = toks[1].value.lower() if len(toks) > 1 else None
                if target in info["_offset_let_datasets"]:
                    continue
            if kw is not None and _DATASET_RE.match(kw):
                name = kw
                if name in emitted:
                    continue
                attr_toks = merged_attr_toks.get(name, [])
                if name in info[
                    "_key_suppress_datasets"
                ] and self._is_bare_key_suppression(attr_toks):
                    # 'dN key ""' with no other attributes, following a
                    # 'bar'/'fill' command that already consumed this
                    # dataset -- the writer's auto-key-from-header
                    # suppression marker (see writer.add_bar_chart /
                    # add_fill_between), not a real second series. Consume
                    # silently: no series, no passthrough (matches what the
                    # writer will regenerate from the bar/fill entry's
                    # column_names on next save).
                    emitted.add(name)
                    continue
                emitted.add(name)
                merged = [Token(TokenType.WORD, name, (0, 0))] + attr_toks
                self._build_series_from_attrs(
                    name,
                    merged,
                    datasets,
                    info,
                    marker_cfg,
                    smooth_flags,
                    line_no=child.line_no,
                    raw_stmts=merged_attr_raw.get(name, []),
                )
                continue

            self._dispatch_graph_statement(
                child, info, datasets, marker_cfg, smooth_flags
            )

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
        consumed = (
            set(info["_key_suppress_datasets"]) | emitted | info["_let_source_datasets"]
        )
        # A dataset may also be consumed indirectly, referenced by NAME from
        # another dataset's own attributes rather than having a 'dN ...'
        # line of its own -- e.g. errorbar's 'd1 ... err d2 ...' points at a
        # sibling dataset holding the error column. Such a reference is
        # resolved by the consuming series' own 'data_file'/columns, so it
        # is not orphaned even though it never appears in ``emitted``.
        for attr_toks in merged_attr_toks.values():
            for t in attr_toks:
                if _DATASET_RE.match(t.value):
                    consumed.add(t.value.lower())
        restored: List[str] = []
        for names, raw, data_line_no in data_stmts:
            if not any(n in consumed for n in names):
                restored.append(raw)
            elif not all(n in consumed for n in names):
                # Mixed: some of this statement's datasets became real
                # series (the writer will regenerate a 'data' line for
                # those), others are orphaned (raw text refers to them but
                # nothing carries 'data_file' for them). Re-emitting the
                # whole original line would duplicate the modeled portion;
                # dropping it silently loses the rest. Surface it instead of
                # guessing.
                #
                # This case is now rare in practice: the one recurring
                # source of it -- a 'bar dM fill ...' modeled independently
                # while a LATER 'bar dN from dM ...' (GLE's stacked-bar
                # form) needed dM to stay raw alongside dN -- is headed off
                # up front by ``_bar_stack_datasets`` (see
                # _parse_bar_command), which keeps BOTH names raw so this
                # statement is fully unconsumed instead of mixed. A
                # genuinely mixed statement still reaching here has no
                # narrower fix available: synthesizing a second 'data'
                # clause for just the orphaned names would reference columns
                # the modeled series' OWN regenerated sidecar no longer
                # carries (GLEWriter always rewrites an owned series' data
                # file with exactly the columns it uses -- see
                # GLEWriter.add_bar_chart/_write_columns), which would
                # silently corrupt the file instead of fixing the reference.
                self._note(
                    ImportCategory.DATA,
                    "'"
                    + raw.strip()
                    + "' mixes datasets that became series with datasets "
                    "only referenced by raw GLE; the raw reference(s) may "
                    "not resolve after save",
                    (data_line_no, data_line_no),
                )
        if restored:
            info["passthrough"][0:0] = restored

        self._reconcile_places_names(info)
        self._reconcile_axis_styling(info)
        return info

    def _reconcile_axis_styling(self, info) -> None:
        """Decide what the parked ``*ticks``/``y2labels on`` lines meant.

        Run once the whole graph block has been read, because GLE does not
        fix the order of these statements relative to the ``xaxis ... grid``
        that gives them their meaning:

        * ``xticks``/``xsubticks`` style is grid style, and only when that
          axis HAS a grid. Without one it would restyle bare ticks, which the
          model cannot express -- so the line goes back to passthrough
          verbatim.
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
        """
        for prefix in ("x", "y"):
            ticks = info[f"_{prefix}ticks"]
            subticks = info[f"_{prefix}subticks"]
            gridded = info[f"{prefix}grid"]
            if ticks is not None and not (gridded and ticks["ok"] and not ticks["on"]):
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
                gridded
                and subticks["ok"]
                and subticks["on"]
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
        if info["_y2labels_on_raw"] is not None:
            implied = (
                info["y2format"] is not None
                or info["y2angle"] is not None
                or info["y2labels_hei"] is not None
                or info["y2labels_color"] is not None
                or info["y2min"] is not None
                or info["y2max"] is not None
                or info["y2log"]
                or bool(info["y2label"])
            )
            if not implied:
                info["passthrough"].append(info["_y2labels_on_raw"])
                y2_line = info["_y2labels_on_line"]
                self._note(
                    ImportCategory.STRUCTURE,
                    "'y2labels on' with nothing to style; kept as "
                    "raw GLE, not editable",
                    (y2_line, y2_line) if y2_line is not None else None,
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
            for field in (places_field, names_field):
                raw = info.pop(f"_{field}_raw", None)
                raw_line = info.pop(f"_{field}_raw_line", None)
                if raw is not None:
                    info["passthrough"].append(raw)
                if raw_line is not None:
                    lines.append(raw_line)
                info[field] = None
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
        ``bar``/``fill`` command -- see ``writer.add_bar_chart`` /
        ``add_fill_between``) so it isn't mistaken for a real second series
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

    def _build_series_from_attrs(
        self,
        name,
        merged_toks,
        datasets,
        info,
        marker_cfg,
        smooth_flags,
        line_no=None,
        raw_stmts=None,
    ):
        """Build one series from a dataset's merged attribute tokens.

        ``line_no`` is the first body-order statement that named this
        dataset (the same anchor pass 1 merged its attributes from), threaded
        through so notes raised while building the series carry a real span.

        ``raw_stmts`` is the verbatim source text of each physical 'dN ...'
        statement that fed ``merged_toks`` (usually just one), threaded
        through so a passthrough fallback can re-emit byte-identical source
        instead of rejoining tokens with inserted spaces.
        """
        self._parse_series_command(
            merged_toks,
            datasets,
            info,
            marker_cfg,
            smooth_flags,
            line_no=line_no,
            raw_stmts=raw_stmts,
        )

    def _dispatch_graph_statement(self, stmt, info, datasets, marker_cfg, smooth_flags):
        kw = stmt.keyword
        toks = _words_and_values(stmt)
        if not toks:
            return

        if kw in ("size", "scale", "fullsize"):
            # Graph geometry. Recorded verbatim (plus its parsed arguments)
            # and classified later by _apply_geometry -- never dropped.
            info["geometry_stmts"].append(
                _GraphGeometryStmt(
                    keyword=kw,
                    words=[t.value.lower() for t in toks[1:]],
                    values=_collect_values(toks, 1),
                    raw=self._stmt_text(stmt),
                    line_no=self._opt_line_no(stmt),
                )
            )
            return
        if kw == "title":
            self._parse_title_line(toks, info, stmt)
            return
        if kw in ("xtitle", "ytitle", "y2title"):
            self._parse_axis_title_line(kw, toks, info, stmt)
            return
        if kw in ("xaxis", "yaxis", "y2axis"):
            self._parse_axis_line(kw, toks, info, stmt)
            return
        if kw in ("xlabels", "ylabels", "y2labels"):
            self._parse_labels_line(kw, toks, info, stmt)
            return
        if kw in ("xticks", "yticks", "xsubticks", "ysubticks"):
            self._parse_ticks_line(kw, toks, info, stmt)
            return
        if kw in ("xplaces", "yplaces", "xnames", "ynames"):
            self._parse_places_or_names_line(kw, toks, info, stmt)
            return
        # NOTE: 'data' and 'dN' statements are handled by the two-pass driver
        # in _parse_graph_block, not here.
        if kw == "bar":
            self._parse_bar_command(toks, datasets, info, stmt)
            return
        if kw == "fill":
            self._parse_fill_command(toks, datasets, info, stmt)
            return
        if kw == "key":
            self._parse_key_command(toks, info, stmt)
            return
        if kw == "colormap":
            self._parse_colormap(toks, info, stmt)
            return

        # Unrecognized statement inside a graph block -> axes passthrough.
        info["passthrough"].append(self._stmt_text(stmt))

    # -- text styling (title / axis titles / tick labels) ----------------

    _TEXT_PREFIX = {
        "xtitle": "x",
        "ytitle": "y",
        "y2title": "y2",
        "xlabels": "x",
        "ylabels": "y",
        "y2labels": "y2",
    }

    def _parse_text_options(self, toks, start):
        """Peel ``hei H`` / ``color C`` / ``dist D`` off a title/labels line.

        These three options are shared by GLE's ``title``, ``xtitle`` family
        and ``xlabels`` family, in any order. Returns
        ``(options, remainder)``: a dict with ``hei``/``color``/``dist``
        (None where absent) and the tokens that were none of them, which the
        caller decides what to do with -- there is no "ignore the rest" path.
        """
        opts = {"hei": None, "color": None, "dist": None}
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
        """``title "T" [hei H] [color C] [dist D]``.

        Anything else on the line (``font roman``, a second string, a token
        before the text) cannot be represented, and GLE's ``title`` is a
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

    def _parse_axis_title_line(self, kw, toks, info, stmt) -> None:
        """``xtitle "L" [hei H] [color C] [dist D]`` (and y/y2 twins).

        Same all-or-nothing rule as :meth:`_parse_title_line`: ``adist``,
        ``font`` and ``y2title``'s ``rotate`` are not modeled, and an axis
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

    def _parse_labels_line(self, kw, toks, info, stmt) -> None:
        """``xlabels [off] [hei H] [color C]`` (and y/y2 twins).

        ``off`` is the writer's tick-label suppression for shared axes.
        ``on`` is modeled only for y2, where it is what makes any y2
        tick-label property visible at all (GLE draws no y2 labels without
        it) -- and only if such a property is actually present, which
        :meth:`_reconcile_axis_styling` decides once the block has been read.
        ``dist``/``font``/``log`` are not modeled, so a line carrying them is
        kept whole as raw GLE.
        """
        prefix = self._TEXT_PREFIX[kw]
        opts, remainder = self._parse_text_options(toks, 1)
        leftover: List[Token] = []
        off = False
        on = False
        for tok in remainder:
            word = tok.value.lower()
            if word == "off" and prefix in ("x", "y"):
                off = True
            elif word == "on" and prefix == "y2":
                on = True
            else:
                leftover.append(tok)
        if leftover or (off and (opts["hei"] is not None or opts["color"] is not None)):
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
            info["_y2labels_on_raw"] = self._stmt_text(stmt)
            info["_y2labels_on_line"] = stmt.line_no if stmt is not None else None
        info[f"{prefix}labels_hei"] = opts["hei"]
        info[f"{prefix}labels_color"] = opts["color"]

    def _parse_ticks_line(self, kw, toks, info, stmt) -> None:
        """``xticks``/``xsubticks`` style, parked for later reconciliation.

        On the model these are grid styling, and only meaningful when that
        axis has a grid (see :class:`gleplot.writer.AxisStyle`). GLE allows
        the ``xaxis ... grid`` that decides it to appear anywhere in the
        block, so the line is recorded here and judged by
        :meth:`_reconcile_axis_styling`; ``length``/``off`` and any other
        sub-command mean the line is not ours and goes back to passthrough
        untouched.
        """
        prefix = "x" if kw.startswith("x") else "y"
        key = f"_{prefix}subticks" if "sub" in kw else f"_{prefix}ticks"
        parsed: Dict[str, Any] = {
            "raw": self._stmt_text(stmt),
            "line_no": stmt.line_no if stmt is not None else None,
            "lstyle": None,
            "lwidth": None,
            "color": None,
            "on": False,
            "ok": True,
        }
        i = 1
        m = len(toks)
        while i < m:
            word = toks[i].value.lower()
            if word in ("lstyle", "lwidth") and i + 1 < m:
                value, nxt = _collect_value(toks, i + 1)
                if value is not None:
                    parsed[word] = value
                    i = nxt
                    continue
            elif word == "color" and i + 1 < m:
                color, nxt = _collect_color(toks, i + 1)
                if color is not None:
                    parsed["color"] = color
                    i = nxt
                    continue
            elif word == "on":
                parsed["on"] = True
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
        prefix = {"xaxis": "x", "yaxis": "y", "y2axis": "y2"}[kw]
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
            if w == "grid" and prefix in ("x", "y"):
                # y2 has no grid on the model: GLE's grid is the axis' own
                # ticks stretched across the graph, so 'y2axis grid' would be
                # the y grid drawn from the other side. Left unrecognized (and
                # therefore preserved) rather than folded into ygrid.
                info[f"{prefix}grid"] = True
                i += 1
                continue
            # Unrecognized axis sub-token (off/grid/dticks/dsubticks/nticks/
            # format/hei/...). GLE axis lines are cumulative, so we peel the
            # recognized min/max/log/nofirst/nolast into the model and re-emit
            # the UNRECOGNIZED remainder as a supplementary axis line in
            # passthrough. e.g. 'xaxis min 0 max 2*pi dticks pi/2 grid' ->
            # model gets min/max; passthrough gets 'xaxis dticks pi/2 grid'.
            remainder.append(toks[i])
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
            esc = inner.replace(q, "\\" + q)
            return f"{q}{esc}{q}"
        return tok.value

    # -- explicit tick places/names ---------------------------------------

    def _parse_places_or_names_line(self, kw, toks, info, stmt) -> None:
        """``xplaces v1 v2 ...`` / ``xnames "a" "b" ...`` (and y variants).

        Each is a standalone statement (sibling to ``xaxis``/``yaxis``, not
        one of its sub-tokens) so it is dispatched here directly. A line that
        does not fully parse as a number list (``*places``) or string list
        (``*names``) is kept verbatim in the axes passthrough instead --
        final ``*places``/``*names`` pairing (length match) is checked once
        the whole graph block has been read, in :meth:`_parse_graph_block`.
        """
        is_names = kw.endswith("names")
        prefix = "x" if kw.startswith("x") else "y"
        field = f"{prefix}names" if is_names else f"{prefix}places"

        values: List = []
        i = 1
        m = len(toks)
        if is_names:
            while i < m and toks[i].type is TokenType.STRING:
                values.append(_string_value(toks[i]))
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
          number.  A single-column file switches to index-x (``nox``).
        * **Auto** ``data f.dat`` -- no dataset clauses: register d1=c1,c2,
          d2=c1,c3, ... one per column past the x column (up to the file's
          column count), when the file resolves.  Single-column file -> d1 =
          index,c1.

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
        while i < m:
            name_tok = toks[i]
            if name_tok.type is not TokenType.WORD or not _DATASET_RE.match(
                name_tok.value
            ):
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

        need_auto = not given or any(c is None for _n, c in given)
        ncols = self._file_column_count(data_file) if need_auto else None

        # x column / y offset per GLE: single-column file uses index x.
        if ncols is not None and ncols <= 1:
            cx, cy_first = 0, 1  # x = point index, y = c1
        else:
            cx, cy_first = 1, 2  # x = c1, y starts at c2

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
            if ncols <= 1:
                self._register_dataset("d1", data_file, 0, 1, datasets)
                return ["d1"]
            names = [f"d{k + 1}" for k in range(ncols - 1)]
            for name in names:
                k = int(name[1:]) - 1
                self._register_dataset(name, data_file, 1, k + 2, datasets)
            return names

        # Explicit and/or positional clauses.
        for pos, (name, cols) in enumerate(given):
            if cols is not None:
                self._register_dataset(name, data_file, cols[0], cols[1], datasets)
            else:
                # Positional: y column follows GLE's position-based assignment.
                ycol = pos + cy_first
                self._register_dataset(name, data_file, cx, ycol, datasets)
        return [name for name, _cols in given]

    def _register_dataset(self, name, data_file, xcol, ycol, datasets):
        datasets[name] = (data_file, xcol, ycol)
        self._datasets[name] = (data_file, xcol, ycol)

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
        if source not in datasets:
            return
        magnitude = eval_gle_number(toks[5:])
        if magnitude is None:
            return
        offset = -magnitude if op == "-" else magnitude
        data_file, xcol, ycol = datasets[source]
        self._register_dataset(target, data_file, xcol, ycol, datasets)
        info["_dataset_offsets"][target] = float(offset)
        info["_offset_let_datasets"].add(target)
        # 'source' is consumed by this alias (its file/columns are what the
        # aliased series actually reads) even though it never gets its own
        # 'dN ...' statement -- see the 'data'-statement reconciliation in
        # _parse_graph_block.
        info["_let_source_datasets"].add(source)

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

    def _file_column_count(self, data_file) -> Optional[int]:
        """Number of columns in the resolved data file, or None if unresolved."""
        resolved = self._resolve_table(data_file)
        if resolved.error is not None or resolved.table is None:
            return None
        return resolved.table.n_cols

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

    def _parse_bar_command(self, toks, datasets, info, stmt=None):
        """``bar dN fill COLOR`` (or ``bar dN,dM,... fill c1,c2,...``)"""
        d_names = []
        color = "RED"
        i = 1
        m = len(toks)
        while i < m:
            w = toks[i].value
            wl = w.lower()
            if _DATASET_RE.match(wl):
                d_names.append(wl)
            elif wl == "fill" and i + 1 < m:
                val, nxt = _collect_color(toks, i + 1)
                if val is not None:
                    color = val
                i = nxt
                continue
            i += 1

        if len(d_names) > 1:
            # A single 'bar' command spanning multiple datasets groups them
            # into GLE's automatic side-by-side layout (see the GLE manual's
            # 'bar d1,d2,d3 fill ...' grouped-bar-chart example) -- there is
            # no BarSeries concept for a shared group, only independent
            # per-dataset bars. Modeling only the last dataset (the old
            # behavior) silently dropped the rest with no warning, violating
            # the no-silent-drops contract. Keep the whole statement raw
            # instead.
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "multi-dataset bar group ("
                + ",".join(d_names)
                + ") kept as raw GLE, not editable",
                self._stmt_span(stmt),
            )
            return

        d_name = d_names[0] if d_names else None
        if d_name is None or d_name not in datasets:
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
            return
        if d_name in info["_bar_stack_datasets"]:
            # This dataset ALSO appears in a 'bar dN from dM ...' statement
            # elsewhere in the block (pass 1's look-ahead, ``_bar_stack_names``)
            # -- GLE's stacked-bar relationship has no BarSeries model, so
            # this otherwise-ordinary single-dataset 'bar' must stay raw
            # alongside it rather than being modeled independently. Modeling
            # it anyway would have the writer regenerate ITS dataset's own
            # '.dat' sidecar with only the columns IT uses (GLEWriter always
            # rewrites an owned series' data file that way -- see
            # add_bar_chart/_write_columns), silently truncating away the
            # column(s) the stack statement still needs from that same
            # file. The stack statement's own "multi-dataset bar group" note
            # already explains the group to the no-silent-drops contract, so
            # none is duplicated here.
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
            return
        info["_key_suppress_datasets"].add(d_name)
        data_file, xcol, ycol = datasets[d_name]
        loaded = self._load_series(
            data_file, xcol, ycol, line_no=self._opt_line_no(stmt)
        )
        entry = BarSeries(
            colors=None,
            label=None,
            data_file=data_file,
        )
        if loaded is None or loaded.get("error"):
            # Broken data -> represent as file_series-style reference w/ error.
            info["file_series"].append(
                FileSeries(
                    series_type="bar",
                    data_file=data_file,
                    x_col=xcol,
                    y_col=ycol,
                    color=color,
                    data_error=(loaded or {}).get("error", "unresolved"),
                )
            )
            return
        x = loaded["x"]
        height = loaded["y"]
        entry["x"] = x
        entry["height"] = height
        entry["colors"] = [color] * len(height)
        column_names = self._recovered_column_names(data_file, [xcol, ycol])
        if column_names is not None:
            entry["column_names"] = column_names
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        info["bars"].append(entry)

    def _parse_fill_command(self, toks, datasets, info, stmt=None):
        """``fill dA,dB color COLOR``"""
        # tokens: fill dA , dB color COLOR
        d_names = []
        color = "LIGHTBLUE"
        i = 1
        m = len(toks)
        while i < m:
            w = toks[i]
            wl = w.value.lower()
            if _DATASET_RE.match(wl):
                d_names.append(wl)
            elif wl == "color" and i + 1 < m:
                val, nxt = _collect_color(toks, i + 1)
                if val is not None:
                    color = val
                i = nxt
                continue
            i += 1
        if len(d_names) < 2 or d_names[0] not in datasets or d_names[1] not in datasets:
            info["passthrough"].append(self._bar_fill_passthrough_line(toks, stmt))
            return
        info["_key_suppress_datasets"].add(d_names[0])
        info["_key_suppress_datasets"].add(d_names[1])
        f1, xc1, yc1 = datasets[d_names[0]]
        f2, xc2, yc2 = datasets[d_names[1]]
        # fill data file has c1=x, c2=y1, c3=y2. d1=c1,c2 ; d2=c1,c3.
        loaded = self._load_series(
            f1, xc1, yc1, extra_cols=[yc2], line_no=self._opt_line_no(stmt)
        )
        if loaded is None or loaded.get("error"):
            info["file_series"].append(
                FileSeries(
                    series_type="fill",
                    data_file=f1,
                    x_col=xc1,
                    y1_col=yc1,
                    y2_col=yc2,
                    color=color,
                    data_error=(loaded or {}).get("error", "unresolved"),
                )
            )
            return
        x = loaded["x"]
        y1 = loaded["y"]
        y2 = loaded.get(f"c{yc2}")
        fill_entry = FillSeries(
            x=x,
            y1=y1,
            y2=y2,
            color=color,
            # 1.0 (opaque), not a guessed fraction: `color` as parsed here IS
            # the exact GLE colour text (verbatim, via _collect_color) that
            # will be re-emitted -- if it already carries its own alpha
            # (a hand-written `rgba255(...)`), gleplot.colors.apply_alpha
            # passes an already-formed colour expression through unchanged
            # regardless of this field (see its docstring), and if it is a
            # plain colour, 1.0 is the only value that keeps apply_alpha a
            # no-op so a round-tripped non-alpha fill stays byte-identical
            # (Track G6; see tests/parser/test_recognizer.py and
            # tests/parser/_golden_battery.py::fill_between). A guessed
            # fraction here (this used to be a fixed 0.3, back when alpha was
            # accepted but never rendered) would make apply_alpha rewrite the
            # colour on the very next save.
            alpha=1.0,
            label=None,
            offset=info["_dataset_offsets"].get(d_names[0], 0.0),
            data_file=f1,
        )
        column_names = self._recovered_column_names(f1, [xc1, yc1, yc2])
        if column_names is not None:
            fill_entry["column_names"] = column_names
        info["fills"].append(fill_entry)

    # -- key -------------------------------------------------------------

    def _parse_key_command(self, toks, info, stmt=None):
        rest = [t.value.lower() for t in toks[1:]]
        # Exactly 'key off' -> recognized.
        if rest == ["off"]:
            info["key_off"] = True
            return
        # The modelled option set, in any order: 'pos P', 'hei H', 'nobox',
        # 'offset X Y' -- exactly what GLEWriter.add_legend emits. Parse into a scratch
        # dict first so a later unmodelled token leaves ``info`` untouched.
        # Scanned from the Token list (not the lowered strings above) because
        # a negative literal like the writer's own 'offset 1.5 -0.5' tokenizes
        # as an OP '-' followed by a NUMBER, not a single signed NUMBER token.
        parsed = self._scan_key_options(toks[1:])
        if parsed is not None:
            info["key_pos"] = parsed.get("pos", info["key_pos"])
            info["key_hei"] = parsed.get("hei", info["key_hei"])
            info["key_nobox"] = parsed.get("nobox", info["key_nobox"])
            info["key_offset"] = parsed.get("offset", info["key_offset"])
            return
        # Any richer form ('key pos tr offset 0.2 0.2 compact ...') carries
        # options we cannot model; a cumulative re-emit would produce a
        # competing 'key' line. Keep the WHOLE original line as raw GLE
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
        """Scan the tokens after ``key`` into ``{pos, hei, nobox, offset}``.

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
        """Parse a ``dN ...`` dataset display command into a series entry."""
        d_name = toks[0].value.lower()
        attrs = self._scan_series_attrs(toks[1:])

        # File-vs-import classification decided later per data_file. First
        # figure out the data_file for the main dataset.
        if d_name not in datasets:
            # Unknown dataset ref -> passthrough (defensive).
            info["passthrough"].extend(self._dn_passthrough_lines(toks, raw_stmts))
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

        has_line = attrs["has_line"]
        has_marker = attrs["marker"] is not None
        is_errorbar = bool(attrs["err_refs"]) or bool(attrs["err_consts"])

        # Determine import vs reference for THIS data_file.
        is_import = self._is_import(data_file)

        if is_errorbar:
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
            self._build_file_series(info, data_file, xcol, ycol, attrs, has_line)
            return

        # Import series: load arrays.
        loaded = self._load_series(data_file, xcol, ycol, line_no=line_no)
        if loaded is None or loaded.get("error"):
            self._build_file_series(
                info,
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

        # markersize/linewidth are stored on the object model in their GLE-emit
        # form: markersize is the raw GLE ``msize`` value, linewidth is the
        # matplotlib-points value (writer converts pt->cm). msize is emitted
        # verbatim, so keep it raw. Default GLE msize when absent is 0.15.
        markersize = attrs["msize"] if attrs["msize"] is not None else 0.15
        linewidth = (
            linewidth_cm_to_pt(attrs["lwidth"]) if attrs["lwidth"] is not None else 1.0
        )
        linestyle = attrs["linestyle"] if has_line else "none"

        is_scatter = has_marker and not has_line
        entry = (ScatterSeries if is_scatter else LineSeries)(
            type="scatter" if is_scatter else "line",
            x=x,
            y=y,
            color=attrs["color"] or "BLUE",
            marker=attrs["marker"],
            markersize=markersize,
            linestyle=linestyle,
            linewidth=linewidth,
            label=attrs["label"],
            yaxis="y2" if attrs["y2axis"] else "y",
            offset=info["_dataset_offsets"].get(d_name, 0.0),
            data_file=data_file,
        )
        column_names = self._recovered_column_names(data_file, [xcol, ycol])
        if column_names is not None:
            entry["column_names"] = column_names
        if is_scatter:
            entry["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            info["scatters"].append(entry)
        else:
            entry["_draw_seq"] = info["_draw_seq_counter"]
            info["_draw_seq_counter"] += 1
            info["lines"].append(entry)
            smooth_flags.append(attrs["smooth"])

    def _scan_series_attrs(self, toks) -> dict:
        """Flat scan of dataset attribute tokens (order-tolerant)."""
        a = {
            "has_line": False,
            "smooth": False,
            "color": None,
            "lwidth": None,
            "lstyle": None,
            "linestyle": "-",
            "marker": None,
            "msize": None,
            "y2axis": False,
            "label": None,
            "err_refs": {},  # kind -> dataset name (err/errup/errdown/herr/herrleft/herrright)
            "err_consts": {},  # kind -> (value: float, is_percent: bool) for literals
            "errwidth": None,
            "herrwidth": None,
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
            if w == "smooth":
                a["smooth"] = True
                i += 1
                continue
            if w == "color" and i + 1 < m:
                val, nxt = _collect_color(toks, i + 1)
                a["color"] = val
                i = nxt
                continue
            if w == "lwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                a["lwidth"] = v
                i = nxt if v is not None else i + 2
                continue
            if w == "lstyle" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                if v is not None:
                    a["lstyle"] = int(v)
                    a["linestyle"] = LSTYLE_TO_MATPLOTLIB.get(int(v), "-")
                    i = nxt
                    continue
                i += 2
                continue
            if w == "marker" and i + 1 < m:
                a["marker"] = toks[i + 1].value
                i += 2
                continue
            if w == "msize" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                a["msize"] = v
                i = nxt if v is not None else i + 2
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
                val, nxt = _collect_value(toks, i + 1)
                if val is not None:
                    is_percent = nxt < m and toks[nxt].value == "%"
                    if is_percent:
                        nxt += 1
                    a["err_consts"][w] = (val, is_percent)
                    i = nxt
                    continue
                i += 2
                continue
            if w == "errwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                a["errwidth"] = v
                i = nxt if v is not None else i + 2
                continue
            if w == "herrwidth" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                a["herrwidth"] = v
                i = nxt if v is not None else i + 2
                continue
            if w == "y2axis":
                a["y2axis"] = True
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
            i += 1
        return a

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
            # File reference we won't load -> keep the ORIGINAL dN line raw.
            self._passthrough_original_dn(info, orig_toks, raw_stmts)
            self._note(
                ImportCategory.DATA,
                "constant error on an unresolved file reference; original "
                "'dN ... err' line kept as raw GLE",
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
        markersize = attrs["msize"] if attrs["msize"] is not None else 0.15
        linewidth = (
            linewidth_cm_to_pt(attrs["lwidth"]) if attrs["lwidth"] is not None else 1.0
        )
        # The writer emits ' line lwidth ...' when a linestyle is present with a
        # marker; a marker-only errorbar with no 'line' token has linestyle
        # 'none'. Recover linestyle from lstyle / presence of line.
        linestyle = attrs["linestyle"] if attrs["has_line"] else "none"

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
                    color=attrs["color"] or "BLUE",
                    marker=marker,
                    markersize=markersize,
                    label=attrs["label"],
                    capsize=gle_capsize,
                    yaxis="y2" if attrs["y2axis"] else "y",
                )
            )
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
            info["file_series"].append(
                FileSeries(
                    series_type="errorbar",
                    data_file=data_file,
                    x_col=xcol,
                    y_col=ycol,
                    yerr_col=yerr_col,
                    color=attrs["color"] or "BLUE",
                    marker=marker,
                    markersize=markersize,
                    label=attrs["label"],
                    capsize=gle_capsize,
                    yaxis="y2" if attrs["y2axis"] else "y",
                    data_error=(loaded or {}).get("error", "unresolved"),
                )
            )
            return

        def col_arr(c):
            return loaded.get(f"c{c}") if c is not None else None

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
            y_arr = loaded["y"]
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
            color=attrs["color"] or "BLUE",
            marker=marker,
            markersize=markersize,
            linestyle=linestyle,
            linewidth=linewidth,
            label=attrs["label"],
            capsize=stored_capsize,
            gle_capsize=gle_capsize,
            yaxis="y2" if attrs["y2axis"] else "y",
            offset=(
                info["_dataset_offsets"].get(orig_toks[0].value.lower(), 0.0)
                if orig_toks
                else 0.0
            ),
            data_file=data_file,
        )
        if not err_consts:
            # Column indices in the SAME order the writer emits them (x, y,
            # then y-error column(s) collapsed to one when symmetric i.e.
            # yerr_up_col == yerr_down_col, then x-error likewise) -- see
            # gleplot.writer.GLEWriter.add_errorbar. Constant/percentage
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
        info["errorbars"].append(entry)

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
        self, info, data_file, xcol, ycol, attrs, has_line, error=None
    ):
        markersize = attrs["msize"] if attrs["msize"] is not None else 0.15
        # Branch on has_line ALONE: a 'd1 line marker circle lwidth X' reference
        # is a line (carrying line/lwidth/linestyle) that ALSO has a marker --
        # not an errorbar. Losing the line/lwidth/linestyle by classifying it as
        # an errorbar (the old behavior) drops the whole styled line. Keep the
        # marker as an additional field so it survives on the model.
        if has_line:
            entry = FileSeries(
                series_type="line",
                data_file=data_file,
                x_col=xcol,
                y_col=ycol,
                color=attrs["color"] or "BLUE",
                linestyle=attrs["linestyle"],
                linewidth=(
                    linewidth_cm_to_pt(attrs["lwidth"])
                    if attrs["lwidth"] is not None
                    else 1.0
                ),
                label=attrs["label"],
                yaxis="y2" if attrs["y2axis"] else "y",
            )
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
                color=attrs["color"] or "BLUE",
                marker=attrs["marker"],
                markersize=markersize,
                label=attrs["label"],
                capsize=None,
                yaxis="y2" if attrs["y2axis"] else "y",
            )
        if error is not None:
            entry["data_error"] = error
        entry["_draw_seq"] = info["_draw_seq_counter"]
        info["_draw_seq_counter"] += 1
        info["file_series"].append(entry)

    # -- data loading ----------------------------------------------------

    # -- contour / heatmap recognition ----------------------------------

    def _scan_gleplot_sub_lines(self) -> set:
        """1-based line numbers spanned by ``sub gleplot_<name>`` definitions.

        gleplot emits self-contained palette / colorbar / contour-label subs
        (see :mod:`gleplot.palettes`). Their bodies use ``sub``/``if``/``return``
        etc.; they are dropped wherever they appear (like the metadata block) and
        regenerated canonically from the model on re-save, so they never leak
        into passthrough nor trip the programmatic-construct guard.
        """
        nums: set = set()
        in_sub = False
        for idx, line in enumerate(self.text.splitlines(), start=1):
            low = line.strip().lower()
            if not in_sub:
                if low.startswith("sub gleplot_"):
                    in_sub = True
                    nums.add(idx)
                continue
            nums.add(idx)
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

        # A fitz block is ours iff its generated .z feeds a recognized colormap
        # or a recognized contour block, AND its scattered points are readable.
        for zfile, (info, node) in raw_fitz.items():
            if zfile not in colormap_files and zfile not in self._contour_blocks:
                continue
            if self._read_points(info["points_file"]) is None:
                continue
            self._fitz_blocks[zfile] = info
            self._mark_block_consumed(node)

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
        expression, and no unrecognized options) but WITHOUT touching disk --
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
                _, nxt = _collect_value(toks, i + 1)
                i = nxt if nxt > i + 1 else i + 2
            elif w == "palette" and i + 1 < m:
                palette = toks[i + 1].value
                i += 2
            elif w == "interpolate" and i + 1 < m:
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
        (nx,ny from the ``from..to..step`` ranges) and optional ``ncontour``.
        ``zfile`` is the generated grid name (points base + ``.z``).
        """
        data_file = None
        xr = yr = None
        ncontour = None
        for sl in node.inner_lines:
            toks = _words_and_values(_first_statement_of(sl))
            if not toks:
                continue
            kw = toks[0].value.lower()
            if kw == "data" and len(toks) >= 2:
                data_file, _ = self._read_filename(toks, 1)
            elif kw in ("x", "y") and len(toks) >= 6:
                rng = self._parse_from_to_step(toks)
                if rng is not None:
                    if kw == "x":
                        xr = rng
                    else:
                        yr = rng
            elif kw == "ncontour" and len(toks) >= 2:
                n = _num(toks[1])
                if n is not None:
                    ncontour = int(n)
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
        }

    def _parse_contour_block(self, node: OpaqueBlock) -> Optional[dict]:
        """Parse a ``begin contour`` block matching gleplot's shape, or ``None``.

        Recovers the ``.z`` file it reads and the explicit ``values`` list
        (``None`` when a bare block using GLE's default 10 levels).
        """
        zfile = None
        levels = None
        for sl in node.inner_lines:
            toks = _words_and_values(_first_statement_of(sl))
            if not toks:
                continue
            kw = toks[0].value.lower()
            if kw == "data" and len(toks) >= 2:
                zfile, _ = self._read_filename(toks, 1)
            elif kw == "values":
                # Only the explicit ``values v1 v2 ...`` form is modeled;
                # ``values from a to b step s`` stays a foreign block.
                if len(toks) >= 2 and toks[1].value.lower() == "from":
                    return None
                vals: List[float] = []
                k = 1
                while k < len(toks):
                    v, nxt = _collect_value(toks, k)
                    if v is None:
                        k += 1
                        continue
                    vals.append(v)
                    k = nxt
                if vals:
                    levels = vals
        if zfile is None:
            return None
        return {"zfile": zfile, "levels": levels}

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
                i = nxt if v is not None else i + 2
            elif w == "zmax" and i + 1 < m:
                v, nxt = _collect_value(toks, i + 1)
                vmax = v
                i = nxt if v is not None else i + 2
            elif w == "palette" and i + 1 < m:
                palette = toks[i + 1].value
                i += 2
            elif w == "interpolate" and i + 1 < m:
                interpolation = toks[i + 1].value.lower()
                i += 2
            else:
                unknown = True
                i += 1

        # cmap resolution.
        if color:
            cmap = "rainbow"
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

        # A colormap of a FUNCTION expression (not a .z/.gz file) can't be
        # modeled -> passthrough.
        if not zfile.lower().endswith((".z", ".gz")):
            info["passthrough"].append(self._stmt_text(stmt))
            self._note(
                ImportCategory.STRUCTURE,
                "colormap of a function expression; kept as raw GLE",
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
            hm = HeatmapSeries(
                type="heatmap",
                source="points",
                z=None,
                x=pts[0],
                y=pts[1],
                zpts=pts[2],
                extent=list(fitz["extent"]),
                origin="lower",
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                interpolation="nearest" if interpolation == "nearest" else "bicubic",
                pixels=[int(px), int(py)],
                invert=invert,
                gridsize=list(fitz["gridsize"]),
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
            z, extent = grid
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
        color = attrs["color"] or "BLACK"
        linewidth = (
            linewidth_cm_to_pt(attrs["lwidth"]) if attrs["lwidth"] is not None else 1.0
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
                linewidth=linewidth,
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
            z, extent = grid
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
                linewidth=linewidth,
                linestyle=lstyle,
                clabel=False,
                clabel_fmt="fix 1",
                gridsize=None,
                ncontour=None,
                label=None,
                data_file=zfile,
            )
        info["contours"].append(ct)

    def _read_z_grid(self, filename) -> Optional[Tuple[np.ndarray, List[float]]]:
        """Read a ``.z`` grid sidecar -> (z ndarray (ny,nx), [x0,x1,y0,y1]).

        Returns ``None`` when the file cannot be resolved/parsed. The array is
        returned y-increasing (row 0 = ymin), matching GLE's ``.z`` convention;
        the recovered heatmap/contour therefore always uses ``origin='lower'``
        (a documented, rendering-neutral normalization).
        """
        text = self._read_sidecar_text(filename)
        if text is None:
            return None
        header = None
        values: List[float] = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.startswith("!"):
                if header is None:
                    header = s
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
        return z, [x0, x1, y0, y1]

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

    # -- post-graph colorbar / contour-label calls ----------------------

    def _consume_post_graph_calls(self, nodes, start, axes_info) -> int:
        """Consume ``gleplot_colorbar_v`` / ``gleplot_contour_labels`` calls.

        Each call is preceded by its own ``amove`` (``xg(xgmax)+S yg(ygmin)`` for
        the colorbar, ``0 0`` for the labels). Attaches the recovered colorbar
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
        # optional leading amove, then the sub call.
        amove_sep = None
        j = i
        st = self._as_statement(nodes[j]) if j < len(nodes) else None
        if st is not None and st.keyword == "amove":
            amove_sep = self._amove_colorbar_sep(_words_and_values(st))
            j += 1
        st = self._as_statement(nodes[j]) if j < len(nodes) else None
        if st is None:
            return None
        kw = st.keyword
        toks = _words_and_values(st)
        if kw == "gleplot_colorbar_v":
            self._apply_colorbar_call(toks, amove_sep, axes_info)
            return j + 1
        if kw == "gleplot_contour_labels":
            self._apply_clabel_call(toks, axes_info)
            return j + 1
        return None

    @staticmethod
    def _amove_colorbar_sep(toks) -> Optional[float]:
        """Recover ``S`` from ``amove xg(xgmax)+S yg(ygmin)`` (else None)."""
        text = " ".join(t.value for t in toks)
        m = re.search(r"xgmax\s*\)\s*\+\s*([0-9.eE+-]+)", text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    def _apply_colorbar_call(self, toks, sep, axes_info) -> None:
        args = self._named_args(toks[1:])
        heatmaps = axes_info.get("heatmaps") or []
        if not heatmaps:
            return
        hm = heatmaps[0]
        cb = {
            "label": args.get("label") or None,
            "format": args.get("format") or "fix 1",
            "width": _as_float(args.get("wd"), 0.5),
            "sep": sep if sep is not None else 0.3,
            "zmin": _as_float(args.get("zmin"), 0.0),
            "zmax": _as_float(args.get("zmax"), 1.0),
            "zstep": _as_float(args.get("zstep"), 0.0),
        }
        hm["colorbar"] = cb

    def _apply_clabel_call(self, toks, axes_info) -> None:
        args = self._named_args(toks[1:])
        fname = args.get("file")
        fmt = args.get("format") or "fix 1"
        contours = axes_info.get("contours") or []
        if not fname or not fname.endswith("-clabels.dat"):
            if contours:
                contours[0]["clabel"] = True
                contours[0]["clabel_fmt"] = fmt
            return
        base = fname[: -len("-clabels.dat")]
        for ct in contours:
            df = ct["data_file"]
            ct_base = (
                df[:-4]
                if df.endswith(".dat")
                else (df[:-2] if df.endswith(".z") else df)
            )
            if ct_base == base:
                ct["clabel"] = True
                ct["clabel_fmt"] = fmt
                return
        if contours:
            contours[0]["clabel"] = True
            contours[0]["clabel_fmt"] = fmt

    #: Recognized colorbar/clabel call argument names (used to delimit the
    #: unmodeled ``hi <expr>`` height argument).
    _CALL_ARG_NAMES = frozenset(
        {"zmin", "zmax", "zstep", "palette", "wd", "hi", "format", "label", "file"}
    )

    def _named_args(self, toks) -> dict:
        """Parse GLE named-argument call tokens ``name value name value ...``.

        String values (quoted) are unwrapped; numeric values are collected with
        the expression-tolerant :func:`_collect_value` (so signed numbers like
        ``-1`` are read whole). The ``hi yg(...)-yg(...)`` height argument is a
        multi-token expression that is not modeled (the colorbar always spans
        the graph height); it is skipped up to the next recognized arg name.
        """
        args: dict = {}
        i = 0
        m = len(toks)
        while i < m:
            name = toks[i].value.lower()
            i += 1
            if i >= m:
                break
            if name == "hi":
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
        try:
            cols = extract_columns(resolved.table, xcol, ycol, extra_cols or [])
        except ColumnExtractionError as exc:
            self._note(ImportCategory.DATA, str(exc), span)
            return {"error": str(exc)}
        return cols

    def _is_import(self, data_file) -> bool:
        cls = classify_data_file(self.gle_path, data_file, self._import_list)
        return cls == "import"

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
        vals = [_num(t) for t in toks[1:]]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            return (vals[0], vals[1])
        return None

    def _consume_text_cluster(self, nodes, start) -> Tuple[List[dict], int]:
        """Greedily match the writer's deferred-text pattern after end graph.

        Pattern per text (every ``set`` is optional, in any subset, in order):
            [set hei H]
            [set color C]
            [set just J]
            amove xg(X) yg(Y)
            write "T"

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
                if just in ("left", "center", "right"):
                    self._text_just = just
                i += 1
                continue
            break

        # 'amove xg(X) yg(Y)' -- mandatory: this is what makes the run of
        # 'set' statements above a text cluster rather than unrelated
        # passthrough. If absent, nothing was consumed as a text cluster (any
        # 'set' statements walked above are left for the caller/passthrough
        # by returning the ORIGINAL start index).
        i = self._skip_blanks(nodes, i)
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "amove":
            return start, None
        x, y = self._parse_xg_yg(_words_and_values(stmt))
        if x is None or y is None:
            return start, None
        i += 1

        # 'write "T"' -- mandatory (a blank line may separate the amove from
        # its write in a hand-edited file; tolerate it the same way).
        i = self._skip_blanks(nodes, i)
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "write":
            return start, None
        toks = _words_and_values(stmt)
        text_str = self._first_string(toks)
        if text_str is None:
            return start, None
        i += 1

        return i, TextAnnotation(
            x=x,
            y=y,
            text=text_str,
            color=self._text_color,
            fontsize=self._text_fontsize,
            ha=self._text_just,
            va="center",
            box_color=None,
        )

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

    def _more_graphs_after(self, nodes, i) -> bool:
        for k in range(i + 1, len(nodes)):
            if isinstance(nodes[k], GraphBlock):
                return True
            if self._match_amove(nodes[k]) is not None:
                return True
        return False

    # -- axes assembly ---------------------------------------------------

    def _assemble_axes(self, fig, parsed_axes, sharex, sharey):
        n = len(parsed_axes)
        positions = self._infer_positions(parsed_axes)

        for idx, info in enumerate(parsed_axes):
            rows, cols, one_based = positions[idx]
            ax = Axes(fig, (rows, cols, one_based))
            self._populate_axes(ax, info)
            fig._apply_shared_axes_flags(ax)
            # Restore explicit visibility flags recovered from GLE (override
            # the derived ones where the GLE said something different).
            self._restore_visibility_flags(ax, info)
            fig.axes_list.append(ax)

        self._apply_geometry(fig, parsed_axes)

        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

    # -- graph geometry --------------------------------------------------

    def _apply_geometry(self, fig, parsed_axes) -> None:
        """Map each graph block's recovered geometry onto the axes model.

        Three outcomes per axes, in order of preference (SPEC 3.3 / 8.1.3):

        * **modelled** -- the invertible triple ``amove x y`` + ``size w h`` +
          ``scale 1 1`` becomes :attr:`Axes.placement`, a frame rect in page
          cm that the writer re-emits as the same three statements;
        * **auto** -- no geometry at all, or exactly ``scale auto`` (the
          writer's own default emission): nothing is stored, placement stays
          ``None`` = "GLE decides" until a calibration render resolves it;
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
        reserved = fig._axes_colorbar_reserved_cm(ax)
        if reserved <= 0:
            return False
        from ..writer import GLEWriter

        width_cm = inches_to_cm(fig.figsize[0])
        height_cm = inches_to_cm(fig.figsize[1])
        graph_w = max(width_cm - reserved, width_cm * 0.3)
        expected = (
            f"    size {GLEWriter._format_number(graph_w)} "
            f"{GLEWriter._format_number(height_cm)}"
        )
        return stmts[0].raw == expected

    def _infer_positions(self, parsed_axes) -> List[Tuple[int, int, int]]:
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

        xs = [a[0] for a in amoves]
        ys = [a[1] for a in amoves]
        col_clusters = _cluster(xs)
        row_clusters = _cluster(ys, reverse=True)  # top row = highest y
        rows = len(row_clusters)
        cols = len(col_clusters)
        if rows * cols != n:
            self._note(
                ImportCategory.LAYOUT,
                "amove positions do not form a clean grid; using n x 1 fallback",
                arrangement_span,
            )
            return [(n, 1, k + 1) for k in range(n)]

        positions = []
        for a in amoves:
            col = _which_cluster(a[0], col_clusters)
            row = _which_cluster(a[1], row_clusters, reverse=True)
            one_based = row * cols + col + 1
            positions.append((rows, cols, one_based))
        return positions

    def _populate_axes(self, ax, info):
        ax.title_text = info["title"] or ""
        ax.xlabel_text = info["xlabel"] or ""
        ax.ylabel_text = info["ylabel"] or ""
        ax.y2label_text = info["y2label"] or ""
        ax.xscale = "log" if info["xlog"] else "linear"
        ax.yscale = "log" if info["ylog"] else "linear"
        ax.y2scale = "log" if info["y2log"] else "linear"
        # ``negate`` is GLE's spelling of an inverted axis; the model spells
        # the same thing as a descending limit pair, which is what the writer
        # turns back into ``negate`` (see GLEWriter._axis_direction).
        ax.xmin, ax.xmax = _oriented(info["xmin"], info["xmax"], info["xnegate"])
        ax.ymin, ax.ymax = _oriented(info["ymin"], info["ymax"], info["ynegate"])
        ax.y2min, ax.y2max = _oriented(info["y2min"], info["y2max"], info["y2negate"])
        ax.xplaces = info["xplaces"]
        ax.yplaces = info["yplaces"]
        ax.xnames = info["xnames"]
        ax.ynames = info["ynames"]
        self._populate_axes_styling(ax, info)

        ax.lines = info["lines"]
        ax.scatters = info["scatters"]
        ax.bars = info["bars"]
        ax.fills = info["fills"]
        ax.errorbars = info["errorbars"]
        ax.file_series = info["file_series"]
        ax.texts = info["texts"]
        ax.heatmaps = info["heatmaps"]
        ax.contours = info["contours"]
        ax.passthrough = info["passthrough"]

        # A series whose sidecar had no real header row (hand-written .dat,
        # or a headerless import from an older gleplot version) has no
        # 'column_names' recovered above. Regenerate the same stable
        # defaults Axes.from_dict falls back to for pre-Track-E3 projects,
        # so the next save still gets a named header row.
        for attr in ("lines", "scatters", "bars", "fills", "errorbars"):
            for item in getattr(ax, attr):
                if "column_names" not in item:
                    defaults = item.default_column_names()
                    if defaults is not None:
                        item["column_names"] = defaults

        # Legend tri-state recovery.
        labels_present = self._labels_present(info)
        if info["key_off"]:
            ax.legend_on = False
        elif info["key_pos"] is not None:
            pos_short = info["key_pos"]
            ax.legend_pos = KEY_POSITIONS_SHORT_TO_LONG.get(pos_short, pos_short)
            # 'key pos P' + labels -> auto (None); + no labels -> True.
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
        for prefix in ("x", "y", "y2"):
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
        for prefix in ("x", "y"):
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
        for group in ("lines", "scatters", "bars", "errorbars", "file_series"):
            for s in info[group]:
                if s.get("label"):
                    return True
        return False

    def _restore_visibility_flags(self, ax, info):
        """Reproduce the writer's emission conditions for tick visibility.

        The writer emits:
          - ``xlabels off``          when ``show_xticks`` is False
          - ``ylabels off``          when ``show_yticks`` is False
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

    def _apply_smooth(self, fig, graph_cfg, smooth_flags):
        if not smooth_flags:
            # No line datasets: leave the default (False). The writer emits
            # nothing that depends on it, so byte-identity is unaffected.
            return
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
                "mixed per-series smooth flags; applying smooth to all "
                "line datasets on re-save",
            )

    # -- data-file naming state -----------------------------------------

    def _finalize_data_state(self, fig):
        """Set data_prefix / counters / used-files so re-save reuses names."""
        used = set()
        sidecars = set()
        for ax in fig.axes_list:
            for s in ax.lines + ax.scatters + ax.bars + ax.fills + ax.errorbars:
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
        prefixes = {}
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
        ``.figure`` is the reconstructed model; ``.warnings`` lists recovery
        notes (see the module "Warnings taxonomy").
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

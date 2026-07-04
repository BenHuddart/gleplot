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
3. **subplots_adjust is lost.** The multi-subplot writer bakes
   ``subplots_adjust`` overrides into ``amove``/``size`` cm geometry that is
   not uniquely invertible, so recovered multi-subplot figures come back with
   an empty ``_subplot_adjust``. The *layout* still round-trips byte-identically
   because the recovered ``figsize`` + grid reproduce the same geometry only
   when the original used default spacing; a figure that used a non-default
   ``subplots_adjust`` re-saves with the DEFAULT spacing (documented layout
   loss -- see the fixed-point exceptions in the module report).
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
   ``smooth_curves=True`` (the default) and warns; re-save then applies smooth
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

Tolerances for hand-written input
---------------------------------
Attribute order within a dataset command may vary; axis lines may be given
cumulatively (multiple ``xaxis`` lines merge); numbers may be expressions
(``2*pi``) resolved via :func:`~gleplot.parser.expr.eval_gle_number`; keywords
are case-insensitive; single-quoted strings and ``;``-joined statements are
accepted; British ``GREY`` colors are accepted. Anything not recognized is
preserved verbatim in the appropriate passthrough bucket (header / trailer /
axes) so it re-emits unchanged.

Warnings taxonomy
-----------------
Every recovered ambiguity or loss appends a human-readable string to
``RecognizedFigure.warnings``:

- ``"metadata: ..."``            -- forwarded from ``parse_metadata``.
- ``"structure: ..."``          -- forwarded from the syntax parser.
- ``"data: ..."``               -- a ``data`` reference could not be loaded /
                                   a column could not be extracted (broken
                                   series; emitted verbatim on re-save).
- ``"legend: ..."``             -- a hand-written implicit legend was assumed.
- ``"smooth: ..."``             -- mixed per-series smooth flags.
- ``"layout: ..."``             -- multi-graph grid could not be inferred
                                   cleanly (n x 1 fallback) or share flags
                                   were guessed.
- ``"programmatic: ..."``       -- the file uses GLE programming constructs
                                   (sub/if/for/...); editing may restructure
                                   them (advisory; parse unchanged).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from ..axes import Axes
from ..config import GLEGraphConfig, GLEMarkerConfig, GLEStyleConfig
from ..figure import Figure
from . import metadata as _metadata
from .expr import eval_gle_number
from .lexer import Token, TokenType
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
)
from .units import (
    capsize_cm_to_pt,
    cm_to_inches,
    fontsize_cm_to_pt,
    linewidth_cm_to_pt,
)
from ..dataio import (
    ColumnExtractionError,
    classify_data_file,
    extract_columns,
    resolve_data_reference,
)


__all__ = ["RecognizedFigure", "parse_gle_figure"]


_DATASET_RE = re.compile(r"^d\d+$", re.IGNORECASE)


@dataclass
class RecognizedFigure:
    """Result of :func:`parse_gle_figure`.

    Attributes
    ----------
    figure : Figure
        The reconstructed object model.
    warnings : list of str
        Human-readable recovery notes (see the module "Warnings taxonomy").
    """

    figure: Figure
    warnings: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Token-stream helpers
# --------------------------------------------------------------------------- #

def _words_and_values(stmt: Statement) -> List[Token]:
    """Tokens of a statement, dropping comments."""
    return [t for t in stmt.tokens if t.type is not TokenType.COMMENT]


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


# --------------------------------------------------------------------------- #
# The recognizer
# --------------------------------------------------------------------------- #

class _Recognizer:
    """Stateful recognizer for one document. See :func:`parse_gle_figure`."""

    def __init__(self, text: str, gle_path: Path):
        self.text = text
        self.gle_path = gle_path
        self.warnings: List[str] = []
        # dataset name (lower) -> (data_file, xcol_1based, ycol_1based)
        self._datasets: Dict[str, Tuple[str, int, int]] = {}
        # resolved-table cache per data_file name
        self._table_cache: Dict[str, object] = {}
        self._import_list: Optional[List[str]] = None
        self._used_prefix_indices: Dict[str, int] = {}  # prefix -> max index+1
        self._used_data_files: set = set()

    # -- public driver ---------------------------------------------------

    def run(self) -> RecognizedFigure:
        doc = parse_gle_source(self.text)
        for w in doc.warnings:
            self.warnings.append(f"structure: {w}")

        # 1-based line numbers spanned by the '! gleplot' metadata block; these
        # lines carry parsed values and must be dropped wherever they appear
        # (including inside a graph body) so they never leak into passthrough
        # and re-emit as a stale duplicate block.
        self._meta_lines = self._metadata_line_numbers()

        # Guard: files using GLE programming constructs are not safe to edit.
        self._check_programmatic_constructs(doc.nodes)

        # Metadata block (parsed from the whole file, tolerantly).
        meta, meta_warnings = _metadata.parse_metadata(self.text.splitlines())
        for w in meta_warnings:
            self.warnings.append(f"metadata: {w}")
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

        (figsize, font, fontsize, passthrough_header) = self._parse_preamble(
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

        n = len(nodes)
        while i < n:
            node = nodes[i]
            if isinstance(node, GraphBlock):
                axes_info = self._parse_graph_block(node, marker_cfg, smooth_flags)
                axes_info["amove"] = pending_amove
                pending_amove = None
                # Greedily consume deferred text cluster that follows.
                texts, consumed = self._consume_text_cluster(nodes, i + 1)
                axes_info["texts"] = texts
                parsed_axes.append(axes_info)
                i = consumed
                continue

            # Non-graph node between/after graphs.
            amove = self._match_amove(node)
            if amove is not None:
                pending_amove = amove
                i += 1
                continue

            # Blank line directly separating subplots: skip silently only when
            # between graphs (writer emits a blank between subplots). Otherwise
            # it is trailer content.
            if isinstance(node, BlankOrComment) and self._more_graphs_after(nodes, i):
                i += 1
                continue

            # Anything else after the graphs -> trailer passthrough.
            trailer.extend(self._raw_lines(node))
            i += 1

        fig.passthrough_trailer = trailer

        # --- Assemble axes into the figure. ---
        self._assemble_axes(fig, parsed_axes, sharex, sharey)

        # --- smooth handling (global). ---
        self._apply_smooth(fig, graph_cfg, smooth_flags)

        # --- data-file naming state for byte-identical re-save. ---
        self._finalize_data_state(fig)

        return RecognizedFigure(figure=fig, warnings=self.warnings)

    # -- programmatic-construct guard -----------------------------------

    #: Top-level statement keywords that mark a GLE *programmatic* file (control
    #: flow / subroutines). The syntax parser has no awareness of these, so a
    #: graph inside such a construct parses as a top-level graph and editing it
    #: would restructure the file. We only *warn*; parse behavior is unchanged.
    _PROGRAMMATIC_KEYWORDS = frozenset({
        "sub", "if", "for", "while", "until", "next", "else", "return",
    })

    #: Opaque wrapper block types that establish a coordinate transform. A
    #: graph nested inside one of these is preserved wholesale as raw GLE.
    _TRANSFORM_WRAPPERS = frozenset({"translate", "scale", "rotate", "origin"})

    def _warn_graph_in_transform(self, nodes) -> None:
        for node in nodes:
            if not isinstance(node, OpaqueBlock):
                continue
            if node.block_type not in self._TRANSFORM_WRAPPERS:
                continue
            for sl in node.inner_lines:
                stripped = sl.text.strip().lower()
                if stripped.startswith("begin graph"):
                    self.warnings.append(
                        "structure: graph inside begin translate/scale is "
                        "preserved as raw GLE, not editable"
                    )
                    break

    def _check_programmatic_constructs(self, nodes) -> None:
        for node in nodes:
            if not isinstance(node, Statement):
                continue
            kw = node.keyword
            if kw is not None and kw in self._PROGRAMMATIC_KEYWORDS:
                self.warnings.append(
                    "programmatic: file contains GLE programming constructs "
                    "(sub/if/for); opening for editing may restructure them -- "
                    "consider read-only preview"
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

    def _parse_preamble(self, pre_nodes) -> Tuple[Tuple[float, float], str, float, List[str]]:
        figsize = (8.0, 6.0)
        font = ""
        fontsize = 12.0
        passthrough: List[str] = []

        # Track which lines belong to the metadata block so we drop them.
        meta_line_nos = self._meta_lines

        for node in pre_nodes:
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
            "size_cm": None,        # (w, h) if explicit 'size' present
            "scale_mode": None,     # 'auto' | 'fixed' | None
            "title": None,
            "xlabel": None,
            "ylabel": None,
            "y2label": None,
            "xmin": None, "xmax": None, "xlog": False,
            "ymin": None, "ymax": None, "ylog": False,
            "y2min": None, "y2max": None, "y2log": False,
            "xlabels_off": False, "ylabels_off": False,
            "nofirst_x": False, "nolast_x": False,
            "nofirst_y": False, "nolast_y": False,
            "key_pos": None,        # short-form position or None
            "key_off": False,
            "lines": [], "scatters": [], "bars": [], "fills": [], "errorbars": [],
            "file_series": [],
            "passthrough": [],
            "series_order": [],     # to preserve ordering info if needed
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
        }

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

        for child in block.body:
            if isinstance(child, Statement):
                if self._skip_meta_stmt(child):
                    continue
                kw = child.keyword
                if kw == "data":
                    self._parse_data_command(_words_and_values(child), datasets)
                    continue
                if kw is not None and _DATASET_RE.match(kw):
                    name = kw
                    if name not in merged_attr_toks:
                        merged_attr_toks[name] = []
                        dataset_order.append(name)
                    merged_attr_toks[name].extend(_words_and_values(child)[1:])
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
            if kw is not None and _DATASET_RE.match(kw):
                name = kw
                if name in emitted:
                    continue
                attr_toks = merged_attr_toks.get(name, [])
                if name in info["_key_suppress_datasets"] and self._is_bare_key_suppression(attr_toks):
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
                    name, merged, datasets, info, marker_cfg, smooth_flags
                )
                continue

            self._dispatch_graph_statement(child, info, datasets, marker_cfg, smooth_flags)

        return info

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

    def _build_series_from_attrs(self, name, merged_toks, datasets, info,
                                 marker_cfg, smooth_flags):
        """Build one series from a dataset's merged attribute tokens."""
        self._parse_series_command(merged_toks, datasets, info, marker_cfg, smooth_flags)

    def _dispatch_graph_statement(self, stmt, info, datasets, marker_cfg, smooth_flags):
        kw = stmt.keyword
        toks = _words_and_values(stmt)
        if not toks:
            return

        if kw == "size":
            vals = [_num(t) for t in toks[1:] if _num(t) is not None]
            if len(vals) >= 2:
                info["size_cm"] = (vals[0], vals[1])
            return
        if kw == "scale":
            # 'scale auto' or 'scale 1 1'
            rest = [t.value.lower() for t in toks[1:]]
            if rest and rest[0] == "auto":
                info["scale_mode"] = "auto"
            else:
                info["scale_mode"] = "fixed"
            return
        if kw == "fullsize":
            info["scale_mode"] = "fullsize"
            return
        if kw == "title":
            if self._title_has_unsupported_options(toks):
                # 'title "T" hei 0.6 font roman' -- trailing modifiers cannot be
                # represented on the model and a cumulative re-emit would produce
                # a competing 'title' line. Keep the WHOLE original line as raw
                # GLE (title_text stays unset) and warn.
                info["passthrough"].append(self._stmt_text(stmt))
                self.warnings.append(
                    "structure: title has unsupported options; kept as raw GLE, "
                    "not editable"
                )
            else:
                info["title"] = self._first_string(toks)
            return
        if kw == "xtitle":
            info["xlabel"] = self._first_string(toks)
            return
        if kw == "ytitle":
            info["ylabel"] = self._first_string(toks)
            return
        if kw == "y2title":
            info["y2label"] = self._first_string(toks)
            return
        if kw in ("xaxis", "yaxis", "y2axis"):
            self._parse_axis_line(kw, toks, info, stmt)
            return
        if kw in ("xlabels", "ylabels"):
            # 'xlabels off'
            if any(t.value.lower() == "off" for t in toks[1:]):
                info["xlabels_off" if kw == "xlabels" else "ylabels_off"] = True
            else:
                info["passthrough"].append(self._stmt_text(stmt))
            return
        # NOTE: 'data' and 'dN' statements are handled by the two-pass driver
        # in _parse_graph_block, not here.
        if kw == "bar":
            self._parse_bar_command(toks, datasets, info)
            return
        if kw == "fill":
            self._parse_fill_command(toks, datasets, info)
            return
        if kw == "key":
            self._parse_key_command(toks, info, stmt)
            return

        # Unrecognized statement inside a graph block -> axes passthrough.
        info["passthrough"].append(self._stmt_text(stmt))

    # -- axis line parsing ----------------------------------------------

    def _parse_axis_line(self, kw, toks, info, stmt=None):
        prefix = {"xaxis": "x", "yaxis": "y", "y2axis": "y2"}[kw]
        remainder: List[Token] = []
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
            if w == "nofirst":
                info[f"nofirst_{prefix}"] = True
                i += 1
                continue
            if w == "nolast":
                info[f"nolast_{prefix}"] = True
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

        if remainder:
            rendered = self._render_remainder(remainder, stmt)
            info["passthrough"].append(f"    {kw} {rendered}")
            self.warnings.append(
                f"structure: unrecognized {kw} options ({rendered}) preserved as "
                "a supplementary axis line (cumulative); not editable"
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

    # -- data command ----------------------------------------------------

    def _parse_data_command(self, toks, datasets):
        """``data FILE d1=c1,c2 d2=c1,c3 ...`` -> register datasets.

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
            return
        data_file = self._token_filename(toks[1])
        m = len(toks)

        # Collect dataset clauses in the order given: (name, explicit_cols|None).
        given: List[Tuple[str, Optional[Tuple[int, int]]]] = []
        i = 2
        while i < m:
            name_tok = toks[i]
            if name_tok.type is not TokenType.WORD or not _DATASET_RE.match(name_tok.value):
                i += 1
                continue
            name = name_tok.value.lower()
            if i + 1 < m and toks[i + 1].value == "=":
                cols = []
                j = i + 2
                while j < m:
                    t = toks[j]
                    if t.type is TokenType.WORD and t.value.lower().startswith("c") and t.value[1:].isdigit():
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
                self.warnings.append(
                    f"data: dataset {name} redefined by a later 'data' command; "
                    "using the last definition"
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
                self.warnings.append(
                    f"data: '{data_file}' could not be resolved; auto column "
                    "mapping (data with no dN clauses) skipped"
                )
                return
            if ncols <= 1:
                self._register_dataset("d1", data_file, 0, 1, datasets)
            else:
                for k in range(ncols - 1):
                    self._register_dataset(
                        f"d{k + 1}", data_file, 1, k + 2, datasets
                    )
            return

        # Explicit and/or positional clauses.
        for pos, (name, cols) in enumerate(given):
            if cols is not None:
                self._register_dataset(name, data_file, cols[0], cols[1], datasets)
            else:
                # Positional: y column follows GLE's position-based assignment.
                ycol = pos + cy_first
                self._register_dataset(name, data_file, cx, ycol, datasets)

    def _register_dataset(self, name, data_file, xcol, ycol, datasets):
        datasets[name] = (data_file, xcol, ycol)
        self._datasets[name] = (data_file, xcol, ycol)

    @staticmethod
    def _token_filename(tok) -> str:
        """Filename from a data-command token: unwrap STRING quotes."""
        if tok.type is TokenType.STRING:
            return _string_value(tok)
        return tok.value

    def _file_column_count(self, data_file) -> Optional[int]:
        """Number of columns in the resolved data file, or None if unresolved."""
        resolved = self._resolve_table(data_file)
        if resolved.error is not None or resolved.table is None:
            return None
        return resolved.table.n_cols

    # -- bar / fill ------------------------------------------------------

    def _parse_bar_command(self, toks, datasets, info):
        """``bar dN fill COLOR``"""
        d_name = None
        color = "RED"
        i = 1
        m = len(toks)
        while i < m:
            w = toks[i].value
            wl = w.lower()
            if _DATASET_RE.match(wl):
                d_name = wl
            elif wl == "fill" and i + 1 < m:
                color = toks[i + 1].value
                i += 2
                continue
            i += 1
        if d_name is None or d_name not in datasets:
            info["passthrough"].append("    " + " ".join(t.value for t in toks))
            return
        info["_key_suppress_datasets"].add(d_name)
        data_file, xcol, ycol = datasets[d_name]
        loaded = self._load_series(data_file, xcol, ycol)
        entry = {
            "colors": None,
            "label": None,
            "data_file": data_file,
        }
        if loaded is None or loaded.get("error"):
            # Broken data -> represent as file_series-style reference w/ error.
            info["file_series"].append({
                "series_type": "bar",
                "data_file": data_file,
                "x_col": xcol, "y_col": ycol,
                "color": color,
                "data_error": (loaded or {}).get("error", "unresolved"),
            })
            return
        x = loaded["x"]
        height = loaded["y"]
        entry["x"] = x
        entry["height"] = height
        entry["colors"] = [color] * len(height)
        column_names = self._recovered_column_names(data_file, [xcol, ycol])
        if column_names is not None:
            entry["column_names"] = column_names
        info["bars"].append(entry)

    def _parse_fill_command(self, toks, datasets, info):
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
                color = toks[i + 1].value
                i += 2
                continue
            i += 1
        if len(d_names) < 2 or d_names[0] not in datasets or d_names[1] not in datasets:
            info["passthrough"].append("    " + " ".join(t.value for t in toks))
            return
        info["_key_suppress_datasets"].add(d_names[0])
        info["_key_suppress_datasets"].add(d_names[1])
        f1, xc1, yc1 = datasets[d_names[0]]
        f2, xc2, yc2 = datasets[d_names[1]]
        # fill data file has c1=x, c2=y1, c3=y2. d1=c1,c2 ; d2=c1,c3.
        loaded = self._load_series(f1, xc1, yc1, extra_cols=[yc2])
        if loaded is None or loaded.get("error"):
            info["file_series"].append({
                "series_type": "fill",
                "data_file": f1,
                "x_col": xc1, "y1_col": yc1, "y2_col": yc2,
                "color": color,
                "data_error": (loaded or {}).get("error", "unresolved"),
            })
            return
        x = loaded["x"]
        y1 = loaded["y"]
        y2 = loaded.get(f"c{yc2}")
        fill_entry = {
            "x": x, "y1": y1, "y2": y2,
            "color": color, "alpha": 0.3, "label": None,
            "data_file": f1,
        }
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
        # Exactly 'key pos P' -> recognized.
        if len(rest) == 2 and rest[0] == "pos":
            info["key_pos"] = rest[1]
            return
        # Any richer form ('key pos tr hei 0.3 nobox offset ...') carries options
        # we cannot model; a cumulative re-emit would produce a competing 'key'
        # line. Keep the WHOLE original line as raw GLE (legend untouched) and
        # warn.
        line = self._stmt_text(stmt) if stmt is not None else (
            "    " + " ".join(t.value for t in toks)
        )
        info["passthrough"].append(line)
        self.warnings.append(
            "structure: key has unsupported options; kept as raw GLE, "
            "not editable"
        )

    # -- series command --------------------------------------------------

    def _parse_series_command(self, toks, datasets, info, marker_cfg, smooth_flags):
        """Parse a ``dN ...`` dataset display command into a series entry."""
        d_name = toks[0].value.lower()
        attrs = self._scan_series_attrs(toks[1:])

        # File-vs-import classification decided later per data_file. First
        # figure out the data_file for the main dataset.
        if d_name not in datasets:
            # Unknown dataset ref -> passthrough (defensive).
            info["passthrough"].append("    " + " ".join(t.value for t in toks))
            return
        data_file, xcol, ycol = datasets[d_name]

        has_line = attrs["has_line"]
        has_marker = attrs["marker"] is not None
        is_errorbar = bool(attrs["err_refs"]) or bool(attrs["err_consts"])

        # Determine import vs reference for THIS data_file.
        is_import = self._is_import(data_file)

        if is_errorbar:
            self._build_errorbar(
                info, datasets, data_file, xcol, ycol, attrs, is_import,
                orig_toks=toks,
            )
            return

        if not is_import:
            self._build_file_series(info, data_file, xcol, ycol, attrs, has_line)
            return

        # Import series: load arrays.
        loaded = self._load_series(data_file, xcol, ycol)
        if loaded is None or loaded.get("error"):
            self._build_file_series(
                info, data_file, xcol, ycol, attrs, has_line,
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

        entry = {
            "type": "scatter" if (has_marker and not has_line) else "line",
            "x": x, "y": y,
            "color": attrs["color"] or "BLUE",
            "marker": attrs["marker"],
            "markersize": markersize,
            "linestyle": linestyle,
            "linewidth": linewidth,
            "label": attrs["label"],
            "yaxis": "y2" if attrs["y2axis"] else "y",
            "data_file": data_file,
        }
        column_names = self._recovered_column_names(data_file, [xcol, ycol])
        if column_names is not None:
            entry["column_names"] = column_names
        if has_marker and not has_line:
            info["scatters"].append(entry)
        else:
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
            "err_refs": {},   # kind -> dataset name (err/errup/errdown/herr/herrleft/herrright)
            "err_consts": {}, # kind -> (value: float, is_percent: bool) for literals
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
                a["color"] = toks[i + 1].value
                i += 2
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
            if w in ("err", "errup", "errdown", "herr", "herrleft", "herrright") and i + 1 < m:
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

    def _build_errorbar(self, info, datasets, data_file, xcol, ycol, attrs,
                        is_import, orig_toks=None):
        """Reconstruct an errorbar entry, matching Axes.errorbar's dict schema."""
        # Resolve error column indices from referenced datasets.
        err = attrs["err_refs"]
        err_consts = attrs["err_consts"]

        # Constant / percentage errors ('err 0.5', 'err 10%') carry no data
        # column; GLE synthesizes the error at draw time. We convert them to a
        # concrete data column on save. This requires the y (and, for herr, x)
        # arrays, so it only works when the referencing series can be loaded.
        if err_consts and (not is_import):
            # File reference we won't load -> keep the ORIGINAL dN line raw.
            self._passthrough_original_dn(info, orig_toks)
            self.warnings.append(
                "data: constant error on an unresolved file reference; original "
                "'dN ... err' line kept as raw GLE"
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
        cap_cm = attrs["errwidth"] if attrs["errwidth"] is not None else attrs["herrwidth"]
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
            info["file_series"].append({
                "series_type": "errorbar",
                "data_file": data_file,
                "x_col": xcol, "y_col": ycol,
                "yerr_col": yerr_col,
                "color": attrs["color"] or "BLUE",
                "marker": marker,
                "markersize": markersize,
                "label": attrs["label"],
                "capsize": gle_capsize,
                "yaxis": "y2" if attrs["y2axis"] else "y",
            })
            return

        extra = [c for c in (yerr_up_col, yerr_down_col, xerr_left_col, xerr_right_col)
                 if c is not None]
        loaded = self._load_series(data_file, xcol, ycol, extra_cols=extra)
        if loaded is None or loaded.get("error"):
            if err_consts:
                # Cannot synthesize a constant-error column without the y data.
                self._passthrough_original_dn(info, orig_toks)
                self.warnings.append(
                    "data: constant error but the dataset could not be loaded; "
                    "original 'dN ... err' line kept as raw GLE"
                )
                return
            yerr_col = yerr_up_col if yerr_up_col is not None else None
            info["file_series"].append({
                "series_type": "errorbar",
                "data_file": data_file,
                "x_col": xcol, "y_col": ycol,
                "yerr_col": yerr_col,
                "color": attrs["color"] or "BLUE",
                "marker": marker,
                "markersize": markersize,
                "label": attrs["label"],
                "capsize": gle_capsize,
                "yaxis": "y2" if attrs["y2axis"] else "y",
                "data_error": (loaded or {}).get("error", "unresolved"),
            })
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
            self.warnings.append(
                "data: constant error expression converted to a data column on "
                "save"
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

        entry = {
            "type": "errorbar",
            "x": loaded["x"], "y": loaded["y"],
            "yerr_up": yerr_up, "yerr_down": yerr_down,
            "xerr_left": xerr_left, "xerr_right": xerr_right,
            "color": attrs["color"] or "BLUE",
            "marker": marker,
            "markersize": markersize,
            "linestyle": linestyle,
            "linewidth": linewidth,
            "label": attrs["label"],
            "capsize": stored_capsize,
            "gle_capsize": gle_capsize,
            "yaxis": "y2" if attrs["y2axis"] else "y",
            "data_file": data_file,
        }
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
        info["errorbars"].append(entry)

    def _passthrough_original_dn(self, info, orig_toks):
        """Keep a dataset display line as raw GLE in axes passthrough.

        Used when a ``dN ... err <literal>`` cannot be converted (broken /
        unresolved data): rather than silently dropping the error bars we
        re-emit the original line verbatim so GLE still draws it.
        """
        if not orig_toks:
            return
        rendered = " ".join(self._token_text(t) for t in orig_toks)
        info["passthrough"].append("    " + rendered)

    def _build_file_series(self, info, data_file, xcol, ycol, attrs, has_line, error=None):
        markersize = attrs["msize"] if attrs["msize"] is not None else 0.15
        # Branch on has_line ALONE: a 'd1 line marker circle lwidth X' reference
        # is a line (carrying line/lwidth/linestyle) that ALSO has a marker --
        # not an errorbar. Losing the line/lwidth/linestyle by classifying it as
        # an errorbar (the old behavior) drops the whole styled line. Keep the
        # marker as an additional field so it survives on the model.
        if has_line:
            entry = {
                "series_type": "line",
                "data_file": data_file,
                "x_col": xcol, "y_col": ycol,
                "color": attrs["color"] or "BLUE",
                "linestyle": attrs["linestyle"],
                "linewidth": (
                    linewidth_cm_to_pt(attrs["lwidth"]) if attrs["lwidth"] is not None else 1.0
                ),
                "label": attrs["label"],
                "yaxis": "y2" if attrs["y2axis"] else "y",
            }
            if attrs["marker"] is not None:
                entry["marker"] = attrs["marker"]
                entry["markersize"] = markersize
        else:
            # Marker-only (or bare) reference -> errorbar-style entry (which the
            # writer emits as a marker-only dataset).
            entry = {
                "series_type": "errorbar",
                "data_file": data_file,
                "x_col": xcol, "y_col": ycol,
                "yerr_col": None,
                "color": attrs["color"] or "BLUE",
                "marker": attrs["marker"],
                "markersize": markersize,
                "label": attrs["label"],
                "capsize": None,
                "yaxis": "y2" if attrs["y2axis"] else "y",
            }
        if error is not None:
            entry["data_error"] = error
        info["file_series"].append(entry)

    # -- data loading ----------------------------------------------------

    def _resolve_table(self, data_file):
        if data_file in self._table_cache:
            return self._table_cache[data_file]
        resolved = resolve_data_reference(self.gle_path, data_file)
        self._table_cache[data_file] = resolved
        return resolved

    def _load_series(self, data_file, xcol, ycol, extra_cols=None):
        """Return {'x','y','c{n}'...} or {'error': msg}."""
        resolved = self._resolve_table(data_file)
        if resolved.error is not None or resolved.table is None:
            self.warnings.append(f"data: {resolved.error}")
            return {"error": resolved.error}
        try:
            cols = extract_columns(resolved.table, xcol, ycol, extra_cols or [])
        except ColumnExtractionError as exc:
            self.warnings.append(f"data: {exc}")
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
            series-build time, see ``_default_column_names_like``) fills it
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

        Pattern per text (in order):
            [set hei H]
            set color C
            set just J
            amove xg(X) yg(Y)
            write "T"
        Returns (texts, next_index).
        """
        texts: List[dict] = []
        i = start
        n = len(nodes)
        while i < n:
            # Try to match one text cluster starting at i.
            consumed, text = self._try_one_text(nodes, i)
            if text is None:
                break
            texts.append(text)
            i = consumed
        return texts, i

    def _try_one_text(self, nodes, i) -> Tuple[int, Optional[dict]]:
        n = len(nodes)
        fontsize = None
        color = "BLACK"
        just = "left"
        x = y = None
        text_str = None

        # Optional 'set hei H'
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is not None and stmt.keyword == "set":
            toks = _words_and_values(stmt)
            if len(toks) >= 3 and toks[1].value.lower() == "hei":
                v = _num(toks[2])
                if v is not None:
                    fontsize = fontsize_cm_to_pt(v)
                    i += 1
                    stmt = self._as_statement(nodes[i]) if i < n else None

        # 'set color C'
        if stmt is None or stmt.keyword != "set":
            return i, None
        toks = _words_and_values(stmt)
        if len(toks) >= 3 and toks[1].value.lower() == "color":
            color = toks[2].value
            i += 1
        else:
            return i, None

        # 'set just J'
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "set":
            return i, None
        toks = _words_and_values(stmt)
        if len(toks) >= 3 and toks[1].value.lower() == "just":
            just = toks[2].value.lower()
            i += 1
        else:
            return i, None

        # 'amove xg(X) yg(Y)'
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "amove":
            return i, None
        x, y = self._parse_xg_yg(_words_and_values(stmt))
        if x is None or y is None:
            return i, None
        i += 1

        # 'write "T"'
        stmt = self._as_statement(nodes[i]) if i < n else None
        if stmt is None or stmt.keyword != "write":
            return i, None
        toks = _words_and_values(stmt)
        text_str = self._first_string(toks)
        if text_str is None:
            return i, None
        i += 1

        just_norm = just if just in ("left", "center", "right") else "left"
        return i, {
            "x": x, "y": y, "text": text_str,
            "color": color, "fontsize": fontsize,
            "ha": just_norm, "va": "center", "box_color": None,
        }

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

        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

    def _infer_positions(self, parsed_axes) -> List[Tuple[int, int, int]]:
        """Infer (rows, cols, idx) per axes from recovered amove positions."""
        n = len(parsed_axes)
        if n <= 1:
            return [(1, 1, 1)]

        amoves = [info.get("amove") for info in parsed_axes]
        if any(a is None for a in amoves):
            # Hand-written multi-graph with no amove grid -> n x 1 fallback.
            self.warnings.append(
                "layout: multi-graph without amove positions; using n x 1 grid"
            )
            return [(n, 1, k + 1) for k in range(n)]

        xs = [a[0] for a in amoves]
        ys = [a[1] for a in amoves]
        col_clusters = _cluster(xs)
        row_clusters = _cluster(ys, reverse=True)  # top row = highest y
        rows = len(row_clusters)
        cols = len(col_clusters)
        if rows * cols != n:
            self.warnings.append(
                "layout: amove positions do not form a clean grid; using n x 1 fallback"
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
        ax.xmin = info["xmin"]
        ax.xmax = info["xmax"]
        ax.ymin = info["ymin"]
        ax.ymax = info["ymax"]
        ax.y2min = info["y2min"]
        ax.y2max = info["y2max"]

        ax.lines = info["lines"]
        ax.scatters = info["scatters"]
        ax.bars = info["bars"]
        ax.fills = info["fills"]
        ax.errorbars = info["errorbars"]
        ax.file_series = info["file_series"]
        ax.texts = info["texts"]
        ax.passthrough = info["passthrough"]

        # A series whose sidecar had no real header row (hand-written .dat,
        # or a headerless import from an older gleplot version) has no
        # 'column_names' recovered above. Regenerate the same stable
        # defaults Axes.from_dict falls back to for pre-Track-E3 projects,
        # so the next save still gets a named header row.
        for attr in ("lines", "scatters", "bars", "fills", "errorbars"):
            for item in getattr(ax, attr):
                if "column_names" not in item:
                    defaults = Axes._default_column_names(attr, item)
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
        else:
            if labels_present:
                # Hand-written implicit key: GLE draws a key from the per-series
                # key "label" tokens even without 'key pos'. Re-save will add
                # 'key pos tr' (default), visually equivalent.
                self.warnings.append(
                    "legend: labeled series with no 'key' command; assuming "
                    "auto legend (re-save adds 'key pos tr')"
                )
                ax.legend_on = None
            else:
                ax.legend_on = None

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
            # No line datasets: leave default (True). Writer emits nothing that
            # depends on it, so byte-identity is unaffected.
            return
        if all(smooth_flags):
            graph_cfg.smooth_curves = True
        elif not any(smooth_flags):
            graph_cfg.smooth_curves = False
        else:
            graph_cfg.smooth_curves = True
            self.warnings.append(
                "smooth: mixed per-series smooth flags; applying smooth to all "
                "line datasets on re-save"
            )

    # -- data-file naming state -----------------------------------------

    def _finalize_data_state(self, fig):
        """Set data_prefix / counters / used-files so re-save reuses names."""
        used = set()
        for ax in fig.axes_list:
            for s in ax.lines + ax.scatters + ax.bars + ax.fills + ax.errorbars:
                df = s.get("data_file")
                if df:
                    used.add(df)
        fig._used_data_files = set(used)

        # Derive prefix from the sidecar naming convention: <prefix>_<N>.dat.
        prefix, max_idx = self._derive_prefix(used)
        if prefix is not None:
            fig.data_prefix = prefix
            fig._local_data_counter = max_idx + 1

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

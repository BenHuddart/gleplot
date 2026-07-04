"""Structural parser for GLE source: text -> document tree -> text.

The prime directive is **byte-exact round-tripping**: for any input ``text``,
``emit(parse_gle_source(text))`` must reproduce ``text`` byte-for-byte when no
node has been modified. To guarantee this, every physical line is stored with
its raw text and its original line ending, and :func:`emit` simply concatenates
the raw text of every node's lines unless a node has been explicitly replaced.

The parser layers a *structural view* on top of the flat line list so a later
semantic mapper can walk graph blocks and their statements without losing the
verbatim source. Structure problems (unbalanced ``begin``/``end`` blocks, etc.)
never raise -- they are recorded as :class:`ParseWarning` and the offending
lines fall back to plain statements.

Document model (see classes below):

    GleDocument
      .lines     : list[SourceLine]      -- every physical line, in order
      .nodes     : list[Node]            -- ordered top-level structural view
      .warnings  : list[ParseWarning]

    Node = Statement | GraphBlock | OpaqueBlock | BlankOrComment

Structural nodes reference the ``SourceLine`` objects they were built from, so
raw preservation and the structural walk share the same underlying storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

from .lexer import Token, TokenType, tokenize_line

__all__ = [
    "SourceLine",
    "Statement",
    "GraphBlock",
    "OpaqueBlock",
    "BlankOrComment",
    "Node",
    "ParseWarning",
    "GleDocument",
    "parse_gle_source",
    "emit",
    "split_statements",
]


# --------------------------------------------------------------------------- #
# Line-level storage
# --------------------------------------------------------------------------- #

@dataclass
class SourceLine:
    """One physical line of source, stored verbatim for round-tripping.

    Attributes
    ----------
    line_no:
        1-based index of the line in the original source.
    text:
        The line content *without* its terminator (see ``ending``).
    ending:
        The exact line terminator that followed this line in the source --
        ``"\\n"``, ``"\\r\\n"``, ``"\\r"``, or ``""`` for a final line with no
        trailing newline. ``text + ending`` reproduces the original slice.
    """

    line_no: int
    text: str
    ending: str = "\n"

    @property
    def raw(self) -> str:
        """The exact original bytes of this line including its terminator."""
        return self.text + self.ending


# --------------------------------------------------------------------------- #
# Statement (possibly one of several on a ``;``-separated line)
# --------------------------------------------------------------------------- #

@dataclass
class Statement:
    """A single GLE statement.

    A statement corresponds to one ``;``-separated chunk of a physical line.
    Most lines have exactly one statement (``sub_index == 0``); a line like
    ``set hei 0.5; amove 1 1`` yields two statements sharing the same
    ``source_line`` but with ``sub_index`` 0 and 1.

    Attributes
    ----------
    tokens:
        Lexer tokens for this statement's segment.
    raw:
        The verbatim source text of this statement's segment (excluding the
        ``;`` separator and line ending). Used only for inspection; emission
        of *unmodified* documents always goes through the owning
        ``SourceLine`` to preserve exact bytes including separators.
    line_no:
        1-based physical line number.
    sub_index:
        0-based index of this statement within its physical line.
    source_line:
        Back-reference to the owning :class:`SourceLine`.
    replacement:
        If set (via :meth:`GleDocument.replace_statement`), the new text that
        should be emitted in place of this statement. ``None`` means emit the
        original bytes.
    """

    tokens: List[Token]
    raw: str
    line_no: int
    sub_index: int = 0
    source_line: Optional[SourceLine] = None
    replacement: Optional[str] = None

    @property
    def keyword(self) -> Optional[str]:
        """Lower-cased first WORD token, or ``None`` for an empty statement.

        This is the primary handle the semantic mapper uses to dispatch on a
        statement (``"amove"``, ``"data"``, ``"set"``, ...). Case is folded
        for matching; original case is preserved in ``tokens``.
        """
        for tok in self.tokens:
            if tok.type is TokenType.COMMENT:
                continue
            if tok.type is TokenType.WORD:
                return tok.value.lower()
            # First meaningful token is not a word (number/op/string) -> the
            # statement has no keyword to dispatch on.
            return None
        return None

    @property
    def is_blank(self) -> bool:
        """True if the statement carries no meaningful (non-comment) tokens."""
        return all(t.type is TokenType.COMMENT for t in self.tokens)


# --------------------------------------------------------------------------- #
# Block nodes
# --------------------------------------------------------------------------- #

@dataclass
class GraphBlock:
    """A ``begin graph`` ... ``end graph`` block, descended into.

    Attributes
    ----------
    begin:
        The ``begin graph`` statement.
    end:
        The ``end graph`` statement, or ``None`` if the block was left open at
        end of file (a recorded warning accompanies this).
    body:
        Ordered structural nodes between ``begin`` and ``end``. Contains
        :class:`Statement`, :class:`BlankOrComment`, and any nested
        :class:`OpaqueBlock` nodes.
    """

    begin: Statement
    end: Optional[Statement]
    body: List["Node"] = field(default_factory=list)

    @property
    def line_no(self) -> int:
        return self.begin.line_no


@dataclass
class OpaqueBlock:
    """A non-graph ``begin X`` ... ``end X`` block passed through wholesale.

    Block types such as ``text``, ``tex``, ``object``, ``key``, ``path``,
    ``translate``, ``rotate``, ``scale``, ``origin``, ``clip``, ``table``,
    ``name``, ``box``, ``length`` are not interpreted structurally -- their
    inner lines are kept as raw :class:`SourceLine` objects and re-emitted
    verbatim. The semantic mapper generally skips these.

    Attributes
    ----------
    block_type:
        Lower-cased block name (``"text"``, ``"object"``, ...).
    begin:
        The opening ``begin <type>`` statement.
    end:
        The closing ``end <type>`` statement, or ``None`` if unclosed.
    inner_lines:
        The raw source lines strictly between begin and end.
    """

    block_type: str
    begin: Statement
    end: Optional[Statement]
    inner_lines: List[SourceLine] = field(default_factory=list)

    @property
    def line_no(self) -> int:
        return self.begin.line_no


@dataclass
class BlankOrComment:
    """A physical line that is blank or comment-only.

    Kept as its own node type so structure walkers can trivially skip these
    while emission still reproduces them verbatim.
    """

    statement: Statement

    @property
    def line_no(self) -> int:
        return self.statement.line_no


Node = Union[Statement, GraphBlock, OpaqueBlock, BlankOrComment]


# --------------------------------------------------------------------------- #
# Warnings
# --------------------------------------------------------------------------- #

@dataclass
class ParseWarning:
    """A recoverable structure problem noted during parsing.

    Never fatal. ``line_no`` points at the offending line; ``message`` is a
    short human-readable description.
    """

    line_no: int
    message: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"line {self.line_no}: {self.message}"


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #

# Non-graph block types that are captured opaquely. This is a permissive set:
# any ``begin <word>`` that is not ``graph`` is treated opaquely regardless of
# whether it appears here, but the set documents the known GLE block keywords.
KNOWN_OPAQUE_BLOCKS = frozenset({
    "text", "tex", "object", "key", "path", "translate", "rotate",
    "scale", "origin", "clip", "table", "name", "box", "length",
})


@dataclass
class GleDocument:
    """Parsed GLE document with verbatim line storage and a structural view.

    Use :func:`parse_gle_source` to build one and :func:`emit` (or the
    :meth:`emit` method) to serialise. See module docstring for the model.
    """

    lines: List[SourceLine]
    nodes: List[Node]
    warnings: List[ParseWarning] = field(default_factory=list)

    # -- serialisation -------------------------------------------------------

    def emit(self) -> str:
        """Serialise the document back to text.

        Byte-identical to the parsed input when no statement was replaced.
        Replaced statements are rendered from their ``replacement`` text; all
        other content comes straight from the stored raw line bytes.
        """
        return _emit_lines(self.lines)

    # -- structural navigation ----------------------------------------------

    @property
    def graphs(self) -> List[GraphBlock]:
        """All top-level graph blocks, in document order.

        (Graph blocks nested inside opaque blocks are not exposed here; GLE
        does not nest graphs in practice.)
        """
        return [n for n in self.nodes if isinstance(n, GraphBlock)]

    def statements(self) -> List[Statement]:
        """Flatten to every :class:`Statement` in the document, in order.

        Includes preamble/interlude statements, graph-block body statements,
        and the begin/end statements of graph blocks. Opaque block inner lines
        are *not* included (they are raw-only). Blank/comment lines are
        included via their wrapped statement so callers can see them.
        """
        out: List[Statement] = []
        for node in self.nodes:
            out.extend(_iter_statements(node))
        return out

    # -- modification API (sketch for the semantic layer) --------------------

    def replace_statement(self, statement: Statement, new_text: str) -> None:
        """Replace a single statement's emitted text.

        Minimal support intended to be driven by the semantic mapper. The
        statement's ``replacement`` is set and its owning :class:`SourceLine`
        is rewritten by re-rendering all statements on that physical line
        (so a multi-statement line rejoins with ``;`` separators preserved
        from the original where possible).

        Notes
        -----
        Emission of a modified line reconstructs it from the line's statement
        segments; leading indentation and inter-statement separators from the
        original line are preserved for statements that were *not* replaced.
        Byte-exactness is only guaranteed for statements left untouched; a
        replaced statement is emitted exactly as ``new_text`` (the caller owns
        its formatting).
        """
        statement.replacement = new_text
        src = statement.source_line
        if src is None:
            return
        src.text = _render_line_text(src, self)


# --------------------------------------------------------------------------- #
# Statement splitting (quote-aware, respects comments)
# --------------------------------------------------------------------------- #

def split_statements(text: str) -> List[Tuple[str, int]]:
    """Split a physical line into ``;``-separated statement segments.

    Splitting is quote-aware (``;`` inside a double- or single-quoted string
    does not split) and comment-aware (a ``!`` comment runs to end of line, so
    a ``;`` inside a comment does not split).

    Returns a list of ``(segment_text, start_offset)`` pairs. The segments,
    when rejoined with ``;`` at the recorded offsets, reproduce the line. A
    line with no top-level ``;`` returns a single segment covering the whole
    line.
    """
    segments: List[Tuple[str, int]] = []
    n = len(text)
    seg_start = 0
    i = 0
    in_string: Optional[str] = None
    in_comment = False

    while i < n:
        c = text[i]
        if in_comment:
            i += 1
            continue
        if in_string is not None:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == in_string:
                in_string = None
            i += 1
            continue
        # Not in string/comment.
        if c == '"' or c == "'":
            in_string = c
            i += 1
            continue
        if c == "!":
            in_comment = True
            i += 1
            continue
        if c == ";":
            segments.append((text[seg_start:i], seg_start))
            i += 1
            seg_start = i
            continue
        i += 1

    segments.append((text[seg_start:n], seg_start))
    return segments


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def parse_gle_source(text: str) -> GleDocument:
    """Parse GLE source text into a :class:`GleDocument`.

    Never raises on structural problems. See module docstring for the model
    and guarantees.
    """
    lines = _split_physical_lines(text)
    warnings: List[ParseWarning] = []

    # First pass: build a Statement (or several) per physical line, and wrap
    # blank/comment-only lines. This flat list is what the structural pass
    # consumes.
    per_line: List[List[Statement]] = []
    for src in lines:
        stmts = _statements_for_line(src)
        per_line.append(stmts)

    # Second pass: structural grouping into nodes with begin/end pairing.
    nodes = _build_structure(lines, per_line, warnings)

    return GleDocument(lines=lines, nodes=nodes, warnings=warnings)


def _split_physical_lines(text: str) -> List[SourceLine]:
    """Split source into :class:`SourceLine` objects preserving line endings.

    Handles ``\\n``, ``\\r\\n`` and lone ``\\r``. A trailing newline does *not*
    create a spurious empty final line; a file with no trailing newline keeps
    its last line's ``ending == ""``. An empty input yields no lines.
    """
    if text == "":
        return []

    lines: List[SourceLine] = []
    n = len(text)
    i = 0
    line_no = 1
    start = 0
    while i < n:
        c = text[i]
        if c == "\r":
            if i + 1 < n and text[i + 1] == "\n":
                lines.append(SourceLine(line_no, text[start:i], "\r\n"))
                i += 2
            else:
                lines.append(SourceLine(line_no, text[start:i], "\r"))
                i += 1
            line_no += 1
            start = i
        elif c == "\n":
            lines.append(SourceLine(line_no, text[start:i], "\n"))
            i += 1
            line_no += 1
            start = i
        else:
            i += 1

    if start < n:
        # Final line with no trailing terminator.
        lines.append(SourceLine(line_no, text[start:n], ""))
    return lines


def _statements_for_line(src: SourceLine) -> List[Statement]:
    """Produce the statement(s) for one physical line."""
    segments = split_statements(src.text)
    stmts: List[Statement] = []
    for sub_index, (seg_text, _offset) in enumerate(segments):
        tokens = tokenize_line(seg_text)
        stmts.append(
            Statement(
                tokens=tokens,
                raw=seg_text,
                line_no=src.line_no,
                sub_index=sub_index,
                source_line=src,
            )
        )
    return stmts


def _begin_target(stmt: Statement) -> Optional[str]:
    """If ``stmt`` is a ``begin <word>``, return the lower-cased target word."""
    words = [t for t in stmt.tokens if t.type is TokenType.WORD]
    if len(words) >= 2 and words[0].value.lower() == "begin":
        return words[1].value.lower()
    if len(words) == 1 and words[0].value.lower() == "begin":
        # ``begin`` with no target -- malformed; caller records a warning.
        return ""
    return None


def _is_end(stmt: Statement, target: Optional[str] = None) -> bool:
    """True if ``stmt`` is ``end`` (optionally ``end <target>``)."""
    words = [t for t in stmt.tokens if t.type is TokenType.WORD]
    if not words or words[0].value.lower() != "end":
        return False
    if target is None:
        return True
    if len(words) >= 2:
        return words[1].value.lower() == target
    # Bare ``end`` closes whatever block is open.
    return True


def _build_structure(
    lines: List[SourceLine],
    per_line: List[List[Statement]],
    warnings: List[ParseWarning],
) -> List[Node]:
    """Group flat statements into the ordered top-level node list.

    Handles begin/end pairing for graph blocks (structural) and other block
    types (opaque). Multi-statement lines are handled per-statement, but a
    ``begin``/``end`` is only recognised when it is the sole statement on its
    line -- GLE never mixes block delimiters with other statements on a line,
    and treating a mid-line ``begin`` as a block opener would badly mangle
    round-tripping, so mixed lines pass through as plain statements.
    """
    nodes: List[Node] = []
    n_lines = len(per_line)
    idx = 0
    while idx < n_lines:
        stmts = per_line[idx]
        src = lines[idx]

        # Multi-statement line, or single non-delimiter line.
        if len(stmts) == 1:
            stmt = stmts[0]
            target = _begin_target(stmt)
            if target is not None and target != "":
                consumed, node = _consume_block(
                    lines, per_line, idx, target, stmt, warnings
                )
                nodes.append(node)
                idx = consumed
                continue
            if target == "":
                warnings.append(ParseWarning(
                    stmt.line_no, "'begin' with no block type; treated as statement"
                ))
                nodes.append(_wrap_single(stmt))
                idx += 1
                continue
            if _is_end(stmt):
                # A stray 'end' with no matching open block at this level.
                warnings.append(ParseWarning(
                    stmt.line_no,
                    "'end' without matching 'begin'; treated as statement",
                ))
                nodes.append(_wrap_single(stmt))
                idx += 1
                continue
            nodes.append(_wrap_single(stmt))
            idx += 1
        else:
            # Multi-statement line: emit each statement as its own node. Block
            # delimiters mixed into such lines are not treated structurally.
            for stmt in stmts:
                nodes.append(_wrap_single(stmt))
            idx += 1

    return nodes


def _wrap_single(stmt: Statement) -> Node:
    """Wrap a lone statement as the appropriate leaf node."""
    if stmt.is_blank:
        return BlankOrComment(stmt)
    return stmt


def _consume_block(
    lines: List[SourceLine],
    per_line: List[List[Statement]],
    begin_idx: int,
    target: str,
    begin_stmt: Statement,
    warnings: List[ParseWarning],
) -> Tuple[int, Node]:
    """Consume a begin..end block starting at ``begin_idx``.

    Returns ``(next_index, node)``. For ``target == "graph"`` produces a
    :class:`GraphBlock` with a structured body; for anything else an
    :class:`OpaqueBlock` with raw inner lines. Unbalanced blocks are recovered:
    an unclosed block extends to end of file with a recorded warning.
    """
    n_lines = len(per_line)

    if target == "graph":
        body: List[Node] = []
        j = begin_idx + 1
        while j < n_lines:
            stmts = per_line[j]
            if len(stmts) == 1:
                s = stmts[0]
                inner_target = _begin_target(s)
                if inner_target is not None and inner_target != "":
                    consumed, inner_node = _consume_block(
                        lines, per_line, j, inner_target, s, warnings
                    )
                    body.append(inner_node)
                    j = consumed
                    continue
                if _is_end(s, "graph") or _is_end_bare(s):
                    return j + 1, GraphBlock(begin=begin_stmt, end=s, body=body)
                body.append(_wrap_single(s))
                j += 1
            else:
                for s in stmts:
                    body.append(_wrap_single(s))
                j += 1
        # Ran off the end without an 'end graph'.
        warnings.append(ParseWarning(
            begin_stmt.line_no, "'begin graph' not closed before end of file"
        ))
        return n_lines, GraphBlock(begin=begin_stmt, end=None, body=body)

    # Opaque block: gather raw inner lines until the MATCHING (or bare) end.
    # Nested begin/end pairs inside the opaque block (e.g. `begin text ...
    # end` within `begin key`) must not close the outer block, so track
    # nesting depth; inner blocks stay raw lines (we do not descend).
    inner: List[SourceLine] = []
    depth = 0
    j = begin_idx + 1
    while j < n_lines:
        stmts = per_line[j]
        if len(stmts) == 1:
            s = stmts[0]
            if _begin_target(s) is not None:
                depth += 1
            elif _is_end(s, target) or _is_end_bare(s):
                if depth == 0:
                    return j + 1, OpaqueBlock(
                        block_type=target,
                        begin=begin_stmt,
                        end=s,
                        inner_lines=inner,
                    )
                depth -= 1
        inner.append(lines[j])
        j += 1

    warnings.append(ParseWarning(
        begin_stmt.line_no,
        f"'begin {target}' not closed before end of file",
    ))
    return n_lines, OpaqueBlock(
        block_type=target, begin=begin_stmt, end=None, inner_lines=inner
    )


def _is_end_bare(stmt: Statement) -> bool:
    """True if ``stmt`` is a bare ``end`` with no explicit target word."""
    words = [t for t in stmt.tokens if t.type is TokenType.WORD]
    return len(words) == 1 and words[0].value.lower() == "end"


# --------------------------------------------------------------------------- #
# Emission helpers
# --------------------------------------------------------------------------- #

def _iter_statements(node: Node) -> List[Statement]:
    """Yield the statements reachable from a node (see ``statements``)."""
    if isinstance(node, Statement):
        return [node]
    if isinstance(node, BlankOrComment):
        return [node.statement]
    if isinstance(node, GraphBlock):
        out = [node.begin]
        for child in node.body:
            out.extend(_iter_statements(child))
        if node.end is not None:
            out.append(node.end)
        return out
    if isinstance(node, OpaqueBlock):
        out = [node.begin]
        if node.end is not None:
            out.append(node.end)
        return out
    return []


def _emit_lines(lines: List[SourceLine]) -> str:
    """Concatenate the raw bytes of every source line."""
    return "".join(src.raw for src in lines)


def _render_line_text(src: SourceLine, doc: GleDocument) -> str:
    """Re-render a physical line's text from its (possibly replaced) statements.

    Preserves the original leading whitespace and the inter-statement text
    (``;`` plus any surrounding spaces) for statements left untouched, and
    substitutes ``replacement`` text for replaced ones.
    """
    stmts = [s for s in doc.statements() if s.source_line is src]
    stmts.sort(key=lambda s: s.sub_index)
    if not stmts:
        return src.text
    if len(stmts) == 1:
        s = stmts[0]
        if s.replacement is not None:
            # Preserve leading indentation of the original segment.
            leading = src.text[: len(src.text) - len(src.text.lstrip())]
            return leading + s.replacement.lstrip()
        return src.text

    # Multi-statement: rebuild using original segment offsets so separators
    # survive. We recompute segment boundaries from the original text.
    segments = split_statements(src.text)
    pieces: List[str] = []
    for i, (seg_text, _offset) in enumerate(segments):
        stmt = next((s for s in stmts if s.sub_index == i), None)
        if stmt is not None and stmt.replacement is not None:
            leading = seg_text[: len(seg_text) - len(seg_text.lstrip())]
            pieces.append(leading + stmt.replacement.lstrip())
        else:
            pieces.append(seg_text)
    return ";".join(pieces)


def emit(document: GleDocument) -> str:
    """Serialise ``document`` back to source text (module-level convenience)."""
    return document.emit()

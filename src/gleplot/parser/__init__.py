"""Core GLE-parsing package for gleplot (Track A1: lexer, syntax, expr).

This package turns ``.gle`` source text into a structural document tree with
byte-exact passthrough, ready for a semantic mapper (a separate track) to
interpret. It contains **no Qt imports** and depends only on the standard
library, so it is safe to use from any layer.

The prime directive is round-trip fidelity: ``emit(parse_gle_source(text))``
reproduces ``text`` byte-for-byte when nothing has been modified.

Public entry points (this track's modules only)::

    from gleplot.parser import parse_gle_source, emit, GleDocument
    from gleplot.parser import tokenize_line, Token, TokenType
    from gleplot.parser import eval_gle_number, format_gle_number

Other modules in this package (``tables``, ``units``, ``metadata``) are owned
by a parallel track and are intentionally *not* re-exported here.
"""

from .lexer import Token, TokenType, tokenize_line
from .expr import eval_gle_number, format_gle_number
from .syntax import (
    BlankOrComment,
    GleDocument,
    GraphBlock,
    Node,
    OpaqueBlock,
    ParseWarning,
    SourceLine,
    Statement,
    emit,
    parse_gle_source,
    split_statements,
)

__all__ = [
    # lexer
    "Token",
    "TokenType",
    "tokenize_line",
    # expr
    "eval_gle_number",
    "format_gle_number",
    # syntax
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

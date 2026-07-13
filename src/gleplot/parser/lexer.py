"""Tokenizer for a single physical line of GLE source.

This is a *tolerant* lexer: it never raises on malformed input. When it
encounters something it cannot classify cleanly (for example an unterminated
double-quoted string), it emits a best-effort token and records the situation
via the token type / an ``error`` flag rather than aborting. The point of the
whole parser stack is byte-exact round-tripping of arbitrary ``.gle`` text, so
the lexer must degrade gracefully on anything a human might have typed.

Lexical contract (verified against GLE 4.3.10 ``token.cpp`` / ``pass.cpp``):

* ``!`` begins a comment that runs to end of line, *except* inside a
  double-quoted string. The comment text (including the ``!``) is preserved
  verbatim as a ``COMMENT`` token.
* Strings are double-quoted; ``\\"`` escapes an embedded quote. Single-quoted
  strings are tolerated on input (kept verbatim, quote char recorded) but this
  layer never rewrites them.
* Whitespace is insignificant to structure but every token carries a span into
  the original line so the raw text is always reconstructable.
* Numbers follow ``float()`` semantics: ``1``, ``1.5``, ``.5``, ``5.``,
  ``1e-3``, with an optional leading sign -- but only when the numeric
  literal is immediately followed by a terminator or end-of-line. A digit
  run glued directly to further word characters (no terminator in between)
  is a bareword, not a number followed by a word: ``20_main.dat`` is a
  single ``WORD`` token (not ``NUMBER '20'`` + ``WORD '_main.dat'``),
  ``5.dat`` is ``WORD '5.dat'``, ``1e5abc`` is ``WORD '1e5abc'``. This
  matters for unquoted data filenames, which are the only place valid GLE
  glues digits directly onto identifier characters. ``20,30`` still lexes
  as ``NUMBER OP NUMBER``, ``20!c`` as ``NUMBER COMMENT``, ``2(x)`` as
  ``NUMBER OP ...``, ``20"s"`` as ``NUMBER STRING``, and ``10%`` as
  ``NUMBER WORD('%')`` -- ``,``, ``!``, ``(``, and ``"`` are ordinary word
  terminators, and ``%`` additionally stops the digit-merge (without being a
  general bareword terminator), so those cases are unaffected. This keeps a
  percentage error like ``err 10%`` lexing with a standalone ``'%'`` token,
  which the recognizer's error-value parsing looks for by value.
* Operators recognised as ``OP``: ``= , ( ) * / + - ^``.

The lexer does **not** split on ``;`` -- statement splitting is the concern of
:mod:`gleplot.parser.syntax`, which needs quote-aware splitting and does it
itself. The lexer treats ``;`` as an ``OP`` token so a caller tokenising a full
line still sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TokenType(Enum):
    """Kinds of lexical token produced by :func:`tokenize_line`."""

    WORD = "WORD"          # bareword / identifier / keyword (case preserved)
    NUMBER = "NUMBER"      # numeric literal (float() parseable)
    STRING = "STRING"      # quoted string literal (quotes included in value)
    OP = "OP"             # one of = , ( ) * / + - ^ ;
    COMMENT = "COMMENT"    # ! ... to end of line (! included)
    UNKNOWN = "UNKNOWN"    # anything the lexer could not classify


# Single-character operators. ``;`` is included so a full-line tokenisation
# still surfaces statement separators; the structural splitter handles them.
_OPERATOR_CHARS = frozenset("=,()*/+-^;")

# Characters that terminate a bareword.
_WORD_TERMINATORS = frozenset("=,()*/+-^;!\"' \t")

# Additional characters that stop the "digit glued to word" merge (see
# tokenize_line) without being general bareword terminators. '%' is the only
# member: a percentage literal like 'err 10%' must keep lexing as NUMBER '10'
# + WORD '%' (the recognizer's error-value parsing looks for a standalone
# '%' token), but a bare '%' elsewhere still reads as an ordinary WORD
# character rather than becoming its own terminator-triggered token.
_NUMBER_MERGE_STOPPERS = _WORD_TERMINATORS | frozenset("%")


@dataclass(frozen=True)
class Token:
    """A single lexical token.

    Attributes
    ----------
    type:
        The :class:`TokenType`.
    value:
        The exact source text of the token, verbatim. For ``STRING`` tokens
        this *includes* the surrounding quote characters, so ``value`` sliced
        from the source line is always ``line[span[0]:span[1]]``.
    span:
        ``(start, end)`` half-open character offsets into the source line.
    error:
        Set for tolerated-but-malformed tokens (currently: unterminated
        string). Downstream code may surface this as a warning; it never
        affects round-tripping because ``value`` is still the raw text.
    quote:
        For ``STRING`` tokens, the quote character that opened it (``"`` or
        ``'``). ``None`` otherwise.
    """

    type: TokenType
    value: str
    span: tuple
    error: Optional[str] = None
    quote: Optional[str] = None

    @property
    def start(self) -> int:
        return self.span[0]

    @property
    def end(self) -> int:
        return self.span[1]

    def lower(self) -> str:
        """Case-folded token value (for case-insensitive keyword matching)."""
        return self.value.lower()


def tokenize_line(text: str) -> List[Token]:
    """Tokenise a single physical line of GLE source.

    The input should be one line *without* its trailing newline (the caller in
    :mod:`~gleplot.parser.syntax` strips line endings and preserves them
    separately). Passing a string that contains newlines is tolerated -- the
    newline is treated as ordinary whitespace -- but spans then refer to the
    combined string.

    Never raises. Returns tokens in source order; whitespace produces no token
    but is fully recoverable from the gaps between token spans.
    """
    tokens: List[Token] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Whitespace: skip (recoverable via spans).
        if ch in " \t\r\n":
            i += 1
            continue

        # Comment: '!' to end of line, verbatim.
        if ch == "!":
            tokens.append(Token(TokenType.COMMENT, text[i:], (i, n)))
            break

        # Quoted string (double or tolerated single).
        if ch == '"' or ch == "'":
            tok = _read_string(text, i, n, ch)
            tokens.append(tok)
            i = tok.end
            continue

        # Number literal (including a leading sign only when it is clearly a
        # numeric literal rather than an operator between operands). We take
        # the tolerant route: a '+'/'-' immediately followed by a digit or a
        # dot+digit, and NOT preceded by something that could be an operand,
        # is treated as an operator here -- expression evaluation handles unary
        # signs itself. So the lexer emits '+'/'-' as OP and lets expr.py
        # interpret unary vs binary. Bare numbers still parse here.
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            tok = _read_number(text, i, n)
            if tok is not None:
                if tok.end < n and text[tok.end] not in _NUMBER_MERGE_STOPPERS:
                    # The digit run is glued directly to more word
                    # characters with no terminator between them -- e.g.
                    # '20_main.dat', '1e5abc', '5.dat'. That is only ever a
                    # bareword (typically an unquoted filename) in valid
                    # GLE, so re-read the whole run as a single WORD rather
                    # than splitting off a NUMBER prefix.
                    tok = _read_word(text, i, n)
                tokens.append(tok)
                i = tok.end
                continue

        # Operators.
        if ch in _OPERATOR_CHARS:
            tokens.append(Token(TokenType.OP, ch, (i, i + 1)))
            i += 1
            continue

        # Bareword / identifier / keyword.
        tok = _read_word(text, i, n)
        tokens.append(tok)
        i = tok.end

    return tokens


def _read_string(text: str, start: int, n: int, quote: str) -> Token:
    """Read a quoted string beginning at ``start`` (the opening quote).

    ``\\`` escapes the following character (so ``\\"`` does not close the
    string). An unterminated string is tolerated: the token spans to end of
    line and is flagged with ``error='unterminated-string'``.
    """
    i = start + 1
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == quote:
            end = i + 1
            return Token(
                TokenType.STRING,
                text[start:end],
                (start, end),
                quote=quote,
            )
        i += 1
    # Ran off the end without a closing quote: tolerate, flag it.
    return Token(
        TokenType.STRING,
        text[start:n],
        (start, n),
        error="unterminated-string",
        quote=quote,
    )


def _read_number(text: str, start: int, n: int) -> Optional[Token]:
    """Read a numeric literal beginning at ``start``.

    Uses ``float()`` semantics for the longest prefix that parses. Returns
    ``None`` if no numeric literal can be formed (caller then falls back to
    word/operator handling).
    """
    i = start
    seen_digit = False
    seen_dot = False
    seen_exp = False

    while i < n:
        c = text[i]
        if c.isdigit():
            seen_digit = True
            i += 1
        elif c == "." and not seen_dot and not seen_exp:
            seen_dot = True
            i += 1
        elif (c == "e" or c == "E") and seen_digit and not seen_exp:
            # Exponent: optional sign then digits.
            j = i + 1
            if j < n and text[j] in "+-":
                j += 1
            if j < n and text[j].isdigit():
                seen_exp = True
                i = j
            else:
                break  # 'e' not part of a valid exponent -> stop number here
        else:
            break

    if not seen_digit:
        return None

    literal = text[start:i]
    # Defensive: confirm it really parses (it always should given the scan).
    try:
        float(literal)
    except ValueError:  # pragma: no cover - scan guarantees validity
        return None
    return Token(TokenType.NUMBER, literal, (start, i))


def _read_word(text: str, start: int, n: int) -> Token:
    """Read a bareword up to the next terminator.

    A bareword is any run of characters not in :data:`_WORD_TERMINATORS`. This
    deliberately includes ``.`` (so filenames like ``data.dat`` and dataset
    refs like ``d1=c1,c2`` -- well, the ``=`` splits -- stay intact where
    sensible) and ``_`` and digits mid-word.
    """
    i = start
    while i < n and text[i] not in _WORD_TERMINATORS:
        i += 1
    if i == start:
        # Shouldn't happen (caller guarantees a non-terminator start), but be
        # safe: emit a single-char UNKNOWN token to guarantee progress.
        return Token(TokenType.UNKNOWN, text[start:start + 1], (start, start + 1))
    return Token(TokenType.WORD, text[start:i], (start, i))

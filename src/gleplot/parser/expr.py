"""Safe arithmetic evaluator for GLE numeric expressions.

This is a tiny recursive-descent evaluator over the tokens produced by
:mod:`gleplot.parser.lexer`. It exists so the semantic mapper can turn a token
run such as ``2 * pi`` or ``(1 + 3) / 2`` into a concrete float *without ever
calling* :func:`eval`. Anything it cannot evaluate to a plain number -- a
function call like ``sin(x)``, a variable reference, a dataset expression --
yields ``None``, signalling the caller to treat that statement as opaque
passthrough.

Grammar (standard precedence, ``^`` right-associative)::

    expr    := term (('+' | '-') term)*
    term    := power (('*' | '/') power)*
    power   := unary ('^' power)?          # right-assoc
    unary   := ('+' | '-') unary | atom
    atom    := NUMBER | CONST | '(' expr ')'

Recognised constants (case-insensitive): ``pi``, ``e``.
"""

from __future__ import annotations

import math
from typing import List, Optional, Union

from .lexer import Token, TokenType, tokenize_line

# Case-insensitive named constants.
_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


class _EvalError(Exception):
    """Internal sentinel: expression is not a pure number. Never escapes."""


def eval_gle_number(tokens_or_str: Union[str, List[Token]]) -> Optional[float]:
    """Evaluate an arithmetic expression to a float, or return ``None``.

    Parameters
    ----------
    tokens_or_str:
        Either a raw source fragment (which will be tokenised) or a list of
        :class:`~gleplot.parser.lexer.Token` already produced by the lexer.

    Returns
    -------
    float or None
        The evaluated value, or ``None`` if the input is empty, references an
        unknown identifier / function, contains a syntax error, or otherwise
        is not a closed-form arithmetic constant expression. ``None`` is the
        caller's cue to keep the statement as verbatim passthrough.
    """
    if isinstance(tokens_or_str, str):
        tokens = tokenize_line(tokens_or_str)
    else:
        tokens = list(tokens_or_str)

    # Drop trailing comments -- an inline comment does not invalidate a number.
    tokens = [t for t in tokens if t.type is not TokenType.COMMENT]

    if not tokens:
        return None

    parser = _ExprParser(tokens)
    try:
        value = parser.parse_expr()
        parser.expect_end()
    except _EvalError:
        return None
    if not math.isfinite(value):
        # Division by zero / overflow: not a usable literal.
        return None
    return value


class _ExprParser:
    """Recursive-descent parser/evaluator over a token list."""

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos = 0

    # -- token cursor helpers ------------------------------------------------

    def _peek(self) -> Optional[Token]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _at_op(self, *ops: str) -> bool:
        tok = self._peek()
        return tok is not None and tok.type is TokenType.OP and tok.value in ops

    def expect_end(self) -> None:
        if self._pos != len(self._tokens):
            raise _EvalError()

    # -- grammar -------------------------------------------------------------

    def parse_expr(self) -> float:
        value = self._parse_term()
        while self._at_op("+", "-"):
            op = self._advance().value
            rhs = self._parse_term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _parse_term(self) -> float:
        value = self._parse_power()
        while self._at_op("*", "/"):
            op = self._advance().value
            rhs = self._parse_power()
            if op == "*":
                value = value * rhs
            else:
                if rhs == 0:
                    raise _EvalError()
                value = value / rhs
        return value

    def _parse_power(self) -> float:
        base = self._parse_unary()
        if self._at_op("^"):
            self._advance()
            # Right-associative: recurse into power for the exponent.
            exponent = self._parse_power()
            try:
                return math.pow(base, exponent)
            except (ValueError, OverflowError):
                raise _EvalError()
        return base

    def _parse_unary(self) -> float:
        if self._at_op("+", "-"):
            op = self._advance().value
            operand = self._parse_unary()
            return operand if op == "+" else -operand
        return self._parse_atom()

    def _parse_atom(self) -> float:
        tok = self._peek()
        if tok is None:
            raise _EvalError()

        if tok.type is TokenType.NUMBER:
            self._advance()
            try:
                return float(tok.value)
            except ValueError:  # pragma: no cover - lexer guarantees validity
                raise _EvalError()

        if tok.type is TokenType.WORD:
            key = tok.value.lower()
            if key in _CONSTANTS:
                self._advance()
                # Reject a following '(' -- that would be a function call.
                if self._at_op("("):
                    raise _EvalError()
                return _CONSTANTS[key]
            # Unknown identifier (variable or function name) -> not a number.
            raise _EvalError()

        if tok.type is TokenType.OP and tok.value == "(":
            self._advance()
            value = self.parse_expr()
            if not self._at_op(")"):
                raise _EvalError()
            self._advance()
            return value

        raise _EvalError()


def format_gle_number(value: float) -> str:
    """Format a float the way the GLE writer does (``.6g``).

    Mirrors ``GLEWriter._format_number`` conventions so numbers regenerated by
    the semantic layer match the writer's output. Very small magnitudes snap to
    ``'0'`` and very large ones use scientific notation, matching the writer.
    """
    if isinstance(value, (int, float)):
        if abs(value) < 1e-10:
            return "0"
        if abs(value) > 1e10:
            return f"{value:.3e}"
        return f"{value:.6g}"
    return str(value)

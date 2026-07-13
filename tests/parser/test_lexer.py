"""Tests for the tolerant line lexer."""

import pytest

from gleplot.parser.lexer import Token, TokenType, tokenize_line


def _types(text):
    return [t.type for t in tokenize_line(text)]


def _values(text):
    return [t.value for t in tokenize_line(text)]


# -- basic tokenisation ------------------------------------------------------

def test_empty_line_yields_no_tokens():
    assert tokenize_line("") == []
    assert tokenize_line("   \t ") == []


def test_simple_words():
    assert _values("begin graph") == ["begin", "graph"]
    assert _types("begin graph") == [TokenType.WORD, TokenType.WORD]


def test_case_is_preserved_in_value():
    toks = tokenize_line("Begin GRAPH Title")
    assert [t.value for t in toks] == ["Begin", "GRAPH", "Title"]
    # ...but lower() gives folded form for matching.
    assert [t.lower() for t in toks] == ["begin", "graph", "title"]


def test_spans_reconstruct_source():
    text = 'set  hei   0.5'
    for tok in tokenize_line(text):
        assert text[tok.start:tok.end] == tok.value


# -- strings -----------------------------------------------------------------

def test_double_quoted_string_includes_quotes():
    toks = tokenize_line('write "hello world"')
    assert toks[1].type is TokenType.STRING
    assert toks[1].value == '"hello world"'
    assert toks[1].quote == '"'


def test_escaped_quote_does_not_terminate():
    toks = tokenize_line(r'write "say \"hi\" now"')
    string_toks = [t for t in toks if t.type is TokenType.STRING]
    assert len(string_toks) == 1
    assert string_toks[0].value == r'"say \"hi\" now"'


def test_single_quoted_string_tolerated():
    toks = tokenize_line("write 'legacy'")
    assert toks[1].type is TokenType.STRING
    assert toks[1].value == "'legacy'"
    assert toks[1].quote == "'"


def test_semicolon_inside_string_is_part_of_string():
    toks = tokenize_line('write "a ; b"')
    assert toks[1].value == '"a ; b"'
    # No OP ';' token should appear.
    assert not any(t.type is TokenType.OP and t.value == ";" for t in toks)


def test_bang_inside_string_is_not_a_comment():
    toks = tokenize_line('write "not! a comment"')
    assert toks[1].value == '"not! a comment"'
    assert not any(t.type is TokenType.COMMENT for t in toks)


def test_unterminated_string_is_tolerated_and_flagged():
    toks = tokenize_line('write "oops no close')
    string_toks = [t for t in toks if t.type is TokenType.STRING]
    assert len(string_toks) == 1
    assert string_toks[0].value == '"oops no close'
    assert string_toks[0].error == "unterminated-string"


# -- comments ----------------------------------------------------------------

def test_comment_to_end_of_line():
    toks = tokenize_line("size 20 15 ! the page")
    assert toks[-1].type is TokenType.COMMENT
    assert toks[-1].value == "! the page"


def test_comment_only_line():
    toks = tokenize_line("! just a comment")
    assert len(toks) == 1
    assert toks[0].type is TokenType.COMMENT
    assert toks[0].value == "! just a comment"


def test_comment_span_covers_rest_of_line():
    text = "a ! b c d"
    toks = tokenize_line(text)
    comment = toks[-1]
    assert text[comment.start:comment.end] == "! b c d"


# -- numbers -----------------------------------------------------------------

@pytest.mark.parametrize("lit", ["0", "42", "3.14", ".5", "5.", "1e-3", "1E5",
                                  "6.022e23", "2.5e+10"])
def test_number_literals(lit):
    toks = tokenize_line(lit)
    assert len(toks) == 1
    assert toks[0].type is TokenType.NUMBER
    assert toks[0].value == lit
    assert float(toks[0].value) == float(lit)


def test_leading_sign_is_operator_not_number():
    # The lexer emits +/- as OP; expr.py interprets unary signs.
    toks = tokenize_line("-5")
    assert toks[0].type is TokenType.OP
    assert toks[0].value == "-"
    assert toks[1].type is TokenType.NUMBER
    assert toks[1].value == "5"


def test_trailing_e_not_consumed_as_exponent():
    # '5e' is not a valid exponent, and 'e' is not a terminator after '5' ->
    # the digit-glued-to-word rule (see module docstring) makes the whole
    # thing a single bareword rather than NUMBER '5' + WORD 'e'.
    toks = tokenize_line("5e")
    assert len(toks) == 1
    assert toks[0].type is TokenType.WORD and toks[0].value == "5e"


def test_number_then_word_boundary():
    # A digit run glued directly to further word characters, with no
    # terminator in between, is a single bareword -- not NUMBER + WORD. This
    # is the same rule that makes '20_main.dat' parse as one filename token.
    toks = tokenize_line("0.5cm")
    assert len(toks) == 1
    assert toks[0].type is TokenType.WORD
    assert toks[0].value == "0.5cm"


# -- digit-glued-to-word barewords (unquoted filenames) ----------------------
#
# Regression coverage for gleplot mis-tokenizing unquoted data filenames that
# start with a digit, e.g. Asymmetry's exported ``data 20_main.dat d1=c1,c2``.
# See the lexer module docstring's lexical-contract entry for the rule.

@pytest.mark.parametrize("text,expected_value", [
    ("20_main.dat", "20_main.dat"),
    ("5.dat", "5.dat"),
    ("1e5abc", "1e5abc"),
])
def test_digit_glued_to_word_is_single_bareword(text, expected_value):
    toks = tokenize_line(text)
    assert len(toks) == 1
    assert toks[0].type is TokenType.WORD
    assert toks[0].value == expected_value
    assert toks[0].span == (0, len(text))


@pytest.mark.parametrize("text,expected", [
    # Terminators immediately after a numeric literal stop the merge, so a
    # plain number followed by a recognised terminator still lexes as
    # NUMBER (+ whatever the terminator introduces).
    ("20,30", [(TokenType.NUMBER, "20"), (TokenType.OP, ","),
               (TokenType.NUMBER, "30")]),
    ("20!c", [(TokenType.NUMBER, "20"), (TokenType.COMMENT, "!c")]),
    ("2(x)", [(TokenType.NUMBER, "2"), (TokenType.OP, "("),
              (TokenType.WORD, "x"), (TokenType.OP, ")")]),
    ('20"s"', [(TokenType.NUMBER, "20"), (TokenType.STRING, '"s"')]),
    # '%' stops the digit-merge (without being a general word terminator),
    # so a percentage error value ('err 10%') keeps lexing as a NUMBER
    # followed by a standalone '%' WORD token -- the recognizer's
    # error-value parsing depends on '%' being its own token.
    ("10%", [(TokenType.NUMBER, "10"), (TokenType.WORD, "%")]),
])
def test_number_followed_by_terminator_is_not_merged(text, expected):
    toks = tokenize_line(text)
    assert [(t.type, t.value) for t in toks] == expected


def test_number_glued_to_word_with_embedded_terminator_splits_at_it():
    # '1e-3x': the digit-merge rule re-reads the whole run as a bareword
    # starting from the numeric literal's start, and the bareword reader
    # stops at the first terminator character it meets -- here the '-' that
    # was originally consumed as part of the exponent. This is a known,
    # accepted quirk of the fix (not worth special-casing): the '-'
    # terminator splits the word, same as it would anywhere else.
    toks = tokenize_line("1e-3x")
    assert [(t.type, t.value) for t in toks] == [
        (TokenType.WORD, "1e"),
        (TokenType.OP, "-"),
        (TokenType.WORD, "3x"),
    ]


# -- operators ---------------------------------------------------------------

def test_dataset_assignment_operators():
    toks = tokenize_line("d1=c1,c2")
    kinds = [(t.type, t.value) for t in toks]
    assert kinds == [
        (TokenType.WORD, "d1"),
        (TokenType.OP, "="),
        (TokenType.WORD, "c1"),
        (TokenType.OP, ","),
        (TokenType.WORD, "c2"),
    ]


def test_arithmetic_operators_tokenised():
    toks = tokenize_line("(1+2)*3^4/5")
    ops = [t.value for t in toks if t.type is TokenType.OP]
    assert ops == ["(", "+", ")", "*", "^", "/"]


# -- tolerance / pathological ------------------------------------------------

def test_never_raises_on_weird_input():
    for weird in ['"', "'", "\\", "!!!", "===", "((((", "d1=c1,c2 ! x\"",
                  "\x00 weird", "12.3.4.5"]:
        # Must not raise.
        toks = tokenize_line(weird)
        assert isinstance(toks, list)


def test_multiple_dots_number_stops_cleanly():
    # '12.3.4' -> number '12.3' then '.4' number (or word). Just must not raise
    # and must be span-consistent.
    text = "12.3.4"
    toks = tokenize_line(text)
    for tok in toks:
        assert text[tok.start:tok.end] == tok.value

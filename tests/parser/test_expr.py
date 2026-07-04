"""Tests for the safe arithmetic evaluator."""

import math

import pytest

from gleplot.parser.expr import eval_gle_number, format_gle_number


# -- arithmetic matrix -------------------------------------------------------

@pytest.mark.parametrize("src,expected", [
    ("1", 1.0),
    ("1+2", 3.0),
    ("5-3", 2.0),
    ("2*3", 6.0),
    ("10/4", 2.5),
    ("2^3", 8.0),
    ("1+2*3", 7.0),           # precedence: * before +
    ("(1+2)*3", 9.0),         # parens override
    ("2*3+4*5", 26.0),
    ("10-2-3", 5.0),          # left-assoc subtraction
    ("100/5/2", 10.0),        # left-assoc division
    (".5+.5", 1.0),
    ("1e3", 1000.0),
    ("-5", -5.0),             # unary minus
    ("+5", 5.0),              # unary plus
    ("-(2+3)", -5.0),
    ("--5", 5.0),             # double unary
    ("2*-3", -6.0),           # unary after binary
])
def test_arithmetic(src, expected):
    assert eval_gle_number(src) == pytest.approx(expected)


def test_power_is_right_associative():
    # 2^(3^2) = 2^9 = 512, not (2^3)^2 = 64.
    assert eval_gle_number("2^3^2") == pytest.approx(512.0)


def test_unary_binds_tighter_than_power_on_base():
    # In this grammar power's base is a `unary`, so the leading '-' attaches to
    # the base: -2^2 == (-2)^2 == 4. A parenthesised form makes intent explicit.
    assert eval_gle_number("-2^2") == pytest.approx(4.0)
    assert eval_gle_number("-(2^2)") == pytest.approx(-4.0)


# -- constants ---------------------------------------------------------------

@pytest.mark.parametrize("src", ["pi", "PI", "Pi", "pI"])
def test_pi_any_case(src):
    assert eval_gle_number(src) == pytest.approx(math.pi)


@pytest.mark.parametrize("src", ["e", "E"])
def test_e_any_case(src):
    assert eval_gle_number(src) == pytest.approx(math.e)


def test_two_pi():
    assert eval_gle_number("2*pi") == pytest.approx(2 * math.pi)


def test_pi_over_two():
    assert eval_gle_number("pi/2") == pytest.approx(math.pi / 2)


# -- rejection (None) --------------------------------------------------------

@pytest.mark.parametrize("src", [
    "",
    "   ",
    "sin(x)",         # function call
    "cos(0)",         # function call, even with numeric arg
    "x",              # bare variable
    "foo",            # unknown identifier
    "x+1",            # variable in expression
    "pi(2)",          # constant used as a call
    "1+",             # trailing operator
    "1 2",            # two numbers, no operator
    "(1+2",           # unbalanced paren
    "1+2)",           # unbalanced paren
    "*3",             # leading binary op
    "1/0",            # division by zero -> not finite
    "d1",             # dataset reference
])
def test_rejects_non_numbers(src):
    assert eval_gle_number(src) is None


def test_trailing_comment_is_ignored():
    assert eval_gle_number("2*3 ! six") == pytest.approx(6.0)


def test_accepts_token_list():
    from gleplot.parser.lexer import tokenize_line
    assert eval_gle_number(tokenize_line("3*4")) == pytest.approx(12.0)


# -- formatting --------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0.0, "0"),
    (1.0, "1"),
    (1.5, "1.5"),
    (0.42328, "0.42328"),
    (20.32, "20.32"),
    (1e-12, "0"),          # snaps to zero
])
def test_format_gle_number(value, expected):
    assert format_gle_number(value) == expected


def test_format_matches_writer_convention():
    # Round-trip a value through eval + format and confirm .6g behaviour.
    assert format_gle_number(1.0 / 3.0) == f"{1.0 / 3.0:.6g}"

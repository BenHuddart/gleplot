"""Unit tests for ``Figure(data_prefix=...)`` sanitization.

The prefix is pasted straight into a bare GLE ``data <name> dN=c1,c2``
command, so a prefix carrying punctuation used to produce a script that GLE
rejected at *compile* time ("left hand side contains unquoted string")
instead of failing where the bad value was supplied. It now goes through the
same sanitizer as a per-series ``data_name``.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp


X = np.array([0.0, 1.0, 2.0])
Y = np.array([1.0, 2.0, 3.0])


def _first_sidecar(fig):
    _text, files = fig._generate_gle_with_files()
    return sorted(files)[0]


def test_a_safe_prefix_is_untouched():
    fig = glp.figure(data_prefix="run9")
    assert fig.data_prefix == "run9"
    fig.add_subplot(111).plot(X, Y)
    assert _first_sidecar(fig) == "run9_0.dat"


def test_hyphens_and_underscores_survive():
    """Both are fine in a bare GLE filename (verified against the binary)."""
    fig = glp.figure(data_prefix="run-9_b")
    assert fig.data_prefix == "run-9_b"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("run+2", "run_2"),
        ("run 2", "run_2"),
        ("fig*a", "fig_a"),
        ("a/b", "a_b"),
        ("x(1)", "x_1"),
    ],
)
def test_unsafe_characters_are_replaced_and_warn(raw, expected):
    with pytest.warns(UserWarning, match="not safe in a GLE data filename"):
        fig = glp.figure(data_prefix=raw)
    assert fig.data_prefix == expected


def test_the_warning_names_both_spellings():
    with pytest.warns(UserWarning) as caught:
        glp.figure(data_prefix="run+2")
    message = str(caught[0].message)
    assert "run+2" in message and "run_2" in message


def test_case_is_normalized_silently():
    """Mixed case is valid in a GLE filename, so it is not worth a warning --
    but it is still normalized, exactly as a per-series data_name is."""
    import warnings as _warnings

    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        fig = glp.figure(data_prefix="RunNine")
    assert fig.data_prefix == "runnine"
    assert not [w for w in caught if "data filename" in str(w.message)]


def test_empty_and_none_keep_the_global_counter_behaviour():
    """Falsy means "use the global data_N counter" and must not become 'data'."""
    assert glp.figure(data_prefix=None).data_prefix is None
    assert glp.figure(data_prefix="").data_prefix == ""


def test_a_prefix_of_only_unsafe_characters_falls_back_to_data():
    with pytest.warns(UserWarning):
        fig = glp.figure(data_prefix="+++")
    assert fig.data_prefix == "data"


def test_sanitized_prefix_produces_a_bare_gle_filename():
    with pytest.warns(UserWarning):
        fig = glp.figure(data_prefix="run+2")
    fig.add_subplot(111).plot(X, Y)
    text, _files = fig._generate_gle_with_files()
    assert "data run_2_0.dat" in text
    assert "+" not in text


def test_round_trip_does_not_re_warn():
    with pytest.warns(UserWarning):
        fig = glp.figure(data_prefix="run+2")
    fig.add_subplot(111).plot(X, Y)

    import warnings as _warnings

    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        restored = glp.Figure.from_dict(fig.to_dict())
    assert restored.data_prefix == "run_2"
    assert not [w for w in caught if "data filename" in str(w.message)]

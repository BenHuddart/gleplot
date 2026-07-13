"""Regression tests: unquoted data filenames that start with a digit,
contain a hyphen, or contain a '/' path separator.

Reproduces the bug reported against a real Asymmetry export: the run-label
data sidecar is named e.g. ``20_main.dat``, and the exported ``.gle`` reads:

    data 20_main.dat d1=c1,c2 d2=c1,c3

Plain GLE 4.3 compiles this fine, but gleplot's lexer split the digit-led
filename into a NUMBER token plus a WORD remainder, so the recognizer
registered the data file as just ``"20"``. Two sibling cases share the same
single-token-filename assumption in the recognizer even with the lexer fixed
for digits: hyphenated names (``my-file.dat``) and relative paths
(``sub/dir/file.dat``), because ``-`` and ``/`` both lex as ``OP`` tokens.

See ``gleplot.parser.lexer`` (digit-glued-to-word bareword rule) and
``_Recognizer._read_filename`` (span-contiguous token merge) for the fixes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gleplot.parser import emit, parse_gle_source
from gleplot.parser.recognizer import parse_gle_figure


def _write(tmp_path: Path, name: str, content: str, dats: dict | None = None) -> Path:
    for dat_name, dat_content in (dats or {}).items():
        dat_path = tmp_path / dat_name
        dat_path.parent.mkdir(parents=True, exist_ok=True)
        dat_path.write_text(dat_content, encoding="utf-8")
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# Asymmetry's export shape verbatim (see the module docstring). No '!
# gleplot' metadata block is present, so -- per the Finding-1 conservative
# classification rule -- the data reference is recovered as an external
# 'reference' (file_series), not adopted as an import.
_ASYMMETRY_EXPORT = (
    "begin graph\n"
    '    xtitle "Time (µs)"\n'
    "    data {filename} d1=c1,c2 d2=c1,c3\n"
    "    d1 marker fcircle msize 0.1 color black err d2 errwidth 0.0706 "
    'key "20"\n'
    "end graph\n"
)

_DATA_CONTENT = "0 0.1 0.01\n1 0.2 0.01\n2 0.3 0.01\n"


@pytest.mark.parametrize("filename", ["20_main.dat", "my-file.dat", "sub/dir/file.dat"])
def test_unquoted_filename_resolves(tmp_path, filename):
    src = _ASYMMETRY_EXPORT.format(filename=filename)
    p = _write(tmp_path, "fig.gle", src, {filename: _DATA_CONTENT})

    rec = parse_gle_figure(p)

    # No filename-resolution warning ('data: ... could not be resolved').
    # (The snippet's per-series 'key "20"' with no graph-level 'key pos'
    # legitimately raises an unrelated 'legend:' warning -- see
    # _apply_legend_recovery -- which is not what this test is about.)
    assert not any(w.startswith("data:") for w in rec.warnings)

    ax = rec.figure.axes_list[0]
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert fs["data_file"] == filename
    assert "data_error" not in fs


def test_quoted_filename_with_spaces_still_works(tmp_path):
    # Guard against the fix regressing the pre-existing quoted-filename path.
    src = (
        "begin graph\n"
        '    data "20 main.dat" d1=c1,c2\n'
        "    d1 line color blue\n"
        "end graph\n"
    )
    p = _write(tmp_path, "fig.gle", src, {"20 main.dat": _DATA_CONTENT})

    rec = parse_gle_figure(p)

    assert not any(w.startswith("data:") for w in rec.warnings)
    ax = rec.figure.axes_list[0]
    assert len(ax.file_series) == 1
    assert ax.file_series[0]["data_file"] == "20 main.dat"


def test_digit_led_data_line_round_trips_byte_identical():
    # emit(parse_gle_source(text)) must reproduce text exactly -- the prime
    # directive of the structural parser layer -- for a line containing a
    # digit-led unquoted filename.
    src = "begin graph\n" "    data 20_main.dat d1=c1,c2 d2=c1,c3\n" "end graph\n"
    doc = parse_gle_source(src)
    assert emit(doc) == src


@pytest.mark.parametrize("filename", ["my-file.dat", "sub/dir/file.dat"])
def test_hyphen_and_path_data_lines_round_trip_byte_identical(filename):
    src = f"begin graph\n    data {filename} d1=c1,c2\nend graph\n"
    doc = parse_gle_source(src)
    assert emit(doc) == src

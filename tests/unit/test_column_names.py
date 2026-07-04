"""Unit tests for Track E3: named column headers in generated data sidecars.

Covers:
- ``gleplot.axes.sanitize_column_name``: the sanitizer rules (charset,
  lowercasing, de-duplication, numeric-collision guard).
- ``column_names`` schema on each series type (line/scatter/bar/fill/
  errorbar), as produced by the plotting methods at ``plot()``-time.
- ``GLEWriter.add_data_file`` header-row emission and the column-count
  validation guard.
- Absent-``column_names`` tolerance on ``Axes.from_dict`` (older projects):
  defaults are regenerated rather than the sidecar silently reverting to
  headerless.
- Round-trip fidelity through ``gleplot.parser.recognizer``, including a
  user-renamed column persisting across save -> parse -> save.

The GLE-side "does a header row change rendering" question (auto-key from
header text) is a writer/GLE-compile concern, covered by
``tests/integration/test_graphics_compilation.py``, not here.
"""

from __future__ import annotations

import numpy as np
import pytest

import gleplot as glp
from gleplot import axes as glp_axes
from gleplot.axes import (
    _build_column_names,
    _build_errorbar_column_names,
    _unique_column_names,
    sanitize_column_name,
)
from gleplot.figure import Figure
from gleplot.parser.recognizer import parse_gle_figure
from gleplot.writer import GLEWriter


@pytest.fixture(autouse=True)
def _reset_counter():
    glp_axes._global_data_file_counter = 0
    glp.close()
    yield
    glp_axes._global_data_file_counter = 0
    glp.close()


# --------------------------------------------------------------------------- #
# Sanitizer rules
# --------------------------------------------------------------------------- #


def test_sanitizer_lowercases():
    assert sanitize_column_name("Signal") == "signal"


def test_sanitizer_replaces_non_word_chars_with_underscore():
    assert sanitize_column_name("V (mV)") == "v_mv"


def test_sanitizer_collapses_repeated_underscores():
    assert sanitize_column_name("a---b") == "a_b"


def test_sanitizer_strips_leading_trailing_underscores():
    assert sanitize_column_name("  !signal!  ") == "signal"


def test_sanitizer_empty_falls_back():
    assert sanitize_column_name("", fallback="y") == "y"
    assert sanitize_column_name("###", fallback="y") == "y"


def test_sanitizer_never_produces_whitespace():
    result = sanitize_column_name("a b\tc\nd")
    assert " " not in result and "\t" not in result and "\n" not in result


def test_sanitizer_purely_numeric_label_gets_prefixed():
    # A bare numeric-looking name would defeat GLE's header auto-detection
    # (GLE requires EVERY first-row cell to fail float parsing), so it must
    # never be returned verbatim.
    result = sanitize_column_name("2024", fallback="y")
    assert result == "y_2024"
    with pytest.raises(ValueError):
        float(result)


def test_sanitizer_numeric_after_sanitizing_gets_prefixed():
    # "1e5" survives the charset filter untouched but IS a float.
    result = sanitize_column_name("1e5", fallback="col")
    with pytest.raises(ValueError):
        float(result)


def test_sanitizer_unicode_becomes_underscore():
    result = sanitize_column_name("café Ω")
    assert result != ""
    for ch in result:
        assert ch in "abcdefghijklmnopqrstuvwxyz0123456789_"


def test_unique_column_names_dedupes_with_suffixes():
    assert _unique_column_names(["x", "y", "y"]) == ["x", "y", "y_2"]
    assert _unique_column_names(["a", "a", "a"]) == ["a", "a_2", "a_3"]


def test_unique_column_names_avoids_colliding_with_existing_suffix():
    # If 'y_2' already appears verbatim before the second 'y', the
    # generated suffix must skip past it.
    assert _unique_column_names(["y", "y_2", "y"]) == ["y", "y_2", "y_3"]


# --------------------------------------------------------------------------- #
# column_names schema per series type
# --------------------------------------------------------------------------- #


def test_line_column_names_default():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])
    assert ax.lines[0]["column_names"] == ["x", "y"]


def test_line_column_names_from_label():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="Signal A")
    assert ax.lines[0]["column_names"] == ["x", "signal_a"]


def test_scatter_column_names():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.scatter([1, 2, 3], [1, 2, 3], label="pts")
    assert ax.scatters[0]["column_names"] == ["x", "pts"]


def test_bar_column_names_default():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [4, 5, 6])
    assert ax.bars[0]["column_names"] == ["x", "height"]


def test_bar_column_names_from_label():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [4, 5, 6], label="counts")
    assert ax.bars[0]["column_names"] == ["x", "counts"]


def test_fill_column_names():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.fill_between([1, 2, 3], [0, 0, 0], [1, 2, 3])
    assert ax.fills[0]["column_names"] == ["x", "upper", "lower"]


def test_errorbar_symmetric_column_names():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.5, label="temp")
    assert ax.errorbars[0]["column_names"] == ["x", "temp", "err"]


def test_errorbar_asymmetric_column_names():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=([0.1, 0.1, 0.1], [0.2, 0.2, 0.2]))
    assert ax.errorbars[0]["column_names"] == ["x", "y", "err_up", "err_down"]


def test_errorbar_xy_column_names():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.1, xerr=0.2)
    assert ax.errorbars[0]["column_names"] == ["x", "y", "err", "xerr"]


def test_column_names_unique_within_file_when_label_collides_with_base_name():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    # Label sanitizes to 'x', colliding with the x column's own name.
    ax.plot([1, 2, 3], [1, 2, 3], label="X")
    names = ax.lines[0]["column_names"]
    assert names[0] == "x"
    assert names[1] == "x_2"
    assert len(set(names)) == len(names)


# --------------------------------------------------------------------------- #
# Writer: header emission + column count guard
# --------------------------------------------------------------------------- #


def test_add_data_file_emits_header_row_first_line():
    writer = GLEWriter()
    writer.add_data_file(
        "d.dat", [np.array([1.0, 2.0]), np.array([3.0, 4.0])],
        column_names=["x", "signal"],
    )
    content = writer.data_files["d.dat"]
    assert content.splitlines()[0] == "x signal"
    assert content.splitlines()[1] == "1 3"


def test_add_data_file_no_header_when_column_names_absent():
    writer = GLEWriter()
    writer.add_data_file("d.dat", [np.array([1.0]), np.array([2.0])])
    content = writer.data_files["d.dat"]
    assert content.splitlines()[0] == "1 2"


def test_add_data_file_rejects_mismatched_column_count():
    writer = GLEWriter()
    with pytest.raises(ValueError):
        writer.add_data_file(
            "d.dat", [np.array([1.0]), np.array([2.0])],
            column_names=["x", "y", "extra"],
        )


# --------------------------------------------------------------------------- #
# key clause: header present but no label -> explicit key "" (never bare
# omission), preserving pre-header-row rendering (see writer._key_clause).
# --------------------------------------------------------------------------- #


def test_unlabeled_line_gets_explicit_empty_key_when_header_present():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3])  # no label
    text, _ = fig._generate_gle_with_files()
    assert 'key ""' in text


def test_labeled_line_key_unaffected_by_header():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="sig")
    text, _ = fig._generate_gle_with_files()
    assert 'key "sig"' in text
    assert 'key ""' not in text


def test_unlabeled_bar_gets_standalone_key_suppression_line():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.bar([1, 2, 3], [4, 5, 6])
    text, _ = fig._generate_gle_with_files()
    assert 'd1 key ""' in text


def test_unlabeled_fill_gets_standalone_key_suppression_lines():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.fill_between([1, 2, 3], [0, 0, 0], [1, 2, 3])
    text, _ = fig._generate_gle_with_files()
    assert text.count('key ""') == 2


# --------------------------------------------------------------------------- #
# Absent-key tolerance: older projects regenerate defaults
# --------------------------------------------------------------------------- #


def test_from_dict_regenerates_column_names_when_absent():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="sig")
    d = fig.to_dict()
    del d["figure"]["axes"][0]["lines"][0]["column_names"]  # simulate old project

    fig2 = Figure.from_dict(d)
    assert fig2.axes_list[0].lines[0]["column_names"] == ["x", "sig"]


def test_from_dict_regenerates_errorbar_column_names_when_absent():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.5)
    d = fig.to_dict()
    del d["figure"]["axes"][0]["errorbars"][0]["column_names"]

    fig2 = Figure.from_dict(d)
    assert fig2.axes_list[0].errorbars[0]["column_names"] == ["x", "y", "err"]


def test_from_dict_preserves_column_names_when_present():
    fig = glp.figure(data_prefix="t")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 2, 3], label="sig")
    d = fig.to_dict()
    d["figure"]["axes"][0]["lines"][0]["column_names"] = ["x", "renamed"]

    fig2 = Figure.from_dict(d)
    assert fig2.axes_list[0].lines[0]["column_names"] == ["x", "renamed"]


# --------------------------------------------------------------------------- #
# Round-trip through the recognizer, including a renamed column
# --------------------------------------------------------------------------- #


def test_round_trip_recovers_column_names(tmp_path):
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [4, 5, 6], label="Signal")

    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    recognized = parse_gle_figure(gle_path)
    ax2 = recognized.figure.axes_list[0]
    assert ax2.lines[0]["column_names"] == ["x", "signal"]


def test_round_trip_user_renamed_column_persists(tmp_path):
    """A hand-edited header (simulating a user rename in an external editor,
    or a future GUI rename feature) survives parse -> re-save verbatim.
    """
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [4, 5, 6])

    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    dat_path = tmp_path / "rt_0.dat"
    lines = dat_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "x y"
    lines[0] = "x custom_name"
    dat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    recognized = parse_gle_figure(gle_path)
    ax2 = recognized.figure.axes_list[0]
    assert ax2.lines[0]["column_names"] == ["x", "custom_name"]

    # Re-save: the renamed header must be regenerated verbatim.
    out_dir = tmp_path / "resave"
    out_dir.mkdir()
    recognized.figure.savefig_gle(str(out_dir / "f.gle"))
    resaved = (out_dir / "rt_0.dat").read_text(encoding="utf-8").splitlines()
    assert resaved[0] == "x custom_name"


def test_round_trip_errorbar_column_names_full_cycle(tmp_path):
    fig = glp.figure(data_prefix="rt")
    ax = fig.add_subplot(111)
    ax.errorbar([1, 2, 3], [4, 5, 6], yerr=0.5, label="temp")

    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    recognized = parse_gle_figure(gle_path)
    ax2 = recognized.figure.axes_list[0]
    assert ax2.errorbars[0]["column_names"] == ["x", "temp", "err"]

    out_dir = tmp_path / "resave"
    out_dir.mkdir()
    recognized.figure.savefig_gle(str(out_dir / "f.gle"))
    original_bytes = (tmp_path / "rt_0.dat").read_bytes()
    resaved_bytes = (out_dir / "rt_0.dat").read_bytes()
    assert resaved_bytes == original_bytes


def test_headerless_hand_written_dat_gets_default_column_names(tmp_path):
    """A gleplot-authored .gle referencing a headerless .dat (no header row
    at all) still gets column_names populated with the stable defaults on
    parse, so it acquires a header on next save rather than staying
    headerless forever.

    Post Finding 1, a file is only recognized as an "import" series
    (array-backed ax.lines entry, which is what carries column_names) when
    the '! gleplot' metadata block's import-data list vouches for it. A
    metadata-less reference is treated as an external "reference"
    (file_series) instead. This fixture therefore includes the metadata
    block that gleplot's own writer emits.
    """
    dat_path = tmp_path / "series_1.dat"
    dat_path.write_text("1 2\n2 4\n3 6\n", encoding="utf-8")
    gle_path = tmp_path / "f.gle"
    gle_path.write_text(
        "! GLE graphics file\n"
        "! Generated by gleplot\n"
        "! gleplot-meta-begin v1\n"
        "! gleplot: import-data = series_1.dat\n"
        "! gleplot-meta-end\n"
        "size 10 10\n"
        "begin graph\n"
        "    data series_1.dat d1=c1,c2\n"
        "    d1 line color blue\n"
        "end graph\n",
        encoding="utf-8",
    )

    recognized = parse_gle_figure(gle_path)
    ax = recognized.figure.axes_list[0]
    assert len(ax.lines) == 1
    assert ax.lines[0]["column_names"] == ["x", "y"]

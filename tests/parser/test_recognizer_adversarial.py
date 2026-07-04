"""Regression tests for the adversarial-review fixes to the GLE recognizer.

Each test reproduces a specific finding's bug (using the reviewer's repro
snippets) and asserts the fixed behavior. Findings are numbered to match the
review. The byte-identical fixed-point guard (``test_fixed_point.py``) covers
gleplot-authored files; these target *hand-written* tolerance.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gleplot import Figure
from gleplot.parser.recognizer import parse_gle_figure


def _write(tmp_path: Path, name: str, content: str, dats: dict | None = None) -> Path:
    for dat_name, dat_content in (dats or {}).items():
        (tmp_path / dat_name).write_text(dat_content, encoding="utf-8")
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Finding 1 -- quoted data filenames
# --------------------------------------------------------------------------- #

def test_finding1_quoted_data_filename_resolves_and_imports(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   data "data_3.dat" d1=c1,c2\n'
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    # data_3.dat matches the sidecar heuristic -> import (arrays loaded).
    p = _write(tmp_path, "q.gle", src, {"data_3.dat": "0 0\n5 1\n10 0\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # The quoted name must be UNWRAPPED: it resolves and loads as a line.
    assert len(ax.lines) == 1
    assert ax.lines[0]["data_file"] == "data_3.dat"
    assert list(ax.lines[0]["x"]) == [0.0, 5.0, 10.0]
    assert not any('"' in (s.get("data_file") or "") for s in ax.file_series)


def test_finding1_quoted_missing_file_warns_and_broken_ref(tmp_path):
    # Previously-masked path: quoted name + missing file -> data: warning +
    # broken-reference entry (not silent).
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   data "data_9.dat" d1=c1,c2\n'
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "q.gle", src)  # no data file written
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.lines == []
    assert len(ax.file_series) == 1
    assert ax.file_series[0]["data_file"] == "data_9.dat"
    assert "data_error" in ax.file_series[0]
    assert any(w.startswith("data:") for w in rec.warnings)


def test_finding1_out_of_range_column_warns(tmp_path):
    # Column c9 doesn't exist -> data: warning + broken-reference entry.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   data "data_2.dat" d1=c1,c9\n'
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "q.gle", src, {"data_2.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.lines == []
    assert len(ax.file_series) == 1
    assert "data_error" in ax.file_series[0]
    assert any(w.startswith("data:") for w in rec.warnings)


def test_finding1_header_and_comment_and_ragged(tmp_path):
    # Hand-written data command (quoted filename) referencing a
    # header+comment+ragged whitespace-delimited file.
    dat = (
        "! a comment\n"
        "x y\n"        # header row
        "0 0\n"
        "1 2\n"
        "2 4\n"
    )
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   data "data_1.dat" d1=c1,c2\n'
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "q.gle", src, {"data_1.dat": dat})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # The quoted filename resolved (header + comment lines skipped by loader).
    assert len(ax.lines) == 1
    x = list(ax.lines[0]["x"])
    assert x == [0.0, 1.0, 2.0]
    assert list(ax.lines[0]["y"]) == [0.0, 2.0, 4.0]


# --------------------------------------------------------------------------- #
# Finding 2 / 10 -- multi-line dN attribute accumulation + forward references
# --------------------------------------------------------------------------- #

def test_finding2_multiline_dn_attributes_single_series(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_4.dat d1=c1,c2\n"
        "   d1 line color red\n"
        "   d1 lwidth 0.05\n"
        '   d1 key "A"\n'
        "end graph\n"
    )
    p = _write(tmp_path, "m.gle", src, {"data_4.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # ONE line series, not three.
    assert len(ax.lines) == 1
    s = ax.lines[0]
    assert s["color"] == "red"
    assert s["label"] == "A"


def test_finding10_forward_reference_before_data(tmp_path):
    # 'd1 line ...' appears BEFORE its 'data' command.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   d1 line color green lwidth 0.05\n"
        "   data data_5.dat d1=c1,c2\n"
        "end graph\n"
    )
    p = _write(tmp_path, "f.gle", src, {"data_5.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.lines) == 1
    assert ax.lines[0]["color"] == "green"


def test_finding2_last_wins_warns_on_overwrite(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_6.dat d1=c1,c2\n"
        "   d1 line color red\n"
        "   d1 color blue\n"     # overwrites color -> last wins
        "end graph\n"
    )
    p = _write(tmp_path, "lw.gle", src, {"data_6.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.lines) == 1
    assert ax.lines[0]["color"] == "blue"  # last wins


# --------------------------------------------------------------------------- #
# Finding 3 -- _build_file_series drops line+marker
# --------------------------------------------------------------------------- #

def test_finding3_file_series_line_with_marker(tmp_path):
    # external.csv is NOT a sidecar name -> reference path (file_series).
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data external.csv d1=c1,c2\n"
        "   d1 line marker circle lwidth 0.08 lstyle 2\n"
        "end graph\n"
    )
    p = _write(tmp_path, "fs.gle", src, {"external.csv": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    # Line properties are preserved, not dropped by errorbar-classification.
    assert fs["series_type"] == "line"
    assert fs["linestyle"] == "--"      # lstyle 2
    assert fs["linewidth"] > 0
    assert fs.get("marker") == "circle"  # marker kept as additional field


# --------------------------------------------------------------------------- #
# Finding 4 -- axis unknown tokens preserved cumulatively
# --------------------------------------------------------------------------- #

def test_finding4_axis_remainder_passthrough(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_7.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "   xaxis min 0 max 2*pi dticks pi/2 grid\n"
        "end graph\n"
    )
    p = _write(tmp_path, "ax.gle", src, {"data_7.dat": "0 0\n6 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # Recognized min/max go to the model.
    assert ax.xmin == 0
    assert abs(ax.xmax - 6.283185307179586) < 1e-9
    # Unrecognized remainder re-emitted as a supplementary axis line.
    joined = "\n".join(ax.passthrough)
    assert "xaxis" in joined and "dticks" in joined and "grid" in joined
    assert any(w.startswith("structure:") and "xaxis" in w for w in rec.warnings)


def test_finding4_axis_string_option_keeps_quotes(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_8.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        '   xaxis min 0 max 10 format "fix 2"\n'
        "end graph\n"
    )
    p = _write(tmp_path, "axs.gle", src, {"data_8.dat": "0 0\n10 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    joined = "\n".join(ax.passthrough)
    assert 'format "fix 2"' in joined


def test_finding4_axis_remainder_compiles_in_gle(tmp_path):
    # The reconstructed passthrough line + model-emitted axis line together must
    # compile in real GLE and reproduce the cumulative result.
    import shutil
    import subprocess

    gle_exe = shutil.which("gle") or r"C:\Program Files\GLE\bin\gle.exe"
    if not Path(gle_exe).exists():
        pytest.skip("GLE not installed")

    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_7.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "   xaxis min 0 max 2*pi dticks pi/2 grid\n"
        "end graph\n"
    )
    p = _write(tmp_path, "ax.gle", src, {"data_7.dat": "0 0\n6 1\n"})
    rec = parse_gle_figure(p)
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    # Compile the re-saved file with GLE.
    res = subprocess.run(
        [gle_exe, "-d", "png", "-o", str(tmp_path / "out.png"), str(out)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert res.returncode == 0, f"GLE failed:\n{res.stdout}\n{res.stderr}"
    assert (tmp_path / "out.png").exists()


# --------------------------------------------------------------------------- #
# Finding 5 -- title / key trailing modifiers kept raw
# --------------------------------------------------------------------------- #

def test_finding5_title_with_options_kept_raw(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_a.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        '   title "T" hei 0.6 font roman\n'
        "end graph\n"
    )
    p = _write(tmp_path, "t.gle", src, {"data_a.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # Title text left UNSET (empty) -> the writer emits no competing title line.
    assert ax.title_text == ""
    joined = "\n".join(ax.passthrough)
    assert 'title "T" hei 0.6 font roman' in joined
    assert any("title has unsupported options" in w for w in rec.warnings)
    # Re-save: the raw title line appears exactly once, no empty duplicate.
    out = tmp_path / "t2.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert text.count('title "T"') == 1


def test_finding5_key_with_options_kept_raw(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_b.dat d1=c1,c2\n"
        '   d1 line color blue lwidth 0.05 key "s"\n'
        "   key pos tr hei 0.3 nobox offset 0.2 0.2\n"
        "end graph\n"
    )
    p = _write(tmp_path, "k.gle", src, {"data_b.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    joined = "\n".join(ax.passthrough)
    assert "key pos tr hei 0.3 nobox offset 0.2 0.2" in joined
    assert any("key has unsupported options" in w for w in rec.warnings)


def test_finding5_plain_title_still_modeled(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_c.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        '   title "Plain"\n'
        "end graph\n"
    )
    p = _write(tmp_path, "tp.gle", src, {"data_c.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.title_text == "Plain"


# --------------------------------------------------------------------------- #
# Finding 6 -- no fabricated empty graph
# --------------------------------------------------------------------------- #

def test_finding6_graph_in_translate_no_fabricated_graph(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin translate 2 2\n"
        "begin graph\n"
        "   data inner.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
        "end translate\n"
    )
    p = _write(tmp_path, "tr.gle", src, {"inner.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    # No axes recovered (graph is inside the opaque wrapper).
    assert rec.figure.axes_list == []
    # Warning about the swallowed graph.
    assert any("graph inside begin translate" in w for w in rec.warnings)
    # Re-save must NOT fabricate an empty 'begin graph ... end graph'.
    out = tmp_path / "tr2.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    # The only 'begin graph' is the original inside the translate wrapper.
    assert text.count("begin graph") == 1
    assert "begin translate 2 2" in text
    assert "end translate" in text


def test_finding6_empty_figure_keeps_default_graph():
    # A genuinely empty figure with NO passthrough keeps the historical
    # default empty graph block.
    f = Figure()
    text = f._generate_gle()
    assert "begin graph" in text and "end graph" in text


# --------------------------------------------------------------------------- #
# Finding 7 -- metadata block inside a graph body
# --------------------------------------------------------------------------- #

def test_finding7_metadata_inside_graph_not_duplicated(tmp_path):
    src = (
        "! GLE graphics file\n"
        "! Generated by gleplot\n"
        "! gleplot-meta-begin v1\n"
        "! gleplot: dpi = 150\n"
        "! gleplot: import-data = data_d.dat\n"
        "! gleplot-meta-end\n"
        "\n"
        "size 20.32 15.24\n"
        "begin graph\n"
        "! gleplot-meta-begin v1\n"
        "! gleplot: dpi = 150\n"
        "! gleplot-meta-end\n"
        "   data data_d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "md.gle", src, {"data_d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # The stray metadata lines inside the graph body must NOT land in passthrough.
    joined = "\n".join(ax.passthrough)
    assert "gleplot-meta-begin" not in joined
    assert "gleplot: dpi" not in joined
    assert rec.figure.dpi == 150


# --------------------------------------------------------------------------- #
# Finding 8 -- data command auto-mapping
# --------------------------------------------------------------------------- #

def test_finding8_auto_mapping_multicolumn(tmp_path):
    # 'data f.dat' with no dN clauses, 3-column file -> d1=c1,c2 d2=c1,c3.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_50.dat\n"
        "   d1 line color blue lwidth 0.05\n"
        "   d2 line color red lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "am.gle", src, {"data_50.dat": "0 10 100\n1 20 200\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.lines) == 2
    d1 = next(s for s in ax.lines if s["color"] == "blue")
    d2 = next(s for s in ax.lines if s["color"] == "red")
    assert list(d1["y"]) == [10.0, 20.0]   # c2
    assert list(d2["y"]) == [100.0, 200.0]  # c3
    assert list(d1["x"]) == [0.0, 1.0]      # c1


def test_finding8_auto_mapping_single_column(tmp_path):
    # Single-column file -> d1 = index, c1 (nox).
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_51.dat\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "am1.gle", src, {"data_51.dat": "5\n6\n7\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.lines) == 1
    assert list(ax.lines[0]["y"]) == [5.0, 6.0, 7.0]
    assert list(ax.lines[0]["x"]) == [1.0, 2.0, 3.0]  # 1-based index


def test_finding8_auto_mapping_unresolved_warns(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data missing.dat\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "am_miss.gle", src)
    rec = parse_gle_figure(p)
    assert any(w.startswith("data:") for w in rec.warnings)


# --------------------------------------------------------------------------- #
# Finding 9 -- positional dataset names
# --------------------------------------------------------------------------- #

def test_finding9_positional_dataset_names(tmp_path):
    # 'data f.dat d1 d3' -> d1 gets y=c2 (position 0), d3 gets y=c3 (position 1).
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_52.dat d1 d3\n"
        "   d1 line color blue lwidth 0.05\n"
        "   d3 line color red lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "pos.gle", src, {"data_52.dat": "0 10 100\n1 20 200\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.lines) == 2
    d1 = next(s for s in ax.lines if s["color"] == "blue")
    d3 = next(s for s in ax.lines if s["color"] == "red")
    assert list(d1["y"]) == [10.0, 20.0]   # position 0 -> c2
    assert list(d3["y"]) == [100.0, 200.0]  # position 1 -> c3


# --------------------------------------------------------------------------- #
# Finding 11 -- literal / percentage error bars
# --------------------------------------------------------------------------- #

def test_finding11_constant_error_converted(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_53.dat d1=c1,c2\n"
        "   d1 marker circle err 0.5\n"
        "end graph\n"
    )
    p = _write(tmp_path, "err.gle", src, {"data_53.dat": "0 2\n1 4\n2 8\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.errorbars) == 1
    eb = ax.errorbars[0]
    assert list(eb["yerr_up"]) == [0.5, 0.5, 0.5]
    assert list(eb["yerr_down"]) == [0.5, 0.5, 0.5]
    assert any("constant error expression converted" in w for w in rec.warnings)


def test_finding11_percentage_error_converted(tmp_path):
    # 'err 10%' -> per-point 0.10 * abs(y).
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_54.dat d1=c1,c2\n"
        "   d1 marker circle err 10%\n"
        "end graph\n"
    )
    p = _write(tmp_path, "errp.gle", src, {"data_54.dat": "0 2\n1 4\n2 8\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.errorbars) == 1
    eb = ax.errorbars[0]
    assert list(eb["yerr_up"]) == pytest.approx([0.2, 0.4, 0.8])


def test_finding11_constant_error_broken_ref_keeps_raw(tmp_path):
    # y data unavailable (broken ref) -> warn + keep original dN line raw.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data missing_h.dat d1=c1,c2\n"
        "   d1 marker circle err 0.5\n"
        "end graph\n"
    )
    p = _write(tmp_path, "errbroken.gle", src)
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.errorbars == []
    joined = "\n".join(ax.passthrough)
    assert "err 0.5" in joined
    assert any(w.startswith("data:") for w in rec.warnings)


# --------------------------------------------------------------------------- #
# Finding 12 -- duplicate data command redefining a dataset
# --------------------------------------------------------------------------- #

def test_finding12_duplicate_data_redefinition_warns(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_55.dat d1=c1,c2\n"
        "   data data_55.dat d1=c1,c3\n"   # redefines d1
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "dup.gle", src, {"data_55.dat": "0 10 100\n1 20 200\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    # Last-wins: d1 uses c3.
    assert len(ax.lines) == 1
    assert list(ax.lines[0]["y"]) == [100.0, 200.0]
    assert any("redefined" in w for w in rec.warnings)


# --------------------------------------------------------------------------- #
# Finding 13 -- programmatic-construct guard
# --------------------------------------------------------------------------- #

def test_finding13_programmatic_sub_warns(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "sub myplot\n"
        "   begin graph\n"
        "      data data_k.dat d1=c1,c2\n"
        "      d1 line color blue lwidth 0.05\n"
        "   end graph\n"
        "end sub\n"
        "myplot\n"
    )
    p = _write(tmp_path, "prog.gle", src, {"data_k.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    assert any(w.startswith("programmatic:") for w in rec.warnings)


def test_finding13_for_loop_warns(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "for i = 1 to 3\n"
        "   amove i i\n"
        "next i\n"
    )
    p = _write(tmp_path, "loop.gle", src)
    rec = parse_gle_figure(p)
    assert any(w.startswith("programmatic:") for w in rec.warnings)


def test_finding13_normal_file_no_programmatic_warning(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data data_l.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "normal.gle", src, {"data_l.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    assert not any(w.startswith("programmatic:") for w in rec.warnings)

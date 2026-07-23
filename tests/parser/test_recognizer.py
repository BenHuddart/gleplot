"""Tests for the semantic recognizer (Track B1).

Covers, beyond the byte-identical fixed-point guard in ``test_fixed_point.py``:

* ``to_dict`` equivalence up to the documented normalizations (a ``normalize``
  helper here encodes exactly those documented cases).
* Broken-data recovery (deleted ``.dat`` -> file_series entry with
  ``data_error`` + warning; re-save emits the ``data`` command verbatim).
* Hand-written tolerance: ~8 crafted files exercising attribute-order shuffle,
  cumulative axis lines, arithmetic expressions, single quotes, semicolons,
  British ``GREY``, unknown statements in all three passthrough positions, an
  opaque block inside a graph, a no-metadata (heuristics) file, and a
  missing-grid multi-graph fallback.
* ``gleplot.open_gle`` smoke.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot
from gleplot import Figure, axes as _gleplot_axes
from gleplot.parser.recognizer import RecognizedFigure, parse_gle_figure

from tests.parser import _golden_battery as golden


@pytest.fixture(autouse=True)
def _reset_counter():
    _gleplot_axes._global_data_file_counter = 0
    gleplot.close()
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        gleplot.close()


# --------------------------------------------------------------------------- #
# to_dict equivalence up to documented normalizations
# --------------------------------------------------------------------------- #


def normalize(d: dict) -> dict:
    """Apply the documented recognizer normalizations to a figure ``to_dict``.

    These are the intentional, render-lossless differences between the original
    figure and the recognized one (see ``recognizer.py`` module docstring). By
    applying them to BOTH sides we can assert semantic equivalence.

    Encoded cases:
      * fontsize: snapped through the 6-sig-fig ``set hei`` cm round-trip.
      * markersize / linewidth: snapped through the emitted GLE value
        (msize verbatim; linewidth via pt<->cm; API default 1 -> 1.5).
      * legend_on: explicit True with labels present -> None (auto).
      * data_prefix / counters: dropped (not always recoverable).
      * global_data_counter: dropped.
      * axis limits: rounded to the emitted 6-sig-fig form.
    """
    import copy

    from gleplot.parser.units import (
        fontsize_cm_to_pt,
        fontsize_pt_to_cm,
        linewidth_cm_to_pt,
        linewidth_pt_to_cm,
    )
    from gleplot.writer import GLEWriter

    d = copy.deepcopy(d)
    fig = d["figure"]

    # figsize is recovered as float (cm->inches) even if the source used int
    # literals; same value, coerce both sides to float for comparison.
    if fig.get("figsize") is not None:
        fig["figsize"] = [float(v) for v in fig["figsize"]]

    # Figure-level: drop data-naming/counter state that need not round-trip.
    for k in (
        "data_prefix",
        "local_data_counter",
        "global_data_counter",
        "used_data_files",
        "subplot_adjust",
    ):
        fig.pop(k, None)

    # fontsize -> emitted cm -> pt.
    style = fig["config"]["style"]
    fs = style.get("fontsize")
    if isinstance(fs, (int, float)):
        emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(fs)))
        style["fontsize"] = fontsize_cm_to_pt(float(emitted))

    def _snap_linewidth(v):
        # Writer substitutes default_linewidth (1.5) for API defaults 0/1.
        pt = 1.5 if v in (0, 1) else v
        emitted = GLEWriter._format_number(linewidth_pt_to_cm(float(pt)))
        return linewidth_cm_to_pt(float(emitted))

    def _snap_msize(v):
        if v is None:
            return v
        return float(GLEWriter._format_number(float(v)))

    def _snap_num(v):
        if not isinstance(v, (int, float)):
            return v
        return float(GLEWriter._format_number(float(v)))

    def _snap_array(v):
        if isinstance(v, list):
            return [_snap_num(e) for e in v]
        return v

    # Data arrays are written to the .dat sidecar at 6 significant figures, so
    # recovered arrays are rounded. Snap BOTH sides to that emitted precision.
    _ARRAY_KEYS = {
        "lines": ("x", "y"),
        "scatters": ("x", "y"),
        "bars": ("x", "height"),
        "fills": ("x", "y1", "y2"),
        "errorbars": ("x", "y", "yerr_up", "yerr_down", "xerr_left", "xerr_right"),
    }

    for ax in fig["axes"]:
        # legend tri-state normalization: explicit True with labels -> None.
        labels = any(
            s.get("label")
            for group in ("lines", "scatters", "bars", "errorbars", "file_series")
            for s in ax.get(group, [])
        )
        if ax.get("legend_on") is True and labels:
            ax["legend_on"] = None

        # axis limits snap to emitted precision.
        for lim in ("xmin", "xmax", "ymin", "ymax", "y2min", "y2max"):
            if ax.get(lim) is not None:
                ax[lim] = _snap_num(ax[lim])

        for group in ("lines", "scatters", "errorbars"):
            for s in ax.get(group, []):
                if "markersize" in s:
                    s["markersize"] = _snap_msize(s["markersize"])
                if "linewidth" in s:
                    s["linewidth"] = _snap_linewidth(s["linewidth"])
        for s in ax.get("file_series", []):
            if "markersize" in s:
                s["markersize"] = _snap_msize(s["markersize"])
            if "linewidth" in s:
                s["linewidth"] = _snap_linewidth(s["linewidth"])

        # Data arrays snap to emitted precision.
        for group, keys in _ARRAY_KEYS.items():
            for s in ax.get(group, []):
                for k in keys:
                    if s.get(k) is not None:
                        s[k] = _snap_array(s[k])

        # fill_between alpha is not representable in GLE (writer ignores it);
        # drop it. Its data arrays already snapped above.
        for s in ax.get("fills", []):
            s.pop("alpha", None)

        # Text annotations: fontsize round-trips through cm (snap); box_color
        # is accepted-but-ignored by the writer (never emitted) -> drop.
        #
        # Sticky-fontsize normalization: 'set hei' is GLE interpreter-global
        # state (see recognizer._try_one_text / writer.add_text). The writer
        # only emits 'set hei' when a text's fontsize DIFFERS from whatever is
        # currently active -- so a text with fontsize=None (or one equal to
        # the already-active height) genuinely renders in real GLE at the
        # last-explicit height, not some independent default. The recognizer
        # correctly resolves that inherited value on recovery (it cannot tell
        # "no explicit set hei" apart from "same value restated"). Both sides
        # are therefore normalized to the STICKY-RESOLVED height, seeded from
        # the style default (the preamble's unconditional 'set hei'), matching
        # the value real GLE would use when rendering each text in sequence.
        sticky_fs = style.get("fontsize")
        for s in ax.get("texts", []):
            fs = s.get("fontsize")
            if fs is None:
                fs = sticky_fs
            emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(fs)))
            s["fontsize"] = fontsize_cm_to_pt(float(emitted))
            sticky_fs = s["fontsize"]
            s.pop("box_color", None)

    return d


@pytest.mark.parametrize("name", golden.BUILDER_IDS)
def test_to_dict_equivalence(name, tmp_path):
    """Original and recognized figures agree up to documented normalizations."""
    builder = getattr(golden, name)

    _gleplot_axes._global_data_file_counter = 0
    fig = builder()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    original = fig.to_dict()

    _gleplot_axes._global_data_file_counter = 0
    recognized = parse_gle_figure(gle_path).figure
    recovered = recognized.to_dict()

    assert normalize(recovered) == normalize(original)


# --------------------------------------------------------------------------- #
# Broken-data recovery
# --------------------------------------------------------------------------- #


def test_broken_data_becomes_file_series_with_error(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = golden.single_line()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    # Delete the sidecar so the reference is broken.
    (tmp_path / "golden_0.dat").unlink()

    recognized = parse_gle_figure(gle_path)
    ax = recognized.figure.axes_list[0]

    # The import line became a file_series reference carrying data_error.
    assert ax.lines == []
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert fs["data_file"] == "golden_0.dat"
    assert "data_error" in fs and fs["data_error"]

    # A warning was recorded.
    assert any(w.startswith("data:") for w in recognized.warnings)

    # Re-save emits the same data command verbatim (GLE will fail at compile
    # with its own missing-file error -- an honest preview).
    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "data golden_0.dat d1=c1,c2" in text


# --------------------------------------------------------------------------- #
# Hand-written tolerance
# --------------------------------------------------------------------------- #


def _write(tmp_path: Path, name: str, content: str, dats: dict | None = None) -> Path:
    for dat_name, dat_content in (dats or {}).items():
        (tmp_path / dat_name).write_text(dat_content, encoding="utf-8")
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_attribute_order_shuffled_and_grey(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min -1 max 1\n"
        "   data wave_1.dat d1=c1,c2\n"
        # shuffled attributes + GREY color + single quote label
        "   d1 key 'w' lstyle 2 color GREY line lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "s.gle", src, {"wave_1.dat": "0 0\n5 1\n10 0\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    series = (ax.lines or ax.file_series)[0]
    assert series["color"] == "GREY"
    assert series["linestyle"] == "--"
    assert series["label"] == "w"
    assert ax.xmin == 0 and ax.xmax == 10 and ax.ymin == -1


def test_cumulative_axis_lines(tmp_path):
    # Two xaxis lines: min on one, max+log on the next (hand-written style).
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 1\n"
        "   xaxis max 100 log\n"
        "   yaxis min 1 max 10\n"
        "   data pts_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "c.gle", src, {"pts_1.dat": "1 1\n100 10\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    assert ax.xmin == 1 and ax.xmax == 100
    assert ax.xscale == "log"


def test_arithmetic_expressions_in_numbers(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 0 max 2*pi\n"
        "   yaxis min -1 max 1\n"
        "   data e_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "e.gle", src, {"e_1.dat": "0 0\n6 0\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    assert abs(ax.xmax - 6.283185307179586) < 1e-9


def test_semicolon_joined_statements(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 1 max 3; yaxis min 1 max 3\n"
        "   data sc_1.dat d1=c1,c2\n"
        "   d1 line color RED lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "sc.gle", src, {"sc_1.dat": "1 1\n3 3\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    assert ax.xmin == 1 and ax.xmax == 3 and ax.ymin == 1 and ax.ymax == 3


def test_unknown_statements_in_all_bucket_positions(tmp_path):
    src = (
        "! GLE graphics file\n"
        "! hand note\n"
        "set weird_directive 7\n"  # header passthrough
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data u_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "   mystery_stmt inside graph\n"  # axes passthrough
        "end graph\n"
        "! trailing note\n"  # trailer passthrough
        "draw somebox\n"  # trailer passthrough
    )
    p = _write(tmp_path, "u.gle", src, {"u_1.dat": "1 1\n2 2\n"})
    rec = parse_gle_figure(p)
    fig = rec.figure
    assert "set weird_directive 7" in fig.passthrough_header
    assert "! hand note" in fig.passthrough_header
    assert any("mystery_stmt" in line for line in fig.axes_list[0].passthrough)
    assert any("trailing note" in line for line in fig.passthrough_trailer)
    assert any("draw somebox" in line for line in fig.passthrough_trailer)

    # Passthrough lines survive verbatim on re-save.
    out = tmp_path / "u2.gle"
    fig.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "set weird_directive 7" in text
    assert "mystery_stmt inside graph" in text
    assert "! trailing note" in text
    assert "draw somebox" in text


def test_opaque_block_inside_graph_becomes_axes_passthrough(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data o_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "   begin object thing\n"
        "      raw line one\n"
        "      raw line two\n"
        "   end object\n"
        "end graph\n"
    )
    p = _write(tmp_path, "o.gle", src, {"o_1.dat": "1 1\n2 2\n"})
    rec = parse_gle_figure(p)
    pt = rec.figure.axes_list[0].passthrough
    joined = "\n".join(pt)
    assert "begin object thing" in joined
    assert "raw line one" in joined
    assert "end object" in joined

    # Re-save keeps the opaque block verbatim inside the graph block.
    out = tmp_path / "o2.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "begin object thing" in text
    assert "raw line two" in text


def test_no_metadata_block_all_references(tmp_path):
    # Finding 1: with NO '! gleplot' metadata block, classification is
    # conservative -- EVERY data reference is treated as an external
    # 'reference' (file_series), regardless of filename. A sidecar-looking
    # name like 'data_5.dat' is NOT adopted as an import (which would let a
    # later save rewrite a user's file). Both files land in file_series and
    # nothing is loaded into ax.lines.
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data data_5.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "   data other.csv d2=c1,c2\n"
        "   d2 line color RED lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(
        tmp_path,
        "h.gle",
        src,
        {"data_5.dat": "1 1\n2 2\n", "other.csv": "1 2\n2 1\n"},
    )
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.lines == []
    referenced = {fs["data_file"] for fs in ax.file_series}
    assert referenced == {"data_5.dat", "other.csv"}


def test_missing_grid_multigraph_falls_back(tmp_path):
    # Two graph blocks with NO amove positions -> n x 1 fallback + warning.
    src = (
        "size 15 20\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data g_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
        "begin graph\n"
        "   data h_1.dat d1=c1,c2\n"
        "   d1 line color RED lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(
        tmp_path,
        "mg.gle",
        src,
        {"g_1.dat": "1 1\n2 2\n", "h_1.dat": "1 2\n2 1\n"},
    )
    rec = parse_gle_figure(p)
    positions = [ax.position for ax in rec.figure.axes_list]
    assert positions == [(2, 1, 1), (2, 1, 2)]
    assert any(w.startswith("layout:") for w in rec.warnings)


# --------------------------------------------------------------------------- #
# open_gle smoke
# --------------------------------------------------------------------------- #


def test_open_gle_smoke(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = golden.single_line()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    opened = gleplot.open_gle(gle_path)
    assert isinstance(opened, Figure)
    assert len(opened.axes_list) == 1
    assert opened.axes_list[0].title_text == "single line"


def test_parse_gle_figure_accepts_raw_text(tmp_path):
    # Raw source text (multi-line) is parsed directly, using base_dir for data.
    (tmp_path / "raw_1.dat").write_text("1 1\n2 2\n", encoding="utf-8")
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data raw_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
    )
    rec = parse_gle_figure(src, base_dir=tmp_path)
    assert isinstance(rec, RecognizedFigure)
    assert len(rec.figure.axes_list) == 1

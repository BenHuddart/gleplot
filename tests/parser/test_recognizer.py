"""Tests for the semantic recognizer (Track B1).

Covers, beyond the byte-identical fixed-point guard in ``test_fixed_point.py``:

* ``to_dict`` equivalence up to the documented normalizations (a ``normalize``
  helper here encodes exactly those documented cases).
* Broken-data recovery (deleted ``.dat`` -> file_series entry with
  ``data_error`` + warning; re-save emits the ``data`` command verbatim).
* Hand-written tolerance: ~8 crafted files exercising attribute-order shuffle,
  cumulative axis lines, arithmetic expressions, single quotes, semicolons,
  British ``GREY``, unknown statements in all three passthrough positions, an
  opaque block inside a graph, a no-metadata (heuristics) file, a
  missing-grid multi-graph fallback, and custom marker definitions
  (``define marker`` with its sub, ``defmarker``).
* ``gleplot.open_gle`` smoke.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np
import pytest

import gleplot
from gleplot import Figure
from gleplot import axes as _gleplot_axes
from gleplot.colors import rgb_to_gle
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
        (msize verbatim; linewidth via pt<->cm; API default 0 or 1 -> the
        style's ``default_linewidth``, unless the series is
        ``_lwidth_verbatim``; that marker is dropped).
      * default_color / default_marker_color: recorded as the GLE colour
        they draw.
      * legend_on: explicit True with labels present -> None (auto).
      * legend_spacing: equal to 5 significant figures (emitted in cm).
      * suptitle: one off its default place reads back as the first figure
        text; figure text and figure legend sizes go through ``set hei``.
      * data_prefix / counters: dropped (not always recoverable).
      * global_data_counter: dropped.
      * axis limits: rounded to the emitted 6-sig-fig form.
      * placement: dropped. The writer emits an explicit frame rect for every
        axes and the recognizer reads it back, so a scripted figure's
        ``None`` ("layout decides") legitimately becomes the rect the layout
        decided on.
      * aspect: dropped. ``set_aspect`` is resolved into that rect and is
        not recovered.
      * _draw_seq: dropped. The writer emits all line series before all
        marker series (ASYMMETRY docs / writer emission order), so the
        caller's interleave across kinds is not representable in the .gle;
        the recognizer stamps encounter order (= what GLE actually draws),
        which legitimately differs from the built figure's call order
        whenever lines and markers interleave.
      * NaN: compared as the string ``"nan"``, since ``nan != nan`` would
        fail a line's gap rows on both sides alike.
    """
    import copy
    import math

    from gleplot.colors import apply_alpha as _apply_alpha
    from gleplot.parser.units import (
        fontsize_cm_to_pt,
        fontsize_pt_to_cm,
        linewidth_cm_to_pt,
        linewidth_pt_to_cm,
    )
    from gleplot.writer import GLEWriter

    d = copy.deepcopy(d)

    def _drop_draw_seq(node):
        if isinstance(node, dict):
            node.pop("_draw_seq", None)
            node.pop("legend_seq", None)
            for v in node.values():
                _drop_draw_seq(v)
        elif isinstance(node, list):
            for v in node:
                _drop_draw_seq(v)

    _drop_draw_seq(d)

    def _nan_token(node):
        if isinstance(node, dict):
            return {k: _nan_token(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_nan_token(v) for v in node]
        if isinstance(node, float) and math.isnan(node):
            return "nan"
        return node

    d = _nan_token(d)
    fig = d["figure"]

    # figsize is recovered as float (cm->inches) even if the source used int
    # literals; same value, coerce both sides to float for comparison.
    if fig.get("figsize") is not None:
        fig["figsize"] = [float(v) for v in fig["figsize"]]

    # Figure-level: drop data-naming/counter state that need not round-trip.
    # sidecar_counters/global_sidecar_counters (G8) are the contour/heatmap/
    # fitz analogue of local_data_counter/global_data_counter: the recognizer
    # builds heatmaps/contours directly from parsed filenames, never through
    # axes._reserve_sidecar, so a recovered figure never populates them.
    for k in (
        "data_prefix",
        "local_data_counter",
        "global_data_counter",
        "used_data_files",
        "subplot_adjust",
        "sidecar_counters",
        "global_sidecar_counters",
    ):
        fig.pop(k, None)

    # fontsize -> emitted cm -> pt.
    style = fig["config"]["style"]
    fs = style.get("fontsize")
    if isinstance(fs, (int, float)):
        emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(fs)))
        style["fontsize"] = fontsize_cm_to_pt(float(emitted))

    default_linewidth = style.get("default_linewidth", 1.5)
    for key in ("default_color", "default_marker_color"):
        if key in style:
            style[key] = rgb_to_gle(style[key])

    def _snap_linewidth(v, verbatim=False):
        # Writer substitutes default_linewidth for API defaults 0/1.
        pt = default_linewidth if v in (0, 1) and not verbatim else v
        emitted = GLEWriter._format_number(linewidth_pt_to_cm(float(pt)))
        return linewidth_cm_to_pt(float(emitted))

    def _snap_width(s):
        verbatim = s.pop("_lwidth_verbatim", False)
        if s.get("linewidth") is not None:
            s["linewidth"] = _snap_linewidth(s["linewidth"], verbatim)

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

    def _snap_deep(v):
        # Snap a possibly-nested (2-D ``z`` grid) numeric structure.
        if isinstance(v, list):
            return [_snap_deep(e) for e in v]
        return _snap_num(v)

    # Data arrays are written to the .dat sidecar at 6 significant figures, so
    # recovered arrays are rounded. Snap BOTH sides to that emitted precision.
    _ARRAY_KEYS = {
        "lines": ("x", "y"),
        "scatters": ("x", "y", "mdata", "cdata"),
        "bars": ("x", "height", "bottom", "top"),
        "hists": ("samples",),
        "fits": ("x", "y"),
        "fills": ("x", "y1", "y2"),
        "errorbars": ("x", "y", "yerr_up", "yerr_down", "xerr_left", "xerr_right"),
    }

    for ax in fig["axes"]:
        # Stable axes identity (G5): a .gle file carries no id, so the
        # recognizer always mints a fresh uuid4 per axes -- by design (SPEC
        # 6.2/10.5: "a parsed .gle has no ids -- fresh ones"). Never equal to
        # the original figure's id, so drop it from both sides.
        ax.pop("axes_id", None)

        # legend tri-state normalization: explicit True with labels -> None.
        labels = any(
            s.get("label")
            for group in (
                "lines",
                "scatters",
                "bars",
                "hists",
                "functions",
                "fits",
                "fills",
                "errorbars",
                "file_series",
                "reflines",
                "spans",
            )
            for s in ax.get(group, [])
        )
        if ax.get("legend_on") is True and labels:
            ax["legend_on"] = None

        # legend_fontsize -> emitted cm -> pt, same snap as the style
        # fontsize above (GLEWriter.add_legend's 'hei' token round-trips
        # through the writer's 6-significant-figure cm formatting).
        lfs = ax.get("legend_fontsize")
        if isinstance(lfs, (int, float)):
            emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(lfs)))
            ax["legend_fontsize"] = fontsize_cm_to_pt(float(emitted))
        # Legend spacing goes out as cm at 6 significant figures and comes
        # back divided by the key text height: equal to 5.
        ax["legend_spacing"] = {
            k: float(f"{v:.5g}") for k, v in (ax.get("legend_spacing") or {}).items()
        }

        # Explicit placement: a scripted figure carries None ("let the layout
        # decide") and the writer emits the rect the layout computed; the
        # recognizer reads that rect straight back, so the recovered axes
        # carries it explicitly. Same geometry either way -- drop it from
        # both sides, exactly as ``subplot_adjust`` is dropped above (the
        # rect IS the surviving form of that information). That the rect
        # itself round-trips is asserted by tests/parser/test_graph_geometry.
        ax.pop("placement", None)
        # set_aspect is resolved into that rect too, and is not recovered
        # (agreed for #85): the rect is its surviving form.
        ax.pop("aspect", None)

        # axis limits snap to emitted precision.
        for lim in ("xmin", "xmax", "ymin", "ymax", "y2min", "y2max", "x2min", "x2max"):
            if ax.get(lim) is not None:
                ax[lim] = _snap_num(ax[lim])

        # Axes styling: sizes are points on the model and 'hei' cm in the
        # file, grid widths points and 'lwidth' cm, both written at the
        # writer's precision -- the same round-trip snap the text fontsizes
        # and series linewidths get above. Distances and angles are already
        # in the model's own units, so they come back exact.
        for key in (
            "title_size",
            "xlabel_size",
            "ylabel_size",
            "y2label_size",
            "x2label_size",
            "xticklabel_size",
            "yticklabel_size",
            "y2ticklabel_size",
            "x2ticklabel_size",
        ):
            if ax.get(key) is not None:
                emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(ax[key])))
                ax[key] = fontsize_cm_to_pt(float(emitted))
        for key in ("xgrid_lwidth", "ygrid_lwidth"):
            if ax.get(key) is not None:
                ax[key] = _snap_linewidth(ax[key])

        for group in (
            "lines",
            "scatters",
            "errorbars",
            "hists",
            "functions",
            "fits",
            "derived_series",
            "reflines",
        ):
            for s in ax.get(group, []):
                if "markersize" in s:
                    s["markersize"] = _snap_msize(s["markersize"])
                _snap_width(s)
                for key in (
                    "hist_from",
                    "hist_to",
                    "bar_width",
                    "bin_step",
                    "let_from",
                    "let_to",
                    "let_step",
                ):
                    if isinstance(s.get(key), (int, float)):
                        s[key] = _snap_num(s[key])
        for s in ax.get("file_series", []):
            # The recognizer's account of the file it could not read names
            # the absolute path it looked in, which differs per directory.
            # Compare it with that directory removed.
            error = s.get("data_error")
            if isinstance(error, str):
                head, sep, path = error.partition(": ")
                if sep:
                    s["data_error"] = head + sep + Path(path).name
            if "markersize" in s:
                s["markersize"] = _snap_msize(s["markersize"])
            _snap_width(s)

        # A bar with no top is written missing in its baseline too, because
        # GLE refuses a stack missing on one side only (#317). That baseline
        # comes back missing.
        for s in ax.get("bars", []):
            if isinstance(s.get("bottom"), list) and isinstance(s.get("top"), list):
                s["bottom"] = [
                    "nan" if top == "nan" else bottom
                    for bottom, top in zip(s["bottom"], s["top"])
                ]

        # Data arrays snap to emitted precision.
        for group, keys in _ARRAY_KEYS.items():
            for s in ax.get(group, []):
                for k in keys:
                    if s.get(k) is not None:
                        s[k] = _snap_array(s[k])

        # fill_between alpha (Track G6) is baked into the emitted colour as
        # an ``rgba255(...)`` expression (gleplot.colors.apply_alpha), so the
        # recovered series' 'color' is that expression while the built
        # figure's is still the plain colour the caller passed. Normalize the
        # built side to what actually gets written/recovered -- the same
        # composition the writer performs -- then drop 'alpha' itself: the
        # recognizer has no way to recover a fractional alpha from an
        # already-composed colour expression (see recognizer.py's
        # ``_parse_fill_command``), so it is not representable as a *number*
        # post round-trip, only baked into 'color'. Its data arrays already
        # snapped above.
        for s in ax.get("fills", []) + ax.get("spans", []):
            if "color" in s:
                s["color"] = _apply_alpha(s["color"], s.get("alpha"))
            s.pop("alpha", None)

        # Heatmap / contour series: grids and scattered points are written to
        # ``.z``/``.dat`` sidecars at 6 significant figures, extents/levels/
        # vmin/vmax to the emitted GLE precision; the colorbar's z-range comes
        # back from the emitted call. Snap BOTH sides to those precisions. The
        # recovered ``z`` grid is always y-increasing origin='lower' (documented
        # normalization), so an origin='upper' grid is flipped to match.
        for group in ("heatmaps", "contours"):
            for s in ax.get(group, []):
                if s.get("origin") == "upper" and s.get("z") is not None:
                    s["z"] = [list(row) for row in s["z"]][::-1]
                    s["origin"] = "lower"
                if s.get("z") is not None:
                    s["z"] = _snap_deep(s["z"])
                for k in ("x", "y", "zpts", "extent", "levels"):
                    if s.get(k) is not None:
                        s[k] = _snap_array(s[k])
                for k in ("vmin", "vmax"):
                    if s.get(k) is not None:
                        s[k] = _snap_num(s[k])
                _snap_width(s)
                cb = s.get("colorbar")
                if cb:
                    for k in ("zmin", "zmax", "zstep", "width", "sep"):
                        if cb.get(k) is not None:
                            cb[k] = _snap_num(cb[k])
                    # A step that divides the range is written as
                    # (zmax-(zmin))/n from the printed range, so it comes
                    # back as that quotient: compare one digit coarser.
                    if cb.get("zstep") is not None:
                        cb["zstep"] = float(f"{cb['zstep']:.5g}")

        # Text annotations: fontsize round-trips through cm (snap).
        # ``box_color`` and a non-zero ``rotation`` are emitted and recovered,
        # so they stay in the comparison. ``va``/``ha`` come back from
        # ``set just``.
        #
        # Sticky-fontsize normalization: 'set hei' is GLE interpreter-global
        # state (see recognizer._try_one_text / writer.add_text_annotation). The writer
        # only emits 'set hei' when a text's fontsize DIFFERS from whatever is
        # currently active -- so a text with fontsize=None (or one equal to
        # the already-active height) genuinely renders in real GLE at the
        # last-explicit height, not some independent default. The recognizer
        # correctly resolves that inherited value on recovery (it cannot tell
        # "no explicit set hei" apart from "same value restated"). Both sides
        # are therefore normalized to the STICKY-RESOLVED height, seeded from
        # the style default (the preamble's unconditional 'set hei'), matching
        # the value real GLE would use when rendering each text in sequence.
        #
        sticky_fs = style.get("fontsize")
        for s in ax.get("rugs", []):
            s["ticks"] = [_snap_num(v) for v in s["ticks"]]
            s["length"] = _snap_num(s["length"])
            # Written as given, in cm: no default substitution.
            cm = GLEWriter._format_number(linewidth_pt_to_cm(s["linewidth"]))
            s["linewidth"] = linewidth_cm_to_pt(float(cm))
        for s in ax.get("texts", []):
            fs = s.get("fontsize")
            if fs is None:
                fs = sticky_fs
            emitted = GLEWriter._format_number(fontsize_pt_to_cm(float(fs)))
            s["fontsize"] = fontsize_cm_to_pt(float(emitted))
            sticky_fs = s["fontsize"]

    # Figure-level text: only a suptitle at its default place reads back as
    # one (the rest are written the same way as a Figure.text), and every
    # size goes through the emitted 'set hei'.
    title = fig.get("suptitle")
    if title is not None and not (
        (title["x"], title["y"], title["ha"], title["va"])
        == (0.5, 0.98, "center", "top")
    ):
        fig["texts"] = [fig.pop("suptitle")] + fig.get("texts", [])
    for s in ([fig["suptitle"]] if "suptitle" in fig else []) + fig.get("texts", []):
        if s.get("fontsize") is not None:
            emitted = GLEWriter._format_number(fontsize_pt_to_cm(s["fontsize"]))
            s["fontsize"] = fontsize_cm_to_pt(float(emitted))
    legend = fig.get("legend")
    if legend is not None:
        if legend["fontsize"] is not None:
            emitted = GLEWriter._format_number(fontsize_pt_to_cm(legend["fontsize"]))
            legend["fontsize"] = fontsize_cm_to_pt(float(emitted))
        legend["spacing"] = {k: float(f"{v:.5g}") for k, v in legend["spacing"].items()}

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

    # A guide drawn after the graph writes no sidecar, so the name it is
    # given on load is a fresh reservation, not the one it was built with.
    written = {p.name for p in tmp_path.iterdir()}
    for ax_o, ax_r in zip(original["figure"]["axes"], recovered["figure"]["axes"]):
        for group in ("reflines", "spans"):
            for g_o, g_r in zip(ax_o.get(group, []), ax_r.get(group, [])):
                if g_o.get("data_file") not in written:
                    g_o.pop("data_file", None)
                    g_r.pop("data_file", None)

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


def test_broken_errorbar_becomes_file_series_with_error(tmp_path):
    """``dN ... err dM`` against a missing data file -> FileSeries('errorbar')."""
    _gleplot_axes._global_data_file_counter = 0
    fig = golden.errorbar_symmetric()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    (tmp_path / "golden_0.dat").unlink()

    recognized = parse_gle_figure(gle_path)
    ax = recognized.figure.axes_list[0]

    assert ax.errorbars == []
    assert dict(ax.file_series[0]) == {
        "series_type": "errorbar",
        "data_file": "golden_0.dat",
        "x_col": 1,
        "y_col": 2,
        "yerr_col": 3,
        "color": "RED",
        "marker": "FCIRCLE",
        "markersize": 0.15,
        "label": "sym",
        "capsize": 0.1412,
        "yaxis": "y",
        "data_error": f"Data file not found: {tmp_path / 'golden_0.dat'}",
    }
    assert any(w.startswith("data:") for w in recognized.warnings)


def test_broken_sidecar_keeps_its_reading_options(tmp_path):
    """A missing imported file degrades to a reference with its ``numrows``."""
    fig = gleplot.figure(data_prefix="opts")
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.errorbar([1, 2, 3], [1, 2, 3], yerr=0.2)
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    for dat in tmp_path.glob("*.dat"):
        dat.unlink()
    text = gle_path.read_text(encoding="utf-8")
    lines = [
        line + " numrows 2" if line.lstrip().startswith("data ") else line
        for line in text.splitlines()
    ]
    gle_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    refs = parse_gle_figure(gle_path).figure.axes_list[0].file_series
    assert [(fs["series_type"], fs["max_rows"]) for fs in refs] == [
        ("line", 2),
        ("errorbar", 2),
    ]
    assert all("data_error" in fs for fs in refs)


def _imported(name):
    """A metadata block naming ``name`` gleplot's own file.

    The recognizer loads a series on such a file; a bar, fill or offset
    ``let`` on a file of the user's own is a reference or raw GLE instead.
    """
    return (
        "! gleplot-meta-begin v2\n"
        f"! gleplot: import-data = {name}\n"
        "! gleplot-meta-end\n"
    )


@pytest.mark.parametrize(
    "body",
    [
        "   data f.dat d1=c1,c2 ignore 2\n   bar d1\n",
        "   data f.dat d1=c1,c2 d2=c1,c3 numrows 2\n   fill d1,d2 color red\n",
    ],
)
def test_a_file_read_with_options_is_not_loaded(tmp_path, body):
    """#169: the loader would read rows GLE skips; keep a reference instead."""
    src = (
        _imported("f.dat")
        + "size 12 9\nbegin graph\n   size 10 7\n"
        + body
        + "end graph\n"
    )
    p = _write(tmp_path, "o.gle", src, {"f.dat": "99 99 99\n1 2 3\n2 3 4\n3 5 6\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.bars == [] and ax.fills == [] and ax.errorbars == []
    assert len(ax.file_series) == 1
    assert {"skiprows", "max_rows", "comment"} & set(ax.file_series[0])
    assert any(w.startswith("data:") and "'f.dat'" in w for w in rec.warnings)
    out = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(out))
    assert body.splitlines()[0].strip() in out.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "body, data, written",
    [
        # A text first column labels the x axis; x is the point index.
        ('data "t.dat"\n   d1 line', "a 2 3\nb 3 4\n", "data t.dat d1=c0,c2"),
        ('data "t.dat" d1 d2\n   d2 line', "a 2 3\nb 3 4\n", "data t.dat d1=c0,c3"),
        ('data "t.dat"\n   bar d1', "a 2 3\nb 3 4\n", "data t.dat d1=c0,c2"),
        # 'nox' makes x the point index and y start at c1.
        ('data "n.dat" d1 d2 nox\n   d2 line', "1 2 3\n2 3 4\n", "data n.dat d1=c0,c2"),
        # #323: GLE's rules, not the loader's: 'inf' is text to GLE ...
        ('data "t.dat"\n   d1 line', "inf 2\ninf 3\n", "data t.dat d1=c0,c2"),
        # ... and the statement's 'ignore' skips the row that is a number.
        (
            'data "t.dat" ignore 1\n   d1 line',
            "1 2 3\na 2 3\nb 3 4\n",
            "data t.dat d1=c0,c2 ignore 1",
        ),
    ],
)
def test_positional_x_follows_gle(tmp_path, body, data, written):
    """#169: datasets given without columns get the x GLE gives them."""
    src = f"size 12 9\nbegin graph\n   size 10 7\n   {body}\nend graph\n"
    p = _write(tmp_path, "p.gle", src, {"t.dat": data, "n.dat": data})
    fig = parse_gle_figure(p).figure
    assert fig.axes_list[0].bars == []
    out = tmp_path / "again.gle"
    fig.savefig_gle(str(out))
    assert written in out.read_text(encoding="utf-8")


def test_options_on_one_graph_do_not_stop_another_loading_the_file(tmp_path):
    """#169: GLE reads the file afresh in each graph."""
    src = (
        _imported("f.dat")
        + "begin graph\n   data f.dat d1=c1,c2 ignore 1\n   bar d1\nend graph\n"
        "begin graph\n   data f.dat d2=c1,c3\n   bar d2\nend graph\n"
    )
    p = _write(tmp_path, "two.gle", src, {"f.dat": "1 2 3\n2 3 4\n"})
    first, second = parse_gle_figure(p).figure.axes_list
    assert (len(first.bars), len(second.bars)) == (0, 1)


def test_a_single_text_column_defines_no_dataset(tmp_path):
    """#169: GLE reads a lone text column as x labels only; the statement
    is kept as written."""
    src = 'begin graph\n   data "w.dat"\n   d1 line\nend graph\n'
    p = _write(tmp_path, "w.gle", src, {"w.dat": "a\nb\nc\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    assert ax.file_series == [] and ax.lines == []
    assert '   data "w.dat"' in ax.passthrough


@pytest.mark.parametrize(
    "data, readers",
    [
        ('data "s.dat" d1=c1,c2 delimiters ";"', ["d1 line"]),
        # #322: with 'ignore' a bar became a reference without the delimiters.
        ('data "s.dat" ignore 1 delimiters ";" d1=c1,c2', ["bar d1 fill red"]),
        ('data "s.dat" ignore n d1=c1,c2', ["d1 line color red"]),
        ('data "s.dat" numrows 2*1 d1=c1,c2', ["d1 marker circle"]),
        (
            'data "s.dat" delimiters ";" d1=c1,c2',
            ["let d2 = fit d1", "d2 line", "let d3 = d1+1", "d3 line"],
        ),
        ('data "s.dat" delimiters ";"', ["fill d1,x1 color gray"]),
    ],
)
def test_a_data_statement_with_unmodelled_options_stays_raw(tmp_path, data, readers):
    """#322: the statement and every line reading its datasets are kept."""
    body = "".join(f"   {line}\n" for line in [data, *readers])
    src = f"begin graph\n{body}" '   data "f.dat" d9=c1,c2\n   d9 line\nend graph\n'
    files = {"s.dat": "x;y\n1;2\n2;3\n", "f.dat": "1 2\n2 3\n"}
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src, files))
    ax = rec.figure.axes_list[0]
    assert ax.passthrough == [f"   {line}" for line in [data, *readers]]
    assert len(ax.file_series) == 1 and ax.file_series[0]["data_file"] == "f.dat"
    (note,) = [w for w in rec.warnings if w.startswith("data:")]
    assert "every line that reads its datasets were kept as raw GLE" in note
    text, _ = rec.figure._generate_gle_with_files()
    assert body in text


def test_a_let_reading_a_raw_data_statement_keeps_its_target_raw(tmp_path):
    """#322: ``d2 line`` draws the raw ``let``, not the earlier ``data``."""
    src = (
        'begin graph\n   data "f.dat" d2=c1,c2\n'
        '   data "s.dat" delimiters ";" d1=c1,c2\n'
        "   let d2 = d1+1\n   d2 line color red\nend graph\n"
    )
    files = {"s.dat": "1;2\n2;3\n", "f.dat": "1 2\n2 3\n"}
    ax = parse_gle_figure(_write(tmp_path, "s.gle", src, files)).figure.axes_list[0]
    assert ax.file_series == [] and ax.lines == []
    assert ax.passthrough[-2:] == ["   let d2 = d1+1", "   d2 line color red"]


def test_a_raw_data_statement_redefining_a_dataset_is_reported(tmp_path):
    src = (
        'begin graph\n   data "f.dat" d1=c1,c2\n   d1 line\n'
        '   data "s.dat" delimiters ";" d1=c1,c2\nend graph\n'
    )
    files = {"s.dat": "1;2\n2;3\n", "f.dat": "1 2\n2 3\n"}
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src, files))
    assert any("dataset d1 redefined" in w for w in rec.warnings)
    assert rec.figure.axes_list[0].passthrough == [
        '   data "f.dat" d1=c1,c2',
        '   data "s.dat" delimiters ";" d1=c1,c2',
        "   d1 line",
    ]


def test_broken_bar_becomes_file_series_with_error(tmp_path):
    """``bar dN fill COLOR`` against a missing data file -> FileSeries('bar')."""
    _gleplot_axes._global_data_file_counter = 0
    fig = golden.bar()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    (tmp_path / "golden_0.dat").unlink()

    recognized = parse_gle_figure(gle_path)
    ax = recognized.figure.axes_list[0]

    assert ax.bars == []
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert set(fs.keys()) == {
        "series_type",
        "data_file",
        "x_col",
        "y_col",
        "color",
        "data_error",
    }
    assert fs["series_type"] == "bar"
    assert fs["data_file"] == "golden_0.dat"
    assert fs["x_col"] == 1
    assert fs["y_col"] == 2
    assert fs["color"] == "ORANGE"
    assert fs["data_error"]

    assert any(w.startswith("data:") for w in recognized.warnings)

    # Re-save preserves the "bar" shape verbatim rather than degrading it to
    # a plain dataset -- GLE will still fail on the missing file, but the
    # recovered figure keeps meaning "this was a bar chart" across saves.
    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "data golden_0.dat d1=c1,c2" in text
    assert "bar d1 fill ORANGE" in text

    # Fixed point: re-parsing the recovered output reproduces the identical
    # recognized field set and a byte-identical next save.
    reparsed = parse_gle_figure(out)
    fs2 = reparsed.figure.axes_list[0].file_series[0]
    assert {k: v for k, v in fs2.items() if k != "data_error"} == {
        k: v for k, v in fs.items() if k != "data_error"
    }
    out2 = tmp_path / "again2.gle"
    reparsed.figure.savefig_gle(str(out2))
    assert out2.read_text(encoding="utf-8") == text


def test_broken_fill_becomes_file_series_with_error(tmp_path):
    """``fill dA,dB color COLOR`` against a missing data file -> FileSeries('fill').

    Uses a standalone fixture (rather than ``golden.fill_between``, which also
    plots a line) so the recovered dataset numbering is unambiguous.
    """
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure(data_prefix="golden")
    ax = fig.add_subplot(1, 1, 1)
    x = [0, 1, 2, 3, 4]
    ax.fill_between(x, [0, 0, 0, 0, 0], [0, 1, 4, 9, 16], color="lightblue")
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    (tmp_path / "golden_0.dat").unlink()

    recognized = parse_gle_figure(gle_path)
    ax = recognized.figure.axes_list[0]

    assert ax.fills == []
    assert len(ax.file_series) == 1
    fs = ax.file_series[0]
    assert set(fs.keys()) == {
        "series_type",
        "data_file",
        "x_col",
        "y1_col",
        "y2_col",
        "color",
        "data_error",
    }
    assert fs["data_file"] == "golden_0.dat"
    assert fs["x_col"] == 1
    assert fs["y1_col"] == 2
    assert fs["y2_col"] == 3
    assert fs["color"] == "LIGHTBLUE"
    assert fs["data_error"]

    assert any(w.startswith("data:") for w in recognized.warnings)

    # Re-save must not crash (the 'fill' variant has no y_col, only
    # y1_col/y2_col) and preserves the "fill" shape verbatim.
    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "d1=c1,c2 d2=c1,c3" in text
    assert "fill d1,d2 color LIGHTBLUE" in text

    # Fixed point across a second parse/save cycle.
    reparsed = parse_gle_figure(out)
    fs2 = reparsed.figure.axes_list[0].file_series[0]
    assert {k: v for k, v in fs2.items() if k != "data_error"} == {
        k: v for k, v in fs.items() if k != "data_error"
    }
    out2 = tmp_path / "again2.gle"
    reparsed.figure.savefig_gle(str(out2))
    assert out2.read_text(encoding="utf-8") == text


def test_axis_clip_and_polygon_fills_round_trip(tmp_path):
    """``fill x1,dN``, a clipped ``fill dA,dB``, and ``fill dN`` come back."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    x = [0, 1, 2, 3]
    ax.fill_between(x, [1, 2, 2, 1], baseline="x1", ymin=0)
    ax.fill_between(x, [1, 3, 2, 2], [0, 1, 1, 0], xmin=1, xmax=2, color="blue")
    ax.fill([0, 1, 0.5], [0, 0, 1], color="red")
    ax.fill_between(x, [1, 2, 2, 1], baseline="x2")
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))

    recognized = parse_gle_figure(gle_path)
    fills = recognized.figure.axes_list[0].fills
    assert [item.get("target") for item in fills] == ["x1", None, "polygon", "x2"]
    assert fills[0]["ymin"] == 0
    assert fills[1]["xmin"] == 1 and fills[1]["xmax"] == 2
    assert "target" not in fills[1]
    assert fills[2]["y2"] is None

    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    assert out.read_text(encoding="utf-8") == gle_path.read_text(encoding="utf-8")
    assert "fill d5,x2 color LIGHTBLUE" in out.read_text(encoding="utf-8")


def test_unresolved_single_curve_fills_keep_their_form(tmp_path):
    """A missing sidecar must not turn ``fill x1,dN`` into a two-curve fill."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure(data_prefix="golden")
    ax = fig.add_subplot(111)
    ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x1", xmin=0.5)
    ax.fill([0, 1, 0], [0, 1, 2])
    ax.fill_between([0, 1, 2], [1, 2, 1], baseline="x2", ymax=4)
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    for name in ("golden_0.dat", "golden_1.dat", "golden_2.dat"):
        (tmp_path / name).unlink()

    recognized = parse_gle_figure(gle_path)
    series = recognized.figure.axes_list[0].file_series
    assert [item.get("target") for item in series] == ["x1", "polygon", "x2"]
    assert all("y2_col" not in item for item in series)
    assert series[0]["xmin"] == 0.5
    assert series[2]["ymax"] == 4

    out = tmp_path / "again.gle"
    recognized.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "fill x1,d1 color LIGHTBLUE xmin 0.5" in text
    assert "fill d2 color LIGHTBLUE" in text
    assert "fill d3,x2 color LIGHTBLUE ymax 4" in text
    assert "d1,d2" not in text


def test_fill_with_an_extra_operand_or_keyword_stays_raw(tmp_path):
    """A third dataset or an unknown option is not a modelled fill."""
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data pts.dat d1=c1,c2 d2=c1,c3 d3=c1,c4\n"
        "   fill d1,d2,d3 color BLUE\n"
        "   fill d1,d2 lstyle 1\n"
        "end graph\n"
    )
    p = _write(tmp_path, "raw.gle", src, {"pts.dat": "0 0 1 2\n1 1 2 3\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.fills == []
    assert any("fill d1,d2,d3" in line for line in ax.passthrough)
    assert any("lstyle" in line for line in ax.passthrough)


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
    # GLE renders lstyle 2 as dotted (3 is the dashed one), so that is what
    # the recognizer must report -- see tables.LSTYLE_TO_MATPLOTLIB.
    assert series["linestyle"] == ":"
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


def test_xplaces_xnames_yplaces_ynames_recognized(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 0 max 2\n"
        "   xplaces 0 1 2\n"
        '   xnames "a" "b" "c"\n'
        "   yaxis min 0 max 4\n"
        "   yplaces 0 2 4\n"
        '   ynames "low" "mid" "high"\n'
        "   data pt_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "tk.gle", src, {"pt_1.dat": "0 0\n1 1\n2 4\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.xplaces == [0.0, 1.0, 2.0]
    assert ax.xnames == ["a", "b", "c"]
    assert ax.yplaces == [0.0, 2.0, 4.0]
    assert ax.ynames == ["low", "mid", "high"]
    assert not rec.warnings
    assert not ax.passthrough


def test_text_holding_double_quotes_comes_back_unchanged(tmp_path):
    """Each GLE quoting form the writer uses reads back to the same text."""
    fig = golden.quoted_text()
    path = tmp_path / "quoted.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    assert rec.warnings == []
    want, got = fig.axes_list, rec.figure.axes_list
    assert got[0].title_text == 'a "quoted" title'
    assert got[0].xlabel_text == 'it\'s "x"'
    assert got[0].xnames == ['"0"', "one", 'it\'s "2"']
    assert [t["text"] for t in got[0].texts] == [t["text"] for t in want[0].texts]
    assert got[0].heatmaps[0]["colorbar"]["label"] == 'z "units"'
    assert [s["label"] for s in got[0].lines] == ['the "fit"']
    assert [t["text"] for t in rec.figure.texts] == ['"figure" text']


def test_hand_written_quotes_keep_what_gle_draws(tmp_path):
    """GLE prints a doubled quote in ``xnames`` twice; a concatenation stays."""
    src = (
        "size 10 8\n"
        "begin graph\n"
        "   xaxis min 0 max 2\n"
        "   xplaces 0 1\n"
        '   xnames "5""" "b"\n'
        "   yaxis min 0 max 1\n"
        "end graph\n"
        "amove 1 1\n"
        'write "Total: "+"x"\n'
    )
    fig = parse_gle_figure(_write(tmp_path, "q.gle", src)).figure
    assert fig.axes_list[0].xnames == ['5""', "b"]
    assert fig.texts == []
    assert 'write "Total: "+"x"' in fig.passthrough_trailer


def test_xplaces_xnames_length_mismatch_falls_back_to_passthrough(tmp_path):
    # xnames has fewer entries than xplaces -- not representable on the model
    # (GLEWriter.add_axis_config would raise), so both lines must be kept as
    # raw GLE instead of populating ax.xplaces/xnames.
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   xaxis min 0 max 2\n"
        "   xplaces 0 1 2\n"
        '   xnames "a" "b"\n'
        "   yaxis min 0 max 4\n"
        "   data pt_1.dat d1=c1,c2\n"
        "   d1 line color BLUE lwidth 0.05292\n"
        "end graph\n"
    )
    p = _write(tmp_path, "mismatch.gle", src, {"pt_1.dat": "0 0\n1 1\n2 4\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.xplaces is None
    assert ax.xnames is None
    assert any("xnames/xplaces length mismatch" in w for w in rec.warnings)
    assert any("xplaces 0 1 2" in line for line in ax.passthrough)
    assert any('xnames "a" "b"' in line for line in ax.passthrough)
    # Re-saving must not raise (GLEWriter would reject a mismatched pairing)
    # and must reproduce both lines verbatim, cumulative with the modeled
    # xaxis line.
    text, _ = rec.figure._generate_gle_with_files()
    assert "xplaces 0 1 2" in text
    assert 'xnames "a" "b"' in text


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


# Both GLE forms of a user-defined marker: a subroutine registered with
# ``define marker``, and a font glyph registered with ``defmarker``.
_CUSTOM_MARKER_DEFS = [
    "sub crossbox size mdata",
    "    gsave",
    "    rmove -size/2 -size/2",
    "    box size size",
    "    grestore",
    "end sub",
    "define marker cbox crossbox",
    "defmarker hand pszd 43 1 0 0",
]
_CUSTOM_MARKER_SRC = (
    "size 10 8\n"
    "set hei 0.4\n" + "\n".join(_CUSTOM_MARKER_DEFS) + "\n"
    "begin graph\n"
    "   xaxis min 0 max 4\n"
    "   yaxis min 0 max 8\n"
    "   data cm_1.dat d1=c1,c2 d2=c1,c3\n"
    "   d1 line color BLUE marker cbox msize 0.3\n"
    "   d2 marker hand msize 0.5 color RED\n"
    "end graph\n"
)
_CUSTOM_MARKER_DAT = {"cm_1.dat": "1 2 3\n2 4 5\n3 6 7\n"}


def test_custom_marker_definitions_round_trip(tmp_path):
    p = _write(tmp_path, "cm.gle", _CUSTOM_MARKER_SRC, _CUSTOM_MARKER_DAT)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rec = parse_gle_figure(p)
    # Every note is on the sub's own source lines (the programmatic guard, and
    # a false structure note on 'end sub', #189): the definitions and the
    # datasets using them recover with none.
    first = 3  # after 'size' and 'set hei'
    sub_lines = range(first, first + _CUSTOM_MARKER_DEFS.index("end sub") + 1)
    assert any(w.startswith("programmatic:") for w in rec.warnings)
    assert all(n.source_span[0] in sub_lines for n in rec.notes)
    fig = rec.figure
    assert fig.passthrough_header == _CUSTOM_MARKER_DEFS
    ax = fig.axes_list[0]
    series = ax.lines + ax.scatters + ax.file_series
    assert [s["marker"] for s in series] == ["cbox", "hand"]
    assert ax.passthrough == []

    # GLE resolves a marker name against the definitions read before it.
    out = tmp_path / "again.gle"
    fig.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    defs_at = text.index("\n".join(_CUSTOM_MARKER_DEFS) + "\n")
    graph_at = text.index("begin graph")
    assert defs_at < graph_at
    assert text.index(" marker cbox ", graph_at) > graph_at
    assert text.index(" marker hand ", graph_at) > graph_at

    # A second load and save changes nothing.
    again = tmp_path / "again2.gle"
    parse_gle_figure(out).figure.savefig_gle(str(again))
    assert again.read_bytes() == out.read_bytes()


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


def test_spanning_subplots_are_recovered(tmp_path):
    """gleplot's own spanning grid reloads with its spans and no layout note."""
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "span.gle"
    golden.subplots_spanning().savefig_gle(str(gle_path))
    rec = parse_gle_figure(gle_path)
    assert [ax.position for ax in rec.figure.axes_list] == [
        (3, 3, (1, 2)),
        (3, 3, (3, 6)),
        (3, 3, 4),
        (3, 3, 5),
        (3, 3, (7, 9)),
    ]
    assert not any(w.startswith("layout:") for w in rec.warnings)


def test_default_linewidth_is_read_from_the_metadata(tmp_path):
    """#345: a line plotted after loading gets the width the file used."""
    fig = gleplot.figure(style=gleplot.GLEStyleConfig(default_linewidth=1.0))
    fig.add_subplot(111).plot([0, 1], [0, 1])
    path = tmp_path / "w.gle"
    fig.savefig_gle(str(path))

    loaded = parse_gle_figure(path).figure
    assert loaded.style.default_linewidth == 1.0
    loaded.axes_list[0].plot([0, 1], [1, 0])
    again = tmp_path / "again.gle"
    loaded.savefig_gle(str(again))
    widths = [
        line.split("lwidth ")[1].split()[0]
        for line in again.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("d") and " line " in line
    ]
    assert widths == ["0.03528", "0.03528"]


def test_default_colors_are_read_from_the_metadata(tmp_path):
    """#345: a series plotted after loading gets the colour the file used."""
    style = gleplot.GLEStyleConfig(default_color="C1", default_marker_color="red")
    fig = gleplot.figure(style=style)
    fig.add_subplot(111).plot([0, 1], [0, 1])
    path = tmp_path / "c.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    assert "! gleplot: default_color = rgb255(255,127,14)" in text
    assert "! gleplot: default_marker_color = RED" in text

    loaded = parse_gle_figure(path).figure
    ax = loaded.axes_list[0]
    ax.plot([0, 1], [1, 0])
    ax.scatter([0, 1], [1, 0])
    again = tmp_path / "again.gle"
    loaded.savefig_gle(str(again))
    lines = again.read_text(encoding="utf-8").splitlines()
    assert sum("color rgb255(255,127,14)" in line for line in lines) == 2
    assert any(" marker " in line and "color RED" in line for line in lines)


@pytest.mark.parametrize(
    "style",
    [
        {"default_linewidth": 0},
        {"msize_scale": 2},
        {"default_linewidth": -1.0},
        {"default_color": "rgba255(255,0,0,128)"},
        {"default_marker_color": "rgb(0.2,0.4,0.6)"},
    ],
)
def test_a_recorded_style_value_reloads_without_a_note(tmp_path, style):
    """Whatever the writer records, open_gle reads back as it was."""
    marker = gleplot.GLEMarkerConfig(msize_scale=style.pop("msize_scale", 1.0))
    fig = gleplot.figure(style=gleplot.GLEStyleConfig(**style), marker=marker)
    fig.add_subplot(111).plot([0, 1], [0, 1])
    path = tmp_path / "s.gle"
    fig.savefig_gle(str(path))

    rec = parse_gle_figure(path)
    assert not [w for w in rec.warnings if w.startswith("metadata:")]
    again = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


def test_a_non_finite_default_linewidth_still_saves(tmp_path):
    fig = gleplot.figure(style=gleplot.GLEStyleConfig(default_linewidth=float("nan")))
    path = tmp_path / "n.gle"
    fig.savefig_gle(str(path))
    assert "! gleplot: default_linewidth = nan" in path.read_text(encoding="utf-8")


def test_default_style_values_are_not_recorded(tmp_path):
    fig = gleplot.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1])
    path = tmp_path / "d.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    for key in ("default_linewidth", "default_color", "default_marker_color"):
        assert key not in text


@pytest.mark.parametrize(
    "key, value, default",
    [
        ("default_linewidth", "thick", 1.5),
        ("default_linewidth", "true", 1.5),
        ("default_linewidth", "inf", 1.5),
        ("default_color", "notacolor", "BLUE"),
        ("default_color", "0.3", "BLUE"),
        ("default_marker_color", "true", "BLUE"),
        ("msize_scale", "big", 1.0),
        ("msize_scale", "nan", 1.0),
    ],
)
def test_a_malformed_style_value_in_the_metadata_is_reported(
    tmp_path, key, value, default
):
    """open_gle reports a recorded value it cannot use and keeps the default."""
    fig = gleplot.figure()
    fig.add_subplot(111).plot([0, 1], [0, 1])
    path = tmp_path / "w.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8").replace(
        "! gleplot-meta-end", f"! gleplot: {key} = {value}\n! gleplot-meta-end"
    )
    path.write_text(text, encoding="utf-8")

    rec = parse_gle_figure(path)
    config = rec.figure.marker_config if key == "msize_scale" else rec.figure.style
    assert getattr(config, key) == default
    assert any(w.startswith(f"metadata: {key} = ") for w in rec.warnings)


def test_insets_are_read_from_the_metadata(tmp_path):
    """gleplot names its insets, so frames that do not nest still come back."""
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "insets.gle"
    golden.insets_off_panel().savefig_gle(str(gle_path))
    assert "! gleplot: insets = 3, 4" in gle_path.read_text()
    rec = parse_gle_figure(gle_path)
    positions = [ax.position for ax in rec.figure.axes_list]
    assert positions == [(1, 2, 1), (1, 2, 2), None, None]
    assert rec.figure.metadata_extra == {}
    assert not any(w.startswith("layout:") for w in rec.warnings)


def test_inset_is_recovered_from_its_frame_without_metadata(tmp_path):
    """In a file without gleplot metadata, a graph inside another's frame is one."""
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "inset.gle"
    golden.inset_axes().savefig_gle(str(gle_path))
    lines = gle_path.read_text().splitlines(keepends=True)
    gle_path.write_text("".join(line for line in lines if "gleplot" not in line))
    rec = parse_gle_figure(gle_path)
    positions = [ax.position for ax in rec.figure.axes_list]
    assert positions == [(1, 2, 1), (1, 2, 2), None]
    assert not any(w.startswith("layout:") for w in rec.warnings)


def test_gleplot_file_without_insets_key_has_no_insets(tmp_path):
    """Nested frames in a gleplot file with no insets key stay in the grid."""
    _gleplot_axes._global_data_file_counter = 0
    fig, (a, _b, c) = gleplot.subplots(1, 3, sharey=True)
    for ax in (a, _b, c):
        ax.plot([1, 2], [1, 2])
    c.placement = (3.0, 4.0, 3.0, 2.0)  # inside a's frame
    gle_path = tmp_path / "nested.gle"
    fig.savefig_gle(str(gle_path))
    rec = parse_gle_figure(gle_path)
    assert None not in [ax.position for ax in rec.figure.axes_list]


def test_metadata_inset_without_a_frame_stays_in_the_grid(tmp_path):
    """A listed inset whose amove was removed is laid out, with a note."""
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "inset.gle"
    golden.inset_axes().savefig_gle(str(gle_path))
    lines = gle_path.read_text().splitlines(keepends=True)
    last_amove = max(i for i, line in enumerate(lines) if line.startswith("amove"))
    del lines[last_amove]
    text = "".join(lines).replace("insets = 3", "insets = 3, 7")
    gle_path.write_text(text)
    rec = parse_gle_figure(gle_path)
    assert None not in [ax.position for ax in rec.figure.axes_list]
    assert any("graph 3 is listed as an inset" in w for w in rec.warnings)
    assert any("insets [7]" in w for w in rec.warnings)
    rec.figure.savefig_gle(str(tmp_path / "again.gle"))


def test_aspect_comes_back_as_its_frame_not_as_a_constraint(tmp_path):
    """A reloaded figure keeps the resized frame but forgets set_aspect."""
    _gleplot_axes._global_data_file_counter = 0
    gle_path = tmp_path / "aspect.gle"
    golden.aspect_ratios().savefig_gle(str(gle_path))
    rec = parse_gle_figure(gle_path)
    # The shrunk frames no longer share corners, but keep their cells' centres.
    assert [ax.position for ax in rec.figure.axes_list] == [(1, 2, 1), (1, 2, 2)]
    assert not any(w.startswith("layout:") for w in rec.warnings)
    left = rec.figure.axes_list[0]
    assert left.get_aspect() == "auto"
    assert left.placement is not None
    assert left.placement[2] == pytest.approx(left.placement[3], rel=1e-4)


def test_graphs_that_do_not_tile_a_grid_fall_back(tmp_path):
    """Frames that overlap without nesting: n x 1 fallback + warning."""
    graph = (
        "amove {x} {y}\n"
        "begin graph\n"
        "   size {w} {h}\n"
        "   scale 1 1\n"
        "   data g_1.dat d1=c1,c2\n"
        "end graph\n"
    )
    src = (
        "size 20 15\n"
        + graph.format(x=2, y=2, w=16, h=11)
        + graph.format(x=10, y=8, w=10, h=4)
        + graph.format(x=2, y=13, w=4, h=1)
    )
    p = _write(tmp_path, "overlap.gle", src, {"g_1.dat": "1 1\n2 2\n"})
    rec = parse_gle_figure(p)
    assert [ax.position for ax in rec.figure.axes_list] == [
        (3, 1, 1),
        (3, 1, 2),
        (3, 1, 3),
    ]
    assert any("clean grid" in w for w in rec.warnings)


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


def test_line_mode_round_trip_and_implied_line(tmp_path):
    """A hand-written mode is recovered, and a bare mode keyword implies line.

    GLE sets ``line`` whenever the mode is not plain, so ``d1 fsteps`` with
    no ``line`` keyword is still a line. Re-saving spells it ``line fsteps``.
    The last mode keyword wins, matching graph2.cpp.
    """
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "modes.dat" d1=c1,c2 d2=c1,c2 d3=c1,c2 d4=c1,c2\n'
        "   d1 line steps color BLUE lwidth 0.05292\n"
        "   d2 fsteps color RED\n"
        "   d3 line steps hist color GREEN\n"
        "   d4 line bar color BLACK\n"
        "end graph\n"
    )
    p = _write(tmp_path, "modes.gle", src, {"modes.dat": "0 1\n1 2\n2 1\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    # No metadata block: every reference stays a file series.
    assert [fs["line_mode"] for fs in ax.file_series] == [
        "steps",
        "fsteps",
        "hist",
        "bar",
    ]
    assert all(fs["series_type"] == "line" for fs in ax.file_series)
    out = tmp_path / "modes-again.gle"
    parse_gle_figure(p).figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert " line steps " in text
    assert " line fsteps " in text
    assert " line hist " in text
    assert " line bar " in text
    # The bare ``fsteps`` was rewritten with the line keyword it implies.
    assert "d2 fsteps " not in text


def test_line_mode_on_a_file_errorbar_keeps_it_raw(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "pts.dat" d1=c1,c2\n'
        '   data "err.dat" d2=c1,c2\n'
        "   d1 line steps err d2 color BLUE\n"
        "end graph\n"
    )
    p = _write(
        tmp_path,
        "errmode.gle",
        src,
        {"pts.dat": "0 1\n1 2\n", "err.dat": "0 0.1\n1 0.2\n"},
    )
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.lines == [] and ax.file_series == []
    assert "   d1 line steps err d2 color BLUE" in ax.passthrough
    assert any(
        w.startswith("data: a connecting line, err d2 not read") for w in rec.warnings
    )


def test_dataset_qualifiers_are_recovered_and_round_trip(tmp_path):
    """``mdist``, ``deresolve [average]`` and the data range survive a re-save.

    They used to be skipped by the attribute scan and silently lost. GLE
    reads ``average`` only straight after the ``deresolve`` count, and a
    second ``deresolve`` resets it (graph2.cpp).
    """
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "q.dat" d1=c1,c2 d2=c1,c2 d3=c1,c2\n'
        "   d1 line marker circle mdist 1 deresolve 2 average xmin 1.5\n"
        "   d2 marker square ymin -1 ymax 2*2 deresolve 3\n"
        "   d3 line deresolve 2 average deresolve 5\n"
        "end graph\n"
    )
    p = _write(tmp_path, "q.gle", src, {"q.dat": "0 1\n1 2\n2 1\n"})
    rec = parse_gle_figure(p)
    line, marks, plain = rec.figure.axes_list[0].file_series
    assert {
        k: line[k] for k in ("mdist", "deresolve", "deresolve_average", "xmin")
    } == {
        "mdist": 1.0,
        "deresolve": 2,
        "deresolve_average": True,
        "xmin": 1.5,
    }
    assert (marks["ymin"], marks["ymax"], marks["deresolve"]) == (-1.0, 4.0, 3)
    assert plain["deresolve"] == 5 and "deresolve_average" not in plain
    out = tmp_path / "q-again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "mdist 1 deresolve 2 average xmin 1.5" in text
    assert "deresolve 3 ymin -1 ymax 4" in text
    assert "deresolve 5" in text and "average deresolve" not in text
    again = tmp_path / "q-third.gle"
    parse_gle_figure(out).figure.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == text


def test_data_reading_options_are_recovered_and_round_trip(tmp_path):
    """``ignore``, ``comment`` and ``numrows`` on a hand-written ``data`` line.

    They used to be skipped as unknown tokens and lost on re-save. GLE takes
    them anywhere after the file name, and the comment marker bare or quoted.
    """
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        "   data r.dat ignore 2 d1=c1,c2 comment # numrows 10\n"
        "   d1 line color RED\n"
        '   data r.dat comment "%" d2=c1,c2 d3=c1,c3\n'
        "   d2 marker circle err d3\n"
        "   data r.dat d4=c0,c2\n"
        "   d4 line\n"
        "   data r.dat d5=c1,c2 comment '\"'\n"
        "   d5 line\n"
        "end graph\n"
    )
    p = _write(tmp_path, "r.gle", src, {"r.dat": "1 2 3\n2 3 4\n"})
    line, errs, plain, quote = parse_gle_figure(p).figure.axes_list[0].file_series
    assert (line["skiprows"], line["comment"], line["max_rows"]) == (2, "#", 10)
    assert errs["comment"] == "%" and "skiprows" not in errs
    assert plain["x_col"] == 0
    assert quote["comment"] == '"'
    assert not {"skiprows", "comment", "max_rows"} & set(plain)
    out = tmp_path / "r-again.gle"
    parse_gle_figure(p).figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert 'data r.dat d1=c1,c2 ignore 2 comment "#" numrows 10' in text
    assert 'data r.dat d2=c1,c2 d3=c1,c3 comment "%"' in text
    assert "data r.dat d4=c0,c2\n" in text
    assert "data r.dat d5=c1,c2 comment '\"'\n" in text
    again = tmp_path / "r-third.gle"
    parse_gle_figure(out).figure.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == text


def test_dataset_qualifiers_on_a_loaded_line_and_scatter(tmp_path):
    """An imported (sidecar) line and scatter carry the fields themselves."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 2, 1], marker="o", mdist=0.4, xmax=1.5)
    ax.scatter([0, 1, 2], [2, 1, 2], deresolve=2)
    path = tmp_path / "loaded.gle"
    fig.savefig_gle(str(path))
    ax2 = parse_gle_figure(path).figure.axes_list[0]
    assert (ax2.lines[0]["mdist"], ax2.lines[0]["xmax"]) == (0.4, 1.5)
    assert ax2.scatters[0]["deresolve"] == 2


def test_a_reference_line_with_a_qualifier_stays_a_line(tmp_path):
    """No guide emission writes a data range; an edited guide is kept as a line."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.plot([0, 1], [0, 1])
    ax.axhline(0.5, color="red")
    path = tmp_path / "guide.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("d1 line color RED", "d1 line color RED ymax 2"),
        encoding="utf-8",
    )
    rec = parse_gle_figure(path)
    ax2 = rec.figure.axes_list[0]
    assert ax2.reflines == []
    assert [line.get("ymax") for line in ax2.lines] == [2.0, None]


def test_a_qualifier_with_no_value_keeps_the_line_raw(tmp_path):
    """``mdist`` / ``deresolve`` with no value are kept as written (#165)."""
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "v.dat" d1=c1,c2 d2=c1,c2\n'
        "   d1 line mdist color RED\n"
        "   d2 line deresolve color BLUE\n"
        "end graph\n"
    )
    p = _write(tmp_path, "v.gle", src, {"v.dat": "0 1\n1 2\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.file_series == []
    assert ax.passthrough == [
        '   data "v.dat" d1=c1,c2 d2=c1,c2',
        "   d1 line mdist color RED",
        "   d2 line deresolve color BLUE",
    ]
    assert sum("not modelled" in w for w in rec.warnings) == 2


def test_per_point_marker_sizes_are_recovered(tmp_path):
    """gleplot's ``mdata`` scatter comes back as the built-in marker + sizes."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], s=[10, 40, 90], marker="^", label="b")
    path = tmp_path / "sized.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    (series,) = rec.figure.axes_list[0].scatters
    assert series["marker"] == "FTRIANGLE"
    assert series["mdata"] == pytest.approx(ax.scatters[0]["mdata"], rel=1e-5)
    assert series["markersize"] == pytest.approx(ax.scatters[0]["markersize"])
    assert rec.warnings == []


def test_a_missing_point_in_a_sized_scatter_round_trips(tmp_path):
    """The ``*`` written for a NaN point reads back as NaN and is rewritten."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).scatter([0, 1, 2], [2, float("nan"), 2], s=[10, 40, 90])
    path = tmp_path / "gap.gle"
    fig.savefig_gle(str(path))
    text, files = fig._generate_gle_with_files()
    rec = parse_gle_figure(path)
    (series,) = rec.figure.axes_list[0].scatters
    assert np.isnan(series["y"][1])
    assert rec.figure._generate_gle_with_files() == (text, files)


def test_an_edited_sized_scatter_kept_raw_keeps_its_marker_sub(tmp_path):
    """The parser drops the generated sub; a raw line naming it gets it back."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).scatter([0, 1, 2], [2, 1, 2], s=[10, 40, 90])
    path = tmp_path / "edited.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("mdata d2 color", "mdata d2 line color"), encoding="utf-8"
    )
    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].scatters == []
    out = tmp_path / "edited-again.gle"
    rec.figure.savefig_gle(str(out))
    again = out.read_text(encoding="utf-8")
    assert again.count("sub gleplot_mdata_fcircle size data\n") == 1
    assert "define marker gleplot_mdata_fcircle gleplot_mdata_fcircle\n" in again
    assert "marker gleplot_mdata_fcircle msize" in again


_USER_MDATA = (
    "! gleplot-meta-begin v2\n"
    "! gleplot: import-data = m.dat\n"
    "! gleplot-meta-end\n"
    "size 20.32 15.24\n"
    "sub bubble size data\n"
    "   circle size*data\n"
    "end sub\n"
    "define marker bub bubble\n"
    "begin graph\n"
    '   data "m.dat" d1=c1,c2 d2=c1,c3\n'
    "   d1 marker {marker} msize 0.4 mdata d2 color RED\n"
    "end graph\n"
)


@pytest.mark.parametrize("marker", ["bub", "circle"])
def test_a_hand_written_mdata_is_kept_raw_and_warned(tmp_path, marker):
    """``mdata`` on a marker sub of the user's own (or a built-in, which GLE
    draws at one size) is not modelled: the lines stay as written."""
    p = _write(
        tmp_path,
        "m.gle",
        _USER_MDATA.format(marker=marker),
        {"m.dat": "1 1 0.5\n2 2 1\n3 3 2\n"},
    )
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.scatters == [] and ax.lines == [] and ax.file_series == []
    assert any("'mdata'" in w and "raw GLE" in w for w in rec.warnings)
    out = tmp_path / "m-again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "define marker bub bubble\n" in text
    assert '   data "m.dat" d1=c1,c2 d2=c1,c3\n' in text
    assert f"   d1 marker {marker} msize 0.4 mdata d2 color RED\n" in text


def test_per_point_colours_are_recovered(tmp_path):
    """gleplot's colour-mapped scatter comes back as values, cmap and limits."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[3, -1, 8], cmap="Blues", vmin=-2.5, marker="D")
    path = tmp_path / "coloured.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    (series,) = rec.figure.axes_list[0].scatters
    assert series["marker"] == "FDIAMOND"
    assert list(series["cdata"]) == [3, -1, 8]
    assert (series["cmap"], series["vmin"], series["vmax"]) == ("blues", -2.5, 8.0)
    assert series["color"] is None
    assert rec.warnings == []


def test_a_point_without_a_colour_round_trips(tmp_path):
    """A missing value in the colour column of a file read back: the point is
    written missing, so GLE does not draw it, and that reads back the same."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).scatter([0, 1, 2], [2, 1, 2], c=[1, 5, 2])
    path = tmp_path / "gap.gle"
    fig.savefig_gle(str(path))
    dat = tmp_path / "data_0.dat"
    dat.write_text(dat.read_text().replace("1 1 5\n", "1 1 *\n"))
    rec = parse_gle_figure(path)
    (series,) = rec.figure.axes_list[0].scatters
    assert np.isnan(series["cdata"][1])
    text, files = rec.figure._generate_gle_with_files()
    assert files["data_0.dat"].splitlines()[2] == "* * *"
    rec.figure.savefig_gle(str(path))
    again = parse_gle_figure(path).figure
    assert again._generate_gle_with_files() == (text, files)


def test_an_edited_coloured_scatter_kept_raw_keeps_its_let_and_subs(tmp_path):
    """The parser drops the generated subs; a raw line naming one gets them
    back, and its ``let`` stays beside it."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3], cmap="magma")
    path = tmp_path / "edited.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("mdata d3 key", "mdata d3 line key"), encoding="utf-8")
    rec = parse_gle_figure(path)
    assert rec.figure.axes_list[0].scatters == []
    assert any("per-point colours" in w and "raw GLE" in w for w in rec.warnings)
    out = tmp_path / "edited-again.gle"
    rec.figure.savefig_gle(str(out))
    again = out.read_text(encoding="utf-8")
    assert again.count("sub gleplot_cdata_fcircle_magma size data\n") == 1
    assert again.count("sub gleplot_magma z\n") == 1
    assert (
        "    data data_0.dat d1=c1,c2 d2=c1,c3\n"
        "    let d3 = (d2-1)/(3-1)\n"
        "    d1 marker gleplot_cdata_fcircle_magma msize 0.134164 mdata d3 line"
    ) in again


def test_a_polar_coloured_scatter_round_trips(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111, projection="polar")
    ax.scatter([0.0, 1.0, 2.0], [1, 2, 3], c=[1, 2, 3], label="p")
    path = tmp_path / "polar.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    assert rec.warnings == []
    assert rec.figure._generate_gle_with_files() == fig._generate_gle_with_files()


def test_a_colour_marker_whose_mdata_is_not_a_colour_let_is_kept_raw(tmp_path):
    p = _write(
        tmp_path,
        "m.gle",
        _USER_MDATA.format(marker="gleplot_cdata_fcircle_viridis"),
        {"m.dat": "1 1 0.5\n2 2 1\n3 3 2\n"},
    )
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].scatters == []
    assert any("per-point colours" in w for w in rec.warnings)
    out = tmp_path / "m-again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert '   data "m.dat" d1=c1,c2 d2=c1,c3\n' in text
    assert "sub gleplot_cdata_fcircle_viridis size data\n" in text


def test_a_colour_marker_with_an_unknown_colormap_is_kept_raw(tmp_path):
    src = _USER_MDATA.format(marker="gleplot_cdata_fcircle_nope")
    src = src.replace("mdata d2", "mdata d3").replace(
        "d2=c1,c3\n", "d2=c1,c3\n   let d3 = (d2-0)/(2-0)\n"
    )
    p = _write(tmp_path, "m.gle", src, {"m.dat": "1 1 0.5\n2 2 1\n3 3 2\n"})
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].scatters == []
    assert any("per-point colours" in w for w in rec.warnings)
    out = tmp_path / "m-again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert (
        "   let d3 = (d2-0)/(2-0)\n"
        "   d1 marker gleplot_cdata_fcircle_nope msize 0.4 mdata d3 color RED\n"
    ) in text


def test_a_scatter_colorbar_is_recovered_onto_its_scatter(tmp_path):
    """The bar goes to the colour-mapped scatter drawn in its palette."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3], cmap="plasma")
    ax.scatter([0, 1, 2], [1, 2, 1], c=[4, 5, 6])
    fig.colorbar(ax=ax, label="v")
    # Move the bar onto the first scatter, which ax= alone does not pick.
    ax.scatters[0]["colorbar"] = ax.scatters[1].pop("colorbar")
    ax.scatters[0]["colorbar"].update(zmin=1.0, zmax=3.0, zstep=0.4)
    path = tmp_path / "bar.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    first, second = rec.figure.axes_list[0].scatters
    assert first["colorbar"]["zmax"] == 3.0 and first["colorbar"]["label"] == "v"
    assert "colorbar" not in second
    assert rec.warnings == []


@pytest.mark.parametrize("cmap", ["plasma", "viridis"])
def test_a_scatter_bar_beside_a_heatmap_stays_the_scatters(tmp_path, cmap):
    """A heatmap added after the scatter's bar draws no bar of its own."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3], vmin=0)
    fig.colorbar(ax=ax)
    ax.imshow([[0.0, 1.0], [2.0, 3.0]], cmap=cmap, extent=(0, 2, 0, 2))
    path = tmp_path / "bar.gle"
    fig.savefig_gle(str(path))
    rec = parse_gle_figure(path)
    assert rec.figure._generate_gle_with_files() == fig._generate_gle_with_files()
    if cmap == "plasma":
        assert rec.figure.axes_list[0].scatters[0]["colorbar"]["zmin"] == 0.0


@pytest.mark.parametrize("old_file", [False, True])
def test_an_inverted_heatmaps_bar_stays_the_heatmaps(tmp_path, old_file):
    """Its bar draws the reversed palette; older files wrote the forward one."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3], cmap="viridis_r", vmin=5, vmax=9)
    ax.scatter([0, 1, 2], [1, 2, 1], c=[4, 5, 6], cmap="viridis", vmin=5, vmax=9)
    hm = ax.imshow(
        [[0.0, 1.0], [2.0, 3.0]], cmap="viridis", extent=(0, 2, 0, 2), invert=True
    )
    fig.colorbar(hm, ax=ax)
    path = tmp_path / "bar.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    assert 'palette "gleplot_viridis_r"' in text
    if old_file:
        text = text.replace('palette "gleplot_viridis_r"', 'palette "gleplot_viridis"')
        path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path).figure.axes_list[0]
    assert rec.heatmaps[0]["colorbar"]["zmax"] == 3.0
    assert not any(sc.get("colorbar") for sc in rec.scatters)


def test_a_scatter_bar_goes_to_the_scatter_with_its_range(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3])
    fig.colorbar(ax=ax)
    ax.scatter([0, 1, 2], [1, 2, 1], c=[4, 5, 6])
    path = tmp_path / "bar.gle"
    fig.savefig_gle(str(path))
    first, second = parse_gle_figure(path).figure.axes_list[0].scatters
    assert first["colorbar"]["zmax"] == 3.0 and "colorbar" not in second


def test_a_colorbar_call_with_nothing_to_show_is_noted(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3])
    fig.colorbar()
    path = tmp_path / "bar.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            'palette "gleplot_viridis" width', 'palette "gleplot_magma" width'
        ),
        encoding="utf-8",
    )
    rec = parse_gle_figure(path)
    assert "colorbar" not in rec.figure.axes_list[0].scatters[0]
    assert any("color_range_vertical call was dropped" in w for w in rec.warnings)


def test_a_let_of_the_colour_shape_drawn_as_a_curve_is_not_a_colour(tmp_path):
    """``let dK = (dJ-a)/(b-a)`` with a line of its own is an ordinary curve."""
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   data "m.dat" d1=c1,c2\n'
        "   let d2 = (d1-1)/(3-1)\n"
        "   d2 line color RED\n"
        "end graph\n"
    )
    p = _write(tmp_path, "m.gle", src, {"m.dat": "1 1\n2 2\n3 3\n"})
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].scatters == []
    out = tmp_path / "m-again.gle"
    rec.figure.savefig_gle(str(out))
    assert "let d2 = (d1-1)/(3-1)\n" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "qualifiers",
    [
        "deresolve 1e999 xmin 1e999",
        # #167: these raised out of open_gle instead.
        "svg_smooth 1e999",
        "svg_smooth (1e999-1e999)",
        "lstyle 1e999",
        "lstyle -1e999",
    ],
)
def test_a_non_finite_qualifier_keeps_the_line_raw(tmp_path, qualifiers):
    """A non-finite count or style is not read: the line is kept as written
    (#165, #167)."""
    line = f"   d1 line {qualifiers} color RED"
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "v.dat" d1=c1,c2\n'
        f"{line}\n"
        "end graph\n"
    )
    p = _write(tmp_path, "inf.gle", src, {"v.dat": "0 1\n1 2\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.file_series == []
    assert line in ax.passthrough
    assert any(w.startswith("data:") for w in rec.warnings)


@pytest.mark.parametrize(
    "qualifiers",
    ["mscale 2 mcolor red", "autoscale", "nomissing", "bigfile", "x0axis"],
)
def test_an_unmodelled_dataset_qualifier_keeps_the_line_raw(tmp_path, qualifiers):
    """#165: a ``dN`` line with a word no series models is kept as written."""
    line = f"   d1 line marker circle {qualifiers}"
    src = f'begin graph\n   data "a.dat" d1=c1,c2\n{line}\nend graph\n'
    p = _write(tmp_path, "q.gle", src, {"a.dat": "0 1\n1 2\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.file_series == [] and ax.lines == []
    assert ax.passthrough == ['   data "a.dat" d1=c1,c2', line]
    assert any(
        w.startswith("data: '") and "on d1 is not modelled; the dataset line" in w
        for w in rec.warnings
    )

    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    assert line in out.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "meta, lines",
    [
        # Drawn through an offset let the recognizer consumed, which it does
        # only on gleplot's own file.
        (_imported("a.dat"), "   let d2 = d1+0.5\n   d2 line color red mscale 2\n"),
        # On the secondary axis, which the layout reserves room for.
        ("", "   d1 line color red y2axis mscale 2\n"),
    ],
)
def test_an_unmodelled_qualifier_the_line_cannot_keep_is_reported(
    tmp_path, meta, lines
):
    """#165: the series is modelled, and the note says what is dropped."""
    src = meta + f'begin graph\n   data "a.dat" d1=c1,c2\n{lines}end graph\n'
    p = _write(tmp_path, "q.gle", src, {"a.dat": "0 1\n1 2\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert len(ax.file_series + ax.lines) == 1
    assert not any("mscale" in line for line in ax.passthrough)
    assert any(
        w.startswith("data: 'mscale 2' on d") and "dropped on re-save" in w
        for w in rec.warnings
    )


def test_a_colour_mapped_scatter_kept_raw_keeps_its_let(tmp_path):
    """#165: a raw ``gleplot_cdata_`` line keeps the colour let it reads."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).scatter([0, 1, 2], [2, 1, 2], c=[1, 2, 3], cmap="viridis")
    path = tmp_path / "c.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    line = next(
        ln for ln in text.splitlines() if "gleplot_cdata_" in ln and " mdata " in ln
    )
    path.write_text(text.replace(line, line + " mscale 2"), encoding="utf-8")
    ax = parse_gle_figure(path).figure.axes_list[0]
    assert ax.scatters == []
    assert any(line.lstrip().startswith("let d") for line in ax.passthrough)
    assert ax.passthrough[-1].endswith("mscale 2")


def test_a_qualifier_on_a_contour_line_is_reported(tmp_path):
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    z = [[float(i * j) for j in range(5)] for i in range(4)]
    fig.add_subplot(111).contour(z, levels=[2, 4])
    path = tmp_path / "contour.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8")
    assert "d1 line color BLACK" in text
    path.write_text(
        text.replace("d1 line color BLACK", "d1 line color BLACK deresolve 2"),
        encoding="utf-8",
    )
    rec = parse_gle_figure(path)
    assert len(rec.figure.axes_list[0].contours) == 1
    assert any("'deresolve' on a contour" in w for w in rec.warnings)


def test_marker_config_mdist_comes_back_on_the_series(tmp_path):
    """The figure-wide default is written on each marked line, and read back there.

    The recovered figure has no ``GLEMarkerConfig.mdist``; its marked lines
    carry the value instead, so the script is the same.
    """
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure(marker=gleplot.GLEMarkerConfig(mdist=0.8))
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [1, 2, 1], marker="o")
    ax.plot([0, 1, 2], [2, 1, 2])
    path = tmp_path / "default.gle"
    fig.savefig_gle(str(path))
    recovered = parse_gle_figure(path).figure
    assert recovered.marker_config.mdist is None
    assert recovered.axes_list[0].lines[0]["mdist"] == 0.8
    assert "mdist" not in recovered.axes_list[0].lines[1]
    again = tmp_path / "default-again.gle"
    recovered.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


def test_dataset_qualifiers_on_an_errorbar_are_kept(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "pts.dat" d1=c1,c2 d2=c1,c3\n'
        "   d1 marker circle err d2 color BLUE deresolve 2 xmin 0.5\n"
        "end graph\n"
    )
    p = _write(tmp_path, "errqual.gle", src, {"pts.dat": "0 1 0.1\n1 2 0.2\n"})
    rec = parse_gle_figure(p)
    # No metadata block: the reference is kept, with its qualifiers.
    assert rec.figure.axes_list[0].file_series[0]["deresolve"] == 2
    assert not any("deresolve" in w for w in rec.warnings)

    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    fig.add_subplot(111).errorbar([0, 1], [1, 2], yerr=0.1)
    path = tmp_path / "eb.gle"
    fig.savefig_gle(str(path))
    text = path.read_text(encoding="utf-8").replace(
        " err ", " deresolve 2 average xmin 0.5 err ", 1
    )
    path.write_text(text, encoding="utf-8")
    rec = parse_gle_figure(path)
    errorbar = rec.figure.axes_list[0].errorbars[0]
    # As the reference above keeps them: GLE thins the markers, not the bars.
    assert (errorbar["deresolve"], errorbar["deresolve_average"]) == (2, True)
    assert errorbar["xmin"] == 0.5
    assert rec.warnings == []
    again = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(again))
    assert " deresolve 2 average xmin 0.5" in again.read_text(encoding="utf-8")
    third = tmp_path / "third.gle"
    parse_gle_figure(again).figure.savefig_gle(str(third))
    assert third.read_text(encoding="utf-8") == again.read_text(encoding="utf-8")


def test_an_explicit_smooth_on_a_step_series_round_trips(tmp_path):
    """A script that asks for both keeps the smooth. The pin only blocks the default."""
    _gleplot_axes._global_data_file_counter = 0
    fig = gleplot.figure()
    ax = fig.add_subplot(111)
    ax.step([0, 1, 2], [0, 1, 0], where="post")
    ax.lines[0]["smooth_mode"] = "smooth"
    path = tmp_path / "step-smooth.gle"
    fig.savefig_gle(str(path))
    cmd = [ln for ln in path.read_text(encoding="utf-8").splitlines() if "steps" in ln]
    assert len(cmd) == 1
    assert " smooth" in cmd[0]
    again = tmp_path / "step-smooth-again.gle"
    parse_gle_figure(path).figure.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8")


def test_smooth_on_a_file_line_mode_is_dropped(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "set hei 0.42328\n"
        "begin graph\n"
        '   data "modes.dat" d1=c1,c2\n'
        "   d1 line steps smooth color BLUE\n"
        "end graph\n"
    )
    p = _write(tmp_path, "smooth-steps.gle", src, {"modes.dat": "0 1\n1 2\n2 1\n"})
    rec = parse_gle_figure(p)
    assert any("line mode 'steps'" in w and "dropped" in w for w in rec.warnings)
    out = tmp_path / "smooth-steps-again.gle"
    rec.figure.savefig_gle(str(out))
    cmd = [ln for ln in out.read_text(encoding="utf-8").splitlines() if "steps" in ln]
    assert len(cmd) == 1
    assert "smooth" not in cmd[0]


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


def test_a_hist_let_with_no_display_command_stays_raw(tmp_path):
    fig = gleplot.figure(data_prefix="hist")
    fig.add_subplot(111).hist([0, 1], bins=4, range=(0, 1), histtype="step")
    src = tmp_path / "figure.gle"
    fig.savefig_gle(str(src))
    lines = src.read_text(encoding="utf-8").splitlines()
    src.write_text(
        "\n".join(ln for ln in lines if " line hist" not in ln) + "\n",
        encoding="utf-8",
    )
    recognized = parse_gle_figure(src)
    ax = recognized.figure.axes_list[0]
    assert ax.hists == []
    assert any("let d2 = hist d1" in ln for ln in ax.passthrough)
    assert any("histogram let d2 was not paired" in w for w in recognized.warnings)


@pytest.mark.parametrize(
    "before, after, written",
    [
        ("", "", '   data "d.dat" d1'),
        # Its source is drawn too, and keeps reading the same file.
        ("", "   d1 marker circle\n", '   data "d.dat" d1'),
        # A series written first is renumbered; the let still reads d.dat.
        ('   data "e.dat" d5\n   d5 line\n', "   d1 line\n", '   data "d.dat" d1'),
        # A sibling on the same statement is written on its own.
        ("", "   d3 line\n", "    data d.dat d1=c1,c2"),
    ],
)
def test_a_hist_let_on_a_users_file_stays_raw(tmp_path, before, after, written):
    """#174: a histogram of a file gleplot did not write never rewrites it."""
    dat = "0 2.3 5\n0.4 1.9 6\n0.9 2.5 7\n1.3 3.1 8\n"
    data = '   data "d.dat" d1=c1,c2 d3=c1,c3\n' if "d3" in after else ""
    src = (
        "size 10 8\nbegin graph\n"
        + before
        + (data or '   data "d.dat" d1\n')
        + "   let d2 = hist d1 step 0.5\n"
        + after
        + "   d2 line hist color red\n"
        + "end graph\n"
    )
    p = _write(tmp_path, "h.gle", src, {"d.dat": dat, "e.dat": "0 9\n1 8\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.hists == []
    assert "   let d2 = hist d1 step 0.5" in ax.passthrough
    assert any("histogram let d2 reads d1" in w for w in rec.warnings)

    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert (tmp_path / "d.dat").read_text(encoding="utf-8") == dat
    assert "import-data = d.dat" not in text
    assert written + "\n   let d2 = hist d1 step 0.5\n" in text


def test_a_hist_let_on_an_offset_let_stays_raw(tmp_path):
    """#174: a histogram of a ``let`` that stays raw is kept as written."""
    src = (
        "size 10 8\nbegin graph\n"
        '   data "d.dat" d1\n'
        "   let d2 = d1+1\n"
        "   let d3 = hist d2\n"
        "   d1 line\n"
        "   d2 line\n"
        "end graph\n"
    )
    p = _write(tmp_path, "o.gle", src, {"d.dat": "0 1\n1 2\n"})
    ax = parse_gle_figure(p).figure.axes_list[0]
    assert ax.hists == []
    assert "   let d3 = hist d2" in ax.passthrough


@pytest.mark.parametrize(
    "first",
    ["let d2 = hist d1", "let d2 = d1+1", "let d2 = sin(x) from 0 to 1"],
)
@pytest.mark.parametrize("redefine_last", [False, True])
def test_a_let_redefined_by_a_later_let_stays_raw(tmp_path, first, redefine_last):
    """#379: the second ``let`` is kept, with the first and its readers."""
    lines = ["   let d2 = d2*2", "   d2 line"]
    body = ['   data "d.dat" d1=c1,c2', f"   {first}"]
    body += lines[::-1] if redefine_last else lines
    meta = (
        "! gleplot-meta-begin v2\n! gleplot: dpi = 100\n"
        "! gleplot: import-data = d.dat\n! gleplot-meta-end\n"
    )
    src = meta + "size 10 8\nbegin graph\n" + "\n".join(body) + "\nend graph\n"
    p = _write(tmp_path, "r.gle", src, {"d.dat": "0 1\n1 2\n2 2\n"})
    rec = parse_gle_figure(p)
    ax = rec.figure.axes_list[0]
    assert ax.passthrough == body
    assert any(
        w.startswith("data: d2 is defined by more than one let") for w in rec.warnings
    )
    rec.figure.savefig_gle(str(p))
    assert "\n".join(body) in p.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "body",
    [
        [
            '   data "d.dat" d1=c1,c2 d3=c1,c3',
            "   let d4 = d3+1",
            "   d4 line",
            "   let d2 = d1+1",
            "   let d2 = d2*2",
            "   d2 line",
        ],
        [
            '   data "d.dat" d1=c1,c2 d2=c1,c3',
            "   let d2 = d2+1",
            "   let d2 = d2*2",
            "   d1 line",
            "   d2 line",
        ],
    ],
    ids=["shared-statement", "data-defined-target"],
)
def test_a_redefined_let_keeps_the_data_it_reads(tmp_path, body):
    """#379: the statement the lets read stays as written, with its readers.

    Modelling another dataset of it would rewrite the file the raw lets read.
    """
    meta = (
        "! gleplot-meta-begin v2\n! gleplot: dpi = 100\n"
        "! gleplot: import-data = d.dat\n! gleplot-meta-end\n"
    )
    src = meta + "size 10 8\nbegin graph\n" + "\n".join(body) + "\nend graph\n"
    p = _write(tmp_path, "r.gle", src, {"d.dat": "0 1 5\n1 2 6\n2 2 7\n"})
    rec = parse_gle_figure(p)
    assert rec.figure.axes_list[0].passthrough == body
    rec.figure.savefig_gle(str(p))
    assert "\n".join(body) in p.read_text(encoding="utf-8")
    assert (tmp_path / "d.dat").read_text(encoding="utf-8") == "0 1 5\n1 2 6\n2 2 7\n"


def test_a_string_naming_a_hist_source_does_not_keep_it_raw(tmp_path):
    """#174: only statements, not a title, can read a histogram's samples."""
    fig = gleplot.figure(data_prefix="hist")
    ax = fig.add_subplot(111)
    ax.hist([0, 1, 1], bins=2, range=(0, 1), histtype="step")
    ax.set_title("d1")
    first = tmp_path / "first.gle"
    fig.savefig_gle(str(first))
    recognized = parse_gle_figure(first)
    assert len(recognized.figure.axes_list[0].hists) == 1
    second = tmp_path / "second.gle"
    recognized.figure.savefig_gle(str(second))
    assert second.read_text(encoding="utf-8") == first.read_text(encoding="utf-8")


def _graph_file(tmp_path, *body):
    src = tmp_path / "fn.gle"
    src.write_text(
        "size 12 9\nbegin graph\n    size 12 9\n"
        + "".join(f"    {line}\n" for line in body)
        + "end graph\n",
        encoding="utf-8",
    )
    return src


def test_a_hand_written_function_let_becomes_a_function_series(tmp_path):
    src = _graph_file(
        tmp_path,
        "let d1 = sin(x) from 0 to 6.28 step 0.05",
        'd1 line color red key "sine"',
        "let d2 = exp(-x) from -1 to 2",
        "d2 lstyle 2",
        "d2 line",
    )
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    assert [dict(s) for s in ax.functions] == [
        {
            "expression": "sin(x)",
            "let_from": 0.0,
            "let_to": 6.28,
            "let_step": 0.05,
            "color": "red",
            "linestyle": "-",
            "linewidth": None,
            "label": "sine",
            "_draw_seq": 0,
        },
        {
            "expression": "exp(-x)",
            "let_from": -1.0,
            "let_to": 2.0,
            "color": None,
            "linestyle": ":",
            "linewidth": None,
            "_draw_seq": 1,
        },
    ]
    assert ax.passthrough == []
    text = rec.figure._generate_gle()
    assert "    let d1 = sin(x) from 0 to 6.28 step 0.05\n" in text
    assert '    d1 line color red key "sine"\n' in text
    assert "    let d2 = exp(-x) from -1 to 2\n    d2 line lstyle 2\n" in text


@pytest.mark.parametrize(
    "body",
    [
        # A space GLE does not end the expression at, inside brackets.
        ("let d1 = sin(x)*(x + 1) from 0 to 1", "d1 line"),
        # Parametric, a dataset reference, an option gleplot does not model,
        # and a bound that is an expression.
        ("let d1 = sin(x),cos(x) from 0 to 6", "d1 line"),
        ("let d1 = x from 0 to 1 nsteps 20", "d1 line"),
        ("let d1 = x from 0 to 2*pi", "d1 line"),
        # A display add_function would not write back the same.
        ("let d1 = x from 0 to 1", "d1 line marker circle"),
        ("let d1 = x from 0 to 1", "d1 line smooth"),
        ("let d1 = x from 0 to 1", "d1 line lstyle 1"),
        ("let d1 = x from 0 to 1", 'd1 line key ""'),
        ("let d1 = x from 0 to 1", "d1 marker circle"),
        # No display, and another command reading the dataset.
        ("let d1 = x from 0 to 1",),
        ("let d1 = x from 0 to 1", "d1 line", "fill x1,d1 color blue"),
    ],
)
def test_a_function_let_gleplot_cannot_model_stays_raw_in_place(tmp_path, body):
    src = _graph_file(tmp_path, *body)
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    assert ax.functions == []
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    written = out.read_text(encoding="utf-8")
    assert "".join(f"    {line}\n" for line in body) in written


@pytest.mark.parametrize(
    "body, kind",
    [
        (("data a.dat d1", "d1 line lwidth 0"), "file_series"),
        (("data a.dat d1=c1,c2", "d1 line color red lwidth 0"), "file_series"),
        (("data a.dat d1=c1,c2", "d1 line lwidth 0 y2axis"), "file_series"),
        (("let d1 = x from 0 to 1", "d1 line lwidth 0"), "functions"),
        (("data a.dat d1=c1,c2", "d1 line lwidth 0.03528"), "file_series"),
    ],
)
def test_a_default_sentinel_width_from_a_file_is_written_as_given(tmp_path, body, kind):
    """#172: 0 and 1 pt read from a file are not the style's default width."""
    (tmp_path / "a.dat").write_text("0 1\n1 2\n2 1\n", encoding="utf-8")
    src = _graph_file(tmp_path, *body)
    figure = parse_gle_figure(src).figure
    assert len(getattr(figure.axes_list[0], kind)) == 1
    out = tmp_path / "out.gle"
    figure.savefig_gle(str(out))
    width = body[1].split("lwidth ")[1].split()[0]
    written = out.read_text(encoding="utf-8")
    assert re.findall(r" lwidth (\S+)", written) == [width]
    again = tmp_path / "again.gle"
    parse_gle_figure(out).figure.savefig_gle(str(again))
    assert again.read_text(encoding="utf-8") == written


def test_a_raw_let_keeps_every_function_let_raw(tmp_path):
    # Renumbered, the second curve would become d1 and collide with the raw
    # let that keeps its own name.
    body = (
        "let d2 = x from 0 to 1 nsteps 5",
        "d2 line",
        "let d5 = sin(x) from 0 to 1",
        "d5 line",
    )
    src = _graph_file(tmp_path, *body)
    rec = parse_gle_figure(src)
    assert rec.figure.axes_list[0].functions == []
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    assert "".join(f"    {line}\n" for line in body) in out.read_text("utf-8")


def _fit_file(tmp_path, *body, imported=True):
    """A graph fitting ``d.dat``, listed as gleplot's sidecar when ``imported``."""
    (tmp_path / "d.dat").write_text("0 1\n1 3\n2 5\n", encoding="utf-8")
    meta = (
        "! gleplot-meta-begin v2\n! gleplot: import-data = d.dat\n"
        "! gleplot-meta-end\n"
        if imported
        else ""
    )
    src = tmp_path / "fit.gle"
    src.write_text(
        meta
        + "size 12 9\nbegin graph\n    size 12 9\n"
        + "".join(f"    {line}\n" for line in body)
        + "end graph\n",
        encoding="utf-8",
    )
    return src


def test_a_fit_let_on_a_gleplot_sidecar_becomes_a_fit_series(tmp_path):
    src = _fit_file(
        tmp_path,
        "data d.dat d1=c1,c2",
        "let d2 = fit d1 from -1 with a*x+b to 3 step 0.5",
        'd2 line color red key "line"',
    )
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    [fit] = ax.fits
    assert {k: v for k, v in fit.items() if k not in ("x", "y")} == {
        "expression": "a*x+b",
        "let_from": -1.0,
        "let_to": 3.0,
        "let_step": 0.5,
        "color": "red",
        "linestyle": "-",
        "linewidth": None,
        "label": "line",
        "data_file": "d.dat",
        "_draw_seq": 0,
    }
    assert fit["x"].tolist() == [0.0, 1.0, 2.0]
    assert fit["y"].tolist() == [1.0, 3.0, 5.0]
    assert ax.passthrough == []
    text = rec.figure._generate_gle()
    assert (
        "    data d.dat d1=c1,c2\n"
        "    let d2 = fit d1 with a*x+b from -1 to 3 step 0.5\n"
        '    d2 line color red key "line"\n'
    ) in text


@pytest.mark.parametrize(
    "routine, model",
    [
        ("linfit", "linear"),
        ("logefit", "exp"),
        ("log10fit", "exp10"),
        ("powxfit", "power"),
    ],
)
def test_a_closed_form_fit_let_becomes_a_model_fit_series(tmp_path, routine, model):
    src = _fit_file(
        tmp_path,
        "data d.dat d1=c1,c2",
        f"let d2 = {routine} d1 to 3 from 1",
        "d2 line",
    )
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    [fit] = ax.fits
    assert fit["model"] == model
    assert "expression" not in fit
    assert (fit["let_from"], fit["let_to"]) == (1.0, 3.0)
    assert "let_step" not in fit
    assert ax.passthrough == []
    assert (
        "    data d.dat d1=c1,c2\n"
        f"    let d2 = {routine} d1 from 1 to 3\n"
        "    d2 line\n"
    ) in rec.figure._generate_gle()


@pytest.mark.parametrize(
    "body",
    [
        # Options gleplot does not model.
        ("data d.dat d1=c1,c2", "let d2 = fit d1 with a*x+b rsq r", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = fit d1 with a*x+b xmin 1", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = linfit d1 rsq r", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = linfit d1 s s", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = linfit d1 limit_data o r", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = powxfit d1 xmin 1", "d2 line"),
        # A plain key that would read back as a placeholder, a key format
        # the writer does not write, and a result variable read elsewhere.
        ("data d.dat d1=c1,c2", "let d2 = linfit d1", 'd2 line key "{slope}"'),
        (
            "data d.dat d1=c1,c2",
            "let d2 = linfit d1 s o r",
            'd2 line key "a "+format$(s,"fix 2 nozeroes")',
        ),
        *(
            ("data d.dat d1=c1,c2", "let d2 = linfit d1 s o r", f"d2 line key {key}")
            for key in (
                '"{slope} "+num$(s)',
                '"a"+s',
                '"a"+num$(s)+',
                "num$(1)",
            )
        ),
        ("data d.dat d1=c1,c2", "let d2 = linfit d1", 'd2 line key "a"+"b"'),
        (
            "data d.dat d1=c1,c2",
            "let d2 = linfit d1 s o r",
            "d2 line",
            'title "slope \\expr{s}"',
        ),
        (
            "data d.dat d1=c1,c2",
            "let d2 = linfit d1 s o r",
            'd2 line key "a "+num$(s)',
            "let d3 = s*x",
            "d3 line",
        ),
        (
            "data d.dat d1=c1,c2",
            "let d2 = linfit d1 s o r",
            'd2 line key "a "+num$(s)',
            "d1 marker circle",
        ),
        ("data d.dat d1=c1,c2", "let d2 = logefit d1 limit_data_x", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = linfit d1 with a*x", "d2 line"),
        # GLE ignores a routine's step, which Axes.fit rejects.
        ("data d.dat d1=c1,c2", "let d2 = log10fit d1 step 0.5", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = fit d1", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = fit d1 with a*x + b", "d2 line"),
        # The data is drawn too, shares its statement or its file, or the
        # curve is not a plain line.
        (
            "data d.dat d1=c1,c2",
            "let d2 = fit d1 with a*x",
            "d1 marker circle",
            "d2 line",
        ),
        ("data d.dat d1=c1,c2 d3=c1,c2", "let d2 = fit d1 with a*x", "d2 line"),
        (
            "data d.dat d1=c1,c2",
            "data d.dat d3=c2,c1",
            "let d2 = fit d1 with a*x",
            "d2 line",
            "d3 line",
        ),
        ("data d.dat d1=c1,c2", "let d2 = fit d1 with a*x", "d2 marker circle"),
    ],
)
def test_a_fit_let_gleplot_cannot_model_stays_raw_in_place(tmp_path, body):
    src = _fit_file(tmp_path, *body)
    rec = parse_gle_figure(src)
    assert rec.figure.axes_list[0].fits == []
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    written = out.read_text(encoding="utf-8")
    for line in body:
        if line.startswith("let "):
            assert f"    {line}\n" in written
    # The fit still has the dataset it reads.
    assert "d.dat d1=" in written


def test_a_fit_let_on_the_callers_own_file_stays_raw(tmp_path):
    # Modelled, the fit would rewrite the caller's data file on save.
    body = ('data "d.dat" d1', "let d2 = fit d1 with a*x+b", "d2 line color red")
    src = _fit_file(tmp_path, *body, imported=False)
    rec = parse_gle_figure(src)
    assert rec.figure.axes_list[0].fits == []
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    assert "".join(f"    {line}\n" for line in body) in out.read_text("utf-8")
    assert (tmp_path / "d.dat").read_text("utf-8") == "0 1\n1 3\n2 5\n"


def test_result_variables_named_nowhere_else_are_dropped(tmp_path):
    src = _fit_file(
        tmp_path,
        "data d.dat d1=c1,c2",
        "let d2 = linfit d1 slope offset rsq",
        "d2 line",
    )
    rec = parse_gle_figure(src)
    [fit] = rec.figure.axes_list[0].fits
    assert fit["model"] == "linear"
    assert "    let d2 = linfit d1\n" in rec.figure._generate_gle()


def test_a_key_of_result_variables_becomes_placeholders(tmp_path):
    src = _fit_file(
        tmp_path,
        "data d.dat d1=c1,c2",
        "let d2 = logefit d1 from 1 to 3 E P R",
        'd2 line key "a="+format$(p,"sci 3 e expdigits 2 expsign")+" b="+num$(e)'
        '+" r "+format$(r,"fix 3")',
    )
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    [fit] = ax.fits
    assert fit["label"] == "a={prefactor:.2e} b={exponent} r {rsq:.3f}"
    assert ax.passthrough == []
    expression = (
        '"a="+format$(fit1_prefactor,"sci 3 e expdigits 2 expsign")+" b="+'
        'num$(fit1_exponent)+" r "+format$(fit1_rsq,"fix 3")'
    )
    text = rec.figure._generate_gle()
    assert (
        "    let d2 = logefit d1 from 1 to 3 fit1_exponent fit1_prefactor fit1_rsq\n"
        f"    d2 line key {expression}\n"
    ) in text
    assert f"    text {expression}" in text


def test_result_variables_read_by_another_key_stay_raw(tmp_path):
    # The GLE manual's example: the variables are set up before the graph
    # and shown by a key of their own.
    (tmp_path / "d.dat").write_text("0 1\n1 3\n2 5\n", encoding="utf-8")
    body = (
        "! gleplot-meta-begin v2\n! gleplot: import-data = d.dat\n"
        "! gleplot-meta-end\n"
        "size 12 9\n"
        "s = 0; o = 0; r = 0\n"
        "begin graph\n"
        "    size 12 9\n"
        "    data d.dat d1=c1,c2\n"
        "    let d2 = linfit d1 s o r\n"
        "    d2 line\n"
        "end graph\n"
        "begin key\n"
        '    text "slope "+format$(s,"fix 2")\n'
        "end key\n"
    )
    src = tmp_path / "fit.gle"
    src.write_text(body, encoding="utf-8")
    rec = parse_gle_figure(src)
    assert rec.figure.axes_list[0].fits == []
    text = rec.figure._generate_gle()
    assert "    let d2 = linfit d1 s o r\n" in text
    assert '    text "slope "+format$(s,"fix 2")\n' in text


def _derived_file(tmp_path, *body):
    """A graph over the caller's three-column ``d.dat``."""
    (tmp_path / "d.dat").write_text("0 1 2\n1 3 1\n2 5 4\n", encoding="utf-8")
    src = tmp_path / "derived.gle"
    src.write_text(
        "size 12 9\nbegin graph\n    size 12 9\n"
        + "".join(f"    {line}\n" for line in body)
        + "end graph\n",
        encoding="utf-8",
    )
    return src


def test_a_dataset_let_on_drawn_series_becomes_a_derived_series(tmp_path):
    # The let comes first, as it often does by hand; GLE runs it at the end.
    src = _derived_file(
        tmp_path,
        "data d.dat d1=c1,c2 d2=c1,c3",
        "let d3 = d2-d1 from 0 to 2 nsteps 5 where d1>1 range d2",
        "d1 line",
        "d2 line",
        'd3 line color red key "diff"',
    )
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    [derived] = ax.derived_series
    assert derived["expression"] == "d1-d2"
    assert derived["sources"] == [["file_series", 1], ["file_series", 0]]
    assert derived["let_where"] == "d2>1"
    assert derived["let_range"] == [["file_series", 1]]
    assert (derived["let_from"], derived["let_to"]) == (0.0, 2.0)
    assert derived["let_nsteps"] == 5
    assert derived["label"] == "diff"
    assert ax.passthrough == []
    assert (
        "    let d3 = d2-d1 from 0 to 2 nsteps 5 where d1>1 range d2\n"
        '    d3 line color red key "diff"\n'
    ) in rec.figure._generate_gle()


def test_an_offset_let_on_a_drawn_dataset_is_a_derived_series(tmp_path):
    # gleplot never draws the dataset it offsets, so this is arithmetic.
    src = _derived_file(
        tmp_path, "data d.dat d1=c1,c2", "let d2 = d1+5", "d1 line", "d2 line"
    )
    ax = parse_gle_figure(src).figure.axes_list[0]
    assert [fs.get("offset") for fs in ax.file_series] == [None]
    [derived] = ax.derived_series
    assert derived["expression"] == "d1+5"
    assert derived["sources"] == [["file_series", 0]]


def test_a_dataset_let_left_raw_keeps_every_let_beside_it_raw(tmp_path):
    # d1 is never drawn, so the derived let stays raw. Renumbering the
    # function curve beside it would let it take the name d1 reads.
    body = (
        "data d.dat d1=c1,c2",
        "let d2 = sin(x) from 0 to 3",
        "let d3 = d1*2",
        "d2 line",
        "d3 line",
    )
    src = _derived_file(tmp_path, *body)
    rec = parse_gle_figure(src)
    ax = rec.figure.axes_list[0]
    assert ax.functions == [] and ax.derived_series == []
    assert "".join(f"    {line}\n" for line in body) in rec.figure._generate_gle()


def test_an_offset_let_stays_an_offset_when_it_cannot_be_derived(tmp_path):
    # d1 is an error bar, so ``let d2 = d1+5`` is read as before: an offset.
    src = _derived_file(
        tmp_path,
        "data d.dat d1=c1,c2 d3=c1,c3",
        "d1 line color red err d3",
        "let d2 = d1+5",
        "d2 line color blue",
    )
    ax = parse_gle_figure(src).figure.axes_list[0]
    assert ax.derived_series == []
    assert "let d2 = d1+5" not in ax.passthrough


def test_a_derived_curve_keeps_its_place_in_the_key(tmp_path):
    src = _derived_file(
        tmp_path,
        "data d.dat d1=c1,c2 d2=c1,c3 d4=c1,c3",
        "let d3 = d1-d2",
        'd1 line key "a"',
        'd2 line key "b"',
        'd3 line key "diff"',
        'd4 line key "c"',
    )
    ax = parse_gle_figure(src).figure.axes_list[0]
    labels = sorted((*ax.file_series, *ax.derived_series), key=lambda s: s["_draw_seq"])
    assert [s["label"] for s in labels] == ["a", "b", "diff", "c"]


@pytest.mark.parametrize(
    "body",
    [
        # A dataset that is not a modelled line: an error bar, or no display.
        (
            "data d.dat d1=c1,c2 d2=c1,c3",
            "let d3 = d1-d2",
            "d1 line err d2",
            "d3 line",
        ),
        ("data d.dat d1=c1,c2", "let d2 = d1*2", "d2 line"),
        # Options gleplot does not model, or a where it cannot read whole.
        ("data d.dat d1=c1,c2", "let d2 = d1*2 notune", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 step 1 nsteps 3", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 where d1 > 1", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 where (d1 > 1", "d1 line", "d2 line"),
        (
            "data d.dat d1=c1,c2",
            "let d2 = d1*2 where d1>1 where d1<3",
            "d1 line",
            "d2 line",
        ),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 range x", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 range d1,d1", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 from a", "d1 line", "d2 line"),
        ("data d.dat d1=c1,c2", "let d2 = d1*2 nsteps 2.5", "d1 line", "d2 line"),
        # The parametric form, a curve read again, and a marked curve.
        ("data d.dat d1=c1,c2", "let d2 = 2*x,d1", "d1 line", "d2 line"),
        (
            "data d.dat d1=c1,c2",
            "let d2 = d1*2",
            "let d3 = d2+d1",
            "d1 line",
            "d2 line",
            "d3 line",
        ),
        ("data d.dat d1=c1,c2", "let d2 = d1*2", "d1 line", "d2 marker circle"),
    ],
)
def test_a_dataset_let_gleplot_cannot_model_stays_raw_in_place(tmp_path, body):
    src = _derived_file(tmp_path, *body)
    rec = parse_gle_figure(src)
    assert rec.figure.axes_list[0].derived_series == []
    out = tmp_path / "out.gle"
    rec.figure.savefig_gle(str(out))
    written = out.read_text(encoding="utf-8")
    for line in body:
        if line.startswith("let "):
            assert f"    {line}\n" in written


# --------------------------------------------------------------------------- #
# Page-level line state: set cap / set join / set dashlen
# --------------------------------------------------------------------------- #


def _line_state(fig):
    return fig.style.line_cap, fig.style.line_join, fig.style.dashlen


def test_hand_written_line_state_is_recognized_and_rewritten_in_place(tmp_path):
    src = (
        "size 10 8\n"
        "set hei 0.4\n"
        "set dashlen .2\n"
        "set JOIN Round\n"
        "set cap square\n"
        "begin graph\n"
        "   xaxis min 0 max 1\n"
        "end graph\n"
    )
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src))
    assert _line_state(rec.figure) == ("square", "round", 0.2)
    assert rec.figure.passthrough_header == []
    out = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "set cap square\nset join round\nset dashlen 0.2\nset hei 0.4\n" in text


@pytest.mark.parametrize(
    "preamble,cap",
    [
        # After a drawing statement: moving it up would restyle that stroke.
        ("amove 1 1\nrline 1 0\nset cap round", None),
        # The first is recognized; a second one restyles what follows it.
        ("set cap round\namove 1 1\nset cap butt", "round"),
        # An expression, an unknown word, a non-positive length, two settings.
        ("set dashlen 2*0.1", None),
        ("set cap pointy", None),
        ("set dashlen 0", None),
        ("set cap round join bevel", None),
        # Recognizing it would drop the comment.
        ("set cap round ! rounded ends", None),
    ],
)
def test_line_state_that_cannot_be_modelled_stays_raw(tmp_path, preamble, cap):
    src = "size 10 8\nset hei 0.4\n" + preamble + "\nbegin graph\nend graph\n"
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src))
    assert _line_state(rec.figure) == (cap, None, None)
    raw = preamble.splitlines()[1 if cap else 0 :]
    assert rec.figure.passthrough_header == raw
    out = tmp_path / "again.gle"
    rec.figure.savefig_gle(str(out))
    text = out.read_text(encoding="utf-8")
    assert "\n".join(raw) in text


def test_hand_written_texlabels_is_recognized_and_labels_stay_latex(tmp_path):
    src = (
        "size 10 8\n"
        "set texlabels 1\n"
        "set hei 0.4\n"
        "begin graph\n"
        '   xtitle "$\\mu_0 H$ (T)"\n'
        "   xaxis min 0 max 1\n"
        "end graph\n"
    )
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src))
    fig = rec.figure
    assert fig.style.usetex is True
    assert fig.passthrough_header == []
    ax = fig.axes_list[0]
    assert ax.xlabel_text == r"$\mu_0 H$ (T)"
    # A label set after loading also reaches LaTeX untranslated.
    ax.set_ylabel(r"$\chi$")
    assert ax.ylabel_text == r"$\chi$"
    out = tmp_path / "again.gle"
    fig.savefig_gle(str(out))
    assert "set texlabels 1\nset hei 0.4\n" in out.read_text(encoding="utf-8")


def test_texlabels_after_a_texpreamble_block_is_recognized(tmp_path):
    block = ["begin texpreamble", "   \\usepackage{amsmath}", "end texpreamble"]
    src = (
        "size 10 8\n" + "\n".join(block) + "\nset texlabels 1\nbegin graph\nend graph\n"
    )
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src))
    assert rec.figure.style.usetex is True
    assert rec.figure.passthrough_header == block


@pytest.mark.parametrize(
    "preamble",
    [
        # GLE's own default; recognizing it would drop the line.
        "set texlabels 0",
        # After a drawing statement: moving it up would send that text to LaTeX.
        'amove 1 1\nwrite "a_b"\nset texlabels 1',
        "set texlabels 1 ! LaTeX",
    ],
)
def test_texlabels_that_cannot_be_modelled_stays_raw(tmp_path, preamble):
    src = "size 10 8\nset hei 0.4\n" + preamble + "\nbegin graph\nend graph\n"
    rec = parse_gle_figure(_write(tmp_path, "s.gle", src))
    assert rec.figure.style.usetex is False
    assert rec.figure.passthrough_header == preamble.splitlines()


@pytest.mark.parametrize("kind", ["function", "derived", "hist"])
def test_external_key_listing_a_curve_comes_back_as_the_legend(tmp_path, kind):
    """#208: a ``begin key`` naming a function, derived or histogram curve.

    The legend lists the curve in a different place from its draw order, so
    the writer puts it in a ``begin key`` block after the graph; it comes back
    as the axes' legend, and the text after it as a text annotation.
    """
    fig = gleplot.figure()
    ax = fig.add_subplot()
    ax.plot([0, 1, 2], [1, 2, 3], label="data")
    # Each curve is drawn in a different place from where it was added.
    if kind == "derived":
        ax.derived("d1*2", ax.lines[0], label="f")
    ax.scatter([0.5, 1.5], [1, 2], label="pts")
    if kind == "function":
        ax.function("x", label="f")
    elif kind == "hist":
        ax.hist([0.1, 0.5, 0.6, 1.2], histtype="step", label="f")
    ax.legend()
    ax.text(0.5, 0.5, "note")
    path = tmp_path / "a.gle"
    fig.savefig_gle(str(path))
    text = path.read_text()
    assert "begin key" in text

    got = parse_gle_figure(path).figure
    assert got.passthrough_trailer == []
    assert [t["text"] for t in got.axes_list[0].texts] == ["note"]
    out = tmp_path / "b.gle"
    got.savefig_gle(str(out))
    assert out.read_text() == text


def test_external_key_naming_a_label_twice_is_kept_as_written(tmp_path):
    """A key entry carries only its label, so two same-label series could be
    stamped in either order; the block stays raw rather than swap them."""
    fig = gleplot.figure()
    ax = fig.add_subplot()
    ax.scatter([0, 1], [0, 1], label="s", zorder=10)
    ax.plot([0, 1], [1, 0], label="f", color="red")
    ax.bar([0, 1], [1, 2], label="f", color="green")
    ax.legend()
    path = tmp_path / "a.gle"
    fig.savefig_gle(str(path))
    text = path.read_text()
    assert "begin key" in text

    got = parse_gle_figure(path).figure
    assert "begin key" in got.passthrough_trailer
    out = tmp_path / "b.gle"
    got.savefig_gle(str(out))
    assert out.read_text() == text


@pytest.mark.parametrize(
    "sub, call",
    [
        (
            "sub gleplot_wedge cx cy r a1 a2 clr$ lbl$ ld pct$ pd",
            'gleplot_wedge 0 0 1 0 90 "RED" "a" 1.1 "" 0.6',
        ),
        ("sub gleplot_box x w cw lo q1 med q3 hi", "gleplot_box 1 0.5 0.25 0 1 2 3 4"),
    ],
    ids=["pie", "boxplot"],
)
def test_an_old_pie_or_box_sub_is_kept_as_raw_gle(tmp_path, sub, call):
    """gleplot has no pie or box plot: an old sub and its call stay raw."""
    path = tmp_path / "old.gle"
    path.write_text(
        f"size 10 10\n{sub}\n   amove xg(0) yg(0)\nend sub\n"
        "begin graph\n    xaxis min 0 max 3\nend graph\n"
        f"{call}\n"
    )
    recognized = parse_gle_figure(path)
    assert any(sub.split()[1] in w for w in recognized.warnings)
    text = recognized.figure._generate_gle_with_files()[0]
    assert sub in text
    assert call in text

"""Compiled numeric invariants for calibration record v2 (GLEstudio G9).

``tests/unit/test_calibration.py`` proves the *arithmetic* of
:mod:`gleplot.calibration`. This module proves the arithmetic describes
reality: every assertion here compares a number the module derived against a
number GLE produced, or against ink GLE actually put on a raster.

The two genuinely independent checks are:

* **the box record vs. measured ink** -- ``width()``/``height()`` of the
  injected ``begin name`` block against the bounding box of every non-white
  pixel in the rendered PNG, which is the only way to test a claim about what
  was *drawn* rather than what was *computed*;
* **the x2/y2 derivation vs. where GLE drew a line** -- a coloured reference
  line is plotted against the secondary axes at a known secondary-coordinate
  value, and the derived page-cm position is compared to the position of that
  colour in the raster. Since GLE has no ``x2g()``/``y2g()`` to ask, this is
  the only available oracle for SPEC 6.2's "the secondaries share the primary
  frame" derivation.

Both need the raster border: GLE's bitmaps carry a small fixed physical margin
per side which it quantizes to whole pixels, so the offset is *derived per
pixmap* from ``(pixmap_size - page_size * dpi / 2.54) / 2`` (SPEC 6.2), never
hard-coded. Measured here at 300 DPI: 0.0367 cm / 0.0381 cm.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import gleplot as glp
from gleplot.calibration import (
    AxesSpec,
    TextMetricRequest,
    build_text_metric_script,
    find_ctm_hazards,
    inject_text_metrics,
    instrument_script,
    parse_calibration_records,
)
from gleplot.compiler import GLECompiler
from gleplot.figure import Figure


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = [
    pytest.mark.gle,
    pytest.mark.skipif(not _gle_available(), reason="GLE binary not available"),
]

#: Render resolution for the raster measurements. High enough that the 0.05 cm
#: acceptance bar is ~6 px, so antialiasing spread cannot mask a real error.
DPI = 300

#: Acceptance bar for the box record against measured ink (plan G9).
BOX_TOLERANCE_CM = 0.05

#: Acceptance bar for a frame corner against the requested placement. GLE
#: reports these exactly; the slack is for float formatting in the record.
FRAME_TOLERANCE_CM = 0.005


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _compile(tmp_path: Path, text: str, stem: str = "fig"):
    """Write ``text``, compile it to PNG, return ``(combined_output, png)``.

    ``-verbosity 0`` drops GLE's banner while keeping ``print``, giving a clean
    record channel; both streams are returned because ``print`` lands on stderr
    and the parse layer is specified to accept either.
    """
    script = tmp_path / f"{stem}.gle"
    script.write_text(text, encoding="utf-8")
    proc = subprocess.run(
        ["gle", "-d", "png", "-r", str(DPI), "-verbosity", "0", script.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr, tmp_path / f"{stem}.png"


def _raster_border_cm(image_size, page_size_cm):
    """Per-side raster margin in cm, derived from the pixmap (SPEC 6.2).

    GLE adds a small fixed physical margin and quantizes it to whole pixels, so
    the cm value varies with DPI and must be measured per pixmap rather than
    assumed.
    """
    scale = DPI / 2.54
    bx = (image_size[0] - page_size_cm[0] * scale) / 2.0
    by = (image_size[1] - page_size_cm[1] * scale) / 2.0
    return bx, by


def _px_to_cm(x_px, y_px, image_size, page_size_cm):
    """Raster pixel -> page cm (origin bottom-left, y up), border removed."""
    scale = DPI / 2.54
    bx, by = _raster_border_cm(image_size, page_size_cm)
    return ((x_px - bx) / scale, page_size_cm[1] - (y_px - by) / scale)


def _ink_rect_cm(png_path, page_size_cm):
    """Bounding box in page cm of every non-white pixel in ``png_path``.

    Uses Pillow's own ``getbbox`` on the inverted image, which is exact and far
    faster than a Python pixel loop. The returned rect uses the *outer* edge of
    the extreme pixels, so it is the ink's full extent.
    """
    from PIL import Image, ImageChops

    with Image.open(png_path) as im:
        rgb = im.convert("RGB")
        white = Image.new("RGB", rgb.size, (255, 255, 255))
        bbox = ImageChops.difference(rgb, white).getbbox()
        size = rgb.size
    assert bbox is not None, "rendered page is blank"
    left, top, right, bottom = bbox  # right/bottom are exclusive
    x0, y0 = _px_to_cm(left, bottom, size, page_size_cm)
    x1, y1 = _px_to_cm(right, top, size, page_size_cm)
    return (x0, y0, x1, y1)


def _colour_centre_cm(png_path, page_size_cm, predicate):
    """Page-cm centre of every pixel satisfying ``predicate(array)``.

    Used to find where GLE actually drew a coloured reference line.
    ``predicate`` takes the ``(H, W, 3)`` uint8 array and returns a boolean
    mask. The centre of the matching pixels' bounding box is taken rather than
    a centroid so antialiased edges (which are lighter, and may fail the
    predicate) cannot bias the answer.
    """
    import numpy as np
    from PIL import Image

    with Image.open(png_path) as im:
        arr = np.asarray(im.convert("RGB"))
    size = (arr.shape[1], arr.shape[0])
    ys, xs = np.nonzero(predicate(arr))
    assert xs.size, "no pixel of the reference colour was rendered"
    cx_px = (int(xs.min()) + int(xs.max()) + 1) / 2.0
    cy_px = (int(ys.min()) + int(ys.max()) + 1) / 2.0
    return _px_to_cm(cx_px, cy_px, size, page_size_cm)


def _is_red(arr):
    return (arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)


def _is_blue(arr):
    return (arr[:, :, 2] > 150) & (arr[:, :, 0] < 100) & (arr[:, :, 1] < 100)


# --------------------------------------------------------------------------- #
# Frame corners
# --------------------------------------------------------------------------- #


def test_frame_corners_match_the_requested_placement(tmp_path):
    """``xg(xgmin)``/``yg(ygmin)``/... reproduce ``amove`` + ``size``.

    This is the SPEC 3.3 claim that ``amove x y`` + ``size w h`` + ``scale 1 1``
    round-trips the frame rect exactly, re-established through the v2 record
    and the parse layer rather than by reading GLE's numbers directly.
    """
    src = (
        "size 12 9\n"
        "amove 2.5 1.75\n"
        "begin graph\n"
        "   size 7.5 5.5\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min -5 max 25\n"
        "   let d1 = x*x\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, _png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    res = parse_calibration_records(out, [AxesSpec("ax1")])
    assert res.warnings == []

    cal = res.calibrations["ax1"]
    assert cal.frame_corners_cm == pytest.approx(
        (2.5, 1.75, 10.0, 7.25), abs=FRAME_TOLERANCE_CM
    )
    # ...and the derived map agrees with the corners it was built from.
    assert cal.data_to_cm(0, -5) == pytest.approx((2.5, 1.75), abs=FRAME_TOLERANCE_CM)
    assert cal.data_to_cm(10, 25) == pytest.approx((10.0, 7.25), abs=FRAME_TOLERANCE_CM)
    assert cal.data_to_cm(5, 10) == pytest.approx((6.25, 4.5), abs=FRAME_TOLERANCE_CM)


def test_frame_corners_match_placement_for_a_generated_figure(tmp_path):
    """Same claim, but for a script gleplot's own writer produced.

    The expected rect is read out of the emitted ``amove`` / ``size`` pair
    rather than from ``Axes.placement``: the writer computes the layout rects
    at write time (``Figure._layout_rects``) and does not store them back onto
    an auto-placed axes, so the script is the authority for what was asked for.
    """
    fig, ax = glp.subplots(figsize=(6, 4.5))
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16])
    ax.set_xlabel("X label")
    ax.set_ylabel("Y label")
    fig.savefig_gle(str(tmp_path / "fig.gle"))
    text = (tmp_path / "fig.gle").read_text(encoding="utf-8")

    amove = re.search(r"^amove ([\d.eE+-]+) ([\d.eE+-]+)$", text, re.MULTILINE)
    # ``[ \t]+`` and not ``\s+``: the latter would happily eat the newline
    # before the page-level ``size`` line and match that instead.
    size = re.search(r"^[ \t]+size ([\d.eE+-]+) ([\d.eE+-]+)$", text, re.MULTILINE)
    assert amove is not None and size is not None
    x, y = float(amove.group(1)), float(amove.group(2))
    w, h = float(size.group(1)), float(size.group(2))

    axes_id = ax.axes_id
    out, _png = _compile(tmp_path, instrument_script(text, [axes_id]).text, "inst")
    res = parse_calibration_records(out, [AxesSpec(axes_id)])
    assert res.warnings == []
    assert res.calibrations[axes_id].frame_corners_cm == pytest.approx(
        (x, y, x + w, y + h), abs=FRAME_TOLERANCE_CM
    )


# --------------------------------------------------------------------------- #
# Log axes
# --------------------------------------------------------------------------- #


def test_log_axis_is_affine_in_log10_through_the_parse_layer(tmp_path):
    """Equal decades occupy equal page distance, end to end.

    GLE's record carries only the range; the log-ness comes from the model via
    :class:`AxesSpec`. This checks the two combine into the mapping GLE
    actually drew, by asserting the decade spacing is uniform and the ends land
    exactly on the frame.
    """
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 1 max 1000 log\n"
        "   yaxis min 0.01 max 100 log\n"
        "   let d1 = x\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, _png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    res = parse_calibration_records(out, [AxesSpec("ax1", x_log=True, y_log=True)])
    assert res.warnings == []
    cal = res.calibrations["ax1"]
    x_map = cal.axis_map("x")
    y_map = cal.axis_map("y")

    assert x_map.to_cm(1) == pytest.approx(2.0, abs=FRAME_TOLERANCE_CM)
    assert x_map.to_cm(1000) == pytest.approx(10.0, abs=FRAME_TOLERANCE_CM)
    decades = [x_map.to_cm(10**k) for k in range(4)]
    gaps = [b - a for a, b in zip(decades, decades[1:])]
    assert gaps == pytest.approx([8.0 / 3.0] * 3, abs=1e-9)

    # Four decades over 6 cm on y.
    y_decades = [y_map.to_cm(10.0**k) for k in range(-2, 3)]
    y_gaps = [b - a for a, b in zip(y_decades, y_decades[1:])]
    assert y_gaps == pytest.approx([1.5] * 4, abs=1e-9)

    # Round trip through the inverse.
    assert y_map.to_data(y_map.to_cm(3.7)) == pytest.approx(3.7)


def test_log_flag_comes_from_the_model_not_from_gle(tmp_path):
    """The same record read with the wrong flag gives a different map.

    Not a defect -- it is why SPEC 6.2 says log-ness must come from the model.
    Guards against anyone later "inferring" it from the printed range.
    """
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 1 max 1000 log\n"
        "   yaxis min 0 max 1\n"
        "   let d1 = 0.5\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, _png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    as_log = parse_calibration_records(out, [AxesSpec("ax1", x_log=True)])
    as_linear = parse_calibration_records(out, [AxesSpec("ax1")])
    assert as_log.calibrations["ax1"].axis_map("x").to_cm(10) == pytest.approx(
        2.0 + 8.0 / 3.0
    )
    assert as_linear.calibrations["ax1"].axis_map("x").to_cm(10) == pytest.approx(
        2.0 + 8.0 * 9.0 / 999.0
    )


# --------------------------------------------------------------------------- #
# Secondary-axis derivation vs. rendered ink
# --------------------------------------------------------------------------- #


def test_secondary_axis_maps_match_where_gle_drew_the_reference_lines(tmp_path):
    """The x2/y2 derivation predicts real ink positions.

    A red vertical line is plotted at ``x2 == 0.25`` and a blue horizontal line
    at ``y2 == 0.6``; both are drawn by GLE from *secondary* coordinates. The
    derived page-cm positions must match where those colours ended up in the
    raster. This is the empirical content of SPEC 6.2's claim that x2/y2 share
    the primary frame, which GLE offers no function to query.
    """
    (tmp_path / "vx2.dat").write_text("0.25 0\n0.25 1\n", encoding="utf-8")
    (tmp_path / "hy2.dat").write_text("0 0.6\n10 0.6\n", encoding="utf-8")
    page = (12.0, 9.0)
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        "   x2axis on min 0 max 1\n"
        "   y2axis on min 0 max 1\n"
        "   data vx2.dat d1=c1,c2\n"
        "   data hy2.dat d2=c1,c2\n"
        "   d1 line color red lwidth 0.02 x2axis y2axis\n"
        "   d2 line color blue lwidth 0.02 y2axis\n"
        "end graph\n"
    )
    out, png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    res = parse_calibration_records(out, [AxesSpec("ax1", has_x2=True, has_y2=True)])
    assert res.warnings == []
    cal = res.calibrations["ax1"]
    assert cal.x2_range == pytest.approx((0.0, 1.0))
    assert cal.y2_range == pytest.approx((0.0, 1.0))

    red_x, _ = _colour_centre_cm(png, page, _is_red)
    _, blue_y = _colour_centre_cm(png, page, _is_blue)

    assert cal.axis_map("x2").to_cm(0.25) == pytest.approx(red_x, abs=BOX_TOLERANCE_CM)
    assert cal.axis_map("y2").to_cm(0.6) == pytest.approx(blue_y, abs=BOX_TOLERANCE_CM)

    # And the secondary maps really do borrow the primary frame's extents.
    frame = cal.frame_corners_cm
    assert cal.axis_map("x2").cm_range == pytest.approx((frame[0], frame[2]))
    assert cal.axis_map("y2").cm_range == pytest.approx((frame[1], frame[3]))


def test_secondary_range_mirrors_the_primary_when_there_is_no_secondary_axis(tmp_path):
    """GLE reports the primary range in ``x2gmin``/``y2gmin`` with no x2/y2.

    The behaviour the ``has_x2``/``has_y2`` model flags exist to compensate
    for: without them a consumer would build a y2 map that is a silent
    duplicate of the y map and never know.
    """
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 3 max 17\n"
        "   yaxis min -2 max 42\n"
        "   let d1 = x\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, _png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    cal = parse_calibration_records(out, [AxesSpec("ax1")]).calibrations["ax1"]
    assert cal.x2_range == pytest.approx(cal.x_range)
    assert cal.y2_range == pytest.approx(cal.y_range)
    assert cal.axis_map("x2") is None
    assert cal.axis_map("y2") is None


# --------------------------------------------------------------------------- #
# Bounding box vs. measured ink
# --------------------------------------------------------------------------- #


def test_box_record_matches_measured_ink(tmp_path):
    """``glestudio-box`` is the label-inclusive extent GLE actually drew.

    SPEC 3.3's ``visual_bounds``. Measured against the raster because the whole
    point of the record is that axis decorations fall *outside* the placement
    rect by an amount only a render can know.
    """
    pytest.importorskip("PIL")
    page = (12.0, 9.0)
    src = (
        "size 12 9\n"
        "set hei 0.35\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        '   xtitle "the x axis"\n'
        '   ytitle "the y axis"\n'
        "   let d1 = 5*x\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, png = _compile(tmp_path, instrument_script(src, ["ax1"]).text)
    res = parse_calibration_records(out, [AxesSpec("ax1")])
    assert res.warnings == []
    box = res.boxes["ax1"]
    measured = _ink_rect_cm(png, page)

    assert box.rect == pytest.approx(measured, abs=BOX_TOLERANCE_CM)
    # The box is genuinely larger than the frame: decorations live outside it.
    frame = res.calibrations["ax1"].frame_rect_cm
    assert box.rect[0] < frame[0]
    assert box.rect[1] < frame[1]
    assert box.rect[2] > frame[2]
    assert box.rect[3] > frame[3]


# --------------------------------------------------------------------------- #
# Text metrics
# --------------------------------------------------------------------------- #


def test_text_metrics_scale_linearly_with_hei(tmp_path):
    """Doubling ``hei`` doubles width, height and depth (SPEC 6.3)."""
    requests = [
        TextMetricRequest("small", "Hello Ygq", hei=0.3),
        TextMetricRequest("big", "Hello Ygq", hei=0.6),
    ]
    script = build_text_metric_script(requests)
    assert script.warnings == []
    out, _png = _compile(tmp_path, script.text, "metrics")
    res = parse_calibration_records(out, [], measure_ids=["small", "big"])
    assert res.warnings == []

    small = res.metrics["small"]
    big = res.metrics["big"]
    assert small.width > 0
    assert big.width == pytest.approx(2 * small.width, rel=1e-6)
    assert big.height == pytest.approx(2 * small.height, rel=1e-6)
    assert big.depth == pytest.approx(2 * small.depth, rel=1e-6)
    # A descender makes tdepth negative; the raw sign is preserved.
    assert small.depth < 0


def test_text_metrics_track_the_requested_font(tmp_path):
    requests = [
        TextMetricRequest("a", "Hello Ygq", font="rm", hei=0.3),
        TextMetricRequest("b", "Hello Ygq", font="psh", hei=0.3),
    ]
    out, _png = _compile(tmp_path, build_text_metric_script(requests).text, "fonts")
    res = parse_calibration_records(out, [], measure_ids=["a", "b"])
    assert res.warnings == []
    assert res.metrics["a"].width != res.metrics["b"].width


def test_metrics_appended_to_a_figure_inherit_its_font_state(tmp_path):
    """SPEC 6.3: measure in the figure's *own* fonts and sizes.

    The request omits ``hei``, so the measurement must pick up the ``set hei``
    the figure established -- which is the reason the metric block is appended
    to the figure's script rather than compiled separately.
    """
    src = (
        "size 12 9\n"
        "set hei 0.5\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 1\n"
        "   yaxis min 0 max 1\n"
        "   let d1 = x\n"
        "   d1 line\n"
        "end graph\n"
    )
    combined = inject_text_metrics(
        instrument_script(src, ["ax1"]).text,
        [
            TextMetricRequest("inherited", "Hello Ygq"),
            TextMetricRequest("explicit", "Hello Ygq", hei=0.25),
        ],
    )
    assert combined.warnings == []
    out, _png = _compile(tmp_path, combined.text, "both")
    res = parse_calibration_records(
        out, [AxesSpec("ax1")], measure_ids=["inherited", "explicit"]
    )
    assert res.warnings == []
    # Calibration and metrics arrive together from one compile.
    assert "ax1" in res.calibrations
    assert res.metrics["inherited"].width == pytest.approx(
        2 * res.metrics["explicit"].width, rel=1e-6
    )


# --------------------------------------------------------------------------- #
# Stable ids under reorder
# --------------------------------------------------------------------------- #


def test_calibrations_follow_axes_ids_across_a_reorder(tmp_path):
    """A reorder moves the records, not the identities (G5 + SPEC 6.2).

    The two axes are given distinguishable placements, then the figure is
    reordered exactly as ``test_axes_id_preserved_across_reorder`` does. After
    the reorder each id must still map to *its own* geometry even though the
    record order (graph-block order) has swapped.
    """
    fig = glp.figure(figsize=(6, 6), data_prefix="g9")
    ax_a = fig.add_subplot(2, 1, 1)
    ax_a.plot([1, 2], [1, 2])
    ax_b = fig.add_subplot(2, 1, 2)
    ax_b.plot([3, 4], [3, 4])
    id_a, id_b = ax_a.axes_id, ax_b.axes_id
    specs = [AxesSpec(id_a), AxesSpec(id_b)]

    def calibrate(figure, stem):
        work = tmp_path / stem
        work.mkdir()
        figure.savefig_gle(str(work / "fig.gle"))
        text = (work / "fig.gle").read_text(encoding="utf-8")
        ids = [ax.axes_id for ax in figure.axes_list]
        script = work / "inst.gle"
        script.write_text(instrument_script(text, ids).text, encoding="utf-8")
        proc = subprocess.run(
            ["gle", "-d", "png", "-r", "100", "-verbosity", "0", script.name],
            cwd=work,
            capture_output=True,
            text=True,
        )
        res = parse_calibration_records(proc.stdout + proc.stderr, specs)
        assert res.warnings == [], res.warnings
        return res

    before = calibrate(fig, "before")
    frame_a = before.calibrations[id_a].frame_corners_cm
    frame_b = before.calibrations[id_b].frame_corners_cm
    assert frame_a != frame_b

    payload = fig.to_dict()
    payload["figure"]["axes"] = list(reversed(payload["figure"]["axes"]))
    reordered = Figure.from_dict(payload)
    assert [ax.axes_id for ax in reordered.axes_list] == [id_b, id_a]

    after = calibrate(reordered, "after")
    # Same identities, same geometry -- the record order swapped, the mapping
    # did not. A positional scheme would have silently swapped the frames.
    assert after.calibrations[id_a].frame_corners_cm == pytest.approx(frame_a)
    assert after.calibrations[id_b].frame_corners_cm == pytest.approx(frame_b)
    assert after.boxes[id_a].rect == pytest.approx(before.boxes[id_a].rect)


# --------------------------------------------------------------------------- #
# Fail-closed error state
# --------------------------------------------------------------------------- #


def test_erroring_document_produces_no_records_at_all(tmp_path):
    """The property GLEstudio's last-good-calibration retention rests on.

    GLE aborts before executing *any* ``print`` when the script has an error
    anywhere -- including on a line strictly *after* the print statements. So
    an instrumented broken document yields an empty result, never a partial or
    stale-mixed one (SPEC 6.2: this is normal operation, not error handling).
    """
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        "   let d1 = 5*x\n"
        "   d1 line\n"
        "end graph\n"
        "amove 1 1\n"
        "no_such_command 3\n"  # error *after* the injected prints
    )
    instrumented = instrument_script(src, ["ax1"])
    assert "no_such_command" in instrumented.text
    # The prints really do precede the error line.
    lines = instrumented.text.splitlines()
    assert lines.index("no_such_command 3") > max(
        i for i, line in enumerate(lines) if line.startswith('print "glestudio')
    )

    out, _png = _compile(tmp_path, instrumented.text, "broken")
    assert "aborting" in out.lower()
    res = parse_calibration_records(out, [AxesSpec("ax1")])
    assert res.calibrations == {}
    assert res.boxes == {}
    assert res.is_empty
    # The absence is reported, not swallowed.
    assert {w.category for w in res.warnings} == {"missing"}


def test_a_healthy_document_produces_records_for_every_axes(tmp_path):
    """Control for the test above: the same shape without the error."""
    src = (
        "size 12 9\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 4 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        "   let d1 = 5*x\n"
        "   d1 line\n"
        "end graph\n"
        "amove 7 1.6\n"
        "begin graph\n"
        "   size 4 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 1\n"
        "   yaxis min 0 max 1\n"
        "   let d1 = x\n"
        "   d1 line\n"
        "end graph\n"
    )
    out, _png = _compile(tmp_path, instrument_script(src, ["a", "b"]).text, "two")
    res = parse_calibration_records(out, [AxesSpec("a"), AxesSpec("b")])
    assert res.warnings == []
    assert set(res.calibrations) == {"a", "b"}
    assert set(res.boxes) == {"a", "b"}


# --------------------------------------------------------------------------- #
# The CTM guard is load-bearing
# --------------------------------------------------------------------------- #


def test_ctm_transform_really_corrupts_calibration(tmp_path):
    """Why :func:`find_ctm_hazards` exists, demonstrated by compiling one.

    Under ``translate 3 1`` the frame is really at page (5, 2.6) but the record
    reports (2, 1.6) -- silently, with no error and no visible symptom. The
    box record is wrong by the same offset. The guard flags the statement so
    GLEstudio can demote the axes instead of trusting either number.
    """
    src = (
        "size 15 11\n"
        "translate 3 1\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        "   let d1 = 5*x\n"
        "   d1 line\n"
        "end graph\n"
    )
    hazards = find_ctm_hazards(src)
    assert [(h.keyword, h.kind, h.line_no) for h in hazards] == [
        ("translate", "statement", 2)
    ]

    out, _png = _compile(tmp_path, instrument_script(src, ["ax1"]).text, "ctm")
    res = parse_calibration_records(out, [AxesSpec("ax1")])
    cal = res.calibrations["ax1"]
    # The record is the *user* coordinate, not the page coordinate: the frame
    # is drawn at page x=5 but reported at x=2.
    assert cal.frame_corners_cm == pytest.approx(
        (2.0, 1.6, 10.0, 7.6), abs=FRAME_TOLERANCE_CM
    )
    assert abs(cal.frame_corners_cm[0] - 5.0) > 1.0
    assert abs(res.boxes["ax1"].x - (1.42163 + 3.0)) > 1.0


def test_graph_nested_inside_a_ctm_block_is_not_instrumented_at_all(tmp_path):
    """The second line of defence, and a happy accident of the parser.

    ``begin translate`` is an opaque block whose body the parser keeps as raw
    lines, so a graph inside one is not a top-level graph block and
    :func:`instrument_script` never sees it. The result is *no* record rather
    than a wrong one -- which is the right failure, and consistent with the
    hazard the guard reports for the same source.
    """
    src = (
        "size 15 11\n"
        "begin translate 3 1\n"
        "amove 2 1.6\n"
        "begin graph\n"
        "   size 8 6\n"
        "   scale 1 1\n"
        "   xaxis min 0 max 10\n"
        "   yaxis min 0 max 100\n"
        "   let d1 = 5*x\n"
        "   d1 line\n"
        "end graph\n"
        "end translate\n"
    )
    assert [(h.keyword, h.kind, h.encloses_graph) for h in find_ctm_hazards(src)] == [
        ("translate", "block", True)
    ]
    instrumented = instrument_script(src, ["ax1"])
    assert instrumented.text == src

    out, _png = _compile(tmp_path, instrumented.text, "nested")
    res = parse_calibration_records(out, [AxesSpec("ax1")])
    assert res.is_empty


def test_gleplot_generated_scripts_carry_no_ctm_hazards(tmp_path):
    """The writer emits no page transforms, so nothing is ever demoted."""
    fig, axes = glp.subplots(2, 2, figsize=(8, 6))
    for ax in axes:
        ax.plot([1, 2, 3], [1, 4, 9])
        ax.set_xlabel("x")
    fig.savefig_gle(str(tmp_path / "grid.gle"))
    text = (tmp_path / "grid.gle").read_text(encoding="utf-8")
    assert find_ctm_hazards(text) == []
    # ...even though every graph block contains ``scale 1 1``.
    assert "scale 1 1" in text

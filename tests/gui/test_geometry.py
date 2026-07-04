"""Unit tests for the pure geometry layer (Track E1).

These are Qt-free: :mod:`gleplot.gui.geometry` imports nothing from PySide6, so
the calibration math and the GLE-output parser can be exercised directly.
"""

from __future__ import annotations

import math

import pytest

from gleplot.gui.geometry import (
    AxesCalibration,
    PreviewGeometry,
    parse_calibration_lines,
)


# --------------------------------------------------------------------------- #
# AxesCalibration: affine round-trips
# --------------------------------------------------------------------------- #

def _lin_cal():
    # Matches the empirically observed GLE output for a 2..12 / -1..1 axes:
    # corner (2,-1) -> (1,1) cm, corner (12,1) -> (4.33,6.62) cm.
    return AxesCalibration(
        index=0,
        x_range=(2.0, 12.0),
        y_range=(-1.0, 1.0),
        x_log=False,
        y_log=False,
        cm_rect=(1.0, 1.0, 4.33, 6.62),
    )


def test_linear_corners_map_to_cm_rect():
    cal = _lin_cal()
    assert cal.data_to_cm(2.0, -1.0) == pytest.approx((1.0, 1.0))
    assert cal.data_to_cm(12.0, 1.0) == pytest.approx((4.33, 6.62))


def test_linear_midpoint():
    cal = _lin_cal()
    cx, cy = cal.data_to_cm(7.0, 0.0)  # midpoints of both ranges
    assert cx == pytest.approx((1.0 + 4.33) / 2)
    assert cy == pytest.approx((1.0 + 6.62) / 2)


def test_linear_roundtrip():
    cal = _lin_cal()
    for x, y in [(2.0, -1.0), (12.0, 1.0), (5.5, 0.3), (7.0, 0.0)]:
        cx, cy = cal.data_to_cm(x, y)
        rx, ry = cal.cm_to_data(cx, cy)
        assert rx == pytest.approx(x)
        assert ry == pytest.approx(y)


def test_log_x_roundtrip_and_geometric_midpoint():
    cal = AxesCalibration(
        index=0,
        x_range=(1.0, 100.0),
        y_range=(-1.0, 1.0),
        x_log=True,
        y_log=False,
        cm_rect=(5.83, 1.0, 9.16, 6.62),
    )
    # Geometric midpoint (10) maps to the cm midpoint on a log axis.
    cx, _ = cal.data_to_cm(10.0, 0.0)
    assert cx == pytest.approx((5.83 + 9.16) / 2)
    # Endpoints.
    assert cal.data_to_cm(1.0, -1.0)[0] == pytest.approx(5.83)
    assert cal.data_to_cm(100.0, 1.0)[0] == pytest.approx(9.16)
    # Round-trip.
    for x in [1.0, 10.0, 100.0, 3.16227766]:
        cx, _ = cal.data_to_cm(x, 0.0)
        rx, _ = cal.cm_to_data(cx, 0.0)
        assert rx == pytest.approx(x)


def test_log_y_roundtrip_and_geometric_midpoint():
    cal = AxesCalibration(
        index=0,
        x_range=(2.0, 12.0),
        y_range=(0.1, 1000.0),
        x_log=False,
        y_log=True,
        cm_rect=(1.0, 1.0, 4.33, 6.62),
    )
    # geomean(0.1, 1000) = 10 -> cm midpoint on y.
    _, cy = cal.data_to_cm(7.0, 10.0)
    assert cy == pytest.approx((1.0 + 6.62) / 2)
    for y in [0.1, 1.0, 1000.0]:
        _, cy = cal.data_to_cm(7.0, y)
        _, ry = cal.cm_to_data(0.0, cy)
        assert ry == pytest.approx(y)


def test_log_log_roundtrip():
    cal = AxesCalibration(
        index=0,
        x_range=(1.0, 1000.0),
        y_range=(0.01, 100.0),
        x_log=True,
        y_log=True,
        cm_rect=(2.0, 2.0, 12.0, 8.0),
    )
    for x, y in [(1.0, 0.01), (1000.0, 100.0), (31.6227766, 1.0)]:
        cx, cy = cal.data_to_cm(x, y)
        rx, ry = cal.cm_to_data(cx, cy)
        assert rx == pytest.approx(x)
        assert ry == pytest.approx(y)


# --------------------------------------------------------------------------- #
# Non-positive on log axes
# --------------------------------------------------------------------------- #

def test_nonpositive_on_log_axis_clamps_not_nan():
    cal = AxesCalibration(
        index=0,
        x_range=(1.0, 100.0),
        y_range=(0.1, 1000.0),
        x_log=True,
        y_log=True,
        cm_rect=(5.83, 1.0, 9.16, 6.62),
    )
    cx, cy = cal.data_to_cm(0.0, -5.0)
    assert math.isfinite(cx)
    assert math.isfinite(cy)
    # Clamped to a tiny epsilon -> maps far below the low cm edge, never NaN.
    assert not math.isnan(cx)
    assert not math.isnan(cy)


def test_cm_to_data_on_log_never_nonpositive():
    cal = AxesCalibration(
        index=0,
        x_range=(1.0, 100.0),
        y_range=(0.1, 1000.0),
        x_log=True,
        y_log=True,
        cm_rect=(5.83, 1.0, 9.16, 6.62),
    )
    # Even well outside the box, log inverse stays strictly positive.
    x, y = cal.cm_to_data(-100.0, -100.0)
    assert x > 0.0
    assert y > 0.0


def test_degenerate_zero_span_range():
    cal = AxesCalibration(
        index=0,
        x_range=(5.0, 5.0),
        y_range=(1.0, 3.0),
        x_log=False,
        y_log=False,
        cm_rect=(1.0, 1.0, 4.0, 6.0),
    )
    # Zero-span x collapses to the low cm edge rather than dividing by zero.
    cx, _ = cal.data_to_cm(5.0, 2.0)
    assert cx == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Containment
# --------------------------------------------------------------------------- #

def test_contains_cm():
    cal = _lin_cal()  # box (1,1)-(4.33,6.62)
    assert cal.contains_cm(2.0, 3.0)
    assert cal.contains_cm(1.0, 1.0)  # corner inclusive
    assert cal.contains_cm(4.33, 6.62)
    assert not cal.contains_cm(0.5, 3.0)
    assert not cal.contains_cm(2.0, 7.0)


def test_contains_cm_handles_inverted_corner_order():
    # y0 > y1: containment must still work.
    cal = AxesCalibration(
        index=0,
        x_range=(0.0, 1.0),
        y_range=(0.0, 1.0),
        x_log=False,
        y_log=False,
        cm_rect=(1.0, 6.0, 4.0, 1.0),
    )
    assert cal.contains_cm(2.0, 3.0)


# --------------------------------------------------------------------------- #
# PreviewGeometry: cm <-> px with raster Y-flip
# --------------------------------------------------------------------------- #

def test_cm_to_px_yflip():
    geom = PreviewGeometry(page_size_cm=(10.16, 7.62), dpi=100, axes=[])
    scale = 100 / 2.54
    # Origin cm (0, 0) is the *bottom* left -> maps to bottom of the raster.
    px, py = geom.cm_to_px(0.0, 0.0)
    assert px == pytest.approx(0.0)
    assert py == pytest.approx(7.62 * scale)
    # Top-left cm (0, page_h) -> raster origin.
    px, py = geom.cm_to_px(0.0, 7.62)
    assert px == pytest.approx(0.0)
    assert py == pytest.approx(0.0)


def test_px_cm_roundtrip():
    geom = PreviewGeometry(page_size_cm=(10.16, 7.62), dpi=150, axes=[])
    for cx, cy in [(0.0, 0.0), (5.0, 3.0), (10.16, 7.62)]:
        px, py = geom.cm_to_px(cx, cy)
        rx, ry = geom.px_to_cm(px, py)
        assert rx == pytest.approx(cx)
        assert ry == pytest.approx(cy)


def test_axes_at_px():
    cal0 = AxesCalibration(0, (2, 12), (-1, 1), False, False, (1.0, 1.0, 4.33, 6.62))
    cal1 = AxesCalibration(1, (1, 100), (0.1, 1000), True, True, (5.83, 1.0, 9.16, 6.62))
    geom = PreviewGeometry(page_size_cm=(10.16, 7.62), dpi=100, axes=[cal0, cal1])
    # A point in the middle of axes 0's box (cm ~2.5, 3.8).
    px, py = geom.cm_to_px(2.5, 3.8)
    assert geom.axes_at_px(px, py) is cal0
    # A point in axes 1's box.
    px, py = geom.cm_to_px(7.5, 3.8)
    assert geom.axes_at_px(px, py) is cal1
    # A point in neither.
    px, py = geom.cm_to_px(5.0, 3.8)  # gap between the two boxes
    assert geom.axes_at_px(px, py) is None


def test_data_to_px_full_pipeline():
    # data -> cm -> px, the exact overlay pattern.
    cal = _lin_cal()
    geom = PreviewGeometry(page_size_cm=(10.16, 7.62), dpi=100, axes=[cal])
    cx, cy = cal.data_to_cm(2.0, -1.0)  # bottom-left data corner
    px, py = geom.cm_to_px(cx, cy)
    scale = 100 / 2.54
    assert px == pytest.approx(1.0 * scale)
    assert py == pytest.approx((7.62 - 1.0) * scale)


# --------------------------------------------------------------------------- #
# parse_calibration_lines: tolerance
# --------------------------------------------------------------------------- #

_REAL_OUTPUT = (
    "GLE 4.3.3[t.gle]-C-R-\n"
    "gleplot-cal 0  2   12   -1   1   1   1   4.33   6.62\n"
    "gleplot-cal 1  1   100   0.1   1000   5.83   1   9.16   6.62\n"
    "\n[out][.eps][.png]\n"
)


def test_parse_real_output():
    meta = [(False, False), (True, True)]
    cals, warnings = parse_calibration_lines(_REAL_OUTPUT, meta)
    assert warnings == []
    assert len(cals) == 2
    assert cals[0].index == 0
    assert cals[0].x_range == pytest.approx((2.0, 12.0))
    assert cals[0].y_range == pytest.approx((-1.0, 1.0))
    assert cals[0].cm_rect == pytest.approx((1.0, 1.0, 4.33, 6.62))
    assert cals[0].x_log is False and cals[0].y_log is False
    assert cals[1].x_log is True and cals[1].y_log is True
    assert cals[1].cm_rect == pytest.approx((5.83, 1.0, 9.16, 6.62))


def test_parse_extra_whitespace_and_tabs():
    text = "gleplot-cal    0 \t 2  12   -1\t1   1  1  4.33  6.62"
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert len(cals) == 1
    assert cals[0].x_range == pytest.approx((2.0, 12.0))


def test_parse_missing_line_reports_warning():
    text = "gleplot-cal 0  2 12 -1 1 1 1 4.33 6.62\n"
    cals, warnings = parse_calibration_lines(text, [(False, False), (False, False)])
    assert len(cals) == 1
    assert any("missing" in w and "1" in w for w in warnings)


def test_parse_garbage_is_skipped():
    text = (
        "gleplot-cal 0  2 12 -1 1 1 1 4.33 6.62\n"
        "gleplot-cal garbage not numbers here\n"
        "totally unrelated line\n"
    )
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert len(cals) == 1
    assert any("malformed" in w or "unparseable" in w for w in warnings)


def test_parse_out_of_range_index_skipped():
    text = "gleplot-cal 5  2 12 -1 1 1 1 4.33 6.62\n"
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert cals == []
    assert any("out of range" in w for w in warnings)


def test_parse_no_records():
    cals, warnings = parse_calibration_lines("no cal here at all\n", [(False, False)])
    assert cals == []
    assert any("missing" in w for w in warnings)


def test_parse_scientific_notation():
    text = "gleplot-cal 0  1e-3 1.5e2 -1 1 1 1 4.33 6.62\n"
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert len(cals) == 1
    assert cals[0].x_range == pytest.approx((1e-3, 150.0))


# --------------------------------------------------------------------------- #
# Invalid-calibration rejection (Finding 5)
# --------------------------------------------------------------------------- #

def test_invalid_reason_valid_axes():
    assert _lin_cal().invalid_reason() is None
    assert _lin_cal().is_valid() is True


def test_invalid_reason_log_nonpositive_bound():
    # x is log but its min is <= 0 -> undefined log space.
    cal = AxesCalibration(
        index=0,
        x_range=(0.0, 100.0),
        y_range=(0.1, 1000.0),
        x_log=True,
        y_log=True,
        cm_rect=(1.0, 1.0, 4.0, 6.0),
    )
    assert not cal.is_valid()
    assert "log" in cal.invalid_reason()

    # negative bound on a log y axis.
    cal_y = AxesCalibration(
        index=0,
        x_range=(1.0, 100.0),
        y_range=(-5.0, 1000.0),
        x_log=False,
        y_log=True,
        cm_rect=(1.0, 1.0, 4.0, 6.0),
    )
    assert not cal_y.is_valid()


def test_invalid_reason_min_equals_max():
    cal = AxesCalibration(
        index=0,
        x_range=(5.0, 5.0),
        y_range=(1.0, 3.0),
        x_log=False,
        y_log=False,
        cm_rect=(1.0, 1.0, 4.0, 6.0),
    )
    assert not cal.is_valid()
    assert "degenerate" in cal.invalid_reason()


def test_invalid_reason_degenerate_cm_rect():
    cal = AxesCalibration(
        index=0,
        x_range=(2.0, 12.0),
        y_range=(-1.0, 1.0),
        x_log=False,
        y_log=False,
        cm_rect=(1.0, 1.0, 1.0, 6.0),  # zero width
    )
    assert not cal.is_valid()
    assert "width" in cal.invalid_reason()


def test_parse_log_nonpositive_bound_skipped_with_warning():
    # A log axis (meta True/True) whose printed x-min is 0 must be skipped.
    text = "gleplot-cal 0  0 100 0.1 1000 5.83 1 9.16 6.62\n"
    cals, warnings = parse_calibration_lines(text, [(True, True)])
    assert cals == []
    assert any("skipped" in w and "log" in w for w in warnings)
    # Not also reported as "missing" (it was seen, just rejected).
    assert not any("missing" in w for w in warnings)


def test_parse_min_equals_max_skipped_with_warning():
    text = "gleplot-cal 0  5 5 -1 1 1 1 4.33 6.62\n"
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert cals == []
    assert any("skipped" in w and "degenerate" in w for w in warnings)


def test_parse_degenerate_cm_rect_skipped_with_warning():
    # cm corners give zero height (cy0 == cy1).
    text = "gleplot-cal 0  2 12 -1 1 1 3 4.33 3\n"
    cals, warnings = parse_calibration_lines(text, [(False, False)])
    assert cals == []
    assert any("skipped" in w and "height" in w for w in warnings)


def test_parse_valid_axes_unaffected_by_validation():
    # A mix: axes 0 valid, axes 1 invalid (log with non-positive bound).
    text = (
        "gleplot-cal 0  2 12 -1 1 1 1 4.33 6.62\n"
        "gleplot-cal 1  0 100 0.1 1000 5.83 1 9.16 6.62\n"
    )
    cals, warnings = parse_calibration_lines(text, [(False, False), (True, True)])
    assert len(cals) == 1
    assert cals[0].index == 0
    assert any("skipped" in w for w in warnings)

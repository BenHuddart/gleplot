"""Preview geometry abstraction for the gleplot GUI (Track E1).

This module is the pure-logic core that maps between three coordinate spaces so
draggable annotations can live in *data* coordinates while being drawn on a
raster preview:

    data (axis units)  <->  page cm (GLE page)  <->  view px (rendered raster)

The two mappings are deliberately layered and independent:

* :class:`AxesCalibration` owns ``data <-> cm`` for one graph block. The mapping
  is affine in linear space and affine in ``log10`` space when the relevant axis
  is logarithmic. It is renderer-agnostic: it knows only the axis data ranges
  and the page-cm rectangle of the axes box (both obtained from GLE at compile
  time; see :func:`parse_calibration_lines`).

* :class:`PreviewGeometry` owns ``cm <-> view`` for the *active raster* renderer
  (a PNG rendered at some DPI). The cm->px mapping here is intentionally thin so
  that a future SVG backend can supply its own ``cm <-> view`` scale without
  touching :class:`AxesCalibration` at all.

Renderer contract (for the SVG track)
-------------------------------------
Overlay code must always go ``data -> cm`` via :meth:`AxesCalibration.data_to_cm`
and only then ``cm -> view`` via the *active renderer's* mapping. For the PNG
raster that is :meth:`PreviewGeometry.cm_to_px`. An SVG backend would provide an
equivalent ``cm -> svg-user-units`` transform (the SVG viewBox is authored in
the same page-cm units GLE uses, so its mapping is a pure scale with no Y flip);
it should expose a method with the same signature as :meth:`cm_to_px` /
:meth:`px_to_cm` and reuse the :class:`AxesCalibration` list verbatim. Nothing in
:class:`AxesCalibration` is raster-specific, so no changes there are required.

Overlay usage (for the annotation track)
-----------------------------------------
Given ``geometry`` from ``PreviewController.geometry_ready`` and an annotation at
data ``(x, y)`` belonging to axes ``i``::

    cal = geometry.axes[i]
    cx, cy = cal.data_to_cm(x, y)          # data -> page cm
    px, py = geometry.cm_to_px(cx, cy)     # page cm -> raster px (Y already flipped)

and the inverse, when the user drops the handle at raster ``(px, py)``::

    cx, cy = geometry.px_to_cm(px, py)
    cal = geometry.axes_at_px(px, py)      # which axes was it dropped in?
    if cal is not None:
        x, y = cal.cm_to_data(cx, cy)      # cm -> data (may be None on log clamp)

Log-axis edge case
------------------
On a log axis the mapping is affine in ``log10(value)``, which is undefined for
non-positive values. A log axis whose *range* has a non-positive bound cannot be
calibrated at all, so :func:`parse_calibration_lines` rejects such an axes up
front (see :meth:`AxesCalibration.is_valid`); the range bounds fed to the
interpolation are therefore always strictly positive on a log axis.

Only *point inputs* to :meth:`AxesCalibration.data_to_cm` are still clamped: a
caller may ask for the cm position of a data point that happens to be
non-positive on a log axis (e.g. an annotation the user dragged to the edge),
and clamping it to a tiny positive epsilon keeps the handle pinned at the axis
edge instead of vanishing to NaN. :meth:`AxesCalibration.cm_to_data` can always
produce a valid positive value; the inverse never yields non-positive data on a
log axis, so it returns finite floats. Callers that need to reject out-of-range
results should use :meth:`AxesCalibration.contains_cm`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

__all__ = [
    "AxesCalibration",
    "PreviewGeometry",
    "parse_calibration_lines",
    "CM_PER_INCH",
]

#: Centimetres per inch (exact). Mirrors ``parser.units.INCH_TO_CM`` but kept
#: local so this Qt-free module has no cross-package import for a constant.
CM_PER_INCH = 2.54

#: Smallest positive value substituted for a non-positive coordinate on a log
#: axis before taking ``log10`` (see module docstring, "Log-axis edge case").
_LOG_EPS = 1e-300


def _to_log_space(value: float, is_log: bool, *, clamp: bool = False) -> float:
    """Map ``value`` into the space the axis is affine in.

    Linear axis -> value unchanged. Log axis -> ``log10(value)``.

    ``clamp`` controls the non-positive-input case, which only arises for *point
    inputs* to :meth:`AxesCalibration.data_to_cm` (a valid axes' *range* bounds
    are guaranteed positive on a log axis by :func:`parse_calibration_lines`, so
    they are mapped with ``clamp=False``). When ``clamp`` is true a non-positive
    value is pinned to :data:`_LOG_EPS` so the result stays finite (a handle
    dragged past the axis edge sticks at the edge instead of vanishing to NaN).
    """
    if not is_log:
        return value
    if clamp and value <= 0.0:
        value = _LOG_EPS
    return math.log10(value)


def _from_log_space(value: float, is_log: bool) -> float:
    """Inverse of :func:`_to_log_space`."""
    if not is_log:
        return value
    return 10.0 ** value


@dataclass
class AxesCalibration:
    """Calibration for a single graph block: ``data <-> page cm``.

    Attributes
    ----------
    index:
        Position of this axes in the figure's ``axes_list`` (== graph-block
        order == the ``<idx>`` printed in the ``gleplot-cal`` line).
    x_range, y_range:
        ``(min, max)`` data-coordinate ranges of the axes, as reported by GLE
        (``xgmin``/``xgmax`` and ``ygmin``/``ygmax``).
    x_log, y_log:
        Whether the corresponding axis is logarithmic. When true, the ``data
        <-> cm`` mapping is affine in ``log10`` space for that axis.
    cm_rect:
        ``(x0, y0, x1, y1)`` page-cm coordinates of the axes box: ``(x0, y0)``
        is the corner at ``(x_range[0], y_range[0])`` and ``(x1, y1)`` the
        corner at ``(x_range[1], y_range[1])``. In GLE page cm the origin is the
        bottom-left of the page and y increases upward, so typically
        ``y0 < y1``.
    """

    index: int
    x_range: Tuple[float, float]
    y_range: Tuple[float, float]
    x_log: bool
    y_log: bool
    cm_rect: Tuple[float, float, float, float]

    # -- data -> cm ---------------------------------------------------------
    def data_to_cm(self, x: float, y: float) -> Tuple[float, float]:
        """Map data coordinates ``(x, y)`` to page cm.

        Affine in linear space, affine in ``log10`` space on a log axis. A
        non-positive value on a log axis is clamped to a tiny positive epsilon
        (see module docstring) so the result is always a finite cm pair.
        """
        cx = self._interp(
            x, self.x_range, (self.cm_rect[0], self.cm_rect[2]), self.x_log
        )
        cy = self._interp(
            y, self.y_range, (self.cm_rect[1], self.cm_rect[3]), self.y_log
        )
        return cx, cy

    # -- cm -> data ---------------------------------------------------------
    def cm_to_data(self, cx: float, cy: float) -> Tuple[float, float]:
        """Map page-cm coordinates back to data coordinates.

        Exact inverse of :meth:`data_to_cm` for in-range inputs. On a log axis
        the result is always a positive finite value (never non-positive), so
        this method does not return ``None``; use :meth:`contains_cm` to test
        whether the point lies inside the axes box.
        """
        x = self._interp_inv(
            cx, (self.cm_rect[0], self.cm_rect[2]), self.x_range, self.x_log
        )
        y = self._interp_inv(
            cy, (self.cm_rect[1], self.cm_rect[3]), self.y_range, self.y_log
        )
        return x, y

    def contains_cm(self, cx: float, cy: float) -> bool:
        """True if page-cm point ``(cx, cy)`` lies within this axes box.

        Tolerant of either corner ordering (GLE's y grows upward, but this does
        not assume ``y0 < y1``).
        """
        x0, y0, x1, y1 = self.cm_rect
        xlo, xhi = (x0, x1) if x0 <= x1 else (x1, x0)
        ylo, yhi = (y0, y1) if y0 <= y1 else (y1, y0)
        return xlo <= cx <= xhi and ylo <= cy <= yhi

    def invalid_reason(self) -> Optional[str]:
        """Return why this calibration is unusable, or ``None`` if it is valid.

        A calibration is *invalid* (and produces corrupted math if used) when:

        * a log axis has a non-positive range bound (``log10`` is undefined, so
          the affine-in-log-space mapping cannot be built);
        * either axis has a degenerate range (``min == max``), which collapses
          the whole axis to a single cm edge and makes ``cm_to_data`` ambiguous;
        * the cm rectangle is degenerate (zero width or height), which makes the
          inverse ``cm -> data`` mapping divide by zero.

        :func:`parse_calibration_lines` calls this to skip a bad axes with a
        warning rather than silently emitting NaN/garbage coordinates.
        """
        x0d, x1d = self.x_range
        y0d, y1d = self.y_range
        if self.x_log and (x0d <= 0.0 or x1d <= 0.0):
            return "x is a log axis but its range has a non-positive bound"
        if self.y_log and (y0d <= 0.0 or y1d <= 0.0):
            return "y is a log axis but its range has a non-positive bound"
        if x0d == x1d:
            return "x range is degenerate (min == max)"
        if y0d == y1d:
            return "y range is degenerate (min == max)"
        cx0, cy0, cx1, cy1 = self.cm_rect
        if cx0 == cx1:
            return "cm rectangle has zero width"
        if cy0 == cy1:
            return "cm rectangle has zero height"
        return None

    def is_valid(self) -> bool:
        """True if this calibration can be used without corrupted math.

        Convenience wrapper over :meth:`invalid_reason`.
        """
        return self.invalid_reason() is None

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _interp(
        value: float,
        data_range: Tuple[float, float],
        cm_range: Tuple[float, float],
        is_log: bool,
    ) -> float:
        d0 = _to_log_space(data_range[0], is_log)
        d1 = _to_log_space(data_range[1], is_log)
        # ``value`` is a point input (an annotation coord), which may legitimately
        # be non-positive on a log axis (dragged past the edge): clamp it so the
        # result is finite. The range bounds are validated positive up front.
        v = _to_log_space(value, is_log, clamp=True)
        span = d1 - d0
        if span == 0.0:
            # Degenerate axis range: collapse to the low cm edge.
            return cm_range[0]
        frac = (v - d0) / span
        return cm_range[0] + frac * (cm_range[1] - cm_range[0])

    @staticmethod
    def _interp_inv(
        cm: float,
        cm_range: Tuple[float, float],
        data_range: Tuple[float, float],
        is_log: bool,
    ) -> float:
        c_span = cm_range[1] - cm_range[0]
        if c_span == 0.0:
            return data_range[0]
        frac = (cm - cm_range[0]) / c_span
        d0 = _to_log_space(data_range[0], is_log)
        d1 = _to_log_space(data_range[1], is_log)
        v = d0 + frac * (d1 - d0)
        return _from_log_space(v, is_log)


@dataclass
class PreviewGeometry:
    """Full preview geometry: page size, raster DPI, and per-axes calibration.

    Attributes
    ----------
    page_size_cm:
        ``(width, height)`` of the GLE page in cm (from the figure ``figsize``
        via :func:`gleplot.parser.units.inches_to_cm`).
    dpi:
        Resolution the raster was rendered at. Drives the ``cm <-> px`` scale.
    axes:
        Per-graph-block :class:`AxesCalibration`, in ``axes_list`` order.
    """

    page_size_cm: Tuple[float, float]
    dpi: int
    axes: List[AxesCalibration] = field(default_factory=list)

    # -- cm <-> px for the raster (renderer-specific mapping) ----------------
    def cm_to_px(self, cx: float, cy: float) -> Tuple[float, float]:
        """Map page-cm to raster pixel coordinates.

        ``px = cx * dpi / 2.54``. The raster's origin is the *top* left with y
        growing downward, whereas GLE page cm grows upward, so the y axis is
        flipped: ``py = (page_height - cy) * dpi / 2.54``.
        """
        scale = self.dpi / CM_PER_INCH
        px = cx * scale
        py = (self.page_size_cm[1] - cy) * scale
        return px, py

    def px_to_cm(self, px: float, py: float) -> Tuple[float, float]:
        """Inverse of :meth:`cm_to_px` (undoes the raster Y flip)."""
        scale = self.dpi / CM_PER_INCH
        cx = px / scale
        cy = self.page_size_cm[1] - py / scale
        return cx, cy

    def axes_at_px(self, px: float, py: float) -> Optional[AxesCalibration]:
        """Return the axes whose box contains raster point ``(px, py)``.

        Converts to cm first, then tests each calibration's box. Returns the
        first (lowest-index) match, or ``None`` if the point is outside every
        axes box.
        """
        cx, cy = self.px_to_cm(px, py)
        for cal in self.axes:
            if cal.contains_cm(cx, cy):
                return cal
        return None


# ------------------------------------------------------------------------- #
# Parsing GLE calibration output
# ------------------------------------------------------------------------- #

#: Matches one ``gleplot-cal <idx> <9 numbers>`` record, whitespace-tolerant.
#: GLE inserts variable spacing between fields, so we split on whitespace rather
#: than fixed columns. The leading token is matched loosely so the record can be
#: embedded in a longer stderr line.
_CAL_RE = re.compile(r"gleplot-cal\b(.*)")

_NUM_RE = re.compile(
    r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
)


def parse_calibration_lines(
    text: str,
    axes_meta: Sequence[Tuple[bool, bool]],
) -> Tuple[List[AxesCalibration], List[str]]:
    """Scan GLE output for ``gleplot-cal`` records into calibrations.

    Parameters
    ----------
    text:
        Combined stdout + stderr of the GLE compile. ``gleplot-cal`` lines may
        appear on either stream (they are on stderr for GLE 4.3.3) and carry
        GLE-inserted variable whitespace between fields.
    axes_meta:
        Per-axes ``(x_log, y_log)`` flags in ``axes_list`` order, taken from the
        model snapshot. Used to tag each calibration with its log flags (GLE's
        printed ranges do not encode which axis is logarithmic). The record's
        ``<idx>`` indexes into this sequence.

    Returns
    -------
    (calibrations, warnings):
        ``calibrations`` is the list of successfully parsed
        :class:`AxesCalibration`, sorted by ``index``. ``warnings`` is a list of
        human-readable strings describing skipped/malformed records; parsing is
        tolerant and never raises.
    """
    calibrations: List[AxesCalibration] = []
    warnings: List[str] = []
    seen_indices = set()

    for raw_line in text.splitlines():
        m = _CAL_RE.search(raw_line)
        if m is None:
            continue
        tail = m.group(1)
        nums = _NUM_RE.findall(tail)
        # Expected fields: idx + 4 data-range values (xgmin xgmax ygmin ygmax)
        # + 4 cm-corner values (xg(xgmin) yg(ygmin) xg(xgmax) yg(ygmax)) = 9.
        if len(nums) < 9:
            warnings.append(
                f"malformed gleplot-cal record (expected 9 fields, got "
                f"{len(nums)}): {raw_line.strip()!r}"
            )
            continue
        try:
            idx = int(float(nums[0]))
            xgmin, xgmax, ygmin, ygmax = (float(nums[i]) for i in range(1, 5))
            cx0, cy0, cx1, cy1 = (float(nums[i]) for i in range(5, 9))
        except (ValueError, IndexError):
            warnings.append(
                f"unparseable gleplot-cal record: {raw_line.strip()!r}"
            )
            continue

        if idx in seen_indices:
            warnings.append(f"duplicate gleplot-cal index {idx}; keeping first")
            continue

        if idx < 0 or idx >= len(axes_meta):
            warnings.append(
                f"gleplot-cal index {idx} out of range for {len(axes_meta)} "
                f"axes; skipped"
            )
            continue

        x_log, y_log = axes_meta[idx]
        cal = AxesCalibration(
            index=idx,
            x_range=(xgmin, xgmax),
            y_range=(ygmin, ygmax),
            x_log=bool(x_log),
            y_log=bool(y_log),
            cm_rect=(cx0, cy0, cx1, cy1),
        )
        reason = cal.invalid_reason()
        if reason is not None:
            # Mark the index seen so it is not also flagged "missing" below, but
            # skip it: an invalid calibration would emit corrupted coordinates.
            # The overlay simply has no items for this axes.
            seen_indices.add(idx)
            warnings.append(
                f"gleplot-cal index {idx} skipped ({reason}): {raw_line.strip()!r}"
            )
            continue
        seen_indices.add(idx)
        calibrations.append(cal)

    calibrations.sort(key=lambda c: c.index)

    # Warn about any axes we expected a calibration for but never saw.
    for i in range(len(axes_meta)):
        if i not in seen_indices:
            warnings.append(f"missing gleplot-cal record for axes index {i}")

    return calibrations, warnings

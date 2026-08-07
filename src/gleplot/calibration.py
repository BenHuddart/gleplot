"""Calibration record v2 -- preview instrumentation and geometry recovery.

This module is the Qt-free upstream half of GLEstudio's canvas interactivity
(GLEstudio SPEC 6.2/6.3/10.9). It does three separable jobs:

1. **Instrument** a *preview copy* of a generated GLE script
   (:func:`instrument_script`): wrap every top-level graph block in
   ``begin name glestudio_ax<id> ... end name`` and print, after each block, a
   13-field ``glestudio-cal`` record and a 4-field ``glestudio-box`` record.
   :func:`inject_text_metrics` appends ``glestudio-tw`` records measuring
   arbitrary strings in the figure's own fonts and sizes.
2. **Parse** GLE's stderr back into typed records
   (:func:`parse_calibration_records`) -- ANSI-stripped, tolerant of
   interleaved GLE chatter, and surfacing every anomaly as a
   :class:`CalibrationWarning` rather than dropping it.
3. **Guard** against the one thing that makes the numbers silently wrong
   (:func:`find_ctm_hazards`): a page-level ``scale``/``translate``/``rotate``
   changing the current transformation matrix around a graph block.

Marker spoofing (GLEstudio Phase-6 review, minor 10): a document can carry a
hand-written ``print "glestudio-cal <id> ..."`` as ordinary passthrough --
axes ids travel in ``project.json`` plaintext, so nothing prevents this -- and
it runs *before* the genuine record this module prints after the real graph
block. Since :func:`parse_calibration_records` keeps the first record per id,
that forged one would otherwise win, poisoning the data<->cm map canvas drags
are built on. The optional ``nonce``/``expected_nonce`` parameters on
:func:`instrument_script`, :func:`inject_text_metrics`,
:func:`build_text_metric_script` and :func:`parse_calibration_records`
(minted by :func:`new_calibration_nonce`) close this: every marker becomes
``glestudio-cal:<nonce>`` and only a record carrying the expected value is
accepted, everything else is reported as a ``"spoofed"`` warning and dropped
before id/duplicate handling ever sees it. Opt-in -- omitted, every function
here reproduces its exact pre-hardening behaviour.

Nothing here imports Qt, and nothing here touches the writer: instrumentation
is a *post-generation splice* over parsed source, so gleplot's default output
and its byte-identical fixed point are untouched by construction.

Empirically established facts this module is built on
----------------------------------------------------
Verified against GLE 4.3.10 (the versions/behaviours are load-bearing; re-check
before changing anything below):

* ``print`` output goes to **stderr**, one record per line, each line prefixed
  by an ANSI reset (``ESC[0m``). ``-verbosity 0`` drops the banner and keeps
  ``print``. :func:`strip_ansi` handles the prefix.
* ``xgmin``/``xgmax``/``ygmin``/``ygmax`` **and**
  ``x2gmin``/``x2gmax``/``y2gmin``/``y2gmax`` are all live after ``end graph``
  and survive an enclosing ``end name``, so both records can be printed
  together after the wrapper closes.
* GLE has **no** ``x2g()``/``y2g()`` function. The secondary axes share the
  primary frame, so their maps are *derived*: same cm extent, different data
  range (see :meth:`CalibrationV2.axis_map`).
* When a figure has no independent ``x2``/``y2`` axis, GLE still defines
  ``x2gmin``/``y2gmin``/... -- it reports the **primary** range there. The
  record therefore cannot tell you whether a secondary axis exists; that comes
  from the model, via :attr:`AxesSpec.has_x2` / :attr:`AxesSpec.has_y2`.
  Log-ness likewise comes from the model, never from GLE.
* ``ptx()/pty()/width()/height()`` on a named block give the **label-inclusive**
  bounding box (SPEC 3.3 ``visual_bounds``), accurate to well under the
  0.05 cm acceptance bar (see ``tests/integration/test_calibration_v2_gle.py``).
* ``twidth()/theight()/tdepth()`` exist and scale **exactly** linearly with
  ``set hei`` (doubling ``hei`` doubles all three). ``tdepth()`` is *negative*
  for glyphs with descenders; it is reported raw.
* **GLE aborts before executing any ``print``** when the script has an error
  anywhere -- even an error on a line *after* the print. Instrumentation is
  therefore fail-closed: an erroring document yields *no* records at all,
  which is exactly why GLEstudio retains a last-good calibration per axes id
  (SPEC 6.2) as normal operation rather than error handling.
* Block names accept ``[A-Za-z_][A-Za-z0-9_]*``; ``-`` and ``.`` are rejected
  and a leading digit is rejected. A raw uuid4 hex ``axes_id`` may start with a
  digit, so the ``glestudio_ax`` prefix is not decoration -- it is what makes
  the name legal. See :func:`block_name_for`.
* A CTM change genuinely corrupts calibration, in two different ways:
  ``xg()``/``yg()`` report the user coordinates in force *when the graph was
  drawn* (and are **not** re-mapped afterwards), while ``ptx()``/``pty()`` on a
  named block report device coordinates mapped through the CTM *in force at
  read time*. Measured under ``begin translate 3 1``: a frame really at page
  x=5 reported ``xg(xgmin) == 2`` both inside and outside the block, while
  ``ptx(...)`` reported 1.54 inside and 4.54 outside. Neither is the page
  coordinate. Hence :func:`find_ctm_hazards` and SPEC 6.2's demotion rule.
* GLE strings may be double- or single-quoted. The manual's doubled-``""``
  escape is **broken** in 4.3.10 (documented known bug) and aborts the script,
  so :func:`inject_text_metrics` quotes with whichever delimiter the text does
  not contain, and refuses (with a warning) a string containing both.

Relationship to the v1 path
---------------------------
:mod:`gleplot.gui.geometry` and ``gui/preview.py`` implement *calibration v1*:
a 9-field ``gleplot-cal`` record with no secondary ranges, no bounding box and
no text metrics, consumed only by gleplot's own annotation overlay. v1 is
deliberately left in place and untouched -- it is a different wire format
serving a different consumer, and rewiring a working preview to a superset
format buys gleplot's own GUI nothing. New consumers should use this module.
"""

from __future__ import annotations

import math
import re
import secrets
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from .parser.syntax import (
    BlankOrComment,
    GleDocument,
    GraphBlock,
    Node,
    OpaqueBlock,
    SourceLine,
    Statement,
    parse_gle_source,
)

__all__ = [
    "AxesSpec",
    "AxisMap",
    "BoxRecord",
    "CalibrationResult",
    "CalibrationV2",
    "CalibrationWarning",
    "CtmHazard",
    "InstrumentedScript",
    "TextMetric",
    "TextMetricRequest",
    "BLOCK_NAME_PREFIX",
    "CAL_MARKER",
    "BOX_MARKER",
    "TW_MARKER",
    "block_name_for",
    "build_text_metric_script",
    "find_ctm_hazards",
    "inject_text_metrics",
    "instrument_script",
    "new_calibration_nonce",
    "parse_calibration_records",
    "strip_ansi",
]


#: Prefix applied to every injected ``begin name`` identifier. Not decoration:
#: it guarantees the identifier starts with a letter, which GLE requires and a
#: raw uuid4 hex ``axes_id`` does not.
BLOCK_NAME_PREFIX = "glestudio_ax"

#: Leading token of the 13-field calibration record (SPEC 6.2).
CAL_MARKER = "glestudio-cal"

#: Leading token of the named-block bounding-box record (SPEC 6.2/3.3).
BOX_MARKER = "glestudio-box"

#: Leading token of the text-metric record (SPEC 6.3).
TW_MARKER = "glestudio-tw"

#: Smallest positive value substituted for a non-positive point coordinate on a
#: log axis before taking ``log10``, so a handle dragged past the axis edge
#: pins to the edge instead of becoming NaN. Range *bounds* are never clamped:
#: a log axis with a non-positive bound is rejected outright.
_LOG_EPS = 1e-300

#: CSI escape sequences GLE wraps its stderr lines in.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

#: Legal GLE block-name identifier.
_LEGAL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Characters that would break a record's leading id token (it is parsed by
#: whitespace splitting) or the ``print`` string literal carrying it.
_BAD_ID_RE = re.compile(r"[\s\"']")

#: Same restriction, reused to validate a caller-supplied ``nonce`` (GLEstudio
#: Phase-6 review, minor 10): it sits in the same string literal, immediately
#: before the id field, so it must be whitespace/quote-free for the same
#: reason an id must be.
_BAD_NONCE_RE = _BAD_ID_RE

#: Bare statements that modify the current transformation matrix. ``tran`` and
#: ``rot`` are GLE's documented abbreviations (``keyword.cpp``); all five are
#: accepted at top level (verified).
_CTM_STATEMENTS = frozenset({"translate", "tran", "scale", "rotate", "rot"})

#: ``begin <type>`` blocks that modify the CTM for their body
#: (``op_begin`` in GLE's ``op_def.cpp``). ``origin`` re-bases the coordinate
#: system on the current point; ``shear`` is the non-orthogonal cousin of
#: ``scale``.
_CTM_BLOCKS = frozenset(
    {"translate", "tran", "scale", "rotate", "rot", "origin", "shear"}
)

#: Opaque block types whose bodies are *data or literal text*, not GLE code.
#: :func:`find_ctm_hazards` does not descend into these: a ``begin text`` whose
#: prose contains the word "scale" is not a hazard. Every other opaque block
#: (``sub``, ``if``, ``object``, ``name``, ``clip``, ...) can contain real
#: drawing code and *is* descended into.
_NON_CODE_BLOCKS = frozenset(
    {
        "text",
        "tex",
        "texpreamble",
        "table",
        "key",
        "path",
        "box",
        "length",
        "letz",
        "fitz",
        "fit",
        "contour",
        "surface",
        "config",
    }
)

#: Bound on :func:`find_ctm_hazards` recursion into opaque blocks, so a
#: pathological or mis-parsed document cannot blow the stack.
_MAX_SCAN_DEPTH = 8


# --------------------------------------------------------------------------- #
# Warnings
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CalibrationWarning:
    """One thing that went wrong, categorized rather than stringly-typed.

    SPEC 8.1.4 forbids silent drops: every record this module refuses to use,
    every declared id it never saw a record for, and every record whose id it
    does not recognize produces one of these. They are *returned*, never
    logged and discarded.

    Attributes
    ----------
    category:
        One of ``"malformed"`` (a record that did not parse), ``"unknown-id"``
        (a well-formed record whose id is not in the caller's declared set),
        ``"missing"`` (a declared id with no record), ``"duplicate"`` (a second
        record for an id already seen), ``"invalid"`` (a well-formed record
        whose numbers cannot produce a usable map, e.g. a degenerate range),
        ``"injection"`` (a request that could not be instrumented) or
        ``"spoofed"`` (a record whose marker did not carry the caller's
        ``expected_nonce`` -- see :func:`parse_calibration_records` and
        :func:`new_calibration_nonce`).
    message:
        Human-readable description, suitable for GLEstudio's Output dock.
    subject:
        The axes id / measure id the warning is about, when there is one.
    """

    category: str
    message: str
    subject: Optional[str] = None

    def __str__(self) -> str:
        return self.message


# --------------------------------------------------------------------------- #
# Model-side description of an axes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AxesSpec:
    """What the *model* knows about one axes, which GLE's records do not.

    GLE prints numbers; it does not print whether an axis is logarithmic, nor
    whether a secondary axis exists at all (with no ``x2axis``, GLE reports the
    primary range in ``x2gmin``/``x2gmax`` -- verified). Both facts come from
    the caller's model snapshot and are carried here.

    Attributes
    ----------
    axes_id:
        The stable ``Axes.axes_id`` (G5). Written verbatim into the record and
        used as the dictionary key on the way back, so calibrations survive
        axes reordering.
    x_log, y_log, x2_log, y2_log:
        Whether the corresponding axis is logarithmic. A log axis's map is
        affine in ``log10`` rather than in the value.
    has_x2, has_y2:
        Whether the axes has an *independent* secondary axis. When false,
        :meth:`CalibrationV2.axis_map` returns ``None`` for that axis rather
        than a duplicate of the primary map.
    """

    axes_id: str
    x_log: bool = False
    y_log: bool = False
    x2_log: bool = False
    y2_log: bool = False
    has_x2: bool = False
    has_y2: bool = False


# --------------------------------------------------------------------------- #
# Axis maps
# --------------------------------------------------------------------------- #


def _to_log_space(value: float, is_log: bool, *, clamp: bool = False) -> float:
    """Map ``value`` into the space its axis is affine in.

    Linear axis -> unchanged. Log axis -> ``log10(value)``. ``clamp`` pins a
    non-positive input to :data:`_LOG_EPS`; it is used only for *point* inputs,
    never for range bounds (which :meth:`AxisMap.invalid_reason` rejects).
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
    return float(10.0**value)


@dataclass(frozen=True)
class AxisMap:
    """Affine ``data <-> page cm`` map for one axis of one axes.

    Affine in the value on a linear axis, affine in ``log10(value)`` on a log
    axis. This is the single primitive every derived map in SPEC 6.2 is built
    from -- the primary x/y maps take the frame's own cm extent and GLE's
    printed primary range; the secondary x2/y2 maps take the *same* cm extent
    and the printed secondary range (see :meth:`CalibrationV2.axis_map`).

    Attributes
    ----------
    data_range:
        ``(min, max)`` in data units, as printed by GLE.
    cm_range:
        ``(cm_at_min, cm_at_max)`` page centimetres. Not sorted: on GLE's page
        y grows upward, so a y map normally has ``cm_range[0] < cm_range[1]``,
        but a reversed axis legitimately inverts it.
    is_log:
        Whether the map is affine in ``log10`` (from the model, not from GLE).
    """

    data_range: Tuple[float, float]
    cm_range: Tuple[float, float]
    is_log: bool = False

    def invalid_reason(self) -> Optional[str]:
        """Why this map is unusable, or ``None`` if it is fine.

        A map is unusable when a log axis has a non-positive bound
        (``log10`` undefined), when the data range is degenerate (the whole
        axis collapses to one cm position, so the inverse is ambiguous), or
        when the cm extent is degenerate (the inverse divides by zero).
        """
        d0, d1 = self.data_range
        if self.is_log and (d0 <= 0.0 or d1 <= 0.0):
            return "log axis with a non-positive range bound"
        if not (math.isfinite(d0) and math.isfinite(d1)):
            return "non-finite data range"
        if d0 == d1:
            return "degenerate data range (min == max)"
        c0, c1 = self.cm_range
        if not (math.isfinite(c0) and math.isfinite(c1)):
            return "non-finite cm range"
        if c0 == c1:
            return "degenerate cm range (zero extent)"
        return None

    @property
    def is_valid(self) -> bool:
        """True if :meth:`invalid_reason` is ``None``."""
        return self.invalid_reason() is None

    def to_cm(self, value: float) -> float:
        """Map a data value to page centimetres.

        A non-positive value on a log axis is clamped to a tiny positive
        epsilon so the result stays finite (see :data:`_LOG_EPS`).
        """
        d0 = _to_log_space(self.data_range[0], self.is_log)
        d1 = _to_log_space(self.data_range[1], self.is_log)
        span = d1 - d0
        if span == 0.0:
            return self.cm_range[0]
        v = _to_log_space(value, self.is_log, clamp=True)
        frac = (v - d0) / span
        return self.cm_range[0] + frac * (self.cm_range[1] - self.cm_range[0])

    def to_data(self, cm: float) -> float:
        """Map page centimetres back to a data value.

        Exact inverse of :meth:`to_cm` for in-range inputs. On a log axis the
        result is always strictly positive, so this never yields a value the
        forward map would have had to clamp.
        """
        c_span = self.cm_range[1] - self.cm_range[0]
        if c_span == 0.0:
            return self.data_range[0]
        frac = (cm - self.cm_range[0]) / c_span
        d0 = _to_log_space(self.data_range[0], self.is_log)
        d1 = _to_log_space(self.data_range[1], self.is_log)
        return _from_log_space(d0 + frac * (d1 - d0), self.is_log)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CalibrationV2:
    """One parsed 13-field ``glestudio-cal`` record plus its model flags.

    The record's four cm numbers are ``xg(xgmin) yg(ygmin) xg(xgmax)
    yg(ygmax)`` -- the page-cm positions of the two opposite *frame* corners,
    which for a gleplot-emitted ``amove``/``size``/``scale 1 1`` graph block is
    exactly ``Axes.placement`` (SPEC 3.3). The *label-inclusive* box is a
    separate record, :class:`BoxRecord`.

    Attributes
    ----------
    axes_id:
        Stable model identity the record was tagged with.
    x_range, y_range:
        Primary ranges (``xgmin xgmax``, ``ygmin ygmax``).
    x2_range, y2_range:
        Secondary ranges (``x2gmin x2gmax``, ``y2gmin y2gmax``). When the
        figure has no secondary axis these mirror the primary range -- GLE
        defines the variables unconditionally. Use :attr:`has_x2`/
        :attr:`has_y2` to know whether they mean anything.
    frame_corners_cm:
        ``(x0, y0, x1, y1)``: ``(x0, y0)`` is the corner at
        ``(x_range[0], y_range[0])`` and ``(x1, y1)`` the corner at
        ``(x_range[1], y_range[1])``. GLE page cm, origin bottom-left, y up.
    x_log, y_log, x2_log, y2_log, has_x2, has_y2:
        Copied from the :class:`AxesSpec` the record was matched against.
    """

    axes_id: str
    x_range: Tuple[float, float]
    y_range: Tuple[float, float]
    x2_range: Tuple[float, float]
    y2_range: Tuple[float, float]
    frame_corners_cm: Tuple[float, float, float, float]
    x_log: bool = False
    y_log: bool = False
    x2_log: bool = False
    y2_log: bool = False
    has_x2: bool = False
    has_y2: bool = False

    # -- derived maps -------------------------------------------------------
    def axis_map(self, axis: str) -> Optional[AxisMap]:
        """Return the ``data <-> cm`` map for ``axis``, or ``None``.

        ``axis`` is ``"x"``, ``"y"``, ``"x2"`` or ``"y2"``.

        The **derivation** (SPEC 6.2, "GLE has no ``x2g()``/``y2g()``"): all
        four axes share one frame rectangle, so a secondary map differs from
        its primary only in the *data* range. Writing the frame corners as
        ``(cx0, cy0)`` and ``(cx1, cy1)``, and ``t`` for the identity (linear
        axis) or ``log10`` (log axis) of the axis in question::

            x  : cm(v) = cx0 + f(v, xgmin,  xgmax)  * (cx1 - cx0)
            x2 : cm(v) = cx0 + f(v, x2gmin, x2gmax) * (cx1 - cx0)
            y  : cm(v) = cy0 + f(v, ygmin,  ygmax)  * (cy1 - cy0)
            y2 : cm(v) = cy0 + f(v, y2gmin, y2gmax) * (cy1 - cy0)

            where f(v, lo, hi) = (t(v) - t(lo)) / (t(hi) - t(lo))

        i.e. x2 borrows the horizontal cm extent, y2 the vertical one. ``t``
        is chosen per axis from the model's own log flag, never from GLE.

        Returns ``None`` when the model says the requested secondary axis does
        not exist (asking for ``"y2"`` on a single-y figure would otherwise
        hand back a silent duplicate of the y map), or when the resulting map
        is degenerate (:meth:`AxisMap.invalid_reason`).
        """
        cx0, cy0, cx1, cy1 = self.frame_corners_cm
        if axis == "x":
            m = AxisMap(self.x_range, (cx0, cx1), self.x_log)
        elif axis == "y":
            m = AxisMap(self.y_range, (cy0, cy1), self.y_log)
        elif axis == "x2":
            if not self.has_x2:
                return None
            m = AxisMap(self.x2_range, (cx0, cx1), self.x2_log)
        elif axis == "y2":
            if not self.has_y2:
                return None
            m = AxisMap(self.y2_range, (cy0, cy1), self.y2_log)
        else:
            raise ValueError(f"unknown axis {axis!r} (expected x, y, x2 or y2)")
        return m if m.is_valid else None

    def invalid_reason(self) -> Optional[str]:
        """Why the *primary* maps are unusable, or ``None``.

        Only the primary pair is checked: a figure with a broken secondary
        range is still fully interactive on its primary axes, and
        :meth:`axis_map` already returns ``None`` for the broken one.
        """
        cx0, cy0, cx1, cy1 = self.frame_corners_cm
        for name, m in (
            ("x", AxisMap(self.x_range, (cx0, cx1), self.x_log)),
            ("y", AxisMap(self.y_range, (cy0, cy1), self.y_log)),
        ):
            reason = m.invalid_reason()
            if reason is not None:
                return f"{name}: {reason}"
        return None

    @property
    def is_valid(self) -> bool:
        """True if the primary maps are usable."""
        return self.invalid_reason() is None

    @property
    def frame_rect_cm(self) -> Tuple[float, float, float, float]:
        """Frame as ``(xlo, ylo, xhi, yhi)``, corner ordering normalized."""
        cx0, cy0, cx1, cy1 = self.frame_corners_cm
        return (min(cx0, cx1), min(cy0, cy1), max(cx0, cx1), max(cy0, cy1))

    # -- convenience --------------------------------------------------------
    def data_to_cm(
        self, x: float, y: float, *, x_axis: str = "x", y_axis: str = "y"
    ) -> Optional[Tuple[float, float]]:
        """Map a data point to page cm, or ``None`` if either map is absent.

        ``x_axis``/``y_axis`` select which of the (up to) four axes the point
        is expressed in -- ``y_axis="y2"`` for a series plotted against the
        secondary y axis, for instance.
        """
        mx = self.axis_map(x_axis)
        my = self.axis_map(y_axis)
        if mx is None or my is None:
            return None
        return mx.to_cm(x), my.to_cm(y)

    def cm_to_data(
        self, cx: float, cy: float, *, x_axis: str = "x", y_axis: str = "y"
    ) -> Optional[Tuple[float, float]]:
        """Inverse of :meth:`data_to_cm`."""
        mx = self.axis_map(x_axis)
        my = self.axis_map(y_axis)
        if mx is None or my is None:
            return None
        return mx.to_data(cx), my.to_data(cy)

    def contains_cm(self, cx: float, cy: float) -> bool:
        """True if page-cm point ``(cx, cy)`` lies inside the frame rect."""
        xlo, ylo, xhi, yhi = self.frame_rect_cm
        return xlo <= cx <= xhi and ylo <= cy <= yhi


@dataclass(frozen=True)
class BoxRecord:
    """One parsed ``glestudio-box`` record: the label-inclusive bounding box.

    This is SPEC 3.3's ``visual_bounds``: the extent of everything the graph
    block actually drew, tick labels and axis titles included, which is
    strictly larger than :attr:`CalibrationV2.frame_rect_cm`.

    Attributes
    ----------
    axes_id:
        Stable model identity.
    x, y:
        Page cm of the block's bottom-left corner (``ptx``/``pty`` of ``.bl``).
    width, height:
        Page cm extent.
    """

    axes_id: str
    x: float
    y: float
    width: float
    height: float

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        """``(xlo, ylo, xhi, yhi)`` page cm."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains_cm(self, cx: float, cy: float) -> bool:
        """True if page-cm point ``(cx, cy)`` lies inside the visual bounds."""
        xlo, ylo, xhi, yhi = self.rect
        return xlo <= cx <= xhi and ylo <= cy <= yhi


@dataclass(frozen=True)
class TextMetric:
    """One parsed ``glestudio-tw`` record (SPEC 6.3).

    Attributes
    ----------
    measure_id:
        Caller-chosen identity of the measurement request.
    width:
        ``twidth()`` -- advance width in page cm at the requested font/``hei``.
    height:
        ``theight()`` -- ink height above the baseline, page cm.
    depth:
        ``tdepth()`` -- ink depth below the baseline, page cm. GLE reports this
        **negative** for a string with descenders; the raw value is kept.
    """

    measure_id: str
    width: float
    height: float
    depth: float

    @property
    def total_height(self) -> float:
        """Baseline-to-baseline ink extent, ``height + abs(depth)``."""
        return self.height + abs(self.depth)


@dataclass
class CalibrationResult:
    """Everything :func:`parse_calibration_records` recovered from one compile.

    Attributes
    ----------
    calibrations, boxes:
        Keyed by ``axes_id``.
    metrics:
        Keyed by ``measure_id``.
    warnings:
        Every anomaly, in encounter order then completeness order. Never empty
        by convention only -- callers must surface these (SPEC 6.2).
    """

    calibrations: Dict[str, CalibrationV2] = field(default_factory=dict)
    boxes: Dict[str, BoxRecord] = field(default_factory=dict)
    metrics: Dict[str, TextMetric] = field(default_factory=dict)
    warnings: List[CalibrationWarning] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True if nothing at all was recovered.

        The expected state while the document has a compile error: GLE aborts
        before any ``print``, so a failed compile yields no records rather than
        partial ones (verified). GLEstudio treats this as "keep serving the
        last good calibration", not as a parse failure.
        """
        return not (self.calibrations or self.boxes or self.metrics)


# --------------------------------------------------------------------------- #
# Injection
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InstrumentedScript:
    """Result of :func:`instrument_script`.

    Attributes
    ----------
    text:
        The instrumented preview copy. The input is reproduced byte-for-byte
        apart from the inserted lines.
    block_names:
        ``axes_id -> begin name`` identifier actually emitted, for callers that
        want to reference the block themselves.
    warnings:
        Injection problems (an id that cannot be written into a record, a graph
        block left unclosed, more graph blocks than declared ids, ...).
    nonce:
        The marker-hardening nonce this call was given (echoed back verbatim),
        or ``None`` when the call was not hardened. Pass it on unchanged to any
        further :func:`inject_text_metrics`/:func:`build_text_metric_script`
        call composed with this one, and to :func:`parse_calibration_records`
        as ``expected_nonce`` (see :func:`new_calibration_nonce`).
    """

    text: str
    block_names: Dict[str, str] = field(default_factory=dict)
    warnings: List[CalibrationWarning] = field(default_factory=list)
    nonce: Optional[str] = None


def new_calibration_nonce() -> str:
    """Mint a fresh per-invocation nonce for calibration marker hardening.

    Closes GLEstudio Phase-6 review minor 10: without a nonce, a
    ``print "glestudio-cal <id> ..."`` smuggled into the document as plain
    passthrough (axes ids travel in ``project.json`` plaintext, so an
    attacker able to edit a ``.glez`` before it is opened can construct one)
    runs *before* the genuine record printed after the real graph block, and
    :func:`parse_calibration_records` keeping the first record per id lets
    the forged one win -- poisoning the data<->cm map that feeds canvas
    drags.

    Pass the same string as ``nonce=`` to :func:`instrument_script`,
    :func:`inject_text_metrics` and/or :func:`build_text_metric_script` for
    one compile, and as ``expected_nonce=`` to
    :func:`parse_calibration_records` when parsing that compile's output.
    Every ``glestudio-cal``/``glestudio-box``/``glestudio-tw`` record is then
    accepted only if it carries this exact value; anything else -- including
    a record with no nonce suffix at all -- is reported as a ``"spoofed"``
    :class:`CalibrationWarning` and dropped, rather than racing the genuine
    record for the first-parsed slot.

    Returns 16 hex characters from :func:`secrets.token_hex` -- unguessable,
    and safe to splice into a GLE string literal (no whitespace or quote
    characters). Mint a new one per preview compile: reusing one across
    compiles reopens a replay window this exists to close.
    """
    return secrets.token_hex(8)


def _validate_nonce(nonce: Optional[str]) -> None:
    """Reject a ``nonce`` that cannot be embedded in a GLE string literal.

    ``None`` (the "don't harden this call" default) always passes. A nonce is
    minted by this module's own code (:func:`new_calibration_nonce`) or
    supplied by a caller composing several calls around one shared value --
    either way a malformed one is a programming error, not attacker data, so
    this raises rather than warning.
    """
    if nonce is None:
        return
    if not nonce or _BAD_NONCE_RE.search(nonce):
        raise ValueError(
            f"nonce {nonce!r} must be a non-empty string with no whitespace "
            "or quote characters"
        )


def _marker_token(marker: str, nonce: Optional[str]) -> str:
    """Marker text for a print statement: ``marker`` or ``marker:nonce``."""
    return f"{marker}:{nonce}" if nonce else marker


def strip_ansi(text: str) -> str:
    """Remove CSI escape sequences from ``text``.

    GLE colours its stderr and prefixes even plain ``print`` output with a
    reset (``ESC[0m``), so this runs over every line before matching.
    """
    return _ANSI_RE.sub("", text)


def block_name_for(axes_id: str, *, taken: Optional[Iterable[str]] = None) -> str:
    """Return a legal, unique GLE block name for ``axes_id``.

    GLE block identifiers match ``[A-Za-z_][A-Za-z0-9_]*`` (verified: ``-`` and
    ``.`` are rejected, and a leading digit is rejected). A gleplot
    ``axes_id`` is uuid4 hex, which may start with a digit, so the
    :data:`BLOCK_NAME_PREFIX` is what makes the name legal in the first place.

    Any character outside the legal set is replaced by ``_``. That mapping is
    not injective, so ``taken`` may be supplied with the names already issued;
    a collision is resolved by appending ``_2``, ``_3``, ... The *record* id is
    always the original ``axes_id``, so this sanitization never affects how
    GLEstudio matches a calibration back to its axes.
    """
    base = BLOCK_NAME_PREFIX + re.sub(r"[^0-9A-Za-z_]", "_", axes_id)
    if not _LEGAL_NAME_RE.match(base):  # pragma: no cover - prefix guarantees it
        base = BLOCK_NAME_PREFIX
    used = set(taken or ())
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def _cal_print_line(axes_id: str, nonce: Optional[str] = None) -> str:
    """The 13-field ``glestudio-cal`` print statement for ``axes_id``.

    Field order is normative (SPEC 6.2): id, then the four ranges
    ``xgmin xgmax ygmin ygmax``, then ``x2gmin x2gmax y2gmin y2gmax``, then the
    four frame-corner cm values ``xg(xgmin) yg(ygmin) xg(xgmax) yg(ygmax)``.

    When ``nonce`` is given the marker itself becomes ``glestudio-cal:<nonce>``
    (see :func:`new_calibration_nonce`); ``None`` reproduces the unhardened
    marker exactly.
    """
    marker = _marker_token(CAL_MARKER, nonce)
    return (
        f'print "{marker} {axes_id} "'
        ' xgmin " " xgmax " " ygmin " " ygmax'
        ' " " x2gmin " " x2gmax " " y2gmin " " y2gmax'
        ' " " xg(xgmin) " " yg(ygmin) " " xg(xgmax) " " yg(ygmax)'
    )


def _box_print_line(axes_id: str, block: str, nonce: Optional[str] = None) -> str:
    """The ``glestudio-box`` print statement for ``axes_id``'s named block.

    See :func:`_cal_print_line` for the ``nonce`` marker form.
    """
    marker = _marker_token(BOX_MARKER, nonce)
    return (
        f'print "{marker} {axes_id} "'
        f" ptx({block}.bl)"
        f' " " pty({block}.bl)'
        f' " " width({block})'
        f' " " height({block})'
    )


def _document_of(source: Union[str, GleDocument]) -> Tuple[GleDocument, str]:
    """Normalize a ``str``/``GleDocument`` argument to ``(document, text)``."""
    if isinstance(source, GleDocument):
        return source, source.emit()
    doc = parse_gle_source(source)
    return doc, source


def _indent_of(line: Optional[SourceLine]) -> str:
    """Leading whitespace of ``line``, for cosmetically matching insertions."""
    if line is None:
        return ""
    stripped = line.text.lstrip()
    return line.text[: len(line.text) - len(stripped)]


def _splice(
    doc: GleDocument,
    text: str,
    before: Dict[int, List[str]],
    after: Dict[int, List[str]],
) -> str:
    """Rebuild ``text`` with extra lines spliced in around given line numbers.

    Reassembles from the parsed document's verbatim :class:`SourceLine`
    storage rather than from a ``split``/``join`` round trip, so every
    untouched line -- including its original terminator, which may differ from
    the file's dominant one -- comes back byte-for-byte. Injected lines use the
    anchor line's terminator, falling back to the file's dominant one.

    A file whose last line has no terminator gains one if something is
    inserted after it; this is a preview copy, never the saved project, so the
    trailing-newline difference is immaterial.
    """
    default_nl = "\r\n" if "\r\n" in text else "\n"
    pieces: List[str] = []
    for src in doc.lines:
        nl = src.ending or default_nl
        for extra in before.get(src.line_no, ()):
            pieces.append(extra + nl)
        trailing = after.get(src.line_no, ())
        if trailing and not src.ending:
            pieces.append(src.text + nl)
        else:
            pieces.append(src.raw)
        for extra in trailing:
            pieces.append(extra + nl)
    return "".join(pieces)


def instrument_script(
    source: Union[str, GleDocument],
    axes_ids: Sequence[str],
    *,
    nonce: Optional[str] = None,
) -> InstrumentedScript:
    """Produce the instrumented *preview copy* of a generated script.

    For each top-level graph block, in document order, this wraps the block in
    ``begin name <block> ... end name`` and appends the two SPEC 6.2 records
    immediately after the wrapper closes::

        begin name glestudio_ax<sanitized-id>
        begin graph
            ...
        end graph
        end name
        print "glestudio-cal <id> " xgmin " " ... " " yg(ygmax)
        print "glestudio-box <id> " ptx(...bl) " " ... " " height(...)

    Marker hardening against record spoofing
    -----------------------------------------
    GLEstudio's axes ids travel in ``project.json`` plaintext, so a script
    reached via import passthrough can contain a hand-written
    ``print "glestudio-cal <id> ..."`` that runs *before* the genuine record
    printed here (after the real graph block). Since
    :func:`parse_calibration_records` keeps the first record per id, that
    forged record would otherwise win and poison the data<->cm map that
    feeds canvas drags (GLEstudio Phase-6 review, minor 10).

    Pass ``nonce=`` (typically :func:`new_calibration_nonce`'s return value)
    to close this: every marker this call prints becomes
    ``glestudio-cal:<nonce>`` / ``glestudio-box:<nonce>`` instead of the bare
    marker, and :func:`parse_calibration_records` -- given the same value as
    ``expected_nonce`` -- accepts only records carrying it, reporting
    anything else (including an old-style unsuffixed record) as a
    ``"spoofed"`` warning rather than as a candidate record at all. ``nonce``
    defaults to ``None``, which reproduces the unhardened marker text
    byte-for-byte (the legacy, pre-hardening behaviour every existing caller
    still gets).

    Splice, not writer flag
    -----------------------
    Instrumentation is a post-generation transform over
    :func:`~gleplot.parser.syntax.parse_gle_source`, deliberately *not* a
    writer emission flag:

    * gleplot's byte-identical fixed point is an exit criterion, and a writer
      flag adds a branch through the emission core that the whole golden
      battery would then have to cover. A splice cannot change default output
      because there is no new writer code path at all.
    * The instrumenter must also work on scripts gleplot did not write --
      GLEstudio opens hand-authored ``.gle`` and still wants calibration for
      whatever graph blocks it finds. A writer flag only ever helps figures
      that were generated by the writer.
    * The preview pipeline is already a chain of post-generation script
      transforms (deresolve decimation, SVG-safe font substitution), so this
      matches the shape that is already there.
    * The wrapper straddles the ``amove`` / ``begin graph`` seam, which is
      emitted by two unrelated parts of the writer; splicing at the parsed
      block boundary needs no coordination between them.

    Parameters
    ----------
    source:
        The generated script, as text or an already-parsed document.
    axes_ids:
        Stable ``Axes.axes_id`` values in *graph block order* -- gleplot emits
        one graph block per axes in ``axes_list`` order, so this is
        ``[ax.axes_id for ax in figure.axes_list]``. Blocks beyond the end of
        this sequence are still wrapped and still print records, keyed by their
        positional index, and a warning is recorded: degrading is better than
        silently instrumenting nothing.
    nonce:
        See "Marker hardening" above. Must contain no whitespace or quote
        character if given (:class:`ValueError` otherwise) -- it is minted by
        this module's own code, so a malformed value is a programming error,
        not attacker input.

    Returns
    -------
    InstrumentedScript
        The rewritten text plus the block names used, any warnings, and the
        ``nonce`` it was given (see :attr:`InstrumentedScript.nonce`). When the
        script has no closable graph block the text is returned unchanged.

    Notes
    -----
    Nothing here validates that the script *compiles*. It need not: GLE aborts
    before executing any ``print`` when a script has an error anywhere, so an
    instrumented broken script simply produces no records (verified) -- the
    fail-closed property GLEstudio's last-good-calibration retention is built
    on (SPEC 6.2).

    Only *top-level* graph blocks are instrumented. A graph nested inside an
    opaque block -- in practice a ``begin translate``/``begin scale`` wrapper,
    which the parser keeps as raw lines -- is invisible here and produces no
    record at all. That is the desired outcome and not a coincidence: such a
    graph is exactly the one :func:`find_ctm_hazards` flags, and no record
    beats a wrong one.
    """
    _validate_nonce(nonce)
    doc, text = _document_of(source)
    graphs = doc.graphs

    warnings: List[CalibrationWarning] = []
    block_names: Dict[str, str] = {}
    before: Dict[int, List[str]] = {}
    after: Dict[int, List[str]] = {}
    line_by_no = {src.line_no: src for src in doc.lines}
    taken: List[str] = []

    for index, graph in enumerate(graphs):
        if graph.end is None:
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"graph block at line {graph.line_no} is never closed; "
                    "not instrumented",
                )
            )
            continue
        if index < len(axes_ids):
            axes_id = axes_ids[index]
        else:
            axes_id = str(index)
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"no axes id supplied for graph block {index} at line "
                    f"{graph.line_no}; keyed by positional index instead",
                    subject=axes_id,
                )
            )
        if _BAD_ID_RE.search(axes_id):
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"axes id {axes_id!r} contains whitespace or a quote and "
                    "cannot be written into a calibration record; graph block "
                    f"at line {graph.line_no} not instrumented",
                    subject=axes_id,
                )
            )
            continue
        if axes_id in block_names:
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"axes id {axes_id!r} supplied for more than one graph "
                    f"block; block at line {graph.line_no} not instrumented",
                    subject=axes_id,
                )
            )
            continue

        block = block_name_for(axes_id, taken=taken)
        taken.append(block)
        block_names[axes_id] = block

        indent = _indent_of(line_by_no.get(graph.begin.line_no))
        before.setdefault(graph.begin.line_no, []).append(f"{indent}begin name {block}")
        after.setdefault(graph.end.line_no, []).extend(
            [
                f"{indent}end name",
                _cal_print_line(axes_id, nonce),
                _box_print_line(axes_id, block, nonce),
            ]
        )

    if not before and not after:
        return InstrumentedScript(
            text=text, block_names={}, warnings=warnings, nonce=nonce
        )

    return InstrumentedScript(
        text=_splice(doc, text, before, after),
        block_names=block_names,
        warnings=warnings,
        nonce=nonce,
    )


# --------------------------------------------------------------------------- #
# Text metrics (SPEC 6.3)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TextMetricRequest:
    """One string to measure in a specific font state (SPEC 6.3).

    Attributes
    ----------
    measure_id:
        Caller-chosen identity, echoed in the record. Must contain no
        whitespace or quote character (it is the record's second token).
    text:
        The GLE markup to measure -- already post-mathtext, exactly the string
        the figure draws, so subscripts and font switches inside it are
        measured as drawn.
    font:
        GLE font name (``set font <font>``). ``None`` inherits whatever the
        script left in effect.
    hei:
        Text height in cm (``set hei <hei>``). ``None`` inherits. Metrics scale
        exactly linearly with this (verified: doubling ``hei`` doubles
        ``twidth``, ``theight`` and ``tdepth``).
    extra_state:
        Additional raw GLE statements emitted inside the measurement's
        ``gsave``/``grestore`` pair, for state this dataclass does not model
        (``set fontlwidth ...``, ``set just ...``, ...). Emitted verbatim.
    """

    measure_id: str
    text: str
    font: Optional[str] = None
    hei: Optional[float] = None
    extra_state: Tuple[str, ...] = ()


def _quote_gle_string(text: str) -> Optional[str]:
    """Quote ``text`` as a GLE string literal, or ``None`` if impossible.

    GLE accepts both ``"..."`` and ``'...'``. The manual's doubled-``""``
    escape is **broken in 4.3.10** -- it does not merely mis-measure, it aborts
    the whole script, which under the fail-closed rule would cost every other
    record in the compile too. So the delimiter is chosen to be one the text
    does not contain, and a string containing *both* quote characters is
    refused rather than risked.
    """
    if '"' not in text:
        return '"' + text + '"'
    if "'" not in text:
        return "'" + text + "'"
    return None


def _metric_block(
    requests: Sequence[TextMetricRequest],
    nonce: Optional[str] = None,
) -> Tuple[List[str], List[CalibrationWarning]]:
    """Render measurement statements for ``requests``.

    Each request is wrapped in its own ``gsave``/``grestore`` so one font
    change cannot leak into the next measurement or into anything that follows
    the block (verified: ``gsave``/``grestore`` do restore ``font`` and
    ``hei``). ``nonce`` hardens the emitted ``glestudio-tw`` marker the same
    way as :func:`instrument_script`'s ``nonce`` (see there); ``None``
    reproduces the unhardened marker.
    """
    lines: List[str] = []
    warnings: List[CalibrationWarning] = []
    seen: Set[str] = set()

    for req in requests:
        if _BAD_ID_RE.search(req.measure_id) or not req.measure_id:
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"measure id {req.measure_id!r} is empty or contains "
                    "whitespace/quotes; measurement skipped",
                    subject=req.measure_id,
                )
            )
            continue
        if req.measure_id in seen:
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"duplicate measure id {req.measure_id!r}; "
                    "later request skipped",
                    subject=req.measure_id,
                )
            )
            continue
        literal = _quote_gle_string(req.text)
        if literal is None:
            warnings.append(
                CalibrationWarning(
                    "injection",
                    f"text for measure {req.measure_id!r} contains both a "
                    "single and a double quote, which GLE 4.3.10 cannot "
                    "express in a string literal; measurement skipped",
                    subject=req.measure_id,
                )
            )
            continue
        seen.add(req.measure_id)

        lines.append("gsave")
        if req.font:
            lines.append(f"set font {req.font}")
        if req.hei is not None:
            lines.append(f"set hei {req.hei:g}")
        lines.extend(req.extra_state)
        marker = _marker_token(TW_MARKER, nonce)
        lines.append(
            f'print "{marker} {req.measure_id} "'
            f" twidth({literal})"
            f' " " theight({literal})'
            f' " " tdepth({literal})'
        )
        lines.append("grestore")

    return lines, warnings


def inject_text_metrics(
    source: Union[str, GleDocument],
    requests: Sequence[TextMetricRequest],
    *,
    nonce: Optional[str] = None,
) -> InstrumentedScript:
    """Append a text-measurement block to a script (SPEC 6.3).

    Appending to the figure's *own* script -- rather than measuring in a
    separate compile -- is what SPEC 6.3 means by "the figure's actual fonts
    and sizes": the measurement runs after the figure's own preamble, so any
    ``set font`` / ``set hei`` / TeX preamble the figure established is in
    force, and each request's explicit overrides are applied on top inside a
    ``gsave``/``grestore``. It also keeps the render cycle at **one** compile:
    calibration, box and metric records all arrive on the same stderr stream
    from the same process, and all three are consistently fail-closed together
    when the document has an error.

    :func:`build_text_metric_script` is the standalone counterpart, for
    measuring while the document is *not* compilable.

    Composes with :func:`instrument_script` in either order; the metric block
    is appended at end of file, after every graph block's records.

    ``nonce`` hardens the emitted ``glestudio-tw`` markers exactly as
    :func:`instrument_script`'s ``nonce`` does for its own markers (see there
    for why, and :func:`new_calibration_nonce` to mint one). Pass the *same*
    nonce here as was used for :func:`instrument_script` when composing the
    two, so :func:`parse_calibration_records` can validate every marker from
    the compile against one ``expected_nonce``. Defaults to ``None``, which
    reproduces the unhardened marker text byte-for-byte.
    """
    _validate_nonce(nonce)
    doc, text = _document_of(source)
    lines, warnings = _metric_block(requests, nonce)
    if not lines:
        return InstrumentedScript(
            text=text, block_names={}, warnings=warnings, nonce=nonce
        )

    default_nl = "\r\n" if "\r\n" in text else "\n"
    body = "".join(line + default_nl for line in lines)
    if text and not text.endswith(("\n", "\r")):
        text += default_nl
    return InstrumentedScript(
        text=text + body, block_names={}, warnings=warnings, nonce=nonce
    )


def build_text_metric_script(
    requests: Sequence[TextMetricRequest],
    *,
    page_size_cm: Tuple[float, float] = (2.0, 2.0),
    preamble: Sequence[str] = (),
    nonce: Optional[str] = None,
) -> InstrumentedScript:
    """Build a minimal standalone script that only measures text.

    Use this when the figure's own script cannot be compiled -- the case
    GLEstudio is in whenever the user is mid-mistake, where
    :func:`inject_text_metrics` would yield nothing because GLE aborts before
    any ``print``. The trade-off is that only the state in ``preamble`` plus
    each request's own overrides is in force, so callers that care about
    matching the figure must replay the figure's font preamble here.

    ``page_size_cm`` only has to be non-degenerate; the script draws nothing.

    ``nonce`` hardens the emitted ``glestudio-tw`` markers exactly as
    :func:`instrument_script`'s ``nonce`` does (see there, and
    :func:`new_calibration_nonce`). Defaults to ``None``, reproducing the
    unhardened marker text byte-for-byte.
    """
    _validate_nonce(nonce)
    lines, warnings = _metric_block(requests, nonce)
    head = [f"size {page_size_cm[0]:g} {page_size_cm[1]:g}"]
    head.extend(preamble)
    return InstrumentedScript(
        text="".join(line + "\n" for line in head + lines),
        block_names={},
        warnings=warnings,
        nonce=nonce,
    )


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def _find_record(line: str, marker: str) -> Optional[Tuple[Optional[str], List[str]]]:
    """Locate ``marker`` in ``line``; return its optional nonce and fields.

    The marker is located anywhere in the line rather than anchored at the
    start, so a record still parses when GLE (or a shell wrapper) prefixes it
    with something. Splitting on whitespace rather than fixed columns is
    required: GLE pads its numeric fields with a variable number of spaces.

    ``marker`` may be immediately followed by ``:<nonce>`` (see
    :func:`instrument_script`'s ``nonce`` parameter); when it is, the nonce is
    split out and returned separately rather than becoming -- or corrupting --
    the id field. Returns ``None`` if ``marker`` is not found in ``line`` at
    all; returns ``(None, fields)`` for an unhardened, marker-only record.
    """
    at = line.find(marker)
    if at < 0:
        return None
    rest = line[at + len(marker) :]
    nonce: Optional[str] = None
    if rest[:1] == ":":
        m = re.match(r":(\S*)", rest)
        assert m is not None  # ":" always matches "(\S*)", even as ""
        nonce = m.group(1)
        rest = rest[m.end() :]
    return nonce, rest.split()


def _floats(tokens: Sequence[str]) -> Optional[List[float]]:
    """Parse every token as a float, or ``None`` if any fails."""
    out: List[float] = []
    for tok in tokens:
        try:
            out.append(float(tok))
        except ValueError:
            return None
    return out


def parse_calibration_records(
    text: str,
    axes: Sequence[AxesSpec] = (),
    *,
    measure_ids: Sequence[str] = (),
    expected_nonce: Optional[str] = None,
) -> CalibrationResult:
    """Parse a GLE stderr/stdout stream into typed calibration records.

    Never raises. Every record it cannot use, every declared id it never saw,
    and every record whose id it does not recognize becomes a
    :class:`CalibrationWarning` in the result (SPEC 6.2: "calibration parse
    warnings are surfaced in the Output dock, not discarded").

    Parameters
    ----------
    text:
        Combined GLE output. Records are on **stderr** and ANSI-prefixed;
        both are handled. Interleaved GLE chatter (progress lines, the
        harmless ``dud pcode`` noise malformed markup provokes) is skipped.
    axes:
        The model's view of each axes: stable id plus the log flags and
        secondary-axis presence that GLE's numbers cannot tell you. Records
        are matched to these **by id**, not by position, which is what makes a
        calibration survive an axes reorder. An empty sequence parses records
        with linear/no-secondary assumptions and warns once.
    measure_ids:
        Declared :attr:`TextMetricRequest.measure_id` values, if any. Supplying
        them turns an unexpected or absent metric record into a warning; omit
        to accept whatever arrives.
    expected_nonce:
        The value passed as ``nonce=`` to whichever of
        :func:`instrument_script` / :func:`inject_text_metrics` /
        :func:`build_text_metric_script` produced the script this ``text``
        came from (see :func:`new_calibration_nonce`). When given, a
        ``glestudio-cal``/``glestudio-box``/``glestudio-tw`` record is
        accepted only if its marker carries exactly this nonce. Anything
        else -- no ``:<nonce>`` suffix at all, or a mismatched one -- is
        reported as a ``"spoofed"`` warning and dropped *before*
        id/duplicate/malformed handling ever sees it. This is what stops a
        marker string smuggled into the document as passthrough text (axes
        ids travel in ``project.json`` plaintext) from racing the genuine
        record -- printed after the real graph block -- for the
        first-parsed slot per id (GLEstudio Phase-6 review, minor 10).

        Defaults to ``None``: every record matching the bare marker is
        accepted regardless of any nonce suffix, reproducing the exact
        pre-hardening behaviour for callers that have not adopted nonces.

    Returns
    -------
    CalibrationResult
        Records keyed by id, plus warnings. An erroring compile yields an
        empty result (:attr:`CalibrationResult.is_empty`) rather than partial
        records, because GLE aborts before any ``print``.
    """
    result = CalibrationResult()
    spec_by_id = {spec.axes_id: spec for spec in axes}
    if axes and len(spec_by_id) != len(axes):
        result.warnings.append(
            CalibrationWarning(
                "invalid",
                "duplicate axes ids in the supplied specs; "
                "later specs shadow earlier ones",
            )
        )
    declared_measures = set(measure_ids)
    warned_no_specs = False

    for raw_line in strip_ansi(text).splitlines():
        for marker, handler in (
            (CAL_MARKER, _parse_cal),
            (BOX_MARKER, _parse_box),
            (TW_MARKER, _parse_tw),
        ):
            found = _find_record(raw_line, marker)
            if found is None:
                continue
            nonce, fields = found
            if expected_nonce is not None and nonce != expected_nonce:
                result.warnings.append(
                    CalibrationWarning(
                        "spoofed",
                        f"{marker} record ignored: nonce "
                        f"{'missing' if nonce is None else nonce!r} does not "
                        "match the expected per-invocation nonce (possible "
                        f"spoofed or replayed record): {raw_line.strip()!r}",
                        subject=fields[0] if fields else None,
                    )
                )
                break
            if marker == CAL_MARKER and not axes and not warned_no_specs:
                warned_no_specs = True
                result.warnings.append(
                    CalibrationWarning(
                        "unknown-id",
                        "calibration records present but no axes specs were "
                        "supplied; log flags and secondary axes assumed absent",
                    )
                )
            handler(fields, raw_line, spec_by_id, declared_measures, result)
            break

    for spec in axes:
        if spec.axes_id not in result.calibrations:
            result.warnings.append(
                CalibrationWarning(
                    "missing",
                    f"no {CAL_MARKER} record for axes {spec.axes_id!r}",
                    subject=spec.axes_id,
                )
            )
        if spec.axes_id not in result.boxes:
            result.warnings.append(
                CalibrationWarning(
                    "missing",
                    f"no {BOX_MARKER} record for axes {spec.axes_id!r}",
                    subject=spec.axes_id,
                )
            )
    for measure_id in measure_ids:
        if measure_id not in result.metrics:
            result.warnings.append(
                CalibrationWarning(
                    "missing",
                    f"no {TW_MARKER} record for measure {measure_id!r}",
                    subject=measure_id,
                )
            )

    return result


def _parse_cal(
    fields: List[str],
    raw_line: str,
    spec_by_id: Dict[str, AxesSpec],
    declared_measures: Set[str],
    result: CalibrationResult,
) -> None:
    """Handle one ``glestudio-cal`` line: 1 id + 12 numbers."""
    if len(fields) < 13:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"malformed {CAL_MARKER} record (expected 13 fields, got "
                f"{len(fields)}): {raw_line.strip()!r}",
            )
        )
        return
    axes_id = fields[0]
    values = _floats(fields[1:13])
    if values is None:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"unparseable numbers in {CAL_MARKER} record: " f"{raw_line.strip()!r}",
                subject=axes_id,
            )
        )
        return
    if axes_id in result.calibrations:
        result.warnings.append(
            CalibrationWarning(
                "duplicate",
                f"second {CAL_MARKER} record for axes {axes_id!r}; keeping the "
                "first",
                subject=axes_id,
            )
        )
        return

    spec = spec_by_id.get(axes_id)
    if spec is None:
        # When *no* specs were supplied at all, the caller has already been
        # told once that flags are being assumed; repeating it per record
        # would bury the warnings that matter.
        if spec_by_id:
            result.warnings.append(
                CalibrationWarning(
                    "unknown-id",
                    f"{CAL_MARKER} record for unknown axes id {axes_id!r}; "
                    "log flags and secondary axes assumed absent",
                    subject=axes_id,
                )
            )
        spec = AxesSpec(axes_id)

    cal = CalibrationV2(
        axes_id=axes_id,
        x_range=(values[0], values[1]),
        y_range=(values[2], values[3]),
        x2_range=(values[4], values[5]),
        y2_range=(values[6], values[7]),
        frame_corners_cm=(values[8], values[9], values[10], values[11]),
        x_log=spec.x_log,
        y_log=spec.y_log,
        x2_log=spec.x2_log,
        y2_log=spec.y2_log,
        has_x2=spec.has_x2,
        has_y2=spec.has_y2,
    )
    reason = cal.invalid_reason()
    if reason is not None:
        result.warnings.append(
            CalibrationWarning(
                "invalid",
                f"{CAL_MARKER} record for axes {axes_id!r} cannot produce a "
                f"usable map ({reason}); dropped",
                subject=axes_id,
            )
        )
        return
    result.calibrations[axes_id] = cal


def _parse_box(
    fields: List[str],
    raw_line: str,
    spec_by_id: Dict[str, AxesSpec],
    declared_measures: Set[str],
    result: CalibrationResult,
) -> None:
    """Handle one ``glestudio-box`` line: 1 id + 4 numbers."""
    if len(fields) < 5:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"malformed {BOX_MARKER} record (expected 5 fields, got "
                f"{len(fields)}): {raw_line.strip()!r}",
            )
        )
        return
    axes_id = fields[0]
    values = _floats(fields[1:5])
    if values is None:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"unparseable numbers in {BOX_MARKER} record: " f"{raw_line.strip()!r}",
                subject=axes_id,
            )
        )
        return
    if axes_id in result.boxes:
        result.warnings.append(
            CalibrationWarning(
                "duplicate",
                f"second {BOX_MARKER} record for axes {axes_id!r}; keeping the "
                "first",
                subject=axes_id,
            )
        )
        return
    if spec_by_id and axes_id not in spec_by_id:
        result.warnings.append(
            CalibrationWarning(
                "unknown-id",
                f"{BOX_MARKER} record for unknown axes id {axes_id!r}",
                subject=axes_id,
            )
        )
    if values[2] <= 0.0 or values[3] <= 0.0:
        result.warnings.append(
            CalibrationWarning(
                "invalid",
                f"{BOX_MARKER} record for axes {axes_id!r} has a non-positive "
                f"extent ({values[2]:g} x {values[3]:g}); dropped",
                subject=axes_id,
            )
        )
        return
    result.boxes[axes_id] = BoxRecord(
        axes_id=axes_id, x=values[0], y=values[1], width=values[2], height=values[3]
    )


def _parse_tw(
    fields: List[str],
    raw_line: str,
    spec_by_id: Dict[str, AxesSpec],
    declared_measures: Set[str],
    result: CalibrationResult,
) -> None:
    """Handle one ``glestudio-tw`` line: 1 id + 3 numbers."""
    if len(fields) < 4:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"malformed {TW_MARKER} record (expected 4 fields, got "
                f"{len(fields)}): {raw_line.strip()!r}",
            )
        )
        return
    measure_id = fields[0]
    values = _floats(fields[1:4])
    if values is None:
        result.warnings.append(
            CalibrationWarning(
                "malformed",
                f"unparseable numbers in {TW_MARKER} record: " f"{raw_line.strip()!r}",
                subject=measure_id,
            )
        )
        return
    if measure_id in result.metrics:
        result.warnings.append(
            CalibrationWarning(
                "duplicate",
                f"second {TW_MARKER} record for measure {measure_id!r}; "
                "keeping the first",
                subject=measure_id,
            )
        )
        return
    if declared_measures and measure_id not in declared_measures:
        result.warnings.append(
            CalibrationWarning(
                "unknown-id",
                f"{TW_MARKER} record for undeclared measure {measure_id!r}",
                subject=measure_id,
            )
        )
    result.metrics[measure_id] = TextMetric(
        measure_id=measure_id, width=values[0], height=values[1], depth=values[2]
    )


# --------------------------------------------------------------------------- #
# CTM guard (SPEC 6.2, last bullet)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CtmHazard:
    """A statement that changes the current transformation matrix.

    Any of these makes calibration silently wrong (verified -- see the module
    docstring), so GLEstudio demotes the affected axes to non-interactive
    rather than emitting geometry it cannot trust.

    Attributes
    ----------
    line_no:
        1-based line in the scanned source. For a hazard found inside an
        opaque block the number is absolute in the original text.
    statement:
        The offending source text, stripped.
    keyword:
        Lower-cased CTM operation (``"translate"``, ``"scale"``, ...).
    kind:
        ``"statement"`` for a bare ``translate 1 1``, ``"block"`` for a
        ``begin translate ... end translate``.
    encloses_graph:
        ``True`` when a ``begin graph`` was found inside a hazardous block --
        i.e. the hazard demonstrably affects an axes rather than merely
        existing somewhere in the file. A bare CTM *statement* has unbounded
        effect (it persists until an enclosing ``grestore`` or end of file), so
        it is always reported with ``encloses_graph=False`` and must be treated
        as affecting every axes that follows it.
    """

    line_no: int
    statement: str
    keyword: str
    kind: str = "statement"
    encloses_graph: bool = False


def _statement_text(stmt: Statement) -> str:
    """Best-effort source text of a statement, for reporting."""
    return stmt.raw.strip() if stmt.raw else ""


def _contains_graph(lines: Sequence[SourceLine]) -> bool:
    """True if any of ``lines`` opens a graph block.

    Opaque blocks keep their bodies as raw lines rather than parsed nodes, so
    the only way to tell whether a ``begin translate`` wraps a graph is to look
    at its text. The check is deliberately crude and biased toward reporting:
    a false positive costs an axes its interactivity, a false negative costs
    correctness.
    """
    for src in lines:
        stripped = src.text.strip().lower()
        if stripped.startswith("begin ") and stripped.split()[1:2] == ["graph"]:
            return True
    return False


def _scan_nodes(nodes: Sequence[Node], offset: int, depth: int) -> List[CtmHazard]:
    """Collect CTM hazards from ``nodes``, skipping graph-block interiors."""
    hazards: List[CtmHazard] = []
    for node in nodes:
        if isinstance(node, GraphBlock):
            # Graph-internal geometry is fine: a graph block's own ``scale 1 1``
            # sizes the axis frame within the graph box and is not a page CTM
            # operation (SPEC 3.3). Never descend.
            continue
        if isinstance(node, BlankOrComment):
            continue
        if isinstance(node, Statement):
            keyword = node.keyword
            if keyword in _CTM_STATEMENTS:
                hazards.append(
                    CtmHazard(
                        line_no=node.line_no + offset,
                        statement=_statement_text(node),
                        keyword=keyword,
                        kind="statement",
                    )
                )
            continue
        if isinstance(node, OpaqueBlock):
            block_type = node.block_type.lower()
            if block_type in _CTM_BLOCKS:
                hazards.append(
                    CtmHazard(
                        line_no=node.line_no + offset,
                        statement=_statement_text(node.begin),
                        keyword=block_type,
                        kind="block",
                        encloses_graph=_contains_graph(node.inner_lines),
                    )
                )
                # The whole block is already flagged; anything nested inside it
                # is subsumed.
                continue
            if block_type in _NON_CODE_BLOCKS or depth >= _MAX_SCAN_DEPTH:
                continue
            if not node.inner_lines:
                continue
            # ``sub``/``if``/``object``/... bodies are real GLE code the parser
            # keeps as raw lines. Re-parse them so a ``translate`` hiding in a
            # subroutine is not missed. Line numbers restart at 1 in the
            # re-parse, so the block's own line number is added back.
            inner_text = "".join(src.raw for src in node.inner_lines)
            inner_offset = offset + node.inner_lines[0].line_no - 1
            hazards.extend(
                _scan_nodes(parse_gle_source(inner_text).nodes, inner_offset, depth + 1)
            )
    return hazards


def find_ctm_hazards(source: Union[str, GleDocument]) -> List[CtmHazard]:
    """Find statements that would silently corrupt calibration (SPEC 6.2).

    GLE's ``xg()``/``yg()`` report positions in the *current user coordinate
    system*, and a named block's ``ptx()``/``pty()`` report device coordinates
    re-mapped through whatever CTM is in force when they are read. A page-level
    ``scale``/``translate``/``rotate`` -- which GLEstudio can carry through
    import as passthrough -- therefore makes both numbers wrong, and wrong in
    *different* directions, with no error and no visible symptom. Measured
    under ``begin translate 3 1``, a frame really at page x=5 reported
    ``xg(xgmin) == 2``, and ``ptx()`` reported 1.54 inside the block and 4.54
    outside it.

    What is flagged:

    * bare ``translate`` / ``tran`` / ``scale`` / ``rotate`` / ``rot``
      statements outside any graph block;
    * ``begin translate`` / ``tran`` / ``scale`` / ``rotate`` / ``rot`` /
      ``origin`` / ``shear`` blocks, with :attr:`CtmHazard.encloses_graph` set
      when a graph block is inside.

    What is not flagged: anything inside a ``begin graph`` block. A graph's own
    ``scale 1 1`` is the graph box's frame fraction, a different primitive from
    the page transform (SPEC 3.3), and never a hazard.

    The scan runs on the real parser, not a regex over raw text, so a ``scale``
    appearing inside a string, a comment or a graph sub-command is not
    mistaken for a page transform. It *does* descend into code-bearing opaque
    blocks (``sub``, ``if``, ``object``, ...), which the parser stores as raw
    lines, because a subroutine that translates is exactly as hazardous;
    prose-bearing blocks (``begin text`` and friends) are left alone.

    Returns
    -------
    list of CtmHazard
        In document order. Empty for every script gleplot's own writer
        produces -- the writer emits no CTM operations at all.
    """
    doc, _text = _document_of(source)
    hazards = _scan_nodes(doc.nodes, 0, 0)
    hazards.sort(key=lambda h: h.line_no)
    return hazards

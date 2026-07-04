"""Single-source unit-conversion functions for gleplot <-> GLE round-tripping.

Every physical-unit conversion used by :mod:`gleplot.writer`, :mod:`gleplot.axes`,
and :mod:`gleplot.figure` when emitting GLE lives here, exactly once, so that a
future ``.gle`` parser can invert each one with the matching ``*_to_*``
function instead of re-deriving (and potentially drifting from) the constant.

Provenance
----------
Each constant below is transcribed verbatim from the call site it replaces, as
of the pre-refactor state of this branch (``feature/pyside-gui-editor``). The
refactor that follows this module's creation intentionally does **not**
"correct" or unify inconsistent constants (e.g. ``0.03528`` vs ``0.0353``)
-- see :func:`linewidth_pt_to_cm` and :func:`capsize_pt_to_cm` docstrings.

- ``figsize`` (inches) <-> ``size`` (cm): factor 2.54, from
  ``src/gleplot/writer.py:34-35`` (``GLEWriter.__init__``):
  ``self.width_cm = figsize[0] * 2.54``.
- line width (points) -> GLE ``lwidth`` (cm): factor ``0.03528``, from
  ``src/gleplot/writer.py:332,334,590,592,715,717``
  (``GLEWriter.add_plot_line``, ``add_errorbar``, ``add_plot_line_from_file``).
- font size (points) -> GLE ``set hei`` (cm): divisor ``28.35``, from
  ``src/gleplot/writer.py:71`` (``GLEWriter.add_preamble``) and
  ``src/gleplot/writer.py:779`` (``GLEWriter.add_text``).
- matplotlib ``markersize``/``s`` -> GLE ``msize``: factor
  ``0.025 * msize_scale``, from ``src/gleplot/axes.py:231`` (``Axes.plot``),
  ``src/gleplot/axes.py:350`` (``Axes.errorbar``), and
  ``src/gleplot/axes.py:468`` (``Axes.errorbar_from_file``).
- matplotlib ``capsize`` (points) -> GLE ``errwidth``/``herrwidth`` (cm):
  factor ``0.0353``, from ``src/gleplot/axes.py:363`` (``Axes.errorbar``) and
  ``src/gleplot/axes.py:469`` (``Axes.errorbar_from_file``).

Note the line-width factor (``0.03528``) and the capsize factor (``0.0353``)
are numerically different roundings of the same physical constant
(1 pt = 1/72 in = 2.54/72 cm = 0.0352777... cm) used at different call sites
in the pre-refactor code. Both are preserved verbatim as separate functions
(``linewidth_pt_to_cm`` / ``capsize_pt_to_cm``) rather than unified, per the
"zero behavior change" requirement -- unifying them would change already
-committed golden GLE output for existing round-trip tests.
"""

from __future__ import annotations

__all__ = [
    "INCH_TO_CM",
    "LINEWIDTH_PT_TO_CM_FACTOR",
    "FONTSIZE_PT_TO_CM_DIVISOR",
    "MARKERSIZE_TO_MSIZE_FACTOR",
    "CAPSIZE_PT_TO_CM_FACTOR",
    "inches_to_cm",
    "cm_to_inches",
    "linewidth_pt_to_cm",
    "linewidth_cm_to_pt",
    "fontsize_pt_to_cm",
    "fontsize_cm_to_pt",
    "markersize_to_msize",
    "msize_to_markersize",
    "capsize_pt_to_cm",
    "capsize_cm_to_pt",
]

# 1 inch = 2.54 cm (exact, by definition).
INCH_TO_CM = 2.54

# points -> cm for line widths, as used by GLEWriter.add_plot_line et al.
# 1 point = 1/72 inch = 2.54/72 cm = 0.035277... cm, rounded here to 0.03528.
LINEWIDTH_PT_TO_CM_FACTOR = 0.03528

# points -> cm divisor for font/text height (``set hei``), as used by
# GLEWriter.add_preamble and GLEWriter.add_text. 28.35 points/cm is the
# conventional PostScript approximation (72 pt/in / 2.54 cm/in = 28.346...).
FONTSIZE_PT_TO_CM_DIVISOR = 28.35

# matplotlib markersize/scatter-size -> GLE msize factor (before msize_scale),
# as used by Axes.plot, Axes.errorbar, Axes.errorbar_from_file.
MARKERSIZE_TO_MSIZE_FACTOR = 0.025

# matplotlib capsize (points) -> GLE errwidth/herrwidth (cm), as used by
# Axes.errorbar and Axes.errorbar_from_file. Distinct rounding of 1/72*2.54
# from LINEWIDTH_PT_TO_CM_FACTOR -- see module docstring; preserved verbatim.
CAPSIZE_PT_TO_CM_FACTOR = 0.0353


def _snap(value: float) -> float:
    """Snap a float to 12 significant digits.

    Applied to every inverse-direction conversion (cm -> pt, msize ->
    markersize, cm -> inches on request): the forward/backward float op
    pairs are not bit-exact for every input (deltas ~1e-14 to 1e-16),
    and round-trip identity checks in the parser compare model values
    exactly. 12 significant digits is far beyond any UI-entered
    precision while safely absorbing the noise.
    """
    return float(f"{value:.12g}")


def inches_to_cm(inches: float) -> float:
    """Convert inches to centimeters (figure ``figsize`` -> GLE ``size``)."""
    return inches * INCH_TO_CM


def cm_to_inches(cm: float) -> float:
    """Convert centimeters to inches (GLE ``size`` -> figure ``figsize``).

    Inverse of :func:`inches_to_cm`, snapped to 12 significant digits
    for uniformity with the other inverse-direction conversions (the
    2.54 pair happens to be bit-exact for common values, but the snap
    makes the guarantee unconditional).
    """
    return _snap(cm / INCH_TO_CM)


def linewidth_pt_to_cm(points: float) -> float:
    """Convert a matplotlib line width in points to GLE ``lwidth`` cm.

    Uses :data:`LINEWIDTH_PT_TO_CM_FACTOR` (``0.03528``), matching
    ``GLEWriter.add_plot_line``/``add_errorbar``/``add_plot_line_from_file``.
    """
    return points * LINEWIDTH_PT_TO_CM_FACTOR


def linewidth_cm_to_pt(cm: float) -> float:
    """Convert a GLE ``lwidth`` value in cm back to points.

    Inverse of :func:`linewidth_pt_to_cm`, snapped to 12 significant
    digits (see the module note on inverse-direction snapping).
    """
    return _snap(cm / LINEWIDTH_PT_TO_CM_FACTOR)


def fontsize_pt_to_cm(points: float) -> float:
    """Convert a font size in points to a GLE ``set hei`` value in cm.

    Uses :data:`FONTSIZE_PT_TO_CM_DIVISOR` (``28.35``), matching
    ``GLEWriter.add_preamble``/``add_text``.
    """
    return points / FONTSIZE_PT_TO_CM_DIVISOR


def fontsize_cm_to_pt(cm: float) -> float:
    """Convert a GLE ``set hei`` value in cm back to points.

    Inverse of :func:`fontsize_pt_to_cm`, snapped to 12 significant
    digits: the divide/multiply pair is not bit-exact for every value
    (e.g. 1.5pt round-trips to 1.5000000000000002 unsnapped).
    """
    return _snap(cm * FONTSIZE_PT_TO_CM_DIVISOR)


def markersize_to_msize(markersize: float, msize_scale: float = 1.0) -> float:
    """Convert a matplotlib marker size to a GLE ``msize`` value.

    Formula: ``msize = markersize * 0.025 * msize_scale``, matching
    ``Axes.plot``/``Axes.errorbar``/``Axes.errorbar_from_file``.

    Parameters
    ----------
    markersize : float
        Matplotlib-convention marker size (e.g. 6 by default).
    msize_scale : float
        Figure/marker-config scale factor (``GLEMarkerConfig.msize_scale``),
        explicit here rather than implicit global state.
    """
    return markersize * MARKERSIZE_TO_MSIZE_FACTOR * msize_scale


def msize_to_markersize(msize: float, msize_scale: float = 1.0) -> float:
    """Convert a GLE ``msize`` value back to a matplotlib marker size.

    Inverse of :func:`markersize_to_msize` for the same ``msize_scale``,
    snapped to 12 significant digits: the multiply/divide pair is not
    bit-exact for every scale factor (e.g. msize_scale=1.5 leaves ~1e-14
    of float noise) and round-trip identity checks compare exactly.
    """
    return _snap(msize / (MARKERSIZE_TO_MSIZE_FACTOR * msize_scale))


def capsize_pt_to_cm(points: float) -> float:
    """Convert a matplotlib error-bar cap size in points to GLE cm.

    Uses :data:`CAPSIZE_PT_TO_CM_FACTOR` (``0.0353``), matching
    ``Axes.errorbar``/``Axes.errorbar_from_file``. This is a *different*
    rounding of 1 pt in cm than :func:`linewidth_pt_to_cm` uses -- both are
    preserved verbatim from their respective call sites (see module
    docstring); do not consolidate them.
    """
    return points * CAPSIZE_PT_TO_CM_FACTOR


def capsize_cm_to_pt(cm: float) -> float:
    """Convert a GLE error-bar cap width in cm back to matplotlib points.

    Inverse of :func:`capsize_pt_to_cm`, snapped to 12 significant
    digits (see :func:`_snap`).
    """
    return _snap(cm / CAPSIZE_PT_TO_CM_FACTOR)

"""Broken (split) x- and y-axis support.

A "broken axis" is one logical panel whose x-axis is cut into two or more
adjacent linear segments covering very different ranges -- e.g. a muon
asymmetry spectrum showing 0-0.02 us of fast relaxation on a narrow left
segment and 0.02-3 us of slow relaxation on a wide right one, sharing a
single y-axis. It is the layout of PRL 134, 046702 Fig. 2(a). A broken
*y*-axis is the same assembly turned on its side: segments stacked bottom to
top, sharing one x-axis (``axis='y'``, from ``Figure.add_broken_yaxes``).

Implementation
--------------
GLE has no split-axis primitive, so the assembly is built from ordinary graph
blocks: one ``begin graph``/``end graph`` per segment, positioned adjacently
with ``amove`` + ``size`` + ``scale 1 1`` (which makes the data area exactly
fill the requested box, so the boxes butt together with no internal padding).
The sides that face each other are switched off with GLE's per-side ``off``
sub-command, so what remains is a single continuous frame:

- leftmost segment: full y-axis (line, ticks, labels, title), ``y2axis off``;
- middle segments: ``yaxis off`` and ``y2axis off``;
- rightmost segment: ``yaxis off``, y2axis kept (the panel's right edge).

A broken y-axis does the same with ``xaxis`` (the bottom segment's) and
``x2axis`` (the top segment's).

The seam itself is then drawn explicitly -- nothing, a single rule, or the
conventional double-slash break marks -- anchored to the left segment's
``xg(xgmax)``/``yg(ygmin)``/``yg(ygmax)`` so it lands exactly where GLE drew
the box. A broken y-axis anchors its seam to the lower segment's ``yg(ygmax)``
and ``xg(xgmin)``/``xg(xgmax)``.

Series are declared **once** on the :class:`BrokenAxes` and fanned out to
every segment, sharing one generated ``.dat`` sidecar. GLE clips each dataset
to its own graph's axis range, so a point only appears in the segment whose
range contains it -- which is also what makes ``axvline``/``axvspan`` land in
the right segment automatically.

Limitations
-----------
- The ``.gle`` parser does not reconstruct a ``BrokenAxes``: reading a
  generated file back yields the segments as independent subplots, with the
  seam decoration and shared titles preserved as passthrough content. Nothing
  is dropped, but the broken-axis structure is not recovered.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, cast

import numpy as np

from ._warn import warn_external
from .axes import Axes

#: Accepted ``divider`` styles.
DIVIDER_STYLES = ("none", "line", "slash")

#: Series lists on an :class:`~gleplot.axes.Axes` that a fanned-out call can
#: append to. Used to diff before/after so the sidecar name allocated by the
#: first segment can be reused by the rest.
_FANOUT_SERIES_LISTS = (
    "lines",
    "scatters",
    "bars",
    "hists",
    "fills",
    "errorbars",
    "file_series",
    "texts",
    "reflines",
    "spans",
)

#: Series lists whose sidecar contents are NOT the same in every segment, so
#: their files must stay separate. A guide's concrete end points are derived
#: from the axes limits at write time, and each segment has its own x range --
#: an ``axhline`` spanning "the whole axis" is a different pair of points in
#: each segment. Sharing one file would let the last segment written
#: overwrite the others (which showed up as a guide that only drew in one
#: segment).
_SEGMENT_SPECIFIC_LISTS = frozenset({"reflines", "spans"})


class BrokenAxes:
    """One logical panel whose x-axis (or y-axis) is split into segments.

    Created by :meth:`gleplot.Figure.add_broken_xaxes` or
    :meth:`gleplot.Figure.add_broken_yaxes`, not directly.

    The object accepts the usual :class:`~gleplot.axes.Axes` plotting calls
    once and fans them out to every segment, so a series is never plotted
    twice by hand. Individual segments remain reachable (``bax[0]``,
    ``bax.segments``) for per-segment tick control.

    Parameters
    ----------
    figure : Figure
        Parent figure.
    xlims : sequence of (float, float), optional
        One ``(xmin, xmax)`` per segment, left to right, for a broken
        x-axis. At least two are required -- an axis with one segment is not
        broken. Give this or ``ylims``.
    width_ratios : sequence of float, optional
        Relative width of each segment of a broken x-axis. Default: all
        equal. The segments of a broken axis are usually *not* equal width
        (that is the point), so this is normally given, e.g. ``[1, 3]``.
    position : tuple, optional
        ``(rows, cols, index)`` cell of the figure's subplot grid that the
        whole assembly occupies. Default ``(1, 1, 1)``.
    gap : float, optional
        Physical gap between segments in cm. Defaults to 0 for
        ``divider='none'``/``'line'`` (segments touch) and 0.15 cm for
        ``divider='slash'`` (the break marks need somewhere to sit).
    divider : {'none', 'line', 'slash'}
        How the seam is marked: nothing at all, a single rule along it, or
        the conventional pair of double-slash break marks on the two frame
        lines that cross it.
    divider_color : str
        Colour of the seam decoration.
    divider_linewidth : float, optional
        Seam line width in points. Default: the style config's line width.
    divider_lstyle : int, optional
        GLE ``lstyle`` for a ``'line'`` divider (e.g. 3 for dashed).
    break_mark_size : float
        Half-extent (cm) of each stroke of a ``'slash'`` break mark across
        the frame line. The other extent and the separation between the pair
        scale with it.
    trim_seam_labels : bool
        When a segment starts exactly where the previous one ends, drop the
        second segment's first tick label so the shared value is not printed
        twice on top of itself. Default: True.
    xlabel_dist : float, optional
        Broken x-axis only. Distance in cm from the frame to the shared x
        title. The default is matched to GLE's own ``xtitle`` placement for
        the figure's font size.
    title_dist : float, optional
        Distance in cm from the frame to the shared title. The default is
        matched to GLE's own ``title`` placement for the figure's font size.
    ylims : sequence of (float, float), optional
        One ``(ymin, ymax)`` per segment, bottom to top, for a broken
        y-axis. Keyword-only.
    height_ratios : sequence of float, optional
        Broken y-axis only: relative height of each segment. Default: all
        equal. Keyword-only.
    ylabel_dist : float, optional
        Broken y-axis only: distance in cm from the frame to the shared y
        title. Default: 2.5 times the figure's font height, which clears
        tick labels up to about four characters wide. Keyword-only.

    Raises
    ------
    ValueError
        If both or neither of ``xlims`` and ``ylims`` are given, a keyword
        for the other orientation is given, or a range or ratio is invalid.
    """

    def __init__(
        self,
        figure,
        xlims: Optional[Sequence[Tuple[float, float]]] = None,
        width_ratios: Optional[Sequence[float]] = None,
        position: Tuple[int, int, int] = (1, 1, 1),
        gap: Optional[float] = None,
        divider: str = "line",
        divider_color: str = "black",
        divider_linewidth: Optional[float] = None,
        divider_lstyle: Optional[int] = None,
        break_mark_size: float = 0.2,
        trim_seam_labels: bool = True,
        xlabel_dist: Optional[float] = None,
        title_dist: Optional[float] = None,
        *,
        ylims: Optional[Sequence[Tuple[float, float]]] = None,
        height_ratios: Optional[Sequence[float]] = None,
        ylabel_dist: Optional[float] = None,
    ):
        if (xlims is None) == (ylims is None):
            raise ValueError(
                "BrokenAxes needs exactly one of xlims and ylims; got "
                f"xlims={xlims!r}, ylims={ylims!r}"
            )
        axis = "x" if xlims is not None else "y"
        other = {
            "x": (("height_ratios", height_ratios), ("ylabel_dist", ylabel_dist)),
            "y": (("width_ratios", width_ratios), ("xlabel_dist", xlabel_dist)),
        }[axis]
        for name, value in other:
            if value is not None:
                raise ValueError(
                    f"{name} does not apply to a broken {axis}-axis; got "
                    f"{value!r}. Leave it out."
                )
        given = xlims if axis == "x" else ylims
        lims = [
            cast(Tuple[float, float], tuple(float(v) for v in pair))
            for pair in cast(Sequence[Tuple[float, float]], given)
        ]
        if len(lims) < 2:
            raise ValueError(
                f"a broken {axis}-axis needs at least 2 segments; got "
                f"{len(lims)}. Use add_subplot() for an unbroken axis."
            )
        for lo, hi in lims:
            if not lo < hi:
                raise ValueError(
                    f"each {axis}lims entry must have {axis}min < {axis}max; "
                    f"got ({lo}, {hi})"
                )
        if axis == "y":
            # Stacked bottom to top: a segment that does not start at or
            # above the one below it would draw the axis out of order.
            for (_lo0, hi0), (lo1, hi1) in zip(lims, lims[1:]):
                if lo1 < hi0:
                    raise ValueError(
                        "ylims run bottom to top and must not overlap; got "
                        f"({lo1}, {hi1}) above a segment ending at {hi0}"
                    )

        ratios_name = "width_ratios" if axis == "x" else "height_ratios"
        ratios = width_ratios if axis == "x" else height_ratios
        if ratios is None:
            ratios = [1.0] * len(lims)
        ratios = [float(w) for w in ratios]
        if len(ratios) != len(lims):
            raise ValueError(
                f"{ratios_name} has {len(ratios)} entries but there are "
                f"{len(lims)} segments"
            )
        if any(w <= 0 for w in ratios):
            raise ValueError(f"{ratios_name} must all be > 0; got {ratios}")

        if divider not in DIVIDER_STYLES:
            raise ValueError(
                f"divider must be one of {DIVIDER_STYLES!r}, got {divider!r}"
            )

        self.figure = figure
        #: ``'x'`` or ``'y'``: which axis is broken.
        self.axis = axis
        self.xlims: Optional[List[Tuple[float, float]]] = None
        self.width_ratios: Optional[List[float]] = None
        self.ylims: Optional[List[Tuple[float, float]]] = None
        self.height_ratios: Optional[List[float]] = None
        if axis == "x":
            self.xlims, self.width_ratios = lims, ratios
        else:
            self.ylims, self.height_ratios = lims, ratios
        self.position = tuple(position)
        self.gap = (
            float(gap) if gap is not None else (0.15 if divider == "slash" else 0.0)
        )
        self.divider = divider
        if isinstance(divider_color, np.ndarray):
            # An array breaks the JSON of to_dict().
            divider_color = (
                tuple(divider_color.ravel().tolist())
                if divider_color.ndim
                else divider_color.item()
            )
        self.divider_color = divider_color
        self.divider_linewidth = divider_linewidth
        self.divider_lstyle = divider_lstyle
        self.break_mark_size = float(break_mark_size)
        self.trim_seam_labels = bool(trim_seam_labels)
        self.xlabel_dist = xlabel_dist
        self.title_dist = title_dist
        self.ylabel_dist = ylabel_dist

        #: Shared titles, drawn centred on the whole assembly rather than on
        #: any one segment (GLE's own titles centre on their graph box). A
        #: broken x-axis shares its x title and title; a broken y-axis its
        #: y title and title (its x title is the bottom segment's own).
        self.xlabel_text = ""
        self.title_text = ""
        self.ylabel_text = ""

        self.segments: List[Axes] = []
        for index, (lo, hi) in enumerate(lims):
            seg = Axes(figure, self.position)
            if axis == "x":
                seg.set_xlim(lo, hi)
            else:
                seg.set_ylim(lo, hi)
            seg._break_owner = self
            seg._break_index = index
            # A fanned-out series carries its label in every segment, so the
            # auto-legend rule ("show one iff any series is labelled") would
            # draw the same key N times. Start suppressed; legend() turns
            # exactly one segment back on.
            seg.legend_on = False
            self.segments.append(seg)

        self._apply_segment_frame_flags()

    @property
    def _lims(self) -> List[Tuple[float, float]]:
        """The per-segment ranges along the broken axis."""
        return cast(
            List[Tuple[float, float]], self.xlims if self.axis == "x" else self.ylims
        )

    @property
    def _ratios(self) -> List[float]:
        """The relative segment sizes along the broken axis."""
        return cast(
            List[float],
            self.width_ratios if self.axis == "x" else self.height_ratios,
        )

    # -- geometry -------------------------------------------------------

    def segment_extent(self, index: int, cell_length_cm: float) -> Tuple[float, float]:
        """Where segment ``index`` sits inside the grid cell it shares.

        Returns ``(offset_cm, length_cm)`` along the broken axis: from the
        cell's left edge for a broken x-axis, from its bottom edge for a
        broken y-axis. The gaps are taken out of the cell first, then the
        remainder is divided in proportion to the ratios -- so the ratios
        describe the *plotted* sizes, not the sizes including the gaps.
        """
        n = len(self.segments)
        usable = cell_length_cm - self.gap * (n - 1)
        if usable <= 0:
            raise ValueError(
                f"the {self.gap} cm gaps between {n} broken-axis segments do "
                f"not fit in the {cell_length_cm:.3g} cm cell available; "
                "reduce gap or enlarge the figure"
            )
        ratios = self._ratios
        total = sum(ratios)
        sizes = [usable * w / total for w in ratios]
        offset = sum(sizes[:index]) + self.gap * index
        return offset, sizes[index]

    # -- frame / label bookkeeping --------------------------------------

    def _apply_segment_frame_flags(self) -> None:
        """Switch off the sides that face each other, and de-duplicate labels.

        Single source of truth for the "reads as one panel" rules. Called once
        at construction; per-segment overrides made afterwards (e.g. turning a
        y-axis back on for a diagnostic render) are the caller's to keep.
        """
        last = len(self.segments) - 1
        lims = self._lims
        for index, seg in enumerate(self.segments):
            first = index == 0
            trim = self.trim_seam_labels and index > 0
            contiguous = trim and lims[index][0] == lims[index - 1][1]
            if self.axis == "x":
                # Only the leftmost segment carries the y axis line, ticks,
                # labels and title; the inner sides vanish so the assembly
                # reads as one frame with a single y axis on its left edge.
                seg._show_ylabel = first
                seg._show_yticks = first
                seg._yaxis_off = not first
                seg._y2axis_off = index != last
                # The x title is drawn once, centred on the whole assembly.
                seg._show_xlabel = False
                seg.xlabel_text = ""
                seg.title_text = ""
                # Contiguous segments would print the shared boundary value
                # twice, once at the left segment's max and again at the
                # right's min.
                if trim:
                    seg._remove_first_xtick = contiguous
            else:
                # Only the bottom segment carries the x axis; only the top one
                # keeps the top frame edge.
                seg._show_xlabel = first
                seg._show_xticks = first
                seg._xaxis_off = not first
                seg._x2axis_off = index != last
                # The y title and the title are drawn once, centred on the
                # whole assembly: GLE draws a graph's title with its x axis,
                # which the upper segments switch off.
                seg._show_ylabel = False
                seg.ylabel_text = ""
                seg.title_text = ""
                if trim:
                    seg._remove_first_ytick = contiguous

    def _reassert_frame_flags(self, seg: Axes, apply_shared) -> None:
        """Apply the figure's sharex/sharey flags, then this assembly's rules.

        ``apply_shared`` is ``Figure._apply_shared_axes_flags``. The grid
        flags describe the cells around the assembly; where they disagree
        with its internal geometry, the geometry stands.
        """
        if self.axis == "x":
            show_ylabel, show_yticks = seg._show_ylabel, seg._show_yticks
            remove_first_xtick = seg._remove_first_xtick
            apply_shared(seg)
            seg._show_ylabel, seg._show_yticks = show_ylabel, show_yticks
            seg._show_xlabel = False
            seg._remove_first_xtick = remove_first_xtick
        else:
            show_xlabel, show_xticks = seg._show_xlabel, seg._show_xticks
            remove_first_ytick = seg._remove_first_ytick
            apply_shared(seg)
            seg._show_xlabel, seg._show_xticks = show_xlabel, show_xticks
            # Each segment has a y range no other cell shares, so sharey
            # does not hide its tick labels.
            seg._show_yticks = True
            seg._show_ylabel = False
            seg._remove_first_ytick = remove_first_ytick

    # -- container protocol ---------------------------------------------

    def __len__(self) -> int:
        return len(self.segments)

    def __getitem__(self, index) -> Axes:
        return self.segments[index]

    def __iter__(self):
        return iter(self.segments)

    # -- fan-out --------------------------------------------------------

    def _fanout(self, method_name: str, *args, **kwargs):
        """Call ``method_name`` on every segment and share one data sidecar.

        Each segment allocates its own sidecar name, which would write N
        byte-identical ``.dat`` files for one logical series. Instead the
        entries created on segments 1..N-1 are repointed at the name the first
        segment reserved, so exactly one file is written and every graph block
        references it. Lists in :data:`_SEGMENT_SPECIFIC_LISTS` are exempt --
        their contents genuinely differ per segment.

        Returns the first segment's return value, so the call still behaves
        like the underlying Axes method (``axvline`` returns its declaration
        dict, ``plot`` returns an axes).

        Side note on the generated names: the segments that get repointed have
        already burned a name from the figure's counter, so a broken-axis
        figure's sidecars are numbered with gaps (``bx_0``, ``bx_2``, ...).
        That is cosmetic -- every name in use is still unique and stable
        across saves.
        """
        results = []
        created = []
        for seg in self.segments:
            before = {name: len(getattr(seg, name)) for name in _FANOUT_SERIES_LISTS}
            results.append(getattr(seg, method_name)(*args, **kwargs))
            new = []
            for name in _FANOUT_SERIES_LISTS:
                if name in _SEGMENT_SPECIFIC_LISTS:
                    continue
                new.extend(getattr(seg, name)[before[name] :])
            created.append(new)

        reference = created[0]
        for entries in created[1:]:
            for target, source in zip(entries, reference):
                if "data_file" in target and "data_file" in source:
                    target["data_file"] = source["data_file"]
        return results[0]

    def plot(self, *args, **kwargs):
        """Plot a line/marker series across every segment."""
        self._fanout("plot", *args, **kwargs)
        return self

    def step(self, *args, **kwargs):
        """Step plot across every segment."""
        self._fanout("step", *args, **kwargs)
        return self

    def hist(self, *args, **kwargs):
        """Histogram across every segment. See :meth:`gleplot.Axes.hist`."""
        self._fanout("hist", *args, **kwargs)
        return self

    def stem(self, *args, **kwargs):
        """Stem plot across every segment."""
        self._fanout("stem", *args, **kwargs)
        return self

    def scatter(self, *args, **kwargs):
        """Scatter a series across every segment."""
        self._fanout("scatter", *args, **kwargs)
        return self

    def errorbar(self, *args, **kwargs):
        """Plot an error-bar series across every segment."""
        self._fanout("errorbar", *args, **kwargs)
        return self

    def bar(self, *args, **kwargs):
        """Draw a bar series across every segment."""
        self._fanout("bar", *args, **kwargs)
        return self

    def barh(self, *args, **kwargs):
        """Draw horizontal bars across every segment."""
        self._fanout("barh", *args, **kwargs)
        return self

    def fill_between(self, *args, **kwargs):
        """Fill between two curves across every segment."""
        self._fanout("fill_between", *args, **kwargs)
        return self

    def fill_betweenx(self, *args, **kwargs):
        """Fill between two x curves across every segment."""
        self._fanout("fill_betweenx", *args, **kwargs)
        return self

    def stackplot(self, *args, **kwargs):
        """Stacked bands across every segment.

        Returns the first segment's bands, as :meth:`gleplot.Axes.stackplot`.
        """
        return self._fanout("stackplot", *args, **kwargs)

    def fill(self, *args, **kwargs):
        """Fill one polygon in every segment."""
        self._fanout("fill", *args, **kwargs)
        return self

    def line_from_file(self, *args, **kwargs):
        """Reference an external file's columns as a line, in every segment."""
        self._fanout("line_from_file", *args, **kwargs)
        return self

    def errorbar_from_file(self, *args, **kwargs):
        """Reference an external file's columns as an errorbar series."""
        self._fanout("errorbar_from_file", *args, **kwargs)
        return self

    def axvline(self, *args, **kwargs):
        """Vertical guide.

        On a broken x-axis GLE clips it to the segment whose range contains
        it; on a broken y-axis it spans every segment.
        """
        return self._fanout("axvline", *args, **kwargs)

    def axhline(self, y: float = 0.0, *args, **kwargs):
        """Horizontal guide.

        On a broken x-axis it spans every segment. On a broken y-axis it goes
        to the segment whose range contains ``y``; a guide in the break warns
        and is not drawn (``None`` is returned).
        """
        if self.axis == "x":
            return self._fanout("axhline", y, *args, **kwargs)
        index = self._segment_for(float(y))
        if index is None:
            warn_external(
                f"axhline() at y={y!r} falls in the break between segments "
                f"{self.ylims!r} and was not drawn.",
            )
            return None
        return self.segments[index].axhline(y, *args, **kwargs)

    def hlines(self, *args, **kwargs):
        """Horizontal segments, in every segment they reach."""
        self._fanout("hlines", *args, **kwargs)
        return self

    def vlines(self, *args, **kwargs):
        """Vertical segments, in the segment whose range holds each one."""
        self._fanout("vlines", *args, **kwargs)
        return self

    def axvspan(self, *args, **kwargs):
        """Vertical band, clipped to whichever segment(s) it overlaps."""
        return self._fanout("axvspan", *args, **kwargs)

    def axhspan(self, ymin: float, ymax: float, *args, **kwargs):
        """Horizontal band.

        On a broken x-axis it spans every segment. On a broken y-axis it is
        drawn in each segment it overlaps, cut to that segment's range;
        a band entirely in a break warns and is not drawn. Returns the first
        segment's declaration, or ``None``.
        """
        if self.axis == "x":
            return self._fanout("axhspan", ymin, ymax, *args, **kwargs)
        lo, hi = sorted((float(ymin), float(ymax)))
        first = None
        for seg, (seg_lo, seg_hi) in zip(self.segments, self._lims):
            if hi <= seg_lo or lo >= seg_hi:
                continue
            entry = seg.axhspan(max(lo, seg_lo), min(hi, seg_hi), *args, **kwargs)
            first = entry if first is None else first
        if first is None:
            warn_external(
                f"axhspan({ymin!r}, {ymax!r}) falls in the break between "
                f"segments {self.ylims!r} and was not drawn.",
            )
        return first

    def text(self, x: float, y: float, s: str, **kwargs):
        """Place text at data coordinates in the segment that contains it.

        The segment is the one whose range contains ``x`` on a broken x-axis,
        ``y`` on a broken y-axis. Text is written at an absolute page
        position derived from its own graph's coordinate mapping, so it
        cannot be fanned out: a segment whose range excludes it would draw
        the label outside its box. If no segment contains it the call warns
        and does nothing.

        With ``transform=seg.transAxes`` for one of the segments, ``x`` and
        ``y`` are fractions of that segment's frame and the text goes there.
        """
        transform = kwargs.get("transform")
        for seg in self.segments:
            if transform == seg.transAxes:
                seg.text(x, y, s, **kwargs)
                return self
        coord = x if self.axis == "x" else y
        index = self._segment_for(coord)
        if index is None:
            warn_external(
                f"text() at {self.axis}={coord!r} falls in the break between "
                f"segments {self._lims!r} and was not drawn.",
            )
            return self
        self.segments[index].text(x, y, s, **kwargs)
        return self

    def annotate(self, text: str, xy: Sequence[float], *args, **kwargs):
        """Annotate in the segment that contains the text, as :meth:`text`.

        ``xytext`` (or ``xy`` when it is omitted) picks the segment. An arrow
        whose ``xy`` is in another segment cannot be drawn there (each
        segment maps only its own range), so it warns and is dropped.
        Returns the stored annotation, or ``None`` if nothing was drawn.
        """
        k = 0 if self.axis == "x" else 1
        xytext = args[0] if args else kwargs.get("xytext")
        anchor = float((xy if xytext is None else xytext)[k])
        index = self._segment_for(anchor)
        if index is None:
            warn_external(
                f"annotate() at {self.axis}={anchor!r} falls in the break "
                f"between segments {self._lims!r} and was not drawn.",
            )
            return None
        if self._segment_for(float(xy[k])) != index:
            arrowprops = kwargs.pop("arrowprops", None)
            if len(args) >= 4:
                # positional (xytext, xycoords, textcoords, arrowprops, ...)
                arrowprops = args[3] if arrowprops is None else arrowprops
                args = args[:3] + (None,) + args[4:]
            if arrowprops is not None:
                warn_external(
                    f"annotate() arrow to {self.axis}={xy[k]!r} crosses into "
                    "another segment and was not drawn.",
                )
        return self.segments[index].annotate(text, xy, *args, **kwargs)

    def _segment_for(self, value: float) -> Optional[int]:
        """Index of the segment whose range contains ``value``, or ``None``.

        Boundaries belong to the first (left or lower) segment, so a value
        shared by two contiguous segments is not ambiguous.
        """
        for index, (lo, hi) in enumerate(self._lims):
            if lo <= value <= hi:
                return index
        return None

    def segment_for_x(self, x: float) -> Optional[int]:
        """Index of the segment whose x range contains ``x``, or ``None``.

        Boundaries belong to the *left* segment, so a value shared by two
        contiguous segments is not ambiguous. On a broken y-axis every
        segment shares the x range, so this is 0 or ``None``.
        """
        if self.axis == "y":
            lo, hi = self.segments[0].get_xlim()
            if lo is None or hi is None or min(lo, hi) <= x <= max(lo, hi):
                return 0
            return None
        return self._segment_for(x)

    # -- shared axis state ----------------------------------------------

    def set_xlabel(self, label: str):
        """Set the x title.

        A broken x-axis draws it centred under the whole assembly; a broken
        y-axis gives it to the bottom segment.
        """
        if self.axis == "y":
            self.segments[0].set_xlabel(label)
            return self
        self.xlabel_text = self.segments[0]._text(label)
        return self

    def set_title(self, label: str):
        """Set the title, drawn centred above the whole assembly."""
        self.title_text = self.segments[0]._text(label)
        return self

    def set_ylabel(self, label: str, axis: str = "y"):
        """Set the shared y title.

        A broken x-axis draws it on the leftmost segment. A broken y-axis
        draws it centred beside the whole assembly, ``ylabel_dist`` from the
        frame, and has no ``y2`` title.
        """
        if self.axis == "x":
            self.segments[0].set_ylabel(label, axis=axis)
            return self
        if axis != "y":
            raise ValueError(
                f"a broken y-axis has one y title; axis must be 'y', got {axis!r}"
            )
        self.ylabel_text = self.segments[0]._text(label)
        return self

    def set_ylim(self, ymin: float, ymax: float, axis: str = "y"):
        """Set the y limits on every segment of a broken x-axis.

        A broken y-axis has one range per segment, so this raises
        ``TypeError`` there.
        """
        if self.axis == "y":
            self._primary_y_only("set_ylim", axis)
            raise TypeError(
                "a broken y-axis has one range per segment; set them with the "
                "ylims argument of add_broken_yaxes(), or on an individual "
                "segment via bax[i].set_ylim()"
            )
        for seg in self.segments:
            seg.set_ylim(ymin, ymax, axis=axis)
        return self

    def get_ylim(self, axis: str = "y"):
        """The shared y limits, or the per-segment ranges of a broken y-axis."""
        if self.axis == "y":
            self._primary_y_only("get_ylim", axis)
            return list(cast(List[Tuple[float, float]], self.ylims))
        return self.segments[0].get_ylim(axis=axis)

    def get_xlim(self):
        """The per-segment x ranges, or the shared x limits of a broken y-axis."""
        if self.axis == "y":
            return self.segments[0].get_xlim()
        return list(cast(List[Tuple[float, float]], self.xlims))

    def set_yscale(self, scale, axis: str = "y", segment: Optional[int] = None):
        """Set the y scale.

        On a broken x-axis it applies to every segment. On a broken y-axis
        ``scale`` may be one value for every segment or one per segment, and
        ``segment`` targets exactly one.
        """
        if self.axis == "x":
            self._shared_only("set_yscale", segment)
            for seg in self.segments:
                seg.set_yscale(scale, axis=axis)
            return self
        for seg, value in self._per_segment(scale, segment):
            seg.set_yscale(value, axis=axis)
        return self

    def set_xscale(self, scale, segment: Optional[int] = None):
        """Set the x scale.

        On a broken x-axis ``scale`` may be one value for every segment or
        one per segment, and ``segment`` targets exactly one. On a broken
        y-axis it applies to every segment.
        """
        if self.axis == "y":
            self._shared_only("set_xscale", segment)
            for seg in self.segments:
                seg.set_xscale(scale)
            return self
        for seg, value in self._per_segment(scale, segment):
            seg.set_xscale(value)
        return self

    def set_xticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks=None,
        dsubticks=None,
        segment: Optional[int] = None,
    ):
        """Set the x ticks.

        On a broken x-axis this is the tick interval, per segment or for all
        of them: ``dticks``/``dsubticks`` may each be a single number applied
        to every segment, or a sequence with one entry per segment (``None``
        in a slot leaves that segment alone). Explicit tick *positions* are
        per-segment by nature -- use ``bax[i].set_xticks(ticks, labels)``.

        On a broken y-axis the x ticks are shared, and are set on every
        segment as :meth:`set_yticks` sets a broken x-axis' y ticks.
        """
        if self.axis == "y":
            self._shared_only("set_xticks", segment)
            for seg in self.segments:
                seg.set_xticks(ticks, labels, dticks=dticks, dsubticks=dsubticks)
            return self
        if ticks is not None or labels is not None:
            raise TypeError(
                "explicit x tick positions on a broken x-axis are per segment; "
                "use bax[i].set_xticks(ticks, labels)"
            )
        self._set_tick_intervals("x", dticks, dsubticks, segment)
        return self

    def set_yticks(
        self,
        ticks=None,
        labels=None,
        *,
        dticks=None,
        dsubticks=None,
        segment: Optional[int] = None,
    ):
        """Set the y ticks.

        On a broken x-axis the y ticks are shared: the tick *positions* are
        set on every segment so the horizontal grid lines and sub-tick marks
        stay consistent, even though only the leftmost one prints labels.

        On a broken y-axis this is the tick interval per segment, as
        :meth:`set_xticks` is on a broken x-axis.
        """
        if self.axis == "x":
            self._shared_only("set_yticks", segment)
            for seg in self.segments:
                seg.set_yticks(ticks, labels, dticks=dticks, dsubticks=dsubticks)
            return self
        if ticks is not None or labels is not None:
            raise TypeError(
                "explicit y tick positions on a broken y-axis are per segment; "
                "use bax[i].set_yticks(ticks, labels)"
            )
        self._set_tick_intervals("y", dticks, dsubticks, segment)
        return self

    def _primary_y_only(self, method: str, axis: str) -> None:
        """Refuse a ``y2`` request on a broken y-axis, which has one per segment."""
        if axis != "y":
            raise ValueError(
                f"{method}() on a broken y-axis takes axis='y'; got {axis!r}. "
                f"Use bax[i].{method}(..., axis={axis!r}) for one segment."
            )

    def _shared_only(self, method: str, segment: Optional[int]) -> None:
        """Refuse ``segment=`` on a setting every segment shares."""
        if segment is not None:
            shared = "y" if self.axis == "x" else "x"
            raise ValueError(
                f"{method}() sets the {shared} axis every segment of a broken "
                f"{self.axis}-axis shares, so it takes no segment; got "
                f"segment={segment!r}. Use bax[{segment}].{method}() for one "
                "segment."
            )

    def _set_tick_intervals(self, name, dticks, dsubticks, segment) -> None:
        """``dticks``/``dsubticks`` on the broken axis, per segment or for all."""
        if dticks is not None:
            for seg, value in self._per_segment(dticks, segment):
                if value is not None:
                    setattr(seg, f"{name}dticks", float(value))
        if dsubticks is not None:
            for seg, value in self._per_segment(dsubticks, segment):
                if value is not None:
                    setattr(seg, f"{name}dsubticks", float(value))

    def _per_segment(self, value, segment: Optional[int]):
        """Yield ``(axes, value)`` pairs for a scalar-or-per-segment argument."""
        if segment is not None:
            yield self.segments[segment], value
            return
        if isinstance(value, (list, tuple)):
            if len(value) != len(self.segments):
                raise ValueError(
                    f"expected 1 value or {len(self.segments)} (one per "
                    f"segment); got {len(value)}"
                )
            for seg, item in zip(self.segments, value):
                yield seg, item
            return
        for seg in self.segments:
            yield seg, value

    def legend(self, loc: str = "best", segment: Optional[int] = None, **kwargs):
        """Show a legend in one segment.

        A fanned-out series carries its label in *every* segment, so GLE would
        otherwise draw the same key in each of them. Every segment therefore
        starts with its legend explicitly suppressed and this method turns
        exactly one back on. ``segment`` defaults to the largest one (the
        widest, or on a broken y-axis the tallest), which has the most room
        for a key.
        """
        if segment is None:
            ratios = self._ratios
            segment = max(range(len(ratios)), key=lambda i: ratios[i])
        if self.axis == "y":
            # axhline / axhspan go only to the segments they reach, so a
            # labelled one elsewhere is not in this segment's key.
            missing = [
                entry["label"]
                for index, seg in enumerate(self.segments)
                if index != segment
                for entry in (*seg.reflines, *seg.spans)
                if entry.get("label")
                and not any(
                    other.get("label") == entry["label"]
                    for other in (
                        *self.segments[segment].reflines,
                        *self.segments[segment].spans,
                    )
                )
            ]
            if missing:
                warn_external(
                    f"legend() lists segment {segment}'s entries; the guide "
                    f"label(s) {sorted(set(missing))!r} are in another segment "
                    "of the broken y-axis and are not listed. Pass segment= "
                    "for the segment that holds them."
                )
        for index, seg in enumerate(self.segments):
            if index == segment:
                seg.legend(loc, **kwargs)
            else:
                seg.legend_on = False
        return self

    def set_xlim(self, *args, **kwargs):
        """Set the shared x limits of a broken y-axis.

        A broken x-axis has one range per segment, so this raises
        ``TypeError`` there.
        """
        if self.axis == "y":
            for seg in self.segments:
                seg.set_xlim(*args, **kwargs)
            return self
        raise TypeError(
            "a broken x-axis has one range per segment; set them with the "
            "xlims argument of add_broken_xaxes(), or on an individual "
            "segment via bax[i].set_xlim()"
        )

    def has_plots(self) -> bool:
        """True if any segment carries content."""
        return any(seg.has_plots() for seg in self.segments)

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict.

        Segments are identified by their index in ``figure.axes_list`` rather
        than embedded, because they are already serialized there in full. A
        broken x-axis has no ``axis`` key, so its dict is the one it has
        always been.
        """
        axes_list = self.figure.axes_list if self.figure is not None else []
        common = {
            "position": list(self.position),
            "gap": self.gap,
            "divider": self.divider,
            "divider_color": self.divider_color,
            "divider_linewidth": self.divider_linewidth,
            "divider_lstyle": self.divider_lstyle,
            "break_mark_size": self.break_mark_size,
            "trim_seam_labels": self.trim_seam_labels,
        }
        segments = [axes_list.index(seg) for seg in self.segments]
        if self.axis == "y":
            return {
                "axis": "y",
                "segments": segments,
                "ylims": [list(pair) for pair in self._lims],
                "height_ratios": list(self._ratios),
                **common,
                "ylabel_dist": self.ylabel_dist,
                "title_dist": self.title_dist,
                "ylabel_text": self.ylabel_text,
                "title_text": self.title_text,
            }
        return {
            "segments": segments,
            "xlims": [list(pair) for pair in self._lims],
            "width_ratios": list(self._ratios),
            **common,
            "xlabel_dist": self.xlabel_dist,
            "title_dist": self.title_dist,
            "xlabel_text": self.xlabel_text,
            "title_text": self.title_text,
        }

    @classmethod
    def from_dict(cls, figure, d: dict) -> "BrokenAxes":
        """Rebuild from :meth:`to_dict`, rebinding to already-restored axes.

        The segments must already be present in ``figure.axes_list`` (they are
        restored by ``Figure.from_dict`` before this runs). Their frame flags
        and limits came back with them, so nothing here re-derives them --
        that would silently discard any per-segment customization the user
        made after construction.
        """
        obj = cls.__new__(cls)
        obj.figure = figure
        obj.axis = d.get("axis", "x")
        obj.xlims = obj.width_ratios = obj.ylims = obj.height_ratios = None
        if obj.axis == "y":
            obj.ylims = [tuple(pair) for pair in d.get("ylims", [])]
            obj.height_ratios = list(d.get("height_ratios", []))
        else:
            obj.xlims = [tuple(pair) for pair in d.get("xlims", [])]
            obj.width_ratios = list(d.get("width_ratios", []))
        obj.position = tuple(d.get("position", (1, 1, 1)))
        obj.gap = float(d.get("gap", 0.0))
        obj.divider = d.get("divider", "line")
        obj.divider_color = d.get("divider_color", "black")
        obj.divider_linewidth = d.get("divider_linewidth")
        obj.divider_lstyle = d.get("divider_lstyle")
        obj.break_mark_size = float(d.get("break_mark_size", 0.2))
        obj.trim_seam_labels = bool(d.get("trim_seam_labels", True))
        obj.xlabel_dist = d.get("xlabel_dist")
        obj.title_dist = d.get("title_dist")
        obj.ylabel_dist = d.get("ylabel_dist")
        obj.xlabel_text = d.get("xlabel_text", "")
        obj.title_text = d.get("title_text", "")
        obj.ylabel_text = d.get("ylabel_text", "")

        obj.segments = [figure.axes_list[i] for i in d.get("segments", [])]
        for seg in obj.segments:
            seg._break_owner = obj
        return obj

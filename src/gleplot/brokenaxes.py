"""Broken (split) x-axis support.

A "broken axis" is one logical panel whose x-axis is cut into two or more
adjacent linear segments covering very different ranges -- e.g. a muon
asymmetry spectrum showing 0-0.02 us of fast relaxation on a narrow left
segment and 0.02-3 us of slow relaxation on a wide right one, sharing a
single y-axis. It is the layout of PRL 134, 046702 Fig. 2(a).

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

The seam itself is then drawn explicitly -- nothing, a single rule, or the
conventional double-slash break marks -- anchored to the left segment's
``xg(xgmax)``/``yg(ygmin)``/``yg(ygmax)`` so it lands exactly where GLE drew
the box.

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
- The y-axis is always shared across segments; there is no broken *y*-axis.
"""

from __future__ import annotations

import warnings
from typing import List, Optional, Sequence, Tuple

from .axes import Axes
from .mathtext import mathtext_to_gle

#: Accepted ``divider`` styles.
DIVIDER_STYLES = ("none", "line", "slash")

#: Series lists on an :class:`~gleplot.axes.Axes` that a fanned-out call can
#: append to. Used to diff before/after so the sidecar name allocated by the
#: first segment can be reused by the rest.
_FANOUT_SERIES_LISTS = (
    "lines",
    "scatters",
    "bars",
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
    """One logical panel whose x-axis is split into adjacent segments.

    Created by :meth:`gleplot.Figure.add_broken_xaxes`, not directly.

    The object accepts the usual :class:`~gleplot.axes.Axes` plotting calls
    once and fans them out to every segment, so a series is never plotted
    twice by hand. Individual segments remain reachable (``bax[0]``,
    ``bax.segments``) for per-segment tick control.

    Parameters
    ----------
    figure : Figure
        Parent figure.
    xlims : sequence of (float, float)
        One ``(xmin, xmax)`` per segment, left to right. At least two are
        required -- an axis with one segment is not broken.
    width_ratios : sequence of float, optional
        Relative width of each segment. Default: all equal. The segments of a
        broken axis are usually *not* equal width (that is the point), so this
        is normally given, e.g. ``[1, 3]``.
    position : tuple, optional
        ``(rows, cols, index)`` cell of the figure's subplot grid that the
        whole assembly occupies. Default ``(1, 1, 1)``.
    gap : float, optional
        Physical gap between segments in cm. Defaults to 0 for
        ``divider='none'``/``'line'`` (segments touch) and 0.15 cm for
        ``divider='slash'`` (the break marks need somewhere to sit).
    divider : {'none', 'line', 'slash'}
        How the seam is marked: nothing at all, a single vertical rule, or the
        conventional pair of double-slash break marks on the top and bottom
        frame lines.
    divider_color : str
        Colour of the seam decoration.
    divider_linewidth : float, optional
        Seam line width in points. Default: the style config's line width.
    divider_lstyle : int, optional
        GLE ``lstyle`` for a ``'line'`` divider (e.g. 3 for dashed).
    break_mark_size : float
        Height (half-extent, cm) of each stroke of a ``'slash'`` break mark.
        The stroke width and the separation between the pair scale with it.
    trim_seam_labels : bool
        When a segment starts exactly where the previous one ends, drop the
        second segment's first tick label so the shared value is not printed
        twice on top of itself. Default: True.
    xlabel_dist, title_dist : float, optional
        Distance in cm from the frame to the shared x title / title. Defaults
        are matched to GLE's own ``xtitle``/``title`` placement for the
        figure's font size.
    """

    def __init__(
        self,
        figure,
        xlims: Sequence[Tuple[float, float]],
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
    ):
        xlims = [tuple(float(v) for v in pair) for pair in xlims]
        if len(xlims) < 2:
            raise ValueError(
                "a broken x-axis needs at least 2 segments; got "
                f"{len(xlims)}. Use add_subplot() for an unbroken axis."
            )
        for lo, hi in xlims:
            if not lo < hi:
                raise ValueError(
                    f"each xlims entry must have xmin < xmax; got ({lo}, {hi})"
                )

        if width_ratios is None:
            width_ratios = [1.0] * len(xlims)
        width_ratios = [float(w) for w in width_ratios]
        if len(width_ratios) != len(xlims):
            raise ValueError(
                f"width_ratios has {len(width_ratios)} entries but there are "
                f"{len(xlims)} segments"
            )
        if any(w <= 0 for w in width_ratios):
            raise ValueError(f"width_ratios must all be > 0; got {width_ratios}")

        if divider not in DIVIDER_STYLES:
            raise ValueError(
                f"divider must be one of {DIVIDER_STYLES!r}, got {divider!r}"
            )

        self.figure = figure
        self.xlims = xlims
        self.width_ratios = width_ratios
        self.position = tuple(position)
        self.gap = float(gap) if gap is not None else (0.15 if divider == "slash" else 0.0)
        self.divider = divider
        self.divider_color = divider_color
        self.divider_linewidth = divider_linewidth
        self.divider_lstyle = divider_lstyle
        self.break_mark_size = float(break_mark_size)
        self.trim_seam_labels = bool(trim_seam_labels)
        self.xlabel_dist = xlabel_dist
        self.title_dist = title_dist

        #: Shared x title / title, drawn centred on the whole assembly rather
        #: than on any one segment (GLE's own xtitle centres on its graph box).
        self.xlabel_text = ""
        self.title_text = ""

        self.segments: List[Axes] = []
        for index, (xmin, xmax) in enumerate(xlims):
            seg = Axes(figure, self.position)
            seg.set_xlim(xmin, xmax)
            seg._break_owner = self
            seg._break_index = index
            # A fanned-out series carries its label in every segment, so the
            # auto-legend rule ("show one iff any series is labelled") would
            # draw the same key N times. Start suppressed; legend() turns
            # exactly one segment back on.
            seg.legend_on = False
            self.segments.append(seg)

        self._apply_segment_frame_flags()

    # -- geometry -------------------------------------------------------

    def segment_extent(self, index: int, cell_width_cm: float) -> Tuple[float, float]:
        """Where segment ``index`` sits inside the grid cell it shares.

        Returns ``(x_offset_cm, width_cm)`` measured from the cell's left
        edge. The gaps are taken out of the cell first, then the remainder is
        divided in proportion to ``width_ratios`` -- so the ratios describe
        the *plotted* widths, not the widths including the gaps.
        """
        n = len(self.segments)
        usable = cell_width_cm - self.gap * (n - 1)
        if usable <= 0:
            raise ValueError(
                f"the {self.gap} cm gaps between {n} broken-axis segments do "
                f"not fit in the {cell_width_cm:.3g} cm cell available; "
                "reduce gap or enlarge the figure"
            )
        total = sum(self.width_ratios)
        widths = [usable * w / total for w in self.width_ratios]
        offset = sum(widths[:index]) + self.gap * index
        return offset, widths[index]

    # -- frame / label bookkeeping --------------------------------------

    def _apply_segment_frame_flags(self) -> None:
        """Switch off the sides that face each other, and de-duplicate labels.

        Single source of truth for the "reads as one panel" rules. Called once
        at construction; per-segment overrides made afterwards (e.g. turning a
        y-axis back on for a diagnostic render) are the caller's to keep.
        """
        last = len(self.segments) - 1
        for index, seg in enumerate(self.segments):
            first = index == 0
            # Only the leftmost segment carries the y axis line, ticks, labels
            # and title; the inner sides vanish so the assembly reads as one
            # frame with a single y axis on its left edge.
            seg._show_ylabel = first
            seg._show_yticks = first
            seg._yaxis_off = not first
            seg._y2axis_off = index != last
            # The x title is drawn once, centred on the whole assembly.
            seg._show_xlabel = False
            seg.xlabel_text = ""
            seg.title_text = ""
            # Contiguous segments would print the shared boundary value twice,
            # once at the left segment's max and again at the right's min.
            if self.trim_seam_labels and index > 0:
                seg._remove_first_xtick = self.xlims[index][0] == self.xlims[index - 1][1]

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

    def fill_between(self, *args, **kwargs):
        """Fill between two curves across every segment."""
        self._fanout("fill_between", *args, **kwargs)
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
        """Vertical guide. GLE clips it to the segment whose range contains it."""
        return self._fanout("axvline", *args, **kwargs)

    def axhline(self, *args, **kwargs):
        """Horizontal guide, spanning every segment."""
        return self._fanout("axhline", *args, **kwargs)

    def axvspan(self, *args, **kwargs):
        """Vertical band, clipped to whichever segment(s) it overlaps."""
        return self._fanout("axvspan", *args, **kwargs)

    def axhspan(self, *args, **kwargs):
        """Horizontal band, spanning every segment."""
        return self._fanout("axhspan", *args, **kwargs)

    def text(self, x: float, y: float, s: str, **kwargs):
        """Place text at data coordinates in the segment that contains ``x``.

        Text is written at an absolute page position derived from its own
        graph's coordinate mapping, so it cannot be fanned out: a segment
        whose range excludes ``x`` would draw the label outside its box. If no
        segment contains ``x`` the call warns and does nothing.
        """
        index = self.segment_for_x(x)
        if index is None:
            warnings.warn(
                f"text() at x={x!r} falls in the break between segments "
                f"{self.xlims!r} and was not drawn.",
                UserWarning,
                stacklevel=2,
            )
            return self
        self.segments[index].text(x, y, s, **kwargs)
        return self

    def segment_for_x(self, x: float) -> Optional[int]:
        """Index of the segment whose range contains ``x``, or ``None``.

        Boundaries belong to the *left* segment, so a value shared by two
        contiguous segments is not ambiguous.
        """
        for index, (lo, hi) in enumerate(self.xlims):
            if lo <= x <= hi:
                return index
        return None

    # -- shared axis state ----------------------------------------------

    def set_xlabel(self, label: str):
        """Set the x title, drawn centred under the whole assembly."""
        self.xlabel_text = mathtext_to_gle(label)
        return self

    def set_title(self, label: str):
        """Set the title, drawn centred above the whole assembly."""
        self.title_text = mathtext_to_gle(label)
        return self

    def set_ylabel(self, label: str, axis: str = "y"):
        """Set the shared y title (drawn on the leftmost segment only)."""
        self.segments[0].set_ylabel(label, axis=axis)
        return self

    def set_ylim(self, ymin: float, ymax: float, axis: str = "y"):
        """Set the y limits on every segment (they always share one y-axis)."""
        for seg in self.segments:
            seg.set_ylim(ymin, ymax, axis=axis)
        return self

    def get_ylim(self, axis: str = "y"):
        """Get the shared y limits."""
        return self.segments[0].get_ylim(axis=axis)

    def get_xlim(self):
        """The per-segment x ranges, left to right."""
        return list(self.xlims)

    def set_yscale(self, scale: str, axis: str = "y"):
        """Set the y scale on every segment."""
        for seg in self.segments:
            seg.set_yscale(scale, axis=axis)
        return self

    def set_xscale(self, scale, segment: Optional[int] = None):
        """Set the x scale, per segment or for all of them.

        ``scale`` may be a single value applied to every segment, or one value
        per segment. Pass ``segment`` to target exactly one.
        """
        for seg, value in self._per_segment(scale, segment):
            seg.set_xscale(value)
        return self

    def set_xticks(
        self,
        *,
        dticks=None,
        dsubticks=None,
        segment: Optional[int] = None,
    ):
        """Set the x tick interval, per segment or for all of them.

        ``dticks``/``dsubticks`` may each be a single number applied to every
        segment, or a sequence with one entry per segment (``None`` in a slot
        leaves that segment alone). Explicit tick *positions* are per-segment
        by nature -- use ``bax[i].set_xticks(ticks, labels)`` for those.
        """
        if dticks is not None:
            for seg, value in self._per_segment(dticks, segment):
                if value is not None:
                    seg.xdticks = float(value)
        if dsubticks is not None:
            for seg, value in self._per_segment(dsubticks, segment):
                if value is not None:
                    seg.xdsubticks = float(value)
        return self

    def set_yticks(self, ticks=None, labels=None, *, dticks=None, dsubticks=None):
        """Set the shared y ticks (they are drawn on the leftmost segment).

        The tick *positions* are set on every segment so the horizontal grid
        lines and sub-tick marks stay consistent, even though only the
        leftmost one prints labels.
        """
        for seg in self.segments:
            seg.set_yticks(ticks, labels, dticks=dticks, dsubticks=dsubticks)
        return self

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
        exactly one back on. ``segment`` defaults to the widest one, which has
        the most room for a key.
        """
        if segment is None:
            segment = max(
                range(len(self.width_ratios)), key=lambda i: self.width_ratios[i]
            )
        for index, seg in enumerate(self.segments):
            if index == segment:
                seg.legend(loc, **kwargs)
            else:
                seg.legend_on = False
        return self

    def set_xlim(self, *args, **kwargs):
        """Not available -- the per-segment ranges are fixed at construction."""
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
        than embedded, because they are already serialized there in full.
        """
        axes_list = self.figure.axes_list if self.figure is not None else []
        return {
            "segments": [axes_list.index(seg) for seg in self.segments],
            "xlims": [list(pair) for pair in self.xlims],
            "width_ratios": list(self.width_ratios),
            "position": list(self.position),
            "gap": self.gap,
            "divider": self.divider,
            "divider_color": self.divider_color,
            "divider_linewidth": self.divider_linewidth,
            "divider_lstyle": self.divider_lstyle,
            "break_mark_size": self.break_mark_size,
            "trim_seam_labels": self.trim_seam_labels,
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
        obj.xlabel_text = d.get("xlabel_text", "")
        obj.title_text = d.get("title_text", "")

        obj.segments = [figure.axes_list[i] for i in d.get("segments", [])]
        for seg in obj.segments:
            seg._break_owner = obj
        return obj

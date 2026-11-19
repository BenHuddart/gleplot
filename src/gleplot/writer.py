"""GLE file writer for gleplot.

Besides turning the object model into GLE text, this module owns the
**write-time resolution of series data sources** (:mod:`gleplot.sources`).
Every series' numbers reach the emission code through one path --
:func:`resolve_figure` -> :class:`SourceResolution` -- whether they were baked
in by the scripting API or pulled from a :class:`~gleplot.sources.DataProvider`
table. Emission then sees an ordinary array-bearing series either way, so the
sidecar machinery below is unchanged for inline figures and byte-for-byte
identical to what it produced before sources existed.
"""

import hashlib
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import numpy as np

from . import palettes as _pal
from ._warn import warn_external
from .colors import apply_alpha
from .config import GLEGraphConfig, GLEMarkerConfig, GLEStyleConfig, GlobalConfig
from .guides import (
    GUIDE_MARKER_LABEL,
    GUIDE_MARKER_PREFIX,
    REFLINE_LAYER,
    SPAN_LAYER,
    guide_sub_name,
    guide_sub_texts,
)
from .parser.tables import (
    ARROW_JOIN_SEPS,
    ARROW_TIP_STYLES,
    FIT_MODEL_TO_ROUTINE,
    FIT_PLACEHOLDER_RE,
    FIT_PLACEHOLDER_SPEC_RE,
    FIT_RESULT_PLACEHOLDERS,
    KEY_ANCHOR_X,
    KEY_ANCHOR_Y,
    KEY_POSITIONS_LONG_TO_SHORT,
    KEY_POSITIONS_SHORT_TO_LONG,
    LEGEND_SPACING_TO_KEY,
    LINE_MODES,
    text_align_to_just,
    text_box_pad_token,
)
from .parser.units import (
    fontsize_pt_to_cm,
    inches_to_cm,
    linewidth_pt_to_cm,
)
from .series import (
    _DATASET_NAME_RE,
    SERIES_CLASSES,
    BarSeries,
    ErrorbarSeries,
    FileSeries,
    FillSeries,
    HistSeries,
    LineSeries,
    Series,
    TextAnnotation,
    _unique_column_names,
    is_visible,
    normalize_smooth_mode,
    normalize_svg_smooth,
    sanitize_column_name,
    sorted_zorder_drawables,
)
from .sources import (
    ColumnRef,
    DanglingSourceRef,
    DanglingSourceWarning,
    DataProvider,
    DataSource,
    GridRef,
    resolve_reference,
)

#: A quoted string in a GLE line.
_QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")

#: The sub behind every pie slice (:meth:`GLEWriter.add_wedge`). Called after
#: ``end graph``, where ``xg()``/``yg()`` still address the graph just closed.
#: Like the palette and guide subs, its text depends on nothing but its name,
#: so the parser drops the body and the writer regenerates it.
WEDGE_SUB = """sub gleplot_wedge cx cy r a1 a2 clr$ lbl$ ld pct$ pd
   ! Pie slice: centre (cx, cy) and radius r in data units, from a1 to a2
   ! degrees counter-clockwise from +x. The scale is the smaller of the two
   ! axes' cm per unit, so the slice stays circular in any graph shape.
   ! lbl$ goes ld radii out, left-justified right of x = 0 and right-
   ! justified left of it; pct$ goes pd radii out, centred. An empty string
   ! writes nothing. Text uses the current hei and colour.
   local s = xg(cx+1)-xg(cx)
   if yg(cy+1)-yg(cy) < s then s = yg(cy+1)-yg(cy)
   local m = torad((a1+a2)/2)
   amove xg(cx) yg(cy)
   begin path fill (cvtcolor(clr$))
      ! Without a move inside the path, it starts at the arc, not the centre.
      rmove 0 0
      arc r*s a1 a2
      closepath
   end path
   if lbl$ <> "" then
      amove xg(cx)+ld*r*s*cos(m) yg(cy)+ld*r*s*sin(m)
      if cx+ld*r*cos(m) > 0 then
         set just left
      else
         set just right
      end if
      write lbl$
   end if
   if pct$ <> "" then
      amove xg(cx)+pd*r*s*cos(m) yg(cy)+pd*r*s*sin(m)
      set just center
      write pct$
   end if
end sub"""


#: The subs behind every box of a box plot (:meth:`GLEWriter.add_box`),
#: called after ``end graph`` like :data:`WEDGE_SUB`. The style is
#: matplotlib's default: 1 pt black lines, a ``'C1'`` median, black open
#: circle fliers and a ``'C2'`` triangle mean, both of markersize 6. Each sub
#: saves and restores the graphics state, so it changes no ``set`` state.
#: Being outside the graph block, nothing clips them: the box is clipped to
#: the graph's frame (widened by half its line width), and a flier or mean outside the axis ranges is skipped,
#: as GLE skips a dataset's out-of-range markers.
BOX_SUB = """sub gleplot_box x w cw lo q1 med q3 hi
   ! Box plot box: from q1 to q3, w data units wide, centred on x, with a
   ! median line at med and whiskers out to lo and hi, capped cw data units
   ! wide (0 draws no caps).
   gsave
   set lwidth 0.03528 color black cap butt
   ! The clip reaches half a line width past the frame, so a cap or whisker
   ! lying on the frame is drawn whole.
   local h = 0.03528/2
   local x0 = min(xg(xgmin),xg(xgmax))-h
   local y0 = min(yg(ygmin),yg(ygmax))-h
   begin clip
   begin path clip
      amove x0 y0
      box max(xg(xgmin),xg(xgmax))+h-x0 max(yg(ygmin),yg(ygmax))+h-y0
   end path
   amove xg(x-w/2) yg(q1)
   box xg(x+w/2)-xg(x-w/2) yg(q3)-yg(q1)
   amove xg(x) yg(q1)
   aline xg(x) yg(lo)
   amove xg(x) yg(q3)
   aline xg(x) yg(hi)
   if cw > 0 then
      amove xg(x-cw/2) yg(lo)
      aline xg(x+cw/2) yg(lo)
      amove xg(x-cw/2) yg(hi)
      aline xg(x+cw/2) yg(hi)
   end if
   set color rgb255(255,127,14)
   amove xg(x-w/2) yg(med)
   aline xg(x+w/2) yg(med)
   end clip
   grestore
end sub

sub gleplot_box_flier x y
   ! One point beyond a box plot whisker, if inside the axis ranges.
   if (x >= xgmin) and (x <= xgmax) and (y >= ygmin) and (y <= ygmax) then
      gsave
      set lwidth 0.03528 color black
      amove xg(x) yg(y)
      marker circle 0.15
      grestore
   end if
end sub

sub gleplot_box_mean x y
   ! A box plot mean, if inside the axis ranges.
   if (x >= xgmin) and (x <= xgmax) and (y >= ygmin) and (y <= ygmax) then
      gsave
      set color rgb255(44,160,44)
      amove xg(x) yg(y)
      marker ftriangle 0.15
      grestore
   end if
end sub"""


#: Name prefix of the subs behind per-point marker sizes
#: (:meth:`GLEWriter.add_scatter`): ``gleplot_mdata_<marker>``, lower case.
MDATA_SUB_PREFIX = "gleplot_mdata_"


def mdata_sub_text(marker: str) -> str:
    """The sub and ``define marker`` that give a built-in marker ``mdata``.

    GLE passes a dataset's ``mdata`` value only to a marker defined by a
    subroutine (``g_marker2`` in ``core.cpp``); a built-in marker ignores it.
    This sub draws the built-in marker at ``msize`` times that value. Its text
    depends on nothing but its name, so the parser drops it and the writer
    regenerates it, like the palette, guide and wedge subs.
    """
    name = MDATA_SUB_PREFIX + marker.lower()
    # The ``marker`` command's size is a multiple of ``hei`` (``run.cpp``),
    # so the absolute size is set as ``hei``, saved and restored around it.
    # A size of 0 must draw nothing, and ``set hei 0`` does not.
    return (
        f"sub {name} size data\n"
        "   if data > 0 then\n"
        "      gsave\n"
        "      set hei size*data\n"
        f"      marker {marker.upper()}\n"
        "      grestore\n"
        "   end if\n"
        "end sub\n"
        f"define marker {name} {name}"
    )


#: Name prefix of the subs behind per-point colours
#: (:meth:`GLEWriter.add_scatter`): ``gleplot_cdata_<marker>_<cmap>``, lower
#: case. No marker name has an underscore, so the first one ends the marker.
CDATA_SUB_PREFIX = "gleplot_cdata_"


def cdata_sub_name(marker: str, cmap: str) -> str:
    """The marker sub that draws ``marker`` in ``cmap``'s colour per point."""
    return f"{CDATA_SUB_PREFIX}{marker.lower()}_{_pal.canonical_cmap(cmap)}"


def cdata_sub_text(marker: str, cmap: str) -> str:
    """The sub and ``define marker`` that colour a built-in marker per point.

    The sub's ``data`` is the point's ``mdata`` value: its colour value
    already mapped onto ``[0, 1]`` by a ``let``, which the palette sub
    clamps. GLE draws the legend marker with ``data`` 1, the colormap's last
    colour. Like :func:`mdata_sub_text`, its text depends on nothing but its
    name.
    """
    name = cdata_sub_name(marker, cmap)
    return (
        f"sub {name} size data\n"
        "   gsave\n"
        "   set hei size\n"
        f"   set color gleplot_{_pal.canonical_cmap(cmap)}(data)\n"
        f"   marker {marker.upper()}\n"
        "   grestore\n"
        "end sub\n"
        f"define marker {name} {name}"
    )


#: The subs behind a polar axes (:meth:`GLEWriter.add_polar_frame`). The grid
#: is drawn inside the graph block, in layer 200 with GLE's own grid, so the
#: curves go over it; the tick labels are written after ``end graph``, like
#: the pie text, because text written inside a graph-block ``draw`` loses its
#: font. Adapted from ``polar_grid`` in GLE's ``polarplot.gle``. The style is
#: matplotlib's default: 0.8 pt grey grid lines, a black outer ring, labels
#: every 45 degrees and one per ring along 22.5 degrees.
POLAR_SUB = """sub gleplot_polar_grid rmax step
   ! Polar grid about (0, 0): a ring every step inside rmax, a spoke every
   ! 45 degrees, and the outer ring at rmax.
   gsave
   set color rgb255(176,176,176) lwidth 0.02822
   for k = 1 to int(rmax/step-0.001)
      amove xg(0) yg(0)
      circle xg(k*step)-xg(0)
   next k
   for k = 0 to 7
      amove xg(0) yg(0)
      aline xg(rmax*cos(k*pi/4)) yg(rmax*sin(k*pi/4))
   next k
   set color black
   amove xg(0) yg(0)
   circle xg(rmax)-xg(0)
   grestore
end sub

sub gleplot_polar_labels rmax step dp deg$
   ! Polar tick labels: the angle every 45 degrees outside the rmax ring,
   ! followed by deg$, and each ring's radius with dp decimals along 22.5
   ! degrees. Text uses the current hei and colour.
   gsave
   local s = xg(1)-xg(0)
   local a = 0
   local t$ = ""
   local d = 0
   set just cc
   for k = 0 to 7
      a = k*pi/4
      t$ = format$(45*k,"fix 0")+deg$
      d = rmax*s+0.15+(abs(cos(a))*twidth(t$)+abs(sin(a))*theight(t$))/2
      amove xg(0)+d*cos(a) yg(0)+d*sin(a)
      write t$
   next k
   set just bl
   for k = 1 to int(rmax/step+0.001)
      amove xg(k*step*cos(pi/8)) yg(k*step*sin(pi/8))
      write format$(k*step,"fix "+num$(dp))
   next k
   grestore
end sub"""

#: Layer of the polar grid draw: GLE's own grid layer, below the curves.
POLAR_GRID_LAYER = 200


def polar_ring_step(rmax: float) -> float:
    """Distance between the rings of a polar grid out to ``rmax``.

    The smallest of 1, 2, 2.5 and 5 times a power of ten that gives at most
    five rings, as matplotlib's radial ticks do.
    """
    raw = rmax / 5.0
    magnitude = 10.0 ** math.floor(math.log10(raw))
    for factor in (1.0, 2.0, 2.5, 5.0, 10.0):
        if factor * magnitude >= raw * (1 - 1e-9):
            return float(f"{factor * magnitude:.6g}")
    return 10.0 * magnitude  # pragma: no cover - 10 always qualifies


def polar_degree_mark(usetex: bool) -> str:
    """The degree sign after a polar angle label, in GLE or LaTeX text."""
    return "$^{\\circ}$" if usetex else "^{\\circ}"


def polar_label_decimals(step: float) -> int:
    """Decimals in a polar ring label: as many as ``step`` has."""
    return len(f"{step:.10f}".rstrip("0").split(".")[1])


def polar_window(
    rmax: float, frame: Optional[Tuple[float, float]], hei_cm: float
) -> Tuple[float, float]:
    """The x and y half-ranges of a polar axes' graph window.

    Both axes get the same cm per unit, so the rings are circles, and the
    outer ring is inset from the frame far enough for the angle labels. With
    no frame size (a graph whose geometry gleplot does not place), the
    window is the square ``-rmax .. rmax``.
    """
    if frame is None:
        return rmax, rmax
    # As written to the script, so a parsed figure derives the same window.
    width, height, hei_cm = (
        float(GLEWriter._format_number(v)) for v in (frame[0], frame[1], hei_cm)
    )
    radius = min(width / 2 - (0.15 + 2.5 * hei_cm), height / 2 - (0.15 + 1.2 * hei_cm))
    if radius <= 0:
        radius = min(width, height) / 2
    return rmax * width / 2 / radius, rmax * height / 2 / radius


#: The subs that draw a placed image (:meth:`GLEWriter.add_image`) from
#: inside the graph block, where ``xg()``/``yg()`` map data coordinates to
#: the page, keyed by name; a script defines the ones its images use.
#: ``bitmap`` reads PNG, JPEG, GIF and TIFF files; ``postscript`` reads EPS,
#: and only GLE's PostScript route draws it (with ``-cairo`` it draws
#: nothing).
IMAGE_SUBS: Dict[str, str] = {
    "gleplot_bitmap": """sub gleplot_bitmap f$ x0 x1 y0 y1
   ! Image file f$ stretched from (x0, y0) to (x1, y1) in data coordinates.
   amove xg(x0) yg(y0)
   bitmap f$ xg(x1)-xg(x0) yg(y1)-yg(y0)
end sub""",
    "gleplot_postscript": """sub gleplot_postscript f$ x0 x1 y0 y1
   ! EPS file f$ stretched from (x0, y0) to (x1, y1) in data coordinates.
   amove xg(x0) yg(y0)
   postscript f$ xg(x1)-xg(x0) yg(y1)-yg(y0)
end sub""",
}

#: Graph layer of a placed image: below GLE's grid (200), so the grid, the
#: fills, the axes and the data are all drawn over it. A graph ``draw`` is
#: clipped to the frame.
IMAGE_LAYER = 150

#: Image file extension (lower case) -> the :data:`IMAGE_SUBS` sub drawing it.
_IMAGE_SUB_BY_SUFFIX = {
    ".png": "gleplot_bitmap",
    ".jpg": "gleplot_bitmap",
    ".jpeg": "gleplot_bitmap",
    ".gif": "gleplot_bitmap",
    ".tif": "gleplot_bitmap",
    ".tiff": "gleplot_bitmap",
    ".eps": "gleplot_postscript",
}


def image_sub_name(path: str) -> Optional[str]:
    """The :data:`IMAGE_SUBS` sub that draws ``path``, by its extension.

    ``None`` for a file type GLE cannot place.
    """
    return _IMAGE_SUB_BY_SUFFIX.get(Path(path).suffix.lower())


#: The frame edges a rug can stand on, per axis; the first is the default.
#: The ticks of an ``axis`` rug are ``gleplot_<axis>rug`` calls.
RUG_EDGES = {"x": ("bottom", "top", "both"), "y": ("left", "right", "both")}

#: The subs behind every rug tick (:meth:`GLEWriter.add_rug`), called after
#: ``end graph`` like :data:`BOX_SUB`. A positive ``len`` points into the
#: axes, as GLE's ``ticks length`` does. The frame edges are the min and max
#: of the axis ends, so ``bottom`` stays the lower edge on a reversed axis. A
#: value outside the axis range draws nothing. Each tick saves and restores
#: the graphics state.
RUG_SUB = """sub gleplot_xrug x len pos$ clr$ lw
   ! Rug tick at x on the bottom or top edge of the frame, or both.
   if (x >= xgmin) and (x <= xgmax) then
      gsave
      set lwidth lw color cvtcolor(clr$) cap butt
      if (pos$ = "bottom") or (pos$ = "both") then
         amove xg(x) min(yg(ygmin),yg(ygmax))
         rline 0 len
      end if
      if (pos$ = "top") or (pos$ = "both") then
         amove xg(x) max(yg(ygmin),yg(ygmax))
         rline 0 -len
      end if
      grestore
   end if
end sub

sub gleplot_yrug y len pos$ clr$ lw
   ! Rug tick at y on the left or right edge of the frame, or both.
   if (y >= ygmin) and (y <= ygmax) then
      gsave
      set lwidth lw color cvtcolor(clr$) cap butt
      if (pos$ = "left") or (pos$ = "both") then
         amove min(xg(xgmin),xg(xgmax)) yg(y)
         rline len 0
      end if
      if (pos$ = "right") or (pos$ = "both") then
         amove max(xg(xgmin),xg(xgmax)) yg(y)
         rline -len 0
      end if
      grestore
   end if
end sub"""


@dataclass(frozen=True)
class AxisStyle:
    """Styling for ONE axis (x, y or y2) of a graph block.

    The parameter object :meth:`GLEWriter.add_axes` takes instead of a dozen
    more keyword arguments per axis. Every field is optional and ``None``
    means "emit nothing", so the default instance -- ``AxisStyle()`` -- writes
    exactly the GLE gleplot wrote before axes styling existed.
    :class:`gleplot.Axes` holds the same information as flat attributes
    (``xformat``, ``xgrid``, ``xlabel_size``, ...) and
    ``Figure._axis_style`` assembles them here, applying the figure-wide
    :class:`~gleplot.config.GLEGraphConfig` defaults on the way.

    Attributes
    ----------
    fmt : str, optional
        Tick-label number format -- GLE ``xaxis format "<fmt>"``. Free-form
        (see :func:`gleplot.axes.validate_tick_format`).
    grid : {'major', 'both'}, optional
        Draw grid lines from this axis' ticks (GLE ``xaxis grid``);
        ``'both'`` adds ``xsubticks on`` so the subticks become grid lines
        too. Not meaningful on y2 (the y grid already spans to it).
    grid_lstyle : int, optional
        GLE ``lstyle`` number for the grid/tick lines.
    grid_lwidth : float, optional
        Grid/tick line width in POINTS (converted to GLE cm on emission).
    grid_color : str, optional
        Grid/tick colour.
    title_size, title_color, title_dist : optional
        ``hei`` (points), ``color`` and ``dist`` (cm) of this axis' title --
        GLE ``xtitle "..." hei H color C dist D``.
    label_size, label_color : optional
        ``hei`` (points) and ``color`` of the tick labels (GLE ``xlabels``).
    label_angle : float, optional
        Tick-label rotation in degrees (GLE ``xaxis angle``).
    title_font : str, optional
        GLE font of this axis' title -- ``xtitle "..." font F``.
    side_color, side_lwidth : optional
        Colour and width (points) of the axis line -- GLE ``xside color C
        lwidth W``.
    side_off : bool, optional
        ``xside off`` (True) or ``on`` (False): the axis line alone,
        hidden or shown.
    nticks, ftick, shift, symticks : optional
        Tick placement on the ``xaxis`` line: ``nticks N``, ``ftick F``,
        ``shift S`` (cm) and a bare ``symticks`` when True.
    noticks : list of float, optional
        Positions with no tick -- GLE ``xnoticks p1 p2 ...``.
    nsubticks : int, optional
        Minor ticks per major interval -- ``xaxis nsubticks N``.
    loglabels : str, optional
        Log sub-decade labels -- ``xlabels log MODE``.
    tick_length, tick_width, tick_color, tick_direction : optional
        The major tick marks -- ``xticks length L lwidth W color C``. Length
        (matplotlib's whole tick) and width are points; direction is
        ``'in'`` or ``'out'``, written as the sign of the length.
    subtick_length, subtick_width, subtick_color, subtick_direction : optional
        The same for the minor ticks, on ``xsubticks``.
    minorticks : bool, optional
        ``xsubticks on`` (True) or ``off`` (False).

    Notes
    -----
    ``grid_*`` are only emitted when ``grid`` is set: in GLE the grid lines
    ARE the axis ticks (``xticks lstyle ...``), so a grid style without a
    grid would silently restyle the ticks instead.
    """

    fmt: Optional[str] = None
    grid: Optional[str] = None
    grid_lstyle: Optional[int] = None
    grid_lwidth: Optional[float] = None
    grid_color: Optional[str] = None
    title_size: Optional[float] = None
    title_color: Optional[str] = None
    title_dist: Optional[float] = None
    label_size: Optional[float] = None
    label_color: Optional[str] = None
    label_angle: Optional[float] = None
    title_font: Optional[str] = None
    side_color: Optional[str] = None
    side_lwidth: Optional[float] = None
    side_off: Optional[bool] = None
    nticks: Optional[int] = None
    ftick: Optional[float] = None
    shift: Optional[float] = None
    symticks: Optional[bool] = None
    noticks: Optional[List[float]] = None
    nsubticks: Optional[int] = None
    loglabels: Optional[str] = None
    tick_length: Optional[float] = None
    tick_width: Optional[float] = None
    tick_color: Optional[str] = None
    tick_direction: Optional[str] = None
    subtick_length: Optional[float] = None
    subtick_width: Optional[float] = None
    subtick_color: Optional[str] = None
    subtick_direction: Optional[str] = None
    minorticks: Optional[bool] = None

    def has_tick_label_styling(self) -> bool:
        """True if anything here changes how the tick labels are drawn.

        Used for GLE's y2 rule: y2 (and x2) tick labels are OFF unless
        ``y2labels on`` is given, so any y2 tick-label property implies it.
        """
        return (
            self.fmt is not None
            or self.label_size is not None
            or self.label_color is not None
            or self.label_angle is not None
        )


#: matplotlib's default tick lengths in points (``xtick.major.size`` /
#: ``xtick.minor.size``), for an outward tick given no length.
_MPL_TICK_SIZE = {"major": 3.5, "minor": 2.0}

#: An axis with no styling at all -- shared so the common case allocates
#: nothing and ``style is _NO_STYLE`` short-circuits are possible.
_NO_STYLE = AxisStyle()


def _format_data_filename(name: str) -> str:
    """Quote a data filename for a GLE ``data`` command when needed.

    GLE requires quoting for paths containing whitespace (e.g. absolute
    OneDrive paths). Names without whitespace or quote characters are
    emitted bare, preserving byte-identical output for all previously
    generated scripts.
    """
    name = str(name)
    if any(ch in name for ch in ' \t"'):
        return '"' + name.replace('"', '\\"') + '"'
    return name


def _group_bar_header(members: Sequence[Mapping[str, Any]], n_columns: int):
    """A header row for a grouped bar sidecar, or ``None`` to omit one.

    Omitted unless every member already carries column names and those
    names line up with the columns actually written. A partial header
    would make GLE invent a legend entry the series did not ask for.
    """
    if not members or any(not member.get("column_names") for member in members):
        return None
    stacked = any(member.get("bottom") is not None for member in members)
    names = [str(members[0]["column_names"][0])]
    for member in members:
        named = list(member["column_names"])
        if stacked:
            if member.get("bottom") is not None and len(named) >= 3:
                names.extend(str(part) for part in named[1:3])
            else:
                names.extend(["bottom", "top"])
        else:
            names.append(str(named[1]) if len(named) > 1 else "height")
    if len(names) != n_columns:
        return None
    return names


def _quote_filename(name: str) -> str:
    """Always quote a filename for GLE.

    Used for the contour/heatmap grid and generated files: their names contain
    hyphens (``-cdata.dat``/``-clabels.dat``) which GLE would otherwise parse
    as subtraction ("left hand side contains unquoted string"). Quoting is
    always valid, so it is applied unconditionally in these contexts.
    """
    return '"' + str(name).replace('"', '\\"') + '"'


def _grid_z_file(series: Mapping[str, Any]) -> str:
    """The ``.z`` grid file a heatmap's ``colormap`` or a contour block reads.

    A grid series reads its written ``.z`` sidecar directly; a points series
    reads the ``.z`` file GLE's ``fitz`` generates (the points sidecar's
    name with ``.dat`` replaced by ``.z``).
    """
    df = series["data_file"]
    if series["source"] == "grid":
        return df
    return df[:-4] + ".z" if df.endswith(".dat") else df + ".z"


# -- provider-table sidecars ---------------------------------------------------


class ColumnBinding:
    """Says where a provider-backed series' columns live in a shared sidecar.

    An inline series owns its ``.dat`` outright and writes columns ``c1..cN``
    in role order. A series resolved from a provider table instead *shares*
    one sidecar with every other series drawing from the same table (§3.2), so
    its roles land at whatever column index the union happened to put them at.
    This object carries the mapping the emission code needs to say
    ``dN=c1,c4`` instead of always ``dN=c1,c2``.

    Attributes
    ----------
    data_file : str
        Name of the shared sidecar.
    keys : dict
        Series role (``'x'``, ``'y'``, ``'yerr_up'``, ...) -> stable column
        key in the provider table.
    names : dict
        Column key -> the table's *display* name for it, used to build the
        one header row the shared file gets.
    uid : str
        Identifies the series, so a role it supplies inline (a constant error
        column on an otherwise table-backed errorbar) gets a private column in
        the shared file rather than colliding with another series' column.
    """

    __slots__ = ("data_file", "keys", "names", "uid")

    def __init__(
        self,
        data_file: str,
        keys: Mapping[str, Any],
        names: Mapping[str, str],
        uid: str,
    ) -> None:
        self.data_file = data_file
        self.keys = dict(keys)
        self.names = dict(names)
        self.uid = uid

    def column_for(self, role: str) -> Tuple[str, str]:
        """``(column key, display name)`` for one role.

        A role the reference does not mention is inline data riding along in
        the shared file; it gets a key private to this series and is named
        after the role.
        """
        key = self.keys.get(role)
        if key is None or isinstance(key, list):
            private = f"{self.uid}\x00{role}"
            return private, role
        return key, self.names.get(key, role)

    def with_private(self, roles: Sequence[str]) -> "ColumnBinding":
        """A copy in which ``roles`` get columns private to this series."""
        keys = {role: key for role, key in self.keys.items() if role not in roles}
        return ColumnBinding(self.data_file, keys, self.names, self.uid)


class _SharedSidecar:
    """A ``.dat`` file accumulating the union of several series' columns.

    Columns are keyed, so two series naming the same table column write it
    once and both reference the same ``cN``. Order is first-mention order,
    which makes the file deterministic given a deterministic series walk (see
    :func:`resolve_figure`) and therefore fixed-point safe.
    """

    def __init__(self) -> None:
        self.keys: List[str] = []
        self.names: List[str] = []
        self.columns: List[np.ndarray] = []
        #: Whether the file gets a header row: not when an inline series
        #: whose own file had none shares it (a header could name its keys).
        self.named = True

    def index_of(self, key: str, values: np.ndarray, name: str) -> int:
        """1-based column index of ``key``, appending it on first mention."""
        try:
            return self.keys.index(key) + 1
        except ValueError:
            pass
        self.keys.append(key)
        self.names.append(name)
        values = np.asarray(values)
        # Only the ``*`` missing values of _as_missing are kept as written.
        if values.dtype != object or not (values == "*").any():
            values = values.astype(float)
        self.columns.append(values)
        return len(self.keys)

    def header(self) -> List[str]:
        """The single header row: sanitized display names, made unique."""
        return _unique_column_names(
            [
                sanitize_column_name(name, fallback=f"col{i + 1}")
                for i, name in enumerate(self.names)
            ]
        )


class _InlineSidecar(NamedTuple):
    """The sidecar one inline series wrote: its columns, header, column keys."""

    columns: List[Tuple[str, np.ndarray]]
    column_names: Optional[List[str]]
    keys: List[str]


# -- write-time source resolution ----------------------------------------------


class SourceResolution:
    """The result of resolving every series' data source for one write.

    The single gate between the object model and emission. Ask it for a
    series' data and you get back either an array-bearing series (the original
    object itself when it was inline -- no copy, so inline figures are exactly
    as they were) or ``None``, meaning "skip this one". Every list-walking
    helper in :mod:`gleplot.figure` goes through :meth:`visible` so a skipped
    series disappears from autoscaling, the legend and the emitted script
    alike.

    There are two independent reasons to skip, and they are never conflated:

    * the series' reference is **dangling** (SPEC 3.2) -- it wanted data that
      could not be found, which is a fault, and it is recorded in
      :attr:`warnings`;
    * the series is **hidden** (``visible = False``, SPEC 14.6) -- the user
      switched it off, which is not a fault and produces no warning.
    """

    def __init__(self) -> None:
        #: Structured records for every series skipped this write.
        self.warnings: List[DanglingSourceRef] = []
        self._data: Dict[int, Optional[Series]] = {}
        self._bindings: Dict[int, ColumnBinding] = {}
        # Hold the originals so their ids cannot be reused by a new object
        # while this resolution is alive.
        self._originals: List[Series] = []

    # -- population (used by resolve_figure) --------------------------------

    def _record(
        self,
        series: Series,
        data: Optional[Series],
        binding: Optional[ColumnBinding] = None,
    ) -> None:
        self._originals.append(series)
        self._data[id(series)] = data
        if binding is not None:
            self._bindings[id(series)] = binding

    def _skip(self, series: Series, ref: DanglingSourceRef) -> None:
        self._record(series, None)
        self.warnings.append(ref)

    # -- queries ------------------------------------------------------------

    def data(self, series: Series) -> Optional[Series]:
        """The array-bearing form of ``series``, or ``None`` if it is skipped.

        A series this resolution never saw (one materialized at write time
        from a declaration -- ``axvline`` guides, ``axvspan`` bands) is inline
        by construction and is returned unchanged.

        The hidden check is made here rather than only in
        :func:`resolve_figure` so that it also holds for a series this
        resolution never saw: the autoscale helpers accept ``resolution=None``
        and fall back to an empty :class:`SourceResolution`, and "hidden" has
        to mean hidden on that path too.
        """
        if not is_visible(series):
            return None
        return self._data.get(id(series), series)

    def binding(self, series: Series) -> Optional[ColumnBinding]:
        """The shared-sidecar binding for ``series``, if it has one."""
        return self._bindings.get(id(series))

    def visible(self, series_list: Sequence[Series]) -> List[Series]:
        """``series_list`` resolved, with skipped entries dropped.

        Skipped means dangling *or* hidden -- see the class docstring for why
        those stay two distinct reasons with one shared consequence.
        """
        out = []
        for series in series_list:
            data = self.data(series)
            if data is not None:
                out.append(data)
        return out

    def pairs(self, series_list: Sequence[Series]) -> List[Tuple[Series, Series]]:
        """``(original, resolved)`` for every entry that is not skipped.

        Emission needs both: the resolved copy for the numbers, the original
        for the identity that :meth:`binding` is keyed by.
        """
        out = []
        for series in series_list:
            data = self.data(series)
            if data is not None:
                out.append((series, data))
        return out

    def drawables(self, ax: Any) -> List[Tuple[str, Series, Series]]:
        """z-ordered ``(kind, original, resolved)`` triples for one axes."""
        out = []
        for kind, series in sorted_zorder_drawables(ax):
            data = self.data(series)
            if data is not None:
                out.append((kind, series, data))
        return out

    def emit_warnings(self) -> None:
        """Re-raise every record through the :mod:`warnings` machinery.

        The structured records are the primary channel on ``Figure.source_warnings``;
        this is the courtesy channel so a script
        that silently loses a series at least says so on stderr. Each warning
        carries its record on ``.ref``.
        """
        for ref in self.warnings:
            warn_external(DanglingSourceWarning(ref))


# -- write-time autos for reference-backed grid series (G13; SPEC 14.5) -------
#
# The scripting API bakes a heatmap's/contour's ``extent`` -- and a colorbar's
# ``zmin``/``zmax``/``zstep`` -- at call time from the arrays it is handed.
# A *reference-backed* grid series has no arrays at call time: they arrive per
# write from the provider, and a value baked from an earlier write would go
# stale the moment a cell changed. So those two things become **absent/auto**
# states on such a series, and this is where each write turns them back into
# numbers, from the arrays that write actually resolved.
#
# The computations reproduce the creation APIs' defaults exactly -- grid mode
# ``(0, nx, 0, ny)`` (``Axes.imshow``), points mode the data bounds
# (``Axes._points_from_args``), the colorbar range ``vmin``/``vmax`` else the
# data's nan-safe min/max with ``zstep`` = span / nticks (``Figure.colorbar``)
# -- so an auto value is never a *different* answer from the baked one, only a
# later one.

#: Marker key on a colorbar dict meaning "this range is computed per write".
#: Absent (the historical shape, and what the recognizer rebuilds from an
#: emitted ``gleplot_colorbar_v`` call) means the stored numbers are explicit
#: and are emitted untouched.
COLORBAR_AUTO_RANGE = "auto_range"

#: Companion key: the tick-interval count an auto range divides its span by.
#: Stored only on an auto colorbar, so an explicit one serializes exactly as
#: it did before G13.
COLORBAR_NTICKS = "nticks"

#: Colorbar tick-interval count when none was given (``Figure.colorbar``'s).
DEFAULT_COLORBAR_NTICKS = 5

#: How the comment line under a ``.z`` header that marks a ``pcolormesh``
#: grid begins; the mesh's edges follow (see
#: :meth:`GLEWriter.add_cells_sidecar`).
CELLS_MARKER = "! gleplot: cells"

#: How the comment line under a ``.z`` header that marks a ``contourf`` grid
#: begins; the grid's edges follow (see :meth:`GLEWriter.add_nodes_sidecar`).
NODES_MARKER = "! gleplot: nodes"

#: How the comment line in a ``gleplot_contourf<k>`` palette sub that holds
#: the series' colouring begins (see :meth:`GLEWriter.add_contourf_sub`).
CONTOURF_MARKER = "! gleplot: contourf"

#: The ``extend`` values a ``contourf`` takes, as in matplotlib.
CONTOURF_EXTENDS = ("neither", "min", "max", "both")

#: The ``plot`` series fields :meth:`GLEWriter._dataset_qualifier_clause`
#: writes.
_DATASET_QUALIFIERS = (
    "mdist",
    "deresolve",
    "deresolve_average",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
)


def _grid_values(series: Mapping[str, Any]) -> Optional[np.ndarray]:
    """The z-values a grid series colours by, or ``None`` if it has none.

    ``'grid'`` mode reads the 2-D ``z`` grid; ``'points'`` mode the 1-D
    ``zpts`` samples. A missing array yields ``None`` rather than an
    exception -- the whole point of the auto states is that "no arrays yet"
    is a legal model state, not a bug.
    """
    raw = series.get("zpts") if series.get("source") == "points" else series.get("z")
    if raw is None:
        return None
    values = np.asarray(raw, dtype=float)
    return values if values.size else None


def _bspline_weights(u: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """Node indices and weights GLE's bicubic colormap reads at node coord ``u``.

    ``BicubicIpol::ipol`` (GLE ``src/gle/bitmap/img2ps.cpp``, main 949e21e)
    sums the four nodes ``floor(u) - 1 .. floor(u) + 2``, clamped to the
    grid, weighted by the cubic B-spline ``R``: an approximating spline, not
    an interpolating one, so it does not pass through the node values.
    """
    i = np.floor(u).astype(int)
    d = u - i
    idx = np.stack([np.clip(i + m, 0, n - 1) for m in (-1, 0, 1, 2)])
    x = np.stack([m - d for m in (-1.0, 0.0, 1.0, 2.0)])
    w = sum(
        c * np.clip(x + k, 0, None) ** 3 for c, k in ((1, 2), (-4, 1), (6, 0), (-4, -1))
    )
    return idx, w / 6


def _band_of(values: np.ndarray, levels: List[float]) -> np.ndarray:
    """Each value's band as :meth:`GLEWriter.add_contourf_sub` colours it.

    ``0`` below the first level, ``len(levels)`` above the last, else band
    ``i`` for ``levels[i - 1] < value <= levels[i]``, the first band also
    taking its lower level, as matplotlib's ``contourf`` bands do.
    """
    band = np.searchsorted(levels, values, side="left")
    band[values == levels[0]] = 1
    return band


def contourf_bands_fit(series: Mapping[str, Any]) -> bool:
    """Whether GLE draws a ``contourf`` heatmap's bands where its levels are.

    Emulates the bitmap GLE's ``colormap`` makes of the series' grid (its
    ``pixels``, over its ``extent``, from the node-placed sidecar
    :meth:`GLEWriter.add_nodes_sidecar` writes) and compares each pixel's
    band with the band the grid's bilinear surface puts there. The bands fit
    when every pixel GLE colours differently lies within one pixel of where
    the true band is. Computed from the numbers as written, so a figure read
    back from its file decides the same way.
    """
    fmt = GLEWriter._format_number
    z = np.asarray(series["z"], float)
    z = np.array([float(t) for t in GLEWriter._format_column(z.ravel())]).reshape(
        z.shape
    )
    levels = [float(fmt(v)) for v in series["levels"]]
    ny, nx = z.shape
    px, py = series["pixels"]
    u = (np.arange(px) + 0.5) / px * (nx - 1)
    v = (np.arange(py) + 0.5) / py * (ny - 1)
    xi, xw = _bspline_weights(u, nx)
    yi, yw = _bspline_weights(v, ny)
    rows = sum(z[:, xi[m]] * xw[m] for m in range(4))
    drawn = sum(rows[yi[m], :] * yw[m][:, None] for m in range(4))
    j = np.minimum(np.floor(u).astype(int), nx - 2)
    k = np.minimum(np.floor(v).astype(int), ny - 2)
    a, b = u - j, (v - k)[:, None]
    lower = z[k][:, j] * (1 - a) + z[k][:, j + 1] * a
    upper = z[k + 1][:, j] * (1 - a) + z[k + 1][:, j + 1] * a
    true = lower * (1 - b) + upper * b
    got, want = _band_of(drawn, levels), _band_of(true, levels)
    near = np.zeros(want.shape, bool)
    padded = np.pad(want, 1, mode="edge")
    for dy in range(3):
        for dx in range(3):
            near |= padded[dy : dy + py, dx : dx + px] == got
    return bool(np.all(near))


def auto_extent(series: Mapping[str, Any]) -> Optional[List[float]]:
    """The ``(xmin, xmax, ymin, ymax)`` a resolved grid series' arrays imply.

    Grid mode: ``(0, nx, 0, ny)`` for a ``(ny, nx)`` grid -- index space,
    which is what :meth:`gleplot.Axes.imshow` defaults to. Points mode: the
    scattered samples' bounds, which is what :meth:`gleplot.Axes.tripcolor`
    defaults to.

    Returns ``None`` when the arrays cannot produce a *valid* extent (GLE
    needs ``xmin < xmax`` and ``ymin < ymax``; see
    ``gleplot.axes._require_valid_extent``), i.e. an empty grid or scattered
    samples that are constant in x or y.
    """
    if series.get("source") == "points":
        x = series.get("x")
        y = series.get("y")
        if x is None or y is None:
            return None
        xa = np.asarray(x, dtype=float).ravel()
        ya = np.asarray(y, dtype=float).ravel()
        if xa.size == 0 or ya.size == 0:
            return None
        ext = [
            float(np.min(xa)),
            float(np.max(xa)),
            float(np.min(ya)),
            float(np.max(ya)),
        ]
    else:
        z = series.get("z")
        if z is None:
            return None
        za = np.asarray(z, dtype=float)
        if za.ndim != 2:
            return None
        ny, nx = za.shape
        ext = [0.0, float(nx), 0.0, float(ny)]

    if not all(np.isfinite(v) for v in ext):
        return None
    if not (ext[0] < ext[1] and ext[2] < ext[3]):
        return None
    return ext


def auto_colorbar_range(
    series: Mapping[str, Any], nticks: Optional[int] = None
) -> Optional[Tuple[float, float, float]]:
    """``(zmin, zmax, zstep)`` for an auto colorbar on a resolved heatmap.

    Same precedence :meth:`gleplot.Figure.colorbar` applies when it has the
    arrays in hand: an explicit ``vmin``/``vmax`` on the series wins,
    otherwise the data's nan-safe extreme. Deferring rather than duplicating
    that rule is what makes a later ``vmin`` edit show up on the bar.

    Returns ``None`` when neither an explicit bound nor usable data is
    available for one of the ends (an all-NaN or empty grid).
    """
    divisions = int(nticks) if nticks else DEFAULT_COLORBAR_NTICKS
    if divisions < 1:
        divisions = DEFAULT_COLORBAR_NTICKS

    values = _grid_values(series)
    finite = None
    if values is not None:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            finite = None

    vmin = series.get("vmin")
    vmax = series.get("vmax")
    if vmin is not None:
        zmin = float(vmin)
    elif finite is not None:
        zmin = float(np.min(finite))
    else:
        return None
    if vmax is not None:
        zmax = float(vmax)
    elif finite is not None:
        zmax = float(np.max(finite))
    else:
        return None

    if not (np.isfinite(zmin) and np.isfinite(zmax)):
        return None
    span = zmax - zmin
    zstep = (span / divisions) if span > 0 else 1.0
    return zmin, zmax, zstep


def apply_grid_write_time_autos(data: Series) -> Optional[str]:
    """Fill a resolved grid series' auto ``extent`` / colorbar range in place.

    ``data`` is the *copy* :func:`resolve_figure` made for this write, never
    the document's own series -- an auto value must not be baked back onto the
    model, or the next write would emit a stale one. The colorbar dict is
    replaced rather than mutated for the same reason (a series ``copy()`` is
    shallow, so the dict is shared with the original).

    Returns ``None`` on success, or a short reason string when the resolved
    arrays cannot produce the value, in which case the caller skips the
    series.
    """
    if data.get("extent") is None:
        ext = auto_extent(data)
        if ext is None:
            return "extent"
        data["extent"] = ext

    cb = data.get("colorbar")
    if isinstance(cb, Mapping) and cb.get(COLORBAR_AUTO_RANGE):
        computed = auto_colorbar_range(data, cb.get(COLORBAR_NTICKS))
        if computed is None:
            return "colorbar-range"
        zmin, zmax, zstep = computed
        resolved = dict(cb)
        resolved["zmin"] = zmin
        resolved["zmax"] = zmax
        resolved["zstep"] = zstep
        data["colorbar"] = resolved
    return None


def resolve_figure(
    figure: Any, data_provider: Optional[DataProvider] = None
) -> SourceResolution:
    """Resolve every series' data source across ``figure``.

    Walks the figure in a fixed order -- axes order, then
    :data:`gleplot.series.SERIES_CLASSES` order, then list order -- so the
    shared-sidecar layout (which table gets which filename, and which column
    lands at which index) is a pure function of the figure and is stable
    across repeated writes.

    Sidecar sharing: the first series to reference a given ``table_id`` donates
    its own ``data_file`` name to the shared sidecar, and every later series on
    that table writes into it instead of its own. No new filename is reserved,
    so nothing about the figure is mutated by a write and the fixed-point
    property is untouched.

    A reference that cannot be resolved -- no provider, no such table, no such
    column, or a source kind this build does not know -- produces a
    :class:`~gleplot.sources.DanglingSourceRef` and the series is skipped.
    Nothing raises: a figure in which *every* series is dangling still writes
    a valid, empty ``.gle``.

    A **hidden** series (``visible = False``, SPEC 14.6) is skipped before any
    of that, which is what "a hidden series affects nothing rendered" means in
    practice: it resolves no reference, so it produces no dangling warning
    about data nothing was going to draw; and it never reaches the
    ``table_files`` bookkeeping, so it cannot donate its filename to a shared
    sidecar that only other series write into.

    A resolved :class:`~gleplot.sources.GridRef` series additionally gets its
    **write-time autos** filled in here (SPEC 14.5, G13): an absent ``extent``
    and an auto colorbar range become numbers derived from *this* write's
    arrays, so a cell edit re-flows into both. Only the copy is filled; the
    document keeps its auto state. Arrays that cannot produce them (an empty
    grid, scattered samples constant in x or y, an all-NaN grid under an auto
    colorbar) skip the series with reason ``'unusable-data'`` rather than
    raising -- see :func:`apply_grid_write_time_autos`.
    """
    resolution = SourceResolution()
    table_files: Dict[str, str] = {}

    for axes_index, ax in enumerate(getattr(figure, "axes_list", []) or []):
        for attr, series_cls in SERIES_CLASSES.items():
            for series_index, series in enumerate(getattr(ax, attr, []) or []):
                if not is_visible(series):
                    resolution._record(series, None)
                    continue

                raw = series.get("data_source")
                if raw is None or (
                    isinstance(raw, DataSource) and not raw.is_reference()
                ):
                    # Inline: the arrays are already on the series. Recorded
                    # as itself, so no copy is made and emission is unchanged.
                    resolution._record(series, series)
                    continue

                resolved, reason, missing = resolve_reference(
                    raw, data_provider, series_cls.ARRAY_FIELDS
                )
                if resolved is None:
                    table_id = (
                        raw.get("table_id", "") if isinstance(raw, Mapping) else ""
                    )
                    resolution._skip(
                        series,
                        DanglingSourceRef(
                            axes_index=axes_index,
                            series_attr=attr,
                            series_index=series_index,
                            label=series.get("label"),
                            table_id=str(table_id),
                            reason=str(reason),
                            missing_columns=missing,
                        ),
                    )
                    continue

                data = series.copy()
                for role, values in resolved.values.items():
                    data[role] = values

                if isinstance(raw, GridRef):
                    # A reference-backed grid series may carry an absent
                    # ``extent`` and/or an auto colorbar range (SPEC 14.5).
                    # Now -- with this write's arrays in hand -- is the only
                    # honest moment to turn either into numbers.
                    unusable = apply_grid_write_time_autos(data)
                    if unusable is not None:
                        resolution._skip(
                            series,
                            DanglingSourceRef(
                                axes_index=axes_index,
                                series_attr=attr,
                                series_index=series_index,
                                label=series.get("label"),
                                table_id=str(resolved.table_id),
                                reason="unusable-data",
                                missing_columns=(),
                            ),
                        )
                        continue

                binding = None
                if isinstance(raw, ColumnRef):
                    # Grid series (GridRef) write a raw ``.z``/points sidecar
                    # of their own that GLE's colormap/fitz reads directly --
                    # there is nothing to share.
                    default_name = series.get("data_file") or (
                        f"{getattr(figure, 'data_prefix', None) or 'data'}"
                        f"_table{len(table_files) + 1}.dat"
                    )
                    shared_file = table_files.setdefault(
                        resolved.table_id, str(default_name)
                    )
                    binding = ColumnBinding(
                        shared_file,
                        resolved.column_keys,
                        resolved.display_names,
                        uid=f"{axes_index}.{attr}.{series_index}",
                    )
                resolution._record(series, data, binding)

    return resolution


# -- preview-only deresolve decimation (G7; SPEC 6.1/10.7) --------------------


@dataclass(frozen=True)
class DecimationRecord:
    """One series whose emitted ``dN`` line got a preview-only ``deresolve``.

    Returned via :attr:`GLEWriter.decimation_report` so a caller (GLEstudio's
    render controller) can badge "preview decimated x N" on exactly the
    series that changed, and drive hit-testing off the same decimated point
    set (SPEC 7.1/§10.7 -- decimated-set parity is the *caller's*
    responsibility; this only reports what happened).

    Deliberately keyed by the GLE dataset name rather than an
    ``(axes_index, series_attr, series_index)`` triple like
    :class:`~gleplot.sources.DanglingSourceRef`: the dataset name is already
    the join key a caller needs, since it is what appears in the generated
    script it is about to compile. Threading full series identity through
    every ``add_line``/``add_errorbar_series`` call site was judged not worth
    the extra surface for this first cut; add it if a consumer needs it.

    Attributes
    ----------
    dataset : str
        The GLE dataset name the clause was appended to (e.g. ``'d3'``).
    label : str or None
        The series' legend label, when it has one.
    factor : int
        The ``deresolve`` factor applied (always > 1).
    original_points : int
        Row count of the series before decimation.
    """

    dataset: str
    label: Optional[str]
    factor: int
    original_points: int


@dataclass(frozen=True)
class DecimationCandidate:
    """One series that has already cleared the ``preview_decimation``
    eligibility gate, offered to a :data:`DecimationPolicy` callable so it
    can pick that series' factor.

    Construction implies eligibility: a candidate is only ever built for a
    line/scatter series (the only kinds :meth:`GLEWriter._deresolve_clause`
    is called for) that has already met
    :attr:`~GLEWriter.MIN_DERESOLVE_POINTS`. A policy callable never has to
    re-check kind or point count -- it only has to *choose a factor*, which
    is the one decision that genuinely varies per series (see the mixed
    1k-curve / 500k-trace motivation on :data:`DecimationPolicy`).

    Attributes
    ----------
    dataset : str
        The GLE dataset name this series will be emitted as (e.g. ``'d3'``).
        Assigned by the writer during emission -- a policy can read it back
        for logging/reporting, but should not expect to know it in advance
        (see :data:`DecimationPolicy`'s note on why the ``Mapping`` shape
        keys on ``label`` instead).
    label : str or None
        The series' legend label, when it has one.
    n_points : int
        Row count of the series before decimation.
    kind : str
        ``'line'`` or ``'scatter'`` -- the only two kinds a candidate is
        ever built for. Exposed so a policy can, for example, thin scatter
        series more aggressively than lines of the same size.
    """

    dataset: str
    label: Optional[str]
    n_points: int
    kind: str


#: A ``preview_decimation`` argument, in any of three shapes:
#:
#: - ``int``: one factor for every eligible series (G7's original shape;
#:   byte-for-byte unchanged -- see :meth:`GLEWriter._deresolve_clause`).
#: - ``Mapping[Optional[str], int]``: per-series factors keyed by the
#:   series' ``label``. Labels are the only identifier a figure-authoring
#:   caller can name a series by *before* generation -- dataset names
#:   (``'d1'``, ``'d2'``, ...) are assigned by the writer during emission,
#:   so a caller cannot know them ahead of time, and re-deriving them would
#:   mean duplicating the writer's own axes/series-class/list-order walk
#:   (:func:`resolve_figure`'s docstring). A label absent from the mapping
#:   (including the ``None`` key, for unlabeled series) is simply left
#:   undecimated -- opt-in per series, not a fallback factor.
#: - ``Callable[[DecimationCandidate], Optional[int]]``: the general case,
#:   and the recommended shape for the motivating problem (a figure mixing
#:   a 1k-point curve with a 500k-point trace, where a single figure-wide
#:   factor sized off the smallest series leaves the large one entirely
#:   undecimated -- see G7's caller in GLEstudio). A callable can compute a
#:   factor from :attr:`DecimationCandidate.n_points` directly (e.g.
#:   ``max(1, n_points // target)``), vary it by
#:   :attr:`~DecimationCandidate.kind`, or fall back to the same
#:   label-keyed lookup the ``Mapping`` shape offers as sugar. Returning
#:   ``None`` (or ``<= 1``) exempts that one series, the same as a int
#:   policy of ``1`` exempts every series.
#:
#: All three shapes are consulted only for series that already pass the
#: unchanged eligibility gate (line/scatter kind, >=
#: :attr:`GLEWriter.MIN_DERESOLVE_POINTS` rows) -- a policy never sees, and
#: can never opt in, an errorbar or bar series.
DecimationPolicy = Union[
    int, Mapping[Optional[str], int], Callable[[DecimationCandidate], Optional[int]]
]


@dataclass(frozen=True)
class KeyOptions:
    """One axes' legend, as the options of the GLE key that draws it.

    Built from the ``Axes.legend_*`` state. ``position`` is a long or short
    key position (``None`` = the graph config's); ``fontsize`` is in points
    (``None`` = the current ``set hei``); ``spacing`` maps a matplotlib
    spacing name in :data:`LEGEND_SPACING_TO_KEY` to font-size units;
    ``anchor`` is the axes-fraction point the ``position`` corner sits on;
    ``labelcolor`` is a GLE colour for every entry's text. The last two exist
    only in a ``begin key`` block.
    """

    position: Optional[str] = None
    fontsize: Optional[float] = None
    frameon: bool = True
    offset: Optional[Tuple[float, float]] = None
    compact: bool = False
    background: Optional[str] = None
    spacing: Mapping[str, float] = field(default_factory=dict)
    anchor: Optional[Tuple[float, float]] = None
    labelcolor: Optional[str] = None


def legend_column_breaks(n_entries: int, ncol: int) -> Set[int]:
    """1-based entry counts after which to emit ``key separator``.

    Same split as matplotlib's ``np.array_split`` of the entry list: columns
    are consecutive groups, and the first ``n % ncol`` columns are one entry
    longer. A requested ``ncol`` larger than the entry count collapses to one
    entry per column, which is what that split does too. GLE's ``key
    separator`` (``do_key`` in ``graph.cpp``) starts a new column at that
    point in the dataset order, so the breaks have to fall between entries
    and never before the first or after the last.
    """
    if ncol <= 1 or n_entries <= 1:
        return set()
    ncol = min(int(ncol), int(n_entries))
    base, extra = divmod(int(n_entries), ncol)
    sizes = [base + (1 if i < extra else 0) for i in range(ncol)]
    breaks: Set[int] = set()
    acc = 0
    for size in sizes[:-1]:
        acc += size
        breaks.add(acc)
    return breaks


def legend_corner(position: str) -> Tuple[float, float]:
    """The figure fractions of the page corner a key ``position`` names.

    ``position`` is a long or short key position: ``'top center'`` is
    ``(0.5, 1.0)``. This is where ``Figure.legend(loc=...)`` anchors its
    legend when no ``bbox_to_anchor`` is given.
    """
    words = KEY_POSITIONS_SHORT_TO_LONG.get(position, position).split()
    x = 0.0 if "left" in words else 1.0 if "right" in words else 0.5
    y = 1.0 if "top" in words else 0.0 if "bottom" in words else 0.5
    return (x, y)


def _warn_keyword_form(name: str, series_class: str, method: str) -> None:
    """Deprecation warning for a keyword form of a series entry point."""
    warn_external(
        f"GLEWriter.{name}() is deprecated and will be removed in a future major "
        f"release. Build a gleplot.series.{series_class} and call "
        f"GLEWriter.{method}(series) instead.",
        DeprecationWarning,
    )


class GLEWriter:
    """Writer for GLE script files.

    Parameters
    ----------
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (8, 6)
    dpi : int, optional
        Dots per inch for PNG output. Default: 100
    style : GLEStyleConfig, optional
        Style configuration. If None, a COPY of ``GlobalConfig.style`` is
        taken at construction time (see :class:`gleplot.figure.Figure`'s
        "Global defaults are copied, not shared" note -- same rule here).
    graph : GLEGraphConfig, optional
        Graph configuration. If None, a COPY of ``GlobalConfig.graph`` is
        taken at construction time (same note).
    marker : GLEMarkerConfig, optional
        Marker configuration. If None, a COPY of ``GlobalConfig.marker`` is
        taken at construction time (same note).
    preview_decimation : DecimationPolicy, optional
        Preview-only ``deresolve`` factor (SPEC 6.1/10.7), or ``None`` (the
        default) for today's byte-identical emission. Either a single ``int``
        applied to every eligible series (the original G7 shape), a
        ``Mapping[Optional[str], int]`` keyed by series label, or a
        ``Callable[[DecimationCandidate], Optional[int]]`` for a factor
        computed per series -- see :data:`DecimationPolicy` for the full
        contract and why each shape looks the way it does. See
        :meth:`_deresolve_clause` for the eligibility rule and
        :attr:`decimation_report` for what a caller gets back. Generation-time
        only -- never read from or written to the figure, so ``to_dict``/
        ``from_dict`` and the saved ``.gle`` are untouched (snapshot
        discipline: a preview copy may decimate, the document never does).
    """

    #: A series needs at least this many rows before ``preview_decimation``
    #: touches it. Below this, GLE's own per-point draw cost is a few ms --
    #: not worth measuring -- so decimating would only reshape a small
    #: series's line/markers for zero compile-time benefit, and would change
    #: emitted bytes on figures nobody asked to speed up. Chosen well under
    #: the SPEC-cited "~10x speedup at 200k points" measurement, since a
    #: series in the low thousands already costs enough to be worth thinning
    #: in a fast throwaway preview compile.
    MIN_DERESOLVE_POINTS = 1000

    def __init__(
        self,
        figsize: Tuple[float, float] = (8, 6),
        dpi: int = 100,
        style: Optional[GLEStyleConfig] = None,
        graph: Optional[GLEGraphConfig] = None,
        marker: Optional[GLEMarkerConfig] = None,
        preview_decimation: Optional[DecimationPolicy] = None,
    ):
        """Initialize GLE writer with optional configuration objects."""
        self.figsize = figsize
        self.dpi = dpi
        # Convert inches to cm (GLE uses cm)
        self.width_cm = inches_to_cm(figsize[0])
        self.height_cm = inches_to_cm(figsize[1])

        # Get configuration (fall back to global defaults). When no explicit
        # config object is given, copy the global default instead of holding
        # the ``GlobalConfig`` singleton by reference -- see the identical
        # reasoning, including the "explicit config is still by reference"
        # carve-out, in ``Figure.__init__`` (figure.py). GLEWriter is
        # normally handed an already figure-owned config by
        # ``Figure._generate_gle_lines``; this fallback only matters when a
        # writer is built directly, e.g. in tests.
        self.style = style if style is not None else replace(GlobalConfig.get_style())
        self.graph = graph if graph is not None else replace(GlobalConfig.get_graph())
        self.marker = (
            marker if marker is not None else replace(GlobalConfig.get_marker())
        )

        self.lines_gle: List[str] = []  # GLE script lines
        self.data_files: Dict[str, Any] = {}  # {filename: data_content}
        # Sidecars shared by several provider-backed series, keyed by
        # filename. Their content is only complete once every series has
        # contributed, so they are rendered into ``data_files`` by
        # :meth:`finalize_shared_sidecars` at the end of the write.
        self._shared_sidecars: Dict[str, _SharedSidecar] = {}
        # Each sidecar an inline series wrote, as (columns, header names,
        # column keys), so a second series naming the same file is merged
        # into it rather than overwriting it (see _write_inline_columns).
        self._inline_sidecars: Dict[str, _InlineSidecar] = {}
        # Raw-content sidecars (heatmap/contour ``.z`` grids and scattered
        # ``points.dat`` triples). They are written like any data file but are
        # NOT columnar imports, so they are excluded from the ``import-data``
        # metadata list (see Figure._build_metadata_dict).
        self.raw_sidecars: set = set()
        self.dataset_index = (
            1  # Counter for unique dataset names (d1, d2, d3, ...) - GLE is 1-indexed
        )
        # Dataset numbers the raw GLE kept in the current graph block defines
        # (reserve_datasets); _new_dataset skips them. GLE clears its datasets
        # at 'begin graph', so end_graph clears these.
        self._reserved_datasets: Set[int] = set()
        # id of each series written as one dataset -> the raw (unshifted) name
        # it was given, for the ``let`` of a DerivedSeries that reads it.
        self._dataset_names: Dict[int, str] = {}
        # Column breaks for the graph key, as 1-based entry counts. Empty
        # unless this write is showing a legend with ncol > 1. Counted by
        # _finish_legend_entry as each real key label is emitted, in the
        # same order Figure._count_legend_entries walked.
        self._legend_breaks: Set[int] = set()
        self._legend_entry_count = 0
        # A ``begin key`` queued for the graph that is about to close.
        # Flushed by end_graph, immediately after ``end graph``, because
        # GLE positions that block against the graph that just ended
        # (``graph_x1``/``graph_y2`` in key.cpp). Cleared on flush so a
        # later subplot cannot inherit it.
        self._external_legend: Optional[List[str]] = None
        # The GLE string expression that is the key text of each model fit
        # whose label shows its results, by id of the series. GLE evaluates
        # an in-graph key before the fit runs, so only the ``begin key``
        # after ``end graph`` shows the values. The count numbers the fits'
        # result variables, which are global to the script.
        self._fit_keys: Dict[int, str] = {}
        self._fit_result_count = 0
        self._pending_graph_text_lines: List[str] = []
        # True inside the graph block of a polar axes (add_polar_frame): its
        # curves are drawn through the polar ``let`` (see _polar_dataset).
        self._polar_graph = False
        # Annotation arrows emitted so far: numbers the GLE object names
        # (``annN`` box, ``annN_xy`` tip) that ``join`` connects. Names are
        # page-global in GLE, so the count runs across every graph.
        self._annotation_count = 0
        # Guide subs (gleplot.guides) this write actually called, and where
        # their definitions belong in the script. Populated as the draw calls
        # go out and resolved by finalize_guide_subs, because which guides
        # take the draw form is not known until each axes' limits are.
        self.used_guide_subs: Set[str] = set()
        self._sub_defs_mark: int = 0
        # The palette sub each contourf heatmap written so far colours with,
        # by its data file: gleplot_contourf1, 2, ... in writing order.
        self._contourf_subs: Dict[str, str] = {}
        # Which axes of the graph being written are logarithmic, as the last
        # add_axes call set them (see _add_sized_scatter).
        self._log_axes: Dict[str, bool] = {}
        # Sticky GLE interpreter state as far as add_text_annotation is concerned: 'set
        # hei'/'set color'/'set just' persist across `write` statements until
        # changed again (real GLE semantics -- see recognizer._try_one_text,
        # the read-side counterpart). Tracking the currently-active emitted
        # value here lets add_text_annotation skip a redundant 'set ...' line when a
        # later text asks for the same value already in effect, instead of
        # restating it. Seeded with the preamble's 'set hei' (already emitted
        # unconditionally by add_preamble) so the first add_text_annotation call also
        # skips a redundant 'set hei' when its fontsize matches the style
        # default.
        self._text_state_hei_cm: Optional[str] = self._format_number(
            fontsize_pt_to_cm(self.style.fontsize)
        )
        self._text_state_color: str = "BLACK"
        self._text_state_just: Optional[str] = "left"

        # Preview-only deresolve decimation (G7; SPEC 6.1/10.7). Per-call,
        # never persisted: see the class docstring and _deresolve_clause.
        self._preview_decimation = preview_decimation
        #: Every series this write actually appended a ``deresolve`` clause
        #: to. Empty whenever ``preview_decimation`` is None/<=1, or when no
        #: eligible series met :attr:`MIN_DERESOLVE_POINTS` -- including the
        #: default (no-argument) call, so the default path's report is always
        #: ``[]`` alongside its byte-identical script.
        self.decimation_report: List[DecimationRecord] = []

    @staticmethod
    def _data_read_clause(series: Series) -> str:
        """`` ignore n comment "c" numrows m`` for a file series' ``data`` line.

        Each option is written only when the series has it. The comment
        marker is always quoted: bare, ``!`` would start a script comment
        and ``;`` would end the statement. A marker recovered from a
        single-quoted GLE string may hold ``"``; it keeps single quotes.
        """
        parts = []
        if "skiprows" in series:
            parts.append(f"ignore {int(series['skiprows'])}")
        if "comment" in series:
            comment = str(series["comment"])
            quote = "'" if '"' in comment else '"'
            parts.append(f"comment {quote}{comment}{quote}")
        if "max_rows" in series:
            parts.append(f"numrows {int(series['max_rows'])}")
        return "".join(" " + part for part in parts)

    def _dataset_qualifier_clause(self, series: Series, marked_line: bool) -> str:
        """`` mdist m deresolve N [average] xmin a ...`` for a ``dN`` line.

        Each qualifier is written only when the series has it. A marked line
        (``marked_line``) without its own ``mdist`` takes the figure's
        ``GLEMarkerConfig.mdist``. GLE reads ``average`` only as the token
        straight after the ``deresolve`` count (``graph2.cpp``).
        """
        parts = []
        mdist = series.get("mdist")
        if mdist is None and marked_line:
            mdist = self.marker.mdist
        if mdist is not None:
            parts.append(f"mdist {self._format_number(float(mdist))}")
        if "deresolve" in series:
            parts.append(f"deresolve {int(series['deresolve'])}")
            if series.get("deresolve_average"):
                parts.append("average")
        for name in ("xmin", "xmax", "ymin", "ymax"):
            if name in series:
                parts.append(f"{name} {self._format_number(float(series[name]))}")
        return "".join(" " + part for part in parts)

    def _deresolve_clause(
        self, dataset_name: str, label: Optional[str], n_points: int, kind: str
    ) -> str:
        """A trailing `` deresolve N`` clause for a ``dN`` line, or ``""``.

        Applies only to series kinds whose GLE draw path actually consults
        it -- verified against GLE 4.3.10 source (``graph2.cpp``) and by
        compiling small fixtures and diffing the emitted PostScript:

        - **line/steps/fsteps/hist/impulses/scatter (marker-only)**: drawn
          through ``transform_data()``, which applies ``deresolve`` before
          drawing. Confirmed: a 10-point marker-only dataset with
          ``deresolve 3`` draws 5 markers (points 0,3,6,9 plus GLE's
          always-keep-the-last-point rule -- 9 repeated) versus 10 without.
          This is the only family :meth:`add_line` calls this for.
        - **errorbar (`err`/`errup`/`errdown`/`herr`/...)**: intentionally
          EXCLUDED. ``draw_err`` -> ``getErrorBarData`` builds the whisker
          geometry straight from the dataset's raw, undecimated arrays --
          it never calls ``transform_data``. Compiling an err-only dataset
          with and without ``deresolve`` produced byte-identical PostScript
          (aside from the ``%%Title`` comment). Emitting ``deresolve`` on an
          errorbar series' main dataset would thin its markers/line while
          leaving every whisker in place -- a misleading, broken-looking
          preview for no compile-time win on the whiskers themselves -- so
          :meth:`add_errorbar_series` never calls this.
        - **bar (`bar dN fill ...`, the graph-level statement
          :meth:`add_bar` emits)**: also EXCLUDED. ``drawBar`` reads
          ``GLEDataPairs(toDataSet)`` directly from the raw dataset, bypassing
          ``transform_data`` entirely. Compiling identical ``bar`` fixtures
          with and without a prior ``dN deresolve 3`` on the bar's dataset
          produced byte-identical PostScript. (GLE's OTHER, unrelated bar
          mode -- the per-dataset ``dn ... bar`` line_mode -- does go through
          ``transform_data`` via ``GLEGraphPartLines``, but gleplot's
          ``BarSeries`` never emits that form, so it is moot here.)
        - **fill (`fill dA,dB color ...`)**: NOT wired up by this cut, even
          though ``drawFill`` -> ``transform_data`` means GLE itself would
          honor ``deresolve`` on the two boundary datasets. The two
          datasets a fill references are not symmetric: one is commonly a
          ``let``-derived offset copy that would need the SAME factor
          applied for the polygon to stay a consistent shape (decimating
          only one boundary produces a warped fill), and :meth:`add_fill`
          does not currently track a shared row count/eligibility across
          both sides. Left for a follow-up if fill-heavy previews turn out
          to need it.

        Order within the ``dN`` line does not matter to GLE's parser (the
        per-dataset keyword loop accepts ``line``/``marker``/``deresolve``/
        ``key`` in any order -- verified by compiling both orderings and
        diffing identical PostScript output), so this is always appended
        last for a minimal, single-clause diff against the undecorated line.

        ``kind`` (``'line'`` or ``'scatter'`` -- :meth:`add_line` is the
        only caller, for exactly these two families) is not used to decide
        eligibility here; it is purely payload for a callable
        :data:`DecimationPolicy`'s :class:`DecimationCandidate`, so a policy
        can vary its factor by kind if it wants to.
        """
        policy = self._preview_decimation
        # ``not policy`` is the ``None``/``0``/empty-mapping "no policy at
        # all" case -- identical short-circuit to the original int-only
        # check (``not factor``), so the int path's byte-for-byte output is
        # unaffected. The eligibility gate (kind, via the caller; row count,
        # here) is checked before a Mapping/Callable policy is ever
        # consulted, per DecimationPolicy's contract.
        if not policy or n_points < self.MIN_DERESOLVE_POINTS:
            return ""

        factor: Optional[int]
        if isinstance(policy, int):
            factor = policy
        elif isinstance(policy, Mapping):
            factor = policy.get(label)
        elif callable(policy):
            candidate = DecimationCandidate(
                dataset=dataset_name, label=label, n_points=n_points, kind=kind
            )
            factor = policy(candidate)
        else:
            raise TypeError(
                "preview_decimation must be an int, a "
                "Mapping[Optional[str], int], or a "
                "Callable[[DecimationCandidate], Optional[int]]; got "
                f"{type(policy).__name__!r}"
            )

        if not factor or factor <= 1:
            return ""
        self.decimation_report.append(
            DecimationRecord(
                dataset=dataset_name,
                label=label,
                factor=factor,
                original_points=n_points,
            )
        )
        return f" deresolve {factor}"

    def add_preamble(
        self,
        include_graph_begin: bool = True,
        metadata_lines: Optional[List[str]] = None,
        passthrough_header: Optional[List[str]] = None,
        passthrough_before_hei: Optional[List[str]] = None,
        page_box: bool = False,
    ):
        """Add GLE preamble.

        Includes:
        - Page size setup
        - Font configuration (from style config)
        - Line cap, join and dash length, and LaTeX labels (from style
          config, when set)
        - Optionally begins the first graph block

        Parameters
        ----------
        include_graph_begin : bool
            If True (default), appends 'begin graph' for single-plot
            backward compatibility. Set False for multi-subplot layout.
        metadata_lines : list of str, optional
            The full ``! gleplot-meta-begin``...``! gleplot-meta-end`` block
            (as produced by :func:`gleplot.parser.metadata.emit_metadata`),
            inserted immediately after the two header comment lines and
            before the ``size`` line. Omitted entirely when falsy, so
            figures with nothing to record produce no metadata block.
        passthrough_header : list of str, optional
            Raw lines recovered from a parsed ``.gle`` file that must be
            re-emitted verbatim right after the standard preamble (after
            'set hei ...' + the blank line) and before the first graph
            block/amove. Omitted entirely when falsy (no blank-line churn).
        passthrough_before_hei : list of str, optional
            Raw lines recovered from a parsed ``.gle`` file that sat, in the
            original, between a recognized ``size``/``set font`` and a
            recognized ``set hei`` -- almost always empty. ``hei`` is a
            length in GLE's CURRENT user units, so a preceding CTM-affecting
            statement (``scale .6 .8``, a page-level ``scale``/``rotate``)
            changes what the writer's own ``set hei`` line actually renders
            as; unlike ``passthrough_header``, this content is re-emitted
            BEFORE 'set hei', reproducing that original order instead of
            always putting the writer's own preamble first (see
            ``gleplot.parser.recognizer._parse_preamble``, the only producer
            of this bucket, and its own ``clip.gle`` finding). Omitted
            entirely when falsy, so the overwhelming majority of figures
            (nothing between size/font and hei) emit byte-identically to
            before this parameter existed.
        page_box : bool, optional
            GLE's page-level ``size w h box`` outline modifier (see
            :attr:`gleplot.figure.Figure.page_box`): draws a border around
            the whole page. False (the default) omits the trailing ``box``
            token entirely, matching every figure's output before this
            parameter existed.
        """
        self.lines_gle.extend(
            [
                "! GLE graphics file",
                "! Generated by gleplot",
            ]
        )
        if metadata_lines:
            self.lines_gle.extend(metadata_lines)
        size_line = (
            f"size {self._format_number(self.width_cm)} "
            f"{self._format_number(self.height_cm)}"
        )
        if page_box:
            size_line += " box"
        self.lines_gle.extend(["", size_line])
        # Only set font if explicitly specified
        if self.style.font:
            self.lines_gle.append(f"set font {self.style.font}")
        # Page-level state that every later stroke inherits; 'dashlen' must
        # precede the first 'lstyle' that should use it.
        if self.style.line_cap is not None:
            self.lines_gle.append(f"set cap {self.style.line_cap}")
        if self.style.line_join is not None:
            self.lines_gle.append(f"set join {self.style.line_join}")
        if self.style.dashlen is not None:
            # Not _format_number: its 6 digits would alter a hand-written
            # value on re-save, and it writes a tiny length as 0.
            self.lines_gle.append(f"set dashlen {float(self.style.dashlen):.15g}")
        if self.style.usetex:
            self.lines_gle.append("set texlabels 1")
        if passthrough_before_hei:
            self.lines_gle.extend(passthrough_before_hei)
        self.lines_gle.extend(
            [
                f"set hei {self._format_number(fontsize_pt_to_cm(self.style.fontsize))}",
                "",
            ]
        )
        if passthrough_header:
            self.lines_gle.extend(passthrough_header)
        if include_graph_begin:
            self.lines_gle.append("begin graph")

    def begin_graph(self):
        """Open a new graph block.

        Used in multi-subplot layouts. Each graph block must be closed
        with end_graph().
        """
        self.lines_gle.append("begin graph")
        self._polar_graph = False

    def end_graph(self, passthrough: Optional[List[str]] = None):
        """Close the current graph block.

        Parameters
        ----------
        passthrough : list of str, optional
            Raw lines recovered from a parsed ``.gle`` file that belong
            inside this graph block; emitted verbatim immediately before
            'end graph'. Omitted entirely when falsy (no blank-line churn).

        Notes
        -----
        The deferred graph-data-coordinate text queued by
        :meth:`add_text_annotation` (``_pending_graph_text_lines``) is flushed
        here, AFTER 'end graph' -- that is deliberate (GLE's ``xg()``/``yg()`` need the graph that just
        closed) but it means any 'set color'/'set hei'/'set just' the text
        needed is emitted at the PAGE level, where it is sticky interpreter
        state exactly like the broken-axis seam decoration (see the comment
        above :meth:`add_break_divider`). Left unguarded, a coloured text
        element ending one panel would leak its colour into the axes/ticks
        of the NEXT 'begin graph' block, which draws them with whatever
        colour is currently ambient. The flush is therefore wrapped in
        gsave/grestore, same idiom as the seam decoration, so the colour
        (and height/justification) reverts to ambient the moment this
        panel's text is done -- and the writer's own sticky-state trackers
        are reset alongside it (see ``_text_state_*`` below), since grestore
        changes the REAL GLE state but not this Python-side bookkeeping.
        """
        if passthrough:
            self.lines_gle.extend(passthrough)
        self.lines_gle.append("end graph")
        self._reserved_datasets = set()
        if self._external_legend:
            # Before the deferred ``xg()`` text. ``draw_key`` saves and
            # restores the current point and does not move the graph box,
            # so the text that follows still addresses this graph.
            self.lines_gle.extend(self._external_legend)
            self._external_legend = None
        if self._pending_graph_text_lines:
            self.lines_gle.append("gsave")
            self.lines_gle.extend(self._pending_graph_text_lines)
            self.lines_gle.append("grestore")
            self._pending_graph_text_lines = []
            # grestore reverted the ambient GLE state to what it was before
            # this panel's gsave (i.e. the script-start default: BLACK,
            # style-default height, left-justified) -- resync the sticky
            # trackers to match, or the NEXT panel's add_text_annotation calls would
            # wrongly skip restating a 'set color'/'set hei'/'set just' that
            # real GLE no longer has in effect.
            self._text_state_hei_cm = self._format_number(
                fontsize_pt_to_cm(self.style.fontsize)
            )
            self._text_state_color = "BLACK"
            self._text_state_just = "left"

    def add_amove(self, x_cm: float, y_cm: float):
        """Add absolute move command to position the next graph.

        In GLE, 'amove x y' positions the drawing cursor at absolute
        coordinates (in cm) from the bottom-left of the page.

        Parameters
        ----------
        x_cm : float
            X position in cm from the left edge of the page.
        y_cm : float
            Y position in cm from the bottom edge of the page.
        """
        self.lines_gle.append(
            f"amove {self._format_number(x_cm)} {self._format_number(y_cm)}"
        )

    def add_graph_size(
        self,
        width_cm: Optional[float] = None,
        height_cm: Optional[float] = None,
        force_size: bool = False,
    ):
        """Set graph dimensions and scaling.

        Uses the configured scale_mode (auto, fixed, or fullsize).

        Parameters
        ----------
        width_cm : float, optional
            Graph width in cm. Used if scale_mode is 'fixed' or force_size is True.
        height_cm : float, optional
            Graph height in cm. Used if scale_mode is 'fixed' or force_size is True.
        force_size : bool
            If True, always emit the size command regardless of scale_mode.
            This is how every placed graph is emitted: ``size w h`` +
            ``scale 1 1`` makes the axis frame fill the graph box exactly, so
            the box IS the frame rectangle (SPEC 3.3) -- invertible on parse,
            and letting adjacent subplots' axes touch.

        Notes
        -----
        Without ``force_size`` and without dimensions this falls through to
        ``scale auto`` (GLE fits the graph, labels included, to the page).
        Since metadata v2 that path is reached only by a figure with no axes
        at all; every placed graph is emitted with ``force_size=True`` from a
        rect computed by :meth:`Figure._layout_rects`.
        """
        if force_size and width_cm is not None and height_cm is not None:
            self.lines_gle.append(
                f"    size {self._format_number(width_cm)} {self._format_number(height_cm)}"
            )
            self.lines_gle.append(
                "    scale 1 1"
            )  # Fill entire graph box for tight subplot layout
        elif (
            self.graph.scale_mode == "fixed"
            and width_cm is not None
            and height_cm is not None
        ):
            self.lines_gle.append(
                f"    size {self._format_number(width_cm)} {self._format_number(height_cm)}"
            )
            self.lines_gle.append("    scale 1 1")
        elif self.graph.scale_mode == "fullsize":
            self.lines_gle.append("    fullsize")
        else:  # 'auto' - default
            # Auto-size and center axes within graph box
            self.lines_gle.append("    scale auto")

    def add_graph_geometry_passthrough(self, lines: Sequence[str]):
        """Emit recovered graph-geometry statements verbatim.

        Used for GLE geometry that is real but not invertible into a
        placement rect (``fullsize``, ``scale 0.8 0.8``, a bare ``size w h``
        without the ``scale 1 1`` that would pin the frame). The lines are
        the original source lines, re-emitted in the geometry slot -- the
        first thing inside ``begin graph`` -- INSTEAD of this writer's own
        geometry line, so the figure re-saves byte-for-byte instead of being
        normalized to ``scale auto``.

        Parameters
        ----------
        lines : sequence of str
            ``Axes.geometry_passthrough``: raw source lines, in source
            order, with their original indentation and no trailing newline.
        """
        self.lines_gle.extend(lines)

    def add_math_mode(self) -> None:
        """GLE ``math``: the x and y axes cross at (0, 0).

        Call it before :meth:`add_axes`. ``math`` resets the axis offsets,
        ``symticks`` and x2/y2 ``on`` set before it, so the axis lines
        written after it can still override what it sets.
        """
        self.lines_gle.append("    math")

    def add_axes(
        self,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        y2label: Optional[str] = None,
        x2label: Optional[str] = None,
        title: Optional[str] = None,
        xlog: bool = False,
        ylog: bool = False,
        y2log: bool = False,
        x2log: bool = False,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
        y2min: Optional[float] = None,
        y2max: Optional[float] = None,
        x2min: Optional[float] = None,
        x2max: Optional[float] = None,
        show_xlabel: bool = True,
        show_ylabel: bool = True,
        show_xticks: bool = True,
        show_yticks: bool = True,
        remove_last_xtick: bool = False,
        remove_last_ytick: bool = False,
        remove_first_xtick: bool = False,
        remove_first_ytick: bool = False,
        xdticks: Optional[float] = None,
        ydticks: Optional[float] = None,
        xdsubticks: Optional[float] = None,
        ydsubticks: Optional[float] = None,
        xplaces: Optional[List[float]] = None,
        yplaces: Optional[List[float]] = None,
        xnames: Optional[List[str]] = None,
        ynames: Optional[List[str]] = None,
        xaxis_off: bool = False,
        yaxis_off: bool = False,
        x2axis_off: bool = False,
        y2axis_off: bool = False,
        frame_off: bool = False,
        xstyle: Optional[AxisStyle] = None,
        ystyle: Optional[AxisStyle] = None,
        y2style: Optional[AxisStyle] = None,
        x2style: Optional[AxisStyle] = None,
        x2_series: bool = False,
        title_size: Optional[float] = None,
        title_color: Optional[str] = None,
        title_dist: Optional[float] = None,
        title_font: Optional[str] = None,
    ):
        """Add axis configuration.

        Parameters
        ----------
        xlabel, ylabel : str, optional
            Axis labels
        y2label : str, optional
            Secondary y-axis (right) label
        x2label : str, optional
            Secondary x-axis (top) label
        title : str, optional
            Plot title
        xlog, ylog : bool
            Whether to use logarithmic scale
        y2log : bool
            Whether to use logarithmic scale for y2axis
        x2log : bool
            Whether to use logarithmic scale for x2axis
        xmin, xmax, ymin, ymax : float, optional
            Axis limits. A DESCENDING pair inverts the axis, as it does in
            matplotlib; see :meth:`_axis_direction`.
        y2min, y2max : float, optional
            Secondary y-axis limits
        x2min, x2max : float, optional
            Secondary x-axis limits
        show_xlabel, show_ylabel : bool
            Whether to display axis TITLES (for shared axes)
        show_xticks, show_yticks : bool
            Whether to display axis tick LABELS/NUMBERS (for shared axes)
        remove_last_xtick, remove_last_ytick : bool
            Whether to remove the last tick label using GLE's nolast command
            (used when subplots touch to avoid overlapping labels)
        remove_first_xtick, remove_first_ytick : bool
            Whether to remove the first tick label using GLE's nofirst command
            (used when subplots touch to avoid overlapping labels)
        xdticks, ydticks : float, optional
            Major tick interval (GLE ``dticks``). Needed per-segment on a
            broken axis, where the two segments cover wildly different ranges
            and GLE's automatic choice would collide at the seam.
        xdsubticks, ydsubticks : float, optional
            Minor tick interval (GLE ``dsubticks``).
        xplaces, yplaces : list of float, optional
            Explicit tick positions (GLE ``xplaces``/``yplaces``), emitted as
            their own statement. Overrides the automatic/``dticks`` placement.
        xnames, ynames : list of str, optional
            Tick labels to go with ``xplaces``/``yplaces`` (GLE
            ``xnames``/``ynames``). Must be the same length as the
            corresponding places list.
        xaxis_off, yaxis_off, x2axis_off, y2axis_off : bool
            Disable a single side of the graph frame entirely -- axis line,
            ticks and labels (GLE's ``off`` sub-command; ``x2``/``y2`` are the
            top/right sides GLE draws by default). This is what lets several
            graph blocks butt up against each other and read as one panel:
            the inner sides are switched off and the seam is drawn separately.
        frame_off : bool
            Hide every axis line and tick mark (``xside off``, ``yside off``,
            ``xticks off``, ``yticks off``; GLE copies them onto x2/y2) but
            keep the axes, and with them the graph title, which GLE draws
            with the top axis and ``x2axis off`` would hide.
        xstyle, ystyle, y2style, x2style : AxisStyle, optional
            Per-axis styling -- tick-label format, grid, axis-title and
            tick-label size/colour/angle. Omitted (or the default
            ``AxisStyle()``) emits nothing, so an unstyled figure is
            byte-identical to what gleplot wrote before styling existed.
            x2 has no grid of its own, the same as y2.
        x2_series : bool
            True when a dataset is drawn against the top scale. GLE copies
            ``xaxis log`` onto x2 (``do_axis_part_all``), so a linear top
            scale that actually carries data has to say ``x2axis lin``
            afterwards. A figure that never uses the top scale does not.
        title_size, title_color, title_dist, title_font : optional
            The graph title's ``hei`` (points), ``color``, ``dist`` (cm) and
            ``font`` -- GLE ``title "..." hei H color C font F dist D``. GLE's title belongs to
            the graph block, which is why gleplot models it per-axes and not
            per-figure.

        Raises
        ------
        ValueError
            If a ``*names`` list is given without, or of a different length
            to, its ``*places`` list.

        Notes
        -----
        Emission order inside the graph block matters to GLE, and the order
        here is: the ``title``/``*title`` texts, then per axis its ``xaxis``
        line, ``xplaces``/``xnames``, ``xlabels``, and its grid tick styling
        (``xticks``/``xsubticks``) -- x before y before y2, with ``x2axis``
        last, as before. New tokens on the ``xaxis`` line (``format``,
        ``angle``, ``grid``) go after ``dsubticks`` and before
        ``nofirst``/``nolast``/``off``.

        GLE's y2 and x2 tick labels are off unless ``y2labels on`` /
        ``x2labels on`` is given, so any tick-label property on that axis
        also emits the ``on``. So does any other sign the axis is
        configured (limits, log, or a title): GLE auto-enables the labels
        when a plotted dataset uses the axis, but not when the axis is
        only configured, which otherwise compiled with mirrored tick marks
        and no numbers.
        """
        if xnames is not None and (xplaces is None or len(xnames) != len(xplaces)):
            raise ValueError("xnames must be the same length as xplaces")
        if ynames is not None and (yplaces is None or len(ynames) != len(yplaces)):
            raise ValueError("ynames must be the same length as yplaces")
        xstyle = xstyle or _NO_STYLE
        ystyle = ystyle or _NO_STYLE
        y2style = y2style or _NO_STYLE
        x2style = x2style or _NO_STYLE
        if frame_off:
            # A hidden frame already hides every axis line.
            xstyle = replace(xstyle, side_off=None)
            ystyle = replace(ystyle, side_off=None)
        # GLE copies 'xside off' onto the top edge and 'yside off' onto the
        # right one (do_side), so an edge that is still drawn is switched
        # back on after it.
        if xstyle.side_off and not x2axis_off and not frame_off:
            x2style = replace(x2style, side_off=False)
        if ystyle.side_off and not y2axis_off and not frame_off:
            y2style = replace(y2style, side_off=False)
        self._log_axes = {"x": xlog, "y": ylog, "y2": y2log, "x2": x2log}
        if title:
            opts = self._text_options(title_size, title_color, title_dist, title_font)
            self.lines_gle.append(f'    title "{title}"{opts}')
        # show_xlabel/show_ylabel control the axis title (e.g. "Time (s)"),
        # not the tick marks.
        if show_xlabel:
            self._add_axis_title("x", xlabel, xstyle)
        if show_ylabel:
            self._add_axis_title("y", ylabel, ystyle)
        self._add_axis_title("y2", y2label, y2style)
        self._add_axis_title("x2", x2label, x2style)

        self._add_primary_axis(
            "x",
            xmin,
            xmax,
            log=xlog,
            dticks=xdticks,
            dsubticks=xdsubticks,
            style=xstyle,
            nofirst=remove_first_xtick,
            nolast=remove_last_xtick,
            off=xaxis_off,
            places=xplaces,
            names=xnames,
            show_ticks=show_xticks,
        )
        self._add_primary_axis(
            "y",
            ymin,
            ymax,
            log=ylog,
            dticks=ydticks,
            dsubticks=ydsubticks,
            style=ystyle,
            nofirst=remove_first_ytick,
            nolast=remove_last_ytick,
            off=yaxis_off,
            places=yplaces,
            names=ynames,
            show_ticks=show_yticks,
        )
        self._add_y2_axis(
            y2min,
            y2max,
            log=y2log,
            label=y2label,
            style=y2style,
            off=y2axis_off,
            yaxis_off=yaxis_off,
        )
        self._add_x2_axis(
            x2min,
            x2max,
            log=x2log,
            label=x2label,
            style=x2style,
            off=x2axis_off,
            xaxis_off=xaxis_off,
            xlog=xlog,
            x2_series=x2_series,
        )
        if frame_off:
            for prefix in ("x", "y"):
                self.lines_gle.append(f"    {prefix}side off")
            for prefix in ("x", "y"):
                self.lines_gle.append(f"    {prefix}ticks off")

    def _add_axis_title(
        self, prefix: str, label: Optional[str], style: AxisStyle
    ) -> None:
        """``xtitle "..."`` (and y/y2/x2 twins), when the label is set."""
        if label:
            opts = self._text_options(
                style.title_size, style.title_color, style.title_dist, style.title_font
            )
            self.lines_gle.append(f'    {prefix}title "{label}"{opts}')

    def _add_primary_axis(
        self,
        prefix: str,
        lo: Optional[float],
        hi: Optional[float],
        *,
        log: bool,
        dticks: Optional[float],
        dsubticks: Optional[float],
        style: AxisStyle,
        nofirst: bool,
        nolast: bool,
        off: bool,
        places: Optional[List[float]],
        names: Optional[List[str]],
        show_ticks: bool,
    ) -> None:
        """The ``xaxis``/``yaxis`` line, its places/names, labels and grid."""
        lo, hi, negate = self._axis_direction(lo, hi)
        bare = f"    {prefix}axis"
        cmd = bare
        cmd += self._axis_range(lo, hi, log)
        if log:
            cmd += " log"
        if negate:
            cmd += " negate"
        if dticks is not None:
            cmd += f" dticks {self._format_number(dticks)}"
        if dsubticks is not None:
            cmd += f" dsubticks {self._format_number(dsubticks)}"
        cmd += self._axis_style_tokens(style)
        if nofirst:
            cmd += " nofirst"  # Remove first tick label to prevent overlap
        if nolast:
            cmd += " nolast"  # Remove last tick label to prevent overlap
        if off:
            cmd += " off"
        if cmd != bare:
            self.lines_gle.append(cmd)

        if places is not None:
            self.lines_gle.append(
                f"    {prefix}places "
                + " ".join(self._format_number(v) for v in places)
            )
        if names is not None:
            self.lines_gle.append(
                f"    {prefix}names "
                + " ".join(f'"{self._escape_gle_string(n)}"' for n in names)
            )
        if style.noticks is not None:
            self.lines_gle.append(
                f"    {prefix}noticks "
                + " ".join(self._format_number(v) for v in style.noticks)
            )

        # Hide the tick labels if requested (but keep the ticks themselves),
        # or style them; styling labels that are switched off would be a no-op.
        if not show_ticks:
            self.lines_gle.append(f"    {prefix}labels off")
        else:
            self._add_tick_label_style(prefix, style)
        self._add_tick_mark_style(prefix, style)
        self._add_grid_style(prefix, style)
        self._add_axis_line_style(prefix, style)

    def _add_y2_axis(
        self,
        lo: Optional[float],
        hi: Optional[float],
        *,
        log: bool,
        label: Optional[str],
        style: AxisStyle,
        off: bool,
        yaxis_off: bool,
    ) -> None:
        """The ``y2axis`` line and ``y2labels on``, when y2 is configured.

        GLE mirrors the primary axis onto the opposite side by default, and
        that mirroring is what draws the closing edge of the box. Switching
        the primary axis off takes the mirror with it: ``yaxis ... off``
        silently removes the RIGHT-hand frame line too, even though nothing
        asked for it. That is a real bug for a broken-axis assembly, whose
        rightmost segment always has ``yaxis off`` (the y axis belongs to
        the leftmost segment) and always wants its outer edge drawn -- the
        panel otherwise renders open on the right and reads as clipped.
        Re-assert the mirror explicitly whenever the primary side is off
        and the mirror was not itself turned off.
        """
        lo, hi, negate = self._axis_direction(lo, hi)
        y2_on = yaxis_off and not off
        y2_styled = style is not _NO_STYLE and style != _NO_STYLE
        if lo is not None or hi is not None or log or off or y2_on or y2_styled:
            cmd = "    y2axis"
            cmd += self._axis_range(lo, hi, log)
            if log:
                cmd += " log"
            if negate:
                cmd += " negate"
            cmd += self._axis_style_tokens(style)
            if off:
                cmd += " off"
            elif y2_on:
                cmd += " on"
            if cmd != "    y2axis":
                self.lines_gle.append(cmd)
        # GLE draws no y2 tick labels unless asked (manual: "xlabels on ...
        # the default for the x and y axis, but not for the x2 and y2 axis"),
        # so a y2 format/hei/color/angle is inert without 'y2labels on'.
        # Emitting it is the only way those properties mean anything.
        #
        # GLE itself papers over this for a y2 axis that actually carries a
        # plotted series: GLEGraph::do_each_dataset_settings (graph2.cpp)
        # auto-clears label_off for whichever axis each in-use dataset is
        # assigned to, as long as the script never said 'y2labels on/off'
        # explicitly. That is real GLE behaviour, verified against the
        # 4.3.10 binary -- a y2 series with y2 limits and no styling already
        # renders its numbers with no help from gleplot.
        #
        # The case that auto-behaviour does NOT cover -- and which used to
        # render silently blank -- is a y2 axis configured but carrying no
        # dataset at all: explicit y2 limits/log-scale/title (``set_ylim``/
        # ``set_yscale``/``set_ylabel(axis='y2')``) with nothing plotted on
        # it. There is no dataset to trigger GLE's auto-enable, so the axis
        # compiled happily and drew mirrored tick marks with no numbers.
        # Emitting 'y2labels on' whenever the y2 axis is configured at all
        # (explicit limits, log scale or a title) fixes that case and is a
        # harmless, idempotent no-op for the already-working series case
        # (GLE has no "on but no numbers" state to disturb).
        y2_used = lo is not None or hi is not None or log or bool(label)
        if not off and (y2_used or style.has_tick_label_styling()):
            opts = self._text_options(style.label_size, style.label_color, None)
            self.lines_gle.append(f"    y2labels on{opts}")
        self._add_axis_line_style("y2", style)

    def _add_x2_axis(
        self,
        lo: Optional[float],
        hi: Optional[float],
        *,
        log: bool,
        label: Optional[str],
        style: AxisStyle,
        off: bool,
        xaxis_off: bool,
        xlog: bool,
        x2_series: bool,
    ) -> None:
        """The top scale: the ``x2axis`` line and ``x2labels on``.

        With nothing configured it stays exactly the broken-axis frame
        switch: ``x2axis off``, or ``x2axis on`` when the bottom axis is off
        and the top one is not. A data scale (limits, log,
        linear-vs-copied-log, styling) joins that same line, after the
        ``xaxis`` line, because GLE copies an ``xaxis`` command onto x2
        (manual: put the x2 settings after the x ones). ``log`` is copied
        even though ``min``/``max`` are not (``graph.cpp`` ``do_axis``: LOG
        ignores ``craxis``), so a linear top scale under a log bottom axis
        has to say ``lin``.
        """
        lo, hi, negate = self._axis_direction(lo, hi)
        x2_on = xaxis_off and not off
        # Tick-label styling only. ``title_dist`` is filled with the
        # figure's xlabel distance on every axis, including one that has
        # no top scale, so it must not count as x2 being in use -- that
        # would write ``x2axis lin`` onto every log-x figure.
        x2_tick_styled = style.has_tick_label_styling()
        x2_configured = (
            lo is not None
            or hi is not None
            or log
            or bool(label)
            or x2_tick_styled
            or x2_series
        )
        x2_lin = xlog and not log and x2_configured and not off
        if (
            lo is not None
            or hi is not None
            or log
            or x2_lin
            or off
            or x2_on
            or x2_tick_styled
        ):
            cmd = "    x2axis"
            cmd += self._axis_range(lo, hi, log)
            if log:
                cmd += " log"
            elif x2_lin:
                cmd += " lin"
            if negate:
                cmd += " negate"
            cmd += self._axis_style_tokens(style)
            if off:
                cmd += " off"
            elif x2_on:
                cmd += " on"
            if cmd != "    x2axis":
                self.lines_gle.append(cmd)
        x2_used = lo is not None or hi is not None or log or bool(label)
        if not off and (x2_used or style.has_tick_label_styling()):
            opts = self._text_options(style.label_size, style.label_color, None)
            self.lines_gle.append(f"    x2labels on{opts}")
        self._add_axis_line_style("x2", style)

    # -- axes styling helpers -------------------------------------------

    def _text_options(
        self,
        size: Optional[float] = None,
        color: Optional[str] = None,
        dist: Optional[float] = None,
        font: Optional[str] = None,
    ) -> str:
        """``[ hei H][ color C][ font F][ dist D]`` for a GLE title/labels command.

        Shared by ``title``, ``xtitle``/``ytitle``/``y2title``/``x2title`` and
        ``xlabels``/``ylabels``/``y2labels``/``x2labels``, which all take the same
        options in the same order (the manual's). gleplot sets ``font`` only
        on titles. ``size`` is in matplotlib points and
        becomes GLE's ``hei`` in cm; ``dist`` is already in cm (GLE's own
        unit for it). Returns ``''`` when nothing is set, so the caller can
        concatenate unconditionally.
        """
        out = ""
        if size is not None:
            out += f" hei {self._format_number(fontsize_pt_to_cm(float(size)))}"
        if color is not None:
            out += f" color {color}"
        if font is not None:
            out += f" font {font}"
        if dist is not None:
            out += f" dist {self._format_number(float(dist))}"
        return out

    def _axis_style_tokens(self, style: AxisStyle) -> str:
        """``[ format "F"][ angle A][ grid]`` and the tick placement tokens.

        These live on the axis command itself rather than in a statement of
        their own (manual: ``xaxis format``, ``xaxis angle``, ``xaxis
        grid``, ``xaxis nticks``/``ftick``/``shift``/``symticks``), so they
        are appended to the line the caller is already building.
        """
        out = ""
        if style.fmt is not None:
            out += f' format "{self._escape_gle_string(style.fmt)}"'
        if style.label_angle is not None:
            out += f" angle {self._format_number(float(style.label_angle))}"
        if style.grid is not None:
            out += " grid"
        if style.nticks is not None:
            out += f" nticks {int(style.nticks)}"
        if style.ftick is not None:
            out += f" ftick {self._format_number(float(style.ftick))}"
        if style.shift is not None:
            out += f" shift {self._format_number(float(style.shift))}"
        if style.symticks:
            out += " symticks"
        if style.nsubticks is not None:
            out += f" nsubticks {int(style.nsubticks)}"
        return out

    def _add_axis_line_style(self, prefix: str, style: AxisStyle) -> None:
        """``xside color C lwidth W off|on`` (and y/y2/x2 twins), when set.

        GLE copies an ``xside`` onto x2 and a ``yside`` onto y2, so the
        caller writes x and y before x2 and y2: a later ``x2side`` then
        restyles, or switches back on, the top line on its own.
        """
        opts = ""
        if style.side_color is not None:
            opts += f" color {style.side_color}"
        if style.side_lwidth is not None:
            width = linewidth_pt_to_cm(float(style.side_lwidth))
            opts += f" lwidth {self._format_number(width)}"
        if style.side_off is not None:
            opts += " off" if style.side_off else " on"
        if opts:
            self.lines_gle.append(f"    {prefix}side{opts}")

    @staticmethod
    def _dataset_axis_clause(xaxis: str = "x", yaxis: str = "y") -> str:
        """`` x2axis`` / `` y2axis`` for a dataset drawn on a secondary scale.

        GLE's ``dn`` keywords are order-independent. Both, when both are
        set, are written x2 then y2, which is the order in the manual's
        dual-scale example.
        """
        clause = ""
        if xaxis == "x2":
            clause += " x2axis"
        if yaxis == "y2":
            clause += " y2axis"
        return clause

    def _add_tick_label_style(self, prefix: str, style: AxisStyle) -> None:
        """``xlabels hei H color C log M`` (and y/y2/x2 twins), when set."""
        opts = self._text_options(style.label_size, style.label_color, None)
        if style.loglabels is not None:
            opts += f" log {style.loglabels}"
        if opts:
            self.lines_gle.append(f"    {prefix}labels{opts}")

    def _add_tick_mark_style(self, prefix: str, style: AxisStyle) -> None:
        """``xticks length L lwidth W color C`` and the ``xsubticks`` twin.

        GLE's ``length`` is cm, negative to point out of the frame, and
        under ``symticks`` drawn on each side, so it is half the model's
        length there. GLE has no outward default: an outward tick with no
        length gets matplotlib's (:data:`_MPL_TICK_SIZE`). A minor tick
        with no length is half the major one with the same sign, so it
        only needs a length when its direction differs. The minor line also
        carries ``on``/``off``.
        """
        symmetric = bool(style.symticks)
        major_length = style.tick_length
        if major_length is None and style.tick_direction == "out" and not symmetric:
            major_length = _MPL_TICK_SIZE["major"]
        major_out = major_length is not None and style.tick_direction == "out"
        major = self._tick_mark_options(
            major_length, major_out, symmetric, style.tick_width, style.tick_color
        )
        if major:
            self.lines_gle.append(f"    {prefix}ticks{major}")
        minor_length = style.subtick_length
        minor_out = style.subtick_direction == "out"
        if (
            minor_length is None
            and style.subtick_direction is not None
            and not symmetric
            and minor_out != major_out
        ):
            minor_length = _MPL_TICK_SIZE["minor"]
        minor = self._tick_mark_options(
            minor_length,
            minor_out,
            symmetric,
            style.subtick_width,
            style.subtick_color,
        )
        if style.minorticks is not None:
            minor = (" on" if style.minorticks else " off") + minor
        if minor:
            self.lines_gle.append(f"    {prefix}subticks{minor}")

    def _tick_mark_options(
        self,
        length: Optional[float],
        out: bool,
        symmetric: bool,
        width: Optional[float],
        color: Optional[str],
    ) -> str:
        """``[ length L][ lwidth W][ color C]`` from points."""
        result = ""
        if length is not None:
            cm = linewidth_pt_to_cm(float(length) / (2.0 if symmetric else 1.0))
            if out and cm:
                cm = -cm
            result += f" length {self._format_number(cm)}"
        if width is not None:
            result += f" lwidth {self._format_number(linewidth_pt_to_cm(float(width)))}"
        if color is not None:
            result += f" color {color}"
        return result

    def _add_grid_style(self, prefix: str, style: AxisStyle) -> None:
        """Tick styling for an axis whose grid is on, plus the subtick mode.

        GLE's grid lines are this axis' ticks stretched across the graph, so
        their style is ``xticks lstyle/lwidth/color`` -- which also restyles
        the ticks, as documented on :class:`AxisStyle`. ``grid='both'`` adds
        ``xsubticks on``, GLE's "grid lines at each subtick" mode (manual,
        Fig. "Different grid options").

        Subticks inherit only the tick **colour**, not ``lstyle``/``lwidth``
        (measured with GLE 4.3.10: ``xticks lstyle 3`` + ``xsubticks on``
        draws dashed main grid lines and SOLID subtick ones), so those two
        are repeated on the ``xsubticks`` clause -- as the manual's own
        "Various Settings" grid example does.

        Nothing is emitted when the grid is off: a bare ``xticks color ...``
        would restyle the ticks of a gridless axis, which is not what the
        model says.
        """
        if style.grid is None:
            return
        opts = ""
        if style.grid_lstyle is not None:
            opts += f" lstyle {int(style.grid_lstyle)}"
        if style.grid_lwidth is not None:
            width = linewidth_pt_to_cm(float(style.grid_lwidth))
            opts += f" lwidth {self._format_number(width)}"
        line_opts = opts
        if style.grid_color is not None:
            line_opts += f" color {style.grid_color}"
        if line_opts:
            self.lines_gle.append(f"    {prefix}ticks{line_opts}")
        if style.grid == "both":
            self.lines_gle.append(f"    {prefix}subticks on{opts}")

    # -- broken-axis seam decoration ------------------------------------
    #
    # These are emitted between two adjacent graph blocks, immediately after
    # the LEFT one's ``end graph``. GLE's ``xg()``/``yg()`` map data
    # coordinates to page cm for the graph that most recently ended, and
    # ``xgmin``/``xgmax``/``ygmin``/``ygmax`` hold that graph's data range --
    # the same mechanism the colorbar placement already relies on. Using them
    # (rather than the cm geometry gleplot computed) keeps the decoration
    # pinned to what GLE actually drew.
    #
    # Everything is wrapped in gsave/grestore: ``set lwidth``/``set color``
    # are sticky interpreter state in GLE and would otherwise leak into the
    # following graph block.

    def _seam_style(
        self, color: str, linewidth: Optional[float], lstyle: Optional[int]
    ) -> None:
        """``gsave`` and the colour, width and style of a broken-axis seam."""
        self.lines_gle.append("gsave")
        self.lines_gle.append(f"set color {color}")
        if linewidth is not None:
            self.lines_gle.append(
                f"set lwidth {self._format_number(linewidth_pt_to_cm(linewidth))}"
            )
        if lstyle is not None:
            self.lines_gle.append(f"set lstyle {int(lstyle)}")

    def add_break_divider(
        self,
        gap_cm: float,
        color: str = "BLACK",
        linewidth: Optional[float] = None,
        lstyle: Optional[int] = None,
    ):
        """Draw a single vertical rule down the seam between two segments.

        The rule sits at the centre of the gap, so it lands exactly on the
        join when ``gap_cm`` is 0.
        """
        offset = self._format_number(gap_cm / 2.0)
        self._seam_style(color, linewidth, lstyle)
        self.lines_gle.append(f"amove xg(xgmax)+{offset} yg(ygmin)")
        self.lines_gle.append(f"aline xg(xgmax)+{offset} yg(ygmax)")
        self.lines_gle.append("grestore")

    def add_break_marks(
        self,
        gap_cm: float,
        color: str = "BLACK",
        linewidth: Optional[float] = None,
        width_cm: float = 0.13,
        height_cm: float = 0.20,
        separation_cm: float = 0.06,
    ):
        """Draw the conventional double-slash break marks at the seam.

        Two short parallel strokes, leaning right, are drawn on the bottom
        axis line and two more on the top one, centred on the gap between the
        two segments. ``separation_cm`` is the half-distance between the pair
        of strokes; ``width_cm``/``height_cm`` are the half-extents of each
        stroke.
        """
        centre = f"xg(xgmax)+{self._format_number(gap_cm / 2.0)}"
        w = self._format_number(width_cm)
        h = self._format_number(height_cm)
        sep = self._format_number(separation_cm)

        self._seam_style(color, linewidth, 1)
        for side in ("ygmin", "ygmax"):
            for sign in ("-", "+"):
                self.lines_gle.append(f"amove {centre}{sign}{sep}-{w} yg({side})-{h}")
                self.lines_gle.append(f"aline {centre}{sign}{sep}+{w} yg({side})+{h}")
        self.lines_gle.append("grestore")

    def add_ybreak_divider(
        self,
        gap_cm: float,
        color: str = "BLACK",
        linewidth: Optional[float] = None,
        lstyle: Optional[int] = None,
    ):
        """Draw a single horizontal rule across the seam of a broken y-axis.

        The broken-y counterpart of :meth:`add_break_divider`, emitted after
        the LOWER segment's ``end graph``: the rule sits at the centre of the
        gap above its top edge.
        """
        offset = self._format_number(gap_cm / 2.0)
        self._seam_style(color, linewidth, lstyle)
        self.lines_gle.append(f"amove xg(xgmin) yg(ygmax)+{offset}")
        self.lines_gle.append(f"aline xg(xgmax) yg(ygmax)+{offset}")
        self.lines_gle.append("grestore")

    def add_ybreak_marks(
        self,
        gap_cm: float,
        color: str = "BLACK",
        linewidth: Optional[float] = None,
        width_cm: float = 0.20,
        height_cm: float = 0.13,
        separation_cm: float = 0.06,
    ):
        """Draw double-slash break marks across the seam of a broken y-axis.

        The broken-y counterpart of :meth:`add_break_marks`: two short
        parallel strokes on the left frame line and two on the right one,
        centred on the gap above the LOWER segment. ``width_cm`` and
        ``height_cm`` are the half-extents of each stroke, and
        ``separation_cm`` is the half-distance between the pair.
        """
        centre = f"yg(ygmax)+{self._format_number(gap_cm / 2.0)}"
        w = self._format_number(width_cm)
        h = self._format_number(height_cm)
        sep = self._format_number(separation_cm)

        self._seam_style(color, linewidth, 1)
        for side in ("xgmin", "xgmax"):
            for sign in ("-", "+"):
                self.lines_gle.append(f"amove xg({side})-{w} {centre}{sign}{sep}-{h}")
                self.lines_gle.append(f"aline xg({side})+{w} {centre}{sign}{sep}+{h}")
        self.lines_gle.append("grestore")

    def add_page_ytitle(self, x_expr: str, y_cm: float, text: str):
        """Write a y title at an absolute page position, outside any graph.

        Used for a broken y-axis' shared y title, which must be centred on
        the WHOLE assembly rather than on one segment. The text reads bottom
        to top, centred on ``y_cm``, with its baseline side ending at
        ``x_expr``, a raw GLE expression such as ``'xg(xgmin)-1.06'``.
        """
        self.lines_gle.append("gsave")
        self.lines_gle.append("set just bc")
        self.lines_gle.append("set color BLACK")
        self.lines_gle.append(f"amove {x_expr} {self._format_number(y_cm)}")
        self.lines_gle.append("begin rotate 90")
        self.lines_gle.append(f'write "{self._escape_gle_string(text)}"')
        self.lines_gle.append("end rotate")
        self.lines_gle.append("grestore")

    def add_page_text(
        self,
        x_cm: float,
        y_expr: str,
        text: str,
        just: str = "tc",
        color: str = "BLACK",
        fontsize: Optional[float] = None,
    ):
        """Write text at an absolute page position, outside any graph block.

        Used for a broken axis' shared x title / title, which must be centred
        on the WHOLE assembly rather than on any one segment (GLE's own
        ``xtitle`` centres on its own graph box). ``y_expr`` is a raw GLE
        expression so the caller can anchor it to the graph that just ended,
        e.g. ``'yg(ygmin)-0.55'``.
        """
        self.lines_gle.append("gsave")
        self.lines_gle.append(f"set just {just}")
        self.lines_gle.append(f"set color {color}")
        if fontsize is not None:
            self.lines_gle.append(
                f"set hei {self._format_number(fontsize_pt_to_cm(float(fontsize)))}"
            )
        self.lines_gle.append(f"amove {self._format_number(x_cm)} {y_expr}")
        self.lines_gle.append(f'write "{self._escape_gle_string(text)}"')
        self.lines_gle.append("grestore")

    # -- free page drawing (Figure.circle ... Figure.tex) ---------------
    #
    # Each drawing is its own gsave/grestore group: 'set color'/'set lwidth'
    # are sticky GLE state and must not reach the next drawing. The
    # recognizer takes a group back only when page_drawing_lines reproduces
    # it exactly, so this rendering is the one canonical form.

    def add_page_drawing(self, drawing: dict) -> None:
        """Draw one figure-level drawing (``Figure.circle`` ...) on the page."""
        self.lines_gle.extend(self.page_drawing_lines(drawing))

    @classmethod
    def page_drawing_lines(cls, drawing: dict) -> List[str]:
        """The GLE lines that draw ``drawing``, from ``gsave`` to ``grestore``."""
        commands = {
            "circle": cls._circle_commands,
            "ellipse": cls._ellipse_commands,
            "arc": cls._arc_commands,
            "bezier": cls._bezier_commands,
            "curve": cls._curve_commands,
            "polygon": cls._polygon_commands,
            "table": cls._text_block_commands,
            "tex": cls._text_block_commands,
        }[drawing["kind"]]
        lines = ["gsave"]
        if drawing.get("color", "none") != "none":
            lines.append(f"set color {drawing['color']}")
        if "linewidth" in drawing:
            lwidth = linewidth_pt_to_cm(drawing["linewidth"])
            lines.append(f"set lwidth {cls._format_number(lwidth)}")
        lines.extend(commands(drawing))
        lines.append("grestore")
        return lines

    @classmethod
    def _numbers(cls, *values: float) -> str:
        return " ".join(cls._format_number(v) for v in values)

    @staticmethod
    def _fill_clause(drawing: dict) -> str:
        """The ``fill`` and ``nostroke`` options of a circle or an ellipse."""
        clause = f" fill {drawing['fill']}" if "fill" in drawing else ""
        if drawing.get("color") == "none":
            clause += " nostroke"
        return clause

    @classmethod
    def _circle_commands(cls, d: dict) -> List[str]:
        return [
            f"amove {cls._numbers(d['x'], d['y'])}",
            f"circle {cls._format_number(d['radius'])}{cls._fill_clause(d)}",
        ]

    @classmethod
    def _ellipse_commands(cls, d: dict) -> List[str]:
        # GLE's ellipse takes the two radii (g_ellipse_stroke in core.cpp),
        # though the manual says diameters; width and height are diameters.
        size = cls._numbers(d["width"] / 2, d["height"] / 2)
        return [
            f"amove {cls._numbers(d['x'], d['y'])}",
            f"ellipse {size}{cls._fill_clause(d)}",
        ]

    @classmethod
    def _arc_commands(cls, d: dict) -> List[str]:
        return [
            f"amove {cls._numbers(d['x'], d['y'])}",
            f"arc {cls._numbers(d['radius'], d['theta1'], d['theta2'])}",
        ]

    @classmethod
    def _bezier_commands(cls, d: dict) -> List[str]:
        xs, ys = d["x"], d["y"]
        controls = cls._numbers(*(v for p in zip(xs[1:], ys[1:]) for v in p))
        return [f"amove {cls._numbers(xs[0], ys[0])}", f"bezier {controls}"]

    @classmethod
    def _curve_commands(cls, d: dict) -> List[str]:
        # GLE's curve takes each point as a step from the one before. The
        # steps run between the points as rounded for every other position
        # and keep 12 digits, so GLE's running sum lands on those points.
        xs = [float(cls._format_number(v)) for v in d["x"]]
        ys = [float(cls._format_number(v)) for v in d["y"]]
        steps = " ".join(
            cls._format_number(v, precision=12)
            for k in range(1, len(xs))
            for v in (xs[k] - xs[k - 1], ys[k] - ys[k - 1])
        )
        start, end = cls._numbers(*d["start_slope"]), cls._numbers(*d["end_slope"])
        return [
            f"amove {cls._numbers(xs[0], ys[0])}",
            f"curve {start} {steps} {end}",
        ]

    @classmethod
    def _polygon_commands(cls, d: dict) -> List[str]:
        xs, ys = d["x"], d["y"]
        stroke = "" if d.get("color") == "none" else " stroke"
        fill = f" fill {d['fill']}" if "fill" in d else ""
        lines = [
            f"begin path{stroke}{fill}",
            f"    amove {cls._numbers(xs[0], ys[0])}",
        ]
        lines.extend(f"    aline {cls._numbers(x, y)}" for x, y in zip(xs[1:], ys[1:]))
        lines.extend(["    closepath", "end path"])
        return lines

    @classmethod
    def _text_block_commands(cls, d: dict) -> List[str]:
        # Verbatim: a table lines its columns up from the spaces in the text.
        return [
            f"amove {cls._numbers(d['x'], d['y'])}",
            f"begin {d['kind']}",
            *d["text"].split("\n"),
            f"end {d['kind']}",
        ]

    def add_data_file(
        self,
        filename: str,
        columns: List[np.ndarray],
        column_names: Optional[List[str]] = None,
    ):
        """
        Add external data file.

        Parameters
        ----------
        filename : str
            Name of data file (without path)
        columns : list of arrays
            Column data
        column_names : list of str, optional
            Column names/headers, one per entry in ``columns`` (same order).
            When given, emitted as a single space-separated header line
            before the data rows. Column INDICES used by ``dN=cX,cY``
            references are unaffected by this header -- GLE auto-detects and
            skips a non-numeric first row (see ``auto_has_header`` in the
            GLE source), so ``c1`` etc. still address the first DATA column.

        Raises
        ------
        ValueError
            If ``column_names`` is given and its length does not match
            ``len(columns)``.
        """
        if column_names and len(column_names) != len(columns):
            raise ValueError(
                f"column_names has {len(column_names)} entries but there are "
                f"{len(columns)} columns for {filename!r}"
            )

        lines = []

        # Write header if provided
        if column_names:
            lines.append(" ".join(column_names))

        # Convert columns to 2D array
        data = np.column_stack(columns)

        # Write data rows
        texts = [self._format_column(data[:, j]) for j in range(data.shape[1])]
        lines.extend(" ".join(row) for row in zip(*texts))

        # Add trailing newline for GLE compatibility
        self.data_files[filename] = "\n".join(lines) + "\n"

    def _write_columns(
        self,
        data_file: str,
        named_columns: Sequence[Tuple[str, np.ndarray]],
        column_names: Optional[List[str]],
        binding: Optional[ColumnBinding] = None,
    ) -> List[int]:
        """Place one series' columns and return their 1-based column indices.

        The **single** point where a series' numbers become file columns, and
        the only place that knows whether a sidecar is private to one series
        or shared by a whole provider table.

        With no ``binding`` (every inline series, i.e. everything the
        scripting API produces) this is exactly :meth:`add_data_file` and the
        indices are ``1..N`` in role order -- the historical behaviour, byte
        for byte. With a ``binding``, the columns are merged into the shared
        sidecar named by it and the indices are wherever they landed there.
        """
        if binding is None:
            return self._write_inline_columns(data_file, named_columns, column_names)

        shared = self._shared_sidecars.get(binding.data_file)
        if shared is None:
            shared = self._shared_sidecars[binding.data_file] = _SharedSidecar()
            prior = self._inline_sidecars.get(binding.data_file)
            if prior is not None:
                self._seed_shared(shared, prior)
        indices = []
        for role, array in named_columns:
            key, name = binding.column_for(role)
            indices.append(
                self._share_column(shared, binding.data_file, key, array, name)
            )
        return indices

    def _write_inline_columns(
        self,
        data_file: str,
        named_columns: Sequence[Tuple[str, np.ndarray]],
        column_names: Optional[List[str]],
    ) -> List[int]:
        """An inline series' columns, in a file of its own unless one is named.

        Several series can name one file: a figure read back from a sidecar a
        data provider shared, or a broken axis whose segments all write the
        same data. A file already holding every column (same name, same
        written text) is read as it is; otherwise the columns join a shared
        sidecar, each such column stored once, the first series' own columns
        kept in place so its ``data`` line still reads them.
        """
        if column_names and len(column_names) != len(named_columns):
            raise ValueError(
                f"column_names has {len(column_names)} entries but there are "
                f"{len(named_columns)} columns for {data_file!r}"
            )
        names = [
            column_names[i] if column_names else role
            for i, (role, _array) in enumerate(named_columns)
        ]
        keys = [
            self._column_key(name, array)
            for name, (_role, array) in zip(names, named_columns)
        ]
        shared = self._shared_sidecars.get(data_file)
        prior = self._inline_sidecars.get(data_file)
        if shared is None and prior is None:
            self._inline_sidecars[data_file] = _InlineSidecar(
                list(named_columns), column_names, keys
            )
            self.add_data_file(
                data_file, [array for _role, array in named_columns], column_names
            )
            return list(range(1, len(named_columns) + 1))
        if shared is None:
            assert prior is not None
            if all(key in prior.keys for key in keys):
                return [prior.keys.index(key) + 1 for key in keys]
            shared = self._shared_sidecars[data_file] = _SharedSidecar()
            self._seed_shared(shared, prior)
        if column_names is None:
            shared.named = False
        return [
            self._share_column(shared, data_file, key, array, name)
            for key, name, (_role, array) in zip(keys, names, named_columns)
        ]

    @staticmethod
    def _seed_shared(shared: _SharedSidecar, prior: _InlineSidecar) -> None:
        """Put the columns an inline series already wrote first, in place."""
        shared.named = prior.column_names is not None
        for i, (key, (role, array)) in enumerate(zip(prior.keys, prior.columns)):
            name = prior.column_names[i] if prior.column_names else role
            # A column the series repeats keeps its own index.
            shared.index_of(
                key if key not in shared.keys else f"{key}\x00{i}", array, name
            )

    @staticmethod
    def _share_column(
        shared: _SharedSidecar, data_file: str, key: str, array: Any, name: str
    ) -> int:
        """``shared.index_of``, refusing a column the file's rows cannot hold."""
        if shared.columns and len(array) != len(shared.columns[0]):
            raise ValueError(
                f"Two series write the data file {data_file!r} with "
                f"{len(shared.columns[0])} and {len(array)} rows. Give one of "
                "them its own data_file."
            )
        return shared.index_of(key, array, name)

    def _column_key(self, name: str, array: Any) -> str:
        """A column's name and a digest of its written text."""
        text = "\n".join(self._format_column(np.asarray(array).ravel()))
        return f"{name}\x00{hashlib.sha1(text.encode('utf-8')).hexdigest()}"

    def finalize_shared_sidecars(self) -> None:
        """Render the accumulated provider-table sidecars into ``data_files``.

        Called once, after all emission: a shared file's column set is only
        known when the last series that references its table has been written.
        """
        for filename, shared in self._shared_sidecars.items():
            if shared.columns:
                header = shared.header() if shared.named else None
                self.add_data_file(filename, shared.columns, header)
        self._shared_sidecars.clear()

    def reserve_datasets(self, raw_lines: Sequence[str]) -> None:
        """Keep the next graph block's datasets off the ``dN`` names
        *raw_lines* use.

        *raw_lines* is the raw GLE kept in that block (``Axes.passthrough``).
        Replaces the previous block's reservations.

        Notes
        -----
        Only the names raw GLE defines are reserved: those a ``data``
        statement names and the target of a ``let``. A raw line that only
        reads a dataset (a fit, a fill, a restyle) is left reading the name
        the written series would have had anyway.

        A ``data`` statement that names no datasets fills the lowest
        undefined ones (``freedataset`` in GLE's graph.cpp), and the raw
        statement is written after the series' own. So when the block keeps
        one, every name up to the highest a raw line uses is reserved,
        leaving those slots free for it.
        """
        defined: Set[int] = set()
        used = 0
        bare_data = False
        for line in raw_lines:
            # Names inside a string or a comment are not datasets.
            code = _QUOTED_RE.sub("", line).split("!", 1)[0]
            words = code.split(None, 1)
            if not words:
                continue
            names = [int(m[1:]) for m in _DATASET_NAME_RE.findall(code)]
            used = max([used, *names])
            keyword = words[0].lower()
            if keyword == "data":
                defined.update(names)
                bare_data = bare_data or not names
            elif keyword == "let":
                target = _DATASET_NAME_RE.findall(code.split("=", 1)[0])
                defined.update(int(m[1:]) for m in target)
        if bare_data:
            defined.update(range(1, used + 1))
        self._reserved_datasets = defined

    def _new_dataset(self) -> str:
        """Name a fresh dataset: the next ``dN`` that raw GLE does not use."""
        while self.dataset_index in self._reserved_datasets:
            self.dataset_index += 1
        name = f"d{self.dataset_index}"
        self.dataset_index += 1
        return name

    def _apply_offset(self, source_name: str, offset: float) -> str:
        """Emit a ``let`` command that shifts *source_name* vertically by *offset*.

        Returns the name of a fresh dataset holding ``source_name + offset`` so
        the caller can display the shifted trace while the on-disk ``.dat`` file
        keeps its raw values. The offset therefore lives entirely in the GLE
        script (a waterfall/overlay stack applied at plot time), never baked
        into the data. Error datasets are unaffected -- they carry magnitudes,
        so the caller keeps its ``err`` references on the raw error datasets and
        they ride along with the shifted centre.

        GLE's ``let`` parser is whitespace-sensitive around arithmetic on a
        dataset reference: ``let d2 = d1 + 5`` fails ("unknown token '+'") but
        ``let d2 = d1+5`` works, so the operator is glued to its operands. A
        negative offset is emitted as ``d1-5`` (not ``d1+-5``).
        """
        shifted = self._new_dataset()
        mag = self._format_number(abs(offset))
        sign = "-" if offset < 0 else "+"
        self.lines_gle.append(f"    let {shifted} = {source_name}{sign}{mag}")
        return shifted

    def add_plot_line(
        self,
        x: np.ndarray,
        y: np.ndarray,
        data_file: str,
        color: str = "BLUE",
        linestyle: str = "-",
        linewidth: float = 1.0,
        label: Optional[str] = None,
        marker: Optional[str] = None,
        markersize: float = 0.1,
        nomiss: bool = False,
        yaxis: str = "y",
        xaxis: str = "x",
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
        binding: Optional[ColumnBinding] = None,
        smooth_mode: Optional[str] = None,
        svg_smooth: Optional[int] = None,
        line_mode: Optional[str] = None,
    ):
        """Add a line plot from per-field keywords.

        The keyword form of :meth:`add_line`: each argument is the
        :class:`~gleplot.series.LineSeries` field of the same name, and
        ``binding`` is passed through.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.LineSeries` and call :meth:`add_line` instead.
        """
        _warn_keyword_form("add_plot_line", "LineSeries", "add_line")
        series = LineSeries(
            x=x,
            y=y,
            data_file=data_file,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            marker=marker,
            markersize=markersize,
            nomiss=nomiss,
            yaxis=yaxis,
            xaxis=xaxis,
            offset=offset,
            column_names=column_names,
            smooth_mode=smooth_mode,
            svg_smooth=svg_smooth,
            line_mode=line_mode,
        )
        self.add_line(series, binding=binding)

    def add_line(self, series: Series, binding: Optional[ColumnBinding] = None):
        """
        Add a line series to the graph.

        Points are written to the data file, and drawn, in the order given
        (matplotlib's behavior). The one exception is a ``smooth``-mode line,
        which GLE requires to be monotonic in x -- see :meth:`_row_order`.

        Parameters
        ----------
        series : LineSeries
            The resolved series: its arrays are present (see
            :meth:`SourceResolution.data`). ``x``, ``y``, ``data_file``,
            ``color``, ``linestyle``, ``linewidth`` and ``label`` are required;
            every other field is read with the default its absence has always
            meant.
        binding : ColumnBinding, optional
            Present when this series was resolved from a provider table; its
            columns then go into a sidecar shared with the other series on
            that table (see :meth:`_write_columns`).

        Notes
        -----
        How the fields are emitted:

        - ``linestyle``: a matplotlib linestyle (``'-'``, ``'--'``, ``':'``,
          ``'-.'``); ``'none'`` or empty draws no line, leaving a marker-only
          dataset.
        - ``color``: ``None`` writes no ``color``, so GLE draws in the current
          colour (a recovered dataset line that set none).
        - ``linewidth``: points; 0 or 1 means the style's default width, and
          ``None`` writes no ``lwidth`` (GLE's current line width).
        - ``nomiss``: draw a line through missing values instead of leaving a
          gap (GLE's ``nomiss`` qualifier). No effect when no line is drawn.
        - ``column_names``: the sidecar header row (e.g. ``['x', 'signal']``).
          When present, an explicit ``key`` clause is always emitted (the real
          label, or ``key ""`` when unlabeled) to neutralize GLE's
          auto-key-from-header behavior -- see :meth:`_key_clause`.
        - ``smooth_mode`` (``'none'``, ``'smooth'``, ``'smoothm'``): per-series
          smoothing (SPEC 14.7). Absent defers to the figure-wide
          ``GLEGraphConfig.smooth_curves``; see :meth:`_effective_smooth_mode`.
        - ``svg_smooth``: Savitzky-Golay iterations (>= 1); absent means off.
          Independent of ``smooth_mode``; both may be emitted on one ``dN``
          line, in the order :meth:`_line_token` fixes.
        - ``line_mode`` (``'steps'``, ``'fsteps'``, ``'hist'``, ``'bar'``,
          ``'impulses'``): GLE's ``dn line`` mode, emitted immediately after
          ``line``. Absent leaves the bare ``line`` token.
        - ``mdist``, ``deresolve``, ``deresolve_average`` and the ``xmin`` /
          ``xmax`` / ``ymin`` / ``ymax`` data range: GLE's dataset
          qualifiers, see :meth:`_dataset_qualifier_clause`. A series with
          its own ``deresolve`` gets no preview-only one.
        - ``gaps``: NaN rows are written ``*`` (GLE's missing value), so the
          line breaks there instead of joining across them, and no preview
          ``deresolve`` is added.
        """
        x_array = np.asarray(series["x"])
        y_array = np.asarray(series["y"])
        data_file = series["data_file"]
        color = series["color"]
        linestyle = series["linestyle"]
        linewidth = series["linewidth"]
        label = series["label"]
        marker = series.get("marker")
        markersize = series.get("markersize", 0.1)
        nomiss = series.get("nomiss", False)
        yaxis = series.get("yaxis", "y")
        xaxis = series.get("xaxis", "x")
        offset = series.get("offset", 0.0)
        column_names = series.get("column_names")
        # Passed on raw: the writer normalizes and resolves the figure-wide
        # fallback in one place (_effective_smooth_mode).
        smooth_mode = series.get("smooth_mode")
        svg_smooth = series.get("svg_smooth")
        line_mode = series.get("line_mode")

        # A "no line" state is signalled by a linestyle of none/empty. GLE
        # supports markers on line datasets natively (``d1 line marker circle
        # msize 0.2``), so a series may carry a line, a marker, or both.
        has_line = linestyle not in ("none", "None", "", " ", None)

        # Rows go out in the caller's order unless this series is genuinely
        # ``smooth``-mode smoothed -- see :meth:`_row_order`.
        order = self._row_order(
            x_array, has_line, shared=binding is not None, smooth_mode=smooth_mode
        )
        x_rows, y_rows = x_array[order], y_array[order]
        if series.get("gaps") and binding is None:
            # GLE drops a ``nan`` row and joins its neighbours; ``*`` breaks
            # the line there.
            x_rows = self._as_missing(x_rows, np.isnan(np.asarray(x_rows, dtype=float)))
            y_rows = self._as_missing(y_rows, np.isnan(np.asarray(y_rows, dtype=float)))
        cols = self._write_columns(
            data_file,
            [("x", x_rows), ("y", y_rows)],
            column_names,
            binding,
        )
        has_header = bool(column_names) or binding is not None
        file_name = binding.data_file if binding is not None else data_file

        # Generate plot command with unique dataset name
        d_name = self._new_dataset()
        self._dataset_names[id(series)] = d_name

        cmd = (
            f"    data {_format_data_filename(file_name)} "
            f"{d_name}=c{cols[0]},c{cols[1]}"
        )
        self.lines_gle.append(cmd)

        # A non-zero offset shifts the trace vertically at plot time via a
        # ``let`` on a fresh dataset, leaving the .dat file's values raw.
        display_name = self._apply_offset(d_name, offset) if offset else d_name
        if self._polar_graph:
            display_name = self._polar_dataset(display_name)

        # Generate line command
        line_cmd = f"    {display_name}"

        if has_line:
            # Line plot; smoothing only when opted in (see _line_token).
            # ``nomiss`` follows the smoothing tokens: dn keywords are
            # order-independent in GLE's kw loop except the documented
            # svg_smooth-before-mode rule, which _line_token owns.
            line_cmd += self._line_token(smooth_mode, svg_smooth, line_mode)
            if nomiss:
                line_cmd += " nomiss"
            line_cmd += self._color_clause(color) + self._lwidth_clause(linewidth)

            # Use configured line styles from style config. (A stray second
            # ``lstyle 4`` used to follow the dash-dot case here, overriding
            # the configured value with GLE's sparse-dotted style on every
            # '-.' line series -- removed; the other three emission sites in
            # this file never had it.)
            if linestyle == "--":
                line_cmd += f" lstyle {self.style.line_style_dashed}"
            elif linestyle == ":":
                line_cmd += f" lstyle {self.style.line_style_dotted}"
            elif linestyle == "-.":
                line_cmd += f" lstyle {self.style.line_style_dashdot}"

            if marker:
                # Marker overlaid on the line (line+markers).
                line_cmd += f" marker {marker} msize {self._format_number(markersize)}"
        elif marker:
            # No line: marker-only (scatter). Preserve the historical token
            # order ``marker <name> msize <size> color <color>``.
            line_cmd += f" marker {marker} msize {self._format_number(markersize)}"
            line_cmd += self._color_clause(color)
        # else: neither a line nor a marker (e.g. ``ax.plot(x, y,
        # linestyle='none')`` with no marker -- a real, if pointless,
        # degenerate case matplotlib itself allows) -- the series draws
        # nothing, so nothing is emitted here. This branch used to be
        # unconditional and interpolated ``marker`` even when it was
        # ``None``, putting the literal text "marker None" into the script
        # (GLE then rejects it: "invalid marker name 'None'").

        # Add y2axis directive if using secondary y-axis
        line_cmd += self._dataset_axis_clause(xaxis, yaxis)
        line_cmd += self._dataset_qualifier_clause(series, has_line and bool(marker))

        line_cmd += self._key_clause(label, has_header)
        # Preview-only decimation (G7): "" unless a caller opted in AND this
        # series is large enough -- see _deresolve_clause. Applies to both
        # branches above (line, with or without an overlaid marker, and
        # marker-only/scatter) since both draw through transform_data().
        # ``kind`` is derived from ``has_line``, not from the series class:
        # scatters reach here through add_scatter, which carries them in a
        # LineSeries. Every line (including reference lines, which never
        # carry a marker) has a line, and no scatter does -- exactly
        # gleplot's own KIND split for these two series classes.
        # A series' own ``deresolve`` wins: GLE keeps the last one on the
        # line, so a preview clause after it would replace the caller's.
        # A line with gaps is not thinned: every Nth row would join the ends
        # of different segments across the ``*`` rows.
        if "deresolve" not in series and not series.get("gaps"):
            line_cmd += self._deresolve_clause(
                display_name, label, len(x_array), "line" if has_line else "scatter"
            )

        self.lines_gle.append(line_cmd)
        self._finish_legend_entry(label)

    def add_scatter(self, series: Series, binding: Optional[ColumnBinding] = None):
        """Add a marker-only series to the graph.

        Drawn by :meth:`add_line`, from the fields a scatter has always been
        written with, plus its dataset qualifiers. ``linewidth``, ``nomiss``
        and the smoothing fields are not among them: a scatter is drawn as if
        they were absent.

        Parameters
        ----------
        series : ScatterSeries
            The resolved series: its arrays are present (see
            :meth:`SourceResolution.data`). ``x``, ``y``, ``data_file``,
            ``color``, ``marker``, ``markersize`` and ``label`` are required;
            every other field is read with the default its absence has always
            meant.
        binding : ColumnBinding, optional
            Passed to :meth:`add_line`.

        Notes
        -----
        A series with per-point sizes (``mdata``) is drawn by
        :meth:`_add_sized_scatter` instead, and one with per-point colours
        (``cdata``) by :meth:`_add_coloured_scatter`.
        """
        if "mdata" in series:
            self._add_sized_scatter(series, binding)
            return
        if "cdata" in series:
            self._add_coloured_scatter(series, binding)
            return
        line = LineSeries(
            x=series["x"],
            y=series["y"],
            data_file=series["data_file"],
            color=series["color"],
            linestyle=series.get("linestyle", "none"),
            linewidth=1.0,
            label=series["label"],
            marker=series["marker"],
            markersize=series["markersize"],
            yaxis=series.get("yaxis", "y"),
            xaxis=series.get("xaxis", "x"),
            offset=series.get("offset", 0.0),
            column_names=series.get("column_names"),
        )
        for name in _DATASET_QUALIFIERS:
            if name in series:
                line[name] = series[name]
        self.add_line(line, binding=binding)
        self._dataset_names[id(series)] = self._dataset_names.pop(id(line))

    def _add_sized_scatter(self, series: Series, binding: Optional[ColumnBinding]):
        """A scatter whose points each have their own size (GLE ``mdata``).

        Writes ``dN marker gleplot_mdata_<marker> msize <base> mdata dK``:
        ``dK`` holds each point's size as a multiple of ``msize`` and has no
        display line of its own, so GLE neither draws it nor autoscales to it.
        The marker is the sub :func:`mdata_sub_text` defines. No preview
        ``deresolve`` is added: GLE requires ``dK`` to have exactly as many
        points as ``dN`` draws.

        GLE drops a point whose x or y is NaN, or negative on a log axis,
        from ``dN`` but not from ``dK`` (``transform_data`` in
        ``graph2.cpp``), and then refuses the mismatch. Such a point is
        written as a missing value (``*``) instead, which GLE keeps and does
        not draw.
        """
        x, y, binding = self._missing_where_gle_drops(series, binding)
        d_name, d_sizes = self._mdata_data_line(
            series, binding, x, y, ("mdata", np.asarray(series["mdata"]))
        )
        marker = MDATA_SUB_PREFIX + str(series["marker"]).lower()
        self._mdata_display_line(series, binding, d_name, marker, d_sizes)

    @staticmethod
    def _as_missing(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """``values`` with the rows in ``mask`` written ``*``, GLE's missing value.

        Unchanged (the same array) when ``mask`` selects nothing.
        """
        if not mask.any():
            return values
        rows = np.asarray(values, dtype=float).astype(object)
        rows[mask] = "*"
        return rows

    def _add_coloured_scatter(
        self, series: Series, binding: Optional[ColumnBinding]
    ) -> None:
        """A scatter whose points each have their own colour (``cdata``).

        Writes the values as a hidden dataset ``dC``, maps them onto
        ``[0, 1]`` with ``let dK = (dC-vmin)/(vmax-vmin)`` (``(dC-v)*0`` when
        the two limits are equal, which gives every point the colormap's first
        colour), and draws ``dN marker gleplot_cdata_<marker>_<cmap> msize
        <size> mdata dK``: the sub :func:`cdata_sub_text` defines colours each
        point from its ``dK`` value. Neither ``dC`` nor ``dK`` has a display
        line, so GLE neither draws nor autoscales to them.

        As for :meth:`_add_sized_scatter`, a point GLE would drop from ``dN``
        is written as a missing value, and so is one whose colour value is
        not finite (only a file read back can hold one: ``scatter`` leaves
        such a point out).
        """
        values = np.asarray(series["cdata"], dtype=float)
        unmapped = ~np.isfinite(values)
        x, y, binding = self._missing_where_gle_drops(series, binding, unmapped)
        values = self._as_missing(values, unmapped)
        d_name, d_values = self._mdata_data_line(series, binding, x, y, ("c", values))
        d_mapped = self._new_dataset()
        low = self._format_number(float(series["vmin"]))
        high = self._format_number(float(series["vmax"]))
        # ``d2--5`` would not parse, so a negative vmin flips the operator.
        shift = f"+{low[1:]}" if low.startswith("-") else f"-{low}"
        scale = "*0" if low == high else f"/({high}{shift})"
        self.lines_gle.append(f"    let {d_mapped} = ({d_values}{shift}){scale}")
        marker = cdata_sub_name(str(series["marker"]), series["cmap"])
        self._mdata_display_line(series, binding, d_name, marker, d_mapped)

    def _mdata_data_line(
        self,
        series: Series,
        binding: Optional[ColumnBinding],
        x: np.ndarray,
        y: np.ndarray,
        extra: Tuple[str, np.ndarray],
    ) -> Tuple[str, str]:
        """Write a per-point scatter's columns and its ``data`` line.

        ``extra`` is the role and values of the per-point column. Returns the
        names of the drawn dataset and of the one that reads that column.
        """
        cols = self._write_columns(
            series["data_file"],
            [("x", x), ("y", y), extra],
            series.get("column_names"),
            binding,
        )
        file_name = binding.data_file if binding is not None else series["data_file"]
        d_name = self._new_dataset()
        d_extra = self._new_dataset()
        self.lines_gle.append(
            f"    data {_format_data_filename(file_name)} "
            f"{d_name}=c{cols[0]},c{cols[1]} {d_extra}=c{cols[0]},c{cols[2]}"
        )
        return d_name, d_extra

    def _mdata_display_line(
        self,
        series: Series,
        binding: Optional[ColumnBinding],
        d_name: str,
        marker: str,
        d_mdata: str,
    ) -> None:
        """Draw ``d_name`` with the marker sub ``marker``, fed by ``d_mdata``."""
        label = series["label"]
        offset = series.get("offset", 0.0)
        display_name = self._apply_offset(d_name, offset) if offset else d_name
        if self._polar_graph:
            display_name = self._polar_dataset(display_name)
        msize = self._format_number(series["markersize"])
        named = bool(series.get("column_names")) or binding is not None
        self.lines_gle.append(
            f"    {display_name} marker {marker} msize {msize} mdata {d_mdata}"
            + self._color_clause(series["color"])
            + self._dataset_axis_clause(
                series.get("xaxis", "x"), series.get("yaxis", "y")
            )
            + self._dataset_qualifier_clause(series, False)
            + self._key_clause(label, named)
        )
        self._finish_legend_entry(label)

    def _missing_where_gle_drops(
        self,
        series: Series,
        binding: Optional[ColumnBinding],
        also: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray, Optional[ColumnBinding]]:
        """``series``' x and y with ``*`` where GLE would drop the point.

        ``also`` marks more points to write as missing. When a point is
        missing, a provider-backed series gets its own x and y columns in the
        shared sidecar: another series may read the table's columns, and
        must still see the values.
        """
        x = np.asarray(series["x"])
        y = np.asarray(series["y"])
        xf = np.asarray(x, dtype=float)
        yf = np.asarray(y, dtype=float)
        drop = np.isnan(xf) | np.isnan(yf)
        if also is not None:
            drop |= also
        if self._log_axes.get(series.get("xaxis", "x")):
            drop |= xf < 0
        if self._log_axes.get(series.get("yaxis", "y")):
            drop |= yf < 0
        if not drop.any():
            return x, y, binding
        if binding is not None:
            binding = binding.with_private(("x", "y"))
        return self._as_missing(x, drop), self._as_missing(y, drop), binding

    # -- bar width, the one number GLE derives from the data's shape -------
    #
    # G16. A GLE bar set is sized by the data, not by the script: ``drawBar``
    # (``graph2.cpp``) does
    #
    #     if (br[b]->width == 0) br[b]->width = min_int/(nbars * 2);
    #
    # where ``min_int`` is ``GLEDataPairs::getMinXInterval()`` -- the smallest
    # gap between CONSECUTIVE x values that is strictly positive -- and
    # ``nbars`` is how many datasets the one ``bar`` command groups (1 for
    # :meth:`add_bar`, the member count for :meth:`add_bar_group`). The same
    # ``getMinXInterval`` widens the x DATA range in ``get_dataset_ranges``,
    # by half an interval either side, "so that bars are visible".
    #
    # A dataset with no positive consecutive gap therefore has no width and no
    # range: ``getMinXInterval`` returns ``GLE_INF``. Measured on GLE 4.3.10,
    # all three shapes that reach it are broken today, so nothing that
    # currently draws can be disturbed by fixing them:
    #
    #   * one point (``bar([1], [5])``)  -> "Error: invalid range for
    #     dimension X", exit 1 (the collapsed range having been deferred by
    #     G15; written out instead it is "illegal range for xaxis");
    #   * every x equal (``bar([1, 1], ...)``) -> the same error;
    #   * a descending x column (``bar([3, 1], ...)``) -> the range is fine,
    #     so GLE compiles, but width is infinite and every bar polygon comes
    #     out ``newpath -nan 1.26984 moveto ...``: silent garbage that
    #     Ghostscript then rejects with "Error: /undefined in -nan".
    #
    # The fix is to write down what GLE would have derived, using the one
    # number the data cannot supply -- the spacing -- as a nominal 1. That is
    # not a free choice: it is the spacing of the categorical bar chart
    # ``bar([1], [5])`` is a degenerate case of, it makes the emitted width
    # exactly the width GLE itself computes for the same heights at two
    # points (measured: 0.5 data units, half the frame), and taking the range
    # from the same nominal keeps the two consistent -- ``x ± spacing/2`` is
    # GLE's own bar-range rule with the missing interval filled in.
    #
    # Scaling the nominal with |x| instead (GLE's own single-POINT axis
    # expansion, which G15 defers to, is ±|x|) was rejected on the measured
    # evidence: a lone bar at x = 2023 would become a hairline in a 0..4046
    # frame, where unit spacing gives the year-wide bar the data means.

    #: Bar spacing assumed when GLE cannot measure one from the data.
    BAR_FALLBACK_SPACING = 1.0

    @staticmethod
    def gle_bar_min_x_interval(x: np.ndarray) -> float:
        """GLE's ``GLEDataPairs::getMinXInterval`` for a bar dataset's x column.

        The smallest strictly positive gap between consecutive values, or
        ``inf`` when there is none -- which is GLE's ``GLE_INF``, and the
        signal that the engine can size neither the bars nor the x range.
        """
        values = np.asarray(x, dtype=float)
        if values.size < 2:
            return float("inf")
        gaps = np.diff(values)
        positive = gaps[gaps > 0.0]
        return float(positive.min()) if positive.size else float("inf")

    @classmethod
    def bar_width_gle_cannot_derive(cls, x: np.ndarray) -> Optional[float]:
        """The width to write for this bar dataset, or ``None`` to stay quiet.

        ``None`` for every dataset GLE can size itself, which is what keeps
        the emission byte-identical for bar charts that already draw.
        """
        if math.isfinite(cls.gle_bar_min_x_interval(x)):
            return None
        # drawBar's own formula, min_int/(nbars*2), with nbars = 1.
        return cls.BAR_FALLBACK_SPACING / 2.0

    # -- an explicit width, and what it does to the range (G19) ------------
    #
    # G19 makes ``width`` a real ``BarSeries`` field, so a caller (or a
    # hand-written script the recognizer read) can name the number GLE would
    # otherwise derive. Two questions follow, and both were settled against
    # the live 4.3.10 binary rather than by reading the source twice:
    #
    # 1. Does an explicit width change the range GLE autoscales to? **No.**
    #    ``get_dataset_ranges`` (graph2.cpp) widens a bar dataset's x data
    #    range by ``getMinXInterval()/2`` either side -- the *data's* interval,
    #    never ``br[b]->width``. Measured: a two-point set at x = 1, 2 gets
    #    ``xgmin/xgmax = 0.4/2.6`` with no width, with ``width 0.2`` and with
    #    ``width 2`` alike. So gleplot must not start supplying a range for
    #    bars GLE can measure just because a width was given: those stay
    #    exactly as they are.
    #
    # 2. What half-span should gleplot supply for the datasets GLE *cannot*
    #    measure (G16's three shapes), when a width is given? The width.
    #    GLE's two derivations agree for a single-dataset bar set --
    #    half-interval ``min_int/2`` is *the same number* as the derived width
    #    ``min_int/(nbars*2)`` at ``nbars = 1`` -- so "half-span = width" is
    #    the engine's own proportion (a lone bar filling the middle half of
    #    its frame), and G16's 0.5/0.5 is its no-explicit-width case.
    #    Measured on a lone bar in a 6 cm frame: half-span = width draws
    #    3.0 cm of bar for ``width 0.3`` and for ``width 2`` alike, centred;
    #    holding the half-span at 0.5 instead draws 1.8 cm for ``width 0.3``
    #    and lets ``width 2`` swallow the frame edge to edge (clipped at
    #    both ends). One rule, no clipping, no hairlines.

    @staticmethod
    def bar_explicit_width(series_width: Optional[float]) -> Optional[float]:
        """A ``BarSeries`` ``width`` field as a usable number, or ``None``.

        ``0`` is GLE's own "no width given" sentinel (``drawBar``:
        ``if (br[b]->width == 0) br[b]->width = min_int/(nbars*2)``), so it is
        read here exactly as the engine reads it -- as absent, deferring to
        the derivation -- rather than emitted as a width that would leave the
        engine with nothing to size the degenerate shapes by. A non-finite
        value is no width at all.
        """
        if series_width is None:
            return None
        value = float(series_width)
        if value == 0.0 or not math.isfinite(value):
            return None
        return value

    @classmethod
    def bar_width_to_emit(
        cls, x: np.ndarray, series_width: Optional[float] = None
    ) -> Optional[float]:
        """The ``width w`` to put on this dataset's ``bar`` command, or ``None``.

        An explicit width wins outright and suppresses G16's derived one:
        the caller's number is the answer for every dataset shape, measurable
        or not.
        """
        explicit = cls.bar_explicit_width(series_width)
        if explicit is not None:
            return explicit
        return cls.bar_width_gle_cannot_derive(x)

    @classmethod
    def bar_range_half_span(
        cls, x: np.ndarray, series_width: Optional[float] = None
    ) -> Optional[float]:
        """Half the x range gleplot must supply for this bar set, or ``None``.

        ``None`` -- the overwhelmingly common answer -- means GLE widens the
        range itself from the data's own minimum interval, which is what it
        does whenever that interval is finite, *whatever* width the script
        names (measured; see the note above). Otherwise the half-span is the
        width actually being drawn, so the bar keeps the middle half of its
        frame at any width.
        """
        derived = cls.bar_width_gle_cannot_derive(x)
        if derived is None:
            return None
        explicit = cls.bar_explicit_width(series_width)
        # abs(): a negative width draws a mirrored bar of the same extent.
        return abs(explicit) if explicit is not None else derived

    def add_histogram(
        self,
        samples: np.ndarray,
        data_file: str,
        histtype: str = "step",
        color: str = "BLUE",
        linestyle: str = "-",
        linewidth: float = 1.0,
        label: Optional[str] = None,
        yaxis: str = "y",
        xaxis: str = "x",
        hist_from: Optional[float] = None,
        hist_to: Optional[float] = None,
        bins: Optional[float] = None,
        bin_step: Optional[float] = None,
        edgecolor: Optional[str] = None,
        bar_width: Optional[float] = None,
    ):
        """Draw a histogram GLE bins itself, from per-field keywords.

        The keyword form of :meth:`add_hist`: each argument is the
        :class:`~gleplot.series.HistSeries` field of the same name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.HistSeries` and call :meth:`add_hist` instead.
        """
        _warn_keyword_form("add_histogram", "HistSeries", "add_hist")
        series = HistSeries(
            samples=samples,
            data_file=data_file,
            histtype=histtype,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            yaxis=yaxis,
            xaxis=xaxis,
            hist_from=hist_from,
            hist_to=hist_to,
            bins=bins,
            bin_step=bin_step,
            edgecolor=edgecolor,
            bar_width=bar_width,
        )
        self.add_hist(series)

    def add_hist(self, series: Series):
        """Draw a histogram GLE bins itself.

        ``series`` is the resolved :class:`~gleplot.series.HistSeries`:
        ``samples`` and ``data_file`` are required, and every other field is
        read with the default its absence has always meant.

        The sidecar is the raw samples, two columns and no header: the x
        column is an index ``let hist`` never reads (a one-column file is a
        ``nox`` dataset, and a header would name that dataset in the legend
        because ``let`` marks it used). ``let dK = hist dJ`` then bins the y
        column. ``step`` draws ``dK line hist`` with smoothing pinned off --
        ``transform_data`` splines before it honours the line mode, so a
        figure-wide ``smooth_curves`` would round the bin edges.
        ``stepfilled`` draws ``bar dK`` of one bin width. ``fill x1,dK``
        cannot: it chords the centres and fills down to the axis minimum,
        not along the step outline to zero.
        """
        samples = series["samples"]
        data_file = series["data_file"]
        histtype = series.get("histtype", "step")
        color = series.get("color", "BLUE")
        linestyle = series.get("linestyle", "-")
        linewidth = series.get("linewidth", 1)
        label = series.get("label")
        yaxis = series.get("yaxis", "y")
        xaxis = series.get("xaxis", "x")
        hist_from = series.get("hist_from")
        hist_to = series.get("hist_to")
        bins = series.get("bins")
        bin_step = series.get("bin_step")
        edgecolor = series.get("edgecolor")
        bar_width = series.get("bar_width")
        values = np.asarray(samples, dtype=float).ravel()
        index = np.arange(len(values), dtype=float)
        cols = self._write_columns(data_file, [("x", index), ("y", values)], None)
        source = self._new_dataset()
        target = self._new_dataset()
        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} "
            f"{source}=c{cols[0]},c{cols[1]}"
        )
        self.lines_gle.append(
            self._histogram_let(source, target, hist_from, hist_to, bins, bin_step)
        )

        if histtype == "stepfilled":
            # ``color`` on a bar is the stroke. Matching it to the fill keeps
            # the shared edge of two bins in the fill ink; omitting it leaves
            # GLE's black stroke, which is what a hand-written bar recovers.
            bar_cmd = f"    bar {target} fill {color}"
            if edgecolor is not None:
                bar_cmd += f" color {edgecolor}"
            if bar_width is not None:
                bar_cmd += f" width {self._format_number(bar_width)}"
            self.lines_gle.append(bar_cmd)
            if label:
                quoted = self._quote_gle_key(label)
                self.lines_gle.append(f"    {target} key {quoted}")
                self._finish_legend_entry(label)
            return

        if linewidth is not None:
            try:
                linewidth = float(linewidth)
            except (TypeError, ValueError):
                linewidth = 1.0
        line_cmd = f"    {target}"
        line_cmd += self._line_token(smooth_mode="none", line_mode="hist")
        line_cmd += self._color_clause(color) + self._lwidth_clause(linewidth)
        if linestyle == "--":
            line_cmd += f" lstyle {self.style.line_style_dashed}"
        elif linestyle == ":":
            line_cmd += f" lstyle {self.style.line_style_dotted}"
        elif linestyle == "-.":
            line_cmd += f" lstyle {self.style.line_style_dashdot}"
        line_cmd += self._dataset_axis_clause(xaxis, yaxis)
        line_cmd += self._key_clause(label, has_header=False)
        self.lines_gle.append(line_cmd)
        if label:
            self._finish_legend_entry(label)

    def _histogram_let(
        self,
        source: str,
        target: str,
        hist_from: Optional[float],
        hist_to: Optional[float],
        bins: Optional[float],
        bin_step: Optional[float],
    ) -> str:
        """``let dK = hist dJ`` with only the options the series carries.

        Order is ``from``, ``to``, ``bins``, ``step``. GLE uses ``bins`` when
        both are present; both are still written so a hand-written pair is
        not dropped. Omitting ``bins`` does not invent GLE's default of 10.
        """
        parts = [f"let {target} = hist {source}"]
        if hist_from is not None:
            parts.append(f"from {self._format_number(hist_from)}")
        if hist_to is not None:
            parts.append(f"to {self._format_number(hist_to)}")
        if bins is not None:
            parts.append(f"bins {self._format_number(bins)}")
        if bin_step is not None:
            parts.append(f"step {self._format_number(bin_step)}")
        return "    " + " ".join(parts)

    def add_function(self, series: Series):
        """Draw a curve GLE samples from an expression.

        ``series`` is a :class:`~gleplot.series.FunctionSeries`. The ``let``
        carries only the ``from``/``to``/``step`` the series has, and the
        line is never smoothed: the samples are already as fine as the
        caller asked for. No key is needed to hide a header, because a
        ``let`` dataset has none.
        """
        self._let_curve(series["expression"], series)

    def add_fit(self, series: Series):
        """Draw a curve GLE fits to data.

        ``series`` is a :class:`~gleplot.series.FitSeries`. The data is a
        headerless sidecar read as ``dJ`` and never drawn; ``let dK = fit dJ
        with <expression>``, or the routine for its ``model`` (``let dK =
        linfit dJ``), then fits it, and ``dK`` is drawn as for
        :meth:`add_function`.
        """
        cols = self._write_columns(
            series["data_file"], [("x", series["x"]), ("y", series["y"])], None
        )
        source = self._new_dataset()
        self.lines_gle.append(
            f"    data {_format_data_filename(series['data_file'])} "
            f"{source}=c{cols[0]},c{cols[1]}"
        )
        if "model" not in series:
            self._let_curve(f"fit {source} with {series['expression']}", series)
            return
        definition = f"{FIT_MODEL_TO_ROUTINE[series['model']]} {source}"
        if not self.fit_label_shows_results(series):
            self._let_curve(definition, series)
            return
        # The routine's result variables, in GLE's order, then the key
        # text built from them.
        self._fit_result_count += 1
        names = FIT_RESULT_PLACEHOLDERS[series["model"]]
        variables = {n: f"fit{self._fit_result_count}_{n}" for n in names}
        self._fit_keys[id(series)] = self._fit_key_expression(series, variables)
        self._let_curve(definition, series, [" ".join(variables.values())])

    @staticmethod
    def _fit_placeholders(series: Series) -> list:
        """The placeholders in a model fit's label its model fills.

        Others, as :meth:`gleplot.axes.Axes.fit` rejects them, are text.
        """
        model = series.get("model")
        if model is None:
            return []
        names = FIT_RESULT_PLACEHOLDERS[model]
        return [
            m
            for m in FIT_PLACEHOLDER_RE.finditer(series.get("label") or "")
            if m.group(1) in names
            and (m.group(2) is None or FIT_PLACEHOLDER_SPEC_RE.fullmatch(m.group(2)))
        ]

    @classmethod
    def fit_label_shows_results(cls, series: Series) -> bool:
        """Whether ``series`` is a model fit whose label has a placeholder."""
        return bool(cls._fit_placeholders(series))

    @classmethod
    def _fit_key_expression(cls, series: Series, variables: Dict[str, str]) -> str:
        """The fit's label as a GLE string expression of its ``variables``.

        ``{name:.Nf}`` is ``format$(v,"fix N")`` and ``{name:.Ne}`` the
        ``sci`` format that writes the same text as Python; a bare
        ``{name}`` is ``num$(v)``. The expression has no space outside its
        quotes, so GLE reads it as one ``key`` or ``text`` argument.
        """
        label = series["label"]
        parts = []
        pos = 0
        for match in cls._fit_placeholders(series):
            if match.start() > pos:
                parts.append(f'"{label[pos:match.start()]}"')
            var = variables[match.group(1)]
            spec = match.group(2)
            if spec is None:
                parts.append(f"num$({var})")
            elif spec.endswith("f"):
                parts.append(f'format$({var},"fix {int(spec[1:-1])}")')
            else:
                digits = int(spec[1:-1]) + 1
                parts.append(f'format$({var},"sci {digits} e expdigits 2 expsign")')
            pos = match.end()
        if pos < len(label):
            parts.append(f'"{label[pos:]}"')
        return "+".join(parts)

    def add_derived(
        self, series: Series, sources: Sequence[Series], ranges: Sequence[Series]
    ):
        """Draw a curve GLE computes from datasets already written.

        ``series`` is a :class:`~gleplot.series.DerivedSeries`; ``sources``
        and ``ranges`` are the series its ``sources`` and ``let_range``
        name, as passed to this writer. Each ``dN`` in the expression and
        ``where`` becomes the name the N-th source was written under (its
        raw dataset, before any offset), and ``range`` lists the names of
        ``ranges``. The ``let`` is written after those datasets: GLE runs a
        graph's ``let`` commands in order, so a source that is itself a
        ``let`` must come first.
        """
        names = [self._dataset_names[id(source)] for source in sources]

        def rename(text: str) -> str:
            return _DATASET_NAME_RE.sub(lambda m: names[int(m.group(0)[1:]) - 1], text)

        options = []
        if "let_nsteps" in series:
            options.append(f"nsteps {int(series['let_nsteps'])}")
        if "let_where" in series:
            options.append(f"where {rename(series['let_where'])}")
        if ranges:
            listed = ",".join(self._dataset_names[id(item)] for item in ranges)
            options.append(f"range {listed}")
        self._let_curve(rename(series["expression"]), series, options)

    def _let_curve(
        self, definition: str, series: Series, options: Sequence[str] = ()
    ) -> None:
        """``let dK = <definition> [from a] [to b] [step h] [options]`` and its line."""
        target = self._new_dataset()
        self._dataset_names[id(series)] = target
        parts = [f"let {target} = {definition}"]
        for key, word in (("let_from", "from"), ("let_to", "to"), ("let_step", "step")):
            if key in series:
                parts.append(f"{word} {self._format_number(series[key])}")
        parts.extend(options)
        self.lines_gle.append("    " + " ".join(parts))
        if self._polar_graph:
            target = self._polar_dataset(target)

        linestyle = series.get("linestyle", "-")
        label = series.get("label")
        line_cmd = f"    {target}" + self._line_token(smooth_mode="none")
        line_cmd += self._color_clause(series.get("color"))
        line_cmd += self._lwidth_clause(series.get("linewidth"))
        if linestyle in ("--", ":", "-."):
            line_cmd += f" lstyle {self._lstyle_for(linestyle)}"
        expression = self._fit_keys.get(id(series))
        if expression is not None:
            line_cmd += f" key {expression}"
        else:
            line_cmd += self._key_clause(label, has_header=False)
        self.lines_gle.append(line_cmd)
        self._finish_legend_entry(label)

    def add_bar_chart(
        self,
        x: np.ndarray,
        heights: np.ndarray,
        data_file: str,
        colors: Optional[List[str]] = None,
        label: Optional[str] = None,
        column_names: Optional[List[str]] = None,
        binding: Optional[ColumnBinding] = None,
        width: Optional[float] = None,
        swatch_color: Optional[str] = None,
        edgecolor: Optional[str] = None,
        edge_list: Optional[Sequence[str]] = None,
        fill_list: Optional[Sequence[str]] = None,
        linestyle: Optional[str] = None,
        lstyle: Optional[str] = None,
        linewidth: Optional[float] = None,
        horiz: bool = False,
        bottom: Optional[np.ndarray] = None,
        top: Optional[np.ndarray] = None,
        dist: Optional[float] = None,
    ):
        """Add a bar chart from per-field keywords.

        The keyword form of :meth:`add_bar`: each argument is the
        :class:`~gleplot.series.BarSeries` field of the same name, except
        ``heights``, which is the series' ``height``. ``binding`` is passed
        through.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.BarSeries` and call :meth:`add_bar` instead.
        """
        _warn_keyword_form("add_bar_chart", "BarSeries", "add_bar")
        series = BarSeries(
            x=x,
            height=heights,
            data_file=data_file,
            colors=colors,
            label=label,
            column_names=column_names,
            width=width,
            swatch_color=swatch_color,
            edgecolor=edgecolor,
            edge_list=edge_list,
            fill_list=fill_list,
            linestyle=linestyle,
            lstyle=lstyle,
            linewidth=linewidth,
            horiz=horiz,
            bottom=bottom,
            top=top,
            dist=dist,
        )
        self.add_bar(series, binding=binding)

    def add_bar(self, series: Series, binding: Optional[ColumnBinding] = None):
        """
        Add one bar series to the graph as its own ``bar`` command.

        A series that shares a ``group`` with others goes through
        :meth:`add_bar_group` instead.

        Parameters
        ----------
        series : BarSeries
            The resolved series: its arrays are present (see
            :meth:`SourceResolution.data`). ``x``, ``height``, ``data_file``,
            ``colors`` (may be ``None``) and ``label`` are required; every
            other field is read with the default its absence has always
            meant.
        binding : ColumnBinding, optional
            Present when this series was resolved from a provider table; its
            columns then go into a sidecar shared with the other series on
            that table (see :meth:`_write_columns`).

        Notes
        -----
        How the fields are emitted:

        - ``colors``: GLE color names for each bar; the first is the fill.
          ``None`` fills with ``RED``.
        - ``label``: GLE's ``bar`` command has no ``key`` option, so the label
          is a following ``dN key "..."`` statement. ``bar``'s ``fill``
          already copies into that dataset's ``key_fill``
          (``update_key_fill``), which is the swatch the key draws.
        - ``column_names``: the sidecar header row (e.g. ``['x', 'height']``).
          Unlike the ``dN ... key "..."`` dataset-display commands, GLE's
          ``bar`` command has its own restricted sub-grammar with NO ``key``
          option at all (``bar dN fill COLOR key ""`` is a parse error). So
          when a header row is present, an explicit standalone ``dN key ""``
          statement is emitted right after the ``bar`` command to neutralize
          GLE's auto-key-from-header behavior (verified empirically: this
          statement alone draws nothing, and makes rendering byte-identical
          to the headerless case).
        - ``pattern`` / ``background``: ``pattern P background B`` after the
          fill, which is then the hatch ink. ``bar``'s ``pattern`` also
          updates the dataset's ``key_fill``, so the legend swatch is hatched.
        - ``width``: bar width in DATA units (G19). Absent leaves the sizing
          to GLE, which is what every bar chart gleplot wrote before the field
          existed; a number is emitted verbatim and suppresses G16's derived
          width. See ``bar_width_to_emit``.
        """
        x = np.asarray(series["x"], dtype=float)
        heights = np.asarray(series["height"], dtype=float)
        data_file = series["data_file"]
        colors = series["colors"]
        label = series["label"]
        column_names = series.get("column_names")
        width = series.get("width")
        swatch_color = series.get("swatch_color")
        edgecolor = series.get("edgecolor")
        edge_list = series.get("edge_list")
        fill_list = series.get("fill_list")
        linestyle = series.get("linestyle")
        lstyle = series.get("lstyle")
        linewidth = series.get("linewidth")
        horiz = bool(series.get("horiz"))
        bottom = series.get("bottom")
        top = series.get("top")
        dist = series.get("dist")

        # Default to RED if no colors provided
        if colors is None:
            colors = ["RED"] * len(x)

        # One fill token per dataset. ``fill_list`` is the authored list,
        # which may be longer than one: GLE stores the extras and draws
        # the first. An API series leaves the list absent and the first
        # colour is the fill.
        fill_tokens = list(fill_list) if fill_list else [colors[0]]
        has_header = bool(column_names) or binding is not None
        file_name = binding.data_file if binding is not None else data_file
        emitted_width = self.bar_width_to_emit(x, width)
        d_from = None

        if bottom is not None:
            base = np.asarray(bottom, dtype=float)
            tops = np.asarray(top, dtype=float) if top is not None else base + heights
            names = column_names if column_names and len(column_names) == 3 else None
            # A header we could not line up with the three columns would
            # raise in ``_write_columns``. Dropping it also drops the
            # auto-key, which a label (or the absence of one) already covers.
            has_header = names is not None or binding is not None
            cols = self._write_columns(
                data_file,
                [("x", x), ("bottom", base), ("top", tops)],
                names,
                binding,
            )
            d_from = self._new_dataset()
            d_name = self._new_dataset()
            self.lines_gle.append(
                f"    data {_format_data_filename(file_name)} "
                f"{d_from}=c{cols[0]},c{cols[1]} {d_name}=c{cols[0]},c{cols[2]}"
            )
            bar_cmd = f"    bar {d_name} from {d_from} fill {','.join(fill_tokens)}"
        else:
            cols = self._write_columns(
                data_file, [("x", x), ("height", heights)], column_names, binding
            )
            d_name = self._new_dataset()
            self.lines_gle.append(
                f"    data {_format_data_filename(file_name)} "
                f"{d_name}=c{cols[0]},c{cols[1]}"
            )
            bar_cmd = f"    bar {d_name} fill {','.join(fill_tokens)}"

        bar_cmd += self._bar_pattern_clause([series])
        bar_cmd += self._bar_qualifiers(
            edgecolor,
            edge_list,
            linestyle,
            lstyle,
            linewidth,
            emitted_width,
            dist,
            horiz,
        )
        self.lines_gle.append(bar_cmd)
        # A header names the baseline column too, and GLE would turn that
        # name into a legend entry. The to-dataset is muted by ``_bar_key``.
        if d_from is not None and has_header:
            self.lines_gle.append(f'    {d_from} key ""')
        self._bar_key(d_name, label, swatch_color, has_header)

    def add_bar_group(self, members: Sequence[Mapping[str, Any]]) -> None:
        """One ``bar d1,d2,...`` command for series that share a group id.

        The sidecar has the shared x and one y column per member. A member
        with a baseline adds a from-dataset; its y column is the top.
        Qualifiers that belong to the command (width, dist, horiz, the
        edge) are read from the first member.
        """
        first = members[0]
        x = np.asarray(first["x"], dtype=float)
        # ``from`` is positional: the ith baseline belongs to the ith
        # dataset. If any member is stacked, every member gets a baseline
        # (zeros where the caller did not set one) so a later stack is not
        # applied to an earlier dataset.
        stacked = any(member.get("bottom") is not None for member in members)
        columns: List[Tuple[str, np.ndarray]] = [("x", x)]
        to_slots: List[int] = []
        from_slots: List[Optional[int]] = []
        for member in members:
            height = np.asarray(member["height"], dtype=float)
            if stacked:
                if member.get("bottom") is None:
                    base = np.zeros(height.shape, dtype=float)
                    tops = height
                else:
                    base = np.asarray(member["bottom"], dtype=float)
                    stored = member.get("top")
                    tops = (
                        np.asarray(stored, dtype=float)
                        if stored is not None
                        else base + height
                    )
                columns.append(("bottom", base))
                from_slots.append(len(columns) - 1)
                columns.append(("top", tops))
                to_slots.append(len(columns) - 1)
            else:
                columns.append(("height", height))
                from_slots.append(None)
                to_slots.append(len(columns) - 1)

        header = _group_bar_header(members, len(columns))
        data_file = first["data_file"]
        cols = self._write_columns(data_file, columns, header, None)
        from_names: List[str] = []
        to_names: List[str] = []
        clause = []
        for slot, origin in zip(to_slots, from_slots):
            if origin is not None:
                from_name = self._new_dataset()
                from_names.append(from_name)
                clause.append(f"{from_name}=c{cols[0]},c{cols[origin]}")
            to_name = self._new_dataset()
            to_names.append(to_name)
            clause.append(f"{to_name}=c{cols[0]},c{cols[slot]}")
        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} " + " ".join(clause)
        )

        # An empty ``fill_list`` is a command that named no fill. Absent
        # means each member's own first colour, which is what an API group
        # would say. The two must not collapse: GLE's default for a missing
        # fill is a gradient, and inventing RED would repaint it.
        if "fill_list" in first:
            fills = list(first.get("fill_list") or [])
        else:
            fills = [(member.get("colors") or ["RED"])[0] for member in members]
        bar_cmd = f"    bar {','.join(to_names)}"
        if any(slot is not None for slot in from_slots):
            bar_cmd += " from " + ",".join(from_names)
        if fills:
            bar_cmd += " fill " + ",".join(fills)
        bar_cmd += self._bar_pattern_clause(members)
        bar_cmd += self._bar_qualifiers(
            first.get("edgecolor"),
            first.get("edge_list"),
            first.get("linestyle"),
            first.get("lstyle"),
            first.get("linewidth"),
            self.bar_width_to_emit(x, first.get("width")),
            first.get("dist"),
            bool(first.get("horiz")),
        )
        self.lines_gle.append(bar_cmd)
        has_header = header is not None
        if has_header:
            for dataset in from_names:
                self.lines_gle.append(f'    {dataset} key ""')
        for dataset, member in zip(to_names, members):
            self._bar_key(
                dataset,
                member.get("label"),
                member.get("swatch_color"),
                has_header,
            )

    @staticmethod
    def _bar_pattern_clause(members: Sequence[Mapping[str, Any]]) -> str:
        """`` pattern P,... background B,...`` for a bar command, or empty.

        Both lists are positional over the command's datasets, so they
        cover the leading members that have a pattern. GLE turns a
        ``background`` alone into a ``SHADE`` fill, so a member without a
        pattern ends both lists. What that leaves out is warned about.
        """
        patterns: List[str] = []
        backgrounds: List[str] = []
        stopped = dropped = False
        for member in members:
            pattern = member.get("pattern")
            background = member.get("background")
            if stopped or not pattern:
                stopped = True
                dropped = dropped or bool(pattern or background)
                continue
            patterns.append(pattern)
            if background and len(backgrounds) == len(patterns) - 1:
                backgrounds.append(background)
            elif background:
                dropped = True
        if dropped:
            warn_external(
                "A bar group's pattern or background could not be written: "
                "GLE assigns them to the datasets in order, so only the "
                "leading members' are kept. Give every member of the group "
                "a pattern, or split the group into separate bar() calls."
            )
        if not patterns:
            return ""
        clause = " pattern " + ",".join(patterns)
        if backgrounds:
            clause += " background " + ",".join(backgrounds)
        return clause

    def _bar_qualifiers(
        self,
        edgecolor: Optional[str],
        edge_list: Optional[Sequence[str]],
        linestyle: Optional[str],
        lstyle: Optional[str],
        linewidth: Optional[float],
        emitted_width: Optional[float],
        dist: Optional[float],
        horiz: bool,
    ) -> str:
        """The keywords that follow ``fill`` on a ``bar`` command.

        Empty for a historical ``bar dN fill COLOR`` (and ``width`` is
        appended in its old place when that is the only extra). ``color``
        is the stroke. ``lstyle`` / ``lwidth`` are the edge. ``horiz`` and
        ``dist`` are the orientation and the group spacing.
        """
        parts: List[str] = []
        bare_edge = str(edgecolor).lower() == "none" if edgecolor is not None else False
        no_stroke = bare_edge or linestyle == "none"
        if no_stroke:
            parts.append("lwidth 0")
        else:
            edges = list(edge_list) if edge_list else []
            if not edges and edgecolor:
                edges = [edgecolor]
            if edges:
                parts.append("color " + ",".join(str(item) for item in edges))
            style = lstyle
            if not style and linestyle:
                number = self._lstyle_for(linestyle)
                if number:
                    style = str(number)
            if style:
                parts.append(f"lstyle {style}")
            if linewidth is not None:
                parts.append(
                    "lwidth "
                    + self._format_number(linewidth_pt_to_cm(float(linewidth)))
                )
        if emitted_width is not None:
            parts.append(f"width {self._format_number(emitted_width)}")
        if dist is not None:
            parts.append(f"dist {self._format_number(float(dist))}")
        if horiz:
            parts.append("horiz")
        if not parts:
            return ""
        return " " + " ".join(parts)

    def _bar_key(self, d_name: str, label, swatch_color, has_header: bool) -> None:
        """Legend entry for one bar dataset, or the header auto-key mute."""
        if label:
            quoted = self._quote_gle_key(label)
            if swatch_color:
                self.lines_gle.append(
                    f"    {d_name} keyfill {swatch_color} key {quoted}"
                )
            else:
                self.lines_gle.append(f"    {d_name} key {quoted}")
            self._finish_legend_entry(label)
        elif has_header:
            self.lines_gle.append(f'    {d_name} key ""')

    def add_errorbar(
        self,
        x: np.ndarray,
        y: np.ndarray,
        data_file: str,
        color: str = "BLUE",
        linestyle: str = "-",
        linewidth: float = 1.0,
        label: Optional[str] = None,
        marker: Optional[str] = None,
        markersize: float = 0.1,
        yerr_up: Optional[np.ndarray] = None,
        yerr_down: Optional[np.ndarray] = None,
        xerr_left: Optional[np.ndarray] = None,
        xerr_right: Optional[np.ndarray] = None,
        capsize: Optional[float] = None,
        yaxis: str = "y",
        xaxis: str = "x",
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
        binding: Optional[ColumnBinding] = None,
    ):
        """Add a plot with error bars from per-field keywords.

        The keyword form of :meth:`add_errorbar_series`: each argument is the
        :class:`~gleplot.series.ErrorbarSeries` field of the same name, except
        ``capsize``, which is the emitted cap width in cm (the series'
        ``gle_capsize``). ``binding`` is passed through.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.ErrorbarSeries` and call
        :meth:`add_errorbar_series` instead.
        """
        _warn_keyword_form("add_errorbar", "ErrorbarSeries", "add_errorbar_series")
        series = ErrorbarSeries(
            x=x,
            y=y,
            data_file=data_file,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            marker=marker,
            markersize=markersize,
            yerr_up=yerr_up,
            yerr_down=yerr_down,
            xerr_left=xerr_left,
            xerr_right=xerr_right,
            gle_capsize=capsize,
            yaxis=yaxis,
            xaxis=xaxis,
            offset=offset,
            column_names=column_names,
        )
        self.add_errorbar_series(series, binding=binding)

    def add_errorbar_series(
        self, series: Series, binding: Optional[ColumnBinding] = None
    ):
        """
        Add an error-bar series to the graph.

        Generates GLE error bar syntax using datasets for error values.

        Points are written to the data file, and drawn, in the order given
        (matplotlib's behavior). The one exception is a smoothed line, which
        GLE requires to be monotonic in x -- see :meth:`_row_order`.

        GLE error bar syntax reference (from GLE manual):
        - ``dn err <value|percent|dataset>`` — symmetric vertical errors
        - ``dn errup <value|percent|dataset>`` — upper vertical error
        - ``dn errdown <value|percent|dataset>`` — lower vertical error
        - ``dn errwidth <width>`` — vertical error bar cap width
        - ``dn herr <value|percent|dataset>`` — symmetric horizontal errors
        - ``dn herrleft <value|percent|dataset>`` — left horizontal error
        - ``dn herrright <value|percent|dataset>`` — right horizontal error
        - ``dn herrwidth <width>`` — horizontal error bar cap width

        Parameters
        ----------
        series : ErrorbarSeries
            The resolved series: its arrays are present (see
            :meth:`SourceResolution.data`). ``x``, ``y``, ``data_file``,
            ``color``, ``linestyle``, ``linewidth``, ``label``, ``marker``,
            ``markersize`` and the four error arrays (each may be ``None``)
            are required; every other field is read with the default its
            absence has always meant.
        binding : ColumnBinding, optional
            Present when this series was resolved from a provider table; its
            columns then go into a sidecar shared with the other series on
            that table (see :meth:`_write_columns`).

        Notes
        -----
        How the fields are emitted:

        - ``linestyle``: a matplotlib linestyle (``'-'``, ``'--'``, ``':'``,
          ``'-.'``); ``'none'`` or empty draws no line.
        - ``linewidth``: points; 0 or 1 means the style's default width.
        - ``gle_capsize``: the cap width in cm. A series without it (one saved
          before it existed) falls back to ``capsize``.
        - ``column_names``: the sidecar header row (e.g. ``['x', 'signal',
          'err']``). Only the MAIN dataset's ``key`` clause needs suppressing
          when unlabeled (see :meth:`_key_clause`) -- error sub-datasets
          (``d{n}=c1,cN`` referenced via ``err``/``errup``/``herr``/...) are
          never added to GLE's key-rendering "used dataset" order on their
          own, so they never draw an auto-key regardless of any
          header-derived name on their column (verified empirically).
        """
        x_array = np.asarray(series["x"])
        y_array = np.asarray(series["y"])
        data_file = series["data_file"]
        color = series["color"]
        linestyle = series["linestyle"]
        linewidth = series["linewidth"]
        label = series["label"]
        marker = series["marker"]
        markersize = series["markersize"]
        yerr_up = series["yerr_up"]
        yerr_down = series["yerr_down"]
        xerr_left = series["xerr_left"]
        xerr_right = series["xerr_right"]
        capsize = series.get("gle_capsize", series.get("capsize"))
        yaxis = series.get("yaxis", "y")
        xaxis = series.get("xaxis", "x")
        offset = series.get("offset", 0.0)
        column_names = series.get("column_names")

        has_line = linestyle not in ("", "none", " ", "None")

        # Rows go out in the caller's order unless this series is genuinely
        # smoothed -- see :meth:`_row_order`. Every column below (centres and
        # error magnitudes alike) is indexed by the same ``order`` so a row
        # stays one point.
        order = self._row_order(x_array, has_line, shared=binding is not None)

        # Build columns list: x, y, then error columns. Each entry is tagged
        # with the series ROLE it came from, which is how _write_columns maps
        # it onto a provider table column when this series is table-backed.
        columns = [("x", x_array[order]), ("y", y_array[order])]
        col_idx = 3  # Next column index (c1=x, c2=y, c3=...)

        # Track which columns hold error data
        yerr_up_col = None
        yerr_down_col = None
        xerr_left_col = None
        xerr_right_col = None

        has_yerr = yerr_up is not None or yerr_down is not None
        has_xerr = xerr_left is not None or xerr_right is not None

        # Check if vertical errors are symmetric (same arrays)
        yerr_symmetric = (
            has_yerr
            and yerr_up is not None
            and yerr_down is not None
            and np.array_equal(yerr_up, yerr_down)
        )
        # Check if horizontal errors are symmetric
        xerr_symmetric = (
            has_xerr
            and xerr_left is not None
            and xerr_right is not None
            and np.array_equal(xerr_left, xerr_right)
        )

        if has_yerr:
            if yerr_symmetric:
                # Single column for symmetric error
                columns.append(("yerr_up", np.asarray(yerr_up)[order]))
                yerr_up_col = col_idx
                yerr_down_col = col_idx  # Same column
                col_idx += 1
            else:
                if yerr_up is not None:
                    columns.append(("yerr_up", np.asarray(yerr_up)[order]))
                    yerr_up_col = col_idx
                    col_idx += 1
                if yerr_down is not None:
                    columns.append(("yerr_down", np.asarray(yerr_down)[order]))
                    yerr_down_col = col_idx
                    col_idx += 1

        if has_xerr:
            if xerr_symmetric:
                columns.append(("xerr_left", np.asarray(xerr_left)[order]))
                xerr_left_col = col_idx
                xerr_right_col = col_idx
                col_idx += 1
            else:
                if xerr_left is not None:
                    columns.append(("xerr_left", np.asarray(xerr_left)[order]))
                    xerr_left_col = col_idx
                    col_idx += 1
                if xerr_right is not None:
                    columns.append(("xerr_right", np.asarray(xerr_right)[order]))
                    xerr_right_col = col_idx
                    col_idx += 1

        # Write data file with all columns. The ``*_col`` values above are
        # positions within THIS series' column list; ``cols`` maps each onto
        # the column index it actually got in the file, which is an identity
        # map for a private sidecar and a lookup for a shared one.
        cols = self._write_columns(data_file, columns, column_names, binding)
        has_header = bool(column_names) or binding is not None
        file_name = binding.data_file if binding is not None else data_file

        def _c(local_pos: Optional[int]) -> int:
            # Only ever called from a branch that has just established the
            # column exists, so the narrowing is an invariant, not a check.
            assert local_pos is not None
            return cols[local_pos - 1]

        # Generate dataset name for main data
        d_main = self._new_dataset()

        # Build data command with all dataset references
        data_cmd = (
            f"    data {_format_data_filename(file_name)} "
            f"{d_main}=c{cols[0]},c{cols[1]}"
        )

        # Create error datasets referencing the same file columns
        err_datasets = {}

        if has_yerr:
            if yerr_symmetric:
                d_yerr = self._new_dataset()
                data_cmd += f" {d_yerr}=c{cols[0]},c{_c(yerr_up_col)}"
                err_datasets["yerr"] = d_yerr
            else:
                if yerr_up_col is not None:
                    d_yerr_up = self._new_dataset()
                    data_cmd += f" {d_yerr_up}=c{cols[0]},c{_c(yerr_up_col)}"
                    err_datasets["yerr_up"] = d_yerr_up
                if yerr_down_col is not None:
                    d_yerr_down = self._new_dataset()
                    data_cmd += f" {d_yerr_down}=c{cols[0]},c{_c(yerr_down_col)}"
                    err_datasets["yerr_down"] = d_yerr_down

        if has_xerr:
            if xerr_symmetric:
                d_xerr = self._new_dataset()
                data_cmd += f" {d_xerr}=c{cols[0]},c{_c(xerr_left_col)}"
                err_datasets["xerr"] = d_xerr
            else:
                if xerr_left_col is not None:
                    d_xerr_left = self._new_dataset()
                    data_cmd += f" {d_xerr_left}=c{cols[0]},c{_c(xerr_left_col)}"
                    err_datasets["xerr_left"] = d_xerr_left
                if xerr_right_col is not None:
                    d_xerr_right = self._new_dataset()
                    data_cmd += f" {d_xerr_right}=c{cols[0]},c{_c(xerr_right_col)}"
                    err_datasets["xerr_right"] = d_xerr_right

        self.lines_gle.append(data_cmd)

        # A non-zero offset shifts the plotted centre vertically at plot time
        # via a ``let`` on a fresh dataset; the raw .dat values are untouched
        # and the error datasets (magnitudes) stay bound to the raw columns, so
        # the bars ride along with the shifted centre.
        display_name = self._apply_offset(d_main, offset) if offset else d_main

        # Build the main dataset display command
        line_cmd = f"    {display_name}"

        # Add line/marker styling
        has_line = linestyle not in ("", "none", " ", "None")
        # GLE draws error bars (and their caps) in the DATASET's colour, which
        # only ever gets set by a ``color`` qualifier on the ``dN`` command --
        # an unstyled dataset defaults to black. Track whether the marker/line
        # styling already supplied one so a bars-only series can add it below.
        color_emitted = False

        if marker:
            line_cmd += f" marker {marker} msize {self._format_number(markersize)}"
            line_cmd += self._color_clause(color)
            color_emitted = True
            # Also add line if linestyle is not 'none'
            if has_line:
                line_cmd += self._line_token() + self._lwidth_clause(linewidth)
                if linestyle == "--":
                    line_cmd += f" lstyle {self.style.line_style_dashed}"
                elif linestyle == ":":
                    line_cmd += f" lstyle {self.style.line_style_dotted}"
                elif linestyle == "-.":
                    line_cmd += f" lstyle {self.style.line_style_dashdot}"
        else:
            if has_line:
                line_cmd += self._line_token()
                line_cmd += self._color_clause(color) + self._lwidth_clause(linewidth)
                color_emitted = True
                if linestyle == "--":
                    line_cmd += f" lstyle {self.style.line_style_dashed}"
                elif linestyle == ":":
                    line_cmd += f" lstyle {self.style.line_style_dotted}"
                elif linestyle == "-.":
                    line_cmd += f" lstyle {self.style.line_style_dashdot}"

        # Bars-only series (no marker AND no line -- matplotlib's
        # ``fmt="none"``) previously emitted no ``color`` at all, so GLE drew
        # the bars black no matter what colour was requested. Emit it here so
        # every errorbar dataset carries its series colour, at any dataset
        # index and for any capsize (including ``capsize=0``). The token order
        # matches :meth:`_add_errorbar_file_series`'s marker-less form
        # (``dN color <c> err dM``).
        if not color_emitted:
            line_cmd += self._color_clause(color)

        # Add vertical error bar commands
        if "yerr" in err_datasets:
            line_cmd += f' err {err_datasets["yerr"]}'
        else:
            if "yerr_up" in err_datasets:
                line_cmd += f' errup {err_datasets["yerr_up"]}'
            if "yerr_down" in err_datasets:
                line_cmd += f' errdown {err_datasets["yerr_down"]}'

        if capsize is not None and has_yerr:
            line_cmd += f" errwidth {self._format_number(capsize)}"

        # Add horizontal error bar commands
        if "xerr" in err_datasets:
            line_cmd += f' herr {err_datasets["xerr"]}'
        else:
            if "xerr_left" in err_datasets:
                line_cmd += f' herrleft {err_datasets["xerr_left"]}'
            if "xerr_right" in err_datasets:
                line_cmd += f' herrright {err_datasets["xerr_right"]}'

        if capsize is not None and has_xerr:
            line_cmd += f" herrwidth {self._format_number(capsize)}"

        # Add y2axis directive if using secondary y-axis
        line_cmd += self._dataset_axis_clause(xaxis, yaxis)

        line_cmd += self._key_clause(label, has_header)
        # No preview-decimation clause here, deliberately: this dataset
        # carries err/errup/errdown/herr/... references, and GLE's error-bar
        # draw path never consults `deresolve` (see _deresolve_clause's
        # errorbar paragraph for the source trace + empirical verification).
        # Appending it would thin the markers/line while every whisker stayed
        # at full density -- worse than not decimating at all.

        self.lines_gle.append(line_cmd)
        self._finish_legend_entry(label)

    def add_file_series(self, series: Series):
        """Add a series that references columns of an external data file.

        No sidecar is written: the ``data`` command names the file and
        columns as given.

        Parameters
        ----------
        series : FileSeries
            ``series_type`` picks the GLE shape: ``'line'``, ``'bar'``,
            ``'fill'``, or ``'errorbar'`` (also when absent). ``data_file``
            and the variant's column fields are required, and so is
            ``color`` for an errorbar reference; every other field is read
            with the default its absence has always meant.
        """
        series_type = series.get("series_type", "errorbar")
        if series_type == "line":
            self._add_line_file_series(series)
        elif series_type == "bar":
            self._add_bar_file_series(series)
        elif series_type == "fill":
            self._add_fill_file_series(series)
        else:
            self._add_errorbar_file_series(series)

    def add_errorbar_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        yerr_col: Optional[int] = None,
        color: str = "BLUE",
        marker: Optional[str] = None,
        markersize: float = 0.1,
        label: Optional[str] = None,
        capsize: Optional[float] = None,
        yaxis: str = "y",
        xaxis: str = "x",
    ):
        """Add an errorbar file reference from per-field keywords.

        The keyword form of :meth:`add_file_series` for ``series_type
        'errorbar'``: each argument is the :class:`~gleplot.series.FileSeries`
        field of the same name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.FileSeries` and call :meth:`add_file_series` instead.
        """
        _warn_keyword_form("add_errorbar_from_file", "FileSeries", "add_file_series")
        series = FileSeries(
            series_type="errorbar",
            data_file=data_file,
            x_col=x_col,
            y_col=y_col,
            yerr_col=yerr_col,
            color=color,
            marker=marker,
            markersize=markersize,
            label=label,
            capsize=capsize,
            yaxis=yaxis,
            xaxis=xaxis,
        )
        self.add_file_series(series)

    def _add_errorbar_file_series(self, series: Series):
        """A marker/errorbar series that references columns in an external file."""
        data_file = series["data_file"]
        x_col = series["x_col"]
        y_col = series["y_col"]
        yerr_col = series.get("yerr_col")
        color = series["color"]
        marker = series.get("marker")
        markersize = series.get("markersize", 0.1)
        label = series.get("label")
        capsize = series.get("capsize")
        yaxis = series.get("yaxis", "y")
        xaxis = series.get("xaxis", "x")
        d_main = self._new_dataset()

        data_cmd = (
            f"    data {_format_data_filename(data_file)} {d_main}=c{x_col},c{y_col}"
        )
        d_yerr = None
        if yerr_col is not None:
            d_yerr = self._new_dataset()
            data_cmd += f" {d_yerr}=c{x_col},c{yerr_col}"
        self.lines_gle.append(data_cmd + self._data_read_clause(series))

        d_draw = self._polar_dataset(d_main) if self._polar_graph else d_main
        line_cmd = f"    {d_draw}"
        # Both branches must set ``color``: GLE draws the error bars in the
        # dataset's colour and an unstyled dataset falls back to black (see
        # :meth:`add_errorbar_series`). ``None`` is a recovered reference
        # that set none, and keeps none.
        if marker:
            line_cmd += f" marker {marker} msize {self._format_number(markersize)}"
        line_cmd += self._color_clause(color)

        if d_yerr is not None:
            line_cmd += f" err {d_yerr}"
            if capsize is not None:
                line_cmd += f" errwidth {self._format_number(capsize)}"

        line_cmd += self._dataset_axis_clause(xaxis, yaxis)
        line_cmd += self._dataset_qualifier_clause(series, False)

        if label:
            line_cmd += f" key {self._quote_gle_key(label)}"

        self.lines_gle.append(line_cmd)
        self._finish_legend_entry(label)

    def add_plot_line_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        color: str = "BLUE",
        linestyle: str = "-",
        linewidth: float = 1.0,
        label: Optional[str] = None,
        yaxis: str = "y",
        xaxis: str = "x",
        marker: Optional[str] = None,
        markersize: float = 0.1,
        nomiss: bool = False,
        line_mode: Optional[str] = None,
    ):
        """Add a line file reference from per-field keywords.

        The keyword form of :meth:`add_file_series` for ``series_type
        'line'``: each argument is the :class:`~gleplot.series.FileSeries`
        field of the same name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.FileSeries` and call :meth:`add_file_series` instead.
        """
        _warn_keyword_form("add_plot_line_from_file", "FileSeries", "add_file_series")
        series = FileSeries(
            series_type="line",
            data_file=data_file,
            x_col=x_col,
            y_col=y_col,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            label=label,
            yaxis=yaxis,
            xaxis=xaxis,
            marker=marker,
            markersize=markersize,
            nomiss=nomiss,
            line_mode=line_mode,
        )
        self.add_file_series(series)

    def _add_line_file_series(self, series: Series):
        """A line series that references columns in an external data file.

        ``marker``/``markersize`` overlay a marker on the line (GLE natively
        supports both on one dataset) -- this function is only ever called
        for a series that already has a line (see ``_build_file_series``'s
        ``has_line`` branch; a no-line, marker-only reference is an
        ``'errorbar'`` reference instead), so there is no separate
        no-line/marker-only case to guard here, unlike ``add_line``.

        ``nomiss`` : draw the line through a missing value instead of
        leaving a gap (GLE's ``nomiss`` qualifier).

        The dataset qualifiers are written by
        :meth:`_dataset_qualifier_clause`.
        """
        data_file = series["data_file"]
        x_col = series["x_col"]
        y_col = series["y_col"]
        color = series.get("color", "BLUE")
        linestyle = series.get("linestyle", "-")
        linewidth = series.get("linewidth", 1.0)
        label = series.get("label")
        yaxis = series.get("yaxis", "y")
        xaxis = series.get("xaxis", "x")
        marker = series.get("marker")
        markersize = series.get("markersize", 0.1)
        nomiss = series.get("nomiss", False)
        line_mode = series.get("line_mode")
        d_main = self._new_dataset()
        self._dataset_names[id(series)] = d_main

        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} {d_main}=c{x_col},c{y_col}"
            + self._data_read_clause(series)
        )

        # File series have no per-series smooth field, so they inherit
        # figure-wide smoothing. A line mode must not: fitbez runs before
        # the mode is drawn and would replace the discrete join.
        smooth_mode = "none" if line_mode else None
        d_draw = self._polar_dataset(d_main) if self._polar_graph else d_main
        line_cmd = f"    {d_draw}{self._line_token(smooth_mode, line_mode=line_mode)}"
        if nomiss:
            line_cmd += " nomiss"
        line_cmd += self._color_clause(color) + self._lwidth_clause(linewidth)
        if linestyle == "--":
            line_cmd += f" lstyle {self.style.line_style_dashed}"
        elif linestyle == ":":
            line_cmd += f" lstyle {self.style.line_style_dotted}"
        elif linestyle == "-.":
            line_cmd += f" lstyle {self.style.line_style_dashdot}"

        if marker:
            line_cmd += f" marker {marker} msize {self._format_number(markersize)}"

        line_cmd += self._dataset_axis_clause(xaxis, yaxis)
        line_cmd += self._dataset_qualifier_clause(series, bool(marker))

        if label:
            line_cmd += f" key {self._quote_gle_key(label)}"

        self.lines_gle.append(line_cmd)
        self._finish_legend_entry(label)

    def add_bar_from_file(
        self,
        data_file: str,
        x_col: int,
        y_col: int,
        color: str = "RED",
        label: Optional[str] = None,
        swatch_color: Optional[str] = None,
    ):
        """Add a bar file reference from per-field keywords.

        The keyword form of :meth:`add_file_series` for ``series_type
        'bar'``: each argument is the :class:`~gleplot.series.FileSeries`
        field of the same name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.FileSeries` and call :meth:`add_file_series` instead.
        """
        _warn_keyword_form("add_bar_from_file", "FileSeries", "add_file_series")
        series = FileSeries(
            series_type="bar",
            data_file=data_file,
            x_col=x_col,
            y_col=y_col,
            color=color,
            label=label,
            swatch_color=swatch_color,
        )
        self.add_file_series(series)

    def _add_bar_file_series(self, series: Series):
        """A bar series that references columns in an external data file.

        Used for a ``bar`` dataset the recognizer could not resolve (e.g. a
        missing data file): re-emits the ``data``/``bar`` shape verbatim so
        GLE fails with its own honest missing-file error rather than
        gleplot silently degrading the bar into a plain dataset.
        """
        data_file = series["data_file"]
        x_col = series["x_col"]
        y_col = series["y_col"]
        color = series.get("color", "RED")
        label = series.get("label")
        swatch_color = series.get("swatch_color")
        d_name = self._new_dataset()
        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} {d_name}=c{x_col},c{y_col}"
            + self._data_read_clause(series)
        )
        self.lines_gle.append(f"    bar {d_name} fill {color}")
        if label:
            quoted = self._quote_gle_key(label)
            if swatch_color:
                self.lines_gle.append(
                    f"    {d_name} keyfill {swatch_color} key {quoted}"
                )
            else:
                self.lines_gle.append(f"    {d_name} key {quoted}")
            self._finish_legend_entry(label)

    def _append_fill(
        self, head: str, color_token: str, clip: Mapping[str, Any]
    ) -> None:
        """One ``fill`` command.

        ``head`` is ``dA,dB``, ``x1,dN``, ``dN,x2`` or ``dN``.
        """
        parts = [f"    fill {head} color {color_token}"]
        for name in ("xmin", "xmax", "ymin", "ymax"):
            value = clip.get(name)
            if value is not None:
                parts.append(f"{name} {self._format_number(float(value))}")
        self.lines_gle.append(" ".join(parts))

    def _fill_key(
        self, dataset: str, color_token: str, label, swatch_color, has_header
    ):
        """Legend swatch for one fill dataset, or header auto-key suppression."""
        if label:
            swatch = swatch_color or color_token
            self.lines_gle.append(
                f"    {dataset} keyfill {swatch} key {self._quote_gle_key(label)}"
            )
            self._finish_legend_entry(label)
        elif has_header:
            self.lines_gle.append(f'    {dataset} key ""')

    def add_fill_from_file(
        self,
        data_file: str,
        x_col: int,
        y1_col: int,
        y2_col: Optional[int] = None,
        color: str = "LIGHTBLUE",
        label: Optional[str] = None,
        swatch_color: Optional[str] = None,
        target: Optional[str] = None,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
    ):
        """Add a fill file reference from per-field keywords.

        The keyword form of :meth:`add_file_series` for ``series_type
        'fill'``: each argument is the :class:`~gleplot.series.FileSeries`
        field of the same name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.FileSeries` and call :meth:`add_file_series` instead.
        """
        _warn_keyword_form("add_fill_from_file", "FileSeries", "add_file_series")
        series = FileSeries(
            series_type="fill",
            data_file=data_file,
            x_col=x_col,
            y1_col=y1_col,
            y2_col=y2_col,
            color=color,
            label=label,
            swatch_color=swatch_color,
            target=target,
            xmin=xmin,
            xmax=xmax,
            ymin=ymin,
            ymax=ymax,
        )
        self.add_file_series(series)

    def _add_fill_file_series(self, series: Series):
        """A fill that references columns in an external data file.

        Used for a ``fill`` the recognizer could not resolve; see
        :meth:`_add_bar_file_series`. ``target`` selects ``fill x1,dN``,
        ``fill dN,x2`` or ``fill dN``. Absent ``target`` is the two-curve
        ``fill dA,dB`` and needs ``y2_col``.
        """
        data_file = series["data_file"]
        x_col = series["x_col"]
        y1_col = series["y1_col"]
        y2_col = series.get("y2_col")
        color = series.get("color", "LIGHTBLUE")
        label = series.get("label")
        swatch_color = series.get("swatch_color")
        target = series.get("target")
        clip = {name: series.get(name) for name in ("xmin", "xmax", "ymin", "ymax")}
        d1_name = self._new_dataset()
        if target in ("x1", "x2", "polygon"):
            self.lines_gle.append(
                f"    data {_format_data_filename(data_file)} "
                f"{d1_name}=c{x_col},c{y1_col}" + self._data_read_clause(series)
            )
            if target == "x1":
                head = f"x1,{d1_name}"
            elif target == "x2":
                head = f"{d1_name},x2"
            else:
                head = d1_name
            self._append_fill(head, color, clip)
            self._fill_key(d1_name, color, label, swatch_color, False)
            return
        d2_name = self._new_dataset()
        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} "
            f"{d1_name}=c{x_col},c{y1_col} {d2_name}=c{x_col},c{y2_col}"
            + self._data_read_clause(series)
        )
        self._append_fill(f"{d1_name},{d2_name}", color, clip)
        self._fill_key(d1_name, color, label, swatch_color, False)

    def add_fill_between(
        self,
        x: np.ndarray,
        y1: np.ndarray,
        y2: Optional[np.ndarray],
        data_file: str,
        color: str = "LIGHTBLUE",
        alpha: float = 1.0,
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
        binding: Optional[ColumnBinding] = None,
        label: Optional[str] = None,
        swatch_color: Optional[str] = None,
        target: Optional[str] = None,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
    ):
        """Add a fill from per-field keywords.

        The keyword form of :meth:`add_fill`: each argument is the
        :class:`~gleplot.series.FillSeries` field of the same name, and
        ``binding`` is passed through.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.FillSeries` and call :meth:`add_fill` instead.
        """
        _warn_keyword_form("add_fill_between", "FillSeries", "add_fill")
        series = FillSeries(
            x=x,
            y1=y1,
            y2=y2,
            data_file=data_file,
            color=color,
            alpha=alpha,
            offset=offset,
            column_names=column_names,
            label=label,
            swatch_color=swatch_color,
            target=target,
            xmin=xmin,
            xmax=xmax,
            ymin=ymin,
            ymax=ymax,
        )
        self.add_fill(series, binding=binding)

    def add_fill(self, series: Series, binding: Optional[ColumnBinding] = None):
        """
        Add a filled region: between two curves, to an axis, or a polygon.

        Parameters
        ----------
        series : FillSeries
            The resolved series: its arrays are present (see
            :meth:`SourceResolution.data`). ``x``, ``y1``, ``data_file``,
            ``color`` and ``alpha`` are required; every other field is read
            with the default its absence has always meant.
        binding : ColumnBinding, optional
            Present when this series was resolved from a provider table; its
            columns then go into a sidecar shared with the other series on
            that table (see :meth:`_write_columns`).

        Notes
        -----
        How the fields are emitted:

        - ``alpha``: below 1, ``color`` is re-expressed as a GLE
          ``rgba255(...)`` colour expression (:func:`gleplot.colors.
          apply_alpha`) so the transparency is real in the generated script;
          rendering it requires GLE's ``-cairo`` device (SPEC §6.1/§10.6,
          :meth:`gleplot.figure.Figure.requires_cairo`). At ``alpha >= 1.0``
          ``color`` is written verbatim, unchanged from every pre-Cairo-support
          ``.gle`` this method has ever produced.
        - ``column_names``: the sidecar header row (e.g. ``['x', 'upper',
          'lower']``). GLE's ``fill dA,dB color X`` command (like ``bar``) has
          no ``key`` option of its own, but the two datasets it references
          still go through the generic dataset-key mechanism (they're
          registered via the same "used dataset" bookkeeping as any ``dN``
          display command), so a header row would still risk an auto-key on
          either one. An unlabelled fill neutralizes both with standalone
          ``dN key ""`` statements when a header row is present (verified
          empirically byte-identical to the headerless case). A labelled fill
          puts ``keyfill`` and ``key`` on the first dataset instead: ``fill``
          does not copy its colour into ``key_fill`` the way ``bar`` does, so
          the swatch has to be named. The second dataset still gets
          ``key ""`` when a header would otherwise auto-key it.
        - ``label``: the legend label for that swatch.
        - ``target``: ``"x1"``, ``"x2"`` or ``"polygon"``. Absent keeps the
          two-curve ``fill dA,dB``. A single-curve form writes only ``x`` and
          ``y1``.
        - ``xmin``, ``xmax``, ``ymin``, ``ymax``: GLE's clip window. An
          absent edge is omitted. On ``target="x1"``, ``ymin`` is also the
          line the fill closes on.
        """
        x = series["x"]
        y1 = series["y1"]
        y2 = series.get("y2")
        data_file = series["data_file"]
        color = series["color"]
        alpha = series["alpha"]
        offset = series.get("offset", 0.0)
        column_names = series.get("column_names")
        label = series.get("label")
        swatch_color = series.get("swatch_color")
        target = series.get("target")
        xmin = series.get("xmin")
        xmax = series.get("xmax")
        ymin = series.get("ymin")
        ymax = series.get("ymax")
        single = target in ("x1", "x2", "polygon")
        if single:
            # Role name stays ``y1`` so a provider binding, which keys columns
            # by ARRAY_FIELDS, still finds the curve. The header text is
            # ``column_names`` (``x``, ``y``), not this role.
            roles: List[Tuple[str, Any]] = [("x", x), ("y1", y1)]
        else:
            roles = [("x", x), ("y1", y1), ("y2", y2)]
        cols = self._write_columns(data_file, roles, column_names, binding)
        has_header = bool(column_names) or binding is not None
        file_name = binding.data_file if binding is not None else data_file
        clip = {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax}

        d1_name = self._new_dataset()
        data_cmd = (
            f"    data {_format_data_filename(file_name)} "
            f"{d1_name}=c{cols[0]},c{cols[1]}"
        )
        d2_name: Optional[str] = None
        if not single:
            d2_name = self._new_dataset()
            data_cmd += f" {d2_name}=c{cols[0]},c{cols[2]}"
        self.lines_gle.append(data_cmd)

        # A non-zero offset shifts the curve (both edges of a band) at plot
        # time, leaving the .dat file raw. The keyed dataset is the shifted one.
        fill_a = self._apply_offset(d1_name, offset) if offset else d1_name
        if single:
            if target == "x1":
                head = f"x1,{fill_a}"
            elif target == "x2":
                head = f"{fill_a},x2"
            else:
                head = fill_a
            fill_b = None
        else:
            assert d2_name is not None  # assigned above whenever not single
            fill_b = self._apply_offset(d2_name, offset) if offset else d2_name
            head = f"{fill_a},{fill_b}"

        # The keyfill token is that same colour text, so a round trip does
        # not rewrite rgba255(...) or a plain name.
        color_token = apply_alpha(color, alpha)
        self._append_fill(head, color_token, clip)
        self._fill_key(fill_a, color_token, label, swatch_color, has_header)
        if fill_b is not None and has_header:
            self.lines_gle.append(f'    {fill_b} key ""')

    def add_text(
        self,
        x: float,
        y: float,
        text: str,
        color: str = "BLACK",
        fontsize: Optional[float] = None,
        halign: str = "left",
        box_color: Optional[str] = None,
        valign: str = "center",
        rotation: Optional[float] = None,
        xy: Optional[Sequence[float]] = None,
        arrow: Optional[str] = None,
        arrowstyle: Optional[str] = None,
        arrow_color: str = "BLACK",
        arrow_linewidth: Optional[float] = None,
    ):
        """Add a text annotation from per-field keywords.

        The keyword form of :meth:`add_text_annotation`: ``halign`` and
        ``valign`` are the :class:`~gleplot.series.TextAnnotation` fields
        ``ha`` and ``va``, and every other argument is the field of the same
        name.

        Deprecated, and removed in a future major release: build a
        :class:`~gleplot.series.TextAnnotation` and call
        :meth:`add_text_annotation` instead.
        """
        _warn_keyword_form("add_text", "TextAnnotation", "add_text_annotation")
        series = TextAnnotation(
            x=x,
            y=y,
            text=text,
            color=color,
            fontsize=fontsize,
            ha=halign,
            va=valign,
            box_color=box_color,
            rotation=rotation,
            xy=xy,
            arrow=arrow,
            arrowstyle=arrowstyle,
            arrow_color=arrow_color,
            arrow_linewidth=arrow_linewidth,
        )
        self.add_text_annotation(series)

    @classmethod
    def _text_write_lines(cls, series: Series, name: Optional[str]) -> List[str]:
        """The ``write`` of a text at the current point, boxed and rotated.

        ``series`` is a :class:`~gleplot.series.TextAnnotation`; ``name``
        names the box, for an annotation arrow to ``join``.
        """
        box_color = series.get("box_color")
        rotation = series.get("rotation")
        # Same zero cut as ``_format_number``: an angle it would print as ``0``
        # is not a rotation, and emitting ``begin rotate 0`` would not round
        # trip back to an absent ``rotation`` field.
        angle = None
        if rotation is not None:
            try:
                angle = float(rotation)
            except (TypeError, ValueError):
                angle = None
            if angle is not None and (not math.isfinite(angle) or abs(angle) < 1e-10):
                angle = None
        lines: List[str] = []
        if angle is not None:
            lines.append(f"begin rotate {cls._format_number(angle)}")
        boxed = bool(box_color) or name is not None
        if boxed:
            head = "begin box"
            if box_color:
                head += f" fill {box_color}"
            head += f" add {text_box_pad_token()} nobox"
            if name is not None:
                head += f" name {name}"
            lines.append(head)
        lines.append(f'write "{cls._escape_gle_string(series["text"])}"')
        if boxed:
            lines.append("end box")
        if angle is not None:
            lines.append("end rotate")
        return lines

    def add_figure_text(self, series: Series) -> None:
        """Write a figure-level text (``Figure.text`` / ``Figure.suptitle``).

        ``series`` is a :class:`~gleplot.series.TextAnnotation` whose ``x``
        and ``y`` are figure fractions, placed with ``pagewidth()`` and
        ``pageheight()`` so the fractions stay in the script as written.
        Each text is its own ``gsave``/``grestore`` group that restates its
        colour and justification: the page-level state it starts from is
        whatever the script before it left. The recognizer takes a group
        back only when :meth:`figure_text_lines` reproduces it exactly.
        """
        self.lines_gle.extend(self.figure_text_lines(series))

    @classmethod
    def figure_text_lines(cls, series: Series) -> List[str]:
        """The GLE lines of one figure-level text, ``gsave`` to ``grestore``."""
        lines = ["gsave"]
        fontsize = series.get("fontsize")
        if fontsize is not None:
            hei = cls._format_number(fontsize_pt_to_cm(float(fontsize)))
            lines.append(f"set hei {hei}")
        lines.append(f"set color {series.get('color') or 'BLACK'}")
        just = text_align_to_just(series.get("ha", "left"), series.get("va", "center"))
        lines.append(f"set just {just}")
        lines.append(
            f"amove {cls._page_fraction('pagewidth', series['x'])} "
            f"{cls._page_fraction('pageheight', series['y'])}"
        )
        lines.extend(cls._text_write_lines(series, None))
        lines.append("grestore")
        return lines

    def add_text_annotation(self, series: Series):
        """Add text annotation in graph data coordinates or axes fractions.

        ``series`` is a :class:`~gleplot.series.TextAnnotation`: ``x``,
        ``y`` and ``text`` are required, and every other field is read with
        the default its absence has always meant.

        With ``transform='axes'``, ``x`` and ``y`` are fractions of the frame
        GLE drew, in the ``KEY_ANCHOR_X``/``_Y`` form a ``bbox_to_anchor``
        legend uses. The text is written after ``end graph``, where
        ``xgmin`` ... ``ygmax`` still describe this graph.

        ``va`` selects the other half of GLE's ``set just`` (``t``/``c``/``b``).
        ``rotation`` is degrees counter-clockwise. GLE's ``begin rotate`` turns
        about the current point, so the block opens after ``amove``: that point
        is the alignment point, and closing the block keeps the next label
        unrotated. A background is ``begin box fill`` around the ``write``
        only. The ``amove`` stays outside the box; on GLE 4.3.10 that is the
        form that compiles in graph-data coordinates (the box is measured from
        the text, not from an ``xg()`` expression). ``nobox`` omits the
        outline, which would otherwise be stroked in the current text colour
        and is not a separate model field.

        With ``arrow`` (an ``Axes.annotate`` arrow to ``xy``), the ``write``
        is always boxed and the box named, then ``join`` draws from that
        name to a ``save``d point at ``xy``, so GLE clips the arrow at the
        box edge. The arrow's ``set`` lines sit in their own
        ``gsave``/``grestore``: they never touch the sticky text state.
        """
        x = series["x"]
        y = series["y"]
        color = series.get("color", "BLACK")
        fontsize = series.get("fontsize")
        halign = series.get("ha", "left")
        valign = series.get("va", "center")
        xy = series.get("xy")
        arrow = series.get("arrow")
        arrowstyle = series.get("arrowstyle")
        arrow_color = series.get("arrow_color", "BLACK")
        arrow_linewidth = series.get("arrow_linewidth")

        if fontsize is not None:
            hei_cm = self._format_number(fontsize_pt_to_cm(float(fontsize)))
            if hei_cm != self._text_state_hei_cm:
                self._pending_graph_text_lines.append(f"set hei {hei_cm}")
                self._text_state_hei_cm = hei_cm

        if color and color != self._text_state_color:
            self._pending_graph_text_lines.append(f"set color {color}")
            self._text_state_color = color

        just = text_align_to_just(halign, valign)
        if just != self._text_state_just:
            self._pending_graph_text_lines.append(f"set just {just}")
            self._text_state_just = just

        if series.get("transform") == "axes":
            position = (
                f"{KEY_ANCHOR_X.format(self._format_number(x))} "
                f"{KEY_ANCHOR_Y.format(self._format_number(y))}"
            )
        else:
            position = f"xg({self._format_number(x)}) yg({self._format_number(y)})"
        self._pending_graph_text_lines.append(f"amove {position}")
        name = None
        if arrow is not None and xy is not None:
            self._annotation_count += 1
            name = f"ann{self._annotation_count}"
        self._pending_graph_text_lines.extend(self._text_write_lines(series, name))
        if name is not None:
            assert xy is not None
            tip = f"{name}_xy"
            lines = [
                f"amove xg({self._format_number(xy[0])}) "
                f"yg({self._format_number(xy[1])})",
                f"save {tip}",
                "gsave",
                f"set color {arrow_color}",
            ]
            if arrow_linewidth is not None:
                lwidth = linewidth_pt_to_cm(float(arrow_linewidth))
                lines.append(f"set lwidth {self._format_number(lwidth)}")
            # A restored dict bypasses Axes.annotate: fall back to the
            # values the recognizer accepts, as text_align_to_just does.
            sep = arrow if arrow in ARROW_JOIN_SEPS else "->"
            if sep != "-":
                style = arrowstyle if arrowstyle in ARROW_TIP_STYLES else "filled"
                lines.append(f"set arrowstyle {style}")
            lines.append(f"join {name} {sep} {tip}")
            lines.append("grestore")
            self._pending_graph_text_lines.extend(lines)

    def add_wedge(self, series: Series) -> None:
        """Queue one pie slice for after ``end graph``.

        ``series`` is a :class:`~gleplot.series.Wedge`. It goes out as a
        ``gleplot_wedge`` call (:data:`WEDGE_SUB`) in the same deferred block
        as the text annotations: GLE 4.3.10's PostScript driver loses the
        font of text written inside a graph-block ``draw`` after the first
        one, because it caches the font across the ``gsave``/``grestore``
        GLE wraps each ``draw`` in.

        The sub writes its text in the current height and colour. The height
        is set here through the same sticky tracker the annotations use. The
        colour is the block's starting ``BLACK``, because the figure writes
        an axes' wedges before its annotations. The sub leaves ``set just``
        changed, so that tracker is cleared and the next annotation states
        its own.
        """
        fontsize = series.get("fontsize")
        if fontsize is not None:
            hei_cm = self._format_number(fontsize_pt_to_cm(float(fontsize)))
            if hei_cm != self._text_state_hei_cm:
                self._pending_graph_text_lines.append(f"set hei {hei_cm}")
                self._text_state_hei_cm = hei_cm
        label = self._escape_gle_string(series.get("label") or "")
        autotext = self._escape_gle_string(series.get("autotext") or "")
        num = self._format_number
        self._pending_graph_text_lines.append(
            f"gleplot_wedge {num(series['x'])} {num(series['y'])} "
            f"{num(series['r'])} {num(series['theta1'])} {num(series['theta2'])} "
            f'"{self._escape_gle_string(series["color"])}" "{label}" '
            f'{num(series["labeldistance"])} "{autotext}" '
            f'{num(series["pctdistance"])}'
        )
        self._text_state_just = None

    def add_polar_frame(self, rmax: float) -> None:
        """Make the open graph block a polar axes out to radius ``rmax``.

        ``rmax`` is as written to the script (see :meth:`_format_number`).
        Draws the grid (:data:`POLAR_SUB`) in layer
        :data:`POLAR_GRID_LAYER` and queues the tick labels for after ``end
        graph``, ahead of the axes' other deferred text. Every dataset drawn
        after this goes through :meth:`_polar_dataset`. Call it after
        :meth:`add_axes`, whose window must already be the one
        :func:`polar_window` gives.
        """
        num = self._format_number
        step = polar_ring_step(rmax)
        self.lines_gle.append(f"    begin layer {POLAR_GRID_LAYER}")
        self.lines_gle.append(
            f"        draw gleplot_polar_grid {num(rmax)} {num(step)}"
        )
        self.lines_gle.append("    end layer")
        self._pending_graph_text_lines.append(
            f"gleplot_polar_labels {num(rmax)} {num(step)} "
            f'{polar_label_decimals(step)} "{polar_degree_mark(self.style.usetex)}"'
        )
        self._polar_graph = True

    def _polar_dataset(self, source: str) -> str:
        """``let dK = dJ*cos(x),dJ*sin(x)``: ``source`` as (theta, r) -> (x, y).

        Returns ``dK``, the dataset to draw. GLE keeps the points in their
        order, so a curve that winds back on itself is drawn as given.
        """
        target = self._new_dataset()
        self.lines_gle.append(f"    let {target} = {source}*cos(x),{source}*sin(x)")
        return target

    def add_box(self, series: Series) -> None:
        """Queue one box of a box plot for after ``end graph``.

        ``series`` is a :class:`~gleplot.series.Box`. It goes out as a
        ``gleplot_box`` call (:data:`BOX_SUB`), then a ``gleplot_box_flier``
        call per flier and a ``gleplot_box_mean`` call when it has a mean,
        in the deferred block the text annotations use, so the boxes are
        drawn over the graph unclipped, like the pie wedges.
        """
        num = self._format_number
        x = num(float(series["x"]))
        values = " ".join(
            num(float(series[key]))
            for key in ("width", "capwidth", "whislo", "q1", "med", "q3", "whishi")
        )
        self._pending_graph_text_lines.append(f"gleplot_box {x} {values}")
        for flier in series["fliers"]:
            self._pending_graph_text_lines.append(
                f"gleplot_box_flier {x} {num(float(flier))}"
            )
        if series.get("mean") is not None:
            self._pending_graph_text_lines.append(
                f"gleplot_box_mean {x} {num(float(series['mean']))}"
            )

    def add_image(self, series: Series) -> None:
        """Draw a placed image as a layered ``draw`` call in the graph block.

        ``series`` is a :class:`~gleplot.series.PlacedImage`. The call is a
        :data:`IMAGE_SUBS` sub chosen by the file's extension, in layer
        :data:`IMAGE_LAYER`, so the image lies under the grid and the data
        and is clipped to the frame.
        """
        sub = image_sub_name(series["file"])
        extent = " ".join(self._format_number(float(v)) for v in series["extent"])
        self.lines_gle.append(f"    begin layer {IMAGE_LAYER}")
        self.lines_gle.append(
            f"        draw {sub} {_quote_filename(series['file'])} {extent}"
        )
        self.lines_gle.append("    end layer")

    def add_rug(self, series: Series) -> None:
        """Queue one rug for after ``end graph``.

        ``series`` is a :class:`~gleplot.series.Rug`. It goes out as one
        ``gleplot_xrug`` or ``gleplot_yrug`` call (:data:`RUG_SUB`) per
        value, in the deferred block the box plots use, so the ticks are
        drawn on the frame unclipped.
        """
        num = self._format_number
        rest = (
            f'{num(float(series["length"]))} "{series["position"]}" '
            f'"{self._escape_gle_string(series["color"])}" '
            f'{num(linewidth_pt_to_cm(float(series["linewidth"])))}'
        )
        for value in series["ticks"]:
            self._pending_graph_text_lines.append(
                f"gleplot_{series['axis']}rug {num(float(value))} {rest}"
            )

    def set_legend_breaks(self, breaks: Set[int]) -> None:
        """Where ``key separator`` falls, as 1-based legend-entry counts.

        Set before any series is emitted. ``_finish_legend_entry`` counts
        real key labels in emission order and writes the separator after
        the entries named here.
        """
        self._legend_breaks = set(breaks)
        self._legend_entry_count = 0

    def _finish_legend_entry(self, label: Optional[str]) -> None:
        """Count one legend entry and emit ``key separator`` at a column break.

        A falsy label is not an entry: ``key ""`` only suppresses a header
        auto-key. The separator is its own statement, inserted into GLE's
        dataset order at this point (``do_key``'s SEPARATOR branch), so it
        has to follow the entry's display command and precede the next one.
        """
        if not label:
            return
        self._legend_entry_count += 1
        if self._legend_entry_count in self._legend_breaks:
            self.lines_gle.append("    key separator")

    def add_legend(self, key: KeyOptions):
        """The graph-block ``key`` line for a legend drawn inside the graph.

        Position and every option go on the single ``key`` line (see
        ``_parse_key_command``); a second ``key pos`` line would compete with
        this one on re-emit. Column breaks are separate ``key separator``
        statements emitted beside the entries, because that is where GLE
        inserts them into the dataset order. ``key.anchor`` and
        ``key.labelcolor`` need a ``begin key`` block
        (:meth:`queue_external_legend`) and are not read here.
        """
        cmd = f"    key pos {self._key_position(key)}"
        for option in self._key_options(key):
            cmd += f" {option}"
        self.lines_gle.append(cmd)

    def _key_position(self, key: KeyOptions) -> str:
        """GLE's short form of the key position (long forms are mapped)."""
        pos = key.position if key.position is not None else self.graph.legend_position
        return KEY_POSITIONS_LONG_TO_SHORT.get(pos, pos)

    def _key_options(self, key: KeyOptions) -> List[str]:
        """The key options after the position, in emission order.

        ``offset`` is GLE's displacement INWARD from the anchored corner, in
        cm (verified against GLE 4.3.10 by compiled pixel-diff): for a
        right-anchored key positive dx moves LEFT, for a top-anchored key
        positive dy moves DOWN. ``absolute`` overwrites it, so an anchored
        key is given none (``Figure._write_legend``). ``fontsize`` points become ``hei`` cm, and ``None``
        omits ``hei`` so GLE uses the current ``set hei``. ``background`` is
        the box fill; ``boxcolor`` is not, it strokes the fill swatch
        (``g_box_stroke`` in the 4.3.10 source). The spacing lengths are
        font-size multiples, so they scale by the key's text height.
        """
        options: List[str] = []
        if key.offset is not None:
            dx, dy = key.offset
            options.append(
                f"offset {self._format_number(float(dx))} "
                f"{self._format_number(float(dy))}"
            )
        if key.fontsize is not None:
            options.append(
                f"hei {self._format_number(fontsize_pt_to_cm(float(key.fontsize)))}"
            )
        if not key.frameon:
            options.append("nobox")
        if key.compact:
            options.append("compact")
        if key.background:
            options.append(f"background {key.background}")
        hei = fontsize_pt_to_cm(
            float(key.fontsize if key.fontsize is not None else self.style.fontsize)
        )
        for name, word in LEGEND_SPACING_TO_KEY.items():
            if name not in key.spacing:
                continue
            length = self._format_number(float(key.spacing[name]) * hei)
            options.append(
                f"{word} {length} {length}" if word == "margins" else f"{word} {length}"
            )
        return options

    def add_key_off(self):
        """Suppress the graph key entirely.

        GLE draws a key whenever any dataset carries a ``key "label"``
        attribute, even without a ``key pos`` command, so an explicit
        ``key off`` is required to hide the legend for labeled series.
        """
        self.lines_gle.append("    key off")

    def legend_swatch(
        self,
        color: str,
        linestyle: Optional[str] = None,
        linewidth: Optional[float] = None,
        marker: Optional[str] = None,
        markersize: Optional[float] = None,
        fill: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> str:
        """The ``begin key`` entry tail for one series.

        A fill swatch is ``fill COLOR``, plus ``pattern P`` for a hatched
        bar. Not its ``background``: inside ``begin key`` that keyword is
        the background of the whole key, so the swatch hatches on white. A line swatch restates the colour,
        width and ``lstyle`` the dataset command would, which is what makes
        ``entry->lstyle`` non-empty so the key draws a stroke
        (``key.cpp``). A marker-only series is ``marker`` / ``msize`` /
        ``color``, the same tokens as the dataset line.
        """
        if fill is not None:
            return f"fill {fill}" + (f" pattern {pattern}" if pattern else "")
        parts: List[str] = []
        has_line = linestyle not in ("none", "None", "", " ", None)
        if has_line:
            parts.append(f"color {color}")
            width = self._guide_lwidth_cm(
                1.0 if linewidth is None else float(linewidth)
            )
            parts.append(f"lwidth {self._format_number(width)}")
            style = self._lstyle_for(linestyle or "-")
            if style:
                parts.append(f"lstyle {style}")
        if marker:
            parts.append(f"marker {marker}")
            if markersize is not None:
                parts.append(f"msize {self._format_number(markersize)}")
            if not has_line:
                parts.append(f"color {color}")
        return " ".join(parts)

    def queue_external_legend(
        self, entries: List[tuple], breaks: Set[int], key: KeyOptions
    ) -> None:
        """Queue a ``begin key`` block for the graph that is about to close.

        ``entries`` is ``(series, label, swatch)`` in matplotlib addition
        order. A model fit whose label shows its results gets the key text
        :meth:`add_fit` built, which reads the variables the fit has set.
        ``breaks`` are the 1-based counts after which a column ends, the
        same split as :func:`legend_column_breaks`. The block is written
        by :meth:`end_graph`, after ``end graph``, because that is the
        graph ``position`` and the ``absolute`` coordinates of an anchored
        key are measured against.
        """
        corner = self._key_position(key)
        if key.anchor is not None:
            x, y = (self._format_number(float(v)) for v in key.anchor)
            place = [
                f"    justify {corner}",
                f"    absolute {KEY_ANCHOR_X.format(x)} {KEY_ANCHOR_Y.format(y)}",
            ]
        else:
            place = [f"    position {corner}"]
        self._external_legend = self._key_block_lines(place, entries, breaks, key)

    def add_figure_legend(
        self, entries: List[tuple], breaks: Set[int], key: KeyOptions
    ) -> None:
        """A ``begin key`` block placed on the page (``Figure.legend``).

        ``entries`` and ``breaks`` are as for :meth:`queue_external_legend`.
        ``key.anchor`` is the figure-fraction point the ``key.position``
        corner sits on, ``None`` for that corner of the page. Written outside
        every graph, so it is placed with ``justify`` and an ``absolute``
        page point (:meth:`figure_legend_absolute`), never ``position``,
        which GLE measures against the last graph.
        """
        place = [
            f"    justify {self._key_position(key)}",
            f"    {self.figure_legend_absolute(key, self.style.fontsize)}",
        ]
        self.lines_gle.extend(self._key_block_lines(place, entries, breaks, key))

    @classmethod
    def figure_legend_absolute(cls, key: KeyOptions, fontsize: float) -> str:
        """The ``absolute X Y`` line of a figure legend, without its indent.

        The point is ``pagewidth()``/``pageheight()`` times the anchor
        fraction, moved inward from the anchored side by half the key's
        text height: matplotlib's default ``borderaxespad`` of 0.5 font
        sizes between the legend and the edge it is anchored to.
        ``key.position`` must be set; ``fontsize`` is the page's text height
        in points, used when ``key.fontsize`` is not.
        """
        position = cast(str, key.position)
        corner = KEY_POSITIONS_LONG_TO_SHORT.get(position, position)
        words = KEY_POSITIONS_SHORT_TO_LONG[corner].split()
        fx, fy = key.anchor if key.anchor is not None else legend_corner(corner)
        size = key.fontsize if key.fontsize is not None else fontsize
        pad = 0.5 * fontsize_pt_to_cm(float(size))
        dx = pad if "left" in words else -pad if "right" in words else 0.0
        dy = -pad if "top" in words else pad if "bottom" in words else 0.0
        return (
            f"absolute {cls._page_fraction('pagewidth', fx, dx)} "
            f"{cls._page_fraction('pageheight', fy, dy)}"
        )

    @classmethod
    def _page_fraction(cls, size: str, fraction: float, shift: float = 0.0) -> str:
        """``size()*fraction``, then ``+shift`` cm unless it prints as 0."""
        expr = f"{size}()*{cls._format_number(float(fraction))}"
        step = cls._format_number(abs(shift))
        if step != "0":
            expr += f"{'-' if shift < 0 else '+'}{step}"
        return expr

    def _key_block_lines(
        self, place: List[str], entries: List[tuple], breaks: Set[int], key
    ) -> List[str]:
        """A ``begin key`` block: ``place`` lines, options, then the entries."""
        lines = ["begin key", *place]
        lines.extend(f"    {option}" for option in self._key_options(key))
        textcolor = f" textcolor {key.labelcolor}" if key.labelcolor else ""
        for i, (series, label, swatch) in enumerate(entries, start=1):
            quoted = self._fit_keys.get(id(series)) or self._quote_gle_key(label)
            if swatch:
                lines.append(f"    text {quoted} {swatch}{textcolor}")
            else:
                lines.append(f"    text {quoted}{textcolor}")
            if i in breaks:
                lines.append("    separator")
        lines.append("end key")
        return lines

    def finalize(
        self,
        include_graph_end: bool = True,
        graph_passthrough: Optional[List[str]] = None,
        passthrough_trailer: Optional[List[str]] = None,
    ):
        """Add closing statements.

        Parameters
        ----------
        include_graph_end : bool
            If True (default), appends 'end graph' for single-plot
            backward compatibility. Set False for multi-subplot layout.
        graph_passthrough : list of str, optional
            Raw lines belonging inside the single-plot graph block, passed
            through to :meth:`end_graph` (ignored if ``include_graph_end`` is
            False -- multi-subplot layouts close their own graph blocks
            directly via :meth:`end_graph`).
        passthrough_trailer : list of str, optional
            Raw lines recovered from a parsed ``.gle`` file that belong at
            the very end of the script, after all graph blocks and deferred
            text annotations. Omitted entirely when falsy.
        """
        if include_graph_end:
            self.end_graph(passthrough=graph_passthrough)
        if passthrough_trailer:
            self.lines_gle.extend(passthrough_trailer)

    def get_gle_content(self) -> str:
        """Get complete GLE script content."""
        return "\n".join(self.lines_gle)

    def write_files(self, output_dir: str, base_filename: str = "plot"):
        """
        Write GLE script and data files.

        Parameters
        ----------
        output_dir : str
            Directory for output files
        base_filename : str
            Base name for files (without extension)

        Returns
        -------
        dict
            Mapping of filename to full path
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        files = {}

        # Write GLE script
        gle_file = out_dir / f"{base_filename}.gle"
        gle_file.write_text(self.get_gle_content(), encoding="utf-8")
        files["script"] = gle_file

        # Write data files
        for data_file, content in self.data_files.items():
            data_path = out_dir / data_file
            data_path.write_text(content, encoding="utf-8")
            files[data_file] = data_path

        return files

    # -- contour / heatmap emission -------------------------------------

    def add_z_sidecar(self, filename: str, z: np.ndarray, extent, origin: str):
        """Write a raw ``.z`` grid sidecar.

        Header ``! nx <nx> ny <ny> xmin <x0> xmax <x1> ymin <y0> ymax <y1>``
        followed by ``ny`` lines of ``nx`` values, ROW ymin FIRST (GLE's ``.z``
        format is y-increasing). For ``origin='upper'`` the array rows are
        flipped so row 0 (the top) is written last. Numbers use the writer's
        canonical formatter, single-space separated -- deterministic, so the
        sidecar is fixed-point safe.
        """
        z = np.asarray(z, dtype=float)
        ny, nx = z.shape
        x0, x1, y0, y1 = self._format_extent(extent)
        header = f"! nx {nx} ny {ny} xmin {x0} xmax {x1} ymin {y0} ymax {y1}"
        rows = z[::-1] if origin == "upper" else z
        lines = [header]
        lines.extend(self._format_grid(rows))
        content = "\n".join(lines) + "\n"
        self.data_files[filename] = content
        self.raw_sidecars.add(filename)

    def add_points_sidecar(
        self, filename: str, x: np.ndarray, y: np.ndarray, z: np.ndarray
    ):
        """Write a raw scattered ``x y z`` triples sidecar (no header).

        GLE's ``fitz`` reads raw whitespace-separated triples, one per line, in
        the given order (no sorting). Deterministic / fixed-point safe.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        z = np.asarray(z, dtype=float)
        columns = [self._format_column(c) for c in (x, y, z)]
        lines = [" ".join(row) for row in zip(*columns)]
        content = "\n".join(lines) + "\n"
        self.data_files[filename] = content
        self.raw_sidecars.add(filename)

    def add_sub_defs(self, sub_texts: List[str]):
        """Append self-contained subroutine definitions to the script.

        Each entry is a full multi-line ``sub ... end sub`` block. A blank
        line separates consecutive subs (and follows the last), matching the
        script's readable block spacing.

        Also marks where a sub definition belongs, so the guide subs -- whose
        need is only known once the graph blocks have been written -- can be
        spliced in here later (:meth:`finalize_guide_subs`).
        """
        for text in sub_texts:
            self.lines_gle.extend(text.split("\n"))
            self.lines_gle.append("")
        self._sub_defs_mark = len(self.lines_gle)

    def finalize_guide_subs(self) -> None:
        """Splice in the guide subs the guides actually drawn this write need.

        Called once, after every graph block is written: which guides take
        :mod:`gleplot.guides`' draw form is decided against limits that are
        still unresolved when :meth:`add_sub_defs` runs, so the definitions
        are inserted at that method's mark rather than appended in place.
        (GLE hoists subs, so a later definition would compile too -- the
        splice is for a readable script and a stable byte layout, not for
        the engine.)

        Deterministic in the *set* of subs used, never in discovery order.
        """
        if not self.used_guide_subs:
            return
        lines: List[str] = []
        for text in guide_sub_texts(sorted(self.used_guide_subs)):
            lines.extend(text.split("\n"))
            lines.append("")
        at = self._sub_defs_mark
        self.lines_gle[at:at] = lines

    def add_fitz_block(self, points_file: str, extent, gridsize, ncontour):
        """Emit a ``begin fitz`` .. ``end fitz`` block (before ``begin graph``).

        ``step = (hi - lo) / (n - 1)`` for each axis so the grid spans the
        extent inclusively at ``gridsize`` nodes.
        """
        x0, x1, y0, y1 = extent
        nx, ny = gridsize
        xstep = (x1 - x0) / (nx - 1)
        ystep = (y1 - y0) / (ny - 1)
        self.lines_gle.append("begin fitz")
        self.lines_gle.append(f"   data {_quote_filename(points_file)}")
        self.lines_gle.append(
            f"   x from {self._format_number(x0)} to {self._format_number(x1)} "
            f"step {self._format_number(xstep)}"
        )
        self.lines_gle.append(
            f"   y from {self._format_number(y0)} to {self._format_number(y1)} "
            f"step {self._format_number(ystep)}"
        )
        if ncontour is not None:
            self.lines_gle.append(f"   ncontour {int(ncontour)}")
        self.lines_gle.append("end fitz")

    def add_contour_block(self, z_file: str, levels):
        """Emit a ``begin contour`` .. ``end contour`` block.

        ``levels`` is ``None`` (GLE default 10 levels) or an explicit list of
        z-values emitted as ``values v1 v2 ...``.
        """
        self.lines_gle.append("begin contour")
        self.lines_gle.append(f"   data {_quote_filename(z_file)}")
        if levels:
            vals = " ".join(self._format_number(v) for v in levels)
            self.lines_gle.append(f"   values {vals}")
        self.lines_gle.append("end contour")

    def add_heatmap_data(self, series: Series):
        """Write a heatmap's sidecar and, for scattered samples, its ``fitz``.

        Emitted before the graph that draws it (see :meth:`add_heatmap`).
        ``series`` is the resolved :class:`~gleplot.series.HeatmapSeries`. A
        ``'grid'`` heatmap writes its ``z`` array, at ``extent`` and in
        ``origin`` row order, as a ``.z`` sidecar. A ``'points'`` heatmap
        writes its ``x``/``y``/``zpts`` samples and a ``begin fitz`` block
        that grids them at ``gridsize`` over ``extent``; ``ncontour`` is
        omitted, so GLE's default applies. A ``'function'`` heatmap has no
        data, so it writes nothing.
        """
        if series["source"] == "function":
            return
        data_file = series["data_file"]
        if series["source"] == "points":
            self.add_points_sidecar(data_file, series["x"], series["y"], series["zpts"])
            self.add_fitz_block(data_file, series["extent"], series["gridsize"], None)
        elif series.get("cells"):
            self.add_cells_sidecar(series)
        elif "levels" in series:
            self.add_nodes_sidecar(series)
            self.add_contourf_sub(series)
        else:
            self.add_z_sidecar(
                data_file, series["z"], series["extent"], series["origin"]
            )

    def add_cells_sidecar(self, series: Series):
        """Write a ``pcolormesh`` heatmap's ``.z`` so each value fills its cell.

        GLE's ``colormap ... interpolate nearest`` gives a pixel the value of
        node ``round(n * (x - xmin) / (xmax - xmin))``, so node ``k`` covers
        ``xmin + (k - 1/2, k + 1/2) * (xmax - xmin) / n``, and the bitmap
        stops at ``xmin`` and ``xmax``. With the header half a cell outside
        the mesh and the first row and column repeated, node ``k`` covers
        cell ``k - 1`` exactly; the graph window clips the half cell left
        over at each end.

        The line under the header, which GLE skips as a comment, holds the
        mesh's own edges at the precision every extent is written with, and
        the header is computed from those written edges, so a reload reads
        the same mesh back and writes the same file. The header carries more
        digits than an extent, so the cells land on edges that the shorter
        form would round away.
        """
        fmt = self._format_number
        edges = self._format_extent(series["extent"])
        x0, x1, y0, y1 = (float(v) for v in edges)
        z = np.asarray(series["z"], dtype=float)
        ny, nx = z.shape
        hx, hy = (x1 - x0) / nx / 2, (y1 - y0) / ny / 2
        bounds = (fmt(v, 12) for v in (x0 - hx, x1 + hx, y0 - hy, y1 + hy))
        lines = [
            "! nx {} ny {} xmin {} xmax {} ymin {} ymax {}".format(
                nx + 1, ny + 1, *bounds
            ),
            "{} xmin {} xmax {} ymin {} ymax {}".format(CELLS_MARKER, *edges),
        ]
        for cells in self._format_grid(np.vstack([z[:1], z]), joined=False):
            lines.append(" ".join([cells[0]] + cells))
        self.data_files[series["data_file"]] = "\n".join(lines) + "\n"
        self.raw_sidecars.add(series["data_file"])

    def add_nodes_sidecar(self, series: Series):
        """Write a ``contourf`` heatmap's ``.z`` with its nodes where they are.

        GLE's ``colormap`` puts node ``k`` of ``n`` at ``xmin + k * (xmax -
        xmin) / n``, one spacing short of ``xmax``, while ``begin contour``
        puts the last node on ``xmax``. Writing ``xmax`` (and ``ymax``) one
        node spacing past the last node makes the colormap's nodes the grid's
        own, so the bands sit where the levels cross the grid; the graph
        window, which the grid's extent sets, clips the extra spacing.

        The line under the header, which GLE skips, holds the grid's edges
        as every extent is written, and the header is computed from those
        written edges with more digits, as for
        :meth:`add_cells_sidecar`.
        """
        fmt = self._format_number
        edges = self._format_extent(series["extent"])
        x0, x1, y0, y1 = (float(v) for v in edges)
        z = np.asarray(series["z"], dtype=float)
        ny, nx = z.shape
        bounds = (
            fmt(v, 12)
            for v in (x0, x1 + (x1 - x0) / (nx - 1), y0, y1 + (y1 - y0) / (ny - 1))
        )
        lines = [
            "! nx {} ny {} xmin {} xmax {} ymin {} ymax {}".format(nx, ny, *bounds),
            "{} xmin {} xmax {} ymin {} ymax {}".format(NODES_MARKER, *edges),
        ]
        lines.extend(self._format_grid(z))
        self.data_files[series["data_file"]] = "\n".join(lines) + "\n"
        self.raw_sidecars.add(series["data_file"])

    def add_contourf_sub(self, series: Series):
        """Define the palette sub a ``contourf`` heatmap's colormap calls.

        The colormap passes each pixel's value through unscaled (``zmin 0
        zmax 1``), so the sub compares it with the levels themselves. A value
        above one level and up to the next takes the colour ``cmap`` gives
        the middle of that band on the ``vmin``..``vmax`` scale (the outer levels when unset), as
        matplotlib colours a band. Below the first level and above the last
        it is white, or with ``extend`` the colormap's end colour. When GLE's
        smoothing would not put the band edges on the levels
        (:func:`contourf_bands_fit`), the sub maps the value straight onto the
        colormap instead, inside the same limits.

        The sub's first line, a comment GLE skips, holds the series' colouring
        as written, which is what the recognizer reads back. The sub goes
        before the graph that calls it: GLE finds a sub wherever it is.
        """
        fmt = self._format_number
        name = f"gleplot_contourf{len(self._contourf_subs) + 1}"
        self._contourf_subs[series["data_file"]] = name
        cmap = series["cmap"]
        extend = series["extend"]
        levels = [fmt(v) for v in series["levels"]]
        head = f"{CONTOURF_MARKER} cmap {cmap} extend {extend}"
        for key in ("vmin", "vmax"):
            if series[key] is not None:
                head += f" {key} {fmt(series[key])}"
        head += " levels " + " ".join(levels)
        lv = [float(v) for v in levels]
        lo = lv[0] if series["vmin"] is None else float(fmt(series["vmin"]))
        hi = lv[-1] if series["vmax"] is None else float(fmt(series["vmax"]))
        call = f"gleplot_{cmap}"
        white = "rgb(1, 1, 1)"
        under = f"{call}(0)" if extend in ("min", "both") else white
        over = f"{call}(1)" if extend in ("max", "both") else white
        lines = [
            f"sub {name} z",
            f"   {head}",
            f"   if z < {levels[0]} then return {under}",
            f"   if z > {levels[-1]} then return {over}",
        ]
        if contourf_bands_fit(series):
            tone = [
                fmt(min(max(((a + b) / 2 - lo) / (hi - lo), 0.0), 1.0))
                for a, b in zip(lv, lv[1:])
            ]
            lines.append(f"   local t = {tone[0]}")
            for level, t in zip(levels[1:-1], tone[1:]):
                lines.append(f"   if z > {level} then t = {t}")
            lines.append(f"   return {call}(t)")
        else:
            lines.append(f"   return {call}((z-({fmt(lo)}))/{fmt(hi - lo)})")
        lines.append("end sub")
        self.lines_gle.extend(lines)
        self.lines_gle.append("")

    def add_heatmap(self, series: Series):
        """Emit a heatmap's ``colormap`` statement inside its graph block.

        ``series`` is the resolved :class:`~gleplot.series.HeatmapSeries`.
        ``cmap`` picks the colour mode: ``'gray'`` writes no colour clause,
        ``'rainbow'`` is GLE's built-in ``color``, and any other name is the
        ``gleplot_<cmap>`` palette sub. A ``'function'`` heatmap maps its
        ``expression``, written bare: GLE reads a quoted one as a file name.
        """
        cmap = series["cmap"]
        cmap_mode: Tuple[str, Optional[str]]
        if cmap == "gray":
            cmap_mode = ("gray", None)
        elif cmap == "rainbow":
            cmap_mode = ("color", None)
        else:
            cmap_mode = ("palette", f"gleplot_{cmap}")
        if series["source"] == "function":
            operand = series["expression"]
        else:
            operand = _quote_filename(_grid_z_file(series))
        if "levels" in series:
            name = self._contourf_subs[series["data_file"]]
            self.add_colormap(
                operand, series["pixels"], ("palette", name), 0, 1, False, "bicubic"
            )
            return
        self.add_colormap(
            operand,
            series["pixels"],
            cmap_mode,
            series["vmin"],
            series["vmax"],
            series["invert"],
            series["interpolation"],
        )

    def add_colorbar(self, series: Series):
        """Emit the colorbar sub call after a series' graph, if it has one.

        ``series`` is the resolved :class:`~gleplot.series.HeatmapSeries`, or
        a colour-mapped :class:`~gleplot.series.ScatterSeries`; its ``cmap``
        names the palette and its ``colorbar`` dict (see
        :meth:`gleplot.Figure.colorbar`) holds the call's range, size, format
        and label. A series without one writes nothing.

        A vertical bar starts at ``xg(xgmax)+sep yg(ygmin)`` and spans the
        graph's height; a horizontal one hangs from ``xg(xgmin) yg(ygmin)-sep``
        and spans its width. Both subs take ``wd``/``hi`` as the bar's x/y
        extent, so the graph-sized one is an expression. Named-argument call
        style (``zmin V zmax V ...``); note GLE matches named args by the
        parameter name WITHOUT the ``$`` suffix.
        """
        cb = series.get("colorbar")
        if not cb:
            return
        fmt = self._format_number
        sep = float(cb["sep"])
        thickness = fmt(cb["width"])
        if cb.get("orientation") == "horizontal":
            # ``yg(ygmin)--S`` would not parse back, so a negative gap flips
            # the operator instead.
            below = f"-{fmt(sep)}" if sep >= 0 else f"+{fmt(-sep)}"
            self.lines_gle.append(f"amove xg(xgmin) yg(ygmin){below}")
            sub = "gleplot_colorbar_h"
            size = f"wd xg(xgmax)-xg(xgmin) hi {thickness}"
        else:
            self.lines_gle.append(f"amove xg(xgmax)+{fmt(sep)} yg(ygmin)")
            sub = "gleplot_colorbar_v"
            size = f"wd {thickness} hi yg(ygmax)-yg(ygmin)"
        lbl = self._escape_gle_string(cb.get("label") or "")
        self.lines_gle.append(
            f"{sub} zmin {fmt(cb['zmin'])} zmax {fmt(cb['zmax'])} "
            f"zstep {fmt(cb['zstep'])} "
            f'palette "{_pal.palette_call_name(series["cmap"])}" {size} '
            f'format "{cb["format"]}" label "{lbl}"'
        )

    def add_contour_data(self, series: Series):
        """Write a contour's sidecar, ``fitz`` if scattered, and contour block.

        Emitted before the graph that draws it (see :meth:`add_contour`).
        ``series`` is the resolved :class:`~gleplot.series.ContourSeries`. A
        ``'grid'`` contour writes its ``z`` array, at ``extent``, as a ``.z``
        sidecar (always ``origin='lower'``). A ``'points'`` contour writes its
        ``x``/``y``/``zpts`` samples and a ``begin fitz`` block that grids
        them at ``gridsize`` over ``extent``, with ``ncontour`` when set. The
        ``begin contour`` block then traces ``levels``, or GLE's default
        levels when there are none.
        """
        data_file = series["data_file"]
        if series["source"] == "points":
            self.add_points_sidecar(data_file, series["x"], series["y"], series["zpts"])
            self.add_fitz_block(
                data_file, series["extent"], series["gridsize"], series["ncontour"]
            )
        else:
            self.add_z_sidecar(data_file, series["z"], series["extent"], "lower")
        self.add_contour_block(_grid_z_file(series), series["levels"])

    def add_contour(self, series: Series):
        """Draw a contour's traced lines inside its graph block.

        ``series`` is the resolved :class:`~gleplot.series.ContourSeries`;
        the lines are the ``-cdata.dat`` file its contour block generates,
        drawn in ``color`` at ``linewidth`` and ``linestyle``.
        """
        cdata = _grid_z_file(series)[:-2] + "-cdata.dat"
        self.add_contour_line(
            cdata, series["color"], series["linewidth"], series["linestyle"]
        )

    def add_contour_labels(self, series: Series):
        """Emit the contour-label sub call after a contour's graph, if asked.

        ``series`` is the resolved :class:`~gleplot.series.ContourSeries`.
        With ``clabel`` set, the labels come from the ``-clabels.dat`` file
        its contour block generates, formatted with ``clabel_fmt``; without
        it nothing is written.
        """
        if not series.get("clabel"):
            return
        clabels = _grid_z_file(series)[:-2] + "-clabels.dat"
        self.add_clabel_call(clabels, series["clabel_fmt"])

    def add_colormap(
        self,
        operand: str,
        pixels,
        cmap_mode,
        vmin,
        vmax,
        invert: bool,
        interpolation: str,
    ):
        """Emit the ``colormap`` statement inside a graph block.

        ``operand`` is what the colormap maps, as written: a quoted ``.z``
        file name or a bare expression. Clause order (fixed): operand, px,
        py, [color], [invert], [zmin v],
        [zmax v], [palette name], [interpolate mode]. ``cmap_mode`` is
        ``('color', None)`` for rainbow, ``('palette', 'gleplot_x')`` for a
        named palette, or ``('gray', None)`` for grayscale (no clause).
        """
        px, py = pixels
        cmd = f"    colormap {operand} {int(px)} {int(py)}"
        mode, name = cmap_mode
        if mode == "color":
            cmd += " color"
        if invert:
            cmd += " invert"
        if vmin is not None:
            cmd += f" zmin {self._format_number(vmin)}"
        if vmax is not None:
            cmd += f" zmax {self._format_number(vmax)}"
        if mode == "palette":
            cmd += f" palette {name}"
        if interpolation == "nearest":
            cmd += " interpolate nearest"
        self.lines_gle.append(cmd)

    def add_contour_line(
        self, cdata_file: str, color: str, linewidth: float, lstyle: Optional[int]
    ):
        """Emit the ``data``/``dN line`` pair that draws a contour's polylines.

        ``cdata_file`` is the ``-cdata.dat`` file GLE generates from the
        contour block; it is plotted as a ``line`` dataset.
        """
        d_name = self._new_dataset()
        self.lines_gle.append(f"    data {_quote_filename(cdata_file)} {d_name}=c1,c2")
        if linewidth == 0 or linewidth == 1:
            gle_lwidth = linewidth_pt_to_cm(self.style.default_linewidth)
        else:
            gle_lwidth = linewidth_pt_to_cm(linewidth)
        cmd = (
            f"    {d_name} line color {color} "
            f"lwidth {self._format_number(gle_lwidth)}"
        )
        if lstyle is not None:
            cmd += f" lstyle {int(lstyle)}"
        self.lines_gle.append(cmd)

    def add_clabel_call(self, clabels_file: str, fmt: str):
        """Emit the post-graph contour-label sub call."""
        self.lines_gle.append("amove 0 0")
        self.lines_gle.append(
            f"gleplot_contour_labels file {_quote_filename(clabels_file)} "
            f'format "{fmt}"'
        )

    @staticmethod
    def _color_clause(color: Optional[str]) -> str:
        """`` color <color>`` for a dataset line, or nothing for ``None``.

        ``None`` is a recovered dataset line that set no colour; GLE draws it
        in the current colour.
        """
        return "" if color is None else f" color {color}"

    def _lwidth_clause(self, linewidth: Optional[float]) -> str:
        """`` lwidth <cm>`` for a width in points, or nothing for ``None``.

        0 or 1 means the style's default width. ``None`` is a recovered
        dataset line that set no width; GLE draws it at the current width.
        """
        if linewidth is None:
            return ""
        if linewidth == 0 or linewidth == 1:
            gle_lwidth = linewidth_pt_to_cm(self.style.default_linewidth)
        else:
            gle_lwidth = linewidth_pt_to_cm(linewidth)
        return f" lwidth {self._format_number(gle_lwidth)}"

    # -- guides drawn against GLE's own range (G17) ----------------------

    def _lstyle_for(self, linestyle: str) -> int:
        """The GLE ``lstyle`` number for a matplotlib linestyle.

        Reads the very same ``style.line_style_*`` fields
        :meth:`add_line` reads, so the two emission forms of a guide
        cannot disagree about what ``'--'`` looks like. ``0`` is GLE's own
        "no style set" sentinel and is what a lineless guide
        (``linestyle='none'``) is emitted with -- :mod:`gleplot.guides`'
        subs draw nothing for it, matching the dataset form's do-nothing
        dataset.
        """
        return {
            "-": self.style.line_style_solid,
            "--": self.style.line_style_dashed,
            ":": self.style.line_style_dotted,
            "-.": self.style.line_style_dashdot,
        }.get(linestyle, 0)

    def _guide_lwidth_cm(self, linewidth: float) -> float:
        """A guide's ``lwidth`` in cm, with :meth:`add_line`'s defaulting."""
        if linewidth == 0 or linewidth == 1:
            return linewidth_pt_to_cm(self.style.default_linewidth)
        return linewidth_pt_to_cm(linewidth)

    def _add_guide_draw(self, layer: int, sub_name: str, args: List[str]) -> None:
        """Emit one ``begin layer N`` / ``draw <sub> args`` / ``end layer``.

        The layer is what reproduces today's stacking exactly; see
        :mod:`gleplot.guides` for the numbers and their provenance.
        """
        self.used_guide_subs.add(sub_name)
        self.lines_gle.append(f"    begin layer {layer}")
        self.lines_gle.append(f"        draw {sub_name} " + " ".join(args))
        self.lines_gle.append("    end layer")

    def add_refline(self, series: Series):
        """Draw a reference line as a layered ``draw`` call (G17).

        ``series`` is the :class:`~gleplot.series.RefLine` declaration; its
        ``orient``, ``value``, ``span_lo``/``span_hi``, ``color``,
        ``linestyle``, ``linewidth`` and ``label`` go to
        :meth:`add_refline_draw`, which says when this form is used.
        """
        self.add_refline_draw(
            series["orient"],
            series["value"],
            series["span_lo"],
            series["span_hi"],
            series["color"],
            series["linestyle"],
            series["linewidth"],
            series["label"],
        )

    def add_refline_dataset(self, series: Series, line: Series):
        """Draw a reference line as a marked two-point dataset.

        ``series`` is the :class:`~gleplot.series.RefLine` declaration and
        ``line`` the :class:`~gleplot.series.LineSeries` that
        ``Axes.materialize_reflines`` built from it. The marker (see
        :meth:`add_refline_marker`) goes immediately before the line's
        ``data`` statement, which is how a re-read file binds the two.
        """
        self.add_refline_marker(
            series["orient"], series["value"], series["span_lo"], series["span_hi"]
        )
        self.add_line(line)

    def add_refline_draw(
        self,
        orient: str,
        value: float,
        span_lo: float,
        span_hi: float,
        color: str,
        linestyle: str,
        linewidth: float,
        label: Optional[str],
    ):
        """Emit an ``axvline``/``axhline`` as a layered ``draw`` call (G17).

        Used only when the axis the guide spans has an unresolved bound, so
        the fraction ``span_lo``..``span_hi`` has to be taken against the
        range GLE picks rather than one gleplot invents -- see
        :meth:`gleplot.axes.Axes.guide_needs_engine_range`.

        A labelled guide also gets a **data-free** ``dN`` display line
        carrying the same style and the ``key`` text. A ``draw`` owns no
        dataset and so cannot carry a key itself; an empty dataset can, and
        (verified against GLE 4.3.10) draws no ink and takes no part in
        autoscale, so the legend entry survives without the literal dataset
        coming back.
        """
        gle_lwidth = self._guide_lwidth_cm(linewidth)
        self._add_guide_draw(
            REFLINE_LAYER,
            guide_sub_name("refline", orient),
            [
                self._format_number(value),
                self._format_number(span_lo),
                self._format_number(span_hi),
                f'"{self._escape_gle_string(color)}"',
                self._format_number(gle_lwidth),
                str(self._lstyle_for(linestyle)),
                f'"{self._escape_gle_string(label or "")}"',
            ],
        )
        if label:
            self.add_guide_key(color, linestyle, gle_lwidth, label)

    def add_span(self, series: Series):
        """Draw a span as a layered ``draw`` call (G17).

        ``series`` is the :class:`~gleplot.series.Span` declaration; its
        ``orient``, ``start``/``end``, ``span_lo``/``span_hi``, ``color``,
        ``alpha``, ``label`` and ``swatch_color`` go to
        :meth:`add_span_draw`.
        """
        self.add_span_draw(
            series["orient"],
            series["start"],
            series["end"],
            series["span_lo"],
            series["span_hi"],
            series["color"],
            series["alpha"],
            series["label"],
            swatch_color=series.get("swatch_color"),
        )

    def add_span_dataset(self, series: Series, fill: Series):
        """Draw a span as a marked fill.

        ``series`` is the :class:`~gleplot.series.Span` declaration and
        ``fill`` the :class:`~gleplot.series.FillSeries` that
        ``Axes.materialize_spans`` built from it. The marker (see
        :meth:`add_span_marker`) goes immediately before the fill's ``data``
        statement, which is how a re-read file binds the two.
        """
        self.add_span_marker(
            series["orient"],
            series["start"],
            series["end"],
            series["span_lo"],
            series["span_hi"],
            series["label"],
        )
        self.add_fill(fill)

    def add_span_draw(
        self,
        orient: str,
        start: float,
        end: float,
        span_lo: float,
        span_hi: float,
        color: str,
        alpha: float,
        label: Optional[str],
        swatch_color: Optional[str] = None,
    ):
        """Emit an ``axvspan``/``axhspan`` as a layered ``draw`` call (G17).

        A labelled band also gets a data-free ``dN keyfill ... key`` line.
        The ``draw`` owns no dataset, and ``fill`` cannot carry ``key``;
        an empty dataset with ``keyfill`` draws the swatch and (verified
        on GLE 4.3.10) does not move the autoscale. ``label`` still travels
        as the sub's last argument too, so the draw block stays
        self-describing. ``alpha`` is folded into the colour exactly as
        :meth:`add_fill` folds it, via
        :func:`gleplot.colors.apply_alpha`, and the swatch uses that same
        token.
        """
        color_token = apply_alpha(color, alpha)
        self._add_guide_draw(
            SPAN_LAYER,
            guide_sub_name("span", orient),
            [
                self._format_number(start),
                self._format_number(end),
                self._format_number(span_lo),
                self._format_number(span_hi),
                f'"{self._escape_gle_string(color_token)}"',
                f'"{self._escape_gle_string(label or "")}"',
            ],
        )
        if label:
            self.add_fill_key(swatch_color or color_token, label)

    def add_guide_key(
        self, color: str, linestyle: str, lwidth_cm: float, label: str
    ) -> str:
        """Emit the data-free ``dN`` line that carries a guide's legend entry.

        Token order mirrors :meth:`add_line`'s line branch so the legend
        swatch is identical to the one the dataset form produces; the only
        difference is that no ``data`` statement ever gives this dataset any
        rows. Returns the dataset name.
        """
        d_name = self._new_dataset()
        cmd = f"    {d_name}"
        if linestyle not in ("none", "None", "", " ", None):
            cmd += self._line_token()
            cmd += f" color {color} lwidth {self._format_number(lwidth_cm)}"
            if linestyle == "--":
                cmd += f" lstyle {self.style.line_style_dashed}"
            elif linestyle == ":":
                cmd += f" lstyle {self.style.line_style_dotted}"
            elif linestyle == "-.":
                cmd += f" lstyle {self.style.line_style_dashdot}"
        cmd += f" key {self._quote_gle_key(label)}"
        self.lines_gle.append(cmd)
        self._finish_legend_entry(label)
        return d_name

    def add_fill_key(self, color: str, label: str) -> str:
        """Data-free fill swatch for a guide that has no dataset of its own.

        ``do_dataset_key`` copies ``key_fill`` onto the legend entry, so a
        dataset that is never drawn still contributes a filled square when
        it carries ``keyfill`` and a non-empty ``key``. Returns the dataset
        name. ``color`` is the same token the fill or the span sub uses.
        """
        d_name = self._new_dataset()
        self.lines_gle.append(
            f"    {d_name} keyfill {color} key {self._quote_gle_key(label)}"
        )
        self._finish_legend_entry(label)
        return d_name

    # -- the dataset form's provenance marker (G18-lite) ------------------

    def _add_guide_marker(self, kind: str, orient: str, args: List[str]) -> None:
        """Emit one ``! gleplot:guide ...`` comment line.

        A comment, so the engine never sees it (verified by compiled
        pixel-diff, ``tests/integration/test_guide_marker_compiles.py``), and
        the bytes it precedes are unchanged. The grammar, and the rule for
        what may appear in ``args`` at all, live in :mod:`gleplot.guides`.
        """
        self.lines_gle.append(
            f"    {GUIDE_MARKER_PREFIX} {kind} {orient} " + " ".join(args)
        )

    def _guide_marker_pair(self, first: float, second: float) -> str:
        """``a,b`` -- a marker's two-number field, comma-joined and spaceless.

        The comma is not decoration: GLE's lexer reads a leading sign as an
        operator, so ``-4 -3`` would collect back as the single expression
        ``-7``. See :mod:`gleplot.guides`.
        """
        return f"{self._format_number(first)},{self._format_number(second)}"

    def add_refline_marker(
        self, orient: str, value: float, span_lo: float, span_hi: float
    ) -> None:
        """Mark the two-point dataset that follows as an ``axvline``/``axhline``.

        Emitted immediately before the guide's own ``data`` statement, by
        :meth:`add_refline_dataset`, for every guide
        that materializes (i.e. every guide NOT routed to the draw form by
        ``Axes.guide_needs_engine_range``).
        """
        self._add_guide_marker(
            "refline",
            orient,
            [
                "value",
                self._format_number(value),
                "extent",
                self._guide_marker_pair(span_lo, span_hi),
            ],
        )

    def add_span_marker(
        self,
        orient: str,
        start: float,
        end: float,
        span_lo: float,
        span_hi: float,
        label: Optional[str],
    ) -> None:
        """Mark the fill that follows as an ``axvspan``/``axhspan``.

        ``label`` is emitted only when the band has one: ``fill dA,dB`` has no
        ``key`` option of its own, so unlike a refline's label a band's has
        nowhere else to live -- and unlike a refline's it is dropped rather
        than drawn (the dataset form's legend behaviour is unchanged; see
        :meth:`add_fill`).
        """
        args = [
            "range",
            self._guide_marker_pair(start, end),
            "extent",
            self._guide_marker_pair(span_lo, span_hi),
        ]
        if label:
            args += [GUIDE_MARKER_LABEL, f'"{self._escape_gle_string(label)}"']
        self._add_guide_marker("span", orient, args)

    def _row_order(
        self,
        x_array: np.ndarray,
        has_line: bool,
        shared: bool = False,
        smooth_mode: Optional[str] = None,
    ) -> np.ndarray:
        """Return the order in which a series' points are written to its .dat.

        The caller's order, always -- except for the one case that cannot use
        it. GLE's ``smooth`` fits a piecewise cubic *as a function of x* and
        needs the points in ascending x; handed a non-monotonic dataset it
        draws a tangle. So the rows are sorted by x when, and only when, this
        series' effective smooth mode is exactly ``smooth`` and it draws a
        line (see :meth:`_effective_smooth_mode`).

        ``smoothm`` is pointedly excluded. It is GLE's *multi-valued* variant
        (``fitbez(data, multi=true)``, i.e. a parametric fit), chosen
        precisely for curves that are not functions of x -- a hysteresis
        loop, a closed contour. Sorting those by x is the very corruption
        ``smoothm`` exists to avoid, so a ``smoothm`` series keeps the
        caller's point order like any other. ``svg_smooth`` likewise: the
        Savitzky-Golay filter is a moving window over the rows as given, and
        reordering them would change the filtered result.

        Everywhere else -- which, since smoothing became opt-in, is the great
        majority of series -- the caller's point order is both the drawing
        order and the .dat file's row order, as in matplotlib. It has to be:
        a series whose x is non-monotonic by design (a hysteresis loop, a
        parametric or closed curve, a time-ordered trace that doubles back)
        is a different figure once sorted, and the data file on disk would no
        longer be the data that was passed in.

        The sort is stable, so points sharing an x value keep their input
        order rather than being permuted by an unstable quicksort.

        ``shared`` marks a series whose columns go into a sidecar it shares
        with other series on the same provider table. A shared file has ONE
        row order -- the table's -- so no per-series permutation is possible
        there; the rows go out as the table holds them, and a smoothed
        table-backed series is the caller's responsibility to keep monotonic
        (exactly as it would be for a hand-written ``.dat``).
        """
        smooths = self._effective_smooth_mode(smooth_mode) == "smooth"
        if has_line and smooths and not shared:
            return np.argsort(x_array, kind="stable")
        return np.arange(len(x_array))

    def _effective_smooth_mode(self, smooth_mode: Optional[str] = None) -> str:
        """The smooth mode one dataset is actually emitted with.

        Per-series beats figure-wide, and *absent* beats neither: a series
        with no ``smooth_mode`` field (every series written before SPEC 14.7,
        and every kind but :class:`~gleplot.series.LineSeries` today) defers
        to ``GLEGraphConfig.smooth_curves``, which is what keeps those files
        byte-identical. A series that declares a mode wins -- including
        ``'none'`` on a figure whose default is smoothed, which is the whole
        point of a per-series override.

        Returns a member of :data:`~gleplot.series.SMOOTH_MODES`, never
        ``None``, so no caller has to re-derive the fallback.
        """
        mode = normalize_smooth_mode(smooth_mode)
        if mode is not None:
            return mode
        # The figure-wide default skips a polar graph: GLE smooths the drawn
        # x and y, which need not be in order there ("Cannot SMOOTH: X
        # values out of sequence").
        return (
            "smooth" if self.graph.smooth_curves and not self._polar_graph else "none"
        )

    def _line_token(
        self,
        smooth_mode: Optional[str] = None,
        svg_smooth: Optional[int] = None,
        line_mode: Optional[str] = None,
    ) -> str:
        """Return the ``line`` token, with smoothing, for a display command.

        Every line-drawing path in this writer goes through here, so the
        smoothing qualifiers are decided in exactly one place.

        GLE's ``smooth`` replaces the polyline through the data with a fitted
        piecewise-cubic spline: the drawn curve then passes near, not through,
        the points, and it invents structure between them (overshoot on steep
        steps, ringing around noise). That is an interpolation of the data,
        not the data, so it is **off unless asked for** -- set
        ``GLEGraphConfig(smooth_curves=True)`` on a figure, or
        ``GlobalConfig.graph.smooth_curves = True`` globally, to opt in, or
        set the per-series ``smooth_mode`` (SPEC 14.7) on the one series that
        wants it.

        Two independent clauses, one token order
        ----------------------------------------

        ``smooth_mode`` (``smooth``/``smoothm``) and ``svg_smooth m`` are
        separate options in GLE's ``dn`` grammar and may both appear on one
        line -- but **only in this order**. ``graph2.cpp``'s keyword loop is a
        left-to-right state machine: its ``SVG_SMOOTH`` branch sets the filter
        *and clears* ``smooth``/``smoothm``, while its ``SMOOTH``/``SMOOTHM``
        branches leave ``svg_smooth`` alone. So ``d1 line smooth svg_smooth 2``
        renders identically to ``d1 line svg_smooth 2`` (the ``smooth`` is
        dead), and only ``d1 line svg_smooth 2 smooth`` applies both. Verified
        against GLE 4.3.10 by rendering all three. This method therefore
        always emits ``svg_smooth m`` before the mode token.

        The iteration count is always emitted explicitly. The manual writes
        the parameter as optional (``dn svg_smooth [m]``), but GLE's parser
        unconditionally evaluates the next token as an expression, so a
        trailing bare ``svg_smooth`` is a syntax error ("constant, function,
        or unary operator expected").

        Paths that deliberately never smooth, whatever the setting:

        - ``add_fill`` -- GLE's ``fill dA,dB`` command takes no
          ``smooth`` qualifier, so a band edge is always a polyline.
        - ``add_contour_line`` -- the ``-cdata.dat`` polylines come out of
          GLE's own contouring of the gridded surface; splining them would
          move the level away from the surface it was computed from.
        - the marker-only branch of :meth:`add_line` -- a series with
          ``linestyle='none'`` draws no curve, so there is none to smooth.
          (GLE's own ``smooth`` keyword would *switch the line on*; emitting
          it there would draw a line the caller explicitly turned off.)

        ``smooth`` also constrains point order (it needs monotonic x); that
        consequence is handled in :meth:`_row_order`, the only place a series
        is ever reordered.

        A line mode (``steps`` / ``fsteps`` / ``hist`` / ``bar`` /
        ``impulses``) is a separate assignment in the same keyword loop, so
        its position relative to ``smooth`` does not change which flags are
        set. It does change the picture when both are on: ``transform_data``
        runs ``fitbez`` before ``drawLine`` switches on the mode, and the
        steps are then drawn through the spline. Callers that want the
        discrete join pass ``smooth_mode='none'`` (what :meth:`Axes.plot`
        stores on a line-mode series, and what a file-series line mode
        passes here).
        It is emitted immediately after ``line`` -- ``line steps``, the
        manual's spelling -- and only when the series asked for one. A
        ``None`` mode leaves the token exactly `` line``, which is what
        every pre-existing caller writes.
        """
        token = " line"
        if line_mode is not None:
            if line_mode not in LINE_MODES:
                raise ValueError(
                    f"line_mode must be one of {LINE_MODES}, got {line_mode!r}"
                )
            token += f" {line_mode}"
        iterations = normalize_svg_smooth(svg_smooth)
        if iterations is not None:
            token += f" svg_smooth {iterations}"
        mode = self._effective_smooth_mode(smooth_mode)
        if mode != "none":
            token += f" {mode}"
        return token

    @staticmethod
    def _axis_direction(
        lo: Optional[float], hi: Optional[float]
    ) -> Tuple[Optional[float], Optional[float], bool]:
        """``(min, max, negate)`` for a possibly-descending limit pair.

        matplotlib inverts an axis by giving it descending limits
        (``set_ylim(3, 1)``); GLE spells the same thing as an ascending range
        plus the ``negate`` keyword, which mirrors data coordinates within the
        range -- ``graph2.cpp``'s ``fny()``, and ``graph_ygraph()`` with it, so
        the ``xg()``/``yg()`` coordinates of text annotations follow the flip
        too. GLE will not accept the descending range directly: "Error:
        illegal range for yaxis: min = 3 max = 1".

        So the descending pair IS the model (no separate inverted flag to
        serialize, and the recognizer recovers one by reading ``negate`` back
        as a descending pair), and this is the one place it turns into GLE.

        Log axes never reach here descending: GLE's ``negate`` mirrors
        *linearly* before taking the logarithm, which spaces the decades
        nonsensically, so ``Figure._normalize_inverted_log_limits`` undoes the
        inversion before emission.
        """
        if lo is not None and hi is not None and lo > hi:
            return hi, lo, True
        return lo, hi, False

    @staticmethod
    def _format_number(val: float, precision: int = 6) -> str:
        """Format number for GLE output."""
        if isinstance(val, (int, float)):
            if abs(val) < 1e-10:
                return "0"
            if abs(val) > 1e10:
                return f"{val:.3e}"
            # Use general format with reasonable precision
            formatted = f"{val:.{precision}g}"
            return formatted
        return str(val)

    @classmethod
    def _axis_range(cls, lo: Optional[float], hi: Optional[float], log: bool) -> str:
        """The `` min .. max ..`` of an axis line.

        The pair is one column; on a log axis each end is its own, since a
        linear span says nothing about how far a decade-wide limit may move.
        """
        if log:
            lo_text, hi_text = cls._format_column([lo]) + cls._format_column([hi])
        else:
            lo_text, hi_text = cls._format_column([lo, hi])
        return (f" min {lo_text}" if lo is not None else "") + (
            f" max {hi_text}" if hi is not None else ""
        )

    @classmethod
    def _format_extent(cls, extent: Sequence[float]) -> List[str]:
        """``(xmin, xmax, ymin, ymax)`` as text, each axis's pair one column."""
        return cls._format_column(extent[:2]) + cls._format_column(extent[2:4])

    @classmethod
    def _format_grid(cls, z: np.ndarray, joined: bool = True) -> List[Any]:
        """A 2-D grid's rows as text, the whole grid formatted as one column."""
        texts = cls._format_column(z.ravel())
        nx = z.shape[1]
        rows = [texts[k : k + nx] for k in range(0, len(texts), nx)]
        return [" ".join(row) for row in rows] if joined else rows

    @classmethod
    def _format_column(cls, values: Iterable[Any]) -> List[str]:
        """Numbers that belong together (a data column, an axis range) as text.

        Each value is written by :meth:`_format_number` unless that loses
        data: two values written alike, a value written ``0``, or a value
        above 1e10 cut short, when what is lost exceeds the column's
        tolerance (:meth:`_column_tolerance`). Then every number of the
        column is written with the fewest significant figures, at least six,
        that keep it within half the tolerance, so a data column and the
        axis range set around it round alike.

        The written numbers are iterated to a fixed point, so a file read
        back chooses the same precision and writes the same text.
        Non-numeric entries (``*``) and non-finite ones are written by
        :meth:`_format_number` as they always were.
        """
        values = list(values)
        index = [
            i
            for i, v in enumerate(values)
            if isinstance(v, (int, float)) and math.isfinite(v)
        ]
        numeric = set(index)
        out = [
            "" if i in numeric else cls._format_number(v) for i, v in enumerate(values)
        ]
        if not index:
            return out
        ordered, where = np.unique(
            np.asarray([values[i] for i in index], dtype=float), return_inverse=True
        )
        texts = [cls._format_number(v) for v in ordered]
        precision = cls._column_precision(ordered, texts)
        while precision is not None:
            texts = cls._column_texts(ordered, precision)
            ordered = np.unique(np.asarray([float(t) for t in texts]))
            # Rounding can only merge values, never reorder them.
            where = np.searchsorted(ordered, [float(t) for t in texts])[where]
            texts = cls._column_texts(ordered, precision)
            settled = cls._column_precision(
                ordered, [cls._format_number(v) for v in ordered]
            )
            if settled == precision:
                break
            if settled is None:
                texts = [cls._format_number(v) for v in ordered]
            precision = settled
        for i, k in zip(index, where.ravel()):
            out[i] = texts[k]
        return out

    @staticmethod
    def _column_tolerance(ordered: np.ndarray) -> float:
        """The smallest difference in ``ordered`` (sorted) that is data.

        A millionth of the column's span: six significant figures of the
        range the values cover, so samples a millionth of a curve's height
        apart near a peak are not data, while timestamps a minute apart over
        a few minutes are.
        Never below 1e-12 of the largest magnitude, which is float noise
        (``cos(pi / 2)`` is ``6e-17``).
        """
        size = max(abs(ordered[0]), abs(ordered[-1]))
        return float(max(1e-6 * (ordered[-1] - ordered[0]), 1e-12 * size))

    @classmethod
    def _column_texts(cls, ordered: np.ndarray, precision: int) -> List[str]:
        """``ordered`` at ``precision`` significant figures.

        A value :meth:`_format_number` writes ``0`` stays ``0`` while it is
        within half the column's tolerance of it, so float noise is not
        written out and nothing is zeroed that was not zeroed before.
        """
        tol = cls._column_tolerance(ordered)
        return [
            "0" if abs(v) < 1e-10 and abs(v) <= tol / 2 else f"{v:.{precision}g}"
            for v in ordered
        ]

    @classmethod
    def _column_precision(cls, ordered: np.ndarray, texts: List[str]) -> Optional[int]:
        """None when ``texts``, the sorted distinct ``ordered`` as
        :meth:`_format_number` writes them, keep the column; else the precision.
        """
        tol = cls._column_tolerance(ordered)
        size = np.abs(ordered)
        if not (
            np.any((size < 1e-10) & (size > tol / 2))
            or any(
                abs(float(t) - v) > tol / 2
                for t, v, big in zip(texts, ordered, size > 1e10)
                if big
            )
            or cls._merges(ordered, texts, tol)
        ):
            return None
        for precision in range(6, 17):
            written = np.array(
                [float(t) for t in cls._column_texts(ordered, precision)]
            )
            if np.all(np.abs(written - ordered) <= tol / 2):
                return precision
        return 17

    @staticmethod
    def _merges(ordered: np.ndarray, texts: List[str], tol: float) -> bool:
        """Whether neighbours of ``ordered`` more than ``tol`` apart read alike."""
        same = np.array(texts[1:], dtype=object) == np.array(texts[:-1], dtype=object)
        return bool(np.any(same & (np.diff(ordered) > tol)))

    @staticmethod
    def _escape_gle_string(value: str) -> str:
        """Escape string for inclusion in GLE quoted text."""
        return str(value).replace('"', '\\"')

    @staticmethod
    def _quote_gle_key(label: str) -> str:
        """A double-quoted GLE string for a legend label.

        GLE 4.3.10 ends a string on a quote that is not immediately
        doubled (``Tokenizer.cpp``). A backslash does not keep the quote
        inside the string, so an embedded quote is written as two quote
        characters. A label with no quote is unchanged.
        """
        return '"' + str(label).replace('"', '""') + '"'

    @staticmethod
    def _key_clause(label: Optional[str], has_header: bool) -> str:
        """Build the trailing ``key "..."`` token for a dataset display line.

        GLE auto-detects a non-numeric first row of a data file as a column
        header (``auto_has_header`` in the GLE source) and, when it finds
        one, copies the header cell for a dataset's own column straight into
        that dataset's legend text -- even if the script never writes a
        ``key`` clause at all. An explicit ``key "..."`` (including the empty
        string ``key ""``) on the ``dN ...`` display line always overrides
        that auto-derived text, because GLE parses the ``data`` command
        first (setting the auto key) and the dataset's own attribute line
        second (whatever it sets wins). Verified empirically: rendering a
        labeled dataset is byte-identical with/without a header row, and an
        unlabeled dataset with an explicit ``key ""`` also renders
        byte-identical with/without a header row (both match the historical
        headerless-and-unlabeled rendering); only an unlabeled dataset with
        NO explicit key clause changes rendering when a header row is
        present (GLE silently invents a legend entry from the header text).

        So: whenever a header row is emitted for this series' data file,
        this ALWAYS returns a non-empty clause -- real label if given, else
        ``key ""`` to neutralize the auto-key -- to guarantee unchanged
        rendering regardless of header presence. When there is no header
        row, the historical behavior is preserved exactly: omit the clause
        entirely for an unlabeled series (empty string).
        """
        if label:
            return f" key {GLEWriter._quote_gle_key(label)}"
        if has_header:
            return ' key ""'
        return ""

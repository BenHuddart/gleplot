"""Figure class for gleplot."""

import numpy as np
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Tuple, Optional, Literal, Sequence, List
from .axes import Axes, _sanitize_data_stem, _validate_data_prefix
from .series import Series
from .brokenaxes import BrokenAxes
from .writer import (
    AxisStyle,
    DecimationPolicy,
    GLEWriter,
    SourceResolution,
    resolve_figure,
)
from .compiler import GLECompiler, SUFFIX_TO_COMPILE_FORMAT
from .cairo_support import cairo_font_warning, figure_requires_cairo
from .colors import rgb_to_gle
from .mathtext import mathtext_to_gle
from .config import GLEStyleConfig, GLEGraphConfig, GLEMarkerConfig, GlobalConfig
from .parser import metadata as _gle_metadata
from .parser.units import fontsize_pt_to_cm

#: Envelope identifiers for the gleplot project-file format.
PROJECT_FORMAT = "gleplot-project"

#: Version written by :meth:`Figure.to_dict`.
#:
#: 1 -- every series carries its own baked arrays.
#: 2 -- series may carry a ``data_source`` (:mod:`gleplot.sources`). A series
#:      WITHOUT one is inline, exactly as in version 1, so a version-2 dict
#:      for a figure built through the scripting API is identical to the
#:      version-1 dict it would have produced except for this integer.
PROJECT_VERSION = 2

#: Versions :meth:`Figure.from_dict` accepts. Version 1 is read as "every
#: series is :class:`~gleplot.sources.InlineData`", which needs no conversion
#: at all -- the absence of ``data_source`` already means exactly that.
SUPPORTED_PROJECT_VERSIONS = (1, 2)


def _refline_axis_values(ax, orient: str):
    """Data coordinates the guides of ``ax`` contribute to autoscaling.

    ``orient`` is ``'v'`` (vertical guides -> x coordinates) or ``'h'``
    (horizontal guides -> y coordinates). Only the guide's *data* coordinate
    counts: the extent along the other axis is an axes fraction, so feeding it
    back into autoscale would be circular.
    """
    values = []
    for entry in getattr(ax, "reflines", ()):
        if entry["orient"] == orient:
            values.append(float(entry["value"]))
    for entry in getattr(ax, "spans", ()):
        if entry["orient"] == orient:
            values.append(float(entry["start"]))
            values.append(float(entry["end"]))
    return values


def _plottable(values: np.ndarray, positive_only: bool) -> np.ndarray:
    """``values``, restricted to what the axis can actually show.

    With ``positive_only`` (a log axis) the non-positive entries are dropped,
    mirroring matplotlib, which masks them rather than refusing to autoscale.
    Without it this is the identity, so every ordinary axis is bounded by
    exactly the values it always was.
    """
    if not positive_only:
        return values
    return values[values > 0]


def _filtered_dataclass_kwargs(cls, data: dict) -> dict:
    """Filter ``data`` down to the keys ``cls`` (a dataclass) accepts.

    Used when reconstructing config dataclasses (:class:`GLEStyleConfig`,
    :class:`GLEGraphConfig`, :class:`GLEMarkerConfig`) from a project dict, so
    that unknown keys saved by a newer/older version of gleplot are ignored
    instead of raising ``TypeError`` -- consistent with the forward-compat
    guarantee documented on :meth:`Figure.from_dict`.
    """
    allowed = cls.__dataclass_fields__.keys()
    return {k: v for k, v in data.items() if k in allowed}


class Figure:
    """Matplotlib-like figure for GLE plotting.

    Parameters
    ----------
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (8, 6)
    dpi : int, optional
        Dots per inch. Default: 100
    style : GLEStyleConfig, optional
        Style configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.style` is taken at construction
        time -- see the "Global defaults are copied, not shared" note below.
        An explicitly passed ``style`` is stored by reference, as before.
    graph : GLEGraphConfig, optional
        Graph configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.graph` is taken at construction
        time (same note). An explicitly passed ``graph`` is stored by
        reference, as before.
    marker : GLEMarkerConfig, optional
        Marker configuration. If None, a COPY of
        :attr:`~gleplot.config.GlobalConfig.marker` is taken at construction
        time (same note). An explicitly passed ``marker`` is stored by
        reference, as before.

    Notes
    -----
    **Global defaults are copied, not shared.** ``GlobalConfig.style``/
    ``.graph``/``.marker`` are process-wide singletons. Setting
    ``GlobalConfig.style.font = 'helvetica'`` *before* creating a figure
    still changes that figure's default font, exactly as documented in
    :class:`gleplot.config.GlobalConfig`. But once a ``Figure`` exists, its
    ``style``/``graph``/``marker_config`` are independent objects (when no
    explicit config was passed in): editing ``fig.style.font`` in place (or
    reassigning ``fig.style``) affects only ``fig`` -- it can neither leak
    into other figures created earlier or later in the same process, nor
    mutate ``GlobalConfig`` itself. This is copy-AT-CONSTRUCTION semantics,
    the same rule matplotlib's ``rcParams`` snapshot follows for a new
    ``Figure``/``Axes``.

    This only applies to the *default*, taken from ``GlobalConfig``. A
    ``style``/``graph``/``marker`` object YOU pass in explicitly is still
    stored by reference, unchanged from before this note was added: two
    figures built with the same explicit config object still share it, and
    the object stays live for code that wants to mutate it after
    construction (:mod:`gleplot.parser.recognizer` does exactly this while
    reconstructing a ``Figure`` from parsed GLE text).
    """

    def __init__(
        self,
        figsize: Tuple[float, float] = (8, 6),
        dpi: int = 100,
        style: Optional[GLEStyleConfig] = None,
        graph: Optional[GLEGraphConfig] = None,
        marker: Optional[GLEMarkerConfig] = None,
        sharex: bool = False,
        sharey: bool = False,
        data_prefix: Optional[str] = None,
        height_ratios: Optional[Sequence[float]] = None,
        width_ratios: Optional[Sequence[float]] = None,
    ):
        """Initialize figure with optional configuration objects.

        Parameters
        ----------
        data_prefix : str, optional
            Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
            If None, uses global counter with ``data_`` prefix.

            Used verbatim -- it is never sanitized, so the sidecar names stay
            predictable (``'experimentA'`` yields ``experimentA_0.dat``, not
            ``experimenta_0.dat``). In exchange it is validated: a prefix
            containing whitespace, a control character, or any of
            ``! " + / \\`` raises ``ValueError`` here rather than producing a
            script GLE fails to parse. See
            :func:`gleplot.axes._validate_data_prefix`.

        Raises
        ------
        ValueError
            If ``data_prefix`` is empty/whitespace-only or contains a
            character that is not usable in a GLE data filename.
        height_ratios : sequence of float, optional
            Relative height of each subplot ROW, matplotlib-``gridspec``
            style, e.g. ``[3, 3, 3, 1, 4]`` for a 5-row grid whose 4th row is
            thin. ``None`` (default) keeps every row the same height -- the
            historical behaviour, byte-identical output. Applies only to the
            multi-subplot grid layout (``add_subplot``/:func:`gleplot.subplots`
            with more than one axes); ignored for a single (1,1,1) axes.
            Checked against the actual number of subplot rows at GLE-
            generation time (:meth:`Figure.savefig`/:meth:`savefig_gle`),
            since the grid shape is not always known yet when the figure is
            constructed -- a length mismatch raises :class:`ValueError` then,
            naming both the given length and the row count found.
        width_ratios : sequence of float, optional
            Relative width of each subplot COLUMN. Same semantics, defaults
            and validation timing as ``height_ratios``, but for columns.
        """
        self.figsize = figsize
        self.dpi = dpi

        # Store configuration for passing to writer.
        #
        # When no explicit config is given, take a COPY of the global
        # default rather than the ``GlobalConfig`` singleton itself.
        # ``GLEStyleConfig``/``GLEGraphConfig``/``GLEMarkerConfig`` are all
        # flat dataclasses (str/float/int/bool/Optional[float] fields only,
        # no mutable members), so a shallow ``dataclasses.replace(...)`` --
        # equivalent to ``copy.copy`` here -- is a full, independent copy.
        # Without this, ``fig.style.font = ...`` on a figure that never
        # passed ``style=`` mutates the *same* object every other
        # default-styled ``Figure()`` in the process holds, because
        # ``GlobalConfig.get_style()`` returns one shared instance. This is
        # copy-AT-CONSTRUCTION semantics: changing ``GlobalConfig.style``
        # (etc.) before creating a figure still changes that figure's
        # defaults, same as before; only the *identity* is no longer
        # shared, so later in-place edits on one figure's config cannot
        # leak into another figure's, or into the global default itself.
        #
        # An EXPLICIT config object, by contrast, is still stored BY
        # REFERENCE, not copied: that is a narrower, pre-existing contract
        # the parser recognizer depends on. ``parser/recognizer.py`` builds
        # a ``GLEGraphConfig`` up front, hands it to ``Figure(graph=...)``,
        # then mutates ``smooth_curves`` on that same object afterwards
        # (see ``_apply_smooth``) once it has walked the parsed series and
        # knows whether they carried ``smooth`` -- it relies on
        # ``fig.graph is graph_cfg``. Only the ``GlobalConfig`` singleton is
        # a cross-figure hazard; an object the caller constructed and holds
        # no other reference to is not.
        self.style = style if style is not None else replace(GlobalConfig.get_style())
        self.graph = graph if graph is not None else replace(GlobalConfig.get_graph())
        self.marker_config = (
            marker if marker is not None else replace(GlobalConfig.get_marker())
        )

        # Shared axes configuration
        self.sharex = sharex
        self.sharey = sharey

        # Custom data file naming. Validated (not sanitized) so a prefix GLE
        # cannot parse fails here, at the point the bad value was supplied,
        # instead of at compile time inside a generated 'data <file>' line.
        self.data_prefix = (
            _validate_data_prefix(data_prefix) if data_prefix is not None else None
        )
        self._local_data_counter = 0  # Local counter when using custom prefix
        self._used_data_files: set[str] = set()
        # Per-kind (heatmap/contour/points) contour+fitz sidecar counters --
        # only ever populated when this figure has a custom data_prefix (see
        # axes._reserve_sidecar); a default-prefix figure shares the
        # module-level axes._global_sidecar_counters instead (G8).
        self._sidecar_counters: dict[str, int] = {}
        self._subplot_adjust: dict[str, float] = {}

        # Per-row/per-column relative sizes for the multi-subplot grid
        # (matplotlib-style height_ratios/width_ratios). None (the default)
        # means equal sizes -- see _grid_axis_sizes for how this combines
        # with subplots_adjust's wspace/hspace.
        self.height_ratios = (
            [float(r) for r in height_ratios] if height_ratios is not None else None
        )
        self.width_ratios = (
            [float(r) for r in width_ratios] if width_ratios is not None else None
        )

        self.axes_list = []  # List of Axes objects
        self._current_axes = None  # Current working axes
        # BrokenAxes assemblies. Their segments are ordinary Axes and live in
        # axes_list like any other subplot (so limits, series and emission all
        # work unchanged); this list only records the grouping, the seam
        # decoration and the shared titles.
        self.broken_axes: list = []

        # Raw GLE lines recovered from a parsed .gle file that the recognizer
        # could not map onto the object model, split into two buckets by
        # where they sit relative to the graph block(s):
        #   passthrough_header: emitted right after the standard preamble
        #     (after 'set hei ...' + blank line), before the first graph
        #     block/amove.
        #   passthrough_trailer: emitted at the very end of the script, after
        #     all graph blocks and deferred text annotations.
        # One entry per source line, no trailing newline. Default: empty.
        self.passthrough_header: list = []
        self.passthrough_trailer: list = []

        # Unknown keys recovered from a parsed '! gleplot:' metadata block,
        # re-emitted verbatim in the metadata block on regeneration. Default:
        # empty (no extra keys).
        self.metadata_extra: dict = {}

        # Structured records for series skipped by the LAST write because
        # their data source was dangling (§3.2). Write-time output, not
        # document state: reset by every generation, never serialized.
        self._source_warnings: List = []

        # Structured records for series the LAST write appended a preview
        # ``deresolve`` clause to (§6.1/§10.7, G7). Write-time output, not
        # document state: reset (to ``[]``, since ``preview_decimation`` is a
        # per-call opt-in) by every generation, never serialized -- see
        # :attr:`preview_decimation_report`.
        self._preview_decimation_report: List = []

        self.compiler = None
        try:
            self.compiler = GLECompiler()
        except RuntimeError:
            pass  # GLE not available, but can still write scripts

    @property
    def source_warnings(self) -> List:
        """Series skipped by the most recent GLE generation, and why.

        A list of :class:`gleplot.sources.DanglingSourceRef` -- inspectable
        objects naming the series (axes index, series list, index, label) and
        the reference that could not be resolved (table id, column keys,
        reason). Empty for any figure whose series are all inline, which is
        every figure the scripting API builds.

        Reset at the start of each generation, so it always describes the
        latest ``savefig``/``savefig_gle`` rather than accumulating.
        """
        return list(self._source_warnings)

    @property
    def preview_decimation_report(self) -> List:
        """Series the most recent generation actually decimated, and by how much.

        A list of :class:`gleplot.writer.DecimationRecord` (dataset name,
        label, factor, original point count) -- empty unless that generation
        call passed ``preview_decimation=N`` (``N`` > 1) AND at least one
        eligible series (line/scatter -- see
        :meth:`gleplot.writer.GLEWriter._deresolve_clause` for the full kind/
        threshold rule) met :attr:`gleplot.writer.GLEWriter.MIN_DERESOLVE_POINTS`.
        Always ``[]`` for a generation that did not pass the argument at all,
        matching the DEFAULT emission being byte-identical to a build before
        G7 existed.

        Reset at the start of each generation (mirrors :attr:`source_warnings`),
        so it always describes the latest ``savefig``/``savefig_gle`` rather
        than accumulating. Intended consumer: GLEstudio's render controller,
        to show a "preview decimated x N" badge on the series it names and to
        keep hit-testing locked to the same decimated point set (SPEC §7.1).
        """
        return list(self._preview_decimation_report)

    def subplots_adjust(
        self,
        *,
        left: Optional[float] = None,
        right: Optional[float] = None,
        bottom: Optional[float] = None,
        top: Optional[float] = None,
        wspace: Optional[float] = None,
        hspace: Optional[float] = None,
    ) -> None:
        """Store subplot layout overrides (matplotlib-compatible API).

        Parameters are normalized figure fractions except `wspace`/`hspace`,
        which follow matplotlib semantics (fraction of average subplot width/height).
        """
        candidate = dict(self._subplot_adjust)
        updates = {
            "left": left,
            "right": right,
            "bottom": bottom,
            "top": top,
            "wspace": wspace,
            "hspace": hspace,
        }
        for key, value in updates.items():
            if value is None:
                continue
            val = float(value)
            if key in {"left", "right", "bottom", "top"}:
                if not (0.0 <= val <= 1.0):
                    raise ValueError(f"{key} must be within [0, 1], got {val}")
            else:
                if val < 0.0:
                    raise ValueError(f"{key} must be >= 0, got {val}")
            candidate[key] = val

        left_val = candidate.get("left")
        right_val = candidate.get("right")
        if left_val is not None and right_val is not None and left_val >= right_val:
            raise ValueError("left must be less than right")

        bottom_val = candidate.get("bottom")
        top_val = candidate.get("top")
        if bottom_val is not None and top_val is not None and bottom_val >= top_val:
            raise ValueError("bottom must be less than top")

        self._subplot_adjust = candidate

    def add_subplot(self, *args) -> Axes:
        """
        Add subplot to figure.

        Parameters
        ----------
        *args : int
            Subplot specification (rows, cols, index) or single int
            E.g., add_subplot(2, 2, 1) or add_subplot(221)

        Returns
        -------
        Axes
            New axes object
        """
        if len(args) == 1 and isinstance(args[0], int):
            # Parse single int format (e.g., 221)
            spec = str(args[0])
            if len(spec) == 3:
                rows, cols, idx = int(spec[0]), int(spec[1]), int(spec[2])
            else:
                raise ValueError(f"Invalid subplot spec: {args[0]}")
        else:
            rows, cols, idx = args

        ax = Axes(self, (rows, cols, idx))

        # Derive shared-axes tick/label visibility flags from this figure's
        # current sharex/sharey settings. Kept as a separate method so the GUI
        # layout panel can re-apply the identical derivation after the fact
        # (grid resize / sharing toggle) instead of duplicating the logic.
        self._apply_shared_axes_flags(ax)

        self.axes_list.append(ax)
        self._current_axes = ax
        return ax

    def add_broken_xaxes(self, xlims, **kwargs) -> BrokenAxes:
        """Add a panel whose x-axis is broken into adjacent segments.

        The segments share one y-axis: tick labels and the y title appear only
        on the leftmost one, the sides that face each other are switched off,
        and the seam is marked with a rule or double-slash break marks. Series
        are declared once on the returned object and fanned out to every
        segment, sharing a single data sidecar; GLE clips each dataset to its
        own segment's range.

        Parameters
        ----------
        xlims : sequence of (float, float)
            One ``(xmin, xmax)`` per segment, left to right; at least two.
        **kwargs
            Passed to :class:`gleplot.brokenaxes.BrokenAxes` --
            ``width_ratios``, ``position``, ``gap``, ``divider``,
            ``divider_color``, ``divider_linewidth``, ``divider_lstyle``,
            ``break_mark_size``, ``trim_seam_labels``, ``xlabel_dist``,
            ``title_dist``.

        Returns
        -------
        BrokenAxes

        Notes
        -----
        Plot through the returned object, not through the figure: this sets
        the figure's current axes to the *leftmost segment*, so a subsequent
        ``fig.plot(...)`` / :meth:`gca` would reach only that one segment.

        Examples
        --------
        >>> fig = glp.figure(figsize=(3.4, 2.6))
        >>> bax = fig.add_broken_xaxes([(0, 0.02), (0.02, 3)],
        ...                            width_ratios=[1, 3], divider='slash')
        >>> bax.errorbar(t, a, yerr=e, marker='o', fmt='none')
        >>> bax.set_xlabel('t (us)')
        >>> bax.set_ylabel('Asymmetry (%)')
        """
        bax = BrokenAxes(self, xlims, **kwargs)
        for seg in bax.segments:
            # Derive the grid-level sharing flags first, then let the
            # broken-axis rules (already applied by the constructor) stand
            # where they disagree: the assembly's internal geometry is not
            # negotiable, whereas sharex/sharey describe the grid around it.
            show_ylabel, show_yticks = seg._show_ylabel, seg._show_yticks
            remove_first_xtick = seg._remove_first_xtick
            self._apply_shared_axes_flags(seg)
            seg._show_ylabel, seg._show_yticks = show_ylabel, show_yticks
            seg._show_xlabel = False
            seg._remove_first_xtick = remove_first_xtick
            self.axes_list.append(seg)

        self.broken_axes.append(bax)
        self._current_axes = bax.segments[0]
        return bax

    def _apply_shared_axes_flags(self, ax: Axes) -> None:
        """Set ``ax``'s shared-axes tick/label visibility flags.

        Reads ``ax.position`` (a ``(rows, cols, idx)`` tuple) together with this
        figure's ``sharex``/``sharey`` flags and writes the ``_show_xlabel`` /
        ``_show_xticks`` / ``_remove_*`` visibility flags on ``ax`` accordingly.

        This is the single source of truth for that derivation: ``add_subplot``
        calls it for every new axes, and callers that mutate an axes' position
        or the figure's sharing after axes already exist (e.g. the GUI layout
        panel) call it to re-sync the flags to what a fresh ``add_subplot``
        would have produced. Changing the rules here changes them everywhere.
        """
        rows, cols, idx = ax.position
        # Convert 1-based index to 0-based row/col.
        row = (idx - 1) // cols  # 0 = top row
        col = (idx - 1) % cols  # 0 = left col

        if self.sharex:
            # Only show x-axis labels/ticks on bottom row
            ax._show_xlabel = row == rows - 1
            ax._show_xticks = row == rows - 1
            # Remove last x-tick label if not the bottom row (to prevent overlap when subplots touch)
            ax._remove_last_xtick = row < rows - 1
            ax._remove_first_xtick = False
            # When sharing x, y-axes touch vertically - remove last (top) y-label from all but top row
            # (highest y-label of lower plots could overlap upward into the plot above)
            ax._remove_last_ytick = row > 0
            ax._remove_first_ytick = False
        else:
            ax._show_xlabel = True
            ax._show_xticks = True
            ax._remove_last_xtick = False
            ax._remove_first_xtick = False
            ax._remove_last_ytick = False
            ax._remove_first_ytick = False

        if self.sharey:
            # Only show y-axis labels/ticks on leftmost column
            ax._show_ylabel = col == 0
            ax._show_yticks = col == 0
            # When sharing y, x-axes touch horizontally - remove last x-label from all but rightmost
            ax._remove_last_xtick = col < cols - 1
            ax._remove_first_xtick = False
            # Y-axis labels don't overlap in horizontal arrangement (only shown on leftmost)
            # No need to remove first/last y-labels when plots are side-by-side
            if not self.sharex:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
        else:
            ax._show_ylabel = True
            ax._show_yticks = True
            if not self.sharex:  # Only set if not already set by sharex logic
                ax._remove_last_ytick = False
                ax._remove_first_ytick = False
            if not self.sharex:
                ax._remove_last_xtick = False
                ax._remove_first_xtick = False
                ax._remove_first_xtick = False

    @staticmethod
    def _grid_axis_sizes(
        ratios: Optional[Sequence[float]],
        n: int,
        avail_cm: float,
        gap_frac: Optional[float],
        default_gap_cm: float,
        param_name: str,
    ) -> Tuple[List[float], float]:
        """Per-cell sizes (cm) and the inter-cell gap (cm) along one grid axis.

        Shared by the row (``height_ratios``) and column (``width_ratios``)
        cases in the multi-subplot layout.

        Parameters
        ----------
        ratios : sequence of float, optional
            ``None`` for equal sizes (the pre-existing behaviour), or ``n``
            positive relative sizes, matplotlib ``height_ratios``/
            ``width_ratios`` style.
        n : int
            Number of rows (or columns) in the grid.
        avail_cm : float
            Total space available along this axis, after margins.
        gap_frac : float, optional
            A ``subplots_adjust`` ``wspace``/``hspace`` override: the gap as
            a fraction of the UNIT cell (the size a ratio of 1.0 gets).
            ``None`` uses ``default_gap_cm`` verbatim.
        default_gap_cm : float
            Gap (cm) to use when ``gap_frac`` is ``None``.
        param_name : str
            ``'height_ratios'`` or ``'width_ratios'``, for the error message.

        Returns
        -------
        sizes : list of float
            One size (cm) per row/column.
        gap : float
            The resolved gap (cm) between adjacent cells.

        Notes
        -----
        With uniform ratios (the default, ``ratios=None``) this reproduces
        the historical ``cell_w``/``cell_h`` and ``hspace``/``vspace``
        formulas exactly: a figure that does not use ``height_ratios``/
        ``width_ratios`` gets byte-identical output to before they existed.

        The gap is defined as a fraction of the UNIT cell -- the size a
        ratio of 1.0 would receive -- rather than of any one row/column's
        actual size, so it stays independent of the ratios themselves
        (a ``hspace`` chosen for a uniform grid keeps looking the same after
        some rows are made thinner or thicker).

        Raises
        ------
        ValueError
            If ``ratios`` is given but its length does not equal ``n``, or
            any entry is not strictly positive.
        """
        if ratios is None:
            resolved = [1.0] * n
        else:
            if len(ratios) != n:
                noun = "rows" if param_name == "height_ratios" else "columns"
                raise ValueError(
                    f"{param_name} has length {len(ratios)}, but the subplot "
                    f"grid has {n} {noun}"
                )
            if any(r <= 0 for r in ratios):
                raise ValueError(
                    f"{param_name} entries must all be positive, got {list(ratios)}"
                )
            resolved = [float(r) for r in ratios]

        total_ratio = float(sum(resolved))

        if n > 1 and gap_frac is not None:
            denom = total_ratio + gap_frac * (n - 1)
            unit = avail_cm / denom if denom > 0 else avail_cm / total_ratio
            gap = gap_frac * unit
        else:
            gap = default_gap_cm
            usable = avail_cm - (n - 1) * gap
            unit = usable / total_ratio

        sizes = [r * unit for r in resolved]
        return sizes, gap

    # -- page geometry ---------------------------------------------------
    #
    # ONE routine computes the frame rectangle of every axes, for every
    # figure: a lone plot is simply the 1x1 case of the subplot grid. Before
    # SPEC 3.3 / metadata v2 the single-plot path had no geometry at all (it
    # emitted a bare ``scale auto`` and let GLE auto-fit the page), which made
    # its layout non-invertible and forced a second, ad-hoc geometry hack for
    # the one case where auto-fit visibly broke (a colorbar clipped off the
    # right edge). Both are gone: the writer now always emits an explicit
    # ``amove x y`` + ``size w h`` + ``scale 1 1`` triple, and the recognizer
    # reads it straight back into ``Axes.placement``.
    #
    # GLE draws axis tick labels and axis titles OUTSIDE the frame rectangle,
    # so the margins below are *decoration* margins: space left blank around
    # the grid for those labels to occupy. They are expressed in units of the
    # figure's text height (``hei``), because the overflow scales with the
    # font -- measured against GLE 4.3.10, an 18 pt figure needs exactly the
    # same margins in ``hei`` units as a 12 pt one.

    #: Decoration margin (in units of ``hei``) for the layout's left edge --
    #: a horizontal run of y tick labels plus the rotated y-axis title.
    #: Measured worst cases: 3.11 hei for 4-character tick labels ("-0.5"),
    #: 4.72 hei for 7-character ones ("-0.0001"). The chosen value covers the
    #: former with slack; the latter needs ``subplots_adjust(left=...)``.
    _AUTO_MARGIN_LEFT_HEI = 4.0

    #: Same, bottom edge (one line of x tick labels + the x-axis title).
    #: Measured worst case 2.43 hei.
    _AUTO_MARGIN_BOTTOM_HEI = 3.0

    #: Same, top edge when any axes carries a title. Measured 1.49 hei.
    _AUTO_MARGIN_TITLE_HEI = 2.0

    #: Same, right edge when any axes carries a decorated secondary y-axis.
    #: Measured 3.28 hei.
    _AUTO_MARGIN_Y2_HEI = 4.0

    #: Same, for an edge with no axis title on it: only the outermost tick
    #: label's overhang past the frame corner. Measured worst case 0.52 hei.
    _AUTO_MARGIN_PLAIN_HEI = 1.5

    #: Lower bound on a computed frame extent, as a fraction of the page, so a
    #: very small ``figsize`` (or a very wide colorbar reservation) can never
    #: produce a zero or negative ``size``.
    _MIN_FRAME_FRACTION = 0.3

    @staticmethod
    def _axes_has_y2(ax: Axes) -> bool:
        """True if ``ax`` makes the writer decorate the secondary y-axis.

        Mirrors the conditions under which :meth:`GLEWriter.add_axes` emits a
        ``y2title``/``y2axis`` line -- the only ways the right-hand side of the
        frame acquires labels that need margin reserved for them.
        """
        return bool(
            ax.y2label_text
            or ax.y2min is not None
            or ax.y2max is not None
            or ax.y2scale == "log"
        )

    def _auto_margins_cm(self, writer, resolution) -> Tuple[float, float, float, float]:
        """``(left, right, bottom, top)`` decoration margins in page cm.

        **One policy, for every layout shape.** These are the margins of the
        whole grid, so what has to fit in them is the decoration of the
        *outermost* row and column -- exactly the decoration a lone plot
        carries, which is why the 1x1 case and the grid case cannot want
        different numbers. Each margin is therefore sized from the measured
        decoration overflow in units of ``hei`` (see the class constants
        above), whatever the grid's dimensions and whether or not its axes
        are shared.

        Grids used to keep fixed centimetre margins instead, inherited from
        before any of this was measured (left 1.0 cm plain / 1.5 cm shared).
        That is less than the ~1.32 cm a y-axis title plus tick labels like
        "-0.5" needs at the default 12 pt, so every such grid put ink off the
        left edge of the page. Sizing them like the lone plot fixes that, at
        the cost of moving every existing multi-plot figure's frames.

        The two conditionals are deliberately figure-wide rather than
        per-edge: a title anywhere in the grid reserves the top margin (it is
        the top row that will use it), and a decorated secondary y-axis
        anywhere reserves the right margin. Both over-reserve for the grid
        that puts its titled or y2-bearing axes somewhere other than the
        edge that needs the room -- the same trade the colorbar reservation
        below makes, and preferable to clipping.

        ``subplots_adjust`` overrides are applied last and win outright.
        """
        hei = fontsize_pt_to_cm(self.style.fontsize)
        titled = self._has_titles()
        has_y2 = any(self._axes_has_y2(ax) for ax in self.axes_list)
        margin_left = self._AUTO_MARGIN_LEFT_HEI * hei
        margin_bottom = self._AUTO_MARGIN_BOTTOM_HEI * hei
        margin_top = (
            self._AUTO_MARGIN_TITLE_HEI if titled else self._AUTO_MARGIN_PLAIN_HEI
        ) * hei
        margin_right = (
            self._AUTO_MARGIN_Y2_HEI if has_y2 else self._AUTO_MARGIN_PLAIN_HEI
        ) * hei

        # Convert margin overrides from normalized figure fractions to cm.
        if "left" in self._subplot_adjust:
            margin_left = self._subplot_adjust["left"] * writer.width_cm
        if "right" in self._subplot_adjust:
            margin_right = (1.0 - self._subplot_adjust["right"]) * writer.width_cm
        if "bottom" in self._subplot_adjust:
            margin_bottom = self._subplot_adjust["bottom"] * writer.height_cm
        if "top" in self._subplot_adjust:
            margin_top = (1.0 - self._subplot_adjust["top"]) * writer.height_cm

        # Reserve extra room on the right for a colorbar, if any axes has one.
        # colorbar() enforces exactly one heatmap-bearing axes per figure, so
        # at most one colorbar exists here; it is drawn at the right edge of
        # its (rightmost, in the common 1-row layout) axes. This keeps simple
        # grids correct; a colorbar on an axes that is NOT in the rightmost
        # column could still overlap its neighbour (documented limitation).
        # With no colorbar, margin_right is unchanged.
        cbar_reserved = max(
            (self._axes_colorbar_reserved_cm(ax, resolution) for ax in self.axes_list),
            default=0.0,
        )
        if cbar_reserved > 0:
            margin_right = max(margin_right, cbar_reserved)

        return margin_left, margin_right, margin_bottom, margin_top

    def _has_titles(self) -> bool:
        """True if any subplot has a title (a broken axis titles the assembly)."""
        return any(ax.title_text for ax in self.axes_list) or any(
            bax.title_text for bax in self.broken_axes
        )

    def _layout_rects(self, writer, resolution) -> Tuple[List[tuple], List[tuple]]:
        """Default frame rect + grid cell for every axes, in ``axes_list`` order.

        Returns
        -------
        rects : list of (x, y, w, h)
            The frame rectangle in page cm the grid arrangement computes for
            each axes -- what the writer emits when the axes carries no
            explicit :attr:`Axes.placement` of its own. A broken-axis segment
            gets its slice of the cell rather than the whole cell.
        cells : list of (cell_x, cell_w)
            The un-sliced grid cell each axes sits in, which the broken-axis
            seam decoration needs in order to span the whole cell.

        The grid dimensions come from the axes' ``position`` tuples; sizes
        come from ``height_ratios``/``width_ratios`` (equal when unset) and
        the gaps from ``subplots_adjust``'s ``wspace``/``hspace`` (fixed
        defaults when unset). With one axes this degenerates to a single cell
        filling the page inside the margins -- no gaps are consulted at all.
        """
        margin_left, margin_right, margin_bottom, margin_top = self._auto_margins_cm(
            writer, resolution
        )

        max_rows = max((ax.position[0] for ax in self.axes_list), default=1)
        max_cols = max((ax.position[1] for ax in self.axes_list), default=1)

        # With a single cell there are no relative sizes to distribute, so
        # height_ratios/width_ratios are ignored rather than validated -- a
        # figure-level setting left over from a grid must not turn a lone
        # plot into a ValueError (see _grid_axis_sizes' length check).
        height_ratios = self.height_ratios if len(self.axes_list) > 1 else None
        width_ratios = self.width_ratios if len(self.axes_list) > 1 else None

        avail_w = max(
            writer.width_cm - margin_left - margin_right,
            writer.width_cm * self._MIN_FRAME_FRACTION,
        )
        avail_h = max(
            writer.height_cm - margin_bottom - margin_top,
            writer.height_cm * self._MIN_FRAME_FRACTION,
        )

        # Spacing between subplots; defaults preserve existing behavior.
        # Unlike the outer margins these are still fixed centimetres, and they
        # carry the same decoration an outer margin does (an inner column's y
        # title and tick labels live in the gap to its left). 1.5 cm clears
        # the measured 3.11 hei at the default 12 pt but not at, say, 18 pt,
        # where inner panels need ``subplots_adjust(wspace=...)``.
        default_hspace_cm = 0.0 if self.sharey else 1.5
        default_vspace_cm = 0.0 if self.sharex else 2.0
        wspace_frac = self._subplot_adjust.get("wspace")
        hspace_frac = self._subplot_adjust.get("hspace")

        # Per-column widths / per-row heights (cm), plus the resolved gap.
        # Equal-size unless height_ratios/width_ratios were given at
        # construction time (see _grid_axis_sizes); the equal-ratios path
        # reproduces the historical cell_w/cell_h/hspace/vspace formulas
        # exactly.
        col_widths, hspace = self._grid_axis_sizes(
            width_ratios,
            max_cols,
            avail_w,
            wspace_frac,
            default_hspace_cm,
            "width_ratios",
        )
        row_heights, vspace = self._grid_axis_sizes(
            height_ratios,
            max_rows,
            avail_h,
            hspace_frac,
            default_vspace_cm,
            "height_ratios",
        )

        # Cumulative left edge per column and bottom edge per row (GLE
        # coordinates: origin bottom-left, y increases upward), built once so
        # unequal row/column sizes are placed correctly -- with equal sizes
        # this reduces to the historical ``margin + i * (cell + gap)``
        # arithmetic.
        col_x_offsets = [margin_left]
        for w in col_widths[:-1]:
            col_x_offsets.append(col_x_offsets[-1] + w + hspace)

        row_y_bottoms = []
        consumed_h = margin_top
        for h in row_heights:
            row_y_bottoms.append(writer.height_cm - consumed_h - h)
            consumed_h += h + vspace

        rects: List[tuple] = []
        cells: List[tuple] = []
        for ax in self.axes_list:
            _rows, cols, idx = ax.position
            # Convert 1-based index to row/col (row-major, top-to-bottom)
            row = (idx - 1) // cols  # 0-based, 0 = top row
            col = (idx - 1) % cols  # 0-based, 0 = left col

            cell_x = col_x_offsets[col]
            cell_w = col_widths[col]
            cell_h = row_heights[row]
            y_pos = row_y_bottoms[row]

            # A broken-axis segment occupies a slice of its grid cell rather
            # than the whole thing; everything else about the emission is
            # identical to an ordinary subplot.
            owner = ax._break_owner
            if owner is not None:
                dx, graph_w = owner.segment_extent(ax._break_index, cell_w)
                x_pos = cell_x + dx
            else:
                x_pos = cell_x
                graph_w = cell_w

            rects.append((x_pos, y_pos, graph_w, cell_h))
            cells.append((cell_x, cell_w))

        return rects, cells

    def gca(self) -> Axes:
        """Get current axes (or create if needed)."""
        if self._current_axes is None:
            self.add_subplot(111)
        return self._current_axes

    # Convenience plotting methods (plot on current axes)

    def plot(self, x, y, **kwargs):
        """Plot on current axes."""
        return self.gca().plot(x, y, **kwargs)

    def scatter(self, x, y, **kwargs):
        """Scatter on current axes."""
        return self.gca().scatter(x, y, **kwargs)

    def bar(self, x, height, **kwargs):
        """Bar chart on current axes."""
        return self.gca().bar(x, height, **kwargs)

    def fill_between(self, x, y1, y2, **kwargs):
        """Fill between on current axes."""
        return self.gca().fill_between(x, y1, y2, **kwargs)

    def errorbar(self, x, y, **kwargs):
        """Error bar plot on current axes."""
        return self.gca().errorbar(x, y, **kwargs)

    def text(self, x, y, s, **kwargs):
        """Add text on current axes."""
        return self.gca().text(x, y, s, **kwargs)

    def axvline(self, x=0.0, **kwargs):
        """Vertical reference line on current axes."""
        return self.gca().axvline(x, **kwargs)

    def axhline(self, y=0.0, **kwargs):
        """Horizontal reference line on current axes."""
        return self.gca().axhline(y, **kwargs)

    def axvspan(self, xmin, xmax, **kwargs):
        """Shaded vertical band on current axes."""
        return self.gca().axvspan(xmin, xmax, **kwargs)

    def axhspan(self, ymin, ymax, **kwargs):
        """Shaded horizontal band on current axes."""
        return self.gca().axhspan(ymin, ymax, **kwargs)

    def imshow(self, Z, **kwargs):
        """Display gridded data as a heatmap on current axes."""
        return self.gca().imshow(Z, **kwargs)

    def contour(self, *args, **kwargs):
        """Draw contour lines on current axes."""
        return self.gca().contour(*args, **kwargs)

    def tripcolor(self, x, y, z, **kwargs):
        """Scattered-data heatmap on current axes."""
        return self.gca().tripcolor(x, y, z, **kwargs)

    def tricontour(self, x, y, z, **kwargs):
        """Scattered-data contour lines on current axes."""
        return self.gca().tricontour(x, y, z, **kwargs)

    def colorbar(
        self,
        label: Optional[str] = None,
        format: str = "fix 1",
        nticks: Optional[int] = None,
        width: float = 0.5,
        sep: float = 0.3,
    ):
        """Attach a vertical colorbar to the figure's single heatmap axes.

        Parameters
        ----------
        label : str, optional
            Colorbar axis label (rotated text to the right of the bar).
        format : str
            GLE ``format$`` string for the tick labels (e.g. ``'fix 1'``).
        nticks : int, optional
            Approximate number of tick intervals. Default: 5.
        width : float
            Colorbar width in cm.
        sep : float
            Gap (cm) between the graph's right edge and the colorbar.

        Returns
        -------
        dict
            The stored colorbar dict (also attached to the heatmap under
            ``'colorbar'``).

        Raises
        ------
        ValueError
            If no axes has a heatmap, or if more than one does (ambiguous).
        """
        bearing = [ax for ax in self.axes_list if ax.heatmaps]
        if not bearing:
            raise ValueError(
                "colorbar() requires a heatmap (imshow/tripcolor) on some axes"
            )
        if len(bearing) > 1:
            raise ValueError(
                "colorbar() is ambiguous: more than one axes has a heatmap"
            )
        hm = bearing[0].heatmaps[0]

        if hm["vmin"] is not None:
            zmin = float(hm["vmin"])
        elif hm["source"] == "grid":
            zmin = float(np.nanmin(hm["z"]))
        else:
            zmin = float(np.nanmin(hm["zpts"]))
        if hm["vmax"] is not None:
            zmax = float(hm["vmax"])
        elif hm["source"] == "grid":
            zmax = float(np.nanmax(hm["z"]))
        else:
            zmax = float(np.nanmax(hm["zpts"]))

        divisions = int(nticks) if nticks else 5
        span = zmax - zmin
        zstep = (span / divisions) if span > 0 else 1.0

        cb = {
            "label": mathtext_to_gle(label),
            "format": str(format),
            "width": float(width),
            "sep": float(sep),
            "zmin": zmin,
            "zmax": zmax,
            "zstep": zstep,
        }
        hm["colorbar"] = cb
        return cb

    def xlabel(self, label: str):
        """Set x label on current axes."""
        return self.gca().set_xlabel(label)

    def ylabel(self, label: str, axis: str = "y"):
        """Set y label on current axes.

        Parameters
        ----------
        label : str
            Axis label text
        axis : str, optional
            Which axis: 'y' (left, default) or 'y2' (right)
        """
        return self.gca().set_ylabel(label, axis=axis)

    def title(self, label: str):
        """Set title on current axes."""
        return self.gca().set_title(label)

    def legend(self, **kwargs):
        """Add legend to current axes."""
        return self.gca().legend(**kwargs)

    # File I/O methods

    def absolutize_file_references(self, base_dir) -> None:
        """Rewrite relative reference-mode data paths to absolute paths.

        Reference-mode series (``file_series``) carry their ``data_file``
        verbatim into the generated ``data`` command, so a relative path is
        only valid when GLE runs in the directory the reference is relative
        to. Call this on a figure whose script will be generated or compiled
        SOMEWHERE ELSE: the live preview's temp session dir, an export to a
        different directory, or Save As across directories. Import-mode
        series regenerate their sidecars next to the script and are
        untouched. Paths are emitted in POSIX form (GLE accepts forward
        slashes on Windows); the writer quotes names containing spaces.
        """
        base = Path(base_dir)
        for ax in self.axes_list:
            for fs in ax.file_series:
                name = fs.get("data_file")
                if not name:
                    continue
                ref = Path(name)
                if not ref.is_absolute():
                    fs["data_file"] = (base / ref).resolve().as_posix()

    def savefig_gle(
        self,
        filepath: str,
        data_provider=None,
        preview_decimation: Optional[DecimationPolicy] = None,
        **kwargs,
    ) -> Path:
        """
        Save figure as GLE script.

        Parameters
        ----------
        filepath : str
            Output file path
        data_provider : DataProvider, optional
            Resolver for series whose ``data_source`` references a table
            (see :meth:`savefig` and :mod:`gleplot.sources`).
        preview_decimation : DecimationPolicy, optional
            Preview-only ``deresolve`` factor (SPEC §6.1/§10.7). ``None``
            (the default) emits byte-identically to a build before this
            option existed. A single ``int`` applies one factor to every
            eligible series (unchanged, byte-for-byte, since G7); a
            ``Mapping`` keyed by series label or a per-series
            ``Callable[[DecimationCandidate], Optional[int]]`` instead let a
            mixed figure (e.g. a 1k-point curve alongside a 500k-point
            trace) give each series its own factor -- see
            :data:`gleplot.writer.DecimationPolicy` for the full contract.
            When a resolved factor is given and > 1, large line/scatter
            series (see :attr:`gleplot.writer.GLEWriter.MIN_DERESOLVE_POINTS`)
            get a `` deresolve N`` clause on their ``dN`` line -- GLE then
            draws (and this call's caller may hit-test against) 1-in-N
            points instead of the full series, while axis autoscale is still
            computed from the full, undecimated data. A generation-time
            argument only: never stored on the figure, so ``to_dict``/
            ``from_dict`` and a *saved* ``.gle`` are unaffected -- pass it
            only when writing a throwaway preview copy, never the document
            being saved. See :attr:`preview_decimation_report` for what got
            decimated.
        folder : bool, optional
            If True, place the ``.gle`` script and generated data files
            in a sibling ``<name>.gleplot`` directory.
        **kwargs
            Additional options

        Returns
        -------
        Path
            Path to created GLE file
        """
        output_path, export_dir = self._resolve_export_paths(
            filepath,
            folder=kwargs.pop("folder", False),
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate and save GLE content with data files
        gle_content, data_content = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )

        # Write script
        output_path.write_text(gle_content, encoding="utf-8")

        # Write data files in same directory
        for filename, content in data_content.items():
            data_file = export_dir / filename
            data_file.write_text(content, encoding="utf-8")

        return output_path

    def savefig(
        self,
        filepath: str,
        format: Optional[str] = None,
        dpi: Optional[int] = None,
        data_provider=None,
        cairo: Optional[bool] = None,
        keep_intermediates: bool = False,
        preview_decimation: Optional[DecimationPolicy] = None,
        **kwargs,
    ) -> Path:
        """
        Save figure as GLE script and/or compiled output.

        Parameters
        ----------
        filepath : str
            Output file path
        format : {'pdf', 'png', 'eps', 'jpg', 'svg'}, optional
            Output format. If None, the format is auto-detected from the
            file suffix (``.jpeg`` maps to ``jpg``); an unrecognized or
            missing suffix defaults to saving the ``.gle`` script only.
            If format is given but the file extension differs, format wins.
        dpi : int, optional
            DPI for raster formats
        cairo : bool, optional
            Whether to compile with GLE's ``-cairo`` device flag (SPEC
            §6.1/§10.6). ``None`` (the default) auto-detects via
            :meth:`requires_cairo` -- on for any figure using semi-
            transparency, off otherwise, so an ordinary opaque figure's
            compile behaviour (and its written ``.gle`` text -- the flag is
            compile-time only, never script-time) is completely unchanged.
            Pass ``True``/``False`` to force the flag either way. Ignored
            when ``format`` is ``'gle'`` (no compile happens).

            When Cairo ends up active (auto or forced) and this figure's
            configured font (:attr:`style`'s ``font``) is not one of GLE's
            Cairo-safe fonts, a :class:`UserWarning` is raised: GLE itself
            substitutes a Cairo-safe font in that case (see
            :mod:`gleplot.cairo_support`), and SPEC's "no silent drops" rule
            means that substitution must never happen without gleplot saying
            so.
        data_provider : DataProvider, optional
            Supplies the tables that ``ColumnRef``/``GridRef`` series
            reference (:mod:`gleplot.sources`). Injected **here**, at write
            time, rather than held on the figure: the figure is a
            serializable document that ``to_dict`` round-trips and the
            provider is a live application object, so binding the two would
            make snapshots either lossy or impossible -- and passing it per
            write is what lets one figure be rendered against different
            tables (a preview vs an export, a what-if dataset). Figures whose
            series are all inline (everything the scripting API builds)
            ignore it entirely.

            References that cannot be resolved do not raise: the affected
            series is skipped and recorded in :attr:`source_warnings`.
        keep_intermediates : bool, optional
            If True, skip the post-compile cleanup of GLE-generated contour/
            ``fitz`` intermediates (``-cdata.dat``/``-clabels.dat``/
            ``-cvalues.dat``, and a points-sourced heatmap/contour's
            generated ``.z``) that a compiled export otherwise removes from
            ``export_dir`` afterwards -- see the "Engine intermediates"
            note below. Default False. Has no effect when this figure has
            no contour/heatmap series, or when ``format == 'gle'`` (no
            compile runs, so nothing was generated to clean up).
        preview_decimation : DecimationPolicy, optional
            Preview-only ``deresolve`` factor -- see :meth:`savefig_gle` for
            the full contract. Generation-time only, never stored on the
            figure. Compiling with this set still produces a real
            ``format`` output (PDF/PNG/...), just from a decimated preview
            script -- pass it for a live-preview compile, not for a save the
            user will treat as their document.
        folder : bool, optional
            If True, place the exported file, the intermediate ``.gle``
            script, and generated data files in a sibling
            ``<name>.gleplot`` directory.
        **kwargs
            Additional arguments

        Returns
        -------
        Path
            Path to output file (GLE script or compiled output)

        Notes
        -----
        **Engine intermediates (GLEstudio SPEC 9.1/10.8).** Compiling a
        figure with a contour or a points-sourced (``fitz``) heatmap/contour
        makes the ``gle`` binary itself write extra files into ``export_dir``
        as an undocumented side effect -- ``<stem>-cdata.dat``,
        ``<stem>-clabels.dat``, ``<stem>-cvalues.dat``, and (points-sourced
        only) the generated ``<stem>.z``. These are never gleplot's own
        output, so on a successful compile (``format != 'gle'``) they are
        deleted from ``export_dir`` afterwards by exact name -- never by
        glob or prefix match, so a user's own file can only be caught if its
        name is a byte-for-byte match to one GLE itself would have written
        for *this* figure (see
        :func:`gleplot.compiler.remove_generated_intermediates`). Pass
        ``keep_intermediates=True`` to leave them in place, e.g. to inspect
        a contour's raw crossings while debugging. A failed compile raises
        before cleanup runs, so its intermediates (if any were written) are
        never removed -- they may help diagnose the failure.
        """
        output_path, export_dir = self._resolve_export_paths(
            filepath,
            folder=kwargs.pop("folder", False),
        )
        export_dir.mkdir(parents=True, exist_ok=True)

        # Determine output format from the file suffix. Driven by
        # SUFFIX_TO_COMPILE_FORMAT (shared with GLECompiler) so this can't
        # silently drift out of sync with what the compiler supports.
        # Unknown/missing suffixes (including '.gle') default to 'gle'.
        if format is None:
            format = SUFFIX_TO_COMPILE_FORMAT.get(output_path.suffix.lower(), "gle")

        # Write GLE script and data files
        base_path = output_path.with_suffix(".gle")
        gle_content, data_files = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )
        base_path.write_text(gle_content, encoding="utf-8")

        # Write data files in same directory
        for filename, content in data_files.items():
            data_file = export_dir / filename
            data_file.write_text(content, encoding="utf-8")

        # Compile if needed
        if format != "gle":
            if not self.compiler:
                raise RuntimeError(
                    "GLE compiler not available. "
                    "Install GLE or use savefig_gle() to save script only."
                )

            effective_cairo = self.requires_cairo() if cairo is None else cairo
            if effective_cairo:
                warning = cairo_font_warning(self.style.font)
                if warning:
                    warnings.warn(
                        f"{warning} (figure requires Cairo for its "
                        "semi-transparent colours).",
                        UserWarning,
                        stacklevel=2,
                    )

            output_dpi = dpi or self.dpi
            self.compiler.compile(
                str(base_path), format, dpi=output_dpi, cairo=effective_cairo
            )

            # Post-compile cleanup (G8): only on a *successful* compile --
            # compile() raises before this line otherwise -- and only for
            # this figure's own known contour/fitz stems (never a glob).
            if not keep_intermediates:
                from .compiler import remove_generated_intermediates

                remove_generated_intermediates(
                    export_dir, self._engine_intermediate_filenames()
                )

            return output_path.with_suffix(f".{format}")

        return base_path

    @staticmethod
    def _resolve_export_paths(filepath: str, folder: bool = False) -> Tuple[Path, Path]:
        """Resolve output and export directory paths for save operations."""
        output_path = Path(filepath)
        export_dir = output_path.parent

        if folder:
            export_dir = output_path.parent / f"{output_path.stem}.gleplot"
            output_path = export_dir / output_path.name

        return output_path, export_dir

    def _generate_gle(
        self, data_provider=None, preview_decimation: Optional[DecimationPolicy] = None
    ) -> str:
        """Generate complete GLE script content."""
        content, _ = self._generate_gle_with_files(
            data_provider=data_provider, preview_decimation=preview_decimation
        )
        return content

    def _build_metadata_dict(self, data_files: dict, raw_sidecars=None) -> dict:
        """Assemble the ``! gleplot:`` metadata payload for this save.

        Parameters
        ----------
        data_files : dict
            The ``{filename: content}`` mapping the writer produced for this
            save -- i.e. every data sidecar the figure itself generated.
            Series added via ``*_from_file`` reference external files and
            never appear here, so they are correctly excluded from
            ``import-data``.

        Returns
        -------
        dict
            Suitable for :func:`gleplot.parser.metadata.emit_metadata`. Always
            includes ``dpi`` and ``import-data`` (per that function's
            ALWAYS_EMIT contract); ``sharex``/``sharey``/``msize_scale`` are
            included too but only rendered by ``emit_metadata`` when they
            differ from the documented defaults. Any ``metadata_extra`` keys
            recovered from a parsed file are passed through verbatim.
        """
        raw = set(raw_sidecars or ())
        data = {
            "dpi": self.dpi,
            "sharex": self.sharex,
            "sharey": self.sharey,
            "msize_scale": self.marker_config.msize_scale,
            # Raw-content sidecars (heatmap/contour ``.z`` grids, scattered
            # ``points.dat`` triples) are not columnar imports and must not be
            # vouched for as such -- excluded from ``import-data``.
            "import-data": sorted(k for k in data_files.keys() if k not in raw),
        }
        data.update(self.metadata_extra)
        return data

    def _generate_gle_with_files(
        self, data_provider=None, preview_decimation: Optional[DecimationPolicy] = None
    ) -> tuple:
        """
        Generate complete GLE script content with data files.

        Supports both single-plot and multi-subplot layouts.
        For a single axes (1,1,1), generates a simple graph block.
        For multiple axes, positions each graph using ``amove`` and
        explicit ``size`` commands based on the subplot grid.

        Uses figure's configured style, graph, and marker settings.

        Every series' data goes through ONE path: the source-resolution pass
        (:func:`gleplot.writer.resolve_figure`) runs first and hands the rest
        of this method an array-bearing series whether the numbers were baked
        in at ``plot()`` time or pulled from ``data_provider``'s tables.
        Series whose reference is dangling are skipped -- absent from
        autoscaling, the legend and the script -- and recorded in
        :attr:`source_warnings`; a figure in which every series is dangling
        still produces a valid ``.gle``.

        Parameters
        ----------
        data_provider : DataProvider, optional
            See :meth:`savefig`.
        preview_decimation : DecimationPolicy, optional
            See :meth:`savefig_gle`. Forwarded to :class:`~gleplot.writer.GLEWriter`
            as a constructor argument only -- never read off ``self`` -- so
            this stays a pure function of its arguments plus the figure's
            already-serializable state.

        Returns
        -------
        tuple
            (gle_content, data_files_dict)
        """
        # Pass configuration to writer
        writer = GLEWriter(
            self.figsize,
            self.dpi,
            style=self.style,
            graph=self.graph,
            marker=self.marker_config,
            preview_decimation=preview_decimation,
        )

        # Source resolution, before anything reads a series' numbers.
        resolution = resolve_figure(self, data_provider)
        self._source_warnings = list(resolution.warnings)
        # Reset alongside source_warnings: both are write-time output for
        # THIS generation, not document state (see preview_decimation_report).
        self._preview_decimation_report = []

        is_single = len(self.axes_list) <= 1

        # A figure with NO axes that carries passthrough (e.g. a graph the
        # recognizer swallowed into an opaque 'begin translate/scale' wrapper,
        # preserved wholesale as header+trailer) must not fabricate a spurious
        # empty 'begin graph ... end graph'. Emit only the passthrough. A
        # genuinely empty figure with no passthrough keeps the historical
        # default empty graph block (existing tests rely on it).
        no_fabricate = not self.axes_list and (
            self.passthrough_header or self.passthrough_trailer
        )

        # Palette / colorbar / contour-label subs needed by any axes. Emitted
        # once, right after the preamble, before any graph uses them.
        sub_texts = self._collect_sub_texts(resolution)

        if is_single and no_fabricate:
            writer.add_preamble(
                include_graph_begin=False, passthrough_header=self.passthrough_header
            )
            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )
        elif is_single:
            # Single plot -- the 1x1 case of the grid geometry, emitted through
            # a simpler block sequence (no inter-subplot blank lines, no
            # shared-axis synchronization). 'begin graph' is emitted explicitly
            # (not by the preamble) so palette subs and the fitz/contour
            # pre-graph blocks can precede it.
            writer.add_preamble(
                include_graph_begin=False, passthrough_header=self.passthrough_header
            )
            writer.add_sub_defs(sub_texts)
            rects, _cells = self._layout_rects(writer, resolution)

            if self.axes_list:
                ax = self.axes_list[0]
                self._resolve_axis_limits(ax, resolution)

                self._emit_pre_graph_blocks(writer, ax, resolution)
                # Explicit placement (SPEC 3.3, metadata v2): the frame rect is
                # realized as 'amove x y' + 'size w h' + 'scale 1 1'. This is
                # the DEFAULT emission -- a lone plot is the 1x1 case of the
                # grid geometry (_layout_rects), so its rect is deterministic
                # and invertible instead of being left to GLE's 'scale auto'
                # page fit. The two exceptions below keep their own geometry.
                if ax.geometry_passthrough:
                    # Unmodelled GLE geometry recovered from a parsed file:
                    # re-emitted verbatim, and any amove it had is preserved in
                    # passthrough_header, so nothing is fabricated in front.
                    writer.begin_graph()
                    writer.add_graph_geometry_passthrough(ax.geometry_passthrough)
                elif self.graph.scale_mode == "fullsize":
                    # An explicit writer-level opt-out of gleplot's own layout:
                    # GLE fits the graph (labels included) to the whole page.
                    # There is no rect to emit, so no amove either.
                    writer.begin_graph()
                    writer.add_graph_size()
                else:
                    rect = ax.placement if ax.placement is not None else rects[0]
                    writer.add_amove(rect[0], rect[1])
                    writer.begin_graph()
                    writer.add_graph_size(
                        width_cm=rect[2], height_cm=rect[3], force_size=True
                    )
                self._write_axes_content(writer, ax, resolution)
                writer.end_graph(passthrough=ax.passthrough)
                self._emit_post_graph_calls(writer, ax, resolution)
            else:
                # No axes at all: there is nothing to place, so the historical
                # empty block stands. (A figure with passthrough took the
                # no-fabricate branch above; this is the truly empty figure.)
                writer.begin_graph()
                writer.add_graph_size()
                writer.end_graph()

            if self.passthrough_trailer:
                writer.lines_gle.extend(self.passthrough_trailer)
        else:
            # Multi-subplot layout
            writer.add_preamble(
                include_graph_begin=False, passthrough_header=self.passthrough_header
            )
            writer.add_sub_defs(sub_texts)

            # Resolve each panel's limits from its own data first, then let
            # sharing unify them. Doing it in this order means a shared LOG
            # axis is unified over ranges that are already positive, so the
            # union is positive too -- sanitizing after the unification would
            # instead give each panel its own repaired range and quietly break
            # the sharing.
            for ax in self.axes_list:
                self._resolve_axis_limits(ax, resolution)

            if self.sharex:
                self._synchronize_x_limits(resolution)
            if self.sharey:
                self._synchronize_y_limits(resolution)

            # Per-axes frame rectangles in cm, from the one geometry routine
            # (see _layout_rects). Default margins/spacing are heuristic but
            # can be overridden via subplots_adjust(left=..., right=...,
            # top=..., bottom=..., wspace=..., hspace=...).
            rects, cells = self._layout_rects(writer, resolution)

            for ax, rect, (cell_x, cell_w) in zip(self.axes_list, rects, cells):
                # An explicit placement rect (SPEC 3.3) overrides the computed
                # grid cell: the rect IS the model, the grid is only a helper
                # that computes rects. Figures built through the scripting API
                # carry none and use the computed cell; a figure parsed back
                # from GLE carries the rect recovered from its own
                # amove/size/scale-1-1 triple, which is what makes a
                # subplots_adjust layout survive the round trip.
                x_pos, y_pos, graph_w, cell_h = (
                    ax.placement if ax.placement is not None else rect
                )

                self._emit_pre_graph_blocks(writer, ax, resolution)
                writer.add_amove(x_pos, y_pos)
                writer.begin_graph()
                if ax.geometry_passthrough:
                    writer.add_graph_geometry_passthrough(ax.geometry_passthrough)
                else:
                    writer.add_graph_size(
                        width_cm=graph_w, height_cm=cell_h, force_size=True
                    )

                self._write_axes_content(writer, ax, resolution)

                writer.end_graph(passthrough=ax.passthrough)
                self._emit_post_graph_calls(writer, ax, resolution)
                if ax._break_owner is not None:
                    self._emit_break_decoration(
                        writer, ax._break_owner, ax, cell_x, cell_w
                    )
                writer.lines_gle.append("")  # Blank line between subplots

            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )

        # Provider-table sidecars are only complete once every series that
        # references them has been emitted; render them now, before the
        # metadata block vouches for the figure's data files.
        writer.finalize_shared_sidecars()
        resolution.emit_warnings()

        # Splice the metadata block in after the two header comment lines
        # ('! GLE graphics file' / '! Generated by gleplot') and before the
        # 'size ...' line -- add_preamble always emits exactly those two
        # lines first, so index 2 is the fixed, stable insertion point.
        metadata_dict = self._build_metadata_dict(
            writer.data_files, writer.raw_sidecars
        )
        metadata_lines = _gle_metadata.emit_metadata(metadata_dict)
        if metadata_lines:
            writer.lines_gle[2:2] = metadata_lines

        self._preview_decimation_report = list(writer.decimation_report)
        return writer.get_gle_content(), writer.data_files

    # -- contour / heatmap helpers --------------------------------------

    @staticmethod
    def _heatmap_z_file(hm: dict) -> str:
        """The ``.z`` grid file a heatmap's ``colormap`` references.

        Grid heatmaps reference their written ``.z`` sidecar directly; scattered
        (points) heatmaps reference the ``.z`` file GLE's ``fitz`` generates
        (points base with the ``.dat`` extension replaced by ``.z``).
        """
        df = hm["data_file"]
        if hm["source"] == "grid":
            return df
        return df[:-4] + ".z" if df.endswith(".dat") else df + ".z"

    @staticmethod
    def _contour_z_file(ct: dict) -> str:
        """The ``.z`` grid file a contour block reads (see :meth:`_heatmap_z_file`)."""
        df = ct["data_file"]
        if ct["source"] == "grid":
            return df
        return df[:-4] + ".z" if df.endswith(".dat") else df + ".z"

    def _engine_intermediate_filenames(self) -> "list[str]":
        """Exact basenames of GLE-generated intermediates this figure can produce.

        Used by :meth:`savefig` (G8, GLEstudio SPEC 9.1/10.8) to clean up
        after a compile. Computed purely from the object model -- every
        heatmap/contour on every axes, *not* filtered through a write's
        ``SourceResolution`` -- so a name reserved for a series that is
        dangling on this particular write (and therefore did not get a fresh
        ``begin contour``/``fitz`` block emitted) is still recognized as
        belonging to this figure if a stale file under that name is lying
        around from an earlier, successful compile.

        Two kinds of engine-generated file, mirroring :func:`gcontour.cpp`/
        :func:`fit.cpp` in GLE itself (see
        :func:`gleplot.compiler.remove_generated_intermediates`):

        - Every contour (grid- or points-sourced) can produce
          ``<stem>-cdata.dat``, ``<stem>-clabels.dat`` and
          ``<stem>-cvalues.dat``, where ``<stem>`` is :meth:`_contour_z_file`
          with its ``.z`` extension stripped.
        - A points-sourced (``fitz``) heatmap or contour additionally
          produces the gridded ``<points-stem>.z`` file itself -- that ``.z``
          is GLE's *output*, distinct from the raw ``<points-stem>.dat``
          points sidecar gleplot wrote as ``fitz``'s input (kept: it is
          gleplot's own file, needed to recompile, not an engine byproduct).
          A grid-sourced heatmap/contour's ``.z`` is likewise gleplot's own
          written sidecar, not GLE-generated, and is never included here.
        """
        names: "list[str]" = []
        for ax in self.axes_list:
            for ct in ax.contours:
                z_file = self._contour_z_file(ct)
                stem = z_file[:-2] if z_file.endswith(".z") else z_file
                names.append(f"{stem}-cdata.dat")
                names.append(f"{stem}-clabels.dat")
                names.append(f"{stem}-cvalues.dat")
                if ct.get("source") == "points":
                    names.append(z_file)  # the fitz-generated .z itself
            for hm in ax.heatmaps:
                if hm.get("source") == "points":
                    names.append(self._heatmap_z_file(hm))
        return names

    @staticmethod
    def _cmap_mode(cmap: str):
        """Map a canonical cmap name to a ``colormap`` emission mode tuple.

        Returns ``('gray', None)`` (grayscale, no clause), ``('color', None)``
        (GLE built-in rainbow), or ``('palette', 'gleplot_<name>')``.
        """
        if cmap == "gray":
            return ("gray", None)
        if cmap == "rainbow":
            return ("color", None)
        return ("palette", f"gleplot_{cmap}")

    # -- colorbar layout reservation ------------------------------------
    #
    # A vertical colorbar is drawn AFTER the graph, at ``xg(xgmax)+sep``, so it
    # falls outside the frame rectangle. The reserved width computed here
    # becomes the layout's right-hand margin (:meth:`_auto_margins_cm`), for a
    # lone plot exactly as for a grid, so the bar + ticks + rotated label are
    # not clipped off the page. It is derived purely from the colorbar dict
    # (which the recognizer recovers verbatim), so it recomputes identically on
    # a writer -> recognizer -> writer round trip -- though since metadata v2
    # the emitted rect is also read straight back, so the round trip no longer
    # depends on the re-derivation matching.

    #: Nominal tick-label text height (cm) used only to size the reserved
    #: colorbar margin. A fixed constant (not derived from ``style.fontsize``)
    #: keeps the reservation a pure function of the round-tripping colorbar
    #: dict; a little slack here only widens the margin slightly.
    _CBAR_TEXT_HEI_CM = 0.42

    @staticmethod
    def _estimate_tick_chars(zmin, zmax, fmt) -> int:
        """Widest tick-number character count for a GLE ``fix N`` format.

        Deterministic estimate from the z-range and the ``format$`` string;
        used only to size the reserved colorbar margin (see
        :meth:`_colorbar_reserved_cm`).
        """
        decimals = 1
        parts = str(fmt).strip().lower().split()
        if len(parts) == 2 and parts[0] == "fix":
            try:
                decimals = max(int(parts[1]), 0)
            except ValueError:
                decimals = 1

        def width_of(v) -> int:
            v = float(v)
            n = len(f"{abs(v):.{decimals}f}")
            if v < 0:
                n += 1  # minus sign
            return n

        return max(width_of(zmin), width_of(zmax), 3)

    @classmethod
    def _colorbar_reserved_cm(cls, cb: dict) -> float:
        """Right-hand space (cm), measured from ``xgmax``, a colorbar needs.

        Sized honestly from how ``gleplot_colorbar_v`` lays out (see
        :func:`gleplot.palettes.colorbar_sub_text`): the ``sep`` gap, the bar
        (``wd``), then whichever is wider -- the tick marks + numbers to the
        bar's right, or the rotated axis ``label`` (drawn at ``rc + 1.3``).
        """
        wd = float(cb["width"])
        sep = float(cb["sep"])
        hei = cls._CBAR_TEXT_HEI_CM
        charw = 0.6 * hei
        nchars = cls._estimate_tick_chars(cb["zmin"], cb["zmax"], cb.get("format"))
        # Both extents are measured from the bar's right edge.
        tick_extent = wd / 3.0 + 0.1 + nchars * charw
        label_extent = (1.3 + hei) if cb.get("label") else 0.0
        return sep + wd + max(tick_extent, label_extent) + 0.3  # + safety pad

    def _axes_colorbar_reserved_cm(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ) -> float:
        """Max reserved colorbar margin (cm) over an axes' heatmaps (0 if none).

        A heatmap skipped for a dangling reference draws no colorbar, so it
        reserves no margin either.
        """
        resolution = resolution or SourceResolution()
        reserved = 0.0
        for hm in resolution.visible(ax.heatmaps):
            cb = hm.get("colorbar")
            if cb:
                reserved = max(reserved, self._colorbar_reserved_cm(cb))
        return reserved

    def _collect_sub_texts(self, resolution: Optional[SourceResolution] = None):
        """Gather the palette/colorbar/clabel sub definitions this figure needs.

        Returns the deterministic ordered list of sub-definition texts: used
        palette subs sorted by name, then the colorbar sub (if any colorbar),
        then the contour-labels sub (if any clabel). Skipped (dangling) grid
        series contribute nothing, so a write that drops the only heatmap
        does not leave an unused palette sub behind.
        """
        from . import palettes as _pal

        resolution = resolution or SourceResolution()
        used_cmaps = set()
        any_colorbar = False
        any_clabel = False
        for ax in self.axes_list:
            for hm in resolution.visible(ax.heatmaps):
                if _pal.cmap_needs_sub(hm["cmap"]):
                    used_cmaps.add(hm["cmap"])
                if hm.get("colorbar"):
                    any_colorbar = True
            for ct in resolution.visible(ax.contours):
                if ct.get("clabel"):
                    any_clabel = True

        subs = []
        for cmap in sorted(used_cmaps):
            text = _pal.palette_sub_text(cmap)
            if text:
                subs.append(text)
        if any_colorbar:
            subs.append(_pal.colorbar_sub_text())
        if any_clabel:
            subs.append(_pal.contour_labels_sub_text())
        return subs

    def _emit_pre_graph_blocks(
        self, writer: GLEWriter, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Write sidecars + ``begin fitz``/``begin contour`` blocks for an axes.

        These execute before the graph reads the (generated) grid/contour
        files, so they are emitted immediately before the axes' ``begin graph``.
        """
        resolution = resolution or SourceResolution()
        for hm in resolution.visible(ax.heatmaps):
            if hm["source"] == "points":
                writer.add_points_sidecar(hm["data_file"], hm["x"], hm["y"], hm["zpts"])
                # tripcolor's fitz omits ncontour (GLE default), keeping the
                # heatmap model's ncontour honestly None.
                writer.add_fitz_block(
                    hm["data_file"], hm["extent"], hm["gridsize"], None
                )
            else:
                writer.add_z_sidecar(
                    hm["data_file"], hm["z"], hm["extent"], hm["origin"]
                )

        for ct in resolution.visible(ax.contours):
            if ct["source"] == "points":
                writer.add_points_sidecar(ct["data_file"], ct["x"], ct["y"], ct["zpts"])
                writer.add_fitz_block(
                    ct["data_file"], ct["extent"], ct["gridsize"], ct["ncontour"]
                )
            else:
                writer.add_z_sidecar(ct["data_file"], ct["z"], ct["extent"], "lower")
            writer.add_contour_block(self._contour_z_file(ct), ct["levels"])

    def _emit_post_graph_calls(
        self, writer: GLEWriter, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Write the post-graph colorbar and contour-label sub calls."""
        resolution = resolution or SourceResolution()
        for hm in resolution.visible(ax.heatmaps):
            cb = hm.get("colorbar")
            if not cb:
                continue
            palette_call = self._palette_call_for(hm["cmap"])
            writer.add_colorbar_call(
                sep=cb["sep"],
                zmin=cb["zmin"],
                zmax=cb["zmax"],
                zstep=cb["zstep"],
                palette_call=palette_call,
                width=cb["width"],
                fmt=cb["format"],
                label=cb.get("label"),
            )
        for ct in resolution.visible(ax.contours):
            if ct.get("clabel"):
                clabels = self._contour_z_file(ct)[:-2] + "-clabels.dat"
                writer.add_clabel_call(clabels, ct["clabel_fmt"])

    @staticmethod
    def _palette_call_for(cmap: str) -> str:
        from . import palettes as _pal

        return _pal.palette_call_name(cmap)

    def _legend_offset(self, ax: Axes) -> Optional[Tuple[float, float]]:
        """This axes' legend offset in cm, or the figure-wide default.

        ``Axes.legend_offset`` is None until ``legend(offset=...)`` sets it;
        the figure's :class:`~gleplot.config.GLEGraphConfig` then supplies
        ``(legend_offset_x, legend_offset_y)``. Those default to ``(0, 0)``,
        which means "no offset" and is returned as None so no ``offset``
        clause is written at all.
        """
        offset: Optional[Tuple[float, float]] = getattr(ax, "legend_offset", None)
        if offset is not None:
            return offset
        default = (float(self.graph.legend_offset_x), float(self.graph.legend_offset_y))
        return None if default == (0.0, 0.0) else default

    def _axis_style(self, ax: Axes, prefix: str) -> AxisStyle:
        """Collect one axis' styling off ``ax`` into a writer :class:`AxisStyle`.

        Flat model attributes (``xformat``, ``xgrid``, ``xlabel_size``, ...)
        in, one parameter object out, with the figure-wide
        :class:`~gleplot.config.GLEGraphConfig` distances applied where the
        axes sets none: ``xlabel_distance`` for the x title,
        ``ylabel_distance`` for the y AND y2 titles (GLE's ``ytitle``/
        ``y2title`` are the same decoration on opposite sides).

        Only x and y have a ``grid``: GLE's grid is the axis' own ticks
        stretched across the graph, so a y2 grid would duplicate the y one.
        """
        graph_cfg = self.graph
        dist_default = (
            graph_cfg.xlabel_distance if prefix == "x" else graph_cfg.ylabel_distance
        )
        title_dist = getattr(ax, f"{prefix}label_dist")
        return AxisStyle(
            fmt=getattr(ax, f"{prefix}format"),
            grid=getattr(ax, f"{prefix}grid", None) if prefix != "y2" else None,
            grid_lstyle=getattr(ax, f"{prefix}grid_lstyle", None),
            grid_lwidth=getattr(ax, f"{prefix}grid_lwidth", None),
            grid_color=getattr(ax, f"{prefix}grid_color", None),
            title_size=getattr(ax, f"{prefix}label_size"),
            title_color=getattr(ax, f"{prefix}label_color"),
            title_dist=title_dist if title_dist is not None else dist_default,
            label_size=getattr(ax, f"{prefix}ticklabel_size"),
            label_color=getattr(ax, f"{prefix}ticklabel_color"),
            label_angle=getattr(ax, f"{prefix}ticklabel_angle"),
        )

    def _write_axes_content(
        self, writer: GLEWriter, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """
        Write all plot content for a single Axes into the current graph block.

        This method is shared between single-plot and multi-subplot paths.

        Every series list is walked through ``resolution``, so a series is
        seen here already carrying its numbers (inline or resolved from a
        provider table) or not seen at all (dangling reference, skipped).

        Parameters
        ----------
        writer : GLEWriter
            The GLE writer to append commands to.
        ax : Axes
            The axes whose content should be written.
        resolution : SourceResolution, optional
            The write's source resolution. Omitted (``None``) means "every
            series is inline", which is what a direct caller outside
            :meth:`_generate_gle_with_files` gets.
        """
        resolution = resolution or SourceResolution()

        # Axis properties
        writer.add_axes(
            xlabel=ax.xlabel_text or None,
            ylabel=ax.ylabel_text or None,
            y2label=ax.y2label_text or None,
            title=ax.title_text or None,
            xlog=(ax.xscale == "log"),
            ylog=(ax.yscale == "log"),
            y2log=(ax.y2scale == "log"),
            xmin=ax.xmin,
            xmax=ax.xmax,
            ymin=ax.ymin,
            ymax=ax.ymax,
            y2min=ax.y2min,
            y2max=ax.y2max,
            show_xlabel=ax._show_xlabel,
            show_ylabel=ax._show_ylabel,
            show_xticks=ax._show_xticks,
            show_yticks=ax._show_yticks,
            remove_last_xtick=getattr(ax, "_remove_last_xtick", False),
            remove_last_ytick=getattr(ax, "_remove_last_ytick", False),
            remove_first_xtick=getattr(ax, "_remove_first_xtick", False),
            remove_first_ytick=getattr(ax, "_remove_first_ytick", False),
            xdticks=ax.xdticks,
            ydticks=ax.ydticks,
            xdsubticks=ax.xdsubticks,
            ydsubticks=ax.ydsubticks,
            xplaces=ax.xplaces,
            yplaces=ax.yplaces,
            xnames=ax.xnames,
            ynames=ax.ynames,
            xaxis_off=ax._xaxis_off,
            yaxis_off=ax._yaxis_off,
            x2axis_off=ax._x2axis_off,
            y2axis_off=ax._y2axis_off,
            xstyle=self._axis_style(ax, "x"),
            ystyle=self._axis_style(ax, "y"),
            y2style=self._axis_style(ax, "y2"),
            title_size=ax.title_size,
            title_color=ax.title_color,
            title_dist=(
                ax.title_dist
                if ax.title_dist is not None
                else self.graph.title_distance
            ),
        )

        # Heatmap colormap (drawn behind everything as the background) and
        # contour polylines, before the ordinary series (fills, bars, ...).
        for hm in resolution.visible(ax.heatmaps):
            writer.add_colormap(
                self._heatmap_z_file(hm),
                hm["pixels"],
                self._cmap_mode(hm["cmap"]),
                hm["vmin"],
                hm["vmax"],
                hm["invert"],
                hm["interpolation"],
            )

        for ct in resolution.visible(ax.contours):
            cdata = self._contour_z_file(ct)[:-2] + "-cdata.dat"
            writer.add_contour_line(
                cdata, ct["color"], ct["linewidth"], ct["linestyle"]
            )

        # Add fill regions (background). axvspan/axhspan bands are realized
        # here too: they are declarations until the axis limits are known, and
        # they belong in the same background layer as fills so the data series
        # always draw on top of their guides.
        limits = (ax.xmin, ax.xmax, ax.ymin, ax.ymax)
        fill_pairs = resolution.pairs(ax.fills) + [
            (span, span) for span in ax.materialize_spans(limits)
        ]
        for fill_series, fill_data in fill_pairs:
            writer.add_fill_between(
                fill_data["x"],
                fill_data["y1"],
                fill_data["y2"],
                fill_data["data_file"],
                fill_data["color"],
                fill_data["alpha"],
                offset=fill_data.get("offset", 0.0),
                column_names=fill_data.get("column_names"),
                binding=resolution.binding(fill_series),
            )

        # Reference lines (axvline/axhline), drawn above the shaded bands but
        # still below every data series.
        for ref_data in ax.materialize_reflines(limits):
            writer.add_plot_line(
                ref_data["x"],
                ref_data["y"],
                ref_data["data_file"],
                color=ref_data["color"],
                linestyle=ref_data["linestyle"],
                linewidth=ref_data["linewidth"],
                label=ref_data["label"],
                marker=None,
                markersize=ref_data["markersize"],
                yaxis="y",
                offset=0.0,
                column_names=ref_data.get("column_names"),
            )

        for kind, series, series_data in resolution.drawables(ax):
            binding = resolution.binding(series)
            if kind == "bar":
                writer.add_bar_chart(
                    series_data["x"],
                    series_data["height"],
                    series_data["data_file"],
                    series_data["colors"],
                    series_data["label"],
                    column_names=series_data.get("column_names"),
                    binding=binding,
                )
            elif kind == "line":
                writer.add_plot_line(
                    series_data["x"],
                    series_data["y"],
                    series_data["data_file"],
                    color=series_data["color"],
                    linestyle=series_data["linestyle"],
                    linewidth=series_data["linewidth"],
                    label=series_data["label"],
                    marker=series_data.get("marker"),
                    markersize=series_data.get("markersize", 0.1),
                    yaxis=series_data.get("yaxis", "y"),
                    offset=series_data.get("offset", 0.0),
                    column_names=series_data.get("column_names"),
                    binding=binding,
                )
            elif kind == "scatter":
                writer.add_plot_line(
                    series_data["x"],
                    series_data["y"],
                    series_data["data_file"],
                    color=series_data["color"],
                    linestyle=series_data.get("linestyle", "none"),
                    marker=series_data["marker"],
                    markersize=series_data["markersize"],
                    label=series_data["label"],
                    yaxis=series_data.get("yaxis", "y"),
                    offset=series_data.get("offset", 0.0),
                    column_names=series_data.get("column_names"),
                    binding=binding,
                )
            else:
                writer.add_errorbar(
                    series_data["x"],
                    series_data["y"],
                    series_data["data_file"],
                    color=series_data["color"],
                    linestyle=series_data["linestyle"],
                    linewidth=series_data["linewidth"],
                    label=series_data["label"],
                    marker=series_data["marker"],
                    markersize=series_data["markersize"],
                    yerr_up=series_data["yerr_up"],
                    yerr_down=series_data["yerr_down"],
                    xerr_left=series_data["xerr_left"],
                    xerr_right=series_data["xerr_right"],
                    capsize=series_data.get("gle_capsize", series_data.get("capsize")),
                    yaxis=series_data.get("yaxis", "y"),
                    offset=series_data.get("offset", 0.0),
                    column_names=series_data.get("column_names"),
                    binding=binding,
                )

        # Add external-file series (no generated data files).
        for fs_data in ax.file_series:
            series_type = fs_data.get("series_type", "errorbar")
            if series_type == "line":
                writer.add_plot_line_from_file(
                    fs_data["data_file"],
                    fs_data["x_col"],
                    fs_data["y_col"],
                    color=fs_data.get("color", "BLUE"),
                    linestyle=fs_data.get("linestyle", "-"),
                    linewidth=fs_data.get("linewidth", 1.0),
                    label=fs_data.get("label"),
                    yaxis=fs_data.get("yaxis", "y"),
                    marker=fs_data.get("marker"),
                    markersize=fs_data.get("markersize", 0.1),
                )
            elif series_type == "bar":
                writer.add_bar_from_file(
                    fs_data["data_file"],
                    fs_data["x_col"],
                    fs_data["y_col"],
                    color=fs_data.get("color", "RED"),
                )
            elif series_type == "fill":
                writer.add_fill_from_file(
                    fs_data["data_file"],
                    fs_data["x_col"],
                    fs_data["y1_col"],
                    fs_data["y2_col"],
                    color=fs_data.get("color", "LIGHTBLUE"),
                )
            else:
                writer.add_errorbar_from_file(
                    fs_data["data_file"],
                    fs_data["x_col"],
                    fs_data["y_col"],
                    yerr_col=fs_data.get("yerr_col"),
                    color=fs_data["color"],
                    marker=fs_data.get("marker"),
                    markersize=fs_data.get("markersize", 0.1),
                    label=fs_data.get("label"),
                    capsize=fs_data.get("capsize"),
                    yaxis=fs_data.get("yaxis", "y"),
                )

        # Add text annotations.
        for text_data in ax.texts:
            writer.add_text(
                x=text_data["x"],
                y=text_data["y"],
                text=text_data["text"],
                color=text_data.get("color", "BLACK"),
                fontsize=text_data.get("fontsize"),
                halign=text_data.get("ha", "left"),
                box_color=text_data.get("box_color"),
            )

        # Add legend if needed. legend_on is tri-state: None means auto
        # (show iff labels exist); True/False is an explicit user choice.
        legend_sources = (
            resolution.visible(ax.lines)
            + resolution.visible(ax.scatters)
            + resolution.visible(ax.bars)
            + resolution.visible(ax.errorbars)
            + list(ax.file_series)
            + list(ax.reflines)
            + list(ax.spans)
        )
        labels_present = any(series.get("label") for series in legend_sources)
        show_legend = ax.legend_on if ax.legend_on is not None else labels_present
        if show_legend:
            writer.add_legend(
                ax.legend_pos,
                fontsize=getattr(ax, "legend_fontsize", None),
                frameon=getattr(ax, "legend_frameon", True),
                offset=self._legend_offset(ax),
            )
        elif labels_present:
            # GLE draws an implicit key from per-dataset key "label" tokens;
            # it must be switched off explicitly.
            writer.add_key_off()

    def _emit_break_decoration(
        self,
        writer: GLEWriter,
        bax: BrokenAxes,
        seg: Axes,
        cell_x: float,
        cell_w: float,
    ):
        """Emit the seam marker, or the shared titles, after a segment's graph.

        Called right after each broken-axis segment's ``end graph``, which is
        the only point where GLE's ``xg()``/``yg()`` refer to that segment's
        box. Every segment but the last gets the seam decoration on its right
        edge; the last one carries the titles, which are centred on the whole
        assembly (``cell_x + cell_w/2``) rather than on any single graph.
        """
        index = seg._break_index
        is_last = index == len(bax.segments) - 1

        if not is_last:
            if bax.divider == "line":
                writer.add_break_divider(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    lstyle=bax.divider_lstyle,
                )
            elif bax.divider == "slash":
                size = bax.break_mark_size
                writer.add_break_marks(
                    bax.gap,
                    color=rgb_to_gle(bax.divider_color),
                    linewidth=bax.divider_linewidth,
                    width_cm=0.65 * size,
                    height_cm=size,
                    separation_cm=0.3 * size,
                )
            return

        # Titles. GLE places its own xtitle one tick-label row below the frame;
        # 1.57 * the font height reproduces that offset (measured against a
        # native `xtitle` render, matching to ~0.02 cm), and the title sits
        # 0.55 * the font height above the frame.
        hei_cm = fontsize_pt_to_cm(self.style.fontsize)
        centre_x = cell_x + cell_w / 2.0
        if bax.xlabel_text:
            dist = bax.xlabel_dist if bax.xlabel_dist is not None else 1.57 * hei_cm
            writer.add_page_text(
                centre_x,
                f"yg(ygmin)-{writer._format_number(dist)}",
                bax.xlabel_text,
                just="tc",
            )
        if bax.title_text:
            dist = bax.title_dist if bax.title_dist is not None else 0.55 * hei_cm
            writer.add_page_text(
                centre_x,
                f"yg(ygmax)+{writer._format_number(dist)}",
                bax.title_text,
                just="bc",
            )

    # -- axis limits -----------------------------------------------------
    #
    # GLE derives an axis' range from the data when the script does not give
    # one, and REFUSES to compile a log axis whose range reaches zero or
    # below: "Error: illegal range for log axis: min = 0 max = 3". That makes
    # an omitted bound unusable on a log axis -- ``yaxis log`` over data
    # containing a zero is rejected exactly like ``yaxis min 0 log`` is -- so
    # gleplot has to resolve log limits itself and always emit a positive
    # ``min``. See :meth:`_apply_log_limits`.

    #: Range emitted for a log axis about which nothing positive is known
    #: (every value non-positive, or no in-memory data at all). Arbitrary, but
    #: legal, deterministic, and a decade wide so the axis still reads as
    #: logarithmic.
    _LOG_FALLBACK_RANGE = (1.0, 10.0)

    def _resolve_axis_limits(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Fill in ``ax``'s missing limits from its data, then make them legal.

        Autoscaling matters beyond aesthetics for bar charts (which need an
        explicit x range) and for every log axis (see above). Runs before the
        shared-axis synchronization, so what that unifies is already resolved.
        """
        if ax.xmin is None or ax.xmax is None:
            data_xmin, data_xmax = self._get_data_xlim(ax, resolution)
            if ax.xmin is None:
                ax.xmin = data_xmin
            if ax.xmax is None:
                ax.xmax = data_xmax
        if ax.ymin is None or ax.ymax is None:
            data_ymin, data_ymax = self._get_data_ylim(ax, resolution)
            if ax.ymin is None:
                ax.ymin = data_ymin
            if ax.ymax is None:
                ax.ymax = data_ymax

        self._normalize_inverted_log_limits(ax)
        self._apply_log_limits(ax, resolution)

    def _normalize_inverted_log_limits(self, ax: Axes):
        """Undo an axis inversion on a log axis, which GLE cannot draw.

        Descending limits invert an axis (``set_ylim(3, 1)``, matplotlib's
        idiom), and :meth:`GLEWriter._axis_direction` emits that as GLE's
        ``negate``. But GLE's ``negate`` mirrors the value *linearly* before
        taking the logarithm -- ``fnAxisX`` in ``axis.cpp`` computes
        ``max - (v - min)`` and only then ``log10`` -- so on a log axis it
        does not reverse the decades, it smears them: measured against GLE
        4.3.10, ``yaxis min 1 max 100 log negate`` puts 1, 10 and 100 at
        7.00, 6.88 and 1.00 cm, with the first two decades on top of each
        other.

        There is no way to spell a reversed log axis in GLE, so the inversion
        is dropped rather than drawn wrong, and said out loud.
        """
        for which, scale in (("x", ax.xscale), ("y", ax.yscale), ("y2", ax.y2scale)):
            if scale != "log":
                continue
            lo, hi = self._axis_limits(ax, which)
            if lo is None or hi is None or lo <= hi:
                continue
            warnings.warn(
                f"{which}-axis has descending limits ({lo!r} .. {hi!r}), "
                "which would invert it, but GLE cannot invert a log axis "
                f"(its 'negate' does not reverse the decades). Drawing "
                f"{hi!r} .. {lo!r} the usual way round instead.",
                UserWarning,
            )
            self._set_axis_limits(ax, which, hi, lo)

    def _apply_log_limits(
        self, ax: Axes, resolution: Optional[SourceResolution] = None
    ):
        """Force every log-scaled axis of ``ax`` onto a positive range.

        A log axis cannot show zero or negative values, and GLE will not
        compile a script that asks it to. matplotlib's answer is to keep
        drawing: it masks the non-positive values when autoscaling, and
        ignores a non-positive bound passed to ``set_xlim``/``set_ylim`` with
        a warning. gleplot does the same, and additionally has to *write down*
        the resulting range, because leaving a bound out would hand the
        decision back to GLE, which would fail on the same raw data.

        The replacement bound is therefore the axis' own data, bounded over
        its positive values only. The limits are stored back onto ``ax`` --
        like the ordinary autoscale above, which has always written what it
        derived back onto the axes -- so the model says what the script says,
        and a re-save (of this figure or of the file parsed back from it)
        finds nothing left to repair and warns no further.
        """
        for which, scale in (
            ("x", ax.xscale),
            ("y", ax.yscale),
            ("y2", ax.y2scale),
        ):
            if scale != "log":
                continue
            lo, hi = self._axis_limits(ax, which)
            fixed = self._log_safe_range(ax, which, lo, hi, resolution)
            if fixed != (lo, hi):
                setter = "set_xlim" if which == "x" else "set_ylim"
                warnings.warn(
                    f"{which}-axis is log-scaled, but the range it resolved "
                    f"to ({lo!r} .. {hi!r}) is not an increasing positive "
                    "one, which GLE refuses to draw. Using "
                    f"{fixed[0]:g} .. {fixed[1]:g} instead, from the positive "
                    f"values plotted on it. Call {setter}() with a positive "
                    "range to choose your own.",
                    UserWarning,
                )
                self._set_axis_limits(ax, which, *fixed)

    def _log_safe_range(
        self,
        ax: Axes,
        which: str,
        lo: Optional[float],
        hi: Optional[float],
        resolution: Optional[SourceResolution],
    ) -> Tuple[Optional[float], Optional[float]]:
        """``lo``..``hi`` made legal for a log axis, or returned untouched.

        Untouched is the common answer, and deliberately so: an omitted bound
        is only a problem when the data GLE would autoscale over reaches zero.
        A log plot of positive data keeps emitting a bare ``yaxis log``, and a
        series gleplot cannot see the numbers of (a file series) keeps its
        autoscale as well -- guessing a range for data this process never read
        would be worse than the error it is trying to avoid.

        When the range does need fixing, only the offending bound is replaced,
        so ``set_ylim(0, 400)`` on a log axis keeps its 400.
        """
        scan = {
            "x": self._get_data_xlim,
            "y": self._get_data_ylim,
            "y2": self._get_data_y2lim,
        }[which]

        # What the axis will actually span: the explicit bounds where given,
        # and what GLE would autoscale to where not.
        data_lo, data_hi = (None, None)
        if lo is None or hi is None:
            data_lo, data_hi = scan(ax, resolution)
        effective_lo = lo if lo is not None else data_lo
        effective_hi = hi if hi is not None else data_hi

        if effective_lo is None:
            # No visible data and no explicit bound: nothing to judge.
            return (lo, hi)
        if effective_lo > 0 and (effective_hi is None or effective_hi > effective_lo):
            return (lo, hi)

        pos_lo, pos_hi = scan(ax, resolution, positive_only=True)
        fallback_lo, decade = self._LOG_FALLBACK_RANGE
        new_lo = lo if (lo is not None and lo > 0) else pos_lo
        if new_lo is None:
            new_lo = fallback_lo
        new_hi = hi if (hi is not None and hi > new_lo) else pos_hi
        if new_hi is None or new_hi <= new_lo:
            new_hi = new_lo * decade
        return (float(new_lo), float(new_hi))

    @staticmethod
    def _axis_limits(ax: Axes, which: str) -> Tuple[Optional[float], Optional[float]]:
        if which == "x":
            return (ax.xmin, ax.xmax)
        if which == "y":
            return (ax.ymin, ax.ymax)
        return (ax.y2min, ax.y2max)

    @classmethod
    def _axis_span(
        cls, ax: Axes, which: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """``(lower, upper)`` extent of an axis, whichever way round it reads."""
        lo, hi = cls._axis_limits(ax, which)
        if lo is not None and hi is not None and lo > hi:
            return (hi, lo)
        return (lo, hi)

    @classmethod
    def _axis_is_inverted(cls, ax: Axes, which: str) -> bool:
        """True if the axis' limits descend, i.e. it is drawn inverted."""
        lo, hi = cls._axis_limits(ax, which)
        return lo is not None and hi is not None and lo > hi

    @staticmethod
    def _set_axis_limits(ax: Axes, which: str, lo: float, hi: float):
        if which == "x":
            ax.xmin, ax.xmax = lo, hi
        elif which == "y":
            ax.ymin, ax.ymax = lo, hi
        else:
            ax.y2min, ax.y2max = lo, hi

    def _synchronize_x_limits(self, resolution: Optional[SourceResolution] = None):
        """Synchronize x-axis limits across all axes when sharex is enabled."""
        # Find global x-axis limits
        lo_global = None
        hi_global = None
        inverted = False

        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.xmin is None or ax.xmax is None:
                data_xmin, data_xmax = self._get_data_xlim(ax, resolution)
                if ax.xmin is None:
                    ax.xmin = data_xmin
                if ax.xmax is None:
                    ax.xmax = data_xmax

            # Track the global SPAN. A descending pair is an inverted axis
            # (see GLEWriter._axis_direction), so read its extent through
            # min/max rather than trusting the order, and carry the inversion
            # over to the shared result -- sharing an axis must not silently
            # flip a panel back the right way up.
            lo, hi = self._axis_span(ax, "x")
            inverted = inverted or self._axis_is_inverted(ax, "x")
            if lo is not None and (lo_global is None or lo < lo_global):
                lo_global = lo
            if hi is not None and (hi_global is None or hi > hi_global):
                hi_global = hi

        # Apply global limits to all axes
        for ax in self.axes_list:
            if inverted and lo_global is not None and hi_global is not None:
                ax.xmin, ax.xmax = hi_global, lo_global
            else:
                ax.xmin, ax.xmax = lo_global, hi_global

    def _synchronize_y_limits(self, resolution: Optional[SourceResolution] = None):
        """Synchronize y-axis limits across all axes when sharey is enabled."""
        # Find global y-axis limits
        lo_global = None
        hi_global = None
        inverted = False

        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.ymin is None or ax.ymax is None:
                data_ymin, data_ymax = self._get_data_ylim(ax, resolution)
                if ax.ymin is None:
                    ax.ymin = data_ymin
                if ax.ymax is None:
                    ax.ymax = data_ymax

            # See _synchronize_x_limits on descending (inverted) pairs.
            lo, hi = self._axis_span(ax, "y")
            inverted = inverted or self._axis_is_inverted(ax, "y")
            if lo is not None and (lo_global is None or lo < lo_global):
                lo_global = lo
            if hi is not None and (hi_global is None or hi > hi_global):
                hi_global = hi

        # Apply global limits to all axes
        for ax in self.axes_list:
            if inverted and lo_global is not None and hi_global is not None:
                ax.ymin, ax.ymax = hi_global, lo_global
            else:
                ax.ymin, ax.ymax = lo_global, hi_global

    def _get_data_xlim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate x-axis limits from data.

        Reads through ``resolution``, so table-backed series autoscale from
        their resolved values and skipped (dangling) series contribute
        nothing -- the limits describe what will actually be drawn.

        With ``positive_only``, values <= 0 are dropped before bounding, which
        is what a log axis needs (:meth:`_apply_log_limits`); the result is
        ``(None, None)`` when nothing positive is plotted.
        """
        resolution = resolution or SourceResolution()
        xmin, xmax = None, None

        x_bearing: Sequence[Sequence[Series]] = (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.bars),
            resolution.visible(ax.errorbars),
        )
        for data_list in x_bearing:
            for data in data_list:
                x = _plottable(np.asarray(data["x"]), positive_only)
                if len(x) > 0:
                    if xmin is None or x.min() < xmin:
                        xmin = float(x.min())
                    if xmax is None or x.max() > xmax:
                        xmax = float(x.max())

        for fill_data in resolution.visible(ax.fills):
            x = _plottable(np.asarray(fill_data["x"]), positive_only)
            if len(x) > 0:
                if xmin is None or x.min() < xmin:
                    xmin = float(x.min())
                if xmax is None or x.max() > xmax:
                    xmax = float(x.max())

        for series in resolution.visible(ax.heatmaps) + resolution.visible(ax.contours):
            x0, x1 = series["extent"][0], series["extent"][1]
            if not positive_only or x0 > 0:
                if xmin is None or x0 < xmin:
                    xmin = float(x0)
            if not positive_only or x1 > 0:
                if xmax is None or x1 > xmax:
                    xmax = float(x1)

        # Vertical guides carry a data x-coordinate and, like matplotlib's
        # axvline/axvspan, participate in autoscaling. Horizontal ones do not:
        # their x extent is an axes FRACTION, so including it would be
        # circular.
        for value in _refline_axis_values(ax, "v"):
            if positive_only and value <= 0:
                continue
            if xmin is None or value < xmin:
                xmin = value
            if xmax is None or value > xmax:
                xmax = value

        return xmin, xmax

    def _get_data_ylim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate y-axis limits from data (see :meth:`_get_data_xlim`)."""
        resolution = resolution or SourceResolution()
        ymin, ymax = None, None

        # A series' ``offset`` shifts its trace vertically at plot time (the .dat
        # values stay raw), so autoscale must add it back when bounding the data
        # -- otherwise a waterfall stack falls off the auto-computed axis.
        offset_bearing: Sequence[Sequence[Series]] = (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
        )
        for data_list in offset_bearing:
            for data in data_list:
                y = _plottable(
                    np.asarray(data["y"]) + data.get("offset", 0.0), positive_only
                )
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())

        for bar_data in resolution.visible(ax.bars):
            height = _plottable(np.asarray(bar_data["height"]), positive_only)
            if len(height) > 0:
                if ymin is None or height.min() < ymin:
                    # Bars are drawn from a zero baseline, so the baseline
                    # bounds them from below -- except on a log axis, where
                    # zero is not a value the axis can show at all.
                    ymin = float(
                        height.min() if positive_only else min(0, height.min())
                    )
                if ymax is None or height.max() > ymax:
                    ymax = float(height.max())

        for fill_data in resolution.visible(ax.fills):
            off = fill_data.get("offset", 0.0)
            y1 = np.asarray(fill_data["y1"]) + off
            y2 = np.asarray(fill_data["y2"]) + off
            all_y = _plottable(np.concatenate([y1, y2]), positive_only)
            if len(all_y) > 0:
                if ymin is None or all_y.min() < ymin:
                    ymin = float(all_y.min())
                if ymax is None or all_y.max() > ymax:
                    ymax = float(all_y.max())

        for eb_data in resolution.visible(ax.errorbars):
            y = np.asarray(eb_data["y"]) + eb_data.get("offset", 0.0)
            yerr_up = eb_data.get("yerr_up")
            yerr_down = eb_data.get("yerr_down")

            if len(y) > 0:
                y_with_err = y.copy()
                if yerr_up is not None:
                    y_with_err_up = _plottable(y + np.asarray(yerr_up), positive_only)
                    if len(y_with_err_up) > 0 and (
                        ymax is None or y_with_err_up.max() > ymax
                    ):
                        ymax = float(y_with_err_up.max())
                if yerr_down is not None:
                    y_with_err_down = _plottable(
                        y - np.asarray(yerr_down), positive_only
                    )
                    if len(y_with_err_down) > 0 and (
                        ymin is None or y_with_err_down.min() < ymin
                    ):
                        ymin = float(y_with_err_down.min())

                y = _plottable(y, positive_only)
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())

        for series in resolution.visible(ax.heatmaps) + resolution.visible(ax.contours):
            y0, y1 = series["extent"][2], series["extent"][3]
            if not positive_only or y0 > 0:
                if ymin is None or y0 < ymin:
                    ymin = float(y0)
            if not positive_only or y1 > 0:
                if ymax is None or y1 > ymax:
                    ymax = float(y1)

        # Horizontal guides carry a data y-coordinate (see _get_data_xlim for
        # the mirror-image reasoning).
        for value in _refline_axis_values(ax, "h"):
            if positive_only and value <= 0:
                continue
            if ymin is None or value < ymin:
                ymin = value
            if ymax is None or value > ymax:
                ymax = value

        return ymin, ymax

    def _get_data_y2lim(
        self,
        ax: Axes,
        resolution: Optional[SourceResolution] = None,
        positive_only: bool = False,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate secondary-y limits from the series drawn against y2.

        Deliberately narrower than :meth:`_get_data_ylim`, which bounds *every*
        series on the axes regardless of which y axis it belongs to: y2 limits
        are normally left to GLE, and the one thing gleplot has to know for
        itself is what a log-scaled y2 can legally span. Only the series kinds
        that carry a ``yaxis`` field can be on y2 at all; bars, fills, grids
        and reference lines are always primary.
        """
        resolution = resolution or SourceResolution()
        y2min, y2max = None, None

        for data_list in (
            resolution.visible(ax.lines),
            resolution.visible(ax.scatters),
            resolution.visible(ax.errorbars),
        ):
            for data in data_list:
                if data.get("yaxis") != "y2":
                    continue
                y = _plottable(
                    np.asarray(data["y"]) + data.get("offset", 0.0), positive_only
                )
                if len(y) > 0:
                    if y2min is None or y.min() < y2min:
                        y2min = float(y.min())
                    if y2max is None or y.max() > y2max:
                        y2max = float(y.max())

        return y2min, y2max

    def view(self, dpi: Optional[int] = None, format: str = "png") -> Optional[object]:
        """
        Display the figure inline (in Jupyter notebooks) or save to a temporary file.

        This method renders the figure to an image format and displays it if running
        in a Jupyter notebook or IPython environment. Otherwise, it saves to a
        temporary file and returns the path.

        Parameters
        ----------
        dpi : int, optional
            Resolution in dots per inch. If None, uses figure's dpi setting.
        format : {'png', 'pdf'}, optional
            Output format. Default is 'png' for inline display.

        Returns
        -------
        Path or None
            Path to the generated file, or None when displayed inline in Jupyter.

        Raises
        ------
        RuntimeError
            If GLE compiler is not available.

        Examples
        --------
        >>> import gleplot as glp
        >>> fig = glp.figure()
        >>> ax = fig.add_subplot(111)
        >>> ax.plot([1, 2, 3], [1, 4, 9])
        >>> fig.view()  # Display in notebook

        Notes
        -----
        Requires GLE to be installed for compilation.
        In non-Jupyter environments, saves to a temporary file instead.
        """
        import tempfile

        if not self.compiler:
            raise RuntimeError("GLE compiler not available. Install GLE to use view().")

        output_dpi = dpi or self.dpi

        # Try to detect Jupyter/IPython environment
        try:
            from IPython import get_ipython
            from IPython.display import Image, display

            ipython = get_ipython()
            in_notebook = ipython is not None and "IPKernelApp" in get_ipython().config
        except ImportError:
            in_notebook = False

        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Save to temporary file
            self.savefig(str(tmp_path), format=format, dpi=output_dpi)

            if in_notebook:
                # Display inline in Jupyter
                if format == "png":
                    img = Image(filename=str(tmp_path))
                    display(img)
                    return None
                elif format == "pdf":
                    # For PDF, try to display or provide a link
                    print(f"PDF saved to: {tmp_path}")
                    print(
                        "Note: PDF inline display limited in Jupyter. Consider using 'png' format."
                    )
                    return tmp_path
            else:
                # Not in notebook - inform user of temp file location
                print(f"Plot saved to temporary file: {tmp_path}")
                print(f"Open this file to view the plot.")
                return tmp_path

        except Exception as e:
            # Clean up on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise e

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the figure to a JSON-safe project dictionary.

        Produces the full, lossless object-model representation used by the
        project-file format and (later) undo/redo snapshots. The result is a
        top-level envelope::

            {
                "format": "gleplot-project",
                "version": 1,
                "gleplot_version": <installed gleplot version>,
                "figure": { ... }
            }

        The ``figure`` block captures figure-level parameters (``figsize``,
        ``dpi``, ``sharex``, ``sharey``, ``data_prefix``), the data-file
        naming state, subplot layout overrides, unrecognized-content
        passthrough buckets (``passthrough_header``, ``passthrough_trailer``)
        and metadata-block passthrough (``metadata_extra``), the per-figure
        style / graph / marker configuration overrides (serialized via each
        config's own ``to_dict``), and every axes with all of its series and
        state (including its own ``passthrough`` bucket) via
        :meth:`Axes.to_dict`.

        Only authoritative state is serialized. Axis limits are serialized as
        they currently sit on each axes: limits explicitly set by the user are
        captured, while limits left unset remain ``None`` and are re-derived
        from data at GLE-generation time -- keeping the format independent of
        that (order-dependent, potentially expensive) derivation. Calling
        ``to_dict`` twice on an unchanged figure yields an identical dict.

        The generated-series ``data_file`` names and the figure's set of used
        data-file names are round-tripped exactly, so regenerated GLE does not
        depend on the module-global data-file counter. The counter's current
        value is nonetheless also saved (``global_data_counter``) so that
        continued plotting after :meth:`from_dict` in a fresh process picks up
        where the original session left off instead of restarting at 0 and
        colliding with (or duplicating) previously used ``data_N.dat`` names.
        The contour/heatmap/fitz sidecar counters get the same treatment
        (``sidecar_counters`` for a figure with a custom ``data_prefix``,
        ``global_sidecar_counters`` for the shared default-prefix counter --
        see ``axes._reserve_sidecar``), so a figure reloaded via
        :meth:`from_dict` and then given a new contour/heatmap series keeps
        numbering forward rather than restarting at ``1``.

        Returns
        -------
        dict
            JSON-serializable project dictionary.
        """
        from . import __version__
        from . import axes as _axes_module

        figure_block = {
            "figsize": list(self.figsize),
            "dpi": self.dpi,
            "sharex": self.sharex,
            "sharey": self.sharey,
            "data_prefix": self.data_prefix,
            "local_data_counter": self._local_data_counter,
            "global_data_counter": _axes_module._global_data_file_counter,
            "used_data_files": sorted(self._used_data_files),
            "sidecar_counters": dict(getattr(self, "_sidecar_counters", {}) or {}),
            "global_sidecar_counters": dict(_axes_module._global_sidecar_counters),
            "subplot_adjust": {k: float(v) for k, v in self._subplot_adjust.items()},
            "height_ratios": (
                list(self.height_ratios) if self.height_ratios is not None else None
            ),
            "width_ratios": (
                list(self.width_ratios) if self.width_ratios is not None else None
            ),
            "passthrough_header": list(self.passthrough_header),
            "passthrough_trailer": list(self.passthrough_trailer),
            "metadata_extra": dict(self.metadata_extra),
            "config": {
                "style": self.style.to_dict(),
                "graph": self.graph.to_dict(),
                "marker": self.marker_config.to_dict(),
            },
            "axes": [ax.to_dict() for ax in self.axes_list],
            # Broken-axis assemblies reference their segments by index into
            # "axes" (the segments themselves are serialized there in full).
            "broken_axes": [bax.to_dict() for bax in self.broken_axes],
        }

        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_VERSION,
            "gleplot_version": __version__,
            "figure": figure_block,
        }

    def requires_cairo(self) -> bool:
        """Whether rendering this figure needs GLE's ``-cairo`` device flag.

        True whenever the figure uses semi-transparency anywhere it can
        appear -- a ``fill_between``/``axvspan``/``axhspan`` with
        ``alpha < 1`` (:meth:`Axes.fill_between`, :meth:`Axes.axvspan`,
        :meth:`Axes.axhspan`), or any colour expressed directly as
        ``rgba(...)``/``rgba255(...)``. See
        :func:`gleplot.cairo_support.figure_requires_cairo` for the exact
        rule and :func:`gleplot.compiler.build_compile_args` for where the
        answer turns into a compiler flag.

        Built on :meth:`to_dict` (per SPEC's "render always works from a
        to_dict() snapshot" rule) rather than a live-model walk; axvspan/
        axhspan declarations carry their ``alpha`` from the moment they're
        created, so this sees them correctly even though their concrete x/y
        coordinates are only materialized later, at write time
        (:meth:`Axes.materialize_spans`).

        Returns
        -------
        bool
        """
        return figure_requires_cairo(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "Figure":
        """Reconstruct an equivalent :class:`Figure` from a project dict.

        Parameters
        ----------
        d : dict
            A project dictionary as produced by :meth:`to_dict`.

        Returns
        -------
        Figure
            A figure equivalent to the one that was serialized: round-tripping
            through :meth:`to_dict` reproduces an equal dictionary and
            regenerated GLE (with the same ``data_prefix``) is byte-identical.

        Raises
        ------
        ValueError
            If the envelope ``format`` is missing/unrecognized or the
            ``version`` is unsupported.

        Notes
        -----
        Unknown keys inside the envelope, the ``figure`` block, and the
        ``config`` sub-dicts (``style``/``graph``/``marker``) are ignored for
        forward compatibility.

        The module-global data-file counter (used to name auto-generated
        ``data_N.dat`` series when a figure has no custom ``data_prefix``) is
        restored to ``max(current in-process value, saved value)``. Taking
        the max means that in a fresh process this simply continues the
        saved sequence, while in a long-running process with other figures
        already using the counter, it never rewinds and risks a future
        collision.
        """
        from . import axes as _axes_module

        fmt = d.get("format")
        if fmt != PROJECT_FORMAT:
            raise ValueError(
                f"Unrecognized project format {fmt!r}; expected {PROJECT_FORMAT!r}"
            )
        version = d.get("version")
        if version not in SUPPORTED_PROJECT_VERSIONS:
            raise ValueError(
                f"Unsupported project version {version!r}; this build supports "
                f"version(s) {', '.join(str(v) for v in SUPPORTED_PROJECT_VERSIONS)}"
            )

        fig_block = d.get("figure")
        if not isinstance(fig_block, dict):
            raise ValueError("Project envelope is missing a 'figure' object")

        config = fig_block.get("config") or {}
        style = (
            GLEStyleConfig(
                **_filtered_dataclass_kwargs(GLEStyleConfig, config["style"])
            )
            if config.get("style")
            else None
        )
        graph = (
            GLEGraphConfig(
                **_filtered_dataclass_kwargs(GLEGraphConfig, config["graph"])
            )
            if config.get("graph")
            else None
        )
        marker = (
            GLEMarkerConfig(
                **_filtered_dataclass_kwargs(GLEMarkerConfig, config["marker"])
            )
            if config.get("marker")
            else None
        )

        figsize = fig_block.get("figsize", (8, 6))
        figsize = tuple(figsize)

        fig = cls(
            figsize=figsize,
            dpi=fig_block.get("dpi", 100),
            style=style,
            graph=graph,
            marker=marker,
            sharex=fig_block.get("sharex", False),
            sharey=fig_block.get("sharey", False),
            height_ratios=fig_block.get("height_ratios"),
            width_ratios=fig_block.get("width_ratios"),
        )

        # Restore the prefix verbatim, bypassing __init__'s validation. This is
        # recorded state, not a user-supplied value: the recognizer derives a
        # prefix from filenames already present in a parsed .gle, and those can
        # legitimately contain characters __init__ rejects (a quoted
        # 'data "my file_0.dat"' yields the prefix 'my file'). Re-validating
        # here would make such a figure impossible to round-trip -- and would
        # break GUI undo/redo, which restores every snapshot through from_dict.
        fig.data_prefix = fig_block.get("data_prefix")

        fig._local_data_counter = fig_block.get("local_data_counter", 0)
        fig._used_data_files = set(fig_block.get("used_data_files", []))
        fig._sidecar_counters = dict(fig_block.get("sidecar_counters") or {})
        fig._subplot_adjust = {
            k: float(v) for k, v in (fig_block.get("subplot_adjust") or {}).items()
        }
        fig.passthrough_header = list(fig_block.get("passthrough_header", []))
        fig.passthrough_trailer = list(fig_block.get("passthrough_trailer", []))
        fig.metadata_extra = dict(fig_block.get("metadata_extra", {}))

        saved_counter = fig_block.get("global_data_counter", 0)
        _axes_module._global_data_file_counter = max(
            _axes_module._global_data_file_counter, saved_counter
        )

        # Same "never rewind" treatment for the global sidecar (contour/
        # heatmap/fitz) counters (G8): take the per-kind max so continued
        # plotting in this process picks up past the highest index either
        # side has seen, instead of risking a future collision.
        saved_sidecar_counters = fig_block.get("global_sidecar_counters") or {}
        for _kind, _saved_idx in saved_sidecar_counters.items():
            _axes_module._global_sidecar_counters[_kind] = max(
                _axes_module._global_sidecar_counters.get(_kind, 0), _saved_idx
            )

        fig.axes_list = [
            Axes.from_dict(fig, ax_d) for ax_d in fig_block.get("axes", [])
        ]
        # Rebind the broken-axis groupings once every segment exists; this also
        # restores each segment's ``_break_owner`` back-reference (the one
        # piece of segment state Axes.from_dict cannot recover on its own).
        fig.broken_axes = [
            BrokenAxes.from_dict(fig, b_d) for b_d in fig_block.get("broken_axes", [])
        ]
        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

        return fig

    def close(self):
        """Close figure."""
        self.axes_list.clear()
        self.broken_axes.clear()
        self._current_axes = None

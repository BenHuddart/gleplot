"""GLE file writer for gleplot."""

import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .config import GLEStyleConfig, GLEGraphConfig, GLEMarkerConfig, GlobalConfig
from .parser.units import (
    inches_to_cm,
    linewidth_pt_to_cm,
    fontsize_pt_to_cm,
)
from .parser.tables import KEY_POSITIONS_LONG_TO_SHORT


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


def _quote_filename(name: str) -> str:
    """Always quote a filename for GLE.

    Used for the contour/heatmap grid and generated files: their names contain
    hyphens (``-cdata.dat``/``-clabels.dat``) which GLE would otherwise parse
    as subtraction ("left hand side contains unquoted string"). Quoting is
    always valid, so it is applied unconditionally in these contexts.
    """
    return '"' + str(name).replace('"', '\\"') + '"'


class GLEWriter:
    """Writer for GLE script files.

    Parameters
    ----------
    figsize : tuple, optional
        Figure size (width, height) in inches. Default: (8, 6)
    dpi : int, optional
        Dots per inch for PNG output. Default: 100
    style : GLEStyleConfig, optional
        Style configuration. If None, uses global default.
    graph : GLEGraphConfig, optional
        Graph configuration. If None, uses global default.
    marker : GLEMarkerConfig, optional
        Marker configuration. If None, uses global default.
    """

    def __init__(
        self,
        figsize: Tuple[float, float] = (8, 6),
        dpi: int = 100,
        style: Optional[GLEStyleConfig] = None,
        graph: Optional[GLEGraphConfig] = None,
        marker: Optional[GLEMarkerConfig] = None,
    ):
        """Initialize GLE writer with optional configuration objects."""
        self.figsize = figsize
        self.dpi = dpi
        # Convert inches to cm (GLE uses cm)
        self.width_cm = inches_to_cm(figsize[0])
        self.height_cm = inches_to_cm(figsize[1])

        # Get configuration (fall back to global defaults)
        self.style = style or GlobalConfig.get_style()
        self.graph = graph or GlobalConfig.get_graph()
        self.marker = marker or GlobalConfig.get_marker()

        self.lines_gle = []  # GLE script lines
        self.data_files = {}  # {filename: data_content}
        # Raw-content sidecars (heatmap/contour ``.z`` grids and scattered
        # ``points.dat`` triples). They are written like any data file but are
        # NOT columnar imports, so they are excluded from the ``import-data``
        # metadata list (see Figure._build_metadata_dict).
        self.raw_sidecars: set = set()
        self.dataset_index = (
            1  # Counter for unique dataset names (d1, d2, d3, ...) - GLE is 1-indexed
        )
        self._pending_graph_text_lines: List[str] = []
        # Sticky GLE interpreter state as far as add_text is concerned: 'set
        # hei'/'set color'/'set just' persist across `write` statements until
        # changed again (real GLE semantics -- see recognizer._try_one_text,
        # the read-side counterpart). Tracking the currently-active emitted
        # value here lets add_text skip a redundant 'set ...' line when a
        # later text asks for the same value already in effect, instead of
        # restating it. Seeded with the preamble's 'set hei' (already emitted
        # unconditionally by add_preamble) so the first add_text call also
        # skips a redundant 'set hei' when its fontsize matches the style
        # default.
        self._text_state_hei_cm: Optional[str] = self._format_number(
            fontsize_pt_to_cm(self.style.fontsize)
        )
        self._text_state_color: str = "BLACK"
        self._text_state_just: str = "left"

    def add_preamble(
        self,
        include_graph_begin: bool = True,
        metadata_lines: Optional[List[str]] = None,
        passthrough_header: Optional[List[str]] = None,
    ):
        """Add GLE preamble.

        Includes:
        - Page size setup
        - Font configuration (from style config)
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
        """
        self.lines_gle.extend(
            [
                "! GLE graphics file",
                "! Generated by gleplot",
            ]
        )
        if metadata_lines:
            self.lines_gle.extend(metadata_lines)
        self.lines_gle.extend(
            [
                "",
                f"size {self._format_number(self.width_cm)} {self._format_number(self.height_cm)}",
            ]
        )
        # Only set font if explicitly specified
        if self.style.font:
            self.lines_gle.append(f"set font {self.style.font}")
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
        The deferred graph-data-coordinate text queued by :meth:`add_text`
        (``_pending_graph_text_lines``) is flushed here, AFTER 'end graph' --
        that is deliberate (GLE's ``xg()``/``yg()`` need the graph that just
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
        if self._pending_graph_text_lines:
            self.lines_gle.append("gsave")
            self.lines_gle.extend(self._pending_graph_text_lines)
            self.lines_gle.append("grestore")
            self._pending_graph_text_lines = []
            # grestore reverted the ambient GLE state to what it was before
            # this panel's gsave (i.e. the script-start default: BLACK,
            # style-default height, left-justified) -- resync the sticky
            # trackers to match, or the NEXT panel's add_text calls would
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
            Used for subplot layouts where each graph needs an explicit size.
            Subplots use 'scale 1 1' to make plot area fill the entire graph box
            with no padding, so axes from adjacent subplots can touch.
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

    def add_graph_box_size(self, width_cm: float, height_cm: float):
        """Emit a bare graph ``size W H`` (no ``scale``) for the single-plot path.

        Unlike :meth:`add_graph_size` (which, in ``auto`` mode, emits
        ``scale auto`` and lets GLE fill the whole page), this pins the graph
        box to ``width_cm`` x ``height_cm`` while still letting GLE auto-inset
        the axis labels/ticks inside that box. Used only when a colorbar needs
        reserved space to the right of an otherwise single (1,1,1) graph, so
        the bar + ticks + rotated label are not clipped off the page.
        """
        self.lines_gle.append(
            f"    size {self._format_number(width_cm)} "
            f"{self._format_number(height_cm)}"
        )

    def add_axes(
        self,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        y2label: Optional[str] = None,
        title: Optional[str] = None,
        xlog: bool = False,
        ylog: bool = False,
        y2log: bool = False,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        ymin: Optional[float] = None,
        ymax: Optional[float] = None,
        y2min: Optional[float] = None,
        y2max: Optional[float] = None,
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
    ):
        """Add axis configuration.

        Parameters
        ----------
        xlabel, ylabel : str, optional
            Axis labels
        y2label : str, optional
            Secondary y-axis (right) label
        title : str, optional
            Plot title
        xlog, ylog : bool
            Whether to use logarithmic scale
        y2log : bool
            Whether to use logarithmic scale for y2axis
        xmin, xmax, ymin, ymax : float, optional
            Axis limits
        y2min, y2max : float, optional
            Secondary y-axis limits
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

        Raises
        ------
        ValueError
            If a ``*names`` list is given without, or of a different length
            to, its ``*places`` list.
        """
        if xnames is not None and (xplaces is None or len(xnames) != len(xplaces)):
            raise ValueError("xnames must be the same length as xplaces")
        if ynames is not None and (yplaces is None or len(ynames) != len(yplaces)):
            raise ValueError("ynames must be the same length as yplaces")
        if title:
            self.lines_gle.append(f'    title "{title}"')

        # Only show axis titles if requested
        # Note: show_xlabel controls the title (e.g. "Time (s)"), not the tick marks
        if xlabel and show_xlabel:
            self.lines_gle.append(f'    xtitle "{xlabel}"')

        if ylabel and show_ylabel:
            self.lines_gle.append(f'    ytitle "{ylabel}"')

        # Add y2axis title if provided
        if y2label:
            self.lines_gle.append(f'    y2title "{y2label}"')

        # Handle axis ranges and tick labels
        # Note: We keep the axis and ticks visible but can hide the tick labels
        x_cmd = "    xaxis"
        if xmin is not None:
            x_cmd += f" min {self._format_number(xmin)}"
        if xmax is not None:
            x_cmd += f" max {self._format_number(xmax)}"
        if xlog:
            x_cmd += " log"
        if xdticks is not None:
            x_cmd += f" dticks {self._format_number(xdticks)}"
        if xdsubticks is not None:
            x_cmd += f" dsubticks {self._format_number(xdsubticks)}"
        if remove_first_xtick:
            x_cmd += " nofirst"  # Remove first tick label to prevent overlap
        if remove_last_xtick:
            x_cmd += " nolast"  # Remove last tick label to prevent overlap
        if xaxis_off:
            x_cmd += " off"

        # Add xaxis command if it has parameters
        if x_cmd != "    xaxis":
            self.lines_gle.append(x_cmd)

        if xplaces is not None:
            self.lines_gle.append(
                "    xplaces " + " ".join(self._format_number(v) for v in xplaces)
            )
        if xnames is not None:
            self.lines_gle.append(
                "    xnames "
                + " ".join(f'"{self._escape_gle_string(n)}"' for n in xnames)
            )

        # Hide x-axis tick labels if requested (but keep the ticks themselves)
        if not show_xticks:
            self.lines_gle.append("    xlabels off")

        # Same for y-axis
        y_cmd = "    yaxis"
        if ymin is not None:
            y_cmd += f" min {self._format_number(ymin)}"
        if ymax is not None:
            y_cmd += f" max {self._format_number(ymax)}"
        if ylog:
            y_cmd += " log"
        if ydticks is not None:
            y_cmd += f" dticks {self._format_number(ydticks)}"
        if ydsubticks is not None:
            y_cmd += f" dsubticks {self._format_number(ydsubticks)}"
        if remove_first_ytick:
            y_cmd += " nofirst"  # Remove first tick label to prevent overlap
        if remove_last_ytick:
            y_cmd += " nolast"  # Remove last tick label to prevent overlap
        if yaxis_off:
            y_cmd += " off"

        # Add yaxis command if it has parameters
        if y_cmd != "    yaxis":
            self.lines_gle.append(y_cmd)

        if yplaces is not None:
            self.lines_gle.append(
                "    yplaces " + " ".join(self._format_number(v) for v in yplaces)
            )
        if ynames is not None:
            self.lines_gle.append(
                "    ynames "
                + " ".join(f'"{self._escape_gle_string(n)}"' for n in ynames)
            )

        # Hide y-axis tick labels if requested (but keep the ticks themselves)
        if not show_yticks:
            self.lines_gle.append("    ylabels off")

        # Handle y2axis (secondary y-axis) if limits or log scale specified.
        #
        # GLE mirrors the primary axis onto the opposite side by default, and
        # that mirroring is what draws the closing edge of the box. Switching
        # the primary axis off takes the mirror with it: ``yaxis ... off``
        # silently removes the RIGHT-hand frame line too, even though nothing
        # asked for it. That is a real bug for a broken-axis assembly, whose
        # rightmost segment always has ``yaxis off`` (the y axis belongs to
        # the leftmost segment) and always wants its outer edge drawn -- the
        # panel otherwise renders open on the right and reads as clipped.
        # Re-assert the mirror explicitly whenever the primary side is off
        # and the mirror was not itself turned off.
        y2_on = yaxis_off and not y2axis_off
        if y2min is not None or y2max is not None or y2log or y2axis_off or y2_on:
            y2_cmd = "    y2axis"
            if y2min is not None:
                y2_cmd += f" min {self._format_number(y2min)}"
            if y2max is not None:
                y2_cmd += f" max {self._format_number(y2max)}"
            if y2log:
                y2_cmd += " log"
            if y2axis_off:
                y2_cmd += " off"
            elif y2_on:
                y2_cmd += " on"
            self.lines_gle.append(y2_cmd)

        # The top side has no gleplot-level configuration of its own; it is
        # only ever switched off (inner edge of a broken-axis assembly) --
        # or switched back on, for the same reason as y2axis above, when the
        # bottom axis is off and the top one is not.
        if x2axis_off:
            self.lines_gle.append("    x2axis off")
        elif xaxis_off:
            self.lines_gle.append("    x2axis on")

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
        self.lines_gle.append("gsave")
        self.lines_gle.append(f"set color {color}")
        if linewidth is not None:
            self.lines_gle.append(
                f"set lwidth {self._format_number(linewidth_pt_to_cm(linewidth))}"
            )
        if lstyle is not None:
            self.lines_gle.append(f"set lstyle {int(lstyle)}")
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

        self.lines_gle.append("gsave")
        self.lines_gle.append(f"set color {color}")
        if linewidth is not None:
            self.lines_gle.append(
                f"set lwidth {self._format_number(linewidth_pt_to_cm(linewidth))}"
            )
        self.lines_gle.append("set lstyle 1")
        for side in ("ygmin", "ygmax"):
            for sign in ("-", "+"):
                self.lines_gle.append(
                    f"amove {centre}{sign}{sep}-{w} yg({side})-{h}"
                )
                self.lines_gle.append(
                    f"aline {centre}{sign}{sep}+{w} yg({side})+{h}"
                )
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
        for row in data:
            line = " ".join(self._format_number(val) for val in row)
            lines.append(line)

        # Add trailing newline for GLE compatibility
        self.data_files[filename] = "\n".join(lines) + "\n"

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
        shifted = f"d{self.dataset_index}"
        self.dataset_index += 1
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
        yaxis: str = "y",
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
    ):
        """
        Add line plot to graph.

        Points are written to the data file, and drawn, in the order given
        (matplotlib's behavior). The one exception is a smoothed line, which
        GLE requires to be monotonic in x -- see :meth:`_row_order`.

        Parameters
        ----------
        x, y : arrays
            Data coordinates
        data_file : str
            External data file name
        color : str
            GLE color name
        linestyle : str
            Matplotlib linestyle ('-', '--', ':', '-.')
        linewidth : float
            Line width
        label : str, optional
            Legend label
        marker : str, optional
            GLE marker name
        markersize : float
            Marker size for GLE (msize)
        yaxis : str
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        column_names : list of str, optional
            Sidecar header row (e.g. ``['x', 'signal']``). When given, an
            explicit ``key`` clause is always emitted (the real label, or
            ``key ""`` when unlabeled) to neutralize GLE's auto-key-from-
            header behavior -- see :meth:`_key_clause`.
        """
        x_array = np.asarray(x)
        y_array = np.asarray(y)

        # A "no line" state is signalled by a linestyle of none/empty. GLE
        # supports markers on line datasets natively (``d1 line marker circle
        # msize 0.2``), so a series may carry a line, a marker, or both.
        has_line = linestyle not in ("none", "None", "", " ", None)

        # Rows go out in the caller's order unless this series is genuinely
        # smoothed -- see :meth:`_row_order`.
        order = self._row_order(x_array, has_line)
        self.add_data_file(data_file, [x_array[order], y_array[order]], column_names)

        # Generate plot command with unique dataset name
        d_name = f"d{self.dataset_index}"
        self.dataset_index += 1

        cmd = f"    data {_format_data_filename(data_file)} {d_name}=c1,c2"
        self.lines_gle.append(cmd)

        # A non-zero offset shifts the trace vertically at plot time via a
        # ``let`` on a fresh dataset, leaving the .dat file's values raw.
        display_name = self._apply_offset(d_name, offset) if offset else d_name

        # Generate line command
        line_cmd = f"    {display_name}"

        # Convert matplotlib linewidth (points) to GLE lwidth (cm)
        # If linewidth is 0 or 1, use default from style config
        if linewidth == 0 or linewidth == 1:
            gle_lwidth = linewidth_pt_to_cm(self.style.default_linewidth)
        else:
            gle_lwidth = linewidth_pt_to_cm(linewidth)

        if has_line:
            # Line plot; ``smooth`` only when opted in (see _line_token).
            line_cmd += self._line_token()
            line_cmd += f" color {color} lwidth {self._format_number(gle_lwidth)}"

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
        else:
            # No line: marker-only (scatter). Preserve the historical token
            # order ``marker <name> msize <size> color <color>``.
            line_cmd += f" marker {marker} msize {self._format_number(markersize)} color {color}"

        # Add y2axis directive if using secondary y-axis
        if yaxis == "y2":
            line_cmd += " y2axis"

        line_cmd += self._key_clause(label, bool(column_names))

        self.lines_gle.append(line_cmd)

    def add_bar_chart(
        self,
        x: np.ndarray,
        heights: np.ndarray,
        data_file: str,
        colors: Optional[List[str]] = None,
        label: Optional[str] = None,
        column_names: Optional[List[str]] = None,
    ):
        """
        Add bar chart to graph.

        Uses a single fill color for all bars due to GLE bar rendering
        limitations in downstream format conversion.

        Parameters
        ----------
        x : array
            Bar positions (categories)
        heights : array
            Bar heights
        data_file : str
            Data file name
        colors : list of str, optional
            GLE color names for each bar. If multiple colors are provided,
            the first color is used for all bars.
        label : str, optional
            Legend label (not currently supported by GLE for bar charts)
        column_names : list of str, optional
            Sidecar header row (e.g. ``['x', 'height']``). Unlike the
            ``dN ... key "..."`` dataset-display commands, GLE's ``bar``
            command has its own restricted sub-grammar with NO ``key``
            option at all (``bar dN fill COLOR key ""`` is a parse error).
            So when a header row is present, an explicit standalone
            ``dN key ""`` statement is emitted right after the ``bar``
            command to neutralize GLE's auto-key-from-header behavior
            (verified empirically: this statement alone draws nothing, and
            makes rendering byte-identical to the headerless case).
        """
        x = np.asarray(x, dtype=float)
        heights = np.asarray(heights, dtype=float)

        # Default to RED if no colors provided
        if colors is None:
            colors = ["RED"] * len(x)

        # GLE reliably supports one fill color per bar dataset.
        bar_color = colors[0]

        # Create single data file with all bars
        self.add_data_file(data_file, [x, heights], column_names)

        d_name = f"d{self.dataset_index}"
        self.dataset_index += 1
        cmd = f"    data {_format_data_filename(data_file)} {d_name}=c1,c2"
        self.lines_gle.append(cmd)

        bar_cmd = f"    bar {d_name} fill {bar_color}"
        self.lines_gle.append(bar_cmd)

        if column_names and not label:
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
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
    ):
        """
        Add plot with error bars to graph.

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
        x, y : arrays
            Data coordinates
        data_file : str
            External data file name
        color : str
            GLE color name
        linestyle : str
            Matplotlib linestyle ('-', '--', ':', '-.')
        linewidth : float
            Line width
        label : str, optional
            Legend label
        marker : str, optional
            GLE marker name
        markersize : float
            Marker size for GLE (msize)
        yerr_up : array, optional
            Upward vertical error bar magnitudes
        yerr_down : array, optional
            Downward vertical error bar magnitudes
        xerr_left : array, optional
            Leftward horizontal error bar magnitudes
        xerr_right : array, optional
            Rightward horizontal error bar magnitudes
        capsize : float, optional
            Width of error bar caps in cm
        yaxis : str
            Which y-axis to use: 'y' (left, default) or 'y2' (right)
        column_names : list of str, optional
            Sidecar header row (e.g. ``['x', 'signal', 'err']``). Only the
            MAIN dataset's ``key`` clause needs suppressing when unlabeled
            (see :meth:`_key_clause`) -- error sub-datasets (``d{n}=c1,cN``
            referenced via ``err``/``errup``/``herr``/...) are never added
            to GLE's key-rendering "used dataset" order on their own, so
            they never draw an auto-key regardless of any header-derived
            name on their column (verified empirically).
        """
        x_array = np.asarray(x)
        y_array = np.asarray(y)

        has_line = linestyle not in ("", "none", " ", "None")

        # Rows go out in the caller's order unless this series is genuinely
        # smoothed -- see :meth:`_row_order`. Every column below (centres and
        # error magnitudes alike) is indexed by the same ``order`` so a row
        # stays one point.
        order = self._row_order(x_array, has_line)

        # Build columns list: x, y, then error columns
        columns = [x_array[order], y_array[order]]
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
                columns.append(np.asarray(yerr_up)[order])
                yerr_up_col = col_idx
                yerr_down_col = col_idx  # Same column
                col_idx += 1
            else:
                if yerr_up is not None:
                    columns.append(np.asarray(yerr_up)[order])
                    yerr_up_col = col_idx
                    col_idx += 1
                if yerr_down is not None:
                    columns.append(np.asarray(yerr_down)[order])
                    yerr_down_col = col_idx
                    col_idx += 1

        if has_xerr:
            if xerr_symmetric:
                columns.append(np.asarray(xerr_left)[order])
                xerr_left_col = col_idx
                xerr_right_col = col_idx
                col_idx += 1
            else:
                if xerr_left is not None:
                    columns.append(np.asarray(xerr_left)[order])
                    xerr_left_col = col_idx
                    col_idx += 1
                if xerr_right is not None:
                    columns.append(np.asarray(xerr_right)[order])
                    xerr_right_col = col_idx
                    col_idx += 1

        # Write data file with all columns
        self.add_data_file(data_file, columns, column_names)

        # Generate dataset name for main data
        d_main = f"d{self.dataset_index}"
        self.dataset_index += 1

        # Build data command with all dataset references
        data_cmd = f"    data {_format_data_filename(data_file)} {d_main}=c1,c2"

        # Create error datasets referencing the same file columns
        err_datasets = {}

        if has_yerr:
            if yerr_symmetric:
                d_yerr = f"d{self.dataset_index}"
                self.dataset_index += 1
                data_cmd += f" {d_yerr}=c1,c{yerr_up_col}"
                err_datasets["yerr"] = d_yerr
            else:
                if yerr_up_col is not None:
                    d_yerr_up = f"d{self.dataset_index}"
                    self.dataset_index += 1
                    data_cmd += f" {d_yerr_up}=c1,c{yerr_up_col}"
                    err_datasets["yerr_up"] = d_yerr_up
                if yerr_down_col is not None:
                    d_yerr_down = f"d{self.dataset_index}"
                    self.dataset_index += 1
                    data_cmd += f" {d_yerr_down}=c1,c{yerr_down_col}"
                    err_datasets["yerr_down"] = d_yerr_down

        if has_xerr:
            if xerr_symmetric:
                d_xerr = f"d{self.dataset_index}"
                self.dataset_index += 1
                data_cmd += f" {d_xerr}=c1,c{xerr_left_col}"
                err_datasets["xerr"] = d_xerr
            else:
                if xerr_left_col is not None:
                    d_xerr_left = f"d{self.dataset_index}"
                    self.dataset_index += 1
                    data_cmd += f" {d_xerr_left}=c1,c{xerr_left_col}"
                    err_datasets["xerr_left"] = d_xerr_left
                if xerr_right_col is not None:
                    d_xerr_right = f"d{self.dataset_index}"
                    self.dataset_index += 1
                    data_cmd += f" {d_xerr_right}=c1,c{xerr_right_col}"
                    err_datasets["xerr_right"] = d_xerr_right

        self.lines_gle.append(data_cmd)

        # A non-zero offset shifts the plotted centre vertically at plot time
        # via a ``let`` on a fresh dataset; the raw .dat values are untouched
        # and the error datasets (magnitudes) stay bound to the raw columns, so
        # the bars ride along with the shifted centre.
        display_name = self._apply_offset(d_main, offset) if offset else d_main

        # Build the main dataset display command
        line_cmd = f"    {display_name}"

        # Convert linewidth
        if linewidth == 0 or linewidth == 1:
            gle_lwidth = linewidth_pt_to_cm(self.style.default_linewidth)
        else:
            gle_lwidth = linewidth_pt_to_cm(linewidth)

        # Add line/marker styling
        has_line = linestyle not in ("", "none", " ", "None")
        # GLE draws error bars (and their caps) in the DATASET's colour, which
        # only ever gets set by a ``color`` qualifier on the ``dN`` command --
        # an unstyled dataset defaults to black. Track whether the marker/line
        # styling already supplied one so a bars-only series can add it below.
        color_emitted = False

        if marker:
            line_cmd += f" marker {marker} msize {self._format_number(markersize)} color {color}"
            color_emitted = True
            # Also add line if linestyle is not 'none'
            if has_line:
                line_cmd += (
                    f"{self._line_token()} lwidth {self._format_number(gle_lwidth)}"
                )
                if linestyle == "--":
                    line_cmd += f" lstyle {self.style.line_style_dashed}"
                elif linestyle == ":":
                    line_cmd += f" lstyle {self.style.line_style_dotted}"
                elif linestyle == "-.":
                    line_cmd += f" lstyle {self.style.line_style_dashdot}"
        else:
            if has_line:
                line_cmd += self._line_token()
                line_cmd += f" color {color} lwidth {self._format_number(gle_lwidth)}"
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
        # matches :meth:`add_errorbar_from_file`'s marker-less form
        # (``dN color <c> err dM``).
        if not color_emitted:
            line_cmd += f" color {color}"

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
        if yaxis == "y2":
            line_cmd += " y2axis"

        line_cmd += self._key_clause(label, bool(column_names))

        self.lines_gle.append(line_cmd)

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
    ):
        """Add a marker/errorbar series that references columns in an external data file."""
        d_main = f"d{self.dataset_index}"
        self.dataset_index += 1

        data_cmd = (
            f"    data {_format_data_filename(data_file)} {d_main}=c{x_col},c{y_col}"
        )
        d_yerr = None
        if yerr_col is not None:
            d_yerr = f"d{self.dataset_index}"
            self.dataset_index += 1
            data_cmd += f" {d_yerr}=c{x_col},c{yerr_col}"
        self.lines_gle.append(data_cmd)

        line_cmd = f"    {d_main}"
        # Both branches must set ``color``: GLE draws the error bars in the
        # dataset's colour and an unstyled dataset falls back to black (see
        # :meth:`add_errorbar`).
        if marker:
            line_cmd += f" marker {marker} msize {self._format_number(markersize)} color {color}"
        else:
            line_cmd += f" color {color}"

        if d_yerr is not None:
            line_cmd += f" err {d_yerr}"
            if capsize is not None:
                line_cmd += f" errwidth {self._format_number(capsize)}"

        if yaxis == "y2":
            line_cmd += " y2axis"

        if label:
            line_cmd += f' key "{label}"'

        self.lines_gle.append(line_cmd)

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
    ):
        """Add a line series that references columns in an external data file."""
        d_main = f"d{self.dataset_index}"
        self.dataset_index += 1

        self.lines_gle.append(
            f"    data {_format_data_filename(data_file)} {d_main}=c{x_col},c{y_col}"
        )

        if linewidth == 0 or linewidth == 1:
            gle_lwidth = linewidth_pt_to_cm(self.style.default_linewidth)
        else:
            gle_lwidth = linewidth_pt_to_cm(linewidth)

        line_cmd = (
            f"    {d_main}{self._line_token()} color {color} "
            f"lwidth {self._format_number(gle_lwidth)}"
        )
        if linestyle == "--":
            line_cmd += f" lstyle {self.style.line_style_dashed}"
        elif linestyle == ":":
            line_cmd += f" lstyle {self.style.line_style_dotted}"
        elif linestyle == "-.":
            line_cmd += f" lstyle {self.style.line_style_dashdot}"

        if yaxis == "y2":
            line_cmd += " y2axis"

        if label:
            line_cmd += f' key "{label}"'

        self.lines_gle.append(line_cmd)

    def add_fill_between(
        self,
        x: np.ndarray,
        y1: np.ndarray,
        y2: np.ndarray,
        data_file: str,
        color: str = "LIGHTBLUE",
        alpha: float = 1.0,
        offset: float = 0.0,
        column_names: Optional[List[str]] = None,
    ):
        """
        Add fill between two curves.

        Parameters
        ----------
        x, y1, y2 : arrays
            x coordinates and two y series
        data_file : str
            External data file name
        color : str
            GLE fill color
        alpha : float
            Transparency (not directly supported in GLE, but stored)
        column_names : list of str, optional
            Sidecar header row (e.g. ``['x', 'upper', 'lower']``). GLE's
            ``fill dA,dB color X`` command (like ``bar``) has no ``key``
            option of its own, but the two datasets it references still go
            through the generic dataset-key mechanism (they're registered
            via the same "used dataset" bookkeeping as any ``dN`` display
            command), so a header row would still risk an auto-key on
            either one. Neutralize both with standalone ``dN key ""``
            statements when a header row is present (verified empirically
            byte-identical to the headerless case).
        """
        self.add_data_file(data_file, [x, y1, y2], column_names)

        # Create two unique dataset names for the fill between operation
        d1_name = f"d{self.dataset_index}"
        d2_name = f"d{self.dataset_index + 1}"
        self.dataset_index += 2

        cmd = f"    data {_format_data_filename(data_file)} {d1_name}=c1,c2 {d2_name}=c1,c3"
        self.lines_gle.append(cmd)

        # A non-zero offset shifts BOTH band edges vertically by the same amount
        # at plot time (a waterfall band rides with its trace), leaving the .dat
        # file raw. The displayed/keyed datasets are then the shifted ones.
        if offset:
            fill_a = self._apply_offset(d1_name, offset)
            fill_b = self._apply_offset(d2_name, offset)
        else:
            fill_a, fill_b = d1_name, d2_name

        # GLE fill between two datasets: fill d1,d2 color X
        self.lines_gle.append(f"    fill {fill_a},{fill_b} color {color}")

        if column_names:
            self.lines_gle.append(f'    {fill_a} key ""')
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
    ):
        """Add text annotation in graph data coordinates."""
        escaped_text = self._escape_gle_string(text)

        if fontsize is not None:
            hei_cm = self._format_number(fontsize_pt_to_cm(float(fontsize)))
            if hei_cm != self._text_state_hei_cm:
                self._pending_graph_text_lines.append(f"set hei {hei_cm}")
                self._text_state_hei_cm = hei_cm

        if color and color != self._text_state_color:
            self._pending_graph_text_lines.append(f"set color {color}")
            self._text_state_color = color

        just_map = {
            "left": "left",
            "center": "center",
            "right": "right",
        }
        just = just_map.get(str(halign).lower(), "left")
        if just != self._text_state_just:
            self._pending_graph_text_lines.append(f"set just {just}")
            self._text_state_just = just

        # Boxed text in graph-data coordinates can produce invalid bounds in
        # some GLE versions; keep label export robust by emitting plain text.
        # box_color is currently accepted for API compatibility but ignored.
        _ = box_color
        self._pending_graph_text_lines.append(
            f"amove xg({self._format_number(x)}) yg({self._format_number(y)})"
        )
        self._pending_graph_text_lines.append(f'write "{escaped_text}"')

    def add_legend(
        self,
        position: Optional[str] = None,
        fontsize: Optional[float] = None,
        frameon: bool = True,
    ):
        """Add legend configuration.

        Parameters
        ----------
        position : str, optional
            Legend position. If None, uses configured default.
            Options: 'tl', 'tr', 'bl', 'br', 'tc', 'bc', 'lc', 'rc', 'cc'
            or long form: 'top right', 'top left', 'bottom right', 'bottom left', 'center'
        fontsize : float, optional
            Key text height in matplotlib points, emitted as GLE's ``hei`` (in
            cm) on the same ``key`` line. ``None`` omits ``hei`` entirely, so
            GLE uses the current ``set hei`` -- the historical behaviour, and
            byte-identical output for figures that do not size their legend.
        frameon : bool
            Draw the box around the key (GLE's default). ``False`` appends
            ``nobox``.

        Notes
        -----
        All options go on the single ``key`` line: the recognizer models
        ``pos``/``hei``/``nobox`` there (see ``_parse_key_command``), and a
        second ``key`` command would compete with this one on re-emit.
        """
        # Use provided position or fall back to configured default
        pos = position if position is not None else self.graph.legend_position

        # Try long form, else use as-is (short form)
        gle_pos = KEY_POSITIONS_LONG_TO_SHORT.get(pos, pos)
        cmd = f"    key pos {gle_pos}"
        if fontsize is not None:
            cmd += f" hei {self._format_number(fontsize_pt_to_cm(float(fontsize)))}"
        if not frameon:
            cmd += " nobox"
        self.lines_gle.append(cmd)

    def add_key_off(self):
        """Suppress the graph key entirely.

        GLE draws a key whenever any dataset carries a ``key "label"``
        attribute, even without a ``key pos`` command, so an explicit
        ``key off`` is required to hide the legend for labeled series.
        """
        self.lines_gle.append("    key off")

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
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        files = {}

        # Write GLE script
        gle_file = output_dir / f"{base_filename}.gle"
        gle_file.write_text(self.get_gle_content(), encoding="utf-8")
        files["script"] = gle_file

        # Write data files
        for data_file, content in self.data_files.items():
            data_path = output_dir / data_file
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
        x0, x1, y0, y1 = (self._format_number(v) for v in extent)
        header = f"! nx {nx} ny {ny} xmin {x0} xmax {x1} ymin {y0} ymax {y1}"
        rows = z[::-1] if origin == "upper" else z
        lines = [header]
        for row in rows:
            lines.append(" ".join(self._format_number(v) for v in row))
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
        lines = []
        for xi, yi, zi in zip(x, y, z):
            lines.append(
                f"{self._format_number(xi)} {self._format_number(yi)} "
                f"{self._format_number(zi)}"
            )
        content = "\n".join(lines) + "\n"
        self.data_files[filename] = content
        self.raw_sidecars.add(filename)

    def add_sub_defs(self, sub_texts: List[str]):
        """Append self-contained subroutine definitions to the script.

        Each entry is a full multi-line ``sub ... end sub`` block. A blank
        line separates consecutive subs (and follows the last), matching the
        script's readable block spacing.
        """
        for text in sub_texts:
            self.lines_gle.extend(text.split("\n"))
            self.lines_gle.append("")

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

    def add_colormap(
        self,
        z_file: str,
        pixels,
        cmap_mode,
        vmin,
        vmax,
        invert: bool,
        interpolation: str,
    ):
        """Emit the ``colormap`` statement inside a graph block.

        Clause order (fixed): file, px, py, [color], [invert], [zmin v],
        [zmax v], [palette name], [interpolate mode]. ``cmap_mode`` is
        ``('color', None)`` for rainbow, ``('palette', 'gleplot_x')`` for a
        named palette, or ``('gray', None)`` for grayscale (no clause).
        """
        px, py = pixels
        cmd = f"    colormap {_quote_filename(z_file)} {int(px)} {int(py)}"
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
        d_name = f"d{self.dataset_index}"
        self.dataset_index += 1
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

    def add_colorbar_call(
        self,
        sep: float,
        zmin: float,
        zmax: float,
        zstep: float,
        palette_call: str,
        width: float,
        fmt: str,
        label: Optional[str],
    ):
        """Emit the post-graph vertical-colorbar sub call.

        Positioned at ``xg(xgmax)+sep yg(ygmin)`` with height spanning the
        graph. Named-argument call style (``zmin V zmax V ...``); note GLE
        matches named args by the parameter name WITHOUT the ``$`` suffix.
        """
        self.lines_gle.append(f"amove xg(xgmax)+{self._format_number(sep)} yg(ygmin)")
        lbl = self._escape_gle_string(label or "")
        self.lines_gle.append(
            f"gleplot_colorbar_v zmin {self._format_number(zmin)} "
            f"zmax {self._format_number(zmax)} "
            f"zstep {self._format_number(zstep)} "
            f'palette "{palette_call}" wd {self._format_number(width)} '
            f'hi yg(ygmax)-yg(ygmin) format "{fmt}" label "{lbl}"'
        )

    def add_clabel_call(self, clabels_file: str, fmt: str):
        """Emit the post-graph contour-label sub call."""
        self.lines_gle.append("amove 0 0")
        self.lines_gle.append(
            f"gleplot_contour_labels file {_quote_filename(clabels_file)} "
            f'format "{fmt}"'
        )

    def _row_order(self, x_array: np.ndarray, has_line: bool) -> np.ndarray:
        """Return the order in which a series' points are written to its .dat.

        The caller's order, always -- except for the one case that cannot use
        it. GLE's ``smooth`` fits a piecewise cubic *as a function of x* and
        needs the points in ascending x; handed a non-monotonic dataset it
        draws a tangle. So the rows are sorted by x when, and only when, this
        series will actually carry the ``smooth`` qualifier: it draws a line
        and ``smooth_curves`` is on (see :meth:`_line_token`).

        Everywhere else -- which, since smoothing became opt-in, is the great
        majority of series -- the caller's point order is both the drawing
        order and the .dat file's row order, as in matplotlib. It has to be:
        a series whose x is non-monotonic by design (a hysteresis loop, a
        parametric or closed curve, a time-ordered trace that doubles back)
        is a different figure once sorted, and the data file on disk would no
        longer be the data that was passed in.

        The sort is stable, so points sharing an x value keep their input
        order rather than being permuted by an unstable quicksort.
        """
        if has_line and self.graph.smooth_curves:
            return np.argsort(x_array, kind="stable")
        return np.arange(len(x_array))

    def _line_token(self) -> str:
        """Return the ``line`` token for a dataset display command.

        Every line-drawing path in this writer goes through here, so the
        ``smooth`` qualifier is decided in exactly one place.

        GLE's ``smooth`` replaces the polyline through the data with a fitted
        piecewise-cubic spline: the drawn curve then passes near, not through,
        the points, and it invents structure between them (overshoot on steep
        steps, ringing around noise). That is an interpolation of the data,
        not the data, so it is **off unless asked for** -- set
        ``GLEGraphConfig(smooth_curves=True)`` on a figure, or
        ``GlobalConfig.graph.smooth_curves = True`` globally, to opt in.

        Paths that deliberately never smooth, whatever the setting:

        - ``add_fill_between`` -- GLE's ``fill dA,dB`` command takes no
          ``smooth`` qualifier, so a band edge is always a polyline.
        - ``add_contour_line`` -- the ``-cdata.dat`` polylines come out of
          GLE's own contouring of the gridded surface; splining them would
          move the level away from the surface it was computed from.

        Smoothing also constrains point order (it needs monotonic x); that
        consequence is handled in :meth:`_row_order`, the only place a series
        is ever reordered.
        """
        return " line smooth" if self.graph.smooth_curves else " line"

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

    @staticmethod
    def _escape_gle_string(value: str) -> str:
        """Escape string for inclusion in GLE quoted text."""
        return str(value).replace('"', '\\"')

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
            return f' key "{label}"'
        if has_header:
            return ' key ""'
        return ""

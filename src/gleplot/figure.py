"""Figure class for gleplot."""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Literal
from .axes import Axes
from .writer import GLEWriter
from .compiler import GLECompiler, SUFFIX_TO_COMPILE_FORMAT
from .colors import rgb_to_gle
from .config import GLEStyleConfig, GLEGraphConfig, GLEMarkerConfig, GlobalConfig
from .parser import metadata as _gle_metadata

#: Envelope identifiers for the gleplot project-file format.
PROJECT_FORMAT = "gleplot-project"
PROJECT_VERSION = 1


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
        sharex: bool = False,
        sharey: bool = False,
        data_prefix: Optional[str] = None,
    ):
        """Initialize figure with optional configuration objects.

        Parameters
        ----------
        data_prefix : str, optional
            Custom prefix for data file names (e.g., 'test9' creates 'test9_0.dat', 'test9_1.dat').
            If None, uses global counter with ``data_`` prefix.
        """
        self.figsize = figsize
        self.dpi = dpi

        # Store configuration for passing to writer
        self.style = style or GlobalConfig.get_style()
        self.graph = graph or GlobalConfig.get_graph()
        self.marker_config = marker or GlobalConfig.get_marker()

        # Shared axes configuration
        self.sharex = sharex
        self.sharey = sharey

        # Custom data file naming
        self.data_prefix = data_prefix
        self._local_data_counter = 0  # Local counter when using custom prefix
        self._used_data_files: set[str] = set()
        self._subplot_adjust: dict[str, float] = {}

        self.axes_list = []  # List of Axes objects
        self._current_axes = None  # Current working axes

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

        self.compiler = None
        try:
            self.compiler = GLECompiler()
        except RuntimeError:
            pass  # GLE not available, but can still write scripts

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

    def savefig_gle(self, filepath: str, **kwargs) -> Path:
        """
        Save figure as GLE script.

        Parameters
        ----------
        filepath : str
            Output file path
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
        gle_content, data_content = self._generate_gle_with_files()

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
        gle_content, data_files = self._generate_gle_with_files()
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

            output_dpi = dpi or self.dpi
            self.compiler.compile(str(base_path), format, dpi=output_dpi)
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

    def _generate_gle(self) -> str:
        """Generate complete GLE script content."""
        content, _ = self._generate_gle_with_files()
        return content

    def _build_metadata_dict(self, data_files: dict) -> dict:
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
        data = {
            "dpi": self.dpi,
            "sharex": self.sharex,
            "sharey": self.sharey,
            "msize_scale": self.marker_config.msize_scale,
            "import-data": sorted(data_files.keys()),
        }
        data.update(self.metadata_extra)
        return data

    def _generate_gle_with_files(self) -> tuple:
        """
        Generate complete GLE script content with data files.

        Supports both single-plot and multi-subplot layouts.
        For a single axes (1,1,1), generates a simple graph block.
        For multiple axes, positions each graph using ``amove`` and
        explicit ``size`` commands based on the subplot grid.

        Uses figure's configured style, graph, and marker settings.

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
        )

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

        if is_single and no_fabricate:
            writer.add_preamble(
                include_graph_begin=False, passthrough_header=self.passthrough_header
            )
            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )
        elif is_single:
            # Single plot — backward-compatible simple layout
            writer.add_preamble(
                include_graph_begin=True, passthrough_header=self.passthrough_header
            )
            writer.add_graph_size()

            if self.axes_list:
                ax = self.axes_list[0]
                # Calculate axis limits from data if not explicitly set
                # This is especially important for bar charts which need explicit x-axis limits
                if ax.xmin is None or ax.xmax is None:
                    data_xmin, data_xmax = self._get_data_xlim(ax)
                    if ax.xmin is None:
                        ax.xmin = data_xmin
                    if ax.xmax is None:
                        ax.xmax = data_xmax
                if ax.ymin is None or ax.ymax is None:
                    data_ymin, data_ymax = self._get_data_ylim(ax)
                    if ax.ymin is None:
                        ax.ymin = data_ymin
                    if ax.ymax is None:
                        ax.ymax = data_ymax

                self._write_axes_content(writer, ax)
                graph_passthrough = ax.passthrough
            else:
                graph_passthrough = None

            writer.finalize(
                include_graph_end=True,
                graph_passthrough=graph_passthrough,
                passthrough_trailer=self.passthrough_trailer,
            )
        else:
            # Multi-subplot layout
            writer.add_preamble(
                include_graph_begin=False, passthrough_header=self.passthrough_header
            )

            # Determine grid dimensions from axes positions
            max_rows = max(ax.position[0] for ax in self.axes_list)
            max_cols = max(ax.position[1] for ax in self.axes_list)

            # Synchronize axis limits for shared axes
            if self.sharex:
                self._synchronize_x_limits()
            if self.sharey:
                self._synchronize_y_limits()

            # Calculate axis limits from data for any axes without explicit limits
            # This is especially important for bar charts
            for ax in self.axes_list:
                if ax.xmin is None or ax.xmax is None:
                    data_xmin, data_xmax = self._get_data_xlim(ax)
                    if ax.xmin is None:
                        ax.xmin = data_xmin
                    if ax.xmax is None:
                        ax.xmax = data_xmax
                if ax.ymin is None or ax.ymax is None:
                    data_ymin, data_ymax = self._get_data_ylim(ax)
                    if ax.ymin is None:
                        ax.ymin = data_ymin
                    if ax.ymax is None:
                        ax.ymax = data_ymax

            # Calculate per-subplot dimensions in cm.
            # Default margins/spacing are heuristic, but can be overridden via
            # subplots_adjust(left=..., right=..., top=..., bottom=..., wspace=..., hspace=...).

            # Check if any subplot has a title
            has_titles = any(ax.title_text for ax in self.axes_list)

            if self.sharex or self.sharey:
                # Top margin: more room needed if subplots have titles
                margin_top = 1.2 if has_titles else 0.5
                margin_right = 0.5
                # Bottom needs room for x-axis labels (when showing them)
                margin_bottom = 1.5 if self.sharex else 1.0
                # Left always needs room for y-axis labels in multi-subplot layouts
                margin_left = 1.5
            else:
                # Normal margins for non-shared layouts
                margin_top = 1.5 if has_titles else 1.0
                margin_bottom = 1.0
                margin_left = 1.0
                margin_right = 1.0

            # Convert margin overrides from normalized figure fractions to cm.
            if "left" in self._subplot_adjust:
                margin_left = self._subplot_adjust["left"] * writer.width_cm
            if "right" in self._subplot_adjust:
                margin_right = (1.0 - self._subplot_adjust["right"]) * writer.width_cm
            if "bottom" in self._subplot_adjust:
                margin_bottom = self._subplot_adjust["bottom"] * writer.height_cm
            if "top" in self._subplot_adjust:
                margin_top = (1.0 - self._subplot_adjust["top"]) * writer.height_cm

            avail_w = writer.width_cm - margin_left - margin_right
            avail_h = writer.height_cm - margin_bottom - margin_top

            # Spacing between subplots; defaults preserve existing behavior.
            default_hspace_cm = 0.0 if self.sharey else 1.5
            default_vspace_cm = 0.0 if self.sharex else 2.0
            wspace_frac = self._subplot_adjust.get("wspace")
            hspace_frac = self._subplot_adjust.get("hspace")

            if max_cols > 1 and wspace_frac is not None:
                denom = max_cols + wspace_frac * (max_cols - 1)
                cell_w = avail_w / denom if denom > 0 else avail_w / max_cols
                hspace = wspace_frac * cell_w
            else:
                hspace = default_hspace_cm
                usable_w = avail_w - (max_cols - 1) * hspace
                cell_w = usable_w / max_cols

            if max_rows > 1 and hspace_frac is not None:
                denom = max_rows + hspace_frac * (max_rows - 1)
                cell_h = avail_h / denom if denom > 0 else avail_h / max_rows
                vspace = hspace_frac * cell_h
            else:
                vspace = default_vspace_cm
                usable_h = avail_h - (max_rows - 1) * vspace
                cell_h = usable_h / max_rows

            for ax in self.axes_list:
                rows, cols, idx = ax.position
                # Convert 1-based index to row/col (row-major, top-to-bottom)
                row = (idx - 1) // cols  # 0-based, 0 = top row
                col = (idx - 1) % cols  # 0-based, 0 = left col

                # GLE coordinates: origin is bottom-left, y increases upward
                x_pos = margin_left + col * (cell_w + hspace)
                y_pos = (
                    writer.height_cm - margin_top - (row + 1) * cell_h - row * vspace
                )

                writer.add_amove(x_pos, y_pos)
                writer.begin_graph()
                writer.add_graph_size(
                    width_cm=cell_w, height_cm=cell_h, force_size=True
                )

                self._write_axes_content(writer, ax)

                writer.end_graph(passthrough=ax.passthrough)
                writer.lines_gle.append("")  # Blank line between subplots

            writer.finalize(
                include_graph_end=False, passthrough_trailer=self.passthrough_trailer
            )

        # Splice the metadata block in after the two header comment lines
        # ('! GLE graphics file' / '! Generated by gleplot') and before the
        # 'size ...' line -- add_preamble always emits exactly those two
        # lines first, so index 2 is the fixed, stable insertion point.
        metadata_dict = self._build_metadata_dict(writer.data_files)
        metadata_lines = _gle_metadata.emit_metadata(metadata_dict)
        if metadata_lines:
            writer.lines_gle[2:2] = metadata_lines

        return writer.get_gle_content(), writer.data_files

    def _write_axes_content(self, writer: GLEWriter, ax: Axes):
        """
        Write all plot content for a single Axes into the current graph block.

        This method is shared between single-plot and multi-subplot paths.

        Parameters
        ----------
        writer : GLEWriter
            The GLE writer to append commands to.
        ax : Axes
            The axes whose content should be written.
        """
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
        )

        # Add fill regions (background)
        for fill_data in ax.fills:
            writer.add_fill_between(
                fill_data["x"],
                fill_data["y1"],
                fill_data["y2"],
                fill_data["data_file"],
                fill_data["color"],
                fill_data["alpha"],
                offset=fill_data.get("offset", 0.0),
                column_names=fill_data.get("column_names"),
            )

        # Add bar charts
        for bar_data in ax.bars:
            writer.add_bar_chart(
                bar_data["x"],
                bar_data["height"],
                bar_data["data_file"],
                bar_data["colors"],
                bar_data["label"],
                column_names=bar_data.get("column_names"),
            )

        # Add line plots
        for line_data in ax.lines:
            writer.add_plot_line(
                line_data["x"],
                line_data["y"],
                line_data["data_file"],
                color=line_data["color"],
                linestyle=line_data["linestyle"],
                linewidth=line_data["linewidth"],
                label=line_data["label"],
                marker=line_data.get("marker"),
                markersize=line_data.get("markersize", 0.1),
                yaxis=line_data.get("yaxis", "y"),
                offset=line_data.get("offset", 0.0),
                column_names=line_data.get("column_names"),
            )

        # Add scatter plots
        for scatter_data in ax.scatters:
            writer.add_plot_line(
                scatter_data["x"],
                scatter_data["y"],
                scatter_data["data_file"],
                color=scatter_data["color"],
                linestyle=scatter_data.get("linestyle", "none"),
                marker=scatter_data["marker"],
                markersize=scatter_data["markersize"],
                label=scatter_data["label"],
                yaxis=scatter_data.get("yaxis", "y"),
                offset=scatter_data.get("offset", 0.0),
                column_names=scatter_data.get("column_names"),
            )

        # Add errorbar plots
        for eb_data in ax.errorbars:
            writer.add_errorbar(
                eb_data["x"],
                eb_data["y"],
                eb_data["data_file"],
                color=eb_data["color"],
                linestyle=eb_data["linestyle"],
                linewidth=eb_data["linewidth"],
                label=eb_data["label"],
                marker=eb_data["marker"],
                markersize=eb_data["markersize"],
                yerr_up=eb_data["yerr_up"],
                yerr_down=eb_data["yerr_down"],
                xerr_left=eb_data["xerr_left"],
                xerr_right=eb_data["xerr_right"],
                capsize=eb_data.get("gle_capsize", eb_data.get("capsize")),
                yaxis=eb_data.get("yaxis", "y"),
                offset=eb_data.get("offset", 0.0),
                column_names=eb_data.get("column_names"),
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
            ax.lines + ax.scatters + ax.bars + ax.errorbars + ax.file_series
        )
        labels_present = any(series.get("label") for series in legend_sources)
        show_legend = ax.legend_on if ax.legend_on is not None else labels_present
        if show_legend:
            writer.add_legend(ax.legend_pos)
        elif labels_present:
            # GLE draws an implicit key from per-dataset key "label" tokens;
            # it must be switched off explicitly.
            writer.add_key_off()

    def _synchronize_x_limits(self):
        """Synchronize x-axis limits across all axes when sharex is enabled."""
        # Find global x-axis limits
        xmin_global = None
        xmax_global = None

        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.xmin is None or ax.xmax is None:
                data_xmin, data_xmax = self._get_data_xlim(ax)
                if ax.xmin is None:
                    ax.xmin = data_xmin
                if ax.xmax is None:
                    ax.xmax = data_xmax

            # Track global limits
            if ax.xmin is not None:
                if xmin_global is None or ax.xmin < xmin_global:
                    xmin_global = ax.xmin
            if ax.xmax is not None:
                if xmax_global is None or ax.xmax > xmax_global:
                    xmax_global = ax.xmax

        # Apply global limits to all axes
        for ax in self.axes_list:
            ax.xmin = xmin_global
            ax.xmax = xmax_global

    def _synchronize_y_limits(self):
        """Synchronize y-axis limits across all axes when sharey is enabled."""
        # Find global y-axis limits
        ymin_global = None
        ymax_global = None

        for ax in self.axes_list:
            # Calculate data limits if not explicitly set
            if ax.ymin is None or ax.ymax is None:
                data_ymin, data_ymax = self._get_data_ylim(ax)
                if ax.ymin is None:
                    ax.ymin = data_ymin
                if ax.ymax is None:
                    ax.ymax = data_ymax

            # Track global limits
            if ax.ymin is not None:
                if ymin_global is None or ax.ymin < ymin_global:
                    ymin_global = ax.ymin
            if ax.ymax is not None:
                if ymax_global is None or ax.ymax > ymax_global:
                    ymax_global = ax.ymax

        # Apply global limits to all axes
        for ax in self.axes_list:
            ax.ymin = ymin_global
            ax.ymax = ymax_global

    def _get_data_xlim(self, ax: Axes) -> Tuple[Optional[float], Optional[float]]:
        """Calculate x-axis limits from data."""
        xmin, xmax = None, None

        for data_list in [ax.lines, ax.scatters, ax.bars, ax.errorbars]:
            for data in data_list:
                x = np.asarray(data["x"])
                if len(x) > 0:
                    if xmin is None or x.min() < xmin:
                        xmin = float(x.min())
                    if xmax is None or x.max() > xmax:
                        xmax = float(x.max())

        for fill_data in ax.fills:
            x = np.asarray(fill_data["x"])
            if len(x) > 0:
                if xmin is None or x.min() < xmin:
                    xmin = float(x.min())
                if xmax is None or x.max() > xmax:
                    xmax = float(x.max())

        return xmin, xmax

    def _get_data_ylim(self, ax: Axes) -> Tuple[Optional[float], Optional[float]]:
        """Calculate y-axis limits from data."""
        ymin, ymax = None, None

        # A series' ``offset`` shifts its trace vertically at plot time (the .dat
        # values stay raw), so autoscale must add it back when bounding the data
        # -- otherwise a waterfall stack falls off the auto-computed axis.
        for data_list in [ax.lines, ax.scatters]:
            for data in data_list:
                y = np.asarray(data["y"]) + data.get("offset", 0.0)
                if len(y) > 0:
                    if ymin is None or y.min() < ymin:
                        ymin = float(y.min())
                    if ymax is None or y.max() > ymax:
                        ymax = float(y.max())

        for bar_data in ax.bars:
            height = np.asarray(bar_data["height"])
            if len(height) > 0:
                if ymin is None or height.min() < ymin:
                    ymin = float(min(0, height.min()))
                if ymax is None or height.max() > ymax:
                    ymax = float(height.max())

        for fill_data in ax.fills:
            off = fill_data.get("offset", 0.0)
            y1 = np.asarray(fill_data["y1"]) + off
            y2 = np.asarray(fill_data["y2"]) + off
            all_y = np.concatenate([y1, y2])
            if len(all_y) > 0:
                if ymin is None or all_y.min() < ymin:
                    ymin = float(all_y.min())
                if ymax is None or all_y.max() > ymax:
                    ymax = float(all_y.max())

        for eb_data in ax.errorbars:
            y = np.asarray(eb_data["y"]) + eb_data.get("offset", 0.0)
            yerr_up = eb_data.get("yerr_up")
            yerr_down = eb_data.get("yerr_down")

            if len(y) > 0:
                y_with_err = y.copy()
                if yerr_up is not None:
                    y_with_err_up = y + np.asarray(yerr_up)
                    if ymax is None or y_with_err_up.max() > ymax:
                        ymax = float(y_with_err_up.max())
                if yerr_down is not None:
                    y_with_err_down = y - np.asarray(yerr_down)
                    if ymin is None or y_with_err_down.min() < ymin:
                        ymin = float(y_with_err_down.min())

                if ymin is None or y.min() < ymin:
                    ymin = float(y.min())
                if ymax is None or y.max() > ymax:
                    ymax = float(y.max())

        return ymin, ymax

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
            "subplot_adjust": {k: float(v) for k, v in self._subplot_adjust.items()},
            "passthrough_header": list(self.passthrough_header),
            "passthrough_trailer": list(self.passthrough_trailer),
            "metadata_extra": dict(self.metadata_extra),
            "config": {
                "style": self.style.to_dict(),
                "graph": self.graph.to_dict(),
                "marker": self.marker_config.to_dict(),
            },
            "axes": [ax.to_dict() for ax in self.axes_list],
        }

        return {
            "format": PROJECT_FORMAT,
            "version": PROJECT_VERSION,
            "gleplot_version": __version__,
            "figure": figure_block,
        }

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
        if version != PROJECT_VERSION:
            raise ValueError(
                f"Unsupported project version {version!r}; this build supports "
                f"version {PROJECT_VERSION}"
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
            data_prefix=fig_block.get("data_prefix"),
        )

        fig._local_data_counter = fig_block.get("local_data_counter", 0)
        fig._used_data_files = set(fig_block.get("used_data_files", []))
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

        fig.axes_list = [
            Axes.from_dict(fig, ax_d) for ax_d in fig_block.get("axes", [])
        ]
        fig._current_axes = fig.axes_list[-1] if fig.axes_list else None

        return fig

    def close(self):
        """Close figure."""
        self.axes_list.clear()
        self._current_axes = None

"""Live preview engine for the gleplot GUI editor.

This module implements Track D of the editor: a debounced, asynchronous GLE
render pipeline and the view that displays its output. Track E2 extends it
with an optional SVG (vector) render path that falls back to PNG on failure.

:class:`PreviewController`
    Observes a :class:`~gleplot.gui.document.FigureDocument` and, whenever the
    figure changes, re-renders it using the GLE compiler -- entirely off the
    GUI thread via :class:`~PySide6.QtCore.QProcess`. It debounces rapid
    edits, coalesces overlapping renders so only the newest state is ever
    shown, and reports success/failure/empty via Qt signals. See
    :attr:`PreviewController.render_format` for the PNG/SVG switch.

:class:`PreviewView`
    A :class:`~PySide6.QtWidgets.QGraphicsView` that shows the rendered image
    (raster PNG or vector SVG) with wheel-zoom-around-cursor, drag panning,
    fit-to-window and 1:1 zoom, and a placeholder for empty/error states. It
    keeps the last good image on screen through transient compile errors.

Snapshot semantics
-------------------
gleplot's GLE generation mutates unset axis limits on the figure in place (see
``Figure._generate_gle_with_files``). Rendering from the *live* figure would
therefore silently freeze auto-computed limits and couple the preview to edit
order. To stay side-effect-free, every render works from an immediately-taken
``to_dict()`` snapshot rebuilt via ``Figure.from_dict()``; the live document
figure is never passed to GLE.

Empty state
-----------
An empty figure *does* compile in GLE (it produces a blank axes frame), but
rendering nothing wastes a ~200ms GLE round-trip and shows an empty frame that
reads as a bug. So when the document has no figure, no axes, or no axes with
any series, the controller skips the render and emits
:data:`PreviewController.render_skipped_empty` instead of invoking GLE.

SVG rendering and fallback (Track E2)
--------------------------------------
GLE's Cairo-based SVG backend (``gle -d svg``) refuses to draw any PostScript
font (``>> Error: PostScript fonts not supported with '-cairo'``) but still
exits ``0`` and still writes a structurally valid (if incomplete -- missing
text, and any calibration ``print`` line placed after the affected graph block
never executes) SVG file. Since gleplot's default
:class:`~gleplot.config.GLEStyleConfig` emits no ``set font`` line at all,
GLE's own built-in default resolves to a PostScript font, so *every* SVG
render would hit this unless prevented. The controller therefore injects
``set font texcmr`` (a TeX/Cairo-safe font) into the SVG-mode copy of the
script whenever the user's own figure does not already set a font -- this is
pure preview-script surgery, exactly like the existing calibration
``print``-line injection, and never touches ``writer.py`` or a user's saved
file. If the user's *own* configured font is not Cairo-safe (or any other
SVG-only failure occurs), :meth:`PreviewController._on_process_finished`
detects it (exit code + parsed ``GLEError`` + output-file validity, see
:meth:`PreviewController._svg_output_is_valid`) and the controller
permanently falls back to PNG for the rest of the session (see
:attr:`PreviewController.render_format` and :data:`PreviewController.
fallback_activated`), automatically re-rendering in PNG so the user sees
output without intervention.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

from PySide6.QtCore import (
    QObject,
    QProcess,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

try:
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtSvgWidgets import QGraphicsSvgItem

    _QTSVG_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the gui extra
    QSvgRenderer = None  # type: ignore[assignment, misc]
    QGraphicsSvgItem = None  # type: ignore[assignment, misc]
    _QTSVG_AVAILABLE = False

from gleplot.compiler import GLEError, find_gle, parse_gle_errors
from gleplot.figure import Figure
from gleplot.gui.document import FigureDocument
from gleplot.gui.geometry import CM_PER_INCH, PreviewGeometry, parse_calibration_lines
from gleplot.parser.syntax import GraphBlock, parse_gle_source
from gleplot.parser.units import inches_to_cm

_log = logging.getLogger(__name__)

#: Base name (without suffix) of the GLE script written into the session dir.
_SCRIPT_STEM = "preview"
#: Deterministic data-file prefix so generated ``.dat`` sidecars are stable
#: and referenced relatively from the script.
_DATA_PREFIX = "preview"

#: Points per centimetre (1 inch = 72pt = 2.54cm), the SVG viewBox is authored
#: in points regardless of preview DPI. See :class:`SvgViewMapping`.
_PT_PER_CM = 72.0 / CM_PER_INCH

#: GLE's Cairo SVG backend pads the page by exactly 1pt on every side (see
#: module docstring "SVG rendering and fallback"; empirically derived from
#: comparing ``gle -d svg`` output's ``viewBox`` to the requested page size).
_SVG_MARGIN_PT = 1.0

#: Cairo/TeX font forced into the SVG-mode script when the figure does not
#: already set one, so GLE's own PostScript-font default never triggers
#: ``>> Error: PostScript fonts not supported with '-cairo'``.
_SVG_SAFE_FONT = "texcmr"

#: Matches a top-level ``set font ...`` line so we never override an explicit
#: user choice (see module docstring).
_SET_FONT_RE = re.compile(r"^\s*set\s+font\b", re.IGNORECASE)
_SIZE_LINE_RE = re.compile(r"^\s*size\s+[-+0-9.]+\s+[-+0-9.]+\s*$", re.IGNORECASE)

#: Matches a genuine GLE diagnostic location line, e.g.
#: ``>> foo.gle (10) |end graph|`` -- the same anchor
#: :func:`gleplot.compiler.parse_gle_errors` uses to open an error block.
#: ``parse_gle_errors`` itself cannot be used as a general-purpose
#: "did-something-go-wrong" probe on an exit-0 compile: for *any* non-empty
#: text without such a block (e.g. the normal, harmless
#: ``GLE 4.3.3[foo.gle]-C-R-`` banner GLE always prints) it falls back to
#: wrapping the whole raw text as one synthetic :class:`GLEError`, which would
#: make every successful compile look like a failure. This narrower pattern
#: is what actually distinguishes a real diagnostic block from the banner.
_GLE_DIAGNOSTIC_RE = re.compile(r"^>>\s*.+?\s*\(\d+\)\s*\|.*\|\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# view_mapping() contract (frozen -- consumed by the annotation overlay, F1)
# --------------------------------------------------------------------------- #
class ViewMapping(Protocol):
    """``cm <-> view`` mapping for whatever is currently displayed.

    This is the frozen contract between the preview track and the annotation
    overlay track: :meth:`PreviewView.view_mapping` returns an object
    satisfying this protocol (or ``None`` when nothing is displayed), and the
    overlay uses it -- together with the per-axes calibration from
    ``PreviewController.geometry_ready`` -- to place/read back handles:

        cal = geometry.axes[i]
        cx, cy = cal.data_to_cm(x, y)              # data -> page cm
        mapping = view.view_mapping()
        vx, vy = mapping.cm_to_view(cx, cy)         # page cm -> view/scene

    and the inverse when the user drops a handle at scene point ``(vx, vy)``::

        cx, cy = mapping.view_to_cm(vx, vy)
        # then geometry.axes_at_... equivalent / cal.cm_to_data(cx, cy)

    ``(vx, vy)`` are in the :class:`PreviewView` scene's coordinate system --
    i.e. exactly the coordinates the displayed :class:`QGraphicsPixmapItem` /
    :class:`QGraphicsSvgItem` itself is drawn in, *before* any view zoom/pan
    transform (those are view-level, not scene-level, so overlay items placed
    in the scene track zoom/pan automatically like the image does). This is
    the same space :class:`~gleplot.gui.geometry.PreviewGeometry.cm_to_px`
    already used for the raster case; the SVG case reuses the identical shape
    with a different renderer-specific scale (see :class:`SvgViewMapping`).
    """

    def cm_to_view(self, cx: float, cy: float) -> tuple:
        """Map page-cm ``(cx, cy)`` to scene/view coordinates."""
        ...

    def view_to_cm(self, vx: float, vy: float) -> tuple:
        """Inverse of :meth:`cm_to_view`."""
        ...

    def fingerprint(self) -> tuple:
        """A hashable identity of this mapping's concrete class + scale params.

        The annotation overlay captures a mapping's fingerprint when an
        interaction (drag/edit) starts and compares it on each rebuild. A
        change means the ``cm <-> scene`` relationship shifted underneath an
        in-flight gesture -- e.g. a PNG<->SVG format switch, or a DPI change --
        so decoding the stale scene position with the new mapping would
        silently corrupt the committed coordinates. The overlay aborts the
        interaction (reverting to the model position) when the fingerprint
        changes rather than preserving the stale scene position. Two mappings
        that decode a scene point identically compare equal.
        """
        ...


@dataclass
class RasterViewMapping:
    """:class:`ViewMapping` for a displayed raster (PNG) image.

    Thin adapter around :class:`~gleplot.gui.geometry.PreviewGeometry`'s
    existing ``cm <-> px`` methods -- the raster pixmap item is drawn at the
    scene origin at 1 scene-unit-per-pixel, so pixel coordinates and scene
    coordinates coincide.
    """

    geometry: PreviewGeometry

    def cm_to_view(self, cx: float, cy: float):
        return self.geometry.cm_to_px(cx, cy)

    def view_to_cm(self, vx: float, vy: float):
        return self.geometry.px_to_cm(vx, vy)

    def fingerprint(self) -> tuple:
        """Identity for the raster ``cm <-> px`` mapping.

        The raster mapping is fully determined by the render DPI and the page
        height in cm (the only inputs to :meth:`PreviewGeometry.cm_to_px` /
        ``px_to_cm``). A change in either shifts the scene<->cm relationship,
        so both go into the fingerprint. Page width does not affect the
        mapping, so it is deliberately omitted.
        """
        return ("raster", self.geometry.dpi, self.geometry.page_size_cm[1])


@dataclass
class SvgViewMapping:
    """:class:`ViewMapping` for a displayed vector (SVG) image.

    GLE's Cairo SVG backend authors page content directly in page-cm-derived
    units, transformed once into the SVG viewBox (point units, y-down from
    the top-left) via a single affine transform empirically confirmed to be::

        svg_x =  k * cx + margin
        svg_y = -k * cy + (viewbox_height_pt - margin)

    where ``k = 72 / 2.54`` (points per cm) and ``margin = 1pt`` (GLE's fixed
    page padding in this backend). ``QGraphicsSvgItem`` places its content in
    exactly these viewBox units in the scene (its ``boundingRect()`` ==
    ``renderer().defaultSize()`` == the viewBox size), so this mapping's
    output is directly usable as a scene coordinate -- no extra scale step
    beyond what :class:`RasterViewMapping` needs for the raster case.

    Unlike :class:`RasterViewMapping`, this mapping is independent of preview
    DPI (SVG has no raster resolution) and is derived purely from the page
    size in cm, which is why it is constructed directly from
    ``page_size_cm`` rather than from a full :class:`PreviewGeometry`.
    """

    page_size_cm: tuple

    def cm_to_view(self, cx: float, cy: float):
        viewbox_h = self.page_size_cm[1] * _PT_PER_CM + 2 * _SVG_MARGIN_PT
        vx = _PT_PER_CM * cx + _SVG_MARGIN_PT
        vy = -_PT_PER_CM * cy + (viewbox_h - _SVG_MARGIN_PT)
        return vx, vy

    def view_to_cm(self, vx: float, vy: float):
        viewbox_h = self.page_size_cm[1] * _PT_PER_CM + 2 * _SVG_MARGIN_PT
        cx = (vx - _SVG_MARGIN_PT) / _PT_PER_CM
        cy = ((viewbox_h - _SVG_MARGIN_PT) - vy) / _PT_PER_CM
        return cx, cy

    def fingerprint(self) -> tuple:
        """Identity for the vector ``cm <-> svg-unit`` mapping.

        The SVG mapping is DPI-independent and fully determined by the page
        size in cm (both dimensions feed the viewBox transform). The leading
        tag differs from :meth:`RasterViewMapping.fingerprint` so a PNG<->SVG
        format switch always registers as a change even in the unlikely event
        the numeric params coincide.
        """
        return ("svg", self.page_size_cm[0], self.page_size_cm[1])


class PreviewController(QObject):
    """Debounced, asynchronous GLE render engine driven by a document.

    Parameters
    ----------
    document : FigureDocument
        The document to observe. The controller connects to its
        ``figure_changed`` and ``figure_replaced`` signals and schedules a
        render whenever either fires.
    parent : QObject, optional
        Qt parent.

    Signals
    -------
    render_started()
        A GLE process has just been launched.
    render_succeeded(str)
        A render finished; the argument is the path to the produced PNG.
    render_failed(list, str)
        A render failed. The first argument is a list of
        :class:`~gleplot.compiler.GLEError`; the second is the raw process
        output.
    render_skipped_empty()
        The document has nothing renderable (no figure / no series); no GLE
        process was launched.
    geometry_ready(object)
        Emitted on a *successful* render with the :class:`PreviewGeometry`
        derived from the GLE calibration output, or with ``None`` when
        calibration could not be parsed. **Always emitted before**
        ``render_succeeded`` on a successful render so an overlay can install
        the geometry and then react to the new image in one turn. On parse
        failure the geometry is ``None`` (annotations overlay disables itself)
        but ``render_succeeded`` still fires -- calibration never blocks a
        render.
    fallback_activated(str)
        Emitted exactly once per session, the first time an SVG render fails
        for an SVG-specific reason (compile error unique to ``-d svg``,
        invalid/empty SVG output, or ``QtSvg`` unavailable). The argument is a
        short human-readable reason. After this fires, :attr:`render_format`
        is permanently ``'png'`` for the rest of the controller's life (the
        setter is a no-op for ``'svg'`` from then on) and a PNG re-render of
        the current state is launched automatically so the user sees output
        without touching anything.

    Notes
    -----
    Call :meth:`shutdown` (or ``deleteLater``) when done to kill any running
    process and remove the session temp directory.

    The calibration ``print`` lines are injected only into the preview's temp
    copy of the script (see :meth:`_write_script`); user-facing saves go through
    the untouched public figure API and never contain ``gleplot-cal``.
    """

    render_started = Signal()
    render_succeeded = Signal(str)
    render_failed = Signal(list, str)
    render_skipped_empty = Signal()
    geometry_ready = Signal(object)
    fallback_activated = Signal(str)

    #: Default debounce interval in milliseconds.
    DEFAULT_DEBOUNCE_MS = 300
    #: Watchdog timeout in milliseconds; a render exceeding this is killed.
    WATCHDOG_MS = 15000

    def __init__(
        self,
        document: FigureDocument,
        parent: Optional[QObject] = None,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._gle_path = find_gle()
        self._preview_dpi = 150

        # Render format: 'svg' by default only when QtSvg imported successfully
        # AND a one-time session probe (a trivial compile) confirms GLE's
        # ``-d svg`` actually produces a loadable SVG in this environment;
        # otherwise 'png'. See _probe_svg_support(). ``_svg_fallback_reason``
        # is set (once, permanently) the first time an SVG-specific failure is
        # detected, and pins the format to 'png' from then on.
        self._svg_fallback_reason: Optional[str] = None
        self._render_format = "png"
        if _QTSVG_AVAILABLE and self._gle_path and self._probe_svg_support():
            self._render_format = "svg"

        # Session scratch directory for scripts, data files, and PNGs. Created
        # lazily on first render so constructing a controller is cheap.
        self._session_dir: Optional[Path] = None

        # Render bookkeeping. ``_requested_seq`` is bumped every time a render
        # is *requested*; ``_running_seq`` records the sequence of the render
        # currently executing. A finished process whose sequence is older than
        # the latest request is discarded. ``_pending`` records that a newer
        # change landed mid-render so we immediately re-render on completion.
        self._requested_seq = 0
        self._running_seq = 0
        self._pending = False
        self._process: Optional[QProcess] = None
        self._current_output: Optional[Path] = None

        # Calibration geometry from the most recent successful render, or None
        # if calibration could not be parsed. Consumed by the annotation
        # overlay via the ``geometry_ready`` signal.
        self.last_geometry: Optional[PreviewGeometry] = None
        # Per-render calibration inputs captured at launch (from the snapshot,
        # not the live figure): the page size in cm and the per-axes log flags,
        # both needed to build a PreviewGeometry when the process finishes.
        self._cal_page_size_cm: Optional[tuple] = None
        self._cal_axes_meta: list = []
        # The format ('svg'/'png') the *currently running* (or just-finished)
        # process was launched with -- captured at launch time so a mid-flight
        # render_format change (or a fallback triggered by this very render)
        # never confuses which validation path _on_process_finished takes.
        self._running_format = "png"

        # Debounce timer: collapses a burst of change signals into one render.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(debounce_ms)
        self._debounce.timeout.connect(self._start_render)

        # Watchdog: kills a wedged GLE process.
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(self.WATCHDOG_MS)
        self._watchdog.timeout.connect(self._on_watchdog_timeout)

        document.figure_changed.connect(self._on_document_changed)
        document.figure_replaced.connect(self._on_document_changed)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def preview_dpi(self) -> int:
        """Render resolution in DPI. Setting it triggers a re-render."""
        return self._preview_dpi

    @preview_dpi.setter
    def preview_dpi(self, value: int) -> None:
        value = int(value)
        if value != self._preview_dpi:
            self._preview_dpi = value
            self._on_document_changed()

    @property
    def debounce_ms(self) -> int:
        """Current debounce interval in milliseconds."""
        return self._debounce.interval()

    @debounce_ms.setter
    def debounce_ms(self, value: int) -> None:
        self._debounce.setInterval(int(value))

    @property
    def render_format(self) -> str:
        """Current render format: ``'svg'`` (vector) or ``'png'`` (raster).

        Defaults to ``'svg'`` when ``QtSvg`` imported successfully *and* a
        one-time session probe confirmed GLE's ``-d svg`` output loads, else
        ``'png'``. Once :data:`fallback_activated` has fired, this is
        permanently pinned to ``'png'`` -- the setter silently ignores any
        attempt to set ``'svg'`` again for the rest of the session (see
        :attr:`svg_available`).
        """
        return self._render_format

    @render_format.setter
    def render_format(self, value: str) -> None:
        value = str(value).lower()
        if value not in ("svg", "png"):
            raise ValueError(f"render_format must be 'svg' or 'png', got {value!r}")
        if value == "svg" and self._svg_fallback_reason is not None:
            # Sticky fallback: never re-enable SVG once it has failed.
            return
        if value == "svg" and not _QTSVG_AVAILABLE:
            return
        if value != self._render_format:
            self._render_format = value
            self._on_document_changed()

    @property
    def svg_available(self) -> bool:
        """Whether SVG can currently be selected as :attr:`render_format`.

        ``False`` when ``QtSvg`` failed to import or a fallback has already
        been triggered this session (permanently). Used by the main window to
        disable/grey out the "Vector preview (SVG)" toggle with an explanatory
        tooltip.
        """
        return _QTSVG_AVAILABLE and self._svg_fallback_reason is None

    # ------------------------------------------------------------------
    # Change handling / scheduling
    # ------------------------------------------------------------------
    def _on_document_changed(self) -> None:
        """Handle a document change: (re)start the debounce timer."""
        self._debounce.start()

    def request_render(self) -> None:
        """Request a render immediately, bypassing the debounce timer."""
        self._debounce.stop()
        self._start_render()

    def set_gle_path(self, path: Optional[str]) -> None:
        """Update the GLE executable used to render previews.

        The controller caches :func:`~gleplot.compiler.find_gle` at
        construction time (locating GLE once is enough for the common case), so
        when the user changes the configured GLE binary via **Tools ▸ GLE
        Setup…** the main window calls this to refresh the cached path.
        ``path`` is normally the freshly re-resolved :func:`find_gle` result
        (``None`` if GLE is no longer locatable, which ``_launch`` handles by
        surfacing a structured "GLE not found" error).
        """
        self._gle_path = path

    def _start_render(self) -> None:
        """Snapshot the document and launch a render, or coalesce/skip it."""
        snap = self._empty_check_and_snapshot()
        if snap is None:
            # Nothing renderable. If a render is in flight, let it finish
            # (its result would show a stale image, but the emptiness will be
            # re-evaluated only on the next change); otherwise report empty.
            if self._process is None:
                self.render_skipped_empty.emit()
            return

        # A newer request always wins. Bump the requested sequence so that any
        # in-flight render finishing later is recognised as stale.
        self._requested_seq += 1

        if self._process is not None:
            # A render is already running; mark pending so we immediately
            # kick off a fresh render (from the newest state) on completion.
            self._pending = True
            return

        self._launch(snap)

    def _empty_check_and_snapshot(self) -> Optional[dict]:
        """Return a figure snapshot dict, or ``None`` if nothing to render.

        The snapshot is taken *before* any GLE generation so the live figure's
        unset axis limits are never mutated (see module docstring).
        """
        fig = self._document.figure
        if fig is None or not fig.axes_list:
            return None
        if not any(ax.has_plots() for ax in fig.axes_list):
            return None
        return fig.to_dict()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _ensure_session_dir(self) -> Path:
        if self._session_dir is None:
            self._session_dir = Path(tempfile.mkdtemp(prefix="gleplot_preview_"))
        return self._session_dir

    def _launch(self, snap: dict) -> None:
        """Write the GLE script + data files and start a GLE QProcess."""
        if not self._gle_path:
            # No GLE available: surface a structured error rather than hanging.
            err = GLEError(
                file=None, line=None, column=None,
                message="GLE executable not found; cannot render preview.",
            )
            self.render_failed.emit([err], "GLE not found")
            return

        seq = self._requested_seq
        self._running_seq = seq
        fmt = self._render_format
        self._running_format = fmt
        session = self._ensure_session_dir()

        try:
            work_fig = Figure.from_dict(snap)
            # Reference-mode series carry paths relative to the .gle's
            # directory; the preview compiles in a temp session dir, so
            # they must be absolutized or GLE cannot find them.
            project_path = getattr(self._document, "project_path", None)
            if project_path:
                work_fig.absolutize_file_references(Path(project_path).parent)
            self._write_script(work_fig, session, fmt)
            # Capture calibration inputs from the *snapshot* work figure (never
            # the live document): page size in cm and per-axes log flags, in
            # axes_list == graph-block order. Used to build the geometry when
            # the process finishes.
            self._cal_page_size_cm = (
                inches_to_cm(work_fig.figsize[0]),
                inches_to_cm(work_fig.figsize[1]),
            )
            self._cal_axes_meta = [
                (
                    getattr(ax, "xscale", "linear") == "log",
                    getattr(ax, "yscale", "linear") == "log",
                )
                for ax in work_fig.axes_list
            ]
        except Exception as exc:  # noqa: BLE001 - report, never crash the GUI
            err = GLEError(
                file=None, line=None, column=None,
                message=f"Failed to generate GLE script: {exc}",
            )
            self.render_failed.emit([err], str(exc))
            return

        output_name = f"render_{seq}.{fmt}"
        self._current_output = session / output_name

        proc = QProcess(self)
        proc.setWorkingDirectory(str(session))
        # Keep stdout and stderr separate: GLE 4.3.3 emits the ``gleplot-cal``
        # calibration records on *stderr* while errors and diagnostics can land
        # on either stream. We read and concatenate both on finish so
        # calibration parsing sees the records regardless of stream, and error
        # parsing sees everything it did under the old merged mode.
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.finished.connect(self._on_process_finished)
        proc.errorOccurred.connect(self._on_process_error)
        self._process = proc

        args = [
            "-d", fmt,
            "-r", str(self._preview_dpi),
            "-o", output_name,
            f"{_SCRIPT_STEM}.gle",
        ]
        self._watchdog.start()
        self.render_started.emit()
        proc.start(self._gle_path, args)

    def _write_script(self, work_fig: Figure, session: Path, fmt: str = "png") -> None:
        """Write the GLE script and its data sidecars into ``session``.

        Uses ``Figure.savefig_gle`` (the public GLE-export API), which emits
        the ``.gle`` script plus one ``<prefix>_N.dat`` per generated series
        into the target directory. We force a deterministic ``data_prefix`` on
        the work figure so the sidecar names are stable and the script
        references them relatively; combined with ``workingDirectory`` set to
        the session dir, GLE resolves the data files without absolute paths.

        This is deliberately a separate method: the preview integration test
        monkeypatches it to inject a malformed GLE line so that
        :data:`render_failed` (with parsed line numbers) can be exercised
        without a broken public figure API.
        """
        work_fig.data_prefix = _DATA_PREFIX
        # Reset naming state so repeated renders reuse the same sidecar names
        # instead of accumulating collision-avoidance suffixes.
        work_fig._local_data_counter = 0
        work_fig._used_data_files = set()
        script_path = session / f"{_SCRIPT_STEM}.gle"
        work_fig.savefig_gle(str(script_path))
        # Post-process the preview-only copy to inject one calibration ``print``
        # per graph block so GLE emits its axis ranges + box corners at compile
        # time. This touches only the temp script -- writer.py is untouched and
        # user saves never see these lines.
        self._inject_calibration(script_path)
        if fmt == "svg":
            # GLE's Cairo SVG backend rejects PostScript fonts (see module
            # docstring "SVG rendering and fallback"). gleplot emits no
            # ``set font`` line by default, so GLE's own built-in default
            # would otherwise always trigger the error. Force a Cairo-safe
            # font -- but only if the figure/script did not already request
            # one explicitly, so a user's own font choice is never overridden
            # (if that choice is itself PostScript-only, the normal
            # SVG-validation/fallback path below handles it).
            self._inject_svg_font(script_path)

    @staticmethod
    def _inject_svg_font(script_path: Path) -> None:
        """Insert ``set font texcmr`` after the ``size`` line, if needed.

        No-op if the script already contains a ``set font`` line (an explicit
        user choice always wins). See the module docstring "SVG rendering and
        fallback" for why this is necessary at all.
        """
        text = script_path.read_text(encoding="utf-8")
        newline = "\r\n" if "\r\n" in text else "\n"
        raw_lines = text.split(newline)

        if any(_SET_FONT_RE.match(line) for line in raw_lines):
            return  # explicit user font already present; do not override

        for idx, line in enumerate(raw_lines):
            if _SIZE_LINE_RE.match(line):
                raw_lines.insert(idx + 1, f"set font {_SVG_SAFE_FONT}")
                script_path.write_text(newline.join(raw_lines), encoding="utf-8")
                return
        # No ``size`` line found (should not happen for a gleplot-generated
        # script): leave the script untouched rather than guess where to
        # insert -- the SVG validation/fallback path will catch any resulting
        # failure downstream.

    @staticmethod
    def _inject_calibration(script_path: Path) -> None:
        """Insert a ``gleplot-cal`` ``print`` after each graph block.

        Uses :func:`gleplot.parser.syntax.parse_gle_source` to locate every
        top-level :class:`GraphBlock`'s ``end graph`` statement and inserts, on
        the line *immediately after* it (i.e. after any deferred graph-text
        lines GLE emits post-``end graph`` -- those are separate statements, and
        we anchor on the ``end`` statement's own line), the exact empirically
        proven print form::

            print "gleplot-cal {i} " xgmin " " xgmax " " ygmin " " ygmax " "
                  xg(xgmin) " " yg(ygmin) " " xg(xgmax) " " yg(ygmax)

        ``xgmin``/``xg()``/``yg()`` in GLE refer to the most recent graph block,
        so anchoring right after each block's ``end`` is correct. ``{i}`` is the
        block order, which matches ``axes_list`` order (figure.py emits one
        graph block per axes in list order).

        Insertions are done bottom-up (highest line number first) so earlier
        line numbers stay valid as we splice.
        """
        text = script_path.read_text(encoding="utf-8")
        doc = parse_gle_source(text)
        graphs = [n for n in doc.nodes if isinstance(n, GraphBlock)]

        # Map end-graph line number -> block order. Skip any unclosed block
        # (end is None): without an ``end graph`` there is nothing to anchor to,
        # and its calibration will simply be reported missing downstream.
        anchors = {
            g.end.line_no: i
            for i, g in enumerate(graphs)
            if g.end is not None
        }
        if not anchors:
            return

        # Detect the dominant line ending so the injected lines match.
        newline = "\r\n" if "\r\n" in text else "\n"
        raw_lines = text.split(newline)

        # Insert bottom-up so indices below remain valid. ``raw_lines`` is
        # 0-based; ``line_no`` is 1-based, so the end-graph line is at index
        # ``line_no - 1`` and we insert immediately after it.
        for line_no in sorted(anchors, reverse=True):
            i = anchors[line_no]
            print_line = (
                f'print "gleplot-cal {i} " xgmin " " xgmax " " ygmin " " '
                f'ygmax " " xg(xgmin) " " yg(ygmin) " " xg(xgmax) " " yg(ygmax)'
            )
            raw_lines.insert(line_no, print_line)

        script_path.write_text(newline.join(raw_lines), encoding="utf-8")

    def _build_geometry(self, raw: str) -> Optional[PreviewGeometry]:
        """Parse calibration records from ``raw`` into a :class:`PreviewGeometry`.

        Returns ``None`` (never raises) when the page size / axes metadata was
        not captured or when no calibration record could be parsed, so a
        parse failure disables the overlay rather than blocking the render.
        """
        if self._cal_page_size_cm is None:
            return None
        calibrations, _warnings = parse_calibration_lines(
            raw, self._cal_axes_meta
        )
        if not calibrations:
            return None
        return PreviewGeometry(
            page_size_cm=self._cal_page_size_cm,
            dpi=self._preview_dpi,
            axes=calibrations,
        )

    @staticmethod
    def _svg_output_problem(output: Path, raw: str) -> Optional[str]:
        """Return a reason string if ``output`` is not a usable SVG render.

        Checks, in order: ``QtSvg`` availability, that the file loads as a
        valid SVG with a non-empty ``defaultSize()`` (catches truncated/
        corrupt output), and that the output contains a genuine GLE
        diagnostic block (catches the exit-0-but-degraded case: GLE's
        PostScript-font-on-Cairo error, or any other SVG-only compile error,
        exits 0 and still writes a structurally valid SVG missing the
        affected graph's content -- see module docstring). The check is
        :data:`_GLE_DIAGNOSTIC_RE` directly, *not*
        :func:`gleplot.compiler.parse_gle_errors` -- that function is a
        fallback-wrap parser meant to be called only once GLE is already
        known to have failed; on the harmless startup banner GLE always
        prints (even on a clean compile) it would wrap the whole banner as a
        synthetic error and make every successful render look failed.
        Returns ``None`` when the output is good.
        """
        if not _QTSVG_AVAILABLE:
            return "QtSvg is not available"
        try:
            renderer = QSvgRenderer(str(output))
        except Exception as exc:  # noqa: BLE001 - never crash the GUI
            return f"SVG failed to load: {exc}"
        if not renderer.isValid():
            return "SVG output is not a valid SVG document"
        size = renderer.defaultSize()
        if size.isEmpty():
            return "SVG output has an empty bounding size"
        if _GLE_DIAGNOSTIC_RE.search(raw):
            errors = parse_gle_errors(raw)
            message = errors[0].message if errors else raw.strip()
            return f"GLE reported an error during SVG compile: {message}"
        return None

    def _probe_svg_support(self) -> bool:
        """One-time session check that ``gle -d svg`` produces a loadable SVG.

        Compiles a minimal known-good script (an axes box, the same
        Cairo-safe font forced for all SVG renders) in a throwaway temp
        directory. Never raises; any exception or a failed/invalid probe
        result means SVG is not available and the controller starts in
        ``'png'`` mode instead. Runs synchronously (a bare ``gle`` invocation
        on a trivial script is a small fraction of a second) so the format
        decision is stable and available immediately in ``__init__`` --
        the render pipeline itself remains fully async for real renders.
        """
        probe_dir = None
        try:
            probe_dir = Path(tempfile.mkdtemp(prefix="gleplot_svgprobe_"))
            script = probe_dir / "probe.gle"
            script.write_text(
                "size 5 5\n"
                f"set font {_SVG_SAFE_FONT}\n"
                "begin graph\n"
                "   size 3 3\n"
                "   xaxis min 0 max 1\n"
                "   yaxis min 0 max 1\n"
                "end graph\n",
                encoding="utf-8",
            )
            output = probe_dir / "probe.svg"
            result = subprocess.run(
                [self._gle_path, "-d", "svg", "-o", str(output), str(script)],
                cwd=str(probe_dir),
                capture_output=True,
                timeout=10,
                text=True,
            )
            if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
                return False
            raw = (result.stdout or "") + (result.stderr or "")
            problem = self._svg_output_problem(output, raw)
            return problem is None
        except Exception:  # noqa: BLE001 - probe failure just disables SVG
            return False
        finally:
            if probe_dir is not None:
                shutil.rmtree(probe_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Process callbacks
    # ------------------------------------------------------------------
    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        self._watchdog.stop()
        proc = self._process
        self._process = None
        output = self._current_output

        raw = ""
        if proc is not None:
            stdout = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
            stderr = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
            # Concatenate both streams: error parsing wants everything (as it
            # did under the old merged mode) and calibration records live on
            # stderr for this GLE build.
            raw = stdout + stderr
            proc.deleteLater()

        finished_seq = self._running_seq
        stale = finished_seq < self._requested_seq

        # If newer state is pending (or this result is stale), start the next
        # render from the latest snapshot regardless of this one's outcome.
        restart_needed = self._pending or stale
        self._pending = False

        if not stale:
            ok = (
                exit_code == 0
                and output is not None
                and output.exists()
                and output.stat().st_size > 0
            )
            # For an SVG render, exit==0 and a non-empty file are *necessary
            # but not sufficient*: GLE's Cairo backend can exit 0 and write a
            # structurally valid-but-incomplete SVG on a PostScript-font error
            # (see module docstring). Validate the file actually loads in
            # QSvgRenderer with a non-empty size before treating it as success.
            svg_problem: Optional[str] = None
            if ok and self._running_format == "svg":
                svg_problem = self._svg_output_problem(output, raw)
                if svg_problem is not None:
                    ok = False

            if ok:
                # Build calibration geometry from the compile output and emit
                # it BEFORE render_succeeded so an overlay installs geometry in
                # the same turn it learns of the new image. Never blocks the
                # render: any parse failure -> last_geometry = None,
                # geometry_ready(None), but render_succeeded still fires.
                self.last_geometry = self._build_geometry(raw)
                self.geometry_ready.emit(self.last_geometry)
                self.render_succeeded.emit(str(output))
            elif self._running_format == "svg" and svg_problem is not None:
                # SVG-specific failure: permanently fall back to PNG and
                # re-render automatically (never surfaced as a render_failed
                # -- from the user's perspective this is a silent, automatic
                # substitution, not a compile error).
                self.last_geometry = None
                self._activate_svg_fallback(svg_problem)
                restart_needed = True
            else:
                # A failed render has no valid geometry; drop any stale one so
                # an overlay does not keep drawing against an outdated page.
                self.last_geometry = None
                errors = parse_gle_errors(raw)
                if not errors:
                    errors = [GLEError(
                        file=None, line=None, column=None,
                        message="GLE render failed (no output produced).",
                    )]
                self.render_failed.emit(errors, raw)

        if restart_needed:
            snap = self._empty_check_and_snapshot()
            if snap is not None:
                self._launch(snap)
            elif self._process is None:
                self.render_skipped_empty.emit()

    def _activate_svg_fallback(self, reason: str) -> None:
        """Permanently pin :attr:`render_format` to ``'png'`` and notify.

        Idempotent: only the *first* call in a session logs/emits (mirrors
        "log once" from the task brief); later SVG-side problems, if any,
        are silently absorbed by the resulting ``'png'`` renders since
        :attr:`render_format` setter is a no-op for ``'svg'`` from here on.
        """
        if self._svg_fallback_reason is not None:
            return
        self._svg_fallback_reason = reason
        self._render_format = "png"
        _log.warning("SVG preview disabled for this session: %s", reason)
        self.fallback_activated.emit(reason)

    def _on_process_error(self, error) -> None:
        # A start/crash error; ``finished`` may or may not follow. If the
        # process failed to start there will be no ``finished`` signal, so
        # handle cleanup here when the process is genuinely gone.
        if error == QProcess.ProcessError.FailedToStart:
            self._watchdog.stop()
            proc = self._process
            self._process = None
            if proc is not None:
                proc.deleteLater()
            err = GLEError(
                file=None, line=None, column=None,
                message="GLE process failed to start.",
            )
            self.render_failed.emit([err], "FailedToStart")

    def _on_watchdog_timeout(self) -> None:
        """Kill a render that exceeded the watchdog timeout."""
        proc = self._process
        if proc is None:
            return
        # Disconnect finished so kill() doesn't drive the normal path; report
        # a synthetic timeout error here instead.
        try:
            proc.finished.disconnect(self._on_process_finished)
        except (RuntimeError, TypeError):
            pass
        proc.kill()
        proc.waitForFinished(2000)
        proc.deleteLater()
        self._process = None

        err = GLEError(
            file=None, line=None, column=None,
            message=f"GLE render timed out after {self.WATCHDOG_MS // 1000}s and was killed.",
        )
        self.render_failed.emit([err], "watchdog timeout")

        if self._pending or self._running_seq < self._requested_seq:
            self._pending = False
            snap = self._empty_check_and_snapshot()
            if snap is not None:
                self._launch(snap)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Kill any running render and remove the session temp directory."""
        self._debounce.stop()
        self._watchdog.stop()
        if self._process is not None:
            try:
                self._process.finished.disconnect(self._on_process_finished)
            except (RuntimeError, TypeError):
                pass
            self._process.kill()
            self._process.waitForFinished(2000)
            self._process.deleteLater()
            self._process = None
        if self._session_dir is not None and self._session_dir.exists():
            shutil.rmtree(self._session_dir, ignore_errors=True)
        self._session_dir = None

    def deleteLater(self) -> None:  # noqa: N802 - Qt override
        self.shutdown()
        super().deleteLater()


class PreviewView(QGraphicsView):
    """Zoomable/pannable view of the rendered preview image.

    Displays a single image item (raster ``QGraphicsPixmapItem`` or vector
    ``QGraphicsSvgItem``, whichever the controller last rendered) in a
    :class:`QGraphicsScene`. Supports wheel-zoom around the cursor, drag
    panning, fit-to-window, and 1:1 zoom. Through transient compile errors the
    last successfully rendered image stays visible; :meth:`show_placeholder`
    is only used when there is nothing to show.

    :meth:`view_mapping` exposes the frozen ``cm <-> view`` contract (see
    :class:`ViewMapping`) the annotation overlay track consumes together with
    ``PreviewController.geometry_ready``.
    """

    #: Zoom scale clamps (absolute scene->view scale).
    MIN_SCALE = 0.1
    MAX_SCALE = 10.0
    _ZOOM_STEP = 1.15

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._svg_item = None  # Optional[QGraphicsSvgItem]
        self._placeholder_item = None
        self._last_good_path: Optional[str] = None
        self._last_image_size = None
        self._has_shown_image = False

        # Mapping state captured at show_image() time, consumed by
        # view_mapping(). For 'svg' this is derived purely from the page size
        # in cm (see SvgViewMapping); for 'png' it needs a full
        # PreviewGeometry (dpi + page size), installed separately via
        # set_geometry() since PreviewController emits geometry_ready
        # independently of render_succeeded/show_image.
        self._current_format: Optional[str] = None
        self._geometry: Optional[PreviewGeometry] = None

        # Annotation-overlay coordination (Track F1). The overlay sets
        # ``annotations_enabled`` for status/UI, and suspends drag-panning
        # while the cursor is over an annotation item so item dragging is not
        # swallowed by ScrollHandDrag panning (the two fight -- see
        # suspend_pan()). ``_pan_mode`` remembers the drag mode to restore.
        self._annotations_enabled = False
        self._pan_mode = QGraphicsView.DragMode.ScrollHandDrag
        self._pan_suspended = False

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def last_good_path(self) -> Optional[str]:
        """Path of the most recently shown image, or ``None``."""
        return self._last_good_path

    @property
    def annotations_enabled(self) -> bool:
        """Whether the annotation overlay is active over this view.

        Driven by :class:`~gleplot.gui.annotations.AnnotationOverlay` (it sets
        this from its ``overlay_enabled_changed`` signal). Purely informational
        for the view/UI; the overlay owns the items and their behaviour.
        """
        return self._annotations_enabled

    @annotations_enabled.setter
    def annotations_enabled(self, value: bool) -> None:
        self._annotations_enabled = bool(value)

    def suspend_pan(self, suspend: bool) -> None:
        """Suspend (or restore) drag-panning so item dragging isn't swallowed.

        In :attr:`QGraphicsView.DragMode.ScrollHandDrag` the viewport grabs a
        left-drag for panning *before* it ever reaches a movable
        :class:`~gleplot.gui.annotations.AnnotationItem`, so the two fight and
        the item never moves. The overlay calls ``suspend_pan(True)`` while the
        cursor is over an annotation item (on hover-enter) and
        ``suspend_pan(False)`` on hover-leave, temporarily switching the view to
        :attr:`~QGraphicsView.DragMode.NoDrag` so the item receives the drag.
        The previous mode is captured once and restored on un-suspend, so this
        composes with any future drag-mode changes.
        """
        if suspend:
            if not self._pan_suspended:
                self._pan_mode = self.dragMode()
                self._pan_suspended = True
                super().setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            if self._pan_suspended:
                self._pan_suspended = False
                super().setDragMode(self._pan_mode)

    def setDragMode(self, mode) -> None:  # noqa: N802 - Qt override
        """Track the pan drag-mode so :meth:`suspend_pan` restores it correctly."""
        if self._pan_suspended:
            # Remember the requested mode; it becomes active on un-suspend.
            self._pan_mode = mode
            return
        self._pan_mode = mode
        super().setDragMode(mode)

    def set_geometry(self, geometry: Optional[PreviewGeometry]) -> None:
        """Install the calibration geometry for the *raster* mapping.

        Connect this to ``PreviewController.geometry_ready``. Only consumed
        when the currently displayed image is a PNG -- an SVG's mapping needs
        only the page size (captured directly from the SVG file at
        :meth:`show_image` time), never this geometry. Safe to call with
        ``None`` (e.g. on a failed render); :meth:`view_mapping` simply
        returns ``None`` for the raster case until a valid geometry arrives.
        """
        self._geometry = geometry

    def view_mapping(self) -> Optional[ViewMapping]:
        """Return the ``cm <-> view`` mapping for the currently shown image.

        Returns ``None`` when nothing is displayed, or (for the raster case
        only) when no :class:`PreviewGeometry` has been installed yet via
        :meth:`set_geometry`. See :class:`ViewMapping` for the frozen
        contract the annotation overlay consumes.
        """
        if self._current_format == "svg" and self._last_image_size is not None:
            # page size in cm is recovered from the viewBox captured at
            # show_image() time -- independent of dpi, unlike the raster case.
            width_pt, height_pt = self._last_image_size
            page_w_cm = (width_pt - 2 * _SVG_MARGIN_PT) / _PT_PER_CM
            page_h_cm = (height_pt - 2 * _SVG_MARGIN_PT) / _PT_PER_CM
            return SvgViewMapping(page_size_cm=(page_w_cm, page_h_cm))
        if self._current_format == "png" and self._geometry is not None:
            return RasterViewMapping(geometry=self._geometry)
        return None

    def show_image(self, path: str) -> None:
        """Display the image at ``path`` (``.png`` or ``.svg``).

        Zoom and center are preserved when the new image has the same
        size/viewBox as the previous one (the common live-preview case: a
        re-render of the same figure geometry). On the first image, after a
        new figure is installed (:meth:`reset_view`), or when the format
        switches between raster and vector, the image is fit into the view.
        """
        is_svg = str(path).lower().endswith(".svg")
        if is_svg:
            self._show_svg(path)
        else:
            self._show_pixmap(path)

    def _show_pixmap(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            # Corrupt/partial file: keep whatever is currently shown.
            return

        self._clear_placeholder()
        new_size = (pixmap.width(), pixmap.height())
        format_changed = self._current_format != "png"
        same_size = (not format_changed) and new_size == self._last_image_size

        self._clear_svg_item()
        if self._pixmap_item is None:
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._pixmap_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation
            )
            self._scene.addItem(self._pixmap_item)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._current_format = "png"
        self._last_image_size = new_size
        self._last_good_path = path

        if not self._has_shown_image or not same_size:
            self._has_shown_image = True
            self.fit_to_window()

    def _show_svg(self, path: str) -> None:
        if not _QTSVG_AVAILABLE:
            # Should never be reached: the controller falls back to PNG
            # before emitting an .svg path when QtSvg is unavailable. Guard
            # anyway so a stray call degrades to a no-op, not a crash.
            return
        renderer = QSvgRenderer(path)
        if not renderer.isValid() or renderer.defaultSize().isEmpty():
            # Corrupt/partial file: keep whatever is currently shown.
            return

        self._clear_placeholder()
        size = renderer.defaultSize()
        new_size = (size.width(), size.height())
        format_changed = self._current_format != "svg"
        same_size = (not format_changed) and new_size == self._last_image_size

        self._clear_pixmap_item()
        if self._svg_item is None:
            self._svg_item = QGraphicsSvgItem(path)
            self._scene.addItem(self._svg_item)
        else:
            self._svg_item.setSharedRenderer(renderer)

        self._scene.setSceneRect(self._svg_item.boundingRect())
        self._current_format = "svg"
        self._last_image_size = new_size
        self._last_good_path = path

        if not self._has_shown_image or not same_size:
            self._has_shown_image = True
            self.fit_to_window()

    def show_placeholder(self, text: str) -> None:
        """Show ``text`` centered, only when no image is available.

        If an image is currently displayed (e.g. a transient compile error),
        this is a no-op so the last good render stays on screen.
        """
        if self._pixmap_item is not None or self._svg_item is not None:
            return
        if self._placeholder_item is None:
            self._placeholder_item = self._scene.addText(text)
            self._placeholder_item.setDefaultTextColor(Qt.GlobalColor.gray)
        else:
            self._placeholder_item.setPlainText(text)
        self._scene.setSceneRect(self._placeholder_item.boundingRect())
        # Never fitInView on the text: before the window is first shown the
        # viewport is tiny, which would bake in a microscopic scale. Show the
        # placeholder at its natural size instead.
        self.resetTransform()
        self.centerOn(self._placeholder_item)

    def reset_view(self) -> None:
        """Forget saved zoom/size so the next image is fit-to-window.

        The main window connects this to ``FigureDocument.figure_replaced`` so
        a freshly opened figure starts framed rather than inheriting the
        previous figure's zoom.
        """
        self._has_shown_image = False
        self._last_image_size = None

    def clear_image(self) -> None:
        """Remove the current image (e.g. when the document goes empty)."""
        self._clear_pixmap_item()
        self._clear_svg_item()
        self._current_format = None
        self._last_image_size = None
        self._has_shown_image = False

    # ------------------------------------------------------------------
    # Zoom / pan slots
    # ------------------------------------------------------------------
    def fit_to_window(self) -> None:
        """Scale the scene so the whole image fits in the viewport."""
        if self._scene.sceneRect().isEmpty():
            return
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_actual_size(self) -> None:
        """Reset zoom to 1:1 (one image pixel/point per view pixel)."""
        self.resetTransform()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._pixmap_item is None and self._svg_item is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self._ZOOM_STEP if delta > 0 else 1.0 / self._ZOOM_STEP
        self._apply_zoom(factor)

    def _apply_zoom(self, factor: float) -> None:
        current = self.transform().m11()
        target = current * factor
        if target < self.MIN_SCALE:
            factor = self.MIN_SCALE / current
        elif target > self.MAX_SCALE:
            factor = self.MAX_SCALE / current
        if abs(factor - 1.0) < 1e-9:
            return
        self.scale(factor, factor)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _clear_pixmap_item(self) -> None:
        if self._pixmap_item is not None:
            self._scene.removeItem(self._pixmap_item)
            self._pixmap_item = None

    def _clear_svg_item(self) -> None:
        if self._svg_item is not None:
            self._scene.removeItem(self._svg_item)
            self._svg_item = None

    def _clear_placeholder(self) -> None:
        if self._placeholder_item is not None:
            self._scene.removeItem(self._placeholder_item)
            self._placeholder_item = None

"""Live preview engine for the gleplot GUI editor.

This module implements Track D of the editor: a debounced, asynchronous GLE
render pipeline and the view that displays its output.

:class:`PreviewController`
    Observes a :class:`~gleplot.gui.document.FigureDocument` and, whenever the
    figure changes, re-renders it to a PNG using the GLE compiler -- entirely
    off the GUI thread via :class:`~PySide6.QtCore.QProcess`. It debounces
    rapid edits, coalesces overlapping renders so only the newest state is
    ever shown, and reports success/failure/empty via Qt signals.

:class:`PreviewView`
    A :class:`~PySide6.QtWidgets.QGraphicsView` that shows the rendered PNG
    with wheel-zoom-around-cursor, drag panning, fit-to-window and 1:1 zoom,
    and a placeholder for empty/error states. It keeps the last good image on
    screen through transient compile errors.

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
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

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

from gleplot.compiler import GLEError, find_gle, parse_gle_errors
from gleplot.figure import Figure
from gleplot.gui.document import FigureDocument

#: Base name (without suffix) of the GLE script written into the session dir.
_SCRIPT_STEM = "preview"
#: Deterministic data-file prefix so generated ``.dat`` sidecars are stable
#: and referenced relatively from the script.
_DATA_PREFIX = "preview"


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

    Notes
    -----
    Call :meth:`shutdown` (or ``deleteLater``) when done to kill any running
    process and remove the session temp directory.
    """

    render_started = Signal()
    render_succeeded = Signal(str)
    render_failed = Signal(list, str)
    render_skipped_empty = Signal()

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
        session = self._ensure_session_dir()

        try:
            work_fig = Figure.from_dict(snap)
            # Reference-mode series carry paths relative to the .gle's
            # directory; the preview compiles in a temp session dir, so
            # they must be absolutized or GLE cannot find them.
            project_path = getattr(self._document, "project_path", None)
            if project_path:
                work_fig.absolutize_file_references(Path(project_path).parent)
            self._write_script(work_fig, session)
        except Exception as exc:  # noqa: BLE001 - report, never crash the GUI
            err = GLEError(
                file=None, line=None, column=None,
                message=f"Failed to generate GLE script: {exc}",
            )
            self.render_failed.emit([err], str(exc))
            return

        output_name = f"render_{seq}.png"
        self._current_output = session / output_name

        proc = QProcess(self)
        proc.setWorkingDirectory(str(session))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.finished.connect(self._on_process_finished)
        proc.errorOccurred.connect(self._on_process_error)
        self._process = proc

        args = [
            "-d", "png",
            "-r", str(self._preview_dpi),
            "-o", output_name,
            f"{_SCRIPT_STEM}.gle",
        ]
        self._watchdog.start()
        self.render_started.emit()
        proc.start(self._gle_path, args)

    def _write_script(self, work_fig: Figure, session: Path) -> None:
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
        work_fig.savefig_gle(str(session / f"{_SCRIPT_STEM}.gle"))

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
            raw = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
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
            if ok:
                self.render_succeeded.emit(str(output))
            else:
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
    """Zoomable/pannable view of the rendered preview PNG.

    Displays a single pixmap in a :class:`QGraphicsScene`. Supports
    wheel-zoom around the cursor, drag panning, fit-to-window, and 1:1 zoom.
    Through transient compile errors the last successfully rendered image
    stays visible; :meth:`show_placeholder` is only used when there is nothing
    to show.
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
        self._placeholder_item = None
        self._last_good_path: Optional[str] = None
        self._last_image_size = None
        self._has_shown_image = False

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

    def show_image(self, path: str) -> None:
        """Display the image at ``path``.

        Zoom and center are preserved when the new image has the same pixel
        size as the previous one (the common live-preview case: re-render of
        the same figure geometry). On the first image, or after a new figure
        is installed (:meth:`reset_view`), the image is fit into the view.
        """
        pixmap = QPixmap(path)
        if pixmap.isNull():
            # Corrupt/partial file: keep whatever is currently shown.
            return

        self._clear_placeholder()
        new_size = (pixmap.width(), pixmap.height())
        same_size = new_size == self._last_image_size

        if self._pixmap_item is None:
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._pixmap_item.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation
            )
            self._scene.addItem(self._pixmap_item)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._scene.setSceneRect(QRectF(pixmap.rect()))
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
        if self._pixmap_item is not None:
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
        if self._pixmap_item is not None:
            self._scene.removeItem(self._pixmap_item)
            self._pixmap_item = None
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
        """Reset zoom to 1:1 (one image pixel per view pixel)."""
        self.resetTransform()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._pixmap_item is None:
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
    def _clear_placeholder(self) -> None:
        if self._placeholder_item is not None:
            self._scene.removeItem(self._placeholder_item)
            self._placeholder_item = None

"""Interactive text-annotation overlay for the live preview (Track F1).

This module implements the marquee editor feature: dragging, editing, adding
and deleting the free-form text annotations (``Axes.text`` entries) directly on
the rendered preview image, in *data* coordinates, with the model as the single
source of truth.

Coordinate pipeline (frozen contracts)
--------------------------------------
Every annotation lives in the DATA coordinates of its owning axes. To place a
hit-target on the raster we chain the two frozen mappings:

    data (axis units)
        --  AxesCalibration.data_to_cm  -->  page cm
        --  ViewMapping.cm_to_view      -->  scene coordinates

and the inverse on drop::

    scene
        --  ViewMapping.view_to_cm      -->  page cm
        --  AxesCalibration.cm_to_data  -->  data

The per-axes :class:`~gleplot.gui.geometry.AxesCalibration` arrives via
``PreviewController.geometry_ready`` (a :class:`~gleplot.gui.geometry.PreviewGeometry`
or ``None``); the ``cm <-> scene`` :class:`~gleplot.gui.preview.ViewMapping`
comes from ``PreviewView.view_mapping()`` and MUST be refetched after every
render (it is invalidated by ``show_image``/``set_geometry``; see the preview
module contract). Overlay items are placed in the *scene* so view zoom/pan
transforms carry them along with the image automatically -- we never apply a
view transform ourselves.

Why the overlay must not "double draw"
--------------------------------------
The rendered PNG/SVG already contains the baked text pixels. The overlay items
are therefore *transparent* hit-rectangles with only a selection outline; the
annotation's glyphs are drawn by GLE, not by us. The one exception is transient
UI: while dragging we show a semi-transparent "ghost" of the text (because the
baked pixels stay at the OLD position until the debounced re-render lands), and
while editing we show an editable text child.

The no-jump sequencing problem
------------------------------
A drag ends by writing new data coords into the model and calling
``document.notify_changed()``. That schedules a debounced (~300ms) re-render;
when it lands, ``geometry_ready`` + ``render_succeeded`` fire and the overlay
*rebuilds* every item against the fresh image -- which now has the text at the
new position. Between the drop and that rebuild there is a window where the
baked image still shows the OLD position. To avoid a visible "snap back", the
dragged item keeps its ghost visible at the drop location until the rebuild
replaces it. On rebuild the fresh render already has the glyphs in the right
place, so the ghost is simply dropped.

Mid-render drags: if the user starts another drag *during* that render window,
the rebuild must not teleport the item they are actively holding. The overlay
therefore skips rebuilding any item that is currently being dragged or edited
(:attr:`AnnotationItem.is_interacting`) and re-syncs it on the next clean
rebuild.

Cross-axes drags (Phase-later)
------------------------------
Dropping an annotation inside a *different* axes' box does NOT re-home it to
that axes in this phase: the annotation stays owned by its original axes and
its new data coords are computed via that axes' transform even when the drop is
outside the box (GLE renders text outside the graph frame fine). Re-homing
between axes is deferred.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
)

from gleplot.gui.geometry import CM_PER_INCH, AxesCalibration, PreviewGeometry

__all__ = ["AnnotationItem", "AnnotationOverlay"]

#: Points per centimetre (72pt per inch). Used to translate a font's point
#: size into the cm-then-scene scale so a hit-rect roughly matches the baked
#: glyph height on the page.
_PT_PER_CM = 72.0 / CM_PER_INCH

#: Default GLE text height in points when an annotation has ``fontsize is None``
#: (GLE's own default is ~10pt for gleplot's style; the hit-rect only needs to
#: be a plausible click target, so an approximate default is fine).
_DEFAULT_FONTSIZE_PT = 10.0

#: Fractional padding added around the estimated text bounds so the click
#: target is generous (the estimate is deliberately not pixel-perfect).
_HIT_PAD_FRAC = 0.30

#: Selection outline pen colour/appearance.
_SELECT_COLOR = QColor(30, 120, 220)
#: Ghost text colour while dragging (semi-transparent).
_GHOST_ALPHA = 150


class AnnotationItem(QGraphicsRectItem):
    """One draggable/editable hit-rect for a single ``Axes.text`` dict.

    The item is a transparent rectangle approximating the rendered glyphs'
    bounds in scene coordinates. It carries a reference to *the very dict* in
    ``axes.texts`` it represents (identity, not a copy) plus its owning
    :class:`~gleplot.gui.geometry.AxesCalibration`, so a drop can write new
    coords straight back into the model.

    States
    ------
    normal
        Invisible fill, no outline; ``OpenHand`` cursor on hover.
    selected
        Dashed selection outline (still no fill).
    dragging
        A semi-transparent :class:`QGraphicsSimpleTextItem` ghost child shows
        the text at the cursor position (the baked pixels are stale until the
        next render).
    editing
        A :class:`QGraphicsTextItem` child with ``TextEditorInteraction``,
        pre-filled with the current text; commit on focus-out/Enter, cancel on
        Escape.
    """

    def __init__(
        self,
        overlay: "AnnotationOverlay",
        text_dict: dict,
        cal: AxesCalibration,
    ) -> None:
        super().__init__()
        self._overlay = overlay
        self.text_dict = text_dict
        self.cal = cal

        self._ghost: Optional[QGraphicsSimpleTextItem] = None
        self._editor: Optional[QGraphicsTextItem] = None
        self._dragging = False
        self._editing = False
        # Guards itemChange during programmatic setPos in sync_position().
        self._syncing = False
        # Guards itemChange during programmatic setSelected() in
        # sync_selection(), so the overlay's own select_annotation() doesn't
        # loop back into selection_changed (mirrors TextsPanel's _updating).
        self._selecting = False

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True
        )
        # Transparent fill; outline only appears when selected. The rect is
        # local (origin at item pos); we position the item via setPos.
        self.setBrush(Qt.GlobalColor.transparent)
        self.setPen(QPen(Qt.GlobalColor.transparent))
        # Draw above the image but let the ghost/editor children sit on top.
        self.setZValue(10)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------
    @property
    def is_interacting(self) -> bool:
        """True while the user is actively dragging or editing this item.

        The overlay skips rebuilding interacting items so a re-render landing
        mid-gesture never teleports the handle out from under the cursor.
        """
        return self._dragging or self._editing

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    def _effective_fontsize_pt(self) -> float:
        fs = self.text_dict.get("fontsize")
        try:
            return float(fs) if fs is not None else _DEFAULT_FONTSIZE_PT
        except (TypeError, ValueError):
            return _DEFAULT_FONTSIZE_PT

    def rebuild_rect(self, cm_per_scene_unit: float) -> None:
        """Recompute the local hit-rect from the text/font and cm->scene scale.

        ``cm_per_scene_unit`` is the number of page-cm one scene unit spans
        (measured by the overlay from the active :class:`ViewMapping`). The
        font's point size -> cm -> scene units gives the glyph height in scene
        units; :class:`QFontMetricsF` gives the text width for that height.
        Horizontal-alignment offset (``ha``) shifts the rect so the item's
        *position* (set by :meth:`sync_position`) always denotes the annotation
        anchor point, matching GLE's ``amove xg()/yg()`` anchor.

        Vertical: GLE's writer emits no vertical ``just`` for annotations, so
        the baked text sits with its baseline at the anchor. We centre the rect
        vertically on the anchor as a pragmatic approximation (documented in the
        module docstring); the generous padding absorbs the mismatch for click
        targeting.
        """
        if cm_per_scene_unit <= 0.0:
            return
        # scene units per cm is the inverse; glyph height in cm then scene.
        scene_per_cm = 1.0 / cm_per_scene_unit
        height_cm = self._effective_fontsize_pt() / _PT_PER_CM
        height_scene = height_cm * scene_per_cm
        if height_scene <= 0.0:
            height_scene = 1.0

        text = str(self.text_dict.get("text", ""))
        font = QFont()
        # setPointSizeF drives QFontMetricsF; we then scale metrics from the
        # font's own pixel height to our target scene height so width tracks
        # the string length at the correct aspect.
        font.setPointSizeF(max(self._effective_fontsize_pt(), 1.0))
        fm = QFontMetricsF(font)
        raw_h = fm.height() if fm.height() > 0 else 1.0
        raw_w = fm.horizontalAdvance(text) if text else raw_h * 0.6
        scale = height_scene / raw_h
        w = max(raw_w * scale, height_scene * 0.4)
        h = height_scene

        pad_w = w * _HIT_PAD_FRAC
        pad_h = h * _HIT_PAD_FRAC

        ha = str(self.text_dict.get("ha", "left")).lower()
        # Anchor is at local (0,0); place the rect so the anchor matches ha.
        if ha == "center":
            x0 = -w / 2.0
        elif ha == "right":
            x0 = -w
        else:  # left (default)
            x0 = 0.0
        # Vertically centre the rect on the anchor.
        y0 = -h / 2.0
        self.setRect(
            QRectF(x0 - pad_w, y0 - pad_h, w + 2 * pad_w, h + 2 * pad_h)
        )

    def sync_position(self, scene_pos: QPointF) -> None:
        """Move the item to ``scene_pos`` without triggering a model write.

        Used by the overlay when rebuilding item positions from the model after
        a render. Guarded so the resulting ``itemChange`` is ignored.
        """
        self._syncing = True
        try:
            self.setPos(scene_pos)
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # Selection appearance / sync
    # ------------------------------------------------------------------
    def sync_selection(self, selected: bool) -> None:
        """Set selection state without notifying the overlay (no re-emit).

        Used by :meth:`AnnotationOverlay.select_annotation` so a
        panel-driven (or overlay-driven) programmatic selection doesn't loop
        back through :data:`AnnotationOverlay.selection_changed`. Mirrors
        :meth:`sync_position`'s ``_syncing`` guard discipline.
        """
        self._selecting = True
        try:
            self.setSelected(selected)
        finally:
            self._selecting = False

    def itemChange(self, change, value):  # noqa: N802 - Qt override
        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged
        ):
            self._update_selection_pen()
            if not self._selecting:
                self._overlay._on_item_selection_changed(self)
        return super().itemChange(change, value)

    def _update_selection_pen(self) -> None:
        if self.isSelected():
            pen = QPen(_SELECT_COLOR)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            pen.setWidthF(1.5)
            self.setPen(pen)
        else:
            self.setPen(QPen(Qt.GlobalColor.transparent))

    # ------------------------------------------------------------------
    # Hover cursor
    # ------------------------------------------------------------------
    def hoverEnterEvent(self, event):  # noqa: N802 - Qt override
        if not self._editing:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Suspend view panning so a left-drag reaches this item instead of
            # being grabbed by ScrollHandDrag (the two fight -- see
            # PreviewView.suspend_pan / the panning-vs-drag note).
            self._overlay.set_pan_suspended(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802 - Qt override
        self.unsetCursor()
        if not self._dragging:
            self._overlay.set_pan_suspended(False)
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if self._editing:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSelected(True)
            self._begin_drag()
        super().mousePressEvent(event)

    def _begin_drag(self) -> None:
        self._dragging = True
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._show_ghost()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        super().mouseReleaseEvent(event)
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._commit_drag()
            # The cursor may have left the (old) rect during the drag; if it is
            # no longer hovering, restore panning. isUnderMouse() is a good
            # enough proxy and errs toward restoring pan.
            if not self.isUnderMouse():
                self._overlay.set_pan_suspended(False)

    def _commit_drag(self) -> None:
        """Write the item's final scene position back to the model as data."""
        # Keep the ghost visible until the rebuild lands (no-jump): the baked
        # pixels still show the old position until the debounced re-render.
        self._overlay.commit_item_move(self)

    # ------------------------------------------------------------------
    # Inline edit
    # ------------------------------------------------------------------
    def mouseDoubleClickEvent(self, event):  # noqa: N802 - Qt override
        self.begin_edit()
        event.accept()

    def begin_edit(self) -> None:
        """Enter inline text-edit mode (pre-filled, editable)."""
        if self._editing:
            return
        self._editing = True
        self.setSelected(True)
        self._clear_ghost()
        editor = QGraphicsTextItem(self)
        editor.setPlainText(str(self.text_dict.get("text", "")))
        editor.setDefaultTextColor(_SELECT_COLOR)
        editor.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        # Position the editor at the anchor (item local origin).
        editor.setPos(0.0, -editor.boundingRect().height() / 2.0)
        editor.setZValue(20)
        editor.installSceneEventFilter(self)
        self._editor = editor
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        # Select-all so typing replaces the placeholder immediately.
        cursor = editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        editor.setTextCursor(cursor)

    def sceneEventFilter(self, watched, event):  # noqa: N802 - Qt override
        """Handle Enter (commit) / Escape (cancel) in the inline editor."""
        from PySide6.QtCore import QEvent

        if watched is self._editor and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.commit_edit()
                    return True
            elif key == Qt.Key.Key_Escape:
                self.cancel_edit()
                return True
        return super().sceneEventFilter(watched, event)

    def focusOutEvent(self, event):  # noqa: N802 - Qt override
        super().focusOutEvent(event)

    def commit_edit(self) -> None:
        """Commit the inline-edit buffer to the model (empty => delete)."""
        if not self._editing or self._editor is None:
            return
        new_text = self._editor.toPlainText()
        self._teardown_editor()
        self._overlay.commit_item_text(self, new_text)

    def cancel_edit(self) -> None:
        """Abandon the inline edit, leaving the model untouched."""
        if not self._editing:
            return
        self._teardown_editor()

    def _teardown_editor(self) -> None:
        self._editing = False
        if self._editor is not None:
            self._editor.removeSceneEventFilter(self)
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self._editor)
            self._editor = None

    # ------------------------------------------------------------------
    # Ghost (drag preview)
    # ------------------------------------------------------------------
    def _show_ghost(self) -> None:
        self._clear_ghost()
        text = str(self.text_dict.get("text", ""))
        if not text:
            return
        ghost = QGraphicsSimpleTextItem(text, self)
        color = QColor(_SELECT_COLOR)
        color.setAlpha(_GHOST_ALPHA)
        ghost.setBrush(color)
        # Scale the ghost font so its height ~ the hit-rect height.
        rect = self.rect()
        target_h = rect.height() / (1.0 + 2 * _HIT_PAD_FRAC)
        raw_h = ghost.boundingRect().height() or 1.0
        ghost.setScale(max(target_h / raw_h, 0.05))
        ghost.setPos(0.0, -ghost.boundingRect().height() * ghost.scale() / 2.0)
        ghost.setZValue(15)
        self._ghost = ghost

    def keep_ghost(self) -> None:
        """Ensure a drag ghost is showing (used to bridge the render window).

        No-op while editing: the inline editor owns the visual then, and a
        ghost underneath would double-draw.
        """
        if self._editing:
            return
        if self._dragging and self._ghost is None:
            self._show_ghost()

    def _clear_ghost(self) -> None:
        if self._ghost is not None:
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self._ghost)
            self._ghost = None

    def clear_transients(self) -> None:
        """Drop any ghost/editor children (called on teardown/rebuild)."""
        self._clear_ghost()
        self._teardown_editor()

    # ------------------------------------------------------------------
    # Delete key
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        if self._editing:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._overlay.delete_item(self)
            event.accept()
            return
        super().keyPressEvent(event)


class AnnotationOverlay(QObject):
    """Owns the annotation hit-items over the preview and syncs them to the model.

    Parameters
    ----------
    document : FigureDocument
        The shared document; mutations write into ``ax.texts`` dicts and call
        ``document.notify_changed()`` (one notify == one undo step).
    preview_view : PreviewView
        The view whose scene the overlay items live in; its ``view_mapping()``
        supplies the ``cm <-> scene`` transform.
    parent : QObject, optional
        Qt parent.

    Signals
    -------
    overlay_enabled_changed(bool)
        Emitted when the overlay transitions between enabled (valid geometry +
        mapping) and disabled (either is ``None``). The main window uses it to
        enable/disable the "Add text annotation" action and status hints.
    selection_changed(object)
        Emitted with the selected :class:`AnnotationItem`'s ``text_dict``
        (object identity) when the *user* changes the on-canvas selection, or
        ``None`` when the selection is cleared. NOT emitted for programmatic
        selection made via :meth:`select_annotation` -- mirrors
        ``TextsPanel.text_selected`` vs. ``TextsPanel.select_text``. This is
        the sync hook the main window uses to drive the Texts panel from
        canvas clicks (see :meth:`select_annotation` for the reverse
        direction).

    Wiring (done by the main window, kept explicit)
    -----------------------------------------------
    * ``PreviewController.geometry_ready`` -> :meth:`set_geometry`
    * ``PreviewController.render_succeeded`` -> :meth:`on_render_succeeded`
    """

    overlay_enabled_changed = Signal(bool)
    #: Emitted right after a click placed a new annotation (add-mode consumed).
    #: The main window uses it to clear the "Click to place" status hint.
    add_text_placed = Signal()
    #: Emitted with the selected item's ``text_dict`` (object identity) when
    #: the *user* changes the on-canvas selection (click/deselect via Qt's
    #: selection machinery). NOT emitted for programmatic selection made via
    #: :meth:`select_annotation` -- same discipline as
    #: ``TextsPanel.text_selected`` vs. ``TextsPanel.select_text``. Emits
    #: ``None`` when the selection is cleared.
    selection_changed = Signal(object)

    def __init__(self, document, preview_view, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._document = document
        self._view = preview_view
        self._geometry: Optional[PreviewGeometry] = None
        self._items: List[AnnotationItem] = []
        self._enabled = False

        # Add-text mode: while active, the next click on the preview places a
        # new annotation. Driven by begin_add_text()/cancel_add_text().
        self._add_mode = False

        # Pending inline-edit request: after adding a new annotation we want to
        # enter edit mode once the item exists post-rebuild. Matched by (dict)
        # identity captured at add time.
        self._pending_edit_dict: Optional[dict] = None

        # Remembers the selected annotation's dict (identity) so selection
        # survives a rebuild (items are recreated by rebuild(), so Qt's own
        # per-item isSelected() state doesn't carry over). Mirrors
        # _pending_edit_dict's "remember by identity, re-apply after rebuild"
        # pattern. None means "no selection".
        self._selected_dict: Optional[dict] = None

        # Install ourselves as a scene event filter so we can catch clicks on
        # empty scene area for add-text placement.
        scene = self._view.scene()
        if scene is not None:
            scene.installEventFilter(self)

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        """Whether the overlay currently has a usable geometry + mapping."""
        return self._enabled

    @property
    def items(self) -> List[AnnotationItem]:
        """The live annotation items (test/inspection helper)."""
        return list(self._items)

    @property
    def add_mode(self) -> bool:
        """Whether the overlay is waiting for a click to place a new text."""
        return self._add_mode

    # ------------------------------------------------------------------
    # Geometry / render wiring
    # ------------------------------------------------------------------
    def set_geometry(self, geometry: Optional[PreviewGeometry]) -> None:
        """Install calibration geometry (connect to ``geometry_ready``).

        ``None`` (parse failure / failed render) disables the overlay and
        clears all items. A valid geometry does not itself rebuild -- the paired
        ``render_succeeded`` does (so items land on the fresh image with a valid
        ``view_mapping``). Geometry arrives *before* ``render_succeeded`` per the
        controller contract, so storing it here is enough.
        """
        self._geometry = geometry
        if geometry is None:
            self._set_enabled(False)
            self._clear_items()
            self.cancel_add_text()

    def on_render_succeeded(self, _path: str = "") -> None:
        """Rebuild item positions against the freshly rendered image.

        Connect to ``PreviewController.render_succeeded``. Refetches
        ``view_mapping`` (never cached across renders) and reconciles items with
        the model's current ``texts`` lists. Skips any item the user is actively
        dragging/editing so a mid-gesture render never teleports it.
        """
        self.rebuild()

    # ------------------------------------------------------------------
    # Rebuild
    # ------------------------------------------------------------------
    def _mapping(self):
        """Refetch the active ``cm <-> scene`` mapping (never cached)."""
        return self._view.view_mapping()

    def _cm_per_scene_unit(self, mapping) -> float:
        """Measure page-cm spanned by one scene unit along x (uniform scale)."""
        c0 = mapping.view_to_cm(0.0, 0.0)
        c1 = mapping.view_to_cm(1.0, 0.0)
        return abs(c1[0] - c0[0])

    def rebuild(self) -> None:
        """Reconcile overlay items with the model's annotations + fresh render.

        The overlay is enabled iff both a geometry and a view mapping exist. On
        enable it (re)builds one :class:`AnnotationItem` per ``ax.texts`` dict,
        positioned at the annotation's data coords mapped through
        data->cm->scene. Items the user is actively interacting with are left
        in place (their model dict is not yet written for a drag, or is being
        edited); every other item is rebuilt from scratch so identity stays
        simple.
        """
        mapping = self._mapping()
        fig = self._document.figure
        if self._geometry is None or mapping is None or fig is None:
            self._set_enabled(False)
            self._clear_items()
            return

        cm_per_scene = self._cm_per_scene_unit(mapping)

        # Preserve items currently being interacted with (drag/edit); rebuild
        # everything else. Dropped ghosts from a just-committed drag are cleared
        # here because the fresh render now bakes the text at the new position.
        preserved = [it for it in self._items if it.is_interacting]
        for it in self._items:
            if it not in preserved:
                it.clear_transients()
                self._remove_item(it)

        self._items = list(preserved)

        # Map each preserved item's dict so we don't duplicate it below.
        preserved_dicts = {id(it.text_dict) for it in preserved}

        pending_edit_item: Optional[AnnotationItem] = None
        axes_list = list(getattr(fig, "axes_list", []) or [])
        for cal in self._geometry.axes:
            if cal.index >= len(axes_list):
                continue
            ax = axes_list[cal.index]
            for td in list(getattr(ax, "texts", []) or []):
                if id(td) in preserved_dicts:
                    continue
                item = self._make_item(td, cal, mapping, cm_per_scene)
                if item is None:
                    continue
                self._items.append(item)
                if self._pending_edit_dict is not None and td is self._pending_edit_dict:
                    pending_edit_item = item

        # Re-sync preserved (interacting) items' rects to the new scale but not
        # their position (the user owns it mid-gesture). Keep the drag ghost so
        # the baked-pixel lag until this render is not seen as a snap-back.
        for it in preserved:
            it.rebuild_rect(cm_per_scene)
            it.keep_ghost()

        self._set_enabled(True)

        # Re-apply the remembered selection (by dict identity) now that items
        # have been recreated: rebuilding replaces AnnotationItem instances, so
        # Qt's own isSelected() state is lost even though the *annotation*
        # itself is still logically selected. Uses the no-emit path so a
        # rebuild never re-fires selection_changed on its own.
        if self._selected_dict is not None:
            self._apply_selection(self._selected_dict, emit=False)

        # Fulfil a pending add-then-edit request now that the item exists.
        if pending_edit_item is not None:
            self._pending_edit_dict = None
            pending_edit_item.begin_edit()

    def _make_item(
        self, text_dict: dict, cal: AxesCalibration, mapping, cm_per_scene: float
    ) -> Optional[AnnotationItem]:
        try:
            cx, cy = cal.data_to_cm(float(text_dict["x"]), float(text_dict["y"]))
            vx, vy = mapping.cm_to_view(cx, cy)
        except (KeyError, TypeError, ValueError):
            return None
        item = AnnotationItem(self, text_dict, cal)
        scene = self._view.scene()
        if scene is None:
            return None
        scene.addItem(item)
        item.rebuild_rect(cm_per_scene)
        item.sync_position(QPointF(vx, vy))
        return item

    # ------------------------------------------------------------------
    # Model mutations (called by AnnotationItem)
    # ------------------------------------------------------------------
    def commit_item_move(self, item: AnnotationItem) -> None:
        """Write ``item``'s dropped scene position into its model dict as data.

        Cross-axes policy: the annotation keeps its ORIGINAL owning axes even
        when dropped outside that axes' box; coords are computed via that axes'
        transform regardless (see module docstring). Keeps the ghost visible so
        the baked-pixel lag until the next render is not seen as a snap-back.
        """
        mapping = self._mapping()
        if mapping is None:
            return
        scene_pos = item.pos()
        cx, cy = mapping.view_to_cm(scene_pos.x(), scene_pos.y())
        x, y = item.cal.cm_to_data(cx, cy)
        item.text_dict["x"] = float(x)
        item.text_dict["y"] = float(y)
        item.keep_ghost()
        self._document.notify_changed()

    def commit_item_text(self, item: AnnotationItem, new_text: str) -> None:
        """Commit an inline-edit result; empty text deletes the annotation."""
        stripped = new_text.strip()
        if stripped == "":
            self.delete_item(item)
            return
        if item.text_dict.get("text") == new_text:
            # No change: still rebuild to drop the editor child cleanly.
            item.clear_transients()
            self.rebuild()
            return
        item.text_dict["text"] = new_text
        self._document.notify_changed()

    def delete_item(self, item: AnnotationItem) -> None:
        """Remove ``item``'s dict from its axes' ``texts`` list + notify."""
        fig = self._document.figure
        removed = False
        if fig is not None:
            axes_list = list(getattr(fig, "axes_list", []) or [])
            if item.cal.index < len(axes_list):
                ax = axes_list[item.cal.index]
                texts = getattr(ax, "texts", None)
                if texts is not None and item.text_dict in texts:
                    texts.remove(item.text_dict)
                    removed = True
        item.clear_transients()
        self._remove_item(item)
        if item in self._items:
            self._items.remove(item)
        if self._selected_dict is item.text_dict:
            self._selected_dict = None
        if removed:
            self._document.notify_changed()

    # ------------------------------------------------------------------
    # Selection sync (F1 <-> TextsPanel contract)
    # ------------------------------------------------------------------
    def select_annotation(self, text_dict: Optional[dict]) -> None:
        """Programmatically select the item whose ``text_dict`` matches.

        Matched by object identity (the same dict as an ``ax.texts`` entry),
        mirroring how :class:`AnnotationItem` carries the dict. Deselects all
        other items. A no-op if no live item currently has that identity
        (e.g. the dict belongs to a different axes not currently rendered, or
        the overlay is disabled) -- except that the *remembered* selection is
        still updated so a subsequent rebuild (which may bring the matching
        item into existence) re-applies it.

        Does NOT emit :data:`selection_changed` -- same no-emit discipline as
        ``TextsPanel.select_text``, since this is meant to be called *in
        response to* an external selection (e.g. the Texts panel), not as a
        user action on the canvas itself. Passing ``None`` clears the
        selection.
        """
        self._apply_selection(text_dict, emit=False)

    def _apply_selection(self, text_dict: Optional[dict], *, emit: bool) -> None:
        """Shared implementation for programmatic and user-driven selection.

        Always updates ``_selected_dict`` (the identity remembered across
        rebuilds) and syncs every live item's Qt selection state via the
        no-emit ``sync_selection`` path (so this never re-enters
        :meth:`_on_item_selection_changed`), then optionally emits
        :data:`selection_changed` once for the caller.
        """
        self._selected_dict = text_dict
        for it in self._items:
            it.sync_selection(it.text_dict is text_dict)
        if emit:
            self.selection_changed.emit(text_dict)

    def _on_item_selection_changed(self, item: AnnotationItem) -> None:
        """Route a user-driven ``ItemSelectedHasChanged`` to the overlay.

        Called by :meth:`AnnotationItem.itemChange` (guarded there so
        programmatic ``sync_selection`` calls never reach here). Deselects
        any other item (single-selection discipline) and emits
        :data:`selection_changed` with the newly-selected dict, or ``None``
        if the item was deselected and nothing else is selected.
        """
        if item.isSelected():
            self._selected_dict = item.text_dict
            for other in self._items:
                if other is not item and other.isSelected():
                    other.sync_selection(False)
            self.selection_changed.emit(item.text_dict)
        else:
            if self._selected_dict is item.text_dict:
                self._selected_dict = None
                self.selection_changed.emit(None)

    # ------------------------------------------------------------------
    # Add-text mode
    # ------------------------------------------------------------------
    def begin_add_text(self) -> None:
        """Arm add-text mode: the next preview click places a new annotation."""
        if not self._enabled:
            return
        self._add_mode = True

    def cancel_add_text(self) -> None:
        """Disarm add-text mode (e.g. Esc)."""
        self._add_mode = False

    def _place_text_at(self, scene_pos: QPointF) -> bool:
        """Add a new annotation at ``scene_pos`` and request an inline edit.

        Picks the containing axes (by cm containment); if none contains the
        point, falls back to the nearest axes by cm-rect centre distance and
        the point is simply expressed in that axes' coords (documented
        fallback). Uses the public ``Axes.text`` API so the appended dict schema
        matches exactly. Returns True if an annotation was added.
        """
        mapping = self._mapping()
        fig = self._document.figure
        if not self._enabled or mapping is None or fig is None or self._geometry is None:
            return False

        cx, cy = mapping.view_to_cm(scene_pos.x(), scene_pos.y())
        cal = self._axes_for_cm(cx, cy)
        if cal is None:
            return False
        axes_list = list(getattr(fig, "axes_list", []) or [])
        if cal.index >= len(axes_list):
            return False
        ax = axes_list[cal.index]
        x, y = cal.cm_to_data(cx, cy)

        # Public API guarantees the exact dict schema; text() appends and
        # returns self, so the new dict is the last entry.
        ax.text(float(x), float(y), "text")
        new_dict = ax.texts[-1]
        self._pending_edit_dict = new_dict
        self.cancel_add_text()
        self._document.notify_changed()
        self.add_text_placed.emit()
        return True

    def _axes_for_cm(self, cx: float, cy: float) -> Optional[AxesCalibration]:
        """Containing axes by cm, else nearest by cm-rect centre distance."""
        if self._geometry is None or not self._geometry.axes:
            return None
        for cal in self._geometry.axes:
            if cal.contains_cm(cx, cy):
                return cal
        # Fallback: nearest axes centre (clamped placement, documented).
        best = None
        best_d = None
        for cal in self._geometry.axes:
            mx = (cal.cm_rect[0] + cal.cm_rect[2]) / 2.0
            my = (cal.cm_rect[1] + cal.cm_rect[3]) / 2.0
            d = (mx - cx) ** 2 + (my - cy) ** 2
            if best_d is None or d < best_d:
                best_d = d
                best = cal
        return best

    # ------------------------------------------------------------------
    # Scene event filter (add-text click capture)
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # noqa: N802 - Qt override
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent

        if (
            self._add_mode
            and event.type() == QEvent.Type.GraphicsSceneMousePress
            and isinstance(event, QGraphicsSceneMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if self._place_text_at(event.scenePos()):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def set_pan_suspended(self, suspend: bool) -> None:
        """Ask the view to suspend/restore drag-panning (item-drag support)."""
        suspend_pan = getattr(self._view, "suspend_pan", None)
        if callable(suspend_pan):
            suspend_pan(suspend)

    def _set_enabled(self, value: bool) -> None:
        if value != self._enabled:
            self._enabled = value
            # Keep the view's informational flag in sync for status/UI.
            try:
                self._view.annotations_enabled = value
            except AttributeError:
                pass
            self.overlay_enabled_changed.emit(value)
            if not value:
                self.cancel_add_text()

    def _remove_item(self, item: AnnotationItem) -> None:
        scene = self._view.scene()
        if scene is not None and item.scene() is scene:
            scene.removeItem(item)

    def _clear_items(self) -> None:
        for it in self._items:
            it.clear_transients()
            self._remove_item(it)
        self._items = []

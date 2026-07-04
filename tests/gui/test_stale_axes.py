"""Regression tests for FIX 3: stale axes references after undo/redo/Open.

After ``set_figure`` replaces the Figure (undo/redo/Open), the Axes/Series
panels must NOT keep editing the old figure's dead Axes. These tests wire the
real panels + document + undo stack the way ``MainWindow`` does and assert that
edits made after an undo land on ``document.figure``'s axes.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtWidgets import QApplication

from gleplot.figure import Figure
from gleplot.gui.document import FigureDocument
from gleplot.gui.panels import AxesPanel, LayoutPanel, SeriesPanel
from gleplot.gui.undo import UndoStack


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _wire(document):
    """Wire layout/axes/series panels + undo stack like MainWindow does."""
    layout = LayoutPanel(document)
    axes = AxesPanel(document)
    series = SeriesPanel(document)
    layout.axes_selected.connect(axes.set_axes)
    layout.axes_selected.connect(series.set_axes)
    undo = UndoStack(document)
    return layout, axes, series, undo


def _two_subplot_doc():
    """A 1x2 figure with a line on each subplot, wrapped in a document.

    Two subplots let the tests select a *non-default* slot so the panels'
    ``_axes`` override is genuinely populated with a real Axes (rather than
    left None, which would mask the stale-reference bug via the gca() fallback).
    """
    doc = FigureDocument()
    fig = Figure()
    a1 = fig.add_subplot(1, 2, 1)
    a1.plot([0, 1, 2], [0, 1, 4], label="s1", color="BLUE")
    a2 = fig.add_subplot(1, 2, 2)
    a2.plot([0, 1, 2], [4, 1, 0], label="s2", color="BLUE")
    doc.set_figure(fig)
    return doc, a1, a2


def test_axes_panel_edit_after_undo_lands_on_live_figure(qapp):
    doc, a1, a2 = _two_subplot_doc()
    layout, axes_panel, series_panel, undo = _wire(doc)
    layout.refresh()

    # Select slot 0 (a1) so the panels' _axes override points at a1.
    layout.slot_list.setCurrentRow(0)
    assert axes_panel._axes is a1

    # Two recorded title edits on a1 so we have something to undo.
    a1.set_title("first")
    doc.notify_changed()
    a1.set_title("second")
    doc.notify_changed()

    # Undo the "second" edit: set_figure installs a brand-new Figure object,
    # making a1 a dead object.
    assert undo.undo() is True
    assert a1 not in doc.figure.axes_list  # a1 is now dead

    # The panel must target a LIVE axes of the new figure, not dead a1. (The
    # exact slot depends on the restored figure's current-axes, which undo does
    # not serialize; the load-bearing invariant is "live, not dead".)
    target = axes_panel._current_axes()
    assert target in doc.figure.axes_list
    assert target is not a1

    # Edit the title via the panel write path.
    axes_panel.title_edit.setText("edited-after-undo")
    axes_panel._on_title_edited()

    # The edit must land on the LIVE figure (visible in to_dict), not the
    # dead a1 (which would be silently lost).
    d = doc.figure.to_dict()
    titles = [a.get("title_text") for a in d["figure"]["axes"]]
    assert "edited-after-undo" in titles
    assert target.title_text == "edited-after-undo"
    assert a1.title_text != "edited-after-undo"


def test_series_panel_edit_after_undo_lands_on_live_figure(qapp):
    doc, a1, a2 = _two_subplot_doc()
    layout, axes_panel, series_panel, undo = _wire(doc)
    layout.refresh()

    layout.slot_list.setCurrentRow(0)  # select a1
    assert series_panel._axes is a1

    # Two recorded color edits so we have something to undo.
    a1.lines[0]["color"] = "GREEN"
    doc.notify_changed()
    a1.lines[0]["color"] = "RED"
    doc.notify_changed()

    assert undo.undo() is True  # back to GREEN; a1 becomes dead
    assert a1 not in doc.figure.axes_list
    target = series_panel._current_axes()
    assert target in doc.figure.axes_list
    assert target is not a1

    # Edit color via the series-panel write path (mutate selected series dict).
    series_panel.series_list.setCurrentRow(0)
    sd = series_panel._selected_series_dict()
    assert sd is not None
    sd["color"] = "MAGENTA"
    doc.notify_changed()

    live_series = target.lines[0]
    assert live_series["color"] == "MAGENTA"
    # The dict the panel edited IS the live figure's series (not dead a1's).
    assert sd is live_series
    assert a1.lines[0]["color"] != "MAGENTA"


def test_layout_panel_reemits_axes_selected_on_figure_replaced(qapp):
    """LayoutPanel must re-emit axes_selected after figure_replaced even when
    the selected row index is unchanged, so downstream panels retarget."""
    doc = FigureDocument()
    fig = doc.new_figure()
    fig.gca().plot([0, 1, 2], [0, 1, 4], label="s")

    layout = LayoutPanel(doc)
    layout.refresh()

    received = []
    layout.axes_selected.connect(lambda ax: received.append(ax))

    # Replace with a same-shaped figure (single subplot, row index 0 unchanged).
    new_fig = FigureDocument().new_figure()
    new_fig.gca().plot([0, 1, 2], [4, 1, 0], label="t")
    doc.set_figure(new_fig)

    assert received, "axes_selected must fire on figure_replaced"
    assert received[-1] is doc.figure.gca()

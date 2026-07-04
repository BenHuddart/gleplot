"""Tests for RawGlePanel, the read-only viewer of preserved raw GLE content.

Track C2: content the recognizer (``gleplot.parser.recognizer``) could not
map onto the object model is preserved verbatim in three buckets --
``Figure.passthrough_header``, ``Axes.passthrough`` (per axes), and
``Figure.passthrough_trailer`` -- and re-emitted on save. These tests build
an *authentic* figure with content in all three buckets the same way
``tests/parser/test_recognizer.py::test_unknown_statements_in_all_bucket_positions``
does: a hand-written ``.gle`` with unrecognized lines in all three
positions, parsed with ``parse_gle_figure``.

Skips cleanly when PySide6 is not installed (same convention as
``test_panels.py``).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pyside6 = pytest.importorskip("PySide6", reason="PySide6 not installed (gui extra)")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

import gleplot
from gleplot.gui.panels import RawGlePanel
from gleplot.parser.recognizer import parse_gle_figure


# ----------------------------------------------------------------------
# Stub document (mirrors tests/gui/test_panels.py's StubDocument; Track D's
# real FigureDocument is not imported per the file-ownership rules).
# ----------------------------------------------------------------------
class StubDocument(QObject):
    figure_changed = Signal()
    figure_replaced = Signal()

    def __init__(self, figure=None):
        super().__init__()
        self._figure = figure
        self.notify_count = 0

    @property
    def figure(self):
        return self._figure

    def set_figure(self, figure):
        self._figure = figure
        self.figure_replaced.emit()

    def notify_changed(self):
        self.notify_count += 1
        self.figure_changed.emit()


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _write(tmp_path: Path, name: str, content: str, dats: dict | None = None) -> Path:
    for dat_name, dat_content in (dats or {}).items():
        (tmp_path / dat_name).write_text(dat_content, encoding="utf-8")
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


_SRC_ALL_BUCKETS = (
    "! GLE graphics file\n"
    "! hand note\n"
    "set weird_directive 7\n"           # header passthrough
    "size 20.32 15.24\n"
    "set hei 0.42328\n"
    "begin graph\n"
    "   data u_1.dat d1=c1,c2\n"
    "   d1 line color BLUE lwidth 0.05292\n"
    "   mystery_stmt inside graph\n"      # axes passthrough
    "end graph\n"
    "! trailing note\n"                   # trailer passthrough
    "draw somebox\n"                      # trailer passthrough
)


def _make_passthrough_figure(tmp_path):
    p = _write(tmp_path, "u.gle", _SRC_ALL_BUCKETS, {"u_1.dat": "1 1\n2 2\n"})
    return parse_gle_figure(p).figure


@pytest.fixture
def passthrough_figure(tmp_path):
    return _make_passthrough_figure(tmp_path)


@pytest.fixture
def document(qapp, passthrough_figure):
    return StubDocument(passthrough_figure)


# ------------------------------------------------------------------
# Sanity: the fixture really does populate all three buckets.
# ------------------------------------------------------------------
def test_fixture_populates_all_three_buckets(document):
    fig = document.figure
    assert any("weird_directive" in line for line in fig.passthrough_header)
    assert any("mystery_stmt" in line for line in fig.axes_list[0].passthrough)
    assert any("trailing note" in line for line in fig.passthrough_trailer)


# ------------------------------------------------------------------
# Bucket contents rendering
# ------------------------------------------------------------------
class TestBucketRendering:
    def test_shows_header_section_content(self, document):
        panel = RawGlePanel(document)
        all_text = _all_section_text(panel)
        assert "set weird_directive 7" in all_text
        assert "! hand note" in all_text

    def test_shows_axes_section_content(self, document):
        panel = RawGlePanel(document)
        all_text = _all_section_text(panel)
        assert any("mystery_stmt" in line for line in all_text.splitlines())

    def test_shows_trailer_section_content(self, document):
        panel = RawGlePanel(document)
        all_text = _all_section_text(panel)
        assert "! trailing note" in all_text
        assert "draw somebox" in all_text

    def test_section_titles_present(self, document):
        panel = RawGlePanel(document)
        titles = _section_titles(panel)
        assert "Header" in titles
        assert "Trailer" in titles
        assert any(t.startswith("Axes") for t in titles)

    def test_axes_section_titled_with_row_col(self, document):
        panel = RawGlePanel(document)
        titles = _section_titles(panel)
        # Single 1x1 layout -> axes idx 1 -> (0,0).
        assert "Axes (0,0)" in titles

    def test_empty_state_hidden_when_content_present(self, document):
        panel = RawGlePanel(document)
        assert panel.empty_label.isHidden() is True

    def test_summary_count_matches_total_lines(self, document):
        panel = RawGlePanel(document)
        fig = document.figure
        expected = (
            len(fig.passthrough_header)
            + len(fig.axes_list[0].passthrough)
            + len(fig.passthrough_trailer)
        )
        assert str(expected) in panel.summary_label.text()
        assert "preserved" in panel.summary_label.text()
        assert "verbatim on save" in panel.summary_label.text()


# ------------------------------------------------------------------
# Empty state
# ------------------------------------------------------------------
class TestEmptyState:
    def test_clean_figure_shows_empty_state(self, qapp):
        fig = gleplot.figure()
        ax = fig.gca()
        ax.plot([1, 2, 3], [1, 2, 3])
        doc = StubDocument(fig)
        panel = RawGlePanel(doc)
        assert panel.empty_label.isHidden() is False
        assert "editable" in panel.empty_label.text()

    def test_clean_figure_summary_is_empty(self, qapp):
        fig = gleplot.figure()
        doc = StubDocument(fig)
        panel = RawGlePanel(doc)
        assert panel.summary_label.text() == ""

    def test_no_figure_shows_empty_state(self, qapp):
        doc = StubDocument(None)
        panel = RawGlePanel(doc)
        assert panel.empty_label.isHidden() is False


# ------------------------------------------------------------------
# Refresh on figure_replaced
# ------------------------------------------------------------------
class TestRefresh:
    def test_refresh_on_figure_replaced_switches_content(self, document, qapp):
        panel = RawGlePanel(document)
        assert "weird_directive" in _all_section_text(panel)

        clean_fig = gleplot.figure()
        clean_fig.gca().plot([1, 2], [1, 2])
        document.set_figure(clean_fig)

        assert panel.empty_label.isHidden() is False
        assert "weird_directive" not in _all_section_text(panel)

    def test_refresh_on_figure_changed(self, document):
        panel = RawGlePanel(document)
        # notify_changed() should re-run refresh() too (guard pattern parity
        # with the other panels) without raising, even though passthrough
        # buckets themselves aren't edited via this panel.
        document.notify_changed()
        assert "weird_directive" in _all_section_text(panel)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _all_section_text(panel: RawGlePanel) -> str:
    from PySide6.QtWidgets import QPlainTextEdit

    return "\n".join(
        w.toPlainText() for w in panel._section_widgets if isinstance(w, QPlainTextEdit)
    )


def _section_titles(panel: RawGlePanel) -> list:
    from PySide6.QtWidgets import QLabel

    return [
        w.text()
        for w in panel._section_widgets
        if isinstance(w, QLabel)
    ]

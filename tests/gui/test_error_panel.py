"""Tests for ErrorPanel's recognizer-warnings section (Track C2).

Covers :meth:`ErrorPanel.set_warnings`/:meth:`ErrorPanel.clear_warnings` --
added alongside the existing compile-error list to surface recognizer
warnings (``list[str]``, prefixed ``structure:``/``metadata:``/``data:``/
``legend:``/``smooth:``/``layout:``) produced by
``gleplot.parser.recognizer.parse_gle_figure`` when opening a ``.gle`` file.
Verifies the warnings section renders distinctly from, and independently of,
the existing error list (:meth:`set_errors`/:meth:`clear`).

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

from PySide6.QtWidgets import QApplication

from gleplot.compiler import GLEError
from gleplot.gui.error_panel import ErrorPanel


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestSetWarnings:
    def test_set_warnings_populates_list(self, qapp):
        panel = ErrorPanel()
        panel.set_warnings(["data: missing file foo.dat", "structure: unbalanced block"])
        assert panel._warnings_list.count() == 2

    def test_set_warnings_prefixes_each_row_with_warning_glyph(self, qapp):
        panel = ErrorPanel()
        panel.set_warnings(["data: missing file foo.dat"])
        text = panel._warnings_list.item(0).text()
        assert text.startswith("⚠")
        assert "data: missing file foo.dat" in text

    def test_set_warnings_shows_the_section(self, qapp):
        panel = ErrorPanel()
        assert panel._warnings_list.isHidden() is True
        panel.set_warnings(["structure: something recovered"])
        assert panel._warnings_list.isHidden() is False

    def test_set_warnings_empty_list_hides_section(self, qapp):
        panel = ErrorPanel()
        panel.set_warnings(["data: x"])
        panel.set_warnings([])
        assert panel._warnings_list.isHidden() is True
        assert panel._warnings_list.count() == 0

    def test_set_warnings_replaces_previous_warnings(self, qapp):
        panel = ErrorPanel()
        panel.set_warnings(["data: first"])
        panel.set_warnings(["legend: second", "smooth: third"])
        assert panel._warnings_list.count() == 2
        texts = [panel._warnings_list.item(i).text() for i in range(2)]
        assert any("second" in t for t in texts)
        assert any("third" in t for t in texts)
        assert not any("first" in t for t in texts)


class TestClearWarnings:
    def test_clear_warnings_empties_list_and_hides_section(self, qapp):
        panel = ErrorPanel()
        panel.set_warnings(["data: x", "layout: y"])
        panel.clear_warnings()
        assert panel._warnings_list.count() == 0
        assert panel._warnings_list.isHidden() is True


class TestCoexistenceWithErrors:
    def test_set_warnings_does_not_affect_error_list(self, qapp):
        panel = ErrorPanel()
        panel.set_errors([GLEError(file=None, line=3, column=1, message="boom")])
        panel.set_warnings(["data: missing file"])
        assert panel._list.count() == 1
        assert panel._warnings_list.count() == 1

    def test_clear_does_not_affect_warnings(self, qapp):
        panel = ErrorPanel()
        panel.set_errors([GLEError(file=None, line=3, column=1, message="boom")])
        panel.set_warnings(["data: missing file"])
        panel.clear()
        assert panel._list.count() == 0
        assert panel._warnings_list.count() == 1
        assert panel._warnings_list.isHidden() is False

    def test_clear_warnings_does_not_affect_errors(self, qapp):
        panel = ErrorPanel()
        panel.set_errors([GLEError(file=None, line=3, column=1, message="boom")])
        panel.set_warnings(["data: missing file"])
        panel.clear_warnings()
        assert panel._list.count() == 1
        assert panel._warnings_list.count() == 0

    def test_both_sections_can_be_populated_simultaneously(self, qapp):
        panel = ErrorPanel()
        panel.set_errors([GLEError(file=None, line=1, column=2, message="syntax error")])
        panel.set_warnings(["data: missing file foo.dat"])
        assert panel._list.isHidden() is False
        assert panel._warnings_list.isHidden() is False
        assert panel._list.count() == 1
        assert panel._warnings_list.count() == 1


class TestWarningsStylingDistinctFromErrors:
    def test_warnings_list_has_its_own_stylesheet(self, qapp):
        panel = ErrorPanel()
        # Distinct styling requirement: the warnings list must not share the
        # (default, unstyled) error list's stylesheet.
        assert panel._warnings_list.styleSheet() != ""
        assert panel._warnings_list.styleSheet() != panel._list.styleSheet()

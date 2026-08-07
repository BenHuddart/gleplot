"""Tests for the structured import report (GLEstudio plan G4; SPEC 10.4).

``RecognizedFigure.notes`` is the source of truth (a tuple of
:class:`~gleplot.parser.report.ImportNote`); ``RecognizedFigure.warnings`` is
now a derived ``"category: message"`` string view kept for backward
compatibility. This suite covers, per the task:

* one fixture per :class:`~gleplot.parser.report.ImportCategory` asserting the
  note's category and (where the module docstring's span-coverage table says
  it is achievable) a real ``source_span``;
* string-compatibility: ``warnings`` is byte-identical to what the pre-G4
  string-returning API produced, derived from ``notes`` alone;
* that notes are runtime-only and never leak into anything serialized
  (``Figure.to_dict()``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import gleplot
from gleplot import axes as _gleplot_axes
from gleplot.parser.recognizer import RecognizedFigure, parse_gle_figure
from gleplot.parser.report import ImportCategory, ImportNote

from tests.parser import _golden_battery as golden


@pytest.fixture(autouse=True)
def _reset_counter():
    # Matches tests/parser/test_recognizer.py: the one test here that uses the
    # golden battery (a live gleplot.figure()) must not leak global data-file
    # counter / open-figure state into other test modules.
    _gleplot_axes._global_data_file_counter = 0
    gleplot.close()
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        gleplot.close()


def _write(tmp_path: Path, name: str, content: str, dats: dict | None = None) -> Path:
    for dat_name, dat_content in (dats or {}).items():
        (tmp_path / dat_name).write_text(dat_content, encoding="utf-8")
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _line(text: str, n: int) -> str:
    """1-indexed physical line ``n`` of ``text`` (for asserting real spans)."""
    return text.splitlines()[n - 1]


# --------------------------------------------------------------------------- #
# warnings <-> notes compatibility
# --------------------------------------------------------------------------- #


def test_warnings_is_derived_from_notes_not_stored_independently():
    """``warnings`` is a computed property, not a second copy of the data."""
    assert "warnings" not in RecognizedFigure.__dataclass_fields__
    assert "notes" in RecognizedFigure.__dataclass_fields__


def test_empty_recognition_has_no_notes_and_no_warnings(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "clean.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    assert rec.notes == ()
    assert rec.warnings == []


def test_rendered_strings_match_category_colon_message(tmp_path):
    """``warnings`` reproduces exactly ``"<category>: <message>"`` per note."""
    src = (
        "size 20.32 15.24\n"
        "sub myplot\n"
        "   begin graph\n"
        "      data data_k.dat d1=c1,c2\n"
        "      d1 line color blue lwidth 0.05\n"
        "   end graph\n"
        "end sub\n"
        "myplot\n"
    )
    p = _write(tmp_path, "prog.gle", src, {"data_k.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    assert rec.notes  # the fixture must actually trigger a note
    assert rec.warnings == [note.rendered for note in rec.notes]
    for note, warning in zip(rec.notes, rec.warnings):
        assert warning == f"{note.category.value}: {note.message}"


# --------------------------------------------------------------------------- #
# One fixture per category: category + span-coverage assertions
# --------------------------------------------------------------------------- #


def test_metadata_category_and_block_span(tmp_path):
    src = (
        "! gleplot-meta-begin v1\n"
        "! gleplot: dpi = 100\n"
        "! gleplot-meta-end\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "meta_v1.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    meta_notes = [n for n in rec.notes if n.category is ImportCategory.METADATA]
    assert meta_notes, rec.notes
    note = meta_notes[0]
    assert "v1" in note.message
    # Span coverage: the whole metadata block (parse_metadata does not track
    # a finer origin for its own warnings) -- lines 1-3 here.
    assert note.source_span == (1, 3)


def test_structure_category_and_statement_span(tmp_path):
    # A 'title' line with an unsupported option (a second string) cannot be
    # modeled and is kept as raw GLE with a structure: note -- see
    # _parse_title_line. The note's span is the exact offending statement.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        '   title "T" "extra"\n'
        "   data d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "title.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    struct_notes = [n for n in rec.notes if n.category is ImportCategory.STRUCTURE]
    assert any("title has unsupported options" in n.message for n in struct_notes)
    note = next(n for n in struct_notes if "title has unsupported options" in n.message)
    assert note.source_span == (3, 3)
    assert _line(src, 3).strip().startswith("title")


def test_data_category_and_series_anchor_span(tmp_path):
    """A broken import reference's note spans the ``dN`` statement that built it.

    Uses the golden-battery writer path (like the pre-existing
    ``test_broken_data_becomes_file_series_with_error``) so the series is
    genuinely classified 'import' (metadata's import-data list vouches it) --
    a hand-written file with no metadata block is always a 'reference' and
    never goes through the ``_load_series`` path this test targets.
    """
    _gleplot_axes._global_data_file_counter = 0
    fig = golden.single_line()
    gle_path = tmp_path / "f.gle"
    fig.savefig_gle(str(gle_path))
    (tmp_path / "golden_0.dat").unlink()

    rec = parse_gle_figure(gle_path)
    data_notes = [n for n in rec.notes if n.category is ImportCategory.DATA]
    assert data_notes, rec.notes
    note = data_notes[0]
    assert note.source_span is not None
    start, end = note.source_span
    assert start == end
    text = gle_path.read_text(encoding="utf-8")
    # The span lands on the 'd1 ...' display statement that referenced the
    # now-missing sidecar, not the 'data' statement itself.
    assert _line(text, start).strip().startswith("d1")


def test_legend_category_key_line_span(tmp_path):
    # A 'key' line with an option combination the model cannot express (a
    # richer form than pos/hei/nobox/offset) is kept whole as raw GLE.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data d.dat d1=c1,c2\n"
        '   d1 line color blue lwidth 0.05 key "s"\n'
        "   key pos tr compact\n"
        "end graph\n"
    )
    p = _write(tmp_path, "key.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    legend_notes = [n for n in rec.notes if n.category is ImportCategory.LEGEND]
    assert any("key has unsupported options" in n.message for n in legend_notes)
    note = next(n for n in legend_notes if "key has unsupported options" in n.message)
    assert note.source_span == (5, 5)
    assert _line(src, 5).strip().startswith("key")


def test_layout_category_geometry_group_span(tmp_path):
    # 'fullsize' cannot be modeled as a placement rect; kept verbatim with a
    # layout: note spanning the geometry statement(s) that triggered it.
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   fullsize\n"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "fullsize.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    layout_notes = [n for n in rec.notes if n.category is ImportCategory.LAYOUT]
    assert any("graph geometry" in n.message for n in layout_notes)
    note = next(n for n in layout_notes if "graph geometry" in n.message)
    assert note.source_span == (3, 3)
    assert _line(src, 3).strip() == "fullsize"


def test_smooth_category_has_no_span(tmp_path):
    # Mixed smooth flags are a whole-figure aggregate (SPEC docstring: "always
    # None") -- no single dataset line is more responsible than the other.
    # smooth_flags is only populated for 'import'-classified series (loaded
    # arrays), so the metadata block's import-data list must vouch both files
    # -- a hand-written file with no metadata block never reaches this path
    # (it stays a 'reference', built by _build_file_series instead).
    src = (
        "! gleplot-meta-begin v2\n"
        "! gleplot: dpi = 100\n"
        "! gleplot: import-data = d1.dat, d2.dat\n"
        "! gleplot-meta-end\n"
        "size 20.32 15.24\n"
        "begin graph\n"
        "   data d1.dat d1=c1,c2\n"
        "   data d2.dat d2=c1,c2\n"
        "   d1 line color blue lwidth 0.05 smooth\n"
        "   d2 line color red lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(
        tmp_path,
        "smooth.gle",
        src,
        {"d1.dat": "0 0\n1 1\n", "d2.dat": "0 0\n1 2\n"},
    )
    rec = parse_gle_figure(p)
    smooth_notes = [n for n in rec.notes if n.category is ImportCategory.SMOOTH]
    assert len(smooth_notes) == 1
    assert smooth_notes[0].source_span is None


def test_programmatic_category_and_statement_span(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "sub myplot\n"
        "   begin graph\n"
        "      data data_k.dat d1=c1,c2\n"
        "      d1 line color blue lwidth 0.05\n"
        "   end graph\n"
        "end sub\n"
        "myplot\n"
    )
    p = _write(tmp_path, "prog2.gle", src, {"data_k.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    prog_notes = [n for n in rec.notes if n.category is ImportCategory.PROGRAMMATIC]
    assert len(prog_notes) == 1
    assert prog_notes[0].source_span == (2, 2)
    assert _line(src, 2).strip() == "sub myplot"


# --------------------------------------------------------------------------- #
# Serialization: notes/warnings are runtime-only
# --------------------------------------------------------------------------- #


def test_notes_and_warnings_never_reach_to_dict(tmp_path):
    src = (
        "size 20.32 15.24\n"
        "begin graph\n"
        "   fullsize\n"
        "   data d.dat d1=c1,c2\n"
        "   d1 line color blue lwidth 0.05\n"
        "end graph\n"
    )
    p = _write(tmp_path, "fullsize2.gle", src, {"d.dat": "0 0\n1 1\n"})
    rec = parse_gle_figure(p)
    assert rec.notes  # sanity: this fixture does produce notes
    snapshot = rec.figure.to_dict()

    def _walk(obj):
        if isinstance(obj, dict):
            assert "notes" not in obj
            assert "warnings" not in obj
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                _walk(v)

    _walk(snapshot)


def test_import_note_is_frozen_and_hashable():
    note = ImportNote(ImportCategory.DATA, "boom", (1, 2))
    hash(note)  # frozen dataclass -> hashable
    try:
        note.message = "changed"  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("ImportNote must be immutable")


# --------------------------------------------------------------------------- #
# String-compatibility over a broad existing-warning corpus
# --------------------------------------------------------------------------- #


def test_string_compatibility_across_every_category(tmp_path):
    """A single file that fires every category at once still round-trips.

    Combines all the per-category fixtures above into one document and
    checks ``warnings`` is still exactly ``[n.rendered for n in notes]`` --
    guards against any emission site bypassing ``_note``/``self.notes``.
    """
    src = (
        "! gleplot-meta-begin v1\n"
        "! gleplot: dpi = 100\n"
        "! gleplot: import-data = d1.dat, d2.dat\n"
        "! gleplot-meta-end\n"
        "sub myplot\n"
        "end sub\n"
        "size 20.32 15.24\n"
        "begin graph\n"
        "   fullsize\n"
        '   title "T" "extra"\n'
        "   data d1.dat d1=c1,c2\n"
        "   data d2.dat d2=c1,c2\n"
        "   d1 line color blue lwidth 0.05 smooth\n"
        '   d2 line color red lwidth 0.05 key "s"\n'
        "   key pos tr compact\n"
        "end graph\n"
    )
    p = _write(
        tmp_path,
        "kitchen_sink.gle",
        src,
        {"d1.dat": "0 0\n1 1\n", "d2.dat": "0 0\n1 2\n"},
    )
    rec = parse_gle_figure(p)
    categories = {n.category for n in rec.notes}
    # At minimum: metadata, structure, legend, layout, smooth, programmatic.
    assert ImportCategory.METADATA in categories
    assert ImportCategory.STRUCTURE in categories
    assert ImportCategory.LEGEND in categories
    assert ImportCategory.LAYOUT in categories
    assert ImportCategory.SMOOTH in categories
    assert ImportCategory.PROGRAMMATIC in categories
    assert rec.warnings == [n.rendered for n in rec.notes]
    for n in rec.notes:
        if n.source_span is not None:
            assert n.source_span[0] <= n.source_span[1]
            assert 1 <= n.source_span[0] <= len(src.splitlines())

"""Tests for the structural parser (document tree + emission)."""

import pytest

from gleplot.parser.syntax import (
    BlankOrComment,
    GraphBlock,
    OpaqueBlock,
    Statement,
    emit,
    parse_gle_source,
    split_statements,
)


# -- statement splitting -----------------------------------------------------

def test_split_no_semicolon():
    segs = split_statements("size 20 15")
    assert [s for s, _ in segs] == ["size 20 15"]


def test_split_two_statements():
    segs = split_statements("set hei 0.5; amove 1 1")
    assert [s for s, _ in segs] == ["set hei 0.5", " amove 1 1"]


def test_split_respects_string_quotes():
    segs = split_statements('write "a ; b"; amove 1 1')
    assert [s for s, _ in segs] == ['write "a ; b"', ' amove 1 1']


def test_split_respects_comment():
    segs = split_statements("amove 1 1 ! a ; b")
    assert [s for s, _ in segs] == ["amove 1 1 ! a ; b"]


# -- single graph structure --------------------------------------------------

SINGLE = (
    "! header\n"
    "size 20 15\n"
    "\n"
    "begin graph\n"
    '    title "t"\n'
    "    data d.dat d1=c1,c2\n"
    "    d1 line color BLUE\n"
    "end graph"
)


def test_single_graph_node_shape():
    doc = parse_gle_source(SINGLE)
    graphs = doc.graphs
    assert len(graphs) == 1
    gb = graphs[0]
    assert isinstance(gb, GraphBlock)
    assert gb.begin.keyword == "begin"
    assert gb.end is not None and gb.end.keyword == "end"
    # Body statements (excluding blanks) present.
    body_stmts = [n for n in gb.body if isinstance(n, Statement)]
    keywords = [s.keyword for s in body_stmts]
    assert "title" in keywords
    assert "data" in keywords


def test_preamble_statements_before_graph():
    doc = parse_gle_source(SINGLE)
    # First nodes are the comment (blank/comment) and 'size' statement.
    assert isinstance(doc.nodes[0], BlankOrComment)  # '! header'
    size_stmt = next(n for n in doc.nodes if isinstance(n, Statement)
                     and n.keyword == "size")
    assert size_stmt.line_no == 2


def test_no_warnings_for_wellformed():
    doc = parse_gle_source(SINGLE)
    assert doc.warnings == []


# -- multi-graph with interlude ----------------------------------------------

MULTI = (
    "size 30 15\n"
    "amove 1 1\n"
    "begin graph\n"
    "   d1 line\n"
    "end graph\n"
    "amove 16 1\n"
    "begin graph\n"
    "   d2 line\n"
    "end graph\n"
)


def test_two_graphs_with_interlude_between():
    doc = parse_gle_source(MULTI)
    assert len(doc.graphs) == 2
    # The 'amove 16 1' interlude sits between the two graph blocks as a
    # top-level statement node (order-preserving single list).
    node_kinds = [type(n).__name__ for n in doc.nodes]
    # Expect: Statement(size), Statement(amove), GraphBlock, Statement(amove),
    # GraphBlock.
    assert node_kinds.count("GraphBlock") == 2
    gb_positions = [i for i, n in enumerate(doc.nodes)
                    if isinstance(n, GraphBlock)]
    # There is at least one Statement node between the two graph blocks.
    between = doc.nodes[gb_positions[0] + 1: gb_positions[1]]
    assert any(isinstance(n, Statement) and n.keyword == "amove"
               for n in between)


# -- opaque blocks -----------------------------------------------------------

OPAQUE = (
    "begin text\n"
    "  this is opaque ; with a semicolon\n"
    '  and "quotes" and ! bang\n'
    "end text\n"
    "after\n"
)


def test_opaque_block_not_descended():
    doc = parse_gle_source(OPAQUE)
    opaque = next(n for n in doc.nodes if isinstance(n, OpaqueBlock))
    assert opaque.block_type == "text"
    assert len(opaque.inner_lines) == 2
    # Inner content is kept raw, not parsed into statements.
    assert "opaque" in opaque.inner_lines[0].text


@pytest.mark.parametrize("block", [
    "object", "tex", "key", "path", "translate", "rotate", "scale",
    "origin", "clip", "table", "name", "box", "length",
])
def test_known_opaque_block_types(block):
    src = f"begin {block}\n  stuff\nend {block}\n"
    doc = parse_gle_source(src)
    assert any(isinstance(n, OpaqueBlock) and n.block_type == block
               for n in doc.nodes)
    assert emit(doc) == src


# -- multi-statement lines ---------------------------------------------------

def test_multi_statement_line_splits_into_nodes():
    doc = parse_gle_source("set hei 0.5; amove 1 1\n")
    stmt_nodes = [n for n in doc.nodes if isinstance(n, Statement)]
    assert len(stmt_nodes) == 2
    assert stmt_nodes[0].keyword == "set"
    assert stmt_nodes[1].keyword == "amove"
    assert stmt_nodes[0].sub_index == 0
    assert stmt_nodes[1].sub_index == 1


# -- blank / comment preservation --------------------------------------------

def test_blank_and_comment_lines_are_nodes():
    doc = parse_gle_source("\n! comment\n   \nsize 1 1\n")
    blanks = [n for n in doc.nodes if isinstance(n, BlankOrComment)]
    assert len(blanks) == 3  # empty, comment, whitespace-only


# -- unbalanced block recovery -----------------------------------------------

def test_unclosed_graph_recovers_with_warning():
    doc = parse_gle_source("begin graph\n   d1 line\n")
    assert len(doc.graphs) == 1
    assert doc.graphs[0].end is None
    assert any("not closed" in w.message for w in doc.warnings)
    # Still round-trips.
    assert emit(doc) == "begin graph\n   d1 line\n"


def test_stray_end_recovers_with_warning():
    doc = parse_gle_source("size 1 1\nend graph\n")
    assert any("without matching" in w.message for w in doc.warnings)
    assert emit(doc) == "size 1 1\nend graph\n"


def test_unclosed_opaque_recovers_with_warning():
    doc = parse_gle_source("begin object\n  x\n")
    assert any("not closed" in w.message for w in doc.warnings)
    assert emit(doc) == "begin object\n  x\n"


# -- statements() walk -------------------------------------------------------

def test_statements_walk_includes_graph_body():
    doc = parse_gle_source(SINGLE)
    keywords = [s.keyword for s in doc.statements()]
    assert "begin" in keywords
    assert "title" in keywords
    assert "end" in keywords


# -- modification API --------------------------------------------------------

def test_replace_statement_single_line():
    doc = parse_gle_source("size 20 15\nbegin graph\nend graph\n")
    size_stmt = next(s for s in doc.statements() if s.keyword == "size")
    doc.replace_statement(size_stmt, "size 30 20")
    out = emit(doc)
    assert "size 30 20" in out
    assert "size 20 15" not in out
    # Other lines untouched.
    assert "begin graph\nend graph\n" in out


def test_replace_preserves_indentation():
    doc = parse_gle_source("begin graph\n    title \"old\"\nend graph")
    title_stmt = next(s for s in doc.statements() if s.keyword == "title")
    doc.replace_statement(title_stmt, 'title "new"')
    out = emit(doc)
    assert '    title "new"' in out


def test_replace_one_of_multi_statement_line():
    doc = parse_gle_source("set hei 0.5; amove 1 1\n")
    amove = next(s for s in doc.statements() if s.keyword == "amove")
    doc.replace_statement(amove, "amove 2 2")
    out = emit(doc)
    assert out == "set hei 0.5; amove 2 2\n"


# -- line ending fidelity ----------------------------------------------------

def test_crlf_endings_preserved():
    src = "size 1 1\r\nbegin graph\r\nend graph\r\n"
    doc = parse_gle_source(src)
    assert emit(doc) == src


def test_no_trailing_newline_preserved():
    src = "size 1 1\nend graph"
    doc = parse_gle_source(src)
    assert emit(doc) == src
    assert doc.lines[-1].ending == ""


def test_empty_input():
    doc = parse_gle_source("")
    assert doc.lines == []
    assert doc.nodes == []
    assert emit(doc) == ""


class TestOpaqueBlockNesting:
    """MA-review fix: nested begin/end inside opaque blocks."""

    def test_nested_text_in_key_block(self):
        from gleplot.parser.syntax import parse_gle_source, OpaqueBlock, Statement
        src = "begin key\nbegin text\nlabel\nend\nend key\n"
        doc = parse_gle_source(src)
        opaques = [n for n in doc.nodes if isinstance(n, OpaqueBlock)]
        assert len(opaques) == 1
        blk = opaques[0]
        assert blk.block_type == "key"
        assert blk.end is not None
        inner_texts = [ln.text for ln in blk.inner_lines]
        assert inner_texts == ["begin text", "label", "end"]
        assert not doc.warnings
        assert doc.emit() == src

    def test_doubly_nested_opaque(self):
        from gleplot.parser.syntax import parse_gle_source, OpaqueBlock
        src = "begin object o\nbegin box\nbegin text\nhi\nend\nend\nend object\n"
        doc = parse_gle_source(src)
        opaques = [n for n in doc.nodes if isinstance(n, OpaqueBlock)]
        assert len(opaques) == 1
        assert opaques[0].end is not None
        assert not doc.warnings
        assert doc.emit() == src

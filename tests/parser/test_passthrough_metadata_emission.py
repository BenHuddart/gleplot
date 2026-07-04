"""Track B2: passthrough bucket emission positions and metadata-block wiring.

Covers the writer-facing half of Track B2 (the model fields themselves --
``Figure.passthrough_header``/``passthrough_trailer``/``metadata_extra`` and
``Axes.passthrough`` -- are exercised for serialization round-tripping in
``tests/integration/test_project_io.py`` and ``tests/unit/test_serialization.py``;
byte-exact structural round-tripping is covered in
``tests/parser/test_passthrough_roundtrip.py``).

This module asserts:

* Each bucket lands at its documented canonical position in the generated
  GLE text, for both the single-plot and multi-subplot writer paths --
  verified structurally via ``gleplot.parser.syntax.parse_gle_source`` so the
  assertions dogfood the same parser the recognizer track will build on.
* An empty-bucket figure produces byte-identical output to one with buckets
  populated-then-cleared (no blank-line churn), except for the metadata
  block that Track B2 adds for every figure.
* The ``! gleplot:`` metadata block emitted by ``_generate_gle_with_files``
  matches what ``parser.metadata.parse_metadata`` recovers, for both a
  default figure and a figure with every non-default knob set.
* ``import-data`` lists exactly the generated data sidecars for a save and
  excludes ``*_from_file`` references.
* A metadata- and passthrough-bearing script still compiles with the real
  GLE toolchain (smoke test; skipped if GLE is not installed).
"""

import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler
from gleplot.parser import parse_gle_source
from gleplot.parser import metadata as gle_metadata
from gleplot.parser.syntax import Statement, BlankOrComment
from tests._tempdir import make_tempdir


# --------------------------------------------------------------------------- #
# Bucket emission positions
# --------------------------------------------------------------------------- #

class TestBucketPositionsSinglePlot:
    def _build(self):
        fig = glp.figure(data_prefix='fig')
        fig.passthrough_header = ['! header passthrough', 'set some_directive 1']
        fig.passthrough_trailer = ['! trailer passthrough']
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9], label='q')
        ax.passthrough = ['! axes passthrough', 'amove 1 1']
        return fig

    def test_header_passthrough_before_first_graph_block(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        text = out.read_text(encoding='utf-8')
        doc = parse_gle_source(text)

        # Locate the header passthrough lines and the first graph block in
        # document order: the passthrough lines must precede the graph.
        header_idx = next(
            i for i, ln in enumerate(doc.lines) if ln.text == '! header passthrough'
        )
        graph = doc.graphs[0]
        assert header_idx < graph.begin.line_no - 1  # line_no is 1-based

    def test_axes_passthrough_immediately_before_end_graph(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        doc = parse_gle_source(out.read_text(encoding='utf-8'))

        graph = doc.graphs[0]
        # The body's last two non-blank nodes should be the axes passthrough
        # lines (raw statements), directly followed by 'end graph'.
        body_stmts = [n for n in graph.body if isinstance(n, (Statement, BlankOrComment))]
        last_texts = [
            (s.statement.source_line.text if isinstance(s, BlankOrComment) else s.raw)
            for s in body_stmts[-2:]
        ]
        assert last_texts == ['! axes passthrough', 'amove 1 1']
        assert graph.end is not None
        assert graph.end.keyword == 'end'

    def test_trailer_passthrough_after_last_graph_block(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        doc = parse_gle_source(out.read_text(encoding='utf-8'))

        graph = doc.graphs[0]
        trailer_idx = next(
            i for i, ln in enumerate(doc.lines) if ln.text == '! trailer passthrough'
        )
        assert trailer_idx + 1 > graph.end.line_no  # after 'end graph', 1-based vs 0-based


class TestBucketPositionsMultiSubplot:
    def _build(self):
        fig, axes = glp.subplots(1, 2, data_prefix='fig')
        fig.passthrough_header = ['! header passthrough']
        fig.passthrough_trailer = ['! trailer passthrough']
        axes[0].plot([1, 2, 3], [1, 4, 9])
        axes[0].passthrough = ['! ax0 passthrough']
        axes[1].plot([1, 2, 3], [3, 2, 1])
        axes[1].passthrough = ['! ax1 passthrough']
        return fig

    def test_header_before_first_graph(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        doc = parse_gle_source(out.read_text(encoding='utf-8'))

        header_idx = next(
            i for i, ln in enumerate(doc.lines) if ln.text == '! header passthrough'
        )
        assert len(doc.graphs) == 2
        assert header_idx < doc.graphs[0].begin.line_no - 1

    def test_each_axes_passthrough_stays_in_its_own_graph_block(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        doc = parse_gle_source(out.read_text(encoding='utf-8'))

        assert len(doc.graphs) == 2
        for graph, expected in zip(doc.graphs, ['! ax0 passthrough', '! ax1 passthrough']):
            body_stmts = [n for n in graph.body if isinstance(n, (Statement, BlankOrComment))]
            last = body_stmts[-1]
            last_text = last.statement.source_line.text if isinstance(last, BlankOrComment) else last.raw
            assert last_text == expected

    def test_trailer_after_all_graph_blocks(self, tmp_path):
        fig = self._build()
        out = tmp_path / 'plot.gle'
        fig.savefig_gle(str(out))
        doc = parse_gle_source(out.read_text(encoding='utf-8'))

        trailer_idx = next(
            i for i, ln in enumerate(doc.lines) if ln.text == '! trailer passthrough'
        )
        last_graph_end = doc.graphs[-1].end.line_no
        assert trailer_idx + 1 > last_graph_end


# --------------------------------------------------------------------------- #
# Empty-bucket byte-identity (no blank-line churn)
# --------------------------------------------------------------------------- #

class TestEmptyBucketByteIdentity:
    def test_untouched_figure_matches_populated_then_cleared(self):
        """A figure that never touches the passthrough buckets must generate
        byte-identical GLE to one where the buckets were populated and then
        reset back to empty -- i.e. emission must be purely conditional on
        current bucket contents, with no residual formatting difference."""
        fig_plain = glp.figure(data_prefix='fig')
        ax_plain = fig_plain.add_subplot(111)
        ax_plain.plot([1, 2, 3], [1, 4, 9], label='q')

        fig_touched = glp.figure(data_prefix='fig')
        fig_touched.passthrough_header = ['! temp']
        fig_touched.passthrough_header = []
        fig_touched.passthrough_trailer = ['! temp']
        fig_touched.passthrough_trailer = []
        fig_touched.metadata_extra = {'temp': 'x'}
        fig_touched.metadata_extra = {}
        ax_touched = fig_touched.add_subplot(111)
        ax_touched.plot([1, 2, 3], [1, 4, 9], label='q')
        ax_touched.passthrough = ['! temp']
        ax_touched.passthrough = []

        plain_content, plain_data = fig_plain._generate_gle_with_files()
        touched_content, touched_data = fig_touched._generate_gle_with_files()

        assert plain_content == touched_content
        assert plain_data == touched_data

    def test_no_passthrough_produces_no_passthrough_lines(self):
        fig = glp.figure(data_prefix='fig')
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9])
        content, _ = fig._generate_gle_with_files()

        # Only the metadata block should be new relative to pre-B2 output;
        # no stray blank lines or passthrough markers appear.
        assert '! header' not in content
        assert '! trailer' not in content
        assert '! axes' not in content
        # No doubled blank lines anywhere (churn smell).
        assert '\n\n\n' not in content


# --------------------------------------------------------------------------- #
# Metadata block correctness
# --------------------------------------------------------------------------- #

class TestMetadataBlockCorrectness:
    def test_default_figure_emits_dpi_and_empty_import_data_only(self):
        fig = glp.figure(data_prefix='fig')
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 4, 9])
        content, data_files = fig._generate_gle_with_files()

        data, warnings = gle_metadata.parse_metadata(content.splitlines())
        assert warnings == []
        assert data['dpi'] == 100
        assert data['import-data'] == sorted(data_files.keys())
        # Defaults omitted.
        assert 'sharex' not in data
        assert 'sharey' not in data
        assert 'msize_scale' not in data

    def test_non_default_figure_round_trips_every_field(self):
        marker = glp.GLEMarkerConfig(msize_scale=2.5)
        fig, axes = glp.subplots(1, 2, dpi=150, sharey=True, marker=marker, data_prefix='fig')
        fig.metadata_extra = {'future_flag': 'hello'}
        axes[0].plot([1, 2, 3], [1, 2, 3])
        axes[1].plot([1, 2, 3], [3, 2, 1])

        content, data_files = fig._generate_gle_with_files()
        data, warnings = gle_metadata.parse_metadata(content.splitlines())
        assert warnings == []
        assert data['dpi'] == 150
        assert data['sharey'] is True
        assert data['msize_scale'] == 2.5
        assert data['import-data'] == sorted(data_files.keys())
        assert data['future_flag'] == 'hello'

    def test_metadata_block_sits_after_header_comments_before_size(self, tmp_path):
        fig = glp.figure(data_prefix='fig')
        fig.add_subplot(111).plot([1, 2, 3], [1, 2, 3])
        content, _ = fig._generate_gle_with_files()
        lines = content.split('\n')

        assert lines[0] == '! GLE graphics file'
        assert lines[1] == '! Generated by gleplot'
        assert lines[2] == gle_metadata.BEGIN_MARKER
        end_idx = lines.index(gle_metadata.END_MARKER)
        assert lines[end_idx + 1] == ''
        assert lines[end_idx + 2].startswith('size ')


# --------------------------------------------------------------------------- #
# import-data accuracy: generated sidecars vs *_from_file references
# --------------------------------------------------------------------------- #

class TestImportDataAccuracy:
    def test_generated_series_listed_file_series_excluded(self):
        fig = glp.figure(data_prefix='fig')
        ax = fig.add_subplot(111)
        ax.plot([1, 2, 3], [1, 2, 3], label='generated')
        ax.line_from_file('external.dat', 1, 2, label='referenced')

        content, data_files = fig._generate_gle_with_files()
        data, _ = gle_metadata.parse_metadata(content.splitlines())

        assert data['import-data'] == sorted(data_files.keys())
        assert 'external.dat' not in data['import-data']
        assert all(name.startswith('fig_') for name in data['import-data'])

    def test_import_data_sorted_and_matches_multiple_series(self):
        fig = glp.figure(data_prefix='fig')
        ax = fig.add_subplot(111)
        for i in range(3):
            ax.plot([1, 2, 3], [i, i + 1, i + 2], label=f'l{i}')

        content, data_files = fig._generate_gle_with_files()
        data, _ = gle_metadata.parse_metadata(content.splitlines())

        assert data['import-data'] == sorted(data_files.keys())
        assert data['import-data'] == sorted(data['import-data'])
        assert len(data['import-data']) == 3


# --------------------------------------------------------------------------- #
# Real GLE compile smoke test
# --------------------------------------------------------------------------- #

def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


@pytest.mark.skipif(not _gle_available(), reason='GLE not installed')
def test_metadata_and_passthrough_figure_compiles_with_real_gle():
    """A .gle carrying the metadata block, header/trailer passthrough, and
    axes-local passthrough must still be valid GLE source that the real GLE
    binary accepts -- the metadata block is a comment block and passthrough
    lines are themselves valid GLE, so this should compile cleanly."""
    fig = glp.figure(data_prefix='fig')
    fig.passthrough_header = ['! recovered header comment']
    fig.passthrough_trailer = ['! recovered trailer comment']
    fig.metadata_extra = {'future_key': 'future_value'}
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3, 4], [1, 4, 9, 16], color='blue', label='quad')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.passthrough = ['! recovered axes-local comment']

    tempdir = make_tempdir()
    gle_file = tempdir / 'passthrough_metadata.gle'
    fig.savefig_gle(str(gle_file))

    compiler = GLECompiler()
    pdf_file = compiler.compile(str(gle_file), output_format='pdf')

    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 0

"""Unit tests for the GLE compiler wrapper."""

import shutil
import subprocess
import sys
import unittest
import warnings
from pathlib import Path
from unittest import mock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from gleplot.compiler import (
    RASTER_COMPILE_FORMATS,
    SUPPORTED_COMPILE_FORMATS,
    GLECompileError,
    GLECompiler,
    GLEError,
    autodetect_gle,
    build_compile_args,
    find_gle,
    parse_gle_errors,
    set_gle_path_override,
)
from tests._tempdir import make_tempdir


# ---------------------------------------------------------------------------
# Fixtures: sample GLE compiler output blocks.
# ---------------------------------------------------------------------------

SINGLE_ERROR_OUTPUT = (
    "GLE 4.3.3[bad.gle]-C-R-\n"
    "\n"
    ">> bad.gle (3) |let d1 = sin(x frum 0 to 2*pi|\n"
    ">>                                           ^\n"
    ">> Error: expected closing ')'\n"
    "\n"
    "[bad][.eps]\n"
)

NO_CARET_OUTPUT = (
    "GLE 4.3.3[bad.gle]-C-R-\n"
    "\n"
    ">> bad.gle (5) |some source text|\n"
    ">> Error: something went wrong\n"
    "\n"
    "[bad][.eps]\n"
)

MULTI_ERROR_OUTPUT = (
    "GLE 4.3.3[bad.gle]-C-R-\n"
    "\n"
    ">> bad.gle (2) |x = 1 +|\n"
    ">>                    ^\n"
    ">> Error: expected expression\n"
    "\n"
    ">> bad.gle (7) |y = foo(|\n"
    ">>                     ^\n"
    ">> Error: expected closing ')'\n"
    "\n"
    "[bad][.eps]\n"
)

UNPARSEABLE_OUTPUT = "something totally unexpected blew up\nwith no structure at all\n"


class TestParseGleErrors(unittest.TestCase):
    """Tests for parse_gle_errors()."""

    def test_single_error_with_caret(self):
        errors = parse_gle_errors(SINGLE_ERROR_OUTPUT)
        self.assertEqual(len(errors), 1)
        err = errors[0]
        self.assertIsInstance(err, GLEError)
        self.assertEqual(err.file, 'bad.gle')
        self.assertEqual(err.line, 3)
        self.assertEqual(err.source_line, 'let d1 = sin(x frum 0 to 2*pi')
        # Caret points just past the end of the quoted source (30 chars).
        self.assertEqual(err.column, len(err.source_line))
        self.assertIn("expected closing ')'", err.message)

    def test_error_without_caret_line(self):
        errors = parse_gle_errors(NO_CARET_OUTPUT)
        self.assertEqual(len(errors), 1)
        err = errors[0]
        self.assertEqual(err.file, 'bad.gle')
        self.assertEqual(err.line, 5)
        self.assertIsNone(err.column)
        self.assertEqual(err.source_line, 'some source text')
        self.assertIn('something went wrong', err.message)

    def test_multiple_errors(self):
        errors = parse_gle_errors(MULTI_ERROR_OUTPUT)
        self.assertEqual(len(errors), 2)

        first, second = errors
        self.assertEqual(first.line, 2)
        self.assertEqual(first.source_line, 'x = 1 +')
        self.assertIn('expected expression', first.message)

        self.assertEqual(second.line, 7)
        self.assertEqual(second.source_line, 'y = foo(')
        self.assertIn("expected closing ')'", second.message)

    def test_unparseable_output_falls_back_to_raw_message(self):
        errors = parse_gle_errors(UNPARSEABLE_OUTPUT)
        self.assertEqual(len(errors), 1)
        err = errors[0]
        self.assertIsNone(err.file)
        self.assertIsNone(err.line)
        self.assertIsNone(err.column)
        self.assertEqual(err.message, UNPARSEABLE_OUTPUT.strip())

    def test_empty_output_returns_no_errors(self):
        self.assertEqual(parse_gle_errors(''), [])
        self.assertEqual(parse_gle_errors('   \n  \n'), [])

    def test_column_matches_caret_relative_to_source(self):
        # Caret directly under the 'x' at index 4 of the quoted source.
        output = (
            ">> file.gle (1) |abcd efgh|\n"
            ">>                   ^\n"
            ">> Error: bad token\n"
        )
        errors = parse_gle_errors(output)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].source_line, 'abcd efgh')
        # pipe is at index 16 ('>> file.gle (1) |'); caret at index 21
        # => column = 21 - 16 - 1 = 4
        self.assertEqual(errors[0].column, 4)


class TestFindGle(unittest.TestCase):
    """Tests for find_gle() discovery order."""

    def setUp(self):
        # find_gle now consults a process-global override first; ensure a clean
        # slate so these auto-detect tests aren't affected by an earlier one.
        set_gle_path_override(None)

    def tearDown(self):
        set_gle_path_override(None)

    def test_env_var_takes_priority(self):
        with mock.patch.dict('os.environ', {'GLE_PATH': str(Path(__file__))}):
            with mock.patch('gleplot.compiler.shutil.which', return_value='/should/not/be/used'):
                self.assertEqual(find_gle(), str(Path(__file__)))

    def test_env_var_ignored_if_nonexistent(self):
        with mock.patch.dict('os.environ', {'GLE_PATH': 'C:/does/not/exist/gle.exe'}):
            with mock.patch('gleplot.compiler.shutil.which', return_value='/usr/bin/gle'):
                self.assertEqual(find_gle(), '/usr/bin/gle')

    def test_env_var_nonexistent_emits_warning(self):
        with mock.patch.dict('os.environ', {'GLE_PATH': 'C:/does/not/exist/gle.exe'}):
            with mock.patch('gleplot.compiler.shutil.which', return_value='/usr/bin/gle'):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    find_gle()
                self.assertTrue(
                    any('GLE_PATH' in str(w.message) for w in caught),
                    f"expected a warning mentioning GLE_PATH, got: {[str(w.message) for w in caught]}",
                )

    def test_which_used_when_no_env_var(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch('gleplot.compiler.shutil.which', return_value='/usr/local/bin/gle'):
                self.assertEqual(find_gle(), '/usr/local/bin/gle')

    def test_falls_back_to_well_known_paths(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch('gleplot.compiler.shutil.which', return_value=None):
                with mock.patch('gleplot.compiler.sys.platform', 'win32'):
                    # Well-known entries are now glob patterns expanded against
                    # the real filesystem; make each pattern "match itself" so
                    # the first (literal) win32 path is returned regardless of
                    # the host OS running the test (e.g. Linux CI).
                    with mock.patch(
                        'gleplot.compiler.glob.glob',
                        side_effect=lambda pat, recursive=False: [pat],
                    ):
                        with mock.patch('gleplot.compiler.Path.exists', return_value=True):
                            result = find_gle()
                            self.assertEqual(result, r'C:\Program Files\GLE\bin\gle.exe')

    def test_returns_none_when_nothing_found(self):
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch('gleplot.compiler.shutil.which', return_value=None):
                with mock.patch('gleplot.compiler.Path.exists', return_value=False):
                    self.assertIsNone(find_gle())

    def test_explicit_gle_path_arg_bypasses_discovery(self):
        # GLECompiler(gle_path=...) should not need to call find_gle() at all.
        with mock.patch('gleplot.compiler.find_gle') as mock_find:
            compiler = GLECompiler(gle_path='/explicit/path/to/gle')
            self.assertEqual(compiler.gle_path, '/explicit/path/to/gle')
            mock_find.assert_not_called()


class TestGlePathOverride(unittest.TestCase):
    """Tests for the explicit override consulted first by find_gle()."""

    def tearDown(self):
        set_gle_path_override(None)

    def test_override_wins_over_env_and_path(self):
        # The override represents an explicit in-app choice and must outrank
        # GLE_PATH and PATH (an existing file is required).
        override = str(Path(__file__))
        set_gle_path_override(override)
        with mock.patch.dict('os.environ', {'GLE_PATH': '/some/other/gle'}):
            with mock.patch(
                'gleplot.compiler.shutil.which', return_value='/on/path/gle'
            ):
                self.assertEqual(find_gle(), override)

    def test_missing_override_warns_and_falls_through(self):
        set_gle_path_override('C:/does/not/exist/gle.exe')
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch(
                'gleplot.compiler.shutil.which', return_value='/usr/bin/gle'
            ):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    result = find_gle()
                self.assertEqual(result, '/usr/bin/gle')
                self.assertTrue(
                    any('does not exist' in str(w.message) for w in caught),
                    f"expected a fall-through warning, got: "
                    f"{[str(w.message) for w in caught]}",
                )

    def test_empty_string_clears_override(self):
        set_gle_path_override(str(Path(__file__)))
        set_gle_path_override('')  # normalized to "unset"
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch(
                'gleplot.compiler.shutil.which', return_value='/usr/bin/gle'
            ):
                self.assertEqual(find_gle(), '/usr/bin/gle')

    def test_autodetect_ignores_override(self):
        # autodetect_gle() is what the GUI's "Auto-detect" button calls; it must
        # bypass whatever the user has currently pinned.
        set_gle_path_override(str(Path(__file__)))
        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch(
                'gleplot.compiler.shutil.which', return_value='/usr/bin/gle'
            ):
                self.assertEqual(autodetect_gle(), '/usr/bin/gle')


class TestRobustWellKnownDetection(unittest.TestCase):
    """The well-known fallback expands glob patterns for versioned installs."""

    def tearDown(self):
        set_gle_path_override(None)

    def test_glob_matches_versioned_install_dir(self):
        # A GLE installed under a versioned dir (e.g. "GLE-4.3.9") is only
        # reachable via the glob patterns, not the two literal paths.
        versioned = r'C:\Program Files\GLE-4.3.9\bin\gle.exe'

        def fake_glob(pattern, recursive=False):
            # Only the wildcard pattern matches the versioned install.
            if '*' in pattern and pattern.startswith(r'C:\Program Files'):
                return [versioned]
            return []

        with mock.patch.dict('os.environ', {}, clear=False):
            import os as _os
            _os.environ.pop('GLE_PATH', None)
            with mock.patch('gleplot.compiler.shutil.which', return_value=None):
                with mock.patch('gleplot.compiler.sys.platform', 'win32'):
                    with mock.patch(
                        'gleplot.compiler.glob.glob', side_effect=fake_glob
                    ):
                        with mock.patch(
                            'gleplot.compiler.Path.exists', return_value=True
                        ):
                            self.assertEqual(find_gle(), versioned)


def _real_gle_available():
    return find_gle() is not None


@unittest.skipUnless(_real_gle_available(), "GLE compiler not available on this machine")
class TestCompileIntegration(unittest.TestCase):
    """Integration-style tests that invoke the real installed GLE binary."""

    def setUp(self):
        self.tempdir = make_tempdir()
        self.compiler = GLECompiler()

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write_good_gle(self, directory: Path, name: str = 'good.gle') -> Path:
        gle_file = directory / name
        gle_file.write_text(
            "size 8 6\n"
            "begin graph\n"
            "   title \"Test\"\n"
            "end graph\n"
        )
        return gle_file

    def _write_bad_gle(self, directory: Path, name: str = 'bad.gle') -> Path:
        gle_file = directory / name
        gle_file.write_text(
            "size 8 6\n"
            "begin graph\n"
            "let d1 = sin(x frum 0 to 2*pi\n"
            "end graph\n"
        )
        return gle_file

    def test_compile_pdf_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='pdf')
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.pdf')
        self.assertGreater(result.stat().st_size, 0)

    def test_compile_png_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.png')

    def test_compile_jpg_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='jpg', dpi=150)
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.jpg')

    def test_compile_eps_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='eps')
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.eps')

    def test_compile_error_path_raises_gle_compile_error(self):
        gle_file = self._write_bad_gle(self.tempdir)
        with self.assertRaises(GLECompileError) as ctx:
            self.compiler.compile(str(gle_file), output_format='pdf')

        exc = ctx.exception
        self.assertTrue(exc.errors)
        self.assertGreater(len(exc.raw_output), 0)
        first = exc.errors[0]
        self.assertEqual(first.line, 3)
        self.assertIn("expected closing ')'", first.message)

        # No output file should have been produced.
        output_path = gle_file.with_suffix('.pdf')
        self.assertFalse(output_path.exists())

    def test_compile_missing_input_raises_file_not_found(self):
        missing = self.tempdir / 'does_not_exist.gle'
        with self.assertRaises(FileNotFoundError):
            self.compiler.compile(str(missing), output_format='pdf')

    def test_compile_handles_paths_with_spaces(self):
        spacey_dir = self.tempdir / 'dir with spaces'
        spacey_dir.mkdir()
        gle_file = self._write_good_gle(spacey_dir, name='my file.gle')

        result = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        self.assertTrue(result.exists())
        self.assertEqual(result.name, 'my file.png')

    def test_compile_does_not_leave_stray_eps(self):
        # GLE 4.3.3 with -o does not leave a stray .eps for non-eps output
        # formats, so a plain non-eps compile should not produce one.
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='png', dpi=150)
        self.assertTrue(result.exists())

        stray_eps = gle_file.with_suffix('.eps')
        self.assertFalse(stray_eps.exists())

    def test_compile_timeout(self):
        gle_file = self._write_good_gle(self.tempdir)
        with mock.patch(
            'gleplot.compiler.subprocess.run',
            side_effect=subprocess.TimeoutExpired(cmd='gle', timeout=0.001),
        ):
            with self.assertRaises(GLECompileError) as ctx:
                self.compiler.compile(str(gle_file), output_format='pdf', timeout=0.001)
            self.assertIn('timed out', str(ctx.exception))

    def test_compile_svg_happy_path(self):
        # SVG emits a benign cairo font warning on stderr but exits 0 and
        # produces a valid file with the installed GLE 4.3.3.
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format='svg', dpi=150)
        self.assertTrue(result.exists())
        self.assertEqual(result.suffix, '.svg')


class TestBuildCompileArgs(unittest.TestCase):
    """Tests for build_compile_args(): the single, unified device-flag
    builder (Track G3). Previously GLECompiler.compile() built an uppercase
    ``-d PDF`` with ``-r`` only for raster formats, while gui/preview.py
    built a lowercase ``-d svg`` with ``-r`` unconditional (including for
    vector formats, where GLE just ignores it). This is the one place that
    decides the shape now.
    """

    def test_all_supported_formats_produce_lowercase_device_flag(self):
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            args = build_compile_args(fmt, 'out', 'in.gle')
            self.assertEqual(args[0], '-d')
            self.assertEqual(args[1], fmt.lower())

    def test_uppercase_and_mixed_case_input_normalized_to_lowercase(self):
        for given in ('PDF', 'Pdf', 'pDf'):
            args = build_compile_args(given, 'out', 'in.gle')
            self.assertEqual(args[1], 'pdf')

    def test_raster_formats_include_dpi_flag(self):
        for fmt in RASTER_COMPILE_FORMATS:
            args = build_compile_args(fmt, 'out', 'in.gle', dpi=150)
            self.assertIn('-r', args)
            self.assertEqual(args[args.index('-r') + 1], '150')

    def test_vector_formats_omit_dpi_flag_even_when_dpi_given(self):
        vector_formats = SUPPORTED_COMPILE_FORMATS - RASTER_COMPILE_FORMATS
        self.assertTrue(vector_formats)  # sanity: pdf/eps/svg are vector
        for fmt in vector_formats:
            args = build_compile_args(fmt, 'out', 'in.gle', dpi=300)
            self.assertNotIn('-r', args)

    def test_raster_format_without_dpi_omits_dpi_flag(self):
        # dpi is optional; when the caller doesn't have one to give (or
        # doesn't care), -r must not appear with a garbage value.
        args = build_compile_args('png', 'out', 'in.gle')
        self.assertNotIn('-r', args)

    def test_dpi_is_coerced_to_int_string(self):
        args = build_compile_args('png', 'out', 'in.gle', dpi=150.0)
        self.assertEqual(args[args.index('-r') + 1], '150')

    def test_output_and_input_paths_appear_last_in_order(self):
        args = build_compile_args('pdf', 'result.pdf', 'script.gle')
        self.assertEqual(args[-3:], ['-o', 'result.pdf', 'script.gle'])

    def test_output_before_input_with_o_flag(self):
        args = build_compile_args('pdf', 'result.pdf', 'script.gle')
        o_index = args.index('-o')
        self.assertEqual(args[o_index + 1], 'result.pdf')
        self.assertEqual(args[o_index + 2], 'script.gle')

    def test_accepts_path_objects(self):
        args = build_compile_args('pdf', Path('out.pdf'), Path('in.gle'))
        self.assertIn('out.pdf', args)
        self.assertIn('in.gle', args)

    def test_unsupported_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_compile_args('bogus', 'out', 'in.gle')

    # -- cairo: flag construction (Track G6). Deciding *when* to enable it
    #    (figures using alpha) lives in Figure.requires_cairo() /
    #    Figure.savefig(), not here -- this builder only ever does what its
    #    caller tells it, for every device gleplot supports.
    def test_cairo_false_by_default_omits_flag(self):
        args = build_compile_args('pdf', 'out', 'in.gle')
        self.assertNotIn('-cairo', args)

    def test_cairo_true_appends_flag_directly_after_device(self):
        args = build_compile_args('pdf', 'out', 'in.gle', cairo=True)
        self.assertIn('-cairo', args)
        # Placed right after -d <fmt>, before -o/-r, matching GLE's "options
        # before filename" convention used throughout this module.
        self.assertEqual(args[:3], ['-d', 'pdf', '-cairo'])

    def test_cairo_and_raster_dpi_compose(self):
        args = build_compile_args('png', 'out', 'in.gle', dpi=150, cairo=True)
        self.assertIn('-cairo', args)
        self.assertIn('-r', args)
        self.assertEqual(args[args.index('-r') + 1], '150')

    def test_cairo_true_present_for_every_supported_device(self):
        # All devices gleplot supports (pdf/eps/png/jpg/svg) accept -cairo on
        # the command line -- verified empirically against a real GLE 4.3.10
        # binary; see build_compile_args' Notes for the per-device behaviour
        # that flag actually produces (semi-transparency support for
        # pdf/eps/png/jpg; graceful vs. hard-erroring PostScript-font
        # handling for svg, which is Cairo-backed either way).
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            with self.subTest(fmt=fmt):
                args = build_compile_args(fmt, 'out', 'in.gle', cairo=True)
                self.assertIn('-cairo', args)

    def test_cairo_false_absent_for_every_supported_device(self):
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            with self.subTest(fmt=fmt):
                args = build_compile_args(fmt, 'out', 'in.gle', cairo=False)
                self.assertNotIn('-cairo', args)

    def test_cairo_omitted_defaults_to_false_for_every_supported_device(self):
        # The default (caller passes nothing) must match cairo=False exactly
        # -- an ordinary, no-alpha figure's compile command line is
        # completely unaffected by this feature existing.
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            with self.subTest(fmt=fmt):
                default_args = build_compile_args(fmt, 'out', 'in.gle')
                explicit_false_args = build_compile_args(
                    fmt, 'out', 'in.gle', cairo=False
                )
                self.assertEqual(default_args, explicit_false_args)

    def test_compiler_compile_uses_build_compile_args(self):
        # GLECompiler.compile() must build its command line through the one
        # shared function rather than a parallel inline implementation.
        with mock.patch(
            'gleplot.compiler.build_compile_args', wraps=build_compile_args,
        ) as spy:
            compiler = GLECompiler(gle_path='/explicit/path/to/gle')
            with mock.patch('gleplot.compiler.subprocess.run') as run:
                run.return_value = mock.Mock(returncode=0, stdout='', stderr='')
                with mock.patch('gleplot.compiler.Path.exists', return_value=True):
                    compiler.compile('in.gle', output_format='png', dpi=150)
        spy.assert_called_once()
        _args, kwargs = spy.call_args
        self.assertEqual(kwargs.get('dpi'), 150)
        self.assertEqual(kwargs.get('cairo'), False)

    def test_compiler_compile_passes_cairo_true_through(self):
        # GLECompiler.compile(cairo=True) is the explicit-override path
        # (Track G6): no Figure to auto-detect from, so the caller's choice
        # must reach build_compile_args -- and therefore the actual GLE
        # command line -- unchanged.
        with mock.patch(
            'gleplot.compiler.build_compile_args', wraps=build_compile_args,
        ) as spy:
            compiler = GLECompiler(gle_path='/explicit/path/to/gle')
            with mock.patch('gleplot.compiler.subprocess.run') as run:
                run.return_value = mock.Mock(returncode=0, stdout='', stderr='')
                with mock.patch('gleplot.compiler.Path.exists', return_value=True):
                    compiler.compile('in.gle', output_format='pdf', cairo=True)
        _args, kwargs = spy.call_args
        self.assertEqual(kwargs.get('cairo'), True)
        cmd = run.call_args[0][0]
        self.assertIn('-cairo', cmd)


class TestGLECompileErrorAttributes(unittest.TestCase):
    """Tests for the GLECompileError exception shape."""

    def test_carries_errors_and_raw_output(self):
        errors = [GLEError(file='f.gle', line=1, column=2, message='oops', source_line='src')]
        exc = GLECompileError('failed', errors=errors, raw_output='raw text')
        self.assertEqual(exc.errors, errors)
        self.assertEqual(exc.raw_output, 'raw text')
        self.assertIsInstance(exc, RuntimeError)

    def test_defaults_to_empty_errors(self):
        exc = GLECompileError('failed')
        self.assertEqual(exc.errors, [])
        self.assertEqual(exc.raw_output, '')


if __name__ == '__main__':
    unittest.main()


class TestAnsiColoredOutput(unittest.TestCase):
    """Linux/macOS GLE builds wrap diagnostics in ANSI color escapes."""

    def test_ansi_colored_error_block_parses_with_location(self):
        from gleplot.compiler import parse_gle_errors
        raw = (
            "GLE 4.3.9[bad.gle]-C-R-\n"
            "\x1b[0m\x1b[91m>> bad.gle (3) |let d1 = sin(x frum 0 to 2*pi|\n"
            "\x1b[0m\x1b[91m>>                                           ^\n"
            "\x1b[0m\x1b[91m>> Error: expected closing ')'\x1b[0m\n"
        )
        errors = parse_gle_errors(raw)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].line, 3)
        self.assertEqual(errors[0].message, "expected closing ')'")
        self.assertNotIn("\x1b", errors[0].source_line or "")

    def test_plain_output_unaffected(self):
        from gleplot.compiler import parse_gle_errors
        raw = (
            ">> bad.gle (3) |let d1 = sin(x frum 0|\n"
            ">> Error: expected closing ')'\n"
        )
        errors = parse_gle_errors(raw)
        self.assertEqual(errors[0].line, 3)

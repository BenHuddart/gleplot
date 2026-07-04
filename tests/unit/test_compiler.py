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
    GLECompiler,
    GLECompileError,
    GLEError,
    find_gle,
    parse_gle_errors,
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

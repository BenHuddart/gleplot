"""Unit tests for the GLE compiler wrapper."""

import logging
import subprocess
import sys
import warnings
from pathlib import Path
from unittest import mock

import pytest

import gleplot as glp
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
    remove_generated_intermediates,
    set_gle_path_override,
)

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

# ---------------------------------------------------------------------------
# Fixtures below are *verbatim* stderr/stdout captured from a real
# `gle 4.3.10` run (ANSI colour escapes stripped; see
# ``_ANSI_ESCAPE_RE``/``parse_gle_errors`` docstring), reproducing the two
# defects found in GLEstudio's Phase-6 gate review:
#
# (1) GLE emits a *blank* line where the caret would go for several of the
#     commonest error classes (no column info available), instead of going
#     straight to the ">> Error:" line. The old message-scan loop stopped at
#     that blank line, so the structured error's ``message`` degraded to the
#     literal "GLE error" while the real diagnostic text was dropped.
# (2) When a script has several independent errors, GLE only prints a full
#     ">> file (line) |source|" location block before the *first* one;
#     subsequent errors are bare ">> Error: ..." lines with no location,
#     separated by a blank line. The old parser only ever produced one
#     GLEError per run because it fell out of the outer scanning loop after
#     failing to match a location line for those later blocks.
#
# Each fixture's originating ``.gle`` script is given in its comment so the
# capture can be reproduced with ``gle <script>.gle`` (GLE 4.3.10,
# /usr/local/bin/gle).

# missing_data.gle:
#   size 10 10
#   begin graph
#      data "nope.dat"
#   end graph
MISSING_DATA_FILE_OUTPUT = (
    "GLE 4.3.10[missing_data.gle]-C-R-\n"
    "\n"
    '>> missing_data.gle (3) |data "nope.dat"|\n'
    "\n"
    ">> Error: can't open: 'nope.dat': No such file or directory\n"
    "\n"
    "\n"
    "[missing_data][.eps]\n"
)

# unknown_colour.gle:
#   size 10 10
#   set color "notacolor"
#   amove 1 1
#   box 2 2
UNKNOWN_COLOUR_OUTPUT = (
    "GLE 4.3.10[unknown_colour.gle]-C-R-\n"
    "\n"
    '>> unknown_colour.gle (2) |set color "notacolor"|\n'
    "\n"
    ">> Error: found 'notacolor', but expecting color or fill specification\n"
    "\n"
    "\n"
    "[unknown_colour][.eps]\n"
)

# unclosed.gle:
#   size 10 10
#   begin graph
#      title "test"
UNCLOSED_BLOCK_OUTPUT = (
    "GLE 4.3.10[unclosed.gle]-C\n"
    "\n"
    '>> unclosed.gle (3) |title "test"|\n'
    "\n"
    ">> Error: end of file while in block type 'graph' starting on line 2\n"
    "\n"
    "\n"
    "Errors, GLE aborting.\n"
)

# markup_error.gle:
#   size 10 10
#   amove 1 1
#   write "\setfont{notafont}text"
MARKUP_ERROR_OUTPUT = (
    "GLE 4.3.10[markup_error.gle]-C-R-\n"
    "\n"
    '>> markup_error.gle (3) |write "\\setfont{notafont}text"|\n'
    "\n"
    ">> Error: invalid font name {notafont}, expecting one of:\n"
    ">>        rm, rmi, rmb, rmbi, ss,\n"
    ">>        ssi, ssb, ssbi, texmi, texsy,\n"
    ">>        texex, glemark, texcmb, texcmex, texcmitt,\n"
    ">>        texcmmi, texcmr, texcmss, texcmssb, texcmssi,\n"
    ">>        texcmsy, texcmti, texcmtt, psagb, psagbo,\n"
    ">>        psagd, psagdo, psbd, psbdi, psbli,\n"
    ">>        psc, pscb, pscbo, psco, psh,\n"
    ">>        pshb, pshbo, pshc, pshcb, pshcbo,\n"
    ">>        pshcdo, psho, pshn, pshnb, pshnbo,\n"
    ">>        pshno, psncsb, psncsbi, psncsi, psncsr,\n"
    ">>        pspb, pspbi, pspi, pspr, pssym,\n"
    ">>        pstb, pstbi, psti, pstr, pszcmi,\n"
    ">>        pszd, plba, plcc, plcg, plci,\n"
    ">>        plcr, plcs, pldr, plge, plgg,\n"
    ">>        plgi, plsa, plsg, plsr, plss,\n"
    ">>        plsym1, plsym2, plti, pltr, plba,\n"
    ">>        plsa, tt, tti, ttb, ttbi,\n"
    ">>        psbl, arial8, arial8b, arial8i, arial8bi,\n"
    ">>        cour8, cour8b, cour8i, cour8bi, times8,\n"
    ">>        times8b, times8i, times8bi\n"
    "\n"
    "\n"
    "[markup_error][.eps]\n"
)

# multiple_bad_commands.gle:
#   size 10 10
#   frobnicate 1 2 3
#   amove 1 1
#   zorptastic 4 5 6
#   amove 1 1
#   quuxify 7 8 9
#
# (Also independently reproduced with 20 distinct unknown commands: GLE
# prints 20 ">> Error:" lines, only the first preceded by a location block.)
MULTIPLE_BAD_COMMANDS_OUTPUT = (
    "GLE 4.3.10[multiple_bad_commands.gle]-C\n"
    "\n"
    ">> multiple_bad_commands.gle (2) |frobnicate 1 2 3|\n"
    ">>                 ^\n"
    ">> Error: function 'FROBNICATE' not defined\n"
    "\n"
    ">> Error: function 'ZORPTASTIC' not defined\n"
    "\n"
    ">> Error: function 'QUUXIFY' not defined\n"
    "\n"
    "\n"
    "Errors, GLE aborting.\n"
)


class TestParseGleErrors:
    """Tests for parse_gle_errors()."""

    def test_single_error_with_caret(self):
        errors = parse_gle_errors(SINGLE_ERROR_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert isinstance(err, GLEError)
        assert err.file == "bad.gle"
        assert err.line == 3
        assert err.source_line == "let d1 = sin(x frum 0 to 2*pi"
        # Caret points just past the end of the quoted source (30 chars).
        assert err.column == len(err.source_line)
        assert "expected closing ')'" in err.message

    def test_error_without_caret_line(self):
        errors = parse_gle_errors(NO_CARET_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.file == "bad.gle"
        assert err.line == 5
        assert err.column is None
        assert err.source_line == "some source text"
        assert "something went wrong" in err.message

    def test_multiple_errors(self):
        errors = parse_gle_errors(MULTI_ERROR_OUTPUT)
        assert len(errors) == 2

        first, second = errors
        assert first.line == 2
        assert first.source_line == "x = 1 +"
        assert "expected expression" in first.message

        assert second.line == 7
        assert second.source_line == "y = foo("
        assert "expected closing ')'" in second.message

    def test_unparseable_output_falls_back_to_raw_message(self):
        errors = parse_gle_errors(UNPARSEABLE_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.file is None
        assert err.line is None
        assert err.column is None
        assert err.message == UNPARSEABLE_OUTPUT.strip()

    def test_empty_output_returns_no_errors(self):
        assert parse_gle_errors("") == []
        assert parse_gle_errors("   \n  \n") == []

    # -- Real-GLE regression coverage: blank line stands in for the caret ---

    def test_missing_data_file_message_survives_blank_caret_line(self):
        errors = parse_gle_errors(MISSING_DATA_FILE_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.file == "missing_data.gle"
        assert err.line == 3
        assert err.column is None
        assert err.source_line == 'data "nope.dat"'
        assert err.message == "can't open: 'nope.dat': No such file or directory"
        assert err.message != "GLE error"

    def test_unknown_colour_message_survives_blank_caret_line(self):
        errors = parse_gle_errors(UNKNOWN_COLOUR_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.line == 2
        assert (
            err.message
            == "found 'notacolor', but expecting color or fill specification"
        )

    def test_unclosed_block_message_survives_blank_caret_line(self):
        errors = parse_gle_errors(UNCLOSED_BLOCK_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.line == 3
        assert (
            err.message == "end of file while in block type 'graph' starting on line 2"
        )

    def test_markup_error_multiline_message_survives_blank_caret_line(self):
        errors = parse_gle_errors(MARKUP_ERROR_OUTPUT)
        assert len(errors) == 1
        err = errors[0]
        assert err.line == 3
        assert err.message.startswith("invalid font name {notafont}, expecting one of:")
        # The wrapped list of valid font names (continuation lines with no
        # repeated "Error:" prefix) must still be folded into the message,
        # not truncated at the first line.
        assert "rm, rmi, rmb, rmbi, ss," in err.message
        assert "times8b, times8i, times8bi" in err.message

    # -- Real-GLE regression coverage: multiple errors, one location only ---

    def test_multiple_bad_commands_each_produce_their_own_error(self):
        errors = parse_gle_errors(MULTIPLE_BAD_COMMANDS_OUTPUT)
        assert len(errors) == 3

        first, second, third = errors
        assert first.file == "multiple_bad_commands.gle"
        assert first.line == 2
        assert first.source_line == "frobnicate 1 2 3"
        assert first.message == "function 'FROBNICATE' not defined"

        # GLE prints no location block for the second/third errors; the
        # parser must still surface them as distinct GLEErrors rather than
        # silently dropping them or folding them into the first.
        assert second.file is None
        assert second.line is None
        assert second.message == "function 'ZORPTASTIC' not defined"

        assert third.file is None
        assert third.line is None
        assert third.message == "function 'QUUXIFY' not defined"

    def test_column_matches_caret_relative_to_source(self):
        # Caret directly under the 'x' at index 4 of the quoted source.
        output = (
            ">> file.gle (1) |abcd efgh|\n"
            ">>                   ^\n"
            ">> Error: bad token\n"
        )
        errors = parse_gle_errors(output)
        assert len(errors) == 1
        assert errors[0].source_line == "abcd efgh"
        # pipe is at index 16 ('>> file.gle (1) |'); caret at index 21
        # => column = 21 - 16 - 1 = 4
        assert errors[0].column == 4


class TestFindGle:
    """Tests for find_gle() discovery order."""

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        # find_gle now consults a process-global override first; ensure a clean
        # slate so these auto-detect tests aren't affected by an earlier one.
        set_gle_path_override(None)
        yield
        set_gle_path_override(None)

    def test_env_var_takes_priority(self):
        with mock.patch.dict("os.environ", {"GLE_PATH": str(Path(__file__))}):
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/should/not/be/used"
            ):
                assert find_gle() == str(Path(__file__))

    def test_env_var_ignored_if_nonexistent(self):
        with mock.patch.dict("os.environ", {"GLE_PATH": "C:/does/not/exist/gle.exe"}):
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/bin/gle"
            ):
                assert find_gle() == "/usr/bin/gle"

    def test_env_var_nonexistent_emits_warning(self):
        with mock.patch.dict("os.environ", {"GLE_PATH": "C:/does/not/exist/gle.exe"}):
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/bin/gle"
            ):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    find_gle()
                assert any(
                    "GLE_PATH" in str(w.message) for w in caught
                ), f"expected a warning mentioning GLE_PATH, got: {[str(w.message) for w in caught]}"

    def test_which_used_when_no_env_var(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/local/bin/gle"
            ):
                assert find_gle() == "/usr/local/bin/gle"

    def test_falls_back_to_well_known_paths(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch("gleplot.compiler.shutil.which", return_value=None):
                with mock.patch("gleplot.compiler.sys.platform", "win32"):
                    # Well-known entries are now glob patterns expanded against
                    # the real filesystem; make each pattern "match itself" so
                    # the first (literal) win32 path is returned regardless of
                    # the host OS running the test (e.g. Linux CI).
                    with mock.patch(
                        "gleplot.compiler.glob.glob",
                        side_effect=lambda pat, recursive=False: [pat],
                    ):
                        with mock.patch(
                            "gleplot.compiler.Path.exists", return_value=True
                        ):
                            result = find_gle()
                            assert result == r"C:\Program Files\GLE\bin\gle.exe"

    def test_returns_none_when_nothing_found(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch("gleplot.compiler.shutil.which", return_value=None):
                with mock.patch("gleplot.compiler.Path.exists", return_value=False):
                    assert find_gle() is None

    def test_explicit_gle_path_arg_bypasses_discovery(self):
        # GLECompiler(gle_path=...) should not need to call find_gle() at all.
        with mock.patch("gleplot.compiler.find_gle") as mock_find:
            compiler = GLECompiler(gle_path="/explicit/path/to/gle")
            assert compiler.gle_path == "/explicit/path/to/gle"
            mock_find.assert_not_called()


class TestGlePathOverride:
    """Tests for the explicit override consulted first by find_gle()."""

    @pytest.fixture(autouse=True)
    def _teardown(self):
        yield
        set_gle_path_override(None)

    def test_override_wins_over_env_and_path(self):
        # The override represents an explicit in-app choice and must outrank
        # GLE_PATH and PATH (an existing file is required).
        override = str(Path(__file__))
        set_gle_path_override(override)
        with mock.patch.dict("os.environ", {"GLE_PATH": "/some/other/gle"}):
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/on/path/gle"
            ):
                assert find_gle() == override

    def test_missing_override_warns_and_falls_through(self):
        set_gle_path_override("C:/does/not/exist/gle.exe")
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/bin/gle"
            ):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    result = find_gle()
                assert result == "/usr/bin/gle"
                assert any("does not exist" in str(w.message) for w in caught), (
                    f"expected a fall-through warning, got: "
                    f"{[str(w.message) for w in caught]}"
                )

    def test_empty_string_clears_override(self):
        set_gle_path_override(str(Path(__file__)))
        set_gle_path_override("")  # normalized to "unset"
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/bin/gle"
            ):
                assert find_gle() == "/usr/bin/gle"

    def test_autodetect_ignores_override(self):
        # autodetect_gle() is what the GUI's "Auto-detect" button calls; it must
        # bypass whatever the user has currently pinned.
        set_gle_path_override(str(Path(__file__)))
        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch(
                "gleplot.compiler.shutil.which", return_value="/usr/bin/gle"
            ):
                assert autodetect_gle() == "/usr/bin/gle"


class TestRobustWellKnownDetection:
    """The well-known fallback expands glob patterns for versioned installs."""

    @pytest.fixture(autouse=True)
    def _teardown(self):
        yield
        set_gle_path_override(None)

    def test_glob_matches_versioned_install_dir(self):
        # A GLE installed under a versioned dir (e.g. "GLE-4.3.9") is only
        # reachable via the glob patterns, not the two literal paths.
        versioned = r"C:\Program Files\GLE-4.3.9\bin\gle.exe"

        def fake_glob(pattern, recursive=False):
            # Only the wildcard pattern matches the versioned install.
            if "*" in pattern and pattern.startswith(r"C:\Program Files"):
                return [versioned]
            return []

        with mock.patch.dict("os.environ", {}, clear=False):
            import os as _os

            _os.environ.pop("GLE_PATH", None)
            with mock.patch("gleplot.compiler.shutil.which", return_value=None):
                with mock.patch("gleplot.compiler.sys.platform", "win32"):
                    with mock.patch(
                        "gleplot.compiler.glob.glob", side_effect=fake_glob
                    ):
                        with mock.patch(
                            "gleplot.compiler.Path.exists", return_value=True
                        ):
                            assert find_gle() == versioned


@pytest.mark.gle
class TestCompileIntegration:
    """Integration-style tests that invoke the real installed GLE binary."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.tempdir = tmp_path
        self.compiler = GLECompiler()

    def _write_good_gle(self, directory: Path, name: str = "good.gle") -> Path:
        gle_file = directory / name
        gle_file.write_text(
            "size 8 6\n" "begin graph\n" '   title "Test"\n' "end graph\n"
        )
        return gle_file

    def _write_bad_gle(self, directory: Path, name: str = "bad.gle") -> Path:
        gle_file = directory / name
        gle_file.write_text(
            "size 8 6\n" "begin graph\n" "let d1 = sin(x frum 0 to 2*pi\n" "end graph\n"
        )
        return gle_file

    def test_compile_pdf_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="pdf")
        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.stat().st_size > 0

    def test_compile_png_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="png", dpi=150)
        assert result.exists()
        assert result.suffix == ".png"

    def test_compile_jpg_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="jpg", dpi=150)
        assert result.exists()
        assert result.suffix == ".jpg"

    def test_compile_eps_happy_path(self):
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="eps")
        assert result.exists()
        assert result.suffix == ".eps"

    def test_compile_error_path_raises_gle_compile_error(self):
        gle_file = self._write_bad_gle(self.tempdir)
        with pytest.raises(GLECompileError) as ctx:
            self.compiler.compile(str(gle_file), output_format="pdf")

        exc = ctx.value
        assert exc.errors
        assert len(exc.raw_output) > 0
        first = exc.errors[0]
        assert first.line == 3
        assert "expected closing ')'" in first.message

        # No output file should have been produced.
        output_path = gle_file.with_suffix(".pdf")
        assert not output_path.exists()

    def test_compile_missing_include_names_the_file_and_the_library(self):
        gle_file = self.tempdir / "inc.gle"
        gle_file.write_text('size 8 6\ninclude "no_such_routines.gle"\n')
        with pytest.raises(GLECompileError) as ctx:
            self.compiler.compile(str(gle_file), output_format="pdf")

        message = str(ctx.value)
        assert "'no_such_routines.gle'" in message
        assert "include library" in message
        assert "getting_started.html#gle-s-include-library" in message
        assert ctx.value.errors[0].line == 2

    def test_compile_missing_input_raises_file_not_found(self):
        missing = self.tempdir / "does_not_exist.gle"
        with pytest.raises(FileNotFoundError):
            self.compiler.compile(str(missing), output_format="pdf")

    def test_compile_handles_paths_with_spaces(self):
        spacey_dir = self.tempdir / "dir with spaces"
        spacey_dir.mkdir()
        gle_file = self._write_good_gle(spacey_dir, name="my file.gle")

        result = self.compiler.compile(str(gle_file), output_format="png", dpi=150)
        assert result.exists()
        assert result.name == "my file.png"

    def test_compile_does_not_leave_stray_eps(self):
        # GLE 4.3.3 with -o does not leave a stray .eps for non-eps output
        # formats, so a plain non-eps compile should not produce one.
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="png", dpi=150)
        assert result.exists()

        stray_eps = gle_file.with_suffix(".eps")
        assert not stray_eps.exists()

    def test_compile_timeout(self):
        gle_file = self._write_good_gle(self.tempdir)
        with mock.patch(
            "gleplot.compiler.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gle", timeout=0.001),
        ):
            with pytest.raises(GLECompileError) as ctx:
                self.compiler.compile(str(gle_file), output_format="pdf", timeout=0.001)
            assert "timed out" in str(ctx.value)

    def test_compile_svg_happy_path(self):
        # SVG emits a benign cairo font warning on stderr but exits 0 and
        # produces a valid file with the installed GLE 4.3.3.
        gle_file = self._write_good_gle(self.tempdir)
        result = self.compiler.compile(str(gle_file), output_format="svg", dpi=150)
        assert result.exists()
        assert result.suffix == ".svg"


class TestRemoveGeneratedIntermediates:
    """G8: exact-name-only cleanup of contour/fitz engine intermediates.

    Pure filesystem tests -- no GLE binary needed (the compiled-output
    version of this, exercised end-to-end through ``Figure.savefig``, is
    ``tests/integration/test_intermediate_cleanup.py``).
    """

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.tempdir = tmp_path

    def _touch(self, *names: str) -> None:
        for name in names:
            (self.tempdir / name).write_text("x\n")

    def test_removes_only_listed_names_that_exist(self):
        self._touch(
            "t_contour1-cdata.dat",
            "t_contour1-clabels.dat",
            "t_contour1-cvalues.dat",
            "t_contour1.z",  # not in the list: gleplot's own sidecar
        )
        removed = remove_generated_intermediates(
            self.tempdir,
            [
                "t_contour1-cdata.dat",
                "t_contour1-clabels.dat",
                "t_contour1-cvalues.dat",
                # No -clabels for this one (e.g. clabel=False): listed but
                # never written -- must be silently skipped, not an error.
                "t_contour2-cdata.dat",
            ],
        )
        remaining = {p.name for p in self.tempdir.iterdir()}
        assert remaining == {"t_contour1.z"}
        assert {p.name for p in removed} == {
            "t_contour1-cdata.dat",
            "t_contour1-clabels.dat",
            "t_contour1-cvalues.dat",
        }

    def test_similar_but_different_name_is_not_removed(self):
        self._touch("userdata_contour1-cdata.dat", "t_contour1-cdata.dat.bak")
        remove_generated_intermediates(
            self.tempdir, ["t_contour1-cdata.dat", "t_contour1-clabels.dat"]
        )
        remaining = {p.name for p in self.tempdir.iterdir()}
        assert remaining == {"userdata_contour1-cdata.dat", "t_contour1-cdata.dat.bak"}

    def test_rejects_names_with_path_separators(self):
        # Defence in depth: even a malformed candidate name can never escape
        # `directory` -- nothing outside it is touched.
        outside = self.tempdir.parent / "escaped-cdata.dat"
        outside.write_text("do not touch\n")
        try:
            remove_generated_intermediates(
                self.tempdir, ["../escaped-cdata.dat", "sub/dir-cdata.dat"]
            )
            assert outside.exists()
        finally:
            outside.unlink(missing_ok=True)

    def test_empty_filenames_is_a_noop(self):
        self._touch("unrelated.dat")
        removed = remove_generated_intermediates(self.tempdir, [])
        assert removed == []
        assert (self.tempdir / "unrelated.dat").exists()

    def test_duplicate_names_removed_once(self):
        self._touch("t_contour1-cdata.dat")
        removed = remove_generated_intermediates(
            self.tempdir, ["t_contour1-cdata.dat", "t_contour1-cdata.dat"]
        )
        assert len(removed) == 1


class TestBuildCompileArgs:
    """Tests for build_compile_args(): the single, unified device-flag
    builder (Track G3). Previously GLECompiler.compile() built an uppercase
    ``-d PDF`` with ``-r`` only for raster formats, while other call sites
    built a lowercase ``-d svg`` with ``-r`` unconditional (including for
    vector formats, where GLE just ignores it). This is the one place that
    decides the shape now.
    """

    def test_all_supported_formats_produce_lowercase_device_flag(self):
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            args = build_compile_args(fmt, "out", "in.gle")
            assert args[0] == "-d"
            assert args[1] == fmt.lower()

    def test_uppercase_and_mixed_case_input_normalized_to_lowercase(self):
        for given in ("PDF", "Pdf", "pDf"):
            args = build_compile_args(given, "out", "in.gle")
            assert args[1] == "pdf"

    def test_raster_formats_include_dpi_flag(self):
        for fmt in RASTER_COMPILE_FORMATS:
            args = build_compile_args(fmt, "out", "in.gle", dpi=150)
            assert "-r" in args
            assert args[args.index("-r") + 1] == "150"

    def test_vector_formats_omit_dpi_flag_even_when_dpi_given(self):
        vector_formats = SUPPORTED_COMPILE_FORMATS - RASTER_COMPILE_FORMATS
        assert vector_formats  # sanity: pdf/eps/svg are vector
        for fmt in vector_formats:
            args = build_compile_args(fmt, "out", "in.gle", dpi=300)
            assert "-r" not in args

    def test_raster_format_without_dpi_omits_dpi_flag(self):
        # dpi is optional; when the caller doesn't have one to give (or
        # doesn't care), -r must not appear with a garbage value.
        args = build_compile_args("png", "out", "in.gle")
        assert "-r" not in args

    def test_dpi_is_coerced_to_int_string(self):
        args = build_compile_args("png", "out", "in.gle", dpi=150.0)
        assert args[args.index("-r") + 1] == "150"

    def test_output_and_input_paths_appear_last_in_order(self):
        args = build_compile_args("pdf", "result.pdf", "script.gle")
        assert args[-3:] == ["-o", "result.pdf", "script.gle"]

    def test_output_before_input_with_o_flag(self):
        args = build_compile_args("pdf", "result.pdf", "script.gle")
        o_index = args.index("-o")
        assert args[o_index + 1] == "result.pdf"
        assert args[o_index + 2] == "script.gle"

    def test_accepts_path_objects(self):
        args = build_compile_args("pdf", Path("out.pdf"), Path("in.gle"))
        assert "out.pdf" in args
        assert "in.gle" in args

    def test_unsupported_format_raises_value_error(self):
        with pytest.raises(ValueError):
            build_compile_args("bogus", "out", "in.gle")

    # -- cairo: flag construction (Track G6). Deciding *when* to enable it
    #    (figures using alpha) lives in Figure.requires_cairo() /
    #    Figure.savefig(), not here -- this builder only ever does what its
    #    caller tells it, for every device gleplot supports.
    def test_cairo_false_by_default_omits_flag(self):
        args = build_compile_args("pdf", "out", "in.gle")
        assert "-cairo" not in args

    def test_cairo_true_appends_flag_directly_after_device(self):
        args = build_compile_args("pdf", "out", "in.gle", cairo=True)
        assert "-cairo" in args
        # Placed right after -d <fmt>, before -o/-r, matching GLE's "options
        # before filename" convention used throughout this module.
        assert args[:3] == ["-d", "pdf", "-cairo"]

    def test_cairo_and_raster_dpi_compose(self):
        args = build_compile_args("png", "out", "in.gle", dpi=150, cairo=True)
        assert "-cairo" in args
        assert "-r" in args
        assert args[args.index("-r") + 1] == "150"

    def test_cairo_true_present_for_every_supported_device(self):
        # All devices gleplot supports (pdf/eps/png/jpg/svg) accept -cairo on
        # the command line -- verified empirically against a real GLE 4.3.10
        # binary; see build_compile_args' Notes for the per-device behaviour
        # that flag actually produces (semi-transparency support for
        # pdf/eps/png/jpg; graceful vs. hard-erroring PostScript-font
        # handling for svg, which is Cairo-backed either way).
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            args = build_compile_args(fmt, "out", "in.gle", cairo=True)
            assert "-cairo" in args

    def test_cairo_false_absent_for_every_supported_device(self):
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            args = build_compile_args(fmt, "out", "in.gle", cairo=False)
            assert "-cairo" not in args

    def test_cairo_omitted_defaults_to_false_for_every_supported_device(self):
        # The default (caller passes nothing) must match cairo=False exactly
        # -- an ordinary, no-alpha figure's compile command line is
        # completely unaffected by this feature existing.
        for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
            default_args = build_compile_args(fmt, "out", "in.gle")
            explicit_false_args = build_compile_args(fmt, "out", "in.gle", cairo=False)
            assert default_args == explicit_false_args

    def test_compiler_compile_uses_build_compile_args(self):
        # GLECompiler.compile() must build its command line through the one
        # shared function rather than a parallel inline implementation.
        with mock.patch(
            "gleplot.compiler.build_compile_args",
            wraps=build_compile_args,
        ) as spy:
            compiler = GLECompiler(gle_path="/explicit/path/to/gle")
            with mock.patch("gleplot.compiler.subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                with mock.patch("gleplot.compiler.Path.exists", return_value=True):
                    compiler.compile("in.gle", output_format="png", dpi=150)
        spy.assert_called_once()
        _args, kwargs = spy.call_args
        assert kwargs.get("dpi") == 150
        assert kwargs.get("cairo") is False

    def test_compiler_compile_passes_cairo_true_through(self):
        # GLECompiler.compile(cairo=True) is the explicit-override path
        # (Track G6): no Figure to auto-detect from, so the caller's choice
        # must reach build_compile_args -- and therefore the actual GLE
        # command line -- unchanged.
        with mock.patch(
            "gleplot.compiler.build_compile_args",
            wraps=build_compile_args,
        ) as spy:
            compiler = GLECompiler(gle_path="/explicit/path/to/gle")
            with mock.patch("gleplot.compiler.subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                with mock.patch("gleplot.compiler.Path.exists", return_value=True):
                    compiler.compile("in.gle", output_format="pdf", cairo=True)
        _args, kwargs = spy.call_args
        assert kwargs.get("cairo") is True
        cmd = run.call_args[0][0]
        assert "-cairo" in cmd


def test_grayscale_adds_nocolor_on_every_format():
    for fmt in sorted(SUPPORTED_COMPILE_FORMATS):
        assert "-nocolor" in build_compile_args(fmt, "out", "in.gle", grayscale=True)
        assert "-nocolor" not in build_compile_args(fmt, "out", "in.gle")


def test_transparent_adds_the_flag_only_for_png():
    for fmt in sorted(SUPPORTED_COMPILE_FORMATS - {"jpg"}):
        args = build_compile_args(fmt, "out", "in.gle", transparent=True)
        assert ("-transparent" in args) == (fmt == "png")


def test_output_options_come_before_the_output_and_input_paths():
    args = build_compile_args(
        "png", "out", "in.gle", dpi=150, cairo=True, transparent=True, grayscale=True
    )
    assert args == [
        "-d",
        "png",
        "-cairo",
        "-nocolor",
        "-transparent",
        "-r",
        "150",
        "-o",
        "out",
        "in.gle",
    ]


def _run_compile(**kwargs):
    compiler = GLECompiler(gle_path="/explicit/path/to/gle")
    with mock.patch("gleplot.compiler.subprocess.run") as run:
        run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("gleplot.compiler.Path.exists", return_value=True):
            compiler.compile("in.gle", **kwargs)
    return run.call_args[0][0]


def test_compile_passes_transparent_and_grayscale_to_gle():
    cmd = _run_compile(
        output_format="png", transparent=True, grayscale=True, cairo=True
    )
    assert "-transparent" in cmd
    assert "-nocolor" in cmd


def test_compile_warns_that_a_jpeg_cannot_be_transparent():
    with pytest.warns(UserWarning, match="save as PNG") as record:
        cmd = _run_compile(output_format="jpg", transparent=True)
    assert record[0].filename == __file__
    assert "-transparent" not in cmd


def test_compile_warns_that_a_grayscale_png_needs_cairo_to_stay_transparent():
    with pytest.warns(UserWarning, match="pass cairo=True"):
        _run_compile(output_format="png", transparent=True, grayscale=True)


def _line_figure():
    fig = glp.figure()
    fig.add_subplot(111).plot([1, 2], [1, 2])
    return fig


def test_savefig_passes_transparent_and_grayscale_to_the_compiler(tmp_path):
    fig = _line_figure()
    fig.compiler = mock.Mock()
    fig.savefig(str(tmp_path / "a.png"))
    _args, kwargs = fig.compiler.compile.call_args
    assert (kwargs["transparent"], kwargs["grayscale"]) == (False, False)
    fig.savefig(str(tmp_path / "a.png"), transparent=True, grayscale=True)
    _args, kwargs = fig.compiler.compile.call_args
    assert (kwargs["transparent"], kwargs["grayscale"]) == (True, True)


def _tex_compile(script, *args, **kwargs):
    """Write the ``.gle/`` LaTeX cache a real GLE compile of a TeX figure does."""
    stem = Path(script).stem
    cache = Path(script).parent / ".gle"
    (cache / stem).mkdir(parents=True, exist_ok=True)
    (cache / "texpreamble.tex").write_text("new")
    (cache / stem / f"{stem}_tex.tex").write_text("new")


def _tex_figure_with_fake_compiler():
    fig = _line_figure()
    fig.tex(2, 2, r"\textbf{Note}")
    fig.compiler = mock.Mock()
    fig.compiler.compile.side_effect = _tex_compile
    return fig


def test_savefig_removes_the_tex_cache_it_created(tmp_path):
    _tex_figure_with_fake_compiler().savefig(str(tmp_path / "f.pdf"))
    assert not (tmp_path / ".gle").exists()


def test_savefig_keeps_tex_cache_entries_that_were_already_there(tmp_path):
    cache = tmp_path / ".gle"
    (cache / "other").mkdir(parents=True)
    (cache / "texpreamble.tex").write_text("old")
    _tex_figure_with_fake_compiler().savefig(str(tmp_path / "f.pdf"))
    assert sorted(p.name for p in cache.iterdir()) == ["other", "texpreamble.tex"]


def test_savefig_removes_its_own_tex_folder_left_by_an_earlier_save(tmp_path):
    fig = _tex_figure_with_fake_compiler()
    fig.savefig(str(tmp_path / "f.pdf"), keep_intermediates=True)
    fig.savefig(str(tmp_path / "f.pdf"))
    assert sorted(p.name for p in (tmp_path / ".gle").iterdir()) == ["texpreamble.tex"]


def test_savefig_keeps_new_preamble_while_another_script_uses_the_cache(tmp_path):
    fig = _tex_figure_with_fake_compiler()

    def concurrent(script, *args, **kwargs):
        _tex_compile(script)
        (Path(script).parent / ".gle" / "other").mkdir()

    fig.compiler.compile.side_effect = concurrent
    fig.savefig(str(tmp_path / "f.pdf"))
    assert sorted(p.name for p in (tmp_path / ".gle").iterdir()) == [
        "other",
        "texpreamble.tex",
    ]


def test_savefig_keep_intermediates_keeps_the_tex_cache(tmp_path):
    fig = _tex_figure_with_fake_compiler()
    fig.savefig(str(tmp_path / "f.pdf"), keep_intermediates=True)
    assert (tmp_path / ".gle" / "f" / "f_tex.tex").exists()


def test_failed_compile_keeps_the_tex_cache(tmp_path):
    fig = _tex_figure_with_fake_compiler()

    def fail(script, *args, **kwargs):
        _tex_compile(script)
        raise GLECompileError("LaTeX failed", errors=[], raw_output="")

    fig.compiler.compile.side_effect = fail
    with pytest.raises(GLECompileError):
        fig.savefig(str(tmp_path / "f.pdf"))
    assert (tmp_path / ".gle" / "texpreamble.tex").exists()


@pytest.mark.parametrize(
    "name, value",
    [
        ("bbox_inches", "tight"),
        ("pad_inches", 0.2),
        ("facecolor", "white"),
        ("facecolor", (1, 1, 1)),
        ("edgecolor", "red"),
    ],
)
def test_savefig_warns_on_matplotlib_page_keywords(tmp_path, name, value):
    fig = _line_figure()
    with pytest.warns(UserWarning, match=f"savefig\\({name}=") as record:
        fig.savefig(str(tmp_path / "a.gle"), **{name: value})
    assert record[0].filename == __file__


def test_savefig_page_keyword_defaults_do_not_warn(tmp_path):
    fig = _line_figure()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig.savefig(
            str(tmp_path / "a.gle"),
            bbox_inches=None,
            pad_inches=None,
            facecolor="auto",
            edgecolor="auto",
        )


@pytest.mark.parametrize("save", ["savefig", "savefig_gle"])
def test_savefig_warns_on_keywords_it_ignores(tmp_path, save):
    fig = _line_figure()
    with pytest.warns(UserWarning) as record:
        getattr(fig, save)(
            str(tmp_path / "a.gle"), metadata={"Title": "t"}, transparant=True
        )
    assert [str(w.message) for w in record] == [
        f"{save}() ignores unsupported keyword(s): metadata, transparant."
    ]
    assert record[0].filename == __file__
    assert (tmp_path / "a.gle").exists()


def test_module_savefig_warns_on_keywords_it_ignores(tmp_path):
    glp.close()
    glp.plot([0, 1], [0, 1])
    with pytest.warns(UserWarning, match=r"savefig\(\) ignores .*: orientation") as rec:
        glp.savefig(str(tmp_path / "a.gle"), orientation="landscape")
    assert rec[0].filename == __file__
    glp.close()


@pytest.mark.parametrize("name", ["transparent", "grayscale"])
def test_savefig_warns_that_compile_options_need_a_compile(tmp_path, name):
    with pytest.warns(UserWarning, match=f"savefig\\({name}=True\\) has no effect"):
        _line_figure().savefig(str(tmp_path / "a.gle"), **{name: True})


@pytest.mark.parametrize(
    "suffix, warns", [("pdf", True), ("svg", True), ("png", False)]
)
def test_savefig_warns_that_vector_heatmaps_stay_in_colour(tmp_path, suffix, warns):
    fig = glp.figure()
    fig.add_subplot(111).imshow([[0.0, 1.0], [1.0, 0.0]])
    fig.compiler = mock.Mock()
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        fig.savefig(str(tmp_path / f"a.{suffix}"), grayscale=True)
    messages = [str(w.message) for w in record if "heatmap" in str(w.message)]
    assert bool(messages) == warns


class TestGLECompileErrorAttributes:
    """Tests for the GLECompileError exception shape."""

    def test_carries_errors_and_raw_output(self):
        errors = [
            GLEError(file="f.gle", line=1, column=2, message="oops", source_line="src")
        ]
        exc = GLECompileError("failed", errors=errors, raw_output="raw text")
        assert exc.errors == errors
        assert exc.raw_output == "raw text"
        assert isinstance(exc, RuntimeError)

    def test_defaults_to_empty_errors(self):
        exc = GLECompileError("failed")
        assert exc.errors == []
        assert exc.raw_output == ""


class TestAnsiColoredOutput:
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
        assert len(errors) == 1
        assert errors[0].line == 3
        assert errors[0].message == "expected closing ')'"
        assert "\x1b" not in (errors[0].source_line or "")

    def test_plain_output_unaffected(self):
        from gleplot.compiler import parse_gle_errors

        raw = (
            ">> bad.gle (3) |let d1 = sin(x frum 0|\n"
            ">> Error: expected closing ')'\n"
        )
        errors = parse_gle_errors(raw)
        assert errors[0].line == 3


def _fake_gle_run(returncode):
    return mock.Mock(returncode=returncode, stdout="gle stdout", stderr="gle stderr")


def test_failed_compile_reports_output_only_in_the_exception(capsys):
    compiler = GLECompiler(gle_path="/explicit/path/to/gle")
    with mock.patch("gleplot.compiler.subprocess.run", return_value=_fake_gle_run(1)):
        with mock.patch("gleplot.compiler.Path.exists", return_value=True):
            with pytest.raises(GLECompileError) as excinfo:
                compiler.compile("in.gle")

    assert "gle stdout" in excinfo.value.raw_output
    assert "gle stderr" in excinfo.value.raw_output
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("verbose", [False, True])
def test_compile_output_goes_to_the_logger_only_when_verbose(verbose, capsys, caplog):
    compiler = GLECompiler(gle_path="/explicit/path/to/gle")
    caplog.set_level(logging.INFO, logger="gleplot.compiler")
    with mock.patch("gleplot.compiler.subprocess.run", return_value=_fake_gle_run(0)):
        with mock.patch("gleplot.compiler.Path.exists", return_value=True):
            compiler.compile("in.gle", verbose=verbose)

    logged = [r.getMessage() for r in caplog.records if r.name == "gleplot.compiler"]
    assert logged == (["gle stdout\ngle stderr"] if verbose else [])
    assert capsys.readouterr() == ("", "")


def test_gle_output_is_read_as_utf8_with_bad_bytes_replaced():
    # A UTF-8 echo of the script, then 0x81: invalid UTF-8, undefined cp1252.
    real_run = subprocess.run
    emit = (
        "import sys; sys.stderr.buffer.write(b'\\xc3\\x85 bad \\x81 byte'); "
        "sys.exit(1)"
    )

    def fake_gle(cmd, **kwargs):
        return real_run([sys.executable, "-c", emit], **kwargs)

    compiler = GLECompiler(gle_path="/explicit/path/to/gle")
    with mock.patch("gleplot.compiler.subprocess.run", side_effect=fake_gle):
        with mock.patch("gleplot.compiler.Path.exists", return_value=True):
            with pytest.raises(GLECompileError) as excinfo:
                compiler.compile("in.gle")

    assert "\u00c5 bad \ufffd byte" in excinfo.value.raw_output

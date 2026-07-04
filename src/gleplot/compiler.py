"""GLE compiler wrapper for gleplot."""

import os
import re
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal


#: Well-known install locations to probe, keyed by `sys.platform` prefix.
_WELL_KNOWN_PATHS = {
    'win32': [
        r'C:\Program Files\GLE\bin\gle.exe',
        r'C:\Program Files (x86)\GLE\bin\gle.exe',
    ],
    'default': [
        '/usr/local/bin/gle',
        '/opt/homebrew/bin/gle',
        '/usr/bin/gle',
    ],
}

#: Output formats (GLE ``-d`` device names, lowercased) that
#: :meth:`GLECompiler.compile` accepts.
SUPPORTED_COMPILE_FORMATS = frozenset({'pdf', 'png', 'eps', 'jpg', 'svg'})

#: Mapping from a file suffix (including the leading dot, lowercased) to the
#: GLE compile format that should be used to produce it. Kept alongside
#: :data:`SUPPORTED_COMPILE_FORMATS` so callers (e.g. ``Figure.savefig``) that
#: auto-detect a format from a filename can't drift out of sync with what the
#: compiler actually supports. ``.jpeg`` maps to ``jpg`` since GLE only
#: recognizes ``jpg`` as a device name.
SUFFIX_TO_COMPILE_FORMAT = {
    f'.{fmt}': fmt for fmt in SUPPORTED_COMPILE_FORMATS
}
SUFFIX_TO_COMPILE_FORMAT['.jpeg'] = 'jpg'


def find_gle() -> Optional[str]:
    """
    Locate the GLE executable on this system.

    Discovery precedence (first match wins):

    1. ``GLE_PATH`` environment variable -- the supported way to pin a
       specific GLE binary (e.g. to select among several installed versions,
       or to point at a non-standard install location). If ``GLE_PATH`` is
       set but does not point at an existing path, a :class:`UserWarning` is
       emitted and discovery falls through to the next step rather than
       silently ignoring the misconfiguration.
    2. ``shutil.which("gle")`` (searches ``PATH``, respecting ``PATHEXT`` on
       Windows)
    3. Platform-specific well-known install locations

    Returns
    -------
    str, optional
        Path to the GLE executable, or None if it could not be found.
    """
    env_path = os.environ.get('GLE_PATH')
    if env_path:
        if Path(env_path).exists():
            return env_path
        warnings.warn(
            f"GLE_PATH is set to {env_path!r} but that path does not exist; "
            "falling back to PATH / well-known install locations.",
            stacklevel=2,
        )

    which_path = shutil.which('gle')
    if which_path:
        return which_path

    well_known = _WELL_KNOWN_PATHS.get(sys.platform, _WELL_KNOWN_PATHS['default'])
    for path in well_known:
        if Path(path).exists():
            return path

    return None


@dataclass
class GLEError:
    """A single structured error parsed from GLE compiler output."""

    file: Optional[str]
    line: Optional[int]
    column: Optional[int]
    message: str
    source_line: Optional[str] = None


class GLECompileError(RuntimeError):
    """Raised when GLE compilation fails.

    Parameters
    ----------
    message : str
        Human-readable summary of the failure.
    errors : list[GLEError]
        Structured errors parsed from the compiler output.
    raw_output : str
        The raw combined output produced by the GLE process.
    """

    def __init__(self, message: str, errors: Optional[list] = None, raw_output: str = ''):
        super().__init__(message)
        self.errors: list = errors if errors is not None else []
        self.raw_output = raw_output


# Matches the location/source line, e.g.:
#   >> bad.gle (3) |let d1 = sin(x frum 0 to 2*pi|
_LOCATION_RE = re.compile(
    r'^>>\s*(?P<file>.+?)\s*\((?P<line>\d+)\)\s*\|(?P<source>.*)\|\s*$'
)

# Matches the caret line, e.g.:
#   >>                                           ^
# The caret's absolute column position (from the start of the line) is used,
# together with the position of the opening '|' on the location line, to
# compute the column within the quoted source text.
_CARET_RE = re.compile(r'^>>\s*\^\s*$')

# Matches the message line, e.g.:
#   >> Error: expected closing ')'
_MESSAGE_RE = re.compile(r'^>>\s*(?:Error:\s*)?(?P<message>.+)$')


def parse_gle_errors(output: str) -> list:
    """
    Parse structured errors out of raw GLE compiler output.

    GLE reports errors in blocks that look like::

        >> bad.gle (3) |let d1 = sin(x frum 0 to 2*pi|
        >>                                           ^
        >> Error: expected closing ')'

    Multiple such blocks may appear in one run. The caret line is optional
    (some errors only report file/line/message). If the output cannot be
    parsed as one or more GLE error blocks, a single :class:`GLEError` is
    returned with ``message`` set to the raw output.

    Parameters
    ----------
    output : str
        Combined stdout/stderr text produced by the GLE process.

    Returns
    -------
    list of GLEError
        Structured errors found in the output. Always non-empty for
        non-empty input.
    """
    if not output or not output.strip():
        return []

    lines = output.splitlines()
    errors = []

    i = 0
    n = len(lines)
    while i < n:
        loc_match = _LOCATION_RE.match(lines[i])
        if not loc_match:
            i += 1
            continue

        file = loc_match.group('file')
        line_no = int(loc_match.group('line'))
        source_line = loc_match.group('source')
        # Position of the opening '|' delimiter on the location line, used
        # below to translate the caret's absolute column into a column
        # relative to the start of the quoted source text.
        pipe_pos = lines[i].index('|')
        column = None
        i += 1

        # Optional caret line.
        if i < n:
            caret_match = _CARET_RE.match(lines[i])
            if caret_match:
                caret_pos = lines[i].index('^')
                column = max(caret_pos - pipe_pos - 1, 0)
                i += 1

        # Message line(s): collect subsequent ">> " lines that aren't a new
        # location block, up to (but not including) a blank line or EOF.
        message_parts = []
        while i < n and lines[i].startswith('>>'):
            msg_match = _MESSAGE_RE.match(lines[i])
            if msg_match:
                text = msg_match.group('message').strip()
                if text:
                    message_parts.append(text)
            i += 1

        message = ' '.join(message_parts) if message_parts else 'GLE error'

        errors.append(GLEError(
            file=file,
            line=line_no,
            column=column,
            message=message,
            source_line=source_line,
        ))

    if not errors:
        # Unparseable output: fall back to a single error carrying the raw text.
        errors.append(GLEError(
            file=None,
            line=None,
            column=None,
            message=output.strip(),
            source_line=None,
        ))

    return errors


class GLECompiler:
    """Wrapper for GLE command-line compiler.

    When ``gle_path`` is not given explicitly, the GLE executable is located
    via :func:`find_gle`, which searches (in order) the ``GLE_PATH``
    environment variable, ``PATH`` (via :func:`shutil.which`), and a set of
    platform-specific well-known install locations. Set ``GLE_PATH`` to pin a
    specific GLE binary, e.g. when multiple versions are installed.
    """

    def __init__(self, gle_path: Optional[str] = None):
        """
        Initialize GLE compiler.

        Parameters
        ----------
        gle_path : str, optional
            Path to GLE executable. If None, resolved via :func:`find_gle`
            (``GLE_PATH`` env var, then ``PATH``, then well-known install
            locations).
        """
        self.gle_path = gle_path or find_gle()

        if not self.gle_path:
            raise RuntimeError("GLE not found. Install GLE or provide gle_path.")

    def compile(
        self,
        input_file: str,
        output_format: Literal['pdf', 'png', 'eps', 'jpg', 'svg'] = 'pdf',
        dpi: int = 150,
        verbose: bool = False,
        timeout: int = 30,
    ) -> Path:
        """
        Compile GLE file to output format.

        Parameters
        ----------
        input_file : str
            Path to .gle input file
        output_format : {'pdf', 'png', 'eps', 'jpg', 'svg'}
            Output format
        dpi : int
            DPI for raster formats (png, jpg)
        verbose : bool
            Print compiler output
        timeout : int
            Maximum number of seconds to allow the GLE process to run.

        Returns
        -------
        Path
            Path to output file

        Raises
        ------
        FileNotFoundError
            If the input file does not exist.
        GLECompileError
            If compilation fails (nonzero exit code, or the expected output
            file was not produced). Carries structured ``errors`` and the
            ``raw_output`` from the GLE process.
        """
        input_path = Path(input_file).resolve()

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Determine output file
        output_path = input_path.with_suffix(f'.{output_format}')

        # Build command (all options must come before filename). Pass as a
        # list (no shell=True) so paths containing spaces are handled safely
        # on all platforms, notably "Program Files" on Windows.
        cmd = [
            self.gle_path,
            '-d', output_format.upper(),
            '-o', str(output_path),
        ]

        if output_format in ('png', 'jpg'):
            cmd.extend(['-r', str(dpi)])

        cmd.append(str(input_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise GLECompileError(
                f"GLE compilation timed out after {timeout}s",
                errors=[],
                raw_output='',
            )

        # GLE writes most diagnostic/error output to stderr, but some builds
        # emit informational or error text on stdout too. Concatenate both
        # streams so nothing is silently dropped; parse_gle_errors only
        # matches its specific block pattern, so extra non-matching text is
        # harmless.
        raw_output = '\n'.join(s for s in (result.stdout, result.stderr) if s)

        if verbose or result.returncode != 0:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            errors = parse_gle_errors(raw_output)
            raise GLECompileError(
                f"GLE compilation failed: {raw_output.strip()}",
                errors=errors,
                raw_output=raw_output,
            )

        if not output_path.exists():
            errors = parse_gle_errors(raw_output)
            raise GLECompileError(
                f"Output file not created: {output_path}",
                errors=errors,
                raw_output=raw_output,
            )

        return output_path

    def info(self) -> dict:
        """Get GLE version and info."""
        try:
            result = subprocess.run(
                [self.gle_path, '-info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return {'version': result.stdout.strip()}
        except Exception as e:
            return {'error': str(e)}

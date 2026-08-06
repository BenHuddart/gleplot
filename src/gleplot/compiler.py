"""GLE compiler wrapper for gleplot."""

import glob
import os
import re
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Union


#: Well-known install locations to probe, keyed by ``sys.platform`` prefix.
#: Entries may be literal paths *or* glob patterns (``*``/``**``): the desktop
#: GUI ships to users who install GLE in a variety of locations and versioned
#: directories, so :func:`autodetect_gle` expands every entry with
#: :func:`glob.glob` and keeps the existing matches. Ordinary ``pip`` / library
#: use is unaffected (the literal entries below match the common installs).
_WELL_KNOWN_PATHS = {
    'win32': [
        r'C:\Program Files\GLE\bin\gle.exe',
        r'C:\Program Files (x86)\GLE\bin\gle.exe',
        # Versioned / non-default install roots, e.g. "GLE-4.3.9".
        r'C:\Program Files*\GLE*\bin\gle.exe',
        r'C:\Program Files*\GLE*\gle.exe',
        # Per-user installs (some installers / manual unzips land here).
        os.path.join(
            os.environ.get('LOCALAPPDATA', r'C:\Users\Default\AppData\Local'),
            'Programs', 'GLE*', '**', 'gle.exe',
        ),
    ],
    'darwin': [
        '/usr/local/bin/gle',      # Homebrew (Intel)
        '/opt/homebrew/bin/gle',   # Homebrew (Apple Silicon)
        '/opt/local/bin/gle',      # MacPorts
        '/usr/bin/gle',
        '/Applications/GLE*/**/gle',
    ],
    'default': [
        '/usr/local/bin/gle',
        '/opt/homebrew/bin/gle',
        '/usr/bin/gle',
        '/snap/bin/gle',           # snap
    ],
}

#: Process-global explicit override for the GLE executable, set via
#: :func:`set_gle_path_override`. This is how the desktop GUI pins the binary
#: the user chose in **Tools ▸ GLE Setup…**; it takes precedence over every
#: other discovery source (see :func:`find_gle`). ``None`` means "not set"
#: (library / CLI default), so nothing changes for non-GUI use.
_gle_path_override: Optional[str] = None


def set_gle_path_override(path: Optional[str]) -> None:
    """Pin (or clear) the GLE executable used by :func:`find_gle`.

    The GUI calls this with the user's configured path (persisted in
    ``QSettings``) so that every component resolving GLE via :func:`find_gle`
    -- live preview, export, the status bar -- honors the same choice. An
    empty string is normalized to ``None`` (i.e. "clear the override and fall
    back to auto-detection").

    Parameters
    ----------
    path : str or None
        Absolute path to a GLE executable, or ``None`` / ``""`` to clear the
        override and revert to auto-detection.
    """
    global _gle_path_override
    _gle_path_override = path or None

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

#: Formats for which GLE's ``-r`` (raster resolution / DPI) flag is
#: meaningful. Passing ``-r`` for a vector format (pdf/eps/svg) is harmless --
#: GLE silently ignores it -- but including it unconditionally (as the GUI
#: preview used to) obscures which formats it actually affects.
RASTER_COMPILE_FORMATS = frozenset({'png', 'jpg'})


def build_compile_args(
    output_format: str,
    output_path: Union[str, Path],
    input_path: Union[str, Path],
    dpi: Optional[int] = None,
    cairo: bool = False,
) -> List[str]:
    """Build the GLE command-line arguments for one compile invocation.

    This is the single place that decides ``-d``/``-r``/``-cairo``/``-o``
    argument shape, used by both :meth:`GLECompiler.compile` and the GUI's
    async compile service (:mod:`gleplot.gui.compile_core`,
    :mod:`gleplot.gui.compile_service`) so preview and export can never again
    drift apart the way they had: :meth:`GLECompiler.compile` used to pass an
    *uppercase* device name (``-d PDF``) and included ``-r`` only for raster
    formats, while ``gui/preview.py`` passed a *lowercase* device name and
    included ``-r`` unconditionally (harmless for vector formats -- GLE
    ignores it -- but inconsistent). Both now go through this function, which
    lowercases the device name (GLE's ``-d`` is case-insensitive; verified
    against a real ``gle`` binary) and includes ``-r`` only for
    :data:`RASTER_COMPILE_FORMATS`.

    Does **not** include the ``gle`` executable path itself -- callers using
    :mod:`subprocess` prepend it to this list; callers using
    :class:`~PySide6.QtCore.QProcess` pass it as the separate ``program``
    argument to ``QProcess.start()``.

    Parameters
    ----------
    output_format : str
        One of :data:`SUPPORTED_COMPILE_FORMATS` (case-insensitive).
    output_path : str or Path
        Value passed to ``-o``. Can be relative (resolved against the
        process's working directory) or absolute.
    input_path : str or Path
        The ``.gle`` script to compile. Same relative/absolute freedom as
        ``output_path``.
    dpi : int, optional
        Raster resolution. Only emitted (as ``-r <dpi>``) when
        ``output_format`` is in :data:`RASTER_COMPILE_FORMATS` *and* ``dpi``
        is not ``None``.
    cairo : bool, optional
        When ``True``, appends ``-cairo`` to enable GLE's Cairo rendering
        backend (SPEC §6.1/§10.6). Required for a script using
        semi-transparency (an ``rgba(...)``/``rgba255(...)`` colour); GLE
        fails outright on such a script without it, on every device this
        function supports *except* ``svg`` (``-d svg`` always renders
        through GLE's Cairo backend regardless of this flag -- but see the
        Notes below for why passing it explicitly still matters there too).
        Deciding *when* to enable Cairo is the caller's job:
        :meth:`gleplot.figure.Figure.savefig` passes
        ``figure.requires_cairo()`` automatically; other callers pass an
        explicit override.

    Notes
    -----
    Device composition under ``-cairo`` (verified against a real GLE 4.3.10
    binary; see ``gleplot.cairo_support`` for the font-substitution half of
    this):

    * ``pdf``/``eps``/``png``/``jpg`` -- without ``-cairo``, a script using
      semi-transparency fails (exit 1, "semi-transparency only supported
      with command line option '-cairo'"); with it, they succeed. ``png``/
      ``jpg`` route through an internal Cairo PDF pass first (visible in
      GLE's own progress output as ``[foo.pdf][foo.png]``) but GLE cleans up
      that intermediate itself -- no leftover ``.pdf`` was observed.
    * ``svg`` -- GLE *always* selects its Cairo SVG backend for ``-d svg``,
      with or without ``-cairo`` on the command line. But the flag still
      changes behavior: GLE's own automatic PostScript-font fallback
      (silently substituting a Cairo-safe font, with only an informational
      note) is gated on the ``-cairo`` *flag* being present, not on the
      Cairo backend being active. Compile ``-d svg`` *without* ``-cairo``
      against the default (PostScript) font and GLE still exits 0 but drops
      the affected text from the output (a hard, uncaught
      ``PostScript fonts not supported with '-cairo'`` at the point each
      character would have been drawn) -- exactly the failure mode
      ``gleplot.gui.preview``'s pre-emptive ``set font texcmr`` injection
      works around. Passing ``-cairo`` explicitly for an SVG compile lets
      GLE's own graceful fallback run instead.

    Returns
    -------
    list of str
        E.g. ``['-d', 'png', '-r', '150', '-o', 'out.png', 'in.gle']``.

    Raises
    ------
    ValueError
        If ``output_format`` is not in :data:`SUPPORTED_COMPILE_FORMATS`.
    """
    fmt = output_format.lower()
    if fmt not in SUPPORTED_COMPILE_FORMATS:
        raise ValueError(
            f"Unsupported GLE compile format: {output_format!r} "
            f"(supported: {sorted(SUPPORTED_COMPILE_FORMATS)})"
        )

    args = ['-d', fmt]
    if cairo:
        args.append('-cairo')
    if fmt in RASTER_COMPILE_FORMATS and dpi is not None:
        args.extend(['-r', str(int(dpi))])
    args.extend(['-o', str(output_path), str(input_path)])
    return args


def remove_generated_intermediates(
    directory: Union[str, Path], filenames: "list[str]"
) -> "list[Path]":
    """Delete engine-generated intermediates by exact name (GLEstudio §9.1/§10.8).

    GLE's ``begin contour``/``fitz`` code paths write files into the
    compiling script's directory as an undocumented side effect of running
    the ``gle`` binary -- never something gleplot itself asked GLE to write.
    ``begin contour`` always produces ``<stem>-cdata.dat``,
    ``<stem>-clabels.dat`` and ``<stem>-cvalues.dat`` (GLE derives ``<stem>``
    from its ``data "<stem>.z"`` line by stripping the extension --
    ``GetMainName`` in GLE's own ``gcontour.cpp``); a scattered (points-based)
    heatmap or contour additionally runs ``fitz``, which writes a gridded
    ``<stem>.z`` from the raw points ``.dat`` gleplot wrote (``fit.cpp``).
    None of these are gleplot's own output and none of them are meant to
    survive past the compile that produced them -- left behind, they clutter
    (and can go stale in) the export directory.

    This function does no globbing and no prefix matching: ``filenames`` is
    the closed, exact list of basenames a *specific* figure's contour/fitz
    series can produce (built by
    :meth:`~gleplot.figure.Figure._engine_intermediate_filenames`, itself
    derived from sidecar names that figure's own writer reserved -- see
    ``axes._reserve_sidecar``). A name is removed only if it is a literal,
    case-sensitive match to something in ``filenames`` *and* it exists as a
    plain file directly inside ``directory``; anything else -- a user's own
    file, a same-looking name in a different figure's stem sequence, a
    subdirectory -- is left alone. Path separators in a candidate name are
    rejected outright (defence in depth: every real caller only ever puts
    plain basenames in ``filenames``, but nothing here should ever escape
    ``directory`` even if a caller lists something malformed).

    Parameters
    ----------
    directory : str or Path
        The directory the ``.gle`` script was compiled from (its intermediates
        land here -- see the module note in ``Figure.savefig``).
    filenames : list of str
        Exact basenames to remove if present.

    Returns
    -------
    list of Path
        The files actually removed (a subset of ``filenames``; a name with no
        matching file -- e.g. a dangling series that produced no output, or
        a heatmap/contour without ``clabel`` so no ``-clabels.dat`` -- is
        silently skipped, not an error).
    """
    directory = Path(directory)
    removed: "list[Path]" = []
    for name in dict.fromkeys(filenames):  # de-dupe, preserve order
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            continue
        candidate = directory / name
        try:
            if candidate.is_file():
                candidate.unlink()
                removed.append(candidate)
        except OSError:
            # Best-effort cleanup: a permissions error or a race (file
            # removed by something else between the is_file() check and the
            # unlink()) should not turn a successful compile into a failure.
            pass
    return removed


def _iter_well_known_gle_paths() -> "list[str]":
    """Return existing GLE executables among the well-known locations.

    Each entry in :data:`_WELL_KNOWN_PATHS` for the current platform is treated
    as a :func:`glob.glob` pattern (a literal path is simply a pattern with no
    wildcards), so versioned / non-standard install directories are matched
    too. Results are de-duplicated while preserving discovery order.
    """
    patterns = _WELL_KNOWN_PATHS.get(sys.platform, _WELL_KNOWN_PATHS['default'])
    seen: set = set()
    found: list = []
    for pattern in patterns:
        # recursive=True so a ``**`` segment spans nested directories.
        for match in glob.glob(pattern, recursive=True):
            if match not in seen and Path(match).exists():
                seen.add(match)
                found.append(match)
    return found


def autodetect_gle() -> Optional[str]:
    """
    Auto-detect the GLE executable, ignoring any explicit override.

    This is the discovery used both as the fallback inside :func:`find_gle`
    (when no override is set) and directly by the GUI's **GLE Setup** dialog to
    propose a path regardless of what the user has currently pinned.

    Discovery precedence (first match wins):

    1. ``GLE_PATH`` environment variable -- the supported way to pin a
       specific GLE binary from the environment (e.g. to select among several
       installed versions, or a non-standard install location). If ``GLE_PATH``
       is set but does not point at an existing path, a :class:`UserWarning` is
       emitted and discovery falls through rather than silently ignoring the
       misconfiguration.
    2. ``shutil.which("gle")`` (searches ``PATH``, respecting ``PATHEXT`` on
       Windows)
    3. Platform-specific well-known install locations (:data:`_WELL_KNOWN_PATHS`,
       expanded as globs so versioned install dirs are matched).

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

    well_known = _iter_well_known_gle_paths()
    if well_known:
        return well_known[0]

    return None


def find_gle() -> Optional[str]:
    """
    Locate the GLE executable, honoring an explicit override first.

    Discovery precedence (first match wins):

    1. The explicit override set via :func:`set_gle_path_override` (how the
       GUI pins the user's chosen binary). If the override is set but no longer
       points at an existing path, a :class:`UserWarning` is emitted and
       discovery falls through to auto-detection rather than failing outright.
    2. Everything :func:`autodetect_gle` checks (``GLE_PATH`` env, then
       ``PATH``, then well-known install locations).

    The override deliberately outranks ``GLE_PATH``: it represents an explicit,
    in-app choice by the user, which should win over an ambient environment
    variable. With no override set (the library / CLI default) this is exactly
    :func:`autodetect_gle`.

    Returns
    -------
    str, optional
        Path to the GLE executable, or None if it could not be found.
    """
    if _gle_path_override:
        if Path(_gle_path_override).exists():
            return _gle_path_override
        warnings.warn(
            f"Configured GLE path {_gle_path_override!r} does not exist; "
            "falling back to auto-detection.",
            stacklevel=2,
        )

    return autodetect_gle()


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
#: ANSI SGR color/style escape sequences (e.g. ``\x1b[91m``) emitted by
#: GLE builds compiled with CONSOLE_COLORS=ON (the Linux/macOS default).
_ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*m')

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

    # Linux/macOS GLE builds (CONSOLE_COLORS=ON) wrap diagnostics in ANSI
    # color escapes, which would defeat the location regex below and
    # degrade every error to an unstructured raw-text fallback. Strip them
    # up front; harmless on output that has none (Windows builds).
    output = _ANSI_ESCAPE_RE.sub('', output)

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
        cairo: bool = False,
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
        cairo : bool
            Whether to pass GLE's ``-cairo`` device flag (SPEC §6.1/§10.6).
            Required for any script using semi-transparency (an
            ``rgba(...)``/``rgba255(...)`` colour -- e.g. a ``fill_between``
            with ``alpha < 1``); without it GLE fails outright on such a
            script (``semi-transparency only supported with command line
            option '-cairo'``). This method has no ``Figure`` to inspect, so
            it never decides this for you -- ``cairo`` is an explicit,
            caller-supplied override. :meth:`gleplot.figure.Figure.savefig`
            is the caller that *does* have the figure and passes
            ``figure.requires_cairo()`` here automatically; pass an explicit
            ``True``/``False`` yourself when compiling a ``.gle`` file this
            compiler didn't write (or to force the flag either way).

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
        # on all platforms, notably "Program Files" on Windows. Argument
        # shape (device name case, when -r is included) comes from the one
        # shared builder so this never drifts from the GUI's compile paths
        # again -- see build_compile_args().
        cmd = [self.gle_path] + build_compile_args(
            output_format, output_path, input_path, dpi=dpi, cairo=cairo,
        )

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

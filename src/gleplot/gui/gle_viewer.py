"""Preview/export support for hand-written ``.gle`` files.

This module is the counterpart to :mod:`gleplot.gui.preview` for the "File ▸
Open" path where the opened file is a hand-written GLE script rather than a
gleplot ``.glep`` project: there is no :class:`~gleplot.figure.Figure` to
snapshot, so we simply run the file through :class:`~gleplot.compiler.GLECompiler`
as-is and report a structured result.

Both functions here are pure logic -- no Qt widgets or signals -- so they can
be driven synchronously from a worker thread or a ``QProcess``-based caller
without pulling in GUI dependencies. The main window / preview integration
decides how (and on which thread) to invoke them.

Temp directory ownership
-------------------------
:func:`compile_gle_preview` writes its compiled output into ``output_dir`` if
given, or otherwise creates a fresh directory via ``tempfile.mkdtemp()``. In
the latter case **the caller owns that directory** and is responsible for
removing it (e.g. with ``shutil.rmtree``) once the preview is no longer
needed -- this module never deletes it, mirroring how
``PreviewController.shutdown()`` owns cleanup of its own session directory.

The established working directory is reported back via
``GlePreviewResult.work_dir`` on **every** outcome once it has been created --
success, compile failure, or a sidecar-copy error -- so the caller can always
clean it up and never leaks a directory on a failed preview.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from gleplot.compiler import GLECompileError, GLECompiler, GLEError, parse_gle_errors

__all__ = ['GlePreviewResult', 'compile_gle_preview', 'export_gle_file']


@dataclass
class GlePreviewResult:
    """Outcome of compiling a hand-written ``.gle`` file.

    Attributes
    ----------
    png_path : Path, optional
        Path to the compiled output file, or ``None`` on failure. Despite the
        attribute name (kept for the requested API shape), this holds
        whatever output format was requested -- see :func:`export_gle_file`.
    errors : list of GLEError
        Structured errors parsed from the compiler output. Empty on success.
    raw_output : str
        The raw combined stdout/stderr from the GLE process.
    success : bool
        Whether compilation succeeded and the output file exists.
    work_dir : Path, optional
        The directory the compile ran in. It is **always** populated once a
        working directory has been established -- both on success and on every
        failure path after the directory exists -- so the caller can clean it
        up regardless of outcome. ``None`` only when the function returned
        before establishing a working directory (e.g. the input file does not
        exist). When ``output_dir`` was supplied by the caller this equals that
        directory; otherwise it is the ``mkdtemp`` directory the caller owns.
    """

    png_path: Optional[Path]
    errors: List[GLEError] = field(default_factory=list)
    raw_output: str = ''
    success: bool = False
    work_dir: Optional[Path] = None


def _compile(
    gle_path: Union[str, Path],
    output_format: str,
    dpi: int,
    output_dir: Optional[Union[str, Path]],
) -> GlePreviewResult:
    """Shared implementation for :func:`compile_gle_preview` and
    :func:`export_gle_file`.

    ``GLECompiler.compile`` always writes its output next to the *input*
    file (``input_path.with_suffix(...)``), ignoring any notion of an output
    directory. To honor ``output_dir``, the source ``.gle`` file (and any
    sibling data files it may reference, e.g. ``*.dat``/``*.z``/``*.csv``) is
    copied into the target directory first, and the compiler is pointed at
    that copy.
    """
    source = Path(gle_path)
    if not source.exists():
        # No working directory was established, so work_dir stays None.
        err = GLEError(file=str(source), line=None, column=None,
                        message=f"Input file not found: {source}")
        return GlePreviewResult(png_path=None, errors=[err], raw_output='', success=False)

    if output_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix='gleplot_gle_preview_'))
    else:
        work_dir = Path(output_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    # From here on a working directory exists: EVERY return path must carry
    # work_dir so the caller can clean it up (FIX 5 -- prevents a leaked temp
    # dir on any failure path).
    work_gle = work_dir / source.name
    if work_gle.resolve() != source.resolve():
        try:
            shutil.copy2(source, work_gle)
            # Best-effort: bring along common sidecar data formats referenced by
            # the script so relative `data` statements still resolve.
            for sidecar in source.parent.glob(f'{source.stem}*'):
                if sidecar == source:
                    continue
                if sidecar.suffix.lower() in {'.dat', '.csv', '.z'}:
                    shutil.copy2(sidecar, work_dir / sidecar.name)
            # Also copy any data file referenced anywhere in the same directory,
            # since GLE scripts commonly reference shared '.dat' files by a name
            # unrelated to the script's own stem.
            for sidecar in source.parent.glob('*.dat'):
                dest = work_dir / sidecar.name
                if not dest.exists():
                    shutil.copy2(sidecar, dest)
        except OSError as exc:
            # A locked/unreadable file (e.g. PermissionError on a .dat held by
            # another process) must not crash File>Open. Surface a structured
            # failure naming the offending file instead (FIX 6).
            offending = getattr(exc, 'filename', None) or str(source)
            err = GLEError(
                file=str(offending), line=None, column=None,
                message=f"Could not copy file into preview directory: {exc}",
            )
            return GlePreviewResult(
                png_path=None, errors=[err], raw_output='', success=False,
                work_dir=work_dir,
            )

    try:
        compiler = GLECompiler()
    except RuntimeError as exc:
        err = GLEError(file=None, line=None, column=None, message=str(exc))
        return GlePreviewResult(
            png_path=None, errors=[err], raw_output='', success=False,
            work_dir=work_dir,
        )

    try:
        output_path = compiler.compile(str(work_gle), output_format, dpi=dpi)
    except GLECompileError as exc:
        errors = exc.errors or parse_gle_errors(exc.raw_output) or [
            GLEError(file=None, line=None, column=None, message=str(exc))
        ]
        return GlePreviewResult(
            png_path=None, errors=errors, raw_output=exc.raw_output, success=False,
            work_dir=work_dir,
        )
    except FileNotFoundError as exc:
        err = GLEError(file=str(work_gle), line=None, column=None, message=str(exc))
        return GlePreviewResult(
            png_path=None, errors=[err], raw_output='', success=False,
            work_dir=work_dir,
        )

    return GlePreviewResult(
        png_path=output_path, errors=[], raw_output='', success=True,
        work_dir=work_dir,
    )


def compile_gle_preview(
    gle_path: Union[str, Path],
    dpi: int = 150,
    output_dir: Optional[Union[str, Path]] = None,
) -> GlePreviewResult:
    """Compile a hand-written ``.gle`` file to PNG for preview purposes.

    Parameters
    ----------
    gle_path : str or Path
        Path to the ``.gle`` script to compile.
    dpi : int, optional
        Raster resolution, forwarded to the GLE ``-r`` flag. Default 150.
    output_dir : str or Path, optional
        Directory to compile into. If omitted, a fresh directory is created
        with ``tempfile.mkdtemp()`` -- **the caller owns this directory** and
        must remove it when done (this function never deletes it).

    Returns
    -------
    GlePreviewResult
        ``success`` is True and ``png_path`` points at the produced PNG on
        success; otherwise ``errors``/``raw_output`` describe the failure.
    """
    return _compile(gle_path, 'png', dpi, output_dir)


def export_gle_file(
    gle_path: Union[str, Path],
    target_path: Union[str, Path],
    format: str = 'pdf',
    dpi: int = 300,
) -> GlePreviewResult:
    """Export a hand-written ``.gle`` file to a chosen format and location.

    Compiles ``gle_path`` into the directory containing ``target_path`` and,
    on success, ensures the compiled output ends up at ``target_path``
    (renaming it if the compiler's natural output name differs).

    Parameters
    ----------
    gle_path : str or Path
        Path to the ``.gle`` script to compile.
    target_path : str or Path
        Desired output file location. Its parent directory is used as the
        compile working directory; its final path is what's returned as
        ``png_path`` on success (name kept for API-shape consistency with
        :func:`compile_gle_preview`, though the format may not be PNG).
    format : {'pdf', 'png', 'eps', 'jpg', 'svg'}, optional
        Output format. Default ``'pdf'``.
    dpi : int, optional
        Raster resolution for png/jpg formats. Default 300.

    Returns
    -------
    GlePreviewResult
    """
    target = Path(target_path)
    result = _compile(gle_path, format, dpi, target.parent)
    if not result.success or result.png_path is None:
        return result

    if result.png_path != target:
        target.parent.mkdir(parents=True, exist_ok=True)
        if result.png_path.exists():
            shutil.move(str(result.png_path), str(target))
        result.png_path = target

    return result

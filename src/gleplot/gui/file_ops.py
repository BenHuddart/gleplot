"""Dialog-driven file open/save operations for the gleplot GUI editor.

This module wires the ``.gle`` recognizer/writer round-trip
(:func:`gleplot.parser.recognizer.parse_gle_figure` /
:meth:`~gleplot.figure.Figure.savefig_gle`) up to Qt file dialogs and a
:class:`FigureDocument`. ``.gle`` is the native, only supported on-disk format
for the editor -- the legacy JSON ``.glep`` project format has been removed.
Every public function accepts an already-resolved ``path`` so tests (and
programmatic callers, e.g. a "reopen last project" action) can bypass the
dialog entirely; when ``path`` is omitted a native file dialog is shown.

Recent-files tracking and the last-used directory are persisted via
``QSettings("gleplot", "gleplot")`` by default; pass an explicit
``settings=`` (e.g. an ini-backed :class:`QSettings` pointed at a scratch
file) to isolate tests from the user's real settings store.

Wiring these into a File menu (recent-files list, New/Open/Save/Save As
actions, keyboard shortcuts) is the main window's responsibility -- this
module has no knowledge of menus or actions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from gleplot.gui.document import FigureDocument
from gleplot.parser.recognizer import RecognizedFigure, parse_gle_figure

__all__ = [
    'open_project',
    'install_recognized',
    'save_project_current',
    'save_project_as',
    'add_recent_file',
    'get_recent_files',
]

#: Filter string shared by the open and save-as dialogs.
_FILE_FILTER = "GLE figure (*.gle);;All files (*)"

#: QSettings organization/application names used when the caller doesn't
#: inject its own QSettings instance.
_ORG = "gleplot"
_APP = "gleplot"

#: QSettings keys.
_KEY_LAST_DIR = "file_ops/last_dir"
_KEY_RECENT_FILES = "file_ops/recent_files"

#: Maximum number of entries kept in the recent-files list.
MAX_RECENT_FILES = 8

#: Legacy JSON project extension, no longer supported. Kept only so a
#: leftover entry in a user's recent-files list (persisted by an older
#: version of gleplot) can be recognized and rejected with a clear message.
_LEGACY_PROJECT_SUFFIX = ".glep"


def _default_settings() -> QSettings:
    return QSettings(_ORG, _APP)


def _last_dir(settings: QSettings) -> str:
    return settings.value(_KEY_LAST_DIR, "", type=str) or ""


def _remember_dir(settings: QSettings, path: Union[str, Path]) -> None:
    settings.setValue(_KEY_LAST_DIR, str(Path(path).parent))


def _show_error(parent: Optional[QWidget], title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def _remove_recent_file(path: Union[str, Path], settings: QSettings) -> None:
    """Drop ``path`` from the recent-files list (case-insensitively)."""
    key = os.path.normcase(os.path.abspath(str(Path(path))))
    recent = get_recent_files(settings=settings)
    recent = [p for p in recent if os.path.normcase(os.path.abspath(p)) != key]
    settings.setValue(_KEY_RECENT_FILES, recent)


# ----------------------------------------------------------------------
# Open
# ----------------------------------------------------------------------
def open_project(
    parent: Optional[QWidget],
    document: FigureDocument,
    path: Optional[Union[str, Path]] = None,
    settings: Optional[QSettings] = None,
) -> bool:
    """Open a ``.gle`` file into ``document`` as an editable figure.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget for the file dialog / error message box.
    document : FigureDocument
        Document to install the recognized figure into.
    path : str or Path, optional
        ``.gle`` file to open. If ``None``, a native "Open" dialog is shown
        (filtered to ``*.gle``, defaulting to the last-used directory).
    settings : QSettings, optional
        Settings store for the last-used directory and recent-files list.
        Defaults to ``QSettings("gleplot", "gleplot")``.

    Returns
    -------
    bool
        ``True`` if the file was recognized and installed as an editable
        figure; ``False`` if the dialog was cancelled, the path is a legacy
        ``.glep`` project (removed from ``recent`` and rejected with a
        critical message box), or recognition raised an unexpected exception
        (also shown via a critical message box).

        Note that the GLE recognizer is tolerant by design: a hand-written or
        partially-broken ``.gle`` still returns a figure, just with entries
        appended to ``document.open_warnings`` (e.g. a missing sidecar
        ``.dat`` produces a ``"data: ..."`` warning, not a failure). ``False``
        here means the file could not be opened as an editable figure at
        all -- it does NOT decide whether to fall back to a read-only GLE
        preview; that fallback is the main window's responsibility.
    """
    settings = settings or _default_settings()

    if path is None:
        chosen, _ = QFileDialog.getOpenFileName(
            parent, "Open", _last_dir(settings), _FILE_FILTER,
        )
        if not chosen:
            return False
        path = chosen

    path = Path(path)

    if path.suffix.lower() == _LEGACY_PROJECT_SUFFIX:
        _remove_recent_file(path, settings)
        _show_error(
            parent, "Open Failed",
            f"'{path.name}' is a legacy .glep project file.\n\n"
            "The .glep project format is no longer supported; .gle is the "
            "native format now.",
        )
        return False

    try:
        rec = parse_gle_figure(path)
    except Exception as exc:  # noqa: BLE001 - unexpected recognizer failure
        _show_error(parent, "Open Failed", str(exc))
        return False

    install_recognized(document, rec, path, settings=settings)
    return True


def install_recognized(
    document: FigureDocument,
    rec: RecognizedFigure,
    path: Union[str, Path],
    settings: Optional[QSettings] = None,
) -> None:
    """Install an already-parsed :class:`RecognizedFigure` into ``document``.

    Split out of :func:`open_project` so a caller that has *already* run the
    recognizer (e.g. the main window probes ``.gle`` warnings to decide between
    editable and read-only-preview modes) can commit the parse result without
    re-parsing the file. Performs exactly the document-side work
    ``open_project`` does after a successful parse: installs the figure
    (``set_figure`` first, which resets ``project_path``/``open_warnings``),
    then assigns the real path and recognizer warnings, marks the document
    clean, and records the file in the last-dir / recent-files stores.

    Parameters
    ----------
    document : FigureDocument
        Document to install the recognized figure into.
    rec : RecognizedFigure
        The parse result (``rec.figure`` + ``rec.warnings``).
    path : str or Path
        The ``.gle`` file the figure was parsed from (used for the project
        path and recent-files tracking).
    settings : QSettings, optional
        Settings store; defaults to ``QSettings("gleplot", "gleplot")``.
    """
    settings = settings or _default_settings()
    path = Path(path)

    document.set_figure(rec.figure)
    document.project_path = path
    document.open_warnings = rec.warnings
    document.mark_clean()

    _remember_dir(settings, path)
    add_recent_file(path, settings=settings)


# ----------------------------------------------------------------------
# Save
# ----------------------------------------------------------------------
def save_project_current(
    parent: Optional[QWidget],
    document: FigureDocument,
    path: Optional[Union[str, Path]] = None,
    settings: Optional[QSettings] = None,
) -> bool:
    """Save ``document`` to its current ``.gle`` path, prompting if unset.

    If ``document.project_path`` is ``None`` (a never-saved document), this
    delegates to :func:`save_project_as`. Otherwise it saves in place.

    Parameters
    ----------
    parent, document, settings
        See :func:`open_project`.
    path : str or Path, optional
        Explicit path to save to, bypassing both the project-path check and
        any dialog. Primarily for tests.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on cancellation or failure.
    """
    settings = settings or _default_settings()

    if path is None:
        path = document.project_path
        if path is None:
            return save_project_as(parent, document, settings=settings)

    if document.figure is None:
        _show_error(parent, "Save Failed", "No figure to save.")
        return False

    try:
        document.figure.savefig_gle(str(path))
    except OSError as exc:
        _show_error(parent, "Save Failed", str(exc))
        return False

    path = Path(path)
    document.project_path = path
    document.open_warnings = []
    document.mark_clean()
    _remember_dir(settings, path)
    add_recent_file(path, settings=settings)
    return True


def save_project_as(
    parent: Optional[QWidget],
    document: FigureDocument,
    path: Optional[Union[str, Path]] = None,
    settings: Optional[QSettings] = None,
) -> bool:
    """Save ``document`` to a new ``.gle`` path (File ▸ Save As).

    Parameters
    ----------
    parent, document, settings
        See :func:`open_project`.
    path : str or Path, optional
        Explicit destination, bypassing the "Save As" dialog. If given
        without a ``.gle`` suffix, the suffix is *not* forced (only the
        dialog path does suffix-completion) so tests can use arbitrary
        extensions if needed.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on cancellation or failure.
    """
    settings = settings or _default_settings()

    if path is None:
        chosen, _ = QFileDialog.getSaveFileName(
            parent, "Save As", _last_dir(settings), _FILE_FILTER,
        )
        if not chosen:
            return False
        chosen_path = Path(chosen)
        if chosen_path.suffix.lower() != ".gle":
            chosen_path = chosen_path.with_name(chosen_path.name + ".gle")
        path = chosen_path

    if document.figure is None:
        _show_error(parent, "Save Failed", "No figure to save.")
        return False

    try:
        document.figure.savefig_gle(str(path))
    except OSError as exc:
        _show_error(parent, "Save Failed", str(exc))
        return False

    path = Path(path)
    document.project_path = path
    document.open_warnings = []
    document.mark_clean()
    _remember_dir(settings, path)
    add_recent_file(path, settings=settings)
    return True


# ----------------------------------------------------------------------
# Recent files
# ----------------------------------------------------------------------
def add_recent_file(
    path: Union[str, Path],
    settings: Optional[QSettings] = None,
) -> None:
    """Add ``path`` to the front of the recent-files list.

    Deduplicates (an existing entry is moved to the front rather than
    duplicated) and caps the list at :data:`MAX_RECENT_FILES` entries.

    Deduplication is filesystem-case-aware: paths are compared after
    ``os.path.normcase(os.path.abspath(...))`` so that on Windows (and other
    case-insensitive filesystems) ``Foo.gle`` and ``foo.gle`` are recognised
    as the same file. The *original* casing that was passed in is what gets
    stored/displayed -- only the comparison is normalized.
    """
    settings = settings or _default_settings()
    path_str = str(Path(path))
    key = os.path.normcase(os.path.abspath(path_str))

    recent = get_recent_files(settings=settings)
    recent = [
        p for p in recent
        if os.path.normcase(os.path.abspath(p)) != key
    ]
    recent.insert(0, path_str)
    recent = recent[:MAX_RECENT_FILES]

    settings.setValue(_KEY_RECENT_FILES, recent)


def get_recent_files(settings: Optional[QSettings] = None) -> List[str]:
    """Return the recent-files list, most-recent-first.

    Returns
    -------
    list of str
        Up to :data:`MAX_RECENT_FILES` path strings.
    """
    settings = settings or _default_settings()
    value = settings.value(_KEY_RECENT_FILES, [])
    if value is None:
        return []
    if isinstance(value, str):
        # QSettings on some backends collapses a single-element list to a
        # bare string; normalize back to a list.
        return [value]
    return list(value)

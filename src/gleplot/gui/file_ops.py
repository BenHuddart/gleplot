"""Dialog-driven project open/save operations for the gleplot GUI editor.

This module wires :mod:`gleplot.project` (the plain JSON ``.glep``
read/write functions) up to Qt file dialogs and a :class:`FigureDocument`.
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
from gleplot.project import load_project, save_project

__all__ = [
    'open_project',
    'save_project_current',
    'save_project_as',
    'add_recent_file',
    'get_recent_files',
]

#: Filter string shared by the open and save-as dialogs.
_FILE_FILTER = "gleplot project (*.glep);;All files (*)"

#: QSettings organization/application names used when the caller doesn't
#: inject its own QSettings instance.
_ORG = "gleplot"
_APP = "gleplot"

#: QSettings keys.
_KEY_LAST_DIR = "file_ops/last_dir"
_KEY_RECENT_FILES = "file_ops/recent_files"

#: Maximum number of entries kept in the recent-files list.
MAX_RECENT_FILES = 8


def _default_settings() -> QSettings:
    return QSettings(_ORG, _APP)


def _last_dir(settings: QSettings) -> str:
    return settings.value(_KEY_LAST_DIR, "", type=str) or ""


def _remember_dir(settings: QSettings, path: Union[str, Path]) -> None:
    settings.setValue(_KEY_LAST_DIR, str(Path(path).parent))


def _show_error(parent: Optional[QWidget], title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


# ----------------------------------------------------------------------
# Open
# ----------------------------------------------------------------------
def open_project(
    parent: Optional[QWidget],
    document: FigureDocument,
    path: Optional[Union[str, Path]] = None,
    settings: Optional[QSettings] = None,
) -> bool:
    """Open a ``.glep`` project file into ``document``.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget for the file dialog / error message box.
    document : FigureDocument
        Document to install the loaded figure into.
    path : str or Path, optional
        Project file to open. If ``None``, a native "Open" dialog is shown
        (filtered to ``*.glep``, defaulting to the last-used directory).
    settings : QSettings, optional
        Settings store for the last-used directory and recent-files list.
        Defaults to ``QSettings("gleplot", "gleplot")``.

    Returns
    -------
    bool
        ``True`` if a project was loaded and installed; ``False`` if the
        dialog was cancelled or loading failed (a critical message box is
        shown on failure).
    """
    settings = settings or _default_settings()

    if path is None:
        chosen, _ = QFileDialog.getOpenFileName(
            parent, "Open Project", _last_dir(settings), _FILE_FILTER,
        )
        if not chosen:
            return False
        path = chosen

    path = Path(path)
    try:
        fig = load_project(path)
    except (ValueError, OSError) as exc:
        _show_error(parent, "Open Project Failed", str(exc))
        return False
    except Exception as exc:  # noqa: BLE001 - includes json.JSONDecodeError
        _show_error(parent, "Open Project Failed", str(exc))
        return False

    document.set_figure(fig)
    document.project_path = path
    document.mark_clean()

    _remember_dir(settings, path)
    add_recent_file(path, settings=settings)
    return True


# ----------------------------------------------------------------------
# Save
# ----------------------------------------------------------------------
def save_project_current(
    parent: Optional[QWidget],
    document: FigureDocument,
    path: Optional[Union[str, Path]] = None,
    settings: Optional[QSettings] = None,
) -> bool:
    """Save ``document`` to its current project path, prompting if unset.

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
        _show_error(parent, "Save Project Failed", "No figure to save.")
        return False

    try:
        save_project(document.figure, path)
    except OSError as exc:
        _show_error(parent, "Save Project Failed", str(exc))
        return False

    path = Path(path)
    document.project_path = path
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
    """Save ``document`` to a new project path (File ▸ Save As).

    Parameters
    ----------
    parent, document, settings
        See :func:`open_project`.
    path : str or Path, optional
        Explicit destination, bypassing the "Save As" dialog. If given
        without a ``.glep`` suffix, the suffix is *not* forced (only the
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
            parent, "Save Project As", _last_dir(settings), _FILE_FILTER,
        )
        if not chosen:
            return False
        chosen_path = Path(chosen)
        if chosen_path.suffix.lower() != ".glep":
            chosen_path = chosen_path.with_name(chosen_path.name + ".glep")
        path = chosen_path

    if document.figure is None:
        _show_error(parent, "Save Project Failed", "No figure to save.")
        return False

    try:
        save_project(document.figure, path)
    except OSError as exc:
        _show_error(parent, "Save Project Failed", str(exc))
        return False

    path = Path(path)
    document.project_path = path
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
    case-insensitive filesystems) ``Foo.glep`` and ``foo.glep`` are recognised
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

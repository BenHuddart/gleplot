"""Application entry point for the gleplot GUI editor.

Provides :func:`main`, the callable registered as the ``gleplot-gui``
console script (see ``pyproject.toml``: ``[project.scripts]``).

Passing ``--smoke-test`` constructs the :class:`QApplication` and
:class:`MainWindow` headlessly (forcing the Qt ``offscreen`` platform) and
returns ``0`` immediately without showing the window or entering the event
loop. Packaging CI uses this to verify the frozen app imports and builds its
main window without a display.

An optional positional argument names a ``.gle`` file to open on launch
(``gleplot-gui figure.gle``). It is opened *after* the window is shown, and
is ignored entirely under ``--smoke-test`` (smoke-test only verifies
construction; see :func:`main`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gleplot.gui.main_window import MainWindow


def _set_window_icon(app: QApplication) -> None:
    """Set the application/window icon from the bundled PNG asset.

    Resolves the asset relative to this package's directory (works on all
    supported Python versions -- ``importlib.resources.files`` is 3.9+ -- and
    inside the PyInstaller onedir bundle, where the spec ships the PNG to
    ``gleplot/gui/assets/``). Defensive: any failure to locate or load the
    asset is ignored so a missing icon never breaks startup.
    """
    try:
        icon_path = Path(__file__).resolve().parent / "assets" / "gleplot.png"
        if icon_path.is_file():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass


def open_editor(
    path: Optional[str] = None,
    *,
    parent=None,
    settings=None,
    gle_executable: Optional[str] = None,
) -> MainWindow:
    """Open a gleplot editor window inside an existing ``QApplication``.

    This is the supported embedding API for host applications (e.g. analysis
    programs that export ``.gle`` figures and want to hand them to the editor
    in-process). Unlike :func:`main`, it never creates a ``QApplication``,
    never mutates application-global identity (name, organization, app icon),
    and never runs an event loop — the host owns all of that.

    Parameters
    ----------
    path : str, optional
        A ``.gle`` file to open. May show the same modal prompts as
        File ▸ Open (programmatic-file warning, parse-failure fallback).
    parent : QWidget, optional
        Qt parent for the window.
    settings : QSettings, optional
        Injected settings store for recent-files/last-dir state; ``None``
        uses gleplot's own ``QSettings("gleplot", "gleplot")``.
    gle_executable : str, optional
        Explicit GLE binary for preview rendering. When given it overrides
        gleplot's persisted GLE-path preference (via
        :func:`gleplot.compiler.set_gle_path_override`, which is
        process-global) so the editor compiles with the same binary as the
        host. ``None`` leaves gleplot's own discovery in effect.

    Returns
    -------
    MainWindow
        The shown editor window. The caller must keep a reference — Qt does
        not keep parentless windows alive on the Python side.

    Raises
    ------
    RuntimeError
        If no ``QApplication`` exists. Creating one here would be a trap:
        the host is expected to own the application and its event loop.
    """
    if QApplication.instance() is None:
        raise RuntimeError(
            "open_editor() requires an existing QApplication; it is an "
            "embedding API. Use gleplot.gui.app.main() to run standalone."
        )

    window = MainWindow(parent=parent, settings=settings)

    if gle_executable:
        # MainWindow.__init__ applied gleplot's own persisted override;
        # re-apply the host's choice (session-only, not persisted).
        window.apply_gle_executable(gle_executable)

    # Window-local icon only: setWindowIcon on the QApplication would leak
    # gleplot branding onto the host's windows.
    try:
        icon_path = Path(__file__).resolve().parent / "assets" / "gleplot.png"
        if icon_path.is_file():
            window.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass

    if path is not None:
        window.open_path(str(path))

    window.show()
    return window


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Launch the gleplot GUI editor.

    Creates (or reuses) a :class:`QApplication`, shows the main window,
    and runs the Qt event loop.

    Parameters
    ----------
    argv : sequence of str, optional
        Command-line arguments. Defaults to ``sys.argv``, in which case
        ``argv[0]`` (the program name) is skipped when looking for a file
        argument. Callers passing an explicit ``argv`` are expected to pass
        only real arguments (no leading program name), matching how this
        module's own tests invoke ``main([...])`` — so no leading element is
        skipped in that case. The first element that isn't the
        ``--smoke-test`` flag is treated as a ``.gle`` file path to open.

    Returns
    -------
    int
        The application's exit code: ``2`` if a file argument was given but
        does not exist (checked before any ``QApplication`` is created), the
        Qt event loop's exit code if this call owns the application, or
        ``0`` for ``--smoke-test`` or when reusing an existing application.
    """
    args = list(argv) if argv is not None else sys.argv
    scan = args[1:] if argv is None else args

    smoke_test = "--smoke-test" in args
    file_arg = next((a for a in scan if a != "--smoke-test"), None)

    # Under --smoke-test, ignore any file argument entirely: smoke-test only
    # verifies that construction succeeds, and never shows the window or
    # opens anything (see module docstring).
    file_path: Optional[Path] = None
    if file_arg is not None and not smoke_test:
        file_path = Path(file_arg)
        if not file_path.is_file():
            print(f"gleplot-gui: no such file: {file_arg}", file=sys.stderr)
            return 2

    if smoke_test:
        # Run headless so this works without a display (e.g. packaging CI).
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(args)

    app.setApplicationName("gleplot")
    app.setOrganizationName("gleplot")
    # Note: no setApplicationDisplayName — Qt appends it to every window
    # title, which duplicates MainWindow's own "gleplot editor — ..." prefix.
    _set_window_icon(app)

    window = MainWindow()

    if smoke_test:
        # Verify construction only: do not show the window or run the event
        # loop. Return success immediately.
        return 0

    window.show()

    if file_path is not None:
        # After show(): modal prompts the open may raise (programmatic-file
        # question, parse-failure fallback) should appear over a visible
        # window rather than an invisible one.
        window.open_path(str(file_path))

    if owns_app:
        return app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())

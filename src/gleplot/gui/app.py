"""Application entry point for the gleplot GUI editor.

Provides :func:`main`, the callable registered as the ``gleplot-gui``
console script (see ``pyproject.toml``: ``[project.scripts]``).

Passing ``--smoke-test`` constructs the :class:`QApplication` and
:class:`MainWindow` headlessly (forcing the Qt ``offscreen`` platform) and
returns ``0`` immediately without showing the window or entering the event
loop. Packaging CI uses this to verify the frozen app imports and builds its
main window without a display.
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Launch the gleplot GUI editor.

    Creates (or reuses) a :class:`QApplication`, shows the main window,
    and runs the Qt event loop.

    Parameters
    ----------
    argv : sequence of str, optional
        Command-line arguments. Defaults to ``sys.argv``.

    Returns
    -------
    int
        The application's exit code.
    """
    args = list(argv) if argv is not None else sys.argv

    smoke_test = "--smoke-test" in args
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

    if owns_app:
        return app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())

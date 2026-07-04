"""Application entry point for the gleplot GUI editor.

Provides :func:`main`, the callable registered as the ``gleplot-gui``
console script (see ``pyproject.toml``: ``[project.scripts]``).
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from gleplot.gui.main_window import MainWindow


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

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(args)

    app.setApplicationName("gleplot")
    app.setOrganizationName("gleplot")
    # Note: no setApplicationDisplayName — Qt appends it to every window
    # title, which duplicates MainWindow's own "gleplot editor — ..." prefix.

    window = MainWindow()
    window.show()

    if owns_app:
        return app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())

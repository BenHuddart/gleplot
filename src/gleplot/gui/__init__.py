"""
gleplot.gui - PySide6-based GUI editor for gleplot.

This subpackage provides a desktop application for interactively building
and previewing GLE plots. It is an optional extra (``pip install gleplot[gui]``)
and is not imported by the core :mod:`gleplot` package.

Importing :mod:`gleplot.gui` itself is lightweight; PySide6 is only imported
when submodules such as :mod:`gleplot.gui.app` or :mod:`gleplot.gui.main_window`
are imported.
"""

__all__ = ["open_editor"]


def __getattr__(name: str):
    # Lazy re-export: keeps `import gleplot.gui` PySide6-free while letting
    # embedders write `from gleplot.gui import open_editor`.
    if name == "open_editor":
        from gleplot.gui.app import open_editor

        return open_editor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

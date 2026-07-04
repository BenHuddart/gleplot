"""gleplot.gui.data - Data manager for the gleplot GUI editor (Phase 1, Track E).

This subpackage provides:

- :mod:`gleplot.gui.data.loader` - pure-Python (no Qt) delimited text file
  loading into a :class:`~gleplot.gui.data.loader.DataTable`.
- :mod:`gleplot.gui.data.panel` - :class:`~gleplot.gui.data.panel.DataPanel`,
  a self-contained ``QWidget`` for loading data files and mapping columns to
  plot series on a :class:`gleplot.figure.Figure`.
"""

from .loader import DataTable, load_data_file

__all__ = ["DataTable", "load_data_file"]

try:
    from .panel import DataPanel  # noqa: F401

    __all__.append("DataPanel")
except ImportError:
    # PySide6 (the ``gui`` extra) is not installed; loader.py remains
    # usable standalone without Qt.
    pass

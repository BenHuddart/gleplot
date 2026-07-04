"""gleplot.gui.panels - Property panels for the gleplot GUI editor.

Exposes the figure/axes/series property panels used by the "Properties"
dock. Each panel binds to a duck-typed ``document`` object (see
``figure_panel.py`` for the exact contract) rather than importing
``gleplot.gui.document`` directly, so this subpackage has no dependency on
the parallel document/preview development track.
"""

from .axes_panel import AxesPanel
from .figure_panel import FigurePanel
from .layout_panel import LayoutPanel
from .series_panel import SeriesPanel

__all__ = ["FigurePanel", "AxesPanel", "SeriesPanel", "LayoutPanel"]

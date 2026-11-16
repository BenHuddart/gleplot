"""
Examples for gleplot library.

Basic examples:
    - line_plots: Basic line plotting with multiple series
    - scatter_plots: Scatter plots with trend lines
    - bar_charts: Bar charts with multiple colors

Advanced examples:
    - fill_between: Fill between curves
    - log_scale: Logarithmic scaling
    - combined_plots: Combined plot types
    - multiple_styles: Multiple line styles and markers

Run all examples:
    python -m examples.run_all
"""

from .advanced import (
    example_combined_plot,
    example_fill_between,
    example_log_scale,
    example_multiple_styles,
)
from .basic import (
    example_bar_chart,
    example_basic_line_plot,
    example_scatter_plot,
)

__all__ = [
    # Basic examples
    "example_basic_line_plot",
    "example_scatter_plot",
    "example_bar_chart",
    # Advanced examples
    "example_fill_between",
    "example_log_scale",
    "example_combined_plot",
    "example_multiple_styles",
]

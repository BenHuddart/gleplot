"""Advanced gleplot examples demonstrating complex plotting features."""

from .fill_between import example_fill_between, example_fill_between_conditional
from .log_scale import example_log_scale
from .combined_plots import example_combined_plot
from .multiple_styles import example_multiple_styles
from .shared_axes import (
    example_sharex_stacked,
    example_sharey_sidebyside,
    example_both_shared,
    example_residual_plot,
    example_comparison_with_without,
)
from .subplots import (
    example_side_by_side,
    example_stacked,
    example_2x2_grid,
    example_1x3_comparison,
)
from .errorbar_from_file import (
    example_errorbar_from_file,
    example_dual_axis_from_file,
    example_line_overlay_from_file,
)
from .text_annotations import example_text_annotations
from .per_element_styling import example_per_element_styling
from .batch_figures import example_batch_figures
from .line_from_file import example_line_from_file
from .data_prefix import example_data_prefix

__all__ = [
    'example_fill_between',
    'example_fill_between_conditional',
    'example_log_scale',
    'example_combined_plot',
    'example_multiple_styles',
    'example_sharex_stacked',
    'example_sharey_sidebyside',
    'example_both_shared',
    'example_residual_plot',
    'example_comparison_with_without',
    'example_side_by_side',
    'example_stacked',
    'example_2x2_grid',
    'example_1x3_comparison',
    'example_errorbar_from_file',
    'example_dual_axis_from_file',
    'example_line_overlay_from_file',
    'example_text_annotations',
    'example_per_element_styling',
    'example_batch_figures',
    'example_line_from_file',
    'example_data_prefix',
]

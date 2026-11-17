"""Advanced gleplot examples demonstrating complex plotting features."""

from .batch_figures import example_batch_figures
from .broken_axis import (
    example_broken_axis_line,
    example_broken_axis_none,
    example_broken_axis_slash,
)
from .combined_plots import example_combined_plot
from .configuration import (
    example_global_config,
    example_line_styles,
    example_marker_config,
    example_per_figure_config,
    example_smooth_curves,
)
from .data_prefix import example_data_prefix
from .errorbar_from_file import (
    example_dual_axis_from_file,
    example_errorbar_from_file,
    example_line_overlay_from_file,
)
from .fill_between import example_fill_between, example_fill_between_conditional
from .line_from_file import example_line_from_file
from .log_scale import example_log_scale
from .multiple_styles import example_multiple_styles
from .per_element_styling import example_per_element_styling
from .phase_diagram import example_phase_diagram
from .prl_fig2a_style import example_prl_fig2a_style
from .secondary_yaxis import example_secondary_yaxis
from .shared_axes import (
    example_both_shared,
    example_comparison_with_without,
    example_residual_plot,
    example_sharex_stacked,
    example_sharey_sidebyside,
)
from .subplots import (
    example_1x3_comparison,
    example_2x2_grid,
    example_side_by_side,
    example_stacked,
)
from .text_annotations import example_text_annotations

__all__ = [
    "example_fill_between",
    "example_fill_between_conditional",
    "example_log_scale",
    "example_combined_plot",
    "example_multiple_styles",
    "example_sharex_stacked",
    "example_sharey_sidebyside",
    "example_both_shared",
    "example_residual_plot",
    "example_comparison_with_without",
    "example_side_by_side",
    "example_stacked",
    "example_2x2_grid",
    "example_1x3_comparison",
    "example_errorbar_from_file",
    "example_dual_axis_from_file",
    "example_line_overlay_from_file",
    "example_text_annotations",
    "example_per_element_styling",
    "example_batch_figures",
    "example_line_from_file",
    "example_data_prefix",
    "example_phase_diagram",
    "example_broken_axis_slash",
    "example_broken_axis_line",
    "example_broken_axis_none",
    "example_prl_fig2a_style",
    "example_secondary_yaxis",
    "example_global_config",
    "example_per_figure_config",
    "example_marker_config",
    "example_smooth_curves",
    "example_line_styles",
]

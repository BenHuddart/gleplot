"""Run all gleplot examples."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from basic import (
    example_basic_line_plot,
    example_scatter_plot,
    example_bar_chart,
    example_symmetric_error_bars,
    example_asymmetric_error_bars,
    example_horizontal_error_bars,
)
from advanced import (
    example_fill_between,
    example_log_scale,
    example_combined_plot,
    example_multiple_styles,
    example_sharex_stacked,
    example_sharey_sidebyside,
    example_both_shared,
    example_residual_plot,
    example_comparison_with_without,
)


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("gleplot Examples - Matplotlib-like API for GLE")
    print("="*60 + "\n")
    
    examples = [
        ("Basic Line Plot", example_basic_line_plot),
        ("Scatter Plot", example_scatter_plot),
        ("Bar Chart", example_bar_chart),
        ("Symmetric Error Bars", example_symmetric_error_bars),
        ("Asymmetric Error Bars", example_asymmetric_error_bars),
        ("Horizontal Error Bars", example_horizontal_error_bars),
        ("Fill Between", example_fill_between),
        ("Log Scale", example_log_scale),
        ("Combined Plot", example_combined_plot),
        ("Multiple Styles", example_multiple_styles),
        ("Shared X-Axis (Stacked)", example_sharex_stacked),
        ("Shared Y-Axis (Side-by-side)", example_sharey_sidebyside),
        ("Both Axes Shared (2x2 Grid)", example_both_shared),
        ("Residual Plot Analysis", example_residual_plot),
        ("Comparison: Shared vs Non-shared", example_comparison_with_without),
    ]
    
    for name, example_func in examples:
        try:
            print(f"\n[{name}]")
            example_func()
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("Generated GLE files: example_*.gle")
    print("To compile to PDF: gle example_*.gle -d PDF")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

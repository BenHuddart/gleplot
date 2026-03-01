"""Run all gleplot examples."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from basic import (
    example_basic_line_plot,
    example_scatter_plot,
    example_bar_chart,
)
from advanced import (
    example_fill_between,
    example_log_scale,
    example_combined_plot,
    example_multiple_styles,
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
        ("Fill Between", example_fill_between),
        ("Log Scale", example_log_scale),
        ("Combined Plot", example_combined_plot),
        ("Multiple Styles", example_multiple_styles),
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

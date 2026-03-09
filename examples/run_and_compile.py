"""Run all gleplot examples and compile to multiple formats."""

import sys
import os
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
    example_errorbar_with_line,
    example_combined_errorbars,
)
from advanced import (
    example_fill_between,
    example_fill_between_conditional,
    example_log_scale,
    example_combined_plot,
    example_multiple_styles,
    example_sharex_stacked,
    example_sharey_sidebyside,
    example_both_shared,
    example_residual_plot,
    example_comparison_with_without,
    example_side_by_side,
    example_stacked,
    example_2x2_grid,
    example_1x3_comparison,
    example_errorbar_from_file,
    example_dual_axis_from_file,
)
import gleplot as glp


def main():
    """Run all examples and compile to PDF, EPS, and PNG."""
    # Change to output directory
    output_dir = Path(__file__).parent / 'outputs'
    output_dir.mkdir(exist_ok=True)
    os.chdir(output_dir)
    
    print("\n" + "="*70)
    print("gleplot Examples - Generating Figures")
    print("="*70 + "\n")
    
    examples = [
        ("Basic Line Plot", example_basic_line_plot, "example_basic_line_plot"),
        ("Scatter Plot", example_scatter_plot, "example_scatter_plot"),
        ("Bar Chart", example_bar_chart, "example_bar_chart"),
        ("Symmetric Error Bars", example_symmetric_error_bars, "example_symmetric_error_bars"),
        ("Asymmetric Error Bars", example_asymmetric_error_bars, "example_asymmetric_error_bars"),
        ("Horizontal Error Bars", example_horizontal_error_bars, "example_horizontal_error_bars"),
        ("Error Bars on Line", example_errorbar_with_line, "example_errorbars_line"),
        ("Combined X+Y Error Bars", example_combined_errorbars, "example_combined_errorbars"),
        ("Fill Between", example_fill_between, "example_fill_between"),
        ("Conditional Fill Between", example_fill_between_conditional, "example_fill_between_conditional"),
        ("Log Scale", example_log_scale, "example_log_scale"),
        ("Combined Plot", example_combined_plot, "example_combined_plot"),
        ("Multiple Styles", example_multiple_styles, "example_multiple_styles"),
        ("Side-by-Side Subplots", example_side_by_side, "example_subplots_1x2"),
        ("Stacked Subplots", example_stacked, "example_subplots_2x1"),
        ("2x2 Subplot Grid", example_2x2_grid, "example_subplots_2x2"),
        ("1x3 Comparison", example_1x3_comparison, "example_subplots_1x3"),
        ("Shared X-Axis (Stacked)", example_sharex_stacked, "example_shared_x_axis"),
        ("Shared Y-Axis (Side-by-side)", example_sharey_sidebyside, "example_shared_y_axis"),
        ("Both Axes Shared (2x2 Grid)", example_both_shared, "example_shared_both_axes"),
        ("Residual Plot Analysis", example_residual_plot, "example_residual_plot"),
        ("Comparison: Shared vs Non-shared", example_comparison_with_without, "example_shared_comparison"),
        ("Error bars from file", example_errorbar_from_file, "example_errorbar_from_file"),
        ("Dual axis from file", example_dual_axis_from_file, "example_dual_axis_from_file"),
    ]
    
    # Check if GLE is available
    compiler = None
    try:
        from gleplot.compiler import GLECompiler
        compiler = GLECompiler()
        print(f"✓ GLE compiler found: {compiler.gle_path}\n")
    except Exception as e:
        print(f"✗ GLE compiler not available: {e}")
        print("  Will generate .gle files only (no PDF/EPS/PNG)\n")
    
    success_count = 0
    failed = []
    
    for name, example_func, basename in examples:
        try:
            print(f"[{name}]")
            
            # Run example (creates .gle file)
            example_func()
            
            gle_file = Path(f"{basename}.gle")
            if not gle_file.exists():
                print(f"  ✗ GLE file not created")
                failed.append(name)
                continue
            
            # Rename data files to be example-specific BEFORE compiling
            # This prevents later examples from overwriting data files
            data_files = list(Path('.').glob('data_*.dat'))
            gle_content = gle_file.read_text()
            for data_file in data_files:
                new_name = f"{basename}_{data_file.name}"
                # Update GLE file to reference renamed data file
                gle_content = gle_content.replace(str(data_file.name), new_name)
                # Rename the data file
                data_file.rename(new_name)
            # Write updated GLE file
            gle_file.write_text(gle_content)
            
            # Compile to different formats if GLE is available
            if compiler:
                formats = ['pdf', 'eps', 'png']
                for fmt in formats:
                    try:
                        output = compiler.compile(
                            str(gle_file), 
                            output_format=fmt,
                            dpi=150 if fmt == 'png' else None
                        )
                        size_kb = output.stat().st_size / 1024
                        print(f"  ✓ {fmt.upper()}: {output.name} ({size_kb:.1f} KB)")
                    except Exception as e:
                        print(f"  ✗ {fmt.upper()} compilation failed: {e}")
            
            success_count += 1
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append(name)
            import traceback
            traceback.print_exc()
            print()
    
    # Summary
    print("="*70)
    print(f"Results: {success_count}/{len(examples)} examples completed")
    
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
    
    print(f"\nOutput directory: {output_dir}")
    print(f"Files generated:")
    
    # List all generated files
    all_files = sorted(output_dir.glob('example_*'))
    if all_files:
        by_ext = {}
        for f in all_files:
            ext = f.suffix
            if ext not in by_ext:
                by_ext[ext] = []
            by_ext[ext].append(f.name)
        
        for ext in ['.gle', '.pdf', '.eps', '.png']:
            if ext in by_ext:
                print(f"  {ext}: {len(by_ext[ext])} files")
    else:
        print("  (none)")
    
    print("="*70 + "\n")


if __name__ == '__main__':
    main()

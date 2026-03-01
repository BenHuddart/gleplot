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
)
from advanced import (
    example_fill_between,
    example_log_scale,
    example_combined_plot,
    example_multiple_styles,
)
import gleplot as glp


def main():
    """Run all examples and compile to PDF, EPS, and PNG."""
    # Change to output directory
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    os.chdir(output_dir)
    
    print("\n" + "="*70)
    print("gleplot Examples - Generating Figures")
    print("="*70 + "\n")
    
    examples = [
        ("Basic Line Plot", example_basic_line_plot, "example_basic_line_plot"),
        ("Scatter Plot", example_scatter_plot, "example_scatter_plot"),
        ("Bar Chart", example_bar_chart, "example_bar_chart"),
        ("Fill Between", example_fill_between, "example_fill_between"),
        ("Log Scale", example_log_scale, "example_log_scale"),
        ("Combined Plot", example_combined_plot, "example_combined_plot"),
        ("Multiple Styles", example_multiple_styles, "example_multiple_styles"),
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

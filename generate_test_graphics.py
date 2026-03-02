#!/usr/bin/env python
"""Generate graphics files for inspection.

This script runs various gleplot tests and examples, saving all
generated graphics files to the test_graphics_output directory
for manual inspection.
"""

import sys
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import gleplot as glp

output_dir = Path(__file__).parent / 'test_graphics_output'
output_dir.mkdir(exist_ok=True)

print("=" * 70)
print("Generating Test Graphics for Inspection")
print("=" * 70)
print(f"\nOutput directory: {output_dir.absolute()}\n")


def test_basic_line_plot():
    """Test basic line plot."""
    print("1. Basic line plot...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 10, 100)
    ax.plot(x, np.sin(x), color='blue', label='sin(x)', linewidth=2)
    ax.plot(x, np.cos(x), color='red', linestyle='--', label='cos(x)', linewidth=2)
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Basic Line Plot')
    ax.legend()
    
    fig.savefig(str(output_dir / 'test_01_line_plot.gle'))
    try:
        fig.savefig(str(output_dir / 'test_01_line_plot.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE (PDF compilation requires GLE)")


def test_scatter_plot():
    """Test scatter plot."""
    print("2. Scatter plot...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    np.random.seed(42)
    x = np.random.randn(50)
    y = 2 * x + np.random.randn(50) * 0.5
    
    ax.scatter(x, y, color='green', marker='o', label='Data points')
    ax.set_xlabel('X variable')
    ax.set_ylabel('Y variable')
    ax.set_title('Scatter Plot with Correlation')
    ax.legend()
    
    fig.savefig(str(output_dir / 'test_02_scatter.gle'))
    try:
        fig.savefig(str(output_dir / 'test_02_scatter.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_bar_chart():
    """Test bar chart."""
    print("3. Bar chart...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([23, 45, 56, 78, 32])
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    
    ax.bar(categories, values, color=colors)
    ax.set_xlabel('Category')
    ax.set_ylabel('Value')
    ax.set_title('Colorful Bar Chart')
    
    fig.savefig(str(output_dir / 'test_03_bar_chart.gle'))
    try:
        fig.savefig(str(output_dir / 'test_03_bar_chart.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_error_bars():
    """Test error bars."""
    print("4. Error bars...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2.3, 4.5, 3.8, 5.2, 4.9])
    yerr = np.array([0.3, 0.4, 0.2, 0.5, 0.3])
    
    ax.errorbar(x, y, yerr=yerr, marker='o', color='blue', 
                label='Measurements', capsize=5)
    ax.set_xlabel('Measurement number')
    ax.set_ylabel('Value')
    ax.set_title('Data with Error Bars')
    ax.legend()
    
    fig.savefig(str(output_dir / 'test_04_error_bars.gle'))
    try:
        fig.savefig(str(output_dir / 'test_04_error_bars.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_fill_between():
    """Test fill between."""
    print("5. Fill between...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    y_upper = y + 0.3
    y_lower = y - 0.3
    
    ax.fill_between(x, y_lower, y_upper, color='lightblue', alpha=0.5, 
                     label='Uncertainty band')
    ax.plot(x, y, color='blue', linewidth=2, label='Mean')
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Fill Between Example')
    ax.legend()
    
    fig.savefig(str(output_dir / 'test_05_fill_between.gle'))
    try:
        fig.savefig(str(output_dir / 'test_05_fill_between.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_log_scale():
    """Test logarithmic scale."""
    print("6. Log scale...")
    fig = glp.figure(figsize=(6, 4.5))
    ax = fig.add_subplot(111)
    
    x = np.logspace(0, 3, 50)
    y = x ** 2
    
    ax.plot(x, y, color='red', marker='o', markersize=4)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('x (log scale)')
    ax.set_ylabel('y (log scale)')
    ax.set_title('Logarithmic Scale Plot')
    
    fig.savefig(str(output_dir / 'test_06_log_scale.gle'))
    try:
        fig.savefig(str(output_dir / 'test_06_log_scale.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_subplots_basic():
    """Test basic subplots."""
    print("7. Basic subplots (2x2)...")
    fig, axes = glp.subplots(2, 2, figsize=(8, 7))
    
    x = np.linspace(0, 2*np.pi, 100)
    
    axes[0].plot(x, np.sin(x), color='blue')
    axes[0].set_title('sin(x)')
    
    axes[1].plot(x, np.cos(x), color='red')
    axes[1].set_title('cos(x)')
    
    axes[2].plot(x, np.tan(x), color='green')
    axes[2].set_title('tan(x)')
    axes[2].set_ylim(-5, 5)
    
    axes[3].plot(x, np.sin(x) * np.cos(x), color='purple')
    axes[3].set_title('sin(x)·cos(x)')
    
    fig.savefig(str(output_dir / 'test_07_subplots_basic.gle'))
    try:
        fig.savefig(str(output_dir / 'test_07_subplots_basic.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_shared_x_axis():
    """Test shared x-axis."""
    print("8. Shared x-axis subplots...")
    fig, axes = glp.subplots(3, 1, sharex=True, figsize=(7, 9))
    
    x = np.linspace(0, 10, 100)
    
    axes[0].plot(x, np.sin(x), color='blue', label='Signal A')
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title('Shared X-Axis Example')
    axes[0].legend()
    
    axes[1].plot(x, np.sin(2*x), color='red', label='Signal B')
    axes[1].set_ylabel('Amplitude')
    axes[1].legend()
    
    axes[2].plot(x, np.sin(x) + np.sin(2*x), color='green', label='Combined')
    axes[2].set_xlabel('Time (s)')
    axes[2].set_ylabel('Amplitude')
    axes[2].legend()
    
    fig.savefig(str(output_dir / 'test_08_shared_x_axis.gle'))
    try:
        fig.savefig(str(output_dir / 'test_08_shared_x_axis.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_shared_y_axis():
    """Test shared y-axis."""
    print("9. Shared y-axis subplots...")
    fig, axes = glp.subplots(1, 3, sharey=True, figsize=(12, 4.5))
    
    x1 = np.linspace(0, 5, 50)
    x2 = np.linspace(0, 5, 50)
    x3 = np.linspace(0, 5, 50)
    
    axes[0].scatter(x1, x1**2, color='blue', marker='o')
    axes[0].set_xlabel('Input A')
    axes[0].set_ylabel('Response')
    axes[0].set_title('Condition A')
    
    axes[1].scatter(x2, 1.5*x2**2, color='red', marker='s')
    axes[1].set_xlabel('Input B')
    axes[1].set_title('Condition B')
    
    axes[2].scatter(x3, 0.8*x3**2, color='green', marker='^')
    axes[2].set_xlabel('Input C')
    axes[2].set_title('Condition C')
    
    fig.savefig(str(output_dir / 'test_09_shared_y_axis.gle'))
    try:
        fig.savefig(str(output_dir / 'test_09_shared_y_axis.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_shared_both_axes():
    """Test with both axes shared."""
    print("10. Both axes shared (2x2)...")
    fig, axes = glp.subplots(2, 2, sharex=True, sharey=True, figsize=(7, 6))
    
    x = np.linspace(-3, 3, 60)
    
    axes[0].plot(x, x, color='blue', label='y=x')
    axes[0].set_ylabel('y')
    axes[0].set_title('Linear')
    axes[0].legend()
    
    axes[1].plot(x, x**2 - 5, color='red', label='y=x²-5')
    axes[1].set_title('Quadratic')
    axes[1].legend()
    
    axes[2].plot(x, 0.3*x**3, color='green', label='y=0.3x³')
    axes[2].set_xlabel('x')
    axes[2].set_ylabel('y')
    axes[2].set_title('Cubic')
    axes[2].legend()
    
    axes[3].plot(x, 8*np.sin(x), color='purple', label='y=8sin(x)')
    axes[3].set_xlabel('x')
    axes[3].set_title('Sine')
    axes[3].legend()
    
    fig.savefig(str(output_dir / 'test_10_shared_both.gle'))
    try:
        fig.savefig(str(output_dir / 'test_10_shared_both.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def test_complex_combined():
    """Test complex combined plot."""
    print("11. Complex combined plot...")
    fig = glp.figure(figsize=(7, 6))
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)
    
    # Fill between
    ax.fill_between(x, y1, y2, where=(y1 >= y2), color='lightblue', 
                     alpha=0.3, label='sin > cos')
    ax.fill_between(x, y1, y2, where=(y1 < y2), color='lightcoral', 
                     alpha=0.3, label='cos > sin')
    
    # Lines
    ax.plot(x, y1, color='blue', linewidth=2, label='sin(x)')
    ax.plot(x, y2, color='red', linewidth=2, linestyle='--', label='cos(x)')
    
    # Scatter at intersections
    intersections_x = [np.pi/4, 5*np.pi/4]
    intersections_y = [np.sin(np.pi/4), np.sin(5*np.pi/4)]
    ax.scatter(intersections_x, intersections_y, color='black', 
               marker='o', s=100, zorder=5, label='Intersections')
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Complex Combined Plot')
    ax.legend()
    ax.set_xlim(0, 10)
    
    fig.savefig(str(output_dir / 'test_11_complex_combined.gle'))
    try:
        fig.savefig(str(output_dir / 'test_11_complex_combined.pdf'))
        print("   ✓ Saved GLE and PDF")
    except:
        print("   ✓ Saved GLE")


def main():
    """Run all test graphics generation."""
    tests = [
        test_basic_line_plot,
        test_scatter_plot,
        test_bar_chart,
        test_error_bars,
        test_fill_between,
        test_log_scale,
        test_subplots_basic,
        test_shared_x_axis,
        test_shared_y_axis,
        test_shared_both_axes,
        test_complex_combined,
    ]
    
    for test_func in tests:
        try:
            test_func()
            glp.close()
        except Exception as e:
            print(f"   ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Graphics Generation Complete!")
    print("=" * 70)
    print(f"\nAll files saved to: {output_dir.absolute()}")
    print("\nGenerated files:")
    
    gle_files = sorted(output_dir.glob("*.gle"))
    pdf_files = sorted(output_dir.glob("*.pdf"))
    
    print(f"  • {len(gle_files)} GLE scripts")
    print(f"  • {len(pdf_files)} PDF files")
    
    print("\nTo view GLE scripts:")
    print("  cat test_graphics_output/test_*.gle")
    
    print("\nTo compile individual GLE files:")
    print("  gle test_graphics_output/test_01_line_plot.gle -d pdf")
    
    print("\nTo compile all GLE files:")
    print("  for f in test_graphics_output/*.gle; do gle $f -d pdf; done")
    print()


if __name__ == '__main__':
    main()

"""
gleplot Examples - Demonstrating the matplotlib-like API for GLE plotting
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import gleplot as glp


def example_1_basic_line_plot():
    """Example 1: Basic line plotting."""
    print("Creating example 1: Basic line plot...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Create data
    x = np.linspace(0, 2*np.pi, 100)
    y_sin = np.sin(x)
    y_cos = np.cos(x)
    
    # Plot
    ax.plot(x, y_sin, color='blue', label='sin(x)', linestyle='-')
    ax.plot(x, y_cos, color='red', label='cos(x)', linestyle='--')
    
    # Labels and title
    ax.set_xlabel('x (radians)')
    ax.set_ylabel('y')
    ax.set_title('Sine and Cosine Functions')
    ax.legend()
    
    # Save
    fig.savefig('example_1_lines.gle')
    print("  ✓ Saved to example_1_lines.gle")


def example_2_scatter_plot():
    """Example 2: Scatter plots."""
    print("Creating example 2: Scatter plot...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Create random data
    np.random.seed(42)
    n = 50
    x = np.random.randn(n)
    y = 2*x + np.random.randn(n) * 0.5
    
    # Scatter plot
    ax.scatter(x, y, color='blue', s=20, marker='o', label='Data points')
    
    # Add trend line
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, p(x_line), color='red', linestyle='--', label='Trend')
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_title('Scatter Plot with Trend Line')
    ax.legend()
    
    fig.savefig('example_2_scatter.gle')
    print("  ✓ Saved to example_2_scatter.gle")


def example_3_bar_chart():
    """Example 3: Bar charts."""
    print("Creating example 3: Bar chart...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Data
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([10, 24, 36, 18, 7])
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    
    # Bar chart
    ax.bar(categories, values, color=colors, label='Values')
    
    ax.set_xlabel('Category')
    ax.set_ylabel('Value')
    ax.set_title('Bar Chart Example')
    ax.legend()
    
    fig.savefig('example_3_bars.gle')
    print("  ✓ Saved to example_3_bars.gle")


def example_4_fill_between():
    """Example 4: Fill between curves."""
    print("Creating example 4: Fill between...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Create data
    x = np.linspace(0, 2*np.pi, 100)
    y_upper = np.sin(x) + 0.5
    y_lower = np.sin(x) - 0.5
    
    # Fill between
    ax.fill_between(x, y_lower, y_upper, color='lightblue', alpha=0.5, label='±0.5')
    
    # Plot center line
    ax.plot(x, np.sin(x), color='blue', label='sin(x)')
    
    ax.set_xlabel('x (radians)')
    ax.set_ylabel('y')
    ax.set_title('Fill Between Curves')
    ax.legend()
    
    fig.savefig('example_4_fill.gle')
    print("  ✓ Saved to example_4_fill.gle")


def example_5_log_scale():
    """Example 5: Logarithmic scaling."""
    print("Creating example 5: Log scale...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Data that works well with log scale
    x = np.logspace(0, 3, 50)  # 10^0 to 10^3
    y = x**2
    
    # Plot
    ax.plot(x, y, color='blue', marker='o', linestyle='-', label='y = x²')
    
    # Set log scales
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    ax.set_xlabel('x (log scale)')
    ax.set_ylabel('y (log scale)')
    ax.set_title('Log-Log Plot')
    ax.legend()
    
    fig.savefig('example_5_loglog.gle')
    print("  ✓ Saved to example_5_loglog.gle")


def example_6_combined_plot():
    """Example 6: Combined plot types."""
    print("Creating example 6: Combined plot types...")
    
    fig = glp.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    
    # Data
    x = np.linspace(0, 10, 50)
    y_line = 0.5 * x + 2
    y_upper = y_line + np.random.randn(len(x)) * 0.5 + 0.5
    y_lower = y_line - np.random.randn(len(x)) * 0.5 - 0.5
    
    # Fill between (background)
    ax.fill_between(x, y_lower, y_upper, color='lightgreen', alpha=0.3)
    
    # Plot line
    ax.plot(x, y_line, color='darkgreen', linewidth=2, label='Linear fit')
    
    # Scatter points
    np.random.seed(42)
    x_scatter = np.random.uniform(0, 10, 20)
    y_scatter = 0.5 * x_scatter + 2 + np.random.randn(20) * 1.5
    ax.scatter(x_scatter, y_scatter, color='red', marker='o', s=30, label='Data points')
    
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_title('Combined Plot: Lines, Scatter, and Fill')
    ax.legend(loc='upper left')
    ax.set_xlim(-0.5, 10.5)
    
    fig.savefig('example_6_combined.gle')
    print("  ✓ Saved to example_6_combined.gle")


def example_7_multiple_styles():
    """Example 7: Multiple line styles and markers."""
    print("Creating example 7: Multiple styles...")
    
    fig = glp.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 10, 30)
    
    # Different line styles
    ax.plot(x, x, color='blue', linestyle='-', label='solid')
    ax.plot(x, 2*x, color='red', linestyle='--', label='dashed')
    ax.plot(x, 3*x, color='green', linestyle=':', label='dotted')
    ax.plot(x, 4*x, color='orange', linestyle='-.', label='dash-dot')
    
    # Scatter with markers
    ax.scatter(x[::3], 5*x[::3], color='purple', marker='o', s=40, label='markers')
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Line Styles and Markers')
    ax.legend()
    
    fig.savefig('example_7_styles.gle')
    print("  ✓ Saved to example_7_styles.gle")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("gleplot Examples - Matplotlib-like API for GLE")
    print("="*60 + "\n")
    
    examples = [
        example_1_basic_line_plot,
        example_2_scatter_plot,
        example_3_bar_chart,
        example_4_fill_between,
        example_5_log_scale,
        example_6_combined_plot,
        example_7_multiple_styles,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("Generated GLE files: example_*.gle")
    print("To compile to PDF: gle example_*.gle -d PDF")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()

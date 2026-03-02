"""Shared axes examples.

Demonstrates how to create multi-panel figures with shared x or y axes
for tighter, more professional layouts. When axes are shared, interior
subplots omit redundant labels and ticks, and spacing is automatically
reduced for a cleaner appearance.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_sharex_stacked():
    """Example: Stacked plots with shared x-axis."""
    print("Creating example: Stacked plots with shared x-axis...")
    
    # Shared x-axis is ideal for time series or data at the same x positions
    fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 10))
    
    x = np.linspace(0, 10, 100)
    
    # Top: Signal
    signal = np.sin(2 * np.pi * 0.5 * x) * np.exp(-x / 10)
    axes[0].plot(x, signal, color='blue', label='Signal')
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title('Signal Analysis with Shared X-Axis')
    axes[0].legend()
    axes[0].set_ylim(-1.2, 1.2)
    
    # Middle: Noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.1, len(x))
    axes[1].plot(x, noise, color='gray', linewidth=0.5, label='Noise')
    axes[1].set_ylabel('Noise')
    axes[1].legend()
    axes[1].set_ylim(-0.5, 0.5)
    
    # Bottom: Signal + Noise
    combined = signal + noise
    axes[2].plot(x, combined, color='green', label='Combined')
    axes[2].set_xlabel('Time (s)')  # Only bottom plot shows x-label
    axes[2].set_ylabel('Output')
    axes[2].legend()
    axes[2].set_ylim(-1.5, 1.5)
    
    fig.savefig('example_shared_x_axis.gle')
    print("  ✓ Saved to example_shared_x_axis.gle")


def example_sharey_sidebyside():
    """Example: Side-by-side plots with shared y-axis."""
    print("Creating example: Side-by-side plots with shared y-axis...")
    
    # Shared y-axis is ideal for comparing different conditions at the same scale
    fig, axes = glp.subplots(1, 3, sharey=True, figsize=(18, 5))
    
    x1 = np.linspace(0, 5, 50)
    x2 = np.linspace(0, 5, 50)
    x3 = np.linspace(0, 5, 50)
    
    # Left: Condition A
    y1 = x1**2 + np.random.normal(0, 1, len(x1))
    axes[0].scatter(x1, y1, color='blue', marker='o', label='Condition A')
    axes[0].set_xlabel('Input A')
    axes[0].set_ylabel('Response')  # Only leftmost shows y-label
    axes[0].set_title('Condition A')
    axes[0].legend()
    
    # Center: Condition B
    y2 = 1.5 * x2**2 + np.random.normal(0, 1.5, len(x2))
    axes[1].scatter(x2, y2, color='red', marker='s', label='Condition B')
    axes[1].set_xlabel('Input B')
    axes[1].set_title('Condition B')
    axes[1].legend()
    
    # Right: Condition C
    y3 = 0.8 * x3**2 + np.random.normal(0, 0.8, len(x3))
    axes[2].scatter(x3, y3, color='green', marker='^', label='Condition C')
    axes[2].set_xlabel('Input C')
    axes[2].set_title('Condition C')
    axes[2].legend()
    
    fig.savefig('example_shared_y_axis.gle')
    print("  ✓ Saved to example_shared_y_axis.gle")


def example_both_shared():
    """Example: 2x2 grid with both axes shared."""
    print("Creating example: 2x2 grid with both axes shared...")
    
    # Sharing both axes creates a very tight, unified layout
    fig, axes = glp.subplots(2, 2, sharex=True, sharey=True, figsize=(10, 8))
    
    x = np.linspace(-3, 3, 60)
    
    # Different transformations of the same data
    # Top-left: Linear
    y1 = x
    axes[0].plot(x, y1, color='blue', label='y = x')
    axes[0].set_ylabel('y')  # Only left column shows y-label
    axes[0].set_title('Linear')
    axes[0].legend()
    
    # Top-right: Quadratic
    y2 = x**2 - 5
    axes[1].plot(x, y2, color='red', label='y = x²-5')
    axes[1].set_title('Quadratic')
    axes[1].legend()
    
    # Bottom-left: Cubic
    y3 = 0.3 * x**3
    axes[2].plot(x, y3, color='green', label='y = 0.3x³')
    axes[2].set_xlabel('x')  # Only bottom row shows x-label
    axes[2].set_ylabel('y')
    axes[2].set_title('Cubic')
    axes[2].legend()
    
    # Bottom-right: Sine
    y4 = 8 * np.sin(x)
    axes[3].plot(x, y4, color='purple', label='y = 8sin(x)')
    axes[3].set_xlabel('x')
    axes[3].set_title('Sine')
    axes[3].legend()
    
    fig.savefig('example_shared_both_axes.gle')
    print("  ✓ Saved to example_shared_both_axes.gle")


def example_residual_plot():
    """Example: Data and residuals with shared x-axis (common in data analysis)."""
    print("Creating example: Data with residuals (shared x-axis)...")
    
    fig, axes = glp.subplots(2, 1, sharex=True, figsize=(10, 8))
    
    # Generate data with a linear trend and scatter
    np.random.seed(123)
    x = np.linspace(0, 10, 50)
    y_true = 2.5 * x + 5
    y_measured = y_true + np.random.normal(0, 2, len(x))
    
    # Top: Data with fit
    axes[0].scatter(x, y_measured, color='blue', marker='o', label='Measured')
    axes[0].plot(x, y_true, color='red', linewidth=2, linestyle='--', label='Fit: y=2.5x+5')
    axes[0].set_ylabel('Value')
    axes[0].set_title('Linear Regression with Residual Analysis')
    axes[0].legend()
    
    # Bottom: Residuals
    residuals = y_measured - y_true
    axes[1].scatter(x, residuals, color='green', marker='o')
    axes[1].plot(x, np.zeros_like(x), color='black', linestyle='--', linewidth=1)
    axes[1].set_xlabel('x')
    axes[1].set_ylabel('Residual')
    axes[1].set_title('Residuals')
    
    fig.savefig('example_residual_analysis.gle')
    print("  ✓ Saved to example_residual_analysis.gle")


def example_comparison_with_without():
    """Example: Direct comparison showing benefit of shared axes."""
    print("Creating example: Comparison (with vs without shared axes)...")
    
    # Without shared axes (standard spacing)
    print("  Creating without shared axes...")
    fig1, axes1 = glp.subplots(3, 1, sharex=False, figsize=(8, 12))
    
    x = np.linspace(0, 2*np.pi, 80)
    
    axes1[0].plot(x, np.sin(x), color='blue')
    axes1[0].set_xlabel('x')
    axes1[0].set_ylabel('sin(x)')
    axes1[0].set_title('Without Shared Axes')
    
    axes1[1].plot(x, np.cos(x), color='red')
    axes1[1].set_xlabel('x')
    axes1[1].set_ylabel('cos(x)')
    
    axes1[2].plot(x, np.tan(np.clip(x, -np.pi/2.2, np.pi/2.2)), color='green')
    axes1[2].set_xlabel('x')
    axes1[2].set_ylabel('tan(x)')
    axes1[2].set_ylim(-5, 5)
    
    fig1.savefig('example_without_shared_axes.gle')
    print("    ✓ Saved to example_without_shared_axes.gle")
    
    # With shared x-axis (tighter, cleaner)
    print("  Creating with shared x-axis...")
    fig2, axes2 = glp.subplots(3, 1, sharex=True, figsize=(8, 12))
    
    axes2[0].plot(x, np.sin(x), color='blue')
    axes2[0].set_ylabel('sin(x)')
    axes2[0].set_title('With Shared X-Axis')
    
    axes2[1].plot(x, np.cos(x), color='red')
    axes2[1].set_ylabel('cos(x)')
    
    axes2[2].plot(x, np.tan(np.clip(x, -np.pi/2.2, np.pi/2.2)), color='green')
    axes2[2].set_xlabel('x')  # Only bottom shows x-label
    axes2[2].set_ylabel('tan(x)')
    axes2[2].set_ylim(-5, 5)
    
    fig2.savefig('example_with_shared_axes.gle')
    print("    ✓ Saved to example_with_shared_axes.gle")


if __name__ == '__main__':
    print("=" * 60)
    print("Shared Axes Examples for gleplot")
    print("=" * 60)
    print()
    
    example_sharex_stacked()
    print()
    
    example_sharey_sidebyside()
    print()
    
    example_both_shared()
    print()
    
    example_residual_plot()
    print()
    
    example_comparison_with_without()
    print()
    
    print("=" * 60)
    print("All shared axes examples created successfully!")
    print("=" * 60)
    print()
    print("Benefits of shared axes:")
    print("  • Tighter layout with reduced spacing")
    print("  • Eliminates redundant labels and ticks")
    print("  • Creates cleaner, more professional figures")
    print("  • Maintains consistent scale across subplots")
    print("  • Ideal for time series, residual plots, and comparisons")

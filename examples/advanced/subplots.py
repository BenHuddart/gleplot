"""Subplot examples.

Demonstrates how to create multi-panel figures using gleplot's subplot
support. Each subplot is a separate GLE graph block positioned with
``amove`` and given explicit dimensions via the ``size`` command.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_side_by_side():
    """Example: Two plots side by side (1x2 grid)."""
    print("Creating example: Side-by-side subplots...")

    fig, axes = glp.subplots(1, 2, figsize=(14, 6))

    x = np.linspace(0, 2 * np.pi, 80)

    # Left: sine
    axes[0].plot(x, np.sin(x), color='blue', label='sin(x)')
    axes[0].set_xlabel('x (radians)')
    axes[0].set_ylabel('y')
    axes[0].set_title('Sine')
    axes[0].legend()

    # Right: cosine
    axes[1].plot(x, np.cos(x), color='red', label='cos(x)')
    axes[1].set_xlabel('x (radians)')
    axes[1].set_ylabel('y')
    axes[1].set_title('Cosine')
    axes[1].legend()

    fig.savefig('example_subplots_1x2.gle')
    print("  ✓ Saved to example_subplots_1x2.gle")


def example_stacked():
    """Example: Two plots stacked vertically (2x1 grid)."""
    print("Creating example: Stacked subplots...")

    fig, axes = glp.subplots(2, 1, figsize=(8, 10))

    x = np.linspace(0, 10, 60)

    # Top: linear data with error bars
    y1 = 2 * x + 3 + np.random.default_rng(42).normal(0, 1, len(x))
    axes[0].errorbar(x, y1, yerr=1.0, marker='o', fmt='none', color='blue',
                     label='Measurements')
    axes[0].plot(x, 2 * x + 3, color='red', linestyle='--', label='Fit')
    axes[0].set_xlabel('x')
    axes[0].set_ylabel('y')
    axes[0].set_title('Linear Fit with Error Bars')
    axes[0].legend()

    # Bottom: residuals
    residuals = y1 - (2 * x + 3)
    axes[1].scatter(x, residuals, color='green', marker='o')
    axes[1].set_xlabel('x')
    axes[1].set_ylabel('Residual')
    axes[1].set_title('Residuals')
    axes[1].set_ylim(-4, 4)

    fig.savefig('example_subplots_2x1.gle')
    print("  ✓ Saved to example_subplots_2x1.gle")


def example_2x2_grid():
    """Example: 2x2 grid with different plot types."""
    print("Creating example: 2x2 subplot grid...")

    fig, axes = glp.subplots(2, 2, figsize=(12, 10))

    x = np.linspace(0, 2 * np.pi, 50)

    # Top-left: line plot
    axes[0].plot(x, np.sin(x), color='blue', label='sin')
    axes[0].plot(x, np.cos(x), color='red', linestyle='--', label='cos')
    axes[0].set_title('Trig Functions')
    axes[0].set_xlabel('x')
    axes[0].set_ylabel('y')
    axes[0].legend()

    # Top-right: scatter
    np.random.seed(42)
    xs = np.random.randn(40)
    ys = 0.8 * xs + np.random.randn(40) * 0.3
    axes[1].scatter(xs, ys, color='green', marker='o', label='Data')
    axes[1].set_title('Correlation')
    axes[1].set_xlabel('x')
    axes[1].set_ylabel('y')

    # Bottom-left: bar chart
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([12, 25, 18, 30, 22])
    axes[2].bar(categories, values, color='blue')
    axes[2].set_title('Bar Chart')
    axes[2].set_xlabel('Category')
    axes[2].set_ylabel('Count')

    # Bottom-right: error bars
    xm = np.array([1, 2, 3, 4, 5])
    ym = np.array([10, 18, 25, 35, 42])
    axes[3].errorbar(xm, ym, yerr=([2, 3, 2, 4, 3], [3, 2, 4, 3, 5]),
                     marker='s', fmt='none', color='red', capsize=3,
                     label='±err')
    axes[3].set_title('Error Bars')
    axes[3].set_xlabel('x')
    axes[3].set_ylabel('y')
    axes[3].legend()

    fig.savefig('example_subplots_2x2.gle')
    print("  ✓ Saved to example_subplots_2x2.gle")


def example_1x3_comparison():
    """Example: 1x3 grid comparing function transformations."""
    print("Creating example: 1x3 comparison...")

    fig, axes = glp.subplots(1, 3, figsize=(18, 5))

    x = np.linspace(0.1, 5, 80)

    axes[0].plot(x, x, color='blue', label='y = x')
    axes[0].plot(x, x**2, color='red', linestyle='--', label='y = x²')
    axes[0].set_title('Polynomial')
    axes[0].set_xlabel('x')
    axes[0].legend()

    axes[1].plot(x, np.log(x), color='green', label='y = ln(x)')
    axes[1].plot(x, np.sqrt(x), color='blue', linestyle='--',
                 label='y = √x')
    axes[1].set_title('Roots & Logs')
    axes[1].set_xlabel('x')
    axes[1].legend()

    axes[2].plot(x, np.exp(-x), color='red', label='y = e⁻ˣ')
    axes[2].plot(x, 1 / x, color='blue', linestyle=':', label='y = 1/x')
    axes[2].set_title('Decay Functions')
    axes[2].set_xlabel('x')
    axes[2].set_ylim(0, 5)
    axes[2].legend()

    fig.savefig('example_subplots_1x3.gle')
    print("  ✓ Saved to example_subplots_1x3.gle")


if __name__ == '__main__':
    example_side_by_side()
    example_stacked()
    example_2x2_grid()
    example_1x3_comparison()
    print("\nAll subplot examples created.")

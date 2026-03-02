"""Error bar plot examples.

Demonstrates how to create plots with error bars using gleplot,
including symmetric, asymmetric, and horizontal error bars.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_symmetric_error_bars():
    """Example: Simple symmetric vertical error bars."""
    print("Creating example: Symmetric error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    # Experimental data with constant uncertainty
    x = np.array([1, 2, 3, 4, 5, 6, 7, 8])
    y = np.array([2.1, 3.9, 6.2, 7.8, 10.1, 12.3, 13.8, 16.2])

    ax.errorbar(x, y, yerr=0.5, marker='o', fmt='-', color='blue',
                label='Measurement')

    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Distance (m)')
    ax.set_title('Symmetric Error Bars')
    ax.legend()

    fig.savefig('example_symmetric_errorbars.gle')
    print("  ✓ Saved to example_symmetric_errorbars.gle")


def example_asymmetric_error_bars():
    """Example: Asymmetric vertical error bars (different up/down)."""
    print("Creating example: Asymmetric error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([10, 25, 40, 55, 70])

    # Different upper and lower error magnitudes
    yerr_lower = np.array([2, 3, 4, 5, 3])
    yerr_upper = np.array([5, 4, 6, 3, 7])

    ax.errorbar(x, y, yerr=(yerr_lower, yerr_upper), marker='s',
                fmt='none', color='red', capsize=4, label='Asymmetric')

    ax.set_xlabel('Category')
    ax.set_ylabel('Value')
    ax.set_title('Asymmetric Error Bars')
    ax.legend()

    fig.savefig('example_asymmetric_errorbars.gle')
    print("  ✓ Saved to example_asymmetric_errorbars.gle")


def example_horizontal_error_bars():
    """Example: Both vertical and horizontal error bars."""
    print("Creating example: Horizontal + vertical error bars...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    np.random.seed(42)
    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2.5, 4.0, 3.5, 5.0, 6.5])

    # Vertical and horizontal uncertainties
    yerr = np.array([0.4, 0.3, 0.5, 0.3, 0.4])
    xerr = np.array([0.2, 0.3, 0.15, 0.25, 0.2])

    ax.errorbar(x, y, yerr=yerr, xerr=xerr, marker='o', fmt='none',
                color='blue', capsize=3, label='Data ± σ')

    ax.set_xlabel('X measurement')
    ax.set_ylabel('Y measurement')
    ax.set_title('Horizontal and Vertical Error Bars')
    ax.legend()

    fig.savefig('example_hv_errorbars.gle')
    print("  ✓ Saved to example_hv_errorbars.gle")


def example_errorbar_with_line():
    """Example: Error bars on a line plot (connect points)."""
    print("Creating example: Error bars with line...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.linspace(0, 2 * np.pi, 12)
    y = np.sin(x)

    # Error varies with the measurement
    yerr = 0.1 + 0.1 * np.abs(np.cos(x))

    ax.errorbar(x, y, yerr=yerr, marker='o', fmt='-', color='green',
                capsize=3, label='sin(x) ± δ')

    ax.set_xlabel('x (radians)')
    ax.set_ylabel('sin(x)')
    ax.set_title('Error Bars on Line Plot')
    ax.legend()

    fig.savefig('example_errorbars_line.gle')
    print("  ✓ Saved to example_errorbars_line.gle")


if __name__ == '__main__':
    example_symmetric_error_bars()
    example_asymmetric_error_bars()
    example_horizontal_error_bars()
    example_errorbar_with_line()
    print("\nAll error bar examples created.")

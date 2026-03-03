"""
Example demonstrating the view() function for displaying plots inline.

This example shows how to use the view() function to display plots
in Jupyter notebooks or save to temporary files.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import gleplot as glp


def example_view_basic():
    """Example: Basic usage of view() function."""
    print("Creating a basic plot with view()...")
    
    # Create figure and plot
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Create data
    x = np.linspace(0, 2*np.pi, 100)
    y = np.sin(x)
    
    # Plot
    ax.plot(x, y, color='blue', label='sin(x)')
    ax.set_xlabel('x (radians)')
    ax.set_ylabel('y')
    ax.set_title('Sine Function')
    ax.legend()
    
    # View the plot (displays inline in Jupyter or saves to temp file)
    result = fig.view()
    print(f"View result: {result}")
    

def example_view_with_options():
    """Example: Using view() with custom DPI."""
    print("\nCreating a high-resolution plot with view(dpi=300)...")
    
    # Create a scatter plot
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    np.random.seed(42)
    x = np.random.randn(50)
    y = 2*x + np.random.randn(50) * 0.5
    
    ax.scatter(x, y, color='red', s=20, marker='o')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_title('Scatter Plot (High DPI)')
    
    # View with custom DPI
    result = fig.view(dpi=300)
    print(f"View result: {result}")


def example_module_level_view():
    """Example: Using module-level view() function."""
    print("\nUsing module-level glp.view() function...")
    
    # Use matplotlib-style API
    fig, ax = glp.subplots()
    
    x = [1, 2, 3, 4, 5]
    y = [1, 4, 9, 16, 25]
    
    ax.plot(x, y, 'b-o', label='quadratic')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_title('Module-level view() Demo')
    ax.legend()
    
    # Use module-level view function
    result = glp.view()
    print(f"View result: {result}")


if __name__ == '__main__':
    print("=" * 60)
    print("gleplot view() Function Examples")
    print("=" * 60)
    
    try:
        example_view_basic()
    except Exception as e:
        print(f"Error in example_view_basic(): {e}")
    
    try:
        example_view_with_options()
    except Exception as e:
        print(f"Error in example_view_with_options(): {e}")
    
    try:
        example_module_level_view()
    except Exception as e:
        print(f"Error in example_module_level_view(): {e}")
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)

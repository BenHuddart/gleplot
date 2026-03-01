"""Scatter plot example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_scatter_plot():
    """Example: Scatter plots with trend line."""
    print("Creating example: Scatter plot...")
    
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
    
    fig.savefig('example_scatter_plot.gle')
    print("  ✓ Saved to example_scatter_plot.gle")


if __name__ == '__main__':
    example_scatter_plot()

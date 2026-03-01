"""Combined plot types example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_combined_plot():
    """Example: Combined plot types."""
    print("Creating example: Combined plot types...")
    
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
    
    fig.savefig('example_combined_plot.gle')
    print("  ✓ Saved to example_combined_plot.gle")


if __name__ == '__main__':
    example_combined_plot()

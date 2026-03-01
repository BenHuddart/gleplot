"""Basic line plotting example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_basic_line_plot():
    """Example: Basic line plotting with multiple series."""
    print("Creating example: Basic line plot...")
    
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
    fig.savefig('example_basic_line_plot.gle')
    print("  ✓ Saved to example_basic_line_plot.gle")


if __name__ == '__main__':
    example_basic_line_plot()

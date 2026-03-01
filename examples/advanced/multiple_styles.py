"""Multiple line styles and markers example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_multiple_styles():
    """Example: Multiple line styles and markers."""
    print("Creating example: Multiple styles...")
    
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
    
    fig.savefig('example_multiple_styles.gle')
    print("  ✓ Saved to example_multiple_styles.gle")


if __name__ == '__main__':
    example_multiple_styles()

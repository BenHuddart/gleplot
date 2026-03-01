"""Fill between curves example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_fill_between():
    """Example: Fill between curves."""
    print("Creating example: Fill between...")
    
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
    
    fig.savefig('example_fill_between.gle')
    print("  ✓ Saved to example_fill_between.gle")


if __name__ == '__main__':
    example_fill_between()

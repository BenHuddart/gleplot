"""Logarithmic scale example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_log_scale():
    """Example: Logarithmic scaling."""
    print("Creating example: Log scale...")
    
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
    
    fig.savefig('example_log_scale.gle')
    print("  ✓ Saved to example_log_scale.gle")


if __name__ == '__main__':
    example_log_scale()

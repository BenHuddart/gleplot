"""Bar chart example."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_bar_chart():
    """Example: Bar charts with multiple colors."""
    print("Creating example: Bar chart...")
    
    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)
    
    # Data
    categories = np.array([1, 2, 3, 4, 5])
    values = np.array([10, 24, 36, 18, 7])
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    
    # Bar chart
    ax.bar(categories, values, color=colors, label='Values')
    
    ax.set_xlabel('Category')
    ax.set_ylabel('Value')
    ax.set_title('Bar Chart Example')
    ax.legend()
    
    fig.savefig('example_bar_chart.gle')
    print("  ✓ Saved to example_bar_chart.gle")


if __name__ == '__main__':
    example_bar_chart()

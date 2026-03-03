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


def example_fill_between_conditional():
    """Example: Conditional fill_between using where= parameter."""
    print("Creating example: Conditional fill between...")

    fig = glp.figure(figsize=(8, 6))
    ax = fig.add_subplot(111)

    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)

    # Fill above/below zero differently
    ax.fill_between(x, y1, y2, where=(y1 >= y2), color='lightblue',
                    alpha=0.5, label='sin ≥ cos')
    ax.fill_between(x, y1, y2, where=(y1 < y2), color='lightcoral',
                    alpha=0.5, label='sin < cos')

    ax.plot(x, y1, color='blue', linewidth=2, label='sin(x)')
    ax.plot(x, y2, color='red', linewidth=2, linestyle='--', label='cos(x)')

    # Mark intersection points
    intersections_x = [np.pi/4, 5*np.pi/4]
    intersections_y = [np.sin(np.pi/4), np.sin(5*np.pi/4)]
    ax.scatter(intersections_x, intersections_y, color='black',
               marker='o', s=80, label='Intersections')

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Conditional Fill Between')
    ax.legend()
    ax.set_xlim(0, 10)

    fig.savefig('example_fill_between_conditional.gle')
    print("  ✓ Saved to example_fill_between_conditional.gle")


if __name__ == '__main__':
    example_fill_between()
    example_fill_between_conditional()

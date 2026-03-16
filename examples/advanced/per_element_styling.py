"""Per-element styling examples for gleplot."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_per_element_styling():
    """Show style differences applied per plotted element."""
    print("Creating example: Per-element styling...")

    x = np.linspace(0.0, 6.0, 80)

    fig = glp.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)

    ax.plot(x, np.exp(-0.4 * x), color='darkblue', linestyle='-', linewidth=2.2, label='Decay A')
    ax.plot(x, np.exp(-0.25 * x), color='darkgreen', linestyle='--', linewidth=1.8, label='Decay B')
    ax.plot(x, np.exp(-0.15 * x), color='darkred', linestyle=':', linewidth=2.6, label='Decay C')

    sample_x = x[::8]
    sample_y = np.exp(-0.25 * sample_x)
    ax.scatter(sample_x, sample_y, color='orange', marker='s', s=42, label='Sampled points')

    band_low = np.exp(-0.25 * x) - 0.08
    band_high = np.exp(-0.25 * x) + 0.08
    ax.fill_between(x, band_low, band_high, color='lightgreen', alpha=0.35, label='Tolerance band')

    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Response')
    ax.set_title('Per-Element Styling in One Axes')
    ax.legend(loc='top right')

    fig.savefig('example_per_element_styling.gle')
    print('  + Saved to example_per_element_styling.gle')


if __name__ == '__main__':
    example_per_element_styling()

"""Data prefix naming example for gleplot."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_data_prefix():
    """Demonstrate deterministic data sidecar naming with data_prefix."""
    print("Creating example: data_prefix naming...")

    x = np.linspace(0.0, 1.0, 60)

    fig = glp.figure(figsize=(9, 5), data_prefix='experiment_17')
    ax = fig.add_subplot(111)

    ax.plot(x, x, color='blue', linewidth=2, label='linear', data_name='Linear Reference')
    ax.plot(x, x**2, color='red', linestyle='--', linewidth=2, label='quadratic', data_name='Quadratic Reference')
    ax.fill_between(
        x,
        x**2 - 0.04,
        x**2 + 0.04,
        color='pink',
        alpha=0.25,
        label='uncertainty',
        data_name='Quadratic Uncertainty',
    )

    ax.set_xlabel('Normalized input')
    ax.set_ylabel('Response')
    ax.set_title('Custom data_prefix and data_name Output Files')
    ax.legend(loc='top left')

    fig.savefig('example_data_prefix.gle')
    print('  + Saved to example_data_prefix.gle')
    print('  + Sidecar .dat files use experiment_17_* or sanitized data_name labels.')


if __name__ == '__main__':
    example_data_prefix()

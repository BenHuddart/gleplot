"""Batch figure generation example for gleplot."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_batch_figures():
    """Generate a batch of related figures in a loop."""
    print("Creating example: Batch figure generation...")

    out_dir = Path('batch_outputs')
    out_dir.mkdir(exist_ok=True)

    x = np.linspace(0.0, 2.0 * np.pi, 200)
    phases = [0.0, np.pi / 6.0, np.pi / 3.0, np.pi / 2.0]

    for idx, phase in enumerate(phases, start=1):
        fig = glp.figure(figsize=(8, 5), data_prefix=f'batch_{idx}')
        ax = fig.add_subplot(111)

        y = np.sin(x + phase)
        ax.plot(x, y, color='blue', linewidth=2, label=f'phase={phase:.2f}')
        ax.set_xlabel('x')
        ax.set_ylabel('sin(x + phase)')
        ax.set_title(f'Batch Figure {idx}')
        ax.legend(loc='top right')

        output_file = out_dir / f'example_batch_{idx}.gle'
        fig.savefig(str(output_file))
        print(f'  + Saved {output_file}')


if __name__ == '__main__':
    example_batch_figures()

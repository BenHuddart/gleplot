"""Line-from-file examples for gleplot."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_line_from_file():
    """Plot measured points and overlay a model line from one file."""
    print("Creating example: line_from_file...")

    data_file = Path('line_from_file_data.dat')

    with open(data_file, 'w', encoding='utf-8') as handle:
        handle.write('! c1=x  c2=y_measured  c3=y_error  c4=y_model\n')

        np.random.seed(21)
        x = np.linspace(0.0, 10.0, 18)
        y_model = 2.0 + 0.65 * x
        y_error = 0.18 + 0.05 * np.random.rand(len(x))
        y_measured = y_model + np.random.normal(0.0, y_error)

        for xi, yi, ei, mi in zip(x, y_measured, y_error, y_model):
            handle.write(f'{xi:8.3f} {yi:10.4f} {ei:8.4f} {mi:10.4f}\n')

    fig = glp.figure(figsize=(9, 6))
    ax = fig.add_subplot(111)

    ax.errorbar_from_file(
        str(data_file),
        x_col=1,
        y_col=2,
        yerr_col=3,
        color='blue',
        marker='o',
        markersize=5,
        capsize=3,
        label='Measured',
    )

    ax.line_from_file(
        str(data_file),
        x_col=1,
        y_col=4,
        color='red',
        linestyle='--',
        linewidth=2,
        label='Model',
    )

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Line Overlay From Existing Data File')
    ax.legend(loc='top left')

    fig.savefig('example_line_from_file.gle')
    print('  + Saved to example_line_from_file.gle')
    print(f'  + Data file: {data_file}')


if __name__ == '__main__':
    example_line_from_file()

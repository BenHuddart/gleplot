"""Text annotation examples for gleplot."""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_text_annotations():
    """Demonstrate text placement, alignment, and annotation boxes."""
    print("Creating example: Text annotations...")

    x = np.linspace(0.0, 10.0, 200)
    y = np.sin(x)

    fig = glp.figure(figsize=(9, 6))
    ax = fig.add_subplot(111)

    ax.plot(x, y, color='blue', linewidth=2, label='Signal')

    # Mark peak and trough labels with different alignments.
    ax.text(1.57, 1.0, 'Peak', color='darkblue', fontsize=11, ha='center', va='bottom')
    ax.text(4.71, -1.0, 'Trough', color='darkred', fontsize=11, ha='center', va='top')

    # Add an annotation with a boxed background.
    ax.text(
        7.5,
        0.6,
        'Window: 7.0 to 8.0 s',
        color='black',
        fontsize=10,
        ha='left',
        va='center',
        bbox={'fill': 'white', 'line': 'black', 'lw': 0.5},
    )

    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude')
    ax.set_title('Text Annotation Patterns')
    ax.legend(loc='upper right')

    fig.savefig('example_text_annotations.gle')
    print('  + Saved to example_text_annotations.gle')


if __name__ == '__main__':
    example_text_annotations()

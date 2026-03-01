"""
Test suite for gleplot library - DEPRECATED

This file is maintained for backward compatibility only.
Tests have been reorganized into separate modules for better maintainability.

New test structure:
    Unit tests (tests/unit/):
        - test_plotting.py: Line plots, scatter plots, bar charts, fill_between
        - test_axes.py: Axis properties, labels, limits, scales
        - test_utilities.py: Color and marker conversion utilities

    Integration tests (tests/integration/):
        - test_file_io.py: File I/O operations and GLE script generation
        - test_api.py: Figure API and GLE code generation

For new tests, please add them to the appropriate module in the unit/ or integration/
directories rather than adding them here.

To run tests, use:
    pytest tests/
"""

# Import all tests from reorganized modules for backward compatibility
from .unit.test_plotting import (
    TestBasicPlotting,
    TestScatterPlots,
    TestBarCharts,
    TestFillBetween,
)
from .unit.test_axes import TestAxisProperties
from .unit.test_utilities import TestColorMapping, TestMarkerMapping
from .integration.test_file_io import TestFileIO
from .integration.test_api import TestFigureAPI, TestGLEGeneration
from .integration.test_graphics_compilation import (
    TestGraphicsCompilation,
    TestImageProperties,
    TestGraphicsWithAdvancedFeatures,
)
from .integration.test_graphics_validation import (
    TestGraphicsValidation,
    TestGraphicsFormattingConsistency,
)

__all__ = [
    'TestBasicPlotting',
    'TestScatterPlots',
    'TestBarCharts',
    'TestFillBetween',
    'TestAxisProperties',
    'TestColorMapping',
    'TestMarkerMapping',
    'TestFileIO',
    'TestFigureAPI',
    'TestGLEGeneration',
    'TestGraphicsCompilation',
    'TestImageProperties',
    'TestGraphicsWithAdvancedFeatures',
    'TestGraphicsValidation',
    'TestGraphicsFormattingConsistency',
]


def run_tests():
    """Run all tests."""
    import unittest
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()

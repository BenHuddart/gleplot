# Gleplot Test Suite Structure

## Overview
The gleplot test suite has been organized into a comprehensive structure with unit tests, integration tests, and specialized graphics validation tests.

## Directory Structure

```
tests/
├── __init__.py                          # Test package documentation
├── test_gleplot.py                      # Backward compatibility wrapper (23 tests)
│
├── unit/                                # Unit tests (10 tests)
│   ├── __init__.py
│   ├── test_plotting.py                 # Lines, scatter, bars, fill_between (5 tests)
│   ├── test_axes.py                     # Axis properties (1 test)
│   └── test_utilities.py                # Color & marker utils (4 tests)
│
└── integration/                         # Integration tests (23 tests)
    ├── __init__.py
    ├── test_file_io.py                  # GLE file I/O (3 tests)
    ├── test_api.py                      # Figure API & GLE generation (6 tests)
    ├── test_graphics_compilation.py     # Graphics compilation (13 tests)
    ├── test_graphics_validation.py      # Graphics validation (10 tests)
    ├── graphics_analysis.py             # Image analysis utilities
    └── GRAPHICS_TESTING.md              # Graphics testing user guide
```

## Test Summary by Category

### Unit Tests (10 tests)
Tests individual components in isolation.

#### Plotting Tests (5)
- `TestBasicPlotting`: Line plotting (1)
- `TestScatterPlots`: Scatter plots (1)
- `TestBarCharts`: Bar charts (1)
- `TestFillBetween`: Fill between curves (1)

#### Axis Tests (1)
- `TestAxisProperties`: Axis labels, limits, scales, legend (1)

#### Utility Tests (4)
- `TestColorMapping`: Color conversion (3)
- `TestMarkerMapping`: Marker conversion (1)

### Integration Tests (23 tests)
Tests interaction between components.

#### File I/O Tests (3)
- `TestFileIO`: GLE script saving and content validation

#### API Tests (6)
- `TestFigureAPI`: Figure creation and management (5)
- `TestGLEGeneration`: GLE code generation with features (1)

#### Graphics Compilation Tests (13)
- `TestGraphicsCompilation`: PDF/EPS/PNG compilation (7)
- `TestImageProperties`: File properties validation (3)
- `TestGraphicsWithAdvancedFeatures`: Advanced plot compilation (3)

#### Graphics Validation Tests (10)
- `TestGraphicsValidation`: Structure and metadata validation (9)
- `TestGraphicsFormattingConsistency`: Cross-format consistency (1)

## Total Test Count: 33 Tests

### Breakdown by Format
- GLE script generation: 9 tests
- PDF generation: 6 tests
- EPS generation: 6 tests
- PNG generation: 6 tests
- Cross-format: 2 tests
- Utilities & API: 4 tests

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### By Category
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Graphics tests only
pytest tests/integration/test_graphics_*.py -v
```

### Specific Types
```bash
# File I/O tests
pytest tests/integration/test_file_io.py -v

# Graphics compilation tests
pytest tests/integration/test_graphics_compilation.py -v

# Graphics validation tests
pytest tests/integration/test_graphics_validation.py -v
```

### With Coverage
```bash
pytest tests/ --cov=gleplot --cov-report=html
```

## Test Dependencies

### Required
- `unittest` (Python standard library)
- `numpy` (for example data)
- `gleplot` (the package being tested)

### Optional
- `pytest` (for running tests)
- GLE (Graphics Layout Engine) - for graphics compilation tests
  - Installed automatically in GitHub Actions
  - Manual installation: `brew install gle` (macOS) or `apt-get install gle` (Linux)

## Key Features

### Smart Skipping
Tests that require GLE automatically skip if not available:
```python
try:
    self.compiler = GLECompiler()
    self.gle_available = True
except RuntimeError:
    self.gle_available = False

def test_compile_to_pdf(self):
    if not self.gle_available:
        self.skipTest("GLE compiler not available")
```

### Backward Compatibility
The old `test_gleplot.py` file imports all test classes, allowing:
- Existing test runners to continue working
- Gradual migration to new structure
- Single source of truth for test discovery

### Organized by Functionality
- Unit tests validate individual functions
- Integration tests validate workflows
- Graphics tests validate visual output

## GitHub Actions Integration

The `.github/workflows/test.yml` workflow:
1. Installs GLE on test runners
2. Runs all tests on Ubuntu and macOS
3. Tests with Python 3.9 and 3.11
4. Includes code coverage reporting

Example output:
```
tests/unit/test_plotting.py::TestBasicPlotting::test_simple_line_plot PASSED
tests/integration/test_file_io.py::TestFileIO::test_save_gle_script PASSED
tests/integration/test_graphics_compilation.py::TestGraphicsCompilation::test_compile_to_pdf PASSED
```

## Adding New Tests

### Unit Test
Create in `tests/unit/test_*.py`:
```python
class TestNewFeature(unittest.TestCase):
    def test_something(self):
        # Test code
```

### Integration Test
Create in `tests/integration/test_*.py`:
```python
class TestNewIntegration(unittest.TestCase):
    def test_workflow(self):
        # Integration test code
```

### Update Backward Compatibility
Add import to `tests/test_gleplot.py`:
```python
from unit.test_new import TestNewFeature
```

## Best Practices

1. **Use setUp/tearDown**: Properly initialize and clean up tests
2. **Skip when needed**: Use `self.skipTest()` for optional dependencies
3. **Descriptive names**: Test names should describe what's being tested
4. **One assertion**: Keep tests focused and simple
5. **Temporary files**: Use `tempfile.mkdtemp()` for file-based tests
6. **Clean paths**: Use `Path` instead of string paths

## Test Execution Times

Approximate times on modern hardware:
- Unit tests: < 1 second
- Integration API tests: < 1 second  
- Integration I/O tests: < 1 second
- Graphics compilation tests: 10-30 seconds (depends on GLE availability)
- Graphics validation tests: 5-15 seconds
- **Total: ~20-50 seconds**

## Troubleshooting

### GLE Not Found
```bash
# Check if installed
which gle

# Install if needed
brew install gle          # macOS
apt-get install gle       # Linux
```

### Import Error
Ensure you're running pytest from the workspace root:
```bash
cd /path/to/gleplot
pytest tests/
```

### Test Timeouts
GLE compilation can take time. Check system resources if tests timeout frequently.

## Future Additions

Potential test areas:
- [ ] Command-line interface tests
- [ ] Configuration/settings tests
- [ ] Error handling and edge cases
- [ ] Performance benchmarks
- [ ] Data validation tests

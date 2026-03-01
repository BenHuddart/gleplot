# Test Suite Quick Reference

## Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Graphics tests only
pytest tests/integration/test_graphics_*.py -v

# Specific test file
pytest tests/unit/test_plotting.py -v

# Specific test class
pytest tests/unit/test_plotting.py::TestBasicPlotting -v

# Specific test method
pytest tests/unit/test_plotting.py::TestBasicPlotting::test_simple_line_plot -v

# With coverage report
pytest tests/ --cov=gleplot --cov-report=html

# Verbose with timings
pytest tests/ -v --durations=10
```

## Test Files Overview

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/test_plotting.py` | 5 | Lines, scatter, bars, fill |
| `tests/unit/test_axes.py` | 1 | Axis properties |
| `tests/unit/test_utilities.py` | 4 | Color/marker conversion |
| `tests/integration/test_file_io.py` | 3 | GLE file I/O |
| `tests/integration/test_api.py` | 6 | Figure API & generation |
| `tests/integration/test_graphics_compilation.py` | 13 | PDF/EPS/PNG compilation |
| `tests/integration/test_graphics_validation.py` | 10 | Graphics validation |
| **Total** | **33** | **All feature coverage** |

## Image Analysis Quick Start

```python
from tests.integration.graphics_analysis import (
    PDFAnalyzer, EPSAnalyzer, PNGAnalyzer, validate_graphics_file
)

# Analyze PDF
pdf = PDFAnalyzer('output.pdf')
if pdf.is_valid_pdf():
    print(f"Pages: {pdf.get_page_count()}")

# Analyze EPS
eps = EPSAnalyzer('output.eps')
if eps.is_valid_eps():
    print(f"Bounding box: {eps.get_bounding_box()}")

# Analyze PNG
png = PNGAnalyzer('output.png')
if png.is_valid_png():
    print(f"Dimensions: {png.get_image_dimensions()}")
    print(f"Color depth: {png.get_color_depth()} bits")

# Generic validation
result = validate_graphics_file('output.pdf')
if result['valid']:
    print(f"Valid {result['format']}: {result['size_kb']:.1f} KB")
```

## Common Test Patterns

### Test with GLE Availability Check
```python
def setUp(self):
    try:
        self.compiler = GLECompiler()
        self.gle_available = True
    except RuntimeError:
        self.gle_available = False

def test_compile(self):
    if not self.gle_available:
        self.skipTest("GLE not available")
    # Test code
```

### Create Temporary Files
```python
import tempfile
from pathlib import Path

def setUp(self):
    self.tempdir = Path(tempfile.mkdtemp())

def tearDown(self):
    # Clean up
    for f in self.tempdir.glob('*'):
        f.unlink()
    self.tempdir.rmdir()
```

### Test Plot Creation
```python
def setUp(self):
    glp.close()
    self.fig = glp.figure(figsize=(8, 6))
    self.ax = self.fig.add_subplot(111)

def tearDown(self):
    glp.close()
```

## Test Status

- ✅ Plotting (lines, scatter, bars, fill)
- ✅ Axis properties (labels, limits, scales, legend)
- ✅ Color/marker utilities
- ✅ File I/O (GLE script generation)
- ✅ Figure API
- ✅ GLE code generation
- ✅ Graphics compilation (PDF, EPS, PNG)
- ✅ Graphics validation (structure, metadata, dimensions)
- ✅ Cross-format consistency

## Skip Reasons

Tests automatically skip if:
- `skipTest("GLE compiler not available")` - GLE not installed
- `skipTest("Feature not implemented")` - Feature under development

Example run with skips:
```
PASSED .......................... 30 passed
SKIPPED .......................... 3 skipped
```

## Performance Targets

| Category | Expected Time |
|----------|---------------|
| Unit tests | < 1 sec |
| Integration API tests | < 1 sec |
| Graphics compilation | 10-30 sec |
| Graphics validation | 5-15 sec |
| **Total** | **~20-50 sec** |

## Documentation

- **[TEST_STRUCTURE.md](TEST_STRUCTURE.md)** - Complete test organization
- **[GRAPHICS_TESTING_SUMMARY.md](GRAPHICS_TESTING_SUMMARY.md)** - Graphics test details
- **[GRAPHICS_TESTING.md](GRAPHICS_TESTING.md)** - Graphics testing guide

## Troubleshooting

### Tests fail with import errors
```bash
# Run from workspace root
cd /path/to/gleplot
pytest tests/
```

### GLE compilation tests skipped
```bash
# Install GLE
brew install gle              # macOS
sudo apt-get install gle      # Ubuntu/Debian
```

### Permissions error on temp files
Ensure write permissions to temp directory:
```bash
# Check temp directory
python -c "import tempfile; print(tempfile.gettempdir())"
```

## CI/CD Integration

Tests run automatically on:
- Push to main branch
- Pull requests
- Platforms: Ubuntu, macOS
- Python versions: 3.9, 3.11

View results: `.github/workflows/test.yml`

## Contributing New Tests

1. Choose appropriate file or create new one
2. Follow existing patterns
3. Use descriptive test names
4. Add docstrings
5. Update test imports in `tests/test_gleplot.py`
6. Run full test suite before committing

```bash
pytest tests/ -v --cov=gleplot
```

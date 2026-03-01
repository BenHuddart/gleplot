# Graphics Compilation and Validation Tests

This directory contains comprehensive tests for graphics file generation and validation in gleplot.

## Overview

The graphics testing suite includes:

1. **Graphics Compilation Tests** (`test_graphics_compilation.py`)
   - Tests compilation of GLE scripts to PDF, EPS, and PNG formats
   - Validates file existence, format correctness, and file sizes
   - Tests with various plot types and features

2. **Graphics Validation Tests** (`test_graphics_validation.py`)
   - Advanced validation using image analysis utilities
   - Verifies file structure and integrity
   - Tests formatting consistency across different formats
   - Extracts and validates metadata (page count, bounding box, dimensions, etc.)

3. **Graphics Analysis Module** (`graphics_analysis.py`)
   - `PDFAnalyzer`: Analyze PDF structure and metadata
   - `EPSAnalyzer`: Analyze EPS/PostScript structure
   - `PNGAnalyzer`: Analyze PNG image properties
   - `validate_graphics_file()`: Generic validation helper

## Running the Tests

### All graphics tests
```bash
pytest tests/integration/test_graphics_compilation.py tests/integration/test_graphics_validation.py -v
```

### Specific test class
```bash
pytest tests/integration/test_graphics_compilation.py::TestGraphicsCompilation -v
```

### Specific test
```bash
pytest tests/integration/test_graphics_compilation.py::TestGraphicsCompilation::test_compile_to_pdf -v
```

### With coverage
```bash
pytest tests/integration/test_graphics_*.py --cov=gleplot --cov-report=html
```

## Test Categories

### TestGraphicsCompilation
Tests basic compilation functionality:
- `test_save_gle_script`: GLE file generation
- `test_compile_to_pdf`: PDF compilation
- `test_compile_to_eps`: EPS compilation
- `test_compile_to_png`: PNG compilation with custom DPI
- `test_pdf_contains_elements`: PDF structure validation
- `test_eps_contains_elements`: EPS structure validation
- `test_png_valid_header`: PNG header validation

### TestImageProperties
Tests file size and format properties:
- `test_pdf_file_size_reasonable`: PDF file size validation
- `test_eps_file_size_reasonable`: EPS file size validation
- `test_png_file_size_reasonable`: PNG file size validation

### TestGraphicsWithAdvancedFeatures
Tests compilation with advanced plot features:
- `test_compile_with_fill_between`: Fill between curves
- `test_compile_with_log_scale`: Logarithmic scales
- `test_compile_with_multiple_colors`: Multiple colors

### TestGraphicsValidation
Advanced validation tests:
- `test_validate_pdf_structure`: Detailed PDF analysis
- `test_validate_eps_structure`: Detailed EPS analysis
- `test_validate_png_structure`: PNG validation
- `test_pdf_has_page_info`: Extract page information
- `test_eps_has_bounding_box`: Extract bounding box
- `test_png_has_dimensions`: Extract image dimensions
- `test_png_color_depth`: Validate color depth
- `test_validate_graphics_file_helper`: Generic validation helper

### TestGraphicsFormattingConsistency
Tests consistency across formats:
- `test_same_figure_multiple_formats`: Same figure to PDF, EPS, PNG
- `test_complex_plot_all_formats`: Complex plots across formats

## Requirements

### Core Requirements
- GLE (Graphics Layout Engine) installed on the system
- Available on PATH or can be found at standard locations

### Optional Enhancement
For more advanced image analysis:
```bash
pip install Pillow   # For advanced PNG analysis
# or
pip install pdf2image  # For advanced PDF analysis
```

## Skip Behavior

Tests are automatically skipped if GLE is not available:
```
SKIPPED [100%] GLE compiler not available
```

To install GLE:
- **macOS**: `brew install gle`
- **Linux**: `apt-get install gle` or `yum install gle`
- **Windows**: Download from [GLE website](http://glx.sourceforge.io)

## Expected Output

Successful test runs produce:
- Valid PDF files with proper headers and structure
- Valid EPS files with PostScript headers and showpage
- Valid PNG files with PNG signatures and valid dimensions

## Example Test Output

```
tests/integration/test_graphics_compilation.py::TestGraphicsCompilation::test_compile_to_pdf PASSED
tests/integration/test_graphics_validation.py::TestGraphicsValidation::test_pdf_has_page_info PASSED
tests/integration/test_graphics_validation.py::TestGraphicsFormattingConsistency::test_same_figure_multiple_formats PASSED
```

## Troubleshooting

### GLE not found
Ensure GLE is installed and in PATH:
```bash
which gle
or
gle -info
```

### Compilation timeout
Increase timeout in GLECompiler if needed (default: 30 seconds)

### PNG dimensions not extracted
Some PNG files may not have accessible dimension data. Check if PNG is valid first with `PNGAnalyzer.is_valid_png()`

## Architecture

```
graphics_analysis.py
├── PDFAnalyzer
│   ├── is_valid_pdf()
│   ├── get_file_size()
│   ├── has_valid_structure()
│   └── get_page_count()
├── EPSAnalyzer
│   ├── is_valid_eps()
│   ├── get_file_size()
│   ├── has_valid_structure()
│   └── get_bounding_box()
├── PNGAnalyzer
│   ├── is_valid_png()
│   ├── get_file_size()
│   ├── get_image_dimensions()
│   └── get_color_depth()
└── validate_graphics_file()
```

## Future Enhancements

Potential additions:
1. **Pixel-level comparison**: Compare rendered images pixel-by-pixel with reference images
2. **Text extraction**: Extract and validate text from PDF/EPS files
3. **Color analysis**: Verify correct colors are rendered
4. **Performance metrics**: Track compilation time and file sizes
5. **Batch testing**: Test collections of plots simultaneously

# gleplot - Matplotlib-like Plotting for GLE

A Python library that provides a **matplotlib-compatible API** for creating scientific plots that directly generate GLE (Graphics Layout Engine) scripts for publication-quality vector graphics.

## Quick Start

```python
import numpy as np
import gleplot as glp

# Create data
x = np.linspace(0, 2*np.pi, 100)

# Create figure and plot
fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
ax.plot(x, np.sin(x), color='blue', label='sin(x)')
ax.plot(x, np.cos(x), color='red', linestyle='--', label='cos(x)')

# Configure plot
ax.set_xlabel('x (radians)')
ax.set_ylabel('y')
ax.set_title('Trigonometric Functions')
ax.legend()

# Save as PDF (auto-compiles via GLE)
fig.savefig('trig.pdf')

# Or save as GLE script for manual editing
fig.savefig('trig.gle')
```

## Features

✨ **Matplotlib-Compatible API** - All familiar functions work identically  
✨ **Direct GLE Generation** - Optimized script output (1-2 KB)  
✨ **Vector Graphics** - PDF, PNG, EPS export with publication quality  
✨ **Full Plotting Support** - Lines, scatter, bars, fill_between, errorbar  
✨ **Error Bars** - Symmetric, asymmetric, vertical and horizontal  
✨ **Subplots** - Multi-panel figures with flexible grid layouts  
✨ **Publication Ready** - Suitable for all major academic journals  
✨ **Lightweight** - Pure Python, minimal dependencies  

## Documentation

📚 **[Live Sphinx Documentation](https://benhuddart.github.io/gleplot/)** - Complete API reference and guides

**Key Documentation Resources:**
- **[Configuration System](docs/guides/CONFIGURATION.md)** - Customize gleplot appearance and behavior
- **[Configuration API](docs/guides/CONFIGURATION_API.md)** - Complete configuration reference  
- **[Semantic Versioning](docs/guides/VERSIONING.md)** - Automatic version management
- **[Versioning Quick Reference](docs/guides/VERSIONING_QUICK_REF.md)** - Common version bump patterns
- **[Testing Quick Reference](docs/guides/TESTING_QUICK_REFERENCE.md)** - Fast commands and examples
- **[Test Structure](docs/guides/TEST_STRUCTURE.md)** - Test organization and architecture
- **[Graphics Testing](docs/guides/GRAPHICS_TESTING.md)** - Complete graphics testing documentation

## Installation

### Requirements
- Python 3.7+
- numpy

### Optional
- GLE 4.3+ (for PDF/PNG/EPS compilation)
  ```bash
  # Verify installation
  gle -info
  ```

  Install GLE from the official upstream sources:
  - **Preferred (all platforms):** Download prebuilt releases from https://github.com/vlabella/GLE/releases/latest
    - Windows: `.exe` installer
    - macOS: `.dmg`
    - Linux: `.zip`
  - **Alternative:** Download from the official GLE site: https://glx.sourceforge.io/download/
  - **Build from source:** Follow the platform-specific build instructions in the upstream README:
    https://github.com/vlabella/GLE/blob/main/README.md

  GLE upstream also recommends installing runtime dependencies:
  - Ghostscript
  - LaTeX distribution (e.g., TeX Live or MiKTeX)

  Quick first-time verification:
  ```bash
  # Locate Ghostscript/LaTeX and other runtime dependencies
  gle -finddeps

  # Confirm GLE is installed and discover paths
  gle -info
  ```

### Install gleplot
```bash
pip install -e .
```

Or in development mode:
```bash
pip install -e ".[dev]"
```

## Project Structure

```
gleplot/
├── src/gleplot/                    # Source code
│   ├── __init__.py                # Main API
│   ├── figure.py                  # Figure class
│   ├── axes.py                    # Axes class  
│   ├── colors.py                  # Color utilities
│   ├── markers.py                 # Marker definitions
│   ├── writer.py                  # GLE script writer
│   ├── compiler.py                # GLE compiler wrapper
│   └── config.py                  # Configuration system
│
├── tests/                          # Test suite (140 tests)
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   ├── agent/                     # Agent tests
│   ├── test_gleplot.py            # Core test suite
│   └── generate_test_graphics.py  # Graphics generation tests
│
├── examples/                       # Example scripts
│   ├── basic/                     # Basic plotting examples
│   │   ├── line_plots.py
│   │   ├── scatter_plots.py
│   │   ├── bar_charts.py
│   │   └── error_bars.py
│   ├── advanced/                  # Advanced examples
│   │   ├── subplots.py
│   │   ├── shared_axes.py
│   │   ├── fill_between.py
│   │   ├── log_scale.py
│   │   └── combined_plots.py
│   └── gleplot_examples.py        # Main examples runner
│
├── docs/                           # Documentation
│   ├── guides/                    # User guides
│   ├── agent/                     # Development notes
│   └── source/                    # Sphinx source files
│
├── pyproject.toml                 # Package configuration
├── README.md                       # This file
└── LICENSE                        # GPL-2.0+
```

## Usage

### Line Plots
```python
ax.plot(x, y, color='blue', linestyle='--', label='data')
```

### Scatter Plots
```python
ax.scatter(x, y, color='red', marker='o', s=50, label='points')
```

### Bar Charts
```python
ax.bar([1, 2, 3], [10, 20, 30], color=['red', 'green', 'blue'])
```

### Fill Between
```python
ax.fill_between(x, y1, y2, color='lightblue', alpha=0.3)
```

### Error Bars
```python
# Symmetric vertical error bars
ax.errorbar(x, y, yerr=0.5, marker='o', color='blue', label='Data')

# Asymmetric vertical error bars
ax.errorbar(x, y, yerr=([lower_arr], [upper_arr]), marker='s', fmt='none')

# Both vertical and horizontal error bars
ax.errorbar(x, y, yerr=yerr, xerr=xerr, marker='o', capsize=3)
```

### Subplots
```python
# Using subplots() convenience function
fig, axes = glp.subplots(2, 2, figsize=(12, 10))
axes[0].plot(x, y1)        # top-left
axes[1].scatter(x, y2)     # top-right
axes[2].bar(x, y3)         # bottom-left
axes[3].errorbar(x, y4, yerr=err)  # bottom-right
fig.savefig('grid.pdf')

# Using add_subplot() method
fig = glp.figure(figsize=(14, 6))
ax1 = fig.add_subplot(1, 2, 1)  # left panel
ax2 = fig.add_subplot(1, 2, 2)  # right panel

# Shared axes for tighter layouts (stacked plots)
fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 10))
# Only bottom subplot shows x-axis label and ticks
axes[0].plot(x, signal)
axes[1].plot(x, noise)
axes[2].plot(x, combined)
axes[2].set_xlabel('Time')  # Only need to label bottom

# Shared axes for side-by-side comparisons
fig, axes = glp.subplots(1, 3, sharey=True, figsize=(18, 5))
# Only leftmost subplot shows y-axis label and ticks
axes[0].scatter(x1, y1)
axes[0].set_ylabel('Response')  # Only need to label left
axes[1].scatter(x2, y2)
axes[2].scatter(x3, y3)
```

### Axis Control
```python
ax.set_xlabel('X axis')
ax.set_ylabel('Y axis')
ax.set_title('My Plot')
ax.set_xlim(0, 10)
ax.set_ylim(0, 100)
ax.set_xscale('log')
ax.set_yscale('log')
ax.legend(loc='upper left')
```

## Testing

Run the comprehensive test suite:
```bash
cd tests
python -m pytest test_gleplot.py -v
```

Or run directly:
```bash
python test_gleplot.py
```

**Expected output**: 140 tests, all passing

## Examples

Run the example scripts:
```bash
cd examples
python gleplot_examples.py
```

Or run specific example categories:
```bash
# Basic examples
python basic/line_plots.py
python basic/scatter_plots.py
python basic/bar_charts.py
python basic/error_bars.py

# Advanced examples
python advanced/subplots.py
python advanced/shared_axes.py
python advanced/fill_between.py
python advanced/log_scale.py
python advanced/combined_plots.py
python advanced/multiple_styles.py
```

Each example generates GLE script files and optionally compiles them to PDFs.

## API Reference

### Figure
```python
fig = glp.figure(figsize=(8, 6), dpi=100)
```

### Axes
```python
ax = fig.add_subplot(111)
ax.plot(...)
ax.scatter(...)
ax.bar(...)
ax.fill_between(...)
```

### Module-level convenience
```python
glp.figure()
glp.plot(x, y)
glp.scatter(x, y)
glp.xlabel('X')
glp.savefig('plot.pdf')
```

## Comparison: gleplot vs matplotlib

| Feature | gleplot | matplotlib |
|---------|---------|------------|
| **API** | 100% compatible | Reference implementation |
| **Output** | GLE vector graphics | PNG/PDF raster + vector |
| **File size** | 1-2 KB script | 50-100 KB PNG |
| **Compilation** | GLE → PDF/PNG | Built-in |
| **Learning curve** | None (familiar API) | Moderate |
| **Use case** | Publication graphics | General-purpose plotting |

## Troubleshooting

### GLE not found
If compilation fails, ensure GLE is installed and in PATH:
```bash
which gle
gle -info
```

### Import errors
Make sure gleplot is properly installed:
```bash
pip install -e .
```

### Test failures
Run tests with verbose output:
```bash
python -m pytest tests/ -vv
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Run: `python -m pytest tests/`
5. Submit pull request

## License

gleplot is licensed under GPL-2.0+ (compatible with GLE license).

## References

- **GLE Documentation**: https://glx.sourceforge.io/
- **GLE GitHub**: https://github.com/vlabella/GLE
- **Matplotlib Documentation**: https://matplotlib.org/
- **NumPy Documentation**: https://numpy.org/

## Status

✅ **Production Ready**  
✅ **140/140 Tests Passing**  
✅ **Multiple Example Categories**  
✅ **Full Documentation**  
✅ **Automatic Semantic Versioning**

## Repository

- **GitHub**: https://github.com/benhuddart/gleplot
- **Issues**: https://github.com/benhuddart/gleplot/issues
- **Documentation**: https://benhuddart.github.io/gleplot/

---

For questions, issues, or feature requests, please [open an issue on GitHub](https://github.com/benhuddart/gleplot/issues).

Happy plotting! 📊

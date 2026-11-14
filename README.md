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

# Keep the script, compiled output, and data sidecars together
fig.savefig('trig.pdf', folder=True)
```

## Features

- **Matplotlib-compatible API** -- familiar names and call patterns for common plot types
- **Direct GLE generation** -- compact `.gle` scripts (typically a few kilobytes)
- **Vector output** -- PDF, PNG, EPS, SVG, and JPG when GLE is installed
- **Plot types** -- lines, scatter, bars, `fill_between`, `errorbar`, heatmaps, contours, and more
- **Error bars** -- symmetric, asymmetric, vertical, and horizontal
- **File-based series** -- plot from existing data columns without extra generated sidecars
- **Subplots** -- multi-panel figures with flexible grids and `subplots_adjust`
- **Broken x-axes** -- adjacent x ranges in one panel with configurable break markers
- **Reference lines and spans** -- `axvline`, `axhline`, `axvspan`, `axhspan`
- **Markers** -- matplotlib `fillstyle` and `markerfacecolor` mapped to GLE marker families
- **Lightweight core** -- pure Python with NumPy as the main dependency

## GUI Editor

gleplot also ships a desktop editor (PySide6) for building figures without writing code: load data, pick columns, style series, arrange subplots, annotate, and export -- all with a live preview.

### Install
```bash
pip install "gleplot[gui]"
```

### Launch
```bash
gleplot-gui
```

### Features

- **Live preview** -- debounced async GLE compile; SVG by default with a sticky PNG fallback when needed
- **On-canvas annotations** -- add, drag, edit, and delete text labels on the preview (synced with the Texts tab)
- **Data manager** -- load CSV or `.dat` files, map columns, import or reference in place
- **Named columns** -- generated `.dat` sidecars use series labels as column names
- **Property panels** -- Layout, Figure, Axes, Series, and Texts for point-and-click editing
- **Native `.gle` files** -- save and open plain GLE scripts; unrecognized content is preserved
- **Export** -- PDF, PNG, EPS, SVG, JPG, raw GLE, optional folder bundle
- **Undo and redo** -- full editing history
- **Programmatic `.gle` preview** -- read-only render and export for scripts with GLE programming constructs

### Requirements
The editor needs GLE 4.3+ installed and discoverable (via `GLE_PATH` or `PATH`) to render the live preview and export non-`.gle` formats -- see [Installation](#installation) above. The status bar shows the detected GLE path (or "not found").

Prebuilt Windows and macOS builds are attached to each [GitHub Release](https://github.com/benhuddart/gleplot/releases).

See the **[GUI Editor Guide](docs/guides/GUI_EDITOR.md)** for a full walkthrough, and `examples/gui/` for a ready-to-open sample project.

## Documentation

**[Sphinx documentation](https://benhuddart.github.io/gleplot/)** — API reference, gallery, and tutorials.

**User guides**

- **[GUI Editor](docs/guides/GUI_EDITOR.md)** — desktop editor walkthrough and troubleshooting
- **[Matplotlib migration](docs/guides/MATPLOTLIB_MIGRATION.md)** — API mapping and behavioral differences
- **[Broken axes](docs/guides/BROKEN_AXES.md)** — split x-axes for two timescales
- **[Reference lines and spans](docs/guides/REFERENCE_LINES_AND_SPANS.md)** — `axvline`, `axhline`, `axvspan`, `axhspan`
- **[Colors and markers](docs/guides/COLORS_AND_MARKERS.md)** — color and marker mappings
- **[Configuration](docs/guides/CONFIGURATION.md)** and **[Configuration API](docs/guides/CONFIGURATION_API.md)** — global and per-figure styling
- **[Contour and heatmaps](docs/guides/CONTOUR_AND_HEATMAPS.md)** — gridded and scattered raster plots
- **[File-based series](docs/guides/FILE_BASED_SERIES.md)** — plot from existing columns
- **[Troubleshooting](docs/guides/TROUBLESHOOTING.md)** — common runtime issues

**Contributing**

- **[Development workflow](docs/guides/DEVELOPMENT_WORKFLOW.md)** — tests, versioning, and releases
- **[Versioning](docs/guides/VERSIONING.md)** and **[quick reference](docs/guides/VERSIONING_QUICK_REF.md)** — semantic versioning
- **[Testing quick reference](docs/guides/TESTING_QUICK_REFERENCE.md)** and **[test structure](docs/guides/TEST_STRUCTURE.md)**
- **[Graphics testing](docs/guides/GRAPHICS_TESTING.md)** — compiled output validation

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
│   ├── dataio.py                  # Delimited data-file loading
│   ├── writer.py                  # GLE script writer
│   ├── compiler.py                # GLE compiler wrapper
│   ├── config.py                  # Configuration system
│   ├── parser/                    # Parse existing .gle back into the object model
│   └── gui/                       # PySide6 desktop editor
│
├── tests/                          # Test suite
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   ├── parser/                    # GLE parser tests
│   ├── gui/                       # GUI editor tests
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

### File-Based Series
```python
# Error bars from existing file columns (1-based column indices)
ax.errorbar_from_file(
  'experiment.dat',
  x_col=1,
  y_col=2,
  yerr_col=3,
  marker='o',
  color='blue',
  label='Measurement'
)

# Overlay fit/model line from the same file without creating data_*.dat
ax.line_from_file(
  'experiment.dat',
  x_col=1,
  y_col=4,
  color='red',
  linestyle='--',
  linewidth=2,
  label='Model fit'
)
```

### Foldered Exports
```python
# Creates trig.gleplot/trig.pdf, trig.gleplot/trig.gle, and data files
fig.savefig('trig.pdf', folder=True)
```

### Secondary Y-Axis
```python
# Plot data with different scales on same graph
fig = glp.figure()
ax = fig.add_subplot(111)

# Plot on left y-axis (default)
ax.plot(days, temperature, color='red', label='Temperature', yaxis='y')
ax.set_ylabel('Temperature (°C)', axis='y')
ax.set_ylim(10, 30, axis='y')

# Plot on right y-axis
ax.plot(days, humidity, color='blue', label='Humidity', yaxis='y2')
ax.set_ylabel('Humidity (%)', axis='y2')
ax.set_ylim(30, 90, axis='y2')

# Log scale on secondary axis
ax.set_yscale('log', axis='y2')

ax.legend()
fig.savefig('dual_axis.pdf')
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

# Fine-tune multi-panel layout (matplotlib-compatible)
fig.subplots_adjust(
  left=0.12,
  right=0.98,
  bottom=0.1,
  top=0.92,
  wspace=0.35,
  hspace=0.4,
)
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

**Expected output**: a comprehensive test suite (unit, integration, parser, and GUI tests), all passing

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
python advanced/secondary_yaxis.py
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
| **API** | Matplotlib-like for supported plot types (see [migration guide](docs/guides/MATPLOTLIB_MIGRATION.md)) | Reference implementation |
| **Output** | GLE script plus PDF/PNG/EPS/SVG when GLE is installed | Built-in raster and vector backends |
| **Script size** | Typically a few KB `.gle` plus `.dat` sidecars | N/A (in-memory or image files) |
| **Rendering** | External `gle` binary | Built-in |
| **Learning curve** | Low if you already use matplotlib for the same primitives | Moderate |
| **Use case** | Publication vector figures via GLE | General-purpose plotting |

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

## Repository

- **GitHub**: https://github.com/benhuddart/gleplot
- **Issues**: https://github.com/benhuddart/gleplot/issues
- **Documentation**: https://benhuddart.github.io/gleplot/

---

For questions, issues, or feature requests, please [open an issue on GitHub](https://github.com/benhuddart/gleplot/issues).

# gleplot `view()` Function

The `view()` function allows you to display gleplot figures inline in Jupyter notebooks or save them to temporary files for viewing.

## Overview

The `view()` function automatically detects whether you're running in a Jupyter notebook environment and handles display accordingly:

- **In Jupyter notebooks**: Displays the plot inline using IPython.display
- **In regular Python scripts**: Saves to a temporary file and prints the path

## Usage

### Basic Usage

```python
import gleplot as glp
import numpy as np

# Create a figure
fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)

# Plot some data
x = np.linspace(0, 2*np.pi, 100)
y = np.sin(x)
ax.plot(x, y, 'b-', label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.set_title('Sine Wave')
ax.legend()

# Display inline (in Jupyter) or save to temp file
fig.view()
```

### Custom DPI

You can specify a custom DPI (dots per inch) for higher resolution:

```python
# High-resolution display
fig.view(dpi=300)
```

### Module-Level Function

For matplotlib-style compatibility, you can use the module-level `view()` function:

```python
import gleplot as glp

# Create plot using module-level functions
fig, ax = glp.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
ax.set_title('Quadratic')

# Display using module-level function
glp.view()
```

## Parameters

- **dpi** (int, optional): Resolution in dots per inch. If None, uses the figure's dpi setting (default: 100)
- **format** (str, optional): Output format. Options are `'png'` (default) or `'pdf'`. PNG is recommended for inline display.

## Returns

- **In Jupyter**: Returns `None` after displaying inline via IPython.display
- **Outside Jupyter**: Returns a Path object pointing to the temporary file

## Requirements

- GLE (Graphics Layout Engine) must be installed for the `view()` function to work
- For Jupyter notebook display: IPython must be available (included with Jupyter)

## Examples

### Example 1: Simple Line Plot

```python
fig = glp.figure()
ax = fig.add_subplot(111)
ax.plot([1, 2, 3, 4], [1, 4, 9, 16], 'ro-')
ax.set_xlabel('X')
ax.set_ylabel('Y²')
fig.view()
```

### Example 2: Subplots Grid

```python
fig, axes = glp.subplots(2, 2, figsize=(12, 10))

# Top-left
axes[0].plot([1, 2, 3], [1, 2, 3], 'b-')
axes[0].set_title('Linear')

# Top-right
axes[1].scatter([1, 2, 3], [1, 4, 9], color='red')
axes[1].set_title('Scatter')

# Bottom-left
axes[2].bar([1, 2, 3], [3, 5, 2], color='green')
axes[2].set_title('Bar')

# Bottom-right
axes[3].plot([1, 2, 3], [3, 1, 2], 'g--')
axes[3].set_title('Dashed')

# Display entire grid
fig.view()
```

### Example 3: High DPI for Publication

```python
fig = glp.figure(figsize=(10, 8))
ax = fig.add_subplot(111)

# Complex plot with many data points
x = np.linspace(0, 10, 1000)
y = np.sin(x) * np.exp(-x/10)
ax.plot(x, y, 'b-', linewidth=2)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Amplitude')
ax.set_title('Damped Oscillation')

# High resolution for detail
fig.view(dpi=300)
```

## Comparison with `savefig()`

- **`savefig()`**: Saves to a permanent file with a specified name and location
- **`view()`**: Creates a temporary file and displays it inline (in Jupyter) or prints the temp file path

Both functions require GLE to be installed for compilation.

## Tips

1. **Use PNG format**: Default PNG format works best for inline display in Jupyter
2. **Adjust DPI**: Increase DPI (e.g., 200-300) for better quality with detailed plots
3. **Temporary files**: Files created by `view()` are saved in the system temp directory
4. **Combined workflow**: Use `view()` for quick checks and `savefig()` for final output

## See Also

- [example_view.py](../../examples/example_view.py) - Python script examples
- [example_view_notebook.ipynb](../../examples/example_view_notebook.ipynb) - Jupyter notebook examples
- [Figure.savefig()](../source/api.rst) - For saving to permanent files

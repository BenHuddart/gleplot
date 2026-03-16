# Text Annotations

Use `Axes.text()` (or module-level `gleplot.text()`) to place text directly in data coordinates.

## Basic Usage

```python
import gleplot as glp

fig = glp.figure(figsize=(8, 5))
ax = fig.add_subplot(111)
ax.plot([0, 1, 2], [0.5, 1.3, 0.8])

ax.text(1.0, 1.3, 'Local maximum')
fig.savefig('text_basic.gle')
```

## Alignment Controls

```python
ax.text(2.0, 0.5, 'Left aligned', ha='left', va='center')
ax.text(2.0, 0.2, 'Centered', ha='center', va='center')
ax.text(2.0, -0.1, 'Right aligned', ha='right', va='center')
```

Supported alignment values:

- Horizontal `ha`: `left`, `center`, `right`
- Vertical `va`: `top`, `center`, `bottom`

## Font and Color

```python
ax.text(0.5, 1.0, 'Blue note', color='blue', fontsize=12)
```

## Boxed Text

Use the `bbox` dictionary for callouts that stand out from the data.

```python
ax.text(
    3.0,
    0.8,
    'Fit region',
    bbox={'fill': 'white', 'line': 'black', 'lw': 0.5},
)
```

## Using Module-Level Convenience API

```python
import gleplot as glp

glp.figure(figsize=(7, 4))
glp.plot([0, 1, 2], [1, 2, 1])
glp.text(1.0, 2.0, 'Peak')
glp.savefig('text_convenience.gle')
```

## Tips

- Place text after plotting so you can choose coordinates with known axis limits.
- Use concise labels and avoid overlapping with markers or error bars.
- Combine color + `bbox` for high-contrast annotations in dense plots.
- For reusable patterns, see `examples/advanced/text_annotations.py`.

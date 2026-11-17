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

`va` is the vertical half of GLE's `set just` (`tc`, `bc`, `bl`, and the other corner codes). The default `center` keeps the single-word forms `left`, `center`, and `right`, which GLE centers vertically. There is no separate baseline; `va='baseline'` warns and is drawn as `center`.

## Rotation

`rotation` is degrees counter-clockwise about the alignment point (GLE `begin rotate`).

```python
ax.text(1.0, 1.0, 'peak', va='bottom', ha='center', rotation=45)
```

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
    bbox={'facecolor': 'white'},
)
```

`facecolor` (alias `fill`) is the color of a filled background, drawn with GLE `begin box fill` and a 0.05 cm pad. The box has no outline. `edgecolor`, `linewidth`, `pad`, and `boxstyle` are accepted and ignored, with a warning.

## Arrows

`ax.annotate` places the text at `xytext` with an arrow to the point `xy`,
both in data coordinates:

```python
ax.annotate('peak', xy=(1.0, 1.3), xytext=(1.4, 1.6), arrowprops={'arrowstyle': '->'})
```

The arrow styles and the `arrowprops` keys that are honoured are listed in the
[Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md).

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

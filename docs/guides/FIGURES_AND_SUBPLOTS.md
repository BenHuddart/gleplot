# Figures and Subplots

A figure holds one or more axes. Each axes is written as its own GLE graph
block.

## Creating a figure

```python
import gleplot as glp

fig = glp.figure(figsize=(8, 6))  # 8 inches wide, 6 inches tall
ax = fig.add_subplot(111)
```

`figsize` is in inches, as in matplotlib.

## Subplot grids

`add_subplot` takes the matplotlib grid position:

```python
import numpy as np
import gleplot as glp

x = np.linspace(0, 10, 100)
fig = glp.figure(figsize=(12, 8))

ax1 = fig.add_subplot(2, 2, 1)
ax1.plot(x, np.sin(x))
ax1.set_title('Plot 1')

ax2 = fig.add_subplot(2, 2, 2)
ax2.plot(x, np.cos(x))
ax2.set_title('Plot 2')

ax3 = fig.add_subplot(2, 2, 3)
ax3.plot(x, x)
ax3.set_title('Plot 3')

ax4 = fig.add_subplot(2, 2, 4)
ax4.plot(x, x**2)
ax4.set_title('Plot 4')

fig.savefig('grid.gle')
```

`glp.subplots(nrows, ncols)` creates the figure and all its axes at once.
The axes come back as a flat list in row order, not matplotlib's 2-D array;
a 1×1 grid returns the axes itself.

## Shared axes

Share the x-axis or y-axis when panels should be compared directly.

Shared x-axis (stacked plots):

```python
import numpy as np
import gleplot as glp

x = np.linspace(0, 10, 200)
fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 10))

axes[0].plot(x, np.sin(x))
axes[1].plot(x, np.cos(x))
axes[2].plot(x, np.sin(x) + np.cos(x))
axes[2].set_xlabel('time')

fig.savefig('shared_x.gle')
```

Shared y-axis (side-by-side plots):

```python
fig, axes = glp.subplots(1, 3, sharey=True, figsize=(14, 4))
axes[0].scatter(x, np.sin(x))
axes[1].scatter(x, np.cos(x))
axes[2].scatter(x, np.sin(2 * x))
axes[0].set_ylabel('Response')
```

- `sharex=True`: only the bottom row shows x tick labels and the x-axis label.
- `sharey=True`: only the leftmost column shows y tick labels and the y-axis label.
- Axis limits are synchronized across the shared dimension.

## Adjusting the layout

`Figure.subplots_adjust(...)` sets the margins and the spacing between panels
when labels, legends, or titles need more room.

- `left`, `right`, `bottom`, `top` are fractions of the figure, in `[0, 1]`.
- `wspace` and `hspace` follow matplotlib: a fraction of the average panel size.

```python
import numpy as np
import gleplot as glp

fig, axes = glp.subplots(2, 2, figsize=(10, 8))
x = np.linspace(0, 10, 100)

for i, ax in enumerate(axes, start=1):
    ax.plot(x, np.sin(x + i), label=f'Panel {i}')
    ax.legend()

fig.subplots_adjust(
    left=0.12,
    right=0.98,
    bottom=0.10,
    top=0.93,
    wspace=0.35,
    hspace=0.40,
)
```

The values are checked as in matplotlib: `left < right`, `bottom < top`,
`wspace >= 0` and `hspace >= 0`.

For a split x-axis inside one panel, see [Broken Axes](BROKEN_AXES.md).

## Drawing on the page

A figure can draw shapes and blocks of text on the page itself, outside any
axes. These are gleplot methods, not matplotlib ones: positions and sizes are
in centimetres from the bottom-left corner of the page, and line widths are in
points.

```python
import gleplot as glp

fig = glp.figure(figsize=(6, 4))
ax = fig.add_subplot(111)
ax.plot([0, 1, 2], [0, 1, 4])

fig.circle(2, 3, radius=0.4, fill='red')
fig.ellipse(6, 3, 2, 1, color='blue', linewidth=1.5)
fig.arc(10, 3, 1, 0, 180)
fig.bezier([1, 2, 3, 4], [6, 8, 4, 6])
fig.curve([6, 7, 8], [6, 7, 6], (1, 0), (1, 0))
fig.polygon([10, 12, 11], [6, 6, 8], fill='yellow')
fig.table(1, 9, 'a    b\n1    22')
fig.tex(8, 9, r'\textbf{Note}')

fig.savefig('page.gle')
```

Each call writes one GLE primitive (`circle`, `ellipse`, `arc`, `bezier`,
`curve`, a `begin path` block, a `begin table` block, a `begin tex` block).
The drawings are written after every axes, so they sit on top of them, in the
order they were added. A figure with no axes holds only its drawings.
`color='none'` leaves a circle, an ellipse or a polygon without an outline.

`Figure.tex` text is set by LaTeX, so compiling the figure needs a LaTeX
installation that GLE can find. GLE sets it in one LaTeX box, so a newline
does not start a new line in the output; use a `tabular` for several lines.
A line of `tex` or `table` text cannot start with the word `begin` or `end`,
which GLE would read as block structure; `\begin{...}` is fine.

`open_gle` reads the drawings in a file gleplot wrote back into the figure.

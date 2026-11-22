# Migrating from gleplot 5 to 6

gleplot 6 is the first stable release. It narrows gleplot to what GLE does
natively, checks arguments when a call is made, and draws more like
matplotlib by default. This page lists what a gleplot 5 script may need to
change, and what to use instead. The [changelog](https://benhuddart.github.io/gleplot/changelog.html)
has every change.

## Installing

gleplot is on PyPI:

```bash
pip install gleplot
```

Compiling a figure needs GLE and, now, **GLE's include library** (`gleinc`).
Colormaps, colorbars, contour labels, rugs and some reference lines are drawn
by GLE's own routines (`palettes.gle`, `brewer.gle`, `color.gle`,
`contour.gle`, `rugs.gle`, `graphutil.gle`), which the script `include`s
instead of defining its own subroutines. GLE's release packages ship the
library. A GLE built from source may not have it: see
[GLE's include library](https://benhuddart.github.io/gleplot/getting_started.html#gle-s-include-library).
Without it, `savefig` raises `gleplot.compiler.GLECompileError` naming the
missing file.
Saving a `.gle` script still needs nothing.

## What gleplot covers

gleplot writes standard GLE, with matplotlib's names where they map cleanly.
Where matplotlib does something GLE has no command for, gleplot no longer
builds it from generated subroutines: it accepts the keyword, warns, and the
[matplotlib migration guide](MATPLOTLIB_MIGRATION.md) lists the gap. That is
why the features below are gone.

## Removed

| gleplot 5 | gleplot 6 |
|---|---|
| `ax.pie(...)`, `glp.pie(...)` | removed; GLE has no pie chart. |
| `ax.boxplot(...)`, `glp.boxplot(...)` | removed; GLE has no box plot. Draw the statistics you need with `bar`, `errorbar` or `hlines`/`vlines`. |
| `Figure.add_broken_xaxes`, `add_broken_yaxes`, `glp.BrokenAxes` | removed; GLE has no broken axis. Use a logarithmic axis, or two subplots, to show two ranges. |
| `GLEWriter.add_plot_line`, `add_errorbar`, `add_bar_chart`, `add_fill_between`, `add_histogram`, `add_text` and the `add_*_from_file` methods | removed. Code that drives `GLEWriter` directly builds a series from `gleplot.series` and calls the writer's entry point for that kind. |

Using a removed name raises `AttributeError` (`ImportError` for
`from gleplot import BrokenAxes`). `Figure.to_dict()` no longer
has the `wedges`, `boxes`, `broken_axes` and `break_index` keys.

## Bad arguments raise at the call

An argument value gleplot cannot use raises `ValueError` (or `TypeError` for
a wrong type) when the call is made, naming the argument, where gleplot 5
warned, drew something else, or failed later at `savefig`. For example:

| call | gleplot 6 |
|---|---|
| `ax.plot(x, y, color='blu')` | `ValueError`; gleplot 5 warned and drew black |
| `ax.plot(x, y, linewidth=float('nan'))`, or a negative width | `ValueError` |
| `ax.axhline(float('nan'))`, a NaN or infinite `axvline`, `axhspan` or `axvspan` edge | `ValueError` |
| `ax.set_xlim(0, float('inf'))`, `ax.set_xlim(True, 2)`, `ax.set_xlim(0, 1, axis='y')` | `ValueError` or `TypeError` |
| `ax.set_xlabel('t', axis='z')`, `ax.get_xlim('y')` | `ValueError`: the axis is `'x'` or `'x2'` (`'y'` or `'y2'` for the y calls) |
| `fig.add_subplot(2, 2, 0)`, or an index past the grid | `ValueError` |
| `glp.subplots(2, 1, sharex='yes')` | `ValueError`; `sharex`/`sharey` take matplotlib's `True`, `False`, `'all'`, `'none'`, `'row'` and `'col'` |
| `GLEGraphConfig(scale_mode='bogus')` | `ValueError` |
| `ax.imshow(masked_array)` | `ValueError`; pass `np.ma.filled(Z, value)` |
| `line_from_file` or `errorbar_from_file` with a double quote in `data_file` | `ValueError`; GLE cannot read such a file name |

An unknown keyword *name* still only warns, with the same message for every
call, and never raises:

```python
fig, ax = glp.subplots()
ax.plot([1, 2, 3], [1, 4, 9], colour='red')
# UserWarning: plot() ignores unsupported keyword(s): colour.
```

## Calls that take matplotlib's arguments

### `subplots` returns a numpy array

`glp.subplots` returns matplotlib's numpy array of `Axes`, squeezed as
matplotlib squeezes it, and takes only `nrows` and `ncols` positionally. A
grid of two or more rows and columns is indexed by row and column, and
iterating over it yields rows:

```python
fig, axes = glp.subplots(2, 2, figsize=(8, 6))  # was subplots(2, 2, (8, 6))
axes[1, 1].plot([1, 2, 3], [3, 1, 2])           # was axes[3]
for ax in axes.flat:                            # was: for ax in axes
    ax.set_xlabel('x')
```

A single row or column is still indexed as `axes[i]`.

### `scatter(x, y, s, c)`

`scatter` takes matplotlib's positional order: the third and fourth
arguments are the size `s` and the colours `c`, and everything else is a
keyword. A gleplot 5 call with a colour in the third place now raises:

```python
ax.scatter(x, y, 30, color='red')  # was scatter(x, y, 'red', 30)
```

### `bar(x, height, width, bottom)`

`bar` takes matplotlib's positional order: the third and fourth arguments
are the bar `width` and the `bottom` baseline, and everything else, `align`
included, is a keyword. `barh(y, width, height, left)` already had that
order; its `align` is now a keyword too. A gleplot 5 call with a colour in
the third place now raises:

```python
ax.bar(x, h, color='red')  # was bar(x, h, 'red')
```

### `set_xlim` and `set_ylim` return the limits

As in matplotlib, `set_xlim` and `set_ylim` return the `(low, high)` they
set, so they no longer chain:

```python
ax.set_xlim(0, 1)  # was ax.set_xlim(0, 1).set_ylim(0, 2)
ax.set_ylim(0, 2)
```

### Format strings and error bar shapes

- `plot`, `step` and `errorbar` read matplotlib's format strings: `'ro'` is
  red circles with no line and `'k--'` a black dashed line. A `color`,
  `marker` or `linestyle` keyword wins over the format, with a warning.
- `errorbar(fmt='none')` draws only the error bars, even with `marker=`; use
  `linestyle='none'` for markers without a line. `errorbar(fmt='')` draws the
  default solid line.
- A two-element `yerr` or `xerr` is read as matplotlib reads it, one error
  per point. For a lower and an upper error on every point, pass two rows:
  `yerr=([0.1] * N, [0.2] * N)`. The shapes are in the
  [matplotlib migration guide](MATPLOTLIB_MIGRATION.md) ("Line keywords").

## Changes to what is drawn

### Colours follow matplotlib's cycle

A series given no colour takes the next of matplotlib's `'C0'` to `'C9'`, per
axes, where gleplot 5 drew lines and markers in blue, bars in red and fills
in light blue. Pass a colour to keep the old one. For one colour on every
uncoloured line and marker, as before:

```python
fig = glp.figure(
    style=glp.GLEStyleConfig(default_color='BLUE', default_marker_color='BLUE')
)
```

Bars, fills and `stackplot` layers always take the cycle; give them `color=`.
The rules are in "Default colours" in the
[matplotlib migration guide](MATPLOTLIB_MIGRATION.md).

### Bars have no edge unless one is asked for

`bar` and `barh` no longer draw GLE's black outline, and `linewidth` or
`linestyle` without `edgecolor` draws no edge, as in matplotlib: they style
the edge that `edgecolor` asks for. Pass `edgecolor` for an outline:

```python
ax.bar([1, 2, 3], [3, 1, 2], edgecolor='black', linewidth=2)
```

### Lines, histograms and axes

- A `plot` or `step` line breaks at NaN or infinity, as matplotlib's does,
  instead of joining across the gap, including a line whose data comes from
  a `data_source`. A broken line is drawn unsmoothed, with a warning, under
  `smooth_curves=True`.
- `hist(histtype='step')` draws its line in `edgecolor` when one is given.
  The alpha of an RGBA `color` no longer reaches an `edgecolor`, and a
  `stepfilled` histogram with `edgecolor='none'` is stroked in its fill
  colour.
- With series on both y axes and no limits set, the left axis is ranged from
  the left-axis series only, as with matplotlib's `twinx`. Call `set_ylim` to
  keep a wider range.
- A reference line or span on an axis gleplot cannot range (no data and no
  limit on that axis, or data that all have one value) is drawn after the graph by GLE's `graphutil.gle`, so
  it sits above the data. Set the axis limit to keep it below.

### Colormaps, colorbars and contours

- Colormaps are GLE's own routines. The ColorBrewer maps (`'Blues'`,
  `'RdBu'`, and the rest) are drawn in their own colours, stepped, instead of
  a warning and a stand-in map.
- A colorbar is GLE's `color_range_vertical` or `color_range_horizontal`. Its
  tick format follows the step, and it has no separate outline.
- `contour(clabel=True)` labels are written by GLE's `contour_labels`, in
  blue in a white box.
- An `imshow` or `tripcolor` grid's nodes are placed as `contour` and
  `tricontour` place them, so a heatmap and its contours line up. The heatmap
  reaches up to one grid spacing further right and up than in gleplot 5.
- A rug is drawn by GLE's `rugs.gle` and writes its values to a data file.

[Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md) describes each of
these.

## Files written by gleplot 5

A `.gle` file written by gleplot 5 or earlier opens and compiles, as
hand-written GLE. The subroutines gleplot 5 generated (`gleplot_*`; gleplot
6 names its own `glp_*`) are kept as raw GLE with the commands that call
them, so pies, box plots, broken axes, colormaps and the like still draw but
are not editable from Python. The oldest files' `v1` metadata header is
not read. See
[Opening GLE Files](OPENING_GLE_FILES.md).

A `Figure.to_dict()` snapshot saved with a broken axis loads its segments as
separate axes, drawn over each other in its place, with a warning.

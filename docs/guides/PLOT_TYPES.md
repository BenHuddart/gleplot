# Plot Types

The plotting methods on `Axes` take matplotlib's arguments. This page shows
the common calls. Where GLE draws something differently from matplotlib, the
[Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md) has the details for
each method. Colours, markers and line styles are listed in
[Colors and Markers](COLORS_AND_MARKERS.md).

The snippets below assume this setup:

```python
import numpy as np
import gleplot as glp

x = np.linspace(0, 10, 20)
y = np.sin(x)
y2 = np.cos(x)
err = np.full_like(x, 0.1)
samples = np.random.default_rng(0).random(200)

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
```

## Lines

```python
ax.plot(x, y, label='data', color='blue', linestyle='-', linewidth=2)
```

`ax.vlines(x, ymin, ymax)` and `ax.hlines(y, xmin, xmax)` draw segments
whose ends are data coordinates. How they are written is in the
[migration guide](MATPLOTLIB_MIGRATION.md) ("Segments"):

```python
ax.vlines(peaks, 0, heights, colors='k', label='peaks')
ax.hlines([0.5, 1.5], 0, [2, 3], linestyles='dashed')
```

For a guide across the whole axes, see
[Reference lines and spans](REFERENCE_LINES_AND_SPANS.md).

## Scatter

```python
ax.scatter(x, y, s=50, color='red', marker='o', alpha=0.6)
```

`s` is an area in points², as in matplotlib. Pass one value per point for a
bubble chart, e.g. `s=population / 1e6`, or one number per point for `c` to
colour each point through a colormap, e.g. `c=temperature, cmap='viridis'`;
see [Colors and Markers](COLORS_AND_MARKERS.md).

## Error bars

```python
ax.errorbar(x, y, yerr=err, marker='o', capsize=3)
```

## Bars

```python
ax.bar(x, y, width=0.4, color='green', edgecolor='black', label='bars')
ax.bar(x, y2, bottom=y)
ax.bar(x, y, yerr=err, capsize=3)
ax.barh(x, y, xerr=err)
```

## Steps, stems and histograms

These use GLE line modes on the same data:

```python
ax.step(x, y, where='pre')            # line fsteps
ax.plot(x, y, drawstyle='steps-mid')  # line hist
ax.stem(x, y)                         # line impulses
ax.hist(samples, bins=20, range=(0, 1), histtype='step')
ax.hist(samples, bins=20, range=(0, 1), histtype='stepfilled')
```

`where` is `'pre'` (default), `'post'` or `'mid'`. `hist` draws counts:
`step` is `line hist` on GLE's binned dataset, and `stepfilled` is adjoining
bars of one bin width.

## Function curves

GLE can sample an expression in `x` itself, so a smooth curve needs no data
file:

```python
ax.function('sin(x)', xmin=0, xmax=6.28, step=0.05)  # let d1 = sin(x) from 0 to 6.28 step 0.05
ax.function('exp(-x^2/2)', color='red', linestyle='--', label='gauss')
```

The expression is GLE syntax, written without spaces. Without `xmin` and
`xmax` GLE samples the x axis range, and without `step` it takes 100 points.
gleplot does not evaluate the expression, so the curve does not widen the y
range of other data on the axes; call `set_ylim` if it leaves it. Use `plot`
when you already have the arrays.

## Fitted curves

GLE can fit an expression to data and draw the fitted curve:

```python
ax.scatter(x, y)
ax.fit(x, y, 'a*exp(-x/b)+c', xmin=0, xmax=5)  # let d2 = fit d1 with a*exp(-x/b)+c from 0 to 5
```

Every name in the expression other than `x` is a coefficient. GLE starts each
at 0 and finds the values that fit best by least squares. `fit` draws only
the curve, so plot the data yourself. `xmin`, `xmax` and `step` set where the
curve is drawn, as for `function`; all of the data is fitted. The fitted
values stay inside GLE, so to use them in Python, or to start from other
values, fit in Python and `plot` the result.

For a straight line, an exponential or a power law, give `model` instead of
an expression, and GLE fits it in closed form with its own routine:

```python
ax.fit(x, y, model='linear')       # let d2 = linfit d1         y = a*x+b
ax.fit(x, y, model='exp', xmin=0)  # let d2 = logefit d1 from 0  y = a*exp(b*x)
ax.fit(x, y, model='exp10')        # let d2 = log10fit d1       y = a*10^(b*x)
ax.fit(x, y, model='power')        # let d2 = powxfit d1        y = a*x^b
```

A model needs points at two or more distinct x. The last three fit a
straight line to the logs of the data, so they need y above 0, and `power`
needs x above 0 too. `xmin` and `xmax` set where the curve is drawn, but
`step` does not apply: GLE always draws a model at 100 points.

A model's label can show the fitted values. `{slope}` and `{offset}` are the
`a` and `b` of `linear`, `{prefactor}` and `{exponent}` the `a` and `b` of
the other three, and `{rsq}` is r² for all four. Add `:.Nf` for N decimal
places or `:.Ne` for scientific notation, as in a Python format string:

```python
ax.fit(x, y, model='linear', label='y = {slope:.2f}x + {offset:.2f}')
ax.fit(x, y, model='power', label='$r^2$ = {rsq:.3f}')
ax.legend()
```

GLE computes the numbers when it draws the graph, after it has read the
graph's own key, so a legend with such a label is a `begin key` block after
the graph, as one placed with `bbox_to_anchor` is.

In a hand-written routine with result variables (`let d2 = logefit d1 s o
r`), GLE puts the exponent `b` of `logefit`, `log10fit` and `powxfit` in the
first variable and the prefactor `a` in the second, the reverse of what the
GLE manual says. gleplot reads such a `let` when its variables are named
nowhere but in it and in the curve's key. It keeps one whose variables are
used elsewhere, and one with a `step`, a data window or a `limit_data`
option, as raw GLE.

## Curves computed from other series

GLE can also compute a curve from series already on the axes. In the
expression, `d1` ... `dn` stand for the series in `sources`, in order:

```python
ax.line_from_file('run1.dat', x_col=1, y_col=2)
ax.line_from_file('run2.dat', x_col=1, y_col=2)
a, b = ax.file_series
ax.derived('d1-d2', [a, b], label='difference')  # let d3 = d1-d2
```

The numbers stay inside GLE, so this works on data gleplot never reads.
Sources are line, scatter, `line_from_file`, function and fit series of the
same axes, taken from `ax.lines`, `ax.scatters`, `ax.file_series`,
`ax.functions` and `ax.fits`. GLE computes the curve at the x values of every
source, interpolating the others where they have no point. `range` limits
that to the x values of the series it names, `where` keeps only the points
where an expression is true, and `xmin`, `xmax` with `step` or `nsteps` add
evenly spaced x values:

```python
ax.derived('(d1+d2)/2', [a, b], where='d1>0', range=a)
```

The curve is drawn after every other data series of the axes. A source
with an `offset` is read without it. gleplot does not evaluate the
expression, so the curve does not widen the y range. Only GLE's
single-expression `let` is written; a hand-written parametric
`let d2 = x-exp, y-exp` stays raw GLE, as does a `let` that reads a dataset
gleplot does not model as one of these series.

## Marker spacing, thinning and clipping

```python
ax.plot(x, y, marker='o', mdist=0.5)               # a marker every 0.5 cm
ax.plot(x, y, deresolve=10, deresolve_average=True)  # mean of every 10 points
ax.plot(x, y, xmin=0, xmax=5)                      # clip this series only
```

matplotlib's `markevery` has no GLE equivalent; see the
[migration guide](MATPLOTLIB_MIGRATION.md) ("Marker spacing, thinning and clipping").

## Fills

Fills use GLE's `fill` command. Two curves are `fill dA,dB`. A curve can
close on the axis instead (`baseline='x1'` or `'x2'`), a boolean `where`
clips each run with `xmin` / `xmax`, and `ax.fill(x, y)` is a closed polygon
(`fill dN`). `ax.fill_betweenx(y, x1, x2)` fills between two curves of y,
drawn as a polygon, and `ax.stackplot(x, y1, y2, ...)` stacks one band per
layer:

```python
ax.fill_between(x, y, y2, alpha=0.3, color='blue')
ax.fill_between(x, y, where=(x > 5))
ax.fill_between(x, y, baseline='x1')
ax.fill(x, y, alpha=0.4)
ax.fill_betweenx(depth, lo, hi, alpha=0.3)
ax.stackplot(x, y, y2, labels=['a', 'b'])
```

## Pie charts

```python
ax.pie([15, 30, 45, 10], labels=['A', 'B', 'C', 'D'], autopct='%1.1f%%')
```

One wedge per value, with no outline. The axes' lines and ticks are hidden
and its title stays.

## Box plots

```python
ax.boxplot([[1, 2, 3, 4, 9], [2, 3, 4]], tick_labels=['A', 'B'])
```

One vertical box per sample set: quartiles, whiskers at 1.5 times the
interquartile range, and the points beyond them.

### Rugs

```python
ax.rug([1.2, 2.5, 2.7, 4.1])                       # ticks on the bottom edge
ax.rug([3, 9], axis='y', position='both', color='C1')
```

A rug marks each value with a short tick on the frame: on the bottom, top or
both edges for `axis='x'`, on the left, right or both for `axis='y'`. The
ticks are `length` cm long (0.3 by default) and point into the axes; a
negative length points out, as GLE's tick lengths do. Matplotlib has no rug,
so `Axes.rug` is gleplot's own.

## Polar plots

```python
fig = glp.figure()
ax = fig.add_subplot(projection='polar')
ax.plot(theta, r, label='data')
ax.function('cos(2*x)')
ax.set_ylim(0, 1.5)
```

`plot` and `scatter` take theta in radians and the radius. `function` reads
`x` in its expression as theta, from 0 to 2π unless `xmin`/`xmax` say
otherwise. A grid of rings and spokes, labelled with the angles and radii,
replaces the frame. `set_ylim(0, rmax)` sets the outer ring; otherwise it is
the largest radius in the data, rounded up to a ring, or 1 for function
curves alone. Legends and the title work as on any axes. Other plotting
methods raise `NotImplementedError` on a polar axes; see "Polar axes" in
the [matplotlib migration guide](MATPLOTLIB_MIGRATION.md).

## Placed images

```python
ax.image('micrograph.png', extent=(0, 10, 0, 5))
```

Stretches a PNG, JPEG, GIF, TIFF or EPS file over `(left, right, bottom,
top)` in data coordinates, under the grid and the data. GLE reads the file
when it compiles, and a relative path is read from the folder the `.gle`
script is saved in. An EPS file is drawn only when GLE compiles through
PostScript: not to SVG, and not when the figure has semi-transparent colours.
To colour a 2-D array instead, use `imshow` (see
[Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md)).

## Other plot types

- Heatmaps and contours: [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).
- Series read from an existing data file: [File-Based Series](FILE_BASED_SERIES.md).
- Reference lines and shaded spans: [Reference Lines and Shaded Spans](REFERENCE_LINES_AND_SPANS.md).
- Text and arrows: [Text Annotations](TEXT_ANNOTATIONS.md).

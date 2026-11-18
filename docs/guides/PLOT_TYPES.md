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

## Scatter

```python
ax.scatter(x, y, s=50, color='red', marker='o', alpha=0.6)
```

`s` is an area in points², as in matplotlib. One series has one marker size;
plot one series per size.

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
(`fill dN`):

```python
ax.fill_between(x, y, y2, alpha=0.3, color='blue')
ax.fill_between(x, y, where=(x > 5))
ax.fill_between(x, y, baseline='x1')
ax.fill(x, y, alpha=0.4)
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

## Other plot types

- Heatmaps and contours: [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).
- Series read from an existing data file: [File-Based Series](FILE_BASED_SERIES.md).
- Reference lines and shaded spans: [Reference Lines and Shaded Spans](REFERENCE_LINES_AND_SPANS.md).
- Text and arrows: [Text Annotations](TEXT_ANNOTATIONS.md).

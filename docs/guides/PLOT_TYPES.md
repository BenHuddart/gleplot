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

## Other plot types

- Heatmaps and contours: [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).
- Series read from an existing data file: [File-Based Series](FILE_BASED_SERIES.md).
- Reference lines and shaded spans: [Reference Lines and Shaded Spans](REFERENCE_LINES_AND_SPANS.md).
- Text and arrows: [Text Annotations](TEXT_ANNOTATIONS.md).
